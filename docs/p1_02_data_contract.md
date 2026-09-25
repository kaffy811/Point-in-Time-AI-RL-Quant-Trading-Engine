# P1-02 — Point-in-Time Data Contract

Status: IMPLEMENTED / LOCALLY VERIFIED / REMOTE-CI PENDING.
This is a contract implementation, not a certified historical database or Gate A approval.

## Event time and knowledge time

`fiscal_period_end` describes an economic period. `filing_accepted_at` describes when a filing was accepted. `available_timestamp` describes when the particular observation/version could be known. For example, a June 30 fact filed August 2 at 16:37 ET is unavailable for the August 2 16:10 ET signal. Vendor publication/revision can make availability later still. `ingested_at` is acquisition provenance, not a substitute historical publication timestamp. All timestamps must include timezone offsets and are normalized to UTC; dates are exchange-local dates.

No fixed fiscal-quarter lag is used. Every visible observation satisfies `available_timestamp <= signal_timestamp`. Facts also satisfy `filing_accepted_at <= signal_timestamp`. `ingested_at`, source versions and dataset hashes are audit metadata, not feature inputs.

## Canonical datasets

All four schemas in `src/data/schemas.py` are immutable, reject unknown fields and nonfinite numeric values, and carry source, source version, ingestion and availability provenance. Missing prices, volume and fact values use explicit nulls; corporate-action fields cannot be inferred from missing data.

| Dataset | Observation identity | Important fields |
|---|---|---|
| Security master | security_id, valid_from | ticker, exchange, company_name, sector, industry, valid_to |
| Index membership | security_id, index_id, effective_from | effective_to, available_timestamp |
| Market | security_id, trade_date | OHLC, raw OHLC, volume, dividend, split_factor, action source/version |
| Fundamental | security_id, fact_name, period start/end, period_type, unit, revision_id | filing acceptance, accession, value, supersedes_revision_id |

Stable security IDs are internal; ticker is never a join key. Separate share classes have separate IDs. Ticker reuse is allowed on nonoverlapping exchange/ticker intervals. Overlapping identities, orphan IDs and duplicate observations fail loudly, including identical duplicate rows. Source versions cannot silently resolve conflicting rows. Repeated dataset snapshots must not be concatenated with keep-last deduplication.

All identity and membership intervals use `[start, end)`. Null end means unbounded, not a fabricated far-future date. Finite endpoints also require `end_available_timestamp`: the end's knowledge time must lie between row availability and ingestion, and no later than the effective end. A snapshot hides endpoints not yet announced. Retroactive interval corrections are rejected: their bitemporal revision model needs a separate reviewed extension, never a silent historical overwrite.

## Unified historical API

```python
from datetime import datetime
from src.data.pit_store import PITStore

store = PITStore(validated_bundle, explicit_calendar, config)
snapshot = store.snapshot(
    signal_timestamp=datetime.fromisoformat("2024-08-02T16:10:00-04:00"),
    universe="sp500",
)
```

All future research consumers must use this path. Provider normalization and dataset-wide quality reports are administrative ingestion tools, not historical feature sources. PITStore validates the whole bundle before admitting it, filters membership and master on identity/event/knowledge time, then gates all market and fundamental history by availability. Facts are resolved only after filtering; output is deterministic under input row reordering.

Snapshot returns historically eligible securities, membership, all available daily history, and latest available revision per fundamental observation. This is not a guarantee of execution-time tradability: trading halts, lot sizes, delisting settlements and next-open availability are outside P1-02. Missing known identity for an active membership raises an error rather than silently removing the member. Missing/stale market records never shrink the universe.

`missing_market_security_ids` means no available historical bar at all. `latest_completed_session` and `stale_market_security_ids` identify missing bars for the most recent session whose close plus delay has elapsed. `incomplete_market_security_ids` identifies null OHLC/volume on that session. Consumers must handle these explicitly in their own approved future contracts; no fill-forward or imputation is implemented here.

## Completed bars and calendar

Approved configuration: formation at 16:10 America/New_York; daily bars no earlier than official session close plus five minutes; execution remains next trading-day open. Normal-session floor is 16:05 ET. An early-close session ending at 13:00 has a 13:05 floor; formation remains 16:10. Actual later availability always wins. This is an operational assumption, not a guarantee about any vendor's speed.

