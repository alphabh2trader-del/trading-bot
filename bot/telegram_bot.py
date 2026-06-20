#!/usr/bin/env python3
"""
Telegram interface for the trading bot.

Commands:
  /run <routine>  — trigger a GitHub Actions routine
  /status         — Alpaca account equity + open positions
  /positions      — live open positions from Alpaca
  /help           — list commands

Any other text is forwarded to Claude AI, which has full context
about the trading bot and responds like a personal assistant.
"""
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

import anthropic
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Allow imports from the trading bot root (src/, execution/, config.py, etc.)
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
GITHUB_PAT = os.environ["GITHUB_PAT"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "alphabh2trader-del/trading-bot")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

VALID_ROUTINES = {
    "premarket", "analysis", "plan", "open",
    "midday", "afternoon", "review", "weekly", "reset",
}

_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_history: dict[int, list[dict]] = {}  # per-chat conversation history (in-memory)

SYSTEM_PROMPT = """You are the AI assistant for an automated swing trading bot. You run inside Telegram and help the owner understand and manage their bot.

About the bot:
- Strategy: swing trading, pullbacks to EMA50/EMA200 on Daily chart with RSI 14 confirmation, 4H execution
- Watchlist: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM, V, UNH
- Risk: 1% per trade, max 2 open trades, 2% daily loss limit, 8% max drawdown
- Runs automatically via GitHub Actions — 8 routines per weekday (7am to 4pm ET)
- Currently in PAPER TRADING mode on Alpaca
- Uses bracket orders: one order places the entry, take profit, and stop loss together — Alpaca closes automatically
- Adaptive learning: after each EOD review, the bot analyzes the last 10 trades and adjusts score thresholds and R:R requirements
- The owner gets Telegram alerts on every trade open, close, and system error

Daily schedule (ET):
  7:00 AM  premarket  — news filter, block if FOMC/CPI/NFP
  8:00 AM  analysis   — AI market sentiment via Perplexity
  9:00 AM  plan       — scan watchlist, score setups
  9:35 AM  open       — execute confirmed setups on Alpaca
  10:30 AM midday     — check if TP/SL hit
  2:00 PM  afternoon  — final position check
  4:00 PM  review     — EOD report + adaptive learning
  Saturday 10:00 AM weekly — deep analysis + weekly report

Available commands in this chat:
  /run <routine>  — trigger any routine right now
  /status         — account balance and open positions
  /positions      — open positions detail
  /help           — list commands

Answer questions about the strategy, routines, performance, or general trading concepts. Be concise. If asked to run a routine, remind them to use /run <name>."""


def _guard(update: Update) -> bool:
    """Only respond to the authorized chat."""
    return update.effective_chat.id == ALLOWED_CHAT_ID


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    await update.message.reply_text(
        "Trading Bot — Commands\n\n"
        "/run <routine>   trigger a routine\n"
        "  premarket  analysis  plan  open\n"
        "  midday  afternoon  review  weekly  reset\n\n"
        "/status      account equity + open positions\n"
        "/positions   live positions on Alpaca\n"
        "/help        this message\n\n"
        "Or type anything to chat with the AI assistant."
    )


async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /run <routine>\nExample: /run open")
        return

    routine = context.args[0].lower()
    if routine not in VALID_ROUTINES:
        await update.message.reply_text(
            f"Unknown routine: {routine}\n"
            f"Valid: {', '.join(sorted(VALID_ROUTINES))}"
        )
        return

    await update.message.reply_text(f"Triggering '{routine}' on GitHub Actions...")

    url = (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/actions/workflows/trading_routines.yml/dispatches"
    )
    payload = json.dumps({"ref": "main", "inputs": {"routine": routine}}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_PAT}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
                await update.message.reply_text(
                    f"'{routine}' is running on GitHub Actions."
                )
            else:
                await update.message.reply_text(f"GitHub returned {resp.status}. Check Actions tab.")
    except Exception as exc:
        await update.message.reply_text(f"Failed to trigger routine: {exc}")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    try:
        from src.execution.alpaca_bridge import get_account, get_positions
        account = get_account()
        positions = get_positions()

        lines = [
            "Account Status",
            f"Equity:        ${account['equity']:,.2f}",
            f"Cash:          ${account['cash']:,.2f}",
            f"Buying Power:  ${account['buying_power']:,.2f}",
        ]
        if positions:
            lines.append(f"\nOpen Positions ({len(positions)}):")
            for p in positions:
                sign = "+" if p["unrealized_pnl"] >= 0 else ""
                lines.append(
                    f"  {p['symbol']}: {p['qty']} sh @ ${p['avg_entry']:.2f}"
                    f" | P&L: {sign}${p['unrealized_pnl']:.2f}"
                )
        else:
            lines.append("\nNo open positions.")

        await update.message.reply_text("\n".join(lines))
    except Exception as exc:
        await update.message.reply_text(f"Status error: {exc}")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    try:
        from src.execution.alpaca_bridge import get_positions
        positions = get_positions()
        if not positions:
            await update.message.reply_text("No open positions on Alpaca.")
            return
        lines = ["Open Positions (Alpaca live):"]
        for p in positions:
            sign = "+" if p["unrealized_pnl"] >= 0 else ""
            lines.append(
                f"  {p['symbol']}: {p['qty']} shares @ ${p['avg_entry']:.2f}"
                f"\n    Market value: ${p['market_value']:.2f}"
                f" | P&L: {sign}${p['unrealized_pnl']:.2f}"
            )
        await update.message.reply_text("\n".join(lines))
    except Exception as exc:
        await update.message.reply_text(f"Positions error: {exc}")


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        return
    chat_id = update.effective_chat.id
    text = update.message.text

    history = _history.setdefault(chat_id, [])
    history.append({"role": "user", "content": text})
    if len(history) > 20:
        history[:] = history[-20:]

    try:
        response = _claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history,
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as exc:
        await update.message.reply_text(f"AI error: {exc}")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    logging.info("Bot started — polling for Telegram updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
