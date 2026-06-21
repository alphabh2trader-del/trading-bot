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
- Outcome: Initial OOS test (2019-2024) looked good (67% win, PF 1.29) BUT a proper
  stress test (`backtest/verify.py`) showed it FAILS: PF collapses to ~1.0 at realistic
  costs (0.15%/side), turns LOSING on a survivorship-free ETF-only universe, and is
  negative in 2016-2018 and 2022-2024. Thin ~0.2%/trade edge eaten by fees+slippage.
  **RETIRED 2026-06-21.**

---

## v3.0 — trend_timing_v1  (ACTIVE)

- Created: 2026-06-21
- Status: ACTIVE (paper)
- Summary: Faber GTAA trend timing. Monthly: hold each of 18 ETFs (equity + TLT + GLD)
  when its monthly close > 10-month SMA, equal weight, exposure 1.0×; else cash.
- Reason: meanrev failed the cost/survivorship/multi-period stress test. Trend timing
  trades rarely and rides big moves, so costs are negligible.
- Outcome: Validated ETF-only (no survivorship bias), 2007-2025, costs on turnover.
  Cost-robust (CAGR 10.96%→10.54% as cost triples), **profitable in EVERY sub-period**
  (2008 crash, 2022 bear included), ~10.5% CAGR / ~24% maxDD / Sharpe 0.79 — half the
  drawdown of buy & hold SPY. User chose full exposure (1.0×) on the paper account.
  Realistic target ~10.5%/yr (~0.84%/mo) on $100k paper, with ~24% drawdown accepted.

---
