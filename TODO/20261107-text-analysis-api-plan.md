# Multilingual text-analysis API

**Last Updated**: 2026-11-08
**Level**: 5 - a reusable API host, a new model runtime and a new HTTP contract.

## 0. Operating contract

**Table A - Operating contract**

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Deliver one production-ready FastAPI component that extracts selected spaCy features from English or Chinese text while declaring Tamil as unavailable until its model exists. |
| A2 | Hard scope - in | A neutral reusable local Python API host; one independently started text-analysis API process; exact request/result/health/error contracts; W3C trace propagation; current CloudEvents diagnostics; `sm`, `md` and `lg` model profiles; two concurrent analyses; a manual verification workflow; owning configuration and documentation. |
| A3 | Hard scope - out | Table B prices every exclusion. None permits coupling text analysis to summary evaluation or an existing pipeline. |
| A4 | Chosen strategy | Fowler: extract the proven single-component FastAPI host from summary evaluation, keep service-specific contracts and diagnostics behind adapters, and run spaCy through a standard two-process executor with immediate admission refusal instead of a custom worker protocol or queue. |
| A5 | Plan state | Row 3 implementation and live verification are in progress. |
| A6 | ESCALATE triggers | 1. HHEM or UniEval HTTP/event behavior must change. 2. Text analysis must share another service process. 3. Source text must enter logs, paths, shell arguments, URLs or service persistence. 4. A request may choose a package, URL, path or executable. 5. More than two concurrent analyses or a waiting queue is required. 6. Tamil must produce features before a trained model is configured. 7. `ci.yml` or a workflow other than `spacy-tests.yml` must change. 8. The service must join `digest.yml` or another production pipeline. |
| A7 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 rows in flight because every row updates this plan and later rows consume the preceding host/workflow contract, refilling the slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A8 | Verification rule | Run no local tests, installs, imports, server starts or model loads. Add no new ordinary test suite. Existing CI may exercise changed summary-evaluator behavior; live text-analysis evidence comes only from `.github/workflows/spacy-tests.yml`. |
| A9 | Text trust boundary | Request text may enter only the validated request, the process-pool call and the returned feature data. It never becomes a prompt, event field, command argument, path, package, URL or retained service record. |
| A10 | Production/test boundary | `services/local_api_host/`, `services/text_analysis/src/` and `config/text-analysis/` are production inputs. Workflow YAML, preparation/probe scripts, temporary evidence and artifacts are verification machinery and are never imported by the API package. |

**Table B - Exclusions and their cost**

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Integration with digest ingestion, selection, summarization or publication | The digest receives no spaCy output from this work. | A separate integration plan naming the consuming stage and persisted contract. |
| B2 | Content-similarity or duplicate-story decisions | The API returns linguistic evidence but does not decide whether two texts describe one event. | A labelled similarity design with a measured false-merge policy. |
| B3 | Coreference, semantic-role labelling or cross-sentence relations | Pronouns and implied subjects remain unresolved. | A selected model/library, runtime cost and new result contract. |
| B4 | Tamil model execution | Requests using `ta` return `LANGUAGE_UNAVAILABLE`. | A configured trained Tamil pipeline that satisfies the declared feature capabilities. |
| B5 | Transformer profiles | `trf` quality and latency cannot be selected. | A separate runtime decision that prices Torch, transformer packages, model bytes and CPU latency. |
| B6 | HHEM or UniEval trace/event migration | Existing evaluator events remain on their current Python envelope without W3C fields. | A separate compatibility plan for those public and recorded contracts. |
| B7 | Waiting queue, FIFO reservations or disconnect recovery | A third simultaneous request receives `429 BUSY`, and accepted work may finish after a caller disconnects. | Measured demand for waiting, cancellation or owned task retirement. |
| B8 | Service-side result/event persistence | Operators use current HTTP results and caller-owned workflow artifacts only. | A retention, access and deletion contract. |
| B9 | Local or new ordinary tests | Feedback depends on existing CI and the manual workflow. | A separate change to the agreed verification boundary. |
| B10 | Changes to `ci.yml`, workflows other than `spacy-tests.yml`, `.github/scripts/`, `CLAUDE.md` or `AGENTS.md` | The new API remains outside ordinary pipeline automation. | An explicit scope change naming the affected behavior and cost. |

**Table C - Ownership and boundaries**

