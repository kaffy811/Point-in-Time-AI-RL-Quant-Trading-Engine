"""Generated secret sentinels must never survive sanitized provider diagnostics."""
import json
from pathlib import Path
import secrets
from unittest.mock import Mock

import pytest

from src.data.providers.wrds.connection import Connector, ProviderError
from src.data.providers.wrds.diagnostics import sanitized_exception
from src.data.providers.wrds.v2_diagnostics import Diagnostic, STAGES


@pytest.mark.parametrize('connect_failure', [True, False])
def test_database_cause_survives_without_secret_text(tmp_path: Path, connect_failure: bool) -> None:
    secret = secrets.token_urlsafe(32)
    exc = RuntimeError('postgresql://user:' + secret + '@host/db password=' + secret)
    exc.pgcode = '42703'  # type: ignore[attr-defined]
    db = Mock()
    factory = Mock(side_effect=exc) if connect_failure else Mock(return_value=db)
    db.connection.exec_driver_sql.side_effect = exc
    with pytest.raises(ProviderError) as caught:
        Connector(factory).query('bounded query', {})
    audit = Diagnostic(tmp_path)
    audit.at('FETCH_CIK_LINKS', 'wciklink_cusip_fixture', ['wrdssec_common.wciklink_cusip'])
    report = audit.failure(caught.value)
    assert report['exception_class'] == 'RuntimeError'
    assert report['sqlstate'] == '42703'
    assert report['pipeline_stage'] == ('CONNECT_WRDS' if connect_failure else 'FETCH_CIK_LINKS')
    assert 'undefined column' in report['sanitized_exception_message']
    assert secret not in json.dumps(report) and secret not in str(caught.value)
    assert audit.path is not None and secret not in audit.path.read_text()


@pytest.mark.parametrize('stage', sorted(STAGES))
def test_all_stage_labels_and_append_only_diagnostics(tmp_path: Path, stage: str) -> None:
    secret = secrets.token_urlsafe(32)
    audit = Diagnostic(tmp_path)
    audit.at(stage, 'MOCK_OPERATION', [])
    result = audit.failure(ValueError(secret))
    assert result['pipeline_stage'] == stage
    first = audit.path
    audit.failure(ValueError(secret))
    assert first != audit.path and first is not None and first.exists()
    assert secret not in first.read_text()


def test_raw_text_never_interpolated() -> None:
    secret = secrets.token_urlsafe(32)
    for error in (ValueError(secret), FileNotFoundError(secret), KeyError(secret)):
        assert secret not in json.dumps(sanitized_exception(error))


@pytest.mark.parametrize('wrapped', [True, False])
def test_forged_safe_diagnostic_cannot_bypass_allowlist(tmp_path: Path, wrapped: bool) -> None:
    secret = secrets.token_urlsafe(32)
    detail = {'sanitized_exception_message': secret, 'password': secret,
              'exception_class': secret, 'provider_stage': secret, 'sqlstate': secret}
    error = ProviderError(secret, detail) if wrapped else ValueError(secret)
    if not wrapped:
        error.safe_diagnostic = detail  # type: ignore[attr-defined]
    report = Diagnostic(tmp_path).failure(error)
    assert secret not in json.dumps(report)
    assert 'password' not in report
    with pytest.raises(ProviderError) as caught:
        Connector(Mock(side_effect=error)).query('bounded', {})
    assert secret not in str(caught.value)
    assert secret not in json.dumps(caught.value.safe_diagnostic)
