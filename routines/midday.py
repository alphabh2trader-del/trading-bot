"""MIDDAY — 11:00 ET: check positions, exits only (no new trades)."""
from execution.portfolio import check_tp_sl_hits
from reporting.telegram import send_message, send_exit_alert
from risk.risk_engine import update_drawdown


def run(state: dict) -> None:
    closed = check_tp_sl_hits(timeframe="4Hour")
    for t in closed:
        send_exit_alert(t)
        update_drawdown(state)

    if not closed:
        send_message("MIDDAY: No position changes. Monitoring.")
    else:
        send_message(f"MIDDAY: {len(closed)} position(s) closed.")
