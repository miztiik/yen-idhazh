# Console Charts

**Last Updated**: 2026-09-10

What a chart on the operator console has to conform to: the one coordinate
frame every chart draws through, the pointer readout every chart with a shared
column carries, how a missing number is marked rather than drawn as a zero, and
where the model-change rule may appear.

**This page is for somebody adding or changing a console chart.** It says
nothing about which panel is on which route - that is
[console.md](console.md) - and nothing about how a figure may be worded, ranked
or tinted, which is
[../../concepts/console-design.md](../../concepts/console-design.md). The
distinction is the one those pages already draw: this is the machinery, that is
the policy.

The modules it governs are
[frame.ts](../../../frontend/src/lib/charts/frame.ts), which owns the width, the
margin box and the two domain rules;
[Chart.svelte](../../../frontend/src/lib/charts/Chart.svelte), which owns a live
chart's lifetime; and
[core.ts](../../../frontend/src/lib/charts/core.ts), the registration list that
decides what the lazy engine chunk weighs.

## Every chart draws through one coordinate frame, in CSS pixels

**Every chart draws through one coordinate frame, in CSS pixels.**
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns the width, the margin box and the two domain rules - linear, rounded
outward to numbers a reader can place, and anchored at zero only where the
mark's *length* carries the value; and log, snapped to whole decades. A mark
that encodes by position takes the padded domain instead, because a zero no run
was ever measured at is plot spent on nothing. The rounding is a default rather
than a law: a chart whose domain is already decided by something else turns it
off, because rounding a fixed domain outward moves every mark on the chart to
buy a tick label that reads the same either way. The log rule has one user since
2026-08-30 - the stage-timing y axis, drawing whole decades and the eight steps
between them. It had two until the compression scatter was replaced by a per-day
count, and a count of articles is linear. Which rule a chart takes is decided by
the extent it draws, and the
threshold is stated under stage timings below. The tick values come from `d3`
either way, which
is the part hand-rolling gets wrong. Before the frame, each chart chose its own
`viewBox` and let the browser fit it to the column, and a `viewBox` is a scale
factor rather than a unit. Measured
2026-08-25 at a 1057px window: the same `font-size="10"` came out 4.5px in the
three-up failure panel and 16.6px in the chart under it, and a `stroke-width` of
1 came out at 0.45px and 1.66px. One module means a chart cannot invent a fifth
convention.

A prerendered chart has no element to measure, so the server draws at
`console.chart_width` and the client redraws once it has measured the real
width. The knob is what keeps the prerendered chart honest: without a width
given to it, a server-rendered SVG has to pick an arbitrary one, and picking an
arbitrary one is the defect.

The arithmetic comes from `d3-scale` and `d3-array`, which compute and draw
nothing. This is not a chart library returning ([../../concepts/design-system.md](../../concepts/design-system.md)):
they own no element, no canvas and no theme, and no reader route imports either
one. `npm run bundle-gate` holds that true: its encoder check refuses any of the
three assist symbols on the first-load path, whatever pulled them there. The
same script also holds each prerendered page's HTML under a ceiling, and a
route earns one when somebody has priced its growth: `/404` and `/evals/` move
only when the source does, `/archive/` grows by one day link a published day,
and `/console/` grows with the item-telemetry rows inside the page's window. A
day page and the home page weigh whatever the day published, so they are
measured and reported and never failed - a ceiling on either would cap the news
rather than catch a regression
([../../concepts/config.md](../../concepts/config.md)).

The item-health viewport has three parts, in this order:

