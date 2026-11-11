# The run timeline

**Last Updated**: 2026-11-11

What shape does the newest run's clock have, and where do its facts come from?

The Pipelines `runTimelineQuery` reads native item-health cells at view time.
The native contract is
[`item_health.py`](../../../backend/idhazh/contracts/item_health.py).
The browser derives the clock in
[`console/pipelines/run-timeline.ts`](../../../frontend/src/lib/console/pipelines/run-timeline.ts).
There is no public monthly timeline, producer, retention knob or second row
contract. No source ledger was deleted.

## Two measurements, not two grains

The default **Elapsed time** view draws one recorded window per shard. Its
start is the earliest valid item start and its end is the latest corresponding
recorded item end. Zero is the earliest valid start in the run; the domain ends
at the latest valid completion. A left gap means later recorded work, and a
right gap means an earlier final completion. The interval includes parked
waits, not measured continuous activity. Workflow setup and publication are
outside this item window.

**Item work** instead adds recorded, nonnegative `item_total_ms` readings per
shard, starting every bar at zero. Those costs exclude parked queue waits; they
are not continuous intervals beginning at fetch start. Its independent domain
is the largest shard cost. Neither view stacks call totals or estimated visual
time onto a wall clock.

Both views sort descending by the measurement shown, with shard number breaking
ties and unavailable readings last. Longer is not automatically less efficient:
the items and failures can differ.
Duration labels retain seconds beyond an hour and carry rounded seconds into
the next minute rather than printing a sixty-second remainder.

## Coverage and inspection

`newestRunRows` compares numeric run suffixes with BigInt, not lexical ordering.
Run totals include every recorded item, even one whose shard is missing.
Endpoint coverage and cost coverage are independent: a missing end never
removes a measured cost, and a missing cost never removes a valid interval.
Missing or reversed endpoints do not produce inferred ends. The readout names
coverage per run and shard; unmatched shards are counted explicitly.

Processed items per minute counts all attempts, including failures, over the
recorded item window, only when every item has a valid endpoint pair and that
window is positive. It is not a publication rate or a concurrency estimate.

Selecting a shard opens article details. Items default to descending cost;
start-time ordering preserves sequencing inspection. `console.timeline_bars`
bounds each page of article details, never the shard rows or run arithmetic.
Pagination retains access to every article in that shard.

Stage averages reuse the complete, reconciling cohort from
[`duration-cohort.ts`](../../../frontend/src/lib/console/duration-cohort.ts):
fetch, extract, summarize and checking, with positive unclaimed time and
overlap kept separate. The cohort and excluded clocks are named; incomplete
items still contribute their recorded costs to item work. Per-item inspection
retains known stages, queue and robots readings, status, UTC endpoints and the
signed gap. Label, summary and visual-plan readings are non-additive details;
the existing estimate flag identifies attributed visual-plan time.

## Design rationale

The worker fetches before processing its ready list, so an article's work can
be separated by a parked wait. Adding queue-excluded cost to the original
start shortens the apparent run; summing stages per shard cannot restore those
missing intervals. Recorded endpoints and work totals therefore need separate
axes, not normalized fills or an inferred active start.

One row per shard keeps the main comparison compact as article counts grow.
The default no longer shows simultaneous all-article sequencing; article
identity, ordering and recorded readings remain in the inspector. Exact
busy/idle stretches require active-interval recording and cannot be recovered
from these totals.

## See also

- [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) - native panel queries and drawings.
- [telemetry-series.md](telemetry-series.md) - projection retirement and retained state.
- [../../concepts/console-design.md](../../concepts/console-design.md) - shared drawing and readout rules.
