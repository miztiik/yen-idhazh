# Console chart craft - one axis, one hover, one colour rule

**Last Updated**: 2026-08-31
**Level**: 4 (structural, 4+ files, across all three console routes)

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The console's three routes each grew their own axis, hover, legend and colour habits, so a reader learns the page three times and several panels are unreadable on a phone. |
| Hard scope - in | The three prerendered routes `/console/`, `/console/model/`, `/console/machine/`; the shared chart primitives under `frontend/src/lib/charts/`; the console components under `frontend/src/lib/components/`; the tunable knobs in `config/appearance.json` and `config/idhazh.json`; the browser suite under `frontend/tests/`. |
| Hard scope - out | Reader-facing routes (`/`, `/<date>/`, `/archive/`); any pipeline stage; any persisted backend contract, unless a row names one explicitly and clears its ESCALATE trigger; new source data; any new chart type in `frontend/src/lib/charts/core.ts`. |
| ESCALATE triggers | (a) any row that needs a field the committed ledgers do not carry - stop, do not widen a contract to draw a chart; (b) any row that would register a new echarts type, because the lazy chart chunk measured 197,561 gzipped B against its own 200,000 B line; (c) any row whose built route crosses its `page_weight.ceilings_bytes` entry and cannot be brought back under it by deleting markup; (d) Row #5's second rename, which is unresolved (section 2, Row #5 decision 2). |
| Chosen strategy | Fix the shared primitive once and let every chart inherit it, before touching a single panel. Rows #1-#4 are the primitives; every later row is cheaper because they landed. Ruled by Jony (what survives) with Susan holding the sufficiency veto on Rows #7, #8, #17 and #19. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3. |

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

### Measured at 8c0b82c, 2026-08-31, node 24.12.0, 1440x1000 and 390x844

| Route | Window control | Charts drawn | Charts with a hover readout | Page height desktop | Page height phone |
| --- | --- | --- | --- | --- | --- |
| `/console/` | yes, 7/14/30/90 | 24 | 4 | 10,484 px | 16,385 px |
| `/console/model/` | yes, 7/14/30/90 | 17 | 3 | 3,818 px | 6,650 px |
| `/console/machine/` | **none** | 7 | 3 | 5,038 px | 9,219 px |

Zero console errors and zero 4xx on all six loads. The window choice is already shared across routes through the `idhazh:console-window` localStorage key, so a preset picked on one route holds on the next; the Machine route is the only one that cannot set it.

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | One date axis for every chart | - | A | PENDING | - | - | - |
| 2 | Hover readout is the default, and it replaces the legend | - | A | PENDING | - | - | - |
| 3 | The model-change rule, on every chart it means something on | 1 | B | PENDING | - | - | - |
| 4 | Semantic movement colour, direction-aware, both themes | - | A | PENDING | - | - | - |
| 5 | Route labels and panel titles read alike | - | A | PENDING | - | - | - |
| 6 | The Machine route joins the shared window | - | B | PENDING | - | - | - |
| 7 | Failed items become sources ranked by articles lost | 2 | C | PENDING | - | - | - |
| 8 | Feeds gain their denominator, and the failure list gains a cap | - | C | PENDING | - | - | - |
| 9 | Sources cut short fills its frame | 1 | C | PENDING | - | - | - |
| 10 | Articles published, beside charts published | 4 | C | PENDING | - | - | - |
| 11 | Run health gains a readout and loses its dead margin | 1, 2 | C | PENDING | - | - | - |
| 12 | A chart never draws a span nothing measured | 1 | C | PENDING | - | - | - |
| 13 | The chart-arm flow survives a phone | - | C | PENDING | - | - | - |
| 14 | Every daily-figures disclosure states its window | 6 | D | PENDING | - | - | - |
| 15 | Which sources the checker doubts | 2 | D | PENDING | - | - | - |
| 16 | What one summary cost becomes a chart | 1, 2 | D | PENDING | - | - | - |
| 17 | The model-change panel earns the width it takes | 4 | D | PENDING | - | - | - |
| 18 | The shard board survives a phone | - | D | PENDING | - | - | - |
| 19 | Context headroom becomes one chart | 1, 2, 6 | E | PENDING | - | - | - |
| 20 | Peak memory, per shard and in one number | 2, 6 | E | PENDING | - | - | - |
| 21 | Run latency, one chart per percentile and one across them | 1, 2, 6 | E | PENDING | - | - | - |
| 22 | Closure - distil, re-derive the ceilings, delete the plan | 1-21 | F | PENDING | - | - | - |

## 2 - Rows

### Row #1 - One date axis for every chart

- **Scope:** Every chart on the three console routes labels its date axis through one helper, with a thinning rule that cannot overlap at any width, and no label may be clipped by the frame.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/src/lib/charts/run-history.ts`
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - `frontend/src/lib/components/BandDistance.svelte`
  - `frontend/src/lib/components/SourceCutRange.svelte`
  - `frontend/src/lib/components/RunLengths.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `config/appearance.json`
  - `frontend/src/lib/server/config.ts`
  - `frontend/tests/console-axis.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check` 0/0; `npm run build`; `npm run bundle-gate`; browser suite green; section-12 smoke at 1440 and 390 on all three routes; every route under its `page_weight.ceilings_bytes` entry.
