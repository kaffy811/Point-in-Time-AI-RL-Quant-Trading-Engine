"""Expanding walk-forward split construction with interval purge and embargo."""
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Literal
from zoneinfo import ZoneInfo

from src.alpha.labels import LabelFrame, LabelRow
from src.data.schemas import Calendar
from src.features.contracts import FeatureFrame, FeatureRow
from src.features.registry import FEATURE_REGISTRY
from src.preprocessing.pipeline import Preprocessor, TransformResult
from src.utils.config import Phase1Config

SplitName = Literal["TRAIN", "VALIDATION", "TEST"]


class WalkForwardError(ValueError):
    """Blocking split or leakage contract violation."""


@dataclass(frozen=True)
class FoldManifest:
    fold_id: str
    test_year: int
    train_nominal_start: int
    train_nominal_end: int
    validation_nominal_year: int
    test_nominal_year: int
    validation_effective_start: datetime | None
    test_effective_start: datetime | None
    embargo_sessions: int
    validation_embargoed_sessions: tuple[date, ...]
    test_embargoed_sessions: tuple[date, ...]
    train_candidate_count: int
    train_purged_count: int
    train_embargo_excluded_count: int
    train_missing_label_count: int
    train_invalid_label_count: int
    train_final_count: int
    validation_candidate_count: int
    validation_purged_count: int
    validation_embargo_excluded_count: int
    validation_missing_label_count: int
    validation_invalid_label_count: int
    validation_final_count: int
    test_candidate_count: int
    test_invalid_label_count: int
    test_embargo_excluded_count: int
    test_missing_label_count: int
    test_final_count: int
    invalid_label_reasons: dict[str, int]
    feature_manifest_hash: str
    label_manifest_hash: str
    preprocessor_hash: str
    config_hash: str

    def to_dict(self) -> dict[str, object]:
        return self.__dict__ | {
            "validation_effective_start": self.validation_effective_start.isoformat()
            if self.validation_effective_start else None,
            "test_effective_start": self.test_effective_start.isoformat()
            if self.test_effective_start else None,
            "validation_embargoed_sessions": [day.isoformat()
                                                for day in self.validation_embargoed_sessions],
            "test_embargoed_sessions": [day.isoformat() for day in self.test_embargoed_sessions],
        }


@dataclass(frozen=True)
class FoldOutput:
    manifest: FoldManifest
    train: FeatureFrame
    validation: FeatureFrame
    test: FeatureFrame
    labels: dict[SplitName, tuple[LabelRow, ...]]
    transformed: dict[SplitName, TransformResult]
    preprocessor: Preprocessor


def _signal_year(row: FeatureRow) -> int:
    return row.signal_timestamp.astimezone(ZoneInfo("America/New_York")).year


