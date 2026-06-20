import csv
from datetime import datetime, timedelta, date
from pathlib import Path

import config
from reporting.telegram import send_chunked

MEMORY_DIR = Path(__file__).parent.parent / "memory"
TRADES_FILE = MEMORY_DIR / "trades.csv"
REPORTS_DIR = MEMORY_DIR / "reports"


def generate_and_send() -> str:
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    all_trades = _load_closed_trades()
    weekly = [t for t in all_trades if _parse_ts(t) >= week_ago]
    monthly = [t for t in all_trades if _parse_ts(t) >= month_ago]

    w = _stats(weekly)
    m = _stats(monthly)
    live_ready = m["total"] >= 10 and m["win_rate"] >= 60.0

    lines = [
        f"# WEEKLY REVIEW — {now.strftime('Week of %Y-%m-%d')}",
        "",
        "## THIS WEEK",
        f"Trades: {w['total']} | Wins: {w['wins']} | Losses: {w['losses']}",
        f"Win rate: {w['win_rate']:.1f}%",
        f"Gross P&L: {w['gross']:+.2f} | Fees: ${w['fees']:.4f} | Net: ${w['net']:+.2f}",
        f"Profit factor: {w['pf']:.2f} | Max drawdown: {w['max_dd']:.2f}%",
        "",
        "## ALL-TIME (30 DAYS)",
        f"Trades: {m['total']} | Win rate: {m['win_rate']:.1f}%",
        f"Net P&L: ${m['net']:+.2f} | Total fees: ${m['fees']:.4f}",
        "",
        "## LIVE READINESS",
        ("✅ READY — Win rate ≥ 60% over 30 days. Consider going live." if live_ready
         else f"❌ NOT READY — Win rate {m['win_rate']:.1f}% (need 60%, min 10 trades)."),
        "",
        "## TRADE LOG (THIS WEEK)",
    ]

    if weekly:
        lines.append("Symbol | Dir | Net P&L | Fees | R:R")
        for t in weekly:
            lines.append(
                f"{t['symbol']} | {t['direction'].upper()} | "
                f"${float(t.get('net_pnl_usd') or 0):+.2f} | "
                f"${float(t.get('fees_usd') or 0):.4f} | "
                f"{t.get('rr', '?')}"
            )
    else:
        lines.append("No closed trades this week.")

    report = "\n".join(lines)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"report_{now.strftime('%Y-%m-%d')}.md").write_text(report, encoding="utf-8")
    send_chunked(report)
    return report


def _load_closed_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "closed"]


def _parse_ts(t: dict) -> datetime:
    ts = t.get("exit_timestamp") or t.get("timestamp") or ""
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min


def _stats(trades: list[dict]) -> dict:
    if not trades:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "gross": 0.0, "fees": 0.0, "net": 0.0, "pf": 0.0, "max_dd": 0.0}
    wins = [t for t in trades if float(t.get("pnl_usd") or 0) > 0]
    losses = [t for t in trades if float(t.get("pnl_usd") or 0) <= 0]
    gross = sum(float(t.get("pnl_usd") or 0) for t in trades)
    fees = sum(float(t.get("fees_usd") or 0) for t in trades)
    gp = sum(float(t.get("pnl_usd") or 0) for t in wins)
    gl = abs(sum(float(t.get("pnl_usd") or 0) for t in losses))
    pf = gp / gl if gl > 0 else float("inf")

    running = peak = max_dd = 0.0
    for t in trades:
        running += float(t.get("pnl_pct") or 0)
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    return {
        "total": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100,
        "gross": gross, "fees": fees, "net": gross - fees,
        "pf": pf, "max_dd": max_dd,
    }
