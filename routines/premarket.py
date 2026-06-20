"""PREMARKET — 07:00 ET: rebuild watchlist, check overnight, news flag."""
import os
import requests
from dotenv import load_dotenv

import config
from data.universe import build_watchlist
from execution.portfolio import check_tp_sl_hits
from reporting.telegram import send_message, send_exit_alert

load_dotenv()


def _check_news(state: dict) -> None:
    if state.get("perplexity_calls_today", 0) >= config.PERPLEXITY_CALLS_MAX:
        return
    key = os.getenv("PERPLEXITY_API_KEY", "")
    if not key:
        return
    try:
        resp = requests.post(
            config.PERPLEXITY_API_URL,
            json={
                "model": config.PERPLEXITY_MODEL,
                "messages": [{
                    "role": "user",
                    "content": "Are there any high-impact US market events today (earnings, CPI, FOMC, NFP, Fed)? "
                               "Answer: YES or NO, then list the events if any."
                }],
            },
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
        state["news_blocked"] = answer.strip().upper().startswith("YES")
        state["perplexity_calls_today"] = state.get("perplexity_calls_today", 0) + 1
        if state["news_blocked"]:
            send_message(f"NEWS BLOCK active today:\n{answer}")
    except Exception as e:
        send_message(f"Premarket news check failed: {e}")


def run(state: dict) -> None:
    # 1. Rebuild watchlist from scratch
    watchlist = build_watchlist()
    state["watchlist"] = watchlist

    # 2. Check overnight TP/SL hits
    closed = check_tp_sl_hits(timeframe="1Day")
    for t in closed:
        send_exit_alert(t)

    # 3. News check (Perplexity call #1)
    _check_news(state)

    events = "blocked" if state.get("news_blocked") else "none"
    send_message(
        f"PREMARKET COMPLETE\nWatching {len(watchlist)} tickers: {', '.join(watchlist[:5])}...\n"
        f"Overnight closures: {len(closed)} | Events today: {events}"
    )
