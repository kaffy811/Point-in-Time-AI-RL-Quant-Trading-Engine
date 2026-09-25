"""Completed daily bar availability; explicit calendar handles holidays/early closes."""
from datetime import datetime, timedelta

from src.data.schemas import Calendar, MarketRecord


def completed_bar_floor(row: MarketRecord, calendar: Calendar, delay_minutes: int) -> datetime:
    session = calendar.session(row.trade_date)
    if session is None:
        raise ValueError("timestamp violation: market record on a non-session date")
    return session.close_timestamp + timedelta(minutes=delay_minutes)
