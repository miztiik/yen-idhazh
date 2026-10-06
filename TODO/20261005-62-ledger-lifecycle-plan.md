# Plan 62 - Ledgers that start, pause, resume and stop

**Last Updated**: 2026-10-05

**Level**: 3 (CLAUDE.md section 6). L1 and L5 cross a boundary: L1 joins the site build to the data explorer, and L5 changes how every console route places its window. No row changes a persisted shape, and Table C, C1 stops any row that would.

**Status**: written 2026-10-05 from Fowler's proposal and his revision of the same day, and from the owner's rulings on them (Table D). Checked against `main` at 36fe716e0. L1 merged under plan 60 as #1327 (row L1, decision 5). The owner ruled that the plan 60 owner session runs this plan after L1 merges (Table D, D4). An id such as "Fowler's option M3" names a row of those two documents, which are not in the repository.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Ledgers start, pause, resume and stop. Since #1309 a ledger's index starts on its first raw day, but the readers treat a day before a ledger began as a day that is missing: the data explorer asks the archive for it and then reports a fault. The tests hid this until #1309, because the canary began every ledger on the 1st of a month and the browser answer key read other inputs than the page. Now ten browser tests fail on `main` (run 37361239642, 2026-10-05). This plan makes every reader and every test treat each stage of a ledger's life as normal |
| A2 | Hard scope - in | - The data explorer leaves out a ledger's days before its first day and names that day, and it asks the archive only for days the site copy trimmed (L1).<br>- Every data explorer browser test serves data it built and checks written-out results. The canary keeps only the checks that do not depend on what it holds (L2).<br>- The real compaction is tested on each lifecycle state, and the states get a page of their own (L3).<br>- A panel slice leaves out the days before a ledger began and names its first day. How far a ledger is packed comes from all three indexes (L4).<br>- Every console window ends on the site's newest published day, reads exactly that window, and says when a record's rows stop (L5).<br>- A published ledger that has no compact folder yet does not stop the site build (L7).<br>- When the archive does not answer for trimmed days, the explorer answers the site's days and names the archive (L8).<br>- Console specs outside the explorer that read canary content serve the data they check (L9) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Change the readers and the tests, never the data: no persisted shape changes, a day before a ledger began is outside the ledger and never a fault, every window ends on a day that no ledger can move, and every test serves the data it checks. Fowler, 2026-10-05, on the owner's rulings of the same day |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows that share a file run one at a time, computed from their Files touched lists. L5 and L9 never run at the same time, because each finds part of its list of console specs only when it is dispatched. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table B - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | A field on the compact index, written by the site copy, that says where the copy trimmed: `trimmed_before` (Fowler's C2) | The explorer works out whether the site trimmed a ledger from the copy's own rule, shared through `frontend/src/lib/data/site-window.ts` (new in L1), and one build constant. That holds while the rule is "a window of days that ends on the newest named day", and while a committed index names every day after its first entry, which is true by construction since #1309 | A trim rule of another kind, for example a cap by bytes. Then a Level 5 change in two commits, reader first (CLAUDE.md section 11): an optional date `trimmed_before` on `CompactIndex` in `backend/idhazh/contracts/ledger_index.py`, with a new version and changelog line; the frontend copy in `frontend/src/lib/data/compact-index.ts`, with its guard and `COMPACT_INDEX_STAMP`; and the field set in `backend/tests/contracts/test_frontend_index_shapes.py` |
| B2 | A field on the compact index, written by the gardener, that names a ledger's first recorded day: `begins` (Fowler's C3) | After a ledger's first month closes, its month entry starts on the 1st. So the days of that month before the ledger began read as quiet days instead of being cut. No surface misreads this today: the console dates "Recording started" from rows, not from the index (`frontend/src/lib/console/recording.ts`). A day before a ledger began and a day dropped by retention also read the same, and no answer needs to tell them apart | A surface that must name a ledger's exact first day after its first month closes. Then a Level 5 change on the gardener's own index. Plan 60's row "The marks are worked out from the indexes, and the watermark files go" could not rebuild the field from named paths without a read that grows (Guardrail #12) |
| B3 | A pause mark and a stop mark on each period (Fowler's C4) | A paused writer, a stopped writer and a quiet stretch all read as `empty` days. The family's `lifecycle_status` in `config/ledgers.json` says only what is true now, with no date | Writers that record "ran and wrote nothing" apart from "did not run": a new writer record, Level 5 |
| B4 | Choosing the words of three sentences that Reader and Jony own (Fowler's E5, E9 and H3): the explorer's answer for a ledger that has never held a row, joined with one that has rows; the `behind` note for the days a stopped packing has not reached; and the sentence for trimmed days that the archive did not answer | The first two keep today's words. The first says that the ledger is not on this site yet, which is false for a ledger that is packed but has never held a row. L8 cannot finish without the third | Reader and Jony rule (CLAUDE.md section 14). L8 asks them for the third when it is dispatched, and L5 takes the second if they rule first. The first needs a Level 1 row of its own after their ruling |
| B5 | Showing a family's `paused` or `retired` status on a console surface | An operator sees no sign of it. The explorer already parses the status (`frontend/src/lib/console/explorer/registry.ts`) and shows nothing from it. No family is paused or retired today | Reader and Jony rule whether and where it shows; then a Level 1 row |
| B6 | A test that each published explorer example names only columns its ledger has | No test catches an example that names a column its ledger lacks; it fails when an operator runs it. Table G, G17 checks the statement, the ledgers and the preset only | A contract-tier row that reads each example's columns against its ledger's row contract (CLAUDE.md section 13) |
| B7 | Specs outside the console that compute their answer from data, such as `frontend/tests/ledger-ranges.spec.ts`, which takes its expected slice from the disk reader | They break Table D, D3 until a row rewrites them, and a producer change can still turn one red after a merge | L9's inventory, run over the `reader`, `archive`, `publishing` and `model-search` groups, as a row of its own |

### ESCALATE triggers

Table C - when to stop and ask

| # | Trigger | What happens |
| --- | --- | --- |
| C1 | A change to a persisted shape: a model under `backend/idhazh/contracts/` that a later run reads, or a frontend copy of one, such as `frontend/src/lib/data/compact-index.ts`. No row here moves one; Table B prices the three this plan leaves out | Stop and surface ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)). A persisted shape is a Level 5 decision for the owner |
| C2 | A row's Oracle, or a test that a row adds, that would read the canary's content or compute its expected answer from data (Table D, D3) | Stop. Write the check again on a root the test builds, with its expected values written out |
| C3 | A change that lets a ledger's first day choose, widen, move or end a window (Table D, D2) | Stop and surface. The window rule is the owner's |
| C4 | Two personas still disagree after one debate | Stop and surface |

## 1. Status Reckoner

Row ids are the phase ids of Fowler's proposal, which the plan 60 owner already uses. L6 is not a row: it is L9's rejected alternative 1.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Days before a ledger began are cut from the selected window | - | A | DONE #1327, carried under plan 60 (row L1, decision 5) | fantastic-fortnight | #1327 | L1 explorer starts at first day |
| L2 | Explorer browser tests serve the data they check | L1, plan 60 row #32 | B | PENDING | - | - | - |
| L3 | Lifecycle states at the producers | L1 | B | PENDING | - | - | - |
| L4 | A slice cuts only the days before a ledger began | L1 | B | DONE | fluffy-couscous | - | Plan 62 row l4 |
| L5 | Console windows end on the site's newest published day | L4 | C | DONE | solid-potato | - | Plan 62 row l5 |
| L7 | A published ledger that has not started | L1 | B | PENDING | - | - | - |
| L8 | The archive's failures are named as the archive's | L1, L2, L4 | C | PENDING | - | - | - |
| L9 | Console specs outside the explorer serve the data they check | L2 | C | PENDING | - | - | - |

## 2. Shared declarations

Rows point here. Each rule, word, state and test is declared once.

### 2.1 The owner's rulings

Table D - the owner's rulings of 2026-10-05

| # | Ruling | Authority |
| --- | --- | --- |
| D1 | When the window selected in the data explorer starts before a ledger's first day, the answer leaves out that ledger's earlier days. It names the first day in the sentence the explorer already prints when no archive is set: "Days before {day} are not on this site." L1's rejected alternative 1 holds the option this ruling turned down | The owner, 2026-10-05 |
| D2 | A window ends on the current day. The data explorer opens on today, its presets end today, and the reader's window selection sets the span. A ledger's first day never chooses, widens or moves a window, so a ledger that began four years ago never makes the explorer open four years in the past | The owner, 2026-10-05 |
| D3 | A test checks what the code does, never what the data holds. No test computes its expected answer from data: no answer key runs the query door again over the canary or the committed data. No test depends on what a fixture happens to hold, beyond what the test built for its own purpose | The owner, 2026-10-05 |
| D4 | Fowler's phases are one plan, this one, which the plan 60 owner session runs after L1. The rest of his phase list is approved | The owner, 2026-10-05 |
| D5 | Every console window ends on the site's newest published day (Fowler's option M3) | The owner, 2026-10-05 |

