import config
from data.market_data import fetch_bars_safe, data_age_minutes
from strategy.scorer import calculate_score, Setup
from memory.logger import log_opportunity
from src.skills.earnings_filter import is_earnings_within


def build_plan(watchlist: list[str], regime: str) -> list[Setup]:
    if regime == "EXTREME":
        return []

    threshold = config.SCORE_THRESHOLD
    candidates: list[Setup] = []

    for symbol in watchlist:
        d1 = fetch_bars_safe(symbol, "1Day", timeout_sec=1.0)
        h4 = fetch_bars_safe(symbol, "4Hour", timeout_sec=1.0)

        if d1 is None or h4 is None:
            log_opportunity(symbol, score=0, reason="TIMEOUT — data fetch failed")
            continue

        if data_age_minutes(h4) > config.DATA_FRESHNESS_MAX_MIN:
            log_opportunity(symbol, score=0, reason=f"STALE DATA — age {data_age_minutes(h4):.1f} min")
            continue

        setup = calculate_score(symbol, d1, h4, regime)

        if setup is None:
            log_opportunity(symbol, score=0, reason="No valid setup (direction/RSI/proximity filter)")
            continue

        if setup.score < threshold:
            log_opportunity(symbol, score=setup.score, reason=f"Score {setup.score} below threshold {threshold}")
            continue

        # Earnings filter — skip setups with earnings within the buffer window
        blocked, ereason = is_earnings_within(symbol, days_buffer=config.EARNINGS_BUFFER_DAYS)
        if blocked:
            log_opportunity(symbol, score=setup.score, reason=f"Earnings block: {ereason}")
            continue

        candidates.append(setup)

    # Return ALL qualifying setups, best score first. We no longer cap to the top-2
    # (user decision 2026-06-21): a good opportunity should never be dropped just to
    # respect a count. Execution gates the list by the open-risk budget and the
    # per-sector cap (risk/risk_engine.py), so concentration stays bounded without
    # throwing away signal here.
    candidates.sort(key=lambda s: s.score, reverse=True)
    return candidates


def setups_to_dict(setups: list[Setup]) -> list[dict]:
    return [
        {
            "symbol": s.symbol,
            "direction": s.direction,
            "entry_price": s.entry_price,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "rr": s.rr,
            "score": s.score,
            "sector": s.sector,
            "regime": s.regime,
            "rsi_value": s.rsi_value,
            "reason": s.reason,
            "status": "CONFIRMED",
        }
        for s in setups
    ]
