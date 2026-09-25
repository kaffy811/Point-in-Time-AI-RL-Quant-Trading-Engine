"""Raw one-day return and sign-explicit five-day reversal."""
from dataclasses import replace

from src.features.momentum import momentum
from src.features.pipeline import Computation, FeatureContext


def reversal(context: FeatureContext, name: str) -> Computation:
    calculated = momentum(context, "ret_5d" if name == "ret_5d_reversal" else "ret_1d")
    if name == "ret_5d_reversal" and calculated.value is not None:
        return replace(calculated, value=-calculated.value)
    return calculated
