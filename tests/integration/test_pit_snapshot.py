from conftest import et
from src.data.pit_store import PITStore, Snapshot
from src.data.schemas import DataBundle


def test_unified_snapshot_all_records_obey_knowledge_cutoff(store, payload, calendar, config):
    signal = et("2024-08-02T16:10")
    snapshot = store.snapshot(signal_timestamp=signal)
    for dataset in (snapshot.securities, snapshot.memberships, snapshot.market, snapshot.fundamentals):
        assert all(row.available_timestamp <= snapshot.signal_timestamp for row in dataset)
        assert all(row.security_id in snapshot.security_ids for row in dataset)
    assert Snapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    # Storage order must not influence snapshots or revision selection.
    reversed_bundle = DataBundle.model_validate({k: list(reversed(v)) for k, v in payload.items()})
    assert PITStore(reversed_bundle, calendar, config).snapshot(signal_timestamp=signal) == snapshot
