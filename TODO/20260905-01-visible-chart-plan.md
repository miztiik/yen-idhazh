# 01 - The chart stops being invisible

**Last Updated**: 2026-09-05
**Level**: 3 (cross-cutting: a reader-facing component, a build-time payload read, two config files)

**Chain**: first plan of the visual-planner group. Next: [`20260905-02-retire-the-route-name-plan.md`](20260905-02-retire-the-route-name-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - section 2.1 (root cause), section 6.1 (the two carriers), rows 21, 28, 37.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A published chart cannot read the page's colours, so it is unreadable in the dark theme - the loudest reader-facing defect on the site, and it is fixable today against the renderer that ships |
| Hard scope - in | The carrier: inline SVG for seed items, fetch-and-inline for the rest. Colour resolved from the page's tokens in both themes. A browser check at whole-day scale. Settling the duplicated `visual_side` knob |
| Hard scope - out | The renderer (plan 12 replaces it). The legibility floor and the density floor (plan 12). Any backend byte - the theme is resolved at the carrier, so `chart_spec()`'s hardcoded hex is plan 12's to delete. Any new visual type |
| ESCALATE triggers | 1. Inlining the seed moves the measured gzipped bytes per published item more than 25 percent above the figure `idhazh site-weight` prints on the base tree. 2. A day page cannot resolve token colours without a per-mark class emitted by the backend - that reverses row 28 and is Level 5. 3. `visual_side` turns out to have a live reader after all |
| Chosen strategy | Resolve the theme at the carrier with CSS custom properties and change no backend byte (Fowler, 2026-09-05). A presentation attribute loses to a stylesheet rule, so an inlined SVG is styleable by the host page with no change to what the backend writes |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Why N = 1.** All four rows touch `frontend/src/lib/components/ItemVisual.svelte` or its call site. Rows sharing a file are dispatched one at a time and merged before the next starts.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The seed items carry their drawing in the page | - | A | DONE | yi-v01 | #401 | worker (runSubagent unavailable - persona files read directly) |
| 2 | A past-seed item is themed too | 1 | B | PENDING | - | - | - |
| 3 | A whole committed day, looked at | 2 | C | PENDING | - | - | - |
| 4 | One knob, one value | - | C | PENDING | - | - | - |

---

## 2. Row #1 - The seed items carry their drawing in the page

- **Scope:** The first `digest.shell_seed_items` items render their visual as an inline `<svg>` in the prerendered document, and every drawn colour resolves from the page's own tokens in both themes.
- **Files touched:**
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/src/lib/server/payload.ts` (read the SVG text at build time)
  - `frontend/src/lib/payload/project.ts` (the runtime projection's field allow-list, if the text travels)
  - `frontend/src/app.css` or the token layer that owns `--chart-N`
  - `frontend/tests/item-visual.spec.ts` (new)
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check` 0/0; `npm run build`; `npm run bundle-gate`; `idhazh site-weight`; the browser suite; the section 12 smoke on `/` and one `/<date>/` at 390 and 1440 in both themes.
- **Oracle:** In a real browser, on a seed item that has a visual: the figure contains exactly one `<svg>` and zero `<img>`, **and** the fill of a drawn mark equals the computed value of a probe element whose `background-color` is set to `var(--chart-1)` - asserted separately in the light theme and the dark theme. **No fixed hex can satisfy both**, so the assertion cannot pass against a baked colour.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The theme is resolved at the carrier, not by changing what the backend writes. A presentation attribute on an inlined SVG loses to any stylesheet rule, so the host page wins with no backend edit | Fowler, 2026-09-05 |
| 2 | Only the seed inlines. A day has carried 621 items and inlining every SVG puts roughly a megabyte of markup in one document | Pseudo-plan section 6.1, row 37 |
| 3 | The `img` element is deleted rather than kept as a fallback. An SVG inside `img` is a separate document and can never read the page - keeping it would leave the defect reachable | Jony, row 21 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Emit sentinel colours from `chart_spec()` and swap them, as the console does | Real, and it changes backend bytes that plan 12 deletes. The carrier alone is enough because CSS beats a presentation attribute | Fowler |
| 2 | Inline every item's SVG | About a megabyte of markup on the largest committed day, on the surface a phone loads first | Carmack |
| 3 | Keep the `img` and set `filter:` to fake a dark theme | Alters every colour including ones chosen to mean something, and cannot honour a token | Susan |

---

## 3. Row #2 - A past-seed item is themed too

- **Scope:** An item past the seed fetches its SVG and inlines it into the DOM, so it gets the same colours as a seed item rather than staying an unreadable image.
- **Files touched:**
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/tests/item-visual.spec.ts`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** as row 1, plus zero new console errors and zero new 404s with the fetch path exercised.
- **Oracle:** Scroll a real committed day past the seed, then assert the same probe-colour equality on a past-seed item in both themes. **And assert the count of `<img>` elements inside item figures is zero page-wide** - the whole point is that no item is left on the unreadable carrier.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fetch-and-inline rather than a second prerendered copy. The reading page is already two contexts and a past-seed item already requires a fetch | Row 37 |
| 2 | A failed fetch leaves the item shorter, never a broken-image glyph or a grey placeholder | Row 34, Susan |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Prerender every item's SVG inline | Row 1 decision 2 - the byte cost | Carmack |
| 2 | Leave past-seed items on the `img` carrier | Two visual treatments on one scroll, which reads as a broken site | Jony, row 35 |

---

## 4. Row #3 - A whole committed day, looked at

- **Scope:** A browser check that renders one real committed day end to end - every item, both themes, phone and desktop width - and asserts the page-level properties no per-visual check can see.
- **Files touched:**
  - `frontend/tests/whole-day.spec.ts` (new)
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:** the new spec passes against the real build; the browser suite stays green; runtime recorded in the gates doc.
- **Oracle:** On the heaviest committed day, at 390 and at 1440, in both themes: zero console errors, zero responses at 400 or above, zero horizontal overflow, and **every item figure resolves its colours from a token** - the row 1 probe assertion applied to every drawn visual on the page rather than to one.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This check exists because every other gate in the programme measures one visual, and a per-visual oracle cannot see a wall of identical drawings or a page that never settles | Susan, 2026-09-05 |
| 2 | It runs against the REAL build, not the canary. The canary publishes one day of fixtures and cannot reach day scale | Recorded gates behaviour |
| 3 | The spec is written to be re-used. Plans 12 and 18 run it again rather than writing their own | Fowler |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Check one visual per type and infer the page | That is what every other gate already does, and it is what left a 40.6 percent screen-use surface passing every review | Susan |
| 2 | A screenshot diff of the whole day | Fails on every publish, so it would be disabled within a week | Jony |

---

## 5. Row #4 - One knob, one value

- **Scope:** `visual_side` is declared in two config files with two different values and no reader. Settle it to one owner or delete it.
- **Files touched:**
  - `config/idhazh.json` and `config/appearance.json` (whichever loses)
  - `backend/idhazh/contracts/app_config.py` or the appearance contract
  - `schemas/app-config.schema.json` / `schemas/appearance-config.schema.json` (generated)
  - `tests/fixtures/contracts/app-config/tuned.json`, `tests/fixtures/contracts/appearance-config/{committed,defaults}.json`
  - `frontend/src/lib/server/config.ts`
  - `docs/concepts/design-system.md`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; `python -m idhazh.contracts.export` then `git diff --exit-code -- schemas/`; the contracts and appearance test modules; the full suite in CI.
- **Oracle:** `git grep -n 'visual_side'` returns declarations from exactly ONE config file and its contract, and the value it declares is the position `DigestItem.svelte` actually renders.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The visual already sits below the summary.** `DigestItem.svelte` renders title, summary, reader note, then the visual. So pseudo-plan O35 is satisfied on main and this row records that rather than moving anything | Verified 2026-09-05 |
| 2 | The knob is **deliberately** reserved, not accidental dead config - `design-system.md` states it stays unread until the render spec is handed the width it will occupy. So the choice is which file owns it, not whether it may exist | Fowler, delete-first applied to the duplicate only |
| 3 | Any contract field removed here takes a schema stamp, a changelog entry and its fixture keys in the same commit | CLAUDE.md section 11 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Delete `visual_side` from both files | It is reserved with a written reason and plan 12 is what makes it live. Deleting it discards a decision somebody already argued | Fowler |
| 2 | Leave both and let the reader of the day decide | Two files declaring one name with two values is how a config change lands in the file nobody reads | Fowler |
| 3 | Wire it up now so the duplicate has a reader | The knob's own doc says a setting that draws an illegible chart is worse than no setting. Wiring it before plan 12 ships exactly that | Susan |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-02-retire-the-route-name-plan.md`](20260905-02-retire-the-route-name-plan.md) - the next plan in the chain.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract.
