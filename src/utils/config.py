"""Strict frozen research configuration; no experiment execution."""

import hashlib
import json
from datetime import date, time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Universe(StrictModel):
    name: Literal["sp500_pit"]


class Research(StrictModel):
    start: date
    end: date
    reserved_year: Literal[2026]

    @model_validator(mode="after")
    def frozen_period(self) -> "Research":
        if self.start != date(2010, 1, 1) or self.end != date(2025, 12, 31):
            raise ValueError("Research interval is frozen at 2010–2025")
        return self


class Signal(StrictModel):
    frequency: Literal["weekly"]
    timestamp: Literal["post_close"]
    formation_time: time

    @model_validator(mode="after")
    def post_close(self) -> "Signal":
        if self.formation_time != time(16, 10):
            raise ValueError("Approved formation time is 16:10 ET")
        return self
    timezone: Literal["America/New_York"]


class MarketData(StrictModel):
    completed_bar_delay_minutes: Literal[5]


class Winsorization(StrictModel):
    enabled: Literal[True]
    lower_quantile: float = Field(ge=0.01, le=0.01)
    upper_quantile: float = Field(ge=0.99, le=0.99)
    interpolation: Literal["linear"]


class Imputation(StrictModel):
    method: Literal["median"]


class Scaling(StrictModel):
    enabled: Literal[False]


class FeatureSelection(StrictModel):
    enabled: Literal[False]


class Preprocessing(StrictModel):
    winsorization: Winsorization
    imputation: Imputation
    scaling: Scaling
    feature_selection: FeatureSelection


class Execution(StrictModel):
    timing: Literal["next_open"]


class Label(StrictModel):
    horizon_trading_days: Literal[5]
    benchmark: Literal["SPY"]


class Selection(StrictModel):
    top_k: Literal[25]


class Validation(StrictModel):
    scheme: Literal["expanding_walk_forward"]
    purge_days: Literal[5]
    embargo_days: Literal[5]


class Cost(StrictModel):
    base_bps: Literal[10]
    sensitivity_bps: tuple[int, ...]

    @model_validator(mode="after")
    def frozen_scenarios(self) -> "Cost":
        if self.sensitivity_bps != (5, 10, 20):
            raise ValueError("Frozen cost scenarios must be [5, 10, 20]")
        return self


class Portfolio(StrictModel):
    long_only: Literal[True]
    max_position: float = Field(ge=0.10, le=0.10)
    max_sector: float = Field(ge=0.30, le=0.30)


class Model(StrictModel):
    type: Literal["lightgbm_regressor"]
    objective: Literal["regression"]
    learning_rate: float = Field(gt=0, le=1)
    num_leaves: int = Field(ge=2)
    min_child_samples: int = Field(ge=1)
    feature_fraction: float = Field(gt=0, le=1)
    bagging_fraction: float = Field(gt=0, le=1)
    lambda_l2: float = Field(ge=0)


class Phase1Config(StrictModel):
    universe: Universe
    research: Research
    signal: Signal
    market_data: MarketData
    preprocessing: Preprocessing
    execution: Execution
    label: Label
    selection: Selection
    validation: Validation
    cost: Cost
    portfolio: Portfolio
    model: Model
    seed: int = Field(ge=0)

    def config_hash(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject silently overwritten YAML research assumptions."""


def _mapping(loader: UniqueKeyLoader, node: yaml.MappingNode) -> dict[object, object]:
    result: dict[object, object] = {}
    # PyYAML stubs leave construct_object untyped; validate its output via Pydantic.
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)  # type: ignore[no-untyped-call]
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)  # type: ignore[no-untyped-call]
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_config(path: str | Path) -> Phase1Config:
    with Path(path).open(encoding="utf-8") as stream:
        payload = yaml.load(stream, Loader=UniqueKeyLoader)
    return Phase1Config.model_validate(payload)
