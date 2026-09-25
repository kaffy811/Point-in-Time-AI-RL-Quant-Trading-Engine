"""Executable forward-return labels; intentionally separate from FeatureFrame."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo

from src.data.pit_store import PITStore
from src.returns.economic_return import ReturnError, economic_total_return

LABEL_VERSION = "phase1_label_v1"
SCHEDULE_VERSION = "calendar_weekly_next_open_v1"


class LabelError(ValueError):
    """Invalid label configuration or schedule."""


@dataclass(frozen=True)
class LabelRow:
    security_id: str
    signal_timestamp: datetime
    entry_execution_timestamp: datetime | None
    exit_execution_timestamp: datetime | None
    label_end_timestamp: datetime | None
    holding_session_count: int | None
    security_total_return: float | None
    benchmark_total_return: float | None
    target_excess_return: float | None
    label_valid: bool
    invalid_reason: str | None
    label_version: str = LABEL_VERSION
    data_manifest_hash: str = ""
    schedule_version: str = SCHEDULE_VERSION


@dataclass(frozen=True)
class LabelFrame:
    rows: tuple[LabelRow, ...]
    label_version: str
    schedule_version: str
    data_manifest_hash: str
    is_forward_looking: Literal[True] = True

    def to_dict(self) -> dict[str, object]:
        return {
            "label_version": self.label_version,
            "schedule_version": self.schedule_version,
            "data_manifest_hash": self.data_manifest_hash,
            "is_forward_looking": self.is_forward_looking,
            "rows": [row.__dict__ for row in self.rows],
        }

    def content_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LabelError("signal timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


class ExecutableLabelBuilder:
    """Build labels from explicit signal timestamps and the canonical schedule."""

    def __init__(self, store: PITStore, *, benchmark_security_id: str = "SEC_SPY",
                 dataset_version: str = "phase1-label") -> None:
        self.store = store
        self.benchmark_security_id = benchmark_security_id
        self.dataset_version = dataset_version

    def build(self, signal_timestamps: tuple[datetime, ...]) -> LabelFrame:
        signals = tuple(sorted({_utc(value) for value in signal_timestamps}))
        if len(signals) < 2:
            raise LabelError("at least two signal timestamps are required for a holding interval")
        self._validate_signal_schedule(signals)
        manifest_hash = self.store.data_manifest_hash(self.dataset_version)
        output: list[LabelRow] = []
        for index, signal in enumerate(signals[:-1]):
            next_signal = signals[index + 1]
            entry: datetime | None = None
            exit_time: datetime | None = None
            try:
                entry, entry_session = self.store.next_execution_open(signal)
                exit_time, exit_session = self.store.next_execution_open(next_signal)
                if entry >= exit_time:
                    raise LabelError("INVALID_EXECUTION_SCHEDULE")
                snapshot = self.store.snapshot(signal_timestamp=signal,
                                               benchmark_security_id=self.benchmark_security_id)
            except (LabelError, ValueError) as exc:
                reason = str(exc) if str(exc) else "INVALID_EXECUTION_SCHEDULE"
                for security_id in self._eligible_ids(signal):
                    output.append(self._invalid(security_id, signal, reason, manifest_hash,
                                                entry, exit_time))
                continue
            for security_id in snapshot.security_ids:
                output.append(self._make_row(security_id, signal, entry, exit_time,
                                             entry_session.trade_date, exit_session.trade_date,
                                             manifest_hash))
        return LabelFrame(tuple(output), LABEL_VERSION, SCHEDULE_VERSION, manifest_hash)

    def _validate_signal_schedule(self, signals: tuple[datetime, ...]) -> None:
        for current, following in zip(signals, signals[1:]):
            timezone_name = ZoneInfo(self.store._config.signal.timezone)
            local_current = current.astimezone(timezone_name).date()
            local_following = following.astimezone(timezone_name).date()
            if self.store._calendar.session(local_current) is None or self.store._calendar.session(
                    local_following) is None:
                raise LabelError("INVALID_EXECUTION_SCHEDULE")
            if not 3 <= (local_following - local_current).days <= 10:
                raise LabelError("INVALID_EXECUTION_SCHEDULE")

    def _eligible_ids(self, signal: datetime) -> tuple[str, ...]:
        try:
            return self.store.snapshot(signal_timestamp=signal).security_ids
        except ValueError:
            return ()

    def _invalid(self, security_id: str, signal: datetime, reason: str,
                 manifest_hash: str, entry: datetime | None, exit_time: datetime | None) -> LabelRow:
        return LabelRow(security_id, signal, entry, exit_time, exit_time,
                        None, None, None, None, False, reason,
                        data_manifest_hash=manifest_hash)

    def _make_row(self, security_id: str, signal: datetime, entry: datetime,
                  exit_time: datetime, entry_date: date, exit_date: date,
                  manifest_hash: str) -> LabelRow:
        security_records = self.store.forward_market(security_id, entry_date, exit_date)
        benchmark_records = self.store.forward_market(self.benchmark_security_id,
                                                       entry_date, exit_date)
        expected_dates = tuple(session.trade_date for session in
                               self.store.calendar_sessions(entry_date, exit_date))
        try:
            security_return = economic_total_return(security_records, entry_date, exit_date,
                                                    expected_dates=expected_dates)
        except ReturnError as exc:
            return self._invalid(security_id, signal, str(exc), manifest_hash, entry, exit_time)
        try:
            benchmark_return = economic_total_return(benchmark_records, entry_date, exit_date,
                                                     expected_dates=expected_dates)
        except ReturnError as exc:
            reason = str(exc)
            return self._invalid(security_id, signal,
                                 reason if reason == "UNSUPPORTED_CORPORATE_ACTION"
                                 else "MISSING_BENCHMARK", manifest_hash, entry, exit_time)
        return LabelRow(security_id, signal, entry, exit_time, exit_time,
                        len(expected_dates) - 1, security_return,
                        benchmark_return, security_return - benchmark_return, True, None,
                        data_manifest_hash=manifest_hash)
