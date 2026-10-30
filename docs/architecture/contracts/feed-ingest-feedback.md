# Feed-ingest feedback

**Last Updated**: 2026-10-30

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

Terminal article-fetch and extraction failures also have individual rows in
`rejected-articles`, written through the registered ledger writer at run or
standalone-stage finalization. Each row keeps the actual article status,
download failure and low-level code separately from robots permission, status
and failure. Unobserved facts remain null. Retries do not create extra rows,
and successful recovery creates no stale rejection. Run finalization retains
completed failures after a later stage fails, including when no article is
selected. The [harvesting failure flow](../sources/feed-harvesting.md#work-facts-and-failures)
defines local writes, separate Git delivery and the process-loss limit.
These detail rows are not new health contributions: existing grouped work facts
remain the only input to feed-health aggregation. The field meanings and old
file compatibility are defined in
[rejected articles](../../reference/feed-planner-ledgers.md#m-rejected-articles).

Request counters increment at actual transport dispatch, after address
validation and [the document's robots check](../sources/feed-harvesting.md#request-and-extraction-controls).
An observed article robots warning does not become a failed article operation
or a rejection after successful download and admission. Retries and redirects
add real requests. A cache hit adds zero requests; validation and parsing do
not become HTTP requests. Unknown accounting remains null with incomplete coverage.

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

## Deferred controls

Technical admission trials, temporary restrictions, earned recovery, adaptive
polling and operational review are deferred, not delivered by these counters.
Request spend remains report-only; the current next-selection behavior is
defined in [curation](../sources/feed-curation.md).

### Admission trials

The conditional sample permits up to 100 distinct articles in each
non-overlapping age group `[24,36]`, `[12,24)`, `[6,12)`, `[2,6)` and `[0,2)`
hours, fewer when unavailable. Retries and redirects can exceed 500 HTTP
requests across those groups. Each considered entry needs a selected,
group-capped, unknown-age or future-age disposition. Total implementation cost
and configuration placement remain unsettled. This is not an ordinary-work,
selection-input or selected-output cap.

### Restrictions and recovery

The approved but inactive policy pauses only the evidenced source or endpoint
after 3 consecutive confirmed source-side failures within a configured window.
Known success resets that streak; unknown and pipeline outcomes neither count
nor reset it. An article refusal affects only that article.

A 24-hour pause makes a check due on the next permitted planner run; elapsed
time alone does not restore ordinary work. Recovery requires 3 consecutive
successful checks across at least 2 UTC dates and at least 80 percent known
outcomes. Confirmed source failure resets progress and starts another 24-hour
pause; unknown and pipeline outcomes neither count as successes nor reset
progress.

Allow up to 20 recovery-check opportunities per planner run, at most 1 per
source, oldest due first, with ties by stable source ID then endpoint identity.
This is not a request budget or ordinary-work cap. Recovery restores limited
trial access, not catalog membership or permanent-retirement authority.

The policy-state contract is still unapproved. Current run-count rest cannot
retain pause deadlines, check purpose and recovery progress beyond bounded
evidence. Do not encode those meanings in failure codes or reliability.
Before implementation, settle the configured window, the known-outcome
cohort and its reset, first enablement, and missing or refused prior state.
State must survive not-due and deferred checks without inventing work or
recovery. Any extension follows the
[TypeScript contract ownership](../../reference/feed-planner-ledgers.md#typescript-contract-ownership)
and versioning rules; the earlier clean break grants no new deletion permission.

### Polling and operational review

Adaptive polling still needs an approved formula, budget, maximum discovery
gap and coverage trade-off before it can suppress a feed request. Quiet feeds
are not source failures. Operational review is a no-go for implementation
until its caller, cadence, authority and independent evidence are approved.
Neither higher internal scores nor generated fixtures prove a live
feedback-and-next-consumer loop.

## Design rationale

Batched facts retain actual work without preserving a causal request archive.
The declared execution/feed/endpoint/day identity removes duplicate storage
representations while retaining distinct real attempts. The same validated
facts serve all three windows; no snapshot head, revision chain or separate
summary ledger is required.

## See also

- [Feed history](../sources/planner-feed-history.md)
- [Operator APIs](../sources/feed-operator-api.md)
- [Planning completion](../sources/feed-ingest-audit.md)
- [Ledger persistence](persistence.md)
