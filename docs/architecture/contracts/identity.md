# Identity contracts

**Last Updated**: 2026-11-06

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
| A3 | Article and URL keys | Their declared SHA-256 encodings | An address or foreign domain item, not a captured input. |
| A4 | Native TypeScript event `source + id` | Producer-local protocol URI reference and a fresh lowercase UUIDv4 | One event occurrence; replay retains the saved envelope. |
| A5 | Native TypeScript `traceId` | Nonzero 16 random bytes, encoded as 32 lowercase hexadecimal characters | One execution. |
| A6 | Native TypeScript `spanId` | Nonzero 8 random bytes, encoded as 16 lowercase hexadecimal characters | One operation within that execution. |
| A7 | Python protocol identifiers | The owning Python contract's UUID rules | Foreign caller, execution and operation identities; see section 6. |
| A8 | Native TypeScript `candidate_id` | A fresh lowercase hyphenated UUIDv4 | One captured article input, not its URL, event or operation. |
| A9 | Native TypeScript `document_id` | The full SHA-256 resource address key | A fetched feed or article document, without calling a feed an article. |

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

Each producer declares its fixed logical URI in its own `declare-event-source.ts`
module; the independent workflow uses `declare-workflow-event-source.ts`.
These protocol identities are not configuration, deployment addresses or fetch
destinations. Shared `EventSourceSchema` validates URI references when events
are constructed or read, without enumerating applications or reading files.
Schema, creation, reading and codec entry points remain separately exported;
the browser's framework-free observation-order path stays independent.

### Native API support

Every authored TypeScript HTTP API supports this standard. Native support means
the producing API constructs and validates its application event at the actual
work or error boundary, using its local producer identity and real operation.
It does not mean replacing HTTP results with event envelopes or inventing work
events for health and diagnostic reads.
An HTTP error adapter formats the response without re-emitting a
domain failure that the producer already reported.

Table B - verified API and producer bindings

| ID | Surface | Producer URI and declaration | Native work and functional evidence |
| --- | --- | --- | --- |
| B1 | Planner HTTP: health, plan, fetch/parse, collections, selection, partition, persistence and feed-health-state | `/services/feed-ingest-plan`; `services/feed-ingest-plan/src/declare-event-source.ts` | Mounted routes receive `PlanInputs.event_source`; real progress and terminal article events retain their operations. `plan-entry-points.test.ts`, `operation-logging.test.ts` and the named planner route cases cover real API/CLI work. |
| B2 | Independent summarizer HTTP: health, diagnostics and summarize; summarizer CLI | `/services/summarizer`; `services/summarizer/src/declare-event-source.ts` | HTTP and CLI use the same local identity and request-private event bus. `services/summarizer/test/pipeline-events.test.ts` verifies actual HTTP/CLI output, isolated histories and saved-event replay. It is not mounted into the composed listener. |
| B3 | Fingerprint HTTP: fingerprint and health; fingerprint CLI | `/services/host-fingerprints`; `services/host-fingerprints/src/declare-event-source.ts` | Actual written/disabled results and failures create native events. `fingerprint-persistence.test.ts` covers real writes, disabled work, failures and CLI output; `serve-feed-apis.test.ts` covers the real composed port. |
| B4 | Probe HTTP: sample, start/stop task profile and cache latency; probe CLI | `/services/host-probes`; `services/host-probes/src/declare-event-source.ts` | Native handled/disabled outcomes and safe failures come from real commands. `native-events.test.ts` and `probe.test.ts` cover all commands, private reports, cleanup and retained profile operations; `serve-machine-apis.test.ts` covers native machine composition. |
| B5 | Delivery HTTP: health and safe-persist-data | `/services/typescript-api`; delivery's declaration in `services/feed-ingest-plan/src/declare-event-source.ts` | The handler creates completion/failure events before supervision. `safe-persist-http.test.ts` verifies native stderr before relay, unchanged occurrence/context after relay and actual local Git delivery; finalization retains the same native facts. |
| B6 | Composed listener: health, lifecycle and request-error boundary | `/services/typescript-api`; `services/serve-pipeline-apis/src/declare-event-source.ts` | The host constructs its own request-failure event and relays validated producer events unchanged. `supervise-http-child.test.ts`, `server-events.test.ts` and `serve-feed-apis.test.ts` exercise real listeners and error paths without reverse native dependencies. |
| B7 | Non-HTTP phased workflow and upload inventory | `/workflows/ai-pipeline` in `.github/scripts/declare-workflow-event-source.ts`; upload inventory reuses B1 | The workflow and inventory emit real native events without a registry file. `workflow-handoff.test.ts` and planner `operation-logging.test.ts` preserve saved handoff, upload facts and source identities. |

Delivery intentionally retains the API host's published namespace through its
own declaration; neither producer loads the other's source. Their integration
case holds these declarations equal. Sources are logical protocol identities,
not deployment settings or directory-derived names.

Accepted native events retain source, occurrence ID, UTC time, carrier and data
through relay. Producer-specific validators reject unknown types and unsafe
extra fields. A delivery completion carrier must agree with its saved receiving
context; a successful or repeated profile stop retains the original profile
operation even when stop headers differ. Full task profiles and summarizer
events retain their private transports, not a second copy in normal logs.
Readiness packets, native HTTP results and CLI result stdout keep their
existing protocols. No runtime tracing or collector is implied.

---

## 5. Content, resource and foreign-boundary identities

