"""User-authenticated bounded V2 extraction; freeze six PERMNOs before reading links."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .connection import Connector, interactive_factory
from .extract import (
    bounded_table, digest, json_bytes, sync_directory, sync_file, write_once, write_parquet_once,
)
from .v2_diagnostics import FINGERPRINT, FREEZE, Diagnostic, inventory, selection_preflight

ROOT = Path(__file__).resolve().parents[4]
EXCLUDED = [12350, 13030, 14093, 78690, 90298]
STRATA = ['ordinary_long_lived', 'ticker_change', 'cusip_change', 'membership_change',
          'combined_identity_change_proxy', 'amendment_check_after_freeze']
CATALOG_SQL = '''WITH candidates AS (
 SELECT DISTINCT permno FROM crsp.stksecurityinfohist
 WHERE secinfostartdt <= %(end)s AND secinfoenddt >= %(start)s
 AND permno NOT IN %(excluded)s ORDER BY permno LIMIT 60
), history AS (
 SELECT h.permno, min(secinfostartdt) AS first_date, max(secinfoenddt) AS last_date,
 count(DISTINCT ticker)::integer AS ticker_count,
 count(DISTINCT tradingsymbol)::integer AS symbol_count,
 count(DISTINCT cusip)::integer AS cusip_count
 FROM crsp.stksecurityinfohist h JOIN candidates c ON c.permno=h.permno
 WHERE secinfostartdt <= %(end)s AND secinfoenddt >= %(start)s GROUP BY h.permno
)
SELECT h.*, EXISTS (SELECT 1 FROM crsp.dsp500list_v2 m WHERE m.permno=h.permno
 AND (m.mbrstartdt BETWEEN %(start)s AND %(end)s
 OR m.mbrenddt BETWEEN %(start)s AND %(end)s)) AS membership_change
FROM history h ORDER BY h.permno'''
HISTORY_SQL = '''SELECT permno, ticker, tradingsymbol, cusip, cusip9,
 secinfostartdt, secinfoenddt FROM crsp.stksecurityinfohist
 WHERE permno IN %(permnos)s AND secinfostartdt <= %(end)s AND secinfoenddt >= %(start)s
 ORDER BY permno, secinfostartdt, secinfoenddt, cusip, cusip9, ticker, tradingsymbol
 LIMIT 501'''
LINK_SQL = '''SELECT cik, cusip_full, cusip, cikdate1, cikdate2, tmatch, validated
 FROM wrdssec_common.wciklink_cusip
 WHERE cusip IN %(cusips)s OR cusip_full IN %(full)s
 ORDER BY cik, cusip, cusip_full, cikdate1, cikdate2, validated, tmatch LIMIT 201'''


def choose(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Selection uses only declared pre-resolution CRSP/membership fields."""
    if not 6 <= len(rows) <= 60 or len({r['permno'] for r in rows}) != len(rows):
        raise ValueError('Candidate catalog must contain 6–60 unique PERMNOs')
    if any(type(r['permno']) is not int or r['permno'] in EXCLUDED for r in rows):
        raise ValueError('Invalid/additionally excluded candidate')
    ordered = sorted(rows, key=lambda r: r['permno'])
    selected: list[dict[str, Any]] = []
    for stratum in STRATA:
        remaining = [r for r in ordered if r['permno'] not in {s['permno'] for s in selected}]

        def matches(row: dict[str, Any]) -> bool:
            ticker = row['ticker_count'] > 1 or row['symbol_count'] > 1
            cusip = row['cusip_count'] > 1
            return bool({
                'ordinary_long_lived': str(row['first_date']) <= '2010-01-01'
                and str(row['last_date']) >= '2025-12-31' and not ticker and not cusip,
                'ticker_change': ticker, 'cusip_change': cusip,
                'membership_change': row['membership_change'],
                'combined_identity_change_proxy': ticker and cusip,
                'amendment_check_after_freeze': True,
            }[stratum])

        eligible = [r for r in remaining if matches(r)]
        chosen = (eligible or remaining)[0]
        selected.append({'permno': chosen['permno'], 'selection_slot': stratum,
                         'metadata_stratum_matched': bool(eligible),
                         'fallback': None if eligible else 'LOWEST_UNUSED_PERMNO'})
    return selected