- **Failure rate against volume**: one chart. Per-day columns of the day's items, split by where each one stopped - finished, then fetch, extract and summarize failures in the categorical ramp - so the height of a column IS the volume. Each stage's failure share is a line on a right-hand axis **fixed at 0 to 100%**: scaled to the window's own maximum, a single day in view normalised its bar to itself, so a 12% rate and a 90% one both filled the panel. **Every rate is printed in type with its denominator in the same sentence** - `16% failed, 672 of the 4,273 that reached it.` - because an SVG `<title>` does not fire on touch and does not survive the screenshot an operator pastes into an issue. **A stage under `console.min_attempts_for_rate` prints its counts and no rate at all**, and its line breaks over any day that thin, because a share of four items is not a measurement. An empty window says so rather than drawing a column of zeroes, because a column of zeroes reads as a run that went badly.
- **Summary length against the length asked for**: one column a day, stacked three ways - inside the target band, short of it, past it - with the `summarize.bands` ladder printed as numbers beside the chart and the worst misses named underneath in a ranked list. Hand-written SVG in the categorical chart ramp, a word beside every swatch, and the counts carried on the column as `data-band-inside`, `data-band-short` and `data-band-long` so an oracle can add them up. It follows the shared window and declares itself `data-windowed="band-distance"`. It replaced a scatter of article length against summary length: the scatter placed every article in the browser, which is what made the console document 40 percent of its weight, and it answered "what does the corpus look like" where the operator's question is "how many missed, and by how much".
- **Why items failed**: a ledger of causes, then the sources those failures cost the most articles, then the rows behind a selected one. **A cause is a stage and a code**, ranked by count through `RankedList` - a bar in the cell, a markup sparkline of that cause's daily count, and breadth as `sources hit: 3 of 47`. **Breadth is the column that earns its width**: one source changing its markup and the extractor being broken carry the same count and a very different number of sources, and until this landed the two read identically. **Which source is the second ranking, and it is the one column of the item table nothing above it answered.** A cause says what broke and a source says where, and an operator acts on both. It is a second `RankedList` and no new chart type: 122 sources against an eight-stop ramp is not a stacked bar, and the question - which is biggest - is a ranking, which this console already draws as a list with an opinion. **The magnitude is ARTICLES, one per source per day**, the rule `compressionView` reads the same ledger by, so the two surfaces cannot disagree about how many articles a day held; the rows under it are one per stage per run, so counting rows would leave every bar in proportion and every number too big. **The denominator rides in the value** - `42 of 42 articles` is a source that stopped working and `42 of 500` is a bad afternoon, and the count alone cannot tell them apart. **No tint and no verdict on a source row**: per-source yield is not measurable until the ledger is thirty days deep ([../sources/health.md](../sources/health.md)), so a colour would publish a threshold nobody agreed. Capped at `console.source_rows` with the tail in one sentence - measured 2026-09-01 over the committed projection, a thirty-day window holds 60 sources with a loss and 778 lost articles, so the tail names 50 sources and 398 articles. The rows below are the detail, and they sit behind a shut `<details>`: still newest-first, which is the one shape on this page a date sort is right for, still **capped at `console.failure_list_max` with a `Show 25 more` button**, and still stating their own scope - `Showing 25 of 214 failed items in this window.` A code chip, a selected cause and a selected source all filter them, and they narrow together rather than replacing one another; picking a cause or a source opens the disclosure, because a filter whose result is behind a shut disclosure is a control with no visible effect; a new window, a new chip, a new cause or a new source resets the cap, because each is a new question. **The `Item` column is gone and `item_id` rides on the row's `title`**: it is a content address, it was the widest cell in the table, and no operator acts on one - the page-level grep it cost is a terminal job. Uncapped the list measured 7824px against 800 rows and put the compression chart at document y=9105. The section sits last for the same reason, and the disclosure is why the two rankings stay readable: the rows are the only child that can outgrow the screen. They survive verbatim rather than being deleted - the address in one is where troubleshooting a single URL starts, and a documented workflow begins there. **There is no cause text and none is invented** - the published projection withholds `detail` ([telemetry-series.md](telemetry-series.md)), which can carry fetched article text, so the code is everything the browser is given. **The stage is a word and not a mark.** The design asked for a monochrome stage glyph beside it and it is refused here: the icon set is one generated module that reaches every route, because a lookup on a dynamic key cannot be tree-shaken. Fifteen glyphs cost the routes 1,404 to 1,900 gzipped bytes (measured 2026-08-29, [../../concepts/design-system.md](../../concepts/design-system.md)), which is 94 to 127 bytes a glyph a route against a 64-byte ratchet tolerance, so three stage marks would move `/`, `/404`, `/<date>/`, `/<date>/<topic>/`, `/archive/` and `/evals/` - six reader routes that cannot show this section at all. The same page calls an icon that needs a caption a label wearing a costume, and the stage name is already in the cell.

