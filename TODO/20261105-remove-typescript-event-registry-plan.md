# Remove the TypeScript event-source registry

**Last Updated**: 2026-11-05
**Level**: 5 - producer identity ownership and native API diagnostic contracts.

## 0. Operating contract

Table A - Operating contract

| ID | Field | Value |
| --- | --- | --- |
| A1 | Intent | Every TypeScript HTTP API emits its application events with a native producer identity, without loading a shared source registry. |
| A2 | Hard scope - in | Remove the registry, loader and exports; migrate every caller, config-copy list and CI reference; give every API in Table C real native event emission; retire obsolete registry and plain-delivery-translation tests; update canonical documentation. |
| A3 | Meaning of native support | The API constructs and validates its own CloudEvents 1.0 events using its local protocol identity and actual operation context. A constant without an emitting code path does not qualify. Native HTTP response bodies are not event envelopes. |
| A4 | Chosen construction | Producer-local protocol constants, existing shared envelope/context helpers, service-owned diagnostic contracts and strict identity-preserving relay. Architecture authority: Fowler. |
| A5 | Compatibility | Preserve existing source URIs, event types, saved application payloads, HTTP routes/results, resource identities, private readiness/stdout protocols and private profile transport. Table E declares the additions and the live transport being retired. |
| A6 | Contract movement | Delete the authored configuration contract. Move the delivery event contract to its producer without changing its saved shape. Add the native diagnostic contracts in Table E before their writers. No historical event, receipt, ledger or server-evidence migration. |
| A7 | Execution boundary | Execute the three rows in order. No instruction-file change or exception is implied. |
| A8 | ESCALATE triggers | 1. An additional authored HTTP API or registry consumer changes this inventory. 2. A declared URI, response, saved shape or operation relationship cannot be preserved. 3. A named consumer still requires the retired transport. 4. Work requires a dependency, workspace, source-selection knob, instruction-file change or another persisted-family migration. |
| A9 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan; keep parallel N = 1 rows in flight; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. Parallel N is one because the source cutover, reader expansion and writer cutover share contracts and must land in order. |

Table B - Scope boundaries

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Replacing HTTP response bodies with CloudEvents or adding response fields | Clients continue to receive their existing native JSON rather than a universal response envelope. | A separate requirement for an HTTP protocol migration, with its client changes priced first. |
| B2 | Changing Python evaluator events | Their existing foreign protocol remains separate. Only the named configuration-staging dependency is removed here. | A separate cross-language event-standardization requirement. |
| B3 | New tracing, log collection, retention, dependencies or feature flags | Native events use the current stderr/private-file channels and existing libraries; no new monitoring product or runtime is delivered. | A concrete capability the existing channels cannot provide. |
| B4 | Rewriting historical events, recorded identities or committed data | Older source identities retain their original meaning; historical recordings are not relabeled to look newly emitted. | A demonstrated read-side incompatibility, escalated before changing its family. |
| B5 | Published-site changes and unrelated test or documentation cleanup | The site and unrelated legacy code remain as they are; this plan does not certify their behavior. | A direct dependency of the native-event change, identified before widening the row. |
| B6 | Changes to CLAUDE.md or AGENTS.md | The implementation must fit their existing protocol-literal allowance and architecture boundaries. | A separate explicit instruction to change the protected file. |

Table C - Complete TypeScript HTTP API check

