"""Diagnostic-only distributions. Never export reusable preprocessing parameters."""
from math import floor
from statistics import median

from src.features.contracts import FeatureFrame
from src.features.registry import MISSING_FEATURES, RAW_FEATURES

QA_WARNING = (
    "Full-sample statistics in QA reports are diagnostic only and must never be reused "
    "as model preprocessing parameters."
)


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = floor(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def quality_report(frame: FeatureFrame) -> dict[str, object]:
    details = {}
    for name in RAW_FEATURES + MISSING_FEATURES:
        cells = [next(v for v in row.values if v.name == name) for row in frame.rows]
        known = [cell.value for cell in cells if cell.value is not None]
        reasons: dict[str, int] = {}
        for cell in cells:
            if cell.missing_reason:
                reasons[cell.missing_reason] = reasons.get(cell.missing_reason, 0) + 1
        details[name] = {
            "non_null_pct": 100 * len(known) / len(cells) if cells else None,
            "missing_count": len(cells) - len(known),
            "median": median(known) if known else None,
            "p01": percentile(known, .01), "p05": percentile(known, .05),
            "p95": percentile(known, .95), "p99": percentile(known, .99),
            "min": min(known) if known else None, "max": max(known) if known else None,
            "inf_count": 0,  # FeatureFrame rejects nonfinite values before report creation.
            "missing_reasons": reasons,
        }
    return {"scope": "feature_data_quality_only", "warning": QA_WARNING,
            "row_count": len(frame.rows), "security_count": len({r.security_id for r in frame.rows}),
            "signal_count": len(frame.snapshots), "timestamp_violations": 0,
            "feature_statistics": details}
