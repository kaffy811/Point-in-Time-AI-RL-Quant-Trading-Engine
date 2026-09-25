"""Provider normalization stays outside the downstream PIT firewall."""
from typing import Protocol

from pydantic import AwareDatetime

from src.data.schemas import Contract, FundamentalFact, Text


class ProviderContext(Contract):
    security_id: Text
    cik: Text
    accession_number: Text
    identity_mapping_version: Text
    ingested_at: AwareDatetime


class FundamentalAdapter(Protocol):
    def normalize(
        self, companyfacts: bytes, filing_header: bytes, context: ProviderContext,
    ) -> tuple[FundamentalFact, ...]: ...
