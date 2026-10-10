# Telemetry

**Last Updated**: 2026-10-10

How the pipeline records progress, timings and outcomes. Logs explain a running process; committed, validated rows supply later runs and operator views.

Storage and publication are being migrated to [telemetry intent](telemetry-intent.md). Read [the ledger registry](../architecture/contracts/ledger-registry.md) for current paths. New charts fetch and query their data in the browser; remaining projections and prerendered data routes are known migration work, not patterns to extend. The ledgers `ledger.published` names reach the site as copies, not projections: the build copies their compact files whole, every column included, and the repository that commits them is public, so none of their columns is private ([what the site holds for the door](../architecture/publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)).

## The envelope

Nested events use `{ ts, src, v, run, name, level, ctx, data }`.

| Field | Meaning |
| --- | --- |
| `ts` | Event instant in UTC |
| `src` | Emitting stage or subsystem |
| `v` | Envelope version |
| `run` | Run identity |
| `name` | Declared event name |
| `level` | Severity |
| `ctx` | Stable item, source and model context |
| `data` | Event-specific values |

The typed helper in [telemetry/events.py](../../backend/idhazh/telemetry/events.py) builds the envelope. `ctx` and `data` vary by event. A log envelope is not a persisted payload contract; a row a later process reads is.

## Event names

Every listed name has an emitter. [The vocabulary test](../../backend/tests/test_telemetry.py) holds this list to `EventName`.

### The two nested events

- `item.summarize.failed`: the model request did not produce a summary. Record the typed failure and exception type.
- `item.visual.failed`: an attempted picture did not land. The item may publish without it; distinguish that failure from a deliberate no-picture result.

### The six flat records

- `item.start`: the item entering work.
- `stage.done`: a named stage completed, including call identity and prompt/reply counts where applicable.
- `model.waiting`: an active request's elapsed wait. `logging.waiting_heartbeat_seconds` controls the interval; zero disables it.
- `item.done`: a settled success or failure.
- `item.abandoned`: an item the shard ended without attempting.
- `shard.done`: totals, failures by code and the slowest item.

Flat records carry envelope fields and cells at one level. Their item cells use `ItemHealthRow` names; the emitter rejects undeclared names. Stage, call, waiting, shard-summary and request-capture fields are declared explicitly by the helper. Do not invent log-only spellings for an existing measurement.

## The span tree

`observability.tracing_enabled` controls tracing. A span records a start instant, duration and parent, so a reader can inspect a slow sub-step rather than only a stage total. Disabling tracing writes no traces and must not change pipeline results.

The tree includes item, fetch, robots, extract, tag, summarize, render-prompt, model-call, parse-reply, score and visual-planner work. [telemetry/spans.py](../../backend/idhazh/telemetry/spans.py) owns the exact vocabulary.

A model-call span is a generation with model identity and token counts. Prefill and decode are reported durations on it, not child spans: the server reports those totals after the request, without independently measured start instants.

### Text never leaves the process

This rule applies to telemetry capture, not to the article's authorized model request.

- Record only declared attribute keys and validated values: digests, counts, flags and closed names.
- Do not put article text, prompts, replies, URLs, titles, request headers or secrets in span attributes.
- Record full UTF-8 SHA-256 digests and lengths when the question is whether two inputs were identical.
- Reject invalid attributes rather than silently dropping them.
- Exercise the leak checks with real injection fixtures. A shape check alone cannot detect article text that happens to match an allowed token shape.

### Where a span goes

Tracing writes a local file that the run commits under `state/traces/`. There is no hosted collector, telemetry SDK, destination environment variable or second export path. A run does not depend on a tracing service being available.

## The committed traces, briefly

Raw traces retain nesting for recent-run inspection. Their layout is `state/traces/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.jsonl`; each line is one span. The `traces` gardener task removes expired files according to `config/gardener/traces.json`.

Delete expired traces rather than summarising them again. Item health keeps the stage measurements the console needs. No publication gate or reader page may depend on a raw trace being present. A gap before tracing was enabled is missing instrumentation, not zero work.

`idhazh telemetry item <item_id> --date YYYY-MM-DD` prints the item's settled
health rows and each matching trace tree. The date is required and means UTC.
Health uses the shared ledger reader, including packed days, months and years.
The command reads trace files from that day alone and applies the current
retention in `config/gardener/traces.json`, even when expired files remain.
Missing or expired traces leave health visible with a reason.

