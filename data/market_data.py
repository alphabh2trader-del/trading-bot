import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()

_trading: TradingClient | None = None
_data: StockHistoricalDataClient | None = None


def _tc() -> TradingClient:
    global _trading
    if _trading is None:
        paper = os.getenv("TRADING_MODE", "paper") == "paper"
        _trading = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=paper,
        )
    return _trading


def _dc() -> StockHistoricalDataClient:
    global _data
    if _data is None:
        _data = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )
    return _data


def fetch_bars(symbol: str, timeframe: str, lookback_days: int = 365) -> pd.DataFrame:
    tf_map = {"1Day": TimeFrame.Day, "4Hour": TimeFrame(4, TimeFrameUnit.Hour)}
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf_map[timeframe],
        start=datetime.utcnow() - timedelta(days=lookback_days),
    )
    bars = _dc().get_stock_bars(req)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level=0)
    df.index = pd.to_datetime(df.index)
    df.columns = [c.lower() for c in df.columns]
    return df


def fetch_bars_safe(symbol: str, timeframe: str, timeout_sec: float = 1.0) -> pd.DataFrame | None:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fetch_bars, symbol, timeframe)
        try:
            return future.result(timeout=timeout_sec)
        except (FuturesTimeout, Exception):
            return None


def data_age_minutes(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return float("inf")
    last_bar = df.index[-1]
    if last_bar.tzinfo is None:
        last_bar = last_bar.tz_localize("UTC")
    now = datetime.utcnow().replace(tzinfo=last_bar.tzinfo)
    return (now - last_bar).total_seconds() / 60


def get_account() -> dict:
    acc = _tc().get_account()
    return {
        "equity": float(acc.equity),
        "cash": float(acc.cash),
        "buying_power": float(acc.buying_power),
    }


def get_live_quote(symbol: str) -> dict:
    req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quote = _dc().get_stock_latest_quote(req)[symbol]
    ask = float(quote.ask_price)
    bid = float(quote.bid_price)
    mid = (ask + bid) / 2 if (ask + bid) > 0 else ask
    spread_pct = (ask - bid) / mid * 100 if mid > 0 else 999.0
    return {"bid": bid, "ask": ask, "mid": mid, "spread_pct": spread_pct}
