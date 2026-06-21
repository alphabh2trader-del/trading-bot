# AI Swing Trading Bot

An autonomous swing trading system built for prop firm funded accounts. Runs fully automated on GitHub Actions — no server required.

---

## What It Does

- Scans 26 liquid US ETFs and large caps every trading day
- Detects **mean-reversion** swing setups (Connors RSI-2) — buys short-term dips inside an uptrend
- Manages risk automatically (position sizing, disaster stop, drawdown limits, diversification)
- Sends trade alerts and daily summaries via Telegram
- Saves performance data to git on every run
- Runs in **paper trading mode** by default before going live

---

## Strategy — `meanrev_rsi2_v1` (Connors RSI-2 mean reversion)

| Parameter | Value |
|---|---|
| Type | Swing mean reversion, long-only (no day trading) |
| Universe | 26 liquid ETFs + large caps |
| Timeframe | Daily |
| Trend filter | Close > SMA 200 |
| Entry | Wilder RSI(2) < 10 (oversold), entered next open |
| Exit | Close > SMA 5, or −8% disaster stop, or 10-day time stop |
| Risk per trade | 1% of equity (sized vs the 8% stop) |
| Max open positions | 6 (max 1 per sector) |
| Max daily loss / total drawdown | 3% / 8% (hard kill-switches) |

### Backtest (yfinance daily, out-of-sample 2019–2024, incl. COVID crash)

| Metric | In-sample (2010–18) | **Out-of-sample (2019–24)** |
|---|---|---|
| Win rate | 68.5% | **67.4%** |
| Profit factor | 1.41 | **1.29** |
| Portfolio CAGR | — | **~7.4%** |
| Max drawdown | — | **~7.1%** (under the 8% mandate) |
| Sharpe | — | **~0.89** |

Reproduce: `python -m backtest.meanrev_report` (integrated) or `python -m backtest.research` (research grid).

**Realistic objective (on a $100k paper account):** ~0.6% / month on average (~7% / year),
ending an average month near **$100,600**. Months vary — good ones reach +2–3%, some are
flat or negative, with drawdowns up to ~7%. This is honest and risk-controlled: +10%/month
is not achievable without leverage that would breach the 8% drawdown limit.

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
| 07:00 | premarket | Check overnight exits, news/sentiment flags |
| 08:00 | analysis | Scan universe for RSI-2 mean-reversion setups |
| 09:00 | plan | Confirm the day's setups |
| 09:35 | open | Enter setups at market (5-min wait after open) |
| 10:30 | midday | Rule-based exits (close>SMA5 / stop) |
| 14:00 | afternoon | Rule-based exits; positions held overnight |
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
