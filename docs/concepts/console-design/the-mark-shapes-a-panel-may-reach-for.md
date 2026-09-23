# The mark shapes a panel may reach for

**Last Updated**: 2026-09-23

Five named shapes and three panel-level controls. Each is here because a reader
was doing arithmetic the drawing should have done for them, and each carries what
it cannot say - a shape reused where it does not fit is a shape a reader stops
trusting.

The rules these shapes obey are in
[the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md).
What a figure may say in words is [../console-design.md](../console-design.md).

| Shape | Use it for | It cannot say |
| --- | --- | --- |
| Range mark | one quantity's typical reading and its worst | anything about the shape between the two ends |
| Two-named-ends mark | two different measurements of one thing | when inside the item either end fell |
| Span track | one reading against the window it sits in | when in the window each end fell |
| Tile strip | a reading that is quiet on most days | how big the reading was on the day it fired |
| Reserved box | a panel whose rows have not arrived | which of the four nothings it is holding - the page says that once, above |

## A typical reading and the worst one are one mark, not two bars

A **range mark** is a track with a fill and a notch. The fill runs to the median
and the notch stands at the maximum, so the distance between them is the spread
and the reader measures it with their eye rather than by subtracting two
sentences.

**Why it exists: four bars a row is eighty bars.** The shard board carries a
memory reading and a processor reading, each with a typical value and a worst
one. Drawn as bars that is four per row, and a run of twenty shards is eighty
bars in one panel with the reader pairing them by eye. Drawn as two range marks
it is two tracks, and the pairing is already done.

**What the reader loses, named.** A range mark says nothing about the shape
between its two ends: a shard whose items were all near the median and one that
had a single spike draw identically. That distinction belongs to a distribution
panel over items, which is a different grain and a different question - the
board is a break panel over shards, and its job is the extreme and the shard
that owns it.

Both marks obey the first chart rule. The memory mark takes the runner's 16 GiB
into the domain beside the drawn values rather than as the maximum, so a shard
that went past the ceiling would still draw past the line, and the panel prints
the ceiling. The processor mark is a share, so it runs nought to a hundred.

## A mark with two named ends is not a range mark, and it says which end is which

A range mark has a typical end and a worst end, and the reader learns that shape
once. **A mark whose two ends are two different measurements is a different
mark**, and giving it the range mark's field names would have taught a reader to
read a floor as a median. So it carries its own names.

The shipped one is the kernel headroom mark on the memory panel of
`/console/machine/`. Its fill runs to `os_mem_available_min_bytes` - the least
memory the kernel had while the model worked on that item - and its notch stands
at `os_mem_available_bytes`, which is what the item left when it ended. **A
machine whose floor falls and whose end also falls is leaking; one whose floor
falls and whose end recovers was only working hard.** The two states draw
differently, and the floor alone draws them the same.

**What the reader loses, named.** The mark says nothing about when in the item
the floor fell, so an item that dipped once and an item that sat at the floor
throughout draw identically. That is a question for a sampled series over one
item, which is a different grain and an instrument nobody has built - and the
panel says it cannot answer it rather than leaving the reader to assume it did.

## A reading and the window it is read against are one track

A **span track** is a band and an upright. The band runs from the lowest reading
the window holds to the highest, and the upright stands where the newest run
read. Whether that run was unusual is then one look, rather than three numbers a
reader converts and subtracts.

**Why it exists: a sentence cannot be compared with the sentence beside it.** A
reading followed by its span in prose, in a different unit from its neighbour and
with its ends buried mid-paragraph, makes a reader do the conversion by hand
before they can say which of the two was the odd one this run. Two tracks make
that comparison free.

**No panel draws a span track today.** The shape is kept whole, with its rules
held in `frontend/tests/console-host-spans.spec.ts`, because the honest version
of the processor share - the one that separates out the time the host gave
another tenant - needs this band rather than a second one. **What that costs:** a
rule nothing currently obeys, which is a rule that can rot without a page going
red. A panel that draws it owes a page oracle putting a real band against the
numbers printed beside it.

