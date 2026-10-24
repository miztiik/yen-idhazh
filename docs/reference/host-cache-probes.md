# What optional cache probes measure

**Last Updated**: 2026-10-24

The TypeScript host probe separates last-level-cache event counts from a
controlled working-set latency curve. Neither is the existing memory-copy
benchmark. No cache result changes a host-fingerprint row or a Python contract.

**Status: in progress.** The bounded native-tool adapters are implemented.
Task API integration and actual Linux runner evidence remain to be verified.
Counter availability is not evidence that any counter was measured.

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
Work elsewhere in that process is included. Control acknowledgements bound
the actual observation interval; the counter's running time is also retained.
Exit, PID reuse and a different owner produce explicit unavailable results.
Only the probe's own perf subprocess can be stopped; the target is never
signalled.

`multichase` runs one native dependent random pointer chain at each configured
working set. Chain construction writes the pointers before timing. The tool
pins its own benchmark thread to its first allowed CPU, drops its initial
500 millisecond warm-up sample, and reports nanoseconds per load.
The adapter retains the actual working set, stride, translation-locality
range, individual readings, mean, benchmark PID/start identity and interval.
The translation-locality range groups nearby addresses to limit address
translation overhead; it does not remove that overhead.

This is a cache-working-set latency curve, not a direct L3 hit latency.
Translation, prefetch, processor frequency, scheduling and memory placement
can affect it. The proof pairs it with the existing fingerprint's CPU,
capacity and L3 context, rather than collecting another hardware identity.
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

The default curve spans 4 KiB through 1 GiB, using a 64 byte stride and at most
256 KiB of translation locality. It takes two measured samples per point after
the tool's discarded warm-up. The total latency deadline is 30 seconds.
This allocation is separate from the copy benchmark and task CPU windows.

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

`perf` comes from Ubuntu's Linux tools package. `multichase` is Apache-2.0
software built at the committed upstream revision with GCC, make and Perl.
The installation records elapsed seconds and the actual perf and multichase
binary byte counts. It adds no Python package, default npm dependency,
browser asset or committed binary. Missing or failed installation fails the
proof rather than fabricating an instrument.

A runner can refuse all hardware counters. Its refusal verifies detection
and API behavior, not cache hit/miss measurement. Actual counters then remain
pending on an operator-controlled Linux host that already exposes the
hardware performance-monitoring unit and permits these user-space events for
an owned PID. No permission change is part of this feature.

## Design rationale

The mature native tools own event access and pointer-chase execution.
The TypeScript code validates and controls them; it does not implement another
native benchmark. `lat_mem_rd` uses a fixed-stride chain that can be affected
by stride-sensitive prefetch, so it does not satisfy the random-chain method
used here. The two instruments remain independently optional because task
event counts and a controlled latency curve answer different questions.

## See also

- [host-metrics.md](host-metrics.md) - existing CPU, memory and hardware context.
- [../how-to/run-feed-ingest-plan-test.md#resource-proof](../how-to/run-feed-ingest-plan-test.md#resource-proof) - isolated proof boundaries.
- [../../config/host-cache-tools.json](../../config/host-cache-tools.json) - optional Linux tool dependencies.
- [perf stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html) - event, control and output semantics.
- [multichase](https://github.com/google/multichase) - established native pointer-chase tool.
