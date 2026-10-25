"""Synthetic V2 scope/roster/status boundaries; no network or real confirmation claims."""
from datetime import date
import io
import json
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.data.identity.audit import ROOT
from src.data.identity.phase_a import History, Link
from src.data.identity.v2_resolution import (
    CONFIG, OUTPUT, PERMNOS, SEC_RAW, SELECTION_SHA256, config, inputs, publish_json, run_c1, run_c2,
)
from src.data.providers.sec_identity import FIELDS, authorized_url
from src.data.providers.sec_v2 import (
    _BoundClient, accession_plan, header_url, metadata_url, retrieve, submission_rows,
)
from src.data.providers.wrds.extract import digest, json_bytes

CIK = '0000000001'
ACC = '0000000001-10-000001'


def source_row(accession=ACC, day='2010-06-29', form='10-Q'):
    return dict(accessionNumber=accession, form=form, filingDate=day,
                acceptanceDateTime=day + 'T12:00:00Z', reportDate='', primaryDocument='x.htm')


def payload(rows, cik=CIK):
    return json_bytes({'cik': int(cik), 'filings': {
        'recent': {k: [r[k] for r in rows] for k in FIELDS},
        'files': [{'name': 'MUST_NOT_FETCH_HISTORY.json'}]}})


def roster(asofs=('2010-06-30',), same_day=False):
    return {'authorized_ciks': [CIK], 'observations': [
        {'security_id': 10026, 'as_of_timestamp': d + 'T16:10:00-04:00',
         'as_of_date': d, 'cik': CIK, 'same_day': same_day, 'first_evidence_date': d}
        for d in asofs]}


def plan(rows, asofs=('2010-06-30',), same_day=False):
    return accession_plan(roster(asofs, same_day), {CIK: {'status': 'RETRIEVED'}},
                          {CIK: payload(rows)}, config(ROOT))


def header(cik=CIK, role='FILER', clock='20100629120000'):
    return (f'<SEC-HEADER>x\n<ACCEPTANCE-DATETIME>{clock}\nACCESSION NUMBER:\t{ACC}\n'
            'FILED AS OF DATE:\t20100629\nCONFORMED SUBMISSION TYPE:\t10-Q\n'
            f'\n{role}:\n\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t{cik}\n'
            + ('\nFILED BY:\n\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t0000000002\n'
               if role == 'SUBJECT COMPANY' else '') + '</SEC-HEADER>').encode()


@pytest.fixture
def c1_corpus(tmp_path, monkeypatch):
    (tmp_path / 'configs').mkdir()
    shutil.copy(ROOT / CONFIG, tmp_path / CONFIG)
    phase_a = tmp_path / 'src/data/identity/phase_a.py'
    phase_a.parent.mkdir(parents=True)
    shutil.copy(ROOT / 'src/data/identity/phase_a.py', phase_a)
    history = tuple(History(p, date(2000, 1, 1), date(2030, 1, 1), 'X', 'X',
                            '12345678', '123456789') for p in PERMNOS[:2])
    links = (Link(CIK, '12345678', '123456789', date(2001, 1, 1), None, 3, None),)
    raw = tmp_path / 'data/raw/wrds/gate_a/data_02_v2'
    raw.mkdir(parents=True)
    completion = {'sources': {'synthetic': {'content_hash': 'synthetic-unit-only'}}}
    (raw / 'wrds_fixture_manifest.json').write_bytes(json_bytes(completion))
    monkeypatch.setattr('src.data.identity.v2_resolution.inputs',
                        lambda _: (completion, history, links))
    return tmp_path


def test_c1_all_24_in_frozen_order_and_exact_retry(c1_corpus):
    summary = run_c1(c1_corpus)
    assert summary['observation_count'] == 24
    assert summary['permnos'] == PERMNOS
    assert summary['status_counts'] == {'RESOLVED_PENDING_SEC_CONFIRMATION': 8, 'UNRESOLVED': 16}
    assert all(c['passed'] == c['total'] == 24 for c in summary['future_invariance'].values())
    data = pq.read_table(c1_corpus / OUTPUT / 'c1_identity_samples.parquet').to_pylist()
    assert [r['security_id'] for r in data] == [p for p in PERMNOS for _ in range(4)]
    assert {r['selection_manifest_sha256'] for r in data} == {SELECTION_SHA256}
    before = {p: p.read_bytes() for p in (c1_corpus / OUTPUT).iterdir()}
    assert run_c1(c1_corpus) == summary
    assert all(p.read_bytes() == body for p, body in before.items())


