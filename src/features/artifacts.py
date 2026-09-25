"""Serialize existing validated features and diagnostic-only QA; no dataset reads."""
import json
from dataclasses import asdict
from pathlib import Path

from src.data.lineage import content_hash
from src.features.contracts import FeatureFrame
from src.features.quality import QA_WARNING, quality_report
from src.features.registry import FeatureRegistry


def write_feature_artifacts(
    frame: FeatureFrame, registry: FeatureRegistry, output: Path, *,
    git_commit: str | None, working_tree_hash: str, working_tree_dirty: bool,
) -> None:
    """git_commit=None explicitly represents an unborn repo, never a fabricated SHA."""
    if registry.content_hash() != frame.registry_hash:
        raise ValueError("artifact registry does not match the generated feature definitions")
    output.mkdir(parents=True, exist_ok=True)
    definitions = [asdict(entry) for entry in registry.entries]
    report = quality_report(frame)
    dates = sorted(s.signal_timestamp.isoformat() for s in frame.snapshots)
    statistics = report["feature_statistics"]
    manifest = {
        "feature_set_version": frame.feature_set_version,
        "data_manifest_hash": frame.data_manifest_hash,
        "git_commit": git_commit, "working_tree_hash": working_tree_hash,
        "working_tree_dirty": working_tree_dirty,
        "signal_timestamp_start": dates[0] if dates else None,
        "signal_timestamp_end": dates[-1] if dates else None,
        "feature_definitions": definitions, "registry_hash": content_hash(definitions),
        "feature_frame_hash": content_hash(frame.model_dump(mode="json")),
        "row_count": len(frame.rows), "security_count": report["security_count"],
        "quality_statistics": statistics, "inf_count": 0, "timestamp_violations": 0,
        "diagnostic_warning": QA_WARNING,
    }
    outputs = {
        "feature_manifest.json": manifest,
        "feature_schema.json": {"feature_set_version": frame.feature_set_version,
                                "model_features": registry.model_features(),
                                "definitions": definitions,
                                "wire_missing_value": "null", "model_missing_value": "NaN",
                                "json_schema": FeatureFrame.model_json_schema()},
        "feature_frame.json": frame.model_dump(mode="json"),
        "feature_quality_report.json": report,
    }
    for filename, value in outputs.items():
        (output / filename).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
                                      + "\n", encoding="utf-8")
    lines = ["# P1-03 Feature Quality Report", "", QA_WARNING, "",
             f"Rows: {len(frame.rows)}; securities: {report['security_count']}; "
             f"signals: {report['signal_count']}.", "",
             "FeatureFrame validation rejected any nonfinite values or timestamp violations.", "",
             "| Feature | Non-null % | Median | p01 | p05 | p95 | p99 | Min | Max | Inf |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    assert isinstance(statistics, dict)
    for name, stats in statistics.items():
        lines.append("| " + " | ".join([name] + [str(stats[key]) for key in
                     ("non_null_pct", "median", "p01", "p05", "p95", "p99", "min", "max",
                      "inf_count")]) + " |")
    lines += ["", "## Missingness / history sufficiency", ""]
    for name, stats in statistics.items():
        lines.append(f"- {name}: {json.dumps(stats['missing_reasons'], sort_keys=True)}")
    lines += ["", "No alpha prediction, future label, portfolio or performance evaluation.",
              "Research results: [TODO: 待实验结果]", ""]
    (output / "feature_quality_report.md").write_text("\n".join(lines), encoding="utf-8")
