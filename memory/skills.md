# ACTIVE SKILLS REGISTRY

All active skills are listed here. Never overwrite. Never remove without explicit instruction.

---

## 1. Market Analysis

- File: `src/skills/market_analysis.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Computes EMA 200, EMA 50, RSI 14, detects bullish/bearish engulfing and rejection candles.
- Functions: `ema()`, `rsi()`, `detect_candle_pattern()`, `check_trend()`, `check_entry_conditions()`

---

## 2. News Filtering

- File: `src/skills/news_filtering.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Auto-blocks trading during CPI, FOMC, NFP events using Google Custom Search and Perplexity APIs.
- Functions: `is_high_impact_event_today()`, `get_upcoming_events()`, `block_if_event()`

---

## 3. Telegram Notification

- File: `src/skills/telegram_notify.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Sends trade entry signals, exit alerts, and daily P&L summaries via Telegram bot.
- Functions: `send_message()`, `send_trade_alert()`, `send_daily_summary()`

---

## 4. Sentiment Analysis

- File: `src/skills/sentiment.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Queries Perplexity API for macro market sentiment score. Can reduce position size or block trades during extreme negative sentiment.
- Functions: `get_sentiment_score()`, `macro_environment_analysis()`, `sentiment_summary()`

---

## 5. Earnings Filter

- File: `src/skills/earnings_filter.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Blocks trade entries when a symbol has earnings within 3 days. Uses yfinance (no API key needed). Fails open — if data is unavailable the trade is not blocked.
- Functions: `get_next_earnings_date()`, `is_earnings_within()`

---

## 6. ATR Stop Loss

- File: `src/skills/atr_stops.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Replaces fixed 0.1% stop loss buffer with a volatility-adjusted ATR stop (1.5x ATR from entry). Also provides dynamic position sizing based on real risk per share.
- Functions: `atr()`, `calculate_atr_stop()`, `calculate_position_size()`

---

## 7. Volume Analysis

- File: `src/skills/volume_analysis.py`
- Status: ACTIVE
- Added: 2026-06-19
- Description: Confirms trade signals with volume. Checks volume vs 20-bar average, detects volume spikes, and identifies breakouts on high volume. Rejects entry signals where the confirmation candle is not backed by sufficient volume.
- Functions: `check_volume_confirmation()`, `detect_volume_spike()`, `check_breakout_volume()`, `get_volume_signal()`

---
