import os
import requests
from dotenv import load_dotenv

load_dotenv()

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


def _query(prompt: str, model: str = "sonar") -> str:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise EnvironmentError("PERPLEXITY_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def macro_environment_analysis() -> str:
    prompt = (
        "Give a brief macro market analysis for today. "
        "Focus on: US equities trend, USD strength, key risk events this week. "
        "Answer in 3-4 sentences."
    )
    return _query(prompt)


def news_risk_detection(symbols: list[str] | None = None) -> str:
    focus = f"for {', '.join(symbols)}" if symbols else "for US equities"
    prompt = (
        f"What are the top 3 current news risks {focus} that could cause sharp price moves? "
        "Answer in bullet points."
    )
    return _query(prompt)


def sentiment_summary() -> dict:
    prompt = (
        "Rate the current overall US stock market sentiment on a scale from -1.0 (extremely bearish) "
        "to +1.0 (extremely bullish). Reply with only: SCORE: <number> and REASON: <one sentence>."
    )
    raw = _query(prompt)
    score = 0.0
    reason = raw
    for line in raw.splitlines():
        if line.startswith("SCORE:"):
            try:
                score = float(line.replace("SCORE:", "").strip())
            except ValueError:
                pass
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
    return {"score": score, "reason": reason}
