# SYSTEM IMPROVEMENT LOG

All improvements are appended here. Never delete entries.

---

## 2026-06-19 — Initial Setup

- System initialized with swing_core_v1 strategy
- Execution platform: Alpaca (paper trading)
- 4 skills registered: Market Analysis, News Filtering, Telegram Notification, Sentiment Analysis
- 2 MCP services planned: Telegram bot, Web search

---

## 2026-06-20 — Risk config unification (Phase 1)

- `memory/config.json` is now the single source of truth for risk parameters; `config.py` loads them at import (no more divergent constants).
- Daily kill-switch (`MAX_DRAWDOWN_PCT`) aligned from 2.0% → 3.0% to match `config.json` and CLAUDE.md spec ("Max daily loss: 3%").
- Added enforcement of the account-level total drawdown limit (8%), which was previously defined but never checked. Peak equity is tracked in `memory/equity_state.json` (persisted across runs); `risk/risk_engine.check_risk` locks the kill-switch when total drawdown >= `MAX_TOTAL_DRAWDOWN_PCT`.
- `MIN_RR` (scorer hard floor, 1.8) kept distinct from `config.json` `target_rr_*` — not overwritten.

---

## 2026-06-21 — Architecture cleanup, skills wiring, validation (Phases 2–7)

- **trades.csv schema unified** (`memory/trade_schema.py`): both writers (`execution/engine.py`,
  `src/memory/state.py`) now share `TRADE_FIELDNAMES` (20 cols); CSV header migrated.
- **Skills wired into the live (runner.py) path**, previously reachable only from the unused
  `main.py`: ATR stops + volume confirmation in `strategy/scorer.py`; earnings filter in
  `decision/planner.py`; sentiment gate in `routines/premarket.py` (block + size reduction
  applied in `plan.py`/`open.py`). See `skills.md` integration section.
- **Swing-hold bug fixed**: `routines/afternoon.py` no longer force-closes positions at EOD
  (it was closing every trade because none were tagged "swing") — positions now exit only on
  their TP/SL bracket, per the swing-only mandate.
- **Dead code removed**: `main.py` (redundant entry point) and `src/risk/engine.py` (orphan
  duplicate). `src/strategy/swing_core.py` kept (dependency of two registered skills).
- **Validation added**: `backtest/` engine + runner (R-multiple metrics) and `tests/` (23
  pytest cases). Added `pytest` to requirements.
- **Backtest finding (critical)**: the old `detect_structure` (strictly monotonic highs/lows)
  fired ~1/540 bars → strategy produced almost no setups. Replaced with a half-window HH/HL
  structure check. First real backtest: 56 trades, 30.4% win rate, PF 0.87, expectancy
  -0.089R → **strategy is below breakeven and NOT validated** (see `strategy.md`).
- **DST fixes**: `_is_midday()` now uses pytz (DST-safe); workflow header documents the cron
  DST caveat (winter `open` lands pre-market and skips) with recommended schedule fix.

---

## 2026-06-21 — New profitable strategy: meanrev_rsi2_v1 (Connors RSI-2)

- Researched documented swing strategies (Perplexity + literature) and built a research
  backtester (`backtest/research.py`, yfinance, train/test split, costs). Tested the
  Connors mean-reversion family vs a trend baseline; all held up out-of-sample.
- Selected **Connors RSI-2** (long-only, daily): buy close>SMA200 & WilderRSI(2)<10;
  exit close>SMA5 / -8% disaster stop / 10-day. OOS 2019-2024: 67.4% win, PF 1.29.
- Integrated as the ACTIVE strategy (`strategy/mean_reversion.py`): wired into
  `routines/analysis.py` (planning), `decision/validator.py` (skip price-zone/regime for
  market entry), `execution/engine.py` (market entry, no bracket TP), and rule-based
  exits via `execution/portfolio.check_meanrev_exits()` run in premarket/midday/afternoon.
- Risk management (full redesign): 1% risk/trade vs 8% stop, **max 6 concurrent positions**
  (up from 2), exposure cap 6%, 1/sector. Portfolio OOS: CAGR ~7.4%, max DD ~7.1% (under
  the 8% mandate), Sharpe ~0.89 — chosen as the best return that stays prop-safe.
- Universe expanded to 26 liquid ETFs + large caps (`config.BASE_WATCHLIST`).
- Added `backtest/meanrev_report.py` (integrated backtest, writes memory/backtests/) and
  `tests/test_meanrev.py`. Wilder RSI added to `strategy/indicators.py`. Strategy id ->
  `meanrev_rsi2_v1`, version 2.0. Legacy trend scorer kept but inactive.
- Realistic objective documented: ~0.6%/month (~7%/yr), ~$100,600 end-of-month on a
  $100k paper account; +10%/month is not achievable within the 8% drawdown mandate.

