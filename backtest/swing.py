"""Swing-sleeve backtest — validates the D1-trend / pullback system with fees.

The live swing sleeve (strategy/scorer.py) enters on H4 bars, but free intraday
history only goes back ~60 days — far too short to measure an edge. So this harness
replays the SAME rules on DAILY bars over several years as a faithful proxy:

  trend   : close > EMA200  -> long bias ; close < EMA200 -> short bias
  pullback: price within PULLBACK_BAND of EMA50
  momentum: RSI(14) in the entry zone and turning the right way
  structure: swing structure agrees with the direction
  stop    : ATR(14) * mult from entry  ;  target: TP_R_MULT * risk
  exit    : first of TP / SL (intrabar) or MAX_HOLD days

It is an ACCOUNT-LEVEL simulator: 1% risk per trade, the 6% open-risk budget, and
realistic round-trip costs (commission-free equities + slippage). Output = win rate,
profit factor, avg R, monthly return, CAGR, max drawdown — i.e. the numbers needed to
judge the "X% per month" goal honestly, net of fees.

Usage:  python -m backtest.swing
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import config
from strategy.indicators import ema, rsi, atr, detect_structure

# --- Backtest knobs (mirror live config where it exists) ---
PULLBACK_BAND = 0.015          # daily bars are coarser than H4 -> slightly looser than live 0.008
ATR_MULT = config.ATR_STOP_MULT
TP_R_MULT = config.TP_R_MULT
MAX_HOLD = 12                  # trading days
RISK_PCT = config.MAX_RISK_PER_TRADE / 100.0
RISK_BUDGET = config.MAX_OPEN_RISK_PCT / 100.0
COST_ROUNDTRIP = 0.0010        # ~0.05%/side: commission-free equities + slippage


def load_ohlc(symbols, start, end) -> dict:
    import yfinance as yf
    raw = yf.download(symbols, start=start, end=end, progress=False, auto_adjust=True)
    out = {}
    for s in symbols:
        try:
            df = pd.DataFrame({
                "open": raw["Open"][s], "high": raw["High"][s],
                "low": raw["Low"][s], "close": raw["Close"][s],
                "volume": raw["Volume"][s],
            }).dropna()
        except Exception:
            continue
        if len(df) > 250:
            out[s] = df
    return out


def _signal(df: pd.DataFrame, i: int):
    """Return (direction, entry, stop, tp) for a setup at bar i, or None.
    Only uses data up to and including bar i (no lookahead)."""
    if i < 200:
        return None
    win = df.iloc[: i + 1]
    close = win["close"]
    ema200 = ema(close, 200).iloc[-1]
    ema50 = ema(close, 50).iloc[-1]
    rsi14 = rsi(close, 14)
    last_rsi, prev_rsi = rsi14.iloc[-1], rsi14.iloc[-2]
    atr14 = atr(win, 14).iloc[-1]
    last = win.iloc[-1]

    if np.isnan(ema200) or np.isnan(atr14) or np.isnan(last_rsi):
        return None

    above = last["close"] > ema200
    near_ema50 = abs(last["close"] - ema50) / ema50 < PULLBACK_BAND
    structure = detect_structure(win)

    if above and structure == "bullish":
        direction = "long"
    elif (not above) and structure == "bearish":
        direction = "short"
    else:
        return None

    rsi_ok = (direction == "long" and 38 <= last_rsi <= 58 and last_rsi > prev_rsi) or \
             (direction == "short" and 42 <= last_rsi <= 62 and last_rsi < prev_rsi)
    if not rsi_ok or not near_ema50:
        return None

    entry = last["close"]
    if direction == "long":
        stop = min(last["low"] * 0.999, entry - ATR_MULT * atr14)
        tp = entry + (entry - stop) * TP_R_MULT
    else:
        stop = max(last["high"] * 1.001, entry + ATR_MULT * atr14)
        tp = entry - (stop - entry) * TP_R_MULT
    if abs(entry - stop) <= 0:
        return None
    return direction, float(entry), float(stop), float(tp)


def _exit(df: pd.DataFrame, entry_i: int, direction: str, stop: float, tp: float):
    """Walk forward from entry_i+1; return (exit_price, R_multiple, bars_held)."""
    risk = abs(df.iloc[entry_i]["close"] - stop)
    for j in range(entry_i + 1, min(entry_i + 1 + MAX_HOLD, len(df))):
        bar = df.iloc[j]
        if direction == "long":
            if bar["low"] <= stop:
                return stop, -1.0, j - entry_i
            if bar["high"] >= tp:
                return tp, TP_R_MULT, j - entry_i
        else:
            if bar["high"] >= stop:
                return stop, -1.0, j - entry_i
            if bar["low"] <= tp:
                return tp, TP_R_MULT, j - entry_i
    # Time stop — exit at last available close
    j = min(entry_i + MAX_HOLD, len(df) - 1)
    exit_px = df.iloc[j]["close"]
    entry_px = df.iloc[entry_i]["close"]
    r = ((exit_px - entry_px) if direction == "long" else (entry_px - exit_px)) / risk
    return float(exit_px), float(r), j - entry_i


def simulate(data: dict) -> dict:
    """Account-level event simulation across all symbols on a shared 1%/6% risk budget."""
    # Build a unified trading calendar.
    all_dates = sorted(set().union(*[set(df.index) for df in data.values()]))
    pos_index = {s: {d: k for k, d in enumerate(df.index)} for s, df in data.items()}

    equity = 1.0
    open_risk = 0.0
    open_trades = []          # list of dicts: symbol, entry_i, dir, stop, tp, exit_date
    closed = []               # realized R + cost per trade
    equity_curve = {}
    held_symbols = set()

    for d in all_dates:
        # 1. Close any trades whose exit date is today.
        for t in list(open_trades):
            if t["exit_date"] == d:
                r = t["R"]
                # Round-trip cost as a fraction of equity: notional = risk/stop_dist*entry.
                lev = t["entry"] / abs(t["entry"] - t["stop"])
                cost = RISK_PCT * lev * COST_ROUNDTRIP
                pnl = r * RISK_PCT - cost
                equity *= (1 + pnl)
                open_risk -= RISK_PCT
                held_symbols.discard(t["symbol"])
                open_trades.remove(t)
                closed.append({"R": r, "pnl": pnl, "win": r > 0})

        # 2. Scan for new entries (sorted for determinism), respect the risk budget.
        for s in sorted(data.keys()):
            if open_risk + RISK_PCT > RISK_BUDGET + 1e-9:
                break
            if s in held_symbols:
                continue
            df = data[s]
            i = pos_index[s].get(d)
            if i is None or i < 200 or i >= len(df) - 1:
                continue
            sig = _signal(df, i)
            if not sig:
                continue
            direction, entry, stop, tp = sig
            exit_px, r, bars = _exit(df, i, direction, stop, tp)
            exit_date = df.index[min(i + bars, len(df) - 1)]
            open_trades.append({
                "symbol": s, "entry": entry, "stop": stop, "tp": tp,
                "dir": direction, "R": r, "exit_date": exit_date,
            })
            open_risk += RISK_PCT
            held_symbols.add(s)

        equity_curve[d] = equity

    eq = pd.Series(equity_curve)
    return _summary(eq, closed)


def _summary(eq: pd.Series, closed: list) -> dict:
    if not closed or len(eq) < 2:
        return {"trades": 0}
    wins = [t for t in closed if t["win"]]
    losses = [t for t in closed if not t["win"]]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else 0
    monthly = (1 + cagr) ** (1 / 12) - 1
    dd = (eq / eq.cummax() - 1).min()
    return {
        "trades": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "avg_R": round(np.mean([t["R"] for t in closed]), 2),
        "total_return_pct": round((eq.iloc[-1] - 1) * 100, 1),
        "cagr_pct": round(cagr * 100, 2),
        "monthly_pct": round(monthly * 100, 2),
        "max_dd_pct": round(abs(dd) * 100, 1),
        "final_equity": round(eq.iloc[-1], 3),
        "years": round(years, 1),
    }


def main():
    symbols = config.SWING_WATCHLIST
    start, end = "2021-01-01", "2026-06-01"
    print(f"Loading {len(symbols)} swing symbols {start}..{end} (daily)...")
    data = load_ohlc(symbols, start, end)
    print(f"  loaded {len(data)} symbols with sufficient history\n")

    res = simulate(data)
    print("=" * 60)
    print("SWING SLEEVE BACKTEST (daily proxy, net of fees)")
    print("=" * 60)
    if res.get("trades", 0) == 0:
        print("  No trades generated.")
        return res
    for k in ["trades", "win_rate", "profit_factor", "avg_R", "monthly_pct",
              "cagr_pct", "total_return_pct", "max_dd_pct", "final_equity", "years"]:
        print(f"  {k:<16}: {res[k]}")

    _write_report(res, start, end, len(data))
    return res


def _write_report(res: dict, start: str, end: str, n: int) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Swing-Sleeve Backtest — dual_swing+trend_v1 — {stamp}",
        "",
        "Daily-bar proxy of the live D1-trend / H4-pullback system (free intraday",
        "history is too short to backtest H4 directly). Account-level sim: 1% risk/trade,",
        f"6% open-risk budget, round-trip cost {COST_ROUNDTRIP*100:.2f}% (fees + slippage).",
        "",
        f"- Universe: {n} liquid large-caps (config.SWING_WATCHLIST)",
        f"- Period: {start} -> {end} ({res['years']} yrs)",
        f"- Stop: ATR(14) x {ATR_MULT} | Target: {TP_R_MULT}R | Max hold: {MAX_HOLD} days",
        "",
        "## Results (net of fees)",
        "",
        f"- Trades: {res['trades']}",
        f"- Win rate: {res['win_rate']}%",
        f"- Profit factor: {res['profit_factor']}",
        f"- Avg R: {res['avg_R']}",
        f"- **Return: {res['monthly_pct']}%/month  ({res['cagr_pct']}%/yr)**",
        f"- Max drawdown: {res['max_dd_pct']}%",
        f"- Final equity (from 1.0): {res['final_equity']}",
        "",
        "Note: a daily-bar approximation tends to UNDERSTATE an intraday-entry edge",
        "(coarser pullback timing, wider effective stops). Reproduce: `python -m backtest.swing`.",
    ]
    out = Path(__file__).parent.parent / "memory" / "backtests"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"swing_backtest_{stamp}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport -> {path}")


if __name__ == "__main__":
    main()