- **Oracle:** In a real browser at 1440, 768 and 390, for every `svg` on the three routes, collect the bounding boxes of every date-axis `text` node and assert (a) no two boxes on one axis overlap horizontally, and (b) every box sits inside its own `svg`'s box. Bite-proof it by setting `chart.tick_density` high enough to force a collision and watching the test fail.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `dayTicks` in `frame.ts` is the one helper. `axisLabels` in `run-history.ts` becomes a caller of it rather than a second rule. | Fowler |
| 2 | The thinning rule is measured, not counted: the helper takes the plot width and the widest label's advance and drops labels until they fit, with the first and last day always kept. A fixed `tick_density` cannot hold at both 1440 and 390. | Jony |
| 3 | `chart.tick_density` stays in `config/appearance.json` as the CEILING on labels, never the target. Its existing mirror in `frontend/src/lib/server/config.ts` is unchanged, so `test_contracts.py` still passes. | CLAUDE.md Rule #6 |
| 4 | A dropped label leaves its tick mark. A reader counting columns needs the grid even where the date is gone. | Jony |
| 5 | The right-most label anchors `end` and the left-most `start`, which `dayTicks` already does; `SourceCutRange`'s value axis must do the same - its `10,000` currently renders clipped as `10,00` at 1440. | measured 2026-08-31 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rotate the labels 45 or 90 degrees | Vertical type is slower to read than fewer horizontal labels, it forces bottom margin on every chart on the page to pay for the worst one, and the console already has a thinning rule that works - it is just not applied everywhere. | Jony |
| 2 | Alternate labels on two rows | Doubles the bottom margin on every chart to buy labels a thinning rule gives free, and two rows of dates read as two series. | Jony |
| 3 | Leave `run-history.ts` with its own rule | It is the rule that draws only two labels on a thirty-day strip, which is the defect. Two helpers is how they drifted. | Fowler |

### Row #2 - Hover readout is the default, and it replaces the legend

- **Scope:** Every console chart with a shared column carries `ChartReadout` and pointer, keyboard and touch selection; the standing legend under any chart that gains one is deleted, because the readout already prints the swatch and the label.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/src/lib/components/ChartReadout.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/lib/components/SourceCutRange.svelte`
  - `frontend/src/lib/components/TargetBar.svelte`
  - `frontend/src/lib/components/ShardBoard.svelte`
  - `frontend/tests/console-readout.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** as Row #1, plus the readout must work from the keyboard (Left, Right, Escape) on every chart that gains one, and the prerendered resting column must be in the document with script off.
- **Oracle:** Enumerate every `svg` on the three routes. Partition it into "has a shared column" and "does not" by a declared `data-readout-columns` attribute the component sets. Assert every chart in the first partition resolves a `[data-readout]` strip, that hovering column 0 and the last column prints two different `[data-readout-day]` values, and that no chart in the first partition also renders a static legend element. The second partition must be non-empty and each member must name why in a `data-readout-none` reason string, so "no hover" is always a stated decision and never an omission.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The readout is the legend. One implementation, `ChartReadout`, already states this; the row makes it true everywhere rather than in seven of twenty-four places. | Jony |
| 2 | A chart with no shared column - a ranked list, a single target bar - gets no readout and must say so in `data-readout-none`. A tooltip on a list is a tooltip on a fact already in type. | Susan |
| 3 | The resting column stays prerendered. The hover is an addition; the numbers are readable with no script. | CLAUDE.md Rule #1 |
| 4 | Touch counts. `pointerReadout` binds pointer events, so a tap already selects a column; the row asserts it rather than assuming it. | Reader |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A floating tooltip that follows the cursor | It covers the mark it describes, it cannot be reached from a keyboard, and it prints nothing with script off. The strip below the plot was chosen for those three reasons and the reasons have not changed. | Jony |
| 2 | Keep the legends and add the readout | One fact drawn twice is how two of them drift, and a legend under every chart is most of the vertical space a phone spends on this page. | Susan |
| 3 | A readout on every chart including the ranked lists | A ranked list has no shared column to bind to, so the strip would print the row the cursor is already on. | Susan |

### Row #3 - The model-change rule, on every chart it means something on

