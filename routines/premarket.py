"""PREMARKET — 07:00 ET: rebuild watchlist, check overnight, news flag."""
import os
import requests
from dotenv import load_dotenv

import config
from data.universe import build_watchlist
from execution.portfolio import check_tp_sl_hits, check_meanrev_exits
from reporting.telegram import send_message, send_exit_alert
from src.skills.sentiment import sentiment_report

load_dotenv()


def _check_sentiment(state: dict) -> None:
    """Macro sentiment gate (Perplexity). Can block or flag size reduction.
    Fails open and respects the daily Perplexity call budget."""
    if state.get("perplexity_calls_today", 0) >= config.PERPLEXITY_CALLS_MAX:
        return
    if not os.getenv("PERPLEXITY_API_KEY", ""):
        return
    try:
        rep = sentiment_report()
        state["sentiment_score"] = rep["score"]
        state["sentiment_block"] = rep["blocked"]
        state["sentiment_reduce"] = rep["reduced_size"]
        state["perplexity_calls_today"] = state.get("perplexity_calls_today", 0) + 1
        if rep["blocked"]:
            send_message(f"SENTIMENT BLOCK: {rep['block_reason']}")
        elif rep["reduced_size"]:
            send_message(f"SENTIMENT: {rep['reduce_reason']}")
    except Exception as e:
        send_message(f"Premarket sentiment check failed: {e}")


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

    # 2. Check overnight exits (bracket TP/SL + mean-reversion rule/stop)
    closed = check_tp_sl_hits(timeframe="1Day") + check_meanrev_exits()
    for t in closed:
        send_exit_alert(t)

    # 3. News check (Perplexity call #1)
    _check_news(state)

    # 4. Sentiment gate (Perplexity call #2, budget-permitting)
    _check_sentiment(state)

    events = "blocked" if state.get("news_blocked") else "none"
    sentiment = state.get("sentiment_score")
    sent_str = f" | Sentiment {sentiment:+.2f}" if sentiment is not None else ""
    send_message(
        f"PREMARKET COMPLETE\nWatching {len(watchlist)} tickers: {', '.join(watchlist[:5])}...\n"
        f"Overnight closures: {len(closed)} | Events today: {events}{sent_str}"
    )
