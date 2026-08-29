# Console signal plan - make the operator page answerable at a glance

**Last Updated**: 2026-08-30
**Level**: 4 (structural; 4+ files, new shared components, one new chart type)

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 4; honor the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The console renders its data honestly and answers almost none of the questions it was built for: five of its six tables sort by date rather than by severity, two of its charts carry no per-day axis label and no hoverable point, one scatter draws 2,740 marks in one colour, and the size chart draws the item ceiling while claiming to draw site growth. |
| Hard scope - in | The `/console/` route and every component it renders; `config/appearance.json` and its Pydantic contract; the shared time window and its UI control; one new chart type (Sankey); three new shared display components; the chart prose scrub; re-baselining the console byte ceiling. |
| Hard scope - out | The reader-facing digest, archive, `/evals/` and `/404`. The telemetry projection's column set (`docs/architecture/publishing/telemetry-series.md`) - no new column is published by this plan. Backend pipeline logic. The label copy for `What the model did`, which is protected verbatim. |
| ESCALATE triggers | (a) Any row that needs a new published telemetry column - that is a persisted-contract change, PAUSE per CLAUDE.md section 6. (b) The lazy chart chunk exceeding 200,000 B gzipped after the Sankey lands. (c) `/console/` HTML exceeding its re-derived ceiling by more than 20 percent. (d) Any proposal to lend the health ramp to a figure with no agreed threshold. |
| Chosen strategy | Rank by magnitude, not by date; give every threshold a visible marker; give every trend a hoverable point with a date. Ruled by Susan (Craft and Delight), 2026-08-30, on a six-surface review. |
| Byte posture | The owner relaxed the byte budget for this plan on 2026-08-30: signal outranks transfer size on the operator page. Ceilings are re-derived, not held. `/console/` is `noindex` and is not a reader surface. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. |

### Measured baseline (Windows 11, node 24, Chromium via Playwright, built from `ee5ec00`, 2026-08-30)

| Fact | Value |
| --- | --- |
| `Time per item, by stage` text nodes | 7 total: six decade labels (`10 ms` to `1000 s`) plus one span string `24-29 Aug 2026`. Zero per-day labels. |
| `Time per item, by stage` point marks | 0 across 4 polylines. Nothing is hoverable. |
| `Model tokens per second` text nodes | 7, same shape, same absence of a per-day label. |
| `Article length against summary length` marks | 2,740 in one colour on a 1026px plot. |
| Failure panels | three at 492px, 2 text nodes each. |
| Hover readout box width | 88-121px over a 220px plot: 40 to 55 percent of the chart it explains (measured 2026-08-29). |
| Run-health fills, light theme | `--band-medium` `#8a6300`, `--band-low` `#b4331f` on `--color-surface` `#fff`. Both are text-weight colours used as 16px solid fills. |
| Run-health strip placement | right-jammed; the left half of the grid is empty when days are fewer than columns. |
| Site day cost against item count | 2.97 MB to 17.4 MB as items ran 117 to 731. The chart draws the item ceiling, not site growth. |
| Per-item site cost | 24,378 B, spread 23,066 to 26,538. |
| `/console/` HTML | 76,716 B gzipped; ceiling in `config/idhazh.json` is 301,580 B. |
| `/console/` page height | 8,794px. |
| Tables on the page | 6. Five sort by date. |

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Shared time window: config presets, UI control, cost disclosure | - | A | PENDING | - | - | - |
| 2 | Shared display primitives: RankedList, TargetBar, Sparkline | - | A | PENDING | - | - | - |
| 3 | Funnel to Sankey, left to right, categorical colour | - | A | PENDING | - | - | - |
| 4 | Time per item: per-day axis, point marks, hover values, non-occluding readout | 1 | B | PENDING | - | - | - |
| 5 | Model tokens per second: per-day axis and the same readout contract | 1 | B | PENDING | - | - | - |
| 6 | Run health: per-theme fill ramp, framed panel, bottom date labels, left-anchored strip | 1 | B | PENDING | - | - | - |
| 7 | Failure rate reimagined: rate against volume, not three bare panels | 1 | B | PENDING | - | - | - |
| 8 | Published trend to a per-day skyline; delete the two on-record counts | 1 | B | PENDING | - | - | - |
| 9 | Site size: bytes-per-item trend, and a ceiling card with a runway | 1 | B | PENDING | - | - | - |
| 10 | Compression scatter to distance-from-band bars plus an outlier list | 1 | B | PENDING | - | - | - |
| 11 | Feeds that failed: distance-to-quarantine bar and a per-feed outcome strip | 2 | B | PENDING | - | - | - |
| 12 | Failed items to a failure ledger ranked by cause | 1, 2 | C | PENDING | - | - | - |
| 13 | Sources cut short to a length range plot with the cap drawn as a rule | 1, 2 | C | PENDING | - | - | - |
| 14 | What the model did: eleven measure cards over a table on demand | 1, 2 | C | PENDING | - | - | - |
| 15 | Charts drawn for articles: two target bars, a verdict sentence, rows on demand | 1, 2 | C | PENDING | - | - | - |
| 16 | Chart prose scrub: keep the sentence that decides, cut the sentence that narrates | 4, 5, 6, 7, 8, 9, 10 | D | PENDING | - | - | - |
| 17 | Closure: re-baseline bytes, re-measure the page, record the rulings | 1-16 | E | PENDING | - | - | - |

