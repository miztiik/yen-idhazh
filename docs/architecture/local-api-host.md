# How independent local Python APIs are hosted

**Last Updated**: 2026-11-09

How independent Python APIs acquire one bounded loopback listener without
giving the host ownership of service payloads or behavior.

## One component per native application

`services/local_api_host/` is an installable Python package that composes one
selected `ApiComponentRuntime` into one FastAPI application. The host owns the
application lifespan, health and OpenAPI route wiring, loopback request guard,
bounded request-body reading, optional W3C trace propagation, Uvicorn settings
and exact lifespan exit result.

The service owns its router, opaque state, startup and shutdown callbacks,
health observation, health response schema and body, refusal bodies and
diagnostic event data. The host never inspects a service status word, error
payload or event envelope. A service that has several internal modules may
combine them behind one service-owned component before calling the host; the
host itself has no registration list or plugin discovery. Complete native
applications can share a listener through the explicit assembly below.

`HostSettings` declares the application title and schema version, exact health
and schema paths, one loopback listener, body byte and read-time bounds,
graceful shutdown wait and whether response trace propagation is enabled.
Unknown settings and non-loopback hosts are rejected by the contract.

## Complete-application assembly

`compose_applications` accepts a fixed tuple of complete applications produced
by `compose_api`. `bind_application` returns a typed immutable
`ApplicationBinding` containing the original application and its validated host
settings. The aggregate exposes those bindings as `application_bindings`; it
does not copy component state, service identity or event sinks.

All bindings must agree on listener/body/read bounds, shutdown timeout and
trace propagation. Native titles, versions and health/schema paths remain
independent. Construction rejects repeated applications, colliding paths and
nonliteral or non-HTTP routes rather than silently selecting one provider.
There is no discovery or another listener configuration.

Standard framework routes forward the unchanged ASGI request to its native
application for every HTTP method. A known operation's trailing-slash variant
is also dispatched to that application, which refuses it using its own native
behavior; it is not a successful alias or redirect. Unknown paths use the
first application's default guarded behavior. The aggregate adds no guard or
receiving trace wrapper, so each request acquires exactly one receiving
operation.

Every native health/schema endpoint remains intact. Schema requests invoke the
original native OpenAPI builder, including its custom request definitions;
there is no combined schema that could confuse identically named native
models. The aggregate has no additional schema or documentation endpoint.

The aggregate enters each native `app.router.lifespan_context(app)` once and
unwinds in reverse order using `AsyncExitStack`. Only the native host's
lossless lifecycle contract is accepted: a later startup/lifespan failure
propagates through earlier native lifespans, which retain it alongside their
own independent cleanup failures. Component shutdown and event-sink cleanup
are never called a second time by the assembly.

## Request boundary

The outer request layer captures a monotonic start instant before any guard or
body access. When trace propagation is enabled, it accepts one valid W3C
`traceparent`, keeps its trace ID as the parent of a fresh nonzero span,
canonicalizes valid `tracestate` and writes the new unsampled carrier on every
response. Missing or invalid context creates a fresh root. The middleware stores
the one receiving `OperationMetadata` at `request.state.operation_metadata` and
the monotonic start at `request.state.request_started_at` before guards run.
`OperationMetadata` carries `traceId`, `spanId`, optional `parentSpanId`, a
required `links` JSON array and optional canonical `traceState`. Root and
receiving-operation factories emit an empty link array. Optional fields are
omitted rather than serialized or accepted as null. Its native schema metadata
has version `2026-11-03`. Decoded link arrays validate as immutable native
tuples; generated optional-field schemas contain neither null branches nor
null defaults. The evaluator's `tests/test_trace_context.py` and real
`check_trace_context.ts` bridge bind the native JSON reader, serialized fields,
schema and codec to the shared TypeScript authority. Trace data is not inserted
into a JSON body.
Canonical state is limited to the authority's W3C 512-byte allowance; invalid
optional state is omitted without discarding a valid parent identity.
The receiving layer reports supplied malformed metadata through an optional
typed service callback, after storing the actual receiving operation. It
suppresses the standard parser's unsafe raw-state warnings; the evaluator
instead emits a fixed body-free diagnostic. A callback may return the service's
native logging-failure response, which receives the same carrier.

The next layer refuses any browser `Origin`, duplicate `Host` or `Host` outside
the configured loopback binding before reading the request body. The selected
component renders both path-specific and default refusal responses, so the host
does not create another public error vocabulary.

The bounded body reader accepts one UTF-8 `application/json` identity-encoded
body, enforces declared length and streamed bytes, and applies one absolute
read deadline. It reports typed internal failure codes for the service adapter
to map into its existing public result.

## Lifecycle and health

The lifespan emits typed service-owned started data, starts the component,
tracks whether startup completed and always invokes its shutdown callback.
Health observation remains service-owned: `HealthRenderer` returns the exact
response plus a separate readiness boolean. The host uses only that boolean to
emit one ready event. It does not infer readiness from an HTTP status or payload
field.
`compose_api(..., service_operation=...)` accepts the actual operation already
used to construct service loggers and controllers. Enabled callers reuse it for
host lifecycle callbacks rather than allocate a second service root.
Standalone callers keep the default root allocation; disabled propagation
keeps the host's untraced lifecycle profile.

The terminal callback is selected after component cleanup:

- Completed startup with clean component cleanup emits
  `started -> [ready] -> stopped`.
- Failed component startup with clean component cleanup emits
  `started -> failed(startup)` and never emits stopped.
- Any component cleanup failure takes precedence and emits `failed(shutdown)`
  once, never stopped, while retaining an earlier startup or lifespan failure.
- A shutdown failure after completed startup also emits `failed(shutdown)` and
  never stopped.

The host then closes the event sink. Terminal callback and event-sink close
failures remain independent cleanup failures, and the raised result retains the
original lifespan failure plus every cleanup failure. Uvicorn success is
accepted only when startup and shutdown both completed without a lifespan error.

## Dependency cost

The evaluator already installed FastAPI, Pydantic and Uvicorn. Reusing the
standard W3C codec adds one 60,256-byte pure-Python
`opentelemetry-api==1.45.1` wheel to that existing environment; it benefits
trace parsing and canonical state propagation without adding a tracing provider
or telemetry exporter. The package has its own frozen lock, and consuming
services also lock the local path dependency.

## Design rationale

One neutral host prevents each Python API from copying listener safety,
lifespan cleanup and response-trace behavior. Keeping payload rendering behind
typed callbacks prevents that reuse from turning unrelated health, error and
event contracts into one generic service vocabulary. A fixed component passed
by the caller keeps imports and process ownership explicit; runtime discovery
would add ordering, import-safety and failure rules with no current use.
An explicit service operation joins construction, model loading and lifecycle
diagnostics without introducing a mutable current request. Request context
remains in its own ASGI scope; neither a lifecycle callback nor a metadata
warning borrows the last request's context.
Forwarding complete applications instead of copying component routers retains
native host-added operations, exception handlers, schema customization and
cleanup without coupling independently evolving provider contracts.

## See also

- [evaluation/summary-evaluator.md](evaluation/summary-evaluator.md) - how the
  evaluator adapts its scorer registrations to one host component.
- [text-analysis/gliner-api.md](text-analysis/gliner-api.md) - independent
  provider applications assembled on the existing text-analysis listener.
- [../reference/summary-evaluator-api.md](../reference/summary-evaluator-api.md) -
  the evaluator's unchanged wire contract.
- [../reference/repository-layout.md](../reference/repository-layout.md) -
  package ownership and writers.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - frozen dependency
  and evaluator checks.
