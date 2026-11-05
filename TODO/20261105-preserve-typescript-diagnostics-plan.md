# Preserve TypeScript article and delivery diagnostics

**Last Updated**: 2026-11-05
**Level**: 5 - versioned diagnostic contracts.
**Status**: Both review PRs are open. The combined candidate includes the main service rename and is under verification.

## 0. Operating contract

Table A - Plan scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Keep the specific article failure cause and the actual delivery result/request identity visible to the operator. |
| A2 | Hard scope - in | TypeScript article failure diagnostics; existing stderr relay and log mirror; same-run Markdown report capture; separate delivery-completion payload; existing request operation context; fixture tests and directly related docs. |
| A3 | Hard scope - out | Table B. |
| A4 | Chosen strategy | Reuse the existing `HarvestDiagnosticsSchema`; typed stderr plus same-run report capture, previously called B2; no ledger extension. Architecture: two focused PRs, with both delivery faults in the same PR. |
| A5 | Reviewed evidence | Main revision `656ee8d60d4898b388e0b2206218c70c8b571bac`; the diagnostic writer, evidence contracts and supervision logic are unchanged after the service moved to `services/serve-pipeline-apis/`. The supplied parent brief identifies article detail loss, delivery fact loss and wrong delivery request context. The full parent transcript was not directly accessible. |
| A6 | Historical evidence limit | The supplied historical article reached quality rejection; the enabled minimum was 60 extracted source words. Its exact count was not saved, so whether the page was short or extraction missed content remains unknown. No historical facts will be invented. |
| A7 | Execution | Execute per docs/how-to/execute-a-plan.md; parallel N = 1 because both rows share the writer, tests and docs; one dedicated worktree and ordinary review PR per row; no delegated investigation or live workflow dispatch. Row 2 starts from row 1's verified pushed foundation after its PR opens, without waiting for a merge. One session merges the ordered PR group after its checks pass. Honor the escalation triggers below. |
| A8 | ESCALATE triggers | 1. A ledger, native HTTP result or receipt must change. 2. A source, event type, server name or tracking identity must change. 3. Article acceptance, reliability scoring, Python or the published frontend must change. 4. New raw content retention, a new model destination or a tracing runtime is required. 5. An older-format reader, migration, backfill or additional defect outside this brief is proposed. |
| A9 | Repository location | `TODO/20261105-preserve-typescript-diagnostics-plan.md`; the active execution specification. |

Table B - Excluded work and its cost

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | New ledger columns, diagnostic state stores and later-run diagnostic queries | Later runs cannot query the newly logged word counts or extraction causes; same-run logs/reports provide them to people only. | A named later-run consumer and a separate retained-contract design. |
| B2 | Native HTTP response changes, receipt changes and new endpoints | Callers continue receiving their existing native shapes; full article diagnostics are in stderr/report evidence, not `/plan`. | A separate requirement for a native API consumer. |
| B3 | Article acceptance, the 60-word rule and reliability scoring | Diagnostics do not repair source quality or change which articles pass. | A separate acceptance/scoring requirement with its evidence. |
| B4 | New raw article text/HTML output, refetching the historical page and historical backfills | The original missing count and page-versus-extractor explanation cannot be recovered by this correction. | A separate content-handling investigation; it is not inferred from this plan. |
| B5 | Python, published frontend, source/type/server renaming, PID logging, tracing runtime and unrelated `code: null` cleanup | Those surfaces and unrelated cleanup remain unchanged. | A separate concrete requirement and its named consumers. |
| B6 | Live workflow dispatch and publication certification | Merging the code does not prove a live feed or delivery run. | A separate operational task with its verification. |
| B7 | Claiming coverage beyond the supplied parent brief | Full parent-chat coverage remains unverified; the three supplied faults are covered below. | Access to the parent transcript, not another choice about B2 or the JSON shape. |

## 1. Status Reckoner

Table C - PR rows

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Article failure diagnostics and same-run report | - | A | IN-FLIGHT | jubilant-giggle | #1922 | - |
| C2 | 2 | Delivery completion facts and request context | 1 | A | IN-FLIGHT | verbose-couscous | #1923 | - |

## 2. Row #1 - Article failure diagnostics and same-run report

**Scope:** Preserve each final article failure's complete safe typed cause through stderr, the existing log mirror and the same-run report, without changing acceptance, ledgers or native HTTP responses.

**Files touched:**

