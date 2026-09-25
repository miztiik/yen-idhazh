# Plan 51 - The console fetches and draws its own data

**Last Updated**: 2026-09-26

**Level**: 5 (CLAUDE.md section 6). Row 3 decides whether `state/` reaches a browser, which is a publishing contract, and sections 2.6 to 2.10 are a design contract fifty-one panels are built to. Rows 1 and 2 are Level 3 and Level 2 and carry no contract change beyond one copied settlement key.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3 and N5 - the browser queries the store for the slice it draws, fetches at view time, and d3 draws it. **Contract**: section 2 declares every shape, key, signature and config literal these three rows need. **Code**: the three rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 - rows 1 and 2 share no source file, and so do rows 5 and 6; merge each pull request before dispatching the next; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The Hardware route counts every job twice, its span control sits fifteen panels above the reader who wants it, and every chart on the console is drawn from data baked into the page by the build. This makes one panel prove the whole chain - query the store in the browser, draw it in d3 - and writes the vocabulary, the hover strip and the gates the other fifty follow. |
| Hard scope - in | - `state/host-fingerprint/` is read settled, so a job counts once.<br>- The five-tab console strip sticks, and the span control rides on it.<br>- `state/host-fingerprint/` becomes parquet and reaches the browser, which queries it for the columns and days one panel draws.<br>- `frontend/src/lib/data/` holds the one query door every later panel uses; `frontend/src/lib/charts/d3/` holds the house style every later chart uses. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A tenth prerendered route, or retiring an existing one.<br>2. A charting library that is not d3.<br>3. A new committed payload under `frontend/public/`.<br>4. A measured figure that contradicts section 3.<br>5. Any change to `ConsoleBand` beyond the one additive field row 7 declares - it is the payload every console route fetches first.<br>6. **A chart type that is not one of the nine in section 2.6.** A tenth is a design question, not an improvisation.<br><br>**"How the browser reaches the bytes" was trigger 1 and is settled**, 2026-09-25: `state/` carries its own indexes, declared by plan 50's section titled "The shapes a worker must not invent" and committed; the build copies the published stores' compact periods verbatim into gitignored `frontend/static/state/` and generates nothing.<br><br>**The build-time readers were a trigger here and are now plan 50's.** Four modules under `frontend/src/lib/server/` open these stores as CSV and serve every panel the console has; moving the stores breaks all four. That escalation sits on plan 50's row titled **The three stores `work.py` writes become parquet**. |
| Chosen strategy | Correct the number first, move the chrome second, change the grammar last. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The other fifty panels, on all five console routes | Two grammars coexist: one panel queries parquet and draws in d3, fifty read CSV at build time and draw in ECharts. `echarts@^5.6.0` stays installed with sixteen importers | The route plan, which starts from the vocabulary, the strip and the gates in sections 2.6 to 2.9, and from the panel-by-panel contract in section 2.10. **Rows 4 to 7 exist to make that plan cheap, not to be it** |
| Panel ids on `/console/model/`, `/console/voices/` and `/console/judgement/` | Those three routes import neither `Panel.svelte` nor `PanelGroup.svelte`, so they draw no `data-console-panel-id` and **no gate and no capture can reach them**. Row 6's judged set is 26 panels on two routes, and a panel on the other three ships unseen | A route-plan row that wraps those three routes' sections in `Panel.svelte` and adds their route keys to `console.panel_groups`. It is a prerequisite of a full capture, not a follow-up |
| Three `/console/` panels nested inside another panel's body | "Reading the prompt", "Writing the summary" and "How much of each prompt was already in memory" are `<Panel>` elements inside another panel and carry no id, so the capture never sees them | A route-plan row that either gives each an id and its parent's group, or takes its `Panel.svelte` wrapper away. It is one or the other, not both |
| Taking any route off `export const prerender` | Nine files under `frontend/src` keep it. Row 7's panel fetches after mount on a page that still prerenders, which is legal and is what lets one panel prove N3 without moving a route | The plan that moves a whole route, which owns the first-paint and no-script questions for every panel on it |
| Retiring the nine payloads under `frontend/public/` | Telemetry-intent N7 and N8 get no stone here. `frontend/public/machine/<YYYY-MM>.csv`, the `machine-shard-row` roll-up of `host-fingerprint` joined to `item-health`, keeps being published | The same whole-route plan. Retiring a published payload needs every reader moved first |
| The throughput spread per machine kind | The Platform Mix panel says what we were given and not how much one machine varies | It is the machine cards' and the shard board's question. Row 7's readout links to them |
| Fixing defect 26, the settlement-key guard that reads one constant twice | Row 1 adds a third key to a guard that cannot fully check it, and says so in the pull request | Its own row. A pull request that fixes a guard and the thing the guard was meant to catch leaves neither fix with an independent witness |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star and sits above this plan (CLAUDE.md section 0d). The seven rules a panel obeys are [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md).

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N1 | Parquet at rest, CSV retired | **Not here.** Plan 50 moves all four stores; row 3 publishes them |
| N2 | The browser queries the parquet itself | **Stone laid by row 7.** One module owns the engine and every later panel queries through it |
| N3 | The browser fetches its own data at view time | **Stone laid by row 7**, on one panel that fetches after mount |
| N4 | Prerendering is an anti-pattern | **Not here.** Nine files keep `export const prerender`, and ESCALATE trigger 1 stops a row adding a tenth |
| N5 | d3 is the only charting library | **Stone laid by rows 4 to 6**, which write the nine chart types, the hover strip and the ten gates, and by row 7, which moves one importer of fifteen |
| N6 | One writer per path | **Inherited** from plan 50's door |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Stone laid by row 3.** What reaches the site is the store itself, copied unchanged and gitignored, so it cannot say anything `state/` does not. **The six projections that can are retired by the route plan**, each in the pull request that moves its last reader |
| N9, N10, N11 | The name, the two roots, the one shard pattern | **Inherited** from plan 50's door. This plan mints no naming rule of its own |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The Hardware route stops counting every job twice | - | A | PENDING | - | - | - |
| 2 | The console shell: a stuck tab strip, the span control on it, four named anchors | - | A | PENDING | - | - | - |
| 3 | The four stores the console reads are published | plan 50's rows titled "The index task, two compact periods, and the diagram moves into the page", "The three stores `work.py` writes become parquet" and "`span-rollup` becomes parquet" | B | PENDING | - | - | - |
| 4 | The chart vocabulary and the house style, with no panel moved | - | B | PENDING | - | - | - |
| 5 | One readout strip, every chart, and hover a keyboard can reach | 4 | C | PENDING | - | - | - |
| 6 | The ten sufficiency gates and the panel capture group | 4 | C | PENDING | - | - | - |
| 7 | One panel end to end: the browser fetches the store and draws it in d3 | 1, 2, 3, 4, 5, 6 | D | PENDING | - | - | - |

**Two pairs run two-wide and both were checked by diffing their `Files touched` lists.** Rows 1 and 2 share nothing: row 1 holds `payload.ts`, `host-fingerprint.ts`, `machine-counters.ts`, `fleet.ts`, `PlatformMixPanel.svelte` and `machine/+page.server.ts`; row 2 holds `+layout.svelte`, `ConsoleNav.svelte`, `SiteHeader.svelte`, `band.ts` and `app.css`. **Rows 5 and 6 both edit `config/appearance.json`** - row 5 the `chart.readout_max_share` value, row 6 the `console.panel_groups` object - so whoever lands second rebases that one file by hand; nothing else is shared.

**Rows 4, 5 and 6 are the deliverable and row 7 is the proof.** Sections 2.6 to 2.9 declare all three, so none of them invents anything. Row 4 writes modules and no panel, which is why it can run beside row 3.

**The seam is after row 6, and the reason is a type rather than a preference.** Row 5 replaces one exported type: `DayReadout` has nine producers and thirteen consumers under `frontend/src`, so **there is no intermediate commit where half the console is on the new shape and the tree compiles**. That is why it cannot be split by panel, and why its `Files touched` runs to twenty-two paths rather than four. Row 4 alone would ship a vocabulary nothing has exercised, which is a rule that rots with no page going red.

**Row 3 publishes; it migrates nothing.** Plan 50 moves all four stores, because one module writes three of them and two plans editing that file would collide. What this row adds is the copy step, the allow-list, the measured ceiling and the test that binds a panel's store to that list. It reverts to nothing.

**Rows 1 and 7 share three files** - `fleet.ts`, `PlatformMixPanel.svelte` and `machine/+page.server.ts` - which is why row 7 waits on row 1 rather than running beside it.

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

