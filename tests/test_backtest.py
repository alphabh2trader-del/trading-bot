"""Backtest engine — exit detection and stats aggregation."""
from types import SimpleNamespace

import pandas as pd

from backtest import engine
from backtest.engine import compute_stats, simulate_symbol


def _setup(direction="long", entry=100.0, sl=98.0, tp=104.0, score=80):
    return SimpleNamespace(
        symbol="TEST", direction=direction, entry_price=entry,
        stop_loss=sl, take_profit=tp, score=score, rr=2.0,
    )


def test_walk_to_exit_long_takes_profit():
    h4 = pd.DataFrame({
        "high": [100, 101, 104, 105],
        "low": [99, 100, 102, 103],
        "close": [100, 101, 103, 104],
    })
    idx, outcome, price = engine._walk_to_exit(h4, entry_i=0, setup=_setup())
    assert outcome == "TP" and price == 104.0 and idx == 2


def test_walk_to_exit_long_stops_out():
    h4 = pd.DataFrame({
        "high": [100, 101, 100],
        "low": [99, 97, 96],
        "close": [100, 98, 97],
    })
    idx, outcome, price = engine._walk_to_exit(h4, entry_i=0, setup=_setup())
    assert outcome == "SL" and price == 98.0 and idx == 1


def test_walk_to_exit_straddle_assumes_stop_first():
    # one bar touches both SL (98) and TP (104) -> conservative: SL
    h4 = pd.DataFrame({"high": [100, 105], "low": [99, 97], "close": [100, 100]})
    _, outcome, _ = engine._walk_to_exit(h4, entry_i=0, setup=_setup())
    assert outcome == "SL"


def test_compute_stats_basic():
    trades = [{"pnl_r": 2.0}, {"pnl_r": -1.0}, {"pnl_r": 2.0}, {"pnl_r": -1.0}]
    stats = compute_stats(trades)
    assert stats["trades"] == 4
    assert stats["win_rate"] == 50.0
    assert stats["profit_factor"] == 2.0   # 4R profit / 2R loss
    assert stats["total_r"] == 2.0


def test_compute_stats_empty():
    assert compute_stats([])["trades"] == 0


def test_simulate_records_a_trade(monkeypatch):
    d1 = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
        index=pd.date_range("2020-01-01", periods=250, freq="D"),
    )
    n = 60
    h4 = pd.DataFrame({
        "high": [100.0] * 51 + [104.0] * (n - 51),
        "low": [99.0] * n,
        "close": [100.0] * n,
        "volume": [1_000_000] * n,
    }, index=pd.date_range("2021-01-01", periods=n, freq="4h"))

    calls = {"n": 0}

    def fake_score(symbol, d1_slice, h4_slice, regime):
        calls["n"] += 1
        return _setup() if calls["n"] == 1 else None

    monkeypatch.setattr(engine, "calculate_score", fake_score)
    trades = simulate_symbol("TEST", d1, h4, score_threshold=0)
    assert len(trades) == 1
    assert trades[0]["outcome"] == "TP"
    assert trades[0]["pnl_r"] == 2.0
