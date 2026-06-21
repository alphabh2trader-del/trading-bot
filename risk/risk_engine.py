import sys
import config
from state.daily_state import save_state
from reporting.telegram import send_message


def check_risk(state: dict) -> None:
    """Account-level guard, run at the start of every routine.

    Risk model (user decision 2026-06-21): there is NO daily halt. A bad day only
    SHRINKS per-trade size (see daily_risk_multiplier), it never stops the bot from
    trading. The ONLY thing that halts the system is the account-level catastrophe
    drawdown — this is what protects a funded prop account from termination.
    """
    if state.get("kill_switch") == "LOCKED":
        send_message("System LOCKED. Run --reset to reactivate.")
        sys.exit(0)

    # Account-level (total) drawdown guard — tracks peak equity across all runs.
    # Skipped silently if equity is unavailable (e.g. local dry-run without creds).
    try:
        from src.execution.alpaca_bridge import get_account
        from state.risk_state import update_total_drawdown
        equity = float(get_account().get("equity", 0.0))
        total_dd = update_total_drawdown(equity)
        if total_dd >= config.MAX_TOTAL_DRAWDOWN_PCT:
            state["kill_switch"] = "LOCKED"
            save_state(state)
            send_message(
                f"KILL SWITCH: total drawdown {total_dd:.2f}% >= {config.MAX_TOTAL_DRAWDOWN_PCT}% "
                f"(account catastrophe stop). System LOCKED."
            )
            sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass


def daily_risk_multiplier(state: dict) -> float:
    """Shrink per-trade risk as the day's realised loss grows — never blocks a trade.

    Replaces the old hard daily kill-switch. `daily_drawdown` is the day's realised
    loss as a positive percentage. We walk config.DAILY_DERISK_LADDER (rows of
    [loss_threshold_pct, size_multiplier]) and return the multiplier for the first
    row whose threshold the loss is still BELOW. So a clean day trades full size, a
    losing day trades smaller and smaller size — but always > 0.
    """
    dd = float(state.get("daily_drawdown", 0.0))
    ladder = config.DAILY_DERISK_LADDER
    for threshold, mult in ladder:
        if dd < float(threshold):
            return float(mult)
    return float(ladder[-1][1]) if ladder else 1.0


def _open_swing_risk_pct() -> float:
    """Sum of risk_pct across currently-open SWING positions (trend sleeve excluded —
    it has no per-trade stop risk)."""
    from execution.portfolio import get_open_trades
    total = 0.0
    for t in get_open_trades():
        if "trend" in (t.get("notes", "") or "").lower():
            continue
        try:
            total += float(t.get("risk_pct") or 0)
        except ValueError:
            pass
    return total


def can_open_trade(state: dict) -> tuple[bool, str]:
    """Gate a new swing entry. No daily halt and no fixed position-count cap (user
    choice): the only gates are the aggregate OPEN-RISK budget and a generous sanity
    ceiling on concurrent positions."""
    from execution.portfolio import get_open_trades
    open_count = len(get_open_trades())
    if open_count >= config.MAX_POSITIONS_CEILING:
        return False, f"Safety ceiling reached ({config.MAX_POSITIONS_CEILING} open positions)"

    open_risk = _open_swing_risk_pct()
    # Reserve room for at least the next trade's (possibly de-risked) size.
    next_risk = config.MAX_RISK_PER_TRADE * daily_risk_multiplier(state)
    if open_risk + next_risk > config.MAX_OPEN_RISK_PCT + 1e-9:
        return False, (
            f"Open-risk budget spent: {open_risk:.2f}% used + {next_risk:.2f}% next "
            f"> {config.MAX_OPEN_RISK_PCT:.1f}% cap"
        )

    return True, "OK"


def sector_allowed(sector: str, state: dict) -> bool:
    return state.get("open_sectors", []).count(sector) < config.SECTOR_MAX


def update_drawdown(state: dict) -> None:
    from state.risk_state import get_daily_pnl_pct
    pnl = get_daily_pnl_pct()
    state["daily_drawdown"] = max(0.0, -pnl)