### 2.2 Words this plan uses

Table E - words

| # | Word | Meaning |
| --- | --- | --- |
| E1 | First day | The oldest day that any of a ledger's three indexes names. A month entry counts from its 1st, and a year entry from 1 January (`frontend/src/lib/data/slice.ts`) |
| E2 | Tier | A place an answer reads from: the site, the archive, or the writers' raw files that the site build lists |
| E3 | Site copy | The build step that copies each published ledger's indexes, and the files they name, to the site (`frontend/scripts/published-ledgers.mjs`) |
| E4 | Trim line | The first of the N days that end on the newest day the indexes name, where N is the widest preset in `console.window_presets` (`config/appearance.json`). The site copy keeps every entry that overlaps those N days |
| E5 | Archive | The committed `state/` files on `main`, which the explorer reads from `ledger.archive_base_url` (`config/idhazh.json`) |
| E6 | Cut | Start an answer later than the window asked for, and say so in the answer |
| E7 | Pinned day | The UTC day a test sets as today: with `page.clock` in a browser test, or as an argument in a logic test. A built root's days are counted from it |
| E8 | Built root | A state tree that a test writes for itself with the builder (Table G, G1) |
| E9 | Newest published day | The newest day the site published a digest, as `latestDate()` in `frontend/src/lib/server/payload.ts` reads it |
| E10 | Canary-day move | A measurement, never a commit. Set `DATE` in `backend/utilities/build_canary_day.py` to a later day, run the named specs with `npm --prefix frontend run test:changed`, which builds the canary again from the edited file, and set `DATE` back. It reads nothing the canary holds: a spec that turns red is a spec that depends on what the canary holds |

### 2.3 The states of a ledger's life

Table F - lifecycle states. The third column is true on `main` today. The fourth is what this plan builds, and it names the row that builds each part.

| # | State | What the indexes say | What every reader answers |
| --- | --- | --- | --- |
| F1 | Declared, never packed | No compact folder for the ledger: a pass with no raw day writes nothing | The door answers `missing`: a panel says the record is not packed yet, and the explorer says the ledger has no days on this site yet. The site build stages nothing for it and writes one log line (L7) |
| F2 | Packed, never held a row | Every entry is `empty`, or `packed` with 0 rows where it was written before #1309 | Quiet days |
| F3 | Begins mid-month | The first daily entry is the first raw day. Once its month closes, the month entry starts on the 1st; once its year packs, the year entry starts on 1 January | A window that starts before the first day is cut at that day, and the answer names the day. Never `unreachable` (L1 for the explorer, L4 for a panel slice) |
| F4 | Quiet day | An `empty` entry with no file. A month or a year with no row is `empty` too | A quiet day, with no gap named |
| F5 | Lost day | A `lost` daily entry, or the day listed in a month's or a year's `lost_days` | Named as lost, as today |
| F6 | Writer paused, then resumed | `empty` days while it is paused. The family's `lifecycle_status` in `config/ledgers.json` holds only its current value | Quiet days, as F4 |
| F7 | Writer stopped or retired | As F6, with no end: `empty` days continue up to the newest due day | Quiet days. A console record whose rows stop before the window's start says so (L5) |
| F8 | Packing paused, then resumed | The newest entry stops moving. After the resume it moves `max_periods_per_run` days a wake. The task's `lifecycle_status` is in its declaration under `config/gardener/`, which the site does not carry | How far the ledger is packed is the newest day any index names (L4). The days after it stay visible at the window's right edge, and the `behind` note names them (L5) |
| F9 | Packing stopped | As F8, and the indexes freeze | As F8 |
| F10 | Trimmed off the site, still in the archive | The site copy dropped each entry that ends before the trim line. The trimmed index carries no mark of it | The explorer asks the archive only for trimmed days inside the selected window (L1). If the archive does not answer, the explorer answers the site's days and names the archive (L8) |
| F11 | Dropped by retention | A month past its keep window is deleted with its entry, so the first day moves later | As F3 |
| F12 | Index missing | Some of the three indexes, but not all of them | A fault, as today: `index-missing` when `monthly.json` or `yearly.json` is absent. The site build refuses a ledger that has some of its indexes but not all three |
| F13 | A hole inside the ledger | A day after the first day with no entry | A fault, as today: `day-missing` |
| F14 | Not packed yet | The site build lists the raw days after the newest packed day | The explorer reads them, and panels stop at the newest packed day, as today |

### 2.4 The tests

Table G - the tests. A G-number is Fowler's test number (his I7 is G7 here), so G11 and G12 are kept and not used. Test titles are in Table H.