def test_c1_excludes_ambiguous_and_future_only_from_sec_roster(c1_corpus, monkeypatch):
    h = (History(10026, date(2000, 1, 1), date(2030, 1, 1), 'X', 'X', '12345678', '123456789'),)
    links = tuple(Link(c, '12345678', '123456789', date(2001, 1, 1), None, 3, None)
                  for c in (CIK, '0000000002'))
    monkeypatch.setattr('src.data.identity.v2_resolution.inputs',
                        lambda _: ({'sources': {}}, h, links))
    summary = run_c1(c1_corpus)
    assert summary['status_counts'] == {'AMBIGUOUS': 4, 'UNRESOLVED': 20}
    r = json.loads((c1_corpus / OUTPUT / 'sec_request_roster.json').read_bytes())
    assert r['authorized_ciks'] == [] and r['observations'] == []


@pytest.mark.parametrize('key,value', [('permnos', list(reversed(PERMNOS))),
    ('resampling', True), ('as_of_dates', ['2026-01-01']), ('headers_per_cik', 4),
    ('historical_shard_expansion', True), ('issuer_forms', ['SC 13G'])])
def test_resolution_config_drift_fails_closed(c1_corpus, key, value):
    path = c1_corpus / CONFIG
    cfg = json.loads(path.read_bytes())
    cfg[key] = value
    path.write_bytes(json_bytes(cfg))
    with pytest.raises(ValueError, match='config mismatch'):
        run_c1(c1_corpus)


def test_roster_latest_before_asof_deduplicates_and_ignores_future():
    future = source_row('0000000001-30-000001', '2030-06-29')
    p = plan([source_row(), future], ('2010-06-30', '2015-06-30'))['candidates'][0]
    assert p['headers'] == [ACC]
    assert [r['accessions'] for r in p['observations']] == [[ACC], [ACC]]
    assert not authorized_url(metadata_url(CIK))  # original two-CIK allowlist stays fixed


def test_cap_exceeded_never_selects_outcome_subset():
    dates = ('2010-06-30', '2015-06-30', '2020-06-30', '2025-06-30')
    rows = [source_row(f'0000000001-{year}-000001', '20' + year + '-06-29')
            for year in ('10', '15', '20', '25')]
    p = plan(rows, dates)['candidates'][0]
    assert p['header_acquisition'] == 'CAP_EXCEEDED_NO_SUBSET' and p['headers'] == []
    assert len(p['required_accessions']) == 4
    assert len(p['observations']) == 4


def test_same_day_first_evidence_can_only_use_that_date():
    same = source_row('0000000001-10-000002', '2010-06-30', 'SC 13G/A')
    p = plan([source_row(), same], same_day=True)['candidates'][0]
    assert p['observations'][0]['accessions'] == [same['accessionNumber']]
    assert p['headers'] == sorted([ACC, same['accessionNumber']])
    assert p['amendments_in_bounded_response'] == 1


@pytest.mark.parametrize('bad', ['cik', 'arrays', 'duplicate', 'timezone'])
def test_invalid_metadata_cannot_authorize_headers(bad):
    obj = json.loads(payload([source_row()]))
    if bad == 'cik':
        obj['cik'] = 2
    elif bad == 'arrays':
        obj['filings']['recent']['form'] = []
    elif bad == 'duplicate':
        obj = json.loads(payload([source_row(), source_row()]))
    else:
        obj['filings']['recent']['acceptanceDateTime'] = ['2010-06-29T12:00:00']
    with pytest.raises(ValueError):
        submission_rows(json_bytes(obj), CIK)
    p = accession_plan(roster(), {CIK: {'status': 'RETRIEVED'}}, {CIK: json_bytes(obj)},
                       config(ROOT))['candidates'][0]
    assert p['submissions_status'] == 'INVALID_SUBMISSIONS_SOURCE' and p['headers'] == []


def mock_http(monkeypatch, body, url, *, error=None):
    response = MagicMock()
    response.__enter__.return_value = response
    response.url, response.status = url, 200
    response.read.side_effect = io.BytesIO(body).read
    opener = Mock()
    opener.open.side_effect = error
    if error is None:
        opener.open.return_value = response
    monkeypatch.setattr('src.data.providers.sec_v2.build_opener', lambda *_: opener)
    monkeypatch.setattr('src.data.providers.sec_v2.time.sleep', lambda _: None)
    return opener


def test_transport_url_bound_cache_hash_and_contact_not_persisted(tmp_path, monkeypatch):
    url = metadata_url(CIK)
    opener = mock_http(monkeypatch, payload([source_row()]), url)
    client = _BoundClient(tmp_path, 'Synthetic test contact@example.invalid', {url})
    first = client.fetch(url, header=False)
    assert client.fetch(url, header=False) == first and opener.open.call_count == 1
    assert all('contact@example.invalid' not in p.read_text() for p in tmp_path.iterdir())
    with pytest.raises(ValueError, match='outside frozen'):
        client.fetch(metadata_url('0000000002'), header=False)
    target = tmp_path / first[1]['receipt']['path']
    target.chmod(0o600)
    target.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash/size'):
        client.fetch(url, header=False)


