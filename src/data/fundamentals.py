"""Revision resolution occurs only after applying both knowledge-time gates."""
from datetime import datetime

from src.data.schemas import FundamentalFact


def available_revisions(
    rows: tuple[FundamentalFact, ...], timestamp: datetime
) -> tuple[FundamentalFact, ...]:
    latest: dict[tuple[object, ...], FundamentalFact] = {}
    for row in rows:
        if row.available_timestamp <= timestamp and row.filing_accepted_at <= timestamp:
            key = row.observation_key()
            if key not in latest or row.available_timestamp > latest[key].available_timestamp:
                latest[key] = row
    return tuple(latest[key] for key in sorted(latest, key=str))
