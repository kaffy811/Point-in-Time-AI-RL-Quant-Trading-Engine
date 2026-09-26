"""Real-fixture loading and deterministic, offline Phase A audit generation."""
from collections import Counter
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .phase_a import History, Link, resolve

ROOT = Path(__file__).resolve().parents[3]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n").encode()


def load_fixtures(manifest_path: Path, root: Path = ROOT) -> tuple[
    tuple[History, ...], tuple[Link, ...], dict[str, Any], list[dict[str, Any]]
]:
    manifest = json.loads(manifest_path.read_text())
    if manifest["provider"] != "WRDS/CRSP":
        raise ValueError("Real WRDS fixture provenance required")
    tables = {}
    evidence = []
    expected = {"security_history": "crsp.stksecurityinfohist",
                "cik_links": "wrdssec_common.wciklink_cusip"}
    for key, table_name in expected.items():
        entry = manifest["sources"][key]
        if entry["source_table"] != table_name:
            raise ValueError("Unexpected provider source table")
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to((root / "data/raw/wrds/gate_a/data_02").resolve()):
            raise ValueError("Fixture path is outside the authorized raw directory")
        content = path.read_bytes()
        if digest(content) != entry["sha256"]:
            raise ValueError("Raw fixture content hash mismatch")
        table = pq.read_table(pa.BufferReader(content))
        if table.num_rows != entry["rows"] or table.num_rows == 0:
            raise ValueError("Raw fixture row count mismatch or empty real evidence")
        tables[key] = table.to_pylist()
        evidence.append({"source_table": table_name, "rows": table.num_rows,
                         "sha256": digest(content), "schema": str(table.schema)})
    history = tuple(History.from_row(r) for r in tables["security_history"])
    links = tuple(Link.from_row(r) for r in tables["cik_links"])
    if {r.permno for r in history} != set(manifest["fixture_permnos"]):
        raise ValueError("PERMNO coverage differs from acquisition manifest")
    return history, links, manifest, evidence


def observations(config: dict[str, Any], history: tuple[History, ...],
                 links: tuple[Link, ...]) -> tuple[tuple[int, datetime], ...]:
    if config["observation_policy"] != "history_boundaries_and_link_first_dates_v1":
        raise ValueError("Unknown observation policy")
    if config["timezone"] != "America/New_York" or config["signal_time"] != "16:10:00":
        raise ValueError("Use the frozen exchange-local signal convention")
    result = set()
    for permno in config["permnos"]:
        rows = [r for r in history if r.permno == permno]
        if not rows:
            raise ValueError("Configured PERMNO is missing from real fixtures")
        days = {date.fromisoformat(d) for d in config["anchor_dates"]}
        for row in rows:
            days.update((row.start - timedelta(days=1), row.start, row.end,
                         row.end + timedelta(days=1)))
        cusips = {r.cusip for r in rows if r.cusip is not None}
        full = {r.cusip9 for r in rows if r.cusip9 is not None}
        for link in links:
            if link.first and (link.cusip in cusips or link.cusip_full in full):
                days.update((link.first - timedelta(days=1), link.first,
                             link.first + timedelta(days=1)))
        for day in days:
            result.add((permno, datetime.combine(day, time.fromisoformat(config["signal_time"]),
                                                ZoneInfo(config["timezone"]))))
    return tuple(sorted(result))


def invariance(permno: int, stamp: datetime, history: tuple[History, ...],
               links: tuple[Link, ...]) -> dict[str, bool]:
    """Adversarial in-memory perturbations; never manufactured fixture evidence."""
    day = stamp.astimezone(ZoneInfo("America/New_York")).date()
    original = resolve(permno, stamp, history, links)
    past_history = tuple(r for r in history if r.start <= day)
    past_links = tuple(r for r in links if r.first is not None and r.first <= day)
    future_h = tuple(r for r in history if r.start > day)
    future_l = tuple(r for r in links if r.first is not None and r.first > day)
    # Reuse real identifier payloads while preserving future temporal position.
    h_payload = history[0] if history else None
    l_payload = links[0] if links else None
    mutated_h = tuple(replace(r, cusip=h_payload.cusip, cusip9=h_payload.cusip9,
                              ticker=h_payload.ticker, trading_symbol=h_payload.trading_symbol)
                      if r.start > day and h_payload else r for r in history)
    mutated_l = tuple(replace(r, cik=l_payload.cik, cusip=l_payload.cusip,
                              cusip_full=l_payload.cusip_full, validated=3)
                      if r.first is not None and r.first > day and l_payload else r for r in links)
    audit_mutation = tuple(replace(r, last=None, tmatch=None) for r in links)
    checks = {
        "repeat": original == resolve(permno, stamp, history, links),
        "reverse_input_order": original == resolve(permno, stamp, history[::-1], links[::-1]),
        "remove_future_records": original == resolve(permno, stamp, past_history, past_links),
        "append_future_records": original == resolve(permno, stamp, history + future_h,
                                                       links + future_l),
        "mutate_future_payloads": original == resolve(permno, stamp, mutated_h, mutated_l),
        "remove_last_date_and_tmatch": original == resolve(permno, stamp, history, audit_mutation),
    }
    return checks


