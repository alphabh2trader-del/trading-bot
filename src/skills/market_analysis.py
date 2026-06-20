"""
Skill: Market Analysis
Computes EMA 200, EMA 50, RSI 14, detects trend and candlestick patterns.
"""
import pandas as pd
from src.strategy.swing_core import (
    ema,
    rsi,
    check_trend,
    check_entry_conditions,
    is_bullish_engulfing,
    is_bearish_engulfing,
    has_rejection_wick,
    Signal,
)
from typing import Optional


def analyze(
    daily_df: pd.DataFrame,
    h4_df: pd.DataFrame,
    symbol: str,
    target_rr: float = 2.0,
) -> dict:
    trend = check_trend(daily_df)
    signal = check_entry_conditions(h4_df, trend, target_rr)

    if signal:
        from src.skills.volume_analysis import get_volume_signal
        vol = get_volume_signal(h4_df)
        if not vol["confirmed"]:
            signal = None
        else:
            signal.reason += f" | Vol {vol['ratio']:.1f}x avg"

    if signal:
        signal.symbol = symbol

    last = h4_df.iloc[-1]
    h4_rsi = rsi(h4_df["close"], 14).iloc[-1]

    return {
        "symbol": symbol,
        "trend": trend,
        "h4_rsi": round(h4_rsi, 2),
        "signal": signal,
        "daily_ema200": round(ema(daily_df["close"], 200).iloc[-1], 4),
        "h4_ema50": round(ema(h4_df["close"], 50).iloc[-1], 4),
        "last_close": round(last["close"], 4),
    }


def scan_watchlist(
    watchlist: list[str],
    get_bars_fn,
    target_rr: float = 2.0,
) -> list[dict]:
    """
    Scans a list of symbols for valid trade setups.
    get_bars_fn(symbol, timeframe) must return a DataFrame.
    """
    results = []
    for symbol in watchlist:
        try:
            daily = get_bars_fn(symbol, "1Day")
            h4 = get_bars_fn(symbol, "4Hour")
            result = analyze(daily, h4, symbol, target_rr)
            if result["signal"]:
                results.append(result)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})
    return results
