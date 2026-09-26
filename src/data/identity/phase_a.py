"""Deterministic preliminary PERMNO→historical CUSIP→CIK evidence resolution.

Phase A never confirms SEC identity. Raw snapshot scores/endpoints are separate audit
metadata, not historically available identity inputs.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime
import math
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

Status = Literal["RESOLVED_PENDING_SEC_CONFIRMATION", "AMBIGUOUS", "UNRESOLVED"]


def source_date(value: Any) -> date | None:
    if value is None:
        return None
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    raise ValueError("Expected a source ISO date, not an inferred timestamp")


def identifier(value: Any, length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9*@#]{" + str(length) + "}", value):
        raise ValueError("Invalid source identifier; never guess or pad CUSIPs")
    return value


@dataclass(frozen=True)
class History:
    permno: int
    start: date
    end: date
    ticker: str | None
    trading_symbol: str | None
    cusip: str | None
    cusip9: str | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "History":
        start, end = source_date(row["secinfostartdt"]), source_date(row["secinfoenddt"])
        if start is None or end is None or start > end:
            raise ValueError("Missing/invalid CRSP history interval; no open-end inference")
        if type(row["permno"]) is not int or row["permno"] <= 0:
            raise ValueError("Invalid PERMNO")
        for key in ("ticker", "tradingsymbol"):
            if row[key] is not None and not isinstance(row[key], str):
                raise ValueError("Invalid descriptive metadata")
        return cls(row["permno"], start, end, row["ticker"], row["tradingsymbol"],
                   identifier(row["cusip"], 8), identifier(row["cusip9"], 9))


@dataclass(frozen=True)
class Link:
    cik: str
    cusip: str | None
    cusip_full: str | None
    first: date | None
    last: date | None
    validated: int
    tmatch: float | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Link":
        cik = row["cik"]
        if not isinstance(cik, str) or not re.fullmatch(r"\d{10}", cik) or int(cik) == 0:
            raise ValueError("CIK must be a source 10-digit string")
        validated = row["validated"]
        if type(validated) not in (int, float) or validated not in (0, 1, 2, 3):
            raise ValueError("Invalid validated code")
        tmatch = row["tmatch"]
        if tmatch is not None and (type(tmatch) not in (int, float) or not math.isfinite(tmatch)):
            raise ValueError("Invalid audit-only tmatch")
        # Preserve last in the raw evidence model only. Never use it as validity/expiry.
        return cls(cik, identifier(row["cusip"], 8), identifier(row["cusip_full"], 9),
                   source_date(row["cikdate1"]), source_date(row["cikdate2"]),
                   int(validated), None if tmatch is None else float(tmatch))


@dataclass(frozen=True)
class Resolution:
    security_id: int
    security_id_type: str
    as_of_timestamp: str
    as_of_date: str
    historical_ticker: str | None
    historical_trading_symbol: str | None
    historical_cusip: str | None
    historical_cusip9: str | None
    preliminary_cik: str | None
    candidate_ciks: tuple[str, ...]
    wrds_validated: int | None
    cik_evidence_first_date: str | None
    resolution_status: Status
    resolution_reason: str
    primary_link_source: str
    match_tier: str | None
    crosscheck_status: str = "NOT_RUN_PHASE_A"
    sec_confirmation_status: str = "NOT_PERFORMED"

    def row(self) -> dict[str, Any]:
        return asdict(self)


def resolve(permno: int, as_of: datetime, history: tuple[History, ...],
            links: tuple[Link, ...]) -> Resolution:
    if type(permno) is not int or permno <= 0:
        raise ValueError("A positive PERMNO is required")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of_timestamp must have an explicit timezone")
    local = as_of.astimezone(ZoneInfo("America/New_York"))
    day = local.date()
    base: dict[str, Any] = dict(
        security_id=permno, security_id_type="CRSP_PERMNO",
        as_of_timestamp=local.isoformat(), as_of_date=day.isoformat(),
        historical_ticker=None, historical_trading_symbol=None, historical_cusip=None,
        historical_cusip9=None, preliminary_cik=None, candidate_ciks=(), wrds_validated=None,
        cik_evidence_first_date=None, primary_link_source="wrdssec_common.wciklink_cusip",
        match_tier=None,
    )

    def result(status: Status, reason: str) -> Resolution:
        return Resolution(**base, resolution_status=status, resolution_reason=reason)

    active = [r for r in history if r.permno == permno and r.start <= day <= r.end]
    if not active:
        return result("UNRESOLVED", "NO_HISTORICAL_SECURITY_RECORD")
    identities = {(r.ticker, r.trading_symbol, r.cusip, r.cusip9) for r in active}
    if len(identities) != 1:
        return result("AMBIGUOUS", "CONFLICTING_HISTORICAL_SECURITY_RECORDS")
    ticker, symbol, cusip, cusip9 = identities.pop()  # Exactly one projection, not row ranking.
    base.update(historical_ticker=ticker, historical_trading_symbol=symbol,
                historical_cusip=cusip, historical_cusip9=cusip9)
    if cusip is None and cusip9 is None:
        return result("UNRESOLVED", "NO_HISTORICAL_CUSIP")
    if cusip is not None and cusip9 is not None and cusip9[:8] != cusip:
        return result("UNRESOLVED", "INCONSISTENT_CRSP_CUSIP_IDENTIFIERS")

    nine = [r for r in links if cusip9 is not None and r.cusip_full == cusip9
            and r.validated == 3]
    eight = [r for r in links if cusip is not None and r.cusip == cusip and r.validated == 2]
    # Exclude future/null dates BEFORE choosing a tier: future 9-digit evidence must
    # not replace an already-historical 8-digit resolution. Same-day evidence remains
    # provisional, so it must not silently eliminate a plausible competing candidate.
    eligible9 = [r for r in nine if r.first is not None and r.first <= day]
    eligible8 = [r for r in eight if r.first is not None and r.first <= day]
    selected = eligible9 if eligible9 else eligible8
    if not selected:
        # Do not distinguish future-only versus absent here: that would change past
        # resolution output when future links are appended. Raw audit keeps the detail.
        return result("UNRESOLVED", "NO_HISTORICALLY_ELIGIBLE_STRONG_LINK")
    base.update(wrds_validated=3 if eligible9 else 2,
                match_tier="EXACT_CUSIP9" if eligible9 else "EXACT_CUSIP8")
    ciks = tuple(sorted({r.cik for r in selected}))
    base["candidate_ciks"] = ciks
    if len(ciks) > 1:
        return result("AMBIGUOUS", "MULTIPLE_PLAUSIBLE_CIKS")
    first = min(r.first for r in selected if r.first is not None)
    base["cik_evidence_first_date"] = first.isoformat()
    if first == day:
        return result("UNRESOLVED", "SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED")
    base["preliminary_cik"] = ciks[0]
    return result("RESOLVED_PENDING_SEC_CONFIRMATION", "UNIQUE_HISTORICALLY_EVIDENCED_CIK")
