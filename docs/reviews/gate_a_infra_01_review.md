# GATE-A-INFRA-01 — Independent implementation review

Review date: 2026-09-25. Reviewer: independent review agent, separate from the implementation agent. Scope: WRDS provider package, mock tests, dependency/lockfile integration, CLI, CI, Git exclusions and documentation. No live WRDS connection, authentication or licensed download was performed. No implementation files were modified by this reviewer.

## Initial disposition (superseded by re-review below)

**CHANGES REQUIRED: BLOCKER = 0, HIGH = 1, MEDIUM = 0, LOW = 0.** Counts concern implementation findings; repository provenance remains a separate unresolved prerequisite. INFRA-01 does not qualify for Conditional PASS on this revision. This review does not approve research assumptions or declare Gate A PASS. DATA-02 must not start until the owner's prerequisites are satisfied.

## Initial HIGH (closed by re-review) — SQL conversion loses native dates and decimals before export

Location: `src/data/providers/wrds/connection.py:65–66`; downstream failure at `src/data/providers/wrds/extract.py:42–47`.

`Connector.query()` calls WRDS `raw_sql` with `coerce_float=False` and `dtype_backend="pyarrow"`. The installed/pinned WRDS 3.4.0 delegates to pandas 2.2.3 `read_sql_query`. That SQL conversion converts Python `datetime.date` and `decimal.Decimal` values from the driver into Arrow strings. Avoiding float coercion alone does not preserve their native types.

Reproduced offline through the real WRDS `raw_sql` and pandas SQL conversion, with a mocked DB-API cursor returning `(date(2020, 1, 2), Decimal("1.123456789"))`:

```text
pandas 2.2.3
{'date': string[pyarrow], 'amount': string[pyarrow]}
[{'date': '2020-01-02', 'amount': '1.123456789'}]
```

Consequences: an actual SQL DATE selected as `date_column` is rejected by the export's native-date check, so the documented bounded market extraction cannot complete on normal DATE results. With no date filter, historical DATE and NUMERIC columns silently publish as strings, contradicting the native Parquet contract. Empty and all-null columns also need explicit source schema handling, rather than guessing types from values.

The existing native/decimal tests replace `raw_sql` with a manually constructed DataFrame. They therefore bypass the conversion responsible for the fault and cannot establish correctness of the live ingestion path.

Required fix: preserve DB-native types through acquisition and Arrow conversion, including integer nullability/precision, DATE, TIMESTAMP, NUMERIC and leading-zero text identifiers. Use authoritative source column metadata for empty/all-null columns where value inference cannot recover the SQL type. Add offline regression tests at the DB-API/real WRDS conversion boundary, plus end-to-end export assertions for native date coverage and decimal values. Do not simply parse strings by guessed column names or enable float coercion.

## Repository/worktree prerequisite — unresolved independently of code counts

Commands were run from `/Users/kaffy/Documents/RL Engine`:

```text
pwd: /Users/kaffy/Documents/RL Engine
git rev-parse --show-toplevel: /Users/kaffy/Documents/RL Engine
git branch --show-current: phase1/pit-feature-store
git status --short: all project content untracked
git ls-files | head -50: no output
```

The project files exist and Git recognizes this directory. The parent investigation reports a real `.git` directory and an unborn branch with no commits, rather than a normal committed isolated worktree. These facts do not prove this is the owner's intended repository or explain the missing historical baseline. An ordinary reviewer-ready baseline diff is unavailable. Confirmation of the intended repository, or relocation/restoration to the correct baseline followed by full verification, is still required. No commits, staging, repository initialization or relocation were performed by this reviewer.

## Verified strengths and limits

- Allowlisted tables; validated/quoted SQL identifiers; bound value parameters; explicit columns; at most ten identities; cap-plus-one overflow rejection; deterministic projected-column ordering.
- Exclusive version-directory reservation and no overwrite of successful or failed versions; Parquet content hashes, schema hashes, parameter-inclusive query hashes and UTC retrieval provenance.
- Interactive, memory-only authentication wrapper avoids WRDS credential-file helpers. SQL echo disabled; public error messages sanitized. Read-only transactions and connection/statement timeouts configured. Transient retry is bounded and cleanup is attempted per connection.
- Current downstream research modules do not import the live WRDS provider. CLI planning is offline. CI installs the locked WRDS extra; raw WRDS paths and licensed identity Parquet paths are excluded from Git.
- Read-only file permissions are application-level immutability, not tamper-proof storage, as documented. Consumers still need to verify COMPLETE manifests and hashes. No live authentication, entitlement or database result schema was certified by this review.
- Research Owner's DATA-01 PASS decision is accepted as the governing status. Older local evidence documents may require explicit supersession; their historical content should not be fabricated or silently rewritten as a new experiment.

## Verification

```text
.venv/bin/pytest tests/unit/data/wrds -q: 29 passed
.venv/bin/pytest -q: 183 passed in 10.71s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 55 source files
Offline real-WRDS/pandas DB-API conversion reproduction: native date/decimal become strings
```

Tests and static checks passing do not override the reproduced HIGH finding. Re-review the native-type fix and new regressions before updating INFRA-01 disposition.


## Independent re-review — native-type fix

Reviewed the updated `connection.py`, new `native.py`, explicit safe Arrow conversion in `extract.py`, six new native-boundary test cases, adjusted lifecycle tests and updated connector documentation. The reviewer did not implement this fix.

**Current implementation counts: BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0.** The initial HIGH is closed. Repository/worktree provenance and owner confirmation remain pending independently; therefore this report does not yet grant overall INFRA-01 Conditional PASS or authorize DATA-02. Gate A remains BLOCKED.

The connection now executes parameterized SQL using the WRDS-owned SQLAlchemy connection's `exec_driver_sql`. It captures DB-API cursor metadata before fetching results, carries Python values in an object-typed frame, and writes through an explicit Arrow schema derived from PostgreSQL type OIDs and NUMERIC precision/scale. This removes the pandas SQL conversion that caused the reproduced DATE/NUMERIC fault. Nullable integers above 2**53 are also preserved exactly. The schema is available for empty and all-null result columns. Unknown OIDs and unconstrained NUMERIC fail closed; this documented supported-type boundary still needs to be checked against actual columns during user-operated extraction.

The new tests mock database rows and cursor metadata, but execute the production connector/native conversion/export path. They cover native dates, decimal precision/scale, nullable large integers, leading-zero text, empty/all-null schema preservation, timestamp/binary/float conversion and unsupported type rejection. No tests were represented as live WRDS results.

Independent verification on the repaired revision:

```text
.venv/bin/pytest tests/unit/data/wrds -q: 35 passed in 0.93s
.venv/bin/pytest -q: 189 passed in 10.57s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 56 source files
```

The initial reproduction and counts above are retained as review history, not current defects. No live WRDS authentication/download, identity-resolution implementation, repository staging or commit was performed by this reviewer.

The reviewer additionally verified all 13 SHA-256 file hashes in `artifacts/gate_a/infra_01/local_verification.json` against the reviewed files. This identifies the reviewed implementation snapshot without implying a committed Git baseline.