---

## 2026-06-21 — Stress test retired RSI-2; deployed trend_timing_v1 (Faber GTAA)

- Built `backtest/verify.py` to stress-test meanrev_rsi2_v1 on the user's concerns:
  fees+slippage sensitivity, survivorship (ETF-only), parameter robustness, multi-period.
  **Result: RSI-2 FAILS** — PF 1.29 → ~1.0 at 0.15%/side cost, LOSING on ETF-only at
  realistic cost, and negative in 2016-2018 & 2022-2024. The earlier 7.4% was inflated by
  optimistic costs + survivorship-biased stock picks + a favourable 2019-2024 window.
- Researched and validated a cost-robust replacement (`backtest/momentum.py`): **Faber
  trend timing** — monthly, hold ETFs above their 10-month SMA, else cash, across 18 ETFs
  incl. TLT + GLD. Cost-robust (CAGR ~unchanged as cost triples), profitable in every
  period 2007-2025 (incl. 2008/2022), ~10.5% CAGR / ~24% maxDD / Sharpe 0.79.
- Established (and documented) that with a fixed Sharpe, exposure/leverage only slides the
  return/drawdown line: 0.33×→8% DD/3.6%; 1.0×→24% DD/10.5%; 1.5×→34% DD/15.4%. Leverage
  cannot rescue a thin edge — it only scales a robust one. User chose **1.0× full exposure**.
- Integrated as ACTIVE: new `strategy/trend_timing.py` (10-month SMA qualification +
  equal-weight portfolio), `execution/engine.rebalance_portfolio()` (monthly buy/sell to
  target), monthly-guarded `routines/analysis.py` rebalance with persistent
  `memory/trend_state.json`. open/midday/afternoon become no-ops (no per-day setups).
  Universe -> 18 ETFs. Strategy id -> trend_timing_v1 (v3.0). Added tests/test_trend.py.
- Realistic objective: ~0.84%/month (~10.5%/yr), ~$110,500 after a year on $100k paper,
  drawdown up to ~24% accepted (paper). For a real funded account, redeploy at ~0.33×.

---

## 2026-06-21 — Self-improvement loop reconnected to the ACTIVE strategy

- **Bug found & fixed**: the learning loop (`memory/adaptive.py`) was tuning `score_threshold`
  and `min_rr` — parameters of the RETIRED swing/meanrev strategies. The ACTIVE
  `trend_timing_v1` uses NEITHER, so the bot's "learning" affected zero live trades. Worse,
  its `win_rate < 45% → tighten` rule would mis-fire on trend following (which wins ~40-45%
  by design). The loop is now **strategy-aware** (dispatches on `system.strategy`).
- **New trend-timing learning** (capital preservation, not return-chasing): reads realised
  account drawdown from `memory/equity_state.json` and walks `trend.exposure` DOWN a discrete
  ladder [1.0, 0.66, 0.33] when drawdown breaches soft (12%) / deep (18%) thresholds, then
  restores it one rung at a time after recovery (≤6%, with hysteresis to prevent flapping).
  Exposure is the single risk dial, so this directly trades return for safety only when the
  account is bleeding. Verified end-to-end: a simulated 14% drawdown de-risked 1.0×→0.66×.
- **Telegram on EVERY change**: `_notify()` sends each adjustment (de-risk / restore / flag)
  to Telegram, and every change is appended to `improvements.md` + `session_snapshots.jsonl`.
- **Monthly structural robustness re-check** (deep/weekly run, once per calendar month):
  re-runs a small SMA-lookback grid (`backtest.momentum.evaluate_lookback`) and FLAGS — via
  Telegram, without auto-changing — if `trend.sma_months` drifts out of the robust cluster.
  Structural params are never auto-flipped (that would be overfitting; see research_notes.md).
- **Drawdown kill-switch reconciled**: account backstop was 8% while the chosen 1.0× exposure
  has an expected ~24% drawdown — the bot would have self-locked on the first normal drawdown
  and never learned. Set paper backstop to 25% (catastrophe-only); documented that a FUNDED
  account must reset to `max_total_drawdown_pct_funded` (8%) AND `trend.base_exposure` 0.33×.
- `config.py` now sources `TREND_EXPOSURE`/`TREND_SMA_MONTHS` from `memory/config.json` so the
  loop's adjustments persist across CI runs (same mechanism as the monthly rebalance guard).
- Added `tests/test_adaptive.py` (7 cases: de-risk/restore/hysteresis/no-data-safe/ladder).
  Total suite 42 green. Overnight strategy research saved to `memory/research_notes.md`
  (vol targeting + multi-lookback are the top candidates, gated on the `verify.py` bar).

---
