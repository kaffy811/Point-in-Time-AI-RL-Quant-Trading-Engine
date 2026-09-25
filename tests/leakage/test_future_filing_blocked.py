from conftest import et


def test_filing_acceptance_not_period_end_controls_visibility(store):
    before = store.snapshot(signal_timestamp=et("2024-08-02T14:59:59"))
    at = store.snapshot(signal_timestamp=et("2024-08-02T15:00:00"))
    assert not before.fundamentals
    assert {r.revision_id for r in at.fundamentals} == {"r1", "missing"}
    assert all(r.filing_accepted_at <= at.signal_timestamp for r in at.fundamentals)
