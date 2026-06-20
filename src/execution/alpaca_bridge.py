import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

_trading_client: TradingClient | None = None
_data_client: StockHistoricalDataClient | None = None


def _get_trading_client() -> TradingClient:
    global _trading_client
    if _trading_client is None:
        paper = os.getenv("TRADING_MODE", "paper") == "paper"
        _trading_client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=paper,
        )
    return _trading_client


def _get_data_client() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )
    return _data_client


def get_account() -> dict:
    account = _get_trading_client().get_account()
    return {
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "portfolio_value": float(account.portfolio_value),
    }


def get_bars(symbol: str, timeframe: str, lookback_days: int = 365) -> pd.DataFrame:
    tf_map = {
        "1Day": TimeFrame.Day,
        "4Hour": TimeFrame.Hour,
        "1Hour": TimeFrame.Hour,
    }
    alpaca_tf = tf_map.get(timeframe, TimeFrame.Day)
    start = datetime.utcnow() - timedelta(days=lookback_days)

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=alpaca_tf,
        start=start,
    )
    bars = _get_data_client().get_stock_bars(request)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level=0)
    df.index = pd.to_datetime(df.index)
    df.columns = [c.lower() for c in df.columns]
    return df


def submit_market_order(
    symbol: str,
    qty: float,
    side: str,
) -> dict:
    order_side = OrderSide.BUY if side == "long" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=symbol,
        qty=round(qty, 2),
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )
    order = _get_trading_client().submit_order(request)
    return {"order_id": str(order.id), "status": str(order.status)}


def get_positions() -> list[dict]:
    positions = _get_trading_client().get_all_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry": float(p.avg_entry_price),
            "market_value": float(p.market_value),
            "unrealized_pnl": float(p.unrealized_pl),
        }
        for p in positions
    ]


def close_position(symbol: str) -> dict:
    result = _get_trading_client().close_position(symbol)
    return {"order_id": str(result.id), "status": str(result.status)}
