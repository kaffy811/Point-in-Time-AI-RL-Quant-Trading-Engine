import pytest
from pydantic import ValidationError

from conftest import et
from src.data.lineage import build_manifest
from src.data.pit_store import PITStore
from src.data.schemas import Calendar, DataBundle, FundamentalFact, IndexMembership
from src.data.validation import DataContractError


def test_end_knowledge_must_be_explicit_and_not_retroactive(payload):
    row = payload["memberships"][0]
    row["end_available_timestamp"] = None
    with pytest.raises(ValidationError, match="knowledge timestamp"):
        IndexMembership.model_validate(row)
    row["end_available_timestamp"] = "2016-01-01T00:00:00Z"
    with pytest.raises(ValidationError, match="retrospective"):
        IndexMembership.model_validate(row)


def test_independent_duration_and_currency_observations(payload, calendar, config):
    payload["fundamentals"] = [payload["fundamentals"][0]]
    original = payload["fundamentals"][0]
    for start, unit in [("2024-01-01", "USD"), ("2024-04-01", "USD"),
                        ("2024-04-01", "EUR")]:
        payload["fundamentals"].append(dict(original, fiscal_period_start=start,
                                             period_type="duration", unit=unit))
    snapshot = PITStore(DataBundle.model_validate(payload), calendar, config).snapshot(
        signal_timestamp=et("2024-08-02T16:10"))
    assert len(snapshot.fundamentals) == 4


def test_revision_with_missing_predecessor_fails(payload, calendar, config):
    payload["fundamentals"] = [payload["fundamentals"][1]]
    with pytest.raises(DataContractError, match="invalid_revision"):
        PITStore(DataBundle.model_validate(payload), calendar, config)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_fact_values_rejected(payload, value):
    with pytest.raises(ValidationError):
        FundamentalFact.model_validate(dict(payload["fundamentals"][0], value=value))


def test_calendar_duplicate_and_unknown_coverage_rejected(calendar):
    raw = calendar.model_dump(mode="json")
    raw["sessions"].append(raw["sessions"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        Calendar.model_validate(raw)


def test_manifest_cannot_predate_ingestion(bundle, calendar):
    with pytest.raises(ValueError, match="precedes"):
        build_manifest(bundle, calendar, "v1", et("2024-01-01T00:00"))


def test_publicly_announced_future_end_is_visible(payload, calendar, config):
    payload["memberships"][0]["end_available_timestamp"] = "2014-01-01T00:00:00Z"
    store = PITStore(DataBundle.model_validate(payload), calendar, config)
    snapshot = store.snapshot(signal_timestamp=et("2014-01-03T16:10"))
    old = next(r for r in snapshot.memberships if r.security_id == "SEC_OLD")
    assert old.effective_to is not None
    assert old.end_available_timestamp <= snapshot.signal_timestamp
