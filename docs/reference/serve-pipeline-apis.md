# Serve pipeline APIs

**Last Updated**: 2026-11-05

Which local listener serves planning, article fetching/parsing, machine
measurements and output delivery?
`services/serve-pipeline-apis` hosts a native-built application through one
local HTTP server per task. The native API packages assemble their existing
Hono handlers; shared hosting supplies the Bun listener and its lifetime.
It is build-time operator tooling, not a backend for the published site.

## Listener authority

`config/hono-server.json` is the composed listener's only address and
supervision source.
Tasks capture that validated file in their private startup data. HTTP input,
headers and environment values cannot select another destination. Internal
planning requests use the owned listener address, never the incoming Host
header.

Table A - Listener settings

| Id | Field | Default and meaning |
| --- | --- | --- |
| A1 | `hostname` | `127.0.0.1`; only this loopback address and `::1` are accepted. |
| A2 | `port` | `8787`; an occupied port fails startup without adopting or stopping its listener. |
| A3 | `idle_timeout_seconds` | 30 seconds; active planning and delivery disable the per-request idle timer. |
| A4 | `supervision.readiness_timeout_ms` | 30000 milliseconds; startup and owned-child readiness must finish within this wait. |
| A5 | `supervision.shutdown_timeout_ms` | 10000 milliseconds; allows graceful application and worker cleanup before forced exit. |
| A6 | `supervision.forced_exit_timeout_ms` | 5000 milliseconds; bounds confirmation after killing only the spawned child. |

These waits retain their previous effective values. Native startup packets
capture the shared controls under `server.supervision`; missing controls fail
validation before spawning. Feed settings and top-level machine startup fields
provide no fallback.

Extraction, parser limits, host instruments, profiling, ledger registration
and output validation stay with their existing modules. Their standalone
commands retain their own listener settings; those settings do not choose the
composed workflow address. The application adds no root workspace, Python
collector or separate machine-server process.

## Explicit task groups

The feed package's `scripts/serve-feed-apis.ts` receives planning or delivery
startup; the probe package's `src/api/serve-machine-apis.ts` receives machine
startup. Each native entry validates its complete private packet and builds
the application under the shared child lifetime. The caller selects the
trusted entry and fixed group before startup, not through an API request.
There is no shared native entry, module registry or request-selected import.

Table B - Route groups

| Id | Group | Native modules and lifetime |
| --- | --- | --- |
| B1 | `planning` | Planning, fetch/parse, fingerprint and sampling/profile routes; one listener covers fingerprint capture and the complete planner request. |
| B2 | `machine` | Fingerprint and sampling/profile routes only; planning and delivery are absent. |
| B3 | `delivery` | The existing private safe-persist handler only; no collection inputs or planner batches are loaded. |

