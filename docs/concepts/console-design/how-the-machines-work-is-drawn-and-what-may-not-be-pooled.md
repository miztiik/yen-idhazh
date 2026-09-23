# How the machine's work is drawn, and what may not be pooled

**Last Updated**: 2026-09-23

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

- **The machine is the unit, and the pooled figure is deleted rather than kept
 for comparison.** Each group prints its own read rate, write rate and
 multiple, from its own shards, sum over sum. One headline survives and it is
 the write-cost multiple of **the machine that read the most tokens in that
 run**, named on the line.
- **Shards that recorded no machine are their own group and are never merged
 into a named one.** 24 of the 380 committed rows have no processor name, and
 folding them into a machine attributes somebody else's seconds to it.
- **The one case where pooling is allowed carries its own sentence.** Where no
 shard of a run named a machine at all, the single group IS the pooled split,
 and the panel says so: a run that drew more than one machine - 86 of the 90
 did - would have had two machines averaged into it.
- **A run that drew one machine says so too.** That is a good state, 4 of 90,
 and the panel reads as one rather than as a panel with a missing spread.
- **Colour is assigned ascending by key, and the key is the machine's digest
 where one was recorded and its model-name string where none was.** Arbitrary
 on purpose: by speed or by draw count the ramp would encode an ordering it
 does not mean, and by order of first appearance a machine would change colour
 when the operator changed the span - which is the control the colour exists to
 survive. The ramp is assigned once for the page, over every machine any panel
 can show at any preset, so the assignment is fixed for a build.
- **`--chart-8`, the grey, is reserved for "Machine not recorded" and is given
 to no machine.** An absence is not a machine and must not take a machine's
 hue.
- **`console.machine_colour_stops` bounds the ramp, and the overflow is named in
 words.** Seven machines take seven stops; an eighth folds the tail into one
 row that lists its members. Never two machines in one colour without the page
 saying so.
- **The name is on the row, always.** Colour here encodes a fact, so it is
 semantic and may never be the only carrier of it. That is also why the split
 is rows rather than a scatter: a scatter cannot carry a name per mark.
- **A card carries every watched instruction-set flag, present or absent.** A
 present flag takes `--tint-accent`; an absent one takes a hairline outline at
 the same width. The machine we draw most reports none of the watched AVX-512
 entries, so a list of what a machine has cannot show the one it is missing -
 and the missing one is what decode dispatches on. **Never read** and
 **reported none of them** are different facts: the first draws no chip and
 says so.
- **The copy rate and the buffer it was taken with are one sentence, and a rate
 nobody can grade is withheld.** The buffer has to be at least
 `observability.host_fingerprint_bandwidth_cache_multiple` times the machine's
 cache before anybody can say the copy left it. Measured 2026-09-21 over the 65
 committed host rows, nine fall short - a 512 MiB buffer against 260 MiB or
 480 MiB of L3 - and **those nine are the slowest rates in the fleet, not the
 fastest**, so the short buffer is a reason to distrust them rather than
 evidence they read high.
- **A card says what clock the machine ran at and how long it had been up.**
 Uptime is there because a machine started minutes ago still has an empty page
 cache, which is one of the two reasons a run reads its weights back off disk -
 without it the eviction strip has one explanation instead of two. That reason
 is why the reading earns its place and **is not printed on the panel**: a
 Hardware subtitle is one sentence ending in its own grain, so a second sentence
 explaining a card would break the rule that keeps the page scannable. Every
 committed row is a freshly started machine: 2.6 to 38 minutes of uptime, median
 3.8 minutes, over 65 rows on 2026-09-21. **The clock prints alone.** The
 ceiling column a share would divide by is empty on all 65, so a card that drew
 a percentage of it would publish the empty-column defect a second time. Both
 are sentences rather than bars: one reading each, with nothing to compare it
 against.
