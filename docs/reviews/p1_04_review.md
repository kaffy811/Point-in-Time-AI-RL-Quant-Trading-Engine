# P1-04 Independent Review — Train-Only Preprocessing

## Scope and method

This review was performed independently of the P1-04 implementation. I read
`AGENTS.md`, `docs/p1_04_implementation.md`, the preprocessing implementation,
the feature policy registry, the artifact writer, and the preprocessing tests.
I also ran the focused preprocessing tests, Ruff, and Mypy. The review checks
the frozen 1%/99% linear winsorization convention, winsorize-then-median
ordering, train-only state, policy handling, schema validation, artifact
provenance, and leakage-test evidence. No approval is based solely on test
count.

## Evidence

The implementation has the following controls:

- `Preprocessor.fit` accepts only `fit_split="TRAIN"` and derives all bounds
  and medians from the supplied TRAIN `FeatureFrame`.
- Quantiles use an explicit linear interpolation implementation; medians are
  computed after clipping the finite TRAIN observations.
- Missing indicators are registry policies with `winsorize=False`,
  `impute=False`, and `passthrough=True`.
- Infinite values are rejected during both fit and transform. A continuous
  feature with no finite TRAIN observations fails loudly.
- Transform validates the feature registry hash and exact model-column order.
  It does not mutate the frozen preprocessor.
- JSON artifacts contain the fitted parameters, feature order, registry hash,
  fit row count/security count, row-ID hash, config hash, input manifest hash,
  and transform diagnostics. No pickle or P1-03 QA report is loaded.
- The focused suite currently passes: 9 tests; the full local suite passes:
  143 tests. Ruff and Mypy pass for the preprocessing implementation and the
  full source tree.

## Hand and contract checks

| Check | Result |
|---|---|
| Train values `(1, 2, missing, 100)` | lower `1.02`, upper `98.04`, median of clipped values `2.0`; implementation agrees |
| Even median `[1,2,3,4]` | `2.5`; implementation agrees |
| Missing indicator policy | passthrough and excluded from winsorization/imputation |
| `+inf` / `-inf` | rejected during fit and transform |
| All-missing continuous TRAIN feature | rejected with `PreprocessingError` |
| Registry/order mismatch | rejected before transform |
| Serialized state | `to_dict`/`from_dict` round-trip is deterministic |
| QA isolation | preprocessing source has no artifact or feature-QA import |

## Findings

| Severity | Finding | Impact / recommendation |
|---|---|---|
| RESOLVED | The future-row append invariance test now appends extreme future rows outside the explicit TRAIN selection and verifies that the fitted state is unchanged while the row-ID hash changes. | The explicit TRAIN boundary is now tested directly. |
| RESOLVED | `transform` now checks `parameter.impute` and fails loudly for a missing value under a non-imputable policy. A dedicated policy test covers this behavior. | Policy behavior is enforced rather than inferred from current registry defaults. |
| RESOLVED | The artifact test now reads `preprocessor.json`, parses it as JSON, and verifies a deterministic `from_dict` round-trip. | File-level serialization evidence is present. |

No open findings were identified. The previous two MEDIUM findings and LOW
finding are resolved in the current tree. The added tests do not demonstrate
real-data coverage, which remains a separate Gate A limitation.

## Unresolved research risks

- Synthetic fixtures do not validate real provider taxonomy, corporate-action
  semantics, or 2010–2025 distribution shift. Gate A remains PARTIAL.
- Full-sample P1-03 QA distributions remain diagnostic-only and must not be
  reused by P1-04 or later model code.
- Remote CI has not run; local evidence cannot close that requirement.

## Recommendation

**APPROVE** for P1-04 Conditional Pass. The final review result is:

```text
BLOCKER = 0
HIGH = 0
MEDIUM = 0
LOW = 0
```

The ticket may be recorded as `CONDITIONAL PASS / LOCAL VERIFIED /
REMOTE-CI PENDING` after the repository’s final local verification. Remote CI
and the real-data vertical slice remain separate gates.
