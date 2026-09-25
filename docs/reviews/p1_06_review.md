# P1-06 Independent Walk-Forward Review

**Reviewer:** independent quantitative leakage audit  
**Scope:** split ownership, interval purge, exchange-session embargo, fold isolation, preprocessing isolation, label handling, artifacts and determinism  
**Recommendation:** **APPROVE**  
**Finding counts:** BLOCKER 0 · HIGH 0 · MEDIUM 0 · LOW 0

## Verification performed

- Read `AGENTS.md`, `RDR-009-WF`, the P1-04 preprocessing contract and the P1-05 label contract.
- Reviewed `src/validation/walk_forward.py`, `src/validation/artifacts.py`, the P1-06 runner and validation tests.
- Re-reviewed the remediation for missing labels, malformed valid labels, separate purge/embargo counts, config propagation, local-time signal-year ownership and incomplete calendar coverage.
- Confirmed the future-label append invariance test is present.
- Ran the complete local test suite: **154 passed**.
- Ran Ruff: **passed**.
- Ran Mypy: **passed**.
- Inspected the generated synthetic fold manifest and preprocessing artifact.

## Approved controls

Split ownership is derived from the America/New_York signal year. Purge uses the actual `label_end_timestamp` and the strict rule `label_end_timestamp < downstream_effective_start`; equality is excluded. Embargo dates come from the explicit exchange calendar and are not computed with calendar-day offsets. The builder fails closed when fewer than five sessions are available after a nominal boundary.

Missing `(security_id, signal_timestamp)` label records fail with `MISSING_LABEL_RECORD`. A `label_valid=True` row must have entry, exit and label-end timestamps, with `label_end_timestamp == exit_execution_timestamp`. Invalid labels are excluded from supervised outputs and counted by reason. Purge, embargo, missing-label and invalid-label counts are represented separately in the fold manifest.

Each fold fits a new P1-04 preprocessor on TRAIN and transforms validation/test with that state. The runner loads and passes the canonical `Phase1Config` and records its config hash. Feature rows and label rows remain separate, sample keys are checked for disjointness, temporal ordering is checked, 2026 is rejected as a test year, and labels ending after 2025 are excluded.

The exact-boundary, malformed/missing-label, future-label append and reserved-2026 regression checks pass. Calendar and schedule edge cases are covered by the P1-05/P1-02 contract tests. The local quality gates are clean: 154 tests, Ruff and Mypy.

## Final recommendation

**APPROVE.** BLOCKER, HIGH, MEDIUM and LOW counts are all zero after remediation. P1-06 may be recorded as:

```text
CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING
```

This approval covers the synthetic/local contract only. Gate A remains **PARTIAL** because no real 2010–2025 provider coverage or corporate-action/calendar vertical slice has been validated. No model performance conclusion is made.
