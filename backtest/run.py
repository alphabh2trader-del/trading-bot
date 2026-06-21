"""Backtest runner — fetches historical bars from Alpaca for the watchlist,
replays the strategy, and writes a report to memory/backtests/.

Usage:
    python -m backtest.run                 # default watchlist, ~2y D1 / 1y H4
    python -m backtest.run --symbols AAPL MSFT --days 540
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import config
from data.market_data import fetch_bars
from backtest.engine import simulate_symbol, compute_stats

REPORTS_DIR = Path(__file__).parent.parent / "memory" / "backtests"


def run(symbols: list[str], days: int, threshold: int) -> dict:
    all_trades: list[dict] = []
    per_symbol: dict[str, dict] = {}

    for symbol in symbols:
        try:
            d1 = fetch_bars(symbol, "1Day", lookback_days=days * 2)
            h4 = fetch_bars(symbol, "4Hour", lookback_days=days)
        except Exception as e:
            print(f"  {symbol}: data fetch failed — {e}")
            continue

        trades = simulate_symbol(symbol, d1, h4, regime="NORMAL", score_threshold=threshold)
        per_symbol[symbol] = compute_stats(trades)
        all_trades.extend(trades)
        print(f"  {symbol}: {per_symbol[symbol]['trades']} trades, "
              f"win rate {per_symbol[symbol]['win_rate']}%")

    overall = compute_stats(all_trades)
    _write_report(symbols, days, threshold, overall, per_symbol, all_trades)
    return overall


def _write_report(symbols, days, threshold, overall, per_symbol, trades) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"backtest_{stamp}.md"

    lines = [
        f"# Backtest Report — {stamp}",
        "",
        f"- Symbols: {', '.join(symbols)}",
        f"- H4 lookback: {days} days (D1: {days * 2})",
        f"- Score threshold: {threshold}",
        f"- Strategy: {config_value('strategy')}",
        "",
        "## Overall",
        "",
        f"- Trades: {overall['trades']}",
        f"- Win rate: {overall['win_rate']}%",
        f"- Profit factor: {overall['profit_factor']}",
        f"- Expectancy: {overall['expectancy_r']} R/trade",
        f"- Total: {overall['total_r']} R",
        f"- Max drawdown: {overall['max_drawdown_r']} R",
        "",
        "## Per symbol",
        "",
        "| Symbol | Trades | Win % | PF | Expectancy (R) |",
        "|--------|-------:|------:|---:|---------------:|",
    ]
    for sym, st in per_symbol.items():
        lines.append(f"| {sym} | {st['trades']} | {st['win_rate']} | "
                     f"{st['profit_factor']} | {st['expectancy_r']} |")

    lines += ["", "## Notes", "",
              "Results are in R-multiples (reward/risk). Wins target +2R, losses -1R.",
              "This measures the raw setup edge; it excludes slippage, fees, and the",
              "news/earnings/sentiment filters applied live."]

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {path}")


def config_value(key: str) -> str:
    try:
        import json
        cfg = json.loads((Path(__file__).parent.parent / "memory" / "config.json").read_text())
        return cfg.get("system", {}).get(key, "unknown")
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy backtest")
    parser.add_argument("--symbols", nargs="+", default=config.BASE_WATCHLIST)
    parser.add_argument("--days", type=int, default=365, help="H4 lookback in days")
    parser.add_argument("--threshold", type=int, default=config.SCORE_THRESHOLD)
    args = parser.parse_args()

    print(f"Backtesting {len(args.symbols)} symbols over {args.days}d "
          f"(threshold {args.threshold})...")
    overall = run(args.symbols, args.days, args.threshold)
    print(f"\nOVERALL: {overall['trades']} trades | win rate {overall['win_rate']}% | "
          f"PF {overall['profit_factor']} | expectancy {overall['expectancy_r']}R")


if __name__ == "__main__":
    main()
