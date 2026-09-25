import pytest
from pydantic import ValidationError

from conftest import et
from src.data.schemas import IndexMembership


def test_exact_membership_boundary(store):
    before = store.snapshot(signal_timestamp=et("2015-06-30T23:59:59"))
    after = store.snapshot(signal_timestamp=et("2015-07-01T00:00:00"))
    assert "SEC_OLD" in before.security_ids and "SEC_NEW" not in before.security_ids
    assert "SEC_NEW" in after.security_ids and "SEC_OLD" not in after.security_ids
    for row in after.memberships:
        assert row.effective_from <= after.signal_timestamp
        assert row.effective_to is None or after.signal_timestamp < row.effective_to


def test_invalid_interval(payload):
    row = payload["memberships"][0]
    row["effective_to"] = row["effective_from"]
    with pytest.raises(ValidationError, match="invalid interval"):
        IndexMembership.model_validate(row)


def test_unannounced_end_hidden(store):
    snapshot = store.snapshot(signal_timestamp=et("2014-01-03T16:10"))
    old = next(r for r in snapshot.memberships if r.security_id == "SEC_OLD")
    assert old.effective_to is None and old.end_available_timestamp is None
