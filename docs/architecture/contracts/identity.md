# Identity contracts

**Last Updated**: 2026-11-04

How files, work units, content, event occurrences and operations retain distinct identities.

This page owns identifier meanings across Python and TypeScript. File storage follows
[persistence.md](persistence.md); declared payloads follow [schemas.md](schemas.md).

---

## 1. What an identifier addresses

Table A - distinct identities

| ID | Identifier | Generation | What it identifies |
| --- | --- | --- | --- |
| A1 | Ledger `unit_id` | UUIDv5 from the fixed namespace and work seed | Repeatable work, unchanged across retries. |
| A2 | Ledger `file_id` | UUIDv8 under the writer's file contract | One physical file, not an event or operation. |
| A3 | Article, URL and offer identities | Their declared SHA-256 encodings | Content or a domain item, not an execution. |
| A4 | Native TypeScript event `source + id` | Configured producer URI reference and a fresh lowercase UUIDv4 | One event occurrence; replay retains the saved envelope. |
| A5 | Native TypeScript `traceId` | Nonzero 16 random bytes, encoded as 32 lowercase hexadecimal characters | One execution. |
| A6 | Native TypeScript `spanId` | Nonzero 8 random bytes, encoded as 16 lowercase hexadecimal characters | One operation within that execution. |
| A7 | Python protocol identifiers | The owning Python contract's UUID rules | Foreign caller, execution and operation identities; see section 6. |

---

## 2. Unit Identity (`unit_id`)

The `unit_id` answers: **which work unit does this record belong to?**

- **Namespace UUID**: `de055294-e352-5d65-a1b7-d14b5e20844d`. The committed namespace seed in `backend/idhazh/ledger/filenames.py` and `packages/ledger-file-writer/src/uuid/unit-id.ts` remains unchanged. It is a protocol constant: changing it would break the identity of earlier work.
- **Seeding string**:
  ```
  {ledger}|{covers}|{run_id}|{job}|{shard}|{producer}
  {ledger}|{covers}|{run_id}|{pipeline_name}|{task_name}|{shard}|{producer}
  ```
  The first form is the legacy job identity. The second identifies a pipeline task.
- **Invariance**: When a GitHub Action job fails and is re-run, GitHub preserves the `run_id`. The re-run produces the identical `unit_id`.
- **Compaction resolution**: The ledger compaction union keeps the highest `attempt` for each `unit_id`, cleanly replacing earlier attempts without duplicates.

---

## 3. File Identity (`file_id`)

The `file_id` answers: **which physical file is this on disk?**

Each raw file carries its own `file_id`, used as its filename:
```
state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet
```

### Generic writer UUIDv8 layout

The Python ledger door and the matching generic TypeScript writer use this
RFC 9562 layout:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   unix_ts_ms (high 32 bits)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   unix_ts_ms (low 16 bits)    |  ver (0x8)    |  rand_a (12)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|var (0b10)|                   rand_b (62 bits)                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       rand_b (continued)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

1. **High 48 bits**: Current UTC instant as epoch milliseconds (`Date.now()` or `written_at_ms`). Guarantees lexicographical and directory sorting by time.
2. **Version nibble (4 bits)**: `0x8` (UUIDv8).
3. **Random bits**: Derived from `SHA-256("{unit_id}|{attempt}|{written_at_ms}")`.
   - `rand_a` (12 bits): The low 12 bits of digest bytes 0 and 1.
   - `variant` (2 bits): `0b10` (RFC 4122/9562 standard variant).
   - `rand_b` (62 bits): The low 62 bits of digest bytes 2 through 9.

Python (`backend/idhazh/ledger/filenames.py`) is the identity authority. The reusable TypeScript writer implements the same bit packing in `packages/ledger-file-writer/src/uuid/`.

The native planner's physical-file contract remains separate: ordinary planner
files combine the UTC millisecond clock with random UUIDv8 suffix bits; rejected
raw files use the existing schema/day/content digest encoding. Neither algorithm
changes when operation metadata changes.

---

## 4. Native TypeScript event and operation metadata

Event envelopes follow CloudEvents 1.0. Operation metadata follows OpenTelemetry
identifier and relationship names. Propagation follows W3C Trace Context. These
contracts do not enable runtime tracing. Project aliases for the standard
identifiers are not supported.

The shared contracts live in `packages/common-contracts/src/schemas/`.
`OperationMetadataSchema` contains `traceId`, `spanId`, optional `parentSpanId`,
`links` and optional `traceState`. A root has no parent; a child keeps its
parent's execution and receives a different operation ID. A link contains a
producing operation's `traceId` and `spanId` and may cross executions.
Parentage describes enclosing work, not every completed input.

`CloudEventSchema` defines one structured JSON profile: `specversion: "1.0"`,
`id`, `source`, `type`, `time`, `datacontenttype: "application/json"`,
`traceparent`, optional `tracestate`, and `data`. Event `time` is the actual UTC
occurrence instant, not an operation start or duration. Several occurrences can
share the same operation. Standard carrier spellings appear only at the event
or transport boundary; the native operation uses the names above.

