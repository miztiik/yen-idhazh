# Standalone HHEM evaluation API

**Last Updated**: 2026-11-02
**Level**: 5 - new model execution and API contracts; authoring only.

## 0 - Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Give a local caller a real HHEM source-support score without running or changing the news pipeline. |
| A2 | Hard scope - in | - Independent Python FastAPI service, dependencies and committed configuration.<br>- One CPU model copy, one scoring request at a time, bounded waiting and synchronous responses.<br>- Configurable anchored word windows, optional full-source comparison, body-free results and events.<br>- Manual two-text workflow, request timings and existing TypeScript CPU/RAM collection across the scoring run. |
| A3 | Hard scope - out | Table B records the exclusions, their costs and what would reopen them. |
| A4 | Chosen strategy | Native transient Pydantic contracts and one supervised scoring process; a Python workflow caller reuses the existing resource API. Requirements determine behavior; Fowler determines the independent packaging and process boundaries. |
| A5 | ESCALATE triggers | 1. Before implementing the new model/configuration/contract design, stop for the Level-5 decision under [section 6](../CLAUDE.md#6-correction-levels). This plan is not execution permission.<br>2. Stop before making results, logs or reports authoritative inputs to a later run, changing a shared contract, or changing the trust boundary.<br>3. Stop if the official model cannot load under the isolated dependency selection without patching library/model internals, changing weights, or changing scoring semantics.<br>4. Stop before changing an exclusion, adding a new network-test exception, or exceeding the platform job limit. Use [scope-change handling](../docs/how-to/handle-scope-change.md). |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes. |
| A7 | Delivery | Each Status Reckoner row is one dependent PR. The dependencies are serial because each outcome consumes the preceding outcome; pool capacity does not create independent work. All rows start PENDING. |

Table B - Exclusions and their costs

| Id | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Production wiring, `digest.yml`, existing evaluator changes and published-site changes | Production continues using its current evaluator; this API does not change published scores. | A separate integration intent and a plan for its readers and writers. |
| B2 | Summarization, article fetching, artifact lookup and other quality metrics or engines | Callers supply both texts; the score cannot assess completeness, writing quality, copying or unsupported numbers. | A separate capability request, not another branch in this service. |
| B3 | GPU execution, quantization and multiple scoring workers | CPU throughput is limited to one evaluation at a time; overload waits or is refused. | A new runtime decision with its model-quality and runner costs. |
| B4 | Jobs, polling for completed results, replay, ledgers and Git delivery | A caller must keep its connection and save its response; a service restart loses unfinished work. | A persisted-contract design and its read-side compatibility rule before any writer. |
| B5 | Live config reload, remote config lookup and collector endpoint changes | New settings take effect only at startup; resource observation uses the existing API. | A distinct operator requirement that the current startup or collector interface cannot meet. |
| B6 | Live model downloads or TCP listeners in ordinary tests | Offline tests prove composition and failure handling, not live model loading or socket transport. | The separate manual workflow proves those boundaries; a broader test exception requires a separate decision. |
| B7 | Policy-file edits and unrelated repairs | Existing policies, production adapters and unrelated defects remain unchanged. | Explicit instructions for that separate change; neither this plan nor its execution edits `CLAUDE.md` or `AGENTS.md`. |

## 1 - Status Reckoner

Table C - Delivery outcomes

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Declare independent contracts and startup settings | - | A | PENDING | - | - | - |
| C2 | 2 | Serve real bounded HHEM evaluations | 1 | B | PENDING | - | - | - |
| C3 | 3 | Run the manual workflow with resource evidence | 2 | C | PENDING | - | - | - |

## 2 - Row #1 - Declare independent contracts and startup settings

- **Scope:** Ship independently installable native contracts, explicit startup settings, compatibility vectors, their reference documentation and a model-free CI gate.
- **Files touched:** Paths marked new do not exist yet; other paths are existing integration points.
  - `services/hhem-evaluator/pyproject.toml` (new)
  - `services/hhem-evaluator/uv.lock` (new)
  - `services/hhem-evaluator/.python-version` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/__init__.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluate_request.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluation_result.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluation_event.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/worker_message.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/service_settings.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/load_settings.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/resolve_ids.py` (new)
  - `services/hhem-evaluator/tests/test_contracts.py` (new)
  - `services/hhem-evaluator/tests/test_settings.py` (new)
  - `services/hhem-evaluator/tests/test_event_ids.py` (new)
  - `services/hhem-evaluator/tests/check_uuid_vectors.ts` (new)
  - `tests/fixtures/hhem-evaluator/event-id-vectors.json` (new)
  - `config/hhem-evaluator/settings.json` (new)
  - `.github/workflows/ci.yml`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/contracts/identity.md`
  - `docs/reference/hhem-evaluation-api.md` (new)
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect the shared selection with `npm --prefix .\frontend run test:changed -- --list`; follow the selected existing checks rather than changing the selector.
  - Local, from the service directory: `uv sync --frozen --group dev`; `uv run --frozen ruff check src tests`; `uv run --frozen mypy src tests`; `uv run --frozen pytest tests/test_contracts.py tests/test_settings.py tests/test_event_ids.py`. Configure these tools in the service manifest, not the backend manifest.
  - Local: install the existing shared writer's locked Bun dependencies for the UUID comparison. The test invokes its actual UUID function; missing Bun or dependencies fails with preparation instructions, not a skip.
  - CI: add an isolated service gate conditioned on the existing scope job's code result. Install this package's locked development environment, not the backend or model extra; run its complete offline suite, lint and strict types. Keep existing full-suite checks authoritative on the merge candidate.
  - Record the tested revision, selected inputs, commands and results outside the repository. Do not claim that contract-only installation proves model loading.
- **Oracle:** The native readers accept the declared valid request/result/IPC fixtures, reject each declared invalid boundary, and produce the same event UUIDs as the existing TypeScript implementation for the named vectors. This cannot settle model loading, HTTP lifecycle or numerical model quality.
- **Decisions:**

Table D - Contract ownership and transport

| Id | Decision | Authority |
| --- | --- | --- |
| D1 | All new shapes are transient service contracts in the new service package, with no `idhazh` imports, root-package installation or legacy registry entry. Caller artifacts are outputs of one run, not inputs to a later run. A new later-run reader triggers A5. | Fowler; [schema authority](../docs/architecture/contracts/schemas.md). |
| D2 | Give each native contract date-stamped schema metadata and a short changelog. Initial version is `2026-11-02`. Results, error envelopes, events and IPC packets carry `version`; the route identifies request-body version. There is no older service payload to migrate; reject unsupported versions explicitly and leave all legacy families unchanged. | [Versioning](../CLAUDE.md#11-schema-versioning). |
| D3 | The HTTP routes are `GET /api/2026-11-02/health`, `POST /api/2026-11-02/evaluate` and generated `GET /api/2026-11-02/openapi.json`. The date prefix and operation names are protocol constants, not runtime knobs. No Swagger UI, streaming route or result-history endpoint is needed. | Plan protocol choice; FastAPI's native schema generation. |
| D4 | Pydantic owns validation and the generated schemas. Reject unknown HHEM input fields, coercion of strings/booleans into numeric controls, explicit null controls and nonblank-text failures. Optional means omittable, not nullable; OpenAPI must express the same rule. Resolve omitted controls from startup settings, never duplicated request-class defaults. | Requirements; native Pydantic behavior. |
| D5 | Request and correlation IDs accept hyphenated UUIDv4 strings and preserve supplied spelling, including letter case. Only omission generates a lowercase UUIDv4. Reject invalid supplied values; never replace them to turn refusal into success. Every HTTP attempt also receives a fresh internal execution UUIDv4, independent of supplied IDs or content. | Requirements; [identity convention](../docs/architecture/contracts/identity.md). |
| D6 | For complete evaluations return 200. Refusals use 400 for malformed/invalid JSON or controls, 403 for browser-origin/host refusal, 408 for input-read expiry, 413 for body overflow, 415 for unsupported media/encoding, 429 for full waiting capacity, 503 for disabled/unready service or queue-wait expiry, 504 for evaluation expiry, and 500 for model, worker, protocol or logging failure. Capacity and queue-expiry responses include configured `Retry-After`. Error statuses may carry a partial result. | Requirements; explicit local API policy. |
| D7 | References are the existing scorer's `chunks`, `dual_score`, model identity and loaded-weight hashing, the planner's stderr delivery, and the resource API's pinned-process commands. They are read-only references, not imports or edit targets. The current planner logger is not a ready-made HHEM envelope: the new event fields are declared in Table G. | Direct reads of `backend/idhazh/evals/hhem.py`, `services/feed-ingest-plan/src/logging/structured-logger.ts` and [resource commands](../docs/reference/host-probe-api.md). |
| D8 | The closed service error codes are `INVALID_JSON`, `INVALID_REQUEST`, `INPUT_TIMEOUT`, `BODY_TOO_LARGE`, `UNSUPPORTED_MEDIA`, `ORIGIN_FORBIDDEN`, `HOST_FORBIDDEN`, `WINDOW_LIMIT_EXCEEDED`, `QUEUE_FULL`, `QUEUE_TIMEOUT`, `SERVICE_DISABLED`, `SERVICE_STOPPED`, `WORKER_NOT_READY`, `MODEL_LOAD_FAILED`, `MODEL_IDENTITY_CHANGED`, `MODEL_SCORING_FAILED`, `INVALID_MODEL_OUTPUT`, `WORKER_EXITED`, `WORKER_PROTOCOL_FAILED`, `WORKER_STOP_FAILED`, `EVALUATION_TIMEOUT`, `CLIENT_DISCONNECTED`, `LOGGING_FAILED`, `INTERNAL_ERROR`. Each has a fixed safe message and the D6 status for its category. Client disconnect has only a terminal event, not an attempted response. | Explicit failure contract. |

Table E - Evaluation request fields

| Id | Field | Contract | Authority |
| --- | --- | --- | --- |
| E1 | `source_text`, `summary_text` | Required nonblank UTF-8 strings. Check blankness without rewriting either string. Their order is source then summary. | Requirements. |
| E2 | `full_source_text` | Optional nonblank string; mandatory when the effective full-comparison flag is true. When that flag is false, this field does not cause scoring. Never substitute the primary source. | Requirements. |
| E3 | `hhem_full`, `include_window_details` | Optional strict booleans; omission uses their separate configuration defaults. | Requirements. |
| E4 | `chunk_words`, `chunk_overlap_words` | Optional strict integers. Resolve both defaults first; then require size greater than zero and overlap greater than or equal to zero and below size. The pair 1500/900 is valid. | Requirements. |
| E5 | `request_id`, `correlation_id` | Optional strings governed by D5. No paths, model selectors, executable names, destinations or fetch URLs are request controls. | Requirements. |

Table F - Body-free response shapes

| Id | Shape | Fields and invariants | Authority |
| --- | --- | --- | --- |
| F1 | Evaluation envelope | `version`, `status` (`complete`, `partial`, `failed`), `execution_id`, `request_id`, `correlation_id`, `terminal_event_id`, `hhem`, `hhem_full`, `hhem_delta`, `effective_settings`, `windows`, `model`, `worker`, `timings_ms`, `errors`; add `window_details` only when requested. No input text or event-history array. | Requirements. |
| F2 | Score and outcome rules | Scores are finite numbers in [0, 1]; delta is primary minus full in [-1, 1], only when both scores exist. Complete requires the requested comparisons and terminal logging to succeed. Partial preserves a completed primary score when another required operation fails. Failed has no completed primary score. An incomplete comparison's maximum is not a completed score. Errors are nonempty on partial/failed results. | Requirements; Fowler's per-window construction. |
| F3 | Effective settings and counts | `effective_settings` contains resolved `chunk_words`, `chunk_overlap_words`, `hhem_full`, `include_window_details`. `windows` contains `primary` and nullable `full` counts (`planned`, `scored`) and `full_reused_primary`. Reuse reports the full logical plan with zero additional scored windows. Unplanned counts are null, not invented zeroes. | Requirements. |
| F4 | Window details | `primary` and nullable `full` arrays contain only completed valid windows: `index`, `start_word`, `end_word`, `score`. Positions are zero-based, end-exclusive indices into whitespace-split words. On identical-source reuse, full details mirror primary details without another model call. No window text. | Requirements; explicit position convention. |
| F5 | Model identity | `reference`, `configured_revision`, `loaded_revision`, `foundation_reference`, `foundation_revision`, `loaded_weights_sha256`, `loaded_config_sha256`, `service_config_sha256`, `runtime_versions`. Fingerprints describe actual loaded tensors/configuration; runtime versions identify Python, PyTorch and Transformers. Model identity is null before successful loading. | Requirements; actual-byte identity in the existing scorer. |
| F6 | Worker identity | `generation`, `pid`, nullable decimal-string `start_ticks`, nullable `pin_unavailable_reason`. The PID belongs to the owned scoring process, never the HTTP process. Replacements advance generation. Missing observations remain unavailable. | Existing TypeScript process-pin contract. |
| F7 | Timings | `queue_wait`, `primary_scoring`, `full_scoring`, `total`, each in milliseconds from monotonic clocks. Scoring durations cover their comparison's model exchanges; total starts at HTTP receipt and includes reading, validation, waiting and cleanup. Not-started work and reused full scoring have null durations. Actual measured zero remains valid. | Requirements. |
| F8 | Error detail | `code`, `phase`, nullable `field`, nullable `window_index`, `message`. Error phase uses G1's operation vocabulary; field is a known contract path or null. Use D8, never raw exceptions, input values or caller-chosen field names. Before validation, unresolved IDs, model identity, counts and timings may be null. If terminal logging fails, return `LOGGING_FAILED`, an error HTTP status and null `terminal_event_id`; do not claim a link to a log that was not written. | Requirements; safe failure projection. |
| F9 | Health | `version`, `service_instance_id`, `status` (`disabled`, `loading`, `ready`, `replacing`, `stopping`, `failed`), nullable `worker`, nullable `model`, `queue_depth`, `queue_capacity`, nullable `failure_code`. Return 200 only when ready; otherwise 503. It retains no completed results. | Requirements; process ownership. |

Table G - Events and deterministic identities

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | The event envelope is `version`, `event_id`, `execution_id`, positive integer `sequence`, nullable `request_id`, nullable `correlation_id`, nullable `caused_by_event_id`, nullable `run_id`, nullable `pipeline_name`, nullable `task_name`, `operation_id`, `operation`, `phase`, `occurred_at`, `level`, `details`. Operation values are `service`, `worker`, `request`, `queue`, `primary`, `full`; phase values are `started`, `completed`, `failed`, `cancelled`. Operation IDs are fresh UUIDv4 values retained across that operation's phases. UTC occurrence time is captured at emission. | Requirements; existing event and identity concepts. |
| G2 | Use the standard DNS namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8` and exactly `hhem\n{execution_id}\n{sequence}` as the UTF-8 UUIDv5 name, without a trailing newline. Sequence starts at one and increases within one execution. Lifecycle work has its own execution identity; caller IDs never determine uniqueness. Define this seed once. | Existing `createUuidV5` in `packages/ledger-file-writer/src/uuid/name-id.ts`; Python standard `uuid.uuid5`. |
| G3 | Root request/service events have no cause. Queue and comparison events point to their actual initiating event; the terminal event points to the last completed or failed operation. One parent emitter owns ordering and terminalization, including cancellation races. A result refers to that emitted terminal event, not to another reconstructed record. | Requirements; causality and single-writer construction. |
| G4 | Declare one strict details model with optional typed `status`, `worker`, `model`, `window_index`, `window_count`, `scored_window_count`, `queue_depth`, `duration_ms`, `score`, `errors`; reuse F2/F5/F6/F8 for shared values. Only the operation's measured fields are present. Enforce the configured serialized-byte limit before writing. No arbitrary diagnostic dictionary, exception repr, headers, credentials, text, absolute paths or input-derived property names. Use standard-library logging to stderr, with write failures propagated. Disable raw access logs/progress output; do not forward raw child stderr. | Requirements; [logging and trust rules](../CLAUDE.md#1b-logging). |
| G5 | The named compatibility fixture contains namespace, execution identity, sequence, exact seed and expected UUID, including repeated caller IDs with distinct execution identities. The Python check and a small Bun reader call their native UUID implementations against the same vectors. There is no TypeScript dependency in the service runtime. | Requirements; Fowler's independent-package ruling. |
| G6 | Optional startup context has only `run_id`, `pipeline_name`, `task_name`, each a nonempty bounded ASCII identity or null. The manual caller supplies its platform run identity and fixed workflow/task identity through a validated private startup packet; standalone startup may leave them null. Context is not scoring configuration, an HTTP body extension or a job framework, and is never derived from either text. | Requirements for available run context. |

Table H - Worker packet contract

| Id | Packet | Fields and behavior | Authority |
| --- | --- | --- | --- |
| H1 | Bootstrap | Versioned validated startup settings and frozen model asset identities; no article text, request-selected executable or backend object. Startup reports the owned process identity separately from loaded readiness. | Requirements. |
| H2 | Ready | `version`, `kind=ready`, `worker`, `model`; successful loading is reported only after fingerprints exist. Startup failure is a closed failure packet, not readiness with missing weights. | Requirements. |
| H3 | Score command | `version`, `kind=score_window`, `execution_id`, `generation`, `comparison` (`primary`, `full`), `window_index`, `start_word`, `end_word`, `source_text`, `summary_text`. One command is outstanding at a time. This private packet is the only text-bearing outbound boundary. | Fowler; requirements. |
| H4 | Window outcome | `version`, `kind` (`window_scored`, `window_failed`), matching execution/generation/comparison/window identity, nullable finite `score`, nullable `scoring_ms`, nullable closed `error`. Success requires a score; failure forbids one. No text. Parent validation rejects stale, duplicate, malformed and out-of-order outcomes. | Fowler; primary-retention requirement. |
| H5 | IPC transport | Use owned multiprocessing byte pipes and bounded JSON packets, not request-object pickle messages or a broker. Derive command bounds from the configured request allowance plus validated metadata; outcome bounds follow their finite shape. Run blocking pipe and process operations off the HTTP event loop. Closing/killing a worker must also release its pipe readers. | Standard-library process isolation; requirements. |

Table I - Initial authored settings

| Id | Setting | Initial value and meaning | Authority |
| --- | --- | --- | --- |
| I1 | `enabled` | False while the isolated feature is in development. Its declaring field states removal when the standalone API is released after real-model workflow verification. The manual command explicitly enables only its own invocation and records that effective setting; it does not edit the file. | Existing standalone-service pattern; proposed startup policy. |
| I2 | `hhem.model.reference`, `hhem.model.revision` | Initialize the reference from the existing `HHEM_MODEL` literal, without importing that module at runtime. Revision is `8e4a2e6e96c708cc76c2344f7e4757df2515292c`. Both are required configuration values, not Python defaults. | Direct scorer read and immutable model metadata. |
| I3 | `hhem.foundation.reference`, `hhem.foundation.revision` | Initialize the reference from the selected upstream HHEM configuration's `foundation` attribute. Revision is `7bcac572ce56db69c1ea7c8af255c5d7c9672fc2`. These are tokenizer/config assets only, not a second model's weights. | Direct upstream constructor and asset metadata reads. |
| I4 | `hhem.model.files`, `hhem.foundation.files` | Model: `config.json`, `configuration_hhem_v2.py`, `modeling_hhem_v2.py`, `model.safetensors`. Foundation: `config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `spiece.model`. Download only these named inputs at the configured full commit IDs. No repository discovery or foundation weights. | Verified immutable asset inventories; fixed-size reads. |
| I5 | `hhem.cpu_threads`, `hhem.interop_threads`, `hhem.cache_directory` | Two compute threads, one inter-operation thread, and `services/hhem-evaluator/var/model-cache`. Thread defaults are initial resource estimates, not measured throughput claims. Cache paths are operator configuration, never request fields. | Proposed CPU defaults; isolated dependency design. |
| I6 | `scoring.chunk_words`, `scoring.chunk_overlap_words`, `scoring.max_windows_per_comparison` | 900 words, 100 words of regular overlap, and at most 256 planned windows per comparison. Reject a larger plan explicitly before admission; never drop windows. The count limit bounds diagnostics and pathological near-total overlap and is adjustable without source edits. | Requirements for geometry; proposed finite operational bound. |
| I7 | `response.hhem_full`, `response.include_window_details` | Both false. They are permanent optional API controls; removing one requires a versioned API change. | Requirements. |
| I8 | `listener.host`, `listener.port`, `listener.max_body_bytes`, `listener.body_read_timeout_ms` | `127.0.0.1`, port 3010, 1048576 bytes (1 MiB) and 5000 milliseconds (five seconds). Host accepts only the configured loopback literals. Bound streamed reads even without Content-Length. | Proposed finite listener defaults. |
| I9 | `queue.capacity`, `queue.wait_timeout_ms`, `queue.retry_after_seconds` | Eight waiting reservations, 60000 milliseconds (one minute) and a two-second retry delay. A waiting reservation includes an input currently being read; one active evaluation is separate. | Requirements; proposed finite admission defaults. |
| I10 | `evaluation.timeout_ms` | 120000 milliseconds (two minutes), shared across all windows and both comparisons after dequeue. It is not reset for each window or full comparison. | Proposed evaluation deadline. |
| I11 | `worker.startup_timeout_ms`, `worker.replacement_timeout_ms`, `worker.stop_grace_ms`, `worker.forced_stop_ms`, `worker.shutdown_timeout_ms` | 600000 milliseconds (ten minutes) for initial download/load, 120000 milliseconds (two minutes) for cached replacement, 5000 milliseconds (five seconds) for graceful stop, another 5000 milliseconds to confirm forced stop, and 15000 milliseconds (fifteen seconds) for owned shutdown. Shutdown must accommodate its stop phases. | Proposed finite lifetime defaults. |
| I12 | `worker.max_proc_identity_bytes`, `logging.level`, `logging.max_event_bytes` | 4096 bytes for one owned PID's identity read; `INFO`; 4096 bytes per JSONL event. These are bounds, not truncation instructions. Invalid configuration fails with the setting named. | Existing bounded process reads; proposed event limit. |
| I13 | Runtime and model libraries | Separate CPython 3.12 environment. The model extra selects Transformers 4.57.6, CPU-only PyTorch 2.8.0, model-download library 0.36.0 and SentencePiece 0.2.1, with transitive versions resolved into the lockfile. Use the CPU package index, not accelerator wheels. Metadata compatibility is checked; actual loading remains Row #2/Row #3 evidence. | Published package metadata; avoid the legacy Transformers-5 adapter without changing it. |
| I14 | Packaging and dependency cost | Use the already-available `uv` tool for an independent manifest, lock and environment. Pydantic supplies validation; FastAPI/Uvicorn supply HTTP; HTTPX supplies the eventual caller and in-process test transport. API/dev installs exclude the model extra. The extra adds large CPU wheels and model downloads only where real inference runs; nothing ships to the published site. No root dependency change. | Mature-library reuse and isolated install requirement. |
| I15 | Configuration validation | Every operational value above is authored in the settings file and validated by its native reader. Revisions must be full commit IDs; no source fallback or environment-selected model destination. Freeze effective settings at startup; replacement never rereads changed config. The operational limits are initial policy choices, not benchmark results, and fall within A5's pre-implementation design decision. | Requirements; configuration substitution and startup-only semantics. |

- **Rejected alternatives:**

Table J - Contract and packaging alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Import the backend contract package for transient models | Its initializer eagerly imports the legacy model family and couples the independent service to backend packaging. | Backend installation and a new cross-package dependency; a separate decoupling change before isolation is real. | Fowler; direct initializer read. |
| J2 | Reuse the planner's event object without a new contract | Its current sparse event output does not declare this API's request, cause, terminal or worker identities. | A shared event-contract change and migrations for unrelated readers, with no beneficiary in this scope. | Direct logger/contract reads. |
| J3 | Generate service IDs through TypeScript at runtime | Python already implements the required UUID algorithms. | A second runtime and process dependency for each service installation. | Requirements. |
| J4 | Inherit the backend's model dependencies or port its adapter | The independent API need not inherit a newer loader's incompatibility with old remote code. | A coupled runtime and maintenance of library-internal compatibility code; A5 applies if the isolated official loader fails. | Requirements; official model loader. |

## 3 - Row #2 - Serve real bounded HHEM evaluations

- **Scope:** Ship the actual local HTTP API, official CPU inference, anchored scoring and a bounded process lifecycle that preserves completed primary scoring across full-source failure.
- **Files touched:**
  - `services/hhem-evaluator/pyproject.toml`
  - `services/hhem-evaluator/uv.lock`
  - `services/hhem-evaluator/src/hhem_evaluator/__main__.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/serve_api.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/dispatch_evaluation.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/read_request_body.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/queue_evaluations.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/plan_windows.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/score_windows.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/load_model.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/fingerprint_model.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/maintain_worker.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/run_worker.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/read_process_identity.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/emit_events.py` (new)
  - `services/hhem-evaluator/tests/test_windows.py` (new)
  - `services/hhem-evaluator/tests/test_scoring.py` (new)
  - `services/hhem-evaluator/tests/test_api.py` (new)
  - `services/hhem-evaluator/tests/test_worker_lifecycle.py` (new)
  - `services/hhem-evaluator/tests/test_text_boundaries.py` (new)
  - `services/hhem-evaluator/tests/replay_predictions.py` (new)
  - `services/hhem-evaluator/scripts/capture-model-recordings.py` (new)
  - `tests/fixtures/hhem-evaluator/model-inputs.json` (new)
  - `tests/fixtures/hhem-evaluator/model-predictions.json` (new)
  - `tests/fixtures/hhem-evaluator/model-identity.json` (new)
  - `.gitignore`
  - `docs/architecture/evaluation/hhem-evaluation-api.md` (new)
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect the shared selection, then run the service lint/types and one combined pytest invocation for the five new test modules. Keep Row #1's native contract suite in the service CI gate.
  - Contract/unit: test effective defaults and invalid resolved pairs, the E4 example, single-window and empty-input refusal, exact-step and anchored-tail geometry, both signs of delta, finite-score rejection, optional full scoring, exact-source reuse, details omission and source/summary direction.
  - Integration: use the real FastAPI app through HTTPX ASGI transport with its actual lifespan. Use real multiprocessing pipes and owned child processes, with recorded predictions only at the model boundary. Synchronize failure cases with explicit test handshakes, not timing guesses. No production replay mode or test-selected executable/API control.
  - Lifecycle cases: fill waiting capacity, retain responsive health while scoring, expire a queued request, cancel queued work without killing another request, cancel/expire active work, crash or invalidate full scoring after primary completion, reject stale replies, replace only after joined exit, stop after parent disappearance, and fail closed when exit or model-identity consistency cannot be established.
  - Privacy/failure cases: put distinct canary text in valid inputs, invalid values and unknown property names. Assert absence from responses, all log streams and error details; cover streamed overflow, slow input, logging failure and child failure. Ensure bounded reads work without Content-Length.
  - Real-model recording: the capture script uses the production loader and selected settings to record the named, project-authored model inputs and actual outcomes. Keep provenance and actual identity with the fixture; do not invent expected model scores. Commit only these bounded fixtures, not weights, caches or raw third-party diagnostics.
  - CI: the complete model-free service suite and existing required checks run on the merge candidate. The model extra is excluded from ordinary CI.
- **Oracle:** Through the actual request/controller/worker path, complete primary scoring, block full scoring, expire the evaluation, and assert an error-status partial result with the exact completed primary maximum, null full/delta, terminated old PID, unchanged queued work and a replacement using the same model identity. This proves lifecycle and retention, not hosted-runner speed or the model's factual accuracy.
- **Decisions:**

Table K - Real execution and failure handling

| Id | Decision | Authority |
| --- | --- | --- |
| K1 | Use one HTTP process, no reload/multiworker launch, and one spawn-owned model process. The HTTP process never loads tensors. FastAPI lifespan owns the controller and shutdown; loading/readiness and replacement leave health responsive. Routes validate and dispatch only. | Requirements; official FastAPI lifespan interface. |
| K2 | Implement the existing anchored geometry independently, without a backend dependency: split on whitespace; for a source at or below window size, score the original string once; otherwise join each full word range with spaces. Step is size minus overlap. If the last regular window does not reach the end, add the end-anchored full window once. Never add a short tail. Score every planned window and take its maximum. | Direct `chunks` and `score_over_chunks` read; requirements. |
| K3 | Compare primary and full source strings exactly, without trimming or whitespace normalization for equality. When full scoring is enabled and the strings match, reuse the completed primary score and diagnostics under F3/F4. Otherwise complete and validate primary before dispatching the first full window. Stop the comparison at its first failure; never report a maximum over unfinished work as its score. | Requirements; Fowler. |
| K4 | Load only the named immutable assets in Table I through the maintained model-download library. Supply the foundation's local tokenizer/config snapshot through the official model configuration, so the upstream constructor cannot follow its unpinned foundation default. Then use the official AutoModel loader and `predict` on CPU, original floating-point weights and inference mode. All inference/replacement loads are local-only; no article text reaches a download client. | Direct upstream constructor/card read; immutable-loading requirement. |
| K5 | Fingerprint loaded tensors in sorted-name order, including name, dtype, shape and bytes. Fingerprint actual effective prompt, tokenizer assets and model config; replace local cache paths with their immutable logical identities before canonical hashing. Record the effective service-config digest separately. A replacement must match the initial loaded identity; a cache mutation or load discrepancy makes it unavailable. No moving branch or model label substitutes for loaded identity. | Requirements; existing actual-byte fingerprint precedent. |
| K6 | Reserve bounded waiting capacity before reading a body. A reservation includes reading/validated waiting work; the active request is separate. Release it on refusal/cancellation or promotion. FIFO order is validation completion order. There is no unbounded task/future/body-reader list. Full capacity refuses immediately; queued deadlines continue during replacement and are not reset. | Requirements; finite memory and overload behavior. |
| K7 | The controller alone owns active execution identity, terminalization and the queue. Queued cancellation removes only that reservation. Active cancellation/deadline/failure stops its exact owned worker, closes IPC, confirms exit and only then creates a replacement. Preserve other queued identities and deadlines. If stopped exit cannot be confirmed, load no second model and remain unavailable. A separate parent-lifetime pipe makes the child stop on owner loss even during a blocking prediction; do not rely only on a daemon flag or its next score-command read. No process-name killing, detached worker or executor-only cancellation. | Requirements; process-safety construction. |
| K8 | Retain per-window validated progress in the parent and aggregate there. Use Table H, not stderr parsing, to know what completed. A disconnected client receives no fictional HTTP response; emit its cancellation and release its text/future. Connected full-source failures retain primary under F2. Release request bodies and completed state when delivery ends; no result cache. | Fowler; requirements. |
| K9 | Apply the single evaluation deadline from dequeue across both comparisons; body and queue have their own bounds. Stop/confirmation time can extend response latency only by the declared cleanup bounds; record actual total latency. If cleanup also fails, preserve the original error and add the cleanup failure rather than replace it. | Requirements; explicit timing semantics. |
| K10 | Bind only to configured loopback, refuse browser Origin headers and unexpected Host values, disable CORS and redirects, and enforce JSON/UTF-8/body limits before Pydantic parsing. Safe validation handlers must omit Pydantic's input echoes and unrecognized property names. Log only declared events; logging failure changes the HTTP outcome even if scores were calculated. | Requirements; input-text and transport boundaries. |
| K11 | Implement each file's named question, not another execution framework. The architecture page owns lifecycle and failure rationale; the reference page owns fields/limits and links to it. Do not copy or correct unrelated production-evaluation prose. Ignore the service's generated `var/` directory explicitly before capture/download writes. | [Documentation routing](../docs/reference/documentation-structure.md); isolation scope. |
| K12 | The ordinary test prediction reader validates captured input identity and recorded replies at the model-call boundary; it is test code only. Lifecycle tests still execute the production controller, reduction, JSON protocol and real process termination. No test asserts a plausible canned score as evidence of actual model execution. | Requirements; recorded-boundary test policy. |

- **Rejected alternatives:**

Table L - Runtime alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Run inference on the event loop or only move it to a thread | A running model call can block health or continue after cancellation without a reliable stop boundary. | Unresponsive or unbounded cancellation; a different isolation design before it meets the requirement. | Requirements. |
| L2 | Add workers, a broker, job IDs or polling | This changes serial one-model execution and synchronous delivery. | Additional model memory, infrastructure and a new persistence/transport contract. | Requirements. |
| L3 | Return only one final worker reply | A full-source crash loses primary scoring that already completed. | A durable intermediate mechanism or an acknowledgement protocol; the per-window exchange already supplies the needed evidence. | Fowler. |
| L4 | Mean aggregation, short tail windows or silent truncation | Each changes what a reported score means. | A new scoring decision and quality comparison, rather than a compatible standalone API. | Requirements; direct scorer read. |
| L5 | Return success on invalid scores, missing observations or failed logging | It reports work or evidence that did not succeed. | Loss of failure visibility and trustworthy results; no score fallback satisfies this intent. | Requirements. |

## 4 - Row #3 - Run the manual workflow with resource evidence

- **Scope:** Ship a separate manual workflow that calls the real API with two supplied texts and reports scores, timings and honest run-wide worker CPU/RAM evidence.
- **Files touched:**
  - `services/hhem-evaluator/pyproject.toml`
  - `services/hhem-evaluator/uv.lock`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/host_profile_reader.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/workflow_report.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/run_manual_evaluation.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/collect_task_profile.py` (new)
  - `services/hhem-evaluator/src/hhem_evaluator/report_evaluation.py` (new)
  - `services/hhem-evaluator/scripts/serve-host-probes.ts` (new)
  - `services/hhem-evaluator/tests/test_host_profile_reader_parity.py` (new)
  - `services/hhem-evaluator/tests/test_manual_evaluation.py` (new)
  - `services/hhem-evaluator/tests/test_manual_workflow.py` (new)
  - `services/hhem-evaluator/tests/host-profile-bridge.ts` (new)
  - `tests/fixtures/hhem-evaluator/workflow-report.json` (new)
  - `config/hhem-evaluator/host-probes.json` (new)
  - `.github/workflows/hhem-evaluation-api-test.yml` (new)
  - `.github/workflows/ci.yml`
  - `backend/tests/workflows/_harness.py`
  - `docs/how-to/run-hhem-evaluation-api.md` (new)
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect shared selection; run the service lint/types and one combined pytest invocation for the three new modules. Run the existing workflow checks selected for the bounded inventory edit, including `backend/tests/workflows/test_workflow_inputs.py` and `backend/tests/workflows/test_triggers.py`; leave unrelated full-suite execution to CI.
  - Compatibility: compare every consumed resource field's type, requiredness, nullability and enum with the actual native TypeScript schema through the named Bun bridge. Fail on mismatch or a missing runtime, never skip.
  - Integration: compose the real HHEM ASGI handler/controller with recorded model predictions. Route host commands over a test-only pipe to the existing native `createSampleHandler`, using the named `tests/fixtures/host-probes/process-inputs.json` and generated per-test files. Close its real collector/handler. Test the Python report reader and client against these real in-process handlers, not a mocked HTTP response or open socket.
  - Lifecycle/report cases: score success, partial error-status response, profiling disabled/unavailable, target exit/reuse/replacement, stop failure, bad readiness identity, early owned-child exit, parent-pipe closure and owned cleanup. A cleanup error must not replace the first failure or erase a valid score. Ordinary cases use pipes and in-process handlers; the real dispatch observes actual socket startup.
  - Workflow safety: read only the named new workflow; require exactly two text inputs and only manual dispatch, contents-read permission, no production call, no article URL lookup, no summary generation, no input-expression interpolation and no Git writes. Add it only to the generic bounded workflow filename inventory, not the production routing/input registry.
  - CI: extend the isolated service gate's preparations with the host probe's existing locked dependencies and run the complete offline caller/contract suite. The regular gate still downloads no weights.
  - Real-model observation: after execution is permitted and the workflow exists at its selected ref, dispatch it with the named project-authored source and summary fixtures. Inspect its actual HTTP result, model identity, worker pin, terminal event, timings, resource interval/unavailable reasons and shutdown outcome on `ubuntu-latest`. Require actual worker CPU and RAM observations for the enabled normal-case proof; honest unavailable results do not replace that evidence. No ledger is written, so this is a repeatable capability check, not a production-side-effect gate. A failed real-model run leaves this row incomplete; correct the in-scope cause or trigger A5.
- **Oracle:** One real manual dispatch returns a validated score from the selected CPU model and reports resource evidence for that same owned worker, with body-free logs/artifacts and no surviving owned children. A missing resource reading must be explicitly unavailable, and cannot prove CPU/RAM measurement or model-quality calibration.
- **Decisions:**

Table M - Caller, resources and reporting

| Id | Decision | Authority |
| --- | --- | --- |
| M1 | Workflow inputs are exactly `source_text` and `summary_text`, both required strings. The source input is the full article but becomes the primary API source; explicitly request no second full comparison. Do not add a model/ref input or engine matrix. The workflow's selected checkout/ref and the committed settings select the model. | Requirements. |
| M2 | Read the two named values from the platform-owned `GITHUB_EVENT_PATH` JSON file with a fixed input-byte allowance derived from the service body limit plus bounded envelope overhead. The workflow platform already creates this file; application code makes no additional text file. Never interpolate the texts into `run`, argv, environment expressions, paths, URLs, summaries or artifacts. Reject over-limit input, never truncate it. | Text-is-data boundary; workflow's required input form. |
| M3 | Python orchestrates owned service children and uses HTTPX with `trust_env=False`, redirects disabled, finite connect/read limits and explicit response-size bounds. Destinations derive only from committed loopback listener settings, not proxy/destination environment variables or article content. Parse HHEM responses with the native Pydantic result model even on error HTTP statuses, preserving partial scores. No handwritten HTTP/retry client or automatic duplicate evaluation. | Fowler; existing transport libraries. |
| M4 | Use the existing host probe's `loadConfig`, `serveSamples` and start/stop task-profile commands, without modifying their code or endpoints. A small owned Bun launcher loads the dedicated host settings, starts the existing server and shuts it down on termination or parent-pipe closure. Reuse its existing package installation and lockfile; add no second TypeScript package or collector. | Direct service/config/endpoint reads; Fowler. |
| M5 | Dedicated host configuration starts from the native host-probe settings, enables task profiling and process RAM, leaves machine RAM and cache probes off, and selects port 3011. Keep the existing global configuration unchanged. Native Zod validation owns this file; Python neither redefines it nor overrides profiling flags invisibly. | Existing instrument defaults are off; separate caller intent. |
| M6 | Establish owned-child readiness through a fresh startup identity/private pipe and matching HTTP health for HHEM; do not adopt an already-listening process. Once its model is ready, start one host profile for the F6 PID/start-tick pair before the first evaluation, retain it for the caller's scoring run, and stop it before stopping that worker. This measures the scoring run, not preceding model download/load time. | Requirements; process-pin API. |
| M7 | On generation change, never retarget an existing handle or sum interrupted CPU percentages/peaks into an invented whole-run reading. Preserve the observed interval, cancellation/end reason and old/new worker identity, and mark coverage incomplete. A later caller may start another profile through the same existing endpoints; this one-request workflow needs no replacement-profile loop. Unavailable pins skip measurement explicitly, not scoring. | Requirements; native profile interruption semantics. |
| M8 | The narrow Python host reader consumes: start `status`, optional `reason`, `handle`, `expires_at`, `target`; stop `status`, optional `reason`, `handle`, `end_reason`; profile `identity`, `outcome`, `end_reason`, `started_at`, `finished_at`, `elapsed_ms`, `unavailable`, plus `profile.processes.worker` fields `cpu_interval_ms`, `cpu`, `sampled_rss_max_kb`, `unavailable`. Native CPU observations retain `reason` and nullable `value` with `cpu_time_ms` and `percent_one_core`. Ignore unconsumed host fields deliberately; validate all consumed fields without copying raw samples, cache schemas or the whole profile. | Existing `task-command-schema.ts` and `profile-schema.ts`; Fowler. |
| M9 | Declare the new workflow-report contract before its writer: `version`, `status` (`complete`, `partial`, `failed`), nullable native `evaluation`, `resources`, `errors`. Resources contain `status` (`complete`, `incomplete`, `unavailable`), nullable native profile projection, nullable initial/final worker identities and nullable `reason` (`configured_off`, `pin_unavailable`, `profile_start_failed`, `profile_stop_failed`, `worker_replaced`, `profile_interrupted`, `measurement_unavailable`). Complete resource evidence requires the same worker, an uninterrupted explicit stop and available CPU/RAM observations. Save only this validated body-free JSON plus a short Markdown rendering. Keep CPU units explicit: one-core percent can exceed 100 percent; display KiB-derived memory in MiB without changing stored units. | Native HHEM authority plus the existing TypeScript resource contract. |
| M10 | The report preserves a valid evaluation even when resource collection or cleanup fails. An error HTTP result or operational failure fails the workflow step after writing available evidence; individually unavailable measurements stay null with reasons and are not called successful measurements. In `finally`, stop profile, HTTP service and host service through owned handles with bounded escalation; capture cleanup failures separately. | Requirements; honest partial failure. |
| M11 | Use the full configured model extra only in the manual inference job; ordinary CI remains model-free. Check out the selected ref once and keep it throughout the run. Upload only an explicit body-free file list; do not upload the event payload, texts, caches, model files or raw child output. Report actual runner conditions beside any resource reading, without a performance threshold. | Requirements; runner evidence and publication boundaries. |
| M12 | The new reference remains the field/limit authority; the new how-to owns setup, dispatch, failure inspection and cleanup. Add only links/inventory entries to the existing Actions and gate pages. Resource field meanings continue to live in the host-probe references rather than another definition. These are current behavior docs, not approval records. | [Documentation routing](../docs/reference/documentation-structure.md). |

- **Rejected alternatives:**

Table N - Workflow alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | A TypeScript HHEM caller with a complete second result schema | Python can reuse its native result contract directly. | A cross-language copy of the larger result family; the selected design needs only the smaller resource-reader projection. | Fowler. |
| N2 | Add a Python CPU/RAM collector or new collector commands | The existing pinned-process start/stop API already supplies the measurements. | Another implementation, schema family and platform test surface, without a new capability. | Requirements; existing resource API. |
| N3 | Profile the HTTP PID or present an exited worker as complete coverage | It measures the wrong process or hides an interrupted observation interval. | Misleading resource evidence; no labeling change can recover the missing interval. | Requirements. |
| N4 | Enable the existing global profiler settings or modify production workflows | It changes unrelated callers and turns isolated proof into deployment. | Broader runtime effects and a separate production-integration review. | Requirements. |
| N5 | Fetch an article or generate a summary inside the manual workflow | It adds work beyond testing this API and changes the supplied-input experiment. | More dependencies, external-content acquisition and another model execution, with separate failure meanings. | Requirements. |
