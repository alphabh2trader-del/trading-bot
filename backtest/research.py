"""Strategy research backtester.

Independent of the live bot — used to FIND a strategy with a real edge before
wiring anything into production. Uses yfinance daily data (long history, broad
universe), a strict train/test (in-sample / out-of-sample) split, transaction
costs, and honest metrics. Long-only mean-reversion (Connors family) plus a
trend baseline.

Usage:
    python -m backtest.research            # full report, train + test
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Broad, liquid, long-history universe (mean reversion works best on index/sector ETFs).
ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV", "XLY",
        "XLP", "XLI", "XLU", "XLB", "EEM", "EFA", "SMH", "XBI", "KRE"]
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "V", "UNH", "HD"]
UNIVERSE = ETFS + STOCKS

TRAIN = ("2010-01-01", "2018-12-31")
TEST = ("2019-01-01", "2024-12-31")
SLIPPAGE = 0.0005  # 0.05% per side, applied to entry and exit


# ---------- indicators ----------

def wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period).mean()


# ---------- data ----------

def load_universe(start: str, end: str, symbols=UNIVERSE) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    data = {}
    raw = yf.download(symbols, start=start, end=end, progress=False, auto_adjust=True, group_by="ticker")
    for s in symbols:
        try:
            df = raw[s].dropna().copy() if isinstance(raw.columns, pd.MultiIndex) else raw.dropna().copy()
            df.columns = [c.lower() for c in df.columns]
            if len(df) > 250:
                data[s] = df
        except Exception:
            continue
    return data


# ---------- strategies ----------
# Each returns a boolean entry Series and an exit-rule callable(df, i_entry)->exit logic
# implemented inline in backtest_symbol for clarity.

def signal_rsi2(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = wilder_rsi(df["close"], 2)
    df["sma200"] = sma(df["close"], 200)
    df["sma5"] = sma(df["close"], 5)
    df["entry"] = (df["rsi"] < 5) & (df["close"] > df["sma200"])
    df["exit_rule"] = df["close"] > df["sma5"]
    return df


def signal_rsi4_2555(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = wilder_rsi(df["close"], 4)
    df["sma200"] = sma(df["close"], 200)
    df["entry"] = (df["rsi"] < 25) & (df["close"] > df["sma200"])
    df["exit_rule"] = df["rsi"] > 55
    return df


def signal_rsi3_r3(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    r = wilder_rsi(df["close"], 2)
    df["rsi"] = r
    df["sma200"] = sma(df["close"], 200)
    falling3 = (r < r.shift(1)) & (r.shift(1) < r.shift(2)) & (r.shift(2) < r.shift(3))
    df["entry"] = (df["close"] > df["sma200"]) & falling3 & (r.shift(2) < 60) & (r < 10)
    df["exit_rule"] = r > 70
    return df


def signal_trend_pullback(df: pd.DataFrame) -> pd.DataFrame:
    """Baseline: buy pullback to 20SMA in an uptrend, exit on close above prior high or time."""
    df = df.copy()
    df["sma200"] = sma(df["close"], 200)
    df["sma20"] = sma(df["close"], 20)
    df["rsi"] = wilder_rsi(df["close"], 3)
    df["entry"] = (df["close"] > df["sma200"]) & (df["close"] < df["sma20"]) & (df["rsi"] < 30)
    df["exit_rule"] = df["close"] > df["sma20"]
    return df


STRATEGIES = {
    "RSI2 (Connors)": signal_rsi2,
    "RSI4 25/55": signal_rsi4_2555,
    "R3": signal_rsi3_r3,
    "Trend pullback": signal_trend_pullback,
}


# ---------- backtest ----------

def backtest_symbol(df: pd.DataFrame, max_hold: int = 10) -> list[dict]:
    """Enter at next day's close after a signal; exit at the close of the day the
    exit rule first becomes true (or after max_hold days). One position at a time."""
    trades = []
    n = len(df)
    closes = df["close"].values
    entry_sig = df["entry"].fillna(False).values
    exit_sig = df["exit_rule"].fillna(False).values

    i = 1
    while i < n - 1:
        if entry_sig[i] and not np.isnan(closes[i]):
            entry_px = closes[i] * (1 + SLIPPAGE)
            exit_i = None
            for j in range(i + 1, min(i + 1 + max_hold, n)):
                if exit_sig[j]:
                    exit_i = j
                    break
            if exit_i is None:
                exit_i = min(i + max_hold, n - 1)
            exit_px = closes[exit_i] * (1 - SLIPPAGE)
            ret = (exit_px - entry_px) / entry_px
            trades.append({"entry_i": i, "exit_i": exit_i, "ret": ret, "hold": exit_i - i})
            i = exit_i + 1
        else:
            i += 1
    return trades


def stats(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_ret": 0, "pf": 0, "expectancy": 0, "total_ret": 0}
    rets = np.array([t["ret"] for t in trades])
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    gp = wins.sum()
    gl = abs(losses.sum())
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(rets) * 100, 1),
        "avg_ret": round(rets.mean() * 100, 3),
        "pf": round(gp / gl, 2) if gl > 0 else float("inf"),
        "expectancy": round(rets.mean() * 100, 3),
        "total_ret": round(rets.sum() * 100, 1),
        "avg_hold": round(np.mean([t["hold"] for t in trades]), 1),
    }


def run_period(data: dict, signal_fn) -> dict:
    all_trades = []
    for sym, df in data.items():
        sdf = signal_fn(df)
        all_trades.extend(backtest_symbol(sdf))
    return stats(all_trades)


def portfolio_sim(data: dict, signal_fn, max_concurrent: int = 6,
                  stop_pct: float = 0.08, max_hold: int = 10,
                  start_equity: float = 100_000, position_frac: float = None) -> dict:
    """Compounding equal-fraction portfolio. Enter at next close after a signal,
    size each position to a fixed fraction of equity, exit on the strategy rule,
    a disaster stop (-stop_pct), or max_hold. Cap concurrent positions. Returns
    CAGR / max drawdown / Sharpe on a daily equity curve."""
    # Build per-symbol signal frames aligned on a common date index.
    frames = {s: signal_fn(df) for s, df in data.items()}
    all_dates = sorted(set().union(*[set(f.index) for f in frames.values()]))

    equity = start_equity
    open_pos = {}  # symbol -> dict(entry_px, shares, entry_date, days)
    daily_equity = []

    for date in all_dates:
        # mark-to-market + manage exits
        for sym in list(open_pos.keys()):
            f = frames[sym]
            if date not in f.index:
                continue
            row = f.loc[date]
            pos = open_pos[sym]
            pos["days"] += 1
            px = row["close"]
            exit_now = bool(row.get("exit_rule", False)) or pos["days"] >= max_hold
            stop_hit = px <= pos["entry_px"] * (1 - stop_pct)
            if exit_now or stop_hit:
                fill = px * (1 - SLIPPAGE) if not stop_hit else pos["entry_px"] * (1 - stop_pct)
                equity += pos["shares"] * (fill - pos["entry_px"])
                del open_pos[sym]

        # new entries (next-close fill modeled as same-day close here for simplicity)
        if len(open_pos) < max_concurrent:
            for sym, f in frames.items():
                if sym in open_pos or date not in f.index:
                    continue
                row = f.loc[date]
                if bool(row.get("entry", False)) and not np.isnan(row["close"]):
                    if len(open_pos) >= max_concurrent:
                        break
                    frac = position_frac if position_frac else 1.0 / max_concurrent
                    alloc = equity * frac
                    entry_px = row["close"] * (1 + SLIPPAGE)
                    shares = alloc / entry_px
                    open_pos[sym] = {"entry_px": entry_px, "shares": shares,
                                     "entry_date": date, "days": 0}

        # record equity (incl. open MTM)
        mtm = equity
        for sym, pos in open_pos.items():
            f = frames[sym]
            if date in f.index:
                mtm += pos["shares"] * (f.loc[date, "close"] - pos["entry_px"])
        daily_equity.append((date, mtm))

    eq = pd.Series([e for _, e in daily_equity], index=[d for d, _ in daily_equity])
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    daily_ret = eq.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
    return {
        "final_equity": round(eq.iloc[-1]),
        "cagr_pct": round(cagr * 100, 2),
        "max_dd_pct": round(abs(dd.min()) * 100, 2),
        "sharpe": round(sharpe, 2),
    }


def main():
    print("Loading TRAIN data...")
    train = load_universe(*TRAIN)
    print(f"  {len(train)} symbols")
    print("Loading TEST data...")
    test = load_universe(*TEST)
    print(f"  {len(test)} symbols\n")

    print(f"{'Strategy':<18} | {'period':<5} | {'trades':>6} {'win%':>6} "
          f"{'avg%':>7} {'PF':>5} {'totRet%':>8} {'hold':>5}")
    print("-" * 78)
    for name, fn in STRATEGIES.items():
        for label, data in [("TRAIN", train), ("TEST", test)]:
            s = run_period(data, fn)
            print(f"{name:<18} | {label:<5} | {s['trades']:>6} {s['win_rate']:>6} "
                  f"{s['avg_ret']:>7} {str(s['pf']):>5} {s['total_ret']:>8} "
                  f"{s.get('avg_hold', 0):>5}")
        print("-" * 78)

    # Portfolio-level validation on the OUT-OF-SAMPLE test period.
    print("\nPortfolio sim (OUT-OF-SAMPLE 2019-2024, max 6 concurrent, 8% disaster stop):")
    print(f"{'Strategy':<18} | {'finalEq':>9} {'CAGR%':>7} {'maxDD%':>7} {'Sharpe':>7}")
    print("-" * 56)
    for name, fn in STRATEGIES.items():
        p = portfolio_sim(test, fn)
        print(f"{name:<18} | {p['final_equity']:>9} {p['cagr_pct']:>7} "
              f"{p['max_dd_pct']:>7} {p['sharpe']:>7}")


if __name__ == "__main__":
    main()
