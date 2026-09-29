# Plan 55 - One page queries every ledger

**Last Updated**: 2026-09-29

**Level**: 5 (CLAUDE.md section 6). It adds a member to a persisted vocabulary (`RouteId` on the console band), it adds an entry point to the query door, it changes how the shared engine starts, and it opens a surface where an operator's own text reaches a query engine.

**Chain** (CLAUDE.md section 0d). **Intent**: the owner looks through the project's own recorded data directly - pick the ledgers, pick the days, write the question, read the answer - without waiting for somebody to build a panel for it. **Contract**: section 2 declares every address, shape, name, statement, knob and refusal these rows need, against the code as it stands on `main` today, so a worker writes each row with no further decision. **Code**: the six rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight as a running pool, refilling a slot the moment a worker returns and never waiting on a merge; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every figure on the console is a panel somebody wrote for one question. A question nobody anticipated has no surface, and answering it means a clone, a Python session and a morning. This plan gives the owner one page that reads every ledger the project declares, over any span including today, with the query written by hand and the answer drawn as a table and as a chart. |
| The page, in one sentence | **An empty shell that prerenders nothing.** It arrives with no data in it; the reader picks ledgers and days, types a query and presses run, or arrives on an address that carries a query and presses run themselves. |
| Hard scope - in | - `/console/data-explorer/` is a sixth console tab, labelled `Records`, that **prerenders nothing** - a shell answered by the existing `404.html` fallback, which fetches everything it draws.<br>- The query door gains `ask()`: one read-only statement over a chosen set of ledgers and days, on an engine sealed after its add-ons are loaded.<br>- Every ledger `config/ledgers.json` declares reaches the page's picker; every published one is queryable; an unpublished one says so by name.<br>- A span reaches **today**: packed month files, packed day files, and the writers' own files for days not packed yet, with each date read through exactly one tier.<br>- **What the build copies to the site is capped at the widest span the console can ask for**, and a date older than the cap is read from the committed repository instead.<br>- The answer is a table and, where its columns can carry one, a chart from the vocabulary the chart-vocabulary row established.<br>- A query is saved in this browser, found again, and carried in the page address.<br>- The shared span control gets smaller and the console's default span becomes 14 days. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. **The page prerenders, or a loader returns data to it.** It ships an empty shell or it is not this page.<br>2. **The sealing statements in section 2.6 are weakened, reordered so that the lock lands before the add-ons, or dropped because a query failed.** A query that fails after the seal is a missing add-on to add to the pre-load list, never a reason to leave the configuration open.<br>3. A statement that is not read-only reaches the engine, or the door builds an identifier from anything but `LEDGER_NAMES`.<br>4. An address runs a query instead of loading it into the editor.<br>5. A ledger is published that `config/ledgers.json` does not declare.<br>6. A second module imports `@duckdb/duckdb-wasm`, or a module other than `ledger.ts` builds a published address.<br>7. `ConsoleBand` changes beyond gaining one route id.<br><br>**A new chart type is not an escalation** - it is Susan's call on the vocabulary page. |
| Chosen strategy | Three independent rows first - the chrome, the reader, the data - then the page that needs all three, then what the page does with an answer, then the reach past the cap and the polish. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3, because wave 1 holds exactly three file-disjoint rows and every later wave holds one. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Taking the six existing prerendered routes off prerender | `/`, `/archive/`, `/evals/` and the three console pages keep their documents. Telemetry-intent N4 stays in tension with plan 26's ruling, and this plan does not resolve it - it only stops N4 being read as a bar on a page that bakes nothing | [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) section 6, which is already written as executable rows and needs only the owner's word |
| A switch on the page that opens the engine seal | Nothing an operator can reach another way. The one capability the seal genuinely removes is joining a ledger against a file of your own, and a file the **page** reads and hands the engine as a buffer restores it without opening anything. Reading past the site's cap needs no switch either - row 6 does it with the page's own fetch | A config value in `config/appearance.json`, default off, with its removal condition on its declaring line - never a control in the page, because a switch reached by a shared address is a switch a stranger's query can find already on |
| Dropping a local file onto the page and joining a ledger against it | You cannot compare a ledger against a spreadsheet you hold. It is the only real loss the seal causes, and the seal is not what would need to move: the page reads the file with the browser's own file API and registers it as one more buffer | Its own row. About one component, one buffer registration and a column-type check, and it opens no network path |
| A download of any kind - CSV, Parquet, Arrow | You cannot open an answer in a spreadsheet. Row 5's copy-to-clipboard covers the case it was wanted for, and refusing a file also refuses the formula-injection surface a cell beginning `=` opens | Owner decision. It is one function and one button, and the cell-escaping rule comes with it |
| Writing anything back - a saved query committed to the repository, a query the pipeline runs | A saved query notices nothing when a column is renamed; it simply fails the next time you run it | A row that gives a saved query a file under `config/`, its own contract and a test that runs it |
| A second engine, a second dialect, or a query language of our own | One dialect. An operator learns DuckDB SQL, which they can use anywhere else | Nothing. This is a refusal, not a deferral |
| Charts outside the vocabulary page's list | The page draws what the console draws. An answer whose shape no type fits gets a table and a sentence saying why | Susan adds a type to the vocabulary page, which is a design call and not an escalation |
| Byte-range requests for any file | A wide span fetches whole files. Every file the door reads is already bounded by the span control and refused past `console.explorer_max_fetch_bytes` | A measurement showing a real span the ceiling refuses that ranges would have answered |
| The two-second lag between a run finishing and its rows being packed | Nothing. Row 2 reads the writers' own files for days not packed yet, so a span reaches the current hour | - |

### The intent this plan serves

[docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) is the north star and sits above this plan (CLAUDE.md section 0d).

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N2 | The browser queries the parquet itself | **Delivered for arbitrary questions.** The door was built for panels; row 2 here opens it to a question nobody wrote a panel for |
| N3 | The browser fetches its own data at view time | **Delivered whole on one route.** This page fetches the ledger registry, the indexes and the data after mount, and bakes none of it |
| N4 | Prerendering is an anti-pattern | **This route never prerenders.** It is the first console route with no document. It does not remove the existing six; plan 26 section 6 owns that |
| N5 | d3 is the only charting library | **Inherited.** Row 5 draws only from the vocabulary page's list |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Advanced.** Row 3 publishes the ledgers themselves and the registry that names them; nothing new enters git |
| N9, N10, N11 | The name, the two tiers, the one shard pattern | **Inherited** from plan 50. This plan declares no persisted shape of its own except one member on an existing vocabulary |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The span control shrinks and the strip gains a sixth tab | - | A | PENDING | - | - | - |
| 2 | The door answers a written question on a sealed engine | - | A | PENDING | - | - | - |
| 3 | Every declared ledger reaches the site, capped at the widest span | - | A | PENDING | - | - | - |
| 4 | The page: pick the ledgers and the days, write the question, read the table | 1, 2, 3 | B | PENDING | - | - | - |
| 5 | The answer gets a shape, and a question is kept, found again and shared | 4 | C | PENDING | - | - | - |
| 6 | Reach past the cap, the glyphs, the gates, the pictures and the how-to | 4, 5 | D | PENDING | - | - | - |

**Six rows, six pull requests, four waves.** Wave 1 is rows 1, 2 and 3 together; wave 2 is row 4; wave 3 is row 5; wave 4 is row 6.

**Readiness is the file-disjointness test, not the group letter** (execute-a-plan.md). The three rows of wave 1 were sized to pass it, and the table below is the proof - each row owns a whole surface and no path appears twice.

| Surface | Row 1 | Row 2 | Row 3 |
| --- | --- | --- | --- |
| `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` | **owns** | - | - |
| `config/idhazh.json`, `backend/idhazh/contracts/knobs/ledger.py`, `knobs/page_weight.py` | - | - | **owns** |
| `frontend/src/lib/components/Window*.svelte`, `frontend/src/lib/console/band.ts` | **owns** | - | - |
| `frontend/src/lib/data/**`, `frontend/src/lib/console/waiting.ts` | - | **owns** | - |
| `frontend/scripts/*.mjs`, `frontend/asset-base.js` | - | - | **owns** |
| `backend/idhazh/contracts/console_band.py`, `telemetry/publish/console_band.py` | **owns** | - | - |
| `frontend/src/lib/server/config.ts` | **owns** | - | - |

**Row 2 touches no config file at all, which is what makes wave 1 three-wide.** Its row ceiling arrives as an argument (`AskOptions.maxRows`, section 2.4) rather than as a knob it reads, so the knobs that bound the page are minted by the row that reads them - row 4 - and row 2's tests pass a literal. This is the single change that turned a two-wide wave into a three-wide one.

**The tab ships in row 1 behind a flag in `config/appearance.json`, and row 4 removes the flag.** The flag lives with the other console appearance knobs rather than in `config/idhazh.json`, so row 1 and row 3 never touch the same file. Its removal condition is on its declaring line: row 4's merge.

**Rows 5 and 6 are single-slot waves on purpose.** Everything left after row 4 edits `frontend/src/routes/console/data-explorer/+page.svelte`, so a second worker there would be two workers on one file. The pool is three; the work at that depth is one.

**Row 4 is the keystone and cannot be split.** It creates the route, the panel shells, the ledger picker, the editor and the table in one commit, because there is no intermediate state where the route exists and draws nothing - a console route that renders an empty page is a tab that lies.

**What each wave costs while it runs.** Wave 1 is three workers writing in three worktrees; the expensive gates - the build, the browser run - serialise behind the shared gate lock whatever the pool size says, so three slots buy three writers and not three builds.

## 2. The contracts

### 2.1 The door as it stands on `main`, which is what these rows extend

The query door shipped. **It is ten modules, not the three an earlier draft of this plan named**, and a row that edits the wrong one is a row that fails at its first import. This table is the map every frontend row reads first.

