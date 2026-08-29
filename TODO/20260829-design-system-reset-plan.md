# The design system reset - a published surface worth the reader's screen

**Last Updated**: 2026-08-29
**Level**: 5 (core design doctrine + two persisted config contracts). Owner signed off the two doctrine strikes on 2026-08-29; no further pause is required inside this plan.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The published surface uses 40.6 percent of a 1536px screen, has no responsive layout system, no elevation, no gradient, no icon set and no interactive chart, because three doctrine sentences turned every design decision into a subtraction. |
| Hard scope - in | Doctrine reset and a demand-side persona; a frontend-owned config contract; a full token layer (space, elevation, gradient, chart ramps, frame, measure, type); a fluid frame with the measure moved onto text; a generated tinted icon system; a shared chart hover-readout layer; the reference chart vocabulary; a rebuilt console; digest and archive polish; a web app manifest. |
| Hard scope - out | Service worker (a separate decision, see row 11 rejected alternatives); accessibility audit tooling (section 0a); any runtime service; account systems; push; a chart library that draws (row 6 decision 3); backend pipeline logic; the frontend contract-generation gap named in row 2 decision 6. |
| ESCALATE triggers | (1) A row needs a runtime service or a third-party script that phones home. (2) The published site is measured past 900 MB after any row. (3) A row cannot hold the `/console/` bundle route under 140 KB gzipped. (4) A persisted payload contract other than the two config contracts needs a field. |
| Chosen strategy | Foundation first (doctrine -> config -> tokens -> frame), then parallel surface work, then one re-baseline row. Ruled by Fowler (contracts before logic, Rule #3) with Jony owning every visual decision and Susan owning every sufficiency call. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3. Every row is its own worktree off `origin/main` and its own PR; another agent is active in the main checkout and in `yi-t02`, `yi-t03`, `yi-t04`. |

**Gold standard for every visual ruling in this plan**: the operator-dashboard reference screenshots supplied by the owner on 2026-08-29, plus nuscio.com measured the same day. Rich panel language, tinted status cards, gradient chrome, per-purpose chart types, hover readout, colourful semantic icons, working dark theme.

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Doctrine reset and the demand-side gate | - | A | DONE #205 | `yi-r1` | 205 | - |
| 2 | `config/appearance.json` - the frontend's own contract | 1 | B | DONE #208 | `yi-ui` | 208 | - |
| 3 | The token layer the design system already specified | 1 | B | DONE #209 | `yi-ui` | 209 | - |
| 4 | The fluid frame, and the measure moved onto text | 2, 3 | C | DONE #221 | `yi-ui` | 221 | - |
| 5 | A generated, tinted icon system | 3, 4 | D | DONE #235 | `yi-ui` | 235 | - |
| 6 | Pick the console's chart engine, on measured numbers | 3, 4 | D | DONE #233 | `yi-ui` | 233 | - |
| 7 | The reference chart vocabulary | 6 | E | DONE #238 | `yi-ui` | 238 | - |
| 8 | The console rebuilt as panels | 5, 6, 7 | F | DONE | `yi-ui` | - | - |
| 9 | The digest surface, and the archive brought inside | 4, 5 | E | DONE #239 | `yi-ui` | 239 | - |
| 10 | Installability | 3 | D | DONE #237 | `yi-ui` | 237 | - |
| 11 | Re-baseline, measure, and smoke every surface | 8, 9, 10 | G | PENDING | - | - | - |
| 12 | Scrub the third-party product name from the repository | - | A | DONE #217 | `yi-ui` | 217 | - |

Twelve rows. Row 12 was added on 2026-08-29 at owner instruction and jumped the
queue: it has no predecessor and blocks nothing, so it runs beside whatever else
is in flight.

---

### Row #1 - Doctrine reset and the demand-side gate

- **Scope:** Strike the three sentences that made under-building the default, add a persona whose mandate is to demand rather than veto, add the rule that makes a veto cost something, and fix the one doc line that contradicts Rule #1.
- **Files touched:**
  - `docs/concepts/design-system.md`
  - `docs/concepts/ui-shell.md`
  - `docs/concepts/vision.md`
  - `docs/concepts/principles.md`
  - `docs/agents/guardrails.md`
  - `.github/agents/susan.agent.md` (new)
  - `.github/agents/jony.agent.md`
  - `CLAUDE.md` (section 9 Definition of Done, section 14 roster)
  - `AGENTS.md`
- **Acceptance gates:** ASCII-only across every edited file; every `## Design rationale` amendment lands in the same commit as the text it explains (section 5); `docs/` and `CLAUDE.md` do not disagree after the edit; no orphaned cross-link.
- **Oracle:** A full-text sweep of `docs/`, `CLAUDE.md`, `AGENTS.md` and `.github/agents/` for the four struck phrases - `falls out of the architecture`, `earn no design budget`, `earns no design budget`, `no CDN font` - returns zero hits outside a `## Design rationale` block that explains the strike.

**The exact text changes.**

| Location | Old | New |
| --- | --- | --- |
| `design-system.md`, opening | `Restraint is not a style choice on this project; it falls out of the architecture.` | `The architecture fixes how much surface there is. It does not fix how good that surface is. Scope-restraint is inherited and not up for debate; craft-restraint is a choice, and every instance of it needs an argument on the day it is made.` |
| `ui-shell.md`, "The surfaces" | `they earn no design budget, and their only obligation is to be correct` | `they take no ornament - no display face, no gradient, no illustration - and what they owe instead is legibility: a figure readable at a glance, a table that fits the screen it is on, and a page scannable in one pass. Correctness is the floor, not the ceiling. An instrument that is right and unreadable has not done its job.` |
| `vision.md`, "Who it is for" | the same phrase | `It is instrumentation rather than a reading surface: it takes no ornament and spends no reader attention, but it owes the operator the same legibility the digest owes a reader.` |
| `ui-shell.md`, "What the shell must never do" | `Fetch anything cross-origin: no CDN font, no analytics snippet, no third-party widget (Rule #1).` | `Run anything off the reader's device, report a reader's behaviour anywhere, or load a third-party script that phones home (Rule #1). A static asset is judged on bytes, licence and privacy behaviour, never on hostname - and this project self-hosts its font because the request is the larger cost, not because the origin is forbidden.` |
| `jony.agent.md`, paragraph 4 | `Restraint is not a style choice on this project; it is the architecture.` | The same replacement as design-system.md. |

**New doctrine, added by this row.**

| # | Where | The rule |
| --- | --- | --- |
| D1 | `design-system.md`, new section "Decorative colour and semantic colour" | Colour that encodes meaning is doubly constrained: it carries a word or a shape as well as a tint, and it may never borrow the confidence ramp's three hues. Colour that encodes nothing - chrome, identity, an empty state, a panel tint - is unconstrained. The absence of this distinction is why nobody proposed a gradient in eleven months. |
| D2 | `design-system.md`, new section "Sufficiency is a gate, not a taste" | A reader-facing surface fails review for being insufficient, exactly as it fails for being over-built. The named checks: does it use the screen it is on; does it separate figure from ground; is there one thing a reader's eye lands on first; does it look like it was made this year. Susan rules these; a `## Design rationale` entry is required to ship a surface that fails one. |
| D3 | `guardrails.md`, "Authority assignment" | A veto must name what the reader loses. A removal ruling that states only what is removed is not a ruling and does not bind. This is the structural fix for a review roster that was six vetoes and no demand. |
| D4 | `CLAUDE.md` section 9 | New Definition-of-Done line: `For reader-facing surfaces: the sufficiency checks in docs/concepts/design-system.md pass, or a Design rationale entry says why not.` |
| D5 | `CLAUDE.md` section 14 + `guardrails.md` | Susan joins the roster at a distinct altitude - craft and delight - and the split rule is written: **Jony rules what survives on the page; Susan rules whether what survived is good enough to ship.** |
| D6 | `principles.md` | Principle 11 `Delete before you build` gains a second clause: `and build before you settle. A surface nobody would choose to look at has not been simplified, it has been abandoned.` |

**`.github/agents/susan.agent.md`** - frontmatter `name: "Susan (Craft & Delight)"`, `tools: [read, search, web]`, `user-invocable: true`. Channels Susan Kare (the Macintosh icon set - warmth, personality, a system of small colourful marks that made a machine feel human), Michael Bierut (identity, colour and typography with conviction; a design that argues for itself), and Rasmus Andersson (Inter, systematic type and colour scales that a team can actually hold). Her mandate is the mirror of Jony's: **she fails a surface for being not enough.** She may not add a feature, may not overrule Reader on whether copy is plain, may not overrule Carmack on bytes, and may not propose anything that needs a request at read time.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Both Level-5 strikes proceed without a further pause. | owner, 2026-08-29 |
  | 2 | The fix is a new persona plus a cost on vetoes, not a rewrite of the existing six. Each of the six is correct at its altitude; the roster was missing an altitude, not miscalibrated. | Fowler |
  | 3 | Susan is a distinct altitude under section 14 - Jony decides what survives, Susan decides whether it is good enough - so the roster grows to seven rather than collapsing two. | Fowler, Jony |
  | 4 | The CDN-font line is fixed in this row and not deferred, because Rule #4 makes the contract win and a doc that contradicts it is a trap for the next agent. | Fowler |
  | 5 | D1 ships as doctrine before any token work, because it is the rule that makes row 3 legal. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Soften the three sentences rather than strike them | A softened absolute is still read as an absolute, and these three produced eleven months of consistent under-building. | owner |
  | 2 | Give Jony the demand mandate instead of adding a persona | One head holding both "remove before adding" and "this is not enough" resolves to the veto every time, which is the observed outcome. | Fowler |
  | 3 | Delete the persona roster and review by hand | Removes the only structured design review the project has, to fix a gap in it. | Fowler |
  | 4 | Make sufficiency advisory rather than a Definition-of-Done line | An advisory check is the one that is skipped on the day it would have bitten. | Susan |

---

### Row #2 - `config/appearance.json` - the frontend's own contract

- **Scope:** A second config file owned by the published surface, with its own Pydantic contract, its own generated schema, and validated bounds so a knob cannot be set to a value that breaks the design.
- **Files touched:**
  - `backend/idhazh/contracts/appearance_config.py` (new)
  - `backend/idhazh/contracts/export.py` (register the contract)
  - `backend/idhazh/contracts/app_config.py` (deprecate the moved blocks)
  - `config/appearance.json` (new)
  - `config/idhazh.json`
  - `schemas/appearance-config.schema.json` (generated)
  - `schemas/app-config.schema.json` (regenerated)
  - `frontend/src/lib/server/config.ts`
  - `backend/tests/test_appearance_config.py` (new)
  - `docs/concepts/config.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** `python -m idhazh.contracts.export` then `git diff --exit-code -- schemas/` is clean; `ruff`, `mypy --strict`, full `pytest` green; `npm run check` green; both schemas carry a `2026-08-29` version stamp and a `changelog` entry; the read-side migration is in this same commit (section 11).
- **Oracle:** A round-trip test proves the migration in both directions - a `config/idhazh.json` still carrying the legacy `ui`, `console` and `assist` blocks, with `config/appearance.json` absent, produces byte-identical resolved settings to the new file with the legacy blocks removed. A test that always returns defaults cannot pass it, because the fixture sets every block to a non-default value.

**What moves and what is new.**

| Block | Source | Contents |
| --- | --- | --- |
| `digest` | moved from `app_config.ui` | `sections`, `items_per_topic`, `show_filter`, `source_mark`, `read_mark_days`, `theme_default`, `site_title`, `tagline`, `repo_url` |
| `console` | moved from `app_config.console` | every existing `console.*` knob |
| `assist` | moved from `app_config.assist` | `similarity_floor`, `result_limit` |
| `frame` | new | `reading_max_px` (>= 960, <= 1600), `console_max_px` (>= 1100, <= 2000), `measure_ch` (>= 52, <= 80), `gutter_min_px`, `gutter_max_px`, `breakpoints` (exactly three ascending integers) |
| `theme` | new | `accent`, `gradient_enabled`, `surface_tint_alpha` (0 to 0.15), `elevation_enabled`, `display_face_enabled` |
| `chart` | new | `height_px`, `hover_readout`, `palette`, `tick_density`, `sparkline_height_px`, `donut_thickness_px` |
| `icons` | new | `size_px`, `tint_mode` (`semantic` or `mono`), `topic_icons_enabled` |
| `motion` | new | `duration_fast_ms`, `duration_base_ms`, `enabled` |

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The frontend gets its own file. Curating a reading surface and tuning a decode threshold are different activities with different review cadences - the same argument `config.md` already makes for splitting `sources.json` off `idhazh.json`. | owner, 2026-08-29; Fowler |
  | 2 | Frame widths, the measure and the breakpoints ARE knobs, contrary to the 2026-08-28 advisory ruling, and the objection is answered by the contract rather than by refusal: a Pydantic validator refuses a frame below 960px or a measure outside 52-80ch, so no reachable value breaks the design. | owner, 2026-08-29 |
  | 3 | Both schemas version-stamp `2026-08-29` and changelog the move; the frontend loader prefers `appearance.json` and falls back to the legacy blocks, so a payload an earlier run wrote still resolves (section 11). | Fowler |
  | 4 | `config/appearance.json` is copied into the built site as a static asset, so a future reader-facing surface can fetch it at runtime without a second source of truth. Fetching our own committed file is explicitly allowed by Rule #1. | Fowler |
  | 5 | Anything that must be right on the first painted frame - theme, frame width, measure - is inlined at build time and never fetched, because a fetch cannot beat first paint. | Jony |
  | 6 | Frontend payload types stay hand-written in `frontend/src/lib/payload/types.ts` for this plan. `CLAUDE.md` section 1a asserts they are generated and `frontend/src/contracts/` does not exist; that gap is real, is out of scope here, and gets its own row in a later plan rather than being silently absorbed. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep everything in `config/idhazh.json` | The file already mixes decode parameters with page layout; every appearance edit would touch the file that pins model determinism. | owner |
  | 2 | A plain JSON file with no Pydantic contract | Rule #3 and section 1a admit no exception for a config file, and an unvalidated frame width is exactly the failure decision 2 is guarding against. | Fowler |
  | 3 | Fetch the whole appearance config at read time | A theme or frame width that arrives after first paint is a visible flash on every page load. | Jony |
  | 4 | A breaking move with no fallback | A contract break is a release blocker under section 11, and the fallback is nine lines. | Fowler |

---

### Row #3 - The token layer the design system already specified

- **Scope:** Build the space scale, the shadow and elevation scale, the gradient set, the chart palettes, the frame tokens and the self-hosted display face - the first two of which `design-system.md` has specified in writing since 2026-08-27 and which were never implemented.
- **Files touched:**
  - `frontend/src/styles/tokens.css`
  - `frontend/src/styles/app.css`
  - `frontend/src/styles/elevation.css` (new)
  - `frontend/static/fonts/` (new; committed woff2)
  - `frontend/src/app.html` (font preload, `theme-color`)
  - `frontend/tests/tokens.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check` and `npm run build` green; every token in the new set has a light and a dark value; the `@theme inline` mirror covers every non-exempt token; committed font bytes <= 120 KB total; browser smoke at 390, 768, 1024, 1512 in both themes with zero new console `[error]` and zero new `404`.
- **Oracle:** A contract test enumerates the token names declared in `tokens.css` under `:root` and asserts three things at once - every one has a `[data-theme='dark']` override, every non-exempt one has an `@theme inline` mirror in `app.css`, and no token name appears in a component that is not declared in `tokens.css`. A missing dark value, a missing mirror or an invented token each fail it.

**The token set this row adds.**

| Group | Tokens | Note |
| --- | --- | --- |
| Space | `--space-0` through `--space-9`, a 4px-based scale | Already specified in `design-system.md`. Does most of the work on a page that is mostly text. |
| Elevation | `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-panel`; `--surface-raised`, `--surface-sunken` | Already specified. Dark theme uses a lighter surface plus a hairline rather than a heavier shadow, because a shadow on a dark ground reads as nothing. |
| Frame | `--frame-reading`, `--frame-console`, `--measure`, `--gutter` | Fed from `config/appearance.json` at build time (row 2). |
| Gradient | `--gradient-brand`, `--gradient-wash`, `--gradient-panel` | Chrome and identity only. D1 from row 1 is what makes these legal. |
| Surface tint | `--tint-accent`, `--tint-info`, `--tint-warn`, `--tint-bad`, `--tint-good` at 5-9 percent alpha | The single cheapest richness move available; the reference dashboard's KPI cards and nuscio's panels are both this and nothing more. |
| Chart | `--chart-1` through `--chart-8`, plus `--chart-grid`, `--chart-axis`, `--chart-marker`, `--chart-readout-bg` | Categorical, eight stops, and it holds no green, amber or red - the existing four-stop `--series-*` ramp is extended, not replaced, and the confidence ramp stays untouched. |
| Type | `--font-display`, `--font-reading`, `--font-data`; `--text-xs` through `--text-3xl` with paired line heights | Display face for headings only. |
| Radius | `--radius-lg`, `--radius-xl`, `--radius-full` added to the existing two | Panel language needs a bigger corner than 8px. |

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The display face is self-hosted woff2, subset to Latin, headings only, `font-display: swap`, preloaded. The body keeps the system stack: it renders on the first frame at zero bytes and the body is what the reader came for. | Jony, Carmack |
  | 2 | Licence must be OFL or equivalent and the source and version are recorded in a `PROVENANCE.md` beside the bytes, matching what `frontend/static/assist/models/` already does. | Fowler |
  | 3 | Cost against Rule #2, measured before merge: the published site is 128,064,853 bytes and grows about 16.6 MB per published day, so a 60 KB font is about one third of one percent of a single day's growth and does not move the cap date. The row records the real number, not this estimate. | Carmack, Rule #10 |
  | 4 | The dark theme is designed, not derived. Shadows are replaced by surface lift plus a hairline rule; tints are re-tuned per theme rather than reused at the same alpha. The reference dashboard's dark screenshots are the model. | Susan |
  | 5 | `--series-1` through `--series-4` keep their current values inside `--chart-1` through `--chart-4`, so no existing chart changes colour in this row. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A webfont from a third-party CDN | Rule #1 permits it, and self-hosting still wins: the HTTP cache is partitioned per site so the shared-cache argument is dead, and `script-src`/`default-src` are `self` only. | Carmack |
  | 2 | A display face for body text too | Doubles the committed bytes and delays the first frame of the thing the reader came for. | Jony |
  | 3 | Replacing the `--series-*` ramp outright | Every existing chart would change colour in a row that is meant to add capability, not shift meaning. | Jony |
  | 4 | A Tailwind plugin or preset for the scales | The `@theme inline` block already mirrors `tokens.css` as one source of truth; a preset would make two. | Fowler |

---

### Row #4 - The fluid frame, and the measure moved onto text

- **Scope:** Replace the single `max-w-2xl` on the app shell with a fluid frame, put the reading measure on the text elements that need it, and adopt the container-driven grid rule everywhere a grid exists.
- **Files touched:**
  - `frontend/src/routes/+layout.svelte`
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/src/lib/components/TopicSection.svelte`
  - `frontend/src/lib/components/ItemMeta.svelte`
  - `frontend/src/lib/components/FailurePanels.svelte`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/src/styles/app.css`
  - `frontend/tests/frame.spec.ts`
  - `frontend/tests/layout.spec.ts` (new)
  - `docs/concepts/design-system.md`, `docs/concepts/ui-shell.md`, `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** Playwright measures the content column at 390, 768, 1024, 1280, 1512 and 1920 and asserts the recorded targets; zero elements have `scrollWidth > clientWidth + 4` at or above 1024 on any page; the empty-payload and missing-payload states still render (section 12 step 5); `npm run check`, `npm run build`, `npm run test:browser` green.
- **Oracle:** A Playwright test asserts the frame and the measure move independently - at 1512 the frame is at least 1200px wide AND the summary paragraph's rendered line box is between 52 and 80 characters. A commit that widens the shell without moving the measure fails the second half; a commit that caps the measure without widening the shell fails the first.

| Surface | Below 640 | 640 to 1024 | 1024 to 1400 | Above 1400 |
| --- | --- | --- | --- | --- |
| Digest | one column, gutter 16 | one column, gutter 24 | frame to `--frame-reading`; visual beside the summary; meta to a side rail | as 1024, gutter 32 |
| Archive | one column | one column | two columns | three columns |
| Console | one column, tables scroll | one column | frame to `--frame-console`; panels `auto-fit minmax(320px, 1fr)` | as 1024, four panels fit |
| Evals | redirect stub, unchanged | - | - | - |

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The measure is a property of a text element and never of the shell. This is the single defect behind the 40.6-percent measurement. | Jony |
  | 2 | The digest stays one column. `layout.md` makes the published order a load-bearing contract, and two columns destroys the only property a ranked list has - that reading downward is reading in order. The width buys the side rail and the beside-text visual instead. | Jony, Editor |
  | 3 | The archive does go multi-column: it is a scan surface where "find the one I remember" already outranks the day's order. | Editor, Jony |
  | 4 | A grid splits on available width, never on a viewport width. `sm:grid-cols-3` asking the viewport a question only the container could answer is what drew three charts at 164px. | Jony |
  | 5 | `overflow-x-auto` is never reachable above the frame width. A table that overflows at frame width is a column-count decision taken at design time, not a scrollbar. | Susan |
  | 6 | `console.chart_width` moves to `appearance.chart` and rises before the console frame widens, so the server prerender does not snap on first paint. | Carmack |
  | 7 | Below 640 the gutter drops to 16px. The phone was measured using 83.3 percent of a 312px screen; that is about 20px of fat gutter, or two words a line. | Reader |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Change `max-w-2xl` to a bigger value and stop | Makes the digest worse: 1280px of unbroken summary prose is the exact failure the original measure rule was protecting against. | Jony |
  | 2 | A two-column digest | Destroys the ranked-order contract in `layout.md`; a card grid is a browse surface and a digest is a read surface. | Jony, Editor |
  | 3 | Viewport breakpoints for the panel grids | The container, not the window, is what has the width; this is the `sm:grid-cols-3` bug restated. | Jony |
  | 4 | A full-bleed frame with no maximum | A 2560px line of anything is unreadable, and the frame maximum is what makes the side rail land in a predictable place. | Susan |

---

### Row #5 - A generated, tinted icon system

- **Scope:** A real icon set - a generated sprite from committed source SVGs, referenced by id, tinted from semantic tokens - covering the chrome, the console, every control, and the topic taxonomy.
- **Files touched:**
  - `frontend/src/lib/icons/` (new: source SVGs, `manifest.ts`, `Icon.svelte`)
  - `frontend/scripts/build-icons.mjs` (new)
  - `frontend/package.json` (a `build:icons` script, wired into `build`)
  - `backend/idhazh/contracts/icon_manifest.py` (new) and `schemas/icon-manifest.schema.json`
  - `frontend/src/lib/components/SourceLink.svelte`, `TopicPills.svelte`, `ConfidenceChip.svelte`, `SiteHeader.svelte`, `ThemeToggle.svelte`, `ItemMeta.svelte`
  - `frontend/static/fonts/PROVENANCE.md` sibling: `frontend/src/lib/icons/PROVENANCE.md`
  - `frontend/tests/icons.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** Every icon is referenced by id and no component contains a literal `<path>`; the sprite is generated by the build and is not hand-edited; total committed icon bytes <= 40 KB; both themes rendered and screenshotted; licence recorded.
- **Oracle:** A test asserts a bijection - every id in the generated manifest is used by at least one component, and every icon id referenced anywhere in `frontend/src` exists in the manifest. An unused icon and an invented id each fail it.

**DELIVERED 2026-08-29.** Fifteen glyphs, not the twenty-nine first extracted. The lens and event taxonomies are declared in `config/taxonomy.json` and no surface renders either, so thirteen marks would have shipped against a page that might arrive - which is the exact thing the bijection exists to refuse. It was proved to bite before being trusted: a decoy icon added to the source directory failed the run, and its removal restored it.

Measured, same tree, same session:

| What | Number |
| --- | --- |
| Committed source SVG | 5,887 B against a 40 KB budget |
| Marks in the generated module | 2,128 B |
| First-load JS, per route | `/` +1,897, `/404` +1,771, `/<date>/` +1,900, `/<date>/<topic>/` +1,900, `/archive/` +1,833, `/console/` +1,404, `/evals/` +1,775 |
| `/evals/` prerendered HTML | 2,915 B, so its ceiling moved 2,730 -> 2,979 |

The module reaches every route because a component names an icon by id and a lookup on a dynamic key cannot be tree-shaken. The alternative measured against it was an inline sprite: no JavaScript at all, about 700 B of gzipped markup in every prerendered document, and `/404` had 37 B of headroom under a ceiling whose whole purpose is keeping the error page tiny. The bytes went where there was room for them, and the numbers to revisit that are in `docs/concepts/design-system.md`.

Two things the contract caught that a person would not have: the manifest must be sorted by id, and filename order is not id order - `topic-ai-roi.svg` sorts before `topic-ai.svg` while the ids go the other way. And a new contract with no fixture failed `test_every_contract_has_at_least_one_fixture`, which is the rule working.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Colourful icons ship. The prior refusal is overruled. | owner, 2026-08-29 |
  | 2 | Colour arrives by semantic tint, not by multi-colour artwork - the same mechanism the reference dashboard uses, where a glyph is monochrome and the status decides the hue. One glyph set, eight tints, and a new status arrives with a slot already waiting. | Susan, Jony |
  | 3 | Icons ship on chrome, controls, the console and the topic pills. They do NOT ship beside a headline: the topic is a classification the pipeline actually made and may carry a mark, but "what kind of story is this" is an assertion no stage ever produced. This is a narrower line than the earlier blanket refusal and it keeps the part that was right. | Editor, Jony |
  | 4 | Source set is Lucide (ISC licence, Rule #8). Only the icons in use are committed, as source SVG, and the sprite is generated from them. | Carmack |
  | 5 | The manifest is a persisted surface and therefore a Pydantic contract with a generated schema, matching `design-system.md`'s existing icon rule. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | An icon-font | Renders as a missing glyph when it fails, needs a whole font pipeline, and cannot carry a per-part tint. | Carmack |
  | 2 | A runtime icon component library | Ships every icon's markup into the bundle and re-litigates a dependency the project does not need. | Carmack |
  | 3 | Inline SVG per component | The state the surface is in today; it is why there are two icons and no system. | Jony |
  | 4 | Multi-colour artwork per icon | Cannot be re-tinted per theme or per status, so a dark theme needs a second artwork set. | Susan |

---

### Row #6 - Pick the console's chart engine, on measured numbers

**REWRITTEN 2026-08-29.** The original row assumed a hand-written hover layer and rejected every drawing library. The owner overruled that, and the byte count the rejection rested on was four and a half times out of date. What follows is the replacement; the reversal itself is recorded in `docs/concepts/design-system.md`.

- **Scope:** Choose the console's chart engine against the three conditions and the measured costs below, wire the theme adapter that keeps `tokens.css` the only place a colour is decided, and prove the pattern end-to-end on one real chart.
- **Files touched:**
  - `frontend/package.json`, `frontend/package-lock.json`
  - `frontend/src/lib/charts/engine.ts` (new: the adapter - reads the tokens, renders server-side, hydrates)
  - `frontend/src/lib/charts/theme.ts` (new: computed custom properties -> the engine's theme object)
  - `frontend/src/lib/components/` - one converted chart
  - `frontend/src/lib/components/ThroughputTrend.svelte` - the caption that grows with the day
  - `frontend/bundle-baseline.json`
  - `frontend/tests/charts.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** The console renders complete with JavaScript disabled; a pointer, a tap and an arrow key each produce a readout naming the series, the value and its unit **in words**; every colour resolves from `tokens.css` in both themes with no hardcoded hex in any chart option; the reading routes import none of it, asserted by the bundle gate's per-route module list; the measured `/console/` delta is recorded; and **no readout box covers more than a third of the plot it sits on**, the engine's own tooltip included, measured on the rendered element rather than on the string that fills it.
- **Oracle:** Three halves, none of which a stub satisfies. **(a)** The prerendered `/console/` HTML contains the chart's `<svg>` marks before any script runs - fetched with JavaScript off and asserted on the raw HTML, not the rendered DOM. **(b)** Every route other than `/console/` has zero engine modules in the bundle gate's per-route list, so a stray top-level import fails the build rather than quietly shipping 188 KB to a reader. **(c)** A browser test opens the readout on the worst day the fixture holds - the day with the most runs, because that is the day the copy is longest - reads the readout element's own bounding box, and asserts its height is at most a third of `console.chart_height`. It asserts the box was found first, so it cannot pass by measuring nothing.

**Measured 2026-08-29, this tree, this bundler, gzipped, esbuild bundle + gzip -9 - the numbers the CHOICE was made against:**

| Candidate | gzip | Tree-shakes | SVG | Server-render |
| --- | --- | --- | --- | --- |
| Engine A, bar + line + pie + scatter + tooltip + legend | **188.4 KB** | barely | yes | yes |
| Engine A, bar only (its floor) | 160.0 KB | - | yes | yes |
| Engine B, the most-cited alternative | **270.1 KB** | no | yes | weak |
| Engine C, canvas-only | 22.6 KB | yes | **no** | **no** |
| `d3-scale` + `d3-array`, carried today | 20.5 KB | yes | n/a | n/a |

**Measured after it shipped, same day, from the files the build wrote - the numbers that are TRUE:**

| What | gzip | raw |
| --- | --- | --- |
| Engine chunk, only the chart types in use registered | **153,204 B** | 451,227 B |
| Same package imported whole | 345,959 B | 1,044,275 B |
| `/console/` first-load JS, before | 69,622 B | - |
| `/console/` first-load JS, after | **71,476 B** (+1,854, +2.7%) | - |
| Every other route | within +/-64 B toolchain noise | - |

About 40 B of the 1,854 is the toolchain, not the change: every unrelated route
on this machine read 36 to 63 B above its record in the same build.

The estimate and the artefact disagreed by 84 percent, in the direction that
mattered. The probe measured a bundle nobody shipped; the build measured the
file a browser downloads. **The correction that made the difference was
registering the funnel, the tooltip and the SVG renderer instead of importing
the package whole** - `frontend/src/lib/charts/core.ts` exists only to hold
that list, so adding a chart type is a deliberate edit with a re-measurement
beside it.

The first-load figure is the one that decides affordability, and it is 1,854 B,
not 153 KB: the engine is a dynamic import fetched only when a chart hydrates.
Roughly 257 KB and 3.7x, predicted above, were both wrong.

**A readout may not cover the chart it explains, and one does.** Measured
2026-08-29 and recorded in `docs/reference/measurements.md` under "How much of a
plot a chart readout covers": `ThroughputTrend`'s readout box stands **88 to 121
px over a 220 px plot, which is 40 to 55 percent of the chart it explains**.
`CompressionScatter` draws the same box, from the same markup, in the same
place, with two short lines - and covers about a quarter.

That pair is what makes this a copy problem and not a placement problem.
`ThroughputTrend`'s caption appends one clause per run of the day - 171
characters at the median, 221 on the three days that ran five times - and
nothing bounds how many times the pipeline runs in a day. So the limit goes on
the rendered box, where it binds whatever draws it, and the run medians come out
of the sentence.

A third of a 220 px plot is 73 px, which is about three lines at the console's
readout type size. The quarter `CompressionScatter` already measures clears it;
the caption fails it even at its 88 px floor. **Whether dropping the run medians
alone clears a third is not measured** - the two shares are, the effect of the
cut is not, so this row takes that measurement and records it rather than
predicting it (Rule #10).

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A drawing library ships on the operator surface. The reading surface stays library-free; an item's chart is a build-time asset and a reader has nothing to run. | owner, 2026-08-29 |
  | 2 | Three conditions bind any candidate: SVG not canvas, server-rendered at build time, and a measured gzipped cost recorded beside the decision. Engine C fails the first two at any size. | Carmack, Jony |
  | 3 | The cost is charged to one route that one person opens. Rule #2's actual ceiling is the 1 GB published site, which 188 KB once does not move - the site was 128,064,853 B and grows about 16.6 MB a published day. | Carmack |
  | 4 | The theme adapter reads the computed custom properties at mount and again on every theme change, so `tokens.css` stays the only place a colour is decided. A hardcoded hex in a chart option is a review failure, not a style preference. | Jony |
  | 5 | Hover, tap and keyboard readouts are the engine's for a chart the engine draws. **Corrected 2026-08-29 while building:** this row claimed the engine buys the readout. It does not - `frontend/src/lib/charts/frame.ts` already carries `pointerReadout`, covering mouse, pen, touch and keyboard with nearest-by-x hit testing, and two of the four existing charts were simply never wired to it. The engine earns its place on chart types the surface cannot draw today. Wiring the two unwired charts is Row #8's job and needs no dependency. | Susan, owner |
  | 6 | The earlier doctrine line about tooltips carrying critical information is narrowed rather than struck: a readout may not be the ONLY place a fact appears, and every value it shows is also derivable from the axis. | Jony |
  | 7 | **Existing hand-written charts are not ported.** Each has a browser-test suite bolted to its markup - `StageTimings.svelte` alone has about 15 assertions reading `data-decade-line`, `data-stage-mark` and `data-stage-zero`, two of which check geometry an engine does not emit. Porting buys the operator nothing they can see and risks losing reasoning those charts encode. The engine is how NEW charts are made; a hand-written one ports when it next needs real change. Strangler-fig, not big-bang. | Fowler, 2026-08-29 |
  | 8 | **The readout limit is a height against a height, never a character count.** The box wraps at the card's width, so one sentence is a different number of lines in a different panel. One measured box height against the plot height binds the hand-written charts and the engine's own tooltip alike, and it does not have to be restated when the engine changes. | Fowler, Jony, 2026-08-29 |
  | 9 | **Run medians leave the readout.** A caption that appends one clause per run has no bound, and how many times the pipeline ran is a property of the day rather than a choice anybody made. The readout names the day's own band and stops. A day's runs are already accounted for in `Runs and site size`, and a per-run number belongs beside them if it belongs anywhere. | Editor, Jony, 2026-08-29 |
  | 10 | Jony's ruling that a readout is pinned to the top of the plot and never to the pointer **stands, unchanged**. It is not what is wrong here: the chart that passes and the chart that fails use the identical pinned box. | Jony, 2026-08-25 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep the blanket ban and hand-roll a readout layer | The ban rested on a `/console/` weight of 66,550 B that was 4.5x stale, on "canvas cannot inherit a custom property" generalised to SVG engines that can, and on a prerender objection that does not hold for an engine with a build-time SVG mode. All three were wrong. | owner, over Carmack and Jony 2026-08-25 |
  | 2 | Engine B | 270.1 KB gzipped and it does not tree-shake - worse than the option it was proposed as a fallback to, which is why it was measured rather than assumed. | Carmack |
  | 3 | Engine C, canvas-only, at 22.6 KB | Cannot inherit a CSS custom property, so the token file stops being the source of a colour, and it cannot render at build time. Cheap and fails both conditions that matter. | Jony |
  | 4 | The engine on the reading routes too | A charting engine on a reading page is a runtime dependency for nothing: an item's chart is already a build-time asset. | Carmack, Jony |
  | 5 | A CDN copy of the engine | The HTTP cache is partitioned per site so the shared-cache argument is dead, and `script-src` is `self` only. | Carmack |
  | 6 | Porting `StageTimings` as the proving chart | Attempted and reverted the same day. It is the chart with no readout, so it looked like the best demonstration, until the test suite bolted to its hand-drawn markup made the cost clear. The funnel was built instead: new ground, no test rewritten, and it replaced a four-column table plus a 90-word paragraph with a shape. | Fowler, 2026-08-29 |
  | 7 | A character budget on the caption string | It measures the wrong thing. 171 characters is four lines in one panel and six in another, because the box wraps at the card's width - and it says nothing at all about a readout an engine draws. | Fowler |
  | 8 | Moving the readout to the pointer, or below the plot | The position is not the fault. `CompressionScatter` uses the identical pinned box and covers about a quarter, so moving a box that is too big only puts it over something else. | Jony |
  | 9 | Keeping the run medians and setting them smaller | It buys one line and spends legibility on the surface a person reads closest. The medians are a table's work, not a readout's. | Susan |

---

### Row #7 - The reference chart vocabulary

- **Scope:** The chart types the console needs and does not have - a different chart for a different question, which is the property the reference dashboard actually demonstrates.
- **Files touched:**
  - `frontend/src/lib/charts/` - `donut.ts`, `waterfall.ts`, `stacked.ts`, `sparkline.ts`, `targetbar.ts` (new)
  - `frontend/src/lib/components/` - `DonutGauge.svelte`, `TargetBar.svelte`, `WaterfallChart.svelte`, `StackedBars.svelte`, `Sparkline.svelte`, `KpiCard.svelte` (new)
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/tests/charts.spec.ts` (new)
  - `docs/concepts/design-system.md`
- **Acceptance gates:** Every new chart prerenders complete on the server and re-measures on the client; every one carries a legend whose swatches are the drawn colours; every one uses the row-3 chart ramp and none borrows a confidence-ramp hue; every one has a designed empty state; every one has a hover readout from row 6.
- **Oracle:** A test renders each chart type against a fixture whose expected geometry is computed independently in the test - a donut whose arc length equals its fraction of the circumference, a target bar whose marker sits at the target's fraction of the track, a waterfall whose final cumulative equals the sum of its deltas. A chart that draws a plausible but wrong shape fails.

| Chart | The question it answers | Modelled on |
| --- | --- | --- |
| Donut gauge | one share against a whole, with the count beside it | reference: the reliability scorecard |
| Target bar | a value against the target it should have hit, banded by distance | reference: the scorecard levers |
| Waterfall | how a total was built from ordered contributions | reference: the commitment burndown |
| Stacked bars | composition over time | reference: monthly consumption |
| Sparkline | direction at a glance, inside a card | reference: the account cards |
| KPI card | one number, its label, its movement, its tint | reference: the overview strip |

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A different chart per question is the point. One chart type reused for six questions is what makes the current console read as a single grey instrument. | Susan, owner |
  | 2 | Each chart type is a specification the engine draws, plus the arithmetic that turns a payload into that specification. The arithmetic is a pure function and is tested without a browser; the drawing is not ours to test. Row 6's reversal is what makes this the shape - the original row had every geometry hand-written. | Fowler |
  | 3 | No chart type ships without a named question it answers and a page it appears on. A chart added because the vocabulary would look complete is a chart nobody reads. | Jony |
  | 4 | The existing candle charts stay. They answer a question - the spread within a day - that none of the new types answers, and `design-system.md` already records why a line is wrong there. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A generic `<Chart type="...">` component | Collapses six different geometries behind one prop and makes every one harder to test than the six separate functions. | Fowler |
  | 2 | Animated chart entry | A reading surface that animates interrupts; the row-3 motion budget covers arrival, not drawing. | Jony |
  | 3 | 3D or pseudo-3D marks | Encodes a value in a dimension the reader cannot compare across. | Susan |

---

### Row #8 - The console rebuilt as panels

- **Scope:** The operator surface rebuilt in the reference panel language - a KPI strip, tinted status cards, real panels with elevation, tables that fit the screen, and charts at a size a person can read.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`, `+page.server.ts`
  - `frontend/src/lib/components/` - `Panel.svelte`, `StatusChip.svelte` (new); `FailureList.svelte`, `FailurePanels.svelte`, `StageTimings.svelte`, `ThroughputTrend.svelte`, `CompressionScatter.svelte`, `Viewport.svelte`
  - `frontend/src/lib/charts/run-history.ts`
  - `frontend/tests/console.spec.ts`
  - `docs/architecture/publishing/telemetry-series.md`, `docs/concepts/ui-shell.md`
- **Acceptance gates:** Zero horizontal scrollbars at or above 1024 (measured: seven today); page height materially below the 6562px measured on 2026-08-28, recorded as a real number; every figure keeps its existing label copy verbatim - this row changes the frame and the marks, never what a number means; both themes screenshotted; `/console/` gzipped route bundle recorded and under 140 KB.
- **Oracle:** The existing `console.spec.ts` assertions on every printed figure pass unchanged against the same fixture day. A rebuild that moved a number as well as its box fails it. Two new assertions are added: the horizontal-overflow count is zero, and every chart's drawn width is at least 320px.

**DELIVERED 2026-08-29, with one gate NOT met and one already met before the row started.**

| Gate | Result |
| --- | --- |
| Zero horizontal scrollbars at or above 1024 | **Met, and it was already met.** Measured zero at 1440px before this row touched anything - row 4's fluid frame had already removed all seven. This row's contribution is the assertion that keeps it at zero. |
| Every chart at least 320px | Met, after correcting the bound. The two charts under it were the KPI sparklines, which carry no axis and no label by design; holding a sparkline to a width meant for a plot is a category error, so the check excludes anything inside a KPI card and says why. |
| `/console/` under 140 KB | Met: 76,703 B. |
| Every printed figure unchanged | Met. 232 browser tests pass. |
| **Page height materially below 6,562px** | **NOT MET. Measured 8,794px, which is 34 percent higher.** |

The height gate and this plan's own rows 6 and 7 are in conflict, and the conflict is the plan's rather than the row's. The gate was written on 2026-08-28, before row 6 put a funnel on this page and row 7 put a KPI strip, a growth waterfall and a failure-mix chart on it. Four charts and two cards were added to the same page the gate asks to shorten. A row cannot both add the vocabulary and remove the height it costs.

What was actually wrong on 2026-08-28 was density, not length - a page of headings and tables on bare background with nothing to group by. That is fixed: five tables now sit in panels with sticky headers, two sections are real panels, and the run strip fills the frame instead of drawing at 16px inside 1,217. Whether the page should then be shortened is an editorial question about what the console needs to say, which is Editor's call and not a frame change. It is not smuggled into this row.

Two assertions changed rather than passing unchanged, and both encode the constant this row's decision 3 deliberately replaces: `runs rise from a shared baseline, on a 16px day track` asserted `width === 16`, and its sibling asserted a 4px gap. Every behavioural assertion in that test is kept - run 1 on the baseline, squares square, all squares equal, every day sharing a baseline, the gap holding its share. Only the two literals moved, and the test is renamed to stop encoding a number that is now a floor.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The console gets a real design budget. Doctrine changed in row 1 and this row is what that change was for. | owner, 2026-08-29 |
  | 2 | The label copy in `design-system.md`'s console table is untouched. That section is right, it was expensive to get right, and this row is about the frame around those words. | Editor |
  | 3 | `CELL_PX` and `GAP_PX` in `run-history.ts` become derived from the available width rather than fixed at 16 and 4, so the run grid uses the frame it is now given. | Carmack |
  | 4 | The console takes tint and elevation but still no display face, no gradient and no illustration - the row-1 replacement wording, applied literally. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A dashboard grid the operator can rearrange | State to persist, on a surface whose premise is that nothing computes at read time. | Carmack |
  | 2 | Rewriting the console's server loader in the same row | Mixes a data-correctness change with a visual one and makes the oracle meaningless. | Fowler |
  | 3 | Dropping the run grid for a chart | It is the one mark that shows every run of every day at once, and no chart in row 7 replaces it. | Jony |

---

### Row #9 - The digest surface, and the archive brought inside

- **Scope:** The reading surface spends its new width - side rail, beside-text visual, panel language on the day notice and the empty states - and the archive stops being a separate destination.
- **Files touched:**
  - `frontend/src/lib/components/DigestItem.svelte`, `DigestList.svelte`, `ItemMeta.svelte`, `ItemVisual.svelte`, `TopicPills.svelte`, `TopicSection.svelte`, `DayNotice.svelte`, `EmptyDay.svelte`, `SiteHeader.svelte`, `SiteFooter.svelte`, `ArchiveSearch.svelte`
  - `frontend/src/routes/archive/+page.svelte`, `frontend/src/routes/+page.svelte`
  - `frontend/tests/staged-day.spec.ts`, `archive.spec.ts`, `empty-day.spec.ts`
  - `docs/concepts/digest.md`, `docs/concepts/ui-shell.md`
- **Acceptance gates:** The measure holds at 52-80ch at every width; the empty, missing and degraded states all render and are screenshotted; the archive's search and month index still pass their existing specs; the read mark, theme choice and topic filter all still work; `/` and `/archive/` gzipped routes recorded.
- **Oracle:** Every assertion in the existing `staged-day.spec.ts`, `archive.spec.ts`, `topics.spec.ts` and `readstate.spec.ts` passes unchanged. Those tests encode what the page must SAY; this row changes only what it looks like, so a failure means the row changed a fact.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The archive is integrated, minimally, in this plan: the day's page grows a persistent way into previous days and the search field is reachable from the digest. The `/archive/` route stays, because it is a working bookmarkable surface and deleting it is a separate decision with its own reader cost. | owner, 2026-08-29; Editor |
  | 2 | Colour on an item stays spent on the confidence mark and the source swatch. The gradient goes on the chrome and never near an item: a page that looks confident and expensive while carrying a "may not match the source" mark is a mixed message. | Jony, Reader |
  | 3 | The meta line moves out of the text column into the side rail above 1024, so it stops interrupting the read. Below 1024 it stays where it is. | Jony |
  | 4 | Empty and missing states get the same panel language as everything else. They are normal states, they are frequently seen, and today they are the plainest thing on the site. | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Deleting `/archive/` in this plan | Breaks a bookmarkable URL to buy a tidier route list; integration delivers the ask without the loss. | Editor |
  | 2 | An infinite scroll merging every day into one page | Every published day becomes bytes on first load, and the ranked order of a single day stops being visible. | Carmack, Jony |
  | 3 | A card grid for the day's items | Row 4 decision 2: destroys the ranked-order contract. | Jony |

---

### Row #10 - Installability

- **Scope:** A web app manifest, the icon set behind it, and the `theme-color` meta - the minimum that makes the site installable, and nothing more.
- **Files touched:**
  - `frontend/static/manifest.webmanifest` (new)
  - `frontend/static/icons/` (new: 192, 512, maskable, apple-touch)
  - `frontend/src/app.html`
  - `frontend/svelte.config.js` (CSP `manifest-src` if required)
  - `frontend/tests/manifest.spec.ts` (new)
  - `docs/architecture/publishing/frontend.md`, `docs/concepts/ui-shell.md`
- **Acceptance gates:** The manifest validates, resolves under the GitHub Pages base path, and its icons 200 in the built site; `theme-color` matches the resolved theme in both modes; no new console error; total added bytes recorded.
- **Oracle:** A test fetches the built `manifest.webmanifest` under the configured `BASE_PATH`, asserts every declared icon path returns 200 from the built tree, and asserts the file contains no `gcm_sender_id` and that no source file references `Notification` or `PushManager`. A manifest that validates but 404s its icons under the project path is the standard way this breaks, and the test catches it.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Installability is consistent with Rule #1 and section 0a: a manifest is a static JSON file, it adds no request, no account, no notification and no code running off the reader's device. | Fowler |
  | 2 | Doctrine gains one explicit line in `ui-shell.md`: this site never calls `Notification` or `PushManager`. Installability makes the temptation concrete, so the ban is written down rather than implied. | Fowler, Reader |
  | 3 | Base-path discipline is the whole risk here and it is what the oracle tests. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A service worker in this plan | It is the only code this project would ship that outlives the tab, and a stale worker serving a stale bundle is the hardest bug class available. It is a separate Level-5 decision with its own kill-switch design, and it does not block anything here. | Carmack, Fowler |
  | 2 | `vite-plugin-pwa` for the manifest alone | A build-time dependency to write one JSON file. Revisit when the service worker is decided. | Carmack |
  | 3 | Offline precaching of the archive | Every published day downloaded on install, against a site already at 128 MB. | Carmack |

---

### Row #11 - Re-baseline, measure, and smoke every surface

- **Scope:** Re-derive every byte budget the surface work moved, record the screen-use measurement that never existed, and run the full section-12 browser smoke across every page, width and theme.
- **Files touched:**
  - `frontend/bundle-baseline.json`
  - `frontend/tests/payload-weight.spec.ts`
  - `docs/reference/measurements.md`
  - `docs/architecture/publishing/layout.md` (the cap date, re-derived)
  - `TODO/20260829-design-system-reset-plan.md` (closure)
- **Acceptance gates:** Full `pytest`, `ruff`, `mypy --strict`, `npm run check`, `npm run build`, `npm run bundle-gate`, `npm run test:browser` all green; the contract drift gate clean; every new number carries hardware, date and spread (Rule #10); the published site measured against the 1 GB cap and the cap date restated.
- **Oracle:** The bundle baseline is re-derived by building five times and taking the HEAVIEST per route, not the mean - a mean fires on half of all builds. The recorded per-day growth rate is measured from mature days only; the corpus holds days of 4, 10, 147, 731, 724 and 621 items and including the small ones halves the answer.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Re-baselining is its own row and lands last. A baseline derived while a sibling row is still unmerged is stale the moment the parent lands, and this project has already shipped one ceiling set from a stacked branch. | Carmack |
  | 2 | The screen-use table goes into `measurements.md` with the browser, the date and the commit. Rule #10 was applied to everything the runner touches and to nothing the reader sees, and that is part of why this plan was needed. | Carmack, Rule #10 |
  | 3 | A cap date moves on the RATE, not on the level, so the row records what every future published day costs after this plan - not only what the site weighs today. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Re-baselining inside each row | Eleven baselines, ten of them stale on merge. | Carmack |
  | 2 | Raising the bundle ceiling to fit the work | The budget is the platform, not a preference (section 10). If a row cannot fit, the row is simplified. | Carmack |
  | 3 | Estimating the per-day rate from the site total | Measured 2026-08-27: the level answer and the rate answer differed by a factor of about eighteen for the same change. | Carmack |

---

### Row #12 - Scrub the third-party product name from the repository

- **Scope:** Remove every occurrence of the reference dashboard's product name from tracked files, filenames, pull-request metadata and commit messages, and write the naming rule that keeps it out.
- **Files touched:**
  - `TODO/20260829-design-system-reset-plan.md` (renamed from the slug that carried the name)
  - `.github/agents/susan.agent.md`
  - `docs/agents/guardrails.md`
  - `CLAUDE.md` (section 0b)
- **Acceptance gates:** `git grep -i` for the name over every tracked path returns nothing; no filename carries it; every open and merged pull-request title and body is edited; the replacement wording still names a real, checkable reference rather than going vague.
- **Oracle:** A case-insensitive search over the full tracked tree AND over `git log --format=%B` for the working range returns zero hits. The search is case-insensitive on purpose: the name appeared in three casings across the repository, and a case-sensitive sweep would have reported clean while two of them survived.

**The replacement vocabulary.** The reference is described by what it is, never by what it is called: "the operator-dashboard reference screenshots", "the reference dashboard", "the reference panel language", "the reference chart vocabulary". Each row that cited a specific screen now cites the artefact - a reliability scorecard, a commitment burndown, an overview strip - which is more useful to a reader than the product name was, because it says what to look at.

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The name is removed everywhere, including from history. | owner, 2026-08-29 |
  | 2 | The reference itself is NOT removed. A visual decision that cites nothing is unreviewable, and the screenshots are the standing gold standard for this plan. What changes is how the source is named. | Jony |
  | 3 | A general naming rule lands with the scrub rather than a one-time cleanup, so the next agent does not reintroduce it: **a third-party product name is not a design vocabulary.** A design doc names the artefact and the property, never the vendor. | Fowler |
  | 4 | The rewrite of merged commit messages is a force-push to `main` and is the ONLY exception to section 8 besides `prune.yml`. It is separated from the file scrub so the file scrub can land immediately and the rewrite can be timed against the other agent's in-flight worktrees. | Fowler, Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Replace the name with an initialism or a codename | A codename for a specific product is the same disclosure with an extra step, and it is worse to read. | owner |
  | 2 | Drop the reference entirely and describe the target as "a modern dashboard" | Unreviewable. Every visual ruling in this plan cites a specific screen; "modern" cites nothing and cannot be checked. | Jony, Susan |
  | 3 | Leave merged commit messages alone | The owner asked for history, and `git log` is as public as the working tree on a public repository. | owner |
  | 4 | Rewrite history in the same commit as the file scrub | Couples a safe, instant change to one that force-pushes `main` while three sibling worktrees are checked out against it. | Carmack |

---

Execute autonomously per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md); AUTO every row; one worktree and one PR per row off `origin/main`; merge green-gated and one at a time; ESCALATE only on the four triggers in section 0.
