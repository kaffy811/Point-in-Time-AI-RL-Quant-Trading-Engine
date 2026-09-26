# DATA-02 bounded SGML confirmation — independent review

Review date: 2026-09-25. Reviewer: independent review agent, separate from the implementation agent. Scope: the four owner-authorized raw-header retrieval cases, offline SGML parser, confirmation overlay, config, tests and generated evidence. No network requests, additional WRDS extraction or implementation edits were performed by this reviewer.

## Disposition

**BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0** in the final reviewed implementation. The raw-SGML-first interpretation follows the latest Research Owner authorization supplied for this task; the earlier API/index-only policy conflict is not silently treated as an approval. This review certifies neither five suitable issuers nor overall DATA-02 completion. Gate A remains BLOCKED.

## Evidence reviewed

The four actual raw headers are bound to fixed CIK/accession URLs, independent receipts, exact saved paths and SHA-256 content hashes. Offline parsing uses the verified bytes. Raw source values remain preserved: SGML ACCEPTANCE-DATETIME is interpreted in America/New_York under the approved policy and converted to UTC; the old structured API values are not relabeled.

Only explicit COMPANY DATA identifiers within top-level FILER or FILED BY sections qualify as filers. SUBJECT COMPANY is a separate role. Distinct multiple filers produce AMBIGUOUS; an arbitrary first filer is never selected. During review, a malformed same-role block containing repeated COMPANY DATA sections was identified as a potential silent omission; the author added explicit rejection and a regression test before final verification. Duplicate/missing header identity fields, incorrect accessions, incomplete headers and ambiguous/nonexistent local timestamps fail closed.

A unique matching filer is usable only when its acceptance instant is no later than the observation. Same-day CUSIP-evidence observations are restricted to the designated first-evidence accession and filing date; an older 10-Q cannot bypass that requirement. Earlier observations can independently use the matching issuer filing. All per-accession outcomes remain in the row-level audit.

Acquisition is limited to the four fixed previously authorized cases, at most three attempts per case and 65,536 bytes per response, with fixed retry backoff. Only the exact authorized submission URL is allowed; alternate-source redirects are rejected. The provider stores the exact prefix through the closing header; a bounded read chunk may receive some following bytes, but filing bodies are not saved as evidence. Cached receipts are checked before reuse. No fixture-protocol-v2 extraction is executed.

## Independently checked results

| Overlay status | Observations |
|---|---:|
| SEC_CONFIRMED | 8 |
| ROLE_CONFLICT | 2 |
| NOT_YET_AVAILABLE | 0 |
| PENDING_SOURCE_UNAVAILABLE | 0 |
| AMBIGUOUS | 0 |

The overlay confirms two distinct issuers, not five. Both first-evidence ownership filings identify the candidate only as SUBJECT COMPANY, with another CIK as FILED BY; those two same-day observations remain unconfirmed. The two prior 10-Q headers identify the corresponding candidates as FILER. The other 264 unresolved and nine ambiguous Phase A observations remain unchanged.

The reviewer independently regenerated all three SGML artifacts in a temporary root and obtained byte-identical outputs. Final implementation hashes were checked against the generated SGML manifest after the parser hardening. Frozen Phase A implementation/result checks execute through `accepted_inputs`; its historical resolutions remain unmodified. Raw SEC headers and licensed overlay Parquet are Git-ignored, and no raw/Parquet files appear in the tracked-file inventory.

## Verification

```text
.venv/bin/pytest tests/unit/data/identity/test_sgml_audit.py -q: 11 passed
.venv/bin/pytest -q: 227 passed in 10.40s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 65 source files
```

Synthetic parser/transport cases are explicitly labeled and do not substitute for the four actual header fixtures. Tests requiring local real inputs skip when those inputs are unavailable; CI alone cannot certify licensed/local evidence coverage. The review does not authorize additional issuers, WRDS queries, cohort selection or unexecuted fixture-protocol proposals.

Final follow-up: the exact-accession secondary source is independently bound to its hash/path/CIK URL and raw submissions accession. All four unchanged API timestamp values and the 14,400-second SGML-minus-API deltas were checked in the final generated manifest. Ambiguity now explicitly takes precedence over another accession confirmation. Tests, static checks and byte-identical regeneration above were rerun on this final revision. The appended Research Owner decision and SGML documentation explicitly supersede the earlier OPEN source-priority status without executing protocol v2.
