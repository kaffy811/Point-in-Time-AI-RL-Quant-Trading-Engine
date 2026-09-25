# GATE-A-INFRA-01 — WRDS Local Connector

Status: implemented for independent review; live authentication and entitlement verification
remain user-operated. No licensed samples were downloaded. No Gate A PASS is asserted.

## Boundary

`src/data/providers/wrds/` is the only live WRDS ingestion layer. Research consumers
must read immutable raw Parquet, then use separately reviewed canonical normalization
and PIT Store contracts. This ticket performs no identity resolution or date-interval
normalization, and does not certify raw historical records as PIT-safe.

Research Owner decision (2026-09-25): DATA-01 = PASS; INFRA-01 = IMPLEMENTED /
LOCALLY VERIFIED / INDEPENDENT REVIEW PENDING (initial status); Gate A = BLOCKED. DATA-02 scope
is now settled, but implementation is authorized only after independent review
has BLOCKER=0/HIGH=0 and the repository location is confirmed. See
`gate_a_infra_01_repository_check.md` and `research_decisions.md`.

## Install and verify

```sh
uv sync --frozen --extra wrds
uv run --frozen --extra wrds pytest tests/unit/data/wrds -q
uv run --frozen --extra wrds ruff check .
uv run --frozen --extra wrds mypy src
uv run --frozen --extra wrds pytest
```

WRDS is an optional ingestion dependency; CI installs the extra for mocked tests.
The lockfile pins the transitive environment. No test requires network or credentials.

## Local authentication

Run the following yourself in a local interactive terminal:

```sh
uv run --frozen --extra wrds wrds-ingest health
```

Enter credentials only in the terminal and complete any institution-required WRDS/Duo
approval. Never put credentials in chat, CLI arguments, JSON specs, environment files,
Git, logs or documentation. The password is obtained using `getpass`, held only in
process memory and never written to disk. This implementation does not automate Duo.
A noninteractive invocation fails before requesting credentials.

