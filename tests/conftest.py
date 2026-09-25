import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.data.pit_store import PITStore
from src.data.schemas import Calendar, DataBundle
from src.utils.config import load_config

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/p1_02"


def et(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"))


@pytest.fixture
def payload():
    return json.loads((FIXTURES / "canonical.json").read_text())


@pytest.fixture
def bundle(payload):
    return DataBundle.model_validate(payload)


@pytest.fixture
def calendar():
    return Calendar.model_validate_json((FIXTURES / "calendar.json").read_text())


@pytest.fixture
def config():
    return load_config(ROOT / "configs/phase1_baseline.yaml")


@pytest.fixture
def store(bundle, calendar, config):
    return PITStore(bundle, calendar, config)


@pytest.fixture(scope="module")
def feature_data():
    from experiments.phase1.p1_03_fixture import fixture
    return fixture()


@pytest.fixture
def feature_store(feature_data, config):
    bundle, calendar = feature_data
    return PITStore(bundle, calendar, config)


@pytest.fixture
def feature_pipeline(feature_store):
    from src.features.calculators import phase1_pipeline
    return phase1_pipeline(feature_store, benchmark_security_id="SEC_SPY", dataset_version="synthetic-v1")


def context_at(store, stamp, sid="SEC_ALPHA"):
    from src.features.pipeline import FeatureContext
    snap = store.snapshot(signal_timestamp=stamp, benchmark_security_id="SEC_SPY")
    return FeatureContext(sid, snap.signal_timestamp, snap.completed_sessions,
                          tuple(r for r in snap.market if r.security_id == sid), snap.benchmark_market,
                          tuple(r for r in snap.fundamentals if r.security_id == sid),
                          snap.market_anchor_date(sid))
