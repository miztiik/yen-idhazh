# Why a summary was doubted, and what the checker measures

**Last Updated**: 2026-10-11

`/console/model/` answers what the model wrote, how long it took, and what it got
wrong. Its eleven panels are the measure cards, throughput, call endings, refusing
rules, doubt reasons, faithfulness, source doubts, writing cost, checking cost,
summary length and the newest model change. The eleven original card labels stay
verbatim; determinism is the twelfth card. The cards and distributions are drawn to
the rules in
[../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md).

Which panel sits on which route is [console.md](console.md).

The nine eligible panels read the declarations in
`frontend/src/lib/console/queries/model.ts` through `sliceOnce`, at view time.
The cards and their daily disclosure remain private build-time inputs; their
published-summary and determinism counts come from distinct day metrics, not
score-row counts. The reasons remain private published-item decisions. No live
ledger values or ledger-read metadata are serialized into the route page data.
A missing private input and a recorded quiet input say different things.

Native throughput uses the same nearest-rank quartiles and median for the
daily candle and each run's readout. A single-run day therefore prints the
same middle rate in both places. Only paired reading and writing measurements
enter that population; whole-day token totals still supply the weighted rates.

The page owns one window control and one recording frame. Sampling, measurement
off, recording start, coverage by another record and private partial-read notes
keep the shared recording helpers' words. Live doors retain lost-day and
set-aside-file notes even when the surviving record is quiet. A missing value is
not a zero, and a failed read never supplies a success-shaped fallback.

## Why a summary was doubted, and the one ledger that can answer it

The route draws the five reasons a summary failed to reach the top band, one
column a day, over the window the page shares. The measure cards above it say how
often the checker stopped; this says which check failed.

**It reads the committed day payloads, not the eval ledger.** `band_reason` is
decided by `verdict` and written onto the published item by `assemble.build_day`.
The eval ledger's 35 columns carry the inputs a reason is decided from - `hhem`,
`coverage`, `unsupported_numbers`, `hedge_dropped` - and the band, and no reason
column at all. The route reads only the publication inventory's named day payloads,
and what ships is one count per reason per day
rather than the payloads. Re-deriving the reason from the ledger's inputs was
refused: it puts a second copy of `verdict` in a second language, and the day the
two disagree the console is wrong about the item a reader was shown
([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**The five are drawn apart and never added into one doubt count.** A single
number says how often the checker stopped and never says which fault to go and
fix. Each item carries at most one reason, so the five add up with nothing
counted twice - which is what makes the stack legal and what the oracle checks.

**Stacked, on `dateSeries`.** Each reason has one named series token, and the
stack counts decisions from the same day. It is not a sum of unrelated scores.
The drawing follows
[../../concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md](../../concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md)
without the former engine chart or its shape control. Every recorded checker
change marks the reason chart; faithfulness marks only changes whose
`score_moved` is true. Settings are dashed, checker changes dotted; a day with
both draws the settings boundary and prints both changes in its readout.

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

The recorded-only panel is gone. Its eight instruments now sit beside the
measure each explains, and the map still owes every measured field a receiver.

**The artefact is `DRAWN_BY`, not the charts.**
[../../../frontend/src/lib/console/eval-instruments.ts](../../../frontend/src/lib/console/eval-instruments.ts)
assigns every measured column of the eval ledger to exactly one panel, and
`NOT_A_MEASUREMENT` says of every remaining column why it is not one - fifteen
identity and provenance columns, each with a sentence. Between them the two must
name every property of
`EvalRow`,
once, and name nothing else.
`backend/tests/contracts/test_frontend_console_lists.py` compares the sets;
[../../../frontend/tests/console-model-instruments.spec.ts](../../../frontend/tests/console-model-instruments.spec.ts)
visits each receiver's declared route. So a column added to `EvalRow`
next month fails a test rather than going undrawn - which is the defect the map
exists for: `hhem` and `coverage` were scored on every summary from the first
published day and read by nothing on the site for two weeks.

| Instrument | Receiver and reading |
| --- | --- |
| Compression | Summary length: median percent on the run's row, no mark of its own |
| Self repetition | Daily figures: median percent, adjacent to coherence |
| Coherence | Daily figures: median signed cosine to two decimal places |
| Semantic coverage | Daily figures: median percent; before 24 September 2026, not measured |
| Evidential density | Source doubts: median per 1,000 article words on its source row |
| Speculative density | Source doubts: the same unit, beside the hedge count |
| Extraction suspect | Pipelines extraction: distinct published articles and days |
| Determinism violation | Twelfth model card and daily figures: distinct published articles per day |

The authoritative labels and notes remain `RECORDED` and `FLAGS`. None receives a
threshold, direction, tint or worst marker. Each receiving panel says once:
**Nothing acts on these numbers.** Densities are figures, never parts of a bar.
Sources meet score and item records only on the declared URL key, keeping the
later score of a repeated URL. Unmatched scores are counted, never assigned a
fabricated source; a small sample refuses its share instead of drawing zero.

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

**A median line and its quartile spread on faithfulness.** Measured 2026-09-06 over the
fifteen committed days, the middle summary's faithfulness sat between 88 and 95
percent while the lower quarter swung from 73 to 94 - so the level and the tail
are different facts. The median is the line; the lower and upper quarters are
its spread, not separate percentile lines. The table prints all three readings.

**A line, and no shape switch.** One percentile added to another is not
a quantity, and neither is one day's share added to the next day's. The condition
for carrying that control is that both shapes read the same array honestly. Bars
here would not.

**A daily figure is that day's middle measured summary.** Medians and percentiles
use the project's nearest-rank rule: an actual observation, never an average of
two observations. The daily disclosure does not replace an unavailable reading
with zero. A coherence cosine keeps its sign and is not mislabeled a percentage.

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
[../../reference/site-weight.md](../../reference/site-weight.md#page-and-payload-guardrails);
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

`RunLengths`, `Sparkline` and `ThroughputTrend` accept the optional structured
model rule; callers that omit it retain their legacy behavior. `completeModelRule`
(also exported as `fullModelRule`) preserves changes on unmeasured days in a note
rather than moving their boundary to another measured day. Throughput keeps its
candles and adds the window-median rule; call endings skip empty cells and put
length endings at the bottom. Writing and checking keep `TimeHistogram` and its
domains. Refusing rules use the same identity-free `failedRuleQuery`,
`failureRuleRows` and `FailureList.ranking` as Pipelines, restricted to model stages.

The newest model change compares dated model-ID sets over the widest declared
span, splitting independent score and timing populations at the change date.
It never joins the before and after article populations. The approved declaration
does not carry a faithfulness-score column: its median-score change therefore says
not measured rather than inventing a score or broadening the query.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md) - how the measure cards, the distributions and the compression chart are allowed to draw.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what the checker measures and what a verdict means.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control these panels answer to.
- [../../reference/site-weight.md](../../reference/site-weight.md#page-and-payload-guardrails) - how route and fetched-payload costs are bounded.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
