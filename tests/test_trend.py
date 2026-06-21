"""Trend-timing strategy: 10-month SMA qualification and portfolio construction."""
import numpy as np
import pandas as pd

import config
from strategy.trend_timing import _qualifies, target_portfolio


def _daily(closes):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": closes, "high": closes * 1.01, "low": closes * 0.99,
        "close": closes, "volume": np.full(len(closes), 1_000_000),
    }, index=pd.date_range("2020-01-01", periods=len(closes), freq="D"))


def test_qualifies_in_uptrend():
    # ~300 trading days rising -> last monthly close above its 10-month SMA
    df = _daily(np.linspace(100, 200, 420))
    assert _qualifies(df) is True


def test_not_qualifies_in_downtrend():
    df = _daily(np.linspace(200, 100, 420))
    assert _qualifies(df) is False


def test_qualifies_false_on_short_history():
    assert _qualifies(_daily(np.linspace(100, 110, 50))) is False


def test_target_portfolio_equal_weight_scaled_by_exposure():
    up = _daily(np.linspace(100, 200, 420))
    down = _daily(np.linspace(200, 100, 420))
    data = {"SPY": up, "QQQ": up, "TLT": down}

    def fetch(sym):
        return data[sym]

    target = target_portfolio(["SPY", "QQQ", "TLT"], fetch, exposure=1.0)
    assert set(target) == {"SPY", "QQQ"}           # only uptrending held
    assert abs(sum(target.values()) - 1.0) < 1e-6  # fully invested at exposure 1.0
    assert abs(target["SPY"] - 0.5) < 1e-6         # equal weight


def test_target_portfolio_all_cash():
    down = _daily(np.linspace(200, 100, 420))
    target = target_portfolio(["SPY", "QQQ"], lambda s: down, exposure=1.0)
    assert target == {}  # nothing in an uptrend -> all cash
