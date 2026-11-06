# Summary evaluator API

**Last Updated**: 2026-11-06

Which routes and startup settings the single `summary-evaluator` application exposes.
This is a local workflow service, not a backend for the published site.
The [architecture](../architecture/evaluation/local-model-api.md) explains
process ownership and failure handling.

## Configuration and routes

`config/fastapi-server.json` owns the listener, explicit component selection,
diagnostic settings and request-body bounds. The frozen native models live
in `services/hhem-evaluator/src/hhem_evaluator/contracts/`. Shared settings,
health, generic API errors and CloudEvents schemas have version `2026-11-06`.
They are current-only: previous application versions and retired generation
settings are rejected, not read through aliases. Historical logs and model
recordings remain unchanged. HHEM and native UniEval scoring schemas retain
their own versions.

Table A - Listener and component selection

| Id | Setting | Meaning |
| --- | --- | --- |
| A1 | `listener.host`, `listener.port` | Loopback `127.0.0.1`, port 3010. The host can also be the literal `::1`. |
| A2 | `listener.max_body_bytes` | At most 1048576 bytes, or 1 MiB, per input body. |
| A3 | `listener.body_read_timeout_ms` | An absolute input-read deadline of 5000 milliseconds, or five seconds. |
| A4 | `enabled_routes` | A distinct list drawn from `hhem` and `unieval`; both are enabled by default. Each task selects only its required scorers. An empty list disables both scoring operations. |
| A5 | `shutdown_timeout_ms` | 15000 milliseconds, or fifteen seconds, for Uvicorn's graceful wait. This cannot be shorter than an enabled scorer's worker shutdown wait. Enabled worker cleanups run concurrently. |

Table B - Native operations

| Id | Route | Meaning |
| --- | --- | --- |
| B1 | `GET /api/2026-11-05/get-summary-evaluator-health` | Shared readiness, enabled scorers, the actual service instance and diagnostic-file availability. Every enabled scorer must be ready for HTTP 200; otherwise the response is HTTP 503. |
| B2 | `GET /api/2026-11-05/get-hhem-health` | HHEM's own observed worker/model state, independent of UniEval. Registered only with HHEM enabled. |
| B3 | `POST /api/2026-11-05/evaluate-summary-hhem` | The unchanged [native evaluation operation](hhem-evaluation-api.md). Registered only with HHEM enabled. |
| B4 | `GET /api/2026-11-05/get-summary-evaluator-schema` | The application's current native schemas. Always registered, without an interactive documentation UI. |
| B5 | `POST /api/2026-11-05/evaluate-summary-unieval` | The [four-score UniEval operation](unieval-api.md), with an independent reference summary. |
| B6 | `GET /api/2026-11-05/get-unieval-health` | UniEval's observed model/worker/queue state, independent of HHEM. Registered only with UniEval enabled. |

Disabled operation routes return HTTP 404. Shared health explicitly reports
disabled scorers; it does not claim their models loaded. Browser origins,
duplicate or unexpected Host headers and slash redirects remain refused.

The standalone default requires only prepared evaluator assets. HHEM-only
startup reads no UniEval configuration; UniEval-only startup reads no HHEM
configuration. Disabled scorers construct no controller or worker and import
no optional model libraries. Neither scorer calls generation or its sibling.

The [routing convention](api-routing.md) separates the fixed HTTP date from
payload schema dates. The old dated evaluator paths, `/health` and the former
`/v1/chat/completions` proxy return HTTP 404. The native generation server
keeps its own upstream paths; it is not part of this application.
The launcher refuses `--routes llama` and the removed `--model-config`
option. Authored `llama` transport settings are refused, not ignored.

## Safe local refusals

Scoring routes retain their own native result/error envelopes.
Host/Origin refusals for health, schema and unknown routes instead use
`contracts/api_error_detail.py` and `refuse_request.py`:

```json
{"error":{"code":"HOST_FORBIDDEN","message":"The request Host header is not accepted.","type":"api_error"}}
```

The message comes from the declared local error policy, never request input
or a raw exception. The guard runs before body reading. Bounded reads,
disconnect handling, absolute deadlines and real cleanup failures remain
part of the enabled scorers' request path.

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

The standalone launcher also checks the actual Uvicorn lifespan outcome.
A failed startup or shutdown exits nonzero even when Uvicorn's `run()`
returns normally. Its bound socket and diagnostic file still close.

## See also

- [../architecture/evaluation/local-model-api.md](../architecture/evaluation/local-model-api.md) - composition and owned lifetimes.
- [api-routing.md](api-routing.md) - dated operations and the native generation exception.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - unchanged scoring requests, results and worker packets.
- [unieval-api.md](unieval-api.md) - independent full-source evaluation and four-score results.
- [../how-to/run-the-gates.md#independent-python-service-contracts](../how-to/run-the-gates.md#independent-python-service-contracts) - focused offline checks.
