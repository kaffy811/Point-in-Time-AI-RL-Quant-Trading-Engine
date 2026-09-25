from datetime import datetime

import pytest

from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle
from src.data.validation import DataContractError


@pytest.mark.parametrize("dataset", ["securities", "memberships", "market", "fundamentals"])
def test_duplicate_canonical_records_fail(payload, calendar, config, dataset):
    payload[dataset].append(dict(payload[dataset][0]))
    with pytest.raises(DataContractError, match="duplicate"):
        PITStore(DataBundle.model_validate(payload), calendar, config)


@pytest.mark.parametrize("dataset", ["memberships", "market", "fundamentals"])
def test_orphan_ids_fail(payload, calendar, config, dataset):
    for row in payload[dataset]:
        row["security_id"] = "ORPHAN"
    with pytest.raises(DataContractError, match="orphan_security_id"):
        PITStore(DataBundle.model_validate(payload), calendar, config)


def test_invalid_snapshot_requests_fail(store):
    with pytest.raises(ValueError, match="timezone-aware"):
        store.snapshot(signal_timestamp=datetime(2024, 7, 5))
    with pytest.raises(ValueError, match="coverage"):
        store.snapshot(signal_timestamp=et("2026-01-01T16:10"))
    with pytest.raises(ValueError, match="universe"):
        store.snapshot(signal_timestamp=et("2024-07-05T16:10"), universe="today_sp500")


def test_missing_prices_never_shrink_universe(store):
    snapshot = store.snapshot(signal_timestamp=et("2024-07-05T16:10"))
    assert "SEC_GOOG" in snapshot.security_ids
    assert "SEC_GOOG" in snapshot.missing_market_security_ids


def test_stale_and_incomplete_prices_are_explicit(store):
    july5 = store.snapshot(signal_timestamp=et("2024-07-05T16:10"))
    assert "SEC_NEW" in july5.incomplete_market_security_ids
    july8 = store.snapshot(signal_timestamp=et("2024-07-08T16:10"))
    assert "SEC123" not in july8.missing_market_security_ids
    assert "SEC123" in july8.stale_market_security_ids
    assert "SEC123" in july8.security_ids
