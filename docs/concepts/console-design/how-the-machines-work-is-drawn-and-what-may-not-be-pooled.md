# How the machine's work is drawn, and what may not be pooled

**Last Updated**: 2026-11-14

The Hardware route and the run timeline draw one machine's work. One measurement
shapes all of it: **a run does not get one machine.** Measured 2026-09-17 over
the committed shard records - 380 rows, 95 runs, 19 dates - **86 of the 90 runs
that name a processor drew more than one kind of processor**. Kinds per run: one
on 4 runs, two on 39, three on 43, four on 4. Inside a single run the read rate
between the fastest and the slowest machine runs 1.00x to 6.08x, median 2.32x,
and 45 of the 86 exceed 2x. Run `2026-09-12-34689544296` read at 59.71 tokens a
second on one shard's machine and 9.83 on another's.

So the rules below are not a preference about charts. **A figure pooled across
the machines of one run is wrong on 95.6 percent of runs**, and it was the most
quotable number on the route.

What each panel is and where its data comes from is
[../../architecture/publishing/console-machine.md](../../architecture/publishing/console-machine.md).
The chart rules these panels obey are
[the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md).

## A machine is a colour and a name, and no rate is pooled across two of them

- **The machine is the unit, and no pooled speed headline survives.** Hardware
 now draws Reading and Writing separately, as ranked comparisons against the
 reference machine of each run. The reference is the kind with most qualifying
 articles; its name breaks a tie. Each article is normalized against that run's
 reference middle before a kind's typical seconds are quoted. Missing reference
 readings stay unqualified. The old machine-split boards and their write-cost
 headline are no longer Hardware drawings.
- **Shards that recorded no machine are their own group and are never merged
 into a named one.** 24 of the 380 committed rows have no processor name, and
 folding them into a machine attributes somebody else's seconds to it.
- **A machine without a name cannot become the reference.** It does not acquire
 another machine's speed by pooling. Hardware names the missing comparable work.
- **A run that drew one machine says so too.** That is a good state, 4 of 90,
 and the panel reads as one rather than as a panel with a missing spread.
- **Daily placement history groups jobs by exact reported L3 bytes across CPU
 vendors.** MiB is a display conversion, not a grouping rounded to a bin.
 The widest bounded host query fixes the descending capacity order and colour
 positions across presets. Capacities sample the full configured chart palette
 rather than adjacent shades of one hue, so neighbouring groups remain distinct.
 Numerical legend order carries capacity order; darkness does not imply rank.
 Missing L3 is a separate neutral `L3 not measured` group; measured zero stays
 `0 MiB L3`. CPU names and versioned fingerprint qualifiers remain in job
 details. Equal capacities do not imply equal topology or performance.
- **These are recorded job counts, not independently identified machines.**
 A fingerprint groups reported characteristics, not physical hosts. Repeated
 rows remain counted as jobs. The ledger contains no L2 capacity, so no L2
 aggregate is offered and the limitation is printed beside the chart.
- **Each measured capacity gets the same decorative gradient treatment.**
 The existing gradient switch keeps fills flat when false. When true, an
 opaque lighter-to-base gradient restarts within each capacity subsegment or
 job square, with matching swatches. Existing appearance tokens and the
 uniform tint floor supply the stops in both themes. Neither tint nor gradient
 carries speed, utilization, health or probability.
- **The name is on the row, always.** Colour here encodes a fact, so it is
 semantic and may never be the only carrier of it. The rankings use named rows,
 not a scatter that cannot carry a name per mark.
- **A count of jobs is a count and never a rate.** No percentage, no
 probability, no pie: what the next job will draw is precisely what the
 processor lottery refuses to quote. Under `console.fleet_min_rows` placements
 it is **one square a job**, a column a day - a bar over a handful of
 placements reads as "this much" and invites a rate the count cannot support,
 while a square a job reads as "these ones", because every mark is a job a
 reader can point at. A day's squares stand as a block no wider than the
 busiest day's is tall, so a day's height is its count and kinds with the most
 jobs fill from the bottom. **It switches at 160 as a
 declared estimate and not a measurement** - see the design rationale below.
