# Telemetry

**Last Updated**: 2026-09-16

The structured-event vocabulary: the envelope every event carries, the event names that are emitted, the two shapes those names take, the span tree a developer can switch on, and the rule that there is no network sink. "Telemetry" here means a **local, structured log**; it is not a runtime analytics SDK, which is a project non-goal ([principles.md](principles.md), [../../CLAUDE.md](../../CLAUDE.md) section 0a).

This page is the concept-tier statement of the logging doctrine in `CLAUDE.md` section 1b.

The code is [`backend/idhazh/telemetry/`](../../backend/idhazh/telemetry/), and its modules are this page's sections: `events.py` for the log line, `spans.py` for the span tree, `sinks.py` for where a span goes, `rollup.py` for the committed fold, `traces.py` for where a committed trace lands, and `census.py` for the item-level census.

## One event, one payload, one log line

The pipeline is event-driven: a stage consumes one validated payload and emits another ([pipeline-loop.md](pipeline-loop.md)). The logging rule falls straight out of that - **a stage logs the same structured envelope it emits.** There is no second, prettier, human-oriented log format that can disagree with the persisted record about what happened.

## The envelope

Every event is one flat, serializable payload with a fixed envelope:

`{ ts, src, v, run, name, level, ctx, data }`

| Field | Meaning |
| --- | --- |
| `ts` | Timestamp of the event. |
| `src` | The stage or subsystem that emitted it. |
| `v` | Envelope version, so a reader can evolve its parsing. |
| `run` | The run this event belongs to, so a day's records group. |
| `name` | The event name, from the vocabulary below. |
| `level` | Severity. |
| `ctx` | Stable context - the item's content address, the source, the model reference. |
| `data` | The event-specific payload. |

`ctx` and `data` are open objects on purpose: their keys vary by event, and pinning them would force a schema bump every time a stage records a new piece of context. The fixed, typed part is the envelope.

