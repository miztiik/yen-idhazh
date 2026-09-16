# The Run Timeline

**Last Updated**: 2026-09-16

**What shape does the run timeline have, and why that shape?** This page answers
that one question. The shape landed before any producer so the writers produce
what the chart reads rather than a shape the chart has to migrate (Guardrail #3);
since 2026-09-16 both exist.
[`backend/idhazh/telemetry/publish/run_timeline.py`](../../../backend/idhazh/telemetry/publish/run_timeline.py)
is the writer and the panel on `/console/machine/` is the reader. **How it is
drawn is not on this page** -
[`../../concepts/console-design.md`](../../concepts/console-design.md) owns that,
because a drawing is not a contract and a person arrives holding one question or
the other.

The machine-readable copy is `backend/idhazh/contracts/run_timeline.py`, and it
is the one a build reads. The generated schema is
`schemas/run-timeline-row.schema.json` and is never hand-edited.

## The question the timeline answers

The console can already say what a run cost and what each stage cost. It cannot
say **where the time went, item by item, across one run** - which item started
late, which one ran long, and how much of the run's wall clock sits inside no
step anybody named. Five ledgers hold pieces of that answer and none of them
holds the answer, because none of them places an item on a clock.

## The shape

One row is **one item**. The chart's y axis is items, so the row's key is the
item and every column on it is about that one item.

| Column | What it is |
| --- | --- |
| `date`, `run_id`, `shard`, `item_id` | which item, in which execution, on which work shard |
| `start_offset_ms` | milliseconds from the run's start to the moment this item's own work began |
| `item_total_ms` | how long the bar is, once the wait is taken out |
| the eight step columns | what each named step cost, each one optional |
| `residual_ms` | the bar minus the eight steps, signed |

### The clock is an offset, never a timestamp

An item that waited forty seconds for a worker sits forty seconds to the right,
so the wait is the first thing a reader sees. A wall-clock timestamp would make
the reader subtract, and a category axis - one evenly spaced column an item -
would hide the queue entirely, which is the one thing this chart exists to show.

The wait is drawn as **position and not length**: `start_offset_ms` places the
bar and `item_total_ms` is the item's own cost with its wait already taken out,
which is the same number `ItemHealthRow.item_total_ms` holds. Counting the wait
in both would draw it twice.

### Eight named steps, in the order they happen

| # | Step | Column | Where the name comes from |
| --- | --- | --- | --- |
| 1 | plan | `plan_ms` | new - no ledger times choosing an item yet |
| 2 | fetch | `fetch_ms` | `ItemHealthRow` |
| 3 | extract | `extract_ms` | `ItemHealthRow` |
| 4 | label call | `label_ms` | `ItemHealthRow` |
| 5 | summary call | `summary_ms` | `ItemHealthRow` |
| 6 | visual plan | `visual_plan_ms` | `ItemHealthRow` |
| 7 | score | `score_ms` | `EvalRow` |
| 8 | publish | `publish_ms` | new - no ledger times placing an item yet |

**Six of the eight keep the spelling a ledger already gave them.** One vocabulary
across the instrument is worth more than a shorter name, because the moment the
names come apart a reader comparing a bar against the census is comparing two
spellings of one number without knowing it.

**Every step is optional, and an absent step is not a zero.** An item that died
at fetch carries `fetch_ms` and seven nulls, and it still draws - a bar needs a
start and a length and this row has both. An untimed step cannot be subtracted,
so whatever it cost lands in the residual, where a reader can see there is time
nobody accounted for.

### Two numbers no ledger holds, and six re-filed on purpose

`start_offset_ms` and `residual_ms` are new. The eight durations are the same
numbers the census keeps, re-filed against a clock, and that is the row's job
rather than an oversight: a chart cannot join five ledgers at fetch time, and a
projection that cuts named cells out of a wider row is what every other console
payload already is. It is one account of each measurement, filed twice, with the
census as the source.

### The residual is its own column

`residual_ms` is `item_total_ms` minus the eight named steps, and it gets a
column of its own because **a step that absorbed the leftover reads as slower
than it was** and a reader cannot tell the overhead from the work.
`SpanRollupRow.unattributed_ms` made this ruling once already for the shard; this
is the same ruling for the item.

**It is signed, for the reason `ItemHealthRow.stage_gap_ms` is signed.** Two of
the eight genuinely overlap: the visual plan is decoded inside the
summarize-and-plan call, so `visual_plan_ms` is apportioned out of `summary_ms`
rather than timed beside it, and adding the two counts part of one call twice. A
negative residual says exactly that - two steps overlapped, or two clocks
disagreed - and clamping it to zero would delete the only signal that says so.

**The subtraction happens in the contract and nowhere else.** A row that omits
`residual_ms` gets it filled from its own columns; a row that supplies one the
arithmetic does not agree with is refused. Two subtractions in two modules is how
a chart and a ledger start reporting different overheads for one item.

## What the shape refuses to carry

No address, no `url_key`, no title, no fetched text - only an item id the
pipeline minted, a clock, and durations of our own work. So there is nothing to
redact, and no second `public-run-timeline` shape to declare: this is published
whole, the way `span-rollup-row`, `day-metrics` and `runtime-counters-row`
already are. Where the rows land was left to the writer, and the writer chose a
published mirror alone: every cell is either a census column or arithmetic over
one, so a committed `state/run-timeline/` would be a third copy of numbers git
already carries, and re-deriving a month costs one month of census day files.

## Which cells a run can fill, and from where

Six of the eight steps have a producer and two do not. The writer reads one
ledger for all six - `state/item-health/` - and joins nothing.

| Step | Census column it is filled from |
| --- | --- |
| `fetch_ms`, `extract_ms`, `label_ms`, `summary_ms`, `visual_plan_ms` | the column of the same name |
| `score_ms` | `faithfulness_ms` |
| `plan_ms`, `publish_ms` | nothing times either step; written empty |

**Step 7 takes its NAME from `EvalRow.score_ms` and its VALUE from the census.**
They are one stopwatch: `stages/work.py` times the scorers once and files that
integer in both places. The census copy is the one that matters here because it
is taken inside the item's own clock, so it is the copy `item_total_ms` already
contains - and a residual is only honest when every step subtracted from a total
was counted inside it. Reading the eval ledger instead would open a second file a
day for a number already in the first.

**A row with no clock produces no row.** An item the planner listed and no shard
ever picked up has no start, no total and no shard. The contract says an absent
row reads as never worked, which is exactly true of it.

**The run's zero is the earliest item start in that run, not the manifest's.**
The manifest's `started_at` is when the process began, and that covers collecting
feeds and planning the day - work no item is charged for and no bar can draw. A
zero there would push every bar right by one constant and make x=0 a moment the
chart never shows.

## What this page does not settle

**Whether the chart is readable.** How the eight steps are coloured, whether the
residual drawn hollow is legible beside them, how many items fit on one screen,
and what a negative residual looks like are all questions about a drawing, and a
drawing is not a contract. Every one of them was settled on 2026-09-16 in
[`../../concepts/console-design.md`](../../concepts/console-design.md), which is
where a person changing the panel arrives. The one clause that was settled here
first, because it is a property of the column rather than of the drawing: the
residual is drawn hollow and never tinted, since nobody has agreed how much
overhead is too much and a colour would publish an alarm that does not exist.

## Design rationale

**The contract landed before the producers.** A consumer that starts reading a
shape the writers then change is a migration nobody needed, and the cost of
getting it wrong is paid by every writer at once. The cost of getting it right
early is one file with no caller for as long as it takes the writers to arrive.

## Rejected alternatives

| Option | Why rejected | What it would cost to take |
| --- | --- | --- |
| Build the chart first and infer the shape from what it needs | the chart would ship against empty columns and apologise, which is what the console already does on three panels | one rebuild of the projection after the columns fill |
| Draw from `span-rollup` alone | the rollup is folded per shard and per span name, so it knows how long fetching took and never which article was being fetched. It cannot place one item on a clock | a second per-item store |
| Fold the residual into the step beside it | that step then reads as slower than it was, and no reader can tell the overhead from the work | nothing - it is cheaper to leave it out, which is what makes it a trap |
| Clamp a negative residual to zero so every bar draws | the only signal that two steps overlapped disappears, and the known overlap is real rather than hypothetical | the same column, minus the one thing it catches |

## See also

- [`console-payloads.md`](console-payloads.md) - every dataset the operator
  console reads, its producer, and what may not cross the boundary.
- [`../../concepts/console-design.md`](../../concepts/console-design.md) - how
  the panel draws this shape: the ramp, the gutter, the axis and the two ways a
  residual is drawn.
- [`../contracts/schemas.md`](../contracts/schemas.md) - how a persisted shape is
  versioned, stamped and generated.
- [`../../concepts/telemetry.md`](../../concepts/telemetry.md) - what the
  pipeline records about itself, and the rule against two accounts of one number.
- [`../sources/item-health.md`](../sources/item-health.md) - the per-item census
  six of the eight step names come from.
