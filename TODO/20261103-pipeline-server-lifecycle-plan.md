# Pipeline server lifecycle and reporting plan

**Last Updated**: 2026-11-03
**Level**: 5 - server/workflow integration; execute ready rows in dependency order.

## 0. Operating contract

Table A - Intent and scope

| Id | Field | Direction |
| --- | --- | --- |
| A1 | Intent | Two workflows use simple local API servers, useful error logs, real readiness and clean shutdown. Summary evaluation generates text with one selected summarization model per run, then evaluates that generated summary. |
| A2 | Workflows | Update `feed-ingest-plan-test.yml`. Create `summary-eval-tests.yml` from the existing HHEM workflow and replace that old workflow when the new one lands. |
| A3 | TypeScript API server | One Bun server serves several API modules: machine fingerprints, machine measurements, fetch, parse and the existing planning/delivery operations. Each workflow task enables the modules it needs. Do not start a separate server for every API. |
| A4 | Python API server | One FastAPI application serves HHEM and llama routes. Model requests enter FastAPI and are forwarded with HTTPX to the native llama-server process on a private loopback port. |
| A5 | Native llama process | The generation task owns the native executable and Python API server. The forwarding route does not load models, choose weights or implement a general proxy. |
| A6 | Machine fingerprints | Collection and measurement stay in TypeScript. Python may call their HTTP APIs; TypeScript neither installs nor calls Python to collect machine facts. |
| A7 | Dependencies | Reuse the existing frozen Python model environment and pinned Bun dependencies. |
| A8 | UniEval | Implement through the separate [UniEval API plan](20261103-unieval-api-plan.md), extending the same Python server and summary workflow. Add no placeholder route or fake score here. |
| A9 | Construction | Explicit routers, existing process handles, standard logging and small visible workflow tasks. Test the real APIs live; stop/start services between phases rather than add capacity studies or a service framework. |
| A10 | Breaking changes | Cut over changed producers and consumers together. Remove replaced implementations and aliases; add no backward-compatible paths, dual readers or fallback launchers. |
| A11 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 1 because the rows change shared server, workflow and integration files. |
| A12 | ESCALATE | Pause for a Level-5 change, a changed article-text destination, a committed ledger-format change, an unplanned model-selection policy/dependency change or expansion beyond these workflows. Selecting a valid declared model through D is normal run input, not a new design decision. |
| A13 | Protected files | Do not modify `CLAUDE.md` or `AGENTS.md`. Keep approval narratives and personal attributions out of code and documentation. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan; parallel N = 1 because the rows share integration files; honor the ESCALATE triggers in section 0.

Table B - What this change does not include

| Id | Exclusion | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Production digest workflow and shared production llama launcher changes | Those callers retain their existing setup and filenames. | A separate production migration; do not make this experiment depend on it. |
| B2 | Summarizer and older phased-workflow cutovers | Those existing workflows are not modernized by this change. | A separately named migration. The old phased workflow is inspiration, not another target. |
| B3 | UniEval model integration | This plan cannot claim a real UniEval score or simultaneous HHEM/UniEval execution. | The receiving plan named in A8 owns both outcomes. |
| B4 | Dynamic plugin loading | Adding an API requires one explicit router registration. | A real independently installed-extension requirement and its trust boundary. |
| B5 | Custom log quotas, rotation and retention policy | Files can grow for the duration of a run; the runner's storage remains finite. | An observed storage problem. Use standard logging handlers if rotation becomes necessary. |
| B6 | Capacity studies, speed thresholds and synthetic model evaluations | No claimed throughput or co-resident model capacity. | A concrete later decision that needs that measurement. |

### 0.1 Server configuration

Table C - Ports and authority

| Id | Server | Default | Single source | Client behavior |
| --- | --- | --- | --- | --- |
| C1 | Hono on Bun | `127.0.0.1:8787` | `config/hono-server.json` | Both workflows use this address for their selected TypeScript APIs. |
| C2 | FastAPI on Uvicorn | `127.0.0.1:3010` | `config/fastapi-server.json` | Summary tasks call generation and evaluation through this address. |
| C3 | Native llama-server | `http://127.0.0.1:8080` | Existing selected configuration's `model_server.base_url` | The forwarding route uses this private address; the workflow caller does not bypass FastAPI. |

