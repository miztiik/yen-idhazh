# 14 - The rest of the ship-or-not bar

**Last Updated**: 2026-10-25
**Level**: 3 (build-failing checks on the published browser surface)

**Chain**: previous [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) | next [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O36, rows 22, 31, 32, 33, 36, sections 12.10, 12.13 G31.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 12 shipped the floors that decide whether a drawing can be read. The remaining checks must protect that delivery in the browser: every fact remains reachable by keyboard, the browser shell remains stable across navigation and reload, and motion remains finite and respectful of reduced motion. |
| Hard scope - in | The existing mark and fact limits remain authoritative; a keyboard route to every fact; reusable browser-shell identity checks; motion tokenised, bounded and killable |
| Hard scope - out | A new per-visual byte cap; chart-specific test fixtures; prerendered chart markup; new chart types; accessibility audit tooling; legibility and density floors owned by plan 12 |
| ESCALATE triggers | 1. A fact is reachable only on hover and cannot be given a keyboard route without a new interaction pattern. 2. The browser shell cannot produce stable geometry, text, focus order and accessibility from the same validated data and width. 3. A future chart or shell change requires layout animation, an invented motion limit or a per-type exception |
| Chosen strategy | Generic shared-shell checks replace visual-specific checks. A new chart uses the same shell contract; it does not get a separate identity or motion test |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Existing mark limits bound visual complexity | - | A | COLLAPSED | - | - | - |
| 2 | Every fact is reachable without a mouse | - | A | DONE | p14-r2 | #696 | - |
| 3 | The browser shell is stable across loads and navigation | 1, 2 | B | PENDING | - | - | - |
| 4 | Motion is shared, finite and reduced-motion safe | 3 | C | PENDING | - | - | - |

---

## 2. Row #1 - Existing mark limits bound visual complexity

- **Scope:** No new visual byte limit. Keep `visuals.min_chart_points`, `visuals.max_chart_points`, `visuals.max_facts`, text limits and the existing mark-count validator as the complexity contract. A plan outside those limits follows the existing validation and downgrade behaviour.
- **Files touched:** None for a new implementation. The result is recorded in the plan and in the current contract documentation.
- **Acceptance gates:** The existing visual contract and validator tests are the gates. No byte gate or byte measurement is added.
- **Oracle:** Valid plans with between the configured minimum and maximum marks publish. Plans outside the configured mark window are refused or downgraded by the existing validator; no additional byte rule changes them.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Mark and fact limits are the complexity boundary. A byte limit is a second, arbitrary size rule with no fixed reader-facing failure mode. | Visual contract, validator |
| 2 | Adding a byte limit does not improve graceful degradation. Invalid visual plans already degrade; the existing story stays unchanged. | `VisualsConfig`, `visual_validator.py` |
| 3 | Site growth belongs in site-weight and retention measurement, not in a per-visual published-data rule. | Guardrail #10, site-weight documentation |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Add a per-visual byte cap | It is an arbitrary new threshold layered on top of existing mark and text bounds and would require a separate measurement and downgrade vocabulary. | Fowler, current visual contract |
| 2 | Put each chart type on a different byte budget | It creates chart-specific exceptions and defeats the shared visual shell. | Susan, architecture |

---

## 3. Row #2 - Every fact is reachable without a mouse

- **Scope:** No fact exists only on hover. Every value a visual communicates is reachable by keyboard, and the accessible description carries what the drawing says.
- **Files touched:** `frontend/src/lib/visual/**`, `frontend/src/lib/components/ItemVisual.svelte`, `frontend/tests/**`, `docs/concepts/design-system.md`, `docs/architecture/publishing/visuals.md`. **It said `frontend/src/lib/charts/**` until 2026-09-14, and that is the operator console's own chart engine - 19 files, imported by console components only.** The reader's drawing has lived in `frontend/src/lib/visual/` since plan 12 row #1b, and this row is the reader's surface.
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke at 390 and 1440 in both themes.
- **Oracle:** For every published visual on a real day, the set of values reachable by keyboard equals the set reachable by pointer. Comparing the two sets is the check; asserting that *some* keyboard route exists is not, because the defect is always one fact that only hover reaches.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The dominant device has no hover.** A fact behind a pointer is a fact most readers never get | Row 33, Reader |
| 2 | The browser writes the accessible name from the same `Drawing` used to place every mark, so one derivation supplies both facts and labels | Current reader visual |
| 3 | Focus order and the accessible tree stay with the shared browser shell. Row 3 verifies their stability across navigation and reload rather than comparing build output | 12.13 G31 |
| 4 | Row 3 names the stable geometry, focus order, accessible name and complete fact set that its shared browser contract guards | 12.13 G31 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | An audit tool as the gate | Descoped at project level. This is a behaviour check, not a conformance score | CLAUDE.md section 0a |
| 2 | A separate accessibility pass later | Splitting it across build time and client side is how it silently regresses, which the source document names as the hazard | 12.13 G31 |

---

## 4. Row #3 - The browser shell is stable across loads and navigation

- **Scope:** Strengthen one reusable browser contract for the browser-owned visual shell. It applies to every valid visual-data shape the shared reader shell can render, not to one chart implementation or one seed item.
- **Files touched:** `frontend/src/lib/components/ItemVisual.svelte`, `frontend/src/lib/visual/**`, `frontend/tests/visual-legibility.spec.ts`, `frontend/tests/**` only where the shared shell test needs support, `docs/concepts/design-system.md`, `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke across representative narrow and wide viewports.
- **Oracle:** For real rendered visuals in the shared shell, navigation and reload produce the same geometry, text, accessible name, focus route and drawing facts for the same data and measured width. The shell must not gain chart-specific markup or per-type identity exceptions.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Charts are browser-owned and never prerendered. There is no build-time SVG against which a hydration byte comparison can be meaningful. | Reader visual architecture, owner ruling |
| 2 | D3 supplies drawing arithmetic; Svelte emits the shared DOM. The browser contract covers their combined output rather than either implementation alone. | Architecture boundary |
| 3 | One test reads all currently rendered visuals on the real day fixture and checks the shared shell contract. It does not name or branch on chart types. | Reusable browser test |
| 4 | Navigation, reload and repeated navigation are part of the identity contract because the shell mounts the same visual through several lifecycle paths. | Existing visual-legibility coverage |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Compare build-time SVG with post-hydration SVG | No chart markup exists at build time in the current architecture. | Fowler, current code |
| 2 | Add a separate identity test for each chart type | It makes the chart vocabulary multiply test code and creates unicorn fixtures. | Susan |
| 3 | Compare screenshots | Screenshot differences are font and platform artifacts; they do not prove stable geometry or accessible facts. | Jony |

---

## 5. Row #4 - Motion is shared, finite and reduced-motion safe

- **Scope:** Reader charts use no entrance or value animation unless a future shared-shell motion is admitted through the existing token system. Any shell or console motion honours reduced motion and is finite; it must not scale with the number of reader visual items.
- **Files touched:** `frontend/src/styles/**`, `frontend/src/lib/charts/d3/motion.ts`, `config/appearance.json`, `frontend/tests/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; the browser suite; the section 12 smoke in both themes.
- **Oracle:** A representative shared page contract counts browser animations before and after navigation and with reduced motion requested. Reader charts have no animation. Reduced-motion mode has zero running page animations in the tested reader surface; no animation count grows with item count. Existing finite loading motion settles when loading ends.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chart motion is unnecessary until a real reading aid is admitted. The current visual implementation is static. | Susan, current reader shell |
| 2 | A generic animation inventory is stronger than a chart count: it proves the shared page boundary and catches later chart or shell additions regardless of type. | Browser contract |
| 3 | Motion timing and allowed properties use shared appearance tokens and the existing D3 motion guard. A component must not invent its own duration or layout animation. | Config, D3 motion helper |
| 4 | Reduced motion removes animation rather than shortening it, and it leaves no frozen or decorative moving state. | Accessibility requirement |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Add a fixed number of entrance animations | That recreates unbounded per-item work by number alone and has no current reading benefit. | Susan |
| 2 | Add per-chart motion and per-chart tests | It creates chart-specific behavior and test unicorns. | Shared shell |
| 3 | Add a separate motion contract for reader visual types | Generic page motion applies to the shell regardless of chart implementation. | Fowler, Susan |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-13-switch-on-deletion-plan.md`](20260905-13-switch-on-deletion-plan.md) - the previous plan.
- [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) - the next plan.
- [Reader chart rules](../docs/concepts/design-system.md#a-charts-column-is-set-by-what-the-chart-was-drawn-at) - the delivered text floor and unscaled width; mark-count limits remain with the visual validator.