| ID | API and verified implementation | Checked routes or modules | Required outcome |
| --- | --- | --- | --- |
| C1 | Planner: `services/feed-ingest-plan/src/api/server.ts` and its named `src/api/routes/` modules | Under `/api/2026-11-05`: health; plan; fetch/parse; collections and exists/complete/cancel/finalize/release; select-articles; partition-articles; persist-selected-articles; feed-health-state. | Keep native planner events and remove their source-file dependency. All mounted modules receive the same producer-owned source through `PlanInputs`. |
| C2 | Summarizer: `services/summarizer/src/api/serve-http-api.ts` and `src/start-api-server.ts` | `GET /health`, `GET /api/diagnostics`, `POST /api/summarize`. | HTTP and CLI select the same local identity; retain request-private event buses, saved events and response carriers. |
| C3 | Fingerprint: `services/host-fingerprints/src/api/server.ts` and `src/api/routes/fingerprint.route.ts` | `POST /api/2026-10-20/fingerprint`, `GET /api/2026-10-20/health`. | Add native completion/failure events to actual fingerprint work, both standalone and composed. The standalone handler currently has no registry dependency and no native event envelope. |
| C4 | Host probes: `services/host-probes/src/api/server.ts`, `task-profile-route.ts` and `cache-latency-route.ts` | `GET /api/2026-10-20/sample`; `POST /api/2026-10-24/start-task-profile`, `/stop-task-profile`, `/cache/latency`. | Add safe native operation/failure events. Preserve the actual profile operation and private full-profile reporting. Standalone handlers currently use plain diagnostics. |
| C5 | Delivery: `services/feed-ingest-plan/scripts/safe-persist-http-api.ts` | Versioned health and `POST /api/2026-11-05/safe-persist-data`, through its exported app and composed delivery group. | Construct the completion event in the handler, not in its supervisor; preserve the already published completion source and payload. |
| C6 | Composition: shared `services/serve-pipeline-apis/src/create-api-app.ts` and `src/supervise-api-task.ts`; native `services/feed-ingest-plan/scripts/create-feed-api-app.ts`, `serve-feed-apis.ts`, `supervise-feed-api-task.ts`; machine `services/host-probes/src/api/create-machine-app.ts`, `serve-machine-apis.ts`, `supervise-machine-api-task.ts` | Planning group mounts planner and machine modules; machine group mounts fingerprint/probes; delivery group mounts delivery; own `GET /health` and request-error boundary. | Local lifecycle source, native request-failure event and validated relay of native module events without relabeling them. Native assembly and decoders stay in native packages; shared hosting has no reverse native dependency. Summarizer is not mounted here. |
| C7 | Additional non-HTTP producers | `.github/scripts/ai-pipeline.ts`; planner upload-inventory helper; summarizer CLI. | Migrate their registry reads too. They do not constitute additional HTTP APIs. |
| C8 | Checked non-API surfaces | Package manifests and serving/route declarations under `packages/`, `frontend/`, `backend/`, `.github/`, `services/`, `tests/`, `notebooks/`, `config/`, `.claude/` and `.vscode/`. | No additional authored TypeScript HTTP implementation was found. Frontend page loaders are static-build inputs; there is no `frontend/src/**/+server.ts`. Package libraries and test-only listeners are not new API services. |

Table D - Producer-local source declarations

| ID | Producer | Native module and declaration | URI and compatibility |
| --- | --- | --- | --- |
| D1 | Planner and upload inventory | `services/feed-ingest-plan/src/declare-event-source.ts`: `PLANNER_EVENT_SOURCE` | `/services/feed-ingest-plan`, unchanged. |
| D2 | Summarizer HTTP and CLI | `services/summarizer/src/declare-event-source.ts`: `SUMMARIZER_EVENT_SOURCE` | `/services/summarizer`, unchanged. |
| D3 | Composed listener and supervisor | `services/serve-pipeline-apis/src/declare-event-source.ts`: `PIPELINE_API_EVENT_SOURCE` | `/services/typescript-api`, unchanged. |
| D4 | Native delivery events | `services/feed-ingest-plan/src/declare-event-source.ts`: `DELIVERY_EVENT_SOURCE` | Same URI as D3, intentionally retaining the existing delivery producer namespace. Keep these owner-local protocol declarations equal with the delivery/lifecycle integration assertion; do not introduce a cross-service source lookup or circular import. |
| D5 | Fingerprint API | `services/host-fingerprints/src/declare-event-source.ts`: `HOST_FINGERPRINT_EVENT_SOURCE` | `/services/host-fingerprints`, new for native fingerprint events. |
| D6 | Host-probe API | `services/host-probes/src/declare-event-source.ts`: `HOST_PROBE_EVENT_SOURCE` | `/services/host-probes`, new for native probe events. |
| D7 | Independent phased workflow | `.github/scripts/declare-workflow-event-source.ts`: `WORKFLOW_EVENT_SOURCE` | `/workflows/ai-pipeline`, unchanged. |