## 2 - Row #1 - Shared time window: config presets, UI control, cost disclosure

- **Scope:** One window governs every windowed surface on the console, set from a preset control on the page and defaulted from config, with the transfer cost of a wider window stated before it is paid.
- **Files touched:**
  - `config/appearance.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `frontend/src/lib/charts/viewport.ts`
  - `frontend/src/lib/components/Viewport.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/tests/console-window.spec.ts` (new)
- **Acceptance gates:** `ruff`, `mypy --strict`, contract drift gate byte-identical, `svelte-check` 0 errors, browser smoke on `/console/`, page renders with JavaScript disabled at the default window.
- **Oracle:** Set the control to each preset in turn and assert that every windowed surface reports the same day count in its own accessible description. A surface that disagrees with the control fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Presets are `[7, 14, 30, 90]` in a new `console.window_presets` array; `console.default_window_days` stays 30 and must be a member of the array, enforced in the Pydantic validator beside the existing min/max checks. | Owner, 2026-08-30 |
  | 2 | Default 30, not 14: the page states its own retirement rules over 14 days, so a window equal to the rule shows the rule with no margin and a 7-day window cannot show it at all. | Owner, 2026-08-30 |
  | 3 | The control is a segmented set of radio inputs, not a select: four options, all visible, keyboard-reachable, no popup. It sits directly under the page intro, above the first chart, so it is read before anything it governs. | Jony (UI/UX) |
  | 4 | Widening re-fetches month CSVs through the existing `loadVisibleMonths` path. The control names the cost in words before it is paid - the number of extra months a preset will fetch - and shows a busy state while fetching. No page reload. | Owner, 2026-08-30 |
  | 5 | The choice persists in `localStorage` and is read on mount, never during prerender, so first paint always matches the prerendered seed. | Fowler (Architecture and Engineering) |
  | 6 | Two surfaces do NOT follow the window, and each says so on the page. `Feeds that failed` keeps the pipeline's own consecutive-failure count and quarantine marker, because a windowed count would disagree with the quarantine decision the pipeline actually took. `Site size` prints the current absolute number always; the window governs only its delta and its runway. | Susan (Craft and Delight), 2026-08-30 |
  | 7 | `Sources cut short most often` becomes windowed, dropping its hard-coded 7 days. The earlier objection was that a hidden knob could make the section's own sentence lie; a control the operator is looking at cannot, provided the sentence reads the same window the query reads. The section must print its denominator, which at 7 days runs as low as 6 articles. | Susan (Craft and Delight), 2026-08-30 |
  | 8 | At a 7-day window, any surface whose decision rule is stated over 14 days prints `The rule reads 14 days. Widen the window to see it.` and prints no median. A median of the wrong span is worse than no median. | Susan (Craft and Delight), 2026-08-30 |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A per-chart window control | Six controls invite six different windows, and two charts on different windows cannot be compared. The operator's question spans the page. | Susan |
  | 2 | A free numeric input or a slider | Every value is a distinct fetch cost and most are indistinguishable. Four presets are the whole useful range. | Jony |
  | 3 | A full page reload on change | The viewport already fetches and merges month CSVs incrementally. A reload discards rows already paid for. | Carmack (Engine and Runtime) |
  | 4 | Prerendering one page per preset | Four prerendered console pages quadruple the route's contribution to the site and each still needs the runtime fetch for months outside its seed. | Carmack |
  | 5 | Applying the window to the feed quarantine count as well | The marker on the page would then disagree with the quarantine the pipeline performed. Two numbers for one decision is the defect class the run strip already avoids. | Susan |

## 3 - Row #2 - Shared display primitives: RankedList, TargetBar, Sparkline

- **Scope:** Three small components that four sections share, so the console gains one ranked shape rather than six bespoke tables.
- **Files touched:**
  - `frontend/src/lib/components/RankedList.svelte` (new)
  - `frontend/src/lib/components/TargetBar.svelte` (new)
  - `frontend/src/lib/components/Sparkline.svelte` (new)
  - `frontend/src/lib/charts/rank.ts` (new; the sort, cap and tail-sentence helpers)
  - `frontend/tests/console-ranked.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** `svelte-check` 0 errors, unit tests on `rank.ts`, browser smoke, each component renders an empty state without throwing.
