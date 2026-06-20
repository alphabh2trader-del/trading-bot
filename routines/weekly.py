"""WEEKLY — Saturday 10:00 ET: full weekly report to Telegram + deep adaptive review."""
from reporting.weekly_report import generate_and_send
from reporting.telegram import send_message
from memory.adaptive import run_adaptive_learning


def run(state: dict) -> None:
    send_message("Generating weekly review...")
    generate_and_send()
    run_adaptive_learning(state, deep=True)
