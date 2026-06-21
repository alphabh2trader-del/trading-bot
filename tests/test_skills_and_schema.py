"""Skills wiring + trade CSV schema consistency."""
from pathlib import Path

import pandas as pd

from memory.trade_schema import TRADE_FIELDNAMES
from src.skills.atr_stops import calculate_atr_stop
from src.skills.volume_analysis import get_volume_signal
from strategy.scorer import calculate_score


TRADES_CSV = Path(__file__).parent.parent / "memory" / "trades.csv"


def test_trades_csv_header_matches_schema():
    header = TRADES_CSV.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == TRADE_FIELDNAMES


def test_atr_stop_below_entry_for_long():
    df = pd.DataFrame({
        "high": [11, 12, 13, 12, 14, 13],
        "low": [9, 10, 11, 10, 12, 11],
        "close": [10, 11, 12, 11, 13, 12],
    })
    stop, atr_val = calculate_atr_stop(df, "long", atr_multiplier=1.5)
    assert stop < df["close"].iloc[-1]
    assert atr_val > 0


def test_atr_stop_above_entry_for_short():
    df = pd.DataFrame({
        "high": [14, 13, 12, 13, 11, 12],
        "low": [12, 11, 10, 11, 9, 10],
        "close": [13, 12, 11, 12, 10, 11],
    })
    stop, _ = calculate_atr_stop(df, "short", atr_multiplier=1.5)
    assert stop > df["close"].iloc[-1]


def test_volume_signal_confirms_on_spike():
    df = pd.DataFrame({
        "high": [10] * 25, "low": [9] * 25, "close": [9.5] * 25,
        "volume": [100] * 24 + [500],
    })
    sig = get_volume_signal(df)
    assert bool(sig["confirmed"]) is True
    assert sig["ratio"] >= 1.2


def test_scorer_returns_none_on_insufficient_data():
    small = pd.DataFrame({
        "open": [1, 2], "high": [1, 2], "low": [1, 2],
        "close": [1, 2], "volume": [1, 1],
    })
    assert calculate_score("X", small, small, "NORMAL") is None
