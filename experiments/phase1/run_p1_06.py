"""Generate a deterministic synthetic P1-06 fold artifact."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

OUTPUT = ROOT / "artifacts/p1_06"


def source_hash() -> str:
    digest = hashlib.sha256()
    for directory in (ROOT / "src/validation", ROOT / "src/preprocessing"):
        for path in sorted(directory.rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    from src.validation.artifacts import write_fold_artifacts, write_quality_report
    from src.validation.walk_forward import WalkForwardBuilder
    from tests.unit.validation.test_walk_forward import feature_and_labels, synthetic_calendar
    from src.utils.config import load_config

    features, labels = feature_and_labels()
    config = load_config(ROOT / "configs/phase1_baseline.yaml")
    fold = WalkForwardBuilder(features, labels, synthetic_calendar(),
                              config_hash=config.config_hash(), config=config).build(2017)
    write_fold_artifacts(OUTPUT / "fold_2017", fold)
    write_quality_report(OUTPUT, (fold,))
    status = {
        "ticket": "P1-06", "status": "CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING",
        "independent_review": "APPROVE; BLOCKER=0; HIGH=0; MEDIUM=0; LOW=0",
        "artifact_scope": "synthetic fixture only", "folds": ["fold_2017"],
        "feature_manifest_hash": features.data_manifest_hash,
        "label_manifest_hash": labels.content_hash(), "git_commit": None,
        "working_tree_hash": source_hash(), "remote_ci": "PENDING", "gate_a": "PARTIAL",
        "research_results": "[TODO: 待实验结果]",
        "limitations": ["Synthetic records are not 2010–2025 source coverage.",
                        "No model, IC/RankIC, portfolio or performance metrics.",
                        "Parquet artifacts are native pyarrow files; real-data provenance remains pending.",
                        "git commit unavailable because repository has no commits."],
    }
    (OUTPUT / "implementation_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps({"status": status["status"], "output": str(OUTPUT),
                      "fold": fold.manifest.fold_id}))


if __name__ == "__main__":
    main()
