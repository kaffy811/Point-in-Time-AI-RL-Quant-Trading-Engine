# AI/RL Quant Trading Engine — Research Engineering Rules

1. Leakage prevention has priority over model performance.
2. Any median, scaler, winsorization threshold, feature selector, PCA or learned preprocessing must be fitted on TRAIN only.
3. Validation and test data are transform-only.
4. Never use current S&P 500 membership as historical membership.
5. Fundamental features may only be used when: available_timestamp <= signal_timestamp.
6. Labels may use future returns. Features may never use future information.
7. No Sharpe / return result may be reported without: turnover and transaction cost impact.
8. Phase 1 contains no RL implementation.
9. Alpha prediction and portfolio construction must remain separate modules.
10. Test data may not be used for: hyperparameter selection, feature selection, preprocessing fitting, threshold calibration.
11. Every experiment must be reproducible from config.
12. Never invent experimental results. Missing results must be marked: [TODO: 待实验结果]
13. Every code change must include or update tests.
14. Prefer simple transparent baselines before introducing additional models.

Research assumptions are frozen. Report ambiguities in docs/research_decisions.md and wait for the Research Owner before implementing dependent behavior.
Each ticket requires independent review; implementation is not research approval.
