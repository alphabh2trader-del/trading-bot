"""MIDDAY — 11:00 ET: check positions, exits only (no new trades)."""
from execution.portfolio import check_tp_sl_hits, check_meanrev_exits
from reporting.telegram import send_message, send_exit_alert
from risk.risk_engine import update_drawdown
from src.execution.alpaca_bridge import is_market_open


def run(state: dict) -> None:
    if not is_market_open():
        return  # silent — nothing to check if market is closed

    closed = check_tp_sl_hits(timeframe="1Day") + check_meanrev_exits()
    for t in closed:
        send_exit_alert(t)
        update_drawdown(state)

    if not closed:
        send_message("MIDDAY: No position changes. Monitoring.")
    else:
        send_message(f"MIDDAY: {len(closed)} position(s) closed.")
