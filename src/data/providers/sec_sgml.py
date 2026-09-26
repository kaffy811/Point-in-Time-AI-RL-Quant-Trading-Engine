"""Bounded raw-header retrieval for four explicitly authorized pending accessions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

CASES = frozenset({
    ("0001505611", "0001019432-11-000009"),
    ("0001505611", "0001013762-11-002352"),
    ("0001556266", "0001213900-15-004248"),
    ("0001556266", "0001213900-15-004052"),
})
ROOT = Path(__file__).resolve().parents[3]


def source_url(cik: str, accession: str) -> str:
    if (cik, accession) not in CASES:
        raise ValueError("CIK/accession outside bounded SGML authorization")
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{accession}.txt")


class SameURLRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Any:
        if newurl != req.full_url:
            raise ValueError("No alternate source/CIK redirect is authorized")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_header(response: Any, cap: int) -> tuple[bytes, int]:
    prefix = b""
    while len(prefix) < cap:
        chunk = response.read(min(4096, cap - len(prefix)))
        if not chunk:
            break
        prefix += chunk
        match = re.search(rb"</(?:SEC|IMS)-HEADER>", prefix)
        if match:
            return prefix[:match.end()], len(prefix)
    raise ValueError("Complete raw SEC header unavailable within byte cap")


def retrieve(config_path: Path, user_agent: str, root: Path = ROOT) -> dict[str, Any]:
    if not re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", user_agent):
        raise ValueError("A genuine contact User-Agent is required locally")
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if ({(r["cik"], r["accessionNumber"]) for r in config["cases"]} != CASES
            or len(config["cases"]) != 4
            or config["sec_fixture_directory"] != "data/raw/sec/gate_a/data_02"
            or config["max_attempts_per_accession"] != 3
            or config["backoff_seconds"] != [1, 2]
            or config["max_prefix_bytes"] != 65536):
        raise ValueError("Config must preserve approved finite case set and retrieval caps")
    directory = root / config["sec_fixture_directory"]
    directory.mkdir(parents=True, exist_ok=True)
    prior = json.loads((directory / "sec_fixture_manifest.json").read_text())
    if {(r["cik"], r["accessionNumber"]) for r in prior["selected_accessions"]} != CASES:
        raise ValueError("SGML cases must equal the existing pending accession roster")
    results = []
    for case in config["cases"]:
        cik, accession = case["cik"], case["accessionNumber"]
        url = source_url(cik, accession)
        target = directory / (accession + ".header.sgml")
        receipt_path = directory / (accession + ".header.receipt.json")
        record: dict[str, Any] = {**case, "url": url, "attempts": []}
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            content = target.read_bytes()
            if (receipt["url"] != url or receipt["path"] != target.name
                    or receipt["sha256"] != hashlib.sha256(content).hexdigest()):
                raise ValueError("Cached raw SEC header receipt mismatch")
            record.update(status="RETRIEVED", receipt=receipt)
            results.append(record)
            continue
        if target.exists():
            raise ValueError("Incomplete raw-header cache; preserve and investigate")
        record["status"] = "PENDING_SOURCE_UNAVAILABLE"
        for attempt in range(3):
            time.sleep(0.5 if attempt == 0 else config["backoff_seconds"][attempt - 1])
            request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity",
                                           "Range": "bytes=0-65535"})
            try:
                with build_opener(SameURLRedirect()).open(request, timeout=20) as response:
                    if response.url != url:
                        raise ValueError("Unexpected source redirect")
                    header, received = read_header(response, 65536)
                    http_status = response.status
                receipt = {"url": url, "path": target.name,
                           "sha256": hashlib.sha256(header).hexdigest(),
                           "retrieved_at": datetime.now(timezone.utc).isoformat(),
                           "bytes_received": received, "header_bytes_saved": len(header),
                           "extraction": "EXACT_SUBMISSION_PREFIX_THROUGH_CLOSING_HEADER",
                           "http_status": http_status}
                with target.open("xb") as handle:
                    handle.write(header)
                with receipt_path.open("x") as handle:
                    json.dump(receipt, handle, indent=2)
                record["attempts"].append({"attempt": attempt + 1, "status": http_status})
                record.update(status="RETRIEVED", receipt=receipt)
                break
            except HTTPError as exc:
                record["attempts"].append({"attempt": attempt + 1, "status": exc.code})
                if exc.code not in {500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError):
                record["attempts"].append({"attempt": attempt + 1, "status": "NETWORK_ERROR"})
            except ValueError as exc:
                record["attempts"].append({"attempt": attempt + 1, "status": str(exc)})
                break
        results.append(record)
        # Persist bounded progress without losing earlier successes on interruption.
        partial = {"config_sha256": hashlib.sha256(config_bytes).hexdigest(),
                   "cases": results, "acquisition_complete": len(results) == 4}
        (directory / "sgml_fixture_manifest.json").write_text(json.dumps(partial, indent=2) + "\n")
    manifest = {"config_sha256": hashlib.sha256(config_bytes).hexdigest(),
                "cases": results, "acquisition_complete": True}
    (directory / "sgml_fixture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/gate_a_data_02_sgml.json")
    args = parser.parse_args()
    result = retrieve(args.config, os.environ.get("SEC_USER_AGENT", ""))
    print(json.dumps([{k: row[k] for k in ("cik", "accessionNumber", "status", "attempts")}
                      for row in result["cases"]]))


if __name__ == "__main__":
    main()
