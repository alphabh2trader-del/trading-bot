import pandas as pd
from typing import Optional


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> list[float]:
    highs = []
    prices = df["high"].values
    for i in range(lookback, len(prices) - lookback):
        if prices[i] == max(prices[i - lookback: i + lookback + 1]):
            highs.append(prices[i])
    return highs


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> list[float]:
    lows = []
    prices = df["low"].values
    for i in range(lookback, len(prices) - lookback):
        if prices[i] == min(prices[i - lookback: i + lookback + 1]):
            lows.append(prices[i])
    return lows


def _is_fresh(level: float, df: pd.DataFrame, max_tests: int = 3) -> bool:
    tests = ((df["high"] >= level * 0.998) & (df["low"] <= level * 1.002)).sum()
    return tests <= max_tests


def find_nearest_level(
    df: pd.DataFrame,
    price: float,
    direction: str,
    proximity_pct: float = 0.5,
) -> Optional[float]:
    lows = find_swing_lows(df)
    highs = find_swing_highs(df)

    candidates = lows if direction == "long" else highs
    fresh = [l for l in candidates if _is_fresh(l, df)]
    nearby = [l for l in fresh if abs(l - price) / price * 100 <= proximity_pct]
    if not nearby:
        return None
    return min(nearby, key=lambda l: abs(l - price))
