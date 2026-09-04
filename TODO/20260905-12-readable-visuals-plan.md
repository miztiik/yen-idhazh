# 12 - Visuals a reader can read

**Last Updated**: 2026-09-05
**Level**: 4 (structural: the rendering engine, the drawn surface, and two build-failing floors)

**Chain**: previous [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) | next [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O4, O5, O18, O19, O20, O36, O47, rows 22 to 37, sections 2.2, 7, 7.2, 7.5.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 01 made the chart's colours readable. It is still drawn on a fixed 825 by 437 canvas, so on a 390 CSS px phone it scales to about 0.31x and a 10px axis label draws at about **3.1 CSS px** - below the smallest type on the site at every supported width. That is not a taste complaint; it is a chart whose labels nobody can read. This plan replaces the renderer and makes "can a person read it" a gate rather than an opinion |
| Hard scope - in | d3 replaces Vega-Lite and `vl-convert` for every type the planner can already emit; the drawing takes the width it is given; the legibility floor and the density floor as **build-failing** oracles; the number formatter; caption and one annotated mark; the whole-day look repeated |
| Hard scope - out | Any new visual type (plans 15 to 18). The byte cap, the keyboard route and hydration byte-identity (plan 14). The console (plan 20). Migrating the console's own charts - it keeps its engine and has no complaint against it |
| ESCALATE triggers | 1. The legibility floor cannot be satisfied at 390 CSS px without dropping data the plan selected - that is a planning problem, not a drawing one, and it goes back to plan 10's validator. 2. A per-type bespoke component is proposed - the payload's own metadata is the design system. 3. Removing `vl-convert` moves a published byte other than through the intended redraw |
| Chosen strategy | Engine first, behind the same call site and output-comparable; then the page work; then the floors that make it checkable. Engine swap and layout are different hats and never share a commit |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Why the floors are in this plan and not the next.** A phase boundary is a place work stops. Full-width reflow **without** a legibility floor makes the wide end worse rather than better, and a check a person can skip is the one skipped on the day it would have bitten. Susan ruled the two floors into this plan on 2026-09-05; the byte cap and the hydration check may stand alone.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A new engine behind the same seam | - | A | PENDING | - | - | - |
| 2 | The drawing takes the width it is given | 1 | B | PENDING | - | - | - |
| 3 | Numbers a reader can say out loud | 1 | B | PENDING | - | - | - |
| 4 | The smallest label a person can read, and enough marks to be worth the space | 2, 3 | C | PENDING | - | - | - |
| 5 | A caption, and one mark that lands first | 4 | D | PENDING | - | - | - |
| 6 | A whole day, again | 5 | E | PENDING | - | - | - |

---

## 2. Row #1 - A new engine behind the same seam

- **Scope:** d3 emitters replace Vega-Lite and `vl-convert` for every type the planner can emit today, behind the same render call site.
- **Files touched:** `frontend/src/lib/charts/**` or a new digest-visual module, `backend/idhazh/render/chart.py` (retired), `pyproject.toml` (`vl-convert` removed), `frontend/package.json` (exact-pinned d3 modules), `backend/tests/test_render.py`, `frontend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite; `npm run check`; build; `bundle-gate`; the browser suite.
- **Oracle:** The same plan rendered twice **in one process and once in a fresh process** produces byte-identical output after rounding. Determinism is the property a build-time renderer must have, and one process cannot prove it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **d3, not ECharts**, for digest visuals: entity-derived colour per mark, non-standard marks, no fixed canvas, node-edge layout, and only the modules used are shipped. The cost is stated plainly - axis, legend and tooltip behaviour we author rather than inherit | O5, section 7 |
| 2 | `d3-array` and `d3-scale` are **already dependencies**, so the install cost is lower than the source document implies. What is added is the shape, axis and layout modules | C21, verified 2026-09-05 |
| 3 | **Exact-pin every d3 module.** A caret range lets a patch bump change pixels with no diff to review. Record the set in `renderer_version` | Row 24 |
| 4 | The build step emits markup as strings, so no DOM is needed at build time and `d3-selection` appears only on the hydrated path | Section 7.2 |
| 5 | A renderer bump re-renders **whole days or none.** Otherwise one page shows two drawing styles in one scroll, which reads as a broken site | Row 35 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep Vega-Lite and fix the canvas | The colour is baked in by the backend, the canvas is fixed, and per-mark authored colour is not available. Plan 01 bought the colour; the rest needs the engine | Jony |
| 2 | Use ECharts, as the console does | Series colour is a chart-level concept there and fights per-mark authoring; and a hydrated route ships the whole engine | Jony, section 7.1 |
| 3 | Migrate the console too | 23 test files, a working sentinel bridge, no complaint against it. A separate decision if it is ever wanted | Section 7.4 |

---

## 3. Row #2 - The drawing takes the width it is given

- **Scope:** No fixed canvas. The box is a function of what is encoded and the space available, on phone, tablet and desktop.
- **Files touched:** `frontend/src/lib/charts/**`, `frontend/src/lib/components/ItemVisual.svelte`, `config/idhazh.json` (`visuals.canvas_width` retired), `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke at 360, 390 and 1440 in both themes.
- **Oracle:** At three widths, the drawn plot's width is within a stated tolerance of the container's content width - measured in a real browser, not asserted from the CSS.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The page uses the full width available on every medium. No fixed canvas, no fixed pixel constraint | O18, row 25 |
| 2 | **There is no `canvas_height`.** The block holds `canvas_width` alone, plus four knobs no row names - `max_chart_points`, `max_facts`, `max_diagram_steps`, `min_diagram_steps`. Each must move or die with the renderer | C18, verified 2026-09-05 |
| 3 | Measured 2026-09-02: committed charts are 825 by 437 in an 890px card body. A fixed 16:10 box previously reserved 85px of empty band above and below every one | Section 2.2, `ItemVisual.svelte` |
| 4 | The reading page is two contexts - a seed item is prerendered and a past-seed item is drawn after a fetch - and **one code path draws both** | Row 37 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A responsive canvas at three fixed sizes | Three canvases is three sets of the same defect | Susan |

---

## 4. Row #3 - Numbers a reader can say out loud

- **Scope:** The display formatter: SI prefixes, one declared locale applied at build time, declared precision, shared by the compiler and the console.
- **Files touched:** a shared formatter module under `frontend/src/lib/`, `config/idhazh.json` (`visuals.number_format`), `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/src/lib/charts/**`, `frontend/src/lib/console/**`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `npm run check`; build; `bundle-gate`; the browser suite.
- **Oracle:** The same value formatted by the digest path and by the console path returns the identical string, asserted over a table of magnitudes spanning thousands to trillions. **Two formatters is how `2M` and `2,000,000` end up on one page**, and only a cross-path assertion catches it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | SI, and metric, wherever a quantity has an SI form: `2M tokens`, not `2,000,000 tokens`. **The prefix set is the SI set and nothing else** - no `bn`, no `lakh`, no `crore`, because each is read differently by a different part of the audience | O47, section 7.5 |
| 2 | **One declared locale, at build time.** `1.234` is one thousand two hundred and thirty-four in Berlin and slightly more than one in London. Reading the reader's browser would make two readers see different bytes, which breaks byte identity and is the reader-varying behaviour Rule #1 refuses | O47 |
| 3 | Precision is declared in config, so `2M` versus `2.4M` is a decision and not an accident of the input | O47 |
| 4 | **Formatting is not a derived value** and needs no provenance - nothing about the quantity moved. `convert` is, and it landed in plan 10 | O47, O45 |
| 5 | `d3-format` and `d3-time-format` are already named in the module matrix and do the prefix and precision rules with no code of ours | Section 7.5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Detect the reader's locale at runtime | Two readers see different bytes; the byte-identity oracle breaks; Rule #1 refuses reader-varying behaviour | O47 |
| 2 | Per-chart formatting | The path to `2M` and `2,000,000` on one page | Susan |

---

## 5. Row #4 - The smallest label a person can read, and enough marks to be worth the space

- **Scope:** Two build-failing oracles: the legibility floor and the density floor.
- **Files touched:** `frontend/src/lib/charts/**`, `frontend/tests/visual-sufficiency.spec.ts` (new), `config/idhazh.json`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke at every supported width.
- **Oracle:** For every drawn visual on a real committed day, the smallest drawn string's **computed** font size clears the site's smallest type **after** the scale-to-fit, at 360, 390 and 1440. Computed, not declared - the whole defect is that a declared 10px draws at 3.1.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These are **compiler oracles, not review items.** A check a person can skip is the one skipped on the day it would have bitten | O36, Susan |
| 2 | Measured 2026-09-02: 10px axis labels draw at about **3.1 CSS px** on a 390px phone, below the smallest type on the site at every supported width | Section 2.2 |
| 3 | The size ratio ships as **`density_floor`**. The semantic measure keeps the name `information_delta` - a size ratio carries no semantics and says nothing about faithfulness | Row 27, owner |
| 4 | Both floors live in this plan, not the next, because full-width reflow without a legibility floor makes the wide end worse | Susan, 2026-09-05 |
| 5 | A shortened number is still a drawn label and faces this floor unchanged. Making a number shorter is not a licence to set it smaller | O47 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Advisory checks in review | The programme has already converged once on the minimum that passed every review - a surface using 40.6 percent of a 1536px screen | Susan |
| 2 | Defer the floors to the sufficiency plan | A phase boundary is a place work stops, and this is the phase that changes the widths | Susan |

---

## 6. Row #5 - A caption, and one mark that lands first

- **Scope:** The figure renders `title` and `caption` when present, and every visual carries at least one annotation drawn differently from its siblings.
- **Files touched:** `frontend/src/lib/components/ItemVisual.svelte`, `frontend/src/lib/charts/**`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** as row 4.
- **Oracle:** Every published visual has exactly one annotated mark whose computed style differs from its siblings in at least one channel - asserted per visual on a real day, not on a fixture.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `title` and `caption` have **no home today** - the figure renders an image and nothing else. Caption is optional and rendered when present | Row 29, O20 |
| 2 | One mark lands first. **Eight bars of equal weight have no reading order** | Row 30 |
| 3 | Colour comes from the closed token set by default; an entity-derived palette may be proposed and degrades to the token ramp, and derived colours are still contrast-checked in both themes | Row 28, O19 |
| 4 | Empty stays empty: no placeholder, no reserved slot, no skeleton. Already true, written down so the downgrade ladder cannot reintroduce it | Row 34 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let every mark be equal | Then the reader has to find the point themselves, which is the work the visual was supposed to do | Susan |

---

## 7. Row #6 - A whole day, again

- **Scope:** Plan 01's whole-day browser check re-run against the new renderer, at day scale, both themes, phone and desktop.
- **Files touched:** `frontend/tests/whole-day.spec.ts`, `docs/how-to/run-the-gates.md`, `docs/reference/measurements.md`
- **Acceptance gates:** the browser suite; the section 12 smoke; `idhazh site-weight`.
- **Oracle:** On the heaviest committed day: zero console errors, zero responses at 400 or above, zero horizontal overflow, every visual clearing both floors, **and more than one rendered type on the page**. A day publishing a single shape is a recorded defect, and only a day-scale check can see it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is the check no per-visual oracle can make. A per-visual gate cannot see a grey wall, a page that never settles, or 80 charts of identical width stacked | Susan, 2026-09-05 |
| 2 | The largest committed day carries 621 items, so motion must be tokenised, bounded and killable - 621 entrance animations is a page that never settles | Row 32 |
| 3 | A single-shape day is recorded as a defect and read jointly with keep rate. It is not a diversity target | Row 49 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Trust the per-visual floors | They pass individually on a page that is a wall of identical drawings | Susan |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) - the previous plan.
- [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) - the next plan.
