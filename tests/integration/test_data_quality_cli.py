import json
import subprocess
import sys

from conftest import FIXTURES, ROOT


def command(output, source):
    return [sys.executable, "-m", "src.data.cli", "--input", str(source),
            "--calendar", str(FIXTURES / "calendar.json"),
            "--config", str(ROOT / "configs/phase1_baseline.yaml"),
            "--dataset-version", "synthetic-p1-02-v1", "--as-of", "2024-08-02T16:10:00-04:00",
            "--ingested-at", "2026-01-01T04:00:00+00:00", "--output", str(output)]


def test_report_cli_end_to_end(tmp_path):
    result = subprocess.run(command(tmp_path, FIXTURES / "canonical.json"), cwd=ROOT,
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["status"] == "PASS"
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert len(manifest["datasets"]) == 4
    assert all("content_hash" in row for row in manifest["datasets"])


def test_failed_validation_still_writes_evidence(payload, tmp_path):
    payload["market"].append(payload["market"][0])
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(payload))
    result = subprocess.run(command(tmp_path / "report", source), cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads((tmp_path / "report/data_quality_report.json").read_text())
    assert report["status"] == "FAIL" and report["duplicate_counts"] == 1