- **Over that floor the count is one bar a day, split by the reported L3 capacity
 that ran its jobs, largest daily count at the bottom.** The panel's title asks which
 machines ran our jobs, day by day, and a ranked list answers which is biggest
 rather than what is changing. Rank each day independently, not by a whole-window
 series total or machine speed. **Only days
 that recorded a placement are drawn** - a zero-height day would say the
 platform gave us nothing that day, and a day the record never reached says
 nothing at all.
- **Every observed capacity remains visible, with no speed-based folds.**
 The legend sits below the plot in wrapping vertical columns, largest L3
 first and unmeasured last. Actual daily counts still determine stack position.
 Selecting a day opens all capacity counts, known zeros and actual jobs
 under their own qualified CPU names, with each job's reported L3.
 The held day stays outlined; phone job details wrap instead of scrolling.
- **Framing and hover are compact, not incomplete.** Keep the title, one
 context line and the capacity/swatch key. Only small-cohort mode adds `One square
 per job.` Below the plot are the selected UTC day and total recorded jobs,
 without a selection instruction. Actual mark hover shows only that date, capacity and its
 exact capacity-day count out of the day's recorded jobs. Day space shows the
 date and total. Keyboard/touch selection exposes complete counts and speed
 notes plus run, job or pipeline/task, shard, machine, L3, seconds and speed.
- **The machine mix reads after mount through the shared query reader.** Its
 window is the route's own, ending on the common item-health, host-fingerprint
 and run-shards evidence day, and
 the door starts it no earlier than the day the record began. It asks only for the columns it draws. Changing the window keeps
 whole files already read, and a late answer cannot replace a newer selection.
 The widest host query fixes the capacity and identity universes, but the document carries
 no fleet rows. The drill-through uses the rows
 already fetched for the window. `data-readout-fetched` declares that this
 panel's strip arrives with those rows and is absent from the initial document.
- **The machine mix draws four distinct empty states.** Loading keeps the
 chart's reserved height and shimmer. A covered window without jobs is quiet;
 an unpublished ledger is missing; a hole, failed fetch or engine failure is
 unreachable and uses the warning tint. Lost evidence is not a recorded zero.
 The heading and note always stay. The shared
 [query-reader contract](../../architecture/publishing/how-the-query-door-answers-a-panel.md)
 owns the fault names and file rules.

**A panel title may not name a machine as if a run had one.** "The host under
the newest run" let the page carry one processor string for the whole of its
life, and that framing is why a panel summing four counters across three
machines read as correct for weeks. **A run is not a machine** is the most
load-bearing fact on this route, and a title that hides it hides everything under
it.

## What is holding the machine's memory is two parts a reader may add, and two brackets they may not

> **Abutting slices invite addition.** Where the numbers cannot be added, the marks overlap on purpose, and the reader never has to be told.

The bar first asked for was four slices side by side summing to the machine: the
model server, our own python, the page cache and what is free. **It cannot be
drawn, and that is measured rather than feared.** Stacking those four exceeds the
machine on **378 of 378 committed rows that carry a machine reading, by 1.21x at
the narrowest and 1.87x at the widest, measured 2026-09-21** over
`state/item-health/`. Two independent double-counts produce it. The weight file
is mapped rather than read in, so its pages are resident in the model server and
counted in the page cache at the same moment. And what the kernel reports as
available is mostly that same reclaimable page cache, so the page cache is
already inside the free slice.

**So the bar draws only what partitions the machine, and everything else is a
bracket.** Two parts abut and add up exactly: what the kernel says it could still
hand out, and what is held. Under them sit the two process readings, each
labelled *at most*, **both anchored at the bar's origin so they visibly sit on
top of each other**, with the stretch they both claim tinted across both rows. A
reader can add two bars drawn end to end and cannot add two that overlap. That is
the whole mechanism: the refusal is in the geometry, and the caption only
explains what the eye has already been stopped from doing.

