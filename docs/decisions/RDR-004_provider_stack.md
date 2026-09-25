# RDR-004 — Phase 1 Approved Provider Combination

**Status: APPROVED / GATE A REMAINS BLOCKED UNTIL ACCESS AND AUDIT**

## Preferred research-grade stack

CRSP U.S. Stock + CRSP historical S&P 500 constituents via WRDS + SEC EDGAR accession-level filings + approved historical CRSP-to-SEC linking tables.

Canonical responsibilities:

- CRSP supplies the permanent security identity backbone (internal `security_id` maps to PERMNO), historical S&P 500 membership, executable daily open, raw OHLCV, corporate-action/distribution fields and delisting economics.
- SEC EDGAR supplies accession-level filing history, `ACCEPTANCE-DATETIME`, XBRL facts and amendment chronology.
- WRDS CCM / SEC linking tables supply effective-dated PERMNO/CUSIP/GVKEY/CIK identity links where entitled.

Ticker remains descriptive metadata and is never a permanent identity. Current Company Facts snapshots, fixed-lag fundamentals and current ticker-to-CIK mappings are insufficient for Phase 1 PIT research.

## Fundamental and corporate-action rules

Fundamentals are reconstructed from accession-level filings. A usable fact must satisfy `filing_accepted_at <= signal_timestamp`; an amendment becomes visible only after its own acceptance timestamp. Post-acceptance SEC corrections remain a documented provider limitation until archived evidence is available.

The market layer must preserve enough evidence to audit splits, ordinary distributions, supported nonordinary distributions and delisting events. Unsupported or unresolved events fail closed with explicit reasons; they are never silently ignored.

## Conditional fallback

If licensed CRSP/WRDS access is unavailable, Norgate Data US Stocks Platinum + SEC EDGAR is the only approved fallback for a Gate A evaluation. It is conditional and does not claim CRSP-level corporate-action event depth. Complex events that cannot be independently reconstructed are unsupported and excluded fail-closed.

## Rejected approximations

Current S&P 500 constituents backfilled through history, Yahoo-only, FMP-only, Polygon-only, Wikipedia membership history and fixed-lag fundamentals are not approved canonical combinations.

RDR-004 approval does not pass Gate A. Access, adapter implementation, cohort freeze, real audits and independent review with BLOCKER=0/HIGH=0 remain required.
