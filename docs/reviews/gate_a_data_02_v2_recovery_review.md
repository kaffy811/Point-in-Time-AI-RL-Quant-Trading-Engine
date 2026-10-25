# DATA-02 V2 pre-execution recovery — independent review

Review date: 2026-10-25. Reviewer: independent review agent, separate from the
implementation agent. Scope: the recovery changes to
`src/data/providers/wrds/fixture_v2.py`, `v2_diagnostics.py`, shared INFRA-01 export
primitives in `extract.py`, their mocked regressions, and the V2 protocol/decision
documentation. Existing staged diagnostics changes were distinguished from the new
unstaged recovery changes.

**BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0.** No implementation finding remains
open in the reviewed recovery scope. This is an independent implementation review;
it is not research approval, evidence of ingestion, or a Gate A pass.

## Prerequisite and selection boundary

The missing prerequisite is
`artifacts/gate_a/identity_spine/v2_selection_manifest.json`: durable evidence of the
six selected PERMNOs and their pre-resolution CRSP-only metadata provenance. Its
companion fingerprint is
`artifacts/gate_a/identity_spine/v2_selection_manifest.sha256`. Initial acquisition
creates these artifacts; `--resume` requires the existing manifest. A missing
manifest and empty raw directory permit the owner-authorized initial selection,
while read-only `--diagnose` reports `INITIAL_SELECTION_READY_NOT_EXECUTED`.

The first provider query is the precommitted CRSP security-history/membership
aggregate. It uses only `crsp.stksecurityinfohist` and `crsp.dsp500list_v2`. The
unchanged numeric candidate order, six protocol slots, exclusions and explicit
fallback rule determine six distinct identifiers. CIK links, SEC accessions,
resolution outcomes, returns and performance do not enter this query or selection.

The catalog snapshot and receipt precede exclusive creation of the selection
manifest. The manifest file is flushed and synced, its content hash is persisted
exclusively as the fingerprint, and both files and their directory are synced
before any selected security-history or CIK-link query. A fingerprint or sync
failure stops subsequent provider work. A valid manifest found on retry is reused
automatically, even without `--resume`; `choose` and catalog acquisition do not run
again. Missing or incompatible provenance fails closed rather than selecting a
replacement sample.

## Filesystem and connector behavior

- An existing empty V2 raw directory is accepted. A raw destination that is a
  file, a symlink, an orphan fingerprint, or an incompatible existing manifest is
  rejected before provider querying.
- A nonempty raw directory without a compatible frozen manifest is preserved and
  rejected. Existing output files are never replaced: compatible receipted cache
  files are verified and reused; incomplete or conflicting files fail closed.
- Retry verifies config, catalog query/content/schema/count/path provenance, six
  distinct nonexcluded identifiers and protocol slot order. A matching completion
  manifest is reused without mutation.
- V2 uses the existing INFRA-01 `Connector` and its bounded retry/timeout behavior.
  Native Arrow conversion, caps, exclusive Parquet/JSON writes and hashes are
  shared through `extract.py`; no additional WRDS connection path is introduced.
- The recovery diff does not modify the Phase A resolver, `validated={2,3}`
  eligibility, CUSIP priority, temporal evidence, or FILER/SUBJECT handling.

## Independent offline verification

```text
.venv/bin/pytest -q
266 passed in 10.48s
.venv/bin/ruff check .
All checks passed!
.venv/bin/mypy src
Success: no issues found in 68 source files
```

The added regressions cover empty-directory acceptance, destination collisions,
unmanifested nonempty directory preservation, incompatible frozen evidence,
fingerprint-write failure, interrupted sync, repeated provider failure after
freeze, exact automatic/explicit reuse, and pre-authentication/offline CLI paths.
Provider mocks assert that the manifest and matching fingerprint already exist
when selected history or links are requested. Existing tests also verify caps,
determinism, field invariance, fallback behavior and immutable cache reuse.

Final documentation/status review confirmed that the protocol, decision register,
failure diagnosis and status artifacts distinguish implementation readiness from
unexecuted live selection, identify both the catalog input and durable selection
output, retain zero frozen identifiers and preserve Gate A BLOCKED. The protocol
artifact's config and provider implementation hashes match the reviewed files.
`git diff --check` also passed. Ruff and MyPy were rerun after these documentation
updates and passed again.

No live WRDS/SEC/network request, authentication, live V2 selection, real CIK-link
inspection or resolution-outcome inspection was performed for this review. Mock
results are software verification only; real catalog schema compatibility,
coverage and subsequent outcomes remain unverified. No real selection manifest
was created by this review. The one initial selection authorization is unconsumed
by the review. DATA-02 remains IN PROGRESS and Gate A remains BLOCKED.
