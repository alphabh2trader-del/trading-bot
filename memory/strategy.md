# CURRENT ACTIVE STRATEGY — v4.0

## Version

- ID: dual_swing+trend_v1
- Created: 2026-06-21
- Status: ACTIVE (paper trading)
- Replaces: trend_timing_v1 (now the TREND SLEEVE — still running, at 30% capital)

## Why two strategies at once

The single monthly trend strategy is robust but slow (~0.84%/mo) and only acts once a
month. The user wants more activity and more profit "on the spot." So the bot now runs
TWO uncorrelated sleeves on one Alpaca account, on DISJOINT universes, simultaneously:

| Sleeve | Capital | Universe | Cadence | Edge |
|--------|---------|----------|---------|------|
| **Swing** | 70% | 16 liquid large-cap stocks | daily | D1-trend / H4-pullback, 1% risk/trade |
| **Trend** | 30% | 18 ETFs (eq + TLT + GLD) | monthly | Faber GTAA, cost-robust core |

They never collide: the trend rebalance is scoped to the ETF universe (and 30% of
capital); swing trades only the stock watchlist. Disjoint symbol sets = no interference.

## SWING SLEEVE rules (daily)

- Trend filter: D1 close > EMA200 → long bias; < EMA200 → short bias.
- Pullback: H4 price near EMA50 + RSI(14) in zone (long 38-58 rising / short 42-62 falling).
- Structure + MACD + volume confirmation feed the 0-100 score; entry above threshold.
- Stop: structure low/high with an ATR(14)×1.5 volatility buffer. Target: 2R.
- Sizing: 1% risk of full equity per trade (shrinks on losing days — see risk model).

## TREND SLEEVE rules (monthly, unchanged logic, now 30% sleeve)

- For each ETF: HOLD if monthly close > 10-month SMA; else CASH. Equal weight × exposure.
- Rebalanced once per calendar month, scoped to the ETF universe and 30% of equity.

## RISK MODEL (rewritten 2026-06-21 — user decisions)

- **No daily halt.** A losing day does NOT stop trading; per-trade size shrinks down a
  ladder instead: <1% loss → 1.0×, <2% → 0.66×, <3% → 0.5×, ≥3% → 0.33× (never 0).
- **No fixed position-count cap.** New swing entries are gated by an aggregate
  OPEN-RISK budget (6% of equity); good setups are taken until the budget is spent.
  A 20-position sanity ceiling guards against a runaway day.
- **Only hard stop = account catastrophe drawdown** (25% paper / 8% funded). This is the
  one thing that locks the system — it protects a funded prop account from termination.
- Per-sector cap = 2 open positions (was 1) so clustered good setups aren't all dropped.

## VALIDATION — net of fees

**Swing sleeve** (`python -m backtest.swing`, daily-bar proxy, 2021-2026, round-trip
cost 0.10%, account-level 1%/6% sim):
- Trades 167 | Win rate 46.1% | Profit factor 1.22 | Avg R 0.14
- Return ~0.27%/month (~3.2%/yr) | Max DD 10.4%
- The edge SURVIVES fees (PF > 1, positive avg R) but is THIN. A daily proxy understates
  an H4-entry edge, so live H4 should do somewhat better — but do NOT expect 5%/month.

**Trend sleeve** (`python -m backtest.momentum`, ETF-only, 2007-2025, 0.30% cost):
- CAGR ~10.5% / maxDD ~24% / Sharpe 0.79, positive in every sub-period incl. 2008 & 2022.
- On the 30% allocation it contributes ~3.1%/yr to the blended account.

**Blended realistic expectation: ~0.5-1.0% / month (~6-10%/yr), NOT 5%/month.**
5%/month consistently is not achievable under capital-preservation constraints without
large leverage (and the matching drawdown). The honest target stays low single-digit
monthly, lumpy month to month.

## Validation Status

- Backtested: YES — both sleeves, net of fees, multi-year.
- Paper traded: starting now (dual sleeve).
- Live traded: NO. For a funded account set risk.max_total_drawdown_pct = 8 and
  trend.base_exposure = 0.33 (the trend sleeve's 24% DD exceeds an 8% funded limit).