@pytest.mark.parametrize('header_request', [True, False])
def test_finite_failures_are_preserved_without_unbounded_retry(tmp_path, monkeypatch, header_request):
    url = header_url(CIK, ACC) if header_request else metadata_url(CIK)
    opener = mock_http(monkeypatch, b'', url,
                       error=HTTPError(url, 503, 'unavailable', {}, None))
    client = _BoundClient(tmp_path, 'Synthetic test contact@example.invalid', {url})
    body, record = client.fetch(url, header=header_request)
    assert body is None and record['status'] == 'PENDING_SOURCE_UNAVAILABLE'
    expected = 3 if header_request else 1
    assert len(record['attempts']) == opener.open.call_count == expected
    assert client.fetch(url, header=header_request) == (body, record)
    assert opener.open.call_count == expected


def test_oversize_root_no_evidence_and_no_shard_fallback(tmp_path, monkeypatch):
    url = metadata_url(CIK)
    opener = mock_http(monkeypatch, b'x' * 2097153, url)
    body, record = _BoundClient(tmp_path, 'Synthetic contact@example.invalid', {url}).fetch(
        url, header=False)
    assert body is None and record['status'] == 'PENDING_SOURCE_UNAVAILABLE'
    assert opener.open.call_count == 1
    assert len(list(tmp_path.iterdir())) == 1  # outcome only, no successful source receipt


def test_rosters_durable_before_each_network_stage(c1_corpus, monkeypatch):
    root = c1_corpus
    run_c1(root)
    calls = []

    def fetch(self, url, *, header):
        assert (root / OUTPUT / 'sec_request_roster.json').is_file()
        if header:
            assert (root / OUTPUT / 'sec_accession_roster.json').is_file()
            calls.append('HEADER')
            return None, {'url': url, 'status': 'PENDING_SOURCE_UNAVAILABLE', 'attempts': []}
        calls.append('SUBMISSIONS')
        return payload([source_row()]), {'url': url, 'status': 'RETRIEVED', 'receipt': {}}

    monkeypatch.setattr(_BoundClient, 'fetch', fetch)
    result = retrieve('Synthetic contact@example.invalid', root)
    assert calls == ['SUBMISSIONS', 'HEADER']
    assert result['acquisition_complete'] and len(result['headers']) == 1


def test_real_v2_input_provenance_and_frozen_resolver_unchanged():
    if not (ROOT / 'data/raw/wrds/gate_a/data_02_v2/wrds_fixture_manifest.json').exists():
        pytest.skip('Local licensed V2 fixtures absent')
    before = (ROOT / 'src/data/identity/phase_a.py').read_bytes()
    _, history, _ = inputs(ROOT)
    assert {r.permno for r in history} <= set(PERMNOS)
    assert before == (ROOT / 'src/data/identity/phase_a.py').read_bytes()


def test_publish_refuses_conflicting_audit(tmp_path):
    path = tmp_path / 'immutable.json'
    publish_json(path, {'test': 1})
    with pytest.raises(ValueError, match='without overwrite'):
        publish_json(path, {'test': 2})
    assert json.loads(path.read_bytes()) == {'test': 1}


def prepare_v1(root, monkeypatch):
    directory = root / 'artifacts/gate_a/identity_spine'
    directory.mkdir(parents=True, exist_ok=True)
    v1_rows = [{'security_id': p, 'as_of_timestamp': '2010-06-30T16:10:00-04:00',
                'cik': c, 'sgml_status': 'SEC_CONFIRMED'}
               for p, c in ((1, CIK), (2, '0000000002'))]
    path = directory / 'sgml_identity_samples.parquet'
    pq.write_table(pa.Table.from_pylist(v1_rows), path)
    publish_json(directory / 'sgml_confirmation_manifest.json', {
        'licensed_output_sha256': digest(path.read_bytes()),
        'confirmed_ciks': [CIK, '0000000002']})
    monkeypatch.setattr('src.data.identity.v2_resolution.accepted_inputs', lambda _: (
        (), (), [SimpleNamespace(security_id=r['security_id'],
                                 as_of_timestamp=r['as_of_timestamp'],
                                 resolution_status='RESOLVED_PENDING_SEC_CONFIRMATION')
                 for r in v1_rows], {}))
    for name in ('src/data/identity/v2_resolution.py', 'src/data/providers/sec_v2.py'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, path)


