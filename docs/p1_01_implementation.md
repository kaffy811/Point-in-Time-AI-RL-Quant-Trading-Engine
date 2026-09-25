# P1-01 — Repository Bootstrap

Status: **IMPLEMENTED / LOCALLY VERIFIED / REMOTE-CI PENDING**

Closing evidence: commit SHA — pending; CI run URL — pending; remote test count — pending; independent bootstrap review — no outstanding BLOCKER/HIGH. Local bootstrap evidence below refers to the original 23-test checkpoint, not the expanded P1-02 suite. On first push, record the successful CI run for the exact pushed commit and review status here before setting CLOSED. No remote is configured.

Implemented repository module boundaries, the 14 research rules, frozen baseline YAML, typed configuration validation, canonical configuration hashing, explicit UTC logging, CLI, locked dependencies and CI. No experiment code or research results were generated.

Local verification on Python 3.11.8:

- `uv sync --frozen --python 3.11`: passed.
- `.venv/bin/pytest`: 23 passed (unit and CLI integration).
- `.venv/bin/ruff check .`: passed.
- `.venv/bin/mypy src`: passed, 13 source files.
- `.venv/bin/quant-engine --config configs/phase1_baseline.yaml`: passed.

The independent reviewer initially identified a HIGH type-check failure: invalid float Literal annotations and untyped PyYAML calls. Float fields now enforce equal lower/upper frozen bounds; the external untyped constructor calls have narrowly scoped suppressions followed by Pydantic validation. Regression tests reject altered portfolio caps.

Independent recheck confirmed the HIGH finding resolved: 23 tests, Ruff and Mypy passed; no outstanding BLOCKER/HIGH findings within bootstrap scope. This does not approve quantitative research gates.

Remote CI has not run; no Git remote was supplied. No commit or PR has been created. Leakage, schema and portfolio accounting suites await the corresponding implementations; empty directories do not demonstrate research gate acceptance.

Research questions are recorded in research_decisions.md. At this bootstrap checkpoint the next ticket was P1-02 PIT Data Contracts; its subsequent implementation and evidence are now in docs/p1_02_implementation.md. Research Owner decisions are needed before implementing behavior dependent on those open questions.

Research results: [TODO: 待实验结果]
