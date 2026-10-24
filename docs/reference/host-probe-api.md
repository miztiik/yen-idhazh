# Start and stop a task resource profile

**Last Updated**: 2026-10-24

Which local HTTP commands measure one process for an operator-owned task?
The Bun host probe includes PID CPU and optional process and machine RAM.
Optional [cache probes](host-cache-probes.md) add exact last-level-cache
event counts to this same task lifetime and a separate native latency command.
It samples until explicit stop, process exit, process reuse, service shutdown
or the declared safety expiry. CPU windows and polling cadence do not end
a task. [Measurement scopes and units](host-metrics.md#whole-task-typescript-samples)
define what the returned numbers mean.

## Listener and trust

Run `bun run src/index.ts --serve` in `services/host-probes`.
The listener accepts only configured loopback addresses, `127.0.0.1` or
`::1`. This is operator tooling with no authentication, not a published-site
backend. Requests with a browser `Origin` header are refused.

Task commands require UTF-8 JSON and `Content-Type: application/json`.
Unknown fields fail. No command accepts a path, executable, URL, proc root,
configuration override or process name to search. Task names, identity and
PID pins must come from the operator, never fetched article text.
Linux writes process identity and counters to `/proc/<pid>/stat`.
The operator supplies both the requested PID and its kernel start ticks.
The start ticks distinguish a reused PID from the original process.

`GET /api/2026-10-20/sample` remains the independent single-interval machine
CPU/RAM command. It neither creates a task handle nor obeys the task-profile
enable switch. Its existing response and one-shot CLI remain unchanged.

## Start

`POST /api/2026-10-24/start-task-profile` accepts:

```json
{
  "identity": {
    "pipeline_name": "operator-task",
    "task_name": "parse-document",
    "run_id": "operator-run",
    "correlation_id": "cd8002f4-ea0d-435c-8a60-3cffb0ed45ec",
    "request_id": "f72beb64-8ad9-4b6f-a932-cc26699dde66"
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

The identity requires nonempty pipeline, task and run strings and UUID
correlation and request strings. It is metadata, not a durable replay key.
Each successful start creates a new, unguessable UUID `handle`.
Success returns HTTP 200 with `status: "started"`, that `handle`,
the verified `target` and `expires_at`, a UTC instant.
The caller starts its actual work only after this response.

PID and start ticks are checked before collector startup and again in the
collector's opening observation. A stale or unverifiable pin returns 409.
A caller that aborts startup receives no usable handle; the collector is
closed before startup cleanup returns. Failed startup releases its reserved
capacity.

## Stop

`POST /api/2026-10-24/stop-task-profile` accepts:

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
the first stop owns the outcome.

Normal HTTP stop uses `end_reason: "explicit_stop"`. A target exit or PID
reuse closes the profile as `cancelled`, with `owner_exited` or `pid_reused`.
Safety expiry uses `cancelled` and `expired`, not successful full-task
completion. Service shutdown uses `cancelled` and `service_stopped`.
No close operation signals or kills an observed target or server.

Start and stop also return `cache_counters` separately from `profile`.
Its default-off result does not start perf or read cache hardware.
With cache counters enabled, an unavailable tool or hardware permission stays
an explicit cache result; CPU/RAM profiling continues. The result retains its
own actual interval and does not change the task's CPU window or polling.
The separate `POST /api/2026-10-24/cache/latency` command accepts `{}` and
does not create a task handle. Its bounds and units are in the cache reference.

The instrument and completed handles exist only in this service process.
There is no disk registry, host-ledger field or request-journal change.
A restart loses its handles. CPU/RAM metadata may be returned by this API,
reported through the existing TypeScript callback or written to structured
stderr; none of these makes it durable request authority.

## Bounds and failures

`config/host-probes.json` owns these controls. The task instrument remains
default-off; its process-RAM and machine-RAM controls are separate.
Neither CPU windows nor polling intervals limit task lifetime.

Table A - task HTTP bounds

| ID | Control | Default and effect |
| --- | --- | --- |
| A1 | `task_profile.max_profile_handles` | 16 entries total, including starting, running, closing and completed profiles. Reservation precedes asynchronous startup. |
| A2 | `task_profile.profile_handle_ttl_ms` | 21600000 milliseconds, or six hours, for the explicit HTTP safety expiry; completed results are retained for at most another such period. `expires_at` exposes the task deadline. |
| A3 | `max_request_body_bytes` | 16384 bytes, or 16 KiB, per JSON command, including streamed bodies. |

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

Invalid JSON or controls return 400; oversized bodies return 413.
Stale process pins return 409, occupied active capacity returns 429,
and an unknown or evicted handle returns 404. A stopping service refuses
new starts with 503. Unexpected collection or report failures log an error
and return 500, not a successful profile. Missing individual measurements
stay null with a reason; a real zero PID CPU interval remains zero.
All responses are uncached.

## Embedded use

The existing `profileTask` wrapper still pins the actual calling PID by
default. `startTaskProfile` also accepts an explicitly pinned `target` and
optional `server`. Its session exposes `target`, `expires_at`, `settled`
and an idempotent `close(outcome, end_reason)` method. `settled` returns
either the validated profile or an explicit error, including automatic
closure. The ordinary wrapper has no HTTP safety expiry and closes only
when its work settles.

An embedded HTTP caller must await the handler's `close()` on service
shutdown. The ordinary host-probe service does this through `stop()`;
its CLI also handles stop signals. Startup reservations, active collectors
and pending closes are included. There is no feed-planner or GitHub
dependency in this lifecycle.

## Design rationale

The commands reuse the independent task collector so synchronous work cannot
block polling. A bounded in-memory owner prevents concurrent starts from
oversubscribing capacity, retains idempotent stops and owns cleanup.
Explicit pins prevent process-name discovery and PID reuse from changing
what a profile measures. Expiry bounds abandoned handles without presenting
an incomplete task as a successful full-task observation.

## See also

- [Host measurements](host-metrics.md)
- [Fetch and parse operator API](../architecture/sources/feed-operator-api.md)
- [Isolated resource proof](../how-to/run-feed-ingest-plan-test.md#resource-proof)
