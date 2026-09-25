# Research Decision Record register

Entries in the open table below remain proposals, not approved research changes. Approved P1-02 clarifications are recorded separately below. Owner approval is required before dependent implementation. Phase 1 research results: [TODO: 待实验结果]

| ID | Question requiring a decision | Proposed resolution | Blocks |
|---|---|---|---|
| RDR-001 | A fixed five-session label can differ from next weekly rebalance during holiday weeks. Which governs? | Use actual consecutive weekly execution opens; retain explicit duration metadata. | P1-05, P1-06 |
| RDR-002 | What exact side of each chronological boundary receives the five-session embargo? Are label endpoints inclusive? | Specify interval rules and examples before implementing splits. | P1-06 |
| RDR-003 | Top-25 can violate sector feasibility; fewer than 25 eligible assets can occur. | Fail and report infeasibility; do not silently change candidates or caps. Confirm whether sector cap also applies to EW. | P1-09, P1-10 |
| RDR-004 | Which licensed PIT membership, prices, corporate actions and filing sources are available? How are revisions and delistings handled? | Select versioned sources and availability contracts before ingestion. | Production data and Gate A |
| RDR-005 | Are labels raw open returns or corporate-action-aware total returns? How do costs fund trades? | Specify splits, dividends, delisting, initial cash, terminal liquidation and additive net-return accounting. | P1-05, P1-09 |
| RDR-006 | Covariance window, shrinkage method, horizon scaling, gamma and kappa are not fixed. | Freeze values and units before MVO; no test-based calibration. | P1-10 |
| RDR-007 | Several feature formulas, all-missing imputation, winsor bounds and metric conventions are undefined. | Freeze a feature/metric dictionary, risk-free assumption and annualization rules. | P1-03, P1-04, P1-08, P1-12 |
| RDR-008 | Validation search space, boosting rounds, early stopping, bagging frequency and alpha gate thresholds are not fixed. | Register policy before examining test results; specify reuse of earlier test years in later folds. | P1-07, Gate B |


## Approved P1-02 clarifications — Research Owner's P1-02 instruction

- **RDR-009 APPROVED / IMPLEMENTED:** Signal forms after the completed bar is available. Config uses 16:10 America/New_York, with a minimum bar delay of five minutes after the explicit official session close (normally 16:05 ET). Early-close floor follows that session's close; formation stays 16:10. Execution remains next trading-day open. No horizon or portfolio logic changed.
- **RDR-010 APPROVED / IMPLEMENTED:** Fundamental knowledge requires both filing acceptance and revision availability. Select latest available revision per exact fact/period/unit observation; preserve accession, revision ID and predecessor. Do not backfill final revised values.
- **RDR-011 APPROVED / CONTRACT ONLY:** Preserve raw executable OHLC plus actions and provenance. Future feature series use PIT split/dividend adjustments; executable accounting uses raw prices plus explicit actions; returns must share a consistent total-return treatment. RDR-005 remains open for the detailed future accounting implementation.
- **RDR-012 ENGINEERING GUARDRAIL:** Finite membership/master endpoints carry their own knowledge timestamp; unannounced future endpoints are redacted. Retrospective interval corrections are unsupported and rejected, requiring a future reviewed bitemporal extension.
- **RDR-013 CONSERVATIVE PROVIDER LIMITATION:** SEC offline one-accession normalization uses ingestion availability for current Company Facts values. No historical publication or revision completeness is claimed. Synthetic provider-format tests are not evidence of live provider coverage. Production data source approval under RDR-004 is still pending.

P1-02 introduces no feature, label, preprocessing, optimizer, alpha or backtest implementation.

## RDR-008-LABEL — Research Owner executable-label convention

The existing numeric RDR-008 remains reserved for model-policy decisions. This P1-05 contract is therefore recorded with a suffix rather than overwriting that entry. Labels use the first next exchange-session open after a signal and the first next-session open after the following scheduled signal; no fixed dataframe shift is allowed. Security and SPY use the same interval and shared corporate-action-consistent economic-return primitive. The target is simple excess return, labels remain physically separate from FeatureFrame, and invalid labels retain explicit reason codes without imputation. `label_end_timestamp` is emitted for later purge/embargo logic. Gate A remains PARTIAL.

## RDR-004 — Research Owner provider-stack decision: APPROVED

