# Console charts - real coordinates, real scales

**Last Updated**: 2026-08-25
**Level**: 4 (CLAUDE.md section 6 - structural, 4+ files, one new runtime dependency)

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 4; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every console chart declares pixel-looking numbers into a 360-unit viewBox that is then stretched, so text and strokes scale like a bitmap and no chart renders at its declared size. |
| Hard scope - in | The four console chart components; a shared coordinate/scale module; `d3-scale` + `d3-array`; a `console.chart_width` knob; categorical series tokens; a per-route gzip ceiling in the bundle gate; the doc sections those changes falsify. |
| Hard scope - out | The ~1.3 MB day payload `+layout.server.ts` inlines into every prerendered page. A frontend unit-test runner. The throughput model-swap mark. Any reader-facing digest surface. Any backend change. |
| ESCALATE triggers | (1) Measured gzip delta on the console route exceeds 10 KB. (2) Any reader route (`/`, `/<date>/`, `/<date>/<vertical>/`, `/archive/`) gains a single byte of first-load JS. (3) A row needs a persisted-contract change beyond the additive `console.chart_width` field. (4) A browser-suite assertion about reader-facing content has to change. |
| Chosen strategy | Scales, not a chart library: `d3-scale` + `d3-array` for nice domains and honest ticks; marks, SVG and prerendering stay ours. Ruled by Jony (surface) and Carmack (bytes), independently, on 2026-08-25; accepted by the owner the same day. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. |

### Measured baseline

Taken 2026-08-25 on this repository: `npm run build` in `frontend/`, then `gzip -9` over each route's HTML and its preloaded `_app/immutable` modules.

| Route | HTML gz | First-load JS gz | Modules |
| --- | --- | --- | --- |
| `/console/` | 268.9 KB | **52.9 KB** | 18 |
| `/` | 192.8 KB | 48.0 KB | 20 |
| `/2026-08-25/` | 374.7 KB | 47.9 KB | 20 |
| `/2026-08-25/ai/` | 372.5 KB | 48.0 KB | 20 |
| `/archive/` | 873.1 KB | 43.4 KB | 18 |

Console route chunk `nodes/4.*.js`: 37.4 KB raw / **12.4 KB gz**. Whole build 133.8 MB against the 1 GB cap.

Live console at a 1057 px window, every `viewBox` read against its `getBoundingClientRect()`:

| Chart | viewBox w | Rendered w | Scale | `font-size="10"` renders as | `stroke-width="1"` renders as |
| --- | --- | --- | --- | --- | --- |
| 3x failure panel | 360 | 163 px | 0.45x | 4.5 px | 0.45 px |
| compression scatter | 360 | 572 px | 1.59x | 15.9 px | 1.59 px |
| stage timings | 360 | 598 px | 1.66x | 16.6 px | 1.66 px |
| throughput candles | 360 | 598 px | 1.66x | 16.6 px | 1.66 px |

## 1. Status reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Coordinate frame, scales, tokens and a byte ceiling | - | A | PENDING | - | - | - |
| 2 | Throughput candles on the frame | 1 | B | PENDING | - | - | - |
| 3 | Stage timings on the frame | 1 | B | PENDING | - | - | - |
| 4 | Compression scatter on the frame | 1 | B | PENDING | - | - | - |
| 5 | Failure panels on the frame | 1 | B | PENDING | - | - | - |

## 2. Row #1 - Coordinate frame, scales, tokens and a byte ceiling

