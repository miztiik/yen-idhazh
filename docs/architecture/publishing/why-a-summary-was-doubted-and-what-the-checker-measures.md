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

**Nothing sets a bar.** No threshold line, no red, no band tint, no polarity -
and the spec fails the build if a tinted element appears inside either score
panel. The committed window is fifteen days and the summarizer is about to change
twice, so a threshold taken off it would be a guess wearing a measurement's
clothes. The one number that *is* a bar - the configured lead-coverage share - is
printed as a count of summaries under it and never drawn as a line to fail
against, because it caps a summary at "fairly sure" and has never on its own
marked one "not sure".

**Two lines on faithfulness, one on lead coverage.** Measured 2026-09-06 over the
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

**A day is that day's middle summary, and the recorded table says so.** A median
over the whole window needs every summary's reading, and carrying 6,966 of them
into the page to print four figures is not a trade worth making. The table prints
the quietest day, the middle day and the loudest day, each by its own middle
summary, and names that in the panel rather than leaving a reader to assume a
window median.

**The two densities are drawn per thousand words, not per word.** Per word they
are 0.011 and 0.004 - two numbers a reader cannot tell apart, neither of which
reads as a quantity of anything. Per thousand words they are 11.0 and 4.0
markers, which is a count of phrases in about four pages.

**The faithfulness plot fails a sufficiency check on purpose.** Its axis runs
from zero to a hundred, so the fifteen committed days sit in the top fifth of the
plot and four fifths of it is empty - which is
[../../concepts/design-system.md](../../concepts/design-system.md)'s first check,
does it use the space it is on, answered no. Cropping the axis to the data would
fill the plot and would also turn a four-point drift into a cliff. This panel
exists because a band could not show a four-point move; a plot that shows a
four-point move as a collapse is the same failure with the sign flipped. The
empty four fifths is what tells an operator the movement is small, and that is
worth more than the space. Recorded here rather than waved through, per
`CLAUDE.md` section 9.

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
