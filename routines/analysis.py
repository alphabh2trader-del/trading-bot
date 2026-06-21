"""ANALYSIS — 08:00 ET: scan watchlist for Connors RSI-2 mean-reversion setups.

Signals are computed on completed daily bars; entries are taken at the next
session by the `open` routine. The EXTREME-regime guard still blocks all new
trades during market panics (capital preservation).
"""
from data.market_data import fetch_bars_safe
from data.universe import get_watchlist
from strategy.regime import get_regime
from strategy.mean_reversion import build_plan
from reporting.telegram import send_message


def _fetch_daily(symbol: str):
    return fetch_bars_safe(symbol, "1Day", timeout_sec=3.0)


def run(state: dict) -> None:
    # 1. Market regime from SPY — block new entries in EXTREME conditions
    spy_d1 = fetch_bars_safe("SPY", "1Day", timeout_sec=3.0)
    regime = get_regime(spy_d1) if spy_d1 is not None else "NORMAL"
    state["regime"] = regime

    if regime == "EXTREME":
        send_message("ANALYSIS: Market regime = EXTREME. No new trades today.")
        state["setups"] = []
        return

    # 2. Scan for oversold mean-reversion setups (top N by conviction)
    watchlist = get_watchlist(state)
    setups = build_plan(watchlist, _fetch_daily)
    state["setups"] = setups

    if not setups:
        send_message(f"ANALYSIS done. Regime: {regime}. No oversold setups today.")
        return

    summary = " | ".join(f"{s['symbol']} RSI{s['rsi_value']} (sc {s['score']})" for s in setups)
    send_message(f"ANALYSIS done. Regime: {regime}. {len(setups)} setup(s): {summary}")