- **Scope:** Add the one module every chart will draw through, the dependency behind it, the knob it needs to prerender, the categorical colours it needs, and the gate that stops the next dependency arriving unpriced.
- **Files touched:**
  - `frontend/package.json`, `frontend/package-lock.json`
  - `frontend/src/lib/charts/frame.ts` (new)
  - `frontend/src/styles/tokens.css`
  - `frontend/scripts/bundle-gate.mjs`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json` (generated)
  - `config/idhazh.json`
  - `frontend/src/lib/server/config.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/frontend.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`, `mypy --strict`, `pytest`, contract export byte-identical, `npm run check`, `npm run build`, `npm run bundle-gate`, browser suite green (62 tests).
- **Oracle:** Measured gzip delta on `/console/` first-load JS is `<= 10 KB` **and** every reader route's first-load JS gz is byte-identical to the section 0 baseline. Both figures taken by the same script that produced the baseline, recorded in `measurements.md` with hardware and date.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `d3-scale` + `d3-array` only. They compute; they draw nothing. Marks, SVG and prerendering stay ours. | Jony + Carmack, 2026-08-25; owner accepted |
  | 2 | Self-hosted through the bundler. Never a CDN. | Carmack |
  | 3 | `frame.ts` exports the responsive width, the margin box, and the two domain rules. One module, so a chart cannot invent a fifth convention. | Fowler altitude, ruled by Jony |
  | 4 | SSR fallback width comes from a new `console.chart_width` knob, so the prerendered SVG has a real width before any script runs; the client redraws at the measured width. | Jony |
  | 5 | `console.chart_width` is additive with a default: `version` stamped, `changelog` entry appended, no read-side migration needed. | CLAUDE.md section 11 |
  | 6 | New `--series-1` through `--series-4`, a categorical ramp distinct from the semantic `--band-*` ramp. `--source-swatch-*` is not reused: it is a set of pale background tints for `SourceMark`, not stroke colours. | Jony |
  | 7 | `bundle-gate.mjs` grows a per-route gzipped ceiling beside its existing encoder string check. A repo with no byte gate has no defence against the next 336 KB request. | Carmack, as a condition of approving the dependency |
  | 8 | `design-system.md`'s "There is no chart library, on any surface" is amended, not deleted: it becomes "no chart library; a scale library is not a chart library", with the uplot removal left standing. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | `echarts` | 336 KB gz, 6.4x the console's entire first-load JS. Canvas: cannot prerender, cannot inherit a CSS custom property. | Carmack (bytes), Jony (canvas) |
  | 2 | `@observablehq/plot` | 128 KB gz. Needs a DOM shim to prerender, and three of four charts are bespoke marks it would not shorten. | Carmack, Jony |
  | 3 | `chart.js` | 67 KB gz, canvas, same two disqualifications. | Carmack, Jony |
  | 4 | `uplot` | 21.9 KB gz, and it was already carried between 2026-08-23 and 2026-08-24 and removed in #57. Its recorded beneficiary was pan and zoom, which `Viewport.svelte` implements itself. Re-adding it re-litigates a settled decision on grounds bytes cannot overturn. | Jony, recorded in `frontend.md` |
  | 5 | `LayerChart` | Svelte 5 and SVG, the closest real fit, but a component library is at its worst when every chart is bespoke. | Jony |
  | 6 | Any library from a public CDN | Partitioned HTTP cache since Chrome 86 / Firefox 85 / Safari ITP 2.1 makes a cross-site cache hit impossible, so it is a cold fetch for 100% of first-time visitors. `svelte.config.js` ships `script-src: ['self', 'wasm-unsafe-eval']`, which blocks it before the cache is consulted. Widening the CSP buys nothing. | Carmack |
  | 7 | Borrow yen-gov's `lib/colors/` wholesale | It resolves an unbounded, data-driven category set (36-hue OkLCh, curated anchors, hash fallback) for political parties. The console has four named series and three health bands, a closed set. Borrow the idea - read a themeable token first, fall back to a constant - not the code. | Jony |
  | 8 | Fix the units without the dependency | Would ship the same zero-based axes and hand-rolled tick arithmetic the owner is looking at. `.nice()` and `ticks()` are the part we get wrong by hand. | Owner, 2026-08-25 |

## 3. Row #2 - Throughput candles on the frame

- **Scope:** Redraw `ThroughputTrend` through `frame.ts`, on a padded domain, with the second y scale removed.
- **Files touched:**
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console.spec.ts`
  - `docs/architecture/summarize/throughput.md`
- **Acceptance gates:** `npm run check`, `npm run build`, browser suite green, and a before/after screenshot pair at 380 px, 768 px and 1400 px.
- **Oracle:** `viewBox` width equals `getBoundingClientRect().width` to within 1 px at all three widths, so every declared `font-size` renders at that number of CSS pixels.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The y domain is the drawn extent rounded outward by `.nice()`, not zero-anchored, and both endpoints are printed. Zero belongs on an axis only when the mark's LENGTH encodes the value. A candle encodes by position. Measured cost of the current rule: the read whisker occupies 17.5% of plot height and the interquartile box 3.7%. | Jony |
  | 2 | The prompt-reuse line and its right-hand 0-100% axis are deleted. A second y scale on a tokens-per-second chart invites a correlation that does not exist; prompt reuse is a cache statistic. The number stays in the legend. | Jony |
  | 3 | Axis furniture is rendered by its series. A series with nothing to draw takes its axis, ticks and legend entry with it - unconditionally, not only when the window holds one day. | Jony |
  | 4 | A one-day chart still draws the candle. Min, p25, median, p75, max is five numbers and a real shape. It drops the calendar axis and prints the date as one label. | Jony |
  | 5 | The per-mark `<title>` stays. `console.spec.ts` binds to its text at line 385, and promoting tooltips to a pinned readout is a separate change nobody asked for. No new `<title>` is added. | This plan; Jony preferred deletion |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep the zero-anchored domain | Spends 82% of the plot on 0 tok/s, a value that means "did not run", on a chart whose stated job is showing spread. | Jony |
  | 2 | Draw a single marker for prompt reuse on a one-day window | One point compares to nothing. A lone point is drawn only when it shares a scale with a series it can be compared against. | Jony |
  | 3 | Hide the whole chart until two days exist | Five order statistics per series is a real shape on day one; hiding it would have hidden a working instrument for a month. | Jony |
  | 4 | Delete the per-mark `<title>` nodes now | Would rewrite browser assertions for a tooltip redesign outside this plan's scope. Recorded so the next reader knows it is deferred, not overlooked. | This plan |

## 4. Row #3 - Stage timings on the frame

