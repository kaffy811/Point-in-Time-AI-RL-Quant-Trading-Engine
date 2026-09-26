"""Actual local fixtures only; no substitute provider evidence in CI."""
import json
import shutil

import pytest

from src.data.identity.audit import ROOT, load_fixtures, run


@pytest.fixture
def local_copy(tmp_path):
    source = ROOT / "data/raw/wrds/gate_a/data_02"
    files = [source / name for name in ("wrds_fixture_manifest.json",
             "stksecurityinfohist_fixture.parquet", "wciklink_cusip_fixture.parquet")]
    if not all(p.exists() for p in files):
        pytest.skip("Local real WRDS fixtures required")
    dest = tmp_path / "data/raw/wrds/gate_a/data_02"
    dest.mkdir(parents=True)
    for p in files:
        shutil.copyfile(p, dest / p.name)
    return tmp_path, dest


def test_hash_tampering_fails_before_resolution(local_copy):
    root, dest = local_copy
    path = dest / "stksecurityinfohist_fixture.parquet"
    path.write_bytes(path.read_bytes() + b"tamper-test")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_fixtures(dest / "wrds_fixture_manifest.json", root)


def test_report_reproducibility_and_no_final_sec_status(local_copy):
    root, _ = local_copy
    config = ROOT / "configs/gate_a_data_02.json"
    first = run(config, root)
    output = root / "artifacts/gate_a/identity_spine"
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    second = run(config, root)
    assert first == second
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    assert first["status"] == "PRELIMINARY_COMPLETED"
    assert first["final_sec_identity_confirmed"] is False
    assert "RESOLVED" not in first["status_counts"]
    assert first["Gate A"] == "BLOCKED"
    assert first["ciks_requiring_sec_confirmation"]
    assert all(x["passed"] == x["total"] for x in first["future_invariance"].values())
    assert json.loads((output / "identity_manifest.json").read_text()) == second