| Id | Artifact | Path | Responsibility |
| --- | --- | --- | --- |
| C1 | Neutral API host | `services/local_api_host/` | `compose_api(settings, component, render_health, events)` owns one selected component's FastAPI app, Uvicorn settings, lifespan, health/schema wiring, local-request guard, optional W3C response propagation and exact server shutdown. It owns no text-analysis or evaluator model behavior. |
| C2 | Evaluator adapter | `services/summary_evaluator/src/summary_evaluator/serve_http/` | Adapt current evaluator components to C1 while preserving every evaluator route, payload, event and process-lifetime behavior. |
| C3 | Text-analysis package | `services/text_analysis/src/text_analysis/` | Own settings, API contracts, component assembly, process-pool admission, lazy model use and feature extraction. |
| C4 | Production modules | C3 | Contains `__main__.py`, `create_api_component.py`, `load_service_settings.py`, `declare_api_contracts.py`, `declare_service_settings.py`, `manage_models.py`, `run_analysis.py`, `extract_features.py`, `extract_relations.py` and `emit_events.py`. `__init__.py` contains no behavior. |
| C5 | API configuration | `config/text-analysis/settings.json` | Own only production runtime settings: listener/body bounds, concurrency, spaCy/models, features, relation rules and logging. |
| C6 | Manual workflow | `.github/workflows/spacy-tests.yml` | Prepare a selected runtime, start the branch API, call real routes through a TypeScript trace-aware client, retain evidence and stop the exact child. |
| C7 | Verification scripts | `services/text_analysis/scripts/` | Prepare configured model wheels, own the temporary server process and call the API. They are not API imports. |
| C8 | Documentation | `docs/architecture/local-api-host.md`, `docs/architecture/text-analysis/text-analysis-api.md`, `docs/reference/text-analysis-api.md`, `docs/how-to/run-spacy-tests.md` and existing routing/layout pages | Define the reusable host, text-analysis behavior, exact wire contract and manual operation once. |
| C9 | Dependency boundary | `local_api_host` | Text analysis depends on `local_api_host`, never on `summary_evaluator`; summary evaluation also depends on `local_api_host`. Neither service imports the other's package. |
| C10 | Output boundary | HTTP and stderr | The API writes no result or event file. HTTP responses and stderr CloudEvents are its only outputs; the workflow may redirect them into its temporary directory. |
| C11 | `HostSettings` | `local_api_host/contracts.py` | Strict title, schema version, health path, schema path, listener host/port/body bounds, shutdown wait and boolean trace propagation. |
| C12 | `ApiComponentRuntime` | `local_api_host/create_api_component.py` | Router, opaque state, async start/shutdown, async health observation and path-to-refusal callbacks. Evaluator-specific worker observations stay outside this type. |
| C13 | `HostEventSink` | `local_api_host/create_api_component.py` | Async-safe `started`, `ready`, `stopped`, `failed` callbacks that receive the host/request trace context and typed service-owned event data. |
| C14 | `RequestTrace` | `local_api_host/propagate_trace_context.py` | Trace ID, span ID, optional parent span ID and optional canonical trace state; middleware stores it plus the monotonic request-start instant on request state and writes its W3C carrier on the response. |

**Table D - HTTP and trace contract**

| Id | Concern | Contract |
| --- | --- | --- |
| D1 | Analyze | `POST /api/2026-11-07/analyze-text` accepts Table E and returns its result or Table G error. |
| D2 | Health | `GET /api/2026-11-07/get-text-analysis-health` returns strict `enabled`, `status` from `ready`, `disabled`, `failed`, `stopping`, `active_requests`, `max_concurrent_requests`, `pool_ready` and configured language/profile/feature capabilities without loading a model. HTTP 200 only for `ready`; every other status is 503. |
| D3 | Schema | `GET /api/2026-11-07/get-text-analysis-schema` returns current FastAPI OpenAPI without interactive Swagger or ReDoc pages. |
| D4 | Listener | Default loopback `127.0.0.1:3020`; one Uvicorn process; no reload, proxy headers, server header or Uvicorn access/error output. |
| D5 | Local safety | C1 rejects browser Origin, duplicate Host and any Host other than the configured loopback binding before body reading. It enforces configured body bytes and body-read deadline. |
| D6 | Incoming trace | C1 reads `traceparent` and optional `tracestate`. Valid context keeps its trace ID and becomes the parent of a new nonzero span; outgoing flags are `00` and canonical state is preserved. Missing or invalid context creates a new root, matching the TypeScript APIs. |
| D7 | Response trace | Every response, including health, schema, refusal and `429`, returns the operation's `traceparent` and optional canonical `tracestate`. Trace data is not duplicated in the JSON body. |
| D8 | Parent identity | The incoming span ID is retained as internal `parentSpanId`; it is not a request ID. The new response span ID identifies this API operation. |
| D9 | Event parity | Every event caused by an HTTP request carries the exact trace carrier returned with that response. Service lifecycle events use one service-root context. |
| D10 | CloudEvents boundary | HTTP payloads remain native API JSON. Only emitted diagnostics use the current CloudEvents structured envelope in Table G. |
| D11 | Route matching | Paths and methods match exactly, with no trailing-slash aliases or redirects. Retired/unknown paths return 404; wrong methods retain `Allow`. |