def write_parquet(path: Path, rows: list[dict[str, Any]]) -> str:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd")
    return digest(path.read_bytes())


def run(config_path: Path, root: Path = ROOT) -> dict[str, Any]:
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if config["phase"] != "A":
        raise ValueError("Only preliminary Phase A is implemented")
    raw_manifest_path = root / config["fixture_manifest"]
    history, links, raw_manifest, sources = load_fixtures(raw_manifest_path, root)
    if set(config["permnos"]) != set(raw_manifest["fixture_permnos"]):
        raise ValueError("Config must match the owner-supplied real fixture securities")
    requested = observations(config, history, links)
    resolutions = [resolve(p, t, history, links) for p, t in requested]
    checks = [invariance(p, t, history, links) for p, t in requested]
    if not all(all(c.values()) for c in checks):
        raise ValueError("Future invariance failed; no successful audit may be published")
    output = root / config["output"]
    if output.resolve() != (root / "artifacts/gate_a/identity_spine").resolve():
        raise ValueError("Use the authorized identity audit directory")
    output.mkdir(parents=True, exist_ok=True)
    # Raw WRDS-derived audit detail stays in ignored Parquet, never tracked Markdown.
    rows = [r.row() for r in resolutions]
    sample_hash = write_parquet(output / "identity_samples.parquet", rows)
    ambiguous_rows = [r.row() for r in resolutions if r.resolution_status == "AMBIGUOUS"]
    # Slice the common typed table so empty ambiguity still retains the result schema.
    table = pq.read_table(output / "identity_samples.parquet")
    ambiguous_table = table.filter(pa.array([r.resolution_status == "AMBIGUOUS"
                                             for r in resolutions]))
    pq.write_table(ambiguous_table, output / "ambiguous_links.parquet", compression="zstd")
    audit_rows = [{**asdict(link), "audit_only_not_pit": True} for link in links]
    audit_hash = write_parquet(output / "wrds_link_evidence.parquet", audit_rows)
    counts = dict(sorted(Counter(r.resolution_status for r in resolutions).items()))
    reasons = dict(sorted(Counter(r.resolution_reason for r in resolutions).items()))
    ciks = sorted({r.preliminary_cik for r in resolutions if r.preliminary_cik is not None})
    ambiguous_ciks = sorted({c for r in resolutions if r.resolution_status == "AMBIGUOUS"
                            for c in r.candidate_ciks})
    same_day_ciks = sorted({c for r in resolutions
                           if r.resolution_reason == "SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED"
                           for c in r.candidate_ciks})
    tested = {name: {"passed": sum(c[name] for c in checks), "total": len(checks)}
              for name in checks[0]}
    future_h_cases = sum(any(h.start > t.date() for h in history) for _, t in requested)
    future_l_cases = sum(any(link.first and link.first > t.date() for link in links)
                        for _, t in requested)
    manifest = {
        "ticket": "GATE-A-DATA-02", "phase": "A", "status": "PRELIMINARY_COMPLETED",
        "independent_review_report": "docs/reviews/gate_a_data_02_phase_a_review.md",
        "Gate A": "BLOCKED", "final_sec_identity_confirmed": False,
        "config_sha256": digest(config_bytes), "config": config,
        "implementation_sha256": {p.name: digest(p.read_bytes())
                                   for p in sorted(Path(__file__).parent.glob("*.py"))},
        "fixture_manifest_sha256": digest(raw_manifest_path.read_bytes()),
        "provider_retrieved_at": raw_manifest["retrieved_at_utc"], "sources": sources,
        "real_permno_count": len(config["permnos"]), "observation_count": len(resolutions),
        "status_counts": counts, "reason_counts": reasons,
        "ciks_requiring_sec_confirmation": ciks,
        "ambiguous_ciks_requiring_investigation": ambiguous_ciks,
        "same_day_ciks_requiring_acceptance_check": same_day_ciks,
        "validated_input_counts": dict(sorted(Counter(str(r.validated) for r in links).items())),
        "future_invariance": tested,
        "nonvacuous_future_history_observations": future_h_cases,
        "nonvacuous_future_link_observations": future_l_cases,
        "licensed_outputs": {"identity_samples.parquet": sample_hash,
                              "ambiguous_links.parquet": digest(
                                  (output / "ambiguous_links.parquet").read_bytes()),
                              "wrds_link_evidence.parquet": audit_hash},
        "sec_archive_validation": "NOT_RUN_PHASE_A",
        "ccm_crosscheck": "NOT_RUN_PHASE_A",
        "real_8_digit_fallback_coverage": any(r.validated == 2 for r in links),
        "limitations": ["No SEC accession confirmation or CCM cross-check performed.",
                        "No historical WRDS revision snapshots; retrospective corrections are unproven.",
                        "tmatch/cikdate2 retained only in ignored raw audit, not historical resolution.",
                        "Five multi-history securities are not a frozen cohort or proof of all fixture categories."],
    }
    status_lines = "\n".join(f"| {key} | {value} |" for key, value in counts.items())
    reason_lines = "\n".join(f"| {key} | {value} |" for key, value in reasons.items())
    (output / "preliminary_resolution_report.md").write_text(
        "# DATA-02 Phase A — preliminary real-fixture results\n\n"
        f"Real inputs: {len(history)} CRSP history rows, {len(links)} WRDS links, "
        f"{len(config['permnos'])} PERMNOs. Both source hashes and row counts verified.\n\n"
        f"{len(resolutions)} deterministic observations: each history start/end and adjacent "
        "outside day, matching link first-date ±1 day, plus configured anchor dates. "
        "All timestamps use 16:10 America/New_York; no trading-session claim is made.\n\n"
        "| Preliminary status | Observations |\n|---|---:|\n" + status_lines + "\n\n"
        "| Reason | Observations |\n|---|---:|\n" + reason_lines + "\n\n"
        "Unique preliminary CIKs requiring actual SEC accession confirmation: **" +
        ", ".join(ciks) + "**. No CIK is finally confirmed.\n\n"
        "Same-day-only candidates requiring SEC acceptance checks: " + ", ".join(same_day_ciks) +
        ". These remain UNRESOLVED in Phase A.\n\n"
        "Only historically eligible exact-9 validated=3 evidence is preferred; when absent, "
        "exact-8 validated=2 is considered. Equal-date evidence is provisional and cannot "
        "auto-resolve. Multiple CIKs in the selected tier are AMBIGUOUS; repeated evidence "
        "for the same CIK is not a competing identity and stays preserved in raw audit.\n\n"
        "tmatch and cikdate2 are retained in ignored `wrds_link_evidence.parquet` only. "
        "They are current-snapshot evidence, not historical decision inputs. No link expires "
        "at cikdate2. Dates exported as ISO strings are strictly parsed without changing raw bytes.\n\n" +
        ("Real validated=2 fallback evidence is available in this corpus. "
         if manifest["real_8_digit_fallback_coverage"] else
         "No validated=2 links occur in these real fixtures; real fallback coverage is NOT EXERCISED. ") +
        "Fixture category coverage, SEC and CCM checks remain incomplete. "
        "No fabricated evidence, bulk fetch, features, training or performance work occurred. "
        "Gate A remains BLOCKED.\n")
    (output / "ambiguity_report.md").write_text(
        "# DATA-02 Phase A — ambiguity audit\n\n"
        f"AMBIGUOUS observations: {len(ambiguous_rows)}. Candidate CIKs: " +
        ", ".join(ambiguous_ciks) + ".\n\n"
        "Details are in Git-ignored `ambiguous_links.parquet`. No tmatch or row-order "
        "tie-breaker was used. CIKs appearing here are investigation candidates, not "
        "confirmed filers. The last observed filing date is not an expiry date.\n\n"
        "Equal-day candidates remain plausible but unconfirmed; multiple such CIKs are "
        "AMBIGUOUS. A single equal-day-only candidate is UNRESOLVED pending SEC acceptance. "
        "No final SEC identity claim is made. Gate A remains BLOCKED.\n")
    check_lines = "\n".join(f"| {name} | {item['passed']} / {item['total']} |"
                            for name, item in tested.items())
    (output / "future_invariance_report.md").write_text(
        "# DATA-02 Phase A — future evidence invariance\n\n"
        "Compared the entire preliminary result record, including status/reason and historical "
        "identifiers, using in-memory perturbations of the real input corpus. Perturbed rows "
        "were never published as real evidence.\n\n"
        "| Check | Passed / total |\n|---|---:|\n" + check_lines + "\n\n"
        f"Observations with actual future history rows: {future_h_cases}; with actual future "
        f"link rows: {future_l_cases}. Future positions preserve start/first-evidence dates. "
        "Mutations reuse real identifier payloads; appends duplicate only future-positioned rows.\n\n"
        "tmatch and last filing date are excluded from historical results, so later snapshot "
        "changes cannot alter the past output. Raw audit hashes can change and are not historical "
        "features. Same-day links remain unconfirmed.\n\n"
        "Scope: later-effective/newly evidenced rows, order independence and audit-only fields. "
        "Not proof against retroactive vendor edits to already-historical CUSIPs/first dates or "
        "validated codes; those require archived revision provenance. No model leakage metric "
        "or SEC identity approval is inferred. Gate A remains BLOCKED.\n")
    (output / "identity_audit.md").write_text(
        "# DATA-02 identity audit\n\nPhase A preliminary audit executed on hash-verified real "
        "fixtures. See identity_manifest.json and the preliminary, ambiguity and invariance "
        "reports. The earlier missing-input status is superseded. SEC accession identity "
        "confirmation and CCM remain NOT RUN. No final identity approval. Gate A BLOCKED.\n")
    (output / "crosscheck_report.md").write_text(
        "# DATA-02 cross-check\n\nNOT_RUN_PHASE_A. No CCM or SEC accession confirmation "
        "was performed. CUSIP-path candidates cannot be replaced by CCM. "
        "Later confirmation results: [TODO: 待实验结果].\n")
    (output / "identity_manifest.json").write_bytes(encoded(manifest))
    return manifest
