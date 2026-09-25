"""Immutable canonical observations. All knowledge timestamps are explicit and UTC."""
from datetime import date, datetime, timezone
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc(cls, value: object) -> object:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        return value


class Observation(Contract):
    security_id: Text
    source: Text
    source_version: Text
    available_timestamp: AwareDatetime
    ingested_at: AwareDatetime
    availability_basis: Literal[
        "source_timestamp", "assumed_post_close", "ingestion_conservative", "synthetic"
    ]

    @model_validator(mode="after")
    def ingestion_order(self) -> Self:
        if self.available_timestamp > self.ingested_at:
            raise ValueError("timestamp violation: availability cannot be after ingestion")
        return self


class SecurityMaster(Observation):
    ticker: Text
    exchange: Text
    company_name: Text
    sector: Text | None
    industry: Text | None
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None
    end_available_timestamp: AwareDatetime | None

    @model_validator(mode="after")
    def identity_and_interval(self) -> Self:
        if self.security_id == self.ticker:
            raise ValueError("security_id must be an internal stable ID, not ticker")
        if self.valid_to is not None and self.valid_from >= self.valid_to:
            raise ValueError("invalid interval: security master requires [from, to)")
        validate_interval_end(self.valid_to, self.end_available_timestamp,
                              self.available_timestamp, self.ingested_at)
        return self


class IndexMembership(Observation):
    index_id: Text
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None
    end_available_timestamp: AwareDatetime | None

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.effective_to is not None and self.effective_from >= self.effective_to:
            raise ValueError("invalid interval: membership requires [from, to)")
        validate_interval_end(self.effective_to, self.end_available_timestamp,
                              self.available_timestamp, self.ingested_at)
        return self


def validate_interval_end(
    end: datetime | None, known_at: datetime | None, available: datetime, ingested: datetime
) -> None:
    if (end is None) != (known_at is None):
        raise ValueError("interval end and its knowledge timestamp must both be supplied")
    if known_at is not None and end is not None:
        if not available <= known_at <= ingested:
            raise ValueError("timestamp violation: invalid interval-end knowledge time")
        if known_at > end:
            raise ValueError("timestamp violation: retrospective interval correction unsupported")


class MarketRecord(Observation):
    trade_date: date
    open: Positive | None
    high: Positive | None
    low: Positive | None
    close: Positive | None
    raw_open: Positive | None
    raw_high: Positive | None
    raw_low: Positive | None
    raw_close: Positive | None
    volume: Nonnegative | None
    dividend: Nonnegative
    split_factor: Positive
    corporate_action_source: Text
    corporate_action_source_version: Text

    @model_validator(mode="after")
    def raw_prices(self) -> Self:
        for name in ("open", "high", "low", "close"):
            if getattr(self, name) != getattr(self, "raw_" + name):
                raise ValueError("canonical OHLC must equal raw OHLC; adjusted-only data rejected")
        known = [p for p in (self.open, self.high, self.low, self.close) if p is not None]
        if self.high is not None and any(p > self.high for p in known):
            raise ValueError("OHLC high below another price")
        if self.low is not None and any(p < self.low for p in known):
            raise ValueError("OHLC low above another price")
        return self


