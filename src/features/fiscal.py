"""As-of reconstruction of nonoverlapping quarters; never sum overlapping YTD facts."""
from dataclasses import dataclass
from datetime import date, timedelta
from math import isclose

from src.data.schemas import FundamentalFact, Observation
from src.features.fundamental_registry import CONCEPTS
from src.features.market_common import MissingInput
from src.features.pipeline import FeatureContext


@dataclass(frozen=True)
class Quarter:
    ordinal: int
    start: date
    end: date
    value: float | None
    observations: tuple[Observation, ...]
    missing_reason: str | None = None


@dataclass(frozen=True)
class TrailingFlow:
    start: date
    end: date
    value: float
    observations: tuple[Observation, ...]
    quarters: tuple[Quarter, ...]


def split_chain(context: FeatureContext, basis: date, end: date) -> tuple[float, tuple[Observation, ...]]:
    if basis > end:
        raise MissingInput("share_basis_after_price_date")
    if not context.completed_sessions or basis < context.completed_sessions[0]:
        # Absence of earlier schedule coverage cannot certify that no split occurred.
        raise MissingInput("insufficient_share_adjustment_history")
    days = tuple(day for day in context.completed_sessions if basis < day <= end)
    lookup = {bar.trade_date: bar for bar in context.market}
    bars = tuple(lookup[day] for day in days if day in lookup)
    if len(bars) != len(days):
        raise MissingInput("missing_split_history", bars)
    factor = 1.
    for bar in bars:
        factor *= bar.split_factor
    return factor, bars


def normalized_value(fact: FundamentalFact, context: FeatureContext
                     ) -> tuple[float | None, tuple[Observation, ...], str | None]:
    if fact.value is None:
        return None, (fact,), "missing_fundamental_value"
    if fact.fact_name == "capital_expenditures" and fact.value < 0:
        return None, (fact,), "capex_not_normalized_positive_outflow"
    if fact.fact_name == "diluted_eps":
        if fact.share_basis_date is None or context.anchor_date is None:
            return None, (fact,), "missing_eps_share_basis"
        try:
            factor, actions = split_chain(context, fact.share_basis_date, context.anchor_date)
            return fact.value / factor, (fact,) + actions, None
        except MissingInput as exc:
            return None, (fact,) + exc.observations, exc.reason
    return fact.value, (fact,), None


def discrete_quarters(context: FeatureContext, name: str) -> tuple[Quarter, ...]:
    concept = CONCEPTS[name]
    matching = [fact for fact in context.fundamentals if fact.fact_name == name]
    if not matching:
        raise MissingInput("no_visible_fundamental_fact")
    if any(fact.unit != concept.unit or fact.period_type != "duration" for fact in matching):
        raise MissingInput("fundamental_unit_or_kind_mismatch", tuple(matching))
    if any(fact.fiscal_year is None or fact.fiscal_quarter is None for fact in matching):
        raise MissingInput("missing_explicit_fiscal_metadata", tuple(matching))
    grouped: dict[int, list[FundamentalFact]] = {}
    for fact in matching:
        assert fact.fiscal_year is not None and fact.fiscal_quarter is not None
        grouped.setdefault(fact.fiscal_year * 4 + fact.fiscal_quarter - 1, []).append(fact)
    quarters = []
    for ordinal in sorted(grouped):
        group = grouped[ordinal]
        endpoints = {(r.fiscal_quarter_start, r.fiscal_period_end, r.fiscal_year_start) for r in group}
        if len(endpoints) != 1:
            raise MissingInput("ambiguous_fiscal_periods", tuple(group))
        representative = group[0]
        assert representative.fiscal_quarter_start is not None
        # EPS is a ratio over weighted-average shares; YTD EPS cannot be
        # differenced into a valid quarter when shares change. Require direct
        # quarter EPS (or a future explicitly normalized earnings/share input).
        if name == "diluted_eps" and any(
            r.duration_kind == "ytd" and r.fiscal_quarter != 1 for r in group
        ) and not any(r.duration_kind == "quarter" for r in group):
            quarters.append(Quarter(
                ordinal, representative.fiscal_quarter_start,
                representative.fiscal_period_end, None,
                tuple(group), "ytd_eps_not_additive"))
            continue
        direct = [r for r in group if r.duration_kind == "quarter" or r.fiscal_quarter == 1]
        cumulative = [r for r in group if r.duration_kind == "ytd" and r.fiscal_quarter != 1]
        candidates: list[tuple[float | None, tuple[Observation, ...], str | None]] = []
        for fact in direct:
            candidates.append(normalized_value(fact, context))
        for fact in cumulative:
            predecessors = [r for r in grouped.get(ordinal - 1, [])
                            if r.fiscal_year == fact.fiscal_year and r.duration_kind == "ytd"
                            and r.fiscal_year_start == fact.fiscal_year_start
                            and r.fiscal_period_end + timedelta(days=1) == fact.fiscal_quarter_start]
            # Q1 standalone is itself first-quarter YTD; no other standalone substitutes for YTD.
            if fact.fiscal_quarter == 2 and not predecessors:
                predecessors = [r for r in grouped.get(ordinal - 1, [])
                                if r.fiscal_year == fact.fiscal_year and r.fiscal_quarter == 1
                                and r.fiscal_year_start == fact.fiscal_year_start
                                and r.fiscal_period_end + timedelta(days=1) == fact.fiscal_quarter_start]
            if len(predecessors) != 1:
                if not direct:
                    candidates.append((None, (fact,), "missing_or_ambiguous_ytd_predecessor"))
                continue
            previous = predecessors[0]
            current_value, current_refs, current_error = normalized_value(fact, context)
            prior_value, prior_refs, prior_error = normalized_value(previous, context)
            value = (current_value - prior_value
                     if current_value is not None and prior_value is not None else None)
            candidates.append((value, current_refs + prior_refs, current_error or prior_error))
        refs = tuple(r for _, observations, _ in candidates for r in observations)
        good = [value for value, _, _ in candidates if value is not None]
        error = next((reason for value, _, reason in candidates if value is None), None)
        if good and any(not isclose(value, good[0], rel_tol=1e-10, abs_tol=1e-12) for value in good):
            error = "inconsistent_quarter_and_ytd_values"
        value = good[0] if good and error is None else None
        if name == "capital_expenditures" and value is not None and value < 0:
            value, error = None, "negative_discrete_capex_outflow"
        quarters.append(Quarter(ordinal, representative.fiscal_quarter_start,
                                representative.fiscal_period_end, value, refs,
                                error if value is None else None))
    return tuple(quarters)


def trailing_flow(context: FeatureContext, name: str, *, offset: int = 0) -> TrailingFlow:
    quarters = discrete_quarters(context, name)
    latest = quarters[-1].ordinal - offset
    lookup = {q.ordinal: q for q in quarters}
    selected = tuple(lookup[i] for i in range(latest - 3, latest + 1) if i in lookup)
    refs = tuple(r for quarter in selected for r in quarter.observations)
    if len(selected) != 4:
        raise MissingInput("incomplete_ttm_quarters", refs)
    if any(q.value is None for q in selected):
        raise MissingInput(next(q.missing_reason or "invalid_discrete_quarter"
                                for q in selected if q.value is None), refs)
    if any(before.end + timedelta(days=1) != after.start
           for before, after in zip(selected, selected[1:])):
        raise MissingInput("noncontiguous_or_overlapping_quarters", refs)
    value = sum(q.value for q in selected if q.value is not None)
    return TrailingFlow(selected[0].start, selected[-1].end, value, refs, selected)
