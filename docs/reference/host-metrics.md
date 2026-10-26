# What the pipeline records about the machine it ran on

**Last Updated**: 2026-10-26

Every host-fingerprint field, what it means and which readings are optional.
The hardware fingerprint is reusable by any pipeline. Callers name their
pipeline, task and shard; no workflow enum or digest-specific identity is needed.
Python collects the production host fingerprint. The independent Bun fingerprint
service writes the same existing host row through the shared TypeScript writer;
it does not replace the production collector. The separate Bun host probe
returns transient CPU and memory samples without writing a ledger. Item resource
readings and diagnostic memory files are separate optional instruments.

Read this when a number surprises you and you want to know which machine
produced it. Runner hardware varies between jobs, so compare measurements only
when their recorded hardware and conditions match.

**The operator console reads it, from 2026-09-17.** Which machines one run was
given, whether some machines do the same work slower, what kinds of machine we
keep being given over a window, and what a task's own clock and its weights
load cost. Which panels draw it today is
[../architecture/publishing/console-machine.md](../architecture/publishing/console-machine.md),
because the panel list is a config file and a count repeated here would go stale
on a config edit. What each may draw and what it may never draw is
[../concepts/console-design.md](../concepts/console-design.md). The browser asks
for declared panel cells through `frontend/src/lib/console/queries/machine.ts`
over the published host ledger. These measurements appear on the
operator console, not on the news-reading pages.

## Where it lives

| | |
| --- | --- |
| Contract | [`backend/idhazh/contracts/host_fingerprint.py`](../../backend/idhazh/contracts/host_fingerprint.py) |
| Schema | `HostFingerprintRow.json_schema()` from the contract above |
| Ledger | The caller's state root, then `raw/host-fingerprint/<YYYY>/<MM>/<DD>/`; compaction uses the matching `compact/host-fingerprint/` path |
| Files | one immutable `<file_id>.parquet` per completed write in the day directory. The reader settles the later whole row of the same work unit; neither file is edited. |
| Producer | [`silicon.py`](../../backend/idhazh/telemetry/silicon.py), through [`task_telemetry.record`](../../backend/idhazh/telemetry/task_telemetry.py), or the independent [`host-fingerprints`](../../services/host-fingerprints/src/index.ts) API/CLI. Both use the existing host ledger and separate pipeline/task identity. |
| Read by | `/console/machine/`, through the browser questions in `frontend/src/lib/console/queries/machine.ts` and shared helpers in `frontend/src/lib/console/machine/records.ts` |
| Key | `date`, `run_id`, `pipeline_name`, `task_name`, `shard`; legacy rows use `job` instead |
| Switch | `observability.host_telemetry_enabled` for the whole instrument; `host_fingerprint` for host-row writes; `host_fingerprint_placement_enabled` for placement metadata in either collector; `memory_profiling_enabled` for memory/page-fault observations only |
| Committed | The caller owns publication of the files returned by the recorder |
| Shown on news-reading pages | **no.** Operator surface only |

**The collector is independent of its callers.** A pipeline may use the shared
recorder or leave host telemetry out. Existing historical readings and recovery
backups are not rewritten.

Python callers can pass `ask_placement=False` to the task recorder or machine-row
writer to omit the external host-placement request while retaining local
collection and ledger writes. The default is `True`; the elapsed-time writer
makes no placement request. Job instrumentation tests use this existing
acquisition choice and refuse entry to the real placement reader, so a missing
forwarding step fails before any network access.

The default-on `observability.host_fingerprint_placement_enabled` setting also
stops placement reads in both collectors when false. A Python caller's
`ask_placement=False` remains a narrower opt-out; neither choice stops local
fingerprint collection or its ledger write.

The manual feed planner workflow starts the fingerprint HTTP service on the
same runner, checks its versioned health endpoint, and posts only date and
writer identity. The caller is pipeline `feed-ingest-plan`, task
`isolated-plan`, shard 0. It uses the committed instrument, placement and
task-selected copy controls without overriding the copy-task list. A
disabled instrument is an explicit skip, with no listener or host write.
The listener stops after success or failure.

