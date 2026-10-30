# Running the isolated feed planner

**Last Updated**: 2026-10-30

How do the API and CLI execute one real feed plan?
Both compose the same units. The production Python news pipeline, digest
workers and published global health data are unchanged.

## Entry points and controls

From `services/feed-ingest-plan`, use `bun src/index.ts --serve` for the
loopback listener or `bun src/index.ts --cli` for an awaited one-shot run.
`config/feed-ingest-plan-service.json` supplies validated settings. Its service
flag defaults off until production use is approved.
Its `inputs.published_url_lookback_days` value overrides only the planner's
published-URL exclusion window; the global value remains unchanged for other
consumers. The local seven-day window is not the article-age limit.
`listener.max_body_bytes` limits incoming API request bodies.
`extract.max_body_bytes` limits fetched article response bytes.
`listener.parser_concurrency` controls concurrent article HTML parser workers,
not the number of feeds fetched.

The standalone health route reports listener availability and enablement.
The workflow child also reports its startup nonce, process ID and run identity.
The service owns its API code and workflow adapters. GitHub workflow YAML
calls `services/feed-ingest-plan/scripts/`; no native API depends on
`.github/scripts/`. The two independent experiment files retained there
do not supply API execution, history, verification or reporting.
The workflow entry is `scripts/run-feed-ingest-plan.ts`. Preparation lives in
`scripts/feed-ingest-plan-workflow-inputs.ts`: it stages bounded history,
enables only this invocation and captures identity, effective policy and host
evidence. `scripts/feed-ingest-plan-http-client.ts` calls an existing listener
and verifies retained output; it does not start or stop the listener. The entry
supervises `scripts/feed-ingest-plan-server.ts` as a separate child process in
one workflow step. It verifies private-pipe readiness against the child's
process ID, a fresh startup nonce, run, attempt, captured UTC clock and code
revision, then checks that the HTTP health response matches. An occupied port,
wrong identity, early child exit or expired readiness fails the step explicitly.
The same child handles planning and the health summary before shutdown.

The private startup pipe carries validated effective settings, a relative
temporary output root and scalar execution identity. The child reloads named
authored inputs, then reconstructs its fixed run-start clock and live selection
clock. No function, map, credential or article body crosses this pipe. Startup
data is not a saved artifact and is never accepted by an HTTP route. Plain
`--serve` does not stage history or supply workflow controls.

`supervision.readiness_timeout_ms` bounds startup and its health check.
`shutdown_timeout_ms` allows graceful drain after success, failure, cancellation
or pipe closure. `forced_exit_timeout_ms` bounds the supervisor's wait after
killing only its owned child. Defaults allow 30 seconds for readiness, 10 seconds
for drain and 5 seconds to confirm forced exit. The child also applies its own
drain bound if its supervisor disappears. No process is detached, no process
name is used for cleanup, and runner process tracking remains enabled.
`POST /api/2026-10-20/plan` accepts optional numeric `article_limit`, `shards`,
a configured partition strategy, and `institutional_age_hours`,
`trade_press_age_hours`, `community_age_hours` arrays. Each age array is a
strictly increasing nonempty list of positive hours. Unknown fields, strings in numeric API
fields, invalid counts and null controls fail before work. CLI blanks mean
omission. There is no date control.

An article limit bounds the chosen result, not the offered input. Age eligibility
uses the run's effective source-based age windows, resolved before article
fetching and reused by screening, selection and reporting. An omitted age
array retains that bucket's configured windows. Strategy `none` requires one
worker; other counts obey configured partition bounds, currently one through
twenty with four by default. `partition.enabled=false` bypasses worker
assignment without bypassing article selection.

## Real composition and identity

The router dispatches to execution modules. `/plan` calls the stage APIs over
the trusted local listener using validated JSON requests and outcomes. HTTP
is transport, not process isolation or an external message broker.
One collection owns one parsed batch for every configured feed, its offers,
terminal outcomes, identity, effective policy and cancellation.
Selection waits for all required feed and article work. It cannot select a
single feed's partial input. When partitioning is enabled, its HTTP request
follows selection. When disabled, there is no partition request: selected
metadata keeps null worker assignments. Health recording and selected output
are independent writes; useful selected output survives a health-save refusal.

One execution has isolated run identity, attempt, clocks, counters, timings
and batches. Run start supplies the accounting date. The saved parsed age
clock is D19; the fresh selection/feedback clock is D22. Actual HTTP and feed
work use their own UTC occurrence dates, including work after midnight.
The workflow supplies the retry attempt as execution metadata; local runs use
the first attempt. The caller supplies the producer identity at runtime when
it has one; the standalone runner uses its named default. Neither value is a
service setting.
Elapsed duration comes from the monotonic process clock, not wall-clock
subtraction. A restarted standalone chain records unavailable total duration
as null.

The [shared health operation](planner-feed-history.md) captures pre-fetch
rest evidence and refreshes current feedback before selection. Its complete
measured cost belongs in `plan-runs`, without per-candidate history reads
or a persistent summary cache.
New timing entries name these purposes `feed-health-before-fetch` and
`feed-health-for-selection`. Their names, not their positions, identify them.
Selected publication fallback uses the same saved selection-start instant,
after admission; the older saved age clock and first sight are unchanged.