- **Oracle:** For a list of known magnitudes, assert every bar width equals `value / max` of the rendered set and that the printed maximum equals that divisor. A bar scaled to anything else lies about absolute size and fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `RankedList` slots: `label` (entity plus optional glyph and status word), `value` (printed), `track` (bar of `value / max`, or a `TargetBar` where a threshold exists), `trend` (optional sparkline), `context` (one short string - denominator, last outcome, or newest date), `onSelect` (optional; makes the row a filter chip). | Susan |
  | 2 | Ranked by magnitude, never by date. This is the rule the row exists to enforce. | Susan |
  | 3 | Capped, with the tail stated in a sentence - the pattern the source-cut section already uses, generalised. | Susan |
  | 4 | The list's maximum is printed next to the list, because a bar scaled to a hidden divisor cannot be read for absolute size. | Susan |
  | 5 | The empty state distinguishes "nothing was recorded" from "it answered nothing". Already doctrine for one table; it generalises. | Susan |
  | 6 | `TargetBar` draws a track of the threshold's own scale, a fill of the value, and a marker at the threshold. Same component serves the quarantine countdown, the truncation cap and the router-minute rule. | Susan |
  | 7 | The 2026-08-29 refusal of a shared table component ("an abstraction for two call sites") is reversed here and the reversal is written into `docs/concepts/design-system.md` with its reason, not applied silently. The count is four call sites, one of them new. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A generic `Table` component | The console's problem is not table markup, it is that tables were the wrong shape. A generic table would make the wrong shape cheaper to produce. | Susan |
  | 2 | Drawing the ranked bars in echarts | Four static bars per row do not need a chart engine, a canvas or a lazy chunk. Plain markup keeps them readable with JavaScript off. | Carmack |
  | 3 | A shared component for the run strip, scatter, timing trend and funnel too | Each answers a question no ranked list answers. They stay bespoke. | Susan |

## 4 - Row #3 - Funnel to Sankey, left to right, categorical colour

- **Scope:** The stage funnel becomes a left-to-right Sankey whose link widths carry the loss at each stage, drawn in the categorical chart ramp.
- **Files touched:**
  - `frontend/src/lib/charts/core.ts`
  - `frontend/src/lib/charts/chart-funnel.ts` (renamed to `chart-flow.ts`)
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/bundle-baseline.json`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke light and dark, no magenta sentinel present in the rendered DOM, lazy chunk re-measured and recorded.
- **Oracle:** Sum the outgoing link values at every node and assert each equals that node's own value minus its recorded loss. A Sankey whose widths do not conserve the counts is drawing a picture, not the data.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `SankeyChart` is registered in `frontend/src/lib/charts/core.ts`, the single registration site, and the lazy chunk is re-measured in the same commit against the recorded 153,204 B. | Carmack |
  | 2 | Colour comes from `PALETTE` (`--chart-1..8`) through the sentinel bridge, never from a hard-coded hex, so both themes resolve. Loss links take a lower opacity of the same hue rather than a new hue. | Jony |
  | 3 | Left to right, matching the reading direction and the pipeline's own order. | Owner, 2026-08-30 |
  | 4 | Node labels sit outside the node with the count and the share, so a narrow node cannot swallow its own label - the defect the funnel already had to fix once. | Jony |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the funnel and restyling it | A funnel encodes a monotonic sequence as a taper and cannot show where a loss went. A Sankey shows the loss as a branch. | Jony |
  | 2 | A hand-written SVG Sankey | Layout with crossing minimisation is the expensive part and the engine already ships it. The chunk is measured, not assumed. | Carmack |
  | 3 | Top to bottom | The page's other flow reads left to right and the console frame is wide, not tall. Page height is already over its target. | Jony |

## 5 - Row #4 - Time per item: per-day axis, point marks, hover values, non-occluding readout

- **Scope:** The stage-timing trend gains a date label per column, a mark at every point, a hover and keyboard readout of the value under the pointer, and a readout that never covers the plot.
- **Files touched:**
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/tests/console-timings.spec.ts` (new)
  - `config/appearance.json`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, keyboard traversal reaches every point, readout occupies no more than one third of the plot width.
