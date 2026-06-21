import csv
import json
from datetime import date
from pathlib import Path

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"
EQUITY_STATE_FILE = Path(__file__).parent.parent / "memory" / "equity_state.json"


def update_total_drawdown(equity: float) -> float:
    """Track peak account equity (persisted across runs) and return the current
    account-level drawdown from peak, as a positive percentage."""
    if equity <= 0:
        return 0.0
    data = {}
    if EQUITY_STATE_FILE.exists():
        try:
            data = json.loads(EQUITY_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    peak = max(float(data.get("peak_equity", 0.0)), equity)
    data["peak_equity"] = peak
    data["last_equity"] = equity
    EQUITY_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return (peak - equity) / peak * 100 if peak > 0 else 0.0


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
