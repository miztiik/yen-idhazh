# How chart drawing is reported, and the rule it is judged against

**Last Updated**: 2026-09-23

`Visuals drawn for articles` is a Pipelines section in three parts: a flow of
where items go, the two figures the retirement rule names, and a daily table
behind a disclosure. Two cards beside it count what was published.

It is the only console section carrying a written decision rule in its own prose,
which is why it gets a page: over a stated span chart drawing is retired if the
median day spends more than a set number of minutes per published visual, or puts
a visual on fewer than a set share of the items it published.

The rest of Pipelines is
[what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md); how any
figure here is allowed to read is
[../../concepts/console-design.md](../../concepts/console-design.md).

## The chart drawing is a flow, and every drop leaves it as a named branch

The section opens with one diagram of where items go between the work stage
reaching one and a visual reaching a page. It is drawn left to right, the
direction the page reads and the order the pipeline runs its stages in, and it
totals the whole open window rather than one day - a single day's four numbers
are already legible in the table under it, and "where do items go" is a question
about the window.

**A funnel cannot answer the question this section asks.** A funnel draws a
monotonic sequence as a taper, so it says how much is left at each step and
nothing about where the rest went. The three drops here have three different
causes and three different fixes: an item can be answered without the model being
asked at all, the model can be asked and draw nothing, and a drafted chart can
fail the checks that run after it. A taper shows all three as one slope. Every
loss leaves the flow as its own branch, labelled `Answered without a visual`,
`The model drew nothing` and `Did not survive the checks`, and the branch is as
wide as the number of items in it.

**The widths conserve, and that is asserted rather than assumed.** What leaves a
stage is what arrived at it: the branch that carries on plus the branch that was
lost. `frontend/tests/charts.spec.ts` recomputes the four stage totals from the
fixture and checks every node against them, so a layout that drew a plausible
shape from the wrong numbers fails. A flow whose widths do not conserve is
drawing a picture, not the data.

**A branch of zero is not drawn.** A stage that lost nothing has no loss to show,
and a zero-width branch with a label beside it reads as a loss too small to see
rather than as no loss at all.

**A window that gains items prints a sentence instead of a diagram.** The four
counts are not guaranteed to fall: a chart published inside the window can have
been drafted before the window opened, and the committed ledger holds exactly
that - 2026-08-25 recorded 23 drafted and 27 published. Over a whole window the
totals came back monotonic (2,121 reached, 1,425 asked, 144 drafted, 124
published on 2026-08-30), but a narrower window need not, and the drop would be
negative. The diagram steps aside and says which stage gained, because a negative
branch cannot be drawn and a clamped one would be a lie about the count. The
table below it still holds the numbers. Zero reached is the other empty state and
keeps its own sentence, so the two nothings are never one blank panel.

**Colour is the categorical ramp, and a loss keeps the hue of the stage it
left.** Every fill comes from `PALETTE` through the sentinel bridge, so both
themes resolve with no JavaScript at all; a loss branch is the same hue at 0.28
opacity against the flow's 0.55. A second hue would say a loss is a different
kind of thing, and it is the same items going a different way. Both opacities are
low because a label to the right of a node sits over the links leaving it, which
is unavoidable in a flow this shape - the label has to stay readable across them.

**Every label sits outside its node, on two lines, carrying the count and the
share of everything reached.** The narrowest node on the committed ledger is
under three pixels tall, so a label inside it would be unreadable. Three
measurements set the geometry, all taken in the browser on 2026-08-30:

- **Two lines, not one.** `Answered without a chart 696 (33%)` ran 280px into a
 246px column pitch and printed over the next stage's label. Split, the widest
 line is the name alone.
- **The right margin is 170 pixels, not a share of the width.** A label does not
 shrink with the frame, so a percentage leaves too little on a narrow screen - a
 reserved 30 percent still clipped `Did not survive the checks`, which measures
 151px at 12px type.
- **The node gap is 34 pixels, against the engine's default of 14.** `Published`
 and `Did not survive the checks` are 13.8px and 2.2px tall over the committed
 ledger, so at 14px their two-line labels shared nine pixels of one line. A
 two-line label is 31px and the gap has to carry it.

`depth` is set on every node rather than inferred, because an inferred layout
justifies dead ends to the far edge - it would draw the first stage's loss beside
the last stage's.

