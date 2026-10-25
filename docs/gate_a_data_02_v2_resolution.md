# DATA-02 V2 resolution — C1 complete; C2 pending contact configuration

Selection state: **FROZEN_6**. CIK-link extraction: **COMPLETE**. Resampling: **PROHIBITED**.
DATA-02: **IN PROGRESS**. Gate A: **BLOCKED**.

Frozen ordered cohort: 10026, 10028, 10001, 10078, 10100, 10002.
Authoritative selection commit: `3c9d827fa4c78bbad7b0427a373830349a515921`, pushed to GitHub.
Selection SHA-256: `c353f73c16d4fcd0a890cde5def3ee26cc13a85475689a578179b01f5c791eb3`.
The frozen JSON and fingerprint are unchanged. No selection code or original resolver/SGML rule was changed.

## C1 historical resolution

Real WRDS extraction receipts verify 60 catalog rows, 23 history rows and 11 link rows.
The existing Phase A resolver was applied to all six securities on 2010-06-30,
2015-06-30, 2020-06-30 and 2025-06-30 at 16:10 America/New_York. No timestamps
or securities were replaced when history or eligible links were missing.

| C1 status | Count |
|---|---:|
| RESOLVED_PENDING_SEC_CONFIRMATION | 8 |
| AMBIGUOUS | 0 |
| UNRESOLVED | 16 |

Unresolved reasons: 12 NO_HISTORICAL_SECURITY_RECORD; 4 NO_HISTORICALLY_ELIGIBLE_STRONG_LINK.
All six complete-result future/order invariance checks pass 24/24. Future-history
perturbations are nonvacuous for 18 observations; future-link perturbations for 6.
Original Phase A/V1 implementation hashes, fixtures and accepted results were verified.

| PERMNO | As-of date | C1 status | CIK | Reason |
|---:|---|---|---|---|
| 10026 | 2010-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000785956 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10026 | 2015-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000785956 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10026 | 2020-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000785956 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10026 | 2025-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000785956 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10028 | 2010-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000701719 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10028 | 2015-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000701719 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10028 | 2020-06-30 | UNRESOLVED | — | NO_HISTORICALLY_ELIGIBLE_STRONG_LINK |
| 10028 | 2025-06-30 | UNRESOLVED | — | NO_HISTORICALLY_ELIGIBLE_STRONG_LINK |
| 10001 | 2010-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000043350 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10001 | 2015-06-30 | RESOLVED_PENDING_SEC_CONFIRMATION | 0000043350 | UNIQUE_HISTORICALLY_EVIDENCED_CIK |
| 10001 | 2020-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10001 | 2025-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10078 | 2010-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10078 | 2015-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10078 | 2020-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10078 | 2025-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10100 | 2010-06-30 | UNRESOLVED | — | NO_HISTORICALLY_ELIGIBLE_STRONG_LINK |
| 10100 | 2015-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10100 | 2020-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10100 | 2025-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10002 | 2010-06-30 | UNRESOLVED | — | NO_HISTORICALLY_ELIGIBLE_STRONG_LINK |
| 10002 | 2015-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10002 | 2020-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |
| 10002 | 2025-06-30 | UNRESOLVED | — | NO_HISTORICAL_SECURITY_RECORD |

## C2 evidence status

C2 is **NOT STARTED — MISSING_GENUINE_SEC_USER_AGENT**. The current process has no
SEC_USER_AGENT, and an actual contact User-Agent has been requested from the owner.
No SEC requests, header outcomes or C2 final counts are claimed. This local
configuration dependency is not a SEC outage or a completed negative result.

The immutable C1 request roster contains only CIK0000043350 (2 observations),
CIK0000701719 (2) and CIK0000785956 (4). No ambiguous or unresolved case is queried.
Each candidate is limited to one root submissions response of at most 2 MiB;
historical shards are excluded. Latest issuer-form accession at/before each fixed
as-of date and any same-day first-evidence accession are chosen from that response.
An accession roster is durably written before headers. Exact accessions are
deduplicated, at most three per CIK; overflow records a limitation and retrieves
no outcome-selected subset. Raw SGML FILER and Eastern-normalized acceptance
retain the existing precedence. Unavailable raw data cannot be replaced by
submissions membership alone; SUBJECT-only presence cannot confirm identity.

| Required final metric | Result |
|---|---|
| V2 SEC_CONFIRMED observations | [TODO: 待实验结果] |
| V2 unique SEC_CONFIRMED issuers | [TODO: 待实验结果] |
| V1 confirmed issuers | 2 (0001505611, 0001556266) |
| Total V1 + V2 confirmed issuers, deduplicated | [TODO: 待实验结果] |
| V2 ambiguous / unresolved / role-conflict / source-unavailable final counts | [TODO: 待实验结果] |
| Original five-issuer requirement satisfied | NOT EVALUATED — C2 pending |

If the final issuer union remains below five, stop and report it without resampling
or adding CCM/GVKEY. Reaching five establishes only the count requirement, not research approval.

## Design limitations and amendment slot

This is a **precommitted deterministic semantic-validation cohort**, not a
representative random sample. NUMERIC_PERMNO_ASCENDING is precommitted and
contains no outcome-based tie-breaking. Category labels are screening proxies,
not proof of events or SEC amendment availability.

PERMNO 10002 remains the amendment_check_after_freeze slot. Its four fixed
observations have no unique eligible CIK, so SEC amendment evidence cannot
currently be assessed under the bounded authorization. This is
**NOT_ASSESSED_NO_ELIGIBLE_CIK**, not a claim that the issuer had no amendments.
10002 stays in every report and cannot be replaced.

## Reproduction and audit

```bash
.venv/bin/python -m src.data.identity.v2_resolution --phase c1
# With a genuine SEC_USER_AGENT configured locally:
.venv/bin/python -m src.data.providers.sec_v2
.venv/bin/python -m src.data.identity.v2_resolution --phase c2
```

Configuration: configs/gate_a_data_02_v2_resolution.json. C1 manifest and
SEC request roster: artifacts/gate_a/identity_spine/v2_resolution/. Row-level
Parquet and all raw sources remain Git-ignored. Every C1 row carries the
committed selection SHA-256, canonical PERMNO and fixed as-of timestamp.
C2 outputs will retain the same trace plus exact accession/source receipts.
Existing audit files may only be verified and reused, never overwritten.

Independent review: docs/reviews/gate_a_data_02_v2_resolution_review.md.
Review concerns implementation readiness; C2 evidence and ticket acceptance remain pending.
