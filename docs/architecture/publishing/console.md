# Which console panel answers what

**Last Updated**: 2026-10-09

**Known noncompliance:** Existing console prerendering does not meet [Telemetry Intent](../../concepts/telemetry-intent.md) and will be migrated to browser rendering. All new designs, charts and visuals must render in the browser; none may be prerendered.

The console tells an operator what happened to the pipeline; the digest tells a
reader what happened in the world. This page owns the routes and panel placement.
It states the forward rendering rules without claiming the migration is complete.

## Rendering direction

- Fetch the current view's data in the browser through the shared reader. Request only the required columns and dates; do not embed telemetry in HTML or depend on a route's server loader.
- Use d3.js for new charts and the shared sizing, readout and loading rules. Existing prerendered charts and older chart engines are migration work, not templates for new panels.
- Keep query and presentation logic shared across routes. A new panel must not add its own parser, data URL builder or independent interpretation of a recorded measurement.
- Design loading, empty, missing and failed states per panel. A failed request must not blank the route or hide usable content.

The detailed requirements are in [Telemetry Intent](../../concepts/telemetry-intent.md),
[how a console chart gets its data](../../concepts/console-design/how-a-console-chart-gets-its-data.md)
and [console-charts.md](console-charts.md). Static hosting remains; browser rendering
does not require a runtime backend.

## Where each rule lives

| Page | Owns |
| --- | --- |
| This page | The console's questions, routes and panel placement |
| [what-sits-above-every-console-route.md](what-sits-above-every-console-route.md) | Shared navigation and the standing status band |
| [which-console-surfaces-follow-the-window-and-which-say-why-not.md](which-console-surfaces-follow-the-window-and-which-say-why-not.md) | The time-window control and declared exceptions |
| [what-the-pipelines-route-draws.md](what-the-pipelines-route-draws.md) | Run health, failures, stage costs and extraction |
| [how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md](how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md) | Chart-drawing outcomes and their retirement rule |
| [why-a-summary-was-doubted-and-what-the-checker-measures.md](why-a-summary-was-doubted-and-what-the-checker-measures.md) | Summary doubt reasons and checker measurements |
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

Every route starts with its own status summary before the detail it qualifies.
Declare the question in `data-panel-question`. The standing band covers all six
routes, but does not replace their own summaries.

| Surface | Role |
| --- | --- |
| Standing band | Pipeline-wide status, shared by all routes |
| Pipelines glance cards | Route status over the selected window |
| Pipelines `Run health` | Published against planned, by day and run; the first panel below the glance cards |
| Remaining Pipelines panels | Stage failures and costs |
| Summaries, Judgement and Voices | Writing, judgement and source diagnostics below each route's summary |
| Hardware `Whether the speed numbers can be trusted` | Whether the rates are comparable; the first panel on the route |
| Remaining Hardware panels | Machine-specific constraints and failures |

Keep the first useful chart visible without making an operator scroll through
diagnostics before reaching the status that explains them. Figures must be
legible, tables must fit their container, and titles must use plain words.

## The console is six routes

| Path | Label | What it answers |
| --- | --- | --- |
| `/console/` | **Pipelines** | Did the runs work, and what did each stage cost? |
| `/console/model/` | **Summaries** | What was written, how long did it take, and what went wrong? |
| `/console/machine/` | **Hardware** | Which hardware ran the work, and how much did it vary? |
| `/console/judgement/` | **Judgement** | What decisions were made about articles, and where did evaluation disagree? |
| `/console/voices/` | **Voices** | Who supplied the day, and how are feeds discounted? |
| `/console/data-explorer/` | **Data explorer** | What do the ledgers hold, and what does a question of my own return? |

**Data explorer is live.** It is the one console route that prerenders no document of its own: GitHub Pages serves the fallback document, then the browser fetches the registry, indexes and files after the operator chooses a question. The old `console.data_explorer_tab` flag is gone because a tab no longer points at a missing page.

Feed and source panels belong to Voices, not Pipelines. Keep `/console/` as the
Pipelines address; renaming a label is not a reason to break an existing bookmark.
Shared navigation and window behavior follow their owning pages above.

### Each route owns its config, expectations and gate drivers

