"""Frozen V2 C1 and C2 audit overlays; Phase A and its V1 outputs stay unchanged."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .audit import ROOT, invariance
from .phase_a import History, Link, resolve
from .phase_b import accepted_inputs
from .sgml_audit import case_status, parse_header
from ...utils.artifacts import digest, json_bytes, write_once

PERMNOS = [10026, 10028, 10001, 10078, 10100, 10002]
SELECTION_SHA256 = 'c353f73c16d4fcd0a890cde5def3ee26cc13a85475689a578179b01f5c791eb3'
OUTPUT = 'artifacts/gate_a/identity_spine/v2_resolution'
SEC_RAW = 'data/raw/sec/gate_a/data_02_v2'
CONFIG = 'configs/gate_a_data_02_v2_resolution.json'
FREEZE = 'artifacts/gate_a/identity_spine/v2_selection_manifest.json'
FINGERPRINT = 'artifacts/gate_a/identity_spine/v2_selection_manifest.sha256'
RAW = 'data/raw/wrds/gate_a/data_02_v2'
STATUSES = ('SEC_CONFIRMED', 'ROLE_CONFLICT', 'NOT_YET_AVAILABLE', 'AMBIGUOUS',
            'UNRESOLVED', 'PENDING_SOURCE_UNAVAILABLE')


def config(root: Path) -> dict[str, Any]:
    value = json.loads((root / CONFIG).read_bytes())
    if (value['phase'] != 'DATA-02-V2-C1-C2' or value['permnos'] != PERMNOS
            or value['selection_manifest_sha256'] != SELECTION_SHA256
            or value['selection_commit'] != '3c9d827fa4c78bbad7b0427a373830349a515921'
            or value['resampling'] is not False or value['ccm'] is not False
            or value['as_of_dates'] != ['2010-06-30', '2015-06-30', '2020-06-30', '2025-06-30']
            or value['signal_time'] != '16:10:00 America/New_York'
            or value['submissions_max_bytes'] != 2097152 or value['headers_per_cik'] != 3
            or value['header_max_bytes'] != 65536 or value['header_max_attempts'] != 3
            or value['backoff_seconds'] != [1, 2]
            or value['historical_shard_expansion'] is not False
            or value['issuer_forms'] != ['10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '8-K/A']):
        raise ValueError('Frozen V2 resolution config mismatch')
    return dict(value)


def publish(path: Path, content: bytes) -> str:
    """Retry may verify identical output; never replace an existing audit artifact."""
    if path.is_symlink():
        raise ValueError('Audit symlink refused')
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('Existing V2 audit differs; preserve without overwrite')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_once(path, content)
    return digest(content)


def publish_json(path: Path, value: Any) -> str:
    return publish(path, json_bytes(value))


def publish_rows(path: Path, rows: list[dict[str, Any]]) -> str:
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist(rows), sink, compression='zstd')
    return publish(path, sink.getvalue().to_pybytes())


def inputs(root: Path) -> tuple[dict[str, Any], tuple[History, ...], tuple[Link, ...]]:
    cfg = config(root)
    selection_bytes = (root / FREEZE).read_bytes()
    freeze = json.loads(selection_bytes)
    if (digest(selection_bytes) != SELECTION_SHA256
            or (root / FINGERPRINT).read_text() != SELECTION_SHA256 + '\n'
            or (root / FREEZE).is_symlink() or (root / FINGERPRINT).is_symlink()
            or [r['permno'] for r in freeze['selected']] != PERMNOS
            or freeze['protocol']['as_of_dates'] != cfg['as_of_dates']
            or freeze['protocol']['sample_size'] != 6 or freeze['protocol']['resampling'] is not False
            or freeze['status'] != 'FROZEN_NO_RESAMPLING'
            or freeze['links_or_sec_outcomes_inspected_before_freeze'] is not False
            or digest((root / 'configs/gate_a_data_02_v2.json').read_bytes()) != freeze['config_sha256']):
        raise ValueError('Committed six-PERMNO freeze mismatch')
    raw = root / RAW
    completion = json.loads((raw / 'wrds_fixture_manifest.json').read_bytes())
    if (completion['status'] != 'COMPLETE' or completion['provider'] != 'WRDS'
            or completion['selection_manifest_sha256'] != SELECTION_SHA256
            or completion['config_sha256'] != freeze['config_sha256']
            or set(completion['sources']) != {'selection_metadata', 'stksecurityinfohist_fixture',
                                              'wciklink_cusip_fixture'}
            or completion['sources']['selection_metadata'] != json.loads(
                (raw / 'selection_metadata.manifest.json').read_bytes())):
        raise ValueError('V2 extraction completion mismatch')
    tables = {}
    for name, source_tables, cap in (
            ('selection_metadata', ['crsp.stksecurityinfohist', 'crsp.dsp500list_v2'], 60),
            ('stksecurityinfohist_fixture', ['crsp.stksecurityinfohist'], 500),
            ('wciklink_cusip_fixture', ['wrdssec_common.wciklink_cusip'], 200)):
        receipt_path, path = raw / (name + '.manifest.json'), raw / (name + '.parquet')
        receipt = json.loads(receipt_path.read_bytes())
        content = path.read_bytes()
        table = pq.read_table(pa.BufferReader(content))
        if (path.is_symlink() or receipt_path.is_symlink()
                or completion['sources'][name] != receipt or receipt['provider'] != 'WRDS'
                or receipt['source_tables'] != source_tables
                or receipt['path'] != f'{RAW}/{name}.parquet'
                or receipt['content_hash'] != digest(content)
                or receipt['row_count'] != table.num_rows or table.num_rows > cap
                or receipt['schema_hash'] != digest(str(table.schema).encode())
                or receipt['query_hash'] != digest(json_bytes(
                    {'sql': receipt['query'], 'params': receipt['parameters']}))):
            raise ValueError('V2 raw source provenance mismatch')
        tables[name] = table.to_pylist()
    catalog = completion['sources']['selection_metadata']
    if (catalog['content_hash'] != freeze['selection_metadata_sha256']
            or catalog['query_hash'] != freeze['selection_query_hash']
            or not 6 <= catalog['row_count'] <= 60
            or not set(PERMNOS) <= {r['permno'] for r in tables['selection_metadata']}):
        raise ValueError('Frozen V2 catalog evidence mismatch')
    if completion['sources']['stksecurityinfohist_fixture']['parameters'] != {
            'permnos': PERMNOS, 'start': freeze['protocol']['window_start'],
            'end': freeze['protocol']['window_end']}:
        raise ValueError('V2 history query cohort mismatch')
    history = tuple(History.from_row(r) for r in tables['stksecurityinfohist_fixture'])
    links = tuple(Link.from_row(r) for r in tables['wciklink_cusip_fixture'])
    if not {r.permno for r in history} <= set(PERMNOS):
        raise ValueError('V2 history contains noncohort securities')
    if completion['sources']['wciklink_cusip_fixture']['parameters'] != {
            'cusips': sorted({h.cusip for h in history if h.cusip}) or [''],
            'full': sorted({h.cusip9 for h in history if h.cusip9}) or ['']}:
        raise ValueError('V2 links query exceeds frozen history identifiers')
    # Reproduce V1 and verify its frozen implementation hashes, never rewrite V1.
    accepted_inputs(root)
    return completion, history, links


def run_c1(root: Path = ROOT) -> dict[str, Any]:
    completion, history, links = inputs(root)
    cfg = config(root)
    requested = [(p, datetime.fromisoformat(day + 'T16:10:00').replace(
        tzinfo=ZoneInfo('America/New_York'))) for p in PERMNOS for day in cfg['as_of_dates']]
    results = [resolve(p, t, history, links) for p, t in requested]
    checks = [invariance(p, t, history, links) for p, t in requested]
    if not all(all(c.values()) for c in checks):
        raise ValueError('V2 future invariance failed')
    rows = [{**r.row(), 'selection_manifest_sha256': SELECTION_SHA256} for r in results]
    output = root / OUTPUT
    result_hash = publish_rows(output / 'c1_identity_samples.parquet', rows)
    roster_rows: list[dict[str, Any]] = []
    for result in results:
        if (len(result.candidate_ciks) == 1 and (
                result.resolution_status == 'RESOLVED_PENDING_SEC_CONFIRMATION'
                or result.resolution_reason == 'SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED')):
            roster_rows.append({
                'security_id': result.security_id, 'as_of_timestamp': result.as_of_timestamp,
                'as_of_date': result.as_of_date, 'cik': result.candidate_ciks[0],
                'first_evidence_date': result.cik_evidence_first_date,
                'same_day': result.resolution_reason == 'SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED'})
    roster = {'phase': 'V2_C2_REQUEST_ROSTER', 'selection_manifest_sha256': SELECTION_SHA256,
              'selection_commit': cfg['selection_commit'], 'permnos': PERMNOS,
              'c1_results_sha256': result_hash, 'observations': roster_rows,
              'authorized_ciks': sorted({r['cik'] for r in roster_rows}),
              'submissions_per_cik': 1, 'headers_per_cik': cfg['headers_per_cik'],
              'historical_shard_expansion': False, 'resampling': False}
    roster_hash = publish_json(output / 'sec_request_roster.json', roster)
    summary = {'phase': 'V2_C1', 'DATA-02': 'IN PROGRESS', 'Gate A': 'BLOCKED',
               'selection_state': 'FROZEN_6', 'cik_link_extraction': 'COMPLETE',
               'resampling': 'PROHIBITED', 'permnos': PERMNOS,
               'selection_manifest_sha256': SELECTION_SHA256,
               'selection_commit': cfg['selection_commit'],
               'config_sha256': digest((root / CONFIG).read_bytes()),
               'wrds_completion_manifest_sha256': digest(
                   (root / RAW / 'wrds_fixture_manifest.json').read_bytes()),
               'input_source_hashes': {k: v['content_hash'] for k, v in completion['sources'].items()},
               'observation_count': len(rows), 'status_counts': dict(Counter(
                   r.resolution_status for r in results)),
               'reason_counts': dict(Counter(r.resolution_reason for r in results)),
               'future_invariance': {name: {'passed': sum(c[name] for c in checks),
                                          'total': len(checks)} for name in checks[0]},
               'nonvacuous_future_history_observations': sum(
                   any(h.start > t.date() for h in history) for _, t in requested),
               'nonvacuous_future_link_observations': sum(
                   any(link.first and link.first > t.date() for link in links) for _, t in requested),
               'licensed_output_sha256': result_hash, 'sec_request_roster_sha256': roster_hash,
               'eligible_sec_observations': len(roster_rows),
               'eligible_sec_ciks': roster['authorized_ciks'],
               'phase_a_resolver_sha256': digest((root / 'src/data/identity/phase_a.py').read_bytes()),
               'implementation_sha256': digest(Path(__file__).read_bytes()),
               'sampling_description': 'precommitted deterministic semantic-validation cohort'}
    publish_json(output / 'c1_manifest.json', summary)
    return summary


def c1_rows(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = run_c1(root)
    data = (root / OUTPUT / 'c1_identity_samples.parquet').read_bytes()
    return summary, list(pq.read_table(pa.BufferReader(data)).to_pylist())


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['c1', 'c2'], default='c1')
    args = parser.parse_args()
    print(json.dumps(run_c1() if args.phase == 'c1' else run_c2(), sort_keys=True))


def run_c2(root: Path = ROOT) -> dict[str, Any]:
    from ..providers.sec_v2 import accession_plan, header_url, metadata_url, verify_source

    c1, rows = c1_rows(root)
    output, raw = root / OUTPUT, root / SEC_RAW
    roster = json.loads((output / 'sec_request_roster.json').read_bytes())
    acquisition_path = raw / 'sec_acquisition_manifest.json'
    acquisition = json.loads(acquisition_path.read_bytes())
    if (acquisition['selection_manifest_sha256'] != SELECTION_SHA256
            or acquisition['config_sha256'] != digest((root / CONFIG).read_bytes())
            or acquisition['c1_manifest_sha256'] != digest((output / 'c1_manifest.json').read_bytes())
            or acquisition['acquisition_complete'] is not True
            or acquisition['historical_shard_expansion'] is not False
            or set(acquisition['submissions']) != set(roster['authorized_ciks'])):
        raise ValueError('SEC acquisition does not bind to frozen C1')
    payloads = {}
    for cik, record in acquisition['submissions'].items():
        body = verify_source(raw, metadata_url(cik), record, header=False)
        if body is not None:
            payloads[cik] = body
    # Reconstruct the metadata-only accession plan before examining raw header outcomes.
    plan = accession_plan(roster, acquisition['submissions'], payloads, config(root))
    plan_bytes = (output / 'sec_accession_roster.json').read_bytes()
    if (plan_bytes != json_bytes(plan)
            or acquisition['accession_roster_sha256'] != digest(plan_bytes)):
        raise ValueError('SEC accession roster does not reproduce')
    expected = {(c['cik'], a) for c in plan['candidates'] for a in c['headers']}
    headers = acquisition['headers']
    if (len(headers) != len(expected)
            or {(c['cik'], c['accessionNumber']) for c in headers} != expected):
        raise ValueError('SEC header case set differs from frozen accession roster')
    checked = {}
    for record in headers:
        cik, accession = record['cik'], record['accessionNumber']
        source_record = {k: v for k, v in record.items() if k not in {'cik', 'accessionNumber'}}
        body = verify_source(raw, header_url(cik, accession), source_record, header=True)
        evidence = {'cik': cik, 'accessionNumber': accession,
                    'status': 'PENDING_SOURCE_UNAVAILABLE'}
        if body is not None:
            try:
                parsed = parse_header(body, accession)  # existing FILER/time semantics
                candidate = next(c for c in plan['candidates'] if c['cik'] == cik)
                secondary = next(r for r in candidate['required_accessions']
                                 if r['accessionNumber'] == accession)
                if (parsed['form'] != secondary['form']
                        or parsed['filingDate'] != secondary['filingDate']):
                    raise ValueError('Raw/structured accession fields disagree')
                evidence.update(parsed, status='RETRIEVED',
                                acceptance_source='RAW_SGML_EASTERN_PER_P1_02',
                                secondary_acceptance_datetime=secondary['acceptanceDateTime'],
                                sgml_minus_secondary_seconds=(
                                    datetime.fromisoformat(parsed['acceptance_datetime']) -
                                    datetime.fromisoformat(secondary['acceptanceDateTime'].replace(
                                        'Z', '+00:00'))).total_seconds(),
                                source_sha256=record['receipt']['sha256'])
            except (ValueError, TypeError, KeyError):
                evidence['reason'] = 'INVALID_RAW_HEADER_OR_ACCESSION_BINDING'
        checked[(cik, accession)] = evidence
    final_rows = []
    for row in rows:
        result = {**row, 'phase_c1_status': row['resolution_status'],
                  'final_status': row['resolution_status'], 'accession_checks': [],
                  'resolved_cik': None, 'coverage': None, 'header_acquisition': None}
        eligible = next((r for r in roster['observations']
                         if (r['security_id'], r['as_of_timestamp']) ==
                         (row['security_id'], row['as_of_timestamp'])), None)
        if eligible is not None:
            cik = eligible['cik']
            candidate = next(c for c in plan['candidates'] if c['cik'] == cik)
            assignment = next(r for r in candidate['observations']
                              if (r['security_id'], r['as_of_timestamp']) ==
                              (row['security_id'], row['as_of_timestamp']))
            checks = []
            if candidate['header_acquisition'] == 'WITHIN_CAP':
                for accession in assignment['accessions']:
                    evidence = checked[(cik, accession)]
                    # A same-day WRDS link needs the accession on that first-evidence day.
                    if (eligible['same_day'] and evidence.get('status') == 'RETRIEVED'
                            and evidence['filingDate'] != eligible['first_evidence_date']):
                        raise ValueError('Same-day accession does not evidence first date')
                    checks.append({'accessionNumber': accession, 'status': case_status(
                        evidence, cik, datetime.fromisoformat(row['as_of_timestamp']))})
            states = {r['status'] for r in checks}
            status = next((s for s in ('AMBIGUOUS', 'SEC_CONFIRMED', 'PENDING_SOURCE_UNAVAILABLE',
                                       'NOT_YET_AVAILABLE', 'ROLE_CONFLICT') if s in states),
                          'PENDING_SOURCE_UNAVAILABLE')
            result.update(final_status=status, accession_checks=checks, resolved_cik=cik,
                          coverage=assignment['coverage'],
                          header_acquisition=candidate['header_acquisition'])
        final_rows.append(result)
    if any(r['final_status'] not in STATUSES for r in final_rows):
        raise ValueError('Every eligible C1 observation must receive a final audit status')
    result_hash = publish_rows(output / 'c2_identity_samples.parquet', final_rows)
    _, _, v1_results, _ = accepted_inputs(root)
    v1_path = root / 'artifacts/gate_a/identity_spine/sgml_confirmation_manifest.json'
    v1 = json.loads(v1_path.read_bytes())
    v1_data = (v1_path.parent / 'sgml_identity_samples.parquet').read_bytes()
    if digest(v1_data) != v1['licensed_output_sha256']:
        raise ValueError('V1 confirmed output hash mismatch')
    v1_rows = pq.read_table(pa.BufferReader(v1_data)).to_pylist()
    v1_ciks = {r['cik'] for r in v1_rows if r['sgml_status'] == 'SEC_CONFIRMED'}
    if sorted(v1_ciks) != v1['confirmed_ciks'] or len(v1_ciks) != 2:
        raise ValueError('V1 confirmed issuer baseline changed')
    v1_overlay = {(r['security_id'], r['as_of_timestamp']): r['sgml_status'] for r in v1_rows}
    v1_counts = Counter(v1_overlay.get((r.security_id, r.as_of_timestamp), r.resolution_status)
                        for r in v1_results)
    counts = {s: sum(r['final_status'] == s for r in final_rows) for s in STATUSES}
    ciks = sorted({r['resolved_cik'] for r in final_rows if r['final_status'] == 'SEC_CONFIRMED'})
    total = sorted(v1_ciks | set(ciks))
    amendment_ciks = {r['cik'] for r in roster['observations'] if r['security_id'] == 10002}
    summary = {
        'phase': 'V2_C1_C2', 'DATA-02': 'IN PROGRESS', 'Gate A': 'BLOCKED',
        'selection_state': 'FROZEN_6', 'cik_link_extraction': 'COMPLETE',
        'resampling': 'PROHIBITED', 'permnos': PERMNOS,
        'selection_manifest_sha256': SELECTION_SHA256, 'selection_commit': config(root)['selection_commit'],
        'links_or_sec_outcomes_inspected_before_freeze': False,
        'observation_count': len(final_rows), 'v2_status_counts': counts,
        'v2_sec_confirmed_observations': counts['SEC_CONFIRMED'],
        'v2_unique_sec_confirmed_issuers': len(ciks), 'v2_confirmed_ciks': ciks,
        'v1_unique_sec_confirmed_issuers': len(v1_ciks), 'v1_confirmed_ciks': sorted(v1_ciks),
        'total_unique_sec_confirmed_issuers': len(total), 'total_confirmed_ciks': total,
        'v1_plus_v2_status_counts': {s: v1_counts[s] + counts[s] for s in STATUSES},
        'original_issuer_count_requirement_satisfied': len(total) >= 5,
        'disposition': 'ISSUER_COUNT_MET_NOT_RESEARCH_APPROVAL' if len(total) >= 5
        else 'STOPPED_BELOW_FIVE_ISSUERS_NO_RESAMPLING',
        'per_security_counts': [{'permno': p, 'counts': {s: sum(
            r['security_id'] == p and r['final_status'] == s for r in final_rows) for s in STATUSES}}
            for p in PERMNOS],
        'all_observations': [{k: r.get(k) for k in (
            'security_id', 'as_of_date', 'as_of_timestamp', 'phase_c1_status', 'resolution_reason',
            'final_status', 'resolved_cik', 'coverage', 'header_acquisition', 'accession_checks')}
            for r in final_rows],
        'amendment_slot': {'permno': 10002, 'replacement_allowed': False,
                           'status': 'POST_FREEZE_BOUNDED_INSPECTION' if amendment_ciks else
                           'NOT_ASSESSED_NO_ELIGIBLE_CIK', 'ciks': sorted(amendment_ciks)},
        'c1_manifest_sha256': digest((output / 'c1_manifest.json').read_bytes()),
        'sec_acquisition_manifest_sha256': digest(acquisition_path.read_bytes()),
        'sec_accession_roster_sha256': digest(plan_bytes),
        'v1_sgml_manifest_sha256': digest(v1_path.read_bytes()),
        'licensed_output_sha256': result_hash,
        'implementation_sha256': {
            str(p.relative_to(root)): digest(p.read_bytes()) for p in (
                root / 'src/data/identity/v2_resolution.py', root / 'src/data/providers/sec_v2.py')},
        'sampling_description': 'precommitted deterministic semantic-validation cohort',
        'limitations': ['Not a representative random sample.',
                        'One bounded root submissions response per eligible CIK; no historical shards.',
                        'At most three deduplicated accession headers per CIK; missing evidence stays pending.',
                        'Raw SGML is authoritative; submissions membership alone does not prove FILER.',
                        'No CCM/GVKEY, resampling or resolver changes.'],
    }
    publish_json(output / 'c2_manifest.json', summary)
    return summary


if __name__ == '__main__':
    main()
