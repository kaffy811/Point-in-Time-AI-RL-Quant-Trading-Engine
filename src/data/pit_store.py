"""The sole downstream historical-information interface."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime

from src.data.fundamentals import available_revisions
from src.data.index_membership import valid_membership
from src.data.lineage import build_manifest, content_hash
from src.data.schemas import (
    Calendar, Contract, DataBundle, FundamentalFact, IndexMembership, MarketRecord, SecurityMaster,
    Session,
)
from src.data.security_master import valid_security
from src.data.validation import DataContractError, validate_bundle
from src.utils.config import Phase1Config


class Snapshot(Contract):
    signal_timestamp: AwareDatetime
    universe: str
    securities: tuple[SecurityMaster, ...]
    memberships: tuple[IndexMembership, ...]
    market: tuple[MarketRecord, ...]
    fundamentals: tuple[FundamentalFact, ...]
    missing_market_security_ids: tuple[str, ...]
    latest_completed_session: date | None
    stale_market_security_ids: tuple[str, ...]
    incomplete_market_security_ids: tuple[str, ...]
    completed_sessions: tuple[date, ...] = ()
    benchmark_security: SecurityMaster | None = None
    benchmark_market: tuple[MarketRecord, ...] = ()

    def market_anchor_date(self, security_id: str) -> date | None:
        """Last completed/available bar for this identity; missing values are not skipped."""
        return max((row.trade_date for row in self.market if row.security_id == security_id),
                   default=None)

    @property
    def security_ids(self) -> tuple[str, ...]:
        return tuple(row.security_id for row in self.securities)


class PITStore:
    def __init__(self, bundle: DataBundle, calendar: Calendar, config: Phase1Config) -> None:
        issues = validate_bundle(bundle, calendar, config.market_data.completed_bar_delay_minutes)
        if issues:
            raise DataContractError(issues)
        self._bundle = bundle
        self._calendar = calendar
        self._config = config

    def data_manifest(self, dataset_version: str) -> dict[str, object]:
        """Audit-only provenance. Research consumers must not use these aggregates as inputs."""
        observations = (*self._bundle.securities, *self._bundle.memberships,
                        *self._bundle.market, *self._bundle.fundamentals)
        if not observations:
            raise ValueError("cannot build ingestion provenance for an empty bundle")
        return build_manifest(self._bundle, self._calendar, dataset_version,
                              max(r.ingested_at for r in observations))

    def data_manifest_hash(self, dataset_version: str) -> str:
        return content_hash(self.data_manifest(dataset_version))

    def next_execution_open(self, signal_timestamp: datetime) -> tuple[datetime, Session]:
        """Resolve the first explicit exchange-session open after a signal.

        This is a forward-looking label operation and is intentionally separate
        from ``snapshot``, whose contract only exposes information knowable at
        the signal timestamp.
        """
        timestamp = signal_timestamp.astimezone(timezone.utc)
        for session in sorted(self._calendar.sessions, key=lambda item: item.open_timestamp):
            if session.open_timestamp > timestamp:
                return session.open_timestamp, session
        raise ValueError("INVALID_EXECUTION_SCHEDULE")

    def calendar_sessions(self, start: date, end: date) -> tuple[Session, ...]:
        return tuple(session for session in sorted(self._calendar.sessions,
                                                   key=lambda item: item.trade_date)
                     if start <= session.trade_date <= end)

    def forward_market(self, security_id: str, start: date, end: date) -> tuple[MarketRecord, ...]:
        """Return canonical future bars for label construction only."""
        return tuple(sorted((row for row in self._bundle.market
                             if row.security_id == security_id and start <= row.trade_date <= end),
                            key=lambda row: row.trade_date))

    def signal_timestamp(self, day: date) -> datetime:
        """Formation time for a supplied session; weekly scheduling is not implemented here."""
        session = self._calendar.session(day)
        if session is None:
            raise ValueError("cannot form a session signal on a holiday/non-session")
        timestamp = datetime.combine(day, self._config.signal.formation_time,
                                     ZoneInfo(self._config.signal.timezone))
        floor = session.close_timestamp + timedelta(
            minutes=self._config.market_data.completed_bar_delay_minutes)
        if timestamp < floor:
            raise ValueError("configured formation precedes completed-bar availability")
        return timestamp

    def snapshot(
        self, *, signal_timestamp: datetime, universe: str = "sp500",
        benchmark_security_id: str | None = None,
    ) -> Snapshot:
        if signal_timestamp.tzinfo is None or signal_timestamp.utcoffset() is None:
            raise ValueError("signal timestamp must be timezone-aware")
        timestamp = signal_timestamp.astimezone(timezone.utc)
        local_day = timestamp.astimezone(ZoneInfo(self._config.signal.timezone)).date()
        self._calendar.session(local_day)  # Assert explicit calendar coverage, including holidays.
        if universe not in ("sp500", "sp500_pit"):
            raise ValueError("unsupported universe")
        memberships = tuple(sorted((r for r in self._bundle.memberships
                                    if r.index_id == "sp500" and valid_membership(r, timestamp)),
                                   key=lambda r: r.security_id))
        ids = {r.security_id for r in memberships}
        securities = tuple(sorted((r for r in self._bundle.securities
                                   if r.security_id in ids and valid_security(r, timestamp)),
                                  key=lambda r: r.security_id))
        if {r.security_id for r in securities} != ids:
            raise ValueError("PIT identity coverage gap: active membership lacks known valid master")
        # Future interval endpoints must not reveal an unannounced future deletion/ticker change.
        memberships = tuple(r.model_copy(update={"effective_to": None,
                                                   "end_available_timestamp": None})
                            if r.end_available_timestamp and r.end_available_timestamp > timestamp
                            else r for r in memberships)
        securities = tuple(r.model_copy(update={"valid_to": None, "end_available_timestamp": None})
                           if r.end_available_timestamp and r.end_available_timestamp > timestamp
                           else r for r in securities)
        market = tuple(sorted((r for r in self._bundle.market if r.security_id in ids
                               and r.available_timestamp <= timestamp),
                              key=lambda r: (r.trade_date, r.security_id)))
        fundamentals = available_revisions(tuple(r for r in self._bundle.fundamentals
                                                if r.security_id in ids), timestamp)
        benchmark_security = None
        benchmark_market: tuple[MarketRecord, ...] = ()
        if benchmark_security_id is not None:
            known = [r for r in self._bundle.securities if r.security_id == benchmark_security_id
                     and valid_security(r, timestamp)]
            if len(known) != 1:
                raise ValueError("benchmark needs exactly one PIT-valid stable security identity")
            benchmark_security = known[0]
            if benchmark_security.end_available_timestamp and (
                benchmark_security.end_available_timestamp > timestamp
            ):
                benchmark_security = benchmark_security.model_copy(
                    update={"valid_to": None, "end_available_timestamp": None})
            benchmark_market = tuple(sorted((r for r in self._bundle.market
                                             if r.security_id == benchmark_security_id
                                             and r.available_timestamp <= timestamp),
                                            key=lambda r: r.trade_date))
        # No market-based universe filtering: missing bars cannot silently erase delisted names.
        market_ids = {r.security_id for r in market}
        completed = [s.trade_date for s in self._calendar.sessions
                     if s.close_timestamp + timedelta(
                         minutes=self._config.market_data.completed_bar_delay_minutes) <= timestamp]
        expected_day = max(completed) if completed else None
        latest = {r.security_id: r for r in market if r.trade_date == expected_day}
        stale = tuple(sorted(ids - set(latest))) if expected_day is not None else ()
        incomplete = tuple(sorted(sid for sid, row in latest.items()
                                  if any(getattr(row, field) is None for field in
                                         ("raw_open", "raw_high", "raw_low", "raw_close", "volume"))))
        return Snapshot(signal_timestamp=timestamp, universe="sp500", securities=securities,
                        memberships=memberships, market=market, fundamentals=fundamentals,
                        missing_market_security_ids=tuple(sorted(ids - market_ids)),
                        latest_completed_session=expected_day, stale_market_security_ids=stale,
                        incomplete_market_security_ids=incomplete,
                        completed_sessions=tuple(sorted(completed)),
                        benchmark_security=benchmark_security, benchmark_market=benchmark_market)