- Keep native model destinations in committed configuration; do not select them through environment variables or HTTP input.
- Move composed listener settings to C1/C2; keep extraction, scoring and measurement settings in their existing files. Server configuration does not select summarization weights.
- Do not launch separate fingerprint, probe or summarizer servers in these workflows.
- Use explicit enabled router groups, not module names imported from request data. Reject port conflicts; do not adopt or kill an unrelated process.
- Refresh the named TypeScript call sites after the planner and machine-measurement metadata cutovers. Reuse `packages/common-contracts` event/context helpers and the canonical identity contract.

### 0.2 Model input and generated-summary handoff

Table D - Workflow form and model selection

| Id | Item | Contract |
| --- | --- | --- |
| D1 | Model textbox | String input `models_file`, labelled as a model JSON path relative to `config/`. Prefill it with `models/ornith-1.5-9b-q5km.json`, the current `config/idhazh.json.models_file` value. The workflow default must remain aligned with that pointer. |
| D2 | Path handling | Reuse the existing model-file validator and declaration loader. Accept its `models/<name>.json` convention, not a repository-root path, arbitrary filesystem path or remote repository ID. Blank uses the committed pointer; an invalid nonblank value fails before model startup. |
| D3 | Selected data | The declaration supplies actual weight files, immutable revisions, digests, model identity, server settings and request settings. Do not change only the request's model name, add a model catalog or discover repository files automatically. |
| D4 | Run isolation | Exactly one summarization declaration per workflow run. Select another declaration in a separate dispatch; no model matrix, model loop or shared-default edit. |
| D5 | Source input | Required `source_text` remains data read from the bounded platform event. Remove the old workflow's `summary_text` input: generation now supplies the summary. |
| D6 | Generation instruction | Store the summarization instruction in `config/summary-eval-tests.json`, shared across model runs. Use the selected declaration's request/template settings and existing final-answer extraction; exclude reasoning from the evaluated answer. |
| D7 | Evaluator selection | `models_file` changes the summarizer only. HHEM and later UniEval keep their separately declared evaluator models. |

Table E - Same-run handoff

| Id | Item | Contract |
| --- | --- | --- |
| E1 | Generation receipt | Declare one native same-run result containing run/attempt identity, selected declaration and loaded model identity, a hash of the exact source sent for generation, the validated final `summary_text`, status and errors. Write it atomically under the current run directory. |
| E2 | Evaluator inputs | Re-read the same bounded source event and the generation receipt. Verify run/attempt, selected model and source identity, then send the exact source and generated summary to HHEM and later UniEval. Do not regenerate, substitute text or accept a receipt from another run. |
| E3 | Generation failure | Failed, missing, empty or incomplete generation does not trigger evaluation. Report the generation error and evaluators as not run; do not invent zero scores or fall back to a supplied summary. |
| E4 | Partial evaluation | An evaluator failure preserves the generated summary and the other evaluator's completed result. Neither scores nor model identity can come from an earlier run. |
| E5 | Reports and files | Report the selected model/declaration, generated summary, actual evaluator results and server outcomes. Escape source/summary disclosures as literal text. Generation data belongs in its declared result/report, never diagnostic logs; evaluator result JSON stays body-free. |

### 0.3 Workflow tasks

Table F - Execution order

| Id | Workflow task | Required behavior |
| --- | --- | --- |
| F1 | Feed: collect and select | Start the Bun API with planning and machine routes, check its real readiness, perform existing feed work and stop it in the task's cleanup path. Preserve normal ledger delivery behavior. |
| F2 | Feed: finalization | Use the same Bun application and existing delivery handlers when the finalization task needs HTTP delivery. A task may restart the application with only its required modules; it does not get a separate per-API server implementation. |
| F3 | Summary: prepare | Install frozen tool dependencies, validate D's selection and inputs, then restore/acquire the declared native assets. No digest memory tuning or job graph. |
| F4 | Summary: generate | Start native llama and FastAPI's forwarding route, make a real generation request through FastAPI, write E1 and stop both processes. Use the Bun machine APIs for measurements. |
| F5 | Summary: evaluate | After successful generation, start FastAPI with HHEM enabled and score E2's generated pair. Preserve measurements, partial results and worker shutdown. The separate UniEval plan extends this phase. |
| F6 | Summary: produce report | Read E's results and render the actual selected model, generated summary, scores, failures and lifecycle facts. Never turn a failed generation/evaluation into a successful report outcome. |
| F7 | Summary: retain output | Upload results/report on success or failure when available. Upload server log files on error/cancellation. Use default artifact retention. |
| F8 | Either workflow: failure | Detect a server exit during readiness without waiting out the full timeout. Run the task's cleanup and leave a real failed outcome. A later phase may start fresh services; it must not relabel an earlier failure as success. |

