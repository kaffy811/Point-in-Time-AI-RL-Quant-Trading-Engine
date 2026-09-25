"""PIT-only orchestration. Numerical calculators are explicit, separately reviewable inputs."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Mapping

from src.data.lineage import content_hash
from src.data.pit_store import PITStore
from src.data.schemas import FundamentalFact, MarketRecord, Observation
from src.features.contracts import FeatureFrame, FeatureRow, FeatureValue, SnapshotProvenance
from src.features.lineage import reference
from src.features.registry import MISSING_FEATURES, RAW_FEATURES, FeatureRegistry


@dataclass(frozen=True)
class FeatureContext:
    security_id: str
    signal_timestamp: datetime
    completed_sessions: tuple[date, ...]
    market: tuple[MarketRecord, ...]
    benchmark_market: tuple[MarketRecord, ...]
    fundamentals: tuple[FundamentalFact, ...]
    anchor_date: date | None = None


@dataclass(frozen=True)
class Computation:
    value: float | None
    observations: tuple[Observation, ...]
    observations_used: int
    missing_reason: str | None = None


Calculator = Callable[[FeatureContext], Computation]


class FeaturePipeline:
    def __init__(
        self, store: PITStore, registry: FeatureRegistry, calculators: Mapping[str, Calculator], *,
        benchmark_security_id: str, dataset_version: str,
    ) -> None:
        if set(calculators) != set(RAW_FEATURES):
            raise ValueError("calculators must implement exactly the raw feature whitelist")
        if not benchmark_security_id.strip() or not dataset_version.strip():
            raise ValueError("explicit benchmark stable ID and data version are required")
        self._store = store
        self._registry = registry
        self._calculators = dict(calculators)
        self._benchmark_id = benchmark_security_id
        self._dataset_version = dataset_version

    def generate(self, signal_timestamps: tuple[datetime, ...]) -> FeatureFrame:
        if len(set(signal_timestamps)) != len(signal_timestamps):
            raise ValueError("duplicate signal timestamps")
        rows = []
        catalog = {}
        snapshots = []
        for signal in sorted(signal_timestamps):
            snapshot = self._store.snapshot(signal_timestamp=signal,
                                            benchmark_security_id=self._benchmark_id)
            snapshots.append(SnapshotProvenance(
                signal_timestamp=snapshot.signal_timestamp, security_ids=snapshot.security_ids,
                snapshot_hash=content_hash(snapshot.model_dump(mode="json")),
                benchmark_security_id=self._benchmark_id))
            for sid in snapshot.security_ids:
                own_market = tuple(r for r in snapshot.market if r.security_id == sid)
                own_facts = tuple(r for r in snapshot.fundamentals if r.security_id == sid)
                context = FeatureContext(sid, snapshot.signal_timestamp, snapshot.completed_sessions,
                                         own_market, snapshot.benchmark_market, own_facts,
                                         snapshot.market_anchor_date(sid))
                identity: tuple[Observation, ...] = (
                    next(r for r in snapshot.securities if r.security_id == sid),
                    next(r for r in snapshot.memberships if r.security_id == sid),
                )
                own_hashes = {reference(r).reference_id for r in (*own_market, *own_facts)}
                benchmark_hashes = {reference(r).reference_id for r in snapshot.benchmark_market}
                cells = []
                for name in RAW_FEATURES:
                    computed = self._calculators[name](context)
                    used = list(computed.observations)
                    allowed = own_hashes | (benchmark_hashes if name.startswith("beta_") else set())
                    if any(reference(r).reference_id not in allowed for r in used):
                        raise ValueError("calculator referenced data outside its PIT input context")
                    used.extend(identity)
                    if name.startswith("beta_") and snapshot.benchmark_security is not None:
                        used.append(snapshot.benchmark_security)
                    references = {reference(r).reference_id: reference(r) for r in used}
                    catalog.update(references)
                    cells.append(FeatureValue(
                        name=name, value=computed.value,
                        input_references=tuple(sorted(references)),
                        available_timestamp=max(r.available_timestamp for r in references.values()),
                        missing_reason=computed.missing_reason,
                        observations_used=computed.observations_used,
                    ))
                by_name = {cell.name: cell for cell in cells}
                for name in MISSING_FEATURES:
                    raw = by_name[name.removesuffix("_is_missing")]
                    cells.append(FeatureValue(
                        name=name, value=int(raw.value is None),
                        input_references=raw.input_references,
                        available_timestamp=raw.available_timestamp,
                        observations_used=raw.observations_used,
                    ))
                rows.append(FeatureRow(security_id=sid, signal_timestamp=snapshot.signal_timestamp,
                                       values=tuple(cells)))
        return FeatureFrame(data_manifest_hash=self._store.data_manifest_hash(self._dataset_version),
                            registry_hash=self._registry.content_hash(),
                            rows=tuple(rows), inputs=tuple(catalog[key] for key in sorted(catalog)),
                            snapshots=tuple(snapshots))
