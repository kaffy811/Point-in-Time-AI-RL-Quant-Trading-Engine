"""Content-addressed references to the exact observations actually consumed."""
from src.data.lineage import content_hash
from src.data.schemas import FundamentalFact, IndexMembership, MarketRecord, Observation, SecurityMaster
from src.features.contracts import InputReference


def reference(record: Observation) -> InputReference:
    digest = content_hash(record.model_dump(mode="json"))
    common = dict(reference_id=digest, security_id=record.security_id,
                  available_timestamp=record.available_timestamp,
                  source=record.source, source_version=record.source_version)
    if isinstance(record, MarketRecord):
        return InputReference.model_validate(dict(dataset="market", observation_date=record.trade_date,
                                                  **common))
    if isinstance(record, FundamentalFact):
        return InputReference.model_validate(dict(dataset="fundamentals",
                              observation_date=record.fiscal_period_end,
                              filing_accepted_at=record.filing_accepted_at,
                              revision_id=record.revision_id, **common))
    if isinstance(record, SecurityMaster):
        return InputReference.model_validate(dict(dataset="securities",
                              observation_date=record.valid_from.date(), **common))
    if isinstance(record, IndexMembership):
        return InputReference.model_validate(dict(dataset="memberships",
                              observation_date=record.effective_from.date(),
                              **common))
    raise TypeError("unsupported observation type")