- Keep preparation, generation, evaluation, report and artifact upload visible as workflow steps. Put process handling in small scripts rather than copied shell loops.
- One phase script owns its children from start through request to final cleanup in the same workflow step. This keeps live stderr available without a detached log follower or a cross-step process registry.
- Stop the summarization model before loading evaluators. Server restarts do not regenerate or change E1's summary.
- Retain finite startup and shutdown waits. Reuse current service values where applicable; log-file volume is not a request, model or process deadline.
- The new manual workflow must first exist on the default branch before it can be dispatched by name. Do not label registration or offline checks as a successful live model run.

### 0.4 Logging and reporting

Table G - Small logging contract

| Id | Property | Behavior |
| --- | --- | --- |
| G1 | Filename | `{server_name}_{yyyy_mm_dd}_{run_id}_{attempt}.log`; UTC run-start day, platform run identifier and platform attempt. Local runs use the existing invocation identity and attempt one. |
| G2 | Server names | Fixed roles `hono-server`, `fastapi-server` and `llama-server`; never source text, a URL or model output. Restarting a role within a run appends with a new start event. |
| G3 | Live and file output | Write the same accepted CloudEvents JSONL records to stderr and the role's file as they occur. Keep control packets on their existing private channel. |
| G4 | Useful detail | Brief startup, ready and stop events plus warnings/errors. Disable access-log noise, per-token output and repeated success dumps. Request bodies, prompts, model output and secrets are not log fields. |
| G5 | Envelope | CloudEvents `specversion`, `id`, `source`, `type`, `time`, `datacontenttype` and typed `data`. Put severity, safe error details and measured lifecycle facts in `data`; use the settled context helpers where context is present. |
| G6 | Python implementation | Standard `logging` with stderr/file handlers and a JSON formatter. No new logging library or rotation setup. |
| G7 | Native diagnostics | Use the selected native server's quiet logging settings and the existing safe diagnostic projection. Forward diagnostic text as JSON data, not raw workflow commands. Keep prompt/body logging disabled; do not invent a separate raw-body log channel. |
| G8 | Capture failure | If the file cannot be opened or written, emit an explicit safe stderr warning and mark the log unavailable. Continue the API work; do not manufacture a log or make the score fail because its diagnostic mirror failed. |
| G9 | Volume | Stream records rather than collecting the whole file in memory. Add no byte quota, rotation worker, size polling or log-cap-triggered server shutdown. |
| G10 | Report | A small server table shows ready/failed, observed startup duration, shutdown result and log filename. Missing observations remain unavailable. API results and actual exits establish task success, not finding a terminal log line. |
| G11 | Retention | Log files stay under the current disposable run directory. Upload them for failed/cancelled runs when finalization can run; use platform defaults and never add them to Git or the site. |
| G12 | Failure truth | Keep the original API/process error and any cleanup failure separately. Failure of an optional diagnostic mirror is a diagnostic warning; an owned process that will not stop is an operational failure. Hard runner termination cannot promise a final upload. |

### 0.5 Contract ownership

Table H - Existing boundaries and new same-run data

| Id | Data or behavior | Authority |
| --- | --- | --- |
| H1 | TypeScript operation/event metadata | Existing `packages/common-contracts` schemas and helpers; no competing envelope or identity allocator. |
| H2 | Machine data and handlers | Existing `services/host-fingerprints` and `services/host-probes`; expose their native handlers on C1 and preserve their existing read-side parity check. |
| H3 | HHEM requests/results and owned scoring | Existing `services/hhem-evaluator/src/hhem_evaluator/contracts/` and controller. |
| H4 | llama forwarding request/result | Native models in the same Python contract package; only the required generation operation, not a general proxy protocol. |
| H5 | Generation handoff and combined workflow result | `.github/scripts/summary-eval-tests/summary_eval_pipeline/contracts.py`; declare E before logic, version changed models and update readers with writers. These are same-run artifacts, not committed ledgers or restart stores. |
| H6 | Model selection | Existing model-file validation and configuration loader. The form default is D1; server configuration does not duplicate it. |
| H7 | Native model assets and arguments | Reuse the declaration/argument readers in `backend/idhazh/llm/server.py` and `backend/utilities/model_runtime.py`; do not change production startup behavior. |

