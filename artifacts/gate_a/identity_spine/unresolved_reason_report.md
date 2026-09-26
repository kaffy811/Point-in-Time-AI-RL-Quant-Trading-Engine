# Phase B1 — unresolved root-cause audit

All **266** Phase A UNRESOLVED observations are assigned exactly one reason.
Frozen Phase A bytes and implementation hashes verified; no resolver changes.

| Reason | Count |
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

Classification precedence: missing history → conflicting history → missing CUSIP →
inconsistent CUSIP pair → no exact-related links → only unvalidated links →
validated/match-class mismatch → same-day SEC requirement → missing first dates →
all dated strong matches after as-of → OTHER. Null dates do not become valid evidence.
NO_CRSP_CUSIP_ASOF includes both no active CRSP row and a row without identifiers.
Multiple rows with a single identical projection are not conflicting identities.

The report inspects the full downloaded snapshot to explain why the PIT resolver
could not resolve. These reasons are administrative diagnostics, not historical
features: e.g. adding a future link may change a diagnostic category but never the
frozen historical identity result. A future or unvalidated link is not a resolution.

## Representative real observations

Examples are observation references and aggregate evidence counts; full licensed
row details stay in ignored Parquet and raw fixtures.

| Reason | PERMNO | As-of date | Active history rows | Related links | Strong exact links | Future strong links |
|---|---:|---|---:|---:|---:|---:|
| NO_CRSP_CUSIP_ASOF | 12350 | 2010-10-21 | 0 | 0 | 0 | 0 |
| NO_CRSP_CUSIP_ASOF | 12350 | 2025-10-11 | 1 | 0 | 0 | 0 |
| NO_WRDS_LINK_FOR_CUSIP | 12350 | 2016-05-25 | 1 | 0 | 0 | 0 |
| NO_WRDS_LINK_FOR_CUSIP | 12350 | 2017-10-04 | 1 | 0 | 0 | 0 |
| ONLY_UNVALIDATED_WRDS_LINK | 12350 | 2010-10-22 | 1 | 2 | 0 | 0 |
| ONLY_UNVALIDATED_WRDS_LINK | 12350 | 2011-02-10 | 1 | 2 | 0 | 0 |
| FIRST_EVIDENCE_AFTER_ASOF | 12350 | 2012-10-03 | 1 | 4 | 3 | 3 |
| FIRST_EVIDENCE_AFTER_ASOF | 12350 | 2012-10-08 | 1 | 4 | 3 | 3 |
| FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC | 14093 | 2015-06-02 | 1 | 2 | 1 | 0 |
| FIRST_EVIDENCE_SAME_DAY_NEEDS_SEC | 78690 | 2011-09-08 | 1 | 1 | 1 | 0 |

Zero-count categories have no real example; no examples were fabricated.
Ambiguous observations are outside this 266-row audit and remain unchanged.
Gate A remains BLOCKED.
