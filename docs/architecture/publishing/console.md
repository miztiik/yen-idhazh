# Which console panel answers what

**Last Updated**: 2026-11-24

The console tells an operator what happened to the pipeline; the digest tells a
reader what happened in the world. This page owns the routes and panel placement.

## Rendering direction

- Panels over published Parquet ledgers fetch their declared columns and dates in the browser through `sliceOnce`. Their ledger values are not embedded in HTML.
- All console charts use native components and d3 helpers. ECharts, its option builders and its server-side SVG renderer are absent. Keep the shared sizing, readout and loading rules.
- Keep query and presentation logic shared across routes. A new panel must not add its own parser, data URL builder or independent interpretation of a recorded measurement.
- Design loading, empty, missing and failed states per panel. A failed request must not blank the route or hide usable content.

Private inputs remain build-time exceptions: Pipelines reads manifests, published
item facts and day metrics; Summaries keeps its retained cards, daily coherence
and bounded publication dates; Voices keeps the source census, source decisions and feed
inputs; Judgement keeps its published merge counts and hand marks. Those inputs
are not newly published by removing the chart engine. Hardware's page carries
configuration and words, then asks its three native ledgers in the browser.
Existing route shells remain prerendered; Operations uses a static app shell and Data explorer uses the fallback
document. New data panels follow browser-owned delivery, not these exceptions.

The detailed requirements are in [Telemetry Intent](../../concepts/telemetry-intent.md),
[how a console chart gets its data](../../concepts/console-design/how-a-console-chart-gets-its-data.md)
and [console-charts.md](console-charts.md). Static hosting remains; browser rendering
does not require a runtime backend.

## Where each rule lives

| Page | Owns |
| --- | --- |
| This page | The console's questions, routes and panel placement |
| [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) | Shared navigation, window control and on-demand source dates |
| [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) | The time-window control and declared exceptions |
| [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) | Run health, failures, stage costs and retained visual attempts |
| [how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md) | Chart-drawing outcomes and their retirement rule |
| [why-a-summary-was-doubted-and-what-the-checker-measures.md](why-a-summary-was-doubted-and-what-the-checker-measures.md) | Retained summary measurements and their data boundaries |
| [who-supplied-the-day-and-which-feeds-failed.md](who-supplied-the-day-and-which-feeds-failed.md) | Sources and feed failures |
| [console-machine.md](console-machine.md) | Hardware and whether performance figures are comparable |
| [console-truncation.md](console-truncation.md) | The effect of the article truncation cap across routes |
| [console-site-size.md](console-site-size.md) | Published-site growth and deploy limits |
| [console-charts.md](console-charts.md) | Shared chart geometry, interaction and missing-data marks |
| [console-payloads.md](console-payloads.md) | Current data delivery and its remaining migration work |
| [telemetry-series.md](telemetry-series.md) | What each measurement covers |
| [../../concepts/console-design.md](../../concepts/console-design.md) | Wording, ranking, colour and presentation |

## The console answers two questions, and every panel names which

**Is it working?** A status panel shows central values or counts across the
subsystems it covers. **What is broken?** A diagnostic panel shows the extreme
and the individual responsible within one subsystem. Its heading and content
must answer the same question.

Pipelines and Summaries open on a status summary before the detail it
qualifies; the other routes open on their first comparison.
Declare the question in `data-panel-question`. No repeated global verdict band
or cross-route metric sentence sits above those comparisons.

| Surface | Role |
| --- | --- |
| Pipelines glance cards | Route status over the selected window |
| Pipelines `Run health` | Published against planned, by day and run; the first panel below the glance cards |
| Remaining Pipelines panels | Stage failures and costs |
| Summaries, Judgement and Voices | Writing, judgement and source diagnostics below each route's summary |
| Hardware panels | Machine-specific constraints and failures |

Keep the first useful chart visible without making an operator scroll through
diagnostics before reaching the status that explains them. Figures must be
legible, tables must fit their container, and titles must use plain words.

## Console routes

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, and what did each stage cost? |
| `/console/operations/` | **Operations** | Which judges finished work, and what did Gardener write, defer or repair? |
| `/console/machine/` | **Hardware** | Which hardware ran the work, and how much did it vary? |
| `/console/model/` | **Summaries** | What was written, how long did it take, and what went wrong? |
| `/console/judgement/` | **Judgement** | Which stories did the day merge, and where is the merge line relative to pairs marked as separate stories? |
| `/console/voices/` | **Voices** | Who supplied the day, and how are feeds discounted? |
| `/console/data-explorer/` | **Data explorer** | What do the ledgers hold, and what does a question of my own return? |

