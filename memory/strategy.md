# CURRENT ACTIVE STRATEGY — v2.0

## Version

- ID: meanrev_rsi2_v1
- Created: 2026-06-21
- Status: ACTIVE (paper trading)
- Replaces: swing_core_v1 (trend pullback — backtested NEGATIVE, retired; see strategy_history.md)

## Strategy Type

Short-term swing **mean reversion** (Connors RSI-2 family), long-only. NO day trading
(positions are held overnight, exit on a daily rule). NO counter-trend shorts.

## Universe

26 liquid symbols: index/sector ETFs (SPY, QQQ, IWM, DIA, XLF, XLK, XLE, XLV, XLY,
XLP, XLI, XLU, XLB, SMH, XBI, KRE) + large caps (AAPL, MSFT, NVDA, AMZN, GOOGL, META,
TSLA, JPM, V, UNH). Mean reversion is strongest on liquid ETFs.

## Rules (daily bars)

ENTRY (long):
- Close > SMA(200)  — only buy dips inside an uptrend
- Wilder RSI(2) < 10 — short-term oversold
- Entered at the next session's open (market order)

EXIT (whichever first):
- Close > SMA(5)  — primary, rule-based (mean reversion completed)
- Price <= entry × 0.92  — disaster stop (-8%)
- Held >= 10 sessions  — time stop

## Risk Management

- 1% account risk per trade, sized against the 8% disaster stop (~12.5% equity/position)
- Max 6 concurrent positions, max 1 per sector bucket (diversification)
- Total risk exposure cap: 6%
- Daily kill-switch: 3% | Total drawdown kill-switch: 8% (enforced in risk_engine)
- EXTREME market regime (SPY) and news/earnings/sentiment filters block new entries

## Validation Status

- Backtested: YES — train 2010-2018 + OUT-OF-SAMPLE test 2019-2024 (incl. COVID crash)
- Paper traded: starting now
- Live traded: NO (unlock per CLAUDE.md: win rate >= 60% over 30d, DD < 8%, >= 10 trades)

### Backtest results (yfinance daily, next-open entry, 0.05%/side slippage)

Per-trade edge (26 symbols):
- TRAIN 2010-2018: 1830 trades, 68.5% win, PF 1.41
- TEST 2019-2024 (OOS): 1064 trades, **67.4% win, PF 1.29**, +0.23%/trade

Portfolio (OOS, deployed config — 6 positions, 1% risk):
- **CAGR ~7.4% | max drawdown ~7.1% | Sharpe ~0.89**

The edge holds out-of-sample. Win rate (67%) exceeds the 55-60% target; drawdown (7.1%)
is within the 8% mandate. Reproduce with `python -m backtest.meanrev_report`.

## REALISTIC OBJECTIVE (paper account)

Assuming the Alpaca paper default of **$100,000**:

- Expected average: **~0.6% / month (~7% / year)** — i.e. ~**+$600 in an average month**,
  ending the month around **$100,600**; ~$107,000 after a year.
- This is an AVERAGE: individual months vary widely. Good months can be +2-3%
  (~+$2,000-3,000); some months are flat or negative. Expect drawdowns up to ~7%.
- NOT a guarantee. Backtested edge ≠ future returns. The target is honest and
  risk-controlled, not a get-rich number — +10%/month is not achievable without
  leverage that would breach the 8% drawdown limit and risk the funded account.

To push returns higher one would raise position count or per-trade risk, but the
backtest shows that pushes max drawdown above 8% (prop-firm account-ending) — so the
deployed config deliberately caps risk at the mandate.
