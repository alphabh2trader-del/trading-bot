"""REVIEW — 16:00 ET: EOD report, learning log, state reset."""
import csv
from datetime import date
from pathlib import Path

from execution.portfolio import get_daily_summary
from memory.learning import run_eod_learning
from memory.adaptive import run_adaptive_learning
from memory.logger import update_opportunity_outcome
from data.market_data import fetch_bars_safe
from reporting.eod_report import send_eod_report
from risk.risk_engine import update_drawdown

MEMORY_DIR = Path(__file__).parent.parent / "memory"
OPP_LOG = MEMORY_DIR / "opportunity_log.md"
TRADES_FILE = MEMORY_DIR / "trades.csv"


def _load_today_closed() -> list[dict]:
    today = date.today().isoformat()
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [
            r for r in csv.DictReader(f)
            if r.get("status") == "closed" and (r.get("exit_timestamp") or "").startswith(today)
        ]


def run(state: dict) -> None:
    # 1. Update drawdown
    update_drawdown(state)

    # 2. EOD Telegram report
    send_eod_report()

    # 3. Update opportunity log with today's outcomes
    trades_today = _load_today_closed()
    missed_symbols = []

    if OPP_LOG.exists():
        today = date.today().isoformat()
        lines = OPP_LOG.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if today in line and "REJECTED" in line:
                parts = line.split("—")
                if len(parts) >= 2:
                    sym = parts[1].replace("REJECTED", "").strip()
                    missed_symbols.append(sym)
                    try:
                        df = fetch_bars_safe(sym, "1Day", timeout_sec=1.0)
                        if df is not None and not df.empty:
                            eod_price = float(df.iloc[-1]["close"])
                            update_opportunity_outcome(sym, eod_price, 0.0, "long")
                    except Exception:
                        pass

    # 4. Learning log (Perplexity call #2)
    run_eod_learning(trades_today, missed_symbols, state)

    # 5. Adaptive parameter adjustment (runs after market close, never during trading)
    run_adaptive_learning(state)

    # 6. Reset daily counters (keep kill_switch if LOCKED)
    state["daily_drawdown"] = 0.0
    state["trades_today"] = 0
    state["wins_today"] = 0
    state["losses_today"] = 0
    state["exposure_pct"] = 0.0
    state["open_sectors"] = []
    state["setups"] = []
    state["news_blocked"] = False
    # perplexity_calls_today resets via new-day detection in load_state()
