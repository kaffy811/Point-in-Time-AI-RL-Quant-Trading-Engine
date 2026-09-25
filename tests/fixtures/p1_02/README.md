# Synthetic P1-02 fixtures

All identities, prices, facts and SEC-format payloads here are artificial test data. Names such as FB/META and GOOG/GOOGL illustrate identity handling; these are not actual market observations or company financials.

`calendar.json` is a sparse synthetic exchange schedule, not a complete historical calendar. Dates omitted within coverage represent non-sessions in this simulation only. Production must supply a complete, versioned official session schedule. Missing-price counts intentionally reflect the sparse synthetic records and are not real data quality measurements.

`canonical.json` covers departed/current members, ticker change/reuse, share classes, early close/holiday boundaries, a split/dividend, missing prices and fundamentals, Friday and weekend amendments. SEC fixtures exercise one filing normalization without network access.
