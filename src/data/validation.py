"""Fail-loud dataset constraints shared by PIT construction and quality reporting."""
from collections import defaultdict
from datetime import datetime
from typing import Callable, Iterable, TypeVar

from src.data.market_data import completed_bar_floor
from src.data.schemas import Calendar, Contract, DataBundle

T = TypeVar("T")


class Issue(Contract):
    code: str
    dataset: str
    message: str


class DataContractError(ValueError):
    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.code}/{i.dataset}: {i.message}" for i in issues))


def duplicates(rows: Iterable[T], key: Callable[[T], object], dataset: str) -> list[Issue]:
    seen: set[object] = set()
    issues = []
    for row in rows:
        identity = key(row)
        if identity in seen:
            issues.append(Issue(code="duplicate", dataset=dataset, message=str(identity)))
        seen.add(identity)
    return issues


def overlaps(
    rows: Iterable[T], key: Callable[[T], object],
    bounds: Callable[[T], tuple[datetime, datetime | None]], dataset: str,
) -> list[Issue]:
    groups: dict[object, list[T]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    issues = []
    for identity, group in groups.items():
        ordered = sorted(group, key=lambda row: bounds(row)[0])
        for before, after in zip(ordered, ordered[1:]):
            end = bounds(before)[1]
            if end is None or bounds(after)[0] < end:
                issues.append(Issue(code="invalid_interval", dataset=dataset,
                                    message=f"overlapping intervals: {identity}"))
    return issues


def validate_bundle(bundle: DataBundle, calendar: Calendar, delay_minutes: int) -> tuple[Issue, ...]:
    issues: list[Issue] = []
    issues += duplicates(bundle.securities, lambda r: (r.security_id, r.valid_from), "securities")
    issues += duplicates(bundle.memberships,
                         lambda r: (r.security_id, r.index_id, r.effective_from), "memberships")
    issues += duplicates(bundle.market, lambda r: (r.security_id, r.trade_date), "market")
    issues += duplicates(bundle.fundamentals,
                         lambda r: (*r.observation_key(), r.revision_id), "fundamentals")
    issues += overlaps(bundle.securities, lambda r: r.security_id,
                       lambda r: (r.valid_from, r.valid_to), "securities")
    issues += overlaps(bundle.securities, lambda r: (r.exchange, r.ticker),
                       lambda r: (r.valid_from, r.valid_to), "securities")
    issues += overlaps(bundle.memberships, lambda r: (r.security_id, r.index_id),
                       lambda r: (r.effective_from, r.effective_to), "memberships")
    ids = {row.security_id for row in bundle.securities}
    for dataset in ("memberships", "market", "fundamentals"):
        for row in getattr(bundle, dataset):
            if row.security_id not in ids:
                issues.append(Issue(code="orphan_security_id", dataset=dataset,
                                    message=row.security_id))
    for market in bundle.market:
        try:
            floor = completed_bar_floor(market, calendar, delay_minutes)
            if market.available_timestamp < floor:
                raise ValueError("daily bar available before configured completed-bar floor")
        except ValueError as exc:
            issues.append(Issue(code="timestamp_violation", dataset="market", message=str(exc)))
    facts: dict[tuple[object, ...], list[object]] = defaultdict(list)
    # Group before checking chains: never infer revisions by file order or source version.
    for fact in bundle.fundamentals:
        facts[fact.observation_key()].append(fact)
    from src.data.schemas import FundamentalFact

    for key, raw in facts.items():
        group = [r for r in raw if isinstance(r, FundamentalFact)]
        ordered = sorted(group, key=lambda r: (r.available_timestamp, r.revision_id))
        for index, fact in enumerate(ordered):
            prior = ordered[index - 1] if index else None
            expected = prior.revision_id if prior else None
            if fact.supersedes_revision_id != expected or (
                prior and (fact.available_timestamp <= prior.available_timestamp
                           or fact.filing_accepted_at < prior.filing_accepted_at)
            ):
                issues.append(Issue(code="invalid_revision", dataset="fundamentals",
                                    message=f"ambiguous, broken or non-monotone revision chain: {key}"))
    return tuple(issues)
