# B2 bounded SGML audit

Latest evidence overlay; prior Phase B reports remain historical snapshots.
Frozen Phase A implementation, input hashes and all 283 outcomes reproduced unchanged.
Only the four already authorized accessions were requested; no v2 extraction.

| Observation status | Count |
|---|---:|
| SEC_CONFIRMED | 8 |
| ROLE_CONFLICT | 2 |
| NOT_YET_AVAILABLE | 0 |
| PENDING_SOURCE_UNAVAILABLE | 0 |
| AMBIGUOUS | 0 |

Unique end-to-end confirmed issuers: **2** (0001505611, 0001556266).
Counts cover 8 previously pending observations and 2 same-day observations.
The other 264 unresolved and 9 ambiguous Phase A observations are unchanged.

| Candidate CIK | Accession | Raw filer CIKs | Acceptance UTC |
|---|---|---|---|
| 0001505611 | 0001019432-11-000009 | 0001019432 | 2011-09-08T14:22:19+00:00 |
| 0001505611 | 0001013762-11-002352 | 0001505611 | 2011-08-22T21:12:24+00:00 |
| 0001556266 | 0001213900-15-004248 | 0001643794 | 2015-06-02T16:43:57+00:00 |
| 0001556266 | 0001213900-15-004052 | 0001556266 | 2015-05-20T19:35:09+00:00 |

SGML ACCEPTANCE-DATETIME is interpreted in America/New_York per P1-02,
then converted to UTC. Structured metadata is secondary and cannot override it.
The earlier API timestamps have the same clock text but explicit Z; the raw
SGML times in these four summer filings are four hours later in UTC. Both raw
sources are retained; no structured timestamp is silently relabeled.

The two 10-Q headers identify the candidate as FILER. The two first-evidence
13G/13G-A headers identify it only as SUBJECT COMPANY; FILED BY belongs to
another CIK. No additional CIK was queried. Same-day observations remain unconfirmed.
For later observations a separate matching issuer filing may confirm identity;
all accession outcomes remain in ignored row-level audit output.

Multiple filer identities within a header return AMBIGUOUS, never first-filer selection.
All matching accepted accessions are checked against the observation timestamp.
Unavailable raw sources stay pending; no weaker metadata substitution is used.

Five suitable issuers are not validated. DATA-02 IN PROGRESS; Gate A BLOCKED.