Measured 2026-08-24 on the committed ledger: the console document went from
11552px to 4878px.

**A stage's denominator is what the stage before it let through, never the
day.** An item that died at fetch never reached extract, so counting it in
extract's denominator understates every stage after the first. The projection
carries the funnel already: one row per planned item per run, holding the stage
that item ended at, so `series.ts` walks the pipeline order once per day and
each stage's `reached` is the one before it minus that one's failures. A row
that never left `plan` is in the day and in no stage's denominator. Measured
2026-08-30 over the 4,273 rows of the committed projection: 672 items died at
fetch, 437 at extract and 19 at summarize, so extract reads 10.2 percent against
the day's 4,273 and 12.1 percent against the 3,601 that actually reached it, and
summarize reads 0.4 against 0.6. The three panels divided by the day and were
wrong about two stages of three.

**Three panels became one chart because a rate on its own cannot be acted on.**
A stage that failed both of the two items it was given drew the same full bar as
an outage, and the number that tells them apart - the denominator - was the one
number the panel did not print. Volume and rate are one question, so they are
one picture: the column says how much work there was and the line says how much
of it failed. The split also cost every panel its width: three charts side by
side measured 164px each in a 624px column, and `font-size="10"` reached the
screen at 4.5px in one of them (measured 2026-08-25). That 164px is the number
`console-frame.spec.ts` forbids, and the three-up row was the surface it was
written against - so the chart that replaces it is a `<figure>`, which is what
that check scans. Ruled by Susan (Craft and Delight) and Jony (UI/UX) on the
console signal review, 2026-08-30.

Two alternatives were rejected there. **Keeping three panels and adding
sparklines** leaves the split, which is the defect rather than the content
(Jony). **A single headline failure rate for the whole pipeline** hides which
stage failed, and which stage failed is the actionable half (Susan).

**The scatter was replaced on 2026-08-30, and what it cost is why.** It drew
article length against summary length on a log x axis: 2,740 marks in one colour
on a 1026px plot, measured that day. The dense middle rendered as a solid block,
which hid the outliers - the only marks on it anybody could act on - and reading
it meant taking two axes per mark to answer one question. The question is how far
a summary landed from the length the prompt asked for, so the distance is what
is drawn: at the widest preset that is 90 columns instead of one mark an article,
and the outliers are named rather than hunted for. Ruled by Susan (Craft and
Delight) with the owner on the measurement, 2026-08-30. The runner-up was a
density-binned scatter with only the outliers drawn individually; it was refused
because it keeps the two-axis reading the bar removes. Reducing the mark opacity
was refused for making a paler blob (Jony).

**Colour here is categorical, never the confidence ramp.** A summary outside its
band missed a length somebody chose in `config/`, and a policy limit is not a
verdict on the run - `TargetBar` draws the same line, lending the ramp only to a
threshold that is a health fact. Every swatch carries its word, so the three bins
are readable in a screenshot and in either theme.

**The bounds are printed as numbers beside the chart.** A shaded target zone with
no printed bound cannot be checked against what is drawn over it, which is what
the scatter asked a reader to do. The table prints one row a rung -
`under 60` / `30 to 45` - read off the ladder rather than off a rung, because a
rung records only the length it starts at and the last one has no ceiling at all.