**The envelope is not a persisted contract and it has no schema.** A log line is evidence and not a record ([Logs are not the record](#logs-are-not-the-record)), so nothing under `schemas/` owns these field types and nothing should. What holds the shape instead is one typed helper, `telemetry.event`, that every emitter calls. This page fixes the shape and the names; that function is the only place either is built.

## Event names

**Two shapes, one vocabulary.** Every name below is an `EventName`, and which shape a name takes is fixed: `telemetry.FLAT_RECORDS` holds the six that are flat records and `telemetry.event` refuses any of them. A reader never has to guess which shape a line is, because the name decides it.

### The two nested events

These carry the `{ ctx, data }` envelope above.

- `item.summarize.failed` - the model was asked and did not answer. `ctx` carries the item, the source and the model reference; `data` carries the typed failure code and the exception type.
- `item.visual.failed` - the marks compiled and the file did not land. `ctx` carries the item, its content address and the model reference; `data` carries the visual state and the exception type. The item publishes without its picture, so nothing else records this: a planner that correctly found nothing to draw and a disk that would not take the file look identical on the page, and `VisualDecision.none_reason` only separates them for a reader who already has the day's payload open.

### The six flat records

Added 2026-09-15. A 5x model-time regression ran for six days unnoticed: nothing printed during a 200-minute shard, and the one line that did fire per item fired only for items that passed. These are what a shard says while it is still running.

- `item.start` - which item is in flight. A shard killed on its timeout names the item it died on.
- `stage.done` - one named stage ended. `stage` says which; a model call also carries `call`, the prompt's SHA-256 and the character counts of what crossed the wire.
- `model.waiting` - a model call is still in flight, and for how long. Every `logging.waiting_heartbeat_seconds`; `0` turns it off.
- `item.done` - the item ended, for a failure exactly as for a success.
- `item.abandoned` - the shard ended before this item ran.
- `shard.done` - the shard's totals, its failures counted by code, and its slowest item.

**A flat record is one line of `{ envelope } | { cells }` with no nesting, and the cells are `ItemHealthRow`'s own column names.** That is the whole design: `grep` and `jq` both work on it without a path expression, and a field called one thing in the log and another in the census is impossible because the vocabulary is derived from the row rather than restated. `telemetry.events.record` refuses a cell name the row does not declare, so a typo fails the run rather than minting a field nobody reads.

Ten cells are not census columns: `stage`, `call` and `waited_s` say which record this is, `items`, `failures` and `slowest` are the shard's totals, and `prompt_sha256`, `prompt_chars`, `reply_chars` and `captured` say what crossed the wire. **`prompt_sha256` is the one fact here the census row cannot hold**, because putting it there needs `Summary` widened too - the assemble stage builds the row from the summary payload and the summary carries no prompt digest.

`telemetry.EventName` holds those names and nothing else, and a test fails when this list and that vocabulary disagree in either direction. A name is added in the commit that emits it.

**This list held 20 names until 2026-08-30, and 19 of them had no emitter.** They were not a backlog and they were not lost by accident - see [Rejected alternatives](#rejected-alternatives).

## The span tree

A second shape of evidence, on by default since 2026-09-06, and the only one that carries a start instant and a parent.

`observability.tracing_enabled` is true in the committed config (2026-09-06 - see [Design rationale](#design-rationale)). A work shard opens a span per stage and one per sub-step and writes one JSON line per span to the committed trace under `state/traces/`, so a recent run stays openable from the repository and a rolling window bounds it - see [The committed traces, briefly](#the-committed-traces-briefly). The switch is still real: turned off, a shard traces into a sink that drops every span and writes neither a trace nor a rollup.

**What a span buys that a ledger column does not**, stated so the feature can be judged: a start instant, a parent, and a step too small to earn a column of its own. `fetch_ms`, `extract_ms` and `summarize_ms` already split an item three ways. What they cannot say is which of these took the time:

| Span | Nests inside | The question no column answers |
| --- | --- | --- |
| `item` | - | the whole item, twice: the work stage fetches every item, then summarizes them in a different order |
| `fetch` | `item` | - |
| `robots` | `fetch` | whether the first item from a host paid for a slow `robots.txt` that the next twenty did not |
| `extract` | `item` | - |
| `tag` | `extract` | whether a taxonomy that grew a hundred patterns is what made extraction slower |
| `summarize` | `item` | - |
| `render_prompt` | `summarize` | how long building the JSON schema from the Pydantic model takes |
| `model_call` | `summarize` | the generation - see below |
| `parse_reply` | `summarize` | the verbatim check, which is the longest string comparison in the pipeline |
| `score` | `item` | - |
| `visual_planner` | `item` | what the picture's gate, ladder and render cost, after the summarize-and-plan call answered |

**`model_call` is a generation**, the span subtype a tracing tool draws differently. It carries the model reference and the token counts. **Prefill and decode are attributes on it and not child spans**: llama-server reports both as totals in the reply, after the call returned, so nothing can be wrapped around either. A span drawn around a duration reported retrospectively is a shape nobody measured.

### Text never leaves the process

This is the Guardrail #11 boundary and it is the reason the span tree is built the way it is rather than the way a tracing SDK's quickstart builds it.

- **The attribute vocabulary is closed.** `telemetry.AttrKey` lists every name a span may carry, and a name absent from it cannot be recorded at a call site. There is no `input`, no `output`, no `url`, no `title` and no `detail`.
- **Every value is a digest, a count, a flag or a closed name.** `telemetry.attribute` refuses a string over 64 characters - one SHA-256 digest - and refuses anything that is not lowercase and unspaced. It raises rather than dropping: every value is built from a validated payload by our own code, so a refusal is a programming error.
- **Where the text would go, a digest and a count go.** `source_digest`, `prompt_digest` and `output_digest` are SHA-256 over UTF-8 in full, the convention `idhazh.fingerprint.text_digest` already sets. They answer the question a stored prompt would have answered - did we send the same bytes twice - and they answer nothing else.
- **The guard is a test, not a note.** `backend/tests/test_spans.py` runs a whole work stage over pages carrying a planted sentinel, captures every attribute of every span, and asserts the sentinel appears in none of them. `backend/tests/test_canaries.py` runs the same sweep over all five committed injection canaries. A single leaked character fails the build.

The second sentinel in that test is deliberate: one is a sentence, which the shape rule refuses on the space alone, and one is a lowercase unspaced token the shape rule would accept. The second is what makes the test measure the structural control rather than the regex.

### Where a span goes

**A committed file by default. A host is opt-in, through the environment.** Owner decision, 2026-08-30.

A run writes to the committed trace under `state/traces/` whenever tracing is on. It additionally sends to a Langfuse host only when `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are all set - all three, checked separately, so a half-configured environment is a file-only run rather than a failure inside the client. No workflow sets any of them and CI holds no such secret, so an ordinary run reaches no third party whatever the toggle says.

`langfuse` is an optional extra and is not in `.[dev]`. Measured 2026-08-30 (Python 3.14.2, three clean venvs): **32,656,612 installed bytes** and **260.9 s to install**, spread 24.9 s over n=3. Two thirds of the bytes are the three OpenTelemetry distributions the client is built on. A missing package degrades to the file sink and logs that it did; it never stops a run (section 1a).

Two things the host sink does not do, measured against Langfuse 4.14.4 rather than assumed:

- **It does not reproduce the nesting on the host.** A child span closes before its parent, so when a child is handed over its parent has no handle yet and the SDK generates its own span ids. The file keeps the exact tree; the host gets one trace per item with the parent named on each observation.
- **It does not send a completion start time.** The reply carries prefill and decode as totals and no first-token instant, so the field would be a number we invented.

## The committed rollup

The span tree is evidence and expires with the run. One summary of it is a record and is committed: `state/span-rollup/<YYYY-MM>.csv`, one row per `(date, run_id, shard, span_name)`, carrying how many spans of that name the shard opened and how long they took added together. The fold lives in `telemetry.roll_up_spans` and the row is `SpanRollupRow`.

**It commits five span names, not the eleven the tracer opens**, and the five are the steps no ledger column already times:

| Committed span | Why it earns a row |
| --- | --- |
| `item` | the per-item wall clock the three stage columns never add into one |
| `robots` | the slow `robots.txt` read buried inside `fetch` |
| `tag` | the taxonomy match buried inside `extract` |
| `render_prompt` | building the JSON schema, buried inside `summarize` |
| `parse_reply` | the verbatim check, buried inside `summarize` |

The other six are left out because a ledger already holds their timing. `fetch`, `extract` and `summarize` are `fetch_ms`, `extract_ms` and `summarize_ms` on the item-health row; `score` is `score_ms` on the eval row; `visual_planner` is `decision_ms` on the visual decision; and `model_call` is `prefill_ms` plus `decode_ms`. A row for any of those would be a second account of a number a ledger already keeps.

**Every second of the shard is accounted for.** The `item` row carries one number more, `unattributed_ms`: the shard's wall clock minus the time inside its item spans. That residual is the overhead between and around items that no span covers - model load, file writes, scheduling. `item.total_ms` plus `unattributed_ms` is the shard's wall clock, so the rollup is self-checking; a set of spans that claims more time than the shard ran is unreconcilable and the fold raises rather than round the residual to zero. It rides on the `item` row alone - the one row a working shard always produces - and is null on the other four spans and on any row written before the column existed.

**The rollup is derived, and it restates nothing.** It is a fold of the shard's own spans, not a parallel record. Its three measured columns - `count`, `total_ms` and `unattributed_ms` - are held disjoint, outside the key, from the columns of every committed ledger by a contract-tier test ([`backend/tests/contracts/`](../../backend/tests/contracts/)). That disjointness is the whole reason a fold of the spans can be committed where a raw span cannot: it cannot disagree with the item-health, eval, runtime-counter or visual ledgers, because it shares no measurement with any of them.

**It costs the same on a busy day as an empty one** (Guardrail #12). The fold reads one shard's spans - a bounded input - and writes at most five rows per shard per run. A name the shard never opened produces no row rather than a zero, so an absent row reads as never opened and never as opened-and-measured-nothing.

## The committed traces, briefly

The rollup above is the **record** of a run and it lasts. A raw trace is **evidence with a short life**: the nested tree of spans an operator opens to walk one recent run step by step, for the question the rollup's per-stage totals cannot answer - which span inside a stage took the time. A short rolling window of the most recent runs is committed under `state/traces/<YYYY>/<MM>/<DD>-<run>-<shard>.jsonl`, one JSON line per span, so a recent run stays openable from the repository rather than being lost with a gitignored file or a CI artifact that expires in days. The date is spelled once: the `<YYYY>/<MM>/` directories and the `<DD>` prefix are the run's day, and the run slot is the ordinal alone.

**A trace is a lookup, so it is deleted rather than folded.** `retention.prune_traces` removes whole files whose published day is more than `observability.trace_window_days` behind today, and folds nothing - a summary of a raw trace would invent a total nobody reads, and the rollup already holds every total a reader asks for. It is the same shape as the `state/seen/` prune and for the same reason: a store nobody reads past a window is bytes answering no question, and its honest retention is deletion. There is no fuse, because the worst case is an operator losing a drill-down into a run that has already left the window, not a published byte - which is what the picture pruner's fuse exists to protect.

**Bounded by construction** (Guardrail #12). The window makes the cost constant: at most `trace_window_days` days of traces on disk, whatever the project's age. Measured 2026-09-06 (Python 3.14.2, a real traced run over the committed fixture, n=3, deterministic to two bytes): about 2,943 bytes an item across the nine work spans, so a run at the 160-item `run.safety_ceiling_per_run` ceiling then in force wrote about 0.47 MB of work spans, a little more with the score and visual spans; the ceiling has since come down to 80, which roughly halves that. Over the five scheduled runs a day and the default seven-day window, `state/traces/` stays bounded well under 21 MB - a fraction of the 1 GB Pages reference it is not even part of, since `state/` is committed but never published. The default is seven days, a week of runs; `observability.trace_window_days` is the knob.

A trace is committed only while a run writes one, and a run writes one only with `observability.tracing_enabled` on - the committed default since 2026-09-06. A run before that day wrote none, so the window fills forward from the flip and never reaches behind it, which is [the discontinuity every panel must name](#design-rationale).

## The item-level census

The item-health ledger is the durable item-level census. It records every
planned item as `ok` or `failed`, with a closed `FailureCode` vocabulary. A log
line is evidence that the event happened; the ledger row is the record a later
run or dashboard reads.

Two stages write that census, and one row identity keeps them from disagreeing.

A worker commits the rows for its own items as soon as each one settles. Until
it did, a shard's verdicts left the runner only inside a run artifact that
expires and is never committed - so a run stopped between the workers and the
publish had measured every item and recorded none of it. A bad day is exactly
the day worth measuring.

Assemble then writes the whole day's census, including a `not_attempted` row for
every planned item no article payload arrived for. That keeps the denominator in
the same file as the failure count.

**A row is one planned item on one run**: `(date, run_id, item_id)`. The ledger
filters on that identity before it writes, so assemble's copy of a row the worker
already committed is the same row and lands once. That filter is what makes a
second writer safe: `merge=union` keeps the lines from both sides rather than
collapsing them, the published projection copies every row into the file the
console reads, and an append-only ledger cannot correct a row afterwards.

The filter reads the file the job checked out, and a checkout is pinned to the
commit its run was triggered at - so it cannot see a row a second attempt at the
same work pushed after that commit. The commit step settles the file again after
the merge, which is the only moment both attempts are in one place. Both halves
are needed: on 2026-08-31 the committed month held 44 keys twice, from one day
when only the first existed.

A worker records only items that have settled. An item whose summary payload is
simply not written yet was interrupted, not failed, and assemble classifies it
later once the difference no longer matters.

## What the machine was doing

A throughput number with no machine beside it is not a measurement (Guardrail
#10), so ten cells of the census row are about the host rather than the item:
the processor, the runner label, how busy that processor was across the item,
the one-minute load, three memory readings and what the kernel counted against
the job's memory limit.

`backend/idhazh/telemetry/host.py` is the only thing that reads them, and it
reads them for two consumers at two grains.

| Consumer | Grain | The question it answers |
| --- | --- | --- |
| the item row | one item | did this item meet a noisy neighbour? |
| `state/runtime-counters.csv` | one shard | what did the whole job cost, and does the census's own clock agree with the server's? |

**They stay two stores on purpose.** The counters row is the independent check on
the census's own timings, and a check folded into the thing it checks stops
being a check.

**The item row records the sample taken while that item ran, never the shard's
average.** An average says nothing about the item that was slow, which is the
whole question these cells exist to answer.

Three column names appear on both rows, and **two of the three are supposed to
differ**. `cpu_busy_pct` is one item's window on the item row and the whole
job's - cache restore and weight load included - on the shard row.
`cgroup_peak_bytes` is a high-water mark read at two different instants.
`cpu_model` is the third and it is not like the others: a processor does not
change inside a job, so two different answers would mean the host had been read
twice. Both rows take it from one `host_facts` call.

Every source is one local file read, and a reading that cannot be taken records
empty rather than failing the item. `/sys/fs/cgroup/memory.peak` has measured
absent on every GitHub-hosted runner this project has probed, so that cell is
usually empty in CI and always empty on a developer machine - a fact about the
instrument, not about the job. What one sample costs is in
[measurements.md](../reference/measurements.md).

## The visual ledger, and the eight terms that outlive it

`state/visuals/<YYYY-MM>.csv` is the third committed record here: one row per
**attempt** at a picture, not one per published visual. A per-publication ledger
would leave every refusal uncommitted, so the machine loop would stop being
auditable while still being the gate. `none` is the majority outcome by design,
which is exactly why a `none` with no recorded cause makes the largest number an
operator reads the one that explains nothing.

`observability.visuals_full_grain_months` is where that stops being readable
attempt by attempt. Past it the month folds to `state/visual-aggregate/` and the
attempts are deleted, so **what the fold keeps is the whole of what anybody can
ever ask of an old month.** That key is settled and it is eight terms:

| Half | Terms | The question it keeps answerable |
| --- | --- | --- |
| Cause | `date`, `decision`, `none_reason`, `rejection_reason` | which gate refused most, and which check inside the validator |
| Stratum | `potential_primary`, `family`, `element_band`, `downgrade_depth` | how the classes differ, and how the keep rate moved with downgrade depth |

The counts are stored and the rate is not: `attempts` and `published` can be
added across groups and a rate cannot, so a console divides rather than averaging
averages. Each measured column keeps a count, both ends and the three quartiles -
a **distribution and never a mean**, because a bimodal spread is the interesting
finding and a mean reports the empty middle between two clumps.

**Two columns carry a distribution, and a third was deliberately left out.**
`elements` is the raw count the band came from, so a reader keeps both the
stratum and the spread inside it. `marks` is the ladder's own currency - each
rung reads a percentile of the depth-0 published mark counts, so folding that
population away would leave every floor computed from nothing, which the ladder
reads as a refusal rather than as a fault. `decision_ms` is not one of them: how
long the planner took is the span tree's question, and this project holds a
committed rollup's measured columns disjoint from every ledger's for the reason
[the rollup restates nothing](#the-committed-rollup) gives.

**The fold is in `retention.fold_visual_month` and the pass that deletes is not
written yet**, because nothing writes the store. The key is settled first because
the fold is the one decision here that cannot be revised; the pass lands with the
writer. [adaptive-pruning.md](adaptive-pruning.md#the-visual-fold-key-is-eight-terms-and-it-could-not-wait)
carries the argument for each term and the measurement behind the bands.

## No network sink

There is no runtime call home (Guardrail #1), and there is nowhere to send a log even if there were:

- **Backend, developer machine** - structured records to stderr through the standard library `logging` module, configured once at the entry point. A developer reads them in the terminal. Level from [config.md](config.md); default `INFO`.
- **Backend, CI** - the same stderr stream. GitHub Actions captures and retains it with the run, and **that IS the log store.** Nothing is uploaded anywhere else. Anything a later run needs to read is a committed artifact or a ledger row, never a log line.
- **Frontend** - the browser console, and only the browser console. A published page logs what a reader would need to hand back when something looks wrong. No SDK, no beacon, no `fetch` to a collector.

**Secrets never reach a log record.** Not a token, not a signed URL, not a request header.

The span tree is the one thing here that CAN reach a host, and the host is opt-in and carries no text - see [Where a span goes](#where-a-span-goes). It does not reverse this section: tracing is on by default now, but a host is reached only when three environment variables are all set, no workflow sets them, and CI holds no such secret - so an ordinary run still sends nothing anywhere.

Because every event is a plain serializable payload, a captured stream is a fixture: it can be replayed and asserted against in tests with no mocks and no network (Guardrail #7).

## Logs are not the record

The distinction that matters operationally: a log line and a span are **evidence of what happened**, while a committed artifact or ledger row is **the record of what happened**. CI logs age out and `backend/var/` is thrown away with the checkout. If a later run, a dashboard or a human needs a fact, that fact belongs in the item-health ledger, the eval ledger or the run manifest - not in a log line or a span somebody would have to go find.

**No page reads a trace and no gate depends on one.** The whole test suite passes with tracing on and with it off, and that is asserted rather than assumed.

## One writer, one grain, one ladder

Thirteen stores under `state/` is not thirteen designs. It is six grains, and the sprawl that is real sits in the writers and the publishers rather than in the stores.

**A store's grain is its key, and a store keeps its own file only when its key is one no other store's key can hold.** That is the whole rule. Six keys qualify.

| Grain | Key | Stores |
| --- | --- | --- |
| item | date, run, item | `item-health` - the census |
| observation | address, output digest, scorer version | `scores`, `score-index` |
| address | url key | `seen`, `published`, `counterfactual-scores` |
| feed | run, feed | `feed-health`, `feed-retirements.csv` |
| shard and run | date, run, shard | `runtime-counters.csv`, `span-rollup`, `visual-prunes` |
| day | date | `day-metrics`, `day-validations.csv` |

**An item-grain ledger cannot hold a fact about a thing that was never an item.** A feed that returned nothing has no items, so its failure has no item row to sit on - and a feed returning nothing is the case `feed-health` exists for. `seen` holds 76,834 addresses against 12,217 planned items, six times the population, because most addresses were never planned. A candidate the ranker refused is the whole point of `counterfactual-scores` and is never planned either. Those are not sprawl; they are the questions an item row cannot answer.

**Age is the second reason a store keeps its own file.** `item-health` is a fourteen-month census, `seen` is a ninety-day lookup, `published` is an unbounded membership test. Fold stores with different windows together and exactly one window survives: keep ninety days and the census dies, keep fourteen months and a ninety-day lookup pays for fourteen. Estimated 2026-09-15 from today's rate held forward: folding `seen` into the census would take it from a flat 34 MB to about 162 MB, for a read that never looks past day 90.

**What is consolidated is the write path, not the row.** One constructor per grain, one append, one read, one fold, one projector. Where a second constructor already exists for the same grain it is a defect rather than a design, and the item grain has two. `telemetry/record.py` fills about 53 of the census columns as the work stage learns them and closes into a validated `ItemHealthRow`; `telemetry/census.py` builds the row again afterwards out of the article and the summary payloads, which carry none of those cells. Nothing keeps the recorder's row, so 70 of item-health's 113 columns are empty on every committed row and the second constructor is the one whose answer lands.

**The ladder is day, month, year, and each rung answers a different question.** Day files, because a day is the unit a prune deletes and the unit a window fetches - both stay cheap only while the file boundary is the day boundary. Month folds at `observability.item_health_full_grain_months`, because a trend over a year does not need every item. Year is unbuilt and stays unbuilt until a month fold is too big to read, which at kilobytes a month it is not.

**The published mirror is a redaction step, not a copy.** `state/` is committed and never published; `frontend/public/` is published and never holds a ledger. Between them sits a projection that drops the columns a reader may not have - `PublicTelemetryRow` exists to strip 77 of them. Calling the published copy pollution mistakes the safety control for the leak. What it costs is 8.8 MB of a 39.2 MB site, under 1 percent of the 1 GB cap, and it is bounded: `public_telemetry_keep_months` deletes a published month in the same pass that folds its source, so the mirror plateaus rather than grows. The site reaches its cap on pictures and stories, not on telemetry.

**A published payload with no reader is deleted rather than kept for later.** `scores/` and `feed-health/` were 6,455,733 bytes that no console route fetched, and on 2026-09-16 they went with their two projections. A mirror nobody reads drifts from the ledger it mirrors and nobody notices, which is the same failure as a column nobody writes. The ledgers under `state/scores/` and `state/feed-health/` stay - they are the record, and the console reads them at build time.

### What folds, what does not, and the test that decides

Read this table before proposing a merge. A store folds only when it fails **every** one of three tests: it must key on something that is always an item, keep the same window as the census, and hold no fact the census could not have recorded at write time.

| Store | Keys on | Window | Verdict |
| --- | --- | --- | --- |
| `item-health` | an item | 14 months | **the census.** Whatever folds, folds here |
| `visual-prunes` | a run | with the pictures | **FOLD** into a run-grain ledger beside `runtime-counters`. 41 rows, and a run is not an item |
| `validation-<date>.csv` | a model | never | **RETIRE.** Four rows with a date in the filename. The numbers belong in the measurement record |
| `day-validations.csv` | a day | with the day | **KEEP**, move to day files. A receipt is not an item |
| `scores` | an observation | 14 months | **KEEP.** One item holds several rows - re-measurement is the point, and an item key allows only one |
| `score-index` | a digest | with the scores | **KEEP.** 76 bytes an observation against 819 for a census row. Reading the wide store to answer a narrow question costs 10.8 times more |
| `seen` | an address | 90 days | **KEEP.** 76,834 addresses against 12,217 planned items. Most were never planned, so most can never have a row |
| `counterfactual-scores` | a candidate | with the scores | **KEEP.** The refused candidates are the point, and a refused candidate is never planned |
| `feed-health` | a feed | with the feeds | **KEEP.** A feed that returned nothing has no items, and that is the case it exists for |
| `feed-retirements.csv` | a feed | never | **KEEP flat.** A fact with no day does not belong in a day tree |
| `runtime-counters.csv` | a shard | 14 months | **KEEP**, move to day files. It is the independent check on the census's own timings, and a check folded into the thing it checks stops being one (Guardrail #10) |
| `span-rollup` | a shard and a span | 14 months | **KEEP.** Its columns are held disjoint from every ledger's by a contract test, which is what lets a fold of spans be committed at all |
| `traces` | a shard | 7 days | **KEEP.** Evidence, not a record. Deleted rather than folded |
| `published` | an address | never | **KEEP - see below.** The one that looks foldable and is not |

**`published` is derivable from the census for fourteen months and undecidable after that, so it stays.** A `stage=publish, outcome=ok` row carries the same fact, so the derivation is real - but the census folds to month grain at `observability.item_health_full_grain_months` and the item rows are deleted, while `published` has no window at all (`collect.published_window_days` is `-1`). A store that forgets cannot be the guard against publishing something twice. A surgical prune keyed on the row's own date does not rescue it: the question is not which rows to delete, it is which rows must never be deleted, and that set is all of them.

There is a second reason, and it bites in production rather than in year two. A run that dies after the workers and before assemble leaves rows reading `stage=publish, outcome=ok` for a day that never published. `published` records what the digest actually carried. Derive one from the other and a resumed run republishes a story a reader has already seen.

## Telemetry optimisation options

**None of these is decided, and each names what is not yet known.** They are recorded together so the next pass starts from a list rather than from a rediscovery.

| Option | What it would buy | What is not known yet |
| --- | --- | --- |
| Fill the census columns the run already computes | 58 of the 70 empty columns, from values the process holds and discards | Nothing blocking. The cost is one commit, not a measurement |
| Fold `visual-prunes` and `runtime-counters` into one run-grain ledger | one store and one writer instead of three | whether the month fold can carry two row shapes without a second fold path |
| Move the three flat files to day trees | a store `idhazh telemetry prune` can reach, since that command takes a day file out and has no way to rewrite a row out of a flat one ([../architecture/publishing/retention.md](../architecture/publishing/retention.md#a-named-prune-one-store-one-range-of-days-2026-09-16)) | the one-time migration's cost, and whether any reader assumes a single file |
| Compress the published projections | **measured 2026-09-15: 6,720,442 bytes of 8,726,606, 77.0 percent**, with no new dependency ([../reference/measurements.md](../reference/measurements.md#what-compressing-the-telemetry-takes-against-re-encoding-it-2026-09-15)) | whether every console fetch path handles the encoding. One build settles it. `span-rollup/` is 67 bytes and gzips to 77, so a switch has to leave a file alone where compressing it does not pay |
| Re-encode every closed-vocabulary column as an ordinal integer | **measured 2026-09-15: 369,855 bytes of `state/item-health/`, 7.1 percent** - a ninth of what compressing the same files takes, and it costs a legend shipped beside the data and `grep failed` over a committed day | nothing. It is priced and deferred: compression is taken first, and an ordinal taken first would be re-encoded when compression lands |
| A query engine over a rolling month index, in the browser | one fetch instead of a month of rows | the engine's wire size. The month it would replace is no longer an estimate: `telemetry/2026-09.csv` is 1,186,543 bytes and gzips to 254,252 |
| A year rung on the fold ladder | a shape for year-over-year | nothing, until a month fold is too big to read. At kilobytes a month it is not |

**Further research is needed before the last four land.** Each is a design with a price nobody has paid to find out, and an unmeasured number may not justify a design (Guardrail #10).

## Design rationale

Logging the emitted envelope, rather than a separate hand-written message, exists so a log and a persisted payload can never disagree - the classic debugging failure where the log says one thing and the file on disk says another. The cost is that log lines are structured rather than chatty; the benefit is that they are greppable, replayable, and true. Authority: Fowler.

Treating the Actions run log as the log store, rather than shipping logs anywhere, is what keeps Guardrail #1 intact end to end: a project with no runtime backend should not acquire one for observability. Authority: Carmack.

**The envelope stopped calling itself a contract on 2026-08-30.** This page said it was "a persisted surface with its own schema, stamped and evolved like any contract", and there was no such model under `backend/idhazh/contracts/` and no such file under `schemas/`. The claim also contradicted this page's own doctrine two sections down: a log line is evidence and a ledger row is the record, and a record earns a schema where evidence does not. What the sentence reached for was real, so it was replaced rather than dropped. One typed helper now builds every envelope, which gives a shape nobody persists the same guarantee a schema gives one somebody does. The name list was cut on the same day and for the same reason: 20 names with one emitter reads as a promise, not as a vocabulary. Authority: Fowler, 2026-08-30.

**The span tree was adopted on the owner's reasoning and not on the engineering case.** Three personas judged Langfuse against this project alone and refused it: the ledgers already hold the split, and a third-party client is a dependency, a default that publishes text, and a thing to keep working. The owner's argument is different and was not one they were briefed on - the skill and the code transfer to a future repository, and that is worth paying for. What that argument does NOT do is relax Guardrail #11, which is why the row's acceptance test is the leak guard and not the span tree. Authority: owner, 2026-08-30.

**One claim made when the row was planned turned out to be wrong, and it is recorded because it shaped a decision.** The plan said that Langfuse being OpenTelemetry underneath made the local file sink "a configuration rather than a second code path". It is not. The `Langfuse` client is wired to the OTLP HTTP exporter and a Langfuse host; getting a file out of it means either taking the OpenTelemetry SDK as a direct dependency - the thing that was rejected - or writing the sink. So the sink is written, in about thirty lines of standard library, and that is what makes the default path free of the optional package and testable with no network. Measured against Langfuse 4.14.4, 2026-08-30. The version in the plan was also stale: it said v3, and the client is v4.

**A fold of the spans became a committed record on 2026-09-06, and it is not the fourth record the table below rejects.** The veto was against committing a raw span as a parallel account of a run - a shape free to disagree with the item-health, eval and runtime-counter ledgers. The rollup cannot disagree with them: a contract test holds its columns disjoint from theirs, so it carries a per-span count and duration no ledger holds and nothing else. What made a raw span a fourth record - restating a number three files already keep - is exactly what the disjointness check forbids. So the fold is committed and the raw span stays evidence under `backend/var/`. Authority: Fowler, pseudo-plan sections 14.4 and 14.4a, 2026-08-30.

**The rollup became self-checking on 2026-09-06T15:00, and where the residual lives was the real decision.** A rollup that only says how long each step took cannot say whether the steps add up to the shard's wall clock, so time could go missing between items and nothing would catch it. `unattributed_ms` closes that: `item.total_ms` plus `unattributed_ms` is the wall clock the shard ran, and the fold refuses a set of spans that claims more. The residual is a per-shard quantity, so it needs exactly one row per shard to live on; the `item` span is the shard's top-level span and the one row every rollup already carries, so the residual rides there, null on the four sub-steps and null on any row an earlier run wrote - which is what keeps the field additive, with no read-side migration. It is reported as its own number and never folded into the nearest stage's total: a stage that absorbed the leftover would read as slower than it was, and the leftover is the shard's, not the stage's. Authority: Fowler on the contract shape, Andre on reporting the residual rather than absorbing it, 2026-09-06.

**Tracing switched on by default on 2026-09-06, and the CI hazard that kept it off never applied to the file sink.** It was off because a publish job that can fail on a third party's availability is a worse job (below) - but that hazard is the *host*, and CI never had the host: no workflow sets the three Langfuse variables and CI holds no such secret, so a traced run in CI writes the committed file and reaches nothing. On by default is what makes the committed trace and the span rollup exist for the runs a reader actually looks at, rather than only for a developer who remembered to export a variable. The runner cost is negligible - Carmack measured the span collection at about one part in 128,000 of a shard's time. Guardrail #11 still holds it safe: the attribute vocabulary is closed, and `backend/tests/test_spans.py` and `backend/tests/test_canaries.py` now run that guard in CI over real spans. Authority: owner, 2026-09-06.

**The flip is a discontinuity, and every panel that plots a span number must name it.** A committed rollup row exists only from 2026-09-06 forward, because no run before that day wrote one. A sub-step series that begins on the flip date is the instrument switching on, not the pipeline slowing down, and a chart that reads the gap as a regression is reading an artefact of the switch. The date is recorded as a discontinuity in [`../reference/measurements.md`](../reference/measurements.md), for the same reason a hardware change is.

**The rollup measured nothing for nine days, and the cause was a path nobody named.** From 2026-09-06 every shard folded its spans and appended `state/span-rollup/<YYYY-MM>.csv` into its own checkout. No commit step staged that path, so each fold died with its runner; assemble, on another machine, projected a directory that had never existed and published a header row. Nothing failed and no test was red - the instrument ran, cost what it cost, and reported nothing. `state/traces/` was missed the same way and by the same list: `stage_work` opens a file sink onto it whenever tracing is on, and nothing staged it either, so the raw evidence the fold is taken from never survived its runner. The fix is both paths in the work job's commit step, a seed in each so `git add` under `set -euo pipefail` cannot abort the step on a fresh clone, and both in assemble's refresh set so a lost race does not let the union merge double the rows. The lasting part is the test: the stores a stage writes are now read out of the stage and compared against the paths the job stages, so the two lists cannot drift again. Authority: Carmack found the rollup, 2026-09-15.

**One ledger for everything was proposed on 2026-09-15 and narrowed to one write path.** The owner's case was that the sprawl is real and that item-grain, day-filed data is the right shape for this project - which is correct, and is why `item-health` is the census. What the measurement refused was folding the other stores into it: three of them key on something that was never an item, and three more carry a different retention, so a single store would have to keep one window and lose the questions the others answer. The part of the intent that survives whole is the part that was costing something - one constructor per grain instead of two, one publisher instead of seven, and the ladder written down so a later rung is a decision rather than a discovery. Authority: owner set the intent; Fowler ruled the grains; Carmack priced the windows. 2026-09-15.

**A query engine in the browser is a good idea that is not due yet, and the margin is wider than the estimate said.** A rolling one-month index queried on the reader's machine would replace fetching a month of rows - but the engine is 2 to 10 MB over the wire against a published month that **gzips to 254,252 bytes, measured 2026-09-15**, so it costs between 8 and 39 times what it saves at today's volume. The engine's size is still an estimate; the month is not. The cheap 77 percent is compressing the projection, which needs no dependency. Revisit when a month passes about 50 MB, which needs roughly four times today's items a day - `run.safety_ceiling_per_run` is 80 and forbids it. Authority: Carmack, 2026-09-15.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A hosted log sink or error-tracking SDK | Reverses Guardrail #1 and adds a dependency, a secret and a bill to a project that has none of the three. | Carmack |
| A separate human-readable log format alongside the structured one | Two records of one event, free to disagree, and the disagreement always surfaces at the worst moment. | Fowler |
| Free-text log messages | Not greppable, not replayable as a fixture, and impossible to assert on in a test. | Fowler |
| Keeping run history in logs rather than the ledger | CI logs age out. A trend you cannot query in a year is not a measurement (Guardrail #10). | Fowler |
| Scraping item failures back out of logs | The workers already hand Assemble typed payloads. A log scraper would make evidence pretend to be the record. | Fowler |
| The OpenTelemetry SDK, taken directly | What it sells is a wire protocol to a collector, and Guardrail #1 forbids the collector. Its span attributes also carry the prompt by default, and this repository is public, so a default left alone is a Guardrail #11 breach with no undo. It is taken instead inside Langfuse's Python client, which is built on it - one dependency rather than two for one span tree - and the conditions ride with it: off in CI, digests and counts where the text would go, and the ledgers stay the record. | Andre, Carmack and Fowler, 2026-08-30 |
| Writing emitters for the 19 event names this page used to list | Every fact they would report is already in the item-health ledger, the eval ledger or the run manifest, and a CI log expires in two days. It is 19 emitters written into a store that forgets, beside a record that does not. | Fowler, 2026-08-30 |
| Sending `input` and `output` as the Langfuse client intends | They are free text, its own decorator fills them with the prompt and the completion, and this repository is public - so a default left alone republishes article bodies, which section 0a forbids outside `corpus/`. Both fields are passed explicitly as null, the attribute bag rides in `metadata`, and the client's own `mask` hook is wired to refuse whatever it is handed. | Andre, 2026-08-30 |
| Tracing on by default, or on in CI (2026-08-30) | Rejected then as a publish job that could fail on a third party's availability, for a view nothing in the job reads. Reversed 2026-09-06: the hazard was the host, and CI has no host - the sink there is the committed file, no key, no third party (see Design rationale). | Carmack 2026-08-30; owner 2026-09-06 |
| Sampling the span collection | The committed rollup is folded from every span to reconcile the shard's wall clock, so dropping any span breaks that reconciliation. The collection cost is negligible in any case - Carmack measured it at about one part in 128,000 of a shard. | owner, 2026-09-06 |
| Committing a raw span as a record | A fourth account of the same run, free to disagree with the other three. A *derived* fold that restates nothing is the committed rollup above; a raw span stays evidence under `backend/var/`. | Fowler, 2026-08-30 |
| Reproducing the nesting on the host with the SDK's own context managers | It works, and it costs a second code path for a sink that is opt-in and untestable here (no test touches the network, Guardrail #7). The file sink keeps the exact tree; the host gets one trace per item with the parent named. | Carmack, 2026-08-30 |
| One ledger at item grain, every other store folded into it | Three stores key on something that was never an item - a feed that returned nothing, an address nobody planned, a candidate the ranker refused - so no item row can hold their facts. Three more carry a different retention, and a merged store keeps one window and loses the rest. The write path consolidates; the row does not. | Fowler and Carmack, 2026-09-15 |
| Taking telemetry off the published site to save the size budget | It is under 1 percent of the cap and already plateaus at its retention, and there is no server - so removing it leaves the console with nothing to fetch and no month control. The projection is also the redaction step that strips 77 columns from the ledger. What could go was the 6,455,733 bytes no route read, and that went on 2026-09-16. | Carmack and Susan, 2026-09-15 |
| Keeping `scores/` and `feed-health/` published in case somebody fetches them | Searched the built bundle on 2026-09-16 - 357 emitted files, 70 of them client chunks - and no chunk a browser loads names either path. The cost of being wrong is one re-publish; the cost of keeping them was two projections maintained for nobody, drifting unwatched from the ledgers they mirrored. | Susan, 2026-09-16 |
| A query engine shipped to the browser over a rolling month index | The engine is 2 to 10 MB over the wire against a published month that gzips to 254,252 bytes, measured 2026-09-15 - 8 to 39 times what it saves. It costs more than it saves until a month passes about 50 MB, which the per-run item ceiling forbids. Compress the projection instead. | Carmack, 2026-09-15 |
| A year rung on the fold ladder, built now | A month fold is kilobytes. A rung that folds nothing anybody struggles to read is a store to keep working for no question. | Fowler, 2026-09-15 |

## See also

- [pipeline-loop.md](pipeline-loop.md) - the stages a run moves through.
- [config.md](config.md) - the log level, which is the only knob logging has.
- [evaluation.md](evaluation.md) - the ledger that IS the record, as distinct from the log.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the item-level census ledger.
- [principles.md](principles.md) - principle 9, logging is local by construction.
- [../../CLAUDE.md](../../CLAUDE.md) - section 1b (logging) and the no-telemetry-SDK non-goal (section 0a).
