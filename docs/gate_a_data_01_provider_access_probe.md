# GATE-A-DATA-01 — Provider Access Probe

Status: **PASS — Research Owner decision, 2026-09-25**.

The owner confirms record-level access to `crsp.dsf_v2`, `crsp.dsp500list_v2`,
`crsp.stksecurityinfohist`, `wrdssec_common.wciklink_cusip`, `crsp.stkdistributions`
and `crsp.stkdelists`. This supersedes the access-blocked status below. The earlier
probe JSON is retained as historical evidence; this update records the owner's
new evidence assessment, not a new live probe performed in this turn. Gate A remains
BLOCKED. INFRA-01 review/location checks and DATA-02 historical linking remain separate.

## Earlier probe (historical, superseded for access status)

This probe was executed after RDR-004 approval. It answers only whether the approved datasets are legally and programmatically accessible; it did not inspect predictive outcomes or select a cohort by returns.

Result: SEC public accession/submissions access is available and returned historical 2010/2015/2020/2025 records plus an XBRL filing index. CRSP/WRDS and Norgate entitlements are unavailable in the current environment. SEC contract fit remains PARTIAL because the accession-level canonical adapter, revision chain and historical identity linking are not yet implemented.

## Preferred checks

Verify access to:

1. CRSP PERMNO security identity and active/inactive history;
2. CRSP historical S&P 500 constituent history;
3. CRSP daily `DlyOpen`, raw OHLCV, distributions, adjustment fields and delisting economics;
4. WRDS CCM / SEC linking tables with effective dates;
5. SEC accession indexes, complete filing/XBRL records and acceptance timestamps.

## Fallback checks

If preferred access is unavailable, probe Norgate Platinum for exact historical constituents, delisted securities, OHLCV and documented adjustment/event fields, together with SEC accession-level archives. Record the narrower supported corporate-action scope before any cohort is frozen.

## Output

The detailed matrix is in `artifacts/gate_a/provider_access_probe.json`. A failed preferred probe may activate the documented fallback only after its entitlement and corporate-action scope are verified; no rejected provider was substituted.
