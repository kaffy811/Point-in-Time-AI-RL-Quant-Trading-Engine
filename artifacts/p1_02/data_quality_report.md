# P1-02 Data Quality Report

Status: **PASS**

Data contracts only; no performance results. See JSON for rejection details.

| Metric | Value |
|---|---|
| status | "PASS" |
| scope | "data_contract_only" |
| dataset_version | "synthetic-p1-02-v1" |
| as_of | "2024-08-02T16:10:00-04:00" |
| config_hash | "93f9eab030bc7486320c785703c347e8327ed54b9a279d43f88b84b322abc4fe" |
| input_content_hash | "2611069bda18b53497bdb3b5279fc767f765f4a8ce4750d1ac37b00fbf70e74d" |
| date_coverage | {"securities": {"field": "valid_from", "start": "2010-01-01T05:00:00+00:00", "end": "2022-06-09T04:00:00+00:00"}, "memberships": {"field": "effective_from", "start": "2010-01-01T05:00:00+00:00", "end": "2015-07-01T04:00:00+00:00"}, "market": {"field": "trade_date", "start": "2024-07-03", "end": "2024-08-02"}, "fundamentals": {"field": "fiscal_period_end", "start": "2024-06-30", "end": "2024-06-30"}} |
| number_of_securities | 6 |
| membership_additions | 5 |
| membership_removals | 1 |
| duplicate_counts | 0 |
| missing_price_counts | {"raw_open": 1, "raw_high": 1, "raw_low": 1, "raw_close": 1} |
| missing_price_observations | 44 |
| missing_volume_counts | 1 |
| fundamental_fact_counts | 4 |
| missing_fundamental_values | 1 |
| late_filings | 2 |
| late_filings_definition | "filing acceptance after report as_of, not regulatory lateness" |
| invalid_intervals | 0 |
| orphan_security_ids | 0 |
| ticker_changes | 1 |
| records_rejected_for_timestamp_violations | 0 |
| schema_rejected_records | 0 |

## Issues

```json
[]
```

## Limitations

['Dataset-wide diagnostic; not a historical feature source.', 'PASS validates supplied contracts, not provider completeness or truth.', 'No performance metrics or research gate approval.']
