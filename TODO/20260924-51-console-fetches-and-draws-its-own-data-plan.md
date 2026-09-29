# Plan 51 - The console fetches and draws its own data

**Last Updated**: 2026-09-29

**Level**: 5 (CLAUDE.md section 6). Row 3 decides whether `state/` reaches a browser, which is a publishing contract, and sections 2.6 to 2.9 are the design contract the panels are built to. The other rows are Level 2 to Level 3 and carry no contract change beyond one copied settlement key.

**Chain** (CLAUDE.md section 0d). **Intent**: [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) N2, N3 and N5 - the browser queries the ledger for the slice it draws, fetches at view time, and d3 draws it. **Contract**: section 2 declares every shape, key, signature and config literal these rows need, so a worker builds each row with no further decision. **Code**: the eight rows.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as a worker returns and never waiting on a merge; serialise merges and re-check each branch against the advanced main; run the browser and build gates one at a time behind the shared gate lock (execute-a-plan.md, "the workers are parallel; the machine is not"); consult a persona only where two answers would lead to different code; AUTO-merge on green gates where no ESCALATE trigger fired; honor the ESCALATE triggers in section 0.

## Execution handover (zero-context cold start)

A paste-ready brief for an agent that picks this plan up with no prior context. [execute-a-plan.md](../docs/how-to/execute-a-plan.md) is the canonical contract; this brief adds only what this plan's run has learned. Written 2026-09-28, about 13:50 UTC, when the first owner handed over after row 5 merged.

```text
You are the OWNER of TODO/20260924-51-console-fetches-and-draws-its-own-data-plan.md.
You have no prior context. Execution is AUTHORIZED (owner, 2026-09-27): deliver it end
to end with a running pool, settle any ambiguity by debate (two or more personas from
.github/agents/, asked in parallel, converging on one ruling), record every deviation in
the table below, and stop only on an ESCALATE trigger (section 0).

STEP 0 - COLD START. Read CLAUDE.md, AGENTS.md, docs/how-to/execute-a-plan.md,
docs/how-to/ship-a-pr.md, docs/how-to/run-the-gates.md, and docs/reference/agent-notes.md
with its four pages. This machine is Windows and agents share its terminals: start every
command with a tag of your own and a Set-Location to your own checkout, and send long
output to a file under %TEMP%, then read the file. Then read this plan's section 0,
section 1 (the Status Reckoner, the only tracker), section 2.2, and each row just before
you dispatch it.

STEP 1 - ADOPT OR CLOSE. Run git worktree list, gh pr list and git branch -vv. At the
last update, 2026-09-29 at about 01:20 UTC, nothing of this plan was in flight. Rows 1,
2, 4, 5, 6, 7 and 9 had merged (#1138, #1140, #1137, #1143, #1144, #1154, #1157), and
so had #1146, this run's tool notes and defects 38 to 47. This run's worktrees, local
branches and leftover folders were all swept, row 9's after its merge, so any plan 51
checkout you find was made after that update.

STEP 2 - DISPATCH. Row 7 merged on 2026-09-28 (#1154). Its open questions were
settled by Carmack and Fowler before dispatch - row 7's decisions 10 to 18 and
deviations 7 to 12 - and its parquet reader by the owner (deviations 14 and 15).
The person was told the same evening that plan 50's row 9 no longer waits on this
plan, and that its readers import sliceFromDisk() from frontend/src/lib/server/.
Row 9 merged on 2026-09-29 (#1157), settled at dispatch by Carmack and Fowler
(deviations 19 and 20); the person was asked to tell plan 52's owner about deviation
20. Nothing is ready now. Row 3 needs packed files of its three ledgers on main, and
row 8 needs row 3 (deviation 16). Measured on main at e5a0f8718: state/compact/ does
not exist, the three ledgers are still CSV, and every packing task is report-only.
  after packed files of    row 3. They reach main by whatever route plan 50 and the
  the three ledgers are    person take - this plan asks nothing of plan 50
  on main                  (deviation 18) - and never before plan 50's row 9
                           merges. Row 2's text says row 3 must date the
                           completeness sentence from the newest compacted day, not
                           from generated_at, but row 3's file list does not name
                           frontend/src/lib/console/completeness.ts. Settle it at
                           dispatch.
  after row 3              row 8. Get Susan's ruling on defect 38 first: does speed or
                           placement count decide which machines are left without a
                           colour? Defect 39 rides on it. Row 8's file list also misses
                           two things other text gives it: defect 44 says row 8 moves
                           MemoryBoard.svelte onto absentHatch, and row 5's decision 21
                           says the row that first puts a house-style component on a
                           route removes its <title>. Settle both at dispatch. Row 7
                           hands row 8 five more: the service worker skips the
                           engine's .wasm by its suffix, beside the encoder's files;
                           the cold-load spec asserts the engine is not first-load
                           (deviation 11); the engine starts loading at the same time
                           as the data fetches, or a cold load reaches the four-trip
                           ceiling; the oracle adds "the engine's worker cannot fetch
                           an origin connect-src does not name"; and how the device keeps the engine across
                           deploys (deviation 12). Its scope line reads "no change to
                           the door's contract", so it may fix engine.ts. Row 9 hands
                           row 8 two more: its page keeper has run only in Node, whose
                           engine copies a buffer where a browser's takes it, so row 8's
                           panel is its first browser run; and ledgerReach() asks for
                           monthly.json, which is not there until a ledger's first
                           month is packed, so a browser logs a 404 that the smoke
                           check counts (Carmack, 2026-09-29). Settle it at dispatch;
                           the fix Carmack named, an empty monthly.json from the first
                           packing pass, is plan 50's, and this plan asks nothing of
                           plan 50 (deviation 18).

STEP 3 - GATES. A worker runs `npm --prefix frontend run test:changed -- --list`, then
only its row's named acceptance gates, then pushes and reports. CI is the one full-suite
run (CLAUDE.md section 9). A worker keeps a running report in a file under %TEMP% from
its first push on (execute-a-plan.md): row 5's first worker ran out of room mid-row, and
its pushed draft is what let the row be finished rather than done again.

STEP 4 - MERGE. GitHub refuses auto-merge on this repository, so merge by hand when CI
is green: gh pr merge <N> --repo miztiik/yen-idhazh --squash --delete-branch, run from
outside the repository, then confirm with gh pr view <N> --json state,mergeCommit. Just
after main moves, GitHub reports mergeable as UNKNOWN: ask again rather than update the
branch. A worker call blocks you until that worker returns, so merge every green pull
request before you start the next worker; row 2's waited an hour. If two open pull
requests each stamp their own Reckoner line, the second conflicts on this file: merge
origin/main into its branch, keep both lines and push. Never rebase and force-push.

STEP 5 - CLOSE. When every row is DONE, follow the closing section of
execute-a-plan.md. A commit made on this machine is stamped +02:00 unless TZ=UTC is set
for it (docs/reference/agent-notes/git-and-github.md), and a plan-doc stamp pushed
straight to the trunk is such a commit. GitHub's own squash merges carry the same
offset; that is defect 48, and it is not this plan's to fix.

OPEN FOR THE PERSON. Nothing. The person answered on 2026-09-28: plan 55 is the query
page's own plan; d3-sankey lays the flow out (deviation 13); and this plan leaves plan
50's plan alone (deviation 18), so how packed files first reach main is plan 50's
question and the person's, not this plan's.
```

### Deviations and owner rulings to date

Only what no row records. Each row's own departures are in its decisions and its "Corrected" and "found in execution" notes, and the side-by-side run of rows 5 and 6 is in section 1.

| # | Row | The plan said | What is true, and why | Authority |
| --- | --- | --- | --- | --- |
| 1 | 1, 2, 4 | Parallel N = 2 | Rows 1, 2 and 4 ran three-wide. They shared no file, and the owner asked for parallel work | Plan owner, 2026-09-27 |
| 2 | all | AUTO-merge on green gates | GitHub refuses auto-merge on this repository, so every row merged by hand, as plan 50's deviation 12 found | Found at merge |
| 3 | - | A change reaches main through a pull request | #1133 brought a retired word into an agent note, and main's retired-word test went red. The one-word fix went straight to main (9c7df2d09), so every open branch could go green | Plan owner, 2026-09-27 |
| 4 | 2, 6 | The owner merges each row as its gates go green | A worker call blocks the owner until it returns, so row 2's pull request waited about an hour with its gates green. Row 6 merged row 2's branch into its own to move on, and a helper agent merged row 6 | Plan owner, 2026-09-28 |
| 5 | 5 | One worker delivers a row | Row 5's first worker ran out of room and returned a draft with five browser tests failing. The owner chose to finish it on the same branch, and a second worker did | Owner, 2026-09-28 |
| 6 | 7 | This plan builds row 7 (decision 8) | On 2026-09-27 the owner's words were read as handing row 7 to plan 50's owner, so the row sat unstarted after it was ready. The owner ruled on 2026-09-28 that this plan builds it | Owner, 2026-09-28 |
| 7 | 7 | Plan 50's paragraph "What a reader does with a stamp it does not know": the door refuses an index on any version mismatch | The door reads an index at its own stamp or an older one when the fields it reads check out, and refuses only a newer one. The gardener rewrites the indexes at its own wake, not in the commit that moves the stamp, so exact equality would blank every panel from a shape change to the next wake - days at the measured wake rate, and up to a month for `monthly.json` - which CLAUDE.md section 11 calls a release blocker. Plan 50's owner is told here. Row 7's decision 10 | Carmack and Fowler, 2026-09-28 |
| 8 | 7 | Decision 3: the engine's selector picks between the single-threaded builds | One build ships, the one that needs WebAssembly exception handling. It adds 36.7 MB to a 99.8 MB site, which reaches 12.7 percent of the 1 GiB cap; the other build would add 42.2 MB more for browsers from before 2022. Row 7's decision 11 | Carmack and Fowler, 2026-09-28 |
| 9 | 7 | Section 2.2: `ledger.ts` holds both entry points | `sliceFromDisk()` lives under `frontend/src/lib/server/`, where SvelteKit itself refuses a browser import, and a core module that imports nothing tied to one environment holds the logic, so a Node test can load it. Plan 50's row 9 imports it from there. Row 7's decision 16 | Fowler, 2026-09-28 |
| 10 | 7 | Section 2.2's `SliceResult` | `ok` and `quiet` also carry `through`, the newest day compacted or `null`, so a panel can say how far its data reaches; a span wholly after that day is `quiet`. Row 7's decision 14 | Carmack and Fowler, 2026-09-28 |
| 11 | 7, 8 | Row 7 asserts in `console-cold-load.spec.ts` that the engine is not first-load | No page loads the door until row 8, so that assertion could not fail in row 7. The bundle gate's new entry, proved by a deliberate static import, is row 7's witness, and the cold-load assertion moves to row 8. Row 7's decision 18 | Carmack, 2026-09-28 |
| 12 | 7, 8 | Decision 2 and section 2.2: the engine is fetched once, and a daily file is cached for ever | Measured 2026-09-28 on the live site: Pages sends `Cache-Control: max-age=600` and an `ETag` built from the deploy time and the size (`"6aba5aa3-152"` on a 338-byte file deployed at 12:16:35 UTC). So an unchanged file is sent again after every deploy, several times a day, and the engine's 8.2 MB (compressed) is paid once a deploy rather than once. Row 8 decides how the device keeps it | Plan owner, measured 2026-09-28 |
| 13 | 4 | Decision 6: the flow's layout is our own arithmetic on `d3-shape`, and `d3-sankey` is not taken | d3-sankey 0.12.3 lays the flow out. The flow keeps two rules of its own on top of it: each node sits in the column of its depth, so a drop stays beside its stage, and each column is stacked again from the shared top edge. The owner put the added weight at about 2 KB gzipped and asked for no measurement. The vocabulary page carries the reasons | Owner, 2026-09-28 |
| 14 | 7 | Decision 11 as set at dispatch: the engine is pinned exactly at `1.33.1-dev57.0` | The engine takes a caret range like every other dependency, and the test is the guard: the door's oracle runs against whatever version is installed, so an upgrade that changed a behaviour turns it red on the pull request that raised the version, which a pin would only have delayed. Plan 55 takes the engine the same way | Owner, 2026-09-28 |
| 15 | 7 | Row 7's scope: no config change. Its ESCALATE note: host the parquet add-on on this site, checked against a digest, with the native engine for the Node half | The engine downloads its parquet add-on from DuckDB's own host, as it does on any site. One config value, `ledger.engine_extension_repository`, tells the engine where and gives the page's `connect-src` that one origin. The door's oracle downloads the add-on once on a fresh machine, which is the one exception to "no test touches the network". The owner ruled that the trust-boundary guardrail does not apply to this download and that the guardrail's text stays as it is | Owner, 2026-09-28 |
| 16 | 3, 8 | Row 3 depends on plan 50's rows 7 and 9 | Row 3 also needs packed files of its three ledgers on main. Its decision 5 sets each ceiling from a built index, and no index exists until something packs a day. Plan 50's row 9 ships the three packing tasks report-only (plan 50 deviation 98), so row 3 cannot start the day row 9 merges unless packed files reach main another way. Row 9 also misses two readers of these ledgers, `evalRows()` and `itemHealthRows()` in `payload.ts` (plan 50 deviation 132). The person was asked how packed files first reach main, and ruled that this plan leaves plan 50's plan alone (deviation 18) | Plan owner, measured on main at e5a0f8718, 2026-09-28 |
| 17 | 8, 9 | Plan 52 handed its door work to row 7: a cache for the page's life, one registration a file, and `ledgerReach` (plan 52, "Found while planning", item 2) | Row 7 merged without it, so it is row 9. Row 8 waits on it, because plan 52 asks for it before any panel calls the door | Plan owner, 2026-09-28 |
| 18 | - | (not in the plan) | The person ruled that this plan leaves plan 50's plan alone, because its owner is busy. This plan's owner had added two lines there that evening, plan 50's deviations 132 and 133, and plan 50's owner has since numbered its own next line after them, so they stay and nothing more is changed there. Plan 50's row 9 now carries the two readers deviation 16 names, so this plan does not take them, and how packed files first reach main is plan 50's question and the person's | Owner, 2026-09-28 |
| 19 | 7, 9 | Row 7 wrote that an index is never read from a cache, because file selection acts on what it says | An index is read once a page and kept. Every slice and every reach on one page then acts on the same index, which plan 52's window needs, because it anchors on a first and a newest day fixed for the page; and reading it again before each slice would put one more round trip in front of every slice, where a cold load allows four serial round trips. A build-time call reads its indexes fresh each time. What an open tab shows after a deploy is on the door's page. Row 9's decisions 4 to 9 | Carmack and Fowler, 2026-09-29 |
| 20 | 9 | Plan 52 section 2.3: `ledgerReach` answers `{state: 'unreachable'; at: DateStamp}` | Its `unreachable` carries no day. A slice names the first day it could not answer; a reach asks for no day, so there is none to name, and the console says why instead. Plan 52's owner is told through the person, and plan 52 is not edited here | Carmack and Fowler, 2026-09-29 |
| 21 | 3, 8 | Deviation 16: packed files of the three ledgers reach main only if something packs them | The person answered on 2026-09-29 (plan 50 deviation 135). Plan 50's row 9 packs every day the packing rule already admits in its one-time migration, and writes each ledger's day index, so packed files and an index are on main the day that row merges. The packing tasks stay report-only, so the packed days end at the day the migration ran until a person turns them on. Recorded here by plan 50's owner | Owner, 2026-09-29 |

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The Hardware route counts every job twice, its span control sits far above the reader who wants it, and every chart on the console is drawn from data baked into the page by the build. This plan corrects the count, moves the chrome, and writes the query door, the chart vocabulary, the hover strip and the gates the fifty later panels follow - then proves the whole chain on one panel: query the ledger in the browser, draw it in d3. |
| Hard scope - in | - `state/host-fingerprint/` is read settled, so a job counts once.<br>- The console's tab strip sticks, however many tabs it holds, the span control rides on it, and a sentence says how complete the page is.<br>- The three ledgers the console reads reach the browser as published parquet.<br>- `frontend/src/lib/data/` holds the one query door every later panel calls in the browser and every build-time reader calls while the site is built; `frontend/src/lib/charts/d3/` holds the house style every later chart draws to.<br>- One panel queries the published ledger for the columns and days it draws and is redrawn in d3. |
| Hard scope - out | see the table below |
| ESCALATE triggers | 1. A tenth prerendered route, or retiring an existing one.<br>2. A charting library that is not d3.<br>3. A new committed payload under `frontend/public/`.<br>4. Any change to `ConsoleBand`'s shape - it is the payload every console route fetches first, so a retyped or removed field ripples to every route.<br><br>**A new chart type is not an escalation.** It is Susan's call (section 2.6).<br><br>**"How the browser reaches the bytes" is settled**: `state/` carries its own indexes, declared and committed by plan 50 (its section titled "The shapes a worker must not invent"); the build copies the published ledgers' compact periods verbatim into gitignored `frontend/static/state/` and generates nothing.<br><br>**Compaction and the ledger migration are plan 50's, not this plan's.** Plan 50 migrates the ledgers to parquet, owns every compaction trigger and its eligibility rule, and declares the index and watermark shapes. **Its compaction also merges: a compacted file holds one row per record**, so the two halves of a job's machine record arrive as one row and the door never merges (owner decision, 2026-09-27). This plan publishes what plan 50 compacted and reads it in the browser. |
| Chosen strategy | Correct the number first, move the chrome and publish second, write the shared parts third, prove them on one panel last. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The other fifty panels, on every console route | Two grammars coexist: one panel queries parquet and draws in d3, fifty read CSV at build time and draw in ECharts. `echarts@^5.6.0` stays installed with its importers | [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md), which starts from the vocabulary, the strip and the gates in sections 2.6 to 2.9, and from the panel-by-panel verdict table Susan ruled, now carried in plan 52. **Rows 4 to 8 exist to make that plan cheap, not to be it** |
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
| N5 | d3 is the only charting library | **Stone laid by rows 4 to 6**, which write the starting chart types, the hover strip and the ten gates, and by row 8, which moves one importer |
| N6 | One writer per path | **Inherited** from plan 50's door |
| N7, N8 | `state/` is the only source; no production artefact under `frontend/` in git | **Stone laid by row 3.** What reaches the site is the ledger itself, copied unchanged and gitignored, so it cannot say anything `state/` does not. **The projections that can are retired by plan 52**, each in the pull request that moves its last reader |
| N9, N10, N11 | The name, the two roots, the one shard pattern | **Inherited** from plan 50's door. This plan mints no naming rule of its own |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The Hardware route stops counting every job twice | - | A | DONE | p51r1 | #1138 | p51-r1-worker |
| 2 | The console shell: a stuck tab strip, the span control on it, jump links, a completeness sentence | - | A | DONE | p51r2 | #1140 | p51-r2-worker |
| 3 | The three ledgers the console reads are published | plan 50's rows titled "One compaction task a ledger, two compact periods, and the diagrams move into the page" and "The three ledgers the console's routes read become parquet" | B | PENDING | - | - | - |
| 4 | The chart vocabulary and the house style, with no panel moved | - | B | DONE | p51r4 | #1137 | p51-r4-worker |
| 5 | One readout strip, every chart, and hover a keyboard can reach | 1, 4 | C | DONE | p51r5 | #1143 | p51-r5-worker |
| 6 | The ten sufficiency gates and the panel capture group | 4, 5 | C | DONE | p51r6 | #1144 | p51-r6-worker |
| 7 | The query door module and its two entry points | 4; plan 50's row titled "The index and watermark shapes are declared" | C | DONE | p51r7 | #1154 | p51-r7-worker |
| 8 | One panel end to end: the browser fetches the ledger and draws it in d3 | 1, 2, 3, 4, 5, 6, 7, 9 | D | PENDING | - | - | - |
| 9 | The door keeps what it fetched for the page's life, and says how far a ledger reaches | 7 | C | DONE | p51r9 | #1157 | p51-r9-worker |

