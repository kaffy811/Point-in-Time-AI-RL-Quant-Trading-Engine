"""Raw PIT ratios from discrete-quarter TTM and exact-period instant balances."""
from datetime import date, timedelta

from src.data.schemas import FundamentalFact, Observation
from src.features.fiscal import split_chain, trailing_flow
from src.features.fundamental_registry import CONCEPTS
from src.features.market_common import missing, MissingInput, result
from src.features.pipeline import Computation, FeatureContext


def instant(context: FeatureContext, name: str, end: date | None = None) -> FundamentalFact:
    concept = CONCEPTS[name]
    rows = [r for r in context.fundamentals if r.fact_name == name]
    if end is not None:
        rows = [r for r in rows if r.fiscal_period_end == end]
    elif rows:
        latest = max(r.fiscal_period_end for r in rows)
        rows = [r for r in rows if r.fiscal_period_end == latest]
    if len(rows) != 1:
        raise MissingInput("missing_or_ambiguous_instant_fact", tuple(rows))
    fact = rows[0]
    if fact.unit != concept.unit or fact.period_type != "instant":
        raise MissingInput("fundamental_unit_or_kind_mismatch", (fact,))
    if fact.value is None:
        raise MissingInput("missing_fundamental_value", (fact,))
    return fact


def market_cap(context: FeatureContext) -> tuple[float, tuple[Observation, ...]]:
    shares = instant(context, "shares_outstanding")
    assert shares.value is not None
    if shares.equity_scope != "single_class":
        raise MissingInput("unverified_share_class_scope", (shares,))
    if context.anchor_date is None:
        raise MissingInput("no_available_market_bar", (shares,))
    basis = shares.share_basis_date or shares.fiscal_period_end
    try:
        factor, actions = split_chain(context, basis, context.anchor_date)
    except MissingInput as exc:
        raise MissingInput(exc.reason, (shares,) + exc.observations) from exc
    price = next(r for r in context.market if r.trade_date == context.anchor_date)
    records = (shares, price) + actions
    if price.raw_close is None:
        raise MissingInput("missing_raw_close", records)
    capitalization = price.raw_close * shares.value * factor
    if capitalization <= 0:
        raise MissingInput("nonpositive_market_cap", records)
    return capitalization, records


def fundamental(context: FeatureContext, name: str) -> Computation:
    consumed: tuple[Observation, ...] = ()
    try:
        if name == "book_to_market":
            equity = instant(context, "common_equity")
            consumed += (equity,)
            cap, records = market_cap(context)
            consumed += records
            assert equity.value is not None
            return result(equity.value / cap, consumed)
        if name == "debt_to_assets":
            assets = instant(context, "assets")
            consumed += (assets,)
            has_total = any(r.fact_name == "total_debt" and r.fiscal_period_end == assets.fiscal_period_end
                            for r in context.fundamentals)
            names = ("total_debt",) if has_total else ("current_debt", "long_term_debt")
            debt = 0.
            for concept in names:
                fact = instant(context, concept, assets.fiscal_period_end)
                consumed += (fact,)
                assert fact.value is not None
                debt += fact.value
            assert assets.value is not None
            if assets.value <= 0:
                raise MissingInput("nonpositive_assets")
            return result(debt / assets.value, consumed)
        flow_name = {"earnings_yield": "common_net_income", "fcf_yield": "operating_cash_flow",
                     "roe": "common_net_income", "roa": "net_income",
                     "gross_profit_to_assets": "gross_profit", "operating_margin": "operating_income",
                     "revenue_growth": "revenue", "eps_growth": "diluted_eps"}[name]
        flow = trailing_flow(context, flow_name)
        consumed += flow.observations
        if name in ("revenue_growth", "eps_growth"):
            prior = trailing_flow(context, flow_name, offset=4)
            consumed += prior.observations
            if prior.end + timedelta(days=1) != flow.start:
                raise MissingInput("noncontiguous_yoy_ttm")
            if prior.value <= 0:
                raise MissingInput("nonpositive_prior_ttm")
            return result(flow.value / prior.value - 1, consumed)
        numerator = flow.value
        if name == "fcf_yield":
            capex = trailing_flow(context, "capital_expenditures")
            consumed += capex.observations
            if (capex.start, capex.end) != (flow.start, flow.end):
                raise MissingInput("mismatched_ttm_periods")
            numerator -= capex.value
        if name in ("earnings_yield", "fcf_yield"):
            denominator, records = market_cap(context)
            consumed += records
        elif name == "operating_margin":
            revenue = trailing_flow(context, "revenue")
            consumed += revenue.observations
            if (revenue.start, revenue.end) != (flow.start, flow.end):
                raise MissingInput("mismatched_ttm_periods")
            denominator = revenue.value
        else:
            balance_name = "common_equity" if name == "roe" else "assets"
            current = instant(context, balance_name, flow.end)
            consumed += (current,)
            previous = instant(context, balance_name, flow.start - timedelta(days=1))
            consumed += (previous,)
            assert current.value is not None and previous.value is not None
            denominator = (current.value + previous.value) / 2
        if denominator <= 0:
            raise MissingInput("nonpositive_ratio_denominator")
        return result(numerator / denominator, consumed)
    except MissingInput as exc:
        return missing(MissingInput(exc.reason, consumed + exc.observations))
