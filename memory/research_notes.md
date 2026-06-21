# RESEARCH NOTES — Strategy improvement ideas

> Notes taken during an overnight research pass (2026-06-21). Nothing here is auto-deployed.
> These are candidate improvements to discuss before changing the live `trend_timing_v1`.
> The active strategy was chosen for ROBUSTNESS (survived cost + slippage + survivorship +
> every regime 2007-2025). Any change below must clear the SAME bar via `backtest/verify.py`
> or it does not ship. "Better in backtest" is not enough — it must be better *robustly*.

---

## TL;DR — what is worth testing, ranked

1. **Volatility targeting (exposure overlay)** — STRONGEST evidence. Scale total exposure
   to a constant ~10% annualised vol instead of a fixed 1.0×. Literature: Sharpe +~40%,
   max DD cut from ~40% to ~25% on trend systems. Fits our "exposure is the single risk
   dial" framing perfectly and is the cleanest way to honour the 8% drawdown mandate on a
   funded account WITHOUT amputating returns. **Top candidate.**
2. **Multi-lookback signal (average of several SMAs / momentum windows)** — robustness, not
   return. Replace the single 10-month SMA with a vote across e.g. {6, 8, 10, 12}-month SMAs
   (or 1/3/6/12-month momentum average à la Faber RS). Faber himself says 10 months is "just
   representative" — averaging removes the single-parameter fragility and cuts whipsaw.
3. **Defensive-asset ranking (top-N relative strength)** — possible return boost, but my own
   earlier test showed naive momentum *rotation* fails 2008-2010. Only worth it combined with
   the absolute SMA filter (Faber RS-style), never standalone.
4. **NOT recommended: chasing the best single parameter set** — every source warns this is
   overfitting. Look for clusters of good params, not the peak.

---

## Detailed findings

### 1. Volatility targeting / scaling  ⭐ best risk-adjusted improvement
- Concretum & QuantPedia: a trend system scaled to a 10% annual vol target reached Sharpe
  ~0.87 (vs ours ~0.79) and cut max DD materially (one study: 40% → 25%).
- Mechanism: each rebalance, estimate portfolio vol over a trailing window (e.g. 60-90d) and
  set `exposure = vol_target / realised_vol` (capped, e.g. 0.3×–1.5×). In calm uptrends you
  lever up modestly; in turbulent markets you automatically de-risk.
- WHY it fits us: we already proved Sharpe is ~constant across exposure, so a *static* dial
  only slides the line. Vol targeting makes the dial **dynamic and counter-cyclical** — that
  is the one thing that can raise Sharpe rather than just rescale it.
- CAVEAT (Twoquants "bittersweet truth"): vol targeting can underperform in slow grinding
  bulls and adds turnover (→ cost). Must be stress-tested with our cost model before shipping.
- Position-sizing comparison (Concretum): Volatility Targeting (IRR 11.5%, maxDD ~26%) and
  Volatility Parity (IRR 12.8%) both beat naive; "Parity + Pyramiding" hits 20% IRR but 49%
  DD — too hot for a prop mandate. **Pick plain Volatility Targeting.**

### 2. Multi-lookback / parameter averaging (whipsaw + overfitting fix)
- CXO/Zakamulin: broad parameter stability across MA lengths; choosing the single best is
  overfitting → average a cluster.
- Concrete: hold an ETF if its monthly close is above the *average* of its {6,8,10,12}-month
  SMAs, or require ≥3 of 4 to agree. Smoother, fewer false flips, almost no extra cost.
- Faber Relative Strength variant ranks assets by mean of 1/3/6/12-month total return — same
  idea applied to ranking.

### 3. Dual / accelerating momentum (Antonacci GEM, EP's ADM)
- GEM: ~7.8% CAGR, ~33% maxDD in some windows — concentration (1 ETF) raises DD; not obviously
  better than our diversified ~10.5%/24%.
- Accelerating Dual Momentum: momentum score = mean(1m,3m,6m) return, monthly, single ETF.
  ~10% CAGR, ~19% DD, ~1-1.5 trades/yr. Lower DD is attractive BUT single-ETF concentration
  is fragile and whipsaws on fast reversals (late 2018, spring 2020). Diversification (what we
  have) is the safer prop choice. Borrow the *accelerating score* idea (weight recent months)
  into our SMA filter rather than adopting wholesale.
- VAA (Vigilant Asset Allocation): aggressive crash protection, often >50% in cash — lower DD
  but big tracking error / can sit out rallies. Defensive; revisit only if drawdown becomes
  the binding constraint on a funded account.

### 4. Reality check on Faber GTAA (our base)
- Honest negative: the real GTAA *ETF* was shuttered; the public model did ~5.3%/yr from 2015
  (late into rallies, late out of downturns). Our backtest's ~10.5% leans on 2019-21/2025.
  → This is exactly why (1) vol targeting and (2) multi-lookback matter: they attack the two
  known GTAA weaknesses (static sizing + single-param lag). Worth doing, carefully.

### 5. VIX mean-reversion overlay (secondary, opportunistic)
- Large VIX spikes (≥5pt) → SPY +5% over next 20d (5× baseline), but only as a *long-only*
  add-on when SPY 50d>200d. Mixed evidence; underperforms a basic RSI MR system. Could be a
  small satellite sleeve later, NOT a core change.

---

## Proposed experiment plan (for tomorrow, gated on backtest)

A. Implement vol-targeting exposure in `backtest/momentum.py` (research only) → compare
   Sharpe / maxDD / per-period vs the static 1.0× baseline, WITH the cost model.
B. Implement multi-lookback SMA vote in the same harness → compare whipsaw count + per-period.
C. Only if EITHER clears the full `verify.py` bar (cost-robust, survivorship-free, profitable
   every sub-period) do we wire it into the live `strategy/trend_timing.py`.
D. If both pass, prefer combining: multi-lookback signal + vol-targeted sizing.

## What I changed tonight (separate from the above research)
- Fixed the self-improvement loop so it actually controls the ACTIVE strategy (it was tuning
  dead swing/meanrev parameters). See improvements.md entry dated 2026-06-21. The loop now
  manages `trend.exposure` for capital preservation and re-validates `trend.sma_months`
  robustness monthly, with a Telegram alert on every change. The research ideas above are NOT
  yet implemented — they need the backtest gate first.

## Sources
- Faber GTAA & critiques: mebfaber.com/timing-model, quantifiedstrategies.com/meb-faber-momentum-trend-following-strategy, cxoadvisory.com, allocatesmartly.com (Zakamulin)
- Vol targeting: concretumgroup.com/position-sizing-in-trend-following, quantpedia.com/an-introduction-to-volatility-targeting, twoquants.com/bitterweet-truth-of-volatility-targeting
- Dual momentum: optimalmomentum.com, turingtrader.com/portfolios/ep-accelerating-dual-momentum, quantifiedstrategies.com/dual-momentum-trading-strategy
- VAA: papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624
- VIX MR: quantifiedstrategies.com/using-vix-to-trade-spy-and-sp-500