- **Scope:** Redraw `StageTimings` through `frame.ts` and stop colouring stage categories with health-band tokens.
- **Files touched:**
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/tests/console.spec.ts`
- **Acceptance gates:** `npm run check`, `npm run build`, browser suite green, before/after screenshots at three widths.
- **Oracle:** `viewBox` width equals rendered width to within 1 px at all three widths, and no `--band-*` token appears as a series colour anywhere in the component.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `fetch` moves off `--band-low` and `score` off `--band-high` to `--series-*`. On a page where those tokens mean run health, a red fetch line and a green score line read as "fetch is broken, score is fine" when they only mean "these are four different stages". | Jony |
  | 2 | The y domain follows Row #2 decision 1: padded, `.nice()`, both endpoints printed. Milliseconds are encoded by position. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep the band tokens and add a legend note | A legend cannot undo the colour a reader has already read. | Jony |
  | 2 | Reuse `--source-swatch-0..7` | Pale background tints sized for a `SourceMark` chip; they have no contrast as strokes on `--color-surface`. | Jony |

## 5. Row #4 - Compression scatter on the frame

- **Scope:** Redraw `CompressionScatter` through `frame.ts`, give it the y axis it has never had, and collapse its per-point reference lines into step paths.
- **Files touched:**
  - `frontend/src/lib/components/CompressionScatter.svelte`
  - `frontend/tests/console.spec.ts`
- **Acceptance gates:** `npm run check`, `npm run build`, browser suite green, before/after screenshots at three widths.
- **Oracle:** The band reference renders as at most 4 `<path>` nodes for any point count, verified in the browser against the current 447, and every plotted point's y position is unchanged from the pre-change render.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One vertical `<line>` per point becomes one step `<path>` per band boundary. `bandFor()` resolves to one of 3-4 bands, so 447 lines carry the information of 4. Measured today: 447 nodes for a 4-node fact. | Jony (design), Carmack (nodes) |
  | 2 | The x axis becomes a real `scaleLog` with minor ticks. It is logarithmic today and reads as linear because the ticks are hand-picked. | Jony |
  | 3 | The chart gains a y axis. "summary words" is currently printed at x=282 on the bottom row, so the y variable is labelled on the x axis - which is why the chart reads as unfinished rather than as ugly. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Reduce the per-point line opacity | The wash is a node-count problem, not an alpha problem. 447 overlapping strokes at any opacity is not a reference line. | Jony |
  | 2 | Restore `uplot` for this chart specifically | This is the exact chart it was removed from in #57, for reasons this plan does not overturn. | Jony, recorded in `frontend.md` |

## 6. Row #5 - Failure panels on the frame

- **Scope:** Redraw the three `FailurePanels` sparklines through `frame.ts` at their true 163 px width, keeping their fixed domain.
- **Files touched:**
  - `frontend/src/lib/components/FailurePanels.svelte`
  - `frontend/tests/console.spec.ts`
- **Acceptance gates:** `npm run check`, `npm run build`, browser suite green, before/after screenshots at three widths.
- **Oracle:** `viewBox` width equals rendered width to within 1 px, so the panel's labels render at 10 px rather than the measured 4.5 px and its strokes at 1 px rather than 0.45 px.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | These panels keep their full 0-100% domain. A rate over a known range is compared across panels and across days, so a padded domain would break the comparison the panel exists for. This is the second clause of the domain rule and it stops Row #2's rule being over-applied. | Jony |
  | 2 | The unlabelled 50% dashed reference is deleted. An unlabelled reference at a value nobody acts on is decoration. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Pad these domains too, for consistency with Row #2 | Consistency of mechanism over consistency of meaning. The panels are already correct. | Jony |
  | 2 | Label the 50% line instead of deleting it | Nothing in the pipeline acts on a 50% stage failure rate; `run.success_floor_pct` is 70 and is a different measurement. A reference nobody acts on earns no ink. | Jony |

## 7. Findings outside this plan's scope

Recorded because each was measured while writing it, and each is larger than anything above.

| Finding | Measured | Why it is out of scope here |
| --- | --- | --- |
| `frontend/src/routes/+layout.server.ts` returns `day: loadDay(latest)`, inlining the whole latest-day payload into every prerendered page including `/console/`, whose page component never reads it | roughly 1.3 MB of HTML per page | A load-function and payload-shape change, not a chart change. Two orders of magnitude larger than this entire plan. |
| `/archive/` ships 873.1 KB gzipped HTML, the heaviest route on the site | measured 2026-08-25 | Same cause as above; belongs with it. |
| The frontend has no unit-test runner, so a pure charting rule can only be proved through a browser | `frontend/tests/` is 62 Playwright tests, zero `*.test.ts` | A tooling decision. yen-gov uses vitest and is the precedent to copy. |
| The console receives its telemetry rows twice: inlined as `initialRows` and fetched as monthly CSVs by the viewport | roughly 1000 rows | A data-flow change on the console load function. |

## See also

- [`../docs/concepts/design-system.md`](../docs/concepts/design-system.md) - the chart rules Row #1 amends.
- [`../docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the uplot removal Rows #1 and #4 leave standing.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - where the bundle figures land.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the contract the stamp above points at.
