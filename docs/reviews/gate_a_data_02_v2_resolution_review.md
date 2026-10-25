# DATA-02 V2 C1/C2 — independent review

Review date: 2026-10-25. Reviewer: independent review agent, separate from the
implementation agent. No live WRDS or SEC request was made by this reviewer.
Real local WRDS input provenance and the unchanged resolver were inspected read-only;
mock HTTP tests are never counted as SEC identity evidence.

## Initial revision — changes required

Initial counts: **BLOCKER=0, HIGH=1, MEDIUM=0, LOW=0**.

### HIGH — offline identity audit imports the live WRDS layer

The initial `v2_resolution.py` imports `providers.wrds.extract` and
`providers.wrds.v2_diagnostics`; the former transitively imports `Connector`.
`sec_v2.py` also imports the WRDS extraction module for hash/JSON helpers. This
couples the offline identity audit to the live ingestion layer and fails the
existing `test_architecture_has_no_live_provider_imports` guard. Required repair:
use provider-independent artifact/hash primitives and read-only freeze verification
without weakening the existing architecture test or changing the Phase A resolver.
No live query caused by these imports was observed; this is an architectural and
required-verification defect.

Independent checks on that revision:

```text
pytest -q: 1 failed, 293 passed in 10.79s
  failure: test_architecture_has_no_live_provider_imports
Ruff: passed
MyPy: passed, 70 source files
targeted V2 tests: 28 passed
```

## Frozen evidence inspected

The authoritative selection JSON is byte-identical to commit
`3c9d827fa4c78bbad7b0427a373830349a515921`, SHA-256
`c353f73c16d4fcd0a890cde5def3ee26cc13a85475689a578179b01f5c791eb3`.
Its ordered six PERMNOs remain 10026, 10028, 10001, 10078, 10100, 10002.
The independent read-only reproduction yields all 24 predeclared observations:
8 RESOLVED_PENDING_SEC_CONFIRMATION and 16 UNRESOLVED; there are no AMBIGUOUS
observations. Each of the six existing future-invariance checks passes 24/24.
The three unique eligible CIKs are 0000043350, 0000701719 and 0000785956.

`phase_a.py`, `sgml_audit.py`, and the original `sec_identity.py`/`sec_sgml.py`
provider files are byte-identical to the frozen commit. No original resolver,
validated tier, CUSIP priority, temporal rule, tmatch rule, or FILER/SUBJECT parser
change was found. The new C2 path derives a finite request roster from unique
historically eligible C1 cases, then freezes an accession roster from bounded
submissions metadata before any raw-header outcome. It does not request historical
shards, ambiguous CIKs or alternative samples. Exceeding the three-header cap
records the coverage shortfall without choosing a subset based on confirmation.

The synthetic C2 tests cover FILER equality, SUBJECT-only role conflict, acceptance
after the as-of instant, multiple filers, unavailable sources, all-observation
retention, issuer-union deduplication, immutable retries and tampered source rejection.
The amendment slot remains 10002 even without an eligible CIK. The documented cohort
is a precommitted deterministic semantic-validation cohort, not a representative
random sample.

## Live evidence and final disposition

C2 live confirmation and final evidence review: **[TODO: 待实验结果]**.
The implementation agent is repairing the architecture finding before producing
immutable production audit artifacts. A later re-review will record final checks
and whether live evidence is complete. Code readiness does not itself certify
five confirmed issuers or provide research approval. DATA-02 remains IN PROGRESS;
Gate A remains BLOCKED.

## Repaired revision — implementation readiness

The initial HIGH is closed. Hash/JSON/durable exclusive-write primitives now live
in provider-independent `src/utils/artifacts.py`. INFRA-01's extraction module
reexports the original APIs without changing their behavior. The identity overlay
checks the pinned committed JSON, fingerprint, all three raw receipts, source hashes,
Arrow schemas, row counts and exact history/link identifier parameters directly,
without importing WRDS. The SEC V2 provider also uses the independent helpers.
The existing architecture guard is unchanged.

**Current implementation counts: BLOCKER=0, HIGH=0, MEDIUM=0, LOW=0.**

Independent repaired-revision checks:

```text
pytest -q: 294 passed in 10.46s
Ruff: passed
MyPy: passed, 71 source files
isolated runtime import of identity.v2_resolution and providers.sec_v2:
  no src.data.providers.wrds, wrds, or sqlalchemy modules loaded
```

Unavailable/invalid submissions metadata now records the amendment count as null,
rather than asserting that zero amendments exist. The fixed 10002 slot remains
unchanged. This disposition permits code readiness to be distinguished from the
pending live confirmation evidence. It does not assert C2 completion, a five-issuer
result, DATA-02 acceptance or Gate A PASS. Live evidence remains pending final audit.

## Final C1 artifacts and documentation review

Production C1 artifacts are now present under
`artifacts/gate_a/identity_spine/v2_resolution/`. Independent read-only verification
recomputed all 24 rows from the pinned six-PERMNO inputs with the unchanged resolver;
the complete rows, frozen order and four fixed timestamps match exactly. Every row
carries the authoritative selection SHA-256. The C1 Parquet hash, config hash,
implementation hash, SEC request-roster hash and roster-to-result binding all match.
The roster contains exactly eight eligible observations for the three CIKs listed
above, with no ambiguous/unresolved CIK expansion. All four observations for 10002
remain present and unresolved. Future-history perturbations are nonvacuous for 18
observations and future-link perturbations for six.

The resolution document lists every observation and explicitly describes the
nonrandom semantic-validation cohort and unassessed amendment slot. Protocol,
decision-register and JSON status updates consistently preserve FROZEN_6,
COMPLETE CIK-link extraction, PROHIBITED resampling, DATA-02 IN PROGRESS and
Gate A BLOCKED. The selected JSON/fingerprint and original resolver/parser files
remain unchanged. No raw WRDS/SEC data are tracked by Git.

Final independent checks after adding the isolated runtime-import regression:

```text
pytest -q: 295 passed in 10.65s
Ruff: passed
MyPy: passed, 71 source files
git diff --check: passed
```

**Final implementation/C1 review counts: BLOCKER=0, HIGH=0, MEDIUM=0, LOW=0.**

**C2 has not started.** No V2 raw SEC source directory, submissions response or SGML
header is present. The implementation agent reports that the process lacks a genuine
SEC_USER_AGENT and has requested contact configuration from the owner. This is a
local execution prerequisite, not an observed SEC failure and not a negative result
from the cohort. C2 confirmation counts and the V1+V2 issuer-count requirement remain
**[TODO: 待实验结果]**. The final zero review counts apply to implementation and C1
evidence only; they do not certify unexecuted C2, ticket acceptance or research approval.