## Concurrency and ownership

There is no all-runs readiness chain. Independent plans and document
requests can progress together. Configured pools bound permitted requests
and history reads. One listener shares `listener.parser_concurrency`
native HTML workers; concurrent requests do not each create another full
pool. CLI work can own a pool for its own lifetime.

Workers use the actual extractor and sanitizer. Fetch precedes its parse.
One request's cancellation or failed worker must not close another request's
jobs. Listener shutdown closes its owned workers; an injected pool remains
with its caller.

The workflow forwards termination to its cancellation signal and closes the
startup pipe in `finally`. The child observes EOF as well as termination signals,
stops accepting requests, cancels parsing and drains its listener. If drain does
not finish within the configured bound, the child exits and the supervisor
reaps it, using a forced kill only if needed. Completed response and health files
remain in the temporary run directory for the unchanged finalization, report,
artifact and recovery tasks. A planning failure remains a failed workflow.

## First sight and retained output

Discovery records global earliest sight by canonical URL key, independent of
the feed that encountered it. Named files and native indexes bound its
configured lookback. Missing history does not prove absence. Current real
sightings can be saved without pretending that missing days were empty.

The chosen result produces metadata-only Parquet and one text-bearing
artifact. Health is batched by execution and actual UTC work day. A small
run row records completed, partial or failed outcome, including an explicit
empty result. The [ledger reference](../../reference/feed-planner-ledgers.md)
owns the exact fields and row identities.

Only sparse body-free progress and failure events leave the runtime. Each JSONL
line has a strict run envelope and a flexible `details` object; callers may
name required detail keys for an event. The publisher marks missing requested
keys or unsafe details with `details._compliance.status` set to
`NON_COMPLIANT`, and does not include rejected values in that marker. Unknown
detail keys are allowed. Caller-supplied HTTP URLs and detail keys for article
text, bodies, policies, headers, credentials or URLs are refused. Details are limited to
4,096 bytes, six levels, 128 values, 128 characters per key and 512 characters
per string. The document execution unit emits one started and one completed
or failed event for each fetch or parse, both in `/plan` and standalone calls.
It names the server-owned request and article identity, `feed_id` and
`publisher_id`. `scope: document` identifies this work; `scope: plan` identifies
aggregate orchestration, not a second fetch of that document. Worker callbacks
do not emit duplicate lifecycles. Started events have null duration; terminal
events measure elapsed milliseconds, including time waiting for a parser.
Persistence emits its lifecycle around the actual write, including standalone
requests; replay does not repeat completed work.

Article fetch and parse failure events alone may include `details.article_url`.
The execution unit supplies this address separately from flexible details.
The publisher removes its query and fragment, rejects credentials and signed
or token-bearing addresses, and refuses non-HTTP addresses. Started and
completed events never include article URLs. Caller-provided URL fields,
article bodies, credentials and reserved compliance markers remain refused.
Logged addresses are diagnostic data, never inputs to fetching, files or commands.

The progress report reads the event array from the current run. No later run
reads archived JSONL, so the event shape can move without a history migration.
The report displays flexible details and warns when the publisher marks an
event non-compliant.
Completed earlier files are retained after a later failure.

## Design rationale

The maintainer-directed change on 2026-10-29 permits diagnostic article
addresses only on fetch/parse failures, replacing the former blanket refusal.
The separate publisher argument prevents arbitrary details from granting that
permission. Existing document execution owns progress instead of adding a
second API wrapper or another worker event stream. This also reports empty
article extraction as failed instead of reporting only a completed worker.
The strict envelope remains shared; details remain flexible rather than
operation-specific schemas.

One supervised step gives the child the same lifetime as the HTTP client
without losing in-memory batch references between planning and health reporting.
Startup is a transient native payload, not a ledger, because no later run reads
it. Pipe closure gives the child a cleanup signal even when the supervisor
cannot deliver termination. Planning stages use actual HTTP calls to that listener. The CLI and direct
library entry start an owned ephemeral loopback listener for their stage calls
and stop it after finalization. Completed stages proceed immediately; neither
HTTP nor parser deadlines impose a minimum duration.

Native workers provide real extraction overlap rather than promises around
synchronous DOM work. Separate execution state prevents concurrent plans
from mixing data or clocks. Explicit independent outputs preserve useful work
without reporting a failed stage as completed planning.

Maintainer decision, 2026-10-27 UTC: the isolated planner uses a local
seven-day published-URL exclusion window. The global 730-day setting remains
unchanged for its other readers. Seven days permits the same URL to be selected
again after that window; the separate article-age limit remains unchanged.

## See also

- [Operator APIs](feed-operator-api.md)
- [Policies](feed-ingest-policies.md)
- [Planning completion](feed-ingest-audit.md)
- [Isolated workflow](../../how-to/run-feed-ingest-plan-test.md)
