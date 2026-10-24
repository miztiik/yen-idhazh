# Fetch and parse operator requests

**Last Updated**: 2026-10-23

How do separate HTTP requests fetch and parse the same article without
duplicating completed work? These are local build-time APIs, not site services.
The existing [runner](feed-plan-runner.md) owns listener setup and enablement.

## Two independent endpoints

`POST /api/2026-10-20/fetch` accepts a JSON object with `request_id` and
`correlation_id` as UUIDv4 strings, `source_id` naming an active configured
source, and `kind` as `feed` or `article`. A feed fetch uses that source's
committed URL and refuses a supplied URL. An article fetch requires `url`,
an operator-owned HTTP or HTTPS control. It optionally accepts
`caused_by_event_id`, a UUIDv5 observation that caused this request.
Unknown controls fail. No request field names a filesystem path.

The fetch uses the same DNS validation, pinned sockets, robots permission,
redirect checks, byte limit and retries as `/plan`. Its response includes
`fetch_request_id`, the canonical URL, `article_id`, body digest, fetch status,
attempt evidence and observations. It never returns the raw body. A failed
fetch is a recorded outcome, not successful content.

`POST /api/2026-10-20/parse` accepts only `request_id`, `fetch_request_id`,
`article_id` and `correlation_id`. It reads that one completed fetched
document from the configured output root. It checks URL identity, body
digest, byte bounds, source, run and correlation before parsing.
Missing receipts return HTTP 404. Failed fetches return HTTP 409.
Mismatched identities return HTTP 400. Damaged receipts fail explicitly.
The response contains `kind`, `parsed`, `failure`, its fetch request identity
and its new observation. RSS and Atom produce sanitized discovery entries;
HTML produces sanitized article prose, title, author and paywall evidence.
Malformed content remains a typed failure with no invented parsed result.
Parsing makes no network request.

The parser and permitted fetch stage are shared with the existing `/plan`
and CLI composition. Parsed feed links remain discovery data: the existing
validated discovery flow, or an explicit operator request, must authorize a
later fetch. Page content, canonical tags and extraction results never select
a destination. The listener has no authentication; keep it loopback or in an
operator-protected build environment.

## Identity and causes

`article_id` is the existing canonical URL hash, called `url_key` on later
candidates, selections and dispatches. It stays unchanged through fetch,
parse and later stages. The existing run/source/ordinal `candidate_id`
identifies an offered entry, not a different article identity.
`correlation_id` connects observations from the same work. Parse inherits
the fetched run ID even when requested on a later UTC day.

Each fetch, parse and network/DNS attempt has a distinct UUIDv5 `event_id`.
Parse's `caused_by_event_id` names its fetch observation; each attempt names
its containing fetch observation. A fetch may name an earlier observation.
Event IDs derive from correlation, request key, operation and attempt sequence,
not response text. Replaying a completed request returns the same IDs.
`/plan` emits the same document and attempt observations in live progress;
its existing audit and progress IDs retain their own separate namespaces.
Each actual feed parse emits exactly one parse observation, including empty
and malformed feeds. A refused fetch does not claim a parse attempt.
All recorded instant strings use UTC with `Z`.

## Durable replay and interrupted requests

The operator APIs write `planner-operations.sqlite` under `outputRoot`, the
same operator-configured root that holds native planner output.
Pydantic's `PlannerOperation` and `FetchedDocument` declarations own the
stored records; small Zod copies are bound by the existing native contract
comparison. Original date-only receipts remain readable with their original
version and exact response bytes. Missing retry wait measurements read as
null, not zero; new receipts carry the dated compatible revision.
The SQLite table and fixed filename are storage protocol constants.

The indexed request key is global across fetch, parse and keyed plans.
The input fingerprint hashes validated JSON in schema field order. The
configuration fingerprint hashes the effective harvest fingerprint, service
settings, UTC/history settings, ledger settings, registrations and checkout
commit. Reusing a key with different input, operation or configuration returns
HTTP 409. A parse also refuses a fetch made with different configuration.
No runtime environment variable selects an artifact path or destination.

