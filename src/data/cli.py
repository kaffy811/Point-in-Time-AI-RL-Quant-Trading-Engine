"""Validate supplied canonical JSON and produce reproducible data-only artifacts."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from src.data.providers.sec_companyfacts import unique_json
from src.data.quality import generate_report, write_report
from src.data.schemas import Calendar
from src.utils.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--ingested-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/p1_02"))
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    calendar = Calendar.model_validate(json.loads(args.calendar.read_text(encoding="utf-8"),
                                                  object_pairs_hook=unique_json))
    report, manifest = generate_report(
        payload, calendar, load_config(args.config), as_of=args.as_of,
        dataset_version=args.dataset_version, ingested_at=args.ingested_at,
    )
    write_report(report, manifest, args.output)
    print(json.dumps({"status": report["status"], "output": str(args.output)}))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
