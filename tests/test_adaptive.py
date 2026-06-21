"""Self-improvement loop (memory/adaptive.py) — trend-timing exposure control.

Verifies the bot's learning loop actually drives the ACTIVE strategy's risk dial:
de-risks exposure as realised drawdown deepens, and restores it after recovery.
File I/O and Telegram are stubbed so these are pure-logic, network-free tests.
"""
import memory.adaptive as adaptive


def _setup(monkeypatch, dd, exposure=1.0, base=1.0):
    """Stub config + drawdown + side effects; return the captured config dict."""
    cfg = {
        "system": {"strategy": "trend_timing_v1"},
        "trend": {
            "exposure": exposure,
            "base_exposure": base,
            "min_exposure": 0.33,
            "sma_months": 10,
            "soft_derisk_dd_pct": 12.0,
            "deep_derisk_dd_pct": 18.0,
            "restore_dd_pct": 6.0,
            "derisk_ladder": [1.0, 0.66, 0.33],
        },
    }
    saved = {}
    monkeypatch.setattr(adaptive, "_load_config", lambda: cfg)
    monkeypatch.setattr(adaptive, "_save_config", lambda c: saved.update(c))
    monkeypatch.setattr(adaptive, "_realised_drawdown_pct", lambda: dd)
    monkeypatch.setattr(adaptive, "_notify", lambda *a, **k: None)
    monkeypatch.setattr(adaptive, "_log_improvement", lambda *a, **k: None)
    monkeypatch.setattr(adaptive, "_append_snapshot", lambda *a, **k: None)
    return cfg, saved


def test_no_change_in_normal_drawdown(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=4.0, exposure=1.0)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert snap["changes"] == []
    assert cfg["trend"]["exposure"] == 1.0


def test_derisk_one_rung_on_soft_breach(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=13.0, exposure=1.0)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert cfg["trend"]["exposure"] == 0.66
    assert any("DE-RISK" in c for c in snap["changes"])


def test_deep_derisk_on_deep_breach(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=20.0, exposure=1.0)
    adaptive.run_adaptive_learning({}, deep=False)
    assert cfg["trend"]["exposure"] == 0.33


def test_restore_after_recovery(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=3.0, exposure=0.33, base=1.0)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    # walks UP one rung (0.33 -> 0.66), not straight back to base (hysteresis)
    assert cfg["trend"]["exposure"] == 0.66
    assert any("RESTORE" in c for c in snap["changes"])


def test_restore_never_exceeds_base(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=2.0, exposure=0.66, base=0.66)
    adaptive.run_adaptive_learning({}, deep=False)
    assert cfg["trend"]["exposure"] == 0.66  # already at base, no over-restore


def test_no_drawdown_data_is_safe(monkeypatch):
    cfg, saved = _setup(monkeypatch, dd=None, exposure=1.0)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert snap["changes"] == []
    assert cfg["trend"]["exposure"] == 1.0


def _setup_dual(monkeypatch, dd, exposure, swing_trades):
    """Stub config (dual strategy) + drawdown + swing trade history + side effects.
    Returns (cfg, saved, captured) where `captured` records notify/save calls."""
    cfg = {
        "system": {"strategy": "dual_swing+trend_v1"},
        "trend": {
            "exposure": exposure, "base_exposure": 1.0, "min_exposure": 0.33,
            "sma_months": 10, "soft_derisk_dd_pct": 12.0, "deep_derisk_dd_pct": 18.0,
            "restore_dd_pct": 6.0, "derisk_ladder": [1.0, 0.66, 0.33],
        },
    }
    captured = {"saved": 0, "alerts": []}
    monkeypatch.setattr(adaptive, "_load_config", lambda: cfg)
    monkeypatch.setattr(adaptive, "_save_config", lambda c: captured.update(saved=captured["saved"] + 1))
    monkeypatch.setattr(adaptive, "_realised_drawdown_pct", lambda: dd)
    monkeypatch.setattr(adaptive, "_notify", lambda t: captured["alerts"].append(t))
    monkeypatch.setattr(adaptive, "_log_improvement", lambda *a, **k: None)
    monkeypatch.setattr(adaptive, "_append_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(adaptive, "_load_closed_trades", lambda: swing_trades)
    return cfg, captured


def _swing(pnl):
    return {"status": "closed", "notes": "swing | setup", "net_pnl_usd": str(pnl)}


def test_dual_capital_preservation_still_derisks(monkeypatch):
    # The SAFE auto-action (exposure de-risk) must still fire under the dual strategy.
    cfg, captured = _setup_dual(monkeypatch, dd=13.0, exposure=1.0, swing_trades=[])
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert cfg["trend"]["exposure"] == 0.66
    assert any("DE-RISK" in c for c in snap["changes"])
    assert captured["saved"] == 1            # config saved for the risk change


def test_dual_swing_flag_never_touches_config(monkeypatch):
    # A degraded swing sample must ALERT but change NOTHING (no config save).
    bad = [_swing(-100)] * 25 + [_swing(50)] * 5   # ~17% win rate, PF < 1
    cfg, captured = _setup_dual(monkeypatch, dd=2.0, exposure=1.0, swing_trades=bad)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert snap["swing"]["flag"] is True
    assert captured["saved"] == 0            # NOTHING was written to config
    assert any("SWING PERFORMANCE ALERT" in a for a in captured["alerts"])
    # And the strategy params are untouched (no 'adaptive' section invented).
    assert "adaptive" not in cfg


def test_dual_swing_small_sample_not_evaluated(monkeypatch):
    # Below the minimum sample, the swing health check stays silent (no judging on noise).
    cfg, captured = _setup_dual(monkeypatch, dd=2.0, exposure=1.0,
                                swing_trades=[_swing(-100)] * 10)
    snap = adaptive.run_adaptive_learning({}, deep=False)
    assert snap["swing"]["evaluated"] is False
    assert snap["swing"]["flag"] is False
    assert captured["alerts"] == []


def test_ladder_index_picks_nearest():
    ladder = [1.0, 0.66, 0.33]
    assert adaptive._ladder_index(ladder, 1.0) == 0
    assert adaptive._ladder_index(ladder, 0.66) == 1
    assert adaptive._ladder_index(ladder, 0.33) == 2
    assert adaptive._ladder_index(ladder, 0.5) == 1  # closest to 0.66