Trace groups name the run, attempt, job and shard in deterministic order.
Older filenames that did not record an attempt or job label those as unknown.
Settled health is not attributed to an attempt. Parent links preserve nesting;
two item passes remain separate lines and their elapsed times are never added.

## The item-level census

Item health records every planned item, including failures and items not attempted. Keep the denominator beside the outcomes.

The worker seals a validated row while it can still observe host samples, request waits and model timings. Worker publication and assemble prefer that same row. Reconstruct from article and summary payloads only when the sealed row is missing, and leave unobservable cells absent.

Workers file settled items. Assemble accounts for missing work after it knows what arrived. Shared ledger identity and settlement rules prevent the two writers or a retry from counting one item twice. [Item health](../architecture/sources/item-health.md) owns column meanings and failure codes.

## What the machine was doing

Sample changing host conditions around the item they describe. Do not substitute a shard average for an item's CPU or memory reading. A missing operating-system reading stays absent and must not fail the item.

Read fixed host facts once per job. The host-fingerprint row records machine capabilities, probe results and job-level counters; the item row records conditions during its own work. Join them through their declared identities rather than repeating fixed host facts on every item.

[Host metrics](../reference/host-metrics.md) defines the columns. [Pipeline cost](../reference/pipeline-cost.md) defines valid rate and memory comparisons.

## No network sink

- Backend logging goes to stderr through standard-library logging, configured once at the entry point. Plain command logs format timestamps in UTC with a trailing `Z`. GitHub Actions retains that stream as the job log.
- Frontend logging goes to the browser console. Do not add a beacon, collector request or runtime analytics SDK.
- Never log credentials, signed URLs or request headers.
- Tests may replay captured structured events without a network connection.

## Logs are not the record

Logs and raw traces help explain an execution. They expire. Facts required by later runs or operator charts belong in validated committed payloads, not in a log scraper. Pipeline correctness must be independent of tracing.

## One writer, one grain, one ladder

A record's grain is what one row describes: an item, an observation, a feed, an address, a shard or a day. Keep separate records when their identities or retention needs differ. A feed that returned no items cannot be represented by an item row; a publication-membership record must not disappear when detailed item measurements expire.

Reuse the [persistence API](../architecture/contracts/persistence.md), not a second writer or path formula. Use the registry for paths and configured lifecycle rules for retention. Compact only when the result preserves the questions readers need to answer. Do not merge records merely because they sit under the same directory.

### Where a judging night files what it measured

File a measurement by what it describes, not by which workflow executed it. The council records whether work started, finished or timed out. Each judge records its own selections, verdicts and quality measurements. A holdout score of a judge's output belongs to that judge, not to the council that scheduled it.

The [council contract](../architecture/publishing/llm-council.md) and ledger registry own the exact shapes and paths. Keep judge-specific fields out of the shared council outcome.

## Design rationale

Structured events share names with the data they describe, so logs and records cannot quietly drift into different vocabularies. Spans add timing structure that flat rows cannot express. Item health keeps stage measurements; short-lived traces keep recent detail. One persistence path controls storage without forcing unrelated populations into one row shape.

The Pipelines page does not print robots, tag, prompt-render or reply-parse
totals. Those timings sit inside stages already shown and lose the item and
attempt when added across a shard. The eight item-stage fields and the main
timeline remain. An operator inspects a particular item's parent-linked trace
instead; expired detail is reported as unavailable, never reconstructed from
settled health or treated as zero. No extra committed aggregate or public
payload is needed for that question.

On 2026-10-02, miztiik authorized merging this retirement while a content run
was active, after all CI checks passed. This was a one-time exception to the
retirement's quiet-window requirement. An older run retains its checkout and
may still attempt to publish the removed files; new runs neither read nor
write them. The exception grants no permission to cancel a run or rewrite
history.

## See also

- [telemetry-intent.md](telemetry-intent.md) - required storage and browser design.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - item outcomes and columns.
- [../architecture/contracts/persistence.md](../architecture/contracts/persistence.md) - writing and reading records.
- [../architecture/contracts/ledger-registry.md](../architecture/contracts/ledger-registry.md) - current paths and identities.
- [../reference/host-metrics.md](../reference/host-metrics.md) - host readings.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - checks.
