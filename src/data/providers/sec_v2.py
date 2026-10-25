"""V2 SEC acquisition restricted to the verified frozen C1 and accession rosters."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .sec_identity import FIELDS
from .sec_sgml import SameURLRedirect, read_header
from ...utils.artifacts import digest, json_bytes
from ..identity.audit import ROOT
from ..identity.sec_confirmation import accepted_instant
from ..identity.v2_resolution import (
    CONFIG, OUTPUT, SEC_RAW, SELECTION_SHA256, c1_rows, config, publish, publish_json,
)


def metadata_url(cik: str) -> str:
    if not re.fullmatch(r'\d{10}', cik) or int(cik) == 0:
        raise ValueError('Invalid roster CIK')
    return f'https://data.sec.gov/submissions/CIK{cik}.json'


def header_url(cik: str, accession: str) -> str:
    metadata_url(cik)
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
        raise ValueError('Invalid roster accession')
    return (f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/'
            f'{accession.replace("-", "")}/{accession}.txt')


def submission_rows(body: bytes, cik: str) -> list[dict[str, Any]]:
    obj = json.loads(body)
    if str(obj['cik']).zfill(10) != cik:
        raise ValueError('SEC submissions CIK mismatch')
    recent = obj['filings']['recent']
    if (not all(isinstance(recent.get(k), list) for k in FIELDS)
            or len({len(recent[k]) for k in FIELDS}) != 1):
        raise ValueError('SEC submissions fields/lengths mismatch')
    rows = [{k: recent[k][i] for k in FIELDS} for i in range(len(recent['accessionNumber']))]
    if len({r['accessionNumber'] for r in rows}) != len(rows):
        raise ValueError('Duplicate SEC accession in submissions')
    for row in rows:
        header_url(cik, row['accessionNumber'])
        if not all(isinstance(row[k], str) for k in FIELDS):
            raise ValueError('SEC metadata fields must be source strings')
        # Strict dates/aware acceptance for deterministic selection; no timezone guesses.
        if datetime.strptime(row['filingDate'], '%Y-%m-%d').date().isoformat() != row['filingDate']:
            raise ValueError('Invalid SEC filing date')
        accepted_instant(row['acceptanceDateTime'])
    return rows


def accession_plan(roster: dict[str, Any], sources: dict[str, dict[str, Any]],
                   payloads: dict[str, bytes], cfg: dict[str, Any]) -> dict[str, Any]:
    """No raw-header outcome participates in this deterministic accession decision."""
    candidates = []
    for cik in roster['authorized_ciks']:
        source = sources[cik]
        rows: list[dict[str, Any]] = []
        source_status = source['status']
        if source_status == 'RETRIEVED':
            try:
                rows = submission_rows(payloads[cik], cik)
            except (ValueError, TypeError, KeyError):
                source_status = 'INVALID_SUBMISSIONS_SOURCE'
        selected = {}
        assignments = []
        for observation in [r for r in roster['observations'] if r['cik'] == cik]:
            prior = [r for r in rows if r['form'] in cfg['issuer_forms']
                     and r['filingDate'] <= observation['as_of_date']]
            prior.sort(key=lambda r: (r['filingDate'], accepted_instant(r['acceptanceDateTime']),
                                      r['accessionNumber']))
            same_day = [r for r in rows if observation['same_day']
                        and r['filingDate'] == observation['first_evidence_date']]
            for row in (prior[-1:] + same_day):
                selected[row['accessionNumber']] = row
            relevant = same_day if observation['same_day'] else prior[-1:]
            assignments.append({**observation,
                                'accessions': sorted(r['accessionNumber'] for r in relevant),
                                'coverage': 'SELECTED' if relevant else
                                'NO_REQUIRED_ACCESSION_IN_BOUNDED_RESPONSE'})
        exceeded = len(selected) > cfg['headers_per_cik']
        candidates.append({
            'cik': cik, 'submissions_status': source_status,
            'submissions_receipt': source.get('receipt'), 'observations': assignments,
            'required_accessions': [selected[a] for a in sorted(selected)],
            'header_acquisition': 'CAP_EXCEEDED_NO_SUBSET' if exceeded else 'WITHIN_CAP',
            'headers': [] if exceeded else sorted(selected),
            'amendments_in_bounded_response': sum(r['form'].endswith('/A') for r in rows)
            if source_status == 'RETRIEVED' else None,
            'amendment_inspection_timing': 'AFTER_COMMITTED_SELECTION_FREEZE',
        })
    return {'phase': 'V2_C2_ACCESSION_ROSTER', 'selection_manifest_sha256': SELECTION_SHA256,
            'request_roster_sha256': digest(json_bytes(roster)),
            'historical_shard_expansion': False, 'candidates': candidates,
            'policy': 'LATEST_ISSUER_FORM_AT_OR_BEFORE_FIXED_ASOF_PLUS_SAME_DAY_FIRST_EVIDENCE',
            'header_outcomes_inspected_before_accession_roster': False}


def verify_source(directory: Path, url: str, record: dict[str, Any], *, header: bool) -> bytes | None:
    """Offline verification binds acquisition records to exact cached URL/source bytes."""
    key = digest(url.encode())
    outcome = directory / (key + '.outcome.json')
    target = directory / (key + ('.sgml' if header else '.json'))
    if (record['url'] != url or outcome.is_symlink()
            or json.loads(outcome.read_bytes()) != record):
        raise ValueError('SEC cached outcome binding mismatch')
    if record['status'] != 'RETRIEVED':
        if record['status'] != 'PENDING_SOURCE_UNAVAILABLE' or target.exists():
            raise ValueError('Invalid SEC failed cache')
        return None
    content = target.read_bytes()
    receipt = record['receipt']
    cap = 65536 if header else 2097152
    if (target.is_symlink() or receipt['path'] != target.name or receipt['url'] != url
            or receipt['sha256'] != digest(content) or receipt['bytes'] != len(content)
            or len(content) > cap):
        raise ValueError('SEC cached source hash/size mismatch')
    return content


class _BoundClient:
    """No arbitrary URL CLI; caller derives exact URLs from durable verified rosters."""
    def __init__(self, directory: Path, user_agent: str, allowed: set[str]):
        if not re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', user_agent):
            raise ValueError('A genuine contact SEC_USER_AGENT is required locally')
        self.directory, self.user_agent, self.allowed = directory, user_agent, allowed
        directory.mkdir(parents=True, exist_ok=True)

    def fetch(self, url: str, *, header: bool) -> tuple[bytes | None, dict[str, Any]]:
        if url not in self.allowed:
            raise ValueError('SEC URL outside frozen V2 roster')
        key = digest(url.encode())
        target = self.directory / (key + ('.sgml' if header else '.json'))
        outcome = self.directory / (key + '.outcome.json')
        if outcome.exists():
            record = json.loads(outcome.read_bytes())
            return verify_source(self.directory, url, record, header=header), record
        if target.exists() or target.is_symlink() or outcome.is_symlink():
            raise ValueError('Incomplete SEC cache; preserve without overwrite')
        record = {'url': url, 'status': 'PENDING_SOURCE_UNAVAILABLE', 'attempts': []}
        attempts = 3 if header else 1
        content = None
        for attempt in range(attempts):
            time.sleep(0.5 if attempt == 0 else (1, 2)[attempt - 1])
            headers = {'User-Agent': self.user_agent, 'Accept-Encoding': 'identity'}
            if header:
                headers['Range'] = 'bytes=0-65535'
            try:
                with build_opener(SameURLRedirect()).open(Request(url, headers=headers),
                                                        timeout=20) as response:
                    if response.url != url:
                        raise ValueError('Unexpected SEC redirect')
                    if header:
                        content, received = read_header(response, 65536)
                    else:
                        content = response.read(2097153)
                        received = len(content)
                        if received > 2097152:
                            raise ValueError('SEC submissions response exceeded byte cap')
                    code = response.status
                receipt = {'url': url, 'path': target.name, 'sha256': digest(content),
                           'bytes': len(content), 'bytes_received': received,
                           'http_status': code,
                           'retrieved_at': datetime.now(timezone.utc).isoformat()}
                publish(target, content)
                record['attempts'].append({'attempt': attempt + 1, 'status': code})
                record.update(status='RETRIEVED', receipt=receipt)
                break
            except HTTPError as exc:
                record['attempts'].append({'attempt': attempt + 1, 'status': exc.code})
                content = None
                if exc.code not in {500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError):
                record['attempts'].append({'attempt': attempt + 1, 'status': 'NETWORK_ERROR'})
                content = None
            except ValueError:
                record['attempts'].append({'attempt': attempt + 1,
                                           'status': 'INVALID_OR_OVERSIZE_RESPONSE'})
                content = None
                break
        publish_json(outcome, record)
        return content, record


def retrieve(user_agent: str, root: Path = ROOT) -> dict[str, Any]:
    summary, _ = c1_rows(root)
    roster_path = root / OUTPUT / 'sec_request_roster.json'
    roster = json.loads(roster_path.read_bytes())
    if digest(roster_path.read_bytes()) != summary['sec_request_roster_sha256']:
        raise ValueError('C1 SEC request roster hash mismatch')
    cfg = config(root)
    client = _BoundClient(root / SEC_RAW, user_agent,
                          {metadata_url(cik) for cik in roster['authorized_ciks']})
    payloads, sources = {}, {}
    for cik in roster['authorized_ciks']:
        body, record = client.fetch(metadata_url(cik), header=False)
        sources[cik] = record
        if body is not None:
            payloads[cik] = body
    plan = accession_plan(roster, sources, payloads, cfg)
    plan_hash = publish_json(root / OUTPUT / 'sec_accession_roster.json', plan)
    # Only after exclusive publication may this finite header URL set be requested.
    header_urls = {header_url(c['cik'], a) for c in plan['candidates'] for a in c['headers']}
    client.allowed = header_urls
    headers = []
    for candidate in plan['candidates']:
        for accession in candidate['headers']:
            _, record = client.fetch(header_url(candidate['cik'], accession), header=True)
            headers.append({'cik': candidate['cik'], 'accessionNumber': accession, **record})
    result = {'phase': 'V2_C2_ACQUISITION', 'selection_manifest_sha256': SELECTION_SHA256,
              'config_sha256': digest((root / CONFIG).read_bytes()),
              'c1_manifest_sha256': digest((root / OUTPUT / 'c1_manifest.json').read_bytes()),
              'accession_roster_sha256': plan_hash,
              'submissions': sources, 'headers': headers, 'acquisition_complete': True,
              'historical_shard_expansion': False, 'Gate A': 'BLOCKED'}
    publish_json(root / SEC_RAW / 'sec_acquisition_manifest.json', result)
    return result


def main() -> None:
    import os
    result = retrieve(os.environ.get('SEC_USER_AGENT', ''))
    print(json.dumps({'acquisition_complete': result['acquisition_complete'],
                      'submissions': len(result['submissions']), 'headers': len(result['headers']),
                      'header_statuses': [r['status'] for r in result['headers']]}))


if __name__ == '__main__':
    main()
