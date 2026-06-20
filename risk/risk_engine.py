import sys
import config
from state.daily_state import save_state
from reporting.telegram import send_message


def check_risk(state: dict) -> None:
    if state.get("kill_switch") == "LOCKED":
        send_message("System LOCKED. Run --reset to reactivate.")
        sys.exit(0)

    drawdown = state.get("daily_drawdown", 0.0)
    if drawdown >= config.MAX_DRAWDOWN_PCT:
        state["kill_switch"] = "LOCKED"
        save_state(state)
        send_message(f"KILL SWITCH: daily drawdown {drawdown:.2f}% >= {config.MAX_DRAWDOWN_PCT}%. System LOCKED.")
        sys.exit(0)


def can_open_trade(state: dict) -> tuple[bool, str]:
    if state.get("daily_drawdown", 0.0) >= config.MAX_DRAWDOWN_PCT:
        return False, f"Daily loss limit hit: -{state['daily_drawdown']:.1f}%"

    from execution.portfolio import get_open_trades
    if len(get_open_trades()) >= config.MAX_CONCURRENT_POSITIONS:
        return False, f"Max concurrent positions ({config.MAX_CONCURRENT_POSITIONS}) reached"

    exposure = state.get("exposure_pct", 0.0)
    if exposure >= config.MAX_TOTAL_EXPOSURE:
        return False, f"Max exposure reached: {exposure:.1f}%"

    return True, "OK"


def sector_allowed(sector: str, state: dict) -> bool:
    return state.get("open_sectors", []).count(sector) < config.SECTOR_MAX


def update_drawdown(state: dict) -> None:
    from state.risk_state import get_daily_pnl_pct
    pnl = get_daily_pnl_pct()
    state["daily_drawdown"] = max(0.0, -pnl)
