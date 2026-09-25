# P1-05 — Executable Label Builder

Status: **CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING**. Independent review approved the implementation with BLOCKER=0, HIGH=0, MEDIUM=0 and LOW=0. Gate A remains **PARTIAL** because the artifact uses a synthetic fixture rather than a real 2010–2025 provider vertical slice.

## Frozen convention

For each signal timestamp, the builder resolves the first explicit exchange-session open after the signal and the first session open after the next scheduled signal. It does not use `shift(-5)`. The resulting interval is recorded as `[entry_execution_timestamp, label_end_timestamp]`, with `label_end_timestamp` equal to the exit execution timestamp.

Security and SPY returns use the same interval and the shared `src/returns/economic_return.py` primitive. The target is simple excess return:

```text
target_excess_return = security_total_return - benchmark_total_return
```

Labels are intentionally forward-looking, are physically separate from `FeatureFrame`, and are never imputed. Missing prices, missing benchmark data, invalid schedules and unsupported corporate actions produce explicit invalid reason codes.

## Artifacts and tests

`experiments/phase1/run_p1_05.py` generates:

```text
artifacts/p1_05/label_manifest.json
artifacts/p1_05/label_schema.json
artifacts/p1_05/labels.json
artifacts/p1_05/label_quality_report.md
artifacts/p1_05/implementation_status.json
```

Tests cover open-to-open arithmetic, excess-return arithmetic, holiday schedule resolution, exact label interval metadata, split invariance, dividend treatment, incomplete-session coverage, missing benchmark/exit values, serialization artifacts and feature/label module separation. No purge, embargo, walk-forward, IC/RankIC, model or portfolio code is included.

Target diagnostics in the quality report are read-only and are not preprocessing parameters. Research results remain `[TODO: 待实验结果]`.

## Independent review

The review is recorded at `docs/reviews/p1_05_review.md`; all findings are resolved with BLOCKER=0, HIGH=0, MEDIUM=0 and LOW=0. Remote CI remains pending.

## Decision record

The research-decision register already reserves numeric `RDR-008` for model-policy decisions. To avoid overwriting that existing record, the executable-label decision is recorded as **RDR-008-LABEL** in `docs/research_decisions.md` and `docs/decisions/RDR-008_label_convention.md`.
