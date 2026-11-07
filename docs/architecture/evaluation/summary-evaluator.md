# How one Python API serves summary evaluation

**Last Updated**: 2026-11-07

How the shared `summary-evaluator` application serves independent evaluation methods
with independent queues and model workers. Exact routes, settings and diagnostics
live in the [server reference](../../reference/summary-evaluator-api.md).

## Explicit composition

One Uvicorn process binds the configured loopback listener before model
startup. The application registers only its explicitly enabled routers.
Each scorer's router delegates to its own evaluation controller. Neither
scorer generates a summary, calls the other scorer or chooses a model from
request text. The listener has no generation router, forwarder, upstream
health polling or generation-client lifespan.

The HHEM scoring controller, queue, recorded-output validation and owned
worker remain [separate from app construction](hhem-evaluation-api.md).
The serving package reads shared configuration and supplies listener, logging
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

Source coverage is an explicitly selected third method with its own bounded
queue and owned model process. Its [legacy retrieval calculation](source-coverage.md)
is not native UniEval's independent-reference relevance. The default remains
HHEM plus native UniEval; disabled coverage reads no configuration/resources and
constructs no worker. Enabling it adds resident model memory rather than sharing
a native scorer's model.

The workflow calls the separate native generation server directly and owns
its acquisition, launch, readiness and exit. The evaluation application does
not read generation configuration or depend on that process.

The installed package is `summary_evaluator` under
`services/summary_evaluator/src/`. `serve_http` assembles requests and logs;
`hhem`, `unieval` and `source_coverage` retain their independent scoring and worker policies.
`shared` provides strict primitives, bounded transport, queue mechanics and
process identity. It imports no scorer or serving package. Each scorer maps a
shared code-only failure to its existing public error. Event writers are
closed functions supplied by the serving package, not scorer imports of it.

## Real readiness and independent work

Shared health reports the exact application instance, each scorer's state
and diagnostic-file availability. HHEM readiness still requires its observed
model and owned worker identities; UniEval reports its own observed model and
worker. No generation observation appears in evaluator health or OpenAPI.

Aggregate readiness requires every enabled scorer. A failed scorer does not
erase its sibling's readiness or completed result. An empty selection exposes
only application health and schema and constructs no model worker.

Enabled scorers perform heavy work in their own model processes, not on the HTTP
event loop. Each finite queue reserves capacity before body reading.
Host/Origin checks, bounded input reads, disconnect handling and absolute
input, queue and evaluation deadlines remain in the actual scoring path.
Generic operational and unknown-route refusals use the independent
`serve_http/refuse_request.py` renderer and declared `serve_http/contracts/error_detail.py` shape.

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

Coverage returns one complete metric payload or a fixed safe error. Native
batches are validated before reduction; missing or nonfinite output does not
become zero or partial success. A failed coverage child does not erase completed
native scorer work. The caller retains its report/completion event, while the
API collects no machine readings and writes no duplicate evaluation-event file.

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
The package split changes ownership, not those wire identities. Existing
native schema metadata remains inherited from its neutral primitive base.
The old model-free environment and stopped-service caches are not moved or
deleted. New preparation reads only the configured cache and log paths.

## See also

- [../../reference/summary-evaluator-api.md](../../reference/summary-evaluator-api.md) - shared API contract and settings.
- [../../reference/api-routing.md](../../reference/api-routing.md) - dated first-party routes and the upstream native-protocol exception.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring and cancellation.
- [unieval-api.md](unieval-api.md) - independent UniEval scoring and source coverage.
- [source-coverage.md](source-coverage.md) - distinct legacy retrieval and complete-result boundary.
- [../../reference/summary-evaluation-workflow.md](../../reference/summary-evaluation-workflow.md) - current caller and machine control.
- [../../how-to/run-the-gates.md#independent-python-service-contracts](../../how-to/run-the-gates.md#independent-python-service-contracts) - offline composition checks.
