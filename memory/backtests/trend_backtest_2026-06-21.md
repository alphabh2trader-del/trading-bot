# Trend-Timing Backtest — trend_timing_v1 — 2026-06-21

- Strategy: Faber GTAA — hold ETF when monthly close > 10-month SMA, else cash
- Universe: 18 ETFs (equity + TLT bonds + GLD gold)
- Exposure: 1.0x | cost modeled: 0.30% per turnover unit (fees+slippage)

## Deployed config (exposure 1.0x), full history 2007-2025

- CAGR: 10.54%  (~0.84%/month)
- Max drawdown: 24.08%
- Sharpe: 0.79

## Per-period (positive in every regime — cost-robust)

| Period | CAGR | Max DD |
|--------|------|--------|
| 2008-2010 | 6.02% | 20.96% |
| 2011-2015 | 10.02% | 12.03% |
| 2016-2018 | 9.43% | 12.72% |
| 2019-2021 | 21.06% | 12.92% |
| 2022-2024 | 10.42% | 15.33% |
| 2025-2030 | 14.8% | 6.28% |

Passed cost (0.05->0.30%/turnover), survivorship (ETF-only), and multi-period stress tests. Reproduce: `python -m backtest.momentum`.