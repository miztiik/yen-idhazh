# How one Python API serves summary evaluation

**Last Updated**: 2026-11-06

How the shared `summary-evaluator` application serves HHEM and native UniEval
with independent queues and model workers. Exact routes, settings and diagnostics
live in the [server reference](../../reference/fastapi-server.md).

## Explicit composition

One Uvicorn process binds the configured loopback listener before model
startup. The application registers only its explicitly enabled routers.
Each scorer's router delegates to its own evaluation controller. Neither
scorer generates a summary, calls the other scorer or chooses a model from
request text. The listener has no generation router, forwarder, upstream
health polling or generation-client lifespan.

The HHEM scoring controller, queue, recorded-output validation and owned
worker remain [separate from app construction](hhem-evaluation-api.md).
The shared configuration supplies listener, logging and component selection;
`load_settings` combines it with HHEM's named scoring configuration into the
existing frozen private-worker snapshot. Old authored copies of `enabled`,
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

## Real readiness and independent work

Shared health reports the exact application instance, both scorer states
and diagnostic-file availability. HHEM readiness still requires its observed
model and owned worker identities; UniEval reports its own observed model and
worker. No generation observation appears in evaluator health or OpenAPI.

Aggregate readiness requires every enabled scorer. A failed scorer does not
erase its sibling's readiness or completed result. An empty selection exposes
only application health and schema and constructs no model worker.

Both scorers perform heavy work in their own model processes, not on the HTTP
event loop. Each finite queue reserves capacity before body reading.
Host/Origin checks, bounded input reads, disconnect handling and absolute
input, queue and evaluation deadlines remain in the actual scoring path.
Generic operational and unknown-route refusals use the independent
`refuse_request.py` renderer and declared `api_error_detail.py` shape.

## Owned shutdown and diagnostics

The application lifespan closes each enabled scorer through its existing
worker controller. Disconnect cancels admitted scoring work and follows its
bounded owned-child retirement policy. There is no generation client to
close and no invented generation shutdown outcome.

Enabled component cleanups run concurrently, each within its declared wait,
so adding another independent worker does not add their shutdown waits.
Every cleanup still runs when another fails. A single failure
keeps its native exception type; multiple original and cleanup failures are
retained separately in the raised group.
HHEM's existing parent-loss watcher, bounded worker replacement and confirmed
exit rules are unchanged. The current workflow's private control and
TypeScript machine-measurement channels are unchanged.

Standard logging formats validated native data as CloudEvents JSONL. The
same accepted records reach stderr and the role's named file. A failed file
mirror warns safely and records that the log is unavailable; it does not
invalidate completed model work. Validated HTTP results and actual process
receipts, not a search through terminal output, establish success.

## Design rationale

One evaluation address serves related scoring operations while separate
workers and queues retain their independent work. Separate HTTP deployments
would add another listener and lifecycle; the shared HTTP process remains a
common restart boundary.

Keeping a dormant generation proxy would retain another API's transport,
configuration and failure surface without enabling evaluation. The existing
workflow already speaks the native protocol directly. Explicit scorer routers
need no plugin registry or generic worker framework. HTTPX remains in the
frozen environment for resource preparation and offline ASGI boundaries.
Scoring snapshots, model identities, event seeds and recordings are unchanged.

## See also

- [../../reference/fastapi-server.md](../../reference/fastapi-server.md) - shared API contract and settings.
- [../../reference/api-routing.md](../../reference/api-routing.md) - dated first-party routes and the upstream native-protocol exception.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring and cancellation.
- [unieval-api.md](unieval-api.md) - independent UniEval scoring and source coverage.
- [../../reference/summary-evaluation-workflow.md](../../reference/summary-evaluation-workflow.md) - current caller and machine control.
- [../../how-to/run-the-gates.md#independent-python-service-contracts](../../how-to/run-the-gates.md#independent-python-service-contracts) - offline composition checks.
