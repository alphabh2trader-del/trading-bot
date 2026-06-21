# AI Swing Trading Bot

An autonomous **dual-strategy** trading system for prop-firm-style funded accounts. It runs
two uncorrelated sleeves on one Alpaca account, on **disjoint universes**, at the same time:

- **Swing sleeve (70% of capital, daily):** a D1-trend / H4-pullback system on 16 liquid
  large-cap stocks — risk-based 1% per trade.
- **Trend sleeve (30% of capital, monthly):** the cost-robust Faber GTAA ETF rotation
  (`trend_timing_v1`) — the proven defensive core.

It runs **fully on GitHub Actions** — no server, no VPS, no always-on machine. Every
scheduled routine checks out the repo, runs, and commits its state back, so the bot's
memory lives in git.

> **Status:** paper trading (`dual_swing+trend_v1`). Live trading stays locked until the
> documented unlock conditions are met (see [Live Trading Unlock](#live-trading-unlock-conditions)).
>
> **Realistic expectation:** ~0.5–1.0%/month (~6–10%/yr), **lumpy** month to month — **not**
> 5%/month. A consistently higher return is not achievable under capital-preservation
> constraints without large leverage and the matching drawdown. See [Strategy](#strategy).

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Strategy — `trend_timing_v1`](#strategy--trend_timing_v1-faber-gtaa-trend-timing)
4. [Backtest](#backtest--stress-tested)
5. [Risk Model (layered)](#risk-model-layered)
6. [Self-Improvement Loop](#self-improvement-loop-memoryadaptivepy)
7. [Rebalance Safety Mechanics](#rebalance-safety-mechanics)
8. [Tech Stack](#tech-stack)
9. [Active Skills](#active-skills-modules)
10. [Automation & State Persistence](#automation--state-persistence)
11. [Repository Layout](#repository-layout)
12. [Setup](#setup)
13. [Running Locally](#running-locally)
14. [Testing](#testing)
15. [Live Trading Unlock & Funded Migration](#live-trading-unlock-conditions)
16. [Troubleshooting](#troubleshooting)
17. [Risk Disclaimer](#risk-disclaimer)

---

## What It Does

- Runs **two strategies at once** on one account, on disjoint symbol sets so they never collide:
  - **Swing (70%):** every day it scans 16 liquid large-cap stocks for D1-trend / H4-pullback
    setups, takes the qualifying ones (gated by a shared risk budget), and manages each with an
    ATR-buffered stop and a 2R target.
  - **Trend (30%):** once a month it holds the ETFs in an uptrend (monthly close above their
    10-month SMA), equal-weighted, and moves the rest to cash — cost-robust, profitable in every
    market regime since 2008 in stress testing.
- Sends **plan, trade, exit, EOD and weekly** alerts via Telegram.
- **Learns between sessions**: de-risks the trend sleeve when the account draws down, restores it
  after recovery, and flags structural parameter drift for human review.
- Commits all state (trades, config, equity peak, snapshots) back to git on every run.

---

## Architecture & Data Flow

The single entry point is [`runner.py`](runner.py), invoked once per routine:

```
python runner.py --routine <name>
        │
        ├── load_state()            # memory/daily_plan.json (resets each calendar day)
        ├── check_risk(state)       # kill-switches (daily loss + total drawdown) — may exit
        └── routines.<name>.run(state)
                │
                ├── data/market_data.py        → Alpaca historical bars (IEX feed)
                ├── strategy/trend_timing.py   → who qualifies (10-month SMA)
                ├── execution/engine.py        → rebalance_portfolio() → Alpaca orders
                ├── risk/ + state/             → drawdown tracking, kill-switches
                ├── memory/adaptive.py         → self-improvement (review/weekly only)
                └── reporting/telegram.py      → notifications
        │
        └── save_state()            # persist daily_plan.json
```

**Two key ideas:**

- **Alpaca is the source of truth for positions.** `rebalance_portfolio()` reads live
  positions from Alpaca and trades the *delta* to the target — the local `trades.csv` is a
  log, not the position book.
- **State persists through git, not a database.** Each CI job ends by committing `memory/`.
  The next job checks out that state. Files like `trend_state.json` (last rebalance month),
  `equity_state.json` (peak equity), and `config.json` (live-tunable params) are the bot's
  "memory" across otherwise-stateless runs.

---

## Strategy — `dual_swing+trend_v1`

Two sleeves, disjoint universes, one account:

| | **Swing sleeve** | **Trend sleeve** |
|---|---|---|
| Capital | 70% | 30% |
| Universe | 16 liquid large-cap **stocks** | 18 **ETFs** (eq + TLT + GLD) |
| Cadence | Daily | Monthly |
| Signal | D1 close vs EMA200 (trend) + H4 pullback to EMA50 + RSI zone + structure/MACD/volume score | Monthly close > 10-month SMA |
| Entry | Score above threshold, validated (spread/zone/regime) | Equal weight × `exposure` |
| Stop / target | Structure low/high + ATR(14)×1.5 buffer / **2R** | None — exits via monthly rebalance |
| Sizing | **1% risk** of equity per trade (shrinks on losing days) | 30%-sleeve equal weight |

They never interfere: the monthly rebalance is **scoped to the ETF universe and 30% of
capital** (`rebalance_portfolio(..., capital_frac=0.30, universe=TREND_UNIVERSE)`), so swing
stock positions are never touched, and the swing scorer only sees the stock watchlist.

### Trend sleeve — why Faber GTAA (and not the retired RSI-2 mean reversion)

Mean reversion's thin
~0.2%/trade edge did **not** survive realistic fees + slippage or a survivorship-free
universe (it was retired after `backtest/verify.py` showed PF 1.29 → ~1.0 at 0.15%/side and
losing on ETF-only data). Trend timing trades rarely and rides large moves, so costs are a
negligible fraction of each trade.

The defensive sleeves (**TLT, GLD**) are what cut the drawdown: in equity bear markets they
often trend *up*, so the bot rotates into them instead of sitting fully in cash.

### Backtest — both sleeves, net of fees

**Trend sleeve** — ETF-only (no survivorship bias), 2007–2026, costs on turnover
(`python -m backtest.momentum`):

| Metric | 0.10% cost | 0.30% cost (realistic) |
|---|---|---|
| CAGR | 10.96% | **10.54%** |
| Max drawdown | 23.7% | **24.1%** |
| Sharpe | 0.82 | **0.79** |

Positive in **every** sub-period (2008–10 +6.0%, 2011–15 +10.0%, 2016–18 +9.4%, 2019–21
+21.1%, 2022–24 +10.4%, 2025+ +14.8%). Buy & hold SPY over the same window: ~10.6% CAGR but
**50.8%** drawdown — same return, half the pain. On the 30% allocation the trend sleeve
contributes ~3.1%/yr.

**Swing sleeve** — daily-bar proxy of the H4 system, 2021–2026, account-level 1%/6% sim,
0.10% round-trip cost (`python -m backtest.swing`):

| Trades | Win rate | Profit factor | Avg R | Return | Max DD |
|---|---|---|---|---|---|
| 167 | 46.1% | 1.22 | 0.14 | ~0.27%/mo (~3.2%/yr) | 10.4% |

The swing edge **survives fees** (PF > 1, positive avg R) but is **thin**. A daily proxy
understates an intraday-entry edge, so live H4 should do somewhat better — but do **not**
expect 5%/month from it.

> **Blended realistic objective:** ~**0.5–1.0%/month (~6–10%/yr)**, lumpy month to month.
> 5%/month consistently is **not** achievable under capital-preservation constraints without
> large leverage and the matching drawdown. The headline is the yearly figure, not any month.
> Backtest edge ≠ future returns.

---

## Risk Model (layered)

Rewritten 2026-06-21 by user decision: **a losing day never halts trading and there is no
fixed position-count cap** — the system stays opportunistic, but bounded. Layers, slow to fast:

1. **Position construction** — trend sleeve: equal weight × `exposure`, diversified across 18
   ETFs incl. defensive sleeves (bonds, gold). Swing sleeve: 1% risk per trade, ATR-buffered stop.
2. **Open-risk budget** (the swing gate, replaces the count cap) — new swing entries are allowed
   only while the **sum of open swing risk** stays under `max_open_risk_pct` (**6%**). Good
   setups are taken until the budget is spent — no arbitrary "max 2 trades" cut-off. A
   `max_positions_ceiling` (20) is a sanity backstop against a runaway day.
3. **Daily de-risk ladder** (replaces the daily kill-switch) — per-trade size shrinks as the
   day's realised loss grows: `<1% → 1.0× · <2% → 0.66× · <3% → 0.5× · ≥3% → 0.33×` (never 0).
   A bad day **reduces size, it does not stop the bot.**
4. **Adaptive exposure ladder** (slow, trend sleeve) — the self-improvement loop walks trend
   `exposure` down `1.0× → 0.66× → 0.33×` as account drawdown deepens, restoring after recovery.
5. **Account catastrophe stop** (the ONLY hard halt) — runs at the start of **every** routine:
   tracks all-time peak equity in `equity_state.json` and **LOCKS** the bot if drawdown crosses
   `max_total_drawdown_pct` (25% paper / 8% funded). This is what protects a funded account from
   prop-firm termination. A locked bot does nothing until `--routine reset`.

All thresholds live in **`memory/config.json`** (single source of truth); [`config.py`](config.py)
loads them at import. There is no second place to change a limit.

> **Paper vs funded:** the 25% catastrophe stop is for *paper*. A real funded account (8% limit)
> must set `max_total_drawdown_pct = 8` and redeploy the trend sleeve at **0.33× exposure** (see
> [Funded Migration](#funded-account-migration)). The daily de-risk ladder protects capital well
> before that catastrophe stop is ever reached.

---

## Self-Improvement Loop (`memory/adaptive.py`)

The bot adapts the **active** strategy between sessions — **never during market hours**.
It is *strategy-aware*: it tunes the parameters the live strategy actually uses.

- **Daily (review, 16:00 ET)** — reads realised account drawdown from `equity_state.json`
  and walks `trend.exposure` **down** a discrete ladder (1.0× → 0.66× → 0.33×) when drawdown
  breaches **12% / 18%**, then restores it **one rung at a time** after recovery (≤6%, with
  hysteresis so it doesn't flap). Pure capital preservation — it only trades return for
  safety when the account is bleeding. The trim takes effect at the next monthly rebalance
  (the 25% kill-switch is the immediate catastrophe stop).
- **Monthly (weekly run, deep)** — re-runs an SMA-lookback grid and **flags** (Telegram, no
  auto-change) if the active 10-month lookback drifts out of its robust cluster. Structural
  parameters are **never auto-flipped** — that would be overfitting.
- **Every change** is logged to `improvements.md` + `session_snapshots.jsonl` **and sent to
  Telegram**, so you see each adjustment as it happens.

Covered by `tests/test_adaptive.py` (de-risk / restore / hysteresis / no-data-safe / ladder).

---

## Rebalance Safety Mechanics

The monthly rebalance ([`execution/engine.py:rebalance_portfolio`](execution/engine.py)) is
built to **never trade on bad information**:

- **Data-outage abort** — if more than **25%** of the universe fails to return data, the
  rebalance is **aborted** and the month is **not marked done**, so the next scheduled run
  retries instead of trading on a partial picture.
- **Protect held positions** — any symbol whose data couldn't be fetched this run is treated
  as *unknown*, not *bearish*: it is **never sold**. A transient Alpaca hiccup can no longer
  liquidate the book.
- **Resize to weight** — for symbols already held, the bot trades the *delta* toward the
  target dollar value, but only when drift exceeds the **15% rebalance band** (no churn on
  small price moves). This is what makes an exposure de-risk actually **trim** existing
  holdings, and keeps the book equal-weight over time.

Covered by `tests/test_rebalance.py` (new entries / resize / band / exit / protect).

---

## Tech Stack

| Component | Tool |
|---|---|
| Broker | [Alpaca](https://alpaca.markets) (paper + live, `alpaca-py`) |
| Market data | Alpaca historical bars (IEX feed) |
| Backtest data | [yfinance](https://github.com/ranaroussi/yfinance) (ETF closes, survivorship-free) |
| Market sentiment / news | [Perplexity AI](https://www.perplexity.ai) (`sonar`) |
| Notifications | Telegram Bot API |
| Scheduling | GitHub Actions (cron, UTC) |
| Tests | pytest (51 tests) |
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

> Under `dual_swing+trend_v1` these skills are **active again** on the swing sleeve: ATR stops and
> volume confirmation feed `strategy/scorer.py`, the earnings filter gates entries in
> `decision/planner.py`, and news/sentiment flags block or reduce in the premarket/open routines.

---

## Automation & State Persistence

All routines run via GitHub Actions on a UTC cron and commit `memory/` back to the repo.

| Time (ET) | Routine | What it does |
|---|---|---|
| 07:00 | premarket | Health check, overnight exits, news/sentiment flags |
| 08:00 | analysis | **Swing plan (daily)** — scan stocks for setups; **+ trend rebalance** once per month |
| 09:00 | plan | Plan checkpoint |
| 09:35 | open | **Execute swing entries** after the 5-min wait (gated by the risk budget) |
| 10:30 | midday | Position check + TP/SL exits |
| 14:00 | afternoon | Position check + TP/SL exits (positions held overnight — swing, no force-close) |
| 16:00 | review | EOD report + **self-improvement loop** (daily) |
| Saturday 10:00 | weekly | Full weekly report + **monthly robustness re-check** |

**How state survives stateless CI runs:** each job ends with
`git add memory/ && commit && push` (with `pull --rebase` + retry so a concurrent push never
loses an update). The committed files — `daily_plan.json`, `trend_state.json`,
`equity_state.json`, `config.json`, `trades.csv`, `session_snapshots.jsonl` — are read back on
the next run. **None of these are gitignored.**

> **DST:** crons are UTC and set for EDT. For trend timing this is harmless — the monthly
> rebalance submits DAY market orders that Alpaca queues for the next open regardless of the
> exact minute, and `open` takes no per-day entries. See the header of
> [`trading_routines.yml`](.github/workflows/trading_routines.yml).

---

## Repository Layout

```
runner.py                  Single entry point (--routine <name>)
config.py                  Loads memory/config.json; constants (watchlist, fees, thresholds)
routines/                  One module per scheduled job (premarket … weekly)
strategy/scorer.py         Swing setup scoring (EMA/RSI/MACD/ATR/volume) → Setup
strategy/trend_timing.py   10-month SMA qualification + equal-weight portfolio construction
decision/planner.py        Swing plan: scan watchlist, earnings filter, rank by score
execution/engine.py        open_paper_trade(), rebalance_portfolio() (scoped), trade logging
execution/portfolio.py     Open-position queries, TP/SL exit checks, daily summary
risk/risk_engine.py        Open-risk budget + daily de-risk ladder + catastrophe stop
state/                     daily_plan.json + equity peak / drawdown tracking
data/market_data.py        Alpaca bars + live quotes (timeout-safe fetch)
memory/                    Persistent state + logs (committed each run)
  ├── config.json          Single source of truth for risk/strategy params
  ├── adaptive.py          Self-improvement loop
  ├── trades.csv           Trade log (20-column shared schema)
  ├── equity_state.json    Peak equity (drawdown tracking)
  ├── trend_state.json     Last rebalance month + holdings
  ├── research_notes.md    Strategy research backlog (gated on verify.py)
  └── backtests/           Backtest reports
backtest/                  swing.py (swing sleeve), momentum.py (trend sleeve), verify.py (RSI-2)
reporting/                 Telegram, EOD + weekly reports
src/                       Skills (ATR/volume/earnings) + alpaca_bridge (used in prod)
tests/                     pytest suite (51 tests)
.github/workflows/         trading_routines.yml (8 scheduled jobs + manual reset)
```

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/alphabh2trader-del/trading-bot.git
cd trading-bot
pip install -r requirements.txt
```

### 2. Create your `.env`

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
PERPLEXITY_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TRADING_MODE=paper
```

### 3. Add the same as GitHub Secrets

Repo → **Settings → Secrets and variables → Actions** → add each variable above.

### 4. Enable GitHub Actions

The workflows in `.github/workflows/` run automatically on schedule. You can also trigger any
routine manually via **Actions → Trading Routines → Run workflow** (including `reset`).

---

## Running Locally

```bash
python runner.py --routine premarket
python runner.py --routine analysis     # daily swing plan + monthly trend rebalance
python runner.py --routine open          # execute swing entries
python runner.py --routine review        # EOD + self-improvement loop
python runner.py --routine weekly
python runner.py --routine reset         # clears a LOCKED kill-switch
```

Without Alpaca credentials the broker calls fail safe (the routines no-op gracefully and
Telegram prints to the console instead of sending).

---

## Testing

```bash
python -m pytest -q          # 51 tests
python -m backtest.swing     # swing-sleeve backtest, net of fees (writes memory/backtests/)
python -m backtest.momentum  # trend-sleeve backtest (writes memory/backtests/)
python -m backtest.verify    # RSI-2 stress test (why mean reversion was retired)
```

Tests are pure-logic and network-free (broker/data/Telegram are stubbed), so they run
anywhere in under a second.

---

## Live Trading Unlock Conditions

The bot stays in **paper** mode until, over a 30-day period:

- Win rate ≥ 60%
- Total drawdown < 8%
- Minimum 10 closed trades

A weekly report is sent to Telegram every Saturday with live-readiness status.

### Funded Account Migration

Before connecting a real funded prop account (typical 8% max drawdown):

1. In `memory/config.json`, set `risk.max_total_drawdown_pct` to **8.0**.
2. Set `trend.base_exposure` and `trend.exposure` to **0.33** (≈8% expected drawdown).
3. Set `TRADING_MODE=live` and point `ALPACA_BASE_URL` at the live endpoint.
4. Start with minimal exposure; scale only after stability is confirmed.

At 0.33× the realistic target is ~3.6% / year with ~8% max drawdown — the price of fitting
inside a strict prop-firm limit.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Telegram says **"System LOCKED"** | A kill-switch tripped. Investigate, then `--routine reset`. |
| **"REBALANCE ABORTED — data unavailable"** | Alpaca data outage; the bot retries next run. No action needed. |
| No rebalance happened this month | It only acts on the first scheduled run of the month; check `memory/trend_state.json`. |
| CI job failed | A Telegram "ERROR: <routine> failed" alert is sent; check the Actions log. |
| Backtest can't download data | `yfinance` needs internet; the committed report in `memory/backtests/` is the fallback. |

---

## Risk Disclaimer

This bot is for educational and research purposes. Trading involves substantial risk of loss.
Past paper performance does not guarantee future live results. Use at your own risk.