**The flow layout costs 5,672 gzipped bytes of lazy chart chunk**, measured
2026-08-30 by registering `SankeyChart` in place of `FunnelChart` - the whole of
the difference, with both cases byte-identical on every build. That leaves
**2,439 bytes under the 200,000-byte line** the chart vocabulary is held to,
which is 1.2 percent: **the next chart type registered crosses it**, and the
answer then is to measure what the current set costs before adding to it.
**Re-measure the registration list whenever it is edited** - it is a file
somebody has to edit, and a recorded figure taken before six chart types were
added once sat 25 percent under the truth.

## The rule is judged first, and the daily rows come second

A paragraph with the rule but none of the three numbers is rejected. Seven
columns of daily counts cannot ask the operator to take a fourteen-day median of
a ratio, twice, against two limits that are nowhere on the screen.

The section leads with the two figures the rule names. Each is a `TargetBar` -
the track at the threshold's own scale, the fill at the window median, a rule
drawn at the threshold - with a `Sparkline` under it, because `4.2 and falling`
and `4.2 and rising` are different pictures and a single number is neither. One
sentence above them states both figures and which side of its threshold each fell
on.

**The sentence and the two bars are one computation.** `chartRule` in
[frontend/src/lib/charts/glance.ts](../../../frontend/src/lib/charts/glance.ts)
returns the medians, both bars' geometry, both trends and the sentence together,
and the browser suite asserts the printed sentence is byte-identical to the one
the module builds. A verdict written in the template could say `inside` while the
bar beside it drew a fill past its marker, and nothing on the page would look
wrong.

