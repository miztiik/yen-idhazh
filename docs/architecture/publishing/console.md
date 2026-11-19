# Which console panel answers what

**Last Updated**: 2026-11-19

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
Route shells remain prerendered; Data explorer retains its existing fallback
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

## The console is six routes

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, and what did each stage cost? |
| `/console/model/` | **Summaries** | What was written, how long did it take, and what went wrong? |
| `/console/machine/` | **Hardware** | Which hardware ran the work, and how much did it vary? |
| `/console/judgement/` | **Judgement** | Which stories did the day merge, and how close does the merge line sit to pairs a person marked apart? |
| `/console/voices/` | **Voices** | Who supplied the day, and how are feeds discounted? |
| `/console/data-explorer/` | **Data explorer** | What do the ledgers hold, and what does a question of my own return? |

**Data explorer is live.** It is the one console route that prerenders no document of its own: GitHub Pages serves the fallback document, then the browser fetches the registry, indexes and files after the operator chooses a question. The old `console.data_explorer_tab` flag is gone because a tab no longer points at a missing page.

Feed and source panels belong to Voices, not Pipelines. Keep `/console/` as the
Pipelines address; renaming a label is not a reason to break an existing bookmark.
Shared navigation and window behavior follow their owning pages above.

Model read/write timing (`item-cost`) sits beside throughput on Summaries.
The whole-summary duration distribution (`write-cost`) sits after stage timings
on Pipelines. Moving a panel does not change its clocks or evidence endpoint:
item-cost uses item-health alone, while write-cost keeps the common item-health
and summary-quality-evals endpoint. Both retain item-health's own first-day
clamp and print their selected UTC bounds.

Summaries retains model-work cards, throughput, item cost, call endings,
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

### Every panel title on the five routes is a noun phrase

Name the information shown, not the implementation: no trailing question mark
or opening auxiliary verb. `What`, `Which` and `How` are valid when they name
the content rather than ask a question. A grammatical title must still explain
what the operator learns; mechanism names alone are not enough.

Copy changes keep stable addresses. Summaries' retained section is
`Model figures by recorded day`, not a claim about live work today.

## Judgement draws the published merges and the hand marks

The tab says: `Which stories the day merged, and how close the merge line sits to
pairs a person marked apart.` Two panels form one untitled group, in this order:

- `merged-stories` counts the published `same_story_as` decisions. Daily columns
  count stories merged behind another; dots count the largest group, including
  its retained story. The merge share stays in words with its denominator.
- `holdout-margin`, titled `The pairs a person marked apart`, compares each pair
  a person marked apart with the merge line, which is `floor_min` in the
  committed config. It keeps the score-range strip for pairs marked one story and
  the margin. See the
  [holdout drawing rule](../../concepts/console-design/the-rules-every-console-chart-obeys.md#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score).

Both panels span the full row, so the margin keeps its drawn width. The margin's
axis reaches `holdout_axis_below_line` score points below the merge line and
`holdout_axis_above_line` above it, both route knobs in
`config/console/judgement.json` that must be above zero; a pair beyond either
edge is drawn as a chip at that edge. A note under
the window control says where the judge's own records are read: `pair-verdicts`
and `threshold-history` are Data explorer ledgers, and the note links to that
route using the address in the shared route table. It also says they do not
change what the site merges.

Both panels keep their build-time reads. The digest days and the hand marks are
not published ledgers. `content-similarity-holdout.ts` stays under
`frontend/src/lib/server/`; the browser must not import it. Reads keep their
existing window and holdout-reach bounds. The browser changes the window over
those inlined results, without a fetch; only `merged-stories` follows it, because
the marks are read over their own reach.

Each panel has a stable id, one leading figure or sentence, a visible comparison,
a named question, a chart type, and a readout declaration. Each declines the
summary-settings rule because it draws published merges or the merge line against
hand marks, not how summaries are written. Both are in the route's `judged` list.

The component boundary keeps absent evidence as `null` and supplied empty
evidence as an empty array or a zero-count record. Missing evidence prints an
unavailable sentence without measured zeros. Hand-mark rows retain their
existing `RecordRead` alongside the rows, and the derived holdout marks keep the
same mark read. The page carries each read once with its mark reach. Successful
empty results say no rows were returned, not that nobody marked a pair. Required
blank measurements are not converted to zero.

Unavailable windowed panels still name the selected span. Geometry checks use
the existing private route builder's real populated or successful-empty records;
missing-source checks remain separate. A missing plot fails a geometry assertion,
not a reason to skip it. The shared canary is not filled with invented judge data.

Useful partial rows remain visible. Lost-day notes are narrowed to the displayed
span. Set-aside counts describe the loaded input, not a newly inferred count for
the preset. `lastRows` is a packed period, never an exact last execution date.
Unreadable diagnostics are not rendered as paths, links or markup. Real generated
ledger and route tests cover these distinctions without a fabricated fetch,
another archive read or another state vocabulary.

The old per-article desk and lens heading and its named absence are removed.
These panels do not promise classification evidence they cannot show.

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

Judgement draws no panel from the judge's own ledgers. `pair-verdicts` and
`threshold-history` are Data explorer ledgers, so the page names where to read
them instead of drawing them, and it carries no hand-copied column list for
contracts no ordinary panel reads. The hand-marks panel stays because it needs
neither ledger: it reads the marks and the merge line the site applies. That
line is the committed `floor_min`, read from config rather than from the newest
run record, because the run record only restates the same number and a second
reader of one value is a second answer. Authority: Jony, Fowler, 2026-11-19.

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
