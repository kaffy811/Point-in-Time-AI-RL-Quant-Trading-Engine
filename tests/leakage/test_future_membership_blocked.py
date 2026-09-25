from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle


def test_survivorship_fixture(store):
    past = store.snapshot(signal_timestamp=et("2014-01-03T16:10"))
    later = store.snapshot(signal_timestamp=et("2016-01-04T16:10"))
    assert "SEC_OLD" in past.security_ids and "SEC_NEW" not in past.security_ids
    assert "SEC_NEW" in later.security_ids and "SEC_OLD" not in later.security_ids


def test_effective_but_not_yet_known_membership_hidden(payload, calendar, config):
    payload["memberships"][1]["available_timestamp"] = "2020-01-01T00:00:00Z"
    store = PITStore(DataBundle.model_validate(payload), calendar, config)
    assert "SEC_NEW" not in store.snapshot(signal_timestamp=et("2016-01-04T16:10")).security_ids
