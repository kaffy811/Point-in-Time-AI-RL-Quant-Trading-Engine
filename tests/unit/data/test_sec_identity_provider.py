"""Mock HTTP transport; no network and no fabricated real SEC confirmation."""
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError

import pytest

from src.data.providers.sec_identity import (
    MetadataRedirect, SECMetadataClient, authorized_url, rows_from_columns,
)

URL = "https://data.sec.gov/submissions/CIK0001556266.json"


def test_authorization_and_redirect_guards():
    assert authorized_url(URL)
    assert not authorized_url("https://data.sec.gov/submissions/CIK0001499961.json")
    assert not authorized_url(URL + "?extra=1")
    assert not authorized_url("https://example.invalid/submissions/CIK0001556266.json")
    with pytest.raises(ValueError, match="redirect outside"):
        MetadataRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")


def test_cache_hash_and_no_contact_in_receipt(tmp_path, monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.url = URL
    response.read.return_value = b'{"cik":1556266}'
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr("src.data.providers.sec_identity.build_opener", lambda *_: opener)
    monkeypatch.setattr("src.data.providers.sec_identity.time.sleep", lambda _: None)
    client = SECMetadataClient(tmp_path, "unit-test contact@example.invalid", max_requests=1)
    first = client.fetch(URL)
    assert client.fetch(URL) == first
    assert opener.open.call_count == 1
    assert "contact@example.invalid" not in str(first[1])
    with pytest.raises(ValueError, match="budget exhausted"):
        client.fetch("https://data.sec.gov/submissions/CIK0001505611.json")
    (tmp_path / first[1]["path"]).write_bytes(b"modified")
    with pytest.raises(ValueError, match="hash mismatch"):
        client.fetch(URL)


def test_http_failure_is_not_evidence(tmp_path, monkeypatch):
    opener = Mock()
    opener.open.side_effect = HTTPError(URL, 503, "unavailable", {}, None)
    monkeypatch.setattr("src.data.providers.sec_identity.build_opener", lambda *_: opener)
    monkeypatch.setattr("src.data.providers.sec_identity.time.sleep", lambda _: None)
    client = SECMetadataClient(tmp_path, "unit-test contact@example.invalid")
    with pytest.raises(RuntimeError, match="503"):
        client.fetch(URL)
    assert not list(tmp_path.glob("*.receipt.json"))
    assert len(list(tmp_path.glob("*.failure.json"))) == 1


def test_metadata_array_integrity():
    with pytest.raises(ValueError, match="fields missing"):
        rows_from_columns({}, "0001556266")
    with pytest.raises(ValueError, match="not authorized"):
        rows_from_columns({}, "0001499961")