**Table E - Request, features and result**

| Id | Field or shape | Contract |
| --- | --- | --- |
| E1 | `text` | Required nonblank Unicode string. Preserve exact source text; refuse a body over D5 rather than trim or truncate. |
| E2 | `language` | Required literal `en`, `zh` or `ta`. No regional fallback or language canonicalizer. `ta` is valid input but currently unavailable. |
| E3 | `model_profile` | Optional literal `sm`, `md` or `lg`; omission selects configured `md`. |
| E4 | `features` | Optional nonempty unique list from E8-E13. Omission selects `relations`, `entities`, `sentences` and `document_metrics` in that order. |
| E5 | Removed request fields | No payload `version`, `request_id`, package, model version, URL, path, executable or runtime group. |
| E6 | Result root | Strict `status`, resolved `language`, selected `model` and ordered `features`; no service/process identity, trace fields, queue state or timings. |
| E7 | Model identity | Strict profile, package, model version and spaCy version actually used. |
| E8 | `entities` | Ordered source mentions with label, exact text, zero-based half-open code-point offsets and sentence index. |
| E9 | `sentences` | Ordered sentence index, exact text and zero-based half-open code-point offsets. |
| E10 | `relations` | Ordered sentence-local action spans, nonempty actor spans and possibly empty object/time/place spans. No coreference or cross-sentence linking. |
| E11 | `noun_phrases` | Ordered noun-chunk spans where the selected language/model supports them; otherwise feature-level `FEATURE_UNAVAILABLE`. |
| E12 | `linguistic_tokens` | Ordered tokens with text, offsets, sentence index and nullable lemma, part of speech, dependency, head index and morphology. |
| E13 | `document_metrics` | Source code-point/UTF-8 byte counts, token/sentence/entity counts and nullable relation count. It does not trigger an unselected relation calculation. |
| E14 | Feature result | One entry per requested feature in request order: `feature`, `status` from `complete`, `failed`, nullable typed `data`, nullable feature error. Complete has only data; failed has only error. |
| E15 | Top-level status | `complete` when every feature completes and `partial` when completed and failed features coexist; both use HTTP 200. `failed` means every requested feature has a feature-level failure and uses HTTP 422. Request-level failures use Table G's error result instead. |
| E16 | Evidence span | Exact source text plus integer `start_char`, `end_char`, `sentence_index`; slicing the input by the half-open offsets must reproduce the text. |
| E17 | Partial preservation | A missing capability produces feature-level `FEATURE_UNAVAILABLE`; an isolated extractor/post-processing exception produces feature-level `FEATURE_FAILED`. Completed siblings survive either. Shared document analysis, invalid worker outcome, transport and process failures remain request-level `ANALYSIS_FAILED`. |

**Table F - Settings, models and runtime**