def acquire_synthetic(root, monkeypatch, *, raw_header=None, fail_header=False):
    calls = []

    def open_request(request, timeout):
        url = request.full_url
        calls.append(url)
        body = payload([source_row()])
        if url == header_url(CIK, ACC):
            if fail_header:
                raise HTTPError(url, 503, 'unavailable', {}, None)
            body = raw_header if raw_header is not None else header()
        else:
            assert url == metadata_url(CIK)
        response = MagicMock()
        response.__enter__.return_value = response
        response.url, response.status = url, 200
        response.read.side_effect = io.BytesIO(body).read
        return response

    opener = Mock()
    opener.open.side_effect = open_request
    monkeypatch.setattr('src.data.providers.sec_v2.build_opener', lambda *_: opener)
    monkeypatch.setattr('src.data.providers.sec_v2.time.sleep', lambda _: None)
    retrieve('Synthetic contact@example.invalid', root)
    return calls


@pytest.mark.parametrize('mode,expected', [
    ('filer', {'SEC_CONFIRMED': 8}), ('subject', {'ROLE_CONFLICT': 8}),
    ('late', {'SEC_CONFIRMED': 6, 'NOT_YET_AVAILABLE': 2}),
    ('ambiguous', {'AMBIGUOUS': 8}), ('unavailable', {'PENDING_SOURCE_UNAVAILABLE': 8})])
def test_c2_all_observations_roles_time_and_unique_issuer_union(c1_corpus, monkeypatch, mode, expected):
    root = c1_corpus
    prepare_v1(root, monkeypatch)
    raw_header = header()
    if mode == 'subject':
        raw_header = header(role='SUBJECT COMPANY')
    elif mode == 'late':
        raw_header = header(clock='20100630170000')
    elif mode == 'ambiguous':
        raw_header = header().replace(b'</SEC-HEADER>',
            b'\nFILER:\n\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t0000000002\n</SEC-HEADER>')
    calls = acquire_synthetic(root, monkeypatch, raw_header=raw_header,
                              fail_header=mode == 'unavailable')
    result = run_c2(root)
    assert result['observation_count'] == 24
    assert len(result['all_observations']) == 24
    assert result['v2_status_counts'] == {s: expected.get(s, 16 if s == 'UNRESOLVED' else 0)
                                         for s in result['v2_status_counts']}
    # V1 CIK=1 is also in V2: union must not count it twice.
    assert result['total_unique_sec_confirmed_issuers'] == 2
    assert result['original_issuer_count_requirement_satisfied'] is False
    assert result['disposition'] == 'STOPPED_BELOW_FIVE_ISSUERS_NO_RESAMPLING'
    assert sum(result['v1_plus_v2_status_counts'].values()) == 26
    assert [r['permno'] for r in result['per_security_counts']] == PERMNOS
    assert all(sum(r['counts'].values()) == 4 for r in result['per_security_counts'])
    assert result['amendment_slot']['permno'] == 10002
    assert result['amendment_slot']['status'] == 'NOT_ASSESSED_NO_ELIGIBLE_CIK'
    assert result['Gate A'] == 'BLOCKED'
    assert calls.count(metadata_url(CIK)) == 1
    assert len(calls) == (4 if mode == 'unavailable' else 2)
    before = {p: p.read_bytes() for p in (root / OUTPUT).iterdir()}
    assert run_c2(root) == result
    assert all(p.read_bytes() == body for p, body in before.items())
    # All row-level outputs are traceable; no case disappeared on failed SEC evidence.
    rows = pq.read_table(root / OUTPUT / 'c2_identity_samples.parquet').to_pylist()
    assert [r['security_id'] for r in rows] == [p for p in PERMNOS for _ in range(4)]
    assert {r['selection_manifest_sha256'] for r in rows} == {SELECTION_SHA256}


def test_c2_tampered_source_or_accession_roster_fails_closed(c1_corpus, monkeypatch):
    root = c1_corpus
    prepare_v1(root, monkeypatch)
    acquire_synthetic(root, monkeypatch)
    path = root / SEC_RAW / (digest(header_url(CIK, ACC).encode()) + '.sgml')
    path.chmod(0o600)
    path.write_bytes(header() + b'tampered')
    with pytest.raises(ValueError, match='hash/size'):
        run_c2(root)
    assert not (root / OUTPUT / 'c2_manifest.json').exists()


def test_runtime_offline_audit_imports_do_not_load_wrds_connector():
    result = subprocess.run([sys.executable, '-c',
        'import sys; import src.data.identity.v2_resolution; import src.data.providers.sec_v2; '
        'assert not any(n.startswith("src.data.providers.wrds") or n == "wrds" '
        'for n in sys.modules)'], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