- **Oracle:** Count the rendered date labels and assert the count equals the number of plotted days, capped by `chart.tick_density` with the endpoints always present. Count the point marks and assert the count equals days times series. Both currently return 1 and 0 against expectations of 6 and 24.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The x axis prints a date per column, thinned to `chart.tick_density` with the first and last day always labelled. The single span string is deleted; the accessible description keeps the range. | Owner, 2026-08-30 |
  | 2 | Every point gets a mark. Without a mark there is nothing to aim a pointer at and nothing for a keyboard to land on. | Owner, 2026-08-30 |
  | 3 | The readout is a fixed strip below the plot, not a floating box over it. It shows the date and every series value at the hovered column at once, so a comparison does not require four hovers. | Susan |
  | 4 | Readout width is capped at one third of the plot; a new `chart.readout_max_share` knob carries the cap, and the value is asserted in the browser test. The measured 40 to 55 percent occlusion is the defect. | Jony |
  | 5 | A vertical guide line marks the hovered column across all series. | Jony |
  | 6 | The existing `pointerReadout` helper in `frame.ts` already handles mouse, pen, touch and keyboard with nearest-by-x. It is reused, not rewritten. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A floating tooltip that dodges the cursor | Dodging moves the thing being read. The measured occlusion is the complaint; a strip below the plot cannot occlude at all. | Jony |
  | 2 | Labelling only the first and last day | That is the current behaviour expressed differently, and it is what makes a spike unattributable to a date. | Owner |
  | 3 | Dropping the log axis for a linear one | Stage timings span three decades. A linear axis flattens four of the five stages into the baseline. | Carmack |

## 6 - Row #5 - Model tokens per second: per-day axis and the same readout contract

- **Scope:** The throughput trend gains the same per-day axis labels, marks and readout contract the timing trend gains, so two charts stacked on one page do not behave differently.
- **Files touched:**
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - `frontend/tests/console-throughput.spec.ts` (new)
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, keyboard traversal, readout share within cap.
- **Oracle:** The same label-count and mark-count assertions as row #4, run against this chart. Currently 7 text nodes with no per-day label.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Identical axis, mark and readout behaviour to row #4. Two adjacent charts that hover differently teach the operator nothing and cost him a second guess. | Susan |
  | 2 | The existing candle marks stay; they already carry the spread, which a line would discard. | Carmack |
  | 3 | A model-swap date draws a vertical rule, so a throughput change can be attributed to a swap rather than guessed at. | Andre (AI / LLM) |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Merging this chart into the timing chart | Tokens per second and milliseconds per item are different units with different decades. One axis would have to lie about one of them. | Carmack |
  | 2 | Deferring this row into row #4 | Two components, two test files, two independently reviewable diffs. Bundling raises the revert cost with no gain. | Fowler |

## 7 - Row #6 - Run health: per-theme fill ramp, framed panel, bottom date labels, left-anchored strip

- **Scope:** The run strip gets fill-weight colours in both themes, sits inside a panel, labels its dates below the grid, and starts at the left edge instead of jamming to the right.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/tokens.css`
  - `frontend/src/app.css`
  - `frontend/src/lib/charts/run-history.ts`
  - `frontend/tests/console-run-health.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke in both themes, screenshots before and after in both themes attached to the PR.
- **Oracle:** Assert each fill token's contrast against `--color-surface` in both themes falls inside the fill band, and assert the strip's first square's left edge equals the grid's left edge when day count is below column count. The right-jam currently fails the second.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `--band-high`, `--band-medium` and `--band-low` are TEXT colours and stay text colours. A parallel fill ramp `--fill-high`, `--fill-medium`, `--fill-low` is added per theme. The light-theme values `#8a6300` and `#b4331f` read as olive and brick mud at 16px solid; the dark-theme values are already fill-weight. | Jony |
  | 2 | The strip is wrapped in a `Panel`, so it has an edge like every other section. An unframed grid on a page background reads as a stray artefact. | Jony |
  | 3 | Date labels move below the grid, where an axis label belongs and where they cannot be mistaken for a row heading. | Jony |
  | 4 | The strip anchors left and grows right. `today_anchor: "right"` governs the scroll position of an overflowing strip, not the alignment of an underfull one; the two were conflated. | Owner, 2026-08-30 |
  | 5 | The strip follows the shared window from row #1. | Owner, 2026-08-30 |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Lightening the band tokens themselves | They are used as text elsewhere. Lightening them to fill weight would fail text contrast on every other surface that reads them. | Jony |
  | 2 | Using opacity on the existing tokens | Opacity over a tinted surface produces a different colour per surface and cannot be checked for contrast once. | Jony |
  | 3 | Centring an underfull strip | Centred, the strip moves as days accumulate. Left-anchored, a day stays where the operator last saw it. | Jony |

