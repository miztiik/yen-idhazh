# Measure and record a completed task

**Last Updated**: 2026-11-26

Which local HTTP commands measure and record an operator-owned task?
The Bun host probe includes PID CPU and optional process and machine RAM.
Optional [cache probes](host-cache-probes.md) attach exact last-level-cache
events to this same handle lifetime; their separate latency command measures
an owned native benchmark, not the caller's task CPU.
It samples until explicit stop, process exit, process reuse, service shutdown
or the declared safety expiry. CPU windows and polling cadence do not end
a task. [Measurement scopes and units](host-metrics.md#whole-task-typescript-samples)
define what the returned numbers mean.

## Listener and trust

Run `bun run src/index.ts --serve` in `services/host-probes`.
The listener accepts only configured loopback addresses, `127.0.0.1` or
`::1`. This is operator tooling with no authentication, not a published-site
backend. Requests with a browser `Origin` header are refused.

The feed workflow uses the same native handlers through the
[independent machine API server](serve-pipeline-apis.md), alongside
fingerprint routes but separate from planning. The probe package's
`src/api/serve-machine-apis.ts` also assembles the machine-only application for
summary evaluation without feed source or feed settings. It composes the real
fingerprint and profiling implementations; shared hosting owns only their
listener and process lifetime. The explicit machine listener and shared supervision
waits come from `config/hono-server.json`. The standalone command above retains
its own listener controls.

Task commands require UTF-8 JSON and `Content-Type: application/json`.
Unknown fields fail. No command accepts a path, executable, URL, proc root,
configuration override or process name to search. Task names, identity and
PID pins must come from the operator, never fetched article text.
Linux writes process identity and counters to `/proc/<pid>/stat`.
The operator supplies both the requested PID and its kernel start ticks,
the process start-time counter in that file.
The start ticks distinguish a reused PID from the original process.

`GET /api/2026-11-05/sample-host` remains the independent single-interval machine
CPU/RAM command. It neither creates a task handle nor obeys the task-profile
enable switch. Its existing response and one-shot CLI remain unchanged.

## Start

`POST /api/2026-11-05/start-task-profile` accepts:

```json
{
  "identity": {
    "pipeline_name": "operator-task",
    "task_name": "parse-document",
    "run_id": "operator-run"
  },
  "target": { "pid": 4242, "start_ticks": "12345" },
  "server": { "pid": 4243, "start_ticks": "12346" }
}
```

These example pins are not live identities. `server` is optional. It names
one additional process explicitly; it does not search for a model server.
The target owns the task profile. Its CPU and RAM appear under
`processes.worker`; the optional server appears under `processes.server`.
The probe's own PID is not substituted for the requested target.

The identity requires only nonempty pipeline, task and run strings.
It is business metadata, not a durable replay key.
Each successful start creates a new, unguessable UUID `handle`.
Success returns HTTP 200 with `status: "started"`, that `handle`,
the verified `target`, `expires_at`, a UTC instant, and the allocated profile
operation described below.
The caller starts its actual work only after this response.

An enabled start allocates one operation context, the identifiers and
relationships for this measurement. Its top-level `traceId` is a nonzero
32-character lowercase hexadecimal execution ID. Its `spanId` is a nonzero
16-character lowercase hexadecimal operation ID. A valid incoming W3C
`traceparent` header makes the profile a child of that operation: it retains
the execution ID and stores the caller's operation ID as `parentSpanId`.
The shared codec also preserves valid `tracestate` as `traceState`.
A missing or invalid carrier starts a fresh execution and omits the parent.
`links` is empty because a profile consumes no completed operation result.
These fields describe the profile only; they do not enable runtime tracing.

Native commands and profiles accept only the current shape. There are no
old-field aliases, historical conversions or foreign UUIDs in this identity.

The target PID and start ticks are checked before collector startup and again
in the collector's opening observation. A stale or unverifiable pin returns 409.
A caller that aborts startup receives no usable handle; the collector is
closed before startup cleanup returns. Failed startup releases its reserved
capacity.

## Stop

`POST /api/2026-11-05/stop-task-profile` accepts:

```json
{
  "handle": "c80a7d40-7821-4454-b118-669eb8f5f290",
  "outcome": "success"
}
```

`outcome` is `success`, `error` or `cancelled`. Stop while the target is
still alive to obtain its closing CPU counters. The reply has HTTP 200,
`status: "stopped"`, the `handle`, `end_reason` and validated `profile`.
Concurrent and repeated stops return the same result while retained;
the first closing event owns the result.
The returned `profile` carries the exact top-level operation metadata allocated
at start. Stop uses only the genuine resource `handle`; missing, invalid or
different tracing headers do not replace the profile's operation.

Normal HTTP stop uses `end_reason: "explicit_stop"`. A target exit or PID
reuse closes the profile as `cancelled`, with `owner_exited` or `pid_reused`.
Safety expiry uses `cancelled` and `expired`, not successful full-task
completion. Service shutdown uses `cancelled` and `service_stopped`.
No close operation signals or kills an observed target or server.

Start and stop return `cache_counters` beside the unchanged CPU/RAM `profile`.
Both cache flags default to false. Counter refusal remains explicit and does
not stop CPU/RAM profiling. The cache result retains its own actual interval.
`POST /api/2026-11-05/measure-cache-latency` accepts only `{}` and creates no task handle.
Its native-tool, concurrency, body-time and working-set bounds are defined in
the [cache reference](host-cache-probes.md).

The transient command's completed handles exist only in this service process.
A restart loses its handles. CPU/RAM metadata may be returned by this API,
reported through the existing TypeScript callback or written to structured
stderr; recording the evidence is a separate command.

## Record

`POST /api/2026-11-26/record-task-performance` files one completed
[Task Performance row](../architecture/contracts/schemas.md#task-performance)
without sampling again. The standalone listener takes a trusted launch file
with `--serve --recording-context launch.json`. It contains `state_root`,
optional `registry_path` (defaults to `config/ledgers.json`), and `execution`:
`run_id`, `attempt`, `pipeline_name`, `shard`, `git_sha`, and the distinct
`accounting_days` the caller admits. Explicit paths are relative to the
launcher's working directory unless absolute. The composed machine child
takes the same execution fields as `task_performance` on its private startup
pipe and reuses its selected state root and registry. Start only one recording
listener at a time for that private root. Without a trusted execution the
record route refuses writes; existing commands keep their defaults.

The JSON body contains `date`, `writer` (the execution identity without
`accounting_days`, plus `task_name`), and `measurement` (the row's measurement
fields, including `task_kind` and `outcome`). The request cannot name the
destination or set `version`, `producer`, `job` or substitute row identity.
The writer stamps `producer: "host-probes"` and `job: null`. Use only the
flat summary of a closed profile, not its samples, PIDs or handle. TypeScript
callers can use `summarizeClosedTaskProfile` to select the whole-interval CPU,
RAM and elapsed readings. Independently measured phases or model-serving
sessions can send their typed evidence without a profile or handle. If supplied,
`host_unit_id` must match verified capture bytes in the same private root,
admitted days and execution; omit it when no capture was available.

When the launched job enables the master `observability.host_telemetry_enabled`
switch, the existing task profiler is enabled and both profile memory settings
follow `observability.memory_profiling_enabled`. Memory off refuses non-null RAM
readings, not independently measured elapsed time or model counters. Request
bodies cannot change these settings.

`written` returns the validated `row` and its one completed `files` receipt.
Master off returns `disabled` / `configured_off`; a paused or retired family
returns `skipped` / `ledger_not_active`. Both have `row: null` and `files: []`.
The writer verifies the exact raw UTC day in the private root before writing.
An equal retry returns the original relative path, ID and digest, even after
restart. Omitted nullable values and explicit nulls compare equally. A changed
row for the same task and attempt returns 409 without replacement. Another
named task or attempt can have its own record. No retry can recover a
measurement that never closed or a lost private root.

Bad JSON or measurements return 400, an unmatched launch context returns 403,
and unreadable or unverifiable persistence returns 500. The existing JSON
body bound and browser-origin refusal apply. The receipt is not a publication
action; [delivery checks](../architecture/publishing/committing.md#evidence-is-not-permission)
remain the caller's responsibility.

The offline recording test sends its exact Parquet files to the ordinary
Python reader and packer. Run it with the installed backend environment
(`IDHAZH_PYTHON` selects the interpreter when it is not `python`).

## Native command diagnostics

All commands follow the
[native API event standard](../architecture/contracts/identity.md#native-api-support).
After an actual result, `host_probe_completed` contains only the command name
and outcome. For transient commands, `handled` means the command returned its
native result, not that a measurement was available or that the profiled task succeeded.
Disabled start/stop creates no collector, handle or measurement.

An enabled start uses the real profiler operation for its event. Successful
and repeated stops use that same retained operation, ignoring conflicting stop
headers. Ordinary requests derive a child from a valid incoming carrier or a
root otherwise. Safe failure events contain only their fixed code; body cleanup
uses the receiving request, background profile failure uses its session, and
service cleanup uses its owned lifetime operation.

Full `{event: "task_profile", profile}` reports remain the existing private
callback/child transport and task evidence. They are excluded from normal
event mirrors. Native diagnostics never copy profiles, PIDs, counters,
request bodies, exception text or paths. The one-shot CLI keeps its native
sample on stdout and emits the corresponding safe event on stderr.

## Bounds and failures

`config/host-probes.json` owns these controls. Without an instrumented job
launch, the task instrument remains default-off; RAM follows the
[measurement controls](host-metrics.md#whole-task-typescript-samples).
Neither CPU windows nor polling intervals limit task lifetime.

Table A - task HTTP bounds

| ID | Control | Default and effect |
| --- | --- | --- |
| A1 | `task_profile.max_profile_handles` | 16 entries total, including starting, running, closing and completed profiles. Reservation precedes asynchronous startup. |
| A2 | `task_profile.profile_handle_ttl_ms` | 21600000 milliseconds, or six hours, for the explicit HTTP safety expiry; completed results are retained for at most another such period. `expires_at` exposes the task deadline. |
| A3 | `max_request_body_bytes` | 16384 bytes, or 16 KiB, per JSON command, including streamed bodies. |
| A4 | `task_profile.lifecycle_timeout_ms` | 10000 milliseconds, or ten seconds, for collector startup and one closing deadline that includes shutdown and asynchronous reporting. It does not limit task duration. |

New starts remove expired results, then the earliest-started completed result
when space is needed. Active profiles are never evicted. Completed results
can therefore disappear before their retention deadline. An expired task
still returns its cancelled result while that result is retained.
Expiry uses elapsed time from a monotonic clock, not changes to the UTC wall
clock. A longer task needs an explicit configuration change before starting.
GitHub still kills a hosted job at six hours.

Both task commands return `status: "disabled", reason: "configured_off"`
with HTTP 200 when the instrument is off. No host read, clock-rate command,
worker or handle is created. Body validation still applies.
No profile operation is allocated. The native command event still carries
its receiving-request operation.

Invalid JSON or controls return 400; oversized bodies return 413.
Stale process pins return 409, occupied active capacity returns 429,
and an unknown or evicted handle returns 404. A stopping service refuses
new starts with 503. Unexpected collection or report failures log an error
and return 500, not a successful profile. Missing individual measurements
stay null with a reason; a real zero PID CPU interval remains zero.
The owned collector is terminated before a report callback is awaited.
A callback that never settles fails stop and shutdown at the closing deadline.
All responses are uncached.

Table B - native probe event payloads

| ID | Event type | Strict data |
| --- | --- | --- |
| B1 | `host_probe_completed` | `operation`: `sample`, `start-task-profile`, `stop-task-profile` or `cache-latency`; `outcome`: `handled` or `disabled`. |
| B2 | `host_probe_failed` | `code: "HOST_PROBE_FAILED"` |
| B3 | `host_probe_cleanup_failed` | `code: "HOST_PROBE_CLEANUP_FAILED"` |
| B4 | `host_probe_body_cleanup_failed` | `code: "HOST_PROBE_BODY_CLEANUP_FAILED"` |
| B5 | `task_profile_failed` | `code: "TASK_PROFILE_FAILED"` |
| B6 | `host_probe_completed` | `operation: "record-task-performance"`; `outcome`: `written`, `disabled` or `skipped`. |

## Embedded use

The existing `profileTask` wrapper still pins the actual calling PID by
default. `startTaskProfile` also accepts an explicitly pinned `target` and
optional `server`. Its session exposes `target`, `expires_at`, `settled`
and an idempotent `close(outcome, end_reason)` method. `operation` holds the
context allocated at enabled start. An optional `parent` in the profiling
options supplies an enclosing operation through the shared contract;
without one, start creates a root. The collector receives that allocated
context and returns it unchanged rather than allocating another operation.
`settled` returns
either the validated profile or an explicit error, including automatic
closure. The ordinary wrapper has no HTTP safety expiry and closes only
when its work settles.

An embedded HTTP caller must await the handler's `close()` on service
shutdown. The ordinary host-probe service does this through `stop()`;
its CLI also handles stop signals. Startup reservations, active collectors
and pending closes are included. There is no feed-planner or GitHub
dependency in this lifecycle.

`createSampleHandler(config, probeContext, report, diagnostics)` keeps full
profiles on `report` and safe native events on `diagnostics.writeEvent`.
The optional `diagnostics.lifetimeContext` identifies service cleanup;
request and profile operations remain separate and are passed explicitly.

## Design rationale

The commands reuse the independent task collector so synchronous work cannot
block polling. A bounded in-memory maintainer prevents concurrent starts from
oversubscribing capacity, retains idempotent stops and owns cleanup.
Explicit pins prevent process-name discovery and PID reuse from changing
what a profile measures. Expiry bounds abandoned handles without presenting
an incomplete task as a successful full-task observation.
The resource handle and the profile operation remain separate: the handle
addresses retained control state, while the operation identifies the measurement.
The existing common-contracts package supplies validation and the W3C codec.
Its pinned OpenTelemetry API and core libraries affect tool installation only;
they add no tracing provider, exporter or published-site bytes.

## See also

- [Host measurements](host-metrics.md)
- [Fetch and parse operator API](../architecture/sources/feed-operator-api.md)
- [Native instrument checks](../how-to/run-the-gates.md#independent-typescript-packages-and-services)
- [Serve pipeline APIs](serve-pipeline-apis.md)