The API writes its raw Parquet under the caller's run state root.
`resources.json` retains the exact request, validated row, unavailable reasons
and completed file receipts. The caller checks those receipts against actual
Parquet before adding the host file to the four planner metadata ledgers'
publication and recovery path. Host persistence or validation failure remains
failed evidence, not a fabricated row. Missing hardware stays unavailable.
The Resources report shows L3 and total machine RAM capacity in MiB; stored
`l3_cache_bytes` and the hardware hash do not change. Live task RAM profiling
remains a separate instrument. The independent copy/cache proof also uses the
HTTP API, but its temporary host files are removed rather than published as
real-run observations. See the [commit policy](../architecture/publishing/committing.md#design-rationale)
for validation, retries and the four planner-only day indexes.

Whole-instrument off and memory-only off are different controls. Their exact
configuration, overrides and effects are in [Controls and precedence](#controls-and-precedence).

## Collection and limits

The fingerprint groups hardware characteristics; it is not a unique machine
serial number. Its pipeline/task/run/shard identity says which execution produced the row.
Per-item resource readings live on the item-health row, not in a second copy of
the job fingerprint.

New Python rows use fingerprint algorithm 2. Logical counts come from the online
CPU list, physical counts require complete package/core topology, and target
capacity uses the Python process taking the reading. Missing or contradictory
inputs stay null. A missing frequency entry does not reduce the CPU count.
Item CPU shares are unknown when the aggregate line lacks its four required
counters, any counter resets, or the resulting shares are impossible.

The work stage receives the server PID written by the model-server maintainer. It
checks the PID and the kernel start-time counter before and after each server
status read. An exited or reused PID makes server memory and fault readings
unknown; a job with no server PID records no server process values. Server
status reads name one process and do not search the Python process list.
Individual `/proc` and `/sys` reads stop at 1 MiB; a missing, denied, malformed
or oversized reading stays unknown. Closing an item waits for its sampler to
stop, and repeated closes return the same cells.

Table A - collected measurements

| ID | Capability | Required status | Recorded result and limit |
| --- | --- | --- | --- |
| A1 | Hardware identity | Core | CPU model/vendor/family/stepping, microcode, watched flags, L3 and versioned fingerprint. A fingerprint groups reported characteristics; it is not a machine serial number. |
| A2 | CPU topology | Core | Visible logical processors and fully validated physical cores. Unknown or contradictory source data stays null. See [CPU capability fields](#what-the-processor-can-do). |
| A3 | CPU capacity and frequency | Optional | Affinity/cpuset, quota and frequency observations. Frequency reads are off by default. |
| A4 | Task timing and model counters | Optional | Elapsed task time, model-load time and server prompt counters when the caller has those inputs. |
| A5 | CPU and load over an item window | Optional | Whole-window busy/steal share, busy extrema and closing one-minute load. |
| A6 | Memory and page faults | Optional | Selected process RAM, machine RAM/swap, available-memory minimum and major page-fault delta. |
| A7 | Memory artifacts and copy speed | Optional | Process/sample files, server RSS, cgroup peak and an opt-in copy benchmark. The copy probe allocates two buffers and competes for memory bandwidth. |
| A8 | Ledger writing | Optional | Immutable ledger files through the shared Python or TypeScript writer. A pipeline chooses whether and how to publish its writes. |

The live runtime is Linux with `/proc` and `/sys`, as on the Ubuntu runner.
Windows development or recorded-fixture success does not certify live Linux
collection. Unsupported or missing observations are unavailable, never zero.
Missing observations remain empty cells; collection does not invent a reading.
Memory diagnostics are separate from the persisted hardware fingerprint.

## Independent fingerprint API and CLI

`services/host-fingerprints` collects hardware, capacity, optional frequency,
uptime, placement and the runner label into `HostFingerprintRow`. Its HTTP API
does not accept task timing or model counters. The CLI retains those optional
caller inputs, and the shared ledger retains their fields for other producers.
The service is build-time operator tooling, not a backend for the published site.

`machine_memory_total_mib` is total RAM visible to the Linux kernel at capture,
from `MemTotal` in `/proc/meminfo`. Linux kB means 1024 bytes; division by 1024
gives MiB without rounding. This optional positive number is machine capacity,
not free or available RAM, process memory, a cgroup limit or a task sample.
Missing, malformed, duplicate, oversized or unsupported input leaves it null
with an unavailable reason. Task-memory profiling does not control this capacity
reading. Total RAM is not part of the hardware hash, and `l3_cache_bytes` stays
byte-valued.

From the service directory, run:

```text
bun run src/index.ts --fingerprint --context caller.json --state-root generated-state
bun run src/index.ts --serve --state-root generated-state
```

`caller.json` is an operator-authored input, not fetched article data. Its shape:

```json
{
  "date": "2026-10-21",
  "writer": {
    "run_id": "2026-10-21-123",
    "attempt": 1,
    "job": null,
    "pipeline_name": "fixture-pipeline",
    "task_name": "inspect-host",
    "shard": 0,
    "producer": "telemetry.silicon",
    "git_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "model_load_ms": null,
  "job_seconds": null,
  "server_prompt_tokens": null,
  "server_prompt_seconds": null
}
```

The four trailing cells default to null: the collector does not invent task
timing or model counters. `job` is null or matches `task_name` for a generic
caller. A legacy job-only identity remains valid. Producer `telemetry.silicon`
preserves the existing host work-unit identity; attempts remain separate
immutable writes and normal ledger settlement chooses the later whole row.
Dates and timestamps are UTC. Integer inputs must be exactly representable
JavaScript safe integers; values outside that range fail rather than round.

`POST /api/2026-10-20/fingerprint` takes only `date` and `writer` from that
example. The four timing/model keys are refused with 400 even when null:
`model_load_ms`, `job_seconds`, `server_prompt_tokens` and
`server_prompt_seconds`. API-generated rows leave those existing ledger cells
null; the API neither accepts nor collects them. Success returns
`status: "written"`, the validated `row`, an `unavailable` reason map, and the
shared writer's `files`. Each file's `path` is relative to the caller's state
root, with POSIX separators; no absolute local path is returned. The caller
owns publication. The API writes raw Parquet only: it creates no index and does
not commit, push, compact or deploy. Validation failures return 400; oversized
request bodies return 413. A collection or persistence failure returns 500,
never a row or success-shaped paths. The CLI prints JSON only after persistence,
or exits nonzero and logs the failure on stderr.

`GET /api/2026-10-20/health` reports readiness and the selected instrument
switch without collection or writes. GET on the write endpoint returns 405.
Other methods are refused. Neither endpoint is cacheable. No endpoint accepts
an output path or metadata URL from the request.

`--settings <file>` selects the caller's `idhazh.json`; the committed file is
the default. Both `observability.host_telemetry_enabled` and `host_fingerprint`
must permit collection. Either false returns `status: "disabled"`, `row: null`
and empty files, without host reads or directory creation. The shared
frequency and bandwidth fields remain authoritative. There is no competing
host telemetry setting in the service config.

`--config <file>` selects the authored service controls in
`config/host-fingerprints.json`. Defaults bind loopback on port 3004, limit
each host input and HTTP body to 1048576 bytes (1 MiB), permit at most 8192
online processors, read the eight named cache indices, and inspect at most
64 cgroup ancestor levels. These limits bound one collection; exceeding a host
input limit yields an unavailable reading, not a partial count.
The metadata URL is committed and restricted to the host link-local address;
its default deadline is 2000 milliseconds. Either the selected
`host_fingerprint_placement_enabled: false` or `metadata_url: null` prevents
metadata access and records `configured_off`. A deadline records
`metadata_timeout`; an unreachable transport records `metadata_unavailable`;
a status other than 200 records `metadata_http_<status>`; an invalid or empty
body records `metadata_invalid`; a body above the read limit records
`metadata_too_large`. These failures leave placement null, not the whole
fingerprint unavailable, and do not stop the ledger write.
`copy_repeats` defaults to three real memory transfers, taking their median.
Only tasks selected by the existing observability bandwidth list take that
optional benchmark; the recorded buffer size is derived from L3 and the shared
floor/cache multiple.

Linux reads named proc/sys files only. Online IDs determine logical count;
every online CPU must supply a package/core pair for physical count.
`/proc/self/status` supplies this Bun process's affinity, intersected with
online IDs. Cgroup v1/v2 quota uses the tightest visible ancestor; one missing
or malformed ancestor makes quota unknown. Frequency is optional; incomplete
maximum-frequency coverage is null, never a smaller CPU count. Algorithm 2
hashes only the existing seven static hardware facts using sorted ASCII JSON.
Windows and macOS return unavailable hardware, never invented measurements.

The named Bun checks cover authored Linux-format input transcripts, the
independently recorded full schema/types/nullability and hardware hash bytes,
real API-handler/CLI writes, and real Parquet WASM/Arrow readback. They run no
Python, read no backend source, install no Python package, and do not claim
that a Python reader ran. Backend code is not a TS test/runtime prerequisite.
The schema fixture records the shared row's columns, types, nullability and a
complete value. The named backend contract check
`backend/tests/contracts/test_host_fingerprint_snapshot.py` binds that
snapshot to the actual Pydantic model in CI. The Bun checks use the recorded
snapshot without a Python prerequisite; they do not claim that Python ran.
No test contacts a network: placement replays bounded native response bodies
and transport failures; the CLI placement read is explicitly off. The live-Linux
test runs only on Linux and reports its machine separately; Windows fixture
results do not certify Linux collection or live cloud metadata access.

## Independent CPU and memory samples

`services/host-probes` is an opt-in Bun service, separate from the production
pipeline and the persisted Python instrument. From that directory, run
`bun run src/index.ts --sample` for one JSON response, or
`bun run src/index.ts --serve` for `GET /api/2026-10-20/sample`.
The service does not create hardware identities or write state files.

`config/host-probes.json` owns the sampling interval, listener and read limit.
The defaults wait 1000 milliseconds between CPU snapshots, bind loopback
`127.0.0.1` on port 3005, and read at most 1048576 bytes (1 MiB) per proc file.
Missing or invalid controls fail startup by field name. No environment setting
changes these controls. Each request has its own opening and closing snapshot;
the wait is asynchronous, not a blocking sleep. `interval_ms` reports actual
monotonic elapsed time between those snapshots; `sampled_at` is the closing
observation's UTC instant.

The delay is requested, not a minimum-duration guarantee: timer precision and
scheduling can make the actual interval differ. `interval_ms` is measured from
the monotonic clock, never copied from configuration. Task work is not padded
to turn a partial observation into a full CPU window.

The response contains `cpu`, `memory_kb`, `vmstat`, and an `unavailable` map.
CPU percentages are differences from the aggregate `/proc/stat` line, not
lifetime averages. `user` includes nice time; `system` includes interrupt and
soft-interrupt time. `idle`, `iowait`, and `steal` remain separate. All five
percentages sum to 100 without intermediate rounding. Guest counters are
already included in user/nice and are not counted twice. A reset of any
contributing counter, no elapsed ticks, or invalid input makes CPU unavailable.

Memory `total`, `free`, and `available` come directly from the corresponding
`/proc/meminfo` fields. The `memory_kb` unit is Linux kB, meaning 1024 bytes.
The available estimate is never substituted with free memory. `vmstat` reports
the closing absolute counters `pgfault`, `pgmajfault`, `pswpin`, and `pswpout`
from `/proc/vmstat`: fault counts for the first two and page counts for the
last two. These are neither rates nor process-specific measurements.

Missing, denied, malformed, or oversized inputs produce null measurements and
explicit component/field reasons. Missing memory fields degrade independently.
Unsupported platforms return null observations with `unsupported_platform`,
without waiting for a CPU interval. Unexpected I/O errors fail explicitly:
the CLI exits nonzero and the HTTP server logs the error and returns 500.
Responses are not cacheable and are validated locally. They are transient
API data, not a persisted contract or a replacement for host-fingerprint rows.

`bun test` and `bun run check` in the service cover recorded Linux CPU inputs,
authored bounded memory/vmstat fixtures, real temporary-file interval changes,
the HTTP request handler and the CLI. No test contacts the network. Windows
fixture results do not certify live Linux collection.

## Whole-task TypeScript samples

A task wrapper measures actual work on a separate Bun worker thread, in
`services/host-probes/src/task-profile/task-profiler.ts`.
The thread takes an opening observation before
work, polls until work settles, then takes a closing observation and stops.
Synchronous JavaScript parsing cannot block its polling loop. Repeated closes
return the same result and report it once. Task failures and cancellation still
close the instrument. A cancelled caller does not detach unfinished work: the
wrapper closes when that work settles. Unexpected collector or report failures
are errors, not successful measurements.

`config/host-probes.json` owns three independent task controls:
`task_profile.enabled` starts the instrument, `memory_enabled` permits PID RAM,
and `machine_memory_enabled` permits whole-machine RAM and vmstat reads.
All three default to false. Their declaring schema states their retirement
conditions. Whole off starts no thread and reads no host or process file.
Machine RAM off performs no task meminfo/vmstat reads; CPU and separately
enabled PID RAM still work. PID RAM off does not disable machine RAM.
`cpu_window_ms` and `poll_interval_ms` both default to 1000 milliseconds.
Neither ends the task measurement: the worker observes the entire task.
The former sets the rolling CPU window; the latter requests one poll each
second. They remain independently configurable. Actual intervals can be
longer when collection or scheduling is slow; fast work can finish before
its first periodic poll and still has opening and closing observations.
`max_retained_samples` defaults to 128 observations and must hold the window's
polls plus two endpoints. Both raw CPU history and returned observations stay
bounded. Whole-task counts, extrema and endpoint differences survive eviction.
`lifecycle_timeout_ms` defaults to 10000 milliseconds for starting the collector
and for one closing deadline covering collector shutdown and asynchronous
reporting, not for limiting task duration. The owned collector stops before
the report callback runs. A callback that does not settle fails closing at
that deadline; it cannot keep the collector or HTTP shutdown waiting forever.
An actual-work failure and a reporting failure remain separate errors.

Host CPU remains machine-wide, including other work on the machine.
Whole-task shares use opening and closing counters. Each rolling sample reports its actual
interval and whether it spans the configured window; a short task can have no
full window, or no elapsed CPU ticks. Busy extrema mean user plus system
percentages across measured rolling windows. No wait is added to a task to
manufacture a reading. Observation instants use the real UTC clock and elapsed
time uses a monotonic clock, independent of a caller's frozen planning clock.

Process CPU is separate. It measures the added user and kernel CPU time between
two reads of the same PID and kernel start-time counter. Child-process CPU is
excluded; Linux guest time is not added twice. Counters stay integers until
subtraction, including values larger than JavaScript's exact number range.
Each process uses its own actual monotonic observation interval, not the
requested polling interval or the machine's observation time.

`processes.worker.cpu` and `processes.server.cpu` report the whole-task
`cpu_time_ms` and `percent_one_core`, with `cpu_interval_ms` beside them.
Sampled process `cpu_window` values use the same units over rolling windows.
One fully used core is 100 percent; a multi-threaded PID can exceed 100 percent.
Zero added ticks over a positive interval is a real zero, not unavailable.
Clock ticks are Linux CPU-accounting units. The fixed command
`/usr/bin/getconf CLK_TCK` resolves their rate lazily once per enabled Bun
process, with bounded output and the configured lifecycle deadline. This costs
one Linux system-tool invocation and no npm or Python dependency. The returned
`process_clock_ticks_per_second` records that verified rate or an unavailable
reason; the collector never assumes a rate when it cannot read one.
Very short intervals inherit the counter's clock-tick resolution.

PID CPU collection does not depend on RAM enablement. A missing process status
file makes its RAM unknown without discarding valid CPU counters from its stat
file. A counter reset or PID reuse remains unavailable in the whole-task CPU
result even after its raw sample leaves bounded history. The collector never
rebinds a reused PID. Machine idle time is shared unused time, not guaranteed
task growth capacity: these one-core process percentages do not claim a share
of a verified target affinity or CPU quota.

With machine RAM enabled, total, free and available RAM use the existing probe.
The result also contains sampled minimum available RAM and the endpoint
difference in machine major page faults. Independently enabled process RAM
names the calling PID by default. An optional additional server requires an
operator-supplied PID and its kernel start ticks; there is no process search.
Start ticks are checked before
and after each status read. Exit, PID reuse and missing fields have explicit
reasons and null values. RSS is resident RAM; anonymous RSS is resident
anonymous memory. `hwm_lifetime` is Linux's process-lifetime high-water mark,
not a task peak. `sampled_rss_max_kb` is only the largest observed RSS, not an
exact peak. Process readings include all its threads and
other work in that process; they are not task-exclusive allocations.
An in-process caller also includes its collector-thread overhead.

The [generic task HTTP commands](host-probe-api.md) reuse this collector for
an explicitly pinned external target. In those results, `processes.worker`
names the supplied target, not the probe service. The ordinary TypeScript
wrapper still defaults to the actual calling PID.

Profiles are locally validated transient metadata, separate from hardware
rows and request journals. They retain pipeline, task, run, correlation and
request identity, but no article text or paths. The
[operator API](../architecture/sources/feed-operator-api.md#optional-task-profiles)
defines the actual fetch/parse boundaries. The
[isolated checks](../how-to/run-feed-ingest-plan-test.md#resource-proof)
separate recorded CPU-bound work, live document work, the real RAM HTTP
endpoint and the existing optional copy benchmark. Copying measures median
read-plus-write throughput with two cache-sized buffers; it does not measure
L3 hit or miss counts and runs outside fetch/parse CPU windows.

The separate default-off [cache probes](host-cache-probes.md) measure exact
last-level-cache read events with Linux perf and a native random-pointer-chain
working-set latency curve. Copy throughput is neither of those measurements.
Cache results are transient and do not add fingerprint fields.

The isolated workflow's `profile_machine_memory` checkbox defaults false.
When selected, it enables the existing profiler around the whole real HTTP
planner invocation and separately selects the controlled sample/copy/cache
proof. It does not enable per-document profiles or a resource ledger. Global
`host_telemetry_enabled` still controls collection; `memory_profiling_enabled`
still controls process and machine RAM. The fingerprint and placement switches
also govern the basic actual-host observation.

The job summary and one grouped Resources notice combine actual host facts,
the live planner process and the separate controlled proof, with each scope
labelled. The planner and listener share one PID. An absent separate-server
PID means there is no second process to measure, not that the HTTP API is down.
No process is counted twice. CPU values include all work in the measured PID.

RAM display uses decimal GB: 1 GB is 1,000,000,000 bytes. Linux proc `kB`
values remain KiB in the stored readings and are multiplied by 1,024 before
display. Free RAM and available RAM each show `X.XX GB / Y.YY GB total
(NN.nn% free)` or `(NN.nn% available)`. Available RAM includes reclaimable
cache; free RAM does not. The lowest observed available RAM describes only
sampled observations, never an assured whole-run minimum. Its percentage is
unavailable if the corresponding total was not retained.

`resources.json` holds the validated actual-host and live-process evidence;
the separate `resource-proof.json` describes controlled work. Missing,
disabled, failed and unsupported readings retain their reasons, never zero
or successful collection. No sample dump enters the summary or notices.
Reporting off reads no evidence and writes no summary or annotations. These
transient inputs add no native host fields, durable request fields or ledger.

## Controls and precedence

The normally selected shared file is `config/idhazh.json`. A workflow that
prepares a candidate configuration uses that selected configuration instead.
"Shared" means these jobs read the same setting, not that data is sent elsewhere.
A major page fault is a memory page retrieved from storage, not an application
error or crash. Enabling collection attempts these readings; it does not make an
unavailable source measurable.

Table B - whole-instrument selection

| ID | Setting | Meaning |
| --- | --- | --- |
| B1 | `observability.host_telemetry_enabled: true` | Allow host collection in either collector. This is the committed default. |
| B2 | `observability.host_telemetry_enabled: false` | Stop host collection for every caller; no workflow choice can override it. |
| B3 | Caller uses `task_telemetry.record` | Collect through the shared Python API with separate pipeline, task and shard identity. |
| B4 | Caller does not record, or a workflow wrapper selects `off` | Leave host telemetry out for that invocation without changing stored data. Workflow dispatch controls are optional wrappers, not part of the recorder contract. |

Table C - controls inside an enabled instrument

| ID | Setting | Enables or stops | Does not control |
| --- | --- | --- | --- |
| C1 | `memory_profiling: inherit` | Read `observability.memory_profiling_enabled` from the selected `idhazh.json`; the committed value is true | Collector choice and the master switch |
| C2 | `memory_profiling: on` | Enable OS memory, major page-fault and memory-artifact collection for the invocation | CPU/load collection or the separately selected copy benchmark |
| C3 | `memory_profiling: off` | Stop those memory/fault observations; leave their cells unavailable | CPU/load, timing, identity, heartbeat, item health or memory copying |
| C4 | `observability.host_fingerprint: false` | Stop raw job fingerprint writes/probes | The complete resource monitor or per-item memory/CPU observations |
| C5 | Empty `host_fingerprint_bandwidth_jobs`, or zero `host_fingerprint_bandwidth_floor_mib` | Stop the copy benchmark | Other host observations |
| C6 | `observability.host_fingerprint_placement_enabled: false` | Stop placement metadata reads in either collector; leave those cells empty | Local host readings, the fingerprint row or its task clock |

The master false value or caller's off choice wins first. Memory on cannot
restart a disabled instrument. Whole off skips host readings, raw host
writes and host-memory artifacts. It keeps work, item health and progress
logging. No setting deletes existing readings.

Placement metadata requires the configured switch. Python also requires the
caller's `ask_placement` choice. Either false value skips the external read;
true in the config cannot override a caller opting out, and a caller's
default-on cannot override config opting out.

Set the master field to false to stop collection for every caller:

```json
"host_telemetry_enabled": false
```

Changing `memory_profiling_enabled` to false is not equivalent: CPU/load
telemetry remains enabled.

**Memory-copy measurements are opt-in per task.** Set
`observability.host_fingerprint_bandwidth_jobs` in `config/idhazh.json`.
The default is `[]`. Use the task name in this list to enable the benchmark for
that task; use `[]` to keep it off everywhere. The machine identity and core
hardware fields still record when the copy is off. An unselected task has
`memcpy_probe_mib=0` and an empty `memcpy_gib_s`. The buffer floor also disables
copying when it is zero.

**Any pipeline can record its task.** Use
[`task_telemetry.record`](../../backend/idhazh/telemetry/task_telemetry.py)
around the work, passing the pipeline name, task name, shard, run identity,
loaded settings and state root. Pipeline and task names are separate validated
strings, not workflow enums. The recorder writes the opening host row and
closing task clock through the shared ledger, and returns the exact paths for
the caller's publisher. A work failure still runs the closing step. The caller
owns publication and may omit this optional instrument entirely.

New generic rows store `pipeline_name` and `task_name` as separate columns and
leave legacy `job` null. Aggregations combine the names when they need a unique
task key. Existing job-only rows keep their `job` values and remain readable.
Readers compare a legacy job's text value, not its Python enum identity.
The host and item-health ledgers join generic rows on date, run, pipeline, task
and shard; legacy rows join on date, run, job and shard. No historical row is
rewritten or relabelled.

The file envelope, which records who wrote a ledger file, has its own version.
Its pipeline and task columns are declared from envelope version `2026-10-12`.
The site check uses that version for added writer columns and the row's version
for its own fields. An older file can lack the added writer columns without a
rewrite; a current file cannot.

The Hardware page keeps generic host identity separate from the legacy job
field. Its fleet list combines pipeline and task only for display. A generic
host row covers a reported shard only when an item row matches its date, run,
pipeline, task and shard; otherwise the item-backed placement remains visible.

**It files by day, and that is the shape the read wants.** A host record only
earns its keep when somebody counts across many days, and a day tree is the
shape a bounded window can read (Guardrail #12).

**The item-health ledger can refer to a host row without copying its hardware.**
Generic rows join on date, run, pipeline, task and shard. Legacy rows use the
job and shard fields:

```sql
SELECT ih.item_id, hf.fingerprint, hf.cpu_model, hf.microcode, hf.flags
FROM item_health ih
JOIN host_fingerprint hf
  ON hf.date = ih.date AND hf.run_id = ih.run_id
 AND hf.shard = ih.machine_shard
 AND (
      (ih.machine_pipeline_name IS NOT NULL
       AND hf.pipeline_name = ih.machine_pipeline_name
       AND hf.task_name = ih.machine_task_name)
      OR (ih.machine_pipeline_name IS NULL AND hf.job = ih.machine_job)
 )
```

**What a machine WAS is here; what it HAD at the moment is on the item row.**
This table is taken once a job and holds the parts - the processor, its cache,
its flags. Memory moves inside a job, so it is sampled per item instead: six
`os_` columns on the item-health ledger carry what `/proc/meminfo` said, including
the lowest headroom seen while the model worked on that one item
([../architecture/sources/item-health.md](../architecture/sources/item-health.md#what-the-machine-had-against-what-a-process-held)).
Neither table repeats the other's cells.

Set `observability.memory_profiling_enabled` to false to disable OS process and
machine memory, major-fault, job-rollcall and runtime-memory artifact collection.
The command-line override is `--memory-profiling on|off`; workflow dispatches use
`inherit|on|off`. False leaves memory and fault cells empty with a disabled
reason. It does not stop CPU/load collection, process start-tick identity,
heartbeat, the item census or the separately controlled memory-bandwidth copy.
The whole-instrument off control bypasses collection and keeps only the
waiting heartbeat.

## Identity

| Column | Type | What it is |
| --- | --- | --- |
| `version` | date stamp | The schema generation this row was written under |
| `date` | `YYYY-MM-DD` | The run's date |
| `run_id` | run id | The run |
| `pipeline_name` | validated string? | The generic pipeline identity. Paired with `task_name`; both are absent on legacy rows |
| `task_name` | validated string? | The generic task identity. Paired with `pipeline_name`; both are absent on legacy rows |
| `job` | legacy enum or string, nullable | The old workflow identity. New generic rows store null |
| `shard` | int, 0+ | The shard inside the task. A single-shard task writes 0 |
| `fingerprint` | 16 hex characters? | A digest over the hardware cells that do not depend on the execution |
| `fingerprint_version` | 1 or 2? | The digest algorithm; null exactly when the digest is null |

**`fingerprint` is countable only with `fingerprint_version`.** New Python rows
use algorithm 2, which digests vendor, family, model, stepping, model name, L3
and watched flags only. Counts, target constraints, frequency, placement and
clocks are excluded. Existing algorithm 1 and 2 rows keep their original labels
and values; no historical row is rewritten or replayed. Consumers group by the
pair `(fingerprint_version, fingerprint)`; equal digest text under versions 1
and 2 does not establish continuity.

**The closed `job` vocabulary is for legacy rows only.** A generic caller stores
`pipeline_name` and `task_name` as separate validated strings and leaves `job`
null. The ledger combines the pair only when it needs one unique task key.

## What the processor is

Every cell here is the host's own report from `/proc/cpuinfo`. None of it is a
codename anybody recognised.

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `cpu_model` | string? | The `model name` line | The label a person recognises |
| `cpu_vendor` | string? | `vendor_id` | Splits the fleet at the coarsest level |
| `cpu_family` | int? | `cpu family` | With model and stepping, names the part exactly |
| `cpu_model_number` | int? | `model` | The number, not the marketing name |
| `cpu_stepping` | int? | `stepping` | Two machines with one model name can differ here |
| `microcode` | string? | `microcode` | Moves under a fixed stepping, so a performance change with no other change shows up here |

**Two machines reporting the same `cpu_model` are not the same machine.** Four
draws all reporting AMD EPYC 7763 differed by 8.8 percent on decode. Family,
model and stepping are the columns that can say why, and `microcode` is the one
that moves without anything else moving.

## What the processor can do

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `flags` | string | The watched instruction-set flags, sorted, space joined | **The cell that tracks prefill.** llama.cpp dispatches to a different kernel when the wider instructions are there |
| `cpu_physical_cores` | int? | Unique validated package/core pairs across online CPUs | Visible topology; unknown when topology is partial or contradictory |
| `cpu_logical_processors` | int? | Validated online CPU cardinality | Denominator for whole-machine load and busy processor-seconds |
| `cpu_allowed_processors` | int? | Online processors allowed to the measured target by affinity and effective cpuset | Target constraint, never the monitor's own mask |
| `cpu_quota_cores` | float? | Minimum finite target cgroup quota/period across visible ancestry | Fractional and separate from affinity |
| `cpu_quota_state` | `finite`, `unlimited`, `unavailable`? | Meaning of the target quota read | Distinguishes verified unlimited from unreadable and unmeasured |
| `cpu_target_measured_at` | UTC timestamp? | Frozen target-constraint capture | Null when no target was measured |
| `l3_cache_bytes` | int? | L3 as the kernel reports it | Ranges 32 MiB to 480 MiB across the fleet, and **it is what sizes the bandwidth probe.** Read it beside `memcpy_probe_mib` |

**`flags` holds only the flags in `WATCHED_FLAGS`**, which is a fixed tuple in
the contract: the AMX, AVX-512, VNNI, FMA and SSE entries an inference runtime
dispatches on. A raw `flags` line is two hundred words and most of it says
nothing about throughput. Adding one to the watched set is a code change and not
a schema change, which is the trade: the column stays a fixed width, and the
vocabulary lives in the contract rather than in the schema.

**An empty `flags` is a reading, not a gap.** The machine we draw most, the EPYC
7763, reports none of the watched AVX-512 entries at all.

`cpu_logical_processors` counts IDs in `/sys/devices/system/cpu/online`, so
sparse IDs count as processors and do not imply missing CPUs. A physical count
is recorded only when every online CPU has a valid package and core ID.
`cpu_allowed_processors` is the online intersection of the measured Python
process's effective affinity mask; that mask already includes its cpuset.
`cpu_quota_cores` is the tightest valid quota found from the process cgroup up
through its visible ancestors. A denied, missing or malformed ancestor makes
the quota unavailable rather than treating it as unlimited.

## What the processor will not tell us

**A host fingerprint contains no cache event counts or cache occupancy.**
The [optional transient instrument](host-cache-probes.md) attempts exact
last-level-cache events on the actual host. A denied or unsupported instrument
is unavailable, not a zero count. It does not change this persisted record.

Read on `ubuntu-latest` on 2026-09-20 by a dispatched job that ran the six
`/proc` and `/sys` reads below, on three draws of image `ubuntu-24.04`
20260907.300.1, kernel `6.17.0-1022-azure`. An AMD
EPYC 9V74 80-Core and an AMD EPYC 7763 64-Core answered all six reads
identically; an Intel Xeon Platinum 8573C answered the first two the same way.

```
$ cat /proc/sys/kernel/perf_event_paranoid
4

$ ls /sys/bus/event_source/devices/
breakpoint
kprobe
msr
software
tracepoint
uprobe

$ ls /sys/bus/event_source/devices/cpu/events/
-> no such directory

$ ls -d /sys/fs/resctrl
no resctrl

$ grep -om1 rdt_a /proc/cpuinfo
no rdt_a

$ grep -om1 cqm_occup_llc /proc/cpuinfo
no cqm
```

Those draws did not expose a usable hardware counter source. That observation
does not settle another image or pool, and a single named sysfs directory is
not a portable capability test: some processors expose different PMU names.
The optional instrument attempts its exact events and reports the actual
tool, permission or event refusal. It never changes `perf_event_paranoid`,
requests elevated counter privileges or alters kernel security.

**Cache occupancy through the resource-director interface is gone the same way.**
`/sys/fs/resctrl` is not mounted and `/proc/cpuinfo` carries neither `rdt_a` nor
`cqm_occup_llc` - which is what a host keeps to itself when it isolates tenants.
Even where it answered, the reading would vary by draw, because the L3 sizes
recorded above span 32 MiB to 480 MiB, so it could not be compared across a run.

**What this reading cannot settle:** whether a different runner image, or a
different pool, would answer differently. It names the image and the kernel it
read, so the next person can tell whether they are asking the same machine.
Three draws across two vendors answering identically is the reason it is written
down once rather than retaken per draw.

## Why the model server's memory mark reads lower than it did

`llama_rss_peak_bytes` on the item row is `VmHWM` for the model server, and one
server serves a whole shard - so a figure that goes down from one item to the
next says something is wrong. It goes down in every shard. **Almost all of that
is the rows being read in an order the mark was never taken in, and the small
remainder is the kernel's own rule for what `VmHWM` prints.**

Measured 2026-09-20 over the whole committed `state/item-health/` tree by
[`backend/utilities/server_memory_mark.py`](../../backend/utilities/server_memory_mark.py)
- 1,250 rows carrying the mark, over 28 day files and 68 jobs. Exact counts over
committed files, so no spread.

| Rows read in this order | Pairs | Falls | Jobs with a fall |
| --- | --- | --- | --- |
| `item_started_at` - where the fetch loop reached the item | 1,182 | 277 | 68 of 68 |
| `item_ended_at` - where the mark was read | 1,182 | 15 | 13 of 68 |

**The row carries two clocks and they are two different orders.** The work stage
fetches every item and then runs the model over them sorted by source length, so
`item_started_at` is the fetch loop's order and the mark is read one statement
before `item_ended_at` is stamped. 1,144 of the 1,250 rows sit at a different
position under the two. Read on the fetch clock, 95 percent of the falls are an
item's mark compared against an item whose mark was taken later.

**The 15 that survive are the kernel, not a restart.** Every one of them has the
server holding within 0.75 percent of the resident set it held on the row
before - a restarted server has given the weights back and reads a fraction of
12 GB - and every drop is a whole number of 4 KiB pages, between 136 KiB and
620 KiB. Meanwhile the server's current resident set falls in 324 of the same
1,182 pairs, worst drop 566 MB, so the machine is taking pages back from it all
the time.

`VmHWM` is the larger of the current resident set and a stored mark the kernel
refreshes only when the process itself gives memory back. It never reclaims
into that stored mark. So a resident set that climbs, gets read, and is then
reclaimed before any unmap records it leaves the next read lower than the last
one. The archive shows the outside of that rule directly: the mark reads below
the current set on 0 of 1,250 rows, and equals it exactly on 298.

**What this reading cannot settle:** the row does not store the server's process
id or start-time counter, so old rows cannot be checked again for process
identity. New reads validate both while collecting; a restart or reused PID
leaves the affected cells unknown. This still says nothing about how much of
the mark is weights against working memory - there is no per-region reading
here.

**The committed rows are not wrong; the column's description was.** Every value
is what `/proc/<pid>/status` printed at that item's two boundaries, highest of
the two. What was wrong was the sentence beside it, which said "peak resident
memory of the model server over the item" - it is not scoped to the item, and it
is not a peak that only rises.

## What the machine was doing when we asked

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `cpu_observed_mhz` | float? | Mean valid `cpu MHz` sample across online processors | A point sample, never a sustained rate; legitimate legacy averages migrate here |
| `cpu_reported_max_mhz` | float? | Maximum validated `cpuinfo_max_freq` policy value with full online coverage | Reported hardware maximum, never inferred from the observed sample |
| `boot_seconds` | float? | Uptime when the probe ran | A small number is a freshly started machine with a cold page cache; a large one was pooled and handed to us. **Every machine drawn so far is the first case**: 156 s to 2,277 s, median 227 s, over 65 rows |
| `memcpy_gib_s` | float? | Large-block copy rate, bytes read plus written | **Decode is bandwidth bound and this is the only bandwidth reading anywhere** |
| `memcpy_probe_mib` | int? | The buffer each side of the copy used, as used rather than as configured | Says whether `memcpy_gib_s` measured memory or cache |

**`memcpy_probe_mib` is why `memcpy_gib_s` can be trusted.** A buffer that does
not clear `l3_cache_bytes` measures cache, and reads several times higher than
memory. The two columns sit side by side so nobody can read one for the other,
and `observability.host_fingerprint_bandwidth_floor_mib` sets the floor - **zero
switches the probe off and leaves the rate empty**, which is different from a
rate of zero.

**The probe sizes itself against the machine, from 2026-09-20.** The buffer is
the larger of that floor and
`observability.host_fingerprint_bandwidth_cache_multiple` times the L3 this
machine reports, so a part with more cache than anybody has drawn cannot quietly
turn the reading into a cache reading. There is no longer a sentence here asking
a person to raise a constant when a bigger part arrives. What it costs: on a
machine reporting 480 MiB the probe holds two buffers of 960 MiB, so 1.9 GiB of
the runner's 16 GB, taken before the model server starts.

**The console grades a committed row by that same value, and withholds the rate
of a row that falls short of it.** One number rather than two, because a probe
and a page holding separate copies of it could disagree, and the page would then
refuse a row the probe wrote correctly. A withheld rate is not printed at all:
the card says what buffer was used against what cache, how many times it was, and
how many times it had to be.

**A row divides `memcpy_probe_mib` by `l3_cache_bytes` to grade its own rate**,
and rows written before that date do not survive the division. Measured
2026-09-20 over the 60 rows then committed under `state/host-fingerprint/`,
exact counts over committed files and therefore carrying no spread:

| L3 reported | Buffer / cache | Rows | Rate, min / median / max GiB/s |
| --- | --- | --- | --- |
| 32 MiB, AMD EPYC 7763 | 16.00 | 52 | 29.40 / 40.39 / 48.57 |
| 48 MiB, Intel Xeon 8370C | 10.67 | 1 | 25.02 |
| 260 MiB, Intel Xeon 8573C | 1.97 | 4 | 21.96 / 23.17 / 26.42 |
| 480 MiB, Intel Xeon 6973P-C | 1.07 | 3 | 24.44 / 25.08 / 26.08 |

The buffer is 512 MiB on all 60, so the seven rows in the last two lines are the
ones a reader cannot grade. **Their rates are the seven slowest of the 60, not
the fastest**, which is the opposite of what a cache-resident buffer would do -
so the undersized margin is a reason to distrust those figures rather than
evidence that they were inflated. The likelier reading is that these two Xeon
parts are simply slower per allotted processor than the EPYC 7763, and the
probe cannot say so while its own buffer is in question.

## Where the platform put us

| Column | Type | What it is |
| --- | --- | --- |
| `vm_size` | string? | The platform's own name for this machine size |
| `vm_location` | string? | The region |
| `vm_zone` | string? | The availability zone, where one is published |
| `vm_fault_domain` | string? | The fault domain, which separates one rack from another |
| `runner_name` | string? | The runner label the platform gave the job |
| `measured_at` | timestamp? | When the probe ran |

These four come from the host metadata service on a link-local address. **They
are the placement decision in the platform's vocabulary rather than ours**, which
is the only way to ask whether "a lottery" is really "which pools we draw from".
A machine that does not answer records nothing, which is every developer machine.

`fingerprint` and `measured_at` are the two cells that carry a question mark
because of the second half: the half a job writes at its end measured no machine,
so it names none and stamps no probe time. A compacted row carries both, because
the probe's half is where they come from.

## What the job cost

The half written at job end. Every reading comes from the workflow - one from a
step that ran before the checkout existed, one from the log of the server this
job started, one from that server's own `GET /metrics` body - so a run of the
stage anywhere else records none of them.

| Column | Type | What it is | What it is for |
| --- | --- | --- | --- |
| `model_load_ms` | float? | Milliseconds the server spent opening the weights before the first item | The fixed cost `run.shard_size` exists to amortise. Measured 1.1 to 1.5 percent of a work shard's fixed cost |
| `job_seconds` | int? | The job's own wall clock, first step to the clock write | **The cell the truncation-cap rollback reads.** Before it, that number lived only in the GitHub jobs API, which drops a job record when the run ages out |
| `server_prompt_tokens` | int? | Prompt tokens llama-server itself counted reading, cached tokens excluded | **The second instrument.** The item ledger's own answer is `sum(input_tokens) - sum(cached_tokens)`, and arithmetic over that ledger cannot check that ledger |
| `server_prompt_seconds` | float? | Seconds llama-server itself counted reading prompts | The other half. A rate is a ratio, and the 80 percent defect this check caught in August 2026 was in the numerator, so one cell alone could not see it |

**`job_seconds` is a floor on the task's wall clock and never a ceiling.** The
steps after it - the ledger push, log summaries and artifact uploads - are
outside the window. A caller that records the closing clock can populate it;
server counters remain empty unless that caller supplies their source files.

**`server_prompt_tokens` and `server_prompt_seconds` are the only two cells on
the site that can disagree with the item ledger.** Everything else that answers
"how fast did this run read?" is arithmetic over the item-health ledger, and a sum
over a ledger cannot tell you the ledger is wrong. These two come from a counter
the model server kept on its own, so the two answers are independent - which is
what let a 0.746 percent drift on one article be seen at all. The bound is 5
percent and it is not a `config/` knob: tuning it is how a failing check is made
to pass.

**These cells sit here and nowhere else, and that is on purpose.**
`state/runtime-counters.csv` carried a second copy of them until 2026-09-20. The
clock parser lives in
[`silicon.py`](../../backend/idhazh/telemetry/silicon.py), beside the writer.
Python owns each invocation's host row.

## Identity names

Generic pipeline and task names are validated lowercase strings, not enum
members. This lets another pipeline use the same writer without changing a
shared vocabulary. The trade-off is that the schema checks their shape, not
whether a pipeline exists. Legacy `job` values remain readable and retain their
closed vocabulary where it applies. Hardware values stay open because vendors
and cloud providers can add them without notice; rejecting a new value would
discard the reading the fingerprint exists to capture.

`flags` is a fixed set - `WATCHED_FLAGS` - stored as a space-separated string
to keep one column. Its full vocabulary lives in the contract.

## Design rationale

**The HTTP API collects hardware, not work done by its caller.** Maintainer
ruling, 2026-10-26 UTC: remove timing/model inputs from the HTTP API only, with
no request migration. The CLI, Python producers and persisted ledger keep those
fields and their existing consumers. Total machine RAM is an optional addition
to the shared row; unmeasured historical capacity stays null. No compatibility
migration, historical rewrite or replacement metrics ledger is introduced.
Placement is optional and its failure cannot discard local hardware or a
completed write. The API creates no host index; publication remains the caller's
responsibility.

**The independent collector shares the existing persistence stack.** Zod
validates caller context and the full host row; the existing
`packages/ledger-file-writer` supplies identity, typed Arrow columns, Parquet
WASM serialization and atomic persistence. There is no second Parquet
implementation or HTTP framework. The cost is installing the existing Arrow
and WASM runtime assets with this operator tool; none enter the browser bundle.
The service's direct Arrow/WASM development dependencies support independent
readback tests, not a second writer. TypeScript and Bun declarations are
development-only costs.

**A transient CPU sample retains the complete observed interval.** The Bun
response keeps steal as a fifth bucket rather than hiding it inside idle or
renormalizing the four requested buckets. The service reuses Zod for local
validation and Bun's native HTTP server; there is no extra server framework
or browser bundle. TypeScript and Bun type declarations affect development
installs only.

**A task record describes only the task that took it.** A collector does not
claim that its runner measured another pipeline or task. The caller decides
where to place the shared ledger and which exact writes its publisher commits.

The recorder accepts separate pipeline and task names plus a shard. Those
columns form the generic identity; a unique ledger unit combines them only
where a single key is required. Old job-only rows keep their original identity.
The opening hardware row and closing clock share one work-unit identity, so the
later file completes the row rather than adding a second task record. Each write
is an immutable file through the shared ledger, and the reader settles attempts
using the common rules in
[Persistence](../architecture/contracts/persistence.md#the-two-identifiers).

**Platform placement is an independent opt-out.** Maintainer ruling,
2026-10-24: keep placement collection on by default, but let the operator stop
the external metadata request in the selected config while local host
collection and ledger writes continue. A caller may still opt out for one task;
neither control may defeat the other.

## See also

- [../concepts/telemetry.md](../concepts/telemetry.md) - the instrument as a whole, and the two finer grains this sits beside.
- [pipeline-cost.md](pipeline-cost.md) - the instrument log.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #10 (a number carries its hardware) and Guardrail #12 (a growing read declares itself).
