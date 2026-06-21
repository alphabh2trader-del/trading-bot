"""Backtest engine — replays the live strategy (strategy.scorer.calculate_score)
over historical D1/H4 bars and measures the actual edge: how often qualified
setups reach their take-profit before their stop-loss.

The engine is data-source agnostic: pass in D1 and H4 DataFrames (DatetimeIndex,
columns open/high/low/close/volume). `backtest/run.py` wires it to Alpaca; tests
inject synthetic frames. No account or broker is involved here — results are
expressed in R-multiples (reward/risk units) so they are equity-independent.
"""
from __future__ import annotations

import pandas as pd

import config
from strategy.scorer import calculate_score


def simulate_symbol(
    symbol: str,
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    regime: str = "NORMAL",
    score_threshold: int | None = None,
) -> list[dict]:
    """Walk the H4 series forward; whenever a qualified setup appears and no
    position is open, enter and hold until TP or SL is touched. Returns a list
    of closed-trade records."""
    threshold = config.SCORE_THRESHOLD if score_threshold is None else score_threshold
    trades: list[dict] = []

    i = 50
    n = len(h4)
    while i < n:
        d1_slice = d1[d1.index <= h4.index[i]]
        if len(d1_slice) < 200:
            i += 1
            continue

        h4_slice = h4.iloc[: i + 1]
        setup = calculate_score(symbol, d1_slice, h4_slice, regime)
        if setup is None or setup.score < threshold:
            i += 1
            continue

        exit_idx, outcome, exit_price = _walk_to_exit(h4, i, setup)
        if outcome is None:
            break  # ran out of data while in a position

        risk = abs(setup.entry_price - setup.stop_loss)
        pnl = (exit_price - setup.entry_price) if setup.direction == "long" \
            else (setup.entry_price - exit_price)
        pnl_r = pnl / risk if risk > 0 else 0.0
        pnl_pct = pnl / setup.entry_price * 100 if setup.entry_price else 0.0

        trades.append({
            "symbol": symbol,
            "direction": setup.direction,
            "entry_time": str(h4.index[i]),
            "exit_time": str(h4.index[exit_idx]),
            "entry_price": round(setup.entry_price, 4),
            "stop_loss": round(setup.stop_loss, 4),
            "take_profit": round(setup.take_profit, 4),
            "exit_price": round(exit_price, 4),
            "score": setup.score,
            "rr": setup.rr,
            "outcome": outcome,
            "pnl_r": round(pnl_r, 3),
            "pnl_pct": round(pnl_pct, 3),
        })

        i = exit_idx + 1  # no overlapping positions per symbol

    return trades


def _walk_to_exit(h4: pd.DataFrame, entry_i: int, setup) -> tuple[int, str | None, float]:
    """From the bar after entry, find the first bar that touches SL or TP.
    If a single bar straddles both, SL is assumed hit first (conservative)."""
    sl, tp = setup.stop_loss, setup.take_profit
    for j in range(entry_i + 1, len(h4)):
        bar = h4.iloc[j]
        if setup.direction == "long":
            if bar["low"] <= sl:
                return j, "SL", sl
            if bar["high"] >= tp:
                return j, "TP", tp
        else:
            if bar["high"] >= sl:
                return j, "SL", sl
            if bar["low"] <= tp:
                return j, "TP", tp
    return len(h4) - 1, None, float("nan")


def compute_stats(trades: list[dict]) -> dict:
    """Aggregate performance metrics over a list of closed trades."""
    n = len(trades)
    if n == 0:
        return {
            "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "profit_factor": 0.0, "expectancy_r": 0.0, "total_r": 0.0,
            "max_drawdown_r": 0.0,
        }

    wins = [t for t in trades if t["pnl_r"] > 0]
    losses = [t for t in trades if t["pnl_r"] <= 0]
    gross_profit = sum(t["pnl_r"] for t in wins)
    gross_loss = abs(sum(t["pnl_r"] for t in losses))
    total_r = sum(t["pnl_r"] for t in trades)

    # Max drawdown on the cumulative-R equity curve.
    peak = 0.0
    cum = 0.0
    max_dd = 0.0
    for t in trades:
        cum += t["pnl_r"]
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / n * 100, 1),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "expectancy_r": round(total_r / n, 3),
        "total_r": round(total_r, 2),
        "max_drawdown_r": round(max_dd, 2),
    }
