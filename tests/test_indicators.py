"""Indicator sanity checks — deterministic, no network."""
import pandas as pd

from strategy.indicators import ema, rsi, atr, rvol, detect_structure


def test_ema_of_constant_is_constant():
    s = pd.Series([5.0] * 50)
    assert abs(ema(s, 10).iloc[-1] - 5.0) < 1e-9


def test_rsi_strong_uptrend_is_high():
    # mostly-up series with small pullbacks (so loss > 0, avoiding the
    # zero-division NaN edge case of a perfectly monotonic series)
    deltas = ([1.0, 1.0, 1.0, -0.3] * 15)
    s = pd.Series(pd.Series(deltas).cumsum())
    assert rsi(s, 14).iloc[-1] > 70


def test_rsi_monotonic_fall_is_low():
    s = pd.Series(range(60, 1, -1), dtype=float)
    assert rsi(s, 14).iloc[-1] < 5


def test_atr_is_positive():
    df = pd.DataFrame({
        "high": [11, 12, 13, 12, 14],
        "low": [9, 10, 11, 10, 12],
        "close": [10, 11, 12, 11, 13],
    })
    assert atr(df, period=3).iloc[-1] > 0


def test_rvol_detects_volume_spike():
    df = pd.DataFrame({"volume": [100] * 20 + [400]})
    assert rvol(df, lookback=20) == 4.0


def test_detect_structure_bullish():
    df = pd.DataFrame({
        "high": list(range(10, 25)),
        "low": list(range(5, 20)),
    })
    assert detect_structure(df) == "bullish"
