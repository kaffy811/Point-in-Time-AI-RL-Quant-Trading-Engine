import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cli_outputs_config_hash_only() -> None:
    command = [sys.executable, "-m", "src.utils.cli", "--config",
               str(ROOT / "configs/phase1_baseline.yaml")]
    first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["status"] == "configuration_valid"
    assert payload["research_results"] == "[TODO: 待实验结果]"
    assert "INFO quant_engine" in first.stderr


def test_invalid_config_exits_nonzero(tmp_path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("seed: 42")
    result = subprocess.run([sys.executable, "-m", "src.utils.cli", "--config", str(path)],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0
    assert not result.stdout
