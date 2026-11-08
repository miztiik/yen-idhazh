# How independent Python APIs serve summary evaluation

**Last Updated**: 2026-11-08

How each `summary-evaluator` process serves one selected evaluation method
with its own listener, queue and model worker. Exact routes, settings and diagnostics
live in the [server reference](../../reference/summary-evaluator-api.md).

## Explicit composition

Each Uvicorn process binds its scorer's committed loopback listener before model
startup. HHEM and UniEval use separate API processes, not only
separate workers behind one address. Stopping one API does not stop another API
or its model worker. The neutral
[local Python API host](../local-api-host.md) owns the listener, FastAPI lifespan,
request guard, health route and exact Uvicorn exit. A fixed evaluator
registration list binds each declared scorer to its module's
`create_api_component` adapter. The evaluator folds the enabled registrations
into one aggregate component before calling the neutral host; setup still runs
only for the selected scorer and includes only its native FastAPI router.
Each scorer's router delegates to its own evaluation controller. Neither
scorer generates a summary, calls the other scorer or chooses a model from
request text. The listener has no generation router, forwarder, upstream
health polling or generation-client lifespan.

An adapter owns its settings validation, controller construction, startup,
shutdown, native health observation and refusal of unsafe Host/Origin headers.
The evaluator extension of the neutral component interface carries those typed
callbacks, the native router, worker observations and an opaque controller for
existing private app-state callers. The evaluator adapter supplies validated
listener/logging bounds, closed event writers and one service instance identity;
the neutral host contains no scorer-specific construction, health, admission or
start/stop branch. HHEM and UniEval retain their existing
private state aliases; each selected controller shares its own API instance identity.
Typed callbacks also expose the selected worker's configured bounds and observed exit,
without making the host inspect an opaque controller. Diagnostic callbacks use the same
declared CloudEvents envelopes, not a new per-API logging implementation.
One actual service operation is created before logger and controller
construction and supplied to the neutral host. Each controller and model-load
operation belongs to that service branch. The validated API flag enables
receiving and response carriers; a scorer consumes the operation already
stored by the host rather than extract another parent.

Adding an API means its implementation adapter plus one deliberate registration
entry. Its configuration and public component vocabulary, native request/result
and health declarations, diagnostics, tests and owning documentation must also
be supplied as needed. Registration must match the declared component
vocabulary; it cannot bypass payload validation or invent a new public health
field. The CLI's accepted route choices come from that same declaration.
There is no directory scan, request-selected import or live discovery,
and adding an API requires no new shared lifecycle or request-guard branch.
The existing `create_app` arguments remain compatible; scorer-specific
snapshot overrides are private caller inputs, not another execution path.

The HHEM scoring controller, queue, recorded-output validation and owned
worker remain [separate from app construction](hhem-evaluation-api.md).
The serving package resolves the explicitly selected committed listener and supplies logging
and component selection to each scorer's reader. HHEM validates its existing
frozen private-worker snapshot. Old authored copies of `enabled`,
`listener` and `logging` are rejected, not used as competing authorities.
The scoring wire contract does not change merely because its configuration
is assembled from two named files.
With HHEM disabled, no scoring controller or worker is constructed, and the
shared entry point does not read HHEM's settings.

UniEval has its own explicit router, frozen settings, finite queue and owned
model process. Its [four-score calculation](unieval-api.md) is not an
HHEM window rule or a generic evaluator plugin. Disabled UniEval neither
loads its optional dependencies nor reads its configuration. Enabled
components retain separate observed health and completed results.

The workflow calls the separate native generation server directly and owns
its acquisition, launch, readiness and exit. The evaluation application does
not read generation configuration or depend on that process.

The installed package is `summary_evaluator` under
`services/summary_evaluator/src/`. `serve_http` assembles requests and logs;
`hhem` and `unieval` retain their independent scoring and worker policies.
`shared` provides strict primitives, bounded transport, queue mechanics and
process identity, plus the evaluator-specific worker extension of the neutral
component interface. It imports no scorer or serving package. Each scorer maps a
shared code-only failure to its existing public error. Event writers are
closed functions supplied by the serving package, not scorer imports of it.

## Real readiness and independent work

Application health reports the exact application instance, the selected scorer's state
and diagnostic-file availability. HHEM readiness still requires its observed
model and owned worker identities; UniEval reports its own observed model and
worker. No generation observation appears in evaluator health or OpenAPI.

An independent API reports readiness only for its selected scorer; other scorer
slots are explicitly disabled. The caller validates its startup nonce, actual API
PID/start pin, application instance and native worker/model identity. A failed API
or readiness wait does not cancel a sibling's request or erase its completed result.
Generic in-memory composition still supports an empty selection for health/schema
boundaries, but a real scorer launcher must resolve exactly one scorer.

