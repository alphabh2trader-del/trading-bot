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
