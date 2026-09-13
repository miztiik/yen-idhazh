# 12 - Visuals a reader can read

**Last Updated**: 2026-09-13
**Level**: 5 (core design: where a drawing becomes pixels, a persisted contract, the drawn surface, and two build-failing floors)

**Chain**: previous [`20260905-11-two-call-planner-plan.md`](20260905-11-two-call-planner-plan.md) | next [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O4, O5, O18, O19, O20, O36, O47, rows 22 to 37, sections 2.2, 7, 7.2, 7.5.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 01 made the chart's colours readable. It is still drawn on a fixed 825 by 437 canvas, so on a 390 CSS px phone it scales to about 0.31x and a 10px axis label draws at about **3.1 CSS px** - below the smallest type on the site at every supported width. That is not a taste complaint; it is a chart whose labels nobody can read. This plan replaces the renderer and makes "can a person read it" a gate rather than an opinion |
| Hard scope - in | d3 replaces Vega-Lite and `vl-convert` for every type the planner can already emit, **drawn in the reader's browser from data the payload carries**; the drawing takes the width it is given; the legibility floor and the density floor as **build-failing** oracles; the number formatter; caption and one annotated mark; the whole-day look repeated |
| Hard scope - out | Any new visual type (plans 15 to 18). The byte cap, the keyboard route and hydration byte-identity (plan 14). The console (plan 20). Migrating the console's own charts - it keeps its engine and has no complaint against it |
| ESCALATE triggers | 1. The legibility floor cannot be satisfied at 390 CSS px without dropping data the plan selected - that is a planning problem, not a drawing one, and it goes back to plan 10's validator. 2. A per-type bespoke component is proposed - the payload's own metadata is the design system. 3. **Restated 2026-09-13 under the owner ruling.** It read: removing `vl-convert` moves a published byte other than through the intended redraw. Every drawing a reader receives moves now, by design, so the old trigger would fire on the intended change and catch nothing. What escalates instead is a day whose **marks** move - a published spec that draws a different number, a different count of marks, or a different order from the SVG it replaces. That is a compiler defect wearing a renderer's clothes. 4. The d3 modules the reading page now ships push it past its `page_weight` entry and the entry cannot be justified on what the reader gains |
| Chosen strategy | **Contract first, then the engine, then the page, then the floors.** The payload learns to carry the chart's data while the old renderer still runs and nothing a reader sees moves; then the browser starts drawing and the renderer is deleted in one commit; then the layout work; then the floors that make it checkable. Contract, engine and layout are three different hats and no two share a commit |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

**Why the floors are in this plan and not the next.** A phase boundary is a place work stops. Full-width reflow **without** a legibility floor makes the wide end worse rather than better, and a check a person can skip is the one skipped on the day it would have bitten. Susan ruled the two floors into this plan on 2026-09-05; the byte cap and the hydration check may stand alone.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1a | The payload carries the chart's data, and nothing draws it from there yet | - | A | PENDING | - | - | - |
| 1b | The browser draws the chart, and the pipeline stops rendering | 1a | B | PENDING | - | - | - |
| 2 | The drawing takes the width it is given | 1b | C | PENDING | - | - | - |
| 3 | Numbers a reader can say out loud | 1b | C | PENDING | - | - | - |
| 4 | The smallest label a person can read, and enough marks to be worth the space | 2, 3 | D | PENDING | - | - | - |
| 5 | A caption, and one mark that lands first | 4 | E | PENDING | - | - | - |
| 6 | A whole day, again | 5 | F | PENDING | - | - | - |

**Row #1 became rows #1a and #1b on 2026-09-13, and the plan gained a group.** The owner ruled
that the reader's browser draws the chart and the pipeline never does
([`../docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md)).
That makes the old row #1 a contract change and a renderer deletion in one commit, which are
different hats and never share one (section 0). The contract lands first so the engine row is a
deletion plus a drawing over data already on the wire.

---

## 2. Row #1a - The payload carries the chart's data, and nothing draws it from there yet

- **Scope:** `DigestVisual` gains the compiled spec - the data and its shape - and `renderer_version`. Both are additive and optional. The pipeline still renders SVG exactly as it does today and the page still reads the file, so no drawing a reader receives moves in this row.
- **Why this is a row of its own.** The ruling adds a persisted contract and deletes a renderer. Landing them together gives any failure two suspects. Landing the contract first means row #1b is a deletion plus a drawing over data that is already on the wire and has already been proved to reproduce what the old renderer drew - which is an oracle row #1b cannot have once the SVG is gone.
- **Files touched:** `backend/idhazh/contracts/digest_day.py`, `schemas/digest-day.schema.json`, `backend/idhazh/contracts/visual_decision.py`, `schemas/visual-decision.schema.json`, `backend/idhazh/render/write.py`, `frontend/src/lib/payload/types.ts`, `backend/tests/test_contracts.py`, `backend/tests/test_render.py`, `tests/fixtures/contracts/digest-day/two-runs.json`, `docs/architecture/publishing/visuals.md`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite; export + drift; `npm run check`; build. Plus:
  - both schemas carry today's `version` and a `changelog` entry. **`schemas/digest-day.schema.json` already carries a `2026-09-13` stamp** from plan 25 row #8, so today's stamp is the minute form `2026-09-13T<HH>:<MM>`; a bare repeat raises `TypeError` at import from `backend/idhazh/contracts/base.py`;
  - the new fields are **optional and absent reads as "no data carried"**, because every committed day predates them and none is rewritten;
  - `frontend/src/lib/payload/types.ts` is **edited by hand**. There is no TypeScript generator, no `frontend/src/contracts/` directory and no emitter for it under `frontend/scripts/` - the file's own header says it mirrors the schema, and the drift gate covers `schemas/` only. Verified 2026-09-13. A worker who runs an export and sees no diff has proved nothing about this file;
  - **no committed `.svg` file changes and no published path moves.** This is the row's own safety property and it is asserted, not assumed.
- **Oracle:** **The data on the wire redraws the picture the old renderer drew.** On a built fixture day, for every rendered visual, the published spec's marks match the committed drawing's - same count, same values, same order. Built from a fixture, never walked over the committed archive (`CLAUDE.md` section 13, Guardrail #12). **This is the row's whole reason to exist**: it is the last moment at which the old output and the new input can be compared at all.
- **What this row does not do:** it does not draw anything from the new fields, delete a renderer, remove a dependency, or move a byte a reader receives.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The spec is the data and its shape, never geometry or an authored string.** The plan contract already forbids geometry, literal values and authored text, and publishing the compiled spec must not become the hole that lets one through. What travels is what the compiler derived from Tier 1 elements | Owner ruling 2026-09-13; `visual.py`'s plan prohibitions |
| 2 | **`renderer_version` is minted here, not in #1b.** The ruling's named cost is that a drawing stops being an archival artefact - a later code change can redraw history with nothing in the payload to show it moved. The field is what makes that visible, so it lands with the data rather than with the drawing | Owner ruling 2026-09-13 |
| 3 | **`path` stays in this row.** Retiring it while the renderer still writes files would leave a page that cannot find its drawing. It retires in #1b, with the renderer, in one commit | `CLAUDE.md` Guardrail #5 |
| 4 | **`VisualDecision.spec` stops being described as Vega-Lite JSON in this row**, because the description is a persisted contract's meaning and #1b changes what the field holds. A shifted meaning is a breaking change and ships its read side in the same commit | `CLAUDE.md` section 11 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Publish the Vega-Lite spec as-is and let the browser interpret it | It ships the grammar this plan is removing, to the reader, on every page. The spec that travels is the compiled data the d3 emitters read | O4, O5 |
| 2 | Skip this row and land the contract with the engine | One commit, two suspects, and the comparison against the old drawing becomes impossible the moment the drawing is deleted | Fowler |
| 3 | Keep the spec in `backend/var/` and have the browser fetch it from there | `backend/var/` is gitignored and the payload is a one-day artifact. It is unreachable 24 hours after a run, which is the defect the ruling names | `visuals.md` |

---

## 3. Row #1b - The browser draws the chart, and the pipeline stops rendering

- **Scope:** d3 draws the chart in the reader's browser from the data row #1a put on the wire. The build-time renderer, `vl-convert`, the committed SVG files, `DigestVisual.path` and the controls that exist only because two runs write the same file all retire here.
- **Files touched:** a new digest-visual module under `frontend/src/lib/` - **not** `frontend/src/lib/charts/**`, which is the console's own engine and which rejected alternative 3 says is not migrated; `frontend/src/lib/components/ItemVisual.svelte`; `frontend/package.json` (exact-pinned d3 modules); `backend/idhazh/render/chart.py` (deleted); `backend/idhazh/render/write.py`; `backend/idhazh/render/__init__.py`; `backend/idhazh/retention.py`; `backend/utilities/drop_raced_assets.py` (deleted); `backend/idhazh/stages/validate_days.py`; `pyproject.toml` (`vl-convert-python` and the `vl_convert.*` mypy override removed); `backend/idhazh/contracts/digest_day.py` and `schemas/digest-day.schema.json` (`path` retired); `backend/tests/test_render.py`; `frontend/tests/**`; `docs/architecture/publishing/visuals.md`; `docs/concepts/design-system.md`
- **The 495 committed drawings - 6.01 MB, mean 12.4 KB each, measured 2026-09-13 - are deleted in a commit of their own inside this row.** A 6 MB asset deletion and a new renderer in one diff is a diff nobody can review; split, one of them is a deletion anybody can check by counting.
- **Acceptance gates:** `ruff`; `mypy --strict`; the full suite; export + drift; `npm run check`; build; `bundle-gate`; the browser suite. Plus:
  - the reading page's `page_weight` entry is **re-baselined in the same commit**, and every d3 module the page now ships is named with its byte cost and its beneficiary feature (Guardrail #8). Every module in the section 7.2 matrix now reaches the reader, which is what makes row 36's per-visual byte cap load-bearing rather than a formality;
  - `docs/how-to/run-the-gates.md` loses any step that depends on the retired renderer;
  - `schemas/digest-day.schema.json` carries today's `version`, a `changelog` entry, and the read-side migration for a payload that still carries `path`.
- **Oracle:** **the same data drawn twice in one page session and once in a fresh page load produces the same marks** - same count, same values, same positions after rounding. This is the surviving form of the old row's oracle. The old one compared two build-time renders in one process and in a fresh one, and it cannot be asked once no file is written; determinism moves to the data and the drawing code, which is where the architecture record already argued it belongs.
- **A second oracle, because the first one cannot see the reader:** with the digest page open at 390 CSS px, every drawn string resolves at or above `--text-xs`. This row asserts only that the browser path can be **measured** at all - enforcing the floor is row #4's job, and row #4 cannot start until something measurable is drawing.
- **What this row does not do:** it does not change which stories get a visual, the plan the model writes, the validator, the downgrade ladder, the sufficiency bar, or the console's own charts.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The reader's browser draws the chart and the pipeline never draws one.** The full ruling, with both costs named, is in [`../docs/architecture/publishing/visuals.md`](../docs/architecture/publishing/visuals.md). It supersedes pseudo-plan row 22 and retires row 31 | Owner, 2026-09-13, under `CLAUDE.md` section 0 |
| 2 | **A reader with JavaScript off gets no chart**, where today they get one. Named here because a veto that removes must say what the reader loses, and this row is where the loss actually lands | Owner ruling 2026-09-13; `CLAUDE.md` section 14 |
| 3 | **d3, not ECharts**, for digest visuals: entity-derived colour per mark, non-standard marks, no fixed canvas, node-edge layout, and only the modules used are shipped. The cost is stated plainly - axis, legend and tooltip behaviour we author rather than inherit | O5, section 7 |
| 4 | `d3-array` and `d3-scale` are **already dependencies**, so the install cost is lower than the source document implies. What is added is the shape, axis and layout modules, and now `d3-selection`, which the matrix put on the hydrated path when there was one | C21, verified 2026-09-05; corrected 2026-09-13 |
| 5 | **Exact-pin every d3 module.** A caret range lets a patch bump change pixels with no diff to review. The set is recorded in `renderer_version`, which row #1a minted. The two modules already present are caret-ranged and repinning them moves the console's lockfile too - that is a cost of this row, not a reason to skip the pin | Row 24; verified 2026-09-13 |
| 6 | **A renderer bump re-renders whole days or none.** Under the ruling this stops being a build step and becomes a `renderer_version` the page reads: one page must not draw two styles in one scroll, which reads as a broken site | Row 35 |
| 7 | **The prerendered routes are untouched.** Prerendering a route and prerendering a chart are different acts and only the second one ends here | `TODO/20260911-26-retire-prerender-plan.md` |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep Vega-Lite and fix the canvas | The colour is baked in by the backend, the canvas is fixed, and per-mark authored colour is not available. Plan 01 bought the colour; the rest needs the engine | Jony |
| 2 | Use ECharts, as the console does | Series colour is a chart-level concept there and fights per-mark authoring; and the reading page would ship the whole engine | Jony, section 7.1 |
| 3 | Migrate the console too | 23 test files, a working sentinel bridge, no complaint against it. A separate decision if it is ever wanted | Section 7.4 |
| 4 | Keep the build-time SVG as a no-JavaScript fallback | Two renderers, permanently, kept identical by a control nobody has ever tested - which is what pseudo-plan row 31 asked for and what the ruling retires. It also keeps every byte the ruling removes | Owner ruling 2026-09-13; `CLAUDE.md` Guardrail #5 |
| 5 | Run d3 in Node at build time so the pipeline still emits SVG | Installs Node and an `npm ci` in **every** shard of the sharded `work` job, and puts a Python process across the backend/frontend boundary `CLAUDE.md` section 4 calls a structural invariant. It also buys none of what the ruling buys: the canvas is still fixed at build time | Owner ruling 2026-09-13; `CLAUDE.md` section 4 |

---

## 4. Row #2 - The drawing takes the width it is given

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

## 5. Row #3 - Numbers a reader can say out loud

- **Scope:** The display formatter: SI prefixes, one declared locale applied at build time, declared precision, shared by the compiler and the console.
- **Files touched:** a shared formatter module under `frontend/src/lib/`, `config/idhazh.json` (`visuals.number_format`), `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `frontend/src/lib/charts/**`, `frontend/src/lib/console/**`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `npm run check`; build; `bundle-gate`; the browser suite.
- **Oracle:** The same value formatted by the digest path and by the console path returns the identical string, asserted over a table of magnitudes spanning thousands to trillions. **Two formatters is how `2M` and `2,000,000` end up on one page**, and only a cross-path assertion catches it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | SI, and metric, wherever a quantity has an SI form: `2M tokens`, not `2,000,000 tokens`. **The prefix set is the SI set and nothing else** - no `bn`, no `lakh`, no `crore`, because each is read differently by a different part of the audience | O47, section 7.5 |
| 2 | **One declared locale, at build time.** `1.234` is one thousand two hundred and thirty-four in Berlin and slightly more than one in London. Reading the reader's browser would make two readers see different bytes, which breaks byte identity and is the reader-varying behaviour Guardrail #1 refuses | O47 |
| 3 | Precision is declared in config, so `2M` versus `2.4M` is a decision and not an accident of the input | O47 |
| 4 | **Formatting is not a derived value** and needs no provenance - nothing about the quantity moved. `convert` is, and it landed in plan 10 | O47, O45 |
| 5 | `d3-format` and `d3-time-format` are already named in the module matrix and do the prefix and precision rules with no code of ours | Section 7.5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Detect the reader's locale at runtime | Two readers see different bytes; the byte-identity oracle breaks; Guardrail #1 refuses reader-varying behaviour | O47 |
| 2 | Per-chart formatting | The path to `2M` and `2,000,000` on one page | Susan |

---

## 6. Row #4 - The smallest label a person can read, and enough marks to be worth the space

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

## 7. Row #5 - A caption, and one mark that lands first

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

## 8. Row #6 - A whole day, again

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
