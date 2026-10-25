"""Mocked V2 selection/acquisition tests; never counted as real research evidence."""
from datetime import date
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd
import pytest

from src.data.providers.wrds.fixture_v2 import ROOT, acquire, choose
from src.data.providers.wrds.extract import digest
from src.data.providers.wrds.v2_diagnostics import FINGERPRINT, FREEZE, RAW


def catalog() -> list[dict[str, Any]]:
    return [{'permno': 10000 + i, 'first_date': date(2000, 1, 1),
             'last_date': date(2025, 12, 31), 'ticker_count': 1 + (i in (1, 4)),
             'symbol_count': 1, 'cusip_count': 1 + (i in (2, 4)),
             'membership_change': i == 3} for i in range(8)]


def test_deterministic_metadata_only_six() -> None:
    rows = catalog()
    selected = choose(rows)
    assert [r['permno'] for r in selected] == list(range(10000, 10006))
    assert selected == choose(list(reversed(rows)))
    for row in rows:
        row.update(validated=0, cik=None, resolver_outcome='UNRESOLVED', returns=-999)
    assert selected == choose(rows)
    assert len({r['permno'] for r in selected}) == 6


def test_fallback_and_invalid_catalog() -> None:
    rows = catalog()
    for row in rows:
        row.update(ticker_count=1, cusip_count=1, membership_change=False)
    assert choose(rows)[1]['fallback'] == 'LOWEST_UNUSED_PERMNO'
    with pytest.raises(ValueError):
        choose(rows[:5])
    with pytest.raises(ValueError):
        choose(rows + rows)


def prepare(tmp_path: Path) -> None:
    (tmp_path / 'configs').mkdir()
    shutil.copy(ROOT / 'configs/gate_a_data_02_v2.json', tmp_path / 'configs')


class MockConnector:
    def __init__(self, root: Path, oversize: bool = False):
        self.root, self.calls, self.oversize = root, 0, oversize

    def query(self, sql: str, params: dict[str, Any]) -> Any:
        self.calls += 1
        frozen = self.root / 'artifacts/gate_a/identity_spine/v2_selection_manifest.json'
        if self.calls == 1:
            assert not frozen.exists()
            assert 'wrdssec' not in sql and 'returns' not in sql
            return pd.DataFrame(catalog())
        assert frozen.exists()
        assert len(json.loads(frozen.read_bytes())['selected']) == 6
        assert (self.root / FINGERPRINT).read_text() == digest(frozen.read_bytes()) + '\n'
        if self.calls == 2:
            assert len(params['permnos']) == 6
            return pd.DataFrame([{'permno':10000,'cusip':'12345678','cusip9':'123456789'}]
                                * (501 if self.oversize else 1))
        assert self.calls == 3
        return pd.DataFrame({'cik': [], 'cusip': []})


def test_freeze_precedes_link_query_and_rerun_reuses(tmp_path: Path) -> None:
    prepare(tmp_path)
    connector = MockConnector(tmp_path)
    acquire(connector, tmp_path)  # type: ignore[arg-type]
    assert connector.calls == 3
    before = (tmp_path / FREEZE).read_bytes()
    acquire(connector, tmp_path)  # type: ignore[arg-type]
    assert (tmp_path / FREEZE).read_bytes() == before
    assert connector.calls == 3


def test_cap_stops_without_resampling(tmp_path: Path) -> None:
    prepare(tmp_path)
    connector = MockConnector(tmp_path, oversize=True)
    with pytest.raises(ValueError, match='cap exceeded'):
        acquire(connector, tmp_path)  # type: ignore[arg-type]
    assert connector.calls == 2
    assert (tmp_path / 'artifacts/gate_a/identity_spine/v2_selection_manifest.json').exists()


@pytest.mark.parametrize('field,value', [('protocol','other'), ('candidate_order','DESC'),
    ('as_of_dates',['2025-12-31']), ('signal_time','00:00 UTC')])
