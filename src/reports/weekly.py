"""
Weekly Review Report Generator.
Reads trades.csv and produces a formatted weekly review stored in memory/reports/.
Includes: win rate, drawdown, profit factor, broker fees (paper = $0), trade log summary.
Auto-promotes suggestion when win rate >= 60% over a full month.
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"
REPORTS_DIR = MEMORY_DIR / "reports"
TRADES_FILE = MEMORY_DIR / "trades.csv"
CONFIG_FILE = MEMORY_DIR / "config.json"

BROKER_FEE_PER_TRADE = 0.0  # paper trading = $0


def _load_trades_this_week() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    week_ago = datetime.utcnow() - timedelta(days=7)
    trades = []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("exit_timestamp") or row.get("timestamp")
            if not ts:
                continue
            try:
                trade_date = datetime.fromisoformat(ts)
                if trade_date >= week_ago:
                    trades.append(row)
            except ValueError:
                continue
    return trades


def _load_all_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _compute_stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("status") == "closed"]
    if not closed:
        return {
            "total": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "total_pnl_pct": 0.0,
            "profit_factor": 0.0, "max_drawdown_pct": 0.0,
            "total_fees": 0.0,
        }

    wins = [t for t in closed if float(t.get("pnl_pct", 0)) > 0]
    losses = [t for t in closed if float(t.get("pnl_pct", 0)) <= 0]

    gross_profit = sum(float(t.get("pnl_usd", 0)) for t in wins)
    gross_loss = abs(sum(float(t.get("pnl_usd", 0)) for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    total_pnl_pct = sum(float(t.get("pnl_pct", 0)) for t in closed)

    # Simplified drawdown: largest single losing streak
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in closed:
        running += float(t.get("pnl_pct", 0))
        peak = max(peak, running)
        dd = peak - running
        max_dd = max(max_dd, dd)

    total_fees = len(closed) * BROKER_FEE_PER_TRADE

    return {
        "total": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(closed) * 100,
        "total_pnl_pct": total_pnl_pct,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "total_fees": total_fees,
    }


def _check_live_readiness(all_trades: list[dict]) -> tuple[bool, str]:
    month_ago = datetime.utcnow() - timedelta(days=30)
    month_trades = []
    for t in all_trades:
        if t.get("status") != "closed":
            continue
        ts = t.get("exit_timestamp") or t.get("timestamp")
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts) >= month_ago:
                month_trades.append(t)
        except ValueError:
            continue

    if len(month_trades) < 10:
        return False, f"Not enough trades in the last 30 days ({len(month_trades)}/10 minimum)."

    wins = sum(1 for t in month_trades if float(t.get("pnl_pct", 0)) > 0)
    win_rate = wins / len(month_trades) * 100
    if win_rate >= 60.0:
        return True, f"WIN RATE {win_rate:.1f}% over 30 days — READY FOR LIVE TRADING."
    return False, f"Win rate {win_rate:.1f}% (need 60%). Keep paper trading."


def generate_weekly_report() -> str:
    now = datetime.utcnow()
    week_label = now.strftime("Week of %Y-%m-%d")

    weekly_trades = _load_trades_this_week()
    all_trades = _load_all_trades()

    weekly_stats = _compute_stats(weekly_trades)
    all_time_stats = _compute_stats(all_trades)
    live_ready, live_msg = _check_live_readiness(all_trades)

    report_lines = [
        f"# WEEKLY REVIEW REPORT",
        f"## {week_label}",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
        f"## THIS WEEK",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Trades | {weekly_stats['total']} |",
        f"| Wins | {weekly_stats['wins']} |",
        f"| Losses | {weekly_stats['losses']} |",
        f"| Win Rate | {weekly_stats['win_rate']:.1f}% |",
        f"| Total P&L | {weekly_stats['total_pnl_pct']:+.2f}% |",
        f"| Profit Factor | {weekly_stats['profit_factor']:.2f} |",
        f"| Max Drawdown | {weekly_stats['max_drawdown_pct']:.2f}% |",
        f"| Broker Fees | ${weekly_stats['total_fees']:.2f} (paper = $0) |",
        f"",
        f"---",
        f"",
        f"## ALL-TIME",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Trades | {all_time_stats['total']} |",
        f"| Win Rate | {all_time_stats['win_rate']:.1f}% |",
        f"| Total P&L | {all_time_stats['total_pnl_pct']:+.2f}% |",
        f"| Profit Factor | {all_time_stats['profit_factor']:.2f} |",
        f"| Max Drawdown | {all_time_stats['max_drawdown_pct']:.2f}% |",
        f"| Total Fees Paid | ${all_time_stats['total_fees']:.2f} |",
        f"",
        f"---",
        f"",
        f"## LIVE TRADING READINESS",
        f"",
        f"{'READY' if live_ready else 'NOT READY'}: {live_msg}",
        f"",
        f"---",
        f"",
        f"## TRADE LOG (This Week)",
        f"",
    ]

    if weekly_trades:
        report_lines.append("| Symbol | Dir | Entry | Exit | P&L% | P&L$ | Fee |")
        report_lines.append("|--------|-----|-------|------|------|------|-----|")
        for t in weekly_trades:
            if t.get("status") != "closed":
                continue
            report_lines.append(
                f"| {t.get('symbol','')} | {t.get('direction','')} "
                f"| {t.get('entry_price','')} | {t.get('exit_price','')} "
                f"| {float(t.get('pnl_pct',0)):+.2f}% "
                f"| ${float(t.get('pnl_usd',0)):+.2f} "
                f"| $0.00 |"
            )
    else:
        report_lines.append("No closed trades this week.")

    report = "\n".join(report_lines)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_filename = REPORTS_DIR / f"report_{now.strftime('%Y-%m-%d')}.md"
    report_filename.write_text(report, encoding="utf-8")

    return report
