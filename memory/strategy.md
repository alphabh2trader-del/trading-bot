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

- Backtested: YES — 2026-06-21 (see memory/backtests/)
- Paper traded: NO (starting now)
- Live traded: NO — **DO NOT** deploy live; current edge is negative.

### Backtest result — 2026-06-21 (10-symbol watchlist, ~540d H4, threshold 65)

- Trades: 56 | Win rate: **30.4%** | Profit factor: **0.87** | Expectancy: **-0.089 R/trade**
- Target was 55–60% win rate. With +2R/-1R the breakeven win rate is 33.3%, so the
  strategy is currently **below breakeven** — it would lose money net of slippage/fees.
- Conclusion: **swing_core_v1 is NOT validated.** The setup edge needs improvement
  (entry filters, level/zone quality, RR, regime gating) before paper results can be
  trusted or live trading considered. Re-run `python -m backtest.run` after each change.

Note: a backtest also exposed that the old `detect_structure` (strictly monotonic
highs/lows) fired ~1 in 540 bars, so the strategy produced essentially no setups; it
was replaced with a half-window higher-high/higher-low structure check (2026-06-21).

### Parameter sweep — 2026-06-21 (`python -m backtest.sweep`)

Swept take-profit (2.0/2.5/3.0 R) × volume-confirmation requirement (off/on) at
threshold 65 on the 10-symbol watchlist (~540d H4). **Every combination stayed
unprofitable** (PF 0.77–0.93, all expectancies negative). At each TP the win rate sat
3–4 points BELOW that TP's breakeven (e.g. TP 2.0 needs 33.3%, got 30.4%; TP 3.0 needs
25%, got 23.2%). Requiring volume confirmation hurt results; raising TP beyond 2R only
shifts breakeven without the signal ever clearing it.

**Diagnosis: the entry signal has no demonstrable edge** on this universe/period —
tuning trade geometry or filters cannot fix that. Real improvement requires reworking
the entry signal itself (different features, true SPY-regime gating in-sample, a
different/curated universe, exit logic), which is signal research, not parameter tuning.
Defaults kept spec-compliant (TP 2.0R, no hard volume filter); `TP_R_MULT` /
`REQUIRE_VOLUME_CONFIRM` config knobs + `backtest/sweep.py` retained for future research.

**Status: DO NOT trade live. Treat paper results as unvalidated until a reworked signal
backtests with a positive edge (target win rate >50% at 2R, or PF > 1.3).**
