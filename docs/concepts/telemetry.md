# Telemetry

**Last Updated**: 2026-08-30

The structured-event vocabulary: the envelope every event carries, the event names that are emitted, and the rule that there is no network sink. "Telemetry" here means a **local, structured log**; it is not a runtime analytics SDK, which is a project non-goal ([principles.md](principles.md), [../../CLAUDE.md](../../CLAUDE.md) section 0a).

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

Because every event is a plain serializable payload, a captured stream is a fixture: it can be replayed and asserted against in tests with no mocks and no network (Rule #7).

## Logs are not the record

The distinction that matters operationally: a log line is **evidence of what happened**, while a committed artifact or ledger row is **the record of what happened**. CI logs age out. If a later run, a dashboard or a human needs a fact, that fact belongs in the item-health ledger, the eval ledger or the run manifest - not in a log line somebody would have to go find.

## Design rationale

Logging the emitted envelope, rather than a separate hand-written message, exists so a log and a persisted payload can never disagree - the classic debugging failure where the log says one thing and the file on disk says another. The cost is that log lines are structured rather than chatty; the benefit is that they are greppable, replayable, and true. Authority: Fowler.

Treating the Actions run log as the log store, rather than shipping logs anywhere, is what keeps Rule #1 intact end to end: a project with no runtime backend should not acquire one for observability. Authority: Carmack.

**The envelope stopped calling itself a contract on 2026-08-30.** This page said it was "a persisted surface with its own schema, stamped and evolved like any contract", and there was no such model under `backend/idhazh/contracts/` and no such file under `schemas/`. The claim also contradicted this page's own doctrine two sections down: a log line is evidence and a ledger row is the record, and a record earns a schema where evidence does not. What the sentence reached for was real, so it was replaced rather than dropped. One typed helper now builds every envelope, which gives a shape nobody persists the same guarantee a schema gives one somebody does. The name list was cut on the same day and for the same reason: 20 names with one emitter reads as a promise, not as a vocabulary. Authority: Fowler, 2026-08-30.

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

## See also

- [pipeline-loop.md](pipeline-loop.md) - the stages a run moves through.
- [config.md](config.md) - the log level, which is the only knob logging has.
- [evaluation.md](evaluation.md) - the ledger that IS the record, as distinct from the log.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the item-level census ledger.
- [principles.md](principles.md) - principle 9, logging is local by construction.
- [../../CLAUDE.md](../../CLAUDE.md) - section 1b (logging) and the no-telemetry-SDK non-goal (section 0a).
