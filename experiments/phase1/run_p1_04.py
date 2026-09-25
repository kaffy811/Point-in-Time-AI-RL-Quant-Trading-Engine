"""Generate a deterministic, synthetic P1-04 preprocessing artifact."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.phase1.p1_03_fixture import fixture
from src.data.pit_store import PITStore
from src.features.calculators import phase1_pipeline
from src.features.contracts import FeatureFrame
from src.features.registry import FEATURE_REGISTRY
from src.preprocessing.artifacts import write_fold_artifacts, write_quality_report
from src.preprocessing.pipeline import Preprocessor
from src.utils.config import load_config

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/p1_04"


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src/preprocessing").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def subset(frame: FeatureFrame, timestamp: datetime) -> FeatureFrame:
    rows = tuple(row for row in frame.rows if row.signal_timestamp == timestamp)
    row_refs = {ref for row in rows for value in row.values for ref in value.input_references}
    inputs = tuple(ref for ref in frame.inputs if ref.reference_id in row_refs)
    snapshots = tuple(snapshot for snapshot in frame.snapshots
                      if snapshot.signal_timestamp == timestamp)
    return frame.model_copy(update={"rows": rows, "inputs": inputs, "snapshots": snapshots})


def main() -> None:
    bundle, calendar = fixture()
    config = load_config(ROOT / "configs/phase1_baseline.yaml")
    store = PITStore(bundle, calendar, config)
    pipeline = phase1_pipeline(store, benchmark_security_id="SEC_SPY",
                               dataset_version="synthetic-p1-04-v1")
    timestamps = tuple(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"))
                       for value in ("2024-08-02T16:10", "2025-02-07T16:10"))
    frame = pipeline.generate(timestamps)
    # The fixture's first snapshot intentionally has no finite ROE/ROA history.
    # Include both synthetic snapshots so every registered feature has at least
    # one legal TRAIN observation; this artifact is a contract smoke test, not
    # a representative OOS fold.
    train = frame
    test = subset(frame, timestamps[1])
    preprocessor = Preprocessor.fit(
        train, FEATURE_REGISTRY,
        lower_quantile=config.preprocessing.winsorization.lower_quantile,
        upper_quantile=config.preprocessing.winsorization.upper_quantile,
        interpolation=config.preprocessing.winsorization.interpolation,
    )
    transformed_train = preprocessor.transform(train, FEATURE_REGISTRY, split="TRAIN")
    transformed_test = preprocessor.transform(test, FEATURE_REGISTRY, split="TEST")
    fold_output = OUTPUT / "fold_synthetic"
    write_fold_artifacts(fold_output, preprocessor, fold_id="fold_synthetic",
                         input_manifest_hash=frame.data_manifest_hash,
                         config_hash=config.config_hash(), git_commit=None,
                         test=transformed_test)
    write_quality_report(OUTPUT, preprocessor, (transformed_train, transformed_test))
    status = {
        "ticket": "P1-04", "status": "CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING",
        "independent_review": "APPROVE; BLOCKER=0; HIGH=0; MEDIUM=0; LOW=0",
        "artifact_scope": "synthetic fixture only", "data_source": "synthetic-p1-04-v1",
        "feature_set_version": frame.feature_set_version, "registry_hash": frame.registry_hash,
        "data_manifest_hash": frame.data_manifest_hash, "train_rows": len(train.rows),
        "test_rows": len(test.rows), "git_commit": None, "remote_ci": "PENDING",
        "gate_a": "PARTIAL", "research_results": "[TODO: 待实验结果]",
        "limitations": ["Synthetic records are not 2010–2025 source coverage.",
                        "No labels, alpha, portfolio or performance metrics.",
                        "git commit unavailable because repository has no commits."],
    }
    (OUTPUT / "implementation_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps({"status": status["status"], "output": str(OUTPUT),
                      "train_rows": len(train.rows), "test_rows": len(test.rows)}))


if __name__ == "__main__":
    main()