**A bracket is drawn against the whole bar, never inside the held part.** The
model server's resident set is **larger than everything the kernel calls held on
375 of those 378 rows** - a median of 75.5 percent of the machine against 52.3
percent held. Drawing it inside the held part would be a false statement about
99.2 percent of the record, and it would quietly retract the word *at most*: the
difference is the mapped weight pages, which are resident and reclaimable at the
same time.

**Where the row carries what each process holds on its own, the held part splits
and the bar has four abutting parts after all.** Anonymous memory is not
file-backed, so it cannot double-count with the page cache and the parts close.
Those two columns exist on the item row and **no committed row carries either**,
so the four-part shape reaches a reader through the canary first. The panel draws
whichever shape the row supports and **prints which one the reader is looking
at**, per bar and in a sentence under the list.

**The remainder keeps its sign, and the bar is widened rather than trimmed.**
Where the two own-memory readings together exceed what the kernel says is held,
two readings taken a moment apart have disagreed. The bar is drawn against a
scale that holds the overshoot, the machine's own edge is marked inside it, and
the amount is printed. Clamping the remainder to zero would delete the finding
while leaving every sum looking correct - the same rule the unclaimed-time column
already carries.

**The swap is ruled underneath, on the swap file's own scale.** Measured over the
same 378 rows: a median of 60 KiB, a p90 of 61.1 MiB and a worst of 657.9 MiB
against a 3.00 GiB swap file. On the machine's scale the median is four
ten-thousandths of one percent and paints nothing, which is the sub-pixel band the
chart rules refuse; on the swap file's scale the worst row is 21.4 percent and is
a mark worth drawing. Either way the figure is printed in words beside it, and a
swap that reads zero says so rather than drawing an empty track with no
explanation.

**One bar is one moment.** Each day draws the row where the kernel had the least
left to hand out, and names the article it came from, so every part of that bar
is read off one row. An average of two moments that never met is not a thing the
machine was ever holding.