The composed application forwards each module's current native JSON; it adds
no identity aliases or response wrapper. The existing
[planner APIs](../architecture/sources/feed-operator-api.md) and
[profile commands](host-probe-api.md) retain their own validation, operation
metadata and resource handles. CloudEvents are diagnostic envelopes, not
wrappers around each HTTP command.
The current planner prefix is `/api/2026-11-05`. Its
[document and article identities](../architecture/sources/feed-operator-api.md#independent-fetch-and-parse-endpoints)
and [combined response controls](../architecture/sources/feed-plan-runner.md#entry-points-and-controls)
also apply on this shared listener.

`GET /health` returns the exact child's startup nonce, PID, configured port,
group, enabled modules and enablement. The supervisor compares the private
readiness packet with the spawned PID and invocation, then verifies this
uncached HTTP result and the selected module's native identity. Planning also
checks the captured run, attempt, UTC clock, revision and operation context.
A socket or a log line is not readiness. A disabled
instrument still returns its native disabled result; it is not a fabricated
measurement.

The shared parent supervisor and child lifetime detect early exit and enforce
the invocation's validated startup, drain and forced-exit waits. Native adapters
retain their own readiness and failure checks. Cancellation, stop signals and
parent-pipe loss close the owned application. Shutdown aborts admitted requests, awaits module cleanup,
closes profile workers and parser work, and reaps only the owned child.
Original work failure and cleanup failure remain separate.
The supervisor also drains the child diagnostic stream before closing its
mirror. A nonzero shutdown of a live ready child remains a cleanup failure
even when the caller already failed.

## Diagnostics and current-task evidence

The supervisor streams brief accepted CloudEvents to stderr and the same
append-only file:

```text
hono-server_<yyyy_mm_dd>_<run_id>_<attempt>.log
```

The date is the UTC run-start day. `run_id` is the platform run identifier,
not the planner's date-prefixed business identity or the startup nonce.
Local callers use their existing invocation identity and attempt one.
Restarting the role in the same run appends a fresh start event.
`src/declare-event-source.ts` supplies the unchanged `/services/typescript-api`
protocol identity, without a source registry.
The existing common-contracts helpers allocate and validate event and operation
metadata without a tracing provider, exporter or global active context.

Server diagnostics contain startup, readiness, stop, safe error codes and
observed lifecycle facts, but no process IDs. Private readiness, supervision,
profiling and current-task evidence retain their existing process identities.
Validated terminal article diagnostics are a narrow exception to the lifecycle
projection: the writer emits and mirrors the original accepted
[`ArticleFailureDiagnosticSchema`](../../packages/common-contracts/src/schemas/article-failure-diagnostic.schema.ts)
CloudEvent unchanged. Its occurrence ID, UTC time, planner source and actual
operation carrier are preserved, including full safe native quality and
extraction evidence. Invalid terminal records emit `CHILD_DIAGNOSTIC_INVALID`
without copying their content. The
[planner log contract](../architecture/sources/feed-operator-api.md#structured-operation-logs)
owns this current-only subtype.
Delivery completion retains its existing strict diagnostic shape.
[`DeliveryCompletionDiagnosticSchema`](../../services/feed-ingest-plan/scripts/safe-persist-http-diagnostic.ts)
retains the native `landed`, `already-on-main`, `no-changes` or `failed` status,
nullable lowercase hexadecimal commit and nonnegative file count.
Its `run_id` and attempt come from the actual delivery request, not the
supervised task. Its group remains `delivery` and phase remains
`operation_completed`. Severity and nullable duration, exit code and safe code
keep their existing validation and defaults.

The complete native request `context` appears in completion data and supplies
the CloudEvent carrier without allocating another operation. The writer
preserves its execution, operation, optional parent and trace state, and
required input links under the
[shared identity contract](../architecture/contracts/identity.md#4-native-typescript-event-and-operation-metadata).
Missing or invalid context and unknown relay fields emit
`CHILD_DIAGNOSTIC_INVALID`; they never fall back to supervision.
Lifecycle diagnostics keep their supervision operation and exclude
`operation_completed`. Both diagnostic readers accept only their current
shapes; saved task evidence is unchanged. The local API source, native
completion event type and server name are unchanged. No path or process ID
is added to completion data.

Native packages supply typed, validated events to the shared mirror. The feed
decoder validates delivery completion/failure and terminal article events,
then delegates machine events to the probe package. Fingerprint's
`./diagnostic` export validates `host_fingerprint_completed` and
`host_fingerprint_failed`; probe's `./diagnostic` export validates
`host_probe_completed`, `host_probe_failed`, `host_probe_cleanup_failed`,
`host_probe_body_cleanup_failed` and `task_profile_failed`. Their safe data
contains only native status, command/outcome or the declared failure code,
never a host row, profile, measurement or path. A handled command does not
claim that a measurement was available.

Shared hosting validates its own `typescript_api_request_failed` subtype,
with only `API_OPERATION_FAILED` in its data. It imports no native package.
Accepted native envelopes are mirrored unchanged, including source, occurrence
ID, UTC time, carrier and data. Invalid or unknown types produce
`CHILD_DIAGNOSTIC_INVALID`, not a replacement event. Existing plain diagnostic
writers retain their strict transition readers; this reader expansion does
not change the HTTP handlers or claim their native emission.
Article reports recognize rejection markers only in server lifecycle events;
a native delivery code with the same spelling does not create an evidence gap.
Ordinary planner failures still use the body-free lifecycle projection.
Private startup/control
packets remain on stdout. Article bodies, prompts, model output, secrets,
raw headers and raw exception text are not server-log fields.
Routine task-profile reports are validated with the native measurement model,
retained in task evidence and omitted from normal server logs. Explicit stop
also returns the native API result. Server shutdown interrupts an active
profile without that HTTP reply, so its real cancelled outcome, closure reason,
operation identity and measurements remain in the evidence and report after
the manager clears its entries. A successful measurement is not a server error.

An open, write or close failure marks the file mirror unavailable and emits
one explicit safe stderr warning. It does not fail useful API work. There is
no log quota, rotation worker or custom retention policy. Actual request,
process and cleanup failures still fail the task.

Each task writes its current observation atomically to the named
`hono-server-planning.json`, `hono-server-machine.json` or
`hono-server-delivery.json` in the disposable run directory.
`src/server-evidence.ts` owns the versioned envelope. The probe package's
`src/api/create-machine-server-evidence.ts` binds it to the real native profile
validator for both machine and feed readers. Readers accept the current shape
only; earlier same-day evidence without profile reports reads as
no captured reports, not a successful empty measurement. These files are same-run evidence, not committed ledgers,
request journals or restart stores.

Table C - Evidence meanings

| Id | Field | Meaning |
| --- | --- | --- |
| C1 | `startup`, `startup_ms` | Observed ready or failed outcome, and elapsed milliseconds until readiness or startup failure. Missing observations stay unavailable. |
| C2 | `shutdown`, `exit_code` | Observed stop, forced exit or cleanup failure, with the actual child exit status when known. |
| C3 | `log_filename`, `log_available` | The identity-checked role filename and mirror availability at the last saved observation; an existing partial file can still be retained. |
| C4 | `error_code`, `cleanup_error_code` | The original work/start failure and a separate cleanup failure, when present. |
| C5 | `reported_profiles` | Native profile results observed before exit, once per execution/operation pair. No reports means none captured, not proof no profiles ran. Full samples and unavailable reasons retain their native meaning. |

The feed report reads these outcomes, including failed startup. Artifact
preparation retains available evidence and logs without requiring a successful
planner response. Its terminal-article reader reads only these distinct named
mirrors, not a directory listing or latest-file search. A partial mirror can
supply complete validated records with an explicit evidence-gap notice.
Failure/cancellation uploads use platform retention defaults.
Hard runner termination cannot guarantee a final report or upload.

## Design rationale

Native construction reuses the real Hono planner and delivery applications and
machine handlers. Feed-ingest-plan owns planning and delivery assembly;
host-probes composes the existing fingerprint and profile implementations.
Shared hosting imports none of them, including in its tests and dependency
metadata. Typed construction arguments carry the application, failure policy,
diagnostic decoder and bound evidence validator without a plugin framework.
Only validated JSON-shaped controls cross the private process pipe.

The evaluator CI job checks one sparse candidate checkout in two stages.
Shared hosting first installs, checks and tests with every native service
absent. The same checkout then gains only named machine packages, settings and
recorded inputs. Real Linux child tests verify fingerprint writes, explicit
profile stop, shutdown-only profile evidence, worker cleanup and released
listeners while feed source and feed configuration remain physically absent.
The machine entry, parent adapter and actual summary helper also pass dependency
inspection. Those builds provide import metadata only; process checks execute
source entries so worker URLs retain their module-relative paths.
Inspection supplements execution; it does not replace it.

Explicit groups keep task resources visible without per-API processes.
Hono and Zod remain existing tool dependencies. Host-probes adds the shared
hosting and fingerprint installation closure and the already locked Hono
version for composition; published-site bytes are unchanged. Existing
standalone tools and older workflows are not migrated.

Process ownership is established by private control data, not a copied ID in
a diagnostic line.
Preserving the validated article event avoids assigning its failure to the
server's supervision operation or losing the measured cause in a generic error.
Delivery results need their own payload because completion describes a request,
while lifecycle events describe the server that receives it.

Event producer URIs and private control identifiers identify the existing
protocol, not a source directory. Their names stay unchanged when the source
moves so current readers and recorded observations retain their meaning.

## See also

- [Run the isolated feed workflow](../how-to/run-feed-ingest-plan-test.md)
- [Gate commands](../how-to/run-the-gates.md#independent-typescript-packages-and-services)
- [Host measurements](host-metrics.md)
- [Native identity contract](../architecture/contracts/identity.md)