- **L3 and the copy rate are lengths on a track every card of the panel
 shares.** Two numbers in two sentences on two cards is a subtraction the
 reader performs; two bars on one domain is a difference the eye reads. The
 reading stays in words under its own bar, so the track is the comparison and
 never the carrier of the number.
  - **Each measure has its own domain and it comes from the readings drawn.**
    No runner model publishes a ceiling for either, so there is no limit to
    measure distance from: a fixed maximum would clip the next bigger machine
    or spend the track on room nothing reaches. The domain is anchored at zero
    and niced by `linearAxis`, which makes two lengths the two readings.
  - **MiB of cache and GiB/s of copy rate share no axis.** They are two
    quantities, so neither reading can be read off the other's length. The
    twenty-to-one test does not apply between them and is never taken.
  - **An ungraded rate is refused rather than pooled with the graded ones**:
    nobody can say what a copy over a buffer that did not clear the cache
    measured, and a length on the shared track would claim they can. The card
    says why its rate is not drawn.
  - **Under two readings of a kind there is no bar.** A lone bar's domain is
    its own value, so it fills the track whatever it says, and a full bar reads
    as a maximum rather than as the only one. Named on the card, because a bar
    missing beside a bar drawn is the state a reader would otherwise have to
    work out. The three refusals are `absent`, `alone` and `ungraded`, and
    `data-machine-bar-state` carries whichever holds.
- **A count of machine kinds is a count and never a rate.** No percentage, no
 probability, no pie: what the next job will draw is precisely what the
 processor lottery refuses to quote. Under `console.fleet_min_rows` it is a
 list with a sentence and **no bar at all** - bars over a handful of placements
 read as a distribution, and a reader who has read one will act on it. **It
 ships at 160 as a declared estimate and not a measurement** - see the design
 rationale below.
- **Over that floor the count is a trend, one group a day and one bar a kind.**
 The panel's title asks what the platform has been giving us lately, and a
 ranked list answers which is biggest rather than what is changing. The
 ordering the list carried is not lost, it is the sentence above the plot.
 **Only days that recorded a placement are drawn** - a zero-height group would
 say the platform gave us nothing that day, and a day the record never reached
 says nothing at all - so the count of days missing from the window is printed
 in the same sentence.
- **Past `console.fleet_top_kinds` the rarest kinds are one bar, named in
 words.** A grouped bar is only a bar while it is wide enough to paint: at
 `console.chart_width` of 760 and the widest span the window control offers, 90
 days, a day band is 8.4 px, five bars in it draw 1.09 px each after the chart
 engine's own gaps and seven draw 0.77 px. Four kinds plus the fold row is the
 largest set that clears a pixel there. **The fold bar equals the kinds it
 folded, in the window and on every day of it**, and the page carries both
 figures so it can be held to them agreeing.
- **None of the empty states is tinted and none gets the reserved box.** The
 route is prerendered and reads `state/` at build time, so there is no fetch,
 no waiting state and no unreachable state. Every nothing here is settled at
 build time and gets words. The heading and the note always stay.

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

