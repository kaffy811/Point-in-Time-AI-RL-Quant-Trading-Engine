import pytest
from pydantic import ValidationError

from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle, FundamentalFact


def test_weekend_revision_visible_after_publication(store):
    friday = store.snapshot(signal_timestamp=et("2024-08-02T17:00"))
    saturday = store.snapshot(signal_timestamp=et("2024-08-03T11:00"))
    monday = store.snapshot(signal_timestamp=et("2024-08-05T16:10"))
    def assets(s):
        return next(r for r in s.fundamentals if r.fact_name == "us-gaap:Assets")
    assert assets(friday).value == 12
    assert assets(saturday).value == assets(monday).value == 13
    assert any(r.value is None for r in monday.fundamentals)


@pytest.mark.parametrize("change", [
    {"available_timestamp": "2024-08-01T00:00:00Z"},
    {"filing_accepted_at": "2024-08-02T15:00:00"},
    {"period_type": "duration"},
])
def test_bad_fundamental_times(payload, change):
    row = payload["fundamentals"][0]
    row.update(change)
    with pytest.raises(ValidationError):
        FundamentalFact.model_validate(row)


@pytest.mark.parametrize("change", [
    {"supersedes_revision_id": None},
    {"supersedes_revision_id": "unknown"},
    {"revision_id": "r1"},
    {"available_timestamp": "2024-08-03T15:00:00Z"},
])
def test_revision_ambiguity_fails(payload, calendar, config, change):
    payload["fundamentals"][1].update(change)
    with pytest.raises(ValueError):
        PITStore(DataBundle.model_validate(payload), calendar, config)
