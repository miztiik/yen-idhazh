# What a Compaction Pass Costs

**Last Updated**: 2026-10-04

How much time and repeated index work the every-tier ledger fixture costs.
This measures local file work, not the production runner's six-hour limit.

## Conditions and method

Windows, Intel Core i7-1265U, 10 physical cores and 12 logical processors.
The developer machine was shared. One gate lock held the complete comparison.
Each case ran in its own Python process with a fresh temporary state tree.
Imports and temporary-tree cleanup are outside the reported time. Raw seeding
and three real compaction passes are inside it. cProfile measured each pass.

The baseline is commit `a02af2a4acd80c8993fd45c55e88bbba5c2eaf8c`.
Its `backend/` and `config/` were extracted with `git archive`. The first two
cases used that same original test helper: 18 rows on nine filed days, with
138 calendar days taken by the daily stage. The third used the reduced helper:
the same 18 rows, all four tiers, and 123 calendar days. The minimum allowed
waits are 31 days for months and 63 days for years.

## Current reading

Table A. One consecutive comparison, not a confidence interval.

| Id | Code and input | Fixture seconds | Index-write calls by pass | Path resolutions across passes |
| --- | --- | ---: | --- | ---: |
| A1 | Original code, original span | 153.618 | 138, 6, 2 | 4192 |
| A2 | Batched code, original span | 121.854 | 3, 2, 2 | 1378 |
| A3 | Batched code, minimum span | 101.757 | 3, 2, 2 | 1243 |

The same-input change took 20.7 percent less time. With the smaller fixture,
the measured reduction was 33.8 percent. These are single paired observations
on a shared machine, not predictions for CI.

The index count is the structural result. The old first pass called
`write_index` 138 times and serialized 140 indexes, including two empty
companion indexes. The new first pass serialized three indexes, one per tier.
Both later passes serialized two final indexes each. Every changed index and
watermark is planned once, after all stages decide their entries. The restart
tests check that no source deletion precedes those final indexes.

The original span uses the same helper in both code versions, so its improvement
is not a fixture-size change. The minimum span retains November and December
in the year file: range pruning must preserve untouched rows across more than
one year-file row group while rebuilding all four tiers.

## Where the remaining time goes

A separate current-fixture profile took 57.561 seconds on the same shared
Windows machine. Its different wall time is not another paired comparison.
Table B ranks functions by total time, including their callees. Times overlap.

| Id | Function | Calls | Total seconds |
| --- | --- | ---: | ---: |
| B1 | `_every_tier.a_census_in_every_tier` | 1 | 57.507 |
| B2 | `_task.run_task` | 3 | 53.598 |
| B3 | `compaction.run` | 3 | 49.265 |
| B4 | `_monthly_period.absorb` | 3 | 17.337 |
| B5 | `_io.open` | 507 | 15.848 |
| B6 | `_compact_tree.load` | 101 | 15.754 |
| B7 | `persist.load_stored` | 101 | 15.735 |
| B8 | `persist._opened` | 101 | 15.685 |
| B9 | `pathlib.open` | 238 | 13.971 |
| B10 | `_compact_tree.apply` | 3 | 13.888 |

On Windows, the next cost is small-file I/O. Opening files spent 14.060
seconds inside `_io.open`, and 269 atomic renames spent 9.730 seconds inside
`nt.replace` - about 30 ms for each file operation, far above a normal disk.
The passes load 101 ledger files; monthly absorption accounts for 92 daily
files, including quiet days.

**The 30 ms figure is a cost of that Windows machine, not a cost of the
code.** The same profile, on the same fixture, run on GitHub's own
`ubuntu-latest` runner (4 vCPU, no GPU; see `.github/workflows/compaction-profile.yml`,
dispatched by hand on 2026-10-03) took 1.748 seconds wall time end to end -
33 times faster than the 57.561-second Windows reading for the same work.
Table C ranks the same ten functions by total time on Linux; none of them
is a file operation.

| Id | Function | Calls | Total seconds |
| --- | --- | ---: | ---: |
| C1 | `_every_tier.a_census_in_every_tier` | 1 | 1.739 |
| C2 | `_task.run_task` | 3 | 1.528 |
| C3 | `compaction.run` | 3 | 1.432 |
| C4 | `_daily_period.compact` | 3 | 0.823 |
| C5 | `_daily_period._take` | 123 | 0.773 |
| C6 | `persist._rendered` | 135 | 0.741 |
| C7 | `persist.render_period` | 126 | 0.620 |
| C8 | `parquet.render` | 135 | 0.415 |
| C9 | `pathlib.relative_to` | 2624 | 0.327 |
| C10 | `paths._under_the_two_roots` | 1297 | 0.310 |

Neither `_io.open` nor `os.replace` reaches the top ten by total time or by
self time (time inside the function alone, excluding callees). The tenth
place by self time, `core.close` at 136 calls, holds 0.036 seconds. That is
a ceiling, not a measurement of either function by itself: on Linux, the
total self time spent across every open call and every replace call in the
whole three-pass run is below 0.036 seconds combined. Against the Windows
reading - 507 opens taking 14.060 seconds total (about 27.7 ms per open) and
269 renames taking 9.730 seconds total (about 36.2 ms per rename) - a
0.036-second ceiling spread over the same 776 calls works out to about
0.05 ms per call, roughly 600 times smaller than the Windows reading. The
tool only keeps the ten largest functions, so "about 0.05 ms" is a labeled
estimate from that ceiling, not a per-call measurement; the firm fact is the
0.036-second ceiling on the whole run.

**Verdict: the small-file I/O cost is a cost of the Windows machine, not a
code cost.** The code itself opens and renames the same small number of
files on both machines. On Linux those operations are too fast to even
appear in a profile that already lists the ten slowest functions call by
call. The 30 ms-per-operation figure on Windows is almost certainly
antivirus scanning of the worktree and the system temp folder, not a
property of the compaction code. See
[`docs/reference/agent-notes.md`](../agent-notes.md) for the resulting note;
no code change follows from this reading, and no machine setting was
changed to produce it.

## Reproduce

Use the existing Python development environment from the repository root.
The utility extracts only the baseline code and config into a temporary
directory. It never reads the committed data archive.

```text
python backend/utilities/gate_lock.py -- python backend/utilities/benchmark_compaction.py --baseline a02af2a4acd80c8993fd45c55e88bbba5c2eaf8c
python backend/utilities/gate_lock.py -- python backend/utilities/benchmark_compaction.py --profile-current
```

The first command runs the old input on old code, that same input on current
code, then the current reduced input. The second profiles the whole current
fixture once and prints the ten largest functions by total time and by time
spent inside the function itself. Total time includes called functions, so
those numbers overlap and must not be added.

To reproduce the Linux reading above instead of a local one, dispatch
`.github/workflows/compaction-profile.yml` by hand (Actions tab, or
`gh workflow run compaction-profile.yml`) on `main`. It installs the same
development environment as the `gates` job in `ci.yml` and runs the second
command above on GitHub's `ubuntu-latest` runner, printing both ranked
tables to the job log and the step summary.

## See also

- [../../architecture/publishing/ledger-compaction.md](../../architecture/publishing/ledger-compaction.md) - the compaction order and restart behavior.
- [../../architecture/contracts/persistence.md](../../architecture/contracts/persistence.md) - root checks and ledger file writes.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the local gate lock and focused tests.
