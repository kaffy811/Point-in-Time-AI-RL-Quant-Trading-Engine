"""Corporate-action-consistent executable open-to-open returns."""
from datetime import date

from src.data.schemas import MarketRecord


class ReturnError(ValueError):
    """The economic return cannot be constructed from canonical observations."""


def economic_total_return(records: tuple[MarketRecord, ...], entry_date: date,
                          exit_date: date, *, expected_dates: tuple[date, ...] | None = None) -> float:
    """Return a cash-inclusive return from entry open through exit open.

    ``split_factor`` is the number of shares received for one pre-event share;
    dividends are cash distributions per share. Events on intermediate and exit
    sessions are included. The primitive deliberately fails on missing prices.
    """
    ordered = {record.trade_date: record for record in records}
    entry = ordered.get(entry_date)
    exit_record = ordered.get(exit_date)
    if expected_dates is not None and any(day not in ordered for day in expected_dates):
        raise ReturnError("INCOMPLETE_MARKET_COVERAGE")
    if entry is None or entry.raw_open is None:
        raise ReturnError("MISSING_ENTRY_PRICE")
    if exit_record is None or exit_record.raw_open is None:
        raise ReturnError("MISSING_EXIT_VALUE")
    if entry_date >= exit_date or entry.raw_open <= 0 or exit_record.raw_open <= 0:
        raise ReturnError("INVALID_ENTRY_PRICE")
    shares = 1.0
    cash = 0.0
    for day in sorted(day for day in ordered if entry_date < day <= exit_date):
        row = ordered[day]
        if "unsupported" in row.corporate_action_source.lower():
            raise ReturnError("UNSUPPORTED_CORPORATE_ACTION")
        if row.split_factor <= 0:
            raise ReturnError("UNSUPPORTED_CORPORATE_ACTION")
        shares *= row.split_factor
        cash += row.dividend * shares
    entry_value = entry.raw_open
    exit_value = shares * exit_record.raw_open + cash
    return exit_value / entry_value - 1.0
