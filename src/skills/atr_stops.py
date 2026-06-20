"""
Skill: ATR Stop Loss
Calculates volatility-adjusted stop loss and position size using Average True Range.
Replaces the fixed 0.1% buffer with a stop proportional to each symbol's real volatility.
"""
import pandas as pd
import numpy as np


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range over `period` bars."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def calculate_atr_stop(
    df: pd.DataFrame,
    direction: str,
    atr_multiplier: float = 1.5,
    period: int = 14,
) -> tuple[float, float]:
    """
    Returns (stop_loss, atr_value) for the latest candle.
    direction: "long" or "short"
    atr_multiplier: how many ATRs below/above entry to place the stop (default 1.5)
    """
    atr_series = atr(df, period)
    last_atr = atr_series.iloc[-1]
    last_candle = df.iloc[-1]

    if direction == "long":
        stop = last_candle["close"] - (atr_multiplier * last_atr)
    else:
        stop = last_candle["close"] + (atr_multiplier * last_atr)

    return round(stop, 4), round(last_atr, 4)


def calculate_position_size(
    equity: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
) -> int:
    """
    Returns the number of shares to buy given account equity, risk %, entry and stop.
    risk_pct: e.g. 0.01 for 1%
    """
    risk_amount = equity * risk_pct
    risk_per_share = abs(entry - stop_loss)
    if risk_per_share == 0:
        return 0
    return max(1, int(risk_amount / risk_per_share))
