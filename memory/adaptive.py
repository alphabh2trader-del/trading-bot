"""Adaptive self-improvement — runs after EOD review (daily) and weekly (deep).

This is the bot's learning loop. It is STRATEGY-AWARE and, above all, CONSERVATIVE:
the ONE thing it changes automatically is RISK (exposure), never an entry/exit parameter.
That design choice exists precisely so the loop can never "improve" the bot into the
ground by tuning the edge away on a handful of noisy trades.

For the ACTIVE strategy `dual_swing+trend_v1` (`_run_dual_adaptive`):
  1. CAPITAL PRESERVATION (auto) — reads realised account drawdown
     (memory/equity_state.json) and walks the TREND sleeve's `trend.exposure` DOWN a
     discrete ladder when drawdown deepens, restoring it after recovery (with hysteresis).
     Lowering exposure cuts both drawdown and return — a pure safety move.
  2. SWING PERFORMANCE (alert-only) — analyses the swing trade HISTORY (read-only; the
     full trades.csv is never modified or pruned) and, ONLY on a meaningful sample
     (>= 25 closed trades), sends a Telegram ALERT if win rate / profit factor falls
     through the floor. It changes NOTHING — the human decides whether to adjust.
  3. MONTHLY (deep) — re-validates `trend.sma_months` against a robust SMA cluster and
     FLAGS drift for review; never auto-flips a structural parameter (overfitting risk).

Every automatic change (only ever capital preservation) is logged to improvements.md +
session_snapshots.jsonl AND sent to Telegram.

`trend_timing_v1` keeps `_run_trend_adaptive`; legacy swing/meanrev keep the old tuning
path for the record. Called only between sessions — never during market hours.
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
EQUITY_STATE_FILE = MEMORY_DIR / "equity_state.json"
TREND_STATE_FILE = MEMORY_DIR / "trend_state.json"

# Legacy hard limits (swing/meanrev path)
_SCORE_MIN = 60
_SCORE_MAX = 80
_RR_FLOOR = 1.5
_RR_CEILING = 2.0


# --------------------------------------------------------------------------- I/O
def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _log_improvement(title: str, lines: list[str]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = "\n".join(f"- {ln}" for ln in lines)
    with open(IMPROVEMENTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## {ts} — {title}\n\n{block}\n\n---\n")


def _append_snapshot(snap: dict) -> None:
    with open(SNAPSHOTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap) + "\n")


def _notify(text: str) -> None:
    """Send a Telegram message; never let a notification failure break the loop."""
    try:
        from reporting.telegram import send_message
        send_message(text)
    except Exception:
        pass


def _load_closed_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("status") == "closed"]


def _realised_drawdown_pct() -> float | None:
    """Current account drawdown from peak, from memory/equity_state.json (written each
    run by risk_engine.check_risk via update_total_drawdown). None if not tracked yet."""
    if not EQUITY_STATE_FILE.exists():
        return None
    try:
        data = json.loads(EQUITY_STATE_FILE.read_text(encoding="utf-8"))
        peak = float(data.get("peak_equity", 0.0))
        last = float(data.get("last_equity", 0.0))
        if peak <= 0 or last <= 0:
            return None
        return max(0.0, (peak - last) / peak * 100)
    except Exception:
        return None


# ----------------------------------------------------------------- TREND TIMING
def _ladder_index(ladder: list[float], value: float) -> int:
    """Index of the ladder rung closest to `value` (ladder is descending)."""
    return min(range(len(ladder)), key=lambda i: abs(ladder[i] - value))


def _apply_trend_exposure_control(cfg: dict, deep: bool):
    """Capital-preservation core: mutate cfg['trend']['exposure'] toward the right ladder
    rung for the current drawdown, and (deep only) flag SMA robustness drift. Returns
    (changes, dd, robustness_note). Does NOT save/notify/snapshot — the caller does.

    This is the ONLY thing the loop ever changes automatically: it reduces (or restores)
    RISK. It never touches an entry/exit parameter — that protects the edge from being
    tuned away on noise. Shared by the trend-only and dual-strategy paths.
    """
    trend = cfg.setdefault("trend", {})
    ladder = [float(x) for x in trend.get("derisk_ladder", [1.0, 0.66, 0.33])]
    base = float(trend.get("base_exposure", 1.0))
    cur = float(trend.get("exposure", base))
    soft = float(trend.get("soft_derisk_dd_pct", 12.0))
    deep_dd = float(trend.get("deep_derisk_dd_pct", 18.0))
    restore = float(trend.get("restore_dd_pct", 6.0))

    dd = _realised_drawdown_pct()
    idx = _ladder_index(ladder, cur)
    changes: list[str] = []

    if dd is not None:
        # De-risk: walk DOWN the ladder as drawdown deepens.
        target_idx = idx
        if dd >= deep_dd:
            target_idx = max(idx, 2)            # deepest protection rung
        elif dd >= soft:
            target_idx = max(idx, 1)            # one rung down
        # Restore: walk UP one rung once recovered (hysteresis prevents flapping).
        elif dd <= restore and cur < base:
            target_idx = max(0, idx - 1)

        target_idx = min(target_idx, len(ladder) - 1)
        new_exposure = min(ladder[target_idx], base)  # never exceed base on restore

        if abs(new_exposure - cur) > 1e-9:
            direction = "DE-RISK" if new_exposure < cur else "RESTORE"
            reason = (f"realised drawdown {dd:.1f}% "
                      f"({'>=' if new_exposure < cur else '<='} "
                      f"{soft if new_exposure < cur else restore:.0f}%)")
            changes.append(f"exposure: {cur:.2f}x → {new_exposure:.2f}x ({direction}; {reason})")
            trend["exposure"] = round(new_exposure, 4)

    # Monthly structural robustness re-check (deep only, once per calendar month).
    robustness_note = None
    if deep:
        this_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if trend.get("last_robustness_check") != this_month:
            robustness_note = _revalidate_sma_robustness(int(trend.get("sma_months", 10)))
            trend["last_robustness_check"] = this_month
            if robustness_note and robustness_note.get("flag"):
                changes.append(
                    f"⚠ sma_months={robustness_note['active']} drifted out of the robust "
                    f"cluster (robust set: {robustness_note['robust']}). FLAGGED for review "
                    f"— NOT auto-changed."
                )

    return changes, dd, robustness_note


def _run_trend_adaptive(deep: bool) -> dict:
    """Trend-only strategy path: capital-preservation exposure control + robustness recheck."""
    cfg = _load_config()
    trend = cfg.setdefault("trend", {})
    cur = float(trend.get("exposure", trend.get("base_exposure", 1.0)))
    changes, dd, robustness_note = _apply_trend_exposure_control(cfg, deep)

    if changes:
        _save_config(cfg)
        _log_improvement("Adaptive (trend_timing_v1)", changes)
        _notify("🤖 AUTO-AMÉLIORATION — trend_timing_v1\n" + "\n".join(f"• {c}" for c in changes))

    snap = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "routine": "weekly" if deep else "review",
        "strategy": "trend_timing_v1",
        "realised_drawdown_pct": round(dd, 2) if dd is not None else None,
        "exposure": trend.get("exposure", cur),
        "base_exposure": float(trend.get("base_exposure", 1.0)),
        "sma_months": trend.get("sma_months", 10),
        "changes": changes,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if robustness_note:
        snap["robustness"] = robustness_note
    _append_snapshot(snap)
    return snap


# ----------------------------------------------------- DUAL (swing + trend)
# Minimum CLOSED swing trades before we even look at performance — 10 trades is noise
# for a strategy whose true win rate is ~46%. We never auto-tune entry params; if the
# sample looks genuinely degraded we ALERT a human and leave the strategy untouched.
_SWING_MIN_SAMPLE = 25
_SWING_WINDOW = 50
_SWING_WR_FLOOR = 0.40        # alert if rolling win rate drops below this
_SWING_PF_FLOOR = 1.0         # alert if rolling profit factor drops below break-even


def _swing_closed_trades() -> list[dict]:
    """Closed SWING trades only (trend-sleeve rows excluded). Read-only — the full
    trades.csv history is never modified or pruned, so it stays available for analysis."""
    return [t for t in _load_closed_trades()
            if "trend" not in (t.get("notes", "") or "").lower()]


def _swing_performance_flag() -> dict:
    """ALERT-ONLY health check on the swing sleeve. Reads trade history, never writes a
    single strategy parameter — so it can NEVER nuke the edge. Sends Telegram if the
    rolling sample looks degraded; otherwise stays silent."""
    trades = _swing_closed_trades()
    n = len(trades)
    if n < _SWING_MIN_SAMPLE:
        return {"swing_trades": n, "evaluated": False, "flag": False,
                "note": f"sample {n} < {_SWING_MIN_SAMPLE} — not enough to judge"}

    recent = trades[-_SWING_WINDOW:]
    pnl = [float(t.get("net_pnl_usd") or 0) for t in recent]
    wins = [p for p in pnl if p > 0]
    gross_win = sum(p for p in pnl if p > 0)
    gross_loss = -sum(p for p in pnl if p < 0)
    wr = len(wins) / len(recent)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    flag = (wr < _SWING_WR_FLOOR) or (pf < _SWING_PF_FLOOR)
    result = {
        "swing_trades": n, "evaluated": True, "window": len(recent),
        "win_rate": round(wr, 3), "profit_factor": round(pf, 2) if pf != float("inf") else None,
        "flag": bool(flag),
    }
    if flag:
        msg = (
            f"⚠ SWING PERFORMANCE ALERT (review needed — NOTHING was changed)\n"
            f"Last {len(recent)} swing trades: win rate {wr:.0%}, profit factor "
            f"{result['profit_factor']}.\n"
            f"Below the floor (WR {_SWING_WR_FLOOR:.0%} / PF {_SWING_PF_FLOOR:.1f}). "
            f"The bot does NOT auto-tune the strategy — you decide if/what to adjust."
        )
        _notify(msg)
        _log_improvement("Swing performance FLAG (no change made)", [msg.replace("\n", " ")])
    return result


def _run_dual_adaptive(deep: bool) -> dict:
    """Active dual_swing+trend_v1 path. Automatic action is LIMITED to capital
    preservation (trend exposure de-risk). Swing performance is ALERT-ONLY: it analyses
    the trade history but never modifies a strategy parameter — so the self-improvement
    loop can reduce risk on its own, but can never silently degrade the edge."""
    cfg = _load_config()
    trend = cfg.setdefault("trend", {})
    cur = float(trend.get("exposure", trend.get("base_exposure", 1.0)))

    # 1. Capital preservation (the only auto-change).
    changes, dd, robustness_note = _apply_trend_exposure_control(cfg, deep)
    if changes:
        _save_config(cfg)
        _log_improvement("Adaptive (dual_swing+trend_v1 — capital preservation)", changes)
        _notify("🤖 AUTO-AMÉLIORATION — préservation du capital\n" + "\n".join(f"• {c}" for c in changes))

    # 2. Swing performance — ALERT ONLY, no parameter writes.
    swing = _swing_performance_flag()

    snap = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "routine": "weekly" if deep else "review",
        "strategy": "dual_swing+trend_v1",
        "realised_drawdown_pct": round(dd, 2) if dd is not None else None,
        "trend_exposure": trend.get("exposure", cur),
        "swing": swing,
        "changes": changes,            # only ever capital-preservation changes
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if robustness_note:
        snap["robustness"] = robustness_note
    _append_snapshot(snap)
    return snap


def _revalidate_sma_robustness(active_months: int) -> dict | None:
    """Re-run a small SMA-lookback grid on recent data and check that the active lookback
    is still in the robust cluster (every member profitable, active within ~20% of best).
    Flag-only — never auto-changes the parameter. Returns None if data is unavailable."""
    try:
        from backtest.momentum import evaluate_lookback  # research harness
    except Exception:
        return None
    grid = sorted({active_months - 2, active_months, active_months + 2, 8, 10, 12})
    grid = [m for m in grid if m >= 4]
    results: dict[int, float] = {}
    for m in grid:
        try:
            res = evaluate_lookback(m, years=5, cost=0.0020)
            results[m] = float(res.get("cagr", 0.0))
        except Exception:
            continue
    if active_months not in results or len(results) < 2:
        return None
    robust = [m for m, c in results.items() if c > 0]
    best = max(results.values())
    active_cagr = results[active_months]
    drifted = (active_cagr <= 0) or (best > 0 and active_cagr < 0.80 * best)
    return {
        "active": active_months,
        "active_cagr": round(active_cagr, 4),
        "grid": {str(k): round(v, 4) for k, v in results.items()},
        "robust": robust,
        "flag": bool(drifted),
    }


# ----------------------------------------------------------- LEGACY (swing/meanrev)
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


def _run_legacy_adaptive(deep: bool) -> dict:
    trades = _load_closed_trades()
    stats_10 = _compute_stats(trades, 10)
    cfg = _load_config()
    adaptive = cfg.setdefault("adaptive", {"score_threshold": 65, "midday_score_threshold": 75, "min_rr": 1.8})
    adjustments: list[dict] = []
    score = adaptive.get("score_threshold", 65)
    min_rr = adaptive.get("min_rr", 1.8)
    wr_10 = stats_10.get("win_rate")
    rr_10 = stats_10.get("avg_rr", 0.0)
    n_10 = stats_10.get("count", 0)

    if n_10 >= 5 and wr_10 is not None and wr_10 < 0.45:
        new = min(score + 2, _SCORE_MAX)
        if new != score:
            adjustments.append({"param": "score_threshold", "from": score, "to": new, "reason": f"win_rate(10) = {wr_10:.0%} < 45%"})
            score = new
    if n_10 >= 10 and wr_10 is not None and wr_10 > 0.70:
        new = max(score - 1, _SCORE_MIN)
        if new != score:
            adjustments.append({"param": "score_threshold", "from": score, "to": new, "reason": f"win_rate(10) = {wr_10:.0%} > 70%"})
            score = new
    if n_10 >= 5 and 0 < rr_10 < 1.5:
        new = round(min(min_rr + 0.1, _RR_CEILING), 2)
        if new != min_rr:
            adjustments.append({"param": "min_rr", "from": min_rr, "to": new, "reason": f"avg_rr(10) = {rr_10:.2f} < 1.5"})
            min_rr = new
    if n_10 >= 5 and rr_10 > 2.2:
        new = round(max(min_rr - 0.1, _RR_FLOOR), 2)
        if new != min_rr:
            adjustments.append({"param": "min_rr", "from": min_rr, "to": new, "reason": f"avg_rr(10) = {rr_10:.2f} > 2.2"})
            min_rr = new

    if adjustments:
        adaptive["score_threshold"] = score
        adaptive["midday_score_threshold"] = max(score + 10, 70)
        adaptive["min_rr"] = min_rr
        cfg["adaptive"] = adaptive
        _save_config(cfg)
        lines = [f"{a['param']}: {a['from']} → {a['to']} ({a['reason']})" for a in adjustments]
        _log_improvement("Adaptive Parameter Update", lines)
        _notify("🤖 AUTO-AMÉLIORATION\n" + "\n".join(f"• {ln}" for ln in lines))

    snap = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "routine": "weekly" if deep else "review",
        "trades_total": len(trades),
        "win_rate_10": round(wr_10, 3) if wr_10 is not None else None,
        "avg_rr_10": rr_10 if n_10 else None,
        "score_threshold": score,
        "min_rr": min_rr,
        "adjustments": adjustments,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _append_snapshot(snap)
    return snap


# ------------------------------------------------------------------- DISPATCHER
def run_adaptive_learning(state: dict, deep: bool = False) -> dict:
    """Analyse performance and adjust the ACTIVE strategy's parameters if warranted.

    Args:
        state: current daily state dict (not mutated here)
        deep:  True on the weekly run — enables the monthly structural robustness re-check.
    """
    cfg = _load_config()
    strategy = cfg.get("system", {}).get("strategy", "")
    try:
        if strategy == "dual_swing+trend_v1":
            return _run_dual_adaptive(deep)
        if strategy == "trend_timing_v1":
            return _run_trend_adaptive(deep)
        return _run_legacy_adaptive(deep)
    except Exception as exc:  # learning must never crash a routine
        _append_snapshot({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "routine": "weekly" if deep else "review",
            "error": str(exc),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return {"error": str(exc)}
