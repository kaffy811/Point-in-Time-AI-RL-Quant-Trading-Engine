"""Local real Phase A/SEC evidence; perturbations are negative tests only."""
import json
import shutil

import pytest

from src.data.identity.audit import ROOT, digest
from src.data.identity.phase_b import accepted_inputs, classify, run_b1, run_b2
from src.data.identity.sec_confirmation import verify_index


@pytest.fixture
def corpus(tmp_path):
    raw = ROOT / "data/raw/wrds/gate_a/data_02"
    sec = ROOT / "data/raw/sec/gate_a/data_02"
    source = ROOT / "artifacts/gate_a/identity_spine"
    if not (raw / "stksecurityinfohist_fixture.parquet").exists():
        pytest.skip("Local licensed WRDS fixtures required")
    if not (sec / "sec_fixture_manifest.json").exists():
        pytest.skip("Local real SEC accession fixtures required")
    for path in (raw, sec):
        dest = tmp_path / path.relative_to(ROOT)
        shutil.copytree(path, dest)
    dest = tmp_path / source.relative_to(ROOT)
    dest.mkdir(parents=True)
    for name in ("identity_manifest.json", "identity_samples.parquet"):
        shutil.copyfile(source / name, dest / name)
    shutil.copytree(ROOT / "src/data/identity", tmp_path / "src/data/identity")
    return tmp_path


def test_b1_accounts_for_every_unresolved_once(corpus):
    h, links, results, _ = accepted_inputs(corpus)
    before = [r.row() for r in results]
    report = run_b1(corpus)
    assert report["counts"] == {
        "NO_CRSP_CUSIP_ASOF": 23, "NO_WRDS_LINK_FOR_CUSIP": 70,
        "ONLY_UNVALIDATED_WRDS_LINK": 159, "FIRST_EVIDENCE_AFTER_ASOF": 12,
        "FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC": 2, "CUSIP_MATCH_CLASS_MISMATCH": 0,
        "MULTIPLE_SECURITY_HISTORY_ROWS": 0, "FIRST_EVIDENCE_DATE_MISSING": 0, "OTHER": 0,
    }
    assert sum(report["counts"].values()) == 266
    for r in results:
        if r.resolution_status == "UNRESOLVED":
            assert classify(r, h, links)[0] in report["counts"]
        else:
            with pytest.raises(ValueError, match="only classifies"):
                classify(r, h, links)
    assert before == [r.row() for r in accepted_inputs(corpus)[2]]


def test_b2_actual_conflicts_fail_closed(corpus):
    report = run_b2(corpus)
    assert report["final_sec_confirmed_observations"] == 0
    assert report["unique_sec_confirmed_issuers"] == 0
    assert report["remaining_ambiguous_observations"] == 9
    assert report["phase_b_status_counts"] == {
        "RESOLVED_PENDING_SEC_CONFIRMATION": 8, "AMBIGUOUS": 9, "UNRESOLVED": 266}
    reasons = {r["confirmation_reason"] for r in report["selected_accessions"]}
    assert "ARCHIVE_FILER_CIK_MISMATCH_OR_AMBIGUOUS" in reasons
    assert "ACCEPTANCE_TIME_SOURCE_CONFLICT_OWNER_DECISION_REQUIRED" in reasons
    assert report["original_five_issuer_requirement_satisfied"] is False


def test_unverified_receipt_path_rejected(corpus):
    path = corpus / "data/raw/sec/gate_a/data_02/sec_fixture_manifest.json"
    manifest = json.loads(path.read_text())
    item = next(r for r in manifest["selected_accessions"] if r["archive_status"] == "RETRIEVED")
    original = path.parent / item["archive_receipt"]["path"]
    outside = path.parent.parent / "unverified.html"
    outside.write_bytes(original.read_bytes() + b"<!-- altered test input -->")
    item["archive_receipt"]["path"] = "../unverified.html"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="bound to verified"):
        run_b2(corpus)


def test_raw_source_tampering_rejected(corpus):
    directory = corpus / "data/raw/sec/gate_a/data_02"
    manifest = json.loads((directory / "sec_fixture_manifest.json").read_text())
    receipt = manifest["raw_sources"][0]
    path = directory / receipt["path"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash/path mismatch"):
        run_b2(corpus)


def test_archive_api_timestamp_not_relabelled(corpus):
    directory = corpus / "data/raw/sec/gate_a/data_02"
    manifest = json.loads((directory / "sec_fixture_manifest.json").read_text())
    item = next(r for r in manifest["selected_accessions"]
                if r["archive_status"] == "RETRIEVED" and r["form"] == "10-Q")
    content = (directory / item["archive_receipt"]["path"]).read_bytes()
    before = digest(content)
    with pytest.raises(ValueError, match="ACCEPTANCE_TIME_SOURCE_CONFLICT"):
        verify_index(content, item)
    assert digest(content) == before


def test_audits_repeat_without_changing_phase_a(corpus):
    folder = corpus / "artifacts/gate_a/identity_spine"
    phase_a = {name: (folder / name).read_bytes()
               for name in ("identity_manifest.json", "identity_samples.parquet")}
    first1, first2 = run_b1(corpus), run_b2(corpus)
    audit = {p.name: p.read_bytes() for p in folder.iterdir()}
    assert first1 == run_b1(corpus)
    assert first2 == run_b2(corpus)
    assert audit == {p.name: p.read_bytes() for p in folder.iterdir()}
    assert phase_a == {name: (folder / name).read_bytes() for name in phase_a}
