# Running the isolated feed planner

**Last Updated**: 2026-10-28

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

The health route reports listener availability and enablement only.
The service owns its API code and workflow adapters. GitHub workflow YAML
calls `services/feed-ingest-plan/scripts/`; no native API depends on
`.github/scripts/`. The two independent experiment files retained there
do not supply API execution, history, verification or reporting.
The workflow entry is `scripts/run-feed-ingest-plan.ts`. Preparation lives in
`scripts/feed-ingest-plan-workflow-inputs.ts`: it stages bounded history,
enables only this invocation and captures identity, effective policy and host
evidence. `scripts/feed-ingest-plan-http-client.ts` calls an existing listener
and verifies retained output; it does not start or stop the listener. The entry
still owns same-process listener startup and shutdown, including the health
summary request before shutdown.
`POST /api/2026-10-20/plan` accepts optional numeric `freshness_hours`,
`article_limit`, `shards` and a configured partition strategy. Unknown fields,
strings in numeric API fields, invalid counts and null controls fail before
work. CLI blanks mean omission. There is no date control.

An article limit bounds the chosen result, not the offered input. Freshness
changes the age cutoff without changing recency half-life. Strategy `none`
requires one worker; other counts obey the configured partition bounds.

## Real composition and identity

The router dispatches to execution modules. Internal stages exchange
validated serializable payloads. `/plan` does not call itself over HTTP.
Permitted fetching supplies parsed candidates and actual work facts;
selection waits for the complete eligible input and current health;
partitioning waits for that selection. Health recording may overlap
partitioning, and independent selected output survives a health-save refusal.

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

Only sparse body-free progress and failure events leave the runtime.
There are no exported full work events, archived parsed/rejected populations,
classification products, per-operation ledgers or full-audit receipt graph.
Article parser start events carry no duration; completion and failure events
carry elapsed milliseconds measured from the worker's start response.
Completed earlier files are retained after a later failure.

## Design rationale

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