Table E - Native event contracts and boundaries

| ID | Contract | Exact requirement |
| --- | --- | --- |
| E1 | Common envelope | Retain `EventSourceSchema`, `createCloudEvent`, `readCloudEvent` and the existing operation/carrier helpers. Producer constants identify fixed logical components, not deployment settings, fetch destinations or source-file locations. Validate them when constructing events. Shared contracts must not enumerate applications. |
| E2 | Fingerprint events | `services/host-fingerprints/src/api/create-fingerprint-event.ts` owns strict payloads and native creation/reading. `host_fingerprint_completed` has `{status: "written" or "disabled"}` from the actual response. `host_fingerprint_failed` has `{code: "HOST_FINGERPRINT_FAILED"}`. Use D5; never copy the host row or output paths into these events. |
| E3 | Probe completion | `services/host-probes/src/api/create-probe-event.ts` owns `host_probe_completed` with strict `{operation, outcome}`. Operations are `sample`, `start-task-profile`, `stop-task-profile`, `cache-latency`; outcome is `handled` or `disabled`. Emit only after the actual command result. `handled` does not claim that a measurement was available or that work being profiled succeeded. |
| E4 | Probe failures | The E3 module owns these strict event-type/code pairs: `host_probe_failed`/`HOST_PROBE_FAILED`, `host_probe_cleanup_failed`/`HOST_PROBE_CLEANUP_FAILED`, `host_probe_body_cleanup_failed`/`HOST_PROBE_BODY_CLEANUP_FAILED`, `task_profile_failed`/`TASK_PROFILE_FAILED`. Payload is `{code}` only; source is D6. Replace the corresponding existing plain event records, not every informational console message. |
| E5 | Composition failure | `services/serve-pipeline-apis/src/create-request-failure-event.ts` owns `typescript_api_request_failed` with strict `{code: "API_OPERATION_FAILED"}` and source D3. Emit from the real composition error boundary, not from an invented success or health request. |
| E6 | Delivery completion | Move `DeliveryCompletionDiagnosticSchema` and `createDeliveryCompletionEvent` into `services/feed-ingest-plan/scripts/safe-persist-http-diagnostic.ts`. Preserve type `safe_persist_http_completed` and data fields `server_name`, `group`, `run_id`, `attempt`, `phase`, `status`, `commit`, `files`, `context`, `severity`, `duration_ms`, `exit_code`, `code`, including current literals, nullable values and defaults. Derive request/result validators from `SafePersistHttpRequestSchema` and `MetadataDeliveryResultSchema`, not from the supervisor. Final factory input is `source`, `runNumber`, `attempt`, `status`, `commit`, `files`, `context`, plus the existing optional ancillary fields. Map `runNumber` to `data.run_id`. Native handler selects D4. |
| E7 | Delivery failure | The E6 module owns native `safe_persist_http_failed` with strict `{code}`, reusing `PlannerErrorResponseSchema.shape.code`. Use the actual receiving operation and D4. Keep detailed sanitized failure evidence in its existing response/evidence surfaces, not in the new mirrored payload. |
| E8 | Operation ownership | Ordinary new request events derive a child from a valid incoming carrier, otherwise a root. Enabled profile start uses the operation returned by the real profiler; successful stop, including repeated stop, uses the retained profile operation despite conflicting stop headers. Background profile failure uses its allocated session operation. Disabled commands may have a receiving-request diagnostic context but create no profile, handle or measurement. Shutdown errors use the owned service lifetime context. Existing planner/summarizer relationships do not change. |
| E9 | Data minimization | New host/composition events contain only their declared safe payloads and standard envelope metadata. No arbitrary details, bodies, prompts, model output, headers, raw exception strings, paths, PIDs or measurements. Parent/input relationships remain in the native operation/profile; the generic carrier is not a second serialized copy of the complete operation. |
| E10 | Relay | Native feed and machine decoders dispatch known event types to their producer-owned validators and return typed results to shared hosting. Shared hosting validates its own request-failure subtype without importing native packages. Mirror an accepted native event unchanged, including source, occurrence ID, UTC time, carrier and data. Delivery carrier must agree with `writeTraceContext(data.context)`. Retain terminal article forwarding and ordinary planner failure projection. Unknown/malformed events produce the existing safe `CHILD_DIAGNOSTIC_INVALID` warning, never blanket passthrough. |
| E11 | Private transport | Keep the validated `{event: "task_profile", profile}` callback/child transport and `reported_profiles` evidence exactly as they are, excluded from normal output/mirrors. Keep private readiness packets and CLI result stdout. Native events do not turn these data/control protocols into public diagnostics. |
| E12 | Versioning | New diagnostic schemas carry a `2026-11-05` metadata version, one-line changelog and current-only read rule. The byte-equivalent delivery schema move does not change its version or saved data. Existing shared, planner, summarizer, workflow and server-evidence versions remain unchanged. |

