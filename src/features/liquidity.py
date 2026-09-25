"""Raw nominal dollar liquidity, never adjusted price times raw volume."""
from math import fsum, log1p

from src.features.market_common import market_window, missing, MissingInput, result, total_return_prices
from src.features.pipeline import Computation, FeatureContext


def liquidity(context: FeatureContext, name: str) -> Computation:
    count = {"adv_usd_20d": 20, "adv_usd_60d": 60, "log_dollar_volume_20d": 20,
             "dollar_volume_change_20d": 40, "amihud_20d": 21}[name]
    try:
        bars = market_window(context, count)
        selected = bars[1:] if name == "amihud_20d" else bars
        if any(bar.volume is None for bar in selected):
            raise MissingInput("missing_raw_volume", bars)
        dollar_volume = tuple(bar.raw_close * bar.volume for bar in selected
                              if bar.raw_close is not None and bar.volume is not None)
        if name == "dollar_volume_change_20d":
            prior = fsum(dollar_volume[:20]) / 20
            if prior <= 0:
                raise MissingInput("nonpositive_prior_dollar_volume", bars)
            value = (fsum(dollar_volume[20:]) / 20) / prior - 1
        elif name == "amihud_20d":
            if any(volume <= 0 for volume in dollar_volume):
                raise MissingInput("nonpositive_dollar_volume", bars)
            prices = total_return_prices(bars)
            returns = tuple(after / before - 1 for before, after in zip(prices, prices[1:]))
            value = 1e6 * fsum(abs(ret) / volume for ret, volume in zip(returns, dollar_volume)) / 20
        else:
            value = fsum(dollar_volume) / count
            if name == "log_dollar_volume_20d":
                value = log1p(value)
        return result(value, bars)
    except MissingInput as exc:
        return missing(exc)