| Id | Concern | Contract |
| --- | --- | --- |
| F1 | Settings root | Strict `version`, `changelog`, `enabled`, `listener`, `max_concurrent_requests`, `spacy_version`, `default_features`, `allowed_features`, `languages`, `relation_rules`, `logging`. No workflow key. |
| F2 | Enabled | Default `true`; `false` creates no process pool, leaves health/schema available and makes analysis return `SERVICE_DISABLED`. |
| F3 | Listener/body | Host `127.0.0.1`, port `3020`, maximum body `1,048,576` bytes, body-read deadline `5,000` milliseconds and graceful shutdown `15,000` milliseconds. |
| F4 | Concurrency | `max_concurrent_requests: 2`; allowed values are `1` or `2`. The initial value means at most two spaCy analyses and two resident model instances. A value above two is a later measured runtime decision. |
| F5 | spaCy | Exact configured spaCy `3.8.18`; model package versions `3.8.0`. Startup verifies installed spaCy identity without loading model weights. |
| F6 | English models | Language entry fields are `enabled: true`, `default_profile: "md"`, `supported_features` and `profiles`. Profiles map `sm`, `md`, `lg` to exact package/version/HTTPS URL for `en_core_web_sm`, `en_core_web_md`, `en_core_web_lg`; all support the Table E vocabulary. |
| F7 | Chinese models | Same language-entry shape as F6 for `zh_core_web_sm`, `zh_core_web_md`, `zh_core_web_lg`; default `md`; noun phrases are absent from `supported_features` and nullable token attributes remain allowed. Preparation includes exact `spacy-pkuseg==1.0.2`. |
| F8 | Tamil declaration | Language entry is `enabled: false`, `default_profile: null`, empty `supported_features` and empty `profiles`. After strict field-vocabulary validation, `ta` returns `LANGUAGE_UNAVAILABLE` before profile/model resolution or process-pool admission. |
| F9 | Model destinations | Every profile declares exact package, version and HTTPS wheel URL in configuration. Requests and environment variables cannot add or replace a destination. |
| F10 | Dependencies | Production: FastAPI, Pydantic, Uvicorn, spaCy, AnyIO, OpenTelemetry API and the local API-host package. Verification group: `httpx`. No Torch or transformer bridge. |
| F11 | Relation policy | One common configured policy: action POS `VERB`, `AUX`; actor paths `nsubj`, `csubj`, `nsubj:xsubj`, `agent -> pobj`; object paths `dobj`, `dative`, `attr`, `oprd`, `nsubjpass`, `csubjpass`; conjunction `conj`; time labels `DATE`, `TIME`; place labels `GPE`, `LOC`, `FAC`. Initial language overrides are empty. |
| F12 | Relation algorithm | Visit source-ordered actions; collect configured actor/object dependent subtrees and recursive conjunctions; treat passive subjects as objects; attach configured time/place entities in the action sentence; deduplicate by offsets; emit nothing without an actor. |
| F13 | Runtime preparation | `uv sync --frozen`, then install exact configured spaCy/model wheels through the trusted preparation script. Start through `uv run --no-sync python -m text_analysis`; requests never install software. |
| F14 | Production preparation | The script supports one selected language/profile for workflow use and all enabled profiles for production preparation. It verifies installed package and model metadata in a fresh subprocess without loading weights. |
| F15 | Executor | Parent owns `ProcessPoolExecutor(max_workers=max_concurrent_requests)`. It submits one strict `AnalysisCommand` dump containing text, language, profile and ordered features, and validates one `AnalysisOutcome` containing model identity, feature results and F18 process timings. The trusted parent creates the serialized value; callers never supply executor bytes. No custom command/reply protocol or worker generation exists. |
| F16 | Admission | After body validation, acquire a configured AnyIO capacity token without waiting. No token returns `429 BUSY`; accepted work is submitted immediately, so the executor receives no waiting backlog. |
| F17 | Process-local model slot | Each executor process stores at most one current `(language, profile)` model. Same-key work reuses it; a different key releases and replaces it before analysis. |
| F18 | Timing | The process returns nonnegative `model_load_ms` and `analysis_ms`. The parent measures `total_ms` with a monotonic clock from immediately before body reading until the validated response model is complete, before encoding. Timings appear only in Table G events. |
| F19 | Failure | Missing capability and isolated post-processing failures produce E14 `FEATURE_UNAVAILABLE` or `FEATURE_FAILED` without failing service health. Missing package/model maps to request-level `MODEL_UNAVAILABLE`. Shared document analysis, invalid worker outcome, executor transport or process failure maps to request-level `ANALYSIS_FAILED`; executor/process integrity failures also fail health and stop admission. No automatic pool repair occurs. |
| F20 | Disconnect | The service does not monitor or replace work for a disconnected caller. Accepted analysis may complete without a delivered response. |
| F21 | Health | Ready requires valid settings and a usable executor, not loaded weights. Report active requests, capacity, configured capabilities and pool readiness; never worker PID, generation, queue depth or loaded-model claims. |
| F22 | Shutdown | C1 stops admission and waits for active analyses within the configured graceful interval. It cancels unstarted futures and closes the executor. It emits no stopped event until every pool process exits; exceeding the interval fails lifespan so the external owner terminates the API process group. |
| F23 | Logging | Strict `level` and positive `max_event_bytes`; default `INFO` and `4,096` bytes. No file path, retention or workflow field. |
| F24 | Model capability check | After loading, verify configured language, pipeline components and parser/entity labels. A missing capability fails only its selected feature with `FEATURE_UNAVAILABLE`; incompatible package/language identity is `MODEL_UNAVAILABLE`. |

