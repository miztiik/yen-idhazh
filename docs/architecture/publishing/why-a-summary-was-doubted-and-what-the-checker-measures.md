# What the summary console measures

**Last Updated**: 2026-11-17

`/console/model/` answers what the model wrote, how long it took, and what it got
wrong. Its panels are the retained measure cards, throughput, model read/write
timing, call endings, faithfulness, checking cost and summary length.
The cards and distributions are drawn to
the rules in
[../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md).

Which panel sits on which route is [console.md](console.md).

The native panels read the declarations in
`frontend/src/lib/console/queries/model.ts` through `sliceOnce`, at view time.
The cards and their daily disclosure remain private build-time inputs; their
published-summary count comes from distinct day metrics, not score-row counts.
Bounded dates from the publication inventory preserve the shared published-day
window without opening payload items or reconstructing reasons. No live
ledger values or ledger-read metadata are serialized into the route page data.
A missing private input and a recorded quiet input say different things.

Native throughput uses the same nearest-rank quartiles and median for the
daily candle and each run's readout. A single-run day therefore prints the
same middle rate in both places. Only paired reading and writing measurements
enter that population; whole-day token totals still supply the weighted rates.
The build-time reducer keeps its interpolated readings for existing callers;
the native adapter explicitly selects the nearest-rank rule for both grains.

The page owns one window control and one recording frame. Sampling, measurement
off, recording start, coverage by another record and private partial-read notes
keep the shared recording helpers' words. Live doors retain lost-day and
set-aside-file notes even when the surviving record is quiet. A missing value is
not a zero, and a failed read never supplies a success-shaped fallback.

## What one item cost the model is two clocks, drawn apart

`item-cost` sits immediately after throughput. Throughput measures tokens per
second; this panel keeps the independent reading/writing duration distributions
and their paired per-token costs. Its lead names the writing median.
[nativeItemCost](../../../frontend/src/lib/console/model/item-cost.ts) and
[ItemCost.svelte](../../../frontend/src/lib/console/model/ItemCost.svelte)
reduce and draw the original item-health cells, not summary-quality scores.

The two distributions share one seconds domain and the existing doubling bins.
Reading independently includes finite, nonnegative prefill_ms; writing includes
finite, nonnegative decode_ms. Measured zero belongs in the first bin; absence
does not. Each histogram applies console.min_attempts_for_rate to its own clock
count and prints the count when it cannot draw a distribution.

The two per-token cohorts are independent of those histogram populations.
Reading pairs a nonnegative prefill clock with input > cached >= 0 and divides
the clock sum by the fresh-token sum. Writing pairs a nonnegative decode clock
with positive output tokens and divides by their sum. Each prints its pair
count. These remain time-per-token costs, not inverted tokens-per-second rates.
Unknown cache counts are not zero reuse; the note counts prompts whose cache
count is unknown. The writing/reading cost ratio is unavailable unless both
costs exist and the reading cost is positive.

This panel keeps its item-health-only endpoint. It does not inherit Summaries'
common item-health/evaluation endpoint or the private cards' published-day
window. Each selected preset refreshes that independent reach; the first day
clamps to item-health's own first day. Its compact note prints the actual UTC
bounds. Request epochs discard stale answers, retry retains the successful
endpoint, and missing, quiet and unreachable stay distinct.

