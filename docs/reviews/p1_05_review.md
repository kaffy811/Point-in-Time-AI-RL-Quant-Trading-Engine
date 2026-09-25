# P1-05 Independent Review — Executable Label Builder

## Scope and evidence

I re-reviewed the current P1-05 tree against AGENTS.md, RDR-008-LABEL,
`docs/p1_05_implementation.md`, `src/alpha/labels.py`,
`src/returns/economic_return.py`, the PITStore schedule methods, generated
artifacts, and the focused tests. This review specifically rechecked the
findings from the first audit.

Verification performed:

```text
pytest -q tests/unit/alpha/test_labels.py tests/unit/data/test_pit_store.py
16 passed
pytest -q
149 passed
ruff check .
All checks passed
mypy src
Success
```

Synthetic tests do not establish Gate A real-provider coverage.

## Rechecked requirements

- Execution endpoints are resolved from explicit exchange-calendar opens; no
  fixed `shift(-5)` is used.
- Signal dates are checked against the explicit calendar and the supplied
  sequence is constrained to a weekly-like 3–10 calendar-day cadence.
- Holiday scheduling resolves the next actual session open.
- Security and SPY use the exact same entry and exit interval.
- The target is simple excess return: security return minus SPY return.
- `label_end_timestamp` equals the exit execution timestamp and is available
  for later purge construction.
- The shared economic-return primitive now accepts expected session dates and
  fails with `INCOMPLETE_MARKET_COVERAGE` when interval coverage is incomplete.
- Split and dividend handling remain covered by hand-checked synthetic tests.
- Benchmark unsupported corporate actions preserve
  `UNSUPPORTED_CORPORATE_ACTION` instead of being relabeled as missing data.
- `holding_session_count` is now the elapsed endpoint interval count, with the
  convention documented in `label_schema.json`.
- Missing labels remain invalid with explicit reason codes and are never
  imputed.
- Label data remains physically separate from FeatureFrame and preprocessing.
- Artifacts retain label/schedule versions, data manifest hash, frame hash,
  validity counts, and diagnostic-only target statistics.

## Finding resolution

| Original finding | Resolution | Verification |
|---|---|---|
| HIGH — incomplete intermediate market coverage could produce a valid label | **Resolved** | `expected_dates` is passed from the calendar into both security and benchmark return calculations; missing coverage raises `INCOMPLETE_MARKET_COVERAGE`; regression test added. |
| MEDIUM — benchmark unsupported actions were mapped to `MISSING_BENCHMARK` | **Resolved** | Benchmark error handling preserves `UNSUPPORTED_CORPORATE_ACTION`; other benchmark return failures remain `MISSING_BENCHMARK`. |
| MEDIUM — endpoint-inclusive holding count was ambiguous/off by one | **Resolved** | Count is `len(expected_dates) - 1`, and the artifact schema documents it as elapsed trading-session intervals. |
| LOW — arbitrary signal sequences could be labeled as weekly | **Resolved** | Builder validates calendar session dates and 3–10 calendar-day spacing before constructing labels. |

## Remaining research risk

Provider-specific corporate-action taxonomy, delisting settlement values, and
real historical calendar/data completeness remain open Gate A risks. The
synthetic fixtures demonstrate contract behavior only and do not validate a
2010–2025 provider vertical slice.

## Final recommendation

**APPROVE.** Current findings are `BLOCKER=0`, `HIGH=0`, `MEDIUM=0`, and
`LOW=0`. P1-05 is ready for:

```text
CONDITIONAL PASS / LOCAL VERIFIED / REMOTE-CI PENDING
```

Gate A remains **PARTIAL**, and no real-data coverage or predictive result is
claimed.
