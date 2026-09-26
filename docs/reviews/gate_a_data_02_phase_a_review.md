# GATE-A-DATA-02 Phase A — independent review

Review date: 2026-09-25. Reviewer: independent review agent, separate from the implementation agent. Scope: offline preliminary historical identity resolution, real-input loading, reproducible audit generation, config, tests and generated Phase A evidence. No implementation files were modified and no live provider access was performed by this reviewer.

## Disposition

**Phase A implementation: BLOCKER = 0, HIGH = 0, MEDIUM = 0, LOW = 0.** No actionable implementation defect was found in the reviewed final revision. This is a preliminary-stage code/evidence review, not final DATA-02 acceptance or research approval. Gate A remains BLOCKED.

The preliminary state `RESOLVED_PENDING_SEC_CONFIRMATION` must not be interpreted as SEC-confirmed identity. SEC accession checks, optional CCM disagreement reporting and full fixture-category acceptance remain unperformed. The earlier INFRA repository question is superseded by the Research Owner's canonical repository confirmation and tracked baseline.

## Reviewed behavior

- CRSP PERMNO is canonical. Inclusive source history endpoints select historical CUSIP/CUSIP9; ticker/trading symbol are descriptive metadata. Missing or conflicting historical records fail closed, with no current-identifier backfill.
- Candidate dates are filtered before choosing the approved exact-nine validated=3 tier or exact-eight validated=2 fallback. Future/null first evidence cannot displace a historical candidate; same-day-only evidence does not auto-resolve without SEC acceptance confirmation. Multiple CIKs in the selected tier remain AMBIGUOUS; no score/row-order winner is chosen.
- `cikdate2` is never treated as expiry or identity validity. `tmatch` and last-observation dates remain raw audit-only fields and are excluded from historical decisions/output invariance claims. Exact source identifiers are checked without padding or check-digit fabrication.
- Phase A has no live WRDS/SEC imports, feature/label calculation, cohort freeze, membership ingestion or corporate-action economics. No final SEC or CCM result is fabricated.
- Raw source bytes are checked against their acquisition-manifest hashes, row counts and expected tables before resolution. Config, source hashes and implementation hashes accompany deterministic outputs. The reviewer independently regenerated all nine output artifacts in a temporary root and found byte-for-byte agreement with the delivered artifacts, including all three licensed Parquet hashes.
- Git reports no tracked raw/Parquet files. The three licensed result Parquets and raw WRDS fixture manifest were independently checked as ignored. Review/report/config files remain ordinary reviewable artifacts.

## Real evidence and limits

The available source corpus contains 91 CRSP security-history rows and 35 WRDS links across five PERMNOs. The configured boundary/anchor observation policy produces 283 observations:

| Preliminary status | Observations |
|---|---:|
| RESOLVED_PENDING_SEC_CONFIRMATION | 8 |
| AMBIGUOUS | 9 |
| UNRESOLVED | 266 |

These are observation counts, not five independently confirmed SEC filers. The corpus exercises historical ticker/CUSIP changes and actual multi-CIK ambiguity. It does not establish all originally requested issuer categories, SEC amendment validation, membership-change coverage or real validated=2 fallback coverage. Perturbed rows test code behavior only; they are not provider evidence.

Each of six invariance checks passes for all 283 observations: repeated resolution, reversed input order, removal/append/mutation of future-positioned records and removal of audit-only last dates/scores. Review confirms the code excludes future records before tier choice. The checks do not prove immunity to retrospective vendor corrections of an already-historical first date, CUSIP or validated code. Archived historical revisions remain a stated source limitation.

Most real-fixture tests deliberately skip in CI environments lacking licensed local inputs. The reported local acceptance counts include those tests; future CI green status alone cannot substitute for rerunning them with the hash-verified corpus.

## Independent verification

```text
.venv/bin/pytest tests/unit/data/identity -q: 17 passed
.venv/bin/pytest -q: 206 passed in 10.38s
.venv/bin/ruff check .: passed
.venv/bin/mypy src: passed, 60 source files
Temporary-root audit regeneration: all generated artifacts byte-identical
Generated licensed Parquet SHA-256 verification: all matched
Git raw/Parquet tracked-file inventory: empty
```

A transient string-concatenation edit was encountered while implementation was still changing; the author repaired it before this final verification. Final lint, type checks, all tests and regeneration above were rerun on the repaired revision. No unresolved finding is concealed by the final counts.

This review covers Phase A only. Final DATA-02 still requires its outstanding real SEC accession evidence and separately reviewed dependent behavior. No Gate A PASS is declared.

Final documentation cross-check: `docs/gate_a_data_02_identity_spine.md` now supersedes the missing-input state, matches the actual preliminary counts and explicitly records the unresolved SEC/CCM and fixture-coverage limitations.
