# DATA-02 fixture protocol V2 — authorized supplemental six

Research Owner authorization supersedes the former three-slot proposal. Checkpoint
`2a6a046` preserves the accepted Phase A/B1/B2 audit: eight SEC-confirmed observations,
two confirmed issuers, two role conflicts and nine original ambiguous observations.
DATA-02 remains IN PROGRESS; Gate A remains BLOCKED.

## Precommitted selection

Config: `configs/gate_a_data_02_v2.json`. The candidate catalog is the lowest **60
numeric PERMNOs** with a CRSP security-history interval overlapping 2010-01-01 through
2025-12-31, excluding original PERMNOs 12350, 13030, 14093, 78690 and 90298. Only
aggregated historical security metadata and historical S&P membership-event metadata
are retrieved for this catalog. This is a bounded convenience sample, not a claim
of representative market coverage. No current membership filter is applied.

Choose exactly six distinct PERMNOs in this fixed order, excluding earlier selections:

1. Ordinary long-lived: observed endpoints cover the window, with no observed ticker,
   symbol or CUSIP change. This is endpoint coverage, not proof of uninterrupted listing.
2. Ticker/trading-symbol change: more than one distinct non-null ticker or symbol.
3. CUSIP change: more than one distinct non-null eight-character CUSIP.
4. Historical S&P addition/removal: membership start/end lies inside the window.
5. Combined ticker/symbol and CUSIP change: a reorganization **screening proxy**, not
   proof of a corporate event. Actual category evidence must be assessed separately.
6. Amendment audit slot: lowest unused PERMNO. SEC amendment availability is checked
   only after freezing, never used to select a successful issuer.

For each slot take the lowest eligible unused numeric PERMNO. If the stratum is
absent, take the lowest unused PERMNO and explicitly record the coverage shortfall.
If fewer than six candidates are available, stop without widening the catalog.
The ordering never uses links, validated codes, SEC metadata, resolver outcomes,
returns or performance. Null metadata is not an identifier backfill.

`v2_selection_manifest.json` is written exclusively under
`artifacts/gate_a/identity_spine/` **before any CIK-link request**, containing all six
PERMNOs, slot/fallback decisions, catalog hash, query hash, code/config hashes and
freeze timestamp. Catalog row-level metadata remains Git-ignored. Until this file
exists from real WRDS metadata, no real PERMNO selection is claimed.

The prerequisite **input** is `data/raw/wrds/gate_a/data_02_v2/selection_metadata.parquet`
with `selection_metadata.manifest.json`. It is obtained by the existing INFRA-01
`Connector.query` path using only the bounded CRSP aggregate above. It is not a
pre-existing six-PERMNO roster: the durable prerequisite for subsequent extraction is
the **output** `artifacts/gate_a/identity_spine/v2_selection_manifest.json`.
No CIK-link, SEC accession, resolver-outcome or return/performance input is queried or
inspected to create it.

## Bounded provider acquisition

Run locally, entering WRDS credentials only at the terminal prompt:

```bash
cd '/Users/kaffy/Documents/RL Engine'
.venv/bin/python -m src.data.providers.wrds.fixture_v2
```

The provider uses the existing interactive connector, never plaintext credential
storage. It requests one aggregate catalog (at most 60 rows), then history for the
six frozen PERMNOs (cap 500), then links for only their historical CUSIP/CUSIP9 values
(cap 200; at most 120 distinct exact identifiers combined). History/link queries
read cap+1 to detect overflow; they do not truncate. All validated codes/dates are
retained as evidence; filtering remains the frozen resolver's responsibility.

Raw output: `data/raw/wrds/gate_a/data_02_v2/`, Git-ignored. Files have query,
schema/content hashes and retrieval timestamps. Existing directories/frozen samples
are not silently overwritten. An existing empty V2 directory is allowed. An existing
file at the raw-directory path fails closed, as does nonempty raw output without a
compatible frozen manifest. Individual target files are exclusively created; complete
compatible cached files may only be verified and reused. On failure preserve artifacts and diagnose the stage;
never rerun with a different sample. No bulk market, returns, CCM or facts query.

The shared INFRA-01 bounded Arrow conversion, native Parquet writer, hash/JSON and
durable exclusive manifest writer are used by both extraction paths; there is no
second connection/authentication path. The V2 catalog aggregate remains its reviewed
fixed bounded query rather than an unrestricted SQL interface.

Freeze writes flush and fsync the file and containing directory. Its SHA-256 is then
persisted exclusively as `v2_selection_manifest.sha256` before selected history or
CIK-link acquisition. The fingerprint is verified on every retry. Once the JSON is
written, the six identifiers remain frozen even if fingerprint persistence, schema
validation, connection or any later query fails. An incomplete/conflicting JSON or
fingerprint fails closed; it never authorizes reselection. If an interruption left
the fingerprint absent, retry validates the original JSON/catalog evidence and writes
only the missing fingerprint, retaining the same JSON bytes and six identifiers.

