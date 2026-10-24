# What working-set latency the Linux runner measured

**Last Updated**: 2026-10-24

Which cache numbers were obtained with the integrated API and Python-free
native tools? The random pointer chain produced a real latency curve.
Linux refused hardware event access. Neither finding is direct L3-hit latency.

## Machine and method

The existing resource proof wrote `resource-proof.json` in
[CI run 40093385329](https://github.com/miztiik/yen-idhazh/actions/runs/40093385329)
at head `a5a67d4206b21cf35e67ac20755e501536dba908` and executed merge
`4ac3c08a207f60b79e398de379803fb7a6d8fb61`.
All five CI jobs passed. The machine reported AMD EPYC 7763, four visible
and four allowed logical processors, and 32 MiB of L3. CPU quota was
unavailable. Kernel: `7.0.0-1017-azure`; architecture: x64; Bun: 1.3.13.

Apache-2.0 multichase revision
`8b68e918f8d2e84794f2c20cdb6c7ebb9c3952bb` ran one dependent random pointer
chain. Each address supplies the next load, rather than overlapping
independent loads. The stride was 64 bytes, native pages were 4096 bytes,
and translation locality was at most 256 KiB.
Chain construction wrote the pointers before timing. Each point discarded
one 500 millisecond warm-up, then measured two 500 millisecond samples.
The reported value is the mean of those native samples.

The latency HTTP command ran with task profiling off. Taskset restricted each
owned benchmark to CPU 0, and the adapter verified the child's actual mask.
The UTC window was 2026-10-24T12:25:29.452Z through
2026-10-24T12:25:41.098Z; actual elapsed time was 11.65 seconds.

Table A - observed working-set curve

| ID | Working-set address range | Nanoseconds per dependent load |
| --- | --- | --- |
| A1 | 4 KiB | 1.246 |
| A2 | 32 KiB | 1.340 |
| A3 | 256 KiB | 3.798 |
| A4 | 2 MiB | 11.606 |
| A5 | 16 MiB | 20.813 |
| A6 | 128 MiB | 78.305 |
| A7 | 1 GiB | 77.447 |

The largest address range exceeded the reported L3 size. This does not
identify which cache served each load. Scheduling, translation, prefetch,
frequency and memory placement still affect the curve.

## Counter and ownership evidence

The existing task HTTP journey enabled cache counters for its actual separate
Bun target PID 8714, start ticks 37370. The target remained alive at stop;
the repeated stop returned identical bytes. Official perf attempted
`LLC-loads:u` and `LLC-load-misses:u` without privileges or kernel changes.
Both returned `permission_denied`; counts and event timings were null.
This does not establish that the machine lacks a hardware unit.
Actual counts remain pending on an operator-controlled Linux host that
already exposes and permits these events for its owned target.

The separate affinity proof restricted an owned caller from CPUs `[0,1,2,3]`
to `[1,3]`. Its native benchmarks verified actual singleton CPU 1.
The existing Linux controller case passed concurrent failure plus complete
owned cleanup. Native cancellation ended its benchmark and preserved the
observed operator process.

## Actual native tool cost

Official perf revision `028ef9c96e96197026887c0f092424679298aae8` was built
with Python support and Python-generated vendor tables disabled.
Build execution tracing counted zero Python executions. Its direct ELF and
resolved runtime libraries were libm, zlib, libstdc++, liblzma, libzstd,
libgcc, libc and the Linux loader, plus the virtual vDSO at runtime.
No libpython, Python extension, interpreter or module package was added.
The distribution's perf package was not installed or extracted.

Source fetch took 5 seconds; perf build took 114 seconds; multichase build
took 2 seconds. Total native setup took 147 seconds, including package work.
The only added OS package was `build-essential` version
`12.12ubuntu2.26.04.2`, an 18 KiB installed meta-package. The declared native
toolchain, flex, bison, pkg-config, binutils, strace and util-linux were
already present. These figures describe this image, not every future runner.

Perf executable: 9,161,744 bytes. Multichase executable: 1,208,608 bytes.
These are executable sizes, not the total preinstalled dependency size.
No native executable enters the repository or published site.

The two named cache recordings under `tests/fixtures/host-probes/` exactly
match this artifact. They are bounded parser inputs, not claims about a later
host. The remaining instrument gap is successful hardware counter access,
not native latency, API routing or cleanup verification.

## See also

- [../host-cache-probes.md](../host-cache-probes.md) - controls and interpretation.
- [../host-metrics.md](../host-metrics.md) - the existing hardware collector.
- [../../how-to/run-feed-ingest-plan-test.md#resource-proof](../../how-to/run-feed-ingest-plan-test.md#resource-proof) - isolated proof boundaries.
