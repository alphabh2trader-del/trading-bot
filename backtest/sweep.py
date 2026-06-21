"""Parameter sweep — fetches each symbol's bars ONCE, then replays the strategy
across a grid of trade-geometry / filter settings to find robust improvements.

Usage:
    python -m backtest.sweep                       # default watchlist
    python -m backtest.sweep --symbols AAPL MSFT --days 540

Only adopt changes that improve expectancy *robustly* (consistent direction,
meaningful size) — the sample is small, so beware of overfitting.
"""
import argparse

import config
from data.market_data import fetch_bars
from backtest.engine import simulate_symbol, compute_stats

# (tp_r_mult, require_volume_confirm) grid, evaluated at the score threshold below.
TP_GRID = [2.0, 2.5, 3.0]
VOL_GRID = [False, True]


def _load_bars(symbols, days):
    bars = {}
    for s in symbols:
        try:
            bars[s] = (
                fetch_bars(s, "1Day", lookback_days=days * 2),
                fetch_bars(s, "4Hour", lookback_days=days),
            )
        except Exception as e:
            print(f"  skip {s}: {e}")
    return bars


def _run_combo(bars, threshold):
    trades = []
    for sym, (d1, h4) in bars.items():
        trades.extend(simulate_symbol(sym, d1, h4, score_threshold=threshold))
    return compute_stats(trades)


def main():
    parser = argparse.ArgumentParser(description="Strategy parameter sweep")
    parser.add_argument("--symbols", nargs="+", default=config.BASE_WATCHLIST)
    parser.add_argument("--days", type=int, default=540)
    parser.add_argument("--threshold", type=int, default=config.SCORE_THRESHOLD)
    args = parser.parse_args()

    print(f"Loading bars for {len(args.symbols)} symbols (once)...")
    bars = _load_bars(args.symbols, args.days)

    print(f"\nGrid sweep @ threshold {args.threshold} "
          f"({len(TP_GRID) * len(VOL_GRID)} combos)\n")
    print(f"{'TP(R)':>6} {'reqVol':>7} {'trades':>7} {'win%':>6} "
          f"{'PF':>6} {'exp(R)':>8} {'totR':>7} {'maxDD':>7}")
    print("-" * 60)

    results = []
    for tp in TP_GRID:
        for req_vol in VOL_GRID:
            config.TP_R_MULT = tp
            config.REQUIRE_VOLUME_CONFIRM = req_vol
            config.MIN_RR = min(1.8, tp)  # floor must not exceed the RR being tested
            stats = _run_combo(bars, args.threshold)
            results.append((tp, req_vol, stats))
            print(f"{tp:>6.1f} {str(req_vol):>7} {stats['trades']:>7} "
                  f"{stats['win_rate']:>6.1f} {str(stats['profit_factor']):>6} "
                  f"{stats['expectancy_r']:>8.3f} {stats['total_r']:>7.2f} "
                  f"{stats['max_drawdown_r']:>7.2f}")

    best = max(results, key=lambda r: r[2]["expectancy_r"])
    print("\nBest by expectancy:",
          f"TP={best[0]}R reqVol={best[1]} -> exp {best[2]['expectancy_r']}R "
          f"(win {best[2]['win_rate']}%, PF {best[2]['profit_factor']}, n={best[2]['trades']})")


if __name__ == "__main__":
    main()
