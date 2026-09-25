from datetime import date

import pytest
from pydantic import ValidationError

from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle, MarketRecord
from src.data.validation import DataContractError


def test_completed_bar_exact_boundary(store):
    at_close = store.snapshot(signal_timestamp=et("2024-07-05T16:00"))
    at_available = store.snapshot(signal_timestamp=et("2024-07-05T16:05"))
    assert all(r.trade_date < date(2024, 7, 5) for r in at_close.market)
    assert any(r.trade_date == date(2024, 7, 5) for r in at_available.market)


def test_early_close_holiday_and_dst(store):
    early = store.snapshot(signal_timestamp=et("2024-07-03T13:05"))
    assert any(r.trade_date == date(2024, 7, 3) for r in early.market)
    holiday = store.snapshot(signal_timestamp=et("2024-07-04T16:10"))
    assert all(r.trade_date != date(2024, 7, 4) for r in holiday.market)
    with pytest.raises(ValueError, match="holiday"):
        store.signal_timestamp(date(2024, 7, 4))
    assert store.signal_timestamp(date(2024, 3, 8)).utcoffset().total_seconds() == -18000
    assert store.signal_timestamp(date(2024, 3, 11)).utcoffset().total_seconds() == -14400
    assert store.signal_timestamp(date(2024, 7, 5)).hour == 16
    assert store.signal_timestamp(date(2024, 7, 5)).minute == 10


@pytest.mark.parametrize("change", [
    {"available_timestamp": "2024-07-05T20:00:00Z"},
    {"trade_date": "2024-07-04"},
])
def test_invalid_daily_timestamp_rejected(payload, calendar, config, change):
    payload["market"][1].update(change)
    with pytest.raises(DataContractError, match="timestamp_violation"):
        PITStore(DataBundle.model_validate(payload), calendar, config)


def test_raw_corporate_actions_preserved(store):
    rows = store.snapshot(signal_timestamp=et("2024-07-05T16:10")).market
    split = next(r for r in rows if r.split_factor == 2)
    assert split.open == split.raw_open == 50
    assert split.dividend == .5
    assert split.corporate_action_source_version == "actions-v1"
    assert any(r.raw_open is None for r in rows)


@pytest.mark.parametrize("field,value", [("open", 999), ("split_factor", 0),
                                         ("volume", -1), ("raw_open", float("nan"))])
def test_invalid_prices_fail(payload, field, value):
    row = payload["market"][0]
    row[field] = value
    with pytest.raises(ValidationError):
        MarketRecord.model_validate(row)
