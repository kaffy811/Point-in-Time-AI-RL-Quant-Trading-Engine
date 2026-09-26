"""Run offline real-fixture Phase A identity audit."""
import argparse
from pathlib import Path

from .audit import ROOT, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/gate_a_data_02.json")
    args = parser.parse_args()
    manifest = run(args.config)
    print(f"Phase A observations: {manifest['observation_count']}; "
          f"status counts: {manifest['status_counts']}; Gate A BLOCKED")


if __name__ == "__main__":
    main()
