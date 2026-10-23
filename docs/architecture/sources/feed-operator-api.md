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
All recorded instant strings use UTC with `Z`.

## Durable replay and interrupted requests

The operator APIs write `planner-operations.sqlite` under `outputRoot`, the
same operator-configured root that holds native planner output.
Pydantic's `PlannerOperation` and `FetchedDocument` declarations own the
stored records; small Zod copies are bound by the existing native contract
comparison. They are new dated contracts, so no older shape needs migration.
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

## Design rationale

Separate endpoints let an operator inspect a real fetch before parsing it.
Identity-only references keep raw paths and untrusted page controls outside
the parse boundary. SQLite reuses Bun's bundled open-source storage engine
for atomic commit and process locking: no package, download or browser bytes
are added. Opaque response JSON is retained solely for exact HTTP replay,
not interpreted as new planning authority. A stopped plan is refused because
the existing native ledger writer and the request journal cannot share one
transaction; pretending otherwise would duplicate durable work.

## See also

- [Planner execution](feed-plan-runner.md)
- [Harvesting](feed-harvesting.md)
- [Contract schemas](../contracts/schemas.md)
- [Isolated checks](../../how-to/run-feed-ingest-plan-test.md)