SQLite's full synchronous commits retain the captured run, correlation and
UTC start before work, then atomically commit the private artifact and exact
HTTP response together. Completed requests replay after listener or process
restart without fetching, parsing or writing more ledgers. One write
transaction owns work at a time across processes. Concurrent callers receive
HTTP 409 `REQUEST_BUSY` and retry the same key; they do not start duplicate
work. SQLite recovers an interrupted transaction on reopen.
After the captured-identity commit, the next write lock re-reads and validates
the request before doing work. If another process completed it between locks,
the second caller returns that completed response instead of repeating work.

A fetch or parse interrupted before its final commit resumes with its original
captured identity. An external fetch can therefore occur again after a crash,
but no completed artifact or response is duplicated. Exactly-once network I/O
cannot be promised across a process crash. Completed failed fetches replay
their failure; a deliberate fresh observation needs a new request key.

`POST /plan` remains compatible without a key. An optional UUIDv4
`Idempotency-Key` header adds the same completed-response replay. A keyed plan
interrupted after starting returns HTTP 409 `REQUEST_INCOMPLETE`, rather than
silently repeating potentially durable ledger writes. Inspect that recorded
run and its receipts before submitting new work. The CLI remains unchanged.

Records have no automatic expiry: retention lasts until the operator removes
the named store while the listener is stopped. Keep it for as long as request
keys or fetch receipts may be reused. Removing it deliberately ends replay
protection and makes its fetch references unavailable; do not reuse old keys.
No history walk, empty-day fabrication or receipt restamping occurs.

## Optional task profiles

The separate [whole-task instrument](../../reference/host-metrics.md#whole-task-typescript-samples)
can profile actual fetch and parse work. The ordinary listener loads
`config/host-probes.json`; both new task switches default off. Embedded callers
can pass `PlanRuntime.task_profiling` with validated controls and a report
callback. An absent callback configuration leaves profiling out. The ordinary
listener writes enabled profiles as structured stderr records, never into the
HTTP response, fetched artifact or SQLite record.

Fetch starts measurement only after the active source and operator URL pass
validation. Parse starts only after its completed fetch, configuration,
article identity, correlation, body digest, body bounds and source pass their
checks. Completed replay, key conflicts and these input refusals create no
actual-work profile. A transport, safety or parser failure after work starts
can create an error profile. Typed fetch and parse failures still keep their
existing response behavior.

The profile uses the journal's captured run, correlation and request identity;
its observation clock is real UTC, not the captured planning clock. A report
callback receives only the locally validated resource metadata. Profile
controls stay outside the durable configuration fingerprint, so changing these
runtime controls does not invalidate a completed response or create a new
request. No ranking, selection, article text or source-status rule changes.
Unexpected collection or callback errors fail explicitly and do not commit a
successful response. As with any interrupted fetch, retry can repeat unfinished
external work.

## Design rationale

Separate endpoints let an operator inspect a real fetch before parsing it.
Identity-only references keep raw paths and untrusted page controls outside
the parse boundary. SQLite reuses Bun's bundled open-source storage engine
for atomic commit and process locking: no package, download or browser bytes
are added. Opaque response JSON is retained solely for exact HTTP replay,
not interpreted as new planning authority. A stopped plan is refused because
the existing native ledger writer and the request journal cannot share one
transaction; pretending otherwise would duplicate durable work.

A separate collector event loop is necessary because the actual parser can
block its own thread. Runtime reporting stays outside durable response bytes
so measurement cannot restamp a completed request or expose private content.

## See also

- [Planner execution](feed-plan-runner.md)
- [Harvesting](feed-harvesting.md)
- [Contract schemas](../contracts/schemas.md)
- [Isolated checks](../../how-to/run-feed-ingest-plan-test.md)