**Readiness is the file-disjointness test, not the group letter** (execute-a-plan.md). The letters record which rows the author believed independent; the `Files touched` lists are the fact, and the shared-file notes below are why three depends-on edges exist that the letters do not show.

**Rows 1 and 2 run two-wide.** They share no file: row 1 holds `payload.ts`, `host-fingerprint.ts`, `machine-counters.ts`, `fleet.ts`, `PlatformMixPanel.svelte`; row 2 holds `+layout.svelte`, `ConsoleNav.svelte`, `SiteHeader.svelte`, `band.ts`, `app.css`.

**Rows 3 and 4 run two-wide.** Row 3 is backend, config and the build (`config/idhazh.json`, `copy-visuals.mjs`, `bundle-gate.mjs`, the ceiling test); row 4 is new frontend chart modules under `frontend/src/lib/charts/d3/`. Disjoint.

**Group C is rows 5, 6 and 7, and depends-on edges make it safe.** The overlaps that force the edges: **rows 5 and 6 both edit `config/appearance.json`** (row 5 the `chart.readout_max_share` value, row 6 the `console.panel_groups` and `console.judged_panel_ids` keys), so row 6 depends on row 5 and the file is edited once at a time; **rows 1 and 5 both edit `fleet.ts`** (row 5 rebuilds its `Readout` producer), so row 5 depends on row 1; and **row 7 edits `chart-vocabulary.spec.ts` and `frontend/package.json`, which row 4 creates and touches** (row 4 adds `d3-shape`, row 7 adds the engine), so row 7 depends on row 4. Row 7's index-shape test binds to the Pydantic index contracts **plan 50's index-shapes row** declares, so it also waits on that plan-50 row - for the shape only, never for live data. Row 7 shares `bundle-gate.mjs` with row 3 (row 3 the ceiling key, row 7 the engine's `FORBIDDEN` entry), but row 3 waits on plan 50's migration, which waits on row 7, so row 7 always lands first and the file is edited in order. **The cross-plan chain stays acyclic**: plan 50's migration -> plan 51 row 7 -> plan 51 row 4 -> nothing, and plan 51 row 7 -> plan 50's index-shapes row, which reaches nothing in plan 51.

**Rows 5 and 6 run side by side anyway** (plan owner, 2026-09-28). The edge from row 6 to row 5 orders one file, and the two rows edit different lines of it: row 5 re-sets `chart.readout_max_share`, and row 6 adds two `console` keys. Whichever row merges second takes main in first.

**Why the query door is its own row (row 7) and not folded into the panel.** It is the N2 and N3 keystone every one of plan 52's fifty panels calls, so it ships as an independently revertible row with its own witness, exactly as the vocabulary (row 4), the strip (row 5) and the gates (row 6) do. Plan 50's row titled "The three ledgers the console's routes read become parquet" also depends on this row by name; the door depends only on row 4 and on plan 50's index-shapes row (for the shape of the index it reads), neither of which reaches plan 50's migration, so the door lands before that migration and the cross-plan pointer resolves without a cycle.

**Rows 4, 5, 6 and 7 are the shared deliverable; row 8 is the proof.** Sections 2.2 and 2.6 to 2.9 declare all of them, so no row invents anything. Row 4 writes modules and no panel, which is why it runs beside row 3.

**Row 5 replaces one exported type and cannot be split by panel.** `DayReadout` becomes `Readout` across its producers and consumers, so there is no intermediate commit where half the console is on the new shape and the tree compiles. That is why its `Files touched` is long and why row 6 (which shares the config file) waits on it. **Plan 54's run-yield chart has landed on `DayReadout`** (#1117): `RunYield.svelte` builds its own columns of the old type, so row 5 converts it with every other chart and the type is swapped once.

**Row 3 publishes; it migrates nothing and triggers no compaction.** Plan 50 migrates the ledgers and owns every compaction trigger and its eligibility rule. Row 3 adds the copy step, the allow-list, the ceiling and the test that binds a panel's ledger to that list. It reverts to nothing.

**Row 8 is the proof and lands last.** It rewrites `fleet.ts` into a d3 draw, wires the panel to the query door, and joins the capture group, so it shares `fleet.ts`, `PlatformMixPanel.svelte` and `host-fingerprint.ts` with row 1 and the query door with row 7, and cannot run beside them.

**Row 9 is the door work plan 52 handed this plan, which row 7 merged without** (deviation 17). It needs only row 7, so it is the one row ready while rows 3 and 8 wait on plan 50. Row 8 waits on it, because plan 52 asks for it before any panel calls the door.

## 2. The contracts

### 2.1 `HOST_FINGERPRINT_KEY`, the frontend copy

`backend/idhazh/ledger/keys.py` declares `HOST_FINGERPRINT_KEY: Final = ("date", "run_id", "job", "shard")`. The frontend carries a hand-written copy beside `ITEM_HEALTH_KEY` in `frontend/src/lib/server/payload.ts`, and `frontend/tests/day-shards.spec.ts` holds the copies in step:

```ts
/** What makes two machine rows the same record. The Pydantic original is
 *  `ledger.HOST_FINGERPRINT_KEY`; `day-shards.spec.ts` holds this copy in step. */
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

**This merge is for the build-time CSV reader only.** Once plan 50 moves this ledger to parquet, its compaction does the merge (owner decision, 2026-09-27): a compacted file already holds one row per job, so no reader merges, and plan 50 deletes `mergedDayShards` if nothing else calls it.

### 2.2 The query door

The query door is three modules under `frontend/src/lib/data/`, and a panel sees only the first. `ledger.ts` is the public door every panel calls; `engine.ts` is **the only module in `frontend/` that imports the query engine** (`@duckdb/duckdb-wasm`), mirroring the backend's single-engine rule; `slice.ts` turns a date range into the set of files to fetch. A panel imports `ledger.ts` and nothing deeper. **Corrected at row 7's dispatch, 2026-09-28:** the logic sits in a core module beside these, the index copy in a module of its own, and `sliceFromDisk()` in a module under `frontend/src/lib/server/` (row 7's decision 16).

**`ledger.ts` has two entry points over one query.** `slice()` is what a panel calls in the browser; it fetches the compacted files over HTTP. `sliceFromDisk()` is what a build-time reader under `frontend/src/lib/server/` calls while the site is built; it reads the same files from `state/` on disk. Plan 50's row titled "The three ledgers the console's routes read become parquet" moves today's build-time readers onto `sliceFromDisk()` and adds no export of its own.

```ts
/** Ask a committed ledger for the slice a panel draws. Columns and a date range
 *  are named by the caller; nothing fetches a whole ledger. */
export async function slice(ledger: LedgerName, opts: SliceOptions): Promise<SliceResult>;

/** The same query over the same compacted files, read from disk while the site is
 *  built. `stateDir` is `STATE_ROOT` from `frontend/src/lib/server/payload.ts`.
 *  Only build-time readers under `frontend/src/lib/server/` call it; a panel never does.
 *  Corrected at row 7's dispatch (deviation 9): it is exported from a module under
 *  `frontend/src/lib/server/`, not from `ledger.ts`, so SvelteKit refuses a browser import. */
export async function sliceFromDisk(
	stateDir: string,
	ledger: LedgerName,
	opts: SliceOptions
): Promise<SliceResult>;

/** What a caller asks for. `columns` is required and non-empty; the range is closed
 *  at both ends. */
export type SliceOptions = {
	columns: readonly string[];
	from: DateStamp;
	to: DateStamp;
	where?: readonly Predicate[];
};

/** One parquet row as the engine hands it back. */
export type Row = Record<string, string | number | boolean | null>;

/** What the door hands a panel, so the panel draws the right one of four nothings
 *  without inspecting an error. `rows` is empty for every state but `ok`; `loading`
 *  is the panel's own state before the promise resolves and is not returned here.
 *  `through` is the newest day `daily.json` names, or `null` before the first
 *  compaction, so a panel can say how far its data reaches (deviation 10). */
export type SliceResult =
	| { state: 'ok'; rows: Row[]; through: DateStamp }
	| { state: 'quiet'; rows: []; through: DateStamp | null } // covered, or wholly past `through`, and no rows
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

**The engine runs in two places, and `engine.ts` owns both.** In the browser it loads the package's single-threaded build behind a dynamic `import()` (row 7 decisions 3 and 4). At build time, in Node, it loads the package's blocking Node build and reads its wasm from the installed package. So there is still one engine and one importer (section 2.5 refusal 1). Both entry points run the same query over the same compacted files, so a build-time page and a browser panel asking for the same span get the same rows.

**Whole files are fetched and handed to the engine as buffers**, the same way the month search index already is. There are no byte-range requests anywhere in this plan - a date-range query and an HTTP range request are different things, and only the first is used. Column projection saves parse time, not bytes.

**File selection follows the span.** `console.window_presets` is `[1, 7, 14, 30, 90]`. A span of 30 days or less is served entirely from the daily period - the two indexes plus one daily file per date; only the widest span reaches a monthly file. No raw file is published, so the one-day span reads one daily file and is the cheapest in the set.

**The browser cannot list a directory, so the ledger carries its own indexes.** Owner ruling, 2026-09-25: **`state/` presents its own index, and the build generates nothing.** Plan 50's section titled "The shapes a worker must not invent" declares the small JSON files that do it, each committed, each with exactly one writer. This plan invents no address book, declares no contract of its own, and adds no generating step.

**Three findings settled it, and none of them is the byte ceiling that prompted the question.**

**The band is prerendered into every console document.** `+layout.ts` carries `prerender = true`, so at build time SvelteKit resolves the fetch and serialises the result into each console page. Anything that loader fetches is inlined into every console document, so a file fetched there inherits the same cost under a different name. **What escapes it is fetching at view time from the query door**, which is what N3 asks for anyway.

**A band-carried list would have undercounted, silently.** `console/band.json` is written by `stages/assemble.py` during a digest run at one moment; the files reach the site at a later one. `digest.yml` has no concurrency group by design, so more shards land in between, and the list would name fewer files than the tree holds. The browser would read twelve shards of sixteen and the chart would be quietly low, with no error and no 404 - the defect-33 class arriving through a new door, and no test could have caught it, because the invariant would have had to hold across two processes at two different times.

**A list generated at build time has the same hole, one step later.** Plan 50 closes it at the source instead: its compaction task, one per ledger, re-lists a raw day directory before it reads it, so no elapsed-time guess stands between the tree and the list. **That re-list is what makes a committed index trustworthy**, and it is what this plan depends on.

| # | File | Writer | Why that writer is safe | Committed |
| --- | --- | --- | --- | --- |
| 1 | `state/compact/<ledger>/index/<period>.json` | that ledger's compaction task | one task per ledger, the only writer of its indexes | **yes** |

**No watermark is on this list.** The door finds the compaction edge in `daily.json`, whose newest day is the newest day compacted, so a watermark stays a file only the gardener reads. Plan 50 states the rule; owner decision, 2026-09-27.

#### What the build does, which is copy bytes and nothing else

**The staged tree is a verbatim subtree copy, so the published path and the committed path are the same string.** The step copies, for every ledger whose `LedgerConfig.published` names it: the two compact periods and their indexes. `LedgerConfig` is the `ledger` block in `config/idhazh.json`, declared by plan 50 in `backend/idhazh/contracts/knobs/ledger.py` - **not** the ledger registry `LedgersConfig` in `backend/idhazh/contracts/ledgers.py`, which differs by one letter. Nothing else is copied, and nothing is renamed, merged, re-sorted or regenerated.

| # | What reaches the site | Published address |
| --- | --- | --- |
| 1 | Compact data, both periods | `state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet`, `state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet` |
| 2 | Compact indexes | `state/compact/<ledger>/index/<period>.json` |

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
| 2 | Fetch only the indexes the span could touch. A span of 30 days or less touches `daily.json` only, so that is one small request |
| 3 | For each date in the span take the **coarsest period that covers it** - monthly, then daily - and fetch that file once |
| 4 | Hand every buffer to the engine as one query with a date predicate |

**A date is reachable through exactly one file, and that is an invariant with a test rather than a convention.** A date in two periods is read twice and every number on the panel doubles - the same defect class as the double count filed as 33. Plan 50's row titled **One compaction task a ledger, two compact periods, and the diagrams move into the page** carries the oracle that asserts it, over a fixture ledger carrying both periods, in one process, at one moment.

**A compacted file holds one row per record, and the door does not merge.** Plan 50's compaction applies each ledger's own merge rule while it builds the file, so the two halves of a job's machine record arrive as one row (owner decision, 2026-09-27). The door returns rows exactly as the files hold them. A second merge rule in TypeScript would be a copy of plan 50's that somebody has to keep in step.

**A hole is `unreachable`, never a low chart.** A date at or before the newest day `daily.json` names that neither index names is a hole: the door returns `{ state: 'unreachable', at }` and the panel draws the `unreachable` state with that date in the console and nothing else. Drawing the rest would be an undercount nobody could see.

**A date after the newest day `daily.json` names has not been compacted yet, so it is not drawn at all, and the freshness sentence says so.** No raw file is published, so the newest data a panel can show is the newest compact daily file. Compaction runs at the gardener's wake, never at the end of a content run: at plan 50's defaults - a 00:40 UTC wake and `compact_after_days: 1` - the newest day a panel can show is the day before yesterday, once that wake's files are published. **Plan 50 ships each compaction report-only** (its deviation 98), so no compact file exists until a person turns that ledger's compaction on; that switch is plan 50's ESCALATE trigger 6.

**Two periods are what make an arbitrary span affordable.** The widest span reads one or two monthly files plus the daily files past the newest whole month, instead of one daily file per day. At month grain alone a span would pull whole months it did not ask for; at day grain alone the widest span would be a request per day.

#### The reader's first request is bounded by config, never by the archive

**This is Guardrail #12 pointed at a reader.** An index that gained an entry every month would make a reader's request grow for as long as the project runs, so its length is bounded by config.

**The bound: an index holds its keep-window of entries and no more. `daily.json` holds at most `daily_keep_days + 31`, `monthly.json` at most the months `monthly_window` keeps.** Two config values a person sets, and no term of elapsed time. The `+31` is the month-absorption rule, not slack: a month is absorbed whole, so the daily period holds between `daily_keep_days` and `daily_keep_days + 31` days.

**Two controls hold the bound.** First, plan 50's gardener config refuses two things at load for a published ledger: monthly files kept forever (a `monthly_window` of `{unit: forever}`), and daily and monthly files that together reach back less far than the widest value in `console.window_presets`. The daily window is deliberately narrower than the widest span - that is what the monthly period is for. Second, `page_weight.payload_ceilings_bytes` gains an entry for each published `index/daily.json`, and `bundle-gate.mjs` checks it every build - a smoke alarm derived from config that moves when config moves.

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

`frontend/src/lib/charts/d3/` (new, no other row in either plan touches it). **Every function here is pure and takes its numbers as arguments.** One named colour constant is the exception and is named as one: `RESERVED_GREY` **re-exports `UNRECORDED_STOP` from `machine-colour.ts`** rather than minting a second grey. **The hatch is a builder, not a constant** (Fowler, Susan and Carmack, 2026-09-27): `absentHatch({ degrees, gapPx, linePx })` takes its angle from the panel, which reads `console.absent_hatch_degrees`, because a pure module cannot read config and a knob nothing reads cannot pass the substitution test - row 8 mints the knob beside its first reader. It has no default angle, and its stripes sit on the page surface, never over a grey fill.

| Module | Exports | What it owns |
| --- | --- | --- |
| `scale.ts` | `bandScale`, `linearScale`, `timeScale` | The three scales a console chart may reach for, each reading its range from the frame |
| `axis.ts` | `valueAxis` | Tick counts, formats and the label rule for a **value** axis, from `config/appearance.json`. **There is no `dateAxis`** - `dayTicks` in `frontend/src/lib/charts/frame.ts` owns every date axis on this console and gains no second home, which is the same reason section 2.6 refuses `d3-axis` |
| `ordered-colour.ts` | `orderedRamp`, `RESERVED_GREY`, `absentHatch` | The five-step speed ramp, the grey for an absence and the hatch for a known machine with no reading |
| `motion.ts` | `transition`, `prefersReducedMotion` | One duration, one easing, and the reduced-motion branch written once |
| `empty.ts` | `emptyState`, drawn by `EmptyState.svelte` | **Re-exported from `frontend/src/lib/console/waiting.ts`**, which already owns `loading`, `quiet`, `missing` and `unreachable` and their sentences. This module adds the drawing of each state and mints no second vocabulary (Guardrail #4). **A floor missed is `too-few`, added to `waiting.ts` with its sentence** (Fowler, Susan and Carmack, 2026-09-27): `refused` and `unreachable` already mean a fetch that failed. Every state keeps the chart's height, and every one but `loading` prints its sentence - `unreachable` on the warn tint, because a tint alone cannot say what failed (Susan) |

### 2.4 The appearance knobs these rows read

Every value below is a knob (Guardrail #6). Some exist and some are minted; the "Read by" column names the row.

| Key | Status | Value | Read by |
| --- | --- | --- | --- |
| `console.machine_colour_stops` | **Exists at 7, becomes 5** | `5` | Row 8's ramp. Five steps because a reader cannot rank many steps of one hue on a thin bar, and three panels share machine colour so a silent mismatch ships |
| `console.fleet_min_rows` | Exists | `160`, unchanged | Row 8. The knob keeps its job and changes what it switches: below it the panel draws one mark per job instead of switching off |
| `console.fleet_top_kinds` | Exists | `4`, unchanged | Row 8's merge rule |
| `frame.breakpoints_px` | Exists as `[640, 1024, 1400]` | unchanged | Row 2 sticks at `breakpoints_px[1]`. **No second key naming that width** |
| `console.window_presets` | **Exists as `[1, 7, 14, 30, 90]`** | unchanged | Row 2's span control draws one segment per value, and the door reads its widest value for file selection. **No second key naming the same values** |
| `console.absent_hatch_degrees` | **New** | `45` | Row 8's hatch for a known machine with no throughput reading, passed to `absentHatch`. Row 8 also carries the knob's default in `frontend/src/lib/server/config.ts` and the two every-knob fixtures, and moves `MemoryBoard.svelte`'s `.absent-bar` onto it - the other hatch that means no reading (Fowler and Carmack, 2026-09-27) |
| `console.plot_min_fill_share` | **New** | `0.85` | Gate 1 (section 2.8), specced in row 6. A fill floor with the same standing as `console.fleet_min_rows`: the spec asserts the drawn plot fills at least this share of the panel's content box |
| `console.judged_panel_ids` | **New** | `[]` (row 8 adds `platform-mix`, which is panel 6b's id in `console.panel_groups`; the contract refuses an id no route draws, so `6b` itself would fail the build) | Row 6's sufficiency specs only. The opt-in subset of `console.panel_groups` the gates judge; capture still runs over all of `panel_groups`, so a panel is captured before it is judged |
| `page_weight.payload_ceilings_bytes."state/compact/<ledger>/index/"` | **New, one per published ledger** | set in row 3 from the built `daily.json`, at least twice its size per the field's own rule | `frontend/scripts/bundle-gate.mjs` and `backend/tests/contracts/test_page_ceilings.py`. **The key names the one directory that holds files directly**: `payloadsFor` does not recurse, so a key naming `state/compact/<ledger>/` returns nothing and fails the gate by name. It lives in `config/idhazh.json`, not `config/appearance.json` |

**`console.bandwidth_min_kinds` and `console.min_attempts_for_rate` already exist and are unchanged.** The chart types in section 2.6 name them, but the panels that read them are plan 52's; no row here reads them, so they are not in the table above.

**Three page-weight gates fire before the site cap, and row 3 must clear all three.** `page_weight.cold_console_load_bytes` is what a console reader's first load may cost, so **the query engine ships behind a dynamic import**, the same rule the gate already enforces for the on-device encoder. `page_weight.payload_ceilings_bytes` caps each fetched payload and has **no key covering `state/`** today, so a staged ledger is a payload no gate can see until the key above is minted. And `test_page_ceilings.py` asserts `cold_console_load_bytes` sits between the worst page and that page plus the telemetry ceiling, so adding a payload key moves that two-sided assertion - **which is why the key, the ceiling and the assertion move in one commit, row 3's.**

**`cold_console_load_bytes` counts month-grained copies, and the door fetches days.** Row 3 sets the ledger's payload ceiling on `index/daily.json` only, and the fetched-data total is bounded by `console.window_presets`' widest value against `daily_keep_days` (plan 50's gardener config) - which is the bound `test_page_ceilings.py` is given, in the same commit.

### 2.5 What a panel may not do

Three refusals, each enforced by a test rather than a review note.

| # | Refusal | Enforced by |
| --- | --- | --- |
| 1 | A panel imports the query engine directly | `git grep -l duckdb -- frontend/src` returns exactly one path |
| 2 | A panel builds a URL or a path | `slice()` takes a `LedgerName`, never a path; and an import walk in `chart-vocabulary.spec.ts` finds `sliceFromDisk` imported only under `frontend/src/lib/server/` |
| 3 | A panel asks for every column | `columns` is required and non-empty, refused by name at the door |

### 2.6 The chart vocabulary - nine types to start, and Susan adds more

Susan's starting set, 2026-09-26. **It is a starting set, not a closed one** (owner, 2026-09-27). A panel that needs a type this table lacks asks Susan; her ruling adds the type - its name, signature and drawing component - to this table and to the vocabulary page before it is built. That is a design call, not an escalation. The five mark shapes already ruled in [docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md) are marks **inside** these types, not types; nothing there is superseded.

**Each type is one `.ts` module returning geometry and one `.svelte` component that draws it.** The `.ts` module is pure and takes every number as an argument (section 2.3); the component owns the DOM. Where a type's drawing half already lives in an existing component, the table names it and no new component is made.

| # | The name a worker types | The signature | The question it answers | Right when | Wrong when | Drawn by |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `rankedList` | `(rows: readonly {label: string; value: number; segments?: readonly {label: string; value: number}[]}[], opts: {max?: number}) => RankedGeometry` | which one is worst | a bounded set of named things, one magnitude each, and the reader acts on the name | the question is "what is changing" - that is type 2 | **`frontend/src/lib/components/RankedList.svelte`, which exists and has four importers. No new component** - markup not SVG: seventy rows would be seventy chart instances, and markup still draws with no script |
| 2 | `dateSeries` | `(series: readonly {label: string; token: ChartToken; points: readonly {date: DateStamp; value: number \| null}[]}[], opts: {frame: Frame; stacked?: boolean; density: number; valueTicks: number; padding: number}) => SeriesGeometry` | what is changing | a value per day or per run, one to five series, compared across time | the set is not ordered by time. A run mix drawn as a trend invites a cause nothing measured | `DateSeries.svelte`. Ticks from `dayTicks` in `frontend/src/lib/charts/frame.ts`, **never from an axis generator** |
| 3 | `distribution` | `(values: readonly number[], opts: {frame: Frame; minValues: number; valueTicks: number; rules?: readonly {at: number; label: string}[]}) => BinGeometry` | how bad does it get | one quantity over many items, the tail is the point, the spread crosses a decade | fewer than `console.fleet_min_rows` values. A histogram of eight readings is a claim | `Distribution.svelte`. Cumulative curve on a second axis, 0 to 100 |
| 4 | `partsOfOne` | `(rows: readonly {label: string; parts: readonly {label: string; value: number}[]}[], opts: {order: readonly string[]; overlapping?: boolean}) => PartsGeometry` | what is this one thing made of | components of a single total, fixed order, a handful of rows | the components do not sum to the total - set `overlapping` and each part becomes a bracket anchored at the origin rather than a stacked segment, because overlapping parts do not add up to the row total | `PartsOfOne.svelte`, segments as markup not paths |
| 5 | `tileStrip` | `(tiles: readonly {date: DateStamp; state: 'quiet' \| 'fired' \| 'absent'; reading?: number}[], opts: {thresholds: readonly [number, number]}) => TileGeometry` | was it quiet, and which day did it fire | a reading that is zero or absent on most days | the reading has a useful value axis every day - that is type 2 | `TileStrip.svelte`. **Three states, never two.** Both thresholds from config |
| 6 | `paired` | `(rows: readonly {label: string; before: number; after: number; attempts: {before: number; after: number}}[], opts: {minAttempts: number}) => PairedGeometry` | what did the change move | two measurements of the same measures, and the reader wants the direction | either side is below `console.min_attempts_for_rate` - the row draws nothing and prints why | **`frontend/src/lib/components/SwapDots.svelte`, which exists. No new component** - through `swapScale` in `frontend/src/lib/charts/series.ts`. Symmetric about no change, minimum half-width |
| 7 | `overlapTimeline` | `(items: readonly {id: string; source: string; shard: number; startMs: number; steps: readonly {label: string; ms: number}[]}[]) => TimelineGeometry` | what was happening at the same time | work items on a real clock, where the queue is the finding | the reader wants totals. A timeline is the worst shape for a sum | **`RunTimelinePanel.svelte`, which keeps its own hand SVG** and is this type's first and only caller. No new component |
| 8 | `flow` | `(stages: readonly {label: string; arrived: number; left: number; drops: readonly {label: string; count: number}[]}[], opts: {narrow: boolean; frame: Frame; nodeWidth: number; nodeGap: number}) => FlowGeometry \| SteppedGeometry` | where did they go, and where did they leave | a funnel of four or fewer stages with named drops | never - below `frame.breakpoints_px[0]` it returns the stepped shape from the same call, and counts that are not one flow come back as the stepped shape with a note | `Flow.svelte`; the panel computes `narrow` from the width against `frame.breakpoints_px[0]`, our own layout with filled `curveBumpX` ribbons at or above it (d3-sankey considered and not taken, 2026-09-27) and a markup list below |
| 9 | `pairedScatter` | `(points: readonly {label: string; x: number; y: number}[], opts: {frame: Frame; minRows: number; minSubjects: number; valueTicks: number}) => ScatterGeometry` | do these two move together | at least `console.fleet_min_rows` rows **and** `console.bandwidth_min_kinds` distinct subjects | below either floor. Two points define a line, so a scatter of two is a claim. It draws nothing and names the floor it missed | `PairedScatter.svelte`. **No trend line, ever** - a fitted line is a verdict nobody agreed to |

**The signatures were corrected on 2026-09-27** (Fowler, Susan and Carmack) to the rule section 2.3 states: every floor, tick count, padding and layout gap is an argument with no default, because a pure module cannot read config. `paired` takes an attempt count per side and applies its floor row by row, so one thin row draws nothing and says why while the others draw. Each floor-guarded type also exports a `<type>Shortfall` that returns the sentence for the floor it missed.

**Every geometry function returns its type or `null`** - the `| null` is dropped from the signature column above for brevity and is not optional. On `null` the component renders `emptyState` (section 2.3), which takes the reason to show; for the floor-guarded types (`distribution`, `paired`, `pairedScatter`) that reason is the floor it missed, named in words (for example "fewer than 160 readings"). A type that returns an empty geometry rather than `null` draws an empty frame, which gate 8 fails.

**Susan's current advice is to avoid** pie, donut over anything but a single completed share, gauge, dial, radar, treemap, word cloud, bubble, anything in three dimensions, and a bar chart of a rate below `console.min_attempts_for_rate` placements, because each answers a question a listed type answers better. Changing that advice is her call.

**A panel may offer more than one view of its data** (owner, 2026-09-27). Where Susan rules a panel needs it, the panel shows a switch between two or more chart types over the same query result: a small set of radio buttons, never a drop-down. Switching redraws and fetches nothing. Which panels get a switch, and between which types, is Susan's call per panel. No panel in this plan has one; the first is built by the plan-52 row that needs it.

**A reused component takes the new geometry as its data prop.** Types 1, 6 and 7 name an existing component (`RankedList.svelte`, `SwapDots.svelte`, `RunTimelinePanel.svelte`) rather than a new one; each takes its type's geometry (`RankedGeometry`, `PairedGeometry`, `TimelineGeometry`) as its data prop and renders `emptyState` (section 2.3) on a `null` return. "No new component" is not "no prop change": the row that first uses one of these three updates its props to the geometry type in the same commit.

**Plan 52 already has two panels that need a type this table lacks** - a range mark (a fill to a median with a notch at the worst) and a target marker on a bar. The plan-52 row that builds either asks Susan to add the type first. This plan's own panel (6b, row 8) is a `dateSeries`.

**The packages, and the rule that keeps them small.**

| # | Package | For | Status |
| --- | --- | --- | --- |
| 1 | `d3-array` | binning, quantiles, extent | installed |
| 2 | `d3-scale` | every scale above | installed |
| 3 | `d3-shape` | `line` and `stack` for type 2, `area` and `curveBumpX` for type 8 | **added 2026-09-27** at 3.2.0 |
| 4 | `d3-sankey` | type 8's layout | **added 2026-09-28 at 0.12.3** (owner; deviation 13). It was considered and not taken on 2026-09-27 (Fowler, Susan and Carmack): a straight funnel has no crossings, merges or loops, and it installs older second copies of `d3-array`, `d3-shape` and `d3-path`. The owner took it for Guardrail #8 at about 2 KB gzipped. The flow keeps its own two rules on top of the library's layout; the reasons are in the vocabulary page's design rationale |
| 5 | `d3-axis` | - | **refused.** It would fork the measured label-thinning rule `dayTicks` owns, and that rule exists because four console axes once drew their dates on top of each other |
| 6 | `d3-selection`, `d3-transition` | - | **refused.** Svelte owns the DOM |
| 7 | `d3-scale-chromatic` | - | **refused.** Colour comes from `--chart-1` to `--chart-8` and the tint tokens. A library ramp collides with the confidence ramp within a month |

**On this console d3 is a maths library, not a drawing library.** A worker who writes `select()` inside a Svelte component has left the vocabulary.

### 2.7 The readout strip - hover data on every chart, reachable by keyboard and touch

**Every chart shows hover data** (owner, 2026-09-27). Point at, tab to or tap a mark and the readout under the chart shows its values. The only exception is a chart with nothing to show beyond what it already prints, and that exception needs Susan's agreement.

**The console has two hover systems today, and one of them only a mouse can use.** `frontend/src/lib/components/ChartReadout.svelte` is the ruled one, a fixed strip below the plot. Other charts put their hover text in a native `title=`, the browser's own tooltip: no keyboard reaches it, no thumb reaches it, no theme styles it and no test reads it. It is used in `ShardBoard.svelte`, `voices/+page.svelte`, `DiskReadsPanel.svelte`, `ProcessorLostPanel.svelte`, `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte`, `console/+page.svelte` and the machine and judgement panels row 5 lists. **Row 5 moves every one of those texts into its chart's readout, so no hover data is lost** - the same words now reach a keyboard and a tap too.

**One module owns it**, `ChartReadout.svelte`, fed by one builder, `frontend/src/lib/charts/readout.ts`. Every chart calls the builder and passes its result. No chart composes its own strip and no chart sets `title=` on a mark.

**`DayReadout` in `frontend/src/lib/charts/frame.ts` is replaced by `Readout`, and `readoutCapStyle` moves to `readout.ts` with it.** The pointer-nearest-column and keyboard-stepping machinery `frame.ts` holds for the old shape - `columnStrip`, `nearestColumn`, `pointerReadout`, `readoutMarks`, `notMeasuredRow` and their types `ReadoutMark`, `ReadoutRow`, `StripSeries`, `ReadoutOptions` - moves into `readout.ts` too, retyped onto `Readout`, so behaviours 3 and 4 have one home. **Every producer and consumer of `DayReadout` moves in row 5's single commit**, which is why that row cannot be split by panel - there is no intermediate commit where half the console is on the new shape and the tree compiles.

```ts
/** One reading as a chart hands it over: a number its series formats, a word
 *  printed as written, or null for a reading nobody took. */
export type ReadoutValue = number | string | null;

/** A line that belongs to one column only - a run of that day, a settings move. */
export interface ReadoutLine { label: string; value: string; swatch: string | null; }

/** `newest` is the newest column with a reading, `last` the last column drawn,
 *  `first` the first; a number is the column the panel's own sentence names. */
export type ReadoutResting = 'newest' | 'first' | 'last' | number;

/** What a column chart hands the builder. */
export interface ReadoutInput {
	type: 'dateSeries' | 'distribution' | 'tileStrip';
	columns: readonly string[];          // each hoverable column's label, in draw order and reader spelling
	series: readonly {
		label: string;                     // at most 24 characters; a label that wraps turns one entry into two
		swatch: string | null;
		values: readonly ReadoutValue[];
		format: (value: number, column: number) => string; // told the column, so "3 of 12" can read its second number
		note?: string;                     // one constant printed once for the series
	}[];
	events?: { lines: readonly (readonly ReadoutLine[])[]; none?: string };
	notMeasured: string;                 // one string, from the panel's empty-state vocabulary
	resting: ReadoutResting;
}

/** The column shape `ChartReadout.svelte` prints. */
export interface Readout {
	columns: string[];
	series: { label: string; swatch: string | null; values: (string | null)[]; note?: string }[];
	events: ReadoutLine[][];
	eventsNone: string;
	notMeasured: string;
	resting: number;
	empty: string | null;
}

/** The record shape, for a chart whose hover describes one thing at a time. */
export interface ReadoutFacts {
	subject: string;
	facts: { label: string; value: string | null; swatch: string | null; reserve?: number }[];
	notMeasured: string;
	empty: string | null;
}

export function readoutOf(input: ReadoutInput): Readout;
export function factsOf(subject: string,
                        facts: readonly { label: string; value: ReadoutValue;
                                          format?: (value: number) => string; swatch?: string | null }[],
                        notMeasured: string): ReadoutFacts;
export function recordsOf(records: readonly ReadoutFacts[]): ReadoutFacts[]; // each fact reserves its widest reading
```

**The builder refuses what would print a lie.** A series whose length is not the column count throws; a series with no reading in any column has no entry; an empty string or a bare dash as a value throws, because a blank entry reads as a zero. A number stays a number until its one `format` turns it into words. **A chart of records drawn in HTML takes `markReadout`**, the record twin of `pointerReadout`: one tab stop, arrow keys that follow the layout (`walk: 'row'`, `'list'`, or a grid's row length), a tap that selects and stays.

**Two shapes, because most types have no shared column.** A column chart - `dateSeries`, `distribution`, `tileStrip` - has one column per day or bin, and its hover is that column across every series. Every other type describes one thing at a time - a row, a segment, a point, an item or a stage - so its hover is a record. `readoutOf` builds a `Readout` and is called only by the three column types; `factsOf` builds a `ReadoutFacts` and is called by every other type. `ChartReadout.svelte` selects its layout from the shape it is handed: the column strip for a `Readout`, the record for a `ReadoutFacts`. The table below says what each type shows.

| Type | Returns | The strip shows | At rest |
| --- | --- | --- | --- |
| `dateSeries` | `Readout` | the date in reader spelling, then every series at that date with its swatch and value | the newest date |
| `distribution` | `Readout`, two series | the bin's two bounds as the column, then two rows - the count in the bin and the cumulative share at it, each with its own `format` | the slowest bin, because the tail is what the panel exists to find (Susan, 2026-09-28) |
| `tileStrip` | `Readout` | the date, the state in words, and the reading where one was taken | the newest tile |
| `rankedList` | `ReadoutFacts` | the hovered row: its label, its value, and each segment's value and share of the row | the first row |
| `partsOfOne` | `ReadoutFacts` | the hovered part: its label, its value and its share of the whole | the largest part of the first row |
| `paired` | `ReadoutFacts` | the hovered row: before, after, the change, and the attempts behind each side | the first row |
| `overlapTimeline` | `ReadoutFacts` | the item, its source, its shard, its start offset, and each drawn step's own ms | the first item |
| `flow` | `ReadoutFacts` | the stage name, what arrived, what left, what dropped and why | the first stage |
| `pairedScatter` | `ReadoutFacts` | the hovered point: its label and both values | the first point in ranking order |

**`factsOf` has real callers in row 5.** The charts that move a native tooltip into their readout, and the charts that gain hover data for the first time, are mostly record charts - boards, ranked rows, bars against a target - so row 5 builds the record layout and uses it.

**Every chart declares one of three attributes, and a test enumerates them.** `data-readout-columns="<count>"` for a column strip, `data-readout-records="<count>"` for a record strip, or - rarely - `data-readout-none="<reason>; agreed with Susan"`. A chart declaring none of the three fails `frontend/tests/console-readout.spec.ts`, which row 5 widens to the three attributes and to every console route. **A chart somebody decided needs no hover and a chart where the strip was forgotten are the same chart on screen**, which is why the exception must say why and who agreed.

| # | Behaviour |
| --- | --- |
| 1 | **The strip does not move and never floats.** A fixed block below the plot, capped at `chart.readout_max_share`. **Its entries lie side by side and wrap to a new line only when they run out of room - never one entry per line stacked under the chart** (owner, 2026-09-27). A floating box covers the mark it explains; one that dodges the cursor moves the thing being read |
| 2 | **There is no edge case because there is no edge.** The strip cannot leave the panel. What is clamped is the vertical guide, to the plot's own inset |
| 3 | **Pointer:** a column chart takes the nearest column to the pointer's x, on `pointermove`, whatever the y - a reader should not have to hit a 2px line. A record chart takes the row, segment or point under the pointer |
| 4 | **Keyboard:** the wrapping element is one tab stop. Left and Right step a column, Home and End jump, Escape returns to rest. **One stop per chart, never one per mark.** A `ReadoutFacts` strip has no columns to step: Up and Down move between records and Escape rests |
| 5 | **Touch:** a tap sets the column or the record and it stays set. No long-press, no drag-to-scrub, no hover-only value. A tap outside returns to rest |
| 6 | **Dismiss:** pointer leave, Escape, or a tap outside. It returns to the resting column and **is never blank** - an emptying strip changes the panel's height |
| 7 | **A mark with no data prints the not-measured word**, from the same vocabulary the panel's empty state uses. Never a zero, never a dash, never a blank cell. **A null drawn as a zero is the commonest lie a console tells** |
| 8 | **A series absent from the whole window has no row.** A key for a series with no committed rows is a claim the data does not support |
| 9 | **The strip is the legend, and it lies horizontal** (behaviour 1). No chart draws a second key |
| 10 | **No native tooltip on a mark.** Row 5 moves every one into its chart's readout, so the text a pointer showed is now shown to a keyboard and a tap as well; nothing is lost. A `title` outside a chart - a link, a badge - is not a mark and is untouched: the rule is that **no element inside a `[data-readout-columns]`, `[data-readout-records]` or `[data-readout-none]` subtree carries a `title`** |

**One open defect lands with the builder rather than being left where it is.** `chart.readout_max_share` was written for a desktop and wraps the readout into a tall block on a narrow plot. The fix is behaviour 1: entries side by side across the full plot width, then the cap re-set at the width where the readout wraps. It rewrites three assertions in `console-chrome.spec.ts` and `console-timings.spec.ts`, **and that is correct** - a guard moved as a side effect of something else is a guard nobody meant to move, and this one is moved on purpose.

### 2.8 The sufficiency gates - ten, each decidable

A reviewer fails a pull request on any of these. A panel that fails ships only with a `## Design rationale` entry saying why (CLAUDE.md section 9).

| # | Gate | How a reviewer decides | What fails it |
| --- | --- | --- | --- |
| 1 | **Uses the screen it is on** | the panel's spec prints the width the drawn plots cover as a share of the panel's content width, at 390, 768 and 1440. **Covered width**, so two small multiples side by side fill a panel together and two thin charts at opposite edges do not pass as one wide one (Susan, 2026-09-28) | any width where that share is under `console.plot_min_fill_share`, or no share printed |
| 2 | **Separates figure from ground** | the spec reads the colour each surface lands on screen as - the page around the panel, the panel, and the ground under each plot - with every see-through layer blended onto what is behind it | the panel the same colour as the page, or a plot on a ground that is not the panel's own. **A plot gets no tint of its own**: on a sunken ground `--fill-medium` falls from 3.26:1 to 2.89:1 in light, under the 3:1 a fill needs (Susan, 2026-09-28; Fowler agreed) |
| 3 | **One thing lands first** | exactly one element carries `data-lede`, and the spec asserts its measured type size or mark area is the largest in the panel | zero, two, or one that is not the largest |
| 4 | **Made this year** | read the component | a native `title=` on a mark; a bare table of numbers with no shape beside it; a control that is a `<select>` or a verb-button where the two-state radio is the rule. **The clause "a plot with no tint or elevation separating it from the panel" was struck on 2026-09-28**: gate 2 now fails a plot that has a ground of its own (Susan) |
| 5 | **The comparison reads in two seconds** | **exactly one element in the panel** carries `data-comparison="..."` whose sentence contains ` against `, **or** a composition-over-time panel (a stacked `dateSeries` of counts or shares) declares `data-comparison="composition"`, **its stacked bars show two fills or more**, and it ships a `## Design rationale` line saying it has no two-quantity comparison (Fowler and Susan, 2026-09-28) | a missing attribute, or two; a sentence with no "against" that is not the declared composition case. "Peak memory" is a subject; "how near 16 GiB the worst shard got, against the rest" is a comparison |
| 6 | **A trend carries its confounders** | every `dateSeries` sits under a `data-model-rule` declaration, on itself or the element that holds it - the vocabulary `BandDistance`, `StageTimings`, `TimeHistogram` and `ContextCostPanel` already draw. `yes` draws a `data-model-rule-line` or a visible `data-model-rule-empty` sentence; `no` gives its reason in `data-model-rule-none`, five words or more. **No second attribute** - the plan named `data-settings-rule`, and one fact with two attributes can disagree with itself (Fowler and Susan, 2026-09-28) | a trend with no declaration, or a `yes` that draws neither. **A line that moved because somebody changed the temperature looks exactly like a line that moved because the model got worse** |
| 7 | **Every column it draws has a reader** | already enforced by `backend/tests/contracts/test_column_readers.py`, unchanged by this plan | a column drawn while its name is still in `UNREAD_CELLS`. The worker moves the name up rather than routing around the test |
| 8 | **Four nothings, told apart** | the panel renders waiting, quiet, missing and unreachable as four distinct states, from the vocabulary `frontend/src/lib/console/waiting.ts` already owns, **compared as a reader sees them** - the visible words and the colour of the box standing in for the chart. A judged panel needs a driver in the spec's `DRIVERS`, keyed by its id, that puts it into each state; a judged id with none is refused by name (Fowler, 2026-09-28) | any two drawing the same thing. **A quiet pipeline and a broken fetch must never be the same picture** |
| 9 | **The strip is declared** | `frontend/tests/console-readout.spec.ts`, widened by row 5 to the three attributes | a chart declaring none of the three attributes; a declared count with no strip; a `data-readout-none` without its reason and Susan's agreement; a swatch drawn inside a chart that has one |
| 10 | **It queries columns, not ledgers** | `frontend/tests/chart-vocabulary.spec.ts` walks the query door's call sites | `SELECT *`, an unbounded date range, or a ledger fetched whole. **A column ledger read as a row ledger has paid for the format and not used it** |

**Where each gate is enforced.** Gates 1, 2, 3, 5, 6 and 8 are specs in `panel-sufficiency.spec.ts` (row 6). Gate 10 is `chart-vocabulary.spec.ts` (row 4). Gates 7 and 9 are tests that exist today (`test_column_readers.py` and `console-readout.spec.ts`) and are listed so a worker does not write a second copy. Gate 4 is a reviewer reading the component against the capture section 2.9 produces - it is not a spec because "a bare table of numbers with no shape beside it" is not decidable by a selector.

**These gates ship enforcing on an opt-in list, not on the whole console.** The judged set is `console.judged_panel_ids`, a subset of `console.panel_groups` that only the sufficiency specs read; capture (section 2.9) still runs over all of `panel_groups`. Gate 3 needs `data-lede` and gate 5 needs `data-comparison`, and neither exists anywhere in `frontend/src` today; gate 6 needs every trend to declare `data-model-rule`, which four components do and the rest do not. So judging every addressable panel would fail up to three gates on the day row 6 lands. **A gate that is red on arrival is a gate people learn to skip.** A panel joins `judged_panel_ids` in the pull request that redraws it; row 8's panel is the first, and row 6 ships one fixture panel so the gates have a witness before then.

### 2.9 The screenshot gate

**Pixel-diff baselines are refused, and the reason is this repository's rather than general.** A committed baseline is a binary blob `prune.yml` rewrites on a schedule, and font rendering differs between a developer machine and `ubuntu-latest` - so a baseline goes red for a reason nobody caused, and the one thing worse than no gate is a gate people learn to re-bless. `toHaveScreenshot` is not used on this console. **The reader loses** automatic detection of a one-pixel shift; what buys it back is the ten gates above, which are arithmetic and cannot drift.

**So the gate is capture, attach, and a human reads them against decidable assertions.**

| # | | Ruling |
| --- | --- | --- |
| 1 | Viewports | **390, 768 and 1440 CSS px** - exactly the three `console-axis.spec.ts` already measures at. The console measures at three different sets today and this collapses them to one. Reuse, do not fork |
| 2 | Themes | **both, every time.** The dark theme is designed and not derived: a shadow on a dark ground reads as nothing, so a panel that passes gate 2 in light can fail it in dark |
| 3 | Count | **seven images a panel** - three widths times two themes, **clipped to the bounding box of the `[data-console-panel-id="<id>"]` element `Panel.svelte` draws**, plus one at 390 dark with the query door's fetch routed to a 503 by `page.route('**/state/compact/**', r => r.fulfill({status: 503}))`, which is the one way a spec reaches the `unreachable` state without a second build. **As built (2026-09-28):** the clip is the box padded by half the gap to the next panel, so the panel's edge against its ground is in the picture; the seventh image refuses every data request the loaded page actually made, not only the query door's, and first checks each one is made and refused again (Susan's approach, with Fowler's check and Carmack's one bounded settle wait); and **it is taken only where the route asks for data after it arrives**. The Machine route asks for none today, so its panels have six images and a notes line saying why - a seventh would be the healthy page under another name |
| 4 | What each shows | the panel's title, its note, the plot, and the readout strip **at its resting column**. The strip is prerendered and must never capture blank |
| 5 | Where they live | `frontend/test-results/panels/<panel-id>--<width>--<theme>--loaded.png`, and `--unreachable.png` for the seventh (Susan, 2026-09-28), **gitignored**, uploaded as a run artefact and linked from the pull request. Never committed. Each capture test also writes `_notes--<route>--<width>--<theme>.txt`: each panel's state, its plots' share of its width, and the test's run time |
| 6 | The comparison tool is the naming rule | the name sorts so the same panel at the same width in the same theme from two runs lands adjacent in a listing. A reviewer downloads two artefacts and opens two folders side by side. No diffing tool, no dependency |
| 7 | Pass | all seven present, the ten gates green, and **the reviewer can state the panel's comparison sentence after two seconds of looking at the 390 dark image**. That image decides: it is the narrowest, the least tested, and the theme nobody checks |
| 8 | Fail | a missing image; an empty plot where gate 8 was not declared; a strip captured blank; **a 390 image that is the 1440 image with everything smaller.** A panel that only works at one width has not been drawn, it has been positioned |
| 9 | Tooling | Playwright, already here. A new spec group `panels` in `frontend/scripts/test-groups.ts` so the shared selector can skip it when nothing it renders moved. `page.screenshot({ clip })` per panel - no new dependency, no new config file. **Playwright cuts a clip that runs past the window to the window with no error**, so the window grows to fit a tall panel and the PNG's own width and height are checked against the clip; a stuck strip outside the panels is unstuck for the shot, so it is never in a picture (Carmack and Susan, 2026-09-28) |
| 10 | The list is config, not an array | the capture spec reads every id in `console.panel_groups`; the sufficiency spec reads only `console.judged_panel_ids`, a subset. **A panel added to `panel_groups` without a capture fails the capture gate rather than shipping unseen**, and a panel added to `judged_panel_ids` without the three attributes fails the sufficiency gates - within the routes that can produce an id at all. **The Pipelines route produces none** (found 2026-09-28): the capture spec names it in `DRAWS_NO_PANEL_ID` and fails if it starts drawing ids, so its panels cannot become pictureable and stay unpictured |

### 2.10 The panel-by-panel verdict table lives in plan 52

Susan ruled all fifty-one panels on 2026-09-26 - each KEEP, REDRAW, REPLACE, DELETE or NEW, with the columns it queries and the chart it becomes. **That verdict table is plan 52's contract, not this plan's**, and it now lives in [`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md). This plan executes exactly one of those panels - **panel 6b, "What kinds of machine we keep being given"** - and its full spec is row 8.

**One thing the verdict table surfaced belongs here, because it tests section 2.6.** Two plan-52 panels - a machine-speed range and a feed-discount target bar - want a type the starting list does not have. Susan adds it when plan 52 builds them (section 2.6). This plan's own panel needs no new type.

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
  | 7 | **Measured, decision 1's drop does not happen.** Over the 12 committed days, 381 rows, 121 were a job's second half, and no cell disagreed. Fleet placements are 260 before the merge and 260 after, and the machine counters' runs, shards and refused runs are unchanged. The fleet already skipped a row with no fingerprint and `mergeHost` already joined a shard's halves, so no count was doubled. What moves is where the clock sits: 185 of 260 placements carry `job_seconds`, against 64 | Measurement, 2026-09-27 |
  | 8 | **A key whose rows fill one cell two different ways is left as it was, and no count field is returned.** That is a retry on a second runner or a writer fault; merged, the run would be read off whichever machine came first, and `mergeHost` could never refuse it. The test counts the rows that come back. Carmack preferred a named warning at build time; the contract's own words say the test counts, and the page already names the refusal | Fowler and Carmack, 2026-09-27 |
  | 9 | **The colour ramp's own `Other machines` group never takes one of the four named slots.** It always joins the last bar, keeps the ramp's colour, and `outsideTop` keeps its meaning, so the page's two figures are two derivations again. On the committed record the bars become 149, 25, 18, 14 and a last bar of 54, where the ramp's group had ranked second at 68 | Jony, 2026-09-27, breaking a tie between Fowler (for) and Susan (against, as more than the row asked) |
  | 10 | The fold sentence names the kinds too rare for a bar of their own and the machines the page has no colour left for, apart, each once, off the open span's own placements; `another` where the name also has a bar; the count is the number of names listed | Susan, 2026-09-27 |
  | 11 | **Two cyan bars side by side ship, and the colour is defect 37.** With the ramp's group last, AMD EPYC 7763 (stop 3) and AMD EPYC 9V74 (stop 6) stand next to each other in 8 of 11 day groups, and on the dark theme those stops are 2.3 apart on the CIEDE2000 scale, so the panel fails the two-second check there. The fault is the ramp the whole site shares, so it takes its own change; the Hardware drawing page says so in its design rationale | Susan, 2026-09-27 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Settle in the producer so one row lands | Sound design, wrong defect. The producer cannot know the clock at probe time, which is why there are two halves | Its own plan, and it moves a persisted contract | Fowler |
  | 2 | Sweep every remaining raw `readDayShards` call in one row | Right instinct, wrong row. Each ledger needs its own ruling on which key settles it and whether the rule is a merge or a preference | A follow-up that rules each ledger's settlement key, ledger by ledger | Fowler |
  | 3 | Merge this into row 7 | Row 7 is a browser query and a redraw. A correction buried in a rewrite is a correction nobody can revert alone | Zero; costs the revert | Owner, 2026-09-24 |

---

### Row #2 - The console shell: a stuck tab strip, the span control on it, jump links, a completeness sentence

- **Scope:** the chrome every console route sits in, and **the sentence that says how complete the page is**. No panel changes, no ledger is read differently, and no data moves.

**Row 2 ships before row 3, and that ordering is the requirement rather than a convenience.** Every chart on the console draws the newest days that **exist**, not the last N days - so when data stops, a chart gains no gap at the right edge. It slides back in time and looks exactly as full as it did yesterday. Reader's verdict on that, 2026-09-24: *"I read a month-old chart, believed it, and closed the tab satisfied."* A page that can go quiet without saying so is worse than useless, so the sentence exists before anything starts fetching.

**The completeness sentence is a template with named slots, computed from a field that already exists** - `generated_at` on `ConsoleBand`, the instant the run that wrote the record finished. **No new `ConsoleBand` field.** It is UTC (CLAUDE.md section 2), and every slot is formatted in UTC with `UTC` printed beside the time.

Two templates, and one switch chooses between them:

```
Complete to {HH:MM} UTC on {weekday day month}. A run still going is not on this page yet.
```
```
Nothing has been recorded since {HH:MM} UTC on {weekday day month}. {n} days are missing.
```

- **The switch is the reader's clock.** Template 2 fires when the UTC day of `generated_at` trails the reader's own UTC day by more than `console.completeness_grace_days` (default 1). `{n}` is the whole UTC days between the two - today is still being recorded and the record's own day is not missing - so it is at least one, and one reads `1 day is missing.` The prerendered page has no reader's clock, so it prints template 1 and claims nothing about age; a browser recomputes at mount, at every 00:00 UTC, and when the page is shown again.
- **The slots.** `{HH:MM}` is `generated_at` as UTC hours and minutes; `{weekday day month}` is its UTC weekday and date, always spelled out. **No slot says `today`**: the page's day is the UTC day, a reader's is not always, and a prerendered page is read for a day or more.
- **Why not `covers_through` and `compaction_lag_days`, as this row first said.** `covers_through` is a date with no time, and it is the run's own day - the same UTC day as `generated_at` on every run - and `compaction_lag_days` is always 0, so a switch between those two fields can never fire, and a record that stopped being written is not rewritten to say so. Only the reader's clock can see that it is old. **Row 3 has to revisit the sentence**: once panels draw compacted periods, the newest day a panel can draw trails `generated_at`, and the sentence must date that day instead. Corrected 2026-09-27; Susan, Reader and Fowler agreed the clock, the grace and the dropped lag, and Reader ruled the words.

The load-bearing word is **complete**: a promise about the left side and an admission about the right, so once it is read a gap is a fact rather than a defect. It is a sentence, not a badge, not a colour and not a grey timestamp. The filled examples ("Complete to 18:23 UTC on Sunday 27 September"; "Nothing has been recorded since 18:23 UTC on Sunday 27 September. 2 days are missing.") are illustrations, not the contract.

Ruled by Susan on 2026-09-24. The complaint: the Hardware route is fifteen panels long with no quick way back, and the span control sits at the top where a reader nine panels down cannot reach it.

**The strip is built for any number of tabs** (owner, 2026-09-27). The console will gain routes - a Security tab for the canary-feed checks is the next one foreseen - so nothing in this row may assume today's count. The tabs come from the route list in `frontend/src/lib/console/band.ts`, and every layout rule below holds for one tab more or one fewer. Adding a route is a list entry and a page, never a layout change.

| # | Element | Ruling | What the reader loses |
| --- | --- | --- | --- |
| 1 | The tab strip | **Stuck from `frame.breakpoints_px[1]` up**, one tab per console route, however many there are. Below that it stays where it is | one strip-height of every screen above that width, against a long route of scrolling |
| 2 | `Days shown` | Moves onto the strip at the trailing end of the tabs, as a **compact control with one segment per `console.window_presets` value**: the number, and the months it would fetch under it. Below the breakpoint it is the same control on its own row under the tabs, not stuck. Amended 2026-09-27 from "below it, unchanged and full width" - Susan, with Fowler: one control in one place keeps keyboard, screen-reader and reading order the same at every width | the word `days` on every segment, said once beside them; on a phone the band starts one control row lower |
| 3 | The tab description line, while stuck | Hidden. It is already hidden below 1024 px and is the anchor's `title`. An empty box under the strip takes the height back, so the page does not move when it sticks | the one-line summary of the other routes while scrolled; it returns at the top |
| 4 | Back to the top | An **`On this page` row of the route's own group names** under the span control, read from `console.panel_groups[route]`, and a `Top` link on each group heading. A route with no groups, or one unnamed group, shows no anchor row | nothing |
| 5 | The site header | Not stuck, unchanged. Its tagline drops on console routes only | the site's one-line self-description on operator routes; it stays on every reading route |
| 6 | The `Console` heading | Not stuck, scrolls away | nothing. It names the surface once, and repeating it every screen is furniture |
| 7 | The days status sentence | Stays under the strip, never inside it | nothing. It is a sentence, not a control |

- **Files touched:**
  - `frontend/src/routes/console/+layout.svelte` (the strip, sticky from the breakpoint; the span control on it; the completeness sentence; the days sentence under the band; the `On this page` row)
  - `frontend/src/lib/components/ConsoleNav.svelte` (one row and a sideways-scrolling tab list from the breakpoint up, each tab's worst state under its label; the description line's stuck state; the `Worst:` word on the band's worst route)
  - `frontend/src/lib/components/WindowControl.svelte` (the compact control) and `WindowStatus.svelte` (its sentence, split out so it can stay under the band)
  - `frontend/src/lib/components/WindowControlSource.svelte`, `frontend/src/lib/console/window-slot.ts` (each route hands its window up to the layout that draws the control), and the five route pages' `<WindowControl>` line, `machine/+page.svelte` included at that line only
  - `frontend/src/lib/console/strip.ts` (when the strip is stuck; the page kept still; the scroll padding)
  - `frontend/src/lib/console/completeness.ts` (the sentence), `frontend/src/lib/console/band.ts` (reads `generated_at`)
  - `frontend/src/lib/components/PanelGroup.svelte` (a group's id and its `Top` link), `ConsoleBand.svelte` (`Latest day` for `Yesterday`)
  - `frontend/src/lib/components/SiteHeader.svelte` (the tagline drops on console routes)
  - `console.completeness_grace_days`: `config/appearance.json`, `backend/idhazh/contracts/knobs/console.py`, both changelogs, `frontend/src/lib/server/config.ts`
  - `frontend/tests/console-shell.spec.ts` (the oracle), `console-nav.spec.ts`, `console-band.spec.ts`, `console-window.spec.ts`
  - Corrected 2026-09-27: the list named `frontend/src/app.css`, which is `frontend/src/styles/app.css` and needed no change, and it left out the route pages, which each drew their own control.
- **Acceptance gates:** the browser smoke on every console route at 390, 768 and 1440 - the set section 2.9 fixes, straddling the `breakpoints_px[1]` sticky boundary (CLAUDE.md section 12); zero new `[error]` and zero new `404`. Local `npm --prefix frontend run test:changed -- --list`, then the selected checks. CI runs the full suite.
- **Oracle:** at 1440 (above the boundary) the stuck strip's measured height equals one row and each of the route's anchors scrolls its heading into view below the stuck band rather than behind it; at 768 (below) nothing is stuck. **The spec runs twice - with the real routes and with one extra test route added** - so a new tab cannot break the strip. It cannot settle whether the breakpoint is the right one; decision 4 makes it a knob. A media query cannot read the knob, so the stylesheets repeat its value, and `console-shell.spec.ts` reads the knob and checks the strip sticks at it and not a pixel below - moving the knob is a code change to two stylesheets, and the spec says which.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **A dropdown is refused for the span control.** A menu hides all but one option, and it hides the price at the moment the browser starts fetching its own data | Susan, 2026-09-24 |
  | 2 | **Collapsing the logo on scroll is refused.** It buys zero pixels because the header already leaves the screen, and scroll-linked motion has to be designed twice for reduced motion | Susan, 2026-09-24 |
  | 3 | **Collapsing the band is refused.** The band is what an operator reads on landing; collapsed, he opens a disclosure to learn that yesterday failed. Its worst-thing fragment rides in the strip on the worst route's own tab, as the word `Worst:` before the fragment that tab already carries, shown at the top and when stuck alike, and the tab list opens with that tab in view. Amended 2026-09-27 from "one short line": a separate line printed the fragment twice in one row and took about 200 px from the tabs | Susan, 2026-09-24; amended by Susan with Fowler and Jony, 2026-09-27 |
  | 4 | It sticks at `frame.breakpoints_px[1]` (inclusive), reusing the existing key. A stuck control is one band at the width it sticks at, so the tabs and the span control together are one row there. **When the tabs do not fit, the tab list scrolls sideways inside the strip and the span control stays pinned at its end**; the strip never wraps to a second line and no label is shortened, whatever the number of tabs. Below the breakpoint the strip is not stuck and may wrap | Owner, 2026-09-27, for any number of tabs; Susan for the breakpoint. A second key naming that width is the duplicate this project rejects everywhere else |
  | 5 | Named anchors beat one floating arrow. A long route's panels sit in declared groups, and named anchors work with no script at every width | Susan, 2026-09-24 |
  | 6 | This row does not touch `PlatformMixPanel.svelte`. Row 1 owns that file and runs beside this one | Fowler |
  | 7 | **The band's first fact is labelled `Latest day`, not `Yesterday`.** The verdict is the newest day the record holds, which is today once today's first run has finished, so `Yesterday` contradicted the sentence above it. A fixed name needs no clock and stays true on a page read a week later | Susan, 2026-09-27. Reader and Fowler asked for the date itself; the fixed name meets both their reasons without printing the date three times in one band |
  | 8 | **The one-day preset says `1 day`**, in the sentence under the band and to a screen reader | All four, 2026-09-27 |
  | 9 | **From the breakpoint up a tab's worst state stands on its own line under its label**, never broken inside the phrase, so a tab is as wide as the longer line. Measured on the built page with each tab one line wide, the landing route - whose control carries prices and is the widest - showed four of five tabs whole at every width from 1366 to 1920 | Jony, Susan and Reader, 2026-09-27. Susan's condition: every label starts level, a tab with no worst state included |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Stick the strip at every width | On a narrow screen the tabs wrap onto several lines, and a stuck control that wraps covers much of a small screen | Zero; costs the small-screen reader much of the page | Susan |
  | 2 | A floating back-to-top arrow | It goes one place; a route with several groups needs one destination per group, and an arrow needs script where an anchor does not | Zero; costs every destination but one | Susan |
  | 3 | Merge this into row 1 | Route chrome and a settlement-key change in one pull request, because both happen to be about one route | Zero; costs the independent revert | Fowler |
  | 4 | Keep the span control under the band below the breakpoint, moved there by CSS order | Keyboard and screen-reader order would run tabs, control, band while the eye reads tabs, band, control | Zero; costs a keyboard reader a jump past the band and back | Susan and Fowler, 2026-09-27; Reader preferred it for the phone and can live with the control above the band |
  | 5 | Two copies of the span control, one shown per width | Two radio groups to hold in step, and every check that finds the control by its one attribute would find two | A second control, and about 25 locators rewritten | Fowler, 2026-09-27, over Jony's preference |
  | 6 | The band above the strip | The completeness sentence could not sit both under the strip and above the band, and it reverses the order that puts the tabs first on a phone | Zero; costs that order | Fowler and Jony, 2026-09-27 |
  | 7 | A pinned `Worst now:` line while stuck, beside the tabs | It prints the worst tab's own fragment twice in one row and takes about 200 px from the tabs, so they scroll even at 1440 | Zero; costs that width | Susan, Fowler and Jony, 2026-09-27 |
  | 8 | `today` in the sentence, relative to the reader | The page's day is the UTC day and a reader's is not always; beside a UTC time `today` names the wrong day for part of every day far from UTC | Zero; costs the glance `today` gave | Reader and Susan, 2026-09-27 |
  | 9 | Each tab one line wide, label and worst state side by side | On the landing route the fifth tab stayed out of view at every width up to 1920, 5px short at the widest | Zero; saves one line of every tab's height | Jony, Susan and Reader, 2026-09-27 |
  | 10 | The prices leave the tiles while the strip is stuck | It hides what a choice downloads at the moment a reader deep in a route makes it, which is what refused the dropdown, and the tabs slide sideways as the strip sticks | Zero; buys one tab at 1024 and 1280 on the landing route, while stuck only | Jony, Susan and Reader, 2026-09-27 |

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

- **Scope:** section 2.6's starting chart types become modules and a doc page; `d3-shape` is added; the house style in section 2.3 is written. **No panel moves**, which is what lets this revert to nothing.
- **Files touched:**
  - `frontend/src/lib/charts/d3/` - the directory this row creates, which no other row in either plan touches: `scale.ts`, `axis.ts`, `ordered-colour.ts`, `motion.ts`, `empty.ts` with `EmptyState.svelte`, its drawing half, and **one `.ts` module per chart type, plus one `.svelte` component for each type section 2.6 does not give an existing component**, named exactly as section 2.6 names them. `rankedList`, `paired` and `overlapTimeline` get their `.ts` only (corrected 2026-09-27 to match section 2.6); `RankedList.svelte`, `SwapDots.svelte` and `RunTimelinePanel.svelte` keep their props until the row that first draws each from its geometry
  - `frontend/src/lib/console/waiting.ts` (`too-few` and `tooFewSentence`, the floor-missed state the personas ruled on 2026-09-27; the one vocabulary `empty.ts` re-exports)
  - `frontend/scripts/test-groups.ts`, `frontend/scripts/doc-test-inputs.ts`, `frontend/scripts/test-scope.ts`, `frontend/scripts/tests/test-scope.test.mjs` (the new spec joins the logic group, and an edit to the vocabulary page buys that spec rather than reading as documentation only)
  - `frontend/package.json`, `frontend/package-lock.json` (`d3-shape`; `d3-sankey` considered and not taken, 2026-09-27 - section 2.6; added 2026-09-28 by the owner's ruling, deviation 13)
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md` (the starting types join the five marks, the page says marks sit inside types, and **the page is the list a new type is added to**, with Susan's ruling beside it)
  - `frontend/tests/chart-vocabulary.spec.ts` (new: every chart-type module under `frontend/src/lib/charts/d3/` is listed on the vocabulary page and every listed type has its module; the single-engine-importer walk section 2.5 refusal 1 names; and gate 10's columns-not-ledgers walk, which is vacuous until a panel queries in rows 7 and 8)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and `python backend/utilities/doc_load.py` before and after. CI runs the full suite. **The check on a package that lands is its measured compressed weight, recorded on the vocabulary page** - corrected 2026-09-27, because `ci.yml`'s bundle gate weighs pages and data files and scans first-load code for banned names, and weighs no script (Carmack).
- **Oracle:** **every chart type is written down, and nothing has left the house style.** Every chart-type module under `frontend/src/lib/charts/d3/` is listed on the vocabulary page and every listed type has its `.ts` module there, so a new type arrives on purpose - with its page entry and Susan's ruling - never by accident; the five house-style modules section 2.3 declares are the only other modules there. An AST walk finds no `d3-selection`, `d3-transition`, `d3-axis` or `d3-scale-chromatic` import anywhere under `frontend/src/`. It cannot settle whether the starting types are the right ones; the first panel of each, and Susan, do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Doctrine ships before the panel that proves it.** A vocabulary plus a panel cannot be reverted without reverting the panel, and the vocabulary is the half more likely to need editing | Susan, 2026-09-26 |
  | 2 | **On this console d3 is a maths library.** Scales and path generators only; Svelte owns the DOM. A `select()` inside a component has left the vocabulary | Susan |
  | 3 | Four packages are refused by name - the axis, selection, transition and colour-ramp ones - so nobody re-argues them. Each would fork a rule this console already owns | Susan, section 2.6 |
  | 4 | **Nine types to start, and the list grows.** Susan adds a type when a panel needs one; the list lives on the vocabulary page and the test keeps the page and the code in step. It is not an escalation | Owner, 2026-09-27, giving the call to Susan |
  | 5 | **The hatch is a builder that takes its angle from the panel, with no default.** Row 8 mints `console.absent_hatch_degrees` beside its first reader | Fowler, Susan and Carmack, 2026-09-27 |
  | 6 | **The flow's layout is d3-sankey's, and the funnel's two rules are applied on top of it** (re-ruled 2026-09-28; this row first wrote the layout itself on `d3-shape`). Each node sits in the column of its depth, and each column is stacked again from the shared top edge after the library runs. Guardrail #8 made writing our own a person's call, and the owner took the library at about 2 KB gzipped. Deviation 13 | Owner, 2026-09-28, overturning Fowler, Susan and Carmack, 2026-09-27 |
  | 7 | **A floor missed is `too-few`, every floor is an argument with no default, and `paired` refuses one row at a time** | Fowler, Susan and Carmack, 2026-09-27 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Write the vocabulary inside the first panel | The rule would land with no independent witness and could not be edited without touching a panel | One merge cycle | Susan |
  | 2 | Take `d3-axis` for the tick logic | It forks the measured label-thinning rule `dayTicks` owns - a rule that exists because four console axes once drew their dates on top of each other | Zero to take; costs one rule two homes | Susan |
  | 3 | Take a colour-ramp package | It collides with the confidence ramp within a month. Colour comes from the eight chart tokens | Zero; costs the palette its single source | Susan |

---

### Row #5 - One readout strip, every chart, and hover a keyboard can reach

- **Scope:** section 2.7's builder and strip, and **hover data on every chart**: `DayReadout` becomes `Readout` everywhere it is built or read; every native tooltip's text moves into its chart's readout; every chart that shows no hover data today gains it, unless Susan agrees it has nothing more to show; and the narrow-width defect is fixed.

**This row replaces one exported type and cannot be split by panel.** There is no intermediate commit where half the console is on the new shape and the tree compiles, so every producer and consumer moves together. **Commits inside this pull request:** the type swap first, with no visible change; then one commit per chart that moves a tooltip into its readout or gains hover data. **It depends on row 1** (both edit `fleet.ts` and `PlatformMixPanel.svelte`) **and row 4** (it draws to the house style). It also converts plan 54's run-yield chart, which landed on `DayReadout` (#1117).
- **Files touched:**
  - `frontend/src/lib/charts/readout.ts` (new, the builder, `readoutCapStyle`, and the pointer/keyboard machinery), `frontend/src/lib/components/ChartReadout.svelte` (the strip - entries side by side, the column and record layouts - and the narrow-width fix), `frontend/src/lib/charts/frame.ts` (`DayReadout`, `readoutCapStyle`, `columnStrip`, `nearestColumn`, `pointerReadout`, `readoutMarks`, `notMeasuredRow`, `ReadoutMark`, `ReadoutRow`, `StripSeries`, `ReadoutOptions` all leave for `readout.ts`)
  - the other producers of `DayReadout`, under `frontend/src/lib/`: `cost.ts`, `fleet.ts`, `glance.ts` (`timeSplitColumns`, `failureMixColumns`), `machine.ts` (two functions), `doubt-reasons.ts`, `eval-instruments.ts`, `context-cost.ts`
  - the consumers: `Chart.svelte`, `BandDistance.svelte`, `FailurePanels.svelte`, `RunLengths.svelte`, `StageTimings.svelte`, `ThroughputTrend.svelte`, `TimeHistogram.svelte`, `ContextCostPanel.svelte`, `TailTrendPanel.svelte`, `console/+page.svelte`, `JudgeAgreement.svelte`, `MergedStoriesPanel.svelte`, `MergeLinePlot.svelte`, and `routes/console/RunHealthPanel.svelte`, which builds the columns of the one readout `components/RunYield.svelte` and `components/RunSquares.svelte` share
  - the charts whose native tooltips move into their readout: `ShardBoard.svelte`, `voices/+page.svelte`, `DiskReadsPanel.svelte`, `ProcessorLostPanel.svelte`, `ConsoleBand.svelte`, `FailureList.svelte`, `MemoryBoard.svelte`, `RecordGates.svelte`, `RunTimelinePanel.svelte`, `console/+page.svelte`, `MachineCardsPanel.svelte`, `MachineSplitPanel.svelte`, `PlatformMixPanel.svelte`, `HoldoutMargin.svelte`, `VerdictSplit.svelte`
  - the charts that show no hover data today: `KpiCard.svelte`, `Sparkline.svelte`, `SwapDots.svelte`, `TargetBar.svelte`, `SourceCutRange.svelte`, and `Chart.svelte`'s no-column case. **Each gains a readout, or keeps `data-readout-none` with its reason and Susan's agreement written beside it**
  - `config/appearance.json` (`chart.readout_max_share` re-set at the width where the readout wraps)
  - `frontend/tests/console-readout.spec.ts` (the three attributes, every console route, and the moved-tooltip check), `frontend/tests/console-chrome.spec.ts`, `frontend/tests/console-timings.spec.ts` (three assertions move with the cap)
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, and the browser smoke on every console route at 390, 768 and 1440 in both themes. CI runs the full suite.
- **Oracle:** **every chart shows hover data, and no hover text was lost.** Every chart on every console route carries `data-readout-columns`, `data-readout-records` or `data-readout-none`, and every `data-readout-none` names its reason and Susan's agreement; for every chart mark that carried a native tooltip before this row, hovering that mark shows the same facts in the chart's readout; no element inside a declared chart carries a `title`; and for one chart of each shape, Tab reaches it, Left and Right step a column (Up and Down a record), Home and End jump, and Escape returns to rest. It cannot settle whether the strip reads well; the capture group and a reviewer do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Every chart shows hover data.** `data-readout-none` is a rare exception - a chart with nothing to show beyond what it already prints - with its reason and Susan's agreement written in the component. A chart somebody decided needs no hover and a chart where the strip was forgotten look the same on screen, so the exception has to say why | Owner, 2026-09-27; Susan rules each exception |
  | 2 | **The strip never floats and never empties.** A floating box covers the mark it explains; an emptying strip changes the panel's height | Susan |
  | 3 | **A mark with no data prints the not-measured word.** Never a zero, never a dash, never a blank cell. A null drawn as a zero is the commonest lie a console tells | Susan |
  | 4 | **The narrow-width cap is re-set here, on purpose.** It was written for a desktop and wraps the readout on a narrow plot. A guard moved as a side effect of something else is a guard nobody meant to move; this one is moved deliberately and the three assertions move with it | Susan |
  | 5 | **The strip is the legend, and it lies horizontal**: entries side by side, wrapping only when they run out of room. No chart draws a second key | Owner, 2026-09-27 |
  | 6 | **No hover text is dropped.** Every native tooltip's words move into the readout; changing how hover works must not shrink what a reader can see | Owner, 2026-09-27 |
  | 7 | **The builder's shape, as section 2.7 now states it.** Numbers stay numbers until the one `format(value, column)`; `notMeasured` is one string; event lines carry their own `none`; `factsOf` takes a format per fact; `newest` means the newest column with a reading and `last` is a separate rule. `columnStrip`, `StripSeries` and `notMeasuredRow` are deleted, not kept beside the builder | Fowler, 2026-09-28 |
  | 8 | **A moved tooltip's sentence stays on its mark as the accessible name** (`role="img"` and `aria-label`), and the oracle checks that every figure and every word of four letters or more in that name is printed in the strip. A one-time inventory of the titles before and after is taken, not committed | Fowler, 2026-09-28 |
  | 9 | **The cap is 1, the whole plot**, and each value keeps the room its widest reading needs so the strip does not shift as the pointer moves | Susan, 2026-09-28 |
  | 10 | **Arrow keys follow the layout the reader sees**: Left and Right along a row, Up and Down down a list, both across a grid. A record chart that already had its own key keeps it | Susan, 2026-09-28 |
  | 11 | **A distribution rests on its slowest bin**, not its median bin: the tail is what the panel exists to find | Susan, 2026-09-28 |
  | 12 | **Exceptions agreed**: one target bar, the machine cards, the machine split, the platform mix list, the verdict split, the shard board (its titles deleted, every figure already printed on its row), and the empty states of three judgement charts. **Refused**, so each gains a strip: the KPI card trend lines, the standalone sparklines, the source-cut range and the swap dots. HoldoutMargin becomes records for its dots, its off-scale chips and its one-story range | Susan, 2026-09-28 |
  | 13 | **An SVG `<title>` is a mouse-only tooltip too**, so its words move into the strip as well - 25 of them in 13 files. The console band's run squares take one grouped line of verdict words. A failure-table row's `title` is not a chart mark and is untouched | Susan, 2026-09-28 |
  | 14 | **Decision 9's reserve holds at every width, capped at the strip's own width.** The strip is a CSS container and a value's kept room is at most its width, so a phone keeps the room wherever it fits and never scrolls sideways - measured at 31 px sideways on `/evals/` and the console at 360 px before the cap. The first worker's proposal, the reserve from the small breakpoint up only, is not taken: it let entries jump on a phone | Susan, 2026-09-28 |
  | 15 | **The visual-planner flow keeps its exception, reworded**: every stage and every branch prints its count and share beside its node. The one hover-only fact, what a share is of, is printed once under the flow at every width, and where the diagram cannot draw at all - no script, or an engine that never downloaded - the stepped list shows at every width. A record strip under it is refused: it would reprint what the reader is looking at | Susan, 2026-09-28 |
  | 16 | **Three more exceptions agreed**: memory held (one bar a day, every part, bracket and swap printed under it), prompt reuse (one span per request and measure, its low, middle, high and item count printed under it), and the voices weight bar (one row per feed, its weight printed on the row, the floor the one figure in the sentence above) | Susan, 2026-09-28 |
  | 17 | **A KPI card's strip prints no hint; the card grid's lead says it once**, in "line" on `/console/model/` and in "bars" on `/console/`'s `At a glance`, which gains a lead. A card keeps room for its model-change line on every day | Susan, 2026-09-28 |
  | 18 | **The failure ledger's row lines read into one strip under the ledger** that prints the pointed row. One tab stop for every line: Up and Down step causes, Left and Right step days, Escape returns to the worst cause on the newest day. A strip under every row, and one printing every cause at a day, are refused | Susan, 2026-09-28 |
  | 19 | **A sparkline builds its own strip** from its marks, a series label and one formatter told the day. `sparklineMarks` takes `{date, value}` points, so a dropped reading takes its date with it; a swap rule names the point it lands on; a card's figure and its strip print through one formatter. A line in a list reports every change to the list and takes the list's pick back, and the list prints one strip with the same builder | Fowler, 2026-09-28 |
  | 20 | **The card's unused engine-backed trend is deleted**, with `sparkline()`, the comparison test that existed for it and the polarity spec's stub | Fowler, 2026-09-28 |
  | 21 | **The four house-style components keep their `<title>`s until a row puts one on a route.** The tooltip test counts `<title>` elements, so that row cannot merge until it adds the strip. Row 8 is the first that draws one; its file list and plan 52's inherited list are where the four belong | Fowler, 2026-09-28 |
  | 22 | **A strip heads a day in the reader's spelling** through `shortDate`, a mark whose name names the day spells it the same way, `dayMonth` strips stay, and one assertion refuses a heading in the ledger's spelling | Fowler, 2026-09-28 |
  | 23 | **Where a moved `<title>` did not fit a column.** A tinted "nothing measured" span keeps no words of its own: the coverage note prints what the tint is and each day in it prints the not-measured sentence. The context-limit line and the merge line's holdout zone print their whole sentence once under the chart, true when the limit moved or a mark falls off the plot. The throughput strip prints every word of its candles, one entry a run, and holds room for its busiest day. A dashed model-change rule's meaning is one shared sentence beside the chart's "nothing changed" sentence, printed whenever a rule is drawn | Susan, 2026-09-28 |
  | 24 | **The console band's run squares keep their words as their names and lose their `title`**; words after the squares, on their line, say every verdict at once, grouped - `2 runs ran clean, 1 run failed`. The squares sit in the middle of the words' line, and the words stand further from the last square than the squares from each other. A line of its own under the row is refused: it put the band at 134 px against its 130 px line at 1440, and on the same line the band grows about 6 px, not 20 | Susan, 2026-09-28 |
  | 25 | **`At a glance`'s lead is one line at a phone's width: "Point at a card's bars to read a day."** The two-line lead put the first chart at 1,191 px at 390 px against its 1,200 px line on a developer machine, which the CI runner measures lower still. The keys are the ones every other console strip names. If the CI run still puts the first chart past 1,200 px at 390, that number comes back to Susan rather than the line moving on a guess | Susan, 2026-09-28 |
  | 26 | **The readout test's key detector skips a fill drawn inside a mark that names itself** - the disk-read tiles paint each day's bar as an empty span inside the tile that names the day - counting only a mark with no named mark inside it, so a whole drawing that names itself cannot hide a key | Fowler, 2026-09-28 |
  | 27 | **A count prints with its noun, spelt by one call for a column's name and its strip**: the length chart's count row is `Written that day`, `1 summary`, so every word a column's name says is in the strip at that column. A card's strip gets a browser check beside the card-figure test: it rests on the newest day and prints the card's figure exactly; only a card whose newest day is not measured is skipped, and the check fails if it compared no card | Fowler, 2026-09-28 |

- **Landed at #1143:** every chart on the five console routes declares a column strip, a record strip or an exception Susan agreed; no chart carries a `title` or an SVG `<title>`; the KPI cards, the standalone sparklines, the failure ledger's lines and the holdout margin read into strips; seven strips head their days in the reader's spelling. The four house-style components under `$lib/charts/d3/` still draw a `<title>` and are on no route (decision 21).

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Keep the native tooltips where they are | Only a mouse reaches them - no keyboard, no tap, no theme and no test | Zero; costs keyboard and touch readers every one of those texts | Susan |
  | 2 | A floating tooltip that follows the cursor | It covers the mark it explains, and one that dodges the cursor moves the thing being read | Zero; costs readability | Susan |
  | 3 | Move the strip per panel, as each panel is redrawn | `DayReadout` is one exported type with many producers and consumers, so no intermediate commit type-checks | It does not compile | Fowler |

---

### Row #6 - The ten sufficiency gates and the panel capture group

- **Scope:** section 2.8's gates become specs, **enforcing on an opt-in list of panel ids rather than on the whole console**; section 2.9's capture group is added and driven from config. **No panel moves.**

**This row depends on row 4** (the gate specs judge charts drawn to the vocabulary) **and row 5** (both edit `config/appearance.json`, so it lands after the readout row).

**A panel joins the judged set in the pull request that redraws it.** Gate 3 needs `data-lede` and gate 5 needs `data-comparison`, which exist nowhere in `frontend/src` today, and gate 6 needs a `data-model-rule` declaration most trends lack, so enforcing on all 15 addressable panels would make the gate red on the day it lands. Row 8's panel is the first in the set.
- **Files touched:**
  - `frontend/tests/panel-sufficiency.spec.ts` (new: gates 1, 2, 3, 5, 6 and 8 - **gate 4 is a reviewer reading the component and is not a spec**), `frontend/tests/panel-captures.spec.ts` (new, the seven images a panel)
  - `frontend/scripts/test-groups.ts` (the `panels` name in `FRONTEND_GROUPS`, its entry in the `FILES` record, **and its key in the object literal inside `groupedSpecs`** - a missing key there throws `No test group owns <file>`)
  - `frontend/scripts/test-scope.ts` (`CONSOLE` gains `panels`), `frontend/playwright.config.ts` (the project)
  - `config/appearance.json` (**new key `console.judged_panel_ids`**, the opt-in subset the sufficiency specs read; `console.panel_groups` unchanged, still the capture and nav source), `backend/idhazh/contracts/knobs/console.py` (the new key)
  - `frontend/tests/fixtures/panels/` (a test-only panel exercising gates 1, 2, 3, 5, 6 and 8 on one passing and one deliberately failing input, so the gates have a witness before row 8's real panel)
  - `.github/workflows/ci.yml` (**a third `actions/upload-artifact@v7` with `if: always()`, `name: panel-captures`, `path: frontend/test-results/panels/`, `retention-days: 14`** - the two existing uploads are `if: failure()`, and a capture gate whose artefact only exists on red is a gate nobody can read. Plus `SKIP_PANELS_SUITE`, the twin of the console switch)
  - `docs/concepts/design-system.md` (the ten gates **rewrite the five sufficiency checks in place** rather than adding a second list - CLAUDE.md section 5)
  - **Also touched, found in execution (2026-09-28):** `frontend/scripts/tests/test-scope.test.mjs` (the truth table gains the `panels` answer), `frontend/scripts/run-checks.ts` (`SKIP_PANELS_SUITE: 'false'` for a local run), `backend/tests/workflows/test_ci_selection.py` (the fifth answer and the upload); `frontend/tests/support/panel-gates.ts` (the measuring and the six pure judges), `console-panels.ts` (the config read), `console-widths.ts` and `server-render.ts` (the three widths and the server compile step, moved out of `console-axis.spec.ts` and `chart-vocabulary.spec.ts`, which now import them); `backend/tests/test_appearance_config.py` (the contract's three refusals); `backend/idhazh/contracts/appearance_config.py` and `app_config.py` (changelog), the two every-knob fixtures under `tests/fixtures/contracts/`; `frontend/src/lib/server/config.ts` (`consoleConfig()` keeps only its declared keys, so neither new knob is inlined into the five console documents) with its test in `frontend/tests/appearance-config.spec.ts`; `docs/concepts/config/appearance.md`, `docs/reference/test-selection.md`, `docs/how-to/run-the-gates.md` and `docs/reference/agent-notes/browser.md`. **The CI upload is `if: !cancelled()`, not `if: always()`** - a cancelled run's pictures are a partial set (Carmack) - with `compression-level: 0` and `if-no-files-found: error`, and the failure-only traces upload leaves the pictures out
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks, including a first run of the `panels` group over the fixture panel this row ships (the real judged set is just row 8's panel, later). CI runs the full suite and uploads the artefact. **The browser job's own timeout and the site-cap walk are the checks on the capture set** - if the seven-image-a-panel set does not fit, the 768 width is dropped first, because 390 and 1440 are the two the gates are judged at.
- **Oracle:** **every judged id is captured, and every gate catches its failing fixture.** `console.judged_panel_ids` is a subset of `console.panel_groups`, so every judged id resolves to a captured `[data-console-panel-id]`; and over the fixture panel this row ships, each of gates 1, 2, 3, 5, 6 and 8 clears the good input and fails the deliberately bad one - a witness independent of row 8. It cannot settle whether a real panel is good; a reviewer reading the 390 dark image does that, and it cannot reach the four routes that draw no id at all - the three Hard scope - out names, and Pipelines (found 2026-09-28).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Pixel-diff baselines are refused**, and for this repository's own reason: a committed baseline is a binary blob `prune.yml` rewrites on a schedule, and font rendering differs between a developer machine and the runner - so it goes red for a reason nobody caused. **The reader loses** automatic detection of a one-pixel shift; the ten gates buy it back, because they are arithmetic and cannot drift | Susan, 2026-09-26 |
  | 2 | **Both themes, every time.** The dark theme is designed and not derived: a shadow on a dark ground reads as nothing, so a panel passing gate 2 in light can fail it in dark | Susan |
  | 3 | **The 390 dark image decides.** It is the narrowest, the least tested and the theme nobody checks | Susan |
  | 4 | **Three viewports, reusing the three `console-axis.spec.ts` already measures at.** The console measures at three different sets today; this collapses them to one rather than adding a fourth | Susan, Guardrail #4 |
  | 5 | **The naming rule is the comparison tool.** Two artefacts, two folders, side by side. No diffing tool and no dependency | Susan |
  | 6 | The gates ship before the first panel they judge. A gate that lands with the panel it judges has no independent witness | Fowler |
  | 7 | **The gates enforce on an opt-in list, not on the whole console**, and `console.judged_panel_ids` is where that set lives - separate from `console.panel_groups` so capture still covers every panel. The addressable panels would fail up to three gates today, because `data-lede` and `data-comparison` exist nowhere yet and most trends declare no `data-model-rule`. A panel joins `judged_panel_ids` in the pull request that redraws it | Fowler |
  | 8 | **The capture reaches 15 panels on one route, not 26 on two** (corrected 2026-09-28; the plan said 26 on two). The Pipelines route hands `Panel` no id: of its eleven sections one draws three panels, four draw no panel frame and none carries its id, so no picture can be filed by one. The capture names it in `DRAWS_NO_PANEL_ID` and fails the day it starts drawing ids. Giving each section one framed, addressed panel is a route change, not a picture change, and is out of this plan's scope, like the three routes Hard scope - out names | Fowler |
  | 9 | **The witness is composed of the real `Panel` and `DateSeries`**, server-compiled by the step `chart-vocabulary.spec.ts` already used, moved to `frontend/tests/support/server-render.ts` and extended to keep each component's CSS. One good input, and one bad input per gate that fails that gate and no other | Fowler, Susan and Carmack, 2026-09-28 |
  | 10 | **Gate 1 measures covered width** - the union of the plot boxes across the content width. The widest single plot fails two small multiples; the span from first to last passes two thin charts at opposite edges | Susan, 2026-09-28 |
  | 11 | **Gate 2 compares resolved colours** and fails a panel the colour of the page, or a plot with a ground of its own; gate 4's tint clause is struck. **The reader loses** a plot area tinted apart from its panel, and keeps every mark on it readable: a tint under a plot costs every mark (`--fill-medium` 3.26:1 to 2.89:1 in light, the grid 1.20:1 to 1.07:1, the dark axis 3.2:1 to 2.76:1) | Susan, Fowler agreed, 2026-09-28 |
  | 12 | **Gate 3 is exactly one `data-lede`, strictly the largest**: type size against every other visible word, or mark area against every other filled mark | Susan, 2026-09-28 |
  | 13 | **Gate 5 is exactly one `data-comparison`**, and `composition` passes only where its stacked bars show two fills or more | Fowler and Susan, 2026-09-28 |
  | 14 | **Gate 6 reads the existing `data-model-rule` declaration and adds no attribute.** `yes` needs a `data-model-rule-line` or a visible `data-model-rule-empty`; `no` needs a reason of five words or more. `DateSeries` draws no rule line yet, so a judged panel that must say `yes` waits for it | Fowler and Susan, 2026-09-28 |
  | 15 | **Gate 8 drivers are keyed by panel id, with a named refusal**, and compare what a reader sees rather than the component's own state attribute | Fowler, 2026-09-28 |
  | 16 | **The seventh image refuses what the page actually fetched**, checks every recorded address is asked for and refused again, settles once for a bounded time, and is taken only where the route fetched data - so no seventh image is a copy of the first six | Susan, with Fowler's check and Carmack's bound, 2026-09-28 |
  | 17 | **Names end `--loaded` or `--unreachable`; the clip is padded by half the gap between panels; a stuck strip is never in a picture** | Susan, 2026-09-28 |
  | 18 | **A viewport clip, the window grown to fit, and a PNG size check** - no `fullPage`. The panels project runs fully parallel and has no cleanup hook; each capture test records its own run time, reported against the 180 s test timeout | Carmack, 2026-09-28 |
  | 19 | **`panels` is a fifth selector answer, not the console's.** Fowler first proposed reusing the console answer, on the condition that a fifth answer earns its place only if Susan names paths that move every picture and not the console group; she named tokens, `config/appearance.json`, `ChartReadout`, `DateSeries` and `Panel`, so the answer and `SKIP_PANELS_SUITE` were kept | Fowler and Susan, 2026-09-28 |
  | 20 | **A panel id is unique across the whole console**, and the contract refuses one on two routes. Pictures are filed by id alone, and the judged list is a flat list of ids | Carmack, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | `toHaveScreenshot` with committed baselines | Baselines go red for reasons nobody caused, and a gate people learn to re-bless is worse than no gate | Committed binary blobs the prune rewrites | Susan |
  | 2 | Full-page captures instead of clipped ones | A full page is large, so seven a panel stops being affordable, and a reviewer cannot tell which panel moved | Runner seconds and artefact bytes | Susan |
  | 3 | A hand-written array of panel ids in the spec | A panel added without a capture would ship unseen, which is the failure the gate exists for | Zero; costs the gate its completeness | Susan |
  | 4 | Enforce the gates on all 26 addressable panels at once | Three of the ten need attributes that exist nowhere in `frontend/src`, so every panel would fail three gates on the day the row lands. A gate that is red on arrival is a gate people learn to skip | Zero; costs the gate its credibility | Fowler |
  | 5 | The panel pictures follow the console's own selector answer | One answer fewer to keep in step, but a token, chart, readout or appearance edit - the kind that moves every picture at once - would be pictured only on the merge push, after a reviewer had approved it unseen | Pictures of the widest-reaching edits arrive only after the merge | Susan, 2026-09-28 |
  | 6 | A new `data-settings-rule` attribute for gate 6 | `data-model-rule` already declares the same fact on four components, and two attributes for one fact can disagree | A second attribute to keep in step with the first on every trend | Fowler and Susan, 2026-09-28 |
  | 7 | The seventh image from a 503 on `**/state/compact/**` alone | No pictured panel fetches through the query door yet, so it would picture the healthy page and file it as broken | A broken-state picture that shows the healthy page | Susan, 2026-09-28 |

---

### Row #7 - The query door module and its two entry points

- **Scope:** the three modules of the query door under `frontend/src/lib/data/`, **both of its entry points** - `slice()` for a panel in the browser and `sliceFromDisk()` for a build-time reader - and the hand-written index-shape copy the door reads. **No panel, no chart, no config change** - this is the shared reader every later panel calls, shipped with its own witness. **It depends on row 4** (it edits the vocabulary spec and the package manifest that row creates) **and on plan 50's index-shapes row** (its index-shape test binds to the Pydantic contracts that row declares); it needs no live published data, which is why plan 50's migration row can depend on it in turn.

**This is the N2 and N3 keystone.** Section 2.2 is its full contract: `ledger.ts` is the public door (`slice()` and `sliceFromDisk()`, the closed `LedgerName`, the address composed inside the module); `engine.ts` is the only `@duckdb/duckdb-wasm` importer and runs in both places; `slice.ts` turns a date range into the coarsest-period file set with the one-file-per-date invariant. In the browser the engine is reached only through a dynamic `import()`, so it is not first-load. **The door does not merge rows**: plan 50's compaction writes one row per record.

- **Files touched:**
  - `frontend/src/lib/data/ledger.ts` (new: the public door - `slice()` and `sliceFromDisk()` - and the closed `LedgerName`; **the address is composed here and nowhere else**)
  - `frontend/src/lib/data/engine.ts` (new: **the only module that imports `@duckdb/duckdb-wasm`** - the single-threaded browser build behind a dynamic `import()`, and the blocking Node build for `sliceFromDisk()`)
  - `frontend/src/lib/data/slice.ts` (new: a date range to a file set, coarsest period per date, one file per date)
  - `frontend/package.json`, `frontend/package-lock.json` (`@duckdb/duckdb-wasm`)
  - `frontend/scripts/bundle-gate.mjs` (the `FORBIDDEN` list gains `@duckdb/duckdb-wasm` and its `.wasm` asset names, so a static import of the engine or its wasm fails the gate)
  - `frontend/tests/chart-vocabulary.spec.ts` (the single-engine walk finds exactly one importer of the engine, and the import walk finds `sliceFromDisk` only under `frontend/src/lib/server/`)
  - `frontend/tests/ledger-door.spec.ts` (new, in the `logic` group of `frontend/scripts/test-groups.ts`), `tests/fixtures/ledger-door/` (a compacted fixture ledger: daily files, one monthly file, one zero-row day, and both indexes)
  - `backend/tests/contracts/test_frontend_index_shapes.py` (new: binds the hand-written `CompactEntry` and `CompactIndex` copy in `ledger.ts` to the Pydantic originals plan 50 declares)
  - `frontend/tests/console-cold-load.spec.ts` (the engine is not first-load)
  - **Corrected at dispatch, 2026-09-28** (decisions 10 to 18, deviations 7 to 12):
    - `frontend/tests/console-cold-load.spec.ts` leaves this row. No page loads the door yet, so the assertion could not fail; row 8 carries it.
    - The door's logic moves out of `ledger.ts` into a core module under `frontend/src/lib/data/` that takes a byte source and imports nothing tied to one environment - no `$app/*`, no `node:*` - so `ledger-door.spec.ts` can load it. The hand-written `CompactEntry` and `CompactIndex` copy, the stamp this build reads, and the guard get a module of their own beside it, and `test_frontend_index_shapes.py` binds that module. `ledger.ts` keeps `slice()`, `LedgerName` and the public types, and binds `__ASSET_BASE_URL__ || base`.
    - `sliceFromDisk()` moves to a new module under `frontend/src/lib/server/`.
    - `backend/tests/contracts/test_ledger_door_fixture.py` (new): the fixture's two indexes validate against the real `CompactIndex`, and each entry's `rows` and `bytes` match the file the backend reader opens.
    - Docs: a new page under `docs/architecture/publishing/` holds the door's rules and is linked from rule 4 of `docs/concepts/console-design/how-a-console-chart-gets-its-data.md`; `docs/architecture/contracts/schemas.md` names the hand copy, its test and the stamp rule; `docs/reference/site-weight.md` records the engine's measured bytes and the Pages cache reading in deviation 12.
    - The contract gate is `pytest backend/tests/contracts` with no `-q`: `pyproject.toml` already passes one, and a second drops the summary line.
  - **Found in execution, 2026-09-28** (the names decision 16 left to the worker, one question each): `frontend/src/lib/data/slice-shapes.ts` (what a caller may ask, the four answers, the refusal), `frontend/src/lib/data/compact-index.ts` (the hand copy, the stamp and the guard), `frontend/src/lib/data/slice-reader.ts` (the core: the states and the address), `frontend/src/lib/data/slice-query.ts` (the one statement and the rows it hands back), `frontend/src/lib/data/fetched-bytes.ts` (the byte source over HTTP), `frontend/src/lib/server/ledger-disk.ts` (`sliceFromDisk()` and the disk byte source), `tests/fixtures/ledger-door/README.md`, `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`.
  - **Found in execution, 2026-09-28** (the owner's ruling on the parquet reader, deviation 15): `config/idhazh.json` and `backend/idhazh/contracts/knobs/ledger.py` (`ledger.engine_extension_repository`, validated), `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `backend/tests/contracts/test_app_config.py`, `frontend/src/lib/server/config.ts` (`engineExtensionRepository()`), `frontend/asset-base.js` (`engineOrigins()`), `frontend/svelte.config.js` (`connect-src`), `frontend/vite.config.ts` and `frontend/src/app.d.ts` (`__ENGINE_EXTENSION_REPOSITORY__`), `frontend/tests/asset-base.spec.ts`, `docs/architecture/contracts/persistence.md`, `docs/architecture/publishing/the-on-device-encoder-and-its-vectors.md`, `docs/reference/site-weight.md`.
- **Acceptance gates:** local `npm --prefix frontend run test:changed -- --list` then the selected checks; `pytest backend/tests/contracts -q`. `ci.yml`'s bundle gate and site-cap walk are re-read, because a package and a wasm asset landed. CI runs the full suite.
- **Oracle:** given recorded index and parquet responses for the fixture ledger, `slice()` returns exactly the requested columns for exactly the requested date range, reads each date through one file only, returns `quiet` for the zero-row day and `unreachable` on a hole; `sliceFromDisk()` over the same fixture files on disk returns the same rows; and `git grep -l duckdb -- frontend/src` returns exactly one path. It cannot settle whether a panel draws the result well; row 8 and Susan do that.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The door is its own row, not folded into the panel.** It is the keystone every one of plan 52's fifty panels calls, and plan 50 depends on it by name; a keystone ships with an independent witness | Fowler |
  | 2 | **`@duckdb/duckdb-wasm` is the reader, and this is how every panel reads every ledger** - no carve-out for size. The engine is fetched once and cached; a ledger downloaded whole would be fetched on every view by every reader, and that asymmetry holds at any size | Owner, 2026-09-24 |
  | 3 | **The single-threaded build is the pick.** The threaded one needs cross-origin isolation, which needs response headers a static host cannot set; the engine's own bundle selector already chooses correctly | Carmack. Written down so nobody spends a day discovering it |
  | 4 | **The engine is reached only through a dynamic `import()`, and the `FORBIDDEN` list enforces it.** Without that line the rule is a habit, and a careless static import lands the engine in first-load | Carmack |
  | 5 | **`where` is a structured predicate, never raw SQL.** The door binds each value as a query parameter, so no text a panel passes can become SQL (Guardrail #11) | Fowler |
  | 6 | **The door reads a hand-written copy of two shapes plan 50 declares** - `CompactEntry` and `CompactIndex` - bound to the Pydantic originals by `test_frontend_index_shapes.py`, the same binding `test_frontend_field_set.py` already uses. **No `Watermark` copy**: the edge is the newest day `daily.json` names. This plan declares no new persisted contract | Fowler; owner 2026-09-27 for dropping `Watermark` |
  | 7 | **A date is reachable through exactly one file.** The door takes the coarsest period covering a date; the oracle over the two-period rule lives with plan 50's row titled "One compaction task a ledger, two compact periods, and the diagrams move into the page", and this row consumes it | Fowler |
  | 8 | **The door has both entry points, and plan 50 only calls the second.** Plan 50's parquet migration needs today's build-time readers to keep working once the CSV files go; building that entry here keeps one owner for the door and for the engine's Node set-up | Owner, 2026-09-27 |
  | 9 | **The door does not merge rows.** Plan 50's compaction writes one row per record (section 2.2), so a merge here would be a second copy of plan 50's rule | Owner, 2026-09-27 |
  | 10 | **The door reads an index at its own stamp or an older one, and refuses a newer one.** It carries the stamp `CompactIndex` declares, and `test_frontend_index_shapes.py` pins that constant to `CompactIndex.schema_version()`. An index at that stamp or older is read when the fields the door reads pass a guard; a newer one draws `unreachable`, puts both stamps in the browser console, and fetches no data file. This mirrors the backend, where `persist.load` refuses only a newer shape. Deviation 7 | Carmack and Fowler, 2026-09-28 |
  | 11 | **One engine build ships: the single-threaded one that needs WebAssembly exception handling**, emitted by Vite from the site's own origin. A browser without the feature draws `unreachable`. **The package takes a caret range, `^1.33.1-dev57.0`, like every other dependency**: the door's oracle runs against whatever version is installed, so an upgrade that breaks a query or the add-on turns it red on the pull request that raised the version. This replaces the exact pin Carmack and Fowler set at dispatch. Deviations 8 and 14 | Carmack and Fowler, 2026-09-28; owner, 2026-09-28, for the caret |
  | 12 | **The engine's worker starts from a `blob:` bootstrap that imports the same-origin worker file by absolute URL.** A worker started from a same-origin URL takes its policy from its own response headers, and Pages sends none, so it would run with no `connect-src` at all; a `blob:` worker inherits the page's policy, which needs no new source. This row proves the inheritance once on a built page - a `blob:` worker's request to another origin is refused - and writes the reading down; row 8's oracle keeps it | Carmack and Fowler, 2026-09-28 |
  | 13 | **The fixture is what production writes.** The files with rows come from the backend door, `persist()` at the compact tier, for real `HostFingerprintRow` rows; the zero-row day is rendered by the same engine module with the contract's own columns, because `persist()` writes nothing for no rows; the two indexes are hand-written, and `test_ledger_door_fixture.py` checks them. The throwaway script that wrote the files is not committed | Fowler and Carmack, 2026-09-28 |
  | 14 | **The four states, where section 2.2 was silent.** An entry with `rows: 0` is never fetched, so a span of quiet days loads no engine; no rows after the filter is `quiet`, never an empty `ok`. A date after `through` is clamped away, and a span wholly past it is `quiet`. `unreachable.at` is the first hole, ascending; a named file that fails to arrive, or whose decoded length differs from its entry's `bytes`, is `unreachable` at the first date it covers inside the span - the decoded length, because Pages compresses what it serves. `daily.json` absent is `missing`; `monthly.json` absent means no monthly entries; any other index failure is `unreachable` at `from`. A caller error throws by name: no columns, a column that is not `^[a-z_][a-z0-9_]*$` (every identifier is then double-quoted), `from` after `to`, a malformed date, an empty `in` list. Deviation 10 | Carmack and Fowler, 2026-09-28 |
  | 15 | **`monthly.json` is fetched only when the span starts before the oldest day `daily.json` names**, as section 2.2 says, so the 30-day default reads one index and a cold load stays inside four round trips. Carmack preferred fetching both together, which saves the 90-day span one round trip; that is a one-line change once plan 50 writes `monthly.json` from its first run, so a young ledger answers no 404 | Fowler, 2026-09-28 |
  | 16 | **The door is split so a Node test can load its logic.** A core module holds the states, the index guard, the address and the query, and takes a byte source; `ledger.ts` binds the site's prefix for `slice()`; `sliceFromDisk()` lives under `frontend/src/lib/server/`. The engine's Node half is reached only from that server module, and the browser build must be shown to carry none of it. The import walk keeps every panel on `ledger.ts`, so no panel can build a path through the core. Deviation 9 | Fowler and Carmack, 2026-09-28 |
  | 17 | **Files are read by column name** (`union_by_name`), so a span that crosses a day written before a column existed reads that column as null instead of failing, and an integer the engine hands back as a `BigInt` becomes a `number` | Carmack and Fowler, 2026-09-28 |
  | 18 | **This row proves the core, the Node engine and the bundle gate, not the browser engine.** Nothing loads the door in a browser until row 8, so its end-to-end test is the browser half's first run, and the cold-load assertion moves there with it. Deviation 11 | Fowler and Carmack, 2026-09-28 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Fold the door into the panel (row 8) | The keystone would ship with no independent witness and could not be reverted without reverting the panel, and plan 50's dependency on this row's title would not resolve | Zero; costs the witness and the cross-plan pointer | Fowler |
  | 2 | Let a panel build its own path | A panel that could name a path could name any path, and the published list would stop being the bound | Zero; costs the trust boundary | Fowler |
  | 3 | Have the browser probe files until a 404 | A 404 stops being a defect signal and becomes a loop terminator, so a genuinely missing file reads as a normal end | Zero; costs telling an absence from a fault | Fowler |
  | 4 | A `where` clause of raw SQL | It is the Guardrail #11 surface: fetched text reaching the query. A structured predicate closes it | Zero; costs the boundary | Fowler |
  | 5 | Let plan 50 add the build-time entry point | Two plans would edit `ledger.ts` and `engine.ts`, and the engine's Node set-up would have no owner | Zero; costs one owner per module | Owner, 2026-09-27 |

- **Found in execution, 2026-09-28 - ESCALATE: the pinned engine reads no parquet by itself.** Measured on a Windows developer machine, Node 24.12.0. `@duckdb/duckdb-wasm@1.33.1-dev57.0` is DuckDB 1.5.4 and links only DuckDB's core functions; `read_parquet` is a separate extension file, `wasm_eh/parquet.duckdb_extension.wasm`, 3,218,307 bytes, SHA-256 `4845705bbd69fc9ad52878d96a505c73cae4a6c509822079cc2413e5eb437f95`, which the engine downloads from `extensions.duckdb.org` the first time a query needs it. The newest stable release, 1.32.0 (DuckDB 1.4.3), is the same. In a browser the page's `connect-src`, which names this site and the encoder's two model hosts, refuses that host. In Node the blocking build loads an extension only over HTTP or from a cache under the user's home directory, and pointed at a local file or directory it hangs rather than failing. `@duckdb/node-api@1.5.4-r.1` - DuckDB 1.5.4, the same source build - links parquet and read the fixture with no download in 53 ms; it installs a 38 MB binary per platform. **So on this branch every query over parquet ends `unreachable`**, the door's three engine oracle tests in `ledger-door.spec.ts` fail by design, and the branch is not to be merged until the owner rules. **Carmack and Fowler both recommend** serving the pinned extension from the site's own origin - fetched at build time and checked against a SHA-256 kept in `config/`, never committed - and moving the Node half to the native engine at the same DuckDB version. That re-opens decisions 8 and 16, adds a pin file, a fetch step, a package and a CI cache, adds 3.2 MB to the site, and is a scope change the owner approves.
- **Resolved by the owner, 2026-09-28 - the engine downloads its add-on, as it does on any site.** The owner ruled that the site allows DuckDB-Wasm's normal behaviour: the engine's automatic add-on loading stays on, `engine.ts` tells it where to fetch with `SET custom_extension_repository`, and the page's `connect-src` admits that one origin. Both read `ledger.engine_extension_repository` in `config/idhazh.json`, DuckDB's own host by default. Measured the same day with a throwaway page: under the shipped policy Chromium 151 and Edge 154 both refused the add-on (`csp`); with its origin added both read the fixture's month file, 3 rows of 35 columns. The Node half needs nothing else - over HTTPS the blocking build downloaded the add-on in 1.3 s and keeps it under the home directory - so decisions 8 and 16 stand, and there is no native engine, no site copy and no digest. The door's three engine oracle tests pass, one after its span was moved off the fixture's hole on 2026-09-04. Deviations 14 and 15.
- **Found in execution, 2026-09-28 - three rules decision 14 did not state.** A column no file in the span holds reads as null in every row, with the column named in the console - the same answer decision 17 gives for a day written before the column existed. An engine that does not start, or a query it cannot answer, is `unreachable` at the span's first day with the engine's message in the console, as decision 11 already rules for a browser without the feature. A 64-bit integer outside the range a `number` holds exactly is refused by name (`SliceValueError`) and the slice is `unreachable`, rather than the slice throwing at the panel. Worker's reading of decisions 11, 14 and 17.
- **Found in execution, 2026-09-28 - rows come back sorted** by every requested column (`ORDER BY ALL`), so the same files give the same rows in the same order whichever engine reads them. Carmack and Fowler, 2026-09-28.
- **Found in execution, 2026-09-28 - the bundle gate only read the route modules.** It searched `build/_app/immutable/entry/` and `nodes/`, but a chunk a route imports statically is fetched with it, so a static import shared by two routes would have landed in `chunks/` unseen. The gate now follows every static import from those two directories. The encoder check gets the same fix. Bitten 2026-09-28: static imports of the package into the archive and evals pages failed the new gate on two files, both under `chunks/`, so the old gate would have passed that build; a `slice()` call from the front page was not flagged. The same static import also breaks the prerender before any gate runs, with an error that names neither page nor rule - recorded in `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`.
- **Found in execution, 2026-09-28 - decision 13's writer moved under it.** Plan 50's compaction (#1151) landed while this row ran. It split the compact write out of `persist()` into `persist_period()`, which also writes a period that holds no rows, and it made each row's `covers` cell the day its raw file covered, even inside a month file - so the first fixture's month rows were refused, and CI's `gates` job failed on the fixture test. Each fixture row is now filed raw by `persist()` under the job that measured it, then compacted with `load_stored()`, `settle_rows()` and `persist_period()`, the way the compaction builds a period. `host-fingerprint` is not in the compaction's door table yet, so its rows settle by the key its day tree declares. No persona ruled: the fixture follows the contract plan 50 wrote.

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

**The three gate attributes this panel carries** (section 2.8): `data-lede` on the stacked-plot group, which is the lede; `data-model-rule="no"` with the reason in `data-model-rule-none`, on the element that holds the `dateSeries`, because the settings-change rule tracks model settings that do not bear on which machine the platform handed us (row 6 reads this existing declaration rather than the `data-settings-rule` this plan first named, 2026-09-28); and `data-comparison="composition"` with a `## Design rationale` line, because a stacked count over days is a composition, not a two-quantity comparison - the gate-5 exemption, not a miss. **Joining the judged set also needs a gate 8 driver**: `DRIVERS` in `frontend/tests/panel-sufficiency.spec.ts` gains a `platform-mix` entry that puts the panel into each of its four nothings, or the spec refuses the judged id by name.

**Four rules in the machine-pooling doc change, not one.** Besides the ramp reversal (decision 5): the under-threshold form becomes one dot per job (the doc's "a list with a sentence and no bar" was an ECharts-era rule); the doc's sentence that the route "is prerendered, so there is no fetch, no waiting state and no unreachable state" is removed, because this panel now fetches after mount; and the fold justification stops citing ECharts pixel widths. All four edits land in this row's commit.

- **Files touched:**
  - `frontend/src/lib/charts/fleet.ts` (the option builder becomes a d3 draw), `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (queries the door, draws in d3, drill-through), `frontend/src/routes/console/machine/+page.server.ts` (drops the build-time read of this panel's data)
  - `frontend/src/lib/server/host-fingerprint.ts` (this panel stops reading it at build time)
  - `config/appearance.json` (`console.machine_colour_stops` 7 to 5, `console.absent_hatch_degrees` new, `console.judged_panel_ids` gains `platform-mix`), `backend/idhazh/contracts/knobs/console.py` (the two knob changes, section 2.4)
  - `frontend/tests/panel-sufficiency.spec.ts` (a `platform-mix` entry in `DRIVERS`, so gate 8 can put the panel into each nothing)
  - `frontend/src/lib/server/config.ts` (the hardcoded `machine_colour_stops: 7` fallback moves to 5)
  - `frontend/src/lib/charts/machine-colour.ts` (**the arbitrary-key rule reverses to an ordered ramp - see decision 5**), `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`
  - `frontend/tests/console-machine-split.spec.ts` (the "Seven stops for a machine" assertion becomes five), `frontend/tests/console-machine-panels.spec.ts`, `frontend/tests/console-machine-data.spec.ts`
- **Acceptance gates:** the browser smoke on `/console/machine` (CLAUDE.md section 12) - zero new `[error]`, zero new `404`, and **the panel draws each of gate 8's four nothings**: `loading` before the door resolves, `missing` when its ledger is not published, `quiet` when the window is covered but empty, and `unreachable` when a date is a hole or the engine fails to start. Local `npm --prefix frontend run test:changed -- --list` then the selected checks; `ruff check .`, `mypy backend`, `pytest backend/tests/contracts -q`. CI runs the full suite.
- **Oracle:** given a recorded `slice()` response for one compacted fixture day - one row per job, as plan 50's compaction writes it - the d3 panel draws one stacked bar per day with one segment per machine kind, the kinds in median-throughput order, the unrecorded kind last and outside the merged group, and every readout row carrying an absolute rate. **It is not a comparison against the ECharts panel**: this row rewrites `fleet.ts` from an option builder into a draw, so the old panel does not survive the commit, and the row changes the colour count, the shape under the threshold, the merge rule and the readout - so "same colours, same labels" would be false by design. It cannot settle whether the drawing is good enough to ship; Susan rules that (CLAUDE.md section 14).
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

---

### Row #9 - The door keeps what it fetched for the page's life, and says how far a ledger reaches

- **Scope:** the door work plan 52 handed this plan (its section "Found while planning, handed to the plans that own them", item 2), which row 7 merged without. Three changes to the query door, and none to what a panel asks it or gets back:
  - **`ledgerReach(ledger)`** in `frontend/src/lib/data/ledger.ts`, with the signature plan 52 section 2.3 gives: `Promise<{state: 'ok'; first: DateStamp; through: DateStamp} | {state: 'quiet'} | {state: 'missing'} | {state: 'unreachable'; at: DateStamp}>`. It reads `daily.json` and `monthly.json`, starts no engine, and gives one answer a ledger for the page's life. Plan 52's window code anchors a route's span on it. **Corrected at dispatch, 2026-09-29:** `unreachable` carries no `at` (deviation 20).
  - **A data file is fetched once for the page's life**, keyed by its path and the version its index entry names. Row 7 already passes that key: `ByteSource.data(path, version)`, where the version is the entry's rows and bytes.
  - **A file is registered with the engine once**, under a name made from that key, and **every name sits under one directory, `door/`**. Today each slice registers its files under fresh names and drops them when it ends. **Corrected at dispatch, 2026-09-29:** the engine mints each name, `door/<n>.parquet`, from a counter, never from the key, an index or a caller (decision 5).

  **Why now.** Plan 52 counted one route at 30 days: about 590 requests and up to 14 copies of one window without the cache, about 62 requests and one copy with it (Carmack). Its route rows ask one window from up to fifteen queries a route, and changing how the door spends requests after a panel calls it would move that panel's numbers under it. **No page, no panel.**
- **Files touched:** `frontend/src/lib/data/ledger.ts`, `frontend/src/lib/data/slice-reader.ts`, `frontend/src/lib/data/slice-query.ts` (the engine takes a key with each file), `frontend/src/lib/data/engine.ts` (the names and how long a registration lives), `frontend/src/lib/server/ledger-disk.ts` if the build-time reader shares the change, `frontend/tests/ledger-door.spec.ts`, `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`. **Found in execution:** `frontend/src/lib/data/page-keeper.ts` (new: what a page keeps, and the byte-source type, moved from `slice-reader.ts`), `frontend/src/lib/data/ledger-reach.ts` (new: how far a ledger reaches), and `frontend/src/lib/data/fetched-bytes.ts` (its header, decision 9)
- **Acceptance gates:** `npm --prefix frontend run test:changed -- --list`, then the selected checks. CI runs the full suite. No browser smoke: this row draws nothing.
- **Oracle:** **each file crosses the network once and enters the engine once.** Over the fixture ledger, with a byte source and an engine that count what they are asked: two slices over overlapping spans fetch each data file once and register it once; a file whose index entry names a new version is fetched and registered again; every registered name starts with `door/`; and `ledgerReach` answers the first and newest day the two indexes name, or `missing`, `quiet` or `unreachable` wherever `slice()` would, with no engine started. It cannot settle whether a route is fast enough; plan 52's row titled **The query door, measured at the console's real volume** does.
- **Settled at dispatch, 2026-09-29 (Carmack and Fowler):** in a browser an index is read once a page and kept, and a tab left open across a deploy shows the data it opened with; the build-time reader reads its indexes fresh on every call. Decisions 4 to 9 and deviation 19.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **This row lands before any panel calls the door**, so row 8 waits on it (deviation 17) | Plan 52, found while planning, item 2 |
  | 2 | **Every registered name sits under `door/`.** Plan 55's seal belongs to the whole engine, not to one connection: measured 2026-09-28, a seal set from one connection refused a file outside the allowed directory on a second. A tab keeps one engine across console pages, so once plan 55's page has sealed it, a panel file outside `door/` would read nothing. Choosing the directory costs nothing here, because this row renames the files anyway | Plan owner, measured 2026-09-28 (plan 55 section 2.6) |
  | 3 | **A column-shaped result, a "newest N days" ask and a structured aggregate are not in this row.** Plan 52 names them as the fixes for a miss in its measurement row, so they wait for that reading | Plan 52 section 2.10 |
  | 4 | **A page keeper, `page-keeper.ts`, holds each ledger's two indexes and the name the engine holds each data file under, for the page's life - names, never bytes.** Two asks at the same moment share one fetch; what a fetch returned is kept, the bytes or the 404, and a fetch that threw is not; a file of the wrong length is neither registered nor kept; the engine starts only when every file a slice needs arrived whole. A browser's engine empties the buffer it is handed, so kept bytes would read as an empty file | Carmack and Fowler, 2026-09-29 |
  | 5 | **The engine mints every name, `door/<n>.parquet`, from a counter**, never from index text, a `covers` value or a caller, so no fetched text can name a file. `QueryEngine` becomes register (bytes in, the minted name out), drop, and rows over a statement that names the files | Carmack and Fowler, 2026-09-29 |
  | 6 | **One keeper a page in a browser, made on first use in `ledger.ts` and never released, so the per-slice drop goes; a fresh keeper for each `sliceFromDisk()` call, which reads the indexes as the disk holds them and drops every file it registered when the call ends.** A build reads many ledgers in one process, and a development server reads `state/` again as it changes | Carmack and Fowler, 2026-09-29 |
  | 7 | **No retry on a stale file.** A kept index and a day file re-packed or removed after a deploy answer `unreachable` with the reason, and a reload fixes it | Carmack and Fowler, 2026-09-29 |
  | 8 | **`ledgerReach(ledger)` sits beside `slice()` in `ledger.ts`, and its logic in `ledger-reach.ts`**, not in `slice-reader.ts`. It reads both indexes at the same time through the keeper, starts no engine, and reads each index with the slice's own reader, so the two never disagree. `through` is the newest daily day; `first` is the oldest day either index names, a month counting from its first day; a `monthly.json` this build will not act on leaves the daily days and a console line saying why | Carmack and Fowler, 2026-09-29 |
  | 9 | **Row 7's "an index, never from a cache" becomes "read once a page, and kept"** in the byte source's comment, the header of `fetched-bytes.ts` and the door's page, which says what an open tab shows after a deploy and why (deviation 19). The byte-source type moved to `page-keeper.ts`, the module that now reads through it | Carmack and Fowler, 2026-09-29 |
  | 10 | **The oracle's new-version case is a new keeper, not a changed entry under one keeper.** A keeper keeps its index, so an entry cannot change under it; the next page's keeper asks for the re-packed file under its new version and registers it again, while the open page answers from the name it holds | Row 9's worker, as the dispatch asked, 2026-09-29 |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Leave the cache to plan 52's window code | A second cache in front of the door, and plan 55's page, which does not use that code, would pay the full cost | Zero; costs one cache a caller | Plan owner |
  | 2 | Let plan 52 fall back to asking `slice()` for today to learn a ledger's newest day | By plan 52's own estimate, a 90-day window then reads `unreachable` until about 31 October | Zero; costs the console its longest window for a month | Plan 52 section 2.3 |
  | 3 | When a kept index names a file the deploy re-packed or removed, read both indexes again and retry once | Nothing has shown an open tab meeting this, and the retry would move a page's first and newest day under panels already drawn. It is the move if an open tab is ever seen answering `unreachable` after a deploy | About 20 lines in the reader | Carmack and Fowler, 2026-09-29 |
  | 4 | A caching byte source in front of an unchanged engine: keep each file's bytes and register them again for every slice | A browser's engine empties the buffer it is handed, so the second slice would hand it an empty file; the Node engine copies, so every Node test would pass while the browser failed. The spec's engine now empties buffers the browser's way, and this design fails it | About 10 lines; costs a door that works only in Node | Carmack and Fowler, 2026-09-29 |

## Dependent plans

- `TODO/20260924-50-idhazh-gardener-plan.md`. Row 3 waits on its rows titled **One compaction task a ledger, two compact periods, and the diagrams move into the page** and **The three ledgers the console's routes read become parquet**. In the other direction, plan 50's row titled **The three ledgers the console's routes read become parquet** waits on this plan's row 7, titled **The query door module and its two entry points** - and row 7 depends only on row 4 and on plan 50's index-shapes row, neither of which reaches that migration, so row 7 lands first and the two pointers resolve without a cycle. **Plan 50 also owns two things this plan relies on**: its compaction writes one row per record, so the door never merges; and its migration row moves today's build-time readers onto row 7's `sliceFromDisk()`, which lives under `frontend/src/lib/server/` (deviation 9), and adds no export of its own. Nothing else in that plan is a predecessor here.
- `TODO/20260926-54-check-publication-plan.md`. Its run-yield chart landed on `DayReadout` (#1117) and now shares one readout with the run squares in `Run health`; row 5 converts that readout, built in `routes/console/RunHealthPanel.svelte`, with every other chart. Nothing here waits on plan 54.
- **[`20260926-52-fifty-panels-move-and-six-projections-go-plan.md`](20260926-52-fifty-panels-move-and-six-projections-go-plan.md)** takes over after row 8, in thirteen rows. Its route rows wait on rows 3 and 8 here, and its window code reads `ledgerReach` from row 9. **The panel-by-panel verdict table Susan ruled now lives in plan 52** - all fifty-one panels, each KEEP, REDRAW, REPLACE, DELETE or NEW, with the columns each queries and the chart it becomes. Many of the redraws and new panels exist only because the browser can now query the ledger. One row per route; each row moves that route's panels to the query door and **deletes the projection under `frontend/public/` that fed them**. Rows 4 to 8 here exist to make that plan cheap, not to be it.
- **The old charts are evidence of an old limit, not a decision to preserve** (Susan). They were drawn against what a build-time projection could carry - a narrow, pre-summed slice of the columns - so columns of real answers sat unread on every run: why an article was chosen, why a fetch was slow, what the source answered, how old the news was, whether a summary was cut off and reported as a success, which rule refused a reply, and whether a trend moved because of the model or because somebody changed a setting. Plan 52 draws them.
- [`20260928-55-one-page-queries-every-ledger-plan.md`](20260928-55-one-page-queries-every-ledger-plan.md). Its row 3 edits the door's own files and needs row 9's `door/` names for its seal, so it runs after row 9; its row 4 extends row 3's copy step, so it runs after row 3. Nothing here waits on it.
- `TODO/20260823-known-defects-plan.md`, defect 33, closes in row 1's pull request.

## See also

- [docs/concepts/telemetry-intent.md](../docs/concepts/telemetry-intent.md) - the eleven statements this plan lays stones for.
- [docs/concepts/console-design/how-a-console-chart-gets-its-data.md](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) - the seven rules every row here is built to.
- [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the contract the stamp points at.
