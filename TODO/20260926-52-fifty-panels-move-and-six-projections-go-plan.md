# Plan 52 - The console's panels ask the ledger when they are looked at, ECharts leaves, and six projections go

**Last Updated**: 2026-09-28

**Level**: 5 (CLAUDE.md section 6). Row 5 changes a persisted payload every console document carries, and row 12 deletes a committed ledger that no revert of code brings back. The route rows are Level 3: each crosses code and published data on one route. **Authorizing this plan is the design consultation section 6 asks of rows 5, 11 and 12.**

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3, N4, N5, N7 and N8 - a panel asks `state/` for the columns and days it draws, when it is looked at, drawn in d3, and no pre-shaped copy of a ledger survives under `frontend/`. **Contract**: section 2 declares every file, query, type, knob, field, sentence and deletion the rows need; section 2.7 is Susan's panel verdicts of 2026-09-26 turned into ids, queries and types. **Code**: the thirteen rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates each row to a worker; keep parallel N = 4 rows in flight as a running pool, refilling a slot the moment a worker returns and never waiting on a merge; a row is ready when its `Depends-on` rows are DONE and its `Files touched` list shares no entry with a row in flight; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock; **pause the whole pool while row 4 measures**; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Blocked by** | Row 1 starts now; row 2 follows it, and row 10 follows both. Every other row waits on work outside this plan, listed with its title under the Reckoner: plan 51's rows titled **The query door module and its two entry points** (draft pull request #1154, held for the owner's ruling on how the engine gets its parquet reader), **The three ledgers the console reads are published** and **One panel end to end: the browser fetches the ledger and draws it in d3**, and plan 50's row titled **The three ledgers the console's routes read become parquet**. **Rows 6 to 9 also merge only when compaction is switched on** for every ledger the row reads (plan 50 ships each compaction report-only, its deviation 98) and the published `daily.json` and `monthly.json` together cover `max(console.window_presets)` days. The worker checks both on the live site at dispatch |
| Why this plan exists | A console panel reads a file the build wrote in advance, so the question it can ask was fixed by whoever wrote that file. The browser can now ask the ledger directly. This plan moves every panel whose facts are in the three published ledgers onto the query door, redraws every chart that still uses ECharts so it can be uninstalled, applies Susan's verdicts, and deletes the six telemetry projections under `frontend/public/` once nothing reads them |
| Hard scope - in | - Each route gets its own console file, gate drivers and test expectations, so the route rows share no file (row 1).<br>- The chart types become ready for a route: the ranked list draws a range and a floor, the date series carries the settings line, and every type carries its readout (row 2).<br>- Every panel's query is declared in code before any panel draws it, with the loading states every route shares (row 3).<br>- The door is measured at the console's real volume before any route moves (row 4).<br>- The band reads the ledgers and carries the settings and checker changes; four projections nothing draws go (row 5).<br>- Every panel whose facts are in `item-health`, `scores` or `host-fingerprint` asks the door at view time (rows 6 to 9); every panel on the console gets its id and gate attributes (rows 6 to 10).<br>- Susan's verdicts, applied panel by panel: panels 4 and 15 deleted, panels 3 and 13 replaced, panel 22 folded into panel 18, the new panels added, the rest kept or redrawn (section 2.7).<br>- The `telemetry` and `run-timeline` projections go (row 11); the `span-rollup` ledger goes and one item's trace becomes a command (row 12); `echarts` is uninstalled (row 13) |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. **A panel needs a column its query in section 2.7 does not name, or a column in `UNREAD_CELLS` or on the withheld list (section 2.3).** Stop and report the column and why: row 3's registry is the one record of which surface reads a column.<br>2. **A panel on the build-time list (section 2.8) is asked to move to the door.** Its dataset is not published; moving it is the out-of-scope plan below.<br>3. **Row 4 misses its pass line.** The fixes are in the query door, which is plan 51's module (section 2.10).<br>4. **Deleting any path under `state/` other than `state/span-rollup/`.**<br>5. **An owner ruling in section 2.11 differs from its default.** Re-open only the rows it names.<br>6. **A route row needs to edit a file on the cross-route list (section 2.2) or a file that names another route.** Stop: the file belongs to the row the list names |
| Chosen strategy | Contracts first, then one pull request per route, then deletions. Rows 1 to 3 take every file the route rows would otherwise share off the table - the panel lists, the gate drivers, the test expectations, the chart components, the column registry and the loading states - so the route rows run side by side. Ruled by Fowler (CLAUDE.md section 14), 2026-09-28 |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 4 and 12 run alone |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Publishing the other datasets the console reads**: `state/day-metrics/`, `state/feed-health/`, the run manifests and item facts inside the digest day files, the source-health view, and `state/content-similarity-judge/` | Fifteen panels, and the feed row of a sixteenth, keep a build-time read (section 2.8), so Pipelines, Summaries, Voices and Judgement stay prerendered and N2, N3 and N4 are not met for those panels. They draw without ECharts, so N5 is met. **The reader loses** nothing they have today; they do not gain view-time freshness on those panels | Its own plan: each dataset needs a parquet contract, a writer through the ledger door, a compaction task, a publish entry and a `LedgerName` member - plan 50's row 9 five more times. Plan 50's ESCALATE trigger 3 makes each migration a person's call |
| Changes to the query door itself (a file cache, a column-shaped result, a "newest N days" ask, a structured aggregate) | Rows 6 to 9 take the door as plan 51 ships it. Row 4 says whether that is fast enough | Plan 51's owner, who is handed the recommendations in the found-while-planning table |
| New questions beyond Susan's verdicts | None today | A later Susan pass |
| `failed_field` (verdict 27) | It stays in `UNREAD_CELLS`, empty on every committed row | A row that gives it a writer or deletes the column |
| A query page where an operator types a question | None today. The door is a module a panel calls | Its own plan, with its own injection surface (plan 50 row 10's evidence) |

### The intent this plan serves

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N2 | The browser queries the parquet itself | **Delivered for every panel whose facts are in the three published ledgers**: 35 of the console's 52 panels here, plus plan 51's `platform-mix`. The other fifteen, and `feeds-failed`'s feed row, are the first out-of-scope row |
| N3 | The browser fetches its own data at view time | The same 35 |
| N4 | The prerendered routes come off it | **Hardware's document carries no ledger data** after row 8. Whether it also drops the prerender flag is owner ruling R2 (section 2.11) |
| N5 | d3 is the only charting library | **Delivered.** Row 13 uninstalls `echarts` and deletes `Chart.svelte`, `engine.ts`, `core.ts` and `frontend/src/lib/server/chart-render.ts` |
| N7 | No telemetry projection survives in `frontend/` | **Delivered for the six** (rows 5 and 11). `console/band.json` is owner ruling R1 |
| N8 | `frontend/` holds UI code, not artefacts | The same six |

## 1. Status Reckoner

**Thirteen pull requests.** One row is one pull request. The dispatcher is a running pool: a slot frees when a worker returns, never when a pull request merges. `Depends-on` and `Files touched` are the readiness test; `Parallel-group` is a hint. The route rows (6 to 10) are the four-wide stretch.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Each route gets its own console file, gate drivers and test expectations | - | A | PENDING | - | - | - |
| 2 | The ranked list draws a range and a floor, the date series carries the settings line, and every type carries its readout | 1 | B | PENDING | - | - | - |
| 3 | Every panel's question is declared before it is drawn | 2; plan 51 row 7 | C | PENDING | - | - | - |
| 4 | The query door, measured at the console's real volume | 3 | D (alone) | PENDING | - | - | - |
| 5 | The band reads the ledgers and carries the settings changes, and the four projections nothing draws go | plan 50 row 9 | C | PENDING | - | - | - |
| 6 | Pipelines asks the ledger | 1, 2, 3, 4, 5; plan 51 row 3; plan 51 row 8 | E | PENDING | - | - | - |
| 7 | Summaries asks the ledger | 1, 2, 3, 4, 5, 6; plan 51 row 3; plan 51 row 8 | F | PENDING | - | - | - |
| 8 | Hardware asks the ledger, and its page carries no data | 1, 2, 3, 4, 5; plan 51 row 8 | E | PENDING | - | - | - |
| 9 | Voices asks the ledger, and the ranking panels join it | 1, 2, 3, 4, 5; plan 51 row 3; plan 51 row 8 | E | PENDING | - | - | - |
| 10 | Judgement carries its ids and gates, and its readers are named for the judge | 1, 2 | E | PENDING | - | - | - |
| 11 | The `telemetry` and `run-timeline` projections go | 5, 6 | G | PENDING | - | - | - |
| 12 | The `span-rollup` ledger is deleted, and one item's trace is a command | 6, 11 | H (alone) | PENDING | - | - | - |
| 13 | ECharts leaves | 6, 7, 8, 9, 10, 11 | I | PENDING | - | - | - |

**The rows outside this plan that the `Depends-on` cells name**, written as `plan N row M` so `backend/utilities/plan_status.py` resolves them; a row is cited by its title everywhere else:

| Cell | Row title | State on 2026-09-28 |
| --- | --- | --- |
| plan 50 row 9 | The three ledgers the console's routes read become parquet | PENDING |
| plan 51 row 3 | The three ledgers the console reads are published | PENDING |
| plan 51 row 7 | The query door module and its two entry points | IN-FLIGHT, draft #1154 |
| plan 51 row 8 | One panel end to end: the browser fetches the ledger and draws it in d3 | PENDING |

**Why the route rows can run side by side.** After rows 1 to 3, each route's page, server load, panel directory, console file, gate drivers, test expectations, own specs and own doc page belong to that route alone, and every file that serves two routes is on the cross-route list in section 2.2 with the one row that edits it. **A shared module a route row stops importing is left in place** and deleted by row 13, so no two route rows delete the same file. **A `console.*` knob a route row stops reading is left in place** and deleted by row 13.

**Why row 7 waits for row 6.** Row 6 builds the failed-rule list that Summaries' `refusing-rule` reuses, and draws `extraction_suspect` on Pipelines' `extraction`; row 7 then owns `frontend/src/lib/console/eval-instruments.ts`'s panel map for all eight unwired instruments. Row 11 also waits for row 6, so this costs time only if row 7 runs longer than row 11 (Fowler, 2026-09-28).

**Why rows 4 and 12 run alone.** Row 4's results are timings, and load from a sibling row moves them: the whole pool pauses, no other worktree builds, runs a browser or holds the gate lock (Carmack, 2026-09-28). Row 12 is the one-way deletion (plan 50's rule: a revert of a neighbour must not take a deletion with it).

**Merge windows.** Rows 5, 11 and 12 edit `.github/workflows/digest.yml`, so each merges only while no digest run is queued or running.

**What a worker runs locally.** The list the shared selector gives for the row's own changes (`npm --prefix frontend run test:changed -- --list`). After row 1 that is the route's own tests and pictures for a route row. **A row that edits a file two routes render runs every spec whose page renders it** - on plan 51 a shared readout change passed its route's specs locally and failed 17 in CI. CI runs the full suite.

**Every new test module a row adds carries a module-level `pytestmark`**, so `backend/tests/test_marks.py` is in no row's list. **The plan-doc itself is excluded from the disjointness diff**; every row stamps its own Reckoner line.

## 2. The contracts

Every name below is declared once, here. A row cites the section; it does not restate it.

### 2.1 What "moved" means for one panel

A panel is moved when all of these hold. A route row is done when every panel on its route is moved, or is on the build-time list (section 2.8) and holds properties 1 and 3 to 8.

| # | Property | Checked by |
| --- | --- | --- |
| 1 | It carries `data-console-panel-id` with its id from section 2.7, and its route's console file lists it in page order | `frontend/tests/panel-captures.spec.ts` |
| 2 | Its data comes from queries declared in `frontend/src/lib/console/queries/` (section 2.3), asked through `sliceOnce` at view time | gate 10 in `frontend/tests/chart-vocabulary.spec.ts`, widened by row 3 |
| 3 | **It keeps its component, or draws with a vocabulary type.** A KEEP panel keeps its component unless that component imports `frontend/src/lib/charts/Chart.svelte` or draws a chart rendered by `frontend/src/lib/server/chart-render.ts`; such a panel is drawn on the type section 2.7 names (Susan's KEEP rule, 2026-09-28). A kept component may import `frontend/src/lib/charts/machine.ts`, `glance.ts` or `cost.ts` for their other helpers, because row 13 strips the engine code out of those three rather than deleting them. After row 13 nothing on the console imports `echarts` | the single-engine walk in `chart-vocabulary.spec.ts`; row 13's uninstall |
| 4 | It carries exactly one `data-lede`, exactly one `data-comparison`, a `data-model-rule` declaration and `data-panel-question` (plan 51 section 2.8; [console.md](../docs/architecture/publishing/console.md)) | `frontend/tests/panel-sufficiency.spec.ts` |
| 5 | It draws the loading rules of section 2.4 and every state of `frontend/src/lib/console/waiting.ts`, and its route's driver module puts it into each | gate 8 in `panel-sufficiency.spec.ts` |
| 6 | Its readout declares `data-readout-columns`, `data-readout-records` or `data-readout-none` (plan 51 section 2.7) | `frontend/tests/console-readout.spec.ts` |
| 7 | Its id is in its route's `judged` list | `panel-sufficiency.spec.ts` |
| 8 | A test drives its pure module from a recorded `slice()` result under `tests/fixtures/console/<route>/`, or from its build-time input, and touches no network | the row's own spec |

### 2.2 Each route's console file, gate drivers and test expectations (row 1)

**`config/console/<route>.json`**, one file for each of `pipelines`, `model`, `machine`, `voices` and `judgement` - the closed set `RouteId` in `frontend/src/lib/console/band.ts` names.

```json
{
  "panel_groups": [
    { "id": "what-the-machine-was-doing", "title": "What the machine was doing", "panels": ["two-clocks", "processor-lost"] }
  ],
  "judged": ["platform-mix"],
  "knobs": {}
}
```

| Key | Meaning | Refused at load, by name |
| --- | --- | --- |
| `panel_groups` | The route's panels in drawn order, grouped as the jump links group them. A route with one untitled group writes `"title": ""` | a route that titles some groups and not others; a panel named twice on one route; a panel named on two routes; a route key outside `RouteId` |
| `judged` | The route's panels the sufficiency gates judge | an id not in this route's `panel_groups` |
| `knobs` | Values only this route's panels read, each minted in the row that first reads it (section 2.9) | a key a reader asks for that is absent. No default lives in code |

**One loader.** `routeConsoles()` in `frontend/src/lib/server/config.ts` reads all five files once and applies every refusal above; `panelGroupsFor(route, drawn)` and `frontend/tests/support/console-panels.ts` both use it. `console.panel_groups` and `console.judged_panel_ids` leave `config/appearance.json` and `ConsoleConfig` in `backend/idhazh/contracts/knobs/console.py`, with their four validators. **No alias and no Pydantic model is owed**: a configuration file this project authors declares what its own readers compute on and refuses a missing key by name (owner ruling 2026-09-21). CLAUDE.md section 1a still says every config file is a Pydantic model; row 1 hands the owner a one-line amendment and does not make it (section 0).

**Gate drivers.** `DRIVERS` leaves `frontend/tests/panel-sufficiency.spec.ts` for `frontend/tests/support/panel-drivers/<route>.ts`, one module a route, each exporting `DRIVERS: Record<string, Driver>`; the spec imports all five and refuses an id two modules drive. **The sufficiency spec judges per route, width and theme from one page load** (30 loads, not about 300), and drives gate 8 per route, because a route's panels share addresses (Carmack, 2026-09-28: at about 50 judged panels the per-panel loop times out under the 180 s test timeout).

**The capture route list is the set of console files present**, and a route's address is its `href` in `BAND_UNREAD.routes` in `band.ts`. `CONSOLE_ROUTE_PATHS` and `DRAWS_NO_PANEL_ID` are deleted.

**Test expectations per route.** Every spec that names two or more console routes moves its per-route expectations into `frontend/tests/support/console-expect/<route>.ts`, typed out as literals - never read back from the config they guard, because a spec that reads its own source proves only that the page agrees with itself. The spec imports all five. Seventeen specs name two or more routes: `console-axis`, `console-band`, `console-chart-lifetime`, `console-chart-pending`, `console-chrome`, `console-frame`, `console-mark-parity`, `console-model-panels`, `console-model-rule`, `console-nav`, `console-polarity`, `console-readout`, `console-shell`, `console-title`, `console-voices`, `console-window` and `console` (each `frontend/tests/<name>.spec.ts`). A spec with no per-route expectation is left as it is. **Row 1 also makes `console-chart-pending` and `console-chart-lifetime` skip a route that draws no `Chart.svelte`**, so rows 6 and 8 do not turn them red by moving the last one.

**The cross-route rule, and its check.** A file names a route when it contains that route's address from `BAND_UNREAD.routes`. After row 1, a route row edits no file that names another route, except its own `console-expect`, driver and console file. `frontend/tests/console-route-scope.spec.ts` (new, logic group) fails when a spec or a `panel-drivers/*.ts` names a second route's address, unless the spec is on the list below. **The cross-route list, each file with the one row that edits it:**

| File | Edited by |
| --- | --- |
| the seventeen specs above | row 1, then row 13 |
| `frontend/tests/console-nav.spec.ts` `NAMED_ABSENCES` | row 10 |
| `frontend/src/lib/console/band.ts`, `backend/idhazh/telemetry/publish/console_band.py`, `backend/idhazh/contracts/console_band.py`, `tests/fixtures/contracts/console-band/newest-day.json` | row 5, then row 11 |
| `frontend/src/lib/console/waiting.ts`, `frontend/src/lib/console/recording.ts`, `frontend/src/lib/components/RouteStatus.svelte` | row 3 |
| `frontend/src/lib/components/FailureList.svelte` | row 2, then row 6 |
| `frontend/src/lib/console/eval-instruments.ts`, `frontend/tests/console-model-instruments.spec.ts` | row 7 |
| `docs/architecture/publishing/console.md` | rows 1, 10, 13, in that order |
| every other doc that names two or more routes (`ui-shell.md`, `console-charts.md`, the window page, `what-the-quality-and-source-panels-draw.md` and their siblings) | row 13 |

**Selector.** `config/console/` joins `CONSOLE_OWNED` and `PANELS_DRAWN` in `frontend/scripts/test-scope.ts`, with cases in `frontend/scripts/tests/test-scope.test.mjs`; without it the selector reads a console file as unknown and selects everything (Carmack).

**Route verdict panels.** Row 1 marks the one `is it working` panel on the three routes that have none - `model-cards`, `source-health`, `merged-stories` - with `data-panel-verdict="route"` and updates console.md's question table. Markup only; no pixel moves (Jony, 2026-09-28).

### 2.3 A panel's query (row 3)

**`frontend/src/lib/console/queries/`**: one module for each of `pipelines`, `model`, `machine` and `voices`; `shared.ts` for a query two routes draw; `window.ts` for the range and the memo.

```ts
import type { LedgerName, Predicate, SliceResult } from '$lib/data/ledger';

/** What one panel asks one ledger. Declared here and nowhere else, so the columns
 *  a panel reads are one list the column registry names. `columns` is written as a
 *  literal array of string literals, so a backend test can read it. */
export interface PanelQuery {
	readonly name: string;
	readonly ledger: LedgerName;
	readonly columns: readonly string[];
	readonly where?: readonly Predicate[];
}

/** window.ts - the closed UTC range a preset asks for. */
export function windowRange(presetDays: number, reach: { first: DateStamp; through: DateStamp }): { from: DateStamp; to: DateStamp };

/** window.ts - one slice per query name for the current range. A new range replaces
 *  the held promise; nothing else is kept. */
export function sliceOnce(query: PanelQuery, range: { from: DateStamp; to: DateStamp }): Promise<SliceResult>;
```

- **Names.** A query is exported as `<panelIdInCamelCase>Query`, and its `name` is that identifier. A panel with two queries names both.
- **The window is anchored on the data, not the clock** (Carmack and Fowler, 2026-09-28). `to` is the oldest `through` among the ledgers the route's panels read; `from` is the later of `to - (presetDays - 1)` and that ledger's `first`. **One query a preset**: a narrower preset is a new ask, and the door's own cache serves its files. The reach comes from `ledgerReach(ledger)` in `frontend/src/lib/data/ledger.ts`, which plan 51's owner is asked to add (found-while-planning item 3): `Promise<{state: 'ok'; first: DateStamp; through: DateStamp} | {state: 'quiet'} | {state: 'missing'} | {state: 'unreachable'; at: DateStamp}>`, reading both indexes and starting no engine, one answer a ledger for the page's life. **If plan 51 declines**, `window.ts` holds `ledgerThrough(ledger, today)`, which calls `slice(ledger, {columns: ['date'], from: today, to: today})` and takes `through` from its `quiet` answer, and `from` is `to - (presetDays - 1)` unclamped - the owner is then told that a 90-day window reads `unreachable` until about 31 October (1 December on Hardware), an estimate assuming two days of compaction lag.
- **A panel that does not follow the window** asks for `from = to = through` (the newest day) or filters that day's rows to the newest run, and names the day or run it drew. Section 2.7's `Window` column says which.
- **Two ledgers meet by day or by `url_key`, never on `item_id` or `run_id`** (Andre, 2026-09-28). A daily figure totals each ledger by its own `date` and matches the totals on the date. A row that needs something from the other ledger looks it up by `url_key`, which is the same across runs and days; `item_id` holds only within one day, and a score row carries the run that first scored its text. A row with no match is counted and printed, never dropped. `item-health` meets `host-fingerprint` on `(date, run_id, job, shard)`, the whole of `HOST_FINGERPRINT_KEY`.
- **Withheld cells.** A query never names `canonical_url` or `detail` from `item-health`, or `source_url` or `title` from `scores`: each is text from a stranger or a page address. `url_key` is named only to join and is never drawn. The list is declared once, as `WITHHELD_FROM_PANELS` beside `COLUMN_READERS` in `backend/idhazh/contracts/item_health.py` and `backend/idhazh/contracts/eval_row.py`; `FORBIDDEN_COLUMNS` in `backend/idhazh/contracts/public_telemetry.py` imports it, so row 11 can delete that module (Fowler and Andre, 2026-09-28).
- **The column registry follows the declarations.** Every column a declared query names is listed in `COLUMN_READERS` under the module that declares it - `shared`, then `pipelines`, `model`, `machine`, `voices` when two declare it - and leaves `UNREAD_CELLS`. The same for `host-fingerprint`. The comment above `COLUMN_READERS` gains: a declared panel query counts as a reader. After row 3 no route row edits a registry.
- **Two checks.** `backend/tests/contracts/test_panel_queries.py` reads each `columns: [...]` literal under `frontend/src/lib/console/queries/` and fails on a ledger not in `LedgerConfig.published`, a column the ledger's Pydantic row lacks, a column in `UNREAD_CELLS`, or a withheld column; it imports the withheld list and never retypes it. `frontend/tests/console-drawn-cells.spec.ts` (logic group) reads every `.ts` and `.svelte` under `frontend/src/lib/console/` and `frontend/src/lib/charts/d3/` and fails on `{@html `, `innerHTML =`, `outerHTML =`, `insertAdjacentHTML(`, `document.write(`; an `href`, `src`, `srcset`, `action`, `formaction` or `xlink:href` whose value holds a `{...}` other than a leading `{base}`; `fetch(`, `import(`, `new URL(`, `location.`, `window.open(`, `sendBeacon(`, `console.<name>(`; and `url_key` in any `.svelte` file or `charts/d3/` file. Measured 2026-09-28: none matches today (Andre).
- **The canary carries every declared column**, with at least one row per state a panel distinguishes: a `length` finish, a `429`, a `network_error`, a watchlist hit, an inferred `time_source`, a negative `stage_gap_ms`. So no route row edits `backend/utilities/build_canary_day.py`.

### 2.4 How a panel loads and draws

| # | Step | Rule |
| --- | --- | --- |
| 1 | First frame | The panel draws its reserved box: `Reserved.svelte` at `console.chart_height` for a chart, its row cap times its row pitch for a list, its label with an empty value for a card. **Never a dash, a zero or a sentence while waiting**, because each is an answer. The box stays still until `console.shimmer_after_ms`, then shimmers on the route's one `data-shimmer` switch. No spinner and no timer per panel. A list that settles shorter than its cap shrinks once (Jony, 2026-09-28) |
| 2 | Order | Panels query as they mount, in page order, so the verdict is asked first. No panel waits to be scrolled into view, and no panel moves up because its data arrives sooner |
| 3 | Range | Section 2.3's window rule |
| 4 | States said once | A state every panel on the route shares - loading, `unreachable`, `missing`, `quiet` - is said once, in the route's standing line (`RouteStatus.svelte`, row 3) with one retry, as Pipelines does today. When the shimmer starts the line adds `Fetching the record. After each site update the first visit also downloads the N MB program that reads it.`, N from the build's `__QUERY_ENGINE_BYTES__` define. With scripts off the line says, through a `<noscript>` rule: `The empty panels here are drawn in your browser from the published record, so they need JavaScript.` A panel speaks only when its state differs from the route's; `too-few` is always its own |
| 5 | Nothing happened | A window with rows in which nothing fired is **loaded**, never `quiet`: it draws and says so, in the sentence section 2.7 gives the panel. `quiet` means only a window with no rows (Susan, 2026-09-28) |
| 6 | Draw | Rows go to a pure function in the panel's own `frontend/src/lib/console/<route>/<panel-id>.ts` returning the type's input; the type returns geometry; the component draws. No aggregation in a `.svelte` file |
| 7 | Settings line | A date series passes `rule: {changes}` from section 2.6, or `{declined: <reason>}` with the reason in its `Rule` cell. The route says once, beside the completeness sentence, what the line can see (section 2.6) |
| 8 | Freshness | The route's completeness sentence (plan 51 row 2) says how far the data reaches. **A panel that mixes build-time data with the door says where the door's rows stop** |
| 9 | Cells | Section 2.3's withheld-cells rule. A drawn cell is text, escaped by Svelte, never logged |

**Colour.** A quantity drawn on more than one panel keeps one token on all of them, from `frontend/src/lib/console/series-tokens.ts` (row 2). The stages keep the tokens `STAGE_TOKENS` in `glance.ts` gives them today, queue wait takes `--chart-4`, reading and writing keep what `cost.ts` gives them, and `fetch-time`'s parts take `--chart-5` to `--chart-8` so a part is never read as a stage. No panel picks a token by hand (Susan, 2026-09-28).

**The lede.** One `data-lede` per panel: the finding sentence above the plot at `--text-lg` for `watchlist`, `why-chosen`, `feeds-failed`, `closest-to-memory` and `article-age`; the items-per-minute figure for `run-timeline`; the top row for every other ranked-list panel; the plot itself for every date series and distribution (Susan, 2026-09-28).

### 2.5 The chart types, made ready for a route (row 2)

**No new type** (Susan, 2026-09-28). The vocabulary page already defines a range mark as a row of a ranked list, and a second target bar would draw one mark two ways.

| # | Type | Change | Drawn by |
| --- | --- | --- | --- |
| 1 | `rankedList` | `(rows: readonly {label: string; value: number; context?: string; status?: string; segments?: readonly {label: string; value: number; token: string}[]; range?: {high: number; count: number}; ends?: {end: number}}[], opts: {max?: number; order?: 'largest-first' \| 'smallest-first'; minCount?: number; rules?: readonly {at: number; label: string}[]; tail?: string}) => RankedGeometry \| null`. A row carries at most one of `segments`, `range` and `ends`, refused by name. The divisor is the largest `value`, `high`, `end` or rule, so nothing is clipped. `minCount` is required once a row carries `range`; a row under it draws no mark, prints `Too few: 12 of the 20 articles a row needs.`, and ranks after every drawn row. `status` is the word pill (`disagrees`, `on the floor`). A rule is a dashed upright carrying its name, drawn as `Distribution.svelte` draws one | `RankedList.svelte`, taking `RankedGeometry`. The range mark (fill to `value`, notch at `high`) and the two-named-ends mark (fill to `value`, notch at `end`) move here from the markup `ShardBoard.svelte` and `MemoryBoard.svelte` use; `rangeMark` geometry moves here from `frontend/src/lib/charts/machine.ts`, not copied. Its importers - `BandDistance.svelte`, `FailureList.svelte`, `routes/console/model/+page.svelte` - move to the geometry prop in this row |
| 2 | `dateSeries` | `opts.rule: {changes: readonly {date: DateStamp; words: string}[]} \| {declined: string}`, required. `opts.domain?: [number, number]`. Each point may carry `spread?: {low: number; high: number}` | `DateSeries.svelte` writes `data-model-rule` from `rule`, so the attribute and the drawing cannot disagree: `yes` for `changes`; `no`, with `data-model-rule-none`, for `declined`, refused under five words. A change is a 1 px dashed vertical in `--color-text-tertiary` carrying `data-model-rule-line`, on the boundary between its day's column and the one before; its words reach the strip through `ReadoutInput.events` at that column, never on the plot. An empty `changes` prints `data-model-rule-empty` with the sentence section 2.6 gives. A spread is drawn behind its line in the series' colour mixed with the page surface at `--chart-spread-mix`, one value both themes declare |
| 3 | `distribution` | `opts.scale: 'linear' \| 'log'`, required. `opts.domain?: [number, number]`. `TimeHistogram.svelte`, which kept panels on two routes draw, gains the same optional `domain` | `Distribution.svelte`. A panel with two charts or small multiples passes one domain to each, so two halves are drawn on one scale. A window that spans a setting change says in its note: `This window spans a setting change on 12 Sep; both sides are drawn together.` |
| 4 | `tileStrip` | A tile is never narrower than `console.tile_min_px` (`6`, an estimate). Where a window holds more days than fit, the strip draws the newest days that fit and one line under it counts the rest: `63 earlier days: 2 fired, 58 quiet, 3 not recorded.` The strip prints its first and last day under it in `dayTicks`' words, once under the last strip when strips share an axis | `TileStrip.svelte` |
| 5 | `partsOfOne` | Each part takes its token from `series-tokens.ts` by name, never by position | `PartsOfOne.svelte` |
| 6 | every type | Declares its readout per plan 51 section 2.7 - `readoutOf` for `dateSeries`, `distribution` and `tileStrip`, `factsOf` for the rest - and its `data-readout-*` attribute. `TileStrip.svelte` and `PartsOfOne.svelte` lose `title=`; `DateSeries`, `Distribution`, `Flow` and `PairedScatter` lose their SVG `<title>` (plan 51 row 5 decision 21) | each component |
| 7 | the target bar | `frontend/src/lib/components/TargetBar.svelte` is already markup and stays. `targetBar()` and the `echarts` type import leave `frontend/src/lib/charts/targetbar.ts`; `vocabulary.spec.ts` and `console-ranked.spec.ts` move onto `targetGeometry`, which returns the same band | - |

### 2.6 The settings line and the checker line (row 5)

**The band carries both, read from the run manifests and from `state/scores`, over `max(console.window_presets)` days** (Andre's option B1, 2026-09-28). `item-health` cannot see the prompt, the chat template, the reply shape, the runtime build or the weights' hash; measured 2026-09-28, a rule read from it missed the prompt changes of 14 to 18 and 24 September and drew five false lines. The band already reads the manifests and is fetched by every route.

**Fields on `ConsoleBand`** (`backend/idhazh/contracts/console_band.py`), both additive and both nullable - null means the band did not compute it, and the panel draws the declined rule:

```python
class SettingsMove(Model):
    date: DateStamp                      # the UTC day the inputs moved
    inputs: list[str]                    # >= 1, no repeats; each a PipelineInputs field, or sampling.<key> / runtime_flags.<key>, spelled as comparableInputs() spells it

class BandSettingsMoved(Model):
    recorded_from: DateStamp | None      # the first UTC day in the span whose runs record inputs, or None
    changes: list[SettingsMove]          # dates ascend, never repeat, none before recorded_from

class CheckerMove(Model):
    date: DateStamp                      # the UTC day a new scorer_version first appears in state/scores
    score_moved: bool                    # True when the part that computes the faithfulness number changed

settings_moved: BandSettingsMoved | None = None
checker_moved: list[CheckerMove] | None = None
```

- **The settings rule.** For each UTC day D in the span, take every run on D whose record holds inputs. Turn each run's inputs into one name per setting (each keyed block gives one name per key, after `PipelineInputs`' reader converts old spellings) and drop blank values. D's values for a name are all the values it held across those runs. **A name moved on D when D holds a value missing from the newest earlier day in the span on which that name held any value. A name with no earlier value has not moved.** The span is read from the newest recorded day before its first day onward, so its first day can show a change. The accepted cost: a switch reverted the next day draws no second line (Andre, 2026-09-28).
- **The checker rule.** `scorer_version` compared day to day in `state/scores`; `score_moved` compares the string with its `metrics-`, `bands=` and `lead=` parts removed, which leaves what computes the faithfulness number. `faithfulness` draws only `score_moved` dates; `doubt-reasons` and the `not sure` card draw every date. Measured 2026-09-28: five checker changes (23, 24, 26 and 29 August, 24 September); the manifests hold one.
- **One port, one answer.** `settingsMoved()` is ported to Python using `RENAMED_FLAGS` and `SPLIT_FLAGS` from `backend/idhazh/contracts/fingerprint.py`; `frontend/src/lib/console/settings-moved.ts` takes the same rule and gains `settingsRules(band)`, wording each change through `SETTING_WORDS`. One test runs both over `tests/fixtures/settings-moved/five-on-one-day.json`, which gains a day whose two runs differ.
- **Store names, never values** (Carmack). Measured on the 15 recorded days: 8 change days, 1 to 21 names each; 90 days is an estimated 8 KB raw, 2.4 KB compressed.
- **The band's ceiling.** `page_weight.payload_ceilings_bytes."console/band.json"` is 2,000 bytes over the wire today; the new fields cross it. Row 5 sets it from the built band at twice its compressed size, in the same commit, as plan 51 row 3 set the ledger ceilings. The band is inlined into every prerendered console document, so each grows by the same amount.
- **Version, changelog, read side** (Fowler). `version` is the UTC day the row merges, or `YYYY-MM-DDTHH:MM` if the band already changed that day. The new entry goes on top; keep the 2026-09-23, 09-19 and 09-12 entries; the 2026-09-09 entry becomes `Earlier changes are in this file's git history.`; each `change` is at most 83 characters. The change only adds fields, so no migration; a test shows the fixture without either key validates to `None`, as `test_console_payloads_producer.py` does for `covers_through`. `newest-day.json` is regenerated. `readBand` in `band.ts` maps both fields and reads an absent or malformed value as `null`; `BAND_UNREAD` carries `null`. A new field-set test binds `band.ts`'s fields to `ConsoleBand`, in the style of `test_served_day.py`.

**The sentences** (Andre, 2026-09-28; the window's length is printed where `30` stands):

| Case | Sentence |
| --- | --- |
| Nothing moved in the window | `Nothing changed about how the summaries are written inside these 30 days.` On a chart that also draws the checker line: `Nothing changed about how the summaries are written or checked inside these 30 days.` |
| The window starts before `recorded_from` | `How the summaries are written was first recorded on 13 Sep, so a change before that day draws no line.` If nothing moved after it, add `Nothing about it changed from 13 Sep on.` |
| `recorded_from` is null | `How the summaries are written was not recorded on these days, so this chart cannot mark a change.` |
| A checker line's title | `The checker changed on 26 Aug. Everything left of this line was checked by the one before it.` Its readout row: `How summaries are checked: the checker changed on this day`. A date where both moved prints both rows |
| Once per route, beside the completeness sentence | `A dashed line marks a day a recorded setting changed: the model, its settings, the prompt, the chat template, the runtime or the weights file.` |

**The line replaces each kept chart's own model-change mark**: the step on `ThroughputTrend.svelte` and the line on `KpiCard` (Susan). **The reader loses** nine unnamed lines the old settings digest draws between 23 August and 10 September; four are in today's 30-day view, and all leave the 90-day view by 9 December.

### 2.7 The panels, route by route

Susan's verdict numbers (2026-09-26) are kept. **KEEP means the question and the drawing stay** (section 2.1 property 3). `Window`: `follows` the route's window, or `newest run`, `newest day` or `the change`. `Rule`: the settings line's declaration, and for `no` its reason. A `Type` of `as it is` keeps the component named. "Build-time" means section 2.8. Columns written as "the columns X reads" are exactly those, listed into the query by row 3 from that function.

#### Pipelines (`/console/`), row 6 - one untitled group, in this order

| Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- |
| 1 KEEP | `at-a-glance` | At a glance | build-time: `publishedCharts`, `dayMetrics` | the two cards as they are | no - counts of what published | follows |
| 1 KEEP | `run-health` | Run health | build-time: `loadManifests`, `dayMetrics` | `RunYield` and `RunSquares` as they are | no - planned against published | follows |
| 1 KEEP | `site-cost-per-item` | What one more article costs | build-time: `publishedItems`, `loadManifests` | `dateSeries`, bars | yes - a `run_visual_decision` change moves the bytes an article costs | follows |
| 2 REDRAW | `failure-mix` | What is failing, by stage | `item-health`: `date`, `stage`, `outcome`, `code`, `failed_rule`; the list is `failedRuleQuery` in `queries/shared.ts` | `dateSeries` stacked by stage, `data-comparison="composition"` with its rationale line; the stages are a radio group above a `FailureList.svelte` of `failed_rule`, the stage that failed most chosen at rest, capped at `console.failure_list_max`. A bar segment is not the control, because a keyboard cannot reach it | yes | follows |
| 1 KEEP | `item-time-split` | Where an item's time went | `item-health`: the columns `timeSplitColumns` in `frontend/src/lib/charts/glance.ts` reads | `dateSeries` stacked | yes | follows |
| 3 REPLACE | `slower-on-same-work` (was `throughput-viewport`) | Whether a run is getting slower on the same work | `item-health`: `date`, `cpu_model`, `label_prefill_ms`, `label_input_tokens`, `label_cached_tokens`, `decode_ms`, `output_tokens` | `dateSeries`, one point a day: the seconds a typical article costs on the window's most common `cpu_model`, named under the axis. Reading rate = `label_prefill_ms / (label_input_tokens - label_cached_tokens)`; writing rate = `decode_ms / output_tokens`; a row counts only when all five cells are filled and both divisors are above zero. The typical article is the window's median tokens read and written, priced at that day's median rates. Time per token hardly moves with article length; seconds per article move 2.8 times from the shortest quarter to the longest (Carmack, 2026-09-28) | yes | follows |
| 1 KEEP | `stage-timings` | Time per item by stage | `item-health`: `date`, `fetch_ms`, `extract_ms`, `summarize_ms` | `StageTimings.svelte` as it is, the settings line from section 2.6 | yes | follows |
| 1 KEEP | `item-cost` | What one item cost the model | `item-health`: the columns `frontend/src/lib/console/item-cost.ts` reads | two `TimeHistogram.svelte` charts as they are, reading then writing, on one domain (Jony: one panel, not two) | no - one distribution of the window | follows |
| 4 DELETE | `prompt-memory` | - | - | - | **The reader loses**, on the route they land on, the share of each prompt already in memory printed beside the reading cost it explains, and the count of items read whole. Hardware's `prompt-reuse` answers it one tab away, linked from `item-cost`'s note. Its note - the share follows article length - moves into the design rationale of the Hardware drawing page | - |
| 1 KEEP | `run-timeline` | Where the run's time went, on the run's own clock | `item-health`: `run_id`, `item_id`, `source_id`, `shard`, `item_index`, `item_started_at`, `item_ended_at`, `queue_wait_ms`, `fetch_ms`, `robots_ms`, `extract_ms`, `label_ms`, `summary_ms`, `visual_plan_ms`, `faithfulness_ms`, `stage_gap_ms`, `item_total_ms`. `start_offset_ms` and `residual_ms` are computed in the panel's module as `backend/idhazh/telemetry/publish/run_timeline.py` computes them today. **The span sub-steps go** (`tag`, `render_prompt`, `parse_reply`); `robots_ms` from the row replaces the span's `robots` | `RunTimelinePanel.svelte` as it is. The items-per-minute figure returns above it as its lede. The overrun ("time counted twice") gets a mark unlike the no-reading hatch | no - one run on its own clock | newest run |
| 1 KEEP | `chart-drawing` | Visuals drawn for articles | build-time: `dayMetrics`, `chartFlow` | `flow` (`Flow.svelte`) and its day table | no - counts of what was drawn | follows |
| 5 REDRAW | `extraction` | What the extractor found | `item-health`: `date`, `element_class`, `span_integrity`, `source_form`, `elements_found`; and `scores`: `date`, `url_key`, `extraction_suspect` for the instrument in section 2.7a | figure cards; `rankedList` of element classes with `span_integrity` as a second segment; the yield trend a `dateSeries`. Carries `data-eval-panel="extraction"` | yes, on the trend | follows |
| 23 NEW | `article-age` | How old an article was when we published it | `item-health`: `published_at`, `time_source`, `item_started_at`, `outcome` | `distribution`, `scale: 'log'`, hours from publication to our run, a rule at the median. **Stated times only**: an inferred time is the hour we first saw the address, so it reads younger than it is; the lede counts them: `31 of 212 publication times were inferred and are not drawn.` | no - one distribution of the window | follows |

Panels 19 and 20 moved to Voices (Jony, 2026-09-28): they explain the ranker, which is not Pipelines' question. **Panning leaves with panel 3**: `Viewport.svelte`'s pan buttons and its Left, Right, Plus and Minus keys go, and `console.pan_days` stops being read. **The reader loses** an earlier span of the same width and the keys that stepped the window (Jony).

#### Summaries (`/console/model/`), row 7 - one untitled group, in this order

| Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- |
| 12 KEEP | `model-cards` | the twelve cards | build-time: `state/day-metrics/` through `modelWork` and `buildCardTrends` (Andre, 2026-09-28: the three distinct counts cannot be rebuilt from the ledgers - they disagreed with `day-metrics` on 11 of 35 days). A disclosure `The days behind the cards` under the cards holds the daily table and carries `data-eval-panel="daily-figures"`; `daily-figures` is no longer a panel id | `KpiCard` as it is; the twelfth card is `determinism_violation` | yes, the settings line replacing the card's own line; the `not sure` card also draws the checker line | follows |
| 12 KEEP | `model-throughput` | the throughput chart's title | `item-health`: the columns `throughputWithin` in `frontend/src/lib/server/model-work.ts` reads | `ThroughputTrend.svelte` as it is, its step replaced by the settings line | yes | follows |
| 24 NEW | `call-ending` | How a model call ended | `item-health`: `date`, `summary_finish_reason`, `label_finish_reason`, `recovered` | `dateSeries` stacked, `length` at the bottom, then the other reasons by count | yes | follows |
| 25 NEW | `refusing-rule` | Which rule refused a reply | `failedRuleQuery` from `queries/shared.ts`, with the model's stages selected | `FailureList.svelte`, the divisor printed, capped at `console.failure_list_max` - the same query and component as `failure-mix`'s list, so two routes cannot print two counts for one rule (Jony) | no - a ranking of the window | follows |
| 12 KEEP | `doubt-reasons` | Why a summary was doubted | build-time: `reasonDays` over the digest day files | `dateSeries` stacked | yes, and the checker line on every checker date | follows |
| 12 KEEP | `faithfulness` | Summary faithfulness, day by day | `scores`: `date`, `hhem`, `scorer_version` | `dateSeries`, the median as the line and the quartiles as its `spread`. The link `How each of these measures is scored` stays beside the heading; it is not a panel | yes, and the checker line on `score_moved` dates | follows |
| 12 KEEP | `source-doubts` | Which sources the checker doubts | `scores`: the columns `sourceDoubts` reads, with `evidential_density` and `speculative_density`; `item-health`: `url_key`, `source_id`, joined by `url_key` | `RankedList.svelte`; the two densities are figures on each row, never segments | no - a ranking of the window | follows |
| 12 KEEP | `write-cost` | What one summary cost | `item-health`: the columns `writeTimes` reads | `TimeHistogram.svelte` as it is | no - one distribution of the window | follows |
| 12 KEEP | `score-cost` | What checking one summary cost | `scores`: the columns `scoreCost` reads | `TimeHistogram.svelte` as it is | no - one distribution of the window | follows |
| 12 KEEP | `summary-length` | How long summaries came out | `item-health`: the columns `runLengths` reads; `scores`: `date`, `compression` | `RunLengths.svelte` as it is; `compression`'s day median printed on its day's row | yes | follows |
| 12 KEEP | `model-change` | What the model change moved | `item-health` and `scores`: the columns `modelSwap` reads, the scores joined by `url_key` | `SwapDots.svelte` as it is | no - it is the change itself | the change |
| 13 REPLACE | `recorded-only` | - | - | - | **Deleted as a panel.** Its eight instruments go where section 2.7a puts them. **The reader loses** the one place listing unwired instruments, and each instrument's quietest, middle and loudest day side by side; `eval-instruments.ts` keeps the list, and its test fails on an instrument in no panel | - |

#### 2.7a Where the eight unwired instruments go (Andre, 2026-09-28)

Each keeps the `label` and `note` it has in `frontend/src/lib/console/eval-instruments.ts`, and gets no threshold, no tint, no good or bad direction and no worst-value marker. A panel that takes one says once: `Nothing acts on these numbers.`

| Instrument | What it measures | Goes to | Drawn as |
| --- | --- | --- | --- |
| `compression` | summary length over article length | `summary-length` | the day's median percent on that day's row; no mark of its own |
| `self_repetition` | how often the summary repeats its own four-word runs | the `daily-figures` disclosure | a column, the day's median percent, next to `coherence` |
| `coherence` | how well each summary sentence follows the one before | the `daily-figures` disclosure | a column, the day's median to two decimal places; read against `self_repetition`, because a repeated sentence scores as coherent |
| `semantic_coverage` | how many of the article's most-used words the summary kept | the `daily-figures` disclosure | a column, the day's median percent; days before 24 September print as not measured |
| `evidential_density` | how often the article says who reported a claim | `source-doubts` | a figure on each source row, the median per 1,000 article words |
| `speculative_density` | how often the article hedges | `source-doubts` | beside `evidential_density` and the row's dropped-hedge count |
| `extraction_suspect` | the checker thought the extracted text was page furniture | `extraction` on Pipelines | distinct articles out of summaries checked, beside the extractor's own `not_prose` and `contaminated` refusals |
| `determinism_violation` | one input gave two different summaries | the twelfth card and the `daily-figures` disclosure | distinct articles a day, never ledger rows. It earns a card because it says whether a before-and-after comparison on this route compares like with like |

Row 7 owns the map in `eval-instruments.ts` and rewrites `frontend/tests/console-model-instruments.spec.ts` to visit each route `EVAL_PANELS` names; row 6 only puts `data-eval-panel="extraction"` on its panel (Fowler, 2026-09-28).

#### Hardware (`/console/machine/`), row 8 - today's four groups

`platform-mix` is plan 51 row 8's. Every other panel moves; none keeps a build-time read.

| Group | Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What the machine was doing | 6 KEEP | `two-clocks` | Whether the speed numbers can be trusted | `item-health` and `host-fingerprint`: the columns `clockAgreement` reads, joined on `HOST_FINGERPRINT_KEY` | `rankedList`, a row a shard of the newest run: value the gap between the two counts in percent, one rule at `tolerancePct`, the two counts in the readout, `status` `disagrees` past the rule (Susan: `pairedScatter` needs 160 rows and three kinds, which one run never has) | no - two clocks of one job | newest run |
| | 6 KEEP | `processor-lost` | the title it has | `item-health`: the columns `processor-lost.ts` reads | `tileStrip` | no - the host's share | follows |
| | 6 KEEP | `disk-reads` | the title it has | `item-health` and `host-fingerprint`: the columns `disk-reads.ts` reads | `tileStrip` | no - the host took memory | follows |
| | 6 KEEP | `machine-cards` | Which machines this run was given | `host-fingerprint`: the columns `machine-cards.ts` reads | the cards as they are | no - one run's machines | newest run |
| | 7 REDRAW | `slower-machines` (was `reading-against-writing`) | Which machines do the same work slower | `item-health`: `run_id`, `cpu_model`, `label_prefill_ms`, `label_input_tokens`, `label_cached_tokens`, `decode_ms`, `output_tokens` | **two `rankedList`s side by side, `Reading` and `Writing`**, a row a `cpu_model`: value the kind's median seconds for the typical article's reading (writing), each article's rate first divided by the median rate of the window's most common `cpu_model` in the same run, so runtime switches the row does not record cancel; `range` notch at the slowest tenth, printed `slowest tenth`; floor `machine.knobs.slower_machines_min_articles`; capped at `console.fleet_top_kinds`. **Never one total**: one kind reads a token in 37 percent of another's time and writes one in 145 percent of it (Carmack, 2026-09-28) | no - kinds, not days | follows |
| | 6b REDRAW | `platform-mix` | plan 51 row 8 | plan 51 row 8 | plan 51 row 8 | plan 51 row 8 | plan 51 row 8 |
| Where the time went | 8 REDRAW | `slowest-articles` (was `shard-board`) | Which articles took longest in the last run | `item-health`: `run_id`, `item_id`, `source_id`, `shard`, `item_total_ms`, `fetch_ms`, `extract_ms`, `summarize_ms`, `stage_gap_ms`, `queue_wait_ms` | `rankedList`, `machine.knobs.slowest_articles_rows` rows: value `item_total_ms`; segments `fetch_ms`, `extract_ms`, `summarize_ms`, and `other` where `stage_gap_ms` is above zero; context `waited 12 s first` from `queue_wait_ms`, which sits outside `item_total_ms`. A row whose `stage_gap_ms` is below zero draws its bar whole and its readout says `stages overlapped by 1.2 s` | no - one run | newest run |
| | 6 KEEP | `tail-trend` | Whether the slowest articles are getting slower | `item-health`: `date`, `item_total_ms`, and the columns `percentileHistory` reads | its five subplots as they are, the settings line on each | yes | follows |
| How close we are to the limits | 9 REDRAW | `closest-to-memory` (was `memory-board`) | Which articles left the machine least memory | `item-health`: `item_id`, `source_id`, `os_mem_available_min_bytes`, `os_mem_available_bytes`, `llama_rss_bytes`, `source_words` | `rankedList` with `ends`: fill to `os_mem_available_min_bytes`, notch at `os_mem_available_bytes`, `order: 'smallest-first'`, `machine.knobs.closest_to_memory_rows` rows, the article's length as context | no - a ranking | follows |
| | 6 KEEP | `memory-held` | What is holding the machine's memory | `item-health`: the columns `memory-held.ts` reads | its bars as they are | no - one day's split | newest day |
| | 10 REDRAW | `context-headroom` | How much of the reading limit an article takes | `item-health`: `summary_input_tokens`, `label_input_tokens`, `n_ctx_configured`, `truncation_cap_tokens` | two small `distribution`s, label and summary, `scale: 'log'`, each with one rule at the reading limit and one at the truncation cap, each printing its value. The limit rule sits at the smallest `n_ctx_configured` in the window, and the note names any other value | no - one distribution of the window | follows |
| What the model spends | 6 KEEP | `article-cost` | What one article costs the machine | `item-health` and `host-fingerprint`: the columns `article-cost.ts` reads, joined on `HOST_FINGERPRINT_KEY` | its tracks as they are | no - per article | follows |
| | 11 REDRAW | `prompt-reuse` | How much text the model reads again | `item-health`: `date`, `label_cache_pct`, `label_input_tokens`, `summary_cache_pct`, `summary_input_tokens`, and the columns `prompt-reuse.ts` reads for its own figure | `dateSeries`, two lines: the median tokens held per request, label and summary. The server's share and ours are printed beside it as the check. **Not the share as a trend**: the share follows article length, so a longer article shows a smaller share while the same amount is held (Susan) | yes | follows |
| | 6 KEEP | `read-against-written` | What a run reads against what it writes | `item-health`: the columns `readAgainstWritten` reads | `dateSeries` | yes | follows |
| | 6 KEEP | `counterfactual-cost` | What the runner's work would have cost elsewhere | `item-health`: the columns `costOverDays` reads, and the rate from config | `dateSeries`, the running shape | yes - the model, the quantisation and `n_parallel` move what the work costs | follows |

**Route sentences** (Jony, 2026-09-28). The recording sentences, `data-machine-record`, the intro, the refused runs and the newest run come from declared queries through `recording.ts`; the browser refuses exactly the runs the server refuses today. **The lost state** is a day on which `item-health` has published rows and `host-fingerprint` has none. The intro's `read at build time and published nowhere` becomes `read from the published record when you open this page`.

#### Voices (`/console/voices/`), row 9 - two groups

| Group | Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What the sources supplied | 16 KEEP | `source-health` | Sources we may ask, and what they yield | build-time: `sourceHealthView` | the table as it is; its yield column draws `RankedList.svelte`'s bar on one shared scale | no - permissions | follows |
| | 18 REDRAW, with 22 folded in | `feeds-failed` | Feeds and articles that failed | the feed row from the build-time `feedResults`, written for the widest preset; the article row from `item-health`: `date`, `source_id`, `http_status`, `outcome`, `code`, `source_form`, `tier` | `tileStrip`, two rows a source, feed above articles, **one key for both rows**, on one axis ending at the older of the two rows' newest days, named under it: `Feed results after 26 Sep wait for their article fetches.` An article tile fires on a row whose `code` is `http_client_error`, `http_rate_limited`, `http_server_error` or `network_error`, against `voices.knobs.article_fails_marked` and `voices.knobs.article_fails_named`. **A status class never gets its own colour** (Susan; Jony agreed): the readout prints each code in words with its status, `rate limited (429) on 7 of 9 fetches`, then `source_form` and `tier`, and each drawn row ends with its commonest code and its newest failed day, `mostly rate limited, last 26 Sep`. Sources with a fired tile in either row are drawn, most fired days first, up to `console.feed_rows`; one line counts the rest: `31 other sources answered on every day.` The two rows draw together; if the article row cannot be fetched, the feed row draws alone and says so | no - outcomes, not a trend | follows |
| | 21 NEW | `fetch-time` | Where a fetch spent its time | `item-health`: `source_id`, `fetch_ms`, `fetch_connect_ms`, `fetch_ttfb_ms`, `robots_ms`, `retry_total_ms`, `retry_count` | `rankedList` capped at `console.source_rows`, a row a source: value the mean `fetch_ms`; segments the means of `robots_ms`, `retry_total_ms`, `fetch_connect_ms`, `fetch_ttfb_ms`, and `the rest` = `fetch_ms` minus those four; `retry_count` in the readout only. **Means, not medians**: the medians of the parts do not add up to the median of the whole. Rows without `robots_ms` are left out. The four clocks do not overlap (Carmack, 2026-09-28: `fetch_ms` contains them all; over 6,536 rows they never exceeded it by more than 4 ms of rounding) | no - a ranking | follows |
| | 16 KEEP | `retiring` | Sources close to retiring themselves | build-time: `sourceHealthView` | `TargetBar.svelte` rows as they are | no - a rule's distance | follows |
| | 16 KEEP | `source-cuts` | Sources cut short most often | `item-health`: the columns `sourceCuts` reads | `SourceCutRange.svelte` as it is (its axis is log, and a fill from zero has no place on it) | no - a ranking | follows |
| What the ranking did | 17 REDRAW | `ranking-discount` | How far the ranking discounts each feed | build-time: the source-health view's `reliability`, `reliability_reads`, `opportunities`, `reliability_floor` and `run_id` for every live feed (Susan and Jony, 2026-09-28: `item-health` has no row for a feed whose reads failed, which is what the discount measures) | `rankedList`, a row a feed, heaviest first, ties by most reads, capped at `console.source_rows`: value `1 - reliability`; context `14 reads`; `status` `on the floor` where the fill meets the rule; one rule at `1 - reliability_floor`, named `the most the ranking takes`; tail `9 more discounted, 2 on the floor; 180 answered every read; 23 were not read in 14 days and keep full weight.` The note names the view's run. The ranking headline stays the view's `headline_sentence` | no - one run's setting | newest run |
| | 19 NEW | `why-chosen` | Why the newest day's articles were chosen | `item-health`: `date`, `item_id`, `source_id`, `selection_score`, `authority_score`, `tier_score`, `feed_weight`, `feed_reliability`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step` | `partsOfOne`, `voices.knobs.why_chosen_rows` rows ranked by score, five parts in this order: `authority_score`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step` (`tier_score`, `feed_weight` and `feed_reliability` are multiplied into `authority_score` in `backend/idhazh/rank.py`, so they are not parts). The readout prints `authority 0.72 = tier 1.0 x weight 0.8 x reliability 0.9`. Lede: `On 26 Sep, authority made 81 percent of the twenty scores.` Finding: if authority fills nearly every track, the order is the source list's order and the bonuses decide nothing | no - one day's choice | newest day |
| | 20 NEW | `watchlist` | What the watchlist caught | `item-health`: `date`, `watchlist_hit`, `watchlist_bonus`, `on_front_page`, `carried_by` | `tileStrip`, one tile a day, against `voices.knobs.watchlist_hits_marked` and `voices.knobs.watchlist_hits_named`; one line says what a filled day means: `A filled day: the watchlist caught at least one article.` Lede: `The watchlist caught 9 articles on 4 of 30 days; 2 reached the front page.` A quiet window: `The watchlist matched no article in this window.` | no - a count of hits | follows |

**Panel 22 (`source-answer`) is folded into `feeds-failed`** (Susan and Jony): both drew `http_status` a source a day. **The reader loses** the tiles of sources whose feed and articles answered every day; one line counts them.

#### Judgement (`/console/judgement/`), row 10 - one untitled group, in this order

Every panel keeps its build-time read and its component; none imports ECharts.

| Verdict | Id | Component |
| --- | --- | --- |
| 14 KEEP | `merged-stories` | `MergedStoriesPanel.svelte` |
| 14 KEEP | `merge-line` | `MergeLinePlot.svelte` |
| 14 KEEP | `judge-agreement` | `JudgeAgreement.svelte` |
| 14 KEEP | `record-gates` | `RecordGates.svelte` |
| 14 KEEP | `verdict-split` | `VerdictSplit.svelte` |
| 14 KEEP | `holdout-margin` | `HoldoutMargin.svelte` |
| 15 DELETE | - | the `What the model made of each article` heading and its `data-console-empty="judgement"` sentence. **The reader loses** the sentence saying the model's desk and lens choices go unrecorded, and its pointer to Summaries. It returns with whichever plan wires the judge's per-article record |

**Comparison sentences** (Susan, 2026-09-28), one `data-comparison` each: `slower-on-same-work` "the newest day against the window's median"; `why-chosen` "the authority part against the four bonuses"; `article-age` "articles over a day old against newer ones"; `refusing-rule` "the rule that refused most against every other rule"; `call-ending` "calls cut off at the length limit against calls that ended on their own"; `slower-machines` "each machine kind's typical time against the fastest kind's"; `slowest-articles` "each article's longest stage against its other stages"; `closest-to-memory` "the memory each article left free against its length"; `context-headroom` "each prompt against the reading limit"; `prompt-reuse` "tokens held for label prompts against tokens held for summary prompts"; `ranking-discount` "each feed's discount against the most the ranking takes"; `feeds-failed` "each source's feed against its article fetches"; `fetch-time` "the largest part of each fetch against the other parts"; `two-clocks` "each shard's gap against the tolerance"; `item-cost` "writing one summary against reading one prompt" (Jony); `failure-mix` the declared `composition` case. Every other panel writes its own from its standfirst, containing ` against `.

### 2.8 Panels that keep a build-time read

| Route | Panel | Dataset | Why it cannot move here |
| --- | --- | --- | --- |
| Pipelines | `at-a-glance`, `run-health`, `site-cost-per-item`, `chart-drawing` | the digest day files, the run manifests, `state/day-metrics/` | none is a published ledger |
| Summaries | `model-cards` with its `daily-figures` disclosure | `state/day-metrics/` | the distinct counts cannot be rebuilt from the ledgers (section 2.7) |
| Summaries | `doubt-reasons` | the digest day files | the reason is a decision recorded on the published item and in no ledger; rebuilding it means re-implementing the band rule with each day's thresholds, and a `not_scored` item has no score row to rebuild from (Andre) |
| Voices | `source-health`, `retiring`, `ranking-discount`, and the feed row of `feeds-failed` | the source-health view, `state/feed-health/` | not published |
| Judgement | all six | `state/content-similarity-judge/` and the digest day files | not published |

**Each is drawn once** (Susan, 2026-09-28): its pure module takes the chart type's input, and the build-time load is the only code that shapes that input, so the later move replaces the load and nothing the reader sees; the move is done when its pictures show the same marks. **The reader loses** view-time freshness on these panels until the out-of-scope plan publishes their datasets.

### 2.9 Knobs this plan mints

Each lives in its route's `knobs` (section 2.2) unless named otherwise. A value marked estimate is a starting point Susan reads on the 390 dark picture.

| Key | Default | Minted by | Reader |
| --- | --- | --- | --- |
| `console.tile_min_px` in `config/appearance.json` | `6`, estimate | row 2 | `TileStrip.svelte` |
| `--chart-spread-mix` in `frontend/src/styles/tokens.css`, both themes | `0.25`, estimate | row 2 | `DateSeries.svelte` |
| `machine.knobs.slowest_articles_rows` | `20` | row 8 | `slowest-articles` |
| `machine.knobs.closest_to_memory_rows` | `20` | row 8 | `closest-to-memory` |
| `machine.knobs.slower_machines_min_articles` | `20`, estimate | row 8 | `slower-machines` |
| `voices.knobs.article_fails_marked`, `voices.knobs.article_fails_named` | `1`, `3` | row 9 | `feeds-failed` |
| `voices.knobs.why_chosen_rows` | `20` | row 9 | `why-chosen` |
| `voices.knobs.watchlist_hits_marked`, `voices.knobs.watchlist_hits_named` | `1`, `3` | row 9 | `watchlist` |
| `page_weight.payload_ceilings_bytes."console/band.json"` in `config/idhazh.json` | twice the built band's compressed size | row 5 | `frontend/scripts/bundle-gate.mjs` |

### 2.10 The door at the console's real volume (row 4)

**Why it runs before any route moves.** About 35 panels will ask the door for rows, and the door returns rows, not totals. At 1,000 items a day and a 90-day window a trend query builds about 90,000 row objects on the main thread, and a route asks up to fifteen queries. Whether that is fast enough decides the door's return shape, which is cheapest to change while no panel calls it (Carmack, 2026-09-28).

| # | Part | Rule |
| --- | --- | --- |
| 1 | Data | A generated, uncommitted 90-day compact fixture, written by plan 50's own compaction code from real rows given new dates, at 1,000 `item-health`, 925 `scores` and 69 `host-fingerprint` rows a day - the busiest measured day plus a quarter |
| 2 | Scope | The declared queries of all four data routes, at the 30-day preset (the page's default) and at 90 days |
| 3 | Runs | Cold (a fresh browser context) and warm (a reload), five of each, interleaved; the site served with Pages' own headers (`max-age=600` and an `ETag`). "Drawn" means the panel's loaded attribute is set |
| 4 | Recorded | Bytes, requests, serial requests on the longest chain, engine start, each query's engine time and main-thread time, time until every panel is drawn, and the longest main-thread task. Network time is computed as serial requests x 100 ms plus bytes / 10 Mbit/s, and labelled arithmetic |
| 5 | Machine | This developer machine (Intel Core i7-1265U, Windows 11), the whole pool paused, the gate lock held, Chromium at 4x CPU slowdown |
| 6 | Pass line, written before the run | Warm, 90 days: every panel drawn within 3 s, and no main-thread task over 200 ms. Cold, 30 days: at most 4 serial requests, and every panel drawn within 3 s after the engine arrives. Judged on the worst of the five runs; all five reported |
| 7 | Written to | `docs/reference/benchmarks/the-query-door-at-the-consoles-real-volume.md`, linked from the instrument log in `docs/reference/pipeline-cost.md` |
| 8 | A miss | ESCALATE trigger 3. The fixes are plan 51's: the door keeps each index and file for the page's life keyed by path and version (about 50 lines); a column-shaped result; a "newest N days" ask; a structured aggregate. Any CI guard that follows counts rows and never times wall-clock on a shared runner |

### 2.11 Rulings asked of the owner, and the default each row proceeds on

| # | Situation | Options, with what each costs | Default the rows proceed on |
| --- | --- | --- | --- |
| R1 | N8 names `console/band.json` among the artefacts that leave `frontend/`. The band is sentences and counts the pipeline composes about its own run, inlined into every console document | A. Keep it where it is and strike it from N8: one line on the intent page. B. Move it under `state/` and publish it with the ledgers: a publish entry for a file that is not a ledger, and its address moves. C. Compute it in the browser: needs `feed-health` and the run manifests published first, and puts several fetches ahead of the first verdict | **Leave both the band and N8 as they are**; only the owner narrows intent (Fowler). Row 5 changes what the band reads and carries, not where it lives |
| R2 | N4 says the console routes come off prerender. After row 8, Hardware's document can carry no ledger data | A. **A prerendered page with no data**: the band's verdict, the tab strip, the window control, the intro's words and every panel's title, note and reserved box, and no figure, date, window length or mark; every panel fetches at view time. Costs: with scripts off, or when the record cannot be fetched, Hardware shows its frame and no figure, where today it shows every mark. B. **Off prerender** (`prerender = false`, `ssr = false`, served by the `404.html` fallback): `+page.server.ts` must go and config reaches the page through a build-time define beside `__UI_CONFIG__`; the page is blank until the bundle boots; Pages answers with HTTP 404; nothing shows without scripts; the band is one round trip later; the cold chain becomes 5 serial requests against the 4 `console-cold-load.spec.ts` allows; `console-window-claims.spec.ts`, `console-nav.spec.ts` and the scripts-off Machine specs break; it reverses the 2026-09-12 ruling in `docs/architecture/publishing/frontend.md` | **A** (Susan, Carmack and Jony, 2026-09-28). Row 8 builds it. A ruling for B is a new row after row 13 |
| R3 | Plan 51's row 3 publishes every `item-health` column, including `canonical_url` and `detail`, and every `scores` column, including `title` and `source_url`. `public_telemetry.py` refuses the first three as a trust boundary; the 2026-09-26 ruling weighed pending work and download size, not that boundary | A. Publish them: the public site carries the addresses of pages the pipeline refused and the headlines of summaries it dropped. B. Withhold them: a second, narrower copy of each compacted period, which plan 51 refused | **None assumed.** No panel here draws a withheld cell (section 2.3), whatever the ruling. If `url_key` is withheld too, `source-doubts` and `model-change` move to section 2.8. The owner rules before plan 51's row 3 merges (Andre, 2026-09-28) |
| R4 | The settings line needs the run manifests' inputs, which no published ledger holds | B1. The band carries the changes (section 2.6): a `ConsoleBand` change and a higher band ceiling. B2. Nine more columns on `item-health`: a persisted-contract change, blind before the day it lands. B3. Publish the manifests: the out-of-scope plan. B4. Read `item-health`'s settings columns: misses the prompt and draws false lines | **B1**, on this plan's authorization (Andre, 2026-09-28) |

## Rows

### Row #1 - Each route gets its own console file, gate drivers and test expectations

- **Scope:** section 2.2, and nothing that moves a pixel: no id is added to a panel, no frame is added, no data read changes. The five console files are written with today's panel lists (`pipelines` and `machine` as they are; `model`, `voices` and `judgement` with empty `panel_groups` until their route rows); the drivers and per-route expectations move; the seventeen cross-route specs read their per-route expectations from `console-expect`; the capture and sufficiency specs are restructured; the selector learns `config/console/`; the three route verdict panels get `data-panel-verdict="route"`.
- **Files touched:**
  - `config/appearance.json`, `config/console/pipelines.json`, `config/console/model.json`, `config/console/machine.json`, `config/console/voices.json`, `config/console/judgement.json` (new)
  - `backend/idhazh/contracts/knobs/console.py`, `backend/idhazh/contracts/appearance_config.py`, `backend/idhazh/contracts/app_config.py` (changelog lines), `backend/tests/test_appearance_config.py`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `frontend/src/lib/server/config.ts`, `frontend/tests/appearance-config.spec.ts`
  - `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/machine/+page.server.ts` (both read `panelGroupsFor` from the loader)
  - `frontend/src/routes/console/model/+page.svelte`, `frontend/src/routes/console/voices/+page.svelte`, `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte` (`data-panel-verdict="route"`)
  - `frontend/tests/support/console-panels.ts`, `frontend/tests/panel-captures.spec.ts`, `frontend/tests/panel-sufficiency.spec.ts`, `frontend/tests/fixtures/panels/WitnessPanel.svelte`
  - `frontend/tests/support/panel-drivers/pipelines.ts`, `model.ts`, `machine.ts`, `voices.ts`, `judgement.ts` (new); `frontend/tests/support/console-expect/pipelines.ts`, `model.ts`, `machine.ts`, `voices.ts`, `judgement.ts` (new)
  - `frontend/tests/console-axis.spec.ts`, `console-band.spec.ts`, `console-chart-lifetime.spec.ts`, `console-chart-pending.spec.ts`, `console-chrome.spec.ts`, `console-frame.spec.ts`, `console-mark-parity.spec.ts`, `console-model-panels.spec.ts`, `console-model-rule.spec.ts`, `console-nav.spec.ts`, `console-polarity.spec.ts`, `console-readout.spec.ts`, `console-shell.spec.ts`, `console-title.spec.ts`, `console-voices.spec.ts`, `console-window.spec.ts`, `console.spec.ts` (each under `frontend/tests/`), `frontend/tests/console-route-scope.spec.ts` (new)
  - `frontend/scripts/test-scope.ts`, `frontend/scripts/tests/test-scope.test.mjs`, `frontend/scripts/test-groups.ts`
  - `docs/concepts/config/appearance.md`, `docs/architecture/publishing/console.md` (the question table), `docs/reference/test-selection.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/test_appearance_config.py backend/tests/contracts`, `npm --prefix frontend run test:tooling`, `npm --prefix frontend run test:changed -- --list` then the selected checks (every console group: this row touches every route). The row prints the panels tests' worker seconds and the browser job's wall time from its CI run. CI runs the full suite.
- **Oracle:** **nothing a reader sees moved, and each route now owns its own files.** The six pictures of one Hardware panel and one Pipelines section are the same before and after; `console-route-scope.spec.ts` fails when a driver module names a second route's address (bite: add `/console/voices/` to `panel-drivers/machine.ts`, watch it fail, restore); the selector lists only Hardware's groups for an edit to `config/console/machine.json`. It cannot settle whether any panel is good; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A file per route.** It is the refactor that splits the one surface every route row would otherwise edit, so it runs first (execute-a-plan.md) | Fowler, 2026-09-28 |
  | 2 | **Structural only.** Summaries and Voices draw no `Panel` frame and four Pipelines sections have none, so adding ids and frames moves pixels on three routes; each route row adds its own | Fowler, 2026-09-28 |
  | 3 | **Per-route expectations are typed out, not read from config.** `console-nav`, `console-title` and `console-voices` type the routes out on purpose; a spec that reads the source it guards proves only that the page agrees with itself | Fowler, 2026-09-28 |
  | 4 | **The sufficiency spec judges a route, a width and a theme per page load**; gate 8 is driven per route | Carmack, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep one `console.panel_groups` and let the dispatcher treat per-route keys as disjoint | The readiness test compares files, and the judged list is one flat list every row appends to | Five route rows serial, or a hand resolution per merge | Fowler |
  | 2 | Make the cross-route specs read `config/console/` | A spec that reads what it guards cannot catch a wrong entry | The guard | Fowler |

---

### Row #2 - The ranked list draws a range and a floor, the date series carries the settings line, and every type carries its readout

- **Scope:** section 2.5 and the colour contract in section 2.4. **No panel moves**, and no route row edits `frontend/src/lib/charts/d3/` or a component this row changes afterwards. The settings line's *data* is row 5's; this row only makes `dateSeries` take `rule`.
- **Files touched:**
  - `frontend/src/lib/charts/d3/rankedList.ts`, `dateSeries.ts`, `DateSeries.svelte`, `distribution.ts`, `Distribution.svelte`, `tileStrip.ts`, `TileStrip.svelte`, `partsOfOne.ts`, `PartsOfOne.svelte`, `Flow.svelte`, `PairedScatter.svelte`
  - `frontend/src/lib/components/RankedList.svelte`, `BandDistance.svelte`, `FailureList.svelte`, `frontend/src/routes/console/model/+page.svelte` (the geometry prop), `frontend/src/lib/components/ShardBoard.svelte`, `frontend/src/lib/components/MemoryBoard.svelte` (the marks move out), `frontend/src/lib/charts/machine.ts` (`rangeMark` moves out), `frontend/src/lib/components/TimeHistogram.svelte` (`domain`)
  - `frontend/src/lib/charts/targetbar.ts`, `frontend/tests/vocabulary.spec.ts`, `frontend/tests/console-ranked.spec.ts`
  - `frontend/src/lib/console/series-tokens.ts` (new), `frontend/src/lib/charts/glance.ts`, `frontend/src/lib/charts/cost.ts` (their tokens move out), `frontend/src/styles/tokens.css` (`--chart-spread-mix`)
  - `config/appearance.json` (`console.tile_min_px`), `backend/idhazh/contracts/knobs/console.py`, `backend/idhazh/contracts/appearance_config.py`, `frontend/src/lib/server/config.ts`, `backend/tests/test_appearance_config.py`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `frontend/tests/fixtures/panels/WitnessPanel.svelte`, `frontend/tests/panel-sufficiency.spec.ts` (callers of the new `rule`), and `frontend/src/lib/console/machine/PlatformMixPanel.svelte` if plan 51's row 8 has merged
  - `frontend/tests/chart-types.spec.ts` (new), `frontend/scripts/test-groups.ts`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (the widened ranked list, the settings line, the spread, the log scale, the tile width; Susan's ruling beside each; plan 51 section 2.6's sentence that two plan-52 panels need a new type is struck there)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks - **every spec whose page renders a changed component**, which is every console group; `ruff check .`, `pytest backend/tests/test_appearance_config.py`; `python backend/utilities/doc_load.py` before and after. CI runs the full suite.
- **Oracle:** **each change draws what its signature promises, and nothing that drew before draws differently.** Over written-down rows in `chart-types.spec.ts`: a `range` row puts the fill at `value` and the notch at `high`, and below `minCount` draws no mark and ranks last; `rule: {changes}` puts one line per date inside the frame on the boundary before its column and writes `data-model-rule="yes"`, and `{declined}` under five words is refused; a log `distribution` bins by decade; a 90-day `tileStrip` at 390 px draws tiles of at least 6 px and the overflow line. The pictures of `BandDistance`, `FailureList`, `ShardBoard` and `MemoryBoard` panels match before and after. `chart-vocabulary.spec.ts` stays green unchanged.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **No new type.** A range mark is a row of a ranked list, and a second target bar would draw one mark two ways | Susan, 2026-09-28 |
  | 2 | **The rule is one value, `changes` or `declined`, and the component writes the attribute from it**, so the two cannot disagree | Susan, 2026-09-28 |
  | 3 | **Every shared component is made ready here**, so four route rows do not each change it | Fowler and Susan, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | A second target bar under `d3/` | `TargetBar.svelte` is markup drawn from `targetMarks` | Two drawings of one mark | Susan, 2026-09-28 |
  | 2 | Throughput and summary length as a range row a day | A set ordered by time is a trend, and a row list carries no settings line | Both panels lose gate 6, and summary length its short end | Susan, 2026-09-28 |

---

### Row #3 - Every panel's question is declared before it is drawn

- **Scope:** section 2.3 in full, and the loading states every route shares (section 2.4 steps 1, 2 and 4): `waiting.ts` states that count days, not months; `RouteStatus.svelte` with its one retry and its `data-shimmer` switch; the `__QUERY_ENGINE_BYTES__` define measured by the build; `recording.ts` reading declared queries. The `fetch_ttfb_ms` description is corrected: the code stops at the response headers, not the first byte of the body (Carmack). **No panel imports a query yet.**
- **Files touched:**
  - `frontend/src/lib/console/queries/window.ts`, `shared.ts`, `pipelines.ts`, `model.ts`, `machine.ts`, `voices.ts` (new)
  - `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/eval_row.py`, `backend/idhazh/contracts/host_fingerprint.py` (registries, `WITHHELD_FROM_PANELS`, one changelog line each), `backend/idhazh/contracts/public_telemetry.py` (imports the withheld list), `backend/tests/contracts/test_column_readers.py`, `backend/tests/contracts/test_panel_queries.py` (new)
  - `backend/utilities/build_canary_day.py`
  - `frontend/src/lib/console/waiting.ts`, `frontend/src/lib/console/recording.ts`, `frontend/src/lib/components/RouteStatus.svelte` (new), `frontend/vite.config.ts`, `frontend/src/app.d.ts`
  - `frontend/tests/chart-vocabulary.spec.ts` (gate 10: every `slice(` or `sliceOnce(` call takes a `PanelQuery` imported from `$lib/console/queries/`), `frontend/tests/console-drawn-cells.spec.ts` (new), `frontend/tests/console-waiting.spec.ts` (new), `frontend/scripts/test-groups.ts`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`, `npm --prefix frontend run test:changed -- --list` then the selected checks. CI runs the full suite.
- **Oracle:** **every column a panel will draw is declared once, registered once, and carried by the canary.** `test_column_readers.py` is green with every newly declared column out of `UNREAD_CELLS`; `test_panel_queries.py` refuses a misspelt column and a withheld one (bite: add `detail` to `queries/voices.ts`, watch it fail, restore); `console-drawn-cells.spec.ts` refuses `{@html ` in a file under `frontend/src/lib/console/` (bite, restore); the canary's rows carry a non-empty value for every declared column and one row per listed state. It cannot settle whether a query answers its panel's question; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The queries land before their panels.** They are the declared contract, read by a test in the same row, not modules waiting for a reader | Fowler, 2026-09-28 |
  | 2 | **The shared waiting code is built once here**; left to the first route row, the other three would copy it or wait | Fowler, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Each route row edits the registry | Four rows serial on one contract file, and a column two routes read has two claimants | Route rows one at a time | Fowler |
  | 2 | Leave the registry for row 13 | Every route row would draw a column the registry still calls unread | A false registry for the length of the plan | Fowler |

---

### Row #4 - The query door, measured at the console's real volume

- **Scope:** section 2.10, exactly as written, before any route moves. **The whole pool pauses while it runs.**
- **Files touched:** `backend/utilities/door_volume_fixture.py` (new, writes the uncommitted fixture), `frontend/scripts/measure-door.mjs` (new), `docs/reference/benchmarks/the-query-door-at-the-consoles-real-volume.md` (new), `docs/reference/pipeline-cost.md`.
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `npm --prefix frontend run check:tooling`; `python backend/utilities/doc_load.py` before and after. The fixture is never committed.
- **Oracle:** the benchmark page carries every reading section 2.10 names, the pass line as written before the run, and a pass or a miss on the worst run. A miss is ESCALATE trigger 3, reported with the numbers to plan 51's owner.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Measured at production volume, not on the canary.** The canary holds a few items a day, hundreds of times fewer rows than the question is about | Carmack, 2026-09-28 |
  | 2 | **The pass line is written before the run**, so the reading is compared with a line and not with itself | Carmack, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Measure inside a route row and set a budget knob from the reading | The canary is too small to show the cost, and a budget set from its own reading can never fail | A trigger that cannot fire, and route rows built before the door's shape is known | Carmack, 2026-09-28 |
  | 2 | Time the draw in CI | The runner is shared by four test workers, so wall-clock there is load, not the page | A red build nobody caused | Carmack, 2026-09-28 |

---

### Row #5 - The band reads the ledgers and carries the settings changes, and the four projections nothing draws go

- **Scope:** section 2.6 in full. In `backend/idhazh/telemetry/publish/console_band.py`: the machine facts already read `state/host-fingerprint/` (the comment naming `machine/` is corrected); the site size is read from `run.json` and the article count from `state/day-metrics/`, never from `digest.json`; the months list names the `telemetry` months only. The Judgement tab's description in `console_band.py`, `band.ts` and `newest-day.json` becomes `Which stories the day merged, and where the judge and a person disagreed.` Then the `machine`, `run-days`, public `day-metrics` and public `span-rollup` projections go with their producers, contracts, knobs, copy-step entries, publication checks and canary calls; `state/day-metrics/` and `state/span-rollup/` stay. **In its own commit, `backend/utilities/migrate_to_parquet.py` and its test go**, gated on `git ls-files state/item-health state/scores state/host-fingerprint` finding no `.csv` - its own declared condition.
- **Files touched:**
  - `backend/idhazh/telemetry/publish/console_band.py`, `machine.py`, `run_days.py`, `span_rollup.py`, `day_metrics.py` (the public half only), `dispatch.py`, `series.py`
  - `backend/idhazh/contracts/console_band.py`, `backend/idhazh/contracts/fingerprint.py` (read only unless a name moves), `backend/idhazh/contracts/machine_shard.py`, `backend/idhazh/contracts/public_run_day.py`, `backend/idhazh/contracts/console_payloads.py`, `backend/idhazh/contracts/__init__.py`, `backend/idhazh/contracts/knobs/observability.py`, `backend/idhazh/config.py`, `backend/idhazh/path_classes.py`
  - `backend/idhazh/publication_checks/checks/console.py`, `backend/utilities/build_canary_day.py`, `backend/utilities/migrate_to_parquet.py` (deleted), `backend/tests/ledger/test_migrate_to_parquet.py` (deleted)
  - `frontend/src/lib/console/band.ts`, `frontend/src/lib/console/settings-moved.ts`, `frontend/tests/settings-moved.spec.ts`, `tests/fixtures/settings-moved/five-on-one-day.json`, `tests/fixtures/contracts/console-band/newest-day.json`
  - `config/idhazh.json`, `frontend/scripts/copy-visuals.mjs`, `.gitignore`, `.github/workflows/digest.yml`
  - `backend/tests/test_console_payloads_producer.py`, `backend/tests/contracts/test_console_band_fields.py` (new, the field-set binding), `backend/tests/contracts/test_app_config.py`, `backend/tests/contracts/test_gardener_config.py`, `backend/tests/contracts/test_stamped_boundary.py`, `backend/tests/pipeline/test_day_shards.py`, `backend/tests/workflows/_harness.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `docs/architecture/publishing/console-payloads.md`, `docs/architecture/publishing/retention.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/concepts/config/retention-ages.md`, `docs/concepts/adaptive-pruning.md`, `docs/concepts/growing-reads.md`
  - **At dispatch the worker re-runs the searches for `machine_shard`, `MachineShard`, `public_machine_keep_months`, `PublicRunDay`, `public_run_day`, `public_run_days_keep_months`, `public_day_metrics_keep_months`, `publish_public`, `public_span_rollup_keep_months` and the literal paths `"machine/"`, `run-days/`, `day-metrics/<YYYY-MM>` and `span-rollup/<YYYY-MM>`, adds every match outside `state/`, `corpus/` and `TODO/` to this list, and says so in the pull request**
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests`, `npm --prefix frontend run test:changed -- --list` then the selected checks; `idhazh check-publication` over the canary tree; the browser smoke on `/console/` and `/console/machine/` (the band). CI runs the full suite. **Merge window.**
- **Oracle:** **the band says the same as before, plus the two new lines.** Over the canary tree the band before and after is equal field for field except `months` (the telemetry months only), `settings_moved`, `checker_moved` and the Judgement description. Over the committed record the Python rule and `settings-moved.ts` return the same change dates, and `settings_moved` names the prompt changes of 14 to 18 and 24 September. A band without either new key validates to `None`. After the row no path under `build/` starts with `machine/`, `run-days/`, `day-metrics/` or `span-rollup/`. It cannot settle whether the lines read well on a chart; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The settings line reads the run manifests, through the band** (owner ruling R4, default B1) | Andre, 2026-09-28 |
  | 2 | **The band never opens `digest.json`**: 2.25 s median a run against 0.28 s through `day-metrics`, measured 2026-09-28 on this machine | Carmack, 2026-09-28 |
  | 3 | **These four projections go before any panel moves.** The band was the last reader of two, and nothing reads the other two | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Move the projections under `state/` | A pre-shaped copy under `state/` is still a pre-shaped copy (N7) | A second writer of every fact they hold | Fowler |
  | 2 | Store each change's values beside its names | A 64-character hash per change is what would make the field large and hard to compress | The band's ceiling several times over | Carmack, 2026-09-28 |

---

### Row #6 - Pipelines asks the ledger

- **Scope:** every Pipelines panel in section 2.7, in its order, with its id, frame, gate attributes, driver, expectations and `judged` entry. `/console/` stops fetching `telemetry/<YYYY-MM>.csv` and stops reading `run-timeline/`, `state/span-rollup/` and `data.months`. The build-time panels move to section 2.1 property 3. The row builds `FailureList.svelte`'s stage radio group and puts `data-eval-panel="extraction"` on `extraction`; it does not touch `eval-instruments.ts`. It rewrites the scripts-off case in `console-chart-pending.spec.ts`'s Pipelines expectations.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/RunTimelinePanel.svelte`, `frontend/src/routes/console/RunHealthPanel.svelte`, `frontend/src/lib/components/FailureList.svelte`
  - `frontend/src/lib/console/pipelines/` (new directory: one component and one pure module a moved panel)
  - `config/console/pipelines.json`, `frontend/tests/support/panel-drivers/pipelines.ts`, `frontend/tests/support/console-expect/pipelines.ts`
  - `frontend/tests/console-item-cost.spec.ts`, `console-pipeline-timeline.spec.ts`, `console-substeps.spec.ts` (deleted: the span sub-steps go), `console-telemetry-heal.spec.ts`, `console-reserved.spec.ts`, `console-flow.spec.ts`, `extraction-trend.spec.ts`, `extraction-window.spec.ts`, `time-split.spec.ts`, `console-run-health.spec.ts`, `console-throughput.spec.ts` (each under `frontend/tests/`), and every other spec that visits only `/console/`
  - `tests/fixtures/console/pipelines/` (new: one recorded `slice()` result per query)
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md`, `docs/architecture/publishing/how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md`, `docs/architecture/publishing/run-timeline.md`
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, the `panels` group included. The browser smoke on `/console/` at 390, 768 and 1440 in both themes: zero new `[error]`, zero new `404`, every moved panel draws each state when its fetch is refused, and the page still renders with its data absent. CI runs the full suite.
- **Oracle:** **each moved panel draws from a recorded slice what section 2.7 says.** `failure-mix` one stack a day, and the list ranks `failed_rule` for the chosen stage; `run-timeline` the offsets `run_timeline.py` computed for the canary run; `slower-on-same-work` one point a day on one `cpu_model`, named; `article-age` excludes an inferred time and counts it in the lede. `/console/` makes no request for `telemetry/`, `run-timeline/` or `span-rollup/`. It cannot settle whether the panels are worth their place; Susan reads the 390 dark pictures.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **One pull request for the route.** Its page and server load are one surface | Fowler |
  | 2 | **The run timeline loses its span sub-steps.** 5,887 ms a day does not earn a column; **the reader loses** `tag`, `render_prompt` and `parse_reply` past seven days, and row 12's command gives them back for one item inside the trace window | Susan, 2026-09-26 |
  | 3 | **The items-per-minute figure returns above the run timeline as its lede**, the price of replacing panel 3 | Susan, 2026-09-26 and 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Delete the `telemetry` and `run-timeline` projections here | Their producers share backend files with rows 5 and 12 | This row serial with both | Fowler |

---

### Row #7 - Summaries asks the ledger

- **Scope:** every Summaries panel in section 2.7 and section 2.7a. `/console/model/+page.server.ts` keeps `reasonDays`, the `day-metrics` reads behind `model-cards`, and config.
- **Files touched:**
  - `frontend/src/routes/console/model/+page.svelte`, `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/lib/console/model/` (new directory), `frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/console/model-cards.ts`, `frontend/src/lib/console/doubt-reasons.ts`, `frontend/src/lib/components/ThroughputTrend.svelte`, `frontend/src/lib/components/KpiCard.svelte` (their own model-change marks give way to the settings line)
  - `config/console/model.json`, `frontend/tests/support/panel-drivers/model.ts`, `frontend/tests/support/console-expect/model.ts`
  - `frontend/tests/console-model.spec.ts`, `model-cards.spec.ts`, `console-model-instruments.spec.ts`, `console-ranked.spec.ts` (its Summaries cases), and every other spec that visits only `/console/model/`
  - `tests/fixtures/console/model/` (new)
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`
- **Acceptance gates:** as row 6, on `/console/model/`. `KpiCard` also sits on Pipelines' `at-a-glance`, so the `/console/` pictures are in the selected set.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `call-ending` stacks `length` at the bottom; each of the eight instruments appears where section 2.7a puts it with `Nothing acts on these numbers.`; the protected h2 `What the model did` and its eleven labels are unchanged and the twelfth is the label `eval-instruments.ts` gives `determinism_violation`; `faithfulness` draws a checker line on 26 August and none on 24 September.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The eight instruments go where section 2.7a puts them**, with no threshold, tint or direction | Andre, 2026-09-28 |
  | 2 | **The model cards keep their build-time read** | Andre, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep "Measured, and nothing acts on it" as a list | A backlog is not an operator's question | Zero; costs the route a panel of chores | Susan, 2026-09-26 |
  | 2 | Rebuild the cards' three distinct counts from `scores` and `item-health` in the browser | Measured over the committed record, the rebuilt count disagreed with `day-metrics` on 11 of 35 days, once by 143 | Cards that print a different number from the record | Andre, 2026-09-28 |
  | 3 | Put three instruments behind a switch on `faithfulness` | A switch changes the chart type over one query result; three measures with their own scales and directions are three results, and `coherence` runs from -1 to 1 where the faithfulness axis starts near 65 percent | The tail the panel exists to show | Andre and Susan, 2026-09-28 |

---

### Row #8 - Hardware asks the ledger, and its page carries no data

- **Scope:** every Hardware panel in section 2.7 except `platform-mix`, and the route sentences under that table. Owner ruling R2's default A: `/console/machine/+page.server.ts` returns config and words only, the route stays prerendered, and the built page holds the band's verdict, the tab strip, the window control, the intro's words and every panel's title, note and reserved box in page order, with **no figure, date, window length or mark**. When the data arrives nothing above the first panel moves, except a recording or refused-run sentence, because that sentence is the finding (Jony). It rewrites the scripts-off case in `console-machine-page.spec.ts`.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`, `frontend/src/routes/console/machine/+page.server.ts`
  - every `*Panel.svelte` under `frontend/src/lib/console/machine/` except `PlatformMixPanel.svelte`, and `article-cost.ts`, `context-cost.ts`, `disk-reads.ts`, `memory-held.ts`, `processor-lost.ts`, `prompt-reuse.ts` in that folder
  - `config/console/machine.json`, `frontend/tests/support/panel-drivers/machine.ts`, `frontend/tests/support/console-expect/machine.ts`
  - `frontend/tests/console-machine.spec.ts`, `console-machine-page.spec.ts`, `console-machine-panels.spec.ts`, `console-machine-split.spec.ts`, `console-machine-data.spec.ts`, `console-article-cost.spec.ts`, `console-timings.spec.ts`, and every other spec that visits only `/console/machine/`
  - `tests/fixtures/console/machine/` (new)
  - `docs/architecture/publishing/console-machine.md`, `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md` (with panel 4's note in its design rationale)
- **Acceptance gates:** as row 6, on `/console/machine/`, plus: the served HTML of `/console/machine/` holds no ledger value (search it for a known canary figure and find none; the band's inlined verdict is not a ledger value); a cold visit and a move from Pipelines each draw the band and every panel; nothing above the first panel moves when the data arrives, at 390 and 1440.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `slower-machines` draws two lists, one row per `cpu_model`, each rate divided by the same run's reference median; `two-clocks` marks a shard past `tolerancePct` `disagrees`; the lost state appears for a canary day with `item-health` rows and no `host-fingerprint` rows.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A prerendered page with no data, not off prerender**, until the owner rules R2 | Susan, Carmack and Jony, 2026-09-28 |
  | 2 | **Panel 7 takes a new id and title**: its old id named another panel, and its old title read like Pipelines' panel 3 | Susan, 2026-09-26; Jony, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Take Hardware off prerender in this row | It is owner ruling R2, and option B's costs - a blank first paint, HTTP 404, nothing with scripts off, a fifth serial request - are the owner's to accept | A new row after row 13 if the owner rules B | Susan, Carmack and Jony, 2026-09-28 |
  | 2 | Draw `slower-machines` as one total a kind | One kind reads a token in 37 percent of another's time and writes one in 145 percent of it, so a total says the two are the same | The panel's finding | Carmack, 2026-09-28 |

---

### Row #9 - Voices asks the ledger, and the ranking panels join it

- **Scope:** every Voices panel in section 2.7, in its two groups. `feeds-failed` absorbs panel 22. `ranking-discount` is redrawn on its build-time view. `why-chosen` and `watchlist` arrive from Susan's Pipelines verdicts.
- **Files touched:**
  - `frontend/src/routes/console/voices/+page.svelte`, `frontend/src/routes/console/voices/+page.server.ts`
  - `frontend/src/lib/console/voices/` (new directory)
  - `config/console/voices.json`, `frontend/tests/support/panel-drivers/voices.ts`, `frontend/tests/support/console-expect/voices.ts`
  - `frontend/tests/console-voices-feeds.spec.ts`, `console-voices-retiring.spec.ts`, and every other spec that visits only `/console/voices/`
  - `tests/fixtures/console/voices/` (new)
  - `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`
- **Acceptance gates:** as row 6, on `/console/voices/`.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `feeds-failed` fires an article tile for a canary `429` and a `network_error` and prints `mostly rate limited`; its axis ends at the older of the two rows' newest days; `fetch-time`'s segments sum to its bar; `why-chosen`'s five parts sum to `selection_score` for every drawn row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Panel 22 folds into panel 18** | Susan and Jony, 2026-09-28 |
  | 2 | **`ranking-discount` reads the source-health view**, because `item-health` has no row for the feeds it exists to show | Susan and Jony, 2026-09-28 |
  | 3 | **`why-chosen` and `watchlist` sit here**, beside the ranking panel, not on Pipelines | Jony, 2026-09-28; Susan confirmed |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Tint each fired article tile by its status class | A class is coarser than the fix - a 404 and a 429 are both 4xx and are fixed differently - and a colour per class needs a second key a 6 px tile cannot carry | A key the feed row does not share | Susan, 2026-09-28; Jony agreed |
  | 2 | Draw `ranking-discount` from `item-health` | A feed whose reads failed has no row there, and those are the feeds the discount exists to show; any hand-set `feed_weight` under 1.0 would also draw a bar past the floor | The panel's subject | Susan and Jony, 2026-09-28 |
  | 3 | Hold panel 18 until `feed-health` is published | The article row is the half the verdict found missing | The reader waits a plan for it | Susan, 2026-09-28 |

---

### Row #10 - Judgement carries its ids and gates, and its readers are named for the judge

- **Scope:** section 2.7's Judgement table: ids, frames where missing, gate attributes, drivers, expectations and `judged` entries; panel 15's heading deleted; `NAMED_ABSENCES` in `console-nav.spec.ts` loses it; console.md's Judgement section rewritten. `frontend/src/lib/server/similarity-ledger.ts` becomes `content-similarity-judge.ts` and `similarity-holdout.ts` becomes `content-similarity-holdout.ts` (plan 50's handed-over question: neither is named for the judge or the ledger it reads).
- **Files touched:**
  - `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/judgement/+page.server.ts`, `HoldoutMargin.svelte`, `JudgeAgreement.svelte`, `MergedStoriesPanel.svelte`, `MergeLinePlot.svelte`, `RecordGates.svelte`, `VerdictSplit.svelte` in that folder
  - `frontend/src/lib/server/similarity-ledger.ts`, `frontend/src/lib/server/similarity-holdout.ts` (renamed), and every importer a search for the two names finds
  - `config/console/judgement.json`, `frontend/tests/support/panel-drivers/judgement.ts`, `frontend/tests/support/console-expect/judgement.ts`, `frontend/tests/console-nav.spec.ts`
  - `frontend/tests/merge-line.spec.ts` and every judgement spec the same search finds
  - `docs/architecture/publishing/console.md`
- **Acceptance gates:** as row 6, on `/console/judgement/`.
- **Oracle:** every judgement panel is judged and green on gates 1, 2, 3, 5, 6 and 8; `git grep -n -e similarity-ledger -e similarity-holdout -- frontend docs backend` finds history and nothing else.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The two readers keep their home under `frontend/src/lib/server/` and take the judge's name.** The folder is what keeps a build-time read out of a browser bundle; the names were the defect | plan 50's handed-over question, CLAUDE.md section 0b |
  | 2 | **Panel 15's heading goes with its tab description**, which repeated it word for word; row 5 already rewrote the description | Jony, 2026-09-28 |

---

### Row #11 - The `telemetry` and `run-timeline` projections go

- **Scope:** `frontend/public/telemetry/` and `frontend/public/run-timeline/`, with their producers `public_telemetry.py` and `run_timeline.py`, contracts `PublicTelemetryRow` and `RunTimelineRow`, knobs, the gardener's `public-copy` series in `config/gardener/telemetry-aggregate.json`, copy-step entries, publication checks, the `telemetry/` page-weight ceiling and the canary's projection step. **What bounds a cold console load** once the telemetry ceiling goes is written into `test_page_ceilings.py` and `bundle-gate.mjs`: the plan 51 row 3 ledger ceilings times the route's declared queries. **The band's `months` field goes**: `ConsoleBand` refuses unknown keys and CI reads the committed band, so a `mode="before"` validator drops `months` from an older band, with its removal condition on its line (`delete when no committed band carries months`); `version` stamped, changelog rotated as row 5 did. `band.ts` already reads a band without `months`.
- **Files touched** (from the searches for `public_telemetry`, `PublicTelemetryRow`, `telemetryRows`, `TELEMETRY_ROOT`, `public-telemetry`, `telemetry/<YYYY-MM>`, `run_timeline`, `run-timeline`, `RunTimelineRow`, `loadRunTimeline` and `public_run_timeline`, outside `state/`, `corpus/` and `TODO/`, on 2026-09-28; re-run at dispatch and add any new match):
  - `.github/workflows/digest.yml`, `.gitignore`, `config/idhazh.json`, `config/appearance.json`, `config/gardener/telemetry-aggregate.json`
  - `backend/idhazh/contracts/__init__.py`, `base.py`, `console_band.py`, `console_payloads.py`, `item_health.py`, `knobs/console.py`, `knobs/observability.py`, `machine_panels.py`, `public_telemetry.py` (deleted), `run_timeline.py` (deleted), each under `backend/idhazh/contracts/`
  - `backend/idhazh/gardener/tasks/telemetry_aggregate.py`, `backend/idhazh/month_partition.py`, `backend/idhazh/path_classes.py`, `backend/idhazh/publication_checks/checks/console.py`, `backend/idhazh/stages/assemble.py`, `backend/idhazh/telemetry/__init__.py`, `backend/idhazh/telemetry/publish/console_band.py`, `dispatch.py`, `public_telemetry.py` (deleted), `run_timeline.py` (deleted), `series.py`
  - `backend/utilities/build_canary_day.py`
  - `backend/tests/contracts/test_cell_shapes.py`, `test_page_ceilings.py`, `test_repo_structure.py`, `test_retention_knobs.py`, `test_run_timeline.py` (deleted), `test_stamped_boundary.py`, `test_taxonomy_and_prompts.py`, `test_two_call_ledgers.py`; `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`, `test_telemetry_aggregate_task.py`; `backend/tests/pipeline/test_console_payload_gate.py`, `test_day_shards.py`, `test_publish_window.py`; `backend/tests/test_publish_telemetry.py` (deleted), `backend/tests/test_run_timeline_producer.py` (deleted); `backend/tests/workflows/_harness.py`, `test_commit_script.py`, `test_daily_commit_steps.py`; `tests/fixtures/gardener/prune-oracle/removals.json`, `windows.json`; `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/console-band/newest-day.json`
  - `frontend/scripts/build-canary.mjs`, `build-state.ts`, `copy-visuals.mjs`, `run-checks.ts`, `bundle-gate.mjs`, `tests/build-state.test.mjs`, `tests/test-scope.test.mjs`
  - `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/run-timeline.ts` (deleted)
  - `frontend/tests/console-telemetry-heal.spec.ts`, `one-pass-reductions.spec.ts`, `service-worker.spec.ts`, `telemetry-header.spec.ts`, `support/reduction-input.ts`, `console-band.spec.ts`
  - the docs the search finds: `docs/architecture/contracts/schemas.md`, `state-ledgers.md`; `docs/architecture/publishing/committing.md`, `console-payloads.md`, `retention.md`, `run-timeline.md`, `telemetry-series.md`, `the-served-day-and-the-documents-that-stopped-being-written.md`, `what-a-month-shard-holds-and-how-it-reaches-a-browser.md`, `what-sits-above-every-console-route.md`, `which-console-surfaces-follow-the-window-and-which-say-why-not.md`; `docs/architecture/sources/health.md`, `i-feed.md`, `item-health-columns.md`, `item-health.md`; `docs/architecture/summarize/prompt.md`; `docs/concepts/adaptive-pruning.md`, `config/retention-ages.md`, `growing-reads.md`, `partitions.md`, `summary-metrics.md`, `telemetry-intent.md`, `telemetry.md`; `docs/how-to/run-the-pipeline.md`; `docs/reference/agent-notes/gates-and-builds.md`, `git-and-github.md`, `shell-and-tools.md`; `docs/reference/benchmarks/compressing-the-telemetry-against-re-encoding-it.md`, `docs/reference/host-metrics.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests`, `npm --prefix frontend run test:changed -- --list` then the selected checks; `idhazh check-publication` over the canary tree. CI runs the full suite. **Merge window.**
- **Oracle:** no path under `build/` starts with `telemetry/` or `run-timeline/`; a band written before this row and one written after both validate; the built site is smaller by the two directories, measured and written in the pull request.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`months` is removed with a read-side validator, not left in place.** `ConsoleBand` refuses unknown keys and CI reads the committed band, so without the validator a band written before this row fails the build (CLAUDE.md section 11) | Fowler, 2026-09-28 |
  | 2 | **These two go after Pipelines moves**, because Pipelines' panels are their last readers, and before `span-rollup`, whose search would otherwise find names this row deletes | Fowler, 2026-09-28 |

---

### Row #12 - The `span-rollup` ledger is deleted, and one item's trace is a command

- **Scope:** the family in one commit: `state/span-rollup/`, `SpanRollupRow`, the `SPAN_ROLLUP` member of `LedgerName`, its `config/ledgers.json` entry, its writer in `backend/idhazh/stages/work.py` and `backend/idhazh/telemetry/rollup.py`, its readers `backend/idhazh/stages/validate_days.py`, `backend/idhazh/telemetry/inventory.py` and `frontend/src/lib/server/span-rollup.ts`, and the canary's shard. Plan 50 row 10's measurements and Susan's two rulings of 2026-09-26 move into the design rationale of [docs/concepts/telemetry.md](../docs/concepts/telemetry.md). **The replacement**: `idhazh telemetry item <item_id> --date <YYYY-MM-DD>` prints that item's `item-health` row and, inside `observability.trace_window_days`, its span tree from the one trace file; the two `item` spans of one `trace_id` print as two lines, never summed. **Runs alone.**
- **Files touched** (from the search for `span-rollup`, `span_rollup`, `SPAN_ROLLUP` and `SpanRollup` on 2026-09-28, less what rows 5 and 11 already removed; re-run at dispatch):
  - `state/span-rollup/` (deleted), `config/ledgers.json`, `config/idhazh.json`, `.github/workflows/digest.yml`, `.gitignore`
  - `backend/idhazh/contracts/span_rollup.py` (deleted), `backend/idhazh/contracts/__init__.py`, `ledger_name.py`, `element.py`, `console_payloads.py`, `knobs/observability.py`
  - `backend/idhazh/ledger/__init__.py`, `keys.py`, `rows.py`, `settle.py`; `backend/idhazh/path_classes.py`; `backend/idhazh/publication_checks/checks/console.py`
  - `backend/idhazh/stages/work.py`, `backend/idhazh/stages/validate_days.py`, `backend/idhazh/telemetry/inventory.py`, `prune.py`, `rollup.py`, `cli.py`, `item.py` (new), `publish/console_band.py`, `publish/dispatch.py`, `publish/series.py`
  - `backend/utilities/build_canary_day.py`, `backend/utilities/migrate_to_day_shards.py`
  - `frontend/scripts/build-canary.mjs`, `frontend/scripts/copy-visuals.mjs`, `frontend/src/lib/server/span-rollup.ts` (deleted)
  - `backend/tests/conftest.py`, `backend/tests/contracts/test_app_config.py`, `test_ledger_registry.py`, `test_span_rollup.py` (deleted), `test_stamped_boundary.py`; `backend/tests/gardener/tasks/test_trials_task.py`; `backend/tests/pipeline/test_compact.py`, `test_day_shards.py`, `test_publication_hook.py`, `test_publication_registry.py`, `test_recorded_inputs.py`; `backend/tests/test_console_payloads_producer.py`, `test_ledger.py`, `test_spans.py`, `test_telemetry.py`; `backend/tests/telemetry/test_item_command.py` (new); `backend/tests/workflows/_harness.py`, `test_ledger_staging.py`, `test_pipeline_tests_workflow.py`, `test_telemetry_cli.py`; `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `tests/fixtures/day-shards/writer-files/README.md`
  - `docs/architecture/contracts/schemas.md`, `docs/architecture/extraction/elements.md`, `docs/architecture/publishing/committing.md`, `console-payloads.md`, `retention.md`, `run-timeline.md`, `what-the-pipelines-route-draws.md`, `docs/concepts/adaptive-pruning.md`, `config/retention-ages.md`, `console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`, `console-design/the-rules-every-console-chart-obeys.md`, `growing-reads.md`, `partitions.md`, `pipeline-loop.md`, `telemetry-intent.md`, `telemetry.md`, `docs/reference/benchmarks/compressing-the-telemetry-against-re-encoding-it.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests`, `npm --prefix frontend run test:changed -- --list` then the selected checks. CI runs the full suite. **Merge window.**
- **Oracle:** **the family is gone and nothing asks for it.** `git grep -n -e span-rollup -e span_rollup -e SPAN_ROLLUP -e SpanRollup` finds history and nothing else; `config/ledgers.json` loads; a digest run over the canary writes no `span-rollup` path. The command prints the canary item's row and span tree, its two `item` spans as two lines.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Deleted, not migrated** | Susan, 2026-09-26 (plan 50 row 10's evidence) |
  | 2 | **Not retired first.** The data stays in git history for 60 to 90 days either way (CLAUDE.md section 8), which is the reversal | Fowler |
  | 3 | **Its own pull request, after the projections**: it is the one-way change, and its search would otherwise find names row 11 deletes | Fowler, 2026-09-28 |

---

### Row #13 - ECharts leaves

- **Scope:** `echarts` is uninstalled. Deleted: `frontend/src/lib/charts/Chart.svelte`, `engine.ts`, `core.ts`, `frontend/src/lib/server/chart-render.ts`, and every module under `frontend/src/lib/charts/` whose only purpose was an ECharts option (`chart-flow.ts`, `extraction-trend.ts`, `stacked.ts`, `waterfall.ts`, `fleet.ts` if plan 51 row 8 left an option in it); the engine code is removed from `machine.ts`, `glance.ts` and `cost.ts`, which kept components still import. Deleted also: every module under `frontend/src/lib/` whose last importer a route row removed, including the build-time readers in `frontend/src/lib/server/` no route calls, and `Viewport.svelte`. `COLUMN_READERS` loses any entry naming a deleted file. Every `console.*` knob no reader reads leaves `config/appearance.json` and `ConsoleConfig` (`console.pan_days`, `console.zoom_factor` and any other the search finds). The cross-route docs stop naming the engine.
- **Files touched:** the modules above; `frontend/package.json`, `frontend/package-lock.json`; `frontend/scripts/bundle-gate.mjs`; `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/host_fingerprint.py`, `backend/idhazh/contracts/knobs/console.py`, `config/appearance.json`, `frontend/src/lib/server/config.ts`, the two every-knob fixtures; the seventeen cross-route specs of section 2.2 where they name the engine; `docs/concepts/design-system.md`, `docs/architecture/publishing/console.md`, `frontend.md`, `console-charts.md`, `ui-shell.md`, the window page, `what-the-quality-and-source-panels-draw.md`, `docs/how-to/run-the-gates.md`, `docs/concepts/telemetry-intent.md` (N5's replaced column). The worker lists every deleted module in the pull request, from `git grep -l echarts -- frontend` and an importer search per module.
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, `npm --prefix frontend run check`, `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`; the bundle gate. CI runs the full suite.
- **Oracle:** **`git grep -n echarts -- frontend/src frontend/package.json` finds nothing**, the build succeeds, every console route draws in the browser smoke, and every byte of one cold visit to `/console/` and to `/console/machine/` - the engine included - is measured before and after and written in the pull request.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`machine.ts`, `glance.ts` and `cost.ts` lose their engine code, not their files.** Kept components import their other helpers | Susan, 2026-09-28 |
  | 2 | **Shared modules and unread knobs are deleted here and nowhere earlier**, so no two route rows delete the same file | Fowler, 2026-09-28 |

## What this plan inherits and must close

| # | Inherited from | Closed by |
| --- | --- | --- |
| 1 | Plan 51: four routes draw no panel id | rows 1 (structure) and 6 to 10 (ids) |
| 2 | Plan 51: `echarts` stays installed while two grammars coexist | row 13 |
| 3 | Plan 50 row 9: `backend/utilities/migrate_to_parquet.py` carries "delete when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`" | row 5, its own commit |
| 4 | Plan 50 row 10, collapsed: `span-rollup` is deleted, not migrated | row 12 |
| 5 | Telemetry-intent N7 and N8 | rows 5 and 11; the band is owner ruling R1 |
| 6 | Plan 51 row 5 decision 21: the four house-style components keep their `<title>` until a row puts one on a route | row 2 |
| 7 | Plan 50's open questions: `similarity-ledger.ts` is a second name | row 10. **`scores` renamed `summary-quality`** stays the owner's call: a directory rename is a data migration |

The placeholder's section "The shape this plan is expected to take", which plan 50 cites, is section 1 of this plan.

## Found while planning, handed to the plans that own them

| # | What | Owner |
| --- | --- | --- |
| 1 | Plan 50's row 9 says `frontend/src/lib/server/payload.ts` reads none of the three ledgers it migrates. It reads two: `itemHealthRows` opens `state/item-health/` and `evalRows` opens `state/scores/`. `_machine_rows` and `read_health_rows` in `backend/idhazh/telemetry/publish/console_band.py`, and `machine.py`, `run_timeline.py` and `public_telemetry.py` beside it, also read those ledgers as CSV and are not in its file list. Moved without them, Summaries, Pipelines' item cost and the band's machine verdict read nothing | plan 50, row titled **The three ledgers the console's routes read become parquet** |
| 2 | Plan 51's row 3 publishes columns `public_telemetry.py` refuses as a trust boundary (owner ruling R3). `ItemHealthRow.detail`'s description says "Never source text" while the `_DETAIL` comment says a stranger's headline arrives in it | the owner, before plan 51's row titled **The three ledgers the console reads are published** merges |
| 3 | The door, before any caller exists: keep each index and file for the page's life keyed by path and version, registering each file with the engine once (Carmack: about 590 requests and up to 14 copies of one window at 30 days without it, about 62 and one copy with it; about 50 lines); add `ledgerReach(ledger)` (section 2.3); consider a column-shaped result | plan 51, row titled **The query door module and its two entry points** (#1154) |
| 4 | Plan 51's row 8 adds `platform-mix` to `console.judged_panel_ids` in `config/appearance.json`; after this plan's row 1 that is `judged` in `config/console/machine.json`, and its date series takes the `rule` argument after row 2 | plan 51, row titled **One panel end to end: the browser fetches the ledger and draws it in d3** |
| 5 | CLAUDE.md section 1a says every config file is a Pydantic model; the owner ruling of 2026-09-21 says a project-authored config file declares only what its readers compute on. A one-line amendment | the owner |

## See also

- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) - the ledgers, the compaction and the migration this plan reads through; its row 10 holds the `span-rollup` measurements.
- [`20260924-51-console-fetches-and-draws-its-own-data-plan.md`](20260924-51-console-fetches-and-draws-its-own-data-plan.md) - the query door (section 2.2), the chart vocabulary (2.6), the readout strip (2.7), the ten gates (2.8) and the pictures (2.9) this plan builds on.
- [`../docs/concepts/telemetry-intent.md`](../docs/concepts/telemetry-intent.md) - N2 to N8.
- [`../docs/concepts/console-design/how-a-console-chart-gets-its-data.md`](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every panel here is built to.
- [`../docs/architecture/publishing/console-payloads.md`](../docs/architecture/publishing/console-payloads.md) - what the console reads today, and the projections this plan deletes.