## 1. Status Reckoner

Table I - PR sequence

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | 1 | Serve TypeScript APIs together in the feed workflow | - | A | PENDING | - | - | - |
| I2 | 2 | Serve HHEM and llama through one FastAPI application | - | B | IN-REVIEW | fuzzy-giggle (shared-fastapi-server) | #1906 | Shared FastAPI server |
| I3 | 3 | Deliver the live summary-eval-tests workflow | 1, 2 | C | PENDING | - | - | - |

## 2. Row #1 - Serve TypeScript APIs together in the feed workflow

- **Scope:** Ship one Bun application for the existing TypeScript APIs and use it in the feed workflow, with simple structured logs and clean task lifetimes.
- **Correction level:** 5 for the application boundary; retain the settled metadata contracts.
- **External prerequisites:** The metadata rows titled "Convert the planner and every planner caller" and "Convert host profiling without breaking Python control" must merge before this row starts. Native HTTP commands/results remain JSON; CloudEvents describe logs, not replacement request envelopes.
- **Files touched:**
  - `services/typescript-api/package.json` - new composition entry point, not another generic runtime package.
  - `services/typescript-api/bun.lock` - generated by Bun.
  - `services/typescript-api/tsconfig.json`
  - `services/typescript-api/src/index.ts`
  - `services/typescript-api/src/create-api-app.ts`
  - `services/typescript-api/src/load-settings.ts`
  - `services/typescript-api/src/write-server-event.ts`
  - `services/typescript-api/test/api-composition.test.ts`
  - `services/feed-ingest-plan/package.json`
  - `services/feed-ingest-plan/bun.lock`
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/config/service-settings.ts`
  - `services/feed-ingest-plan/scripts/http-child-lifetime.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-http-client.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-workflow-inputs.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-server.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-server.ts`
  - `services/feed-ingest-plan/scripts/run-feed-ingest-plan.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-report.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-artifacts.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-report.test.ts`
  - `services/host-fingerprints/src/index.ts`
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-probes/package.json`
  - `services/host-probes/src/index.ts`
  - `services/host-probes/src/api/server.ts`
  - `config/hono-server.json`
  - `config/typescript-event-sources.json` - use the upstream metadata version.
  - `config/feed-ingest-plan-service.json`
  - `.github/workflows/feed-ingest-plan-test.yml`
  - `.github/workflows/ci.yml`
  - `frontend/scripts/test-scope.ts`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `docs/how-to/run-feed-ingest-plan-test.md`
  - `docs/reference/host-probe-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`

Table J - Detailed tasks

| Id | Task | Completion condition |
| --- | --- | --- |
| J1 | Refresh the planner and machine API call sites after the metadata cutovers. | Existing operation context, startup nonce and business run identity keep their separate meanings. No duplicate event/context implementation is added. |
| J2 | Declare the shared app's configuration and same-run server evidence. | C1 and G are represented before their readers/writers. Domain settings remain in their current modules; no second port registry or diagnostic quota is introduced. |
| J3 | Compose existing route handlers on one Bun server. | Fingerprint, sampling/profile, fetch, parse and planning calls use the same configured address. Each module still owns its validation and operation code. No independent machine-server process is started. |
| J4 | Provide explicit route groups for workflow tasks. | Planning tasks register planning plus machine routes; summary tasks can register machine routes only; delivery tasks use the existing private delivery handler. Request input cannot choose imports or destinations. |
| J5 | Wire the merged child/request lifetime to this application. | Preserve exact-child readiness, early-exit detection and cancellation cleanup. Keep required health in the single native result and request cleanup before return; do not restore separate summary/release calls, retired batches or a replacement continuation handle. |
| J6 | Wire real machine API calls into feed preparation. | Do not collect a fingerprint before its API is started and then claim that the HTTP route was used. Keep normal writer identity, output location and delivery behavior. |
| J7 | Implement G using the shared CloudEvents helpers. | Brief records reach stderr and the named file as emitted. A file-write failure produces a warning and does not stop feed work. Private control packets are not printed as diagnostics. |
| J8 | Add server outcome reporting and failure log uploads. | Failed startup can still produce a report/log artifact. Report generation and article-metadata delivery remain separate; default artifact retention is unchanged. |
| J9 | Update installation, sparse checkout and selected checks. | Frozen installation includes the real app and its module dependencies. Shared app changes select affected module tests; no new browser or performance suite is introduced. |
| J10 | Remove only replaced code and update living docs. | The feed workflow has short calls to actual task programs, not a copied server loop. Unrelated standalone utilities and other workflows are not migrated. |

