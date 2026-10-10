# Plan 52 - The console's panels ask the ledger when they are looked at, ECharts leaves, and six projections go

**Last Updated**: 2026-10-10

**Status**: Row 1 is merged in PR #1529. Rows 3a and 3 are implemented on `feat/console-judgement-panels`, ready for PR checks and merge: route-owned window tests and truthful retained Judgement evidence. Row 12 and its related public-projection and reader deletions are complete in merged PR #1189. Row 12 stays COLLAPSED.

**Level**: 5 (CLAUDE.md section 6). Rows 5 and 10 change a persisted payload every console document carries. The route rows are Level 3: each crosses code and published data on one route. **Authorizing this plan is the design consultation section 6 asks of rows 5 and 10.** Row 12's approved deletion is carried by #1189.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3, N4, N5, N7 and N8 - a panel asks `state/` for the columns and days it draws, when it is looked at, drawn in d3, and no pre-shaped copy of a ledger survives under `frontend/`. **Contract**: section 2 declares every file, function, query, column, type, knob, field, sentence and deletion the rows need; section 2.7 is Susan's panel verdicts of 2026-09-26 turned into ids, columns, types and words. **Code**: the twelve rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates each row to a worker; keep parallel N = 4 rows in flight as a running pool, refilling a slot the moment a worker returns and never waiting on a merge; a row is ready when its `Depends-on` rows are DONE and its `Files touched` list shares no entry with a row in flight, in this plan or in the rows of plan 55 that section 1 names; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. The original user task authorizes implementation; the latest direction in section 0 controls what is checked.

## 0. Operating contract

**Latest user direction.** Implementation is authorized by the original task, not by a new approval round. Stop size, performance and timing measurements, and baseline-picture work. Do not run measurement harnesses, collect before/after readings, create or refresh picture baselines, or hold a row for a missing measurement. This overrides older measurement and picture-comparison requirements below, including section 2.10 and ESCALATE trigger 3. Correctness tests, missing/empty-data checks and integrated browser smoke remain mandatory. Existing test timeouts remain in force; a timeout is a correctness failure to investigate, not permission to start a benchmark.

**Owner direction, 2026-10-10.** Row 3 may repair the outgoing Pipelines page's shared-config access and update its renamed reader references in the three shared docs listed in its scope. Visual and colour improvements are approved. Bring concrete speed improvements for a shell UI with no prerender to the owner before changing that architecture; the existing measurement suspension remains in force.

**Structural repair approved, 2026-10-10.** The owner selected A3 after Fowler and Susan's consultation. Row 3a completes route ownership of the shared window tests before row 3 retains existing read-state information and unknown counts through Judgement. This replaces the proposed five-literal exception. Both are ordered Level 3 changes, not new persisted contracts or a no-prerender change. Keep real zero and partial evidence, independent exact expectations, and every existing route and assertion.

