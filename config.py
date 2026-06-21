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
MAX_CONCURRENT_POSITIONS = int(_RISK.get("max_open_trades", 6))        # legacy (informational); gating is by risk budget below
MAX_DRAWDOWN_PCT = float(_RISK.get("max_daily_loss_pct", 3.0))         # daily loss reference (no longer halts — drives the de-risk ladder)
MAX_TOTAL_DRAWDOWN_PCT = float(_RISK.get("max_total_drawdown_pct", 8.0))  # account-level catastrophe halt (the ONLY hard stop)
MAX_TOTAL_EXPOSURE = 6.0    # % of equity at risk (informational)

# Risk model (user decision 2026-06-21): no daily halt, no fixed position-count cap.
# New swing entries are gated by an aggregate OPEN-RISK budget; per-trade size shrinks
# as the day's realised loss grows (a bad day reduces size, never blocks a trade).
MAX_OPEN_RISK_PCT = float(_RISK.get("max_open_risk_pct", 6.0))         # sum of open swing risk_pct must stay under this
MAX_POSITIONS_CEILING = int(_RISK.get("max_positions_ceiling", 20))   # sanity backstop against a runaway day
# [loss_pct_threshold, size_multiplier] — first row whose threshold the daily loss is
# still BELOW wins. e.g. -1.5% loss -> 0.66x size; -3%+ -> 0.33x. Never 0 (never blocks).
DAILY_DERISK_LADDER = _RISK.get("daily_derisk_ladder", [[1.0, 1.0], [2.0, 0.66], [3.0, 0.5], [100.0, 0.33]])
SECTOR_MAX = 2             # max open positions per sector (was 1; raised so good clustered setups aren't all dropped)

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

# --- Trade geometry (legacy trend scorer) ---
TP_R_MULT = 2.0             # take-profit distance as a multiple of risk (R)

# --- Mean reversion (Connors RSI-2) — RETIRED: failed cost/survivorship stress test ---
MEANREV_RSI_PERIOD = 2
MEANREV_RSI_THRESHOLD = 10
MEANREV_TREND_SMA = 200
MEANREV_EXIT_SMA = 5
MEANREV_STOP_PCT = 0.08
MEANREV_MAX_HOLD = 10

# --- Trend timing (Faber GTAA) — ACTIVE strategy ---
# These are sourced from memory/config.json ("trend" section) so the self-improvement
# loop (memory/adaptive.py) can adjust exposure for capital preservation and persist it.
_TREND = _CFG.get("trend", {})
_SWING = _CFG.get("swing", {})
TREND_TIMING_ENABLED = bool(_TREND.get("enabled", True))
TREND_CAPITAL_ALLOCATION = float(_TREND.get("capital_allocation", 0.30))  # 30% sleeve; the rest funds swing buying power
SWING_ENABLED = bool(_SWING.get("enabled", True))
TREND_SMA_MONTHS = int(_TREND.get("sma_months", 10))   # hold ETF when monthly close > N-month SMA
TREND_SMA_DAYS = 200        # ~10 months, used for the minimum-history check
TREND_EXPOSURE = float(_TREND.get("exposure", 1.0))    # 1.0 = fully invest the 30% sleeve; <1 de-risk, >1 leverage
TREND_BASE_EXPOSURE = float(_TREND.get("base_exposure", 1.0))  # the exposure to restore to after recovery
# Rebalance band: a held position is only re-traded toward its target weight when it
# drifts more than this fraction away. Keeps the book ~equal-weight and lets an
# exposure change (adaptive de-risk) actually trim positions, without churning on noise.
REBALANCE_BAND = float(_TREND.get("rebalance_band", 0.15))

# --- Universe ---
# Trend timing trades a diversified ETF set: equity index/sector + bonds (TLT) + gold (GLD).
# The defensive sleeves (TLT, GLD) cut drawdown by trending up when equities fall.
TREND_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV", "XLY",
    "XLP", "XLI", "XLU", "XLB", "SMH", "XBI", "KRE", "TLT", "GLD",
]

# --- Swing watchlist (DISJOINT from TREND_UNIVERSE) ---
# Liquid large-caps with tight spreads and high RVOL — the daily D1/H4 pullback
# system trades these. Kept separate from the ETF trend sleeve so the two
# strategies never fight over the same symbol (rebalance scopes to TREND_UNIVERSE).
SWING_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AMD", "NFLX", "JPM", "V", "UNH", "CRM", "COST", "AVGO", "QCOM",
]
BASE_WATCHLIST = SWING_WATCHLIST

SECTOR_MAP = {
    # ETFs (each its own "sector" bucket so concurrency caps still apply sensibly)
    "SPY": "index", "QQQ": "index", "IWM": "index", "DIA": "index",
    "XLF": "etf-fin", "XLK": "etf-tech", "XLE": "etf-energy", "XLV": "etf-health",
    "XLY": "etf-cons", "XLP": "etf-staples", "XLI": "etf-ind", "XLU": "etf-util",
    "XLB": "etf-mat", "SMH": "etf-semi", "XBI": "etf-bio", "KRE": "etf-banks",
    # stocks (swing watchlist)
    "AAPL": "tech", "MSFT": "tech", "NVDA": "semi",
    "AMZN": "consumer", "GOOGL": "tech", "META": "tech",
    "TSLA": "auto", "JPM": "finance", "V": "finance",
    "UNH": "health", "AMD": "semi", "NFLX": "consumer",
    "CRM": "software", "COST": "consumer", "AVGO": "semi", "QCOM": "semi",
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
