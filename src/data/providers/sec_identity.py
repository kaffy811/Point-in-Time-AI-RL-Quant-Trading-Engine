"""Bounded SEC identity metadata ingestion; only the two owner-authorized CIKs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

AUTHORIZED_CIKS = frozenset({"0001505611", "0001556266"})
FIELDS = ("accessionNumber", "form", "filingDate", "acceptanceDateTime", "reportDate",
          "primaryDocument")


def authorized_url(url: str) -> bool:
    for cik in AUTHORIZED_CIKS:
        if re.fullmatch(r"https://data\.sec\.gov/submissions/CIK" + cik +
                        r"(?:-submissions-\d{3})?\.json", url):
            return True
        if re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/data/" + str(int(cik)) +
                        r"/\d{18}/\d{10}-\d{2}-\d{6}-index\.html?", url):
            return True
    return False


class MetadataRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Any:
        if not authorized_url(newurl):
            raise ValueError("SEC redirect outside CIK/metadata allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SECMetadataClient:
    def __init__(self, directory: Path, user_agent: str, max_requests: int = 12):
        if not re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", user_agent):
            raise ValueError("Use an identified SEC User-Agent with an actual contact")
        if not 1 <= max_requests <= 12:
            raise ValueError("Identity extraction is bounded to at most 12 requests")
        self.directory = directory
        self.user_agent = user_agent
        self.max_requests = max_requests
        self.requests = 0
        directory.mkdir(parents=True, exist_ok=True)

    def fetch(self, url: str) -> tuple[bytes, dict[str, Any]]:
        if not authorized_url(url):
            raise ValueError("SEC URL/CIK outside Phase B2 authorization")
        key = hashlib.sha256(url.encode()).hexdigest()[:20]
        suffix = ".json" if url.endswith(".json") else ".html"
        target = self.directory / (key + suffix)
        receipt = self.directory / (key + ".receipt.json")
        if receipt.exists():
            meta = json.loads(receipt.read_text())
            body = target.read_bytes()
            if meta["url"] != url or hashlib.sha256(body).hexdigest() != meta["sha256"]:
                raise ValueError("SEC cached evidence hash mismatch")
            return body, meta
        if target.exists():
            raise ValueError("Incomplete SEC cache; preserve evidence and investigate")
        if self.requests >= self.max_requests:
            raise ValueError("Bounded SEC request budget exhausted")
        self.requests += 1
        time.sleep(0.5)
        request = Request(url, headers={"User-Agent": self.user_agent,
                                       "Accept-Encoding": "identity"})
        try:
            with build_opener(MetadataRedirect()).open(request, timeout=30) as response:
                if not authorized_url(response.url):
                    raise ValueError("Unexpected SEC redirect outside authorization")
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ValueError("SEC metadata response exceeded bounded size")
        except HTTPError as exc:
            failure = {"url": url, "http_status": exc.code,
                       "retrieved_at": datetime.now(timezone.utc).isoformat(),
                       "status": "ACCESS_FAILED_NO_IDENTITY_EVIDENCE"}
            (self.directory / (key + ".failure.json")).write_text(json.dumps(failure, indent=2))
            raise RuntimeError(f"SEC metadata HTTP {exc.code}") from None
        except (URLError, TimeoutError):
            failure = {"url": url, "status": "NETWORK_ERROR_NO_IDENTITY_EVIDENCE",
                       "retrieved_at": datetime.now(timezone.utc).isoformat()}
            (self.directory / (key + ".failure.json")).write_text(json.dumps(failure, indent=2))
            raise RuntimeError("SEC metadata network error") from None
        meta = {"url": url, "path": target.name, "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "bytes": len(body)}
        with target.open("xb") as handle:
            handle.write(body)
        with receipt.open("x") as handle:
            json.dump(meta, handle, indent=2)
        return body, meta

    def json(self, url: str) -> tuple[dict[str, Any], dict[str, Any]]:
        body, meta = self.fetch(url)
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("Expected SEC metadata object")
        return result, meta


def rows_from_columns(payload: dict[str, Any], cik: str) -> list[dict[str, Any]]:
    if cik not in AUTHORIZED_CIKS:
        raise ValueError("CIK not authorized")
    if not all(key in payload for key in FIELDS):
        raise ValueError("SEC metadata fields missing")
    lengths = {len(payload[key]) for key in FIELDS}
    if len(lengths) != 1:
        raise ValueError("SEC metadata arrays have unequal lengths")
    return [{"cik": cik, **{key: payload[key][i] for key in FIELDS}}
            for i in range(len(payload["accessionNumber"]))]


def extract_metadata(client: SECMetadataClient, targets: dict[str, str]) -> dict[str, Any]:
    if set(targets) != AUTHORIZED_CIKS:
        raise ValueError("Only the exact authorized pair may be extracted")
    evidence = []
    selected = []
    failures = []
    for cik, first_date in sorted(targets.items()):
        obj, receipt = client.json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        if str(obj["cik"]).zfill(10) != cik:
            raise ValueError("SEC submissions CIK mismatch")
        evidence.append(receipt)
        rows = rows_from_columns(obj["filings"]["recent"], cik)
        # This pair's bounded root responses contain the target historical dates.
        # No automatic historical-shard expansion or issuer expansion is allowed.
        same_day = [r for r in rows if r["filingDate"] == first_date]
        if not same_day:
            failures.append({"cik": cik, "status": "TARGET_DATE_MISSING_NO_AUTO_EXPANSION"})
        if len(same_day) > 3:
            raise ValueError("Same-day accession cap exceeded; narrow explicitly")
        issuer_forms = {"10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A"}
        prior = sorted([r for r in rows if r["filingDate"] < first_date
                        and r["form"] in issuer_forms],
                       key=lambda r: (r["filingDate"], r["acceptanceDateTime"], r["accessionNumber"]))
        chosen = [(r, "SAME_DAY_FIRST_EVIDENCE") for r in same_day]
        if prior:
            chosen.append((prior[-1], "PRIOR_ISSUER_FILING"))
        for row, purpose in chosen:
            accession = row["accessionNumber"]
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                raise ValueError("Malformed SEC accession")
            url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                   f"{accession.replace('-', '')}/{accession}-index.htm")
            item = {**row, "selection_purpose": purpose, "index_url": url,
                    "submissions_source_sha256": receipt["sha256"]}
            try:
                _, archive = client.fetch(url)
                evidence.append(archive)
                item["archive_receipt"] = archive
                item["archive_status"] = "RETRIEVED"
            except RuntimeError as exc:
                item["archive_status"] = str(exc)
                failures.append({"cik": cik, "accessionNumber": accession, "status": str(exc)})
            selected.append(item)
    output = {"authorized_ciks": sorted(AUTHORIZED_CIKS), "targets": targets,
              "selection_policy": "up to 3 same-date filings plus latest prior issuer filing per CIK",
              "selected_accessions": selected, "raw_sources": evidence, "failures": failures,
              "network_requests_this_run": client.requests,
              "identity_confirmed": False}
    (client.directory / "sec_fixture_manifest.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


def main() -> None:
    import argparse
    import os

    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=root / "configs/gate_a_data_02_phase_b.json")
    parser.add_argument("--max-requests", type=int, default=None)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if (set(config["authorized_ciks"]) != AUTHORIZED_CIKS
            or config["sec_fixture_directory"] != "data/raw/sec/gate_a/data_02"):
        raise ValueError("Provider configuration exceeds Phase B2 scope")
    user_agent = os.environ.get("SEC_USER_AGENT", "")
    limit = config["max_requests_per_invocation"] if args.max_requests is None else args.max_requests
    client = SECMetadataClient(root / config["sec_fixture_directory"], user_agent, limit)
    result = extract_metadata(client, config["first_evidence_dates"])
    print(json.dumps({"accessions": len(result["selected_accessions"]),
                      "failures": result["failures"], "requests": client.requests}))


if __name__ == "__main__":
    main()
