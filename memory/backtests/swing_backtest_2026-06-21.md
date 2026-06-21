# Swing-Sleeve Backtest — dual_swing+trend_v1 — 2026-06-21

Daily-bar proxy of the live D1-trend / H4-pullback system (free intraday
history is too short to backtest H4 directly). Account-level sim: 1% risk/trade,
6% open-risk budget, round-trip cost 0.10% (fees + slippage).

- Universe: 16 liquid large-caps (config.SWING_WATCHLIST)
- Period: 2021-01-01 -> 2026-06-01 (5.4 yrs)
- Stop: ATR(14) x 1.5 | Target: 2.0R | Max hold: 12 days

## Results (net of fees)

- Trades: 167
- Win rate: 46.1%
- Profit factor: 1.22
- Avg R: 0.14
- **Return: 0.27%/month  (3.24%/yr)**
- Max drawdown: 10.4%
- Final equity (from 1.0): 1.188

Note: a daily-bar approximation tends to UNDERSTATE an intraday-entry edge
(coarser pullback timing, wider effective stops). Reproduce: `python -m backtest.swing`.