import os
import requests
from dotenv import load_dotenv

load_dotenv()

MAX_MSG_LEN = 4096


def _send(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print(f"[Telegram] {text[:120]}")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram error] {e}")
        return False


def send_message(text: str) -> bool:
    return _send(text)


def send_chunked(text: str) -> None:
    for i in range(0, len(text), MAX_MSG_LEN):
        _send(text[i: i + MAX_MSG_LEN])


def send_trade_alert(setup: dict, trade: dict) -> bool:
    direction = "BUY" if setup["direction"] == "long" else "SELL"
    return _send(
        f"<b>PAPER TRADE — {direction} {setup['symbol']}</b>\n"
        f"Entry: ${trade['entry_price']} | SL: ${trade['stop_loss']} | TP: ${trade['take_profit']}\n"
        f"R:R: {setup['rr']} | Score: {setup['score']} | Size: {trade['position_size']} shares\n"
        f"Risk: ${trade['risk_usd']} (1%) | Potential: ${trade['potential_usd']}\n"
        f"RSI: {setup['rsi_value']} | Regime: {setup['regime']}\n"
        f"Reason: {setup['reason']}"
    )


def send_exit_alert(trade: dict) -> bool:
    outcome = "TP HIT ✅" if float(trade.get("pnl_usd") or 0) > 0 else "SL HIT ❌"
    return _send(
        f"<b>TRADE CLOSED — {trade['symbol']} ({trade['direction'].upper()})</b>\n"
        f"{outcome}\n"
        f"Gross P&L: ${trade.get('pnl_usd', '?')} | Fees: ${trade.get('fees_usd', '?')}\n"
        f"Net P&L: ${trade.get('net_pnl_usd', '?')}"
    )