def test_config_drift_stops_before_queries(tmp_path: Path, field: str, value: Any) -> None:
    prepare(tmp_path)
    path = tmp_path / 'configs/gate_a_data_02_v2.json'
    config = json.loads(path.read_bytes())
    config[field] = value
    path.write_text(json.dumps(config))
    connector = MockConnector(tmp_path)
    with pytest.raises(ValueError, match='protocol mismatch'):
        acquire(connector, tmp_path)  # type: ignore[arg-type]
    assert connector.calls == 0


def latest_diagnostic(root: Path) -> dict[str, Any]:
    files = list((root / 'artifacts/gate_a/identity_spine/v2_diagnostics').glob('*.json'))
    return json.loads(max(files, key=lambda p: p.stat().st_mtime_ns).read_bytes())


def test_no_freeze_resume_fails_offline_and_preserves_directory(tmp_path: Path) -> None:
    prepare(tmp_path)
    raw = tmp_path / 'data/raw/wrds/gate_a/data_02_v2'
    raw.mkdir(parents=True)
    connector = MockConnector(tmp_path)
    with pytest.raises(FileNotFoundError):
        acquire(connector, tmp_path, resume=True)  # type: ignore[arg-type]
    report = latest_diagnostic(tmp_path)
    assert report['pipeline_stage'] == 'FREEZE_SELECTION'
    assert report['exception_class'] == 'FileNotFoundError'
    assert report['frozen_permno_count'] == 0
    assert report['paths_successfully_written_before_failure'] == []
    assert connector.calls == 0 and list(raw.iterdir()) == []


def test_initial_selection_allows_existing_empty_raw_directory(tmp_path: Path) -> None:
    prepare(tmp_path)
    (tmp_path / 'data/raw/wrds/gate_a/data_02_v2').mkdir(parents=True)
    connector = MockConnector(tmp_path)
    acquire(connector, tmp_path)
    assert connector.calls == 3
    assert (tmp_path / 'artifacts/gate_a/identity_spine/v2_selection_manifest.json').is_file()


def test_initial_selection_rejects_nonempty_raw_directory_without_freeze(tmp_path: Path) -> None:
    prepare(tmp_path)
    raw = tmp_path / 'data/raw/wrds/gate_a/data_02_v2'
    raw.mkdir(parents=True)
    marker = raw / 'preserve.me'
    marker.write_bytes(b'partial')
    connector = MockConnector(tmp_path)
    with pytest.raises(ValueError, match='Nonempty V2 raw directory'):
        acquire(connector, tmp_path)
    assert connector.calls == 0 and marker.read_bytes() == b'partial'
    assert not (tmp_path / 'artifacts/gate_a/identity_spine/v2_selection_manifest.json').exists()


