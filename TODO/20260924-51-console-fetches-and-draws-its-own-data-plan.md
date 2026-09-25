# Plan 51 - The console fetches and draws its own data

**Last Updated**: 2026-09-24

**Level**: 5 (CLAUDE.md section 6). Row 3 decides whether `state/` reaches a browser, which is a publishing contract. Rows 1 and 2 are Level 3 and Level 2 and carry no contract change beyond one copied settlement key.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3 and N5 - the browser queries the store for the slice it draws, fetches at view time, and d3 draws it. **Contract**: section 2 declares every shape, key, signature and config literal these three rows need. **Code**: the three rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 - rows 1 and 2 share no source file, and rows 3 and 4 are each serial against them; merge each pull request before dispatching the next; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The Hardware route counts every job twice, its span control sits fifteen panels above the reader who wants it, and every chart on the console is drawn from data baked into the page by the build. This makes one panel prove the whole chain - query the store in the browser, draw it in d3 - and writes the house style the rest follow. |
| Hard scope - in | - `state/host-fingerprint/` is read settled, so a job counts once.<br>- The five-tab console strip sticks, and the span control rides on it.<br>- `state/host-fingerprint/` becomes parquet and reaches the browser, which queries it for the columns and days one panel draws.<br>- `frontend/src/lib/data/` holds the one query door every later panel uses; `frontend/src/lib/charts/d3/` holds the house style every later chart uses. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A tenth prerendered route, or retiring an existing one.<br>2. A charting library that is not d3.<br>3. A new committed payload under `frontend/public/`.<br>4. A measured figure that contradicts section 3.<br>5. Any change to `ConsoleBand` beyond the one additive field row 4 declares - it is the payload every console route fetches first.<br>6. **Row 3 stops before its first commit and asks.** `frontend/src/lib/server/host-fingerprint.ts` and `frontend/src/lib/server/machine-counters.ts` read `state/host-fingerprint/` as CSV at build time and serve the fourteen panels this plan scopes out. Moving the store to parquet breaks both. Three answers are defensible - a second build-time reader through the same engine, a dual write for one release, or holding the migration until every panel is on the browser door - and they are different plans. This is Level 5 and it is the first thing to settle.<br><br>**"How the browser reaches the bytes" was trigger 1 and is settled**, 2026-09-25: `state/` carries its own indexes, declared by plan 50's section titled "The shapes a worker must not invent" and committed; the build copies the published stores' compact periods verbatim into gitignored `frontend/static/state/` and generates nothing. |
| Chosen strategy | Correct the number first, move the chrome second, change the grammar last. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The other fourteen panels on `/console/machine`, and the four other console routes | Two grammars coexist on one route: one panel queries parquet and draws in d3, fourteen read CSV at build time and draw in ECharts. `echarts@^5.6.0` stays installed with fifteen importers | The charting plan, which starts from row 3's house style instead of inventing one. **Row 3 exists to make that plan cheap, not to be it** |
| Taking any route off `export const prerender` | Nine files under `frontend/src` keep it. Row 3's panel fetches after mount on a page that still prerenders, which is legal and is what lets one panel prove N3 without moving a route | The plan that moves a whole route, which owns the first-paint and no-script questions for every panel on it |
| Retiring the nine payloads under `frontend/public/` | Telemetry-intent N7 and N8 get no stone here. `frontend/public/machine/<YYYY-MM>.csv`, the `machine-shard-row` roll-up of `host-fingerprint` joined to `item-health`, keeps being published | The same whole-route plan. Retiring a published payload needs every reader moved first |
| The throughput spread per machine kind | The Platform Mix panel says what we were given and not how much one machine varies | It is the machine cards' and the shard board's question. Row 3's readout links to them |
| Fixing defect 26, the settlement-key guard that reads one constant twice | Row 1 adds a third key to a guard that cannot fully check it, and says so in the pull request | Its own row. A pull request that fixes a guard and the thing the guard was meant to catch leaves neither fix with an independent witness |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star and sits above this plan (CLAUDE.md section 0d). The seven rules a panel obeys are [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md).

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N1 | Parquet at rest, CSV retired | **Stone laid by row 3** for `state/host-fingerprint/`, through the door plan 50 builds |
| N2 | The browser queries the parquet itself | **Stone laid by row 3.** One module owns the engine and every later panel queries through it |
| N3 | The browser fetches its own data at view time | **Stone laid by row 3**, on one panel that fetches after mount |
| N4 | Prerendering is an anti-pattern | **Not here.** Nine files keep `export const prerender`, and ESCALATE trigger 2 stops a row adding a tenth |
| N5 | d3 is the only charting library | **Stone laid by row 3**, which writes the house style and moves one importer of fifteen |
| N6 | One writer per path | **Stone laid by row 3**, by routing `host-fingerprint` through plan 50's door |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Stone laid by row 3.** The staged copy is byte-identical and gitignored, so `state/` stays the only source and nothing production lands under `frontend/` in git |
| N9, N10, N11 | The name, the two roots, the one shard pattern | **Inherited** from plan 50's door. This plan mints no naming rule of its own |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The Hardware route stops counting every job twice | - | A | PENDING | - | - | - |
| 2 | The console shell: a stuck tab strip, the span control on it, four named anchors | - | A | PENDING | - | - | - |
| 3 | `host-fingerprint` becomes parquet, is compacted every run, and is published | plan 50's rows titled "The payload store, the two roots, and the arrow mapping" and "The index task, two compact periods, and the diagram moves into the page" | B | PENDING | - | - | - |
| 4 | One panel end to end: the browser fetches the store and draws it in d3 | 1, 2, 3 | C | PENDING | - | - | - |

**Rows 1 and 2 run two-wide and their lists were diffed: they share nothing.** Row 1 holds `frontend/src/lib/server/payload.ts`, `host-fingerprint.ts`, `machine-counters.ts`, `frontend/src/lib/charts/fleet.ts` and `frontend/src/lib/console/machine/PlatformMixPanel.svelte`; row 2 holds `frontend/src/routes/console/+layout.svelte`, `ConsoleNav.svelte`, `SiteHeader.svelte`, `frontend/src/lib/console/band.ts` and `frontend/src/app.css`. No spec file is in both lists.

**Row 3 is the migration and row 4 is the reader.** Row 3 is the only one-way change here: `state/host-fingerprint/` becomes parquet and the store is published. Row 4 adds the query door, the 7,321,471-byte engine and the d3 house style, and all of it reverts to nothing. Row 4 also rewrites `fleet.ts` and `PlatformMixPanel.svelte`, which row 1 owns, and reads `console.span_choices_days`, which row 2 mints - which is why it waits on both.

**Row 3 waits on two of plan 50's rows, not one.** The door and `StoreConfig.published` come from the first; every index, every watermark and every compact file the browser addresses comes from the second, which also carries the one-file-per-date oracle this plan's design rests on.

**Row 3 also collides with plan 50's row titled "The gardener: registry, config, schedule, record, commit loop"** on `frontend/src/lib/server/host-fingerprint.ts`. An owner running both plans holds whichever is not already in flight.

## 2. The contracts

### 2.1 `HOST_FINGERPRINT_KEY`, the frontend copy

`backend/idhazh/ledger.py` line 262 declares `HOST_FINGERPRINT_KEY: Final = ("date", "run_id", "job", "shard")`. The frontend carries a hand-written copy beside `ITEM_HEALTH_KEY` in `frontend/src/lib/server/payload.ts`:

