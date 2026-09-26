# DATA-02 B2 — bounded raw SGML confirmation

Research Owner authorized only the four previously pending accessions. This audit
supersedes the earlier B2 source-precedence blockage; earlier reports remain dated
historical evidence. Phase A source, fixtures and outcomes are unchanged.

Raw SGML ACCEPTANCE-DATETIME takes priority, interpreted as America/New_York per
P1-02 and converted to UTC. Exact-accession submissions metadata is secondary;
its original timestamp and difference from SGML are recorded. WRDS cikdate1 is
never sufficient to establish same-day timing.

The provider downloads at most a 64 KiB prefix per attempt and saves bytes only
through the closing SEC header. Each of four fixed accession URLs has at most
three attempts, with 1/2-second backoff after transient errors. Redirects cannot
expand the scope. Cached source bytes must match their receipt. All raw sources,
receipts and observation-level Parquet remain Git-ignored.

The offline audit verifies exact accession, role-scoped COMPANY DATA CIKs and
acceptance time. FILED BY is explicitly treated as a filing-party role, whereas
SUBJECT COMPANY cannot confirm filer identity. Multiple distinct filer CIKs are
AMBIGUOUS; malformed or duplicate identity fields fail the run. No accession-prefix
CIK, current ticker, company name or tmatch tie-breaker is used.

Only the two authorized CIKs' 8 pending and 2 same-day observations are eligible.
Same-day observations require their first-evidence accession; older issuer
filings cannot bypass this check. For later observations, an unambiguous matching
issuer accession accepted by as-of confirms identity, even if another ownership
filing lists the issuer as its subject. Every accession outcome is retained.
An ambiguous eligible header blocks confirmation; otherwise a matching accepted
header confirms, missing required evidence stays pending, matching late evidence
is NOT_YET_AVAILABLE, and subject-only evidence is ROLE_CONFLICT.

Verification commands (offline except the explicitly labeled provider command):

```bash
# Local real fixtures required; accepted Phase A hashes are verified.
.venv/bin/python -m src.data.identity.sgml_audit
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy src
# Optional explicit provider invocation; genuine contact supplied locally.
SEC_USER_AGENT='<project and genuine contact>' .venv/bin/python -m src.data.providers.sec_sgml
```

The real run confirms 8 observations / 2 issuers. The two same-day observations
are role conflicts and remain unconfirmed. No after-as-of or unavailable-source
case remains in this bounded set. Nine original ambiguous observations remain.
The five-issuer validation requirement is not satisfied; fixture-protocol-v2 is
not executed. DATA-02 IN PROGRESS; Gate A BLOCKED.

Header format reference: [SEC accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