**One shape, one place it is written down, and no copy to keep in step.** The
maths lives in `frontend/src/lib/charts/span-track.ts` and nowhere else. Two
pieces of markup that have to agree by eye are how a marker in one panel and a
verdict in another come to disagree about one number with nothing on screen
looking wrong.

**What the reader loses, named.** A span track says nothing about the shape
between its ends, and nothing about when in the window each end fell: a figure
that drifted steadily and one that jumped once and held draw identically. That
is a question for a series over runs, which is a different grain - `Whether the
slowest articles are getting slower` on `/console/machine/` is the panel built
for it, for a different figure.

**An absent span is said, never drawn.** Where no run in the window recorded the
figure the panel says so in words and draws nothing, because a band of no length
would report a window that read the same thing every day. Where the window has
both ends but they sit closer than one pixel at `console.chart_width`, the span
is printed and the band becomes a mark - the sub-pixel rule applied to a band
rather than to a split. A run that recorded nothing keeps the band it cannot be
placed on: the window still measured something, and the missing upright is the
fact.

**A figure with no span is not given a track.** A count of the slots a server was
started with has no low-to-high window to place a run inside, so it is a line of
text. The range rule binds a figure with a span, and nothing else.

## A reading that is quiet on most days is a strip of tiles, never a line

> **A rare event has no useful value axis.** Draw one tile a day at a fixed
> height, in three states, and lead with the finding in words.

A rare reading is one that sits at zero or is absent on most of the days in the
window and matters enormously on the few where it does not - a processor another
tenant took, the kernel reading the model's weights back off disk. **A line or an
area over days cannot draw one, and the reason is the value axis.** Auto-scaled,
the axis takes its top from the largest day in view, so a window whose worst day
was trivial draws exactly like a window whose worst day was severe and the reader
learns nothing from the shape. Fixed to the threshold instead, almost every day
is a flat line on the floor, the panel looks broken, and the reader stops
opening it. There is no third setting.

**So the panel is a strip: one tile a day, or one tile a shard, and the tile
carries a state rather than a height.** Three states, never two:

| State | What it means | How it is drawn |
| --- | --- | --- |
| Not recorded | The run predates the column, or the machine did not answer | A blank cell, visibly different from a quiet one |
| Recorded and quiet | The reading was taken and sat under the first threshold | An outlined tile |
| Recorded and fired | The reading crossed the first threshold | A filled tile |

**Two states would be the default failure**, because the archive for a new
column is mostly absent and an absence drawn as a quiet day is a panel claiming a
clean machine on every run that predates its own instrument.

