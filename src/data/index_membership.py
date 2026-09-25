"""Membership is left-closed, right-open, and knowledge-time filtered."""
from datetime import datetime

from src.data.schemas import IndexMembership


def valid_membership(row: IndexMembership, timestamp: datetime) -> bool:
    return (row.available_timestamp <= timestamp and row.effective_from <= timestamp
            and (row.effective_to is None or timestamp < row.effective_to))
