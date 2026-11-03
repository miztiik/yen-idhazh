# Standardize TypeScript event and operation metadata

**Last Updated**: 2026-11-03
**Level**: 5 - TypeScript metadata contract.

## 0. Operating contract

Table A - scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Give TypeScript event, execution and operation identifiers one meaning, using CloudEvents, OpenTelemetry names and W3C Trace Context without building a tracing system. |
| A2 | Hard scope - in | Shared metadata schemas and creation/propagation helpers; planner APIs, stages, workers, ledgers and callers; host profiling; summarizer; phased workflow; functional coverage; removal of retired implementations and documentation. |
| A3 | Chosen strategy | CloudEvents `id` identifies an event occurrence. `traceId` identifies an execution. `spanId` identifies an operation. `parentSpanId` identifies its enclosing operation. `links` identify input dependencies. These meanings follow the standards in Table S. |
| A4 | Read rule | Changed TypeScript APIs and ledger families are current-only. No migration, backfill, old-field aliases, dual readers or retrospective ID conversion. Cut over each producer with its consumers. Existing route paths stay. |
| A5 | Runtime boundary | Metadata creation, validation and propagation only. No tracing SDK, provider, recorder, exporter, collector, automatic instrumentation, trace output files, telemetry flag or export-buffer settings. Do not modify CLAUDE.md or AGENTS.md. |
| A6 | ESCALATE triggers | 1. A Python-owned protocol must change. 2. Identifiers become authorization or a new idempotency promise. 3. Runtime tracing or export is needed. 4. A changed field has a consumer outside the named file scopes. 5. A functional flow needs another persisted metadata field not declared here. |
| A7 | Parallelism | At most three independent rows after the foundation: planner, summarizer and phased workflow. Host follows planner because they edit the same proof scripts. Serialize overlapping source paths. |
| A8 | Delivery | One nested project session per PR. The coordinator verifies each candidate and merges serially after its required checks pass. This document replaces the earlier UUID-consolidation and tracing-runtime proposals. |
| A9 | Tests | Prove working producer-to-consumer flows, relationships, retry behavior, isolation, replay and lifecycle behavior. No field-name snapshots, source-grep tests, documentation-compliance tests or tests whose only result is that an old spelling disappeared. |
| A10 | Removal | Each cutover removes its old implementation, aliases, obsolete fixtures and tests that defend only the retired format. Remove shared code with its last caller. Do not leave a second supported implementation after a green merge. |

Execute per docs/how-to/execute-a-plan.md: one coordinator carries the plan and delegates each PR to a nested project session; keep parallel N = 3 rows in flight because only three post-foundation rows have independent scopes; serialize overlapping files and merges; merge only after required checks pass; honor the ESCALATE triggers in section 0.

Table B - explicit exclusions and costs

| ID | What is out | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Changing ledger unit UUIDv5, ledger file UUIDv8, SHA-256 article/offer identities or existing namespace seeds | Repeatable work, physical files and content keep their distinct algorithms. They are not event or operation metadata. | A separate defect in those identities. |
| B2 | Changing Python event, request and startup protocols | Foreign UUID fields remain at those boundaries. They do not become native TypeScript API aliases. | A separate cross-language contract change. |
| B3 | Creating a tracing runtime or trace files | No new timing tree, trace viewer or export capability ships. Existing Python tracing remains unchanged. | A separate runtime tracing requirement. |
| B4 | Adding request idempotency or saved-response replay | Repeated commands retain their existing work/conflict/finalization behavior, not a new replay guarantee. | A defined repeat-request requirement and business contract. |
| B5 | Building topic clustering | The proposal's domain names become clear, but no clustering capability ships. | The clustering implementation plan. |
| B6 | Changing protected instruction files | Existing rules remain unchanged. This design needs no telemetry-SDK exception. | A separate explicit instruction for the named file. |
| B7 | Converting retained old TypeScript records | Old artifacts using removed fields are not converted. Existing unsupported-input/partial-history rules apply; known history can be incomplete until current records accumulate. Do not silently manufacture replacement references or delete history. | A separate historical-data requirement. |

## 1. Status reckoner

Table C - PR sequence

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Define shared event and operation metadata | - | A | PENDING | - | - | - |
| C2 | 2 | Convert the planner and every planner caller | 1 | B | PENDING | - | - | - |
| C3 | 3 | Convert host profiling without breaking Python control | 1, 2 | C | PENDING | - | - | - |
| C4 | 4 | Convert summarizer event metadata | 1 | B | PENDING | - | - | - |
| C5 | 5 | Convert phased workflow events and continuation | 1 | B | PENDING | - | - | - |

## 2. Exact current-to-target replacements

Table D - exact names, paths and meanings