```ts
/** What makes two machine rows the same record. The Pydantic original is
 *  `ledger.HOST_FINGERPRINT_KEY`; the test below holds this copy in step. */
export const HOST_FINGERPRINT_KEY = ['date', 'run_id', 'job', 'shard'] as const;
```

**The settle rule is a cell merge, and the mechanism this repository already has cannot express one. That is this row's real work.** `settledDayShards(dir, key, prefer, days)` takes `Preference = (later, kept) => boolean`, a predicate that chooses **one whole row** and throws the other away. Two host-fingerprint rows of one key are two halves of one row, so choosing either loses cells.

So `payload.ts` grows a second, narrower door beside the one it has:

```ts
/** Two rows of one key are one job's two halves: the hardware probe wrote one
 *  before the heaviest step, the clock wrote the other after the last item.
 *  Neither row is preferred - the cells are unioned, and a cell present in both
 *  is a defect the test below counts. */
export function mergedDayShards(
	dir: string,
	key: readonly string[],
	days?: number
): CsvTable;
```

`settledDayShards` is untouched, because `state/scores/` and `state/item-health/` genuinely do want one row of the two. **A merge is not a preference with a different name**, and expressing it as one is what would have lost the cells quietly.

**Settlement is per day.** The key carries a `date` cell, so a re-measurement of the same job on a later day cannot be deleted by settling over the whole window.

### 2.2 The query door

`frontend/src/lib/data/store.ts` is **the only module in `frontend/` that imports the query engine**, mirroring the backend's single-engine rule. Every panel goes through it.

```ts
/** Ask a committed store for the slice a panel draws. Columns and a date range
 *  are named by the caller; nothing fetches a whole store. */
export async function slice(
	store: StoreName,
	opts: { columns: readonly string[]; from: string; to: string; where?: string }
): Promise<Row[]>;

/** One parquet row as the engine hands it back. */
export type Row = Record<string, string | number | boolean | null>;

/** The stores this console may query. A closed set: a panel cannot name a path. */
export type StoreName = 'host-fingerprint';
```

**`StoreName` maps to an address inside this module and nowhere else.** The door joins `visuals.asset_base_url` - or SvelteKit's own repository prefix when that knob is empty, which is the shipped default - onto the committed path unchanged: `state/compact/<store>/index/daily.json`, `state/compact/<store>/daily/<YYYY>/<MM>/<DD>.parquet`, `state/compact/<store>/monthly/<YYYY>/<MM>.parquet`. Getting the prefix wrong is the commonest failure on this host, so one module owns it. A panel that could name a path could name any path, and the published list would stop being the bound.

**Whole files are fetched and handed to the engine as buffers**, the same way the month search index already is. No byte ranges. Column projection then saves parse time rather than bytes, and the plan says that rather than implying the fetch got smaller.

**Cost, one store, per span the control offers.** `console.span_choices_days` is `[1, 7, 14, 30, 90]`. At `daily_keep_days: 45` a span of 30 or less is served entirely from the daily period; only the 90-day span reaches a monthly file.

| span | index requests | monthly files | daily files | total requests | bytes |
| --- | --- | --- | --- | --- | --- |
| 1 day | 2 | 0 | 1 | **3** | ~13 KB |
| 7 days | 2 | 0 | 7 | **9** | ~93 KB |
| 30 days | 2 | 0 | 30 | **32** | ~397 KB |
| 90 days | 3 | 1-2 | 55 | **59** | ~760 KB |

At the measured 89 ms edge the two index requests are one round-trip wave of about 180 ms before the first byte of data. **The one-day span is the cheapest in the set, which is only true because no raw file is published** - the paragraph below says what that cost.

**The browser cannot list a directory, so the store carries its own indexes.** Owner ruling, 2026-09-25: **`state/` presents its own index, and the build generates nothing.** Plan 50's section titled "The shapes a worker must not invent" declares the small JSON files that do it, each committed, each with exactly one writer. This plan invents no address book, declares no contract of its own, and adds no generating step.

**Three findings settled it, and none of them is the byte ceiling that prompted the question.**

**The band is prerendered into every console document.** `+layout.ts` carries `prerender = true`, so at build time SvelteKit resolves the fetch and serialises the result into each console page. That is why the band has a 2,000-byte ceiling, and any file the same loader fetches inherits the same economics under a different name. **What escapes it is fetching at view time from the query door**, which is what N3 asks for anyway.

**A band-carried list would have undercounted, silently.** `console/band.json` is written by `stages/assemble.py` during a digest run at one moment; the files reach the site at a later one. `digest.yml` has no concurrency group by design, so more shards land in between, and the list would name fewer files than the tree holds. The browser would read twelve shards of sixteen and the chart would be quietly low, with no error and no 404 - the defect-33 class arriving through a new door, and no test could have caught it, because the invariant would have had to hold across two processes at two different times.

**A list generated at build time has the same hole, one step later.** Plan 50 closes it at the source instead: the index task re-lists a raw day directory at every wake and the daily compaction re-lists it again before reading, so no elapsed-time guess stands between the tree and the list. **That re-list is what makes a committed index trustworthy**, and it is what this plan depends on.

| # | File | Writer | Why that writer is safe | Committed |
| --- | --- | --- | --- | --- |
| 1 | `state/compact/<store>/index/<period>.json` | that period's compaction | one period, one task, one writer | **yes** |
| 2 | `state/compact/<store>/<period>/watermark.json` | that period's compaction | same task, written after the data | **yes** |

#### What the build does, which is copy bytes and nothing else

**The staged tree is a verbatim subtree copy, so the published path and the committed path are the same string.** The step copies, for every store whose `StoreConfig.published` names it: the two compact periods, their indexes and their watermarks. Nothing else, and nothing is renamed, merged, re-sorted or regenerated.

| # | What reaches the site | Published address |
| --- | --- | --- |
| 1 | Compact data, both periods | `state/compact/<store>/daily/<YYYY>/<MM>/<DD>.parquet`, `state/compact/<store>/monthly/<YYYY>/<MM>.parquet` |
| 2 | Compact indexes and watermarks | `state/compact/<store>/index/<period>.json`, `state/compact/<store>/<period>/watermark.json` |

**The raw tier is not published, and that is what the per-run compaction buys.** Measured 2026-09-25, one open day of `host-fingerprint` is 30 per-writer shards and about 342 KB as parquet against 21,930 bytes as CSV - 15.1 times larger, because a one-row file of 31 columns is about 9,300 bytes of page, dictionary and statistics overhead. Publishing it would make the smallest span the control offers the worst value in the set: 33 requests and 342 KB to draw 25 rows. **The daily compaction runs at the end of every content run instead**, so the newest compact daily file is at most one run old and a one-day span is two index requests and one file of about 13 KB. The cost is git churn, measured at about 8 KB of history a day per store.

**A verbatim copy is what answers N7, and it is a stronger answer than the earlier design gave.** `frontend/public/machine/<YYYY-MM>.csv` is a projection: the `machine-shard-row` roll-up of one store **joined to** another. A byte copy joins nothing, drops no column and renames nothing, so the committed tree and the published tree can be compared file by file - which the earlier design's renumbered open-day files could not be. N10 already blesses the compact tier as derived and rebuildable.