## 8 - Row #7 - Failure rate reimagined: rate against volume, not three bare panels

- **Scope:** The three fetch, extract and summarize panels become one chart that shows failure rate against the volume it was measured on, so a 100 percent failure on two items cannot look like an outage.
- **Files touched:**
  - `frontend/src/lib/components/FailurePanels.svelte`
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/tests/console-failure.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, empty-window state renders.
- **Oracle:** Assert every printed rate carries its denominator in the same accessible label, and that a stage below `console.min_attempts_for_rate` renders as an explicit low-sample state rather than a rate. A bare percentage with no denominator fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One chart replaces three panels: per-day stacked bars of succeeded against failed per stage, with the failure share drawn as a line on a right-hand axis. Volume and rate become one picture. | Susan |
  | 2 | The three stages become three series in the categorical ramp, not three separate 492px panels carrying two text nodes each. | Jony |
  | 3 | A stage below `console.min_attempts_for_rate` prints the counts and suppresses the rate. The knob exists and is currently applied to one table only. | Fowler |
  | 4 | Follows the shared window. | Owner, 2026-08-30 |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping three panels and adding sparklines | Three panels at 492px on a 1600px frame is the layout that produced two text nodes each. The problem is the split, not the content. | Jony |
  | 2 | A single headline failure rate for the whole pipeline | Which stage failed is the actionable half. An aggregate hides it. | Susan |

## 9 - Row #8 - Published trend to a per-day skyline; delete the two on-record counts

- **Scope:** The published-items trend becomes per-day bars, and the two cumulative row counts in the page intro are deleted.
- **Files touched:**
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/+page.server.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, no unused server-side computation left behind.
- **Oracle:** Assert the intro carries no monotonic cumulative count, and that the bar count equals the window's day count. Assert `totalRows` and `itemHealthRows` have no remaining reader in `frontend/src`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The two on-record counts are deleted. Both only ever grow, so neither can indicate a state, and both are computed and shipped for a sentence nobody acts on. | Owner, 2026-08-30 |
  | 2 | Published items become per-day bars in `--chart-3`, not a line: a count per day is a discrete quantity and a line implies interpolation between days. | Jony |
  | 3 | Their server-side computation is removed in the same commit, not left orphaned. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the counts as a footer credit | A number with no decision attached is noise wherever it is placed. | Susan |

## 10 - Row #9 - Site size: bytes-per-item trend, and a ceiling card with a runway