| ID | Current location / name | Action | Exact target name or path | Target meaning and rule |
| --- | --- | --- | --- | --- |
| D1 | Summarizer/workflow event `eventId` | Replace | Event `id` | CloudEvents occurrence identity. Allocate one lowercase UUIDv4 with `crypto.randomUUID()` per new event. Delete `evt-`/`evt_` prefixes. This is not an operation ID. |
| D2 | Event `eventType` | Rename | Event `type` | Keep current type values. Planner progress uses the fixed value `planner.progress`. |
| D3 | Event `timestamp`; progress `occurred_at` | Move | Event `time` | Actual UTC event occurrence instant. Do not reinterpret it as an operation start/end. |
| D4 | Summarizer event `payload` | Move | Event `data` | Preserve the complete application payload, including structured summary output. |
| D5 | Phased-workflow event `payload`, `durationMs`, `cumulativeMs` | Move | Event `data.result`, `data.durationMs`, `data.cumulativeMs` | `result` contains the original payload unchanged. Preserve both existing timing calculations and units; these remain log-gap/cumulative measurements, not span durations. Evaluation reads `data.result`. |
| D6 | Missing standard event attributes | Add | Event `specversion`, `source`, `datacontenttype` | Values are `"1.0"`, the configured producer URI reference, and `"application/json"`, respectively. |
| D7 | Event `correlationId`; progress `correlation_id` | Replace | Event `traceparent`; optional event `tracestate` | Standard CloudEvents tracing extension containing the emitting operation context. No event-envelope `traceId`/`spanId` aliases. |
| D8 | `PlannerObservationSchema.event_id` | Replace | Observation `spanId` | Identifies this fetch, parse or attempt operation. Use E2's native format, not a UUID or a renamed CloudEvent `id`. Keep the observation schema and its useful domain facts. |
| D9 | Operation/row/runtime `correlation_id`; local `correlationId` | Replace | Record `traceId`; local `traceId` | Identifies one execution using E1's native format. Do not convert an old UUID by removing its hyphens. Boundary-specific exceptions are D21/D22/D29. |
| D10 | Attempt `caused_by_event_id` pointing at its containing fetch | Replace | Attempt `parentSpanId` | Exactly the containing fetch's `spanId`; both have the same `traceId`. |
| D11 | Parse `caused_by_event_id` pointing at its completed fetch | Replace | Parse `links[0].traceId`, `links[0].spanId` | Reference the actual input fetch. `parentSpanId` refers to enclosing collection/caller work when present, not that finished input. A standalone root omits `parentSpanId`. |
| D12 | Caller fetch `caused_by_event_id` | Delete | No alias | Parentage comes from resolved execution context. An offered article's input dependency is D16. An arbitrary caller event ID is not a valid parent reference. |
| D13 | Command `request_id`; internal `requestId` / document request key | Remove duplicate identity | Response `spanId`; held operation `spanId`; fetched document `observation.spanId`; local `spanId` | Allocate once before work and retain through its outcome. Commands do not carry a second caller-generated UUID for the same operation. Lookup uses both `traceId` and `spanId`. |
| D14 | Parse request/response `fetch_request_id` | Replace | `links[0].traceId`, `links[0].spanId` | One link to the held fetch whose body is consumed. Remove the parse request's redundant `article_id`; derive it from that document. |
| D15 | Fetched document `parent_fetch_request_id` | Delete redundant ancestor copy | No direct replacement column | D16 references the producing feed parse; that parse's link identifies the originating feed fetch. Resolve this chain from held work. |
| D16 | Offered-article fetch `batch_id`; fetched document `parent_batch_id` | Replace | Operation/request `links[0].traceId`, `links[0].spanId` | Reference the feed parse that produced the offer. Keep the SHA-256 `offer_id` to choose an article within that output. |
| D17 | Stage result `batch_id`; local `batchId` | Remove duplicate identity | Result `spanId`; local `spanId` | One stage operation produces one addressable result. Register it under that operation instead of allocating another batch UUID. |
| D18 | Stage input `batch_id`, `parsed_batch_id`, `selection_batch_id`, `feed_fetch_request_id`, `article_fetch_request_id` | Replace | Input/result `links[].traceId`, `links[].spanId` | Reference producing operations. Single-input commands require one link of the expected result kind. Collection completion links to its contributing parse results. |
| D19 | Planner `collection_id`; local `collectionId` | Remove duplicate execution identity | Collection-reference `traceId`; local `traceId` | One collection per execution. The held collection also has its own `spanId`. Preserve startup outcome lookup using F1's preallocated execution context, not another UUID. |
| D20 | Candidate, rejection, entity and saved run-response `correlation_id` | Replace | Record `traceId` | Associate the record with its producing execution. Keep business `run_id` and writer `attempt` separate. Do not add an operation ID to a domain row that does not need one. |
| D21 | Stage business `context.correlation_id` | Remove duplicate location | Stage result's top-level `traceId` | Stage `context` keeps captured UTC/run/writer facts only. Operation metadata is at the result's top level; do not store both copies. |
| D22 | Failure `execution.correlation_id` | Replace | `execution.traceId`, `execution.spanId` | Both nullable when unavailable. The execution can be known while its operation is not, so `traceId` may be present with null `spanId`, never the reverse. Preserve run/attempt/git facts. |
| D23 | Parser job `id` and separately generated UUID | Replace | Job/result `traceId`, `spanId` | The worker executes the already allocated parse operation and returns its context unchanged. Do not create a second identity merely for message matching. |
| D24 | Host `identity.request_id`, `identity.correlation_id` | Remove | Profile top-level `traceId`, `spanId`, optional `parentSpanId`, `links` | Identify the actual profiling operation. `identity` keeps `pipeline_name`, `task_name`, `run_id`. Do not change measurements. |
| D25 | Profile `handle`; startup `nonce` / `startup_id`; temporary-file UUID | Keep | Existing names unchanged | These address a real resource, prove a control handshake or prevent file-name collisions. They are not aliases for event/operation/execution identity. |
| D26 | News-view `event_id` | Rename in the clustering proposal | `cluster_id` | A proposed domain-column rename, not a compatibility alias or a standard tracing name. This plan does not implement clustering. |
| D27 | News-view `source_event_id`, `target_event_id`, `event_ids` | Rename in the clustering proposal | `source_cluster_id`, `target_cluster_id`, `cluster_ids` | Preserve proposed relationships and cluster ULIDs. Remove the retired proposed spellings. |
| D28 | Producer-local `generateUuidV5`, `buildDeterministicEventId`, timestamp correlation and observation seed generation | Delete | G1's shared creation functions | Do not move retired algorithms into another helper. Preserve the ledger UUIDv5 helper and Python parity vectors. |
| D29 | Python startup UUID fields and evaluator `correlationId` | Keep at the foreign boundary only | Existing foreign field names unchanged | Do not reinterpret UUIDs as trace IDs. Strip unneeded foreign metadata when constructing native host identity. No old TypeScript API reader is added. |
| D30 | Progress `version`, `run_id`, `operation`, `phase`, `details` | Move | Event `data.version`, `data.run_id`, `data.operation`, `data.phase`, `data.details` | Keep progress behavior, bounded safe details and measurements. Add an envelope, not new timing features. |
| D31 | Health row/read projection `check_request_id` | Replace | Row/projection `links[0].traceId`, `links[0].spanId` | Reference the logical feed-check fetch operation, not a network retry. Use `links: []` when no check is known; otherwise exactly one link. Carry it unchanged with the same historical check so rest/reliability logic does not count it twice. Historical links do not require a live store entry. |
| D32 | Saved response / `FeedPlanResult.batches` with parsed/selection/partition batch IDs | Delete | No replacement receipt object | These expired live references are not needed after execution. Keep the actual output file receipts, selected identities and assignments. Live stage calls use F5/F6's links. |
| D33 | `DocumentOperationContext.request_id` and standalone run-number derivation from that UUID | Replace | Captured operation E6; existing `run_id` | Keep the current run-ID format. If no operator run number exists, use the execution's `traceId` bytes as the existing decimal random component. Do not use event IDs or allocate another UUID. |
| D34 | Private startup `runtime.correlation_id`; runtime/run-context metadata | Replace | `runtime.traceId`, `runtime.spanId`, optional `runtime.parentSpanId`, `runtime.links`, optional `runtime.traceState` | Pass the allocated root context through the existing startup packet. Keep its independent nonce and business settings. Use a business-only projection for stage `context` under D21. |

