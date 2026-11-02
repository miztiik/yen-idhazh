# HHEM evaluation API

**Last Updated**: 2026-11-02

Which fields, identities and startup settings the independent HHEM evaluator
accepts. The package serves synchronous local CPU evaluations with one owned
model process and bounded waiting. Existing pipeline evaluation and published
data are unchanged. The [architecture](../architecture/evaluation/hhem-evaluation-api.md)
owns admission, cancellation, model loading and failure handling.

## Native ownership and version

`services/hhem-evaluator/src/hhem_evaluator/contracts/` owns the native Pydantic
models and their on-demand JSON Schemas. Every schema has date-stamped
`version` and `changelog` metadata. The initial version is `2026-11-02`.
Results, health, events, settings and worker packets require this wire version;
unsupported or missing versions fail validation. There is no older service
payload to migrate and no legacy contract registration.

The protocol reserves `GET /api/2026-11-02/health`,
`POST /api/2026-11-02/evaluate` and `GET /api/2026-11-02/openapi.json`.
The request body's version comes from that route, not a body field. These
are protocol names, not listener settings. No interactive documentation UI,
streaming, polling or result-history endpoint is defined.

These are transient contracts. The caller supplies both texts and saves the
response. No service result is an authoritative input to a later run.

## Request and resolved controls

`EvaluateRequest` rejects unknown fields, numeric coercion and explicit null.
Omittable fields have no operational class default. Native JSON Schema and
FastAPI OpenAPI generation both describe them as optional, non-nullable inputs.

Table A - Request fields