## 1. Status Reckoner

Table F - PR sequence

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Remove the registry and localize existing producer identities | - | A | DONE | urban-goggles | - | - |
| F2 | 2 | Move native diagnostic contracts to producers and expand relay readers | 1 | B | DONE | urban-goggles | - | - |
| F3 | 3 | Emit native events across every API and retire legacy translation | 2 | C | PENDING | - | - | - |

## 2. Row #1 - Remove the registry and localize existing producer identities

- **Scope:** Remove the runtime registry in the same PR as all existing callers, obsolete registry tests, named-input copies and current source-ownership documentation.
- **Files touched:**
  - `config/typescript-event-sources.json` - delete.
  - `packages/common-contracts/src/load-event-sources.ts` - delete.
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/package.json`
  - `packages/common-contracts/test/metadata-flow.test.ts`
  - `packages/common-contracts/test/rejection.test.ts`
  - `packages/common-contracts/test/article-failure-diagnostic.test.ts`
  - `services/feed-ingest-plan/src/declare-event-source.ts` - add D1.
  - `services/feed-ingest-plan/src/load-plan-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-upload-inventory.ts`
  - `services/feed-ingest-plan/test/failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/harvest.test.ts`
  - `services/feed-ingest-plan/test/health-fields.test.ts`
  - `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/planner-diagnostics.test.ts`
  - `services/feed-ingest-plan/test/report-native-evidence.test.ts`
  - `services/feed-ingest-plan/test/safe-persist-http.test.ts`
  - `services/feed-ingest-plan/test/planner-process-recordings.ts`
  - `services/feed-ingest-plan/test/publication-recordings.ts`
  - `services/summarizer/src/declare-event-source.ts` - add.
  - `services/summarizer/src/start-api-server.ts`
  - `services/summarizer/src/execute-cli-pipeline.ts`
  - `services/summarizer/test/pipeline-events.test.ts`
  - `services/summarizer/test/model-runtime.test.ts`
  - `services/serve-pipeline-apis/src/declare-event-source.ts` - add.
  - `services/serve-pipeline-apis/src/supervise-api-task.ts`
  - `services/serve-pipeline-apis/test/supervise-http-child.test.ts`
  - `services/host-probes/test/machine-api-recordings.ts`
  - `.github/scripts/declare-workflow-event-source.ts` - add.
  - `.github/scripts/ai-pipeline.ts`
  - `.github/scripts/test/workflow-handoff.test.ts`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py`
  - `.github/workflows/ai-pipeline-tests.yml`
  - `.github/workflows/ci.yml`
  - `services/hhem-evaluator/tests/test_pipeline_preparation.py`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `docs/architecture/contracts/identity.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/reference/summarizer-api.md`
  - `docs/reference/serve-pipeline-apis.md`
  - `docs/reference/workflow-pipeline-events.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261103-standardize-typescript-metadata-plan.md`
  - `TODO/20261105-remove-typescript-event-registry-plan.md`
