import csv
import uuid
from datetime import datetime
from pathlib import Path

import config
from data.market_data import get_live_quote
from src.execution.alpaca_bridge import get_account, submit_bracket_order, submit_market_order, close_position
from memory.logger import log_execution_entry
from memory.trade_schema import TRADE_FIELDNAMES as FIELDNAMES

TRADES_FILE = Path(__file__).parent.parent / "memory" / "trades.csv"


def open_paper_trade(setup: dict, risk_multiplier: float = 1.0) -> dict:
    account = get_account()
    equity = account["equity"]
    entry = setup["entry_price"]
    sl = setup["stop_loss"]
    tp = setup["take_profit"]
    risk_per_share = abs(entry - sl)
    risk_usd = equity * (config.MAX_RISK_PER_TRADE / 100) * risk_multiplier
    size = round(risk_usd / risk_per_share, 2) if risk_per_share > 0 else 0

    is_meanrev = setup.get("strategy") == "meanrev"
    if is_meanrev:
        # Mean reversion: market entry, no bracket TP (exit is rule-based and
        # managed by the daily routines). The disaster stop is software-managed.
        try:
            order = submit_market_order(setup["symbol"], size, setup["direction"])
            alpaca_order_id = order["order_id"]
        except Exception as e:
            alpaca_order_id = f"ERROR:{e}"
        tp_value = ""
        potential = ""
        notes = f"meanrev | {setup.get('reason', '')}"
    else:
        # Trend setups: bracket order — TP and SL handled automatically by Alpaca.
        try:
            order = submit_bracket_order(
                symbol=setup["symbol"], qty=size, side=setup["direction"],
                take_profit_price=tp, stop_loss_price=sl,
            )
            alpaca_order_id = order["order_id"]
        except Exception as e:
            alpaca_order_id = f"ERROR:{e}"
        tp_value = tp
        potential = round(size * abs(tp - entry), 2)
        notes = setup.get("reason", "")

    trade = {
        "trade_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": setup["symbol"],
        "direction": setup["direction"],
        "entry_price": entry,
        "stop_loss": sl,
        "take_profit": tp_value,
        "position_size": size,
        "risk_pct": config.MAX_RISK_PER_TRADE,
        "risk_usd": round(risk_usd, 2),
        "potential_usd": potential,
        "status": "open",
        "exit_price": "",
        "exit_timestamp": "",
        "pnl_pct": "",
        "pnl_usd": "",
        "fees_usd": "",
        "net_pnl_usd": "",
        "alpaca_order_id": alpaca_order_id,
        "notes": notes,
    }

    _append_trade(trade)
    log_execution_entry(setup, trade, equity)
    return trade


def _price(symbol: str) -> float:
    """Latest tradable price: live quote mid, else last daily close."""
    try:
        return float(get_live_quote(symbol)["mid"])
    except Exception:
        from data.market_data import fetch_bars_safe
        df = fetch_bars_safe(symbol, "1Day", timeout_sec=3.0)
        return float(df["close"].iloc[-1]) if df is not None and not df.empty else 0.0


def _log_trend_open(symbol: str, price: float, qty: float, weight: float, order_id: str) -> None:
    trade = {k: "" for k in FIELDNAMES}
    trade.update({
        "trade_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol, "direction": "long",
        "entry_price": round(price, 4), "stop_loss": "", "take_profit": "",
        "position_size": qty, "risk_pct": round(weight * 100, 2),
        "status": "open", "alpaca_order_id": order_id,
        "notes": f"trend | weight {weight:.3f}",
    })
    _append_trade(trade)


