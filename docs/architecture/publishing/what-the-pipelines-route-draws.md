# What the Pipelines route draws

**Last Updated**: 2026-10-12

Moved plots use the shared width observer and redraw in the CSS-pixel frame
their panel actually occupies. Private date axes retain missing days as null,
not zero, so a settings change on a day without a reading still has its place.
The route resolves its record window before calling the private panels settled.
Native reads start independently; request epochs prevent late windows replacing
the current one, and the extractor and recorded flags retain separate states.
Native record limitations sit after the failure plot, not above the private
carry line: receiving the ledger must not move the window controls or chrome.
The retained run-square cut wording is tested on that actual component with
independent capped and uncapped records; no item-ledger cut identities cross
the native page's private manifest boundary.
After the representative-test consolidation, native disk/private contracts run
in the logic group. Explicit Pipelines component, lifecycle, window, waiting,
request-dependency and populated plot cases run in the console group. Retained
compression and identity-list oracles mount the actual retained components,
not retired route UI. There is no restored cross-route panels/capture matrix.

The retained timing and histogram plots name their actual drawing elements for
the shared chart checks. Timeline rows name their actual bar frames. An absent
private chart-share record still has a headline, stating its absence rather
than inventing a percentage. The first published-count card is the route verdict;
its count note names the same calendar that its bars draw.

`/console/` answers two questions: did the runs work, and what each stage cost.
This page holds its native stage and cost readings and its private run figures.
Chart drawing has its own page,
[how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md),
and the feed and source panels belong to Voices
([who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md)).

How any figure here is allowed to read is
[../../concepts/console-design.md](../../concepts/console-design.md). Which
surfaces follow the window control is
[which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md).

## Plan52: native readings and private published-day facts

The route now has twelve addressed panels, in this order: `at-a-glance`,
`run-health`, `site-cost-per-item`, `failure-mix`, `item-time-split`,
`slower-on-same-work`, `stage-timings`, `item-cost`, `run-timeline`,
`chart-drawing`, `extraction`, `article-age`. Configuration comes from
`consoleKnobs()` and `routeConsole('pipelines')`, not from page data.

The browser uses the declared queries in `console/queries/pipelines.ts` and the
shared `routeReach`, four-argument `rangeFor` and `sliceOnce` lifecycle. Failure
mix, failed rules, item time split, fixed-reference work, stage timings, model
cost, newest-run timeline and stated article ages read `item-health`. The
recorded extraction flags separately read `summary-quality-evals`. It is not a ledger
named `scores`. Neither route load nor the browser reads telemetry CSV,
`run-timeline`, `span-rollup` or a month inventory for these panels.

`at-a-glance`, `run-health`, `site-cost-per-item`, `chart-drawing`, and extraction's
published-chart share and yield remain private BUILD_TIME readings of manifests,
published-chart counts and day metrics. They are not newly published datasets
and are not reconstructed from native queries. Extraction's private share is
prepared for each permitted window and recorded endpoint, so a native endpoint
earlier than the built day does not reuse the wrong day's share.
`ChartDrawing.svelte` retains its private `chartFlow` diagram or stepped list,
target cards and sparklines. Those use published-day records, not inferred
item failure populations.

Before native answers arrive their frames reserve space, without bars, dates or
numbers posing as readings. Failure-rule and evaluator states are independent
of the item sections. Retry re-asks only failed queries; successful returned
answers keep their own ranges. A retry keeps the original common endpoint; only
a new preset starts a new window. The record notice uses the ledger's actual
first day, not the first plotted day. Lost days, set-aside files, unknown cells,
and recorded zero remain distinct.

The approved A1 contracts are wired: FailureList accepts identity-free rule rows
with stage radios, StageTimings retains the complete settings/checker rule, and
the two cost histograms use the named reading-prompt and writing-reply tokens.
The rule ranking makes no source, detail or distinct-article claim. Failure
percentages divide failed rows by recorded rows, since the declared slice carries
no article identity. Private payload shrinkage is a signed reading, not a zero
bar. No unavailable value is filled with zero to get a gate through.

