# DATA-02 V2 failure diagnostics/resume — independent review

Review date: 2026-09-25. Scope: sanitized exception handling, connector stage propagation, offline V2 diagnostics, frozen-sample resume and new mock regressions. Reviewer is separate from the implementation agent. No live WRDS access, authentication, selection query or real link-outcome inspection was performed by this reviewer.

## Initial disposition (superseded by repaired-revision review)

**CHANGES REQUIRED: BLOCKER = 0, HIGH = 1, MEDIUM = 0, LOW = 0.**

### HIGH — an exception attribute bypasses sanitization

`sanitized_exception` initially returns `dict(exc.safe_diagnostic)` whenever any exception has that attribute. Neither exception type, keys nor values are validated. `Diagnostic.failure` serializes the returned fields, and `Connector.query` can also interpolate the unchecked message into ProviderError.

Offline reproduction with a generated secret sentinel: attach a dictionary containing `sanitized_exception_message=<sentinel>` and `dsn=<sentinel>` to an ordinary RuntimeError's `safe_diagnostic` attribute, then call `Diagnostic.failure`. The supposedly sanitized JSON persisted both the secret and the unexpected `dsn` field. No actual credential was used or printed in this review.

Required fix: revalidate the retained diagnostic structure against explicit safe keys and allowed values, including the message, exception class, SQLSTATE and provider stage. Unknown fields/values must be dropped or replaced with fixed text. A trustworthy-looking attribute name must never bypass the serialization boundary. Add a regression exercising both the diagnostic-file and Connector wrapping paths with generated secret sentinels.

## Scope and behavior checked

- Offline CLI preflight requires an existing frozen manifest before interactive factory construction. `--diagnose` performs no network request. With no freeze, the flow must stop rather than choose six securities again.
- Explicit resume uses persisted selected identifiers and cached query/content/schema/count provenance; it does not call `choose` or query a replacement catalog. Existing partial unreceipted Parquet is preserved and rejected. New files and completion manifests use exclusive creation; differing existing completion data are not overwritten.
- Diagnostics use fixed operation identifiers, stage labels, known relative paths, frozen counts and fresh append-only UUID filenames. Connection versus query/schema stages are retained without reconstructing driver exception text.
- The earlier successful health/CRSP/WRDS-SEC checks remain valid evidence. A current missing freeze is a local precondition failure, not a demonstrated authentication failure. An existing raw directory can explain a later old-command FileExistsError, but does not reconstruct the unknown original failure.

Initial independent targeted verification: 23 diagnostics/V2 mocked tests passed. These tests did not catch the attribute-bypass issue above. Final disposition and full verification will be appended after repair.


## Final independent re-review

**Current implementation counts: BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0.** The original HIGH is closed. Nested diagnostic dictionaries now undergo explicit key/value allowlisting rather than being trusted: unknown messages/classes/states/stages are replaced or omitted, and arbitrary extra fields are dropped. New generated-sentinel regressions cover ordinary upstream exceptions with a forged attribute and injected ProviderError details through both Diagnostic serialization and Connector wrapping.

Independent final checks:

```text
.venv/bin/pytest tests/unit/data/wrds tests/unit/data/test_wrds_fixture_v2.py -q
60 passed in 1.07s
.venv/bin/pytest -q: 252 passed in 10.98s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 68 source files
```

Mocked resume checks preserve exact frozen/partial bytes, prohibit `choose`, reuse cached data without querying, and reject unreceipted partial files without replacement. Missing-freeze preflight makes zero provider calls. Appended diagnostics preserve earlier files and report successful writes separately from failed operations.

The reviewer inspected the two existing sanitized offline reports only, not real link outcomes. One records `REQUIRE_EXISTING_FROZEN_SELECTION` at FREEZE_SELECTION with FileNotFoundError; the other records `OFFLINE_REPLAY_OLD_DIRECTORY_RESERVATION` at WRITE_RAW_FIXTURE with FileExistsError. Both show an existing empty raw directory, zero frozen identifiers, no written data artifacts and `historical_failure_recovered=false`. These are distinct current reproducible local failures; neither identifies the original unlogged failure or contradicts successful authentication/table health evidence.

The present workspace therefore does not meet the resume prerequisite. No live retry, new selection, artifact removal or directory overwrite was performed by this reviewer or authorized by this review. Restoring/authorizing an appropriate frozen-state recovery is a Research Owner process dependency. Code review passing does not imply V2 ingestion completion or Gate A PASS; Gate A remains BLOCKED.


## Owner-corrected initial-selection review — 2026-09-26

The latest Research Owner decision supersedes the preceding no-initial-selection process restriction: the observed state is **V2_PRE_EXECUTION_BLOCKED**, with an empty raw directory and no frozen sample/outcomes. Exactly one initial metadata-only selection is authorized. The earlier review's resume-only conclusion remains historical context, not the current authorization.

Independent review of the correction found **BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0**. Initial acquisition permits an existing empty raw directory; a nonempty directory without frozen selection evidence fails before any provider query and preserves its contents. An existing freeze still prohibits initial reselection; explicit resume reuses the frozen identifiers. The durable six-PERMNO selection manifest is written before CIK-link acquisition, and no SEC access is introduced. Config, selection algorithm and downstream identity semantics are unchanged.

The offline diagnostic now names `artifacts/gate_a/identity_spine/v2_selection_manifest.json` and its role as durable six-PERMNO selection evidence using an exact allowlisted message. The reviewed append-only report records zero frozen identifiers and no recovered historical failure. This is not a new authentication/entitlement failure; successful health evidence remains intact.

Independent verification of the corrected revision:

```text
.venv/bin/pytest tests/unit/data/wrds tests/unit/data/test_wrds_fixture_v2.py -q
62 passed in 0.50s
.venv/bin/pytest -q: 254 passed in 6.44s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 68 source files
```

The added mocked tests cover empty-directory initial acquisition and preservation/rejection of nonempty unmanifested state. The reviewer ran no live WRDS command, made no real selection, inspected no real link outcomes and did not change implementation or raw artifacts. This is implementation readiness, not proof that the authorized initial run has occurred. DATA-02 remains IN PROGRESS; Gate A remains BLOCKED.
