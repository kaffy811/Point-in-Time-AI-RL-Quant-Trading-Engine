# Proposed fixture-protocol-v2 — Research Owner approval required

Status: PROPOSAL ONLY. No additional WRDS extraction or SEC CIK expansion is authorized
by this document. Resolver rules remain frozen. This is an identity-validation fixture
protocol, not the final Gate A investment cohort.

## Why v2 is needed

The original five multi-history PERMNOs supplied only two distinct unique preliminary
CIKs. The other paths are ambiguous, unvalidated or absent. B2 currently confirms zero
issuers end-to-end: one archive-access problem and one acceptance-source conflict remain.
Five selected PERMNOs therefore do not prove five validated issuers or all case categories.

## Fixed inputs and deterministic selection

1. Retain both existing unique preliminary CIKs and their original observations as
   reserved slots; do not replace failures silently. Resolve their SEC blockers separately.
2. Before any new extraction, the owner approves a versioned **candidate catalog of at
   most ten historical PERMNOs**, with source references and event/as-of dates. Catalog
   evidence must be historical and independent of returns, IC, performance, current
   ticker mapping or current index membership. No unbounded database discovery is allowed.
3. Pin catalog SHA-256, schema, three target slots and selection policy in config before
   querying. The additional slots are: ordinary long-lived history, a historically
   evidenced index addition/removal, and an issuer with an accession-level amendment.
   Existing change fixtures can cover ticker/symbol and CUSIP transitions, but each
   category must be supported by actual source evidence rather than labels inferred
   from row counts. A slot without catalog evidence remains empty.
4. Within each slot sort eligible catalog entries by numeric PERMNO, then documented
   event date. Choose the first unused PERMNO; exclude already selected PERMNOs. Overlap
   across slots is recorded, not resolved by financial outcomes. Select at most **three
   new PERMNOs**. Produce a frozen selection manifest before fetching their detailed rows.
   This makes selection reproducible from a finite approved catalog, not a guessed roster.
5. Use a predeclared historical window (2010-01-01 through 2025-12-31) and event-specific
   as-of dates with the existing exchange-local 16:10 convention. Retain exact original
   source intervals and evidence, including any interval needed to cover the first date.
   Index evidence only annotates the fixture; do not construct a membership dataset.

## Two bounded acquisition stages after approval

- Stage 1: one security-history extraction for the three selected PERMNOs, cap 500 rows;
  then one link extraction for their actually observed CUSIPs, cap 200 rows and at most
  ten distinct identifiers per request. Exceeding any cap stops for review rather than
  truncating or automatically broadening the request. Preserve hashes and query evidence.
- Stage 2: run the unchanged resolver on predeclared observations. Preserve all AMBIGUOUS,
  UNRESOLVED and pending outcomes. Freeze the resulting unique CIK proposal, then obtain
  explicit owner authorization for **that new SEC CIK allowlist** before requesting SEC
  metadata. The current authorization still contains only the existing two CIKs.
- For each approved new CIK, retrieve at most three accession indexes/headers needed
  for historical identity, same-day acceptance or amendment evidence. No facts or
  filing-body collection. Any byte, row, CIK or accession cap breach stops the stage.

## Acceptance and stopping rules

Require five distinct PERMNO-to-issuer chains with unique SEC-confirmed CIKs, actual
historical identifier evidence, acceptance timestamps under an owner-approved source
policy, and documented coverage of all original categories. Multiple observations for
one issuer count once. An ambiguity or timestamp/source conflict cannot count as a pass.

If either reserved issuer or a new slot fails, the protocol remains incomplete. Do not
pick a later successful candidate after seeing results, increase the pool, relax validated
or time rules, infer current identifiers, or extract another WRDS batch automatically.
Record failure and submit a bounded amendment for approval. Independent review remains
mandatory. Gate A stays BLOCKED throughout this fixture exercise.