Retained telemetry components keep independent real-input correctness cases
off-route; those fixtures do not restore compression, source rankings or item
details to Pipelines. Populated native panel gates use packed declared records
with explicit feed timestamps and measured clocks. The ordinary canary's
inferred article timestamp is not treated as a measured age. With scripts
disabled, native frames explicitly say the article record needs JavaScript;
private published-day marks remain in the document.

At a glance is the sole route verdict; run health remains its own comparison.
Declared date plots name the exact calendar they drew, including null days, and
opted-in count cards name their own declined settings rule. The native cold-load
check keeps the four-hop ceiling on independent ledger/data/engine branches,
with real held responses and planted serial requests proving the distinction.

Native readout headings spell dates for readers and declare that their inputs
are fetched. Private strips remain prerendered. The site-cost horizon states
both measured rates and the Pages cap; its signed size delta names the selected
span. Shared legacy month-price and reserved-tint contracts are still tested on
their retained real components, while the route's waiting and retry tests hold
its declared native index. A clipped native calendar is not widened with
invented pre-record days to satisfy a legacy telemetry oracle.

The flag count keeps the newest recorded boolean for each distinct article;
null cells cannot replace a flag, and conflicting booleans on its latest
recorded day stay unknown in any row order. Counts remain exactly the recorded
counts, not claims that a checker ran. The panel states that checker identity
and version are unavailable. The declared query has only date, article key and
the flag. `EvalRow` defaults the flag to false, and `work.py`'s `to_eval_row`
does not pass an extraction measurement. No contract guarantees that other
evaluators leave null. A zero count therefore says only that no recorded flag
is true. Proving instrument selection needs an owner-designed provenance
producer and declared query contract; this route invents neither.
Each native half states its returned dates beside the private published figures.
Private payload-size rates require the immediately preceding manifest and the
current manifest to both record a finite size; a missing size is not zero.

The approved item-time composition uses one complete, reconciling cohort for
fetch, extract, summarize, faithfulness, the total and the signed gap. Summarize
is counted once. Label, summary and visual-plan calls remain non-additive details,
including timed counts and null readings. Positive unnamed gaps and negative
overlap are averaged separately, so cancellation cannot hide overlap. The chart
draws every positive duration, an adjacent overlap deduction and an elapsed-time
marker; formatted readouts, cohort counts and exclusions explain the arithmetic.

## Where a run's time went is one panel on Pipelines, at two grains

| Panel | Grain | The sentence it is for |
| --- | --- | --- |
| Where the run's time went, on the run's own clock | one bar an item, or one bar a shard | Whether the run queued or worked in parallel, and where in it the time actually went. |

**It answers "is it working".** It takes the run's central shape - what it took
end to end, what its items cost added up, and how many ran at once - and it
covers every item of the run rather than picking the worst one out. The grain
switch changes the row and never the question.

