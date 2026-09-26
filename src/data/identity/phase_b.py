"""Administrative Phase B audits; frozen Phase A decisions are never rewritten."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from .audit import ROOT, digest, encoded, load_fixtures
from .phase_a import History, Link, Resolution, resolve

REASONS = (
    "NO_CRSP_CUSIP_ASOF", "NO_WRDS_LINK_FOR_CUSIP", "ONLY_UNVALIDATED_WRDS_LINK",
    "FIRST_EVIDENCE_AFTER_ASOF", "FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC",
    "CUSIP_MATCH_CLASS_MISMATCH", "MULTIPLE_SECURITY_HISTORY_ROWS",
    "FIRST_EVIDENCE_DATE_MISSING", "OTHER",
)


def accepted_inputs(root: Path = ROOT) -> tuple[tuple[History, ...], tuple[Link, ...],
                                               tuple[Resolution, ...], dict[str, Any]]:
    directory = root / "artifacts/gate_a/identity_spine"
    manifest = json.loads((directory / "identity_manifest.json").read_text())
    for name, expected in manifest["implementation_sha256"].items():
        if digest((root / "src/data/identity" / name).read_bytes()) != expected:
            raise ValueError("Accepted Phase A implementation changed")
    raw_manifest = root / manifest["config"]["fixture_manifest"]
    if digest(raw_manifest.read_bytes()) != manifest["fixture_manifest_sha256"]:
        raise ValueError("Phase A fixture manifest changed")
    history, links, _, _ = load_fixtures(raw_manifest, root)
    data = (directory / "identity_samples.parquet").read_bytes()
    if digest(data) != manifest["licensed_outputs"]["identity_samples.parquet"]:
        raise ValueError("Accepted Phase A results changed")
    results = []
    for row in pq.read_table(pa.BufferReader(data)).to_pylist():
        row["candidate_ciks"] = tuple(row["candidate_ciks"])
        result = Resolution(**row)
        if result != resolve(result.security_id, datetime.fromisoformat(result.as_of_timestamp),
                             history, links):
            raise ValueError("Phase A reproduction mismatch")
        results.append(result)
    if dict(Counter(r.resolution_status for r in results)) != manifest["status_counts"]:
        raise ValueError("Accepted status counts differ")
    return history, links, tuple(results), manifest


def classify(result: Resolution, history: tuple[History, ...],
             links: tuple[Link, ...]) -> tuple[str, dict[str, Any]]:
    if result.resolution_status != "UNRESOLVED":
        raise ValueError("B1 only classifies Phase A UNRESOLVED observations")
    day = datetime.fromisoformat(result.as_of_timestamp).date()
    active = [h for h in history if h.permno == result.security_id and h.start <= day <= h.end]
    detail: dict[str, Any] = {
        "security_id": result.security_id, "as_of_date": result.as_of_date,
        "phase_a_reason": result.resolution_reason, "active_history_rows": len(active),
        "related_link_rows": 0, "matching_strong_rows": 0,
        "future_matching_strong_rows": 0, "null_first_matching_strong_rows": 0,
    }
    if not active:
        return "NO_CRSP_CUSIP_ASOF", detail
    projections = {(h.ticker, h.trading_symbol, h.cusip, h.cusip9) for h in active}
    if len(projections) > 1:
        return "MULTIPLE_SECURITY_HISTORY_ROWS", detail
    cusip, full = result.historical_cusip, result.historical_cusip9
    if cusip is None and full is None:
        return "NO_CRSP_CUSIP_ASOF", detail
    if cusip and full and full[:8] != cusip:
        return "CUSIP_MATCH_CLASS_MISMATCH", detail
    related = [r for r in links if (cusip is not None and r.cusip == cusip)
               or (full is not None and r.cusip_full == full)]
    detail["related_link_rows"] = len(related)
    if not related:
        return "NO_WRDS_LINK_FOR_CUSIP", detail
    strong = [r for r in related if r.validated in (2, 3)]
    if not strong:
        return "ONLY_UNVALIDATED_WRDS_LINK", detail
    matching = [r for r in strong if (r.validated == 3 and full is not None
                                     and r.cusip_full == full)
                or (r.validated == 2 and cusip is not None and r.cusip == cusip)]
    detail["matching_strong_rows"] = len(matching)
    detail["future_matching_strong_rows"] = sum(r.first is not None and r.first > day
                                                 for r in matching)
    detail["null_first_matching_strong_rows"] = sum(r.first is None for r in matching)
    if not matching:
        return "CUSIP_MATCH_CLASS_MISMATCH", detail
    if result.resolution_reason == "SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED":
        return "FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC", detail
    known_first = [r.first for r in matching if r.first is not None]
    if not known_first:
        return "FIRST_EVIDENCE_DATE_MISSING", detail
    if all(first > day for first in known_first):
        return "FIRST_EVIDENCE_AFTER_ASOF", detail
    return "OTHER", detail


def run_b1(root: Path = ROOT) -> dict[str, Any]:
    history, links, results, manifest = accepted_inputs(root)
    unresolved = [r for r in results if r.resolution_status == "UNRESOLVED"]
    rows = []
    for result in unresolved:
        reason, detail = classify(result, history, links)
        rows.append({**detail, "unresolved_root_cause": reason})
    counts = {reason: sum(r["unresolved_root_cause"] == reason for r in rows)
              for reason in REASONS}
    if sum(counts.values()) != manifest["status_counts"]["UNRESOLVED"]:
        raise ValueError("B1 must account for every unresolved observation exactly once")
    examples = {reason: sorted([r for r in rows if r["unresolved_root_cause"] == reason],
                               key=lambda r: (r["security_id"], r["as_of_date"]))[:2]
                for reason in REASONS}
    output = root / "artifacts/gate_a/identity_spine"
    payload = {
        "ticket": "GATE-A-DATA-02", "phase": "B1", "classification_scope": "RETROSPECTIVE_AUDIT_ONLY",
        "phase_a_manifest_sha256": digest((output / "identity_manifest.json").read_bytes()),
        "unresolved_observations": len(unresolved), "counts": counts,
        "representative_real_examples": examples, "mutually_exclusive": True,
        "phase_a_results_unchanged": True, "Gate A": "BLOCKED",
        "precedence": ["NO_ACTIVE_HISTORY_AS_NO_CRSP_CUSIP_ASOF",
                       "MULTIPLE_SECURITY_HISTORY_ROWS", "NO_CRSP_CUSIP_ASOF",
                       "INCONSISTENT_CRSP_PAIR_AS_CUSIP_MATCH_CLASS_MISMATCH",
                       "NO_WRDS_LINK_FOR_CUSIP", "ONLY_UNVALIDATED_WRDS_LINK",
                       "CUSIP_MATCH_CLASS_MISMATCH", "FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC",
                       "FIRST_EVIDENCE_DATE_MISSING", "FIRST_EVIDENCE_AFTER_ASOF", "OTHER"],
        "note": "Future/current snapshot evidence explains failure only; never changes a past result.",
    }
    pq.write_table(pa.Table.from_pylist(rows), output / "unresolved_root_causes.parquet")
    (output / "unresolved_reason_counts.json").write_bytes(encoded(payload))
    lines = ["# Phase B1 — unresolved root-cause audit", "",
             f"All **{len(unresolved)}** Phase A UNRESOLVED observations are assigned exactly one reason.",
             "Frozen Phase A bytes and implementation hashes verified; no resolver changes.", "",
             "| Reason | Count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in counts.items()]
    lines += ["", "Classification precedence: missing history → conflicting history → missing CUSIP →",
              "inconsistent CUSIP pair → no exact-related links → only unvalidated links →",
              "validated/match-class mismatch → same-day SEC requirement → missing first dates →",
              "all dated strong matches after as-of → OTHER. Null dates do not become valid evidence.",
              "NO_CRSP_CUSIP_ASOF includes both no active CRSP row and a row without identifiers.",
              "Multiple rows with a single identical projection are not conflicting identities.", "",
              "The report inspects the full downloaded snapshot to explain why the PIT resolver",
              "could not resolve. These reasons are administrative diagnostics, not historical",
              "features: e.g. adding a future link may change a diagnostic category but never the",
              "frozen historical identity result. A future or unvalidated link is not a resolution.", "",
              "## Representative real observations", "",
              "Examples are observation references and aggregate evidence counts; full licensed",
              "row details stay in ignored Parquet and raw fixtures.", "",
              "| Reason | PERMNO | As-of date | Active history rows | Related links | Strong exact links | Future strong links |",
              "|---|---:|---|---:|---:|---:|---:|"]
    for reason, records in examples.items():
        for row in records:
            lines.append(f"| {reason} | {row['security_id']} | {row['as_of_date']} | "
                         f"{row['active_history_rows']} | {row['related_link_rows']} | "
                         f"{row['matching_strong_rows']} | {row['future_matching_strong_rows']} |")
    lines += ["", "Zero-count categories have no real example; no examples were fabricated.",
              "Ambiguous observations are outside this 266-row audit and remain unchanged.",
              "Gate A remains BLOCKED.", ""]
    (output / "unresolved_reason_report.md").write_text("\n".join(lines))
    return payload


def run_b2(root: Path = ROOT) -> dict[str, Any]:
    from .sec_confirmation import accepted_instant, verify_index

    _, _, results, _ = accepted_inputs(root)
    directory = root / "data/raw/sec/gate_a/data_02"
    sec_manifest_path = directory / "sec_fixture_manifest.json"
    sec_manifest = json.loads(sec_manifest_path.read_text())
    allowed = {"0001505611", "0001556266"}
    if set(sec_manifest["authorized_ciks"]) != allowed:
        raise ValueError("Unauthorized SEC fixture CIK")
    sources = {item["sha256"]: item for item in sec_manifest["raw_sources"]}
    verified_bytes: dict[str, bytes] = {}
    for receipt in sources.values():
        path = (directory / receipt["path"]).resolve()
        if path.parent != directory.resolve():
            raise ValueError("SEC raw source hash/path mismatch")
        content = path.read_bytes()
        if digest(content) != receipt["sha256"]:
            raise ValueError("SEC raw source hash/path mismatch")
        verified_bytes[receipt["sha256"]] = content
    checked = []
    for item in sec_manifest["selected_accessions"]:
        if item["cik"] not in allowed:
            raise ValueError("Unauthorized CIK in selected SEC metadata")
        source = sources[item["submissions_source_sha256"]]
        if source["url"] != f"https://data.sec.gov/submissions/CIK{item['cik']}.json":
            raise ValueError("Unexpected submissions provenance URL")
        raw = json.loads(verified_bytes[source["sha256"]])
        if str(raw["cik"]).zfill(10) != item["cik"]:
            raise ValueError("SEC source CIK mismatch")
        recent = raw["filings"]["recent"]
        indices = [i for i, value in enumerate(recent["accessionNumber"])
                   if value == item["accessionNumber"]]
        fields = ("accessionNumber", "form", "filingDate", "acceptanceDateTime", "reportDate",
                  "primaryDocument")
        if len(indices) != 1 or any(recent[k][indices[0]] != item[k] for k in fields):
            raise ValueError("Selected metadata differs from raw SEC source")
        report = {k: item[k] for k in ("cik", *fields, "selection_purpose", "index_url")}
        report["archive_confirmed"] = False
        report["confirmation_reason"] = "ARCHIVE_UNAVAILABLE"
        report["api_acceptance_timestamp_parsed"] = accepted_instant(item["acceptanceDateTime"]).isoformat()
        if item["archive_status"] == "RETRIEVED":
            archive = item["archive_receipt"]
            if archive["sha256"] not in sources or archive != sources[archive["sha256"]]:
                raise ValueError("Archive receipt not bound to verified source")
            if archive["url"] != item["index_url"]:
                raise ValueError("Archive URL differs from selected accession")
            try:
                accepted = verify_index(verified_bytes[archive["sha256"]], item)
                report["archive_confirmed"] = True
                report["confirmation_reason"] = "ARCHIVE_FILER_AND_METADATA_CONSISTENT"
                report["confirmed_acceptance_timestamp"] = accepted.isoformat()
                report["acceptance_source"] = "SEC_ACCESSION_INDEX_EASTERN_PER_P1_02"
                report["api_archive_acceptance_instant_agrees"] = (
                    accepted == accepted_instant(item["acceptanceDateTime"]))
            except (ValueError, KeyError) as exc:
                report["confirmation_reason"] = str(exc)
        report["retrieval_status"] = item["archive_status"]
        checked.append(report)
    final_rows = []
    for result in results:
        row = result.row()
        row["phase_b_status"] = result.resolution_status
        row["sec_reason"] = "NOT_ELIGIBLE_FOR_AUTHORIZED_SEC_CONFIRMATION"
        row["confirmed_accession"] = None
        unique = result.preliminary_cik
        same_day = result.resolution_reason == "SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED"
        if same_day and len(result.candidate_ciks) == 1:
            unique = result.candidate_ciks[0]
        if unique in allowed:
            supporting = [r for r in checked if r["cik"] == unique and r["archive_confirmed"]
                          and accepted_instant(r["confirmed_acceptance_timestamp"])
                          <= accepted_instant(result.as_of_timestamp)]
            # Same-day admission must be supported by that first-evidence date's filing,
            # not a different older filing that cannot time the day's CUSIP evidence.
            if same_day:
                supporting = [r for r in supporting
                              if r["filingDate"] == result.cik_evidence_first_date]
            if supporting:
                supporting.sort(key=lambda r: (r["confirmed_acceptance_timestamp"], r["accessionNumber"]))
                row["phase_b_status"] = "SEC_CONFIRMED"
                row["sec_reason"] = "ARCHIVE_FILER_CIK_AND_ASOF_ACCEPTANCE_CONFIRMED"
                row["confirmed_accession"] = supporting[0]["accessionNumber"]
            else:
                row["sec_reason"] = "NO_ELIGIBLE_ARCHIVE_CONFIRMATION"
        final_rows.append(row)
    final = [r for r in final_rows if r["phase_b_status"] == "SEC_CONFIRMED"]
    count_issuers = len({r["preliminary_cik"] or r["candidate_ciks"][0] for r in final})
    count_ambiguous = sum(r["phase_b_status"] == "AMBIGUOUS" for r in final_rows)
    output = root / "artifacts/gate_a/identity_spine"
    summary = {
        "ticket": "GATE-A-DATA-02", "phase": "B2", "status": "COMPLETE" if all(
            r["archive_confirmed"] for r in checked) else "PARTIAL_ARCHIVE_CONFIRMATION_BLOCKED",
        "phase_a_results_unchanged": True, "authorized_ciks": sorted(allowed),
        "sec_fixture_manifest_sha256": digest(sec_manifest_path.read_bytes()),
        "selected_accessions": checked, "final_sec_confirmed_observations": len(final),
        "unique_sec_confirmed_issuers": count_issuers,
        "remaining_ambiguous_observations": count_ambiguous,
        "phase_b_status_counts": dict(Counter(r["phase_b_status"] for r in final_rows)),
        "original_five_issuer_requirement_satisfied": False,
        "five_issuer_requirement_reason": "Fewer than five authorized/validated issuers; category coverage also unproven",
        "DATA-02": "NOT_PASS", "Gate A": "BLOCKED",
    }
    pq.write_table(pa.Table.from_pylist(final_rows), output / "phase_b_identity_samples.parquet")
    (output / "sec_confirmation_manifest.json").write_bytes(encoded(summary))
    lines = ["# Phase B2 — SEC accession confirmation", "",
             "Only CIKs 0001505611 and 0001556266 were queried. Two bounded submissions",
             "responses supplied exact-date accessions and one latest prior issuer filing each.",
             "No filing bodies, facts, unrelated issuers, or additional WRDS data were downloaded.",
             "Raw HTTP responses and retrieval failures remain in the ignored SEC directory.", "",
             "| CIK | Accession | Form | Archive status | Confirmation |",
             "|---|---|---|---|---|"]
    lines += [f"| {r['cik']} | {r['accessionNumber']} | {r['form']} | "
              f"{r['retrieval_status']} | {r['confirmation_reason']} |" for r in checked]
    lines += ["", f"Final SEC-confirmed observations: **{len(final)}**.",
              f"Unique SEC-confirmed issuers: **{count_issuers}**.",
              f"Remaining ambiguous observations: **{count_ambiguous}**.",
              "Original five-issuer validation requirement: **NOT SATISFIED**.", "",
              "An entry in a CIK submissions list is insufficient to verify that CIK's filer",
              "role in the archive (ownership filings may list a subject company). Archive",
              "filer identity, accession, form, filing/report dates and primary document must match.",
              "API/archive acceptance discrepancies block final confirmation. P1-02's Eastern",
              "convention applies to SGML headers; it does not authorize overriding an",
              "explicit API timezone with an unzoned HTML index. Source precedence remains",
              "an open Research Owner decision. No timestamp is silently relabeled or",
              "inferred from a filing date.",
              "Same-day evidence additionally requires the first-evidence date's accession",
              "accepted no later than the observation timestamp. Without that evidence it",
              "remains unresolved; prior issuer filings do not bypass this same-day check.", "",
              "No ambiguous candidate was selected or fetched. Original Phase A results stay",
              "unchanged. Independent fixture-protocol-v2 approval is required before any",
              "additional WRDS extraction. DATA-02 is NOT PASS; Gate A remains BLOCKED.", ""]
    (output / "sec_confirmation_report.md").write_text("\n".join(lines))
    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Offline Phase B1/B2; no live provider access")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/gate_a_data_02_phase_b.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if (config["phase"] != "B1_B2" or config["additional_wrds_extraction"] is not False
            or set(config["authorized_ciks"]) != {"0001505611", "0001556266"}
            or config["phase_a_manifest"] != "artifacts/gate_a/identity_spine/identity_manifest.json"
            or config["sec_fixture_directory"] != "data/raw/sec/gate_a/data_02"
            or config["acceptance_conflict_policy"] != "FAIL_CLOSED_PENDING_RESEARCH_OWNER"):
        raise ValueError("Config must preserve the Phase B authorization and conflict policy")
    raw = json.loads((ROOT / config["sec_fixture_directory"] / "sec_fixture_manifest.json").read_text())
    if raw["targets"] != config["first_evidence_dates"]:
        raise ValueError("SEC fixture selection differs from run config")
    b1, b2 = run_b1(), run_b2()
    directory = ROOT / "artifacts/gate_a/identity_spine"
    run_manifest = {
        "config_sha256": digest(args.config.read_bytes()), "config": config,
        "implementation_sha256": {p.name: digest(p.read_bytes()) for p in (
            Path(__file__), Path(__file__).with_name("sec_confirmation.py"),
            ROOT / "src/data/providers/sec_identity.py")},
        "unresolved_reason_counts_sha256": digest((directory / "unresolved_reason_counts.json").read_bytes()),
        "sec_confirmation_manifest_sha256": digest((directory / "sec_confirmation_manifest.json").read_bytes()),
        "licensed_outputs_sha256": {name: digest((directory / name).read_bytes()) for name in (
            "unresolved_root_causes.parquet", "phase_b_identity_samples.parquet")},
        "final_sec_confirmed_observations": b2["final_sec_confirmed_observations"],
        "unique_sec_confirmed_issuers": b2["unique_sec_confirmed_issuers"],
        "remaining_ambiguous_observations": b2["remaining_ambiguous_observations"],
        "original_five_issuer_requirement_satisfied": False, "Gate A": "BLOCKED",
    }
    (directory / "phase_b_run_manifest.json").write_bytes(encoded(run_manifest))
    print(json.dumps({"B1_counts": b1["counts"], "B2_status": b2["status"],
                      "confirmed_observations": b2["final_sec_confirmed_observations"],
                      "confirmed_issuers": b2["unique_sec_confirmed_issuers"],
                      "ambiguous_observations": b2["remaining_ambiguous_observations"]}))


if __name__ == "__main__":
    main()
