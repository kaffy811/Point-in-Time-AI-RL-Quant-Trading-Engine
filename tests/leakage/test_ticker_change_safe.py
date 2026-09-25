from conftest import et


def test_ticker_change_preserves_internal_identity(store):
    for stamp, expected in [("2021-01-04T16:10", "FB"), ("2022-06-08T23:59:59", "FB"),
                            ("2022-06-09T00:00", "META"), ("2023-01-03T16:10", "META")]:
        snapshot = store.snapshot(signal_timestamp=et(stamp))
        row = next(r for r in snapshot.securities if r.security_id == "SEC123")
        assert row.ticker == expected
    past = store.snapshot(signal_timestamp=et("2021-01-04T16:10"))
    assert next(r for r in past.securities if r.security_id == "SEC123").valid_to is None
