from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle


def test_amendment_does_not_backfill(store, payload, calendar, config):
    signal = et("2024-08-02T16:10")
    original = store.snapshot(signal_timestamp=signal)
    asset = next(r for r in original.fundamentals if r.fact_name == "us-gaap:Assets")
    assert asset.value == 10 and asset.revision_id == "r1"
    payload["fundamentals"][2]["value"] = 999999
    changed = PITStore(DataBundle.model_validate(payload), calendar, config)
    assert changed.snapshot(signal_timestamp=signal) == original


def test_vendor_availability_after_filing_is_binding(payload, calendar, config):
    payload["fundamentals"] = [payload["fundamentals"][0]]
    payload["fundamentals"][0]["available_timestamp"] = "2024-08-05T20:00:00Z"
    store = PITStore(DataBundle.model_validate(payload), calendar, config)
    assert not store.snapshot(signal_timestamp=et("2024-08-02T16:10")).fundamentals