**Three things went with the scatter, and none of them has a reader now.** The
dashed cap lines and their handover labels, which read `extract`'s cut off the
points in view; the diamond for an article the run cut short; and the pointer
readout, because a bar of counts has no mark to land on and its column already
carries a `<title>`. `capsInView`, `capLabel` and `seenWords` were deleted with
them. `CompressionPoint` keeps `source_seen_words` and `truncation_flagged`,
because `placeRow` still decides all three of its outcomes off the two lengths
and nothing else.

**A row the section cannot place is counted out loud.** The article length before
the cut is nullable - the pre-cap body is never persisted, so an older cut row
has no length to recover - and a row without one has no band. Measured over the
committed ledger 2026-08-29: 142 of 2,683 rows, 5.3 percent. The sentence under
the intro says how many, for whatever window is open, and the count comes from
the rows the server dropped rather than from a constant, so the sentence and the
columns answer out of one decision. A window that dropped nothing prints no
sentence at all. A section that drops articles without saying so under-reports
its own gaps.

**The oracle is that the split adds up.** `inside + short + long` equals the
day's own count of articles a band can be read for, recomputed in
[frontend/tests/console-compression.spec.ts](../../../frontend/tests/console-compression.spec.ts)
from the committed ladder and the canary's own projection rather than through the
page's reader. A split that does not add up is mis-binning articles, and the
picture would still look right. The canary was given one summary that runs past
its band on the same day - 260 words where the rung asks for 50 to 90 - because
every other row it writes lands inside or short, and a third state the fixture
cannot reach is a state an implementation can pass by never entering.

## Every chart with a shared column carries a pointer readout

**Every chart with a shared column carries a pointer readout, and it is not an
SVG `<title>`.** It was two charts when the strip was written and seven of
twenty-four by 2026-08-30; it is the default on all three console routes from
2026-08-31, and a chart with no shared column now says so in
`data-readout-none` rather than by saying nothing.
Both are **never pinned to the pointer** - a readout under a thumb is a
readout nobody reads. One
Svelte action beside `observeWidth` drives it
([frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)):
`pointermove` and `pointerdown` on the `<svg>`, which is one stream covering
mouse, pen and touch, plus `focusin`, `keydown`, `pointerleave` and `focusout`.
The hit rule is nearest mark **by x**, from positions the chart already
computed. Only a mouse leaving clears the readout, because a touch raises
`pointerleave` the moment the thumb lifts and clearing there would blank the
numbers before they could be read.

The `<svg>` takes `tabindex="0"` and the marks take none: Left and Right step,
Home and End jump, Escape closes. A tab stop per data point is a trap rather
than access - the committed ledger draws 2,541 of them. The `<title>` elements
stay as each mark's accessible name and are never the publication: nothing a
readout alone can tell you is needed to read either chart, which is also the
whole no-JavaScript answer.

**The stage-timing chart takes one of the two, and it is a strip below the plot
rather than a box over it.** A floating box was measured on 2026-08-29 at 88 to
121px over a 220px plot - 40 to 55 percent of the chart it was explaining - so
this one is laid out under the plot where it cannot cover a mark at any width,
and `chart.readout_max_share` bounds it at a third of the plot so it cannot
become a paragraph beside a chart being glanced at. The run-health strip still
gets none - it has no per-day point to land on, and it says so where it is
drawn. `FailurePanels` gained one: it does print every stage's rate and its
denominator in type under the plot, but not per day, and the day is the column
the strip prints.

**That strip is the legend as well.** The legend already printed the newest day's
four numbers and a sentence under it said which day they were, which is the
readout's resting state written out longhand. One strip prints a date and four
values, opens on the newest day, and follows a pointer or an arrow key; the row
order is still fixed by the newest day, because a legend that re-sorts under the
eye as the pointer moves is a legend nobody can read. Nothing is hidden until a
pointer arrives, so the no-JavaScript answer is the page as it prerenders.

