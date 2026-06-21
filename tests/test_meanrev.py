"""Connors RSI-2 mean-reversion strategy: signal, exit, indicator."""
import numpy as np
import pandas as pd

import config
from strategy.indicators import wilder_rsi
from strategy.mean_reversion import compute_signal, should_exit


def _daily(closes):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": closes, "high": closes * 1.005, "low": closes * 0.995,
        "close": closes, "volume": np.full(len(closes), 1_000_000),
    }, index=pd.date_range("2020-01-01", periods=len(closes), freq="D"))


def test_wilder_rsi_low_after_drop():
    closes = list(np.linspace(100, 130, 60)) + [125, 120]  # sharp 2-day drop
    rsi = wilder_rsi(_daily(closes)["close"], 2)
    assert rsi.iloc[-1] < 20


def test_compute_signal_fires_on_oversold_uptrend():
    base = list(np.linspace(100, 160, 220))
    base[-1] = base[-2] * 0.96  # crush RSI(2) while staying above SMA200
    sig = compute_signal("SPY", _daily(base))
    assert sig is not None
    assert sig["direction"] == "long"
    assert sig["strategy"] == "meanrev"
    # disaster stop is 8% below entry
    assert abs(sig["stop_loss"] - round(sig["entry_price"] * (1 - config.MEANREV_STOP_PCT), 4)) < 1e-6
    assert sig["score"] >= 65


def test_compute_signal_none_below_trend():
    # downtrend: price below SMA200 -> no long signal even if oversold
    base = list(np.linspace(160, 100, 220))
    sig = compute_signal("SPY", _daily(base))
    assert sig is None


def test_compute_signal_none_when_not_oversold():
    base = list(np.linspace(100, 160, 220))  # steadily rising, RSI not < 10
    sig = compute_signal("SPY", _daily(base))
    assert sig is None


def test_should_exit_on_rule():
    # last close above the 5-day SMA -> rule exit (>= 6 bars for SMA5)
    closes = [100, 99, 98, 97, 96, 105]
    do_exit, reason = should_exit(_daily(closes), {"stop_loss": 80}, days_held=2)
    assert do_exit and "RULE" in reason


def test_should_exit_on_stop():
    closes = [100, 99, 98, 97, 96, 90]
    do_exit, reason = should_exit(_daily(closes), {"stop_loss": 95}, days_held=1)
    assert do_exit and "STOP" in reason


def test_should_exit_on_max_hold():
    # below SMA5 and above stop, but held too long
    closes = [100, 101, 102, 103, 104, 100]
    do_exit, reason = should_exit(_daily(closes), {"stop_loss": 80},
                                  days_held=config.MEANREV_MAX_HOLD)
    assert do_exit and "MAX_HOLD" in reason
