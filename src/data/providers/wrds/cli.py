"""Local user-operated WRDS ingestion CLI."""
import argparse
import json
from pathlib import Path

from .connection import Connector, interactive_factory
from .extract import extract
from .query import QuerySpec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health")
    for name in ("plan", "extract"):
        sub = commands.add_parser(name)
        sub.add_argument("--spec", type=Path, required=True)
        if name == "extract":
            sub.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        if args.command == "health":
            if not Connector(interactive_factory()).health():
                raise ValueError("Health check failed")
            print(json.dumps({"status": "CONNECTED", "entitlements_verified": False}))
            return
        payload = json.loads(args.spec.read_text())
        for key in ("columns", "identities"):
            payload[key] = tuple(payload[key])
        spec = QuerySpec(**payload)
        sql, params = spec.compile()
        if args.command == "plan":
            print(json.dumps({"sql": sql, "parameters": params}, indent=2))
            return
        path = extract(Connector(interactive_factory()), spec, args.version)
        print(json.dumps({"manifest": str(path), "status": "EXTRACTED"}))
    except Exception:
        # No exception interpolation: drivers/configuration can contain secrets.
        parser.exit(1, "WRDS operation failed. Check the spec, version, local authentication, "
                    "entitlement and connectivity. No raw exception was logged.\n")


if __name__ == "__main__":
    main()
