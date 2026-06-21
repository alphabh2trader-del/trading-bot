"""Risk engine + position sizing + drawdown tracking."""
import json

import config
from src.skills.atr_stops import calculate_position_size
from risk import risk_engine
from state import risk_state


def test_position_size_flat_one_percent():
    # 100k equity, 1% risk, $5 risk per share -> 200 shares
    shares = calculate_position_size(equity=100_000, risk_pct=0.01, entry=150, stop_loss=145)
    assert shares == 200


def test_position_size_zero_risk_returns_zero():
    assert calculate_position_size(equity=100_000, risk_pct=0.01, entry=150, stop_loss=150) == 0


def test_total_drawdown_tracks_peak(tmp_path, monkeypatch):
    monkeypatch.setattr(risk_state, "EQUITY_STATE_FILE", tmp_path / "eq.json")
    assert risk_state.update_total_drawdown(10_000) == 0.0
    assert risk_state.update_total_drawdown(9_200) == 8.0   # 8% off the 10k peak
    # recovery does not reset the peak; new high resets drawdown to 0
    assert risk_state.update_total_drawdown(11_000) == 0.0


def test_daily_drawdown_does_not_halt_only_shrinks_size(monkeypatch):
    # New risk model: a daily loss NEVER blocks a trade — it only reduces size.
    monkeypatch.setattr(risk_engine, "_open_swing_risk_pct", lambda: 0.0)
    monkeypatch.setattr("execution.portfolio.get_open_trades", lambda: [])
    state = {"daily_drawdown": config.MAX_DRAWDOWN_PCT}
    allowed, _ = risk_engine.can_open_trade(state)
    assert allowed is True
    # ...but the per-trade size multiplier has shrunk below 1.0.
    assert risk_engine.daily_risk_multiplier(state) < 1.0
    # A clean day trades full size.
    assert risk_engine.daily_risk_multiplier({"daily_drawdown": 0.0}) == 1.0


def test_can_open_trade_blocks_when_risk_budget_spent(monkeypatch):
    # No position-count cap; the gate is the aggregate open-risk budget.
    monkeypatch.setattr(risk_engine, "_open_swing_risk_pct", lambda: config.MAX_OPEN_RISK_PCT)
    monkeypatch.setattr("execution.portfolio.get_open_trades", lambda: [])
    allowed, reason = risk_engine.can_open_trade({"daily_drawdown": 0.0})
    assert allowed is False
    assert "budget" in reason.lower()


def test_can_open_trade_allows_within_budget(monkeypatch):
    monkeypatch.setattr(risk_engine, "_open_swing_risk_pct", lambda: 0.0)
    monkeypatch.setattr("execution.portfolio.get_open_trades", lambda: [])
    allowed, _ = risk_engine.can_open_trade({"daily_drawdown": 0.0})
    assert allowed is True


def test_sector_allowed_respects_cap():
    # SECTOR_MAX = 2 now: a single open tech position still allows one more.
    assert risk_engine.sector_allowed("tech", {"open_sectors": ["tech"]}) is True
    assert risk_engine.sector_allowed("tech", {"open_sectors": ["tech", "tech"]}) is False
    assert risk_engine.sector_allowed("finance", {"open_sectors": ["tech", "tech"]}) is True
