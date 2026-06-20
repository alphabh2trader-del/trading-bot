from pathlib import Path

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"

# --- Scoring ---
SCORE_THRESHOLD = 65
MIDDAY_SCORE_THRESHOLD = 75  # applied after 10:30 ET

REGIME_BONUS = {"TREND": 10, "NORMAL": 0, "CHOP": -10, "EXTREME": 0}

# --- Risk ---
MAX_DRAWDOWN_PCT = 2.0
MAX_RISK_PER_TRADE = 1.0    # % of equity
MAX_TOTAL_EXPOSURE = 3.0    # % of equity
SECTOR_MAX = 1              # max 1 open position per sector

# --- Execution ---
MAX_SPREAD_PCT = 0.20
MIN_RVOL = 1.5
MIN_AVG_VOLUME = 1_000_000
DATA_FRESHNESS_MAX_MIN = 5
OPEN_WAIT_MINUTES = 5       # no trades in first 5 min after open

# --- R:R ---
MIN_RR = 1.8                # hard floor — below this rr_score = 0

# --- Watchlist ---
BASE_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "JPM", "V", "UNH",
]

SECTOR_MAP = {
    "AAPL": "tech",     "MSFT": "tech",     "NVDA": "tech",
    "AMZN": "consumer", "GOOGL": "tech",    "META": "tech",
    "TSLA": "auto",     "JPM": "finance",   "V": "finance",
    "UNH": "health",    "AMD": "tech",      "NFLX": "consumer",
}

# --- Broker fees (sell-side) ---
SEC_FEE_RATE = 0.0000278
FINRA_TAF_RATE = 0.000145
FINRA_TAF_MAX = 7.27

# --- Perplexity ---
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"
PERPLEXITY_CALLS_MAX = 2


def _load_adaptive_overrides() -> None:
    """Apply adaptive parameter adjustments written by memory/adaptive.py."""
    import json
    cfg_path = MEMORY_DIR / "config.json"
    if not cfg_path.exists():
        return
    try:
        adaptive = json.loads(cfg_path.read_text(encoding="utf-8")).get("adaptive", {})
        global SCORE_THRESHOLD, MIDDAY_SCORE_THRESHOLD, MIN_RR
        if "score_threshold" in adaptive:
            SCORE_THRESHOLD = int(adaptive["score_threshold"])
        if "midday_score_threshold" in adaptive:
            MIDDAY_SCORE_THRESHOLD = int(adaptive["midday_score_threshold"])
        if "min_rr" in adaptive:
            MIN_RR = float(adaptive["min_rr"])
    except Exception:
        pass


_load_adaptive_overrides()