def _acquire(connector: Connector, root: Path, diagnostic: Diagnostic,
             resume: bool) -> dict[str, Any]:
    diagnostic.at('VALIDATE_SCHEMA', 'V2_CONFIG_VALIDATION')
    config_path = root / 'configs/gate_a_data_02_v2.json'
    config = json.loads(config_path.read_bytes())
    if (config['protocol'] != 'DATA-02-V2'
            or config['candidate_order'] != 'NUMERIC_PERMNO_ASCENDING'
            or config['as_of_dates'] != ['2010-06-30', '2015-06-30', '2020-06-30', '2025-06-30']
            or config['signal_time'] != '16:10:00 America/New_York'
            or config['sample_size'] != 6 or config['candidate_cap'] != 60
            or config['excluded_permnos'] != EXCLUDED or config['strata_order'] != STRATA
            or config['history_row_cap'] != 500 or config['link_row_cap'] != 200
            or config['window_start'] != '2010-01-01' or config['window_end'] != '2025-12-31'
            or config['resampling'] is not False or config['ccm'] is not False):
        raise ValueError('Frozen V2 protocol mismatch')
    directory = root / 'data/raw/wrds/gate_a/data_02_v2'
    audit = root / 'artifacts/gate_a/identity_spine'
    freeze_path = audit / 'v2_selection_manifest.json'
    diagnostic.at('FREEZE_SELECTION', 'V2_RESUME_PREFLIGHT')
    freeze = selection_preflight(root, require_frozen=resume)
    resume = freeze is not None
    if freeze is None:
        diagnostic.at('WRITE_RAW_FIXTURE', 'RESERVE_V2_RAW_DIRECTORY')
        directory.mkdir(parents=True, exist_ok=True)
        if any(directory.iterdir()):
            raise ValueError(
                'Nonempty V2 raw directory without frozen selection manifest; preserve without overwrite.')
    sources: dict[str, Any] = {}

    def fetch(name: str, sql: str, params: dict[str, Any], cap: int) -> Any:
        tables = (['crsp.stksecurityinfohist', 'crsp.dsp500list_v2']
                  if name == 'selection_metadata' else ['crsp.stksecurityinfohist']
                  if name == 'stksecurityinfohist_fixture' else ['wrdssec_common.wciklink_cusip'])
        stage = ('FETCH_MEMBERSHIP' if name == 'selection_metadata' else
                 'FETCH_SECURITY_HISTORY' if name == 'stksecurityinfohist_fixture'
                 else 'FETCH_CIK_LINKS')
        diagnostic.at('VALIDATE_SCHEMA', name + '_CACHE_VALIDATION', tables)
        path = directory / (name + '.parquet')
        receipt_path = directory / (name + '.manifest.json')
        query_hash = digest(json_bytes({'sql': sql, 'params': params}))
        if path.exists() or receipt_path.exists():
            if not resume or not path.is_file() or not receipt_path.is_file():
                raise ValueError('Incomplete existing fixture; preserve without overwriting')
            receipt = json.loads(receipt_path.read_bytes())
            content = path.read_bytes()
            if (receipt['query_hash'] != query_hash or receipt['content_hash'] != digest(content)
                    or receipt['path'] != str(path.relative_to(root))):
                raise ValueError('Existing fixture provenance mismatch')
            table = pq.read_table(pa.BufferReader(content))
            if (table.num_rows > cap or table.num_rows != receipt['row_count']
                    or digest(str(table.schema).encode()) != receipt['schema_hash']):
                raise ValueError('Existing fixture schema/count mismatch')
            sources[name] = receipt
            return table
        diagnostic.at(stage, name, tables)
        frame = connector.query(sql, params)
        diagnostic.at('VALIDATE_SCHEMA', name + '_SOURCE_SCHEMA', tables)
        table = bounded_table(frame, cap)
        path = directory / (name + '.parquet')
        diagnostic.at('WRITE_RAW_FIXTURE', name + '_PARQUET')
        write_parquet_once(path, table)
        diagnostic.wrote(path)
        sources[name] = {'provider': 'WRDS',
                         'source_tables': (['crsp.stksecurityinfohist', 'crsp.dsp500list_v2']
                             if name == 'selection_metadata' else
                             ['crsp.stksecurityinfohist'] if name == 'stksecurityinfohist_fixture'
                             else ['wrdssec_common.wciklink_cusip']),
                         'requested_history_window': bounds, 'path': str(path.relative_to(root)), 'row_count': len(frame),
                         'content_hash': digest(path.read_bytes()),
                         'schema_hash': digest(str(table.schema).encode()),
                         'query_hash': digest(json_bytes({'sql': sql, 'params': params})),
                         'retrieved_at': datetime.now(timezone.utc).isoformat(),
                         'query': sql, 'parameters': params}
        diagnostic.at('WRITE_MANIFEST', name + '_RECEIPT')
        write_once(receipt_path, json_bytes(sources[name]))
        diagnostic.wrote(receipt_path)
        return table

    bounds = {'start': config['window_start'], 'end': config['window_end']}
    if freeze is None:
        catalog = fetch('selection_metadata', CATALOG_SQL,
                        {**bounds, 'excluded': tuple(EXCLUDED)}, 60)
        diagnostic.at('FREEZE_SELECTION', 'CHOOSE_AND_FREEZE_SIX', [])
        selected = choose(catalog.to_pylist())
        freeze = {'protocol': config, 'config_sha256': digest(config_path.read_bytes()),
                  'implementation_sha256': digest(Path(__file__).read_bytes()),
                  'selected': selected, 'frozen_at': datetime.now(timezone.utc).isoformat(),
                  'selection_metadata_sha256': sources['selection_metadata']['content_hash'],
                  'selection_query_hash': sources['selection_metadata']['query_hash'],
                  'links_or_sec_outcomes_inspected_before_freeze': False,
                  'status': 'FROZEN_NO_RESAMPLING', 'Gate A': 'BLOCKED'}
        audit.mkdir(parents=True, exist_ok=True)
        diagnostic.at('WRITE_MANIFEST', 'WRITE_FROZEN_SELECTION')
        write_once(freeze_path, json_bytes(freeze))
        diagnostic.wrote(freeze_path)
    else:
        selected = freeze['selected']
        sources['selection_metadata'] = json.loads(
            (directory / 'selection_metadata.manifest.json').read_bytes())
        expected_query = digest(json_bytes({'sql': CATALOG_SQL,
                                           'params': {**bounds, 'excluded': tuple(EXCLUDED)}}))
        if freeze['selection_query_hash'] != expected_query:
            raise ValueError('Frozen selection catalog evidence mismatch')
    # Persist the fingerprint before any history/link query. A failed fingerprint
    # write leaves the manifest frozen; a retry validates it and never selects again.
    diagnostic.at('WRITE_MANIFEST', 'FINGERPRINT_FROZEN_SELECTION', [])
    selection_hash = digest(freeze_path.read_bytes())
    fingerprint = root / FINGERPRINT
    if not fingerprint.exists():
        write_once(fingerprint, (selection_hash + '\n').encode())
        diagnostic.wrote(fingerprint)
    elif fingerprint.read_text() != selection_hash + '\n':
        raise ValueError('Frozen selection provenance mismatch')
    sync_file(freeze_path)
    sync_file(fingerprint)
    sync_directory(audit)
    # The manifest exists before any selected history / CIK-link acquisition.
    history = fetch('stksecurityinfohist_fixture', HISTORY_SQL,
                    {**bounds, 'permnos': tuple(s['permno'] for s in selected)}, 500)
    diagnostic.at('VALIDATE_SCHEMA', 'HISTORICAL_CUSIP_BOUNDS', ['crsp.stksecurityinfohist'])
    cusips = sorted({r['cusip'] for r in history.to_pylist() if r['cusip']})
    full = sorted({r['cusip9'] for r in history.to_pylist() if r['cusip9']})
    if not cusips and not full:
        raise ValueError('No real historical identifiers; preserve frozen sample')
    if len(cusips) + len(full) > 120:
        raise ValueError('Identifier cap exceeded; preserve frozen sample')
    fetch('wciklink_cusip_fixture', LINK_SQL,
          {'cusips': tuple(cusips) or ('',), 'full': tuple(full) or ('',)}, 200)
    manifest = {'status': 'COMPLETE', 'provider': 'WRDS', 'sources': sources,
                'selection_manifest_sha256': selection_hash,
                'config_sha256': digest(config_path.read_bytes())}
    diagnostic.at('WRITE_MANIFEST', 'WRITE_V2_COMPLETION_MANIFEST', [])
    completion = directory / 'wrds_fixture_manifest.json'
    if completion.exists():
        if not resume or json.loads(completion.read_bytes()) != json.loads(json_bytes(manifest)):
            raise ValueError('Existing completion manifest differs; preserve without overwriting')
    else:
        write_once(completion, json_bytes(manifest))
        diagnostic.wrote(completion)
    return freeze


