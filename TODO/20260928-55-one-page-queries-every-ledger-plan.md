# Plan 55 - One page queries every ledger

**Last Updated**: 2026-09-28

**Level**: 5 (CLAUDE.md section 6). It adds a member to a persisted vocabulary (`RouteId` on the console band), it adds an entry point to the query door plan 51 declares, and it opens a surface where an operator's own text reaches a query engine.

**Chain** (CLAUDE.md section 0d). **Intent**: the owner looks through the project's own recorded data directly - pick the ledgers, pick the days, write the question, read the answer - without waiting for somebody to build a panel for it. **Contract**: section 2 declares every address, shape, key, knob and refusal these rows need, so a worker builds each row with no further decision. **Code**: the eight rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as a worker returns and never waiting on a merge; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every figure on the console is a panel somebody wrote for one question. A question nobody anticipated has no surface, and answering it means a clone, a Python session and a morning. This plan gives the owner one page that reads every ledger the project declares, over any span including today, with the query written by hand and the answer drawn as a table and as a chart. |
| The page, in one sentence | **An empty shell that prerenders nothing.** It arrives with no data in it; the reader picks ledgers and days, types a query and presses run, or arrives on an address that carries a query and presses run themselves. |
| Hard scope - in | - `/console/data-explorer/` is a sixth console tab, labelled `Records`, that **prerenders nothing** - a shell answered by the existing `404.html` fallback, which fetches everything it draws.<br>- The query door gains `ask()`: one read-only statement over a chosen set of ledgers and days, on an engine sealed against the network and the file system.<br>- Every ledger `config/ledgers.json` declares reaches the page's picker; every published one is queryable; an unpublished one says so by name.<br>- A span reaches **today**: packed month files, packed day files, and the writers' own files for days not packed yet, with each date read through exactly one tier.<br>- **What the build copies to the site is capped at the widest span the console can ask for**, so nothing reaches the site that no page could fetch.<br>- The answer is a table and, where its columns can carry one, a chart from the vocabulary plan 51 row 4 established.<br>- A query is saved in this browser, found again, and carried in the page address.<br>- The shared span control gets smaller and the console's default span becomes 14 days. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. **The page prerenders, or a loader returns data to it.** It ships an empty shell or it is not this page.<br>2. The engine gains network, file or extension access.<br>3. A statement that is not read-only reaches the engine.<br>4. An address runs a query instead of loading it into the editor.<br>5. A ledger is published that `config/ledgers.json` does not declare.<br>6. A second module imports the engine, or builds a published address.<br>7. `ConsoleBand` changes beyond gaining one route id.<br><br>**A new chart type is not an escalation** - it is Susan's call (plan 51 section 2.6). |
| Chosen strategy | Ship the shared chrome first (the span control, the tab), then the reader (`ask()` and the publishing), then the page, then what the page can do with an answer. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2, because six of the eight rows share `config/appearance.json` or the route directory. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Taking the six existing prerendered routes off prerender | `/`, `/archive/`, `/evals/` and the three console pages keep their documents. Telemetry-intent N4 stays in tension with plan 26's ruling, and this plan does not resolve it - it only stops N4 being read as a bar on a page that bakes nothing | [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) section 6, which is already written as executable rows and needs only the owner's word |
| A switch on the page that opens the engine seal | Nothing an operator can reach another way. The one capability the seal genuinely removes is joining a ledger against a file of your own, and a file the **page** reads and hands the engine as a buffer restores it without opening anything. **Reading the repository past the site's cap needs no switch either** - row 3 decision 8 does it with the page's own fetch | A config value in `config/appearance.json`, default off, with its removal condition on its declaring line - never a control in the page, because a switch reached by a shared address is a switch a stranger's query can find already on |
| Dropping a local file onto the page and joining a ledger against it | You cannot compare a ledger against a spreadsheet you hold. It is the only real loss the seal causes, and the seal is not what would need to move: the page reads the file with the browser's own file API and registers it as one more buffer | Its own row. About one component, one buffer registration and a column-type check, and it opens no network path |
| A download of any kind - CSV, Parquet, Arrow | You cannot open an answer in a spreadsheet. Row 7's copy-to-clipboard covers the case it was wanted for, and refusing a file also refuses the formula-injection surface a cell beginning `=` opens | Owner decision. It is one function and one button, and the cell-escaping rule comes with it |
| Writing anything back - a saved query committed to the repository, a query the pipeline runs | A saved query notices nothing when a column is renamed; it simply fails the next time you run it. Plan 50 already records that a committed, named query would be a reader for gate 7's purposes and this one is not | A row that gives a saved query a file under `config/`, its own contract and a test that runs it |
| A second engine, a second dialect, or a query language of our own | One dialect. An operator learns DuckDB SQL, which they can use anywhere else | Nothing. This is a refusal, not a deferral |
| Charts outside plan 51 section 2.6's vocabulary | The page draws what the console draws. An answer whose shape no type fits gets a table and a sentence saying why | Susan adds a type to the vocabulary page, which is a design call and not an escalation |
| Panel ids on `/console/model/`, `/console/voices/` and `/console/judgement/` | Inherited from plan 51. Those routes still draw no id, so no gate and no picture reaches them | Plan 52's route rows |
| The two-second lag between a run finishing and its rows being packed | Nothing. Row 4 reads the writers' own files for days not packed yet, so a span reaches the current hour | - |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star and sits above this plan (CLAUDE.md section 0d).

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N2 | The browser queries the parquet itself | **Delivered for arbitrary questions.** Plan 51 row 7 built the door for panels; row 3 here opens it to a question nobody wrote a panel for |
| N3 | The browser fetches its own data at view time | **Delivered whole on one route.** This page fetches the ledger registry, the indexes and the data after mount, and bakes none of it |
| N4 | Prerendering is an anti-pattern | **This route never prerenders.** It is the first console route with no document, and it is the proof that a console route can work that way. It does not remove the existing six; plan 26 section 6 owns that and this plan does not pre-empt it |
| N5 | d3 is the only charting library | **Inherited.** Row 6 draws only from plan 51 section 2.6's vocabulary |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Advanced.** Row 4 publishes the ledgers themselves and the registry that names them; nothing new enters git |
| N9, N10, N11 | The name, the two tiers, the one shard pattern | **Inherited** from plan 50. This plan mints no naming rule and declares no persisted shape of its own except one member on an existing vocabulary |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The span control loses its label and the console opens on fourteen days | - | A | PENDING | - | - | - |
| 2 | The strip gains a sixth tab and the band learns its route id | - | A | PENDING | - | - | - |
| 3 | The door answers a written question on a sealed engine | plan 51's row titled "The query door module and its two entry points" | B | PENDING | - | - | - |
| 4 | Every declared ledger reaches the site, and a span reaches today | plan 51's row titled "The three ledgers the console reads are published"; plan 50's row titled "One compaction task a ledger, two compact periods, and the diagrams move into the page" | B | PENDING | - | - | - |
| 5 | The page: pick the ledgers and the days, write the question, read the table | 2, 3, 4 | C | PENDING | - | - | - |
| 6 | The answer gets a shape, or says why it cannot have one | 5 | D | PENDING | - | - | - |
| 7 | A question is kept, found again and shared | 5 | D | PENDING | - | - | - |
| 8 | The glyphs, the gates, the pictures and the page that says how to use it | 1, 5, 6, 7 | E | PENDING | - | - | - |

**Readiness is the file-disjointness test, not the group letter** (execute-a-plan.md).

**Rows 1 and 2 run two-wide.** Row 1 holds `WindowControl.svelte`, `WindowStatus.svelte` and the `default_window_days` value; row 2 holds `console_band.py`, `band.ts`, `ConsoleNav.svelte` and the `panel_groups` key. They share `config/appearance.json` and `backend/idhazh/contracts/knobs/console.py` and edit different keys of each, so whichever merges second takes main in first.

**Rows 3 and 4 run two-wide.** Row 3 is frontend query code under `frontend/src/lib/data/`; row 4 is backend config, the copy step and the ceilings. Disjoint.

**Rows 6 and 7 run two-wide.** Row 6 holds the chart components; row 7 holds the saved list, the history and the address. Both import the page from row 5 and neither edits the other's files. They share `frontend/src/routes/console/data-explorer/+page.svelte`, so they merge in order and the second takes main in first.

**Row 5 is the keystone and cannot be split.** It creates the route, the panel shells, the ledger picker, the editor and the table in one commit, because there is no intermediate state where the route exists and draws nothing - a console route that renders an empty page is a tab that lies.

**Row 8 lands last on purpose.** Its pictures are of the finished panels, so it cannot run before the panels exist, and its icon set is sized from what rows 5 to 7 actually reach for rather than from this document's guess.

**Why row 1 is in this plan at all.** The span control is shared by every console route, so shrinking it is not this page's change - but this page is the first surface where the control sits beside a second control on the same row, and the owner ruled the shape here (2026-09-28). It ships first so rows 5 to 7 build against the final control rather than against one that moves under them.

**What can start, and what waits, measured 2026-09-28 by plan 51's owner.** This plan is AUTHOR-AND-STOP until the owner authorizes it. Once authorized:

| # | Rows | Can start | Why |
| --- | --- | --- | --- |
| 1 | 1 and 2 | After plan 52's first row merges | They wait on no other plan's data. But plan 52's row titled **Each route gets its own console file, gate drivers and test expectations** moves `console.panel_groups` and the other console keys out of `config/appearance.json` into one file a route, and rewrites `console-nav.spec.ts` and `console-window.spec.ts`. Run beside it, both rows here edit keys while they move. That row depends on nothing |
| 2 | 3 | After plan 51's row 9 merges | Its dependency, plan 51's row 7, merged on 2026-09-28 (#1154). Plan 51's row titled **The door keeps what it fetched for the page's life, and says how far a ledger reaches** edits the same files - `ledger.ts`, `slice-reader.ts`, `engine.ts` - and puts every buffer the door registers under `door/`, which section 2.6's seal needs. That row needs only row 7, so it is ready now |
| 3 | 4, then 5 to 8 | After packed files are on main | Row 4 extends plan 51's row 3, which publishes packed files, and none exist: `state/compact/` is absent on main, and plan 50 ships every packing task report-only. The three console ledgers also wait on plan 50's row titled **The three ledgers the console's routes read become parquet**, not started, and on a person turning their packing on. Rows 5 to 8 wait on row 4 |

**So rows 1 to 3 can run as soon as those two rows merge, and rows 4 to 8 wait on plan 50 and on a person's call to turn packing on.**

## 2. The contracts

### 2.1 The address, the tab, and the route id

| # | What | Value |
| --- | --- | --- |
| 1 | Address | `/console/data-explorer/` |
| 2 | Route id | `data-explorer`, a new member of `RouteId` in `backend/idhazh/contracts/console_band.py` and of the `RouteId` union in `frontend/src/lib/console/band.ts` |
| 3 | Tab label | `Records` |
| 4 | Tab description | `Ask the project's own record a question, and read the answer.` |
| 5 | What it carries from another route | `The tabs either side of this one draw the questions somebody already asked.` |
| 6 | Panel group | one group, id `data-explorer`, title `""` - the Pipelines shape, because what the three panels need is an order rather than a grouping |
| 7 | Panel ids, in order | `data-explorer-ask`, `data-explorer-rows`, `data-explorer-shape` |

**The id and the label differ on purpose, and that is the established pattern**: `model` is labelled `Summaries` and `machine` is labelled `Hardware`.

**Adding a route id is additive and has a precedent in the same file.** `ConsoleBand.__changelog__` already carries `2026-09-12 - RouteId gains the route ids judgement and voices. Additive: an older payload names three of the five and validates unchanged.` This row appends one entry of the same shape and moves `version`. A band payload written before this row names five routes and still validates; the frontend draws a tab for every route the payload carries and nothing for one it does not, so an old payload costs the tab and never the page.

### 2.2 This route prerenders nothing, and that is a shipped pattern rather than a new argument

`frontend/src/routes/console/data-explorer/+page.ts` declares both:

```ts
export const prerender = false;
export const ssr = false;
```

| # | Fact | Read from |
| --- | --- | --- |
| 1 | The static adapter already has a fallback | `frontend/svelte.config.js`: `adapter({ fallback: '404.html', strict: false })` |
| 2 | Two routes already ship no document and are answered by that fallback | `frontend/src/routes/[date]/+page.ts` and `[date]/[vertical]/+page.ts`, both `export const ssr = false` |
| 3 | What the fallback costs | GitHub Pages serves `404.html` with an HTTP 404 status. The dated routes have lived with it since 2026-09-09 |
| 4 | What this route does **not** cost | Every item in plan 26 section 6 is about converting one of the six existing routes: re-homing a server load, re-pricing a ceiling that measures prerendered HTML, rewriting a spec that reads the prerendered document, re-drawing a server-drawn chart. A route that never prerendered has none of those, and this route has no `+page.server.ts` at all |

**The page's only input is what it fetches.** No loader returns data, so there is nothing a build could bake in, which is the property telemetry-intent N4 is actually about.

**No other plan's trigger fires, and this plan edits none of them.** Plan 51's first ESCALATE trigger is "a tenth prerendered route, or retiring an existing one"; this route is not prerendered and retires nothing, so the trigger does not reach it. Telemetry-intent N4's first clause - no new prerendered data page - is satisfied twice over. **Its second clause, that the existing ones come off, still disagrees with plan 26's delivered ruling on main**; that contradiction is older than this plan, belongs to plan 26 section 6, and is not repaired here.

### 2.3 The door answers a written question

Row 3 adds one export to `frontend/src/lib/data/ledger.ts`. Everything else in plan 51 section 2.2 is unchanged: `slice()` stays, `sliceFromDisk()` stays, `engine.ts` stays the only importer of the engine, and the address is still composed inside `ledger.ts` and nowhere else.

```ts
/** Run one read-only statement over a chosen set of ledgers and days.
 *  The caller chooses the ledgers and the span; the statement shapes the answer
 *  and never chooses a file. */
export async function ask(opts: AskOptions): Promise<AskResult>;

export type AskOptions = {
	/** Non-empty. Each becomes one table of the same name, hyphens and all -
	 *  a statement quotes it as "item-health". */
	ledgers: readonly LedgerName[];
	from: DateStamp;
	to: DateStamp;
	/** One read-only statement. Refused before the engine sees it if it is not. */
	sql: string;
	/** From `console.explorer_max_rows`. The answer stops here and says so. */
	maxRows: number;
};

/** One column of the answer, as the engine describes it. */
export type Column = { name: string; type: string };

/** What the fetch actually cost, so the page prints a reading and never a guess. */
export type FetchCost = { files: number; bytes: number; fromCache: number; ms: number };

export type AskResult =
	| { state: 'ok'; columns: readonly Column[]; rows: Row[]; capped: boolean; read: FetchCost }
	| { state: 'quiet'; columns: readonly Column[]; read: FetchCost }
	| { state: 'missing'; ledger: LedgerName }
	| { state: 'unreachable'; at: DateStamp }
	| { state: 'refused'; because: string };
```

**`ask` rather than `query`.** The module is already called the query door, so `query()` beside `slice()` would put the same word in two jobs one sentence apart (CLAUDE.md section 0b).

**`LedgerName` widens to every name `config/ledgers.json` declares.** It is 26 names today. It stays a hand-written closed union in `ledger.ts` and a backend test binds it to the registry in both directions, the same binding `test_frontend_vocabularies.py` already uses. A panel still names a ledger and never a path.

**The columns come from the engine and from nowhere else.** The page runs `DESCRIBE` against the registered tables to fill the schema panel, and reads the answer's own columns off the result. There is no second copy of a ledger's column list to keep in step.

### 2.4 What bounds the bytes: the span control, never the statement

| # | Rule |
| --- | --- |
| 1 | The caller names the ledgers and the days. `slice.ts` turns that into a file set exactly as it does for a panel |
| 2 | Each file is fetched whole and handed to the engine as a buffer, registered under a table name. There are no byte-range requests anywhere in this plan |
| 3 | **The statement never names a file, a path or a URL.** It sees table names and nothing else. A statement that could name a path could name any path |
| 4 | The page prints what the span will cost - files and bytes, from the indexes - **before** the run, and what it actually cost after |
| 5 | Guardrail #12 is satisfied by the span, not by the archive: the first view fetches `console.default_window_days` of the selected ledgers and no more, however long the project has been running |

### 2.5 A span reaches today, through three kinds of file

**Each date is read through exactly one tier.** The door takes, per date, the first of these that covers it:

| # | Tier | Address | When it covers a date |
| --- | --- | --- | --- |
| 1 | Packed month | `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet` | The whole month is packed |
| 2 | Packed day | `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet` | That day is packed |
| 3 | The writers' own files | `state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet`, every name in that day's `RawDayIndex` | The day is not packed yet |
| 4 | **The same file in the repository** | `<ledger.archive_base_url>/state/compact/<ledger>/...` | The date is older than what the site carries (section 2.5's cap), and the repository still holds it |

**Nothing is missing to build this.** `RawDayIndex` is already declared in `backend/idhazh/contracts/ledger_index.py` by plan 50 - the ledger, the date, the file names for that day, and when they were listed. The browser cannot list a directory, and this is the file that means it does not have to.

**A date in two tiers is a defect, not a merge.** Reading one date twice doubles every number on the answer, which is the defect class filed as 33. The oracle in row 4 asserts one tier per date over a fixture ledger carrying all three kinds.

**The writers' own files are not packed, so they cost more per day.** One request per writer file instead of one for the day. This is why panels stay on packed files: a panel draws on arrival for every reader, and this page fetches when an operator presses a button. Row 5 prints the file count before the run, so the cost is visible at the moment it is chosen.

**Where the three kinds disagree, the packed file wins by being the only one read.** Plan 50's packing applies each ledger's own merge rule while it builds the file, so a packed day holds one row per record. The writers' files for an unpacked day hold what the writers wrote, which can be two rows of one record for a ledger whose merge rule is a cell union. Row 4's oracle asserts the row count of a day read as writers' files equals the row count of that day once packed, for a fixture ledger with such a rule, or names the difference. **A difference that cannot be removed is printed on the page** rather than hidden: the status sentence says which dates came from unpacked files.

#### What reaches the site is capped at the widest span, not at what `state/` holds

**The publishing decision is site-wide; the cap on it is derived from config.** There is one staged tree, served at one address, and any page may fetch any of it - so this is not a per-route setting and no row here invents one. What the cap does is refuse to copy a file no page could ask for.

| # | Rule |
| --- | --- |
| 1 | The build copies the periods covering the last `max(console.window_presets)` days, rounded out to whole monthly files, because a month is the unit a monthly file comes in |
| 2 | The raw tier is copied only for dates no packed file covers, which plan 50's packing rule already bounds to a day or two |
| 3 | **The number is read from config, never written down.** `window_presets` is `[1, 7, 14, 30, 90]` today, so the copy reaches back 90 days plus the part-month at the far end. Adding a wider preset widens the copy with no source edit, which is the substitution test (Guardrail #6) |
| 4 | **What `state/` holds is a different question and belongs to plan 50's keep windows.** Git keeps the history; the site carries the part a reader can reach |

**This is what makes row 4 safe to run over twenty-six ledgers.** Without it the copy would grow with the archive for as long as the project runs, which is Guardrail #12 pointed at the site rather than at a runner.

#### Past the cap, the page reads the repository, and the seal stays shut

**The cap costs the reader nothing, because the same file is already published somewhere else.** `state/` is committed, the repository is public, and a browser can read a committed file directly. So a date older than the site carries is fetched from the repository instead, and only the address changes.

**Measured 2026-09-28**, against a committed file on `main`:

| # | What was read | Value |
| --- | --- | --- |
| 1 | Repository visibility | public |
| 2 | Status for `<archive base>/state/host-fingerprint/2026/09/16/settled.csv` | 200, 350 bytes |
| 3 | `access-control-allow-origin` | `*` - so a browser may read it from our own page |
| 4 | `cache-control` | `max-age=300`. A packed file never changes, but this host re-validates after five minutes, so a repeated query over old dates pays the fetch again |
| 5 | `accept-ranges` | `bytes`. Noted and unused - this plan makes no range requests |

**The page fetches it; the engine never does.** `ledger.ts` composes the archive address exactly as it composes the site address, fetches the file, and hands the engine one more buffer. **No engine setting changes and no trigger fires**: the engine still cannot open a URL, load an extension or reach a file the door did not give it.

| # | Rule |
| --- | --- |
| 1 | The address is `ledger.archive_base_url`, **a committed value in `config/idhazh.json`**, joined onto the same committed path. An environment value is not an acceptable control for a destination (Guardrail #11) |
| 2 | `connect-src` gains that one origin, computed from the same config value in `frontend/asset-base.js`, so the address and the browser's own policy cannot disagree - the pattern `visuals.asset_base_url` already uses |
| 3 | **What widening `connect-src` admits, stated rather than implied.** The origin serves files and accepts none, so nothing can be sent to it; what it adds is that a query can read any public file on that host, which is already public. It cannot reach any other host, because `connect-src` still names only these |
| 4 | Where the value is empty the page reads the site only, and a date past the cap answers `unreachable` with its date. The empty default is what a fresh clone runs on |
| 5 | The repository's own keep windows decide how far back this reaches. Where the repository no longer holds a date either, the answer is `unreachable` and says which date |

**What this buys, plainly: the site carries ninety days and the page can still answer a question about last spring.**

### 2.6 The engine is sealed, and the seal is structural

Four controls, strongest first. Row 3 proves each one rather than assuming it.

| # | Control | What it stops |
| --- | --- | --- |
| 1 | Only buffers the door registered are visible, and **every one sits under one directory, `door/`**. `registerFileBuffer` only; **`registerFileURL` is never called** | The statement cannot reach a file the door did not fetch |
| 2 | Once per engine, before this page's first statement: `LOAD parquet`, then `SET allowed_directories = ['door/']`, then `SET enable_external_access = false`, `SET autoinstall_known_extensions = false`, `SET autoload_known_extensions = false`, and last `SET lock_configuration = true`. **The order is part of the control**: the engine refuses `allowed_directories` once access is off, and loads no add-on after it | `read_csv('https://...')`, `ATTACH`, `INSTALL`, `LOAD`, a file outside `door/`, and the statement turning any of them back on |
| 3 | The page refuses, before the engine sees it: more than one statement; anything that is not `SELECT`, `WITH ... SELECT`, `DESCRIBE`, `SUMMARIZE` or `EXPLAIN`; and a statement longer than `console.explorer_query_max_chars` | A write - including a `COPY` into `door/`, which control 2 does not stop - a schema change, and a paste large enough to stop the tab responding |
| 4 | `connect-src 'self'`, the configured asset base, and the origin of `ledger.engine_extension_repository`, where the engine fetches its parquet add-on (plan 51 deviation 15), all computed in `frontend/asset-base.js` | Anything that got past 1 to 3 reaching a third party |

**Measured 2026-09-28 by plan 51's owner, and controls 1 to 3 are written to it.** In Node, on the engine build plan 51 ships - DuckDB v1.5.4 inside `@duckdb/duckdb-wasm` 1.33.1-dev57.0 - one fresh engine a case, reading one parquet file from `tests/fixtures/ledger-door/`. A browser runs the same engine code; row 3's own seal test, in a browser, is the check.

| # | What ran | What happened |
| --- | --- | --- |
| 1 | The four settings as this section first wrote them, then a read | `read_parquet` does not exist. The parquet reader is an add-on this build downloads, and autoload is off |
| 2 | `LOAD parquet`, the four settings, then a read | Refused: `enable_external_access = false` blocks every registered buffer, registered before the seal or after it |
| 3 | `LOAD parquet`, `allowed_directories = ['door/']`, the four settings | A buffer under `door/` reads. A buffer outside it, `read_csv('https://...')`, `LOAD httpfs`, `ATTACH` and turning access back on are all refused |
| 4 | `allowed_directories` set after access is off | Refused by the engine, so control 2's order is the only one that works |
| 5 | Everything but `enable_external_access = false` | Buffers read, but `LOAD httpfs` succeeds and `read_csv('https://...')` sends a request. That one setting is the seal |
| 6 | `COPY (SELECT 1) TO 'door/x.csv'` under order 3 | Not refused by the settings: it reached the engine's file layer. Control 3 is what refuses it |
| 7 | Sealed from one connection, then read from a second connection on the same engine | The second is sealed too. The settings belong to the engine, not to a connection |

**The seal belongs to the engine, so it reaches every panel in the tab.** `engine.ts` starts one engine a tab, and moving between console pages keeps it. Once this page has sealed it, every console panel opened afterwards in that tab reads through the sealed engine, so every buffer the door registers - `slice()`'s as well as `ask()`'s - sits under `door/`. Plan 51's row titled **The door keeps what it fetched for the page's life, and says how far a ledger reaches** puts them there; row 3 builds on it, and row 3's oracle checks that a `slice()` still answers after this page has sealed the engine.

**The engine is not pinned to an exact version, and the seal is held by a test rather than by a pin.** `frontend/package.json` takes `@duckdb/duckdb-wasm` at a caret range, the way every other dependency here is taken, so an upgrade is a normal upgrade. The hostile-query set below runs against whatever version is installed, so a release that changed one of these settings turns that test red on the pull request that raised the version - which is where somebody wants to find out, and which a pin would only have delayed. **If a release ever removes one of them, the answer is the previous working version, not a text rule over the statement**: a text rule is a denylist, and a denylist over a language with function syntax is not a boundary.

**The hostile set the oracle runs**, each asserted refused:

```
SELECT * FROM read_csv('https://example.invalid/x.csv')
COPY (SELECT 1) TO 'x.csv'
ATTACH 'x.db' AS other
INSTALL httpfs
LOAD httpfs
SET enable_external_access = true
SELECT 1; DROP TABLE "item-health"
CREATE TABLE t AS SELECT 1
SELECT * FROM "item-health"    -- refused: no columns named
SELECT * FROM read_parquet('elsewhere.parquet')
COPY (SELECT 1) TO 'door/x.csv'    -- control 2 lets this through; control 3 refuses it
```

### 2.7 Every cell is text, and nothing on this page can change that

Guardrail #11. A ledger carries text that came off the open web - an article title, a source address, a server's error string.

| # | Rule | How it is held |
| --- | --- | --- |
| 1 | No `{@html}` anywhere under `frontend/src/routes/console/data-explorer/` | An import and source walk in the route's own spec |
| 2 | A cell is never a link, an image source, a fetch address or a style value, whatever it looks like | The spec renders a fixture row whose cells hold `<script>alert(1)</script>`, `javascript:alert(1)`, `=cmd\|' /c calc'!A1` and `https://example.invalid/x`, and asserts the rendered subtree has no `<a>`, no `<script>`, no `<img>`, and visible text equal to the cell |
| 3 | A column name comes from the engine's schema, never from a cell | `Column.name` is the only source the header reads |
| 4 | A ledger name in a fetch address comes from `LedgerName`, never from typed text | The union is closed and `ledger.ts` composes the address |

**The spreadsheet-formula case is closed by refusing the download**, not by escaping: there is no file for a spreadsheet to open (section 0, hard scope - out).

### 2.8 The answer: the table, then the shape

**The table.**

| # | Behaviour | Knob |
| --- | --- | --- |
| 1 | Sticky header; a row-number column; each header carries the column's type from `DESCRIBE`; numbers right-aligned in tabular figures | - |
| 2 | Headers sort. The sort runs in the engine over rows already in memory - no second fetch | - |
| 3 | One page of rows at a time, with `show more` | `console.explorer_row_page`, default 50 |
| 4 | The answer stops at a ceiling and says so, naming the ceiling and suggesting a narrower span | `console.explorer_max_rows`, default 1000 |
| 5 | A numeric cell carries an in-cell bar proportional to its value within its own column | - |
| 6 | The panel may be widened to the route's full width | - |

**No cell is tinted by value.** A colour that means "bad" needs a rule, and this page cannot have one: it does not know which of 26 ledgers' values are bad. The bar in rule 5 is a comparison a reader makes; a red cell is a verdict nobody issued.

**The shape.** The chart type is chosen from the answer's own columns, first match wins:

| # | The answer holds | The type | Knob that floors it |
| --- | --- | --- | --- |
| 1 | one date or timestamp column and at least one numeric | `dateSeries` | `console.explorer_chart_min_rows` |
| 2 | one text column and exactly one numeric | `rankedList` | `console.explorer_rank_max` |
| 3 | exactly two numeric columns | `pairedScatter` | `console.explorer_chart_min_rows` |
| 4 | exactly one numeric column | `distribution` | `console.explorer_chart_min_rows` |
| 5 | none of the above, or below the floor | no chart | - |

The operator may choose any type that qualifies, as a radio group. **Where no type qualifies the shape panel draws `refused` with the reason in plain words** - `Nothing here to draw: the answer has no number in it.` - and it stays; it is not a dismissible alarm, because it is a normal outcome.

### 2.9 Six states, told apart

`frontend/src/lib/console/waiting.ts` already owns `loading`, `quiet`, `missing`, `unreachable` and `too-few`. Row 5 adds two to that module and mints no second vocabulary (Guardrail #4).

| # | State | What it means here |
| --- | --- | --- |
| 1 | `loading` | The engine, the indexes or the files are on their way |
| 2 | `quiet` | The statement ran and matched no rows |
| 3 | `missing` | A chosen ledger is declared but not published |
| 4 | `unreachable` | A date in the span is named by no index of any tier |
| 5 | `refused` | **New.** The statement did not run. The page refused it, or the engine did, and the reason is shown as text. It is not a fetch that failed, which is what `unreachable` already means |
| 6 | `capped` | **New.** The answer reached `console.explorer_max_rows` and stopped. The rows shown are real; the answer is not the whole one |

### 2.10 The knobs this plan mints or moves

Every value below is a knob (Guardrail #6), in `config/appearance.json` with its model in `backend/idhazh/contracts/knobs/console.py` unless stated.

| Key | Status | Value | Read by |
| --- | --- | --- | --- |
| `console.default_window_days` | **Exists at 30, becomes 14** | `14` | Row 1. Every console route opens on it. It is already in `window_presets`, so the model's own validator passes unchanged |
| `console.window_presets` | Exists as `[1, 7, 14, 30, 90]` | unchanged | Row 1 draws one tile per value. **No second key naming the same values** |
| `console.explorer_row_page` | **New** | `50` | Row 5's table. How many rows one press of `show more` adds |
| `console.explorer_max_rows` | **New** | `1000` | Rows 3 and 5. The most rows one answer holds. Past it the answer is capped and says so, because a browser that renders an unbounded answer stops responding and the message arrives after the freeze |
| `console.explorer_query_max_chars` | **New** | set by row 7 from the measured address limit | Rows 3, 5 and 7. The longest statement the box accepts. **Row 7 sets it from a reading, not from this document** - it measures the longest address GitHub Pages answers, and sizes it so any statement that fits the box also fits a link |
| `console.explorer_chart_min_rows` | **New** | `3` | Row 6. Below it no chart is drawn: two points define a line, so a chart of two is a claim |
| `console.explorer_rank_max` | **New** | `30` | Row 6. The most rows a `rankedList` draws |
| `console.explorer_saved_max` | **New** | `20` | Row 7. How many saved questions this browser keeps. The oldest goes when it is full and the page says which |
| `console.explorer_history_max` | **New** | `10` | Row 7. How many recent runs the list holds |
| `console.explorer_examples` | **New** | the five in section 2.11 | Row 5's example strip. A list of `{id, title, note, ledgers, days, sql}` |
| `console.panel_groups["data-explorer"]` | **New** | section 2.1 row 6 | Rows 2 and 8 |
| `console.judged_panel_ids` | Exists as `[]` | gains the three panel ids | Row 8 |
| `icons.stroke_width` | **New**, in the `icons` block | set by row 8 from the pictures | Row 8. One stroke width for the whole glyph set. Lucide ships at 24 px with a 2 px stroke and the set is drawn at `icons.size_px` 16, so the shipped weight reads heavier than the type beside it. **The value is chosen from the pictures at 390 in both themes, not from this document**; 1.5 is where the row starts |
| `ledger.archive_base_url` | **New**, in `config/idhazh.json` beside `ledger.published` | ships **empty**, which means the site only | Row 3's address composer and `frontend/asset-base.js`'s `connect-src`. The host that serves the committed repository, for dates older than the site carries (section 2.5). **Committed, never environmental**, because it is a destination (Guardrail #11). Empty is the shipped default and is what a fresh clone runs on |
| `page_weight.payload_ceilings_bytes` | Gains entries | set by row 4 from the built files | Row 4, in `config/idhazh.json`. One per published ledger's `index/daily.json`, plus one for `ledgers.json` |

### 2.11 The example questions

Five, in `console.explorer_examples`. Each names the ledgers it needs, so a chip over an unpublished ledger says so instead of failing on run.

| # | id | Title | Ledgers | Days |
| --- | --- | --- | --- | --- |
| 1 | `p99-by-machine` | p99 job time by machine kind | `host-fingerprint` | 14 |
| 2 | `throughput-by-machine` | Prompt throughput by machine kind | `host-fingerprint` | 14 |
| 3 | `feeds-gone-quiet` | Feeds with no good fetch in the span | `feed-health` | 14 |
| 4 | `why-items-failed` | What failed to summarize, and why | `item-health` | 14 |
| 5 | `step-time-by-shard` | Where a run's time went, by step and shard | `span-rollup` | 7 |

**The observability words stay the observability words** (owner, 2026-09-28): `p50`, `p99`, throughput, cardinality, dimension. **One word is retired from this page because it already means something else here**: `grain` is a Pydantic enum naming how a ledger files - `day`, `tree`, `month`, `flat`, `stamp`, `raw-and-compact`. A time bucket is a **bin**, which is the word the reference screenshot itself uses in its readout.

### 2.12 What the page takes from the reference screenshot, and where the reference stops

The owner's reference is a query workbench screenshot and its HTML, kept at `test-results/telemetry_parquet_query_visualizer/code.html`. **Sixty of its seventy-four features ship; fourteen do not.** The full inventory with a verdict and a reason per feature is [docs/concepts/console-design/what-the-data-explorer-borrowed.md](../docs/concepts/console-design/what-the-data-explorer-borrowed.md), written by row 8. Three rules decide every rejection and they are worth stating here because they also decide anything added later.

| # | Rule | What it rejected |
| --- | --- | --- |
| 1 | **A number on this page is a reading or it is not printed.** | `Scanned 6.8 GB`, `AVX-512`, `PARALLEL THREADS: 12`, `Arrow IPC Cache Hit: 94.1%`. Rows 5 and 6 print milliseconds, files, bytes and rows, each measured |
| 2 | **The console owns a job once.** | The left icon rail, the breadcrumb, the collapse-all. The tab strip, the span control and the panel frame already exist |
| 3 | **A verdict needs a rule.** | The green and red status badges, the value coloured red for being high, the animated ring on the point labelled an anomaly. None of them has a rule behind it that this page could hold |

**The glyphs are taken; the font is not.** The reference draws Material Symbols from a Google font. This repository already has an icon system - Lucide, ISC licence, committed as source SVG, drawn from a generated sprite by id, with `frontend/tests/icons.spec.ts` failing both on a glyph nothing draws and on an id that does not exist. Row 8 adds the marks the page needs to that set, at one stroke width, with one provenance file and no third-party request.

## 3. Rows

### Row #1 - The span control loses its label and the console opens on fourteen days

- **Scope:** `WindowControl.svelte` becomes the reference's shape - five short tiles reading `1D 7D 14D 30D 90D`, no standing label and no per-tile price - and `console.default_window_days` becomes 14. **Every console route takes both changes**, which is the cost and is stated in the pull request.

| # | Now | Becomes |
| --- | --- | --- |
| 1 | `Days shown` printed beside the tiles at every width | Gone from the eye. The `<legend class="sr-only">` stays, so a screen reader still hears the group's name, and the `D` on each tile carries the unit |
| 2 | Tiles read `1 7 14 30 90` | `1D 7D 14D 30D 90D` |
| 3 | Every tile reserves a second line for a `+2 months` price whether or not one is due | Gone from the tiles. **The price moves into `WindowStatus.svelte`**, the sentence that already stands under the strip, so the no-jump property the reserved room bought is kept by a line that was always there |
| 4 | `default_window_days` is 30 | 14 |

- **Files touched:**
  - `frontend/src/lib/components/WindowControl.svelte` (the label, the tile text, the price room and its `priceRoom` prop and styles)
  - `frontend/src/lib/components/WindowControlSource.svelte` (the same two changes, or a note in the pull request saying why its shape differs)
  - `frontend/src/lib/components/WindowStatus.svelte` (it gains the price sentence)
  - `config/appearance.json` (`console.default_window_days` 30 -> 14), `backend/idhazh/contracts/knobs/console.py` (the field default, and its description says why 14)
  - `frontend/src/lib/server/config.ts` (the fallback default moves with it)
  - `frontend/tests/console-window.spec.ts`, `frontend/tests/console-window-claims.spec.ts`, `frontend/tests/console-chrome.spec.ts` (the label assertion, the price assertion and any assertion naming 30 days)
  - `tests/fixtures/` - every every-knob config fixture carrying `default_window_days`
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`; the browser smoke on all five existing console routes at 390, 768 and 1440 in both themes. CI runs the full suite.
- **Oracle:** **the control got smaller and nothing below it moved.** Measured in a browser on the built console at 390, 768 and 1440 in both themes: the control's own bounding box is smaller than before on at least one axis at every width, the page's total height is unchanged or smaller, and **selecting each of the five presets in turn moves no element below the strip by more than one pixel** - which is the property the reserved price room was bought for and the one a smaller control could silently lose. It cannot settle whether the new shape reads better; Susan does.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The reference's shape is the shape**: five short tiles, no label, no box, no icon | Owner, 2026-09-28 |
  | 2 | **The unit lives on the tile, not in a label.** `1D` says the same thing in one character that `Days shown` says in ten, and the screen-reader legend is untouched | Susan |
  | 3 | **The price keeps a permanent home, and it is the status sentence.** A price that appears and disappears moved seven panels by 15 px when it landed or cleared, measured 2026-09-09. Moving it to a line that is always drawn keeps that fixed and takes the height back | Susan, with Jony; the measurement is the control's own |
  | 4 | **14 days is the default on every route.** One default, or two routes answer the same question over different spans and a reader cannot compare them | Owner, 2026-09-28 |
  | 5 | **This row ships before the page.** Rows 5 to 7 build against the final control, not one that moves under them | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fork a smaller control for this page only | Two controls for one question, and two windows a reader cannot compare. The control's own docstring is about exactly this | Zero to take; costs the single-window property | Susan |
  | 2 | Keep the label and only drop the price room | Saves the vertical and not the horizontal, and the horizontal is what pushes the control off the strip when a sixth tab arrives | Zero; costs the strip its room | Susan |
  | 3 | Drop the price entirely | The wide span costs month files and a reader would meet the cost after choosing it | Zero; costs the reader the price before they pay it | Carmack |

---

### Row #2 - The strip gains a sixth tab and the band learns its route id

- **Scope:** `RouteId` gains `data-explorer` on both sides, the band's route list gains its entry, the strip draws a sixth tab, and `console.panel_groups` gains the route with its three panel ids. **No page** - the tab points at a route row 5 creates, so this row ships behind a config flag, default off, whose removal condition is row 5's merge.

- **Files touched:**
  - `backend/idhazh/contracts/console_band.py` (`RouteId.DATA_EXPLORER`, one `ChangelogEntry`, the `version` stamp, and the enum's docstring which says "the five console routes")
  - `backend/idhazh/telemetry/publish/console_band.py` (`ROUTES` gains its tuple; the `carries` sentence)
  - `frontend/src/lib/console/band.ts` (`RouteId`, `ROUTE_IDS`, `ROUTE_WORDS`, and the module docstring which says "the console is five routes")
  - `frontend/tests/console-nav.spec.ts` (the third hand-typed copy of the route words)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`panel_groups` gains the route; the field description names it)
  - `config/idhazh.json` (the flag, default off), `backend/idhazh/contracts/knobs/` (its model, with the removal condition on the declaring line)
  - `backend/tests/contracts/test_console_band.py`, `frontend/tests/console-shell.spec.ts`, `frontend/tests/console-band.spec.ts`
  - `docs/architecture/publishing/console-payloads.md` (the route list)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks; the browser smoke on `/console/` with the flag on and off. CI runs the full suite.
- **Oracle:** **an old payload still draws a console.** A band payload written before this row - the committed sample, naming five routes - validates against the new contract unchanged, and the strip drawn from it has five tabs and no gap. A payload naming six draws six. It cannot settle whether the label is the right word; Susan and Reader do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Adding a member to `RouteId` is additive and has a precedent in the same changelog** (2026-09-12, judgement and voices). One entry, one `version` move, no migration | Fowler, CLAUDE.md section 11 |
  | 2 | **The label is `Records`.** The strip is a row of subjects - Pipelines, Summaries, Hardware, Judgement, Voices - and this tab's subject is the record itself. A verb would break the family | Susan, with Reader |
  | 3 | **The tab ships behind a flag until the page exists.** A tab pointing at a route that 404s is worse than no tab | Guardrail #6 |
  | 4 | **The route id is `data-explorer` and the label is `Records`, and they differ on purpose.** `model` is labelled `Summaries` already | Fowler |
  | 5 | **This row draws no panel.** It registers three ids that row 5 implements, and the contract refuses a `judged_panel_ids` entry no route draws - which is why row 8 and not this row adds them there | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | No tab; reach the page by link only | An operator surface nobody can find is an operator surface nobody uses, and the strip is the console's only navigation | Zero; costs the page its readers | Jony |
  | 2 | Label it `Explore` | A verb among five nouns. The strip stops being a list of subjects | Zero; costs the strip its grammar | Susan |
  | 3 | Fold this into row 5 | The contract change and the page would revert together, and a payload change wants its own witness | Zero; costs the witness | Fowler |

---

### Row #3 - The door answers a written question on a sealed engine

- **Scope:** `ask()` joins `slice()` and `sliceFromDisk()` in `frontend/src/lib/data/ledger.ts`; `LedgerName` widens to every name the registry declares; `engine.ts` gains the seal in section 2.6 and the refusal list in front of it; and the door reads a date past the site's cap **from the repository instead, by fetching it in the page** (section 2.5). **No page, no chart, no publishing** - this is the reader, shipped with its own witness.

- **Files touched:**
  - `frontend/src/lib/data/ledger.ts` (`ask`, `AskOptions`, `AskResult`, `Column`, `FetchCost`; `LedgerName` widens; **the archive address is composed here too, and nowhere else**)
  - `frontend/src/lib/data/engine.ts` (`LOAD parquet`, the allowed directory and the four settings, in the order section 2.6 gives, and the connection's read-only open; still the only importer of the engine)
  - `frontend/src/lib/data/statement.ts` (new: is this one read-only statement? - pure, no engine import, so it is unit-testable on its own)
  - `frontend/src/lib/data/slice.ts` (the tier order in section 2.5 gains the writers' files and the repository copy, reading `RawDayIndex`)
  - `config/idhazh.json`, `backend/idhazh/contracts/knobs/ledger.py` (`archive_base_url`, shipping empty), `frontend/asset-base.js` (`connect-src` gains that origin, computed from the same value), `frontend/svelte.config.js` if the allow-list is assembled there
  - `frontend/src/lib/console/waiting.ts` (`refused` and `capped`, with their sentences)
  - `frontend/tests/ledger-door.spec.ts` (widened), `frontend/tests/explorer-seal.spec.ts` (new, in the `logic` group of `frontend/scripts/test-groups.ts`)
  - `tests/fixtures/ledger-door/` (the fixture ledger gains an unpacked day: a `RawDayIndex` and two writer files for it, one of which holds a row whose cells carry the hostile text in section 2.7)
  - `backend/tests/contracts/test_frontend_ledger_names.py` (new: the union in `ledger.ts` and the registry in `config/ledgers.json` are each other, in both directions)
  - `backend/tests/contracts/test_frontend_index_shapes.py` (the hand copy gains `RawDayIndex`)
  - `frontend/tests/chart-vocabulary.spec.ts` (the single-engine walk still finds one importer)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `pytest backend/tests/contracts -q`. CI runs the full suite. No browser smoke - this row draws nothing.
- **Oracle:** **the seal holds and the answer is the answer.** Over the fixture ledger, on recorded responses: each hostile statement in section 2.6 returns `refused` and no network request leaves the page; a `slice()` still answers after the page has sealed the engine; a well-formed statement over two ledgers returns exactly the rows the same query returns from the same files read in Python; a date present in both a packed day and a writer file is read once; the unpacked day returns its rows; a zero-row span returns `quiet`; a date named by no index returns `unreachable`; and an answer past `maxRows` returns `capped` with `maxRows` rows. It cannot settle whether an operator can write a useful query; row 5 and the owner do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The operator's text is a statement, and the structured predicate stays for panels.** Plan 51 row 7 refused raw SQL at the door because the caller there is a panel and fetched text could reach it. The caller here is a person typing into their own browser, and the text they type never leaves it. Both are true at once, which is why this is a second entry point and not a change to the first | Fowler and Andre, 2026-09-28; owner asked for the box |
  | 2 | **The seal is settings and registration, never a text rule over SQL.** A denylist over a language with function syntax is not a boundary. Control 3 in section 2.6 exists to give a fast, readable refusal, not to be the boundary | Carmack, with Andre |
  | 3 | **The engine takes a caret range, not a pin, and the seal test is the guard.** A pin would only delay the day a setting changed; the hostile-query set fails on the upgrade that changed it, in the pull request that raised the version. Where a release removes a setting the answer is the previous working version | Carmack, on the owner's ruling of 2026-09-28 |
  | 3a | **The seal is four lines in one file, so opening it is cheap - and it is opened by a config value, never by a control on the page.** A switch a reader can reach is a switch a shared address finds already on, in a browser holding the operator's own origin. A config value is a diff a person reads, the same reason `model_server.base_url` is committed rather than environmental (Guardrail #11) | Fowler and Carmack |
  | 3b | **What the seal costs, named rather than implied.** Multi-step work is unaffected - a `WITH` clause does everything a temporary table would. **The parquet reader is not built into the engine: it is an add-on the engine downloads** from `ledger.engine_extension_repository` (plan 51 deviation 15), so the seal loads it first, and no add-on loads after the lock. **The one real loss is joining a ledger against a file of your own**, and the seal is not what would have to move for that: the page reads the file with the browser's file API and hands the engine one more buffer. It is in hard scope - out with its price | Carmack; the add-on corrected by plan 51's owner, measured 2026-09-28 (section 2.6) |
  | 4 | **`ask` rather than `query`.** The module is the query door; a `query()` inside it puts one word in two jobs | CLAUDE.md section 0b |
  | 5 | **`LedgerName` widens to the whole registry, and a test binds it both ways.** A ledger declared and not published answers `missing` by name, which is more useful than being absent from the list | Fowler |
  | 6 | **The statement is checked by a pure module with no engine import.** It is the piece most likely to be wrong and the piece cheapest to test exhaustively | Fowler |
  | 7 | **The writers' files are read through `RawDayIndex`, which already exists.** This plan declares no persisted shape | Fowler; plan 50 row 11 |
  | 8 | **A date past the site's cap is read from the repository, and the page does the fetching.** The site carries ninety days; the repository carries what the gardener keeps. Composing one more address costs one config value and one `connect-src` origin, and it leaves the engine exactly as sealed as it was - which is why this is not the same decision as letting the engine open a URL (rejected alternative 5) | Owner, 2026-09-28; measured the same day (section 2.5) |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Build the query page's own engine module, separate from the door | Two importers of the engine, and the refusal in plan 51 section 2.5 becomes unenforceable | Zero; costs the single-engine rule | Fowler |
  | 2 | Keep the structured predicate and add operators until it can express a join | It becomes a query language of our own, badly, and an operator has to learn it | Months, and the result is worse than SQL | Owner, 2026-09-28 |
  | 3 | Parse the statement ourselves and allow only what we understand | A SQL parser is a dependency or a mistake. The engine's own settings are the boundary and they are enforced inside the engine | A parser dependency, and a false sense of a boundary | Carmack |
  | 4 | Read only packed files, as panels do | The answer stops two days short of now, which is the question an operator most often opens this page to ask | Zero; costs the page its point | Owner, 2026-09-28 |
  | 5 | **Open the engine's own URL access** - `enable_external_access` on, the remote-file extension loaded - so a statement can name `https://...` directly | It is the one thing the whole seal exists to prevent, and it buys nothing decision 8 does not already buy. Loading a remote-file extension also means fetching executable code from a third party into the engine, which is a bigger step than reading a data file. **What the reader would lose by not having it**: writing a URL inside the statement rather than picking dates and letting the door choose the address - a keystroke, not a capability | Zero to write, and it turns the hostile statements the settings refuse from refused to allowed | Carmack and Andre; ESCALATE trigger 2 |
  | 6 | Ship more than ninety days to the site so the repository is never needed | It grows the site with the archive forever, and the same bytes are already served from the repository at no cost to the 1 GB cap | Zero now; costs the cap later | Carmack |

---

### Row #4 - Every declared ledger reaches the site, and a span reaches today

- **Scope:** `LedgerConfig.published` names every ledger `config/ledgers.json` declares that plan 50 has migrated; the build copies their packed periods, their indexes, the unpacked days with their `RawDayIndex` files, and `config/ledgers.json` itself, **capped at the widest span the console can ask for** (section 2.5); the payload ceilings are set from the built files. **No frontend code, no page, no d3.**

- **Files touched:**
  - `config/idhazh.json` (`ledger.published`; `page_weight.payload_ceilings_bytes` gains one entry per published ledger's `index/daily.json` and one for `ledgers.json`)
  - `backend/idhazh/contracts/knobs/page_weight.py`, `backend/idhazh/contracts/knobs/ledger.py`
  - `frontend/scripts/copy-visuals.mjs` (the copy step gains the raw tier for unpacked days, the registry file, and the span cap read from `console.window_presets`; **a second staging script is Guardrail #4**)
  - `.gitignore` (one line beside the payload directories already there)
  - `frontend/scripts/build-canary.mjs` (the copy step fails loudly when its root is missing)
  - `frontend/scripts/bundle-gate.mjs`, `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/contracts/test_published_covers_the_registry.py` (new)
  - `frontend/tests/page-weight.spec.ts`
  - `docs/concepts/growing-reads.md` (the raw copy's cost and its bound)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. The bundle gate and the site-cap measurement both walk the built tree and are re-read after the copy step lands. CI runs the full suite.
- **Oracle:** **every published address resolves, each date is reachable through one tier, and nothing is copied that no page could ask for.** Over a built tree: every entry in every published index names a file that exists under `build/`; every date in the union of the three tiers is covered by exactly one of them; every ledger named in `ledger.published` is declared in `config/ledgers.json`; and **the oldest date reachable under `build/state/` is no older than `max(console.window_presets)` days before the build, rounded out to the whole month that holds it** - so raising a preset widens the copy and nothing else does. The built site's total is **measured and recorded beside the 1 GB cap as a reading, not as a gate** - this row publishes every migrated ledger whatever it weighs (decision 6). It cannot settle whether a browser can query the files; row 3 does.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The registry is published, and the page fetches it.** `config/ledgers.json` is copied verbatim. The page's ledger list is then a fetched fact rather than a baked one, which is what makes the refresh in row 5 mean something and what leaves the shell with nothing baked in | Fowler, on the owner's ruling of 2026-09-28 |
  | 2 | **Only unpacked days are published from the raw tier, and packing removes them.** The raw copy is bounded by how far behind packing is - at plan 50's defaults, two days - and never by how long the project has run. **The bound is stated beside the copy step and in `growing-reads.md`** | Guardrail #12; Carmack |
  | 2a | **The copy reaches back exactly as far as the widest preset, and the figure is read from config.** A file older than any span can ask for is weight nothing can fetch. **Publishing is site-wide and this cap is not a per-route setting**: one staged tree, one address, any page may read any of it - what the cap refuses is a file no page could ask for. What `state/` itself holds stays plan 50's keep-window question | Carmack, on the owner's ruling of 2026-09-28; section 2.5 |
  | 3 | **The site total is measured in this row, not estimated.** `state/` measured 66.5 MB on 2026-09-28 across seventeen directories, of which `traces` is 17.2 MB, `scores` 12.5 MB, `seen` 12.5 MB and `item-health` 11.2 MB. **That is a reading of the working tree, not of a built site**, and it is here to say the order of magnitude rather than to be the answer. The row publishes, measures the built tree, and records the margin | Guardrail #10 |
  | 4 | **A ledger plan 50 has not migrated is declared and not published.** It appears in the picker and answers `missing` by name. Listing it is how an operator learns the project has it | Fowler |
  | 5 | **Every column of every published ledger is published.** A narrowed copy stops being the ledger, which is the property that makes it unable to disagree with `state/` | Owner, 2026-09-26, inherited from plan 51 row 3 |
  | 6 | **Every migrated ledger ships, whatever it weighs, and the row never narrows the set to fit.** It publishes, measures the built tree and records the margin. Where a future measurement ever shows the 1 GB cap approaching, what moves is the gardener's keep windows - how much history is held - and never which ledgers the owner is allowed to look at | Owner, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Publish the three ledgers plan 51 publishes and no more | The page answers questions about three ledgers out of twenty-six, which is a panel with extra steps | Zero; costs the page its purpose | Owner, 2026-09-28 |
  | 2 | Publish the whole raw tier | It grows with the archive forever, which is Guardrail #12 pointed at the site cap | Zero now; costs the cap later | Carmack |
  | 3 | Generate a ledger list at build time instead of copying the registry | A generated list is a second copy of the registry that somebody has to keep in step, and the registry is already the shape a contract validates | Zero; costs a second source of truth | Fowler |
  | 4 | Have the page probe for a ledger's index and treat a 404 as "not published" | A 404 stops being a defect signal and becomes a normal answer, so a broken deploy reads as an unpublished ledger | Zero; costs telling an absence from a fault | Fowler, inherited from plan 51 row 7 |

---

### Row #5 - The page: pick the ledgers and the days, write the question, read the table

- **Scope:** `/console/data-explorer/` exists, prerenders nothing, fetches the registry and the indexes on mount, and draws three panels - the ask, the rows, the shape's placeholder. It carries the ledger list with its filter and refresh, the schema panel, the editor with its line numbers and highlighting, the example strip, the run button, the cost line before and after, and the table. **No chart, no saved list, no address handling** - rows 6 and 7 add those into the panels this row creates.

- **Files touched:**
  - `frontend/src/routes/console/data-explorer/+page.ts` (new: `prerender = false`, `ssr = false`)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (new: the route, its three `Panel` elements with the ids in section 2.1, the jump links from the group)
  - `frontend/src/lib/console/explorer/LedgerList.svelte`, `SchemaPanel.svelte`, `QueryEditor.svelte`, `ExampleStrip.svelte`, `CostLine.svelte`, `AnswerTable.svelte` (new)
  - `frontend/src/lib/console/explorer/registry.ts` (new: fetch and refresh `ledgers.json`; the hand copy of `LedgersConfig`'s two fields the page reads)
  - `frontend/src/lib/console/explorer/answer.ts` (new, pure: sort, page, format a cell as text)
  - `frontend/src/lib/console/waiting.ts` (the two new states' sentences, if row 3 did not land them)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`explorer_row_page`, `explorer_max_rows`, `explorer_examples`; the flag from row 2 is removed here, which is its declared removal condition)
  - `frontend/src/lib/server/config.ts` (the new knobs' fallbacks), `tests/fixtures/` (the every-knob fixtures)
  - `frontend/scripts/test-groups.ts` (a `data-explorer` spec joins the `console` group)
  - `frontend/tests/data-explorer.spec.ts` (new), `frontend/tests/data-explorer-cells.spec.ts` (new: section 2.7's four rules)
  - `backend/tests/contracts/test_frontend_registry_shape.py` (new: the hand copy of the registry's fields)
- **Acceptance gates:** the browser smoke on `/console/data-explorer/` at 390, 768 and 1440 in both themes (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, and **the page draws each of the six states in section 2.9**. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **a question typed into the box comes back as the right rows, and nothing on the page is a link a ledger wrote.** Against the fixture ledger served over HTTP: selecting two ledgers and 14 days, typing a join and pressing run produces exactly the rows the same statement produces in Python over the same files; the cost line's file count and byte count equal what the network actually fetched; every one of the six states renders and no two render the same; and the hostile fixture row renders as text with no `<a>`, `<script>` or `<img>` anywhere in the table's subtree. It cannot settle whether the page is good enough to ship; Susan rules that (CLAUDE.md section 14).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The page prerenders nothing, and this is not a new argument.** `adapter-static` already runs `fallback: '404.html'` and two routes already ship no document. The cost is the fallback's HTTP 404 status, which those routes already carry | Owner, 2026-09-28; the adapter setting is the fact |
  | 2 | **No other plan's rule is edited to let this page through.** Plan 51's first trigger counts prerendered routes and this route is not one; plan 26's ruling is about the six that are. Nothing needed rewording, and rewording somebody else's trigger to admit your own page is how a rule stops meaning anything | Fowler, CLAUDE.md section 1 |
  | 3 | **The ledger list is fetched, and Refresh re-fetches it.** `ledgers.json` and each selected ledger's index are re-read with `cache: 'no-store'`, and the page says what moved - a ledger's newest day and its row count. A refresh that re-reads something that cannot change is a button that teaches distrust | Owner, 2026-09-28 |
  | 4 | **The column count and the schema panel are always from the engine.** After a run they describe the answer; before one they describe the selected ledgers, and the label says which | Owner, 2026-09-28 |
  | 5 | **The editor is a `textarea` with a highlighted layer behind it.** About sixty lines, no dependency, and it keeps the keyboard and screen-reader behaviour a real text box has | Carmack, with Susan |
  | 6 | **The cost is shown before the run.** The indexes carry `rows` and `bytes` per file, so the page can say what a span will fetch before anyone presses anything | Carmack |
  | 7 | **An unpublished ledger stays in the list and says so.** The list is what the project has, not what happens to work today | Susan, with Fowler |
  | 8 | **The three panels get ids and a `panel_groups` entry in row 2, and join `judged_panel_ids` in row 8.** A section with no id is a section no picture and no gate can reach | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Prerender the shell like the other five console routes | It would make the page the tenth prerendered route for no gain: it has no loader and nothing to bake, so the document would be chrome and a spinner | Zero; costs the plan a clean answer to N4 | Owner, 2026-09-28 |
  | 2 | CodeMirror for the editor | Roughly 120 KB for line numbers and highlighting, on a route that already loads a query engine | About 120 KB, measured before taking it | Carmack |
  | 3 | A ledger tree with folders, as the reference draws | Twenty-six ledgers at one level. A chevron that opens one folder is a click that buys nothing | Zero; costs a click | Jony |
  | 4 | Let the operator pick the file tier by hand, as the reference's grain selector does | Choosing the tier by hand is how a date gets read twice and every number doubles | Zero; costs correctness | Fowler |
  | 5 | One ledger at a time | A join needs two, and a join is the question a panel cannot already answer | Zero; costs the page its point | Owner, 2026-09-28 |

---

### Row #6 - The answer gets a shape, or says why it cannot have one

- **Scope:** the third panel draws the answer as a chart, chosen from its columns by the rule in section 2.8, from plan 51 section 2.6's vocabulary and its readout strip. Where no type qualifies it draws a named refusal that stays.

- **Files touched:**
  - `frontend/src/lib/console/explorer/shape.ts` (new, pure: columns in, chart type and its geometry arguments out)
  - `frontend/src/lib/console/explorer/ShapePanel.svelte` (new: the type radio group and the chosen chart)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (the third panel's body)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`explorer_chart_min_rows`, `explorer_rank_max`), `frontend/src/lib/server/config.ts`, `tests/fixtures/`
  - `frontend/tests/data-explorer-shape.spec.ts` (new)
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (one section: how a type is chosen when nobody wrote the panel)
- **Acceptance gates:** the browser smoke on `/console/data-explorer/` at the three widths in both themes; local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **the shape follows the columns, and a shape it cannot draw says so.** For one recorded answer of each of the five cases in section 2.8, `shape.ts` returns the named type, and the panel draws it with its readout strip populated at rest; for the fifth it draws the refusal with its sentence and the panel keeps its height. It cannot settle whether the chosen type is the best one for a given answer; the operator's override and Susan do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The type is chosen from the columns, and the operator may override within what qualifies.** The reference lets you draw a line through data with no time axis, which is a chart that asserts an order the data does not have | Susan |
  | 2 | **The refusal is a state of the panel, not an alarm.** An answer with no number in it is a normal outcome, and a red dismissible banner for a normal outcome is how people learn to dismiss banners | Susan |
  | 3 | **The refusal's words are plain.** `Nothing here to draw: the answer has no number in it.` - not the reference's `unindexed binary payload blobs with 0 aggregate metrics` | Reader, CLAUDE.md section 0b |
  | 4 | **No new chart type is added here.** If an answer wants one, that is Susan's call on the vocabulary page and a separate change | Susan, plan 51 row 4 decision 4 |
  | 5 | **No point is highlighted as an anomaly and nothing animates to draw attention.** The page has no rule that makes a value anomalous, and a mark that says "look here" without one is a verdict nobody issued | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Let the operator pick any type for any answer, as the reference does | A line through unordered categories is a false statement drawn confidently | Zero; costs the page its honesty | Susan |
  | 2 | No chart at all - the table is the answer | A bare table of numbers with no shape beside it fails sufficiency gate 4 by name, and a shape is why a query page beats a terminal | Zero; costs the page a gate | Susan |
  | 3 | A chart library with automatic type inference | A second charting library, against telemetry-intent N5 | A dependency and the N5 rule | Fowler |

---

### Row #7 - A question is kept, found again and shared

- **Scope:** a question is saved in this browser under a name and drawn on the example strip; the last runs are listed with their timing and row count; and the page address carries the ledgers, the days and the question, so a link reopens it **into the editor without running it**. Copy-to-clipboard as JSON or as a Markdown table.

**What the address carries.**

```
/console/data-explorer/?ledgers=host-fingerprint,item-health&days=14&q=<the question>
```

| # | Rule |
| --- | --- |
| 1 | Real query parameters. No fragment, so the address reads as an address and can be shared, bookmarked and searched (owner, 2026-09-28) |
| 2 | Opening it **fills the editor and does not press run** |
| 3 | `q` is the statement deflated with `CompressionStream('deflate-raw')` and base64url-encoded, so the address holds a real question rather than a short one |
| 4 | **Row 7 measures the longest address GitHub Pages answers** and sets `console.explorer_query_max_chars` from that reading, so a statement that fits the box always fits a link. It does not assume a limit |
| 5 | A statement past the limit still saves and still runs. The page says the link carries the ledgers and the days only, and offers the clipboard instead |
| 6 | **What this costs, stated once**: text after `?` is sent in the request, so the statement appears in the log of whoever serves the page. It is your own query over your own published data. If that ever matters, moving `q` after a `#` removes both the limit and the log entry and costs nothing else |

- **Files touched:**
  - `frontend/src/lib/console/explorer/keep.ts` (new, pure: the saved list and the history, their bounds and their eviction)
  - `frontend/src/lib/console/explorer/address.ts` (new, pure: to and from the address, including the compression)
  - `frontend/src/lib/console/explorer/SavedStrip.svelte`, `HistoryList.svelte`, `CopyAnswer.svelte` (new)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (the first panel's strip and disclosure; reading the address on mount)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`explorer_saved_max`, `explorer_history_max`, `explorer_query_max_chars`), `frontend/src/lib/server/config.ts`, `tests/fixtures/`
  - `frontend/tests/data-explorer-keep.spec.ts` (new)
  - `docs/reference/benchmarks/address-length-on-pages.md` (new: the measured limit, its method and its date)
- **Acceptance gates:** the browser smoke on `/console/data-explorer/` including opening a shared address in a fresh context; local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **a question survives the round trip and never runs itself.** For a set of statements including one at the measured ceiling, `address.ts` returns the identical text after encode and decode; opening a built page at such an address fills the editor, leaves the run button unpressed and issues no data request until it is pressed; the saved list keeps exactly `explorer_saved_max` entries and names the one it dropped; and the history keeps `explorer_history_max`. It cannot settle what the real address limit is on a host we do not control - the benchmark record does, with its date.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The address carries the question, in query parameters, with no fragment** | Owner, 2026-09-28 |
  | 2 | **An address never runs a query.** A link that executed a stranger's statement would be the one hole the seal cannot close, because the statement would be running with the reader's consent implied rather than given | Fowler and Andre; ESCALATE trigger 6 |
  | 3 | **The statement is compressed before it is encoded.** SQL compresses several times over, so the practical ceiling stops being a design constraint | Carmack |
  | 4 | **The limit is measured before it is used.** There is no limit in the URL specification; the binding one belongs to the host, and 8 KB is a common default rather than a reading | Guardrail #10 |
  | 5 | **Saved questions live in this browser and nowhere else.** A committed, named query would be a reader of the columns it names and would go red when one is renamed; this one simply fails for the person who saved it, which is the right cost for a scratchpad | Fowler, on plan 50's own note |
  | 6 | **Copy to clipboard, never a file.** The owner refused a download; the clipboard is what it was wanted for, and no file means no spreadsheet and no formula cell | Owner, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Put the question after `#` | The owner ruled query parameters so the address reads as one. The fragment stays available as decision 4's escape hatch if a measurement ever demands it | Zero; it is held in reserve rather than refused | Owner, 2026-09-28 |
  | 2 | Run the query when a shared address opens | A link that runs a stranger's statement, on a page that holds every ledger | Zero; costs the boundary | Fowler |
  | 3 | Commit saved questions to the repository | They become readers of the columns they name, with a contract, a test and a review for each. That is a different feature and a good one | Its own row | Fowler |
  | 4 | A CSV download | Refused by the owner. It also re-opens the formula-injection case a refused file closes for free | Owner decision, plus the escaping rule | Owner, 2026-09-28 |

---

### Row #8 - The glyphs, the gates, the pictures and the page that says how to use it

- **Scope:** the marks the page draws join the icon set at one stroke width; the three panels join `console.judged_panel_ids` and pass the ten sufficiency gates or carry a `## Design rationale` line each; the panel captures run at the three widths in both themes; and the how-to page and the borrowed-from-the-reference page are written.

- **Files touched:**
  - `frontend/src/lib/icons/svg/` (the marks in section 2.12, from Lucide, unmodified source), `frontend/src/lib/icons/PROVENANCE.md`
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/appearance.py` (`icons.stroke_width`), `frontend/src/lib/icons/Icon.svelte`
  - `frontend/tests/icons.spec.ts` (the set grows; the two-way check is unchanged)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`judged_panel_ids` gains the three ids)
  - `frontend/tests/panel-sufficiency.spec.ts` (`DRIVERS` gains one entry per judged id, putting each panel into its four nothings)
  - `frontend/tests/panel-captures.spec.ts` (the route joins the capture list, which is read from `panel_groups`)
  - `docs/how-to/query-a-ledger-from-the-console.md` (new)
  - `docs/concepts/console-design/what-the-data-explorer-borrowed.md` (new: the seventy-four-feature inventory, section 2.12)
  - `docs/concepts/design-system.md` (the icon section gains the stroke-width knob and its reason)
  - `docs/reference/repository-layout.md`, `docs/architecture/publishing/console-payloads.md` (the new route and the published registry)
- **Acceptance gates:** the panel captures at 390, 768 and 1440 in both themes plus the unreachable shot; the ten sufficiency gates green on all three ids; `python backend/utilities/doc_load.py` before and after; local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **every mark the page draws is in the set and nothing in the set is undrawn, and every judged panel passes its gates or names its rationale.** `icons.spec.ts` is green in both directions after the set grows; each of the three panel ids is judged, has a driver for its four nothings, and either passes all ten gates or carries a `## Design rationale` line naming the gate and the reason; and seven pictures exist per panel. It cannot settle whether the page is good enough to ship - that is the 390 dark picture and Susan.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The marks are taken and the font is not.** The reference draws Material Symbols from a Google font; this repository already has Lucide committed as source SVG with a two-way test. Taking the font would add a third-party request on every page load and a second licence for marks we already have | Susan, with Carmack on the request |
  | 2 | **One stroke width for the whole set, from a knob, chosen from the pictures.** Lucide ships at 24 px with a 2 px stroke and the set draws at 16 px, so the shipped weight reads heavier than the type beside it. A per-icon weight would be a pile rather than a system | Susan |
  | 3 | **The stroke width changes the existing fifteen glyphs too**, and the pull request carries their pictures. A set with two weights is the thing the knob exists to prevent | Susan |
  | 4 | **The three panels are judged, not merely pictured.** A page whose whole job is reading an answer is the last place a sufficiency gate should be opted out of | Susan |
  | 5 | **The how-to page ships with the page, not after it.** The Docs button points at it, and a button pointing at nothing is worse than no button | Reader |
  | 6 | **The borrowed-from inventory is a concepts page, not a plan appendix.** A plan is distilled and archived; the reasons three classes of feature were refused outlive it and decide the next addition | Fowler, CLAUDE.md section 5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Load the Material Symbols font from Google | A third-party request for every reader, a second icon system, and roughly a font's worth of bytes for about twenty-five marks | Zero to write; costs the request and the second system | Susan and Carmack |
  | 2 | Inline the page's SVGs directly rather than joining the set | It is exactly the state the icon rule was written to prevent, and the two-way test stops seeing them | Zero; costs the system | Susan |
  | 3 | Capture the panels but do not judge them | Two gates read attributes the panels would then not need to carry, and a panel that is never judged never has to be good | Zero; costs the gates their subject | Susan |
  | 4 | Leave the icon weight as Lucide ships it | The marks read heavier than the type beside them at 16 px, which is the "pile rather than a system" failure | Zero; costs the set its coherence | Susan |

## Dependent plans

- [`20260924-51-console-fetches-and-draws-its-own-data-plan.md`](20260924-51-console-fetches-and-draws-its-own-data-plan.md). Row 3 here waits on its row titled **The query door module and its two entry points**; row 4 here waits on its row titled **The three ledgers the console reads are published**. Row 3 here also runs after its row titled **The door keeps what it fetched for the page's life, and says how far a ledger reaches**, which edits the same files and puts the door's buffers under `door/`. Row 5 here edits that plan's ESCALATE trigger 1 wording. Nothing in that plan waits on this one.
- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md). Row 4 here waits on its row titled **One compaction task a ledger, two compact periods, and the diagrams move into the page**, and reads the `RawDayIndex` its row titled **The index and watermark shapes are declared** already delivered (#1136). The more ledgers that plan migrates, the more of the picker works; **no row here blocks on all of them**. **No packed file is on main on 2026-09-28**: that plan ships every packing task report-only, and turning one on is a person's call under it, so row 4 here waits on that call as well as on a migration.
- [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md). Delivered (#613, #614, #645, #649). Its ruling keeps the six prerendered routes and its section 6 is the executable price of reversing that. **This plan neither reverses it nor depends on it**: the new route simply never prerenders, the way the two dated routes already do. **It also inherits one contradiction and does not repair it** - telemetry-intent N4 says the existing prerendered routes come off, and plan 26 ruled they stay. That disagreement is older than this plan and belongs to whichever of the two moves next.
- [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md). It moves fifty panels onto the query door, in thirteen rows. It gains `ask()` from row 3 here and loses nothing to it. **Its first row moves the console keys that rows 1 and 2 here edit** into one file a route, so those two run after it; the rest of the two plans can run beside each other.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan serves.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules the door obeys.
- [docs/concepts/design-system.md](../docs/concepts/design-system.md) - the ten sufficiency gates and the icon rule.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