**Cost, one store, per span the control offers.** `console.window_presets` is `[1, 7, 14, 30, 90]`. At `daily_keep_days: 45` a span of 30 or less is served entirely from the daily period; only the 90-day span reaches a monthly file.

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

**What answers N7 is that the published file is the store, and that the projections go.** The test is not whether a copy is byte-identical - it is whether a published file can say something `state/` does not. A copy cannot, however it is packed. **`frontend/public/machine/<YYYY-MM>.csv` can**: it joins `host-fingerprint` to `item-health` rows summed per shard, so it carries values neither store holds alone and either store can move underneath it. That is the shape N7 exists to retire, and the route plan deletes it along with five more - about 4.1 MB and six directories - each in the pull request that moves its last reader. N10 already blesses a compact period as derived and rebuildable.

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

**Two controls, because the law is not true by itself.** First, a published store may not leave either of its windows null - three windows are null in `config/idhazh.json` today (`item_health_aggregate_keep_months`, `score_archive_keep_months`, `visual_aggregate_keep_months`) and null means never delete. Plan 50's section titled "`config/idhazh_gardener.json`" refuses it at load, along with a `daily_keep_days` below the largest value in `console.window_presets`. Second, `page_weight.payload_ceilings_bytes` gains a measured entry for `daily.json`, and `bundle-gate.mjs` checks it every build.

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
| `console.machine_colour_stops` | **Exists at 7, becomes 5** | `5` | Row 7's ramp. Five steps because a reader cannot rank more than about five steps of one hue on a bar this thin, and three panels share machine colour so a silent mismatch ships |
| `console.fleet_min_rows` | Exists | `160`, unchanged | Row 7. The knob keeps its job and changes what it switches: below it the panel draws one mark per job instead of switching off |
| `console.fleet_top_kinds` | Exists | `4`, unchanged | Row 7's merge rule |
| `frame.breakpoints_px` | Exists as `[640, 1024, 1400]` | unchanged | Row 2 sticks at `breakpoints_px[1]`. **No second key naming 1024** |
| `console.absent_hatch_degrees` | **New** | `45` | Row 7's hatch for a known machine with no throughput reading |
| `console.window_presets` | **Exists as `[1, 7, 14, 30, 90]`** | unchanged | Row 2's five-segment control reads it. **No second key naming the same five values** - an earlier draft minted `console.span_choices_days`, which is this knob under another name, and all five console routes plus `/archive/` read the existing one |
| `page_weight.payload_ceilings_bytes."state/compact/<store>/index/"` | **New, one per published store** | set in row 3 from the measured `daily.json`, at least twice it per the field's own rule | `frontend/scripts/bundle-gate.mjs` and `backend/tests/contracts/test_page_ceilings.py`. **The key names the one directory that holds files directly**: `payloadsFor` does not recurse, so a key naming `state/compact/<store>/` returns nothing and fails the gate by name. It lives in `config/idhazh.json`, not `config/appearance.json` |

**Three page-weight gates fire before the 1 GB site cap and row 3 must clear all three.** `page_weight.cold_console_load_bytes` is 3,400,000 bytes - what a console reader's first load may cost - so **the query engine ships behind a dynamic import**, the same rule the gate already enforces for the on-device encoder. `page_weight.payload_ceilings_bytes` caps each fetched payload and has **no key covering `state/`** today, so a staged store is a payload no gate can see until the key above is minted. And `test_page_ceilings.py` asserts `cold_console_load_bytes` sits between the worst page and that page plus the telemetry ceiling, so adding a payload key moves that two-sided assertion - **which is why the key, the number and the assertion move in one commit, row 3's.**

**`cold_console_load_bytes` cannot see a day-grained fetch, and row 3 says so in one line.** `bundle-gate.mjs` computes `heaviest x copies` where `copies` is a count of months; the door fetches days. Row 3 sets the store's payload ceiling on `index/daily.json` only, and **the fetched-data total is bounded by `console.window_presets`' largest value against `daily_keep_days`** - which is the bound `test_page_ceilings.py` is given, in the same commit.

**The alarm, not the cap, is the number an operator sees first.** `PAGES_HARD_CAP_MB` is 1024 and is where the host refuses; `retention.site_budget_mb` is 800 and is where the console prints a warning. Measured to the alarm the runway is about 723 days, not the 959 measured to the cap.

### 2.5 What a panel may not do

Three refusals, each enforced by a test rather than a review note.

| # | Refusal | Enforced by |
| --- | --- | --- |
| 1 | A panel imports the query engine directly | `git grep -l duckdb -- frontend/src` returns exactly one path |
| 2 | A panel builds a URL or a path | `slice()` takes a `StoreName`, never a path |
| 3 | A panel asks for every column | `columns` is required and non-empty, refused by name at the door |

### 2.6 The chart vocabulary - nine types, and a tenth is an escalation

Ruled by Susan, 2026-09-26. **A panel that needs a type not on this list stops and asks.** The five mark shapes already ruled in [docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md) are marks **inside** these types, not types; nothing there is superseded.

**Each type is one `.ts` module returning geometry and one `.svelte` component that draws it.** The `.ts` module is pure and takes every number as an argument (section 2.3); the component owns the DOM. Where a type's drawing half already lives in an existing component, the table names it and no new component is made.

| # | The name a worker types | The signature | The question it answers | Right when | Wrong when | Drawn by |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `rankedList` | `(rows: readonly {label: string; value: number; segments?: readonly {label: string; value: number}[]}[], opts: {max?: number}) => RankedGeometry` | which one is worst | a bounded set of named things, one magnitude each, and the reader acts on the name | the question is "what is changing" - that is type 2 | `RankedList.svelte`, **markup not SVG**: seventy rows would be seventy chart instances, and markup still draws with no script |
| 2 | `dateSeries` | `(series: readonly {label: string; token: string; points: readonly {date: DateStamp; value: number \| null}[]}[], opts: {frame: Frame; stacked?: boolean}) => SeriesGeometry` | what is changing | a value per day or per run, one to five series, compared across time | the set is not ordered by time. A run mix drawn as a trend invites a cause nothing measured | `DateSeries.svelte`. Ticks from `dayTicks` in `frontend/src/lib/charts/frame.ts`, **never from an axis generator** |
| 3 | `distribution` | `(values: readonly number[], opts: {frame: Frame; rules?: readonly {at: number; label: string}[]}) => BinGeometry` | how bad does it get | one quantity over many items, the tail is the point, the spread crosses a decade | fewer than `console.fleet_min_rows` values. A histogram of eight readings is a claim | `Distribution.svelte`. Cumulative curve on a second axis, 0 to 100 |
| 4 | `partsOfOne` | `(rows: readonly {label: string; parts: readonly {label: string; value: number}[]}[], opts: {order: readonly string[]; overlapping?: boolean}) => PartsGeometry` | what is this one thing made of | components of a single total, fixed order, a handful of rows | the components do not sum to the total - set `overlapping` and they become brackets anchored at the origin, per the memory-held rule | `PartsOfOne.svelte`, segments as markup not paths |
| 5 | `tileStrip` | `(tiles: readonly {date: DateStamp; state: 'quiet' \| 'fired' \| 'absent'; reading?: number}[], opts: {thresholds: readonly [number, number]}) => TileGeometry` | was it quiet, and which day did it fire | a reading that is zero or absent on most days | the reading has a useful value axis every day - that is type 2 | `TileStrip.svelte`. **Three states, never two.** Both thresholds from config |
| 6 | `paired` | `(rows: readonly {label: string; before: number; after: number; attempts: number}[]) => PairedGeometry` | what did the change move | two measurements of the same measures, and the reader wants the direction | either side is below `console.min_attempts_for_rate` - the row draws nothing and prints why | `Paired.svelte`, through `swapScale` in `frontend/src/lib/charts/series.ts`. Symmetric about no change, minimum half-width |
| 7 | `overlapTimeline` | `(items: readonly {id: string; source: string; shard: number; startMs: number; steps: readonly {label: string; ms: number}[]}[]) => TimelineGeometry` | what was happening at the same time | work items on a real clock, where the queue is the finding | the reader wants totals. A timeline is the worst shape for a sum | **`RunTimelinePanel.svelte`, which keeps its own hand SVG** and is this type's first and only caller. No new component |
| 8 | `flow` | `(stages: readonly {label: string; arrived: number; left: number; drops: readonly {label: string; count: number}[]}[], opts: {narrow: boolean}) => FlowGeometry \| SteppedGeometry` | where did they go, and where did they leave | a funnel of four or fewer stages with named drops | never - it returns the stepped shape below `48rem` from the same call | `Flow.svelte`, `d3-sankey` above `48rem` and a markup list below |
| 9 | `pairedScatter` | `(points: readonly {label: string; x: number; y: number}[], opts: {frame: Frame}) => ScatterGeometry` | do these two move together | at least `console.fleet_min_rows` rows **and** `console.bandwidth_min_kinds` distinct subjects | below either floor. Two points define a line, so a scatter of two is a claim. It draws nothing and names the floor it missed | `PairedScatter.svelte`. **No trend line, ever** - a fitted line is a verdict nobody agreed to |

