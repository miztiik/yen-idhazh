# Which judges and dates does the council run?

**Last Updated**: 2026-10-11

The council selects judges and their own dates once, before preparation or any
model job. The venue's clocks and publication rules are in
[llm-council.md](llm-council.md).

## Scheduled dates belong to each judge

The scheduled digest date defaults to yesterday UTC. Each active judge gets
that date plus its own outstanding dates. The council asks
`nights_outstanding(window=...)` on each active judge. It never opens a judge's
ledger to decide what is outstanding. Paused and retired packages are not
imported.

`config/llm_council.json` owns the window. `repair_window_nights` bounds the
older dates, ending before the scheduled date. `first_night` is the floor.
`repair_dates_a_night` caps each judge's answer separately, newest first.
A date outside the supplied window is refused before preparation.

For example, if only judge A owes an older date, the scheduled date gets
cells for A and B, but the older date gets cells for A only. Prepare and settle
use that same ownership. An aggregate date list is useful for the collector's
loop, but never authorizes work for another judge.

The repair cap buys more jobs, not more time inside a job. Each cell keeps its
existing timeout, preamble allowance and wrap-up reserve. A gap dropped by the
cap can return while it remains inside the window. A gap older than the window
needs a manual run. An empty active set selects no judge and writes nothing.

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

Every selected judge receives exactly that date. No judge is asked about
outstanding dates, and no repair date rides along. All selected packages are
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
`state/`, including its own council records. Active work keeps the existing
production scratch and state paths.

The owner approved isolated raw trial writes on 2026-10-11 UTC. During a
selected paused judge's settlement, the council authorizes only its exact trial
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

### Design rationale: one transient selection, no trial ledger field

The planner emits one validated selection with a mode and an ordered list of
judges, each with its declared status and own dates. It travels through
`COUNCIL_SELECTION`, not shell source. Each consumer validates it against the
same committed declarations before work. The matrix still carries exactly
`tenant`, `date`, `shard`, `shards` and `runs_model`. Settlement derives its
aggregate dates and publication derives its active set from this selection.

The selection is invocation transport, not a payload read by a later run.
Trial status does not add a field to any persisted ledger. Separate roots keep
trial bytes out of production rather than trusting a publisher to remove them
after they have already been written there. Publication retries retain the
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
