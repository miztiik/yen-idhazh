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

### Recovery-state gap (proposal only)

The current [health](../../../backend/idhazh/contracts/feed_health_state.py)
and [run](../../../backend/idhazh/contracts/feed_ingest_plan_run.py)
declarations cannot distinguish ordinary from recovery checks, retain a pause
deadline and recovery progress beyond bounded evidence, or represent TRIAL
(limited trial access, not catalog membership). Do not hide these meanings in
`rested_runs`, failure codes or reliability. Current run-count rest is not
[D5 enforcement](../../../TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md#table-d---required-design-decisions-and-stop-conditions).

The smallest proposal is one optional typed access-policy record in health
(C), using the existing feed/endpoint/run/attempt/day identity, and one optional
applied-policy record in runs (D). C would capture ordinary/recovery/neither
purpose, whether a real check occurred, a confirmed success, confirmed source
failure, pipeline error or unknown result, resulting ordinary/restricted/TRIAL phase,
UTC pause deadline, recovery streak, first/latest successful UTC dates, and
known/total outcomes with completeness. D would capture the trusted evaluation
clock, activation, actual approved parameters and explicit configured-window
binding and unit. Initial consecutive confirmed failures would be recomputed
from bounded configured evidence, not unlimited failure history.

To carry finite state beyond the [lifecycle window](../../reference/feed-planner-ledgers.md#l-lookback-summaries),
the proposal would emit actual access decisions for participating restricted
scopes even when not due or a recovery slot is deferred. When no reads or
requests occurred, their actual counters are zero. Carry policy state, not old rows
or cumulative work totals. Reuse must validate endpoint, applied settings and
temporal order. Missing or refused prior policy state is not proof of recovery.

Any approved extension must be additive and read-compatible: native Pydantic
first, version/changelog, named TypeScript field/vocabulary binding cases, and
absent policy read as UNKNOWN, never ordinary or TRIAL. Existing four-family
records must stay readable; the prior eight-ledger deletion permission does
not authorize another clean break. Packing would retain captured policy state
without summing it or adding snapshots. A/B and artifact-only article text stay
unchanged. These are proposed records, not approved field names or a ruling;
the [open decisions in Row 1](../../../TODO/20261024-67-feed-ingest-feedback-and-selection-plan.md#3-row-1---settle-remaining-trial-polling-and-review-policy)
must be settled before declarations, implementation or activation.

## See also

- [Feed history](../sources/planner-feed-history.md)
- [Operator APIs](../sources/feed-operator-api.md)
- [Planning completion](../sources/feed-ingest-audit.md)
- [Ledger persistence](persistence.md)
