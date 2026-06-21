"""AFTERNOON — 14:00 ET: final position check.

This is a SWING bot (NO day trading): positions are held overnight and exit
only on their TP/SL bracket, never force-closed at the end of the session.
"""
from execution.portfolio import check_tp_sl_hits, check_meanrev_exits, get_open_trades
from reporting.telegram import send_message, send_exit_alert
from risk.risk_engine import update_drawdown


def run(state: dict) -> None:
    # Exits: trend bracket fills (TP/SL) + rule-based mean-reversion exits.
    closed = check_tp_sl_hits(timeframe="1Day") + check_meanrev_exits()
    for t in closed:
        send_exit_alert(t)
        update_drawdown(state)

    still_open = get_open_trades()
    send_message(
        f"AFTERNOON: {len(closed)} position(s) closed via TP/SL. "
        f"{len(still_open)} holding overnight (swing)."
    )
