# The rules every console chart obeys

**Last Updated**: 2026-09-23

Thirteen rules settled once so that no panel argues them again. Twelve are chart
craft - what the drawing may do. The thirteenth is the question the panel
answers, and it catches more failures than the other twelve together. Under them
sit the three shapes every panel reaches through: the ranked list, the date axis
and the readout strip. **Each rule carries its reason, and the reason is the
load-bearing part** - a rule quoted without it is a half-quote, and a rule whose
reason has stopped holding is a rule to change.

What a figure may say in words is [../console-design.md](../console-design.md);
which shape a panel reaches for is
[the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md).

## Thirteen rules hold for every chart on this console

- **A fixed value domain is allowed only where the ceiling IS the comparison, and
  then the panel prints the ceiling beside the figure.** Everywhere else the
  domain comes from the data drawn, niced by the scale library - which is what
  `linearAxis` already does. A fixed axis over adaptive data wastes the plot; an
  adaptive axis over a limit deletes the comparison. **Five things are not "the
  data drawn". Four of them widen the domain rather than replacing it; the fifth
  narrows it, and is allowed only on the condition written beside it.** Each is
  named with the shipped site that proves it, because an exception nobody can
  point at is an exception nobody can check.
  - **A limit the panel exists to measure distance from** - 16 GiB of runner
    memory, the model's reading limit - **joins the values the domain is built
    from**, so the limit is a line on the plot and a breach still draws past it.
    It is never the axis maximum, which would clip the breach at the line and
    hide the one reading the panel exists for. Shipped twice: `targetbar.ts`
    runs its track to the larger of the value and the target, and the context
    panel on `/console/machine/` builds its axis from the drawn extent rather
    than from the limit it is measured against.
  - **A share or a cumulative percentage runs 0 to 100**, because a curve that
    stops short of its own top reads as a curve that has not finished. Shipped in
    `TimeHistogram.svelte`. `FailurePanels.svelte` fixes the same axis for a
    second reason worth keeping: a rate over a known range is compared across
    stages and across days, and scaling it to the window's own maximum drew a 12
    percent rate and a 90 percent one at the same height.
  - **A ratio against a baseline is symmetric about that baseline and carries a
    minimum width**, or a two percent change fills the plot and reads as a rout.
    Shipped as `swapScale` in `series.ts`: no change is 100 percent and that
    point is the axis centre, and `minHalf` holds the half-width at 25 percentage
    points however small the real spread turns out to be.
  - **Every plot a panel means the reader to compare shares ONE domain.** A
    per-plot domain inside one panel deletes every comparison the panel was built
    for. Shipped in the five tail plots on `/console/machine/`, which take one
    `linearAxis` over the extent of all five.
  - **A distance far smaller than the population it sits in takes a window
    around the limit instead**, and every value outside that window is counted at
    the edge with its own figure printed rather than drawn. This is the one case
    that narrows the domain, so it carries a condition: **the breach side has to
    stay inside the window**, or it is the clipped breach the first case already
    refuses. Shipped once, on the holdout panel of `/console/judgement/` - see
    [the holdout margin](#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score).

  **The cost this rule accepts, stated rather than hidden:** an adaptive axis
  re-nices when the reader moves the window, so the same panel on two days is not
  comparable by eye. `.nice()` bounds that to whole tick steps and the readout
  strip carries the figure - a reader who wants the number reads it, a reader who
  wants the shape gets a full plot. Audited 2026-09-17 across
  `frontend/src/lib/charts/` and its callers: 24 domains, 21 adapting and 3 fixed
  with cause. The 1 GB Pages cap is not on this list: it is arithmetic in
  `glance.ts` and never a scale.
- **A stacked series has a fixed order, stated once.** Read at the bottom, write
  at the top, everywhere. Unclaimed and residual always last. A stack whose order
  moves between panels cannot be compared between panels, and a reader cannot
  learn it.
- **No piecewise or non-uniform value axis.** Where a spread genuinely defeats a
  linear domain, use a log scale and label it as one. Equal pixel steps standing
  for unequal value steps is a chart that misreports by construction; a log axis
  misreports nothing, it just has to say so. **What the reader loses by not
  having a 0/10/50/100 axis on the shard board:** at a 6x spread across machines
  the low bars compress, and the detail at the low end compresses with them.
  That compression is the true picture of a 6x spread and is the thing worth
  seeing. Measured 2026-09-17: on a linear domain of 0 to 75 tokens a second, a
  12 tok/s bar still draws at 16 percent of the track, which is readable - so
  the refusal costs nothing the panel needed.
- **Two series share one axis when the larger is under 20x the smaller; past that
  the smaller takes its own row on a shared x.** Measure before choosing. At 20:1
  the smaller draws under 5 percent of the plot and reads as zero. The threshold
  is a measurement rather than a taste, and the panel records the ratio it
  measured beside itself.
- **A panel may carry a shape switch or a grain switch where ONE builder call
  returns every shape it offers.** Never two calls, never a second fetch. That is
  what preserves the reason behind the no-re-shaping rule - two derivations that
  can disagree - while allowing a cumulative line and a shard-or-item grain.
- **A switch control sits top right of its own panel, and it is radio inputs.**
  Two named states a reader can see both of beats one state and a verb. Top right
  because the control belongs to the panel rather than to the page.
- **A tooltip is never the only carrier of a fact.** Every panel carrying one also
  carries the readout strip or a printed list. The dominant reading device has no
  hover.
- **A segment under 1 px at `console.chart_width` is not drawn as a segment.**
  Where a split's smallest band falls below that, the split becomes a printed
  figure and the bar draws whole. Measured 2026-09-17 over 23 shard-rows of
  `state/span-rollup/2026-09.csv`: the four sub-steps of a shard's clock together
  draw 0.026 px of a 760 px track and the residual draws 0.039 px, and a browser
  paints neither. **A band at 0.026 px is a legend entry with no mark**, which
  teaches a reader the category is zero when it is only unmeasurable at this
  scale.
- **A legend key for a series with no committed rows is deleted, not drawn
  empty.** A key for an absent series is a claim the data does not support.
- **A figure with a span is drawn as a range, never written as two sentences.**
  Value, low, high, one track. Figures that each have a span, each written as
  prose, are sentences no two of which can be compared.
- **A panel whose title asks a trend question draws a time axis.** A ranked list
  answers "which is biggest", never "what is changing". The title and the shape
  have to agree, or one of them is wrong.
- **Bar thickness comes from one place and a bar is never thickened to fill
  vertical room.** Room left over goes back to the panel. A thick bar reads as
  importance; thickness is not a variable here, so it must not vary.
- **A panel serves _is it working_ or _what is broken_, and names which. A verdict
  panel sits above the panels it verdicts.** A verdict takes the central value or
  the count and covers every subsystem. A break takes the extreme and the
  individual that owns it, and covers every candidate in one subsystem. A panel
  whose title asks one question and whose shape answers the other is the
  commonest defect on this console: of the eight panels that failed review on
  2026-09-17, five failed on this rule and only three on their drawing. **What a
  scattered verdict costs the operator:** he reads ten Hardware panels and only
  then reaches the panel that tells him whether the instruments agree.

Which surface answers which of the two questions is
[../../architecture/publishing/console.md](../../architecture/publishing/console.md);
this page rules how the drawing may read.

## Ranked by magnitude, in one shape

The operator asks the same question of most of this console: which one is worst.
A date sort cannot answer it - the source that cost the digest the most articles
sits wherever it happens to fall, and the feed one run away from being rested
sorts below a feed that has failed harmlessly for a month.

`RankedList`, `TargetBar` and `Sparkline` in
[../../../frontend/src/lib/components/](../../../frontend/src/lib/components/) are the
shape that answers it. Their arithmetic is in
[../../../frontend/src/lib/charts/rank.ts](../../../frontend/src/lib/charts/rank.ts),
`targetbar.ts` and `sparkline.ts`, not in the markup, so the number a list prints
and the bar it draws come from one place.

- **Ranked by magnitude, never by date.** A date sort is a log. It is the right
 shape for exactly one thing on this console - the item list behind a selected
 cause - and the wrong shape for every ranking above it.
- **The list prints its own divisor**, as a sentence: `A full bar is 38 cuts.` A
 bar scaled to a hidden maximum can be read for order and cannot be read for
 size, and nothing on the screen says which of the two the reader has.
- **Capped, with the tail in a sentence.** The sum is printed only where adding
 the hidden magnitudes means something: counts add, distances do not, and a list
 of distances says how many rows are missing and nothing else.
- **The two empty states say different things.** `Nothing has recorded an article
 length yet.` means the ledger cannot answer. `No article was cut short in these
 7 days.` means it answered no. Reading the first as the second is the same
 mistake as reading a null as a zero.
- **No row is tinted.** The order is the ranking. A word beside the name carries
 a status where a row has one, because colour is one signal and never the only
 one.
- **A threshold is a marker on the track, never a subtraction the reader
 performs.** `12 failures` means nothing until the count that rests a feed is on
 the same track. `TargetBar` draws the track at the threshold's own scale, the
 fill at the value, and a rule at the threshold. It takes the confidence ramp
 only where the threshold is a health fact - quarantine is, and a policy limit
 somebody chose is not, so tinting one would invent a verdict nobody agreed to.

The bars and the trend lines are markup, not charts. Seventy target bars in a
feed table would be seventy chart instances, and markup is also what still draws
with JavaScript off. `sparkline.ts` and `targetbar.ts` export the shape both
drawings read, so the two can never disagree about where a marker sits or what
counts as near.

A trend line takes one colour and never the trend ramp. A rising failure count
and a rising published count are the same shape, and green on the first would be
a verdict the page never measured.

**A generic `Table` component is refused, and these three are what replaced it.**
The console's problem was never table markup - it was that a table is the wrong
shape for "which one is worst", and a generic table makes the wrong shape cheaper
to produce. What is shared instead is a shape with an opinion: one order, one
divisor, one tail sentence, two empty states.

## A date axis is thinned by measurement, and a dropped date keeps its mark

One helper: `dayTicks` in
[../../../frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts).
Every hand-written date axis on the console calls it.

**A count cannot hold at two widths.** `chart.tick_density` picks the columns
that carry a tick mark, and then the labels are measured against the room the
plot actually has and dropped in whole steps until no two touch. So the knob is a
**ceiling and never a target**: it can take a label away and it can no longer
force one on. Measured 2026-08-31 on the built console at 390px, before this
rule, four axes drew their dates 13.6, 7.4, 26.1 and 1.9px on top of each other.

The width comes from the string rather than from the element, because the axis is
decided on the server where there is no text engine to ask. `LABEL_ADVANCE_EM`
is 0.58, ten percent over the widest character measured at `font-size="10"` in
Chromium on 2026-08-31 - `20 Aug 2026` is 55.83px over 11 characters. It is
deliberately over: an estimate under the truth lets two labels touch, and an
estimate over it only drops one label the axis could have carried.

**A dropped label keeps its tick mark.** A reader counting columns needs the grid
even where the date is gone, so the marks come from the ceiling and only the
dates thin.

**The end labels anchor inwards.** The first and last tick sit ON the plot edges,
so a centred label there hangs half its width outside the frame and an `svg` cuts
what hangs. Measured 2026-08-31 at 1440, one axis drew `10,000` 3.2px past its
own `svg` and read `10,00`. `tickAnchor` is the rule and it binds a value axis as
well as a date one.

Two console axes are drawn by the engine, and the engine owns where its labels go
- `hideOverlap` is its own measured rule. What they take from here is the date
grammar: `2026-08-25` is how the ledger spells a day and it is not how a page says
one.

The oracle is geometric and reads the page rather than the rule. At 1440, 768 and
390 it collects the box of every element carrying `data-day-axis` and asserts
that no two on one axis overlap and that none is drawn outside the `svg` that
would clip it -
[../../../frontend/tests/console-axis.spec.ts](../../../frontend/tests/console-axis.spec.ts).

## A chart with a shared column prints every series together, in a fixed strip

One contract, one implementation:
[../../../frontend/src/lib/components/ChartReadout.svelte](../../../frontend/src/lib/components/ChartReadout.svelte).
It binds every chart on the console whose marks sit on a shared column - four
series or one - and the rules are not negotiable per chart:

- **A fixed strip below the plot, never a floating box over it.** A floating
 tooltip covers the mark it explains, and one that dodges the cursor moves the
 thing being read. Measured 2026-08-30: a floating box occupied 40 to 55
 percent of the chart it explained.
- **Every series at the hovered column, at once.** Comparing four series must
 not cost four hovers. The strip is the legend as well, so the four numbers a
 reader compares are printed once rather than twice.
- **Capped at `chart.readout_max_share`** - 0.33 today. A share of the plot and
 not a pixel count, so the cap holds at every window width.
- **A vertical guide down the hovered column**, across every series.
- **Reachable by keyboard.** Left and Right step, Home and End jump, Escape
 returns to rest. **A tooltip is never the only place a value appears**: a
 tooltip needs a hover, and a hover is not a thing a thumb can do.
- **It opens on a resting column and is never blank.** The prerendered document
 carries that column's numbers in words, so a reader with no script still gets
 one column read out to him, and the panel never changes size as it fills.

An engine-drawn chart takes the same strip through
[../../../frontend/src/lib/charts/Chart.svelte](../../../frontend/src/lib/charts/Chart.svelte). The action goes on
the wrapping element and never on the SVG, because the engine swaps that SVG out
on hydration; the column centres come from `bandShares`, which recomputes them
from the measured width because the engine keeps its grid insets in pixels.

## A chart with no column to hover says so, and no chart draws a key twice

The strip **is** the legend. It prints each series in the colour that series is
drawn in, at the column the reader is on, so a standing key beside it would draw
the same pair a second time - and one fact drawn twice is how two of them drift.
No chart on the console draws a key: the engine's `legend` component is not even
registered in
[../../../frontend/src/lib/charts/core.ts](../../../frontend/src/lib/charts/core.ts).

A chart with no shared column gets no strip - a ranked list, one target bar, a
flow, two shares of one total. A strip there would print the row the cursor is
already on. **That is a decision, so it is written down where the chart is**:
such a chart carries `data-readout-none` with the reason in words, and a chart
with a column carries `data-readout-columns` with the count.

The pair exists because of what the absence looks like otherwise. A chart
somebody decided needs no hover and a chart where the readout was forgotten are
the same chart on screen.
[../../../frontend/tests/console-readout.spec.ts](../../../frontend/tests/console-readout.spec.ts)
enumerates every chart on the three console routes, fails on one that declares
neither, fails on a declared column with no strip, and fails on a swatch drawn
inside a chart that has one. It also holds the reason to five words, because
`none` passes an attribute check and tells a reader nothing.

## The holdout margin is drawn at the scale of the margin, not of the score

`The pairs a person marked apart` on `/console/judgement/` answers one question:
would tonight's merge line fold together two articles a labeller read as two
different stories? **The comparison it draws, written as a sentence: how far the
closest marked-apart pair sits from the line, against how far the line may fall
in one day.** That is a question about a distance, and the distance is **0.0007**
as of 2026-09-19 while the scores it sits between run from 0.73 to 0.99. A panel
that draws the population cannot draw the distance.

**So the axis is the line and one day's legal fall, never the band.** It runs
from two days' fall below the line to one day's fall above it - one fall cap
either side of `floor_min`, both off `config/idhazh.json`, so the window is the
same width every day and two days of this panel compare. The cap is not a score
in the config: it is `max_down_bins` slots of `bin_width`, and the contract
derives the score from them, so the panel multiplies the same two numbers.
Measured on the built page at 1440: the margin drew at **5.8 px of a 1033 px
plot** on the 0.88 to 1.00 band, and **24 px** on this one. At 5.8 px a dot 13 px
across sits on top of the rule it is measured against, so a reader cannot see
which side of the line the closest call is on - which is the whole of what the
panel is for. The test gates on the 14 px a dot needs, not on the 24, because
the reading moves whenever the fall cap does.

**It reaches two days down because the sentence counts two days.** At the
committed cap of 0.010 one day's legal fall already moves the count on the wrong
side from 1 to all 4, and the day after adds none. The axis still draws both,
because the headline names the day after and an axis stopping at one day would
print a count for a line it had not drawn.

**The zone goes down and only down.** The clamp caps both directions, but only a
fall folds a pair the line refuses today - a rise folds fewer. A corridor drawn
either side of the line would tint scores tomorrow cannot reach. The tint says:
every mark in here is a pair tomorrow could fold.

**The rule stays neutral and the panel takes the tone.** A line is a setting, so
drawing it red would report a fault every day of its life. The panel is what
changes hue - `bad` where a mark is already on the wrong side, `warn` where one
day's fall would put one there - because the fault is the reading, not the
setting.

**Both costs of the line are drawn, not one.** The pairs marked as two stories
are dots; the pairs marked as one story are a range strip on the same axis, the
shape `What the judge said about the line` already ships two of. 117 of the 196
one-story marks score below the line, and each of those is a story the reader
sees twice. Only their scores reach the document - 1.7 KB against 88 KB
for the same rows carrying their addresses and headlines, which the strip does
not draw. **They are carried at six decimal places and that is load-bearing**:
the count is a comparison against the line, two of the 196 sit between 0.93995
and 0.94, and at four places they round onto the line and the panel prints 115.

**This panel is not a time series, and the picture that has the dates ships on
the chart above it.** Four marks spanning 0.0064 on a 0.12-tall axis is 10 px of
a 190 px plot, and four rules inside 10 px is one grey smear. `Where the merge
line sits` already has days on one axis and score on the other, so the same marks
are a tinted strip across that plot. Two drawings, two halves of one question -
this one has the distance and no date, that one has the date and no distance.

**What the reader loses.** A mark far below the line is off this scale, so it is
counted at the edge with its score printed in words rather than drawn. That is
the safe end of the axis and never the breach - a mark above the line always
falls inside the window - but it means a reader cannot see the spread of the
misses from the picture. The shut table under the panel carries every marked
pair at zero attention cost, which is where that spread is.

**This is the fifth case in the thirteen rules above, and the only one that
narrows a domain.** It is allowed here because the breach side stays inside the
window; a fixed axis that clipped the breach is what the first case refuses.

## Design rationale

**The thirteen rules landed in one commit, before any panel was redrawn.** The
rejected alternative was to let each panel row make its own call as it came to
it. Nine rows re-arguing the axis, the stacking order and the switch produce nine
answers, and a reader who moves between two panels cannot learn nine - which is
the defect the rules exist to remove, arriving by the door that was meant to
avoid the argument. The cost of settling first is that every panel row then waits
on one doc row; it was paid once. Landing the rules in the same commit as a panel
that obeys them was refused for a different reason: doctrine plus a panel cannot
be reverted without reverting the panel, and the doctrine is the half more likely
to need editing.

## See also

- [../console-design.md](../console-design.md) - what a figure may say, and in what words.
- [the-mark-shapes-a-panel-may-reach-for.md](the-mark-shapes-a-panel-may-reach-for.md) - the named shapes these rules bind.
- [how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) - where the one-domain and no-pooling rules bite hardest.
- [../design-system.md](../design-system.md) - the tokens, ramps and sufficiency gate this page draws on.
- [../../architecture/publishing/console.md](../../architecture/publishing/console.md) - which surface answers which question.
- [../../architecture/publishing/console-charts.md](../../architecture/publishing/console-charts.md) - the chart frame these rules are implemented in.
- [../config/appearance.md](../config/appearance.md) - `chart.*` and `console.*`, the knobs these rules read.