**Table G - Errors and diagnostics**

| Id | Code or event | HTTP | Contract |
| --- | --- | --- | --- |
| G1 | Error shape | Parent status | Strict `error` with code, fixed safe message, retryable boolean and nullable feature. No text, header, path or raw exception. |
| G2 | `INVALID_REQUEST` | 422 | Retryable false; message `The text-analysis request is invalid.` Malformed JSON, invalid field, invalid trace-independent request value or unsupported media type. |
| G3 | `BODY_TOO_LARGE` | 413 | Retryable false; message `The request body is too large.` Body crosses F3. |
| G4 | `HOST_FORBIDDEN` | 403 | Retryable false; message `The request Host header is not accepted.` |
| G5 | `ORIGIN_FORBIDDEN` | 403 | Retryable false; message `Browser Origin requests are not accepted.` |
| G6 | `SERVICE_DISABLED` | 503 | Retryable false; message `The text-analysis service is disabled.` |
| G7 | `BUSY` | 429 | Retryable true; message `The text-analysis service is busy.` Both F4 slots are active; no waiting. |
| G8 | `LANGUAGE_UNAVAILABLE` | 422 | Retryable false; message `The selected language is not available.` Valid `ta` has no model. |
| G9 | `UNSUPPORTED_MODEL_PROFILE` | 422 | Retryable false; message `The selected model profile is not supported.` |
| G10 | `UNSUPPORTED_FEATURE` | 422 | Retryable false; message `The selected feature is not supported.` |
| G11 | `MODEL_UNAVAILABLE` | 503 | Retryable true; message `The selected model is not available.` Declared package is missing, incompatible or unloadable. |
| G12 | `FEATURE_UNAVAILABLE` | 200 with sibling success, otherwise 422 | Retryable false; message `The selected feature is not available.` The selected model lacks a required capability. |
| G13 | `FEATURE_FAILED` | 200 with sibling success, otherwise 422 | Retryable true; message `The selected feature failed.` An isolated extractor or post-processing exception names only the affected feature and does not fail health. |
| G14 | `ANALYSIS_FAILED` | 500 | Retryable true; message `The text analysis failed.` Shared document analysis, invalid worker outcome, executor transport or process failure; feature is null. |
| G15 | CloudEvents envelope | - | Match the current TypeScript common schema: strict CloudEvents `1.0`, lowercase UUIDv4 ID, source `/services/text-analysis`, valid UTC second/millisecond `Z` time, `application/json`, valid `traceparent`, optional canonical `tracestate`, typed JSON data. |
| G16 | Service event types | - | `text-analysis.service.started`, `.ready`, `.stopped`, `.failed`. |
| G17 | Request event types | - | `text-analysis.request.completed`, `.partial`, `.failed`. Health/schema probes emit no request event. |
| G18 | Request event data | - | Language, profile/package/model/spaCy versions, requested feature names and ordered statuses, feature-local `FEATURE_UNAVAILABLE`/`FEATURE_FAILED` codes, active/capacity counts, F18 timings, aggregate result status and fixed request error code. |
| G19 | Privacy | - | Events contain no request text, evidence text/spans, model URL, raw validation data, headers, process IDs, paths or exceptions. |
| G20 | Delivery | - | Validated JSON lines go to stderr only. The workflow may capture them. A diagnostic write failure does not introduce a public error code or rewrite completed feature data; later health reports failure. |

**Table H - Manual workflow contract**