The sum is asserted exactly, with no tolerance: a tolerance is the gap the
1.87x stack fits back through
([../../../frontend/tests/memory-held.spec.ts](../../../frontend/tests/memory-held.spec.ts)).
The two brackets must overlap by the narrower one's full width; putting them
end to end would misstate the memory even if every number stayed right.
What the readings say, and what the model behind the four-part shape is, are in
[Interpreting machine memory](../../reference/pipeline-cost.md#how-much-of-the-runners-memory-a-run-needs).

## The two rates on a shard row are measured before they are drawn

Reading and writing are two series on one board, so the 20x rule binds: they
share one domain while the larger is under 20x the smaller, and past that writing
takes its own. The board measures the ratio from the run it is drawing and prints
it, rather than choosing once and hoping. Measured 2026-09-20 over the three
newest committed runs, a shard writes at 3.39 to 5.09 tokens a second; the read
rates on the same ledger have run 9.73 to 41.98. That is about 12x at the widest,
so the two share one scale today - and the panel will say so, or say the
opposite, from whatever run it has.

The rate domain is the largest rate on the board and never a round number. A
shard reading at a quarter of its neighbour draws a quarter-length bar, which is
the reading the panel exists for.

## A run's elapsed windows and item work answer different questions

The [native run timeline](../../architecture/publishing/run-timeline.md)
uses one shard row per view, longest first. Its default elapsed view preserves
recorded starts and ends; its work view starts every cumulative cost at zero.
Neither longer work nor a later finish is labelled inefficiency.

Blank space before and after an elapsed window means a later recorded start or
an earlier final completion. Do not draw the full axis as a hollow progress
track: it invites the false reading that every shard should fill it. Internal
busy/idle stretches are not recorded by this instrument.

Keep whole-run duration and cost coverage beside their headlines. A missing
measurement is not zero, and an item missing an endpoint can still have a
recorded cost. Never label work divided by elapsed time as simultaneous items
or busy shards.

Selecting a row opens a paginated article inspector, retaining exact recorded
readings and start-time ordering without a default row per article. The
inspector's stage averages use the shared complete-cohort reconciliation;
nested calls are non-additive details. Stage colors retain their shared
quantity tokens. Signed gaps remain readings, not invented chronological
regions.

## Design rationale

**Read/write token volume keeps every recorded run.** Two categorical traces
share one token scale: Read is solid and Written dashed. Monotone-X
interpolation passes through the actual values without invented extrema; it
does not average or smooth measurements. Only selected or isolated values need
markers. Repeated UTC date labels thin through `runTicks`, never by dropping
runs. The axis explicitly says run sequence, not elapsed time.

The existing readout snaps to an actual run for pointer, tap and keyboard
selection. It prints exact Read/Written values, full run ID, UTC date and
measured versus recorded articles. Rest and Escape use the last known run,
even when unmeasured. Run total and actual Median per article are radios over
one in-memory answer. No anomaly threshold, baseline or failure-colour verdict
is implied by either trace.

**The two independent clocks open Hardware.** The item ledger and the server
measurement can disagree. A ranked percentage gap, with its allowed-gap rule,
decides whether a quoted speed can be trusted before any speed drawing follows.
The count needed to refuse an impossible shard index comes only from the
recorded manifest count, through the narrow `run-shards` ledger. Unknown remains
unknown; neither observed machines nor configuration supplies that denominator.

**Requests and memory now answer different questions.** Context draws label and
summary request distributions against recorded per-slot limits, not a run strip
that conflates calls. Two positive readings is the smallest distribution floor;
the route knob names that cost. Closest-to-memory ranks the tightest held reading
of each dated article against its own total machine memory. Memory-held retains
its process-overlap brackets. The removed prompt-to-memory carry was speculative:
the ledger has no call-boundary measurement that attributes memory separately to
read and written tokens. It is not moved to another panel.

**All dated comparisons name settings changes.** A changed date with no measured
column is named in words as an undrawn rule. No marks is not evidence that the
model did not change. The five tail plots still share one scale and one rule.

**The window needs no full-record context band.** It always ends at the newest
day, and the route prints its dates; another band would repeat that context.

**The job list closes with Close, Escape or selecting the same day.** Outside
clicks do not discard a deliberate selection, and closing returns focus to the
chart.

**Sparse windows keep the reserved plot space and small job squares.** Enlarging
a few jobs would make the same count look different when the window changes.

**`console.fleet_min_rows` ships at 160 and 160 is a declared estimate, not a
measurement.** The share behind it is measured: the rarest of six machine kinds
held 11 of 356 committed counter rows, 3.1 percent. The row count is not.
`console.min_attempts_for_rate` already sets five placements as the floor under
a rate, and five at 3.1 percent needs about 162 rows, so 160 is that arithmetic
rounded. It justifies nothing about the shape of the page: above the gate the
counts are bars, below it the same counts are a square a job, and both say the
same thing. What would settle it is a seventh machine kind arriving - every share
drops, the rarest gets rarer and the bar rises - so the number is re-derived
from the committed rows rather than argued with.

**Reported L3 capacity is the useful ordered reading of placement history.**
 CPU model categories hid the cache comparison behind many unrelated hues.
 Combining vendors by exact cache bytes answers the available question without
 claiming equivalent performance or unique host counts. Closely spaced tints
 obscure the boundaries between capacity groups, especially in narrow stacks.
 Sampling the full configured palette separates those groups; numerical legend
 order carries rank instead of darkness. The tint floor and gradient switch
 still control the decorative fill. Daily count ranking may move segments
 without changing their capacity colour.

L2 aggregation requires a separately declared and collected L2-capacity field;
historical L2 cannot be inferred from L3 or CPU names. Unique physical-machine
counts would additionally require reliable host identity evidence, not the
existing hardware fingerprint. Neither new measurement is part of this view.

## See also

- [../console-design.md](../console-design.md) - what a figure may say, and in what words.
- [the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md) - the thirteen rules these panels obey.
- [the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md) - the range mark and the two-named-ends mark these panels draw.
- [../../architecture/publishing/console-machine.md](../../architecture/publishing/console-machine.md) - what each Hardware panel is, and where its data comes from.
- [../../architecture/publishing/run-timeline.md](../../architecture/publishing/run-timeline.md) - the ledger the timeline reads.
- [../../reference/host-metrics.md](../../reference/host-metrics.md) - every machine column, and what it reads.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the instrument log the console never quotes from.