- **Acceptance gates - local:**
  - Inspect `npm --prefix frontend run test:changed -- --list`; use the independent-package bindings in `docs/how-to/run-the-gates.md`. Do not run its Python-backed groups as a planner-development prerequisite.
  - Run declared `check` commands for common-contracts, planner, summarizer and composition. Combine affected test selectors within each package invocation.
  - Common-contracts: `metadata-flow.test.ts`, `rejection.test.ts`, `article-failure-diagnostic.test.ts` and existing `article-identity-compatibility.test.ts`. Keep generic URI rejection in memory.
  - Planner: the affected test files above, plus `plan-entry-points.test.ts`, `feed-ingest-plan-supervisor.test.ts` and `feed-ingest-plan-finalization.test.ts`. Their generated roots must omit the deleted config file.
  - Summarizer: `pipeline-events.test.ts` and `model-runtime.test.ts`. Shared hosting: `server-events.test.ts` and `supervise-http-child.test.ts`. Native feed assembly: `serve-feed-apis.test.ts`, `relay-feed-api-events.test.ts` and `retain-api-profiles.test.ts`. Machine assembly: `record-machine-api-events.test.ts` and `serve-machine-apis.test.ts`.
  - Run `bun test .github/scripts/test/workflow-handoff.test.ts` and the existing workflow-handoff type check declared in its workflow.
  - Run `node --test frontend/scripts/tests/test-scope.test.mjs`. Replace its deleted-loader example with the existing shared envelope-schema path; do not weaken selector coverage.
  - From `services/hhem-evaluator`, run `uv run --frozen pytest tests/test_pipeline_preparation.py`; run its existing lint/type commands on the changed staging/test inputs. This is the existing Python staging consumer, not a new planner test path.
  - Search authored runtime code, manifests, tests and named input lists for the retired registry, loader, subpath and `EventSources` type. No runnable dependency may remain; delete superseded instructions in the named older plans rather than leaving contradictory requirements.
  - Record selected inputs, check results and test counts for reuse; restore dependencies only after a missing-dependency failure or a manifest dependency change.
- **Acceptance gates - CI:** Existing full native suites, workflow-handoff gate, Python preparation coverage and merge-candidate CI pass. No live model/evaluator or data-writing workflow dispatch is a gate.
- **Oracle:** Real planner, summarizer, workflow and supervised API cases operate with named inputs that contain no registry file and emit the unchanged expected producer identities; restoring a registry read makes those cases fail. This does not establish native emission by C3-C5, which ships in row 3.

Table G - Row 1 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| G1 | Apply D1-D3 and D7 at production entrypoints. These fixed logical identities are named protocol literals under the existing contract, not tunable deployment behavior. Keep generic factories' validated source injection and `PlanInputs.event_source` as `string`. | Fowler; E1. |
| G2 | Remove the `explicit source loading changes producer identity and refuses missing or invalid settings` case and its temporary-file setup. Preserve its useful URI-validity rule through direct in-memory event/schema cases. Rewire metadata/replay/rejection tests instead of deleting their behavioral assertions. Common tests use their own literal fixture source, not imports from application packages. | Fowler; E1. |
| G3 | Delete the shared file, implementation, barrel export and package subpath atomically with every remaining caller and config-copy dependency. Replace the workflow config trigger with its new producer module trigger. Do not create a replacement map, resolver, environment value or missing-file fallback. | Fowler; A1. |
| G4 | Replace the loader paragraph in the existing identity page and add its ownership reason to that page's Design rationale. Update the linked producer references in place. These pages still answer their existing questions, so no additional page or unrelated split is needed. Do not yet declare the final all-API emission matrix. | Fowler; documentation ownership. |

Table H - Row 1 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Move or split the registry, or replace it with environment-selected sources | Retains runtime identity configuration instead of removing the dependency. | Additional loaders, deployment settings and failure cases, without satisfying A1. | Fowler. |
| H2 | Remove every test that imports the old loader | Discards valid replay, context, sanitization and real-entrypoint coverage. | The missing regressions would have to be rebuilt to verify compatibility. | Fowler. |

