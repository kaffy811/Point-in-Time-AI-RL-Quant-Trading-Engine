"""Real licensed fixtures are local-only. Mutations below are negative tests, not evidence.

No fabricated issuer/CIK is used to fill missing real acceptance coverage. Tests requiring
raw fixtures skip in environments without the Git-ignored licensed inputs.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

import pytest

from src.data.identity.audit import ROOT, invariance, load_fixtures, observations
from src.data.identity.phase_a import identifier, resolve, source_date


@pytest.fixture(scope="module")
def real():
    path = ROOT / "data/raw/wrds/gate_a/data_02/wrds_fixture_manifest.json"
    if not path.exists():
        pytest.skip("Real licensed fixture manifest is not available")
    manifest = json.loads(path.read_text())
    if not all((ROOT / item["path"]).exists() for item in manifest["sources"].values()):
        pytest.skip("Real licensed fixture Parquet is not available")
    return load_fixtures(path)


def at(day):
    return datetime.combine(day, datetime.min.time().replace(hour=16, minute=10),
                            ZoneInfo("America/New_York"))


def real_unique_case(real):
    h, links, _, _ = real
    config = json.loads((ROOT / "configs/gate_a_data_02.json").read_text())
    for permno, stamp in observations(config, h, links):
        result = resolve(permno, stamp, h, links)
        if result.preliminary_cik:
            return permno, stamp, result
    pytest.fail("Real fixture corpus has no preliminary unique candidate")


def test_dates_and_identifier_validation():
    assert source_date(None) is None
    assert source_date("2015-06-30") == date(2015, 6, 30)
    with pytest.raises(ValueError):
        source_date("2015/06/30")
    with pytest.raises(ValueError):
        identifier("123", 8)


def test_empty_evidence_unresolved_and_timezone_required():
    assert resolve(1, at(date(2015, 6, 30)), (), ()).resolution_status == "UNRESOLVED"
    with pytest.raises(ValueError, match="timezone"):
        resolve(1, datetime(2015, 6, 30), (), ())


def test_real_hash_row_count_and_permno_coverage(real):
    h, links, manifest, evidence = real
    assert len(h) == manifest["sources"]["security_history"]["rows"]
    assert len(links) == manifest["sources"]["cik_links"]["rows"]
    assert {r.permno for r in h} == set(manifest["fixture_permnos"])
    assert {r["source_table"] for r in evidence} == {
        "crsp.stksecurityinfohist", "wrdssec_common.wciklink_cusip"}


def test_historical_cusip_and_stable_permno_through_real_changes(real):
    h, links, _, _ = real
    ticker_changes = cusip_changes = 0
    for permno in {r.permno for r in h}:
        records = sorted((r for r in h if r.permno == permno), key=lambda r: r.start)
        for row in records:
            for day in (row.start, row.end):
                result = resolve(permno, at(day), h, links)
                assert result.security_id == permno
                assert result.historical_cusip == row.cusip
                assert result.historical_cusip9 == row.cusip9
                assert result.historical_ticker == row.ticker
        for before, after in zip(records, records[1:]):
            ticker_changes += before.ticker != after.ticker
            cusip_changes += before.cusip9 != after.cusip9
    assert ticker_changes > 0 and cusip_changes > 0


def test_no_current_identifier_backfill(real):
    h, links, _, _ = real
    for permno in {r.permno for r in h}:
        first = min(r.start for r in h if r.permno == permno)
        result = resolve(permno, at(first - timedelta(days=1)), h, links)
        assert result.resolution_reason == "NO_HISTORICAL_SECURITY_RECORD"
        assert result.historical_cusip is None and result.preliminary_cik is None


def test_validated_zero_one_never_trusted(real):
    h, links, _, _ = real
    permno, stamp, _ = real_unique_case(real)
    # Deliberate negative perturbation of real rows, not a replacement fixture.
    downgraded = tuple(replace(r, validated=1) for r in links)
    assert resolve(permno, stamp, h, downgraded).resolution_status == "UNRESOLVED"
    weak = tuple(r for r in links if r.validated in (0, 1))
    assert weak
    assert resolve(permno, stamp, h, weak).preliminary_cik is None


def test_real_multi_cik_ambiguity_and_no_score_winner(real):
    h, links, _, _ = real
    config = json.loads((ROOT / "configs/gate_a_data_02.json").read_text())
    cases = [(p, t) for p, t in observations(config, h, links)
             if resolve(p, t, h, links).resolution_reason == "MULTIPLE_PLAUSIBLE_CIKS"]
    assert cases
    for p, t in cases:
        before = resolve(p, t, h, links)
        scores_changed = tuple(replace(r, tmatch=float(index)) for index, r in enumerate(links))
        assert before == resolve(p, t, h, scores_changed[::-1])
        assert before.preliminary_cik is None and len(before.candidate_ciks) > 1


def test_same_day_unresolved_even_with_precise_asof(real):
    h, links, _, _ = real
    permno, _, unique = real_unique_case(real)
    first = date.fromisoformat(unique.cik_evidence_first_date)
    result = resolve(permno, at(first), h, links)
    assert result.resolution_reason == "SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED"
    assert result.preliminary_cik is None
    tomorrow = resolve(permno, at(first + timedelta(days=1)), h, links)
    assert tomorrow.preliminary_cik == unique.preliminary_cik


def test_future_and_null_first_dates_never_auto_resolve(real):
    h, links, _, _ = real
    p, t, _ = real_unique_case(real)
    for first in (None, t.date() + timedelta(days=1)):
        changed = tuple(replace(r, first=first) for r in links)
        assert resolve(p, t, h, changed).resolution_status == "UNRESOLVED"


def test_last_date_is_not_expiration(real):
    h, links, _, _ = real
    p, t, before = real_unique_case(real)
    changed = tuple(replace(r, last=t.date() - timedelta(days=365)) for r in links)
    assert before == resolve(p, t, h, changed)


def test_real_future_invariance_full_output(real):
    h, links, _, _ = real
    config = json.loads((ROOT / "configs/gate_a_data_02.json").read_text())
    for p, t in observations(config, h, links):
        assert all(invariance(p, t, h, links).values())


def test_fallback_mechanism_with_explicit_real_row_perturbation(real):
    # There are NO validated=2 rows in the actual fixture corpus. This unit mutation
    # verifies code only and must not be counted as real 8-digit provider evidence.
    h, links, _, _ = real
    p, t, before = real_unique_case(real)
    changed = tuple(replace(r, validated=2) if r.validated == 3 else r for r in links)
    fallback = resolve(p, t, h, changed)
    assert fallback.preliminary_cik == before.preliminary_cik
    assert fallback.match_tier == "EXACT_CUSIP8"
    assert resolve(p, t, h, links + changed).match_tier == "EXACT_CUSIP9"
    future9 = tuple(replace(r, first=t.date() + timedelta(days=1))
                    for r in links if r.validated == 3)
    assert fallback == resolve(p, t, h, changed + future9)


def test_conflicting_history_is_not_silently_selected(real):
    h, links, _, _ = real
    p, t, _ = real_unique_case(real)
    active = next(r for r in h if r.permno == p and r.start <= t.date() <= r.end)
    other = next(r for r in h if r.cusip9 != active.cusip9 and r.cusip9 is not None)
    conflicting = replace(active, cusip=other.cusip, cusip9=other.cusip9)
    result = resolve(p, t, h + (conflicting,), links)
    assert result.resolution_reason == "CONFLICTING_HISTORICAL_SECURITY_RECORDS"
    assert result.preliminary_cik is None


def test_architecture_has_no_live_provider_imports():
    import ast
    for path in (ROOT / "src/data/identity").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                     [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            assert not any("wrds" in n or n.startswith(("requests", "httpx")) for n in names)


def test_same_instant_timezone_conversion(real):
    from datetime import timezone
    h, links, _, _ = real
    p, t, original = real_unique_case(real)
    assert original == resolve(p, t.astimezone(timezone.utc), h, links)
