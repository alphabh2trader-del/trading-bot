import pandas as pd
from strategy.indicators import ema, atr, detect_structure, atr_expanding


def get_regime(spy_d1: pd.DataFrame) -> str:
    if len(spy_d1) < 30:
        return "NORMAL"

    atr_series = atr(spy_d1)
    current_atr = atr_series.iloc[-1]
    avg_atr_30 = atr_series.tail(31).iloc[:-1].mean()

    if avg_atr_30 > 0 and current_atr > 2 * avg_atr_30:
        return "EXTREME"

    ema200 = ema(spy_d1["close"], 200)
    last_close = spy_d1["close"].iloc[-1]
    ema200_slope = ema200.diff().tail(5).mean()
    ema_flat = abs(ema200_slope) < 0.05 * ema200.iloc[-1] / 200

    if ema_flat and not atr_expanding(atr_series):
        return "CHOP"

    structure = detect_structure(spy_d1)
    if structure == "bullish" and last_close > ema200.iloc[-1]:
        return "TREND"

    return "NORMAL"