- `packages/common-contracts/src/schemas/article-failure-diagnostic.schema.ts` - new strict terminal event/detail contract.
- `packages/common-contracts/src/schemas/event.schema.ts` - share the existing publisher limits without changing the event shape.
- `packages/common-contracts/src/index.ts` - export the new contract.
- `packages/common-contracts/test/article-failure-diagnostic.test.ts` - new contract coverage.
- `services/feed-ingest-plan/src/harvest-feeds/record-rejection.ts` - emit a safe terminal projection after native rejection validation.
- `services/feed-ingest-plan/src/harvest-feeds/harvest-article.ts` - retain and supply the existing actual fetch/parse context.
- `services/feed-ingest-plan/src/api/fetch-operation.ts` - connect the existing stage logger to final article rejection diagnostics.
- `services/feed-ingest-plan/src/api/parse-operation.ts` - connect that logger and preserve available native fetch/extraction evidence.
- `services/feed-ingest-plan/src/logging/structured-logger.ts` - publish the narrowly validated complete diagnostic without generic field loss.
- `services/serve-pipeline-apis/src/write-server-event.ts` - preserve accepted native terminal article CloudEvents.
- `services/feed-ingest-plan/scripts/read-article-failure-diagnostics.ts` - new bounded reader for the existing named log.
- `services/feed-ingest-plan/scripts/feed-ingest-plan-report-evidence.ts` - collect separate typed diagnostic evidence.
- `services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts` - retain diagnostics on complete, partial, error and absent-response paths.
- `services/feed-ingest-plan/src/reporting/article-failure-evidence.ts` - correlate and fold complete safe native diagnostics.
- `services/feed-ingest-plan/src/reporting/failure-evidence-markdown.ts` - correlate evidence and render specific causes/full safe details.
- `services/feed-ingest-plan/src/reporting/plan-markdown.ts` - accept diagnostics in both normal and unavailable-result rendering.
- `services/feed-ingest-plan/test/article-failure-retention.test.ts`
- `services/feed-ingest-plan/test/harvest.test.ts`
- `services/feed-ingest-plan/test/operation-logging.test.ts`
- `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
- `services/feed-ingest-plan/test/failure-evidence.test.ts`
- `services/feed-ingest-plan/test/report-native-evidence.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-outputs.test.ts` - share captured failure evidence between both report modes.
- `services/feed-ingest-plan/test/write-article-failure-events.ts` - real recorded article work in an stderr-producing child.
- `services/serve-pipeline-apis/test/server-events.test.ts`
- `services/serve-pipeline-apis/test/write-server-events.ts`
- `tests/fixtures/feed-ingest-plan/article-terminal-failures.json`
- `docs/architecture/sources/feed-harvesting.md` - work facts and failures.
- `docs/architecture/sources/feed-operator-api.md` - structured logs and Markdown evidence input.
- `docs/reference/serve-pipeline-apis.md` - accepted article diagnostics and mirror availability.
- `TODO/20261105-preserve-typescript-diagnostics-plan.md` - this row's status only.

**Contract:**

Table D - Agreed article event shape

| Id | Field | Type / rule |
| --- | --- | --- |
| D1 | CloudEvent envelope | Existing native envelope, configured planner source and `planner.progress` type; preserve original occurrence ID, time and operation carrier through the relay. |
| D2 | `data.version` | Existing `FEED_INGEST_EVENT_VERSION`, currently `2026-11-05`; no second version field. |
| D3 | `data.run_id` | Existing `RunIdSchema`; actual captured run. |
| D4 | `data.operation` | `fetch`, `parse` or `quality`; quality rejection uses the existing parse operation context. |
| D5 | `data.phase` | Literal `failed`. |
| D6 | `data.details.attempt` | Positive integer; actual attempt. |
| D7 | `data.details.feed_id` | Existing configured feed slug. |
| D8 | `data.details.candidate_id` | Required captured lowercase hyphenated UUIDv4. |
| D9 | `data.details.url_key` | Required SHA-256 article address key, not the address. |
| D10 | `data.details.stage` | Literal `harvest-feeds`. |
| D11 | `data.details.reason_code` | Existing `FETCH_FAILED`, `FETCH_FAILED_HTTP`, `FETCH_TIMEOUT`, `EXTRACT_FAILED`, `EXTRACT_EMPTY`, or post-parse `MISSING_REQUIRED_FIELDS`. |
| D12 | `data.details.diagnostics` | Existing complete `HarvestDiagnosticsSchema`; fields in Tables E and F. |

Table E - Native diagnostic fields

| Id | Field inside `diagnostics` | Type / availability |
| --- | --- | --- |
| E1 | `http_status` | Integer from 100 through 599, or null. |
| E2 | `fetch_failure` | `http`, `timeout`, `unsafe-target`, `dns`, `network`, `body-too-large`, `redirect-loop`, or null. |
| E3 | `error_code` | Native uppercase/underscore code, at most 64 characters, or null; never arbitrary exception text. |
| E4 | `stopped_stage` | `fetch`, `extract`, `parse`, or null. |
| E5 | `detail` | Native bounded fetch/extraction reason, `malformed-feed`, `empty-feed`, quality signal from F7, or null. |
| E6 | `failure_code` | Existing `PlannerItemFailureCodeSchema`, or null; no duplicated vocabulary. |
| E7 | `extraction_failure` | `missing-document-root`, `dom-depth-exceeded`, `empty-content`, `missing-title`, `parser-timeout`, `parser-cancelled`, `parser-failed`, or null. |
| E8 | `fetch_ms`, `extract_ms`, `pacing_time_ms` | Nonnegative integer milliseconds, or null. Do not infer duration by summing retries. |
| E9 | `pacing_settings` | Existing validated `enabled` boolean and nonnegative integer `domain_delay_ms`, `publisher_delay_ms`, `jitter_ms`, or null. |
| E10 | `warnings` | At most two native entries: `malformed-json-ld`, `semantic-dom-fallback`; no recorded warnings is `[]`. |
| E11 | `body_limit` | Existing nonnegative integer `configured_limit_bytes` and `observed_at_least_bytes`, or null; the observation exceeds the limit and requires `body-too-large`. |
| E12 | `response_evidence` | Existing safe native response projection, or null. |
| E13 | `response_evidence.content_type` | Available MIME type without parameters, at most 512 ASCII characters, or null. |
| E14 | `response_evidence.decoded_bytes`, `response_evidence.declared_content_length` | Available nonnegative integer bytes, or null. |
| E15 | `response_evidence.request_profile` | Existing native `firefox` or `chrome` when response evidence exists. |
| E16 | `response_evidence.selected_headers`, `response_evidence.headers_truncated` | Empty object and empty list in this log projection; header values are not retained. |
| E17 | `quality` | The complete native object in Table F, or null when quality was not measured. |

Table F - Native measured quality

| Id | Field inside `quality` | Type / meaning |
| --- | --- | --- |
| F1 | `source_word_count`, `word_count` | Nonnegative integers; source count describes the extracted body before the token cap, not every word on the source page. |
| F2 | `corroborated_word_count` | Positive integer or null; an independent observed zero is invalid. |
| F3 | `token_count` | Nonnegative integer or null. |
| F4 | `too_short`, `not_prose`, `rejected` | Booleans. |
| F5 | `contaminated`, `boilerplate`, `truncated` | Booleans or null. |
| F6 | `truncated_at_tokens`, `truncation_cap_tokens` | Positive integer or null for the cut point; integer at least 256 tokens for the native cap. |
| F7 | `failure_code` | `contaminated`, `boilerplate`, `not_prose`, `too_short`, or null. |
| F8 | `extractor_version`, `sanitizer_version` | Native nonempty version strings. |
| F9 | Cross-field rules | Reuse the native model's count, contamination, truncation and failure-precedence validation. Unknown quality is null, not a zero-filled object. |

**Decisions:**

Table G - Article implementation sequence

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Declare the strict terminal subtype first; stamp its schema metadata `2026-11-05`, add a one-line changelog and current-only read rule. Keep `packages/common-contracts/src/schemas/harvest-diagnostics.schema.ts` unchanged and reuse it, including quality. | Native contract authority; Tables D-F. |
| G2 | Emit only after a final article fetch/extraction rejection with captured identity and native diagnostics. Include post-parse missing title; exclude feed outcomes, preflight exclusions and recoverable per-attempt failures. | Existing native terminal outcomes. |
| G3 | `recordRejection` projects identities, stage/reason and diagnostics, not its full transient record. Use the existing `document_activity` callback and actual operation metadata. Harvest retains its existing fetch/parse contexts; independent API callers connect their existing logger. No new tracking identity or context hook. | Existing harvest and API logging paths. |
| G4 | In parse diagnostics, retain available native fetch evidence from the held artifact rather than copying only HTTP/pacing fields. Keep unmeasured duration null and native HTTP response shapes unchanged. | Existing native fetch diagnostic projection. |
| G5 | Add a narrowly validated publisher branch before generic detail cleaning and ordinary document/quality-subset checks. Do not add `publisher_id` or a second quality object merely to satisfy those checks. Preserve existing bounds and explicit compliance reporting. | Agreed terminal shape; existing publisher controls. |
| G6 | Safely project available response facts: omit header values and MIME parameters, retain native nulls and safe facts. Exclude body, HTML, title, addresses, secrets, arbitrary exception text and stacks. | Native diagnostics and trust boundary. |
| G7 | The server writer validates this same terminal subtype and mirrors the original CloudEvent unchanged. `services/feed-ingest-plan/scripts/http-child-lifetime.ts` and `services/serve-pipeline-apis/src/supervise-api-task.ts` already pipe/drain stderr and remain unchanged. Other module stderr does not bypass its current validation. | Existing diagnostic relay. |
| G8 | Add separate `article_diagnostics` to the existing in-memory `ReportFailureEvidence`, not to rejected rows, `/plan` or another endpoint. The new reader uses only distinct named log files returned by `readServerEvidence`; no directory walk or latest-file search. | Existing report and same-run evidence path. |
| G9 | Validate expected run/attempt from explicit report inputs, saved response or saved failure context; use available captured execution metadata to exclude unrelated requests. Missing identity is an explicit correlation gap, not a guessed run. | Existing run/operation meanings. |
| G10 | Correlate by run, attempt and captured candidate; check feed/address/reason agreement. Identical repetitions count once; conflicting records fail explicitly. Health remains the aggregate authority. Show log-only missing-title evidence without adding it twice to totals or altering reliability. | Existing report evidence semantics. |
| G11 | Name the available typed cause in attention text; expose all safe fields in folded detail. Use unavailable only for absent facts. Read diagnostics before error-response early returns and carry them through unavailable rendering; collect them with existing explicit run/attempt inputs even when `response.json` is absent. Never invent successful planning or health. | Existing renderer and workflow adapter. |
| G12 | Missing/partial mirror, malformed terminal lines and unavailable identity retain explicit evidence-gap notices. Complete records from a partial log remain usable. Do not turn unexpected programming failures into empty evidence. | Existing degrade-with-evidence behavior. |
| G13 | Leave `packages/common-contracts/src/schemas/rejected-article.schema.ts`, `services/feed-ingest-plan/src/record-harvest-failures.ts`, `services/feed-ingest-plan/src/select-articles.ts`, ledger validation/compaction and saved ledger columns unchanged. | B1 and B2. |
| G14 | One behavioral commit: contract -> relay/report readers -> producer/publisher wiring -> fixtures/tests/docs. Reader and writer changes land together. No unrelated structural refactoring; any necessary behavior-preserving Extract Function is a separate structural commit, never mixed into the behavior commit. | Two-hat commit discipline. |

**Acceptance gates:**

- Contract: reject unknown diagnostic fields and invalid native combinations; validate the full quality object and null behavior against the existing authority.
- Unit: safe response projection, typed cause rendering, correlation and duplicate/conflict rules.
- Integration: recorded source inputs plus real parser work carry parser failure, empty extraction, quality refusal, missing title and fetch failure through actual stderr, mirror readback and report.
- Fixture inputs: extend the named terminal fixture in Files touched; continue reading unchanged `tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json`. Load fixtures inside tests. No mocks or external network access.
- Required cases: measured zero versus null; warnings/versions; recovered internal retries; repeated/conflicting records; wrong run/attempt/request; missing/partial logs; complete/partial/error/absent responses. Unsafe title/body/HTML/address/header/exception inputs must not appear in new diagnostics or reports.
- Preservation: unchanged article pass/fail results, native HTTP response shapes, rejection ledger rows and health totals. No browser or Python suite is required for this TypeScript operator-report change.
- Local checks after implementation:

```powershell
npm --prefix .\frontend run test:changed -- --list
bun run --cwd .\packages\common-contracts check
bun run --cwd .\services\feed-ingest-plan check
bun run --cwd .\services\serve-pipeline-apis check
bun run --cwd .\packages\common-contracts test .\test\article-failure-diagnostic.test.ts .\test\rejection.test.ts
bun run --cwd .\services\feed-ingest-plan test .\test\article-failure-retention.test.ts .\test\harvest.test.ts .\test\operation-logging.test.ts .\test\network-failure-evidence.test.ts .\test\failure-evidence.test.ts .\test\report-native-evidence.test.ts
bun run --cwd .\services\serve-pipeline-apis test .\test\server-events.test.ts
```

- Apply existing lint checks selected for the actual diff per `docs/how-to/run-the-gates.md`. Add no dependency; restore one only after a missing-dependency failure.
- CI: ordinary full-suite checks on the merge candidate, once. Do not dispatch a live data-writing workflow as a gate.

**Oracle:** The actual native final-rejection diagnostic equals the accepted stderr event, mirrored event and report detail after the declared safe response projection, while existing outcomes and ledger rows retain their values. This cannot recover the historical word count or establish whether extraction captured the entire source page.

**Rejected alternatives:**

Table H - Evaluated article alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Typed stderr without same-run report capture | Leaves the existing report unable to explain the newly logged causes. | Saves the named-log reader/rendering work, but gives up the requested same-run report detail. | Chosen stderr/report strategy. |
| H2 | Extend the rejected-article ledger instead | Not the selected retention path; changes later-run data without a named consumer for these new facts. | New row contract/columns, writer/readers, retention/compaction checks and broader consumer coordination. | B1; existing ledger consumers. |

## 3. Row #2 - Delivery completion facts and request context

**Scope:** Keep the native delivery result facts and actual receiving request context in a separate validated completion event while lifecycle events retain their supervision context.

**Files touched:**

- `services/feed-ingest-plan/scripts/safe-persist-http-diagnostic.ts` - new native relay contract derived from existing field authorities.
- `services/feed-ingest-plan/scripts/safe-persist-http-api.ts` - emit the already allocated request context with completion facts.
- `services/feed-ingest-plan/package.json` - export that diagnostic contract; no new dependency.
- `services/serve-pipeline-apis/src/delivery-completion-diagnostic.ts` - new strict completion payload/builder.
- `services/serve-pipeline-apis/src/write-server-event.ts` - route validated completion separately from lifecycle events.
- `services/serve-pipeline-apis/src/server-evidence.ts` - separate lifecycle phase membership/metadata; do not change saved task evidence.
- `services/feed-ingest-plan/test/safe-persist-http.test.ts`
- `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
- `services/serve-pipeline-apis/test/server-events.test.ts`
- `services/serve-pipeline-apis/test/write-server-events.ts`
- `docs/architecture/sources/feed-operator-api.md` - safe-persist completion log contract.
- `docs/reference/serve-pipeline-apis.md` - separate payloads, contexts and current-only diagnostics.
- `TODO/20261105-preserve-typescript-diagnostics-plan.md` - this row's status only.

