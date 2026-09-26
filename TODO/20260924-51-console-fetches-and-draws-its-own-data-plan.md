# Plan 51 - The console fetches and draws its own data

**Last Updated**: 2026-09-26

**Level**: 5 (CLAUDE.md section 6). Row 3 decides whether `state/` reaches a browser, which is a publishing contract, and sections 2.6 to 2.9 are the design contract the panels are built to. The other rows are Level 2 to Level 3 and carry no contract change beyond one copied settlement key.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3 and N5 - the browser queries the ledger for the slice it draws, fetches at view time, and d3 draws it. **Contract**: section 2 declares every shape, key, signature and config literal these rows need, so a worker builds each row with no further decision. **Code**: the eight rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as a worker returns and never waiting on a merge; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock (execute-a-plan.md, "the workers are parallel; the machine is not"); consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The Hardware route counts every job twice, its span control sits far above the reader who wants it, and every chart on the console is drawn from data baked into the page by the build. This plan corrects the count, moves the chrome, and writes the query door, the chart vocabulary, the hover strip and the gates the fifty later panels follow - then proves the whole chain on one panel: query the ledger in the browser, draw it in d3. |
| Hard scope - in | - `state/host-fingerprint/` is read settled, so a job counts once.<br>- The five-tab console strip sticks, the span control rides on it, and a sentence says how complete the page is.<br>- The three ledgers the console reads reach the browser as published parquet.<br>- `frontend/src/lib/data/` holds the one query door every later panel calls; `frontend/src/lib/charts/d3/` holds the house style every later chart draws to.<br>- One panel queries the published ledger for the columns and days it draws and is redrawn in d3. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A tenth prerendered route, or retiring an existing one.<br>2. A charting library that is not d3.<br>3. A new committed payload under `frontend/public/`.<br>4. Any change to `ConsoleBand`'s shape - it is the payload every console route fetches first, so a retyped or removed field ripples to every route.<br>5. **A chart type that is not one of the nine in section 2.6.** A tenth is a design question, not an improvisation.<br><br>**"How the browser reaches the bytes" is settled**: `state/` carries its own indexes, declared and committed by plan 50 (its section titled "The shapes a worker must not invent"); the build copies the published ledgers' compact periods verbatim into gitignored `frontend/static/state/` and generates nothing.<br><br>**Compaction and the ledger migration are plan 50's, not this plan's.** Plan 50 migrates the ledgers to parquet, owns every compaction trigger and its eligibility rule, and declares the index and watermark shapes. This plan publishes what plan 50 compacted and reads it in the browser. |
| Chosen strategy | Correct the number first, move the chrome and publish second, write the shared parts third, prove them on one panel last. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The other fifty panels, on all five console routes | Two grammars coexist: one panel queries parquet and draws in d3, fifty read CSV at build time and draw in ECharts. `echarts@^5.6.0` stays installed with its importers | [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md), which starts from the vocabulary, the strip and the gates in sections 2.6 to 2.9, and from the panel-by-panel verdict table Susan ruled, now carried in plan 52. **Rows 4 to 8 exist to make that plan cheap, not to be it** |
| The panel-by-panel verdict table for all fifty-one panels (KEEP / REDRAW / REPLACE / DELETE / NEW) | Plan 52 has no execution backlog until a `prepare-plan` pass turns those verdicts into rows | It lives in plan 52 now; this plan executes only panel 6b, whose spec stays here in row 8 |
| Panel ids on `/console/model/`, `/console/voices/` and `/console/judgement/` | Those three routes import neither `Panel.svelte` nor `PanelGroup.svelte`, so they draw no `data-console-panel-id` and **no gate and no capture can reach them**. Row 6's judged set is the addressable panels on the two routes that draw an id, and a panel on the other three ships unseen | A route-plan row in plan 52 that wraps those three routes' sections in `Panel.svelte` and adds their route keys to `console.panel_groups`. It is a prerequisite of a full capture, not a follow-up |
| Three `/console/` panels nested inside another panel's body | "Reading the prompt", "Writing the summary" and "How much of each prompt was already in memory" are `<Panel>` elements inside another panel and carry no id, so the capture never sees them | A route-plan row that either gives each an id and its parent's group, or takes its `Panel.svelte` wrapper away. It is one or the other, not both |
| Taking any route off `export const prerender` | Nine files under `frontend/src` keep it. Row 8's panel fetches after mount on a page that still prerenders, which is legal and is what lets one panel prove N3 without moving a route | The plan that moves a whole route, which owns the first-paint and no-script questions for every panel on it |
| Retiring the payloads under `frontend/public/` | Telemetry-intent N7 and N8 get no stone here. `frontend/public/machine/<YYYY-MM>.csv`, the roll-up of `host-fingerprint` joined to `item-health`, keeps being published | Plan 52, the same whole-route plan. Retiring a published payload needs every reader moved first |
| The throughput spread per machine kind | The Platform Mix panel says what we were given and not how much one machine varies | It is the machine cards' and the shard board's question. Row 8's readout links to them |
| Fixing defect 26, the settlement-key guard that reads one constant twice | Row 1 adds a third key to a guard that cannot fully check it, and says so in the pull request | Its own row. A pull request that fixes a guard and the thing the guard was meant to catch leaves neither fix with an independent witness |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star and sits above this plan (CLAUDE.md section 0d). The seven rules a panel obeys are [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md).

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N1 | Parquet at rest, CSV retired | **Not here.** Plan 50 migrates the three ledgers the console reads; row 3 publishes them |
| N2 | The browser queries the parquet itself | **Stone laid by row 7**, the query door: one module owns the engine and every later panel queries through it |
| N3 | The browser fetches its own data at view time | **Stone laid by rows 7 and 8** - the door fetches at view time and one panel proves it after mount |
| N4 | Prerendering is an anti-pattern | **Not here.** Nine files keep `export const prerender`, and ESCALATE trigger 1 stops a row adding a tenth |
| N5 | d3 is the only charting library | **Stone laid by rows 4 to 6**, which write the nine chart types, the hover strip and the ten gates, and by row 8, which moves one importer |
| N6 | One writer per path | **Inherited** from plan 50's door |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Stone laid by row 3.** What reaches the site is the ledger itself, copied unchanged and gitignored, so it cannot say anything `state/` does not. **The projections that can are retired by plan 52**, each in the pull request that moves its last reader |
| N9, N10, N11 | The name, the two roots, the one shard pattern | **Inherited** from plan 50's door. This plan mints no naming rule of its own |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The Hardware route stops counting every job twice | - | A | PENDING | - | - | - |
| 2 | The console shell: a stuck tab strip, the span control on it, four named anchors, a completeness sentence | - | A | PENDING | - | - | - |
| 3 | The three ledgers the console reads are published | plan 50's rows titled "The index task, two compact periods, and the diagram moves into the page" and "The three ledgers the console's routes read become parquet" | B | PENDING | - | - | - |
| 4 | The chart vocabulary and the house style, with no panel moved | - | B | PENDING | - | - | - |
| 5 | One readout strip, every chart, and hover a keyboard can reach | 1, 4 | C | PENDING | - | - | - |
| 6 | The ten sufficiency gates and the panel capture group | 4, 5 | C | PENDING | - | - | - |
| 7 | The query door module and its two entry points | 4; plan 50's row titled "The index task, two compact periods, and the diagram moves into the page" | C | PENDING | - | - | - |
| 8 | One panel end to end: the browser fetches the ledger and draws it in d3 | 1, 2, 3, 4, 5, 6, 7 | D | PENDING | - | - | - |

**Readiness is the file-disjointness test, not the group letter** (execute-a-plan.md). The letters record which rows the author believed independent; the `Files touched` lists are the fact, and the shared-file notes below are why three depends-on edges exist that the letters do not show.

**Rows 1 and 2 run two-wide.** They share no file: row 1 holds `payload.ts`, `host-fingerprint.ts`, `machine-counters.ts`, `fleet.ts`, `PlatformMixPanel.svelte`; row 2 holds `+layout.svelte`, `ConsoleNav.svelte`, `SiteHeader.svelte`, `band.ts`, `app.css`.

**Rows 3 and 4 run two-wide.** Row 3 is backend, config and the build (`config/idhazh.json`, `copy-visuals.mjs`, `bundle-gate.mjs`, the ceiling test); row 4 is new frontend chart modules under `frontend/src/lib/charts/d3/`. Disjoint.

