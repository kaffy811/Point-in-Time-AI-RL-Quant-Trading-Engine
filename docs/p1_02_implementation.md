# P1-02 — Point-in-Time Data Contracts

Status: **IMPLEMENTED / LOCALLY VERIFIED / REMOTE-CI PENDING**.
Independent final recheck: **no outstanding BLOCKER/HIGH**. This ticket is not CLOSED. No remote is configured, no push/remote CI has run, and no production data or research gate is certified.

## Implementation

- Four immutable canonical schemas with stable security identity, raw OHLC/action provenance, actual filing acceptance, explicit revision chains and UTC-aware availability.
- Unified PITStore.snapshot with half-open historical membership/master intervals, knowledge gates, hidden unannounced endpoints, deterministic fundamental revision selection and explicit price freshness diagnostics.
- Fail-loud schema, duplicate, interval, orphan, revision and completed-bar checks; no deduplication, imputation or ticker joins.
- Versioned explicit calendar contract; configured 16:10 ET formation and close-plus-five-minute bar floor, including early closes and DST.
- Data-quality JSON/Markdown generator and per-dataset canonical content hashes, raw-input/config/calendar provenance.
- A single SEC Company Facts/filing-header normalization adapter. Conservative ingestion-time availability; synthetic format tests only, no live provider certification.
- Unit, integration and blocking leakage tests; synthetic fixtures for ticker change/reuse, share classes, departed members, amendments, after-signal/weekend filings, holidays, corporate actions, missing values, duplicates and orphans.
- CI runs the entire test suite, Ruff, Mypy, config validation and synthetic report generation, then uploads data-contract evidence keyed by commit SHA.

## Verification commands

```sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/quant-engine --config configs/phase1_baseline.yaml
.venv/bin/python -m src.data.cli --input tests/fixtures/p1_02/canonical.json --calendar tests/fixtures/p1_02/calendar.json --config configs/phase1_baseline.yaml --dataset-version synthetic-p1-02-v1 --as-of 2024-08-02T16:10:00-04:00 --ingested-at 2026-01-01T04:00:00+00:00 --output artifacts/p1_02
```

Latest local checkpoint: **87 tests passed**; Ruff passed; strict Mypy passed (26 source files); report status PASS for synthetic contracts. Generated artifacts are in `artifacts/p1_02/`. This PASS does not establish complete historical data, regulatory filing timeliness or future performance. Missing-price observations are intentionally present in synthetic data and are reported without shrinking the universe.

## Independent review

First review: no BLOCKER/HIGH; one MEDIUM for stale-bar ambiguity and one LOW for A→B→A ticker-count underreporting. Both corrected with regression tests. The review's previously observed test-exception mismatch is also fixed. Final independent recheck confirmed the fixes and independently ran the full suite: **87 tests passed**, with no outstanding BLOCKER/HIGH. Ruff and Mypy passed in the independent runtime-code recheck; the final addition was nine edge-case tests only.

## Research decisions and limits

Approved timing and revision clarifications are recorded under RDR-009/010; corporate-action contract under RDR-011. No features, labels, preprocessing, walk-forward, models, portfolio construction, backtesting or RL were added. The detailed corporate-action/label accounting decisions remain open; this ticket only preserves evidence. The official historical calendar and licensed PIT membership/market/fundamental sources remain the Research Owner's production decisions (RDR-004).

Retrospective master/membership corrections and automatic provider revision reconciliation are unsupported and fail explicitly. SEC current API payloads first ingested today cannot establish historical availability. Synthetic calendar and SEC-format fixtures are labeled as simulations, not real provider validation.

P1-01 retains IMPLEMENTED / LOCALLY VERIFIED / REMOTE-CI PENDING. First push must supply exact commit SHA, successful CI URL, test count and review status in both implementation reports before CLOSED. No CI evidence is fabricated.

Research results: **[TODO: 待实验结果]**.
