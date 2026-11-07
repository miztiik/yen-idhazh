# How one local Python API is hosted

**Last Updated**: 2026-11-07

How an independently started Python service acquires one bounded loopback
listener without giving the host ownership of service payloads or behavior.

## One component per process

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
host itself has no registration list or plugin discovery.

`HostSettings` declares the application title and schema version, exact health
and schema paths, one loopback listener, body byte and read-time bounds,
graceful shutdown wait and whether response trace propagation is enabled.
Unknown settings and non-loopback hosts are rejected by the contract.

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
receiving-operation factories emit an empty link array. Trace data is not
inserted into a JSON body.

The next layer refuses any browser `Origin`, duplicate `Host` or `Host` outside
the configured loopback binding before reading the request body. The selected
component renders both path-specific and default refusal responses, so the host
does not create another public error vocabulary.

The bounded body reader accepts one UTF-8 `application/json` identity-encoded
body, enforces declared length and streamed bytes, and applies one absolute
read deadline. It reports typed internal failure codes for the service adapter
to map into its existing public result.

## Lifecycle and health

The lifespan emits typed service-owned started data, starts the component and
always invokes its shutdown callback. Health observation remains service-owned:
`HealthRenderer` returns the exact response plus a separate readiness boolean.
The host uses only that boolean to emit one ready event. It does not infer
readiness from an HTTP status or payload field.

Shutdown retains the original lifespan failure and every independent cleanup
failure. The event sink emits stopped after clean component shutdown, failed
after a shutdown failure, then closes its own delivery resources. Uvicorn
success is accepted only when startup and shutdown both completed without a
lifespan error.

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

## See also

- [evaluation/summary-evaluator.md](evaluation/summary-evaluator.md) - how the
  evaluator adapts its scorer registrations to one host component.
- [../reference/summary-evaluator-api.md](../reference/summary-evaluator-api.md) -
  the evaluator's unchanged wire contract.
- [../reference/repository-layout.md](../reference/repository-layout.md) -
  package ownership and writers.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - frozen dependency
  and evaluator checks.
