# GATE-A-DATA-02 Phase B1/B2 — independent review

Review date: 2026-09-25. Reviewer: independent review agent, separate from the implementation agent. Scope: administrative B1 failure classification, B2 SEC archive confirmation and bounded metadata acquisition. No live network request or additional WRDS extraction was performed by this reviewer. Phase A implementation and result files were not edited.

## Initial disposition (superseded by re-review below)

**CHANGES REQUIRED: BLOCKER = 0, HIGH = 2, MEDIUM = 0, LOW = 0.** These counts describe the initial reviewed revision. No DATA-02 or Gate A PASS is declared.

### HIGH B2-01 — archive verification reads an unverified receipt path

In `run_b2`, the raw-source inventory is hash/path checked, but a selected accession's `archive_receipt` is checked only for SHA-256 membership in that inventory. The verifier then opens the independently supplied `archive_receipt.path`, without verifying that path or its bytes against the inventory entry.

Reproduced offline in a temporary copy of the real fixture corpus: the successfully retrieved prior 10-Q receipt path was changed to `../unverified.html`; that out-of-directory file contained the original HTML plus an added comment, and therefore had a different content hash. The original raw-source inventory, hashes and verified files were left unchanged. `run_b2` still reported five SEC-confirmed observations. Thus the manifest can attest one source while confirmation consumes different, unverified bytes.

Required fix: bind each selected receipt to its complete verified inventory entry (path, URL and hash), consume the already verified bytes, enforce archive URL/accession/CIK correspondence, and add a negative test for altered/outside receipt paths and mismatched bytes. Preserve raw evidence; do not merely recompute a hash for whichever replacement path is supplied.

### HIGH B2-02 — unresolved acceptance-source conflict becomes an approved instant

The actual prior 10-Q metadata has API acceptance `2015-05-20T15:35:09.000Z`; its archive index displays the same clock face without an explicit timezone. The implementation applies America/New_York to the index, records `api_archive_acceptance_instant_agrees=false`, and nevertheless emits `ARCHIVE_FILER_AND_METADATA_CONSISTENT`, a canonical acceptance instant, and five `SEC_CONFIRMED` observations.

P1-02's existing rule covers the complete-submission SGML acceptance header. It does not settle which source wins when an explicit API instant conflicts with a timezone interpretation of an HTML index. AGENTS.md requires research ambiguities to be recorded and dependent behavior to wait for the Research Owner. Retaining a discrepancy flag does not authorize a new precedence rule.

Required fix: record the disagreement and proposed interpretation in the research decision register; do not admit the conflicting evidence for acceptance-qualified confirmation until the owner resolves the source policy or qualifying authoritative evidence is supplied. Archive filer-CIK agreement can be reported separately as factual evidence. Do not relabel the API's Z suffix or claim that index timestamp precedence is already approved by P1-02.

The current five observations are later than either proposed instant, so this review does not assert those five dates are temporally impossible. The defect is certifying an unapproved canonical timestamp and implementing a general admission rule that can affect future boundary cases.

## Verified scope and strengths

B1 accounts for all 266 Phase A UNRESOLVED observations with one mutually exclusive administrative category: 23 missing CRSP identity, 70 missing related WRDS links, 159 only unvalidated links, 12 future first-evidence dates and two same-day SEC requirements. Zero-count categories are preserved rather than supplied with fabricated examples. Retrospective diagnostics are explicitly separated from historical resolver output.

The Phase A loader checks its frozen implementation hashes, raw fixture provenance and result hash, then reproduces every stored resolution. B2 does not select among the nine ambiguous observations. Same-day evidence requires an eligible filing on that first-evidence date, rather than bypassing the requirement with an older 10-Q.

The actual SC 13G archive correctly fails the target-filer check because the target CIK is a subject company, not its filer. Failed HTTP retrievals remain failures, and the provider permits only the two authorized CIKs and metadata/index paths. The five-issuer and category requirements remain explicitly unmet. No SEC fundamentals or filing facts were fetched or inferred by this review.

## Verification limits

This initial review includes static inspection and the offline receipt-path reproduction above. Implementation tests and documentation were still being completed; final suite counts will be recorded on re-review. The timestamp finding requires a fail-closed implementation or an explicit Research Owner policy decision, not a test-only change.


## Independent re-review — both initial HIGH findings closed

Reviewed the repaired `phase_b.py` and `sec_confirmation.py`, bounded provider CLI/config, new regression/transport tests, Phase B documentation and the unexecuted fixture-protocol-v2 proposal. **Current implementation counts: BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0.** This closes the implementation defects; it does not resolve the underlying SEC evidence or research decision dependencies.

B2-01 is closed: source files are read once, checked against the raw inventory hash and allowed directory, then cached in memory. Selected archive receipts must equal their verified source entries and their selected URL; verification parses the checked bytes. The regression reproduces the original out-of-directory substituted receipt and now rejects it. Raw-byte tampering is rejected as well.

B2-02 is closed by failing closed, not by approving either disputed timestamp. `verify_index` rejects the actual conflicting evidence with `ACCEPTANCE_TIME_SOURCE_CONFLICT_OWNER_DECISION_REQUIRED`. The research decision register explicitly leaves source precedence OPEN for the Research Owner. The explicit API timestamp is preserved. The final report now confirms **zero observations and zero issuers**; all eight preliminary candidates, 266 unresolved observations and nine ambiguous observations retain their Phase A status. The previous five-confirmation output is superseded and must not be cited as accepted evidence.

B1 remains exhaustive and disjoint: 23/70/159/12/2 in the five populated categories, totaling 266. No invented examples populate zero-count categories. The proposal for a new fixture protocol does not authorize or execute additional data extraction.

Independent verification on the repaired revision:

```text
.venv/bin/pytest tests/unit/data/identity/test_phase_b.py tests/unit/data/test_sec_identity_provider.py -q
10 passed in 0.69s
.venv/bin/pytest -q: 216 passed in 6.78s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 63 source files
```

The reviewer independently copied the real corpus into a temporary root and regenerated both audits: all six Phase B generated artifacts match the delivered bytes. The four frozen Phase A artifacts copied for the comparison remain unchanged, and `accepted_inputs` verifies the frozen implementation and source/result hashes. No live network request, raw fixture modification or Phase A implementation change was made by this reviewer.

Final review scope remains B1/B2 only. B2 is PARTIAL because archive availability, filer-role mismatch and acceptance-source conflict are unresolved; the original five-issuer requirement is not satisfied. DATA-02 is NOT PASS and Gate A remains BLOCKED. Green code review counts do not override those evidence limitations or the pending Research Owner decision.
