# Reading-page rebuild - a page that earns two minutes, and a ranking that knows what it covered

**Last Updated**: 2026-08-31
**Level**: 5 (widens two published contracts, mints a state surface, changes the default theme, moves a day's items to a runtime fetch, and restructures the reading surface)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 4; honour the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A 359-item day draws 15 items under five headings and puts 344 of them - 95.8 percent - behind five links. It has no first screen, no figure and ground, no time on any item, and a control that hides its own contents behind a horizontal scrollbar. Meanwhile the pipeline computes a rank score, a carrier count, a watchlist hit and a front-page flag for every item and publishes none of them, so the page cannot answer the one question a reader has: why is this story here. And it has no memory of a subject across days, so a running story's quiet update and an unknown subject's scoop score the same. |
| Hard scope - in | The reading routes `/`, `/[date]/`, `/[date]/[vertical]/` and `/archive/`; the shell (layout, header, footer, theme); `frontend/src/styles/tokens.css` and `app.css`; the served-projection contract and the move of a day's item list from build time to a browser fetch; a service worker with a kill-switch; five additive fields on the published item contract; the same-day duplicate cluster, the per-day source ceiling and the desk-shortfall line in `backend/`; the shared-subject term at assemble; **the cross-day subject credit - the gap measurement, a widened entity registry, a derived heat ledger, per-subject half-lives, and the decayed term shipping at zero weight**; new knobs in `config/appearance.json` and `config/idhazh.json`. |
| Hard scope - out | **The console route.** [TODO/20260830-observability-plan.md](20260830-observability-plan.md) is splitting `frontend/src/routes/console/+page.svelte` into three routes in a live worktree; five horizontal-scroll defects found there are recorded in row 3's Decisions table for that plan to take, and no row here opens that file. **Model-based entity recognition** - a future initiative; the one measurement that gives it a baseline is row 29. **Any reader-facing string for the subject credit** - Editor rules it out of the lead block until it can print the line that decided it, and that line needs cross-day subject identity no contract here supplies. **Turning the subject credit on** - row 33 ships it at zero weight; raising the weight is a separate owner decision with a number row 29 supports. An entity graph search tab. A cross-day `We covered this yesterday` line. Removing any published story from the default view. Publishing `events` or `entities` as reader-facing chips. A second font file. |
| ESCALATE triggers | (a) Any row whose work would drop, hide or unpublish a story that the payload holds - stop, this plan never trades coverage for shape. (b) The duplicate cluster in row 9 merging two different stories on the hand-checked day - a false merge is a story that never ran. (c) Any need to edit `frontend/src/routes/console/+page.svelte` - stop, a sibling plan holds it. (d) A reader route exceeding its committed record in `frontend/bundle-baseline.json` by more than 5 percent. (e) A second woff2 proposed for the wordmark. (f) **Any proposal to set `prerender = false`, drop `entries()`, or serve the reading routes from the `404.html` fallback - stop.** Row 23 moves the day's items to a fetch; it does not move the document. Dropping the document kills the prerender guard, the per-document content-security header, and the ability to tell a day that was never published from one that failed to load. (g) The served day payload's address or shape changing after row 22 merges - a reader's cached shell now depends on it. (h) Row 29's measurement showing most registry entries covered near-daily - then the subject credit does nothing and rows 30 to 33 COLLAPSE with that number cited. Stop and report it. (i) Any proposal to publish a heat value on `DigestItem` or any reader-facing surface, to let the credit subtract from a subject still producing coverage, to raise `entity_decay_weight` above zero in row 33, or to create a second registry for decay rates. |
| Chosen strategy | Spend the data the pipeline already computes before adding any. Give the item a surface so it can hold a chart, a hover state and a leading mark; give the day a time axis taken from the feed rather than from our own scheduler; give the reader five leads chosen across the whole day. Susan ruled the surfaces, Editor ruled the content, Fowler owns the contract change in row 4. |
| Owner decisions | Recorded below, taken 2026-08-31 under CLAUDE.md section 0. |
| Execution | autonomous orchestrator per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Parallel N = 4. |

### Owner decisions, 2026-08-31

| # | Question | Ruling |
| --- | --- | --- |
| 1 | The theme control | **Auto is removed. The site starts dark.** Light is an opt-in stored choice. One moon icon button, two states. Row 2. |
| 2 | The read mark | **Not a word and not a separate dot.** The source monogram carries it, in a ring, bigger. Row 12. |
| 3 | Horizontal scrollbars | **None, anywhere.** Row 3, plus the gate that keeps them out. |
| 4 | Which clock the time on an item comes from | **The feed's publish time.** Our own first-sight time is the fallback, used only where the feed's time is missing or implausible, and the page says which one it printed. Rows 4 and 17. |
| 5 | The wordmark | `Yen Idhazh` - capital Y, no hyphen, bigger, with a colour gradient. Row 6. |
| 6 | The footer | The links and the git build line stay. Everything else is reorganised. Row 5. |
| 7 | The archive's day list | It cannot keep adding one link per published day. Row 13. |
| 8 | Search | Ships, and the search field blends into the topic-pill control. Rows 7 and 13. |
| 9 | Where a day's stories come from | **A browser fetch, not the prerendered document.** The reason given is iteration cost: adding or removing an element must not require reworking six committed documents per published day. Rows 21 to 27. |
| 10 | Hardcoded CSS | **None.** Fonts, colours, sizes and spacing all resolve through the utility layer to the token scale. Row 1, widened from type sizes to every hardcoded value. |
| 11 | Entity ranking | Editor's shared-subject ruling approved in full. Row 15. Decay across days is deferred to its own plan. |
| 12 | The stale-date glyph | The agent's call. Row 17. |
| 13 | Sizing units | **Relative, never a hard pixel count.** A width is a share, a character count or a root-relative step. Row 1 carries the rule and the oracle; rows 12 and 18 are written to it. |
| 14 | Installability | **A progressive web app.** Row 28, which is only buildable once the day arrives by fetch. |
| 15 | Subject heat across days | **A credit that keeps a running story visible on a quiet day**, at a rate set per subject in config with a default. Rows 29 to 33. Held to zero weight until the owner turns it on. |

### Subject heat: the three features that answer to the word "decay"

The requirement was stated as a decay. Three different features answer to that word and only one is worth building. Editor, 2026-08-31.

| Feature | Ruling |
| --- | --- |
| Decay an accumulated credit | **Refused.** An accumulator on a live subject grows every day it runs, so a two-year story eventually outweighs every fresh story permanently. It also answers nothing: on a day the subject produces coverage, today's shared-subject count already said so. |
| A credit that keeps a running story visible on a quiet day | **This is the feature.** Rows 29 to 33. |
| A fatigue term stopping one subject leading five days running | **Refused as a decay.** It is a real problem and its control is a cap, not a rate - row 15 adds one lead per subject. A decay that did this would have to shrink a subject still producing coverage, which is the penalty that breaks the pandemic case the requirement was protecting. |

**What the half-life means, in one sentence a person can check:** the number of days our silence about a subject can last before a new story on it stops reading as the next instalment and starts reading as a fresh story.

**It is not an importance ranking.** A tournament final is enormously important and its half-life is short - a week later nothing new is an instalment. A pandemic's is long because a reader is still following it between instalments. So the credit's starting value is identical for every subject and only the fade rate differs. If a long-tier subject also started higher, the tier would be a permanent ranking of subjects wearing a decay's clothes, which is the refused first feature under a new name.

### Two findings that changed this plan before it was written

| # | Finding | Evidence | Consequence |
| --- | --- | --- | --- |
| 1 | **There is no global ranked order in `day.items`.** It is run-block, then desk-block in `config/taxonomy.json` order, then rank inside the desk. | The first 40 items of `frontend/public/digest/2026/08/30/digest.json` read `ai` x5, `energy` x8, `business-economy` x13, `world` x14. `cli.build_plan` extends one list per desk; `RunPlan` only asserts rank never increases within a desk. | A leading-stories block taken from the head of the published order would ship the top of the AI desk from run 1, not the day's biggest stories. Row 15 needs `rank_score`, which is why row 4 exists. |
| 2 | **`published_at` is genuinely the feed's time today, but the field cannot say so.** `rank.appeared_at` returns the feed's time, or our first-sight time when the feed's is absent or more than `collect.max_future_hours` ahead. Both land in one field. | Measured 2026-08-31 on the 2026-08-30 payload, 359 items: 252 distinct `HH:mm` values, and 4 items (1.1 percent) sit within two minutes of a run stamp. Feed-time to arrival runs 1.6 h minimum, 25.7 h maximum, 5.3 h mean; zero items older than 48 h; zero future-dated. | Ordering by the field is safe on this data. Printing a time without naming its clock is not, because the fallback is silent. Row 4 adds `time_source`. Nothing discards the feed's time: `discover._published_at` already reads `published_parsed` or `updated_parsed` and carries it through extraction into ranking. |
| 3 | **Prerendered documents are what grows the published site, and the reading routes emit six of them per day.** | Measured 2026-08-31 on the built tree, 10 published days: 38.81 MB of HTML across 61 files. For the 2026-08-30 day alone, six documents total 3.67 MB raw against 0.36 MB for the projected payload that would replace them - **a factor of 10**, because the five topic documents are the day filtered five ways. Rule #2 caps the published site at 1 GB. | The owner's decision to fetch is also the cheapest thing available to the cap. Rows 21 to 27. |
| 4 | **`RANK_VERSION` is dead.** It is defined in `backend/idhazh/rank.py` and read by nothing. | Fowler, 2026-08-31. Its own comment claims "a published order that moved for a reason nobody recorded is a published order nobody can defend", and no run has ever recorded it. | Row 15 changes the published order. The stamp is wired to the run manifest in a structural commit before the behavioural change, or the bump records nothing. Row 33 depends on that wiring. |
| 5 | **Zero of 30 registry entries is a subject of the kind the half-life anchors describe.** All 30 are standing organisations - 24 companies covered near-daily, plus five institutions on published calendars. | Editor, 2026-08-31. | A half-life on a company is either meaningless or wrong, because its gap is always near zero. Row 30 widens the registry; row 29 measures whether any gap exists to act on. |
| 6 | **`plan_vertical` is already stateful** - it reads `first_seen`, `already_published` and `settled_today` from `state/`. | Fowler, 2026-08-31. | Row 33 is a widening, not a new property. What is new is that heat is the first input whose value depends on when you ask, which is why its read window never includes the day being ranked. |

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Retire every hardcoded CSS value | - | A | DONE | yi-p01 | #320 | worker |
| 2 | Dark by default, and one moon button | - | A | DONE | yi-p02 | #332 | worker |
| 3 | No horizontal scrollbar, and the gate that keeps it out | - | A | DONE | yi-p03 | #337 | worker |
| 4 | Publish the ranking signal and name the clock | - | A | DONE | yi-p04 | #319 | worker |
| 5 | The footer becomes three lines | - | A | DONE | yi-p05 | #330 | worker |
| 21 | Extract the payload projector into one module | - | A | DONE | yi-p21 | #318 | worker |
| 29 | Measure the gap between our own mentions | - | A | DONE | yi-p29 | #324 | worker |
| 30 | The registry holds a subject, not only an organisation | - | A | DONE | yi-p30 | #317 | worker |
| 22 | The served day becomes a versioned contract | 21 | B | DONE | yi-p22 | #327 | worker |
| 31 | The entity-heat ledger | 30 | B | COLLAPSED | - | - | - |
| 6 | The wordmark: Yen Idhazh | 2 | B | DONE | yi-p06 | #339 | worker |
| 7 | The filter bar: topics and search in one control | 3 | B | PENDING | - | - | - |
| 8 | The item becomes a low-chrome card | 1 | B | DONE | yi-p08 | #329 | worker |
| 9 | Collapse same-story duplicates onto one item | 4 | B | DONE | yi-p09 | #342 | worker |
| 10 | A per-day ceiling on one source's share | 4 | B | DONE | yi-p10 | #334 | worker |
| 11 | A thin desk says what did not run | 4, 7 | B | PENDING | - | - | - |
| 23 | Split a reading route's load into facts and items | 22 | C | DONE | yi-p23 | #343 | worker |
| 12 | The monogram carries the read state | 2, 8 | C | DONE | yi-p12 | #335 | worker |
| 13 | The archive stops adding a link a day | 3, 7 | C | PENDING | - | - | - |
| 14 | Empty, missing and failed-day screens | 8 | C | DONE | yi-p14 | #336 | worker |
| 32 | Half-lives as config, with a fuse and a lifecycle | 30, 31 | C | COLLAPSED | - | - | - |
| 24 | The anchor and the unreachable state | 23 | D | DONE | yi-p24 | #345 | worker |
| 25 | The topic routes fetch their day | 23, 24 | D | DONE | yi-p25 | #349 | worker |
| 16 | Split the item's meta line | 12 | D | PENDING | - | - | - |
| 26 | The day route fetches its day | 25 | E | IN-FLIGHT | yi-p26 | #352 | worker |
| 15 | The day's leading stories | 4, 8 | E | DONE | yi-p15 | #347 | worker |
| 18 | Spend the width: the four-zone column model | 16 | E | DONE | yi-p18 | #360 | worker |
| 19 | Key points on long items only | 16 | E | PENDING | - | - | - |
| 17 | The time rail, and copy that stays true tomorrow | 4, 15 | F | PENDING | - | - | - |
| 27 | Invert the guards and correct every doc | 26 | F | PENDING | - | - | - |
| 33 | The decayed-heat term, shipping at zero weight | 15, 29, 32 | F | COLLAPSED | - | - | - |
| 28 | The site becomes a progressive web app | 26, 27 | G | PENDING | - | - | - |
| 20 | The full-day browser smoke | all | H | PENDING | - | - | - |

**One row ran that this plan never listed.** `test_retrieval_eval.py::test_the_ranking_clears_its_bar` failed on `main` itself and blocked every pull request here. It was not a ranking regression: re-running the 2026-08-26 four-arm decomposition put the re-encode at plus 0.00000 and the whole fall on 111 newly published items competing for the same ten slots against labels pooled when 44.5 percent of the archive carried a vector. `assist.recall_min` was re-derived by its own rule - two standard errors below the measured baseline - and lands on 0.61 from the failing tree and from the passing one alike. Owner authorised, PR #322. The bar now carries an expiry: about six published days of room at the measured slide of 0.01345 a day.

**A second row ran that this plan never listed.** On 2026-09-01 the pipeline opened `state/item-health/2026-09.csv`, and three tests that had been reading only the newest month's file went red on `main`, blocking every pull request here. The repair scoped each assertion to the whole ledger rather than to one shard, and found two more tests that had already gone blind the same way - reading 4,110 of 4,167 rows, and shrinking every month. PR #350.

**Rows 31, 32 and 33 are COLLAPSED under ESCALATE trigger (h), owner ruling 2026-08-31.** Row 29 measured the gap between our own mentions of a registry name at a median of **1 day - consecutive days, no silence at all** - with the longest silence anywhere in the record being 3 days, twice in 163 chances. A half-life set inside that range fires on every name every day; one set above it never fires. The credit has nothing to act on, and the ledger's cost would be paid by assemble on every run whether the credit was switched on or not. Row 30's contract widening stays: it is additive and inert. **What would bring these rows back:** a real subject curated into `config/watchlist.json` (which needs the 30-entry cap raised), or entity recognition landing - the missing piece is the registry, not the mechanism, and row 29 is the continuity baseline that initiative needs.

**Row numbers are identifiers, not sequence.** Rows 21 to 33 were appended after the plan was first written and are ordered by the `Depends-on` and `Parallel-group` columns like every other row.

**File contention.** Rows 8, 12, 16, 18 and 19 all edit `frontend/src/lib/components/DigestItem.svelte` and are serialised by their dependencies for that reason. Rows 15 and 17 both edit `DigestList.svelte`; 17 depends on 15. Rows 23, 25 and 26 edit the reading routes' `+page.server.ts` and `+page.svelte` in strict order. Rows 15 and 33 both edit `rank.py`; 33 depends on 15.

**Corrections found in execution, 2026-08-31.** The sentence that followed - "No two rows in one parallel group open the same file" - was false and is struck. Group A alone had rows 1, 3 and 5 sharing `app.css`, `TopicPills.svelte`, `archive/+page.svelte` and `SiteFooter.svelte`, and rows 2 and 3 sharing `config/appearance.json`. The waves were composed by checking the file lists rather than by trusting the claim. Two further couplings the table missed: **row 11 needs `FilterBar.svelte`, which row 7 creates, so its Depends-on is 4 and 7, not 4 alone**; and **`UiConfig` has two exposure points**, `app_config.py` and `appearance_config.py`, so any knob on it moves two models, two schemas, two changelogs and four fixtures.

**ESCALATE trigger (d) cannot fire as written.** It names a route exceeding its committed record in `frontend/bundle-baseline.json`; that file and the first-load byte ratchet were deleted on 2026-08-30. `npm run bundle-gate` now checks the encoder and the page ceilings in `config/idhazh.json`, and **no reading route is capped** - so a reading-page row moves no ceiling and the trigger has no instrument. Rows 5, 8 and 22 measured their own weight instead and recorded it.

**Why the shell migration and the subject credit are in this plan and not their own.** Fowler ruled both separate plan-docs. Overruled here on facts Fowler did not weigh. For the migration: every row of this plan edits a file it moves, and no row has started - two plans against `DigestList.svelte`, `DigestItem.svelte` and three `+page.server.ts` files would conflict on 12 of 20 rows. For the subject credit: the owner asked for one plan, and rows 15 and 33 both change `rank.py` and the published order, so splitting them puts two live ranking changes in two merge windows nobody can attribute between. The seam Fowler asked for survives as three rules, recorded in row 33.

## 2 - Row #1 - Retire every hardcoded CSS value

- **Scope:** Every hardcoded font, colour, size and space on the reading surface becomes a utility that resolves to the token scale, so row 8's contrast change has a scale to raise.
- **Files touched:**
  - `frontend/src/styles/app.css`
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/lib/components/ItemMeta.svelte`
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/src/lib/components/TopicPills.svelte`
  - `frontend/src/lib/components/SiteFooter.svelte`
  - `frontend/src/lib/components/EmptyDay.svelte`
  - `frontend/src/lib/components/SourceMark.svelte`
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/tests/tokens.spec.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; `npm run bundle-gate`; `frontend/tests/tokens.spec.ts` green; rendered `font-size`, `line-height` and `color` unchanged or changed only to the nearest token step, recorded per element.
- **Oracle:** a source grep over `frontend/src/routes/` and `frontend/src/lib/components/` returns zero matches for a bracketed arbitrary value in a utility class - `text-[`, `leading-[`, `bg-[`, `border-[`, `p-[`, `gap-[`, `w-[`, `h-[` - **and zero matches for a `px` literal in any authored style block**, outside the console route. Both are asserted in `tokens.spec.ts` so neither can come back.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every step keeps its paired leading. A size without a leading is half a decision, and the token file already pairs them. | Susan |
| 2 | Where a hardcoded value sits between two token steps, round to the nearer step and record the pixel delta in the PR body. Inventing a token to preserve a number is how the pile came back. | Susan |
| 3 | The scope is every hardcoded CSS value, not only type. Owner, 2026-08-31. Colour is the one that matters most: a hex in a component is a colour the dark theme cannot override, and dark is about to become the default. | owner |
| 4 | **A size is relative, never a hard pixel count.** Owner, 2026-08-31. The four units allowed, and what each is for: `%` and `fr` for a share of the space available; `ch` for a text measure, because a reading measure is a character count and not a width; `rem` for anything that should scale when a reader raises their browser's font size; `clamp()` where a value must move between two of those. A `px` literal in an authored style block is a value that ignores a reader who set their text larger. | owner, Susan |
| 5 | **Two carve-outs, and only two.** A hairline is `1px`, because a border that scales stops being a hairline. A media-query breakpoint keeps its committed value in `frame.breakpoints_px`, because a media query cannot read a custom property and the breakpoints are already a config surface. Both are exempted by name in the oracle rather than by a general escape. | Susan, Fowler |
| 6 | A genuinely dynamic value - a computed width, a chart coordinate - stays inline, which the design system already permits. The oracle greps authored style blocks and utility classes, not `style=`. | Fowler |
| 7 | The console route is excluded. A sibling plan holds it. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Add tokens matching the existing arbitrary values | Preserves the pile under new names and leaves the scale unusable. | Susan |
| 2 | Do this inside row 8 | Two risk profiles in one PR: a no-op refactor and a visual change. A regression could not be attributed. | Fowler |

## 3 - Row #2 - Dark by default, and one moon button

- **Scope:** The dark theme becomes the base, light becomes the override, and the three-state theme group becomes one moon button with two states.
- **Files touched:**
  - `frontend/src/styles/tokens.css`
  - `frontend/src/app.html`
  - `frontend/src/lib/theme.ts`
  - `frontend/src/lib/components/ThemeToggle.svelte`
  - `frontend/src/lib/icons/generated.ts` and its source SVG set
  - `config/appearance.json`
  - `frontend/tests/tokens.spec.ts`
  - `frontend/tests/icons.spec.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; contract drift gate green after `config/appearance.json` changes; `icons.spec.ts` green with `theme-light` removed from the manifest in the same commit; first painted frame is dark with JavaScript disabled; first painted frame is light with `idhazh:theme=light` stored and no dark flash.
- **Oracle:** a Playwright check that loads every route three ways - no stored choice, `light` stored, `dark` stored - and asserts the computed `background-color` of `<body>` on the first frame matches the expected theme in all three, with zero intermediate repaint.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `:root` carries the dark values; `[data-theme='light']` is the override; the inline script's `catch` branch sets `dark`. A document with no attribute must paint dark. | Susan |
| 2 | One `<button>`, not a group and not a disclosure. Two states need one control; the disclosure Susan proposed on 2026-08-30 existed only to preserve Auto, and Auto is gone. | owner, Susan |
| 3 | The glyph never flips. The page is the state indicator; a flipping icon is a second, weaker copy of it. `aria-label` names the action - `Switch to the light theme` - not the state. No `aria-pressed`. | Susan |
| 4 | Storage always holds `light` or `dark`. Absence of a key never means "the default", or the day the default moves every stored reader moves with it silently. | Susan |
| 5 | `<meta name="color-scheme">` becomes `dark light`. The two media-scoped `theme-color` tags collapse to one unconditional `#0b0e14`, because a reader whose system says light and who has chosen nothing now gets a dark page. | Susan |
| 6 | `digest.theme_default` moves to `"dark"` and stays a knob (Rule #6). | Fowler |
| 7 | `tokens.spec.ts` asserts "every theme colour has a dark override" today. It inverts to "a light override" in this commit or it silently passes on the wrong thing. | Susan |
| 8 | `ThemeChoice`'s `system` member, `watchSystem`, the system branch of `resolve`, and the `theme-light` sun glyph are deleted. | owner |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep Auto as a third state behind a disclosure | The owner removed Auto. What a reader loses is a theme that follows a sunset schedule; what they get is a control with one obvious action instead of three. | owner |
| 2 | Leave `:root` light and set `data-theme="dark"` in `app.html` | The no-script and pre-script frame would still be light, and that frame is what a slow connection shows longest. | Susan |

## 4 - Row #3 - No horizontal scrollbar, and the gate that keeps it out

- **Scope:** Remove every horizontal scroll container on the reader-facing surface, fix the one live overflow defect, and add the gate that stops another one appearing.
- **Files touched:**
  - `frontend/src/lib/components/TopicPills.svelte`
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/src/lib/components/SourceCutRange.svelte`
  - `frontend/src/styles/app.css`
  - `config/appearance.json`
  - `frontend/tests/layout-overflow.spec.ts` (new)
- **Acceptance gates:** `npm run check`; `npm run build`; drift gate green; the new spec passes on every route at 360, 801 and 1536 CSS px in both themes.
- **Oracle:** `document.documentElement.scrollWidth <= document.documentElement.clientWidth` on every route, at three widths, in both themes. One spec, and it is the only thing that gives this ruling a memory.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The pill row wraps. `overflow-x-auto`, `snap-x`, `snap-start` and `shrink-0` come off; `whitespace-nowrap` stays, because it keeps a topic name from breaking mid-word and cannot cause a scrollbar once the row wraps. | Susan |
| 2 | Overflow past `ui.topic_pills_max` (new knob, default 8) goes inside a native `<details>` whose summary reads `+N more`. Priority is decided by count at build time, never by measuring pixels at runtime - a pixel-measured row is wrong until script runs, on a site where every page is prerendered. | Susan |
| 3 | **A live defect ships fixed in this row:** the archive story grid sets `--auto-grid-min: 22rem` (352px) while content at a 360px viewport is 328px, so `minmax(352px, 1fr)` overflows by 24px. The guard goes into `.auto-grid` once, as `minmax(min(var(--auto-grid-min), 100%), 1fr)`, and every caller is fixed. | Susan |
| 4 | `SourceCutRange.svelte`'s scroll container is deleted. `chartWidth(measured, fallback)` already re-measures on the client, so the container only ever shows during the prerendered first frame - which is exactly when a scrollbar is worst. | Susan |
| 5 | **Five console defects are found and not fixed here.** `console-table`'s `overflow-x`, the run strip's `overflow-x-auto`, the failure-list table, the model-card grid minimum, and every console chart's 760px prerendered draw width on a viewport under about 792px. They are recorded for [TODO/20260830-observability-plan.md](20260830-observability-plan.md), which holds that file. ESCALATE trigger (c). | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Hide the scrollbar with `scrollbar-width: none` | Keeps the control that hides its own contents and removes the only hint that more exists. Strictly worse than what is there. | Susan |
| 2 | A fluid grid for the pills | Pills are variable-width labels. A grid gives `Business and Economy` the same track as `AI` and turns a six-pill row into a wall of boxes. | Susan |
| 3 | Runtime priority-plus measured in pixels | Needs measurement before it is correct, so the prerendered document is wrong until hydration. | Susan |

## 5 - Row #4 - Publish the ranking signal and name the clock

- **Scope:** Four additive fields on the published item - the reason a story is in the digest, and which clock its time came from.
- **Files touched:**
  - `backend/idhazh/contracts/` (the digest item model)
  - `backend/idhazh/rank.py`
  - `backend/idhazh/assemble.py`
  - `schemas/digest-day.schema.json` (generated)
  - `frontend/src/lib/payload/types.ts` (generated)
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; contract drift gate regenerates byte-identical; every committed payload under `frontend/public/digest/` still validates against the new schema; `npm run build` prerenders every existing day with the fields absent.
- **Oracle:** every day payload already committed loads through the new reader with no error and no field invented - a read-side migration test that opens all ten committed days and asserts an absent field reads as unknown, never as zero and never as a default that means something.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fields are `carried_by`, `watchlist_hit`, `on_front_page` and `rank_score`, all already computed on `PlannedItem` in `rank.py` and written today only to a gitignored file. This row publishes them; it computes nothing new. | Editor, Fowler |
| 2 | A fifth field, `time_source`, names which clock `published_at` came from - the feed's, or our first sight. `rank.appeared_at` already chooses between them and the choice is currently invisible. Without it, row 17 prints a time it cannot vouch for. | Editor |
| 3 | All five are optional and appended. Ten committed days omit them, and an absent value reads as unknown - never as `0`, which for `carried_by` would be a false claim. Schema `version` stamped, `changelog` entry appended, read-side migration in the same commit (CLAUDE.md section 11). | Fowler |
| 4 | `carried_by` counts syndication of one canonical URL, because `rank.merge` groups by URL. It is **never** rendered as "also covered by N sources" - two outlets writing their own piece produce two addresses and both read 1. Row 9 owns the honest version. | Editor |
| 5 | This is the Level-5 half of the plan. It exists because the owner authorised the leading-stories block and the feed-time rail, and finding 1 proves neither is buildable without it. If the owner refuses, row 15 collapses to a two-per-desk block chosen by position and row 17 loses its fallback label. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Compute the lead block in the browser from what is already published | Re-ranking at read time on a surface whose premise is that nothing computes at read time, and it would print a number nobody measured (Rule #10). | Carmack |
| 2 | Publish `rank_score` only | `carried_by`, `watchlist_hit` and `on_front_page` are what let the page say *why* a story leads. A bare score is a number with no sentence. | Editor |
| 3 | Two separate time fields instead of `time_source` | Doubles the field count to answer a question one enum answers, and leaves two fields that can disagree. | Fowler |

## 6 - Row #5 - The footer becomes three lines

- **Scope:** Six blocks down to three, links first, with two day-facts moved to where the day is.
- **Files touched:**
  - `frontend/src/lib/components/SiteFooter.svelte`
  - `frontend/src/lib/components/DayNotice.svelte`
  - `frontend/src/routes/+layout.server.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; `npm run bundle-gate` with any route record re-taken and recorded; no fact removed from the site, only relocated or merged.
- **Oracle:** a text-diff assertion over the prerendered `/`, `/404`, `/archive/` and `/evals/` documents proving every fact the old footer printed still appears exactly once somewhere on the page that owns it - and that the routes rendering no day no longer carry the day's run facts at all.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Final shape, in order: the three-link nav; the git-and-retention line merged into one sentence; the verification sentence last, at the smallest step. | Susan |
| 2 | The run number and time move to `DayNotice`. A stamp about today's run, printed eight screens below today, is filed in the wrong place. | Susan |
| 3 | The skipped-story count dies in the footer. `DayNotice` already prints it; the footer's copy is the same fact twice on one page. The footer's reason clause - that we could not read enough of the page to summarize fairly - merges into the `DayNotice` sentence so nothing is lost. | Susan |
| 4 | `DayFacts` shrinks to `{ retention_window_months }`. Today the whole day travels on the root layout into every prerendered page including `/404` and `/evals/`, which render no day. The saving is measured against `frontend/bundle-baseline.json` in this commit, with hardware and date, and recorded whatever it turns out to be (Rule #10). | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Delete the verification sentence | It is the only sentence telling a stranger why the confidence mark exists. Removing it costs the reader the meaning of a mark on every item. | Susan |
| 2 | Keep the run stamp in the footer as well | A fact stated twice on one page reads as two facts. | Susan |

## 7 - Row #6 - The wordmark: Yen Idhazh

- **Scope:** The wordmark becomes `Yen Idhazh`, roughly twice its current size, on a five-stop gradient tuned for a dark ground.
- **Files touched:**
  - `frontend/src/lib/components/SiteHeader.svelte`
  - `frontend/src/styles/tokens.css`
  - `config/appearance.json`
  - `frontend/tests/tokens.spec.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; drift gate green; `bundle-gate` unchanged - no new font file (ESCALATE trigger (e)); every gradient stop reads at least 4.5:1 against `--color-bg` in both themes.
- **Oracle:** `tokens.spec.ts` computes the WCAG relative-luminance ratio of every `--gradient-wordmark` stop against `--color-bg` in both themes, from the committed hex values, and fails below 4.5:1. Arithmetic over committed values, so the spread is zero by construction.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Title case, not uppercase. The owner named the string with a capital Y and a capital I; `text-transform: uppercase` makes it a different string. | Susan |
| 2 | Size is `clamp(1.75rem, 1.2rem + 2.2vw, 2.75rem)` - 28px at 360px and 44px from 1280px up, against 20px today. Not 52px: the header sits on every route, and 52px is 8 percent of a 640px phone screen spent before the first story. | Susan |
| 3 | Weight 300, one weight at every width. The committed variable face covers 100 to 900, so the weight axis is free. At 28px on a dark ground, 200 through a clipped gradient shimmers on a low-DPI panel. | Susan |
| 4 | Tracking holds the ratio, not the pixel: `0.06em`. A fixed 4px at 28px is 0.14em and breaks the word into separate letters. | Susan |
| 5 | Five stops at 135deg, `background-size: 100%`. Seven stops across roughly 200px of glyphs puts a stop every 28px and the middle three read as one band. | Susan |
| 6 | **No animation.** The named set is `fadeIn`, `shimmer`, `toastIn`; a cycling `background-position` is a loop rather than a response, `prefers-reduced-motion` is a hard kill-switch so it would need designing twice, and the motion rule permits `transform` and `opacity` only. What is lost is the moving shimmer; what buys it back is size, five stops and a wider angle - and those survive a screenshot, reduced motion and a battery. | Susan |
| 7 | `--wordmark-size` and `--wordmark-tracking` are declared in the `:root` scale block outside both theme blocks. A scale is not a colour. | Susan |
| 8 | Dark gets its own stop set, because dark is now what most readers see. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A second, geometric display face | A second woff2 on every route, bought for the letterforms of ten characters on one string. The committed face already supplies the light weight the reference effect actually uses. | Carmack, Susan |
| 2 | Animate the gradient | Decision 6. | Susan |
| 3 | Link a font CDN | The project self-hosts because the HTTP cache is partitioned per site, so the shared-cache argument is dead, and `default-src` is `self`. | Carmack |

## 8 - Row #7 - The filter bar: topics and search in one control

- **Scope:** One panel holding a search field and the wrapped topic pills, used on both the digest and the archive.
- **Files touched:**
  - `frontend/src/lib/components/FilterBar.svelte` (new, replacing `TopicPills.svelte`)
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/src/routes/archive/+page.server.ts`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; `layout-overflow.spec.ts` from row 3 green; drift gate green; the archive's on-device encoder download does not start on any keystroke.
- **Oracle:** a Playwright check that types into the archive field, asserts the visible list filters, and asserts zero network requests to the model directory - then clicks `Search` and asserts exactly one.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The pills are visible at rest, never behind the field and never collapsed as a set. The only thing a disclosure ever holds is topic nine and beyond, and its summary states how many. | Susan |
| 2 | On the digest, typing filters the day already on the page - no navigation, no URL change, no fetch. On the archive, typing filters the loaded list by title and only the `Search` button starts the on-device search, so the cost is named before the click. | Susan |
| 3 | The panel is sticky only at 1024px and up, where it is one row. Below that it can be four lines plus a field, and a control occupying a third of a phone screen permanently is screen the reader paid for. 1024 is already a committed breakpoint. | Susan |
| 4 | With no script the field hides itself through a `<noscript>` style rule and one sentence replaces it. A dead input that swallows typing is worse than no input. The pills are prerendered links and keep working. | Susan |
| 5 | The archive gains per-topic totals, one integer per vertical, computed in `+page.server.ts` which already loads every day. The pill count and the list count are different numbers and never share a sentence. | Susan |
| 6 | The archive's state and scope sentences move up under the panel. Today they sit below the story list, so the control is behind the answer. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A search field that expands to reveal filters | Hides the filter set behind a control, which is the failure this row exists to avoid. | Susan |
| 2 | Keep two separate blocks | The reason the top of the page is tall is that a field and a pill row each claim their own band of vertical space. | owner |

## 9 - Row #8 - The item becomes a low-chrome card

- **Scope:** The item gains a surface, a radius, a hairline and a hover state, and the type contrast rises onto the token scale.
- **Files touched:**
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/styles/app.css`
- **Acceptance gates:** `npm run check`; `npm run build`; `bundle-gate` records re-taken; `layout-overflow.spec.ts` green; a `prefers-reduced-motion: reduce` run shows no movement of any kind.
- **Oracle:** a Playwright check reading the item's computed `box-shadow` and `border-color` at rest and on hover, in both themes, asserting the rest state carries no shadow and the hover state carries `--shadow-md`; and asserting `transform` is `none` in both states.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Surface on page ground, `--radius-lg`, hairline, **no shadow at rest**. `--shadow-md` and an accent-tinted border arrive on `:hover` and `:focus-within`. | Susan |
| 2 | **No lift.** The title is a heading, not a link; a 2px rise repeated on 359 rows is an affordance lie repeated 359 times. The hover claim is "these lines belong together", and shadow plus border says it in full. | Susan |
| 3 | `prefers-reduced-motion` must remove a transform, not shorten one. `app.css` zeroes `transition-duration` globally, which turns a 2px rise into an instant jump. The media query gains `transform: none` in the same commit, so the rule is right before any transform ever ships. | Susan |
| 4 | Title to `--text-2xl`, summary stays at the reading step, meta to `--text-xs`. Row 1 is the precondition: contrast cannot be raised on a pile. | Susan |
| 5 | The comment "Hairline rules rather than cards: seventeen boxes of chrome on a page whose product is prose is chrome winning" is replaced, not ignored. It named what was removed and never what the reader gave up, so under the guardrails it never bound - and it cost four things: figure and ground on the whole reading surface, the container the item's chart needed, an anchor for a top-of-page list, and any hover or focus feedback. | Susan |
| 6 | In the dark theme the item separator takes `--color-rule-strong`. `--color-rule` on `--color-bg` reads 1.36:1 by arithmetic over the committed values; `--color-rule-strong` reads 1.77:1. Dark is now the default, so this is the figure-and-ground story most readers get. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A full card with a resting shadow | Seventeen elevated boxes on a page whose product is prose. The resting state needs to separate, not to float. | Susan |
| 2 | Hover lift plus shadow | Decision 2. | Susan |
| 3 | Keep hairline rules and add elevation nowhere | Leaves the reading page with one surface colour, which is a page where nothing is in front of anything, and leaves the chart with no container. | Susan |

## 10 - Row #9 - Collapse same-story duplicates onto one item

- **Scope:** Cluster a day's items on the vectors the payload already carries, keep the strongest, and say so on it.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/contracts/` (the digest item model)
  - `schemas/digest-day.schema.json` (generated)
  - `frontend/src/lib/payload/types.ts` (generated)
  - `frontend/src/lib/components/ItemMeta.svelte`
  - `config/idhazh.json`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; every committed day re-validates; a hand-checked day recorded in the PR body with the false-merge count.
- **Oracle:** on a hand-labelled fixture day, every cluster the pass forms contains only items a person marked as the same story - a false-merge count of zero. A false merge is a story that never ran, which is ESCALATE trigger (b).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Clustering runs at build time over `DigestDay.embeddings`, which is already published. Nothing computes at read time. | Carmack |
| 2 | The collapsed items stay in the payload, keep their anchors and keep their archive entries. Only what the default view draws changes. Nothing is unpublished (ESCALATE trigger (a)). | Editor |
| 3 | The line reads `Also covered by N other sources today.` - never derived from `carried_by`, which counts syndication of one address and reads 1 when two outlets write their own piece. | Editor |
| 4 | Where nothing clusters with an item: `Only one of our sources carried this.` Phrased as a fact about our feed set, never as a claim about the world. | Editor |
| 5 | The similarity threshold is a knob in `config/idhazh.json` with a sane default (Rule #6). | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Print `carried_by` as a source count | False on the most common case - independent coverage produces distinct URLs and `rank.merge` groups by URL. | Editor |
| 2 | Cluster in the browser | Read-time computation on a prerendered surface. | Carmack |
| 3 | A cross-day `We covered this yesterday` line | Needs `entities` on `SearchIndexEntry`, which is a separate contract change. Out of scope, and a wrong follow-up claim is a factual error a reader can check. | Editor |

## 11 - Row #10 - A per-day ceiling on one source's share

- **Scope:** A cap on how much of one day one publication may fill, across desks and runs.
- **Files touched:**
  - `backend/idhazh/rank.py`
  - `backend/idhazh/cli.py`
  - `config/idhazh.json`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; a replay over the 2026-08-30 plan recording each source's share before and after.
- **Oracle:** replayed over a real day's candidate set, no `source_id` exceeds the configured share, and the item count does not fall by more than the displaced candidates that were replaced - a displacement, not a deletion.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `collect.max_per_source` is 2 per desk per run. Five desks times five runs times two allows 50 items from one publication in one day - 13.9 percent of a 359-item day - and nothing counts it across the day. | Editor |
| 2 | The ceiling is a share knob in `config/idhazh.json`, not a constant (Rule #6). The value is the owner's call; the mechanism is this row. | Editor, Fowler |
| 3 | A capped candidate is replaced by the next candidate on its desk, never dropped to a shorter day. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Tighten `max_per_source` per desk instead | Starves a desk where one publication is genuinely the best source, and still does not bound the day. | Editor |
| 2 | Cap in the frontend | The page renders; it does not decide what ran. | Fowler |

## 12 - Row #11 - A thin desk says what did not run

- **Scope:** A desk with few stories says why, so a quiet desk and a broken feed stop looking identical.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/contracts/` (the vertical reference model)
  - `schemas/digest-day.schema.json` (generated)
  - `frontend/src/lib/payload/types.ts` (generated)
  - `frontend/src/lib/components/FilterBar.svelte`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; every committed day re-validates with the fields absent.
- **Oracle:** on a fixture day with one deliberately starved desk, the line renders with the real considered and rejected counts; on a healthy desk it does not render at all.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `VerticalPlan` already carries `considered`, `too_old` and `below_feed_floor`, committed in the run manifest beside `digest.json`. `DigestVerticalRef` carries only id, name and count. This row appends the three. | Editor |
| 2 | The line fires only where the desk is thin. A shortfall sentence under every desk is a column of absences pretending to be information. | Editor |
| 3 | Copy names the count and the reason in plain words - how many the feeds offered and how many were too old - never a field name. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Show feed health on the reading page | A fact about our pipeline, not about a story. The standing refusal holds; the console answers it for the one person who asks. | owner |

## 13 - Row #12 - The monogram carries the read state

- **Scope:** The source monogram becomes bigger, becomes a ring, moves to the item's leading edge, and carries read state as fill.
- **Files touched:**
  - `frontend/src/lib/components/SourceMark.svelte`
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/styles/tokens.css`
  - `frontend/tests/tokens.spec.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; `layout-overflow.spec.ts` green at 360px; the dark swatch bound asserted; a screen-reader tree showing the read state on a read item.
- **Oracle:** `tokens.spec.ts` asserts all eight `--source-swatch-*` values read at least 1.5:1 against `--color-surface` in **both** themes, by arithmetic over the committed hex values. Below that the fill is not filled and the whole ruling collapses to brightness alone.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Dim plus font weight is one signal twice, not two.** Both are less ink, and they fail together on a cheap panel, in sunlight and at arm's length. The third cue is fill present or absent - an area difference, which survives every condition brightness does not. | Susan |
| 2 | Ring `1.75rem`, up from a `1.25rem` square - a 1.4x rise, and the largest that keeps the leading column off the prose at the narrowest width. Circle, hairline border in both states, letters at `--text-xs` weight 600. The border takes `--color-rule-strong` when unread and `--color-rule` when read; the swatch is the fill only. A hairline in a swatch reads 1.1:1 in light and is not on screen. **The ring scales with the reader's font size, which a pixel value would not** (row 1, decision 4). | Susan |
| 3 | The mark moves to a leading grid column on the item at **every** width. Today it lives in `ItemMeta`, which moves into a 14rem right rail at 1024px and up - a read indicator 14rem from the title it qualifies is paired with nothing. `ItemMeta` keeps the source name and drops its copy of the mark. | Susan |
| 4 | The dark swatches read 1.16:1 to 1.24:1 against `--color-surface` today, by arithmetic on 2026-08-31. All eight are re-tuned to at least 1.5:1 in this commit. This is a perceptibility floor for a decorative tint, deliberately far below the 3:1 that binds a fill carrying meaning - the source is named in words on the same line. | Susan |
| 5 | The visible `Read` chip dies, per the owner. A visually-hidden `Read.` sits inside the heading, because a fill and a font weight are announced to nobody. The mark itself stays `aria-hidden`; its letters duplicate the source name beside it. | Susan |
| 6 | A read item is never dimmed below `--color-text-secondary`. A dimmed item reads as "you cannot have this" rather than "you already had this". | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Dim plus weight, with no fill change | Decision 1. What the reader loses is the state itself in any condition where brightness is unreliable. | Susan |
| 2 | Keep the eyebrow dot | It encodes read state today with no legend anywhere on the page - filled means unread, hollow means read, and nothing says so. A dot with no sentence. | Susan |
| 3 | Colour the ring border with the source swatch | 1.1:1 against the surface in light. Not visible. | Susan |

## 14 - Row #13 - The archive stops adding a link a day

- **Scope:** The archive's day list stops growing one link per published day and becomes a fixed recent list over month rows.
- **Files touched:**
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/src/routes/archive/+page.server.ts`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; drift gate green; `layout-overflow.spec.ts` green; the day links still work with JavaScript disabled.
- **Oracle:** a fixture archive of 700 published days renders at most `archive_recent_days` rows plus one row per month plus one row per prior year, and the prerendered document's day-list byte count grows with months, not with days.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three blocks: the newest `ui.archive_recent_days` days (new knob, default 7) as rows carrying the long date, the story count and a partial mark; one `<details>` row per month reading `20 of 31 days` plus a story count; one `<details>` per prior year wrapping its months. Every field already exists in `data.days`. | Susan |
| 2 | At 700 days a reader sees about 21 rows instead of about 88 lines of dates. The surface grows with months, and months arrive twelve a year. | Susan |
| 3 | The day links are kept, not deleted. They are the archive's only script-free surface - the page's own `<noscript>` says the story list needs JavaScript. | Susan |
| 4 | `Show N more` on the story list is unchanged. It extends a list already on the page, which is the correct shape for that job. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A month-grouped calendar heat grid | Colour carrying meaning with no second signal. The month row's `20 of 31 days` says the same thing in words and spends no colour. | Susan |
| 2 | A jump-to-date input | A third field on a page that already has one. Month rows reach any date in two clicks and `/YYYY-MM-DD/` is a guessable URL. | Susan |
| 3 | Remove the day list entirely | It is the only surface that works with no script. A no-script reader would get a heading and an apology. | Susan |

## 15 - Row #14 - Empty, missing and failed-day screens

- **Scope:** The states a reader meets on a bad day adopt the item's new surface language.
- **Files touched:**
  - `frontend/src/lib/components/EmptyDay.svelte`
  - `frontend/src/lib/components/DayNotice.svelte`
  - `frontend/src/routes/+error.svelte`
- **Acceptance gates:** `npm run check`; `npm run build`; each state rendered in both themes at 360, 801 and 1536; the day page still renders with its payload absent and with it empty.
- **Oracle:** the browser check from CLAUDE.md section 12 run against three deliberately broken inputs - a day with zero items, a day whose payload file is absent, and a day whose payload is present but unparseable - asserting a designed screen and zero console errors in each.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `EmptyDay` already carries a panel on a neutral tint. It adopts `--color-surface` and the item's radius and hairline so the quiet day and the busy day are visibly the same site. The neutral tint stays neutral - a quiet day is not a fault and colouring it like one says something untrue. | Susan |
| 2 | The failed-day state is the one a reader meets when a run broke, and it is the plainest screen on the site. A day that went wrong must not look like a site that is gone. | Susan |
| 3 | `DayNotice` absorbs the run stamp and the skipped-story reason from row 5. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave the empty state as it is | It is the screen most likely to be a reader's first impression on a bad day, and the one nobody looks at. | Susan |

## 16 - Row #15 - The day's leading stories

- **Scope:** Five leads at the top of the day, chosen across the whole day by an eligibility list and a two-term score, each carrying one true sentence saying why it is there.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/rank.py`
  - `backend/idhazh/contracts/` (the digest item model)
  - `schemas/digest-day.schema.json` (generated)
  - `frontend/src/lib/payload/types.ts` (generated)
  - `frontend/src/lib/components/LeadingStories.svelte` (new)
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/src/lib/day-shape.ts`
  - `config/appearance.json`
  - `docs/architecture/sources/discovery.md`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; `npm run check`; `npm run build`; drift gate green; `bundle-gate` records re-taken; each lead anchors to an item present on the same page; the line-coverage and omission counters recorded in the PR body.
- **Oracle:** on the 359-item fixture day the block holds **at most** `ui.leading_stories` items and never pads, no more than `ui.leading_per_desk` from one desk, at most one per `source_id`, at most one per subject, every one present in `day.items`, and every anchor resolving to an element on the page. On that fixture it holds exactly five. Below three eligible items it does not render.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Selection is by `rank_score` plus a shared-subject term, across the whole day. **Not the head of the published order** - finding 1 shows that head is the top of the AI desk from run 1. | Editor |
| 2 | **The shared-subject term**, computed at assemble over the finished day: distinct `source_id` naming the same entity **in the item's published title**, one item per source per entity, zero below a floor of `ui.lead_cluster_floor` distinct sources, and zero for a cluster holding no `reporting` item. An item takes the largest slug it earned, never the sum - the rule `lens_bonus` already follows. | Editor |
| 3 | The term's ceiling is `ui.lead_shared_subject_weight`, **pinned by a test below what one more trade-press carrier is worth (0.6)**, so a recurring subject cannot outrank a story two independent feeds carried today. **The value may not be set until somebody measures the `carried_by` distribution over a committed day** (Rule #10). | Editor, Carmack |
| 4 | **Lens overlap is refused.** Six live lenses fire on 25.6 percent of real articles, and within a desk the lens that fires is the desk's theme - so overlap restates the topic cap. Worse, `discovery.md` already pays a weight to under-carried lenses; an overlap term would pay the over-carried ones a second time in the opposite direction, breaking that page's own "one fact earns one bonus" rule. What the reader loses is nothing: the cross-desk case it would have caught is already priced by those weights. | Editor |
| 5 | **Eligibility, applied before any score.** Seven rules, each excluding regardless of rank: a `low` band item; a `truncated` item; an item whose `time_source` is not the feed; an `announcement` with no `reporting` item in its cluster; a desk already at `ui.leading_per_desk`; a `source_id` already holding a lead; and a second lead published on the previous calendar day past `ui.lead_max_yesterday`. Every excluded item still publishes, in the stream, marked. | Editor |
| 6 | **One lead per subject, and it is a fourth cap rather than a decay.** The existing three do not bound a subject: a running story crosses desks and sources, so three of five clears all of them. A subject that genuinely deserves two of five means the day has fewer than five distinct stories worth leading, and the honest answer is a shorter block. | Editor |
| 7 | **The block never pads.** Below three eligible items it does not render and the day goes straight to the stream. Four real leads beat five with one filler. | Editor |
| 8 | Five leads, at most two per desk. Both knobs (Rule #6). Two per desk matters more than it looks: 24 of the 30 watchlist entities are tech companies, so the shared-subject signal is structurally biased toward AI and business, and this cap is the only thing holding it. | Editor |
| 9 | **No rank numerals.** A number beside a story implies a score we would then owe the reader an explanation for. | Susan |
| 10 | **The why-line, one per lead, the strongest true one, never a list and never invented.** In order of preference: `Four of today's stories are about Nvidia.` / `This link is on the Hacker News front page.` / `Nvidia is on our watchlist.` / `The same report reached us through three of our feeds.` / `The lead story on our Energy desk.` | Editor |
| 11 | Recency and lens weight get **no sentence**. The rail already prints the time, and a weighted lens is an editorial subsidy for an under-carried theme - "this is here because it mentions tariffs" tells the reader about our config, not about the news. | Editor |
| 12 | Tie-breakers in order: higher `carried_by`; `high` band before `medium`; newer `published_at`; `item_id` ascending. The last is derived from the address, so it cannot be gamed and two builds of one day are identical. | Editor |
| 13 | **`rank_score` carries a recency credit computed at plan time that does not expire during the day** - an item found at 02:20 still carries the same credit at 20:00. The term ranges +0.6 at zero hours to +0.23 at the 24-hour gate, a spread of 0.37, larger than the weighted-lens bonus of 0.3. It biases the block toward early runs, which stabilises it. **Recorded as an accident, not a design**, so nobody later "fixes" it into a decay and destabilises the block. | Editor |
| 14 | **`RANK_VERSION` is wired to the run manifest in a structural commit first, then bumped in the behavioural commit that adds the term.** It is read by nothing today, so a bump would record nothing. | Fowler |
| 15 | Two counters ship with the row and are recorded: **line coverage** (the share of leads carrying a real reason rather than the desk fallback) and an **omission log** (no item above the cluster floor or with `carried_by >= 3` is absent from the block without the build log naming which cap excluded it). Given entities fire on 22.1 percent of items on a title-plus-body match, and this row matches title only, low coverage is a live risk and must be measured before the row ships. | Editor |
| 16 | The ranking arithmetic and the four guards are written into `docs/architecture/sources/discovery.md`, beside the "one fact earns one bonus" rule they obey. What the block *is* goes in `docs/concepts/digest.md`. | Fowler |
| 17 | The three-per-topic slice and topic sections as a page structure are cut. They publish 15 items and hide 344. Breadth is bought back by decision 8; the sections are replaced by the pill row, where every topic is already its own route. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | First N of the published order | Ships the accident instead of the edit. Finding 1. | Editor |
| 2 | A heat score computed in the browser | Read-time re-ranking, and a number nobody measured (Rule #10). | Carmack |
| 3 | Keep topic sections above the leads | Two competing answers to "what should I read first" on one screen. | Editor |
| 4 | `Front page at <source>.` as a why-line | **False.** The salience block holds two Hacker News feeds; `on_front_page` means a link aggregator carried the URL, not that the publisher led with it. It also fired 0 of 160 and 1 of 160 on two committed plans, and `discovery.md` already says retire the feeds below 1 percent. | Editor |
| 5 | `Three sources covered this.` as a why-line | `rank.merge` groups by canonical URL, so `carried_by` counts syndication of one address. Two outlets writing their own pieces produce two addresses and both read 1. | Editor |
| 6 | An `events`-based consequence proxy | `events` names the kind of event, never its size - a seed round and a multi-billion acquisition both read `funding`. It would make every acquisition outrank every research paper, which is a rule about grammar, not importance. Four newsroom tests have no signal here (consequence, human interest, exclusivity, continuity) and inventing a proxy for the one that makes a lead is worse than admitting the gap. | Editor |

## 17 - Row #16 - Split the item's meta line

- **Scope:** The item's facts split into an eyebrow above the title and a footer below the summary.
- **Files touched:**
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/lib/components/ItemMeta.svelte`
  - `frontend/src/lib/bands.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; `bundle-gate` records re-taken; the eyebrow holds at most four elements at every width.
- **Oracle:** a Playwright check asserting the eyebrow contains at most four child elements and that the confidence sentence, the `Listen` control and the original link all sit below the summary in DOM order on every item of the fixture day.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Above the title: the monogram, the source name, the time, the topic chip. Cap of four. Below the summary: the confidence sentence, `Listen`, and `Read the original` pinned to the trailing edge. | Susan |
| 2 | The confidence sentence stays below. It is a claim *about the summary*; printing "leaves out figures from the opening" above a headline the reader has not read is a disclaimer on nothing. | Susan |
| 3 | The topic chip is a tinted fill, not an outline, and does not become a link. An outline means you can act on it; forcing a 44px tap target into a 12px eyebrow line to duplicate the pill row two inches above is a loss, not a gain. It takes `--tint-accent` like the lens chips beside it - one tint for every member of a label family. | Susan |
| 4 | `KIND_WORTH_SAYING` widens from two kinds to four. A ministry's press release and a non-peer-reviewed preprint are both speakers with a stake, and today they arrive in the same typeface as reporting. | Editor |
| 5 | The `Added later today` divider is deleted. It names a run boundary the reader cannot use, and row 17's rail says the same thing in the reader's vocabulary. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Move the whole meta line above the title | Puts the confidence disclaimer on an unread headline and makes the eyebrow seven elements deep, so nothing lands first. | Susan |
| 2 | Print `events` or `entities` as chips on the eyebrow | `events` restates a title we wrote ourselves. An entity absent from the visible text is an unchecked factual claim, and one present in the title says nothing new. | Editor, Jony |

## 18 - Row #17 - The time rail, and copy that stays true tomorrow

- **Scope:** The day orders by feed publish time on a vertical rail, with copy that a prerendered page can keep true for the next day and forever after.
- **Files touched:**
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/src/lib/components/TimeRail.svelte` (new)
  - `frontend/src/lib/format.ts`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; `layout-overflow.spec.ts` green at 360px; drift gate green; no rendered string contains a relative time.
- **Oracle:** a check over the fixture day asserting the rendered time strings are monotonically non-increasing down the page, that no string matches a relative form, and that every item whose `time_source` is our own clock renders the `First seen` form and never a bare clock time.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The stream orders by feed publish time, newest first. The order it replaces is not a ranking - it is desk-blocked (finding 1) - so nothing editorial is lost. The rank survives in the lead block. | Editor |
| 2 | **No relative time anywhere, ever.** The page is prerendered once and read for the next 24 hours with script optionally off; `3 hours ago` baked in at 06:20 is wrong by 18:20 and wrong forever on an archived day. | Editor |
| 3 | The strings: `14:05` for the same day; `Yesterday 23:40` for the day before; `31 Aug, no time given` where the feed gave a date and no clock; `First seen 06:20` where the feed's time was absent or rejected. `Yesterday` is common, not an edge case - feed-to-arrival reaches 25.7 hours against a 24-hour age limit. | Editor |
| 4 | One line at the top of the day names the zone - `Times shown in UTC.` - not 359 repetitions of a suffix. | Editor |
| 5 | The rail draws one marker per time group, not one per item. 359 items over four groups is 355 duplicate labels, and a label repeated 90 times is texture, not information. | Susan |
| 6 | The page never prints a feed time it rejected as impossible. That is the same class of failure as an invented axis label, and `time_source` from row 4 is what makes the distinction visible. | Editor, Andre |
| 7 | The rail is a two-column grid with a hairline behind it and the time label knocking a hole in the line. It collapses to a narrower column below the small breakpoint and never scrolls sideways. | Susan |
| 8 | **The stale-or-unknown-date glyph: `clock-alert` for a rejected or absent feed time, and no glyph at all for a merely old one.** It is added to the icon manifest in this row. The reason it is only one glyph: `no time given` and `First seen 06:20` are already words on the same line, and our own rule is that an icon needing a caption is a label wearing a costume. The mark earns its place on the rejected case alone, because that is the one where the printed time comes from a different clock and a reader scanning the rail would otherwise read it as a feed time. An old story needs no mark - the date says it. | agent, under owner delegation 2026-08-31 |
| 9 | Decision 1 of this row supersedes any statement that "the rank survives in the lead block" unqualified. The lead order is `rank_score` plus the shared-subject term subject to four caps, not `rank_score` order. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Our own pipeline arrival time on the rail | Puts our run schedule into the news timeline. A reader wants to know when the news happened. | owner |
| 2 | Keep payload order and use time only as a label | A rail whose numbers jump up and down as the reader scrolls, which trains them to stop reading it. | Editor |
| 3 | Relative time rewritten by script | Two clocks on one page and a wrong one for every reader with script off. A device may add a relative form beside a correct absolute string; it may never replace it. | Editor |

## 19 - Row #18 - Spend the width: the four-zone column model

- **Scope:** The item's rail breakpoint drops, and the recovered width gets a job at each of the three committed breakpoints.
- **Files touched:**
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/src/styles/app.css`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; `layout-overflow.spec.ts` green; a recorded measurement of the rendered `.measure` width against the frame width at 1280px, taken before the layout is chosen.
- **Oracle:** at each of the three committed breakpoints the item's `grid-template-columns` matches the zone model exactly, and at every width the prose element's width is at or below `--measure` while the frame's used width is at or above 90 percent of the available content box. The same assertions repeated with the root font size raised - every zone moves with it, which is what proves no zone is a pixel count.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four zones, every width relative: the time rail at `4.5rem` to `5.5rem` from the small breakpoint; the card taking `minmax(0, 1fr)` of what remains, with its text children holding the measure in `ch`; a `20rem` to `24rem` visual column from the middle breakpoint, present only when the item has a chart; and a `18rem` sticky right column from the wide breakpoint holding the leading stories and the pills. **No zone is a pixel count** (row 1, decision 4) - the rail and the visual column scale with the reader's font size, and the card is a share of what is left. | Susan |
| 2 | The measure stays on the text and never on the shell. A wide card holding a 68-character paragraph is not wasted space; a wide paragraph is a broken measure. | Susan |
| 3 | The side-rail breakpoint moves from 1024 to 640, so the meta stops interrupting the read at laptop widths. | Susan |
| 4 | **Measure before deciding.** At an 801px window the frame is 789px and the item 725px - 91.9 percent - so the reading page does not waste the screen there. The open gap is between the measure and the 1216px content box at 1536px, and it is unmeasured. Take that number first and record it with hardware and date (Rule #10). | Susan |
| 5 | `digest.visual_side` already exists in config and nothing reads it as a column. This row is what makes it a knob rather than a decoration. | Fowler |
| 6 | A chart draws in CSS pixels at the width it occupies, so the card's content width becomes an input to the build-time render spec. Never crop a chart. | Susan |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Widen the measure | A wide paragraph is where a skim turns into work. The whole reason the measure exists. | Susan |
| 2 | Raise `--frame-reading` past 1280px | The frame is not the constraint. The constraint is that nothing stands beside the prose. | Susan |
| 3 | Cite 624px or 40.6 percent as the current state | Both are dead. 624px was a stale local bundle carrying a layout cap that is gone; 40.6 percent was measured on 2026-08-28 before it was removed. They are the reason the sufficiency gate exists, not a current finding. | Susan |

### What the measurement changed, 2026-09-02

Decision 4 was taken first and it moved three of the other five. The four
numbers, at a 1536px viewport on the built committed digest: the frame's content
box **1,216px**, the frame's used width **1,280px**, the item's used width
**1,216px**, the summary's used width **659.81px**. So the item wasted nothing
of the page and the card wasted **230.19px of itself**, beside the prose, on
every story. Method, hardware and the after-numbers:
[`docs/reference/measurements.md`](../docs/reference/measurements.md#what-the-reading-page-does-with-a-wide-screen-2026-09-02).

- **Zone 4 shipped and paid for the row.** The day is a stream with an `18rem`
  sticky aside from the wide breakpoint, carrying the leading stories. Empty
  width beside the summary falls 230.19 -> 146.19px, and the leads stop taking
  the whole first screen.
- **Zone 4 does not carry the pills.** Row 7's filter panel is already sticky
  and already one band, and a sticky control that is not one band is refused by
  [`docs/concepts/design-system.md`](../docs/concepts/design-system.md). At the
  896px a two-column split leaves, its pills wrap under its field. So the day's
  controls span both columns and the aside starts level with the stream. The
  control was moved nowhere and duplicated nowhere.
- **Zone 3 - the visual column - is refused, and the arithmetic is why.** The
  committed charts are 825 x 437px SVGs with 25 labels at 10px. Across the card
  body they draw at 10.8 CSS px; in a 20rem column at **3.9**. And the column
  does not fit: with the aside taking the one trailing slot the frame can spare,
  a 20rem column beside the measure would leave 130px. Decision 6's own sentence
  is the condition - the render spec has to take the column width first - so
  `digest.visual_side` stays unread and decision 5 is not met. What the figure
  did give back is 85px of empty letterbox per visual, and only 5.4 percent of
  items carry one (249 of 4,598 over twelve days).
- **Decision 3 is refused.** A 14rem rail from the small breakpoint leaves the
  summary **262.8px at 640 and 411px at 801** - 26 and 42 characters against a
  68-character measure, and against a contract floor of 52. And its reason was
  already gone: row 16 took the deciding facts above the title on 2026-09-01, so
  nothing interrupts the read at any width.
- **Zone 1 is at every width, not from the small breakpoint.** Row 12 put the
  read state on the monogram and ruled it must stay beside the title it
  qualifies at every width. Not undone.
- **The time rail is not placed.** Row 17 has not shipped and
  `TimeRail.svelte` does not exist, so zone 1 of decision 1 has nothing to
  place. The zone model leaves room for it and names its token.

## 20 - Row #19 - Key points on long items only

- **Scope:** An item's key points render where the summary is long enough that one paragraph cannot carry the decision.
- **Files touched:**
  - `frontend/src/lib/components/DigestItem.svelte`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; `bundle-gate` records re-taken; a sampled restatement count recorded in the PR body.
- **Oracle:** on the fixture day, key points render on every item above the length threshold and on no item below it, and the item's resting height is unchanged for items below it.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The threshold is the summary's own length band. On a 30-to-45-word brief the points restate the summary and the standing refusal holds. On a 3,000-word article compressed to 200 words they are the only place a reader learns there are three more things in the piece. | Editor |
| 2 | They sit below the confidence sentence and outside the item's resting height, at two to five lines of one clause each. | Editor |
| 3 | **The row starts with a measurement.** Sample twenty items from the top two summary bands and count how many key points restate a clause already in the summary. If most do, the refusal was right at every length and this row COLLAPSES with that count cited. | Editor |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Key points on every item | The same content twice at half the items per screen, which is the case the standing refusal tested. | Jony |
| 2 | Key points instead of the summary | The summary is the product. The points add; they do not replace. | Editor |

## 21 - Row #20 - The full-day browser smoke

- **Scope:** The rebuilt surface is verified against a real 359-item day rather than a small fixture.
- **Files touched:**
  - `frontend/tests/reading-page.spec.ts` (new)
  - `frontend/bundle-baseline.json`
- **Acceptance gates:** every reader route at 360, 801 and 1536 CSS px in both themes; zero new console `[error]` events; zero 404s; `layout-overflow.spec.ts` green; every route's byte record re-taken and committed.
- **Oracle:** the full day renders with zero console errors and zero failed requests at six viewport-and-theme combinations, and the same page renders a designed screen with its payload absent, empty and unparseable.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The smoke runs against a 359-item day. A rail and a card that read well at twelve items and become a wall at 359 is the failure this page has already had once. | Susan |
| 2 | Both themes, because dark is now the default and is what most readers see. | Susan |
| 3 | A degraded arm that reports zero intercepted or aborted requests is a null result, not a pass. The arm prints its count and fails at zero. | Carmack |
| 4 | Every route's byte record is re-taken in this row, after all copy is final. A copy edit moves a route's first-load bytes, so measuring before the strings settle costs a rebuild per word. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Smoke each row's own change only | The failure mode is the composition - twenty rows each correct in isolation producing a page nobody checked whole. | Fowler |

## 22 - Row #21 - Extract the payload projector into one module

- **Scope:** The field list that projects a day payload for serving moves out of a build script into one module both the staging step and the build-time reader import. Structural only; no reader sees a change.
- **Files touched:**
  - `frontend/scripts/copy-visuals.mjs`
  - `frontend/src/lib/payload/project.ts` (new)
  - `frontend/src/lib/server/payload.ts`
  - `frontend/tests/staged-day.spec.ts`
- **Acceptance gates:** `npm run check`; `npm run build`; every staged file byte-identical to what the previous build produced.
- **Oracle:** the staged output of the new module diffs byte-identical against the committed staged tree for all ten published days. A structural change that moves a byte is not a structural change.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One allow-list in one place. Today it is a JavaScript array of thirteen field names in a build script, with a hand-copied duplicate in the spec that tests it - `layout.md` already admits the list "can drift". | Fowler |
| 2 | Structural hat only. No field added, none removed, no behaviour changed. Row 22 does that. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Widen the list in the same commit | Two hats in one PR: a no-op refactor and a contract change. A regression could not be attributed. | Fowler |

## 23 - Row #22 - The served day becomes a versioned contract

- **Scope:** The projected day payload becomes a Pydantic contract with a generated schema, widened to the fields the reading page renders.
- **Files touched:**
  - `backend/idhazh/contracts/digest_view.py` (new)
  - `schemas/digest-view.schema.json` (generated)
  - `frontend/src/lib/payload/project.ts`
  - `frontend/src/lib/payload/types.ts` (generated)
  - `frontend/scripts/copy-visuals.mjs`
  - `frontend/bundle-baseline.json`
  - `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; every committed day projects and validates; the new per-item byte rate and the re-derived site cap date recorded.
- **Oracle:** a test opens all ten committed days through the client-side reader and asserts an absent optional field reads as unknown, never as a default that means something, and that an unknown extra field does not throw.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This is the irreversible step of the migration, not the route switch.** Deleting prerendered documents is reversible by rebuilding. Publishing a payload shape a browser we do not control now depends on is not - a reader's cached shell can be older than the payload it fetches, and `<base>/digest/<Y>/<M>/<D>/digest.json` becomes a public address that cannot move. | Fowler |
| 2 | Three things must be true before it merges: the shape carries a `version` and a `changelog` entry with the read-side migration path written; the shell renders when an expected field is absent and when an unknown field is present; and the ten-day migration test above passes. | Fowler |
| 3 | **One file per day.** Not per day-and-topic - a topic route is a free filter over a day already in hand, and `layout.md` already rejected per-vertical files. Not paged and not chunked: the shell cannot scroll to `#ai-4821903756` until it knows which page holds it, and a deep link is a canonical reader address. | Fowler |
| 4 | `embeddings` stays dropped from the projection. It was 40.0 percent of the day payload and no browser opens it. | Fowler |
| 5 | From here on, a breaking change to this shape needs the read-side migration **in the shell**, not only in the build. Section 11 now has a consumer we cannot upgrade atomically. | Fowler |
| 6 | The site-size runway is re-measured and recorded in this commit. The saving is not a saving until it is measured (Rule #10). | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Serve `DigestDay` whole and delete the projection | Cheaper to build and 56.7 percent more bytes on the wire, measured in `layout.md`. Bytes are what this migration is for. | Carmack |
| 2 | Leave the field list a JavaScript array | Rule #3: a persisted shape a reader's browser parses is a contract before logic reads it. | Fowler |

## 24 - Row #23 - Split a reading route's load into facts and items

- **Scope:** Each reading route's `load` splits into the day's bounded facts plus a seed of items, and the full item list. Both still read at build time. This is the seam everything after it uses.
- **Files touched:**
  - `frontend/src/routes/[date]/+page.server.ts`
  - `frontend/src/routes/[date]/[vertical]/+page.server.ts`
  - `frontend/src/routes/+page.server.ts`
  - `frontend/src/lib/server/payload.ts`
  - `config/appearance.json`
- **Acceptance gates:** `npm run check`; `npm run build`; **prerendered output byte-identical to the previous build on every route.**
- **Oracle:** byte-identical prerendered documents. A seam that changes output is not a seam.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `ui.shell_seed_items` is a new knob (Rule #6). Derived from the owner's 2026-08-31 figures at 490 gzipped bytes an item, a ten-item seed is roughly 4.9 KB gzipped a document - **an estimate, measured in the commit that lands it.** | Fowler, Carmack |
| 2 | Structural hat. Nothing fetches yet. | Fowler |

## 25 - Row #24 - The anchor and the unreachable state

- **Scope:** The client loader, the fragment restoration, and the fifth page state - the payload exists and the fetch failed.
- **Files touched:**
  - `frontend/src/lib/assist/day.ts`
  - `frontend/src/lib/components/PayloadState.svelte` (new)
  - `frontend/src/routes/+layout.svelte`
  - `config/appearance.json`
  - `frontend/tests/payload-state.spec.ts` (new)
- **Acceptance gates:** `npm run check`; `npm run build`; the state rendered in both themes; a blocked-request arm that prints its intercept count and fails at zero.
- **Oracle:** with the day payload blocked at the network layer, the page shows the seed, names what could not be read, offers a retry, and logs zero uncaught errors. With it slow, one sentence appears past the threshold. With a fragment in the URL, the element is scrolled to and focused after the payload renders.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Unreachable is its own state with its own sentence.** Missing means never published; Unreachable means the fetch failed. Telling a reader a day was never published when their train went into a tunnel is a lie they can check. | Fowler |
| 2 | **No spinner, no skeleton, no progress bar.** The first frame is already readable, so there is nothing to fill. Past `ui.payload_slow_ms` one sentence says the rest is still loading - a sentence, never a dot. | Fowler, Susan |
| 3 | Bytes-as-type was weighed and refused here. It is right for the 43 MB encoder because that cost is worth naming before a click and the library reports a real count. A compressed response reports compressed length, so a byte readout on a day payload would print precision the data does not have - which the design system already calls a bar making it up. | Fowler |
| 4 | Nothing greys out while the fetch runs, and the seed stays on screen through every failure. A failure offers a retry. | Susan |
| 5 | Every fetch URL is absolute from `base`, never relative. `trailingSlash: 'always'` makes a relative fetch resolve differently per route, and a path built without `base` works in dev and 404s under the Pages project path. A test asserts it. | Fowler |

## 26 - Row #25 - The topic routes fetch their day

- **Scope:** `/[date]/[vertical]/` stops inlining its item list and fetches the day, filtering client-side.
- **Files touched:**
  - `frontend/src/routes/[date]/[vertical]/+page.svelte`
  - `frontend/src/routes/[date]/[vertical]/+page.server.ts`
  - `frontend/bundle-baseline.json`
- **Acceptance gates:** `npm run check`; `npm run build`; section 12 browser smoke on a topic route; byte records re-taken; `layout-overflow.spec.ts` green.
- **Oracle:** the prerendered topic document carries at most `ui.shell_seed_items` item markers, and the rendered page after hydration holds the same item set the previous build inlined - a set comparison, not a count.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The topic routes move first.** Five of the six documents a day, every one a duplicate of the day route filtered, and no anchor points at a topic route. If it goes wrong the reader still has the day page. | Fowler |
| 2 | `prerender` stays `true` and `entries()` stays. What moves is the item list, not the document. | Fowler |

## 27 - Row #26 - The day route fetches its day

- **Scope:** `/[date]/` stops inlining its item list.
- **Files touched:**
  - `frontend/src/routes/[date]/+page.svelte`
  - `frontend/src/routes/[date]/+page.server.ts`
  - `frontend/bundle-baseline.json`
- **Acceptance gates:** `npm run check`; `npm run build`; section 12 smoke including a deep link to an item anchor; byte records re-taken; the site-size runway re-recorded.
- **Oracle:** as row 25, plus a deep link to an item id that sits below the seed resolves, scrolls and focuses.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`/` stays prerendered forever with the whole day inline, and this is not an oversight.** It is one document per build and does not grow per published day, so it contributes nothing to the cap problem. It is the address a stranger meets first, and it leaves one complete, crawlable, script-free digest on the site. | Fowler |
| 2 | `/404`, `/archive/`, `/evals/` and the console are unchanged. | Fowler |

## 28 - Row #27 - Invert the guards and correct every doc

- **Scope:** The guards that prerendering made free are replaced, and every sentence the migration made false is corrected.
- **Files touched:**
  - `frontend/tests/payload-weight.spec.ts`
  - `.github/workflows/` (a payload validation step)
  - `frontend/svelte.config.js`, `frontend/prerender-guard.js`, `frontend/src/lib/server/payload.ts` (comments)
  - `docs/concepts/ui-shell.md`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/layout.md`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `pytest`; `npm run check`; `npm run build`; the new CI validation step green; zero remaining sentences claiming the reading path makes no runtime request.
- **Oracle:** a deliberately malformed committed day fails the new CI step, and the shell renders a designed state for it rather than a white screen. Both arms, in one test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The build no longer proves every committed day renders.** Prerendering gave that free. A CI step validates every committed day against the generated schema, and the client loader validates at the boundary. The guarantee weakens from "cannot be built" to "cannot be merged" - stated, not hidden. | Fowler |
| 2 | `payload-weight.spec.ts` inverts: a reading route carries **at most** the seed count of item markers. Left alone it becomes trivially true and stops guarding, which `layout.md` records as a failure shape this repo has had twice. | Fowler |
| 3 | The `<details>` rule survives and its reason is rewritten. It is right because it is keyboard-reachable for free and states its own state without a second label. The script-less argument still holds unchanged on `/`, `/archive/`, `/404` and `/evals/` - the amended text says which. | Susan |
| 4 | The content-security header is unaffected and becomes **more** load-bearing: it is emitted per rendered document, a shell is a rendered document, and `connect-src 'self'` bounds every fetch at the browser rather than in our own code. The comment says so. | Fowler |
| 5 | Fowler supplied exact old-to-new text for every affected sentence across four docs and three code comments. It is the largest block of work in this row and the one with no gate behind it, so it is enumerated in the PR body before any of it is written. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Correct the docs at plan closure instead of here | Rule #4: a doc that disagrees with what shipped is a trap for the next agent, and the correction lands in the same commit. | Fowler |

## 29 - Row #28 - The site becomes a progressive web app

- **Scope:** A service worker with a kill-switch, so a reader who has opened a day can read it again with no network, and an installed window is a real offline reader rather than a bookmark.
- **Files touched:**
  - `frontend/src/service-worker.ts` (new)
  - `frontend/static/manifest.webmanifest`
  - `frontend/src/lib/components/PayloadState.svelte`
  - `frontend/src/app.html`
  - `config/appearance.json`
  - `frontend/tests/manifest.spec.ts`
  - `frontend/tests/service-worker.spec.ts` (new)
  - `docs/concepts/ui-shell.md`
- **Acceptance gates:** `npm run check`; `npm run build`; `bundle-gate` records re-taken; `manifest.spec.ts` green with its existing grep intact; the kill-switch exercised in a test; an offline arm that prints its intercept count and fails at zero.
- **Oracle:** a browser opens a day, goes offline, reloads, and reads the same day. Then the kill-switch is published, the browser reloads once, and the worker unregisters itself and clears its caches - asserted by a second reload fetching from the network. Both arms in one spec, because a worker with no proven exit is the failure this row exists to avoid.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The worker ships with its kill-switch designed first, not added later.** `ui-shell.md` already set this condition: a worker is the only code this site ships that outlives the tab, and a stale worker serving a stale bundle is the hardest bug class available to a static site. The switch is a committed file the worker checks on every activation; when it names a version at or above the worker's own, the worker unregisters and clears every cache it owns. | Fowler, owner |
| 2 | **This row is only buildable after row 26.** Before the migration a day was inside its document, so a worker would have cached HTML and gained a reader nothing an ordinary browser cache does not already give. After it, the day is a separate addressable file and offline reading becomes a real feature. | Fowler |
| 3 | **Cache what a reader has already opened, and nothing else.** The shell and its assets on install; a day payload only after that day has been fetched once. No prefetch of days a reader never asked for - that spends a stranger's data on a guess. | Susan, Carmack |
| 4 | **The shell is network-first, the day payloads are cache-first.** A published day never changes after its last run, so serving it from disk is correct. The shell does change, so a stale one is the bug in decision 1. | Fowler |
| 5 | **No push, no notification, no background sync.** `manifest.spec.ts` already greps the source for `Notification` and `PushManager` and fails on either name; the grep widens to the worker file in this commit. The reader decides when to read (CLAUDE.md section 0a). | owner |
| 6 | The offline state is a sentence with a retry, reusing the Unreachable component from row 24 rather than inventing a second one. A reader offline on a day they never opened is told which day could not be read and offered the days they have. | Susan |
| 7 | `ui-shell.md` says "There is no service worker, and that is a separate decision rather than an oversight". That paragraph is rewritten in this commit with the decision, the kill-switch design and the reason the migration changed the answer (Rule #4). | Fowler |
| 8 | Rule #1 is unaffected. A worker runs on the reader's own device over files we already serve; nothing executes off their device and nothing reports their behaviour anywhere. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A worker with no kill-switch | The one failure mode a static site cannot recover from: a reader pinned to a broken bundle with no way to reach the fix. `ui-shell.md` named this condition before the row existed. | Fowler |
| 2 | Precache every published day on install | It spends a stranger's data on days they may never open, and it grows without bound as the archive grows. | Carmack |
| 3 | Ship the worker before row 26 | It would cache prerendered documents, which the browser cache already handles, and gain the reader nothing. | Fowler |
| 4 | Background sync so a day is ready before the reader arrives | Work on the reader's device that they did not ask for, on a schedule we chose. It is the same instinct push notifications come from. | owner |

## 30 - Row #29 - Measure the gap between our own mentions

- **Scope:** For every name in the registry, the number of distinct published days it appears on and the median gap in days between consecutive appearances, over the whole committed record.
- **Files touched:**
  - `backend/utilities/entity_gap.py` (new)
  - `docs/reference/measurements.md`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; the result recorded with hardware, date and the record it was taken over (Rule #10).
- **Oracle:** the utility run twice over the same committed tree produces identical output. It reads committed payloads only and touches no network.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is the exact number a half-life is a judgement about, and **no half-life may be set before it exists.** A half-life shorter than a subject's own observed median gap is dead before the next instalment arrives, so it does nothing. | Editor |
| 2 | **It is also the baseline for the future model-based entity recognition.** A model that finds more entities but splits one subject across three names - "the export controls", "chip export curbs", "the export ban" - improves coverage and makes continuity worse. A coverage-only baseline would score that a win; this one will not. | Editor |
| 3 | The result gates rows 30 to 33. Most entries covered near-daily means the credit does nothing, and those rows COLLAPSE with the number cited rather than shipping an inert knob. ESCALATE trigger (h). | Editor |
| 4 | It costs no contract, no model and no runtime, so it dispatches in the first wave alongside the frontend rows. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Set the half-lives from the three anchors and measure later | "A pandemic stays hot for two to three years" is an estimate, and an estimate may not justify a design (Rule #10). This repo has a measured price for guessing a matching rule: one unstated choice in the lens matcher moved coverage from 8.8 percent to 88.2 percent of items, and a filter that takes 88 of every 100 items is not a filter. | Editor |

## 31 - Row #30 - The registry holds a subject, not only an organisation

- **Scope:** `EntityDef` widens to hold a subject that is not a named organisation, so a pandemic or a tournament can enter the vocabulary at all.
- **Files touched:**
  - `backend/idhazh/contracts/watchlist.py`
  - `schemas/watchlist.schema.json` (generated)
  - `config/watchlist.json`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; the committed watchlist re-validates unchanged.
- **Oracle:** the existing 30 entries validate byte-identically against the widened contract, and one fixture subject with no `cik` and no `feeds` validates.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Widen the existing registry; do not open a second one.** `EntityDef` already has the right shape - an id, a display name, curated aliases, a lifecycle - and `cik` and `feeds` are already optional, which a pandemic has neither of. A second enumeration is two lists to keep in step and a typo in one is silent, which `determinism.md` already rejected for this exact reason. | Fowler |
| 2 | The docstring changes from "one named organisation". The change is a docstring and a changelog entry, not a new model. | Fowler |
| 3 | A standing organisation and a subject are different kinds of entry and the contract says so. A company never goes quiet, so its gap is near zero and a half-life never bites. | Editor |

## 32 - Row #31 - The entity-heat ledger

- **Scope:** A derived projection of the committed day payloads, rebuilt by assemble, holding one row per subject per day.
- **Files touched:**
  - `backend/idhazh/contracts/entity_heat.py` (new)
  - `schemas/entity-heat-row.schema.json` (generated)
  - `backend/idhazh/assemble.py`
  - `state/entity-heat/`
  - `docs/architecture/publishing/layout.md`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; the header check through `require_matching_header`; the per-row byte size measured and recorded, not estimated.
- **Oracle:** deleting a month's file and rebuilding regenerates it byte-identically from the committed day payloads. The rebuild is the repair, and that property is the reason this shape was chosen.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A derived projection, not an accumulator.** A running heat value rewritten each day is a read-modify-write two runs of one day race on, it makes the answer a function of how often the job ran, and a half-life change cannot be re-derived because the history it would need is gone. | Fowler |
| 2 | Rebuilt by assemble, which is the only stage besides collect that sees the whole assembled day - so the distinct-source count is exact rather than a fold over run-level counts. Same shape as the month search index, which is the proven pattern here. | Fowler |
| 3 | Row shape: `date`, `entity_id`, `distinct_sources`, `announcement_only`. The last is **recorded and not applied** - "three sources carried it and all three were announcements" and "nobody carried it" are different facts, and one field must not mean both. | Fowler |
| 4 | **The floor is not baked into the ledger.** The row records what was observed, including counts below the floor; the floor is a knob the read applies (Rule #6). A threshold compiled into a ledger cannot be changed without losing history. | Fowler |
| 5 | **No retention.** It is derived, so a deleted month regenerates. What is bounded is the read - the longest configured half-life times `entity_decay_window_multiple`. | Fowler |
| 6 | Because it is derived, a breaking change needs a rebuild rather than a read-side migration. That is the cheap property this shape buys and the contract says so. | Fowler |
| 7 | `layout.md` already says "every writer of a committed day payload owes its month a rebuild" and names three writers. This makes four. The sentence is corrected in this commit. | Fowler |
| 8 | **Why the file exists at all:** without it the plan job opens every committed day in the decay window to compute heat - 866 KB a day over a multi-year window for a slow subject, read on the hot path and growing forever. | Fowler |

## 33 - Row #32 - Half-lives as config, with a fuse and a lifecycle

- **Scope:** An optional `half_life_days` on a registry entry, a default and three knobs in the app config, and the validation that stops the list becoming untouchable.
- **Files touched:**
  - `backend/idhazh/contracts/watchlist.py`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/watchlist.schema.json`, `schemas/app-config.schema.json` (generated)
  - `config/watchlist.json`, `config/idhazh.json`
  - `docs/concepts/config.md`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; drift gate green; a fresh clone runs on the defaults.
- **Oracle:** a retired entry carrying a non-default half-life fails validation; a half-life outside the fuse fails validation; an entry with no half-life resolves to the default. Three assertions, one spec.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The half-life is a field on the entry that already owns the id. No second registry. | Fowler |
| 2 | **Days, not hours,** and this is a trap worth naming. `collect.recency_half_life_hours` already exists at a different grain - it orders items inside a day from the feed's clock. The observation grain here is the digest date, and an hourly half-life over a daily observation prints precision the data does not have. `discovery.md` says which is which in one sentence. | Fowler |
| 3 | Three tiers, because three anchors were given and a fourth is not supported: **running condition** (no end date, produces coverage for years), **season** (fixed start and end with a calendar between), **one-off** (happens once and is done). A standing organisation is not a tier - its gap is always near zero. | Editor |
| 4 | **The default is the shortest tier.** Too long fails invisibly - a dead subject quietly holds slots and the reader cannot see what it displaced. Too short fails visibly - a running story drops out and it is right there on the page. Bias to the failure a person can see. | Editor |
| 5 | The method a person applies, in order: does the subject have a scheduled next instalment; what is the median gap in our own published record (row 29); does it resolve or persist. Not "how important is it". | Editor |
| 6 | Four guards against a hand-tuned list nobody dares change: a fuse of `gt=0, le=1461` on the half-life; the registry cap of 30 entries; **`retired_on` as how a raised half-life ends** - a tournament finishes, and the entry becomes retired with a date rather than live and untouched; and a validator refusing a non-default half-life on a retired entry. | Fowler |
| 7 | **Absent means the default here**, and that is deliberately the opposite of row 2's rule for stored reader state, where absence must never mean the default. One line says why, or the two read as contradicting each other. | Fowler |
| 8 | **The honest admission: no test can rule that 2.5 years is right for a pandemic.** What is mechanical is that every non-default rate names an active subject and that an unclassified subject gets the default. The trigger to write down: **when a second subject takes a non-default rate, the console gains a per-subject readout.** Not this plan's scope, but a trigger nobody wrote down is a feature nobody ships. | Fowler, Editor |

## 34 - Row #33 - The decayed-heat term, shipping at zero weight

- **Scope:** `plan_vertical` reads the heat ledger over a bounded window and adds a decayed credit, at a default weight of zero.
- **Files touched:**
  - `backend/idhazh/rank.py`
  - `backend/idhazh/cli.py`
  - `config/idhazh.json`
  - `docs/architecture/sources/discovery.md`
  - `backend/tests/`
- **Acceptance gates:** `ruff`; `mypy --strict`; `pytest`; a replay of a committed day producing a byte-identical plan at zero weight; `rank_version` present on the run manifest and bumped.
- **Oracle:** at `entity_decay_weight` 0.0 the replayed plan for every committed day is byte-identical to what shipped. At a non-zero weight, the same replay run twice is identical to itself. Determinism is the check, because a stateful ranker is where it goes.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The read window is `[day - window, day)` and never includes the day being ranked.** Today's counts must not feed today's rank, or run 2 ranks differently from run 1 because run 1 published. This is the load-bearing guard of the whole feature. | Fowler |
| 2 | **The credit adds and never subtracts.** It may lift an item that already earned its place; it may never carry a routine item into a slot on its own, and it may never penalise a subject still producing coverage. A pandemic's 400th routine case count is not a lead. | Editor |
| 3 | **It ships at zero weight.** The mechanism and the switch land in different PRs, because a bonus that starts firing reorders every future day - which is why `watchlist_bonus` going live was an owner decision. Turning it on is the owner's, with a number row 29 supports. | Editor, Fowler |
| 4 | `entity_decay_weight` plus `watchlist_bonus` is pinned by a test below what one more trade-press carrier is worth (0.6), the same relation `discovery.md` already sets for lens weights. A stale subject must not outrank a story two independent feeds carried today. | Editor |
| 5 | **Not a `pipeline_fingerprint` input.** The fingerprint answers "which summarizer configuration". The decay does not change a summary, exactly as a tag does not - `tag.py` set that precedent. The exclusion is written next to the tagger's so nobody re-derives it. | Fowler |
| 6 | **Replay of an old day is exact only while the day payloads exist.** A retention policy that ever deleted a day payload would silently change every later day's rank. `layout.md` today promises text is never deleted; the coupling is written into its retention section before that could change. | Fowler |
| 7 | A hostile page can win heat for a subject we already track and can never invent one - the id is a closed-registry member, the same property `tag.py` has (Rule #11). It can inflate a count through syndication, and the guard is the no-score-for-an-all-announcement-cluster rule from row 15, carried by `source_kind`. | Fowler, Andre |
| 8 | **It reports nothing at first, and that is not a defect.** No committed day carries a heat row and `entities` was empty on every item until 2026-08-26, so the ten committed days seed almost nothing. Say so, the way `discovery.md` said it for the retrieval eval's query tier. | Fowler |
| 9 | **The seam Fowler asked for, kept as three rules even though the plans merged.** The credit may not publish a field on `DigestItem`; the ledger rebuild reads `frontend/public/digest/` and never the staged projection, so rows 22 and 23 narrowing or widening the served field list cannot change a rank; and this row touches no file rows 21 to 28 touch. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship the term at a live weight | Two live ranking changes in one merge window cannot be attributed, and row 15 is already changing the published order. | Editor |
| 2 | Let the credit decide a lead slot | It cannot print the line that decided it - that needs cross-day subject identity no contract here supplies - and a lead must state the reason that actually decided it. A true sentence that is not the reason is not a why-line. | Editor |
| 3 | Bump `RANK_VERSION` and call that the guard | Nothing reads it. It is wired to the run manifest first, in row 15. | Fowler |

### The checks a person runs once the credit is live

| Check | What it answers | Needs a person? |
| --- | --- | --- |
| The gap check (row 29, re-run) | Is this half-life supported by our own coverage at all? A value far above the observed gap is unsupported. | No |
| The displacement check - for every item the credit lifted, name what it displaced, and read both | Is this half-life too long? | Yes, and that is the point |
| The drop-out check - a subject that ranked on day N produced an item on day N+k that did not, with k inside its half-life | Is this half-life too short? | No |

A monthly pass runs the gap check over every long-tier subject and a displacement check on whatever it flags. The default tier needs no calendar review, because a one-off subject expires before a review could reach it.

## What this migration costs, recorded rather than implied

The owner decided this on iteration cost and was right on the bytes too - measured 2026-08-31, six documents a day at 3.67 MB against 0.36 MB for the payload that replaces them. What is given up, and is not coming back:

| Lost | Detail |
| --- | --- |
| The script-less reader, below the seed | They keep `/` whole and the seed on every dated page. Every story below it is gone for them, permanently. |
| Crawler reach on dated pages | A crawler that does not render loses everything below the seed. Search reach on the archive falls, and re-prerendering later does not restore an index quickly. |
| The build proving every day renders | Replaced by a CI step, which can be skipped in a way a build cannot. |
| The instant anchor | A deep link scrolls after a fetch instead of immediately. |
| One failure mode becomes two | The site gains a failure only a reader can observe. Section 12's smoke covers a blocked request; it cannot cover a reader's actual network. |

## Docs to update at closure

| Doc | What changes |
| --- | --- |
| [docs/concepts/design-system.md](../docs/concepts/design-system.md) | The card and its hover state; the transition-is-not-an-animation clause; the reduced-motion transform rule; the fill-versus-brightness ruling on the read mark; the clarification that the not-beside-a-headline rule bans an invented mark, not an identifying one; the wordmark tokens; the dark-first default; the spinner sentence and the `<details>` reason, per row 27; **the relative-units rule and its two carve-outs, per row 1**. |
| [docs/concepts/ui-shell.md](../docs/concepts/ui-shell.md) | Four states become five - Unreachable is its own state. The spinner bullet and its rejected-alternatives row. A `## Design rationale` entry for the migration. **The "there is no service worker" paragraph is rewritten with the decision, the kill-switch design, and why the migration changed the answer** (row 28). The row refusing client-side search is stale as written and is corrected in row 7's commit; the row refusing pipeline health on the reading page still binds and stays. |
| [docs/concepts/digest.md](../docs/concepts/digest.md) | The lead block, its eligibility list and its why-lines; the time rail and the freshness copy; key points on long items; the duplicate-cluster line and the single-source line. |
| [docs/architecture/publishing/layout.md](../docs/architecture/publishing/layout.md) | The two-request budget is now spent, not headroom. The served projection is a contract, not a hand-kept array. The three refused shard shapes and the anchor argument. The 2026-08-27 follow-up about dated route trees deciding the cap date is **resolved** here, with the re-measured rate and date. |
| [docs/architecture/publishing/frontend.md](../docs/architecture/publishing/frontend.md) | "Everything is prerendered" becomes "every document is prerendered; a dated page's stories are not". The zero-runtime-requests bullet, the no-loading-state bullet, the fails-the-build bullet, and the state table. |
| [docs/architecture/sources/discovery.md](../docs/architecture/sources/discovery.md) | The shared-subject term, its four guards and its ceiling, beside the "one fact earns one bonus" rule. The recency-credit accident from row 15 decision 13. The decayed subject credit, its read window, and the sentence distinguishing the two decays now in the config - one per hour over a day's items, one per day over a subject's history. |
| [docs/architecture/publishing/layout.md](../docs/architecture/publishing/layout.md) | The two-request budget is now spent, not headroom. The served projection is a contract, not a hand-kept array. The three refused shard shapes and the anchor argument. The 2026-08-27 follow-up about dated route trees deciding the cap date is **resolved** here, with the re-measured rate and date. The "every writer of a committed day payload owes its month a rebuild" sentence gains a fourth writer. The retention section gains the coupling: deleting a day payload would silently change every later day's rank. |
| [docs/architecture/contracts/schemas.md](../docs/architecture/contracts/schemas.md) | The five new item fields, the three new vertical fields, `digest-view`, `entity-heat-row`, and the widened `EntityDef`. |
| [docs/concepts/config.md](../docs/concepts/config.md) | `topic_pills_max`, `archive_recent_days`, `leading_stories`, `leading_per_desk`, `lead_cluster_floor`, `lead_shared_subject_weight`, `lead_max_yesterday`, `shell_seed_items`, `payload_slow_ms`, the cluster threshold, the per-day source share, `half_life_days`, `entity_decay_half_life_days`, `entity_decay_min_sources`, `entity_decay_window_multiple` and `entity_decay_weight`. |
| [docs/reference/measurements.md](../docs/reference/measurements.md) | Row 29's gap measurement, with hardware, date and the record it was taken over. |
