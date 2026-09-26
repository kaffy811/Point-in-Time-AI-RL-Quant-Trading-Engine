# DATA-02 Phase A — preliminary real-fixture results

Real inputs: 91 CRSP history rows, 35 WRDS links, 5 PERMNOs. Both source hashes and row counts verified.

283 deterministic observations: each history start/end and adjacent outside day, matching link first-date ±1 day, plus configured anchor dates. All timestamps use 16:10 America/New_York; no trading-session claim is made.

| Preliminary status | Observations |
|---|---:|
| AMBIGUOUS | 9 |
| RESOLVED_PENDING_SEC_CONFIRMATION | 8 |
| UNRESOLVED | 266 |

| Reason | Observations |
|---|---:|
| MULTIPLE_PLAUSIBLE_CIKS | 9 |
| NO_HISTORICALLY_ELIGIBLE_STRONG_LINK | 241 |
| NO_HISTORICAL_CUSIP | 5 |
| NO_HISTORICAL_SECURITY_RECORD | 18 |
| SAME_DAY_SEC_ACCEPTANCE_CONFIRMATION_REQUIRED | 2 |
| UNIQUE_HISTORICALLY_EVIDENCED_CIK | 8 |

Unique preliminary CIKs requiring actual SEC accession confirmation: **0001505611, 0001556266**. No CIK is finally confirmed.

Same-day-only candidates requiring SEC acceptance checks: 0001505611, 0001556266. These remain UNRESOLVED in Phase A.

Only historically eligible exact-9 validated=3 evidence is preferred; when absent, exact-8 validated=2 is considered. Equal-date evidence is provisional and cannot auto-resolve. Multiple CIKs in the selected tier are AMBIGUOUS; repeated evidence for the same CIK is not a competing identity and stays preserved in raw audit.

tmatch and cikdate2 are retained in ignored `wrds_link_evidence.parquet` only. They are current-snapshot evidence, not historical decision inputs. No link expires at cikdate2. Dates exported as ISO strings are strictly parsed without changing raw bytes.

No validated=2 links occur in these real fixtures; real fallback coverage is NOT EXERCISED. Fixture category coverage, SEC and CCM checks remain incomplete. No fabricated evidence, bulk fetch, features, training or performance work occurred. Gate A remains BLOCKED.
