# Feed planning completion

**Last Updated**: 2026-10-26

What saved evidence proves that an isolated planning execution finished?
The current planner writes its four declared formats and an independent
selected-text artifact. It does not certify summary quality or publication.

## Recording boundary

One validated in-memory selection supplies both outputs:
an explicitly allowlisted metadata projection and the text-bearing artifact.
Neither output recalculates the selection or removes text from shared data.
The artifact header and native metadata retain the same execution, attempt,
date, order, ranks, scores and worker assignments.

`plan-runs` records the actual status, nullable failure cause, result counts,
separate age and selection clocks, settings used and measured operation
durations. Empty output is explicit. A missing file is not a zero-row result.
The [ledger reference](../../reference/feed-planner-ledgers.md) defines every
retained field.

## What is checked and written

The workflow independently reads current Parquet files and verifies the
declared footer, physical schema, canonical content digest and returned
receipt. It compares the native run row with the response, then reconciles
the artifact with the metadata projection, selected order and assignments.
Only exact current raw Parquet paths enter the commit manifest.

Article bodies never enter committed raw or compact planner files, file
metadata, progress, normal logs, run summaries or commit manifests. Full
parsed and rejected populations are not exported. The private request journal
is not a committed ledger or an uploaded evidence directory.

## Compaction-safe attempt proof

The declared row identities, not generic work-unit columns, settle current
planner data. Identical raw and compact copies represent one fact; genuine
attempts remain distinct. Daily, monthly, reopened-month and yearly packing
retain the original fields and captured score values. Saved reliability
results are not additive contributions.

Native and TypeScript readers reject an incompatible planner format by name.
There is no historical planner migration, compatibility alias, logical
membership archive or full-audit receipt graph. Other families keep their
existing native format and settlement.

## Partial results and boundaries

A failed later stage does not erase completed earlier files. Independent
selected outputs still finalize when health saving fails, with a partial
run and a typed cause. An unavailable file, skipped write or mismatched
readback cannot report completed planning.

Sparse progress proves observed activity only. It does not prove persistence.
The independent host instruments are optional and never establish planner
completion. Downstream worker integration and publication observations remain
separate work.

## Design rationale

Keeping the chosen result and actual run facts is enough to explain planning
without retaining every candidate's assessment or replaying a historical
selection. Exact output verification protects the handoff while the four
small formats replace the former audit products.

## See also

- [Runner](feed-plan-runner.md)
- [Operator APIs](feed-operator-api.md)
- [Persistence](../contracts/persistence.md)
- [Isolated checks](../../how-to/run-feed-ingest-plan-test.md)