## 3. Row #2 - Move native diagnostic contracts to producers and expand relay readers

- **Scope:** Put native diagnostic contracts and factories in their producing modules and teach the supervisor to validate and retain their events before switching existing plain writers.
- **Files touched:**
  - `services/feed-ingest-plan/src/declare-event-source.ts` - add D4.
  - `services/feed-ingest-plan/scripts/safe-persist-http-diagnostic.ts`
  - `services/feed-ingest-plan/scripts/delivery-completion-diagnostic.ts` - delete after consolidation.
  - `services/feed-ingest-plan/scripts/read-feed-api-diagnostic.ts`
  - `services/feed-ingest-plan/scripts/read-article-failure-diagnostics.ts`
  - `services/feed-ingest-plan/test/safe-persist-http.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/relay-feed-api-events.test.ts`
  - `services/feed-ingest-plan/test/report-native-evidence.test.ts`
  - `services/feed-ingest-plan/test/write-feed-api-events.ts`
  - `services/host-fingerprints/src/declare-event-source.ts` - add.
  - `services/host-fingerprints/src/api/create-fingerprint-event.ts` - add.
  - `services/host-fingerprints/package.json`
  - `services/host-fingerprints/test/native-events.test.ts` - add.
  - `services/host-probes/src/declare-event-source.ts` - add.
  - `services/host-probes/src/api/create-probe-event.ts` - add.
  - `services/host-probes/src/api/read-machine-api-diagnostic.ts`
  - `services/host-probes/package.json`
  - `services/host-probes/test/native-events.test.ts` - add.
  - `services/host-probes/test/record-machine-api-events.test.ts`
  - `services/host-probes/test/write-machine-api-events.ts`
  - `services/serve-pipeline-apis/src/create-request-failure-event.ts` - add.
  - `services/serve-pipeline-apis/src/write-server-event.ts`
  - `services/serve-pipeline-apis/src/server-evidence.ts` - name the unchanged lifecycle type for report routing.
  - `services/serve-pipeline-apis/test/server-events.test.ts`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/reference/serve-pipeline-apis.md`
  - `TODO/20261105-preserve-typescript-diagnostics-plan.md`
  - `TODO/20261105-remove-typescript-event-registry-plan.md`
- **Acceptance gates - local:**
  - Inspect the shared selector, then run declared checks for planner, fingerprint, probes and composition.
  - Run the new `native-events.test.ts` files, shared `server-events.test.ts`, machine `record-machine-api-events.test.ts`, and planner `relay-feed-api-events.test.ts`, `report-native-evidence.test.ts`, `safe-persist-http.test.ts` plus `feed-ingest-plan-finalization.test.ts`.
  - Cover strict type/payload validation, malformed source/carrier rejection, new occurrence creation and unchanged replay with minimal in-memory values.
  - Use the existing real stderr/mirror helpers in `services/feed-ingest-plan/test/write-feed-api-events.ts` and `services/host-probes/test/write-machine-api-events.ts` for native events, and the shared `test/write-server-events.ts` for the host's own request-failure events. Accepted events survive unchanged; invalid/unknown types or unsafe extra fields yield safe warnings. Shared tests do not import native packages.
  - Keep existing article forwarding, log-unavailable behavior, private-profile exclusion and completion context/default assertions green.
  - A valid native delivery error code cannot impersonate a server lifecycle rejection marker or create an article-evidence gap.
  - Search the authored tree for the removed delivery schema module and update every import/link found, including the named older plan. No compatibility re-export at the old location.
- **Acceptance gates - CI:** Existing full native suites and merge-candidate CI pass; locked installs remain valid without dependency or workspace changes.
- **Oracle:** Events constructed by the owner factories pass through the real relay subprocess and mirror with identical source, ID, time, carrier and data, while malformed inputs cannot cross that boundary. This proves native contracts/readers, not that every HTTP handler emits them yet.

Table I - Row 2 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| I1 | Consolidate the producer's delivery completion module into its native diagnostic module in a behavior-preserving structural commit before reader expansion. Use E6's native field validators directly; the producer must not import `ServerEventDataSchema` or any other supervisor module for this contract. Update every native reader and test import. | Fowler; producer ownership. |
| I2 | Implement E2-E7 as real owner factories/readers, not placeholders. Export host diagnostic contracts through `./diagnostic` subpaths in the existing host package manifests; reuse the existing planner `./delivery-diagnostic` subpath. No new dependencies or shared application registry. | Fowler; E1-E7. |
| I3 | Expand the finite relay by event type under E10. Keep the existing plain completion translator only while the current handler still emits it; adapt that translator to E6's final factory input. Row 3 removes it with the writer cutover. Private profile transport is not this legacy branch. | Fowler; reader-before-writer ordering. |
| I4 | Publish current contract ownership and reader behavior in the named canonical pages. Do not claim host APIs already emit the new events before row 3. Record schema metadata as E12 requires; do not bump unchanged saved families. | Fowler; A5 and E12. |

Table J - Row 2 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Put application sources and every API payload in common-contracts | Replaces the JSON registry with a code registry and couples unrelated producers to shared application knowledge. | Shared releases and dependency-driven edits for producer-local event changes. | Fowler. |
| J2 | Accept and mirror every syntactically valid CloudEvent | Envelope validity does not prove that the payload is safe for the existing log boundary. | A separately designed sanitizer/consent boundary and new privacy checks; not equivalent to this scoped refactor. | Fowler. |

## 4. Row #3 - Emit native events across every API and retire legacy translation

- **Scope:** Wire real native events into all API families, remove the final plain-delivery transport and its obsolete tests, and publish the verified all-API standard.
- **Files touched:**
  - `services/host-fingerprints/src/index.ts`
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-fingerprints/src/api/routes/fingerprint.route.ts`
  - `services/host-fingerprints/test/native-events.test.ts`
  - `services/host-fingerprints/test/fingerprint-persistence.test.ts`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/host-probes/src/api/task-profile-route.ts`
  - `services/host-probes/src/api/task-profile-manager.ts`
  - `services/host-probes/src/api/cache-latency-route.ts`
  - `services/host-probes/src/api/command-body.ts`
  - `services/host-probes/src/api/create-machine-app.ts`
  - `services/host-probes/test/native-events.test.ts`
  - `services/host-probes/test/probe.test.ts`
  - `services/host-probes/test/serve-machine-apis.test.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-api.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-diagnostic.ts`
  - `services/feed-ingest-plan/scripts/create-feed-api-app.ts`
  - `services/feed-ingest-plan/test/safe-persist-http.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-finalization.test.ts`
  - `services/feed-ingest-plan/test/serve-feed-apis.test.ts`
  - `services/feed-ingest-plan/test/relay-feed-api-events.test.ts`
  - `services/feed-ingest-plan/test/retain-api-profiles.test.ts`
  - `services/serve-pipeline-apis/src/create-api-app.ts`
  - `services/serve-pipeline-apis/src/write-server-event.ts`
  - `services/serve-pipeline-apis/test/server-events.test.ts`
  - `docs/architecture/contracts/identity.md`
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/reference/serve-pipeline-apis.md`
  - `docs/reference/host-probe-api.md`
  - `docs/reference/host-metrics.md`
  - `docs/reference/summarizer-api.md`
  - `docs/reference/workflow-pipeline-events.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `TODO/20261105-preserve-typescript-diagnostics-plan.md`
  - `TODO/20261105-remove-typescript-event-registry-plan.md`
- **Acceptance gates - local:**
  - Inspect the shared selector; run declared checks for fingerprint, probes, planner and composition.
  - Extend existing real handler cases, not a separate fake implementation: fingerprint write/disabled/failure; probe sample/start/stop/cache and safe failures; direct delivery and actual finalization; real composed listener and its error boundary.
  - Run fingerprint `native-events.test.ts` and `fingerprint-persistence.test.ts`; probes `native-events.test.ts`, `probe.test.ts` and `serve-machine-apis.test.ts`; planner `safe-persist-http.test.ts`, `feed-ingest-plan-finalization.test.ts`, `serve-feed-apis.test.ts`, `relay-feed-api-events.test.ts` and `retain-api-profiles.test.ts`; shared hosting `server-events.test.ts`.
  - Use existing recorded host/process inputs and actual ephemeral outputs. Capture through an explicit event-output boundary or real stderr; do not patch business logic, create new disk recordings or scan directories.
  - Verify each Table C API through an actual emitting handler/process case. Reuse unchanged row-1 planner, summarizer and workflow records only when their tested inputs remain unchanged; otherwise rerun the affected selection.
  - Verify enabled profile start/stop carriers against their real operation, including conflicting stop headers and repeated stop. Disabled work must not create handles or measurements. A repeated event occurrence may be new while its retained profile operation stays the same.
  - Verify native delivery events already exist before the supervisor sees them; direct handler and supervised finalization retain E6's completion facts and original context. The relay must not manufacture a replacement occurrence.
  - Remove the old plain completion translator, `SafePersistHttpDiagnosticSchema`/`SafePersistHttpDiagnostic` transport declarations and their configuration/translation-only test cases. Retain native status, field-validation, sanitization, receipt, real-Git and cleanup assertions against the current event contract.
  - Confirm valid new host events do not create spurious invalid-diagnostic/evidence-gap warnings. Keep the existing terminal-article and private-profile report cases green.
  - Check authored code/tests/config-copy lists for retired registry and legacy translation dependencies. Verify documentation links and the completed support matrix against the named real emission cases, not constant existence.
- **Acceptance gates - CI:** Full affected native suites and required merge-candidate CI pass. Existing Linux-only native instrument cases remain CI responsibilities; do not substitute invented measurements locally or dispatch a data-writing workflow. No browser gate is added because published-site code/data are unchanged.
- **Oracle:** For every HTTP API family in Table C, a real operation/error path emits a producer-owned CloudEvent with the declared source and actual operation; when composed, that same event survives strict relay unchanged while its native HTTP response remains valid. Removing any family's emission must fail its corresponding functional case. This does not prove live source/model quality or runtime performance.

Table K - Row 3 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| K1 | Apply E2-E9 at the API boundary, with additive typed event-output options where capture is needed. Keep persistence options and full-profile `report` callbacks semantically separate. Each operation has one native terminal outcome; standalone error adapters must not emit a duplicate of an already reported domain failure. | Fowler. |
| K2 | Thread request/session context through probe command-body, route and manager failure paths rather than creating a mutable current context. Use the existing native results to choose E3 outcomes. Do not manufacture measurement success from a handled or disabled command. | Fowler; E8-E11. |
| K3 | Switch delivery and composition to their owner factories only after row 2 is available. Delete the plain-delivery branch and obsolete transport schema/tests in the same PR; retain no permanent dual reader or legacy wrapper. Preserve private profile and readiness transport. | Fowler; E6, E10-E11. |
| K4 | Define the standard once in `docs/architecture/contracts/identity.md`, including the completed API/source/support matrix and its protocol-literal rationale. Link the API-specific pages to it; document actual event types and private transport exceptions locally. Declare all Table C HTTP APIs supported only with the functional evidence required by this row. | Fowler; documentation ownership. |
| K5 | Update the existing API, metrics and gate sections in place. They remain answers to their current questions; a new cross-cutting narrative page or unrelated documentation split would duplicate the identity page. Do not document user approvals or personal attributions. | Documentation contract. |

Table L - Row 3 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Add constants for host APIs without emitting native events | Leaves the requested all-API capability unimplemented. | A later implementation and another documentation correction; cannot satisfy this row's oracle. | Fowler. |
| L2 | Convert every HTTP response, private profile or readiness packet into a public event | Changes unrelated client/control protocols and exposes data beyond the diagnostic contract. | Coordinated client migrations, data-minimization design and new compatibility work before any such change. | Fowler. |
| L3 | Keep supervisor-created delivery events and the old translation tests | Delivery still depends on another component to construct its event identity and remains different when used directly. | Permanent extra transport/translation logic and continued standalone/composed divergence. | Fowler. |