## 3. Native field and API contracts

Table E - exact operation metadata shape

| ID | Field / type name | Required representation | Source and invariant |
| --- | --- | --- | --- |
| E1 | `TraceIdSchema`; JSON `traceId` | Nonzero 32-character lowercase hexadecimal string | Generate from `crypto.randomBytes(16)` at a new execution root. Regenerate all-zero output. Descendants retain the value. |
| E2 | `SpanIdSchema`; JSON `spanId` | Nonzero 16-character lowercase hexadecimal string | Generate from `crypto.randomBytes(8)` once per operation. Regenerate all-zero or parent-equal output. No timestamp seed, UUID bits or deterministic replay promise. |
| E3 | JSON `parentSpanId` | Optional E2; absent at a root, not null | Enclosing operation's `spanId`, different from the child. Parent/child have the same `traceId`. This is containment, not every input dependency. |
| E4 | `OperationLinkSchema`; JSON `links` | Array of `{ traceId, spanId }`; empty without input dependencies | Native relationship names. Links may cross traces. Live planner input links resolve against expected result kind, config and lifecycle; historical provenance does not become a live lookup. |
| E5 | JSON `traceState` | Optional string | Preserve valid incoming state with the W3C codec. HTTP/CloudEvents spelling is `tracestate`; these are standard boundary representations, not accepted project aliases. |
| E6 | `OperationMetadataSchema` | Composition of E1-E5 | A metadata profile using OpenTelemetry names, not an OTLP export packet, recorded span or promise of timing coverage. No `observation_id`, `parent_observation_id`, `trace_id` or `span_id` aliases. |
| E7 | Headers/extensions `traceparent`, `tracestate` | W3C carrier strings | Encode the current E6 context with the standard propagator. Locally generated contexts use version `00` and unsampled flags `00`; no sampling/recording feature. Decode before deriving a child, not with a local string splitter. |
| E8 | `CloudEventSchema` | Structured JSON envelope with D1-D7 plus validated `data` | Event identity is `source + id`. A new event gets a new `id`; replay preserves the entire saved envelope. Several events can share one operation context. CloudEvents `specversion` stays `"1.0"`; project schema date versions are separate. |

Table F - exact command/result changes

| ID | Surface | Required input after cutover | Required output / held result |
| --- | --- | --- | --- |
| F1 | Collection start / outcome lookup | Start body `{ request }`. The ordinary runner allocates E6 before sending and injects its carrier. Server creates the collection operation as a child in that trace; a missing/invalid carrier starts a fresh execution. Enforce one held collection per `traceId`. Lookup body `{ traceId }`. | Start returns E6 plus existing business `context` and `feeds`. Lookup returns `{ traceId, exists }`. The runner can query its known `traceId` after an uncertain start outcome. |
| F2 | Feed fetch; direct operator article fetch | Feed body `{ feed_id, fetch_item_type: "feed", traceId? }`. Direct article body `{ feed_id, fetch_item_type: "article", url, traceId? }`. Optional body `traceId` selects a held collection; omit it for standalone work. Feed URL stays configuration-owned. | Body-free response contains E6 plus current run/item/status/failure/digest facts. Held fetched body retains its E6 under `observation`, not another outer copy. Collection work is a child of its held root; standalone context follows H3. |
| F3 | Offered article fetch | Body `{ fetch_item_type: "article", offer_id, links: [{ traceId, spanId }] }`. The link selects the producing feed parse; derive feed, URL, run and collection from held work. Do not require duplicate `feed_id` or collection/trace echoes. | E6's `links` retains that dependency. Preserve offer membership, entry ordinal, original source, pending/claimed state, config and article-URL safety checks. |
| F4 | Feed/article parse | Body `{ links: [{ traceId, spanId }] }`, selecting exactly one held completed fetch. No caller `request_id`, `fetch_request_id`, `article_id` or `correlation_id`. | E6 identifies the parse/result. `links[0]` identifies its input fetch. Keep feed offers, article warnings, counts, pending-offer count and failure behavior. Parse consumes the held body without another fetch and preserves claim/retry rules. |
| F5 | Collection complete/cancel/finalize | Complete/cancel body `{ traceId }`. Finalize retains failure/timing facts with `traceId` replacing `collection_id`. Release keeps existing `run_id`/`attempt`. | Complete/cancel allocates one operation context before work and returns its parsed aggregate under that context, plus existing status/receipts/facts. Preserve existing completion reuse and cancellation/finalization rules; do not add cancellation replay. Finalize retains its business outcome and `traceId`. |
| F6 | Select/partition/persist/feed-health-state | Replace each input `batch_id` with exactly one `links` entry. Select requires parsed output; partition requires selected output; persistence requires selected/partitioned output under the existing config rule; health accepts its existing supported document/stage kinds. Retain tuning/action fields. | Each operation returns E6 plus its existing business output. Its own `spanId` is not an echo of the input. Register addressable stage output under the producing pair, without a new batch UUID. Preserve selection claims, new-run rules, immutable-result checks and finalization behavior. |
| F7 | Collection aggregation | Hold ongoing mutable offers/work in the existing collection state, not under a separately generated parsed-batch UUID. Feed/article parse results retain their own operation references. | Completion snapshots the aggregate under F5's producing operation. Its `links` are the actual contributing parse references in execution order, without duplicates. Selection still refuses incomplete/cancelled or per-feed-only input. |
| F8 | Worker, host and event boundaries | Worker executes D23's supplied parse context. Host start accepts business identity and optional W3C headers; stop retains its live `handle`. Event readers take a named current-format JSONL file. | Worker returns the same context; host profile carries its own operation metadata; event readers preserve event IDs/data/carriers. Disabled host profiling retains its existing unavailable result, not a fabricated operation/profile. |