| Id | Workflow behavior | Contract |
| --- | --- | --- |
| H1 | Registration | Keep `.github/workflows/spacy-tests.yml` manual-only with `workflow_dispatch`; no push, pull-request, schedule or callable trigger. It must exist on the default branch before dispatch by filename. |
| H2 | Permissions | `contents: read`; checkout credentials disabled. |
| H3 | Inputs | The dispatch selects its branch or tag. Inputs are language `en` or `zh`; profile `sm`, `md` or `lg`, default `md`; feature mode `default`, `all` or `custom`; optional custom feature CSV; required text. The form explains the default feature order, all-language support and a custom CSV example. |
| H4 | Checkout | Resolve the selected ref to `github.sha`, checkout and verify that exact commit with credentials disabled, record selected ref/SHA, workflow SHA and tested commit, and invalidate evidence after any later Row 3 edit. |
| H5 | Environment | Stock `ubuntu-latest`, Python 3.12, pinned uv and the repository's TypeScript common-contract toolchain. |
| H6 | Preparation | Sync the text-analysis environment, prepare only the selected model, then start with the F13 command. Workflow values never become shell source. |
| H7 | Live behavior | Wait for health, fetch schema, submit selected analysis, submit Tamil and, for Chinese, submit one unavailable noun-phrase feature combination. |
| H8 | Concurrency | Start two `document_metrics` requests concurrently, each using generated 750,000-byte ASCII text under the 1 MiB body bound; wait until health reports two active analyses, then require a third request to return `429 BUSY`. These requests also warm both process-local model slots. |
| H9 | Trace interoperability | A TypeScript probe creates an operation with the existing common helpers, calls every route and proves each response retains the trace ID and returns a new span ID. For analysis/refusal responses, the terminal request event uses the same carrier. |
| H10 | CloudEvents | Validate every captured nonblank stderr record with the actual TypeScript `CloudEventSchema`; validate service/request type and data separately; assert no event value equals supplied text or returned evidence text. |
| H11 | Feature checks | Every completed evidence span round-trips. Chinese noun phrases fail only that feature. Tamil fails before executor admission. Result model identity matches configuration. |
| H12 | Timing checks | Completed/partial/failed request events carry finite nonnegative F18 values. After H8 warms both processes, repeat the selected analysis and require zero model-load time. |
| H13 | Evidence | Write one machine-readable report, captured events and an escaped job summary under the runner temporary directory. No evidence path enters API configuration. |
| H14 | Cleanup | The Python runner starts one new process session, retains the exact `Popen` child and signals only that child's process group in `finally`, so its pool children stop too. It waits, force-kills the same group if needed and confirms the child exit. No PID file, start-tick check, nonce or name-based kill. |
| H15 | Artifact | Upload one run/attempt-named artifact even on failure. Retention belongs to workflow YAML. Cleanup and upload failure fail the job. |
| H16 | Required runs | Before Row 3 merges, dispatch its final branch ref once for English `md` and once for Chinese `md`; both runs must record the same immutable `github.sha`. Other profiles remain manual choices, not merge gates. |
| H17 | Job bound | Sixty minutes; reaching it fails the selected profile and remains below GitHub's six-hour job boundary. |
| H18 | Test boundary | No local command and no new ordinary test directory. Existing CI remains unchanged; this workflow is the text-analysis functional gate. |

## 1. Status Reckoner

**Table I - Delivery rows**

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | 1 | Extract the reusable local Python API host | - | A | DONE | extract-reusable-api-host | - | Extract reusable API host |
| I2 | 2 | Register the manual text-analysis workflow | 1 | B | DONE | register-text-analysis-workflow | - | Register text analysis workflow |
| I3 | 3 | Build and verify the multilingual text-analysis API | 1, 2 | C | PENDING | - | - | - |

## 2. Row #1 - Extract the reusable local Python API host

