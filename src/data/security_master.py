"""Internal security identity keys, independent of ticker history."""
from datetime import datetime

from src.data.schemas import SecurityMaster


def valid_security(row: SecurityMaster, timestamp: datetime) -> bool:
    return (row.available_timestamp <= timestamp and row.valid_from <= timestamp
            and (row.valid_to is None or timestamp < row.valid_to))
