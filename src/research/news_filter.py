import os
import requests
from dotenv import load_dotenv

load_dotenv()

HIGH_IMPACT_KEYWORDS = [
    "CPI", "Consumer Price Index",
    "FOMC", "Federal Reserve", "Fed rate",
    "NFP", "Non-Farm Payroll", "nonfarm payroll",
    "GDP", "unemployment rate",
]

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def _perplexity_query(prompt: str) -> str:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise EnvironmentError("PERPLEXITY_API_KEY not set")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def get_upcoming_events() -> list[str]:
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    prompt = (
        f"Today is {today}. List only the high-impact US economic events scheduled today or tomorrow. "
        "Focus on: CPI, FOMC, NFP, Federal Reserve announcements, GDP. "
        "Reply with a comma-separated list of event names only. If none, reply: NONE"
    )
    raw = _perplexity_query(prompt)
    if "NONE" in raw.upper():
        return []
    found = []
    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword.lower() in raw.lower() and keyword not in found:
            found.append(keyword)
    return found


def is_high_impact_event_today() -> tuple[bool, list[str]]:
    events = get_upcoming_events()
    return len(events) > 0, events


def block_if_event() -> tuple[bool, str]:
    blocked, events = is_high_impact_event_today()
    if blocked:
        return True, f"Trading blocked: high-impact events detected: {', '.join(events)}"
    return False, "No high-impact events. Trading allowed."
