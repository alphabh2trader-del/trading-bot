import os
import requests
from dotenv import load_dotenv
from memory.logger import log_learning
import config

load_dotenv()


def _perplexity(prompt: str) -> str:
    key = os.getenv("PERPLEXITY_API_KEY", "")
    if not key:
        return "Perplexity key not set."
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(
        config.PERPLEXITY_API_URL,
        json={"model": config.PERPLEXITY_MODEL, "messages": [{"role": "user", "content": prompt}]},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def run_eod_learning(trades: list[dict], misses: list[str], state: dict) -> str:
    if state.get("perplexity_calls_today", 0) >= config.PERPLEXITY_CALLS_MAX:
        return "Perplexity call limit reached."

    trades_summary = "; ".join(
        f"{t.get('symbol')} {t.get('direction')} P&L {t.get('net_pnl_usd', '?')}"
        for t in trades
    ) or "No trades today"

    misses_summary = ", ".join(misses) or "None"

    prompt = (
        f"Trading bot review — paper trades today: {trades_summary}. "
        f"Missed setups (rejected): {misses_summary}. "
        "In 3-5 bullet points: what pattern stands out? What should the system do differently?"
    )

    insight = _perplexity(prompt)
    log_learning(insight)
    state["perplexity_calls_today"] = state.get("perplexity_calls_today", 0) + 1
    return insight
