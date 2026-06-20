"""
Skill: Sentiment Analysis
Queries Perplexity API for macro market sentiment. Can block or reduce trades.
"""
from src.research.perplexity import sentiment_summary, macro_environment_analysis
from src.memory.state import load_config


def get_sentiment_score() -> dict:
    return sentiment_summary()


def macro_environment_analysis() -> str:
    from src.research.perplexity import macro_environment_analysis as _macro
    return _macro()


def should_block_trading(score: float) -> tuple[bool, str]:
    config = load_config()
    threshold = config["sentiment"]["block_threshold"]
    if score <= threshold:
        return True, f"Sentiment too negative ({score:.2f}). Trading blocked."
    return False, f"Sentiment OK ({score:.2f})."


def should_reduce_size(score: float) -> tuple[bool, str]:
    config = load_config()
    threshold = config["sentiment"]["reduce_size_threshold"]
    if score <= threshold:
        return True, f"Negative sentiment ({score:.2f}). Reducing position size."
    return False, f"Sentiment neutral or positive ({score:.2f})."


def sentiment_report() -> dict:
    data = get_sentiment_score()
    score = data["score"]
    blocked, block_reason = should_block_trading(score)
    reduced, reduce_reason = should_reduce_size(score)
    return {
        "score": score,
        "reason": data["reason"],
        "blocked": blocked,
        "block_reason": block_reason,
        "reduced_size": reduced,
        "reduce_reason": reduce_reason,
    }
