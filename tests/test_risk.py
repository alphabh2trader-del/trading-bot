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


def test_can_open_trade_blocks_on_daily_drawdown():
    state = {"daily_drawdown": config.MAX_DRAWDOWN_PCT, "exposure_pct": 0.0}
    allowed, _ = risk_engine.can_open_trade(state)
    assert allowed is False


def test_can_open_trade_blocks_on_exposure():
    state = {"daily_drawdown": 0.0, "exposure_pct": config.MAX_TOTAL_EXPOSURE}
    allowed, _ = risk_engine.can_open_trade(state)
    assert allowed is False


def test_sector_allowed_respects_cap():
    state = {"open_sectors": ["tech"]}
    assert risk_engine.sector_allowed("tech", state) is False  # SECTOR_MAX = 1
    assert risk_engine.sector_allowed("finance", state) is True