## 4. Binding implementation and behavior rules

Table G - implementation, dependencies and runtime

| ID | Item | Required implementation and cost |
| --- | --- | --- |
| G1 | Shared location and functions | Extend `packages/common-contracts`; do not create a runtime package. Export `createCloudEvent`, `readCloudEvent`, `createRootContext`, `createChildContext`, `readTraceContext`, `writeTraceContext`, `loadEventSources`, and E's schemas. Imports do not allocate context, read config or install providers. Callers pass context explicitly. |
| G2 | W3C library | Pin `@opentelemetry/api` to `1.9.0` and `@opentelemetry/core` to `2.12.0` for native context types and `W3CTraceContextPropagator`. Released dependencies fit together without a tracing SDK. Core also installs semantic-convention definitions. All added dependency cost is server/tool installation, not browser bytes. |
| G3 | Envelope binding and random primitives | Use existing Zod validation for one narrow structured-JSON CloudEvents producer profile. `createCloudEvent` and `readCloudEvent` take `parseData: (value: unknown) => T`; callers supply their real application validator without passing Zod objects between major versions. Use existing Node `crypto` primitives for E1/E2/D1. No transport bindings, local W3C parser, UUIDv5 algorithm or CloudEvents transport SDK. |
| G4 | Source configuration | Add only `config/typescript-event-sources.json`: `{ "planner": "/services/feed-ingest-plan", "summarizer": "/services/summarizer", "workflow": "/workflows/ai-pipeline" }`. `loadEventSources` validates these named URI references at load; they identify producers, not fetch destinations. Host has no new event producer or unused source setting. |
| G5 | Runtimes and packaging | Keep current runtime versions and package installation paths. Add the common dependency to summarizer/host; refresh affected local-package locks. The standalone workflow imports the shared source entry point explicitly and prepares that package's locked dependencies. Do not create a root workspace or modernize unrelated dynamic dependencies. |
| G6 | No runtime infrastructure | No sdk-trace, async-hooks context manager, resources package, OTLP transformer/exporter, queue, flush lifecycle, collector, telemetry switch or trace output. Existing workers/listeners retain their current shutdown responsibilities. |
| G7 | Versions and rollout | Stamp changed project families and append their changelog entry. Retain current-only version rules; no migration/backfill/dual reader. CloudEvents spec version is not a project date. Each PR cuts over its real consumers and removes its retired path. |

Table H - behavior that implementation must not guess

| ID | Concern | Required rule |
| --- | --- | --- |
| H1 | Occurrence, operation and replay | A new event gets a new `id`; a new operation gets a new `spanId`; a new execution gets a new `traceId`. Reading/redelivering a saved event changes none of them. Do not compute occurrence identity from URL, time, type or payload hash. |
| H2 | Canonical standards statement | Add to the identity contract: "Event envelopes follow CloudEvents 1.0. Operation metadata follows OpenTelemetry identifier and relationship names. Propagation follows W3C Trace Context. These contracts do not enable runtime tracing. Project aliases for the standard identifiers are not supported." |
| H3 | Incoming context and continuations | Use the standard codec. A standalone command derives a child from valid incoming context or starts a root. Collection continuation uses its held collection context. When existing selection rules create another business run, allocate a fresh root and link the original parsed input rather than copying its execution identity. Otherwise a standalone continuation can start a separate trace and link its stored input. Never require input and caller traces to match; invalid optional headers cannot bypass business-reference checks. |
| H4 | Parent versus dependency | Apply D10/D11/D16 and F exactly. Retry is inside its fetch. Completed fetch/feed-parse/stage inputs are links. Do not silently map every old cause field to `parentSpanId` or declare a caller's event ID to be a real parent. |
| H5 | Held work and business safety | Key operation/result lookup by `(traceId, spanId)` and expected kind. Retain capacity, active/consumed state, config fingerprint, configured source/offer membership, run and writer-attempt checks. These references address work; neither trace equality nor possession of a trace ID creates authorization or new response replay. |
| H6 | Worker isolation | Pass context per job/result and match the pair. Do not use global mutable current context. Preserve queue wait, deadlines, cancellation, kind matching and worker reuse behavior. |
| H7 | Python boundary | Keep native packets and evaluator formats unchanged. `measure-host.ts` preserves the `startup_id` handshake, passes only domain labels/run to the new host identity, and creates its local profile context. The evaluator client still supplies a separate foreign UUIDv4 `correlationId` and reads `response.event.payload.serverTelemetry`. |
| H8 | Domain data and safe diagnostics | Preserve the full result at D4/D5's paths and existing measurements. Remove full-event console dumping; emit safe metadata/counts/codes. Do not put source text, prompts, model output, titles, URLs, credentials or raw headers/errors in metadata. No extra trace artifact. |
| H9 | Propagation destination | Propagate carriers only across operator-controlled API, worker and control boundaries. Do not inject them into public article/feed requests. No baggage or environment-selected destination. |
| H10 | Existing ID defects | Replacing the custom fields removes the loose UUID correlation and arbitrary self-cause design. E3 enforces non-self parentage; actual input resolution enforces dependencies. Do not add a separate final patch or compliance test defending retired UUID fields. |
| H11 | Testing and removal | Use real production helpers/stores/readers with recorded inputs. Adapt useful safety/lifecycle cases. Delete old-format-only assertions rather than changing them into new spelling assertions. Manual retired-name review is allowed; do not add a source/doc grep test. |
| H12 | News proposal | D26/D27 rename proposed columns only. Update its active schemas, mappings and examples and remove the old proposed aliases. Do not introduce a new ULID algorithm or claim a deployed news API was migrated. |
| H13 | Existing work/file identities | Retain B1's deterministic work identity, physical-file IDs and their functional parity/retry cases. The new random operation identity does not replace content identity or ledger de-duplication. |

## 5. Row #1 - Define shared event and operation metadata