**Every geometry type is exported from its own module and every one has a no-data answer**: the `.ts` returns `null` and the component renders `emptyState` (section 2.3). A type that returns an empty geometry rather than `null` draws an empty frame, which gate 8 fails.

**Refused, so nobody re-argues them:** pie, donut over anything but a single completed share, gauge, dial, radar, treemap, word cloud, bubble, anything in three dimensions, and a bar chart of a rate below `console.min_attempts_for_rate` placements. **The reader loses nothing**: each answers a question one of the nine answers better, and six percent on a dial is one pixel of arc.

**The packages, and the rule that keeps them small.**

| # | Package | For | Status |
| --- | --- | --- | --- |
| 1 | `d3-array` | binning, quantiles, extent | installed |
| 2 | `d3-scale` | every scale above | installed |
| 3 | `d3-shape` | `line`, `area`, `stack` for types 2 and 4 | **to add** |
| 4 | `d3-sankey` | type 8 only | **to add, and only if type 8 clears its own bytes** |
| 5 | `d3-axis` | - | **refused.** It would fork the measured label-thinning rule `dayTicks` owns, and that rule exists because four console axes once drew their dates on top of each other |
| 6 | `d3-selection`, `d3-transition` | - | **refused.** Svelte owns the DOM |
| 7 | `d3-scale-chromatic` | - | **refused.** Colour comes from `--chart-1` to `--chart-8` and the tint tokens. A library ramp collides with the confidence ramp within a month |

**On this console d3 is a maths library, not a drawing library.** A worker who writes `select()` inside a Svelte component has left the vocabulary.

### 2.7 The readout strip - one module, every chart, and hover that a keyboard can reach

**The console has two hover systems today and one of them is invisible.** `frontend/src/lib/components/ChartReadout.svelte` is the ruled one, a fixed strip below the plot. **Twenty-two marks across nine files use a native `title=` instead**, which no keyboard reaches, no thumb reaches, no theme styles and no test reads - eight in `ShardBoard.svelte` and fourteen more in `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `DiskReadsPanel.svelte`, `ProcessorLostPanel.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte`, `console/+page.svelte` and `voices/+page.svelte`. **That is the defect this section closes.**

**One module owns it**, `ChartReadout.svelte`, fed by one builder, `frontend/src/lib/charts/readout.ts`. Every chart calls the builder and passes its result. No chart composes its own strip and no chart sets `title=` on a mark.

**`DayReadout` in `frontend/src/lib/charts/frame.ts` is replaced by `Readout`, and `readoutCapStyle` moves to `readout.ts` with it.** Nine modules produce `DayReadout` today and thirteen components consume it; **all twenty-two move in row 5's single commit**, which is why that row cannot be split by panel - there is no intermediate commit where half the console is on the new shape and the tree compiles.

```ts
/** What a chart hands the builder. */
export type ReadoutInput = {
	type: ChartType;
	columns: readonly string[];          // the label of each hoverable column, in draw order
	series: readonly {
		label: string;
		swatch: string | null;
		values: readonly (number | null)[];
	}[];
	format: (value: number) => string;   // the one place a number becomes reader text
	notMeasured: string;                 // from the same vocabulary as the panel's empty state
	resting: 'newest' | 'median' | 'first';
};

/** One row of the strip. A row with no swatch is a row with nothing on the plot. */
export type ReadoutSeries = {
	label: string;             // at most 24 characters; a label that wraps turns one row into two
	swatch: string | null;
	values: (string | null)[]; // one per column; null prints the not-measured word
};

/** The column-major shape, for a chart with a shared column across its series. */
export type Readout = {
	columns: string[];
	series: ReadoutSeries[];
	resting: number;
	empty: string | null;
};

/** The record shape, for a chart whose hover describes one entity rather than one column. */
export type ReadoutFacts = {
	subject: string;
	facts: { label: string; value: string | null }[];
	empty: string | null;
};

export function readoutOf(input: ReadoutInput): Readout;
export function factsOf(subject: string, facts: readonly [string, number | null][],
                        format: (v: number) => string, notMeasured: string): ReadoutFacts;
```

**Two shapes, because two of the types do not have a shared column.** `overlapTimeline` and `flow` describe one entity - an item, or a stage - so their hover is a record and not a column of a matrix. The table below says which each type returns.

| Type | Returns | The strip contains | Resting column |
| --- | --- | --- | --- |
| `dateSeries` | `Readout` | the date in reader spelling, then every series at that date with its swatch and value | the newest |
| `distribution` | `Readout` | the bin's two bounds, the count in it, the cumulative share at it | the bin holding the median |
| `tileStrip` | `Readout` | the date, the state in words, and the reading where one was taken | the newest tile |
| `overlapTimeline` | `ReadoutFacts` | the item, its source, its shard, its start offset, and each drawn step's own ms | the first item |
| `flow` | `ReadoutFacts` | the stage name, what arrived, what left, what dropped and why | the first stage |
| `rankedList`, `partsOfOne`, `paired` | neither | **no strip** - the row already prints its own name and number | - |
| `pairedScatter` | neither | **no strip** - there is no shared column. Each mark carries a printed row in a list beneath the plot, in ranking order | - |

**Every chart declares one of two attributes and a test enumerates them.** `data-readout-columns="<count>"` or `data-readout-none="<five words>"`. A chart declaring neither fails `frontend/tests/console-readout.spec.ts`, **which already declares all five routes and already fails a declared count with no strip** - it is not widened by this plan, only made to cover more charts. **A chart somebody decided needs no hover and a chart where the strip was forgotten are the same chart on screen.**

| # | Behaviour |
| --- | --- |
| 1 | **The strip does not move and never floats.** A fixed block below the plot, capped at `chart.readout_max_share`. A floating box covers the mark it explains; one that dodges the cursor moves the thing being read |
| 2 | **There is no edge case because there is no edge.** The strip cannot leave the panel. What is clamped is the vertical guide, to the plot's own inset |
| 3 | **Pointer:** the nearest column to the pointer's x, on `pointermove`, whatever the y. A reader should not have to hit a 2px line |
| 4 | **Keyboard:** the wrapping element is one tab stop. Left and Right step a column, Home and End jump, Escape returns to rest. **One stop per chart, never one per mark** |
| 5 | **Touch:** a tap sets the column and it stays set. No long-press, no drag-to-scrub, no hover-only value. A tap outside returns to rest |
| 6 | **Dismiss:** pointer leave, Escape, or a tap outside. It returns to the resting column and **is never blank** - an emptying strip changes the panel's height |
| 7 | **A mark with no data prints the not-measured word**, from the same vocabulary the panel's empty state uses. Never a zero, never a dash, never a blank cell. **A null drawn as a zero is the commonest lie a console tells** |
| 8 | **A series absent from the whole window has no row.** A key for a series with no committed rows is a claim the data does not support |
| 9 | **The strip is the legend.** No chart draws a second key |
| 10 | **`title=` on a mark is refused.** All twenty-two go in the same pull request as the builder. A navigation anchor outside a plot is not a mark and is exempt by selector: the rule is that **no element inside a `[data-readout-columns]` or `[data-readout-none]` subtree carries a `title`**. **The reader loses** a pointer-only sentence a keyboard and a thumb never had |

**One open defect lands with the builder rather than being left where it is.** `chart.readout_max_share` was written for a desktop and bites at 394px, where three rows become a 174px block of wrapped words beside an empty half-plot (measured 2026-09-25). The fix: lay the rows along one line, wrap across the full plot width, then re-measure the cap at the width where it bites. It rewrites three assertions in `console-chrome.spec.ts` and `console-timings.spec.ts`, **and that is correct** - a guard moved as a side effect of something else is a guard nobody meant to move, and this one is moved on purpose.

### 2.8 The sufficiency gates - ten, each decidable

A reviewer fails a pull request on any of these. A panel that fails ships only with a `## Design rationale` entry saying why (CLAUDE.md section 9).

