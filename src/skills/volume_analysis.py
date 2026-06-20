"""
Skill: Volume Analysis
Confirms trade signals with volume. Adapted from harshgupta1810/volume_analysis_stockmarket.
"""
import pandas as pd


def check_volume_confirmation(df: pd.DataFrame, lookback: int = 20, min_ratio: float = 1.2) -> tuple[bool, float]:
    """
    Compares the latest candle's volume to the lookback-period average.
    Returns (confirmed, ratio). confirmed=True if ratio >= min_ratio.
    """
    if len(df) < lookback + 1:
        return False, 0.0
    avg = df["volume"].iloc[-lookback - 1 : -1].mean()
    if avg == 0:
        return False, 0.0
    ratio = df["volume"].iloc[-1] / avg
    return ratio >= min_ratio, round(ratio, 2)


def detect_volume_spike(df: pd.DataFrame, lookback: int = 5, spike_multiplier: float = 2.0) -> bool:
    """
    True if the latest volume pct_change is more than spike_multiplier times
    the rolling mean of pct_changes — indicates a surge in buying/selling pressure.
    """
    if len(df) < lookback + 2:
        return False
    vol_change = df["volume"].pct_change()
    rolling_mean = vol_change.rolling(window=lookback).mean()
    latest_change = vol_change.iloc[-1]
    latest_mean = rolling_mean.iloc[-1]
    if pd.isna(latest_change) or pd.isna(latest_mean) or latest_mean <= 0:
        return False
    return latest_change > spike_multiplier * latest_mean


def check_breakout_volume(df: pd.DataFrame, lookback: int = 5) -> bool:
    """
    True if price closed above the lookback-period resistance on higher volume
    than the previous bar — confirms a breakout is backed by conviction.
    """
    if len(df) < lookback + 2:
        return False
    resistance = df["high"].iloc[-lookback - 1 : -1].max()
    current_close = df["close"].iloc[-1]
    current_vol = df["volume"].iloc[-1]
    prev_vol = df["volume"].iloc[-2]
    return current_close > resistance and current_vol > prev_vol


def get_volume_signal(df: pd.DataFrame) -> dict:
    """
    Master function. Returns a dict with all volume checks and a combined
    confirmed flag (True if volume confirmation OR spike detected).
    """
    confirmed, ratio = check_volume_confirmation(df)
    spike = detect_volume_spike(df)
    breakout = check_breakout_volume(df)
    return {
        "confirmed": confirmed or spike,
        "ratio": ratio,
        "spike": spike,
        "breakout": breakout,
    }
