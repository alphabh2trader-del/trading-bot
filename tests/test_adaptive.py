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


def test_ladder_index_picks_nearest():
    ladder = [1.0, 0.66, 0.33]
    assert adaptive._ladder_index(ladder, 1.0) == 0
    assert adaptive._ladder_index(ladder, 0.66) == 1
    assert adaptive._ladder_index(ladder, 0.33) == 2
    assert adaptive._ladder_index(ladder, 0.5) == 1  # closest to 0.66
