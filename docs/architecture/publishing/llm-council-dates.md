# Which judges and dates does the council run?

**Last Updated**: 2026-11-05

The council selects judges and their own dates once, before preparation or any
model job. The venue's clocks and publication rules are in
[llm-council.md](llm-council.md).

## Scheduled dates belong to each judge

The scheduled anchor date defaults to yesterday UTC. It is an offered date,
not compulsory work. The council gives each active plugin a `ScheduleRequest`;
the plugin's `schedule(request=...)` returns its complete `JudgeSchedule`.
The council never opens a judge's ledger to decide what is outstanding.
Paused and retired packages are not imported.

`config/llm_council.json` owns the window. `repair_window_nights` bounds the
older dates, ending before the anchor. `first_night` is the older-date floor;
the offered window includes the anchor. The request supplies `anchor_date`,
`window`, `max_dates`, `max_older_dates`, `shards` and `shard_seconds`.
`max_dates` is one plus `repair_dates_a_night`; `max_older_dates` is that
existing repair cap. The effective shard width is the smaller of the plugin's
width and the council's width, and seconds come from the existing shard
deadline calculation. No new resource budget is introduced.

A plugin chooses every actual date, including whether to take the anchor.
An empty answer explicitly declines scheduled work. Nonempty answers must
contain unique valid calendar dates inside the window and satisfy both date
budgets. The council refuses invalid answers before preparation; it never
inserts the anchor, truncates an answer or sorts away a plugin's decision.

For example, judge A can select only an older date while judge B selects the
anchor or declines entirely. Each judge owns only its returned dates. An
aggregate date list never authorizes work for another judge. Selection precedes
preparation; only a matching ready receipt creates judging cells, as described
in [execution and transport](llm-council.md#preparation-authorizes-work-not-selection-alone).

The repair cap buys more jobs, not more time inside a job. Each cell keeps its
existing timeout, preamble allowance and wrap-up reserve. A deferred gap can
return while it remains inside the window. A gap older than the window needs
a manual run. An empty active set, or all active plugins declining, is legal:
no model job or synthetic no-work unit is created.

## Manual runs select judges and one date

The `LLM-COUNCIL` workflow's manual controls require a UTC digest date and a
JSON array of one or more judge names from `config/llm_council.json`:

```json
["content-similarity-judge"]
```

Each name must be unique and registered. A missing input, empty list, malformed
name or date, unknown name, duplicate name or retired judge earns `2 refused`
before any selected package is imported or unit runs. The calendar is checked,
not just the date's digit pattern. A range is not accepted; several dates need
several runs.

Every selected judge receives exactly that date. Scheduling is not called,
and no repair date rides along. All selected packages are
resolved before work starts. Active declarations, model needs, model-fit checks,
ledger-family refusals and safe-name checks keep their existing rules.

An active selected judge publishes as on a scheduled night. An explicitly
selected paused judge may import and execute, but only as a trial. Unselected
paused judges and all retired judges are still not imported.

## A paused trial cannot enter publication

One trial uses
`backend/var/council/trials/<run-id>/<attempt>/<judge>/`. Its existing prepare
and shard helpers route scratch files into `scratch/<date>/`. Settlement reads
the judge's bounded named inputs from that trial tree and writes to its
`state/`, including its own council records. Active scratch is isolated at
`backend/var/council/runs/<run-id>/<attempt>/`, retaining the date/slot/judge
helper layout. Active publication still writes the declared production state
paths. Neither scratch root is shared across attempts.

During a selected paused judge's settlement, the council authorizes only its exact trial
state root, run and attempt. The raw ledger door may then write a paused
family's rows there, including council records. It still refuses retired
families. Production roots and non-raw writers keep the family gate.
A different state root alone is not authorization. The
[ledger family rule](../contracts/ledger-registry.md#the-three-lifecycle-statuses-and-what-each-one-changes)
declares this exception.

The collector settles active and paused work, but only active work enters its
write permissions, observed write evidence, publication receipts and
`PublicationRequest`. Council records are collected separately: paused records
stay in the trial tree. A mixed run's production records contain only its
active judges. A paused-only run makes no publication request, production
machine record, receipt or commit.

The collector always uploads `council-results-<run_id>` after settlement. That
download includes the trial's scratch files, settled state and council records,
even when a unit failed. Planner and shard bundles keep their existing event
transport and retention. Downloadable work is not evidence that it was
published; the collecting job's summary reports the actual outcome.

### Design rationale: selection binds one invocation, not a future run

The council mints its run identity before planning. The planner emits the
versioned `Selection` declared in
`backend/idhazh/contracts/council_invocation.py`: run ID, positive attempt,
Git revision, mode, anchor, offered window and ordered selected judges.
Each judge carries its declared status, chosen dates and admitted positive
width. Scheduled selections retain every active plugin in registration order,
including plugins with no dates.

The selection travels through `COUNCIL_SELECTION`, not shell source.
Planning requires `--run-id` and `--commit`; `--attempt` defaults to
`GITHUB_RUN_ATTEMPT`. Consumers require the selection and exact run, attempt
and revision agreement with their invocation, as well as current declaration
and width checks. An explicit `--date` only narrows already authorized work;
it never grants implicit permission. Local callers must create an explicit
manual selection too. The matrix still carries exactly
`tenant`, `date`, `shard`, `shards` and `runs_model`. Settlement derives its
aggregate dates and publication derives its active set from this selection.

Versioned selection, preparation and shard-file documents belong only to this
invocation. They are not resumed or migrated from an older attempt or revision;
the [schema compatibility rule](../contracts/schemas.md#council-invocation-and-retained-record-compatibility)
distinguishes them from retained council records. Trial status does not add a
field to a persisted ledger. Separate roots keep trial bytes out of production
rather than removing them after writing. Publication retries retain the
existing completed-byte policy and never rerun a judge.

The scoped raw-write exception makes paused-family settlement downloadable
without reopening production. Its exact-root and invocation checks keep a
trial's authorization from leaking to another root or attempt.

`backend/tests/council/test_selected_runs.py` drives prepare, shards and
settlement through real fixture packages and the local Git publisher. It
checks the remote tip and exact receipt paths, not just the summary. Paused
output and council records must exist in the downloadable root and be absent
from publisher writes and the remote tree.

## See also

- [llm-council.md](llm-council.md) - the venue, clocks, events and job summary.
- [committing.md](committing.md) - completed evidence and publication recovery.
- [autotune-content-similarity.md](autotune-content-similarity.md) - what the
  current judge considers outstanding.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - local checks.
