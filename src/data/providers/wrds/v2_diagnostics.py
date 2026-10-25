"""Append-only V2 stage diagnostics and read-only frozen-selection preflight."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .diagnostics import sanitized_exception
from .extract import digest, json_bytes

STAGES = frozenset({'CONNECT_WRDS', 'FREEZE_SELECTION', 'FETCH_SECURITY_HISTORY',
                    'FETCH_MEMBERSHIP', 'FETCH_CIK_LINKS', 'VALIDATE_SCHEMA',
                    'WRITE_RAW_FIXTURE', 'WRITE_MANIFEST'})
RAW = 'data/raw/wrds/gate_a/data_02_v2'
FREEZE = 'artifacts/gate_a/identity_spine/v2_selection_manifest.json'
FREEZE_ROLE = 'durable six-PERMNO selection evidence'
FINGERPRINT = FREEZE.removesuffix('.json') + '.sha256'
KNOWN_FILES = [FREEZE, FINGERPRINT] + [f'{RAW}/{name}{suffix}' for name in (
    'selection_metadata', 'stksecurityinfohist_fixture', 'wciklink_cusip_fixture')
    for suffix in ('.parquet', '.manifest.json')] + [f'{RAW}/wrds_fixture_manifest.json']


def inventory(root: Path) -> dict[str, Any]:
    present = [p for p in KNOWN_FILES if (root / p).is_file()]
    freeze = root / FREEZE
    count = 0
    valid = False
    if freeze.is_file():
        try:
            records = json.loads(freeze.read_bytes())['selected']
            count = len(records) if isinstance(records, list) else 0
            valid = (count == 6 and len({r['permno'] for r in records}) == 6
                     and all(type(r['permno']) is int for r in records))
        except (ValueError, KeyError, TypeError, OSError):
            pass
    return {'selection_already_frozen': freeze.exists(), 'frozen_permno_count': count,
            'frozen_selection_structure_valid': valid, 'existing_artifact_paths': present,
            'raw_directory_exists': (root / RAW).is_dir(),
            'raw_directory_empty': not any((root / RAW).iterdir()) if (root / RAW).is_dir() else None}


class Diagnostic:
    def __init__(self, root: Path):
        self.root = root
        self.before = inventory(root)
        self.stage = 'FREEZE_SELECTION'
        self.query_id = 'V2_PREFLIGHT'
        self.source_tables: list[str] = []
        self.written: list[str] = []
        self.path: Path | None = None
        self.summary: dict[str, Any] | None = None

    def at(self, stage: str, operation: str, tables: list[str] | None = None) -> None:
        if stage not in STAGES:
            raise ValueError('Unknown diagnostic stage')
        self.stage, self.query_id = stage, operation
        if tables is not None:
            self.source_tables = tables

    def wrote(self, path: Path) -> None:
        relative = str(path.relative_to(self.root))
        if relative in KNOWN_FILES:
            self.written.append(relative)

    def failure(self, exc: Exception) -> dict[str, Any]:
        detail = sanitized_exception(exc)
        provider_stage = detail.get('provider_stage')
        stage = provider_stage if provider_stage in {'CONNECT_WRDS', 'VALIDATE_SCHEMA'} else self.stage
        self.summary = {'status': 'FAILED', 'pipeline_stage': stage,
                        'operation_stage': self.stage, 'query_identifier': self.query_id,
                        'source_tables': self.source_tables, **detail,
                        **inventory(self.root), 'state_at_start': self.before,
                        'paths_successfully_written_before_failure': self.written,
                        'recorded_at': datetime.now(timezone.utc).isoformat(),
                        'historical_failure_recovered': False,
                        'Gate A': 'BLOCKED'}
        directory = self.root / 'artifacts/gate_a/identity_spine/v2_diagnostics'
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (uuid4().hex + '.json')
        with self.path.open('xb') as handle:
            handle.write(json_bytes(self.summary))
        return self.summary


def resume_selection(root: Path) -> dict[str, Any]:
    """Verify persisted provenance; never call choose or query a new catalog."""
    if not (root / FREEZE).is_file():
        raise FileNotFoundError(
            f'Required frozen selection manifest missing: {FREEZE}; role={FREEZE_ROLE}.')
    for relative in KNOWN_FILES + [RAW]:
        if (root / relative).is_symlink():
            raise ValueError('Frozen selection provenance mismatch')
    freeze_bytes = (root / FREEZE).read_bytes()
    freeze = json.loads(freeze_bytes)
    fingerprint = root / FINGERPRINT
    if fingerprint.exists() and fingerprint.read_text() != digest(freeze_bytes) + '\n':
        raise ValueError('Frozen selection provenance mismatch')
    config_bytes = (root / 'configs/gate_a_data_02_v2.json').read_bytes()
    if (freeze['config_sha256'] != digest(config_bytes) or freeze['protocol'] != json.loads(config_bytes)
            or freeze['status'] != 'FROZEN_NO_RESAMPLING'
            or freeze['links_or_sec_outcomes_inspected_before_freeze'] is not False
            or not inventory(root)['frozen_selection_structure_valid']):
        raise ValueError('Frozen selection provenance mismatch')
    selected = freeze['selected']
    if any(r['permno'] in freeze['protocol']['excluded_permnos'] for r in selected):
        raise ValueError('Frozen selection includes excluded PERMNO')
    raw = root / RAW
    manifest = json.loads((raw / 'selection_metadata.manifest.json').read_bytes())
    content = (raw / 'selection_metadata.parquet').read_bytes()
    table = pq.read_table(pa.BufferReader(content))
    if (digest(content) != freeze['selection_metadata_sha256']
            or manifest['content_hash'] != freeze['selection_metadata_sha256']
            or manifest['query_hash'] != freeze['selection_query_hash']
            or manifest['query_hash'] != digest(json_bytes(
                {'sql': manifest['query'], 'params': manifest['parameters']}))
            or manifest['path'] != f'{RAW}/selection_metadata.parquet'
            or manifest['provider'] != 'WRDS'
            or manifest['source_tables'] != ['crsp.stksecurityinfohist', 'crsp.dsp500list_v2']
            or not 6 <= table.num_rows <= 60 or manifest['row_count'] != table.num_rows
            or manifest['schema_hash'] != digest(str(table.schema).encode())
            or [r['selection_slot'] for r in selected] != freeze['protocol']['strata_order']
            or not {r['permno'] for r in selected} <= set(table['permno'].to_pylist())):
        raise ValueError('Frozen selection catalog evidence mismatch')
    return dict(freeze)


def selection_preflight(root: Path, *, require_frozen: bool = False) -> dict[str, Any] | None:
    """Read-only local gate, before constructing the interactive WRDS factory."""
    freeze_path = root / FREEZE
    if freeze_path.exists() or freeze_path.is_symlink() or require_frozen:
        return resume_selection(root)
    if (root / FINGERPRINT).exists() or (root / FINGERPRINT).is_symlink():
        raise ValueError('Frozen selection provenance mismatch')
    raw = root / RAW
    if raw.is_symlink() or (raw.exists() and not raw.is_dir()):
        raise FileExistsError('Destination already exists; overwrite refused.')
    if raw.is_dir() and any(raw.iterdir()):
        raise ValueError(
            'Nonempty V2 raw directory without frozen selection manifest; preserve without overwrite.')
    return None
