from src.memory.state import load_config, get_open_trades


def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float | None = None,
) -> float:
    """Returns number of shares to trade at flat 1% risk per trade."""
    config = load_config()
    risk = config["risk"]

    if risk_pct is None:
        risk_pct = risk["risk_per_trade_pct"]

    risk_amount = account_equity * (risk_pct / 100)
    risk_per_share = abs(entry_price - stop_loss)

    if risk_per_share == 0:
        return 0

    return risk_amount / risk_per_share


def can_open_trade(daily_pnl_pct: float, total_drawdown_pct: float) -> tuple[bool, str]:
    """
    Returns (allowed, reason). Blocks new trades if any risk limit is breached.
    """
    config = load_config()
    risk = config["risk"]
    open_trades = get_open_trades()

    if len(open_trades) >= risk["max_open_trades"]:
        return False, f"Max open trades reached ({risk['max_open_trades']})"

    if daily_pnl_pct <= -risk["max_daily_loss_pct"]:
        return False, f"Daily loss limit hit ({daily_pnl_pct:.2f}%)"

    if total_drawdown_pct >= risk["max_total_drawdown_pct"]:
        return False, f"Max drawdown hit ({total_drawdown_pct:.2f}%)"

    return True, "OK"


def validate_rr(entry: float, stop_loss: float, take_profit: float) -> tuple[bool, float]:
    """Returns (valid, rr_ratio). Rejects trades below minimum R:R."""
    config = load_config()
    min_rr = config["risk"]["target_rr_min"]
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    if risk == 0:
        return False, 0.0
    rr = reward / risk
    return rr >= min_rr, rr
