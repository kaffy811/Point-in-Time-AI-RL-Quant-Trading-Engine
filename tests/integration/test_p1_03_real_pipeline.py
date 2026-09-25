from conftest import et
from experiments.phase1.p1_03_fixture import fixture
from src.data.pit_store import PITStore
from src.features.artifacts import write_feature_artifacts
from src.features.calculators import phase1_pipeline
from src.features.registry import FEATURE_REGISTRY
from src.utils.config import load_config


def build(payload_bundle=None):
    bundle, calendar = fixture() if payload_bundle is None else payload_bundle
    config = load_config("configs/phase1_baseline.yaml")
    store = PITStore(bundle, calendar, config)
    pipeline = phase1_pipeline(store, benchmark_security_id="SEC_SPY", dataset_version="synthetic-p1-03-v1")
    stamp = et("2024-08-02T16:10")
    return pipeline, stamp


def test_actual_feature_future_data_invariance():
    pipeline, stamp = build()
    baseline = pipeline.generate((stamp,))
    bundle, calendar = fixture()
    changed_market = bundle.market[:-1] + (bundle.market[-1].model_copy(update={"raw_close": 9999.,
        "close": 9999., "raw_open": 9999., "open": 9999., "raw_high": 9999., "high": 9999.,
        "raw_low": 9999., "low": 9999.}),)
    altered = bundle.model_copy(update={"market": changed_market})
    changed_pipeline, _ = build((altered, calendar))
    changed = changed_pipeline.generate((stamp,))
    assert baseline.rows == changed.rows
    assert baseline.snapshots == changed.snapshots


def test_actual_feature_revision_invariance_before_amendment():
    pipeline, stamp = build()
    before = pipeline.generate((stamp,))
    bundle, calendar = fixture()
    # Changing a revision whose availability is after the signal cannot alter the earlier snapshot.
    facts = tuple(row.model_copy(update={"value": 999.}) if row.revision_id.endswith(":r2") else row
                     for row in bundle.fundamentals)
    altered = bundle.model_copy(update={"fundamentals": facts})
    changed_pipeline, _ = build((altered, calendar))
    changed = changed_pipeline.generate((stamp,))
    assert before.rows == changed.rows


def test_later_amendment_changes_only_after_availability():
    pipeline, _ = build()
    old = pipeline.generate((et("2025-01-19T16:10"),))
    new = pipeline.generate((et("2025-01-21T16:10"),))
    assert old.rows != new.rows


def test_real_feature_artifacts_are_complete(tmp_path):
    pipeline, stamp = build()
    frame = pipeline.generate((stamp,))
    write_feature_artifacts(frame, FEATURE_REGISTRY, tmp_path,
                            git_commit=None, working_tree_hash="synthetic", working_tree_dirty=True)
    for name in ("feature_manifest.json", "feature_schema.json", "feature_quality_report.md"):
        assert (tmp_path / name).exists()
