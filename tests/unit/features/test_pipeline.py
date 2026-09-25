"""Orchestration tests use explicitly artificial calculators, not financial feature formulas."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle
from src.features.artifacts import write_feature_artifacts
from src.features.pipeline import Computation, FeaturePipeline
from src.features.registry import (
    FEATURE_SET_VERSION, MISSING_FEATURES, RAW_FEATURES, FeatureRegistry, FeatureSpec,
)


def mock_registry():
    return FeatureRegistry(tuple(FeatureSpec(
        name=name, family="synthetic_mock_only", dtype="int8" if name in MISSING_FEATURES else "float64",
        definition="Synthetic orchestration test value; not a financial feature calculation",
        lookback="mock latest visible bar", required_sources=("market",),
        availability_rule="PIT", minimum_observations=1, unit="mock",
    ) for name in RAW_FEATURES + MISSING_FEATURES))


def mock_latest(context):
    if not context.market:
        return Computation(None, (), 0, "no_market_history")
    latest = context.market[-1]
    return Computation(latest.raw_close, (latest,), 1,
                       "missing_close" if latest.raw_close is None else None)


def prepare_store(payload, calendar, config):
    master = deepcopy(payload["securities"][4])
    master.update(security_id="SEC_SPY", ticker="SPY")
    payload["securities"].append(master)
    benchmark = deepcopy(payload["market"][0])
    benchmark["security_id"] = "SEC_SPY"
    payload["market"].append(benchmark)
    return PITStore(DataBundle.model_validate(payload), calendar, config)


def generate(store, calculators=None):
    return FeaturePipeline(store, mock_registry(), calculators or dict.fromkeys(RAW_FEATURES,
                           mock_latest), benchmark_security_id="SEC_SPY", dataset_version="mock-v1"
                           ).generate((et("2024-07-05T16:10"),))


def test_pipeline_keeps_missing_universe_and_binds_lineage(payload, calendar, config):
    frame = generate(prepare_store(payload, calendar, config))
    assert {r.security_id for r in frame.rows} == {"SEC123", "SEC_NEW", "SEC_GOOG", "SEC_GOOGL"}
    assert next(r for r in frame.rows if r.security_id == "SEC_GOOG").values[0].value is None
    assert all(v.available_timestamp <= r.signal_timestamp for r in frame.rows for v in r.values)
    assert frame.snapshots[0].benchmark_security_id == "SEC_SPY"


def test_pipeline_future_bar_invariance(payload, calendar, config):
    store = prepare_store(payload, calendar, config)
    full = generate(store)
    signal = et("2024-07-05T16:10")
    payload["market"] = [r for r in payload["market"]
                         if et(r["trade_date"] + "T16:05") <= signal]
    truncated = generate(PITStore(DataBundle.model_validate(payload), calendar, config))
    assert full.rows == truncated.rows
    assert full.inputs == truncated.inputs
    assert full.snapshots == truncated.snapshots
    assert full.data_manifest_hash != truncated.data_manifest_hash  # Honest archive provenance.


def test_pipeline_blocks_benchmark_in_non_beta_feature(payload, calendar, config):
    store = prepare_store(payload, calendar, config)
    def bad(context):
        return Computation(1., context.benchmark_market, len(context.benchmark_market))
    calculators = dict.fromkeys(RAW_FEATURES, mock_latest)
    calculators["ret_5d"] = bad
    with pytest.raises(ValueError, match="outside its PIT"):
        generate(store, calculators)


def test_registry_rejects_extra_target_or_wrong_version():
    registry = mock_registry()
    with pytest.raises(ValueError, match="whitelist"):
        FeatureRegistry(registry.entries + (replace(registry.entries[0], name="target"),))
    with pytest.raises(ValueError, match="unknown feature version"):
        registry.model_features("unknown")
    assert len(registry.model_features(FEATURE_SET_VERSION)) == 41


def test_artifacts_roundtrip_deterministically(payload, calendar, config, tmp_path):
    frame = generate(prepare_store(payload, calendar, config))
    kwargs = dict(git_commit=None, working_tree_hash="synthetic-code", working_tree_dirty=True)
    write_feature_artifacts(frame, mock_registry(), tmp_path, **kwargs)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    write_feature_artifacts(frame, mock_registry(), tmp_path, **kwargs)
    assert first == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    manifest = json.loads((tmp_path / "feature_manifest.json").read_text())
    assert manifest["git_commit"] is None
    assert manifest["data_manifest_hash"] == frame.data_manifest_hash
    assert manifest["row_count"] == 4
    assert "not a financial feature" in manifest["feature_definitions"][0]["definition"]


def test_artifact_writer_rejects_relabeled_definitions(payload, calendar, config, tmp_path):
    frame = generate(prepare_store(payload, calendar, config))
    registry = mock_registry()
    changed = FeatureRegistry((replace(registry.entries[0], definition="Different formula"),)
                              + registry.entries[1:])
    with pytest.raises(ValueError, match="does not match"):
        write_feature_artifacts(frame, changed, tmp_path, git_commit=None,
                                working_tree_hash="mock", working_tree_dirty=True)
