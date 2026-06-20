"""
Skill: News Filtering
Blocks trading during CPI, FOMC, NFP and other high-impact events.
"""
from src.research.news_filter import block_if_event, get_upcoming_events, is_high_impact_event_today


def check_and_block() -> tuple[bool, str]:
    """
    Call this before any trade attempt.
    Returns (blocked: bool, reason: str).
    """
    return block_if_event()


def get_today_events() -> list[str]:
    return get_upcoming_events()


def is_safe_to_trade() -> bool:
    blocked, _ = block_if_event()
    return not blocked


def filter_report() -> dict:
    blocked, reason = block_if_event()
    events = get_today_events()
    return {
        "blocked": blocked,
        "reason": reason,
        "events_detected": events,
    }