Enabled scorers perform heavy work in their own model processes, not on the HTTP
event loop. Every enabled adapter starts its controller in the application
lifespan, so model loading begins at service startup, not on the first request.
Each finite queue reserves capacity before body reading.
Host/Origin checks, bounded input reads, disconnect handling and absolute
input, queue and evaluation deadlines remain in the actual scoring path.
The shared guard selects an enabled adapter's refusal callback by its native
operation path. That callback uses the same dispatcher and native error shape
as ordinary admission; disabled or unknown paths use the generic refusal.
Generic operational and unknown-route refusals use the independent
`serve_http/refuse_request.py` renderer and declared `serve_http/contracts/error_detail.py` shape.

## Owned shutdown and diagnostics

The application lifespan closes its selected scorer through its existing
worker controller. Disconnect cancels admitted scoring work and follows its
bounded owned-child retirement policy. There is no generation client to
close and no invented generation shutdown outcome.

Enabled component cleanups run concurrently, each within its declared wait,
so adding another independent worker does not add their shutdown waits.
Every cleanup still runs when another fails. A single failure
keeps its native exception type; multiple original and cleanup failures are
retained separately in the raised group.
HHEM's existing parent-loss watcher, bounded worker replacement and confirmed
exit rules are unchanged. Each owned API also observes its private parent pipe,
with a bounded whole-lifespan deadline. Its private stopped packet reports only
its own worker's actual exit. API owners are closed independently; the workflow
retains original and cleanup causes separately. The TypeScript machine-measurement
channel remains unchanged.
Each attempt retains its own receiving context through queue promotion,
cancellation and interleaved progress. Current private worker packets carry
the issued load or evaluation operation and require exact reply equality.
Their date stamps are independent of public scoring and recording versions.

Standard logging formats validated native data as CloudEvents JSONL. The
same accepted records reach stderr and the role's named file. A failed file
mirror warns safely and records that the log is unavailable; it does not
invalidate completed model work. Validated HTTP results and actual process
receipts, not a search through terminal output, establish success.
Request-caused file-mirror warnings retain the causing operation; opening
and closing warnings use the service operation. Invalid optional carrier
metadata produces a fixed diagnostic without exposing header or parser text.

## Design rationale

Separate API processes remove the shared restart boundary without duplicating
application construction or scoring behavior. Committed listener settings make
each destination reviewable, while the existing native adapters retain model loading
at startup, bounded queues, cancellation and worker retirement. Legacy single-listener
settings are usable only for an unambiguous single-scorer invocation; multiple-server
callers require the explicit listener table rather than invented ports.
The current table declares only HHEM and UniEval. A frozen previous
three-listener declaration remains a read-only input: all authored bindings
must validate before only the selected maintained listener is resolved.
Coverage selection is refused, not redirected to generation or another scorer.
Saved health may project the previous disabled coverage slot only after full
validation; the original shared or independent process observations stay intact.
Historical CloudEvents coverage diagnostics retain their separate vocabulary.

The retired retrieval and upstream converter were the sole consumers of
`rank-bm25` and `prettytable`; neither remains in the frozen environment.
Native UniEval uses its own model, tokenizer and sentence resources directly.
Their dependencies and native calculations remain unchanged.

Keeping a dormant generation proxy would retain another API's transport,
configuration and failure surface without enabling evaluation. The existing
workflow already speaks the native protocol directly. A fixed registration list
keeps every integration visible without a plugin framework or another worker
implementation. The neutral host owns reusable orchestration while the
evaluator composite and scorer adapters own all native HTTP behavior; this
prevents a new router from silently missing
health, safe refusal or cleanup integration. HTTPX remains in the
frozen environment for resource preparation and offline ASGI boundaries.
Scoring snapshots, model identities, event seeds and recordings are unchanged.
The package split changes ownership, not those wire identities. Existing
native schema metadata remains inherited from its neutral primitive base.
Explicit operation values preserve existing UUID occurrence and causal-link
rules while supplying real HTTP and process continuity. Reader optionality
retains genuinely absent old carriers; enabled live writers still require
their actual operation. A saved event is validated and preserved, never
recreated by a live factory.
The old model-free environment and stopped-service caches are not moved or
deleted. New preparation reads only the configured cache and log paths.

## See also

- [../local-api-host.md](../local-api-host.md) - neutral listener, lifecycle,
  request guard and trace ownership.
- [../../reference/summary-evaluator-api.md](../../reference/summary-evaluator-api.md) - shared API contract and settings.
- [../../reference/api-routing.md](../../reference/api-routing.md) - dated first-party routes and the upstream native-protocol exception.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring and cancellation.
- [unieval-api.md](unieval-api.md) - independent UniEval scoring and source coverage.
- [../../reference/summary-evaluation-workflow.md](../../reference/summary-evaluation-workflow.md) - current caller and machine control.
- [../../how-to/run-the-gates.md#independent-python-service-contracts](../../how-to/run-the-gates.md#independent-python-service-contracts) - offline composition checks.
