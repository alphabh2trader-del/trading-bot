"""Trend-timing strategy (Faber GTAA) — the bot's validated, cost-robust core.

Monthly rebalance across a diversified ETF set (equities + bonds + gold):
  HOLD an ETF when its monthly close > its 10-month SMA (i.e. in an uptrend);
  otherwise that sleeve goes to CASH. Capital is split equally across the ETFs
  currently held, scaled by EXPOSURE.

Why this and not RSI-2: mean reversion's ~0.2%/trade edge did not survive realistic
fees + slippage + survivorship-free testing. Trend timing trades rarely and rides
large moves, so costs are negligible; it is profitable across EVERY period
2008-2025 (incl. GFC, 2022 bear) and cuts drawdown to ~half of buy & hold.

Out-of-sample / full-history (ETF-only, 0.30% turnover cost), exposure 1.0:
  CAGR ~10.5%, max drawdown ~24%, Sharpe ~0.79, positive in all sub-periods.
See memory/strategy.md and `python -m backtest.momentum`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import config

# Persistent across daily state resets and CI runs (committed under memory/).
_REBAL_FILE = Path(__file__).parent.parent / "memory" / "trend_state.json"


def last_rebalance_month() -> str:
    if _REBAL_FILE.exists():
        try:
            return json.loads(_REBAL_FILE.read_text(encoding="utf-8")).get("last_rebalance", "")
        except Exception:
            return ""
    return ""


def mark_rebalanced(month: str, holdings: list[str]) -> None:
    _REBAL_FILE.write_text(
        json.dumps({"last_rebalance": month, "holdings": holdings}, indent=2),
        encoding="utf-8",
    )


def _qualifies(daily: pd.DataFrame) -> bool:
    """True if the latest monthly close is above the 10-month SMA."""
    if daily is None or len(daily) < config.TREND_SMA_DAYS + 5:
        return False
    monthly = daily["close"].resample("ME").last()
    if len(monthly) < config.TREND_SMA_MONTHS + 1:
        return False
    sma = monthly.rolling(config.TREND_SMA_MONTHS).mean()
    return bool(monthly.iloc[-1] > sma.iloc[-1])


def _scan_universe(universe: list[str], fetch_daily, exposure: float = None):
    """Single pass over the universe.

    Returns (weights, failed) where:
      - weights: {symbol: target_weight} for ETFs currently in an uptrend,
        equal-weighted and scaled by EXPOSURE. Empty means 'all cash'.
      - failed:  symbols whose data could NOT be fetched (timeout/exception).
        These are UNKNOWN, not bearish — callers must not treat them as exits.
    """
    exp = config.TREND_EXPOSURE if exposure is None else exposure
    held: list[str] = []
    failed: list[str] = []
    for symbol in universe:
        try:
            daily = fetch_daily(symbol)
        except Exception:
            daily = None
        if daily is None:
            # Could not evaluate this symbol (data hiccup) — flag it, don't drop it.
            failed.append(symbol)
            continue
        if _qualifies(daily):
            held.append(symbol)
    weights: dict = {}
    if held:
        weight = exp / len(held)
        weights = {symbol: round(weight, 4) for symbol in held}
    return weights, failed


def target_portfolio(universe: list[str], fetch_daily, exposure: float = None) -> dict:
    """Return {symbol: target_weight} for the ETFs currently in an uptrend,
    equal-weighted and scaled by EXPOSURE. Empty dict means 'all cash'."""
    weights, _ = _scan_universe(universe, fetch_daily, exposure)
    return weights


def target_portfolio_status(universe: list[str], fetch_daily, exposure: float = None):
    """Like target_portfolio but also returns the list of symbols whose data could
    not be fetched, so the rebalance can abort/protect instead of liquidating on a
    transient data outage. Returns (weights, failed)."""
    return _scan_universe(universe, fetch_daily, exposure)