**Contract:**

Table I - Delivery allowlist and mapping

| Id | Native relay field / server field | Type / rule |
| --- | --- | --- |
| I1 | Relay `event` | Literal `safe_persist_http_completed`; selects the existing configured completion event type, not a new type. |
| I2 | Relay `run_number` -> completion `data.run_id` | Existing numeric-string `SafePersistHttpRequestSchema.shape.runNumber`; actual request run, no additional alias or supervision fallback. |
| I3 | Relay `attempt` -> completion `data.attempt` | Existing positive integer attempt; actual request value. |
| I4 | Relay/completion `status` | Existing `MetadataDeliveryResultSchema.shape.status`: `landed`, `already-on-main`, `no-changes`, `failed`. |
| I5 | Relay/completion `commit` | Existing native lowercase hexadecimal commit string, 40-64 characters, or null. |
| I6 | Relay/completion `files` | Existing native nonnegative integer file count; do not copy paths. |
| I7 | Relay/completion `context` | Existing complete `OperationMetadataSchema`, never null; also supplies the CloudEvent operation carrier. |
| I8 | `context.traceId`, `context.spanId` | Existing nonzero lowercase hexadecimal execution ID of 32 characters and operation ID of 16 characters. |
| I9 | `context.parentSpanId`, `context.traceState`, `context.links` | Existing optional parent ID, optional valid W3C state and required native operation-link array; preserve rather than reconstruct. |
| I10 | Completion `data.server_name`, `data.group`, `data.phase` | Existing server name, delivery group and `operation_completed` phase; derive native field validators rather than redesign names. |
| I11 | Completion ancillary fields | Preserve existing `severity`, finite nonnegative nullable `duration_ms`, nullable integer `exit_code` and nullable bounded-code behavior. Unrelated `code: null` cleanup stays out of scope. |
| I12 | Lifecycle payload | Existing lifecycle fields and supervision context; exclude `operation_completed` from lifecycle phase membership. |