- **Scope:** The size waterfall is replaced by a bytes-per-item trend with its median and spread, and the `Runs and site size` table is replaced by one ceiling card carrying a runway.
- **Files touched:**
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/components/KpiCard.svelte`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, every printed number carries its unit and its basis.
- **Oracle:** Assert the flagged-day set equals the set of days outside one standard deviation of the window median, computed independently in the test. A chart that flags by eye fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The waterfall is replaced. Day cost ran 2.97 MB to 17.4 MB purely because item count ran 117 to 731, so the chart draws the item ceiling and calls it site growth. Bytes per item is the quantity a change can move. | Owner, 2026-08-30, conceded on the measurement |
  | 2 | The trend prints the window median and a plus-or-minus one standard deviation band, and flags days outside it. Current basis: 24,378 B per item, spread 23,066 to 26,538. | Carmack |
  | 3 | The `Runs and site size` heading is deleted. It is two nouns joined by "and", which is two sections. Size becomes a card; the run counts already exist four headings above as the run strip. | Susan |
  | 4 | The size card carries the absolute number, a fill track against 1 GB, the window delta, and a runway in plain words. The runway is the number the ceiling question actually needs and it is nowhere on the page today. | Susan |
  | 5 | `planned` moves onto the run square's own label, where run-level facts already live. | Susan |
  | 6 | The absolute size does not follow the window; only the delta and the runway do. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the waterfall with a per-item normalisation applied | A waterfall encodes contributions to a total. Once normalised, there is no total to contribute to. | Jony |
  | 2 | Keeping the daily size table below the card | Thirty numbers moving by 0.1 MB a day say one thing. The card says it. | Susan |

## 11 - Row #10 - Compression scatter to distance-from-band bars plus an outlier list

- **Scope:** The 2,740-mark scatter is replaced by a per-day stacked bar of inside, too short and too long, with a ranked list of the worst outliers beneath it.
- **Files touched:**
  - `frontend/src/lib/components/CompressionScatter.svelte`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/tests/console-compression.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, the three-way split sums to the day's item count.
- **Oracle:** Assert `inside + tooShort + tooLong` equals the day's summarised count for every day in the window. A split that does not sum is mis-binning items.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The scatter is replaced. 2,740 marks in one colour render the dense region as a solid block, which hides the outliers that are the only actionable marks on it. | Owner, 2026-08-30 |
  | 2 | The question the section answers is "how far from the target band", so distance from the band is what is plotted, not the two raw lengths. | Susan |
  | 3 | The outlier list uses `RankedList` from row #2, ranked by distance from the band. | Susan |
  | 4 | The target band's bounds are printed as numbers beside the chart. A shaded band with no printed bound cannot be checked. | Susan |
  | 5 | Follows the shared window. | Owner, 2026-08-30 |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A density-binned scatter with only outliers drawn individually | It keeps the two-axis reading the operator must perform per mark. The bar answers the question directly. Recorded as the runner-up. | Susan |
  | 2 | Reducing the opacity of the marks | It makes the blob paler. It is still a blob. | Jony |

## 12 - Row #11 - Feeds that failed: distance-to-quarantine bar and a per-feed outcome strip

- **Scope:** The feed table is re-ranked by how close each feed is to quarantine, gains a target bar for that distance, and gains a per-feed run-outcome strip.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/charts/run-history.ts`
  - `frontend/tests/console-feeds.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, a quarantined feed and a healthy feed both render.
- **Oracle:** Assert the rendered quarantine marker position equals `quarantineAfter` read from the same source the pipeline reads, and that the printed failure count equals the pipeline's own consecutive-failure count, not a windowed recount.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Sorted by distance to quarantine, then by count. A feed at 4 of 5 is more urgent than one at 12 of 200 and currently sorts below it. | Susan |
  | 2 | A `TargetBar`: track is `quarantineAfter`, fill is failures, marker at the threshold. This is the second call site that makes `TargetBar` a component rather than a one-off. | Susan |
  | 3 | A per-feed outcome strip over the shared window, reusing `run-history.ts`. "Broken since Tuesday" and "flaky all month" are different jobs and the table cannot currently tell them apart. Susan rates this the highest-value single addition on the console. | Susan |
  | 4 | This is the one table row where the health ramp is legitimate, because quarantine is a health fact and the row already carries the word in text. | Susan |
  | 5 | `Last result` stays as free text. It is the only human-readable cause on the page and is never traded for a glyph. | Susan |
  | 6 | The count and the marker do NOT follow the window; the outcome strip does. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping `Asked` as its own column | The target bar's track length carries it. A column that repeats a bar's scale is a third statement of one fact. | Susan |
  | 2 | A per-feed source mark | A feed id is an identifier here, not a brand. Seventy marks would all mean "this is a feed". | Jony |

## 13 - Row #12 - Failed items to a failure ledger ranked by cause

- **Scope:** A cause-ranked ledger sits above the item list; the item list stays as the detail behind a selected cause.
- **Files touched:**
  - `frontend/src/lib/components/FailureList.svelte`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console-failures.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, selecting a cause filters the list, clearing restores it.
- **Oracle:** Assert the sum of the ledger's counts equals the number of failed rows in the window, and that selecting each cause in turn yields row sets that partition the list with no overlap and no remainder.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The unit of the row becomes a cause - a stage and code pair - because that is the unit of the decision. The item is the unit of the detail. Sorted newest-first, 25 rows of a 214-row spike are 25 rows of one code. | Susan |
  | 2 | Ledger columns: stage and code with a monochrome stage glyph; count with a bar-in-cell; a sparkline of that code's daily count; breadth as `sources hit: n of m`; and the newest occurrence as a relative day. | Susan |
  | 3 | Breadth is the column that separates "one source changed its markup" from "the extractor is broken". Today those two read identically. | Susan |
  | 4 | The `Item` column is dropped from the visible row. `item_id` is a content-addressed id, is the widest column, and no operator acts on it; it moves to the row title attribute. The operator loses page-level grepping of one id, which is a terminal job. | Susan |
  | 5 | The chip filter and the show-more cap are kept unchanged. Both are already right. | Susan |
  | 6 | The published projection withholds `detail`, so this table has no cause text and none is invented. Adding the column would be a persisted-contract change and is an ESCALATE trigger, not a row. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Sorting the existing item list by count | An item list has no count to sort by. The count belongs to the cause. | Susan |
  | 2 | Publishing `detail` to give the table a cause column | It is a persisted-contract change with a prompt-injection surface, since `detail` can carry fetched text. Out of scope by section 0. | Andre |

## 14 - Row #13 - Sources cut short to a length range plot with the cap drawn as a rule

- **Scope:** The source table becomes a horizontal range plot on a log word-length axis with the truncation cap drawn as a vertical rule across every row.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/charts/series.ts`
  - `frontend/tests/console-sources.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, a window with no cuts renders its own empty state.
- **Oracle:** Assert the drawn cap rule's x position equals the cap derived from the rows themselves, and that every article length drawn to the right of it is counted as cut. Derivation must not read the backend knob directly.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The cap goes on the chart. Five columns of numbers were unreadable because the single number they all had to be compared against appeared nowhere in the section. This is the whole defect. | Susan |
  | 2 | One row per source, log word-length axis, min / median / max as a track, one dashed rule across all rows at the cut point. Everything right of the rule is lost text, read spatially. | Susan |
  | 3 | The cap is derived from the rows the way the existing helper derives it, never read from the backend truncation knob, so the drawn rule cannot disagree with the data. | Fowler |
  | 4 | Counts move into the row label - `source - 17 of 38 cut` - preserving the count sort and keeping the denominator beside the figure. | Susan |
  | 5 | `Share cut` is dropped as a column. It is dashed below the minimum-attempts floor, it is explicitly not the sort key, and a rate ranking was already ruled wrong here. | Susan |
  | 6 | The cost sentence moves directly under the heading, above the chart, at body size. It is the most useful line in the section and is currently the smallest type on it. | Susan |
  | 7 | Follows the shared window; the sentence reads the same window the query reads, and the section prints its denominator. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the table and printing the cap in the intro sentence | Recorded as the fallback if the range plot overruns. It answers "how far past the cap" by subtraction rather than by looking. | Susan |
  | 2 | Tinting rows by share cut | A source at 55 percent is not broken; it publishes long articles. The tint would invent a fault. | Susan |
  | 3 | A linear word-length axis | Article lengths here span more than two decades; linear crushes every short source onto the axis. | Carmack |

## 15 - Row #14 - What the model did: eleven measure cards over a table on demand

- **Scope:** The eleven-column table becomes eleven small-multiple cards, each with today's figure, a sparkline and its own explanatory sentence; the daily table moves behind a control.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/components/KpiCard.svelte`
  - `frontend/tests/console-model.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, all eleven labels present verbatim, the daily table reachable and correct.
- **Oracle:** Assert the eleven card labels are byte-identical to the eleven strings in `COLUMNS`, and that each card's headline figure equals the newest day's cell for that key. A card that paraphrases a protected label fails the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The label copy is protected and ships verbatim, all eleven lines. The shape is the defect, not the words. | Owner, prior ruling |
  | 2 | Eleven cards on an `auto-fit minmax(220px, 1fr)` grid. A wide table is the one shape that cannot answer "did it get worse", because a trend is a vertical scan and every neighbouring column is a different quantity. At 30 days the table is 330 numbers and eleven header paragraphs. | Susan |
  | 3 | Each card carries the label, today's figure large, a sparkline over the window, the denominator beside it, and the explanatory sentence moved from the header into the body where there is room for it. | Susan |
  | 4 | A model-swap date draws a vertical rule on every sparkline. Whether a swap moved anything is the question the current table cannot answer at all. | Andre |
  | 5 | The daily table stays, below, behind a `Show the daily figures` control - the same shape-first pattern the failure list already uses. Nothing is deleted. | Susan |
  | 6 | The dash-not-zero rule, the `<1` rule, the denominator-beside-the-share rule and the version-stamped share all survive unchanged. | Owner, prior ruling |
  | 7 | No card gets a health tint. Copied-not-rewritten at 12 percent has no agreed threshold, and a tint would invent one and publish it. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Dropping columns to narrow the table | Every measure is one the operator asked for. The container is wrong, not the count. | Susan |
  | 2 | A single combined chart of all eleven series | Eleven series in one frame with four different units is unreadable at any size. | Jony |

## 16 - Row #15 - Charts drawn for articles: two target bars, a verdict sentence, rows on demand

- **Scope:** The chart-arm section leads with the two figures its own retirement rule names, each as a target bar with a sparkline, plus a one-sentence verdict; the daily table moves behind a control.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/tests/console-charts-arm.spec.ts`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, the 7-day window renders the widen-the-window notice instead of a median.
- **Oracle:** Assert the printed median equals a median computed independently over exactly 14 days, and that at a window below 14 days no median is printed at all.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | This is the only console section with a written decision rule in its own intro - retired above 6 router minutes per published chart, or below 5 percent coverage, over a 14-day median - and the table shows none of the three. Both thresholds become markers. | Susan |
  | 2 | Target bar A: minutes per chart, window median, marker at 6.0. Target bar B: coverage, window median, marker at 5 percent. A sparkline under each, because "4.2 and falling" and "4.2 and rising" are different pictures. | Susan |
  | 3 | One verdict sentence states both figures and whether each is inside its threshold. | Susan |
  | 4 | `Reached`, `Asked` and `Drafted` leave the top level; the Sankey from row #3 draws all three as segments. Raw router minutes leaves too; it is the numerator of the ratio that matters and is not a decision alone. Both are one control away. | Susan |
  | 5 | Below a 14-day window the section prints the widen-the-window notice and no median, per row #1 decision 8. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keeping the seven daily columns at the top level | Seven columns of counts against two constants requires the operator to compute a 14-day median of a ratio in his head. | Susan |
  | 2 | Colouring the target bars with the health ramp | These are policy thresholds, not health. The bar's marker carries the fact without borrowing a ramp that means something else. | Susan |

