import copy
import json

from conftest import et
from src.data.lineage import build_manifest
from src.data.quality import generate_report, write_report
from src.data.schemas import DataBundle

KWARGS = dict(as_of=et("2024-08-02T16:10"), dataset_version="synthetic-v1",
              ingested_at=et("2025-12-31T23:00"))


def test_quality_and_manifest_reproduce(payload, calendar, config, tmp_path):
    report, manifest = generate_report(payload, calendar, config, **KWARGS)
    assert report["status"] == "PASS"
    assert report["number_of_securities"] == 6
    assert report["ticker_changes"] == 1
    assert report["late_filings"] == 2
    assert report["missing_fundamental_values"] == 1
    assert report["missing_price_counts"] == dict.fromkeys(
        ["raw_open", "raw_high", "raw_low", "raw_close"], 1)
    assert report["missing_price_observations"] > 0
    assert report["records_rejected_for_timestamp_violations"] == 0
    write_report(report, manifest, tmp_path)
    first = (tmp_path / "data_quality_report.json").read_bytes()
    write_report(*generate_report(payload, calendar, config, **KWARGS), tmp_path)
    assert first == (tmp_path / "data_quality_report.json").read_bytes()
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest
    assert (tmp_path / "data_quality_report.md").exists()


def test_rejections_are_reported_not_silently_dropped(payload, calendar, config):
    payload["market"][0]["available_timestamp"] = "2024-07-03T17:00:00Z"  # 13:00 ET
    payload["market"].append(copy.deepcopy(payload["market"][1]))
    payload["memberships"][0]["effective_to"] = payload["memberships"][0]["effective_from"]
    payload["market"][1]["security_id"] = "ORPHAN"
    payload["fundamentals"][0]["available_timestamp"] = "2024-07-01T00:00:00Z"
    report, manifest = generate_report(payload, calendar, config, **KWARGS)
    assert report["status"] == manifest["validation_status"] == "FAIL"
    assert report["records_rejected_for_timestamp_violations"] == 2
    assert report["invalid_intervals"] == 1
    assert report["orphan_security_ids"] == 1
    assert report["schema_rejected_records"] == 2


def test_hash_changes_with_data_not_order(payload, calendar):
    bundle = DataBundle.model_validate(payload)
    baseline = build_manifest(bundle, calendar, "v1", KWARGS["ingested_at"])
    reversed_bundle = DataBundle.model_validate({k: list(reversed(v)) for k, v in payload.items()})
    assert build_manifest(reversed_bundle, calendar, "v1", KWARGS["ingested_at"]) == baseline
    payload["fundamentals"][0]["value"] = 42
    changed = build_manifest(DataBundle.model_validate(payload), calendar, "v1", KWARGS["ingested_at"])
    assert changed != baseline


def test_ticker_reversion_counts_both_transitions(payload, calendar, config):
    last = payload["securities"][3]
    last["valid_to"] = last["end_available_timestamp"] = "2024-01-01T00:00:00Z"
    reversion = dict(last)
    reversion.update(ticker="FB", valid_from="2024-01-01T00:00:00Z",
                     available_timestamp="2024-01-01T00:00:00Z",
                     valid_to=None, end_available_timestamp=None)
    payload["securities"].append(reversion)
    report, _ = generate_report(payload, calendar, config, **KWARGS)
    assert report["status"] == "PASS"
    assert report["ticker_changes"] == 2