- **Scope:** Ship the shared metadata schemas, factories and W3C codec without cutting over a service or introducing runtime tracing.
- **Tasks:**
  - Implement Tables E/G once, including explicit config loading and typed CloudEvent data validation. Reading a saved event must not allocate a new identity.
  - Export separate schema/creation/codec entry points through the existing package. Preserve the frontend's framework-free observation-order import path.
  - Refresh named dependent locks and ordinary CI installation inputs. Do not add a tracing job, output directory or artifact.
  - Update the identity contract with H2, the new identity distinction and the actual unchanged Python/B1 patterns. Remove stale planner audit-seed claims.
  - Clarify metadata-only scope in the existing telemetry page; do not alter its Python instrumentation or SDK prohibition.
  - Apply H12 to the clustering proposal. Remove obsolete proposed aliases/examples rather than adding a second accepted vocabulary.
- **Files touched:**
  - `packages/common-contracts/src/schemas/cloud-event.schema.ts`
  - `packages/common-contracts/src/schemas/operation-metadata.schema.ts`
  - `packages/common-contracts/src/create-cloud-event.ts`
  - `packages/common-contracts/src/read-cloud-event.ts`
  - `packages/common-contracts/src/create-operation-context.ts`
  - `packages/common-contracts/src/propagate-trace-context.ts`
  - `packages/common-contracts/src/load-event-sources.ts`
  - `packages/common-contracts/test/metadata-flow.test.ts`
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/package.json`
  - `packages/common-contracts/bun.lock`
  - `packages/ledger-file-writer/bun.lock`
  - `packages/feed-probe/bun.lock`
  - `services/host-fingerprints/bun.lock`
  - `services/feed-ingest-plan/bun.lock`
  - `config/typescript-event-sources.json`
  - `.github/workflows/ci.yml`
  - `docs/architecture/contracts/identity.md`
  - `docs/concepts/telemetry.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/unsupervised-topic-detection-event-clustering.md`
- **Acceptance gates:** Local: inspect the shared changed-test selection, then run common-contract check and `metadata-flow.test.ts` with the relevant existing native cases. Keep existing ledger identity behavior coverage; do not add field-set snapshots. CI: ordinary shared/native merge-candidate suites.
- **Oracle:** Create two real events for one operation, round-trip a saved event, propagate a child context and read its input link; consumers recover the original application values, distinct occurrences and correct relationships. This does not prove service work ownership or lifecycle behavior.

Table I - row 1 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| I1 | Use separate native event, execution and operation identities. | CloudEvents identity and OpenTelemetry context semantics, Table S. |
| I2 | Use only G2's API/codec dependencies and existing Zod/crypto primitives. | Metadata-only scope; released dependency metadata. |
| I3 | Document the adopted standards and remove project aliases. | H2; one meaning per identifier. |

Table J - row 1 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Rename IDs to `observation_id` / `parent_observation_id` | Recreates the custom metadata vocabulary. | Another set of schemas, parsers and relationship rules with no standard-name benefit. | A3/H2. |
| J2 | Add a tracing SDK, exporter or OTLP artifact | Creates an unrequested runtime feature. | New lifecycle, storage, policy and operational work. | A5/B3. |
| J3 | Add the full CloudEvents transport SDK | This plan produces/reads one structured-JSON profile with existing Zod; it does not implement delivery bindings. | Additional AJV, UUID and transport-related installation dependencies and another runtime integration. | G3; KISS. |

## 6. Row #2 - Convert the planner and every planner caller

- **Scope:** Replace planner metadata and redundant live operation IDs end-to-end while preserving work facts, lifecycle checks and actual output.
- **Tasks:**
  - Apply D8-D23/D30-D34 and Table F to contracts before logic. Keep `observation`/`attempt_observations`, ordered counts, HTTP failures, pacing and measured work. Replace only metadata and redundant references.
  - Allocate fetch/parse context before work and retain it through failure/completion; do not regenerate an ID at each observation. Replace the UUID seed helper with composition of held E6 and domain facts.
  - Re-key documents, offers and stages using E4's typed reference pair. Remove request/fetch/batch UUID generation and redundant ancestor copies. Preserve body consumption, config, stage-kind, busy/capacity, offer and run/attempt checks.
  - Implement F1's known execution identity before collection startup, including uncertain-start lookup. Keep completion draining, pending-offer accounting, cancellation, finalization and release behavior. Snapshot the aggregate under F5/F7, not a second batch identity.
  - Wire explicit parse context through the real worker pool. Adapt deadline/cancellation cases instead of adding a tracing lifecycle.
  - Replace correlation metadata in current candidates, rejections, entities, responses, failures and startup packets. Update refinements to compare real business ownership, not trace equality.
  - Apply D31 to feed-health writers and projections; carry the same check link across history and preserve rest/reliability de-duplication. Do not introduce an old-row conversion path.
  - Convert progress writer/reader, report, supervisor, safe-persist client/server and upload inventory together. Remove expired batch references from saved responses under D32. Upload the same application outputs as before, not new trace files.
  - Update each named fixture through the real recording path. Remove old-format-only test assertions/helpers; keep functional coverage. Do not rewrite committed state history.
- **Files touched:**
  - `packages/common-contracts/src/schemas/planner-operation.schema.ts`
  - `packages/common-contracts/src/schemas/planner-stage.schema.ts`
  - `packages/common-contracts/src/schemas/event.schema.ts`
  - `packages/common-contracts/src/schemas/candidate.schema.ts`
  - `packages/common-contracts/src/schemas/rejection.schema.ts`
  - `packages/common-contracts/src/schemas/planner-failure.schema.ts`
  - `packages/common-contracts/src/schemas/planner-response.schema.ts`
  - `packages/common-contracts/src/schemas/raw-document-failure.schema.ts`
  - `packages/common-contracts/src/schemas/article-entities.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-fields.schema.ts`
  - `packages/common-contracts/src/schemas/feed-health-state.schema.ts`
  - `packages/common-contracts/src/version.ts`
  - `packages/common-contracts/test/article-identity-compatibility.test.ts`
  - `packages/common-contracts/test/planner-diagnostics.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/screened-article.test.ts`
  - `packages/ledger-file-writer/test/planner-recordings.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/src/index.ts`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/document.route.ts`
  - `services/feed-ingest-plan/src/api/routes/collection.route.ts`
  - `services/feed-ingest-plan/src/api/routes/stages.route.ts`
  - `services/feed-ingest-plan/src/api/collection-batch.ts`
  - `services/feed-ingest-plan/src/api/collection-contracts.ts`
  - `services/feed-ingest-plan/src/api/collection-operation.ts`
  - `services/feed-ingest-plan/src/api/document-operations.ts`
  - `services/feed-ingest-plan/src/api/document-response.schema.ts`
  - `services/feed-ingest-plan/src/api/document-state.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state-operation.ts`
  - `services/feed-ingest-plan/src/api/feed-health-state.schema.ts`
  - `services/feed-ingest-plan/src/api/feed-offer-state.ts`
  - `services/feed-ingest-plan/src/api/feed-offers.ts`
  - `services/feed-ingest-plan/src/api/fetch-operation.ts`
  - `services/feed-ingest-plan/src/api/operation-context.ts`
  - `services/feed-ingest-plan/src/api/operation-contracts.ts`
  - `services/feed-ingest-plan/src/api/parse-operation.ts`
  - `services/feed-ingest-plan/src/api/partition-operation.ts`
  - `services/feed-ingest-plan/src/api/persistence-operation.ts`
  - `services/feed-ingest-plan/src/api/plan-failure.ts`
  - `services/feed-ingest-plan/src/api/prepare-planning-health.ts`
  - `services/feed-ingest-plan/src/api/record-standalone-run.ts`
  - `services/feed-ingest-plan/src/api/selection-operation.ts`
  - `services/feed-ingest-plan/src/api/stage-response.schema.ts`
  - `services/feed-ingest-plan/src/api/stage-store.ts`
  - `services/feed-ingest-plan/src/availability/feed-lifecycle.ts`
  - `services/feed-ingest-plan/src/config/planner-startup.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-observation.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/document-work.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/fetch-source.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/feed-client.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/harvest-types.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-pool.ts`
  - `services/feed-ingest-plan/src/harvest-feeds/article-parser-worker.ts`
  - `services/feed-ingest-plan/src/health-row.ts`
  - `services/feed-ingest-plan/src/logging/structured-logger.ts`
  - `services/feed-ingest-plan/src/logging/progress-logger.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/feed-lifecycle-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/feed-reliability-history.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/health-summary.ts`
  - `services/feed-ingest-plan/src/read-ledger-history/read-feed-health-fields.ts`
  - `services/feed-ingest-plan/src/recognize-article-entities.ts`
  - `services/feed-ingest-plan/src/record-article-entities.ts`
  - `services/feed-ingest-plan/src/reporting/failure-evidence-markdown.ts`
  - `services/feed-ingest-plan/src/reporting/plan-markdown.ts`
  - `services/feed-ingest-plan/src/resolve-run-context.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/src/run-health.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/screening-input.ts`
  - `services/feed-ingest-plan/src/screen-article-candidates/triage-gates.ts`
  - `services/feed-ingest-plan/src/select-articles.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-deliver.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-http-client.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-upload-inventory.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/retain-workflow-failure.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-api.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-server.ts`
  - `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-source-outcome.test.ts`
  - `services/feed-ingest-plan/test/article-url-cleanup.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/collection-recordings.ts`
  - `services/feed-ingest-plan/test/collection-work.test.ts`
  - `services/feed-ingest-plan/test/curate.test.ts`
  - `services/feed-ingest-plan/test/early-age.test.ts`
  - `services/feed-ingest-plan/test/failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/feed-first-use.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-report.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-history.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle-http.test.ts`
  - `services/feed-ingest-plan/test/feed-lifecycle.test.ts`
  - `services/feed-ingest-plan/test/file-baseline-recording.ts`
  - `services/feed-ingest-plan/test/harvest-recordings.ts`
  - `services/feed-ingest-plan/test/harvest-safety.test.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/parser-deadline.test.ts`
  - `services/feed-ingest-plan/test/partition-recordings.ts`
  - `services/feed-ingest-plan/test/persistence-recordings.ts`
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/plan-entry-points.test.ts`
  - `services/feed-ingest-plan/test/plan-recordings.ts`
  - `services/feed-ingest-plan/test/planner-diagnostics.test.ts`
  - `services/feed-ingest-plan/test/planner-process-recordings.ts`
  - `services/feed-ingest-plan/test/planning-health.test.ts`
  - `services/feed-ingest-plan/test/report-native-evidence.test.ts`
  - `services/feed-ingest-plan/test/request-report.test.ts`
  - `services/feed-ingest-plan/test/selection-metrics.test.ts`
  - `services/feed-ingest-plan/test/triage.test.ts`
  - `services/host-probes/scripts/feed-ingest-plan-profile-proof.ts`
  - `services/host-probes/scripts/feed-ingest-plan-profile-schema.ts`
  - `services/host-probes/scripts/feed-ingest-plan-cache-proof.ts`
  - `tests/fixtures/contracts/feed-ingest-candidate/one-article.json`
  - `tests/fixtures/contracts/feed-ingest-rejection/empty-feed.json`
  - `tests/fixtures/contracts/feed-ingest-event/one-observation.json`
  - `tests/fixtures/contracts/feed-ingest-document-observation/refused-fetch.json`
  - `tests/fixtures/contracts/feed-health-state/one-complete-snapshot.json`
  - `tests/fixtures/contracts/fetched-document/refused.json`
  - `tests/fixtures/contracts/parsed-feed-batch/empty.json`
  - `tests/fixtures/contracts/selected-feed-batch/empty.json`
  - `tests/fixtures/contracts/partitioned-feed-batch/empty.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/response.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/health.json`
  - `tests/fixtures/feed-ingest-plan/entry-points/feed-health-state.rows.json`
  - `tests/fixtures/feed-ingest-plan/health-field-history.json`
  - `tests/fixtures/feed-ingest-plan/ledger-history.json`
  - `tests/fixtures/feed-ingest-plan/portfolio-cases.json`
  - `tests/fixtures/feed-ingest-plan/report-events.json`
  - `tests/fixtures/feed-ingest-plan/screening-cases.json`
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/planner-run-diagnostics.md`
  - `docs/reference/feed-planner-ledgers.md`
