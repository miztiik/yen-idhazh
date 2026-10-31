# Feed rest and retirement

**Last Updated**: 2026-10-31

How does a planner run reuse a supported feed decision without a separate state store?

The planner reads saved rest and retirement calculations from its existing
health Parquet files. Unknown availability alone does not block an active
catalog feed. A supported future rest deadline or proven retirement does.
Draft and retired catalog feeds retain their existing handling.

The TypeScript planner writes the calculations into
`state/raw/feed-ingest-plan/feed-health-state/YYYY/MM/DD/<uuid>.parquet`.
The final workflow publisher commits completed metadata files together.
There is no availability state file, enrollment marker, reservation or
intermediate availability commit.

## Configured decisions

`config/feed-ingest-plan.json` declares `availability`. Its native TypeScript
schema validates the retained policy controls.

Table A

| Id | Control | Default and effect |
| --- | --- | --- |
| A1 | Consecutive failed logical checks before rest | 5 failures start a rest when the saved streak is known. |
| A2 | Initial rest | 24 hours before another eligible check. |
| A3 | Recovery rest | 24 hours after a failed recovery check. |
| A4 | Confirmed failed recovery checks before retirement | 7 qualifying failures are required. |
| A5 | Minimum confirmed failure episode age | 36 hours must also have elapsed. |

Both retirement gates must hold on a new confirmed failing recovery check.
Only target HTTP 404, 410 or 5xx advances that count. Timeouts, robots results,
local parse failures, uncertain transport and interruption cannot prove
retirement. A valid parsed feed, including an empty feed, resets the episode.

A recovery check is eligible at the recorded UTC deadline, not before it.
With the default recovery spacing, seven recovery checks take at least
168 hours after rest starts. The separate episode-age gate starts at the
first proven confirmed failure. Missing history cannot establish that start,
a streak or a recovery count.

## Saved calculations and partial evidence

The [health contract](../../reference/feed-planner-ledgers.md#c-feed-health-state)
declares actual logical check identity and result, rest deadline, episode start,
recovery count, retirement reason and the calculation's actual UTC update time.
`availability_complete` means that the calculation is fully supported, not
that the source is reachable.

Saved calculations are read first. Only missing or unusable calculations are
recovered from the already captured, bounded evidence. A valid zero or supported
null is not a missing field. Unrelated missing columns cannot erase a supported
deadline or retirement decision. An unknown count stays null.

Copying a calculation into a later run does not advance its update time.
Skipped active feeds receive ordinary health rows with no new check identity
or check time. Known unperformed work has zero counters; incomplete actual
request accounting stays null. Interrupted checks do not manufacture success,
source failure or retirement.

Reliability retains its own saved counts, fractions, coverage dates and
completeness. Known entering and leaving contributions adjust a rolling window.
Missing contributions produce a diagnostic and partial values; an unchanged
saved measurement is never relabelled as covering newer dates.

## Independent runs and final delivery

The workflow captures current remote input once. Raw and compact health bytes
come from that same revision. Reads use existing publication inventory, compact
indexes and exact named UTC-day Git membership within the configured windows
and period limit. No growing-tree scan or additional discovery index is used.

Each run owns its captured calculation across real HTTP stage requests.
Another run can publish later without changing that captured input. Independent
runs may check the same feed and save separate immutable results. Their saved
cumulative streaks are not added together. Actual check order selects a coherent
newest calculation; ambiguous order remains incomplete.

Health recording writes local Parquet. Only `safe_persist_data`, through ordinary
final workflow delivery, commits planner output. Failure finalization retains
known partial work when the process can still finish it.

## Design rationale

One ledger keeps work evidence and the calculation that later runs need together.
Separate shared reservations would require writes before source work and would
change the permitted independent-run semantics. Immutable snapshots retain both
results without claiming cross-process exclusive ownership or atomic counters.

## See also

- [Planning history](planner-feed-history.md)
- [Planner execution](feed-plan-runner.md)
- [Operator APIs](feed-operator-api.md)
- [Workflow publication](../publishing/committing.md)
