# AI Swing Trading Bot

An autonomous swing trading system built for prop firm funded accounts. Runs fully automated on GitHub Actions — no server required.

---

## What It Does

- Scans a watchlist of 10 US stocks every trading day
- Detects swing trade setups using EMA, RSI, and candlestick patterns
- Manages risk automatically (position sizing, stop loss, drawdown limits)
- Sends trade alerts and daily summaries via Telegram
- Saves performance data and adapts its parameters weekly
- Runs in **paper trading mode** by default before going live

---

## Strategy

| Parameter | Value |
|---|---|
| Type | Swing trading only (no day trading) |
| Timeframes | Daily (trend) + 4H (entry) |
| Trend filter | EMA 200 |
| Entry trigger | EMA 50 pullback + RSI 40–55 + bullish/bearish candle |
| Risk per trade | 1% of equity |
| Take profit | 1.5R – 2R |
| Stop loss | ATR-based (1.5× ATR from entry) |
| Max open trades | 2 |
| Max daily loss | 3% |
| Max drawdown | 8% |

---

## Tech Stack

| Component | Tool |
|---|---|
| Broker | [Alpaca](https://alpaca.markets) (paper + live) |
| Market sentiment | [Perplexity AI](https://www.perplexity.ai) |
| Notifications | Telegram Bot |
| Scheduling | GitHub Actions (no server needed) |
| Language | Python 3.11 |

---

## Active Skills (Modules)

| Skill | Description |
|---|---|
| Market Analysis | EMA, RSI, candlestick pattern detection |
| News Filtering | Blocks trading during CPI, FOMC, NFP events |
| Sentiment Analysis | Perplexity macro sentiment score — blocks on extreme bear |
| Earnings Filter | Blocks entries within 3 days of earnings |
| Volume Analysis | Confirms signals with volume vs 20-bar average |
| ATR Stop Loss | Volatility-adjusted stop loss + dynamic position sizing |
| Telegram Notify | Trade alerts, exit notifications, daily P&L summary |

---

## Daily Routine (Automated via GitHub Actions)

| Time (ET) | Routine | What it does |
|---|---|---|
| 07:00 | premarket | Rebuild watchlist, check overnight news |
| 08:00 | analysis | Compute market regime, score all tickers |
| 09:00 | plan | Build trade plan for the day |
| 09:35 | open | Execute valid setups (5-min wait after open) |
| 10:30 | midday | Check TP/SL hits, exits only |
| 14:00 | afternoon | Final position check before close |
| 16:00 | review | EOD report + adaptive parameter learning |
| Saturday 10:00 | weekly | Full weekly report sent to Telegram |

All routines commit their output back to the repo so state persists between runs.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/alphabh2trader-del/trading-bot.git
cd trading-bot
pip install -r requirements.txt
```

### 2. Create your `.env` file

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
PERPLEXITY_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TRADING_MODE=paper
```

### 3. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions** and add the same variables as above.

### 4. Enable GitHub Actions

The workflows in `.github/workflows/` will run automatically on schedule. You can also trigger any routine manually via **Actions → Trading Routines → Run workflow**.

---

## Running Locally

```bash
# Run a specific routine manually (this is the single entry point — runner.py)
python runner.py --routine premarket
python runner.py --routine analysis
python runner.py --routine plan
python runner.py --routine open
python runner.py --routine midday
python runner.py --routine afternoon
python runner.py --routine review
python runner.py --routine weekly
```

---

## Live Trading Unlock Conditions

The bot stays in paper mode until these conditions are met over a 30-day period:

- Win rate ≥ 60%
- Total drawdown < 8%
- Minimum 10 closed trades

A weekly report is sent to Telegram every Saturday with live readiness status.

---

## Risk Disclaimer

This bot is for educational and research purposes. Trading involves substantial risk of loss. Past paper performance does not guarantee future live results. Use at your own risk.
