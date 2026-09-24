# Plan 51 - The console fetches and draws its own data

**Last Updated**: 2026-09-24

**Level**: 5 (CLAUDE.md section 6). Row 3 decides whether `state/` reaches a browser, which is a publishing contract. Rows 1 and 2 are Level 3 and Level 2 and carry no contract change beyond one copied settlement key.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3 and N5 - the browser queries the store for the slice it draws, fetches at view time, and d3 draws it. **Contract**: section 2 declares every shape, key, signature and config literal these three rows need. **Code**: the three rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 - rows 1 and 2 share no source file and row 3 waits on row 1; merge each pull request before dispatching the next; consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The Hardware route counts every job twice, its span control sits fifteen panels above the reader who wants it, and every chart on the console is drawn from data baked into the page by the build. This makes one panel prove the whole chain - query the store in the browser, draw it in d3 - and writes the house style the rest follow. |
| Hard scope - in | - `state/host-fingerprint/` is read settled, so a job counts once.<br>- The five-tab console strip sticks, and the span control rides on it.<br>- `state/host-fingerprint/` becomes parquet and reaches the browser, which queries it for the columns and days one panel draws.<br>- `frontend/src/lib/data/` holds the one query door every later panel uses; `frontend/src/lib/charts/d3/` holds the house style every later chart uses. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A tenth prerendered route, or retiring an existing one.<br>2. A charting library that is not d3.<br>3. A new committed payload under `frontend/public/`.<br>4. A measured figure that contradicts section 3.<br>5. Any change to `ConsoleBand` beyond the one additive field row 3 declares - it is the payload every console route fetches first.<br><br>**"How the browser reaches the bytes" was trigger 1 and is settled**, 2026-09-25: the staging step copies the compact tier of every published store plus the unclosed raw days into gitignored `frontend/static/state/`, and `console/band.json` - which the console layout already fetches first - carries the store map. |
| Chosen strategy | Correct the number first, move the chrome second, change the grammar last. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The other fourteen panels on `/console/machine`, and the four other console routes | Two grammars coexist on one route: one panel queries parquet and draws in d3, fourteen read CSV at build time and draw in ECharts. `echarts@^5.6.0` stays installed with fifteen importers | The charting plan, which starts from row 3's house style instead of inventing one. **Row 3 exists to make that plan cheap, not to be it** |
| Taking any route off `export const prerender` | Nine files under `frontend/src` keep it. Row 3's panel fetches after mount on a page that still prerenders, which is legal and is what lets one panel prove N3 without moving a route | The plan that moves a whole route, which owns the first-paint and no-script questions for every panel on it |
| Retiring the nine payloads under `frontend/public/` | Telemetry-intent N7 and N8 get no stone here. `frontend/public/machine/<YYYY-MM>.csv`, the `machine-shard-row` fold of `host-fingerprint` joined to `item-health`, keeps being published | The same whole-route plan. Retiring a published payload needs every reader moved first |
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
| 3 | One panel end to end: parquet at rest, queried in the browser, drawn in d3 | 1, and plan 50's row titled "The payload store, the two roots, and two stores moved to parquet" | B | PENDING | - | - | - |

**Rows 1 and 2 run two-wide and the one file that decides it is `frontend/src/lib/console/machine/PlatformMixPanel.svelte`. Row 1 owns it.** If row 2's shell change reaches that file, row 2 waits. Every `Files touched` entry below names a file, never a directory, because readiness is computed by diffing those lists ([execute-a-plan.md](../docs/how-to/execute-a-plan.md)). The one exception is a directory a row creates that no other row in either plan touches, marked on its own line.

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

**`StoreName` maps to an address inside this module and nowhere else.** The door composes `${base}/state/<store>/<YYYY-MM>.parquet?v=<band.generated_at>` for each month `band.stores[store].months` lists, and `${base}/state/<store>/<YYYY-MM-DD>/<NN>.parquet?v=...` for each open day, `NN` running from `0` to `files - 1`. `base` is SvelteKit's own repository prefix, because getting that wrong is the commonest failure on this host. A panel that could name a path could name any path, and the staging allow-list would stop being the bound.