**Decisions:**

Table J - Delivery implementation sequence

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Declare native relay/completion shapes and changed lifecycle diagnostic metadata first. Stamp them `2026-11-05`, add one-line changelogs and current-only rules. Do not change the separate saved `ServerEvidenceSchema`. | Native diagnostic authority. |
| J2 | Derive request/result field validators from `services/feed-ingest-plan/scripts/feed-ingest-plan-delivery-result.ts` and context validation from the existing common contract. API server already depends on the feed package; do not add a reverse dependency or copy the status vocabulary. | Existing package and contract graph. |
| J3 | The handler passes the exact context already allocated by `commandContext(captureRequestRuntime(...))` to its diagnostic. Its native delivery call, HTTP result and receipt remain unchanged. | Existing receiving operation. |
| J4 | The relay/writer accepts only the explicit allowlist in Table I. Validate the native request/result before projection. Missing or invalid completion context is an explicit diagnostic error, not a fallback to supervision or a newly allocated child. | Diagnostic contract and request isolation. |
| J5 | `createCloudEvent` receives that exact request context. Retain full context in completion data as well as its carrier; keep lifecycle writes on the existing supervision context. | Existing operation/event meanings. |
| J6 | Keep configured sources, event types and server names, process-ID handling and other module projections unchanged. Do not add a tracing runtime or arbitrary diagnostic spreading. | Existing server contract. |
| J7 | Leave native HTTP schemas/client, delivery receipts, ledgers and behavior unchanged. Completion diagnostics do not become the delivery confirmation authority. | Existing native result and receipt readers. |
| J8 | One behavioral commit: contract -> completion reader/builder -> handler/relay wiring -> real integration assertions/docs. Both delivery faults land together; no structural refactoring is required. | One coherent completion outcome. |
| J9 | Both rows use current-only diagnostic readers/writers together. Historical files/events remain untouched; no legacy aliases, dual readers, migrations or backfills. Unchanged ledgers/native results retain their existing readers. | Diagnostic cutover scope. |
| J10 | Link to `docs/architecture/contracts/identity.md` for event/operation meanings; do not rewrite those meanings or introduce another request identifier. | Existing identity contract. |
| J11 | Row 2 follows Row 1 only to serialize their shared writer, tests, docs and plan edits. Either fix is independently reversible; there is no business dependency. | Shared-file scheduling. |

