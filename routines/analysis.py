"""ANALYSIS — 08:00 ET: compute regime, score tickers, write daily plan."""
from data.market_data import fetch_bars_safe
from data.universe import get_watchlist
from strategy.regime import get_regime
from decision.planner import build_plan, setups_to_dict
from reporting.telegram import send_message


def run(state: dict) -> None:
    # 1. Get market regime from SPY
    spy_d1 = fetch_bars_safe("SPY", "1Day", timeout_sec=2.0)
    regime = get_regime(spy_d1) if spy_d1 is not None else "NORMAL"
    state["regime"] = regime

    if regime == "EXTREME":
        send_message(f"ANALYSIS: Market regime = EXTREME. No new trades today.")
        state["setups"] = []
        return

    # 2. Score all tickers
    watchlist = get_watchlist(state)
    setups = build_plan(watchlist, regime)
    state["setups"] = setups_to_dict(setups)

    if not setups:
        send_message(f"ANALYSIS done. Regime: {regime}. No setups qualified today.")
        return

    summary = " | ".join(f"{s.symbol} {s.score}" for s in setups)
    send_message(f"ANALYSIS done. Regime: {regime}. {len(setups)} setup(s): {summary}")
