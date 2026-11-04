# How one Python API serves local model operations

**Last Updated**: 2026-11-03

How the shared FastAPI application serves HHEM and native llama generation
without coupling their model lifetimes. Exact routes, settings and diagnostics
live in the [server reference](../../reference/fastapi-server.md).

## Explicit composition

One Uvicorn process binds the configured loopback listener before model
startup. The application registers only its explicitly enabled routers.
HHEM routing delegates to the existing evaluation controller; llama routing
delegates to one asynchronous HTTPX client. Neither router chooses a model
from request text or imports a module named by a request.

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

The native llama executable stays in a separate process on a private port.
Its phase owns acquisition, launch, exact-child readiness and process exit.
FastAPI neither embeds a model binding nor starts or adopts that process.
The client always uses the selected committed `model_server.base_url`, with
proxy environment settings and redirects disabled.

## Real readiness and independent work

Shared health reports the exact application instance, both component states
and diagnostic-file availability. HHEM readiness still requires its observed
model and owned worker identities. Llama readiness requires a successful
native `/health` observation with status `ok`, not merely a listening socket.
The phase must also check that the native child it started is still alive.

Aggregate readiness requires every enabled component. HHEM's own health and
operation remain available when llama is unavailable. A failed component
does not close the other's completed result or transport.

HHEM performs heavy work in its existing scoring process. Native generation
uses asynchronous HTTP; it does not execute inference on the API event loop.
Finite admission applies before reading generation input, and input, native
response, connection and request deadlines remain bounded. There is no
transport retry, result cache, streaming path or general proxy.

## Owned shutdown and diagnostics

The application lifespan creates and closes the HTTPX client, cancels and
joins its outstanding forwarding requests, and shuts down HHEM through the
existing worker controller. Disconnect closes the outstanding HTTP operation.
It does not claim to stop the separately owned native llama process; the
phase still has to stop and join that process.

Both component cleanups run even when another cleanup fails. An original
failure and cleanup failures are retained separately in the raised group.
HHEM's existing parent-loss watcher, bounded worker replacement and confirmed
exit rules are unchanged. The current workflow's private control and
TypeScript machine-measurement channels are unchanged.

Standard logging formats validated native data as CloudEvents JSONL. The
same accepted records reach stderr and the role's named file. A failed file
mirror warns safely and records that the log is unavailable; it does not
invalidate completed model work. Validated HTTP results and actual process
receipts, not a search through terminal output, establish success.

## Design rationale

One API address keeps caller routing simple while leaving native llama in
the runtime that already loads the selected weights. HTTPX supplies the
asynchronous transport from the existing frozen environment; there is no new
dependency, native build or published-site cost.

Explicit routers and one client need no plugin registry or worker framework.
Keeping the existing HHEM snapshot preserves its private process protocol and
real scoring behavior. Native llama request parameters and response bytes
remain native rather than acquiring a second sampling or summary policy.

## See also

- [../../reference/fastapi-server.md](../../reference/fastapi-server.md) - shared API contract and settings.
- [hhem-evaluation-api.md](hhem-evaluation-api.md) - HHEM scoring and cancellation.
- [../../reference/summary-evaluation-workflow.md](../../reference/summary-evaluation-workflow.md) - current caller and machine control.
- [../../how-to/run-the-gates.md#independent-python-service-contracts](../../how-to/run-the-gates.md#independent-python-service-contracts) - offline composition checks.