**Acceptance gates:**

- Contract/unit: strict lifecycle versus completion shapes, native field validators, unknown-field refusal, missing-context refusal and unchanged ancillary-field handling.
- Integration: extend existing real loopback HTTP/local Git finalization coverage beyond event-type presence; source/network responses remain recorded fixtures.
- Capture the actual handler diagnostic and compare full context/facts against emitted and read-back completion data and the native CloudEvent carrier. Checking only trace ID is insufficient.
- Two real requests with distinct supplied contexts retain distinct receiving operations and their own run/attempt/status/commit/files. Neither completion uses the supervision operation or another newly invented operation.
- Lifecycle start/ready/stop events retain their original supervision operation. Confirm delivery status/commit/count and exact native receipt paths remain equal to the actual HTTP result/saved receipt.
- Cover native completion statuses using existing real delivery fixtures. No new logged paths or PIDs, remote Git fixture or live workflow.
- Local checks after implementation:

```powershell
npm --prefix .\frontend run test:changed -- --list
bun run --cwd .\services\feed-ingest-plan check
bun run --cwd .\services\serve-pipeline-apis check
bun run --cwd .\services\feed-ingest-plan test .\test\safe-persist-http.test.ts .\test\feed-ingest-plan-finalization.test.ts
bun run --cwd .\services\serve-pipeline-apis test .\test\server-events.test.ts
```

- Apply existing selected lint checks. Export-only metadata does not justify dependency installation; restore only after an actual missing-dependency failure.
- CI: ordinary full-suite checks on the merge candidate, once; no live data-writing workflow dispatch.

**Oracle:** Each actual native completion diagnostic has one matching emitted/read-back completion event with equal allowed facts and full request context, while lifecycle identity and native HTTP result/receipt remain unchanged. This does not certify live remote delivery or unrelated logging cleanup.

**Rejected alternatives:**

Table K - Evaluated delivery alternative

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Keep completion in the lifecycle-only projection and supervision context | It is the confirmed defect: loses delivery facts and attributes request work to the wrong operation. | No correction work, but none of the requested delivery diagnostic guarantees; adding nullable delivery fields to every lifecycle event would still require a request-context branch. | Separate validated payload and actual-context requirement. |