The arithmetic is proved without a browser and the geometry is proved with one.
The sum is asserted exactly, with no tolerance: a tolerance is the gap the
1.87x stack fits back through
([../../../frontend/tests/memory-held.spec.ts](../../../frontend/tests/memory-held.spec.ts)).
The overlap is read off the two brackets' boxes on the page and held to the
narrower one's full width, so a change that put them end to end fails even
though every number stayed right
([../../../frontend/tests/console-memory-held.spec.ts](../../../frontend/tests/console-memory-held.spec.ts)).
What the readings say, and what the model behind the four-part shape is, are in
[../../reference/pipeline-cost.md](../../reference/pipeline-cost.md#the-machines-own-reading-arrived-and-the-survival-now-makes-sense).

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

## A run's time is drawn on a real clock, at the grain the reader picks

> **The shape of the run is legible before a single number is.** A wide staircase is a run that queued; a solid block is a run that worked in parallel.

The run timeline on `/console/` draws
[`run-timeline/<YYYY-MM>.csv`](../../architecture/publishing/run-timeline.md).

- **A row is one item and the y axis is items, in start order.** Sorted by start
  rather than by cost, because the queue is the thing a reader cannot get
  anywhere else, and this is the only surface on the site that can say WHICH
  article was being read.
- **A shard grain sits on the same switch, out of the same fold.** Item, item
  grouped by the shard that ran it, and one bar a shard - three states of one
  control, built by one call over one set of rows. Two folds over two ledgers
  could name different runs as the newest. A shard's bar runs from its first
  item's start to its last item's end, which is the stretch it held a worker for,
  and its steps are that shard's items added up - so the same seconds are drawn
  at either grain and the switch cannot put two answers to one question on the
  page.
- **The x axis is elapsed milliseconds from the run's start, and the wait is
  position rather than length.** An item that queued forty seconds sits forty
  seconds to the right; nothing is drawn in front of its bar. A category axis -
  one evenly spaced column an item - would hide the queue entirely, which is the
  one thing the panel exists to show. The zero is the first item's own start and
  not the manifest's: the process start covers collecting and planning, work no
  item is charged for, so a zero there would push every bar right by one constant
  and make x=0 a moment the chart never draws.
- **Eight steps, eight chart-ramp stops, fixed by position.** `--chart-1` to
  `--chart-8` against the eight steps in pipeline order is an exact fit. A step
  keeps its stop whether or not a given run timed it, so two runs drawn a day
  apart compare by eye. The ramp deliberately holds none of the confidence hues
  ([../design-system.md](../design-system.md)), so no step of a pipeline is ever
  told by its colour that it is the failing one.
- **Which steps appear in the legend comes from the rows, never from a list in
  the panel.** A step with a number on at least one bar is drawn; a step with none
  is named in words underneath, and the two silences are separated: `plan` and
  `publish` are timed by nothing in the pipeline at all, and any other absence is
  a gap in what THIS run wrote down. An operator acts on only one of those.
- **Hollow is unclaimed, hatched is overclaimed, and both carry a legend key.**
  Neither is tinted - nobody has agreed how much overhead is too much, so a colour
  would publish an alarm that does not exist. The keys are there because a reader
  cannot name a hatched notch on sight, which is the test a mark has to pass: a
  texture nobody can read is a texture that says nothing.
- **The residual is signed, and the sign changes the drawing rather than the
  colour.** Positive, it is a hollow slice extending the bar to the item's full
  clock, and the steps plus that slice are the item's own time exactly. Negative,
  the steps have already outrun the clock - the visual plan is decoded inside the
  summary call, so it is apportioned out of it rather than timed beside it - and
  the overrun is drawn as a **hatched hollow notch laid over the last stretch of
  the bar**, starting where the item really ended. Laid over and not appended,
  because the stretch it covers is time some step has already drawn once; an
  appended notch would make the bar longer than either reading of it. Hatched and
  not tinted, so an overrun and an overhead are told apart by texture rather than
  by a hue that would rank one of them as worse.
- **A bar names its shard, in a gutter, always.** Two bars overlapping on the
  clock is correct exactly when they sit on different shards, and without the
  shard beside them a reader cannot tell an overlap from a contradiction.
- **Under 24 bars each carries its item id; above that the gutter keeps the
  shard alone.** Density is the service here: a run of four hundred items is a
  wall of thin bars on purpose, because the wall IS the answer, and four hundred
  labels would be four hundred things to read instead.
- **`console.timeline_bars` caps the drawing and never the arithmetic.** Every
  figure above the bars - the span, the work, the items at once - counts the whole
  run, and the panel says how many of how many it drew. A panel that reported the
  run it drew rather than the run that ran would be a quieter kind of wrong.
- **Three figures land before any bar**: what the run took end to end, what its
  items cost added up, and the second divided by the first. That third number is
  the one that says staircase or block - one means a queue however many shards
  were running, and four means four shards genuinely busy together.
- **The four sub-steps are printed figures and never bands.** `robots`, `tag`,
  `render_prompt` and `parse_reply` nest inside steps the bars already draw, and
  together they come to far under one pixel of the track, so they sit under the
  bars as figures with the step each runs inside. A reader who takes `tag read`
  for a step beside taking the article out adds it twice, which is why the place
  it runs is printed next to it rather than left to be guessed.

**A column the panel reads has to carry a value somewhere on the canary day, or
the panel does not ship.**
[../../../frontend/tests/console-pipeline-timeline.spec.ts](../../../frontend/tests/console-pipeline-timeline.spec.ts)
takes the declared list off `run-timeline.ts`, reads `backend/var/canary/`, and
fails on any column empty across every row - then checks on the page that every
step in the legend has a slice behind it and that all eight are accounted for as
drawn, unproduced or unrecorded. The same file holds the grain oracle: it reads
the two arrays off the page and holds the shard grain against the item grain,
per shard and per step. The canary is the right fixture because it is
fixed in size (`CLAUDE.md` Guardrail #12) and because it is built, so it carries
a case the archive has never produced: not one committed census row records an
item clock, so nothing but a built day can place an item on one.

**Three panels would fail that gate today** and are left for a later row. Measured
2026-09-16 over the canary's own published payloads, by counting non-empty cells
per column across every row of each file: the one `day-metrics` record the canary
holds carries `extraction` null, `throughput` null and `stage_timing` empty, so
the extraction census, the throughput figures and the stage-timing panel each
fall back to a "nothing was measured" sentence on the fixture the browser suite
runs against. One further column was empty on every canary row without a panel
behind it - `day-metrics.addresses_considered` - which is a different defect and
a cheaper one. The `run-days` and `span-rollup` payloads are clean.

## Design rationale

**`console.fleet_min_rows` ships at 160 and 160 is a declared estimate, not a
measurement.** The share behind it is measured: the rarest of six machine kinds
held 11 of 356 committed counter rows, 3.1 percent. The row count is not.
`console.min_attempts_for_rate` already sets five placements as the floor under
a rate, and five at 3.1 percent needs about 162 rows, so 160 is that arithmetic
rounded. It justifies nothing about the shape of the page: above the gate the
counts are bars, below it the same counts are a list, and both say the same
thing. What would settle it is a seventh machine kind arriving - every share
drops, the rarest gets rarer and the bar rises - so the number is re-derived
from the committed rows rather than argued with.

**The machine card's two readings are lengths rather than sentences, and that is
what carries the two-second check.** `32 MiB` beside `260 MiB` on two cards is a
division the reader performs; two bars on one track is not. The twelve flag chips
are load-bearing for the same gate: a definition list of text rows with a
semicolon-joined vendor string is a 2004 page, and dropping the chips fails
**made this year**.

## Rejected alternatives

| Option | Why rejected | What the reader loses |
| --- | --- | --- |
| Bandwidth against decode speed, as a scatter | Two points define a line, so a scatter of two is a claim rather than a measurement. It ships at `console.fleet_min_rows` rows **and** `console.bandwidth_min_kinds` distinct kinds carrying a bandwidth reading. | The only on-screen test of whether decode is really bandwidth bound. The card prints the reading per machine and draws it against the other machines of the run, so only the correlation is absent. |
| A processor detail table | Twenty-seven columns is the reference page's job. | Reading a raw column value off the console. Five columns were bought back: the card's own `<details>` carries size, region, zone, fault domain and `microcode` - the one cell that moves without anything else moving. |
| Hashing a machine to a colour stop | It collides about 60 percent of the time over six kinds in seven stops, and a collision is a lie the page cannot see. | - |
| Printing an ungraded copy rate with a caveat | A caveat under a number does not stop the number being compared, and these sit at one end of any ranking. | Nine of 65 rows show no rate at all; the card says why. |

## See also

- [../console-design.md](../console-design.md) - what a figure may say, and in what words.
- [the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md) - the thirteen rules these panels obey.
- [the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md) - the range mark and the two-named-ends mark these panels draw.
- [../../architecture/publishing/console-machine.md](../../architecture/publishing/console-machine.md) - what each Hardware panel is, and where its data comes from.
- [../../architecture/publishing/run-timeline.md](../../architecture/publishing/run-timeline.md) - the ledger the timeline reads.
- [../../reference/host-metrics.md](../../reference/host-metrics.md) - every machine column, and what it reads.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the instrument log the console never quotes from.
