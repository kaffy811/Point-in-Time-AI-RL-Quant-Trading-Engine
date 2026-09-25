"""Artifacts and diagnostic report for executable labels."""
import json
from pathlib import Path
from statistics import mean, pstdev

from src.alpha.labels import LabelFrame


def write_label_artifacts(frame: LabelFrame, output: Path, *, git_commit: str | None,
                          config_hash: str, working_tree_hash: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    valid = [row for row in frame.rows if row.label_valid and row.target_excess_return is not None]
    invalid = [row for row in frame.rows if not row.label_valid]
    values = [row.target_excess_return for row in valid if row.target_excess_return is not None]
    manifest = {
        "label_version": frame.label_version,
        "schedule_version": frame.schedule_version,
        "data_manifest_hash": frame.data_manifest_hash,
        "git_commit": git_commit,
        "working_tree_hash": working_tree_hash,
        "config_hash": config_hash,
        "row_count": len(frame.rows),
        "valid_row_count": len(valid),
        "invalid_row_count": len(invalid),
        "label_frame_hash": frame.content_hash(),
        "is_forward_looking": frame.is_forward_looking,
    }
    schema = {
        "required_columns": [
            "security_id", "signal_timestamp", "entry_execution_timestamp",
            "exit_execution_timestamp", "label_end_timestamp", "holding_session_count",
            "security_total_return", "benchmark_total_return", "target_excess_return",
            "label_valid", "invalid_reason", "label_version", "data_manifest_hash",
            "schedule_version",
        ],
        "target_definition": "security_total_return - benchmark_total_return",
        "future_interval": "[entry_execution_timestamp, label_end_timestamp]",
        "holding_session_count": "elapsed trading-session intervals; endpoint count minus one",
        "no_imputation": True,
    }
    (output / "label_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "label_schema.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    (output / "labels.json").write_text(
        json.dumps(frame.to_dict(), indent=2, sort_keys=True, default=str) + "\n")
    reasons: dict[str, int] = {}
    for row in invalid:
        reasons[row.invalid_reason or "UNKNOWN"] = reasons.get(row.invalid_reason or "UNKNOWN", 0) + 1
    stats = {"mean": mean(values), "std": pstdev(values), "min": min(values), "max": max(values)} \
        if values else {}
    lines = ["# P1-05 Label Quality Report", "",
             "Labels are intentionally forward-looking and are never imputed.", "",
             f"Rows: {len(frame.rows)}; valid: {len(valid)}; invalid: {len(invalid)}.", "",
             f"Invalid reasons: {json.dumps(reasons, sort_keys=True)}", "",
             f"Target diagnostics (read-only): {json.dumps(stats, sort_keys=True)}", "",
             "FeatureFrame is physically separate; no feature or preprocessing artifact is read.",
             "Research results: [TODO: 待实验结果]", ""]
    (output / "label_quality_report.md").write_text("\n".join(lines))
