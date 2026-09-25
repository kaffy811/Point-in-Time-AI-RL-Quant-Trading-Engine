# Gate A — Real Historical Vertical Slice

Status: **BLOCKED / NOT STARTED**. The preflight completed for native Parquet support, but the repository does not currently contain an approved real-data provider combination capable of supplying the required 2010–2025 PIT S&P 500 membership, historical executable opens, corporate actions, and revision-complete filing history.

## Preflight evidence

- `pyarrow==18.1.0` is installed in the project environment and pinned in `pyproject.toml` / `uv.lock`.
- P1-06 artifacts now write and read native Parquet with timezone-preserving schemas.
- The only provider implementation currently present is the archived SEC Company Facts slice. Its own contract states that ingestion-time availability of current Company Facts cannot establish historical 2010–2025 availability or revision completeness.
- No approved historical membership provider, market/corporate-action provider, or source-versioned 20–30 security cohort is available in the repository.

## Decision

Gate A is deliberately **BLOCKED**, rather than approximated with current constituents, historical prices, or synthetic provider payloads. No cohort was frozen because freezing a real cohort without an approved provider would create false evidence. No feature, label, walk-forward, model or performance result was claimed as real data.

RDR-004 now approves a preferred CRSP + SEC/WRDS stack and a conditional Norgate + SEC fallback. The next step is `GATE-A-DATA-01 Provider Access Probe`; no cohort will be frozen until access evidence exists. Once an accessible source combination is confirmed, the cohort must be frozen before inspecting any predictive statistic, then the full breadth and event-centric audits can run.

Independent review is recorded at `docs/reviews/gate_a_real_data_review.md`: **DO NOT PASS GATE A**, with BLOCKER=3, HIGH=1, MEDIUM=1 and LOW=1.

## Required artifacts

`artifacts/gate_a/` contains the preflight manifest, blocker decision, and report placeholders for the required audits. Placeholder reports are explicit `NOT RUN` records; they do not represent successful audits.
