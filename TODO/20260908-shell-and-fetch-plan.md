# Shell And Fetch - one document, every panel fetched, nothing that grows with the archive

**Last Updated**: 2026-09-08
**Level**: 5 (core design, a persisted contract, and the trust boundary). Design consultation is
complete and its rulings are in section 3; no row re-opens one.

**Claims**: the `Build Reuse` package of the decision board in
[`20260906-data-growth-research.md`](20260906-data-growth-research.md), plus the shell migration
the owner directed on 2026-09-08. Supersedes the untracked `20260908-build-reuse-plan.md` draft,
whose ten rows are folded in here as rows 12 to 17.

Execute per [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): orchestrator
dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity;
AUTO-merge on green gates; parallel N = 2 within a group; honour the ESCALATE triggers in
section 1.

---

## 0. The one sentence

**The site becomes a shell. Every page is the same document, and everything a reader or an
operator looks at arrives by fetch.** Nothing the build writes may grow when a run appends a day.

---

## 1. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Measured 2026-09-08: the built site is 110.65 MB across 751 files and grows 1.69 MB and 5.71 pages every published day. One operator page inlines 3,374 KB of ledger rows. A 43.23 MB model sits in git, in the build and in the Pages upload. Four functions walk the whole archive on every build. None of that is what the reader gets - it is what the build carries |
| Hard scope - in | Deleting the 110 dated documents and serving every route from one; the console fetching its months instead of inlining its rows; the verdict band as its own first payload; three distinct states for quiet, missing and unreachable; bounding every read that grows with the archive; moving the encoder out of the repository; deleting the two global build stamps; the gate changes all of that forces; and the seven build-cost findings the superseded draft carried |
| Hard scope - out | A prerendered document for any dated or topic route (owner, 2026-09-08). A deployment or build manifest of any kind (owner, 2026-09-08). Any count that is all-time (owner, 2026-09-08). Caching the built site between CI runs - measured and refused in section 20 |
| ESCALATE triggers | 1. Any row would make a green certify a tree it did not test. 2. A row cannot bound a read without a product decision about what the panel means. 3. Row 11 finds that the search index reader does not already refuse a `model_id` mismatch and the fix is larger than one guard. 4. Susan refuses a console surface and the fix needs new design rather than the vocabulary already named in `docs/concepts/design-system.md` |
| Chosen strategy | Contracts first, then bound what exists, then move the data, then delete the documents, then the encoder, then the gates. Every row ships green on its own - no row leaves `main` in a state where the site is half-migrated |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

---

## 2. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The contracts the rest of this plan reads | - | A | READY | - | - | - |
| 2 | Bound the four archive walks | - | A | READY | - | - | - |
| 3 | The page stops claiming "never" | - | A | READY | - | - | - |
| 4 | The producer writes the console its months | 1 | B | READY | - | - | - |
| 5 | The console fetches instead of inlining | 4 | C | READY | - | - | - |
| 6 | The verdict band arrives first and alone | 5 | D | READY | - | - | - |
| 7 | Quiet, missing and unreachable look different | 5 | D | READY | - | - | - |
| 8 | The shell holds its shape before the data lands | 5 | D | READY | - | - | - |
| 9 | The page carries nothing a later run can change | - | A | READY | - | - | - |
| 10 | One document serves every date | 9 | E | READY | - | - | - |
| 11 | The encoder leaves the repository | 1 | B | READY | - | - | - |
| 12 | The gates measure a shell, not a document | 10 | F | READY | - | - | - |
| 13 | Rebuild only when the push was rebased | - | A | READY | - | - | - |
| 14 | The parcel carries the day, not the archive | - | A | READY | - | - | - |
| 15 | Delete the duplicate verification call | - | A | READY | - | - | - |
| 16 | The build fingerprint covers what the build reads | 15 | B | READY | - | - | - |
| 17 | Stage only what changed | - | A | READY | - | - | - |
| 18 | Measure the build again, and decide what is left | 10, 16 | G | READY | - | - | - |
| 19 | Record what was decided and what it cost | 1-18 | H | READY | - | - | - |

---

## 3. The decisions this plan executes

Every one is the owner's, taken 2026-09-08 under CLAUDE.md section 0. No row re-opens one; a row
that believes a decision is wrong ESCALATEs rather than deviating.

