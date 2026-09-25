import pytest
from pydantic import ValidationError

from src.data.pit_store import PITStore
from src.data.schemas import DataBundle, SecurityMaster
from src.data.validation import DataContractError
from conftest import et


def test_stable_identity_cannot_be_ticker(payload):
    row = payload["securities"][0]
    row["security_id"] = row["ticker"]
    with pytest.raises(ValidationError, match="internal stable ID"):
        SecurityMaster.model_validate(row)


def test_ticker_reuse_and_share_classes(store):
    early = store.snapshot(signal_timestamp=et("2014-01-03T16:10"))
    later = store.snapshot(signal_timestamp=et("2016-01-04T16:10"))
    assert "SEC_OLD" in early.security_ids
    assert "SEC_OLD" not in later.security_ids
    assert "SEC_REUSE" not in later.security_ids  # Same ticker is NOT same member.
    assert {"SEC_GOOG", "SEC_GOOGL"} <= set(later.security_ids)


def test_overlapping_master_fails(payload, calendar, config):
    payload["securities"][3]["valid_from"] = "2021-01-01T00:00:00Z"
    with pytest.raises(DataContractError, match="overlapping"):
        PITStore(DataBundle.model_validate(payload), calendar, config)


def test_future_master_blocks_universe_silencing(payload, calendar, config):
    payload["securities"][0]["available_timestamp"] = "2015-01-01T00:00:00Z"
    other = PITStore(DataBundle.model_validate(payload), calendar, config)
    with pytest.raises(ValueError, match="coverage gap"):
        other.snapshot(signal_timestamp=et("2014-01-03T16:10"))