The preferred Phase 1 research-grade combination is CRSP U.S. Stock + CRSP historical S&P 500 constituents via WRDS + SEC EDGAR accession-level filings + approved historical CRSP-to-SEC linking tables. Internal `security_id` maps to CRSP PERMNO for this stack; ticker remains descriptive metadata. If CRSP/WRDS access is unavailable, Norgate Data US Stocks Platinum + SEC EDGAR is the only approved conditional fallback, with reduced corporate-action audit scope and fail-closed handling for unsupported complex events. Current-constituent backfills, Yahoo-only, FMP-only, Polygon-only, Wikipedia membership history and fixed-lag fundamentals are rejected. This approval does not pass Gate A; provider access and real-data audits remain required under RDR-014-GATE-A.


## P1-03 — open numerical specification under RDR-007

The Research Owner has authorized the exact 31-feature list, missingness preservation, PIT-only inputs, SPY beta benchmark, stateless ranks and no learned preprocessing. Those do not yet resolve all numerical definitions.

**RDR-007 / P1-03 historical proposal (superseded by the decision below):** see `docs/decisions/p1_03_feature_conventions_proposal.md`, sections A (market) and B (fundamentals), for a concrete decision-ready proposal. Approval/amendment has been requested asynchronously; no answer is assumed. No dependent production calculators or frozen definition registry are implemented until this is settled. The proposed dividend-return convention concerns feature computation only; executable label/accounting treatment under RDR-005 remains separate.

Current project statuses: P1-01/P1-02 Conditional PASS; Gate A PARTIAL; P1-03 infrastructure in progress, not Conditional PASS.


## RDR-007 — Research Owner decision: APPROVED WITH MODIFICATIONS

The subsequent Research Owner instruction is binding and supersedes proposal A/B. No further approval is needed for P1-03 calculators. P1-04 preprocessing and P1-08/P1-12 metric decisions remain out of scope.

- Return features use PIT corporate-action-consistent total-return prices; liquidity/market cap use raw prices and raw volume. Latest PIT-available completed bar anchors each security. Trading-observation horizons only; missing observations are never forward-filled. Strict full windows.
- Simple cumulative returns for momentum; daily log returns for volatility/beta. ret_h requires h+1 prices. momentum_12_1 = P[t-21]/P[t-252]-1. Distance to high uses 252 prices and is nonpositive.
- Sample volatility ddof=1, annualization 252. Downside semideviation uses all 60 log returns with threshold zero. Beta uses aligned SPY log returns; zero benchmark variance is missing.
- max_drawdown_60d / max_drawdown_252d use 60 / 252 **price** windows, negative peak-to-trough drawdown (Owner minimum-history table is binding).
- adv_usd_20d / adv_usd_60d use mean raw-close×raw-volume. log_dollar_volume_20d = ln(1+ADV20). dollar_volume_change_20d compares consecutive nonoverlapping 20-session means. Amihud = 1e6×mean(abs(simple daily return)/USD dollar volume); nonpositive DV invalidates the full window.
- Flow facts normalize discrete quarters from explicit quarter/YTD/FY periods before summing TTM. Require same fiscal year when differencing, four contiguous nonoverlapping quarters, and only PIT-visible revisions. Never sum overlapping YTD values or annualize incomplete histories.
- earnings_yield, book_to_market, fcf_yield replace the proposed valuation names. Market cap = raw close×latest PIT shares adjusted for already-known splits after the reported share basis. Negative common earnings/equity/FCF remain valid numerators. CapEx is a positive outflow magnitude.
- ROE uses TTM common earnings / average common equity; ROA uses TTM net income / average assets; gross-profit/assets also uses average assets. Average balances are current and four-quarter-prior values. Nonpositive denominator is missing.
- Operating margin uses TTM operating income/TTM revenue. Revenue and diluted-EPS growth compare current TTM with preceding four-quarter TTM; prior denominator must be positive. No arbitrary floor. Debt/assets uses co-period total debt/assets; total-debt concept takes priority over components to avoid double count.
- Raw missingness retained; 10 fundamental missing indicators. Optional average-tie percentile ranks use only nonmissing current PIT universe values. No learned preprocessing, labels, training or portfolios.

Implementation representation: fiscal year/quarter and quarter-start metadata must be supplied by canonical normalization, not guessed from calendar duration. Missing metadata yields missing features. The previously proposed 70–110 day heuristic is not adopted. Unknown issuer/share-class compatibility cannot justify a valuation ratio; preserve missingness rather than guessing a mapping. EPS share-basis metadata is needed for split-consistent comparisons; raw facts never get silently overwritten. These are data sufficiency checks, not tuned parameters.