- **Scope:** Move the proven single-component FastAPI mechanics into a neutral installable package and adapt summary evaluation to it without changing any evaluator behavior.
- **Files touched:**
  - `services/local_api_host/.python-version`
  - `services/local_api_host/pyproject.toml`
  - `services/local_api_host/uv.lock`
  - `services/local_api_host/src/local_api_host/__init__.py`
  - `services/local_api_host/src/local_api_host/contracts.py`
  - `services/local_api_host/src/local_api_host/create_api_component.py`
  - `services/local_api_host/src/local_api_host/compose_api.py`
  - `services/local_api_host/src/local_api_host/configure_server.py`
  - `services/local_api_host/src/local_api_host/guard_requests.py`
  - `services/local_api_host/src/local_api_host/propagate_trace_context.py`
  - `services/local_api_host/src/local_api_host/read_request_body.py`
  - `services/local_api_host/src/local_api_host/run_server.py`
  - `services/summary_evaluator/pyproject.toml`
  - `services/summary_evaluator/uv.lock`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/compose_api.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/configure_server.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/guard_local_requests.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/run_server.py`
  - `services/summary_evaluator/src/summary_evaluator/shared/create_api_component.py`
  - `services/summary_evaluator/src/summary_evaluator/shared/read_request_body.py`
  - `docs/architecture/local-api-host.md`
  - `docs/architecture/evaluation/summary-evaluator.md`
  - `docs/reference/summary-evaluator-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/20261107-text-analysis-api-plan.md`
- **Acceptance gates:**
  - Local: none.
  - Existing CI: unchanged summary-evaluator contract, component-registration, server-event, API and lifecycle checks exercise the extracted package through the real adapter; no existing workflow edit.
  - Dependency locks: generate `services/local_api_host/uv.lock` and update `services/summary_evaluator/uv.lock`; CI installs the path dependency from those manifests.
  - Record the selected CI checks, exact commit and results in the row report.
- **Oracle:** Every current summary-evaluator HTTP response, OpenAPI path, health payload, event JSON and selected-scorer lifecycle remains byte/field compatible while the implementation imports C1; this cannot certify text-analysis behavior.

**Table J - Row 1 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Reuse code through `local_api_host`, not a shared listener process. | Current independent-scorer architecture and C9. |
| J2 | Compose exactly one selected component per process; keep the registration list outside the host. | Current remote-main scorer lifetime and B10. |
| J3 | Make trace propagation opt-in so evaluator responses/events remain unchanged. | B6 and D6-D9. |
| J4 | Keep health models, error bodies and event writers service-owned callbacks. | Avoids turning evaluator contracts into host vocabulary. |
| J5 | Keep compatibility wrappers at existing evaluator import paths where they prevent broad caller edits; wrappers contain no copied implementation. | Structural reuse with a bounded migration surface. |

**Table K - Row 1 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Import `summary_evaluator` from text analysis | It couples unrelated service ownership and dependencies. | Make summary evaluation a permanent text-analysis runtime dependency. | C9. |
| K2 | Add text analysis to the evaluator listener | It recreates the restart/memory coupling remote main removed. | Change evaluator deployment, health and failure boundaries. | Current architecture. |
| K3 | Copy evaluator server modules | The copies drift and every fix must land twice. | Own duplicate host guards, lifecycle and Uvicorn behavior. | DRY. |
| K4 | Add dynamic subscriptions/plugins | No current runtime discovery requirement exists. | Add import security, ordering and failure semantics. | B10. |

## 3. Row #2 - Register the manual text-analysis workflow

- **Scope:** Put the complete manual workflow on the default branch so Row 3 can be dispatched against an immutable implementation commit.
- **Files touched:**
  - `.github/workflows/spacy-tests.yml`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_triggers.py`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/reference/github-actions.md`
  - `TODO/20261107-text-analysis-api-plan.md`
- **Acceptance gates:**
  - Local: none.
  - Existing CI: unchanged checks selected for these files; no CI workflow edit.
  - After merge: `gh workflow view spacy-tests.yml --ref main` resolves the manual trigger and Table H inputs.
  - Record merged revision and workflow-view result.
- **Oracle:** The default branch exposes a dispatchable workflow whose selected ref resolves to and verifies `github.sha`, and whose steps reference only Row 3 service-local scripts; it cannot prove the absent API implementation.

**Table L - Row 2 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Register before Row 3 because GitHub dispatches the default-branch workflow definition. | GitHub workflow behavior. |
| L2 | Keep the workflow manual-only and let its selected ref own the tested commit. | H1-H4. |
| L3 | Keep preparation, probes, evidence and cleanup under `services/text_analysis/scripts/`, never `.github/scripts/`. | C7 and B10. |
| L4 | Register the manual-only workflow before implementation; later contract changes remain explicit workflow edits with bounded tests. | Reversible delivery boundary. |

**Table M - Row 2 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Add to an existing pipeline/workflow | It couples model downloads and API experiments to unrelated triggers. | Price every affected trigger and runtime. | B10. |
| M2 | Delay first workflow registration until implementation | A filename dispatch requires the workflow to exist on the default branch. | Merge without a registered live-evidence path. | L1. |
| M3 | Add automatic triggers | Every matching event would install models without an explicit operator choice. | Define bounded path selection and profile cost. | H1. |
| M4 | Use local verification instead | It violates the settled verification boundary. | Change A8 and H18. | A8. |

## 4. Row #3 - Build and verify the multilingual text-analysis API

- **Scope:** Implement Tables C-H on the reusable host and prove English/Chinese behavior, two-request concurrency and TypeScript trace interoperability through the registered workflow.
- **Files touched:**
  - `config/text-analysis/settings.json`
  - `.github/workflows/spacy-tests.yml`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_triggers.py`
  - `services/text_analysis/.python-version`
  - `services/text_analysis/pyproject.toml`
  - `services/text_analysis/uv.lock`
  - `services/text_analysis/scripts/prepare-selected-model.py`
  - `services/text_analysis/scripts/run-spacy-test.py`
  - `services/text_analysis/scripts/probe-text-analysis.ts`
  - `services/text_analysis/src/text_analysis/__init__.py`
  - `services/text_analysis/src/text_analysis/__main__.py`
  - `services/text_analysis/src/text_analysis/create_api_component.py`
  - `services/text_analysis/src/text_analysis/load_service_settings.py`
  - `services/text_analysis/src/text_analysis/declare_api_contracts.py`
  - `services/text_analysis/src/text_analysis/declare_service_settings.py`
  - `services/text_analysis/src/text_analysis/manage_models.py`
  - `services/text_analysis/src/text_analysis/run_analysis.py`
  - `services/text_analysis/src/text_analysis/extract_features.py`
  - `services/text_analysis/src/text_analysis/extract_relations.py`
  - `services/text_analysis/src/text_analysis/emit_events.py`
  - `docs/architecture/text-analysis/text-analysis-api.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/reference/text-analysis-api.md`
  - `docs/reference/api-routing.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/reference/github-actions.md`
  - `TODO/20261107-text-analysis-api-plan.md`
