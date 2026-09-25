# P1-06 — Walk-Forward / Purge / Embargo

Status: **CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING**. Independent review approved the implementation with BLOCKER=0, HIGH=0, MEDIUM=0 and LOW=0. Gate A remains **PARTIAL**; the generated fold is synthetic and does not establish real 2010–2025 data coverage.

## Frozen split contract

For test year `Y` in 2017–2025:

```text
TRAIN      signal years 2010..Y-2
VALIDATION signal year    Y-1
TEST       signal year    Y
```

Split ownership is based on `signal_timestamp`. Validation and test starts are embargoed by five actual exchange sessions from the configured calendar. Purge is dynamic: a sample remains eligible only when its `label_end_timestamp` is strictly before the downstream effective boundary. Equality is purged. Invalid labels never enter a supervised split and are counted by reason upstream in the label frame.

Each fold fits a new P1-04 preprocessor on TRAIN only and transforms validation/test with that frozen state. FeatureFrame and LabelFrame remain separate; model-ready transformed X and y artifacts are emitted independently. 2026 test labels are excluded by the phase horizon rule.

## Artifacts

`experiments/phase1/run_p1_06.py` generates a deterministic synthetic `fold_2017` containing split, purge, embargo, preprocessing and native Parquet X/y artifacts. The pinned `pyarrow==18.1.0` dependency is now part of the project lock.

No LightGBM, hyperparameter tuning, IC/RankIC, portfolio, backtest, cost or RL code is included. Research results remain `[TODO: 待实验结果]`.

The independent review is recorded at `docs/reviews/p1_06_review.md`; all findings are resolved. Remote CI remains pending.

## Decision record

The walk-forward convention is recorded as `RDR-009-WF` in `docs/decisions/RDR-009_WF_convention.md`; existing RDR entries were not rewritten.