| # | Decision | Note |
| --- | --- | --- |
| D1 | No prerendered document for any dated or topic route. One document serves every URL | The 110 files, 9.54 MB, growing 5.71 a day |
| D2 | The site is a shell for the home page and the console alike. Content loads dynamically. **This is the golden principle** and it admits no special case | Overrides Susan's ruling that the verdict band stay prerendered. Her objection and the mitigation are in row 6 |
| D3 | No spinner. Reserved boxes plus one late shimmer, in phase across every panel | Susan, accepted |
| D4 | An empty chart draws its frame and ticks and no numbers | Susan, accepted |
| D5 | Panels fill in document order, never arrival order | Susan, accepted |
| D6 | A window that spans data we have and data we do not plots what exists and marks the rest. Quiet, missing and unreachable are three states, not two | Susan found the defect; the owner specified the behaviour |
| D7 | The console carries one line saying its panels need JavaScript, removed on mount | Susan, accepted |
| D8 | No deployment manifest, no build manifest, no commit stamp anywhere on the site | Owner reversed an earlier position mid-session. The commit line is deleted and nothing replaces it |
| D9 | No all-time count, of anything, anywhere. `published_days` and every "N of Y where Y is for ever" goes | Owner. This is Rule #12 applied to what a page says, not only to what it reads |
| D10 | The encoder is fetched from Hugging Face at a pinned revision, with our own GitHub Release asset as failover. It is not committed | Owner, over the recommendation of a single origin. Cost in row 11 |
| D11 | Losing the link preview card on a shared digest URL is accepted | Owner. Not raised again |

---

## 4. What was measured

All figures 2026-09-08 against `main` at `e89d6d8f`. Runner figures come from the GitHub Actions
API on `ubuntu-latest`. Laptop figures are Intel Core i7-1265U / Windows 11 / node 24.12.0, warm
cache, n = 1 unless a spread is given.

| Fact | Value |
| --- | --- |
| Built site | 110.65 MB / 751 files at 19 published days; 87 MB / 36 pages at 5 days |
| Growth | 1.69 MB and 5.71 prerendered pages per published day. Six routes are fixed; the rest are dated |
| Bundle split | encoder 43.23 MB (39.1 pct), `_app/` 22.54 MB (20.4 pct), `digest/` 17.85 MB (16.1 pct), prerendered HTML 14.12 MB (12.8 pct), `index/` 4.05 MB, `telemetry/` 1.12 MB |
| Dated and topic documents | 110 files, 9.54 MB |
| `console/index.html` | 3,726 KB. Inlined data payload 3,374 KB (90.6 pct), rendered markup 351 KB, the 32 server-rendered charts 139 KB (3.7 pct) |
| What is in that payload | `source` 28,486 times, `stage` 9,490, `run_id` 9,383 - roughly 9,400 raw telemetry rows |
| Other console pages | `console/model/` 367 KB, `console/machine/` 280 KB, `archive/` 22 KB |
| Encoder in git | 8 tracked files under `frontend/static/assist/models/`, 43.23 MB, of 20 tracked files under `frontend/static` in total |
| Site builds per publish | 3. digest.yml pre-commit 21 s, digest.yml post-commit 19 s, pages.yml 24 s. Only the third is published |
| Pages build step over time | 8.5 s at 2 published days (2026-08-22), 13 s at 5, 21 s at 11, 24 s at 19. About 0.9 s per published day, though the console pages also landed in that window |
| `assertBuild()` | 16.2 s per call - 3.23 s input hash plus 12.93 s output hash. Called 3 to 5 times per `test:changed`, plus once per build and once per preview start |
| Output hash scope | 222.4 MB / 1,589 files across `frontend/build` and `frontend/.svelte-kit/output`, at 8.14 ms per file and 17.2 MB/s |
| Input hash scope | 66.55 MB, of which corpus 13.44 MB, state 17.72 MB and `frontend/public` 29.75 MB. **91.5 pct of it is data a run appended, not source** |
| Local build stages | copy-visuals 5.82 s, build-state begin 3.23 s, vite build 77.4 s warm, build-state complete 12.93 s |
| Visuals parcel | 6.85 MB compressed, and its `path:` carries the whole 454-file digest tree when one day is new |
| Live artifact storage | 594.4 MB across 332 artifacts, against the 500 MB figure in Rule #2 |
| Actions cache | 9,892 MB of 10,240 MB - 96.6 pct full. A large restore measured 41, 44, 46 and 73 s, against a build of 21 to 24 s |
| Day payload projection | The staged copy is 468.58 bytes an item against the committed 792.65, which is 40.9 pct less. Measured 2026-08-31, 11 days and 3,733 items, gzip -9 |