**It sits low on Pipelines, after the cost panels.** A
window is a span and this panel is one run, so an operator reaches it after a
windowed panel has told him which run to open it on - and the panel that
verdicts the run remains near the top, which is the thirteenth chart rule applied
([../../concepts/console-design/the-rules-every-console-chart-obeys.md](../../concepts/console-design/the-rules-every-console-chart-obeys.md#thirteen-rules-hold-for-every-chart-on-this-console)).
Pipelines takes one untitled group in `config/console/pipelines.json`: what it needed was
an order, not headings, and it already carries four section headings of its own.

**One panel, one source for both grains.** The panel folds item and shard rows in one
builder call, so a step's seconds are the same seconds whichever row a reader is
on. A shard's bar runs from its first item's start to its last item's end, which
is the stretch it held a worker for, and its steps are that shard's items added
up.

**Detailed sub-steps belong to an item inspection.** The page does not print
robots, tag, prompt-render or reply-parse totals below the timeline. The reader
keeps the recorded stage clocks and the timeline, but loses those four aggregate
figures. The [item command](../../concepts/telemetry.md#the-committed-traces-briefly)
prints recent trace trees with their run and attempt instead of adding item
passes together. Expired detail remains unavailable.

**Hollow is unclaimed; a solid 2 px tertiary rule is overclaimed.** The overrun
is not the hatch for an unknown reading. Both have a written legend; neither
claims anybody has agreed how much overhead is too much.

The reader is
[../../../frontend/src/lib/console/pipelines/run-timeline.ts](../../../frontend/src/lib/console/pipelines/run-timeline.ts);
its native clock shape is [run-timeline.md](run-timeline.md) and every drawing rule is
[../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md](../../concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md).
[../../../frontend/tests/console-pipelines-native.spec.ts](../../../frontend/tests/console-pipelines-native.spec.ts)
checks the native offsets, signed residuals, missing clocks and capped totals.
The retained panel draws both grains from that same result.

**It is a snapshot, so the window control does not reach it.** A bar's position
is measured from its own run's start and a span cannot narrow one run, so the
panel names the run it drew. It asks the newest recorded day of item-health for
exactly its declared native clock columns. With that data absent, the view is
empty and the route still renders.

**Pipelines depends on `$lib/charts/machine` for its `seconds` formatter.**

## Run health is one panel: the day's articles, and every run under them

`At a glance` is the route's first panel and its verdict. Its private count cards
compare articles published with visuals published over the same days. `Run health`
follows it and compares the day's delivery with the runs that tried it. It
draws two figures on one day axis, and they answer one question between them -
did each day's runs deliver.

1. **`Articles published against planned`**, a heading and a caption over a chart:
   three bars a day - planned, published, failed - on the left axis, and the
   share published as a line on a right axis fixed at 0 to 100 percent. A day
   nothing was planned on is tinted. Under 480 px of drawing the chart keeps the
   planned bar and the line.
2. **The run squares**: one square a run, stacked on the day it ran, run 1 at the
   bottom. A day's squares stand directly under that day's bars, 8 px
   (`--space-2`) below the chart's date row, with nothing between.

One readout and one hint sit under both, and the panel's reading rule closes it.
The panel has no note under its title.

- **Both figures take their x from one function.** `daySlots` in
  [../../../frontend/src/lib/charts/day-slots.ts](../../../frontend/src/lib/charts/day-slots.ts)
  turns the chart's drawn width, its number of days and its margins into one
  equal slot a day. The chart computes it once and hands that same object to the
  squares, so the squares cannot drift off the bars when a margin moves. Before
  the two figures shared a panel they were laid out by two calculations from two
  left edges, about 41 and 43 px a day apart, and reading down from a bar landed
  on the previous day's squares.
- **A square is 80 percent of its day's slot, and 3 to 14 px.** Those are the
  dense strip's own limits in
  [../../../frontend/src/lib/charts/run-history.ts](../../../frontend/src/lib/charts/run-history.ts):
  no smaller than a square a reader can still see, and no larger than the bar
  beside it, because a square larger than the bar reads as the more important of
  the two. Two squares of one day are a quarter of a square apart, and at least
  1 px.
- **One picked day.** Pointing at either figure, or stepping with Left and Right,
  picks one day on both: the chart draws its guide line, that day's squares take
  the selected tint, and the readout prints the day's counts and one row per run.
  Escape on either figure returns both to the newest day.
- **On a phone the squares keep their own strip.** Where the chart draws its
  narrow shape, or where a square would come out under 3 px - a window of about
  330 days at 1440 px - the squares draw the scrolling strip instead: 16 px
  squares, a date row of their own, and a view that opens on the newest day. A
  tap or an arrow key on the chart scrolls that strip only as far as it takes to
  show the day. A hover, or the start of a touch, never scrolls it; without that
  guard every page scroll that started on the chart would drag the strip with it.
- **A run row says what the run did, in counts.** `Run 1` reads `8 of 8
  succeeded`. A red run adds `under 70%`, a run that tried nothing reads `nothing
  new to try`, and a run that crashed reads `the run failed`. The words `ran
  clean` and `worth a look` are gone from this panel: they named a colour rather
  than a fact, and the colour is already the swatch beside the row. The standing
  band above every route still prints them beside its own squares, from its own
  producer. A square's own label carries
  the whole run - `Run 3 on 20 Aug 2026: 0 of 5 succeeded, under 70%, 5 failed,
  the run failed`.
- **Each figure keeps its own empty state, and the panel never disappears.** A
  window nothing was planned in says so where the chart would be; a window with no
  run says so where the squares would be, in a different sentence from the one an
  empty record gets. Picking a day on the figure that has data still works.
- **The panel states its span in its own accessible label**, `Run health, over N
  days`. A sighted reader has the
  window control at the top of the route and the chart's date row.
- **The squares read left to right in time**, like every other time series on
  the console. Right to left makes the newest day's position depend on how much
  history exists.
- **A scheduled run that wrote no manifest draws no square.** An empty square
  claims evidence the payload does not carry; missed runs need a persisted
  schedule or attempt contract before they can be drawn.
- **The phone strip is a native scroll region** - it pans with the arrow keys,
  costs no bytes and needs no focus management of its own. It opens on the newest
  day once and never re-centres itself after that: the operator scrolled there on
  purpose, and a view that snaps back cannot be read.
- **No date under every column.** Under the chart the squares have no date row at
  all - the chart's date row is directly above them. The phone strip prints a
  sparse one: at 16px a track and 10px a label the dates overlap from about the
  fourth day, and an axis that cannot be read is decoration.
- **One threshold decides the red square, and CI owns it.** CI already reads a
  success floor to decide whether to open an issue. Two numbers answering one
  question drift, and then a red square and an open issue disagree.
- **A skipped item is not counted against a run's health.** An already-published
  article is skipped by design, and counting it would paint a healthy day amber
  for doing its job.

The figures are
[../../../frontend/src/lib/components/RunYield.svelte](../../../frontend/src/lib/components/RunYield.svelte)
and
[../../../frontend/src/lib/components/RunSquares.svelte](../../../frontend/src/lib/components/RunSquares.svelte);
the panel that joins them and prints the readout is
[../../../frontend/src/routes/console/RunHealthPanel.svelte](../../../frontend/src/routes/console/RunHealthPanel.svelte),
and what one run's square says is
[../../../frontend/src/lib/console/run-square.ts](../../../frontend/src/lib/console/run-square.ts).
[../../../frontend/tests/console-run-health.spec.ts](../../../frontend/tests/console-run-health.spec.ts)
checks manifest facts, square labels and the shared day-slot geometry.

## What is failing, by stage

One native panel draws failed-row counts as a daily stack and prints their share
of all recorded rows. It is not a failure-rate-against-volume chart.
[FailureMix.svelte](../../../frontend/src/lib/console/pipelines/FailureMix.svelte)
uses [nativeFailureMix](../../../frontend/src/lib/console/pipelines/failure-mix.ts)
over the declared item-health cells.

- **The divisor is all recorded rows in the returned window.** The numerator is
  rows whose outcome is `failed`. The query carries no article identity, so
  neither figure counts distinct articles. It infers no reached-stage population
  and applies no attempt floor to this share.
- **The stack keeps the returned calendar.** A recorded day with no failed row is
  a real zero. A day with no recorded row is unknown and stays null, not zero.
  The native rows do not establish whether anything was planned on that day.
  A clean recorded window says that no recorded row failed; an empty one supplies
  no failure divisor. Waiting and failed reads retain their reserved states.
- **Every failed stage is conserved.** Fetch, extract and summarize have named
  bands. Failed rows at any other stage form `Other stages`; they are not dropped
  to make the three named bands add up.
- **Rule rankings are separate, identity-free readings.** Stage radios rank the
  chosen stage's failed rows from `failedRuleQuery`. Each printed rule count is
  out of that stage's failed rows; unnamed rules are counted separately.
  The configured rule cap has a tail count, not article or source details. The mix and
  rule ranking keep independent loading, failure and returned-window states.
- **No stage glyph beside the stage name.** The icon set is one generated module
  that reaches every route, so three stage marks would move six reader routes
  that cannot show this section at all. An icon that needs a caption is a label
  wearing a costume, and the stage name is already in the cell.
- **No `run.success_floor_pct` reference line.** That floor is a published rate
  over attempted items and a stage panel is a different denominator. A wrong
  reference line is worse than none.

## Where an item's time went

[ItemTimeSplit.svelte](../../../frontend/src/lib/console/pipelines/ItemTimeSplit.svelte)
draws one mean per returned UTC day from
[nativeTimeSplit](../../../frontend/src/lib/console/pipelines/item-time-split.ts).
Only complete, reconciling clocks enter the cohort: fetch, extract, summarize,
faithfulness, elapsed time and the signed stage gap must all be recorded.
The four stage durations plus that gap must equal elapsed time.

Summarize is counted once. Label, summary and visual-plan clocks are
non-additive details; each keeps its recorded count and remains unknown unless
every clock in the cohort records that detail. Missing, invalid and inconsistent
rows have separate exclusion counts.

Positive gaps supply unattributed duration; negative gaps supply an adjacent
overlap deduction. Their means are taken separately so cancellation cannot hide
overlap. The positive stack minus the deduction equals the elapsed-time marker.
There is no negative stage band. A day with no qualifying clock keeps its place
as null, even if some individual stages were timed. With no complete cohort the
panel says so; it makes no claim about planned work. Before the query settles it
holds its reserved state.

## Time per item, by stage

Stage timing medians read from the item-health ledger, not from the eval
ledger. The item-health ledger has one row per planned item, so it
can answer "is it getting slower" even when the scorer did not run; the eval
ledger owns faithfulness and scorer time for the scored subset, and never carried
these columns.

**The chart draws three stages, and `score_ms` is not one of them.** Every line
on it is something an item waits on - and the scorer reads a summary the model
has already finished, so nothing waits on it. A fourth line there would read as a
fourth constraint on the run. It is on the Summaries route instead, under `What
one summary cost`, beside the cost of writing the summary it checks. An empty
cell is one fewer item timed, never a zero. A zero is a reading: the stage
finished inside the clock's own resolution, so it counts as timed and draws as
an open dot on the baseline.

The axis, the three marks a missing number can take and the model-change rule
are [console-charts.md](console-charts.md)'s, so timing and throughput callers
draw them the same way.

**The Pipelines panels read native records through declared queries.** The
ledger door selects raw or compact files for the requested window. There is no
public telemetry or run-timeline mirror and no build-time timeline reader
([telemetry-series.md](telemetry-series.md),
[console-payloads.md](console-payloads.md)).

## What one item cost the model is two clocks, drawn apart

`What one item cost the model` is a native Pipelines panel with two
distributions and their paired per-token costs. It answers what a run total
cannot: how long the model spent on **one** article, split into the part it
spent reading and the part it spent writing.

Hardware compares independent server and item clocks at run or shard grain.
This panel instead reads the declared `itemCostQuery` cells from item-health for
the selected record window. Its owner is
[nativeItemCost](../../../frontend/src/lib/console/pipelines/item-cost.ts), drawn
by [ItemCost.svelte](../../../frontend/src/lib/console/pipelines/ItemCost.svelte).

### Reading and writing are two charts, and pooling them is refused

Reading and writing have independent clocks. Article length and reply length
can move them separately, so one pooled `model seconds` distribution would hide
which one moved. The lead names the writing median. The per-token comparison
uses each side's own complete clock/token pairs, not a fixed cost ratio or a
claim about a token saving on a particular article.

Both use **doubling bins** from
[series.ts](../../../frontend/src/lib/charts/series.ts), with a shared time domain
so the same duration has the same position. Reading uses finite, non-negative
`prefill_ms`; writing independently uses finite, non-negative `decode_ms`.
A measured zero belongs in the first bin. An absent clock is not a zero.
Each histogram applies `console.min_attempts_for_rate` to its own clock count
and states the count when it has too few readings.

### Prompt reuse belongs to Hardware, not a comparison note on ItemCost

The native Hardware panel draws the day's middle label-call held tokens and
summary-call fresh tokens. Its
[records.ts](../../../frontend/src/lib/console/machine/records.ts) helpers also
print each call's pooled held share over complete input/cache pairs, the
server's middle recorded share and that call's pair count. Label and summary
remain separate; absent cache counts do not become zero reuse.

A share alone cannot say that the cache got worse: it can fall because the
prompt got longer or because less text was held. The dated native readings and
their settings rule carry the comparison. ItemCost links to Hardware; it has no
middle-versus-maximum held-token note, first-call reuse verdict or cache-change
classifier. Per-call charging remains
[the model's contract](../summarize/throughput.md#each-call-is-charged-on-its-own-and-the-item-is-their-sum).

### Every denominator is its own

The two histogram cohorts and two per-token cohorts need not match. Reading's
per-token cost pairs a non-negative prefill clock with recorded input and cache
counts, where `input_tokens > cached_tokens >= 0`. It sums those clocks and
divides by their fresh tokens, `input_tokens - cached_tokens`. Writing independently
pairs a non-negative decode clock with positive output tokens and divides the
clock sum by the output-token sum. Each side prints its own pair count.

An empty cell stays empty. A mean that treats an absent instrument as a zero
turns an unmeasured call into an infinitely fast one. A recorded cache count of
zero can qualify for reading; an unknown cache count cannot. The panel counts
prompts with an input count but no cache count and says they are not treated as
read whole. The writing-to-reading cost ratio is unknown unless both rates exist
and the reading cost is positive.

### It follows the selected native record window

The browser requests `itemCostQuery` for the selected configured preset and
computes these answers from the returned rows. The common recorded endpoint,
query's returned range and request epoch govern this panel just as they govern
the other native windowed answers. There is no server-reduced ItemCost seed or
telemetry-month fallback.

Private published-count cards, run health, site cost, chart drawing and
extraction's published-day facts remain build-time inputs. Their own window and
snapshot rules do not become ItemCost's rules; the prerendered private marks
remain available without scripts.

## Extraction answers both questions, and labels which half is which

`Extraction` is a Pipelines panel in two halves, and it is the console's worked
example of a panel that serves *is it working* and *what is broken* at once
rather than choosing.

The **verdict half** counts distinct articles, found facts, non-prose articles
and contaminated articles from the native extraction slice. A ranked list
counts element classes and rows that would not re-slice. Separately, the
published-chart share comes from private day records. Recorded boolean flags
have their own source state and date range; neither a flag nor its false
default establishes which checker ran.

The **break half** is one private chart, `Whether the yield is falling`.
The panel plots one
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

## Design rationale

### The per-day chart and the run squares became one panel (2026-09-27)

They were two panels - `Items published against items planned` under the glance
cards, and `Run health` below it - answering one question, and they could
disagree with nothing on the page saying why. On 3 September the chart read 86
percent published, an ordinary day, while one of that day's five runs was red.
On 22 September it read 66 percent while all four runs were amber. Over 30 days
the squares were 124 runs: none green, 115 amber, 9 red. And the two figures'
columns did not line up, so reading down from a bar landed on the previous day.
Jony, Susan and Reader converged on one panel, chart first and squares under it,
on one geometry.

| Option | What the reader loses |
| --- | --- |
| Keep the two panels as shipped | Two panels answer one question and disagree with nothing saying why. |
| **One panel, chart first, squares under it** (chosen) | The chart's own note, and the verdict words beside each run; the caption and the counts carry both. |
| The chart replaces the squares | Which run failed. |
| The squares replace the chart | Delivered against planned, per day. |

Three smaller rulings came with it. The panel's span moved into its own
accessible label because it has no note to carry it (Jony, Susan, Reader). A
sparse window's coverage sentence closes the chart's caption, above the tint it
explains (Jony, Reader). And
the 8 px under the chart is measured from the chart's own edge - the date row is
the bottom of the drawing - so about 15 px of air sits between the date text and
the tallest stack (Jony, Susan).

## See also

- [console.md](console.md) - which panel is on which route, and which question it answers.
- [how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md) - the rest of Pipelines.
- [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) - the control these panels answer to.
- [../../concepts/console-design.md](../../concepts/console-design.md) - how a console figure is allowed to read.
- [run-timeline.md](run-timeline.md) - the ledger the run panel draws.
- [telemetry-series.md](telemetry-series.md) - the published projection and the grain of every figure.
- [console-payloads.md](console-payloads.md) - what the console fetches, and what it may never be served.