**Two thresholds a signal, and both are config knobs.** The first decides whether
the tile fills; the second decides whether the panel's headline sentence names a
worst case. One threshold cannot do both: a bar low enough to catch a day worth
looking at is far too low to be worth a sentence. They are declared as
`console.<signal>_marked` and `console.<signal>_named` in
[`config/appearance.json`](../../../config/appearance.json), the contract refuses
a `_marked` above its own `_named`, and moving either is a config edit with no
source change (Guardrail #6).

**The panel leads with the finding as a sentence and the strip is the
evidence.** A panel whose finding is only a shape makes the reader do the
reading, and the whole point of a rare-event panel is that it is scanned and not
studied. **The strip is the same height whether or not anything fired**, so an
operator who has learned where it sits checks it in one glance and the page does
not reflow on the morning something goes wrong.

**Where the underlying figure changed meaning on a date, the strip prints the
correction.** A reading that was collected differently before some date is two
readings sharing one name, and a panel that draws both without saying so reports
a clean past. The processor-lost strip carries that sentence because the busy
figure counted stolen time as ours until 2026-09-20
([../../architecture/sources/item-health.md](../../architecture/sources/item-health.md#what-the-processors-did-and-what-was-taken-from-them)).

## A console panel reserves its room, and names which nothing it is holding

> **A reserved box with no failure state lies, and a failure state with no reserved box shifts the layout.** They are one decision.

Every row the console draws arrives by fetch, which splits one "nothing" into
four - and three of them would draw the same unmarked gap, so **a quiet pipeline
and a broken fetch would be the same picture.** That is the exact pair this
section exists to tell apart.

| State | What happened | What is on screen | What the operator does |
| --- | --- | --- | --- |
| Waiting | the month files are in the air | the axis frame, its ticks, and marks that shimmer | wait |
| Quiet | every month arrived and held nothing | the panels' own empty sentences, plus one line naming the preset that reaches a month with rows in it | widen the window |
| Missing | the pipeline never wrote those months | the panels' own empty sentences, plus one line naming the months in words | nothing - it is real |
| Unreachable | a month was asked for and did not come back | the reserved shape, and one warn-tinted line naming the month, what is drawn instead, and a retry that names its own subject | press it |

**The box appears where a panel's own words would be false, and nowhere else.**
That is the whole rule, and putting the box in front of every non-ready state is
the shape to refuse: a panel with rows on the way that printed "nothing is on
record" would be wrong for the next second, and one whose month did not arrive
would be wrong outright - those are the two the box takes. An empty window and a
real gap are the other way round: the band chart already says "No summaries in
this window" and the failure list already says what it found, and three precise
sentences beat one general one. **What no panel can say for itself is which of
the three settled nothings it is holding**, so that is said once, above the
panels and beside the control that governs the window. The box carries no words
at all for the same reason: a dozen panels each repeating one page-level fact is
a dozen announcements of one thing.

Five rules hold under that table.

- **The box is exactly `console.chart_height` tall, in both the states it
 appears in.**
 [../../../frontend/tests/console-reserved.spec.ts](../../../frontend/tests/console-reserved.spec.ts)
 measures every panel's real bounding box twice in one page session - while the
 months are in the air and once they have landed - and fails on any panel that
 changed size except the one named as fetched. It reads boxes and never a CSS
 property, because a CSS property is not what moves under a cursor. Measured
 2026-09-09 at 1280 CSS px: seven panels, none changed width, one changed height
 by 172 px. **A second case watches the chrome above the panels** - the title,
 the strip, the band, the window control, the carry line and the glance grid,
 each against its own former box. **The set is cut at the first panel's own top
 and never at the fold**: the first panel begins at 894 px, so a 900 px fold cut
 was really asking how tall the runner's fonts were, and on `ubuntu-latest` it
 came back empty and took `main` red. Each block is compared on its own rather
 than the panel's top being compared to itself, because a top says only that the
 total height above it held - a block that grew by the amount its neighbour
 shrank would pass, and the failure would name no block.
- **An empty plot draws its axis frame and its tick marks and no numbers.** A
 tick label needs a value and there is no value, so a number printed there would
 be invented. Both come out of the same `frame` and the same margins the real
 charts use, and the box carries no tint of its own, so the axis sits on the same
 ground the real charts' axes do. Measured over the committed token values:
 `--chart-axis` reads 3.2:1 in dark and 2.58:1 in light on a panel, against
 2.76:1 and 2.38:1 on a tinted box. The waiting frame is exactly as legible as
 the chart it stands in for, neither louder nor quieter.
- **A skeleton mark takes `--color-rule-strong`, and that was measured rather
 than picked.** The sunken surface reads 1.06:1 in dark and 1.13:1 in light on a
 panel - a block nobody can see is not a block, and in light it was gone until
 the sweep crossed it. Rule-strong reads 1.61:1 and 1.48:1: plainly there, and
 still well under the weight of a drawn mark, which is what a placeholder owes.
- **Every skeleton on the surface is on one timeline.** The sweep is switched on
 by a single attribute on an ancestor, so every block starts its animation in the
 same frame and a test can state the property in one line: every animation
 reports the same `startTime`. Out of phase, a dozen sweeping boxes read as a
 dozen broken things rather than as one page waiting.
- **The sweep starts late.** `console.shimmer_after_ms` is how long a wait has to
 outlast before it is worth drawing as one, so a fetch that lands first never
 animates at all. **It ships at 400 as a declared estimate and not a
 measurement** - see the design rationale below.
- **Only a failure takes a hue.** A quiet window and a real gap are normal, and a
 page that tints normal things like faults teaches its operator to stop reading
 the tint.

**And a retry names its own subject.** `Try again` is shorter and it is what the
shape asks for, but a button read out of the sentence above it then names
nothing. `Try August 2026 again` is three words longer and true on its own. It
re-fetches only the months that failed: a retry that re-fetched the whole window
would spend an operator's connection on months already in hand, and would blank
panels that are answering correctly.

## A stacked chart offers lines only where no data is re-shaped

Stacked says what the mix is and how big the total got. Lines say what one series
did on its own, which a stack hides the moment one band halves while its
neighbour doubles. Both questions are worth answering, so the chart offers both
shapes - **but only where one builder call returns every shape the panel offers**,
never two calls and never a second fetch.

What the rule protects against is **two derivations that can disagree**, where a
reader who finds both has nothing on screen saying which to believe. The
strongest form of it is mechanical and is the one to prefer: hand the engine the
identical `data` list in both shapes and change only `type` and `stack`. Two
charts qualify under that form today - `What is failing, by stage` and `How much
text the model has to read again each time`, both callers of `stacked` - and
`console-chrome.spec.ts` fails the build if their two shapes ever draw different
numbers.

**What the widened form costs.** A running total IS a re-shape, so the identical
array test alone would refuse a cumulative line - and the only shape a cost has
that answers whether it is growing is the cumulative one. Widening the test to
one builder call admits it, and the price is that the byte-identical assertion no
longer covers every switch. A panel whose shapes come out of one call but are not
the same array owes its own oracle comparing the two shapes' numbers.

**The counterfactual-cost panel is the first to ship under the widened form, and
this is the oracle it paid.** `costOverDays` walks the window's runs once and
returns one array of days, each carrying what reading cost, what writing cost,
and the running total to that day. The bars read the first two, the line reads
the third, and neither derives anything. `console-machine.spec.ts` asserts the
line's last point equals every bar added up, and asserts it a second time against
the window total the four figures above the chart print - so the two shapes and
the headline number are one piece of arithmetic reached three ways.
`console-machine-panels.spec.ts` then asserts in a browser that moving the switch
changes neither the day count nor that total, which is what a second derivation
would have moved.

One control per panel, never one per series and never a preference that follows
the reader across the site. A Sankey is not a line and a histogram is not a
stacked bar; forcing the control everywhere would mean massaging data to fit it.

**Reading is the bottom band and writing the top, and the panel measures whether
the split may be drawn at all.** At the committed rate, over the 25 days the
ledger held on 2026-09-20, the writing half ran between 27.4 and 45.4 percent of
its own day, and the thinnest band of all measured 2.0 percent of the tallest
column - 3.3 px of a 164 px plot, so the split draws. The rate is the operator's
to type, though, and a writing rate near zero takes that band under a pixel. The
builder measures the thinnest band against the tallest column before it picks a
shape; under a pixel the column draws whole and the split becomes the printed
figure beside it, with the measurement it was decided on printed too.

## A comparison drawn in one unit can be confidently wrong, so it carries both

**Reading and writing are two quantities only if you count them.** Counted in
tokens they are one quantity in two directions, and so are they counted in
seconds. What the two counts do not have to agree about is which side is bigger,
and where they disagree the unit is the whole answer.

The shipped case is `How much of a run is reading and how much is writing` on
`/console/machine/`. A run reads far more tokens than it writes, so in tokens the
read bar towers. **Reading is batched prefill and writing is sequential decode,
so a tall read bar is not a run that spent itself reading.** A panel that offers
only the count teaches that it is, fast and without a caveat, and a reader who
acts on it tunes the prompt when the clock belongs to the answer. So the panel
carries a unit switch, and the switch is the finding rather than a convenience:
which side is taller in each unit is exactly the question "where did the model
time go", answered by looking rather than by a caption.

**The switch qualifies because one call returns both units, and the row set is
decided once.** An item row is admitted on its token counts, and its `prefill_ms`
and `decode_ms` are then summed over exactly those rows. Two independent filters
would let the two units cover different runs, and a panel whose units disagree
about what they measured cannot be recovered by reading it harder. It needs no
new column: both durations already reach the frontend for the read and write
rates on the shard board.

**Each unit measures its own ratio and prints it**, so the 20x threshold is taken
from the data drawn rather than assumed - and where one unit passes 20:1 the
smaller series takes its own row in that unit only. **What the reader loses,
named:** a unit switch is a state to remember, and an operator who reads the
panel in tokens on Monday and in seconds on Tuesday is comparing two pictures.
The panel opens on the same unit every time and prints the unit beside the ratio,
which is the most a switch can do about that.

## A chart says how much of its window it measured, once, above the plot

On `Time per item, by stage`, one footnote per series says one window-level fact
once per line, and a fourth stage would say it a fourth time. **The count is the
defect, not the length**, so shortening each note fixes nothing. One sentence,
and five rules hold it.

- **Once per chart, whatever the series count.** The fact is about the window,
 not about a line.
- **Above the plot, not below it.** A reader meets a broken line before he meets
 the sentence that explains it.
- **The denominator is the day's own item count**, never the sum of the stages'
 totals: one item waits on all three, so summing counts it three times. Where
 the stages reached different amounts of the same days the numerator prints as
 a range, because picking one stage would be arbitrary.
- **Nothing at all where the window was measured in full.** A sentence that only
 ever says "all of it" is noise, and `SPARSE_COVERAGE` is the line it has to
 fall under - see
 [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md).
- **The open-dot legend is a second sentence in the same paragraph**, printed
 once and only where an open dot is drawn.

Not in the hover strip: `ChartReadout` is one contract capped at
`chart.readout_max_share` and it prints one column's values, so a window-level
sentence there would be a second thing that strip means. The oracle asserts
exactly one `[data-timing-coverage]` and holds its two numbers to an independent
reading of the canary ledger. **The series count appears in no assertion** -
that is what proves the sentence stopped scaling with the series
([../../../frontend/tests/console-timings.spec.ts](../../../frontend/tests/console-timings.spec.ts)).

## Design rationale

**`console.shimmer_after_ms` ships at 400 and 400 is a declared estimate, not a
measurement.** Guardrail #10 refuses an unmeasured number the right to justify a
design, so this one justifies nothing: nothing about the shape of the console
depends on it, and the knob decides only whether a wait short enough to be over
already gets animated on its way past. No median payload arrival exists to derive
it from. What would settle it is in
[../../reference/pipeline-cost.md](../../reference/pipeline-cost.md). Taking the
measurement inside a user-interface row was refused: a user-interface row is not
a measurement harness, and a number measured on a laptop's loopback would be the
wrong number twice over.

## See also

- [../console-design.md](../console-design.md) - what a figure may say, and in what words.
- [the-rules-every-console-chart-obeys.md](the-rules-every-console-chart-obeys.md) - the thirteen rules these shapes obey.
- [how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - the panels that draw the range mark and the two-named-ends mark.
- [../design-system.md](../design-system.md) - the tokens, ramps, motion set and sufficiency gate.
- [../../architecture/publishing/telemetry-series.md](../../architecture/publishing/telemetry-series.md) - the grain every figure was measured at.
- [../config/appearance.md](../config/appearance.md) - `console.*`, the knobs these shapes read.