**Whole files are fetched and handed to the engine as buffers**, the same way the month search index already is. No byte ranges. Column projection then saves parse time rather than bytes, and the plan says that rather than implying the fetch got smaller.

**Cost, one store over 90 days: about 9 requests in two round-trip waves.** One of them is the band, which `+layout.ts` already fetches. Three stores is about 27 requests and roughly 445 ms of round trip at the measured 89 ms edge.

**The browser cannot list a directory, and every committed file is named `<uuid8>.parquet` in both tiers.** Owner ruling, 2026-09-24: telemetry-intent N9 binds every tier. The committed tree is not changed to suit a reader.

**There is no index to invent. `console/band.json` is already the address book, and `frontend/src/routes/console/+layout.ts` already fetches it before any panel mounts.** Its contract has said so since 2026-09-09, in its own words: *"The months list rides along and that is the point. A shell cannot ask for a month until it knows which months exist, so a band that left the list out would make the list a second serial hop and the first month a third."* It already carries `months`, `covers_through`, `compaction_lag_days`, `rows_uncompacted` and `generated_at`, and it has a 2,000-byte ceiling. **This row adds one field to it, and no new file anywhere.**

**N9 binds a telemetry payload in a tree under `state/`, not a published address.** Its own text settles it twice: the thing it replaces is `<date>-<run>-<attempt>-<job>-<shard>.csv`, a parsed payload name, and its last three words are *"nothing reads it"* - which a file whose whole job is to be read is not. N11 scopes it explicitly to trees under `state/`, and plan 50 section 5.4 makes that structural by raising on any second segment that is not `raw` or `compact`.

| # | What is written | By whom | Where | At what name |
| --- | --- | --- | --- | --- |
| 1 | Raw shard | the producing stage, through plan 50's door | committed | `state/raw/<store>/<YYYY>/<MM>/<DD>/<uuid8>.parquet` |
| 2 | Compact shard | plan 50's fold task | committed | `state/compact/<store>/<YYYY>/<MM>/<uuid8>.parquet` |
| 3 | Published month | the staging step, **a byte copy of 2** | `frontend/static/state/`, gitignored, into `build/` | `state/<store>/<YYYY-MM>.parquet` |
| 4 | Published open day | the staging step, **byte copies of 1** for days the fold has not closed, sorted by name and numbered | same | `state/<store>/<YYYY-MM-DD>/<NN>.parquet`, `NN` zero-padded from `00` |
| 5 | The address book | `telemetry/publish/console_band.py`, generated whole every run | committed and staged | `console/band.json`, address unchanged |

**Row 3 is a byte copy, not a projection, and that distinction is what answers N7.** `frontend/public/machine/<YYYY-MM>.csv` is a projection: it is the `machine-shard-row` fold of one store **joined to** another. A byte copy joins nothing, folds nothing and drops no column, and N10 already blesses the compact tier as derived and rebuildable.

**The published bundle already runs four address grammars and two of them are unnamed by N8.** `digest/<YYYY>/<MM>/<DD>/digest.json` and `assist/index/<YYYY-MM>.json` are reader-facing, gated and shipped, and N8's replacement list names neither. So N11 cannot bind the published bundle without outlawing them - and it does not try to: it says *every tree under `state/`*. What N8 retires about the projections is the phrase **"in git"**, which is the committed copy and not the address.

**The band carries a count, never a filename**: `open_days: [{date, files: 4}]`. That keeps the band contract's own promise - none of it is an address, so no cell exists that fetched text could arrive in (Guardrail #11) - and nothing probes, because the count is declared and a 404 is a defect rather than a loop terminator.

**`generated_at` rides every data URL as `?v=`.** The current month's file and today's ordinal files change between builds and the host caches assets; the browse index lives with that staleness because a stale list is harmless, and telemetry staleness is not.

