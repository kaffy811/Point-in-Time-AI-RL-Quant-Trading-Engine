"""Train-only winsorization and median imputation for a frozen FeatureFrame.

This module has no access to providers, QA artifacts, labels, or models. Fit state
is derived solely from explicitly supplied TRAIN rows and is immutable thereafter.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from statistics import median
from typing import Any, Literal, cast

from src.features.contracts import FeatureFrame, FeatureRow
from src.features.registry import FEATURE_SET_VERSION, FeatureRegistry


class PreprocessingError(ValueError):
    """Fail-loud contract violation; never silently repair upstream data."""


def _canonical_row_id(row: FeatureRow) -> str:
    return f"{row.signal_timestamp.isoformat()}::{row.security_id}"


def row_ids_hash(rows: tuple[FeatureRow, ...]) -> str:
    values = sorted(_canonical_row_id(row) for row in rows)
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def linear_quantile(values: tuple[float, ...], probability: float) -> float:
    if not values:
        raise PreprocessingError("cannot calculate quantile from zero finite TRAIN values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


@dataclass(frozen=True)
class FeatureParameters:
    name: str
    family: str
    winsorize: bool
    impute: bool
    passthrough: bool
    lower: float | None
    upper: float | None
    median: float | None
    finite_train_count: int
    train_missing_count: int


@dataclass(frozen=True)
class PreparedRow:
    security_id: str
    signal_timestamp: datetime
    values: tuple[float, ...]


@dataclass(frozen=True)
class TransformResult:
    split: Literal["TRAIN", "VALIDATION", "TEST"]
    rows: tuple[PreparedRow, ...]
    clipped_count: dict[str, int]
    imputed_count: dict[str, int]


@dataclass(frozen=True)
class Preprocessor:
    feature_set_version: str
    registry_hash: str
    feature_order: tuple[str, ...]
    parameters: tuple[FeatureParameters, ...]
    fit_split: Literal["TRAIN"]
    fit_row_count: int
    fit_security_count: int
    fit_row_ids_hash: str
    winsor_lower_quantile: float
    winsor_upper_quantile: float
    interpolation: Literal["linear"]
    scaling_enabled: Literal[False] = False
    feature_selection_enabled: Literal[False] = False

    @classmethod
    def fit(
        cls,
        train: FeatureFrame,
        registry: FeatureRegistry,
        *,
        fit_split: Literal["TRAIN"] = "TRAIN",
        lower_quantile: float = 0.01,
        upper_quantile: float = 0.99,
        interpolation: Literal["linear"] = "linear",
    ) -> "Preprocessor":
        if fit_split != "TRAIN":
            raise PreprocessingError("preprocessor fit is permitted only for TRAIN")
        if lower_quantile != 0.01 or upper_quantile != 0.99:
            raise PreprocessingError("P1-04 freezes winsorization at 1%/99%")
        if interpolation != "linear":
            raise PreprocessingError("only linear quantile interpolation is frozen")
        cls._validate_frame(train, registry)
        if not train.rows:
            raise PreprocessingError("cannot fit on empty TRAIN frame")
        feature_order = registry.model_features()
        parameters: list[FeatureParameters] = []
        for name in feature_order:
            spec = registry.spec(name)
            values = tuple(next(cell.value for cell in row.values if cell.name == name)
                           for row in train.rows)
            invalid = [value for value in values if value is not None and not math.isfinite(value)]
            if invalid:
                raise PreprocessingError(f"infinite value reaches preprocessing: {name}")
            finite_values = tuple(cast(float, value) for value in values if finite(value))
            if not finite_values and not spec.passthrough:
                raise PreprocessingError(f"no finite TRAIN observations for model feature: {name}")
            lower = upper = med = None
            if spec.winsorize:
                lower = linear_quantile(finite_values, lower_quantile)
                upper = linear_quantile(finite_values, upper_quantile)
                clipped = tuple(min(max(value, lower), upper) for value in finite_values)
                med = float(median(clipped))
            elif spec.impute:
                med = float(median(finite_values))
            parameters.append(FeatureParameters(
                name=name, family=spec.family, winsorize=spec.winsorize,
                impute=spec.impute, passthrough=spec.passthrough, lower=lower,
                upper=upper, median=med, finite_train_count=len(finite_values),
                train_missing_count=len(values) - len(finite_values)))
        return cls(
            feature_set_version=train.feature_set_version, registry_hash=registry.content_hash(),
            feature_order=feature_order, parameters=tuple(parameters), fit_split="TRAIN",
            fit_row_count=len(train.rows), fit_security_count=len({r.security_id for r in train.rows}),
            fit_row_ids_hash=row_ids_hash(train.rows), winsor_lower_quantile=lower_quantile,
            winsor_upper_quantile=upper_quantile, interpolation=interpolation,
        )

    @staticmethod
    def _validate_frame(frame: FeatureFrame, registry: FeatureRegistry) -> None:
        if frame.feature_set_version != FEATURE_SET_VERSION:
            raise PreprocessingError("feature set version mismatch")
        if frame.registry_hash != registry.content_hash():
            raise PreprocessingError("feature registry hash mismatch")
        expected = registry.model_features()
        for row in frame.rows:
            actual = tuple(cell.name for cell in row.values)
            if actual != expected:
                raise PreprocessingError("feature order/schema mismatch")

    def transform(self, frame: FeatureFrame, registry: FeatureRegistry,
                  *, split: Literal["TRAIN", "VALIDATION", "TEST"]) -> TransformResult:
        if split not in ("TRAIN", "VALIDATION", "TEST"):
            raise PreprocessingError("unknown transform split")
        self._validate_frame(frame, registry)
        if registry.content_hash() != self.registry_hash:
            raise PreprocessingError("transform registry hash mismatch")
        if tuple(registry.model_features()) != self.feature_order:
            raise PreprocessingError("feature order changed after fit")
        by_name = {parameter.name: parameter for parameter in self.parameters}
        rows: list[PreparedRow] = []
        clipped_count = {name: 0 for name in self.feature_order}
        imputed_count = {name: 0 for name in self.feature_order}
        for row in frame.rows:
            values: list[float] = []
            for name in self.feature_order:
                parameter = by_name[name]
                value = next(cell.value for cell in row.values if cell.name == name)
                if value is not None and not math.isfinite(value):
                    raise PreprocessingError(f"infinite value reaches transform: {name}")
                if value is None:
                    if parameter.passthrough:
                        raise PreprocessingError(f"passthrough feature unexpectedly missing: {name}")
                    if not parameter.impute:
                        raise PreprocessingError(f"non-imputable feature unexpectedly missing: {name}")
                    if parameter.median is None:
                        raise PreprocessingError(f"no learned median for missing feature: {name}")
                    value = parameter.median
                    imputed_count[name] += 1
                elif parameter.winsorize:
                    assert parameter.lower is not None and parameter.upper is not None
                    bounded = min(max(value, parameter.lower), parameter.upper)
                    if bounded != value:
                        clipped_count[name] += 1
                    value = bounded
                values.append(float(value))
            rows.append(PreparedRow(row.security_id, row.signal_timestamp, tuple(values)))
        return TransformResult(split, tuple(rows), clipped_count, imputed_count)

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_set_version": self.feature_set_version,
            "registry_hash": self.registry_hash,
            "feature_order": self.feature_order,
            "parameters": [parameter.__dict__ for parameter in self.parameters],
            "fit_split": self.fit_split, "fit_row_count": self.fit_row_count,
            "fit_security_count": self.fit_security_count,
            "fit_row_ids_hash": self.fit_row_ids_hash,
            "winsor_lower_quantile": self.winsor_lower_quantile,
            "winsor_upper_quantile": self.winsor_upper_quantile,
            "interpolation": self.interpolation,
            "scaling_enabled": self.scaling_enabled,
            "feature_selection_enabled": self.feature_selection_enabled,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Preprocessor":
        raw_parameters = cast(list[dict[str, Any]], payload["parameters"])
        params = tuple(FeatureParameters(**item) for item in raw_parameters)
        values = {key: payload[key] for key in (
            "feature_set_version", "registry_hash", "feature_order", "fit_split",
            "fit_row_count", "fit_security_count", "fit_row_ids_hash",
            "winsor_lower_quantile", "winsor_upper_quantile", "interpolation",
            "scaling_enabled", "feature_selection_enabled")}
        values["feature_order"] = tuple(cast(list[str], values["feature_order"]))
        return cls(parameters=params, **cast(dict[str, Any], values))