| # | Module | What it owns | What this plan does to it |
| --- | --- | --- | --- |
| 1 | `frontend/src/lib/data/ledger.ts` | The public face: `slice()`, `ledgerReach()`, the one page keeper, the site address prefix | **Row 2 adds `ask()` here.** Still the only module that composes a published address |
| 2 | `frontend/src/lib/data/slice-shapes.ts` | `LedgerName`, `LEDGER_NAMES`, `DateStamp`, `Row`, `Predicate`, `SliceOptions`, `SliceResult`, `SliceRequestError`, `COLUMN_NAME`, `isDay()` | **Row 2 widens `LEDGER_NAMES` from three names to all twenty-six** and adds the `ask()` shapes |
| 3 | `frontend/src/lib/data/slice.ts` | Pure: `daysBetween()`, `filesFor()` - the coarsest file that holds each day, or the first hole | **Row 2 adds the third tier** (the writers' own files); **row 6 adds the fourth** (the repository) |
| 4 | `frontend/src/lib/data/slice-query.ts` | `QueryEngine`, `statementFor()`, `rowsFor()`, `cellOf()`, `SliceValueError`, `DATE_COLUMN` | Row 2 reuses `cellOf()` unchanged and adds nothing to `statementFor()` |
| 5 | `frontend/src/lib/data/page-keeper.ts` | `pageKeeper()`, `ByteSource`, `WantedFile`, `Holding`, `FileShortfall` - one fetch and one registration per file, for the page's life | **Row 2 calls `hold()` and never registers a file itself** |
| 6 | `frontend/src/lib/data/engine.ts` | The only importer of `@duckdb/duckdb-wasm`. `browserEngine()`, `nodeEngine()`, minted names `door/<n>.parquet` | **Row 2 adds the pre-load and the seal at start** (section 2.6) |
| 7 | `frontend/src/lib/data/compact-index.ts` | The hand copy of `CompactIndex` / `CompactEntry` | Row 2 adds the hand copy of `RawDayIndex` |
| 8 | `frontend/src/lib/data/fetched-bytes.ts` | The `ByteSource` that fetches from this site | **Row 6 gives it the archive prefix** |
| 9 | `frontend/src/lib/data/ledger-reach.ts`, `slice-reader.ts` | How far a ledger reaches; the slice read itself | Untouched |
| 10 | `frontend/src/lib/server/ledger-disk.ts` | `sliceFromDisk()`, the build-time reader | Untouched |

**Three facts about the shipped engine decide most of section 2.6, and none of them was in the earlier draft.**

| # | Fact, read from `engine.ts` on `main` | What follows |
| --- | --- | --- |
| 1 | **The parquet reader is an add-on the engine downloads at first use**, from `ledger.engine_extension_repository`, which is `https://extensions.duckdb.org` in `config/idhazh.json` | Turning auto-install and auto-load off before that add-on is loaded stops every query over every ledger. The pre-load in section 2.6 exists for exactly this |
| 2 | **The browser worker starts from a `blob:` bootstrap, so it inherits the page's `connect-src`** | The browser's own policy is a real boundary on the engine, not only on the page. `connect-src` already names three origins: this site, the asset base and the extension repository |
| 3 | **`register()` mints the name** `door/<n>.parquet` from a counter, and a registered buffer is a **file**, not a table | A statement cannot say `FROM "item-health"` until something creates that name. Section 2.4 is where it is created |

### 2.2 The address, the tab, and the route id

| # | What | Value |
| --- | --- | --- |
| 1 | Address | `/console/data-explorer/` |
| 2 | Route id | `data-explorer`, a new member of `RouteId` in `backend/idhazh/contracts/console_band.py` and of the `RouteId` union in `frontend/src/lib/console/band.ts` |
| 3 | Tab label | `Records` |
| 4 | Tab description | `Ask the project's own record a question, and read the answer.` |
| 5 | Panel group | one group, id `data-explorer`, title `""` - the Pipelines shape, because what the three panels need is an order rather than a grouping |
| 6 | Panel ids, in order | `data-explorer-ask`, `data-explorer-rows`, `data-explorer-shape` |

`RouteId` holds five members today - `pipelines`, `model`, `machine`, `judgement`, `voices`. **The id and the label differ on purpose, and that is the established pattern**: `model` is labelled `Summaries` and `machine` is labelled `Hardware`.

**Adding a route id is additive and has a precedent in the same file.** `ConsoleBand.__changelog__` already carries `2026-09-12 - RouteId gains the route ids judgement and voices. Additive: an older payload names three of the five and validates unchanged.` Row 1 appends one entry of the same shape and moves `version`. A band payload written before this row names five routes and still validates; the frontend draws a tab for every route the payload carries and nothing for one it does not, so an old payload costs the tab and never the page.

### 2.3 This route prerenders nothing, and that is a shipped pattern rather than a new argument

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
| 4 | What this route does **not** cost | Every item in plan 26 section 6 is about converting one of the six existing routes: re-homing a server load, re-pricing a ceiling that measures prerendered HTML, rewriting a spec that reads the prerendered document. A route that never prerendered has none of those, and this route has no `+page.server.ts` at all |

**The page's only input is what it fetches.** No loader returns data, so there is nothing a build could bake in, which is the property telemetry-intent N4 is actually about. No other plan's trigger fires and this plan edits none of them: the count of prerendered routes does not move.

### 2.4 `ask()`: the signature, and how a buffer becomes a table

Row 2 adds one export to `frontend/src/lib/data/ledger.ts` and its shapes to `slice-shapes.ts`. Everything already there is unchanged.

```ts
/** Run one read-only statement over a chosen set of ledgers and days.
 *  The caller chooses the ledgers and the span; the statement shapes the answer
 *  and never chooses a file. */
export function ask(opts: AskOptions): Promise<AskResult>;

export type AskOptions = {
	/** Non-empty. Each becomes one view of the same name, hyphens and all -
	 *  a statement quotes it as "item-health". */
	ledgers: readonly LedgerName[];
	from: DateStamp;
	to: DateStamp;
	/** One read-only statement. Refused before the engine sees it if it is not. */
	sql: string;
	/** The most rows the answer holds. Past it `capped` is true and the rows are real. */
	maxRows: number;
	/** The most bytes this call may fetch. Refused before any fetch when the
	 *  indexes say the span costs more. */
	maxFetchBytes: number;
};

/** One column of the answer, as the engine describes it. */
export type Column = { name: string; type: string };

/** What the fetch actually cost, so the page prints a reading and never a guess. */
export type FetchCost = { files: number; bytes: number; alreadyHeld: number; ms: number };

/** What a span will cost before it is paid, from the indexes alone. */
export type SpanCost = { files: number; bytes: number; unpackedDays: readonly DateStamp[] };

export type AskResult =
	| { state: 'ok'; columns: readonly Column[]; rows: Row[]; capped: boolean; read: FetchCost; unpackedDays: readonly DateStamp[] }
	| { state: 'quiet'; columns: readonly Column[]; read: FetchCost }
	| { state: 'missing'; ledger: LedgerName }
	| { state: 'unreachable'; at: DateStamp }
	| { state: 'refused'; because: string };

/** What the span would cost, from the indexes, fetching no data file. */
export function askCost(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost>;
```

**`ask` rather than `query`.** The module is already the query door, so `query()` beside `slice()` would put the same word in two jobs one sentence apart (CLAUDE.md section 0b).

**A registered buffer is a file, so `ask()` creates one view per ledger.** This is the step with no other home: the engine mints `door/<n>.parquet` and a statement cannot name a ledger until something binds the name.

```ts
// For each selected ledger, in order, after `hold()` has returned its names:
//   CREATE OR REPLACE VIEW "item-health" AS
//     SELECT * FROM read_parquet(['door/1.parquet', 'door/2.parquet'], union_by_name = true)
// For every name in LEDGER_NAMES that this call did NOT select:
//   DROP VIEW IF EXISTS "item-health"
```

| # | Rule about the views | Why |
| --- | --- | --- |
| 1 | The view name is a member of `LEDGER_NAMES` and nothing else, double-quoted | A closed union is the only identifier source. No typed text and no fetched text becomes an identifier (Guardrail #11) |
| 2 | The file list is the minted names `hold()` returned, each quoted as a string literal, exactly as `slice-query.ts` already does in `listOf()` | The engine minted every one of them |
| 3 | **Every unselected ledger's view is dropped on every call** | A view left behind from an earlier run points at files the keeper still holds, so a statement could read a ledger the operator did not select and did not see the cost of. Dropping is one statement per unselected name and it runs before the operator's statement |
| 4 | `union_by_name = true`, matching the panel path | A day written before a column existed reads that column as null rather than failing the read |
| 5 | The door's own view statements are not subject to section 2.6 control 3 | That control reads the operator's text. The door's statements are built from a closed union and minted names |

**`LEDGER_NAMES` widens from three to twenty-six.** It stays a hand-written closed union in `slice-shapes.ts` and a backend test binds it to the registry in both directions, the binding `test_frontend_vocabularies.py` already uses. A panel still names a ledger and never a path.

**The columns come from the engine and from nowhere else.** The page runs `DESCRIBE` against the views to fill the schema panel, and reads the answer's own columns off the result. There is no second copy of a ledger's column list to keep in step.

### 2.5 What bounds the bytes

| # | Rule |
| --- | --- |
| 1 | The caller names the ledgers and the days. `slice.ts` turns that into a file set exactly as it does for a panel |
| 2 | Each file is fetched whole through `pageKeeper.hold()` and handed to the engine once. **`ask()` never calls `engine.register()` itself** - the keeper is what stops a file crossing the network or entering the engine twice |
| 3 | **The statement never names a file, a path or a URL.** It sees view names and nothing else |
| 4 | `askCost()` reads the indexes alone and answers what the span will fetch. The page prints it **before** the run. `ask()` refuses past `maxFetchBytes` with `refused` and a sentence naming the figure and the span, **before any data file is fetched** |
| 5 | Guardrail #12 is satisfied by the span, not by the archive: the first view fetches `console.default_window_days` of the selected ledgers and no more, however long the project has been running |
| 6 | **A browser page keeps every file it has fetched for the page's life** (`page-keeper.ts`), so bytes accumulate across runs on one page. `maxFetchBytes` bounds one call; the reload bounds the page. Row 4 prints the running total beside the cost line so the ceiling is never the first news of it |

### 2.6 The seal, which is applied after the add-ons load and not before

**The earlier draft of this section would have stopped every query on the site.** The engine links only DuckDB's core functions and downloads the parquet reader at first use (section 2.1 fact 1), so turning auto-install and auto-load off at start removes the ability to read a parquet file at all. The order below is the whole of the fix, and ESCALATE trigger 2 exists to stop it being quietly reordered by somebody debugging a failed query.

**In `engine.ts`, in `startInBrowser` and `startInNode`, immediately after the `custom_extension_repository` statement and before the connection is handed back:**

```
INSTALL parquet;
LOAD parquet;
SET enable_external_access = false;
SET autoinstall_known_extensions = false;
SET autoload_known_extensions = false;
SET lock_configuration = true;
```

| # | Rule about that block | Why |
| --- | --- | --- |
| 1 | The pre-load list is **derived by row 2, not guessed by this document.** The row runs one parquet read on an unsealed engine, then `SELECT extension_name FROM duckdb_extensions() WHERE loaded`, and the list it prints is the list that goes above `SET enable_external_access = false`. `parquet` is where it starts | Guardrail #10. A guessed list is a query that fails on a site nobody is watching |
| 2 | The lock is last | `lock_configuration = true` refuses every later `SET`, including the three above it |
| 3 | The block runs in both halves, browser and Node | A seal only the browser has is a seal a build-time reader can be used to get around, and the Node half is what the oracle can drive without a browser |
| 4 | A query that fails after the seal is a **missing add-on**, added to the pre-load list in the same commit | ESCALATE trigger 2. Reaching for the setting instead is how a seal becomes a comment |

**Four controls, strongest first.** Row 2 proves each one rather than assuming it.

| # | Control | What it stops | Where it lives |
| --- | --- | --- | --- |
| 1 | Only buffers the keeper registered are visible, under names the engine minted. **`registerFileURL` is never called** | The statement cannot reach a file the door did not fetch | `engine.ts`, already true on `main` |
| 2 | The block above, in that order | `read_csv('https://...')`, `COPY ... TO`, `ATTACH`, `INSTALL`, `LOAD`, and the statement turning any of them back on | `engine.ts`, row 2 |
| 3 | The page refuses, before the engine sees it: more than one statement; anything that is not `SELECT`, `WITH ... SELECT`, `DESCRIBE`, `SUMMARIZE` or `EXPLAIN`; and a statement longer than `console.explorer_query_max_chars` | A write, a schema change, and a paste large enough to stop the tab responding | `frontend/src/lib/data/statement.ts`, row 2 |
| 4 | `connect-src`, which the browser enforces on the engine's worker as well as on the page, because the worker starts from a `blob:` bootstrap | Anything that got past 1 to 3 reaching a fourth origin | `frontend/asset-base.js`, already true on `main` |

**What control 4 admits today, stated rather than implied.** `connect-src` names three origins: this site, `visuals.asset_base_url`, and `ledger.engine_extension_repository`. Row 3 adds a fourth, `ledger.archive_base_url`, computed from the same config file. **That is the residual, and it is named rather than denied**: with controls 1 to 3 in place a statement cannot reach any of them, and if control 2 were ever removed a statement could read a public file on one of four hosts and nowhere else. It is what the browser can enforce, it is smaller than the open web by every host that is not on that list, and no row here widens it beyond the one address the owner asked for.

**The engine is not pinned to an exact version, and the seal is held by a test rather than by a pin.** `frontend/package.json` takes `@duckdb/duckdb-wasm` at a caret range, the way every other dependency here is taken. The hostile set below runs against whatever version is installed, so a release that changed one of these settings turns that test red on the pull request that raised the version - which is where somebody wants to find out, and which a pin would only have delayed. **If a release ever removes one of them, the answer is the previous working version, not a text rule over the statement**: a text rule is a denylist, and a denylist over a language with function syntax is not a boundary.

**The hostile set the oracle runs**, each asserted refused, and **each asserted refused after a well-formed query over the same engine has succeeded** - so the test cannot pass by having sealed the engine into uselessness:

```
SELECT * FROM read_csv('https://example.invalid/x.csv')
SELECT * FROM read_parquet('https://example.invalid/x.parquet')
COPY (SELECT 1) TO 'x.csv'
ATTACH 'x.db' AS other
INSTALL httpfs
LOAD httpfs
SET enable_external_access = true
SET lock_configuration = false
SELECT 1; DROP VIEW "item-health"
CREATE TABLE t AS SELECT 1
SELECT * FROM "scores"          -- refused: the call did not select that ledger
```

### 2.7 A span reaches today, through four kinds of file

**Each date is read through exactly one tier.** The door takes, per date, the first of these that covers it. Tiers 1 and 2 are `filesFor()` as it stands; row 2 adds tier 3 and row 6 adds tier 4.

| # | Tier | Address | When it covers a date | Row |
| --- | --- | --- | --- | --- |
| 1 | Packed month | `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet` | The whole month is packed | shipped |
| 2 | Packed day | `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet` | That day is packed | shipped |
| 3 | The writers' own files | `state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet`, every name in that day's `RawDayIndex` | The day is not packed yet | 2 |
| 4 | The same file in the repository | `<ledger.archive_base_url>/state/compact/<ledger>/...` | The date is older than the site's cap (section 2.8) and the repository still holds it | 6 |

**Nothing is missing to build tier 3.** `RawDayIndex` is already declared in `backend/idhazh/contracts/ledger_index.py` - the ledger, the date, the file names for that day, and when they were listed. The browser cannot list a directory, and this is the file that means it does not have to.

**A date in two tiers is a defect, not a merge.** Reading one date twice doubles every number on the answer. `filesFor()` already holds this property for tiers 1 and 2 and its docstring says so; the oracle in row 2 extends the assertion over a fixture ledger carrying all three kinds.

**The writers' own files are not packed, so they cost more per day.** One request per writer file instead of one for the day. This is why panels stay on packed files: a panel draws on arrival for every reader, and this page fetches when an operator presses a button. `askCost()` reports the file count before the run, so the cost is visible at the moment it is chosen.

**Where the three kinds disagree, the packed file wins by being the only one read.** Packing applies each ledger's own merge rule while it builds the file, so a packed day holds one row per record; the writers' files for an unpacked day hold what the writers wrote, which can be two rows of one record for a ledger whose merge rule is a cell union. **A difference that cannot be removed is printed on the page** rather than hidden: `AskResult.unpackedDays` carries the dates that came from tier 3 and the status sentence names them.

### 2.8 What reaches the site is capped at the widest span, not at what `state/` holds

**The publishing decision is site-wide; the cap on it is derived from config.** There is one staged tree, served at one address, and any page may fetch any of it - so this is not a per-route setting and no row here invents one. What the cap does is refuse to copy a file no page could ask for.

| # | Rule |
| --- | --- |
| 1 | The build copies the periods covering the last `max(console.window_presets)` days, rounded out to whole monthly files, because a month is the unit a monthly file comes in |
| 2 | The raw tier is copied only for dates no packed file covers, which the packing rule already bounds to a day or two |
| 3 | **The number is read from config, never written down.** Adding a wider preset widens the copy with no source edit, which is the substitution test (Guardrail #6) |
| 4 | **What `state/` holds is a different question and belongs to the gardener's keep windows.** Git keeps the history; the site carries the part a reader can reach |

**Past the cap, the page reads the repository, and the seal stays shut.** `state/` is committed, the repository is public, and a browser can read a committed file directly. So a date older than the site carries is fetched from the repository instead, and only the address changes.

**Measured 2026-09-28**, against a committed file on `main`:

| # | What was read | Value |
| --- | --- | --- |
| 1 | Repository visibility | public |
| 2 | Status for `<archive base>/state/host-fingerprint/2026/09/16/settled.csv` | 200, 350 bytes |
| 3 | `access-control-allow-origin` | `*` - so a browser may read it from our own page |
| 4 | `cache-control` | `max-age=300`. A packed file never changes, but this host re-validates after five minutes, so a repeated query over old dates pays the fetch again |
| 5 | `accept-ranges` | `bytes`. Noted and unused - this plan makes no range requests |

**The page fetches it; the engine never does.** `ledger.ts` composes the archive address exactly as it composes the site address, `fetched-bytes.ts` fetches it, and the keeper hands the engine one more buffer. No engine setting changes and no trigger fires.

| # | Rule |
| --- | --- |
| 1 | The address is `ledger.archive_base_url`, **a committed value in `config/idhazh.json`**, joined onto the same committed path. An environment value is not an acceptable control for a destination (Guardrail #11) |
| 2 | `connect-src` gains that one origin, computed from the same config value in `frontend/asset-base.js`, the pattern `visuals.asset_base_url` and `ledger.engine_extension_repository` already use |
| 3 | The origin serves files and accepts none, so nothing can be sent to it; what it adds is that a query can read any public file on that host, which is already public |
| 4 | Where the value is empty the page reads the site only, and a date past the cap answers `unreachable` with its date. **The empty default is what a fresh clone runs on** |
| 5 | The repository's own keep windows decide how far back this reaches. Where the repository no longer holds a date either, the answer is `unreachable` and names the date |

**What this buys, plainly: the site carries ninety days and the page can still answer a question about last spring.**

### 2.9 The ledger registry, as the page reads it

Row 3 copies `config/ledgers.json` to the site verbatim; row 4 fetches it. **It is an array of families, each holding an array of ledgers** - not a flat map, which is what a hand copy written from the name alone would assume.

```ts
/** The hand copy of the two levels the page reads. `LedgersConfig` in
 *  `backend/idhazh/contracts/` is the source of truth; a backend test binds this. */
export type LedgerFamily = {
	name: string;
	lifecycle_status: string;
	description: string;
	onboarded: string;
	ledgers: readonly { name: string; grain: string }[];
};
export type LedgerRegistry = { families: readonly LedgerFamily[] };
```

| # | Fact, read on 2026-09-29 | Value |
| --- | --- | --- |
| 1 | Families | 20 |
| 2 | Ledgers, over all families | 26 |
| 3 | Fields on a ledger | `name`, `grain`, `prefix`, `stem`, `suffix` - the page reads `name` and `grain` and ignores the rest |
| 4 | `ledger.published` in `config/idhazh.json` today | empty. Row 3 is what fills it |
| 5 | How the page knows a ledger is not queryable | It is in the registry and not in the published list. **Never by probing for a 404** |

**`grain` is the word the registry uses for how a ledger files** - `day`, `tree`, `month`, `flat`, `stamp`, `raw-and-compact`. **The page never reuses that word for a time bucket**; a time bucket is a `bin`. One word, one job (CLAUDE.md section 0b).

### 2.10 Every cell is text, and nothing on this page can change that

Guardrail #11. A ledger carries text that came off the open web - an article title, a source address, a server's error string.

| # | Rule | How it is held |
| --- | --- | --- |
| 1 | No `{@html}` anywhere under `frontend/src/routes/console/data-explorer/` or `frontend/src/lib/console/explorer/` | An import and source walk in the route's own spec |
| 2 | A cell is never a link, an image source, a fetch address or a style value, whatever it looks like | The spec renders a fixture row whose cells hold `<script>alert(1)</script>`, `javascript:alert(1)`, `=cmd\|' /c calc'!A1` and `https://example.invalid/x`, and asserts the rendered subtree has no `<a>`, no `<script>`, no `<img>`, and visible text equal to the cell |
| 3 | A column name comes from the engine's schema, never from a cell | `Column.name` is the only source the header reads |
| 4 | A ledger name in a fetch address or a view name comes from `LEDGER_NAMES`, never from typed text | The union is closed and `ledger.ts` composes both |

**The spreadsheet-formula case is closed by refusing the download**, not by escaping: there is no file for a spreadsheet to open.

### 2.11 The answer: the table, then the shape

**The table.**

| # | Behaviour | Knob |
| --- | --- | --- |
| 1 | Sticky header; a row-number column; each header carries the column's type from `DESCRIBE`; numbers right-aligned in tabular figures | - |
| 2 | Headers sort. The sort runs over rows already in memory - no second fetch and no second statement | - |
| 3 | One page of rows at a time, with `show more` | `console.explorer_row_page`, default 50 |
| 4 | The answer stops at a ceiling and says so, naming the ceiling and suggesting a narrower span | `console.explorer_max_rows`, default 1000 |
| 5 | A numeric cell carries an in-cell bar proportional to its value within its own column | - |
| 6 | The panel may be widened to the route's full width | - |

**No cell is tinted by value.** A colour that means "bad" needs a rule, and this page cannot have one: it does not know which of twenty-six ledgers' values are bad. The bar in rule 5 is a comparison a reader makes; a red cell is a verdict nobody issued.

**The shape.** The chart type is chosen from the answer's own columns, first match wins:

| # | The answer holds | The type | Knob that floors it |
| --- | --- | --- | --- |
| 1 | one date or timestamp column and at least one numeric | `dateSeries` | `console.explorer_chart_min_rows` |
| 2 | one text column and exactly one numeric | `rankedList` | `console.explorer_rank_max` |
| 3 | exactly two numeric columns | `pairedScatter` | `console.explorer_chart_min_rows` |
| 4 | exactly one numeric column | `distribution` | `console.explorer_chart_min_rows` |
| 5 | none of the above, or below the floor | no chart | - |

The operator may choose any type that qualifies, as a radio group. **Where no type qualifies the shape panel draws `refused` with the reason in plain words** - `Nothing here to draw: the answer has no number in it.` - and it stays; it is not a dismissible alarm, because it is a normal outcome.

### 2.12 The states, and which vocabulary owns each

`frontend/src/lib/console/waiting.ts` owns `PanelState = 'ready' | 'loading' | 'quiet' | 'missing' | 'unreachable'` and `ChartState = PanelState | 'too-few'`. **Row 2 adds one member and nothing else** (Guardrail #4).

| # | State | Where it lives | What it means here |
| --- | --- | --- | --- |
| 1 | `loading` | `PanelState`, exists | The engine, the indexes or the files are on their way |
| 2 | `quiet` | `PanelState`, exists | The statement ran and matched no rows |
| 3 | `missing` | `PanelState`, exists | A chosen ledger is declared but not published |
| 4 | `unreachable` | `PanelState`, exists | A date in the span is named by no index of any tier |
| 5 | `refused` | **`PanelState` gains it, row 2** | The statement did not run. The page refused it, the ceiling refused it, or the engine did, and the reason is shown as text. It is not a fetch that failed, which is what `unreachable` already means |
| 6 | `capped` | **not a state.** A boolean on `AskResult.state === 'ok'` | The answer reached `maxRows` and stopped. The rows shown are real; the answer is not the whole one. The panel is `ready` and draws a line above the table |

**`capped` is a flag and not a sixth state on purpose.** A capped answer has rows to draw and a state is what a panel draws *instead of* rows. Spelling it as a state would have put one condition in two vocabularies.

### 2.13 The knobs this plan mints or moves

Every value below is a knob (Guardrail #6), in `config/appearance.json` with its model in `backend/idhazh/contracts/knobs/console.py` unless stated. **The `Row` column is the one that mints it, and it is what keeps wave 1 disjoint.**

| Key | Row | Status | Value | Read by |
| --- | --- | --- | --- | --- |
| `console.default_window_days` | 1 | **Exists at 30, becomes 14** | `14` | Every console route opens on it. It is already in `window_presets`, so the model's own validator passes unchanged |
| `console.window_presets` | 1 | Exists as `[1, 7, 14, 30, 90]` | unchanged | Row 1 draws one tile per value. **No second key naming the same values** |
| `console.panel_groups["data-explorer"]` | 1 | **New** | section 2.2 row 5 | Rows 1 and 6 |
| `console.data_explorer_tab` | 1 | **New**, a flag | `false` | The sixth tab draws only when it is on. **Removal condition, on its declaring line: row 4's merge, which sets it true and deletes the field.** In `appearance.json` rather than `idhazh.json` so rows 1 and 3 never share a file |
| `console.explorer_row_page` | 4 | **New** | `50` | Row 4's table. How many rows one press of `show more` adds |
| `console.explorer_max_rows` | 4 | **New** | `1000` | Row 4 passes it as `AskOptions.maxRows`. The most rows one answer holds, because a browser that renders an unbounded answer stops responding and the message arrives after the freeze |
| `console.explorer_max_fetch_bytes` | 4 | **New** | set by row 4 from a reading | Row 4 passes it as `AskOptions.maxFetchBytes`. **Row 4 sets it from the largest span it can actually complete in a browser, not from this document** - it widens the span until the tab is unusable and takes the step below that |
| `console.explorer_query_max_chars` | 5 | **New** | set by row 5 from the measured address limit | Rows 4 and 5. **Row 5 sets it from a reading** - it measures the longest address GitHub Pages answers, and sizes it so any statement that fits the box also fits a link |
| `console.explorer_chart_min_rows` | 5 | **New** | `3` | Below it no chart is drawn: two points define a line, so a chart of two is a claim |
| `console.explorer_rank_max` | 5 | **New** | `30` | The most rows a `rankedList` draws |
| `console.explorer_saved_max` | 5 | **New** | `20` | How many saved questions this browser keeps. The oldest goes when it is full and the page says which |
| `console.explorer_history_max` | 5 | **New** | `10` | How many recent runs the list holds |
| `console.explorer_examples` | 4 | **New** | the five in section 2.14 | Row 4's example strip. A list of `{id, title, note, ledgers, days, sql}` |
| `console.judged_panel_ids` | 6 | Exists as `[]` | gains the three panel ids | Row 6 |
| `icons.stroke_width` | 6 | **New**, in the `icons` block | set by row 6 from the pictures | One stroke width for the whole glyph set. Lucide ships at 24 px with a 2 px stroke and the set is drawn at `icons.size_px` 16, so the shipped weight reads heavier than the type beside it. **The value is chosen from the pictures at 390 in both themes**; 1.5 is where the row starts |
| `ledger.published` | 3 | Exists, **empty today** | every migrated ledger | `copy-visuals.mjs`. Row 3 is what fills it |
| `ledger.archive_base_url` | 3 | **New**, in `config/idhazh.json` beside `ledger.published` | ships **empty**, which means the site only | Row 6's address composer and `asset-base.js`'s `connect-src`. **Declared by row 3 and first read by row 6**, so no two rows of one wave touch `knobs/ledger.py` |
| `page_weight.payload_ceilings_bytes` | 3 | Gains entries | set by row 3 from the built files | In `config/idhazh.json`. One per published ledger's `index/daily.json`, plus one for `ledgers.json` |

### 2.14 The example questions

Five, in `console.explorer_examples`. Each names the ledgers it needs, so a chip over an unpublished ledger says so instead of failing on run.

| # | id | Title | Ledgers | Days |
| --- | --- | --- | --- | --- |
| 1 | `p99-by-machine` | p99 job time by machine kind | `host-fingerprint` | 14 |
| 2 | `throughput-by-machine` | Prompt throughput by machine kind | `host-fingerprint` | 14 |
| 3 | `feeds-gone-quiet` | Feeds with no good fetch in the span | `feed-health` | 14 |
| 4 | `why-items-failed` | What failed to summarize, and why | `item-health` | 14 |
| 5 | `step-time-by-shard` | Where a run's time went, by step and shard | `span-rollup` | 7 |

**The observability words stay the observability words** (owner, 2026-09-28): `p50`, `p99`, throughput, cardinality, dimension.

### 2.15 What the page takes from the reference, and the three rules that decided it

The owner's reference is a query workbench screenshot and its HTML, kept at `test-results/telemetry_parquet_query_visualizer/code.html`. The feature-by-feature inventory with a verdict and a reason per feature is [docs/concepts/console-design/what-the-data-explorer-borrowed.md](../docs/concepts/console-design/what-the-data-explorer-borrowed.md), written by row 6. Three rules decided every rejection and they are here because they also decide anything added later.

| # | Rule | What it rejected |
| --- | --- | --- |
| 1 | **A number on this page is a reading or it is not printed.** | `Scanned 6.8 GB`, `AVX-512`, `PARALLEL THREADS: 12`, `Arrow IPC Cache Hit: 94.1%`. Rows 4 and 5 print milliseconds, files, bytes and rows, each measured |
| 2 | **The console owns a job once.** | The left icon rail, the breadcrumb, the collapse-all. The tab strip, the span control and the panel frame already exist |
| 3 | **A verdict needs a rule.** | The green and red status badges, the value coloured red for being high, the animated ring on the point labelled an anomaly. None has a rule behind it that this page could hold |

**The glyphs are taken; the font is not.** The reference draws Material Symbols from a Google font. This repository already has an icon system - Lucide, ISC licence, committed as source SVG, drawn from a generated sprite by id, with `frontend/tests/icons.spec.ts` failing both on a glyph nothing draws and on an id that does not exist. Row 6 adds the marks the page needs to that set, at one stroke width, with one provenance file and no third-party request.

## 3. Rows

### Row #1 - The span control shrinks and the strip gains a sixth tab

- **Scope:** `WindowControl.svelte` becomes five short tiles reading `1D 7D 14D 30D 90D` with no standing label and no per-tile price; `console.default_window_days` becomes 14; `RouteId` gains `data-explorer` on both sides; the strip draws a sixth tab behind `console.data_explorer_tab`, default off. **Every console route takes the control changes**, which is the cost and is stated in the pull request.

| # | Now | Becomes |
| --- | --- | --- |
| 1 | `Days shown` printed beside the tiles at every width | Gone from the eye. The `<legend class="sr-only">` stays, so a screen reader still hears the group's name, and the `D` on each tile carries the unit |
| 2 | Tiles read `1 7 14 30 90` | `1D 7D 14D 30D 90D` |
| 3 | Every tile reserves a second line for a `+2 months` price whether or not one is due | Gone from the tiles. **The price moves into `WindowStatus.svelte`**, the sentence that already stands under the strip, so the no-jump property the reserved room bought is kept by a line that was always there |
| 4 | `default_window_days` is 30 | 14 |
| 5 | `RouteId` names five routes | Six. One `ChangelogEntry`, one `version` move, no migration |

- **Files touched:**
  - `frontend/src/lib/components/WindowControl.svelte` (the label, the tile text, the price room and its `priceRoom` prop and styles)
  - `frontend/src/lib/components/WindowControlSource.svelte` (the same two changes, or a note in the pull request saying why its shape differs)
  - `frontend/src/lib/components/WindowStatus.svelte` (it gains the price sentence)
  - `backend/idhazh/contracts/console_band.py` (`RouteId.DATA_EXPLORER`, one `ChangelogEntry`, the `version` stamp, and the enum's docstring which says "the five console routes")
  - `backend/idhazh/telemetry/publish/console_band.py` (`ROUTES` gains its tuple; the `carries` sentence)
  - `frontend/src/lib/console/band.ts` (`RouteId`, `ROUTE_IDS`, `ROUTE_WORDS`, and the module docstring which says "the console is five routes")
  - `frontend/src/lib/console/ConsoleNav.svelte` (the sixth tab, drawn only when the flag is on)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`default_window_days` 30 -> 14 with its description saying why; `panel_groups` gains `data-explorer`; `data_explorer_tab` with its removal condition on the declaring line)
  - `frontend/src/lib/server/config.ts` (the fallbacks for both)
  - `frontend/tests/console-window.spec.ts`, `console-window-claims.spec.ts`, `console-chrome.spec.ts`, `console-nav.spec.ts`, `console-shell.spec.ts`, `console-band.spec.ts`
  - `backend/tests/contracts/test_console_band.py`
  - `tests/fixtures/` - every every-knob config fixture carrying `default_window_days` or `panel_groups`
  - `docs/architecture/publishing/console-payloads.md` (the route list)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`; the browser smoke on all five existing console routes at 390, 768 and 1440 in both themes, with the flag on and off. CI runs the full suite.
- **Oracle:** **the control got smaller, nothing below it moved, and an old payload still draws a console.** Measured in a browser on the built console at 390, 768 and 1440 in both themes: the control's own bounding box is smaller than before on at least one axis at every width, the page's total height is unchanged or smaller, and **selecting each of the five presets in turn moves no element below the strip by more than one pixel** - the property the reserved price room was bought for and the one a smaller control could silently lose. Separately, the committed band sample, which names five routes, validates against the new contract unchanged and draws five tabs with no gap. It cannot settle whether the new shape reads better, nor whether `Records` is the right word; Susan and Reader do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The reference's shape is the shape**: five short tiles, no label, no box, no icon | Owner, 2026-09-28 |
  | 2 | **The unit lives on the tile, not in a label.** `1D` says the same thing in one character that `Days shown` says in ten, and the screen-reader legend is untouched | Susan |
  | 3 | **The price keeps a permanent home, and it is the status sentence.** A price that appears and disappears moved seven panels by 15 px when it landed or cleared, measured 2026-09-09. Moving it to a line that is always drawn keeps that fixed and takes the height back | Susan, with Jony; the measurement is the control's own |
  | 4 | **14 days is the default on every route.** One default, or two routes answer the same question over different spans and a reader cannot compare them | Owner, 2026-09-28 |
  | 5 | **The control change and the tab ship in one pull request.** They are the two edits the console chrome takes, they share `config/appearance.json` and `knobs/console.py`, and splitting them buys a second review of the same file | Fowler |
  | 6 | **The label is `Records`.** The strip is a row of subjects - Pipelines, Summaries, Hardware, Judgement, Voices - and this tab's subject is the record itself. A verb would break the family | Susan, with Reader |
  | 7 | **The tab ships behind a flag in `appearance.json` until the page exists.** A tab pointing at a route that 404s is worse than no tab, and putting the flag in the console's own appearance block is what keeps this row off `config/idhazh.json`, which row 3 owns | Guardrail #6; Fowler |
  | 8 | **This row draws no panel.** It registers three panel ids that row 4 implements; the contract refuses a `judged_panel_ids` entry no route draws, which is why row 6 and not this row adds them there | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fork a smaller control for this page only | Two controls for one question, and two windows a reader cannot compare | Zero to take; costs the single-window property | Susan |
  | 2 | Keep the label and only drop the price room | Saves the vertical and not the horizontal, and the horizontal is what pushes the control off the strip when a sixth tab arrives | Zero; costs the strip its room | Susan |
  | 3 | Drop the price entirely | The wide span costs month files and a reader would meet the cost after choosing it | Zero; costs the reader the price before they pay it | Carmack |
  | 4 | Ship the control and the tab as two pull requests | They edit the same two config surfaces, so the second would take the first in anyway. Two reviews of one file | Zero; costs a review round | Fowler |
  | 5 | No tab; reach the page by link only | An operator surface nobody can find is an operator surface nobody uses | Zero; costs the page its readers | Jony |
  | 6 | Label it `Explore` | A verb among five nouns. The strip stops being a list of subjects | Zero; costs the strip its grammar | Susan |

---

### Row #2 - The door answers a written question on a sealed engine

- **Scope:** `ask()` and `askCost()` join `slice()` and `ledgerReach()` in `frontend/src/lib/data/ledger.ts`; `LEDGER_NAMES` widens to all twenty-six; `engine.ts` pre-loads its add-ons and then seals itself (section 2.6); `statement.ts` refuses anything that is not one read-only statement; `slice.ts` gains the writers'-files tier. **No page, no chart, no publishing, and no config file** - this is the reader, shipped with its own witness.

- **Files touched:**
  - `frontend/src/lib/data/ledger.ts` (`ask`, `askCost`; still the only module that composes a published address)
  - `frontend/src/lib/data/slice-shapes.ts` (`LEDGER_NAMES` widens to twenty-six; `AskOptions`, `AskResult`, `Column`, `FetchCost`, `SpanCost`)
  - `frontend/src/lib/data/ask-reader.ts` (new: hold the files, create and drop the views, run the statement, cap the rows - the body `ledger.ts` calls, beside `slice-reader.ts`)
  - `frontend/src/lib/data/statement.ts` (new: is this one read-only statement? - pure, no engine import, unit-testable on its own)
  - `frontend/src/lib/data/engine.ts` (the pre-load, the four `SET` statements and the lock, in both halves)
  - `frontend/src/lib/data/slice.ts` (the third tier, reading `RawDayIndex`)
  - `frontend/src/lib/data/compact-index.ts` (the hand copy of `RawDayIndex`)
  - `frontend/src/lib/console/waiting.ts` (`PanelState` gains `refused`, with its sentence)
  - `frontend/tests/ledger-door.spec.ts` (widened), `frontend/tests/explorer-seal.spec.ts` (new), `frontend/tests/statement.spec.ts` (new)
  - `frontend/scripts/test-groups.ts` (the two new specs join the `logic` group)
  - `tests/fixtures/ledger-door/` (the fixture ledger gains an unpacked day: a `RawDayIndex` and two writer files for it, one holding a row whose cells carry the hostile text in section 2.10)
  - `backend/tests/contracts/test_frontend_ledger_names.py` (new: the union in `slice-shapes.ts` and the registry in `config/ledgers.json` are each other, in both directions)
  - `backend/tests/contracts/test_frontend_index_shapes.py` (the hand copy gains `RawDayIndex`)
  - `frontend/tests/chart-vocabulary.spec.ts` (the single-engine walk still finds one importer)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (the second entry point, the views, and the seal order)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `pytest backend/tests/contracts -q`, `ruff check .`, `mypy backend`. CI runs the full suite. No browser smoke - this row draws nothing.
- **Oracle:** **the engine still reads parquet after it is sealed, and nothing else gets through.** In one Node run on the fixture ledger, in this order: a well-formed statement over two ledgers returns exactly the rows the same statement returns from the same files read in Python - **this assertion runs first, so the test cannot pass by sealing the engine into uselessness** - and then each of the eleven hostile statements in section 2.6 returns `refused`. Also: a date present in both a packed day and a writer file is read once; the unpacked day returns its rows and its date appears in `unpackedDays`; a zero-row span returns `quiet`; a date named by no index returns `unreachable`; an answer past `maxRows` returns `capped` with exactly `maxRows` rows; a span whose indexes exceed `maxFetchBytes` returns `refused` **with no data file fetched**; and a second call selecting one ledger cannot read the ledger the first call selected. It cannot settle whether an operator can write a useful query; row 4 and the owner do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The pre-load comes before the seal, and the list is measured rather than guessed.** The engine links only core functions and downloads the parquet reader at first use, so sealing first stops every query on the site. The row runs `SELECT extension_name FROM duckdb_extensions() WHERE loaded` after one parquet read on an unsealed engine and pre-loads exactly that list | Carmack; section 2.1 fact 1 |
  | 2 | **The seal ships in both halves, browser and Node.** A seal only the browser has is one a build-time reader can be used around, and the Node half is what the oracle drives without a browser | Carmack |
  | 3 | **The oracle proves a good query works before it proves a bad one fails.** A seal that broke parquet would pass every refusal assertion, which is the failure this ordering exists to catch | Fowler |
  | 4 | **A registered buffer is a file, so the door creates one view per selected ledger and drops every unselected one on every call.** Without the drop, a view from an earlier run lets a statement read a ledger the operator did not select and did not see the cost of | Fowler; section 2.4 |
  | 5 | **The operator's text is a statement, and the structured predicate stays for panels.** The door refused raw SQL because the caller there is a panel and fetched text could reach it. The caller here is a person typing into their own browser, and the text they type never leaves it. Both are true at once, which is why this is a second entry point and not a change to the first | Fowler and Andre, 2026-09-28; owner asked for the box |
  | 6 | **The seal is settings and registration, never a text rule over SQL.** A denylist over a language with function syntax is not a boundary. `statement.ts` exists to give a fast, readable refusal, not to be the boundary | Carmack, with Andre |
  | 7 | **The engine takes a caret range, not a pin, and the seal test is the guard.** A pin would only delay the day a setting changed; the hostile set fails on the upgrade that changed it, in the pull request that raised the version | Carmack, on the owner's ruling of 2026-09-28 |
  | 8 | **This row reads no config file, and its two ceilings arrive as arguments.** It is what makes wave 1 three-wide: the knobs that bound the page are minted by the row that reads them, row 4 | Fowler |
  | 9 | **`ask()` goes through the page keeper and never calls `engine.register()`.** The keeper is what stops a file crossing the network or entering the engine twice, and in a browser registering takes the buffer, so a second registration would read an empty file | Carmack; section 2.1 module 5 |
  | 10 | **`LEDGER_NAMES` widens to the whole registry, and a test binds it both ways.** A ledger declared and not published answers `missing` by name, which is more useful than being absent from the list | Fowler |
  | 11 | **The writers' files are read through `RawDayIndex`, which already exists.** This plan declares no persisted shape | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Seal the engine at start and drop the settings that break parquet | There is no subset that both seals and reads: `enable_external_access` off blocks the add-on download and `autoload` off blocks its use. Pre-loading is what makes both true | Zero to write; costs either the seal or every query | Carmack |
  | 2 | Ship the seal without the pre-load and add add-ons as queries fail | The first failure is on a deployed site, and the reach for the setting is the reach ESCALATE trigger 2 exists to stop | Zero now; costs a broken site and a weakened seal | Carmack |
  | 3 | Build the page's own engine module, separate from the door | Two importers of the engine, and the single-engine rule becomes unenforceable | Zero; costs the single-engine rule | Fowler |
  | 4 | Register each ledger's files under a name the caller chooses, so no view is needed | The engine mints names precisely so no caller and no fetched text can name a file. Changing that to save one statement per ledger trades the property for a line | Zero; costs the minting rule | Carmack |
  | 5 | Keep the structured predicate and add operators until it can express a join | It becomes a query language of our own, badly, and an operator has to learn it | Months, and the result is worse than SQL | Owner, 2026-09-28 |
  | 6 | Parse the statement ourselves and allow only what we understand | A SQL parser is a dependency or a mistake. The engine's own settings are the boundary and they are enforced inside the engine | A parser dependency, and a false sense of a boundary | Carmack |
  | 7 | Read only packed files, as panels do | The answer stops two days short of now, which is the question an operator most often opens this page to ask | Zero; costs the page its point | Owner, 2026-09-28 |
  | 8 | **Open the engine's own URL access** - `enable_external_access` on, the remote-file add-on loaded - so a statement can name `https://...` directly | It is the one thing the whole seal exists to prevent, and it buys nothing row 6 does not already buy. **What the reader would lose by not having it**: writing a URL inside the statement rather than picking dates and letting the door choose the address - a keystroke, not a capability | Zero to write, and it converts every hostile statement from refused to allowed | Carmack and Andre; ESCALATE trigger 2 |

---

### Row #3 - Every declared ledger reaches the site, capped at the widest span

- **Scope:** `ledger.published` names every ledger `config/ledgers.json` declares that has been migrated; the build copies their packed periods, their indexes, the unpacked days with their `RawDayIndex` files, and `config/ledgers.json` itself, **capped at the widest span the console can ask for** (section 2.8); `ledger.archive_base_url` is declared, shipping empty, and `connect-src` is computed from it; the payload ceilings are set from the built files. **No frontend source, no page, no d3.**

- **Files touched:**
  - `config/idhazh.json` (`ledger.published`; `ledger.archive_base_url` empty; `page_weight.payload_ceilings_bytes` gains one entry per published ledger's `index/daily.json` and one for `ledgers.json`)
  - `backend/idhazh/contracts/knobs/ledger.py` (`published`, `archive_base_url` with the same validator shape `engine_extension_repository` already carries)
  - `backend/idhazh/contracts/knobs/page_weight.py`
  - `frontend/scripts/copy-visuals.mjs` (the copy step gains the raw tier for unpacked days, the registry file, and the span cap read from `console.window_presets`; **a second staging script is Guardrail #4**)
  - `frontend/asset-base.js` (`connect-src` gains the archive origin, computed from the same config value)
  - `frontend/scripts/build-canary.mjs` (the copy step fails loudly when its root is missing)
  - `frontend/scripts/bundle-gate.mjs`
  - `.gitignore` (one line beside the payload directories already there)
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/contracts/test_published_covers_the_registry.py` (new)
  - `frontend/tests/page-weight.spec.ts`
  - `docs/concepts/growing-reads.md` (the raw copy's cost and its bound)
  - `docs/architecture/publishing/console-payloads.md` is **not** touched here - row 1 owns it
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`, `npm --prefix frontend run test:changed -- --list` then the selected checks. The bundle gate and the site-cap measurement both walk the built tree and are re-read after the copy step lands. CI runs the full suite.
- **Oracle:** **every published address resolves, each date is reachable through one tier, and nothing is copied that no page could ask for.** Over a built tree: every entry in every published index names a file that exists under `build/`; every date in the union of the three tiers is covered by exactly one of them; every ledger named in `ledger.published` is declared in `config/ledgers.json`; and **the oldest date reachable under `build/state/` is no older than `max(console.window_presets)` days before the build, rounded out to the whole month that holds it** - so raising a preset widens the copy and nothing else does. The built site's total is **measured and recorded beside the 1 GB cap as a reading, not as a gate** - this row publishes every migrated ledger whatever it weighs (decision 6). It cannot settle whether a browser can query the files; row 2 does.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The registry is published, and the page fetches it.** `config/ledgers.json` is copied verbatim. The page's ledger list is then a fetched fact rather than a baked one, which is what makes the refresh in row 4 mean something and what leaves the shell with nothing baked in | Fowler, on the owner's ruling of 2026-09-28 |
  | 2 | **Only unpacked days are published from the raw tier, and packing removes them.** The raw copy is bounded by how far behind packing is - two days at the shipped defaults - and never by how long the project has run. **The bound is stated beside the copy step and in `growing-reads.md`** | Guardrail #12; Carmack |
  | 3 | **The copy reaches back exactly as far as the widest preset, and the figure is read from config.** A file older than any span can ask for is weight nothing can fetch. **Publishing is site-wide and this cap is not a per-route setting**: one staged tree, one address, any page may read any of it | Carmack, on the owner's ruling of 2026-09-28 |
  | 4 | **The site total is measured in this row, not estimated.** `state/` measured 66.5 MB on 2026-09-28 across seventeen directories; **that is a reading of the working tree, not of a built site**, and it is here to say the order of magnitude rather than to be the answer. The row publishes, measures the built tree, and records the margin | Guardrail #10 |
  | 5 | **A ledger that has not been migrated is declared and not published.** It appears in the picker and answers `missing` by name. Listing it is how an operator learns the project has it | Fowler |
  | 6 | **Every migrated ledger ships, whatever it weighs, and the row never narrows the set to fit.** Where a future measurement shows the 1 GB cap approaching, what moves is the gardener's keep windows - how much history is held - and never which ledgers the owner is allowed to look at | Owner, 2026-09-28 |
  | 7 | **Every column of every published ledger is published.** A narrowed copy stops being the ledger, which is the property that makes it unable to disagree with `state/` | Owner, 2026-09-26 |
  | 8 | **This row declares `archive_base_url` and reads it in `asset-base.js`; row 6 is the first to fetch through it.** Declaring it here is what keeps `knobs/ledger.py` and `config/idhazh.json` in one row's hands, and shipping it empty means the declaration changes no behaviour | Fowler |
  | 9 | **This row supersedes the earlier three-ledger publishing row, whichever lands first.** If that row has landed, this one widens its list and its copy step. If it has not, it collapses into this one and its dependants read this row's pull request | Fowler; plan 51's row titled "The three ledgers the console reads are published" |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Publish three ledgers and no more | The page answers questions about three ledgers out of twenty-six, which is a panel with extra steps | Zero; costs the page its purpose | Owner, 2026-09-28 |
  | 2 | Publish the whole raw tier | It grows with the archive forever, which is Guardrail #12 pointed at the site cap | Zero now; costs the cap later | Carmack |
  | 3 | Generate a ledger list at build time instead of copying the registry | A generated list is a second copy of the registry that somebody has to keep in step, and the registry is already the shape a contract validates | Zero; costs a second source of truth | Fowler |
  | 4 | Have the page probe for a ledger's index and treat a 404 as "not published" | A 404 stops being a defect signal and becomes a normal answer, so a broken deploy reads as an unpublished ledger | Zero; costs telling an absence from a fault | Fowler |
  | 5 | Declare `archive_base_url` in row 6, where it is first read | It would put two rows on `knobs/ledger.py` and `config/idhazh.json`, and row 6 runs alone anyway, so the split buys nothing | Zero; costs wave 1 its disjointness | Fowler |

---

### Row #4 - The page: pick the ledgers and the days, write the question, read the table

- **Scope:** `/console/data-explorer/` exists, prerenders nothing, fetches the registry and the indexes on mount, and draws three panels - the ask, the rows, the shape's placeholder. It carries the ledger list with its filter and refresh, the schema panel, the editor with its line numbers and highlighting, the example strip, the run button, the cost line before and after, and the table. `console.data_explorer_tab` is set true and the field deleted, which is its declared removal condition. **No chart, no saved list, no address handling** - row 5 adds those into the panels this row creates.

- **Files touched:**
  - `frontend/src/routes/console/data-explorer/+page.ts` (new: `prerender = false`, `ssr = false`)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (new: the route, its three `Panel` elements with the ids in section 2.2, the jump links from the group)
  - `frontend/src/lib/console/explorer/LedgerList.svelte`, `SchemaPanel.svelte`, `QueryEditor.svelte`, `ExampleStrip.svelte`, `CostLine.svelte`, `AnswerTable.svelte` (new)
  - `frontend/src/lib/console/explorer/registry.ts` (new: fetch and refresh `ledgers.json`; the hand copy in section 2.9)
  - `frontend/src/lib/console/explorer/answer.ts` (new, pure: sort, page, format a cell as text)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`explorer_row_page`, `explorer_max_rows`, `explorer_max_fetch_bytes`, `explorer_examples`; `data_explorer_tab` removed)
  - `frontend/src/lib/console/ConsoleNav.svelte` (the flag's last reader goes with it)
  - `frontend/src/lib/server/config.ts` (the new knobs' fallbacks), `tests/fixtures/` (the every-knob fixtures)
  - `frontend/scripts/test-groups.ts` (the two new specs join the `console` group)
  - `frontend/tests/data-explorer.spec.ts` (new), `frontend/tests/data-explorer-cells.spec.ts` (new: section 2.10's four rules)
  - `backend/tests/contracts/test_frontend_registry_shape.py` (new: the hand copy of the registry's fields)
  - `docs/architecture/publishing/console-payloads.md` (the route's panels)
- **Acceptance gates:** the browser smoke on `/console/data-explorer/` at 390, 768 and 1440 in both themes (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, and **the page draws each of the five states in section 2.12 plus a capped answer**. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **a question typed into the box comes back as the right rows, and nothing on the page is a link a ledger wrote.** Against the fixture ledger served over HTTP: selecting two ledgers and 14 days, typing a join and pressing run produces exactly the rows the same statement produces in Python over the same files; the cost line's file count and byte count equal what the network actually fetched; every state renders and no two render the same; and the hostile fixture row renders as text with no `<a>`, `<script>` or `<img>` anywhere in the table's subtree. It cannot settle whether the page is good enough to ship; Susan rules that (CLAUDE.md section 14).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The page prerenders nothing, and this is not a new argument.** `adapter-static` already runs `fallback: '404.html'` and two routes already ship no document. The cost is the fallback's HTTP 404 status, which those routes already carry | Owner, 2026-09-28 |
  | 2 | **No other plan's rule is edited to let this page through.** The count of prerendered routes does not move, so nothing needed rewording - and rewording somebody else's trigger to admit your own page is how a rule stops meaning anything | Fowler, CLAUDE.md section 1 |
  | 3 | **The ledger list is fetched, and Refresh re-fetches it.** `ledgers.json` and each selected ledger's index are re-read with `cache: 'no-store'`, and the page says what moved - a ledger's newest day and its row count. A refresh that re-reads something that cannot change is a button that teaches distrust | Owner, 2026-09-28 |
  | 4 | **The column count and the schema panel are always from the engine.** After a run they describe the answer; before one they describe the selected ledgers, and the label says which | Owner, 2026-09-28 |
  | 5 | **The editor is a `textarea` with a highlighted layer behind it.** About sixty lines, no dependency, and it keeps the keyboard and screen-reader behaviour a real text box has | Carmack, with Susan |
  | 6 | **The cost is shown before the run, and the running total beside it.** `askCost()` reads the indexes alone; the total is what this page has already pulled into the engine, because the keeper holds every file for the page's life and the ceiling should never be the first news of it | Carmack; section 2.5 rule 6 |
  | 7 | **`explorer_max_fetch_bytes` is set from a reading.** The row widens the span until the tab is unusable and takes the step below that. A ceiling guessed in a document is a ceiling that refuses a span that would have worked | Guardrail #10 |
  | 8 | **An unpublished ledger stays in the list and says so.** The list is what the project has, not what happens to work today | Susan, with Fowler |
  | 9 | **This row removes the flag it did not add.** The flag's declared removal condition is this merge, and a flag removed by a later row is a second implementation living one row longer than it had to | Guardrail #6 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Prerender the shell like the other five console routes | It would make the page the tenth prerendered route for no gain: it has no loader and nothing to bake, so the document would be chrome and a spinner | Zero; costs the plan a clean answer to N4 | Owner, 2026-09-28 |
  | 2 | CodeMirror for the editor | Roughly 120 KB for line numbers and highlighting, on a route that already loads a query engine | About 120 KB, measured before taking it | Carmack |
  | 3 | A ledger tree with folders, as the reference draws | Twenty-six ledgers at one level. A chevron that opens one folder is a click that buys nothing | Zero; costs a click | Jony |
  | 4 | Group the picker by the registry's twenty families | Twenty groups over twenty-six ledgers is a grouping that holds one thing each. The family name goes on the row as a quiet second line instead | Zero; costs nothing, which is why it is not taken | Jony |
  | 5 | Let the operator pick the file tier by hand, as the reference's grain selector does | Choosing the tier by hand is how a date gets read twice and every number doubles | Zero; costs correctness | Fowler |
  | 6 | One ledger at a time | A join needs two, and a join is the question a panel cannot already answer | Zero; costs the page its point | Owner, 2026-09-28 |
  | 7 | Split the page into a shell row and a table row | There is no intermediate state worth shipping: a console route that renders an empty page is a tab that lies | Zero; costs a pull request and ships a lie | Fowler |

---

### Row #5 - The answer gets a shape, and a question is kept, found again and shared

- **Scope:** the third panel draws the answer as a chart chosen by the rule in section 2.11, from the vocabulary page's list and its readout strip, or a named refusal that stays. A question is saved in this browser under a name and drawn on the example strip; the last runs are listed with their timing and row count; and the page address carries the ledgers, the days and the question, so a link reopens it **into the editor without running it**. Copy-to-clipboard as JSON or as a Markdown table.

**What the address carries.**

```
/console/data-explorer/?ledgers=host-fingerprint,item-health&days=14&q=<the question>
```

| # | Rule |
| --- | --- |
| 1 | Real query parameters. No fragment, so the address reads as an address and can be shared, bookmarked and searched (owner, 2026-09-28) |
| 2 | Opening it **fills the editor and does not press run** |
| 3 | `q` is the statement deflated with `CompressionStream('deflate-raw')` and base64url-encoded, so the address holds a real question rather than a short one |
| 4 | **This row measures the longest address GitHub Pages answers** and sets `console.explorer_query_max_chars` from that reading, so a statement that fits the box always fits a link. It does not assume a limit |
| 5 | A statement past the limit still saves and still runs. The page says the link carries the ledgers and the days only, and offers the clipboard instead |
| 6 | `ledgers` is parsed against `LEDGER_NAMES` and an unknown name is dropped with a sentence naming it. **No part of the address becomes an identifier or a path** |
| 7 | **What this costs, stated once**: text after `?` is sent in the request, so the statement appears in the log of whoever serves the page. It is your own query over your own published data. If that ever matters, moving `q` after a `#` removes both the limit and the log entry and costs nothing else |

- **Files touched:**
  - `frontend/src/lib/console/explorer/shape.ts` (new, pure: columns in, chart type and its geometry arguments out)
  - `frontend/src/lib/console/explorer/ShapePanel.svelte` (new: the type radio group and the chosen chart)
  - `frontend/src/lib/console/explorer/keep.ts` (new, pure: the saved list and the history, their bounds and their eviction)
  - `frontend/src/lib/console/explorer/address.ts` (new, pure: to and from the address, including the compression)
  - `frontend/src/lib/console/explorer/SavedStrip.svelte`, `HistoryList.svelte`, `CopyAnswer.svelte` (new)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (the third panel's body; the first panel's strip and disclosure; reading the address on mount)
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (`explorer_chart_min_rows`, `explorer_rank_max`, `explorer_saved_max`, `explorer_history_max`, `explorer_query_max_chars`), `frontend/src/lib/server/config.ts`, `tests/fixtures/`
  - `frontend/tests/data-explorer-shape.spec.ts` (new), `frontend/tests/data-explorer-keep.spec.ts` (new)
  - `frontend/scripts/test-groups.ts`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (one section: how a type is chosen when nobody wrote the panel)
  - `docs/reference/benchmarks/address-length-on-pages.md` (new: the measured limit, its method and its date)
- **Acceptance gates:** the browser smoke on `/console/data-explorer/` at the three widths in both themes, including opening a shared address in a fresh context; local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **the shape follows the columns, and a question survives the round trip without running itself.** For one recorded answer of each of the five cases in section 2.11, `shape.ts` returns the named type and the panel draws it with its readout strip populated at rest; for the fifth it draws the refusal with its sentence and the panel keeps its height. For a set of statements including one at the measured ceiling, `address.ts` returns the identical text after encode and decode; opening a built page at such an address fills the editor, leaves the run button unpressed and **issues no data request until it is pressed**; the saved list keeps exactly `explorer_saved_max` entries and names the one it dropped. It cannot settle whether the chosen type is the best one for a given answer, nor what the real address limit is on a host we do not control - the operator's override and the benchmark record do.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The shape and the keeping ship in one pull request.** Both add into `+page.svelte`, which row 4 created, so as separate rows they would be two workers on one file and a merge nobody reviewed | Fowler; execute-a-plan's shared-surface rule |
  | 2 | **The type is chosen from the columns, and the operator may override within what qualifies.** The reference lets you draw a line through data with no time axis, which is a chart that asserts an order the data does not have | Susan |
  | 3 | **The refusal is a state of the panel, not an alarm.** An answer with no number in it is a normal outcome, and a red dismissible banner for a normal outcome is how people learn to dismiss banners | Susan |
  | 4 | **The refusal's words are plain.** `Nothing here to draw: the answer has no number in it.` - not the reference's `unindexed binary payload blobs with 0 aggregate metrics` | Reader, CLAUDE.md section 0b |
  | 5 | **No new chart type is added here.** If an answer wants one, that is Susan's call on the vocabulary page and a separate change | Susan |
  | 6 | **No point is highlighted as an anomaly and nothing animates to draw attention.** The page has no rule that makes a value anomalous, and a mark that says "look here" without one is a verdict nobody issued | Susan |
  | 7 | **The address carries the question, in query parameters, with no fragment** | Owner, 2026-09-28 |
  | 8 | **An address never runs a query.** A link that executed a stranger's statement would be the one hole the seal cannot close, because the statement would be running with the reader's consent implied rather than given | Fowler and Andre; ESCALATE trigger 4 |
  | 9 | **The statement is compressed before it is encoded.** SQL compresses several times over, so the practical ceiling stops being a design constraint | Carmack |
  | 10 | **The limit is measured before it is used.** There is no limit in the URL specification; the binding one belongs to the host, and 8 KB is a common default rather than a reading | Guardrail #10 |
  | 11 | **Saved questions live in this browser and nowhere else.** A committed, named query would be a reader of the columns it names and would go red when one is renamed; this one simply fails for the person who saved it, which is the right cost for a scratchpad | Fowler |
  | 12 | **Copy to clipboard, never a file.** The owner refused a download; the clipboard is what it was wanted for, and no file means no spreadsheet and no formula cell | Owner, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Let the operator pick any type for any answer, as the reference does | A line through unordered categories is a false statement drawn confidently | Zero; costs the page its honesty | Susan |
  | 2 | No chart at all - the table is the answer | A bare table of numbers with no shape beside it fails sufficiency gate 4 by name, and a shape is why a query page beats a terminal | Zero; costs the page a gate | Susan |
  | 3 | A chart library with automatic type inference | A second charting library, against telemetry-intent N5 | A dependency and the N5 rule | Fowler |
  | 4 | Put the question after `#` | The owner ruled query parameters so the address reads as one. The fragment stays available as decision 10's escape hatch if a measurement ever demands it | Zero; it is held in reserve rather than refused | Owner, 2026-09-28 |
  | 5 | Run the query when a shared address opens | A link that runs a stranger's statement, on a page that holds every ledger | Zero; costs the boundary | Fowler |
  | 6 | Commit saved questions to the repository | They become readers of the columns they name, with a contract, a test and a review for each. That is a different feature and a good one | Its own row | Fowler |
  | 7 | A CSV download | Refused by the owner. It also re-opens the formula-injection case a refused file closes for free | Owner decision, plus the escaping rule | Owner, 2026-09-28 |
  | 8 | Ship the shape and the keeping as two pull requests | Both edit `+page.svelte`. The second would take the first in anyway, and the pool has one slot at this depth | Zero; costs a review round | Fowler |

---

### Row #6 - Reach past the cap, the glyphs, the gates, the pictures and the how-to

- **Scope:** a date older than the site's cap is fetched from the committed repository through `ledger.archive_base_url` (section 2.8), which row 3 declared; the marks the page draws join the icon set at one stroke width; the three panels join `console.judged_panel_ids` and pass the ten sufficiency gates or carry a `## Design rationale` line each; the panel captures run at the three widths in both themes; and the how-to page and the borrowed-from-the-reference page are written.

- **Files touched:**
  - `frontend/src/lib/data/slice.ts` (the fourth tier), `frontend/src/lib/data/fetched-bytes.ts` (the archive prefix), `frontend/src/lib/data/ledger.ts` (the archive address, composed here and nowhere else)
  - `frontend/src/app.d.ts` (the archive define, beside the three already there)
  - `frontend/vite.config.ts` (the define, from `asset-base.js`'s value)
  - `frontend/tests/ledger-door.spec.ts` (the fourth tier), `tests/fixtures/ledger-door/` (a date past the cap, served from a second root)
  - `frontend/src/lib/icons/svg/` (the marks in section 2.15, from Lucide, unmodified source), `frontend/src/lib/icons/PROVENANCE.md`
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/appearance.py` (`icons.stroke_width`), `backend/idhazh/contracts/knobs/console.py` (`judged_panel_ids` gains the three ids), `frontend/src/lib/icons/Icon.svelte`
  - `frontend/tests/icons.spec.ts` (the set grows; the two-way check is unchanged)
  - `frontend/tests/panel-sufficiency.spec.ts` (`DRIVERS` gains one entry per judged id, putting each panel into its four nothings)
  - `frontend/tests/panel-captures.spec.ts` (the route joins the capture list, which is read from `panel_groups`)
  - `docs/how-to/query-a-ledger-from-the-console.md` (new)
  - `docs/concepts/console-design/what-the-data-explorer-borrowed.md` (new: the feature inventory, section 2.15)
  - `docs/concepts/design-system.md` (the icon section gains the stroke-width knob and its reason)
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** the panel captures at 390, 768 and 1440 in both themes plus the unreachable shot; the ten sufficiency gates green on all three ids; `python backend/utilities/doc_load.py` before and after; the browser smoke on `/console/data-explorer/` with a date past the cap; local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** **a date past the cap answers from the repository, every mark the page draws is in the set and nothing in the set is undrawn, and every judged panel passes its gates or names its rationale.** With the archive value set to a second fixture root, a span reaching before the cap returns the same rows as the same statement in Python over the same files, and with the value empty that span returns `unreachable` naming its date. `icons.spec.ts` is green in both directions after the set grows; each of the three panel ids is judged, has a driver for its four nothings, and either passes all ten gates or carries a `## Design rationale` line naming the gate and the reason; and seven pictures exist per panel. It cannot settle whether the page is good enough to ship - that is the 390 dark picture and Susan.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The reach past the cap lands last, with the polish.** It is the one capability nothing else waits on: the page works over ninety days without it, the knob row 3 declared ships empty so the default behaviour is unchanged, and putting it here is what let rows 2 and 3 run in the same wave | Fowler |
  | 2 | **The page fetches the archive; the engine never does.** `ledger.ts` composes the address, `fetched-bytes.ts` fetches it, the keeper hands the engine one more buffer. No engine setting changes and no ESCALATE trigger fires | Carmack; section 2.8 |
  | 3 | **The marks are taken and the font is not.** The reference draws Material Symbols from a Google font; this repository already has Lucide committed as source SVG with a two-way test. Taking the font would add a third-party request on every page load and a second licence for marks we already have | Susan, with Carmack on the request |
  | 4 | **One stroke width for the whole set, from a knob, chosen from the pictures.** Lucide ships at 24 px with a 2 px stroke and the set draws at 16 px, so the shipped weight reads heavier than the type beside it. A per-icon weight would be a pile rather than a system | Susan |
  | 5 | **The stroke width changes the existing glyphs too**, and the pull request carries their pictures. A set with two weights is the thing the knob exists to prevent | Susan |
  | 6 | **The three panels are judged, not merely pictured.** A page whose whole job is reading an answer is the last place a sufficiency gate should be opted out of | Susan |
  | 7 | **The how-to page ships with the page, not after it.** The Docs button points at it, and a button pointing at nothing is worse than no button | Reader |
  | 8 | **The borrowed-from inventory is a concepts page, not a plan appendix.** A plan is distilled and archived; the reasons three classes of feature were refused outlive it and decide the next addition | Fowler, CLAUDE.md section 5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Put the archive tier in row 2, with the rest of the door | It needs `ledger.archive_base_url`, which row 3 declares, so the two rows would share `knobs/ledger.py` and wave 1 would drop to two slots | Zero; costs a parallel slot and a day | Fowler |
  | 2 | Load the Material Symbols font from Google | A third-party request for every reader, a second icon system, and roughly a font's worth of bytes for about twenty-five marks | Zero to write; costs the request and the second system | Susan and Carmack |
  | 3 | Inline the page's SVGs directly rather than joining the set | It is exactly the state the icon rule was written to prevent, and the two-way test stops seeing them | Zero; costs the system | Susan |
  | 4 | Capture the panels but do not judge them | Two gates read attributes the panels would then not need to carry, and a panel that is never judged never has to be good | Zero; costs the gates their subject | Susan |
  | 5 | Leave the icon weight as Lucide ships it | The marks read heavier than the type beside them at 16 px, which is the "pile rather than a system" failure | Zero; costs the set its coherence | Susan |

## Dependent plans

- [`20260924-51-console-fetches-and-draws-its-own-data-plan.md`](20260924-51-console-fetches-and-draws-its-own-data-plan.md). Its row titled **The query door module and its two entry points** is DONE and is what section 2.1 maps; every frontend row here extends it. Its row titled **The three ledgers the console reads are published** is PENDING and **row 3 here supersedes it** - whichever lands first, the other reads its pull request (row 3 decision 9). Its row titled **One panel end to end** depends on that publishing row and is satisfied by either.
- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md). Row 3 here publishes what that plan has packed, and row 2 reads the `RawDayIndex` its row titled **The index and watermark shapes are declared** already delivered (#1136). The more ledgers that plan migrates, the more of the picker works; **no row here blocks on any of them**, because an unmigrated ledger is declared, listed and answers `missing` by name.
- [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md). Delivered (#613, #614, #645, #649). Its ruling keeps the six prerendered routes and its section 6 is the executable price of reversing that. **This plan neither reverses it nor depends on it**: the new route simply never prerenders, the way the two dated routes already do. **It also inherits one contradiction and does not repair it** - telemetry-intent N4 says the existing prerendered routes come off, and plan 26 ruled they stay. That disagreement is older than this plan and belongs to whichever of the two moves next.
- [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md). It moves fifty panels onto the query door. **It takes the seal in row 2 whether it wants it or not**, because the seal lives in the one engine module both use - which is why the oracle there proves a good query works before it proves a bad one fails.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan serves.
- [docs/architecture/publishing/how-the-query-door-answers-a-panel.md](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md) - the door as row 2 extends it.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules the door obeys.
- [docs/concepts/design-system.md](../docs/concepts/design-system.md) - the ten sufficiency gates and the icon rule.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
