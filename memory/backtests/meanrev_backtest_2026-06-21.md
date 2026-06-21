# Integrated Backtest — meanrev_rsi2_v1 — 2026-06-21

- Universe: 26 symbols (SPY, QQQ, IWM, DIA, XLF, XLK, XLE, XLV...)
- Rules: long when close>SMA200 and WilderRSI2<10; exit close>SMA5 / -8% stop / 10d; next-open entry; 0.05%/side slippage.
- compute_signal vs vectorized mask agree on sample latest bar: True

## Per-trade edge

| Period | trades | win% | avg%/trade | PF | total% | avg hold |
|--------|-------:|-----:|-----------:|---:|-------:|---------:|
| TRAIN 2010-2018 (in-sample) | 1830 | 68.5 | 0.287 | 1.41 | 525.7 | 3.5 |
| TEST 2019-2024 (OUT-OF-SAMPLE) | 1064 | 67.4 | 0.268 | 1.29 | 285.1 | 3.5 |

## Portfolio (out-of-sample, max concurrent = 6, 1% risk geometry)

- Final equity (from 100k): 153091
- CAGR: 7.36%  |  Max drawdown: 7.14%  |  Sharpe: 0.89

Edge holds out-of-sample. Win rate exceeds the 55-60% target; drawdown within the 8% mandate.