**Operations and Data explorer draw in the browser.** Operations has its own
static entry shell so a direct visit returns HTTP 200. The shell contains no
chart or evidence; the browser reads the existing staged records. Data explorer
uses the shared fallback and fetches its registry, indexes and files after the
operator chooses a question. Operations is not a verdict in the saved Console band.

Feed and source panels belong to Voices, not Pipelines. Keep `/console/` as the
Pipelines address; renaming a label is not a reason to break an existing bookmark.
Shared navigation and window behavior follow their owning pages above.

Model read/write timing (`item-cost`) sits beside throughput on Summaries.
The whole-summary duration distribution (`write-cost`) sits after stage timings
on Pipelines. Moving a panel does not change its clocks or evidence endpoint:
item-cost uses item-health alone, while write-cost keeps the common item-health
and summary-quality-evals endpoint. Both retain item-health's own first-day
clamp and print their selected UTC bounds.

Summaries retains model-work cards, throughput, item cost, daily length cutoffs,
HHEM faithfulness with a note where its full-article reading differs, checking
cost and summary length. Its daily table retains coherence. Mixed reason
breakdowns and source doubt rankings have no panel, query or private aggregate.

### Each route owns its config, expectations and gate drivers

`config/console/<route>.json` owns that route's panel groups, judged ids and
route-only numeric knobs. Shared knobs remain in `config/appearance.json`.
The [appearance config page](../../concepts/config/appearance.md#console-surface)
defines the keys, validation and the single `__CONSOLE__` build-time value.
Only route files and the server config loader import its reader; shared panels
take config as props. The layout reads the active route's groups for jump links,
even when the route has no server load.

The browser suite checks one representative console journey and shared
layout, plus an independent telemetry-month failure/retry boundary.
Route-specific evidence and deterministic reader behavior belong in
their integration and contract tests. Do not create a browser case for every
panel, route, viewport, theme or evidence state. Keep design review on the
changed surface rather than turning the route inventory into a gate matrix.

Tests use named fixtures and the explicit retained-spec inventory, not a
repository walk. Adding a route does not require another browser driver,
expectation matrix or suite of presentation assertions.

### A label is not an address

Use **Summaries** for the output and **Hardware** for the machine. **Judgement**
names the activity, and **Voices** is the source route's chosen label. These
reader-facing names do not require route ids, paths or data keys to change.

### Every panel title is a noun phrase

Name the information shown, not the implementation: no trailing question mark
or opening auxiliary verb. `What`, `Which` and `How` are valid when they name
the content rather than ask a question. A grammatical title must still explain
what the operator learns; mechanism names alone are not enough.

Copy changes keep stable addresses. Summaries' retained section is
`Model figures by recorded day`, not a claim about live work today.

## Operations separates judging from data upkeep

[Operations](what-operations-draws.md) keeps Council completion and the
Gardener write calendar separate under the same UTC preset. Judge results stay
on Judgement, digest production stays on Pipelines, and resource measurements
stay on Hardware.

## Judgement draws the published merges and the holdout labels

The tab separates **Published grouping** and **Judge: Content Similarity**.
Published grouping has two full-width panels,
in this order:

- `merged-stories` counts the published `same_story_as` decisions. Daily columns
  count stories merged behind another; dots count the largest group, including
  its retained story. The merge share stays in words with its denominator.
- `holdout-margin`, titled `Pairs marked as separate stories`, compares the
  labelled scores with the merge line, which is `floor_min` in the committed
  config. The original labels came from a model, not a human review. The panel
  keeps the score-range strip for pairs marked one story and the margin. These
  are score comparisons, not a replay of the published grouping decisions shown
  in the first panel. See the
  [holdout drawing rule](../../concepts/console-design/the-rules-every-console-chart-obeys.md#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score).

Both panels span the full row, so the margin keeps its drawn width. The margin's
axis reaches `holdout_axis_below_line` score points below the merge line and
`holdout_axis_above_line` above it, both route knobs in
`config/console/judgement.json` that must be above zero; a pair beyond either
edge is drawn as a chip at that edge. The line is the current configuration,
not a record of the floor that grouped an older digest.

Both panels keep their build-time reads. The digest days are not published
ledgers. The holdout labels are in a ledger, `holdout-pairs` in the Data explorer,
but this page still reads their packed files at build time and does not fetch
them in the browser. `content-similarity-holdout.ts` stays under
`frontend/src/lib/server/`; the browser must not import it. Reads keep their
existing window and holdout-reach bounds. The browser changes the window over
those inlined results, without a fetch; only `merged-stories` follows it, because
the marks are read over their own reach.

The grouping panels distinguish absent records from successful empty reads.
The holdout carries its own coverage and shows available partial records
without claiming there were no marks on an unread day.

Under **Judge: Content Similarity**, one UTC digest picker leads three
full-width panels. Warnings below the picker identify an incomplete record.
The nightly Council record does not change what is merged:

- `judge-coverage` draws pairs drawn and returned. Agreed YES or NO, other
  returns and pairs that did not return are separate parts of the draw. The
  selected digest also names usable answers and what the reporting runners saw.
- `judge-score-ranges` puts agreement at the reporting cutoff and upper draw
  bound before the detailed counts in each drawn range. Both cutoffs are
  comparisons against the judge's agreed answers, not merge lines. One stacked
  column per score range shows agreed YES, agreed NO, other returns and pairs
  that did not return, with the drawn total printed above it. Gaps between
  ranges say **Not drawn**, not zero. When the labels or stacks cannot fit,
  compact rows keep the same counts and YES share among agreed YES/NO answers.
- `pair-score-drift` compares the full score mix with its saved baseline.
  The route config supplies the two PSI guides, inclusive at both ends of the
  Moderate band. A gap breaks the line. The rules of thumb do not send alerts
  or change a job.

Below the charts, **Selected digest details** identifies the Council run and
attempt when recorded. It shows the known-answer check and prior-fit
calibration apart from drift, so neither implies a PSI reading.

Both trends share the selected UTC digest with the score ranges and details.
Arrow keys inspect; Enter, click, tap or the date control changes the selection. The
browser asks the query door for named columns over the displayed window
intersected with packed `threshold-history` reach. For each date it keeps the
newest Council run and then the highest attempt. One selected-date query opens
only that exact reading. A packed period's end is not a run date. Legacy nulls,
unavailable measurements and dates not yet published are distinct from a
measured zero. Useful partial evidence stays visible.

The digest control shows the selected reading's recorded judge model. The
**Pairs drawn and returned** timeline uses the shared change divider and
readout on the first displayed UTC digest with a different recorded model.
It compares successive known identities from the newest attempt for each
digest. Missing identities, the first known reading and configuration edits
alone do not create a marker. A divider is where the change was observed in
the data, not a deployment time. Incoming score drift is measured before
judging, so it does not carry this divider.

Data explorer can query the packed `pair-verdicts` and
`threshold-history` rows, including metrics not drawn here. See the [nightly judge
flow](how-the-content-similarity-judge-follows-its-thresholds.md#what-threshold-history-stores)
for how those readings are produced.

### Content Similarity visual trial

The `judge_visual_trial_enabled` switch in `config/console/judgement.json`
adds the following views under the same UTC digest selection. It does not
change the published grouping, Council, data contracts, or the PSI trend.
Turning it off restores the standard views and skips the trial's queries.
Remove trial-only views and reads after the usage review unless chosen to stay.

- **Pairs drawn and returned:** The daily coverage bars share the trial's
  palette: cobalt is YES, cyan is NO, and berry is split or combined MAYBE.
  When split and agreed UNCLEAR are shown separately, UNCLEAR is orchid.
  Refusals, unclassified returns and missing returns are neutral, not MAYBE.
  The coverage and interval charts share one exact-attempt draw projection.
- **Answers by score range:** Each horizontal stack is 100% of the original
  draw in that band, with its exact draw count beside it. Agreed YES, NO,
  UNCLEAR, split, refused and unreturned are disjoint. An unsampled gap has
  no stack. The **draw ranges and bounds by date** plot uses actual saved
  intervals and count-scaled composition ticks. The stepped lines show
  bounds in force; open diamonds mark changes decided after a draw. The
  signed scale keeps every interval, compressing scores below the lowest
  shown lower bound into the configured `judge_visual_trial_context_share`
  of the plot when that expands the range of interest. A scale mark labels
  that transition. Exact slice counts and fit support are compact tables.
- **Verdict and entropy heatmaps:** Date and fixed score band locate
  separate YES, NO and split percentages over all recorded pair rows.
  Entropy instead uses only two valid orders per pair, with MAYBE grouping
  split and agreed UNCLEAR. A single populated outcome, including MAYBE,
  gives zero bits; equal thirds give `log2(3)` bits. Its violet-to-amber
  scale measures entropy, not verdict identity. Show support and
  distinguish zero from no evidence. Changes in the mix or in recorded
  settings are not proof of judge drift. Negative scores occupy an underflow
  band in these heatmaps.
- **Score zone matrix and precision vs recall:** The matrix crosses agreed
  judge outcomes (MAYBE also includes split) with the three pipeline score
  zones from the saved draw bounds. It excludes refusals and prints counts
  and row shares. The scatter is for one selected digest, not a time trend.
  It uses equally scored agreed YES/NO pairs together, and marks the lower
  and upper draw bounds, reporting cutoff and saved 90% recall point with
  filled shapes. Neither view measures accuracy against human labels.
- **Full score pool and PSI:** The histogram uses the stored full-pool
  score bins, not records of what the judge was sent. It can draw without a
  reference. An outline compares the saved reference only when all of its
  named histograms are present and verify; the stored PSI point and its
  availability reason are independent of whether the overlay can be drawn.
- **Canaries:** Three timelines, one per saved expected answer (YES, UNCLEAR,
  NO), align a 0%-100% match line above daily blocks. Each block uses that
  digest attempt's saved expected pairs as its denominator. Agreed YES is
  above UNCLEAR and NO is at the bottom; changed, invalid and missing replies
  have separate bands. Both replies must match the saved answer to count as a
  match. Invalid or missing replies yield open points outside the connected
  line, not ordinary zeroes. A missing saved key leaves a gap. The line
  connects only adjacent complete digests with the same recorded canary-set
  version; dashed dividers mark version changes. Selected-day details show
  the counts and each pair's expected, original and reversed answers. Counts
  and kappa use the saved agent-labelled key, not human truth. The existing
  bounded threshold-history projection supplies the evidence without a
  separate canary read.

The trial reads named staged columns through the same [panel door](how-the-query-door-answers-a-panel.md).
The heavier pair projection starts near the view, is capped at the configured
default window, and is shared by the heatmaps and selected-day score
comparisons. A selected date outside its cap may read just that date.
Every pair must match the selected aggregate's date, run and attempt.
Pair analytics cannot infer missing draw counts, and the histogram does
not fetch outside its bounded reference window.

## Design rationale

One chart library is enough once each route draws through native components.
Retain shared arithmetic and types where a real component imports them; remove
engine options and file readers whose last production caller has gone. A
column's ownership must move to its live query or native reader, never to a
deleted facade. Unread persisted cells stay explicitly named rather than being
silently dropped. Shared knobs follow the same production-reader audit, as
[appearance configuration](../../concepts/config/appearance.md#console-surface)
defines. This changes neither native ledger shapes nor private publication.

The host registry distinguishes recorded metadata from cells selected by a live
console query. Item `n_threads`, `n_batch`, `shard_item_count`,
`cpu_busy_max`, `cpu_busy_min` and `load_1m` remain recorded in `UNREAD_CELLS`.
No current item query selects the last four. A column list, normalization or
unused counter field is not an answer that reads a cell. Schema versions,
writers and historical normalizers do not change for an ownership-only edit.

Judgement's standard nightly panels read the filed aggregate. The separate
visual trial uses bounded pair projections only where per-pair scores or
both verdicts are needed; it never replaces the filed draw totals.
Published grouping is independent: it reads committed outcomes and compares
holdout labels with the current `floor_min`, not with a nightly draw bound
or the recorded floor of an older run.

Judgement's score ranges are ordered categories, not a continuous score axis.
a line would imply readings between differently sized slices. The default
count scale preserves sample size in the bar length; the trial's percentage
scale preserves it as a count beside each bar.

| Alternative | Why not |
| --- | --- |
| Prerender new panels or calculate their telemetry in a server loader | Conflicts with browser-owned loading and drawing in Telemetry Intent |
| Give every panel its own data reader or drawing conventions | Creates competing meanings and duplicates the work needed to change a shared contract |
| Pick fallback server widths per chart | New charts measure their browser container; a guessed build-time width is not their layout |
| Rename paths whenever display labels change | Breaks bookmarks without changing the question a route answers |
| Treat a missing record as a zero or as agreement | Claims a result that was never measured |
| Redraw the retired line panels on the new ledgers | Describes a threshold the site does not apply, and the Data explorer already answers questions about the new ledgers |

## See also

- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - the intended data and rendering model.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shared frame, page states and rendering policy.
- [../../concepts/console-design.md](../../concepts/console-design.md) - presentation requirements for operators.
- [console-charts.md](console-charts.md) - the shared chart rules.
- [frontend.md](frontend.md) - the reader-facing site alongside the console.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - selected checks and browser verification.
