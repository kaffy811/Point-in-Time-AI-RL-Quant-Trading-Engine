import pytest

from conftest import et, context_at
from src.features.fiscal import discrete_quarters, trailing_flow
from src.features.fundamentals import fundamental


def test_ytd_to_discrete_quarters_and_ttm(feature_store):
    ctx = context_at(feature_store, et("2025-02-07T16:10"))
    quarters = discrete_quarters(ctx, "revenue")
    assert [q.value for q in quarters[-4:]] == pytest.approx([200., 201., 202., 203.])
    ttm = trailing_flow(ctx, "revenue")
    assert ttm.value == pytest.approx(806.)
    assert len(ttm.quarters) == 4


def test_ttm_does_not_double_count_ytd(feature_store):
    ctx = context_at(feature_store, et("2025-02-07T16:10"))
    # Fixture contains only YTD records, so TTM must be Q1 + (6M-Q1) + ... + (FY-9M).
    assert trailing_flow(ctx, "operating_cash_flow").value == pytest.approx(166.)


def test_ratios_and_missing_prior_eps(feature_store):
    ctx = context_at(feature_store, et("2025-02-07T16:10"))
    assert fundamental(ctx, "earnings_yield").value is not None
    assert fundamental(ctx, "book_to_market").value is not None
    assert fundamental(ctx, "fcf_yield").value is not None
    assert fundamental(ctx, "roe").value is not None
    assert fundamental(ctx, "roa").value is not None
    assert fundamental(ctx, "gross_profit_to_assets").value is not None
    assert fundamental(ctx, "operating_margin").value is not None
    assert fundamental(ctx, "revenue_growth").value is not None
    assert fundamental(ctx, "eps_growth").value is not None
    assert fundamental(ctx, "debt_to_assets").value is not None


def test_amendment_is_invisible_before_available(feature_store):
    before = context_at(feature_store, et("2025-01-19T16:10"))
    after = context_at(feature_store, et("2025-01-21T16:10"))
    before_flow = trailing_flow(before, "common_net_income")
    after_flow = trailing_flow(after, "common_net_income")
    assert before_flow.value != after_flow.value
    assert fundamental(before, "earnings_yield").value != fundamental(after, "earnings_yield").value


def test_incomplete_ttm_is_missing(feature_store):
    ctx = context_at(feature_store, et("2023-06-30T16:10"))
    with pytest.raises(Exception, match="incomplete_ttm_quarters"):
        trailing_flow(ctx, "revenue")



def test_missing_metadata_is_not_guessed(feature_store):
    ctx = context_at(feature_store, et("2025-02-07T16:10"))
    fact_index = next(i for i, row in enumerate(ctx.fundamentals) if row.fact_name == "revenue")
    fact = ctx.fundamentals[fact_index].model_copy(update={"fiscal_year": None})
    altered = ctx.__class__(ctx.security_id, ctx.signal_timestamp, ctx.completed_sessions,
                            ctx.market, ctx.benchmark_market, ctx.fundamentals[:fact_index] + (fact,) + ctx.fundamentals[fact_index + 1:], ctx.anchor_date)
    with pytest.raises(Exception, match="missing_explicit_fiscal_metadata"):
        discrete_quarters(altered, "revenue")


def test_ytd_eps_is_not_differenced_as_if_additive(feature_store):
    ctx = context_at(feature_store, et("2025-02-07T16:10"))
    eps = tuple(row.model_copy(update={"duration_kind": "ytd"})
                for row in ctx.fundamentals if row.fact_name == "diluted_eps")
    altered = ctx.__class__(ctx.security_id, ctx.signal_timestamp, ctx.completed_sessions,
                            ctx.market, ctx.benchmark_market,
                            tuple(row for row in ctx.fundamentals if row.fact_name != "diluted_eps") + eps,
                            ctx.anchor_date)
    with pytest.raises(Exception, match="ytd_eps_not_additive"):
        trailing_flow(altered, "diluted_eps")