## 17 - Row #16 - Chart prose scrub: keep the sentence that decides, cut the sentence that narrates

- **Scope:** Every console section keeps the sentence that names a threshold, a denominator or a cost, and loses the sentence that describes what the chart is.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - all console components touched by rows #4 to #10
  - `docs/concepts/design-system.md`
- **Acceptance gates:** `svelte-check` 0 errors, browser smoke, every chart retains a non-empty accessible description.
- **Oracle:** Assert every chart still has an `aria-label` or `aria-describedby` resolving to non-empty text. Visible prose may be cut; the accessible description may not.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A sentence that names a threshold, a denominator, a cost or an empty-state reason is kept. A sentence that says what is being measured and why we measure it is cut; the heading already says it. | Owner, 2026-08-30 |
  | 2 | Prose cut from the visible page stays in the accessible description, so a screen-reader user loses nothing. | Jony |
  | 3 | Runs after the chart rows so it scrubs the final copy once, not a moving target eight times. | Fowler |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Scrubbing prose inside each chart row | Eight rows would each re-litigate the same rule and the last one would win. | Fowler |
  | 2 | Cutting all explanatory prose | The threshold sentences are the console's decision rules. Cutting them removes the only place the rules are written. | Susan |

## 18 - Row #17 - Closure: re-baseline bytes, re-measure the page, record the rulings

