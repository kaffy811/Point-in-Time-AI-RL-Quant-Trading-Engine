"""Synthetic parser tests are not substitutes for the four real header fixtures."""
from datetime import datetime
import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from src.data.identity.sgml_audit import case_status, parse_header, run
from src.data.providers.sec_sgml import read_header, retrieve, source_url

ACC = '0001013762-11-002352'
CIK = '0001505611'
ROOT = Path(__file__).resolve().parents[4]


def header(roles: str = 'FILER', clock: str = '20110822171224') -> bytes:
    blocks = ''.join(f'\n{role}:\n\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t{cik}\n'
                     for role, cik in (r.split('=') if '=' in r else (r, CIK)
                                       for r in roles.split(',')))
    return (f'<SEC-HEADER>x\n<ACCEPTANCE-DATETIME>{clock}\nACCESSION NUMBER:\t{ACC}\n'
            f'FILED AS OF DATE:\t20110822\nCONFORMED SUBMISSION TYPE:\t10-Q\n'
            f'{blocks}</SEC-HEADER>').encode()


def test_roles_and_exact_availability() -> None:
    data = {'status': 'RETRIEVED', **parse_header(header(), ACC)}
    assert data['acceptance_datetime'] == '2011-08-22T21:12:24+00:00'
    assert case_status(data, CIK, datetime.fromisoformat('2011-08-22T21:12:24+00:00')) == 'SEC_CONFIRMED'
    assert case_status(data, CIK, datetime.fromisoformat('2011-08-22T21:12:23+00:00')) == 'NOT_YET_AVAILABLE'
    conflict = {'status': 'RETRIEVED', **parse_header(
        header('SUBJECT COMPANY,FILED BY=0001019432'), ACC)}
    assert case_status(conflict, CIK, datetime.now().astimezone()) == 'ROLE_CONFLICT'
    multiple = {'status': 'RETRIEVED', **parse_header(header('FILER,FILER=0001019432'), ACC)}
    assert case_status(multiple, CIK, datetime.now().astimezone()) == 'AMBIGUOUS'
    assert case_status({'status': 'PENDING_SOURCE_UNAVAILABLE'}, CIK,
                       datetime.now().astimezone()) == 'PENDING_SOURCE_UNAVAILABLE'


@pytest.mark.parametrize('content', [header(clock='20111106013000'), header(clock='20110313023000'),
    header().replace(ACC.encode(), b'0000000000-11-000000'),
    header().replace(b'</SEC-HEADER>', b''),
    header().replace(b'\t\tCENTRAL INDEX KEY:', b'\tCENTRAL INDEX KEY:'),
    header().replace(b'</SEC-HEADER>', b'\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t0001019432\n</SEC-HEADER>'),
    header() + header()])
def test_malformed_or_ambiguous_header_fails_closed(content: bytes) -> None:
    with pytest.raises(ValueError):
        parse_header(content, ACC)


def test_bounded_header_reads() -> None:
    data = header()
    saved, received = read_header(io.BytesIO(data + b'x' * 100000), 65536)
    assert saved == data
    assert received <= 65536
    with pytest.raises(ValueError):
        read_header(io.BytesIO(b'x' * 100000), 65536)
    with pytest.raises(ValueError):
        source_url('0001293330', ACC)


def test_three_503_attempts_per_fixed_accession(tmp_path: Path) -> None:
    cfg = ROOT / 'configs/gate_a_data_02_sgml.json'
    config = json.loads(cfg.read_bytes())
    raw = tmp_path / config['sec_fixture_directory']
    raw.mkdir(parents=True)
    (raw / 'sec_fixture_manifest.json').write_text(json.dumps({'selected_accessions': config['cases']}))
    error = HTTPError('test', 503, 'Unavailable', {}, None)
    with patch('src.data.providers.sec_sgml.build_opener') as opener, \
            patch('src.data.providers.sec_sgml.time.sleep') as sleep:
        opener.return_value.open.side_effect = error
        result = retrieve(cfg, 'Test contact@example.org', tmp_path)
    assert opener.return_value.open.call_count == 12
    assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1, 2] * 4
    assert all(len(c['attempts']) == 3 and c['status'] == 'PENDING_SOURCE_UNAVAILABLE'
               for c in result['cases'])
    assert not list(raw.glob('*.sgml'))


def test_real_evidence_reproducible_and_phase_a_unchanged() -> None:
    directory = ROOT / 'data/raw/sec/gate_a/data_02'
    if not (directory / 'sgml_fixture_manifest.json').exists():
        pytest.skip('Licensed/local real fixtures unavailable')
    before = (ROOT / 'artifacts/gate_a/identity_spine/identity_samples.parquet').read_bytes()
    first = run()
    assert first == run()
    assert first['observation_status_counts'] == {
        'SEC_CONFIRMED': 8, 'ROLE_CONFLICT': 2, 'NOT_YET_AVAILABLE': 0,
        'PENDING_SOURCE_UNAVAILABLE': 0, 'AMBIGUOUS': 0}
    assert first['unique_sec_confirmed_issuers'] == 2
    assert before == (ROOT / 'artifacts/gate_a/identity_spine/identity_samples.parquet').read_bytes()
