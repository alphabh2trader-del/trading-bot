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
