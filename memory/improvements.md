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
