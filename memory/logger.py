from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "memory"

EXEC_LOG   = MEMORY_DIR / "execution_log.md"
OPP_LOG    = MEMORY_DIR / "opportunity_log.md"
LEARN_LOG  = MEMORY_DIR / "learning_log.md"


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def log_execution_entry(setup: dict, trade: dict, equity: float) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    _append(EXEC_LOG, f"""
## {ts} — {setup['direction'].upper()} {setup['symbol']} [PAPER]

Score: {setup['score']} | Regime: {setup['regime']} | R:R: {setup['rr']}

Entry: ${trade['entry_price']} | SL: ${trade['stop_loss']} | TP: ${trade['take_profit']}
Size: {trade['position_size']} shares | Risk: ${trade['risk_usd']} (1%) | Potential: ${trade['potential_usd']}
RSI: {setup['rsi_value']} | Sector: {setup['sector']}
Reason: {setup['reason']}
""")


def log_execution_skip(symbol: str, reason: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    _append(EXEC_LOG, f"## {ts} — SKIP {symbol}\nReason: {reason}\n")


def log_opportunity(symbol: str, score: int, reason: str, price: float | None = None) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    price_str = f" | Price at rejection: ${price:.2f}" if price else ""
    _append(OPP_LOG, f"## {ts} — REJECTED {symbol}\nScore: {score} | {reason}{price_str}\n")


def update_opportunity_outcome(symbol: str, eod_price: float, rejected_price: float, direction: str) -> None:
    if rejected_price <= 0:
        return
    move_pct = (eod_price - rejected_price) / rejected_price * 100
    if direction == "short":
        move_pct = -move_pct
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    _append(OPP_LOG, f"  → EOD outcome {ts}: price moved {move_pct:+.2f}% in expected direction\n")


def log_learning(insight: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    _append(LEARN_LOG, f"\n## {ts}\n\n{insight}\n")