The pinned [WRDS client](https://github.com/wharton/wrds/blob/v3.4.0/wrds/sql.py)
owns the provider session. Its default `connect()` path can offer to save `.pgpass`, so this
wrapper initializes with `autoconnect=False` and supplies an explicit SQLAlchemy
connection. It does not call the client's credential-file helpers. The engine uses
TLS, read-only transactions, a 30-second connection timeout, and a 60-second statement
timeout; SQL echo is disabled and parameters are hidden. Public failures omit upstream
exception messages. Connection cleanup runs after every attempt. Only connection-class
SQLSTATEs, server restart states, invalidated connections, connection and timeout errors
are retried (up to three attempts, 1/2-second backoff); authentication, permission and SQL
errors fail immediately. Unknown driver failures are conservatively not retried.
`health` tests connectivity only, not entitlement to all six datasets.

## Bounded extraction

Create a credential-free JSON query spec. This example uses a synthetic PERMNO and must
be replaced with a provider-confirmed identifier and column names before live use:

```json
{
  "table": "crsp.dsf_v2",
  "columns": ["permno", "dlycaldt", "dlyopen"],
  "identity_column": "permno",
  "identities": [999999],
  "date_column": "dlycaldt",
  "start": "2020-01-01",
  "end": "2020-02-01",
  "max_rows": 1000
}
```

```sh
uv run --frozen --extra wrds wrds-ingest plan --spec /path/to/spec.json
uv run --frozen --extra wrds wrds-ingest extract --spec /path/to/spec.json --version sample-v1
```

`plan` is offline. Only these source tables are allowed: `crsp.dsf_v2`,
`crsp.dsp500list_v2`, `crsp.stksecurityinfohist`, `crsp.stkdistributions`,
`crsp.stkdelists`, and `wrdssec_common.wciklink_cusip`. A shared checked SQL template
requires explicit projected columns and 1–10 PERMNOs (CUSIPs for the SEC link table).
Identifiers are validated and quoted; values use bound parameters. No raw SQL CLI exists.
The hard cap is 10,000 rows. A cap-plus-one query detects overflow and fails without
publishing truncated Parquet. Projected columns define deterministic result ordering;
identical duplicate rows are preserved, not silently deduplicated.

Date filtering is optional for bounded security-history/link retrieval. When used it is
`[start, end)` on the explicitly supplied source column, not an identity-validity rule.
Omitting it retains all matching history subject to the row cap. In particular,
`cikdate1/cikdate2` must not be interpreted as full identity-validity endpoints.
No provider-specific column/date semantics are guessed or normalized here.

## Artifacts and reproducibility

Each successful extraction creates:

```text
data/raw/wrds/<schema_table>/<version>/part-00000.parquet
data/raw/wrds/<schema_table>/<version>/manifest.json
```

The manifest records provider, source table, version, exact SQL and parameters, query hash
(including parameters), SQL hash, UTC retrieval time, row count, Arrow schema/hash,
Parquet byte-content hash, observed date coverage and requested bounds, plus package
versions. Queries execute via the WRDS session's SQLAlchemy `exec_driver_sql`, preserving bound
parameters. The pandas `read_sql` / WRDS `raw_sql` conversion path is deliberately
excluded after independent review reproduced DATE/NUMERIC string conversion. Driver
rows become an object-typed frame, then Arrow with an explicit schema from PostgreSQL
cursor type OIDs and numeric precision/scale. Native Arrow/Parquet values are used
without CSV conversion or float coercion. Supported types include integer, float,
boolean, text, bytea, DATE, TIMESTAMP, TIMESTAMPTZ and constrained NUMERIC up to precision
76. Unsupported OIDs or unconstrained NUMERIC fail closed instead of guessing; source
schema compatibility remains an extraction-time check.
Nulls and leading-zero string identifiers remain intact. Coverage is null if no date
column is requested; empty/all-null dates have null extrema. Neither retrieval time nor
date coverage is a historical knowledge timestamp.

A version directory is reserved exclusively before querying. Existing versions, including
failed reservations, are never overwritten. A failed attempt may leave an incomplete
folder; consumers must require the COMPLETE manifest and verify hashes. Use a new version
after investigating a failure. Completed data and manifests are read-only files; this is
application-level write-once storage, not tamper-proof hardware. No automatic deletion or
replacement occurs. Source revisions may change subsequent extractions: reproducibility
comes from retaining and hashing the original snapshot, not assuming a live query never
changes. Raw WRDS files and licensed identity Parquet are Git-ignored.

## Review and evidence

Mocked tests cover all allowlisted tables, query bounds and injection protection, native
Parquet/null preservation, hashes, date coverage, empty exports, version collisions,
overflow rejection, retry/cleanup, sanitized failures, interactive authentication guards,
read-only connection configuration, offline CLI planning and the research import boundary.
Independent ticket review is complete (see final re-review below); repository confirmation
remains required. Live extraction: [TODO: 待实验结果].
No features, labels, training, identity-spine claims or performance results are produced.

Local verification completed: frozen-extra installation and CLI entry point succeeded;
Ruff passed; strict MyPy passed for all 55 source files; the full suite passed 182 tests.
One additional identifier/decimal preservation test was then added, and the final targeted
connector suite passed all 29 tests. No live health or entitlement claim is inferred.

Review inventory: new provider package (`query.py`, `connection.py`, `extract.py`, `cli.py`,
`sql/sample.sql`), mocked connector tests, this document; updates to `pyproject.toml`,
`uv.lock`, `.gitignore`, CI extra installation, and the research decision register.
The supplied workspace has no tracked files (`git ls-files` is empty); an ordinary
baseline diff is therefore unavailable. No existing files were staged or committed.


Independent review initially identified one HIGH in native SQL conversion. The fix
adds `native.py` and tests at the actual cursor-to-Parquet conversion boundary, including
empty/all-null columns, nullable integers above 2**53, dates, decimals, timestamps and
unsupported type rejection. Independent re-review closed the HIGH: current implementation counts are BLOCKER=0,
HIGH=0, MEDIUM=0, LOW=0. Reviewer independently verified 35 connector tests, 189 full-suite
tests, Ruff and strict MyPy (56 source files). See `reviews/gate_a_infra_01_review.md`.
Earlier 182/29 counts describe the pre-review revision. Repository owner confirmation
remains pending, so Conditional PASS has not been assigned and DATA-02 has not started.


Final Research Owner acceptance: **CONDITIONAL PASS / LOCAL VERIFIED**. Canonical
repository location confirmed; the initial local Git state was intentional. Independent
review BLOCKER=0/HIGH=0. The owner authorizes baseline commit, then DATA-02 branch/work.
Gate A remains BLOCKED.
