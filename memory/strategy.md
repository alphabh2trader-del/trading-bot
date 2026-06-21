# CURRENT ACTIVE STRATEGY — v3.0

## Version

- ID: trend_timing_v1
- Created: 2026-06-21
- Status: ACTIVE (paper trading)
- Replaces: meanrev_rsi2_v1 (RETIRED — failed the cost/survivorship/multi-period
  stress test; ~0.2%/trade edge eroded by realistic fees+slippage. See history.)

## Strategy Type

**Trend timing** (Faber GTAA / time-series momentum), long-only, MONTHLY rebalance.
Few trades, large moves captured → transaction costs are negligible, unlike the
short-hold mean-reversion that preceded it.

## Universe (18 ETFs)

Equity index/sector (SPY, QQQ, IWM, DIA, XLF, XLK, XLE, XLV, XLY, XLP, XLI, XLU, XLB,
SMH, XBI, KRE) + **TLT (long bonds)** + **GLD (gold)**. The defensive sleeves trend up
when equities fall, which roughly halves drawdown vs buy & hold.

## Rules (monthly)

- For each ETF: HOLD if monthly close > its 10-month SMA (uptrend); else that sleeve = CASH.
- Capital split EQUALLY across the held ETFs, scaled by EXPOSURE (deployed at 1.0×).
- Rebalanced once per calendar month (first trading day). No intraday management.

## Risk Management

- Exposure 1.0× (full strategy, no leverage). Drawdown ~24% is accepted (paper account).
  Exposure is the single risk dial: 0.33× → ~8% DD; 1.5× (leverage) → ~34% DD.
- Diversification across 18 uncorrelated-ish ETFs incl. bonds & gold.
- Daily 3% / total 8% kill-switches remain active as hard backstops.

## Validation — passed the FULL stress test (this is why it was chosen)

Tested ETF-only (NO survivorship bias), 2007-2025, costs charged on turnover:

- **Cost-robust**: CAGR 10.96% (0.10% cost) → 10.54% (0.30% cost) — barely moves.
- **Profitable in EVERY period** (0.30% cost): 2008-10 +6.0%, 2011-15 +10.0%, 2016-18 +9.4%,
  2019-21 +21.1%, 2022-24 +10.4%, 2025 +14.8%.
- **vs Buy & Hold SPY**: SPY = 10.6% CAGR / 50.8% maxDD; this = ~10.5% CAGR / ~24% maxDD
  (similar return, HALF the drawdown), Sharpe ~0.79.

NOTE: trend following wins by asymmetry — per-trade win rate is ~40-45% (NOT >50%), but it
is profitable across all regimes, which is the real robustness test.

Reproduce: `python -m backtest.momentum` (full) or `python -m backtest.verify` (cost/
survivorship/period stress on the old RSI-2, for the record).

## REALISTIC OBJECTIVE (paper account, exposure 1.0×)

Assuming the Alpaca paper default of **$100,000**:

- Expected average: **~10.5% / year ≈ ~0.84% / month** — about **+$840 in an average month**,
  ending a year near **$110,500**.
- Returns are LUMPY: trend strategies have flat/negative months (down ~3-5%) and strong
  months (+5-8%). The headline is the yearly figure, not any single month.
- Expect drawdowns up to **~24%** (this is the deliberate tradeoff for the higher return;
  the user chose full exposure on a paper account).
- NOT a guarantee — backtest edge ≠ future returns, but this edge held across 2007-2025
  including the 2008 crash and 2022 bear, net of costs and free of survivorship bias.

## Validation Status

- Backtested: YES (2007-2025, cost+survivorship+multi-period robust)
- Paper traded: starting now
- Live traded: NO (unlock per CLAUDE.md; note: 24% DD exceeds an 8% funded-account limit —
  for a real funded account, redeploy at exposure ~0.33×)