Business run numbers, ledger work/file identities, article address keys,
captured candidates, real resource handles, startup handshake values and
temporary-file collision guards keep their existing meanings. None is an alias for an event, execution or
operation. A proposed news cluster has a domain `cluster_id`, not an event
occurrence ID; its ULID rules are unchanged.

Python protocols retain their native UUID fields at that boundary. Do not remove
UUID hyphens to manufacture a trace ID or add old-field aliases to a native
TypeScript API. File envelopes continue to carry only their declared identity
and provenance fields.

### TypeScript resource addresses

An article address key is the complete 64-character lowercase hexadecimal
SHA-256 of the UTF-8 `canonical_url`. The native feed-document key uses the
same resource URL rule. Feed, publisher, taxonomy, run, model and article text
do not enter this hash.

Article HTTP results use `article_id`. Generic fetched documents, operation
observations and failed-document metadata use `document_id`, since their input
can be a feed or an article. A feed HTTP result has its configured `feed_id`
and `document_id`, not an article or candidate identity. Genuine article entity
records retain `article_id`.

Native discovery, selected and rejected storage retain `url_key`. Selection
and partition HTTP rows expose that value as `article_id` through one strict
projection derived from native selected metadata. The real orchestrator
restores the native field when it needs native rows. Neither side accepts the
other spelling. Foreign publication and item-health read copies keep their
existing `item_id` and `url_key`.

Trim the input, accept HTTP scheme spelling without regard to case, then use
the runtime's standard `URL` parser and serializer. Check the existing URL
format and length bounds before parsing and after serialization. Remove the
fragment only. Preserve queries, parameter order, repeated keys, blank values,
encoded delimiters and plus signs as the serializer emits them. Preserve
`www`, non-root trailing slashes, path case and the HTTP/HTTPS distinction.
Do not rebuild queries with `URLSearchParams`, classify tracking parameters,
or unwrap a URL stored inside a query. Normalization is idempotent and is a
fixed identity protocol, not a per-run option.

Syntactic identity does not grant fetch permission. A valid but forbidden
target retains its normalized address and key in preflight refusal evidence,
without a source request. Malformed input has neither an address nor an
invented hash. Initial dispatch uses the same normalized URL that was hashed.
Every actual redirect hop passes the existing target checks and preserves its
query; its destination is evidence, not a replacement for the initial key.

This rule belongs to the native TypeScript planner. Python normalization,
public digest identifiers, configured feed slugs and health endpoint keys
retain their separate rules. No cross-language normalization parity is claimed.
The [native history contract](../sources/planner-feed-history.md#raw-and-compact-copies)
defines current-format reads and independent historical health fields.

### TypeScript captured article inputs

`candidate_id` identifies one article input captured in a run, from a feed
entry or a direct URL admission. `createCandidateId` uses the native
cryptographic UUID facility once, before preflight. `CandidateIdSchema`
requires lowercase hyphenated UUIDv4. Preparation, retries, parsing, screening,
selection accounting, entity evidence and failure recording carry that value;
none recreates it.

Feed inputs retain their original nonnegative `entry_ordinal`, including gaps.
Direct inputs use null because they have no feed position. A fresh capture of
the same URL receives another candidate ID but keeps the same address key.
Current saved payloads retain their stored candidate when validated.

Article refusals require the captured candidate even when their address is
malformed; the URL and address hash then remain null. Feed documents and feed
refusals have no article candidate. A UUID alone grants no permission: the
existing producing-operation links, captured membership, source, address,
configuration, run, attempt and one-shot claim still have to agree.
The [operator API](../sources/feed-operator-api.md#live-document-lifetime)
defines live ownership and the absence of restart recovery.

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

UniEval also creates its execution UUIDv4 before body reading, independently
of caller request/correlation UUIDs and the other model worker. Its private
comparison replies must match that execution, worker generation, dimension,
sentence and source-window identity. Its diagnostic occurrences use fresh
CloudEvents UUIDv4 IDs and retain the request execution ID in safe data.
The reference-summary digest identifies the exact UTF-8 reference bytes,
not the source, generated answer or an event occurrence.

## Design rationale

An event source identifies a logical producer across deployments and file
moves. Keeping that protocol literal beside its producer preserves existing
recordings without a runtime registry, environment override or missing-file
fallback. Shared helpers validate the protocol rather than select applications.

An event occurrence, an execution, an operation and a domain item answer
different questions. Shared metadata removes duplicate identity machinery
without changing repeatable work or foreign protocols. The pinned
`@opentelemetry/api` and `@opentelemetry/core` packages supply context types and
the W3C codec only. Core also installs semantic-convention definitions. Their
cost is server/tool installation, not browser bytes; no tracing SDK, recorder,
exporter, collector, automatic instrumentation or trace file is added.

A query can select the resource itself. Keeping an extra address record is
safer than merging two required parameter values. URL identity does not decide
whether different addresses contain the same story, or whether reporting at
one address has changed.

An address can be captured more than once, while a direct input has no feed
position. Allocating one independent candidate ID at admission preserves those
distinct inputs without inventing a position or coupling them to later
operations.

## See also

- [persistence.md](persistence.md) - how the ledger door reads and writes file envelopes.
- [schemas.md](schemas.md) - schema rules and contract definitions.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - metadata versus recorded timing.
- [../../reference/hhem-evaluation-api.md](../../reference/hhem-evaluation-api.md) - transient HHEM fields and their native owner.
- [../../how-to/execute-a-plan.md](../../how-to/execute-a-plan.md) - execution contract.