- **Acceptance gates:**
  - Local: none. Do not install, import, lint, type-check, start or load models locally.
  - Existing CI: allow unchanged checks selected by the pull request; keep `ci.yml` and every workflow other than `spacy-tests.yml` unchanged, and do not treat ordinary CI as spaCy evidence.
  - Live: dispatch the two H16 runs against the final immutable commit. Any later Row 3 edit invalidates both. Preserve run URL, workflow SHA, tested commit, inputs, artifact ID, conclusion and report.
  - Dependency lock: generate `services/text_analysis/uv.lock` during implementation; verify installation only in CI/manual workflow.
  - Documentation: update every owning page in this row; do not modify `CLAUDE.md` or `AGENTS.md`.
- **Oracle:** Both H16 runs pass Table H against the final commit, every evidence span round-trips, the third concurrent request is refused without waiting, and TypeScript response/event tracing retains one trace with a new API span; this cannot settle linguistic quality, `sm`/`lg` quality or digest usefulness.

**Table N - Row 3 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | Keep request-selectable `sm`, `md`, `lg`; default `md`; omit `trf`. | F5-F10 and spaCy CPU/transformer package design. |
| N2 | Keep selectable features and partial results. | E4 and E8-E17. |
| N3 | Use TypeScript-compatible W3C headers instead of body request/correlation IDs. | D6-D9 and current common contracts. |
| N4 | Use two standard executor processes plus immediate admission, not a custom worker or queue. | F4 and F15-F20. |
| N5 | Keep one lazy model per process, so concurrency bounds memory without LRU coordination. | F17. |
| N6 | Keep API configuration free of workflow settings. | F1 and C5-C7. |
| N7 | Keep all emitted text-analysis diagnostics on the current trace-aware CloudEvents envelope while leaving evaluator envelopes unchanged. | G15-G20 and B6. |
| N8 | Use one common relation policy and add no language override without observed evidence. | F11-F12. |

**Table O - Row 3 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Custom process messages, generations and restart protocol | Standard executor processes already supply required concurrency. | Reintroduce protocol, replacement and worker-specific errors. | F15-F20. |
| O2 | Waiting queue or FIFO reservation | The API contract is immediate capacity or `429`. | Add waiting, timeout, cancellation and queue observability. | G7. |
| O3 | Multiple Uvicorn workers | Each process would duplicate server state and model pools. | Define aggregate health, logging and memory behavior across servers. | C1 and F4. |
| O4 | Global LRU model cache | Processes do not share model objects, so coordination adds no useful reuse. | Add cross-process ownership and eviction. | F17. |
| O5 | Transformer profile | It adds Torch and transformer runtime to the initial API. | Price quality, model bytes and CPU latency first. | B5. |
| O6 | Regional language fallback | Only exact base tags are in contract. | Add canonicalization dependency and fallback semantics. | E2. |
| O7 | Request body version or request ID | Route date and W3C carrier already own those identities. | Add duplicate version/correlation authorities. | D6-D8 and E5. |
| O8 | Persist analyses/events | It creates a sensitive text store unrelated to extraction. | Declare retention, access and deletion. | B8. |
