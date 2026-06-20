"""
Trading Bot — Entry Point
Usage:
  python main.py --mode paper   (default)
  python main.py --mode live
"""
import argparse
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.memory.state import load_config, update_memory
from src.execution.alpaca_bridge import get_account, get_bars, get_positions
from src.strategy.swing_core import check_trend, check_entry_conditions
from src.risk.engine import can_open_trade, calculate_position_size, validate_rr
from src.skills.market_analysis import scan_watchlist
from src.skills.news_filtering import check_and_block, filter_report
from src.skills.sentiment import sentiment_report
from src.skills.telegram_notify import send_message, send_trade_alert, send_daily_summary

WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "JPM", "V", "UNH",
]

SCAN_INTERVAL_SECONDS = 60 * 60 * 4  # every 4 hours


def run_cycle(config: dict) -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n[{now}] Starting scan cycle...")

    # --- News filter ---
    report = filter_report()
    if report["blocked"]:
        print(f"  BLOCKED: {report['reason']}")
        send_message(f"Trading blocked: {report['reason']}")
        return

    # --- Sentiment filter ---
    sent = sentiment_report()
    print(f"  Sentiment score: {sent['score']:.2f} — {sent['reason']}")
    if sent["blocked"]:
        print(f"  SENTIMENT BLOCK: {sent['block_reason']}")
        send_message(sent["block_reason"])
        return

    # --- Account state ---
    account = get_account()
    equity = account["equity"]
    print(f"  Equity: ${equity:,.2f}")

    # --- Risk check ---
    positions = get_positions()
    daily_pnl_pct = sum(p["unrealized_pnl"] for p in positions) / equity * 100 if equity else 0
    total_drawdown_pct = 0.0  # computed from trades.csv in a full implementation
    allowed, reason = can_open_trade(daily_pnl_pct, total_drawdown_pct)
    if not allowed:
        print(f"  RISK BLOCK: {reason}")
        return

    # --- Scan watchlist ---
    print(f"  Scanning {len(WATCHLIST)} symbols...")
    signals = scan_watchlist(
        WATCHLIST,
        get_bars_fn=get_bars,
        target_rr=config["risk"]["target_rr_max"],
    )

    if not signals:
        print("  No signals found.")
        return

    for result in signals:
        if "error" in result:
            print(f"  {result['symbol']}: ERROR — {result['error']}")
            continue

        signal = result["signal"]
        if not signal:
            continue

        rr_ok, rr = validate_rr(signal.entry_price, signal.stop_loss, signal.take_profit)
        if not rr_ok:
            print(f"  {signal.symbol}: R:R {rr:.2f} too low, skipping.")
            continue

        size = calculate_position_size(equity, signal.entry_price, signal.stop_loss)
        print(f"  SIGNAL: {signal.direction.upper()} {signal.symbol} @ {signal.entry_price:.2f}  SL={signal.stop_loss:.2f}  TP={signal.take_profit:.2f}  size={size:.2f}")
        send_trade_alert(signal, equity, size)

        # Paper mode: log only; live mode would submit order
        if config["system"]["mode"] == "live":
            from src.execution.alpaca_bridge import submit_market_order
            order = submit_market_order(signal.symbol, size, signal.direction)
            print(f"  ORDER: {order}")
        else:
            print(f"  [PAPER] Would submit: {signal.direction} {size:.2f} {signal.symbol}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Swing Trading Bot")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    os.environ["TRADING_MODE"] = args.mode
    config = load_config()
    config["system"]["mode"] = args.mode

    print(f"=== TRADING BOT STARTED — MODE: {args.mode.upper()} ===")
    update_memory("last_boot", datetime.utcnow().isoformat())
    send_message(f"Trading bot started — mode: {args.mode.upper()}")

    if args.once:
        run_cycle(config)
        return

    while True:
        try:
            run_cycle(config)
        except KeyboardInterrupt:
            print("\nShutting down.")
            sys.exit(0)
        except Exception as e:
            print(f"  ERROR: {e}")
            send_message(f"Bot error: {e}")

        print(f"  Sleeping {SCAN_INTERVAL_SECONDS // 3600}h until next cycle...")
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
