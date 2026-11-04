# Shared local Python API

**Last Updated**: 2026-11-03

Which routes and startup settings the single FastAPI application exposes.
This is a local workflow service, not a backend for the published site.
The [architecture](../architecture/evaluation/local-model-api.md) explains
process ownership and failure handling.

## Configuration and routes

`config/fastapi-server.json` owns the listener, explicit component selection,
diagnostic settings and HTTP transport bounds. The frozen native models live
in `services/hhem-evaluator/src/hhem_evaluator/contracts/`. Shared settings,
health, llama data and CloudEvents schemas have version `2026-11-03`.
They are current-only: an old event envelope or old authored listener location
is rejected, not read through an alias.

Table A - Listener and component selection

| Id | Setting | Meaning |
| --- | --- | --- |
| A1 | `listener.host`, `listener.port` | Loopback `127.0.0.1`, port 3010. The host can also be the literal `::1`. |
| A2 | `listener.max_body_bytes` | At most 1048576 bytes, or 1 MiB, per input body. |
| A3 | `listener.body_read_timeout_ms` | An absolute input-read deadline of 5000 milliseconds, or five seconds. |
| A4 | `enabled_routes` | A distinct list drawn from `hhem` and `llama`. The development default is an empty list. Its declaring field names the removal condition. |
| A5 | `shutdown_timeout_ms` | 15000 milliseconds, or fifteen seconds, for forwarding-request shutdown and Uvicorn's graceful wait. When HHEM is enabled, this cannot be shorter than its worker shutdown wait. |

Table B - Native operations

| Id | Route | Meaning |
| --- | --- | --- |
| B1 | `GET /health` | Shared readiness, enabled components, the actual service instance and diagnostic-file availability. Every enabled component must be ready for HTTP 200; otherwise the response is HTTP 503. |
| B2 | `GET /api/2026-11-02/health` | HHEM's own observed worker/model state. It remains usable independently of llama health. Registered only with HHEM enabled. |
| B3 | `POST /api/2026-11-02/summary-eval-hhem` | The existing [native evaluation operation](hhem-evaluation-api.md). Registered only with HHEM enabled. There is no `/evaluate` alias. |
| B4 | `POST /v1/chat/completions` | Nonstreaming native llama generation. Registered only with llama enabled. |
| B5 | `GET /api/2026-11-02/openapi.json` | The application's current native schemas. There is no interactive documentation UI. |

Disabled operation routes return HTTP 404. Shared health explicitly reports
disabled components; it does not claim their models loaded. Browser origins,
duplicate or unexpected Host headers and slash redirects remain refused.

## Native llama forwarding

The only upstream operation is `/v1/chat/completions`. Its private origin comes
from the selected committed configuration's `model_server.base_url`, normally
`http://127.0.0.1:8080`. It must be an HTTP loopback origin with an explicit
nonzero port, without credentials, path, query or fragment. Its port must
differ from the shared listener's port.

The loader reads that named configuration and the one declaration named by
its `models_file`. It projects the declaration's
`summarizer.request_timeout_minutes` into the forwarding deadline. It does
not load weights, choose another declaration or duplicate a model selection
in the shared server configuration. The phase that starts native llama owns
full declaration validation, asset acquisition and the native process.

`LlamaRequest` requires a model string and nonempty text messages with the
roles `system`, `user` or `assistant`. Omitted `stream` means false; any supplied
value other than the boolean false is refused. Native JSON sampling, template
and response-format fields pass through without a per-parameter translation.
They cannot change the destination, route, HTTP method or forwarded headers.
The original validated request bytes are sent unchanged.

Valid native result and error JSON retain their exact response bytes and HTTP
status. Answer, reasoning, usage, timing and other native JSON fields are not
stripped. A length-limited result remains length-limited; extracting and
accepting the final summary is the caller's job. Redirects are not followed.
Invalid or oversized native responses and unreachable origins return explicit
HTTP 502 errors; an expired generation deadline returns HTTP 504. Local input
refusals use safe native error JSON rather than FastAPI validation dumps.

Table C - Transport settings

| Id | Setting | Meaning |
| --- | --- | --- |
| C1 | `llama.connect_timeout_ms` | 5000 milliseconds, or five seconds, to connect. |
| C2 | `llama.health_timeout_ms` | 5000 milliseconds, or five seconds, for one native health observation. |
| C3 | `llama.max_response_bytes` | At most 1048576 decoded bytes, or 1 MiB, per native response. Overflow is refused, not truncated. |
| C4 | `llama.max_inflight_requests` | One admitted generation request. Additional requests receive HTTP 429 before reading their bodies; there is no second queue or retry system. |

## Diagnostics

Standard Python logging sends accepted CloudEvents JSONL records to stderr
and an append-only file named
`fastapi-server_{yyyy_mm_dd}_{run_id}_{attempt}.log`. The date is UTC.
The workflow launcher supplies its platform run identifier and attempt; a local
invocation uses its invocation identity and attempt one. A caller can supply
the run's UTC start instant when creating `EventWriter`.

The default disposable directory is
`services/hhem-evaluator/var/server-logs`. The existing manual launcher uses
its current run-output directory. `logging.level` defaults to `INFO`;
`logging.max_event_bytes` bounds one serialized protocol record at 4096 bytes.
This is not a file-volume limit. There is no file quota, rotation worker or
log-volume-triggered shutdown.

Records contain startup, readiness and stop facts, safe warning/error codes
and the existing body-free HHEM operation data. The
[identity contract](../architecture/contracts/identity.md#6-hhem-execution-and-event-identity)
defines event identity. Prompts, request bodies, model answers, secrets and raw
exception messages are not diagnostic fields. Uvicorn access/error output is
disabled; private startup and process-exit packets stay on their own channel.

An unopenable or unwritable file emits `LOG_FILE_UNAVAILABLE` to stderr and
sets shared health's `log_available` to false. It does not change a score or
stop the API. Confirmed process exit and validated HTTP results establish
outcomes; a terminal log line is not scoring proof.

## See also

- [../architecture/evaluation/local-model-api.md](../architecture/evaluation/local-model-api.md) - composition and owned lifetimes.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - unchanged scoring requests, results and worker packets.
- [../concepts/config/model-file.md](../concepts/config/model-file.md) - selected model authority.
- [../how-to/run-the-gates.md#independent-python-service-contracts](../how-to/run-the-gates.md#independent-python-service-contracts) - focused offline checks.