**What the shell is worth, and it is an estimate until row 18 measures it.** Shipping `_app/`
(22.54 MB), six small documents and the fonts and icons (0.10 MB), with the encoder, the day
payloads, the index, the telemetry and the 110 dated documents all fetched, is about 23.8 MB
against 110.65 MB - roughly 78 pct smaller, and it stops growing. Labelled an estimate per
Rule #10; row 18 replaces it with a measurement.

---

## 5. Row #1 - The contracts the rest of this plan reads

- **Scope:** Every persisted shape this plan introduces, as a Pydantic model, before any logic
  reads or writes it (Rule #3). Nothing else.
- **Files touched:**
  - `backend/idhazh/contracts/` - a model for one month of console telemetry as a browser asks
    for it, and a model for the verdict band row 6 fetches
  - `config/idhazh.json` and its config model - `assist.model_base_url`, `assist.model_revision`,
    `assist.model_fallback_url`; `console.shimmer_after_ms` default 400
  - `schemas/` - generated, `version` stamped `2026-09-08`, `changelog` opened
  - `frontend/src/contracts/` - regenerated
- **Acceptance gates:** contract drift gate regenerates byte-identical; `npm run check`; the
  shared test selector.
- **Oracle:** `git diff --exit-code` after a regeneration run. A hand-edited generated file fails
  this, which is the point.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `console.shimmer_after_ms` default 400 is an estimate, not a measurement. Row 8 measures the median shard read and settles it | Rule #10 |
| 2 | The verdict band is a separate payload from the telemetry months, because it is fetched first and alone (row 6) and because it changes once a run where the months change once a month | Owner D2 mitigation |

---

## 6. Row #2 - Bound the four archive walks

- **Scope:** Four functions in one file walk the whole published tree on every build, and three of
  them walk it through the fourth. Give each a bounded input. This is Rule #12 and it is worth
  doing whether or not the rest of the plan lands.
- **Files touched:**
  - `frontend/src/lib/server/payload.ts` - `publishedDates()` is the root; `loadManifests()`,
    `publishedItems()` and `publishedCharts()` each loop over it. `itemHealthRows()` and
    `feedResults()` read every shard in their directory. `evalRows()` reads the whole eval ledger
  - The console loaders that call them
- **What "bounded" means here:** every one of these takes a window of days or months, defaulting to
  the widest preset the surface offers, exactly as `telemetryRows(root, windowDays)` and
  `dayMetrics(dates)` already do. Both of those already cite Rule #12 in their own comments and are
  the pattern to copy.
- **Already bounded, do not touch:** `telemetryRows`, `dayMetrics`,
  `frontend/src/routes/console/model/+page.server.ts` and
  `frontend/src/routes/console/machine/+page.server.ts`. All four carry explicit bounds and say so.
- **Acceptance gates:** the shared test selector; `npm run check`; browser smoke on all four console
  routes.
- **Oracle:** build the site, note the wall clock of the console routes, add ten days to a fixture
  digest root, build again. **The time must not move.** It does today.
- **Second oracle:** grep `payload.ts` for a function that reads a directory without taking a
  window. There must be none, or the one that remains carries a comment naming what it reads, how
  the cost grows and why a bounded input cannot answer it, per
  [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md).

### Rejected alternatives

| # | Option | Why rejected |
| --- | --- | --- |
| 1 | Cache the walk between builds | Every CI job is a cold start, so a cache saves nothing on the authoritative arm. It also hides the growth rather than removing it |
| 2 | Leave it until the shell lands, since the console will stop calling these anyway | The work does not vanish, it moves to the producer in row 4 and has to be bounded there. Bounding it here first means row 4 copies a correct function rather than a growing one |

---

## 7. Row #3 - The page stops claiming "never"

- **Scope:** Four sentences on the console make an all-time claim. They are the reason the
  unbounded reads exist, and they get less useful as they get more expensive.
- **Files touched:** `frontend/src/routes/console/+page.svelte` and the loader fields behind it in
  `frontend/src/routes/console/+page.server.ts`.
- **The four:**
  - `which read every feed the ledger has ever carried`
  - `{clean} of {checked} feeds have never failed a read`
  - `feeds have never been read at all`
  - `feeds that never failed reported a source we have never read`
- **What replaces them:** the same fact, over the window on screen. `No feed failed a read in these
  30 days.` A feed that broke once in August and has been clean since is not "never failed", and
  the operator's question is whether anything is broken now.
- **Also verify, and do not assume:** whether `sourceHealthView` is windowed at source before
  `sources.reduce(...)` sums `opportunities`, `publications` and `source_failures`; and whether
  `view.runsRead` on the machine page counts the window or the ledger. The machine page's server
  comment claims bounded. Check both; fix what is not.
- **Acceptance gates:** the shared test selector; browser smoke on `/console/`.
- **Oracle:** no reader-facing string on any console route contains `never`, `ever`, `all time` or
  `in all` as a claim about the record rather than about the window.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is Rule #12 applied to what a page says. A sentence that can only be true by reading everything is a growing read wearing a different coat | Owner D9 |

---

## 8. Row #4 - The producer writes the console its months

- **Scope:** The backend writes what the console will fetch: one payload per month of telemetry,
  plus the verdict band. **One month per run. Never a walk over the archive** - the run knows which
  month it just wrote.
- **Files touched:**
  - `backend/idhazh/` - the producer, writing to `frontend/public/telemetry/`
  - `frontend/scripts/copy-visuals.mjs` - stages them like the day payloads it already stages
  - `backend/tests/` - the producer's tests, from a built fixture
- **Nothing consumes these yet.** This row ships alone and changes no page.
- **Acceptance gates:** backend tests; the payloads validate against their schema; `idhazh
  validate-days` still passes.
- **Oracle:** run the producer twice against a fixture with twenty months. The second run opens one
  month, not twenty. Assert on the file handles, not on the wall clock.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Monthly, not daily and not per-window. The state shards are already monthly, so the unit exists and the worst case for a 30-day window is two files | Read from `state/telemetry/` |
| 2 | A frozen month is written once and never rewritten. Only the current month changes, which is what makes a browser cache of an older month correct for ever | Rule #12 |

---

## 9. Row #5 - The console fetches instead of inlining

- **Scope:** The console stops serialising 9,400 telemetry rows into its document and fetches the
  months its window needs.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts` - drops the fifteen row readers
  - `frontend/src/routes/console/model/+page.server.ts`,
    `frontend/src/routes/console/machine/+page.server.ts` - same
  - `frontend/src/routes/console/+page.svelte` - `loadVisibleMonths()`, its pending-month set and
    its month cap already exist. **Promote them from "widen the window" to "load the page".** This
    is a reuse, not an invention
  - `frontend/src/lib/server/chart-render.ts` and `frontend/src/lib/charts/` - charts render in the
    browser from fetched rows
- **Acceptance gates:** the shared test selector; browser smoke on all four console routes,
  including with the payload absent; `npm run check`.
- **Oracle:** `console/index.html` is under 400 KB. It is 3,726 KB today, and 351 KB of that is the
  markup, so the target is the markup plus the shell and nothing else.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Windowed and lazy together: the open window's months first, the rest of the panels behind it | Owner |
| 2 | The 32 charts move to the browser. They are 139 KB of the 3,726 KB, so this is not where the bytes are - it moves because a chart drawn from fetched rows is the only way the window control can mean anything | Measured |

---

## 10. Row #6 - The verdict band arrives first and alone

- **Scope:** The band that answers "is the pipeline working" - yesterday's sentence, the run
  squares, the worst thing with its link, the site-size bar - becomes its own small payload,
  fetched before anything else on the page.
- **Files touched:** `frontend/src/routes/console/+layout.server.ts` (it derives these today and
  stops), the new band payload from row 4, and the console layout component.
- **Why this row exists, stated once:** Susan ruled that the band stay prerendered and named a
  fetched band as the one way this change is a net loss - the operator waits a round trip to learn
  a run failed. The owner overruled her on consistency: one mental model, shell plus fetch, with no
  special case, because a special case makes every future page ask which kind it is. This row is
  the mitigation both sides accepted. **The band is the smallest payload on the site and the first
  request the page makes**, so the answer arrives in one round trip rather than after the page
  settles.
- **Acceptance gates:** the shared test selector; browser smoke; the band renders its own failed
  state per row 7.
- **Oracle:** the band payload is under 5 KB, and in a recorded network trace it is the first
  request the console issues after the document and the bundle.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Consistency beats the round trip. A prerendered band on one page is a second architecture nobody would remember was there | Owner D2, over Susan |
| 2 | The band's payload is separate from the telemetry months so that it can be first and small. Merging them would put 9,400 rows in front of three sentences | Owner |

---

## 11. Row #7 - Quiet, missing and unreachable look different

- **Scope:** Three states, currently two, and the third is a defect that exists today: a month
  shard that fails to load draws an unmarked gap, so **a quiet pipeline and a broken fetch are the
  same picture** - which is the exact thing this page exists to tell apart.
- **The three:**

  | State | Means | Shows |
  | --- | --- | --- |
  | Quiet | The window is genuinely empty | Neutral tint, a sentence saying what is true, and the one preset that would change it |
  | Missing | We never had data for those dates | The span marked on the chart itself, the dates named in the caption. No alarm - normal for a young archive |
  | Unreachable | The fetch did not arrive | Warn tint, names the month, says what it does have, and a `Try again` scoped to that panel |

- **The owner's spec, verbatim in effect:** a 92-day window where June has data, part of July is
  missing and August is fine plots June, marks the July span, and plots August. It does not fail,
  does not draw a flat line through the gap, and does not refuse the window.
- **Files touched:** `frontend/src/lib/charts/`, the console panels, and whatever writes the
  browser-console warning `telemetry <month> unavailable; showing a gap` today.
- **Acceptance gates:** the shared test selector; browser smoke; a spec per state.
- **Oracle:** a built fixture with a hole in the middle of the window renders a marked span, and a
  built fixture whose fetch is blocked renders a different thing. Two screenshots that do not match.

---

## 12. Row #8 - The shell holds its shape before the data lands

- **Scope:** The loading experience Susan specified, and the first use of two things the design
  system already names but nobody has built.
- **What ships:**
  - Every panel titled and sized in the document. Charts reserve their exact box by aspect ratio
    and never change height
  - An empty chart draws its axis frame and tick marks and **no numbers**. An invented axis label
    is a class of failure the shell doc already names
  - `shimmer` and the `loading` state class implemented. Both are named in
    `docs/concepts/design-system.md`; neither exists in CSS today
  - The shimmer starts after `console.shimmer_after_ms`, so a fetch that lands first never animates
  - **Every skeleton shares one timeline, in phase.** Out of phase, twelve sweeping boxes read as
    twelve broken things
  - Under `prefers-reduced-motion`, a flat tinted block with no gradient. The global rule in
    `frontend/src/styles/app.css` zeroes durations, which would freeze a moving gradient mid-sweep
    and leave a bright band nobody chose
  - Panels fill in document order. A panel that finishes early waits its turn
  - One status line for all background work, in words and in files - `Fetching 2 months.` It exists
    in `frontend/src/lib/components/WindowControl.svelte` today, driven off a count
  - Its no-script string becomes untrue the day this lands and is rewritten in the same commit
  - One line above the panels saying they need JavaScript, removed on mount
- **Never:** move anything above the scroll position; dim a panel that already has data; print
  bytes or a percentage; block a control; scroll, steal focus, raise a toast or count a number up;
  announce every arrival.
- **Acceptance gates:** the shared test selector; browser smoke; a reduced-motion spec.
- **Oracle:** the console's layout does not shift between first paint and settled. Measure the
  bounding box of every panel at both moments and compare.
- **Design gate:** Susan reviews before merge, per section 9 of CLAUDE.md.

---

## 13. Row #9 - The page carries nothing a later run can change

- **Scope:** Two global stamps make every page's bytes move on every build, and one of them puts
  today's date inside the oldest day's page. Delete both and show nothing in their place.
- **Files touched:**
  - `frontend/src/lib/components/SiteFooter.svelte` - the build line, the verification sentence,
    the retention sentence
  - `frontend/src/routes/+layout.server.ts` - returns `{ ui }` only; `latestDate` and `loadDay` go
    with it
  - `frontend/vite.config.ts`, `frontend/src/app.d.ts` - `__BUILD_COMMIT__` and `__BUILD_DATE__`
  - `frontend/src/lib/components/EmptyDay.svelte`, `DigestList.svelte` and the call sites - the
    `latest` prop
  - `frontend/tests/footer-facts.spec.ts` - it pins the deleted sentences by regex
  - `docs/architecture/publishing/frontend.md`, `docs/architecture/publishing/layout.md`,
    `docs/concepts/design-system.md` - all three repeat the retention promise
- **Acceptance gates:** `npm run check`; the shared test selector; browser smoke on a dated page,
  an empty day, the archive and the console.
- **Oracle:** record the sha256 of `build/2026-08-21/index.html`. Publish a new day into the digest
  root. Build again. **The hash must be identical.** It is not today - `2026-09-08` appears twice
  in that file, once in the footer and once as `latest` in the layout data.
- **Second oracle:** `+layout.server.ts` imports nothing from `$lib/server/payload`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No commit stamp, no build date, no manifest to fetch one from. The owner considered a fetched manifest and reversed: the commit is not worth a file, a schema, a request and a cleanup story | Owner D8 |
| 2 | The site stops promising that nothing is deleted. Removing the sentence is the honest move; do not replace it with a promise to delete either | Owner |
| 3 | `latest` is deleted end to end rather than moved. No route uses it; the home page computes the same value as `today` | Read from source |

---

## 14. Row #10 - One document serves every date

- **Scope:** The 110 dated and topic documents stop being written. One document serves every URL.
- **Files touched:**
  - `frontend/src/routes/[date]/+page.server.ts`, `[date]/[vertical]/+page.server.ts` - `prerender`
    goes, and the seed goes with it
  - `frontend/src/routes/+page.server.ts`, `archive/+page.server.ts` - same
  - `frontend/svelte.config.js` - the prerender block, `handleUnseenRoutes`, and the comment that
    describes the seed-plus-fetch arrangement this row ends
  - `frontend/prerender-guard.js` - its expectations change or it goes
  - `frontend/src/service-worker.ts` - the shell it caches is now the whole site
- **The mechanism is already configured.** `adapter({ fallback: '404.html', strict: false })` is in
  place, so GitHub Pages serves the fallback for any path it cannot find, and the browser reads the
  address bar to decide what to fetch.
- **Acceptance gates:** browser smoke on `/`, a dated page, a topic page, the archive and all four
  console routes; each with its data file present and absent; `npm run check`; the shared test
  selector.
- **Oracle:** `build/` contains no `index.html` under a dated directory. Six documents, and the
  count does not move when a day is added.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Delete the documents rather than shrink them to a head. A file per day is still a file per day | Owner D1 |
| 2 | The link preview card on a shared digest URL is lost, because Pages serves the fallback with a 404 status and preview crawlers do not run JavaScript. Accepted | Owner D11 |
| 3 | Date navigation gets faster, not slower: the shell is already in memory, so moving from one day to the next crosses only the day's JSON | Read from the existing `[date]` fetch path |

---

## 15. Row #11 - The encoder leaves the repository

- **Scope:** 43.23 MB of ONNX weights come out of git, out of the build and out of the Pages
  upload. The browser fetches them from Hugging Face at a pinned revision, and falls back to our
  own GitHub Release asset when that fails.
- **Files touched:**
  - A GitHub Release asset carrying the weights, published once
  - `frontend/src/lib/assist/loader.ts` - `allowRemoteModels` becomes conditional; the source comes
    from config. Today it is hard-set false with the comment "Same origin, always"
  - `frontend/svelte.config.js`, `frontend/asset-base.js` - `connect-src` gains both origins,
    derived from the same config values that drive the fetch
  - `frontend/src/lib/assist/search.ts` - **refuses** an index whose `model_id` is not the loaded
    encoder. `schemas/search-index.schema.json` already makes `model_id` required; whether the
    reader enforces it is the first thing this row checks
  - The backend index writer - stamps `model_id` from config, so index and encoder cannot disagree
  - `frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22/` - the eight tracked
    files go; `PROVENANCE.md` stays
  - `frontend/src/service-worker.ts` - decides explicitly whether to cache a remote model
- **Acceptance gates:** browser smoke with the model reachable, with Hugging Face blocked, and with
  both blocked; `npm run check`; the shared test selector.
- **Oracle:** the built site contains no `.onnx`. Search still works. With both origins blocked,
  search says so and **every digest assertion still renders** - section 0a requires the bundle to
  render complete with the model absent.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Hugging Face primary, our Release asset as failover | Owner D10, over a recommendation of one origin |
| 2 | The failover is a hard rule: try Hugging Face, on any failure use ours, never the reverse and never a third | This plan |
| 3 | Swapping the encoder later is a re-encode of every published day. That is a growing read and it is legal - it is one-off, a person runs it, and it gets its entry in `docs/concepts/growing-reads.md`. It is never a per-run cost | Rule #12 escape hatch |

### The cost, stated once

`connect-src` is the directive `svelte.config.js` calls "a browser-level impossibility rather than
a property of our own code being careful". It bounds every request a planted instruction inside a
summary could cause (Rule #11). **Two origins is a wider hole than one.** Both are derived from
config so the list is in one place and reviewable, and no third may be added without an owner
decision recorded here.

---

## 16. Row #12 - The gates measure a shell, not a document

- **Scope:** The bundle gate guards per-page ceilings. When every page is the same small document,
  those ceilings stop guarding anything, and the thing that can now grow without a ceiling is a
  fetched payload.
- **Files touched:** `frontend/scripts/` (the bundle gate), `.github/workflows/ci.yml`,
  `.github/workflows/pages.yml` (the published-size report).
- **What changes:**
  - Page ceilings come down to what a shell actually weighs
  - **A payload ceiling is added.** A fetched window has no ceiling today, so nothing would catch a
    month payload that quietly doubled
  - The encoder ceiling changes meaning when the encoder is not in the bundle
- **Acceptance gates:** the gate fails on a deliberately oversized fixture payload and passes on
  the real one.
- **Oracle:** raise a fixture payload past the ceiling; CI goes red. Lower it; CI goes green.

---

## 17. Rows #13 to #17 - The build-cost findings

Five independent rows, each shipping alone. These are the surviving rows of the superseded draft;
its row 1 is delivered by row 9 above, and its rows 7 and 8 are folded into row 18.

| Row | What | Measured saving |
| --- | --- | --- |
| 13 | **Rebuild only when the push was rebased.** The site is built three times per publish and only the third is published; the first two use a different `BASE_PATH` so they can never be reused anyway | About 19 s per publish, five times a day |
| 14 | **The parcel carries the day, not the archive.** The `visuals` artifact's `path:` includes all of `frontend/public/digest/` when one day is new | Upload and download time, and it grows |
| 15 | **Delete the duplicate verification call.** `run-checks.ts` calls `assertBuild` on two adjacent lines with nothing between them | 16.2 s per run |
| 16 | **The build fingerprint covers what the build reads.** `inputFingerprint` hashes 66.55 MB of which 60.91 MB is corpus, state and published payloads - 91.5 pct is data a run appended. Use git's own index rather than hand-rolling a manifest: `git ls-files` already maintains one, handles the racily-clean case, and is not ours to version | Most of 3.23 s per call |
| 17 | **Stage only what changed.** `copy-visuals.mjs` deletes and re-copies every file every build | 5.82 s locally, and **zero in CI** - every CI job starts with the target absent, so this is a local-loop fix only |

Row 16 note: `state/` and `frontend/public/` stay in scope. The console does read them at build
time, so they are genuine inputs and need a cheaper mechanism rather than a shorter list. `corpus/`
is the one to drop - no test result depends on it.

---

## 18. Row #18 - Measure the build again, and decide what is left

- **Scope:** The draft's rows 7 and 8 proposed measuring the stat-versus-read split of the output
  fingerprint and then having the producer hash while the verifiers only stat. **That may no longer
  be worth doing.** The output hash covers 222.4 MB today; after rows 10 and 11 the built site is
  an estimated 23.8 MB, so the same work costs roughly a fifth as much for free.
- **What this row does:** re-measure `assertBuild()`, the whole build, the Pages build step and the
  published size on the migrated tree. Then either close the fingerprint work as no longer worth
  its complexity, or open it with a number that justifies it.
- **Acceptance gates:** none - this row produces a measurement and a recommendation.
- **Oracle:** the numbers in section 4 are replaced with post-migration ones, carrying hardware,
  date and spread (Rule #10).

---

## 19. Row #19 - Record what was decided and what it cost

- **Scope:** The documentation this plan owes.
- **Files touched:**
  - `docs/concepts/ui-shell.md` - **the spinner ban survives on narrower ground.** Its stated reason
    is that a reader already has a readable frame, so there is nothing for a spinner to fill. That
    reason is false on a route that ships an empty shell on purpose. Write the narrower ground down
    or the next agent reads the ban as absolute again
  - `docs/architecture/publishing/` - the shell, the fetch shapes, the three states, the measured
    bytes
  - `docs/concepts/growing-reads.md` - the re-encode migration, and any read row 2 could not bound
  - `CLAUDE.md` section 0a - "the bundle must render complete with the model directory deleted" now
    describes a permanent state rather than a test
  - `docs/reference/agent-notes.md` - anything a worker learned that would make a command lie
- **Acceptance gates:** docs only. No local application suite (AGENTS.md item 5).

---

## 20. Refused, with the measurement that refused it

| # | Option | Why refused | Measured |
| --- | --- | --- | --- |
| 1 | Cache the built site between CI runs | A large cache restore costs 41 to 73 s against a build of 21 to 24 s. The cache is slower than the work | 2026-09-08, four shards |
| 2 | Reuse prerendered pages between builds | Every CI job is a cold start. There is nothing to reuse from | 2026-09-08 |
| 3 | Fetch day payloads from `raw.githubusercontent.com` | Pages serves the identical file from our own origin, on a real CDN, with no rate limit. There is no benefit unless the 1 GB cap binds, and it is about 540 days away at 1.69 MB a day | 2026-09-08 |
| 4 | Point SvelteKit's assets folder at `frontend/public/` to stop the staging copy | The staged copy is a projection, not a duplicate: 468.58 bytes an item against 792.65. Serving the committed shape would send 40.9 pct more bytes to every reader | 2026-08-31 |
| 5 | A deployment or build manifest carrying the commit and the newest day | Considered and reversed by the owner mid-session. The commit is not worth a file, a schema, a request and a cleanup story; `latest_day` and `published_days` are answers the fetched data already carries, and the second is an all-time count | Owner, 2026-09-08 |
| 6 | Shrink the dated documents to a head instead of deleting them | Keeps the link preview and 98 pct of the bytes, but a file per day is still a file per day | Owner, 2026-09-08 |
| 7 | A single origin for the encoder | Recommended and overruled. The owner accepts a wider `connect-src` for availability | Owner, 2026-09-08 |
| 8 | A guard that lists the paths a test may not read | Tried and deleted on 2026-09-06. It enumerated the hazard rather than the safe set, its own upkeep grew with the collections, and a list of paths makes a judgement call look like a permission slip. Rule #12 is enforced by review | CLAUDE.md Rule #12 rationale |

---

## 21. What could go wrong, and where it bites

| # | Risk | Where it shows | Mitigation |
| --- | --- | --- | --- |
| 1 | A fetch fails and the page white-screens | Any route, any panel | Section 1a "degrade, do not fail" and section 12 gate 5. Every row's browser smoke runs with the data file absent |
| 2 | The console's first frame answers nothing | `/console/` | Row 6: the band is the smallest payload and the first request |
| 3 | `connect-src` widens and a planted instruction reaches a second origin | Rule #11 | Row 11: both origins from config, in one place, no third without an owner decision |
| 4 | A row bounds a read by changing what a panel means without saying so | Rows 2 and 3 | ESCALATE trigger 2 |
| 5 | The producer's monthly write quietly becomes a walk | Row 4 | That row's oracle counts file handles, not seconds |
| 6 | Reduced motion freezes a gradient mid-sweep | Row 8 | A flat block, not a shortened animation, and a spec for it |
| 7 | The search index and the loaded encoder disagree silently | Row 11 | The reader refuses a `model_id` mismatch. If it does not today, that is ESCALATE trigger 3 |

---

## See also

- [`CLAUDE.md`](../CLAUDE.md) - sections 0, 0a, 1a, 3, 9, 11, 12, 13; Rules 1, 2, 3, 6, 10, 11, 12.
- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row.
- [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every
  acceptance gate here.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - Rule #12's escape hatch
  and where a chosen growing read is recorded.
- [`docs/concepts/design-system.md`](../docs/concepts/design-system.md) - the motion set and the
  state classes rows 7 and 8 are the first users of.
- [`docs/concepts/ui-shell.md`](../docs/concepts/ui-shell.md) - the five states and the spinner ban
  row 19 narrows.