def acquire(connector: Connector, root: Path = ROOT, *, resume: bool = False,
            diagnostic: Diagnostic | None = None) -> dict[str, Any]:
    audit = diagnostic or Diagnostic(root)
    try:
        return _acquire(connector, root, audit, resume)
    except Exception as exc:
        audit.failure(exc)
        raise


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnose', action='store_true', help='Offline preflight; never query WRDS')
    parser.add_argument('--resume', action='store_true', help='Reuse an existing verified frozen sample')
    args = parser.parse_args()
    audit = Diagnostic(ROOT)
    try:
        if args.diagnose:
            audit.at('FREEZE_SELECTION', 'CHECK_SELECTION_MANIFEST', [])
            freeze = selection_preflight(ROOT)
            print(json.dumps({'status': 'FROZEN_SELECTION_VERIFIED' if freeze else
                              'INITIAL_SELECTION_READY_NOT_EXECUTED',
                              'prerequisite_artifact': FREEZE,
                              **inventory(ROOT)}))
            return
        audit.at('FREEZE_SELECTION', 'V2_LOCAL_PREFLIGHT', [])
        selection_preflight(ROOT, require_frozen=args.resume)
        audit.at('CONNECT_WRDS', 'LOCAL_INTERACTIVE_CONNECTION', [])
        connector = Connector(interactive_factory())
        result = acquire(connector, ROOT, resume=args.resume, diagnostic=audit)
    except Exception as exc:
        detail = audit.summary or audit.failure(exc)
        print(json.dumps(detail, sort_keys=True))
        raise SystemExit(1) from None
    print(json.dumps({'selected_permnos': [r['permno'] for r in result['selected']],
                      'status': 'FROZEN_AND_EXTRACTED'}))


if __name__ == '__main__':
    main()
