"""Frozen Phase 1 calculator wiring. No feature selection or learned transforms."""
from functools import partial

from src.data.pit_store import PITStore
from src.features.fundamentals import fundamental
from src.features.liquidity import liquidity
from src.features.momentum import momentum
from src.features.pipeline import Calculator, FeaturePipeline
from src.features.registry import FEATURE_REGISTRY, FUNDAMENTALS, LIQUIDITY, MOMENTUM, REVERSAL, RISK
from src.features.reversal import reversal
from src.features.risk import risk


def phase1_calculators() -> dict[str, Calculator]:
    calculators: dict[str, Calculator] = {}
    for names, calculator in ((MOMENTUM, momentum), (REVERSAL, reversal), (RISK, risk),
                              (LIQUIDITY, liquidity), (FUNDAMENTALS, fundamental)):
        for name in names:
            calculators[name] = partial(calculator, name=name)
    return calculators


def phase1_pipeline(store: PITStore, *, benchmark_security_id: str, dataset_version: str
                    ) -> FeaturePipeline:
    return FeaturePipeline(store, FEATURE_REGISTRY, phase1_calculators(),
                           benchmark_security_id=benchmark_security_id, dataset_version=dataset_version)
