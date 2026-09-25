"""One SEC filing slice; conservative availability, never historic vendor backfill.

Inputs are archived Company Facts JSON and its complete-submission SGML header.
No network, credentials, ticker lookup, or inferred filing-date-to-time conversion.
"""
import hashlib
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.data.providers.base import ProviderContext
from src.data.schemas import FundamentalFact


def unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate provider JSON key: {key}")
        result[key] = value
    return result


class SECCompanyFactsAdapter:
    def normalize(
        self, companyfacts: bytes, filing_header: bytes, context: ProviderContext,
    ) -> tuple[FundamentalFact, ...]:
        payload = json.loads(companyfacts, object_pairs_hook=unique_json)
        header = filing_header.decode("utf-8")
        if int(payload["cik"]) != int(context.cik):
            raise ValueError("CIK does not match the explicit stable-ID mapping")
        def header_field(pattern: str) -> str:
            values = re.findall(pattern, header)
            if len(values) != 1:
                raise ValueError("missing or ambiguous SEC filing-header identity/timestamp")
            return str(values[0])
        accession = header_field(r"ACCESSION NUMBER:\s*([0-9-]+)")
        cik = header_field(r"CENTRAL INDEX KEY:\s*([0-9]+)")
        stamp = header_field(r"<ACCEPTANCE-DATETIME>([0-9]{14})")
        if accession != context.accession_number or int(cik) != int(context.cik):
            raise ValueError("filing header does not match CIK/accession mapping")
        local = datetime.strptime(stamp, "%Y%m%d%H%M%S")
        zone = ZoneInfo("America/New_York")
        if local.replace(tzinfo=zone, fold=0).utcoffset() != local.replace(
            tzinfo=zone, fold=1
        ).utcoffset():
            raise ValueError("ambiguous/nonexistent SEC local acceptance time")
        accepted = local.replace(tzinfo=zone)
        if accepted > context.ingested_at:
            raise ValueError("filing accepted after payload ingestion")
        version = hashlib.sha256(companyfacts + b"\x00" + filing_header + b"\x00"
                                 + context.identity_mapping_version.encode()).hexdigest()
        rows = []
        seen: set[tuple[object, ...]] = set()
        for taxonomy, concepts in payload["facts"].items():
            for concept, details in concepts.items():
                for unit, values in details["units"].items():
                    for fact in values:
                        if fact["accn"] != context.accession_number:
                            continue
                        row = FundamentalFact(
                            security_id=context.security_id, source="SEC/companyfacts",
                            source_version=version, available_timestamp=context.ingested_at,
                            ingested_at=context.ingested_at,
                            availability_basis="ingestion_conservative",
                            fiscal_period_end=fact["end"], fiscal_period_start=fact.get("start"),
                            filing_accepted_at=accepted, form_type=fact["form"],
                            accession_number=accession, fact_name=f"{taxonomy}:{concept}",
                            value=fact["val"], unit=unit,
                            period_type="duration" if "start" in fact else "instant",
                            revision_id=f"{accession}:{version}", supersedes_revision_id=None,
                        )
                        key = row.observation_key()
                        if key in seen:
                            raise ValueError("duplicate SEC canonical observation; explicit resolution required")
                        seen.add(key)
                        rows.append(row)
        if not rows:
            raise ValueError("selected accession has no facts in supplied payload")
        return tuple(sorted(rows, key=lambda r: str(r.observation_key())))
