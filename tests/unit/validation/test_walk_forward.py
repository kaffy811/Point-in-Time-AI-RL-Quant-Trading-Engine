from datetime import date, datetime, time, timezone

import pytest
from zoneinfo import ZoneInfo

from src.alpha.labels import LABEL_VERSION, SCHEDULE_VERSION, LabelFrame, LabelRow
from src.data.schemas import Calendar, Session
from src.features.contracts import FeatureFrame, SnapshotProvenance
from src.features.registry import FEATURE_REGISTRY
from src.validation.walk_forward import WalkForwardBuilder, WalkForwardError
from tests.unit.features.test_contracts import make_frame

NY = ZoneInfo("America/New_York")


def synthetic_calendar() -> Calendar:
    sessions = []
    for year in range(2010, 2026):
        for month, day in ((1, 2), (1, 9), (1, 16), (1, 23), (1, 30),
                           (12, 20), (12, 27)):
            trade = date(year, month, day)
            opening = datetime.combine(trade, time(9, 30), NY)
            closing = datetime.combine(trade, time(16, 0), NY)
            sessions.append(Session(trade_date=trade, open_timestamp=opening,
                                    close_timestamp=closing))
    return Calendar(source="synthetic", source_version="v1", coverage_start=date(2010, 1, 1),
                    coverage_end=date(2025, 12, 31), sessions=tuple(sessions))


def feature_and_labels() -> tuple[FeatureFrame, LabelFrame]:
    base = make_frame((1., 2., 3.)).model_copy(
        update={"registry_hash": FEATURE_REGISTRY.content_hash(), "data_manifest_hash": "m"})
    old = datetime(2010, 1, 2, tzinfo=timezone.utc)
    inputs = tuple(ref.model_copy(update={"available_timestamp": old}) for ref in base.inputs)
    rows = []
    snapshots = []
    labels = []
    for year, label_end in ((2015, "2015-12-27T16:00:00Z"),
                            (2016, "2016-12-27T16:00:00Z"),
                            (2017, "2017-12-27T16:00:00Z")):
        stamp = datetime(year, 12, 20, 16, 10, tzinfo=NY)
        for row in base.rows:
            values = tuple(cell.model_copy(update={"available_timestamp": old})
                           for cell in row.values)
            changed = row.model_copy(update={"signal_timestamp": stamp, "values": values})
            rows.append(changed)
            exit_time = datetime.fromisoformat(label_end.replace("Z", "+00:00"))
            labels.append(LabelRow(row.security_id, stamp, stamp, exit_time, exit_time,
                                   5, .01, .005, .005, True, None,
                                   LABEL_VERSION, "m", SCHEDULE_VERSION))
        snapshots.append(SnapshotProvenance(signal_timestamp=stamp,
                                            security_ids=tuple(row.security_id for row in base.rows),
                                            snapshot_hash=f"s-{year}"))
    frame = base.model_copy(update={"rows": tuple(rows), "inputs": inputs,
                                   "snapshots": tuple(snapshots)})
    return frame, LabelFrame(tuple(labels), LABEL_VERSION, SCHEDULE_VERSION, "m")


def test_actual_label_end_boundary_is_purged():
    features, labels = feature_and_labels()
    fold = WalkForwardBuilder(features, labels, synthetic_calendar()).build(2017)
    assert fold.manifest.validation_effective_start is not None
    assert fold.manifest.train_final_count == 3
    assert fold.manifest.validation_final_count == 3
    assert fold.manifest.test_final_count == 3
    assert fold.manifest.train_purged_count == 0


def test_future_test_year_is_reserved():
    features, labels = feature_and_labels()
    with pytest.raises(WalkForwardError, match="2017 through 2025"):
        WalkForwardBuilder(features, labels, synthetic_calendar()).build(2026)


def test_label_end_equal_to_downstream_boundary_is_purged():
    features, labels = feature_and_labels()
    boundary = datetime(2017, 12, 20, 21, 10, tzinfo=timezone.utc)
    changed = tuple(row if row.signal_timestamp.year != 2016 else row.__class__(
        **{**row.__dict__, "exit_execution_timestamp": boundary,
           "label_end_timestamp": boundary}) for row in labels.rows)
    fold = WalkForwardBuilder(features, LabelFrame(changed, labels.label_version,
                                                   labels.schedule_version, labels.data_manifest_hash),
                              synthetic_calendar()).build(2017)
    assert fold.manifest.validation_final_count == 0
    assert fold.manifest.validation_purged_count == 3


def test_missing_and_malformed_labels_fail_loudly():
    features, labels = feature_and_labels()
    with pytest.raises(WalkForwardError, match="MISSING_LABEL_RECORD"):
        WalkForwardBuilder(features, LabelFrame(labels.rows[:-1], labels.label_version,
                                                labels.schedule_version, labels.data_manifest_hash),
                           synthetic_calendar()).build(2017)
    malformed = tuple(row if row.signal_timestamp.year != 2017 else row.__class__(
        **{**row.__dict__, "label_end_timestamp": None}) for row in labels.rows)
    with pytest.raises(WalkForwardError, match="incomplete execution interval"):
        WalkForwardBuilder(features, LabelFrame(malformed, labels.label_version,
                                                labels.schedule_version, labels.data_manifest_hash),
                           synthetic_calendar()).build(2017)


def test_future_label_append_cannot_change_prior_fold():
    features, labels = feature_and_labels()
    baseline = WalkForwardBuilder(features, labels, synthetic_calendar()).build(2017)
    future = labels.rows[-1].__class__(**{**labels.rows[-1].__dict__,
                                           "signal_timestamp": datetime(2018, 12, 20,
                                                                         16, 10, tzinfo=NY)})
    extended = LabelFrame(labels.rows + (future,), labels.label_version,
                          labels.schedule_version, labels.data_manifest_hash)
    changed = WalkForwardBuilder(features, extended, synthetic_calendar()).build(2017)
    current = changed.manifest.to_dict()
    original = baseline.manifest.to_dict()
    assert current | {"label_manifest_hash": original["label_manifest_hash"]} == original
