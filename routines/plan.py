"""PLAN — 09:00 ET: confirm top 2 setups, arm the bot."""
from reporting.telegram import send_message


def run(state: dict) -> None:
    if state.get("news_blocked"):
        send_message("PLAN: News block active. No trades today.")
        state["setups"] = []
        return

    setups = state.get("setups", [])
    if not setups:
        send_message("PLAN: No setups available from analysis.")
        return

    lines = [f"<b>FINAL PLAN — 09:00 ET</b>", f"Regime: {state.get('regime', 'NORMAL')}", ""]
    for s in setups:
        direction = "LONG" if s["direction"] == "long" else "SHORT"
        lines.append(
            f"✅ {direction} {s['symbol']} | Entry ~${s['entry_price']} | "
            f"SL ${s['stop_loss']} | TP ${s['take_profit']} | "
            f"R:R {s['rr']} | Score {s['score']}"
        )

    lines += ["", "Bot is ARMED. Waiting for 9:35 execution window."]
    send_message("\n".join(lines))
