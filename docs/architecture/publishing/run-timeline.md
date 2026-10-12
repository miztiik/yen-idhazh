# The run timeline

**Last Updated**: 2026-10-11

What shape does the newest run's clock have, and where do its facts come from?

The Pipelines `runTimelineQuery` reads native item-health cells at view time.
The native contract is
[`item_health.py`](../../../backend/idhazh/contracts/item_health.py).
The browser derives the clock in
[`console/pipelines/run-timeline.ts`](../../../frontend/src/lib/console/pipelines/run-timeline.ts).
There is no public monthly timeline, producer, retention knob or second row
contract. No source ledger was deleted.

## Which rows can be placed

`newestRunRows` compares numeric run suffixes with BigInt, not lexical ordering.
A placed row has an item id, a valid UTC start, a nonnegative item clock and a
recorded whole `machine_shard`. Missing starts or shards remain unplaced; the
reader does not invent either. Zero is the earliest eligible item start.

The six timed parts are fetch, extract, label, summary, visual plan and
faithfulness (called score in the view). Their sum is subtracted from the item
clock for the signed residual. Positive residual is unaccounted time; negative
residual is overlapping work. Queue wait, robots and stage gap retain separate
native readings and are not subtracted again.

## Both grains use one clock

The item grain places each item at its native start offset. The shard grain
runs from that shard's first item start to its last item end. It adds the same
item parts and names the time between items in its residual.

Capping item bars does not cap run totals or shard folds. Both grains share a
scale that includes overlapping steps. Independent clock arithmetic over the
recorded native fixture checks every offset, item clock and six-step residual.
The chart's drawing rules belong in
[`console-design.md`](../../concepts/console-design.md).

## See also

- [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) - native panel queries and drawings.
- [telemetry-series.md](telemetry-series.md) - projection retirement and retained state.