| Field | Value |
| --- | --- |
| **Blocked by** | Row 1 is in flight; rows 2 and 3 follow it. Plan 50 rows 9 and 12 are complete (#1166, #1161); publication and page-cache prerequisites are complete (#1169, #1157). The remaining dependencies are the rows in section 1, not a new measurement. **A route row (6 to 9) merges only when the live site carries what it reads** (section 1, "Before a route row merges"); until then its branch waits and the pool keeps running |
| Why this plan exists | A console panel reads a file the build wrote in advance, so the question it can ask was fixed by whoever wrote that file. The browser can now ask the ledger directly. This plan moves every panel whose facts are in the three published ledgers onto the query door, redraws every chart that still uses ECharts so it can be uninstalled, applies Susan's verdicts, and deletes the six telemetry projections under `frontend/public/` once nothing reads them |
| Hard scope - in | - Each route gets its own console file, test expectations and gate drivers, and every console page reads its config from one build-time value (row 1).<br>- The chart types become ready for a route: the ranked list draws a range and two named ends, the date series carries the settings line and named rules, every type carries its readout and its chart attribute, and the series colours become one table (row 2).<br>- Judgement carries its ids and gates, and its two readers are named for the judge (row 3).<br>- Every panel's query is declared in code before any panel draws it, with the loading states every route shares, the packed canary and the browser fixture; correctness checks remain required, but the volume measurement is suspended (row 4).<br>- The band reads the ledgers and carries the settings and checker changes; four projections nothing draws go (row 5).<br>- Every panel whose facts are in `item-health`, `scores` or `host-fingerprint` asks the door at view time (rows 6 to 9), with Susan's verdicts applied panel by panel: panels 4 and 15 deleted, panels 3 and 13 replaced, panel 22 folded into panel 18, the new panels added, the rest kept or redrawn (section 2.7).<br>- The `telemetry` and `run-timeline` projections go (row 10); `echarts` is uninstalled (row 11); the `span-rollup` ledger goes and one item's trace becomes a command (row 12) |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. **A panel needs a column its query in section 2.7 does not name, or a column in `UNREAD_CELLS`.** Stop and report the column and why: row 4's registry is the one record of which surface reads a column.<br>2. **A panel on the build-time list (section 2.8) is asked to move to the door.** Its dataset is not published; moving it is the first out-of-scope row below.<br>3. **Suspended by the latest user direction.** A missing or failed measurement does not hold rows 6 to 9; correctness failures still block delivery.<br>4. **Deleting any path under `state/` other than `state/span-rollup/`.**<br>5. **An owner ruling in section 2.11 differs from its default.** Re-open only the rows it names.<br>6. **A row needs a file outside its `Files touched` list that the cross-route list (section 2.2) gives another row, or a route row needs a file that names another route.** Stop: the file belongs to the row the list names.<br>7. **The engine's add-on request, made from the engine's own worker, cannot be answered from the local copy in a browser spec** (section 2.3, "The browser fixture"). The test build's add-on address is then a design question for the owner |
| Chosen strategy | Contracts first, then one pull request per route, then deletions. Rows 1 to 4 take every file the route rows would otherwise share off the table - the panel lists, the console config value, the test expectations, the gate drivers, the chart components, the colour table, the column registry, the loading states and the browser fixture - so the route rows run side by side. Ruled by Fowler (CLAUDE.md section 14) |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Row 1 fans out by file inside one checkout, and row 4 runs two workers in sequence on one branch; each row's scope says how |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Publishing the other datasets the console reads**: `state/day-metrics/`, `state/feed-health/`, the run manifests and item facts inside the digest day files, the source-health view, and `state/content-similarity-judge/` | The panels section 2.8 lists keep a build-time read, so N2 and N3 are not met for those panels and their routes stay prerendered. They draw without ECharts, so N5 is met. **The reader loses** nothing they have today; they do not gain view-time freshness on those panels | Its own plan: each dataset needs a parquet contract, a writer through the ledger door, a compaction task, a publish entry and a `LedgerName` member - plan 50's migration row again for each. Plan 50's ESCALATE trigger 3 makes each migration a person's call |
| Changes to the query door itself: a column-shaped result, a "newest N days" ask, a structured aggregate | Rows 6 to 9 use the [shipped query reader and page cache](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md). Measurements are suspended by the latest user direction | A separate owner direction; ESCALATE trigger 3 is suspended |
| New questions beyond Susan's verdicts | None today | A later Susan pass |
| `failed_field` (verdict 27) | It stays in `UNREAD_CELLS`, empty on every committed row | A row that gives it a writer or deletes the column |
| A page where an operator types a question | Nothing here; the Data explorer is delivered | [The written-question reader](../docs/architecture/publishing/how-the-query-door-answers-a-written-question.md), delivered by #1201 and the Data explorer PRs |

### The intent this plan serves

| # | The intent, in short | What this plan does about it |
| --- | --- | --- |
| N2 | The browser queries the parquet itself | **Delivered for every panel whose facts are in the three published ledgers** (section 2.7), alongside the shipped `platform-mix`. The panels section 2.8 lists are the first out-of-scope row |
| N3 | The browser fetches its own data at view time | The same panels |
| N4 | The prerendered routes come off it | **No data route's document carries a ledger value** after its route row (section 2.4, "The built page"). Whether the routes also drop the prerender flag is owner ruling R2 |
| N5 | d3 is the only charting library | **Delivered.** Row 11 uninstalls `echarts` and deletes `Chart.svelte`, `engine.ts`, `core.ts` and `frontend/src/lib/server/chart-render.ts` |
| N7 | No telemetry projection survives in `frontend/` | **Delivered for the six** (rows 5 and 10). `console/band.json` is owner ruling R1 |
| N8 | `frontend/` holds UI code, not artefacts | The same six |

## 1. Status Reckoner

**Eleven remaining pull requests.** Row 12 was completed by #1189. One active row is one pull request. The dispatcher is a running pool: a slot frees when a worker returns, never when a pull request merges. `Depends-on` and `Files touched` are the readiness test; `Parallel-group` is a hint.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Each route gets its own console file, gate drivers and test expectations | - | A | DONE | p52-route-ownership (`feat/console-route-ownership`) | Read from merge | Owner and file workers |
| 2 | The ranked list draws a range and a floor, the date series carries the settings line, and every type carries its readout | 1 | B | PENDING | - | - | - |
| 3a | Each route owns its detailed window tests; the shared spec checks shared promises only | 1 | B | READY: implemented; PR checks and merge pending | p52-judgement (`feat/console-judgement-panels`) | Read from merge | Fowler and owner |
| 3 | Judgement carries its ids and gates, and preserves what the evidence can establish | 1, 3a | B | READY: implemented; PR checks and merge pending | p52-judgement (`feat/console-judgement-panels`) | Read from merge | Susan, Fowler and owner |
| 4 | Every panel's question is declared before it is drawn, and the door is measured at the console's real volume | 2 | C | PENDING | - | - | - |
| 5 | The band reads the ledgers and carries the settings changes, and the three remaining projections nothing draws go | 3, 4 | D | PENDING | - | - | - |
| 6 | Pipelines asks the ledger | 5 | E | PENDING | - | - | - |
| 7 | Summaries asks the ledger | 5 | E | PENDING | - | - | - |
| 8 | Voices asks the ledger, and the ranking panels join it | 4 | D | PENDING | - | - | - |
| 9 | Hardware asks the ledger, and its page carries no data | 5 | E | PENDING | - | - | - |
| 10 | The `telemetry` and `run-timeline` projections go | 6 | F | PENDING | - | - | - |
| 11 | ECharts leaves | 7, 8, 9, 10 | G | PENDING | - | - | - |
| 12 | Moved to #1189: the aggregate is deleted and one item's trace is a command | - | H | COLLAPSED | - | - | - |

**External prerequisites and completed foundations.** Unresolved row dependencies retain their `plan N row M` cells; completed foundations are named by their shipped change:

| Prerequisite | Row title | State at last review |
| --- | --- | --- |
| plan 50 row 9 | The three ledgers the console's routes read become parquet | Complete, #1166 |
| plan 50 row 12 | The closed-day fold of the CSV day trees moves into the gardener | Complete, #1161 |
| Three-ledger publication | The three ledgers the console reads are published | Complete, #1169; live coverage is still checked below |
| Machine mix | One panel end to end: the browser fetches the ledger and draws it in d3 | Complete, #1171; rows 1, 2, 4 and 9 here own its later adaptation |
| Page cache and reach | The door keeps what it fetched for the page's life, and says how far a ledger reaches | Complete, #1157 |

Plan 50's final local Reckoner records both rows DONE. The plan was closed and removed by #1174; its status is read from the named plan file before that local merge, not from a public query or a scan of other plans.

**Rows of other plans that are never in flight with a row here**, because they share files. The readiness check compares against them too:

| Other plan's row | Shared with | Order |
| --- | --- | --- |
| plan 55 row 1, **The span control loses its label and the console opens on fourteen days** | rows 2, 4, 5, 10, 11 and 12 (`config/appearance.json`, `backend/idhazh/contracts/knobs/console.py`, `WindowStatus.svelte`, the `console-window` expectations) | after row 1; whichever of it and row 4 is ready first goes, and the other takes main in first |
| plan 55 row 2, **The strip gains a sixth tab and the band learns its route id** | rows 3, 5, 10, 11 and 12 (`band.ts`, both `console_band.py`, `ConsoleNav.svelte`, every `console-expect/<spec>/index.ts`, `panel-drivers/index.ts`) | after row 1 |

**Why the route rows can run side by side.** After rows 1 to 4, each route's page, server load, panel directory, console file, test expectations, gate drivers, own specs and own doc page belong to that route alone, and every file two routes use is on the cross-route list (section 2.2) with the rows that edit it. **A shared module a route row stops importing is left in place** and deleted by row 11, so no two route rows delete the same file. **A `console.*` knob a route row stops reading is left in place** and deleted by row 11.

**Why row 8 starts before row 5.** Voices draws no settings line, so it needs only row 4. **Row 9 keeps the shipped machine mix** while the other Hardware panels move, after this plan's query and config declarations land. **Row 5's plan 50 prerequisite is complete.** Row 12 there moved the closed-day fold in #1161; row 5 reads that shipped layout and no longer waits for that row.

**Before a route row merges** (rows 6 to 9). The owner confirms, for each ledger the row's queries name: its compaction task on main has `"dry_run": false`, and the live site's `index/daily.json` and `index/monthly.json` together name every UTC day from the later of the ledger's oldest day on main and the day `max(console.window_presets) - 1` days before the merge, to a day at most three days before the merge; a day both indexes name is allowed. A branch that fails waits, and the pool keeps running. Without the check, a route row can merge while the live site has no packed files, and every moved panel on the live console reads "Not published yet." - **the reader loses** the panels they have today.

**Merge windows.** Rows 5, 10 and 12 edit `.github/workflows/digest.yml`, so each merges only while no digest run is queued or running.

**Rows in flight, stretch by stretch:**

| Stretch | Rows in flight | What limits it |
| --- | --- | --- |
| Row 1 | 1, with four spec workers inside it | every other row needs it |
| Rows 2 and 3, then row 4 | 2, then 1 | row 4 shares files with row 2 and names the external prerequisites above |
| Rows 5 and 8 | 2 | rows 6, 7 and 9 need row 5 |
| Rows 6 to 9, then row 10 in row 6's slot | 4 | the pool |
| Row 11 | 1 | row 11 edits shared files; row 12 moved to #1189 |

**What a worker runs locally.** The list the shared selector gives for the row's own changes (`npm --prefix frontend run test:changed -- --list`), restricted to correctness checks by section 0's latest direction. After row 1 that is the route's own correctness tests for a route row; no size, performance, timing or baseline-picture run is required or authorized. **A row that edits a file two routes render runs every correctness spec whose page renders it** - on plan 51 a shared readout change passed its route's specs locally and failed 17 in CI. Integrated browser smoke remains mandatory. CI runs the full suite.

**Every new test module a row adds carries a module-level `pytestmark`**, so `backend/tests/test_marks.py` is in no row's list. **The plan-doc itself is excluded from the disjointness diff**; every row stamps its own Reckoner line.

## 2. The contracts

Every name below is declared once, here. A row cites the section; it does not restate it.

### 2.1 What "moved" means for one panel

A panel is moved when all of these hold. A route row is done when every panel on its route is moved, or is on the build-time list (section 2.8) and holds properties 1, 3, 4, 5, 6, 7, 8 and 10.

| # | Property | Checked by |
| --- | --- | --- |
| 1 | It carries `data-console-panel-id` with its id from section 2.7, and its route's console file lists it in page order | `frontend/tests/panel-captures.spec.ts` |
| 2 | Its data comes from queries declared in `frontend/src/lib/console/queries/` (section 2.3), asked through `sliceOnce` at view time | gate 10 in `frontend/tests/chart-vocabulary.spec.ts`, widened by row 4 |
| 3 | **It keeps its component, or draws with a vocabulary type.** A KEEP panel keeps its component unless that component imports `frontend/src/lib/charts/Chart.svelte` or draws a chart rendered by `frontend/src/lib/server/chart-render.ts`; such a panel is drawn on the type section 2.7 names. A kept component may import `frontend/src/lib/charts/machine.ts`, `glance.ts` or `cost.ts` for their other helpers, because row 11 strips the engine code out of those three rather than deleting them. After row 11 nothing on the console imports `echarts` | the single-engine walk in `chart-vocabulary.spec.ts`; row 11's uninstall |
| 4 | It carries exactly one `data-lede`, exactly one `data-comparison`, a `data-model-rule` declaration and `data-panel-question` ([the sufficiency gates](../docs/concepts/design-system.md#sufficiency-is-a-gate-not-a-taste); [console.md](../docs/architecture/publishing/console.md)), with the lede and comparison section 2.7b gives it | `frontend/tests/panel-sufficiency.spec.ts` |
| 5 | It draws the loading rules of section 2.4 and every state of `frontend/src/lib/console/waiting.ts`, and its route's driver module puts it into each. **A build-time panel** makes no fetch: it is listed in its driver module's `BUILD_TIME`, and gate 8 judges it on `quiet` and `missing` only, from its component test (section 2.2) | gate 8 in `panel-sufficiency.spec.ts`; the route's nothings spec |
| 6 | Its readout declares `data-readout-columns`, `data-readout-records` or `data-readout-none` under [the shared chart and readout rules](../docs/concepts/console-design/the-rules-every-console-chart-obeys.md) | `frontend/tests/console-readout.spec.ts` |
| 7 | Its id is in its route's `judged` list | `panel-sufficiency.spec.ts` |
| 8 | A test drives its pure module from a recorded slice under `tests/fixtures/console/<route>/` (section 2.3), or from its build-time input, reads that fixture inside the test, and touches no network | the row's own spec |
| 9 | Its route's built page carries none of its ledger values (section 2.4, "The built page") | `frontend/tests/console-built-page.spec.ts` |
| 10 | Every chart it draws carries `data-chart-type` or `data-chart` on its marks | gate 1 |

**Before a route row returns**, its worker runs correctness tests and integrated browser smoke, without a volume measurement or baseline-picture comparison. It consults Susan and Jony only where two defensible answers would change the code, and applies every ruling its own files can hold. A ruling that needs a file outside its list is ESCALATE trigger 6. A gate left failing ships only with a `## Design rationale` line on the route's doc page that names it.

### 2.2 Each route's console file, the console value, test expectations and gate drivers (row 1)

**`config/console/<route>.json`**, one file for each of the six members of `RouteId` in `frontend/src/lib/console/band.ts`: `pipelines`, `model`, `machine`, `voices`, `judgement` and `data-explorer`. The Data explorer page is already delivered; row 1 preserves it.

```json
{
  "panel_groups": [
    { "id": "what-the-machine-was-doing", "title": "What the machine was doing", "panels": ["two-clocks", "processor-lost"] }
  ],
  "judged": ["two-clocks"],
  "knobs": {}
}
```

| Key | Meaning | Refused, naming the file and the key |
| --- | --- | --- |
| `panel_groups` | The route's panels in drawn order, grouped as the jump links group them. A route with one untitled group writes `"title": ""` | a route that titles some groups and not others; a group id used twice; a panel named twice on one route, or on two routes |
| `judged` | The route's panels the sufficiency gates judge | an id the route does not draw; an id listed twice |
| `knobs` | Values only this route's panels read, each minted by the row that first reads it (section 2.9) | a value that is not a finite number; a knob a panel asks for that the file does not have: `routeKnobs` throws `config/console/<route>.json names no knobs.<key>`. No default lives in code |

The loader also refuses a file name that is not a `RouteId`, a `RouteId` with no file, a key other than the three above, and a missing one of the three. Row 1 preserves today's `pipelines`, `machine` and `data-explorer` panel groups from `config/appearance.json`, and assigns each route only the existing judged ids it draws. `model`, `voices` and `judgement` have empty `panel_groups` and `judged` until their route rows. Data explorer keeps `data-explorer-ask`, `data-explorer-rows` and `data-explorer-shape` in their existing order.

**One module reads the console config** (`frontend/src/lib/console/route-console.ts`, row 1):

```ts
export interface RouteConsole {
	readonly panel_groups: readonly ConsolePanelGroup[]; // the type moves here from config.ts
	readonly judged: readonly string[];
	readonly knobs: Readonly<Record<string, number>>;
}
export type RouteConsoles = Readonly<Record<RouteId, RouteConsole>>;
export interface ConsoleDefine {
	readonly shared: ConsoleConfig;
	readonly routes: RouteConsoles;
}
/** Pure. Keyed by file name without .json; applies every refusal above. */
export function routeConsolesFrom(files: Readonly<Record<string, unknown>>): RouteConsoles;
export function routeConsole(route: RouteId): RouteConsole;
export function consoleKnobs(): ConsoleConfig;
export function routeKnobs<K extends string>(route: RouteId, keys: readonly K[]): Readonly<Record<K, number>>;
```

- `route-console.ts` uses relative imports only and names `__CONSOLE__` only inside function bodies, because `frontend/vite.config.ts` loads it through `config.ts` before the define exists and outside SvelteKit's aliases.
- `frontend/src/lib/server/config.ts` gains `routeConsoles(): RouteConsoles`, which reads every `config/console/*.json` through `routeConsolesFrom`. `PANEL_GROUP_DEFAULTS`, `panelGroupsFor` and the readers of `console.panel_groups` and `console.judged_panel_ids` go.
- `frontend/vite.config.ts` defines `__CONSOLE__: JSON.stringify({ shared: consoleConfig(), routes: routeConsoles() })` beside `__UI_CONFIG__`; `frontend/src/app.d.ts` types it as `ConsoleDefine`.
- **Only `route-console.ts` names `__CONSOLE__`**, because Vite writes a define's whole value into every module that names it. Only `frontend/src/lib/server/config.ts` and files under `frontend/src/routes/console/` import `route-console.ts`; code under `frontend/src/lib/` takes these values as props, so a test can drive it.
- Row 1 moves `frontend/src/routes/console/+layout.svelte` onto the value - the window presets and default, `completeness_grace_days`, and the active route's titled `panel_groups` as its jump links - because plan 55's route has no server load. Each route row moves its own page onto it and drops `console` and `panelGroups` from its own server load.
- `ConsolePanelGroup`, `console.panel_groups` and `console.judged_panel_ids` leave `backend/idhazh/contracts/knobs/console.py`; both fields leave `config/appearance.json`. Their panel-list validation leaves with them. **No alias and no new Pydantic model is owed**: a configuration file this project authors declares what its own readers compute on and refuses a missing key by name (Guardrail #3, owner ruling 2026-09-21).

**Test expectations**, one folder per spec and one file per route inside it:

```ts
// frontend/tests/support/console-expect/<spec>/index.ts - row 1 writes it; only a new RouteId edits it again
import type { RouteId } from '../../../../src/lib/console/band';
import { EXPECT as pipelines } from './pipelines'; // likewise model, machine, voices, judgement
import { EXPECT as dataExplorer } from './data-explorer';
export interface RouteExpect { /* what <spec> checks on one route */ }
export const BY_ROUTE: Readonly<Record<RouteId, RouteExpect | null>> = { pipelines, model, machine, voices, judgement, 'data-explorer': dataExplorer };

// frontend/tests/support/console-expect/<spec>/<route>.ts - row 1 creates it; after that only <route>'s row edits it
import type { RouteExpect } from './index';
export const EXPECT: RouteExpect | null = { /* typed-out literals */ }; // null: nothing to check on this route
```

- `<spec>` is the spec's file name without `.spec.ts`. The seventeen specs that name two or more console routes today are `console-axis`, `console-band`, `console-chart-lifetime`, `console-chart-pending`, `console-chrome`, `console-frame`, `console-mark-parity`, `console-model-panels`, `console-model-rule`, `console-nav`, `console-polarity`, `console-readout`, `console-shell`, `console-title`, `console-voices`, `console-window` and `console` (each `frontend/tests/<name>.spec.ts`). Row 4 adds an eighteenth, `console-built-page`.
- **A data file holds typed-out values only**, never a value read from `config/` or `band.ts`: a spec that reads the source it guards proves only that the page agrees with itself.
- A spec skips a route whose `EXPECT` is `null`, and holds no route address of its own.
- When `RouteId` gains a member, `npm run check` fails until every `index.ts` names it, because SvelteKit's `tsconfig.json` includes `tests/`.
- Judgement's entry in `NAMED_ABSENCES` moves to `console-expect/console-nav/judgement.ts`. Routes that intentionally draw no `Chart.svelte` declare `null` expectations for `console-chart-pending` and `console-chart-lifetime`; rows 6 and 9 update their own expectation files when moving the last chart. A route still expected to draw charts must fail if its charts vanish, never infer a skip from the rendered page.

**Window-test ownership amendment, 2026-10-10.** Row 3a moves each route's detailed window fixtures, case tables and execution out of `console-window.spec.ts` into that route's focused specs and helpers. The shared spec retains common window arithmetic, control and surface-coverage checks, and cross-route navigation. Expectation files contain independent typed literals only, never executable callbacks or values derived from production copy. The new specs are explicitly registered; helper-only changes select their checks. The amendment covers this shared spec, not an audit of the other sixteen.

**Gate drivers**, one module a route:

```ts
// frontend/tests/support/panel-drivers/<route>.ts - row 1 creates it; after that only <route>'s row edits it
import type { Driver, Nothing } from '../panel-gates';
export const DRIVERS: Readonly<Record<string, Readonly<Record<Nothing, Driver>>>>;
export const BUILD_TIME: readonly string[]; // judged panels drawn at build time (section 2.8)

// frontend/tests/support/panel-drivers/index.ts - row 1 writes it
export const BY_ROUTE: Readonly<Record<RouteId, { readonly DRIVERS: typeof DRIVERS; readonly BUILD_TIME: readonly string[] }>>;
```

- The `Driver` type moves into `frontend/tests/support/panel-gates.ts`. The sufficiency spec refuses a judged id that is in both lists or in neither, and an id two modules drive.
- **A build-time panel's nothings** are checked by its route's nothings spec (`frontend/tests/console-<route>-nothings.spec.ts`, logic group, written by the row that judges the panel): it renders the component from an empty input and from an absent input, with no page build and no faked fetch, passes both readings to `judgeNothings` narrowed to `quiet` and `missing`, and asserts the two sentences differ.
- **The sufficiency spec** is generated from `RouteId`, `CONSOLE_WIDTHS` (`frontend/tests/support/console-widths.ts`) and the two themes, and reads no file at module level: one test of one page load per route, width and theme for gates 1, 2, 3, 5 and 6; and, for each route with a driven panel, one test per theme that makes four page loads, one per nothing. Each test stays inside the 180 s test limit with room to spare (an estimate: under 60 s).

**The capture route list is `RouteId`**, and a route's address is its `href` in `BAND_UNREAD.routes` in `band.ts`. `CONSOLE_ROUTE_PATHS` is deleted. A route with empty `panel_groups` has nothing to capture. `DRAWS_NO_PANEL_ID` in `panel-captures.spec.ts` keeps `pipelines` until row 6 deletes it.

**The cross-route rule, and its check.** A file names a route when it holds that route's `href` as a quoted literal, matching ``(['"`])<href>\1``. `frontend/tests/console-route-scope.spec.ts` (new, logic group, row 1) fails when:

- a `console-expect/<spec>/<route>.ts` or a `panel-drivers/<route>.ts` names another route;
- an `index.ts` in those folders, or one of the eighteen cross-route specs, names any route;
- any other spec names two routes, except `frontend/tests/console-machine-page.spec.ts`, which names `/console/` and belongs to row 9;
- `__CONSOLE__` appears outside `frontend/vite.config.ts`, `frontend/src/app.d.ts` and `route-console.ts`, or a file outside `frontend/src/lib/server/config.ts` and `frontend/src/routes/console/` imports `route-console`;
- (row 4 adds the case) a spec opens a moved route without importing `test` from `door-page` (section 2.3).

**The cross-route list** - every file two or more routes use, and the rows that edit it, in order. A route row edits only the files in the second line for its own route.

| File | Rows that edit it, in order |
| --- | --- |
| the seventeen cross-route spec bodies | 1, 4 (they import `test` from `door-page`), 11; `console-band.spec.ts` also 5 and 10; `console-window.spec.ts` also 3a (owner-approved extraction) |
| `console-expect/<spec>/<route>.ts`, `panel-drivers/<route>.ts`, `config/console/<route>.json` | 1, then that route's row (machine: 9, preserving the shipped `platform-mix`) |
| `console-expect/<spec>/index.ts`, `panel-drivers/index.ts`, `route-console.ts`, `frontend/tests/support/panel-gates.ts` | 1 (`console-built-page`'s folder: 4); `console-window` expectations also 3a (remove route-specific execution contracts) |
| `frontend/src/routes/console/+layout.svelte`, `frontend/vite.config.ts`, `frontend/src/app.d.ts` | 1, 4 |
| `frontend/tests/panel-sufficiency.spec.ts` | 1, 2, 4 |
| `frontend/tests/panel-captures.spec.ts` | 1, 4, 6 |
| `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/machine/+page.server.ts` | 1, then that route's row |
| `frontend/src/lib/console/machine/PlatformMixPanel.svelte` | 2 (chart props), 4 (declared query caller), 9 (route integration) |
| `frontend/src/lib/console/band.ts` | 3, 5 |
| `backend/idhazh/telemetry/publish/console_band.py`, `tests/fixtures/contracts/console-band/newest-day.json` | 3, 5, 10 |
| `backend/idhazh/contracts/console_band.py` | 5, 10 |
| `frontend/src/lib/components/FailureList.svelte`, `KpiCard.svelte`, every `frontend/src/lib/charts/d3/` type module | 2, then 11 |
| `frontend/src/lib/console/waiting.ts`, `recording.ts`, `rates.ts`, `queries/*`, `frontend/src/lib/components/RouteStatus.svelte`, `WindowStatus.svelte`, `Reserved.svelte`, `frontend/src/lib/charts/d3/EmptyState.svelte`, `empty.ts`, `frontend/tests/support/door-page.ts`, `tests/fixtures/console/*` | 4 (`queries/machine.ts` includes `platformMixQuery` and its shipped caller moves with it; the month functions in `waiting.ts`: 11) |
| `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py`, `frontend/src/lib/server/config.ts`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json` | 1, 2, 10, 11 |
| `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json` | 1, 2, 5, 10, 11, 12 |
| `backend/utilities/build_canary_day.py`, `frontend/scripts/build-canary.mjs` | 4, 5, 10, 12 |
| `frontend/src/lib/console/eval-instruments.ts`, `frontend/tests/console-model-instruments.spec.ts` | 7 |
| `.github/workflows/digest.yml` | 5, 10, 12 |
| `docs/architecture/publishing/console.md` | 1, 3, 11 |
| every other doc that names two or more routes | 11 |

**Selector.** `config/console/` joins `CONSOLE_OWNED` and `PANELS_DRAWN` in `frontend/scripts/test-scope.ts`, with cases in `frontend/scripts/tests/test-scope.test.mjs`; without it the selector reads a console file as unknown and selects everything.

Row 1 also owns known defect 45: a selector truth-table case must show that editing `Panel.svelte` selects the console specs as well as the panels group on a pull request.

### 2.3 A panel's query, and the fixtures that test it (row 4)

**`frontend/src/lib/console/queries/`**: one module for each of `pipelines`, `model`, `machine` and `voices`; `shared.ts` for a query two routes draw, re-exported by each route module that draws it; `window.ts` for the reach, the range and the memo.

```ts
import type { DateStamp, LedgerName, LedgerReach, Predicate, SliceResult } from '$lib/data/ledger';
import { ledgerReach } from '$lib/data/ledger';

/** What one panel asks one ledger. Declared here and nowhere else, so the columns a panel
 *  reads are one list the column registry names. `columns` is a literal array of string
 *  literals, so a backend test can read it. */
export interface PanelQuery {
	readonly name: string;
	readonly ledger: LedgerName;
	readonly columns: readonly string[];
	readonly where?: readonly Predicate[];
	readonly span: 'window' | 'newest-day' | 'widest';
}

// window.ts. LedgerReach, from the door (#1157):
//   {state: 'ok'; first; through} | {state: 'quiet'} | {state: 'missing'} | {state: 'unreachable'}
export interface RouteReach {
	/** The oldest `through` among the route's ledgers whose reach is `ok`; null when none is. */
	readonly through: DateStamp | null;
	readonly ledgers: Readonly<Partial<Record<LedgerName, LedgerReach>>>;
}
export function routeReach(ledgers: readonly LedgerName[]): Promise<RouteReach>;

export interface Range {
	readonly from: DateStamp;
	readonly to: DateStamp;
	readonly days: number; // UTC days in [from, to]
	readonly asked: number; // the preset's length
}
/** to = through; from = the later of first and through - (asked - 1). */
export function windowRange(asked: number, through: DateStamp, first: DateStamp): Range;
/** 'window': windowRange(preset, through, the query's ledger's first); 'newest-day': from = to = through;
 *  'widest': windowRange(max(console.window_presets), through, first). A ledger whose reach is not
 *  `ok` answers with that reach, and no slice is asked. */
export function rangeFor(query: PanelQuery, preset: number, reach: RouteReach): Range | LedgerReach;
/** One slice per query name and range. A new range replaces the held promise; nothing else is kept.
 *  The only caller of `slice(` in the console. */
export function sliceOnce(query: PanelQuery, range: Range): Promise<SliceResult>;

export type RouteState = 'loading' | 'ok' | 'quiet' | 'missing' | 'unreachable';
/** The route line's state: `loading` while any answer is pending; else `unreachable` if any is;
 *  else `missing` if any is; else `quiet` if every answer is; else `ok`. The counts feed the
 *  route line's sentence (section 2.4 step 4). */
export function tallyAsks(answers: readonly (SliceResult | LedgerReach | 'pending')[]): {
	readonly state: RouteState;
	readonly missing: number;
	readonly unreachable: number;
};
```

- **Names.** A query is exported as `<panelIdInCamelCase>Query`, and its `name` is that identifier. A query two panels share is named for what it asks (`failedRuleQuery`).
- **The window is anchored on the data, not the clock.** `to` is `RouteReach.through`; each query's `from` is clamped to its own ledger's `first`, from [`ledgerReach()`](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md#how-far-a-ledger-reaches). One query a preset: a narrower preset is a new ask, and the door's cache serves its files.
- **A reach that did not arrive names no day**, as [the query-reader contract](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md#how-far-a-ledger-reaches) declares. A slice's `unreachable` names the first day it could not answer; a reach asks for no day, so its `unreachable` carries none, and any day the console printed for it would be made up. So nothing reads or prints a day from an unreachable reach: each of that ledger's panels answers `unreachable` with no slice asked, its box prints `Did not arrive.`, the route line counts it with the rest (section 2.4 step 4), and the door's own browser-console line says why. The retry asks the reach again: a fetch that failed is fetched again, and an index this build will not act on stays `unreachable` until the page is reloaded.
- **A panel that does not follow the window** asks `span: 'newest-day'`, or `span: 'widest'` (`model-change` only), and names the day, run or change it drew. **The newest run** is the run of the newest day whose `run_id` carries the largest number after its date. Section 2.7's `Window` column says which.
- **Two ledgers meet by day or by `url_key`, never on `item_id` or `run_id`.** `scores` meets `item-health` by `date` or by `url_key`; a `url_key` with two score rows takes the later one. `item-health` meets `host-fingerprint` on `(date, run_id, job, shard)`, the whole of `HOST_FINGERPRINT_KEY`, and an empty item `job` reads as `work`, the way `console_band.py` reads an empty host `job`. A row with no match is counted and printed, never dropped.
- **Rates.** `itemRates` moves from `frontend/src/lib/server/model-work.ts` to `frontend/src/lib/console/rates.ts`, and `model-work.ts` imports it back until its last caller moves. A row qualifies when `prefill_ms`, `input_tokens`, `cached_tokens`, `decode_ms` and `output_tokens` are all filled and `input_tokens - cached_tokens` and `output_tokens` are above zero. **The reference machine** is the window's `cpu_model` with the most qualifying rows, ties by name. **The typical article** reads the window's median `input_tokens - cached_tokens` and writes its median `output_tokens`; its seconds on a day are those two counts priced at that day's median milliseconds per token on the reference machine. `slower-on-same-work`, `slower-machines`, `model-throughput` and `model-change` all use this module.
- **Medians and percentiles are nearest-rank** - an actual value, never an average of two - as `at()` in `frontend/src/lib/console/eval-instruments.ts` computes them.
- **The column registry follows the declarations.** Every column a declared query names is listed in `COLUMN_READERS` under the module that declares it - `shared`, then `pipelines`, `model`, `machine`, `voices` when two declare it - and leaves `UNREAD_CELLS`. The same for `host-fingerprint`. The comment above `COLUMN_READERS` gains: a declared panel query counts as a reader. Row 4 declares and registers `platformMixQuery` from the shipped machine-mix query; after row 4 no route row edits a registry.
- **Two checks.** `backend/tests/contracts/test_panel_queries.py` reads each `columns: [...]` literal under `frontend/src/lib/console/queries/` and fails on a ledger not in `LedgerConfig.published`, a column the ledger's Pydantic row lacks, or a column in `UNREAD_CELLS`. `frontend/tests/console-drawn-cells.spec.ts` (logic group) holds that text which came from the web - `scores.title`, `scores.source_url`, `item-health.canonical_url`, `item-health.detail` - reaches a console page only as text (Guardrail #11). It reads every `.ts` and `.svelte` file under `frontend/src/lib/console/`, `frontend/src/lib/charts/`, `frontend/src/lib/components/` and `frontend/src/routes/console/`, and fails on `{@html`, `bind:innerHTML`, `.innerHTML =`, `.outerHTML =`, `insertAdjacentHTML(`, `document.write(`, `srcdoc` or `.html(`; on an `href`, `src`, `srcset`, `action`, `formaction` or `xlink:href` whose value holds a `{...}` other than a leading `{base}`, unless the spec's `ADDRESS_ALLOWED` list names the file, the attribute and where its value comes from; and on `fetch(`, `sendBeacon(` or `window.open(`, because only the door fetches. The worker records what it matches on the day it lands.
- **The canary is packed.** After the canary's raw rows are written, `backend/utilities/build_canary_day.py` packs `item-health`, `scores` and `host-fingerprint` for every canary day with `persist_period()` from `backend/idhazh/ledger/` and writes both indexes, the way `tests/fixtures/ledger-door/` was built, and `frontend/scripts/build-canary.mjs` copies them where the site serves them. The canary carries every declared column, with at least one row per state a panel distinguishes: a `length` finish, a `429`, a `network_error`, a watchlist hit, an inferred `time_source`, a negative `stage_gap_ms`, a `span_integrity` of false, an empty item `job`, and a day with `item-health` rows and no `host-fingerprint` rows. So no route row edits the canary.
- **Recorded slices.** `tests/fixtures/console/<route>/<queryName>.json` holds `sliceFromDisk()`'s answer over the packed canary for each exported query at the canary's default range. `frontend/tests/recorded-slices.spec.ts` (logic group) recomputes each one and fails on a difference; `IDHAZH_RECORD_SLICES=1` rewrites them. A panel's pure-module test reads its files inside the test (CLAUDE.md section 13).
- **The browser fixture.** `frontend/tests/support/door-page.ts` reuses `test` and `expect` from the shipped `frontend/tests/support/browser.ts` fixture, which serves the worker's add-on requests from the shared cache. Follow [the frontend setup and cache rules](../docs/how-to/run-the-gates.md#the-frontend-gates): `npm run setup:duckdb` prepares the cache before tests; global setup only checks it and fails with the setup command when it is absent. No test downloads an add-on. HTTP-cache tests keep their local add-on host because Playwright routing disables the browser's HTTP cache.
- **A moved route** is one whose page files or `frontend/src/lib/console/<route>/` import `$lib/console/queries/`. A spec opens that route when it quotes the route's address or imports `console-expect`, `console-panels` or `panel-drivers`, and then must import `test` from `door-page`: `console-route-scope.spec.ts` refuses it otherwise. Row 4 switches the seventeen cross-route specs and both panels specs to that `test`; each route row switches its own specs.

### 2.4 How a panel loads and draws

| # | Step | Rule |
| --- | --- | --- |
| 0 | The route's frame | `RouteStatus.svelte` (row 4) is each data route's outer element, so its one `data-shimmer` reaches every box. In order it holds: the route's `WindowControlSource`; the route line, `<p data-console-standing>`, one sentence and, when something did not arrive, one `<button data-console-retry>` labelled `Fetch the record again`, which re-asks only what did not arrive; the said-once sentences that need no ledger read (Pipelines' carry line, Hardware's intro, and step 7's sentence); the panel groups in `panel_groups` order. **Attributes**: `data-console-panels="<route id>"`; `data-route-state` from `tallyAsks()` (section 2.3), `loading` in the built page; `data-shimmer` `on` once `loading` has lasted `console.shimmer_after_ms`, else `off`. Specs wait on `data-route-state` leaving `loading`. **The route line keeps `min-block-size: calc(var(--route-line-reserve) * var(--leading-sm))` in every state**, so nothing below it moves when its sentence changes; `console-waiting.spec.ts` fails a sentence taller than the reserve at any width. Settled at `ok`, the line says what the panels were drawn from: `The panels below reach 26 Sep.` |
| 1 | First frame | The panel draws its reserved box: `Reserved.svelte` at `console.chart_height` for a chart, its row cap times its row pitch for a list, its label with an empty value for a card. **Never a dash, a zero or a sentence while waiting**, because each is an answer. The box stays still until the route's shimmer starts. No spinner and no timer per panel. A list that settles shorter than its cap shrinks once |
| 2 | Order | Panels query as they mount, in page order, so the verdict is asked first. No panel waits to be scrolled into view, and no panel moves up because its data arrives sooner |
| 3 | Range | Section 2.3's window rule |
| 4 | Said once, named in every box | Every door panel's box in a settled nothing names which, with `STATE_WORDS` in `waiting.ts` - `quiet` `Nothing recorded.`, `missing` `Not published yet.`, `unreachable` `Did not arrive.` - drawn only by `EmptyState.svelte` and `Reserved.svelte`, which every door panel uses for its nothings, kept ones included; only `unreachable` is tinted. A build-time panel keeps its own two nothing sentences, and its nothings spec checks they differ (section 2.2). A wait prints no word. `too-few` always prints its own sentence: `Only 12 of the 20 articles this chart needs are in these 30 days, so it is not drawn.` The route line says the worst state once: `Nothing was recorded in these 30 days.` (quiet); `4 panels read a record this site has not published yet, so they have nothing to draw.` (missing); `Part of the record did not arrive, so 6 panels have nothing to draw.` (unreachable). When the shimmer starts the line says `Fetching the record. After each site update the first visit also downloads the N MB program that reads it.`, where N is `__QUERY_ENGINE_BYTES__`: the compressed bytes the site sends for the engine plus its parquet add-on, measured by the build. With scripts off, the layout's existing `<noscript>` line says `Panels drawn from the published record need JavaScript; with it off they keep their shape and stay empty.` |
| 5 | Nothing happened | A window with rows in which nothing fired is **loaded**, never `quiet`: it draws and prints its nothing-fired sentence from section 2.7b. `quiet` means only a window with no rows |
| 6 | Draw | Rows go to a pure function in the panel's own `frontend/src/lib/console/<route>/<panel-id>.ts` returning the type's input; the type returns geometry; the component draws. No aggregation in a `.svelte` file |
| 7 | Settings line | A date series passes `rule: ModelRule` from `settingsRules()` (section 2.6), or `{declined: <reason>}` with the reason in its `Rule` cell. The route says once, in the frame (step 0), what the line can see |
| 8 | Freshness | `WindowStatus.svelte` (row 4) says `Showing {days} days, to {through}.` and, only while the record is shorter than the preset, `The record starts on {first}; the {asked}-day window fills on {first + asked - 1}.` A panel whose ledger starts later than the route's earliest `first` adds `Recorded from {first}.` to its note. **A panel that mixes build-time data with the door says where the door's rows stop** |
| 9 | Cells | A drawn cell is text, escaped by Svelte. It never becomes markup, a link or an address to fetch, and `console-drawn-cells.spec.ts` (section 2.3) checks it |

In every sentence above and in section 2.7b, `30` stands for the window's `days`, `90` for its `asked`, a date for the date it names, and a counted number for the count.

**The built page.** Every data route (Pipelines, Summaries, Voices and Hardware) follows this rule once its route row lands. A **door panel** is any panel with a declared query; `feeds-failed` is one.

- **The prerendered document may carry**: the layout; every panel's title, note and gate attributes; each door panel's first frame (step 1); each build-time panel (section 2.8), drawn in full; the said-once sentences; `WindowStatus`'s sentence for a page with no script yet; and, in the page data, build-time inputs and config values.
- **It may not carry** any value read from `item-health`, `scores` or `host-fingerprint` - in a door panel, in the route line or in the page data - nor any day of the record's reach.
- **What arrives later, and where**: a door panel's marks, lede, readout and state word, inside its box; the route line's sentence and retry, inside its reserve; the reach, inside `WindowStatus`'s two lines. Nothing above the first panel moves, at 390 and 1440 px.
- **The check.** `frontend/tests/console-built-page.spec.ts` (row 4) reads `console-expect/console-built-page/<route>.ts`, which each route row writes as `EXPECT: { doorPanels: Record<string, string>; pageData: readonly string[] }`, typed out. With `javaScriptEnabled: false` at the route's address: `[data-console-panels="<route>"]` has `data-route-state="loading"` and `data-shimmer="off"`, and its `[data-console-standing]` text is empty; for each id in `doorPanels`, the panel's `.panel-body` holds no `svg` except `[data-reserved-frame]`, and its text, whitespace collapsed, equals `doorPanels[id]` - empty for a reserved chart or list, the fixed words for the rest; and the keys of the route's page data in its `__data.json` (the last node's first entry) equal `pageData`. Bite (row 6): a canary figure in `failure-mix`'s first frame fails it.

**Colour.** A colour stop belongs to the name of a quantity. `frontend/src/lib/console/series-tokens.ts` (row 2) maps each name below to one stop, and a plot asks for a stop by name, never by position. Inside one plot no two names share a stop; across plots one stop may carry two names. A plot with one unnamed quantity draws in `--chart-1`. `--chart-8` is only for what no step claims.

| # | Quantity | Token | Routes |
| --- | --- | --- | --- |
| 1 | fetch; a failed-fetch tile | `--chart-1` | Pipelines, Hardware, Voices |
| 2 | extract | `--chart-2` | Pipelines, Hardware |
| 3 | summarize, or model time not split into calls | `--chart-3` | Pipelines, Hardware |
| 4 | label call | `--chart-4` | Pipelines, Hardware |
| 5 | summary call | `--chart-5` | Pipelines, Hardware, Summaries |
| 6 | visual plan | `--chart-6` | Pipelines |
| 7 | checking | `--chart-7` | Pipelines, Hardware, Summaries |
| 8 | unattributed, other, never fetched, not recorded, never checked, the rest of a fetch, other memory | `--chart-8` | all |
| 9 | queue wait | no fill: a 1 px `--chart-axis` line before the first step | Pipelines |
| 10 | reading a prompt; writing a reply | `--chart-6`; `--chart-7` | Pipelines, Hardware |
| 11 | done by then, in a histogram | `--chart-3` | Pipelines, Summaries |
| 12 | the model server's memory; our worker's memory | `--chart-1`; `--chart-3` | Hardware |
| 13 | free memory | no fill: the empty track | Hardware |
| 14 | robots check | `--chart-3` | Pipelines, Voices |
| 15 | waiting for headers; retries; connecting | `--chart-2`; `--chart-4`; `--chart-5` | Voices |
| 16 | authority; recency; lens; watchlist, and a watchlist day; carriage | `--chart-1`; `--chart-2`; `--chart-4`; `--chart-5`; `--chart-7` | Voices |
| 17 | cut off at the length limit; any other ending; ended on its own | `--chart-4`; `--chart-2`; the `--chart-axis` ground | Summaries |
| 18 | numbers not in the article; does not match; opening left out; "maybe" as fact | `--chart-1`; `--chart-2`; `--chart-4`; `--chart-5` | Summaries |
| 19 | a machine | its stop by key, from `machine-colour.ts` | Hardware |
| 20 | a spread behind its middle mark | its series' stop at `--chart-spread-mix` | Summaries, Hardware |

**The lede** is words larger than any other word in its panel (gate 3): `--text-xl` unless section 2.7b marks it, and where the panel already has figures, one step above the largest - `--text-2xl` above `--text-xl` figures, and `--text-3xl` above a `KpiCard`'s `--text-2xl`, through its `lede` prop. Finding sentences and `source-health`'s headline move from `--text-lg` to `--text-xl`.

### 2.5 The chart types, made ready for a route (row 2)

**No new type.** The vocabulary page already defines a range mark as a row of a ranked list, and a second target bar would draw one mark two ways. **Row 2 moves no pixel**: a prop a caller does not pass today is optional, and the route rows pass it.

| # | Type or component | Change | Drawn by |
| --- | --- | --- | --- |
| 1 | `rankedList` | `(rows: readonly {label: string; value: number; context?: string; status?: string; segments?: readonly {label: string; value: number; token: string}[]; range?: {high: number; count: number}; ends?: {end: number}}[], opts: {max?: number; order?: 'largest-first' \| 'smallest-first'; minCount?: number; rules?: readonly {at: number; label: string}[]; tail?: string}) => RankedGeometry \| null`. A row carries at most one of `segments`, `range` and `ends`, refused by name. The divisor is the largest `value`, `high`, `end` or rule, so nothing is clipped. `minCount` is required once a row carries `range`; a row under it draws no mark, prints `Too few: 12 of the 20 articles a row needs.`, and ranks after every drawn row. `status` is the word pill (`disagrees`, `on the floor`). A rule is a dashed upright carrying its name, drawn as `Distribution.svelte` draws one | `RankedList.svelte`, taking `RankedGeometry`. The range mark (fill to `value`, notch at `high`) and the two-named-ends mark (fill to `value`, notch at `end`) move here from the markup `ShardBoard.svelte` and `MemoryBoard.svelte` use; `rangeMark` moves here from `frontend/src/lib/charts/machine.ts`, not copied. Its importers - `BandDistance.svelte`, `FailureList.svelte`, `routes/console/model/+page.svelte` - move to the geometry prop |
| 2 | `dateSeries` | `opts.rule: ModelRule` (section 2.6), required. `opts.rules?: readonly {at: number; label: string}[]`, a dashed horizontal line carrying its name. `opts.domain?: [number, number]`. Each point may carry `spread?: {low: number; high: number}` | `DateSeries.svelte` writes `data-model-rule` from `rule`, so the attribute and the drawing cannot disagree: `yes` for `changes`; `no`, with `data-model-rule-none`, for `declined`, refused under five words. A change is a 1 px vertical in `--color-text-tertiary` carrying `data-model-rule-line`, **dashed for `settings` and dotted for `checker`**, on the boundary between its day's column and the one before; a date with both draws the dashed line and its readout prints both rows. Its words reach the strip through `ReadoutInput.events` at that column, never on the plot. `note` prints under the plot as `data-model-rule-empty` when `changes` is empty, else as `data-model-rule-note`. A spread is drawn behind its line in the series' stop mixed with the page surface at `--chart-spread-mix` |
| 3 | `distribution` | `opts.scale: 'linear' \| 'log'`, required. `opts.domain?: [number, number]`. `opts.rules?: readonly {at: number; label: string}[]`. `TimeHistogram.svelte`, which kept panels on two routes draw, gains the same optional `domain` | `Distribution.svelte`. A panel with two charts or small multiples passes one domain to each, so two halves are drawn on one scale. A window that spans a setting change says in its note: `This window spans a setting change on 12 Sep; both sides are drawn together.` |
| 4 | `tileStrip` | A tile is never narrower than `console.tile_min_px`. Where a window holds more days than fit, the strip draws the newest days that fit and one line under it counts the rest: `63 earlier days: 2 fired, 58 quiet, 3 not recorded.` The strip prints its first and last day under it in `dayTicks`' words, once under the last strip when strips share an axis | `TileStrip.svelte` |
| 5 | `partsOfOne` | Each part takes its token from `series-tokens.ts` by name, never by position | `PartsOfOne.svelte` |
| 6 | every type | Declares its readout under [the shared chart and readout rules](../docs/concepts/console-design/the-rules-every-console-chart-obeys.md) - `readoutOf` for `dateSeries`, `distribution` and `tileStrip`, `factsOf` for the rest - and its `data-readout-*` attribute, and carries `data-chart-type` on its marks. `TileStrip.svelte` and `PartsOfOne.svelte` lose `title=`; `DateSeries`, `Distribution`, `Flow` and `PairedScatter` lose their SVG `<title>` | each component |
| 7 | the target bar | `frontend/src/lib/components/TargetBar.svelte` is already markup and stays. `targetBar()` and the `echarts` type import leave `frontend/src/lib/charts/targetbar.ts`; `vocabulary.spec.ts` and `console-ranked.spec.ts` move onto `targetGeometry`, which returns the same band | - |
| 8 | `KpiCard.svelte` | Gains `lede?: boolean` (its figure at `--text-3xl`) and `rule?: ModelRule`. Given `rule`, it draws the settings line instead of its own model-change line; without it, it draws what it draws today until row 11 | - |
| 9 | `FailureList.svelte` | Gains `stages?: {options: readonly string[]; chosen: string}`: a radio group of stages above the list, which a keyboard reaches; the list ranks `failed_rule` for the chosen stage. Without it, the list draws what it draws today until row 11 | - |
| 10 | `series-tokens.ts` | The colour table of section 2.4, and dark `--chart-6` re-tuned (section 2.9), because today it sits 2.3 apart from `--chart-3` on CIEDE2000, a measure of how different two colours look, and `item-time-split` and `run-timeline` draw both | - |

### 2.6 The settings line and the checker line (row 5)

**The band carries both, read from the run manifests and from `state/scores`, over `max(console.window_presets)` days (the span), plus the newest recorded day before it** (owner ruling R3, default B1). The band already reads the manifests and is fetched by every route.

**Fields on `ConsoleBand`** (`backend/idhazh/contracts/console_band.py`), both additive and both nullable - null means the band did not compute it, and the chart draws the declined rule:

```python
#: A setting's name, never its value: a PipelineInputs field, or sampling.<key> /
#: runtime_flags.<key>. A lookup key: the page prints its words, never the name.
InputName = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[A-Za-z0-9_-]+)?$", max_length=64)
]

class SettingsMove(Model):
    date: DateStamp                                # the UTC day the move was seen
    inputs: list[InputName] = Field(min_length=1)  # distinct; field order, then a block's keys in code-point order

class BandSettingsMoved(Model):
    compared_from: DateStamp | None                # the first UTC day of the span a change can be drawn on
    changes: list[SettingsMove] = Field(default_factory=list)
    # refuses: dates not strictly ascending, a date before compared_from, any change when it is None

class CheckerMove(Model):
    date: DateStamp
    score_moved: bool                              # the part that computes the faithfulness number moved

class BandCheckerMoved(Model):                     # the same validator as BandSettingsMoved
    compared_from: DateStamp | None
    changes: list[CheckerMove] = Field(default_factory=list)

settings_moved: BandSettingsMoved | None = None
checker_moved: BandCheckerMoved | None = None
```

**The settings rule** is a pure function in `backend/idhazh/telemetry/publish/settings_moved.py`; `publish()` does the reads, and they are bounded - the span plus at most `max(console.window_presets)` days before it, never the whole ledger (Guardrail #12).

1. T is the band's anchor day and S = T - (widest - 1), where widest is `max(console.window_presets)`. Read each `run.json` in [S, T] with `RunManifest.read`. Then walk back from S - 1, at most widest days, to the first day that has a run whose `inputs` is not null; call it E.
2. A recorded day is a day with at least one run that has inputs. Flatten each such run: every `PipelineInputs` field is one name; `sampling` and `runtime_flags` give one name per key, `<field>.<key>`, after the manifest reader has applied `RENAMED_FLAGS` and `SPLIT_FLAGS` from `backend/idhazh/contracts/fingerprint.py`; a value that is null or empty is dropped. A day's values for a name are the set of values across its runs.
3. Oldest first: a name moved on day D when D holds a value missing from the newest earlier recorded day on which that name held a value. A name with no earlier value has not moved. So a switch reverted the next day draws a second line on the revert day, and a day whose runs used two values holds both, so a later day that uses either draws no line.
4. One `SettingsMove` for each day in [S, T] with a moved name.
5. `compared_from` is S when E exists; otherwise the day after the oldest recorded day in [S, T]; otherwise null.

**The checker rule**, in the same module:

1. The same S, T and walk-back, over `state/scores`, through the reader `day_metrics.read_score_rows` uses. A day's set is its `scorer_version` values.
2. strip(v): split on `;`, drop the parts that start with `metrics-`, `bands=` or `lead=`, and join the rest again.
3. D is a checker change when it holds a version missing from the newest earlier day's set. `score_moved` is true when D holds a stripped version missing from that day's stripped set. Whole strings are compared: a part that appears or goes away counts.
4. `compared_from` follows settings step 5.

**One rule in two languages.** `frontend/src/lib/console/settings-moved.ts` gains `inputsMoved(days, first)`, the same rule over the published manifests, returning the `settingsMoved` shape; `settingsMoved()` becomes `inputsMoved` plus words, so Hardware's two callers keep working until row 9. Both languages assert `tests/fixtures/settings-moved/five-on-one-day.expected.json`, and `five-on-one-day.json` gains a day whose two runs differ. Row 11 deletes `settingsMoved`, `inputsMoved` and the TypeScript half of that test.

**What a chart receives.** Row 2 declares the two types in `frontend/src/lib/charts/d3/model-rule.ts`; row 5 adds `settingsRules()` to `settings-moved.ts`:

```ts
export interface RuleChange {
	readonly date: DateStamp;
	readonly kind: 'settings' | 'checker'; // drawn dashed / dotted
	readonly words: string; // the readout value at that column
}
export type ModelRule =
	| { readonly changes: readonly RuleChange[]; readonly note: string | null }
	| { readonly declined: string };

export function settingsRules(
	shell: ConsoleShell,
	window: { from: DateStamp; to: DateStamp },
	checker: 'none' | 'score' | 'every'
): ModelRule;
```

- `changes` holds only dates in [from, to], ascending; on a shared date the settings change comes first.
- `faithfulness` passes `'score'`; `doubt-reasons` and the `not sure` card pass `'every'`; every other chart passes `'none'`.
- A name with no entry in `SETTING_WORDS` prints as `a recorded setting`.
- `readBand` in `band.ts` maps the two fields to `settingsMoved` and `checkerMoved` on `ConsoleShell`, beside `months`, and reads an absent or malformed value as `null`; `BAND_UNREAD` carries `null`.

**The sentences** (the window's length is printed where `30` stands, and the dates are examples):

| Case | Sentence |
| --- | --- |
| A settings readout row | `How summaries are written` / `the prompt and the context size changed on this day`, worded by `modelRuleRow` over `namesMovedShort` |
| A checker readout row, score moved | `How summaries are checked` / `the faithfulness scorer changed on this day` |
| A checker readout row, score not moved | `How summaries are checked` / `the checker changed on this day; the faithfulness score did not` |
| Nothing moved in the window | `Nothing changed about how the summaries are written inside these 30 days.` On a chart that also draws the checker line: `Nothing changed about how the summaries are written or checked inside these 30 days.` |
| The window starts before a kind's `compared_from` | `This chart can mark a change in how the summaries are written only from 13 Sep on.` or `This chart can mark a change in the checker only from 23 Aug on.`, each adding `None came after that day.` when no change of its kind is drawn |
| A kind's `compared_from` is null | `How the summaries are written was not recorded on these days, so this chart cannot mark a change.` (`checked` for the checker) |
| The band's field is null | `The record of changes did not arrive with this page, so this chart cannot mark one.` |
| Once per route, in the frame | `A dashed line marks a day a recorded setting changed: the model, its settings, the prompt, the chat template, the runtime or the weights file.` Summaries adds `A dotted line marks a day the checker changed.` |

**Keep names, never values** (Carmack): a change lists the names that moved, not their values.

**The band's ceiling.** `page_weight.payload_ceilings_bytes."console/band.json"` in `config/idhazh.json` is crossed by the new fields. Row 5 sets it from the built band at twice its compressed size, in the same commit, following the [published-ledger ceiling practice](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door). The band is inlined into every prerendered console document, so each grows by the same amount.

**Version, changelog, read side** (Fowler). `version` is the UTC day the row merges, or `YYYY-MM-DDTHH:MM` if the band already changed that day. The new entry goes on top; the 2026-09-23, 09-19 and 09-12 entries stay; the 2026-09-09 entry becomes `Earlier changes are in this file's git history.` The entry's `change` is `Adds settings_moved and checker_moved: days a setting or the checker moved.` and its `why` is `Item-health cannot see the prompt or the checker; the run record and scores can.` The change only adds fields, so no migration; a test shows the fixture without either key validates to `None`, as `test_console_payloads_producer.py` does for `covers_through`. `newest-day.json` is regenerated. A new field-set test binds `band.ts`'s fields to `ConsoleBand`, in the style of `test_served_day.py`.

**The line replaces each kept chart's own model-change mark**: the step on `ThroughputTrend.svelte` and the line on `KpiCard` (Susan). **The reader loses** the unnamed lines the old settings digest draws between 23 August and 10 September, which all leave the 90-day view by 9 December.

### 2.7 The panels, route by route

Susan's verdict numbers (2026-09-26) are kept. **KEEP means the question and the drawing stay** (section 2.1 property 3). `Data after` names every column the panel's query asks, and nothing else. `Window`: `follows` the route's window, or `newest run`, `newest day` or `the change` (section 2.3). `Rule`: the settings line's declaration, and for `no` its reason. A `Type` of `as it is` keeps the component named. "Build-time" means section 2.8. What each panel says - its lede, its comparison and its nothing-fired sentence - is section 2.7b.

#### Pipelines (`/console/`), row 6 - one untitled group, in this order

| Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- |
| 1 KEEP | `at-a-glance` | At a glance | build-time: `publishedCharts`, `dayMetrics` | the two cards as they are, the first with `lede` | no - counts of what published | follows |
| 1 KEEP | `run-health` | Run health | build-time: `loadManifests`, `dayMetrics` | `RunYield` and `RunSquares` as they are | no - planned against published | follows |
| 1 KEEP | `site-cost-per-item` | What one more article costs | build-time: `publishedItems`, `loadManifests` | `dateSeries`, bars, one rule at the window's median bytes an article | yes - a `run_visual_decision` change moves the bytes an article costs | follows |
| 2 REDRAW | `failure-mix` | What is failing, by stage | `item-health`: `date`, `stage`, `outcome`, `code`, `failed_rule`; the list is `failedRuleQuery` in `queries/shared.ts` | `dateSeries` stacked by stage, `data-comparison="composition"` with its rationale line; below it `FailureList.svelte` with `stages` (section 2.5), the stage that failed most chosen at rest, capped at `console.failure_list_max` | yes | follows |
| 1 KEEP | `item-time-split` | Where an item's time went | `item-health`: `date`, `item_total_ms`, `fetch_ms`, `extract_ms`, `summarize_ms`, `label_ms`, `summary_ms`, `visual_plan_ms`, `faithfulness_ms`, `stage_gap_ms` | `dateSeries` stacked, each part in its `series-tokens.ts` stop | yes | follows |
| 3 REPLACE | `slower-on-same-work` (was `throughput-viewport`) | Whether a run is getting slower on the same work | `item-health`: `date`, `cpu_model`, `prefill_ms`, `input_tokens`, `cached_tokens`, `decode_ms`, `output_tokens` | `dateSeries`, one point a day: the typical article's seconds on the reference machine (section 2.3, "Rates"), named under the axis; one rule at the window's median | yes | follows |
| 1 KEEP | `stage-timings` | Time per item by stage | `item-health`: `date`, `fetch_ms`, `extract_ms`, `summarize_ms` | `StageTimings.svelte` as it is, with the settings line | yes | follows |
| 1 KEEP | `item-cost` | What one item cost the model | `item-health`: `date`, `prefill_ms`, `decode_ms`, `input_tokens`, `output_tokens`, `cached_tokens`, `label_input_tokens`, `label_cached_tokens` | two `TimeHistogram.svelte` charts as they are, reading then writing, on one domain, in their `series-tokens.ts` stops (one panel, not two) | no - one distribution of the window | follows |
| 4 DELETE | `prompt-memory` | - | - | - | **The reader loses**, on the route they land on, the share of each prompt already in memory printed beside the reading cost it explains, and the count of items read whole. Hardware's `prompt-reuse` answers it one tab away, linked from `item-cost`'s note. Its note - the share follows article length - moves into the design rationale of the Hardware drawing page | - |
| 1 KEEP | `run-timeline` | Where the run's time went, on the run's own clock | `item-health`: `run_id`, `item_id`, `source_id`, `shard`, `item_index`, `item_started_at`, `item_ended_at`, `queue_wait_ms`, `fetch_ms`, `robots_ms`, `extract_ms`, `label_ms`, `summary_ms`, `visual_plan_ms`, `faithfulness_ms`, `stage_gap_ms`, `item_total_ms`. `start_offset_ms` and `residual_ms` are computed in the panel's module as `backend/idhazh/telemetry/publish/run_timeline.py` computes them today. **The span sub-steps go** (`tag`, `render_prompt`, `parse_reply`); `robots_ms` from the row replaces the span's `robots` | `RunTimelinePanel.svelte` as it is. The overrun ("time counted twice") is a 2 px solid rule in `--color-text-tertiary`, unlike the no-reading hatch | no - one run on its own clock | newest run |
| 1 KEEP | `chart-drawing` | Visuals drawn for articles | build-time: `dayMetrics`, `chartFlow` | `flow` (`Flow.svelte`) and its day table | no - counts of what was drawn | follows |
| 5 REDRAW | `extraction` | What the extractor found | `item-health`: `date`, `stage`, `outcome`, `code`, `url_key`, `element_class`, `span_integrity`, `elements_found`; `scores`: `date`, `url_key`, `extraction_suspect`; build-time: `dayMetrics` for the share published without a chart and the yield trend, because no ledger records whether a published article carries a chart | figure cards; a `rankedList` of element classes plus one row `would not re-slice`, counting rows whose `span_integrity` is false; the yield trend a `dateSeries` from the build-time part. The flagged share, `not_prose` and `contaminated` count distinct `url_key`s, published or not, and the note says the count now includes articles that were not published. Carries `data-eval-panel="extraction"` (row 1) | yes, on the trend | follows |
| 23 NEW | `article-age` | How old an article was when we published it | `item-health`: `published_at`, `time_source`, `item_started_at`, `outcome` | `distribution`, `scale: 'log'`, hours from publication to our run, rules at the median and at 24 hours, named `one day`. **Stated times only**: an inferred time is the hour we first saw the address, so it reads younger than it is | no - one distribution of the window | follows |

**Panels 19 and 20 moved to Voices** (Jony): they explain the ranker, which is not Pipelines' question. **Panning leaves with panel 3**: `Viewport.svelte`'s pan buttons and its Left, Right, Plus and Minus keys go, and `console.pan_days` stops being read. **The reader loses** an earlier span of the same width and the keys that stepped the window.

#### Summaries (`/console/model/`), row 7 - one untitled group, in this order

| Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- |
| 12 KEEP | `model-cards` | What the model did | build-time: `state/day-metrics/` through `modelWork` and `buildCardTrends`, because the three distinct counts cannot be rebuilt from the ledgers - they disagreed with `day-metrics` on 11 of 35 days. Today's intro is its note. A disclosure `The days behind the cards` under the cards holds the daily table and carries `data-eval-panel="daily-figures"`; `daily-figures` is not a panel id | `KpiCard` as it is, the first card with `lede`; the twelfth card is `determinism_violation` | yes, the settings line replacing the card's own line; the `not sure` card also draws every checker change | follows |
| 12 KEEP | `model-throughput` | Model tokens per second | `item-health`: `date`, `run_id`, `model_id`, `prefill_ms`, `decode_ms`, `input_tokens`, `cached_tokens`, `output_tokens` | `ThroughputTrend.svelte` as it is, its step replaced by the settings line, one rule at the window's median | yes | follows |
| 24 NEW | `call-ending` | How a model call ended | `item-health`: `date`, `summary_finish_reason`, `label_finish_reason` | `dateSeries` stacked, one mark a call, `length` at the bottom, then the other reasons by count; an empty reason is skipped | yes | follows |
| 25 NEW | `refusing-rule` | Which rule refused a reply | `failedRuleQuery` from `queries/shared.ts` | `FailureList.svelte` with `stages` set to the model's stages, the divisor printed, capped at `console.failure_list_max` - the same query and component as `failure-mix`'s list, so two routes cannot print two counts for one rule | no - a ranking of the window | follows |
| 12 KEEP | `doubt-reasons` | Why a summary was doubted | build-time: `reasonDays` over the digest day files | `dateSeries` stacked | yes, and every checker change | follows |
| 12 KEEP | `faithfulness` | Summary faithfulness, day by day | `scores`: `date`, `hhem`, `hhem_delta` | `dateSeries`, the median as the line and the quartiles as its `spread`. The link `How each of these measures is scored` stays beside the heading; it is not a panel | yes, and each checker change whose `score_moved` is true | follows |
| 12 KEEP | `source-doubts` | Which sources the checker doubts | `scores`: `date`, `url_key`, `band`, `unsupported_numbers`, `hedge_dropped`, `evidential_density`, `speculative_density`; `item-health`: `url_key`, `source_id` | `RankedList.svelte`, one rule at all sources' doubted share; the two densities are figures on each row, never segments | no - a ranking of the window | follows |
| 12 KEEP | `write-cost` | What one summary cost | `item-health`: `date`, `summarize_ms` | `TimeHistogram.svelte` as it is | no - one distribution of the window | follows |
| 12 KEEP | `score-cost` | What checking one summary cost | `scores`: `date`, `score_ms` | `TimeHistogram.svelte` as it is | no - one distribution of the window | follows |
| 12 KEEP | `summary-length` | How long summaries came out | `scores`: `date`, `run_id`, `model_id`, `summary_word_count`, `source_word_count`, `source_seen_word_count`, `compression` | `RunLengths.svelte` as it is, one row a run; the run's median `compression` printed on its row | yes | follows |
| 12 KEEP | `model-change` | What the model change moved | `scores`: `date`, `model_id`, `summary_word_count`, `source_word_count`, `source_seen_word_count`, `extractiveness`, `verbatim_run`, `band`, `unsupported_numbers`, `hedge_dropped`; `item-health`: `date`, `summarize_ms`, `prefill_ms`, `decode_ms`, `input_tokens`, `cached_tokens`, `output_tokens`. Each side is split at the change date; nothing is joined | `SwapDots.svelte` as it is | no - it is the change itself | the change: `span: 'widest'`; the change is the newest date whose set of `scores.model_id` values differs from the scored date before it |
| 13 REPLACE | `recorded-only` | - | - | - | **Deleted as a panel.** Its eight instruments go where section 2.7a puts them. **The reader loses** the one place listing unwired instruments, and each instrument's quietest, middle and loudest day side by side; `eval-instruments.ts` keeps the list, and its test fails on an instrument in no panel | - |

**Route sentences.** The four `data-recording` sentences become the route's said-once sentences in the frame, as on Hardware.

#### 2.7a Where the eight unwired instruments go

Each keeps the `label` and `note` it has in `frontend/src/lib/console/eval-instruments.ts`, and gets no threshold, no tint, no good or bad direction and no worst-value marker. A panel that takes one says once: `Nothing acts on these numbers.`

| Instrument | What it measures | Goes to | Drawn as |
| --- | --- | --- | --- |
| `compression` | summary length over article length | `summary-length` | the run's median percent on that run's row; no mark of its own |
| `self_repetition` | how often the summary repeats its own four-word runs | the `daily-figures` disclosure | a column, the day's median percent, next to `coherence` |
| `coherence` | how well each summary sentence follows the one before | the `daily-figures` disclosure | a column, the day's median to two decimal places; read against `self_repetition`, because a repeated sentence scores as coherent |
| `semantic_coverage` | how many of the article's most-used words the summary kept | the `daily-figures` disclosure | a column, the day's median percent; days before 24 September print as not measured |
| `evidential_density` | how often the article says who reported a claim | `source-doubts` | a figure on each source row, the median per 1,000 article words |
| `speculative_density` | how often the article hedges | `source-doubts` | beside `evidential_density` and the row's dropped-hedge count |
| `extraction_suspect` | the checker thought the extracted text was page furniture | `extraction` on Pipelines | distinct articles out of summaries checked, beside the extractor's own `not_prose` and `contaminated` refusals |
| `determinism_violation` | one input gave two different summaries | the twelfth card and the `daily-figures` disclosure | distinct articles a day, never ledger rows. It earns a card because it says whether a before-and-after comparison on this route compares like with like |

Row 7 owns the map in `eval-instruments.ts` and rewrites `frontend/tests/console-model-instruments.spec.ts` to visit each route `EVAL_PANELS` names; `data-eval-panel="extraction"` is already on Pipelines' panel from row 1.

#### Hardware (`/console/machine/`), row 9 - today's four groups

`platform-mix` is shipped (#1171); [the machine drawing rules](../docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md) own its behavior. Row 1 moves its config, drivers and expectations, row 2 adapts its chart props, row 4 declares its query and moves its caller to `sliceOnce`, and row 9 completes route integration without changing that behavior. Every other panel moves; none keeps a build-time read.

| Group | Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What the machine was doing | 6 KEEP | `two-clocks` | Whether the speed numbers can be trusted | `item-health`: `date`, `run_id`, `job`, `shard`, `prefill_ms`, `input_tokens`, `cached_tokens`; `host-fingerprint`: `date`, `run_id`, `job`, `shard`, `server_prompt_tokens`, `server_prompt_seconds`; joined on `HOST_FINGERPRINT_KEY` (section 2.3) | `rankedList`, a row a shard of the newest run: value the gap between the two counts in percent, one rule at `machine.knobs.clocks_agree_within_pct`, the two counts in the readout, `status` `disagrees` past the rule | no - two clocks of one job | newest run |
| | 6 KEEP | `processor-lost` | the title it has | `item-health`: `date`, `run_id`, `shard`, `cpu_steal_pct` | `tileStrip` | no - the host's share | follows |
| | 6 KEEP | `disk-reads` | the title it has | `item-health`: `date`, `run_id`, `item_index`, `llama_major_faults`, `os_mem_cached_bytes`, `weights_pinned` | `tileStrip` | no - the host took memory | follows |
| | 6 KEEP | `machine-cards` | Which machines this run was given | `host-fingerprint`: `date`, `run_id`, `job`, `shard`, `fingerprint`, `cpu_model`, `cpu_family`, `cpu_model_number`, `cpu_stepping`, `microcode`, `flags`, `l3_cache_bytes`, `boot_seconds`, `mhz_at_probe`, `memcpy_gib_s`, `memcpy_probe_mib`, `vm_size`, `vm_location`, `vm_zone`, `vm_fault_domain`; `item-health`: `date`, `run_id`, `job`, `shard`, `cpu_model`, for a work shard the host record missed | the cards as they are | no - one run's machines | newest run |
| | 7 REDRAW | `slower-machines` (was `reading-against-writing`) | Which machines do the same work slower | `item-health`: `run_id`, `cpu_model`, `prefill_ms`, `input_tokens`, `cached_tokens`, `decode_ms`, `output_tokens` | **two `rankedList`s side by side, `Reading` and `Writing`**, a row a `cpu_model`: value the median of each qualifying row's rate divided by its run's median rate on the reference machine, times the reference machine's typical seconds (section 2.3, "Rates"); `range` notch at the 90th percentile, printed `slowest tenth`; one rule at the reference machine, named for it; floor `machine.knobs.slower_machines_min_articles`; capped at `console.fleet_top_kinds`. Runs with no reference row are counted and printed. **Never one total**: one kind reads a token in 37 percent of another's time and writes one in 145 percent of it | no - kinds, not days | follows |
| | 6b SHIPPED | `platform-mix` | Which machines ran our jobs, day by day | packed `host-fingerprint` through the shared query reader | existing stacked day bars and job squares | no - host placement | follows |
| Where the time went | 8 REDRAW | `slowest-articles` (was `shard-board`) | Which articles took longest in the last run | `item-health`: `run_id`, `item_id`, `source_id`, `shard`, `item_total_ms`, `fetch_ms`, `extract_ms`, `summarize_ms`, `faithfulness_ms`, `stage_gap_ms`, `queue_wait_ms` | `rankedList`, `machine.knobs.slowest_articles_rows` rows: value `item_total_ms`; segments `fetch_ms`, `extract_ms`, `summarize_ms`, `faithfulness_ms` (named `checking`), and `other` where `stage_gap_ms` is above zero; context `waited 12 s first` from `queue_wait_ms`, which sits outside `item_total_ms`. A row whose `stage_gap_ms` is below zero draws its bar whole and its readout says `stages overlapped by 1.2 s` | no - one run | newest run |
| | 6 KEEP | `tail-trend` | Whether the slowest articles are getting slower | `item-health`: `date`, `run_id`, `summarize_ms` | its five subplots as they are, the settings line on each | yes | follows |
| How close we are to the limits | 9 REDRAW | `closest-to-memory` (was `memory-board`) | Which articles left the machine least memory | `item-health`: `date`, `item_id`, `source_id`, `os_mem_total_bytes`, `os_mem_available_min_bytes`, `source_words` | `rankedList` with `ends`, a row an article: fill to the memory held at its lowest point (`os_mem_total_bytes - os_mem_available_min_bytes`), `ends` at `os_mem_total_bytes`, so free memory is the empty track between them; largest first, `machine.knobs.closest_to_memory_rows` rows, the article's length as context | no - a ranking | follows |
| | 6 KEEP | `memory-held` | What is holding the machine's memory | `item-health`: `date`, `item_id`, `os_mem_total_bytes`, `os_mem_available_bytes`, `llama_rss_bytes`, `python_rss_bytes`, `llama_rss_anon_bytes`, `python_rss_anon_bytes`, `os_swap_total_bytes`, `os_swap_free_bytes` | its bars as they are | no - one day's split | newest day |
| | 10 REDRAW | `context-headroom` | How much of the reading limit an article takes | `item-health`: `label_input_tokens`, `summary_input_tokens`, `n_ctx_configured`, `n_parallel`, `truncation_cap_tokens` | two small `distribution`s, label and summary, `scale: 'log'`, each with two rules printing their values: the reading limit, `n_ctx_configured / n_parallel` (the context one request slot gets; the model server splits its context across its slots), at the smallest value in the window, the note naming any other; and the median `label_input_tokens` of the rows a cap cut (`truncation_cap_tokens` filled), or the note `No article was cut in this window.` | no - one distribution of the window | follows |
| What the model spends | 6 KEEP | `article-cost` | What one article costs the machine | `item-health`: `date`, `run_id`, `job`, `shard`, `item_index`, `item_total_ms`, `cpu_busy_pct`, `prefill_ms`, `decode_ms`, `llama_rss_bytes`; `host-fingerprint`: `date`, `run_id`, `job`, `shard`, `threads`; joined on `HOST_FINGERPRINT_KEY` | its tracks as they are; its band takes its series' stop at `--chart-spread-mix` (today it reads `--color-chart-1`, which no theme defines, so it draws nothing) | no - per article | follows |
| | 11 REDRAW | `prompt-reuse` | How much text the model reads again | `item-health`: `date`, `label_input_tokens`, `label_cached_tokens`, `label_cache_pct`, `label_prefill_tokens_per_s`, `summary_input_tokens`, `summary_cached_tokens`, `summary_cache_pct`, `summary_prefill_tokens_per_s` | `dateSeries`, two lines: the median `label_cached_tokens` per label request (text held from an earlier request), and the median `summary_input_tokens - summary_cached_tokens` per summary request (what the summary call reads fresh; it reuses the whole label prompt, so a held count would only track article length). The server's share and ours are printed beside it as the check | yes | follows |
| | 6 KEEP | `read-against-written` | What a run reads against what it writes | `item-health`: `date`, `run_id`, `input_tokens`, `output_tokens`, `prefill_ms`, `decode_ms` | `dateSeries` | yes | follows |
| | 6 KEEP | `counterfactual-cost` | What the runner's work would have cost elsewhere | `readAgainstWrittenQuery`, and the rate from config | `dateSeries`, the running shape | yes - the model, the quantisation and `n_parallel` move what the work costs | follows |

**Route sentences.** The recording sentences, `data-machine-record`, the refused runs and the newest run come from declared queries through `recording.ts`, and the browser refuses exactly the runs the server refuses today. The built intro keeps its last sentence, which holds no figure; the run count and span join the route line's settled sentence. The newest-run line goes: each newest-run panel names its run. **The lost state** is a day on which `item-health` has published rows and `host-fingerprint` has none. The intro's `read at build time and published nowhere` becomes `read from the published record when you open this page`.

#### Voices (`/console/voices/`), row 8 - two groups, `what-the-sources-supplied` and `what-the-ranking-did`

| Group | Verdict | Id | Title after | Data after | Type | Rule | Window |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What the sources supplied | 16 KEEP | `source-health` | Sources we may ask, and what they yield | build-time: `sourceHealthView` | the table as it is; its yield column draws `RankedList.svelte`'s bar on one shared scale; the view's `headline_sentence` is its lede | no - permissions | follows |
| | 18 REDRAW, with 22 folded in | `feeds-failed` | Feeds and articles that failed | the feed row from the build-time `feedResults`, written for the widest preset; the article row from `item-health`: `date`, `source_id`, `stage`, `outcome`, `code`, `http_status`, `source_form`, `tier`, fetch-stage rows only | `tileStrip`, two rows a source, feed above articles, **one key for both rows**, on one axis ending at the older of the two rows' newest days, named under it: `Feed results after 26 Sep wait for their article fetches.` An article tile fires on a row whose `code` is `http_client_error`, `http_rate_limited`, `http_server_error` or `network_error`, against `voices.knobs.article_fails_marked` and `voices.knobs.article_fails_named`. **A status class never gets its own colour**: the readout prints each code in words with its status, `rate limited (429) on 7 of 9 fetches`, then `source_form` and `tier`, and each drawn row ends with its commonest code and its newest failed day, `mostly rate limited, last 26 Sep`. Sources with a fired tile in either row are drawn, most fired days first, up to `console.feed_rows`; one line counts the rest: `4 more sources failed on fewer days; 31 answered on every day.` It is one reserved box until both rows land. If the article row does not arrive, the feed row draws alone and says `Article fetches did not arrive, so only feed results are drawn.`; with scripts off, a `<noscript>` holds the feed row alone and says `Article fetches need JavaScript, so only feed results are drawn.` | no - outcomes, not a trend | follows |
| | 21 NEW | `fetch-time` | Where a fetch spent its time | `item-health`: `source_id`, `fetch_ms`, `fetch_connect_ms`, `fetch_ttfb_ms`, `robots_ms`, `retry_total_ms`, `retry_count` | `rankedList` capped at `console.source_rows`, a row a source: value the mean `fetch_ms`; segments the means of `robots_ms`, `retry_total_ms`, `fetch_connect_ms`, `fetch_ttfb_ms`, and `the rest` = `fetch_ms` minus those four; `retry_count` in the readout only. **Means, not medians**: the medians of the parts do not add up to the median of the whole. Rows without `robots_ms` are left out. The four clocks do not overlap, and `fetch_ms` contains them all | no - a ranking | follows |
| | 16 KEEP | `retiring` | Sources close to retiring themselves | build-time: `sourceHealthView` | `TargetBar.svelte` rows as they are | no - a rule's distance | follows |
| | 16 KEEP | `source-cuts` | Sources cut short most often | `item-health`: `date`, `source_id`, `url_key`, `source_words_before_cap`, `source_words` | `SourceCutRange.svelte` as it is (its axis is log, and a fill from zero has no place on it) | no - a ranking | follows |
| What the ranking did | 17 REDRAW | `ranking-discount` | How far the ranking discounts each feed | build-time: the source-health view's `reliability`, `reliability_reads`, `opportunities`, `reliability_floor` and `run_id` for every live feed, because `item-health` has no row for a feed whose reads failed, which is what the discount measures | `rankedList`, a row a feed, heaviest first, ties by most reads, capped at `console.source_rows`: value `1 - reliability`; context `14 reads`; `status` `on the floor` where the fill meets the rule; one rule at `1 - reliability_floor`, named `the most the ranking takes`; tail `9 more discounted, 2 on the floor; 180 answered every read; 23 were not read in 14 days and keep full weight.` The note names the view's run | no - one run's setting | newest run |
| | 19 NEW | `why-chosen` | Why the newest day's articles were chosen | `item-health`: `date`, `run_id`, `item_id`, `source_id`, `selection_score`, `authority_score`, `tier_score`, `feed_weight`, `feed_reliability`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step`; each `item_id` keeps its row from its newest run | `partsOfOne`, `voices.knobs.why_chosen_rows` rows ranked by score, five parts in this order: `authority_score`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step`, which sum to `selection_score` (`backend/idhazh/rank.py`; `tier_score`, `feed_weight` and `feed_reliability` are multiplied into `authority_score`, so they are not parts). The readout prints `authority 0.72 = tier 1.0 x weight 0.8 x reliability 0.9` | no - one day's choice | newest day |
| | 20 NEW | `watchlist` | What the watchlist caught | `item-health`: `date`, `url_key`, `watchlist_hit`, `on_front_page` | `tileStrip`, one tile a day, against `voices.knobs.watchlist_hits_marked` and `voices.knobs.watchlist_hits_named`; one line says what a filled day means: `A filled day: the watchlist caught at least one article.` It counts articles by `url_key`, never rows, because an article carried through several runs has a row in each | no - a count of hits | follows |

**Panel 22 (`source-answer`) is folded into `feeds-failed`**: both drew `http_status` a source a day. **The reader loses** the tiles of sources whose feed and articles answered every day; one line counts them.

#### Judgement (`/console/judgement/`), row 3 - one untitled group, in this order

Every panel keeps its build-time read and its component; none imports ECharts. Each declares `data-model-rule="no"` with the reason `the judge's record, not how summaries are written`, and follows the window as it does today; row 3 changes no read.

| Verdict | Id | Component |
| --- | --- | --- |
| 14 KEEP | `merged-stories` | `MergedStoriesPanel.svelte` |
| 14 KEEP | `merge-line` | `MergeLinePlot.svelte` |
| 14 KEEP | `judge-agreement` | `JudgeAgreement.svelte` |
| 14 KEEP | `record-gates` | `RecordGates.svelte` |
| 14 KEEP | `verdict-split` | `VerdictSplit.svelte` |
| 14 KEEP | `holdout-margin` | `HoldoutMargin.svelte` |
| 15 DELETE | - | the `What the model made of each article` heading and its `data-console-empty="judgement"` sentence. **The reader loses** the sentence saying the model's desk and lens choices go unrecorded, and its pointer to Summaries. It returns with whichever plan wires the judge's per-article record |

#### 2.7b What each panel says

`Lede` is the figure or sentence in `data-lede`, at `--text-xl` unless the cell says otherwise (section 2.4, "The lede"). `Comparison` is the panel's one `data-comparison` sentence. `Nothing fired` is the sentence step 5 of section 2.4 prints for a window with rows in which nothing fired; it ends `in these 30 days.` unless it names a run, and a number from a knob prints the knob's value.

| Id | Lede | Comparison | Nothing fired |
| --- | --- | --- | --- |
| `at-a-glance` | articles published, `--text-3xl` | articles published against visuals published | - |
| `run-health` | articles published of those planned | articles published against articles planned, per run | - |
| `site-cost-per-item` | bytes an article, `--text-2xl` | each day's bytes per article against the window's median | - |
| `failure-mix` | the share of articles that failed | the declared `composition` case | `No article failed at any step` |
| `item-time-split` | mean seconds an article | the model's calls against fetching and extracting | - |
| `slower-on-same-work` | the typical article's seconds on the newest day | the newest day against the window's median | - |
| `stage-timings` | median summarize seconds | summarize against fetch and extract | - |
| `item-cost` | seconds to write one summary | writing one summary against reading one prompt | - |
| `run-timeline` | items a minute, `--text-2xl`; its three headline figures drop to `--text-xl` | the shards' work against the time the run took | `No step overran its article's clock in the newest run.` |
| `chart-drawing` | visuals published | visuals published against articles that reached drawing | - |
| `extraction` | the share published without a chart, `--text-3xl` | chartable articles against narrative and unclassified ones | `The checker took no extracted text for page furniture` |
| `article-age` | the sentence `31 of 212 publication times were inferred and are not drawn.` | articles over a day old against newer ones | `Every publication time came from the source` |
| `model-cards` | the first card, `--text-3xl` | each card's newest day against its last 14 days | - |
| `model-throughput` | the newest day's median tokens per second | each day's rate against the window's median | - |
| `call-ending` | calls cut off at the length limit | calls cut off at the length limit against calls that ended on their own | `No call was cut off at the length limit` |
| `refusing-rule` | the top rule's refusals | the rule that refused most against every other rule | `No rule refused a model reply` |
| `doubt-reasons` | the share of summaries doubted | the commonest reason against the rest | - |
| `faithfulness` | the median score | each day's median against its middle half | - |
| `source-doubts` | the top source's doubted share | each source's doubted share against all sources' share | `The checker doubted no source` |
| `write-cost` | median seconds | each time band's count against the share done by then | - |
| `score-cost` | median seconds | each time band's count against the share done by then | - |
| `summary-length` | median words | each run's middle length against its shortest and longest | - |
| `model-change` | the median score change | scores after the change against scores before it | `The published record holds no model change to compare.` |
| `two-clocks` | the widest gap | each shard's gap against the tolerance | `Every shard's two clocks agreed within 5 percent in the newest run.` |
| `processor-lost` | marked days | days past the marked share against days under it | `The host took under 5 percent of the processor every day` |
| `disk-reads` | marked days | days the model was read again from disk against days it was not | `The model stayed in memory every day` |
| `machine-cards` | machines given | each machine's share of the shards against the other machines' shares | - |
| `slower-machines` | the slowest kind's reading time over the reference machine's | each machine kind's typical time against the reference machine's | `Every article ran on one kind of machine` |
| `slowest-articles` | the slowest article's seconds | each article's longest stage against its other stages | - |
| `tail-trend` | the slowest tenth's seconds | the slowest articles against the middle one | - |
| `closest-to-memory` | the sentence `The tightest article left 1.2 GB of the machine's 16 GB free.` | the memory held at each article's lowest point against the machine's total | - |
| `memory-held` | the model server's share | the model server's memory against everything else | - |
| `context-headroom` | the largest prompt's share of the limit | each prompt against the reading limit | `No article reached the truncation cap` |
| `article-cost` | processor seconds, `--text-2xl` | the middle article against the range most articles fall in | - |
| `prompt-reuse` | the median tokens a label request found held | text held for the label call against text the summary call reads fresh | - |
| `read-against-written` | tokens read per token written | tokens read against tokens written | - |
| `counterfactual-cost` | the counterfactual total | each day's cost against the running total | - |
| `source-health` | its `headline_sentence` | each source's yield against the best source's | - |
| `feeds-failed` | the sentence `12 sources failed on at least one day; example.com failed on 9 of 30.` | each source's feed against its article fetches | `Every feed and article fetch answered every day` |
| `fetch-time` | the slowest source's mean seconds | the largest part of each fetch against the other parts | `No fetch was retried` |
| `retiring` | sources near retiring | each source's distance against the retirement rule | - |
| `source-cuts` | the most-cut source's share | each source's typical cut against its range | `No source's articles were cut short` |
| `ranking-discount` | feeds discounted | each feed's discount against the most the ranking takes | - |
| `why-chosen` | the finding below | the authority part against the four bonuses | - |
| `watchlist` | the sentence `The watchlist caught 9 articles on 4 of 30 days; 2 reached the front page.` | days with a catch against days without | `The watchlist caught no article` |
| `merged-stories` | stories merged | stories merged against stories kept apart | - |
| `merge-line` | pairs past the line | each pair's similarity against the merge line | - |
| `judge-agreement` | the share agreed | the judge's verdicts against a person's | - |
| `record-gates` | gates passed | each gate's reading against its bar | - |
| `verdict-split` | pairs judged one story | pairs judged one story against pairs judged two | - |
| `holdout-margin` | its headline figure, `--text-2xl` | each held-out pair's score against the threshold | - |

**The `why-chosen` finding.** A is the `voices.knobs.why_chosen_rows`-th highest `authority_score` among the newest day's candidates; B is the number of drawn articles whose `authority_score` is below A. When B is at least 1: `On 26 Sep the bonuses brought in 19 of the twenty: on their sources' standing alone they would not have made it. Recency added most.`, naming the bonus with the largest total over the drawn rows. When B is 0: `On 26 Sep the bonuses brought in none of the twenty: their sources' standing alone picks the same twenty.`

### 2.8 Panels that keep a build-time read

| Route | Panel | Dataset | Why it cannot move here |
| --- | --- | --- | --- |
| Pipelines | `at-a-glance`, `run-health`, `site-cost-per-item`, `chart-drawing`, and inside `extraction` the share published without a chart and the yield trend | the digest day files, the run manifests, `state/day-metrics/` | none is a published ledger, and no ledger records whether a published article carries a chart |
| Summaries | `model-cards` with its `daily-figures` disclosure | `state/day-metrics/` | the distinct counts cannot be rebuilt from the ledgers (section 2.7) |
| Summaries | `doubt-reasons` | the digest day files | the reason is a decision recorded on the published item and in no ledger; rebuilding it means re-implementing the band rule with each day's thresholds, and a `not_scored` item has no score row to rebuild from |
| Voices | `source-health`, `retiring`, `ranking-discount`, and the feed row of `feeds-failed` | the source-health view, `state/feed-health/` | not published |
| Judgement | all six | `state/content-similarity-judge/` and the digest day files | not published |

**Each is drawn once**: its pure module takes the chart type's input, and the build-time load is the only code that shapes that input, so the later move replaces the load and nothing the reader sees; the move is done when its pictures show the same marks. Gate 8 judges each on `quiet` and `missing` from its route's nothings spec (section 2.2). **The reader loses** view-time freshness on these panels until the out-of-scope plan publishes their datasets.

### 2.9 Knobs and tokens this plan mints

Each knob lives in its route's `knobs` (section 2.2) unless named otherwise. A value derived by a rule is re-derived at dispatch (execute-a-plan.md check 4) and committed with the rule on its declaring line.

| Key | Value | Minted by | Reader |
| --- | --- | --- | --- |
| `console.tile_min_px` in `config/appearance.json` | `6`: the narrowest tile whose inside (its width less both 1 px borders) is at least twice the 2 px gap between tiles, from `TileStrip.svelte`'s CSS, so an empty tile reads as a box, not a stripe | row 2 | `TileStrip.svelte` |
| dark `--chart-6` in `frontend/src/styles/tokens.css` | `#1ab6ff`: the colour with the largest smallest CIEDE2000 distance to the other seven dark stops, hue 180 to 320, contrast 5.9:1 to 8.8:1 on `--color-surface` | row 2 | `series-tokens.ts` |
| `--chart-spread-mix` in `tokens.css`, both themes | `0.30`: the smallest mix, in steps of 0.05, at which every stop's band is at least as far from `--color-surface` on CIEDE2000 as the theme's two closest stops are from each other, and every line is further from its band than the band is from the surface; derived after the `--chart-6` re-tune | row 2 | `DateSeries.svelte`, `article-cost` |
| `--route-line-reserve` in `tokens.css` | `3` lines, an estimate row 4 replaces with the tallest route-line sentence at 390 px | row 4 | `RouteStatus.svelte` |
| `machine.knobs.slowest_articles_rows` | `20` | row 9 | `slowest-articles` |
| `machine.knobs.closest_to_memory_rows` | `20` | row 9 | `closest-to-memory` |
| `machine.knobs.slower_machines_min_articles` | `10`: the fewest articles whose slowest tenth, by nearest rank, is not the single slowest article - ceil(0.9 x n) < n | row 9 | `slower-machines` |
| `machine.knobs.clocks_agree_within_pct` | `5`, today's `CLOCKS_AGREE_WITHIN_PCT`, moved from code to config | row 9 | `two-clocks` |
| `voices.knobs.article_fails_marked`, `voices.knobs.article_fails_named` | `1`, `3` | row 8 | `feeds-failed` |
| `voices.knobs.why_chosen_rows` | `20` | row 8 | `why-chosen` |
| `voices.knobs.watchlist_hits_marked`, `voices.knobs.watchlist_hits_named` | `1`, `3` | row 8 | `watchlist` |
| `page_weight.payload_ceilings_bytes."console/band.json"` in `config/idhazh.json` | twice the built band's compressed size | row 5 | `frontend/scripts/bundle-gate.mjs` |

### 2.10 The door at the console's real volume (row 4)

**Suspended by the latest user direction in section 0.** The historical measurement design below is not an instruction to run it or a readiness gate. Query and loading-state correctness checks remain required.

**Why it runs before any route moves.** Every door panel asks the door for rows, not totals. At 1,000 items a day and a 90-day window a trend query builds about 90,000 row objects on the main thread, and a route asks up to fifteen queries. Whether that is fast enough decides the door's return shape, which is cheapest to change while no panel calls it.

| # | Part | Rule |
| --- | --- | --- |
| 1 | Data | `backend/utilities/door_volume_fixture.py` writes an uncommitted fixture to the temp directory: `max(console.window_presets)` days of each ledger with both indexes, packed as row 4 packs the canary. Each day is one whole committed day with its dates and run ids rewritten; items are copied under new `item_id` and `url_key` values until each day has 1,000 `item-health`, 925 `scores` and 69 `host-fingerprint` rows - the busiest day measured on 2026-09-28, plus a quarter |
| 2 | Scope | The `pipelines`, `model`, `machine` and `voices` routes. A route's queries are every `PanelQuery` its `queries/<route>.ts` exports, shared ones included. The presets are read from `config/appearance.json` at run time: `console.default_window_days` and `max(console.window_presets)`. Each query asks the range its `span` gives it |
| 3 | Harness | A test page Vite builds from `frontend/scripts/measure-door/`, which asks every route query through `sliceOnce` in page order, no query waiting for another. `$app/paths` and the door's build-time values take the site build's values. `frontend/scripts/measure-door.mjs` serves it with `max-age=600` and an `ETag`, as Pages does, and serves the add-on through `door-page.ts` |
| 4 | Runs | For each route and preset: five cold runs (a new browser context, empty cache) and five warm runs (a reload), alternating, with the route order rotating each round, Chromium at 4x CPU slowdown. A timed loop checks whether the slowdown reached the engine's worker; if it did not, the worker's times are multiplied by 4 and labelled |
| 5 | Recorded | Bytes and requests by kind, the longest chain of requests that wait on each other, engine start, each query's engine time and main-thread time, time to the last answer, the longest main-thread task, and the quiet-machine sample. Network time = serial requests x 100 ms + bytes / 10 Mbit/s, labelled as arithmetic and reported only. The worst, the median and the spread |
| 6 | Machine | This developer machine (Intel Core i7-1265U, Windows 11, on mains power), with the date. `python backend/utilities/gate_lock.py --require-lock --timeout 1800 -- node frontend/scripts/measure-door.mjs`, with `CI` unset: it never runs without the lock and never takes it from a live holder. Each run starts only after a 5 s sample shows the machine under 10 percent busy (an estimate), waiting at most 10 minutes for it, and the whole script finishes within 50 minutes, because a waiting selector gives up after 60 |
| 7 | Pass line | Committed on its own before the first reading. Judged per route on the worst of five. Warm, at the widest preset: every query answered within 2 s of navigation, and no main-thread task over 200 ms. Cold, at the default preset: every query answered within 2 s after the add-on arrives. The other 1 s of a route's 3 s is for its modules and drawing - an estimate nothing here measures |
| 8 | Written to | `docs/reference/benchmarks/the-query-door-at-the-consoles-real-volume.md`, linked from the instrument log in `docs/reference/pipeline-cost.md` |
| 9 | A miss | The row still merges. ESCALATE trigger 3 holds rows 6 to 9 until this plan's owner rules on the numbers and the possible fixes: a column-shaped result, a "newest N days" ask, or a structured aggregate. A machine that is never quiet gives no reading, which holds rows 6 to 9 the same way. Any CI guard that follows counts rows and never times wall-clock on a shared runner |

### 2.11 Rulings asked of the owner, and the default each row proceeds on

| # | Situation | Options, with what each costs | Default the rows proceed on |
| --- | --- | --- | --- |
| R1 | N8 names `console/band.json` among the artefacts that leave `frontend/`. The band is sentences and counts the pipeline composes about its own run, inlined into every console document | A. Keep it where it is and strike it from N8: one line on the intent page. B. Move it under `state/` and publish it with the ledgers: a publish entry for a file that is not a ledger, and its address moves. C. Compute it in the browser: needs `feed-health` and the run manifests published first, and puts several fetches ahead of the first verdict | **Leave both the band and N8 as they are**; only the owner narrows intent. Row 5 changes what the band reads and carries, not where it lives |
| R2 | N4 says the console routes come off prerender. After rows 6 to 9, no data route's document carries a ledger value | A. **A prerendered page with no ledger data** (section 2.4, "The built page"): every panel fetches at view time. Costs: with scripts off, or when the record cannot be fetched, a moved panel shows its frame and no figure, where today it shows every mark. B. **Off prerender** (`prerender = false`, `ssr = false`, served by the `404.html` fallback): the server loads must go and config reaches the page through `__CONSOLE__`; the page is blank until the bundle boots; Pages answers with HTTP 404; nothing shows without scripts; the band is one round trip later; the cold chain becomes 5 serial requests against the 4 `console-cold-load` allows; the scripts-off specs break; it reverses the 2026-09-12 ruling in `docs/architecture/publishing/frontend.md` | **A** (Susan, Carmack and Jony). Rows 6 to 9 build it. A ruling for B is a new row after row 11 |
| R3 | The settings line needs the run manifests' inputs, which no published ledger holds | B1. The band carries the changes (section 2.6): a `ConsoleBand` change and a higher band ceiling. B2. Nine more columns on `item-health`: a persisted-contract change, blind before the day it lands. B3. Publish the manifests: the first out-of-scope row. B4. Read `item-health`'s settings columns: misses the prompt and draws false lines | **B1**, on this plan's authorization (Andre) |

## Rows

### Row #1 - Each route gets its own console file, gate drivers and test expectations

- **Scope:** section 2.2, and nothing that moves a pixel: no id is added to a panel, no frame is added, no data read changes. The six console files are written with today's panel lists, including the existing Data explorer groups and judged ids; `route-console.ts` and `__CONSOLE__` land and the layout moves onto them; the two server loads that read panel groups read `routeConsole()`; the drivers move into one module a route and the per-route expectations into one folder a spec; the seventeen cross-route specs read their per-route expectations from `console-expect`; the capture and sufficiency specs are restructured; the selector learns `config/console/`; `data-eval-panel="extraction"` goes on Pipelines' extraction section. **Built by fan-out inside one checkout**: workers own disjoint files and run no git command that writes; the owner runs the selected correctness checks, checks that no spec lost any of the six routes, sends any failing spec back to its worker, and carries the PR. No measurement or baseline-picture work runs.
- **Files touched:**
  - `config/appearance.json`, `config/console/pipelines.json`, `config/console/model.json`, `config/console/machine.json`, `config/console/voices.json`, `config/console/judgement.json`, `config/console/data-explorer.json` (route files new)
  - `backend/idhazh/contracts/knobs/console.py`, `backend/idhazh/contracts/appearance_config.py`, `backend/idhazh/contracts/app_config.py` (changelog lines), `backend/tests/test_appearance_config.py`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `frontend/src/lib/console/route-console.ts` (new), `frontend/src/lib/server/config.ts`, `frontend/vite.config.ts`, `frontend/src/app.d.ts`, `frontend/src/routes/console/+layout.svelte`, `frontend/tests/appearance-config.spec.ts`
  - `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/machine/+page.server.ts` (both read `routeConsole()`), `frontend/src/routes/console/+page.svelte` (`data-eval-panel="extraction"`), `frontend/src/routes/console/data-explorer/+page.svelte` (preserves its three panels through `routeConsole()`)
  - `frontend/tests/support/console-panels.ts`, `frontend/tests/support/panel-gates.ts` (the `Driver` type), `frontend/tests/panel-captures.spec.ts`, `frontend/tests/panel-sufficiency.spec.ts`, `frontend/tests/fixtures/panels/WitnessPanel.svelte`
  - `frontend/tests/support/judgement-route.ts` (the bounded private-build inventory includes `route-console.ts`; generated files stay under the test output; no build timing is collected)
  - `frontend/tests/support/panel-drivers/index.ts`, `pipelines.ts`, `model.ts`, `machine.ts`, `voices.ts`, `judgement.ts`, `data-explorer.ts` (new)
  - `frontend/tests/support/console-expect/<spec>/index.ts` and `console-expect/<spec>/<route>.ts` for each of the seventeen specs and each of the six routes (new)
  - `frontend/tests/console-axis.spec.ts`, `console-band.spec.ts`, `console-chart-lifetime.spec.ts`, `console-chart-pending.spec.ts`, `console-chrome.spec.ts`, `console-frame.spec.ts`, `console-mark-parity.spec.ts`, `console-model-panels.spec.ts`, `console-model-rule.spec.ts`, `console-nav.spec.ts`, `console-polarity.spec.ts`, `console-readout.spec.ts`, `console-shell.spec.ts`, `console-title.spec.ts`, `console-voices.spec.ts`, `console-window.spec.ts`, `console.spec.ts` (each under `frontend/tests/`), `frontend/tests/console-route-scope.spec.ts` (new)
  - `frontend/tests/console-cold-load.spec.ts`, `console-data-explorer-window.spec.ts`, `console-data-explorer.spec.ts` (navigation addresses only, preserving their assertions while satisfying the ownership guard; the cold-load measurement is not run)
  - `frontend/scripts/test-scope.ts`, `frontend/scripts/tests/test-scope.test.mjs`, `frontend/scripts/test-groups.ts`
  - `docs/concepts/config/appearance.md`, `docs/architecture/publishing/console.md` (the question table), `docs/reference/test-selection.md`
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/test_appearance_config.py backend/tests/contracts`, `npm --prefix frontend run test:tooling`, `npm --prefix frontend run check`, `npm --prefix frontend run test:changed -- --list` then the selected correctness checks (every console route: this row touches all six). Integrated browser smoke, including missing/empty-data checks, remains mandatory. No size, performance, timing or baseline-picture run; no collection of CI worker seconds or wall time. CI runs the full suite.
- **Oracle:** **nothing a reader sees moved, and each route now owns its own files.** Existing correctness assertions and browser smoke preserve the Hardware and Data explorer panels without before/after baseline pictures; `routeConsolesFrom` refuses each case in section 2.2's table, one test a case; `console-route-scope.spec.ts` fails when a driver module names a second route's address (bite: add `/console/voices/` to `panel-drivers/machine.ts`, watch it fail, restore); `npm run check` fails when a scratch member is added to `RouteId` and one `index.ts` does not name it (bite, restore); the selector lists only Hardware's groups for an edit to `config/console/machine.json`. It cannot settle whether any panel is good; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A file per route.** It is the refactor that splits the one surface every route row would otherwise edit, so it runs first (execute-a-plan.md) | Fowler |
  | 2 | **Structural only.** Summaries and Voices draw no `Panel` frame and four Pipelines sections have none, so adding ids and frames moves pixels on three routes; each route row adds its own | Fowler |
  | 3 | **Per-route expectations are typed out, one file a spec and a route.** A spec that reads the source it guards proves only that the page agrees with itself, and one file a spec and a route lets four workers build this row and four route rows edit their own files | Fowler, Carmack |
  | 4 | **One build-time value carries every route's console config, and one module reads it.** Plan 55's route has no server load, so a value a server load returns would need a second way in | Fowler, Jony |
  | 5 | **The sufficiency spec judges a route, a width and a theme per page load**, and gate 8 is driven per route and theme, because at about 50 judged panels a per-panel loop times out under the 180 s test limit | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep one `console.panel_groups` and let the dispatcher treat per-route keys as disjoint | The readiness test compares files, and the judged list is one flat list every row appends to | Changes across six routes serial, or a hand resolution per merge | Fowler |
  | 2 | Make the cross-route specs read `config/console/` | A spec that reads what it guards cannot catch a wrong entry | The guard | Fowler |
  | 3 | One expectations file a route, holding every spec's key | Four spec workers would write the same six files at once | The fan-out, so row 1 runs as one worker, which plan 51 showed runs out of room at this size | Fowler, Carmack |
  | 4 | `Partial<Record<RouteId, ...>>` for `BY_ROUTE` | A new route would skip every check without a warning | Silent gaps on the existing Data explorer or a later route | Fowler |
  | 5 | Each route's server load returns its knobs as props | Plan 55's route has no server load, so it needs a second mechanism | Two ways config reaches a page | Jony |

---

### Row #2 - The ranked list draws a range and a floor, the date series carries the settings line, and every type carries its readout

- **Already carried by plan 55 row 20:** optional readouts for PartsOfOne, TileStrip and Flow; explorer-only native tooltip removal; caller part colours (K2), tile thresholds only with readings (K3), caller tile-state words (K4), and an opt-in shared Flow count verdict for a truthful fallback lede. Every other caller keeps its defaults.

- **Scope:** section 2.5 and the colour table of section 2.4. **No pixel moves**, except that dark `--chart-6` takes its re-tuned value, and no route row edits `frontend/src/lib/charts/d3/` or a shared chart component this row changes afterwards. The settings line's data is row 5's; this row declares `ModelRule` in `frontend/src/lib/charts/d3/model-rule.ts` and makes `dateSeries` take it.
- **Files touched:**
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (adapt the shipped caller to the chart props, preserving its host-only rule declaration)
  - `frontend/src/lib/console/explorer/ShapePanel.svelte` (Susan, 2026-10-07: it calls `dateSeries`, `distribution` and `RankedList.svelte`, whose signatures this row changes; whichever of this row and plan 55 rows 19 and 20 merges later adapts the calls)
  - `frontend/src/lib/charts/d3/rankedList.ts`, `dateSeries.ts`, `DateSeries.svelte`, `distribution.ts`, `Distribution.svelte`, `tileStrip.ts`, `TileStrip.svelte`, `partsOfOne.ts`, `PartsOfOne.svelte`, `Flow.svelte`, `PairedScatter.svelte`, `model-rule.ts` (new)
  - `frontend/src/lib/components/RankedList.svelte`, `BandDistance.svelte`, `FailureList.svelte`, `KpiCard.svelte`, `frontend/src/routes/console/model/+page.svelte` (the geometry prop), `frontend/src/lib/components/ShardBoard.svelte`, `frontend/src/lib/components/MemoryBoard.svelte` (the marks move out), `frontend/src/lib/charts/machine.ts` (`rangeMark` moves out), `frontend/src/lib/components/TimeHistogram.svelte` (`domain`)
  - `frontend/src/lib/charts/targetbar.ts`, `frontend/tests/vocabulary.spec.ts`, `frontend/tests/console-ranked.spec.ts`
  - `frontend/src/lib/console/series-tokens.ts` (new), `frontend/src/lib/charts/glance.ts`, `frontend/src/lib/charts/cost.ts` (their tokens move out), `frontend/src/styles/tokens.css` (`--chart-spread-mix`, dark `--chart-6`)
  - `config/appearance.json` (`console.tile_min_px`), `backend/idhazh/contracts/knobs/console.py`, `backend/idhazh/contracts/appearance_config.py`, `frontend/src/lib/server/config.ts`, `backend/tests/test_appearance_config.py`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `frontend/tests/fixtures/panels/WitnessPanel.svelte`, `frontend/tests/panel-sufficiency.spec.ts` (callers of the new `rule`)
  - `frontend/tests/chart-types.spec.ts` (new), `frontend/scripts/test-groups.ts`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (the widened ranked list, the settings and checker lines, the named rules, the spread, the log scale, the tile width and the colour table, with Susan's ruling beside each; range marks remain one vocabulary type)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks - **every spec whose page renders a changed component**, which is every console group; `ruff check .`, `pytest backend/tests/test_appearance_config.py`; `python backend/utilities/doc_load.py docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` before and after. CI runs the full suite.
- **Oracle:** **each change draws what its signature promises, and nothing that drew before draws differently.** Over written-down rows in `chart-types.spec.ts`: a `range` row puts the fill at `value` and the notch at `high`, and below `minCount` draws no mark and ranks last; an `ends` row notches at `end`; `rule: {changes}` puts one line per date inside the frame on the boundary before its column, dashed for `settings` and dotted for `checker`, and writes `data-model-rule="yes"`, and `{declined}` under five words is refused; `opts.rules` draws a named dashed line; a log `distribution` bins by decade; a 90-day `tileStrip` at 390 px draws tiles at least `console.tile_min_px` wide and the overflow line; every type carries `data-chart-type`; `KpiCard` and `FailureList` with no new prop draw what they drew. The pictures of the `BandDistance`, `FailureList`, `ShardBoard` and `MemoryBoard` panels match before and after, apart from dark `--chart-6`. `chart-vocabulary.spec.ts` stays green unchanged. It cannot settle whether a route's panels read well; the route rows' consult does.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **No new type.** A range mark is a row of a ranked list, and a second target bar would draw one mark two ways | Susan |
  | 2 | **The rule is one value, `ModelRule`, and the component writes the attribute from it**, so the two cannot disagree; a checker change is dotted so it is never read as a settings change | Susan, Andre |
  | 3 | **Every shared component is made ready here, and a new prop is optional where a caller omits it today**, so four route rows do not each change it and this row moves no pixel | Fowler, Susan |
  | 4 | **One colour stop a quantity name, from one table**, and dark `--chart-6` is re-tuned, because today it sits 2.3 apart from `--chart-3` on CIEDE2000 and two panels draw both | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | A second target bar under `d3/` | `TargetBar.svelte` is markup drawn from `targetMarks` | Two drawings of one mark | Susan |
  | 2 | Throughput and summary length as a range row a day | A set ordered by time is a trend, and a row list carries no settings line | Both panels lose gate 6, and summary length its short end | Susan |
  | 3 | Fold this row into row 1 | About 95 files, and a chart defect would force a revert of the file split every later row builds on | One CI run saved | Fowler |

---

### Row #3 - Judgement carries its ids and gates, and its readers are named for the judge

- **Authorized repair, 2026-10-10:** use the existing `consoleKnobs()` boundary for Pipelines' shared configuration so the outgoing component does not read Judgement's page-data shape during navigation. Update only the renamed reader references in `docs/architecture/contracts/ledger-registry.md`, `docs/architecture/contracts/persistence.md` and `docs/concepts/growing-reads.md`. These four files extend this row's ownership; later rows retain their other changes.
- **Evidence repair authorized, 2026-10-10:** retain the existing `RecordRead` beside fitted lines, marked pairs, derived holdout readings and the selected committed holdout score. Carry it through the page and affected panels without inventing another state vocabulary. Preserve unknown pair denominators as `null`; do not add them as zeros or suppress a usable independent reading. Show useful partial rows and their existing lost-day, set-aside and reach information. Empty results do not prove that no job ran, fitted or scored. This is an internal reader/page/panel boundary repair, with no new producer, persisted field, dataset publication or runtime fetch.
- **Scope:** section 2.7's Judgement table: ids, frames where missing, gate attributes, driver entries (`BUILD_TIME` holds all six), expectations, `judged` entries and words (section 2.7b); `frontend/tests/console-judgement-nothings.spec.ts` for its six build-time panels; panel 15's heading deleted, with its entry in `console-expect/console-nav/judgement.ts`; the Judgement tab description becomes `Which stories the day merged, and where the judge and a person disagreed.` in `band.ts`, the band producer and `newest-day.json`; console.md's Judgement section rewritten. `frontend/src/lib/server/similarity-ledger.ts` becomes `content-similarity-judge.ts` and `similarity-holdout.ts` becomes `content-similarity-holdout.ts`: neither is named for the judge or the ledger it reads.
- **Files touched:**
  - `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/judgement/+page.server.ts`, `HoldoutMargin.svelte`, `JudgeAgreement.svelte`, `MergedStoriesPanel.svelte`, `MergeLinePlot.svelte`, `RecordGates.svelte`, `VerdictSplit.svelte` in that folder
  - `frontend/src/lib/server/similarity-ledger.ts`, `frontend/src/lib/server/similarity-holdout.ts` (renamed), and every importer a search for the two names finds
  - `config/console/judgement.json`, `frontend/tests/support/panel-drivers/judgement.ts`, `frontend/tests/support/console-expect/<spec>/judgement.ts` for each spec whose Judgement expectation moves, `frontend/tests/console-judgement-nothings.spec.ts` (new)
  - `frontend/src/lib/console/band.ts`, `backend/idhazh/telemetry/publish/console_band.py`, `tests/fixtures/contracts/console-band/newest-day.json` (the tab description)
  - `frontend/tests/merge-line.spec.ts` and every Judgement spec the search finds
  - `docs/architecture/publishing/console.md`
  - `frontend/src/routes/console/+page.svelte` (shared-config access only), `docs/architecture/contracts/ledger-registry.md`, `docs/architecture/contracts/persistence.md`, `docs/concepts/growing-reads.md` (renamed reader references only; owner-authorized repair)
  - `frontend/src/lib/server/content-similarity-judge.ts`, `frontend/src/lib/server/content-similarity-holdout.ts`, `frontend/src/lib/console/merge-line.ts`, `frontend/src/lib/console/holdout.ts`, and a focused Judgement evidence-note helper (reuse the existing `RecordRead` and exported note functions; do not change the shared vocabulary)
  - The direct consumers and independent tests of those internal reader results and nullable denominators, found through a named importer search at dispatch. Record the resulting bounded inventory before editing; these tightly coupled adaptations belong to this approved repair, not another route migration.
  - **Confirmed dependent inventory:** `ledger-rows.spec.ts`, `similarity-ledgers.spec.ts`, `merge-line.spec.ts`, `holdout.spec.ts`, `holdout-domain.spec.ts`, `console-judgement-holdout.spec.ts`, extracted Judgement window/day/record specs; new `judgement-evidence.spec.ts` and `console-judgement-evidence.spec.ts`; `support/judgement-route.ts` fixed module inputs and named evidence options, and `support/ledger-lifecycle.ts` native SQL null fixture support. Their named registration, selection tests and ownership inventory are adapted with them. No new persisted field or producer is required.
  - `recording.ts` delegates set-aside folder lookup to the existing family-folder map for the new judge-ledger caller. Its read and record state vocabularies do not change; plain-ledger paths stay the same. The existing absent-route assertion in `console-judgement-verdict.spec.ts` follows the retained unavailable read rather than expecting an empty successful read.
  - Direct geometry consumers `console-judgement-line.spec.ts`, `console-judgement-agreement.spec.ts` and Judgement's static cases in `panel-sufficiency.spec.ts` use the existing real private route builder for successful empty or populated evidence, while missing-source checks stay separate. Their geometry and timeout assertions are unchanged. No data is seeded into the shared canary.
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `pytest backend/tests/test_console_payloads_producer.py`. The browser smoke on `/console/judgement/` at 390, 768 and 1440 in both themes: zero new `[error]`, zero new `404`, and the page still renders with its data absent. CI runs the full suite.
- **Oracle:** every Judgement panel is judged and green on gates 1, 2, 3, 5 and 6, and on gate 8's `quiet` and `missing` through its nothings spec; `git grep -n -e similarity-ledger -e similarity-holdout -- frontend docs backend` finds history and nothing else; every console tab strip shows the new Judgement description. It cannot settle whether the Judgement panels answer the owner's question; they keep today's drawing.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The two readers keep their home under `frontend/src/lib/server/` and take the judge's name.** The folder is what keeps a build-time read out of a browser bundle; the names were the defect | plan 50's handed-over question, CLAUDE.md section 0b |
  | 2 | **Panel 15's heading goes with its tab description**, which repeated it word for word, and this row rewrites both, so no console page promises the section it deletes | Jony |
  | 3 | **It needs only row 1.** Its components import nothing row 2 changes, and the two rows share no file | Jony, Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fold this row into row 1 | Row 1 would move pixels, and every route row would wait on the Judgement work | One pull request saved | Jony |

---

### Row #3a - Each route owns its detailed window tests

- **Scope:** complete the known ownership defect in `frontend/tests/console-window.spec.ts` for every route it currently tests. Move route-specific factories, cases, real-component compilation and assertions into focused route-owned specs and helpers. Keep genuinely shared window, readout, control, declared surface-coverage and cross-route navigation assertions. Preserve all existing cases, applicability, presets, widths, themes and exact checks; separate structural moves from evidence and copy changes.
- **Files touched:** `frontend/tests/console-window.spec.ts`; its `support/console-expect/console-window/index.ts` and route files as needed to remove route-specific execution contracts; focused route-owned window specs under `frontend/tests/`; bounded helpers under `frontend/tests/support/console-window/`; `frontend/tests/console-route-scope.spec.ts`; `frontend/scripts/test-groups.ts`, `test-scope.ts`, `tests/test-scope.test.mjs`; `docs/architecture/publishing/console.md`, `docs/reference/test-selection.md`; this plan. Reuse `support/server-render.ts` rather than inventing another compiler or registration framework.
- **Bounded extraction inventory:** focused specs `console-judgement-window-spans`, `console-judgement-agreement-readout`, `console-judgement-agreement-marks`, `console-judgement-day-labels`, `console-judgement-record-window`, `console-machine-window`, `console-machine-day-labels`, `console-pipelines-window`, `console-pipelines-day-labels`, `console-model-window`, `console-voices-window`, `console-window-readout`; helpers `controls`, `readout`, `judgement-fixtures`, `machine-spans`, `client-render`, `server-panels` under `support/console-window/`. Only Pipelines' window expectation file and the shared index change; no other route expectation needs execution fields. The three approved reader-reference doc edits accompany structural name coherence.
- **Oracle:** map every original case to its destination and retain its assertions. The shared runner still covers its complete `BY_ROUTE` declarations, including explicit null applicability. A named spec or helper edit is selected, and deleting an expected surface fails. Route-only changes need no shared-spec edit. No production-derived expected words, callback registry, silent skips, broad fallbacks or new tools.
- **Delivery:** ordered structural commits, then row 3's evidence and corresponding exact-copy contract changes. Existing baseline failures may remain during an unchanged structural move; no candidate merges red. Correctness and integrated browser smoke remain mandatory, with no measurements or baseline pictures. This owner-approved scope does not include the other sixteen shared specs, publishing datasets, or changing prerender.

---

### Row #4 - Every panel's question is declared before it is drawn, and the door is measured at the console's real volume

Row 4 owns known defect 40: write one canary job as separate probe and completion halves, then assert that the built Hardware view shows one merged job with fields from both halves.

- **Scope:** sections 2.3 and 2.10, and the parts of section 2.4 every route shares: steps 0, 1, 2, 4 and 8, `STATE_WORDS`, `RouteStatus.svelte`, `WindowStatus.svelte`'s sentences, `__QUERY_ENGINE_BYTES__`, and the built-page check with its `console-expect/console-built-page/` folder. The `fetch_ttfb_ms` description is corrected: the code stops at the response headers, not the first byte of the body. `waiting.ts` gains day functions beside the month ones, and `empty.ts` and the witness panel move to them. **The shipped `platform-mix` adopts its declared query here so gate 10 still holds; no new panel moves.** **Two workers in sequence on one branch**: the first builds everything but the measurement; the second builds the volume fixture and the harness, commits the pass line, and measures. **The CI browser job**: the row records the browser step's time in its own CI run and in the run before it on main, and the harness's cold engine start plus query time for one page load; if that cost times the page loads rows 6 to 9 add would take the browser step past 900 s, the row splits the browser job into two shards in `.github/workflows/ci.yml`, and otherwise its pull request says it did not. **The row merges on a miss too** (section 2.10 part 9).
- **Files touched:**
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (move the shipped query caller to its declaration in the same change as gate 10)
  - `frontend/src/lib/console/queries/window.ts`, `shared.ts`, `pipelines.ts`, `model.ts`, `machine.ts`, `voices.ts` (new), `frontend/src/lib/console/rates.ts` (new), `frontend/src/lib/server/model-work.ts` (`itemRates` moves out)
  - `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/host_fingerprint.py` (registries, one changelog line each), `backend/tests/contracts/test_column_readers.py`, `backend/tests/contracts/test_panel_queries.py` (new)
  - `backend/utilities/build_canary_day.py`, `frontend/scripts/build-canary.mjs` (the canary is packed)
  - `frontend/src/lib/console/waiting.ts`, `frontend/src/lib/console/recording.ts`, `frontend/src/lib/components/RouteStatus.svelte` (new), `frontend/src/lib/components/WindowStatus.svelte`, `frontend/src/lib/components/Reserved.svelte`, `frontend/src/lib/charts/d3/EmptyState.svelte`, `frontend/src/lib/charts/d3/empty.ts`, `frontend/tests/fixtures/panels/WitnessPanel.svelte`, `frontend/src/routes/console/+layout.svelte` (the `<noscript>` words), `frontend/src/styles/tokens.css` (`--route-line-reserve`), `frontend/vite.config.ts` (`__QUERY_ENGINE_BYTES__`), `frontend/src/app.d.ts`
  - `frontend/tests/support/door-page.ts` (new, reuses `support/browser.ts`), `frontend/playwright.config.ts` (preserve check-only global setup), `tests/fixtures/console/pipelines/`, `tests/fixtures/console/model/`, `tests/fixtures/console/machine/`, `tests/fixtures/console/voices/` (new), `frontend/tests/recorded-slices.spec.ts` (new), `frontend/tests/console-built-page.spec.ts` (new), `frontend/tests/support/console-expect/console-built-page/index.ts` and its six route files (new)
  - the seventeen cross-route specs of section 2.2, `frontend/tests/panel-sufficiency.spec.ts` and `frontend/tests/panel-captures.spec.ts` (they import `test` from `door-page`)
  - `frontend/tests/chart-vocabulary.spec.ts` (gate 10: every `slice(` call sits in `queries/window.ts`, and every `sliceOnce(` call takes a `PanelQuery` imported from `$lib/console/queries/`), `frontend/tests/console-drawn-cells.spec.ts` (new), `frontend/tests/console-waiting.spec.ts` (new), `frontend/tests/console-route-scope.spec.ts` (the `door-page` case), `frontend/scripts/test-groups.ts`
  - `.github/workflows/ci.yml`, only if the browser job is split
  - `backend/utilities/door_volume_fixture.py` (new), `frontend/scripts/measure-door.mjs` (new), `frontend/scripts/measure-door/` (new, the harness page), `docs/reference/benchmarks/the-query-door-at-the-consoles-real-volume.md` (new), `docs/reference/pipeline-cost.md`
  - `docs/concepts/console-design/how-a-console-chart-gets-its-data.md`, `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` (the window anchored on the data)
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`, `npm --prefix frontend run check`, `npm --prefix frontend run test:changed -- --list` then the selected checks; `python backend/utilities/doc_load.py docs/concepts/console-design/how-a-console-chart-gets-its-data.md docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` before and after. The volume fixture is never committed. CI runs the full suite.
- **Oracle:** **every column a panel will draw is declared once, registered once, carried by the packed canary and answered the same way by its recorded slice; and the door has a reading against a line written before it.** `test_column_readers.py` is green with every declared column out of `UNREAD_CELLS`; `test_panel_queries.py` refuses a misspelt column and one still in `UNREAD_CELLS` (bite: add `failed_field` to `queries/voices.ts`, watch it fail, restore); `console-drawn-cells.spec.ts` refuses `{@html ` in a file under `frontend/src/lib/console/` (bite, restore); `recorded-slices.spec.ts` fails on an edited fixture (bite, restore); `console-route-scope.spec.ts` refuses, over a fixture tree in which one route imports `$lib/console/queries/`, a spec that opens that route without `door-page`; the harness's cold run with the network blocked answers every query, which proves the add-on reaches the engine's worker from the local copy (otherwise ESCALATE trigger 7); the benchmark page carries every reading section 2.10 names and a pass or a miss on the worst run. It cannot settle whether a query answers its panel's question; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The queries land before their panels.** They are the declared contract, read by a test in the same row, not modules waiting for a reader | Fowler |
  | 2 | **The shared waiting code, the packed canary, the recorded slices and the browser fixture are built once here**; left to the first route row, the other three would copy them or wait | Fowler |
  | 3 | **Measured at production volume, not on the canary**, which holds hundreds of times fewer rows than the question is about; **the pass line is written before the run**, so the reading is compared with a line and not with itself | Carmack |
  | 4 | **The measurement is part of this row, and the row merges on a miss too.** The two parts need the same upstream rows, so merging them adds no wait, and a miss holds only the rows that would call the door | Fowler, Carmack |
  | 5 | **The timing runs under `gate_lock.py --require-lock`, not a paused pool.** The lock covers the whole machine; a paused pool stops nothing in plans 50, 51 and 55 | Carmack |
  | 6 | **The engine's add-on reaches a browser spec from the prepared shared cache.** Setup may download it before tests; global setup only checks it, and the engine checks its signature | [Run the gates](../docs/how-to/run-the-gates.md#the-frontend-gates) |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Each route row edits the registry | Four rows serial on one contract file, and a column two routes read has two claimants | Route rows one at a time | Fowler |
  | 2 | Leave the registry for row 11 | Every route row would draw a column the registry still calls unread | A false registry for the length of the plan | Fowler |
  | 3 | Recorded query answers inside browser specs | The door is never tested in a browser; it is a mock (Guardrail #7) | A test-only switch in shipped code | Carmack |
  | 4 | One browser context per test worker | Test isolation goes, and the engine still starts on every page load | A reset step in every spec | Carmack |
  | 5 | A SHA-256 of the add-on in config | It pins bytes no reader gets and is edited on every engine update, while the engine already checks the add-on's signature | One config value and its upkeep | Carmack |
  | 6 | Measure inside a route row and set a budget knob from the reading | The canary is too small to show the cost, and a budget set from its own reading can never fail | A trigger that cannot fire, and route rows built before the door's shape is known | Carmack |
  | 7 | Time the draw in CI | The runner is shared by four test workers, so wall-clock there is load, not the page | A red build nobody caused | Carmack |

---

### Row #5 - The band reads the ledgers and carries the settings changes, and the three remaining projections nothing draws go

- **Scope:** section 2.6, less the aggregate retirement carried by #1189 (row 12). In `backend/idhazh/telemetry/publish/console_band.py`: the machine facts read `state/host-fingerprint/` (the comment naming `machine/` is corrected); the site size is read from `run.json` and the article count from `state/day-metrics/`, never from `digest.json`; the months list names the `telemetry` months only. Then the `machine`, `run-days` and public `day-metrics` projections go with their producers, contracts, knobs, copy-step entries, publication checks and canary calls; `state/day-metrics/` stays. The migration tool stays: Plan 58 widened it to every ledger still on CSV, so it is deleted by Plan 59 row "The item health summary moves to the door, or stays CSV by ruling", when no ledger a program writes is left on CSV.
- **Files touched:**
  - `backend/idhazh/telemetry/publish/console_band.py`, `settings_moved.py` (new), `machine.py`, `run_days.py`, `day_metrics.py` (the public half only), `dispatch.py`, `series.py`
  - `backend/idhazh/contracts/console_band.py`, `backend/idhazh/contracts/fingerprint.py` (read only unless a name moves), `backend/idhazh/contracts/machine_shard.py`, `backend/idhazh/contracts/public_run_day.py`, `backend/idhazh/contracts/console_payloads.py`, `backend/idhazh/contracts/__init__.py`, `backend/idhazh/contracts/knobs/observability.py`, `backend/idhazh/config.py`, `backend/idhazh/path_classes.py`
  - `backend/idhazh/publication_checks/checks/console.py`, `backend/utilities/build_canary_day.py`
  - `frontend/src/lib/console/band.ts`, `frontend/src/lib/console/settings-moved.ts`, `frontend/tests/settings-moved.spec.ts`, `frontend/tests/console-band.spec.ts`, `tests/fixtures/settings-moved/five-on-one-day.json`, `tests/fixtures/settings-moved/five-on-one-day.expected.json` (new), `tests/fixtures/contracts/console-band/newest-day.json`
  - `config/idhazh.json`, `frontend/scripts/copy-visuals.mjs`, `.gitignore`, `.github/workflows/digest.yml`
  - `backend/tests/test_console_payloads_producer.py`, `backend/tests/contracts/test_console_band_fields.py` (new, the field-set binding), `backend/tests/telemetry/test_settings_moved.py` (new), `backend/tests/contracts/test_app_config.py`, `backend/tests/contracts/test_gardener_config.py`, `backend/tests/contracts/test_stamped_boundary.py`, `backend/tests/pipeline/test_day_shards.py`, `backend/tests/workflows/_harness.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `docs/architecture/publishing/console-payloads.md`, `docs/architecture/publishing/retention.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/concepts/config/retention-ages.md`, `docs/concepts/adaptive-pruning.md`, `docs/concepts/growing-reads.md`
  - **At dispatch the worker re-runs the searches for `machine_shard`, `MachineShard`, `public_machine_keep_months`, `PublicRunDay`, `public_run_day`, `public_run_days_keep_months`, `public_day_metrics_keep_months`, `publish_public` and the literal paths `"machine/"`, `run-days/` and `day-metrics/<YYYY-MM>`, adds every match outside `state/`, `corpus/` and `TODO/` to this list, and says so in the pull request**
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests`, `npm --prefix frontend run test:changed -- --list` then the selected checks; `idhazh check-publication` over the canary tree; the browser smoke on `/console/` and `/console/machine/` (the band). CI runs the full suite. **Merge window.**
- **Oracle:** **the band says the same as before, plus the two new fields.** Over the canary tree the band before and after is equal field for field except `months` (the telemetry months only), `settings_moved` and `checker_moved`. Both languages return `five-on-one-day.expected.json`. A band without either new key validates to `None`. After the row no path under `build/` starts with `machine/`, `run-days/` or `day-metrics/`. **Once, in the pull request and not as a test**: over the committed record, `settings_moved` names the prompt changes of 14 to 18 and 24 September, and `checker_moved` names 23, 24, 26 and 29 August and 24 September, with `score_moved` true on 26 and 29 August only. It cannot settle whether the lines read well on a chart; the route rows do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The settings line reads the run manifests, through the band** (owner ruling R3, default B1). `item-health` cannot see the prompt, the chat template, the reply shape, the runtime build or the weights' hash: measured 2026-09-28, a rule read from it missed the prompt changes of 14 to 18 and 24 September and drew five false lines | Andre |
  | 2 | **The band never opens `digest.json`**: 2.25 s median a run against 0.28 s through `day-metrics`, measured 2026-09-28 on this machine | Carmack |
  | 3 | **The three remaining projections go before any panel moves.** The aggregate projection and its page reader are carried by #1189 (row 12) | Fowler |
  | 4 | **The band's reads are bounded to the span plus one walk-back of the same length**, never the whole ledger (Guardrail #12) | Fowler |
  | 5 | **One rule in two languages, checked against one expected fixture** | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Move the projections under `state/` | A pre-shaped copy under `state/` is still a pre-shaped copy (N7) | A second writer of every fact they hold | Fowler |
  | 2 | Keep each change's values beside its names | Measured on the 15 recorded days: 8 change days, 1 to 21 names each, so 90 days of names is an estimated 2.4 KB compressed; a 64-character hash per change would make the field several times larger | The band's ceiling several times over | Carmack |

---

### Row #6 - Pipelines asks the ledger

- **Scope:** every Pipelines panel in section 2.7, in its order, with its id, frame, gate attributes, driver, expectations, `judged` entry, built-page expectations and words (section 2.7b); `frontend/tests/console-pipelines-nothings.spec.ts` for its build-time panels; the page moves onto `__CONSOLE__` and its server load drops `console` and `panelGroups`; `DRAWS_NO_PANEL_ID` goes from `panel-captures.spec.ts`. `/console/` stops fetching `telemetry/<YYYY-MM>.csv` and stops reading `run-timeline/`, `state/span-rollup/` and `data.months`. It passes `rule` to its `KpiCard`s and `stages` to `failure-mix`'s list, and rewrites the scripts-off case in its `console-chart-pending` expectations. Its own specs import `test` from `door-page`.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/+page.server.ts`, `frontend/src/routes/console/RunTimelinePanel.svelte`, `frontend/src/routes/console/RunHealthPanel.svelte`
  - `frontend/src/lib/console/pipelines/` (new directory: one component and one pure module a moved panel)
  - `config/console/pipelines.json`, `frontend/tests/support/panel-drivers/pipelines.ts`, `frontend/tests/support/console-expect/<spec>/pipelines.ts`, `frontend/tests/panel-captures.spec.ts`, `frontend/tests/console-pipelines-nothings.spec.ts` (new)
  - `frontend/tests/console-item-cost.spec.ts`, `console-pipeline-timeline.spec.ts`, `console-substeps.spec.ts` (deleted: the span sub-steps go), `console-telemetry-heal.spec.ts`, `console-reserved.spec.ts`, `console-flow.spec.ts`, `extraction-trend.spec.ts`, `extraction-window.spec.ts`, `time-split.spec.ts`, `console-run-health.spec.ts` (each under `frontend/tests/`), and every other spec that visits only `/console/`
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md`, `docs/architecture/publishing/how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md`, `docs/architecture/publishing/run-timeline.md`
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, the `panels` group included. The browser smoke on `/console/` at 390, 768 and 1440 in both themes: zero new `[error]`, zero new `404`, every moved panel draws each state when its fetch is refused, and the page still renders with its data absent. The consult of section 2.1. CI runs the full suite. **Before it merges, the live-data check of section 1.**
- **Oracle:** **each moved panel draws from a recorded slice what section 2.7 says.** `failure-mix` one stack a day, and the list ranks `failed_rule` for the chosen stage; `run-timeline` the offsets `run_timeline.py` computed for the canary run; `slower-on-same-work` one point a day on the reference machine, named; `article-age` excludes an inferred time and counts it in the lede. `/console/` makes no request for `telemetry/`, `run-timeline/` or `span-rollup/`, and its built page passes `console-built-page.spec.ts`. It cannot settle whether the panels are worth their place; the consult does.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **One pull request for the route.** Its page and server load are one surface | Fowler |
  | 2 | **The run timeline's detailed sub-steps were removed by #1189.** [The item command](../docs/concepts/telemetry.md#the-committed-traces-briefly) provides retained detail for one item; this row does not remove them again | Susan |
  | 3 | **The items-per-minute figure returns above the run timeline as its lede**, the price of replacing panel 3 | Susan |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Delete the `telemetry` and `run-timeline` projections here | Their producers share backend files with rows 5 and 12 | This row serial with both | Fowler |

---

### Row #7 - Summaries asks the ledger

- **Scope:** every Summaries panel in section 2.7 and section 2.7a, with ids, frames, gate attributes, driver, expectations, `judged` entries, built-page expectations and words; `frontend/tests/console-model-nothings.spec.ts` for `model-cards` and `doubt-reasons`; the page moves onto `__CONSOLE__`, and `/console/model/+page.server.ts` keeps `reasonDays`, the `day-metrics` reads behind `model-cards`, and config values. It passes `rule` to its `KpiCard`s and `stages` to `refusing-rule`'s list. Its own specs import `test` from `door-page`.
- **Files touched:**
  - `frontend/src/routes/console/model/+page.svelte`, `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/lib/console/model/` (new directory), `frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/console/model-cards.ts`, `frontend/src/lib/console/doubt-reasons.ts`, `frontend/src/lib/components/ThroughputTrend.svelte` (its step gives way to the settings line; the median rule)
  - `config/console/model.json`, `frontend/tests/support/panel-drivers/model.ts`, `frontend/tests/support/console-expect/<spec>/model.ts`, `frontend/tests/console-model-nothings.spec.ts` (new)
  - `frontend/tests/console-model.spec.ts`, `model-cards.spec.ts`, `console-model-instruments.spec.ts`, `console-throughput.spec.ts`, `console-ranked.spec.ts` (its Summaries cases), and every other spec that visits only `/console/model/`
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md`
- **Acceptance gates:** as row 6, on `/console/model/`. `KpiCard` also sits on Pipelines' `at-a-glance`, so the `/console/` pictures are in the selected set.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `call-ending` stacks `length` at the bottom; each of the eight instruments appears where section 2.7a puts it with `Nothing acts on these numbers.`; `model-cards` keeps its title `What the model did` and its eleven labels, and the twelfth is the label `eval-instruments.ts` gives `determinism_violation`; over a band fixture carrying checker changes on 23, 24, 26 and 29 August and 24 September with `score_moved` true on 26 and 29 August, `faithfulness` draws dotted lines on 26 and 29 August only and `doubt-reasons` draws all five.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The eight instruments go where section 2.7a puts them**, with no threshold, tint or direction | Andre |
  | 2 | **The model cards keep their build-time read** | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep "Measured, and nothing acts on it" as a list | A backlog is not an operator's question | Zero; costs the route a panel of chores | Susan |
  | 2 | Rebuild the cards' three distinct counts from `scores` and `item-health` in the browser | Measured over the committed record, the rebuilt count disagreed with `day-metrics` on 11 of 35 days, once by 143 | Cards that print a different number from the record | Andre |
  | 3 | Put three instruments behind a switch on `faithfulness` | A switch changes the chart type over one query result; three measures with their own scales and directions are three results, and `coherence` runs from -1 to 1 where the faithfulness axis starts near 65 percent | The tail the panel exists to show | Andre, Susan |

---

### Row #8 - Voices asks the ledger, and the ranking panels join it

- **Scope:** every Voices panel in section 2.7, in its two groups, with ids, frames, gate attributes, driver, expectations, `judged` entries, built-page expectations and words; `frontend/tests/console-voices-nothings.spec.ts` for its build-time panels; the page moves onto `__CONSOLE__`. `feeds-failed` absorbs panel 22; `ranking-discount` is redrawn on its build-time view; `why-chosen` and `watchlist` arrive from Susan's Pipelines verdicts. Its own specs import `test` from `door-page`.
- **Files touched:**
  - `frontend/src/routes/console/voices/+page.svelte`, `frontend/src/routes/console/voices/+page.server.ts`
  - `frontend/src/lib/console/voices/` (new directory)
  - `config/console/voices.json`, `frontend/tests/support/panel-drivers/voices.ts`, `frontend/tests/support/console-expect/<spec>/voices.ts`, `frontend/tests/console-voices-nothings.spec.ts` (new)
  - `frontend/tests/console-voices-feeds.spec.ts`, `console-voices-retiring.spec.ts`, and every other spec that visits only `/console/voices/`
  - `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`
- **Acceptance gates:** as row 6, on `/console/voices/`.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `feeds-failed` fires an article tile for a canary `429` and a `network_error` and prints `mostly rate limited`, and its axis ends at the older of the two rows' newest days; `fetch-time`'s segments sum to its bar; `why-chosen`'s five parts sum to `selection_score` within 0.000001 for every drawn row, each `item_id` taken from its newest run.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Panel 22 folds into panel 18** | Susan, Jony |
  | 2 | **`ranking-discount` reads the source-health view**, because `item-health` has no row for the feeds it exists to show | Susan, Jony |
  | 3 | **`why-chosen` and `watchlist` sit here**, beside the ranking panel, not on Pipelines | Jony, Susan |
  | 4 | **It starts after row 4 alone.** Voices draws no settings line, so it does not wait on the band | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Tint each fired article tile by its status class | A class is coarser than the fix - a 404 and a 429 are both 4xx and are fixed differently - and a colour per class needs a second key a 6 px tile cannot carry | A key the feed row does not share | Susan, Jony |
  | 2 | Draw `ranking-discount` from `item-health` | A feed whose reads failed has no row there, and those are the feeds the discount exists to show; any hand-set `feed_weight` under 1.0 would also draw a bar past the floor | The panel's subject | Susan, Jony |
  | 3 | Hold panel 18 until `feed-health` is published | The article row is the half the verdict found missing | The reader waits a plan for it | Susan |

---

### Row #9 - Hardware asks the ledger, and its page carries no data

- **Scope:** every Hardware panel in section 2.7 except `platform-mix`, and the route sentences under that table. Owner ruling R2's default A: the built page follows section 2.4, "The built page", with no exception; `/console/machine/+page.server.ts` returns config and words only, and the page moves onto `__CONSOLE__`. It rewrites the scripts-off case in `console-machine-page.spec.ts`. `CLOCKS_AGREE_WITHIN_PCT` becomes `machine.knobs.clocks_agree_within_pct`; the constant stays in `frontend/src/lib/charts/machine.ts` and `frontend/src/lib/server/machine-counters.ts` for row 11 to delete. Its own specs import `test` from `door-page`.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`, `frontend/src/routes/console/machine/+page.server.ts`
  - every `*Panel.svelte` under `frontend/src/lib/console/machine/` except `PlatformMixPanel.svelte`, and `article-cost.ts`, `context-cost.ts`, `disk-reads.ts`, `memory-held.ts`, `processor-lost.ts`, `prompt-reuse.ts` in that folder
  - `config/console/machine.json`, `frontend/tests/support/panel-drivers/machine.ts`, `frontend/tests/support/console-expect/<spec>/machine.ts`
  - `frontend/tests/console-machine.spec.ts`, `console-machine-page.spec.ts`, `console-machine-panels.spec.ts`, `console-machine-split.spec.ts`, `console-machine-data.spec.ts`, `console-article-cost.spec.ts`, `console-timings.spec.ts`, and every other spec that visits only `/console/machine/`
  - `docs/architecture/publishing/console-machine.md`, `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md` (with panel 4's note in its design rationale)
- **Acceptance gates:** as row 6, on `/console/machine/`, plus: a cold visit and a move from Pipelines each draw the band and every panel, and nothing above the first panel moves when the data arrives, at 390 and 1440 px.
- **Oracle:** each moved panel draws from a recorded slice what section 2.7 says; `slower-machines` draws two lists, one row per `cpu_model`, each rate divided by the same run's reference median; `two-clocks` marks a shard past the knob `disagrees`; `closest-to-memory` fills to the memory held and ends at the machine's total; the lost state appears for the canary day with `item-health` rows and no `host-fingerprint` rows; the served HTML of `/console/machine/` passes `console-built-page.spec.ts`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A prerendered page with no ledger data, not off prerender**, until the owner rules R2 | Susan, Carmack, Jony |
  | 2 | **Panel 7 takes a new id and title**: its old id named another panel, and its old title read like Pipelines' panel 3 | Susan, Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Take Hardware off prerender in this row | It is owner ruling R2, and option B's costs - a blank first paint, HTTP 404, nothing with scripts off, a fifth serial request - are the owner's to accept | A new row after row 11 if the owner rules B | Susan, Carmack, Jony |
  | 2 | Draw `slower-machines` as one total a kind | One kind reads a token in 37 percent of another's time and writes one in 145 percent of it, so a total says the two are the same | The panel's finding | Carmack |

---

### Row #10 - The `telemetry` and `run-timeline` projections go

- **Scope:** `frontend/public/telemetry/` and `frontend/public/run-timeline/`, with their producers `public_telemetry.py` and `run_timeline.py`, contracts `PublicTelemetryRow` and `RunTimelineRow`, knobs, the gardener's `public-copy` series in `config/gardener/telemetry-aggregate.json`, copy-step entries, publication checks, the `telemetry/` page-weight ceiling and the canary's projection step. **The band's `months` field goes**: `ConsoleBand` refuses unknown keys and CI reads the committed band, so a `mode="before"` validator drops `months` from an older band, with its removal condition on its line (`delete when no committed band carries months`); `version` stamped, changelog rotated as row 5 did. `band.ts` already reads a band without `months`.
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
  - **The docs half splits by file**: one worker carries the code and tests, and further workers take about ten docs each in the same checkout
- **Acceptance gates:** local `ruff check .`, `mypy backend`, `pytest backend/tests`, `npm --prefix frontend run test:changed -- --list` then the selected checks; `idhazh check-publication` over the canary tree. CI runs the full suite. **Merge window.**
- **Oracle:** no path under `build/` starts with `telemetry/` or `run-timeline/`; a band written before this row and one written after both validate; the built site is smaller by the two directories, measured and written in the pull request.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`months` is removed with a read-side validator, not left in place.** `ConsoleBand` refuses unknown keys and CI reads the committed band, so without the validator a band written before this row fails the build (CLAUDE.md section 11) | Fowler |
  | 2 | **These two go after Pipelines moves**, because Pipelines' panels are their last readers. The separate aggregate retirement is carried by #1189 (row 12) | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Merge this row with row 11 | This row runs beside rows 7 to 9 today; merged, it waits for every route row and takes on row 11's size | One pull request saved | Carmack, Fowler |

---

### Row #11 - ECharts leaves

- **Scope:** `echarts` is uninstalled. Deleted: `frontend/src/lib/charts/Chart.svelte`, `engine.ts`, `core.ts`, `frontend/src/lib/server/chart-render.ts`, and every module under `frontend/src/lib/charts/` whose only purpose was an ECharts option (`chart-flow.ts`, `extraction-trend.ts`, `stacked.ts`, `waterfall.ts`, `fleet.ts` if it still holds an option); the engine code and `CLOCKS_AGREE_WITHIN_PCT` are removed from `machine.ts`, `glance.ts` and `cost.ts`, which kept components still import. Deleted also: every module under `frontend/src/lib/` whose last importer a route row removed - the build-time readers in `frontend/src/lib/server/` no route calls and `Viewport.svelte` among them; the month functions in `waiting.ts`; `settingsMoved`, `inputsMoved` and the TypeScript half of the settings test; the branches of `KpiCard` and `FailureList` that serve a caller passing no `rule` or `stages`. `COLUMN_READERS` loses any entry naming a deleted file. Every `console.*` knob no reader reads leaves `config/appearance.json` and `ConsoleConfig` (`console.pan_days`, `console.zoom_factor` and any other the search finds). The cross-route docs stop naming the engine. The aggregate reader is carried by #1189 (row 12) and is not deleted again here.
- **Files touched:** the modules above; `frontend/package.json`, `frontend/package-lock.json`; `frontend/scripts/bundle-gate.mjs`; `backend/idhazh/contracts/item_health.py`, `backend/idhazh/contracts/host_fingerprint.py`, `backend/idhazh/contracts/knobs/console.py`, `config/appearance.json`, `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/machine-counters.ts`, `tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`; `frontend/src/lib/console/waiting.ts`, `frontend/src/lib/console/settings-moved.ts`, `frontend/tests/settings-moved.spec.ts`, `frontend/src/lib/components/KpiCard.svelte`, `frontend/src/lib/components/FailureList.svelte`; the seventeen cross-route specs of section 2.2 where they name the engine; `docs/concepts/design-system.md`, `docs/architecture/publishing/console.md`, `frontend.md`, `console-charts.md`, `ui-shell.md`, `which-console-surfaces-follow-the-window-and-which-say-why-not.md`, `what-the-quality-and-source-panels-draw.md`, `docs/how-to/run-the-gates.md`, `docs/concepts/telemetry-intent.md` (N5's column). The worker lists every deleted module in the pull request, from `git grep -l echarts -- frontend` and an importer search per module.
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, `npm --prefix frontend run check`, `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`; the bundle gate. CI runs the full suite.
- **Oracle:** **`git grep -n echarts -- frontend/src frontend/package.json` finds nothing**, the build succeeds, every console route draws in the browser smoke, and every byte of one cold visit to `/console/` and to `/console/machine/` - the engine included - is measured before and after and written in the pull request.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **`machine.ts`, `glance.ts` and `cost.ts` lose their engine code, not their files.** Kept components import their other helpers | Susan |
  | 2 | **Shared modules, unread knobs, the month functions, the TypeScript settings port and the compatibility branches are deleted here**, so no two route rows delete the same file. The aggregate reader is carried by #1189 (row 12) | Fowler |

---

### Row #12 - Aggregate retirement carried by #1189

The complete aggregate retirement, its public copy, its Pipelines reader and
the item command are complete in merged PR #1189. This row stays COLLAPSED;
do not dispatch another deletion here.
The current command, retention rule and reason for removing the four figures
live in [telemetry](../docs/concepts/telemetry.md).

## What this plan inherits and must close

| # | Inherited from | Closed by |
| --- | --- | --- |
| 1 | Plan 51: four routes draw no panel id | rows 1 (structure), 3 and 6 to 9 (ids) |
| 2 | Plan 51: `echarts` stays installed while two grammars coexist | row 11 |
| 3 | Plan 50's row **The three ledgers the console's routes read become parquet**: `backend/utilities/migrate_to_parquet.py` carries "delete when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`" | superseded: Plan 58 widened the tool to every ledger left on CSV; Plan 59 row "The item health summary moves to the door, or stays CSV by ruling" deletes it |
| 4 | Plan 50's collapsed aggregate migration: delete the family rather than migrate it | completed by #1189; row 12 stays COLLAPSED |
| 5 | Telemetry-intent N7 and N8 | rows 5 and 10; the band is owner ruling R1 |
| 6 | The [shared readout rules](../docs/concepts/console-design/the-rules-every-console-chart-obeys.md): remove the house-style components' remaining native tooltips when they gain their readouts | row 2 |
| 7 | Plan 50's open questions: `similarity-ledger.ts` is a second name | row 3. **`scores` renamed `summary-quality`** stays the owner's call: a directory rename is a data migration |

The placeholder's section "The shape this plan is expected to take", which plan 50 cites, is section 1 of this plan.

## Found while planning, handed to the plans that own them

| # | What | Owner |
| --- | --- | --- |
| 1 | The migration row took `payload.ts`'s two ledger reads. Still outside its file list: `day_metrics.read_health_rows`, which `console_band.py` reads, and `day_shards.settled_day` in `run_timeline.py`, `machine.py` and `public_telemetry.py`. Moved without them, the band's machine verdict and the two projections read nothing until rows 5 and 10 delete them | plan 50, row titled **The three ledgers the console's routes read become parquet** |
| 2 | Preserve the shipped `platform-mix`: move its config, drivers and expectations with the route declarations; adapt its chart props; declare and register `platformMixQuery` with its caller; then complete route integration | row 1 for the route split, row 2 for chart props, row 4 for the query and caller, and row 9 for route integration |
| 3 | Measure the shipped query reader and page cache at the console's real volume | row 4, **Every panel's question is declared before it is drawn, and the door is measured at the console's real volume** |
| 4 | Plan 55's rows 1 and 2 start after row 1 here and share files with later rows (section 1). Its route needs `config/console/data-explorer.json` with its page, a `console-expect/<spec>/data-explorer.ts` for each spec that lists routes (`null` where there is nothing to check), and one line in each `console-expect/<spec>/index.ts` and in `panel-drivers/index.ts`; `npm run check` names every index it misses | plan 55 |
| 5 | CLAUDE.md section 1a says every config file is a Pydantic model; the owner ruling of 2026-09-21 says a project-authored config file declares only what its readers compute on. A one-line amendment | the owner |

## See also

- Plan 50 - the ledgers, the compaction and the migration this plan reads through - is deleted now that it has closed. Its last copy is `git show 7bb8174d3:TODO/20260924-50-idhazh-gardener-plan.md`, and its section **Row #10** holds the `span-rollup` measurements.
- [The query reader](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md) - query, reach, cache and publication behavior.
- [The chart vocabulary](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md) and [chart and readout rules](../docs/concepts/console-design/the-rules-every-console-chart-obeys.md) - the drawing contracts.
- [The design system](../docs/concepts/design-system.md) and [run the gates](../docs/how-to/run-the-gates.md) - sufficiency, panel pictures and browser setup.
- [The Data explorer](../docs/how-to/query-a-ledger-from-the-console.md) - the delivered sixth console route; its shared chart slice is #1503.
- [`../docs/concepts/telemetry-intent.md`](../docs/concepts/telemetry-intent.md) - N2 to N8.
- [`../docs/concepts/console-design/how-a-console-chart-gets-its-data.md`](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the rules every panel here is built to.
- [`../docs/architecture/publishing/console-payloads.md`](../docs/architecture/publishing/console-payloads.md) - what the console reads today, and the projections this plan deletes.
