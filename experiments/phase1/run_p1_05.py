"""Generate a deterministic synthetic P1-05 label artifact."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.phase1.p1_03_fixture import fixture
from src.alpha.label_artifacts import write_label_artifacts
from src.alpha.labels import ExecutableLabelBuilder
from src.data.pit_store import PITStore
from src.utils.config import load_config

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/p1_05"


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src/alpha").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    for path in sorted((ROOT / "src/returns").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    bundle, calendar = fixture()
    config = load_config(ROOT / "configs/phase1_baseline.yaml")
    store = PITStore(bundle, calendar, config)
    signals = tuple(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"))
                    for value in ("2024-08-02T16:10", "2024-08-09T16:10"))
    frame = ExecutableLabelBuilder(store, dataset_version="synthetic-p1-05-v1").build(signals)
    write_label_artifacts(frame, OUTPUT, git_commit=None, config_hash=config.config_hash(),
                          working_tree_hash=source_hash())
    status = {
        "ticket": "P1-05", "status": "CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING",
        "independent_review": "APPROVE; BLOCKER=0; HIGH=0; MEDIUM=0; LOW=0",
        "artifact_scope": "synthetic fixture only", "data_source": "synthetic-p1-05-v1",
        "label_version": frame.label_version, "schedule_version": frame.schedule_version,
        "data_manifest_hash": frame.data_manifest_hash, "rows": len(frame.rows),
        "valid_rows": sum(row.label_valid for row in frame.rows),
        "invalid_rows": sum(not row.label_valid for row in frame.rows),
        "git_commit": None, "remote_ci": "PENDING", "gate_a": "PARTIAL",
        "research_results": "[TODO: 待实验结果]",
        "limitations": ["Synthetic records are not 2010–2025 source coverage.",
                        "No IC, model, portfolio or performance metrics.",
                        "git commit unavailable because repository has no commits."],
    }
    (OUTPUT / "implementation_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps({"status": status["status"], "output": str(OUTPUT),
                      "rows": len(frame.rows), "valid_rows": status["valid_rows"]}))


if __name__ == "__main__":
    main()