class FundamentalFact(Observation):
    fiscal_period_end: date
    fiscal_period_start: date | None
    filing_accepted_at: AwareDatetime
    form_type: Text
    accession_number: Text
    fact_name: Text
    value: Finite | None
    unit: Text
    period_type: Literal["instant", "duration"]
    revision_id: Text
    supersedes_revision_id: Text | None
    fiscal_year: Annotated[int, Field(ge=1900, le=2200)] | None = None
    fiscal_quarter: Annotated[int, Field(ge=1, le=4)] | None = None
    fiscal_year_start: date | None = None
    fiscal_quarter_start: date | None = None
    duration_kind: Literal["quarter", "ytd"] | None = None
    share_basis_date: date | None = None
    equity_scope: Literal["single_class", "unknown"] = "unknown"

    @model_validator(mode="after")
    def fact_times(self) -> Self:
        if self.available_timestamp < self.filing_accepted_at:
            raise ValueError("timestamp violation: fact available before filing acceptance")
        if self.fiscal_period_end > self.filing_accepted_at.date():
            raise ValueError("timestamp violation: fiscal period ends after filing")
        if self.period_type == "duration":
            if self.fiscal_period_start is None or self.fiscal_period_start > self.fiscal_period_end:
                raise ValueError("duration requires a valid fiscal_period_start")
        elif self.fiscal_period_start is not None:
            raise ValueError("instant fact must not have fiscal_period_start")
        if self.share_basis_date is not None and self.share_basis_date > self.filing_accepted_at.date():
            raise ValueError("timestamp violation: share basis after filing acceptance")
        metadata = (self.fiscal_year, self.fiscal_quarter, self.fiscal_year_start,
                    self.fiscal_quarter_start, self.duration_kind)
        if any(value is not None for value in metadata):
            if self.period_type != "duration" or any(value is None for value in metadata):
                raise ValueError("flow fiscal metadata must be complete and belong to a duration")
            assert self.fiscal_year_start is not None and self.fiscal_quarter_start is not None
            if not self.fiscal_year_start <= self.fiscal_quarter_start <= self.fiscal_period_end:
                raise ValueError("inconsistent fiscal quarter boundaries")
            expected_start = (self.fiscal_quarter_start if self.duration_kind == "quarter"
                              else self.fiscal_year_start)
            if self.fiscal_period_start != expected_start:
                raise ValueError("duration start disagrees with quarter/YTD metadata")
            if self.fiscal_quarter == 1 and self.fiscal_quarter_start != self.fiscal_year_start:
                raise ValueError("Q1 must begin at fiscal-year start")
        if self.supersedes_revision_id == self.revision_id:
            raise ValueError("revision cannot supersede itself")
        return self

    def observation_key(self) -> tuple[str, str, date | None, date, str, str]:
        return (self.security_id, self.fact_name, self.fiscal_period_start,
                self.fiscal_period_end, self.period_type, self.unit)


class Session(Contract):
    trade_date: date
    open_timestamp: AwareDatetime
    close_timestamp: AwareDatetime

    @model_validator(mode="after")
    def time_order(self) -> Self:
        from zoneinfo import ZoneInfo

        if self.open_timestamp >= self.close_timestamp:
            raise ValueError("session open must precede close")
        for timestamp in (self.open_timestamp, self.close_timestamp):
            if timestamp.astimezone(ZoneInfo("America/New_York")).date() != self.trade_date:
                raise ValueError("session timestamp must belong to trade_date in New York")
        return self


class Calendar(Contract):
    """Explicit, versioned exchange schedule; no inferred weekday calendar."""
    source: Text
    source_version: Text
    coverage_start: date
    coverage_end: date
    sessions: tuple[Session, ...]

    @model_validator(mode="after")
    def unique_sessions(self) -> Self:
        dates = [s.trade_date for s in self.sessions]
        if self.coverage_start > self.coverage_end:
            raise ValueError("invalid calendar coverage")
        if len(set(dates)) != len(dates):
            raise ValueError("duplicate calendar session")
        if any(d < self.coverage_start or d > self.coverage_end for d in dates):
            raise ValueError("session outside declared calendar coverage")
        return self

    def session(self, day: date) -> Session | None:
        if not self.coverage_start <= day <= self.coverage_end:
            raise ValueError("date outside calendar coverage; cannot infer holiday/session")
        return next((s for s in self.sessions if s.trade_date == day), None)


class DataBundle(Contract):
    securities: tuple[SecurityMaster, ...]
    memberships: tuple[IndexMembership, ...]
    market: tuple[MarketRecord, ...]
    fundamentals: tuple[FundamentalFact, ...]
