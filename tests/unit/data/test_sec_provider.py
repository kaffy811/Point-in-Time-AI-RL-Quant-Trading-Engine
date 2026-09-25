import json

import pytest

from conftest import FIXTURES, et
from src.data.providers.base import ProviderContext
from src.data.providers.sec_companyfacts import SECCompanyFactsAdapter


def inputs():
    return ((FIXTURES / "sec_companyfacts_synthetic.json").read_bytes(),
            (FIXTURES / "sec_header_synthetic.txt").read_bytes(),
            ProviderContext(security_id="SEC123", cik="123",
                            accession_number="0000000123-24-000001",
                            identity_mapping_version="synthetic-mapping-v1",
                            ingested_at=et("2024-08-05T12:00")))


def test_sec_adapter_uses_header_acceptance_and_conservative_ingestion():
    data, header, context = inputs()
    fact, = SECCompanyFactsAdapter().normalize(data, header, context)
    assert fact.filing_accepted_at == et("2024-08-02T16:37")
    assert fact.available_timestamp == context.ingested_at
    assert fact.available_timestamp > fact.filing_accepted_at
    assert fact.availability_basis == "ingestion_conservative"
    assert fact.security_id == "SEC123"
    assert len(fact.source_version) == 64


@pytest.mark.parametrize("change", ["duplicate", "wrong_cik", "no_header", "wrong_accession"])
def test_sec_does_not_guess_missing_or_ambiguous_evidence(change):
    data, header, context = inputs()
    payload = json.loads(data)
    if change == "duplicate":
        values = payload["facts"]["us-gaap"]["Assets"]["units"]["USD"]
        values.append(dict(values[0]))
    elif change == "wrong_cik":
        payload["cik"] = 999
    elif change == "no_header":
        header = b""
    else:
        header = header.replace(b"24-000001", b"24-000002")
    with pytest.raises(ValueError):
        SECCompanyFactsAdapter().normalize(json.dumps(payload).encode(), header, context)
