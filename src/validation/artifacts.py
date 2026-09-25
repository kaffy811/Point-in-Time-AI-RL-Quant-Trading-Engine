"""Auditable walk-forward fold artifacts."""
import json
from pathlib import Path
from typing import Any, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from src.validation.walk_forward import FoldOutput, SplitName


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd", write_statistics=True)


def write_fold_artifacts(output: Path, fold: FoldOutput) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "split_manifest.json").write_text(
        json.dumps(fold.manifest.to_dict(), indent=2, sort_keys=True, default=str) + "\n")
    counts = fold.manifest.to_dict()
    (output / "sample_counts.json").write_text(json.dumps({key: value for key, value in counts.items()
                                                             if key.endswith("count")},
                                                            indent=2, sort_keys=True) + "\n")
    purge = {
        "train_purged_count": fold.manifest.train_purged_count,
        "validation_purged_count": fold.manifest.validation_purged_count,
        "rule": "label_end_timestamp < downstream_effective_start",
    }
    embargo = {
        "sessions": fold.manifest.embargo_sessions,
        "validation": [day.isoformat() for day in fold.manifest.validation_embargoed_sessions],
        "test": [day.isoformat() for day in fold.manifest.test_embargoed_sessions],
    }
    (output / "purge_report.json").write_text(json.dumps(purge, indent=2, sort_keys=True) + "\n")
    (output / "embargo_report.json").write_text(json.dumps(embargo, indent=2, sort_keys=True) + "\n")
    preprocessing = output / "preprocessing"
    preprocessing.mkdir(exist_ok=True)
    (preprocessing / "preprocessor.json").write_text(
        json.dumps(fold.preprocessor.to_dict(), indent=2, sort_keys=True, default=str) + "\n")
    for split, labels in (("train", fold.labels["TRAIN"]),
                          ("validation", fold.labels["VALIDATION"]),
                          ("test", fold.labels["TEST"])):
        split_name = cast(SplitName, split.upper())
        _write_parquet(output / f"X_{split}.parquet", [
            {"security_id": row.security_id, "signal_timestamp": row.signal_timestamp,
             **dict(zip(fold.preprocessor.feature_order, row.values))}
            for row in fold.transformed[split_name].rows])
        _write_parquet(output / f"y_{split}.parquet", [row.__dict__ for row in labels])


def write_quality_report(output: Path, folds: tuple[FoldOutput, ...]) -> None:
    lines = ["# P1-06 Walk-Forward Quality Report", "",
             "Synthetic/local contract artifact; not real-data coverage.", "",
             "| Fold | Train final | Train purged | Validation final | Validation purged | Test final | Invalid labels |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for fold in folds:
        manifest = fold.manifest
        invalid = (manifest.train_invalid_label_count + manifest.validation_invalid_label_count
                   + manifest.test_invalid_label_count)
        lines.append(f"| {manifest.fold_id} | {manifest.train_final_count} | "
                     f"{manifest.train_purged_count} | {manifest.validation_final_count} | "
                     f"{manifest.validation_purged_count} | {manifest.test_final_count} | {invalid} |")
    lines += ["", "No model, IC/RankIC, portfolio or performance metric is computed.",
              "Research results: [TODO: 待实验结果]", ""]
    output.mkdir(parents=True, exist_ok=True)
    (output / "walk_forward_quality_report.md").write_text("\n".join(lines))
