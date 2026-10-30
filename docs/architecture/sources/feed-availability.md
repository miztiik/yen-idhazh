# Durable feed availability

**Last Updated**: 2026-10-30

How does the feed planner pause failed sources without forgetting their state?

`config/feed-availability.json` owns the bounded endpoint-state paths and
thresholds. `packages/common-contracts` owns the persisted state and enrollment
shapes. The planner does not reconstruct eligibility from compactable
feed-health history: the state file under
`state/raw/planner/feed-availability/` is the current durable source of truth.

## Enrollment and endpoint identity

The first planner invocation may initialize state only when both the state file
and its enrollment marker have never been published and
`initial_enrollment` explicitly allows the active configured feeds. State and
marker are written together. Once established, either missing file, corrupt
contents, an un-enrolled active feed, or an endpoint URL change fails closed.
The Git reader also checks path history so removing both files does not look
like first startup.

An operator reenrolls a retired feed, or accepts a changed endpoint, by adding
a unique `feed_id` and UUID `enrollment_id` under
`operator_enrollments`. That event creates a fresh episode and clears the old
reservation, rest and retirement state. Remove the event from configuration
after it has been applied; the saved enrollment ID prevents replaying the same
event from resetting later checks.
An interrupted check remains unavailable until its matching completion arrives
or an operator reenrolls the endpoint. A new run cannot assume it failed.

The configured read set is two named files and each file is bounded by
`max_state_bytes`. The complete enrollment is bounded by `max_enrolled_feeds`.
No raw ledger history walk or history-pruning dependency is involved.

## Checks, rests and retirement

One logical feed request reserves durable state before external fetch. Fetch
retries remain part of that one reservation. Successful fetches acquire a
separate parse phase before parsing. A completion must match the request, run,
attempt and current reservation; a duplicate identical completion is
idempotent, while a stale or conflicting completion is refused. Cancellation
or a crash leaves an unknown reservation, not an invented success or failure.

The committed defaults are:

Table A

| Id | Control | Default |
| --- | --- | ---: |
| A1 | Consecutive failed logical checks before rest | 5 |
| A2 | Initial rest | 24 hours |
| A3 | Recovery rest after any failed recovery check | 24 hours |
| A4 | Confirmed failed recovery checks before retirement | 7 |
| A5 | Minimum age since first confirmed source failure before retirement | 36 hours |

A recovery check is allowed at or after the recorded UTC deadline. Only a
confirmed target HTTP 404, 410 or 5xx advances the failed-recovery count.
Retirement needs a new such failure after both configured limits are met.
With the default recovery rest of 24 hours, the count can take longer than
the minimum episode age. These are independent controls.
With these defaults, the seventh recovery check is no earlier than 168 hours
after entering rest. The 36-hour age gate starts at the first confirmed source
failure, not at rest entry, and does not promise retirement after 36 hours.

Timeouts, robots decisions, parser failures, cancellation, local errors and
ambiguous transport outcomes do not advance retirement. A timeout still counts
as a failed logical check and, once the failure threshold is reached, schedules
another rest at least 24 hours after completion. Any valid parsed feed,
including an empty feed, clears the failure episode and rest.

Collection preflight omits resting, retired, busy and otherwise ineligible
feeds. The durable reservation at fetch remains authoritative: a competing run
can change eligibility after preflight. Race-time `FEED_RESTING`,
`FEED_RETIRED` and `FEED_CHECK_BUSY` outcomes are per-feed skips, not permission
to bypass reservation.

## Publication and restart

The planner uses `packages/data-delivery`'s bounded Git reader and
exact-baseline compare-and-swap writer. A state mutation publishes its complete
snapshot from the revision it read; if `main` moved, the planner refreshes and
reapplies the transition instead of overwriting newer state. State and initial
enrollment marker publish in the same commit.

The workflow checkout persists its write credential and grants `contents:
write`. Availability reads fetch the current `origin/main`, even when the
workflow checkout was created from an older revision. A successful CAS pushes
the availability commit before normal workflow finalization. The later
immutable ledger publisher fetches current `main` again, so it preserves that
state commit. A later workflow or process restores state by reading the same
named files from current `main`; no temporary workflow artifact or compacted
ledger is the recovery source.

CAS uses no shared mutable index or worktree staging. Its private candidate
contains only the named availability paths. It refuses a stale baseline and
does not move the caller's checkout, HEAD or index.

## Configuration and operation

The effective thresholds appear in the workflow policy report. `rest_hours`
and `recovery_rest_hours` are separate positive-duration knobs. Retirement requires both
`failed_recovery_checks_before_retirement` and
`retirement_minimum_age_hours`.

The initial enrollment setting is a one-time bootstrap rule, not permission to
reinitialize missing state. Reenrollment is an explicit configuration event.
Availability errors are surfaced with `FEED_AVAILABILITY_STATE_INVALID`,
`FEED_AVAILABILITY_UNENROLLED` or
`FEED_AVAILABILITY_ENDPOINT_CHANGED`; the fetch race skips are
`FEED_RESTING`, `FEED_RETIRED` and `FEED_CHECK_BUSY`.

## See also

- [Planner execution](feed-plan-runner.md)
- [Health history](planner-feed-history.md)
- [Workflow publication](../publishing/committing.md)
- [Feed planner ledger reference](../../reference/feed-planner-ledgers.md)