The store requires a versioned, explicit exchange session schedule with declared coverage. Holidays have no sessions. Unknown dates outside coverage fail. Market rows on non-session dates fail. Calendar correctness/completeness is a provider obligation; the store cannot establish official calendar truth from a supplied JSON. `signal_timestamp(day)` forms the configured timestamp for a supplied session; weekly scheduling is a later ticket. Arbitrary-time `snapshot()` remains available to test information boundaries, including weekends. DST is handled using America/New_York, never a fixed UTC offset.

## Corporate actions

Canonical open/high/low/close equal raw_open/raw_high/raw_low/raw_close. A contradictory adjusted price is rejected, not renamed raw. Retain unadjusted executable prices, dividend and split data with action source/version. Fixture convention: split_factor is new shares per old share, 1 means no split; dividend is cash per share on the ex-date (`trade_date`); both are in that record's price/share basis. A split of 2 is 2-for-1. Missing action information must not be replaced by guessed neutral values. A combined market row's availability must cover both its raw bar and its action information; the provider must not attach later-revised actions under the original bar timestamp. This source-evidence obligation cannot be proven by a schema alone.

Future feature prices must be split/dividend-adjusted using only actions knowable at the signal timestamp. Future execution accounting uses raw open plus explicit corporate-action handling. Labels and portfolio returns must use a consistent total-return treatment. P1-02 preserves evidence and tests a synthetic split/dividend record; it does not implement any adjustments, returns, labels or accounting. Dividend entitlement/payment timing, split/open ordering and delisting proceeds remain in RDR-005 before P1-05/P1-09.

## Revision policy

A fundamental observation includes exact start/end and unit so quarterly/YTD/annual durations or currencies are never collapsed. Duration facts require a start date; instant facts must not have one. Fact revisions form an explicit linear chain per observation. Revision IDs are unique within that observation; each later row must supersede the immediately preceding version, have strictly later availability and nondecreasing filing acceptance. Branches, missing predecessors and equal-time ambiguity fail. This policy supports amendment/restatement and later vendor correction to the same filing without backfilling past snapshots.

An original root must be explicitly supplied. A first-seen row with no known predecessor does not prove the source has complete revision history. Production provenance must state source coverage. Fundamental null values remain null; no training preprocessing is implemented.

## First provider boundary

`providers/base.py` defines the normalization protocol. `SECCompanyFactsAdapter` accepts archived Company Facts JSON plus the selected complete-submission SGML header and an explicit CIK-to-security-ID context. It verifies CIK/accession agreement, parses the exact header acceptance time (Eastern), rejects ambiguous timestamps/duplicates and selects one accession. It does not join on ticker or guess acceptance from `filed` date. The provider context's identity mapping must be supplied and versioned by the data owner.

Company Facts is an aggregated, updated API; see the [official SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). This adapter conservatively assigns downloaded fact availability to ingestion because it cannot prove when the current vendor representation first appeared. It is deliberately unsuitable for retroactive 2010–2025 research when first downloaded today. It does not infer revision chains across separate downloads; combining overlapping roots fails until an explicit canonical chain is supplied. Current tests use clearly labeled synthetic provider-format fixtures, not live SEC data. Network acquisition and authenticated providers are not implemented.

## Lineage and quality

`src.data.cli` produces data_quality_report.json, data_quality_report.md and manifest.json. Reports include coverage, security counts, additions/removals, duplicates, null prices and entirely missing observations, fact counts, late filings, invalid intervals, orphans, ticker transitions and timestamp rejections. `late_filings` means acceptance after the report's explicit as-of timestamp; it is not a regulatory lateness rule. The report is dataset-wide and may describe future records, so it must never enter a feature matrix.

Each canonical dataset manifest contains dataset_name, dataset_version, source/source_version pairs, ingestion, schema version, row count and an order-independent SHA-256 hash. The calendar is separately hashed; the report carries config and raw-input hashes. Rejected schema rows remain recorded in issues; a report for a rejected payload says FAIL and its manifest says how many rows were excluded. A FAIL manifest cannot certify a usable store. The CLI exits nonzero on any contract issue, while writing rejection evidence. Artifact JSON uses explicit fixed inputs, not wall-clock generation time, so identical inputs reproduce byte-identical reports.

No financial performance metrics are computed. All research results: [TODO: 待实验结果].
