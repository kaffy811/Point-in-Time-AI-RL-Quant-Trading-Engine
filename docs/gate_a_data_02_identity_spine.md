# GATE-A-DATA-02 — Phase A historical identity spine

Status: preliminary real-fixture resolution complete; independent review recorded separately.
**No final SEC identity is confirmed. Gate A remains BLOCKED.**

## Repository and authorization

Canonical repository: `/Users/kaffy/Documents/RL Engine`. Baseline `58805e7` tracks
185 reviewed files; branch: `gate-a/data-02-identity-spine`. DATA-01 is PASS and
INFRA-01 is CONDITIONAL PASS / LOCAL VERIFIED, with BLOCKER=0/HIGH=0 independent review.
The Research Owner explicitly authorized Phase A without SEC accession fixtures.
The earlier missing-input/preparation status is superseded by the supplied real WRDS files.

## Real inputs and reproduction

The owner-supplied manifest and two Parquet files reside in the Git-ignored directory
`data/raw/wrds/gate_a/data_02/`. The runner verifies each source-table name, file SHA-256,
row count and PERMNO coverage before parsing. Actual inputs are 91 security-history rows,
35 CIK/CUSIP link rows, and five PERMNOs. Existing source dates are ISO strings; the
adapter parses their explicit dates without rewriting raw bytes or inventing intervals.

```sh
uv run --frozen --extra wrds python -m src.data.identity.cli --config configs/gate_a_data_02.json
uv run --frozen --extra wrds pytest tests/unit/data/identity -q
uv run --frozen --extra wrds pytest -q
uv run --frozen --extra wrds ruff check .
uv run --frozen --extra wrds mypy src
```

The resolver imports no live provider/network client. It only reads local immutable
fixtures. The JSON config fixes the fixture manifest, securities, sampling policy,
anchor dates, time zone, signal time and output directory. Manifests record code,
config, input and output hashes. Repeated runs produce byte-identical reports/artifacts.

Sampling uses each security's real interval starts/ends and adjacent outside dates,
matching link first-filing dates ±1 day, plus 2015-06-30. This produces 283 observations
at 16:10 America/New_York. This boundary audit makes no exchange-session/tradability claim
and does not ingest membership, freeze a stock cohort or select on performance.

## Resolution behavior

PERMNO is canonical; ticker and trading symbol are descriptive only. Select CRSP
history with inclusive `secinfostartdt <= as_of_date <= secinfoenddt`. No match is
UNRESOLVED. Conflicting active identity projections are AMBIGUOUS; identical projections
from multiple records do not invent another identity, and the raw records are preserved.
Missing historical CUSIPs remain unresolved. Conflicting 8/9-character CRSP identifiers
fail closed; identifiers are never reconstructed or padded.

Apply date eligibility before matching-tier preference. Prefer historical exact CRSP
cusip9 → WRDS cusip_full with validated=3. If that tier has no eligible evidence, fall
back to exact CRSP cusip → WRDS cusip with validated=2. Future nine-character links must
not displace an already-historical eight-character result. Validated 0/1 never resolve.

Strictly earlier cikdate1 is historical evidence. Equal-date evidence remains provisional:
a single equal-day-only CIK is UNRESOLVED with reason
`SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED`; multiple plausible CIKs in the selected
tier remain AMBIGUOUS, including provisional same-day competitors. Phase A does not
inspect SEC acceptance, and never silently treats a date as an intraday timestamp.
Null/future cikdate1 cannot automatically resolve. Duplicate evidence for one CIK is
not a distinct CIK; multiple distinct CIKs are never ranked by tmatch or input order.

A unique strictly earlier candidate is `RESOLVED_PENDING_SEC_CONFIRMATION`, never
`RESOLVED`. The preliminary result keeps PERMNO/type, timestamp/date, historical
identifiers, preliminary CIK, candidate CIKs, validated tier, first evidence date,
status/reason, and explicit NOT_PERFORMED/NOT_RUN_PHASE_A SEC/CCM indicators.

cikdate2 is not an expiry date. It and tmatch are snapshot-only audit fields, retained in
ignored `wrds_link_evidence.parquet` rather than in historical result records. This
prevents later last-observation dates or aggregate scores from changing past output.
Raw input hashes/audit rows are administrative provenance, never feature inputs.

## Actual preliminary results

| Status | Observations |
|---|---:|
| RESOLVED_PENDING_SEC_CONFIRMATION | 8 |
| AMBIGUOUS | 9 |
| UNRESOLVED | 266 |

Unique preliminary CIKs requiring SEC accession confirmation: **0001505611, 0001556266**.
Ambiguous candidates needing investigation: **0001293330, 0001499961**. The first two
also occur as same-day-only candidates requiring acceptance-time checks. Counts are
observations, not independent issuers or five successful identities.

All six invariance checks pass for all 283 observations: repeat, reversed input order,
future-record removal, future-record append, future identifier-payload mutation, and
removal of last-date/score metadata. Compare the complete preliminary result, not just
CIK. Actual future-history rows are present for 275 observations and future-link rows
for 281; perturbations stay in memory and are not claimed as real evidence.

## Audit outputs and limitations

Version-controlled audit outputs in `artifacts/gate_a/identity_spine/`:
`identity_manifest.json`, `preliminary_resolution_report.md`, `ambiguity_report.md`,
`future_invariance_report.md`, `identity_audit.md`, `crosscheck_report.md`.
Licensed row-level `identity_samples.parquet`, `ambiguous_links.parquet` and
`wrds_link_evidence.parquet` remain Git-ignored, as do all source data/manifests.

There are no validated=2 links in the supplied real corpus; real eight-character fallback
coverage is NOT EXERCISED. A clearly labeled in-memory flag perturbation checks the
fallback code path only, and never substitutes for real provider acceptance evidence.
Other adversarial tests alter the real rows only to test failure modes/invariance.
Tests requiring local licensed data skip when those inputs are absent in CI; this is
not a real-fixture CI certification. Pure date/identifier/architecture tests still run.

There are no historical WRDS revision snapshots proving when scores/validated codes
were assigned. Future-effective/newly evidenced rows are isolated, but retrospective
corrections to already-historical identifiers/first dates/validated flags remain an
unproven provider limitation. No claim of full bitemporal reconstruction is made.
No SEC accession or CCM check occurred. Original ordinary/index-change/amendment fixture
category coverage is not certified by these five multi-history fixtures. All final
SEC confirmation results: [TODO: 待实验结果]. No fundamentals, labels, features, bulk
fetch, models, IC/RankIC or portfolio results were produced.


## Independent verification

Independent review: BLOCKER=0, HIGH=0, MEDIUM=0, LOW=0; see
`docs/reviews/gate_a_data_02_phase_a_review.md`. Reviewer independently verified 17
Phase A tests, 206 full-suite tests, Ruff and strict MyPy (60 source files), and rebuilt
all nine audit artifacts byte-identically. These findings cover Phase A only and do
not confirm SEC identity, pass DATA-02 as a whole, or pass Gate A.
