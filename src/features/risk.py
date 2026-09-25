"""Daily log-return risk and negative trailing peak-to-trough drawdowns."""
from math import fsum, sqrt
from statistics import stdev

from src.features.market_common import (
    log_returns, market_window, missing, MissingInput, result, total_return_prices,
)
from src.features.pipeline import Computation, FeatureContext

ANNUAL_TRADING_OBSERVATIONS = 252  # Frozen RDR-007 convention, also exposed in registry.


def risk(context: FeatureContext, name: str) -> Computation:
    horizon = int(name.rsplit("_", 1)[1].removesuffix("d"))
    try:
        bars = market_window(context, horizon if name.startswith("max_drawdown_") else horizon + 1)
        prices = total_return_prices(bars)
        if name.startswith("max_drawdown_"):
            peak = prices[0]
            minimum = 0.0
            for value in prices:
                peak = max(peak, value)
                minimum = min(minimum, value / peak - 1)
            return result(minimum, bars)
        returns = log_returns(prices)
        if name.startswith("realized_vol_"):
            return result(stdev(returns) * sqrt(ANNUAL_TRADING_OBSERVATIONS), bars)
        if name == "downside_vol_60d":
            return result(sqrt(ANNUAL_TRADING_OBSERVATIONS *
                               fsum(min(value, 0.) ** 2 for value in returns) / horizon), bars)
        benchmark = market_window(context, horizon + 1, benchmark=True)
        market_returns = log_returns(total_return_prices(benchmark))
        x_mean, y_mean = fsum(returns) / horizon, fsum(market_returns) / horizon
        variance_sum = fsum((value - y_mean) ** 2 for value in market_returns)
        if variance_sum == 0:
            raise MissingInput("zero_benchmark_variance", bars + benchmark)
        covariance_sum = fsum((x - x_mean) * (y - y_mean)
                              for x, y in zip(returns, market_returns))
        return result(covariance_sum / variance_sum, bars + benchmark)
    except MissingInput as exc:
        return missing(exc)
