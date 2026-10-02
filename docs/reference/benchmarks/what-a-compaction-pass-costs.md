# What a Compaction Pass Costs

**Last Updated**: 2026-10-02

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
machine. Its different wall time is not another paired comparison.
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

The next cost is small-file I/O. Opening files spent 14.060 seconds inside
`_io.open`, and 269 atomic renames spent 9.730 seconds inside `nt.replace`.
The passes load 101 ledger files; monthly absorption accounts for 92 daily
files, including quiet days.
Reducing this work needs a separate change that preserves quiet-day coverage
and atomic writes; removing an open or rename is not a safe one-line fix.

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

## See also

- [../../architecture/publishing/idhazh-gardener.md](../../architecture/publishing/idhazh-gardener.md) - the compaction order and restart behavior.
- [../../architecture/contracts/persistence.md](../../architecture/contracts/persistence.md) - root checks and ledger file writes.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the local gate lock and focused tests.
