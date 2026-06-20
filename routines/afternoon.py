"""AFTERNOON — 14:00 ET: final position check + pre-close exits."""
from execution.portfolio import check_tp_sl_hits, get_open_trades
from execution.engine import close_paper_trade
from data.market_data import get_live_quote
from reporting.telegram import send_message, send_exit_alert
from risk.risk_engine import update_drawdown


def run(state: dict) -> None:
    # Check TP/SL hits since midday
    closed = check_tp_sl_hits(timeframe="4Hour")
    for t in closed:
        send_exit_alert(t)
        update_drawdown(state)

    # 15:30+ — close all non-swing (day trades)
    open_trades = get_open_trades()
    eod_closed = []
    for trade in open_trades:
        notes = trade.get("notes", "").lower()
        if "swing" not in notes:
            try:
                quote = get_live_quote(trade["symbol"])
                result = close_paper_trade(trade["trade_id"], quote["mid"], "EOD close — not swing")
                if result:
                    eod_closed.append(result)
                    send_exit_alert(result)
            except Exception:
                pass

    total_closed = len(closed) + len(eod_closed)
    still_open = get_open_trades()

    send_message(
        f"AFTERNOON: {total_closed} position(s) closed. "
        f"{len(still_open)} holding overnight."
    )
