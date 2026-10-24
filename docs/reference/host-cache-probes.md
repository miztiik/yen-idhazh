# What optional cache probes measure

**Last Updated**: 2026-10-24

The TypeScript host probe separates last-level-cache event counts from a
controlled working-set latency curve. Neither is the existing memory-copy
benchmark. No cache result changes a host-fingerprint row or a Python contract.
L3 means the third-level cache; the last-level cache is called LLC and is not
necessarily L3 on every processor.

Native latency, integrated HTTP routing, verified affinity and complete owned
cleanup have real Linux evidence with the Python-free build. Actual LLC
counter access remains unavailable on the measured runner; detecting that
refusal is not evidence that a counter was measured.

## Instruments and interpretation

Linux `perf stat` attaches only to an explicit operator-owned PID and its
kernel start ticks. The selected events are `LLC-loads:u` and
`LLC-load-misses:u`: the kernel's last-level-cache read access and miss aliases,
restricted to user-space execution. Their hardware mapping is processor
dependent. They are not generic `cache-references` or `cache-misses`, and are
not automatically direct L3 accesses or hits.

The result retains each exact event name, support status, unscaled count,
running nanoseconds and the reported running percentage. Enabled nanoseconds
are an estimate derived from that percentage, which perf rounds to
0.01 percent. Reported multiplexing means the event shared hardware counters
and was not running for the full enabled interval. A displayed 100 percent
means multiplexing was not reported at that precision, not proof that it was
impossible. No hit rate is inferred from unrelated events.

The target is pinned by PID and start identity, not moved to another CPU.
The scope is its existing threads, without inherited descendant counters.
Threads created after attachment are not included.
Work elsewhere in that process is included. Control acknowledgements bound
the actual observation interval; the counter's running time is also retained.
Exit, PID reuse and a different owner produce explicit unavailable results.
Only the probe's own perf subprocess can be stopped; the target is never
signalled.

`multichase` reads an address, then uses it to find the next address in a
randomized order. This dependent pointer chain runs at each configured working
set. Chain construction writes the pointers before timing. The tool
inherits one allowed CPU selected through the native `taskset` command. The
adapter verifies the owned child's actual single-CPU mask after native output
begins; it does not report the parent's mask as an observation of the child.
The tool pins its benchmark thread within that inherited mask, drops its initial
500 millisecond warm-up sample, and reports nanoseconds per load.
The adapter retains the actual working set, stride, reported native page size,
translation-locality range, individual readings, mean, benchmark PID/start
identity and interval.
The translation-locality range groups nearby addresses to limit address
translation overhead; it does not remove that overhead.

This is a cache-working-set latency curve, not a direct L3 hit latency.
Translation, prefetch, processor frequency, scheduling and memory placement
can affect it. The proof pairs it with the existing fingerprint's CPU,
capacity and L3 context, rather than collecting another hardware identity.
The standalone response names its kernel and architecture. Pair it with the
existing collector's hardware row from the same machine when comparing hosts.
It records whether the largest measured working set exceeds the reported L3.

## Controls and bounds

`config/host-probes.json` owns `cache_probe`. Both
`counters.enabled` and `latency.enabled` default to false. The declaring schema
names their retirement conditions. Off starts no native process and reads no
host or target file.

The controls bound concurrent measurements, combined subprocess output,
control acknowledgement time, counter duration, latency duration, working-set
count and working-set bytes. Requests do not supply programs, commands, event
expressions, paths or tool arguments. Events come from a closed validated list;
numeric PIDs must identify an owned process before perf starts.
Cancellation, output overflow, timeout and shutdown close owned subprocesses.
The default counter ceiling matches the task API's six-hour safety expiry.
If an operator selects a shorter ceiling, `completion: "duration_limit"`
and the measured interval identify partial coverage, not full-task counts.

The default curve spans 4 KiB through 1 GiB, using a 64 byte stride and at most
256 KiB of translation locality. It takes two measured samples per point after
the tool's discarded warm-up. The total latency deadline is 30 seconds.
This allocation is separate from the copy benchmark and task CPU windows.

## Operator HTTP commands