- **Acceptance gates - local:** Inspect `npm run test:changed -- --list` from `frontend/`; run selected TypeScript checks and focused composition/lifetime/report tests. Use generated local inputs and real handlers/processes, not fake successful API implementations.
- **Acceptance gates - CI:** Applicable existing service/workflow suites on the merge candidate.
- **Live proof:** Run the actual feed workflow after implementation, keep its normal output and inspect same-port machine/fetch/parse calls, failure diagnostics and shutdown. A live data-writing run is not an endlessly repeated test fixture.
- **Oracle:** The composed server performs actual fingerprint and recorded-input fetch/parse operations through the same port, then closes its owned work. This proves route composition and lifetime behavior, not external-feed reliability or model performance.

Table K - Decisions

| Id | Decision | Basis |
| --- | --- | --- |
| K1 | Compose working handlers instead of starting one server per module. | A3, C1 and H2. |
| K2 | Add one application entry point, not a package for every lifecycle primitive. | A9. |
| K3 | Keep diagnostic file failure separate from useful API work. | G8 and G12. |

Table L - Alternatives not selected

| Id | Alternative | Why not selected | Cost to take it | Basis |
| --- | --- | --- | --- | --- |
| L1 | Separate Bun ports for fingerprint, sampling and fetch/parse | Does not deliver the shared API server. | More processes, readiness checks, addresses and cleanup paths. | A3. |
| L2 | A dynamic API plugin registry | There are known modules to register directly. | Import policy, plugin discovery and another lifecycle contract. | A9. |

## 3. Row #2 - Serve HHEM and llama through one FastAPI application

- **Scope:** Ship one Python API application with a real HHEM route and a real llama forwarding route, using the existing locked model environment.
- **Correction level:** 5 for the API/process boundary.
- **External boundary:** Shared metadata helpers are merged; this row does not depend on the unfinished planner/profile cutovers. Do not edit their reserved TypeScript APIs, proof scripts, `.github/scripts/summary-eval-hhem/measure-host.ts` or `services/hhem-evaluator/tests/host-profile-bridge.ts`. Refresh shared documentation after any intervening merges.
- **Files touched:**
  - `services/hhem-evaluator/src/hhem_evaluator/serve_api.py`
  - `services/hhem-evaluator/src/hhem_evaluator/hhem_router.py` - extracted router.
  - `services/hhem-evaluator/src/hhem_evaluator/llama_router.py` - new HTTPX forwarding route.
  - `services/hhem-evaluator/src/hhem_evaluator/forward_llama.py` - owned native client and bounded forwarding.
  - `services/hhem-evaluator/src/hhem_evaluator/dispatch_llama.py` - input admission and request cancellation.
  - `services/hhem-evaluator/src/hhem_evaluator/guard_local_requests.py` - shared loopback request guard.
  - `services/hhem-evaluator/src/hhem_evaluator/configure_server.py` - one quiet Uvicorn configuration.
  - `services/hhem-evaluator/src/hhem_evaluator/run_server.py` - retain the actual lifespan outcome when the server returns.
  - `services/hhem-evaluator/src/hhem_evaluator/load_llama_settings.py` - project the committed native address and declared request deadline.
  - `services/hhem-evaluator/src/hhem_evaluator/api_settings.py` - new shared listener settings.
  - `services/hhem-evaluator/src/hhem_evaluator/__main__.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/emit_events.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/service_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_contract.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_health.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_event.py` - wrap unchanged native evaluation data in the current CloudEvents transport.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_request.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_result.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_settings.py`
  - `services/hhem-evaluator/tests/test_api.py`
  - `services/hhem-evaluator/tests/test_settings.py`
  - `services/hhem-evaluator/tests/test_contracts.py`
  - `services/hhem-evaluator/tests/service_cases.py`
  - `services/hhem-evaluator/tests/contract_examples.py`
  - `services/hhem-evaluator/tests/llama_cases.py`
  - `services/hhem-evaluator/tests/test_scoring.py`
  - `services/hhem-evaluator/tests/test_text_boundaries.py`
  - `services/hhem-evaluator/tests/test_worker_lifecycle.py`
  - `services/hhem-evaluator/tests/test_llama_api.py` - route/client correctness, not a model substitute.
  - `services/hhem-evaluator/tests/test_llama_contracts.py`
  - `services/hhem-evaluator/tests/test_server_events.py`
  - `services/hhem-evaluator/tests/test_server_lifecycle.py`
  - `services/hhem-evaluator/tests/test_pipeline_report.py` - copy the named shared configuration into the generated report root.
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/serve_hhem.py` - keep the current caller working until PR 3 moves it.
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/services.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/run.py` - read the shared listener address and remove terminal-log matching as scoring proof; preserve host startup/control/measurement behavior.
  - `config/fastapi-server.json`
  - `config/hhem-evaluator/settings.json`
  - `docs/architecture/evaluation/hhem-evaluation-api.md`
  - `docs/architecture/evaluation/local-model-api.md`
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/fastapi-server.md`
  - `docs/architecture/contracts/identity.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/how-to/run-hhem-evaluation-api.md`

