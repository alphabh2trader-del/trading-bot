import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    direction: str        # "long", "short", or "none"
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    reason: str


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def is_bullish_engulfing(df: pd.DataFrame, idx: int) -> bool:
    if idx < 1:
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (
        prev["close"] < prev["open"]
        and curr["close"] > curr["open"]
        and curr["close"] > prev["open"]
        and curr["open"] < prev["close"]
    )


def is_bearish_engulfing(df: pd.DataFrame, idx: int) -> bool:
    if idx < 1:
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (
        prev["close"] > prev["open"]
        and curr["close"] < curr["open"]
        and curr["close"] < prev["open"]
        and curr["open"] > prev["close"]
    )


def has_rejection_wick(candle: pd.Series, direction: str, wick_ratio: float = 0.6) -> bool:
    body = abs(candle["close"] - candle["open"])
    full_range = candle["high"] - candle["low"]
    if full_range == 0:
        return False
    if direction == "long":
        lower_wick = min(candle["open"], candle["close"]) - candle["low"]
        return lower_wick / full_range >= wick_ratio
    elif direction == "short":
        upper_wick = candle["high"] - max(candle["open"], candle["close"])
        return upper_wick / full_range >= wick_ratio
    return False


def check_trend(daily_df: pd.DataFrame) -> str:
    """Returns 'bullish', 'bearish', or 'neutral'."""
    ema200 = ema(daily_df["close"], 200)
    last_close = daily_df["close"].iloc[-1]
    last_ema200 = ema200.iloc[-1]
    if last_close > last_ema200:
        return "bullish"
    elif last_close < last_ema200:
        return "bearish"
    return "neutral"


def check_entry_conditions(
    h4_df: pd.DataFrame,
    trend: str,
    target_rr: float = 2.0,
) -> Optional[Signal]:
    """
    Checks H4 data for a valid pullback entry.
    Returns a Signal if conditions are met, otherwise None.
    """
    if trend == "neutral":
        return None

    h4_df = h4_df.copy()
    h4_df["ema50"] = ema(h4_df["close"], 50)
    h4_df["rsi"] = rsi(h4_df["close"], 14)

    last_idx = len(h4_df) - 1
    last = h4_df.iloc[last_idx]
    last_rsi = last["rsi"]
    last_ema50 = last["ema50"]
    last_close = last["close"]

    near_ema50 = abs(last_close - last_ema50) / last_ema50 < 0.005

    if trend == "bullish":
        rsi_ok = 40 <= last_rsi <= 55
        rsi_rising = last_rsi > h4_df["rsi"].iloc[-2]
        candle_ok = (
            is_bullish_engulfing(h4_df, last_idx)
            or has_rejection_wick(last, "long")
        )
        if near_ema50 and rsi_ok and rsi_rising and candle_ok:
            entry = last["close"]
            sl = last["low"] * 0.999
            risk = entry - sl
            tp = entry + risk * target_rr
            return Signal(
                direction="long",
                symbol="",
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=target_rr,
                reason=f"Bullish pullback to EMA50. RSI={last_rsi:.1f}",
            )

    elif trend == "bearish":
        rsi_ok = 45 <= last_rsi <= 60
        rsi_falling = last_rsi < h4_df["rsi"].iloc[-2]
        candle_ok = (
            is_bearish_engulfing(h4_df, last_idx)
            or has_rejection_wick(last, "short")
        )
        if near_ema50 and rsi_ok and rsi_falling and candle_ok:
            entry = last["close"]
            sl = last["high"] * 1.001
            risk = sl - entry
            tp = entry - risk * target_rr
            return Signal(
                direction="short",
                symbol="",
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=target_rr,
                reason=f"Bearish pullback to EMA50. RSI={last_rsi:.1f}",
            )

    return None
