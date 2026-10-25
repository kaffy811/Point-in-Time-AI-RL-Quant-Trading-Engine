# DATA-02 V2 selection/acquisition — independent review

Review date: 2026-09-25. Reviewer: independent review agent. Scope: frozen V2 config, `src/data/providers/wrds/fixture_v2.py` and mocked acquisition tests. No live WRDS connection, authentication, candidate/link outcome inspection or data extraction was performed by the reviewer. This report concerns code readiness; real execution/evidence remains pending.

## Initial review observations

The selection boundary is correctly placed before link acquisition: a bounded metadata-only CRSP/membership catalog feeds deterministic selection, then an exclusive-create freeze manifest is written before querying the selected history or WRDS CIK links. Candidate order and slot order are explicit; six distinct identifiers exclude the prior five. No returns, SEC/CIK match, validated code, resolution status or successful outcome enters selection. The amendment slot is an inspection after freeze, and the combined-change slot is only a descriptive proxy; neither asserts an actual amendment/reorganization.

Caps are finite: 60 catalog identifiers, six selected securities, 500 history rows (501-row overflow sentinel), at most 120 extracted CUSIP/CUSIP9 values, 200 links (201-row overflow sentinel). Overflow rejects rather than truncates or resamples. Existing raw directory/freeze manifests are not overwritten; failures preserve any frozen sample. Retry/recovery cannot silently choose replacements. The catalog is bounded in output, although computing metadata may scan provider history for those candidates; no market or full membership series is downloaded.

Raw results use authoritative Arrow schema when provided by the connector. Query parameters, query/schema/content hashes and retrieval times are saved; Parquet files are read-only. The provider layer alone opens the interactive connector, and the public command suppresses raw upstream errors. Licensed outputs remain in the ignored raw directory; the reviewable selection manifest contains the frozen metadata-selection decision.

Two implementation-readiness issues were reported during review: strict MyPy needed an annotation for the selected-record list; and several protocol fields were not checked (`protocol`, `candidate_order`, `as_of_dates`, `signal_time`), allowing the manifest to claim a config different from the fixed selection/sampling contract. The type annotation was repaired. Final disposition/verification will be recorded below once the config consistency patch is checked.

## Evidence limitation

Mock tests exercise deterministic selection, unrelated-field invariance, fallbacks, freeze-before-link ordering, refusal to rerun and overflow preservation. They do not prove real table/schema access or category coverage. Every selected security must subsequently be reported, including unresolved/ambiguous/unsuitable outcomes, without replacement. Actual amendment coverage is not guaranteed by metadata-only selection. No CCM or fixture expansion is implemented or approved by this review. DATA-02 is not passed; Gate A remains BLOCKED.


## Final independent disposition

**BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0** for the reviewed pre-execution implementation. Both initial readiness issues are closed: the selected-record list has an explicit type, and all four previously unchecked protocol fields now reject drift before any query. Four negative regression cases verify zero provider calls when those fields change. Source manifests additionally name provider/source tables. The decision register and protocol documentation correctly supersede the earlier no-V2 authorization and three-slot proposal.

Independent final verification:

```text
.venv/bin/pytest tests/unit/data/test_wrds_fixture_v2.py -q: 8 passed in 0.47s
.venv/bin/pytest -q: 235 passed in 12.99s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 66 source files
```

This is code/selection-protocol readiness only. Exactly six real securities have not yet been selected or claimed by this review. Actual V2 candidate metadata, membership column/schema compatibility and entitlement for this specific aggregate query remain unverified at this stage. No real V2 candidate/link outcomes were accessed by the reviewer. The user must complete local interactive authentication; any failed/partial acquisition must retain the frozen sample and must not trigger outcome-based replacement. Real execution and all-six outcome reporting require subsequent evidence review. Gate A remains BLOCKED.
