import pandas as pd
from dataclasses import dataclass
from typing import Optional

import config
from strategy.indicators import (
    ema, rsi, macd, atr, rvol,
    detect_structure, macd_bullish_cross, macd_bearish_cross, atr_expanding,
)
from strategy.levels import find_nearest_level
from src.skills.atr_stops import calculate_atr_stop
from src.skills.volume_analysis import get_volume_signal


@dataclass
class Setup:
    symbol: str
    direction: str          # "long" | "short"
    entry_price: float
    stop_loss: float
    take_profit: float
    rr: float
    score: int
    sector: str
    regime: str
    rsi_value: float
    reason: str


def calculate_score(
    symbol: str,
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    regime: str,
) -> Optional[Setup]:
    if len(d1) < 200 or len(h4) < 50:
        return None

    # --- Indicators ---
    ema200_d1 = ema(d1["close"], 200)
    ema50_h4 = ema(h4["close"], 50)
    rsi14 = rsi(h4["close"], 14)
    macd_data = macd(h4["close"])
    atr14_h4 = atr(h4)
    rv = rvol(h4)
    structure = detect_structure(d1)

    last_d1 = d1.iloc[-1]
    last_h4 = h4.iloc[-1]
    last_rsi = rsi14.iloc[-1]
    prev_rsi = rsi14.iloc[-2]
    last_atr = atr14_h4.iloc[-1]

    above_ema200 = last_d1["close"] > ema200_d1.iloc[-1]
    near_ema50 = abs(last_h4["close"] - ema50_h4.iloc[-1]) / ema50_h4.iloc[-1] < 0.008

    # --- Direction ---
    if above_ema200 and structure == "bullish":
        direction = "long"
    elif not above_ema200 and structure == "bearish":
        direction = "short"
    else:
        return None

    # --- RSI zone ---
    rsi_ok = (direction == "long" and 38 <= last_rsi <= 58 and last_rsi > prev_rsi) or \
             (direction == "short" and 42 <= last_rsi <= 62 and last_rsi < prev_rsi)

    if not rsi_ok or not near_ema50:
        return None

    # --- Entry / SL / TP ---
    # Stop is structure-based (recent swing low/high) but uses an ATR volatility
    # buffer (via the ATR-stop skill) instead of a flat 0.1%. We keep whichever
    # level leaves the most room from entry, so normal noise doesn't stop us out.
    entry = last_h4["close"]
    atr_stop, _ = calculate_atr_stop(h4, direction, atr_multiplier=config.ATR_STOP_MULT)
    if direction == "long":
        sl = min(last_h4["low"] * 0.999, atr_stop)
        tp = entry + (entry - sl) * 2.0
    else:
        sl = max(last_h4["high"] * 1.001, atr_stop)
        tp = entry - (sl - entry) * 2.0

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = reward / risk if risk > 0 else 0

    # --- Scoring ---

    # Trend quality (0–25)
    trend_score = 0
    if above_ema200:
        trend_score += 15
    if structure in ("bullish", "bearish"):
        trend_score += 10

    # Momentum (0–25)
    momentum_score = 0
    if rsi_ok:
        momentum_score += 10
    if (direction == "long" and macd_bullish_cross(macd_data)) or \
       (direction == "short" and macd_bearish_cross(macd_data)):
        momentum_score += 10
    if atr_expanding(atr14_h4):
        momentum_score += 5

    # Structure (0–20)
    structure_score = 10 if near_ema50 else 0
    level = find_nearest_level(h4, entry, direction)
    if level:
        structure_score += 10

    # Liquidity (0–15)
    liquidity_score = 0
    if rv >= 2.0:
        liquidity_score = 15
    elif rv >= 1.5:
        liquidity_score = 8

    # Volume confirmation (0–5) — via volume-analysis skill
    vol_signal = get_volume_signal(h4)
    volume_score = config.VOLUME_CONFIRM_BONUS if vol_signal["confirmed"] else 0

    # R:R (0–15)
    if rr < config.MIN_RR:
        return None  # hard floor
    elif rr >= 3.0:
        rr_score = 15
    elif rr >= 2.0:
        rr_score = 10
    else:
        rr_score = 5

    # Regime bonus
    regime_bonus = config.REGIME_BONUS.get(regime, 0)

    total = trend_score + momentum_score + structure_score + liquidity_score + volume_score + rr_score + regime_bonus
    total = max(0, min(100, total))

    sector = config.SECTOR_MAP.get(symbol, "unknown")

    return Setup(
        symbol=symbol,
        direction=direction,
        entry_price=round(entry, 4),
        stop_loss=round(sl, 4),
        take_profit=round(tp, 4),
        rr=round(rr, 2),
        score=total,
        sector=sector,
        regime=regime,
        rsi_value=round(last_rsi, 1),
        reason=f"EMA200 {'above' if above_ema200 else 'below'} | RSI {last_rsi:.1f} | MACD {'cross' if momentum_score >= 20 else 'no cross'} | Vol {'OK' if volume_score else 'weak'}({vol_signal['ratio']}) | R:R {rr:.2f}",
    )
