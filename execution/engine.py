import csv
import uuid
from datetime import datetime
from pathlib import Path

import config
from data.market_data import get_live_quote
from src.execution.alpaca_bridge import get_account, submit_bracket_order, submit_market_order, close_position
from memory.logger import log_execution_entry
from memory.trade_schema import TRADE_FIELDNAMES as FIELDNAMES

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"


def open_paper_trade(setup: dict, risk_multiplier: float = 1.0) -> dict:
    account = get_account()
    equity = account["equity"]
    entry = setup["entry_price"]
    sl = setup["stop_loss"]
    tp = setup["take_profit"]
    risk_per_share = abs(entry - sl)
    risk_usd = equity * (config.MAX_RISK_PER_TRADE / 100) * risk_multiplier
    size = round(risk_usd / risk_per_share, 2) if risk_per_share > 0 else 0

    is_meanrev = setup.get("strategy") == "meanrev"
    if is_meanrev:
        # Mean reversion: market entry, no bracket TP (exit is rule-based and
        # managed by the daily routines). The disaster stop is software-managed.
        try:
            order = submit_market_order(setup["symbol"], size, setup["direction"])
            alpaca_order_id = order["order_id"]
        except Exception as e:
            alpaca_order_id = f"ERROR:{e}"
        tp_value = ""
        potential = ""
        notes = f"meanrev | {setup.get('reason', '')}"
    else:
        # Trend setups: bracket order — TP and SL handled automatically by Alpaca.
        try:
            order = submit_bracket_order(
                symbol=setup["symbol"], qty=size, side=setup["direction"],
                take_profit_price=tp, stop_loss_price=sl,
            )
            alpaca_order_id = order["order_id"]
        except Exception as e:
            alpaca_order_id = f"ERROR:{e}"
        tp_value = tp
        potential = round(size * abs(tp - entry), 2)
        notes = setup.get("reason", "")

    trade = {
        "trade_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": setup["symbol"],
        "direction": setup["direction"],
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit": tp_value,
        "position_size": size,
        "risk_pct": config.MAX_RISK_PER_TRADE,
        "risk_usd": round(risk_usd, 2),
        "potential_usd": potential,
        "status": "open",
        "exit_price": "",
        "exit_timestamp": "",
        "pnl_pct": "",
        "pnl_usd": "",
        "fees_usd": "",
        "net_pnl_usd": "",
        "alpaca_order_id": alpaca_order_id,
        "notes": notes,
    }

    _append_trade(trade)
    log_execution_entry(setup, trade, equity)
    return trade


def close_paper_trade(trade_id: str, exit_price: float, outcome: str) -> dict | None:
    trades = _load_all_trades()
    updated = None
    for t in trades:
        if t["trade_id"] == trade_id and t["status"] == "open":
            # Close on Alpaca (no-op if already closed by TP/SL bracket)
            try:
                close_position(t["symbol"])
            except Exception:
                pass
            entry = float(t["entry_price"])
            size = float(t["position_size"])
            direction = t["direction"]

            if direction == "long":
                pnl_usd = (exit_price - entry) * size
            else:
                pnl_usd = (entry - exit_price) * size

            pnl_pct = pnl_usd / (entry * size) * 100 if (entry * size) > 0 else 0

            # Fees (sell-side only)
            sale_value = exit_price * size
            sec_fee = sale_value * config.SEC_FEE_RATE
            finra_fee = min(size * config.FINRA_TAF_RATE, config.FINRA_TAF_MAX)
            fees_usd = round(sec_fee + finra_fee, 4)
            net_pnl = round(pnl_usd - fees_usd, 2)

            t.update({
                "status": "closed",
                "exit_price": round(exit_price, 4),
                "exit_timestamp": datetime.utcnow().isoformat(),
                "pnl_pct": round(pnl_pct, 4),
                "pnl_usd": round(pnl_usd, 2),
                "fees_usd": fees_usd,
                "net_pnl_usd": net_pnl,
                "notes": f"{t.get('notes', '')} | {outcome}",
            })
            updated = t

    if updated:
        _save_all_trades(trades)
    return updated


def _append_trade(trade: dict) -> None:
    exists = TRADES_FILE.exists() and TRADES_FILE.stat().st_size > 0
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow({k: trade.get(k, "") for k in FIELDNAMES})


def _load_all_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_all_trades(trades: list[dict]) -> None:
    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(trades)
