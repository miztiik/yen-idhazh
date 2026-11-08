# Summary evaluator API

**Last Updated**: 2026-11-08

Which routes and startup settings each selected `summary-evaluator` process exposes.
This is a local workflow service, not a backend for the published site.
The [architecture](../architecture/evaluation/summary-evaluator.md) explains
process ownership and failure handling.

## Configuration and routes

`config/summary-evals/api.json` owns the per-scorer listeners,
diagnostic settings and request-body bounds. The frozen native models live
in `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/`
and `shared/contracts/`. The reusable listener contract lives in
`services/local_api_host/src/local_api_host/contracts.py`; the evaluator
projects its committed settings into that contract with trace propagation
disabled, so evaluator responses and newly emitted events remain untraced.
Shared settings, health and generic API errors retain version `2026-11-07`.
The native CloudEvents envelope schema has version `2026-11-08` and declares
reader-optional W3C carriers; it adds no payload `version` field and retains
`specversion: "1.0"`. Live health and errors use their current shapes. Deployment
readers also accept frozen `2026-11-07` three-listener and single-listener
settings, but resolve only one maintained scorer. Saved workflow evidence may
read the exact previous health shape only with disabled coverage, then remove
that slot without inventing process observations. Mixed formats, arbitrary
extras, invalid bounds, listener collisions and unknown versions are rejected.
Historical logs retain coverage diagnostics; no records are rewritten.
HHEM score/event data retains `2026-11-02`; native UniEval score/recording data
retains `2026-11-04`.

Table A - Listener and component selection

| Id | Setting | Meaning |
| --- | --- | --- |
| A1 | `listeners.<scorer>.host`, `listeners.<scorer>.port` | Each `hhem` and `unieval` entry has a distinct binding. Defaults are loopback `127.0.0.1`: HHEM retains port 3010 and UniEval uses 3011. The host can also be the literal `::1`. |
| A2 | `listeners.<scorer>.max_body_bytes` | At most 1048576 bytes, or 1 MiB, per input body by default. Each caller uses its intended scorer's bound. |
| A3 | `listeners.<scorer>.body_read_timeout_ms` | An absolute input-read deadline of 5000 milliseconds, or five seconds, by default. |
| A4 | `--routes <scorer>` | Resolve exactly one maintained scorer. The comparison workflow starts separate HHEM and UniEval APIs. No modern default starts every configured listener; coverage selection is refused. |
| A5 | `shutdown_timeout_ms` | 15000 milliseconds, or fifteen seconds, for Uvicorn's graceful request wait. This cannot be shorter than the selected scorer's worker shutdown wait. The owned parent-loss/close allowance also includes that worker's shutdown and forced-stop joins. |

Table B - Native operations

| Id | Route | Meaning |
| --- | --- | --- |
| B1 | `GET /api/2026-11-05/get-summary-evaluator-health` | This API's selected scorer, actual service instance and diagnostic-file availability. The selected scorer must be ready for HTTP 200; otherwise the response is HTTP 503. Other scorer slots are disabled. |
| B2 | `GET /api/2026-11-05/get-hhem-health` | HHEM's own observed worker/model state, independent of UniEval. Registered only with HHEM enabled. |
| B3 | `POST /api/2026-11-05/evaluate-summary-hhem` | The unchanged [native evaluation operation](hhem-evaluation-api.md). Registered only with HHEM enabled. |
| B4 | `GET /api/2026-11-05/get-summary-evaluator-schema` | The application's current native schemas. Always registered, without an interactive documentation UI. |
| B5 | `POST /api/2026-11-05/evaluate-summary-unieval` | The [four-score UniEval operation](unieval-api.md), with an independent reference summary. |
| B6 | `GET /api/2026-11-05/get-unieval-health` | UniEval's observed model/worker/queue state, independent of HHEM. Registered only with UniEval enabled. |

Disabled operation routes return HTTP 404. Shared health explicitly reports
disabled scorers; it does not claim their models loaded. Browser origins,
duplicate or unexpected Host headers and slash redirects remain refused.
The neutral host performs the authority check, while evaluator callbacks retain
the exact native and generic refusal bodies below.

Each standalone invocation requires only its selected evaluator's prepared assets. HHEM-only
startup reads no UniEval configuration; UniEval-only startup reads no HHEM
configuration.
Disabled scorers construct no controller or worker and read no resources.
No scorer calls generation or another scorer.

The [routing convention](api-routing.md) separates the fixed HTTP date from
payload schema dates. The retired coverage evaluation/health routes, old dated evaluator paths,
`/health` and the former
`/v1/chat/completions` proxy return HTTP 404. The native generation server
keeps its own upstream paths; it is not part of this application.
Omitting `--routes` is accepted only when a legacy authored `enabled_routes`
already declares exactly one scorer. Empty or multiple selections fail safely.
Previous explicit selection keeps its original maintained listener and bounds;
a caller starting multiple APIs must use distinct authored listeners.
The previous three-listener shape must include every valid, distinct binding,
including the retired binding, before projection. No reader derives ports,
accepts active coverage health or tries compatibility after invalid input.
An omitted `--settings` uses the named HHEM default only when HHEM is enabled.
The launcher refuses `--routes llama` and the removed `--model-config`
option. Authored `llama` transport settings and retired coverage selections
are refused, not ignored.

## Safe local refusals

HHEM and native UniEval retain their own result/error envelopes.
Host/Origin refusals for health, schema and unknown routes instead use
`serve_http/contracts/error_detail.py` and `serve_http/refuse_request.py`:

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
`fastapi-server_{scorer}_{yyyy_mm_dd}_{run_id}_{attempt}.log`. The date is UTC.
The workflow launcher supplies its platform run identifier and attempt; a local
invocation uses its invocation identity and attempt one. A caller can supply
the run's UTC start instant when creating `EventWriter`.

The default disposable directory is
`services/summary_evaluator/var/server-logs`. The existing manual launcher uses
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

Saved envelopes may carry validated `traceparent` and `tracestate` extensions.
The reader preserves their native occurrence, UTC time, ordered data and
carrier; real legacy absence stays omitted. The identity contract owns the
[strict read rules](../architecture/contracts/identity.md#6-hhem-execution-and-event-identity).
Historical coverage diagnostics remain readable without enabling coverage.
This reader support does not inject live carriers or change scorer responses.

An unopenable or unwritable file emits `LOG_FILE_UNAVAILABLE` to stderr and
sets shared health's `log_available` to false. It does not change a score or
stop the API. Confirmed process exit and validated HTTP results establish
outcomes; a terminal log line is not scoring proof.

The standalone launcher also checks the actual Uvicorn lifespan outcome.
A failed startup or shutdown exits nonzero even when Uvicorn's `run()`
returns normally. Its bound socket and diagnostic file still close.

## See also

- [../architecture/local-api-host.md](../architecture/local-api-host.md) -
  reusable listener, lifecycle and request-boundary contract.
- [../architecture/evaluation/summary-evaluator.md](../architecture/evaluation/summary-evaluator.md) - composition and owned lifetimes.
- [api-routing.md](api-routing.md) - dated operations and the native generation exception.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - unchanged scoring requests, results and worker packets.
- [unieval-api.md](unieval-api.md) - independent full-source evaluation and four-score results.
- [../how-to/run-the-gates.md#independent-python-service-contracts](../how-to/run-the-gates.md#independent-python-service-contracts) - focused offline checks.