**The throughput candle's readout moved below its plot on 2026-08-30, and it is
no longer `caption` verbatim.** It was a box over the plot carrying the
`<title>` sentence unchanged, on the rule that one day gets one sentence rather
than two. That box is the one measured above, and this strip is bounded by the
same `chart.readout_max_share`. `caption` closes with a run list that grows
with the day's run count, so it is the one clause with no bound, and at a third
of the plot it wrapped to four lines per series. The strip is a `<dl>` printing
the day, then one row per series carrying the median and the extent - every
series at once, so comparing read against write costs no second hover. It rests
on the newest day rather than opening blank, so pointing at the chart never
changes the room it takes and never moves the marks under the pointer. The
`<title>` keeps every word, including the middle half the box already draws, and
the run count stays in the verdict line under the legend.

The strip's shape is not this chart's own. `dayTicks`, `dayColumnX`,
`readoutCapStyle` and `readoutMarks` in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
hold the axis-thinning, the column arithmetic, the cap and the hover targets, so
the stage-timing trend directly above this one on the page and this chart cannot
drift apart. Two charts stacked on one page that hover differently cost the
operator a second guess.

**A window with nothing in it says so, rather than removing the chart.** Until
2026-08-30 the throughput trend rendered nothing at all when no day in the
window carried a measurement, while the stage-timing trend six inches above it
printed `We timed nothing in these 30 days`. Found 2026-08-30 by rebuilding the
console against an emptied item-health ledger: the page was intact and threw
nothing, and the chart had simply gone. A chart that vanishes beside one that
explains itself reads as a chart that broke. The heading now stays and one line
of type under it says the window is empty.

**The throughput axis names a day per column.** It shared the run strip's
sparse-label arithmetic until 2026-08-30, which printed the whole window as one
span string and no per-day label at all, so a spike could not be attributed to a
date. It now prints one date per plotted day through `dayTicks`,
thinned to what the plot has room for with both endpoints always kept, and the
span it used to print moved into the `<svg>`'s accessible name. Measured
2026-08-30 by building the canary console from either side of the change on one
machine in one session: 6 text nodes carrying 0 date labels before, 7 carrying 2
after, over a canary of two days. Five of those nodes are the y axis's own ticks
either way, so what moved is one span string becoming one date per column. A
dashed
vertical rule marks each boundary where the day's model differs from the day
before it, so a step in the trend is attributable to a swap rather than guessed
at; the model reaches the page through the prerendered HTML, from the same score
rows the model table reads, and no telemetry column was added to publish it. The
committed ledger holds one real swap - `qwen3-8b-q4-k-m` to 2026-08-26 and
`qwen3-5-9b-q4-k-m` from 2026-08-27 - and the published console draws exactly
one rule, on 2026-08-27, measured 2026-08-30 on a production build. The canary's
throughput days are older than the ledger's first row, so no day there names a
model and the rule cannot draw in the browser gate; the test says where it stops
rather than passing quietly on an absence.

## Stage timings are one trend chart, and its axis is decades

**Stage timings are one trend chart, not a list per day.** Four polylines over a
calendar x axis, oldest on the left, with a mark at every point and a date under
every column the density allows. The old block was one group of four bars per
day - about 150 rows at a 30-day window, and no trend - and "is it getting
slower" is the only question the section is asked.

**The x axis prints a date per column, thinned to what fits.** It used
to print one string for the whole span - `24-29 Aug 2026`, measured on the built
page 2026-08-30 - which is the run strip's sparse-label arithmetic, and that
arithmetic is right for a strip of 16px squares and wrong for a 760px plot. Six
labels over thirty days puts every mark within three columns of a date; one
label over six days put a spike nowhere at all. The first and last day are always
among them, evenly spaced indices fill the rest, and the year is printed once and
then only where it changes. `chart.tick_density` is the ceiling on how many the
axis may carry and the measured fit takes more away where the plot is narrow, so
nothing overlaps at 390px; a column whose date was dropped keeps its tick mark.
`dayTicks` in
[frontend/src/lib/charts/frame.ts](../../../frontend/src/lib/charts/frame.ts)
owns it, so the throughput candle beside it labels its axis the same way, and so
do the band columns, the failure panel, the run lengths and both run strips.
The rule and what it costs are in
[../../concepts/design-system.md](../../concepts/design-system.md).

