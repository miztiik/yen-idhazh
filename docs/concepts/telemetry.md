# Telemetry

**Last Updated**: 2026-08-23

The structured-event vocabulary: the envelope every event carries, the standard event names, and the rule that there is no network sink. "Telemetry" here means a **local, structured log**; it is not a runtime analytics SDK, which is a project non-goal ([principles.md](principles.md), [../../CLAUDE.md](../../CLAUDE.md) section 0a).

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
| `name` | The event name, from the catalog below. |
| `level` | Severity. |
| `ctx` | Stable context - the item's content address, the source, the model reference. |
| `data` | The event-specific payload. |

`ctx` and `data` are open objects on purpose: their keys vary by event, and pinning them would force a schema bump every time a stage records a new piece of context. The fixed, typed part is the envelope.

The envelope is a persisted surface with its own schema, stamped and evolved like any contract - see [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md). This page fixes the shape and the names; the schema owns the field types.

## Standard event names

A stage is observable the moment it emits these; there is no central switch statement to edit.

**Run level:**

- `run.started` / `run.completed` / `run.partial`

**Stage level:**

- `stage.started` / `stage.completed` / `stage.failed`

**Item level:**

- `item.collected`
- `item.extracted` / `item.truncated` / `item.extract.failed`
- `item.summarized` / `item.summarize.failed`
- `item.scored` / `item.flagged`
- `item.routed` / `item.rendered` / `item.render.failed`
- `item.skipped` (already present from an earlier run)

The item-level names are what make a run auditable per item; the run-level names are what make a partial day a fact with a date rather than something a human notices later.

The item-health ledger is the durable item-level census. It records every
planned item as `ok` or `failed`, with a closed `FailureCode` vocabulary. A log
line is evidence that the event happened; the ledger row is the record a later
run or dashboard reads.

## No network sink

There is no runtime call home (Rule #1), and there is nowhere to send a log even if there were:

- **Backend, developer machine** - structured records to stderr through the standard library `logging` module, configured once at the entry point. A developer reads them in the terminal. Level from [config.md](config.md); default `INFO`.
- **Backend, CI** - the same stderr stream. GitHub Actions captures and retains it with the run, and **that IS the log store.** Nothing is uploaded anywhere else. Anything a later run needs to read is a committed artifact or a ledger row, never a log line.
- **Frontend** - the browser console, and only the browser console. A published page logs what a reader would need to hand back when something looks wrong. No SDK, no beacon, no `fetch` to a collector.

**Secrets never reach a log record.** Not a token, not a signed URL, not a request header.

Because every event is a plain serializable payload, a captured stream is a fixture: it can be replayed and asserted against in tests with no mocks and no network (Rule #7).

## Logs are not the record

The distinction that matters operationally: a log line is **evidence of what happened**, while a committed artifact or ledger row is **the record of what happened**. CI logs age out. If a later run, a dashboard or a human needs a fact, that fact belongs in the eval ledger or the run manifest - not in a log line somebody would have to go find.

## Design rationale

Logging the emitted envelope, rather than a separate hand-written message, exists so a log and a persisted payload can never disagree - the classic debugging failure where the log says one thing and the file on disk says another. The cost is that log lines are structured rather than chatty; the benefit is that they are greppable, replayable, and true. Authority: Fowler.

Treating the Actions run log as the log store, rather than shipping logs anywhere, is what keeps Rule #1 intact end to end: a project with no runtime backend should not acquire one for observability. Authority: Carmack.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| A hosted log sink or error-tracking SDK | Reverses Rule #1 and adds a dependency, a secret and a bill to a project that has none of the three. | Carmack |
| A separate human-readable log format alongside the structured one | Two records of one event, free to disagree, and the disagreement always surfaces at the worst moment. | Fowler |
| Free-text log messages | Not greppable, not replayable as a fixture, and impossible to assert on in a test. | Fowler |
| Keeping run history in logs rather than the ledger | CI logs age out. A trend you cannot query in a year is not a measurement (Rule #10). | Fowler |

## See also

- [pipeline-loop.md](pipeline-loop.md) - the stages that emit these events.
- [config.md](config.md) - the level and emit knobs.
- [evaluation.md](evaluation.md) - the ledger that IS the record, as distinct from the log.
- [../architecture/sources/item-health.md](../architecture/sources/item-health.md) - the item-level census ledger.
- [principles.md](principles.md) - principle 9, logging is local by construction.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the event-envelope schema.
- [../../CLAUDE.md](../../CLAUDE.md) - section 1b (logging) and the no-telemetry-SDK non-goal (section 0a).
