from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.utils.config import Phase1Config, load_config

CONFIG = Path(__file__).resolve().parents[2] / "configs/phase1_baseline.yaml"


def test_frozen_baseline() -> None:
    config = load_config(CONFIG)
    assert config.cost.sensitivity_bps == (5, 10, 20)
    assert config.label.horizon_trading_days == 5
    assert config.research.end.year == 2025
    assert len(config.config_hash()) == 64


@pytest.mark.parametrize("section,key,value", [
    ("label", "horizon_trading_days", 10),
    ("label", "benchmark", "QQQ"),
    ("cost", "base_bps", 0),
    ("cost", "sensitivity_bps", [0, 10, 20]),
    ("universe", "name", "sp500_current"),
    ("validation", "purge_days", 0),
    ("validation", "embargo_days", 0),
    ("research", "end", "2026-12-31"),
    ("model", "learning_rate", -0.1),
    ("model", "unknown", 1),
    ("portfolio", "max_position", 0.2),
    ("portfolio", "max_sector", 0.4),
    ("signal", "timestamp", "market_close"),
    ("signal", "formation_time", "16:00"),
    ("market_data", "completed_bar_delay_minutes", 0),
])
def test_invalid_assumptions_rejected(section, key, value) -> None:
    data = yaml.safe_load(CONFIG.read_text())
    data[section][key] = value
    with pytest.raises(ValidationError):
        Phase1Config.model_validate(data)


def test_hash_is_order_independent_and_sensitive() -> None:
    data = yaml.safe_load(CONFIG.read_text())
    baseline = Phase1Config.model_validate(data)
    reordered = Phase1Config.model_validate(dict(reversed(list(data.items()))))
    assert baseline.config_hash() == reordered.config_hash()
    data["seed"] += 1
    assert baseline.config_hash() != Phase1Config.model_validate(data).config_hash()


def test_duplicate_yaml_key_rejected(tmp_path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text(CONFIG.read_text() + "\nseed: 99\n")
    with pytest.raises(ValueError, match="Duplicate"):
        load_config(path)


def test_config_immutable() -> None:
    config = load_config(CONFIG)
    with pytest.raises(ValidationError):
        config.cost.base_bps = 5


@pytest.mark.parametrize("payload", ["", "[]", "seed: 42", "!!python/object:bad {}"])
def test_malformed_config(tmp_path, payload) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(payload)
    with pytest.raises((ValidationError, yaml.YAMLError)):
        load_config(path)
