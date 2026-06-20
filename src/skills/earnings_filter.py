"""
Skill: Earnings Filter
Blocks trade entries when a symbol has earnings announced within days_buffer days.
Uses yfinance to fetch the next earnings date — no API key required.
"""
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


def get_next_earnings_date(symbol: str):
    """Returns the next earnings date as a date object, or None if unavailable."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        if cal is None:
            return None

        # yfinance >= 0.2 returns a dict
        if isinstance(cal, dict):
            earnings = cal.get("Earnings Date")
            if earnings is None:
                return None
            # Can be a list of timestamps or a single value
            if hasattr(earnings, "__iter__") and not isinstance(earnings, str):
                dates = []
                for d in earnings:
                    if hasattr(d, "date"):
                        dates.append(d.date())
                    elif isinstance(d, date):
                        dates.append(d)
                return min(dates) if dates else None
            if hasattr(earnings, "date"):
                return earnings.date()
            return None

        # Older yfinance returns a DataFrame
        if hasattr(cal, "loc"):
            try:
                val = cal.loc["Earnings Date"].iloc[0]
                if hasattr(val, "date"):
                    return val.date()
            except Exception:
                pass

        return None

    except Exception as e:
        logger.warning(f"earnings_filter: could not fetch earnings for {symbol}: {e}")
        return None


def is_earnings_within(symbol: str, days_buffer: int = 3) -> tuple[bool, str]:
    """
    Returns (blocked, reason).
    blocked=True if the next earnings date is within days_buffer days from today.
    Fails open: if data is unavailable, the trade is NOT blocked.
    """
    earnings_date = get_next_earnings_date(symbol)

    if earnings_date is None:
        return False, ""

    today = date.today()
    days_until = (earnings_date - today).days

    if 0 <= days_until <= days_buffer:
        return True, f"Earnings in {days_until}d ({earnings_date})"

    return False, ""
