import config
from data.market_data import get_live_quote, fetch_bars_safe
from strategy.regime import get_regime
from memory.logger import log_execution_skip


def validate_entry(setup: dict, planned_regime: str) -> tuple[bool, str]:
    symbol = setup["symbol"]

    # 1. Live quote check
    try:
        quote = get_live_quote(symbol)
    except Exception as e:
        reason = f"Quote fetch failed: {e}"
        log_execution_skip(symbol, reason)
        return False, reason

    # 2. Spread OK (applies to every strategy)
    if quote["spread_pct"] > config.MAX_SPREAD_PCT:
        reason = f"Spread too wide: {quote['spread_pct']:.3f}% > {config.MAX_SPREAD_PCT}%"
        log_execution_skip(symbol, reason)
        return False, reason

    # Mean-reversion enters at market regardless of the exact price, so the
    # price-zone and regime-change checks (meant for the trend pullback) don't apply.
    if setup.get("strategy") == "meanrev":
        return True, "OK"

    # 3. Price in zone (±0.5% of entry) — trend setups only
    entry = setup["entry_price"]
    mid = quote["mid"]
    if abs(mid - entry) / entry > 0.005:
        reason = f"Price out of zone: current {mid:.2f} vs entry {entry:.2f}"
        log_execution_skip(symbol, reason)
        return False, reason

    # 4. Regime unchanged — trend setups only
    spy_d1 = fetch_bars_safe("SPY", "1Day", timeout_sec=1.0)
    if spy_d1 is not None:
        current_regime = get_regime(spy_d1)
        if current_regime != planned_regime:
            reason = f"Regime changed: was {planned_regime}, now {current_regime}"
            log_execution_skip(symbol, reason)
            return False, reason

    return True, "OK"