**Every point on it carries a mark.** A filled dot is a measured time and an open
dot on the baseline is a measured zero; a day a stage was never timed on has
neither, and the note under the chart counts it. Before 2026-08-30 the chart drew
0 marks across 4 polylines, so there was nothing to aim a pointer at and nothing
for an arrow key to land on.

**Its columns are the window the operator set, not the days that carry a row.**
The chart used to build its own calendar from the first and last dated row it
held, so a control reading 30 days sat above a plot drawing 6. Two spans on one
page cannot be compared, which is the question the operator came for, and it is
the same defect the window control was built to remove - `windowOfDays` returns
exactly N days whatever the ledger holds, for the same reason. So the chart takes
the shared `TimeWindow` and draws `daysInWindow` of it; a day inside the window
with no row is a gap the notes already name, and a row outside the window is not
drawn. A window with no timings in it at all says so and offers the widening,
rather than drawing an empty frame.

**Its y axis is decades, and that is where the domain rule has its threshold.**
The padded, `.nice`, non-zero-anchored linear domain above stands for series
of comparable size. **It yields to a decade-rounded log domain when the drawn
extent spans more than two decades.** Measured 2026-08-25 on the committed
ledger, one linear axis over these four gave `summarize` 78.1% of the plot
height, `score` 2.15%, `fetch` 0.38% and `extract` 0.03%: one stage set the
domain and the other three drew flat on the baseline. The same four values on
the decade axis are 81.4%, 50.2%, 35.2% and 12.9%, so a tenth added to `extract`
and a tenth added to `summarize` are the same vertical move and the axis
measures change at every size. The composition survives the change - `summarize`
still sits on top, `extract` still at the bottom, and the gap still reads as
about three decades - so one instrument answers both questions. Decade gridlines
run full width and are labelled, crossing from milliseconds to seconds at
1000 ms; the eight steps inside each decade are unlabelled stubs on the y axis
only, because 32 full-width rules is a hatch rather than an axis, and without
them a log axis reads as a linear one with odd numbers on it.

**A series is deleted when it carries no information, never when the axis is
failing to show the information it carries.** `extract` at 42 ms was worth
deleting from the linear chart, where it was a flat line at the bottom. That was
a fact about the axis, not about the stage: on the decade axis it gets the same
vertical resolution as `summarize`, so a 3x extractor regression - what a source
changing its markup looks like - is as visible as a 3x model regression, and
nothing else on the console carries that signal.

**Three facts about a missing number, three marks, and none of them a bare
zero.** All three used to arrive at this chart as the number `0`: a day nothing
timed, a day whose median really was zero, and a day timed for only some of its
items. Each day now arrives as a `StageTiming` - the median, how many items the
stage timed, and how many items there were - and each fact draws as itself:

- **Nothing timed** breaks the line, because "no number" and "no time spent" are
 different facts.
- **A measured zero** breaks the line too, and draws an open dot in the stage
 colour, centred on the baseline rule. It is never clamped into the bottom
 decade: a clamped point draws a plunge to the floor of the plot, which states
 that the stage got a thousand times faster. Zero has no position on a decade
 axis, and the baseline rule is the one place on that axis which is not a claim
 about size. A median of zero does not mean the stage took no time - it means
 it finished faster than a 1 ms clock can measure, which is an ordinary state
 for a cheap stage. `state/scores.csv` recorded exactly that for `score_ms` on
 all ten rows of 2026-08-22 - the reading that made the rule necessary, taken
 on a column that has since moved to the Summaries route.
- **A day timed in part** draws the items it timed, and the line under the chart
 says how many that was.

One line of type per stage names whichever of the three happened, because a hole
in a line is a mystery and three holes that look alike are worse than one: `We
timed no fetch work on 3 of the 30 days. The line breaks there.`, `extract took
under 1 ms per item on 1 day, which is faster than we can time. The open dot on
the baseline marks it.`, and `We timed 1,240 of the 1,480 items for extract on 2
days. The line is the items we timed.` A stage timed in full on every day of the
window has nothing to explain and gets no line at all.