def test_resume_reuses_frozen_sample_without_choose_or_catalog(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock
    prepare(tmp_path)
    connector = MockConnector(tmp_path, oversize=True)
    with pytest.raises(ValueError):
        acquire(connector, tmp_path)  # type: ignore[arg-type]
    frozen = tmp_path / 'artifacts/gate_a/identity_spine/v2_selection_manifest.json'
    before = {p: p.read_bytes() for p in (tmp_path / 'data/raw/wrds/gate_a/data_02_v2').iterdir()}
    frozen_bytes = frozen.read_bytes()
    forbidden = Mock(side_effect=AssertionError('selection must never rerun'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.choose', forbidden)
    connector.oversize = False
    connector.calls = 1  # next mock response is fixed security history, never catalog
    result = acquire(connector, tmp_path, resume=True)  # type: ignore[arg-type]
    assert [r['permno'] for r in result['selected']] == list(range(10000, 10006))
    assert frozen.read_bytes() == frozen_bytes
    assert all(p.read_bytes() == contents for p, contents in before.items())
    forbidden.assert_not_called()
    all_bytes = {p: p.read_bytes() for p in (tmp_path / 'data/raw/wrds/gate_a/data_02_v2').iterdir()}
    acquire(connector, tmp_path, resume=True)  # type: ignore[arg-type]
    assert connector.calls == 3  # second resume is entirely cache-backed
    assert all(p.read_bytes() == contents for p, contents in all_bytes.items())


def test_partial_unreceipted_file_is_not_overwritten(tmp_path: Path) -> None:
    prepare(tmp_path)
    connector = MockConnector(tmp_path, oversize=True)
    with pytest.raises(ValueError):
        acquire(connector, tmp_path)  # type: ignore[arg-type]
    path = tmp_path / 'data/raw/wrds/gate_a/data_02_v2/stksecurityinfohist_fixture.parquet'
    path.write_bytes(b'partial evidence retained')
    with pytest.raises(ValueError, match='Incomplete existing fixture'):
        acquire(connector, tmp_path, resume=True)  # type: ignore[arg-type]
    assert connector.calls == 2
    assert path.read_bytes() == b'partial evidence retained'
    assert latest_diagnostic(tmp_path)['pipeline_stage'] == 'VALIDATE_SCHEMA'


def test_failure_stage_records_frozen_count_and_successful_paths(tmp_path: Path) -> None:
    prepare(tmp_path)
    with pytest.raises(ValueError):
        acquire(MockConnector(tmp_path, oversize=True), tmp_path)  # type: ignore[arg-type]
    report = latest_diagnostic(tmp_path)
    assert report['pipeline_stage'] == 'VALIDATE_SCHEMA'
    assert report['query_identifier'] == 'stksecurityinfohist_fixture_SOURCE_SCHEMA'
    assert report['selection_already_frozen'] and report['frozen_permno_count'] == 6
    assert len(report['paths_successfully_written_before_failure']) == 4
    assert report['sanitized_exception_message'].startswith('Row cap exceeded')


@pytest.mark.parametrize('target', [RAW, FREEZE, FINGERPRINT])
def test_existing_target_file_fails_before_query(tmp_path: Path, target: str) -> None:
    prepare(tmp_path)
    path = tmp_path / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'preserve existing evidence')
    connector = MockConnector(tmp_path)
    with pytest.raises((ValueError, FileExistsError)):
        acquire(connector, tmp_path)
    assert path.read_bytes() == b'preserve existing evidence'
    assert connector.calls == 0


def test_failure_after_durable_freeze_never_reselects(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock
    from src.data.providers.wrds.extract import write_once

    prepare(tmp_path)
    connector = MockConnector(tmp_path)

    def fail_fingerprint(path: Path, content: bytes) -> None:
        if path == tmp_path / FINGERPRINT:
            raise OSError('injected disk failure')
        write_once(path, content)

    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.write_once', fail_fingerprint)
    with pytest.raises(OSError):
        acquire(connector, tmp_path)
    assert connector.calls == 1  # only CRSP metadata, never links/history
    frozen_bytes = (tmp_path / FREEZE).read_bytes()
    assert len(json.loads(frozen_bytes)['selected']) == 6
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.write_once', write_once)
    forbidden = Mock(side_effect=AssertionError('selection must never rerun'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.choose', forbidden)
    acquire(connector, tmp_path)  # no --resume required
    assert connector.calls == 3
    assert (tmp_path / FREEZE).read_bytes() == frozen_bytes
    forbidden.assert_not_called()


@pytest.mark.parametrize('tamper', ['fingerprint', 'catalog_receipt', 'manifest'])
def test_incompatible_frozen_evidence_fails_without_query(tmp_path: Path, tamper: str) -> None:
    prepare(tmp_path)
    connector = MockConnector(tmp_path, oversize=True)
    with pytest.raises(ValueError):
        acquire(connector, tmp_path)
    path = tmp_path / {
        'fingerprint': FINGERPRINT, 'catalog_receipt': f'{RAW}/selection_metadata.manifest.json',
        'manifest': FREEZE,
    }[tamper]
    path.chmod(0o600)
    if tamper == 'fingerprint':
        path.write_text('0' * 64 + '\n')
    else:
        record = json.loads(path.read_bytes())
        record['row_count' if tamper == 'catalog_receipt' else 'selected'] = 0
        path.write_text(json.dumps(record))
    before = path.read_bytes()
    with pytest.raises((ValueError, TypeError)):
        acquire(connector, tmp_path)
    assert connector.calls == 2
    assert path.read_bytes() == before


@pytest.mark.parametrize('resume', [True, False])
def test_cli_preflight_never_constructs_factory_on_invalid_state(
        tmp_path: Path, monkeypatch, resume: bool) -> None:
    from unittest.mock import Mock
    from src.data.providers.wrds.fixture_v2 import main

    prepare(tmp_path)
    if not resume:
        raw = tmp_path / RAW
        raw.mkdir(parents=True)
        (raw / 'partial').write_bytes(b'preserve')
    factory = Mock(side_effect=AssertionError('no authentication allowed'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.ROOT', tmp_path)
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.interactive_factory', factory)
    monkeypatch.setattr('sys.argv', ['fixture_v2'] + (['--resume'] if resume else []))
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 1
    factory.assert_not_called()


def test_diagnose_initial_ready_is_read_only_and_offline(tmp_path: Path, monkeypatch, capsys) -> None:
    from unittest.mock import Mock
    from src.data.providers.wrds.fixture_v2 import main

    prepare(tmp_path)
    raw = tmp_path / RAW
    raw.mkdir(parents=True)
    factory = Mock(side_effect=AssertionError('offline only'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.ROOT', tmp_path)
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.interactive_factory', factory)
    monkeypatch.setattr('sys.argv', ['fixture_v2', '--diagnose'])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'INITIAL_SELECTION_READY_NOT_EXECUTED'
    assert report['prerequisite_artifact'] == FREEZE
    assert report['frozen_permno_count'] == 0
    assert list(raw.iterdir()) == [] and not (tmp_path / FREEZE).exists()
    factory.assert_not_called()


def test_freeze_sync_failure_stops_all_later_queries(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock
    from src.data.providers.wrds.extract import sync_file

    prepare(tmp_path)
    connector = MockConnector(tmp_path)
    fail = Mock(side_effect=OSError('injected fsync failure'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.sync_file', fail)
    with pytest.raises(OSError):
        acquire(connector, tmp_path)
    assert connector.calls == 1
    frozen_bytes = (tmp_path / FREEZE).read_bytes()
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.sync_file', sync_file)
    acquire(connector, tmp_path)
    assert connector.calls == 3 and (tmp_path / FREEZE).read_bytes() == frozen_bytes


def test_provider_query_failure_cannot_change_frozen_sample(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import Mock
    from src.data.providers.wrds.fixture_v2 import CATALOG_SQL

    prepare(tmp_path)
    queries = []

    def query(sql: str, params: dict[str, Any]) -> Any:
        queries.append(sql)
        if sql == CATALOG_SQL:
            return pd.DataFrame(catalog())
        assert (tmp_path / FINGERPRINT).is_file()
        raise ConnectionError('injected provider failure')

    connector = Mock(query=query)
    with pytest.raises(ConnectionError):
        acquire(connector, tmp_path)
    before = (tmp_path / FREEZE).read_bytes()
    forbidden = Mock(side_effect=AssertionError('no reselection'))
    monkeypatch.setattr('src.data.providers.wrds.fixture_v2.choose', forbidden)
    for _ in range(2):
        with pytest.raises(ConnectionError):
            acquire(connector, tmp_path)
    assert queries.count(CATALOG_SQL) == 1
    assert (tmp_path / FREEZE).read_bytes() == before
    forbidden.assert_not_called()
