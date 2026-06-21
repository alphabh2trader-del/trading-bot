"""ANALYSIS — monthly trend-timing rebalance (Faber GTAA).

Runs daily at 08:00 ET but only acts once per calendar month: it holds the ETFs
whose monthly close is above their 10-month SMA (equal weight, scaled by
TREND_EXPOSURE) and moves the rest to cash. Market orders queue for the open.
"""
from datetime import date

import config
from data.market_data import fetch_bars_safe
from strategy.trend_timing import target_portfolio_status, last_rebalance_month, mark_rebalanced
from execution.engine import rebalance_portfolio
from reporting.telegram import send_message

# If more than this fraction of the universe fails to return data, the month's
# signal is unreliable — abort the rebalance entirely and retry next run rather
# than trade on a partial picture.
_MAX_FAIL_FRACTION = 0.25


def _fetch_daily(symbol: str):
    # ~520 calendar days (>17 monthly bars) so the 10-month SMA always has enough
    # history; a slightly longer timeout reduces false "data unavailable" drops.
    return fetch_bars_safe(symbol, "1Day", timeout_sec=4.0, lookback_days=520)


def run(state: dict) -> None:
    state["setups"] = []  # trend timing has no per-day setups; open/midday/afternoon are no-ops

    this_month = date.today().strftime("%Y-%m")
    if last_rebalance_month() == this_month:
        return  # already rebalanced this month

    universe = config.TREND_UNIVERSE
    target, failed = target_portfolio_status(universe, _fetch_daily)

    # Abort on a data outage: do NOT mark the month done, so the next scheduled run
    # retries instead of trading (or liquidating) on incomplete information.
    if len(failed) > len(universe) * _MAX_FAIL_FRACTION:
        send_message(
            f"⚠ REBALANCE ABORTED — data unavailable for {len(failed)}/{len(universe)} ETFs "
            f"({', '.join(failed)}). Will retry on the next run; month NOT marked done."
        )
        return

    # Symbols we couldn't evaluate are protected from liquidation this run.
    actions = rebalance_portfolio(target, protect=set(failed))
    mark_rebalanced(this_month, list(target.keys()))
    state["holdings"] = list(target.keys())

    held = ", ".join(target.keys()) if target else "ALL CASH (no ETF in uptrend)"
    extra = ""
    if actions.get("resized"):
        extra += f" | Resized {len(actions['resized'])}"
    if actions.get("protected"):
        extra += f" | Protected {len(actions['protected'])} (no data)"
    send_message(
        f"📅 MONTHLY REBALANCE — {this_month} (exposure {config.TREND_EXPOSURE}x)\n"
        f"Holding {len(target)} ETFs: {held}\n"
        f"Bought {len(actions['bought'])} | Sold {len(actions['sold'])} | "
        f"Kept {len(actions['held'])}{extra}"
    )