class WalkForwardBuilder:
    def __init__(self, features: FeatureFrame, labels: LabelFrame, calendar: Calendar,
                 *, config_hash: str = "", embargo_sessions: int = 5,
                 config: Phase1Config | None = None) -> None:
        if embargo_sessions != 5:
            raise WalkForwardError("P1-06 freezes a five-exchange-session embargo")
        if features.data_manifest_hash != labels.data_manifest_hash:
            raise WalkForwardError("feature/label data manifest mismatch")
        self.features = features
        self.labels = labels
        self.calendar = calendar
        self.config_hash = config_hash
        self.config = config
        self.embargo_sessions = embargo_sessions
        self._label_by_key = {(row.security_id, row.signal_timestamp): row for row in labels.rows}
        if len(self._label_by_key) != len(labels.rows):
            raise WalkForwardError("duplicate label sample identity")

    def build(self, test_year: int) -> FoldOutput:
        if not 2017 <= test_year <= 2025:
            raise WalkForwardError("Phase 1 test years are frozen at 2017 through 2025")
        validation_year = test_year - 1
        train_end = test_year - 2
        rows_by_split: dict[SplitName, list[FeatureRow]] = {"TRAIN": [], "VALIDATION": [], "TEST": []}
        for row in self.features.rows:
            year = _signal_year(row)
            split: SplitName | None = (
                "TRAIN" if year <= train_end and year >= 2010 else
                "VALIDATION" if year == validation_year else
                "TEST" if year == test_year else None
            )
            if split is not None:
                rows_by_split[split].append(row)
        validation_start, validation_embargo = self._effective_start(validation_year,
                                                                      rows_by_split["VALIDATION"])
        test_start, test_embargo = self._effective_start(test_year, rows_by_split["TEST"])
        train_final = self._eligible(rows_by_split["TRAIN"], validation_start, ())
        validation_final = self._eligible(rows_by_split["VALIDATION"], test_start,
                                          validation_embargo)
        test_final = self._eligible(rows_by_split["TEST"], None, test_embargo)
        train_frame = self._frame_for(train_final)
        validation_frame = self._frame_for(validation_final)
        test_frame = self._frame_for(test_final)
        if not train_frame.rows:
            raise WalkForwardError(f"fold {test_year} has no usable TRAIN rows")
        lower = self.config.preprocessing.winsorization.lower_quantile if self.config else .01
        upper = self.config.preprocessing.winsorization.upper_quantile if self.config else .99
        interpolation = self.config.preprocessing.winsorization.interpolation if self.config else "linear"
        preprocessor = Preprocessor.fit(train_frame, FEATURE_REGISTRY,
                                        lower_quantile=lower, upper_quantile=upper,
                                        interpolation=interpolation)
        transformed: dict[SplitName, TransformResult] = {
            "TRAIN": preprocessor.transform(train_frame, FEATURE_REGISTRY, split="TRAIN"),
            "VALIDATION": preprocessor.transform(validation_frame, FEATURE_REGISTRY,
                                                  split="VALIDATION"),
            "TEST": preprocessor.transform(test_frame, FEATURE_REGISTRY, split="TEST"),
        }
        self._assert_disjoint(train_final, validation_final, test_final)
        self._assert_temporal(train_final, validation_final, test_final,
                              validation_start, test_start)
        manifest = FoldManifest(
            fold_id=f"fold_{test_year}", test_year=test_year,
            train_nominal_start=2010, train_nominal_end=train_end,
            validation_nominal_year=validation_year, test_nominal_year=test_year,
            validation_effective_start=validation_start, test_effective_start=test_start,
            embargo_sessions=self.embargo_sessions,
            validation_embargoed_sessions=validation_embargo,
            test_embargoed_sessions=test_embargo,
            train_candidate_count=len(rows_by_split["TRAIN"]),
            train_purged_count=self._purged_count(rows_by_split["TRAIN"], validation_start, ()),
            train_embargo_excluded_count=0,
            train_missing_label_count=self._missing_count(rows_by_split["TRAIN"]),
            train_invalid_label_count=self._invalid_count(rows_by_split["TRAIN"]),
            train_final_count=len(train_final),
            validation_candidate_count=len(rows_by_split["VALIDATION"]),
            validation_purged_count=self._purged_count(rows_by_split["VALIDATION"], test_start,
                                                       validation_embargo),
            validation_embargo_excluded_count=self._embargo_count(rows_by_split["VALIDATION"],
                                                                  validation_embargo),
            validation_missing_label_count=self._missing_count(rows_by_split["VALIDATION"]),
            validation_invalid_label_count=self._invalid_count(rows_by_split["VALIDATION"]),
            validation_final_count=len(validation_final),
            test_candidate_count=len(rows_by_split["TEST"]),
            test_invalid_label_count=self._invalid_count(rows_by_split["TEST"]),
            test_embargo_excluded_count=self._embargo_count(rows_by_split["TEST"], test_embargo),
            test_missing_label_count=self._missing_count(rows_by_split["TEST"]),
            test_final_count=len(test_final),
            invalid_label_reasons=self._invalid_reasons(rows_by_split),
            feature_manifest_hash=self.features.data_manifest_hash,
            label_manifest_hash=self.labels.content_hash(),
            preprocessor_hash=hashlib.sha256(
                json.dumps(preprocessor.to_dict(), sort_keys=True, default=str).encode()).hexdigest(),
            config_hash=self.config_hash,
        )
        label_sets: dict[SplitName, tuple[LabelRow, ...]] = {
            "TRAIN": tuple(self._label_by_key[(row.security_id, row.signal_timestamp)]
                           for row in train_final),
            "VALIDATION": tuple(self._label_by_key[(row.security_id, row.signal_timestamp)]
                                 for row in validation_final),
            "TEST": tuple(self._label_by_key[(row.security_id, row.signal_timestamp)]
                           for row in test_final),
        }
        return FoldOutput(manifest, train_frame, validation_frame, test_frame,
                          label_sets, transformed, preprocessor)

    def _effective_start(self, year: int, rows: list[FeatureRow]) -> tuple[datetime | None, tuple[date, ...]]:
        start = date(year, 1, 1)
        sessions = tuple(session for session in sorted(self.calendar.sessions,
                                                        key=lambda item: item.trade_date)
                         if session.trade_date >= start)
        if len(sessions) < self.embargo_sessions:
            raise WalkForwardError(f"calendar lacks {self.embargo_sessions} sessions after {start}")
        embargoed = tuple(session.trade_date for session in sessions[:self.embargo_sessions])
        candidates = [row for row in rows if row.signal_timestamp.astimezone(
            ZoneInfo("America/New_York")).date() not in embargoed]
        effective = min((row.signal_timestamp for row in candidates), default=None)
        return effective, embargoed

    def _eligible(self, rows: list[FeatureRow], downstream_start: datetime | None,
                  embargoed: tuple[date, ...]) -> list[FeatureRow]:
        result: list[FeatureRow] = []
        for row in rows:
            label = self._label_by_key.get((row.security_id, row.signal_timestamp))
            if label is None:
                raise WalkForwardError(
                    f"MISSING_LABEL_RECORD: {row.security_id}/{row.signal_timestamp.isoformat()}")
            if row.signal_timestamp.astimezone(ZoneInfo("America/New_York")).date() in embargoed:
                continue
            if not label.label_valid:
                continue
            if (label.entry_execution_timestamp is None or label.exit_execution_timestamp is None
                    or label.label_end_timestamp is None
                    or label.label_end_timestamp != label.exit_execution_timestamp):
                raise WalkForwardError("valid label has incomplete execution interval")
            if downstream_start is not None and (
                    label.label_end_timestamp is None or label.label_end_timestamp >= downstream_start):
                continue
            if label.label_end_timestamp is not None and label.label_end_timestamp.year > 2025:
                continue
            result.append(row)
        return result

    def _invalid_count(self, rows: list[FeatureRow]) -> int:
        return sum(1 for row in rows if not (self._label_by_key.get(
            (row.security_id, row.signal_timestamp)) and self._label_by_key[
                (row.security_id, row.signal_timestamp)].label_valid))

    def _missing_count(self, rows: list[FeatureRow]) -> int:
        return sum(1 for row in rows if (row.security_id, row.signal_timestamp) not in self._label_by_key)

    def _purged_count(self, rows: list[FeatureRow], boundary: datetime | None,
                      embargoed: tuple[date, ...]) -> int:
        if boundary is None:
            return 0
        count = 0
        for row in rows:
            if row.signal_timestamp.astimezone(ZoneInfo("America/New_York")).date() in embargoed:
                continue
            label = self._label_by_key.get((row.security_id, row.signal_timestamp))
            if label is not None and label.label_valid and label.label_end_timestamp is not None \
                    and label.label_end_timestamp >= boundary:
                count += 1
        return count

    @staticmethod
    def _embargo_count(rows: list[FeatureRow], embargoed: tuple[date, ...]) -> int:
        return sum(1 for row in rows if row.signal_timestamp.astimezone(
            ZoneInfo("America/New_York")).date() in embargoed)

    def _invalid_reasons(self, rows_by_split: dict[SplitName, list[FeatureRow]]) -> dict[str, int]:
        reasons: dict[str, int] = {}
        for rows in rows_by_split.values():
            for row in rows:
                label = self._label_by_key.get((row.security_id, row.signal_timestamp))
                if label is not None and not label.label_valid:
                    reason = label.invalid_reason or "UNKNOWN"
                    reasons[reason] = reasons.get(reason, 0) + 1
        return reasons

    def _frame_for(self, rows: list[FeatureRow]) -> FeatureFrame:
        snapshots = tuple(snapshot for snapshot in self.features.snapshots
                          if any(row.signal_timestamp == snapshot.signal_timestamp for row in rows))
        references = {reference_id for row in rows for value in row.values
                      for reference_id in value.input_references}
        inputs = tuple(ref for ref in self.features.inputs if ref.reference_id in references)
        return self.features.model_copy(update={"rows": tuple(rows), "snapshots": snapshots,
                                                "inputs": inputs})

    @staticmethod
    def _assert_disjoint(*splits: list[FeatureRow]) -> None:
        keys = [{(row.security_id, row.signal_timestamp) for row in rows} for rows in splits]
        if any(keys[i] & keys[j] for i in range(len(keys)) for j in range(i + 1, len(keys))):
            raise WalkForwardError("fold sample keys overlap")

    def _assert_temporal(self, train: list[FeatureRow], validation: list[FeatureRow],
                         test: list[FeatureRow], validation_start: datetime | None,
                         test_start: datetime | None) -> None:
        for earlier, later in ((train, validation), (validation, test)):
            if earlier and later and max(row.signal_timestamp for row in earlier) >= min(
                    row.signal_timestamp for row in later):
                raise WalkForwardError("fold signal timestamps are not strictly ordered")
        for rows, boundary in ((train, validation_start), (validation, test_start)):
            if boundary is not None:
                crossing = False
                for row in rows:
                    label_end = self._label_by_key[(row.security_id, row.signal_timestamp)].label_end_timestamp
                    if label_end is None or label_end >= boundary:
                        crossing = True
                        break
                if crossing:
                    raise WalkForwardError("sample label interval crosses downstream boundary")
