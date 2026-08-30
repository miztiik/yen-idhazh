# Telemetry

**Last Updated**: 2026-08-30

The structured-event vocabulary: the envelope every event carries, the event names that are emitted, the span tree a developer can switch on, and the rule that there is no network sink. "Telemetry" here means a **local, structured log**; it is not a runtime analytics SDK, which is a project non-goal ([principles.md](principles.md), [../../CLAUDE.md](../../CLAUDE.md) section 0a).

This page is the concept-tier statement of the logging doctrine in `CLAUDE.md` section 1b.

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

**The envelope is not a persisted contract and it has no schema.** A log line is evidence and not a record ([Logs are not the record](#logs-are-not-the-record)), so nothing under `schemas/` owns these field types and nothing should. What holds the shape instead is one typed helper, `telemetry.event()`, that every emitter calls. This page fixes the shape and the names; that function is the only place either is built.

## Event names

One name is emitted:

- `item.summarize.failed` - the model was asked and did not answer. `ctx` carries the item, the source and the model reference; `data` carries the typed failure code and the exception type.

`telemetry.EventName` holds that name and nothing else, and a test fails when this list and that vocabulary disagree in either direction. A name is added in the commit that emits it.

**This list held 20 names until 2026-08-30, and 19 of them had no emitter.** They were not a backlog and they were not lost by accident - see [Rejected alternatives](#rejected-alternatives).

## The span tree

A second shape of evidence, off by default, and the only one that carries a start instant and a parent.

`observability.tracing_enabled` is false in the committed config. Turned on, a work shard opens a span per stage and one per sub-step, and writes one JSON line per span to `backend/var/traces/<date>/<run>-<shard>.jsonl`. That directory is gitignored, nothing downloads it and no page can read it.

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
| `route` | - | - |

**`model_call` is a generation**, the span subtype a tracing tool draws differently. It carries the model reference and the token counts. **Prefill and decode are attributes on it and not child spans**: llama-server reports both as totals in the reply, after the call returned, so nothing can be wrapped around either. A span drawn around a duration reported retrospectively is a shape nobody measured.

### Text never leaves the process

This is the Rule #11 boundary and it is the reason the span tree is built the way it is rather than the way a tracing SDK's quickstart builds it.

- **The attribute vocabulary is closed.** `telemetry.AttrKey` lists every name a span may carry, and a name absent from it cannot be recorded at a call site. There is no `input`, no `output`, no `url`, no `title` and no `detail`.
- **Every value is a digest, a count, a flag or a closed name.** `telemetry.attribute` refuses a string over 64 characters - one SHA-256 digest - and refuses anything that is not lowercase and unspaced. It raises rather than dropping: every value is built from a validated payload by our own code, so a refusal is a programming error.
- **Where the text would go, a digest and a count go.** `source_digest`, `prompt_digest` and `output_digest` are SHA-256 over UTF-8 in full, the convention `idhazh.fingerprint.text_digest` already sets. They answer the question a stored prompt would have answered - did we send the same bytes twice - and they answer nothing else.
- **The guard is a test, not a note.** `backend/tests/test_spans.py` runs a whole work stage over pages carrying a planted sentinel, captures every attribute of every span, and asserts the sentinel appears in none of them. `backend/tests/test_canaries.py` runs the same sweep over all five committed injection canaries. A single leaked character fails the build.

The second sentinel in that test is deliberate: one is a sentence, which the shape rule refuses on the space alone, and one is a lowercase unspaced token the shape rule would accept. The second is what makes the test measure the structural control rather than the regex.

### Where a span goes

**A local file by default. A host is opt-in, through the environment.** Owner decision, 2026-08-30.

A run writes to the file whenever tracing is on. It additionally sends to a Langfuse host only when `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are all set - all three, checked separately, so a half-configured environment is a file-only run rather than a failure inside the client. No workflow sets any of them and CI holds no such secret, so an ordinary run reaches no third party whatever the toggle says.

`langfuse` is an optional extra and is not in `.[dev]`. Measured 2026-08-30 (Windows 11, Python 3.14.2, three clean venvs): **32,656,612 installed bytes** and **260.9 s to install**, spread 24.9 s over n=3. Two thirds of the bytes are the three OpenTelemetry distributions the client is built on. A missing package degrades to the file sink and logs that it did; it never stops a run (section 1a).

Two things the host sink does not do, measured against Langfuse 4.14.4 rather than assumed:

- **It does not reproduce the nesting on the host.** A child span closes before its parent, so when a child is handed over its parent has no handle yet and the SDK generates its own span ids. The file keeps the exact tree; the host gets one trace per item with the parent named on each observation.
- **It does not send a completion start time.** The reply carries prefill and decode as totals and no first-token instant, so the field would be a number we invented.

## The item-level census

The item-health ledger is the durable item-level census. It records every
planned item as `ok` or `failed`, with a closed `FailureCode` vocabulary. A log
line is evidence that the event happened; the ledger row is the record a later
run or dashboard reads.

Two stages write that census, and one row identity keeps them from disagreeing.

A worker commits the rows for its own items as soon as each one settles. Until
it did, a shard's verdicts left the runner only inside a run artifact that
expires in a day and is skipped entirely when a job is cancelled - so a run
stopped between the workers and the publish had measured every item and recorded
none of it. A bad day is exactly the day worth measuring.

Assemble then writes the whole day's census, including a `not_attempted` row for
every planned item no article payload arrived for. That keeps the denominator in
the same file as the failure count.

**A row is one planned item on one run**: `(date, run_id, item_id)`. The ledger
filters on that identity before it writes, so assemble's copy of a row the worker
already committed is the same row and lands once. That filter is what makes a
second writer safe: `merge=union` keeps the lines from both sides rather than
collapsing them, the published projection copies every row into the file the
console reads, and an append-only ledger cannot correct a row afterwards.

A worker records only items that have settled. An item whose summary payload is
simply not written yet was interrupted, not failed, and assemble classifies it
later once the difference no longer matters.

## No network sink

There is no runtime call home (Rule #1), and there is nowhere to send a log even if there were:

- **Backend, developer machine** - structured records to stderr through the standard library `logging` module, configured once at the entry point. A developer reads them in the terminal. Level from [config.md](config.md); default `INFO`.
- **Backend, CI** - the same stderr stream. GitHub Actions captures and retains it with the run, and **that IS the log store.** Nothing is uploaded anywhere else. Anything a later run needs to read is a committed artifact or a ledger row, never a log line.
- **Frontend** - the browser console, and only the browser console. A published page logs what a reader would need to hand back when something looks wrong. No SDK, no beacon, no `fetch` to a collector.

**Secrets never reach a log record.** Not a token, not a signed URL, not a request header.

The span tree is the one thing here that CAN reach a host, and it is off, opt-in, and carries no text - see [Where a span goes](#where-a-span-goes). It does not reverse this section: with `tracing_enabled` false, which is the committed default, there is nothing to send and nothing that could send it.

Because every event is a plain serializable payload, a captured stream is a fixture: it can be replayed and asserted against in tests with no mocks and no network (Rule #7).

## Logs are not the record

The distinction that matters operationally: a log line and a span are **evidence of what happened**, while a committed artifact or ledger row is **the record of what happened**. CI logs age out and `backend/var/` is thrown away with the checkout. If a later run, a dashboard or a human needs a fact, that fact belongs in the item-health ledger, the eval ledger or the run manifest - not in a log line or a span somebody would have to go find.

**No page reads a trace and no gate depends on one.** The whole test suite passes with tracing on and with it off, and that is asserted rather than assumed.

## Design rationale

Logging the emitted envelope, rather than a separate hand-written message, exists so a log and a persisted payload can never disagree - the classic debugging failure where the log says one thing and the file on disk says another. The cost is that log lines are structured rather than chatty; the benefit is that they are greppable, replayable, and true. Authority: Fowler.

Treating the Actions run log as the log store, rather than shipping logs anywhere, is what keeps Rule #1 intact end to end: a project with no runtime backend should not acquire one for observability. Authority: Carmack.

**The envelope stopped calling itself a contract on 2026-08-30.** This page said it was "a persisted surface with its own schema, stamped and evolved like any contract", and there was no such model under `backend/idhazh/contracts/` and no such file under `schemas/`. The claim also contradicted this page's own doctrine two sections down: a log line is evidence and a ledger row is the record, and a record earns a schema where evidence does not. What the sentence reached for was real, so it was replaced rather than dropped. One typed helper now builds every envelope, which gives a shape nobody persists the same guarantee a schema gives one somebody does. The name list was cut on the same day and for the same reason: 20 names with one emitter reads as a promise, not as a vocabulary. Authority: Fowler, 2026-08-30.

**The span tree was adopted on the owner's reasoning and not on the engineering case.** Three personas judged Langfuse against this project alone and refused it: the ledgers already hold the split, and a third-party client is a dependency, a default that publishes text, and a thing to keep working. The owner's argument is different and was not one they were briefed on - the skill and the code transfer to a future repository, and that is worth paying for. What that argument does NOT do is relax Rule #11, which is why the row's acceptance test is the leak guard and not the span tree. Authority: owner, 2026-08-30.

**One claim made when the row was planned turned out to be wrong, and it is recorded because it shaped a decision.** The plan said that Langfuse being OpenTelemetry underneath made the local file sink "a configuration rather than a second code path". It is not. The `Langfuse` client is wired to the OTLP HTTP exporter and a Langfuse host; getting a file out of it means either taking the OpenTelemetry SDK as a direct dependency - the thing that was rejected - or writing the sink. So the sink is written, in about thirty lines of standard library, and that is what makes the default path free of the optional package and testable with no network. Measured against Langfuse 4.14.4, 2026-08-30. The version in the plan was also stale: it said v3, and the client is v4.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A hosted log sink or error-tracking SDK | Reverses Rule #1 and adds a dependency, a secret and a bill to a project that has none of the three. | Carmack |
| A separate human-readable log format alongside the structured one | Two records of one event, free to disagree, and the disagreement always surfaces at the worst moment. | Fowler |
| Free-text log messages | Not greppable, not replayable as a fixture, and impossible to assert on in a test. | Fowler |
| Keeping run history in logs rather than the ledger | CI logs age out. A trend you cannot query in a year is not a measurement (Rule #10). | Fowler |
| Scraping item failures back out of logs | The workers already hand Assemble typed payloads. A log scraper would make evidence pretend to be the record. | Fowler |
| The OpenTelemetry SDK, taken directly | What it sells is a wire protocol to a collector, and Rule #1 forbids the collector. Its span attributes also carry the prompt by default, and this repository is public, so a default left alone is a Rule #11 breach with no undo. It is taken instead inside Langfuse's Python client, which is built on it - one dependency rather than two for one span tree - and the conditions ride with it: off in CI, digests and counts where the text would go, and the ledgers stay the record. | Andre, Carmack and Fowler, 2026-08-30 |
| Writing emitters for the 19 event names this page used to list | Every fact they would report is already in the item-health ledger, the eval ledger or the run manifest, and a CI log expires in two days. It is 19 emitters written into a store that forgets, beside a record that does not. | Fowler, 2026-08-30 |
| Sending `input` and `output` as the Langfuse client intends | They are free text, its own decorator fills them with the prompt and the completion, and this repository is public - so a default left alone republishes article bodies, which section 0a forbids outside `corpus/`. Both fields are passed explicitly as null, the attribute bag rides in `metadata`, and the client's own `mask` hook is wired to refuse whatever it is handed. | Andre, 2026-08-30 |
| Tracing on by default, or on in CI | A publish job that can fail on a third party's availability, for a view nothing in the job reads. Off is also what means CI needs no secret. | Carmack, 2026-08-30 |
| Making a span a committed record | A fourth record of the same run, free to disagree with the other three. The ledgers stay the record and a span stays evidence. | Fowler, 2026-08-30 |
| Reproducing the nesting on the host with the SDK's own context managers | It works, and it costs a second code path for a sink that is opt-in and untestable here (no test touches the network, Rule #7). The file sink keeps the exact tree; the host gets one trace per item with the parent named. | Carmack, 2026-08-30 |

## See also

- [pipeline-loop.md](pipeline-loop.md) - the stages a run moves through.
- [config.md](config.md) - the log level, which is the only knob logging has.
- [evaluation.md](evaluation.md) - the ledger that IS the record, as distinct from the log.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the item-level census ledger.
- [principles.md](principles.md) - principle 9, logging is local by construction.
- [../../CLAUDE.md](../../CLAUDE.md) - section 1b (logging) and the no-telemetry-SDK non-goal (section 0a).