- **Scope:** Every windowed chart whose y value can move when the summarizer changes draws the model-change boundary as a dashed rule with a hover line in the readout; charts the change cannot move draw nothing.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/components/BandDistance.svelte`
  - `frontend/src/lib/components/WriteTimeHistogram.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/tests/console-model-rule.spec.ts` (new)
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1. The rule must not draw where the window holds no boundary, and the empty case must be a named state and not a missing element.
- **Oracle:** Derive the boundary dates from `state/scores.csv`'s `pipeline_fingerprint` transitions, independently of the component. For each windowed chart declaring `data-model-rule="yes"`, assert the count of `[data-model-rule-line]` equals the count of boundaries inside that chart's own drawn span - not inside the window, because a chart can draw fewer days than the window. Bite-proof by building with `STATE_ROOT` pointed at a copy whose fingerprints never change: every rule must disappear and every chart must still draw.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The boundary set is derived once on the server from `pipeline_fingerprint` and passed down, never re-derived per component. `ThroughputTrend` already reads every boundary in the window and is the precedent. | Fowler |
| 2 | "Meaningful" is decided per chart and written into the component, not inferred. A chart of prompt tokens a second is moved by a model change; a chart of feed outcomes is not. | Andre |
| 3 | The rule is dashed, in the neutral rule colour, never in the health ramp. A model change is an event, not a verdict. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Draw the rule on every chart | On a feed-outcome strip it asserts a relationship that does not exist, and a marker that means nothing on half the page trains a reader to ignore it. | Andre |
| 2 | Only ever draw the newest boundary | A ninety-day window can hold two, and hiding the older one makes the older half of the chart unattributable. | Andre |

### Row #4 - Semantic movement colour, direction-aware, both themes

- **Scope:** One helper decides whether a movement is good or bad from the measure's own polarity, and every card, delta and dot on the console paints from it, in both themes.
- **Files touched:**
  - `frontend/src/lib/charts/theme.ts`
  - `frontend/src/lib/components/KpiCard.svelte`
  - `frontend/src/lib/components/SwapDots.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `config/appearance.json`
  - `frontend/tests/console-polarity.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** as Row #1, in light and dark.
- **Oracle:** For every element carrying `data-movement`, read its declared polarity (`lower-is-better` or `higher-is-better`) and its sign, resolve its painted colour through a probe span carrying `var(--movement-good)` and `var(--movement-bad)`, and assert the mapping holds in both themes. Include at least one falling measure that must paint good (time per summary) and one rising measure that must paint good (share published), so no constant can satisfy the test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Polarity is a property of the measure and is declared where the measure is defined, never at the paint site. A component that decides its own polarity is how two cards disagree about whether down is good. | Fowler |
| 2 | Two new tokens, `--movement-good` and `--movement-bad`, in `config/appearance.json` with a value per theme. They are not the health ramp: health says a thing is broken, movement says a number went the right way. | Jony |
| 3 | A movement with no agreed direction paints neutral and says so. Prompt tokens a second has no target, so it is a fact, not a verdict. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Reuse the existing health ramp | Green there means "it worked". A summary that got 3 percent slower is not broken, and painting it red trains the operator to ignore red. | Jony |
| 2 | Sign alone decides the colour | It is the current defect: a fall in time per summary is an improvement and reads red. | owner, 2026-08-31 |

### Row #5 - Route labels and panel titles read alike

- **Scope:** The middle route is relabelled, and every panel title on the three routes is rewritten to one grammar.
- **Files touched:**
  - `frontend/src/lib/server/console-shell.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/tests/console-nav.spec.ts`
  - `frontend/tests/console-title.spec.ts` (new)
  - `docs/architecture/publishing/frontend.md`
  - `docs/concepts/ui-shell.md`
- **Acceptance gates:** as Row #1. `RouteId` and every `href` are unchanged, so no published address moves.
- **Oracle:** Assert every `h2` and every `Panel` title on the three routes matches one declared grammar - a noun phrase naming what is measured, with no trailing question mark - and that the set of `data-console-tab` ids is unchanged from `origin/main`. The second half is what proves the rename is a label change and not a route change.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `/console/model/` is relabelled **Summaries**. Every panel on it is about a published summary - its length, its cost, how long it took, what the checker doubted - and none is about the model as an artefact. | owner, 2026-08-31; Editor concurs |
| 2 | **UNRESOLVED, ESCALATE trigger (d).** The owner proposed relabelling `/console/machine/` to **Model**. Recommendation is to keep **Machine**: that route measures the host and the inference runtime - shards, job clock, processor, peak memory, context window - and moving the word "Model" onto it puts it on the page about the box rather than the page about the output. If the route must say what runs there rather than what it runs on, **Runtime** is truer than Model. The row STOPS here for a ruling and ships decision 1 either way. | owner |
| 3 | The title grammar is a noun phrase, not a question. `Did the runs finish?` and `Do the two clocks agree` become `Runs that finished` and `The two clocks, compared`; `What one more article costs` is already the form and is the model. A page of questions makes a reader answer before reading. | Editor |
| 4 | `RouteId` stays `pipelines` / `model` / `machine` and no `href` moves. A label is not an address. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rename the route directories too | The addresses are published, three specs pin them, and nothing a reader sees improves. | Fowler |
| 2 | Keep the questions and make them all questions | A question title asks the reader to hold it while reading the panel; a noun phrase names what is in front of him. The one title the owner named as the model is a noun phrase. | Editor |

### Row #6 - The Machine route joins the shared window

- **Scope:** `/console/machine/` renders the same `WindowControl` as the other two routes, reads the same localStorage key, and every panel on it that can be windowed is.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/lib/server/runtime-counters.ts`
  - `frontend/tests/console-window.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1, plus the route's `page_weight.ceilings_bytes` entry, which will move because a per-preset precomputation is inlined.
- **Oracle:** Drive each preset on each of the three routes in one browser session, and assert the value written to `idhazh:console-window` on any route is the value read on the next route loaded. Then assert every `[data-windowed]` surface on Machine reports a `data-window-days` equal to the control's. Bite-proof by picking 7 on Machine, navigating to Pipelines, and reading 7 there.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The window is shared across all three routes, not per route. An operator comparing a slow day across Pipelines and Machine cannot do it if the two are on different spans, and the localStorage key already exists for exactly that reason. | owner, 2026-08-31; Fowler concurs |
| 2 | A panel that is about ONE run - the shard board, the host under the newest run - stays out of the window and says which run it is about. The window is a span; a shard board is a snapshot. | Jony |
| 3 | Per-preset answers are precomputed at build time, one small object per preset, the precedent Row #17 of the observability plan set. Inlining every counter row grows the page without bound. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A window control per route with its own key | Two charts on two spans cannot be compared, which is the question an operator came to ask. | Fowler |
| 2 | Leave Machine unwindowed | It is the route whose numbers vary most between runs, so it is the one where "over how long" matters most. | Carmack |

### Row #7 - Failed items become sources ranked by articles lost

- **Scope:** A second ranked list, sources by articles lost in the window, sits between the cause ledger and the item rows, and the item table moves behind a native disclosure.
- **Files touched:**
  - `frontend/src/lib/components/FailureList.svelte`
  - `frontend/src/lib/components/Viewport.svelte`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/src/routes/console/+page.server.ts`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `frontend/tests/console-failures.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1, plus `ruff`, `mypy --strict`, `python -m idhazh.contracts.export` with a clean schema diff, and the contract fixture round-trip.
- **Oracle:** Independently of the component, read `frontend/public/telemetry/*.csv`, dedupe to one article per source per day keyed on `date` and `item_id`, count the losses per source, and assert the drawn rows equal the top `console.source_rows` of that ranking in that order, that the tail sentence's count and sum equal the remainder, and that selecting a source narrows the disclosed rows to exactly the matching set.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The missing dimension is WHICH SOURCE, and it is the only column in the item table no surface above it answers. Measured over `state/item-health/2026-08.csv` on 2026-08-29: 24 of 122 sources own 910 of 1,093 lost articles, 83.3 percent, and published nothing. | Susan |
| 2 | A second `RankedList` instance. No new component, no new chart type, `core.ts` untouched, hand-written markup. | Susan |
| 3 | Dedupe one article per source per day, the rule `compressionView` already uses, so the two surfaces cannot disagree. | Susan |
| 4 | The item rows survive verbatim behind `<details>`. A documented workflow starts from one address; deleting the rows breaks it. | Susan |
| 5 | No tint and no verdict on a source row. Per-source yield is not measurable until the ledger is 30 days deep, so a colour would publish a threshold nobody agreed. | `docs/architecture/sources/health.md` |
| 6 | New knob `console.source_rows`, default 10. | owner, 2026-08-31 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A stacked bar by failure code | `FailurePanels` is already a stacked column of the same days split by stage, one scroll above. Two stacked columns answering adjacent questions is the single grey wall. And 22 codes against an 8-stop ramp. | Susan |
| 2 | A stacked bar by source | 122 sources against 8 colours, and the question it answers - which is biggest - is a ranking, which this console already draws as a list with an opinion. | Susan |
| 3 | A source-by-code heat map or treemap | A new type in `core.ts`, a lazy chunk on a page that renders complete without one, and nobody reads a cell out of a 122-by-22 grid. | Susan |
| 4 | Delete the item table | It is the evidence, and the address in it is where troubleshooting one URL starts. | Susan |

### Row #8 - Feeds gain their denominator, and the failure list gains a cap

- **Scope:** The feed section states how many feeds have never failed, out of how many, over how many runs; names them behind a disclosure; and caps the failure list.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/lib/feed-health.ts`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `frontend/tests/console.spec.ts`
  - `docs/architecture/sources/health.md`
- **Acceptance gates:** as Row #7.
- **Oracle:** Independently of the page, read `state/feed-health/*.csv`, group by feed, and count the feeds with zero failing reads by `failing()` over the whole record. Assert the headline's numerator, denominator and run count all equal the independent computation, that the disclosed names are exactly that set, and that the failure list is capped at `console.feed_rows` with a tail sentence whose count equals the remainder.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A ranked "top 10 most reliable feeds" does NOT ship. Every key it could rank on ties: `collect.max_per_source` is 2, measured 2026-08-29 over 2026-08-26..29 between 73 and 78 of about 85 working feeds hit that cap in every run, and fifteen feeds published exactly 22 across eleven runs. A top ten of a seventy-way tie is charting a constant. | Susan |
| 2 | What the section is really missing is its denominator, and that ships: one headline sentence naming the clean count, the total and the span. | Susan |
| 3 | The clean feeds are NAMED behind `<details>`, alphabetically, with no bars and no order, and the summary says why there is no order. | Susan |
| 4 | The span is the whole record, matching the streak the section already refuses to window. Two spans in one section is the defect the shared window exists to remove. | Susan |
| 5 | New knob `console.feed_rows`, default 10, named to match `console.source_rows`. | owner, 2026-08-31 |
| 6 | Three empty states, and they say different things: no feed result yet; every feed clean; and a record too shallow for "every run" to mean anything. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rank by successful reads | A feed is read once per run and the record is about 21 runs deep, so every working feed ties. | Susan |
| 2 | Rank by items yielded | It counts entries in a feed, so it ranks the firehose, not the reliable. | Susan |
| 3 | Rank by longest unbroken run of answering | Ties for the same reason as reads: a feed that never failed has answered on every run it was asked. | Susan |

### Row #9 - Sources cut short fills its frame

- **Scope:** The source-cut range plot uses the width it is given, gives each row room to read, and stops clipping its right-most axis label.
- **Files touched:**
  - `frontend/src/lib/components/SourceCutRange.svelte`
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/tests/console-source-cuts.spec.ts` (new)
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1, at 1440, 768 and 390.
- **Oracle:** Assert the plot's drawn track spans at least 70 percent of the chart's inner width at 1440, that every axis `text` box sits inside the `svg` box (the `10,000` label measured clipped to `10,00` at 1440 on 2026-08-31), and that the row pitch is at least the readable minimum the design system states.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The right margin is sized from the widest axis label's measured advance, not from a constant. The clip is a constant that stopped being big enough. | Jony |
| 2 | Row pitch grows with the frame up to a ceiling, the way `cellFor` already grows a run-strip cell. Four rows in 130 px is a list, not a chart. | Jony |
| 3 | The log domain still snaps to decades. The dead space left of the shortest article is what a log axis costs and it is the price of placing the two cut rules. | `logAxis` docstring |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Start the domain at the shortest article | The two cut rules are the reason the chart exists, and a domain that floats loses the landmark a reader places a mark against. | Jony |
| 2 | A fixed taller row | It is the same defect facing the other way: a constant that is wrong at some width. | Jony |

### Row #10 - Articles published, beside charts published

- **Scope:** The glance strip gains an articles-published skyline beside the charts-published one, on the same window and the same geometry.
- **Files touched:**
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/tests/console-published.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** Independently count published items per day from the committed day payloads, assert the bar count equals the window's day count, that the card's total equals the sum of the drawn bars, and that the busiest bar is full height. Both skylines must report the same day count, which is what proves they are on one window.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `publishedSkyline` is parameterised over the measure rather than copied. Two skylines from one function cannot drift in geometry. | Fowler |
| 2 | The two cards sit side by side, articles first. The chart count is a fraction of the article count and reads as one only when the denominator is beside it. | Susan |
| 3 | Each card's own total is the window summed, so the number can be checked against the picture. | existing `publishedSkyline` docstring |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One chart with both series | Charts and articles differ by an order of magnitude, so one axis flattens the smaller series to nothing and two axes invite a comparison of slopes that means nothing. | Jony |

### Row #11 - Run health gains a readout and loses its dead margin

- **Scope:** The run strip grows into the width it is given, carries a date cadence rather than two endpoints, prints a hovered day through `ChartReadout`, and drops its standing legend.
- **Files touched:**
  - `frontend/src/lib/charts/run-history.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** At 1440 assert the strip's drawn width is at least 70 percent of its container (measured 2026-08-31 at about 430 px of 1,376, 31 percent), that the axis carries at least three labels over a thirty-day window (it carries two), and that hovering the oldest and the newest column prints two different `[data-readout-day]` values with a per-run line each.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The `CELL_MAX` ceiling of 34 px is what leaves the margin, and it is right for a fortnight and wrong for a page-wide strip with ten days in it. Raise the ceiling and centre the strip when it still cannot fill. Empty space on the right reads as missing data. | Jony |
| 2 | The legend goes; the readout prints the verdict word beside the swatch for the run it is on. | Row #2 decision 1 |
| 3 | The window still says thirty days even when ten carry runs. The empty columns are the fact that nothing ran, which is the thing this strip exists to show. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Shrink the window to the days with runs | It hides a gap, and a gap is a failure this panel is the only place to see. | Editor |
| 2 | Keep the `title` attribute as the hover | A native tooltip is not keyboard-reachable, is not styled, and prints one square rather than the day's whole column. | Jony |

### Row #12 - A chart never draws a span nothing measured

- **Scope:** A windowed chart whose data covers less than the window states the gap in type and draws the empty span as an explicitly empty region, rather than letting the marks pile against one edge.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/src/lib/components/FailurePanels.svelte`
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/components/BandDistance.svelte`
  - `frontend/tests/console-coverage.spec.ts` (new)
  - `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** For each windowed chart, compare the count of columns carrying a mark against the window's day count and assert that whenever the ratio is under a declared threshold the chart renders a `data-coverage-note` naming both numbers. Measured 2026-08-31, `Failure rate against volume` draws 30 columns over a 30-day window with marks on about 7, which is why the chart reads as right-aligned.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The window is not narrowed. The empty span is a true fact - the telemetry projection starts on 2026-08-24 - and a chart that hides it reports a fuller record than exists. | Editor |
| 2 | The note names both numbers: days drawn and days measured. Rule #10 in a sentence a reader can check. | CLAUDE.md Rule #10 |
| 3 | The empty region is tinted at the surface level, not hatched. A hatch is a pattern a reader tries to decode. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Auto-fit the domain to the measured days | It makes a seven-day record look like a thirty-day one, and the preset the reader picked stops meaning anything. | Editor |
| 2 | Say nothing and let the reader see the gap | Measured, the reader reads it as a right-aligned chart and asks why, which is exactly what happened. | owner, 2026-08-31 |

### Row #13 - The chart-arm flow survives a phone

- **Scope:** The chart-arm flow diagram is readable at 360 px, or it is replaced below a breakpoint by the same numbers in a shape that is.
- **Files touched:**
  - `frontend/src/lib/charts/chart-flow.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console-flow.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** as Row #1, with the 390 px arm load-bearing.
- **Oracle:** At 390 assert every flow node label's box sits inside the diagram's box, that no two labels in one stage column overlap, and that the sum of the branch values equals the inflow. If the row takes the fallback, assert the fallback carries the identical numbers as the diagram at 1440 - which is what stops two shapes reporting two different flows.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Label geometry is measured in the browser, never reasoned about. A sankey label does not scale with the SVG: the font is fixed while the chart redraws at container width. | `docs/reference/measurements.md`, 2026-08-30 |
| 2 | Below the breakpoint the flow becomes a stepped list of stage, count and the branch that left - the same numbers, in the shape a 360 px column can hold. | Jony |
| 3 | No new chart type. The fallback is markup. | ESCALATE trigger (b) |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Horizontal scroll on the diagram | The diagram's whole value is seeing every branch at once; a scroll destroys it and hides the small branches off-screen. | Jony |
| 2 | Shrink the font | It was already measured: a one-line label ran 280 px into a 246 px column pitch, and smaller type on a phone is not a fix. | Jony |

### Row #14 - Every daily-figures disclosure states its window

- **Scope:** Both `Show the daily figures` disclosures declare the span they cover, honour the shared window, and say so in their summary line.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/tests/console-window.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** Drive each preset and assert both disclosures' row counts change with the preset and equal the count of days in the window that carry data, and that each summary line names the same day count as the window control.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A disclosure inside a windowed section is windowed. A table that ignores the preset above it is the two-spans defect in a `<details>`. | Fowler |
| 2 | The summary line carries the count, so the span is readable without opening it. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave the tables all-time and label them so | The reader picked a window; two answers on one page for one question is what the shared control removed. | Fowler |

### Row #15 - Which sources the checker doubts

- **Scope:** The Summaries route gains a ranked list of the sources whose summaries most often carry a doubt signal, over the window in force.
- **Files touched:**
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/routes/console/model/+page.svelte`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `frontend/tests/console-doubt.spec.ts` (new)
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** as Row #7.
- **Oracle:** Independently of the page, read `state/scores/*.csv`, group by source, and count rows where `band == 'low'`, where `unsupported_numbers > 0`, and where `hedge_dropped` is true. Assert the drawn rows equal the top `console.doubt_rows` by the declared rank rule, that each row's three counts equal the independent counts, and that every row prints its own denominator - a source with 2 doubted of 3 must not outrank one with 40 of 400 unless the rule says so, and the rule must be stated on the page.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | All three signals already exist on `EvalRow` and are already summarised per source in `model-work.ts`. No contract widens; ESCALATE trigger (a) does not fire. | measured 2026-08-31 |
| 2 | Three counts, never one blended score. A blend hides which of the three fired, and they have different causes: a low band is the grader's confidence, an unsupported number is a fabrication, a dropped hedge is a certainty the article did not have. | Andre |
| 3 | Ranked on the count of doubted summaries, with a floor of `console.min_attempts_for_rate` before any share is printed. The existing floor, not a new one. | Andre |
| 4 | No verdict colour on a source. The grader has a known length bias; a tint here would publish a judgement about a publisher off an instrument that is still being calibrated. | Andre |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A source-by-signal matrix | Same defect as Row #7's rejected heat map: a grid nobody reads a cell out of. | Susan |
| 2 | One combined "doubt score" per source | It is an unmeasured composite presented as a measurement, and Rule #10 forbids it justifying anything. | Andre |

### Row #16 - What one summary cost becomes a chart

- **Scope:** The scoring-cost sentence becomes a distribution chart with the cost labelled on it, keeping the sentence as the readout's resting column.
- **Files touched:**
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/tests/console-model-panels.spec.ts`
  - `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:** as Row #1, with 390 px load-bearing - the x-axis labels measured overlapping there on 2026-08-31.
- **Oracle:** Assert the drawn distribution's median and 95th-percentile marks equal the values `model-work.ts` computes for the same window, that both are labelled in type on the chart, and that at 390 px no two axis labels overlap (Row #1's helper is what makes this pass).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The shape is the histogram `WriteTimeHistogram` already draws, reused, not a second implementation. Same question - how long did a thing take - so the same shape. | Fowler |
| 2 | The median and the 95th are drawn as rules with their values in type, because they are the two numbers the sentence already gives and a reader should not have to read a bar to recover them. | Susan |
| 3 | The sentence survives as the resting readout column, so the panel still says something with script off. | CLAUDE.md Rule #1 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A cost per day line | The question is the distribution of one summary's cost, not its trend; a daily mean hides the tail that the 95th exists to show. | Andre |
| 2 | Keep the sentence alone | Two numbers out of a distribution of 3,529 summaries cannot say whether the tail is long or thin. | Susan |

### Row #17 - The model-change panel earns the width it takes

- **Scope:** The model-change comparison uses the full panel width, paints each measure by its own polarity, and gains the measures the two sides can honestly be compared on.
- **Files touched:**
  - `frontend/src/lib/components/SwapDots.svelte`
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/tests/console-model-panels.spec.ts`
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** as Row #1, light and dark.
- **Oracle:** Assert every measure carries a declared polarity, that its painted colour follows Row #4's mapping in both themes, that the panel's drawn width is at least 90 percent of its container at 1440, and that every added measure has a non-null value on both sides of the boundary - a measure only one side recorded must be named as unmeasured, never drawn as a change.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is the most useful panel on the route, so it gets the width. The current layout wastes it. | owner, 2026-08-31 |
| 2 | Added measures must be recorded on BOTH sides of the boundary. A measure the older model never wrote is not a comparison. | Andre |
| 3 | Polarity per measure, from Row #4. Time per summary falling is good; share published rising is good; prompt tokens a second has no agreed direction and paints neutral. | Row #4 decision 1 |
| 4 | The candidate additions, each to be included only if it clears decision 2: time per summary, summaries inside the length band, summaries the checker doubted, unsupported numbers per hundred, and the read and write rates. | Andre |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Add every column the ledger carries | A panel of twenty deltas is a table, and the panel's value is that it names the few things that moved. | Susan |
| 2 | Backfill the older model's missing measures | It would be an estimate presented as a measurement. | CLAUDE.md Rule #10 |

### Row #18 - The shard board survives a phone

- **Scope:** The shard board becomes readable at 360 px, keeping every value it shows today.
- **Files touched:**
  - `frontend/src/lib/components/ShardBoard.svelte`
  - `frontend/tests/console-machine-data.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1, with 360 and 390 px load-bearing.
- **Oracle:** At 360 px assert no text node in the board wraps to more than a declared maximum number of lines for its content length - measured 2026-08-31 at 390 px, `51 m 24 s` wrapped to four lines, one character per line - that every value carries a visible label (the column headings vanish on a phone today, orphaning the values), and that the set of values rendered at 360 equals the set rendered at 1440.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Below the breakpoint the board becomes one card per shard with label-and-value pairs, not a table with invisible headings. A column heading that only exists on desktop is a value with no name on a phone. | Jony |
| 2 | Every value survives. The owner's reading of the board - that one processor is outperforming another - is the signal it exists to carry, and the fix is positioning, not reduction. | Susan |
| 3 | The processor comparison stays a FACT and gains no verdict. Two shards on the identical processor string measured 1.11x apart, so the processor is not the whole cause and a colour would claim it is. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Horizontal scroll on the table | It hides the job clock, which is the column an operator opens the page for. | Jony |
| 2 | Drop columns on a phone | The board is already one screen of five facts; dropping one makes the phone a different instrument from the desktop. | Susan |

### Row #19 - Context headroom becomes one chart

- **Scope:** The repeated per-run bars become one chart: runs across the x-axis, longest sequence on the y, the context window as a rule, spare capacity as a second series, with a hover readout.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/lib/server/runtime-counters.ts`
  - `frontend/tests/console-machine-data.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** Independently read `state/runtime-counters.csv`, take the longest sequence per readable run, and assert one mark per run in date order, that the rule sits at the configured context window, that the spare series equals window minus longest for every run, and that hovering any run prints the same three numbers the current bar's caption prints. Bite-proof by truncating the ledger: the chart must render its named empty state and the page must stay whole.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Thirteen near-identical bars, each with two lines of prose, is a table pretending to be a chart. One chart across runs is the shape of the question - is headroom trending toward the ceiling. | Susan |
| 2 | The window is a rule, not a bar. A limit is a line a series approaches. | Jony |
| 3 | Spare capacity is drawn as its own connected series so the two can be read against each other; it is derived, so it carries a dotted stroke to say it is not an independent measurement. | Jony |
| 4 | Refused runs stay named above the chart, as today. A run count that quietly excludes one is a run count nobody can check. | existing panel comment |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the bars and cap the count | The repetition is the defect, not the length; ten copies read the same as thirteen. | Susan |
| 2 | One bar showing only the newest run | The panel exists to say whether raising the truncation cap is possible, which is a question about the worst run in the window, not the newest. | Carmack |

### Row #20 - Peak memory, per shard and in one number

- **Scope:** The Machine route reports peak resident memory per shard and the run's own high-water mark, against the runner's 16 GB.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/lib/server/runtime-counters.ts`
  - `frontend/tests/console-machine-data.spec.ts`
  - `docs/reference/measurements.md`
- **Acceptance gates:** as Row #1.
- **Oracle:** Independently read `peak_rss_bytes` from `state/runtime-counters.csv`, and assert the aggregate equals the maximum across the run's shards and never their sum, that the per-shard marks equal the ledger's values, and that a run the reader refuses contributes nothing to either. Include the refused run `2026-08-29-3` in the fixture so the test fails if the refusal is dropped.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The aggregate is a MAXIMUM, never a sum. Shards run on separate hosts, so summing reports a machine that never existed. | Carmack |
| 2 | The 16 GB runner is the rule the marks are read against. Measured 2026-08-31, the high-water mark is 13,589,483,520 B, 12.66 GiB, which is 79 percent of it and is the number this panel exists for. | Carmack |
| 3 | `peak_rss_bytes` is filled on 20 of 54 committed rows, so the panel must draw the measured subset and name the unmeasured count rather than treating absent as zero. | measured 2026-08-31 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One aggregate only | The spread between shards is the finding; one number hides which shard is near the edge. | Carmack |
| 2 | Colour the bar by nearness to 16 GB | No threshold has been agreed, and a tint would publish one. | Susan |

### Row #21 - Run latency, one chart per percentile and one across them

- **Scope:** The latency panel becomes small multiples, one chart per percentile with its own hover, plus one chart carrying all percentiles for the newest run.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/lib/charts/machine.ts`
  - `frontend/tests/console-machine-data.spec.ts`
  - `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:** as Row #1, at 1440 and 390.
- **Oracle:** Assert one chart per configured percentile, each drawing one mark per readable run; that the aggregate chart's value at the newest run equals the corresponding small multiple's newest value for every percentile; and that the small multiples share one y domain so their heights are comparable. That shared domain is the check - five charts on five domains cannot be compared and would be five pictures of the same shape.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Five lines on one chart at five percentiles of the same measure is a bundle a reader untangles by colour; separated, each is a trend he reads in one look. | Susan |
| 2 | The small multiples share a y domain. Independent domains make five different shapes look alike. | Jony |
| 3 | The aggregate chart stays, for the newest run only, because "how long is the tail today" is a different question from "is the tail growing". | Andre |
| 4 | No new chart type. Small multiples are the existing line shape drawn N times. | ESCALATE trigger (b) |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep one chart and add a series toggle | A toggle is a control a reader has to operate before he can read anything, and the comparison across percentiles is exactly what small multiples give free. | Jony |
| 2 | Drop the aggregate | It is the only place the newest run's whole distribution is visible at once. | Andre |

### Row #22 - Closure

- **Scope:** Distil the plan's durable lessons into the living docs, re-derive the three console page ceilings on the merged tree, and delete the plan-doc.
- **Files touched:**
  - `docs/reference/agent-notes.md`
  - `docs/reference/measurements.md`
  - `docs/concepts/design-system.md`
  - `config/idhazh.json`
  - `TODO/20260831-console-chart-craft-plan.md` (deleted)
- **Acceptance gates:** full local suite; CI green; every route under its re-derived ceiling with the seven-publish runway the ceiling rule requires.
- **Oracle:** Five builds per route on the merged tree; the recorded ceiling is the heaviest plus a measured seven published days at the measured per-day rate. A sixth build inside the five-build spread is the control.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The ceilings are re-derived once, at the end, not per row. A ceiling recorded mid-plan describes a tree that never shipped. | `docs/reference/measurements.md`, 2026-08-31 |
| 2 | Every row reports what it could not file, and this row files it. A worker cannot write `agent-notes.md` when it is outside its row's file list. | `docs/how-to/distill-a-plan.md` |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let each row re-record its own ceiling | Twenty-one re-measurements of a number only the last one describes. | Carmack |

## See also

- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [`docs/concepts/design-system.md`](../docs/concepts/design-system.md) - the chart vocabulary and the sufficiency checks.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console routes and what each one owns.
- [`docs/architecture/sources/health.md`](../docs/architecture/sources/health.md) - the feed-health rules Row #8 reads.
