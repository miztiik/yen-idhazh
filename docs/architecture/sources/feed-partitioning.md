# Feed article partitioning

**Last Updated**: 2026-10-30

How are chosen articles assigned to workers without changing the selection?
Partitioning consumes one validated selected batch and returns the same
content and ranks with zero-based worker assignments.

## Current-run construction

The selected batch is server-owned and complete. Duplicate URLs, missing
content, invalid ranks, mismatched execution facts and invalid work values
fail before packing. No file path or caller article list replaces it.

The work estimate is explicit evidence when supplied, otherwise extracted
word count. Words are a work proxy, not a measured execution duration.
Unknown timing, publisher and numeric adjustments stay unchanged.

## Allocation and persistence

`config/feed-ingest-plan.json` supplies strategy and worker bounds.
Its `partition.enabled` boolean defaults to true. When false, the planner
keeps article selection and persistence but bypasses worker assignment.
The report labels supplied worker counts and strategies as ignored in this mode,
not as effective overrides.
The current bounds allow one through twenty workers, with four by default.
`bin-pack` greedily places larger work on the least-loaded worker;
`round-robin` distributes in selected order; `none` uses one worker.
Assignments retain the original selected order and rank.

`persist-selected-articles` uses the same partitioned population for strict
metadata Parquet and the selected-text artifact. It does not reselect,
reconstruct content from history or create a separate dispatch ledger.
Empty selection has explicit empty metadata and an actual empty artifact.

## Named history and proof

Current planner readers accept only the declared four-ledger format.
Metadata and artifact must agree on execution, attempt, date, identities,
order, ranks, scores and assignments. Native verification also checks schema,
footer and canonical digest. A missing selected file cannot stand in for a
verified empty result.

Compaction retains each original execution and attempt, using the declared
row key rather than generic work-unit identity. See
[planning completion](feed-ingest-audit.md#compaction-safe-attempt-proof).
Historical production digest workers are not switched to this handoff here.

## Design rationale

Keeping assignment separate from selection allows real concurrent downstream
work without changing which articles were chosen. One in-memory result
prevents metadata and summarizer text from drifting into different choices.

## See also

- [Curation](feed-curation.md)
- [Operator APIs](feed-operator-api.md)
- [Ledger reference](../../reference/feed-planner-ledgers.md)
- [Persistence](../contracts/persistence.md)