Normal invocation detects and reuses a compatible frozen manifest automatically.
`--resume` additionally requires a pre-existing freeze and fails before interactive
authentication if it is missing. Read-only `--diagnose` reports
`INITIAL_SELECTION_READY_NOT_EXECUTED` for the authorized initial empty state or
`FROZEN_SELECTION_VERIFIED` for compatible frozen evidence; it performs no WRDS query,
does not choose securities and writes no selection artifacts.

## Frozen evaluation and SEC path

Evaluate each selected PERMNO at 16:10 America/New_York on 2010-06-30, 2015-06-30,
2020-06-30 and 2025-06-30, regardless of preliminary outcomes. Missing history remains
unresolved; do not move timestamps to obtain success. Event coverage can be described
from source metadata without adding outcome-selected resolution observations.

Use the accepted Phase A resolver unchanged. No current identifiers, future first
filing evidence, validated=0/1, highest-tmatch or arbitrary-first candidate may resolve.
Preserve multiple candidates as AMBIGUOUS. Same-day evidence requires exact accession
acceptance by as-of; cikdate2 never expires identity.

For unique historically eligible candidates only, freeze an SEC request roster before
retrieval: one bounded submissions response per candidate (2 MiB maximum, no historical
shard expansion), select latest issuer-form filing at/before each predeclared as-of date
and any same-day first-evidence filing. Inspect amendments only within those bounded
responses. Deduplicate exact accessions, cap three headers per candidate; if the required
set exceeds the cap, record the coverage limitation without choosing on confirmation
success. No requests for ambiguous candidates. Raw SGML FILER/acceptance has priority
under the already approved B2 semantics. Subject-only and missing sources never count.

The existing original-two-CIK provider allowlists remain unchanged; any V2 SEC provider
extension must be bound to the new frozen roster, not an unrestricted CIK interface.
SEC extraction starts only after real WRDS input/provenance and frozen roster verification.

## Reporting and stopping

Report all six PERMNOs and every fixed observation, including failures. Count unique
SEC_CONFIRMED CIKs together with the original two; multiple securities of one issuer
count once. Do not resample after outcomes. Fewer than five confirmed issuers means stop
and propose a separate secondary historical identity-evidence experiment. Do not add
CCM/GVKEY or modify the primary CUSIP pipeline. Reaching five is not itself research
approval; category evidence and independent review remain required. Gate A BLOCKED.

## Recovery instruction supersession — 2026-09-26 Research Owner decision

The earlier failure diagnosis is reclassified as `V2_PRE_EXECUTION_BLOCKED`: no sample
was ever frozen and no V2 outcome was observed. The missing prerequisite is the durable
`artifacts/gate_a/identity_spine/v2_selection_manifest.json`, whose role is to record the
six-PERMNO selection and its CRSP-only selection-artifact fingerprint. An empty
`data/raw/wrds/gate_a/data_02_v2/` directory is compatible with one initial selection;
a nonempty directory without that manifest fails closed. Once the initial CRSP-only
selection writes the manifest exclusively, security history may be fetched and only
then may CIK links be queried. A future valid manifest is always resumed exactly.
`--diagnose` reports this explicit prerequisite path without querying WRDS. See
artifacts/gate_a/identity_spine/v2_failure_diagnosis.md.

## Pre-execution recovery — 2026-10-25

The current instruction authorizes resolving the prerequisite and directory semantics,
with one initial selection still available because no manifest, selected PERMNO or
V2 resolution outcome exists. Live selection remains unexecuted during recovery and
must not start before the new independent review has BLOCKER=0 and HIGH=0. Earlier
review counts do not certify this revision. See
`reviews/gate_a_data_02_v2_recovery_review.md` for the new disposition. Passing code
checks does not provide real category evidence, DATA-02 acceptance or Gate A PASS.

## Executed freeze and authorized resolution — 2026-10-25

The owner completed the live freeze/extraction. The exact ordered six are now
10026, 10028, 10001, 10078, 10100, 10002; **no initial selection authorization remains**.
Freeze JSON/fingerprint and diagnostics are committed/pushed as `3c9d827`.
Selection is FROZEN_6, CIK-link extraction COMPLETE, resampling PROHIBITED. The JSON
still records links_or_sec_outcomes_inspected_before_freeze=false and
FROZEN_NO_RESAMPLING; its bytes must never be rewritten.

The owner's C1/C2 authorization retains this protocol's four fixed as-of dates and
SEC bounds. C1 is complete; C2 is pending a genuine contact User-Agent. See
`gate_a_data_02_v2_resolution.md` for all 24 outcomes and pending evidence limits.
This is a precommitted deterministic semantic-validation cohort, not a
representative random sample. The amendment slot 10002 remains even when evidence
cannot be assessed. DATA-02 remains IN PROGRESS and Gate A BLOCKED.
