# 14 - The rest of the ship-or-not bar

**Last Updated**: 2026-09-05
**Level**: 3 (build-failing checks on the published surface, and the test one compliance clause now rests on)

**Chain**: previous [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) | next [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O36, rows 22, 31, 32, 33, 36, sections 12.10, 12.13 G31.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 12 shipped the two floors that decide whether a drawing can be read. Three checks remain, and each fails in a way no reader would report as a bug: a visual can be correct and enormous, correct and unreachable without a mouse, and correct at build time then redrawn differently by the browser. **The third also carries a compliance load** - "code owns the path from spec to pixels" survives progressive enhancement only while the browser reproduces bytes code already chose |
| Hard scope - in | A per-visual byte cap that degrades to `none`; a keyboard route to every fact; hydration byte-identity; motion tokenised, bounded and killable |
| Hard scope - out | The legibility and density floors (plan 12 owns them). Any new type. Any accessibility audit tooling - descoped at project level; basic ARIA and keyboard navigation are in scope and that is what row 2 is |
| ESCALATE triggers | 1. The post-hydrate DOM cannot be made byte-identical to the build-time emit - that reopens a compliance clause and is Level 5. 2. The byte cap would refuse more than a stated share of otherwise-valid visuals, which means the cap is wrong rather than the visuals. 3. A fact is reachable only on hover and cannot be given a keyboard route without a new interaction pattern |
| Chosen strategy | Each check is a build-failing oracle, not a review item. A check a person can skip is the check skipped on the day it would have bitten |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A drawing that costs too much is not drawn | - | A | PENDING | - | - | - |
| 2 | Every fact is reachable without a mouse | - | A | PENDING | - | - | - |
| 3 | The browser draws exactly what the build drew | 1, 2 | B | PENDING | - | - | - |
| 4 | Motion that can be turned off, and that ends | 3 | C | PENDING | - | - | - |

---

## 2. Row #1 - A drawing that costs too much is not drawn

- **Scope:** A per-visual byte cap in config; a compiled visual over the cap becomes `none` with a recorded reason rather than publishing.
- **Files touched:** `frontend/src/lib/charts/**` or the compiler module, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/idhazh/contracts/visual.py` (the reason enum), `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `npm run check`; build; `bundle-gate`; `idhazh site-weight`; the browser suite.
- **Oracle:** A plan whose compiled output exceeds the cap publishes the item **with no visual and a recorded reason**, and the item is otherwise unchanged - asserted by comparing the published item to the same item with the visual removed by hand. Degrading must cost the reader the drawing and nothing else.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | There is **no per-item route**, so a visual lives on a list that has reached 621 items. One expensive drawing is one expensive drawing on a page carrying hundreds | Row 36 |
| 2 | Over-cap degrades to `none` with its own reason, which joins the enum plan 11 established. It is not a validator rejection - the plan was valid and the drawing was too big | Row 36, 12.7 G11 |
| 3 | The cap is a config number with the measurement behind it committed | Rule #6, Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Simplify the drawing until it fits | Silently changes what the reader is shown, and the plan's own downgrade ladder already exists for that decision | Jony |
| 2 | No cap, and rely on the page ceilings | The routes that render a day are counted and not capped, so nothing would ever fire | Carmack |

---

## 3. Row #2 - Every fact is reachable without a mouse

- **Scope:** No fact exists only on hover. Every value a visual communicates is reachable by keyboard, and the accessible description carries what the drawing says.
- **Files touched:** `frontend/src/lib/charts/**`, `frontend/src/lib/components/ItemVisual.svelte`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke at 390 and 1440 in both themes.
- **Oracle:** For every published visual on a real day, the set of values reachable by keyboard equals the set reachable by pointer. Comparing the two sets is the check; asserting that *some* keyboard route exists is not, because the defect is always one fact that only hover reaches.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The dominant device has no hover.** A fact behind a pointer is a fact most readers never get | Row 33, Reader |
| 2 | `alt_text` is generated by the compiler from the plan and the elements, so it is satisfied by construction and never carries model prose | 12.8 X6 |
| 3 | Focus order and the accessible tree are **not** a separate workstream - they fall out of row 3. If the post-hydrate DOM equals the build-time emit byte for byte, both match by construction, because both are functions of that DOM | 12.13 G31 |
| 4 | Row 3's failure message names accessibility among the things it guards, or the next person to relax that test will not know what they are relaxing | 12.13 G31 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | An audit tool as the gate | Descoped at project level. This is a behaviour check, not a conformance score | CLAUDE.md section 0a |
| 2 | A separate accessibility pass later | Splitting it across build time and client side is how it silently regresses, which the source document names as the hazard | 12.13 G31 |

---

## 4. Row #3 - The browser draws exactly what the build drew

- **Scope:** One plan, rendered at build time and again after hydration, compared byte for byte.
- **Files touched:** `frontend/src/lib/charts/**`, `frontend/tests/hydration-identity.spec.ts` (new), `docs/concepts/design-system.md`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke.
- **Oracle:** For a seed item and a past-seed item, the drawn SVG markup after hydration equals the build-time emit byte for byte. **The failure message names what it guards** - pixel identity, focus order and the accessible tree - so a later relaxation is an informed one.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A chart that redraws on hydrate is this project's first spinner in all but name | Row 31 |
| 2 | **This test is what a compliance clause now rests on.** "Deterministic code controls rendering" survives progressive enhancement only while the browser reproduces bytes code already chose. It is recorded as conditionally compliant until this test exists | Section 12.10 |
| 3 | Hydration stays off by default per type, and any hydrated route earns its byte entry before it merges | Row 22 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Compare a screenshot | Fails on every font-rendering difference and would be disabled within a week | Jony |
| 2 | Skip the check and trust the shared code path | The clause is only conditionally compliant without it, and nobody has tested it | Fowler |

---

## 5. Row #4 - Motion that can be turned off, and that ends

- **Scope:** Any motion is tokenised, bounded in duration and count, and honours a reduced-motion preference.
- **Files touched:** `frontend/src/app.css` or the token layer, `frontend/src/lib/charts/**`, `config/appearance.json`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke.
- **Oracle:** On the heaviest committed day, the count of animated elements is bounded by a stated number regardless of item count, and with reduced motion requested the count is **zero**. Both arms, because a preference honoured in one component and not another is the usual shape of this defect.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The largest committed day carries **621 items**. 621 entrance animations is a page that never settles | Row 32 |
| 2 | Motion is bounded by a token, not by each component's own judgement, so the bound cannot drift per chart | Susan |
| 3 | Plan 12 recorded the constraint while changing the renderer; this row is where it becomes a gate | Plan 12 row 6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | No motion at all | Motion that shows a value arriving is a real aid on one drawing. Unbounded motion on 621 is the defect | Susan |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) - the previous plan.
- [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) - the next plan.
- [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md) - where the legibility and density floors landed.