Gate A remains PARTIAL. P1-03 stays IMPLEMENTED / INCOMPLETE until correctness, artifacts and independent review are complete; Conditional PASS remains the Research Owner's decision.

## GATE-A-INFRA-01 / GATE-A-DATA-02 scope and evidence reconciliation — OPEN

The current task contains both identity-spine and connector instructions; the latter
explicitly excludes identity resolution. Implement the independent local connector first.
The Research Owner states DATA-01 passed, but the on-disk DATA-01 report and probe still
record blocked WRDS access. Preserve those historical artifacts; request the newer
passed evidence location before claiming verified live identity samples. Do not fabricate
fixtures, reinterpret filing observation dates as identity validity, or declare Gate A PASS.
Identity-dependent behavior awaits scope/evidence clarification. This does not block the
mock-tested ingestion infrastructure or change the approved provider stack.


## Research Owner gate sequencing and DATA-02 decision — 2026-09-25

Supersedes the earlier scope/access reconciliation entry: DATA-01 is PASS based on
owner-confirmed record-level access to all six requested CRSP/WRDS tables. INFRA-01
is IMPLEMENTED / LOCALLY VERIFIED / INDEPENDENT REVIEW PENDING. Gate A stays BLOCKED.
DATA-02 scope is approved, but work starts only after repository location is verified
and independent INFRA-01 review reports BLOCKER=0/HIGH=0. Current Git inspection finds
an unborn local repository, not an isolated worktree; owner location confirmation is
pending. No new access probe is claimed in this status update.

DATA-02 resolves PERMNO → historical CRSP CUSIP → WRDS CIK evidence → SEC accession.
PERMNO is canonical; ticker is metadata. Select CRSP security history inclusively at
both source dates (`secinfostartdt <= date <= secinfoenddt`); do not silently substitute
the canonical store's half-open convention. No history gives UNRESOLVED; conflicting
history gives AMBIGUOUS. Only validated 2/3 links are strong candidates; 0/1 are not
automatically trusted. `cikdate1/2` are first/last observed filing dates, never full
identity validity intervals or the sole BETWEEN acceptance condition. No score or row
ordering may choose between plausible CIKs. A single strong candidate resolves; multiple
plausible candidates are AMBIGUOUS; none is UNRESOLVED. Resolution must be deterministic,
auditable and unchanged by future identity records. No current-identifier backfill.

Output includes security_id/type, as_of_date, historical ticker/CUSIP/CUSIP9,
resolved_cik, validated/tmatch, first/last CIK evidence dates, status/reason,
primary source and independent crosscheck CIK/source/status. CCM PERMNO→GVKEY→CIK
may report AGREE/DISAGREE but never overwrite the primary path or supply fundamentals.
Approximately five real identity fixtures cover ordinary history, ticker/symbol change,
CUSIP change, index membership change and an amendment where practical; PERMNO 78690 is
an owner-suggested candidate, not a frozen cohort choice. Confirm each resolved fixture
against the actual SEC accession filer CIK. No membership ingestion, bulk market data,
corporate-action economics, features, labels, training, performance or cohort freeze.

Required tests: historical selection, stable PERMNO, no backfill, validated filtering,
ambiguous/unresolved fail-closed, future identity invariance, deterministic repeats,
SEC filer-CIK consistency and CCM disagreement reporting. Identity implementation and
its detailed evidence handling are deferred until the stated prerequisites are met.


INFRA-01 independent review follow-up (2026-09-25): initial HIGH for native SQL type
conversion was repaired and independently re-reviewed; BLOCKER=0/HIGH=0 (MEDIUM=0/LOW=0).
Reviewer independently verified 189 full-suite tests and 35 connector tests, Ruff and
strict MyPy. Repository owner confirmation remains the only unresolved INFRA-01 process
prerequisite; no Conditional PASS or DATA-02 start is inferred from elapsed time.


## Research Owner canonical repository confirmation and INFRA acceptance — 2026-09-25

`/Users/kaffy/Documents/RL Engine` is the canonical primary repository. Its initial
local Git state without remote or prior commits is intentional. INFRA-01 is accepted
as CONDITIONAL PASS / LOCAL VERIFIED with independent BLOCKER=0/HIGH=0. DATA-01 is
PASS; Gate A remains BLOCKED. Create a tracked baseline excluding licensed raw/canonical
data, credentials, environment files and generated Parquet; verify Git status, tracked
files and latest commit, then create `gate-a/data-02-identity-spine`. DATA-02 is authorized
after those steps. This supersedes the pending repository-confirmation entries above.