**Group C is rows 5, 6 and 7, and depends-on edges make it safe.** The overlaps that force the edges: **rows 5 and 6 both edit `config/appearance.json`** (row 5 the `chart.readout_max_share` value, row 6 the `console.panel_groups` and `console.judged_panel_ids` keys), so row 6 depends on row 5 and the file is edited once at a time; **rows 1 and 5 both edit `fleet.ts`** (row 5 rebuilds its `Readout` producer), so row 5 depends on row 1; and **row 7 edits `chart-vocabulary.spec.ts` and `frontend/package.json`, which row 4 creates and touches** (row 4 adds `d3-shape`, row 7 adds the engine), so row 7 depends on row 4. Row 7's index-shape test binds to the Pydantic index contracts **plan 50's index-task row** declares, so it also waits on that plan-50 row - for the shape only, never for live data. Row 7 shares `bundle-gate.mjs` with row 3 (row 3 the ceiling key, row 7 the engine's `FORBIDDEN` entry), but row 3 waits on plan 50's migration, which waits on row 7, so row 7 always lands first and the file is edited in order. **The cross-plan chain stays acyclic**: plan 50's migration -> plan 51 row 7 -> plan 51 row 4 -> nothing, and plan 51 row 7 -> plan 50's index-task row, which reaches nothing in plan 51.

**Why the query door is its own row (row 7) and not folded into the panel.** It is the N2 and N3 keystone every one of plan 52's fifty panels calls, so it ships as an independently revertible row with its own witness, exactly as the vocabulary (row 4), the strip (row 5) and the gates (row 6) do. Plan 50's row titled "The three ledgers the console's routes read become parquet" also depends on this row by name; the door depends only on row 4 and on plan 50's index-task row (for the shape of the index it reads), neither of which reaches plan 50's migration, so the door lands before that migration and the cross-plan pointer resolves without a cycle.

**Rows 4, 5, 6 and 7 are the shared deliverable; row 8 is the proof.** Sections 2.2 and 2.6 to 2.9 declare all of them, so no row invents anything. Row 4 writes modules and no panel, which is why it runs beside row 3.

**Row 5 replaces one exported type and cannot be split by panel.** `DayReadout` becomes `Readout` across its producers and consumers, so there is no intermediate commit where half the console is on the new shape and the tree compiles. That is why its `Files touched` is long and why row 6 (which shares the config file) waits on it.

**Row 3 publishes; it migrates nothing and triggers no compaction.** Plan 50 migrates the ledgers and owns every compaction trigger and its eligibility rule. Row 3 adds the copy step, the allow-list, the ceiling and the test that binds a panel's ledger to that list. It reverts to nothing.

**Row 8 is the proof and lands last.** It rewrites `fleet.ts` into a d3 draw, wires the panel to the query door, and joins the capture group, so it shares `fleet.ts`, `PlatformMixPanel.svelte` and `host-fingerprint.ts` with row 1 and the query door with row 7, and cannot run beside them.

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

The query door is three modules under `frontend/src/lib/data/`, and a panel sees only the first. `ledger.ts` is the public door every panel calls; `engine.ts` is **the only module in `frontend/` that imports the query engine** (`@duckdb/duckdb-wasm`), mirroring the backend's single-engine rule; `slice.ts` turns a date range into the set of files to fetch. A panel imports `ledger.ts` and nothing deeper.

```ts
/** Ask a committed ledger for the slice a panel draws. Columns and a date range
 *  are named by the caller; nothing fetches a whole ledger. */
export async function slice(
	ledger: LedgerName,
	opts: { columns: readonly string[]; from: DateStamp; to: DateStamp; where?: readonly Predicate[] }
): Promise<SliceResult>;

/** One parquet row as the engine hands it back. */
export type Row = Record<string, string | number | boolean | null>;

/** What the door hands a panel, so the panel draws the right one of four nothings
 *  without inspecting an error. `rows` is empty for every state but `ok`; `loading`
 *  is the panel's own state before the promise resolves and is not returned here. */
export type SliceResult =
	| { state: 'ok'; rows: Row[] }
	| { state: 'quiet'; rows: [] }                        // the window is covered but held no rows
	| { state: 'missing'; rows: [] }                      // the ledger is not published
	| { state: 'unreachable'; rows: []; at: DateStamp };  // a date named in no index

/** A structured filter, never raw SQL. Each clause names a column, an operator and
 *  a value the caller supplies; the door binds the value as a query parameter, so
 *  no text a panel passes can become SQL (Guardrail #11). */
export type Predicate = {
	column: string;
	op: '=' | '!=' | '<' | '<=' | '>' | '>=' | 'in';
	value: string | number | readonly (string | number)[];
};

/** The ledgers this console may query. A closed set: a panel names a ledger, never
 *  a path. These are exactly the three row 3 publishes. */
export type LedgerName = 'host-fingerprint' | 'item-health' | 'scores';
```

**`LedgerName` maps to an address inside `ledger.ts` and nowhere else.** The door joins `visuals.asset_base_url` - or SvelteKit's own repository prefix when that knob is empty, which is the shipped default - onto the committed path unchanged: `state/compact/<ledger>/index/daily.json`, `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`, `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet`. Getting the prefix wrong is the commonest failure on this host, so one module owns it. A panel that could name a path could name any path, and the published list would stop being the bound.

**Whole files are fetched and handed to the engine as buffers**, the same way the month search index already is. There are no byte-range requests anywhere in this plan - a date-range query and an HTTP range request are different things, and only the first is used. Column projection saves parse time, not bytes.

**File selection follows the span.** `console.window_presets` is `[1, 7, 14, 30, 90]`. A span of 30 days or less is served entirely from the daily period - the two indexes plus one daily file per date; only the widest span reaches a monthly file. No raw file is published, so the one-day span reads one daily file and is the cheapest in the set.

**The browser cannot list a directory, so the ledger carries its own indexes.** Owner ruling, 2026-09-25: **`state/` presents its own index, and the build generates nothing.** Plan 50's section titled "The shapes a worker must not invent" declares the small JSON files that do it, each committed, each with exactly one writer. This plan invents no address book, declares no contract of its own, and adds no generating step.

**Three findings settled it, and none of them is the byte ceiling that prompted the question.**

**The band is prerendered into every console document.** `+layout.ts` carries `prerender = true`, so at build time SvelteKit resolves the fetch and serialises the result into each console page. Anything that loader fetches is inlined into every console document, so a file fetched there inherits the same cost under a different name. **What escapes it is fetching at view time from the query door**, which is what N3 asks for anyway.

**A band-carried list would have undercounted, silently.** `console/band.json` is written by `stages/assemble.py` during a digest run at one moment; the files reach the site at a later one. `digest.yml` has no concurrency group by design, so more shards land in between, and the list would name fewer files than the tree holds. The browser would read twelve shards of sixteen and the chart would be quietly low, with no error and no 404 - the defect-33 class arriving through a new door, and no test could have caught it, because the invariant would have had to hold across two processes at two different times.

**A list generated at build time has the same hole, one step later.** Plan 50 closes it at the source instead: the index task re-lists a raw day directory at every wake and the daily compaction re-lists it again before reading, so no elapsed-time guess stands between the tree and the list. **That re-list is what makes a committed index trustworthy**, and it is what this plan depends on.

| # | File | Writer | Why that writer is safe | Committed |
| --- | --- | --- | --- | --- |
| 1 | `state/compact/<ledger>/index/<period>.json` | that period's compaction | one period, one task, one writer | **yes** |
| 2 | `state/compact/<ledger>/<period>/watermark.json` | that period's compaction | same task, written after the data | **yes** |

#### What the build does, which is copy bytes and nothing else

**The staged tree is a verbatim subtree copy, so the published path and the committed path are the same string.** The step copies, for every ledger whose `LedgerConfig.published` names it: the two compact periods, their indexes and their watermarks. Nothing else, and nothing is renamed, merged, re-sorted or regenerated.

| # | What reaches the site | Published address |
| --- | --- | --- |
| 1 | Compact data, both periods | `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`, `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet` |
| 2 | Compact indexes and watermarks | `state/compact/<ledger>/index/<period>.json`, `state/compact/<ledger>/<period>/watermark.json` |

**The raw tier is not published.** Publishing an open raw day would make the cheapest span the worst value in the set - many per-writer shards to draw one day - so only compact periods reach the site. The newest thing a panel can draw is therefore the newest compact daily file; plan 50's eligibility rule sets how fresh that is, and row 2's completeness sentence is what tells the reader.

**What answers N7 is that the published file is the ledger.** The test is not whether a copy is byte-identical - it is whether a published file can say something `state/` does not. A copy cannot. **`frontend/public/machine/<YYYY-MM>.csv` can**: it joins `host-fingerprint` to `item-health` rows summed per shard, so it carries values neither ledger holds alone and either ledger can move underneath it. That is the shape N7 exists to retire, and plan 52 deletes it along with the other projections, each in the pull request that moves its last reader. N10 already blesses a compact period as derived and rebuildable.

**An index carries filenames and periods, and nothing else.** No URL, no host, no prefix - the door composes the address from `visuals.asset_base_url`, a constant it already holds, so there is no cell a fetched article could arrive in (Guardrail #11).

#### What the browser reaches for, and why it needs no ledger list

**Two things get a panel to its data, and both are already in hand.** The base URL is `visuals.asset_base_url` in `config/idhazh.json`, read by [frontend/asset-base.js](../frontend/asset-base.js), which also computes the `connect-src` allow-list from the same value so the address and the browser policy cannot disagree. The ledger is named by the panel: a machine-mix panel draws machine fingerprints, and that cannot vary without it becoming a different panel.

**So `LedgerConfig.published` never reaches the browser**, and there is no second copy of it to keep in step. It decides what the build copies, which is a backend question. **One backend test holds the two sides together**: it reads the console panel sources, collects the ledger names they name, and asserts every one is published. Same home and same shape as `backend/tests/contracts/test_frontend_vocabularies.py`.

#### What the door does with a date range

A panel asks for a span; the door turns it into whole files. **There are no byte-range requests anywhere in this plan** - a date-range query and an HTTP range request are different things, and only the first is used.

| # | Step |
| --- | --- |
| 1 | **At view time, from the query door - never from `+layout.ts`.** That loader prerenders, so anything fetched there is inlined into every console document. This is the whole reason the address book never went in the band |
| 2 | Fetch only the indexes the span could touch, plus `daily/watermark.json`. A span of 30 days or less touches `daily.json` only, so that is two small requests |
| 3 | For each date in the span take the **coarsest period that covers it** - monthly, then daily - and fetch that file once |
| 4 | Hand every buffer to the engine as one query with a date predicate |

**A date is reachable through exactly one file, and that is an invariant with a test rather than a convention.** A date in two periods is read twice and every number on the panel doubles - the same defect class as the double count filed as 33. Plan 50's row titled **The index task, two compact periods, and the diagram moves into the page** carries the oracle that asserts it, over a fixture ledger carrying both periods, in one process, at one moment.

**A hole is `unreachable`, never a low chart.** A date at or before the daily watermark that is named in neither index is a hole: the door returns `{ state: 'unreachable', at }` and the panel draws the `unreachable` state with that date in the console and nothing else. Drawing the rest would be an undercount nobody could see.

**A date after the daily watermark is not drawn at all, and the freshness sentence says so.** No raw file is published, so the newest data a panel can show is the newest compact daily file - at most one content run old, because the daily compaction runs at the end of every run.

**Two periods are what make an arbitrary span affordable.** The widest span reads one or two monthly files plus the daily files past the newest whole month, instead of one daily file per day. At month grain alone a span would pull whole months it did not ask for; at day grain alone the widest span would be a request per day.

#### The reader's first request is bounded by config, never by the archive

**This is Guardrail #12 pointed at a reader.** An index that gained an entry every month would make a reader's request grow for as long as the project runs, so its length is bounded by config.

**The bound: an index holds its keep-window of entries and no more. `daily.json` holds at most `daily_keep_days + 31`, `monthly.json` at most `monthly_keep_months`.** Two config values a person sets, and no term of elapsed time. The `+31` is the month-absorption rule, not slack: a month is absorbed whole, so the daily period holds between `daily_keep_days` and `daily_keep_days + 31` days.

**Two controls hold the bound.** First, a published ledger may not leave either of its windows null (null means never delete); plan 50's section titled "`config/idhazh_gardener.json`" refuses a null window at load, along with a `monthly_keep_months` that does not cover the widest value in `console.window_presets` once `daily_keep_days` is subtracted. The daily window is deliberately narrower than the widest span - that is what the monthly period is for. Second, `page_weight.payload_ceilings_bytes` gains an entry for each published `index/daily.json`, and `bundle-gate.mjs` checks it every build - a smoke alarm derived from config that moves when config moves.

**Each file carries its own version, taken from the index entry that names it.** `CompactIndex.entries` holds `covers`, `rows` and `bytes` per file, and the door appends `?v=<rows>-<bytes>` from that entry. A daily file is written once and never rewritten, so its entry never changes and the browser caches it forever; a single site-wide stamp would re-fetch every daily file each day to deliver one new one. The indexes themselves are fetched `cache: 'no-store'`, because a stale index is what file selection would act on.

**Nothing new enters git.** The staged copies are created on the runner inside `npm run build`, copied into `build/` by the bundler, uploaded as the Pages artefact and thrown away with the runner. Ten directories under `frontend/static/` are gitignored and published exactly this way today. **Gitignored is not unpublished**, and the ignore line is doing N8's job.

| # | Why concurrent runs cannot collide here | |
| --- | --- | --- |
| 1 | A digest run writes `<unit_id>.parquet` into `state/` and pushes. It never stages and never builds | No job that commits also builds the site |
| 2 | Only `pages.yml` builds, and its build job is `cancel-in-progress: true` | One builder, always |
| 3 | The band and the files it names are produced from one checkout and shipped in one artefact | **Consistency by construction, not by locking** - adding runners upstream cannot break it |

**The band is generated whole on every run and never appended to**, which is how it is already written. An append would be read-modify-write on a shared path, the shape the minted name exists to end.

**`SELECT *` is refused at this door**, not by convention: `columns` is required, non-empty, and the door raises by name on an empty list ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 5).

### 2.3 The d3 house style

`frontend/src/lib/charts/d3/` (new, no other row in either plan touches it). **Every function here is pure and takes its numbers as arguments.** The two named colour constants are the exception and are named as one: `RESERVED_GREY` **re-exports `UNRECORDED_STOP` from `machine-colour.ts`** rather than minting a second grey, and `ABSENT_HATCH` reads `console.absent_hatch_degrees`.

| Module | Exports | What it owns |
| --- | --- | --- |
| `scale.ts` | `bandScale`, `linearScale`, `timeScale` | The three scales a console chart may reach for, each reading its range from the frame |
| `axis.ts` | `valueAxis` | Tick counts, formats and the label rule for a **value** axis, from `config/appearance.json`. **There is no `dateAxis`** - `dayTicks` in `frontend/src/lib/charts/frame.ts` owns every date axis on this console and gains no second home, which is the same reason section 2.6 refuses `d3-axis` |
| `ordered-colour.ts` | `orderedRamp`, `RESERVED_GREY`, `ABSENT_HATCH` | The five-step speed ramp, the grey for an absence and the hatch for a known machine with no reading |
| `motion.ts` | `transition`, `prefersReducedMotion` | One duration, one easing, and the reduced-motion branch written once |
| `empty.ts` | `emptyState` | **Re-exported from `frontend/src/lib/console/waiting.ts`**, which already owns `loading`, `quiet`, `missing` and `unreachable` and their sentences. This module adds the drawing of each state and mints no second vocabulary (Guardrail #4) |

### 2.4 The appearance knobs these rows read

Every value below is a knob (Guardrail #6). Some exist and some are minted; the "Read by" column names the row.

| Key | Status | Value | Read by |
| --- | --- | --- | --- |
| `console.machine_colour_stops` | **Exists at 7, becomes 5** | `5` | Row 8's ramp. Five steps because a reader cannot rank many steps of one hue on a thin bar, and three panels share machine colour so a silent mismatch ships |
| `console.fleet_min_rows` | Exists | `160`, unchanged | Row 8. The knob keeps its job and changes what it switches: below it the panel draws one mark per job instead of switching off |
| `console.fleet_top_kinds` | Exists | `4`, unchanged | Row 8's merge rule |
| `frame.breakpoints_px` | Exists as `[640, 1024, 1400]` | unchanged | Row 2 sticks at `breakpoints_px[1]`. **No second key naming that width** |
| `console.window_presets` | **Exists as `[1, 7, 14, 30, 90]`** | unchanged | Row 2's five-segment control reads it, and the door reads its widest value for file selection. **No second key naming the same five values** |
| `console.absent_hatch_degrees` | **New** | `45` | Row 8's hatch for a known machine with no throughput reading |
| `console.plot_min_fill_share` | **New** | `0.85` | Gate 1 (section 2.8), specced in row 6. A fill floor with the same standing as `console.fleet_min_rows`: the spec asserts the drawn plot fills at least this share of the panel's content box |
| `console.judged_panel_ids` | **New** | `[]` (row 8 adds `6b`) | Row 6's sufficiency specs only. The opt-in subset of `console.panel_groups` the gates judge; capture still runs over all of `panel_groups`, so a panel is captured before it is judged |
| `page_weight.payload_ceilings_bytes."state/compact/<ledger>/index/"` | **New, one per published ledger** | set in row 3 from the built `daily.json`, at least twice its size per the field's own rule | `frontend/scripts/bundle-gate.mjs` and `backend/tests/contracts/test_page_ceilings.py`. **The key names the one directory that holds files directly**: `payloadsFor` does not recurse, so a key naming `state/compact/<ledger>/` returns nothing and fails the gate by name. It lives in `config/idhazh.json`, not `config/appearance.json` |

**`console.bandwidth_min_kinds` and `console.min_attempts_for_rate` already exist and are unchanged.** The chart types in section 2.6 name them, but the panels that read them are plan 52's; no row here reads them, so they are not in the table above.

**Three page-weight gates fire before the site cap, and row 3 must clear all three.** `page_weight.cold_console_load_bytes` is what a console reader's first load may cost, so **the query engine ships behind a dynamic import**, the same rule the gate already enforces for the on-device encoder. `page_weight.payload_ceilings_bytes` caps each fetched payload and has **no key covering `state/`** today, so a staged ledger is a payload no gate can see until the key above is minted. And `test_page_ceilings.py` asserts `cold_console_load_bytes` sits between the worst page and that page plus the telemetry ceiling, so adding a payload key moves that two-sided assertion - **which is why the key, the ceiling and the assertion move in one commit, row 3's.**

**`cold_console_load_bytes` counts month-grained copies, and the door fetches days.** Row 3 sets the ledger's payload ceiling on `index/daily.json` only, and the fetched-data total is bounded by `console.window_presets`' widest value against `daily_keep_days` (plan 50's gardener config) - which is the bound `test_page_ceilings.py` is given, in the same commit.

### 2.5 What a panel may not do

Three refusals, each enforced by a test rather than a review note.

| # | Refusal | Enforced by |
| --- | --- | --- |
| 1 | A panel imports the query engine directly | `git grep -l duckdb -- frontend/src` returns exactly one path |
| 2 | A panel builds a URL or a path | `slice()` takes a `LedgerName`, never a path |
| 3 | A panel asks for every column | `columns` is required and non-empty, refused by name at the door |

### 2.6 The chart vocabulary - nine types, and a tenth is an escalation

Ruled by Susan, 2026-09-26. **A panel that needs a type not on this list stops and asks.** The five mark shapes already ruled in [docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md) are marks **inside** these types, not types; nothing there is superseded.

**Each type is one `.ts` module returning geometry and one `.svelte` component that draws it.** The `.ts` module is pure and takes every number as an argument (section 2.3); the component owns the DOM. Where a type's drawing half already lives in an existing component, the table names it and no new component is made.

| # | The name a worker types | The signature | The question it answers | Right when | Wrong when | Drawn by |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `rankedList` | `(rows: readonly {label: string; value: number; segments?: readonly {label: string; value: number}[]}[], opts: {max?: number}) => RankedGeometry` | which one is worst | a bounded set of named things, one magnitude each, and the reader acts on the name | the question is "what is changing" - that is type 2 | **`frontend/src/lib/components/RankedList.svelte`, which exists and has four importers. No new component** - markup not SVG: seventy rows would be seventy chart instances, and markup still draws with no script |
| 2 | `dateSeries` | `(series: readonly {label: string; token: string; points: readonly {date: DateStamp; value: number \| null}[]}[], opts: {frame: Frame; stacked?: boolean}) => SeriesGeometry` | what is changing | a value per day or per run, one to five series, compared across time | the set is not ordered by time. A run mix drawn as a trend invites a cause nothing measured | `DateSeries.svelte`. Ticks from `dayTicks` in `frontend/src/lib/charts/frame.ts`, **never from an axis generator** |
| 3 | `distribution` | `(values: readonly number[], opts: {frame: Frame; rules?: readonly {at: number; label: string}[]}) => BinGeometry` | how bad does it get | one quantity over many items, the tail is the point, the spread crosses a decade | fewer than `console.fleet_min_rows` values. A histogram of eight readings is a claim | `Distribution.svelte`. Cumulative curve on a second axis, 0 to 100 |
| 4 | `partsOfOne` | `(rows: readonly {label: string; parts: readonly {label: string; value: number}[]}[], opts: {order: readonly string[]; overlapping?: boolean}) => PartsGeometry` | what is this one thing made of | components of a single total, fixed order, a handful of rows | the components do not sum to the total - set `overlapping` and each part becomes a bracket anchored at the origin rather than a stacked segment, because overlapping parts do not add up to the row total | `PartsOfOne.svelte`, segments as markup not paths |
| 5 | `tileStrip` | `(tiles: readonly {date: DateStamp; state: 'quiet' \| 'fired' \| 'absent'; reading?: number}[], opts: {thresholds: readonly [number, number]}) => TileGeometry` | was it quiet, and which day did it fire | a reading that is zero or absent on most days | the reading has a useful value axis every day - that is type 2 | `TileStrip.svelte`. **Three states, never two.** Both thresholds from config |
| 6 | `paired` | `(rows: readonly {label: string; before: number; after: number; attempts: number}[]) => PairedGeometry` | what did the change move | two measurements of the same measures, and the reader wants the direction | either side is below `console.min_attempts_for_rate` - the row draws nothing and prints why | **`frontend/src/lib/components/SwapDots.svelte`, which exists. No new component** - through `swapScale` in `frontend/src/lib/charts/series.ts`. Symmetric about no change, minimum half-width |
| 7 | `overlapTimeline` | `(items: readonly {id: string; source: string; shard: number; startMs: number; steps: readonly {label: string; ms: number}[]}[]) => TimelineGeometry` | what was happening at the same time | work items on a real clock, where the queue is the finding | the reader wants totals. A timeline is the worst shape for a sum | **`RunTimelinePanel.svelte`, which keeps its own hand SVG** and is this type's first and only caller. No new component |
| 8 | `flow` | `(stages: readonly {label: string; arrived: number; left: number; drops: readonly {label: string; count: number}[]}[], opts: {narrow: boolean}) => FlowGeometry \| SteppedGeometry` | where did they go, and where did they leave | a funnel of four or fewer stages with named drops | never - below `frame.breakpoints_px[0]` it returns the stepped shape from the same call | `Flow.svelte`; the panel computes `narrow` from the width against `frame.breakpoints_px[0]`, `d3-sankey` at or above it and a markup list below |
| 9 | `pairedScatter` | `(points: readonly {label: string; x: number; y: number}[], opts: {frame: Frame}) => ScatterGeometry` | do these two move together | at least `console.fleet_min_rows` rows **and** `console.bandwidth_min_kinds` distinct subjects | below either floor. Two points define a line, so a scatter of two is a claim. It draws nothing and names the floor it missed | `PairedScatter.svelte`. **No trend line, ever** - a fitted line is a verdict nobody agreed to |

**Every geometry function returns its type or `null`** - the `| null` is dropped from the signature column above for brevity and is not optional. On `null` the component renders `emptyState` (section 2.3), which takes the reason to show; for the floor-guarded types (`distribution`, `paired`, `pairedScatter`) that reason is the floor it missed, named in words (for example "fewer than 160 readings"). A type that returns an empty geometry rather than `null` draws an empty frame, which gate 8 fails.

**Refused, so nobody re-argues them:** pie, donut over anything but a single completed share, gauge, dial, radar, treemap, word cloud, bubble, anything in three dimensions, and a bar chart of a rate below `console.min_attempts_for_rate` placements. **The reader loses nothing**: each answers a question one of the nine answers better.

**A reused component takes the new geometry as its data prop.** Types 1, 6 and 7 name an existing component (`RankedList.svelte`, `SwapDots.svelte`, `RunTimelinePanel.svelte`) rather than a new one; each takes its type's geometry (`RankedGeometry`, `PairedGeometry`, `TimelineGeometry`) as its data prop and renders `emptyState` (section 2.3) on a `null` return. "No new component" is not "no prop change": the row that first uses one of these three updates its props to the geometry type in the same commit.

**Plan 52 may find a panel that needs a mark none of the nine hosts** - a range mark (a fill to a median with a notch at the max) or a target marker on a bar. That is ESCALATE trigger 5: plan 52 either restates the panel onto an existing type or escalates a tenth type with its signature and component, and gets it ruled before building. This plan's own panel (6b, row 8) is a `dateSeries`, so it needs no tenth type.

**The packages, and the rule that keeps them small.**

| # | Package | For | Status |
| --- | --- | --- | --- |
| 1 | `d3-array` | binning, quantiles, extent | installed |
| 2 | `d3-scale` | every scale above | installed |
| 3 | `d3-shape` | `line`, `area`, `stack` for types 2 and 4 | **to add** |
| 4 | `d3-sankey` | type 8 only | **to add when the flow type is built; the bundle gate is the check, and if it does not pass the type keeps hand maths** |
| 5 | `d3-axis` | - | **refused.** It would fork the measured label-thinning rule `dayTicks` owns, and that rule exists because four console axes once drew their dates on top of each other |
| 6 | `d3-selection`, `d3-transition` | - | **refused.** Svelte owns the DOM |
| 7 | `d3-scale-chromatic` | - | **refused.** Colour comes from `--chart-1` to `--chart-8` and the tint tokens. A library ramp collides with the confidence ramp within a month |

**On this console d3 is a maths library, not a drawing library.** A worker who writes `select()` inside a Svelte component has left the vocabulary.

### 2.7 The readout strip - one module, every chart, and hover that a keyboard can reach

**The console has two hover systems today and one of them is invisible.** `frontend/src/lib/components/ChartReadout.svelte` is the ruled one, a fixed strip below the plot. **Twenty-one marks across ten files use a native `title=` instead**, which no keyboard reaches, no thumb reaches, no theme styles and no test reads - eight in `ShardBoard.svelte`, three in `voices/+page.svelte`, two each in `DiskReadsPanel.svelte` and `ProcessorLostPanel.svelte`, and one each in `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte` and `console/+page.svelte`. **That is the defect this section closes.**

**One module owns it**, `ChartReadout.svelte`, fed by one builder, `frontend/src/lib/charts/readout.ts`. Every chart calls the builder and passes its result. No chart composes its own strip and no chart sets `title=` on a mark.

**`DayReadout` in `frontend/src/lib/charts/frame.ts` is replaced by `Readout`, and `readoutCapStyle` moves to `readout.ts` with it.** The pointer-nearest-column and keyboard-stepping machinery `frame.ts` holds for the old shape - `columnStrip`, `nearestColumn`, `pointerReadout`, `readoutMarks` and their types `ReadoutMark`, `ReadoutRow`, `StripSeries`, `ReadoutOptions` - moves into `readout.ts` too, retyped onto `Readout`, so behaviours 3 and 4 have one home. **Ten producing functions across eight files** build a `DayReadout` today and thirteen components consume it; **all of them move in row 5's single commit**, which is why that row cannot be split by panel - there is no intermediate commit where half the console is on the new shape and the tree compiles.

```ts
/** What a chart hands the builder. Only the three column types call this; the
 *  two record types call `factsOf` below. */
export type ReadoutInput = {
	type: 'dateSeries' | 'distribution' | 'tileStrip';
	columns: readonly string[];          // the label of each hoverable column, in draw order
	series: readonly {
		label: string;
		swatch: string | null;
		values: readonly (number | null)[];
		format: (value: number) => string; // this series' own number-to-text, so a count and a share sit in one strip
		note?: string;                     // one constant printed once for the series, e.g. a per-kind rate
	}[];
	notMeasured: string;                 // from the same vocabulary as the panel's empty state
	resting: 'newest' | 'median' | 'first';
};

/** One row of the strip. A row with no swatch is a row with nothing on the plot. */
export type ReadoutSeries = {
	label: string;             // at most 24 characters; a label that wraps turns one row into two
	swatch: string | null;
	values: (string | null)[]; // one per column; null prints the not-measured word
	note?: string;             // a constant printed once beside the label, never per column
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

**Two shapes, because two of the types do not have a shared column.** `overlapTimeline` and `flow` describe one entity - an item, or a stage - so their hover is a record and not a column of a matrix. `readoutOf` builds a `Readout` and is called only by the three column types; `factsOf` builds a `ReadoutFacts` and is called only by `overlapTimeline` and `flow`. `ChartReadout.svelte` selects its layout from the shape it is handed: the column strip for a `Readout`, the record list for a `ReadoutFacts`. The table below says which each type returns.

| Type | Returns | The strip contains | Resting column |
| --- | --- | --- | --- |
| `dateSeries` | `Readout` | the date in reader spelling, then every series at that date with its swatch and value | the newest |
| `distribution` | `Readout`, two series | the bin's two bounds as the column, then two rows - the count in the bin and the cumulative share at it, each with its own `format` | the bin holding the median |
| `tileStrip` | `Readout` | the date, the state in words, and the reading where one was taken | the newest tile |
| `overlapTimeline` | `ReadoutFacts` | the item, its source, its shard, its start offset, and each drawn step's own ms | the first item |
| `flow` | `ReadoutFacts` | the stage name, what arrived, what left, what dropped and why | the first stage |
| `rankedList`, `partsOfOne`, `paired` | neither | **no strip** - the row already prints its own name and number | - |
| `pairedScatter` | neither | **no strip** - there is no shared column. Each mark carries a printed row in a list beneath the plot, in ranking order | - |

**`factsOf` and the `ReadoutFacts` record layout are built and unit-tested in row 5** so the vocabulary is complete, but no plan-51 panel returns a `ReadoutFacts` - the first is a plan-52 `overlapTimeline` or `flow` panel. Row 5's oracle covers the three column types plus a unit test on `factsOf`.

**Every chart declares one of two attributes and a test enumerates them.** `data-readout-columns="<count>"` or `data-readout-none="<five words>"`. A chart declaring neither fails `frontend/tests/console-readout.spec.ts`, **which already declares all five routes and already fails a declared count with no strip** - it is not widened by this plan, only made to cover more charts. **A chart somebody decided needs no hover and a chart where the strip was forgotten are the same chart on screen.**

| # | Behaviour |
| --- | --- |
| 1 | **The strip does not move and never floats.** A fixed block below the plot, capped at `chart.readout_max_share`. A floating box covers the mark it explains; one that dodges the cursor moves the thing being read |
| 2 | **There is no edge case because there is no edge.** The strip cannot leave the panel. What is clamped is the vertical guide, to the plot's own inset |
| 3 | **Pointer:** the nearest column to the pointer's x, on `pointermove`, whatever the y. A reader should not have to hit a 2px line |
| 4 | **Keyboard:** the wrapping element is one tab stop. Left and Right step a column, Home and End jump, Escape returns to rest. **One stop per chart, never one per mark.** A `ReadoutFacts` strip has no columns to step: Up and Down move between records and Escape rests |
| 5 | **Touch:** a tap sets the column and it stays set. No long-press, no drag-to-scrub, no hover-only value. A tap outside returns to rest |
| 6 | **Dismiss:** pointer leave, Escape, or a tap outside. It returns to the resting column and **is never blank** - an emptying strip changes the panel's height |
| 7 | **A mark with no data prints the not-measured word**, from the same vocabulary the panel's empty state uses. Never a zero, never a dash, never a blank cell. **A null drawn as a zero is the commonest lie a console tells** |
| 8 | **A series absent from the whole window has no row.** A key for a series with no committed rows is a claim the data does not support |
| 9 | **The strip is the legend.** No chart draws a second key |
| 10 | **`title=` on a mark is refused.** All twenty-one go in the same pull request as the builder. A navigation anchor outside a plot is not a mark and is exempt by selector: the rule is that **no element inside a `[data-readout-columns]` or `[data-readout-none]` subtree carries a `title`**. **The reader loses** a pointer-only sentence a keyboard and a thumb never had |

**One open defect lands with the builder rather than being left where it is.** `chart.readout_max_share` was written for a desktop and wraps the readout into a tall block on a narrow plot. The fix: lay the rows along one line, wrap across the full plot width, then re-set the cap at the width where the readout wraps. It rewrites three assertions in `console-chrome.spec.ts` and `console-timings.spec.ts`, **and that is correct** - a guard moved as a side effect of something else is a guard nobody meant to move, and this one is moved on purpose.

### 2.8 The sufficiency gates - ten, each decidable

A reviewer fails a pull request on any of these. A panel that fails ships only with a `## Design rationale` entry saying why (CLAUDE.md section 9).

| # | Gate | How a reviewer decides | What fails it |
| --- | --- | --- | --- |
| 1 | **Uses the screen it is on** | the panel's spec prints the drawn plot's bounding box as a share of the panel's content box, at 390, 768 and 1440 | any width where that share is under `console.plot_min_fill_share`, or no share printed |
| 2 | **Separates figure from ground** | the spec reads the computed background of page, panel and plot area | any adjacent pair identical |
| 3 | **One thing lands first** | exactly one element carries `data-lede`, and the spec asserts its measured type size or mark area is the largest in the panel | zero, two, or one that is not the largest |
| 4 | **Made this year** | read the component | a native `title=` on a mark; a bare table of numbers with no shape beside it; a plot with no tint or elevation separating it from the panel; a control that is a `<select>` or a verb-button where the two-state radio is the rule |
| 5 | **The comparison reads in two seconds** | the panel carries `data-comparison="..."` whose sentence contains ` against `, **or** a composition-over-time panel (a stacked `dateSeries` of counts or shares) declares `data-comparison="composition"` and ships a `## Design rationale` line saying it has no two-quantity comparison | a missing attribute; a sentence with no "against" that is not the declared composition case. "Peak memory" is a subject; "how near 16 GiB the worst shard got, against the rest" is a comparison |
| 6 | **A trend carries its confounders** | every `dateSeries` renders the settings-change rule, or declares `data-settings-rule="none in window"` | a trend drawn with neither. **A line that moved because somebody changed the temperature looks exactly like a line that moved because the model got worse** |
| 7 | **Every column it draws has a reader** | already enforced by `backend/tests/contracts/test_column_readers.py`, unchanged by this plan | a column drawn while its name is still in `UNREAD_CELLS`. The worker moves the name up rather than routing around the test |
| 8 | **Four nothings, told apart** | the panel renders waiting, quiet, missing and unreachable as four distinct states, from the vocabulary `frontend/src/lib/console/waiting.ts` already owns | any two drawing the same thing. **A quiet pipeline and a broken fetch must never be the same picture** |
| 9 | **The strip is declared** | `frontend/tests/console-readout.spec.ts`, unchanged - it already declares all five routes | a chart declaring neither attribute; a declared column count with no strip; a swatch drawn inside a chart that has one |
| 10 | **It queries columns, not ledgers** | `frontend/tests/chart-vocabulary.spec.ts` walks the query door's call sites | `SELECT *`, an unbounded date range, or a ledger fetched whole. **A column ledger read as a row ledger has paid for the format and not used it** |

**Where each gate is enforced.** Gates 1, 2, 3, 5, 6 and 8 are specs in `panel-sufficiency.spec.ts` (row 6). Gate 10 is `chart-vocabulary.spec.ts` (row 4). Gates 7 and 9 are tests that exist today (`test_column_readers.py` and `console-readout.spec.ts`) and are listed so a worker does not write a second copy. Gate 4 is a reviewer reading the component against the capture section 2.9 produces - it is not a spec because "a bare table of numbers with no shape beside it" is not decidable by a selector.

**These gates ship enforcing on an opt-in list, not on the whole console.** The judged set is `console.judged_panel_ids`, a subset of `console.panel_groups` that only the sufficiency specs read; capture (section 2.9) still runs over all of `panel_groups`. Gate 3 needs `data-lede`, gate 5 needs `data-comparison` and gate 6 needs `data-settings-rule`; none of those attributes exists anywhere in `frontend/src` today, so judging every addressable panel would fail three gates on the day row 6 lands. **A gate that is red on arrival is a gate people learn to skip.** A panel joins `judged_panel_ids` in the pull request that redraws it; row 8's panel is the first, and row 6 ships one fixture panel so the gates have a witness before then.

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
| 10 | The list is config, not an array | the capture spec reads every id in `console.panel_groups`; the sufficiency spec reads only `console.judged_panel_ids`, a subset. **A panel added to `panel_groups` without a capture fails the capture gate rather than shipping unseen**, and a panel added to `judged_panel_ids` without the three attributes fails the sufficiency gates - within the routes that can produce an id at all |

### 2.10 The panel-by-panel verdict table lives in plan 52

Susan ruled all fifty-one panels on 2026-09-26 - each KEEP, REDRAW, REPLACE, DELETE or NEW, with the columns it queries and the chart it becomes. **That verdict table is plan 52's contract, not this plan's**, and it now lives in [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md). This plan executes exactly one of those panels - **panel 6b, "What kinds of machine we keep being given"** - and its full spec is row 8.

**One thing the verdict table surfaced belongs here, because it validates section 2.6.** Two plan-52 panels - a machine-speed range and a feed-discount target bar - want a mark none of the nine types hosts. That is ESCALATE trigger 5, and plan 52 resolves it before it builds either: restate the panel onto an existing type, or escalate a tenth type with its signature and component. This plan's own panel needs no tenth type.

---

### Row #1 - The Hardware route stops counting every job twice

- **Scope:** both console readers of `state/host-fingerprint/` settle by key, and the merged-kinds line names the machines it merged. No backend change, no ledger change, no panel redesign, no parquet and no d3.

**Two defects, one pull request, because they are the same panel's two wrong sentences.**

**Defect 33 - the double count.** Every job writes its machine row in two halves by design: the hardware probe first, the clock after the last item. `ledger.extend_segment` says in its own docstring that it settles nothing and that `day_shards.settled_rows` decides what two rows of one key mean. `frontend/src/lib/server/host-fingerprint.ts` line 145 and `frontend/src/lib/server/machine-counters.ts` line 906 both call `readDayShards`, the plain reader, so both halves reach the page as two job placements - one carrying the machine and one carrying only `job_seconds`, which lands in `Other machines`. About a fifth of the machine rows are the second half of a job and are counted a second time this way.

**The merged-kinds line - `drawn as one bar: .`** `PlatformMixPanel.svelte` line 83 reads `series.at(-1)` for the merged names, but `fleet.ts` line 232 merges into an existing series and pushes nothing when the ramp has already absorbed it, so the last series is a real machine whose merged list is empty. An optional chain swallows it. **The merge returns which series carries it rather than the reader guessing it is last** - guessing is what made this invisible, and a second reader would guess again.

- **Files touched:**
  - `frontend/src/lib/server/payload.ts` (section 2.1's key and rule, beside `ITEM_HEALTH_KEY`)
  - `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/server/machine-counters.ts` (both move to `mergedDayShards`, section 2.1 - a cell union, never `settledDayShards`)
  - `frontend/src/lib/charts/fleet.ts` (the merge names its own series)
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (stops guessing)
  - `frontend/tests/console-machine-data.spec.ts`, `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-cards.spec.ts`
  - `frontend/tests/support/machine-rows.ts` (a fixture day holding one job's two halves)
  - `TODO/20260823-known-defects-plan.md` (defect 33 closes in this commit)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list`, then the selected checks; the browser smoke on `/console/machine` (CLAUDE.md section 12) with zero new `[error]` and zero new `404`. CI runs the full suite.
- **Oracle:** over a fixture day holding one job's two halves, the reader returns **one** row carrying both the machine and the clock, and the merged row's cell count equals the union of the two halves. It cannot settle whether any other ledger needs the same treatment; that is each ledger's own question.
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
  | 2 | Sweep every remaining raw `readDayShards` call in one row | Right instinct, wrong row. Each ledger needs its own ruling on which key settles it and whether the rule is a merge or a preference | A follow-up that rules each ledger's settlement key, ledger by ledger | Fowler |
  | 3 | Merge this into row 7 | Row 7 is a browser query and a redraw. A correction buried in a rewrite is a correction nobody can revert alone | Zero; costs the revert | Owner, 2026-09-24 |

---

### Row #2 - The console shell: a stuck tab strip, the span control on it, four named anchors

- **Scope:** the chrome every console route sits in, and **the sentence that says how complete the page is**. No panel changes, no ledger is read differently, and no data moves.

**Row 2 ships before row 3, and that ordering is the requirement rather than a convenience.** Every chart on the console draws the newest days that **exist**, not the last N days - so when data stops, a chart gains no gap at the right edge. It slides back in time and looks exactly as full as it did yesterday. Reader's verdict on that, 2026-09-24: *"I read a month-old chart, believed it, and closed the tab satisfied."* A page that can go quiet without saying so is worse than useless, so the sentence exists before anything starts fetching.

**The completeness sentence is a template with named slots, computed from fields that already exist** - `covers_through`, `generated_at`, `compaction_lag_days` on `ConsoleBand`. **No new `ConsoleBand` field.** All three are UTC (CLAUDE.md section 2), and every slot is formatted in UTC.

Two templates, and one switch chooses between them:

```
Complete to {HH:MM} {today|weekday}. A run still going is not in this yet.
```
```
Nothing has been recorded since {weekday day month}. {n} days are missing.
```

- **The switch.** Template 2 fires when `covers_through` falls further behind `generated_at` than the routine compaction lag - plan 50's `compact_after_hours` produces a fixed lag, so in routine operation the data sits exactly that far back and template 1 fires. `{n}` is the excess in whole UTC days.
- **The slots.** `{HH:MM}` is `covers_through` as UTC hours and minutes; `{today|weekday}` is "today" when `covers_through` is the current UTC day, else its UTC weekday name; `{weekday day month}` is `covers_through` spelled in UTC.

The load-bearing word is **complete**: a promise about the left side and an admission about the right, so once it is read a gap is a fact rather than a defect. It is a sentence, not a badge, not a colour and not a grey timestamp. The filled examples ("Complete to 14:25 today"; "Nothing has been recorded since Friday 20 September. Four days are missing.") are illustrations, not the contract.

Ruled by Susan on 2026-09-24. The complaint: the Hardware route is fifteen panels long with no quick way back, and the span control sits at the top where a reader nine panels down cannot reach it.

| # | Element | Ruling | What the reader loses |
| --- | --- | --- | --- |
| 1 | The five-tab strip | **Stuck from `frame.breakpoints_px[1]` up.** Below that it stays where it is | one strip-height of every screen above that width, against a long route of scrolling |
| 2 | `Days shown` | Moves to the trailing edge of the stuck strip at that width and up, as a **compact five-segment control**. Below it, unchanged and full width | the word `days` repeated five times |
| 3 | The tab description line, while stuck | Hidden. It is already hidden below 1400 px and is the anchor's `title` | the one-line summary of the other four routes while scrolled; it returns at the top |
| 4 | Back to the top | An **`On this page` row of the route's own group names** under the span control, read from `console.panel_groups[route]`, and a `Top` link on each group heading. A route with no groups, or one unnamed group, shows no anchor row | nothing |
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
- **Acceptance gates:** the browser smoke on all five console routes at 390, 768 and 1440 - the set section 2.9 fixes, straddling the `breakpoints_px[1]` sticky boundary (CLAUDE.md section 12); zero new `[error]` and zero new `404`. Local `npm --prefix frontend run test:changed -- --list`, then the selected checks. CI runs the full suite.
- **Oracle:** at 1440 (above the boundary) the stuck strip's measured height equals one row and each of the route's anchors scrolls its heading into view below the stuck band rather than behind it; at 768 (below) nothing is stuck. It cannot settle whether the breakpoint is the right one; decision 4 makes it a knob so it moves without a code change.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A dropdown is refused for the span control.** A menu hides four of five options, and it hides the price at the moment the browser starts fetching its own data | Susan, 2026-09-24 |
  | 2 | **Collapsing the logo on scroll is refused.** It buys zero pixels because the header already leaves the screen, and scroll-linked motion has to be designed twice for reduced motion | Susan, 2026-09-24 |
  | 3 | **Collapsing the band is refused.** The band is what an operator reads on landing; collapsed, he opens a disclosure to learn that yesterday failed. Its worst-thing fragment rides in the stuck strip as one short line instead | Susan, 2026-09-24 |
  | 4 | It sticks at `frame.breakpoints_px[1]` (inclusive), reusing the existing key. A stuck control is one band at the width it sticks at, so the five tabs and the span control together are one row there; if they do not fit, the tab labels shorten to their initials before the span control wraps to a second line. Below the breakpoint the strip is not stuck and may reflow | Susan. A second key naming that width is the duplicate this project rejects everywhere else |
  | 5 | Four named anchors beat one floating arrow. Fifteen panels sit in four declared groups, and named anchors work with no script at every width | Susan, 2026-09-24 |
  | 6 | This row does not touch `PlatformMixPanel.svelte`. Row 1 owns that file and runs beside this one | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Stick the strip at every width | At 640 px it is two rows and at 360 px three, and a stuck control that reflows eats a third of a small screen | Zero; costs the small-screen reader a third of the page | Susan |
  | 2 | A floating back-to-top arrow | It goes one place. Fifteen panels in four groups need four destinations, and an arrow needs script where an anchor does not | Zero; costs three of the four destinations | Susan |
  | 3 | Merge this into row 1 | Route chrome and a settlement-key change in one pull request, because both happen to be about one route | Zero; costs the independent revert | Fowler |

---

### Row #3 - The three ledgers the console reads are published

- **Scope:** `item-health`, `scores` and `host-fingerprint` are named in `LedgerConfig.published`; the build copies their compact periods into the site; the payload ceiling is set from the built index. **No migration, no compaction, no browser code, no d3, no panel change.**

**Plan 50 migrates the ledgers and owns every compaction trigger. This row only publishes.** It adds the copy step, the allow-list, the ceiling and the test that binds a panel's ledger to that list, and it reverts to nothing. It publishes exactly the three ledgers plan 50's row titled "The three ledgers the console's routes read become parquet" delivers.

**No raw file reaches the site, so the newest thing a panel draws is the newest compact daily file.** How fresh that is follows from plan 50's eligibility rule, and row 2's completeness sentence is what tells the reader. This row changes no schedule and edits no workflow.

**Nothing is narrowed on the way out.** Every column of `item-health` is published, including those `UNREAD_CELLS` says no page reads today - they are the input to the item, feed and search quality work. A published copy that dropped columns would stop being the ledger, which is the property that makes it impossible for it to disagree with `state/`.
- **Files touched:**
  - `config/idhazh.json` (`ledger.published` gains the three ledgers; `page_weight.payload_ceilings_bytes` gains one entry per published ledger's `index/daily.json`), `backend/idhazh/contracts/knobs/page_weight.py`
  - `frontend/scripts/copy-visuals.mjs` (the copy step joins the chain that already stages into `frontend/static/`; **a second staging script is Guardrail #4**), `.gitignore` (one line beside the payload directories already there)
  - `frontend/scripts/build-canary.mjs` (the copy step reads its `STATE_ROOT` switch and **fails loudly when the root is missing**, because an empty ledger and a working ledger both render)
  - `frontend/scripts/bundle-gate.mjs`, `backend/tests/contracts/test_page_ceilings.py` (this row owns the `state/` payload-ceiling key and its two-sided assertion)
  - `backend/tests/contracts/test_published_ledgers_cover_the_panels.py` (new), `frontend/tests/page-weight.spec.ts`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. `ci.yml`'s bundle gate and site-cap measurement both walk the built tree, so both are re-read after the copy step lands. CI runs the full suite.
- **Oracle:** **every published address resolves, and nothing else is published.** Over a built tree: every entry in every published `index/<period>.json` names a file that exists under `build/`, every published ledger is in `LedgerConfig.published`, every ledger a console panel names is in that list, and no path under `build/state/` belongs to the raw tier. It cannot settle whether a browser can query the files; row 7 does that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Publishing and migrating are two rows in two plans.** The migration is one-way and lives with plan 50; publishing reverts to nothing and lives here | Fowler |
  | 2 | **This row triggers no compaction and edits no workflow.** Plan 50 owns every compaction trigger and its eligibility rule; the newest compact day is as fresh as that rule allows, and row 2's sentence says so. An earlier draft ran compaction from `digest.yml`, which plan 50 forbids | Fowler, on plan 50's ruling |
  | 3 | **All three at once, not one to prove it.** They share one copy step, one allow-list and one ceiling shape, so doing one first buys a rehearsal and costs two more merge cycles | Owner, 2026-09-26 |
  | 4 | **Every column is published.** The columns no page reads are the input to pending work, and the reader's download is answered by consolidation rather than by a narrower copy | Owner, 2026-09-26 |
  | 5 | The ceiling is set on each published `index/daily.json` from the built file, in the same commit. A ceiling guessed ahead of the file is a number nothing checked | Guardrail #10 |
  | 6 | One backend test binds the panels to `LedgerConfig.published`. Without it a panel can name a ledger the gardener does not index and the page fetches an address that 404s | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Publish a narrower copy, dropping the unread columns | Throws away the input to the item, feed and search quality work, and the published file stops being the ledger - the property that makes it impossible for it to disagree | Zero to take; costs a workstream | Owner, 2026-09-26 |
  | 2 | Publish the open raw days so the console shows the current hour | An open day is many per-writer shards, so the cheapest span becomes the worst value in the set | Zero; costs the reader a request per shard on every view | Carmack |
  | 3 | Run compaction from `digest.yml` so the console is one run fresh | Plan 50 forbids a compaction trigger outside the gardener, and its eligibility rule makes per-run freshness impossible anyway | Zero; costs plan 50's single-writer rule | Fowler |
  | 4 | Publish one ledger first and the rest later | One copy step, one allow-list and one ceiling shape serve all three; doing one first is a rehearsal that costs two merge cycles | Two merge cycles | Owner, 2026-09-26 |

---

### Row #4 - The chart vocabulary and the house style, with no panel moved

- **Scope:** section 2.6's nine types become a module and a doc page; `d3-shape` is added; the house style in section 2.3 is written. **No panel moves**, which is what lets this revert to nothing.
- **Files touched:**
  - `frontend/src/lib/charts/d3/` - the directory this row creates, which no other row in either plan touches: `scale.ts`, `axis.ts`, `ordered-colour.ts`, `motion.ts`, `empty.ts`, and **one `.ts` module and one `.svelte` component per chart type**, named exactly as section 2.6 names them. `overlapTimeline` gets its `.ts` only; `RunTimelinePanel.svelte` keeps its own SVG and is its first caller
  - `frontend/package.json`, `frontend/package-lock.json` (`d3-shape`; **`d3-sankey` only when the flow type is built and the bundle gate passes**)
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (the nine types join the five marks, and the page says marks sit inside types)
  - `frontend/tests/chart-vocabulary.spec.ts` (new: the closed-set walk, the single-engine-importer walk section 2.5 refusal 1 names, and gate 10's columns-not-ledgers walk, which is vacuous until a panel queries in rows 7 and 8)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and `python backend/utilities/doc_load.py` before and after. CI runs the full suite. **`ci.yml`'s bundle gate is the check on any package that lands** - if it does not pass, the package is dropped and the type keeps hand maths (the flow type is the first candidate, since it has one caller).
- **Oracle:** **the vocabulary is closed and nothing has left it.** Every module under `frontend/src/lib/charts/d3/` is either named in section 2.6's table or is one of the five house-style modules section 2.3 declares, and every name in that table has a `.ts` module there - a type whose drawing half lives in an existing component names that component in the table rather than adding one. An AST walk finds no `d3-selection`, `d3-transition`, `d3-axis` or `d3-scale-chromatic` import anywhere under `frontend/src/`. It cannot settle whether the nine types are the right nine; the first panel of each is what tests that.
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

- **Scope:** section 2.7's builder and strip; **`DayReadout` is replaced by `Readout` across every file that produces or consumes it**; the narrow-width defect fixed; the native `title=` hovers swept.

**This row replaces one exported type and cannot be split by panel.** There is no intermediate commit where half the console is on the new shape and the tree compiles, so every producer and consumer moves together; the change is structural in every file but `ChartReadout.svelte`, where the behaviour lands. **It depends on row 1** (both edit `fleet.ts`) **and row 4** (it draws to the house style).
- **Files touched:**
  - `frontend/src/lib/charts/readout.ts` (new, the builder, `readoutCapStyle`, and the pointer/keyboard machinery), `frontend/src/lib/components/ChartReadout.svelte` (the strip, and the narrow-width fix), `frontend/src/lib/charts/frame.ts` (`DayReadout`, `readoutCapStyle`, `columnStrip`, `nearestColumn`, `pointerReadout`, `readoutMarks`, `ReadoutMark`, `ReadoutRow`, `StripSeries`, `ReadoutOptions` all leave for `readout.ts`)
  - the seven other producer files: `cost.ts`, `fleet.ts`, `glance.ts` (two functions), `machine.ts` (two functions), `doubt-reasons.ts`, `eval-instruments.ts`, `context-cost.ts` under `frontend/src/lib/`
  - the thirteen consumers: `Chart.svelte`, `BandDistance.svelte`, `FailurePanels.svelte`, `RunLengths.svelte`, `StageTimings.svelte`, `ThroughputTrend.svelte`, `TimeHistogram.svelte`, `ContextCostPanel.svelte`, `TailTrendPanel.svelte`, `console/+page.svelte`, `JudgeAgreement.svelte`, `MergedStoriesPanel.svelte`, `MergeLinePlot.svelte`
  - the ten files carrying a native `title=` on a mark: `ShardBoard.svelte` (eight), `voices/+page.svelte` (three), `DiskReadsPanel.svelte` (two), `ProcessorLostPanel.svelte` (two), `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte`, `console/+page.svelte`
  - `config/appearance.json` (`chart.readout_max_share` re-set at the width where the readout wraps)
  - `frontend/tests/console-chrome.spec.ts`, `frontend/tests/console-timings.spec.ts` (three assertions move with the cap)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and the browser smoke on all five console routes at 390, 768 and 1440 in both themes. CI runs the full suite.
- **Oracle:** **every chart declares its strip, and the strip is reachable without a pointer.** Every chart element on five routes carries `data-readout-columns` or `data-readout-none`; **no element inside one of those subtrees carries a `title` attribute** - a navigation anchor outside a plot is exempt by selector rather than by review; and for one chart of each declaring type, Tab reaches it, Left and Right step a column, Home and End jump, and Escape returns to the resting column. It cannot settle whether the strip reads well; the capture group and a reviewer do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A chart that needs no hover says so.** `data-readout-none` with five words. A chart somebody decided needs no hover and a chart where the strip was forgotten are the same chart on screen | Susan, 2026-09-26 |
  | 2 | **The strip never floats and never empties.** A floating box covers the mark it explains; an emptying strip changes the panel's height | Susan |
  | 3 | **A mark with no data prints the not-measured word.** Never a zero, never a dash, never a blank cell. A null drawn as a zero is the commonest lie a console tells | Susan |
  | 4 | **The narrow-width cap is re-set here, on purpose.** It was written for a desktop and wraps the readout on a narrow plot. A guard moved as a side effect of something else is a guard nobody meant to move; this one is moved deliberately and the three assertions move with it | Susan |
  | 5 | The strip is the legend. No chart draws a second key | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep the native hover attributes where they are | No keyboard reaches them, no thumb reaches them, no theme styles them and no test reads them. **The reader loses** those files their pointer-only sentence, which a phone never had | Zero; costs every swept mark its hover | Susan |
  | 2 | A floating tooltip that follows the cursor | It covers the mark it explains, and one that dodges the cursor moves the thing being read | Zero; costs readability | Susan |
  | 3 | Move the strip per panel, as each panel is redrawn | `DayReadout` is one exported type with many producers and consumers, so no intermediate commit type-checks | It does not compile | Fowler |

---

### Row #6 - The ten sufficiency gates and the panel capture group

- **Scope:** section 2.8's gates become specs, **enforcing on an opt-in list of panel ids rather than on the whole console**; section 2.9's capture group is added and driven from config. **No panel moves.**

**This row depends on row 4** (the gate specs judge charts drawn to the vocabulary) **and row 5** (both edit `config/appearance.json`, so it lands after the readout row).

**A panel joins the judged set in the pull request that redraws it.** Gate 3 needs `data-lede`, gate 5 needs `data-comparison` and gate 6 needs `data-settings-rule`; none of the three exists anywhere in `frontend/src` today, so enforcing on all 26 addressable panels would make the gate red on the day it lands. Row 8's panel is the first in the set.
- **Files touched:**
  - `frontend/tests/panel-sufficiency.spec.ts` (new: gates 1, 2, 3, 5, 6 and 8 - **gate 4 is a reviewer reading the component and is not a spec**), `frontend/tests/panel-captures.spec.ts` (new, the seven images a panel)
  - `frontend/scripts/test-groups.ts` (the `panels` name in `FRONTEND_GROUPS`, its entry in the `FILES` record, **and its key in the object literal inside `groupedSpecs`** - a missing key there throws `No test group owns <file>`)
  - `frontend/scripts/test-scope.ts` (`CONSOLE` gains `panels`), `frontend/playwright.config.ts` (the project)
  - `config/appearance.json` (**new key `console.judged_panel_ids`**, the opt-in subset the sufficiency specs read; `console.panel_groups` unchanged, still the capture and nav source), `backend/idhazh/contracts/knobs/console.py` (the new key)
  - `frontend/tests/fixtures/panels/` (a test-only panel exercising gates 1, 2, 3, 5, 6 and 8 on one passing and one deliberately failing input, so the gates have a witness before row 8's real panel)
  - `.github/workflows/ci.yml` (**a third `actions/upload-artifact@v7` with `if: always()`, `name: panel-captures`, `path: frontend/test-results/panels/`, `retention-days: 14`** - the two existing uploads are `if: failure()`, and a capture gate whose artefact only exists on red is a gate nobody can read. Plus `SKIP_PANELS_SUITE`, the twin of the console switch)
  - `docs/concepts/design-system.md` (the ten gates **rewrite the five sufficiency checks in place** rather than adding a second list - CLAUDE.md section 5)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, including a first run of the `panels` group over the fixture panel this row ships (the real judged set is just row 8's panel, later). CI runs the full suite and uploads the artefact. **The browser job's own timeout and the site-cap walk are the checks on the capture set** - if the seven-image-a-panel set does not fit, the 768 width is dropped first, because 390 and 1440 are the two the gates are judged at.
- **Oracle:** **every judged id is captured, and every gate catches its failing fixture.** `console.judged_panel_ids` is a subset of `console.panel_groups`, so every judged id resolves to a captured `[data-console-panel-id]`; and over the fixture panel this row ships, each of gates 1, 2, 3, 5, 6 and 8 clears the good input and fails the deliberately bad one - a witness independent of row 8. It cannot settle whether a real panel is good; a reviewer reading the 390 dark image does that, and it cannot reach the three routes that draw no id at all.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Pixel-diff baselines are refused**, and for this repository's own reason: a committed baseline is a binary blob `prune.yml` rewrites on a schedule, and font rendering differs between a developer machine and the runner - so it goes red for a reason nobody caused. **The reader loses** automatic detection of a one-pixel shift; the ten gates buy it back, because they are arithmetic and cannot drift | Susan, 2026-09-26 |
  | 2 | **Both themes, every time.** The dark theme is designed and not derived: a shadow on a dark ground reads as nothing, so a panel passing gate 2 in light can fail it in dark | Susan |
  | 3 | **The 390 dark image decides.** It is the narrowest, the least tested and the theme nobody checks | Susan |
  | 4 | **Three viewports, reusing the three `console-axis.spec.ts` already measures at.** The console measures at three different sets today; this collapses them to one rather than adding a fourth | Susan, Guardrail #4 |
  | 5 | **The naming rule is the comparison tool.** Two artefacts, two folders, side by side. No diffing tool and no dependency | Susan |
  | 6 | The gates ship before the first panel they judge. A gate that lands with the panel it judges has no independent witness | Fowler |
  | 7 | **The gates enforce on an opt-in list, not on the whole console**, and `console.judged_panel_ids` is where that set lives - separate from `console.panel_groups` so capture still covers every panel. Twenty-six panels would fail three gates today, because `data-lede`, `data-comparison` and `data-settings-rule` exist nowhere yet. A panel joins `judged_panel_ids` in the pull request that redraws it | Fowler |
  | 8 | **The capture reaches 26 panels on two routes, not 51 on five.** Three routes draw no panel id at all; wrapping them is a route-plan row and is named in Hard scope - out rather than assumed | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `toHaveScreenshot` with committed baselines | Baselines go red for reasons nobody caused, and a gate people learn to re-bless is worse than no gate | Committed binary blobs the prune rewrites | Susan |
  | 2 | Full-page captures instead of clipped ones | A full page is large, so seven a panel stops being affordable, and a reviewer cannot tell which panel moved | Runner seconds and artefact bytes | Susan |
  | 3 | A hand-written array of panel ids in the spec | A panel added without a capture would ship unseen, which is the failure the gate exists for | Zero; costs the gate its completeness | Susan |
  | 4 | Enforce the gates on all 26 addressable panels at once | Three of the ten need attributes that exist nowhere in `frontend/src`, so every panel would fail three gates on the day the row lands. A gate that is red on arrival is a gate people learn to skip | Zero; costs the gate its credibility | Fowler |

---

### Row #7 - The query door module and its two entry points

- **Scope:** the three modules of the query door under `frontend/src/lib/data/`, and the hand-written index-shape copy the door reads. **No panel, no chart, no config change** - this is the shared reader every later panel calls, shipped with its own witness. **It depends on row 4** (it edits the vocabulary spec and the package manifest that row creates) **and on plan 50's index-task row** (its index-shape test binds to the Pydantic contracts that row declares); it needs no live published data, which is why plan 50's migration row can depend on it in turn.

**This is the N2 and N3 keystone.** Section 2.2 is its full contract: `ledger.ts` is the public door (`slice(ledger, {columns, from, to, where?})`, the closed `LedgerName`, the address composed inside the module); `engine.ts` is the only `@duckdb/duckdb-wasm` importer; `slice.ts` turns a date range into the coarsest-period file set with the one-file-per-date invariant. The engine is reached only through a dynamic `import()`, so it is not first-load.

- **Files touched:**
  - `frontend/src/lib/data/ledger.ts` (new: the public door and the closed `LedgerName`; **the address is composed here and nowhere else**)
  - `frontend/src/lib/data/engine.ts` (new: **the only module that imports `@duckdb/duckdb-wasm`**, single-threaded build, behind a dynamic `import()`)
  - `frontend/src/lib/data/slice.ts` (new: a date range to a file set, coarsest period per date, one file per date)
  - `frontend/package.json`, `frontend/package-lock.json` (`@duckdb/duckdb-wasm`)
  - `frontend/scripts/bundle-gate.mjs` (the `FORBIDDEN` list gains `@duckdb/duckdb-wasm` and its `.wasm` asset names, so a static import of the engine or its wasm fails the gate)
  - `frontend/tests/chart-vocabulary.spec.ts` (the single-engine walk now finds exactly one importer of the engine)
  - `backend/tests/contracts/test_frontend_index_shapes.py` (new: binds the hand-written `CompactEntry`, `CompactIndex` and `Watermark` copy in `ledger.ts` to the Pydantic originals plan 50 declares)
  - `frontend/tests/console-cold-load.spec.ts` (the engine is not first-load)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `pytest backend/tests/contracts -q`. `ci.yml`'s bundle gate and site-cap walk are re-read, because a package and a wasm asset landed. CI runs the full suite.
- **Oracle:** given recorded index and parquet responses for a fixture ledger, `slice()` returns exactly the requested columns for exactly the requested date range, reads each date through one file only, and renders `unreachable` on a hole; and `git grep -l duckdb -- frontend/src` returns exactly one path. It cannot settle whether a panel draws the result well; row 8 and Susan do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The door is its own row, not folded into the panel.** It is the keystone every one of plan 52's fifty panels calls, and plan 50 depends on it by name; a keystone ships with an independent witness | Fowler |
  | 2 | **`@duckdb/duckdb-wasm` is the reader, and this is how every panel reads every ledger** - no carve-out for size. The engine is fetched once and cached; a ledger downloaded whole would be fetched on every view by every reader, and that asymmetry holds at any size | Owner, 2026-09-24 |
  | 3 | **The single-threaded build is the pick.** The threaded one needs cross-origin isolation, which needs response headers a static host cannot set; the engine's own bundle selector already chooses correctly | Carmack. Written down so nobody spends a day discovering it |
  | 4 | **The engine is reached only through a dynamic `import()`, and the `FORBIDDEN` list enforces it.** Without that line the rule is a habit, and a careless static import lands the engine in first-load | Carmack |
  | 5 | **`where` is a structured predicate, never raw SQL.** The door binds each value as a query parameter, so no text a panel passes can become SQL (Guardrail #11) | Fowler |
  | 6 | **The door reads a hand-written copy of three shapes plan 50 declares** - `CompactEntry`, `CompactIndex`, `Watermark` - bound to the Pydantic originals by `test_frontend_index_shapes.py`, the same binding `test_frontend_field_set.py` already uses. This plan declares no new persisted contract | Fowler |
  | 7 | **A date is reachable through exactly one file.** The door takes the coarsest period covering a date; the oracle over the two-period rule lives with plan 50's index task, and this row consumes it | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fold the door into the panel (row 8) | The keystone would ship with no independent witness and could not be reverted without reverting the panel, and plan 50's dependency on this row's title would not resolve | Zero; costs the witness and the cross-plan pointer | Fowler |
  | 2 | Let a panel build its own path | A panel that could name a path could name any path, and the published list would stop being the bound | Zero; costs the trust boundary | Fowler |
  | 3 | Have the browser probe files until a 404 | A 404 stops being a defect signal and becomes a loop terminator, so a genuinely missing file reads as a normal end | Zero; costs telling an absence from a fault | Fowler |
  | 4 | A `where` clause of raw SQL | It is the Guardrail #11 surface: fetched text reaching the query. A structured predicate closes it | Zero; costs the boundary | Fowler |

---

### Row #8 - One panel end to end: the browser fetches the ledger and draws it in d3

- **Scope:** the Platform Mix panel (6b) queries the published `host-fingerprint` ledger through the query door for the columns and days it draws, and is redrawn in d3 to the vocabulary rows 4 to 6 established. **No backend change, no ledger change, no query-door change** - rows 3, 4, 5, 6 and 7 did those; this row draws one panel and joins the capture group.

**Why this panel.** `frontend/src/lib/charts/fleet.ts` has few importers, and the panel already takes an `svg` prop - the server-side renderer telemetry-intent N5 says exists only to serve ECharts - so this one panel is also the first evidence that renderer can go. It is the smallest thing that exercises the door, the vocabulary, the strip and the gates at once ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 1, which decides any scope argument inside this row).

#### The panel this row delivers

Ruled by Susan on 2026-09-24 against the panel as it stands, whose verdict was SEND BACK: sufficiency checks fail, two spans draw no mark, and the merged-kinds line ships a visible defect.

**The chart type is `dateSeries`, stacked** (section 2.6): the x-axis is the day, each day a stacked bar of machine kinds, returning `SeriesGeometry`. Its readout is the standard below-plot strip (`Readout`, section 2.7); it draws no second key and introduces no `beside` placement.

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

**Colour carries speed, ordered, bound to the whole record.** One hue, five steps (`console.machine_colour_stops`), ranked by each machine kind's median prompt throughput from `server_prompt_tokens / server_prompt_seconds` - both columns of `host-fingerprint`, so no second ledger is needed. **The five steps are quantile cuts over the whole record**, so a step stays stable as kinds are added and a machine keeps its colour when the operator changes the span - surviving the span control is the one thing this colour has to do. Not the confidence hues: a machine that draws slow is a draw, not a failure. A five-step key chip reads `slower` to `faster` and names each step's rate; the readout at a hovered day prints each kind's count that day, with its median rate as the series `note` (section 2.7); the drill-through prints the rate per job. No share, probability or pie returns.

| Case | Colour |
| --- | --- |
| Machine not recorded | `RESERVED_GREY`, flat, sorted last, outside the ramp |
| Known machine, no throughput reading | `RESERVED_GREY` with `ABSENT_HATCH` at `console.absent_hatch_degrees`, the row reads `no speed reading` |
| `Other machines` | allowed **only** over kinds that share one ramp step, named by the band (for example `machines near the slowest step`) |
| Kinds that do not share a step | do not merge. Merging the slowest into the middle is the one thing an ordered ramp cannot do |

**The merge rule and its precedence.** `console.fleet_top_kinds` bounds how many named kinds show before the rest fold into `Other machines`; the fold is allowed only over kinds that already share one ramp step. So `fleet_top_kinds` chooses *how many* named rows and the shared-step rule chooses *which* kinds may combine, and where they disagree the shared-step rule wins - a merge that crossed a colour step would lie about speed.

**Cost, stated: three panels share machine colour, so all three move together and all three must print the rate.**

**Under `console.fleet_min_rows` the panel changes shape rather than switching off.** When the rows in the open window are fewer than `console.fleet_min_rows`, the panel switches - once, automatically, with no manual toggle - to one mark per job: one column a day, one dot a job, coloured by machine, so all five spans draw something. A bar over small counts reads as `this much` and invites a rate a small count cannot support; a dot per job reads as `these ones` and cannot, because every mark is an individual a reader can point at.

**The drill-through.** A click or Enter on a day or a mark opens a list below the plot naming, per job, its run, job, shard, machine, seconds and rate. It reuses the rows already fetched for the window - no second `slice()` - is a tab stop, and closes on Escape or a click outside. A full-record context band under the plot shows where the open window sits in the whole record; it is indicative only, not a second span control.

**The three gate attributes this panel carries** (section 2.8): `data-lede` on the stacked-plot group, which is the lede; `data-settings-rule="none in window"`, because the settings-change rule tracks model settings that do not bear on which machine the platform handed us; and `data-comparison="composition"` with a `## Design rationale` line, because a stacked count over days is a composition, not a two-quantity comparison - the gate-5 exemption, not a miss.

**Four rules in the machine-pooling doc change, not one.** Besides the ramp reversal (decision 5): the under-threshold form becomes one dot per job (the doc's "a list with a sentence and no bar" was an ECharts-era rule); the doc's sentence that the route "is prerendered, so there is no fetch, no waiting state and no unreachable state" is removed, because this panel now fetches after mount; and the fold justification stops citing ECharts pixel widths. All four edits land in this row's commit.

- **Files touched:**
  - `frontend/src/lib/charts/fleet.ts` (the option builder becomes a d3 draw), `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (queries the door, draws in d3, drill-through), `frontend/src/routes/console/machine/+page.server.ts` (drops the build-time read of this panel's data)
  - `frontend/src/lib/server/host-fingerprint.ts` (this panel stops reading it at build time)
  - `config/appearance.json` (`console.machine_colour_stops` 7 to 5, `console.absent_hatch_degrees` new), `backend/idhazh/contracts/knobs/console.py` (the two knob changes, section 2.4)
  - `frontend/src/lib/server/config.ts` (the hardcoded `machine_colour_stops: 7` fallback moves to 5)
  - `frontend/src/lib/charts/machine-colour.ts` (**the arbitrary-key rule reverses to an ordered ramp - see decision 5**), `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`
  - `frontend/tests/console-machine-split.spec.ts` (the "Seven stops for a machine" assertion becomes five), `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-data.spec.ts`
- **Acceptance gates:** the browser smoke on `/console/machine` (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, and **the panel draws each of gate 8's four nothings**: `loading` before the door resolves, `missing` when its ledger is not published, `quiet` when the window is covered but empty, and `unreachable` when a date is a hole or the engine fails to start. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** given a recorded `slice()` response for one fixture day, the d3 panel draws one stacked bar per day with one segment per machine kind, the kinds in median-throughput order, the unrecorded kind last and outside the merged group, and every readout row carrying an absolute rate. **It is not a comparison against the ECharts panel**: this row rewrites `fleet.ts` from an option builder into a draw, so the old panel does not survive the commit, and the row changes the colour count, the shape under the threshold, the merge rule and the readout - so "same colours, same labels" would be false by design. It cannot settle whether the drawing is good enough to ship; Susan rules that (CLAUDE.md section 14).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The chart type is `dateSeries` stacked, and the readout is the standard below-plot strip.** An earlier draft placed a `beside` column justified by empty desktop space; that justification was a pixel measurement, and it is cut with the number | Susan, with Jony |
  | 2 | One panel, not the route. `/console/machine` draws many panels and prerenders; a row that moved it whole would carry `item-health`, the other panels and the prerender decision, and would prove no more about d3 than one panel does | Fowler |
  | 3 | ECharts stays installed. This row moves one importer; uninstalling is plan 52's last charting row | Fowler |
  | 4 | `console.machine_colour_stops` moves from 7 to 5 in this row. **The call sites in `machine/+page.server.ts`, the `config.ts` fallback and the "Seven stops" spec all move together**, or a silent mismatch ships | Susan |
  | 5 | **The machine ramp becomes ordered by speed, reversing the arbitrary-key rule `machine-colour.ts` declares in its own header.** That rule stopped colour implying an order the categorical ramp does not carry; an ordered single-hue ramp carries one by construction. **The reader loses** the guarantee that a machine keeps one colour as the record gains machines - a new fast kind shifts a slower kind down a step - which the quantile-over-the-whole-record binding minimises. The docstring and the machine-drawing page change in this commit | Susan, with Jony on the ramp |
  | 6 | **The under-threshold switch is automatic and single**, on `rows in window < console.fleet_min_rows`; no manual toggle. Two controls would be a layout decision the gates forbid leaving open | Susan |
  | 7 | **The drill-through reuses the window's rows** and issues no second `slice()`; it is a tab stop and closes on Escape. A second query for data already in hand is latency for nothing | Jony |
  | 8 | **Publishing, compaction and the index shape are not decided here.** Row 3 publishes, plan 50 compacts and declares the index and watermark shapes, and row 7 owns the door. This row reads through them and adds no rule of its own | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `RecordGates` on `/console/judgement`, with `targetbar.ts` | A larger blast radius (more importers) for a smaller proof, and it needs a chart type the nine do not yet host | Its own row later, once the house style exists | Fowler |
  | 2 | Keep the build-time read and swap only the drawing | It proves N5 and leaves N2 and N3 where they were, so the same panel gets done twice | Zero now; costs a second pass over one panel | Owner, 2026-09-24 |
  | 3 | Swap the drawing for every ECharts panel here | Many importers, five routes and the server-side renderer in one pull request, before any house style has been reviewed | Its own plan (52) | Fowler |
  | 4 | A `beside` readout placement for the wide viewport | It was justified only by a pixel measurement of empty desktop space, and it forks the shared readout contract row 5 just unified | Zero; costs the single readout contract | Susan |
  | 5 | Keep the machine ramp categorical | It cannot carry speed, which is the panel's whole point; the reader could not tell a fast machine from a slow one by colour | Zero; costs the panel its lede | Susan |

## Dependent plans

- `TODO/20260924-50-idhazh-gardener-plan.md`. Row 3 waits on its rows titled **The index task, two compact periods, and the diagram moves into the page** and **The three ledgers the console's routes read become parquet**. In the other direction, plan 50's row titled **The three ledgers the console's routes read become parquet** waits on this plan's row 7, titled **The query door module and its two entry points** - and row 7 depends only on row 4 and on plan 50's index-task row, neither of which reaches that migration, so row 7 lands first and the two pointers resolve without a cycle. Nothing else in that plan is a predecessor here.
- **[`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md), a placeholder and not yet a plan**, takes over after row 8. **The panel-by-panel verdict table Susan ruled now lives in plan 52** - all fifty-one panels, each KEEP, REDRAW, REPLACE, DELETE or NEW, with the columns each queries and the chart it becomes. Many of the redraws and new panels exist only because the browser can now query the ledger. One row per route; each row moves that route's panels to the query door and **deletes the projection under `frontend/public/` that fed them**. Rows 4 to 8 here exist to make that plan cheap, not to be it.
- **The old charts are evidence of an old limit, not a decision to preserve** (Susan). They were drawn against what a build-time projection could carry - a narrow, pre-summed slice of the columns - so columns of real answers sat unread on every run: why an article was chosen, why a fetch was slow, what the source answered, how old the news was, whether a summary was cut off and reported as a success, which rule refused a reply, and whether a trend moved because of the model or because somebody changed a setting. Plan 52 draws them.
- `TODO/20260823-known-defects-plan.md`, defect 33, closes in row 1's pull request.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan lays stones for.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every row here is built to.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