Table M - Detailed tasks

| Id | Task | Completion condition |
| --- | --- | --- |
| M1 | Declare the server configuration, llama API data and logging changes before logic. | Listener authority is C2; native destination authority is C3. Version changed native contracts and change their real readers/writers together without compatibility branches. |
| M2 | Extract the HHEM routes into an ordinary FastAPI router. | One application registers the router. HHEM keeps its real queue, worker, scoring and partial-result behavior; generic app construction does not duplicate that logic. |
| M3 | Add the thin llama route to that same application. | Expose native `/v1/chat/completions` through one lifespan-owned HTTPX client. Forward the selected declaration's validated request and preserve its response. No arbitrary proxy path, model selection in the route, retry layer, cache or custom HTTP transport. |
| M4 | Preserve meaningful native responses and errors. | The caller sees the actual generated result or explicit failure. Keep the existing nonstreaming request contract, finite HTTP deadlines and explicit cancellation/status handling. Log codes rather than response bodies. |
| M5 | Make readiness describe the enabled real APIs. | A running socket is not proof that HHEM loaded or llama is ready. The phase checks its enabled component's actual health and the process it started. Failed/disabled components are not reported as usable. |
| M6 | Keep heavy model work off the HTTP event loop. | Existing HHEM scoring remains in its owned worker; llama runs natively and is reached with asynchronous HTTP. One route cannot block health for the other. |
| M7 | Apply the small logging contract. | Standard handlers produce G's format. Change the old event reader with its producer; do not make scoring depend on successful diagnostic-file mirroring or a terminal-log search. |
| M8 | Simplify without weakening cleanup. | Close the HTTPX client and HHEM worker through the app lifecycle. Native llama lifetime belongs to the phase task in PR 3. Keep existing parent-loss/worker cleanup protections; add no general worker scheduler. |
| M9 | Remove the deprecated `/evaluate` route and update its callers. | The named HHEM route and the new llama route are current. There is no deprecated alias, redirect or second supported implementation. |
| M10 | Update the API docs and focused checks. | Define the required routes, private native address, real readiness and G's diagnostics. No direct-native bypass is documented for the new workflow. |

- **Acceptance gates - local:** Frozen Ruff/mypy and selected native API, settings, contract and process-lifetime tests from the gate guide. Keep ordinary external network/model calls out of offline tests.
- **Acceptance gates - CI:** Existing offline Python service checks and affected contract checks on the merge candidate.
- **Oracle:** Exercise the actual app/lifespan with recorded responses at the model boundary and prove fixed-upstream request forwarding, native result handling and cleanup. This checks API composition, not live model execution; the following row owns the live end-to-end proof and does not block this row's offline checks.

Table N - Decisions

| Id | Decision | Basis |
| --- | --- | --- |
| N1 | Put llama behind FastAPI. | A4-A5: one Python API address costs one local forwarding hop. |
| N2 | Keep a native llama subprocess rather than embed a new model binding. | Reuses the selected binary, existing argument readers and real runtime; avoids a new native Python dependency. |
| N3 | Keep machine collection in TypeScript. | A6 and H2. |

Table O - Alternatives not selected

