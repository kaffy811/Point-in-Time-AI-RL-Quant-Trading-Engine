"""Auditable data-quality diagnostics, with no alpha or performance metrics."""
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.data.lineage import build_manifest, content_hash
from src.data.schemas import (
    Calendar, Contract, DataBundle, FundamentalFact, IndexMembership, MarketRecord, SecurityMaster,
)
from src.data.validation import Issue, validate_bundle
from src.utils.config import Phase1Config

DATASETS: dict[str, type[Contract]] = {"securities": SecurityMaster, "memberships": IndexMembership,
            "market": MarketRecord, "fundamentals": FundamentalFact}


def inspect_payload(payload: dict[str, Any]) -> tuple[DataBundle, tuple[Issue, ...]]:
    """Retain rejection evidence; never return a partial dataset as a successful load."""
    issues = []
    accepted: dict[str, list[object]] = {}
    if set(payload) != set(DATASETS):
        raise ValueError("payload must contain exactly four canonical datasets")
    for name, schema in DATASETS.items():
        if not isinstance(payload[name], list):
            raise ValueError(f"dataset {name} must be a list")
        accepted[name] = []
        for index, raw in enumerate(payload[name]):
            try:
                accepted[name].append(schema.model_validate(raw))
            except ValidationError as exc:
                message = str(exc)
                code = ("timestamp_violation" if "timestamp violation" in message
                        else "invalid_interval" if "invalid interval" in message
                        else "schema_violation")
                issues.append(Issue(code=code, dataset=name, message=f"row {index}: {message}"))
    return DataBundle.model_validate(accepted), tuple(issues)


def generate_report(
    payload: dict[str, Any], calendar: Calendar, config: Phase1Config, *,
    as_of: datetime, dataset_version: str, ingested_at: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("report as_of must be timezone-aware")
    bundle, rejected = inspect_payload(payload)
    issues = rejected + validate_bundle(bundle, calendar,
                                        config.market_data.completed_bar_delay_minutes)
    counts = Counter(i.code for i in issues)
    coverage: dict[str, object] = {}
    for name, field in (("securities", "valid_from"), ("memberships", "effective_from"),
                        ("market", "trade_date"), ("fundamentals", "fiscal_period_end")):
        values = sorted(getattr(row, field).isoformat() for row in getattr(bundle, name))
        coverage[name] = {"field": field, "start": values[0] if values else None,
                          "end": values[-1] if values else None}
    ticker_history: dict[str, list[SecurityMaster]] = defaultdict(list)
    for security in bundle.securities:
        ticker_history[security.security_id].append(security)
    missing_fields = Counter(field for row in bundle.market
                             for field in ("raw_open", "raw_high", "raw_low", "raw_close")
                             if getattr(row, field) is None)
    # Expected active member/session observations are computed without any price-based selection.
    observed = {(r.security_id, r.trade_date) for r in bundle.market}
    missing_observations = 0
    for session in calendar.sessions:
        if session.close_timestamp > as_of:
            continue
        active_ids = {r.security_id for r in bundle.memberships
                      if r.index_id == "sp500" and r.effective_from <= session.close_timestamp
                      and (r.effective_to is None or session.close_timestamp < r.effective_to)}
        missing_observations += sum((sid, session.trade_date) not in observed for sid in active_ids)
    report: dict[str, object] = {
        "status": "FAIL" if issues else "PASS", "scope": "data_contract_only",
        "dataset_version": dataset_version, "as_of": as_of.isoformat(),
        "config_hash": config.config_hash(), "input_content_hash": content_hash(payload),
        "date_coverage": coverage,
        "number_of_securities": len({r.security_id for r in bundle.securities}),
        "membership_additions": len(bundle.memberships),
        "membership_removals": sum(r.effective_to is not None for r in bundle.memberships),
        "duplicate_counts": counts["duplicate"],
        "missing_price_counts": dict(missing_fields),
        "missing_price_observations": missing_observations,
        "missing_volume_counts": sum(r.volume is None for r in bundle.market),
        "fundamental_fact_counts": len(bundle.fundamentals),
        "missing_fundamental_values": sum(r.value is None for r in bundle.fundamentals),
        "late_filings": sum(r.filing_accepted_at > as_of for r in bundle.fundamentals),
        "late_filings_definition": "filing acceptance after report as_of, not regulatory lateness",
        "invalid_intervals": counts["invalid_interval"],
        "orphan_security_ids": counts["orphan_security_id"],
        "ticker_changes": sum(
            sum(before.ticker != after.ticker for before, after in zip(ordered, ordered[1:]))
            for ordered in (sorted(rows, key=lambda r: r.valid_from)
                            for rows in ticker_history.values())),
        "records_rejected_for_timestamp_violations": counts["timestamp_violation"],
        "schema_rejected_records": len(rejected),
        "issues": [i.model_dump(mode="json") for i in issues],
        "limitations": ["Dataset-wide diagnostic; not a historical feature source.",
                        "PASS validates supplied contracts, not provider completeness or truth.",
                        "No performance metrics or research gate approval."],
    }
    manifest = build_manifest(bundle, calendar, dataset_version, ingested_at)
    manifest["validation_status"] = report["status"]
    manifest["excluded_schema_invalid_rows"] = len(rejected)
    manifest["input_content_hash"] = report["input_content_hash"]
    return report, manifest


def write_report(report: dict[str, object], manifest: dict[str, object], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "data_quality_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# P1-02 Data Quality Report", "", f"Status: **{report['status']}**", "",
             "Data contracts only; no performance results. See JSON for rejection details.", "",
             "| Metric | Value |", "|---|---|"]
    for key, value in report.items():
        if key not in ("issues", "limitations"):
            lines.append(f"| {key} | {json.dumps(value, ensure_ascii=False)} |")
    lines += ["", "## Issues", "", "```json", json.dumps(report["issues"], indent=2), "```",
              "", "## Limitations", "", str(report["limitations"]), ""]
    (output / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")
