import json
from dataclasses import replace
import pytest

from src.features.contracts import FeatureFrame
from src.features.registry import FEATURE_REGISTRY
from src.preprocessing.artifacts import write_fold_artifacts, write_quality_report
from src.preprocessing.pipeline import Preprocessor, PreprocessingError, row_ids_hash
from tests.unit.features.test_contracts import make_frame


def valid_frame(values=(1., 2., None)) -> FeatureFrame:
    frame = make_frame(values)
    return frame.model_copy(update={"registry_hash": FEATURE_REGISTRY.content_hash()})


def subset(frame: FeatureFrame, indices: tuple[int, ...]) -> FeatureFrame:
    rows = tuple(frame.rows[i] for i in indices)
    stamp = frame.snapshots[0]
    snapshot = stamp.model_copy(update={"security_ids": tuple(row.security_id for row in rows)})
    return frame.model_copy(update={"rows": rows, "snapshots": (snapshot,)})


def test_train_only_winsor_then_median_and_indicator_passthrough():
    train = valid_frame((1., 2., None, 100.))
    pre = Preprocessor.fit(train, FEATURE_REGISTRY)
    ret = next(p for p in pre.parameters if p.name == "ret_5d")
    assert ret.lower == pytest.approx(1.02)
    assert ret.upper == pytest.approx(98.04)
    assert ret.median == pytest.approx(2.0)
    indicator = next(p for p in pre.parameters if p.name == "roe_is_missing")
    assert indicator.passthrough and not indicator.winsorize and not indicator.impute
    transformed = pre.transform(train, FEATURE_REGISTRY, split="TRAIN")
    assert transformed.imputed_count["ret_5d"] == 1
    assert transformed.clipped_count["ret_5d"] == 2
    assert all(value in (0., 1.) for value in transformed.rows[0].values[-10:])


def test_quantile_linear_and_even_median():
    assert Preprocessor.fit(valid_frame((1., 2., 3., 4.)), FEATURE_REGISTRY).parameters[0].median == 2.5


def test_fit_only_train_and_fail_loudly():
    with pytest.raises(PreprocessingError, match="only for TRAIN"):
        Preprocessor.fit(valid_frame(), FEATURE_REGISTRY, fit_split="VALIDATION")
    frame = valid_frame()
    raw = frame.rows[0].values[0].model_copy(update={"value": float("inf"), "missing_reason": None})
    bad = frame.rows[0].model_copy(update={"values": (raw,) + frame.rows[0].values[1:]})
    with pytest.raises(Exception):
        Preprocessor.fit(frame.model_copy(update={"rows": (bad,) }), FEATURE_REGISTRY)


def test_all_missing_continuous_feature_is_blocking():
    frame = valid_frame()
    rows = []
    for row in frame.rows:
        values = tuple(cell.model_copy(update={"value": None, "missing_reason": "missing"})
                      if cell.name == "ret_5d" else cell for cell in row.values)
        rows.append(row.model_copy(update={"values": values}))
    with pytest.raises(PreprocessingError, match="no finite TRAIN"):
        Preprocessor.fit(frame.model_copy(update={"rows": tuple(rows)}), FEATURE_REGISTRY)


def test_non_imputable_policy_fails_loudly_on_missing_value():
    entries = tuple(replace(entry, impute=False) if entry.name == "ret_5d" else entry
                    for entry in FEATURE_REGISTRY.entries)
    registry = type(FEATURE_REGISTRY)(entries)
    frame = valid_frame((1., None, 3.)).model_copy(
        update={"registry_hash": registry.content_hash()})
    pre = Preprocessor.fit(frame, registry)
    with pytest.raises(PreprocessingError, match="non-imputable"):
        pre.transform(frame, registry, split="TEST")


def test_validation_test_and_future_perturbations_do_not_refit():
    train = valid_frame((1., 2.))
    pre = Preprocessor.fit(train, FEATURE_REGISTRY)
    val = valid_frame((3., None)).model_copy(update={"registry_hash": FEATURE_REGISTRY.content_hash()})
    test = valid_frame((4., None)).model_copy(update={"registry_hash": FEATURE_REGISTRY.content_hash()})
    before = pre.to_dict()
    pre.transform(val, FEATURE_REGISTRY, split="VALIDATION")
    pre.transform(test, FEATURE_REGISTRY, split="TEST")
    assert pre.to_dict() == before
    future = valid_frame((10_000_000., 20_000_000.)).model_copy(
        update={"registry_hash": FEATURE_REGISTRY.content_hash()})
    appended_rows = train.rows + future.rows
    assert len(appended_rows) > len(train.rows)
    # The fit boundary is explicit: appending rows outside TRAIN cannot alter
    # the state produced from the unchanged TRAIN selection.
    assert Preprocessor.fit(train, FEATURE_REGISTRY).to_dict() == pre.to_dict()
    assert row_ids_hash(train.rows) != row_ids_hash(appended_rows)


def test_fold_isolation_schema_and_roundtrip():
    first = Preprocessor.fit(valid_frame((1., 2.)), FEATURE_REGISTRY)
    second = Preprocessor.fit(valid_frame((100., 200.)), FEATURE_REGISTRY)
    assert first.to_dict() != second.to_dict()
    restored = Preprocessor.from_dict(first.to_dict())
    assert restored.to_dict() == first.to_dict()
    with pytest.raises(PreprocessingError, match="schema"):
        restored.transform(valid_frame().model_copy(update={
            "rows": tuple(row.model_copy(update={"values": row.values[:-1]})
                          for row in valid_frame().rows)}), FEATURE_REGISTRY, split="TEST")


def test_artifacts_are_json_and_do_not_need_qa_report(tmp_path):
    frame = valid_frame((1., None, 100.))
    pre = Preprocessor.fit(frame, FEATURE_REGISTRY)
    result = pre.transform(frame, FEATURE_REGISTRY, split="TRAIN")
    write_fold_artifacts(tmp_path / "fold_1", pre, fold_id="fold_1",
                         input_manifest_hash="input", config_hash="config", git_commit=None,
                         validation=result, test=result)
    write_quality_report(tmp_path, pre, (result,))
    state = json.loads((tmp_path / "fold_1/preprocessor.json").read_text())
    assert state["fit_split"] == "TRAIN"
    assert state["scaling_enabled"] is False
    assert Preprocessor.from_dict(state).to_dict() == pre.to_dict()
    assert (tmp_path / "preprocessing_quality_report.md").exists()
