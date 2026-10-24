# What working-set latency the Linux runner measured

**Last Updated**: 2026-10-24

Which cache-related numbers were actually obtained, and which remain unknown?
The native random pointer chain produced a working-set latency curve.
Linux refused the hardware counters. This is not a direct L3 hit latency.

## Machine and method

The existing CI resource proof wrote `resource-proof.json` in
[run 40083949235](https://github.com/miztiik/yen-idhazh/actions/runs/40083949235),
from cache head `50581c975c1f823448ff7c987f1b907966519513` and executed merge
`f5514509376af0dc45b7fb6923cb7d9b5d04f7b1`.
The machine reported AMD EPYC 7763, four visible and four allowed logical
processors, and 32 MiB of L3. CPU quota was unavailable.
The kernel was `7.0.0-1017-azure`, architecture x64, with Bun 1.3.13.

Apache-2.0 multichase revision
`8b68e918f8d2e84794f2c20cdb6c7ebb9c3952bb` ran one dependent random pointer
chain on its first allowed CPU, CPU 0. The stride was 64 bytes, native pages
were 4096 bytes, and translation locality was at most 256 KiB.
Chain construction wrote the pointers before timing. Each point discarded
one 500 millisecond warm-up, then measured two 500 millisecond samples.
The reported value is the mean of those native samples.

The UTC measurement window was 2026-10-24T10:01:28.377Z through
2026-10-24T10:01:40.010Z; actual elapsed time was 11.63 seconds.

Table A - observed working-set curve

| ID | Working-set address range | Nanoseconds per dependent load |
| --- | --- | --- |
| A1 | 4 KiB | 1.257 |
| A2 | 32 KiB | 1.343 |
| A3 | 256 KiB | 4.340 |
| A4 | 2 MiB | 11.711 |
| A5 | 16 MiB | 59.000 |
| A6 | 128 MiB | 77.361 |
| A7 | 1 GiB | 77.019 |

The largest address range exceeded the L3 size reported by the existing
fingerprint. This does not prove which cache served each load.
Scheduling, translation, prefetch and memory placement still affect the
curve. The two 16 MiB samples were 67.379 and 50.620 nanoseconds per load;
that spread alone prevents presenting their mean as a pure L3 hit latency.

## Hardware counter gap and installation cost

Unprivileged perf 7.0.14 attempted the exact events `LLC-loads:u` and
`LLC-load-misses:u` for a pinned owned PID. Both results were unavailable
with `permission_denied`; counts and counter timings were null.
This finding does not establish that the machine lacks a hardware unit.
No kernel setting, runner privilege or target affinity was changed.
Actual event counts remain pending on an operator-controlled Linux host
that already exposes and permits these events for its owned target.

Optional installation took 10 seconds. The perf executable was
25,192,472 bytes; the multichase executable was 1,208,608 bytes.
These are binary sizes, not the total installed dependency size.
The proof also confirmed default-off behavior, native benchmark cancellation
and survival of the observed operator process.

The named fixtures `cache-working-set-latency.json` and
`cache-counters-unavailable.json` under `tests/fixtures/host-probes/` are
bounded copies of these validated results. They are recorded parser inputs,
not claims about a later host. This run verifies native commands and result
handling; combined API acceptance still follows shared-main integration.

## See also

- [../host-cache-probes.md](../host-cache-probes.md) - controls, API and interpretation.
- [../host-metrics.md](../host-metrics.md) - the existing hardware collector.
- [../../how-to/run-feed-ingest-plan-test.md#resource-proof](../../how-to/run-feed-ingest-plan-test.md#resource-proof) - the existing isolated proof.