| Id | Field | Accepted value |
| --- | --- | --- |
| A1 | `source_text`, `summary_text` | Required nonblank UTF-8 strings, source first. Blankness is checked without changing either string. |
| A2 | `full_source_text` | Omittable nonblank UTF-8 string. Required when the resolved full-comparison flag is true; never replaced with the primary source. Supplying it while full comparison is off does not enable scoring. |
| A3 | `hhem_full`, `include_window_details` | Omittable strict booleans. Each uses its own startup default. |
| A4 | `chunk_words`, `chunk_overlap_words` | Omittable strict integers. Size is positive; overlap is nonnegative. Apply both startup defaults, then require overlap below size. A size of 1500 words with 900 words of overlap is valid. |
| A5 | `request_id`, `correlation_id` | Omittable UUIDv4 strings. Supplied spelling is preserved; only omission generates a value. The [identity contract](../architecture/contracts/identity.md#6-hhem-execution-and-event-identity) defines generation and event seeds. |

`resolve_request` produces `EffectiveSettings` with exactly `chunk_words`,
`chunk_overlap_words`, `hhem_full` and `include_window_details`. An invalid
resolved pair or missing required full source raises a safe `INVALID_REQUEST`
detail. Request fields cannot select paths, models, programs or destinations.

## Body-free outcomes

`EvaluationResult` is both the score envelope and the error envelope. It has
no input text or event-history array. Nullable unresolved values remain null;
they are not replaced with invented IDs, timings or zero counts.

Table B - Result fields

| Id | Field | Contract |
| --- | --- | --- |
| B1 | `version`, `status` | Current wire version; status is `complete`, `partial` or `failed`. |
| B2 | `execution_id`, `request_id`, `correlation_id`, `terminal_event_id` | Execution UUIDv4; nullable caller UUIDv4 values before validation; nullable terminal UUIDv5 only when terminal logging fails. The parent returns the actual emitted terminal event's ID. |
| B3 | `hhem`, `hhem_full`, `hhem_delta` | Nullable finite scores from zero to one. Delta is primary minus full, from minus one to one, and is null without both scores. |
| B4 | `effective_settings` | The resolved control set, or null before valid resolution. |
| B5 | `windows` | Nullable `primary` and `full` plans, each with positive `planned` and nonnegative `scored` counts; scored cannot exceed planned. `full_reused_primary` identifies full-source reuse. Unplanned counts are null. |
| B6 | `model`, `worker` | Nullable identities defined below. A completed primary score requires both. |
| B7 | `timings_ms` | Nullable nonnegative finite `queue_wait`, `primary_scoring`, `full_scoring`, `total`, all in milliseconds measured with monotonic clocks. Unstarted work has null timing; measured zero is valid. Total starts at HTTP receipt and includes reading, validation, waiting and cleanup. |
| B8 | `errors` | Typed closed error details. Empty only on complete results; nonempty on partial and failed results. |
| B9 | `window_details` | Present exactly when requested and controls were resolved. Contains ordered `primary` and nullable `full` arrays of completed windows only. Each window has `index`, `start_word`, `end_word`, `score`; positions are zero-based, end-exclusive whitespace-word indices. No text. |

Complete requires every requested comparison, measured total timing and
successful terminal logging. A comparison's score requires every planned
window to finish; an unfinished maximum is not a score. Partial preserves a
completed primary score when another required operation fails. Failed has no
completed primary score.

Disabled full comparison has no full counts, score, delta, details or timing.
Identical-source reuse reports the full logical plan with zero additional
scored windows, the primary score, mirrored details and null full timing.
The parent compares the original strings exactly, validates each worker reply,
and reduces only completed comparisons.

Table C - Loaded model and owned worker identities

| Id | Shape | Fields |
| --- | --- | --- |
| C1 | Model | `reference`, `configured_revision`, `loaded_revision`, `foundation_reference`, `foundation_revision`, `loaded_weights_sha256`, `loaded_config_sha256`, `service_config_sha256`, `runtime_versions`. Revisions are full lowercase commit IDs; hashes are lowercase SHA-256 digests. Runtime versions name `python`, `pytorch`, `transformers`. These fields describe actual loaded tensors/configuration, not model labels. Contract examples are not load evidence. |
| C2 | Worker | Positive `generation` and `pid`, nullable decimal-string `start_ticks`, nullable `pin_unavailable_reason`. The process is the owned scorer, not HTTP. A pin and unavailable reason are mutually exclusive; one is required. Replacements advance generation. |
| C3 | Unavailable pin | `unsupported_platform`, `process_not_found`, `process_read_failed`, `process_identity_invalid`, `process_identity_too_large`. No exception text or invented start tick. |

`ServiceHealth` requires `version`, `service_instance_id`, `status`, nullable
`worker` and `model`, `queue_depth`, `queue_capacity`, nullable `failure_code`.
Status is `disabled`, `loading`, `ready`, `replacing`, `stopping` or `failed`.
Only ready maps to HTTP 200; it requires model and worker identities without
failure. Other states map to 503. Queue depth cannot exceed capacity; failed
health requires a closed failure code. No completed results are retained.

## Safe errors

`ErrorDetail` contains `code`, `phase`, nullable `field`, nullable `window_index`
and a fixed `message`. Phase is the operation vocabulary in Table E. A field
is a declared request or worker/model/window contract path, never a caller's
unknown property name. `project_request_error` discards raw validation
messages, values and unknown names. Do not return or log a raw validation
exception. The native error policy owns each fixed message.

Table D - Closed error codes and response policy

| Id | Codes | HTTP status and meaning |
| --- | --- | --- |
| D1 | `INVALID_JSON`, `INVALID_REQUEST`, `WINDOW_LIMIT_EXCEEDED` | 400: malformed or invalid request, controls or window plan. |
| D2 | `ORIGIN_FORBIDDEN`, `HOST_FORBIDDEN` | 403: browser origin or host refused. |
| D3 | `INPUT_TIMEOUT` | 408: input-read deadline expired. |
| D4 | `BODY_TOO_LARGE` | 413: configured input byte allowance exceeded. |
| D5 | `UNSUPPORTED_MEDIA` | 415: unsupported media type or encoding. |
| D6 | `QUEUE_FULL` | 429: no waiting reservation; include configured `Retry-After`. |
| D7 | `QUEUE_TIMEOUT`, `SERVICE_DISABLED`, `SERVICE_STOPPED`, `WORKER_NOT_READY` | 503: service unavailable or queue wait expired. Queue expiry includes configured `Retry-After`. |
| D8 | `EVALUATION_TIMEOUT` | 504: the combined evaluation deadline expired. |
| D9 | `MODEL_LOAD_FAILED`, `MODEL_IDENTITY_CHANGED`, `MODEL_SCORING_FAILED`, `INVALID_MODEL_OUTPUT`, `WORKER_EXITED`, `WORKER_PROTOCOL_FAILED`, `WORKER_STOP_FAILED`, `LOGGING_FAILED`, `INTERNAL_ERROR` | 500: model, process, protocol, logging or internal failure. |
| D10 | `CLIENT_DISCONNECTED` | Terminal event only; do not construct an HTTP result. |

Errors may carry a partial result. Terminal logging failure requires
`LOGGING_FAILED`, an error HTTP status and null `terminal_event_id`, even when
scoring completed.

## Events and private worker packets

Table E - Strict event fields

| Id | Fields | Contract |
| --- | --- | --- |
| E1 | `version`, `event_id`, `execution_id`, `sequence` | Current version, deterministic UUIDv5, execution UUIDv4 and positive integer sequence. The event reader recomputes and checks the event ID. |
| E2 | `request_id`, `correlation_id`, `caused_by_event_id` | Nullable caller UUIDv4 values and nullable causal UUIDv5. Root request/service starts have no cause. Queue and comparison events require their actual initiating event; the runtime emitter owns ordering and terminalization. An event cannot cause itself. |
| E3 | `run_id`, `pipeline_name`, `task_name` | Nullable operator startup context, not HTTP extensions or scoring settings. Each non-null identity is one to 128 ASCII letters/digits/dots/underscores/hyphens, beginning with a letter or digit. Context never comes from either text. |
| E4 | `operation_id`, `operation`, `phase` | Operation UUIDv4 retained across phases; operation is `service`, `worker`, `request`, `queue`, `primary`, `full`; phase is `started`, `completed`, `failed`, `cancelled`. |
| E5 | `occurred_at`, `level` | A timezone-aware UTC emission instant; level is `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| E6 | `details` | One strict model with omittable typed `status`, `worker`, `model`, `window_index`, `window_count`, `scored_window_count`, `queue_depth`, `duration_ms`, `score`, `errors`. Include only measured fields, not explicit null or an arbitrary diagnostic dictionary. Counts must agree. |

`encode_json_line` counts the complete UTF-8 JSONL record, including its
newline, against `logging.max_event_bytes` and refuses overflow without
truncation. The parent emitter writes these records to stderr through
standard-library logging and propagates write failures. No raw child stderr,
access logs, progress streams, exception representations or input bodies
belong in these events.

Table F - Private native packets

| Id | Kind | Fields and invariants |
| --- | --- | --- |
| F1 | `bootstrap` | `version`, `settings`, `assets`, `context`. Settings are validated and frozen; `assets.model` and `assets.foundation` must equal the configured immutable asset identities. Context is the separate typed startup context. No article text. |
| F2 | `worker_started` | `version`, `worker`. Reports ownership separately from loaded readiness. |
| F3 | `ready` | `version`, `worker`, `model`. Requires all loaded fingerprints. |
| F4 | `worker_failed` | `version`, `worker`, `error`. Requires a closed worker-phase startup error without a window; it is not incomplete readiness. |
| F5 | `score_window` | `version`, `execution_id`, `generation`, `comparison`, `window_index`, `start_word`, `end_word`, `source_text`, `summary_text`. Comparison is `primary` or `full`; the nonempty end-exclusive range must match the source window's word count. This is the only text-bearing outbound packet. |
| F6 | `window_scored`, `window_failed` | The same version/execution/generation/comparison/window/range identity, nullable finite `score`, nullable nonnegative `scoring_ms`, nullable closed `error`. Success requires a score without error; failure requires an error without score. Its error phase and window index must match. |

The native `WorkerCommand` and `WorkerReply` root models select packets by
`kind` without adding a JSON wrapper. They reject unknown kinds and unsupported
versions. `validate_window_reply` checks every command identity field. The
controller enforces one outstanding command, rejects duplicate and stale
replies, and uses bounded multiprocessing JSON byte pipes, not object pickle
messages or a broker.

## Authored startup settings

`config/hhem-evaluator/settings.json` supplies the API's operational values.
`load_settings` reads only its explicit path, validates it and returns frozen
nested models and immutable asset inventories. Missing or invalid settings
fail by name. There is no environment-selected model destination, source
fallback, remote lookup or live reload. A replacement must use the same
startup snapshot.

Table G - Initial settings and units

| Id | Keys | Authored values |
| --- | --- | --- |
| G1 | `enabled` | `false` during development. The field declares removal when the standalone API is released after real-model workflow verification. |
| G2 | `hhem.model`, `hhem.foundation` | Required references, full immutable revisions and finite named file lists in the committed settings. The model revision is `8e4a2e6e96c708cc76c2344f7e4757df2515292c`; the foundation revision is `7bcac572ce56db69c1ea7c8af255c5d7c9672fc2`. Foundation files are tokenizer/config assets, not another model's weights. |
| G3 | `hhem.cache_directory` | `services/hhem-evaluator/var/model-cache`, a relative POSIX operator path; never a request control. |
| G4 | `scoring.chunk_words`, `scoring.chunk_overlap_words`, `scoring.max_windows_per_comparison` | 900 words per window, 100 words of regular overlap and at most 256 planned windows per comparison. Reject a larger plan; never drop windows. |
| G5 | `response.hhem_full`, `response.include_window_details` | Both `false`; independent permanent optional API controls. |
| G6 | `listener.host`, `listener.port` | `127.0.0.1`, port 3010. Only configured loopback literals `127.0.0.1` and `::1` validate. |
| G7 | `listener.max_body_bytes`, `listener.body_read_timeout_ms` | 1048576 bytes (1 MiB) and 5000 milliseconds (five seconds) for bounded input reads. |
| G8 | `queue.capacity`, `queue.wait_timeout_ms`, `queue.retry_after_seconds` | Eight waiting reservations, 60000 milliseconds (one minute), two seconds. A body being read uses a reservation; the active evaluation is separate. |
| G9 | `evaluation.timeout_ms` | 120000 milliseconds (two minutes), shared across both comparisons after dequeue. |
| G10 | `worker.startup_timeout_ms`, `worker.replacement_timeout_ms` | 600000 milliseconds (ten minutes) initially; 120000 milliseconds (two minutes) for cached replacement. |
| G11 | `worker.stop_grace_ms`, `worker.forced_stop_ms`, `worker.shutdown_timeout_ms` | 5000 milliseconds (five seconds) each for graceful and forced-stop confirmation; 15000 milliseconds (fifteen seconds) for shutdown. Shutdown must accommodate both stop phases. |
| G12 | `worker.max_proc_identity_bytes`, `logging.level`, `logging.max_event_bytes` | 4096 bytes for one process identity read; `INFO`; 4096 serialized bytes per event. Bounds are refusal limits, not truncation instructions. |

CPU affinity, quotas, memory limits and fixed compute/inter-operation thread
counts are not settings. The host and runtime schedule all available CPU and
memory. One model process and serial evaluations constrain concurrent work,
not cores or threads; they do not promise full utilization.

## Installation boundary

The package has its own manifest, lock and CPython 3.12 version file. It has no
backend imports, backend installation dependency or root manifest change.
Pydantic supplies validation, FastAPI/OpenAPI and Uvicorn supply the HTTP
dependencies, and HTTPX supplies in-process transport and caller support.
Their cost is an independent Python dependency tree, not published-site bytes.
FastAPI stays in the 0.121 release family to avoid an unused default telemetry
API dependency.
Hatchling is build-only; Ruff, mypy, pytest and the socket-blocking pytest
plugin are development-only.

The optional `model` extra selects Transformers 4.57.6, CPU-index PyTorch
2.8.0, model-download library 0.36.0 and SentencePiece 0.2.1. It adds large CPU
wheels; actual inference also requires the named model assets. Ordinary
development and CI do not install this extra or download weights. Resolving
their package metadata alone is not evidence that the official model loads.

## Standalone command and captured evidence

Run `python -m hhem_evaluator` in the independent model environment. `--root`
names the repository root and `--settings` names its committed settings file;
both are required operator paths. `--enable` enables that invocation without
editing the development flag. The effective setting is included in the
service-configuration digest. There is one HTTP process, no reload or worker
count control, and no request-selected executable or destination.

`scripts/capture-model-recordings.py` uses that same production loader and
official predictor. The named `tests/fixtures/hhem-evaluator/model-inputs.json`
contains only project-authored fictional text. `model-predictions.json` stores
actual finite predictions, exact input hashes, a UTC capture instant and the
digest of `model-identity.json`. That identity records the actual loaded
tensors, configuration, tokenizer assets and runtimes.

The capture and cached-only reload demonstrate loading and prediction, not
factual-accuracy calibration or hosted-runner speed. Ordinary tests use these
recordings only at the model-call boundary; they do not install the model
extra, download weights or expose a production replay mode.

## Manual caller and report

`python -m hhem_evaluator.run_manual_evaluation --root <repository-root>`
owns one invocation of the existing API and the existing Bun host probe.
It reads only the platform's named dispatch event, sends one HTTP evaluation
with `hhem_full: false`, and writes only the body-free `report.json` and
`report.md` under `services/hhem-evaluator/var/workflow/`. Those two output
paths form the workflow's artifact allowlist, not a text-selected destination.
The [manual how-to](../how-to/run-hhem-evaluation-api.md) owns setup,
first registration, dispatch and failure inspection.

Table H - Manual caller controls

| Id | File and field | Value and meaning |
| --- | --- | --- |
| H1 | `config/hhem-evaluator/workflow.json`: `event_envelope_bytes` | 65536 bytes (64 KiB), added to the API's request allowance when reading the platform event. The encoded API request must still fit its own allowance. Overflow is refused, never truncated. |
| H2 | `max_response_bytes`, `control_max_bytes` | 2097152 bytes (2 MiB) per HTTP response; 16384 bytes (16 KiB) per private control line. |
| H3 | `http_connect_timeout_ms`, `poll_interval_ms` | 5000 milliseconds (five seconds) for connection; 100 milliseconds between readiness observations. Overall response deadlines derive from the API's body, queue, evaluation and shutdown bounds, or the native host lifecycle bound plus connection time. |
| H4 | `pipeline_name`, `task_name` | Committed ASCII run labels. Platform run identity and generated request/correlation UUIDs complete the metadata; neither text supplies a label. |
| H5 | `config/hhem-evaluator/host-probes.json` | Native Zod-owned host settings on loopback port 3011. Task profiling and process RAM are on; machine RAM and cache probes are off. The existing global host settings are unchanged. |

HTTPX disables proxy-environment use and redirects and bounds both time and
response bytes. Error-status evaluator responses still pass through
`EvaluationResult`; completed partial scores survive. Evaluation is never
automatically retried. Private startup identity plus matching HTTP health
proves the evaluator belongs to this caller. The host launcher announces
readiness only after its existing server binds.

`WorkflowReport` has the same initial native version and schema metadata as
the service. It is an output of one run, not authority for another run; there
is no old report shape to migrate. Unsupported versions fail validation.
It adds no shared schema, ledger family or production evaluator dependency.

Table I - Body-free workflow report

| Id | Field | Meaning |
| --- | --- | --- |
| I1 | `version`, `status` | Current wire version; `complete` requires a complete evaluation, complete resource evidence and no caller failures. `partial` retains a primary score with incomplete work or evidence; `failed` has no completed primary score. |
| I2 | `evaluation` | Nullable native `EvaluationResult`, including actual partial scores and terminal event identity. No second HHEM result schema. |
| I3 | `resources.status`, `resources.reason` | Coverage is `complete`, `incomplete` or `unavailable`. A non-complete result names `configured_off`, `pin_unavailable`, `profile_start_failed`, `profile_stop_failed`, `worker_replaced`, `profile_interrupted` or `measurement_unavailable`. |
| I4 | `resources.profile` | Nullable narrow projection of the native host profile: task identity, outcome, end reason, UTC endpoints, elapsed milliseconds, unavailable reasons and worker CPU/RAM summary. Raw samples, machine summaries and cache payloads are not copied. |
| I5 | `resources.initial_worker`, `resources.final_worker` | Nullable native scoring-worker identities. Complete coverage requires the same PID/start-tick pair and generation across an explicit uninterrupted profile stop. A replacement never retargets the existing handle. |
| I6 | `resources.runner`, `resources.shutdown` | Observed operating system, release, architecture and visible logical CPU count; separate stopped-child observations and nullable confirmation of model exit. These are conditions and lifetime evidence, not another CPU/RAM collector. |
| I7 | `errors` | Closed safe failures with `code`, `phase`, `service`, nullable `http_status` and fixed `message`. Cleanup phase stays separate from the original failure. Raw bodies, exceptions and input-derived names are forbidden. |

The host remains the field authority. The Python reader validates only the
consumed fields and discards unconsumed ones. The named Bun bridge compares
their type, requiredness, nullability and vocabulary with the actual native
schemas; missing runtime preparation fails instead of skipping the check.
The [host API](host-probe-api.md) and
[measurement reference](host-metrics.md#whole-task-typescript-samples) own
resource semantics and units. One-core CPU percent is not capped at 100.
Stored memory remains KiB; Markdown also shows MiB. Null readings require
their actual native reason. A missing final worker identity does not prove a
replacement; it leaves coverage incomplete.

The profile opens after model readiness and closes before worker shutdown,
excluding download/load time. Both launchers observe parent-pipe EOF.
Shutdown joins only owned children with declared bounded escalation. A
host-service close precedes API shutdown, so even an undelivered handle cannot
leave its collector observing a stopped worker. A
measurement or cleanup failure cannot erase a validated evaluation. An HTTP
or operational failure fails the workflow after available evidence is saved.

## Design rationale

The caller's control packets and native events use non-inheritable private
channels. Ordinary standard output and standard error can also be inherited
by model-library helper processes, so mixing them with the protocol can corrupt
an otherwise valid shutdown receipt. Raw runtime output stays discarded
through interpreter shutdown; only declared packets and native events reach
the caller.

A service PID exiting does not prove that its model worker stopped. The
receipt must explicitly confirm the supervisor's joined worker exit. A
validated confirmation remains in the report even if another cleanup action
fails; an unclean or unconfirmed shutdown still fails the workflow.

## See also

- [../how-to/run-the-gates.md#independent-python-service-contracts](../how-to/run-the-gates.md#independent-python-service-contracts) - preparation and model-free checks.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - native schema ownership.
- [../architecture/contracts/identity.md#6-hhem-execution-and-event-identity](../architecture/contracts/identity.md#6-hhem-execution-and-event-identity) - caller, execution and event identities.
- [repository-layout.md](repository-layout.md) - package, configuration and fixture locations.
- [../architecture/evaluation/hhem-evaluation-api.md](../architecture/evaluation/hhem-evaluation-api.md) - execution and failure ownership.
- [../how-to/run-hhem-evaluation-api.md](../how-to/run-hhem-evaluation-api.md) - manual dispatch, evidence and cleanup.