- **Acceptance gates:** Local: inspect the shared selector; run common-contract/writer/planner checks and the gate guide's combined entry-point/file-input selection with the changed collection, worker-deadline, lifecycle, logging and diagnostic cases in one native service invocation. Use existing recorded transport and planner loopback coverage. CI: full planner/common/writer suites and existing resource proof; no live publishing dispatch.
- **Oracle:** A recorded collection completes feed fetch/retries, consumes each stored body through parse, harvests a real offered article, selects/partitions/persists output and retains correct work facts while another collection stays isolated; wrong/consumed inputs still fail and carried health checks are not counted twice. This does not measure throughput or validate old historical formats.

Table K - row 2 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| K1 | Replace redundant request/fetch/batch/collection UUIDs with the actual operation/execution references. | D13-D19; existing held-work consumers. |
| K2 | Separate parentage from completed-input links; keep business validation independent. | OpenTelemetry parent/link semantics; current store/config/run rules. |
| K3 | Keep observation slots, useful work evidence and collection lifecycle; do not create a tracing subsystem. | A1/A5; actual fetch/parse and completion paths. |
| K4 | Preserve check provenance with a native link and preserve startup outcome lookup with the preallocated trace. | Feed lifecycle history and runner recovery call sites. |

Table L - row 2 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Retain request/batch UUIDs as aliases of operations | Leaves the duplication this plan removes. | Extra generation, lookup and synchronization paths without a distinct resource. | D13-D19. |
| L2 | Use caller trace equality as an access check | Diagnostic context is not authority and valid linked inputs can cross traces. | A new ownership protocol and unrelated client failures. | H3/H5. |
| L3 | Wrap every HTTP command/response in CloudEvents | Native commands/results are not independently delivered events. | Rewriting every caller without event-delivery semantics. | CloudEvents scope; Table F. |

