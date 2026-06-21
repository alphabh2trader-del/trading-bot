"""
Trading Bot V2 — Entry Point
Usage: python runner.py --routine <name>
Routines: premarket | analysis | plan | open | midday | afternoon | review | weekly | reset
"""
import argparse
import importlib
import sys
from dotenv import load_dotenv

load_dotenv()

from state.daily_state import load_state, save_state
from risk.risk_engine import check_risk

ROUTINES = {
    "premarket": "routines.premarket",
    "analysis":  "routines.analysis",
    "plan":      "routines.plan",
    "open":      "routines.open",
    "midday":    "routines.midday",
    "afternoon": "routines.afternoon",
    "review":    "routines.review",
    "weekly":    "routines.weekly",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading Bot V2")
    parser.add_argument("--routine", required=True,
                        choices=list(ROUTINES.keys()) + ["reset"])
    args = parser.parse_args()

    if args.routine == "reset":
        state = load_state()
        state["kill_switch"] = "ARMED"
        save_state(state)
        print("Kill switch reset — system ARMED.")
        return

    state = load_state()
    # Exits immediately if the kill switch is LOCKED, the daily loss limit
    # (MAX_DRAWDOWN_PCT) is hit, or the account total drawdown crosses
    # MAX_TOTAL_DRAWDOWN_PCT.
    check_risk(state)

    module = importlib.import_module(ROUTINES[args.routine])
    module.run(state)

    save_state(state)


if __name__ == "__main__":
    main()
