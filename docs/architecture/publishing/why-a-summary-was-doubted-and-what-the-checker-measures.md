# Why a summary was doubted, and what the checker measures

**Last Updated**: 2026-09-23

`/console/model/` answers what the model wrote, how long it took, and what it got
wrong. Four panels are on this page: the five reasons a summary was doubted, the
faithfulness score, the lead coverage, and the table of instruments nothing acts
on. The eleven measure cards and the two distributions above them are drawn to
the rules in
[../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md).

Which panel sits on which route is [console.md](console.md).

## Why a summary was doubted, and the one ledger that can answer it

The route draws the five reasons a summary failed to reach the top band, one
column a day, over the window the page shares. The measure cards above it say how
often the checker stopped; this says which check failed.

**It reads the committed day payloads, not `state/scores/`.** `band_reason` is
decided by `verdict` and written onto the published item by `assemble.build_day`.
The score ledger's 35 columns carry the inputs a reason is decided from - `hhem`,
`coverage`, `unsupported_numbers`, `hedge_dropped` - and the band, and no reason
column at all. So the route walks `DIGEST_ROOT` the way `publishedItems` already
does for the Pipelines route, and what ships is one count per reason per day
rather than the payloads. Re-deriving the reason from the ledger's inputs was
refused: it puts a second copy of `verdict` in a second language, and the day the
two disagree the console is wrong about the item a reader was shown
([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**The five are drawn apart and never added into one doubt count.** A single
number says how often the checker stopped and never says which fault to go and
fix. Each item carries at most one reason, so the five add up with nothing
counted twice - which is what makes the stack legal and what the oracle checks.

**Stacked, with a switch to lines.** The same array draws both with only `type`
and `stack` moving, which is the condition
[../../concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md](../../concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md)
sets for that control. Picking `Lines` reaches the live chart, not only the
prerendered one. A chart carries an explicit lifetime - it hydrates, draws when a
reader comes within a screen of it, takes a changed option through `update`, and
is destroyed once - and a small `$effect` in
[../../../frontend/src/lib/charts/Chart.svelte](../../../frontend/src/lib/charts/Chart.svelte)
hands the live chart each new option, so a control that moves the shape or the
window is followed without a rebuild.

**A reason with no items draws nothing, so the panel names it in a sentence.**
`not_scored` has never fired: it needs a missing faithfulness score, and the
scorer has run on every production item. A series that is zero everywhere is
dropped by `stacked`, so without the sentence a reader cannot tell a fault that
never happened from one nobody looked for.

**The column total is the day's reason count, never its doubtful count**, and the
difference is printed. 369 doubtful summaries carry no reason, all of them on the
three days published before the field existed. A panel that folded them into a
band would draw a fault the checker never named; one that dropped them silently
would make three days look clean.

## Every instrument the checker writes, and the panel that owes it a number

Three more panels: the faithfulness score, the lead coverage, and a table of the
six instruments nothing acts on. What matters more than any of the three is the
map they ship with.

**The artefact is `DRAWN_BY`, not the charts.**
[../../../frontend/src/lib/console/eval-instruments.ts](../../../frontend/src/lib/console/eval-instruments.ts)
assigns every measured column of `state/scores/` to exactly one panel, and
`NOT_A_MEASUREMENT` says of every remaining column why it is not one - fifteen
identity and provenance columns, each with a sentence. Between them the two must
name every property of
`EvalRow`,
once, and name nothing else.
[../../../frontend/tests/console-model-instruments.spec.ts](../../../frontend/tests/console-model-instruments.spec.ts)
compares the two sets in the ninety-second gate. So a column added to `EvalRow`
next month fails a test rather than going undrawn - which is the defect the map
exists for: `hhem` and `coverage` were scored on every summary from the first
published day and read by nothing on the site for two weeks.

**Two panels was the scope and six more columns was the survey.** Counted
2026-09-06, ten of the ledger's twenty measured columns had no reader anywhere in
`frontend/src`. Faithfulness and lead coverage got their own panels; the other
eight went to the third. Drawing two and calling the goal met would have left the
map failing its own test on the day it was written.

**`hhem_full` and `hhem_delta` are a sentence, not a second chart.** The checker
scores each summary twice, once against the text the machine was given and once
against the whole article, so a summary that only looks faithful because the
article was cut cannot pass. Measured 2026-09-06 over 6,966 rows the two readings
differ on **7 of them**, because production hands the same string to both - the
finding recorded in [../../concepts/evaluation.md](../../concepts/evaluation.md).
A chart of a number that is flat on 99.9 percent of rows teaches an operator to
stop looking; a sentence saying how often it parts, and by how much, is the same
fact at the size it is worth.

**Two bars, and they are the pipeline's own.** The faithfulness plot draws a rule
at each of the two scores a published story is banded on - `band_high_min` and
`band_medium_min` in [../../../config/idhazh.json](../../../config/idhazh.json),
0.80 and 0.50 as committed - and nothing else on either panel sets a bar. No
reading is tinted, no day is coloured, and the spec still fails the build if a
tinted element appears inside either score panel.

**A rule under the axis floor is dropped, not handed over.** The floor rises to
fill the panel with the range the days hold, and on the committed record it sits
at 65 percent - above the doubt score. The engine clips a rule outside the axis,
so passing it anyway draws nothing and leaves the panel's own sentence naming a
line a reader cannot find. So the plot ships the rules its own scale reaches,
and the panel says "a line crosses the plot at each one the days on it reach"
rather than promising two. The doubt rule comes back on the day the floor drops
to meet a figure beneath it, which is the day an operator opened the panel for.

The distinction is between a threshold and a verdict. A rule across the scale
says what a score has to clear before a reader is told the story matches its
source; a coloured figure says this one is bad, which is a judgement no fifteen
committed days can support. Until 2026-09-25 this page refused both, on the
ground that a threshold taken off this window would be a guess wearing a
measurement's clothes. That reasoning was sound and answered a different
question: these two were never taken off this window. They are already in force -
every published item carries the band they decide - so a panel that hid them was
an operator panel disagreeing with the page a reader sees. Susan and Andre,
2026-09-25. What it cost: an operator can no longer read the plot as a bare
measurement, because a line on it is policy. What it bought: the plot now
answers the question the operator actually has, which is whether today's
summaries clear the bar the site is publishing against.

The one threshold this page did draw until 2026-09-24 - the share of an article's
opening a summary had to keep - stays retired, because plenty of good articles
open slowly.

**Two lines on faithfulness.** Measured 2026-09-06 over the
fifteen committed days, the middle summary's faithfulness sat between 88 and 95
percent while the lower quarter swung from 73 to 94 - so the level and the tail
are two different facts and both are drawn. Lead coverage does the opposite: the
middle summary sat between 57 and 64 percent every single day, so a line of it
beside a moving one would read as the important one. What moves there is the
share of a day that fell under the floor, and that is what is drawn; the level is
in the readout strip and the headline.

**Lines, and no shape switch on either.** One percentile added to another is not
a quantity, and neither is one day's share added to the next day's. The condition
for carrying that control is that both shapes read the same array honestly. Bars
here would not.

**A day is that day's middle summary, and the recorded table says so in full.** A
median over the whole window needs every summary's reading, and carrying 6,966 of
them into the page to print four figures is not a trade worth making. The table
prints the quietest day, the middle day and the loudest day, each by its own
middle summary. It used to name that in four words - "that day's middle summary" -
which is only a definition to somebody who already knew it. It now spells the
median out: half of that day's summaries scored higher, half lower. Susan,
2026-09-25.

**The two densities are drawn per thousand words, not per word.** Per word they
are 0.011 and 0.004 - two numbers a reader cannot tell apart, neither of which
reads as a quantity of anything. Per thousand words they are 11.0 and 4.0
markers, which is a count of phrases in about four pages.

**The faithfulness plot's axis is fitted to the days it drew, and bounded both
ways.** The floor is the lowest figure on the plot rounded down to the step below
it, held between the doubt threshold and
`console.faithfulness_axis_floor_max`; the ceiling is a hundred, because a
percentage has a top the data does not get to move.

Until 2026-09-25 the axis ran from zero, and the page recorded that as a
sufficiency check failed on purpose: the fifteen committed days sat in the top
fifth of the plot and four fifths of it was empty, which is
[../../concepts/design-system.md](../../concepts/design-system.md)'s first check,
does it use the space it is on, answered no. The reason given was real - cropping
to the data turns a four-point drift into a cliff, and this panel exists because
a band could not show a four-point move. The fix keeps that reason and drops the
empty four fifths: the floor may not rise above
`faithfulness_axis_floor_max`, so a quarter of the scale is on screen whatever
the data does, and a four-point move is drawn as a sixth of the panel rather than
as a collapse. Susan, 2026-09-25.

Two bounds and no third. The floor's lower limit is not a knob - it is
`evaluation.band_medium_min`, because below that score every summary carries the
same published band and there is nothing left to zoom into. And one rule outranks
all of them: **the floor never hides a mark.** A day whose lower quarter fell
through the doubt line is the day an operator opened the panel for, so the floor
drops to meet it.

What these panels weigh, and every live page ceiling, is
[../../reference/site-weight.md](../../reference/site-weight.md#the-page-guardrails-and-what-each-route-weighs-2026-09-10);
what to do when one fires is
[../../how-to/run-the-gates.md](../../how-to/run-the-gates.md).

## How long the summaries came out

The compression chart draws three marks a run - the shortest summary, the middle
one and the longest - against the band its own articles were asked for. The
drawing rules are in
[../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md);
three refusals are specific to this plot.

- **No separate chart for where the cut falls.** It is a line. A chart that says
 what a line says has not earned its place.
- **No density-binned scatter, and no paler marks.** Both keep the two-axis
 reading the three-mark split removes, and the second only makes a paler blob.
- **The per-point band lines are collapsed, not faded.** The wash is a node
 count, not an alpha value: one fact drawn 1,166 times is still drawn 1,166
 times at any opacity, and the fact has one value per configured band.

**`uplot` was tried on this plot and removed.** It drew a second, smaller chart
beneath a complete SVG, and the pan and zoom it was bought for live in the window
control rather than in the plot (Guardrail #8).

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md) - how the measure cards, the distributions and the compression chart are allowed to draw.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what the checker measures and what a verdict means.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control these panels answer to.
- [../../reference/site-weight.md](../../reference/site-weight.md) - what this route weighs.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
