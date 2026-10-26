# Feed-ingest feedback

**Last Updated**: 2026-10-26

Which actual feed work informs a later selection?
The planner records per-run, per-feed facts for each actual UTC work day in
`feed-health-state`. The complete field meanings and independent windows are
defined once in [the ledger reference](../../reference/feed-planner-ledgers.md#c-feed-health-state).

## Completed-unit persistence

Fetch and parse operations emit validated in-memory work facts. A run accumulates
them into health rows, rather than writing a ledger file for each article,
attempt or operation. One health file contains all finalized feed rows for
one run, attempt and UTC work day. Work crossing midnight produces separate
day files. Completed feed work is retained when a later stage fails.

Request counters increment at actual transport dispatch, after permission and
address validation. Retries and redirects add real requests. A cache hit adds
zero requests; validation and parsing do not become HTTP requests. Unknown
accounting remains null with incomplete coverage.

A restarted standalone parse restores validated request facts from its saved
fetch receipt. Those requests remain on their original UTC day. If a saved
attempt cannot establish dispatched work, its count remains unknown rather
than becoming complete zero.

## Independent summaries

Lifecycle uses the configured represented-day window. Feed-read reliability
uses its own represented-day window and floor. Request spend uses closed UTC
calendar days ending before the actual selection-start day. See
[Table L](../../reference/feed-planner-ledgers.md#l-lookback-summaries) for
the settings and units.

Only logical feed outcomes and distinct offered URLs determine native
productivity. Rest and robots skips remain outside the reliability
denominator. Saved rolling reliability values are captured results; readers
never add them as fresh daily contributions.

The request report measures spend only. It is not a waste score, admission
qualification, hardware cost or ranking penalty. Missing request evidence
does not trigger another reliability implementation.

## Explicit recording and failures

The public health operation has `summarize` and `record` actions. Summarizing
does not write. Standalone selection has no automatic health-write side
effect. `/plan` calls the shared operation directly and can save health while
partitioning proceeds.

Known malformed native files and indexes become explicit incomplete gaps.
Valid sibling evidence remains usable; unexpected implementation errors still
propagate. An unverified count or lifecycle result is not zero or perfect
health. A failed health save cannot discard a completed selection's
independent metadata and text artifact; the run records a partial outcome
and its cause.

## Design rationale

Batched facts retain actual work without preserving a causal request archive.
The declared execution/feed/endpoint/day identity removes duplicate storage
representations while retaining distinct real attempts. The same validated
facts serve all three windows; no snapshot head, revision chain or fifth
summary ledger is required.

## See also

- [Feed history](../sources/planner-feed-history.md)
- [Operator APIs](../sources/feed-operator-api.md)
- [Planning completion](../sources/feed-ingest-audit.md)
- [Ledger persistence](persistence.md)
