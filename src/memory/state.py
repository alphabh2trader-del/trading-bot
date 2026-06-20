import json
import csv
import os
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"


def _path(filename: str) -> Path:
    return MEMORY_DIR / filename


def load_config() -> dict:
    with open(_path("config.json"), "r") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(_path("config.json"), "w") as f:
        json.dump(config, f, indent=2)


def update_memory(key: str, value: str) -> None:
    memory_file = _path("memory.md")
    content = memory_file.read_text(encoding="utf-8")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    content += f"\n## Update — {timestamp}\n\n- {key}: {value}\n"
    memory_file.write_text(content, encoding="utf-8")


def log_trade(trade: dict) -> None:
    trades_file = _path("trades.csv")
    file_exists = trades_file.exists() and trades_file.stat().st_size > 0
    fieldnames = [
        "trade_id", "timestamp", "symbol", "direction", "entry_price",
        "stop_loss", "take_profit", "position_size", "risk_pct", "status",
        "exit_price", "exit_timestamp", "pnl_pct", "pnl_usd", "notes"
    ]
    with open(trades_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: trade.get(k, "") for k in fieldnames})


def log_improvement(description: str) -> None:
    improvements_file = _path("improvements.md")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    entry = f"\n## {timestamp} — {description}\n\n"
    with open(improvements_file, "a", encoding="utf-8") as f:
        f.write(entry)


def get_open_trades() -> list[dict]:
    trades_file = _path("trades.csv")
    if not trades_file.exists():
        return []
    open_trades = []
    with open(trades_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "open":
                open_trades.append(row)
    return open_trades
