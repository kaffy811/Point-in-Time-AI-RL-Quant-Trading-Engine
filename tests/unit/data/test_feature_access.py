from copy import deepcopy
from datetime import date

import pytest

from conftest import et
from src.data.pit_store import PITStore
from src.data.schemas import DataBundle


def test_benchmark_history_separate_from_candidates(payload, calendar, config):
    spy = deepcopy(payload["securities"][4])
    spy.update(security_id="SEC_SPY", ticker="SPY")
    payload["securities"].append(spy)
    bar = deepcopy(payload["market"][0])
    bar["security_id"] = "SEC_SPY"
    payload["market"].append(bar)
    store = PITStore(DataBundle.model_validate(payload), calendar, config)
    snap = store.snapshot(signal_timestamp=et("2024-07-05T16:10"),
                          benchmark_security_id="SEC_SPY")
    assert snap.benchmark_security.security_id == "SEC_SPY"
    assert "SEC_SPY" not in snap.security_ids
    assert len(snap.benchmark_market) == 1
    assert snap.completed_sessions[-1] == date(2024, 7, 5)
    assert all(r.security_id != "SEC_SPY" for r in snap.market)
    assert len(store.data_manifest_hash("synthetic-v1")) == 64


def test_pre_membership_market_history_is_retained(payload, calendar, config):
    payload["memberships"][2]["effective_from"] = "2024-07-05T00:00:00Z"
    store = PITStore(DataBundle.model_validate(payload), calendar, config)
    snap = store.snapshot(signal_timestamp=et("2024-07-05T16:10"))
    assert "SEC123" in snap.security_ids
    assert any(r.security_id == "SEC123" and r.trade_date == date(2024, 7, 3)
               for r in snap.market)


def test_benchmark_unknown_identity_fails(store):
    with pytest.raises(ValueError, match="benchmark"):
        store.snapshot(signal_timestamp=et("2024-07-05T16:10"), benchmark_security_id="UNKNOWN")