`config/console/<route>.json` owns that route's panel groups, judged ids and
route-only numeric knobs. Shared knobs remain in `config/appearance.json`.
The [appearance config page](../../concepts/config/appearance.md#console-surface)
defines the keys, validation and the single `__CONSOLE__` build-time value.
Only route files and the server config loader import its reader; shared panels
take config as props. The layout reads the active route's groups for jump links,
even when the route has no server load.

A cross-route spec keeps its typed-out expectations under
`frontend/tests/support/console-expect/<spec>/<route>.ts`. Each file exports
`EXPECT`, or `null` when that route has nothing to check. The spec skips null
entries. Its `index.ts` declares `BY_ROUTE` as a record keyed by `RouteId`, so a
new route requires an entry at type check. An expectation file reads no values
from config or the band: it records what the page must show, not what the page
already uses. A chart-lifetime or chart-pending expectation is null when the
route draws no legacy `Chart.svelte`.

The shared window spec owns arithmetic, controls, declared surface coverage,
daily disclosure rules and actual cross-route navigation. It generates route
coverage from the exhaustive `BY_ROUTE` literals. An absent expected surface
fails; an explicit null remains inapplicable. Detailed telemetry, judge,
Hardware and Voices fixtures and execution belong to focused route window
specs. Agreement readouts, marks, day labels and cumulative record bars answer
separate questions. Expectation files contain typed data, not callbacks.
The shared navigation check may use Hardware's small content-span observer;
it does not own Hardware fixtures or component compilation.
The ownership guard checks this execution boundary as well as quoted addresses.

Each `frontend/tests/support/panel-drivers/<route>.ts` exports `DRIVERS` and
`BUILD_TIME`. Drivers put fetched panels into the states declared by
`Nothing` in `panel-gates.ts`. `BUILD_TIME` names judged panels that make no
fetch; their route's component specs check empty and absent inputs through
`judgeNothings` for `quiet` and `missing`. The sufficiency spec refuses an id
in both lists, in neither list, or driven by two routes. The driver index joins
the route records without owning an address.

The capture and sufficiency route lists come from `RouteId`, with addresses
from `BAND_UNREAD.routes`. Empty panel groups have nothing to capture. The
sufficiency tests cover the declared widths and both themes, with one page
load for static gates and separate state-driving tests. They read inputs
inside tests, not at module load.

`frontend/tests/console-route-scope.spec.ts` checks explicit named files, not a
repository walk. A quoted literal equal to one of the six band hrefs names that
route. A route expectation or driver may name only its own route. Their indexes
and the seventeen cross-route spec bodies name no addresses. Other named specs
may name at most one route, except `console-machine-page.spec.ts`, whose built
page checks belong to Hardware. The same guard refuses define use outside its
three owners and direct reader imports outside the loader or route files.
New consumers must join its named input inventory.

### A label is not an address

Use **Summaries** for the output and **Hardware** for the machine. **Judgement**
names the activity, and **Voices** is the source route's chosen label. These
reader-facing names do not require route ids, paths or data keys to change.

### Every panel title on the five routes is a noun phrase

Name the information shown, not the implementation: no trailing question mark
or opening auxiliary verb. `What`, `Which` and `How` are valid when they name
the content rather than ask a question. A grammatical title must still explain
what the operator learns; mechanism names alone are not enough.

Preserve protected copy such as `What the model did` on Summaries. The
[title checks](../../../frontend/tests/console-title.spec.ts) and
[summary-page checks](../../../frontend/tests/console-model.spec.ts) hold labels
and stable addresses together. An approved copy change updates both.

## Judgement distinguishes published merges from judging evidence

The tab says: `Which stories the day merged, and where the judge and a person
disagreed.` Six panels form one untitled group, in this order:

- `merged-stories` counts the published `same_story_as` decisions. Daily columns
  count stories merged behind another; dots count the largest group, including
  its retained story. The merge share stays in words with its denominator.
- `merge-line` compares each nightly calculated line with its proposal. The
  recorded line the newest day used is a separate fact. Neither a calculation
  nor a pair above a threshold proves a published merge.
- `judge-agreement` compares the judge's first reading with its own second
  reading, with the summaries swapped. Disagreement and uncertainty keep their
  own denominators and limits. A day below the reporting floor keeps its counts
  but draws no rate dot.
- `record-gates` compares each recorded count with the count needed to fit a
  line. Its day strip keeps days without rows. Missing counts are not zero bars.
- `verdict-split` separates pairs called one story from pairs called two stories,
  on each side of the merge line. Its cells say eligible, not merged.
- `holdout-margin` compares pairs a person marked apart with the merge line.
  It keeps the score-range strip for pairs marked one story, the margin, and
  the separate committed scoring result. See the
  [holdout drawing rule](../../concepts/console-design/the-rules-every-console-chart-obeys.md#the-holdout-margin-is-drawn-at-the-scale-of-the-margin-not-of-the-score).

All six keep their build-time reads. The digest days and the content-similarity
judge's records are not published ledgers. `content-similarity-judge.ts` and
`content-similarity-holdout.ts` stay under `frontend/src/lib/server/`; the browser
must not import them. Reads keep their existing window and holdout-reach bounds.
The browser changes the window over those inlined results, without a fetch.

Each panel has a stable id, one leading figure or sentence, a visible comparison,
a named question, a chart type, and a readout declaration. Each declines the
summary-settings rule because it draws the judge's record, not how summaries
are written. All six are judged and listed in the route's `BUILD_TIME`.

The component boundary keeps absent evidence as `null` and supplied empty
evidence as an empty array or a zero-count record. Missing evidence prints an
unavailable sentence without measured zeros. The existing readers do not always
distinguish an absent dataset from an empty query result; those results say no
rows were returned, not that no run happened. The component-state test renders
both inputs through the real components and judges their different words,
without a fabricated fetch.

The old per-article desk and lens heading and its named absence are removed.
These panels do not promise classification evidence they cannot show.

## Design rationale

Judgement keeps its existing questions and drawings. The agreement chart has
no human verdict input, so calling it agreement with a person would mislabel
evidence. Its leading disagreement share and comparison describe the two real
readings; the hand-marked comparison remains in `holdout-margin`. Likewise, the
merge-line drawing receives calculated lines, not individual pair scores, so
its leading figure is the newest calculated line, not an invented pair count.
These limits preserve the drawings without presenting absent evidence as fact.

| Alternative | Why not |
| --- | --- |
| Prerender new panels or calculate their telemetry in a server loader | Conflicts with browser-owned loading and drawing in Telemetry Intent |
| Give every panel its own data reader or drawing conventions | Creates competing meanings and duplicates the work needed to change a shared contract |
| Pick fallback server widths per chart | New charts measure their browser container; a guessed build-time width is not their layout |
| Rename paths whenever display labels change | Breaks bookmarks without changing the question a route answers |
| Treat a missing record as a zero or as agreement | Claims a result that was never measured |

## See also

- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - the intended data and rendering model.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - the shared frame, page states and no-prerender policy.
- [../../concepts/console-design.md](../../concepts/console-design.md) - presentation requirements for operators.
- [console-charts.md](console-charts.md) - the shared chart rules.
- [frontend.md](frontend.md) - the reader-facing site alongside the console.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - selected checks and browser verification.
