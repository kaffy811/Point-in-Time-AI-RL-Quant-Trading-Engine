"""Write-once, bounded native Parquet snapshots with completion manifests."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import re
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .connection import Connector
from .query import QuerySpec


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def extract(connector: Connector, spec: QuerySpec, version: str,
            root: Path = Path("data/raw/wrds")) -> Path:
    sql, params = spec.compile()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", version):
        raise ValueError("Invalid extraction version")
    target = root / spec.table.replace(".", "_") / version
    # Atomic exclusive reservation prevents concurrent writers and version replacement.
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        frame = connector.query(sql, params)
        if len(frame) > spec.max_rows:
            raise ValueError("Row cap exceeded; narrow the extraction; no truncated export")
        if list(frame.columns) != list(spec.columns):
            raise ValueError("Returned columns differ from query specification")
        retrieved = datetime.now(timezone.utc).isoformat()
        table = pa.Table.from_pandas(
            frame, schema=frame.attrs.get("source_arrow_schema"), preserve_index=False, safe=True,
        ).replace_schema_metadata(None)
        coverage = None
        if spec.date_column:
            column = table[spec.date_column]
            if not (pa.types.is_date(column.type) or pa.types.is_timestamp(column.type)):
                raise ValueError("Date coverage requires a native date or timestamp column")
            bounds = pc.min_max(column).as_py()
            coverage = {"column": spec.date_column,
                        "min": str(bounds["min"]) if bounds["min"] is not None else None,
                        "max": str(bounds["max"]) if bounds["max"] is not None else None,
                        "null_count": column.null_count}
        parquet = target / "part-00000.parquet"
        pq.write_table(table, parquet, compression="zstd")
        schema = [{"name": f.name, "type": str(f.type), "nullable": f.nullable}
                  for f in table.schema]
        manifest = {
            "manifest_version": 1, "status": "COMPLETE", "provider": "WRDS",
            "source_table": spec.table, "dataset_version": version,
            "query_hash": digest(json_bytes({"sql": sql, "params": params})),
            "sql_template_hash": digest(sql.encode()), "query": sql, "parameters": params,
            "query_spec": asdict(spec), "retrieval_timestamp": retrieved,
            "row_count": table.num_rows, "schema": schema,
            "schema_hash": digest(json_bytes(schema)),
            "content_hash": digest(parquet.read_bytes()), "content_file": parquet.name,
            "date_coverage": coverage,
            "requested_date_interval": {"start": spec.start, "end_exclusive": spec.end},
            "software": {name: package_version(name) for name in ("wrds", "pyarrow", "pandas")},
            "pit_status": "RAW_ONLY_NOT_CANONICAL_OR_PIT_CERTIFIED",
        }
        # Manifest is the completion marker; consumers must reject directories without it.
        with (target / "manifest.json").open("xb") as handle:
            handle.write(json_bytes(manifest))
        parquet.chmod(0o400)
        (target / "manifest.json").chmod(0o400)
    except Exception:
        # Preserve failed reservation for audit; never silently reuse a partial version.
        raise
    return target / "manifest.json"
