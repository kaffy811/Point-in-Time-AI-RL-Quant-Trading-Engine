# Gate A — Independent Real Historical Data Review

Status: **DO NOT PASS GATE A**

Review scope: provider readiness and evidence for the real historical vertical slice. No model or performance results were reviewed or used.

## Evidence reviewed

- `docs/gate_a_real_data_vertical_slice.md`
- `docs/decisions/RDR-014-GATE-A.md`
- `artifacts/gate_a/provider_manifest.json`
- `artifacts/gate_a/provider_access_probe.json`
- `docs/decisions/RDR-004_provider_stack.md`
- `artifacts/gate_a/cohort_manifest.json`
- `artifacts/gate_a/gate_a_decision.json`
- All Gate A audit reports under `artifacts/gate_a/`
- `src/data/providers/sec_companyfacts.py`
- `src/data/pit_store.py` and canonical data schemas
- `pyproject.toml` and `uv.lock`

## Findings

| Severity | Finding | Evidence and impact |
|---|---|---|
| BLOCKER | The approved CRSP/WRDS membership stack has no access evidence. | RDR-004 approves CRSP historical S&P 500 membership and WRDS linking as the preferred source, but `provider_access_probe.json` is `NOT RUN`; the cohort is `NOT FROZEN` and `membership_audit.md` is `NOT RUN`. Historical universe membership therefore cannot yet be independently verified for survivorship bias. |
| BLOCKER | The approved executable-market/corporate-action stack has no access evidence. | RDR-004 approves CRSP daily opens, raw OHLCV, distributions and delisting economics, with a conditional Norgate+SEC fallback. No access probe, market artifact, or adapter output exists; `market_data_quality_report.md` and `corporate_action_mapping.md` are `NOT RUN`. |
| BLOCKER | Approved SEC accession-level access and revision-complete filing evidence are not available. | RDR-004 names SEC EDGAR accession archives and effective-dated linking tables, but only the conservative `SECCompanyFactsAdapter` is implemented. It assigns availability at ingestion and cannot reconstruct first-publication timing or a complete amendment chain for 2010–2025. `filing_timestamp_audit.md`, `taxonomy_mapping_report.md`, and `ttm_audit.md` are `NOT RUN`. |
| HIGH | No real cohort or real vertical-slice artifacts exist. | `cohort_manifest.json` reports zero securities and no selection basis; coverage, label, and walk-forward reports are explicit `NOT RUN`. The required 20–30 security breadth run and 60-observation manual audit have not occurred. |
| MEDIUM | Gate A remains blocked even though the native Parquet preflight is satisfied. | `pyarrow==18.1.0` is declared in `pyproject.toml`, present in `uv.lock`, and imports locally as version `18.1.0`. This resolves the serialization prerequisite but does not provide real historical data evidence. |
| LOW | The repository has no remote CI evidence in the reviewed workspace. | This is a separate project-status issue and is not the reason Gate A fails; the gate is already blocked by missing approved data sources and real-data evidence. |

## Provider and approximation audit

RDR-004 now approves a preferred CRSP U.S. Stock + CRSP historical S&P 500 constituents via WRDS + SEC EDGAR accession-level filings + approved linking tables stack, with a conditional Norgate Platinum + SEC fallback. That is research authorization for a source combination, not evidence that the datasets are accessible in this workspace. `provider_access_probe.json` remains `NOT RUN`, and no approved stack has produced canonical records here. The available SEC adapter is explicitly conservative and unsuitable for retroactive historical availability claims. There is no evidence that current constituents, backfilled prices, or synthetic payloads are being presented as real data; the existing Gate A documents correctly reject those approximations.

The `PITStore` and canonical schemas provide useful contract enforcement, but they cannot establish source truth, provider taxonomy completeness, official calendar completeness, or historical revision provenance without admitted real records.

## Required unblock conditions

Gate A must remain blocked until the approved preferred stack, or the explicitly permitted fallback, has demonstrated access and supplies with provenance:

1. point-in-time historical S&P 500 membership and stable identity;
2. historical executable opens, corporate actions, and exchange calendar;
3. filing acceptance timestamps and revision/amendment history for the selected cohort;
4. a frozen 20–30 security cohort selected for event and data coverage;
5. native Parquet artifacts and the required breadth, event, label, and walk-forward audits.

No model training, IC/RankIC calculation, or performance research is authorized by this review.

## Final recommendation

**DO NOT PASS GATE A.**

Finding counts: **BLOCKER 3, HIGH 1, MEDIUM 1, LOW 1**.
