"""Connors RSI-2 mean-reversion strategy (long-only) — the bot's validated core.

Rules (daily bars):
  ENTRY  : close > SMA(trend) AND Wilder-RSI(2) < threshold   -> long, entered at
           the next session's open (market order).
  EXIT   : close > SMA(exit, default 5)  [primary, rule-based]
           OR price <= entry * (1 - stop_pct)  [disaster stop]
           OR held >= max_hold sessions.

Out-of-sample (2019-2024, 28 ETFs/large-caps, next-open entry, 8% stop, slippage):
  ~67.5% win rate, profit factor 1.27, +0.227%/trade. See memory/strategy.md.

Exits are rule-based (not a fixed take-profit), so positions are managed by the
daily routines via `should_exit`, not by a bracket TP. The disaster stop is the
only hard price level recorded on the trade.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import config
from strategy.indicators import wilder_rsi


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


@dataclass
class MeanRevSignal:
    symbol: str
    rsi: float
    entry_ref: float   # last daily close (reference; live entry is at market)
    stop_loss: float
    score: int


def compute_signal(symbol: str, daily: pd.DataFrame) -> dict | None:
    """Return a CONFIRMED setup dict if today's completed daily bar triggers an
    entry, else None. `daily` must have lowercase OHLCV columns and a date index."""
    n = config.MEANREV_TREND_SMA
    if daily is None or len(daily) < n + 2:
        return None

    close = daily["close"]
    rsi = wilder_rsi(close, config.MEANREV_RSI_PERIOD)
    sma_trend = _sma(close, n)

    last_close = float(close.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    if pd.isna(last_rsi) or pd.isna(sma_trend.iloc[-1]):
        return None

    in_uptrend = last_close > float(sma_trend.iloc[-1])
    oversold = last_rsi < config.MEANREV_RSI_THRESHOLD
    if not (in_uptrend and oversold):
        return None

    stop_loss = round(last_close * (1 - config.MEANREV_STOP_PCT), 4)
    # Score: more oversold -> higher conviction (kept above SCORE_THRESHOLD).
    score = int(min(100, 70 + (config.MEANREV_RSI_THRESHOLD - last_rsi) * 3))

    return {
        "symbol": symbol,
        "direction": "long",
        "entry_price": round(last_close, 4),
        "stop_loss": stop_loss,
        "take_profit": "",          # rule-based exit, no fixed TP
        "rr": "",
        "score": score,
        "sector": config.SECTOR_MAP.get(symbol, "etf"),
        "regime": "MEANREV",
        "rsi_value": round(last_rsi, 1),
        "reason": f"RSI2 {last_rsi:.1f} < {config.MEANREV_RSI_THRESHOLD}, close > SMA{n}",
        "status": "CONFIRMED",
        "strategy": "meanrev",
    }


def should_exit(daily: pd.DataFrame, trade: dict, days_held: int) -> tuple[bool, str]:
    """Decide whether an open mean-reversion position should be closed today."""
    if daily is None or len(daily) < config.MEANREV_EXIT_SMA + 1:
        return False, ""
    close = daily["close"]
    last_close = float(close.iloc[-1])
    sma_exit = float(_sma(close, config.MEANREV_EXIT_SMA).iloc[-1])

    try:
        stop = float(trade.get("stop_loss") or 0)
    except (TypeError, ValueError):
        stop = 0.0

    if stop and last_close <= stop:
        return True, "STOP HIT"
    if last_close > sma_exit:
        return True, f"RULE: close {last_close:.2f} > SMA{config.MEANREV_EXIT_SMA} {sma_exit:.2f}"
    if days_held >= config.MEANREV_MAX_HOLD:
        return True, f"MAX_HOLD {config.MEANREV_MAX_HOLD}d"
    return False, ""


def build_plan(watchlist: list[str], fetch_daily, max_positions: int = None) -> list[dict]:
    """Scan the watchlist for entry signals; return the most-oversold setups,
    capped at max_positions. `fetch_daily(symbol)` returns a daily OHLCV df or None."""
    cap = max_positions or config.MAX_CONCURRENT_POSITIONS
    setups = []
    for symbol in watchlist:
        try:
            daily = fetch_daily(symbol)
        except Exception:
            daily = None
        sig = compute_signal(symbol, daily)
        if sig:
            setups.append(sig)
    setups.sort(key=lambda s: s["score"], reverse=True)
    return setups[:cap]