| # | Test | Row | Tier and group | What it proves | The edit that makes it fail |
| --- | --- | --- | --- | --- | --- |
| G1 | The builder, `frontend/tests/support/ledger-lifecycle.ts` (new). Input: a ledger name, a pinned day, and a list of days, each `packed` with N rows, `empty` or `lost`, plus set-aside counts and closed months. Output: three indexes and real Parquet files in a temporary root. Each file holds a `covers` column and one value column, and each entry's `bytes` is its file's length. It can write a root's site copy with the real trim rule, and it can serve a root to a page. It reads no committed fixture. It writes each file with DuckDB-Wasm's `COPY ... TO`, in the Node build that `nodeEngine` in `frontend/src/lib/data/engine.ts` loads (estimate: not tried there). DuckDB's `COPY (SELECT ...) TO ... (FORMAT PARQUET)` wrote a one-row file for #1318's test. Fallback: a backend script writes the same roots with `ledger.persist`, committed under `tests/fixtures/ledger-lifecycle/` (new, only if the fallback is taken), one root a state | L1 | Fixture | Nothing by itself | - |
| G2 | `backend/tests/gardener/tasks/test_compaction_lifecycle.py` (new), one test a state. Each test writes real raw files under `tmp_path` with `backend/tests/gardener/tasks/_task.py`, and builds its own declaration | L3 | Integration, backend | The real compaction, wake by wake, writes the right entries for: begins mid-month; writer paused, then resumed; writer stopped through a month close; packing resumed after a stall; never written | Filling days before the first raw day (#1309 reverted) fails "begins mid-month". Writing no entry for a day with no raw folder fails "paused" and "stopped". Taking every due day in one wake fails "resumed" |
| G3 | `frontend/tests/ledger-copy.spec.ts`, extended, on state trees the test writes | L3 | Unit, `logic` | Each tree has a written-out list of kept entries and a written-out yes or no from the shared trim rule. A ledger built to begin 120 days before its newest day, with a 90-day window, is kept from that newest day minus 89, and the rule says yes. A ledger built to begin 30 days before keeps every entry, and the rule says no. The copy and the rule are never checked against each other | Changing the copy's window without changing the rule, or the reverse |
| G4 | `frontend/tests/ledger-lifecycle.spec.ts` (new), named under `logic`, on roots G1 builds | L1 (explorer cases), L4 (slice and reach cases), L5 (window cases), L8 (archive failure) | Integration, `logic` | Each state of Table F against written-out values: the first day answered, `siteFrom`, the day in the sentence, the exact archive requests (often none), and `day-missing` for a hole after the first day | Answering a day before the first day as `unreachable`; asking the archive whenever the span starts before the site's first day; cutting at a hole instead of naming it |
| G5 | Delete H43 | L1 | - | It pins today's fault with dates from a fixture made for other door questions. G4 covers its behaviour | - |
| G6 | Delete H41 | L4 | - | The same reason. G4's slice case replaces it | - |
| G7 | Test support. Delete `EXPLORER_CANARY_DAY`, `expectedAsk` and `expectedAskCost` from `frontend/tests/support/explorer-answer.ts`, and let `openExplorer` pin the day its caller names. `frontend/tests/support/browser.ts` keeps blocking the archive host unless a test routes it to a root the test built. `frontend/src/lib/data/ledger.ts` accepts a page-script replacement for the raw-day list, `__RAW_LISTED_THROUGH__`, as it already does for the archive address | L2 | Support | Nothing by itself. After it, no browser test can compute an answer from data | - |
| G8 | Rewrite H9, which takes `siteFrom` from canary data | L2 | End-to-end, `console` | A ledger built to begin 10 days before the pinned day, with the archive off and a 365-day window: the first row is on that day, the sentence names that day, and there is no warning | Reading from the window's first day |
| G9 | A new browser test in `frontend/tests/console-data-explorer.spec.ts`: two built ledgers, with the archive host routed to a root the test built | L2 | End-to-end, `console` | A ledger that began 5 days before the pinned day: the 14-day preset sends no request to the archive host, and the page shows "Days before {that day} are not on this site." A ledger that began 4 years before: the preset reads the 14 days that end on the pinned day, fetches no older file, and shows no such sentence | Asking the archive whenever the window starts before the site's first day; starting the window at the ledger's first day |
| G10 | `frontend/tests/ledger-rows.spec.ts`, a new case on a built site | L5 | Integration, `logic` | A record whose rows stop 40 days before the newest published day: the window ends on that published day, nothing before the window's start is read, and the note names the record's last day | Reaching back for rows; ending on the newest row date |
| G11 | Not used: it belonged to L6, which L9 rejects | - | - | - | - |
| G12 | Not used: Fowler's list of deletions, which are G5, G6, G7 and G17 here | - | - | - | - |
| G13 | The guard for Table D, D2 in G4: a ledger built to begin 1,461 days (4 years) before the pinned day | L1 | Integration, `logic` | A 14-day window is read as selected: the first row is on the window's first day, `siteFrom` is null, and there is no archive request. A 365-day window over the same ledger, trimmed by the real copy rule, asks the archive only for days inside that window | Choosing, widening or moving the window because of a ledger's first day, for example opening it on that day |
| G14 | Rewrite H10, which compares the page with `expectedAsk` and uses the canary date `JOIN_FROM` | L2 | End-to-end, `console` | Two built ledgers with 3 and 2 rows in the window: the join answers 6 rows, the page fetches exactly their built files, and the action line's byte count equals what the network carried | Fetching a file outside the window, or counting one twice |
| G15 | Rewrite H11, which takes `through` from `expectedAskCost` | L2 | End-to-end, `console` | Choosing two built ledgers fetches exactly their two newest-day files | Fetching a second day for the column rail |
| G16 | Rewrite H12, whose answer states depend on five canary ledgers | L2 | End-to-end, `console` | Each answer state comes from a root built for it. The test checks each state's written-out `data-state`, and that the page's pictures of the states all differ | Two states that share words, colour and action |
| G17 | Rewrite H13 as a logic test in `frontend/tests/console-data-explorer-examples.spec.ts` (new), named under `logic`, and delete its browser run | L2 | Unit, `logic` | Every configured example passes `checkStatement` (`frontend/src/lib/data/statement.ts`), names only registered ledgers, and uses a configured preset. Whether an example finds rows is a fact about the data, so no test checks it. Table B, B6 holds its columns | An example with two statements, or one that names an unregistered ledger |
| G18 | Rewrite H14 and H18, whose spans and file paths come from the canary day | L2 | End-to-end, `console` | H14: one built day file, of a size the test wrote, and the held bytes equal that size before and after a refused run. H18: before Run, the only data file fetched is the built newest-day file; after Run, the rows are the built rows | Dropping held files when a run is refused; a link that runs by itself |
| G19 | Rewrite H19 and H20, which pin the canary day. H20 also prints that day in its expected sentence | L2 | End-to-end, `console` | The same notices, on a day each test pins | Changing a notice |
| G20 | Rewrite H21 and H25, which take their lost day from canary data | L2 | End-to-end, `console` | A built ledger with a lost day and 2 set-aside files on written-out days: the two sentences show, no row exists for the lost day, and the chart line breaks there | Drawing the lost day as a zero |
| G21 | Rewrite the tests that use a canary ledger only to carry a question: H6, H17, H22, H23, H26, H28, H30, H31, H34, H37, H39 and H40 | L2 | End-to-end | Each test chooses a built ledger, uses `range()` or `VALUES` where the rows do not matter, and first checks the answer state it needs. Today H26 never checks its states: on `main` three of its four questions end `unreachable` and it still passes (reasoned; it is not among the ten that fail) | Removing the state check |
| G22 | Keep on the canary, each test pinning its own day once G7 lands: H1 to H5, H7, H8, H15, H16, H24, H27, H29, H32, H33, H35, H36 and H38 | L2 | End-to-end, `console` | They do not depend on content: the page renders, the layout holds, and nothing errors. H8 is the check that the presets end today (Table D, D2) | - |
| G23 | Keep the specs `console-data-explorer-address`, `-gaps`, `-keep` and `-shape` (group `logic`) and `console-data-explorer-cells` (group `console`) | - | Unit | Their dates are values the tests wrote themselves | - |

### 2.5 The existing tests, one by one

Table H - tests on `main` at 36fe716e0 that a row rewrites, deletes or keeps, by spec and title, with the line of Table G that decides each one. "Red" marks the ten that fail in run 37361239642.

| # | Spec under `frontend/tests/` | Test title | Table G | Row | Red |
| --- | --- | --- | --- | --- | --- |
| H1 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer opens as the sixth tab and renders its two panels before a run` | G22 | L2 | - |
| H2 | `console-data-explorer.spec.ts` | `THE ORACLE: console chrome resolves to console unless the route asks for workbench` | G22 | L2 | - |
| H3 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer asks for workbench chrome and the other routes keep console chrome` | G22 | L2 | - |
| H4 | `console-data-explorer.spec.ts` | `THE ORACLE: the workbench strip is one compact row at ${view.width}` | G22 | L2 | - |
| H5 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer puts the span and Run in the workbench toolbar` | G22 | L2 | - |
| H6 | `console-data-explorer.spec.ts` | `THE ORACLE: before a run the column rail names the selected ledger's own columns` | G21 | L2 | - |
| H7 | `console-data-explorer.spec.ts` | `THE ORACLE: the Data explorer fallback document carries the shipped content policy` | G22 | L2 | - |
| H8 | `console-data-explorer.spec.ts` | `THE ORACLE: custom date inputs expose reach bounds and presets end today` | G22 | L2 | - |
| H9 | `console-data-explorer.spec.ts` | `THE ORACLE: with no archive prefix, an old custom span reads from the site's oldest day and says so` | G8 | L2 | - |
| H10 | `console-data-explorer.spec.ts` | `THE ORACLE: a typed join matches the query door and the run cost matches the network` | G14 | L2 | Red |
| H11 | `console-data-explorer.spec.ts` | `THE ORACLE: choosing ledgers fetches one through day for each chosen ledger and no other data file` | G15 | L2 | - |
| H12 | `console-data-explorer.spec.ts` | `THE ORACLE: every Data explorer answer state renders distinct words, tint and action` | G16 | L2 | Red |
| H13 | `console-data-explorer.spec.ts` | `THE ORACLE: every published example runs without refusal or unreachable state` | G17 | L2 | Red |
| H14 | `console-data-explorer.spec.ts` | `THE ORACLE: a refused run after a fetch still shows the page-held bytes` | G18 | L2 | - |
| H15 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer does not scroll sideways at phone width` | G22 | L2 | - |
| H16 | `console-data-explorer.spec.ts` | `THE ORACLE: the browser refuses an origin outside connect-src` | G22 | L2 | - |
| H17 | `console-data-explorer.spec.ts` | `THE ORACLE: hostile cell text stays plain in the real table` | G21 | L2 | Red |
| H18 | `console-data-explorer.spec.ts` | `THE ORACLE: a shared address fills the editor and does not run itself` | G18 | L2 | Red |
| H19 | `console-data-explorer.spec.ts` | `THE ORACLE: link notices render on the page` | G19 | L2 | - |
| H20 | `console-data-explorer.spec.ts` | `THE ORACLE: a link naming a day that does not exist shows the span notice, and the page still loads its ledgers` | G19 | L2 | - |
| H21 | `console-data-explorer.spec.ts` | `THE ORACLE: a count by day names the day a ledger lost and the files it set aside, and draws no row for the lost day` | G20 | L2 | - |
| H22 | `console-data-explorer.spec.ts` | `THE ORACLE: every chart case draws its type with a populated readout` | G21 | L2 | Red |
| H23 | `console-data-explorer.spec.ts` | `THE ORACLE: Save, recent runs and Markdown copy preserve text without running a saved question` | G21 | L2 | Red |
| H24 | `console-data-explorer.spec.ts` | `THE ORACLE: browser storage is parsed against closed lists and saved overflow names the drop` | G22 | L2 | - |
| H25 | `console-data-explorer.spec.ts` (added by #1318, not on `main` yet) | `THE ORACLE: a count by day across a lost day breaks its line there, and the strip prints no number for that day` | G20 | L2 | - |
| H26 | `console-data-explorer-still.spec.ts` | `Run moves nothing in answered, capped, quiet and refused states at ${view.width}px` | G21 | L2 | - |
| H27 | `console-data-explorer-still.spec.ts` | `Copy link notice is fixed and moves no region` | G22 | L2 | - |
| H28 | `console-data-explorer-still.spec.ts` | `status text never overlaps the reserved answer link box` | G21 | L2 | - |
| H29 | `console-data-explorer-still.spec.ts` | `M8: every workbench region keeps its idle block size at all four widths` | G22 | L2 | - |
| H30 | `console-data-explorer-still.spec.ts` | `M10: non-run interactions keep every region box fixed` | G21 | L2 | Red |
| H31 | `console-data-explorer-still.spec.ts` | `M11: status words stay in the reserved lines and never scroll sideways` | G21 | L2 | Red |
| H32 | `console-data-explorer-still.spec.ts` | `M12: notices time out, pause on hover or focus, and close on the button` | G22 | L2 | - |
| H33 | `console-data-explorer-still.spec.ts` | `storage notice dismissal does not re-enable storage-backed controls` | G22 | L2 | - |
| H34 | `console-data-explorer-still.spec.ts` | `M13: B2 column rail text flips without changing either rail box` | G21 | L2 | - |
| H35 | `console-data-explorer-still.spec.ts` | `M15: panel ids stay ordered, headed and joined into one workbench surface` | G22 | L2 | - |
| H36 | `console-data-explorer-still.spec.ts` | `M16: phone width has no document overflow and controls stay inside their regions` | G22 | L2 | - |
| H37 | `console-data-explorer-still.spec.ts` | `no workbench control is cut off, idle or after a run, at any width` | G21 | L2 | - |
| H38 | `console-data-explorer-still.spec.ts` | `M17: keyboard order follows the visual order at desktop and phone widths` | G22 | L2 | - |
| H39 | `console-readout.spec.ts`, inside `the readout is the default` | `THE ORACLE: the Data explorer shape panel declares its readout and has no native tooltip` | G21 | L2 | Red |
| H40 | `explorer-boundary.spec.ts`, which reads `tests/fixtures/ledger-door/` | `the browser content policy refuses a statement fetch to an unlisted origin` | G21 | L2 | - |
| H41 | `ledger-door.spec.ts` | `a span that starts before the oldest day any index names is unreachable, and no fault` | G6 | L4 | - |
| H42 | `ledger-door.spec.ts` | `a date both packed and listed is read once, from its packed file` | - | L9 | - |
| H43 | `ledger-door.spec.ts` | `a date in no tier is unreachable at that date, and with no archive the span starts at the site` | G5 | L1 | - |

### 2.6 Gates every row runs

Every row runs what [run-the-gates.md](../docs/how-to/run-the-gates.md) selects for its changed files: `npm --prefix frontend run test:changed -- --list`, then the selected checks, with the expensive gates taken through the lock that page names. Python runs as `.\.venv\Scripts\python.exe`. A row that changes Python runs ruff and mypy. A row that changes TypeScript or Svelte runs `npm --prefix frontend run check`. A row that changes Markdown runs `python backend/utilities/doc_load.py` on each changed page, before and after. A row that changes the published site runs the browser smoke (CLAUDE.md section 12). Each row records the selected inputs and the results in its report. CI runs the full suite once on the merge candidate: a pull request runs what `ciAnswer` in `frontend/scripts/test-scope.ts` selects, and the merge push to `main` runs every group. Each row below names only its focused checks.

## 3. The rows

### Row #L1 - Days before a ledger began are cut from the selected window

- **Scope:** When the window selected in the data explorer starts before the first day that a ledger's tiers name, the answer leaves out that ledger's earlier days and names the first day (Table D, D1). The archive is asked only for days the site copy trimmed, and nothing reads a ledger's first day to choose, widen, move or end a window (Table D, D2). Level 3.
- **Files touched** (Fowler's list, each path checked on `main` at 36fe716e0; the last one was found by search):
  - `frontend/tests/support/ledger-lifecycle.ts` (new: Table G, G1)
  - `frontend/tests/ledger-lifecycle.spec.ts` (new: the explorer cases of Table G, G4 and G13)
  - `frontend/scripts/test-groups.ts` (names the new spec under `logic`)
  - `frontend/src/lib/data/site-window.ts` (new: the site copy's trim rule, moved)
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/ledger.ts`
  - `frontend/vite.config.ts` (`__SITE_WINDOW_DAYS__`)
  - `frontend/src/app.d.ts` (declares `__SITE_WINDOW_DAYS__`)
  - `frontend/tests/explorer-boundary.spec.ts` (its own page build sets the build constants)
  - `frontend/tests/ledger-door.spec.ts` (Table G, G5)
  - `frontend/tests/ledger-copy.spec.ts`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md` (its "Archive tier" section)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/how-to/query-a-ledger-from-the-console.md` (says when the explorer reads the archive; not in Fowler's list)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-lifecycle.spec.ts --spec ledger-copy.spec.ts --spec ledger-door.spec.ts --spec explorer-boundary.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the three pages; the browser smoke of the data explorer. CI: what `ciAnswer` selects for the pull request, then every group on the merge push to `main`. A named observation, not a gate: on that merge push, the ten tests marked "Red" in Table H pass. That is reasoned and not run: the canary's ledgers are younger than the site window, so the page never asks the archive, and it cuts on the same day as today's answer key. If they stay red, the fix is L2, never a change to the canary (Table D, D3).
- **Oracle:** in `ledger-lifecycle.spec.ts`, on roots the test builds, with days counted from its pinned day. A ledger built to begin 5 days ago answers a 14-day window from its first day, names that day, and makes no archive request. A ledger built to begin 4 years ago answers the 14 days that end on the pinned day, and fetches nothing older (Table G, G4 and G13). It cannot settle the live archive path, because no published ledger is trimmed yet (Fowler, 2026-10-05); until one is, trimmed days are checked only on built roots.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three commits, one hat each: (1) test support: the builder (Table G, G1) and the explorer cases of G4 and G13; (2) structural, Extract Function: the site copy's trim rule moves to `frontend/src/lib/data/site-window.ts`, and the copy calls it there; (3) behavioural: cut the days before the first day that every tier names, ask the archive only when the site trimmed days, and delete the test of G5 | Fowler, 2026-10-05 |
| 2 | The explorer asks the archive only when the site's first day is on or before its trim line. It works that out with the site copy's own rule, through `site-window.ts` and one build constant, `__SITE_WINDOW_DAYS__`, and never with a second copy of the arithmetic (Fowler's option F2) | Fowler, 2026-10-05 |
| 3 | A day before every tier's first day is outside the ledger, so the answer is cut and is never `unreachable`. `unreachable` stays for a hole after the first day, an absent named file, an absent coarser index, a file that did not arrive whole, and an engine that did not start | Fowler, 2026-10-05 |
| 4 | No persisted shape changes. The readers work out "trimmed" from the indexes and the copy's rule; Table B, B1 prices the field that would record it (Fowler's option C1) | Fowler, 2026-10-05 |
| 5 | The plan 60 owner carried L1 under plan 60's row "Which days may be packed" ([plan 60](20261004-60-gardener-recovers-on-its-own-plan.md)), as that row's "Fixed after merge" follow-up. It merged as #1327 before this plan-doc reached `main`, so this plan-doc's own pull request stamped this line DONE, and the work is counted once | The owner, 2026-10-05 (Table D, D4) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep refusing a window that starts before a ledger's first day, and change only the test data | The owner ruled that the answer cuts and says so (Table D, D1) | Every explorer question that starts before a ledger's first day stays a fault on the live site. On 2026-10-05 that was every 90-day question (Fowler) | The owner, 2026-10-05 |
| 2 | Ask the archive whenever the window starts before the site's first day, then cut at the archive's first day (Fowler's option F1) | It sends requests that the answer does not need, and the ten red tests stay red until the harness serves an archive | Three cross-origin requests a ledger for every such question, which for a ledger younger than the site window is every question that reaches its start | Fowler, 2026-10-05 |
| 3 | Drop the archive tier, and always cut at the site's first day (Fowler's option F4) | The explorer would lose every day older than the site window, while `console.explorer_reach_days` in `config/appearance.json` promises more | The simplest reader, with no network; no history before the site window | Fowler, 2026-10-05 |
| 4 | Merge the pushed canary fix, branch `plan-60-row-13-canary-fix` at commit bf274b8 (Fowler's option N1). It filed a real row on 2026-08-01 into five canary ledgers, so that each canary index names every day from 2026-08-01 to 2026-08-20, and it pinned that shape with a backend test | It changes the canary only so that tests that read its content pass (Table D, D3), and L2 would delete it. It was never merged, and its branch was deleted from the remote on 2026-10-05 (Fowler's option N2) | `main` green soonest (estimate, not run). Then a builder change and a backend test that L2 deletes, and until L2 the ten tests keep depending on what the canary holds | Fowler, 2026-10-05 |
| 5 | Land L1 and L2 as one pull request (Fowler's option N3) | The largest pull request, and `main` stays red longest | The end state in one step, with no small reversible step between | Fowler, 2026-10-05 |

### Row #L2 - Explorer browser tests serve the data they check

- **Scope:** Every data explorer browser test serves a root it built, pins its own day, and checks written-out results. The answer key that runs the query door again goes, and the canary keeps only the checks that do not depend on what it holds (Table G, G7 to G9 and G14 to G21; G22 and G23 stay as they are). Level 2.
- **Files touched** (from a search at 36fe716e0 for `EXPLORER_CANARY_DAY`, `expectedAsk`, `expectedAskCost` and `openExplorer`; search again at dispatch, after #1318 merges):
  - `frontend/tests/support/explorer-answer.ts`
  - `frontend/tests/support/browser.ts`
  - `frontend/tests/support/ledger-lifecycle.ts` (added by L1)
  - `frontend/src/lib/data/ledger.ts`
  - `frontend/tests/console-data-explorer.spec.ts`
  - `frontend/tests/console-data-explorer-still.spec.ts`
  - `frontend/tests/console-readout.spec.ts`
  - `frontend/tests/explorer-boundary.spec.ts`
  - `frontend/tests/panel-captures.spec.ts` (calls `openExplorer`, whose argument changes; not in Fowler's list)
  - `frontend/tests/console-data-explorer-examples.spec.ts` (new: Table G, G17)
  - `frontend/scripts/test-groups.ts` (names the new spec under `logic`)
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the groups it selects; the changed specs fall in `console`, `panels`, `publishing` and `logic`. Then `npm --prefix frontend run check`, and `doc_load.py` on the two pages. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push to `main`.
- **Oracle:** a canary-day move (Table E, E10) over every spec that Table H names for this row. On the branch every one of them stays green. On the base commit the same move turns red the tests that read the canary, which is what lets this check fail. It cannot settle whether the explorer answers correctly over real published data, which no browser test reads.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each test serves a root it built (Table G, G1), pins its own day, and checks written-out outcomes: the files fetched, the sentence shown, the archive requests and the rows (Fowler's option J1) | Fowler, 2026-10-05 |
| 2 | The page-script replacement for the raw-day list (Table G, G7) lands in the first commit, before any spec serves a built root. `__RAW_LISTED_THROUGH__` is fixed in the bundle with no switch at run time, unlike `__ARCHIVE_BASE_URL__`, and it carries the canary's own list of writer files. So until the replacement lands, a built index whose newest day is not after the canary's listed day still has its columns described from canary files | Found while #1318 was built; relayed by the plan 60 owner, 2026-10-05 |
| 3 | Every root that a test asks a question of holds at least one `packed` day, served with a real Parquet file whose index entry's `bytes` is the file's length. A span with no readable file never runs its question, and the page answers `quiet` | Found while #1318 was built; relayed by the plan 60 owner, 2026-10-05 |
| 4 | H25 sets the span before it chooses the ledger, because before L1 a default span that starts before the first day of the test's index makes the page reach for the archive. After L1 an untrimmed ledger never asks the archive, so the rewrite (Table G, G20) need not keep that order | Found while #1318 was built; relayed by the plan 60 owner, 2026-10-05 |
| 5 | L2 waits for plan 60's row "The explorer's date chart breaks its line at a lost day" (#1318), because both edit `console-data-explorer.spec.ts` and L2 rewrites the test that row adds. The Depends-on cell names that row by number so that the plan reader holds L2; check its title again at dispatch. Any other test #1318 adds is read against Table D, D3 then, and gets a line in Table H | Plan author, 2026-10-05 |
| 6 | G17 keeps no browser run, because whether a published example finds rows is a fact about the data (Table D, D3) | Fowler, 2026-10-05 |
| 7 | Level 2: tests and test support, plus one page-script hook in `ledger.ts` that the shipped page never sets | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Switch the archive off in the explorer specs, with `__ARCHIVE_BASE_URL__` set to an empty string (Fowler's option J2) | The tests still read the canary's content, and they test a configuration that production does not ship | A small edit, and specs that fail again whenever the canary's content moves | Fowler, 2026-10-05 |
| 2 | Keep today's answer key, and rely on L1's trim check (Fowler's option J3) | The key computes answers from data (Table D, D3) | No test edit. The page and the key agree only while the canary stays untrimmed and every span ends before its unpacked day: the coupling that turned `main` red on 2026-10-05 | Fowler, 2026-10-05 |
| 3 | An answer key that reads the page's own inputs over the canary: the archive host routed to the canary's state root, the build's raw listings and the site window (Fowler's option J4, his first proposal) | It still compares the page with an answer computed from data (Table D, D3) | One routing rule and one helper; the page and the key agree by construction | Fowler, 2026-10-05 |

### Row #L3 - Lifecycle states at the producers

- **Scope:** The real compaction is tested wake by wake, on raw files that each test writes and a declaration that each test builds, for the producer states of Table F. The site copy is tested on state trees the test writes, against written-out kept entries, and the states get a page of their own. Level 1.
- **Files touched:**
  - `backend/tests/gardener/tasks/test_compaction_lifecycle.py` (new: Table G, G2)
  - `backend/tests/gardener/tasks/_task.py`
  - `frontend/tests/ledger-copy.spec.ts` (Table G, G3)
  - `docs/architecture/contracts/ledger-lifecycle.md` (new)
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/persistence.md`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/tasks/test_compaction_lifecycle.py backend/tests/gardener/tasks/test_compaction.py`; ruff; mypy; `npm --prefix frontend run test:changed -- --spec ledger-copy.spec.ts`; `doc_load.py` on the three pages. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** G2's "begins mid-month" test passes on the branch. With #1309's start rule reverted in a scratch copy, so that a first run fills from the 1st of its month, the same test fails. It cannot settle a real paused or retired ledger, because no family and no task is paused or retired today.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each backend test builds its own declaration (`compact_after_days`, `max_periods_per_run`, `daily_keep_days`), so a config edit cannot move its expected values | Fowler, 2026-10-05 |
| 2 | The new module carries `pytestmark = pytest.mark.contract`, as `test_compaction.py` does | Plan author, 2026-10-05 |
| 3 | The new page names each state of Table F and what the indexes record for it, and links to the two door pages for what a reader answers. L1, L4, L5, L7 and L8 each change the door page that their change makes untrue | Plan author, 2026-10-05 |
| 4 | Level 1: tests and documentation only | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Take the expected values from a committed declaration under `config/gardener/` | A config edit would move a test's expected values (Table D, D3) | Fewer lines in each test, and tests that go red when an operator changes a knob | Fowler, 2026-10-05 |
| 2 | Check the site copy against the shared trim rule | One function's output would be the other's expected answer (Table D, D3) | Fewer written-out values, and a change that moves both together passes | Fowler, 2026-10-05 |
| 3 | A scenario file that both the backend and the frontend tests read (Fowler's option K4) | Each side already checks written-out values of what it built | One file that both suites depend on, and it catches changes to lifecycle shapes only | Fowler, 2026-10-05 |

### Row #L4 - A slice cuts only the days before a ledger began

- **Scope:** A panel slice whose span starts before a ledger's first day answers from that day, names it, and ends where it was asked to end. `unreachable` stays for faults, how far a ledger is packed (`through`) comes from all three indexes, and the two callers' clamps go. Level 2.
- **Files touched** (from a search at 36fe716e0 for `readSlice(`, `sliceFromDisk(`, `reach.first` and "Clamp the span"):
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/ledger-reach.ts`
  - `frontend/src/lib/data/slice-shapes.ts` (`SliceResult` gains `first` on `ok` and `quiet`)
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (its clamp goes)
  - `frontend/src/lib/server/ledger-rows.ts` (its clamp goes)
  - `frontend/src/lib/data/slice.ts` (found during execution: `firstNamed()` said `daily.json` names at least one day, which stops being true once the door reads the other two indexes when it names none)
  - `frontend/tests/support/ledger-lifecycle.ts` (found during execution: a slice keeps rows by their `date` cell, and the builder wrote none, so no slice over a built root could return a row; the owner ruled the one-line fix, 2026-10-06, and L2 carries the same line)
  - `frontend/tests/ledger-lifecycle.spec.ts` (added by L1: the slice and reach cases of Table G, G4)
  - `frontend/tests/ledger-door.spec.ts` (Table G, G6, and every case that compares a whole `ok` or `quiet` slice with `toEqual`; found during execution: five more cases asserted the old answer for a span that starts before the first day, or for a `daily.json` that names no day while `monthly.json` names a month)
  - `frontend/tests/ledger-rows.spec.ts` (found during execution: a comment said the door answers a day before the first packed day as a hole)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-lifecycle.spec.ts --spec ledger-door.spec.ts --spec ledger-rows.spec.ts --spec platform-mix.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the panel page; the browser smoke of the console's machine page, whose platform panel reads a slice. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** in `ledger-lifecycle.spec.ts`, a ledger built to begin 5 days before the end of a 14-day slice. The answer covers those 5 days, names the first of them, and ends where it was asked to end (Table G, G4). It cannot settle how a panel draws the days before a record began; the panels' own specs and L5 own that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Both doors cut and name the first day they answered from, and `unreachable` stays for faults and failed reads (Fowler's option G2). `first` is the first day the answer covers: the span's own first day, or the ledger's first day when the span starts before it. It is a value the door returns at run time, not a persisted shape | Fowler, 2026-10-05 |
| 2 | When `daily.json` names nothing, the reader reads the other two indexes, and `through` is the newest day any index names, as the site copy and the gardener's daily mark already take it | Fowler, 2026-10-05 |
| 3 | The cut leaves out only the days before the ledger began. The span the caller asked for, and its end, stay as asked (Table D, D1 and D2) | The owner, 2026-10-05 |
| 4 | Level 2: the slice's answer changes, and two callers depend on it | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep today's split: the explorer cuts, the panel slice answers `unreachable`, and each caller clamps (Fowler's option G1) | Two answers for one fact, and a new panel that forgets to clamp shows a fault for a young ledger | No change to the slice | Fowler, 2026-10-05 |
| 2 | Refuse a span that starts before the first day as a request error (Fowler's option G3) | A normal state becomes an error | Every caller reads the reach before it asks | Fowler, 2026-10-05 |

### Row #L5 - Console windows end on the site's newest published day

- **Scope:** Every console panel window ends on the site's newest published day (Table D, D5), reads exactly that window, and never reaches back for rows. A record whose rows stop before the window's start says that it has no rows after its last day. The data explorer is unchanged (Table D, D2). Level 3.
- **Files touched** (from a search at 36fe716e0 for `windowOfDays`, `newestRows`, `latestDate(` and the `today` that each console route computes; search again at dispatch):
  - `frontend/src/lib/charts/viewport.ts`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/judgement/+page.server.ts` (computes `today` and hands it to its page; not in Fowler's list)
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/routes/console/model/+page.server.ts`
  - `frontend/src/routes/console/voices/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/model/+page.svelte`
  - `frontend/src/routes/console/voices/+page.svelte`
  - `frontend/src/lib/server/ledger-rows.ts`
  - `frontend/src/lib/server/host-fingerprint.ts` (calls `newestRows`; not in Fowler's list)
  - `frontend/src/lib/data/slice.ts`
  - `frontend/src/lib/data/ledger-reach.ts`
  - `frontend/src/lib/console/recording.ts`
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte`
  - `backend/idhazh/contracts/knobs/console.py` (the `today_anchor` description)
  - `frontend/tests/ledger-rows.spec.ts` (Table G, G10)
  - `frontend/tests/ledger-lifecycle.spec.ts` (added by L1: the window cases of Table G, G4)
  - `frontend/tests/console-window.spec.ts` (pins that `windowOfDays` ends on the newest date it is handed; not in Fowler's list)
  - `frontend/tests/console.spec.ts` (calls `windowOfDays`; not in Fowler's list)
  - each console spec that assumes a window ends on a record's own last day. Nobody has counted them: run the console group on the L5 branch, and add each failing spec here before editing it
  - `frontend/src/lib/server/payload.ts` (found at dispatch by the owner: `feedResults` takes the window; `latestDate()` is unchanged)
  - `frontend/src/lib/server/window-day.ts` (new; found during execution: the one place the day every console window ends on is read, `latestDate()` or the build's UTC day)
  - `frontend/src/lib/console/RecordNotes.svelte` (found during execution: the quietest line for the day packing has not reached, decision 4)
  - `frontend/src/routes/console/machine/+page.svelte` (found during execution: picks the open window's notes)
  - `frontend/src/lib/server/ledger-disk.ts`, `frontend/src/lib/feed-health.ts` (found during execution: comments that said a reader anchors on the newest packed day)
  - `frontend/src/lib/server/machine-counters.ts` (found during execution: `hostRows` and `loadMachineCounters` take the window)
  - `frontend/src/lib/server/model-work.ts` (found during execution: `sourceCuts` ended its window on its own newest row; it takes the route's window)
  - `frontend/tests/ledger-door.spec.ts` (found during execution: the reach's `ok` answer names `lastRows`)
  - `frontend/tests/support/canary-records.ts`, `frontend/tests/console-machine-data.spec.ts`, `frontend/tests/console-voices-feeds.spec.ts` (found during execution: `-1`, every packed day, is gone; they read the window the console's server reads over the canary, which holds the same days. They still read canary content: L9's inventory keeps them)
  - `frontend/tests/console-voices-sources.spec.ts`, `frontend/tests/one-pass-reductions.spec.ts` (found during execution: `sourceCuts` takes a written-out window; the golden output is unchanged)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`
  - `docs/concepts/config/appearance.md`
  - `docs/architecture/publishing/console-payloads.md`, `docs/concepts/growing-reads.md`, `docs/architecture/publishing/what-sits-above-every-console-route.md`, `docs/architecture/publishing/console-truncation.md`, `docs/architecture/publishing/what-the-pipelines-route-draws.md`, `docs/architecture/publishing/console-machine.md`, `docs/architecture/sources/health.md`, `docs/concepts/console-design/how-the-machines-work-is-drawn-and-what-may-not-be-pooled.md`, `docs/architecture/publishing/telemetry-series.md` (found during execution: each said a window or a read ends on the newest day a ledger holds)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-rows.spec.ts --spec ledger-lifecycle.spec.ts --spec console-window.spec.ts --spec console.spec.ts`, then `--group console`; `npm --prefix frontend run check`; ruff, mypy and the backend tests that `test:changed -- --list` selects for `console.py`; `doc_load.py` on the three pages; the browser smoke of the console's home, judgement, machine, model and voices routes. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `ledger-rows.spec.ts`, on a site the test builds, a record whose rows stop 40 days before the newest published day. The window ends on that published day, nothing before the window's start is read, and the note names the record's last day (Table G, G10). It cannot settle how the days that packing has not reached look at a panel's right edge; Jony and Susan rule on that (decision 4).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every console window ends on the site's newest published day, `latestDate()`, which `recordNotes` already uses to measure how far a record is behind (Fowler's option M3) | The owner, 2026-10-05 |
| 2 | `windowOfDays` places its anchor on the day that the route gives it, which is `latestDate()`, instead of on the newest date in its rows. With `today_anchor` at `right`, that day is the window's last. The build clock no longer places a window | Fowler, 2026-10-05 |
| 3 | `newestRows` reads exactly the window and never reaches back. `PlatformMixPanel` uses the route's window instead of its record's own last packed day | Fowler, 2026-10-05 |
| 4 | Reader and Jony choose the words of the note for a record whose rows stop before the window. Jony and Susan rule how the days that packing has not reached look at a panel's right edge. The worker asks them when the row is dispatched (CLAUDE.md section 14) | Fowler, 2026-10-05 |
| 5 | The `today_anchor` description in `console.py` names the day it means | Fowler, 2026-10-05 |
| 6 | The note's last day comes from the indexes, because nothing before the window is read: the newest daily entry that holds rows, or that month or year when the newest entry that holds rows is a month or a year | Plan author, 2026-10-05, from the Oracle's rule |
| 7 | When no day is published, `latestDate()` is null, and the window ends on the build's UTC day, as `windowOfDays` does today when it is handed no date. There is nothing to draw either way, and the page still renders (CLAUDE.md section 12) | Plan author, 2026-10-05 |
| 8 | Level 3: it changes how every console route places its window | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | End every console window on the build's UTC day (Fowler's option M4) | The owner chose decision 1, which gives the same windows for every build of the same data | A build that runs before the day's digest ends every window on a day with nothing published. The canary build must pin its clock to the fixture's day, or every console panel draws an empty window | The owner, 2026-10-05 |
| 2 | End a stopped record's window on its newest rows, as L5 was first proposed (Fowler's option M1) | The record would move the window into the past (Table D, D2) | A stopped record's last rows stay on screen | The owner, 2026-10-05 |
| 3 | Drop L5 and keep today's code (Fowler's option M2) | Every window still ends on the newest date in its own rows. A record that stopped longer ago than the window shows nothing and gives no reason | Nothing to build | The owner, 2026-10-05 |
| 4 | End every window on the newest day that packing can have reached: the newest published day minus the packing delay (Fowler's option M5) | It is not the current day, and the delay differs by ledger (`compact_after_days`) | No days without a value at the right edge in the normal case | The owner, 2026-10-05 |
| 5 | Remove only the reach-back in `newestRows` | Each route would still end on the newest row date, and the days that the read no longer covers would be drawn as empty (reasoned) | A smaller edit that makes the page worse | Fowler, 2026-10-05 |

### Row #L7 - A published ledger that has not started

- **Scope:** A published ledger with no compact folder of its own stages nothing and writes one line to the build log, so the site still deploys, and the door answers it as Table F, F1 says. A ledger with some but not all of its three indexes still stops the build. Level 2.
- **Files touched:**
  - `frontend/scripts/published-ledgers.mjs`
  - `frontend/tests/ledger-copy.spec.ts`
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-copy.spec.ts --spec published-ledgers.spec.ts`; `doc_load.py` on the panel page. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** in `ledger-copy.spec.ts`, on state trees the test writes, against what `ledgerCopy` returns. A published ledger with no compact folder adds no file and no refusal, and one entry to `logs` that names it. A ledger with only `daily.json` still adds one entry to `refused` for each missing index, which stops the build. It cannot settle a compact folder deleted by accident, which now reads as a ledger that has not started instead of stopping the deploy; rejected alternative 1 prices that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A ledger with no compact folder stages nothing and writes one build-log line. The check is one `existsSync` on a named path (Fowler's option D2) | Fowler, 2026-10-05 |
| 2 | A ledger with some of its indexes but not all three still stops the build | Fowler, 2026-10-05 |
| 3 | Level 2: the site build's refusal changes, and every deploy depends on it | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: the build stops for a published ledger with no compact folder (Fowler's option D1) | A ledger's start is a normal state, and this makes it stop every page from deploying | Every page stops deploying whenever a ledger joins `ledger.published` before its first packed day, for at least two days (estimate: `compact_after_days` is 1, plus the next daily wake). In return, a compact folder deleted by accident stops the build | Fowler, 2026-10-05 |
| 2 | The copy writes three empty indexes (Fowler's option D3) | The site would claim a packing that never ran | The door answers `quiet` instead of `missing`, and the published indexes stop being the committed list | Fowler, 2026-10-05 |

### Row #L8 - The archive's failures are named as the archive's

- **Scope:** When the archive does not answer for trimmed days, the explorer answers the site's days and says that the older days are in the archive, which did not answer. A 404 on the archive's index is no longer worded as "not on this site yet". Level 2.
- **Files touched:**
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/console/waiting.ts`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/tests/support/ledger-lifecycle.ts` (added by L1)
  - `frontend/tests/ledger-lifecycle.spec.ts` (added by L1: the archive failure case of Table G, G4)
  - `frontend/tests/console-data-explorer.spec.ts`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-lifecycle.spec.ts --spec console-data-explorer.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the data explorer. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** a ledger the test built and trimmed, with the archive host left blocked, answers its site days and names the archive. This holds in `ledger-lifecycle.spec.ts`, and in one browser case that serves that root while `frontend/tests/support/browser.ts` blocks the archive host. It cannot settle an archive that answers slowly; the door's whole-file check already covers a file that arrives cut short.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Answer the site's days, and say that the older days are in the archive, which did not answer (Fowler's option H3): degrade, do not fail (CLAUDE.md section 1a) | Fowler, 2026-10-05 |
| 2 | The answer carries which tier did not answer, as a field of the run-time answer in `slice-shapes.ts`. It is not a persisted shape | Fowler, 2026-10-05 |
| 3 | Reader and Jony choose the sentence's words. The worker asks them when the row is dispatched (Table B, B4) | Fowler, 2026-10-05 |
| 4 | Level 2: the explorer's answer changes for one tier | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: `unreachable` in the site's words, or `missing` for a 404 (Fowler's option H1) | The page blames the site for the archive's fault | Nothing to build, and a sentence that is false | Fowler, 2026-10-05 |
| 2 | `unreachable`, named as the archive's fault (Fowler's option H2) | It throws away the site's days, which were readable | True words, and no answer at all while the archive is down | Fowler, 2026-10-05 |

### Row #L9 - Console specs outside the explorer serve the data they check

- **Scope:** Every console spec outside the explorer that reads canary content, and every console reader test that computes its expected answer from a fixture, serves a root it built and checks written-out values. The row starts with an inventory taken when it is dispatched. Level 2.
- **Inventory**, the row's first step, before any edit:
  1. A canary-day move (Table E, E10) over the `console` and `panels` groups. Every spec with a test that turns red, other than the explorer specs of Table H, joins the inventory.
  2. A reading of each `logic` spec whose name starts with `console-` or `ledger-`, for a test that computes its expected value by running a reader over the canary or a committed fixture, or that copies a fixture made for other questions. Each one joins the inventory. Two are known now (Files touched).
  3. The change that starts the row writes every spec that joined into Files touched, with each test's title and the step that found it.
- **Files touched** (known now; the inventory adds the rest):
  - `frontend/tests/ledger-door.spec.ts` (Table H, H42 takes its expected row count from the door fixture's own index)
  - `frontend/tests/ledger-rows.spec.ts` (copies `tests/fixtures/ledger-door/`, a fixture made for door questions, to build its data)
- **Acceptance gates:** local: the inventory's canary-day move, repeated on the branch; `npm --prefix frontend run test:changed -- --list`, then the groups it selects; `npm --prefix frontend run check`. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** the inventory's canary-day move, repeated on the branch, turns no spec in the inventory red. Each rewritten test that took its answer from a fixture now goes red when one value in the root it builds changes. It cannot settle a spec added after the inventory; review asks Table D, D3 of each new test.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No change to the CI test selector (Fowler's option K1). Once the console specs serve the data they check, a producer change cannot turn a console spec red after the merge, and the producer's own lifecycle tests (Table G, G2) run in the backend suite on its pull request | Fowler, 2026-10-05; the owner approved the phase list without L6 (Table D, D4) |
| 2 | A spec joins the inventory only by the two tests of its first step, never by a guess from its name | Plan author, 2026-10-05 |
| 3 | When the inventory is longer than one pull request should carry, the owner fans the row out by file inside one checkout ([execute-a-plan.md](../docs/how-to/execute-a-plan.md#parallel-fan-out)) | Plan author, 2026-10-05 |
| 4 | Level 2: tests only, which every later change depends on | Plan author, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | L6: a named list of canary producers buys the console test group on each pull request that touches one, with a test that each listed path exists, in `frontend/scripts/test-scope.ts`, `frontend/scripts/tests/test-scope.test.mjs` and `docs/how-to/run-the-gates.md` (Fowler's option K2) | A stop-gap spent on tests that Table D, D3 says must change, which would need a removal condition. This row removes its reason | Up to about 10 CI minutes on each such pull request (estimate: the browser job of run 37361239642 ran its tests in 9.9 minutes), and a list of producer paths to keep in step with the code | Fowler, 2026-10-05; the owner approved the phase list without it (Table D, D4) |
| 2 | Run the console group on every pull request (Fowler's option K3) | Every pull request pays for tests that only a producer change needs | About 10 CI minutes on every pull request, by the same estimate | Fowler, 2026-10-05 |