**Nothing new enters git.** The staged copies are created on the runner inside `npm run build`, copied into `build/` by the bundler, uploaded as the Pages artefact and thrown away with the runner. Ten directories under `frontend/static/` are gitignored and published exactly this way today. **Gitignored is not unpublished**, and the ignore line is doing N8's job.

| # | Why concurrent runs cannot collide here | |
| --- | --- | --- |
| 1 | A digest run writes `<uuid8>.parquet` into `state/` and pushes. It never stages and never builds | No job that commits also builds the site |
| 2 | Only `pages.yml` builds, and its build job is `cancel-in-progress: true` | One builder, always |
| 3 | The band and the files it names are produced from one checkout and shipped in one artefact | **Consistency by construction, not by locking** - adding runners upstream cannot break it |

**The band is generated whole on every run and never appended to**, which is how it is already written. An append would be read-modify-write on a shared path, the shape uuid8 exists to end.

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
| `console.fleet_top_kinds` | Exists | `4`, unchanged | Row 3's fold |
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

- **Scope:** both console readers of `state/host-fingerprint/` settle by key, and the fold line names the machines it folded. No backend change, no store change, no panel redesign, no parquet and no d3.

**Two defects, one pull request, because they are the same panel's two wrong sentences.**

**Defect 33 - the double count.** Every job writes its machine row in two halves by design: the hardware probe first, the clock after the last item. `ledger.extend_segment` says in its own docstring that it settles nothing and that `day_shards.settled_rows` decides what two rows of one key mean. `frontend/src/lib/server/host-fingerprint.ts` line 145 and `frontend/src/lib/server/machine-counters.ts` line 906 both call `readDayShards`, the plain reader, so both halves reach the page as two job placements - one carrying the machine and one carrying only `job_seconds`, which lands in `Other machines`. Measured 2026-09-24: 41 of 56 per-writer files over fourteen days hold exactly two rows, 41 of 205 rows, about a fifth.

**The fold line - `drawn as one bar: .`** `PlatformMixPanel.svelte` line 83 reads `series.at(-1)` for the folded names, but `fleet.ts` line 232 merges into an existing series and pushes nothing when the ramp has already folded, so the last series is a real machine whose `folded` list is empty. An optional chain swallows it. **The fold returns which series carries it rather than the reader guessing it is last** - guessing is what made this invisible, and a second reader would guess again.