def rebalance_portfolio(target_weights: dict, protect: set | None = None) -> dict:
    """Monthly trend-timing rebalance to target weights.

    For every symbol in (target ∪ currently held) we compare the CURRENT position
    (Alpaca is the source of truth) to its target dollar value (equity × weight):
      - target 0 & held  -> SELL to cash (a trend broke down) ... UNLESS protected
      - not held & target -> BUY the target quantity (newly entered an uptrend)
      - held & target     -> RESIZE toward the target weight, but only when the
        drift exceeds REBALANCE_BAND (avoids churn on small price drifts). This is
        what makes an EXPOSURE change (e.g. the adaptive de-risk 1.0x->0.66x) actually
        trim existing holdings, and keeps the book equal-weight over time.

    `protect` = symbols whose data could not be fetched this run; they are NEVER sold
    (we can't tell if they're still in trend), preventing a data outage from
    liquidating the book.
    """
    from src.execution.alpaca_bridge import get_account, get_positions, submit_market_order, close_position

    protect = protect or set()
    band = float(getattr(config, "REBALANCE_BAND", 0.15))
    equity = get_account()["equity"]
    positions = {p["symbol"]: p for p in get_positions()}
    actions = {"bought": [], "sold": [], "resized": [], "held": [], "protected": []}

    for symbol in sorted(set(target_weights) | set(positions)):
        weight = float(target_weights.get(symbol, 0.0))
        pos = positions.get(symbol)
        cur_qty = float(pos["qty"]) if pos else 0.0
        cur_val = float(pos["market_value"]) if pos else 0.0

        # --- Exit: no longer in the target ---
        if weight <= 0:
            if cur_qty <= 0:
                continue
            if symbol in protect:
                actions["protected"].append(symbol)  # data unknown -> keep, don't liquidate
                continue
            try:
                close_position(symbol)
            except Exception:
                pass
            for t in get_open_trades_by_symbol(symbol):
                close_paper_trade(t["trade_id"], _price(symbol), "trend exit (below SMA)")
            actions["sold"].append(symbol)
            continue

        price = _price(symbol)
        if price <= 0:
            if cur_qty > 0:
                actions["held"].append(symbol)
            continue
        target_val = equity * weight
        target_qty = round(target_val / price, 4)

        # --- New entry ---
        if cur_qty <= 0:
            if target_qty <= 0:
                continue
            try:
                order = submit_market_order(symbol, target_qty, "long")
                order_id = order["order_id"]
            except Exception as e:
                order_id = f"ERROR:{e}"
            _log_trend_open(symbol, price, target_qty, weight, order_id)
            actions["bought"].append(symbol)
            continue

        # --- Held & in target: resize toward weight only if drift exceeds the band ---
        drift = abs(target_val - cur_val) / target_val if target_val > 0 else 0.0
        delta_qty = round(target_qty - cur_qty, 4)
        if drift > band and abs(delta_qty) > 0:
            side = "long" if delta_qty > 0 else "sell"   # "sell" trims the existing long
            try:
                submit_market_order(symbol, abs(delta_qty), side)
            except Exception:
                pass
            _resize_trend_position(symbol, target_qty, weight)
            actions["resized"].append(symbol)
        else:
            actions["held"].append(symbol)

    return actions


def _resize_trend_position(symbol: str, new_qty: float, weight: float) -> None:
    """Update the open trend CSV row(s) for `symbol` to the new share count after a
    resize. Alpaca remains the source of truth for the live position; this keeps the
    local trade log consistent (one open row per held symbol)."""
    trades = _load_all_trades()
    touched = False
    for t in trades:
        if t.get("symbol") == symbol and t.get("status") == "open":
            t["position_size"] = new_qty
            t["risk_pct"] = round(weight * 100, 2)
            t["notes"] = f"{t.get('notes', '')} | resized to {new_qty}"
            touched = True
    if touched:
        _save_all_trades(trades)


def get_open_trades_by_symbol(symbol: str) -> list[dict]:
    return [t for t in _load_all_trades()
            if t.get("symbol") == symbol and t.get("status") == "open"]


def close_paper_trade(trade_id: str, exit_price: float, outcome: str) -> dict | None:
    trades = _load_all_trades()
    updated = None
    for t in trades:
        if t["trade_id"] == trade_id and t["status"] == "open":
            # Close on Alpaca (no-op if already closed by TP/SL bracket)
            try:
                close_position(t["symbol"])
            except Exception:
                pass
            entry = float(t["entry_price"])
            size = float(t["position_size"])
            direction = t["direction"]

            if direction == "long":
                pnl_usd = (exit_price - entry) * size
            else:
                pnl_usd = (entry - exit_price) * size

            pnl_pct = pnl_usd / (entry * size) * 100 if (entry * size) > 0 else 0

            # Fees (sell-side only)
            sale_value = exit_price * size
            sec_fee = sale_value * config.SEC_FEE_RATE
            finra_fee = min(size * config.FINRA_TAF_RATE, config.FINRA_TAF_MAX)
            fees_usd = round(sec_fee + finra_fee, 4)
            net_pnl = round(pnl_usd - fees_usd, 2)

            t.update({
                "status": "closed",
                "exit_price": round(exit_price, 4),
                "exit_timestamp": datetime.utcnow().isoformat(),
                "pnl_pct": round(pnl_pct, 4),
                "pnl_usd": round(pnl_usd, 2),
                "fees_usd": fees_usd,
                "net_pnl_usd": net_pnl,
                "notes": f"{t.get('notes', '')} | {outcome}",
            })
            updated = t

    if updated:
        _save_all_trades(trades)
    return updated


def _append_trade(trade: dict) -> None:
    exists = TRADES_FILE.exists() and TRADES_FILE.stat().st_size > 0
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow({k: trade.get(k, "") for k in FIELDNAMES})


def _load_all_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_all_trades(trades: list[dict]) -> None:
    with open(TRADES_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(trades)
