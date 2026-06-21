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

    candidates.sort(key=lambda s: s.score, reverse=True)
    return _top2_different_sectors(candidates)


def _top2_different_sectors(setups: list[Setup]) -> list[Setup]:
    result = []
    seen_sectors = set()
    for s in setups:
        if s.sector not in seen_sectors:
            result.append(s)
            seen_sectors.add(s.sector)
        if len(result) == 2:
            break
    return result


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
