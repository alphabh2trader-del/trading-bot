"""OPEN — 09:30 ET: execute valid setups after 5-min wait."""
import time
from datetime import datetime

import pytz

import config
from decision.validator import validate_entry
from execution.engine import open_paper_trade
from execution.portfolio import check_tp_sl_hits
from risk.risk_engine import can_open_trade, sector_allowed, update_drawdown
from reporting.telegram import send_message, send_trade_alert, send_exit_alert
from src.execution.alpaca_bridge import is_market_open
from state.daily_state import save_state


def _is_midday() -> bool:
    # Proper US/Eastern conversion — handles EST/EDT automatically (no fixed offset).
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    return now_et.hour > 10 or (now_et.hour == 10 and now_et.minute >= 30)


def run(state: dict) -> None:
    if not is_market_open():
        send_message("OPEN: Market closed (holiday or early shutdown). Skipping entries.")
        return

    # Defensive block guard — even if plan.py did not run, never enter on a
    # news-blocked day or when macro sentiment is strongly negative.
    if state.get("news_blocked"):
        send_message("OPEN: News block active — no entries today.")
        return
    if state.get("sentiment_block"):
        send_message("OPEN: Sentiment block active — no entries today.")
        return

    # Wait 5 min after open
    time.sleep(config.OPEN_WAIT_MINUTES * 60)

    # Check intraday TP/SL hits first
    closed = check_tp_sl_hits(timeframe="4Hour")
    for t in closed:
        send_exit_alert(t)
        update_drawdown(state)

    setups = state.get("setups", [])
    if not setups:
        send_message("OPEN: No confirmed setups to execute.")
        return

    threshold = config.MIDDAY_SCORE_THRESHOLD if _is_midday() else config.SCORE_THRESHOLD
    executed = 0

    for setup in setups:
        if setup.get("status") != "CONFIRMED":
            continue

        if setup["score"] < threshold:
            from memory.logger import log_execution_skip
            log_execution_skip(setup["symbol"], f"Score {setup['score']} below session threshold {threshold}")
            continue

        allowed, reason = can_open_trade(state)
        if not allowed:
            send_message(f"RISK: {reason} — skipping {setup['symbol']}")
            break

        if not sector_allowed(setup["sector"], state):
            from memory.logger import log_execution_skip
            log_execution_skip(setup["symbol"], f"Sector '{setup['sector']}' already has open position")
            continue

        valid, reason = validate_entry(setup, state.get("regime", "NORMAL"))
        if not valid:
            continue

        # Reduce size on mildly negative macro sentiment (AI research can only
        # block or reduce — never increase — per the system spec).
        risk_multiplier = 0.5 if state.get("sentiment_reduce") else 1.0
        trade = open_paper_trade(setup, risk_multiplier=risk_multiplier)
        send_trade_alert(setup, trade)

        state["trades_today"] = state.get("trades_today", 0) + 1
        state["exposure_pct"] = state.get("exposure_pct", 0.0) + config.MAX_RISK_PER_TRADE
        state["open_sectors"] = state.get("open_sectors", []) + [setup["sector"]]
        setup["status"] = "EXECUTED"
        executed += 1

        save_state(state)

    if executed == 0:
        send_message("OPEN: No entries executed (validation filtered all setups).")
