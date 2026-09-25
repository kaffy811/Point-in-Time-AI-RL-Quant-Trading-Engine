"""Feature values and per-cell references, independent of any fitted preprocessing."""
from datetime import date, datetime
from math import nan
from typing import Literal, Self

from pydantic import AwareDatetime, model_validator

from src.data.schemas import Contract, Finite, Text
from src.features.registry import MISSING_FEATURES, RAW_FEATURES


class InputReference(Contract):
    reference_id: Text
    dataset: Literal["market", "fundamentals", "securities", "memberships"]
    security_id: Text
    observation_date: date
    available_timestamp: AwareDatetime
    source: Text
    source_version: Text
    revision_id: str | None = None
    filing_accepted_at: AwareDatetime | None = None


class FeatureValue(Contract):
    name: Text
    value: Finite | None
    input_references: tuple[str, ...]
    available_timestamp: AwareDatetime | None
    missing_reason: str | None = None
    observations_used: int

    @model_validator(mode="after")
    def missing_contract(self) -> Self:
        if self.name not in RAW_FEATURES + MISSING_FEATURES:
            raise ValueError("non-whitelisted feature; labels/forward targets prohibited")
        if (self.value is None) != (self.missing_reason is not None):
            raise ValueError("missing value and reason must agree")
        if self.observations_used < 0 or len(set(self.input_references)) != len(self.input_references):
            raise ValueError("invalid observation count or duplicate input reference")
        if self.name in MISSING_FEATURES and self.value not in (0, 1):
            raise ValueError("missing indicator must be zero or one")
        return self


class FeatureRow(Contract):
    security_id: Text
    signal_timestamp: AwareDatetime
    values: tuple[FeatureValue, ...]

    @model_validator(mode="after")
    def whitelist(self) -> Self:
        if tuple(v.name for v in self.values) != RAW_FEATURES + MISSING_FEATURES:
            raise ValueError("feature row must contain exactly the registered columns in order")
        by_name = {v.name: v for v in self.values}
        for name in MISSING_FEATURES:
            raw = by_name[name.removesuffix("_is_missing")]
            if by_name[name].value != int(raw.value is None):
                raise ValueError("missing indicator disagrees with raw value")
        return self

    def model_values(self) -> tuple[float, ...]:
        """Missing stays NaN in model views; JSON serialization retains standard nulls."""
        return tuple(nan if cell.value is None else cell.value for cell in self.values)


class SnapshotProvenance(Contract):
    signal_timestamp: AwareDatetime
    security_ids: tuple[str, ...]
    snapshot_hash: Text
    benchmark_security_id: str | None = None


class FeatureFrame(Contract):
    feature_set_version: Literal["phase1_v1"] = "phase1_v1"
    data_manifest_hash: Text
    registry_hash: Text
    rows: tuple[FeatureRow, ...]
    inputs: tuple[InputReference, ...]
    snapshots: tuple[SnapshotProvenance, ...]

    @model_validator(mode="after")
    def information_firewall(self) -> Self:
        refs = {r.reference_id: r for r in self.inputs}
        if len(refs) != len(self.inputs):
            raise ValueError("duplicate input reference IDs")
        keys = [(r.signal_timestamp, r.security_id) for r in self.rows]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate feature rows")
        provenance = {p.signal_timestamp: p for p in self.snapshots}
        if len(provenance) != len(self.snapshots):
            raise ValueError("duplicate signal provenance")
        for row in self.rows:
            if row.signal_timestamp not in provenance or row.security_id not in provenance[
                row.signal_timestamp
            ].security_ids:
                raise ValueError("feature row outside PIT eligible universe")
            for value in row.values:
                if any(key not in refs for key in value.input_references):
                    raise ValueError("unknown feature input reference")
                used = [refs[key] for key in value.input_references]
                benchmark_id = provenance[row.signal_timestamp].benchmark_security_id
                for used_ref in used:
                    is_benchmark = (value.name.startswith("beta_") and benchmark_id is not None
                                    and used_ref.security_id == benchmark_id
                                    and used_ref.dataset in ("market", "securities"))
                    if used_ref.security_id != row.security_id and not is_benchmark:
                        raise ValueError("cross-security feature input outside explicit beta benchmark")
                if value.name in RAW_FEATURES and value.value is not None and not any(
                    r.dataset in ("market", "fundamentals") for r in used
                ):
                    raise ValueError("nonmissing raw feature requires observation lineage")
                if any(r.available_timestamp > row.signal_timestamp or (
                    r.filing_accepted_at is not None and r.filing_accepted_at > row.signal_timestamp
                ) for r in used):
                    raise ValueError("future observation in feature lineage")
                latest = max((r.available_timestamp for r in used), default=None)
                if value.available_timestamp != latest:
                    raise ValueError("feature availability does not reconcile with inputs")
        referenced = {key for row in self.rows for value in row.values
                      for key in value.input_references}
        if referenced != set(refs):
            raise ValueError("unreferenced entries in feature input catalog")
        for signal, snapshot in provenance.items():
            actual = {r.security_id for r in self.rows if r.signal_timestamp == signal}
            if actual != set(snapshot.security_ids):
                raise ValueError("feature rows must preserve full PIT universe, including missingness")
        return self

    def rows_at(self, timestamp: datetime) -> tuple[FeatureRow, ...]:
        return tuple(row for row in self.rows if row.signal_timestamp == timestamp)
