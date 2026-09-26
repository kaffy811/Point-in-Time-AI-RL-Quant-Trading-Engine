# Phase B2 — SEC accession confirmation

Only CIKs 0001505611 and 0001556266 were queried. Two bounded submissions
responses supplied exact-date accessions and one latest prior issuer filing each.
No filing bodies, facts, unrelated issuers, or additional WRDS data were downloaded.
Raw HTTP responses and retrieval failures remain in the ignored SEC directory.

| CIK | Accession | Form | Archive status | Confirmation |
|---|---|---|---|---|
| 0001505611 | 0001019432-11-000009 | SC 13G/A | SEC metadata HTTP 503 | ARCHIVE_UNAVAILABLE |
| 0001505611 | 0001013762-11-002352 | 10-Q | SEC metadata HTTP 503 | ARCHIVE_UNAVAILABLE |
| 0001556266 | 0001213900-15-004248 | SC 13G | RETRIEVED | ARCHIVE_FILER_CIK_MISMATCH_OR_AMBIGUOUS |
| 0001556266 | 0001213900-15-004052 | 10-Q | RETRIEVED | ACCEPTANCE_TIME_SOURCE_CONFLICT_OWNER_DECISION_REQUIRED |

Final SEC-confirmed observations: **0**.
Unique SEC-confirmed issuers: **0**.
Remaining ambiguous observations: **9**.
Original five-issuer validation requirement: **NOT SATISFIED**.

An entry in a CIK submissions list is insufficient to verify that CIK's filer
role in the archive (ownership filings may list a subject company). Archive
filer identity, accession, form, filing/report dates and primary document must match.
API/archive acceptance discrepancies block final confirmation. P1-02's Eastern
convention applies to SGML headers; it does not authorize overriding an
explicit API timezone with an unzoned HTML index. Source precedence remains
an open Research Owner decision. No timestamp is silently relabeled or
inferred from a filing date.
Same-day evidence additionally requires the first-evidence date's accession
accepted no later than the observation timestamp. Without that evidence it
remains unresolved; prior issuer filings do not bypass this same-day check.

No ambiguous candidate was selected or fetched. Original Phase A results stay
unchanged. Independent fixture-protocol-v2 approval is required before any
additional WRDS extraction. DATA-02 is NOT PASS; Gate A remains BLOCKED.
