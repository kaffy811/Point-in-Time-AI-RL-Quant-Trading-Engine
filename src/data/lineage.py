"""Order-independent content hashes of validated canonical datasets."""
import hashlib
import json
from datetime import datetime
from typing import Iterable

from src.data.schemas import Calendar, Contract, DataBundle, Observation

SCHEMA_VERSION = "p1-02.v1"


def content_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def dataset_manifest(
    name: str, rows: Iterable[Observation], dataset_version: str, ingested_at: datetime,
) -> dict[str, object]:
    records = tuple(rows)
    serialized = sorted((r.model_dump(mode="json") for r in records),
                        key=lambda r: json.dumps(r, sort_keys=True))
    sources = sorted({(r.source, r.source_version) for r in records})
    return {
        "dataset_name": name, "dataset_version": dataset_version,
        "source": [s[0] for s in sources], "source_version": [s[1] for s in sources],
        "ingested_at": ingested_at.isoformat(), "schema_version": SCHEMA_VERSION,
        "row_count": len(records), "content_hash": content_hash(serialized),
    }


def build_manifest(
    bundle: DataBundle, calendar: Calendar, dataset_version: str, ingested_at: datetime,
) -> dict[str, object]:
    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("manifest ingestion timestamp must be aware")
    if not dataset_version.strip():
        raise ValueError("dataset_version cannot be empty")
    datasets = []
    for name in ("securities", "memberships", "market", "fundamentals"):
        rows = getattr(bundle, name)
        if any(r.ingested_at > ingested_at for r in rows):
            raise ValueError("manifest ingestion precedes row ingestion")
        datasets.append(dataset_manifest(name, rows, dataset_version, ingested_at))
    return {"schema_version": SCHEMA_VERSION, "datasets": datasets,
            "calendar": {"source": calendar.source, "source_version": calendar.source_version,
                         "content_hash": content_hash(calendar.model_dump(mode="json"))}}


def contract_json(value: Contract) -> str:
    return json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)
