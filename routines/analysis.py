"""ANALYSIS — monthly trend-timing rebalance (Faber GTAA).

Runs daily at 08:00 ET but only acts once per calendar month: it holds the ETFs
whose monthly close is above their 10-month SMA (equal weight, scaled by
TREND_EXPOSURE) and moves the rest to cash. Market orders queue for the open.
"""
from datetime import date

import config
from data.market_data import fetch_bars_safe
from strategy.trend_timing import target_portfolio, last_rebalance_month, mark_rebalanced
from execution.engine import rebalance_portfolio
from reporting.telegram import send_message


def _fetch_daily(symbol: str):
    return fetch_bars_safe(symbol, "1Day", timeout_sec=3.0)


def run(state: dict) -> None:
    state["setups"] = []  # trend timing has no per-day setups; open/midday/afternoon are no-ops

    this_month = date.today().strftime("%Y-%m")
    if last_rebalance_month() == this_month:
        return  # already rebalanced this month

    target = target_portfolio(config.TREND_UNIVERSE, _fetch_daily)
    actions = rebalance_portfolio(target)
    mark_rebalanced(this_month, list(target.keys()))
    state["holdings"] = list(target.keys())

    held = ", ".join(target.keys()) if target else "ALL CASH (no ETF in uptrend)"
    send_message(
        f"📅 MONTHLY REBALANCE — {this_month} (exposure {config.TREND_EXPOSURE}x)\n"
        f"Holding {len(target)} ETFs: {held}\n"
        f"Bought {len(actions['bought'])} | Sold {len(actions['sold'])} | Kept {len(actions['held'])}"
    )