**A stage the window never timed is stated once, in the legend**: the row greys
and prints `not timed` where a value would be. It used to be stated twice - the
legend printed `no data` and a paragraph under it printed the same absence in
longer words. The open dot gets no legend entry either; the line of type names
it, and a key would be a second thing to read for a mark that appears on a
handful of days a year. A run of one day draws a dot, so a stage that runs on
alternate days is drawn rather than absent. With no days at all the section is
one line.

**The legend prints the newest day's value per stage, sorted by that value,
descending.** The number an operator acts on is today's; a window median moves
when the operator pans, which is the same defect that rules out indexing each
stage to its own median. Sorting by the newest day makes vertical position a
second signal beside colour, for free, and it reorders only when two stages have
changed places - which is when the operator wants to notice. **Colour stays
bound to the stage and never to the rank**, so a reorder never repaints a line.
The chart gains no linear/log toggle: a toggle is an admission that we could not
decide which axis is correct.

**The counts ride on the payload rather than being reconstructed from the
value.** The chart used to rebuild "this is absent" from the number it was
handed, which is how the three facts collapsed in the first place: `median`
returned `0` for an empty sample, and `score_ms` went through `Number(cell ?? 0)
|| 0`, which invented a zero sample point out of an empty cell rather than only
losing one. `sample` is now the only way to build a `StageTiming`, and
`median` takes one rather than a `number[]`, so a bare array of numbers - and
the fabricated zero that used to fill an empty cell - no longer type-checks.
`svelte-check` is the gate for that: `StageTimingDay` is a hand-written
prerender input, not a Pydantic contract and not a committed payload, so the
schema versioning in `CLAUDE.md` section 11 does not apply to it. Telling the
three apart cost the console route 509 B of gzipped first-load JavaScript, which
is 0.8 percent of it, measured 2026-08-27 against `origin/main`'s own source
built on the same tree and the same machine.

Authority: Jony, 2026-08-25; the three marks and the counts behind them, Jony
and Fowler, 2026-08-27.

## The model-change rule, and the charts it means something on

A dashed rule down a chart says one sentence: *everything left of this line was
written by a different setup*. That sentence is true of a chart of writing time
and false of a chart of feed outcomes, so the mark is a judgement about what the
chart measures and never a decoration applied everywhere. A marker that means
nothing on half the page teaches an operator to stop reading it, and that costs
the half where it did mean something.

**The boundary is a `pipeline_fingerprint` transition, never a `model_id` one.**
The stamp is a digest over every declared input that can move an output - the
weights, the quantisation, the llama.cpp build, the chat template, the prompt,
the output schema, the truncation cap, the decoding settings, and the extractor
and sanitizer versions
([../../../backend/idhazh/contracts/fingerprint.py](../../../backend/idhazh/contracts/fingerprint.py)).
Measured 2026-08-27 over 2,232 rows the stamp moved four times while every row
named one model, so a slug attributes a changed number to an unchanged pipeline;
[../../concepts/evaluation.md](../../concepts/evaluation.md) segments on the
stamp for the same reason.

**A day is a boundary when it ran a stamp the previous scored day did not run.**
A day that only stopped using one of yesterday's stamps started nothing, so it
is not one. A day carrying several stamps is one boundary, because a day is one
column and a change inside it cannot be placed any finer. Measured 2026-08-31
over the committed ledger - 3,884 rows, 10 scored days - that rule finds five
boundaries: 23, 24, 26, 27 and 29 August. Comparing only the previous day's last
stamp against this day's first would have found two, and would have called
2026-08-26 a single unchanged day while it ran three pipelines.

**Derived once on the server, over the whole ledger, and passed down.**
`pipelineChanges` in `$lib/server/model-work` is the one derivation and
`/console/`'s load calls it; a component that derived its own would be deriving
it off its own day list, and two of them would eventually disagree about when it
happened. Over the whole ledger rather than the window, so a chart opening on
the day after a change still knows the change happened.

