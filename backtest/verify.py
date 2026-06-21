"""Robustness verification for the active strategy.

Answers the hard questions before trusting the edge:
  1. COSTS      — does it survive higher fees + slippage?
  2. SURVIVORSHIP — does it hold on ETFs only (no hand-picked winning stocks)?
  3. OVERFITTING — is the edge stable across nearby parameters?
  4. PERIODS    — is it consistent across regimes (2008 GFC ... 2025)?

Costs are modeled as a round-trip drag: `cost_side` is charged on BOTH the entry
and the exit fill (so a value of 0.0015 = 0.15%/side = 0.30% round trip), covering
commission + bid/ask spread + slippage in one conservative number.

Usage:  python -m backtest.verify
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from strategy.indicators import wilder_rsi

ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV",
        "XLY", "XLP", "XLI", "XLU", "XLB", "SMH", "XBI", "KRE"]
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "V", "UNH", "HD"]


def load(symbols, start, end):
    import yfinance as yf
    raw = yf.download(symbols, start=start, end=end, progress=False,
                      auto_adjust=True, group_by="ticker")
    data = {}
    for s in symbols:
        try:
            df = raw[s].dropna().copy()
            df.columns = [c.lower() for c in df.columns]
            if len(df) > 250:
                data[s] = df
        except Exception:
            pass
    return data


def trades_for(df, rsi_thr=10, exit_sma=5, stop_pct=0.08, cost_side=0.0005,
               max_hold=10, trend_sma=200):
    close = df["close"]
    rsi = wilder_rsi(close, 2)
    sma_t = close.rolling(trend_sma).mean()
    sma_e = close.rolling(exit_sma).mean()
    entry = ((rsi < rsi_thr) & (close > sma_t)).fillna(False).values
    exitr = (close > sma_e).fillna(False).values
    o, l, c = df["open"].values, df["low"].values, df["close"].values
    yrs = df.index.year.values
    n = len(df)
    tr, i = [], 1
    while i < n - 2:
        if entry[i]:
            ep = o[i + 1] * (1 + cost_side)          # entry fill + cost
            xp, j = None, min(i + max_hold, n - 1)
            for k in range(i + 1, min(i + 1 + max_hold, n)):
                if l[k] <= ep * (1 - stop_pct):
                    xp, j = ep * (1 - stop_pct) * (1 - cost_side), k
                    break
                if exitr[k]:
                    xp, j = c[k] * (1 - cost_side), k
                    break
            if xp is None:
                xp = c[j] * (1 - cost_side)
            tr.append({"ret": (xp - ep) / ep, "year": int(yrs[i + 1])})
            i = j + 1
        else:
            i += 1
    return tr


def st(tr):
    if not tr:
        return dict(n=0, win=0, pf=0, avg=0, tot=0)
    r = np.array([t["ret"] for t in tr])
    w, los = r[r > 0], r[r <= 0]
    pf = w.sum() / abs(los.sum()) if los.sum() != 0 else float("inf")
    return dict(n=len(r), win=round((r > 0).mean() * 100, 1), pf=round(pf, 2),
                avg=round(r.mean() * 100, 3), tot=round(r.sum() * 100, 1))


def agg(data, **kw):
    tr = []
    for _, df in data.items():
        tr.extend(trades_for(df, **kw))
    return tr


def main():
    print("Loading 2007-2026 history (once)...")
    full = load(ETFS + STOCKS, "2007-01-01", "2026-01-01")
    etf_only = {k: v for k, v in full.items() if k in ETFS}
    print(f"  {len(full)} symbols ({len(etf_only)} ETFs)\n")

    print("=" * 64)
    print("1) COST SENSITIVITY  (full universe, 2007-2025)")
    print(f"   {'cost/side':>9} {'round-trip':>10} {'trades':>7} {'win%':>6} {'PF':>5} {'avg%':>7} {'tot%':>8}")
    for cs in [0.0005, 0.0010, 0.0015, 0.0020]:
        s = st(agg(full, cost_side=cs))
        print(f"   {cs*100:>8.2f}% {cs*200:>9.2f}% {s['n']:>7} {s['win']:>6} "
              f"{s['pf']:>5} {s['avg']:>7} {s['tot']:>8}")

    print("\n" + "=" * 64)
    print("2) SURVIVORSHIP  (ETFs only — diversified baskets, no hand-picked stocks)")
    print(f"   {'universe':>12} {'cost/side':>9} {'trades':>7} {'win%':>6} {'PF':>5} {'avg%':>7}")
    for name, d in [("ETF-only", etf_only), ("full", full)]:
        for cs in [0.0005, 0.0015]:
            s = st(agg(d, cost_side=cs))
            print(f"   {name:>12} {cs*100:>8.2f}% {s['n']:>7} {s['win']:>6} {s['pf']:>5} {s['avg']:>7}")

    print("\n" + "=" * 64)
    print("3) PERIOD CONSISTENCY  (ETF-only, 0.10%/side cost — conservative)")
    print(f"   {'period':>12} {'trades':>7} {'win%':>6} {'PF':>5} {'avg%':>7} {'tot%':>8}")
    tr_all = agg(etf_only, cost_side=0.0010)
    periods = [("2008-2010", 2008, 2010), ("2011-2015", 2011, 2015),
               ("2016-2018", 2016, 2018), ("2019-2021", 2019, 2021),
               ("2022-2024", 2022, 2024), ("2025+", 2025, 2030)]
    for label, y0, y1 in periods:
        sub = [t for t in tr_all if y0 <= t["year"] <= y1]
        s = st(sub)
        print(f"   {label:>12} {s['n']:>7} {s['win']:>6} {s['pf']:>5} {s['avg']:>7} {s['tot']:>8}")

    print("\n" + "=" * 64)
    print("4) PARAMETER ROBUSTNESS  (ETF-only, 0.10%/side cost)")
    print(f"   {'RSI<':>5} {'exitSMA':>7} {'stop%':>6} {'trades':>7} {'win%':>6} {'PF':>5} {'avg%':>7}")
    for thr in [8, 10, 12]:
        for ex in [4, 5, 6]:
            for stop in [0.06, 0.08, 0.10]:
                s = st(agg(etf_only, rsi_thr=thr, exit_sma=ex, stop_pct=stop, cost_side=0.0010))
                print(f"   {thr:>5} {ex:>7} {stop*100:>5.0f}% {s['n']:>7} {s['win']:>6} {s['pf']:>5} {s['avg']:>7}")


if __name__ == "__main__":
    main()