**The published bundle already runs four address grammars and two of them are unnamed by N8.** `digest/<YYYY>/<MM>/<DD>/digest.json` and `assist/index/<YYYY-MM>.json` are reader-facing, gated and shipped, and N8's replacement list names neither. So N11 cannot bind the published bundle without outlawing them - and it does not try to: it says *every tree under `state/`*. What N8 retires about the projections is the phrase **"in git"**, which is the committed copy and not the address.

**An index carries filenames and periods, and nothing else about them.** No URL, no host, no prefix - the door composes the address from `visuals.asset_base_url`, a constant it already holds, so there is no cell a fetched article could arrive in (Guardrail #11).

#### What the browser reaches for, and why it needs no store list

**Two things get a panel to its data, and both are already in hand.** The base URL is `visuals.asset_base_url` in `config/idhazh.json`, read by [frontend/asset-base.js](../frontend/asset-base.js), which also computes the `connect-src` allow-list from the same value so the address and the browser policy cannot disagree. The store is named by the panel: a machine-mix panel draws machine fingerprints, and that cannot vary without it becoming a different panel.

**So `StoreConfig.published` never reaches the browser**, and there is no second copy of it to keep in step. It decides what the build copies, which is a backend question. **One backend test holds the two sides together**: it reads the console panel sources, collects the store names they name, and asserts every one is published. Same home and same shape as `backend/tests/contracts/test_frontend_vocabularies.py`.

#### What the door does with a date range

A panel asks for a span; the door turns it into whole files. **There are no byte-range requests anywhere in this plan** - a date-range query and an HTTP range request are different things, and only the first is used.

| # | Step |
| --- | --- |
| 1 | **At view time, from the query door - never from `+layout.ts`.** That loader prerenders, so anything fetched there is inlined into every console document. This is the whole reason the address book never went in the band |
| 2 | Fetch only the indexes the span could touch, plus `daily/watermark.json`. A span of 30 days or less touches `daily.json` only, so that is two small requests |
| 3 | For each date in the span take the **coarsest period that covers it** - monthly, then daily - and fetch that file once |
| 4 | Hand every buffer to the engine as one query with a date predicate |

**A date is reachable through exactly one file, and that is an invariant with a test rather than a convention.** A date in two periods is read twice and every number on the panel doubles - the same defect class as the double count filed as 33. Plan 50's row titled **The index task, two compact periods, and the diagram moves into the page** carries the oracle that asserts it, over a fixture store carrying both periods, in one process, at one moment.

**A hole is `unreachable`, never a low chart.** A date at or before the daily watermark that is named in neither index is a hole: the door renders the `unreachable` state with the date in the console and draws nothing. Drawing the rest would be an undercount nobody could see.

**A date after the daily watermark is not drawn at all, and the freshness sentence says so.** No raw file is published, so the newest data a panel can show is the newest compact daily file - at most one content run old, because the daily compaction runs at the end of every run.

**Two periods are what make an arbitrary span affordable.** A 90-day span is one or two monthly files plus 55 daily files instead of 90 daily files. At month grain alone a 39-day span would pull 56 days of data, 44 percent more than requested; at day grain alone a 90-day span is 92 requests.

#### The reader's first request is bounded by config, never by the archive

**This is Guardrail #12 pointed at a reader, and it needs a control rather than an assurance.** An index that gained an entry every month would make a reader's request grow for as long as the project runs.

**The law: an index holds `keep_window` entries and no more. `daily.json` holds at most `daily_keep_days + 31`, `monthly.json` at most `monthly_keep_months`. Two config values a person sets, and no term of elapsed time.**

**Two controls, because the law is not true by itself.** First, a published store may not leave either of its windows null - three windows are null in `config/idhazh.json` today (`item_health_aggregate_keep_months`, `score_archive_keep_months`, `visual_aggregate_keep_months`) and null means never delete. Plan 50's section titled "`config/idhazh_gardener.json`" refuses it at load, along with a `daily_keep_days` below the largest value in `console.span_choices_days`. Second, `page_weight.payload_ceilings_bytes` gains a measured entry for `daily.json`, and `bundle-gate.mjs` checks it every build.

**That second one is a smoke alarm on a bounded thing, not a ceiling a growing store designs against.** It is derived from config and it moves when config moves - which is the distinction the band's 2,000-byte figure could not make, because the band was inlined into every prerendered document and its cap was a guess about that.

**The `+31` in the daily bound is not slack, it is the month-absorption rule.** A month is absorbed whole, so the daily period holds between `daily_keep_days` and `daily_keep_days + 31` days. A bound that said 45 would be wrong for most of every month.

No contract-level cap on an index's length: a second bound over one quantity fires on a legitimate config change rather than on a defect.

**Each file carries its own version, taken from the index entry that names it.** `CompactIndex.entries` already holds `covers`, `rows` and `bytes` per file, and the door appends `?v=<rows>-<bytes>` from that entry. A daily file is written once and never rewritten, so its entry never changes and the browser caches it forever. **A single site-wide stamp would invalidate all 45 daily files every day to deliver one new one** - 596 KB re-fetched to buy 13 KB, 97.8 percent waste for a returning reader. The indexes themselves are fetched `cache: no-store`, because a stale index is what step 3 would act on.

**Nothing new enters git.** The staged copies are created on the runner inside `npm run build`, copied into `build/` by the bundler, uploaded as the Pages artefact and thrown away with the runner. Ten directories under `frontend/static/` are gitignored and published exactly this way today. **Gitignored is not unpublished**, and the ignore line is doing N8's job.

| # | Why concurrent runs cannot collide here | |
| --- | --- | --- |
| 1 | A digest run writes `<unit_id>.parquet` into `state/` and pushes. It never stages and never builds | No job that commits also builds the site |
| 2 | Only `pages.yml` builds, and its build job is `cancel-in-progress: true` | One builder, always |
| 3 | The band and the files it names are produced from one checkout and shipped in one artefact | **Consistency by construction, not by locking** - adding runners upstream cannot break it |

**The band is generated whole on every run and never appended to**, which is how it is already written. An append would be read-modify-write on a shared path, the shape the minted name exists to end.

**`SELECT *` is refused at this door**, not by convention: `columns` is required, non-empty, and the door raises by name on an empty list ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 5).

### 2.3 The d3 house style

`frontend/src/lib/charts/d3/` (new, no other row in either plan touches it). Every export is pure and takes its numbers as arguments; nothing reads a module-scope constant.

| Module | Exports | What it owns |
| --- | --- | --- |
| `scale.ts` | `bandScale`, `linearScale`, `timeScale` | The three scales a console chart may reach for, each reading its range from the frame |
| `axis.ts` | `dateAxis`, `valueAxis` | Tick counts, formats and the label rule, from `config/appearance.json` |
| `ordered-colour.ts` | `orderedRamp`, `RESERVED_GREY`, `ABSENT_HATCH` | The five-step speed ramp, the grey for an absence and the hatch for a known machine with no reading |
| `motion.ts` | `transition`, `prefersReducedMotion` | One duration, one easing, and the reduced-motion branch written once |
| `empty.ts` | `emptyState` | **The four states `waiting.ts` already tells apart**: `loading`, `quiet`, `missing`, `unreachable`. Not three - telling `missing` from `unreachable` is the whole reason that file exists, and a three-state helper silently re-merges the pair it was written to separate |

### 2.4 The appearance knobs these rows read

