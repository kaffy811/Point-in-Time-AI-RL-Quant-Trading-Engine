# V2 failure diagnosis — no resampling

Research Owner independently verified WRDS authentication, `crsp` access and
`wrdssec_common` access as PASS. This incident is **not classified as an authentication
or entitlement failure**.

## Preserved state inspected before changes

- `data/raw/wrds/gate_a/data_02_v2/` exists and is empty.
- `artifacts/gate_a/identity_spine/v2_selection_manifest.json` does not exist.
- Frozen PERMNO count: **0**. No six-security roster can be recovered locally.
- No existing frozen/raw/partial V2 artifact was removed or overwritten.

## Exact observations and limits

| Diagnostic action | Stage | Exception | Sanitized message |
|---|---|---|---|
| Offline preflight, requiring existing frozen selection | FREEZE_SELECTION | FileNotFoundError | Required local artifact is missing. |
| Offline replay of the old exclusive directory-reservation line only | WRITE_RAW_FIXTURE | FileExistsError | Destination already exists; overwrite refused. |

Both actions made zero WRDS requests and zero selection calls. The replay asserted
that the directory already existed and was empty, then reproduced the old `mkdir`
collision without modifying it. These are **current reproducible blockers**, not
recovered exceptions from the first historical failure.

The old implementation discarded the first underlying exception. An empty reserved
directory alone cannot distinguish a catalog-query failure, native-schema conversion
failure, or another interruption before any successful file write. The exact original
stage and exception are therefore **UNKNOWN / NOT RECOVERABLE FROM RETAINED EVIDENCE**.
No schema, authentication or entitlement root cause is invented.

Append-only machine-readable records are under `v2_diagnostics/`. Each includes stage,
operation/query identifier, source tables, sanitized exception class/message (and
allowlisted SQLSTATE when available), frozen state/count, existing known artifacts,
and paths successfully written during that attempt.

## Implementation and safe recovery

The connector retains sanitized underlying exception class/SQLSTATE and distinguishes
connection, query execution and native-schema conversion. No arbitrary driver exception
text, query parameters, DSN, credentials or Duo data are logged. Even an upstream
attribute named `safe_diagnostic` is revalidated against explicit field/value allowlists.
Unknown exception messages are withheld; exact trusted validation messages remain useful.

V2 tracks CONNECT_WRDS, FREEZE_SELECTION, FETCH_SECURITY_HISTORY, FETCH_MEMBERSHIP,
FETCH_CIK_LINKS, VALIDATE_SCHEMA, WRITE_RAW_FIXTURE and WRITE_MANIFEST. The existing
catalog SQL combines history aggregates and membership evidence; its query stage is
FETCH_MEMBERSHIP with **both** source tables identified. SQL, selection policy and
resolver semantics are unchanged.

`--resume` validates and reuses the existing six-security manifest and source hashes.
It never reruns selection/catalog acquisition. Complete cached files are verified and
reused; unreceipted partial files or conflicting manifests stop the run without overwrite.
Diagnostics receive new unique filenames; no previous diagnostic is replaced.

Because this workspace has no frozen selection, **no live V2 retry was performed**.
The missing prerequisite is the durable `artifacts/gate_a/identity_spine/
v2_selection_manifest.json`, which records the six-PERMNO selection and selection
artifact fingerprint before CIK-link extraction. The current owner decision permits
one initial selection when the raw directory is empty; a nonempty directory without
that manifest still fails closed. A future valid manifest is resumed exactly.

Safe offline verification:

```bash
.venv/bin/python -m src.data.providers.wrds.fixture_v2 --diagnose
```

At the diagnostics checkpoint this exited nonzero with FREEZE_SELECTION /
FileNotFoundError. The recovery revision now recognizes the authorized empty initial
state and reports `INITIAL_SELECTION_READY_NOT_EXECUTED` without making queries or
writing a freeze. `--resume` still fails closed until an authentic frozen manifest and
its original catalog evidence exist. These new semantics do not alter the retained
historical diagnostic reports.

The prerequisite is created from the bounded CRSP-only `selection_metadata.parquet`
and its receipt via the INFRA-01 connector. The durable six-PERMNO JSON manifest is
then flushed/fsynced and SHA-256 fingerprinted before selected history or CIK links.
Retry verifies and reuses its exact identifiers and bytes, including when the first
attempt failed after JSON publication but before fingerprint publication. Complete
cached targets are verified, never overwritten; conflicting/partial targets fail
closed. An existing empty raw directory is allowed; nonempty raw output without a
compatible manifest and an existing file at the raw-directory path fail closed.

No live V2 selection, retry, CIK-link or SEC request was performed during this recovery.
Review for the recovery revision is separate from the historical diagnostics review:
`docs/reviews/gate_a_data_02_v2_recovery_review.md`.
DATA-02 IN PROGRESS; Gate A BLOCKED.