**All three numbers are config.** `console.chart_rule_days`,
`console.chart_minutes_target` and `console.chart_coverage_pct` live in
`config/appearance.json`, bounded by `ConsoleConfig`. Hard-coded TypeScript
constants are rejected because they would make the one section that states a
threshold the one section an operator could not move a threshold on (Guardrail
#6). The contract also refuses a preset list whose widest span cannot reach
`chart_rule_days`: a rule no preset can show would print the widen-the-window
notice at every setting of the control, which reads as a broken surface rather
than as a narrow window.

**Coverage divides by what the day published, and a day that published nothing
has no share at all.** The denominator is the item count on the day's own
`digest.json`, read in the same pass that counts its charts, so no new telemetry
column was published to answer this. A quiet day returns null rather than zero
percent: zero would say chart drawing ran and reached nobody, and nineteen quiet
days would drag the median of a healthy fortnight onto the floor. This is the
null-is-not-zero rule the timing medians already follow
([../../concepts/console-design.md](../../concepts/console-design.md)).

**Neither bar takes the health ramp.** These are limits somebody chose, not a
verdict on the machine, so `TargetBar` draws them in its `policy` tone. The
marker carries the fact. Tinting a policy threshold green would invent a health
judgement nobody agreed to, which is the same mistake as a chart borrowing the
band tokens.

**Below the rule's own span the section prints the notice and no number.** The
window control governs the medians, and under `chart_rule_days` the section says
`The rule reads 14 days. Widen the window to see it.` and draws no bar. It is the
same sentence and the same reason as the glance card next to it: a median of the
wrong span is the same figure with a different meaning, and nothing on the page
would say which one is being read. The section carries
`data-windowed="chart-drawing"` and states its span in words at every setting, so
the window oracle in `frontend/tests/console-window.spec.ts` holds it to the
control like every other windowed surface.

**No chart type is registered for this section**, so the lazy engine chunk does
not move for it at all. What every route weighs is
[../../reference/site-weight.md](../../reference/site-weight.md).

## Visuals published sits beside Articles published, and one is the denominator

**A strip that prints how many visuals were drawn without saying what they were
drawn for is rejected**: a reader could not tell a busy day from a
well-illustrated one - 185 visuals is most of a quiet fortnight and a rounding
error on one heavy day. The two cards read left to right as the fraction they
are, articles first, and each carries its own total for the window on screen.

**One bar a day over the control's own window, and the count above the bars is
that same window summed**, so a reader adding up the columns gets the number the
card printed. Bars rather than a line, because a count per day is a discrete
quantity and a line between two days claims a value for the hours in between that
nobody counted. A smoothed line over a fixed fourteen days under a control
reading thirty is the shape to refuse: two spans on one screen.

**The strip is markup rather than an engine drawing.** It is complete before any
script runs, and it follows the control with one drawing instead of a
server-drawn seed and a client redraw that can disagree about the span. A window
that published nothing prints the count and no strip at all, because thirty bars
of zero is an empty plot area and a card is still a card without one.

**One function draws both strips, and each is drawn against its own busiest
day.** `publishedSkyline` takes the measure as an argument, so the two cannot
drift in the one property that makes the pair readable: both are one bar a day,
over the same window, at the same pitch, with the same left edges.
[frontend/tests/console-published.spec.ts](../../../frontend/tests/console-published.spec.ts)
asserts the two strips report the same `data-published-days`, which is the whole
of "they are on one window". Each strip normalises to its own peak rather than to
the larger series: articles run two orders of magnitude above visuals on the
committed ledger, so a shared scale would draw every visual bar as a hairline and
the smaller card would stop saying which of its own days were heavy.

**One chart with both series is refused.** Two axes invite a comparison of slopes
that means nothing, and one axis flattens the smaller series to nothing.

The card is labelled `Visuals published`. It counts visuals in state `rendered`,
the section above it is `Visuals drawn for articles` and the table column is
`Visuals published`, so calling the card `Charts published` would name a drawn
thing with the wrong word. Its label is also a test selector, so the selector
must move with the reader-facing string.

## Both daily tables follow the window, and shut they are not cards

The Pipelines table and the Summaries table are the two `<details>` on the
console that hold a row per day. Both follow the control above them, because two
answers to one question on one page is exactly what a shared control was built to
remove.

Both take one name, byte-identical at the same preset: **Show these figures day
by day, over these N days.** `Show the daily figures` was refused because
"figures" names nothing on a page that is nothing but figures. The day count is
on the line that opens the table, so an operator knows what he is opening before
he opens it.

**Neither table is deleted, and the Pipelines one is the closer call.** Most of
what it holds is drawn above it - the flow covers reached, asked, drafted and
published, and two target bars with their sparklines cover the minutes and the
coverage. Only `Items published` is uncharted. It stays as the per-DAY reading of
a window-level picture: it is the only place a printed rate can be checked
against the two counts it was divided from, and the only way to attribute a
window aggregate to a day.

**The seven daily columns are behind a native `<details>`, not a button.** The
console is complete before any script runs and stays complete if none does, so a
button plus a conditional block would leave the rows permanently unreachable with
JavaScript off - the rows would be gone rather than on demand. A disclosure is
keyboard-reachable for free and says which state it is in without a second label.
`Reached`, `Asked the model`, `Visuals drafted` and raw `Minutes spent` sit in
the table rather than above it: the flow diagram already draws the first three as
branches, and the minutes on their own are the numerator of the ratio rather than
a decision. The table carries the `Items published` column that coverage divides
by, so the share and its denominator sit on one row.

**On Pipelines it ends `[data-windowed="chart-drawing"]` rather than hanging
below it.** It answers the section above it, and a table that has to be found is
a table nobody reads.

**Shut, a disclosure drops its border, its background, its shadow and its
padding.** Closed it is one line of link text, and a bordered, shadowed, rounded
card around it gives a footnote the visual weight of a section - which is what
makes it read as something hanging off the bottom of the page rather than as the
last line of the section above. Open it takes the frame back, because then it
holds a table. The rule is `.console-disclosure:not([open])` in
[../../../frontend/src/styles/app.css](../../../frontend/src/styles/app.css), and
[../../../frontend/tests/console-window.spec.ts](../../../frontend/tests/console-window.spec.ts)
reads the computed values either side - an eye cannot check a box-shadow.

The Summaries table declares `data-windowed="daily-figures"`, so the window
oracle holds it to the control like every other windowed surface. The Pipelines
one declares nothing of its own: it sits inside `chart-drawing`, which already
declares the span and prints it in words.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) - the rest of Pipelines.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control this section answers to.
- [visuals.md](visuals.md) - the drawing pipeline this section reports on.
- [what-drawing-costs-and-what-has-been-retired-for-it.md](what-drawing-costs-and-what-has-been-retired-for-it.md) - the retirement rule at full length.
- [../../reference/site-weight.md](../../reference/site-weight.md) - what every route weighs, and the chart vocabulary's own line.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
