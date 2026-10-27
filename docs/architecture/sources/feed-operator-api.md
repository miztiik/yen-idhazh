# Feed planning operator APIs

**Last Updated**: 2026-10-26

How do local requests fetch, parse, select, partition and persist content?
These are build-time operator APIs, not a server for the static site.
[Table K](../../reference/feed-planner-ledgers.md#k-api-inventory)
is the complete versioned route inventory.

## Independent fetch and parse endpoints

`POST /api/2026-10-20/fetch` requires UUIDv4 `request_id` and
`correlation_id`, an active configured `feed_id`, and `fetch_item_type`
(`feed` or `article`).
There is no public `source_id` alias. A feed request uses the configured
URL. An article request uses either an explicit permitted operator URL or
the complete server-owned `batch_id` and `offer_id` pair, not both.
No caller supplies a file path.

The permitted fetcher retains DNS/address validation, pinned sockets, robots,
redirect, retry, deadline and decoded-byte controls. Its strict response
contains a reference and body-free outcome, not fetched bytes. A failed
fetch remains a typed failure.

`POST /api/2026-10-20/parse` accepts `request_id`, `fetch_request_id`,
`article_id` and `correlation_id`. It checks the saved receipt, configuration,
URL hash, byte limit and identities, then parses without any network call.
Missing receipts return HTTP 404; unavailable fetch content returns HTTP 409.
Malformed controls and damaged receipts fail explicitly.

Feed parsing returns sanitized, body-free offers, discovery evidence and one
parsed `batch_id`. Article parsing completes that same batch without depending
on feed classification labels.
Fetch each offer by its server-owned reference, then parse each fetched
article. Concurrent article parses atomically update the same complete feed
batch. Selection refuses while any offer is still pending. A separate
operator article URL can produce its own batch; unrelated documents are
not silently combined.

## Identity and causes

`article_id` is the canonical URL hash called `url_key` in the retained
ledgers. Internal candidate identity uses the supplying run, feed and
original entry ordinal. It is not another committed article identity.
Publisher IDs remain curated or null.

Transient work facts retain actual UTC operation times and request attempts.
They feed grouped health counters, not a committed per-operation history.
Public responses, progress and commit manifests contain no article bodies.
The body-bearing fetch receipt remains private for the parse operation.

## Durable replay and interrupted requests

`planner-operations.sqlite` lives under the configured output root.
TypeScript contracts declare its private `PlannerOperation` and
`FetchedDocument` records. Reads use one indexed request key, never a history
walk.

The key is shared across fetch, parse and keyed plans. Reuse with different
input, operation or configuration returns HTTP 409. A short transaction
claims the request before asynchronous work; a second short transaction
saves its validated result. No SQLite write lock spans network or worker
parsing work, and independent requests can overlap.

Completed keys replay their saved response without repeating work.
A started or interrupted key returns `REQUEST_INCOMPLETE`; it is not
silently retried. An expired in-memory parsed batch cannot replay a dead
successful stage reference. Inspection or a new execution is required.
This does not promise exactly-once external HTTP work across a hard crash.

Saved fetch receipts retain their original work date. On restart, known
attempt evidence restores real request spend on that date; incomplete
accounting remains unknown. A later parse cannot relabel earlier fetches
as complete zero requests on its own API day.

The optional UUIDv4 `Idempotency-Key` on `/plan` uses this same replay
boundary. Selection has no idempotency key: another call creates a fresh
result that can continue through partitioning and persistence.

## Selection, partition and persistence APIs

All stage inputs are server-owned IDs. The configured article limit bounds
output, never the number of input candidates.
Selected metadata includes `published_at_source`. A trusted source time uses
`source`; otherwise the actual saved selection-start UTC instant uses
`selection`. This fallback is output metadata, not a new age or admission
input. The [ledger reference](../../reference/feed-planner-ledgers.md#b-selected-articles)
owns the compatible historical-read rule.

Table A

| Id | Operation | Input and result |
| --- | --- | --- |
| A1 | `select-articles` | Accepts the complete parsed `batch_id`; returns a fresh selected ID, metadata-only articles, grouped exclusions and request report. No fetch, model call or automatic health write. |
| A2 | `partition-articles` | Accepts a selected ID and optional configured strategy/count; returns assignments and estimated work without reranking. |
| A3 | `feed-health-state` | Accepts a batch ID and explicit `summarize` or `record` action, defaulting to record; returns current health, request spend, `reliability.window_days` and actual receipts when saved. |
| A4 | `persist-selected-articles` | Accepts a partitioned ID; writes selected and rejected metadata plus the selected text artifact, returning exact relative paths, `rejected_files` receipts even for zero-selected results, and a standalone run outcome where applicable. |

Each finalized execution is immutable. A fresh result must not overwrite a
prior artifact or double-count its HTTP work. Replaying the same finalized
result returns its existing receipt. The removed `persist-dispatches`
endpoint has no alias and returns ordinary HTTP 404.

## Optional task profiles

The independent host tools remain optional. Embedded callers can explicitly
provide validated `PlanRuntime.task_profiling` controls and a local report
callback for document work. The ordinary planner does not implicitly load
host-probe configuration or require a profile to complete.
The separate host sample and pinned-process start/stop APIs remain unchanged.
Profiles are not source-cost scores or planner ledger fields.

## Design rationale

Server-owned offer references preserve a complete public feed-to-article
flow without granting fetched prose authority over paths or later requests.
Shared bounded parsing capacity keeps the listener responsive while real
HTML extraction runs. Short private-journal transactions protect request
identity without restoring a listener-wide run queue.

## See also

- [Runner](feed-plan-runner.md)
- [Harvesting and trust checks](feed-harvesting.md)
- [Planning completion](feed-ingest-audit.md)
- [Host probe APIs](../../reference/host-probe-api.md)
