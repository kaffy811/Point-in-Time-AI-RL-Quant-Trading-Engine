"""Generate deterministic synthetic P1-03 feature artifacts; no real data or results."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.phase1.p1_03_fixture import fixture
from src.data.pit_store import PITStore
from src.features.artifacts import write_feature_artifacts
from src.features.calculators import phase1_pipeline
from src.features.registry import FEATURE_REGISTRY
from src.utils.config import load_config

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/p1_03"


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src/features").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    bundle, calendar = fixture()
    config = load_config(ROOT / "configs/phase1_baseline.yaml")
    store = PITStore(bundle, calendar, config)
    pipeline = phase1_pipeline(store, benchmark_security_id="SEC_SPY", dataset_version="synthetic-p1-03-v1")
    timestamps = tuple(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"))
                       for value in ("2024-08-02T16:10", "2025-02-07T16:10"))
    frame = pipeline.generate(timestamps)
    write_feature_artifacts(frame, FEATURE_REGISTRY, OUTPUT, git_commit=None,
                            working_tree_hash=source_hash(), working_tree_dirty=True)
    status = {
        "ticket": "P1-03", "status": "IMPLEMENTED / INCOMPLETE — NOT YET CONDITIONAL PASS",
        "artifact_scope": "synthetic fixture only", "data_source": "synthetic-p1-03-v1",
        "feature_set_version": frame.feature_set_version, "registry_hash": frame.registry_hash,
        "data_manifest_hash": frame.data_manifest_hash, "rows": len(frame.rows),
        "signals": len(frame.snapshots), "security_count": len(frame.snapshots[0].security_ids),
        "git_commit": None, "remote_ci": "PENDING", "gate_a": "PARTIAL",
        "research_results": "[TODO: 待实验结果]",
        "limitations": ["Synthetic records are not 2010–2025 source coverage.",
                        "No labels, alpha, portfolio or performance metrics.",
                        "git commit unavailable because repository has no commits."],
    }
    (OUTPUT / "implementation_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps({"status": status["status"], "output": str(OUTPUT), "rows": len(frame.rows)}))


if __name__ == "__main__":
    main()