The existing [task API](host-probe-api.md) owns counter start, stop, automatic
closure and handle retention. There is no second PID router. With the task
instrument and `cache_probe.counters.enabled` on, start returns a separate
`cache_counters` object: either `started`, or an explicit instrument result.
Work starts only after that reply. Stop returns the final `cache_counters`
beside the unchanged CPU/RAM `profile`. Repeated stops return the same bytes.
A hardware refusal does not stop CPU/RAM profiling or invent cache counts.
An ended start request does not own the counter's later lifetime; its task
handle does.

`POST /api/2026-10-24/cache/latency` accepts only the JSON body `{}`.
It uses `Content-Type: application/json` and rejects browser origins, as the
task commands do. All benchmark choices come from committed configuration.
The reply is `CacheLatencySchema`, including its calendar version, status,
reason, method and actual readings. This separate request does not start a
CPU/RAM task profile.

The shared `max_request_body_bytes` bounds both commands. Latency bodies, and
task-command bodies when cache counters are enabled, also use
`cache_probe.lifecycle_timeout_ms` as their read deadline. The native-tool
deadline is separate. One shared `max_concurrent` limit covers counters and
latency; occupied capacity gives a typed `concurrency_limit` refusal.

Missing tools, denied performance monitoring, unsupported events, malformed
output and unusable affinity are typed unavailable reasons. Missing
measurements have no numeric values; zero is not a substitute.
The service does not lower `perf_event_paranoid`, request a privileged runner,
change kernel security, or run counters as root.

## Linux proof and optional installation

The existing resource proof explicitly enables these controls in memory.
Ordinary service configuration remains off. The existing PR CI and isolated
Linux workflow install only the declared optional tools in
`config/host-cache-tools.json`. The isolated workflow remains manual and has
no new input.

`perf` is built from a pinned official Linux source revision, not installed
from the distribution's perf package. `NO_LIBPYTHON=1` disables its Python
support and `NO_JEVENTS=1` omits Python-generated vendor event tables.
The two requested LLC aliases remain native builtins. Both Python tool
variables name the system's failure command, so an unexpected invocation
cannot silently use an interpreter. The build's execution trace must show
zero Python executions, and the resulting ELF library list must not contain
libpython. Only the native executable is installed, never a Python extension.
The initial distribution package was rejected after inspection found its
CPython extension; linking alone was not its full cost.

`multichase` is Apache-2.0 software built at the committed upstream revision
with GCC, make and Perl. Flex and bison build perf's native parsers; strace
verifies its build executions; binutils verifies ELF dependencies; util-linux
provides taskset. These are optional CI/measurement dependencies, not default
service or browser dependencies.
The installation records elapsed seconds and the actual perf and multichase
binary byte counts, added OS packages and perf's actual ELF dependencies.
The measured setup and native bytes are in the current benchmark record.
It adds no Python package, default npm dependency,
browser asset or committed binary. Missing or failed installation fails the
proof rather than fabricating an instrument.

A runner can refuse all hardware counters. Its refusal verifies detection
and API behavior, not cache hit/miss measurement. Actual counters then remain
pending on an operator-controlled Linux host that already exposes the
hardware performance-monitoring unit and permits these user-space events for
an owned PID. No permission change is part of this feature.

The [current native reading](benchmarks/cache-working-set-latency.md) names
the machine, method and limits. The CI resource proof wrote
`resource-proof.json`; its validated counter refusal and latency result are
copied into the two named recordings under `tests/fixtures/host-probes/`.
Those fixtures test parsing and missing-value behavior without contacting
the network or claiming a live measurement.

## Design rationale

The mature native tools own event access and pointer-chase execution.
The TypeScript code validates and controls them; it does not implement another
native benchmark. `lat_mem_rd` uses a fixed-stride chain that can be affected
by stride-sensitive prefetch, so it does not satisfy the random-chain method
used here. The two instruments remain independently optional because task
event counts and a controlled latency curve answer different questions.

## See also

- [host-metrics.md](host-metrics.md) - existing CPU, memory and hardware context.
- [host-probe-api.md](host-probe-api.md) - the shared task lifetime and PID commands.
- [../how-to/run-feed-ingest-plan-test.md#resource-proof](../how-to/run-feed-ingest-plan-test.md#resource-proof) - isolated proof boundaries.
- [../../config/host-cache-tools.json](../../config/host-cache-tools.json) - optional Linux tool dependencies.
- [perf stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html) - event, control and output semantics.
- [multichase](https://github.com/google/multichase) - established native pointer-chase tool.