- **Files touched:**
  - `frontend/src/lib/server/payload.ts` (section 2.1's key and rule, beside `ITEM_HEALTH_KEY`)
  - `frontend/src/lib/server/host-fingerprint.ts`, `frontend/src/lib/server/machine-counters.ts` (both move to `settledDayShards`)
  - `frontend/src/lib/charts/fleet.ts` (the fold names its own series)
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
  | 6 | The fold fix is structural, not a null guard. `?? []` on the empty list would make the sentence read `0 rarest kinds` and pass every gate | Guardrail #5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Settle in the producer so one row lands | Sound design, wrong defect. The producer cannot know the clock at probe time, which is why there are two halves | Its own plan, and it moves a persisted contract | Fowler |
  | 2 | Sweep every remaining raw `readDayShards` call in one row | Right instinct, wrong row. Each store needs its own ruling on which key settles it and whether the rule is a merge or a preference | A follow-up reading plan 50's section 5.8 map, store by store | Fowler |
  | 3 | Fold this into row 3 | Row 3 is parquet, a browser query and a redraw. A correction buried in a rewrite is a correction nobody can revert alone | Zero; costs the revert | Owner, 2026-09-24 |

---

### Row #2 - The console shell: a stuck tab strip, the span control on it, four named anchors

- **Scope:** the chrome every console route sits in, and **the sentence that says how complete the page is**. No panel changes, no store is read differently, and no data moves.

**Row 2 ships before row 3, and that ordering is the requirement rather than a convenience.** Every chart on the console draws the newest days that **exist**, not the last N days - so when data stops, a chart gains no gap at the right edge. It slides back in time and looks exactly as full as it did yesterday. Reader's verdict on that, 2026-09-24: *"I read a month-old chart, believed it, and closed the tab satisfied."* A page that can go quiet without saying so is worse than useless, so the sentence exists before anything starts fetching.

**The two sentences go in verbatim** and are computable today from fields that already exist - `covers_through`, `generated_at`, `compaction_lag_days`. **No contract changes for this.**

```
Complete to Monday 24 September. Today's runs are not in this yet.
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
  | 2 | **Folding the logo on scroll is refused.** It buys zero pixels because the header already leaves the screen, and scroll-linked motion has to be designed twice for reduced motion | Susan, 2026-09-24 |
  | 3 | **Folding the band is refused.** The band is what an operator reads on landing; folded, he opens a disclosure to learn that yesterday failed. Its worst-thing fragment rides in the stuck strip as one short line instead | Susan, 2026-09-24 |
  | 4 | It sticks at `frame.breakpoints_px[1]`, reusing the existing key. A stuck control must be one band at the width it sticks at: there the five tabs are one row, at 640 px two, at 360 px three | Susan. A second key naming 1024 is the duplicate this project rejects everywhere else |
  | 5 | Four named anchors beat one floating arrow. Fifteen panels sit in four declared groups, and named anchors work with no script at every width | Susan, 2026-09-24 |
  | 6 | This row does not touch `PlatformMixPanel.svelte`. Row 1 owns that file and runs beside this one | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Stick the strip at every width | At 640 px it is two rows and at 360 px three, and a stuck control that reflows eats a third of a small screen | Zero; costs the small-screen reader a third of the page | Susan |
  | 2 | A floating back-to-top arrow | It goes one place. Fifteen panels in four groups need four destinations, and an arrow needs script where an anchor does not | Zero; costs three of the four destinations | Susan |
  | 3 | Fold this into row 1 | Route chrome and a settlement-key change in one pull request, because both happen to be about one route | Zero; costs the independent revert | Fowler |

---

### Row #3 - One panel end to end: parquet at rest, queried in the browser, drawn in d3

- **Scope:** `state/host-fingerprint/` becomes parquet through plan 50's door; the browser queries it for the columns and days the Platform Mix panel draws; the panel is redrawn in d3; and the house style and query door every later panel uses are written here.

**Why this triple and not another.** The store has one producer (`telemetry/silicon.py`), one console reader, and is 76,306 bytes in 58 files. `frontend/src/lib/charts/fleet.ts` has exactly two importers, against four for the next candidate. And the panel already takes an `svg` prop, which is the server-side renderer telemetry-intent N5 says exists only to serve ECharts - so this one panel is also the first evidence it can go.

**The house style and the query door are the deliverable. The panel is the proof.** A change that ships one good panel and no shared parts has bought one panel and left the next fourteen where they were ([how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) rule 1, which decides any scope argument inside this row).

#### The panel this row delivers

Ruled by Susan on 2026-09-24 against the panel as it stands, whose verdict was SEND BACK: three of four sufficiency checks fail, two of five spans draw no mark, and the fold line ships a visible defect.

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
| Kinds that are not ramp-adjacent | do not fold. Folding the slowest into the middle is the one thing an ordered ramp cannot do |

**Cost, stated: three panels share machine colour, so all three move together and all three must print the rate.**

**Under `console.fleet_min_rows` the panel changes shape rather than switching off.** One mark per job - one column a day, one dot a job, coloured by machine - so all five spans draw something. The threshold's reason survives and is why this works: a bar over small counts reads as `this much` and invites a rate, where a dot per job reads as `these ones` and cannot, because every mark is an individual a reader can point at. **The sentence quoting `160` goes**: an internal knob is not a fact a reader can act on (CLAUDE.md section 0b).

**The readout stays a vertical column and moves beside the plot.** It carries names and counts, and counts compare down a right-aligned column in one eye movement. What was wrong was its position: the plot is 760 px inside a 1216 px content box at a 1536 px viewport, with 456 px standing empty beside it.

**What this row draws, in Susan's rank order:** say the machine is not recorded and sort that last, outside `Other machines`; drill through from a day or a mark to the jobs behind it, naming run, job, shard, machine, seconds and rate; one shape switch splitting by `job`; the speed ramp; the unit marks under the threshold; and last, a full-record context band showing where the open window sits.

- **Files touched:**
  - `backend/idhazh/telemetry/silicon.py` (writes through plan 50's door), `backend/idhazh/contracts/host_fingerprint.py` (`version` stamp, one `changelog` line)
  - `backend/idhazh/ledger.py` (`SegmentLedger.HOST_FINGERPRINT` leaves `write_segment`), `backend/idhazh/paths.py`
  - `frontend/scripts/copy-visuals.mjs` (the staging step joins the one that already stages into `frontend/static/`; **a second staging script is Guardrail #4**), `.gitignore` (an eleventh line beside the ten payload directories already there)
  - `frontend/scripts/build-canary.mjs` (the staging step reads its `STATE_ROOT` switch and **fails loudly when the root is missing**, because an empty store and a working store both render)
  - `frontend/scripts/bundle-gate.mjs`, `backend/tests/contracts/test_page_ceilings.py` (the new `state/` payload ceiling)
  - `frontend/package.json`, `frontend/package-lock.json`
  - `frontend/src/lib/data/store.ts` (new, section 2.2 - **the only module that imports the engine**)
  - `frontend/src/lib/charts/d3/scale.ts`, `axis.ts`, `ordered-colour.ts`, `motion.ts`, `empty.ts` (new directory, no other row in either plan touches it)
  - `frontend/src/lib/charts/fleet.ts` (the option builder becomes a d3 draw), `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, `frontend/src/lib/server/host-fingerprint.ts`
  - `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py` (section 2.4)
  - `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-data.spec.ts`, `frontend/tests/console-cold-load.spec.ts`
  - `docs/architecture/publishing/console-charts.md`, `docs/architecture/publishing/what-a-month-shard-holds-and-how-it-reaches-a-browser.md` (a scope clause on its two rejected-alternative rows, which were ruled for the search vector file and not for slicing a telemetry store)
- **Acceptance gates:** the browser smoke on `/console/machine` (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, **the panel still renders when its store is absent, empty, or when the engine fails to start**. `ci.yml`'s bundle gate and site-cap measurement both walk the built tree, so both are re-read after the staging step lands. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/telemetry -q`. CI runs the full suite.
  - **No measurement gates this row.** Two facts are owed and neither is a gate: whether the published host answers a byte-range request, which decides how the store is published rather than how it is read, and the engine asset's transferred size, which the site-cap budget consumes (section 3).
- **Oracle:** given a recorded `slice()` response for one fixture day, the d3 panel draws one mark per machine kind per day, with the kinds in median-throughput order, the unrecorded kind last and outside the fold, and every readout row carrying an absolute rate. **It is not a comparison against the ECharts panel**: this row rewrites `fleet.ts` from an option builder into a draw, so the old panel does not survive the commit, and the row's own scope changes the colour count, the shape under the threshold, the fold rule and the readout position - so "same colours, same labels" would be false by design. It cannot settle whether the drawing is good enough to ship; Susan rules that (CLAUDE.md section 14).
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
  | 10 | **The band is generated whole every run and never appended to**, which is how it is already written. An append is read-modify-write on a shared path, the shape uuid8 exists to end | Owner, 2026-09-24 |
  | 11 | The staging step joins the existing build chain between `copy-visuals` and `vite build`, and is not a new script. A second staging step is Guardrail #4, and the site-weight gate measures `build/` after `vite build`, so a step outside the chain would have the gate measuring a tree without the new bytes | Carmack |
  | 12 | **The reader sees today because the site rebuilds after every digest run, not because the fold ran.** The fold serves git; the build serves the reader. `pages.yml` fires on the content workflow and `digest.yml` runs five times a day, so a staged open day is hours old and is copied straight out of the raw tier with no fold involved | Fowler, reconciling Carmack's refusal of a daily fold with Reader's refusal of closed-periods-only |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `RecordGates` on `/console/judgement`, with `targetbar.ts` | Simpler drawing, but `targetbar` has four importers against `fleet`'s two, so the blast radius is larger for a smaller proof | Its own row later, once the house style exists | Fowler |
  | 2 | Keep the build-time read and swap only the drawing | It proves N5 and leaves N2 and N3 where they were, so the same panel gets done twice | Zero now; costs a second pass over one panel | Owner, 2026-09-24 |
  | 3 | Swap the drawing for every ECharts panel here | Fifteen importers, five routes and the server-side renderer in one pull request, before any house style has been reviewed | Its own plan | Fowler |
  | 4 | Delete `waterfall.ts` and `donut.ts` here | They are ECharts modules with no importer anywhere in `frontend/src`, found 2026-09-24 - real dead code and a free deletion, but not this row's question | A one-line change of its own | Fowler |
  | 5 | Commit the store's published copy under `frontend/public/` | Satisfies neither N7 nor N8, and it is the thing N8 exists to end | Zero; costs both intents and a merge driver | Carmack |
  | 6 | Serve the store from the repository over raw content | Zero published bytes, and cross-origin requests do work. But this project's own prune force-pushes `main` on a schedule, so a commit-pinned address stops resolving and a branch-pinned one changes under a reader mid-session | Zero; costs the reader a broken page after every prune | Carmack |
  | 7 | An index committed into `state/` beside the shards | **It is a shared mutable path**: every run rewrites it, two runs rewrite it at once, and the push race and the merge driver both return - which is precisely what per-writer names were introduced to end | Zero; costs the race back | Owner, 2026-09-24 |
  | 8 | Compute the `<uuid8>` from `(dataset, tier, covers_date)` so both sides derive the same name, and have no index at all | Elegant, and **it dies on N6 rather than on derivability**. A backfill can add rows to a closed day, the fold re-runs, and a computed name means different bytes at the same path - N6 broken at the one place it is load-bearing. You can have an immutable address or a rebuildable derived tier, not both | Zero; costs N6 | Fowler |
  | 9 | An index file the staging step generates | It was the answer until somebody read the payload the console layout already fetches. `console/band.json` has carried a `months` list since 2026-09-09 for exactly this reason, and inventing a second address book beside it is Guardrail #4 | Zero; costs a file nobody needed | Fowler |
  | 10 | Ask the host's own contents API for a directory listing | It is a service rather than a static asset, rate-limited per address, untestable offline, and it breaks if the repository is renamed. Guardrail #1 says a design must not need one | Zero; costs Guardrail #1 | Carmack |
  | 11 | Write an `index.html` into each month directory so the host lists it | It turns the host's limitation into the mechanism, and costs one round trip per store-month instead of one in total, plus 234 extra files | Zero; costs a round trip per month | Carmack |

- **The staging allow-list, which closes this row's old ESCALATE.** The staging step copies the compact tier of every store whose `StoreConfig.published` is true, plus the raw days the fold has not yet closed. Nothing else. `state/` in the repository stays the only source (N7) and nothing production lands under `frontend/` in git (N8), because the staged tree is gitignored and rebuilt each build. **The question of how the browser reaches the bytes is settled and is no longer an escalation.**

- **`ConsoleBand` gains one field**, and it is the only contract change in this plan: `stores: dict[Slug, StoreReach]`, where `StoreReach` carries `months: list[MonthStamp]` and `open_days: list[{date: DateStamp, files: int}]`. Additive and optional, so a band an earlier run wrote still validates and a panel with no entry draws `missing`. `version` stamped, one `changelog` line, and the frontend hand copy with its two binding tests in the same commit.

## Dependent plans

- `TODO/20260924-50-idhazh-gardener-plan.md`, the row titled **The payload store, the two roots, and two stores moved to parquet**, is row 3's predecessor. Nothing else in that plan is a predecessor here.
- `TODO/20260823-known-defects-plan.md`, defect 33, closes in row 1's pull request.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan lays stones for.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every row here is built to.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
