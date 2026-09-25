"""PIT-observation windows and corporate-action-consistent economic return chains."""
from math import isfinite, log

from src.data.schemas import MarketRecord, Observation
from src.features.pipeline import Computation, FeatureContext


class MissingInput(ValueError):
    def __init__(self, reason: str, observations: tuple[Observation, ...] = ()) -> None:
        self.reason = reason
        self.observations = observations
        super().__init__(reason)


def market_window(context: FeatureContext, count: int, *, benchmark: bool = False
                  ) -> tuple[MarketRecord, ...]:
    source = context.benchmark_market if benchmark else context.market
    if context.anchor_date is None:
        raise MissingInput("no_available_market_bar")
    days = tuple(day for day in context.completed_sessions if day <= context.anchor_date)[-count:]
    lookup = {bar.trade_date: bar for bar in source}
    observed = tuple(lookup[day] for day in days if day in lookup)
    if len(days) < count or len(observed) < count:
        raise MissingInput("insufficient_or_gapped_market_history", observed)
    if any(bar.raw_close is None for bar in observed):
        raise MissingInput("missing_raw_close", observed)
    return observed


def total_return_prices(bars: tuple[MarketRecord, ...]) -> tuple[float, ...]:
    """Ex-date reinvestment; split_factor is new/old shares, dividend is post-split/share."""
    values = [1.0]
    for before, after in zip(bars, bars[1:]):
        if before.raw_close is None or after.raw_close is None:
            raise MissingInput("missing_raw_close", bars)
        gross = after.split_factor * (after.raw_close + after.dividend) / before.raw_close
        values.append(values[-1] * gross)
    if any(not isfinite(value) or value <= 0 for value in values):
        raise MissingInput("nonfinite_total_return_chain", bars)
    return tuple(values)


def log_returns(prices: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(log(after) - log(before) for before, after in zip(prices, prices[1:]))


def result(value: float, records: tuple[Observation, ...]) -> Computation:
    if not isfinite(value):
        return Computation(None, records, len(records), "nonfinite_calculation")
    return Computation(value, records, len(records))


def missing(error: MissingInput) -> Computation:
    return Computation(None, error.observations, len(error.observations), error.reason)
