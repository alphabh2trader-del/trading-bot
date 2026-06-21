"""ANALYSIS — 08:00 ET: build the day's plan for BOTH strategy sleeves.

Two strategies run on one Alpaca account, on disjoint universes:

  • SWING sleeve (70% of capital, DAILY): scans config.SWING_WATCHLIST (stocks)
    with the D1-trend / H4-pullback scorer and writes the day's setups to state.
    open/midday/afternoon then execute and manage them.

  • TREND sleeve (30% of capital, MONTHLY): Faber GTAA ETF rebalance — holds each
    ETF whose monthly close is above its 10-month SMA. Acts at most once per
    calendar month (guarded by memory/trend_state.json) and is scoped to the ETF
    universe + 30% capital so it never touches the swing stock positions.
"""
from datetime import date

import config
from data.market_data import fetch_bars_safe
from decision.planner import build_plan, setups_to_dict
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
    # ---------------------------------------------------------------- SWING sleeve
    if config.SWING_ENABLED:
        from data.universe import get_watchlist
        from strategy.regime import get_regime

        # Compute the market regime from SPY ONCE here and store it, so the whole day
        # agrees on it: build_plan blocks on EXTREME and scores the regime bonus, and
        # validate_entry (at execution) only rejects on a regime *change* since the plan.
        # Without this, regime defaulted to NORMAL and the validator rejected entries
        # whenever SPY was actually trending (TREND != NORMAL) — self-defeating.
        spy_d1 = _fetch_daily("SPY")
        regime = get_regime(spy_d1) if spy_d1 is not None else state.get("regime", "NORMAL")
        state["regime"] = regime

        # Use premarket's liquidity-filtered list when available (falls back to
        # config.SWING_WATCHLIST if premarket didn't run, e.g. a manual analysis run).
        watchlist = get_watchlist(state)
        setups = build_plan(watchlist, regime)
        state["setups"] = setups_to_dict(setups)
        if setups:
            top = setups[0]
            send_message(
                f"🔎 SWING PLAN — {len(setups)} setup(s) qualified (regime {regime})\n"
                f"Top: {top.symbol} {top.direction.upper()} | score {top.score} | "
                f"R:R {top.rr} | entry {top.entry_price}"
            )
        else:
            send_message(f"🔎 SWING PLAN — no qualifying setups today (regime {regime}).")
    else:
        state["setups"] = []

    # ---------------------------------------------------------------- TREND sleeve
    if config.TREND_TIMING_ENABLED:
        _rebalance_trend(state)


def _rebalance_trend(state: dict) -> None:
    this_month = date.today().strftime("%Y-%m")
    if last_rebalance_month() == this_month:
        return  # already rebalanced this month

    universe = config.TREND_UNIVERSE
    target, failed = target_portfolio_status(universe, _fetch_daily)

    # Abort on a data outage: do NOT mark the month done, so the next scheduled run
    # retries instead of trading (or liquidating) on incomplete information.
    if len(failed) > len(universe) * _MAX_FAIL_FRACTION:
        send_message(
            f"⚠ TREND REBALANCE ABORTED — data unavailable for {len(failed)}/{len(universe)} ETFs "
            f"({', '.join(failed)}). Will retry on the next run; month NOT marked done."
        )
        return

    # Scope to the ETF universe + 30% capital sleeve so swing stock positions are
    # never touched; protect symbols we couldn't evaluate from liquidation this run.
    actions = rebalance_portfolio(
        target,
        protect=set(failed),
        capital_frac=config.TREND_CAPITAL_ALLOCATION,
        universe=set(universe),
    )
    mark_rebalanced(this_month, list(target.keys()))
    state["holdings"] = list(target.keys())

    held = ", ".join(target.keys()) if target else "ALL CASH (no ETF in uptrend)"
    extra = ""
    if actions.get("resized"):
        extra += f" | Resized {len(actions['resized'])}"
    if actions.get("protected"):
        extra += f" | Protected {len(actions['protected'])} (no data)"
    send_message(
        f"📅 MONTHLY TREND REBALANCE — {this_month} "
        f"(30% sleeve, exposure {config.TREND_EXPOSURE}x)\n"
        f"Holding {len(target)} ETFs: {held}\n"
        f"Bought {len(actions['bought'])} | Sold {len(actions['sold'])} | "
        f"Kept {len(actions['held'])}{extra}"
    )
