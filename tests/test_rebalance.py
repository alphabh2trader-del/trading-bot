"""Rebalance safety + correctness (the two HIGH audit fixes).

Covers:
  - target_portfolio_status flags symbols whose data could not be fetched
    (so the rebalance can abort/protect instead of liquidating on a data outage).
  - rebalance_portfolio actually RESIZES held positions toward target weight
    (so an exposure de-risk trims the book), respects the no-churn band,
    opens new entries, fully exits dropped symbols, and PROTECTS unknown ones.
  - check_tp_sl_hits skips trend positions (empty SL/TP) without crashing.

All broker/data calls and CSV I/O are stubbed — pure logic, no network.
"""
import numpy as np
import pandas as pd

import execution.engine as engine
import src.execution.alpaca_bridge as bridge
import execution.portfolio as portfolio
from strategy.trend_timing import target_portfolio_status


def _daily(closes):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": closes, "high": closes * 1.01, "low": closes * 0.99,
         "close": closes, "volume": np.full(len(closes), 1_000_000)},
        index=pd.date_range("2020-01-01", periods=len(closes), freq="D"),
    )


# ----------------------------------------------------- target_portfolio_status
def test_status_flags_unfetchable_symbols():
    up = _daily(np.linspace(100, 200, 420))

    def fetch(sym):
        if sym == "TLT":
            return None            # simulated data outage
        if sym == "GLD":
            raise TimeoutError()   # simulated exception
        return up

    weights, failed = target_portfolio_status(["SPY", "QQQ", "TLT", "GLD"], fetch, exposure=1.0)
    assert set(failed) == {"TLT", "GLD"}        # unknown, not treated as bearish
    assert set(weights) == {"SPY", "QQQ"}       # only positively-confirmed uptrends held


# ------------------------------------------------------------ rebalance helper
def _patch(monkeypatch, equity, positions, price=100.0):
    orders = []
    monkeypatch.setattr(bridge, "get_account", lambda: {"equity": equity})
    monkeypatch.setattr(bridge, "get_positions", lambda: positions)
    monkeypatch.setattr(bridge, "submit_market_order",
                        lambda sym, qty, side: orders.append((sym, round(float(qty), 4), side)) or {"order_id": "X"})
    monkeypatch.setattr(bridge, "close_position",
                        lambda sym: orders.append((sym, "CLOSE", "")) or {"order_id": "X"})
    monkeypatch.setattr(engine, "_price", lambda sym: price)
    monkeypatch.setattr(engine, "_log_trend_open", lambda *a, **k: None)
    monkeypatch.setattr(engine, "_resize_trend_position", lambda *a, **k: None)
    monkeypatch.setattr(engine, "get_open_trades_by_symbol", lambda sym: [])
    monkeypatch.setattr(engine, "close_paper_trade", lambda *a, **k: None)
    return orders


def test_rebalance_opens_new_entries_from_cash(monkeypatch):
    orders = _patch(monkeypatch, equity=100_000, positions=[], price=100.0)
    actions = engine.rebalance_portfolio({"SPY": 0.5, "QQQ": 0.5})
    assert ("SPY", 500.0, "long") in orders
    assert ("QQQ", 500.0, "long") in orders
    assert set(actions["bought"]) == {"SPY", "QQQ"}


def test_rebalance_trims_held_position_on_exposure_drop(monkeypatch):
    # Held 500 sh worth $50k; exposure de-risk cuts target weight to 0.33 -> $33k -> 330 sh.
    pos = [{"symbol": "SPY", "qty": 500, "market_value": 50_000}]
    orders = _patch(monkeypatch, equity=100_000, positions=pos, price=100.0)
    actions = engine.rebalance_portfolio({"SPY": 0.33})
    assert ("SPY", 170.0, "sell") in orders     # trims 500 -> 330
    assert actions["resized"] == ["SPY"]


def test_rebalance_no_churn_within_band(monkeypatch):
    # Position already at its $50k target (weight 0.5) — drift 0, no order.
    pos = [{"symbol": "SPY", "qty": 500, "market_value": 50_000}]
    orders = _patch(monkeypatch, equity=100_000, positions=pos, price=100.0)
    actions = engine.rebalance_portfolio({"SPY": 0.5})
    assert orders == []
    assert actions["held"] == ["SPY"]


def test_rebalance_exits_dropped_symbol(monkeypatch):
    pos = [{"symbol": "SPY", "qty": 500, "market_value": 50_000}]
    orders = _patch(monkeypatch, equity=100_000, positions=pos, price=100.0)
    actions = engine.rebalance_portfolio({})        # SPY no longer in target
    assert ("SPY", "CLOSE", "") in orders
    assert actions["sold"] == ["SPY"]


def test_rebalance_protects_unknown_symbol(monkeypatch):
    # SPY absent from target but its data was unavailable this run -> never liquidate.
    pos = [{"symbol": "SPY", "qty": 500, "market_value": 50_000}]
    orders = _patch(monkeypatch, equity=100_000, positions=pos, price=100.0)
    actions = engine.rebalance_portfolio({}, protect={"SPY"})
    assert orders == []                              # no close order
    assert actions["protected"] == ["SPY"]
    assert actions["sold"] == []


# ------------------------------------------------- check_tp_sl_hits trend guard
def test_check_tp_sl_hits_skips_trend_positions(monkeypatch):
    trend_trade = {
        "trade_id": "abc", "symbol": "SPY", "direction": "long",
        "status": "open", "stop_loss": "", "take_profit": "", "notes": "trend | weight 0.05",
    }
    monkeypatch.setattr(portfolio, "get_open_trades", lambda: [trend_trade])
    monkeypatch.setattr(portfolio, "get_positions", lambda: [])  # position 'gone' from Alpaca
    # Must NOT raise ValueError on float("") and must report nothing closed.
    assert portfolio.check_tp_sl_hits() == []
