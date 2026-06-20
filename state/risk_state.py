import csv
from datetime import date
from pathlib import Path

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"


def get_daily_pnl_pct() -> float:
    today = date.today().isoformat()
    if not TRADES_FILE.exists():
        return 0.0
    total = 0.0
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("exit_timestamp") or "").startswith(today):
                try:
                    total += float(row.get("pnl_pct", 0))
                except ValueError:
                    pass
    return total


def get_open_positions() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "open"]


def get_open_exposure_pct(equity: float) -> float:
    if equity <= 0:
        return 0.0
    total_value = sum(
        float(p.get("position_size", 0)) * float(p.get("entry_price", 0))
        for p in get_open_positions()
    )
    return total_value / equity * 100
