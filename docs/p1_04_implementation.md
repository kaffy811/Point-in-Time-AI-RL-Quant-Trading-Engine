# P1-04 — Train-Only Preprocessing Pipeline

Status: **CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING**. Independent review approved the implementation with BLOCKER=0, HIGH=0, MEDIUM=0 and LOW=0. Gate A remains **PARTIAL** because the generated artifacts use the deterministic synthetic fixture rather than a real 2010–2025 historical data vertical slice.

## Scope

P1-04 consumes the validated P1-03 `FeatureFrame` and implements only learned preprocessing state:

- 1% / 99% linear train-only winsorization for continuous raw features;
- median imputation fitted from winsorized TRAIN values;
- passthrough missingness indicators;
- strict feature registry hash and column-order validation;
- fail-loud handling for infinite values and all-missing TRAIN features;
- JSON-readable per-fold state, fit lineage and transform diagnostics.

Scaling, PCA, feature selection, labels, LightGBM, portfolios, backtests and RL are outside this ticket.

## Leakage controls

`Preprocessor.fit` accepts only an explicitly supplied TRAIN frame and records `fit_row_ids_hash`. Validation and test frames are transform-only. Frozen parameters are never read from the P1-03 full-sample QA report; that report remains diagnostic-only. Missing indicators are neither winsorized nor imputed. Cross-sectional ranks, when present in a future registry version, are policy-controlled rather than identified by column-name heuristics.

The test suite covers validation/test perturbation invariance, serialization determinism, fold isolation, schema drift, infinite-value rejection, all-missing fold failure and artifact isolation. The synthetic artifact generator is `experiments/phase1/run_p1_04.py`.

## Artifacts

The generator writes:

```text
artifacts/p1_04/fold_synthetic/preprocessor.json
artifacts/p1_04/fold_synthetic/fit_manifest.json
artifacts/p1_04/fold_synthetic/transform_report.json
artifacts/p1_04/preprocessing_quality_report.md
artifacts/p1_04/implementation_status.json
```

These files are evidence of deterministic contract behavior only. They do not contain performance results and do not establish real-data coverage. Any research result remains `[TODO: 待实验结果]`.

## Local verification

```sh
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mypy src
```

The independent review is recorded at `docs/reviews/p1_04_review.md`. Remote CI evidence is a separate requirement before the ticket can be marked CLOSED.