- **Scope:** Re-derive every byte number this plan moved, re-measure the console, and write the rulings into the living docs.
- **Files touched:**
  - `frontend/bundle-baseline.json`
  - `config/idhazh.json`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/frontend.md`
  - `docs/reference/measurements.md`
  - `TODO/20260830-console-signal-plan.md` (deleted at closure)
- **Acceptance gates:** full `pytest`, `ruff`, `mypy --strict`, drift gate, `svelte-check`, full browser suite, page-weight gate green against the re-derived ceiling.
- **Oracle:** Build five times, take the heaviest, and assert the recorded baseline equals it. A mean fires on half of all builds; the heaviest is the only value a gate can hold.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Baselines are re-derived only after every sibling row has merged, and the merged sha is recorded next to each number. A ceiling set from a stacked branch is stale the moment its parent lands. | Carmack |
  | 2 | Every new number carries hardware, date and spread per Rule #10. | Fowler |
  | 3 | The two reversals this plan makes - the shared ranked component, and the windowed source-cut section - are written into `docs/concepts/design-system.md` with the reason the earlier refusal no longer holds. | Fowler |
  | 4 | The console page height is re-measured against the 8,794px baseline and reported honestly whether or not it improved. The card grids and the on-demand tables move it in opposite directions. | Susan |
- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Re-baselining inside each row | Sixteen partial baselines, fifteen of them wrong the moment the next row merges. | Carmack |
  | 2 | Holding the current `/console/` ceiling | The owner relaxed the byte budget for this page on 2026-08-30. The ceiling is re-derived to the new artefact, with the reason recorded. | Owner |

## See also

- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [docs/concepts/design-system.md](../docs/concepts/design-system.md) - the doctrine rows #2, #13 and #17 amend.
- [docs/architecture/publishing/telemetry-series.md](../docs/architecture/publishing/telemetry-series.md) - the published column set that bounds row #12.
- [CLAUDE.md](../CLAUDE.md) - correction levels (section 6), anti-patterns (section 10), agent roster (section 14).
