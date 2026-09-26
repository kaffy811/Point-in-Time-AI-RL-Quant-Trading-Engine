"""Offline raw-header confirmation overlay; never rewrites frozen Phase A."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .audit import ROOT, digest, encoded
from .phase_b import accepted_inputs
from ..providers.sec_sgml import CASES, source_url


def parse_header(content: bytes, accession: str) -> dict[str, Any]:
    text = content.decode('ascii', errors='strict')
    headers = re.findall(r'<SEC-HEADER>.*?</SEC-HEADER>', text, re.S)
    if len(headers) != 1 or not text.endswith('</SEC-HEADER>'):
        raise ValueError('Expected one complete SEC header prefix')
    header = headers[0]

    def field(pattern: str) -> str:
        values = re.findall(pattern, header, re.M)
        if len(values) != 1:
            raise ValueError('Missing/duplicate SGML identity or acceptance field')
        return str(values[0])

    if field(r'^ACCESSION NUMBER:\s*([^\s]+)') != accession:
        raise ValueError('Raw accession mismatch')
    clock = field(r'^<ACCEPTANCE-DATETIME>(\d{14})\s*$')
    naive = datetime.strptime(clock, '%Y%m%d%H%M%S')
    zone = ZoneInfo('America/New_York')
    local = naive.replace(tzinfo=zone)
    if (local.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset()
            or local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive):
        raise ValueError('Ambiguous/nonexistent SGML Eastern timestamp')
    roles: dict[str, list[str]] = {}
    # Only a CIK in COMPANY DATA of its explicit top-level entity block counts.
    blocks = re.split(r'^([A-Z][A-Z ]+):[ \t]*$', header, flags=re.M)
    for index in range(1, len(blocks), 2):
        role, body = blocks[index:index + 2]
        if len(re.findall(r'^\tCOMPANY DATA:', body, re.M)) > 1:
            raise ValueError('Duplicate company data in role block')
        company = re.search(r'^\tCOMPANY DATA:[ \t]*\n((?:\n|\t\t[^\n]*\n)*)', body, re.M)
        if company:
            ciks = re.findall(r'^\t\tCENTRAL INDEX KEY:[ \t]*(\d{10})[ \t]*$',
                              company[1], re.M)
            if len(ciks) != 1 or int(ciks[0]) == 0:
                raise ValueError('Missing/duplicate company CIK')
            roles.setdefault(role, []).extend(ciks)
        elif role in {'FILER', 'FILED BY', 'SUBJECT COMPANY'}:
            raise ValueError('Missing company data in identity role')
    filers = sorted(set(roles.get('FILER', []) + roles.get('FILED BY', [])))
    if not filers:
        raise ValueError('No explicit filer identity')
    return {'accessionNumber': accession, 'acceptance_raw': clock,
            'acceptance_datetime': local.astimezone(timezone.utc).isoformat(),
            'filingDate': datetime.strptime(field(r'^FILED AS OF DATE:\s*(\d{8})\s*$'),
                                            '%Y%m%d').date().isoformat(),
            'form': field(r'^CONFORMED SUBMISSION TYPE:[ \t]*([^\n]+)').strip(),
            'roles': roles, 'filer_ciks': filers}


def case_status(evidence: dict[str, Any], cik: str, as_of: datetime) -> str:
    if as_of.tzinfo is None:
        raise ValueError('Timezone-aware as-of required')
    if evidence['status'] != 'RETRIEVED':
        return 'PENDING_SOURCE_UNAVAILABLE'
    filers = evidence['filer_ciks']
    if len(filers) != 1:
        return 'AMBIGUOUS'
    if cik not in filers:
        if any(cik in values for values in evidence['roles'].values()):
            return 'ROLE_CONFLICT'
        return 'PENDING_SOURCE_UNAVAILABLE'
    accepted = datetime.fromisoformat(evidence['acceptance_datetime'])
    return 'SEC_CONFIRMED' if accepted <= as_of else 'NOT_YET_AVAILABLE'


def run(root: Path = ROOT) -> dict[str, Any]:
    _, _, results, _ = accepted_inputs(root)
    directory = root / 'data/raw/sec/gate_a/data_02'
    config_path = root / 'configs/gate_a_data_02_sgml.json'
    config = json.loads(config_path.read_bytes())
    raw_manifest = directory / 'sgml_fixture_manifest.json'
    acquisition = json.loads(raw_manifest.read_bytes())
    if (acquisition['config_sha256'] != digest(config_path.read_bytes())
            or not acquisition['acquisition_complete']
            or len(acquisition['cases']) != 4
            or {(c['cik'], c['accessionNumber']) for c in acquisition['cases']} != CASES
            or config['acceptance_timezone'] != 'America/New_York'
            or config['evidence_priority'] != 'RAW_SGML_THEN_EXACT_ACCESSION_METADATA_THEN_WRDS_DATE'):
        raise ValueError('SGML acquisition/config mismatch')
    secondary_path = directory / 'sec_fixture_manifest.json'
    secondary = json.loads(secondary_path.read_bytes())
    metadata = {(r['cik'], r['accessionNumber']): r for r in secondary['selected_accessions']}
    if set(metadata) != CASES:
        raise ValueError('Secondary accession roster mismatch')
    checked = []
    for case in acquisition['cases']:
        cik, accession = case['cik'], case['accessionNumber']
        if case['url'] != source_url(cik, accession):
            raise ValueError('Unexpected source URL')
        report = dict(case)
        if case['status'] == 'RETRIEVED':
            receipt = case['receipt']
            path = directory / (accession + '.header.sgml')
            saved = json.loads((directory / (accession + '.header.receipt.json')).read_bytes())
            content = path.read_bytes()
            if (receipt != saved or receipt['url'] != case['url']
                    or receipt['path'] != path.name or path.resolve().parent != directory.resolve()
                    or digest(content) != receipt['sha256']):
                raise ValueError('Raw header receipt/source binding mismatch')
            report.update(parse_header(content, accession))
            item = metadata[(cik, accession)]
            receipts = [r for r in secondary['raw_sources']
                        if r['sha256'] == item['submissions_source_sha256']]
            if len(receipts) != 1:
                raise ValueError('Secondary receipt mismatch')
            source = receipts[0]
            source_path = directory / source['path']
            if (source_path.resolve().parent != directory.resolve() or source['url'] !=
                    f'https://data.sec.gov/submissions/CIK{cik}.json'):
                raise ValueError('Secondary source binding mismatch')
            source_bytes = source_path.read_bytes()
            if digest(source_bytes) != source['sha256']:
                raise ValueError('Secondary source hash mismatch')
            raw = json.loads(source_bytes)
            recent = raw['filings']['recent']
            indices = [i for i, value in enumerate(recent['accessionNumber']) if value == accession]
            if str(raw['cik']).zfill(10) != cik or len(indices) != 1:
                raise ValueError('Secondary exact accession mismatch')
            api_time = recent['acceptanceDateTime'][indices[0]]
            report['secondary_acceptance_datetime'] = api_time
            report['secondary_source_sha256'] = source['sha256']
            report['sgml_minus_secondary_seconds'] = (
                datetime.fromisoformat(report['acceptance_datetime']) -
                datetime.fromisoformat(api_time.replace('Z', '+00:00'))).total_seconds()
            report['acceptance_source'] = 'RAW_SGML_EASTERN_PER_P1_02'

        elif case['status'] != 'PENDING_SOURCE_UNAVAILABLE':
            raise ValueError('Unknown acquisition status')
        checked.append(report)
    rows = []
    for result in results:
        same_day = result.resolution_reason == 'SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED'
        cik = result.preliminary_cik
        if same_day and len(result.candidate_ciks) == 1:
            cik = result.candidate_ciks[0]
        if cik not in {'0001505611', '0001556266'}:
            continue
        relevant = [case for case in checked if case['cik'] == cik]
        if same_day:
            # Fixed first-evidence accession; an older issuer filing cannot time this link.
            relevant = [c for c in relevant if c['accessionNumber'] in {
                '0001019432-11-000009', '0001213900-15-004248'}]
            for case in relevant:
                if case['status'] == 'RETRIEVED' and case['filingDate'] != result.cik_evidence_first_date:
                    raise ValueError('Same-day accession does not evidence first filing date')
        checks = [{'accessionNumber': c['accessionNumber'],
                   'status': case_status(c, cik, datetime.fromisoformat(result.as_of_timestamp))}
                  for c in relevant]
        states = {c['status'] for c in checks}
        # Confirmation needs at least one unique matching filer; keep every case outcome.
        status = next((s for s in ('AMBIGUOUS', 'SEC_CONFIRMED', 'PENDING_SOURCE_UNAVAILABLE',
                                   'NOT_YET_AVAILABLE', 'ROLE_CONFLICT') if s in states),
                      'PENDING_SOURCE_UNAVAILABLE')
        rows.append({'security_id': result.security_id, 'as_of_timestamp': result.as_of_timestamp,
                     'cik': cik, 'phase_a_status': result.resolution_status, 'sgml_status': status,
                     'accession_checks': checks})
    output = root / 'artifacts/gate_a/identity_spine'
    pq.write_table(pa.Table.from_pylist(rows), output / 'sgml_identity_samples.parquet')
    counts = {s: sum(r['sgml_status'] == s for r in rows) for s in (
        'SEC_CONFIRMED', 'ROLE_CONFLICT', 'NOT_YET_AVAILABLE', 'PENDING_SOURCE_UNAVAILABLE',
        'AMBIGUOUS')}
    issuers = sorted({r['cik'] for r in rows if r['sgml_status'] == 'SEC_CONFIRMED'})
    summary = {'phase': 'B2_SGML', 'DATA-02': 'IN PROGRESS', 'Gate A': 'BLOCKED',
               'phase_a_results_unchanged': True, 'eligible_observations': len(rows),
               'observation_status_counts': counts, 'unique_sec_confirmed_issuers': len(issuers),
               'confirmed_ciks': issuers, 'remaining_phase_a_ambiguous_observations': 9,
               'original_five_issuer_requirement_satisfied': False,
               'fixture_protocol_v2': 'NOT_EXECUTED', 'accessions': checked,
               'config_sha256': digest(config_path.read_bytes()),
               'raw_manifest_sha256': digest(raw_manifest.read_bytes()),
               'secondary_manifest_sha256': digest(secondary_path.read_bytes()),
               'phase_a_manifest_sha256': digest((output / 'identity_manifest.json').read_bytes()),
               'implementation_sha256': {p.name: digest(p.read_bytes()) for p in (
                   Path(__file__), root / 'src/data/providers/sec_sgml.py')},
               'licensed_output_sha256': digest((output / 'sgml_identity_samples.parquet').read_bytes())}
    (output / 'sgml_confirmation_manifest.json').write_bytes(encoded(summary))
    lines = ['# B2 bounded SGML audit', '',
             'Latest evidence overlay; prior Phase B reports remain historical snapshots.',
             'Frozen Phase A implementation, input hashes and all 283 outcomes reproduced unchanged.',
             'Only the four already authorized accessions were requested; no v2 extraction.', '',
             '| Observation status | Count |', '|---|---:|']
    lines += [f'| {s} | {n} |' for s, n in counts.items()]
    lines += ['', f'Unique end-to-end confirmed issuers: **{len(issuers)}** ({", ".join(issuers)}).',
              'Counts cover 8 previously pending observations and 2 same-day observations.',
              'The other 264 unresolved and 9 ambiguous Phase A observations are unchanged.', '',
              '| Candidate CIK | Accession | Raw filer CIKs | Acceptance UTC |', '|---|---|---|---|']
    lines += [f"| {c['cik']} | {c['accessionNumber']} | {', '.join(c.get('filer_ciks', []))} | "
              f"{c.get('acceptance_datetime', c['status'])} |" for c in checked]
    lines += ['', 'SGML ACCEPTANCE-DATETIME is interpreted in America/New_York per P1-02,',
              'then converted to UTC. Structured metadata is secondary and cannot override it.',
              'The earlier API timestamps have the same clock text but explicit Z; the raw',
              'SGML times in these four summer filings are four hours later in UTC. Both raw',
              'sources are retained; no structured timestamp is silently relabeled.', '',
              'The two 10-Q headers identify the candidate as FILER. The two first-evidence',
              '13G/13G-A headers identify it only as SUBJECT COMPANY; FILED BY belongs to',
              'another CIK. No additional CIK was queried. Same-day observations remain unconfirmed.',
              'For later observations a separate matching issuer filing may confirm identity;',
              'all accession outcomes remain in ignored row-level audit output.', '',
              'Multiple filer identities within a header return AMBIGUOUS, never first-filer selection.',
              'All matching accepted accessions are checked against the observation timestamp.',
              'Unavailable raw sources stay pending; no weaker metadata substitution is used.', '',
              'Five suitable issuers are not validated. DATA-02 IN PROGRESS; Gate A BLOCKED.', '']
    (output / 'sgml_confirmation_report.md').write_text('\n'.join(lines))
    return summary


if __name__ == '__main__':
    print(json.dumps(run()['observation_status_counts']))
