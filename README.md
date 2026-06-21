# AI Swing Trading Bot

An autonomous swing trading system built for prop firm funded accounts. Runs fully automated on GitHub Actions — no server required.

---

## What It Does

- Trades a diversified set of 18 ETFs (equities + bonds + gold) with **trend timing**
- Each month, holds the ETFs in an uptrend (above their 10-month SMA) and moves the rest to cash
- This is cost-robust (few trades, big moves) and profitable across every regime since 2008
- Sends rebalance alerts and summaries via Telegram
- Saves performance data to git on every run
- Runs in **paper trading mode** by default before going live

---

## Strategy — `trend_timing_v1` (Faber GTAA trend timing)

| Parameter | Value |
|---|---|
| Type | Trend timing / time-series momentum, long-only |
| Universe | 18 ETFs — equity index/sector + TLT (bonds) + GLD (gold) |
| Rebalance | Monthly |
| Hold rule | Monthly close > 10-month SMA (else that sleeve → cash) |
| Allocation | Equal weight across held ETFs × exposure |
| Exposure | 1.0× (full; the single risk dial — 0.33× ≈ 8% DD, 1.5× = leverage) |
| Backstops | 3% daily / 8% total kill-switches remain active |

### Backtest — stress-tested (ETF-only = no survivorship bias, 2007–2025, costs on turnover)

| Metric | Value |
|---|---|
| CAGR (0.10% → 0.30% cost) | **10.96% → 10.54%** (cost-robust) |
| Max drawdown | ~24% (vs 51% for buy & hold SPY) |
| Sharpe | ~0.79 |
| Profitable periods | **All 6** (2008-10, 2011-15, 2016-18, 2019-21, 2022-24, 2025) |

> The previous mean-reversion strategy (`meanrev_rsi2_v1`) was **retired** after a stress
> test (`backtest/verify.py`) showed its thin edge did not survive realistic fees+slippage
> or a survivorship-free universe. Trend following was chosen for robustness.

Reproduce: `python -m backtest.momentum`.

**Realistic objective (on a $100k paper account, exposure 1.0×):** ~10.5% / year ≈
~0.84% / month → ~**$110,500 after a year**. Returns are lumpy (flat/negative months happen);
the yearly figure is the headline. Drawdowns up to ~24% are the deliberate tradeoff for the
return. Note: trend following wins by asymmetry — per-trade win rate is ~40-45%, not >50%,
but it is profitable across all market regimes.

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
| 07:00 | premarket | Health check, news/sentiment flags |
| 08:00 | analysis | **Monthly trend rebalance** (acts once per month; no-op other days) |
| 09:00 | plan | (no per-day setups under trend timing) |
| 09:35 | open | (no per-day entries under trend timing) |
| 10:30 | midday | Position check |
| 14:00 | afternoon | Position check |
| 16:00 | review | EOD report + **self-improvement loop** (see below) |
| Saturday 10:00 | weekly | Full weekly report + **monthly robustness re-check** |

All routines commit their output back to the repo so state persists between runs.

---

## Self-Improvement Loop (`memory/adaptive.py`)

The bot adapts the **active** strategy between sessions — never during market hours:

- **Daily (review)** — reads realised account drawdown and walks `trend.exposure` down a
  discrete ladder (1.0× → 0.66× → 0.33×) when drawdown breaches 12% / 18%, then restores it
  one rung at a time after recovery (with hysteresis). Pure capital preservation — it only
  trades return for safety when the account is bleeding.
- **Monthly (weekly run)** — re-runs an SMA-lookback grid and **flags** (via Telegram, no
  auto-change) if the active lookback drifts out of its robust cluster. Structural parameters
  are never auto-flipped — that would be overfitting.
- **Every change** is logged to `improvements.md` + `session_snapshots.jsonl` **and sent to
  Telegram**, so you see each adjustment as it happens.

The loop is strategy-aware: it tunes the parameters the live strategy actually uses (it used
to tune dead swing-strategy knobs — fixed 2026-06-21).

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