## 7. Row #3 - Convert host profiling without breaking Python control

- **Scope:** Remove redundant host UUID metadata while preserving the real profile resource, measurements and foreign control protocol.
- **Tasks:**
  - Apply D24/D25/D29. Allocate one profile context at enabled profile start; retain it unchanged through stop, expiry, process reuse/exit or service shutdown. Do not start/end SDK spans.
  - Keep handle lookup, PID/start-tick checks and repeated-stop retention. A stop with missing/different headers still addresses the same handle.
  - Pass profile context through the existing collector input/result. The collector performs the same measurement work; it does not create another context merely because it runs in a worker.
  - Update the embedded callers, proof inputs and real HHEM TypeScript bridge. Keep Python startup packets, HHEM identities, machine projection and ready/stopped handshake unchanged.
  - Preserve disabled profiling without starting a collector or fabricating a profile. Remove copied UUID metadata examples and old-format-only assertions in the cutover.
- **Files touched:**
  - `services/host-probes/package.json`
  - `services/host-probes/bun.lock`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/host-probes/src/api/task-command-schema.ts`
  - `services/host-probes/src/api/task-profile-manager.ts`
  - `services/host-probes/src/task-profile/profile-schema.ts`
  - `services/host-probes/src/task-profile/task-collector.ts`
  - `services/host-probes/src/task-profile/task-profiler.ts`
  - `services/host-probes/test/probe.test.ts`
  - `services/host-probes/scripts/feed-ingest-plan-profile-proof.ts`
  - `services/host-probes/scripts/feed-ingest-plan-profile-schema.ts`
  - `services/host-probes/scripts/feed-ingest-plan-cache-proof.ts`
  - `services/host-probes/scripts/host-task-profile-proof.ts`
  - `services/hhem-evaluator/tests/host-profile-bridge.ts`
  - `.github/scripts/summary-eval-hhem/measure-host.ts`
  - `tests/fixtures/host-probes/cache-resource-proof.json`
  - `docs/reference/host-probe-api.md`
  - `docs/reference/host-metrics.md`
- **Acceptance gates:** Local: host check and focused real handler/collector cases, then the existing Python host-reader parity and pipeline-measurement cases because this row changes their actual TypeScript boundary. CI: existing native host suite, resource proof and isolated HHEM suite. Do not add listeners, model downloads or a trace test suite.
- **Oracle:** Start a real enabled profile, stop/read it by the same handle and pass its result through the existing HHEM bridge; the Python-consumed measurement projection remains correct while the profile retains one operation context. This does not join that context to uninstrumented Python work or certify production hardware performance.

Table M - row 3 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| M1 | Retain the genuine profile handle; remove only duplicated operation/execution UUIDs. | Current manager's live-resource contract; D24/D25. |
| M2 | Keep the ongoing Python protocol as a boundary, not a legacy TypeScript API format. | Native Python validators and consumed projection. |

Table N - row 3 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Put a hex trace ID into a foreign UUID field | Invalidates the foreign protocol and changes its meaning. | A deliberate Python contract conversion and all affected readers. | H7. |
| N2 | Rename the handle to `spanId` | A control resource and an operation have different lifetimes and lookup rules. | A new start/stop resource contract without removing a real duplication. | D25/M1. |

## 8. Row #4 - Convert summarizer event metadata

- **Scope:** Replace timestamp-based event metadata without changing summary requests/results or adding runtime tracing.
- **Tasks:**
  - Apply D1-D4/D6/D7/D28 to the real event bus/schema. Delete its UUIDv5 implementation and clock-derived correlation; use the shared event factory and explicit operation context.
  - Keep current event-type values and complete structured output under `data`. Compose shared envelope validation with the service's existing data validators; do not duplicate them across Zod major versions.
  - Allocate context at CLI/HTTP entry and pass it through existing extraction/inference operations and callbacks. Derive child context where actual work is nested; do not add timers, active spans or shutdown flushes.
  - Isolate concurrent request contexts and their event histories. Update reporter/event-history readers with the writer.
  - Remove full-event console dumps. Preserve named private event output and model destination controls; do not require new headers at the model server or upload traces.
  - Adapt functional cases and remove retired UUID/prefix assertions/helpers. Do not retain both event shapes.
- **Files touched:**
  - `services/summarizer/package.json`
  - `services/summarizer/bun.lock`
  - `services/summarizer/src/start-api-server.ts`
  - `services/summarizer/src/services/dispatch-event.service.ts`
  - `services/summarizer/src/schemas/pipeline-event.schema.ts`
  - `services/summarizer/src/schemas/export-all-schemas.ts`
  - `services/summarizer/src/api/serve-http-api.ts`
  - `services/summarizer/src/execute-cli-pipeline.ts`
  - `services/summarizer/src/pipeline/orchestrate-pipeline.service.ts`
  - `services/summarizer/src/reporters/render-github-summary.reporter.ts`
  - `services/summarizer/test/model-runtime.test.ts`
  - `services/summarizer/test/pipeline-events.test.ts`
  - `.github/workflows/yen-ai-pipeline.yml`
  - `docs/reference/summarizer-api.md`
- **Acceptance gates:** Local: summarizer check and combined event/model-boundary cases with recorded model responses and existing local transport. Cover ordinary output, failures and concurrent request isolation without an external model. CI: full summarizer suite and ordinary packaging.
- **Oracle:** Emit two same-type events in one operation, read the saved events and recover complete structured output equal to the API/CLI result; occurrences stay distinct and concurrent requests do not exchange context or history. This does not establish model quality.

Table O - row 4 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| O1 | Retain domain event data while excluding content from metadata/console diagnostics. | Actual structured-output consumers; H8. |
| O2 | Keep native summary commands/responses rather than wrapping the HTTP API in CloudEvents. | Existing API contract; event/command distinction. |

Table P - row 4 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| P1 | Keep deterministic event IDs with another sequence seed | Adds occurrence-identity machinery without a business need. | Counters, persistence and allocation rules instead of a fresh standard event ID. | D1/H1. |
| P2 | Delete content from every event `data` field | Removes a real domain result, not unsafe diagnostic metadata. | A replacement result-transfer protocol outside this change. | D4/O1. |

## 9. Row #5 - Convert phased workflow events and continuation

- **Scope:** Replace workflow event metadata while preserving the saved inference-to-evaluation handoff and existing measurements.
- **Tasks:**
  - Apply D1-D3/D5-D7/D28 to `AIEventPipeline`. Delete its local UUIDv5 code and existing-correlation constructor parameter. Store/read only the current event format.
  - Extract the real named-file event reading/selection into `read-pipeline-events.ts` and foreign request construction into `prepare-evaluation-request.ts`; use these same functions in the production phase path and functional test.
  - Select `type === "OUTPUT_STRUCTURED"` and read `data.result`. Validate the named input; do not rerun inference, allocate replacement saved-event IDs or silently drop malformed records.
  - Allocate a fresh root per phase invocation. Each evaluation operation is a child of that phase and links to its own saved input's producer context. Do not take the first saved correlation as every article's parent.
  - Preserve D5's timing calculations, including the existing resumed cumulative counter; move their stored paths and report readers only. Do not represent a log gap as an operation duration or build new span timing.
  - Keep the foreign evaluator request/response under H7. Allocate its required separate UUID at that boundary, retain returned machine measurements, and do not relabel its Python event as a native TypeScript CloudEvent.
  - Import the shared source entry point explicitly and install its own locked dependencies. Leave runtime versions and unrelated dynamic inference dependencies unchanged. Upload existing application artifacts only.
  - Remove obsolete event parsers, deterministic helpers, old-format-only fixtures/tests and stale documentation as the replacement lands.
- **Files touched:**
  - `.github/scripts/ai-pipeline.ts`
  - `.github/scripts/read-pipeline-events.ts`
  - `.github/scripts/prepare-evaluation-request.ts`
  - `.github/scripts/test/workflow-handoff.test.ts`
  - `.github/workflows/ai-pipeline-tests.yml`
  - `tests/fixtures/typescript-metadata/workflow-output-event.json`
  - `tests/fixtures/typescript-metadata/evaluator-request.json`
  - `tests/fixtures/typescript-metadata/evaluator-response.json`
  - `docs/reference/workflow-pipeline-events.md`
- **Acceptance gates:** Local: shared check and `bun test .github\scripts\test\workflow-handoff.test.ts` against named recorded input/output; call the production reader/selection/request-builder, not copies. Preserve actual output, saved identity, per-input relationships and foreign protocol behavior. CI: native cases and ordinary workflow installation/packaging. No live inference/evaluation dispatch is a metadata gate.
- **Oracle:** The production reader selects a saved inference output unchanged, the production request builder hands its correct source/summary to evaluation, and separate evaluation contexts link to their respective producers without rewriting saved events; the foreign response still yields the same machine measurements. This does not prove live evaluator availability or performance.

Table Q - row 5 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| Q1 | A new phase has its own execution and per-input dependency links. | OpenTelemetry asynchronous-link semantics; existing phase boundary. |
| Q2 | Preserve meaningful existing measurements and the foreign evaluator wire format. | D5/H7; verified current consumers. |

Table R - row 5 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| R1 | Read both old event JSONL and CloudEvents | Adds an unwanted compatibility tail. | A dual reader, duplicate fixtures and later removal. | A4. |
| R2 | Force independent phases and Python into one invented parent chain | Misstates their relationship and hides individual inputs. | A real cross-process propagation design, including Python. | E3/E4/Q1. |

## 10. Standard references

Table S - primary references

| ID | Reference | What it settles |
| --- | --- | --- |
| S1 | [CloudEvents 1.0 specification](https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md) | Event envelope, `source + id` identity, `data` and URI-reference source. |
| S2 | [CloudEvents distributed-tracing extension](https://github.com/cloudevents/spec/blob/main/cloudevents/extensions/distributed-tracing.md) | `traceparent` and `tracestate` event extension names. |
| S3 | [OpenTelemetry tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/) | Execution/operation identity, parentage and input links. Following these names does not require recording/exporting spans. |
| S4 | [W3C Trace Context](https://www.w3.org/TR/trace-context/) | Carrier syntax, nonzero trace/span identifiers and invalid optional context. |
| S5 | [OpenTelemetry trace data model](https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/trace/v1/trace.proto) | Parent/link semantics underlying the native metadata names. This plan does not produce OTLP. |
