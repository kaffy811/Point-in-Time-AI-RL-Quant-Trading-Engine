from datetime import date
from math import isnan

import pytest
from pydantic import ValidationError

from conftest import et
from src.features.contracts import (
    FeatureFrame, FeatureRow, FeatureValue, InputReference, SnapshotProvenance,
)
from src.features.quality import QA_WARNING, percentile, quality_report
from src.features.ranks import cross_sectional_ranks
from src.features.registry import MISSING_FEATURES, RAW_FEATURES


def make_frame(values=(1., 2., None)):
    stamp = et("2024-08-02T16:10")
    rows = []
    references = []
    for i, value in enumerate(values):
        references.append(InputReference(
            reference_id=f"bar{i}", dataset="market", security_id=f"SEC{i}",
            observation_date=date(2024, 8, 2), available_timestamp=stamp,
            source="synthetic", source_version="v1"))
        cells = tuple(FeatureValue(name=name, value=value, input_references=(f"bar{i}",),
                                   available_timestamp=stamp, missing_reason="missing" if value is None
                                   else None, observations_used=1) for name in RAW_FEATURES)
        cells += tuple(FeatureValue(name=name, value=int(value is None), input_references=(f"bar{i}",),
                                    available_timestamp=stamp, observations_used=1)
                       for name in MISSING_FEATURES)
        rows.append(FeatureRow(security_id=f"SEC{i}", signal_timestamp=stamp, values=cells))
    return FeatureFrame(data_manifest_hash="synthetic-manifest", registry_hash="mock-registry", rows=tuple(rows), inputs=tuple(references),
                        snapshots=(SnapshotProvenance(signal_timestamp=stamp,
                                   security_ids=tuple(r.security_id for r in rows),
                                   snapshot_hash="synthetic-snapshot"),))


def test_whitelist_and_missingness():
    frame = make_frame()
    assert len(frame.rows[0].values) == 41
    assert all(isnan(v) for v in frame.rows[2].model_values()[:31])
    assert frame.rows[2].model_values()[31:] == (1.,) * 10
    assert FeatureFrame.model_validate_json(frame.model_dump_json()) == frame


@pytest.mark.parametrize("name", ["label", "target", "future_return", "forward_5d"])
def test_no_forward_columns(name):
    with pytest.raises(ValidationError, match="non-whitelisted"):
        FeatureValue(name=name, value=1, input_references=(), available_timestamp=None,
                     observations_used=0)


@pytest.mark.parametrize("mutation", ["future", "universe", "omitted", "indicator", "inf"])
def test_invalid_frame_fails(mutation):
    raw = make_frame().model_dump(mode="json")
    if mutation == "future":
        raw["inputs"][0]["available_timestamp"] = "2024-08-03T00:00:00Z"
    elif mutation == "universe":
        raw["rows"][0]["security_id"] = "UNEXPECTED"
    elif mutation == "omitted":
        raw["rows"].pop()
    elif mutation == "indicator":
        raw["rows"][0]["values"][-1]["value"] = 1
    else:
        raw["rows"][0]["values"][0]["value"] = float("inf")
    with pytest.raises(ValidationError):
        FeatureFrame.model_validate(raw)


def test_stateless_rank_preserves_ties_missing_and_raw():
    frame = make_frame((2., 2., 4., None))
    before = frame.model_dump_json()
    ranks = cross_sectional_ranks(frame, ("ret_60d",))
    assert [r.value for r in ranks] == [.5, .5, 1., None]
    assert frame.model_dump_json() == before
    assert "ret_60d_xs_rank" not in [v.name for v in frame.rows[0].values]


def test_qa_is_diagnostic_only():
    frame = make_frame()
    report = quality_report(frame)
    assert report["warning"] == QA_WARNING
    assert report["feature_statistics"]["ret_5d"]["median"] == 1.5
    assert percentile([], .05) is None
    assert percentile([1.], .99) == 1.
    assert percentile([0., 10.], .05) == .5


def test_cross_security_lineage_rejected_on_reload():
    raw = make_frame().model_dump(mode="json")
    raw["rows"][1]["values"][0]["input_references"] = ["bar0"]
    with pytest.raises(ValidationError, match="cross-security"):
        FeatureFrame.model_validate(raw)
