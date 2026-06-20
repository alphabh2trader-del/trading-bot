import csv
from datetime import date
from pathlib import Path

import config
from data.market_data import fetch_bars_safe

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"


def get_open_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "open"]


def check_tp_sl_hits(timeframe: str = "1Day") -> list[dict]:
    open_trades = get_open_trades()
    closed = []
    for trade in open_trades:
        symbol = trade["symbol"]
        direction = trade["direction"]
        sl = float(trade["stop_loss"])
        tp = float(trade["take_profit"])

        df = fetch_bars_safe(symbol, timeframe, timeout_sec=2.0)
        if df is None or df.empty:
            continue

        last = df.iloc[-1]
        high = last["high"]
        low = last["low"]

        hit = None
        exit_price = None
        if direction == "long":
            if high >= tp:
                hit, exit_price = "TP HIT", tp
            elif low <= sl:
                hit, exit_price = "SL HIT", sl
        else:
            if low <= tp:
                hit, exit_price = "TP HIT", tp
            elif high >= sl:
                hit, exit_price = "SL HIT", sl

        if hit:
            from execution.engine import close_paper_trade
            result = close_paper_trade(trade["trade_id"], exit_price, hit)
            if result:
                closed.append(result)

    return closed


def get_daily_summary() -> dict:
    today = date.today().isoformat()
    if not TRADES_FILE.exists():
        return {"trades": 0, "wins": 0, "losses": 0, "gross_pnl": 0.0, "fees": 0.0, "net_pnl": 0.0}

    closed_today = []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "closed" and (row.get("exit_timestamp") or "").startswith(today):
                closed_today.append(row)

    wins = [t for t in closed_today if float(t.get("pnl_usd") or 0) > 0]
    losses = [t for t in closed_today if float(t.get("pnl_usd") or 0) <= 0]
    gross = sum(float(t.get("pnl_usd") or 0) for t in closed_today)
    fees = sum(float(t.get("fees_usd") or 0) for t in closed_today)

    return {
        "trades": len(closed_today),
        "wins": len(wins),
        "losses": len(losses),
        "gross_pnl": round(gross, 2),
        "fees": round(fees, 4),
        "net_pnl": round(gross - fees, 2),
        "open": get_open_trades(),
    }
