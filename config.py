import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"


def _load_config_json() -> dict:
    """memory/config.json is the single source of truth for risk parameters."""
    cfg_path = MEMORY_DIR / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


_CFG = _load_config_json()
_RISK = _CFG.get("risk", {})

# --- Scoring ---
SCORE_THRESHOLD = 65
MIDDAY_SCORE_THRESHOLD = 75  # applied after 10:30 ET

REGIME_BONUS = {"TREND": 10, "NORMAL": 0, "CHOP": -10, "EXTREME": 0}

# --- Risk (sourced from memory/config.json — single source of truth) ---
MAX_RISK_PER_TRADE = float(_RISK.get("risk_per_trade_pct", 1.0))       # % of equity per trade
MAX_CONCURRENT_POSITIONS = int(_RISK.get("max_open_trades", 2))
MAX_DRAWDOWN_PCT = float(_RISK.get("max_daily_loss_pct", 3.0))         # daily kill-switch (was 2.0; aligned to spec/config.json)
MAX_TOTAL_DRAWDOWN_PCT = float(_RISK.get("max_total_drawdown_pct", 8.0))  # account-level kill-switch
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

# --- Skills (integrated into scorer/planner) ---
ATR_STOP_MULT = 1.5         # ATR multiplier for the volatility buffer on stops
EARNINGS_BUFFER_DAYS = 3    # block setups with earnings within N days
VOLUME_CONFIRM_BONUS = 5    # score bonus when volume confirms the signal
REQUIRE_VOLUME_CONFIRM = False  # if True, reject setups without volume confirmation

# --- Trade geometry ---
TP_R_MULT = 2.0             # take-profit distance as a multiple of risk (R)

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