| # | Gate | How a reviewer decides | What fails it |
| --- | --- | --- | --- |
| 1 | **Uses the screen it is on** | the panel's spec prints the drawn plot's bounding box as a share of the panel's content box, at 390, 768 and 1440 | any width under **0.85**, or no measurement printed. **0.85 is a declared estimate** (Guardrail #10); what would settle it is a sweep across all panels once the vocabulary lands. The clause that bites today is the second: a panel with no number |
| 2 | **Separates figure from ground** | the spec reads the computed background of page, panel and plot area | any adjacent pair identical |
| 3 | **One thing lands first** | exactly one element carries `data-lede`, and the spec asserts its measured type size or mark area is the largest in the panel | zero, two, or one that is not the largest |
| 4 | **Made this year** | read the component | a native `title=` on a mark; a bare table of numbers with no shape beside it; a plot with no tint or elevation separating it from the panel; a control that is a `<select>` or a verb-button where the two-state radio is the rule |
| 5 | **The comparison reads in two seconds** | the panel carries `data-comparison="..."` and the spec asserts the sentence contains the word ` against ` | a missing attribute, or a sentence with no "against" in it. "Peak memory" is a subject; "how near 16 GiB the worst shard got, against the rest" is a comparison |
| 6 | **A trend carries its confounders** | every `dateSeries` renders the settings-change rule, or declares `data-settings-rule="none in window"` | a trend drawn with neither. **A line that moved because somebody changed the temperature looks exactly like a line that moved because the model got worse** |
| 7 | **Every column it draws has a reader** | already enforced by `backend/tests/contracts/test_column_readers.py`, unchanged by this plan | a column drawn while its name is still in `UNREAD_CELLS`. The worker moves the name up rather than routing around the test |
| 8 | **Four nothings, told apart** | the panel renders waiting, quiet, missing and unreachable as four distinct states, from the vocabulary `frontend/src/lib/console/waiting.ts` already owns | any two drawing the same thing. **A quiet pipeline and a broken fetch must never be the same picture** |
| 9 | **The strip is declared** | `frontend/tests/console-readout.spec.ts`, unchanged - it already declares all five routes | a chart declaring neither attribute; a declared column count with no strip; a swatch drawn inside a chart that has one |
| 10 | **It queries columns, not stores** | `frontend/tests/chart-vocabulary.spec.ts` walks the query door's call sites | `SELECT *`, an unbounded date range, or a store fetched whole. **A column store read as a row store has paid for the format and not used it** |

**Gates 1, 2, 3, 5 and 8 are specs; gate 4 is a reviewer reading the component** against the capture section 2.9 produces, and it is not filed as a spec because "a bare table of numbers with no shape beside it" is not decidable by a selector. Gates 7 and 9 are tests that exist today and are listed so a worker does not write a second copy.

**These gates ship enforcing on an opt-in list, not on the whole console.** Gate 3 needs `data-lede`, gate 5 needs `data-comparison` and gate 6 needs `data-settings-rule`; none of those attributes exists anywhere in `frontend/src` today, so every addressable panel would fail three gates on the day row 6 lands. **A gate that is red on arrival is a gate people learn to skip.** A panel joins the judged set in the pull request that redraws it; row 7's panel is the first.

### 2.9 The screenshot gate

**Pixel-diff baselines are refused, and the reason is this repository's rather than general.** A committed baseline is a binary blob `prune.yml` rewrites on a schedule, and font rendering differs between a developer machine and `ubuntu-latest` - so a baseline goes red for a reason nobody caused, and the one thing worse than no gate is a gate people learn to re-bless. `toHaveScreenshot` is not used on this console. **The reader loses** automatic detection of a one-pixel shift; what buys it back is the ten gates above, which are arithmetic and cannot drift.

**So the gate is capture, attach, and a human reads them against decidable assertions.**

