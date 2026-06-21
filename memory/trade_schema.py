"""Canonical schema for memory/trades.csv.

Single source of truth for the trade journal columns. Every writer MUST use
TRADE_FIELDNAMES so the CSV stays consistent regardless of the code path that
produced it. Readers use csv.DictReader and adapt to the header automatically.
"""

TRADE_FIELDNAMES = [
    "trade_id", "timestamp", "symbol", "direction",
    "entry_price", "stop_loss", "take_profit",
    "position_size", "risk_pct", "risk_usd", "potential_usd",
    "status", "exit_price", "exit_timestamp", "pnl_pct", "pnl_usd",
    "fees_usd", "net_pnl_usd", "alpaca_order_id", "notes",
]
