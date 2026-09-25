# AI/RL Quant Trading Engine

Phase 1 builds a leakage-safe, cost-aware supervised-alpha research baseline. Research design is frozen. Leakage prevention takes priority over performance. No RL is implemented.

## Current scope: P1-02 data contracts

P1-01 is IMPLEMENTED / LOCALLY VERIFIED / REMOTE-CI PENDING. P1-02 adds four canonical data schemas, a unified PIT snapshot API, revision/identity/availability checks, lineage, data-quality reports and one conservative SEC payload adapter. All validation uses synthetic fixtures; no live provider ingestion or alpha experiment has run. Features, preprocessing, LightGBM, walk-forward, portfolios and performance reporting remain pending P1-03–P1-12. Empty module directories are boundaries, not implemented functionality. All research results: **[TODO: 待实验结果]**.

The current workspace is the repository root; no nested repository is needed. Work is on `phase1/data-contract`; subsequent branches follow the specification: `phase1/pit-feature-store`, `phase1/alpha-model`, `phase1/walk-forward`, `phase1/portfolio-baselines`, `phase1/cost-engine`, `phase1/reporting`. Keep each PR scoped to one engineering question.

## Verify bootstrap

Requires uv and Python 3.11 or 3.12.

```sh
uv sync --frozen --python 3.11
uv run --frozen quant-engine --config configs/phase1_baseline.yaml
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy src
```

The CLI only validates configuration and emits its canonical SHA-256 hash. It is not an experiment runner. The future one-command research runner remains pending. CI runs all collected tests, lint and typing; remote CI is not claimed to pass until executed. Dedicated PIT/schema/accounting tests will be added with their implementation tickets.

## Frozen accounting and research contract

PIT historical S&P 500 membership uses stable security IDs. Fundamental availability uses actual filing timestamps. Learned preprocessing is TRAIN-only; validation and test are transform-only. Feature columns must be explicitly whitelisted. Signals form at 16:10 ET after completed daily-bar availability (official close plus at least five minutes); execution remains next trading open. 2010–2025 is the research interval and 2026 is reserved.

Traded notional: `TN = sum(abs(target_weight - pretrade_weight))` across the union of security holdings. One-way turnover: `0.5 * TN`. Pretrade weights drift with prices and must not be replaced by previous target weights. Cost: `TN * bps / 10000`. Net return: `gross_return - cost`. Base cost is 10 bps; sensitivities are 5/10/20 bps. Reports must show gross, net, turnover and costs together.

Read [AGENTS.md](AGENTS.md) before changes. Open research decisions are tracked in [the RDR register](docs/research_decisions.md); proposals do not authorize changing assumptions. Bootstrap validation checks the configuration contract, not quantitative correctness. Independent review and human research gate decisions are required.

## Event time is not knowledge time

A June 30 fiscal period filed on August 2 at 16:37 ET is unavailable to the August 2 16:10 signal. Historical joins use actual availability and filing acceptance, never fiscal-period end plus a fixed lag. Later revisions cannot overwrite earlier snapshots. Historical membership and ticker mappings use stable IDs and left-closed/right-open intervals; even unannounced future interval ends are hidden.

Read the [PIT contract](docs/p1_02_data_contract.md), [P1-02 implementation report](docs/p1_02_implementation.md), and [research decisions](docs/research_decisions.md). The supplied calendar is explicitly synthetic; production calendar/data completeness remains unverified.

## Reproduce P1-02 data-quality artifacts

```sh
uv run --frozen python -m src.data.cli \
  --input tests/fixtures/p1_02/canonical.json \
  --calendar tests/fixtures/p1_02/calendar.json \
  --config configs/phase1_baseline.yaml \
  --dataset-version synthetic-p1-02-v1 \
  --as-of 2024-08-02T16:10:00-04:00 \
  --ingested-at 2026-01-01T04:00:00+00:00 \
  --output artifacts/p1_02
```

This produces JSON/Markdown data-quality reports and a manifest, with no performance metrics. Failure writes rejection evidence and exits nonzero. All downstream research must obtain historical records through `PITStore.snapshot`; administrative reports and provider payloads are not feature inputs.

## P1-03 work in progress

P1-01/P1-02 remain Conditional PASS; Gate A remains PARTIAL. P1-03 now provides PIT-only calculators, lineage validation, whitelist, optional ranks, correctness tests and synthetic diagnostic artifacts. RDR-007 is approved with modifications and the independent numerical review found BLOCKER=0/HIGH=0. P1-03 is Conditional PASS locally; remote CI and real-data Gate A validation remain pending. See [implementation status](docs/p1_03_implementation.md).
