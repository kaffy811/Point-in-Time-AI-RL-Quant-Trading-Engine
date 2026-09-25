"""Human-readable, JSON-only fold artifacts; no opaque pickle state."""
import json
from pathlib import Path

from src.preprocessing.pipeline import Preprocessor, TransformResult


def write_fold_artifacts(
    output: Path, preprocessor: Preprocessor, *, fold_id: str,
    input_manifest_hash: str, config_hash: str, git_commit: str | None,
    validation: TransformResult | None = None, test: TransformResult | None = None,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "preprocessor.json").write_text(
        json.dumps(preprocessor.to_dict(), indent=2, sort_keys=True) + "\n")
    fit_manifest = {
        "fold_id": fold_id, "fit_split": preprocessor.fit_split,
        "fit_row_count": preprocessor.fit_row_count,
        "fit_security_count": preprocessor.fit_security_count,
        "fit_row_ids_hash": preprocessor.fit_row_ids_hash,
        "feature_set_version": preprocessor.feature_set_version,
        "registry_hash": preprocessor.registry_hash,
        "input_manifest_hash": input_manifest_hash, "config_hash": config_hash,
        "git_commit": git_commit, "scaler": "disabled", "feature_selection": "disabled",
    }
    (output / "fit_manifest.json").write_text(json.dumps(fit_manifest, indent=2, sort_keys=True) + "\n")
    transforms = {}
    for result in (validation, test):
        if result is not None:
            transforms[result.split] = {
                "row_count": len(result.rows), "clipped_count": result.clipped_count,
                "imputed_count": result.imputed_count,
            }
    (output / "transform_report.json").write_text(json.dumps(transforms, indent=2, sort_keys=True) + "\n")


def write_quality_report(output: Path, preprocessor: Preprocessor,
                         results: tuple[TransformResult, ...]) -> None:
    lines = ["# P1-04 Preprocessing Quality Report", "",
             "Parameters are fitted from TRAIN only. Validation/test diagnostics do not refit state.", "",
             "| Split | Feature | Clipped | Imputed |", "|---|---|---:|---:|"]
    for result in results:
        for name in preprocessor.feature_order:
            lines.append(f"| {result.split} | {name} | {result.clipped_count[name]} | "
                         f"{result.imputed_count[name]} |")
    lines += ["", "QA distributions from P1-03 are not read by preprocessing.",
              "Scaling: disabled. Feature selection: disabled.", ""]
    output.mkdir(parents=True, exist_ok=True)
    (output / "preprocessing_quality_report.md").write_text("\n".join(lines))
