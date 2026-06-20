from datetime import date
from execution.portfolio import get_daily_summary, get_open_trades
from data.market_data import get_account
from reporting.telegram import send_message


def send_eod_report() -> str:
    today = date.today().strftime("%Y-%m-%d")
    summary = get_daily_summary()
    open_trades = get_open_trades()

    try:
        account = get_account()
        equity = f"${account['equity']:,.2f}"
    except Exception:
        equity = "N/A"

    opened_lines = "\n".join(
        f"• {t['direction'].upper()} {t['symbol']} @ ${t['entry_price']} "
        f"| SL ${t['stop_loss']} | TP ${t['take_profit']}"
        for t in open_trades
    ) or "None"

    # Build closed trades section from summary (simplified)
    win_rate = (summary["wins"] / summary["trades"] * 100) if summary["trades"] > 0 else 0

    report = (
        f"<b>END OF DAY — {today}</b>\n\n"
        f"<b>OPEN POSITIONS:</b>\n{opened_lines}\n\n"
        f"<b>TODAY CLOSED:</b> {summary['trades']} trades | "
        f"W: {summary['wins']} L: {summary['losses']} | Win rate: {win_rate:.0f}%\n"
        f"Gross: ${summary['gross_pnl']:+.2f} | Fees: ${summary['fees']:.4f} | "
        f"Net: ${summary['net_pnl']:+.2f}\n\n"
        f"Account equity: {equity}"
    )

    send_message(report)
    return report