Every value below is a knob (Guardrail #6). Three exist and two are minted.

| Key | Status | Value | Read by |
| --- | --- | --- | --- |
| `console.machine_colour_stops` | **Exists at 7, becomes 5** | `5` | Row 3's ramp. Five steps because a reader cannot rank more than about five steps of one hue on a bar this thin, and three panels share machine colour so a silent mismatch ships |
| `console.fleet_min_rows` | Exists | `160`, unchanged | Row 3. The knob keeps its job and changes what it switches: below it the panel draws one mark per job instead of switching off |
| `console.fleet_top_kinds` | Exists | `4`, unchanged | Row 3's merge rule |
| `frame.breakpoints_px` | Exists as `[640, 1024, 1400]` | unchanged | Row 2 sticks at `breakpoints_px[1]`. **No second key naming 1024** |
| `console.absent_hatch_degrees` | **New** | `45` | Row 3's hatch for a known machine with no throughput reading |
| `console.span_choices_days` | **New** | `[1, 7, 14, 30, 90]` | Row 2's five-segment control. The five values were a hard-coded list and this is the knob that holds them |
| `page_weight.payload_ceilings_bytes."state/<store>/"` | **New, one per published store** | set in row 3 from the staged store's measured size, with headroom | `frontend/scripts/bundle-gate.mjs` and `backend/tests/contracts/test_page_ceilings.py`. **Per store, not one shared key**: the gate multiplies a directory key by the months a page touches, so one key under-counts a page drawing two stores. It lives in `config/idhazh.json`, not `config/appearance.json` |

**Three page-weight gates fire before the 1 GB site cap and row 3 must clear all three.** `page_weight.cold_console_load_bytes` is 3,400,000 bytes - what a console reader's first load may cost - so **the query engine ships behind a dynamic import**, the same rule the gate already enforces for the on-device encoder. `page_weight.payload_ceilings_bytes` caps each fetched payload and has **no key covering `state/`** today, so a staged store is a payload no gate can see until the key above is minted. And `test_page_ceilings.py` asserts `cold_console_load_bytes` sits between the worst page and that page plus the telemetry ceiling, so adding a payload key moves the assertion and row 3 says which way.

**The alarm, not the cap, is the number an operator sees first.** `PAGES_HARD_CAP_MB` is 1024 and is where the host refuses; `retention.site_budget_mb` is 800 and is where the console prints a warning. Measured to the alarm the runway is about 723 days, not the 959 measured to the cap.

### 2.5 What a panel may not do

Three refusals, each enforced by a test rather than a review note.

| # | Refusal | Enforced by |
| --- | --- | --- |
| 1 | A panel imports the query engine directly | `git grep -l duckdb -- frontend/src` returns exactly one path |
| 2 | A panel builds a URL or a path | `slice()` takes a `StoreName`, never a path |
| 3 | A panel asks for every column | `columns` is required and non-empty, refused by name at the door |

## 3. What was measured, and what is still owed

**No measurement gates any row in this plan.** The seven rules follow from what parquet and the browser cache do, and a reading taken on one machine on one day cannot move one of them ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 7, owner-ruled 2026-09-24).

Two facts are owed before row 3 starts and neither is a gate on a design choice.

| # | Fact | Why it is not a gate | What it decides | Cost |
| --- | --- | --- | --- | --- |
| 1 | Does the published host answer a byte-range request | **Answered 2026-09-25: yes, `206` with `Accept-Ranges: bytes`.** On a binary type the offsets are true; on a text type they are the compressed offsets, which is a trap worth knowing | **Nothing here.** This row issues no range request; whole files are fetched. It is recorded so a later plan does not re-take it. One probe is still owed for the record - whether the host maps `.parquet` to a compressible type - and the tree already carries counter-evidence that it gzips `application/octet-stream` at level 5 | Taken |
| 2 | The query engine asset's transferred bytes | It consumes a budget rather than settling a choice | **Answered 2026-09-25: 7,321,471 bytes brotli on the wire** - 7,124,338 of wasm plus the worker and the loader. See the ceiling ruling below | Taken |

**The engine and the console's load ceiling are not the same instrument, and the row ships.** `page_weight.cold_console_load_bytes` is 3,400,000 bytes and `bundle-gate.mjs` computes it by summing **only the fetched data payload keys**; it never opens a script or a wasm file. Comparing 7.3 MB of code against 3.4 MB of data is a category error. The rule that governs code weight is that anything reached only through a dynamic `import()` is not first-load - and the precedent is not marginal: the on-device encoder is 16.22 MB on the wire and ships under it today.

| # | The condition that makes it legal | Enforced by |
| --- | --- | --- |
| 1 | The engine is reached only through a dynamic `import()` | The `FORBIDDEN` list in `bundle-gate.mjs` gains the engine's module and wasm symbols. **Without that line the rule is a habit rather than a control**, and a careless static import passes review |
| 2 | The panel renders with the engine absent or failed | Row 3's acceptance gates |
| 3 | The shell and the freshness sentence paint before the engine is requested | Row 2 ships the sentence, and row 2 ships first |

Against the site cap, 7.3 MB is 0.71 percent of 1 GB and 0.91 percent of the 800 MB alarm - about seven days of the site's runway, paid once. Carmack confirms it against the built tree in row 3.

**Measured 2026-09-24 and not re-derived:** `state/host-fingerprint/` is 76,306 bytes in 58 files, which is 0.007 percent of the 98.7 MB published site. All of `state/` is about 52 MiB - which is why the staging allow-list is the bound and not a preference: a store joins it by setting `StoreConfig.published`, one store at a time, as its panel migrates.

**The threaded engine build is not available on this platform and nobody should spend a day finding out.** It needs cross-origin isolation, which needs response headers a static host cannot set. The single-threaded build is the pick and the engine's own bundle selector already chooses it when the page is not cross-origin isolated.

---

### Row #1 - The Hardware route stops counting every job twice

- **Scope:** both console readers of `state/host-fingerprint/` settle by key, and the merged-kinds line names the machines it merged. No backend change, no store change, no panel redesign, no parquet and no d3.

**Two defects, one pull request, because they are the same panel's two wrong sentences.**

**Defect 33 - the double count.** Every job writes its machine row in two halves by design: the hardware probe first, the clock after the last item. `ledger.extend_segment` says in its own docstring that it settles nothing and that `day_shards.settled_rows` decides what two rows of one key mean. `frontend/src/lib/server/host-fingerprint.ts` line 145 and `frontend/src/lib/server/machine-counters.ts` line 906 both call `readDayShards`, the plain reader, so both halves reach the page as two job placements - one carrying the machine and one carrying only `job_seconds`, which lands in `Other machines`. Measured 2026-09-24: 41 of 56 per-writer files over fourteen days hold exactly two rows, 41 of 205 rows, about a fifth.

**The merged-kinds line - `drawn as one bar: .`** `PlatformMixPanel.svelte` line 83 reads `series.at(-1)` for the merged names, but `fleet.ts` line 232 merges into an existing series and pushes nothing when the ramp has already absorbed it, so the last series is a real machine whose merged list is empty. An optional chain swallows it. **The merge returns which series carries it rather than the reader guessing it is last** - guessing is what made this invisible, and a second reader would guess again.

