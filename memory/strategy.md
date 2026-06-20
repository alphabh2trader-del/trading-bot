# CURRENT ACTIVE STRATEGY — v1.0

## Version

- ID: swing_core_v1
- Created: 2026-06-19
- Status: ACTIVE (paper trading)

## Strategy Type

Swing Trading — NO day trading allowed.

## Timeframes

- Trend: Daily (D1)
- Entry: 4H (H4)

## Trend Filter

EMA 200 on D1:
- Price > EMA200 → LONG bias only
- Price < EMA200 → SHORT bias only
- No counter-trend trades allowed

## Entry Logic

### LONG

1. D1 price above EMA 200 (bullish trend confirmed)
2. Price retraces to EMA 50 OR key support zone on H4
3. RSI 14 between 40–55 and rising
4. Candle confirmation: bullish engulfing or strong rejection wick

### SHORT

1. D1 price below EMA 200 (bearish trend confirmed)
2. Price retraces to EMA 50 OR key resistance zone on H4
3. RSI 14 between 45–60 and falling
4. Candle confirmation: bearish engulfing or rejection wick

## Exit Rules

- Take Profit: 1.5R – 2R
- Stop Loss: structure-based (last swing high/low)
- Trailing SL: only when logically justified, never emotional

## Validation Status

- Backtested: NO
- Paper traded: NO (starting now)
- Live traded: NO
