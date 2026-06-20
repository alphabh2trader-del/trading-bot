"""
Skill: Telegram Notification
Sends trade signals, exit alerts, and daily summaries via Telegram bot.
"""
import os
import requests
from dotenv import load_dotenv
from src.strategy.swing_core import Signal

load_dotenv()


def _send(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception:
        return False


def send_message(text: str) -> bool:
    return _send(text)


def send_trade_alert(signal: Signal, account_equity: float, position_size: float) -> bool:
    direction_emoji = "BUY" if signal.direction == "long" else "SELL"
    text = (
        f"<b>TRADE SIGNAL — {direction_emoji} {signal.symbol}</b>\n"
        f"Entry: {signal.entry_price:.4f}\n"
        f"Stop Loss: {signal.stop_loss:.4f}\n"
        f"Take Profit: {signal.take_profit:.4f}\n"
        f"R:R = {signal.rr_ratio:.1f}\n"
        f"Size: {position_size:.2f} shares\n"
        f"Equity: ${account_equity:,.2f}\n"
        f"Reason: {signal.reason}"
    )
    return _send(text)


def send_exit_alert(symbol: str, direction: str, pnl_pct: float, pnl_usd: float) -> bool:
    result = "PROFIT" if pnl_usd >= 0 else "LOSS"
    text = (
        f"<b>TRADE CLOSED — {symbol} ({direction.upper()})</b>\n"
        f"Result: {result}\n"
        f"P&L: {pnl_pct:+.2f}% | ${pnl_usd:+.2f}"
    )
    return _send(text)


def send_daily_summary(
    date: str,
    total_trades: int,
    wins: int,
    losses: int,
    daily_pnl_pct: float,
    total_drawdown_pct: float,
) -> bool:
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    text = (
        f"<b>DAILY SUMMARY — {date}</b>\n"
        f"Trades: {total_trades} | W: {wins} L: {losses}\n"
        f"Win rate: {win_rate:.1f}%\n"
        f"Daily P&L: {daily_pnl_pct:+.2f}%\n"
        f"Total Drawdown: {total_drawdown_pct:.2f}%"
    )
    return _send(text)