- **Files touched:**
  - `frontend/src/lib/server/payload.ts` (section 2.1's key and rule, beside `ITEM_HEALTH_KEY`)
  - `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/server/machine-counters.ts` (both move to `settledDayShards`)
  - `frontend/src/lib/charts/fleet.ts` (the merge names its own series)
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (stops guessing)
  - `frontend/tests/console-machine-data.spec.ts`, `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-cards.spec.ts`
  - `frontend/tests/support/machine-rows.ts` (a fixture day holding one job's two halves)
  - `TODO/20260823-known-defects-plan.md` (defect 33 closes in this commit)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list`, then the selected checks; the browser smoke on `/console/machine` (CLAUDE.md section 12) with zero new `[error]` and zero new `404`. CI runs the full suite.
- **Oracle:** over a fixture day holding one job's two halves, the reader returns **one** row carrying both the machine and the clock, and the merged row's cell count equals the union of the two halves. It cannot settle whether any other store needs the same treatment; section 5.8 of plan 50 is the map for that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Every machine count on the Hardware route drops by about a fifth when this lands. That is the correction, not a regression.** Said here because a reviewer watching four panels fall at once will otherwise read it as the defect | Owner, 2026-09-24 |
  | 2 | The producer is right and is not touched. Two rows of one key is what `extend_segment` is for | Fowler. The same shape as defects 20 and 32 |
  | 3 | Both readers move in one commit. One settled and one raw is worse than two raw, because then two panels on one route disagree and neither says why | Fowler |
  | 4 | The settle rule is a cell merge, not a preference (section 2.1). A preference rule would keep one half and throw the other away, which is the same data loss wearing a different name | Fowler |
  | 5 | **Defect 26 is not fixed here.** The pull request says in one line that the new key is guarded no better than the other two, and defect 26 keeps its own row | Fowler |
  | 6 | The merge fix is structural, not a null guard. `?? []` on the empty list would make the sentence read `0 rarest kinds` and pass every gate | Guardrail #5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Settle in the producer so one row lands | Sound design, wrong defect. The producer cannot know the clock at probe time, which is why there are two halves | Its own plan, and it moves a persisted contract | Fowler |
  | 2 | Sweep every remaining raw `readDayShards` call in one row | Right instinct, wrong row. Each store needs its own ruling on which key settles it and whether the rule is a merge or a preference | A follow-up reading plan 50's section 5.8 map, store by store | Fowler |
  | 3 | Merge this into row 3 | Row 3 is parquet, a browser query and a redraw. A correction buried in a rewrite is a correction nobody can revert alone | Zero; costs the revert | Owner, 2026-09-24 |

---

### Row #2 - The console shell: a stuck tab strip, the span control on it, four named anchors

- **Scope:** the chrome every console route sits in, and **the sentence that says how complete the page is**. No panel changes, no store is read differently, and no data moves.

**Row 2 ships before row 3, and that ordering is the requirement rather than a convenience.** Every chart on the console draws the newest days that **exist**, not the last N days - so when data stops, a chart gains no gap at the right edge. It slides back in time and looks exactly as full as it did yesterday. Reader's verdict on that, 2026-09-24: *"I read a month-old chart, believed it, and closed the tab satisfied."* A page that can go quiet without saying so is worse than useless, so the sentence exists before anything starts fetching.

**The two sentences go in verbatim** and are computable today from fields that already exist - `covers_through`, `generated_at`, `compaction_lag_days`. **No contract changes for this.**

```
Complete to 14:25 today. A run still going is not in this yet.
```

```
Nothing has been recorded since Friday 20 September. Four days are missing.
```

The load-bearing word is **complete**: it is a promise about the left side and an admission about the right, and once it is read a gap is a fact rather than a defect. It is a sentence, not a badge, not a colour and not a grey timestamp.

Ruled by Susan on 2026-09-24. The complaint: the Hardware route is fifteen panels long with no quick way back, and the span control sits at the top where a reader nine panels down cannot reach it.

| # | Element | Ruling | What the reader loses |
| --- | --- | --- | --- |
| 1 | The five-tab strip | **Stuck from `frame.breakpoints_px[1]` up**, about 47 px. Below that it stays where it is | about 47 px of every screen above that width, against fifteen panels of scrolling |
| 2 | `Days shown` | Moves to the trailing edge of the stuck strip at that width and up, as a **compact five-segment control**. Below it, unchanged and full width | the word `days` repeated five times |
| 3 | The tab description line, while stuck | Hidden. It is already hidden below 1400 px and is the anchor's `title` | the one-line summary of the other four routes while scrolled; it returns at the top |
| 4 | Back to the top | An **`On this page` row of the four group names** under the span control, and a `Top` link on each group heading. The four names are read from `console.panel_groups`, never written out | nothing |
| 5 | The site header | Not stuck, unchanged. Its tagline drops on console routes only | the site's one-line self-description on operator routes; it stays on every reading route |
| 6 | The `Console` heading | Not stuck, scrolls away | nothing. It names the surface once, and repeating it every screen is furniture |
| 7 | The days status sentence | Stays under the strip, never inside it | nothing. It is a sentence, not a control |

- **Files touched:**
  - `frontend/src/routes/console/+layout.svelte` (the strip sticks; the span control moves onto it)
  - `frontend/src/lib/components/ConsoleNav.svelte` (the five-segment control, the description line's stuck state)
  - `frontend/src/lib/components/SiteHeader.svelte` (the tagline drops on console routes)
  - `frontend/src/lib/console/band.ts` (the worst-thing fragment the stuck strip carries)
  - `frontend/src/app.css` (the stuck band's tokens)
  - `frontend/tests/console-nav.spec.ts`, `frontend/tests/console-chrome.spec.ts`, `frontend/tests/console-title.spec.ts`
- **Acceptance gates:** the browser smoke on all five console routes at 360 px, 640 px, 1024 px and 1536 px (CLAUDE.md section 12); zero new `[error]` and zero new `404`. Local `npm --prefix frontend run test:changed -- --list`, then the selected checks. CI runs the full suite.
- **Oracle:** at each of the four widths, the stuck strip's measured height equals one row, and each of the four anchors scrolls its heading into view below the stuck band rather than behind it. It cannot settle whether the breakpoint is the right one; decision 4 makes it a knob so it moves without a code change.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A dropdown is refused for the span control.** A menu hides four of five options, and it hides the price at the moment the browser starts fetching its own data | Susan, 2026-09-24 |
  | 2 | **Collapsing the logo on scroll is refused.** It buys zero pixels because the header already leaves the screen, and scroll-linked motion has to be designed twice for reduced motion | Susan, 2026-09-24 |
  | 3 | **Collapsing the band is refused.** The band is what an operator reads on landing; collapsed, he opens a disclosure to learn that yesterday failed. Its worst-thing fragment rides in the stuck strip as one short line instead | Susan, 2026-09-24 |
  | 4 | It sticks at `frame.breakpoints_px[1]`, reusing the existing key. A stuck control must be one band at the width it sticks at: there the five tabs are one row, at 640 px two, at 360 px three | Susan. A second key naming 1024 is the duplicate this project rejects everywhere else |
  | 5 | Four named anchors beat one floating arrow. Fifteen panels sit in four declared groups, and named anchors work with no script at every width | Susan, 2026-09-24 |
  | 6 | This row does not touch `PlatformMixPanel.svelte`. Row 1 owns that file and runs beside this one | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Stick the strip at every width | At 640 px it is two rows and at 360 px three, and a stuck control that reflows eats a third of a small screen | Zero; costs the small-screen reader a third of the page | Susan |
  | 2 | A floating back-to-top arrow | It goes one place. Fifteen panels in four groups need four destinations, and an arrow needs script where an anchor does not | Zero; costs three of the four destinations | Susan |
  | 3 | Merge this into row 1 | Route chrome and a settlement-key change in one pull request, because both happen to be about one route | Zero; costs the independent revert | Fowler |

---

### Row #3 - `host-fingerprint` becomes parquet, is compacted every run, and is published

**This row stops before its first commit and asks** (ESCALATE trigger 6). `frontend/src/lib/server/host-fingerprint.ts` and `frontend/src/lib/server/machine-counters.ts` read `state/host-fingerprint/` as CSV at build time and serve the fourteen panels this plan scopes out. Moving the store to parquet breaks both, and the three defensible answers - a second build-time reader through the same engine, a dual write for one release, or holding the migration until every panel is on the browser door - are different plans. Nothing else in this row is decided until that is.

- **Scope:** `state/host-fingerprint/` moves through plan 50's door; its daily compaction runs at the end of every content run; the store is published and its ceiling is measured. **No browser code, no d3, no panel change.**

**Why this store and not another.** One producer (`telemetry/silicon.py`), 86 files and 96,925 bytes measured 2026-09-25, and the console readers this plan already owns. It is also the store that prices the format honestly: 31 columns, so a one-or-two-row raw shard is about 11,259 bytes of parquet against about 370 bytes of CSV.

**pyarrow moves into `digest.yml`'s hot path, and this row pays for it.** `state/host-fingerprint/` is written by `plan` (1 job), `work` (4 shards) and `assemble` (1 job) on each of five runs a day - **30 jobs a day**. Plan 50's row titled **The payload store, the two roots, and the arrow mapping** made pyarrow an optional extra precisely to keep it out of those installs, and this row gives that back. **That row's owed `ubuntu-latest` install measurement is taken before this row merges, not after**; the real figure decides whether the per-run compaction moves to a job of its own.
- **Files touched:**
  - `backend/idhazh/telemetry/silicon.py` (writes through the door), `backend/idhazh/store/migrate_host_fingerprint.py` (new, one-shot, removal condition on the line that declares it)
  - `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/server/machine-counters.ts` (whatever the escalation rules)
  - `config/idhazh.json` (`store.published` gains `host-fingerprint`; `page_weight.payload_ceilings_bytes` gains the measured `state/compact/host-fingerprint/index/daily.json` entry), `backend/idhazh/contracts/knobs/page_weight.py`, `backend/idhazh/contracts/file_envelope.py` (`StoreName` gains `HOST_FINGERPRINT`)
  - `config/idhazh_gardener.json` (`index-host-fingerprint`, `compact-host-fingerprint-daily`, `compact-host-fingerprint-monthly`), `backend/idhazh/gardener/tasks/__init__.py`
  - `.github/workflows/digest.yml` (the assemble job ends by running the daily compaction for every published store; three job kinds gain `[parquet]`)
  - `frontend/scripts/copy-visuals.mjs` (the copy step - **a second staging script is Guardrail #4**), `.gitignore` (an eleventh line beside the ten payload directories already there)
  - `backend/tests/contracts/test_published_stores_cover_the_panels.py` (new), `backend/tests/store/test_migrate_host_fingerprint.py`, `backend/tests/workflows/test_digest_workflow.py`, `frontend/tests/page-weight.spec.ts`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/store backend/tests/contracts backend/tests/workflows backend/tests/telemetry -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. `ci.yml`'s bundle gate and site-cap measurement both walk the built tree, so both are re-read after the copy step lands. CI runs the full suite.
- **Oracle:** **migration parity and publication reachability.** Every row in the committed `state/host-fingerprint/` CSV tree reads back from the parquet the migration wrote, field for field, no row lost and none invented; and every store a console panel names is in `StoreConfig.published`, asserted over the panel sources. It cannot settle whether the browser can draw it - row 4 does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The migration ships apart from the drawing.** This is the only one-way change in this plan: once it lands the committed CSV is gone. Reverting a d3 panel must not revert a store migration | Fowler |
  | 2 | **The daily compaction runs at the end of every content run**, not once a day. No raw file is published, so a store compacted daily would show the console nothing newer than yesterday. Measured 2026-09-25: five rewrites a day cost about 8 KB of history, against a 157 MiB pack | Carmack |
  | 3 | The ceiling is measured on `daily.json` and set in the same commit. A ceiling guessed ahead of the file is a number nothing checked | Guardrail #10 |
  | 4 | One backend test binds the panels to `StoreConfig.published`. Without it a panel can name a store the gardener does not index and the page fetches an address that 404s | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Migrate and draw in one pull request | Reverting the drawing reverts the store migration, and row 4's own gate - "the panel renders when its store is absent or empty" - cannot be run against a main that lacks this row | One merge cycle | Fowler |
  | 2 | Publish the store without compacting after every run | The console would show nothing newer than the last gardener wake, which for a live operator surface is the whole point missed | Zero; costs the reader today | Carmack |

---

### Row #4 - One panel end to end: the browser fetches the store and draws it in d3

- **Scope:** the browser queries the published store for the columns and days the Platform Mix panel draws; the panel is redrawn in d3; and the house style and query door every later panel uses are written here. **No backend change and no store change** - row 3 did those.

**Why this triple and not another.** The store has one producer (`telemetry/silicon.py`), one console reader, and is 76,306 bytes in 58 files. `frontend/src/lib/charts/fleet.ts` has exactly two importers, against four for the next candidate. And the panel already takes an `svg` prop, which is the server-side renderer telemetry-intent N5 says exists only to serve ECharts - so this one panel is also the first evidence it can go.

**The house style and the query door are the deliverable. The panel is the proof.** A change that ships one good panel and no shared parts has bought one panel and left the next fourteen where they were ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 1, which decides any scope argument inside this row).

#### The panel this row delivers

Ruled by Susan on 2026-09-24 against the panel as it stands, whose verdict was SEND BACK: three of four sufficiency checks fail, two of five spans draw no mark, and the merged-kinds line ships a visible defect.

**The title and the standfirst go in verbatim.**

```
Which machines ran our jobs, day by day
```

```
We do not pick the machine. The platform hands us one at the start of every job,
so a slow week can be the machine rather than the code. One bar is one kind of
machine on one day, over the last {windowDays} days. It counts what we were
given and predicts nothing about the next job. Darker bars are faster machines.
```

**Colour carries speed, ordered, bound to the whole record.** One hue, five steps (`console.machine_colour_stops`), ranked by each machine kind's median prompt throughput from `server_prompt_tokens / server_prompt_seconds` - both columns of `host-fingerprint`, so no second store is needed. Not the confidence hues: a machine that draws slow is a draw, not a failure. **Bound to the whole record and never to the open window**, because a machine must keep its colour when the operator changes the span, and surviving the span control is the one thing this colour has to do. A five-step key chip reads `slower` to `faster`, and every readout row prints an absolute rate, so no share, probability or pie returns.

| Case | Colour |
| --- | --- |
| Machine not recorded | `RESERVED_GREY`, flat, sorted last, outside the ramp |
| Known machine, no throughput reading | `RESERVED_GREY` with `ABSENT_HATCH` at `console.absent_hatch_degrees`, the row reads `no speed reading` |
| `Other machines` | allowed **only** over ramp-adjacent kinds, taking their shared step, named by the band: `3 machines near 30 tokens a second` |
| Kinds that are not ramp-adjacent | do not merge. Merging the slowest into the middle is the one thing an ordered ramp cannot do |

**Cost, stated: three panels share machine colour, so all three move together and all three must print the rate.**

**Under `console.fleet_min_rows` the panel changes shape rather than switching off.** One mark per job - one column a day, one dot a job, coloured by machine - so all five spans draw something. The threshold's reason survives and is why this works: a bar over small counts reads as `this much` and invites a rate, where a dot per job reads as `these ones` and cannot, because every mark is an individual a reader can point at. **The sentence quoting `160` goes**: an internal knob is not a fact a reader can act on (CLAUDE.md section 0b).

**The readout stays a vertical column and moves beside the plot.** It carries names and counts, and counts compare down a right-aligned column in one eye movement. What was wrong was its position: the plot is 760 px inside a 1216 px content box at a 1536 px viewport, with 456 px standing empty beside it.

**What this row draws, in Susan's rank order:** say the machine is not recorded and sort that last, outside `Other machines`; drill through from a day or a mark to the jobs behind it, naming run, job, shard, machine, seconds and rate; one shape switch splitting by `job`; the speed ramp; the unit marks under the threshold; and last, a full-record context band showing where the open window sits.

- **Files touched:**
  - `backend/idhazh/telemetry/silicon.py` (writes through plan 50's door), `backend/idhazh/contracts/host_fingerprint.py` (`version` stamp, one `changelog` line)
  - `backend/idhazh/ledger.py` (`SegmentLedger.HOST_FINGERPRINT` leaves `write_segment`), `backend/idhazh/paths.py`
  - `frontend/scripts/copy-visuals.mjs` (the copy step joins the one that already stages into `frontend/static/`; **a second staging script is Guardrail #4**), `.gitignore` (an eleventh line beside the ten payload directories already there)
  - `frontend/scripts/build-canary.mjs` (the copy step reads its `STATE_ROOT` switch and **fails loudly when the root is missing**, because an empty store and a working store both render)
  - `frontend/scripts/bundle-gate.mjs`, `backend/tests/contracts/test_page_ceilings.py` (the new `state/` payload ceiling)
  - `frontend/package.json`, `frontend/package-lock.json`
  - `frontend/src/lib/data/store.ts` (new, section 2.2 - **the only module that imports the engine**)
  - `frontend/src/lib/charts/d3/scale.ts`, `axis.ts`, `ordered-colour.ts`, `motion.ts`, `empty.ts` (new directory, no other row in either plan touches it)
  - `frontend/src/lib/charts/fleet.ts` (the option builder becomes a d3 draw), `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, `frontend/src/lib/server/host-fingerprint.ts`
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (section 2.4)
  - `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-data.spec.ts`, `frontend/tests/console-cold-load.spec.ts`
  - `docs/architecture/publishing/console-charts.md`, `docs/architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md` (a scope clause on its two rejected-alternative rows, which were ruled for the search vector file and not for slicing a telemetry store)
- **Acceptance gates:** the browser smoke on `/console/machine` (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, **the panel still renders when its store is absent, empty, or when the engine fails to start**. `ci.yml`'s bundle gate and site-cap measurement both walk the built tree, so both are re-read after the copy step lands. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/telemetry backend/tests/contracts -q`. CI runs the full suite.
  - **No measurement gates this row.** Two facts are owed and neither is a gate: whether the published host answers a byte-range request, which decides how the store is published rather than how it is read, and the engine asset's transferred size, which the site-cap budget consumes (section 3).
- **Oracle:** given a recorded `slice()` response for one fixture day, the d3 panel draws one mark per machine kind per day, with the kinds in median-throughput order, the unrecorded kind last and outside the merged group, and every readout row carrying an absolute rate. **It is not a comparison against the ECharts panel**: this row rewrites `fleet.ts` from an option builder into a draw, so the old panel does not survive the commit, and the row's own scope changes the colour count, the shape under the threshold, the merge rule and the readout position - so "same colours, same labels" would be false by design. It cannot settle whether the drawing is good enough to ship; Susan rules that (CLAUDE.md section 14).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | d3 is the drawing library, and this row writes the house style rather than one chart | Owner, 2026-09-24, on N5 |
  | 2 | **`@duckdb/duckdb-wasm` is the reader.** A panel queries the store for the columns and days it draws instead of downloading it. **This is how every panel reads every store** - not a rule for the large ones, and no store has a carve-out. The engine is fetched once and cached; a store would be fetched on every view by every reader, and that asymmetry holds at any size | Owner, 2026-09-24 |
  | 3 | **The single-threaded build is the pick.** The threaded one needs cross-origin isolation, which needs response headers a static host cannot set. The engine's own bundle selector already chooses correctly | Carmack. Written down so nobody spends a day discovering it |
  | 4 | One panel, not the route. `/console/machine` draws fifteen panels and prerenders; a row that moved it whole would carry `item-health` at 8.5 MB, fourteen more panels and the prerender decision, and would prove no more about d3 than one panel does | Fowler |
  | 5 | ECharts stays installed. This row moves one importer of fifteen; uninstalling is the last charting row's work | Fowler |
  | 6 | The d3 modules are the narrow ones (`d3-selection`, `d3-shape`, `d3-axis`), never the `d3` meta-package. `d3-array@3.2.4` and `d3-scale@4.0.2` are already installed | Carmack, Guardrail #8 |
  | 7 | **Landing d3 now and the engine later is refused.** That exact trade was taken on 2026-09-24 and reversed the same day: a reader designed around the smallest panel guarantees a second reader arrives with the first large one. The cost of deferring is one extra pass over one panel, and it is the pass that has to re-decide the reader under time pressure | Owner, 2026-09-24 |
  | 8 | `console.machine_colour_stops` moves from 7 to 5 in this row. Three panels share machine colour, so a silent mismatch ships | Susan |
  | 9 | **N9 binds a telemetry payload in a tree under `state/`, not a published address.** Its replacement clause names a parsed payload name and its last three words are "nothing reads it", which a file whose job is to be read is not. The published address is computed from the month and the band | Fowler, on the owner's 2026-09-24 ruling |
  | 10 | **Every index is generated whole by its own single writer and never appended to**, and none of them is generated by the build. An append is read-modify-write on a shared path, the shape a minted name exists to end | Owner, 2026-09-24 |
  | 11 | The copy step joins the existing build chain between `copy-visuals` and `vite build`, and is not a new script. A second staging script is Guardrail #4, and the site-weight gate measures `build/` after `vite build`, so a step outside the chain would have the gate measuring a tree without the new bytes | Carmack |
  | 12 | **The reader sees the newest compact daily file, which is at most one content run old.** No raw file is published, so `digest.yml`'s assemble job ends by running the daily compaction for every published store. The compaction serves git; the build serves the reader; and the two now move together | Fowler, on Carmack's measurement of 2026-09-25 |
  | 13 | **An index holds at most its own keep-window of entries - `daily_keep_days + 31`, `monthly_keep_months`.** Two config values, no term of elapsed time. Held by two controls: a published store may leave neither window null, and a measured ceiling that moves when those values move | Owner, 2026-09-25 |
  | 14 | **A date is reachable through exactly one file.** The door takes the coarsest period that covers a date, and plan 50's row titled **The index task, two compact periods, and the diagram moves into the page** carries the oracle that asserts it over a fixture holding both - one process, one moment. Under the band it would have had to hold across two processes at two times, which no test can assert | Fowler |
  | 15 | **The index is fetched by the query door at view time, never by `+layout.ts`.** That loader prerenders, so anything it fetches is inlined into every console document and grows with the published stores. This is the reason the address book is not in the band, and it is sharper than the byte ceiling that prompted the move | Fowler, on the owner's 2026-09-25 ruling |
  | 16 | **One index per period, written by that period's own compaction.** Never one file for many writers: two periods are two tasks | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `RecordGates` on `/console/judgement`, with `targetbar.ts` | Simpler drawing, but `targetbar` has four importers against `fleet`'s two, so the blast radius is larger for a smaller proof | Its own row later, once the house style exists | Fowler |
  | 2 | Keep the build-time read and swap only the drawing | It proves N5 and leaves N2 and N3 where they were, so the same panel gets done twice | Zero now; costs a second pass over one panel | Owner, 2026-09-24 |
  | 3 | Swap the drawing for every ECharts panel here | Fifteen importers, five routes and the server-side renderer in one pull request, before any house style has been reviewed | Its own plan | Fowler |
  | 4 | Delete `waterfall.ts` and `donut.ts` here | They are ECharts modules with no importer anywhere in `frontend/src`, found 2026-09-24 - real dead code and a free deletion, but not this row's question | A one-line change of its own | Fowler |
  | 5 | Commit the store's published copy under `frontend/public/` | Satisfies neither N7 nor N8, and it is the thing N8 exists to end | Zero; costs both intents and a merge driver | Carmack |
  | 6 | Serve the store from the repository over raw content | Zero published bytes, and cross-origin requests do work. But this project's own prune force-pushes `main` on a schedule, so a commit-pinned address stops resolving and a branch-pinned one changes under a reader mid-session | Zero; costs the reader a broken page after every prune | Carmack |
  | 7 | An index committed into `state/` and rewritten by **every run** | It would be a shared mutable path: every run rewrites it, two runs rewrite it at once, and the push race and the merge driver both return. **The indexes this plan reads are not this**: each has exactly one writer, and the raw day index is written only once the day is beyond every writer's reach | Zero; costs the race back | Owner, 2026-09-24 |
  | 8 | Compute a raw file's name from `(dataset, tier, covers_date)` so both sides derive it | Elegant, and **it dies on N6 rather than on derivability**. A backfill can add rows to a closed day, so a computed name means different bytes at the same path - N6 broken at the one place it is load-bearing. The compact periods do take a derivable name, because there the writer is single and the period is the name | Zero; costs N6 | Fowler |
  | 9 | Keep the address book in `console/band.json` | It was the answer for a day. Two things killed it: `+layout.ts` prerenders, so the band is inlined into every console document and that is what its 2,000-byte ceiling was really paying for; and the band is written during a digest run while the files are staged later, so with overlapping runs its open-day list would name fewer files than exist and the chart would be quietly low | Zero; costs a silent undercount and a per-document cost that grows | Owner, 2026-09-25 |
  | 10 | Have the build merge today's shards into one file at a derivable address | It needs a parquet writer in the build, and the indexes exist for the older periods regardless - so it is a second mechanism for a problem the first one already solved | A new build dependency | Fowler, Guardrail #4 |
  | 11 | Have the browser probe `00.parquet`, `01.parquet` until a 404 | A 404 stops being a defect signal and becomes a loop terminator, so a genuinely missing file reads as a normal end | Zero; costs the ability to tell an absence from a fault | Fowler |
  | 12 | A single published address book naming every store | It needs a writer, and the only entity that sees every store at once is the build - which puts the list back one step from the tree it describes. It also buys nothing: a panel names its own store, and each store's indexes sit at a path the browser can compute | Zero; costs a mechanism | Owner, 2026-09-25 |
  | 13 | Publish the open raw days and let the browser read them | **It makes the cheapest span the worst value in the set**: one open day of `host-fingerprint` is 30 per-writer shards, 33 requests and about 342 KB to draw 25 rows - 15.1 times the source bytes, because a one-row file of 31 columns is mostly column overhead | Zero to take, and it costs the reader 29 requests on every view. Measured 2026-09-25 | Carmack |
  | 14 | Publish fewer columns so the raw tier is affordable | The published tree stops being a byte copy, which is this plan's strongest N7 argument, and a second projection is the thing N7 exists to retire | Zero; costs the byte-copy property | Fowler |
  | 15 | Compact once a day rather than after every run, and accept a day-old console | **It buys git about 6 KB a day and costs the reader today's data entirely**, because no raw file is published. Git delta-compresses these rewrites: measured 2026-09-25, one period-file rewrite is 1,649 bytes packed, so five a day is about 8 KB. The "roughly 360 MB" figure an earlier draft used was arithmetic on a false premise and is 33 times too high | About 8 KB of history a day per store | Carmack, 2026-09-25 |
  | 16 | Ask the host's own contents API for a directory listing | A service rather than a static asset, rate-limited per address, untestable offline, and it breaks if the repository is renamed. Guardrail #1 says a design must not need one | Zero; costs Guardrail #1 | Carmack |
  | 14 | Write an `index.html` into each month directory so the host lists it | One round trip per store-month instead of one in total, plus 234 extra files | Zero; costs a round trip per month | Carmack |

- **What the build copies, which closes this row's old ESCALATE.** For every store whose `StoreConfig.published` names it, the step copies the three compact tiers, their indexes, their watermarks, and the raw days past the daily watermark with their own day indexes - **verbatim, into the same relative paths**. It renames nothing, merges nothing and generates nothing. `state/` in the repository stays the only source (N7) and nothing production lands under `frontend/` in git (N8), because the staged tree is gitignored and rebuilt each build. **The question of how the browser reaches the bytes is settled and is no longer an escalation.**

- **This plan declares no new contract.** The three shapes it reads - `CompactEntry`, `CompactIndex` and `Watermark` - are declared by plan 50's section titled "The shapes a worker must not invent", committed by the gardener and read here. **The frontend's copy is hand-written in `frontend/src/lib/data/store.ts` and bound by a backend test**: `backend/tests/contracts/test_frontend_index_shapes.py` reads that module, collects the interfaces, and asserts each names exactly the fields the Pydantic model declares, in order, with the same type - the shape `test_frontend_field_set.py` already uses. **`ConsoleBand` gains nothing and is not touched.**

- **One test binds the panels to the published list.** It reads the console panel sources, collects the store names they name, and asserts every one is in `StoreConfig.published`. Without it a panel can name a store the gardener does not index and the page fetches an address that 404s.

- **The published index gets a hand-written TypeScript type, not a model.** Guardrail #3 scopes to a persisted payload a later run reads; this one is gitignored, rebuilt every build and read only by that build's own bundle. One spec reads a built index and binds the type to the staging script.

## Dependent plans

- `TODO/20260924-50-idhazh-gardener-plan.md`, the row titled **The payload store, the two roots, and two stores moved to parquet**, is row 3's predecessor. Nothing else in that plan is a predecessor here.
- `TODO/20260823-known-defects-plan.md`, defect 33, closes in row 1's pull request.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan lays stones for.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every row here is built to.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