Project schema date stamps and changelogs are attached to the schemas. They do
not replace CloudEvents `specversion`. These are current-only profiles: readers
validate the saved envelope and its application data without migration,
backfill or retrospective identifier conversion.

### Creation, reading and propagation

`createRootContext({ links?, traceState? })` creates a new execution and operation.
`createChildContext(parent, { links? })` creates an operation inside the supplied
parent. Both validate metadata; generated identifiers retry an all-zero value,
and a child also retries its parent's operation ID. There is no mutable current
context, tracing provider or import-time allocation.

`createCloudEvent({ source, type, context, data, parseData })` creates a new
UUIDv4 occurrence and current UTC instant for an existing operation.
`readCloudEvent(saved, parseData)` preserves the saved identity, time and carrier.
Both take the application's real `(value: unknown) => T` validator, so service
schemas need not cross Zod major versions. A saved event is not recreated by a
factory.

`readTraceContext(carrier)` and `writeTraceContext(context)` use
`W3CTraceContextPropagator`, not a local header parser. The reader returns no
context for an absent or invalid optional parent. Valid state is retained through
the codec; native `traceState` is its serialized form. Locally emitted carriers
use version `00` and unsampled flags `00`. Callers derive a child or start a root
explicitly; these identifiers grant no authorization or request replay promise.

`loadEventSources(path)` explicitly reads
`config/typescript-event-sources.json`, written by this repository. It validates
the named TypeScript API server, planner, summarizer and workflow producer URI references. These
identify producers, not fetch destinations. Importing the package reads no
configuration. Schema, creation, reading, source-loading and codec entry points
are exported separately; the browser's framework-free observation-order path
remains independent.

---

## 5. Content, resource and foreign-boundary identities

Business run numbers, ledger work/file identities, article/offer digests, real
resource handles, startup handshake values and temporary-file collision guards
keep their existing meanings. None is an alias for an event, execution or
operation. A proposed news cluster has a domain `cluster_id`, not an event
occurrence ID; its ULID rules are unchanged.

Python protocols retain their native UUID fields at that boundary. Do not remove
UUID hyphens to manufacture a trace ID or add old-field aliases to a native
TypeScript API. File envelopes continue to carry only their declared identity
and provenance fields.

---

## 6. HHEM execution and event identity

The independent evaluator creates a fresh lowercase UUIDv4 for each HTTP
attempt before reading its body. Service lifecycle work has a separate
execution identity. A caller's request and correlation IDs do not determine
either execution identity.

Supplied request and correlation IDs must be hyphenated UUIDv4 strings. Keep
their exact spelling, including letter case. Only omission generates a new
lowercase UUIDv4; explicit null and invalid supplied IDs are refused.

Each operation gets a fresh UUIDv4 retained across its phases. One parent
emitter orders events with a positive sequence starting at one per execution.
Use the DNS namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8` and standard
UUIDv5 with exactly this UTF-8 name, without a trailing newline:

```text
hhem
{execution_id}
{sequence}
```

`services/hhem-evaluator/src/hhem_evaluator/resolve_ids.py` declares this encoding
once and uses Python's standard UUID implementation. The named
`tests/fixtures/hhem-evaluator/event-id-vectors.json` vectors also run through
the existing TypeScript `createUuidV5` implementation. Missing Bun or its locked
dependencies fails that comparison; no TypeScript runtime is added to the
service installation.

The shared Python server carries each HHEM event in CloudEvents 1.0. Its
envelope `id` is the native `event_id`, and `time` is the native UTC
`occurred_at`; the native ordered event is `data`. Shared API, llama and
diagnostic-file occurrences instead receive fresh UUIDv4 event IDs. Their
producer `source` is the fixed URI reference `/fastapi-server`. These are
native Python events, not manufactured TypeScript trace identifiers.
Readers accept the current structured envelope only. Private startup and
worker-control packets remain native JSON, not CloudEvents.

## Design rationale

An event occurrence, an execution, an operation and a domain item answer
different questions. Shared metadata removes duplicate identity machinery
without changing repeatable work or foreign protocols. The pinned
`@opentelemetry/api` and `@opentelemetry/core` packages supply context types and
the W3C codec only. Core also installs semantic-convention definitions. Their
cost is server/tool installation, not browser bytes; no tracing SDK, recorder,
exporter, collector, automatic instrumentation or trace file is added.

## See also

- [persistence.md](persistence.md) - how the ledger door reads and writes file envelopes.
- [schemas.md](schemas.md) - schema rules and contract definitions.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - metadata versus recorded timing.
- [../../reference/hhem-evaluation-api.md](../../reference/hhem-evaluation-api.md) - transient HHEM fields and their native owner.
- [../../how-to/execute-a-plan.md](../../how-to/execute-a-plan.md) - execution contract.