Prompt reuse remains on Hardware, linked from the panel. Its per-call held
tokens, fresh tokens, pooled shares and recorded cache percentages remain
separate readings; an unknown cache count cannot become a whole-prompt read.
Per-call charging follows
[the model's contract](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum).

## Which measurements the console draws

**The inventories describe real readers, not hypothetical receivers.**
[../../../frontend/src/lib/console/eval-instruments.ts](../../../frontend/src/lib/console/eval-instruments.ts)
assigns active measurements through `DRAWN_BY`, measurements no panel reads from
this ledger through `UNDRAWN`, and identities through `NOT_A_MEASUREMENT`. Together they
name every native `EvalRow` property exactly once, and nothing else.
`backend/tests/contracts/test_frontend_console_lists.py` compares the sets;
[../../../frontend/tests/console-model-instruments.spec.ts](../../../frontend/tests/console-model-instruments.spec.ts)
checks retained reductions and proves omitted diagnostics are not requested.
The build-time score reader requests only active measurements and identities.
One native Summaries journey checks arrival and a window change; real private
server rendering checks absent, quiet and populated records, including a valid
day without retired aggregates. The published count and date bounds survive;
missing retained readings stay unknown rather than becoming zero.

| Instrument | Receiver and reading |
| --- | --- |
| Compression | Summary length: median percent on the run's row, no mark of its own |
| Coherence | Daily figures: median signed cosine to two decimal places |
| Extraction cuts | Model cards and daily figures: real count and share, with the historical flag-meaning boundary |
| Summary and article lengths | Per-run shortest, median and longest summary against the requested length bounds |
| Runtime | Writing and checking clocks, tokens, failures and call endings from their native records |

`RECORDED` retains the coherence and compression labels and notes. Neither
receives a new threshold, confidence tint or worst marker. The cards and length
panel each say once: **Nothing acts on these numbers.**

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
0.80 and 0.50 as committed. No reading is tinted and no day is coloured.
The panel explains a flagged summary with "Automated check found a possible
mismatch. Read the original." This guidance is operator-only; reader pages show
neither confidence text nor a quality glyph. Scoring and saved bands are
unchanged.

**A rule under the axis floor is dropped, not handed over.** The floor rises to
fill the panel with the range the days hold, and on the committed record it sits
at 65 percent - above the doubt score. The engine clips a rule outside the axis,
so passing it anyway draws nothing and leaves the panel's own sentence naming a
line a reader cannot find. So the plot ships the rules its own scale reaches,
and the panel says "a line crosses the plot at each one the days on it reach"
rather than promising two. The doubt rule comes back on the day the floor drops
to meet a figure beneath it, which is the day an operator opened the panel for.

The distinction is between a threshold and a verdict. A rule across the scale
says what a score has to clear before it reaches the recorded high-confidence
band; a coloured figure says this one is bad, which is a judgement no fifteen
committed days can support. Until 2026-09-25 this page refused both, on the
ground that a threshold taken off this window would be a guess wearing a
measurement's clothes. That reasoning was sound and answered a different
question: these two were never taken off this window. They are already in force -
every published item carries the band they decide - so a panel that hid them was
an operator panel hiding the policy recorded on published items. Susan and Andre,
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
rather than moving their boundary to another measured day. The cards first
scope that rule to each mini chart's measured date range; their one native
history disclosure retains the complete selected-window rule and the shared
recording note remains visible. The
[model-card rules](../../concepts/console-design/what-the-quality-and-source-panels-draw.md#retained-measures-are-cards-and-the-rows-are-one-control-away)
own the wording and inspection behavior. Throughput keeps its
candles and adds the window-median rule; call endings skip empty cells and put
length endings at the bottom. Writing and checking keep `TimeHistogram` and its
domains. Failed-rule readings live only on Pipelines, through the shared
identity-free `failedRuleQuery`, `failureRuleRows` and `FailureList.ranking`.
Its stage control retains the model-stage readings in the native record. Summaries
mounts no refusal chart and starts no second failed-rule query.

## Design rationale

Reader warnings follow the
[confidence compatibility rule](../../concepts/evaluation.md#the-band-says-what-is-missing-not-how-good-the-item-is):
historical number/hedge chips and unexplained low/medium chips render nothing.
The console does not reinterpret mixed historical decisions as HHEM grades.

The unsupported-number, dropped-hedge, low-band aggregate, mixed-reason,
source-doubt, copying, repetition, lexical-coverage, source-language-density and
output-difference surfaces are removed. This gives up their historical counts,
shares and rankings; no replacement diagnostic or hidden live query remains.
HHEM and its full-article comparison, sentence-encoder coherence, lengths,
compression, real extraction cuts and runtime measurements remain.

The backend no longer calculates or emits those measurements. Current eval,
day, run and human-label contracts omit the retired fields; their native readers
discard the historical keys by name without changing archived records or
recorded scorer identities. Day readers also discard named retired instruments,
not unknown instruments generally. `UNDRAWN` now names only retained fields.
Legacy confidence-reason and copied-source outcome decoding is protocol
compatibility, not an active diagnostic.

The shared console band also omits low-confidence counts and related warnings.
Its model notes retain real failures, context refusals and extraction cuts.

Cards retain one settings-only history. Faithfulness retains scorer markers
only where `score_moved` is true. The publication-date list and independent
article, score and runtime windows remain separate; deleting reason rows must
not move their endpoints or turn unavailable input into a quiet measurement.

The combined model-change comparison is permanently removed, with no hidden
or relocated replacement. The
[quality-panel rationale](../../concepts/console-design/what-the-quality-and-source-panels-draw.md#design-rationale)
names the lost observational comparison. Individual metric trends and their
dated setting/model-change markers remain, as do the cards and their coverage
and absence behavior. Historical pipeline-fingerprint identities still support
the retained markers; removing this view changes no producer or compact contract.

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [../../concepts/console-design/what-the-quality-and-source-panels-draw.md](../../concepts/console-design/what-the-quality-and-source-panels-draw.md) - how the measure cards, the distributions and the compression chart are allowed to draw.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what the checker measures and what a verdict means.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control these panels answer to.
- [../../reference/site-weight.md](../../reference/site-weight.md#page-and-payload-guardrails) - how route and fetched-payload costs are bounded.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
