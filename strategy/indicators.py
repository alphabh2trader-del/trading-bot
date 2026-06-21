import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def wilder_rsi(series: pd.Series, period: int = 2) -> pd.Series:
    """RSI with Wilder's smoothing (EWM). Required for short-period Connors-style
    mean-reversion signals (RSI-2); matches the research backtester."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rvol(df: pd.DataFrame, lookback: int = 20) -> float:
    avg = df["volume"].tail(lookback + 1).iloc[:-1].mean()
    current = df["volume"].iloc[-1]
    return current / avg if avg > 0 else 0.0


def detect_structure(df: pd.DataFrame, lookback: int = 10) -> str:
    """Swing market structure over the last `lookback` bars.

    Compares the recent half of the window against the older half:
    higher-highs AND higher-lows -> bullish; lower-highs AND lower-lows ->
    bearish. This captures trend structure without demanding that every
    consecutive bar increase (which essentially never happens on real data
    and starved the strategy of setups).
    """
    window = df.tail(lookback)
    if len(window) < lookback:
        return "neutral"

    half = lookback // 2
    older_high = window["high"].iloc[:half].max()
    recent_high = window["high"].iloc[half:].max()
    older_low = window["low"].iloc[:half].min()
    recent_low = window["low"].iloc[half:].min()

    if recent_high > older_high and recent_low > older_low:
        return "bullish"
    if recent_high < older_high and recent_low < older_low:
        return "bearish"
    return "neutral"


def macd_bullish_cross(macd_data: dict) -> bool:
    hist = macd_data["histogram"]
    if len(hist) < 2:
        return False
    return hist.iloc[-2] < 0 <= hist.iloc[-1]


def macd_bearish_cross(macd_data: dict) -> bool:
    hist = macd_data["histogram"]
    if len(hist) < 2:
        return False
    return hist.iloc[-2] > 0 >= hist.iloc[-1]


def atr_expanding(atr_series: pd.Series, lookback: int = 5) -> bool:
    tail = atr_series.dropna().tail(lookback + 1)
    if len(tail) < 2:
        return False
    return tail.iloc[-1] > tail.iloc[:-1].mean()
