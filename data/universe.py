import pandas as pd
from datetime import datetime, timedelta

import config
from data.market_data import fetch_bars_safe, data_age_minutes, get_live_quote


def get_watchlist(state: dict) -> list[str]:
    return state.get("watchlist") or config.BASE_WATCHLIST


def build_watchlist(base: list[str] | None = None) -> list[str]:
    candidates = base or config.BASE_WATCHLIST
    liquid = []
    for symbol in candidates:
        try:
            df = fetch_bars_safe(symbol, "1Day", timeout_sec=2.0)
            if df is None or len(df) < 20:
                continue
            avg_volume = df["volume"].tail(30).mean()
            if avg_volume < config.MIN_AVG_VOLUME:
                continue
            quote = get_live_quote(symbol)
            if quote["spread_pct"] > config.MAX_SPREAD_PCT * 2:
                continue
            recent_rvol = df["volume"].iloc[-1] / avg_volume if avg_volume > 0 else 0
            if recent_rvol >= 1.0:  # active pre-market
                liquid.append(symbol)
        except Exception:
            continue
    return liquid or config.BASE_WATCHLIST