| # | | Ruling |
| --- | --- | --- |
| 1 | Viewports | **390, 768 and 1440 CSS px** - exactly the three `console-axis.spec.ts` already measures at. The console measures at three different sets today and this collapses them to one. Reuse, do not fork |
| 2 | Themes | **both, every time.** The dark theme is designed and not derived: a shadow on a dark ground reads as nothing, so a panel that passes gate 2 in light can fail it in dark |
| 3 | Count | **seven images a panel** - three widths times two themes, **clipped to the bounding box of the `[data-console-panel-id="<id>"]` element `Panel.svelte` draws**, plus one at 390 dark with the query door's fetch routed to a 503 by `page.route('**/state/compact/**', r => r.fulfill({status: 503}))`, which is the one way a spec reaches the `unreachable` state without a second build |
| 4 | What each shows | the panel's title, its note, the plot, and the readout strip **at its resting column**. The strip is prerendered and must never capture blank |
| 5 | Where they live | `frontend/test-results/panels/<panel-id>--<width>--<theme>.png`, **gitignored**, uploaded as a run artefact and linked from the pull request. Never committed |
| 6 | The comparison tool is the naming rule | the name sorts so the same panel at the same width in the same theme from two runs lands adjacent in a listing. A reviewer downloads two artefacts and opens two folders side by side. No diffing tool, no dependency |
| 7 | Pass | all seven present, the ten gates green, and **the reviewer can state the panel's comparison sentence after two seconds of looking at the 390 dark image**. That image decides: it is the narrowest, the least tested, and the theme nobody checks |
| 8 | Fail | a missing image; an empty plot where gate 8 was not declared; a strip captured blank; **a 390 image that is the 1440 image with everything smaller.** A panel that only works at one width has not been drawn, it has been positioned |
| 9 | Tooling | Playwright, already here. A new spec group `panels` in `frontend/scripts/test-groups.ts` so the shared selector can skip it when nothing it renders moved. `page.screenshot({ clip })` per panel - no new dependency, no new config file |
| 10 | The list is config, not an array | the spec reads panel ids from `console.panel_groups` in `config/appearance.json`, **which holds 26 ids across a `pipelines` and a `machine` key today**. **A panel added without a capture fails the gate rather than shipping unseen** - within the routes that can produce an id at all |

### 2.10 Every panel, and what it becomes

**Ruled by Susan, 2026-09-26, and this is the contract the route plan executes.** Verdicts: **KEEP** - question and chart both right. **REDRAW** - right question, wrong chart, because the projection forced it. **REPLACE** - wrong question. **DELETE** - answers nothing an operator needs. **NEW** - should exist and does not.

**Fifty-one panels were drawn against what a twenty-column build-time projection could carry.** That is why thirty-nine columns of real answers have sat unread on every item of every run. The projection is gone; the reason those panels do not exist is gone with it.

**A panel this table names must be addressable before it can be judged.** Three of the five routes draw no panel id today (section 0, Hard scope - out), so the gates and the captures reach 26 panels on two routes until a route plan row wraps the other three.

| # | Panel | Route | Verdict | What it answers after |
| --- | --- | --- | --- | --- |
| 1 | At a glance; Run health; What one more article costs; Where an item's time went; Time per item by stage; Reading the prompt; Writing the summary; Where the run's time went; Visuals drawn; Whether the yield is falling | `/console/` | **KEEP** | unchanged |
| 2 | What is failing, by stage | `/console/` | **REDRAW** | queries `stage`, `outcome`, `code`, `failed_rule`. Stays a stacked date series by stage; selecting a stage opens a ranked list of the rules that refused. One glance: not "summarize is failing" but "one rule refused 40 of 52" |
| 3 | Item telemetry viewport | `/console/` | **REPLACE** | wrong question, and its title is two subsystem words (CLAUDE.md section 0b). Becomes **whether a run is getting slower on the same work**: seconds per article over `source_words`, a date series, with the settings rule across it. **The reader loses** the raw items-per-minute figure; it returns above the run timeline, which counts the whole run |
| 4 | How much of each prompt was already in memory | `/console/` | **DELETE** | the same question is drawn properly on Hardware. **The reader loses** the figure on the route they land on; the band keeps the worst-case number and the title links across |
| 5 | What the extractor found | `/console/` | **REDRAW** | queries `element_class`, `span_integrity`, `source_form`, `elements_found`. Figure cards stay; the table becomes a ranked list of element classes, with `span_integrity` as a second segment. One glance: what kind of fact the extractor gets, and how often the span it cited was intact |
| 6 | Trust the speed numbers; processor taken by another tenant; memory taken back; which machines this run got; the slowest articles getting slower; what is holding the memory; what one article costs; reading against writing; what this would have cost elsewhere | `/console/machine/` | **KEEP** | unchanged |
| 6b | What kinds of machine we keep being given | `/console/machine/` | **REDRAW** | **delivered by this plan's row 7**, which is the only panel section 2.10 does not hand to the route plan: five colour stops instead of seven, a new shape under the threshold, a new merge rule, the readout beside the plot, and d3 instead of ECharts |
| 7 | Whether some machines do the same work slower | `/console/machine/` | **REDRAW** | the title asks a rate question and the chart answers a division question. Queries `item_total_ms`, `prefill_ms`, `decode_ms` joined to `cpu_model`. Becomes one range mark per machine kind on a shared domain - fill at the median seconds an article, notch at the worst. **Its id is `reading-against-writing` and belongs to another panel**, which is how it drifted |
| 8 | Which parts of the last run took longest | `/console/machine/` | **REDRAW** | the projection summed per shard, so it could only rank shards - and an operator acts on an article. Queries `item_id`, `source_id`, `shard`, `item_total_ms`, `fetch_ms`, `extract_ms`, `summarize_ms`, `queue_wait_ms`. Becomes a ranked list of the twenty slowest articles, each a segmented track of its four stages |
| 9 | How close an article came to using up memory | `/console/machine/` | **REDRAW** | same grain defect. Queries `item_id`, `source_id`, `os_mem_available_min_bytes`, `llama_rss_bytes`, `source_words`. A ranked list of the twenty articles that left the machine least, each naming its length. One glance: whether long articles are what fills the machine |
| 10 | How much of the reading limit an article takes | `/console/machine/` | **REDRAW** | a percentile refuses "what does the tail look like". Queries `summary_input_tokens`, `label_input_tokens`, `n_ctx_configured`, `source_words_before_cap`, `truncation_cap_tokens`. Becomes a log-binned distribution with a rule at the reading limit and a second at the truncation cap, both printing their value |
| 11 | How much text the model reads again | `/console/machine/` | **REDRAW** | the server publishes its own answer and we compute a second one. Queries `label_cache_pct` and `summary_cache_pct` - **both unread today**. Becomes a date series of the server's own cache share, label and summary as two lines; the derived figure stays as a printed check beside it |
| 12 | The eleven model cards, the daily table, why a summary was doubted, faithfulness by day, which sources the checker doubts, what one summary cost, how long summaries came out, what the model change moved, how each measure is scored | `/console/model/` | **KEEP** | unchanged |
| 13 | Measured, and nothing acts on it | `/console/model/` | **REPLACE** | "which instruments are unwired" is a backlog, not an operator's question. Each instrument moves to the panel that owns its question and carries a `no threshold agreed` marker in words. **The reader loses** the one place listing unwired instruments; `eval-instruments.ts`'s contract test already fails on a column in no panel, so the list moves off the page into the test that was already keeping it |
| 14 | Stories the day merged; where the merge line sits; whether the judge agrees with itself; what the record still needs; what the judge said about the line; pairs marked apart | `/console/judgement/` | **KEEP** | unchanged. **This route is out of reach for now and that is stated rather than implied**: it reads `state/published/` and `state/llm-council/`, neither of which the browser can query. Its panels are KEEP because nothing here can change them |
| 15 | What the model made of each article | `/console/judgement/` | **DELETE** | a heading with no panel under it. **The reader loses** a promise that was never kept. It returns as a row in whichever plan wires `state/content-similarity-judge/` |
| 16 | Sources we may ask and what they yield; sources close to retiring; sources cut short most often | `/console/voices/` | **KEEP** | unchanged |
| 17 | How far the ranking discounts each feed | `/console/voices/` | **REDRAW** | it draws the ranker's input and never what the ranker did. Queries `feed_weight`, `feed_reliability`, `authority_score`, `tier_score`, `selection_score` - **all unread today** - against a count of items that published. One row a source: the discount as a target bar, the count as a figure on the same row. One glance: a source we discount heavily that still places |
| 18 | Feeds that failed | `/console/voices/` | **REDRAW** | a feed answering while its articles return 403 is invisible today. Queries `http_status`, `outcome`, `code`, `source_id`. Two tile rows a source on one date axis: feed outcome above, article fetch below. One glance: the source whose feed is green and whose articles are gone |
| 19 | **Why today's articles were chosen** | `/console/` | **NEW** | `partsOfOne`. Queries `selection_score`, `authority_score`, `tier_score`, `feed_weight`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step`. Twenty rows ranked by score, each a segmented track of what made it, fixed order. One glance: whether one component decides every row - **if `feed_weight` fills every track, the ranker is a whitelist wearing a score**. Nothing on this site says why an article was chosen |
| 20 | **What the watchlist caught** | `/console/` | **NEW** | `tileStrip`. Queries `watchlist_hit`, `watchlist_bonus`, `on_front_page`, `carried_by`. One tile a day, three states, the finding as a sentence above. **If it is always quiet, that is the answer and it should be visible** |
| 21 | **Where a fetch actually spent its time** | `/console/voices/` | **NEW** | `rankedList` with a four-segment track. Queries `fetch_connect_ms`, `fetch_ttfb_ms`, `robots_ms`, `retry_total_ms`, `retry_count`. One glance: which of four reasons a source is slow - a slow server, a flaky one, an uncached robots fetch, or a retry storm. **Three different actions, one number today** |
| 22 | **What the source answered** | `/console/voices/` | **NEW** | `tileStrip`, one tile a day a source, tinted by status class. Queries `http_status`, `source_form`, `tier`, `canonical_url`. One glance: the day a source started returning 403. **The most actionable feed-decay signal in the row, unread** |
| 23 | **How old an article was when we published it** | `/console/` | **NEW** | `distribution`. Queries `published_at`, `time_source`, `item_started_at`. Log-binned hours from publication to our run, a rule at the median, `time_source` splitting where the timestamp was inferred. One glance: whether we publish yesterday's news, and how much of the answer is a guess |
| 24 | **How a model call ended** | `/console/model/` | **NEW** | `dateSeries`, stacked, fixed order, `length` at the bottom. Queries `summary_finish_reason`, `label_finish_reason`, `recovered`. One glance: **a summary that ran out of output budget and that the console reports as a success today** |
| 25 | **Which rule refused a reply** | `/console/model/` | **NEW** | `rankedList` by count, divisor printed. Queries `failed_rule`. Panel 2 says the stage; nothing says the rule |
| 26 | **The settings-change rule** | everywhere | **NEW, not a panel** | a dashed vertical on **every** `dateSeries`, carrying the date and what changed. Reads `model_quantisation`, `n_parallel`, `temperature`, `label_budget_tokens`, `summary_budget_tokens`, `truncation_cap_tokens`, `run_visual_decision` - five of them unread. **These are the confounders under every trend on this console**, which is why gate 6 makes it a gate and not a nicety |
| 27 | `failed_field` | - | **REFUSED** | no panel. Empty on all 14,026 committed rows - it has no writer, not just no reader. Drawing it would publish a blank column as a finding. It belongs in a row that gives it a writer or deletes it |

## 3. What was measured, and what is still owed

**No measurement gates any row in this plan.** The seven rules follow from what parquet and the browser cache do, and a reading taken on one machine on one day cannot move one of them ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 7, owner-ruled 2026-09-24).

Two facts are owed before row 7 starts and neither is a gate on a design choice.

| # | Fact | Why it is not a gate | What it decides | Cost |
| --- | --- | --- | --- | --- |
| 1 | Does the published host answer a byte-range request | **Answered 2026-09-25: yes, `206` with `Accept-Ranges: bytes`.** On a binary type the offsets are true; on a text type they are the compressed offsets, which is a trap worth knowing | **Nothing here.** This row issues no range request; whole files are fetched. It is recorded so a later plan does not re-take it. One probe is still owed for the record - whether the host maps `.parquet` to a compressible type - and the tree already carries counter-evidence that it gzips `application/octet-stream` at level 5 | Taken |
| 2 | The query engine asset's transferred bytes | It consumes a budget rather than settling a choice | **Answered 2026-09-25: 7,321,471 bytes brotli on the wire** - 7,124,338 of wasm plus the worker and the loader. See the ceiling ruling below | Taken |

**The engine and the console's load ceiling are not the same instrument, and the row ships.** `page_weight.cold_console_load_bytes` is 3,400,000 bytes and `bundle-gate.mjs` computes it by summing **only the fetched data payload keys**; it never opens a script or a wasm file. Comparing 7.3 MB of code against 3.4 MB of data is a category error. The rule that governs code weight is that anything reached only through a dynamic `import()` is not first-load - and the precedent is not marginal: the on-device encoder is 16.22 MB on the wire and ships under it today.

| # | The condition that makes it legal | Enforced by |
| --- | --- | --- |
| 1 | The engine is reached only through a dynamic `import()` | The `FORBIDDEN` list in `bundle-gate.mjs` gains the engine's module and wasm symbols. **Without that line the rule is a habit rather than a control**, and a careless static import passes review |
  | 2 | The panel renders with the engine absent or failed | Row 7's acceptance gates |
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
  | 3 | Merge this into row 7 | Row 7 is a browser query and a redraw. A correction buried in a rewrite is a correction nobody can revert alone | Zero; costs the revert | Owner, 2026-09-24 |

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

### Row #3 - The four stores the console reads are published

- **Scope:** `item-health`, `scores`, `host-fingerprint` and `span-rollup` are named in `StoreConfig.published`; their daily compaction runs at the end of every content run; the build copies their compact periods into the site; the ceilings are measured and set. **No migration, no browser code, no d3, no panel change.**

**Plan 50 moves the stores. This row publishes them.** One module writes three of the four, so two plans editing it would collide - the migration belongs where the door is.

**Publishing is what makes compaction time-critical.** No raw file reaches the site, so the newest thing a panel can draw is the newest compact daily file. `.github/workflows/digest.yml`'s assemble job therefore ends by running the daily compaction for every published store. **That is one scheduler, not two**: the policy is still the gardener's config block and the workflow step is a trigger, so the gardener's own wake finds the watermark already moved.

**What that costs, measured 2026-09-25.** Git delta-compresses a rewritten period file, so five compactions a day cost about 8 KB of history per store against a 157 MiB pack. The figure of "roughly 360 MB" an earlier draft used for frequent compaction was arithmetic on a false premise and is 33 times too high.

**Nothing is narrowed on the way out.** All 122 columns of `item-health` are published, including the 39 that `UNREAD_CELLS` says no page reads today - they are the input to the item, feed and search quality work. The reader's bill is answered by consolidation: the same 122 columns are 2.6 times smaller than the CSV they replace once a day is one file.
- **Files touched:**
  - `config/idhazh.json` (`store.published` gains the four stores; `page_weight.payload_ceilings_bytes` gains a measured entry per published store's `index/daily.json`), `backend/idhazh/contracts/knobs/page_weight.py`
  - `.github/workflows/digest.yml` (the assemble job ends by running the daily compaction for every published store)
  - `frontend/scripts/copy-visuals.mjs` (the copy step joins the chain that already stages into `frontend/static/`; **a second staging script is Guardrail #4**), `.gitignore` (an eleventh line beside the ten payload directories already there)
  - `frontend/scripts/build-canary.mjs` (the copy step reads its `STATE_ROOT` switch and **fails loudly when the root is missing**, because an empty store and a working store both render)
  - `backend/tests/contracts/test_published_stores_cover_the_panels.py` (new), `backend/tests/workflows/test_digest_workflow.py`, `frontend/tests/page-weight.spec.ts`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts backend/tests/workflows -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. `ci.yml`'s bundle gate and site-cap measurement both walk the built tree, so both are re-read after the copy step lands. CI runs the full suite.
- **Oracle:** **every published address resolves, and nothing else is published.** Over a built tree: every entry in every published `index/<period>.json` names a file that exists under `build/`, every published store is in `StoreConfig.published`, every store a console panel names is in that list, and no path under `build/state/` belongs to the raw tier. It cannot settle whether a browser can query the files; row 4 does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Publishing and migrating are two rows in two plans.** The migration is one-way and lives with the door; publishing reverts to nothing and lives with the reader | Fowler |
  | 2 | **The daily compaction runs at the end of every content run**, not once a day. No raw file is published, so a store compacted daily would show the console nothing newer than yesterday. Measured: about 8 KB of history a day per store | Carmack |
  | 3 | **All four stores at once, not one to prove it.** They share one copy step, one allow-list and one ceiling shape, so doing one first buys a rehearsal and costs three more merge cycles | Owner, 2026-09-26 |
  | 4 | **Every column is published.** The 39 columns no page reads are the input to pending work, and the download is answered by consolidation rather than by a narrower copy | Owner, 2026-09-26 |
  | 5 | The ceiling is measured on each published `index/daily.json` and set in the same commit. A ceiling guessed ahead of the file is a number nothing checked | Guardrail #10 |
  | 6 | One backend test binds the panels to `StoreConfig.published`. Without it a panel can name a store the gardener does not index and the page fetches an address that 404s | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Publish a narrower copy, dropping the 39 unread columns | Saves 29 percent of the file, measured - and throws away the input to the item, feed and search quality work. The published file also stops being the store, which is the property that makes it impossible for it to disagree | Zero to take; costs a workstream | Owner, 2026-09-26 |
  | 2 | Publish the open raw days so the console shows the current hour | One open day of `host-fingerprint` is 30 per-writer shards, 33 requests and about 342 KB to draw 25 rows - 15.1 times the source bytes | Zero; costs the reader 29 requests on every view | Carmack |
  | 3 | Compact once a day and accept a day-old console | Buys git about 6 KB a day and costs the reader today entirely | About 8 KB of history a day per store | Carmack |
  | 4 | Publish one store first and the rest later | One copy step, one allow-list and one ceiling shape serve all four; doing one first is a rehearsal that costs three merge cycles | Three merge cycles | Owner, 2026-09-26 |

---

### Row #4 - The chart vocabulary and the house style, with no panel moved

- **Scope:** section 2.6's nine types become a module and a doc page; `d3-shape` is added; the house style in section 2.3 is written. **No panel moves**, which is what lets this revert to nothing.
- **Files touched:**
  - `frontend/src/lib/charts/d3/` - the directory this row creates, which no other row in either plan touches: `scale.ts`, `axis.ts`, `ordered-colour.ts`, `motion.ts`, `empty.ts`, and **one `.ts` module and one `.svelte` component per chart type**, named exactly as section 2.6 names them. `overlapTimeline` gets its `.ts` only; `RunTimelinePanel.svelte` keeps its own SVG and is its first caller
  - `frontend/package.json`, `frontend/package-lock.json` (`d3-shape`; **`d3-sankey` only if the flow type clears its own bytes**)
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (the nine types join the five marks, and the page says marks sit inside types)
  - `frontend/tests/chart-vocabulary.spec.ts` (new: the closed-set walk, and the single-engine-importer walk section 2.5 refusal 1 names)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and `python backend/utilities/doc_load.py` before and after. CI runs the full suite. **`ci.yml`'s bundle gate is re-read**, because a package landed.
  - **Named measurement before merge:** the gzipped delta each new package adds, measured on the built bundle. Carmack rules on it in this pull request. **A type whose package does not clear its own bytes loses the package and keeps hand maths** - the flow type is the first candidate, since it has one caller.
- **Oracle:** **the vocabulary is closed and nothing has left it.** Every module under `frontend/src/lib/charts/d3/` is named in section 2.6's table, every name in that table has a `.ts` module there - a type whose drawing half lives in an existing component names that component in the table rather than adding one - and an AST walk finds no `d3-selection`, `d3-transition`, `d3-axis` or `d3-scale-chromatic` import anywhere under `frontend/src/`. It cannot settle whether the nine types are the right nine; the first panel of each is what tests that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Doctrine ships before the panel that proves it.** A vocabulary plus a panel cannot be reverted without reverting the panel, and the vocabulary is the half more likely to need editing | Susan, 2026-09-26 |
  | 2 | **On this console d3 is a maths library.** Scales and path generators only; Svelte owns the DOM. A `select()` inside a component has left the vocabulary | Susan |
  | 3 | Four packages are refused by name - the axis, selection, transition and colour-ramp ones - so nobody re-argues them. Each would fork a rule this console already owns | Susan, section 2.6 |
  | 4 | **Nine types, and a tenth is an escalation.** A reader learns a vocabulary with few words | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Write the vocabulary inside the first panel | The rule would land with no independent witness and could not be edited without touching a panel | One merge cycle | Susan |
  | 2 | Take `d3-axis` for the tick logic | It forks the measured label-thinning rule `dayTicks` owns - a rule that exists because four console axes once drew their dates on top of each other | Zero to take; costs one rule two homes | Susan |
  | 3 | Take a colour-ramp package | It collides with the confidence ramp within a month. Colour comes from the eight chart tokens | Zero; costs the palette its single source | Susan |

---

### Row #5 - One readout strip, every chart, and hover a keyboard can reach

- **Scope:** section 2.7's builder and strip; **`DayReadout` is replaced by `Readout` across all twenty-two files that produce or consume it**; the narrow-width defect fixed; the twenty-two native hover attributes swept.

**This row replaces one exported type and cannot be split by panel.** `DayReadout` has nine producers and thirteen consumers; there is no intermediate commit where half the console is on the new shape and the tree compiles. The change is structural in twenty-one of the twenty-two files and behavioural only in `ChartReadout.svelte`.
- **Files touched:**
  - `frontend/src/lib/charts/readout.ts` (new, the builder and `readoutCapStyle`), `frontend/src/lib/components/ChartReadout.svelte` (the strip, and the narrow-width fix), `frontend/src/lib/charts/frame.ts` (`DayReadout` and `readoutCapStyle` leave)
  - the eight other producers: `cost.ts`, `fleet.ts`, `glance.ts`, `machine.ts`, `doubt-reasons.ts`, `eval-instruments.ts`, `context-cost.ts` under `frontend/src/lib/`
  - the thirteen consumers: `Chart.svelte`, `BandDistance.svelte`, `FailurePanels.svelte`, `RunLengths.svelte`, `StageTimings.svelte`, `ThroughputTrend.svelte`, `TimeHistogram.svelte`, `ContextCostPanel.svelte`, `TailTrendPanel.svelte`, `console/+page.svelte`, `JudgeAgreement.svelte`, `MergedStoriesPanel.svelte`, `MergeLinePlot.svelte`
  - the nine files carrying a native `title=` on a mark: `ShardBoard.svelte` (eight), `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `DiskReadsPanel.svelte`, `ProcessorLostPanel.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte`, `voices/+page.svelte`
  - `config/appearance.json` (`chart.readout_max_share` re-measured at the width where it bites)
  - `frontend/tests/console-chrome.spec.ts`, `frontend/tests/console-timings.spec.ts` (three assertions move with the cap)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and the browser smoke on all five console routes at 390, 768 and 1440 in both themes. CI runs the full suite.
- **Oracle:** **every chart declares its strip, and the strip is reachable without a pointer.** Every chart element on five routes carries `data-readout-columns` or `data-readout-none`; **no element inside one of those subtrees carries a `title` attribute** - a navigation anchor outside a plot is exempt by selector rather than by review; and for one chart of each declaring type, Tab reaches it, Left and Right step a column, Home and End jump, and Escape returns to the resting column. It cannot settle whether the strip reads well; the capture group and a reviewer do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A chart that needs no hover says so.** `data-readout-none` with five words. A chart somebody decided needs no hover and a chart where the strip was forgotten are the same chart on screen | Susan, 2026-09-26 |
  | 2 | **The strip never floats and never empties.** A floating box covers the mark it explains; an emptying strip changes the panel's height | Susan |
  | 3 | **A mark with no data prints the not-measured word.** Never a zero, never a dash, never a blank cell. A null drawn as a zero is the commonest lie a console tells | Susan |
  | 4 | **The narrow-width cap is re-measured here, on purpose.** It was written for a desktop and bites at 394px. A guard moved as a side effect of something else is a guard nobody meant to move; this one is moved deliberately and the three assertions move with it | Susan |
  | 5 | The strip is the legend. No chart draws a second key | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep the native hover attributes where they are | No keyboard reaches them, no thumb reaches them, no theme styles them and no test reads them. **The reader loses** nine files their pointer-only sentence, which a phone never had | Zero; costs twenty-two marks their hover | Susan |
  | 2 | A floating tooltip that follows the cursor | It covers the mark it explains, and one that dodges the cursor moves the thing being read | Zero; costs readability | Susan |
  | 3 | Move the strip per panel, as each panel is redrawn | `DayReadout` is one exported type with nine producers and thirteen consumers, so no intermediate commit type-checks | It does not compile | Fowler |

---

### Row #6 - The ten sufficiency gates and the panel capture group

- **Scope:** section 2.8's gates become specs, **enforcing on an opt-in list of panel ids rather than on the whole console**; section 2.9's capture group is added and driven from config. **No panel moves.**

**A panel joins the judged set in the pull request that redraws it.** Gate 3 needs `data-lede`, gate 5 needs `data-comparison` and gate 6 needs `data-settings-rule`; none of the three exists anywhere in `frontend/src` today, so enforcing on all 26 addressable panels would make the gate red on the day it lands. Row 7's panel is the first in the set.
- **Files touched:**
  - `frontend/tests/panel-sufficiency.spec.ts` (new: gates 1, 2, 3, 5 and 8 - **gate 4 is a reviewer reading the component and is not a spec**), `frontend/tests/panel-captures.spec.ts` (new, the seven images a panel)
  - `frontend/scripts/test-groups.ts` (the `panels` name in `FRONTEND_GROUPS`, its entry in the `FILES` record, **and its key in the object literal inside `groupedSpecs`** - a missing key there throws `No test group owns <file>`)
  - `frontend/scripts/test-scope.ts` (`CONSOLE` gains `panels`), `frontend/playwright.config.ts` (the project)
  - `config/appearance.json` (`console.panel_groups` gains the ids of the panels in the judged set; it holds 26 across a `pipelines` and a `machine` key today)
  - `.github/workflows/ci.yml` (**a third `actions/upload-artifact@v7` with `if: always()`, `name: panel-captures`, `path: frontend/test-results/panels/`, `retention-days: 14`** - the two existing uploads are `if: failure()`, and a capture gate whose artefact only exists on red is a gate nobody can read. Plus `SKIP_PANELS_SUITE`, the twin of the console switch)
  - `docs/concepts/design-system.md` (the ten gates **rewrite the five sufficiency checks in place** rather than adding a second list - CLAUDE.md section 5)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, including a first run of the `panels` group over **the judged set, which is empty until row 7 adds one**. CI runs the full suite and uploads the artefact.
  - **Named measurement before merge:** the wall-clock the `panels` project adds to the browser job and the artefact's total bytes, measured on the first CI run. Carmack rules on it in this pull request; **a capture set that does not fit loses the 768 width first**, because 390 and 1440 are the two the gates are judged at.
- **Oracle:** **the judged set and the capture set are the same set, both ways.** Every id in the judged list produces seven images and is judged by the five specced gates, and every id in that list resolves to a `[data-console-panel-id]` element on a route the spec visits. A panel added to the list without a capture fails. It cannot settle whether a panel is good; a reviewer reading the 390 dark image does that, and it cannot reach the three routes that draw no id at all.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Pixel-diff baselines are refused**, and for this repository's own reason: a committed baseline is a binary blob `prune.yml` rewrites on a schedule, and font rendering differs between a developer machine and the runner - so it goes red for a reason nobody caused. **The reader loses** automatic detection of a one-pixel shift; the ten gates buy it back, because they are arithmetic and cannot drift | Susan, 2026-09-26 |
  | 2 | **Both themes, every time.** The dark theme is designed and not derived: a shadow on a dark ground reads as nothing, so a panel passing gate 2 in light can fail it in dark | Susan |
  | 3 | **The 390 dark image decides.** It is the narrowest, the least tested and the theme nobody checks | Susan |
  | 4 | **Three viewports, reusing the three `console-axis.spec.ts` already measures at.** The console measures at three different sets today; this collapses them to one rather than adding a fourth | Susan, Guardrail #4 |
  | 5 | **The naming rule is the comparison tool.** Two artefacts, two folders, side by side. No diffing tool and no dependency | Susan |
  | 6 | The gates ship before the first panel they judge. A gate that lands with the panel it judges has no independent witness | Fowler |
  | 7 | **The gates enforce on an opt-in list, not on the whole console.** Twenty-six panels would fail three gates today, because `data-lede`, `data-comparison` and `data-settings-rule` exist nowhere yet. A panel joins the judged set in the pull request that redraws it | Fowler |
  | 8 | **The capture reaches 26 panels on two routes, not 51 on five.** Three routes draw no panel id at all; wrapping them is a route-plan row and is named in Hard scope - out rather than assumed | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `toHaveScreenshot` with committed baselines | Baselines go red for reasons nobody caused, and a gate people learn to re-bless is worse than no gate | Committed binary blobs the prune rewrites | Susan |
  | 2 | Full-page captures instead of clipped ones | A full page is large, so seven a panel stops being affordable, and a reviewer cannot tell which panel moved | Runner seconds and artefact bytes | Susan |
  | 3 | A hand-written array of panel ids in the spec | A panel added without a capture would ship unseen, which is the failure the gate exists for | Zero; costs the gate its completeness | Susan |
  | 4 | Enforce the gates on all 26 addressable panels at once | Three of the ten need attributes that exist nowhere in `frontend/src`, so every panel would fail three gates on the day the row lands. A gate that is red on arrival is a gate people learn to skip | Zero; costs the gate its credibility | Fowler |

---

### Row #7 - One panel end to end: the browser fetches the store and draws it in d3

- **Scope:** the browser queries the published store for the columns and days the Platform Mix panel draws, and the panel is redrawn in d3 to the vocabulary rows 4 to 6 established. **No backend change and no store change** - plan 50 and row 3 did those; **no new chart type, no new strip behaviour and no new gate** - rows 4 to 6 did those.

**Why this panel and not another.** `frontend/src/lib/charts/fleet.ts` has exactly two importers, against four for the next candidate. And the panel already takes an `svg` prop, which is the server-side renderer telemetry-intent N5 says exists only to serve ECharts - so this one panel is also the first evidence it can go.

**The query door and the hover strip are the deliverable. The panel is the proof.** Rows 4 to 6 wrote the vocabulary, the strip and the gates; this row is the smallest thing that exercises all three at once and proves the browser can reach the store ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 1, which decides any scope argument inside this row). A change that ships one good panel and no shared parts has bought one panel and left the next fifty where they were.

#### The panel this row delivers

Ruled by Susan on 2026-09-24 against the panel as it stands, whose verdict was SEND BACK: three of five sufficiency checks fail, two of five spans draw no mark, and the merged-kinds line ships a visible defect.

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
  - `frontend/src/lib/charts/fleet.ts` (from an option builder into a draw), `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, `frontend/src/routes/console/machine/+page.server.ts` (its second importer)
  - `frontend/src/lib/data/` - the query door: `store.ts`, `engine.ts`, `slice.ts`
  - `config/appearance.json` (`console.machine_colour_stops` 7 to 5, `console.absent_hatch_degrees`), `config/idhazh.json` if the panel's store needs a ceiling change
  - `frontend/package.json`, `frontend/package-lock.json` (`@duckdb/duckdb-wasm` only; `d3-shape` landed in row 4)
  - `frontend/tests/chart-vocabulary.spec.ts` (the single-engine walk now finds one importer rather than zero)
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
  | 11 | **The copy goes inside `frontend/scripts/copy-visuals.mjs`**, which already stages ten payload directories into `frontend/static/` and runs **before** `build-state.ts --begin` - so the tree a run certifies already holds the staged bytes. A second staging script is Guardrail #4, and a step after `--begin` would change the tree the run is certifying | Carmack |
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
  | 8 | Compute a raw file's name from `(dataset, tier, covers_date)` so both sides derive it | Elegant, and **it dies on N6 rather than on derivability**. A re-run of a failed job writes into its original day, so a computed name would mean different bytes at the same path - N6 broken at the one place it is load-bearing. The compact periods do take a derivable name, because there the writer is single and the period is the name | Zero; costs N6 | Fowler |
  | 9 | Keep the address book in `console/band.json` | It was the answer for a day. Two things killed it: `+layout.ts` prerenders, so the band is inlined into every console document and that is what its 2,000-byte ceiling was really paying for; and the band is written during a digest run while the files are staged later, so with overlapping runs its open-day list would name fewer files than exist and the chart would be quietly low | Zero; costs a silent undercount and a per-document cost that grows | Owner, 2026-09-25 |
  | 10 | Have the build merge today's shards into one file at a derivable address | It needs a parquet writer in the build, and the indexes exist for the older periods regardless - so it is a second mechanism for a problem the first one already solved | A new build dependency | Fowler, Guardrail #4 |
  | 11 | Have the browser probe `00.parquet`, `01.parquet` until a 404 | A 404 stops being a defect signal and becomes a loop terminator, so a genuinely missing file reads as a normal end | Zero; costs the ability to tell an absence from a fault | Fowler |
  | 12 | A single published address book naming every store | It needs a writer, and the only entity that sees every store at once is the build - which puts the list back one step from the tree it describes. It also buys nothing: a panel names its own store, and each store's indexes sit at a path the browser can compute | Zero; costs a mechanism | Owner, 2026-09-25 |
  | 13 | Publish the open raw days and let the browser read them | **It makes the cheapest span the worst value in the set**: one open day of `host-fingerprint` is 30 per-writer shards, 33 requests and about 342 KB to draw 25 rows - 15.1 times the source bytes, because a one-row file of 31 columns is mostly column overhead | Zero to take, and it costs the reader 29 requests on every view. Measured 2026-09-25 | Carmack |
  | 14 | Publish fewer columns so the file is smaller | It saves 29 percent, measured over the eight newest `item-health` files - and it throws away the input to the item, feed and search quality work, and makes the published file something other than the store | Zero to take; costs a workstream | Owner, 2026-09-26 |
  | 15 | Compact once a day rather than after every run, and accept a day-old console | **It buys git about 6 KB a day and costs the reader today's data entirely**, because no raw file is published. Git delta-compresses these rewrites: measured 2026-09-25, one period-file rewrite is 1,649 bytes packed, so five a day is about 8 KB. The "roughly 360 MB" figure an earlier draft used was arithmetic on a false premise and is 33 times too high | About 8 KB of history a day per store | Carmack, 2026-09-25 |
  | 16 | Ask the host's own contents API for a directory listing | A service rather than a static asset, rate-limited per address, untestable offline, and it breaks if the repository is renamed. Guardrail #1 says a design must not need one | Zero; costs Guardrail #1 | Carmack |
  | 17 | Write an `index.html` into each month directory so the host lists it | One round trip per store-month instead of one in total, plus 234 extra files | Zero; costs a round trip per month | Carmack |

- **What the build copies.** For every store whose `StoreConfig.published` names it, the step copies both compact periods, their indexes and their watermarks - **verbatim, into the same relative paths**. It renames nothing, merges nothing, narrows nothing and generates nothing. No raw file is copied. `state/` in the repository stays the only source (N7) and nothing production lands under `frontend/` in git (N8), because the staged tree is gitignored and rebuilt each build.

- **The published file is the store, which is why it cannot disagree with it.** An earlier draft defended this by calling it byte-identical, which set the bar in the wrong place: the property that matters is whether a published file can say something `state/` does not. A copy cannot. **`frontend/public/machine/<YYYY-MM>.csv` can**, because it joins `host-fingerprint` to aggregated `item-health` rows, and a join carries values neither store holds on its own. That file is not defended here - it is deleted by the route plan, in the pull request that moves its last reader.

- **This plan declares no new contract.** The three shapes it reads - `CompactEntry`, `CompactIndex` and `Watermark` - are declared by plan 50's section titled "The shapes a worker must not invent", committed by the gardener and read here. **The frontend's copy is hand-written in `frontend/src/lib/data/store.ts` and bound by a backend test**: `backend/tests/contracts/test_frontend_index_shapes.py` reads that module, collects the interfaces, and asserts each names exactly the fields the Pydantic model declares, in order, with the same type - the shape `test_frontend_field_set.py` already uses. **`ConsoleBand` gains nothing and is not touched.**

## Dependent plans

- `TODO/20260924-50-idhazh-gardener-plan.md`. Row 3 waits on its rows titled **The index task, two compact periods, and the diagram moves into the page**, **The three stores `work.py` writes become parquet** and **`span-rollup` becomes parquet**. Nothing else in that plan is a predecessor here.
- **The route plan, not yet written**, takes over after row 7. **Section 2.10 is its contract and Susan has already ruled it**: fifty-one panels, each KEEP, REDRAW, REPLACE, DELETE or NEW, with the columns each one queries and the chart it becomes. Nine of the redraws and seven of the new panels exist only because the browser can now query the store - the projection is what was stopping them. One row per route; each row moves that route's panels to the query door and **deletes the projection under `frontend/public/` that fed them**.
- **What the route plan is expected to cost, so nobody discovers it:** about seventeen pull requests in total, of which rows 4 to 7 here are four. The redraws batch by the type each becomes - about four pull requests, so one builder is edited once - and the new panels batch by which `UNREAD_CELLS` group they read, so each batch moves one group of names into `COLUMN_READERS` as one reviewable diff.
- **Susan's ruling on the old charts, recorded so it is not re-argued.** Those charts were drawn against what a build-time projection could carry - twenty columns, summed per shard before any page saw them. **The existing chart is evidence of an old limit rather than a decision to preserve.** Thirty-nine columns of real answers sat unread on every item of every run while nobody's job was to say the page was not enough: why an article was chosen, why a fetch was slow, what the source actually answered, how old the news was, whether a summary was cut off mid-sentence and reported as a success, which rule refused a reply, and whether any trend moved because of the model or because somebody changed a setting.
- `TODO/20260823-known-defects-plan.md`, defect 33, closes in row 1's pull request.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan lays stones for.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every row here is built to.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
