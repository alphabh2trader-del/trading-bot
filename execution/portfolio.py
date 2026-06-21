import csv
from datetime import date
from pathlib import Path

import config
from data.market_data import fetch_bars_safe
from src.execution.alpaca_bridge import get_positions

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"


def get_open_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "open"]


def check_meanrev_exits() -> list[dict]:
    """Rule-based exits for mean-reversion positions (no bracket TP). Closes a
    position when the daily close rises back above SMA(exit), the disaster stop
    is breached, or it has been held too long. Run from the daily routines."""
    from datetime import datetime, timezone
    from strategy.mean_reversion import should_exit
    from execution.engine import close_paper_trade

    closed = []
    for trade in get_open_trades():
        if "meanrev" not in (trade.get("notes", "").lower()):
            continue
        symbol = trade["symbol"]
        daily = fetch_bars_safe(symbol, "1Day", timeout_sec=3.0)
        try:
            entered = datetime.fromisoformat(trade["timestamp"])
            days_held = (datetime.now(timezone.utc).replace(tzinfo=None) - entered.replace(tzinfo=None)).days
        except Exception:
            days_held = 0

        do_exit, reason = should_exit(daily, trade, days_held)
        if not do_exit:
            continue
        exit_px = float(daily["close"].iloc[-1]) if daily is not None and not daily.empty \
            else float(trade["entry_price"])
        result = close_paper_trade(trade["trade_id"], exit_px, reason)
        if result:
            closed.append(result)
    return closed


def check_tp_sl_hits(timeframe: str = "1Day") -> list[dict]:
    """Sync open CSV trades with Alpaca — if a position is gone, Alpaca closed it via TP/SL."""
    open_trades = get_open_trades()
    if not open_trades:
        return []

    alpaca_symbols = {p["symbol"] for p in get_positions()}
    closed = []

    for trade in open_trades:
        # Trend-timing positions carry no bracket SL/TP — they exit via the monthly
        # rebalance, not here. Skip them (also avoids float("") on empty levels).
        if "trend" in (trade.get("notes", "").lower()) \
                or not trade.get("stop_loss") or not trade.get("take_profit"):
            continue

        symbol = trade["symbol"]
        if symbol in alpaca_symbols:
            continue  # position still open on Alpaca

        # Position gone — determine outcome from last bar price vs TP/SL levels
        sl = float(trade["stop_loss"])
        tp = float(trade["take_profit"])
        direction = trade["direction"]

        df = fetch_bars_safe(symbol, timeframe, timeout_sec=2.0)
        if df is not None and not df.empty:
            last = df.iloc[-1]
            if direction == "long":
                hit = "TP HIT" if last["high"] >= tp else "SL HIT"
                exit_price = tp if last["high"] >= tp else sl
            else:
                hit = "TP HIT" if last["low"] <= tp else "SL HIT"
                exit_price = tp if last["low"] <= tp else sl
        else:
            hit, exit_price = "SL HIT", sl  # conservative fallback

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
