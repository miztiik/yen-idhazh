# Plan 62 - Ledgers that start, pause, resume and stop

**Last Updated**: 2026-10-07

**Level**: 3 (CLAUDE.md section 6). L1 and L5 cross a boundary: L1 joins the site build to the data explorer, and L5 changes how every console route places its window. No row changes a persisted shape, and Table C, C1 stops any row that would.

**Status**: written 2026-10-05 from Fowler's proposal and his revision of the same day, and from the owner's rulings on them (Table D). Checked against `main` at 36fe716e0. L1 merged under plan 60 as #1327 (row L1, decision 5). The owner ruled that the plan 60 owner session runs this plan after L1 merges (Table D, D4). An id such as "Fowler's option M3" names a row of those two documents, which are not in the repository.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Ledgers start, pause, resume and stop. Since #1309 a ledger's index starts on its first raw day, but the readers treat a day before a ledger began as a day that is missing: the data explorer asks the archive for it and then reports a fault. The tests hid this until #1309, because the canary began every ledger on the 1st of a month and the browser answer key read other inputs than the page. Now ten browser tests fail on `main` (run 37361239642, 2026-10-05). This plan makes every reader and every test treat each stage of a ledger's life as normal |
| A2 | Hard scope - in | - The data explorer leaves out a ledger's days before its first day and names that day, and it asks the archive only for days the site copy trimmed (L1).<br>- Every data explorer browser test serves data it built and checks written-out results. The canary keeps only the checks that do not depend on what it holds (L2).<br>- The real compaction is tested on each lifecycle state, and the states get a page of their own (L3).<br>- A panel slice leaves out the days before a ledger began and names its first day. How far a ledger is packed comes from all three indexes (L4).<br>- Every console window ends on the site's newest published day, reads exactly that window, and says when a record's rows stop (L5).<br>- A published ledger that has no compact folder yet does not stop the site build (L7).<br>- When the archive does not answer for trimmed days, the explorer answers the site's days and names the archive (L8).<br>- Console specs outside the explorer that read canary content serve the data they check (L9).<br>- When a chosen ledger's newest named day holds no rows, the data explorer's column rail still lists its columns (L10).<br>- The "Measurement is off" line names no day outside the window, and says that nothing has been recorded at all only for a record that never held a row (L11).<br>- The data explorer's span sentences count the days read, give every date its year, and name each ledger with its own first day (L12).<br>- The console specs that still work their answer out from the canary, or write out its figures, serve the data they check (L13)<br>- The console specs that work their answer out from the canary's own files, or skip on what it holds, serve the data they check (L14)<br>- The note under the item-cost section says the held part of a prompt hardly changes only when its own two figures show it (L15)<br>- On Hardware and Summaries, the "Recording started" line names a start only where it is known and on screen, Summaries works out its recording lines for each window, and its "Measurement is off" line prints whenever measurement is off (L16)<br>- Every windowed console surface says "1 day" at the 1-day preset (L17)<br>- The console home opens each published day's payload once, and the articles card takes its count from that read (L18)<br>- The swap chart's case in the console's mark-parity test checks a swap the test builds, instead of skipping because the canary holds no model change (L19)<br>- The dwell rule on the retiring strip starts at the oldest day under the mark in the run, so a day that decided nothing inside the run leaves no such day out (L20)<br>- Before a run, the data explorer's action line counts the days the run will read, not the days of the window (L21)<br>- On Summaries and Hardware, the lines for a day that only one record answered say only what is true of the days the window shows (L22)<br>- The pipelines route's page names the Hardware panel as it is drawn now and says the share is printed, and the prompt-cache subtitle says nothing its own figures contradict (L23) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Change the readers and the tests, never the data: no persisted shape changes, a day before a ledger began is outside the ledger and never a fault, every window ends on a day that no ledger can move, and every test serves the data it checks. Fowler, 2026-10-05, on the owner's rulings of the same day |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows that share a file run one at a time, computed from their Files touched lists. L5 and L9 never run at the same time, because each finds part of its list of console specs only when it is dispatched. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table B - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | A field on the compact index, written by the site copy, that says where the copy trimmed: `trimmed_before` (Fowler's C2) | The explorer works out whether the site trimmed a ledger from the copy's own rule, shared through `frontend/src/lib/data/site-window.ts` (new in L1), and one build constant. That holds while the rule is "a window of days that ends on the newest named day", and while a committed index names every day after its first entry, which is true by construction since #1309 | A trim rule of another kind, for example a cap by bytes. Then a Level 5 change in two commits, reader first (CLAUDE.md section 11): an optional date `trimmed_before` on `CompactIndex` in `backend/idhazh/contracts/ledger_index.py`, with a new version and changelog line; the frontend copy in `frontend/src/lib/data/compact-index.ts`, with its guard and `COMPACT_INDEX_STAMP`; and the field set in `backend/tests/contracts/test_frontend_index_shapes.py` |
| B2 | A field on the compact index, written by the gardener, that names a ledger's first recorded day: `begins` (Fowler's C3) | After a ledger's first month closes, its month entry starts on the 1st. So the days of that month before the ledger began read as quiet days instead of being cut. Since L16 the console prints "Recording started" only where a route's read reaches back to the record's oldest named day, and takes the day it names from rows (`frontend/src/lib/console/recording.ts`). So when the widest window starts inside a record's closed first month, after its 1st, no window prints a started line: the page says nothing, and never a false date. A day before a ledger began and a day dropped by retention also read the same. Retention keeps 14 months of the machine record and every score row, more than the widest window, so no answer needs to tell them apart | A surface that must name a ledger's exact first day after its first month closes. Then a Level 5 change on the gardener's own index. Plan 60's row "The marks are worked out from the indexes, and the watermark files go" could not rebuild the field from named paths without a read that grows (Guardrail #12) |
| B3 | A pause mark and a stop mark on each period (Fowler's C4) | A paused writer, a stopped writer and a quiet stretch all read as `empty` days. The family's `lifecycle_status` in `config/ledgers.json` says only what is true now, with no date | Writers that record "ran and wrote nothing" apart from "did not run": a new writer record, Level 5 |
| B4 | Choosing the words of three sentences that Reader and Jony own (Fowler's E5, E9 and H3): the explorer's answer for a ledger that has never held a row, joined with one that has rows; the `behind` note for the days a stopped packing has not reached; and the sentence for trimmed days that the archive did not answer | The first two keep today's words. The first says that the ledger is not on this site yet, which is false for a ledger that is packed but has never held a row. L8 cannot finish without the third | Reader and Jony rule (CLAUDE.md section 14). L8 asks them for the third when it is dispatched, and L5 takes the second if they rule first. The first needs a Level 1 row of its own after their ruling |
| B5 | Showing a family's `paused` or `retired` status on a console surface | An operator sees no sign of it. The explorer already parses the status (`frontend/src/lib/console/explorer/registry.ts`) and shows nothing from it. No family is paused or retired today | Reader and Jony rule whether and where it shows; then a Level 1 row |
| B6 | A test that each published explorer example names only columns its ledger has | No test catches an example that names a column its ledger lacks; it fails when an operator runs it. Table G, G17 checks the statement, the ledgers and the preset only | A contract-tier row that reads each example's columns against its ledger's row contract (CLAUDE.md section 13) |
| B7 | Specs outside the console that compute their answer from data, such as `frontend/tests/ledger-ranges.spec.ts`, which takes its expected slice from the disk reader | They break Table D, D3 until a row rewrites them, and a producer change can still turn one red after a merge | L9's inventory, run over the `reader`, `archive`, `publishing` and `model-search` groups, as a row of its own |
| B8 | Panels that mark the days packing has not reached. Susan and Jony accept a hairline outline on bar and strip panels. Two points are open: whether a panel whose whole window is not packed shows one line ("6 Oct 2026 is not packed yet.") or nothing, and whether line-chart readouts say "not packed yet" | On bar and strip panels those days look like quiet days, and only the route's note says otherwise: the `behind` note, or the quietest line when packing is one day short. The design rationale of `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` records the gap | An owner decision on the two open points, then a Level 1 row with Susan's, Jony's and Reader's rulings (row L5's report) |
| B9 | Naming a hole in the archive's indexes as the archive's (since L8 the explorer calls the archive the repository) | The hole stays `day-missing`, and the page says "No file on this site holds {ledger} for {day}.", which blames the site | A Level 2 row that puts the tier on the `unreachable` answer in `frontend/src/lib/data/slice-shapes.ts`. That is a field of the run-time answer, not a persisted shape, so Table C, C1 does not fire (row L8's report) |
| B10 | Listing the columns of a published ledger that has no file on the site: `candidate-models` once its September 2026 month packs as `empty`, with no file, and a ledger whose writer's last rows are older than the days the site copy keeps (Table E, E4) | The column rail lists no column for such a ledger | A row of its own when the first family is paused or retired. Reading the archive for such a ledger costs 3 index reads and 1 whole file (row L10's report; Fowler, 2026-10-07) |

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
| L2 | Explorer browser tests serve the data they check | L1, plan 60 row #32 | B | DONE | ideal-barnacle | #1351 | Plan 62 row l2 |
| L3 | Lifecycle states at the producers | L1 | B | PENDING | - | - | - |
| L4 | A slice cuts only the days before a ledger began | L1 | B | DONE | fluffy-couscous | #1348 | Plan 62 row l4 |
| L5 | Console windows end on the site's newest published day | L4 | C | DONE | solid-potato | #1353 | Plan 62 row l5 |
| L7 | A published ledger that has not started | L1 | B | DONE | expert-pancake | - | Plan 62 row l7 |
| L8 | The archive's failures are named as the archive's | L1, L2, L4, L5 | C | DONE | jubilant-dollop | #1358 | Plan 62 row l8 |
| L9 | Console specs outside the explorer serve the data they check | L2 | C | DONE | special-robot | #1361 | Plan 62 row l9 |
| L10 | The column rail describes a ledger whose newest day holds no rows | L8 | C | DONE | redesigned-spork | #1360 | Plan 62 row l10 |
| L11 | The "Measurement is off" line names only a day that is on screen | L5 | D | DONE | reimagined-happiness | #1363 | Plan 62 row l11 |
| L12 | The data explorer's span sentences say what each ledger read | L10 | D | DONE | miniature-journey | #1364 | Plan 62 row l12 |
| L13 | The remaining console specs check data they build | L9 | D | DONE | curly-umbrella | #1366 | Plan 62 row l13 |
| L14 | Console specs that work their answer out from the canary's own files check data they build | L9 | D | DONE | glowing-waddle | #1365 | Plan 62 row l14 |
| L15 | The held-part note says what its own two figures show | L13 | E | DONE | fuzzy-goggles | #1368 | Plan 62 row l15 |
| L16 | The console's record notes on Hardware and Summaries say only what is true and on screen | L11 | D | DONE | supreme-journey | #1367 | Plan 62 row l16 |
| L17 | Every windowed console surface says "1 day" at the 1-day preset | L13 | E | PENDING | - | - | - |
| L18 | The console home reads each day payload once | L13 | F | PENDING | - | - | - |
| L19 | console-mark-parity's skipped test checks data it builds | L13 | F | PENDING | - | - | - |
| L20 | The dwell rule is placed right when a day that decided nothing sits inside the run | L14 | F | PENDING | - | - | - |
| L21 | The data explorer's action line counts the days a run will read | plan 55 row #10 | F | PENDING | - | - | - |
| L22 | Summaries' one-sided lines say what is true | L16 | F | PENDING | - | - | - |
| L23 | The pipelines route's page and the prompt-cache subtitle say what is drawn | L15 | F | PENDING | - | - | - |

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
| G21 | Rewrite the tests that use a canary ledger only to carry a question: H6, H17, H22, H23, H26, H28, H30, H31, H34, H37, H39, H40, H44, H48, H50, H51, H61 and H62 | L2 | End-to-end | Each test chooses a built ledger, uses `range()` or `VALUES` where the rows do not matter, and first checks the answer state it needs. Today H26 never checks its states: on `main` three of its four questions end `unreachable` and it still passes (reasoned; it is not among the ten that fail) | Removing the state check |
| G22 | Keep on the canary, each test pinning its own day once G7 lands: H1 to H5, H7, H8, H15, H16, H24, H27, H32, H33, H35, H36, H38, H45 to H47, H49 and H52 to H60. A test that opens the page with no clock reads no day, and stays as it is | L2 | End-to-end, `console` | They do not depend on content: the page renders, the layout holds, and nothing errors. H8 is the check that the presets end today (Table D, D2) | - |
| G23 | Keep the specs `console-data-explorer-address`, `-cells`, `-gaps`, `-keep` and `-shape` (group `logic`) and `console-explorer-rails` (group `console`), and L1's browser test in `explorer-boundary.spec.ts`, which builds the root it reads: H63 to H104 | - | Unit and component; H104 end-to-end | Their dates and values are ones the tests wrote themselves | - |

### 2.5 The existing tests, one by one

Table H - the data explorer's tests that a row rewrites, deletes or keeps, by spec and title, with the line of Table G that decides each one: those on `main` at 36fe716e0 (H1 to H43), and those in the explorer specs at L2's dispatch on 2026-10-06 that H1 to H43 do not name (H44 to H104). "Red" marks the ten that fail in run 37361239642.

| # | Spec under `frontend/tests/` | Test title | Table G | Row | Red |
| --- | --- | --- | --- | --- | --- |
| H1 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer opens as the sixth tab and renders its two panels before a run` | G22 | L2 | - |
| H2 | `console-data-explorer.spec.ts` | `THE ORACLE: console chrome resolves to console unless the route asks for workbench` | G22 | L2 | - |
| H3 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer asks for workbench chrome and the other routes keep console chrome` | G22 | L2 | - |
| H4 | `console-data-explorer.spec.ts` | `THE ORACLE: the workbench strip is one compact row at ${view.width}` | G22 | L2 | - |
| H5 | `console-data-explorer.spec.ts` | `THE ORACLE: Data explorer puts the span and the dates in the toolbar, and Run beside Save and Copy link` (renamed by #1336) | G22 | L2 | - |
| H6 | `console-data-explorer.spec.ts` | `THE ORACLE: before a run the column rail names the selected ledger's own columns` | G21 | L2 | - |
| H7 | `console-data-explorer.spec.ts` | `THE ORACLE: the Data explorer fallback document carries the shipped content policy` | G22 | L2 | - |
| H8 | `console-data-explorer.spec.ts` | `THE ORACLE: custom date inputs expose reach bounds and presets end today` | G22 | L2 | - |
| H9 | `console-data-explorer.spec.ts` | `THE ORACLE: with no archive prefix, an old custom span reads from the site's oldest day and says so` | G8 | L2 | - |
| H10 | `console-data-explorer.spec.ts` | `THE ORACLE: a typed join counts the rows of two built ledgers, fetches only their files in the span, and the run cost matches the network` (renamed by L2; was `THE ORACLE: a typed join matches the query door and the run cost matches the network`) | G14 | L2 | Red |
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
| H25 | `console-data-explorer.spec.ts` (added by #1318) | `THE ORACLE: a count by day across a lost day breaks its line there, and the strip prints no number for that day` | G20 | L2 | - |
| H26 | `console-data-explorer-still.spec.ts` | `Run moves nothing in answered, capped, quiet and refused states at ${view.width}px` | G21 | L2 | - |
| H27 | `console-data-explorer-still.spec.ts` | `Copy link notice is fixed and moves no region` | G22 | L2 | - |
| H28 | `console-data-explorer-still.spec.ts` | `status text never overlaps the reserved answer link box` | G21 | L2 | - |
| H29 | `console-data-explorer-still.spec.ts` (removed by #1336) | `M8: every workbench region keeps its idle block size at all four widths` | - | - | - |
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
| H41 | `ledger-door.spec.ts` (deleted by L4, #1348) | `a span that starts before the oldest day any index names is unreachable, and no fault` | G6 | L4 | - |
| H42 | `ledger-door.spec.ts` | `a date both packed and listed is read once, from its packed file` | - | L9 | - |
| H43 | `ledger-door.spec.ts` (deleted by L1, #1327) | `a date in no tier is unreachable at that date, and with no archive the span starts at the site` | G5 | L1 | - |
| H44 | `console-data-explorer.spec.ts` | `THE ORACLE: Copy link carries the question while the link fits console.explorer_link_max_bytes, and leaves it out one character past` | G21 | L2 | - |
| H45 | `console-data-explorer.spec.ts` | `THE ORACLE: a question kept with a day that is not on the calendar is dropped when the page reads browser storage` | G22 | L2 | - |
| H46 | `console-data-explorer-window.spec.ts` | `the workbench reaches the window's right and bottom edges at ${view.width} x ${view.height}` | G22 | L2 | - |
| H47 | `console-data-explorer-window.spec.ts` | `the regions tile a window that holds them, and the page does not scroll, at ${view.width} x ${view.height}` | G22 | L2 | - |
| H48 | `console-data-explorer-window.spec.ts` | `a long list of a ledger's columns scrolls inside the column rail and never stretches the page, at ${view.width} x ${view.height}` | G21 | L2 | - |
| H49 | `console-data-explorer-window.spec.ts` | `the question strip stays one line, folds the rest into "{n} more" and keeps every title whole, at ${view.width}` | G22 | L2 | - |
| H50 | `console-data-explorer-window.spec.ts` | `the chart heading line holds still and the drawing scrolls in its own box beneath it` | G21 | L2 | - |
| H51 | `console-data-explorer-window.spec.ts` | `a long answer and a long question scroll inside their own regions, and the page does not grow` | G21 | L2 | - |
| H52 | `console-data-explorer-window.spec.ts` | `below the wide breakpoint the workbench runs edge to edge and the answer is one window tall, at ${view.width}` | G22 | L2 | - |
| H53 | `console-data-explorer-window.spec.ts` | `only the Data explorer lifts the width cap and leaves the footer out` | G22 | L2 | - |
| H54 | `console-data-explorer-window.spec.ts` | `Run, Save and Copy link stand next to each other in one group, and Run holds still in every state of it, at ${view.width}` | G22 | L2 | - |
| H55 | `console-data-explorer-window.spec.ts` | `the folded list closes on a press outside it, on Escape and after a pick, and stays open after Forget` | G22 | L2 | - |
| H56 | `console-data-explorer-window.spec.ts` | `Forget on a chip on the line moves focus to the nearest Forget left on the line` | G22 | L2 | - |
| H57 | `console-data-explorer-window.spec.ts` | `Forget on the line moves focus to "{n} more" when no Forget is left on the line` | G22 | L2 | - |
| H58 | `console-data-explorer-window.spec.ts` | `History opens its list in view, each line of it whole and inside the window, at ${view.width}` | G22 | L2 | - |
| H59 | `console-data-explorer-window.spec.ts` | `History closes its list on Escape, on a press outside it and after a pick, as the folded list does` | G22 | L2 | - |
| H60 | `console-data-explorer-window.spec.ts` | `the line that says the ledger list did not arrive starts where the editor heading starts` | G22 | L2 | - |
| H61 | `console-data-explorer-window.spec.ts` | `Ctrl+Enter in the editor runs the question` | G21 | L2 | - |
| H62 | `console-data-explorer-window.spec.ts` | `the copy buttons stand on the answer's heading line and overlap no other region, at ${view.width}` | G21 | L2 | - |
| H63 | `console-data-explorer-shape.spec.ts` | `the five documented answer cases choose their chart type or neutral sentence` | G23 | - | - |
| H64 | `console-data-explorer-shape.spec.ts` | `cells arrive as text, as the door returns them, and still give each chart its figures` | G23 | - | - |
| H65 | `console-data-explorer-shape.spec.ts` | `a date answer with several rows on one UTC day draws no date chart and says why` | G23 | - | - |
| H66 | `console-data-explorer-shape.spec.ts` | `a date column holding a day the chart cannot place draws no date chart and names the column and that day` | G23 | - | - |
| H67 | `console-data-explorer-shape.spec.ts` | `a row whose day is NULL is left out of the date chart, and every figure counts only the rows with a day` | G23 | - | - |
| H68 | `console-data-explorer-shape.spec.ts` | `a date column that holds only NULL draws no chart and says so` | G23 | - | - |
| H69 | `console-data-explorer-shape.spec.ts` | `date charts draw four number columns and name columns that would draw flat` | G23 | - | - |
| H70 | `console-data-explorer-shape.spec.ts` | `a lost day between the days an answer has rows for joins the date axis with no row` | G23 | - | - |
| H71 | `console-data-explorer-shape.spec.ts` | `a lost day outside the answer's first and last day, or one the answer has a row for, adds no day` | G23 | - | - |
| H72 | `console-data-explorer-shape.spec.ts` | `a timestamp answer sits on the date axis by its UTC day` | G23 | - | - |
| H73 | `console-data-explorer-shape.spec.ts` | `a timestamp with a time zone sits on the date axis by its UTC day, not the day the engine printed` | G23 | - | - |
| H74 | `console-data-explorer-shape.spec.ts` | `no-chart reasons follow the first matching documented case` | G23 | - | - |
| H75 | `console-data-explorer-shape.spec.ts` | `an answer can qualify for more than one chart type for the operator switch` | G23 | - | - |
| H76 | `console-data-explorer-shape.spec.ts` | `a timestamp of any precision is a day column, so a TIMESTAMP_NS day column draws over time` | G23 | - | - |
| H77 | `console-data-explorer-shape.spec.ts` | `an enum names a ranked row, as text does` | G23 | - | - |
| H78 | `console-data-explorer-shape.spec.ts` | `every whole number the engine prints is a number to the chart, and a list of numbers is not one` | G23 | - | - |
| H79 | `console-data-explorer-shape.spec.ts` | `a NULL is no reading: the spread and paired floors, the paired figure and the ranked tail count only rows with a number` | G23 | - | - |
| H80 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `the ranked list leaves the NULL row out and says it is in the table` | G23 | - | - |
| H81 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `the paired chart draws no point for a row with a NULL` | G23 | - | - |
| H82 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `the spread chart counts no NULL among the readings in its bins` | G23 | - | - |
| H83 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `the date chart breaks its line at a day whose number is NULL` | G23 | - | - |
| H84 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `a floor counts readings, so a NULL can leave a chart too few to draw, and the sentence names the floor it missed` | G23 | - | - |
| H85 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `the date chart draws every row with a day, and its note says how many rows hold null in the day column` | G23 | - | - |
| H86 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `beside a row with no day, a NULL number still breaks the line on its own day and is still no reading in the spread` | G23 | - | - |
| H87 | `console-data-explorer-shape.spec.ts`, inside `the chart panel draws a NULL as no value, never as zero` | `a date column that holds only NULL puts its sentence in the chart room and draws no chart` | G23 | - | - |
| H88 | `console-data-explorer-cells.spec.ts` | `THE ORACLE: cells print by engine column type, not by JavaScript value` | G23 | - | - |
| H89 | `console-data-explorer-cells.spec.ts` | `THE ORACLE: sorting is total, nulls stay last, and third press restores engine order` | G23 | - | - |
| H90 | `console-data-explorer-cells.spec.ts` | `a cell prints by its column type family: every whole number groups, and a list or a struct is its JSON text` | G23 | - | - |
| H91 | `console-data-explorer-cells.spec.ts` | `the first press sorts numbers and days high to low and everything else A to Z, by the column type family` | G23 | - | - |
| H92 | `console-data-explorer-cells.spec.ts` | `in a number column inf sorts above every number and -inf below it, and nan and -nan sort with the NULLs` | G23 | - | - |
| H93 | `console-data-explorer-cells.spec.ts` | `a timestamp with no zone sorts by its UTC instant when the run is in another time zone` | G23 | - | - |
| H94 | `console-data-explorer-cells.spec.ts` | `timestamp_ns values a few nanoseconds apart sort in time order` | G23 | - | - |
| H95 | `console-data-explorer-cells.spec.ts` | `a timestamp with a time zone sorts by its instant, not by the clock time it prints` | G23 | - | - |
| H96 | `console-data-explorer-cells.spec.ts` | `a timestamp in a year below 1000 sorts as the year it prints` | G23 | - | - |
| H97 | `console-data-explorer-cells.spec.ts` | `text that names no instant sorts last with the NULLs, and a year past what a Date holds does not stop the sort` | G23 | - | - |
| H98 | `console-data-explorer-cells.spec.ts` | `a date column sorts as before: newest first on the first press, oldest first on the second, NULLs last` | G23 | - | - |
| H99 | `console-data-explorer-cells.spec.ts` | `a column draws in-cell bars only when its type is a number, so text that holds digits draws none` | G23 | - | - |
| H100 | `console-data-explorer-cells.spec.ts` | `THE ORACLE: the Data explorer route and explorer components never render cell text as HTML` | G23 | - | - |
| H101 | `console-explorer-rails.spec.ts` | `a long column name wraps inside its row and never reaches the next one, and the whole name reaches a screen reader and a hover` | G23 | - | - |
| H102 | `console-explorer-rails.spec.ts` | `in ${theme}, each type in the column rail and the answer header wears its family's token` | G23 | - | - |
| H103 | `console-explorer-rails.spec.ts` | `in ${theme}, a chosen ledger's row is tinted with an accent edge, its words stay readable, and its focus ring shows` | G23 | - | - |
| H104 | `explorer-boundary.spec.ts` (added by L1, #1327) | `days before a ledger began are cut from the selected window, the page names that day, and the archive host gets no request` | G23 | - | - |

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
  - `frontend/tests/console-data-explorer-window.spec.ts` (found at dispatch by the owner: it calls `openExplorer`)
  - `TODO/20261005-62-ledger-lifecycle-plan.md` (Table H, and Table G lines G21 to G23 that list it, brought up to date; found at dispatch by the owner)
  - `docs/reference/agent-notes/gates-and-builds.md` (found during execution: on a busy box the preview start limit fails a fresh build, which reads as a stale one)
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
  - `frontend/tests/console.spec.ts` (calls `windowOfDays`; not in Fowler's list. Found during execution: its committed-ledger test read every packed day of the committed archive through the `-1` that is gone, and is written out on a record the test builds; its two telemetry-read tests take a written-out window)
  - `frontend/tests/console-item-cost.spec.ts` (found during execution: its two window oracles re-derived each figure from the canary's projection over a window that ended on the projection's own newest row, and failed once the console's window ended on the newest published day. They are one oracle on a site the test builds, with written-out answers - Table C, C2)
  - `frontend/tests/support/published-site.ts` (new; found during execution: the published site a test builds - digest days, telemetry shards and the publication list that names them - shared by the oracles in `ledger-rows.spec.ts` and `console-item-cost.spec.ts`)
  - each console spec that assumes a window ends on a record's own last day. Nobody has counted them: run the console group on the L5 branch, and add each failing spec here before editing it
  - `frontend/src/lib/server/payload.ts` (found at dispatch by the owner: `feedResults` takes the window; `latestDate()` is unchanged. Found during execution: `telemetryRows` reads exactly the window it is handed, where it ran back from the projection's own newest row)
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
- **Follow-ups:**
  - L2 (#1351) added `serveArchiveToPage` to `frontend/tests/support/ledger-lifecycle.ts`. With `siteCopy` and `serveToPage` from the same file, and `publishedWindowDays()` from `frontend/scripts/published-ledgers.mjs`, a test serves a trimmed site and its archive. A test that leaves the archive unserved finds it blocked by `frontend/tests/support/browser.ts`; found during execution (row L2 report), owner 2026-10-06.
- **Files touched:**
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/data/slice-reader.ts` (found during execution: `explainShortfall` is exported, so the archive's console line for a file that did not arrive whole uses the slice's own words)
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
- **Follow-ups:**
  - The inventory's canary-day move must move the canary's day by at least 42 days, on the base and on the branch. `item-health` and `host-fingerprint` keep 41 canary days, so a 36-day move does not clear a pinned window; found during execution (row L2 report), owner 2026-10-06.
  - `npm run test:changed` stops at the first browser failure, so to count every red test, run Playwright directly. The new section in `docs/how-to/run-the-gates.md` says how; found during execution (row L2 report), owner 2026-10-06.
- **Inventory**, the row's first step, before any edit:
  1. A canary-day move (Table E, E10) over the `console` and `panels` groups. Every spec with a test that turns red, other than the explorer specs of Table H, joins the inventory.
  2. A reading of each `logic` spec whose name starts with `console-` or `ledger-`, for a test that computes its expected value by running a reader over the canary or a committed fixture, or that copies a fixture made for other questions. Each one joins the inventory. Two are known now (Files touched).
  3. The change that starts the row writes every spec that joined into Files touched, with each test's title and the step that found it.
- **Files touched** (the inventory, taken on base 8740c2d24 on 2026-10-06 and written by the change that starts the row: each spec, each test's title and the step that found it; found during execution):
  - Step 1, the canary-day move: `DATE` from 2026-08-20 to 2026-10-02, 43 days. The `console` and `panels` groups ran with Playwright directly, with the captures skipped as routine CI skips them. Of 976 tests, 966 passed, 6 were skipped (the same 6 skip on the unmoved canary) and 4 were red. Each red test passed on the unmoved canary. `console-readout.spec.ts` "THE ORACLE: the console has charts on every side of the partition" was red only beside three other workers, and passed alone on the same moved build, so it does not join.
    - `frontend/tests/console-telemetry-heal.spec.ts`: "a failed month load heals on a later widen" (it names the month 2026-07)
    - `frontend/tests/console.spec.ts`: "a candle carries its spread and its runs without a mouse"; "writing draws slower than reading, on one shared scale" (each names the day 2026-08-20)
  - Step 2, a reading of the `logic` specs named `console-*` or `ledger-*`, the explorer's left out. The eight `console-*` specs build their rows in memory, and `ledger-lifecycle.spec.ts` builds its roots, so none of them joins.
    - `frontend/tests/ledger-door.spec.ts`, each test reading an expected figure back from the door fixture: H42 "a date both packed and listed is read once, from its packed file"; "a file whose decoded length is not its entry bytes is unreachable, and the engine never sees it"; "an index is asked for fresh, and a data file under the version its entry names"; "a file whose entry names a new version is fetched and registered again by the next page, and the open page keeps what it holds"; "an open page answers unreachable for a day file removed or re-packed after it opened, and the next page reads the day"; "only a year file is offered to the engine by byte range, and an engine that reads no host is handed it whole"; "the archive answers the days the site copy dropped, and with no archive the days before the site's first are cut"; "a ledger whose packed days hold no rows answers through an empty view over its zero-row file". A test that compares the door's two entry points, or two packings, does not join: the two sides are what it tests, and one side is written out.
    - `frontend/tests/ledger-rows.spec.ts`, each test building its data from the door fixture: "a packed day missing from the middle makes the whole read unreadable, at that day, named day-missing"; "a packed file the list names and the disk lacks makes the read unreadable, named file-missing"; "one day reads on its own, and every cell comes back as the day files spelled it"; "a window whose packed days hold no row reads no row, and names where the rows stop instead of reaching back"; "a window that starts before the first packed day is read from that day"; "a day the packing recorded lost comes back named, beside the files each day set aside"; "a day lost before the window is not named, because nothing before the window is read"; "it is printed once as a plain note, and the recording note never dates the start after it"
    - `frontend/tests/ledger-copy.spec.ts`, which reads every expected field from `tests/fixtures/raw-day-listing/`: "the build listing keeps the compaction listing digest and adds file sizes"
  - Named by the owner from row L5's report (2026-10-07). The move leaves these green, because each one works out its answer from the moved canary:
    - `frontend/tests/console-item-cost.spec.ts`: "the share is printed and never drawn as a trend, and the page says why"
    - `frontend/tests/console.spec.ts`, each other test that reads the canary's files for its answer: "the strip reads oldest to newest, left to right"; "every recorded run gets a square, and nothing else does"; "runs rise from a shared baseline, on a square day track"; "on a phone the strip scrolls, and opens on the newest run"; "the grid draws one square per run, coloured by what the run did"; "a square says what happened without a mouse"; "the run that read only the start of an article says so on its own square"; "THE ORACLE: the feed headline carries its own denominator and span"; "THE ORACLE: the disclosed names are exactly the feeds that did not fail"; "THE ORACLE: the failure list is capped and its tail counts the remainder"; "the telemetry viewport renders the published projection"; "every chart cell equals what the day committed"; "the measured day prints rates, and the day with no minutes prints dashes"; "a visual that never drew is a visual and is not a published chart"; "every model cell equals what the day committed"; "a day the scorer never reached prints dashes, and still prints its speed"
    - `frontend/tests/console-machine-data.spec.ts`: "the canary agrees, and disagrees once one row cost goes missing" and "the server counters are what turn it, and not the item rows alone" (in "THE ORACLE: one item cost, taken away"); "the packed ledgers have rows to read", "nothing derived off them is impossible" and "a run the reader refuses says which run and why" (in "the ledgers this reads, as the canary packs them"); "an empty root cannot fall back to the populated canary or the archive"; "THE ORACLE: the unused share is the largest article recomputed off the ledger", "THE ORACLE: every run mark carries both ends, not one", "the strip prints both ends and names the percentile in words" and "THE ORACLE: the built page draws both ends a run, in date order, under the rule" (in the context panel's block); "THE ORACLE: one value per configured percentile, per readable run", "THE ORACLE: the strip under the plots prints the newest run own ladder" and "THE ORACLE: the printed spread is the newest run slowest over its middle" (in "one plot a percentile, on one shared scale")
    - `frontend/tests/console-voices-feeds.spec.ts`: "THE ORACLE: the printed count is the run the pipeline rests on"; "THE ORACLE: a source we were only ever refused by is in neither count"; "the two counts still add up to the denominator beside them"
    - `frontend/tests/support/canary-records.ts`, which reads the canary's records for them
  - Left out on purpose: `frontend/tests/panel-captures.spec.ts`, whose captures picture the canary (owner, 2026-10-07).
  - `frontend/tests/support/ledger-lifecycle.ts` (found during execution: the builder writes chosen typed columns beside `covers`, `date` and `n`, and a lost day can carry the count of files it set aside, so `ledger-rows.spec.ts` builds the two records it copied from the door fixture. Row L8 held the builder; the owner handed it to this row on 2026-10-07, after L8 merged as #1358. A packed day may also hold 0 rows, as files packed before #1309 do: its file holds every column and no row, and a closed month whose days hold no row packs as `empty`, with no file; owner, 2026-10-07)
  - `frontend/tests/ledger-lifecycle.spec.ts` (found during execution: Fowler's reader case from row L10's decision 4, beside L10's column-rail cases. A ledger whose newest file was packed with 0 rows lists its columns from that file. This closes L10's follow-up; owner, 2026-10-07)
  - Six titles now say what their tests check (found during execution). In `console.spec.ts`: "every chart cell equals what the day committed" is "every chart row is a day of the window, newest first, and its rates follow its own counts"; "every model cell equals what the day committed" is "every model cell prints a count, a share, a time or a dash, on a day of the window"; "writing draws slower than reading, on one shared scale" is "the slower of reading and writing sits lower, on one shared scale". In `console-machine-data.spec.ts`: "the canary agrees, and disagrees once one row cost goes missing" is "the two ledgers agree, and disagree once one row cost goes missing"; the block "the ledgers this reads, as the canary packs them" is "the ledgers this reads, over a record written here", and its "the packed ledgers have rows to read" is "the record reads as one run and one refused run"
  - `frontend/tests/support/canary-records.ts` is unchanged (found during execution): no spec in the inventory reads it now, and 12 specs outside the inventory still do - `console-article-cost`, `console-disk-reads`, `console-doubt`, `console-machine-panels`, `console-memory-board`, `console-model-instruments`, `console-model-panels`, `console-model-rule`, `console-shard-board`, `console-timings`, `console-voices-sources` and `console-window`. Each works its answer out from the canary, so the canary-day move leaves it green, and neither step of the inventory names it
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

### Row #L10 - The column rail describes a ledger whose newest day holds no rows

- **Scope:** When a chosen ledger's newest named day is `empty` (Table F, F4, F6 and F7) or `lost` (F5), the data explorer's column rail still lists that ledger's columns. Level 2.
- **Files touched** (each path checked on `main` at ea1878cdc; search again once decision 1 is ruled):
  - `frontend/src/routes/console/data-explorer/+page.svelte` (the rail describes each chosen ledger from `cost.through`, its newest named day)
  - `frontend/src/lib/data/ask-reader.ts` (`readAsk` answers `quiet` for a span that holds no file before it uses the empty view: a `LIMIT 0` view over the ledger's newest file)
  - `frontend/src/lib/data/ledger-columns.ts` (new: the rail's own door call, which takes no window; found during execution, Fowler's ruling on decision 1)
  - `frontend/src/lib/data/ledger.ts` (exports `askColumns`; found during execution, Fowler's ruling on decision 1)
  - `frontend/tests/ledger-lifecycle.spec.ts` (the reader's case, on a root that Table G, G1 builds)
  - `frontend/tests/console-data-explorer.spec.ts` (the Oracle)
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-lifecycle.spec.ts --spec console-data-explorer.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the data explorer. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-data-explorer.spec.ts`, on a root the test builds (Table D, D3): a ledger whose newest two named days are `empty` and whose day before them is `packed` lists its columns in the rail. On `main` the rail lists no column for it, which is what lets this check fail. It cannot settle a ledger whose newest day that holds rows is older than the selected window; whether the rail reads such a day is decision 1.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The rail gets a door call of its own, `askColumns()` in `frontend/src/lib/data/ledger.ts`, over `readColumns()` in `frontend/src/lib/data/ledger-columns.ts`. It takes no window, and it lists the columns of the files the ledger's empty view reads (`viewSource()` in `ask-reader.ts`): the newest listed raw day that has files, else the newest index entry that names a file, even one with 0 rows. It runs in the written-question door's queue, keeps the fetch ceiling, and leaves `readAsk`, its quiet rule and `SpanCost` as they were. It may read a file older than the selected window: it returns no rows and takes no window, so it cannot choose, widen, move or end one, and Table D, D2 holds. C1 and C3 do not fire | Fowler, 2026-10-07 |
| 2 | L10 waits for L8, because L8 edits `ask-reader.ts`, `+page.svelte` and the written-question page | Found during execution (row L2 report), owner 2026-10-06 |
| 3 | Level 2: what the rail lists changes for one kind of ledger, and every explorer question reads through `ask-reader.ts` | Found during execution (row L2 report), owner 2026-10-06 |
| 4 | Fowler's reader case for a ledger whose files were packed with 0 rows before #1309 waits: the builder refuses `rows: 0`, and L9 owns the builder this round. The empty view's rule already reads such a file. Closed by row L9: the builder packs a day with 0 rows, and the case is in `frontend/tests/ledger-lifecycle.spec.ts` | Found during execution; the owner's dispatch note, 2026-10-07; closed by row L9, owner 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: the rail describes each chosen ledger from its newest named day | When that day holds no rows, the rail lists no column for the ledger | Nothing to build, and no column in the rail for a ledger whose newest day was quiet or lost, or whose writer is paused or stopped | Found during execution (row L2 report), owner 2026-10-06 |
| 2 | Describe from the newest day that holds rows, found from the indexes: a second day for each ledger on `SpanCost`, and the page asks `DESCRIBE` over it | A second rule for "the newest file", which disagrees with the empty view because it skips a file with 0 rows | No new door call, and no column for `candidate-models`, whose packed files hold 0 rows | Fowler, 2026-10-07 |
| 3 | `readAsk` answers a `DESCRIBE` over a span with no file from the empty views | `DESCRIBE` becomes a special case inside the quiet rule, and a third rule is needed so that a ledger with no file does not answer `missing`, whose words are false for it (Table B, B4) | No page change, and an operator's own `DESCRIBE` over a quiet span would answer its columns too | Fowler, 2026-10-07 |

### Row #L11 - The "Measurement is off" line names only a day that is on screen

- **Scope:** When measurement is off, the "Measurement is off" line on the Hardware and Summaries routes names no day outside the window, and says that nothing has been recorded at all only for a record that never held a row. Level 1.
- **Files touched** (each path checked on `main` at 0d61b9b49; the two `+page.server.ts` files found by a search for "Measurement is off", and the two `+page.svelte` files by a search for `recording.off`):
  - `frontend/src/lib/console/recording.ts` (`measurementOff` names the newest recorded day that `recordingNotes` is handed, and says "Nothing has been recorded at all" when it is handed none)
  - `frontend/src/routes/console/machine/+page.server.ts` (Hardware: hands `recordingNotes` the days each window recorded, so a window that starts after the record's rows hands it none)
  - `frontend/src/routes/console/model/+page.server.ts` (Summaries: hands `recordingNotes` the scored days of the widest window, once, so the day the line names can be outside the open window)
  - `frontend/src/routes/console/machine/+page.svelte` (prints the line)
  - `frontend/src/routes/console/model/+page.svelte` (prints the line)
  - `frontend/tests/console-chrome.spec.ts` (pins both wordings of the line)
  - `frontend/tests/ledger-rows.spec.ts` (the Oracle, beside Table G, G10, which builds the same site)
  - `docs/concepts/console-design.md` (the lines with fixed wording, and the rule that quotes `Measurement is off`)
  - `docs/architecture/publishing/console-payloads.md` (a record whose route prints the line gets no second note)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-rows.spec.ts --spec console-chrome.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the two pages; the browser smoke of the console's Hardware and Summaries routes. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `ledger-rows.spec.ts`, on a site the test builds (Table D, D3): a record with measurement off whose rows stop 40 days before the newest published day. For each window the route offers, the line names no day outside that window and does not say "Nothing has been recorded at all". A record that never held a row still says so. It cannot settle the words, which Reader and Jony choose (decision 1); the test pins the words they choose.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader and Jony choose the line's words for both cases (CLAUDE.md section 14) | To be ruled at dispatch (Reader and Jony) |
| 2 | No owner ruling set today's words: #310 shipped them as the observability plan recorded them, under Susan's authority (#304) | The owner, 2026-10-07; the record is #304 |
| 3 | The header of `recording.ts` says "the owner wrote the first of them on 2026-08-30", and the test group "what the recording was doing, in the owner words" in `console-chrome.spec.ts` says the same. The row corrects both | Plan author, 2026-10-07, from #304 and #310 |
| 4 | L11 waits for L5: since #1353 every window ends on the newest published day and reads only its own days, which is what makes the line false for a record whose rows stop before the window | The owner, 2026-10-07 |
| 5 | Level 1: the words of one line and the facts that two routes hand it; a wrong version shows on those two routes | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The line says "Nothing has been recorded at all" of a record whose rows stop before the window, which is false, and "so the figures below stop on that day" can name a day that is not on screen | Nothing to build, and a false line on two routes whenever measurement has been off for longer than the open window | Row L5's report; the owner, 2026-10-07 |

### Row #L12 - The data explorer's span sentences say what each ledger read

- **Scope:** The sentences under a data explorer answer count the days that were read, give every date its year, and name each ledger with its own first day, so that each sentence is true for every ledger the answer read. Level 2.
- **Files touched** (each path checked on `main` at 0d61b9b49):
  - `frontend/src/routes/console/data-explorer/+page.svelte` ("Read from {n} UTC days, {from} to {to}." takes `n` from `spanDays()`, the days asked, and prints the first date with no year)
  - `frontend/src/lib/console/waiting.ts` (`explorerSiteFromSentence`: "Days before {day} are not on this site.", which names no ledger)
  - `frontend/src/lib/console/explorer/days-read.ts` (new; found during execution: the span line and the sentence for each cut ledger, beside `gaps.ts`, with relative imports so the logic suite pins Reader's words. `waiting.ts` says what a panel says while it has no rows, which the span line is not, so `explorerSiteFromSentence` leaves it)
  - `frontend/src/lib/data/ask-reader.ts` (if the answer carries each ledger's first day: it keeps only the earliest of the ledgers' `siteFrom` days)
  - `frontend/src/lib/data/slice-shapes.ts` (found by a search for `siteFrom`: `siteFrom` on `SpanCost` and on the `ok` and `quiet` answers)
  - `frontend/tests/ledger-lifecycle.spec.ts` (the reader's cases, on roots Table G, G1 builds)
  - `frontend/tests/ledger-door.spec.ts` (found by a search for `siteFrom`)
  - `frontend/tests/console-data-explorer.spec.ts` (pins the sentence)
  - `frontend/tests/explorer-boundary.spec.ts` (found by a search for the sentence: pins it)
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/how-to/query-a-ledger-from-the-console.md` (found by a search for the sentence: quotes it)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-lifecycle.spec.ts --spec ledger-door.spec.ts --spec console-data-explorer.spec.ts --spec explorer-boundary.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the two pages; the browser smoke of the data explorer. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on ledgers the test builds (Table D, D3): two ledgers with different first days, both inside the window. The answer names each ledger with its own first day, the sentence counts the days read, and both of its dates carry their year. It cannot settle a ledger whose first day only the archive holds, because both of the Oracle's ledgers begin on the site.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words of the span sentences (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 2 | If the answer carries each ledger's first day, that is a field of the run-time answer in `slice-shapes.ts`, as `unanswered` is since L8, and not a persisted shape, so Table C, C1 does not fire | Plan author, 2026-10-07, from row L8, decision 2 |
| 3 | L12 waits for L10, because L10 edited `+page.svelte`, `ask-reader.ts`, `ledger-lifecycle.spec.ts`, `console-data-explorer.spec.ts` and the written-question page | The owner, 2026-10-07 |
| 4 | Level 2: the sentences under every explorer answer change, and every explorer question reads through `ask-reader.ts` | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | "Read from {n} UTC days" counts the days asked, not the days read. Its first date has no year ("16 Jun to 15 Jun 2030"). "Days before {day} are not on this site." names no ledger, and since L1 the cut is per ledger, so for two ledgers that began on different days it is false for one of them | Nothing to build. Every answer prints its first date with no year, and an answer that cuts a ledger counts days it did not read and can name a first day that is false for another ledger | Reader, row L8's report; the owner, 2026-10-07 |

### Row #L13 - The remaining console specs check data they build

- **Scope:** Every console spec that still works its answer out from the canary, or writes out a canary figure, serves a root it built and checks written-out values. The row starts with an inventory taken when it is dispatched. Level 2.
- **Inventory**, the row's first step, before any edit:
  1. A canary content change: one value in one row that `backend/utilities/build_canary_day.py` writes, with the canary's day left as it is, over the `console` and `panels` groups. Like a canary-day move (Table E, E10), it is a measurement, never a commit. Run Playwright directly, as row L9's follow-ups say, so that every red test is counted.
  2. Every test the change turns red joins the row, except the panel captures in `frontend/tests/panel-captures.spec.ts`, which picture the canary on purpose.
  3. The change that starts the row writes every spec that joined into Files touched, with each test's title.
- **Files touched** (each path checked on `main` at 0d61b9b49. The inventory, taken on base 1414492d5 on 2026-10-07, adds each test's title and the step that found it; found during execution. It counted 71 tests, over the owner's line of about 60, so the row stopped after it. The owner kept 53 here and moved the rest to row L14, 2026-10-07):
  - Step 1, the canary content change: in `_health_rows()`, run 3 of 2026-08-20 of `canary-empty` answers 3 items instead of 0, so the feed still answered with nothing once, on run 2. The `console` and `panels` groups ran with Playwright directly, 3 workers, the captures skipped as routine CI skips them. Of 978 tests, 970 passed, 6 were skipped (the same 6 as on the unchanged canary) and 2 were red, both in `console.spec.ts` and both among its 11 below: "a feed that answered with nothing does not report its last result as ok" and "a feed past the quarantine count is marked rested". No other spec turned red.
  - `frontend/tests/support/canary-records.ts` (12 console specs outside L9's inventory still read it; row L9's report. It goes once none does)
  - The 12 specs, each test that reaches the canary through `canary-records.ts`, found by following each test's calls (39 tests):
    - `frontend/tests/console-article-cost.spec.ts` (8): in "the three costs, as arithmetic", "processor time is the busy share across the LOGICAL processors, not the cores", "the canary carries that case, so the page is drawing a real absence" and "model time is reading the prompt and writing the reply, added up"; in "the panel, on the canary", "THE ORACLE: every printed figure is the fixture rows recomputed", "THE ORACLE: articles no machine record answered for are counted, not dropped", "processor time is printed beside the hour it has to fit inside", "THE ORACLE: the added-memory figure is the fixture steps recomputed" and "a figure the fixture cannot fill prints a dash and the reason, not a zero"
    - `frontend/tests/console-disk-reads.spec.ts` (3): "a day counts the articles that were not first on their shard, and only those"; "the pinning line is read off the runs, not written into the panel"; "the panel leads with the finding, and the finding names the worst day"
    - `frontend/tests/console-doubt.spec.ts` (2): "THE ORACLE: the drawn rows are what the two ledgers say"; "a summary no source could be found for is named, not dropped"
    - `frontend/tests/console-machine-panels.spec.ts` (3): "one group a machine, and no element carries a rate pooled over all shards"; "every rate in a group recomputes from that machine shards alone"; "unchanged machine cards preserve flags, copy speed, clocks, disclosure and L3 ratios"
    - `frontend/tests/console-memory-board.spec.ts` (4): "THE ORACLE: the item minimum on the page recomputes from the canary ledger"; "THE ORACLE: an item with no kernel reading is hatched and its count printed"; "THE ORACLE: the disputed mark is off the page and the page says so"; "every item mark carries its own figures, recomputed from the ledger"
    - `frontend/tests/console-model-instruments.spec.ts` (2): "THE ORACLE: what the page drew is what the built ledger holds"; "THE ORACLE: the axis floor is the one the drawn days ask for"
    - `frontend/tests/console-model-panels.spec.ts` (1): "THE ORACLE: the drawn rules are the values the module measured"
    - `frontend/tests/console-model-rule.spec.ts` (4): "the committed ledger, read by both implementations, agrees"; "a chart that draws the rule draws one per boundary inside its own span"; "a chart that draws no rule in its span says so, rather than being blank"; "the boundary reaches the readout on the days it happened, and no others"
    - `frontend/tests/console-shard-board.spec.ts` (2): "every host figure on a row recomputes from the canary ledgers"; "THE ORACLE: a shard whose clocks disagree says so, and never draws a zero"
    - `frontend/tests/console-timings.spec.ts` (1): "THE ORACLE: one sentence, whatever the series count, with both its numbers"
    - `frontend/tests/console-voices-sources.spec.ts` (8, three of them through the canary's `source-health.json`): "THE ORACLE: the drawn rule stands where the ledger says the cut fell"; "one row per source the cap cut, worst first, with the count in the label"; "the label counts articles, not rows, and the track reads the right cell"; "what the cut cost is the first sentence of the section, with its n"; "a window with no cut renders its own empty state, and absence is not zero"; "THE ORACLE: every state the view holds is drawn, and the states sum to the census"; "THE ORACLE: every source held back is named, with what it withholds"; "THE ORACLE: the publishing record prints counts, and says when it is too short"
    - `frontend/tests/console-window.spec.ts` (1): "THE ORACLE: a daily table drawn under the control is drawn over the control span"
  - `frontend/tests/console.spec.ts` (11 tests write out canary figures: feed names, timing medians and throughput rates. They read no canary file, so the canary-day move left them green; row L9's report. Named here by reading each test): "a feed that answered with nothing is named, and a polite refusal is not"; "a feed that answered with nothing does not report its last result as ok"; "a feed past the quarantine count is marked rested"; "stage medians come from item health, not the score ledger"; "the timing y axis is decades, and it crosses milliseconds to seconds"; "the timing legend is sorted by the newest day, tallest first"; "a stage with no number draws a gap, never a plunge to the axis floor"; "a timing nobody took, a timing of zero and a partly timed day read apart"; "reading and writing are drawn as separate candles per day"; "the throughput axis covers the rates drawn, not zero to the fastest"; "panning to a month with no rows leaves a visible gap". Found during execution: the three feed tests check reads they write and the page against itself, under titles that say so; the timing and token-rate tests draw their charts from days they write (decision 6); the pan serves its own telemetry; and a new test, "a day's two rates are its whole tokens over its whole seconds, and each run keeps its own", holds the rates the throughput test used to write out
  - Titles that named the canary, the fixture or a recomputation now say what their tests check, in 11 of the 12 specs and in `console.spec.ts` (found during execution). The 16 files this row edits or adds hold 309 tests, against 293 before it; the pull request lists each title that changed
  - The 21 tests in nine more console specs that read the canary's own files (`console-band`, `-charts-rule`, `-compression`, `-failure`, `-failures`, `-model-reasons`, `-pipeline-timeline`, `-published` and `-run-health`), the premise test "the fixture reaches all three states, so none of them can pass by never firing" in `console-compression.spec.ts`, and the 3 tests of `console-voices-retiring.spec.ts` that skip on what the canary holds: moved to row L14 (owner, 2026-10-07)
  - Found during execution, and kept here because row L14 must not edit these specs (owner, 2026-10-07): `console-machine-panels.spec.ts` "the canary is a day the record answered for, so a loss is never claimed", whose premise is a fact the canary holds although it reads no canary file; and `console-model-panels.spec.ts` "THE ORACLE: the panel takes the width it is given, and its rows fit it" and "at 390 the labels go above the track rather than squeezing the plot", which skip when the canary holds no model change, by a locator count, so they never run on it
  - `frontend/src/routes/console/+page.server.ts` (`chartDays`, `cutsByRun` and the stage-timing reduction move out: a `+page.server.ts` may export nothing else, so they cannot have logic tests where they are; row L9's report, and decision 6 for the third)
  - `frontend/src/lib/server/chart-days.ts`, `frontend/src/lib/server/cuts-by-run.ts` and `frontend/src/lib/server/stage-timing-days.ts` (new, one question each; decision 6. The third found during execution)
  - `frontend/tests/console-chart-days.spec.ts`, `frontend/tests/console-cuts-by-run.spec.ts` and `frontend/tests/console-stage-timing-days.spec.ts` (new, under `logic`; decision 6)
  - `frontend/scripts/test-groups.ts` (names the new specs under `logic`)
  - `frontend/tests/console-item-cost.spec.ts` (under L9, its test "the share is printed and never drawn as a trend, and the page says why" dropped its canary premise check, that the held part of a prompt has not started moving; decision 4. Unchanged here: the page checks that premise in row L15)
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md` (the held part's reading and its step on 2026-09-13, decision 4; and its sentence that a timed zero "is counted as untimed", which the code and `console-charts.md` contradict, decision 6; found during execution)
  - `frontend/src/lib/console/item-cost.ts` (the `reusedMedian` comment points at that section instead of repeating the 2026-09-05 reading; decision 4, found during execution)
- **Acceptance gates:** local: the inventory's canary content change, repeated on the branch; `npm --prefix frontend run test:changed -- --list`, then the groups it selects; `npm --prefix frontend run check`; the browser smoke of the console's home route, whose build code moves. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** after the row, the same canary content change turns no spec in the `console` and `panels` groups red, except the panel captures. It cannot settle a test that works its answer out from the canary, because the change moves its answer and its expected value together; that is why the 12 specs are named from row L9's report and not by the change.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The inventory is a canary content change, not a canary-day move: a day move changes dates and no figures, so neither step of L9's inventory finds a test that writes out a canary figure | Row L9's report; the owner, 2026-10-07 |
| 2 | The panel captures stay on the canary, because they picture it on purpose | The owner, 2026-10-07, as for row L9 |
| 3 | `chartDays` and `cutsByRun` move out of the route in a structural commit of its own, with no behaviour change, before any test reads them | Row L9's report; the owner, 2026-10-07 |
| 4 | The premise that the item-cost share test dropped is a fact about the data, so no test holds it again (Table D, D3). CLAUDE.md section 13 sends such a check to the producer or to an operator utility; Fowler rules which at dispatch. He ruled an operator utility that a person runs, never on a run's path: `backend/utilities/held_prompt_premise.py` reads the item-health days of a window the person names, counts each item's held tokens by the item-cost section's rule (the first call's figure where an item made two calls), and exits 1 when the largest held count minus the middle one is not under the middle one. Its unit test writes its own rows, and `tests/fixtures/held-prompt/rows.json` holds rows with written-out answers that the Python rule and `itemCost` must both give. Its first run on the committed ledger replaces the 2026-09-05 reading; if that run fails, the note is false today and the owner decides.<br>Superseded: the audit's first reading, over the 90 days ending 2026-10-06, failed - the middle item held 922 tokens and the largest 2,219, because the held part stepped on 2026-09-13. The premise check moves into the page: the note picks its sentence from the two figures it prints (row L15). The audit is not built | Plan author, 2026-10-07; Fowler, 2026-10-07 (his option A3); superseded by the owner, 2026-10-07, after the audit's first reading |
| 5 | Level 2: tests, and one move of two functions out of the console's home route with no behaviour change | The owner, 2026-10-07 |
| 6 | Three files under `frontend/src/lib/server/`, one question each, moved in the structural commit of decision 3: `chart-days.ts` (`ChartDay`, `chartDays`), `cuts-by-run.ts` (`cutsByRun`, over `wasCut` from `model-work.ts`) and `stage-timing-days.ts` (`stageTimingDays`, the route's `timingDays` with `median`, `measured`, `sample`, `timing` and `byDate`). The third is found during execution: no test can hand the medians rows it wrote while they sit in the route. Each gets a logic spec on rows it writes. Of the five timing tests in `console.spec.ts`, "stage medians come from item health, not the score ledger" goes, because the logic spec holds it. The other four draw the chart from days they write and check written-out values (found during execution: a check that holds for any data cannot reach a gap, a zero or a partly timed day without a premise about the canary) | Fowler, 2026-10-07 (his option B3) |
| 7 | The inventory counted 71 tests. This row keeps the 39 tests of the 12 named specs, the 11 in `console.spec.ts`, the three tests of those specs that depend on the canary without reading it, the three moves and decision 4: 53 tests. Row L14 takes the 21 tests of the nine specs found during execution, the compression premise test and `console-voices-retiring.spec.ts`, and edits no file of this row | The owner, 2026-10-07 (option A4 of the row's inventory report) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A canary-day move, as row L9's inventory took | It changes dates, not figures, so it finds none of the 11 tests in `console.spec.ts` and none of the 12 specs | No new step, and a row that misses the tests it exists for | Row L9's report; the owner, 2026-10-07 |
| 2 | As today: the 12 specs keep reading the canary through `canary-records.ts` | `canary-records.ts` reads the canary through the readers that the page's server calls - `itemHealthRows`, `evalRows` and `machineRecord` - so each spec compares the page with an answer computed from data (Table D, D3) | Nothing to build, and a fault in one of those readers moves the page and the expected answer together, so no test turns red | The owner, 2026-10-05 (Table D, D3) |
| 3 | Decision 4's check as a warning in `public_telemetry.py`, a metric in the drift report, or a step of `check-publication` (Fowler's options A1, A2 and A4) | The first makes the code that publishes the browser's copy judge a panel's design, over one month rather than the panel's window, in a log line nobody reads on a green run. The second gives `drift.py`, which compares scores across two windows, a second job. The third lets a fact about the data stop a publish | A check that runs on every run or publish without a person asking | Fowler, 2026-10-07 |
| 4 | The item-cost note picks its own sentence from the two figures it already prints, inside this row (Fowler's option A5) | It changes what the page says, which Reader and Jony own, and this row changes tests and moves code with no behaviour change. The owner took it as a row of its own, L15, after the audit's first reading | One copy of the rule, checked on every build for the window on screen | Fowler, 2026-10-07; the owner, 2026-10-07 |


### Row #L14 - Console specs that work their answer out from the canary's own files check data they build

- **Scope:** Every console test that reads the canary's own files and works its expected answer out from them, and every console test that skips on what the canary holds, builds the data it reads and checks written-out values. A test whose only check is a fact about the data is deleted, and the row names where that check belongs. Level 2.
- **Files touched** (each path checked on `main` at 1414492d5; the tests are row L13's inventory, taken on base 1414492d5, by reading each test):
  - `frontend/tests/console-band.spec.ts` (1): "THE ORACLE: the band prints the articles the headroom buys"
  - `frontend/tests/console-charts-rule.spec.ts` (2): "THE ORACLE: the printed median is the median of the fixture over the rule span"; "the marker on each bar sits where the geometry puts it"
  - `frontend/tests/console-compression.spec.ts` (2): "THE ORACLE: the three-way split adds up to the day, every day in the window"; "the tail says how many rows are hidden, and never sums the distances"
  - `frontend/tests/console-failure.spec.ts` (4): "the printed denominators are the ones the ledger holds"; "a day under the threshold gets no mark, and a day over it gets one"; "a window too thin to divide states that, and never a rate"; "a window holding nothing renders, and says so rather than drawing zero"
  - `frontend/tests/console-failures.spec.ts` (3): "the three empty states say different things"; "the two empty states say different things"; "the rows carry the item id without spending a column on it"
  - `frontend/tests/console-model-reasons.spec.ts` (4): "a high summary never carries a reason in the tree the site was built from"; "THE ORACLE: what the page drew is what the built tree holds"; "the strip is the key, and it prints one row per reason the window saw"; "a reason the window never saw is named in words, not left invisible"
  - `frontend/tests/console-pipeline-timeline.spec.ts` (1): "every column the panel reads carries a value on at least one canary row"
  - `frontend/tests/console-published.spec.ts` (2): "THE ORACLE: the articles card counts what the committed days published"; "THE ORACLE: the cost panel says what it is for, and its chart fills its frame"
  - `frontend/tests/console-run-health.spec.ts` (2): "THE ORACLE: a run row says how many of the articles it tried succeeded"; "on a phone a tap or a step on the chart brings its day into view, and a hover never moves the squares"
  - `frontend/tests/console-voices-retiring.spec.ts` (3, each skipped on the canary because no source is under the mark): "every row draws its bar on the same track with its marker at the same share"; "the dwell is an area under the newest squares, not a number in a chip"; "a live countdown reads its days and its date without colour"
  - `frontend/tests/support/ledger-lifecycle.ts` and `frontend/tests/support/published-site.ts` (only if a rewritten test needs them to build more; every existing behaviour is kept, and the specs that import them run. Neither changed: the two reader tests write their day payloads and manifest into a site `published-site.ts` builds, as row L9's chart test does)
  - `frontend/tests/support/served-telemetry.ts` (new, found during execution: `/console/` fetches its telemetry months, so a test answers those fetches with rows it builds for the window the page opened on. `console-compression`, `console-failure` and `console-failures` use it)
  - `frontend/src/lib/server/source-retiring.ts` (new), `frontend/src/lib/charts/targetbar.ts`, `frontend/src/routes/console/voices/+page.server.ts` and `frontend/src/routes/console/voices/+page.svelte` (decision 4, found during execution: `retiring()`, its helpers and types move out of the route; `shareMarks()` moves to `targetbar.ts`, because the standing panel draws it too; the countdown's readout and the dwell rule's first column are worked out in `retiring()`)
  - `backend/tests/test_console_payloads_producer.py` (decision 5) and `backend/tests/contracts/test_frontend_console_lists.py` (decision 6)
  - Four titles now say what their tests check (found during execution). In `console-charts-rule.spec.ts`: "THE ORACLE: the printed median is the median of the fixture over the rule span" is "THE ORACLE: the printed median is the median of the days the table prints over the rule span"; "the marker on each bar sits where the geometry puts it" is "the marker on each bar sits where the bar says it does". In `console-model-reasons.spec.ts`: "THE ORACLE: what the page drew is what the built tree holds" is "THE ORACLE: each drawn day adds up to its column, and the sentences count the same days". In `console-published.spec.ts`: "THE ORACLE: the articles card counts what the committed days published" is "THE ORACLE: the articles card counts what the chart table says each day published"
  - Two new tests, one for each reader the routes call with no logic test (decision 6): `console-published.spec.ts` "the articles a day published are read off its own payload, over the days the cover reaches" and `console-run-health.spec.ts` "a run manifest reads into the facts its square and its line are built from"
  - Four tests deleted, each with where its check lives: `console-band.spec.ts` "THE ORACLE: the band prints the articles the headroom buys" (the producer's test, decision 5); `console-model-reasons.spec.ts` "a high summary never carries a reason in the tree the site was built from" (`backend/tests/pipeline/test_banding.py`, decision 6); `console-pipeline-timeline.spec.ts` "every column the panel reads carries a value on at least one canary row" (the binding test, decision 6); and `console-compression.spec.ts` "the fixture reaches all three states, so none of them can pass by never firing" (found during execution: it asked whether the canary reaches all three states, and the rewritten oracle builds all three and counts their five parts)
- **Follow-ups** (found during execution):
  - The dwell rule starts at column `dates.length - daysUnder + 1`, but the producer's `dwell()` counts through a day that decided nothing. So for a run of under, nothing, under, which counts 2, the rule underlines the no-decision day and the newest one and leaves out the older under day. A Level 1 fix, with its test shipped alongside; no canary source is under the mark, so no test saw it (Fowler, 2026-10-07).
  - The console home reads every day payload twice, through `publishedItems` and `publishedCharts`. Once row L13 lands, `publishedItems` and its new test can go (Fowler, 2026-10-07).
- **Acceptance gates:** local: the Oracle's two measurements, each over the ten specs on the base and on the branch, run with Playwright directly so that every red test is counted; `npm --prefix frontend run test:changed -- --list`, then the groups it selects for these files; `npm --prefix frontend run check`. CI: what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** the canary content change row L13 used (in `_health_rows()` of `backend/utilities/build_canary_day.py`, run 3 of 2026-08-20 of `canary-empty` answers 3 items instead of 0), and a canary-day move of 42 days or more (Table E, E10), each over the ten specs, on the base and on the branch. On the branch no rewritten test goes red, and each rewritten test goes red when one value in the root it builds changes. It cannot see, on the base, a test that works its answer out from the canary, because both measurements move its answer and its expected value together; that is why the 24 tests are named by reading each one, and why decision 7 adds a third measurement that can see them.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Split from L13 by the owner, 2026-10-07: L13's inventory counted 71 tests, over the owner's line of about 60. L14 takes the 21 tests that read the canary's own files, not through `canary-records.ts`, and the 3 that skip on what the canary holds. L13 keeps `canary-records.ts`, its 12 specs, `console.spec.ts`, `console-item-cost.spec.ts`, the console home route's server file and `frontend/scripts/test-groups.ts` | The owner, 2026-10-07 |
| 2 | The Oracle is row L13's content change and a canary-day move of 42 days or more, each run on the base and on the branch | The owner's dispatch note, 2026-10-07 |
| 3 | Level 2, as row L13 (its decision 5): tests, and a move of the retiring countdown out of the voices route that changes no canary page (decision 4) | The owner, 2026-10-07, for row L13 |
| 4 | The retiring panel (Fowler's option 1b). A browser test cannot hand the prerendered voices route a census, so `retiring()` moves out of the route in a structural commit, and the countdown's readout and the dwell rule's first column move into it in a second; on the canary the prerendered `/console/voices/` page is word for word and tag for tag the base build's. The three tests call it on a census they write. Their check that the newest days under the mark are drawn under it goes: the producer's `dwell()` owns that rule, and `backend/tests/test_source_dwell.py` holds it | Fowler, 2026-10-07 |
| 5 | The band's oracle (Fowler's option 2a). The band's producer works the articles-to-cap figure out and the page prints its sentence word for word, so the check moves to the producer's test, over manifests it writes: 107,232 articles, and "1.4 MB of the 1 GB limit - room for about 107,000 more articles.". `console-site-size.spec.ts` already checks the printed sentence's shape on any data | Fowler, 2026-10-07 |
| 6 | The other prerendered routes (Fowler's option 3a). Each browser test relates two things the page prints, and each reader the routes call with no logic test, `publishedItems` and `loadManifests`, gets one on a site the test builds. A cost-panel day with no count on the articles card fails the test rather than reading as zero. A top-band summary carrying no reason is `verdict()`'s rule, held by `backend/tests/pipeline/test_banding.py`; the run timeline's columns are a contract question, held by a binding test that every `TIMELINE_COLUMNS` entry is a `RunTimelineRow` field that is required and does not allow null | Fowler, 2026-10-07 |
| 7 | A third measurement beside the Oracle's two, in a throwaway checkout: after the build, the canary's own files are written again for a day 43 days later, and the site is served as built with the preview's input check off. A test that reads the canary's files then works its answer out for another day than the page shows. On the base the Oracle's two measurements turned none of the 24 tests red, and this one turned 14 red and no other test | Found during execution |
| 8 | Moving the readout into `retiring()` fixed a defect no canary page could show: a row under the mark printed "complete days.Under the mark" and "of 14.Retires on", because Svelte drops the space at the start of an `{#if}` block | Found during execution |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: the 21 tests keep working their answer out from the canary's own files, and the 3 keep skipping | Each of the 21 compares the page with an answer computed from data (Table D, D3), and the 3 never run | Nothing to build. A fault in a reader moves the page and the expected answer together, so no test turns red, and the countdown rows have no test at all | The owner, 2026-10-05 (Table D, D3) |
| 2 | Change the canary so that a source is under the mark, and the 3 skipping tests run on it | The plan changes the readers and the tests, never the data (Table A, A5), and the 3 tests would then depend on what the canary holds (Table D, D3) | One change to the canary's source census in `backend/utilities/build_canary_day.py`, and 3 tests that turn red when the census moves | The owner, 2026-10-05 (Table A, A5; Table D, D3) |
| 3 | Test `retiring()` alone and leave the readout and the dwell rule's place in the page (Fowler's option 1a) | Both are worked out in the page, so neither would have a test | Nothing beyond decision 4's first move, and two claims with no test | Fowler, 2026-10-07 |
| 4 | Move the retiring panel's markup into a component and render it in the test (Fowler's option 1c) | It moves about 250 lines, and styles the feeds panel shares, for three tests | A component, its styles, a browser smoke and every voices panel picture again | Fowler, 2026-10-07 |
| 5 | Serve built route data to the page through the client-side navigation's `__data.json` (Fowler's options 1d and 3c) | It ties the tests to SvelteKit's data format | `devalue` as a new dev dependency, and tests that break when SvelteKit changes how it writes route data | Fowler, 2026-10-07 |
| 6 | Keep a browser test of the band that serves a built `band.json` (Fowler's option 2b) | The page prints the payload's sentence word for word, so the test would check a copy and leave the arithmetic untested | One more browser test, and the figure still unchecked | Fowler, 2026-10-07 |
### Row #L15 - The held-part note says what its own two figures show

- **Scope:** The note under the console's item-cost section says that the held part of a prompt hardly changes only when its own two figures show it: the largest held count minus the middle one is under the middle one. When they do not, it says the held part moved inside the window. Level 1.
- **Follow-ups:**
  - The rule compares only the largest held count with the middle one, so it cannot see a step that fewer than half the items sit below; that is why the passing words claim nothing about change (row L15 report, 2026-10-07).
- **Files touched** (each path checked on `main` at 1414492d5):
  - `frontend/src/routes/console/+page.svelte` (prints the note, `data-item-cost-share-note`, with the middle and the largest held counts)
  - `frontend/src/lib/console/item-cost.ts` (`reusedMedian` and `reusedWidest`, the two figures the note reads)
  - `frontend/src/lib/console/held-part-note.ts` (new, found during execution: the rule and the note's words in one pure function, so a test pins the words on rows it builds and the page prints what it returns)
  - `frontend/tests/console-item-cost.spec.ts` (the Oracle; "the share is printed and never drawn as a trend, and the page says why" pins today's sentence)
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md` (the prompt-cache section, which holds the reading this row starts from)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-item-cost.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the console's home route. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** on rows the test builds (Table D, D3): a window whose middle item held 922 tokens and whose largest held 2,219 prints the moved sentence, and a window whose largest minus middle is under the middle prints today's sentence. It cannot settle the words, which Reader and Jony choose (decision 1); the test pins the words they choose.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader and Jony choose the note's words for both cases (CLAUDE.md section 14) | Reader and Jony, 2026-10-07; one wording split settled by responsibility: plain language is Reader's |
| 2 | The page checks the premise itself, on every build, for the window on screen, with one copy of the rule. No audit utility is built (row L13, decision 4) | The owner, 2026-10-07, after the audit's first reading (Fowler's option A5) |
| 3 | The evidence: the held part was 922 tokens every day to 2026-09-12 and about 1,800 to 1,940 from 2026-09-14. By the rule (the largest held count minus the middle one is under the middle one), the 30-day window ending 2026-10-06 passes, though it spans the 2026-09-13 step, so its note claims nothing about change; the 90-day window ending the same day fails (middle 922, largest 2,219), so its note says the amount changed a lot | Row L13's report, 2026-10-07; corrected from row L15's report, 2026-10-07 |
| 4 | L15 waits for L13, which edits the item-cost files and the pipelines route's page | The owner, 2026-10-07 |
| 5 | Level 1: the words of one note on one route; a wrong version shows on that route | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The note says the held part hardly changes on a window whose own figures say it moved: the 90-day window prints 922 and 2,219 today | Nothing to build, and a false note on every window that spans a step in the held part | Row L13's report; the owner, 2026-10-07 |
| 2 | An operator utility that checks the premise over a window a person names (row L13, decision 4, Fowler's option A3) | Once the note checks its own premise on every build, the utility is a second copy of the rule with no job left, so building it now and deleting it in this row is churn | A command a person runs, and no change to the page | The owner, 2026-10-07 |

### Row #L16 - The console's record notes on Hardware and Summaries say only what is true and on screen

- **Scope:** On Hardware and Summaries, the "Recording started" line names an instrument's first day only where the route's read holds the record's whole history and the open window shows that day, Summaries works out its recording lines once for each window, and Summaries prints its "Measurement is off" line whenever measurement is off. Level 2.
- **The four faults** (row L11's report, 2026-10-07):
  1. Summaries works out "Recording started on {day}" once over 90 days, so it can name a day that is off screen.
  2. Hardware dates "Recording started on {day}" from the first counter day inside the window, so it is false when recording started before the window.
  3. On Summaries, the "Measurement is off" line prints only when the widest window holds model data.
  4. The Hardware intro says "these 1 days". Moved to row L17 (owner, 2026-10-07).
- **Files touched** (each path checked on `main` at ac5817dc3, found by a search for `recordingNotes`, `RecordRead` and `startedMidWindow`):
  - `frontend/src/lib/console/recording.ts` (`RecordRead` carries `first`; `recordingNotes` takes the reads of the records an instrument draws on, the first day the facts cover and the open window, names only what the window shows, and dates a start only where the facts reach back to each record's first day; the started line's words)
  - `frontend/src/lib/server/ledger-rows.ts` (`windowRows` puts the reach's `first` on the read)
  - `frontend/src/routes/console/machine/+page.server.ts` (hands `recordingNotes` the whole read, for each span, with the machine and article records' reads for the counters and the machine record's for itself)
  - `frontend/src/routes/console/model/+page.server.ts` (works out the recording lines once for each window, with "quality figures")
  - `frontend/src/routes/console/model/+page.svelte` (prints the open window's recording lines after the record notes, in both branches)
  - `frontend/tests/console-chrome.spec.ts` (the started line's words and its rule, and where Summaries prints its recording lines)
  - `frontend/tests/ledger-rows.spec.ts` (the Oracle; each read carries `first`)
  - `frontend/tests/ledger-lifecycle.spec.ts` (the three expected reads in L5's window tests carry `first`, and nothing else changes; decision 4)
  - `docs/concepts/console-design.md`
  - `docs/architecture/publishing/console-payloads.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec ledger-rows.spec.ts --spec console-chrome.spec.ts --spec ledger-lifecycle.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the two pages; the browser smoke of Hardware and Summaries at each window preset, with both switches off for the smoke only, and with their records absent. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `ledger-rows.spec.ts`, on a site and a machine record the test builds (Table D, D3): a record that began 60 days before the newest published day, whose 14-day window starts with 6 quiet days, prints no "Recording started" line in the 1-, 7-, 14- and 30-day windows and names its own first day in the 90-day window, whether each window is handed the whole read or only its own days; a record that began 5 days before names that day in each window that holds it, and in no other; and an instrument whose rows begin after its record's names its own first day. On `main` the 14-day window says that recording started 7 days before the newest published day when handed its own days, and names 16 Apr, which it does not show, when handed the whole read. It cannot settle where Summaries prints its lines when it holds no model data, which the browser smoke shows, nor a record whose first month is packed (Table B, B2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four faults are row L11's findings, left for a row of their own | Found by row L11, owner 2026-10-07 |
| 2 | Fault 4 moves to row L17. Any words for the 1-day intro turn red the Machine oracle in `frontend/tests/console-window.spec.ts`, which L13 held: it requires each windowed surface to say `${preset} days` at every preset, 1 included | The owner, 2026-10-07 |
| 3 | The day a record began comes from its indexes, so nothing before the read is read: `first` on `RecordRead`, beside `lastRows`, the oldest day `readReach()` names. An instrument's first day is the first day it ran in what the route read, from its rows and its lost days, and it is known only where the `first` of every record the instrument draws on is on or after the first day the facts cover, `from` in `recordingNotes`. The line prints in each window that shows that day, and names it. `RecordRead` is a run-time answer, not a persisted shape, so Table C, C1 does not fire | The owner, 2026-10-07 (option B1); the read-wide rule, decision 8 |
| 4 | In `ledger-lifecycle.spec.ts`, only the three `expect(table.read).toEqual` objects in L5's window tests change, one key each | The owner, 2026-10-07 |
| 5 | The words are Reader's: "Recording started on {day}. Earlier in this window, {n} days had a run but no {figures}.", with "1 day had" for one. On Summaries {figures} is "quality figures": it fell back to "server figures", which is false of the checker. No sentence replaces the line where the record began before the window | Reader, 2026-10-07 |
| 6 | The place is Jony's: Summaries' recording lines move out of the "What the model did" section to just after the record notes, in both branches, in Hardware's order: off, sampled, started, counters-only | Jony, 2026-10-07 |
| 7 | Summaries' counters-only line is worked out once for each window too: over 90 days it could name days the open window does not show, as fault 1 did | Reader, found during execution, 2026-10-07 |
| 8 | `recordingNotes` is handed the whole read and `from`, the first day the facts cover, and names only what the open window shows, as `measurementOff` does. It reads a record's lost days from its read, so the route's second list of them goes. The first rule built, a start dated only where the record's indexes begin inside the open window, left Hardware's 30-day window on real data silent about the machine record, whose machine identity rows began on 17 Sep 2026, after the record itself; the browser smoke found it. A caller that hands only a window's days sets `from` to that window's first day, and gets that rule | Found during execution, 2026-10-07 |
| 9 | Level 2: the facts two routes hand their lines, a field every console read carries, and where one route prints four lines | Plan author, 2026-10-07 |
| 10 | The server's counters are formed from the machine record and the article record, a run from either, so their start is known only where both were read from their first days, and a day either record lost dates it. Gated on the machine record alone, Hardware would say "Recording started on 31 Aug 2026" once its read starts on 31 Aug or 1 Sep, for counters that began on 30 Aug: the machine record begins on 1 Sep and the article record in August | Found during execution, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Each of the three faults leaves a false line, or no line, on screen | Nothing to build, and a false or missing line on two routes | Row L11's report; the owner, 2026-10-07 |
| 2 | Carry the first day beside the read, on `LedgerTable` (option B2) | A record's facts from its indexes split between two objects, and each route reads both | No change in a file L12 held | The owner, 2026-10-07 |
| 3 | Each route reads the indexes a second time with `reachFromDisk()` (option B3) | Two reads of the same three files for each record, and a second door call that answers what the first one already answered | No change to `RecordRead` | The owner, 2026-10-07 |
| 4 | Date a start from the oldest period that holds rows, not from the oldest named day | A day the indexes name before the first row is a quiet day of a record that had begun ([console-design.md](../docs/concepts/console-design.md)), not a day before it began | A started line, dated by its rows, for a record whose first named days held no row | Plan author, 2026-10-07 |
| 5 | Name the record's first day from its indexes | After a record's first month closes, its index knows the month and not the day (Table B, B2), so the line could name the 1st of a month the record began later in | A started line in every window that holds the record's first named day | Plan author, 2026-10-07 |
| 6 | Keep the lines under the heading in both branches, or move only the off line (Jony's J2 and J3) | J2 pushes the section's lead away from its heading and leaves the two routes in two orders; J3 splits lines about one checker across a heading | J2: the lines stay inside the section they describe. J3: one line moves | Jony, 2026-10-07 |
| 7 | Date a start only where the record's indexes begin inside the open window (the first rule built) | It cannot see an instrument whose rows begin after its record's, so on real data Hardware's 30-day window lost a true line about the machine record | One fact fewer, `from`, and no line where an instrument began after its record and before the window | Found during execution, 2026-10-07 |

### Row #L17 - Every windowed console surface says "1 day" at the 1-day preset

- **Scope:** At the 1-day preset every windowed console surface says "1 day" in Reader's words, through one phrase helper, and the specs that pin a surface's day count accept it. Level 1.
- **Files touched** (found by a search on `main` at e32768441 for `data-windowed=`, for the day phrases those surfaces print, and for `${preset} days` in the specs; search again at dispatch):
  - `frontend/src/lib/charts/fleet.ts` (`spanWords`: "this one day", "these {n} days") and `frontend/src/lib/console/merge-line.ts` (`span`, its copy): one helper
  - `frontend/src/routes/console/machine/+page.svelte` (the intro: "No run in these 1 days committed a counters row.")
  - `frontend/src/routes/console/model/+page.svelte` (the cards: "the 1 days ending there")
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` ("over the last 1 days")
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/RunHealthPanel.svelte`, `frontend/src/routes/console/voices/+page.svelte`, `frontend/src/routes/console/judgement/RecordGates.svelte`, `frontend/src/routes/console/judgement/MergeLinePlot.svelte`, `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`, `frontend/src/routes/console/judgement/JudgeAgreement.svelte`, `frontend/src/lib/components/KpiCard.svelte`, `frontend/src/lib/components/Viewport.svelte`, `frontend/src/lib/components/FailurePanels.svelte`, `frontend/src/lib/components/BandDistance.svelte`, `frontend/src/lib/components/RunYield.svelte`, `frontend/src/lib/console/machine/ArticleCostPanel.svelte`, `frontend/src/lib/console/machine/ContextCostPanel.svelte`, `frontend/src/lib/console/machine/CounterfactualCostPanel.svelte`, `frontend/src/lib/console/machine/DiskReadsPanel.svelte`, `frontend/src/lib/console/machine/MemoryHeldPanel.svelte`, `frontend/src/lib/console/machine/ProcessorLostPanel.svelte`, `frontend/src/lib/console/machine/PromptReusePanel.svelte`, `frontend/src/lib/console/machine/ReadAgainstWrittenPanel.svelte`, `frontend/src/lib/console/machine/TailTrendPanel.svelte` (the other windowed surfaces)
  - `frontend/src/lib/console/doubt-reasons.ts`, `frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/console/completeness.ts`, `frontend/src/lib/console/waiting.ts`, `frontend/src/lib/charts/cost.ts`, `frontend/src/lib/charts/frame.ts`, `frontend/src/lib/charts/glance.ts` (sentences those surfaces print with the window's day count)
  - `frontend/tests/console-window.spec.ts` (its oracles require each windowed surface to say `${preset} days` at every preset, 1 included, and `machineSpan` reads the Hardware intro)
  - `frontend/tests/console-doubt.spec.ts`, `frontend/tests/console-item-cost.spec.ts`, `frontend/tests/console-model-panels.spec.ts`, `frontend/tests/console-model-reasons.spec.ts`, `frontend/tests/console-published.spec.ts` (each requires `${preset} days` at every preset)
  - `frontend/tests/merge-line.spec.ts`, `frontend/tests/platform-mix.spec.ts`, `frontend/tests/console-judgement-merges.spec.ts` (pin the helper's words or accept both)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; the browser smoke of every console route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on data the test builds (Table D, D3): each windowed surface reads "1 day" at the 1-day preset and "7 days" at the 7-day preset. It cannot settle a sentence that counts something other than the window's days, such as runs or days with rows.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fault 4 of row L16, moved here. It changes `console-window.spec.ts`, which L13 held, so it waits for L13. Since L13 (#1366), `console-article-cost.spec.ts` no longer reads the Hardware intro | The owner, 2026-10-07 |
| 2 | Reader chooses the words (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 3 | `spanWords` in `fleet.ts` and `span` in `merge-line.ts` fold into one helper, which every windowed surface uses | The owner, 2026-10-07 |
| 4 | Level 1: the words of sentences on four routes; a wrong version is obvious and local | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Fix only the Hardware intro, inside row L16 | The oracle in `console-window.spec.ts` requires every windowed surface to say `${preset} days` at the 1-day preset, so the intro alone turns it red, and every other surface keeps "1 days" | One sentence fixed, in a file L13 holds | The owner, 2026-10-07 (row L16's report) |
| 2 | As today | Every console route says "these 1 days", "over the last 1 days" or "the 1 days ending there" at the 1-day preset | Nothing to build | The owner, 2026-10-07 |

### Row #L18 - The console home reads each day payload once

- **Scope:** The console home opens each published day's payload once, through `publishedCharts`, and the articles card takes each day's count from that read, so `publishedItems` goes and the route opens half as many day payloads at build time. Level 2.
- **Files touched** (found by a search on `main` at 3f6440edb for `publishedItems`, the name this row deletes):
  - `frontend/src/lib/server/payload.ts` (`publishedItems` goes; the comment on `publishedCharts` says it is bounded the way `publishedItems` is)
  - `frontend/src/routes/console/+page.server.ts` (imports both readers, hands the page `publishedItems(undefined, widest)`, and hands `chartDays` the map `publishedCharts(undefined, widest)` returns)
  - `frontend/tests/console-published.spec.ts` (imports `publishedItems`; row L14's test "the articles a day published are read off its own payload, over the days the cover reaches"; the comment in "THE ORACLE: the articles card counts what the chart table says each day published" names the two readers)
  - `frontend/tests/console.spec.ts` (not found by the search: the test of `publishedCharts`, "a visual that never drew is a visual and is not a published chart", beside which row L14's days and windows move; decision 4)
  - `docs/concepts/growing-reads.md` (the `payload.publishedItems` line of its table of reads)
  - `docs/architecture/publishing/console-payloads.md` (the `Published items` line names `publishedItems` as the reader it replaces, and a paragraph names three reads off the run-day row)
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md` (says a route walks `DIGEST_ROOT` the way `publishedItems` does)
  - `backend/idhazh/contracts/console_payloads.py` (the entry whose reader is `payload.ts publishedItems()`; decision 5)
  - `backend/idhazh/contracts/public_run_day.py` and `backend/idhazh/telemetry/publish/run_days.py` (each module's docstring names three reads; decision 5)
  - Left as they are: `frontend/src/routes/console/+page.svelte`, which reads the key the route keeps (decision 3); `frontend/tests/empty-day.spec.ts`, whose helper of the same name reads the canary day and imports nothing from `payload.ts`; `TODO/20260926-52-fifty-panels-move-and-six-projections-go-plan.md`, `TODO/20260906-data-growth-research.md` and row L14 of this plan, which record what was true when each was written
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-published.spec.ts --spec console.spec.ts`; `npm --prefix frontend run check`; ruff, mypy and the backend tests that `test:changed -- --list` selects for the three Python files; `doc_load.py` on the three pages; the browser smoke of the console's home route. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console.spec.ts`, on a published site the test builds (Table D, D3): three days that published 4, 0 and 2 articles. Over a 3-day window that ends on the newest published day, `publishedCharts` gives each day's count, the day with none as 0; over a 2-day window it never opens the oldest day. It cannot settle that the route hands the articles card those counts; "THE ORACLE: the articles card counts what the chart table says each day published" relates the card to the table on the page.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The articles card takes each day's count from the map `publishedCharts` returns, which the route already reads for `chartDays`, so each day payload of the widest window is opened once, not twice | Rows L13 and L14 reports; the owner, 2026-10-07 |
| 2 | The count comes from that map and not from `charts`: `chartDays` gives a day whose payload did not load 0 items (`frontend/src/lib/server/chart-days.ts`), while the map leaves that day out, as `publishedItems` did, and a day with no count stays absent rather than reading as zero (row L14, decision 6) | Plan author, 2026-10-07 |
| 3 | The route keeps the name of the key it hands the page, `publishedItems`, so `frontend/src/routes/console/+page.svelte`, which row L17 also edits, does not change | Plan author, 2026-10-07 |
| 4 | Row L14's test of `publishedItems` goes with the function. Its three days and two windows move beside the test of `publishedCharts` in `console.spec.ts`, so the reader the articles card now uses keeps a test of how far back it reads and of a day that published nothing (row L14, decision 6) | Plan author, 2026-10-07 |
| 5 | `console_payloads.py` is an index and never a shape, as its own docstring says, and the other two Python files change only in their docstrings, so Table C, C1 does not fire | Plan author, 2026-10-07 |
| 6 | L18 waits for L13, which moved `chartDays` out of the route: row L14's report said `publishedItems` and its test can go once L13 lands | Fowler, 2026-10-07 (row L14's report) |
| 7 | Level 2: one reader goes, and the articles card and the per-article cost depend on the count it gave | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: `publishedItems` and `publishedCharts` each open every day payload of the widest window | Two readers open the same file to take the same count | Nothing to build, and twice the day-payload reads the route needs at build time | Rows L13 and L14 reports; the owner, 2026-10-07 |
| 2 | Take the count off `charts`, the list the page already receives, and hand the page no second map | A day whose payload did not load would read as 0 articles (decision 2) | One map fewer in the page's data, and a change to `+page.svelte` | Plan author, 2026-10-07 |

### Row #L19 - console-mark-parity's skipped test checks data it builds

- **Scope:** The swap chart's case in `console-mark-parity.spec.ts`, "swap dots: the drawn marks survive a window change and a resize", checks a swap the test builds, and no longer skips because the canary holds no model change. Level 1.
- **Files touched** (found by a search on `main` at 3f6440edb for `test.skip` in the spec, for `data-swap-domain`, and for the helpers that build and render a swap in `console-model-panels.spec.ts`):
  - `frontend/tests/console-mark-parity.spec.ts` (the case skips where the canary holds no model change; the file's header and the `optional` field's comment say why)
  - `frontend/tests/console-model-panels.spec.ts` (`swapFixture()` builds a swap from rows the test writes, and `renderSwap()` renders `SwapDots.svelte` on it; both move to the support file, decision 2)
  - `frontend/tests/support/model-swap.ts` (new: the swap both specs build and render; decision 2)
  - Left as it is: `frontend/src/lib/components/SwapDots.svelte`, which publishes `data-swap-domain` and which the case renders
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-mark-parity.spec.ts --spec console-model-panels.spec.ts`; `npm --prefix frontend run check`. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-mark-parity.spec.ts`, on a swap the test builds (Table D, D3): `SwapDots.svelte`, rendered at the spec's two widths, `WIDE` and `NARROW`, publishes the same `data-swap-domain` and the same marks at both, and a swap built from other rows, standing for the other window, publishes an extent too. The case never skips. It cannot settle the live resize, because a server render draws once; that stays with the other five charts, which draw on the canary.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No row named this skip: rows L13 and L14 took the console tests that skip on what the canary holds, and this one was left | Row L13's report; the owner, 2026-10-07 |
| 2 | The case renders `SwapDots.svelte` on a swap built from rows the test writes, as `console-model-panels.spec.ts` has since L13 (#1366). `swapFixture()`, `renderSwap()` and the helpers that write their rows move to `frontend/tests/support/model-swap.ts`, so the two specs share one swap rather than two copies of it | Plan author, 2026-10-07, from row L13 |
| 3 | L19 waits for L13, which built the swap that `console-model-panels.spec.ts` renders | The owner, 2026-10-07 |
| 4 | Level 1: one test case and its test support; a wrong version is obvious and local | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today: the case skips on the canary | It never runs, so nothing checks the swap chart's extent across a resize or a window change | Nothing to build, and a case that passes by never running | Row L13's report; the owner, 2026-10-07 |
| 2 | Delete the case, because `console-model-panels.spec.ts` already builds a swap | That spec checks the swap panel's layout, and no other test reads `data-swap-domain` | One case fewer, and no test of the extent `SwapDots.svelte` publishes | Plan author, 2026-10-07 |
| 3 | Change the canary so that its ledger holds a model change | The plan changes the readers and the tests, never the data (Table A, A5), and the case would then depend on what the canary holds (Table D, D3) | One change to the canary's rows in `backend/utilities/build_canary_day.py`, and a case that turns red when they move | The owner, 2026-10-05 (Table A, A5; Table D, D3) |
| 4 | Copy the swap's rows and its render into `console-mark-parity.spec.ts` | Two copies of one fixture drift apart, and a change to the swap must be made twice | No support file, and the swap written twice | Plan author, 2026-10-07 |

### Row #L20 - The dwell rule is placed right when a day that decided nothing sits inside the run

- **Scope:** On the voices route's retiring strip, the dwell rule - the line under the days a source has run under the mark - starts at the oldest day under the mark in the run the producer counted, so a day that decided nothing inside the run no longer pushes a day under the mark out from under it. Level 1.
- **Files touched** (found by a search on `main` at 3f6440edb for `dwellFrom` and `daysUnder`):
  - `frontend/src/lib/server/source-retiring.ts` (`dwellFrom` is `dates.length - daysUnder + 1`)
  - `frontend/tests/console-voices-retiring.spec.ts` ("the dwell is an area under the newest squares, not a number in a chip"; no day of its census decided nothing)
  - `docs/concepts/console-design/what-the-quality-and-source-panels-draw.md` ("The dwell is the area" says the rule sits under exactly the contiguous under-the-mark squares at the newest end)
  - Left as they are: `frontend/src/routes/console/voices/+page.svelte`, which draws the rule from `dwellFrom` and prints `daysUnder`; `frontend/tests/staged-day.spec.ts`, whose helper of the same name, `daysUnder()`, lists a tree's days; `backend/idhazh/telemetry/publish/source_health.py`, whose `dwell()` counts the run, and `backend/tests/test_source_dwell.py`, which holds that count
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-voices-retiring.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the console's voices route. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-voices-retiring.spec.ts`, on a census the test writes (Table D, D3): a source whose newest three days are under the mark, a day that decided nothing, and under the mark again, which the census counts as 2 days under, is underlined from the first of those three columns. A source whose newest three days are all under the mark is underlined from the first of them, as today. On `main` the first source is underlined from the second of the three, which is what lets this check fail. It cannot settle the count itself, which the producer's `dwell()` owns and `backend/tests/test_source_dwell.py` holds.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault: the rule starts at column `dates.length - daysUnder + 1`, but the producer's `dwell()` counts through a day that decided nothing. So for a run of under, nothing, under, which counts 2, the rule underlines the no-decision day and the newest one and leaves out the older under day. No canary source is under the mark, so no test saw it | Fowler, 2026-10-07 (row L14's report) |
| 2 | The rule's first column is the run's oldest square under the mark: walking back from the newest square, it passes `daysUnder` squares under the mark and every square between them that decided nothing. It counts no run of its own, because `retiring()` re-derives nothing the run decided (its header; row L14, decision 4). `dwell()` counts over the same dates the strip draws, so the walk ends inside the strip | Plan author, 2026-10-07 |
| 3 | The fix ships with its test, on a census the test writes | Fowler, 2026-10-07 (row L14's report) |
| 4 | L20 waits for L14, which moved `retiring()` out of the voices route and wrote the census its tests read | The owner, 2026-10-07 |
| 5 | Level 1: where one line starts on one panel; a wrong version is obvious and local | Fowler, 2026-10-07 (row L14's report) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The rule leaves out a day under the mark and underlines a day that decided nothing, so the picture disagrees with the count printed beside it | Nothing to build, and a wrong rule whenever a day that decided nothing sits inside a run | Fowler, 2026-10-07 (row L14's report) |
| 2 | The producer publishes the first day of each source's run on the census, and the page draws from it | It changes a persisted shape, `SourceHealthView` in `backend/idhazh/contracts/source_health_view.py` (Table C, C1), to place a line the page can place from squares it already holds | A Level 5 change in two commits, reader first (CLAUDE.md section 11): a new field with a new version and changelog line, and its frontend copy in `frontend/src/lib/server/payload.ts` | Plan author, 2026-10-07 |
| 3 | The page counts the run from the squares itself and ignores `daysUnder` | A count the page works out again is a second verdict, which can disagree with the countdown beside it (`retiring()`'s header) | No use of the producer's count, and two counts of one run | Plan author, 2026-10-07 |

### Row #L21 - The data explorer's action line counts the days a run will read

- **Scope:** Before a run, the data explorer's action line - the line that prices a run before it fetches anything - counts the days the run will read, not the days of the window. Level 2.
- **Files touched** (found by a search on `main` at 3f6440edb for "Run reads", `statusSentence` and `spanDays`; search again at dispatch, after #1357 merges):
  - `frontend/src/lib/console/explorer/status.ts` (`statusSentence`, state `idle`: "Run reads {files}, {size} from {ledgers} over {days} UTC days.")
  - `frontend/src/routes/console/data-explorer/+page.svelte` (`statusLine()` hands that sentence `days: spanDays()`, the window's days)
  - `frontend/src/lib/data/slice-shapes.ts` and `frontend/src/lib/data/ask-reader.ts` (only if `SpanCost.cut` must carry more than each cut ledger and the day its answer starts; decision 3)
  - `frontend/tests/console-data-explorer-still.spec.ts` (pins the words of the `idle` sentence, and reads "Run reads" on the page)
  - `frontend/tests/console-data-explorer.spec.ts` (the Oracle, on roots built with `frontend/tests/support/ledger-lifecycle.ts`)
  - `docs/how-to/query-a-ledger-from-the-console.md` (says what the action line prices)
  - Left as they are: `frontend/scripts/published-ledgers.mjs`, whose `spanDays` is the site copy's own parameter; `TODO/20260928-55-one-page-queries-every-ledger-plan.md`, which declares the action line's words (decision 4)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-data-explorer.spec.ts --spec console-data-explorer-still.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the data explorer. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-data-explorer.spec.ts`, on ledgers the test builds (Table D, D3): one ledger built to begin 5 days before the end of a 14-day window. Before the run, the action line counts the 5 days the run will read; on `main` it counts the window's 14, which is what lets this check fail. A second case adds a ledger built to begin 4 years before, and the line says what Reader rules for two ledgers that read different days. It cannot settle the words, which Reader chooses (decision 1); the test pins the words Reader chooses.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words, and how the line counts when the selected ledgers read different days (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 2 | The fault: the line before a run, "Run reads ... over {n} UTC days.", counts the window's days, not the days each ledger will read. So for one question it can count days that the line under the answer, which counts the days read since L12, does not | Row L12's report; the owner, 2026-10-07 |
| 3 | The count comes from `SpanCost`, which the page asks for before every run. Its `cut` names each selected ledger cut from the window and the day that ledger's answer starts, and it can carry the days each ledger will read (row L12's report). That is a field of a run-time answer, not a persisted shape, so Table C, C1 does not fire | Row L12's report; plan author, 2026-10-07 |
| 4 | L21 waits for plan 55's row "The Data explorer reaches the reference's density" (#1357), which reshapes the data explorer page and edits `status.ts`, `+page.svelte` and both explorer specs this row edits. The Depends-on cell names that row by number so that the plan reader holds L21; check its title again at dispatch. Plan 55 declares the action line's words too, so coordinate with plan 55's owner session before dispatch | The owner, 2026-10-07 |
| 5 | Level 2: the line before every explorer run changes, and every run is priced through `SpanCost` | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | For a ledger that began inside the window, the line counts days before it began, which the run does not read | Nothing to build, and a line that overstates what a run reads whenever every selected ledger began inside the window | Row L12's report; the owner, 2026-10-07 |
| 2 | Build L21 now, beside #1357 | Both change `status.ts`, the page and its two specs, and #1357 reshapes the page this line sits on, so one of the two would be written again | The fix sooner, and the line written a second time after #1357 merges | The owner, 2026-10-07 |

### Row #L22 - Summaries' one-sided lines say what is true

- **Scope:** The two lines that say only one record answered for a day - on Summaries, server counters with no score; on Hardware, a score with no server counters - say only what is true of the days the open window shows. Level 1.
- **The three faults** (row L16's report, 2026-10-07):
  1. Both lines say "this day", but each prints once for a window and speaks for every such day in it.
  2. On Summaries, "Nothing scored the summaries" prints for a day the score record lost, because a timed day with no score row counts as a day nothing scored.
  3. On Hardware, "The summaries were scored" is decided from the article record, which has a row for every run, so it can print for a day nothing scored.
- **Files touched** (found by a search on `main` at 3f6440edb for `countersWithoutScores`, `scoresWithoutCounters`, `countersOnly` and `coveredElsewhere`):
  - `frontend/src/lib/console/recording.ts` (`countersWithoutScores()` and `scoresWithoutCounters()` hold the two lines; `recordingNotes` decides the Hardware line from `coveredElsewhere`)
  - `frontend/src/routes/console/model/+page.server.ts` (`countersOnly`: a timed day in the window that is not a scored day; fault 2)
  - `frontend/src/routes/console/machine/+page.server.ts` (hands `coveredElsewhere` the article record's days, `healthDays`; fault 3)
  - `frontend/tests/console-chrome.spec.ts` ("the two one-sided days each name which instrument answered" pins both lines' words; "a day another instrument covered is named, not drawn as a quiet day")
  - `docs/concepts/console-design.md` (names the six states with fixed wording, these two among them, and who chose each one's words)
  - Left as they are: `frontend/src/routes/console/model/+page.svelte` and `frontend/src/routes/console/machine/+page.svelte`, which print the two lines as the routes hand them
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-chrome.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of Hardware and Summaries at each window preset. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console-chrome.spec.ts`, on facts the test builds (Table D, D3), with the server's counters written every day. A window whose only day without a score row is one the score record lost prints no line saying nothing scored the summaries; a window with two days the scorer did not run prints that line, and it does not call them "this day". On Hardware, a day the article record holds, with no score row and no counters row, gets no line that says the summaries were scored. It cannot settle the words, which Reader and Jony choose (decision 2); the test pins the words they choose.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The three faults are Reader's findings in row L16, left for a row of their own | Reader, 2026-10-07 (row L16's report) |
| 2 | Reader and Jony choose the words of both lines (CLAUDE.md section 14) | To be ruled at dispatch (Reader and Jony) |
| 3 | Summaries' line is worked out in `recording.ts` from the facts the route hands it, as the Hardware line already is, so a test can hand it facts it builds: a `+page.server.ts` may export nothing else, so nothing in it can have a logic test (row L13) | Plan author, 2026-10-07 |
| 4 | Fault 3 is fixed either by Hardware reading which days the score record holds, or by a line that claims no score. Fowler rules which, because the first adds a read of the score record to the Hardware route | To be ruled at dispatch (Fowler) |
| 5 | L22 waits for L16, which changed what the two routes hand `recordingNotes` and where Summaries prints its recording lines | The owner, 2026-10-07 |
| 6 | Level 1: the words of two lines and the facts two routes hand them; a wrong version shows on those two routes | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Each fault leaves a false line on screen | Nothing to build, and a false line on two routes whenever a window holds two or more one-sided days, a lost score day, or a day with articles and no counters | Reader, 2026-10-07 (row L16's report) |
| 2 | Drop the two lines | A one-sided day would read as a full day or a quiet one, which these lines exist to stop (`docs/concepts/console-design.md`) | No words to choose, and a reader who cannot tell why a day has speed figures and no quality figure, or the reverse | Plan author, 2026-10-07 |

### Row #L23 - The pipelines route's page and the prompt-cache subtitle say what is drawn

- **Scope:** The pipelines route's page names the Hardware panel by the title it carries and says how that panel draws, its prompt-cache section says the share is printed and not drawn, and the prompt-cache panel's subtitle says nothing its own figures contradict. Level 1.
- **The three faults** (row L15's report, 2026-10-07):
  1. `docs/architecture/publishing/what-the-pipelines-route-draws.md` names a Hardware panel "How much text the model has to read again each time", drawn one column a day. The Hardware route now draws "How much text the model reads again, and how fast it reads" (`frontend/src/lib/console/machine/PromptReusePanel.svelte`), as spans with no day axis.
  2. The same section says "The share is drawn, and it is named in words beside it", which its own heading contradicts: the share is printed rather than drawn.
  3. The panel's subtitle says the instructions in front of every article "stay in memory between items", but 16.7 percent of items over the 90-day window, and 29.8 percent over the 1-day window, had nothing in memory.
- **Files touched** (found by a search on `main` at 3f6440edb for the old title, "stay in memory between items" and "The share is drawn"):
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md` (its prompt-cache section; faults 1 and 2)
  - `docs/architecture/publishing/console-machine.md` (its table of Hardware panels names the old title, drawn one column a day; found by the search, not named in row L15's report)
  - `docs/architecture/publishing/telemetry-series.md` (its table of figures names the old title; found by the search, not named in row L15's report)
  - `frontend/src/routes/console/+page.svelte` (the panel's `note`, its subtitle; fault 3)
  - `frontend/src/lib/console/prompt-cache-subtitle.ts` (new: the subtitle's words for one window; decision 2)
  - `frontend/tests/console-item-cost.spec.ts` (the Oracle)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-item-cost.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the three pages; the browser smoke of the console's home route. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console-item-cost.spec.ts`, on rows the test builds (Table D, D3): a window in which 1 of 4 items read its prompt whole, which today's subtitle misdescribes, and one in which no item did. The test pins the words the subtitle's function returns for each, and neither says anything the window's own count of items read whole contradicts. It cannot settle the three pages, which no test reads; review reads each against `PromptReusePanel.svelte` and the section's own heading.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the subtitle's words (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 2 | The subtitle's words come from one pure function of the window's `ItemCost`, in `frontend/src/lib/console/prompt-cache-subtitle.ts`, and the page prints what it returns, as the note under the share has since L15 (#1368). So a test pins Reader's words on rows it builds | Plan author, 2026-10-07, from row L15 |
| 3 | The three faults are row L15's findings. The search for the old title found two more pages that name it, `console-machine.md` and `telemetry-series.md`, so this row corrects all three pages | Row L15's report; plan author, 2026-10-07 |
| 4 | L23 waits for L15, which edited the note under the share, the home route's page and the prompt-cache section | The owner, 2026-10-07 |
| 5 | Level 1: the words of one subtitle on one route, and three pages; a wrong version is obvious and local | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The page names a Hardware panel that is not drawn, says the share is drawn under a heading that says it is not, and the subtitle says every article's instructions stay in memory while the panel prints how many items had nothing in memory | Nothing to build, and three pages and one subtitle that a reader can check and find false | Row L15's report; the owner, 2026-10-07 |
| 2 | Change the words in the page, with no function | No test can read them without the canary's page, so their test would rest on what the canary holds (Table D, D3), or they would have none | One file fewer, and words no test pins | Plan author, 2026-10-07 |
