from dataclasses import replace
from math import exp, log, sqrt
from statistics import stdev

import pytest

from conftest import et
from src.features.liquidity import liquidity
from src.features.momentum import momentum
from src.features.reversal import reversal
from src.features.risk import risk


def context(feature_store):
    from conftest import context_at
    return context_at(feature_store, et("2025-01-17T16:10"))


def set_prices(ctx, values, benchmark=False):
    rows = list(ctx.benchmark_market if benchmark else ctx.market)
    assert len(rows) >= len(values)
    start = len(rows) - len(values)
    for index, value in enumerate(values, start=start):
        row = rows[index].model_dump()
        row.update({key: value for key in ("open", "high", "low", "close", "raw_open", "raw_high",
                                           "raw_low", "raw_close")})
        rows[index] = type(rows[index]).model_validate(row)
    return replace(ctx, **{"benchmark_market" if benchmark else "market": tuple(rows)})


@pytest.mark.parametrize("horizon", [1, 5, 20, 60, 120, 252])
def test_hand_computed_simple_returns(feature_store, horizon):
    ctx = context(feature_store)
    values = [100. + i for i in range(253)]
    ctx = set_prices(ctx, values)
    assert momentum(ctx, f"ret_{horizon}d").value == pytest.approx(values[-1] / values[-1-horizon] - 1)


def test_momentum_skip_high_and_reversal(feature_store):
    ctx = set_prices(context(feature_store), [100. + i for i in range(253)])
    assert momentum(ctx, "momentum_12_1").value == pytest.approx(331/100-1)
    assert momentum(ctx, "distance_to_52w_high").value == 0.
    assert reversal(ctx, "ret_5d_reversal").value == -momentum(ctx, "ret_5d").value


def test_log_risk_downside_and_beta(feature_store):
    ctx = context(feature_store)
    logs = [-.02, .01, -.01, .03] * 15
    prices = [100.]
    spy_prices = [100.]
    for value in logs:
        prices.append(prices[-1] * exp(value))
        spy_prices.append(spy_prices[-1] * exp(value / 2))
    ctx = set_prices(set_prices(ctx, prices), spy_prices, benchmark=True)
    assert risk(ctx, "realized_vol_60d").value == pytest.approx(stdev(logs)*sqrt(252))
    expected = sqrt(252 * sum(min(r, 0)**2 for r in logs)/60)
    assert risk(ctx, "downside_vol_60d").value == pytest.approx(expected)
    assert risk(ctx, "beta_60d").value == pytest.approx(2.)
    flat = set_prices(ctx, [100.]*61, benchmark=True)
    assert risk(flat, "beta_60d").value is None
    assert risk(flat, "beta_60d").missing_reason == "zero_benchmark_variance"


def test_mdd_is_in_window_peak_to_trough_not_current(feature_store):
    ctx = set_prices(context(feature_store), [100.] * 57 + [200., 80., 210.])
    assert risk(ctx, "max_drawdown_60d").value == pytest.approx(-.6)
    # Excluded earlier peak cannot influence the full 60-price window.
    ctx = set_prices(ctx, [9999.] + [100.] * 60)
    assert risk(ctx, "max_drawdown_60d").value == pytest.approx(0.)


def test_liquidity_raw_dollars_log1p_nonoverlap_and_amihud(feature_store):
    ctx = set_prices(context(feature_store), [100.] * 20 + [200.] * 20)
    assert liquidity(ctx, "adv_usd_20d").value == 200*10000
    assert liquidity(ctx, "dollar_volume_change_20d").value == 1.
    assert liquidity(ctx, "log_dollar_volume_20d").value == pytest.approx(log(1+200*10000))
    assert liquidity(ctx, "amihud_20d").value == pytest.approx(1e6*(1/(200*10000))/20)


def test_split_dividend_no_phantom_return_vol_or_dollar_volume(feature_store):
    ctx = set_prices(context(feature_store), [100.]*40 + [50.]*21)
    rows = list(ctx.market)
    for index in range(len(rows)-21, len(rows)):
        raw = rows[index].model_dump()
        raw.update(volume=20000., split_factor=2. if index == len(rows)-21 else 1.)
        rows[index] = type(rows[index]).model_validate(raw)
    ctx = replace(ctx, market=tuple(rows))
    assert momentum(ctx, "ret_60d").value == pytest.approx(0.)
    assert risk(ctx, "realized_vol_60d").value == pytest.approx(0.)
    assert liquidity(ctx, "dollar_volume_change_20d").value == pytest.approx(0.)
    dividend = set_prices(ctx, [50.]*20+[49.])
    raw = dividend.market[-1].model_dump()
    raw["dividend"] = 1.
    dividend = replace(dividend, market=dividend.market[:-1] +
                        (type(dividend.market[-1]).model_validate(raw),))
    assert momentum(dividend, "ret_1d").value == pytest.approx(0.)


def test_full_window_gaps_and_null_prices_not_filled(feature_store):
    ctx = context(feature_store)
    gap = replace(ctx, market=ctx.market[:-3]+ctx.market[-2:])
    assert momentum(gap, "ret_5d").value is None
    assert liquidity(gap, "adv_usd_20d").value is None
    raw = ctx.market[-1].model_dump()
    raw.update(close=None, raw_close=None)
    missing = replace(ctx, market=ctx.market[:-1]+(type(ctx.market[-1]).model_validate(raw),))
    assert momentum(missing, "ret_5d").value is None
    short = replace(ctx, market=ctx.market[-20:])
    assert risk(short, "realized_vol_20d").value is None
    assert liquidity(short, "adv_usd_20d").value is not None
