# STRATEGY HISTORY

All past strategies are logged here. Never delete entries.

---

## v1.0 — swing_core_v1

- Created: 2026-06-19
- Status: ACTIVE
- Summary: EMA 200 trend filter (D1) + RSI 14 pullback entry (H4). Structure-based SL. 1.5R–2R TP.
- Reason for creation: Initial system setup.
- Outcome: First backtest 2026-06-21 — 56 trades, 30.4% win rate, PF 0.87, expectancy
  -0.089R. Below breakeven; NOT validated. **RETIRED 2026-06-21** in favour of v2.0.

---

## v2.0 — meanrev_rsi2_v1  (ACTIVE)

- Created: 2026-06-21
- Status: ACTIVE (paper)
- Summary: Connors RSI-2 mean reversion, long-only on 26 liquid ETFs/large caps. Buy
  close>SMA200 & WilderRSI(2)<10; exit close>SMA5 / -8% stop / 10-day. 1% risk, max 6
  concurrent positions.
- Reason for creation: swing_core_v1 had no edge. Researched documented mean-reversion
  strategies (Connors family, via Perplexity + literature) and validated empirically.
- Outcome: Backtested train 2010-2018 + OOS test 2019-2024. OOS: 67.4% win, PF 1.29,
  CAGR ~7.4%, max drawdown ~7.1%, Sharpe ~0.89. First profitable, OOS-validated,
  mandate-compliant strategy. Realistic target ~0.6%/month (~7%/yr) on $100k paper.

---
