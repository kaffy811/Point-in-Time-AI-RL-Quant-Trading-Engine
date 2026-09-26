# DATA-02 Phase B1/B2

Phase A is frozen and accepted. B1 is complete. B2 is **PARTIAL: archive access and
acceptance-time conflict remain unresolved**. DATA-02 is NOT PASS; Gate A is BLOCKED.

## B1 — all 266 unresolved observations accounted for

| Mutually exclusive reason | Count |
|---|---:|
| NO_CRSP_CUSIP_ASOF | 23 |
| NO_WRDS_LINK_FOR_CUSIP | 70 |
| ONLY_UNVALIDATED_WRDS_LINK | 159 |
| FIRST_EVIDENCE_AFTER_ASOF | 12 |
| FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC | 2 |
| CUSIP_MATCH_CLASS_MISMATCH | 0 |
| MULTIPLE_SECURITY_HISTORY_ROWS | 0 |
| FIRST_EVIDENCE_DATE_MISSING | 0 |
| OTHER | 0 |

The tracked reason report/count JSON contains real PERMNO/date examples and aggregate
link counts. Licensed detailed rows remain in ignored Parquet. A zero category has no
invented example. The diagnostic hierarchy is explicit, exhaustive and disjoint.
Future links explain failure retrospectively; they do not become historical features
or change a resolution. Phase A source, raw fixture and result hashes are checked before
both audits; accepted Phase A outputs are never rewritten.

## B2 — bounded, authorized SEC evidence only

Only CIKs 0001505611 and 0001556266 were queried. Two SEC submissions metadata responses
were saved. Deterministic accession selection: at most three records on each WRDS first
filing-evidence date, plus the latest earlier issuer 10-K/10-Q/8-K (including amendments).
In this corpus that selects four accession index pages; no filing bodies/facts were
retrieved. No new WRDS query or unauthorized issuer query was made. SEC responses,
receipts, failures and fixture manifest remain under the ignored SEC raw directory.
The client enforces a CIK/URL allowlist, byte/request caps, pacing, redirect checks,
content-hashed cache reads, and does not retain User-Agent contact information.

| CIK | Selected accession | Finding |
|---|---|---|
| 0001505611 | 0001019432-11-000009 | SC 13G/A index remains HTTP 503 after bounded retry |
| 0001505611 | 0001013762-11-002352 | Prior 10-Q index remains HTTP 503 after bounded retry |
| 0001556266 | 0001213900-15-004248 | Actual index lists authorized CIK as Subject, not filer; fail closed |
| 0001556266 | 0001213900-15-004052 | Prior 10-Q filer CIK matches, but acceptance-time source interpretation conflicts |

For the prior 10-Q the submissions API says `2015-05-20T15:35:09.000Z`, whereas the
index displays `2015-05-20 15:35:09` without an offset. They cannot both denote the same
instant if the index is interpreted in Eastern time. The existing P1-02 convention
covers complete-submission SGML headers, not an unapproved override of explicit API
UTC using HTML index text. Neither raw value was changed. Final confirmation stays
pending and the source-precedence decision is recorded OPEN. Although all current
later observations are after either plausible instant, this does not establish an
approved canonical acceptance timestamp.

A submissions list may include ownership filings with the queried CIK as subject;
it is not sufficient proof of filer identity. No new extraction was made for the
unapproved filed-by CIK encountered inside the authorized accession index.

Final SEC-confirmed observations: **0**. Unique SEC-confirmed issuers: **0**.
Remaining ambiguous observations: **9**. The original five-issuer validation requirement
is **not satisfied**. Eight preliminary candidates and 266 unresolved observations stay
in their Phase A states. No ambiguous candidate was selected or fetched.

## Reproduce and verify

```sh
uv run --frozen --extra wrds python -m src.data.identity.phase_b --config configs/gate_a_data_02_phase_b.json
uv run --frozen --extra wrds pytest tests/unit/data/identity/test_phase_b.py tests/unit/data/test_sec_identity_provider.py -q
uv run --frozen --extra wrds pytest -q
uv run --frozen --extra wrds ruff check .
uv run --frozen --extra wrds mypy src
```

The audit command is offline and requires the real local ignored fixtures. Network
acquisition is isolated in `src.data.providers.sec_identity`; when a further bounded
retry is appropriate, it can be invoked separately with `SEC_USER_AGENT` set locally:

```sh
uv run --frozen --extra wrds python -m src.data.providers.sec_identity --config configs/gate_a_data_02_phase_b.json --max-requests 4
```

No additional retries or extractions are scheduled automatically. Metadata receipts
are bound by exact path/URL/hash and parsing uses the already-verified bytes. Raw
identity evidence is never manufactured in tests. Transport tests mock HTTP; local
negative tests perturb real evidence in temporary directories and never publish it as
actual confirmation. Real-fixture tests skip when licensed/local evidence is absent.

## Remaining decisions

See `gate_a_data_02_fixture_protocol_v2.md`: proposal only, no extra WRDS/SEC extraction
performed. Complete-submission header evidence/source precedence needs owner approval
before dependent timestamp handling. Current SEC access failures and role mismatch
must remain visible. Source references: [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC access guidance](https://www.sec.gov/about/developer-resources), and the exact
accession URLs recorded in the confirmation manifest. No models, IC/RankIC, returns or
portfolio results were computed.


Independent re-review closed both initial HIGH findings (unverified archive-receipt
path and unapproved timestamp precedence). Current BLOCKER/HIGH/MEDIUM/LOW are all zero;
see `docs/reviews/gate_a_data_02_phase_b_review.md`. Reviewer independently verified ten
new targeted tests, 216 full-suite tests, Ruff and MyPy (63 source files), byte-identical
B audit reconstruction and unchanged frozen Phase A artifacts. This accepts engineering
checks only; the missing/conflicting SEC evidence and research decision remain open.
