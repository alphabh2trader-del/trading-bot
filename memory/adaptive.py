"""Adaptive learning — runs after EOD review and weekly routine.

Reads closed trade history, computes rolling performance stats, and adjusts
strategy parameters in memory/config.json if stats cross defined thresholds.
All changes are logged to improvements.md and session_snapshots.jsonl.

Called only between trading sessions — never during market hours.
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).parent
TRADES_FILE = MEMORY_DIR / "trades.csv"
SNAPSHOTS_FILE = MEMORY_DIR / "session_snapshots.jsonl"
IMPROVEMENTS_FILE = MEMORY_DIR / "improvements.md"
CONFIG_FILE = MEMORY_DIR / "config.json"

# Hard limits — adaptive cannot cross these regardless of stats
_SCORE_MIN = 60
_SCORE_MAX = 80
_RR_FLOOR = 1.5
_RR_CEILING = 2.0


def _load_closed_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "closed"]


def _compute_stats(trades: list[dict], window: int) -> dict:
    recent = trades[-window:] if len(trades) >= window else trades
    if not recent:
        return {"count": 0}
    wins = [t for t in recent if float(t.get("net_pnl_usd") or 0) > 0]
    rrs = []
    for t in recent:
        entry = float(t.get("entry_price") or 0)
        sl = float(t.get("stop_loss") or 0)
        tp = float(t.get("take_profit") or 0)
        if entry > 0 and sl > 0 and tp > 0:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            if risk > 0:
                rrs.append(reward / risk)
    return {
        "count": len(recent),
        "win_rate": len(wins) / len(recent),
        "avg_rr": round(sum(rrs) / len(rrs), 3) if rrs else 0.0,
    }


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if "adaptive" not in cfg:
        cfg["adaptive"] = {
            "score_threshold": 65,
            "midday_score_threshold": 75,
            "min_rr": 1.8,
        }
    return cfg


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _log_improvement(lines: list[str]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = "\n".join(f"- {ln}" for ln in lines)
    with open(IMPROVEMENTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## {ts} — Adaptive Parameter Update\n\n{block}\n\n---\n")


def _append_snapshot(snap: dict) -> None:
    with open(SNAPSHOTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")


def run_adaptive_learning(state: dict, deep: bool = False) -> None:
    """Analyse trade history and adjust strategy parameters if warranted.

    Args:
        state: current daily state dict (passed in from runner, not modified here)
        deep:  when True (weekly run), also evaluate 30-trade window stats
    """
    trades = _load_closed_trades()

    stats_10 = _compute_stats(trades, 10)
    stats_30 = _compute_stats(trades, 30) if deep else {"count": 0}

    cfg = _load_config()
    adaptive = cfg["adaptive"]
    adjustments: list[dict] = []

    score = adaptive.get("score_threshold", 65)
    min_rr = adaptive.get("min_rr", 1.8)

    wr_10 = stats_10.get("win_rate")
    rr_10 = stats_10.get("avg_rr", 0.0)
    n_10 = stats_10.get("count", 0)

    # Rule 1 — losing streak: raise score threshold (be more selective)
    if n_10 >= 5 and wr_10 is not None and wr_10 < 0.45:
        new = min(score + 2, _SCORE_MAX)
        if new != score:
            adjustments.append({
                "param": "score_threshold",
                "from": score,
                "to": new,
                "reason": f"win_rate(10) = {wr_10:.0%} < 45%",
            })
            score = new

    # Rule 2 — strong win streak: ease score threshold slightly
    if n_10 >= 10 and wr_10 is not None and wr_10 > 0.70:
        new = max(score - 1, _SCORE_MIN)
        if new != score:
            adjustments.append({
                "param": "score_threshold",
                "from": score,
                "to": new,
                "reason": f"win_rate(10) = {wr_10:.0%} > 70%",
            })
            score = new

    # Rule 3 — poor R:R being achieved: tighten min_rr entry bar
    if n_10 >= 5 and 0 < rr_10 < 1.5:
        new = round(min(min_rr + 0.1, _RR_CEILING), 2)
        if new != min_rr:
            adjustments.append({
                "param": "min_rr",
                "from": min_rr,
                "to": new,
                "reason": f"avg_rr(10) = {rr_10:.2f} < 1.5",
            })
            min_rr = new

    # Rule 4 — excellent R:R being achieved: allow slightly lower bar
    if n_10 >= 5 and rr_10 > 2.2:
        new = round(max(min_rr - 0.1, _RR_FLOOR), 2)
        if new != min_rr:
            adjustments.append({
                "param": "min_rr",
                "from": min_rr,
                "to": new,
                "reason": f"avg_rr(10) = {rr_10:.2f} > 2.2",
            })
            min_rr = new

    if adjustments:
        adaptive["score_threshold"] = score
        adaptive["midday_score_threshold"] = max(score + 10, 70)
        adaptive["min_rr"] = min_rr
        cfg["adaptive"] = adaptive
        _save_config(cfg)
        _log_improvement([
            f"{a['param']}: {a['from']} → {a['to']} ({a['reason']})"
            for a in adjustments
        ])

    _append_snapshot({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "routine": "weekly" if deep else "review",
        "trades_total": len(trades),
        "win_rate_10": round(wr_10, 3) if wr_10 is not None else None,
        "avg_rr_10": rr_10 if n_10 else None,
        "win_rate_30": round(stats_30["win_rate"], 3) if stats_30.get("count", 0) > 0 else None,
        "avg_rr_30": stats_30.get("avg_rr") if stats_30.get("count", 0) > 0 else None,
        "score_threshold": score,
        "min_rr": min_rr,
        "adjustments": adjustments,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
