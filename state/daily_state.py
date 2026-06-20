import json
from datetime import date
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "memory" / "daily_plan.json"

_DEFAULT = {
    "date": "",
    "kill_switch": "ARMED",
    "daily_drawdown": 0.0,
    "regime": "NORMAL",
    "news_blocked": False,
    "setups": [],
    "trades_today": 0,
    "wins_today": 0,
    "losses_today": 0,
    "exposure_pct": 0.0,
    "open_sectors": [],
    "perplexity_calls_today": 0,
    "skipped_tickers": [],
    "watchlist": [],
}


def load_state() -> dict:
    today = date.today().isoformat()
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if state.get("date") == today:
            return state
    state = _DEFAULT.copy()
    state["date"] = today
    save_state(state)
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
