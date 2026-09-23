# What the Pipelines route draws

**Last Updated**: 2026-09-23

`/console/` answers two questions: did the runs work, and what each stage cost.
This page holds three of its panels - where a run's time went, what one item cost
the model, and extraction. Chart drawing has its own page,
[how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md),
and the feed and source panels belong to Voices
([who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md)).

How any figure here is allowed to read is
[../../concepts/console-design.md](../../concepts/console-design.md). Which
surfaces follow the window control is
[which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md).

## Where a run's time went is one panel on Pipelines, at two grains

| Panel | Grain | The sentence it is for |
| --- | --- | --- |
| Where the run's time went, on the run's own clock | one bar an item, or one bar a shard | Whether the run queued or worked in parallel, and where in it the time actually went. |

**It answers "is it working".** It takes the run's central shape - what it took
end to end, what its items cost added up, and how many ran at once - and it
covers every item of the run rather than picking the worst one out. The grain
switch changes the row and never the question.

**It sits low on Pipelines, and `Run health` is the route's first panel.** A
window is a span and this panel is one run, so an operator reaches it after a
windowed panel has told him which run to open it on - and the panel that
verdicts the route goes first, which is the thirteenth chart rule applied
([../../concepts/console-design/the-rules-every-console-chart-obeys.md](../../concepts/console-design/the-rules-every-console-chart-obeys.md#thirteen-rules-hold-for-every-chart-on-this-console)).
Pipelines takes one untitled group in `console.panel_groups`: what it needed was
an order, not headings, and it already carries four section headings of its own.

**One panel, not two, and the grain is why.** Drawing a shard's clock from
`state/span-rollup/` beside an item timeline from `frontend/public/run-timeline/`
is two folds over two ledgers that can name different runs as the newest, and on
the committed data they routinely did - the rollup and the published mirror start
on different days. The merged panel folds both grains from one set of rows in one
builder call, so a step's seconds are the same seconds whichever row a reader is
on. A shard's bar runs from its first item's start to its last item's end, which
is the stretch it held a worker for, and its steps are that shard's items added
up.

**A separate shard panel is refused, and thickness was never the defect.**
Measured 2026-09-17 over 23 shard rows of `state/span-rollup/2026-09.csv`, the
four sub-steps of a shard's clock together drew **0.026 px of a 760 px track**
and the residual drew **0.039 px**. A browser paints neither, so such a panel
publishes a legend teaching a reader that four categories were zero when they
were only unmeasurable at that scale. No bar thickness fixes a band that narrow.

**Every figure it would carry survives, printed.** The four sub-steps sit under
the bars as figures, each beside the step it runs inside - `tag read` is the
tagging step inside taking the article out, not a step beside it, and a reader
who takes it for one adds it twice. The overhead outside every item is printed
with them, and the run's item time plus that overhead is still the shards' whole
clock. Nothing visible is lost, because none of it was ever visible.

**Hollow is unclaimed, hatched is overclaimed, and both carry a legend key.** A
reader cannot name the hatched notch on sight, which is the test: a texture
nobody can read is a texture that says nothing. Neither is tinted - nobody has
agreed how much overhead is too much.

The readers are
[../../../frontend/src/lib/server/run-timeline.ts](../../../frontend/src/lib/server/run-timeline.ts)
and
[../../../frontend/src/lib/server/span-rollup.ts](../../../frontend/src/lib/server/span-rollup.ts);
the producer of the published mirror is
[../../../backend/idhazh/telemetry/publish/run_timeline.py](../../../backend/idhazh/telemetry/publish/run_timeline.py),
its shape is [run-timeline.md](run-timeline.md) and every drawing rule is
[../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md).
[../../../frontend/tests/console-pipeline-timeline.spec.ts](../../../frontend/tests/console-pipeline-timeline.spec.ts)
holds the shard grain against the item grain per shard and per step, and fails on
a declared column that is empty across every canary row.
[../../../frontend/tests/console-substeps.spec.ts](../../../frontend/tests/console-substeps.spec.ts)
re-derives each printed figure straight from the committed rollup cells, proves
the sub-pixel rule on a built fixture in both directions, and reaches the empty
state through a rollup truncated to its header. The fixture rollup the canary
draws is written in
[../../../frontend/scripts/build-canary.mjs](../../../frontend/scripts/build-canary.mjs).

**It is a snapshot, so the window control does not reach it.** A bar's position
is measured from its own run's start and a span cannot narrow one run, so the
panel names the run it drew. It reads one published directory bounded to two
months and one `state/` ledger bounded to the archive window, and with either
gone the view is empty by construction and the route still renders whole.

**Pipelines depends on `$lib/charts/machine` for its `seconds` formatter, and on
`STATE_ROOT`.** The second is the one worth knowing: a build with `STATE_ROOT`
unset draws the named empty state for the sub-steps, which is correct rather than
broken.

## Run health, and the strip of runs beside it

`Run health` is the route's first panel and its verdict: did the runs work.

- **The run strip reads left to right in time**, like every other time series on
  the console. Right to left makes the newest day's position depend on how much
  history exists.
- **A scheduled run that wrote no manifest draws no square.** An empty square
  claims evidence the payload does not carry; missed runs need a persisted
  schedule or attempt contract before they can be drawn.
- **No date under every column.** At 16px a track and 10px a label the dates
  overlap from about the fourth day, and an axis that cannot be read is
  decoration.
- **The strip is a native scroll region** - it pans with the arrow keys, costs no
  bytes and needs no focus management of its own. It never re-centres itself on
  the newest run after a data or layout change: the operator scrolled there on
  purpose, and a view that snaps back cannot be read.
- **One threshold decides the red square, and CI owns it.** CI already reads a
  success floor to decide whether to open an issue. Two numbers answering one
  question drift, and then a red square and an open issue disagree.
- **A skipped item is not counted against a run's health.** An already-published
  article is skipped by design, and counting it would paint a healthy day amber
  for doing its job.

## What is failing, by stage

- **One column a day, with the volume in the column.** A window holding one day
  is one column and still says how much work there was; only a window holding
  nothing at all draws no chart.
- **One chart, not three panels with sparklines.** Three panels leave the split,
  and the split is the defect rather than the content. A single headline failure
  rate is the other end of the same mistake: it hides which stage failed, and
  which stage failed is the actionable half.
- **The failed rows are on demand.** Rendering every failed row in the window
  measured 7,824 px over 800 rows and pushed the compression chart to document
  y=9,105. A cap and a button solve it; a virtual-scrolling table buys a
  dependency and a scroll-position bug for the same result.
- **No stage glyph beside the stage name.** The icon set is one generated module
  that reaches every route, so three stage marks would move six reader routes
  that cannot show this section at all. An icon that needs a caption is a label
  wearing a costume, and the stage name is already in the cell.
- **No `run.success_floor_pct` reference line.** That floor is a published rate
  over attempted items and a stage panel is a different denominator. A wrong
  reference line is worse than none.

## Time per item, by stage

Stage timing medians read from `state/item-health/<YYYY>/<MM>/<DD>/`, not from
`state/scores.csv`. The item-health ledger has one row per planned item, so it
can answer "is it getting slower" even when the scorer did not run; the score
ledger owns faithfulness and scorer time for the scored subset, and never carried
these columns.

**The chart draws three stages, and `score_ms` is not one of them.** Every line
on it is something an item waits on - and the scorer reads a summary the model
has already finished, so nothing waits on it. A fourth line there would read as a
fourth constraint on the run. It is on the Summaries route instead, under `What
one summary cost`, beside the cost of writing the summary it checks. An empty
cell is one fewer item timed, never a zero; a zero is the value the column
defaulted to before it was written, and it is counted as untimed for the same
reason.

The axis, the three marks a missing number can take and the model-change rule
are [console-charts.md](console-charts.md)'s, because the throughput chart beside
this one has to draw them the same way.

**The console reads committed records in two ways.** The run strip, feed list and
timing medians read the ledgers at build time. The item-health viewport fetches
the browser-safe monthly projection under `telemetry/<YYYY-MM>.csv`. Nothing
under `state/` is ever served - the browser reads only the narrow projection that
drops `canonical_url`, `url_key` and `detail`
([telemetry-series.md](telemetry-series.md),
[console-payloads.md](console-payloads.md)).

## What one item cost the model is two clocks, drawn apart

`What one item cost the model` is a section of the Pipelines route with two
distributions and seven printed figures. It answers what a run total cannot: how
long the model spent on **one** article, split into the part it spent reading and
the part it spent writing.

The Hardware route already pools both quantities per run and per shard, out of
the model server's own counters. That is a different measurement of a different
thing, and it cannot say that one item in nine got nothing from the prompt
cache. This section reads the published projection, per item, and follows the
window control.

### Reading and writing are two charts, and pooling them is refused

Measured 2026-09-05 over the 6,104 items of the committed projection that carry
both clocks: a prompt token costs about **101 milliseconds** to read and a
written token about **183** to write, so a written token costs **1.8 times** a
read one. The two also move for different reasons - the article's length moves
the first and the summary's length moves the second - so an operator acts on
them separately. One `model seconds` chart would hide which of the two moved.

The panel prints both rates and the ratio, and then says the thing the ratio is
for: cutting a hundred tokens from the summary saves more time than cutting a
hundred from the article. The sentence is derived from the measured ratio rather
than written down, so it flips if the ratio ever does.

Both are drawn as **doubling bins**, by the same `distribution` the Summaries
route's two clocks use, which lives in
[frontend/src/lib/charts/series.ts](../../../frontend/src/lib/charts/series.ts)
so a route outside `$lib/server/` can reach it - four panels share one binning
and one pair of rules, rather than four that can drift apart.

The axis is a doubling and not a linear one, and the ledger says why. Measured
2026-09-05, reading one prompt runs from **1.4 seconds to 692**, which is nine
doublings; on a linear axis every bar but one is a hairline against the left
edge. Writing is the opposite shape and is drawn the same way on purpose:
**4,456 of 6,104** items land in one bin, 32 to 64 seconds, and drawing it
linearly would suggest a spread the measurement does not have. `fetch_ms`, whose
worst is 43,627 ms against a middle of 567, is not in this section at all - it is
a stage clock and `Time per item, by stage` above already draws it per day.

### The prompt cache is a share, and the share is printed rather than drawn

The panel prints **absolute prompt tokens** - the ones the model read against the
ones it did not - and the share beside them as whole percent. Four more figures
sit under those three: the middle prompt, the middle summary, the middle item's
own share, and how many items were read whole with nothing held over.

**A two-segment track is refused.** One flat bar on no time axis, under a note
telling the reader not to read its direction: a figure a panel disowns is a
figure to remove. **What the reader loses, named:** the picture of the split,
which is three printed counts instead. What the split was ever worth was the
counts it was built from, and the track carried no fact they do not.

**The level and the direction are one subject at the two questions.** This panel
would carry the level - how much of the window's prompt the model already held -
and `How much text the model has to read again each time` on Hardware carries the
direction, one column a day. With no level drawn, the Hardware panel is the whole
answer rather than half of one, so the gap a later reader sees here is a subject
already covered and not a figure to rebuild.

**A falling share here does not mean the cache got worse, and the panel says
so.** Measured 2026-09-05 over the same 6,104 items, `cached_tokens` is nearly a
constant: the middle item kept **922** tokens and the widest kept **941**, while
`input_tokens` runs from a middle of 1,688 to a worst of 7,093. So the share
moves almost entirely because the denominator moves. Drawn as a line over time it
would fall on a week of long articles and read as a cache regression, which is
the one wrong thing an operator could act on. That sentence is the reason a
figure is missing, which is the kind of sentence this console keeps.

Measured over the committed projection the per-item share has a middle of
**0.518**, a 5th percentile of **0.000** and a 95th of **0.820** - and **667 of
6,104** items reused nothing at all. The share is drawn, and it is named in words
beside it.

**These four figures are about the FIRST model call, not about the item.** An
item read by two calls always reuses something, because the second call replays
the first call's prompt and is answered for it - so "read whole with nothing held
over" taken off the item total would count nothing for ever, a live figure
becoming a constant with no code change. Where the projection publishes a split,
the four read `label_*`; where it does not, they read the totals as they always
did, and `perCall` says how many rows of the window were which. Every rate on
this section still pools the totals, which is correct: a sum over both calls is
what the item cost
([the split](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum)).

### Every denominator is its own, because three of them differ

An item that failed before the model saw it has no clock and no token count; one
that failed before the fetch has no stage clock either. Measured 2026-09-05 over
the committed projection: **8,300** rows in all, **6,873** with a stage clock and
**6,104** with the model's own two. One "items" figure would be wrong for at
least one column of this section whichever row set it counted, so each figure
carries the count it answers for and the lead states the widest one.

An empty cell stays empty. A mean that treats an absent instrument as a zero
turns every fetch failure into a fetch that was infinitely fast, and zero reuse
is a real answer that has to stay counted - which is why `readWhole` is a count
and not an exclusion.

### It follows the window's length, not a pan

The reduction is taken on the server, once per entry in
`console.window_presets`, and the browser picks the open one - the same
arrangement `Sources cut short most often` and the Summaries route's
distributions use.

**That is a measured choice, not a preference.** The prerendered seed carries the
eight columns as nulls, because seeded with their real values they cost
`/console/` **176,753 gzipped bytes** - 198,624 to 375,377, and 98,182 over the
recorded ceiling (measured 2026-09-05, recorded in
[telemetry-series.md](telemetry-series.md)). The two alternatives were to seed
the columns this section draws, or to drop the seeded months from `loadedMonths`
and let a runtime fetch fill them. Both were refused: the first buys the ceiling
problem the seed was written to avoid, and the second puts a 244 KB fetch behind
the first click of a control and leaves the section blank until it lands.
Reducing on the server costs the page about a hundred numbers a preset and draws
complete before any script runs.

What it costs is stated on the page: panning does not move these days, and they
always end on the newest day the ledger holds. The section says so in the same
words `Sources cut short most often` does, because one rule stated two ways reads
as two rules.

## Extraction answers both questions, and labels which half is which

`Extraction` is a Pipelines panel in two halves, and it is the console's worked
example of a panel that serves *is it working* and *what is broken* at once
rather than choosing.

The **verdict half** is four cards: articles the reading found enough figures of
one kind in, the share of published chartable articles that went out with no
chart, the share of articles whose every fact still cuts its own characters, and
the facts kept over the window. Four levels, covering the whole reading. They
carry `data-extraction-question="is it working"`.

The **break half** is one chart, `Whether the yield is falling`, carrying
`data-extraction-question="what is broken"`. Two of the cards' own lines tell the
operator to read the direction rather than the level, so the panel plots one
point a day: articles the reading found enough figures in, against published
articles carrying a chart. That pair is the discrimination the panel exists for -
the planner stopping and the extractor stopping look identical in the published
chart count alone, and they have different fixes
([../../concepts/evaluation.md](../../concepts/evaluation.md)).

**Both series count articles, so they share one value domain**, and the panel
prints the ratio it measured. Measured 2026-09-17 over the nine committed day
records that carry an extraction block: `chartable` peaks at 225 and
`chartable_charted` at 20, which is **11.3 times** and inside the 20 a shared
axis holds. The domain is taken from the days drawn rather than fixed - there is
no ceiling here to measure distance from, so a fixed maximum would only waste the
plot on a quiet day.

**A window with one measured day draws that day as a point, not an empty plot**,
and says in words that a single day has a level and no direction. A window with
no measured day draws no axis at all and says so: an axis over nothing is a claim
the data does not support.

The four rules this panel is built to - a panel names which of the two questions
it serves, a title that asks a trend question draws a time axis, two series share
one axis under twenty times with the ratio printed, and a value domain is fixed
only where a ceiling is the comparison - are in
[../../concepts/console-design/the-rules-every-console-chart-obeys.md](../../concepts/console-design/the-rules-every-console-chart-obeys.md#thirteen-rules-hold-for-every-chart-on-this-console).

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md) - the rest of Pipelines.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control these panels answer to.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
- [run-timeline.md](run-timeline.md) - the ledger the run panel draws.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
- [console-payloads.md](console-payloads.md) - what the console fetches, and what it may never be served.
