"""Simple cumulative returns; strictly no future targets or learned transforms."""
from src.features.market_common import market_window, missing, MissingInput, result, total_return_prices
from src.features.pipeline import Computation, FeatureContext


def momentum(context: FeatureContext, name: str) -> Computation:
    if name.startswith("ret_"):
        count = int(name.removeprefix("ret_").removesuffix("d")) + 1
    else:
        count = 253 if name == "momentum_12_1" else 252
    try:
        bars = market_window(context, count)
        prices = total_return_prices(bars)
        if name == "momentum_12_1":
            value = prices[-22] / prices[0] - 1
        elif name == "distance_to_52w_high":
            value = prices[-1] / max(prices) - 1
        else:
            value = prices[-1] / prices[0] - 1
        return result(value, bars)
    except MissingInput as exc:
        return missing(exc)