**The rule is dashed, in the neutral rule ink, and never on the health ramp.** A
pipeline change is an event, not a verdict. It sits on the leading edge of the
changed day rather than through its own marks, so a step in the trend either
lines up with it or does not. A change on the oldest drawn day draws nothing: it
would separate nothing from nothing, because every day on the chart ran the
setup that came out of it.

**Every chart says which bucket it is in, in markup.** A chart that draws
carries `data-model-rule="yes"`, its own drawn span as
`data-model-rule-from`/`-to`, and one `data-model-rule-line` per boundary inside
that span. A chart that does not carries `data-model-rule="no"` and the reason
in words in `data-model-rule-none`. The pair is the point: an absent rule and a
rule nobody remembered to draw look identical on a page, and only one of them is
an answer. Where a drawing chart's span holds no boundary it says so in type
(`data-model-rule-empty`) rather than leaving the reader to guess.

| Chart | Route | Draws | Why |
| --- | --- | --- | --- |
| Time per item, by stage | Pipelines | **yes** | `summarize` is the model writing, and `extract` moves with the extractor version the same stamp digests. |
| Summary length against the length asked for | Pipelines | **yes** | The length a summary comes out at is decided by the prompt and the model, and the stamp covers both. |
| What one more article costs | Pipelines | no | Bytes an article are what got published, not how it was written. |
| Feeds that failed | Pipelines | no | A feed answered or it did not, before any summary existed. |
| Sources we may ask | Pipelines | no | Permission, a rest and a retirement are all decided before a summary is written. |
| Charts drawn for articles | Pipelines | no | The chart arm is a different model call, judged on its own retirement rule. |
| Time to write one summary | Summaries | no | A change moves every bar on it. The axis is seconds, so the window is pooled into one distribution and a day has no position to draw at. |
| Prompt cache | Hardware | no | A change moves it - the prompt is in the stamp - and its engine-drawn axis carries no rule yet. |
| Context headroom | Hardware | no | One bar a run, so there is no day edge to draw between. |
| Tokens per run | Hardware | no | One bar a run, so there is no day edge to draw between. |

The last three are the honest edge of this rule and are recorded rather than
hidden: two of them are charts a change **does** move, and neither draws,
because the mechanism is a `<line>` in an SVG the component owns and neither
chart owns one. Rows #19, #20 and #21 of the console chart-craft plan rebuild
all three, and the rule lands with the chart it belongs to. `ThroughputTrend` on
Summaries has drawn its own version since 2026-08-30, off `model_id` rather than
the stamp; that is the precedent this rule was generalised from and it is not
yet a caller of it.

**The rule reaches the readout as well as the plot.** A boundary day prints one
extra line in the strip under the chart, so a reader stepping the days with an
arrow key meets the change without a pointer. Two charts, one string, from
`$lib/charts/frame` - two charts describing one event differently is how the two
descriptions drift.

The wording never says "the model changed", because the stamp moves for a
reworded prompt or a rebuilt runtime as readily as for new weights, and four of
the five stamps in the ledger cannot be expanded into their cause at all
(measured 2026-08-27). It says *a new model, prompt or setting started here*,
which is the set the stamp actually covers.

Authority: Andre (AI/LLM) on which measures a change moves, Fowler
(Architecture) on one server-side derivation, Jony (UI/UX) on the mark being
neutral ink; console chart-craft plan Row #3, 2026-08-31.

## See also

- [console.md](console.md) - which panel is on which route, and the ruling behind its shape.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure may be worded, ranked and tinted.
- [telemetry-series.md](telemetry-series.md) - the grain every figure was measured at.
- [console-payloads.md](console-payloads.md) - what a browser may fetch.
- [../../reference/measurements-site.md](../../reference/measurements-site.md) - what the engine chunk and each console route weigh.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings a chart has to stay under.
