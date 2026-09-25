# RDR-009-WF — Walk-Forward, Purge and Embargo Convention

**Status: IMPLEMENTED CONTRACT — P1-06**

Phase 1 uses expanding folds with test years 2017–2025. For test year `Y`, training owns signal years 2010–`Y-2`, validation owns `Y-1`, and test owns `Y`. Split ownership uses `signal_timestamp`.

The first five actual exchange sessions at each validation/test nominal start are embargoed. Purge uses the emitted P1-05 label interval: `label_end_timestamp < downstream_effective_start`; equality is excluded. 2026 is reserved and any label requiring 2026 market data is excluded from Phase 1. Each fold fits its own P1-04 preprocessor on TRAIN only. This record does not introduce model training or performance evaluation.
