# P1-03 — Leakage-Safe Feature Pipeline

Status: **CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING**. RDR-007 is approved with modifications and the independent numerical review recommends approval with BLOCKER=0 and HIGH=0.
Remote CI is still pending. Gate A remains **PARTIAL — contracts verified, real historical coverage not yet validated**.

## Implemented independently of numerical formula decisions

- Feature registry contract and frozen 31-raw + 10-fundamental-missingness column whitelist (41 default columns), including approved RDR-007 definitions, names and strict full-window requirements.
- PITStore.snapshot exposes a separately requested benchmark stable ID/history and completed-session dates. Benchmark observations do not enter the eligible universe. Pre-membership market history is retained. Public audit-only manifest/hash access avoids private bundle access by feature consumers.
- Generic FeaturePipeline performs PIT-only acquisition, full-universe row preservation, exact input membership checks, per-cell lineage, availability reconciliation and missing flags. Production market, risk, liquidity and fundamental calculators are wired through `phase1_pipeline`; they do not access providers or raw files.
- FeatureFrame validates registered columns, stable security identity, beta-only explicit benchmark exceptions, no future input timestamps, missingness consistency, finite values and complete PIT-universe coverage. Wire missing values are null; model views expose NaN.
- Content-addressed input references retain source/source version and filing/revision provenance. Registry content hash is bound at generation and checked during artifact writing; values cannot silently be relabeled by a changed registry.
- Optional same-signal percentile ranks retain raw values and preserve nulls. Ties use average ranks divided by the nonmissing cross-section count. Rank views are not added to the default model whitelist and require no fitted state.
- Diagnostic-only QA/report writer emits feature definitions, schema, frame, missingness and distributions. QA statistics must never be reused for preprocessing. Synthetic feature artifacts are generated under `artifacts/p1_03`; they are not real historical coverage or research results.
- Recursive architecture tests prohibit feature dependencies on alpha/portfolio/backtest/preprocessing/providers, direct dataset reads, fitted transforms and private bundle access. Future P1-05 label files remain permitted outside the feature dependency graph.

## Local verification

```sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
```

Results: **134 tests passed**, Ruff passed, strict Mypy passed (42 source files). Tests cover scaffold serialization, whitelist rejection, raw missingness, rank ties, cross-security rejection, actual future-bar and revision invariance, benchmark separation, pre-membership access, hand-calculated market/risk/liquidity formulas, split/dividend behavior, YTD-to-quarter reconstruction, strict TTM, amendment timing, registry binding and artifact determinism. These synthetic tests do not prove real 2010–2025 data completeness.

Independent review found two HIGH infrastructure issues (cross-security frame lineage acceptance and unbound registry definitions), one MEDIUM architecture-test issue, and one HIGH numerical issue: YTD diluted EPS cannot be differenced safely. The first three were corrected; the EPS path now rejects non-Q1 YTD EPS as missing and the fixture uses direct quarterly EPS. The final independent numerical review approved the tree with BLOCKER=0 and HIGH=0; two MEDIUM findings remain for real-provider validation. P1-03 is therefore Conditional PASS locally.

## Research decision and remaining gates

The A/B proposal is preserved as superseded history. RDR-007 was approved with modifications on 2026-09-23 and is recorded as binding in docs/research_decisions.md; the registry and calculators now implement that decision.

AGENTS.md requires: “Report ambiguities in docs/research_decisions.md and wait for the Research Owner before implementing dependent behavior.” That decision is now recorded and implemented. The remaining gate is independent review, not further formula selection.

Remaining verification work is:

1. Preserve the synthetic-artifact limitation: these are diagnostic only, not real 2010–2025 data coverage.
2. Record remote CI evidence when a remote is available; this remains separate from Conditional PASS.

No imputation, fitted winsorization, scaling, labels, training, portfolios, backtests, RL or Jev were implemented. P1-03 is conditionally passed locally; remote CI and Gate A real-data validation remain open. No performance or predictive-value results exist: **[TODO: 待实验结果]**.

## Reviewer-ready change evidence

`artifacts/p1_03/reviewer_ready.patch` captures changes against the local P1-02 starting tree (not a Git commit; the repository still has no commits). `implementation_status.json` records this limitation. `git_commit` must remain null until there is a real commit; no SHA or CI evidence is invented. The generated artifacts are synthetic and diagnostic only.