| Id | Alternative | Why not selected | Cost to take it | Basis |
| --- | --- | --- | --- | --- |
| O1 | Direct native llama calls from the new workflow | Bypasses the intended Python API surface. | Fewer forwarding instructions but another caller-facing endpoint. | A4. |
| O2 | Replace the native executable with an embedded Python model binding | Not necessary to expose the model through FastAPI. | Different dependency build, model loading and cancellation behavior to validate. | A5 and N2. |

## 4. Row #3 - Deliver the live summary-eval-tests workflow

- **Scope:** Replace the HHEM-only workflow with config-selected summarization followed by HHEM evaluation of that generated summary, using the preceding servers.
- **Correction level:** 3 for workflow/report integration; pause for an additional native contract or model change.
- **Files touched:**
  - `.github/workflows/summary-eval-tests.yml` - new workflow.
  - `.github/workflows/hhem-evaluation-api-test.yml` - remove on cutover.
  - `.github/scripts/summary-eval-tests/run.py` - new phase entry point.
  - `.github/scripts/summary-eval-tests/report.py` - report entry point.
  - `.github/scripts/summary-eval-tests/serve.py` - shared app's owned launcher.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/llama.py` - native process handle owned inside the generation task, not another launcher process.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py` - reuse the current declaration readers.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/generation.py` - generation request and receipt.
  - `.github/scripts/summary-eval-hhem/run.py` - move to the new entry point.
  - `.github/scripts/summary-eval-hhem/report.py` - move to the new entry point.
  - `.github/scripts/summary-eval-hhem/serve.py` - replace with the new owned launcher.
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/__init__.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/__init__.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/channels.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/channels.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/control.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/control.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/contracts.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/contracts.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/evaluation.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluation.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/failures.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/failures.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/host_reader.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/host_reader.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/http.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/http.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/inputs.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/inputs.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/report.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/report.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/run.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/run.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/serve_hhem.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/serve_api.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/services.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/services.py`
  - `.github/scripts/summary-eval-hhem/summary_eval_pipeline/settings.py` -> `.github/scripts/summary-eval-tests/summary_eval_pipeline/settings.py`
  - `.github/scripts/summary-eval-hhem/measure-host.ts` - remove the replaced workflow-only bridge.
  - `.github/scripts/summary-eval-hhem/hardware.ts` - remove the replaced workflow-only bridge.
  - `.github/scripts/summary-eval-hhem/project-profile.ts` - remove the replaced workflow-only bridge.
  - `services/hhem-evaluator/pyproject.toml`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/base.py`
  - `services/hhem-evaluator/tests/pipeline_cases.py`
  - `services/hhem-evaluator/tests/owned_service_child.py`
  - `services/hhem-evaluator/tests/test_manual_workflow.py`
  - `services/hhem-evaluator/tests/test_generation_handoff.py`
  - `services/hhem-evaluator/tests/test_pipeline_evaluation.py`
  - `services/hhem-evaluator/tests/test_pipeline_lifetime.py`
  - `services/hhem-evaluator/tests/test_pipeline_measurement.py`
  - `services/hhem-evaluator/tests/test_pipeline_report.py`
  - `services/hhem-evaluator/tests/test_host_profile_reader_parity.py`
  - `services/hhem-evaluator/tests/host-profile-bridge.ts`
  - `config/summary-eval-tests.json`
  - `config/summary-eval-hhem.json` - replace on cutover.
  - `backend/tests/workflows/_harness.py` - update only the named workflow inventory.
  - `.github/workflows/ci.yml`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/github-actions.md`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
  - `docs/how-to/run-the-gates.md`

Table P - Detailed tasks

| Id | Task | Completion condition |
| --- | --- | --- |
| P1 | Move the workflow modules and remove the replaced bridges. | Apply the listed source/target paths with no compatibility wrappers. Update imports, native control readers, test preparation and named workflow inventories in the same PR. |
| P2 | Implement D's form and selection. | Prefill `models_file` with D1's valid default; a focused named-workflow test checks that it matches the committed pointer. Read `source_text` and model selection from the bounded platform event; remove the manual summary input. Test valid selection, invalid paths and switching between two named declaration fixtures in separate invocations. |
| P3 | Prepare the selected run configuration and native assets. | Use frozen Bun installs and `uv run --frozen --extra model --no-dev`. Build any run-local configuration from named required inputs; never edit the shared pointer or scan/copy the growing config tree. Reuse existing model validation, asset and argument readers; no repository resolver, production detached starter or memory tuning. |
| P4 | Generate and retain E1 through F4. | The task owns native llama and FastAPI, checks actual readiness/identity, sends the selected declaration's request through FastAPI, validates/extracts the final answer and atomically saves the receipt before teardown. The client never bypasses FastAPI. |
| P5 | Evaluate the generated pair through F5. | After confirmed native-model shutdown, load HHEM and consume E2. Verify receipt/source/model identity; skip evaluation explicitly under E3. Preserve actual partial results and worker-exit evidence. No second generation or supplied-summary fallback. |
| P6 | Use the Bun machine APIs instead of another collector. | Both phases call existing TypeScript fingerprint/measurement handlers on the shared server. Python only orchestrates and reads their native results. Update the existing named field/vocabulary parity check for consumed machine fields. |
| P7 | Keep lifecycle scoped to each visible workflow task. | A small script starts, calls and stops that phase's required services. Use existing process handles, `finally` and signal cleanup; no cross-step PID database, detached logger, retry daemon or secondary scheduler. |
| P8 | Produce honest combined reporting. | Implement E5, including the actual selected declaration, loaded model and answer evaluated. Preserve generation, evaluator and cleanup errors separately. Report UniEval as not run until its plan lands, without a numeric score. |
| P9 | Keep artifacts simple. | Result/report upload runs even after a phase error; server logs upload on failure/cancellation if present; omit custom retention settings. A log mirror failure does not cancel scoring or erase the real result. |
| P10 | Cut over names and checks together. | Remove the old workflow/config/entry points, update real imports and CI inputs, and keep only the current implementation. Leave production and older experimental workflows untouched. |
| P11 | Perform the real run after workflow registration. | Record the intended source revision and actual workflow outcome. If a server fails, use the phase's stop/start task and report the failure; fix the real path rather than add a benchmark, fake result or bypass call. |

- **Acceptance gates - local:** Shared test selection plus focused model-input/default, generation-handoff, phase-result, report, machine-reader parity and process-cleanup checks. Prove stale receipts and failed generation cannot reach a scorer. These support correctness, not live model execution.
- **Acceptance gates - CI:** Existing selected native/service/workflow suites on the merge candidate. No extra model-quality or resource-capacity gate.
- **Live proof:** The registered workflow resolves its selected JSON, generates through FastAPI, evaluates that same answer with real HHEM and confirms cleanup. Use separate dispatches to exercise another compatible declaration; never a model matrix or loop.
- **Oracle:** The live report binds the selected/loaded summarizer and its actual generated answer to the HHEM result from that run, with confirmed process shutdown. This settles end-to-end execution, not a quality threshold or simultaneous model capacity; offline handoff checks prove refusal cases.

Table Q - Decisions

| Id | Decision | Basis |
| --- | --- | --- |
| Q1 | Evaluate the generated answer, not an independent supplied summary. | D5, E and F4-F6. |
| Q2 | Use explicit phases and restart services between them. | A9 and F; the generation receipt survives process shutdown. |
| Q3 | Do not migrate production just to test native llama. | B1 and H7. |

Table R - Alternatives not selected

| Id | Alternative | Why not selected | Cost to take it | Basis |
| --- | --- | --- | --- | --- |
| R1 | Copy the entire old phased workflow | Imports dynamic installs, memory tuning and unrelated work. | More dependencies, shell and operational behavior to maintain. | A9 and B2. |
| R2 | Add a separate capacity-evaluation stage before real API work | Delays the required functional proof. | Runner time and interpretation without an immediate implementation decision. | A9. |
| R3 | Keep the HHEM-only workflow as a second supported entry | Creates a third workflow for this scope. | Duplicate setup, reports and maintenance. | A2 and A10. |

## See also

- [UniEval API plan](20261103-unieval-api-plan.md)
- [Plan authoring](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Gate commands](../docs/how-to/run-the-gates.md)
- [Feed workflow](../docs/how-to/run-feed-ingest-plan-test.md)
- [Canonical identity contract](../docs/architecture/contracts/identity.md)
- [HHEM process architecture](../docs/architecture/evaluation/hhem-evaluation-api.md)
- [HHEM API](../docs/reference/hhem-evaluation-api.md)
- [Machine probe API](../docs/reference/host-probe-api.md)
- [Summary workflow](../docs/reference/summary-evaluation-workflow.md)
- [Standard Python logging handlers](https://docs.python.org/3/library/logging.handlers.html)
