# Plan 62 - Ledgers that start, pause, resume and stop

**Last Updated**: 2026-10-08

**Level**: 3 (CLAUDE.md section 6). L1 and L5 cross a boundary: L1 joins the site build to the data explorer, and L5 changes how every console route places its window. No row changes a persisted shape, and Table C, C1 stops any row that would.

**Status**: written 2026-10-05 from Fowler's proposal and his revision of the same day, and from the owner's rulings on them (Table D). Checked against `main` at 36fe716e0. L1 merged under plan 60 as #1327 (row L1, decision 5). The owner ruled that the plan 60 owner session runs this plan after L1 merges (Table D, D4). An id such as "Fowler's option M3" names a row of those two documents, which are not in the repository.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Ledgers start, pause, resume and stop. Since #1309 a ledger's index starts on its first raw day, but the readers treat a day before a ledger began as a day that is missing: the data explorer asks the archive for it and then reports a fault. The tests hid this until #1309, because the canary began every ledger on the 1st of a month and the browser answer key read other inputs than the page. Now ten browser tests fail on `main` (run 37361239642, 2026-10-05). This plan makes every reader and every test treat each stage of a ledger's life as normal |
| A2 | Hard scope - in | - The data explorer leaves out a ledger's days before its first day and names that day, and it asks the archive only for days the site copy trimmed (L1).<br>- Every data explorer browser test serves data it built and checks written-out results. The canary keeps only the checks that do not depend on what it holds (L2).<br>- The real compaction is tested on each lifecycle state, and the states get a page of their own (L3).<br>- A panel slice leaves out the days before a ledger began and names its first day. How far a ledger is packed comes from all three indexes (L4).<br>- Every console window ends on the site's newest published day, reads exactly that window, and says when a record's rows stop (L5).<br>- A published ledger that has no compact folder yet does not stop the site build (L7).<br>- When the archive does not answer for trimmed days, the explorer answers the site's days and names the archive (L8).<br>- Console specs outside the explorer that read canary content serve the data they check (L9).<br>- When a chosen ledger's newest named day holds no rows, the data explorer's column rail still lists its columns (L10).<br>- The "Measurement is off" line names no day outside the window, and says that nothing has been recorded at all only for a record that never held a row (L11).<br>- The data explorer's span sentences count the days read, give every date its year, and name each ledger with its own first day (L12).<br>- The console specs that still work their answer out from the canary, or write out its figures, serve the data they check (L13)<br>- The console specs that work their answer out from the canary's own files, or skip on what it holds, serve the data they check (L14)<br>- The note under the item-cost section says the held part of a prompt hardly changes only when its own two figures show it (L15)<br>- On Hardware and Summaries, the "Recording started" line names a start only where it is known and on screen, Summaries works out its recording lines for each window, and its "Measurement is off" line prints whenever measurement is off (L16)<br>- Every windowed console surface says "1 day" at the 1-day preset (L17)<br>- The console home opens each published day's payload once, and the articles card takes its count from that read (L18)<br>- The swap chart's case in the console's mark-parity test checks a swap the test builds, instead of skipping because the canary holds no model change (L19)<br>- The dwell rule on the retiring strip starts at the oldest day under the mark in the run, so a day that decided nothing inside the run leaves no such day out (L20)<br>- Before a run, the data explorer's action line counts the days the run will read, not the days of the window (L21)<br>- On Summaries and Hardware, the lines for a day that only one record answered say only what is true of the days the window shows (L22)<br>- The pipelines route's page names the Hardware panel as it is drawn now and says the share is printed, and the prompt-cache subtitle says nothing its own figures contradict (L23)<br>- The bundle gate reports the index key of a published ledger that is not packed yet as not weighed, and names the ledger, while every other payload key that names nothing still fails (L24)<br>- Hardware's platform-mix panel no longer says that a published machine record that is not packed yet has not been published (L25).<br>- Every console sentence reads right at the one-day window, including the ones that print no day count today (L26).<br>- Judgement's windowed surfaces name their span at every preset (L27)<br>- On Hardware, a run made of article rows alone is no longer counted or dated as one that committed the server's own counters, a failed read of the score record is named instead of dropping the change markers with no note, and the server's counters no longer take the scorer's sampling rate (L28).<br>- Hardware's refused-runs box says what reads a refused run, once a measurement shows whether its words are true (L29).<br>- With no fitted day in the window, the merge line's dashed rule and its label name the line a build used (L30).<br>- When the window holds no row of the record, Judgement's record panel says so instead of drawing three bars at zero (L31).<br>- Judgement's agreement strip prints no share for a day that read too few pairs for one (L32).<br>- Every sentence for a published record or ledger that the door answers `missing` says it is not packed yet, never that it is not published (L33).<br>- At the 1-day window, Voices' two record strips, Hardware's processor-lost strip, the stage timings note on Pipelines, the titles and the cost switch that say "day by day", and two notes on Judgement that speak of lines read right, in Reader's words (L34).<br>- On Pipelines, "What is failing, by stage" and "Where an item's time went" follow the window or say on the page why not, as Jony rules (L35).<br>- On Hardware, the line that says no server figures were written down names no day whose only run the counters refuse while its machine records hold server figures (L36).<br>- The cost of one article on Hardware no longer takes a refused shard's processor count from whichever of its two machine records comes last, once a measurement shows that it does (L37).<br>- Judgement's verdict split and holdout margin take the line a build used, from the one rule row L30 built for the merge line (L38).<br>- On Judgement's agreement panel, "could not tell" is counted against the pairs whose two readings agreed, in the strip and in the sentence (L39).<br>- On Judgement's agreement chart, a day that read fewer pairs than `console.min_attempts_for_rate` is not drawn at its shares' heights, as Jony rules (L40).<br>- After a move between console routes by a tab, the days control shows the window the panels draw (L42).<br>- Every console route sets its own page title, in Reader's words (L43).<br>- Judgement reads every fitted-line and holdout day the council commits once neither read takes its days from the publication inventory: #1352 moved the holdout read, and plan 59's row "The fitted merge line is saved through the door" moves the fitted-line read, so L44 changes no file (L44).<br>- On Judgement, the merge line's held note, the record's sentence while it fills, and the merge line strip's resting heading agree with the days and counts the page draws, in Reader's words (L45).<br>- On Hardware, the started line counts a day whose only run is a refused run of machine records alone, once a measurement shows that it leaves such a day out (L47).<br>- The Data explorer's line under an answer ends on the last day the explorer read, not on the window's last day (L48).<br>- Every console route asks search engines not to list it (L49).<br>- Two console tests prove what they claim (L50).<br>- Judgement's agreement panel words follow the rates they judge (L51). |
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
| B7 | Specs outside the console that compute their answer from data, such as `frontend/tests/ledger-ranges.spec.ts`, which takes its expected slice from the disk reader. `frontend/tests/published-ledgers.spec.ts` is one more: it expects every published ledger's three indexes in the canary build, and it passes today only because the canary packs all seven published ledgers, so a published ledger the canary does not pack would read there as a fault (row L7's report). The test "raw-day listings are complete, bounded and become the baked listed-through value" in `frontend/tests/published-ledgers.spec.ts` never calls `rawListedThrough` the way the build does, with no argument from `frontend/`, so it could not see row L46's fault (row L46's report, 2026-10-08) | They break Table D, D3 until a row rewrites them, and a producer change can still turn one red after a merge | L9's inventory, run over the `reader`, `archive`, `publishing` and `model-search` groups, as a row of its own |
| B8 | Panels that mark the days packing has not reached. Susan and Jony accept a hairline outline on bar and strip panels. Two points are open: whether a panel whose whole window is not packed shows one line ("6 Oct 2026 is not packed yet.") or nothing, and whether line-chart readouts say "not packed yet" | On bar and strip panels those days look like quiet days, and only the route's note says otherwise: the `behind` note, or the quietest line when packing is one day short. The design rationale of `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` records the gap | An owner decision on the two open points, then a Level 1 row with Susan's, Jony's and Reader's rulings (row L5's report) |
| B9 | Naming a hole in the archive's indexes as the archive's (since L8 the explorer calls the archive the repository) | The hole stays `day-missing`, and the page says "No file on this site holds {ledger} for {day}.", which blames the site | A Level 2 row that puts the tier on the `unreachable` answer in `frontend/src/lib/data/slice-shapes.ts`. That is a field of the run-time answer, not a persisted shape, so Table C, C1 does not fire (row L8's report) |
| B10 | Listing the columns of a published ledger that has no file on the site: `candidate-models` once its September 2026 month packs as `empty`, with no file, and a ledger whose writer's last rows are older than the days the site copy keeps (Table E, E4) | The column rail lists no column for such a ledger | A row of its own when the first family is paused or retired. Reading the archive for such a ledger costs 3 index reads and 1 whole file (row L10's report; Fowler, 2026-10-07) |
| B11 | A sentence on Hardware's two change-marker charts for a day that published no digest. The line those charts print when the score read did not read ends "This chart shows every change on the other days.", and that also covers such a day: 19 Sep 2026 on the real records, where a change could show only on the next published day, 20 Sep. Fowler put it out of row L28's scope as a limit of the markers (row L28's report) | The change still shows, on the next published day, so no change is lost. A reader who looks for one on the day that published nothing finds it on the next published day instead, and the line prints only while the score read did not read | A Level 1 row of its own, with Reader's words for such a day |

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
| L3 | Lifecycle states at the producers | L1 | B | DONE | super-waffle | #1375 | Plan 62 row l3 |
| L4 | A slice cuts only the days before a ledger began | L1 | B | DONE | fluffy-couscous | #1348 | Plan 62 row l4 |
| L5 | Console windows end on the site's newest published day | L4 | C | DONE | solid-potato | #1353 | Plan 62 row l5 |
| L7 | A published ledger that has not started | L1 | B | DONE | expert-pancake | #1370 | Plan 62 row l7 |
| L8 | The archive's failures are named as the archive's | L1, L2, L4, L5 | C | DONE | jubilant-dollop | #1358 | Plan 62 row l8 |
| L9 | Console specs outside the explorer serve the data they check | L2 | C | DONE | special-robot | #1361 | Plan 62 row l9 |
| L10 | The column rail describes a ledger whose newest day holds no rows | L8 | C | DONE | redesigned-spork | #1360 | Plan 62 row l10 |
| L11 | The "Measurement is off" line names only a day that is on screen | L5 | D | DONE | reimagined-happiness | #1363 | Plan 62 row l11 |
| L12 | The data explorer's span sentences say what each ledger read | L10 | D | DONE | miniature-journey | #1364 | Plan 62 row l12 |
| L13 | The remaining console specs check data they build | L9 | D | DONE | curly-umbrella | #1366 | Plan 62 row l13 |
| L14 | Console specs that work their answer out from the canary's own files check data they build | L9 | D | DONE | glowing-waddle | #1365 | Plan 62 row l14 |
| L15 | The held-part note says what its own two figures show | L13 | E | DONE | fuzzy-goggles | #1368 | Plan 62 row l15 |
| L16 | The console's record notes on Hardware and Summaries say only what is true and on screen | L11 | D | DONE | supreme-journey | #1367 | Plan 62 row l16 |
| L17 | Every windowed console surface says "1 day" at the 1-day preset | L13 | E | DONE | probable-umbrella | #1374 | Plan 62 row l17 |
| L18 | The console home reads each day payload once | L13 | F | DONE | fluffy-carnival | #1396 | Plan 62 row l18 |
| L19 | console-mark-parity's skipped test checks data it builds | L13 | F | DONE | super-spork | #1391 | Plan 62 row l19 |
| L20 | The dwell rule is placed right when a day that decided nothing sits inside the run | L14 | F | DONE | reimagined-doodle | #1371 | Plan 62 row l20 |
| L21 | The data explorer's action line counts the days a run will read | plan 55 row #10 | F | PENDING | - | - | - |
| L22 | Summaries' one-sided lines say what is true | L16 | F | DONE | fuzzy-meme | #1385 | Plan 62 row l22 |
| L23 | The pipelines route's page and the prompt-cache subtitle say what is drawn | L15 | F | DONE | fuzzy-winner | #1381 | Plan 62 row l23 |
| L24 | The bundle gate does not fail a published ledger that is not packed yet | L7 | G | DONE | supreme-eureka | #1376 | Plan 62 row l24 |
| L25 | Hardware's platform-mix panel says the machine record is not packed yet | L7, L17 | G | DONE | fantastic-giggle | #1384 | Plan 62 row l25 |
| L26 | Every console sentence reads right at the one-day window | L17, L23 | G | DONE | studious-goggles | #1400 | Plan 62 row l26 |
| L27 | Judgement's windowed surfaces name their span | L17 | G | DONE | vigilant-sniffle | #1388 | Plan 62 row l27 |
| L28 | Hardware's notes say only what its records hold | L22 | H | DONE | studious-carnival | #1401 | Plan 62 row l28 |
| L29 | Hardware's refused-runs box says what reads a refused run | L22 | I | DONE | special-parakeet | #1412 | Plan 62 row l29 |
| L30 | The merge line's no-fit rule names the line a build used | L27, L26 (holds `frontend/tests/console-window.spec.ts`) | H | DONE | fluffy-dollop | #1408 | Plan 62 row l30 |
| L31 | The record's bars say when a window holds no row | L27, L26 (holds `frontend/tests/console-window.spec.ts`) | I | DONE | probable-journey | #1414 | Plan 62 row l31 |
| L32 | Judgement's agreement strip prints no share below five pairs | L27, L26 (holds `frontend/tests/console-window.spec.ts`) | J | DONE | cuddly-sniffle | #1409 | Plan 62 row l32 |
| L33 | Every sentence for a record the door answers missing says it is not packed yet | L25 | H | PENDING | - | - | - |
| L34 | The rest of the console reads right at the one-day window | L26, L30 (holds `MergeLinePlot.svelte` as well as `frontend/tests/console-window.spec.ts`), L31 (holds `frontend/tests/console-window.spec.ts`), L32 (holds `JudgeAgreement.svelte` as well as `frontend/tests/console-window.spec.ts`) | K | PENDING | - | - | - |
| L35 | Pipelines' failure and time-split panels follow the window or say why not | L26, L30, L31, L32 (each holds `frontend/tests/console-window.spec.ts`) | L | PENDING | - | - | - |
| L36 | Hardware's one-sided line leaves out a day whose only run was refused | L28, L29 | M | DONE | psychic-goggles | #1421 | Plan 62 row l36 |
| L37 | Article cost names a refused shard's processor time or leaves it out | L29 | N | PENDING | - | - | - |
| L38 | Judgement's verdict split and holdout margin name the line a build used | L30 | M | DONE | jubilant-memory | - | Plan 62 row l38 |
| L39 | Judgement's "could not tell" counts against the pairs that agreed | L32, L31 (holds `merge-line.ts` as well as `merge-line.spec.ts` as well as `frontend/tests/console-window.spec.ts`) | M | DONE | crispy-goggles | #1428 | Plan 62 row l39 |
| L40 | A day under the floor is not drawn at its shares' heights | L32, L31 (holds `frontend/tests/console-window.spec.ts`) | N | PENDING | - | - | - |
| L41 | The Judgement route reads its committed fitted lines and holdout scores | - (plan 59's rows "The fitted merge line is saved through the door", "The merge line's holdout score is saved through the door" and "The committed judge rows move onto the door, and the old CSV files go" later replace this read) | M | DONE | friendly-engine | #1418 | Plan 62 row l41 |
| L42 | The days control shows the window the panels draw after moving between console routes | L31 (holds `frontend/tests/console-window.spec.ts` as well as `which-console-surfaces-follow-the-window-and-which-say-why-not.md`) | O | PENDING | - | - | - |
| L43 | Every console route sets its own page title | - | N | DONE | upgraded-telegram | #1429 | Plan 62 row l43 |
| L44 | The publication inventory names every fitted-line and holdout day the council commits | L41, plan 59's row "The fitted merge line is saved through the door" (it closes this row) | O | PENDING | - | - | - |
| L45 | Judgement's sentences agree with the days and counts it draws | L41 (its third fault waits until the Judgement page reads fitted days after 2 Oct: decision 3) | P | PENDING | - | - | - |
| L46 | The site build bakes the raw days the data explorer may read | - | Q | DONE | automatic-garbanzo | #1427 | Plan 62 row l46 |
| L47 | Hardware's started line counts a day whose only run is machine records alone | L36 | O | PENDING | - | - | - |
| L48 | The Data explorer's line under an answer ends on the last day it read | L12, L46, plan 55's row "The reader chooses the chart and the columns it draws" (holds `frontend/src/routes/console/data-explorer/+page.svelte` as well as `frontend/tests/console-data-explorer.spec.ts`) | R | PENDING | - | - | - |
| L49 | Every console route asks search engines not to list it | L38, plan 55's row "The reader chooses the chart and the columns it draws", L42 | S | PENDING | - | - | - |
| L50 | Two console tests prove what they claim | - | T | PENDING | - | - | - |
| L51 | Judgement's agreement panel words follow the rates they judge | L39, L40 (holds `frontend/src/routes/console/judgement/JudgeAgreement.svelte`) | U | PENDING | - | - | - |

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
  - `docs/architecture/publishing/ledger-compaction.md` (found during execution (owner fold from row L7's report): row 1 of its fault table, and the paragraph on a ledger with no compact folder, said a first pass writes all three indexes; a first pass writes them only when it packs a day, and a pass with no raw day writes nothing)
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
  - `frontend/src/lib/console/span-words.ts` (new, found during execution: the one helper, named for its one question, what words name a window's days; decision 5)
  - `frontend/src/lib/console/held-part-note.ts` (found at dispatch by the owner: it took `spanWords` from `fleet.ts`; its words, Reader's and Jony's in row L15, do not change)
  - `frontend/src/lib/console/recording.ts` (found during execution: its phrase for more than one day takes the helper; at one day it names the date, Reader's words in row L11)
  - `frontend/src/lib/components/RunSquares.svelte`, `frontend/src/lib/components/StageTimings.svelte`, `frontend/src/lib/components/MemoryBoard.svelte` (found during execution: windowed sentences the search missed - "Run health history over 1 days", "We timed nothing in these 1 day", "inside the 1 days this page read")
  - `frontend/tests/span-words.spec.ts`, `frontend/tests/span-sentences.spec.ts`, `frontend/tests/support/span-said.ts` and `frontend/scripts/test-groups.ts` (new, found during execution: the Oracle, the words the browser checks owe at each preset, and the two specs named under `logic`; decision 6)
  - `frontend/tests/console-timings.spec.ts`, `frontend/tests/console.spec.ts`, `frontend/tests/console-judgement-line.spec.ts`, `frontend/tests/console-memory-held.spec.ts`, `frontend/tests/console-frame.spec.ts` (found during execution: they pin a count over the window, "4 of these 15 days", the clamp line's "of the last", and a Hardware subtitle's "last N days", words Reader changed)
  - `docs/concepts/console-design.md` and `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` (found during execution: Reader's two names and the one-day rule; the second page quoted the old one-day sentence)
  - Unchanged, found during execution: `MergeLinePlot.svelte` (its sentences come from `merge-line.ts`), `JudgeAgreement.svelte` (it prints no day count), `KpiCard.svelte` (each route hands it its note), `completeness.ts` (it counts missing days and already says "1 day is missing."), `platform-mix.spec.ts` and `console-judgement-merges.spec.ts` (the words they pin did not change)
  - `frontend/src/routes/console/voices/+page.svelte` also carries an owner fold from row L20 (Level 0): the comment above the dwell rule now says what `dwellStart()` in `frontend/src/lib/server/source-retiring.ts` does
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; the browser smoke of every console route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on data the test builds (Table D, D3): each windowed surface reads "1 day" at the 1-day preset and "7 days" at the 7-day preset. It cannot settle a sentence that counts something other than the window's days, such as runs or days with rows.
- **Follow-ups** (found during execution):
  - Reader's rule that at one day a sentence must not need a second day also binds sentences that print no day count, and these break it at the 1-day preset: the disk panel's legend "How far the memory holding disk copies fell, 2026-10-06 to 2026-10-06"; the latency chart's label, a range of run dates that is one day; the throughput chart's "oldest day on the left"; the run health hint "Left and Right step through the days"; the memory panel's "no run that wrote these days"; the labels "on the busiest day" (Pipelines cards), "one point a day over 1 day" (extraction), "per day, over 1 day" (doubt reasons) and "a day, over 1 day" (merged stories); the counterfactual cost chart's "one column a day" and "added up day by day"; and the chart-drawing verdict's "no day published anything", reachable only where the rule's own span is one day. A Level 1 row with Reader's words.
  - Counts of other days that still print "1 days" when they are 1: the memory panel's "Read over {n} days" and "over {n} days of ledger" (the days the record read) and the chart-drawing line's "over {n} measured days". A Level 1 row, through `countDays`.
  - The Judgement route has no window oracle in `console-window.spec.ts`, and three of its four windowed surfaces can name no span in words: `judge-agreement` always, `record-gates` when no line was fitted, and `merge-line` when no fitted day is in the window. On the canary all three print no day count at 1 and at 7 days (the browser smoke).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fault 4 of row L16, moved here. It changes `console-window.spec.ts`, which L13 held, so it waits for L13. Since L13 (#1366), `console-article-cost.spec.ts` no longer reads the Hardware intro | The owner, 2026-10-07 |
| 2 | Reader chooses the words (CLAUDE.md section 14). Two names: the days on screen are "these 7 days" or "this one day", and a bare count is "7 days" or "1 day", the days control's own words. A count over the window drops "these": "on 5 of 7 days", "on 1 of 1 day". "The last N days" goes, because every window ends on the newest published day. At one day a sentence must not need a second day - no range, no order across days, no waiting for a later day, no worst, middle, median, quietest or loudest day - so about twenty sentences are written whole for one day, such as "This one day did not publish a summary, so there is nothing to explain." and "1 day, 2026-10-06. 12 rows in view." Recorded in `docs/concepts/console-design.md` | Reader, 2026-10-07, in three rulings |
| 3 | `spanWords` in `fleet.ts` and `span` in `merge-line.ts` fold into one helper, which every windowed surface uses | The owner, 2026-10-07 |
| 4 | Level 1: the words of sentences on four routes; a wrong version is obvious and local | The owner, 2026-10-07 |
| 5 | The helper is `frontend/src/lib/console/span-words.ts` with three verbs: `nameSpan` (the days on screen), `openWithSpan` (the same words opening a sentence or a row label) and `countDays` (a bare count, through `plural` in `format.ts`, as the days control counts). Reader's two names need two forms, and a sentence that opens on the span needs a capital | Found during execution |
| 6 | The Oracle is two logic specs on inputs they build, every word written out: `span-words.spec.ts` holds the helper, and `span-sentences.spec.ts` calls each windowed sentence a function writes at one day and at seven. A sentence in a Svelte template is held by the browser loops of `console-window.spec.ts` and five other specs: at the 1-day preset each windowed surface says "one day" or "1 day" and never "1 days", and at seven it says "7 days", in words `tests/support/span-said.ts` writes out. Those loops hold for any data and reach only the states the canary renders, so the browser smoke read every route at 1 and 7 | Found during execution (Table D, D3) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Fix only the Hardware intro, inside row L16 | The oracle in `console-window.spec.ts` requires every windowed surface to say `${preset} days` at the 1-day preset, so the intro alone turns it red, and every other surface keeps "1 days" | One sentence fixed, in a file L13 holds | The owner, 2026-10-07 (row L16's report) |
| 2 | As today | Every console route says "these 1 days", "over the last 1 days" or "the 1 days ending there" at the 1-day preset | Nothing to build | The owner, 2026-10-07 |

### Row #L18 - The console home reads each day payload once

- **Scope:** The console home opens each published day's payload once, through `publishedCharts`, and the articles card takes each day's count from that read, so `publishedItems` goes and the route opens half as many day payloads at build time. Level 2. Found during execution: the "Articles published" card already drew its counts from `charts`, which `publishedCharts` feeds. The `publishedItems` key feeds the cost panel "What one more article costs" and its horizon sentence, so those are the counts that now come from the one read.
- **Files touched** (found by a search on `main` at 3f6440edb for `publishedItems`, the name this row deletes):
  - `frontend/src/lib/server/payload.ts` (`publishedItems` goes; the comment on `publishedCharts` says it is bounded the way `publishedItems` is)
  - `frontend/src/routes/console/+page.server.ts` (imports both readers, hands the page `publishedItems(undefined, widest)`, and hands `chartDays` the map `publishedCharts(undefined, widest)` returns)
  - `frontend/tests/console-published.spec.ts` (imports `publishedItems`; row L14's test "the articles a day published are read off its own payload, over the days the cover reaches"; the comment in "THE ORACLE: the articles card counts what the chart table says each day published" names the two readers. Found during execution: that comment was already false on `main`, because the card and the table both draw `charts`)
  - `frontend/tests/console.spec.ts` (not found by the search: the test of `publishedCharts`, "a visual that never drew is a visual and is not a published chart", beside which row L14's days and windows move; decision 4)
  - `docs/concepts/growing-reads.md` (the `payload.publishedItems` line of its table of reads)
  - `docs/architecture/publishing/console-payloads.md` (the `Published items` line names `publishedItems` as the reader it replaces, and a paragraph names three reads off the run-day row)
  - `docs/architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md` (says a route walks `DIGEST_ROOT` the way `publishedItems` does)
  - `backend/idhazh/contracts/console_payloads.py` (the entry whose reader is `payload.ts publishedItems()`; decision 5. Found during execution: the entry stays, because the run-day row still carries the article count, and its reader now names `payload.ts publishedCharts()`)
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
  - `frontend/tests/support/model-swap.ts` (new: the swap both specs build and render; decision 2. It also holds `BANDS`, which the run-length tests in `console-model-panels.spec.ts` share with the swap, and `buildSwap()`, which builds the swap that stands for the other window; found during execution)
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
- **Files touched** (found by a search on `main` at 3f6440edb for `countersWithoutScores`, `scoresWithoutCounters`, `countersOnly` and `coveredElsewhere`; searched again at dispatch, on `main` at 64361ebf3, after L17: the same files):
  - `frontend/src/lib/console/recording.ts` (`countersWithoutScores()` and `scoresWithoutCounters()` hold the two lines; `recordingNotes` decides the Hardware line from `coveredElsewhere`. Found during execution: both lines are worked out in `recordingNotes`, the two exported functions go, and the field `scoresOnly` is `coveredElsewhere`; the words name the window's days with `nameSpan` from `span-words.ts`, which does not change)
  - `frontend/src/routes/console/model/+page.server.ts` (`countersOnly`: a timed day in the window that is not a scored day; fault 2)
  - `frontend/src/routes/console/machine/+page.server.ts` (hands `coveredElsewhere` the article record's days, `healthDays`; fault 3)
  - `frontend/tests/console-chrome.spec.ts` ("the two one-sided days each name which instrument answered" pins both lines' words; "a day another instrument covered is named, not drawn as a quiet day")
  - `docs/concepts/console-design.md` (names the six states with fixed wording, these two among them, and who chose each one's words)
  - `frontend/src/routes/console/model/+page.svelte` and `frontend/src/routes/console/machine/+page.svelte` (found during execution: they print the field and the data attribute decision 7 renames; listed before as left as they are)
  - `docs/concepts/console-design.md` also carries an owner fold from row L25 (#1384): a panel built on a record keeps its own line for a nothing that the route's note also states, in the note's words and never pointing at the note, as the platform-mix panel's "The machine record is not packed yet." does (Jony and Reader, 2026-10-07)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-chrome.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of Hardware and Summaries at each window preset. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console-chrome.spec.ts`, on facts the test builds (Table D, D3), with the server's counters written every day. A window whose only day without a score row is one the score record lost prints no line saying nothing scored the summaries; a window with two days the scorer did not run prints that line, and it does not call them "this day". On Hardware, a day the article record holds, with no score row and no counters row, gets no line that says the summaries were scored. It cannot settle the words, which Reader and Jony choose (decision 2); the test pins the words they choose.
- **Follow-ups** (found during execution):
  - On Hardware a run of article rows alone, with no server counters, is a valid run (`machineCounters` in `frontend/src/lib/server/machine-counters.ts`; `mergeHost([])` returns empty cells), and article rows name a machine shard from 30 Aug 2026 while the machine record holds rows only from 17 Sep. So two lines are false today in the 30- and 90-day windows: the intro counts the runs of 30 Aug to 16 Sep as runs "that committed counters the model server wrote itself", and the started line dates the server's counters from 30 Aug. The fix changes what "the counters ran" means for three lines, so it is a row of its own; with decision 7, that row's fix for this row's line is one fact the Hardware route hands it (Fowler, 2026-10-07).
  - Hardware ignores how its score read went: if that read fails, the change markers disappear with no note saying why (Fowler, 2026-10-07).
  - Decision 10, with Hardware's sampled line: Hardware hands the scorer's `sample_rate` to the server's counters, which nothing samples (only `host_fingerprint` turns them off), so below 1.0 it would print "Measured on 1 run in 4" about figures nothing samples. One row for both, before anyone sets the rate below 1.0 (Jony and Reader, 2026-10-07).
  - On Hardware the refused-runs box says a refused run is "left out of every windowed figure on this page" and that "nothing here reads the run at all", but the panels built on the article record take its rows by date alone: `readAgainstWritten` in `frontend/src/lib/charts/machine.ts` keeps every row with token counts, whatever its run. In the canary build the days this row's line names on Hardware are exactly the refused runs' days, so the two lines disagree on one screen. Reasoned from the code, not measured; not ruled (found by this row's worker, 2026-10-07).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The three faults are Reader's findings in row L16, left for a row of their own | Reader, 2026-10-07 (row L16's report) |
| 2 | Reader and Jony choose the words of both lines (CLAUDE.md section 14). Summaries: "There are no quality figures for {days}. The machine ran and we timed it, but nothing scored the summaries." Hardware: "No server figures were written down for {days}. The speed figures {where} come from the summariser, not the server." {days} is the window's own words from `nameSpan` where every day on screen is one of them, otherwise the days named, consecutive days joined; {where} is "here", "for that day" or "for those days". The days are named and never counted: a name says where to look, and a count beside the started line reads as a second set of days. Reader proposed and Jony agreed in the one debate round (his first answer was cut in transit, and only its last paragraph arrived); no word was left split, so none fell to Reader's responsibility for plain language | Reader and Jony, 2026-10-07 |
| 3 | Summaries' line is worked out in `recording.ts` from the facts the route hands it, as the Hardware line already is, so a test can hand it facts it builds: a `+page.server.ts` may export nothing else, so nothing in it can have a logic test (row L13) | Plan author, 2026-10-07 |
| 4 | Fault 3 is fixed by a line that claims no score: Hardware draws no quality figure, and the line exists to say where its speed figures came from. The reason this decision was left to Fowler was wrong: Hardware already reads the score record, `evalRows(readSpan)` for its change markers, so reading which days were scored would add no read; it would add that record's read states, its lost days and a second sentence for a day with neither | Fowler, 2026-10-07 |
| 5 | L22 waits for L16, which changed what the two routes hand `recordingNotes` and where Summaries prints its recording lines | The owner, 2026-10-07 |
| 6 | Level 1: the words of two lines and the facts two routes hand them; a wrong version shows on those two routes | The owner, 2026-10-07 |
| 7 | One day rule in `recordingNotes` for both routes. Each route hands the article record's days as `coveredElsewhere` and names the figures the other days are missing, `missing: 'scores'` or `'server-counters'`, both or neither by type, with no default words. `scoresOnly`, `countersWithoutScores()` and `scoresWithoutCounters()` give way to the field `coveredElsewhere` and private words, and the data attribute is `covered-elsewhere` on both routes. Two commits: the move with today's words and rule, then the rule and the words. The tests check every line the notes print, so each case printed its own false line on the base | Fowler, 2026-10-07 (found during execution) |
| 8 | The line names only days the missing record could have answered: none after the earliest day the reads it draws on are packed through, and none at all when one of them did not read | Fowler, 2026-10-07 (found during execution) |
| 9 | Each day is said once. The line leaves out the days the started line counts (Reader; Jony agreed), and while "Measurement is off" prints, the days after the newest recorded day, which the off line speaks for (Jony; Reader agreed). What is lost: on Hardware those days' line no longer says where their speed figures came from | Reader and Jony, 2026-10-07 (found during execution) |
| 10 | While the "sampled" line prints, Summaries prints no line about days the article record alone answered for, because below a rate of 1.0 most days have no score row on purpose (Jony; Reader agreed). Not built in this row: the rate is 1.0, so it cannot show today, and in the shared function it would also hide Hardware's line while Hardware wrongly hands the scorer's rate to the server's counters. A follow-up row, which must land before anyone sets `observability.sample_rate` below 1.0 (Reader's condition) | Jony and Reader, 2026-10-07 (found during execution) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Each fault leaves a false line on screen | Nothing to build, and a false line on two routes whenever a window holds two or more one-sided days, a lost score day, or a day with articles and no counters | Reader, 2026-10-07 (row L16's report) |
| 2 | Drop the two lines | A one-sided day would read as a full day or a quiet one, which these lines exist to stop (`docs/concepts/console-design.md`) | No words to choose, and a reader who cannot tell why a day has speed figures and no quality figure, or the reverse | Plan author, 2026-10-07 |
| 3 | Hardware says which of its days were scored, from the score record it already reads | Hardware draws no quality figure, so no one reads the claim there | No new read, and that record's read states, its lost days and a second sentence for a day with neither scores nor counters | Fowler, 2026-10-07 |
| 4 | Count the days: "on 2 of 14 days" | Beside the started line a count reads as a second set of days, and a count does not say where to look | A shorter line over a wide window | Reader, 2026-10-07; Jony agreed |
| 5 | Two exported functions, one a line, each called by its route (Fowler's shape S2) | Two places to decide which days a line names, and the Summaries fault began when a route printed these words with its own day rule | Each route's line can be read on its own | Fowler, 2026-10-07 |

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
| 1 | Reader chooses the subtitle's words (CLAUDE.md section 14) | Reader, 2026-10-07: "Over {span}, {N} of {M} items had to read {pronoun} whole, with nothing saved from before. The rest reused part of an earlier prompt instead." for some-in-memory, and "Over {span}, every one of the {M} items reused part of an earlier prompt - none had to start from scratch." for none-read-whole. Reader, 2026-10-07 (second round, before merge): "Over {span}, all {M} items had to read their prompts whole, with nothing saved from before." for every item in a window of more than one reading whole, confirmed unchanged from the draft; and, for a window of exactly one item, "Over {span}, the one item reused part of an earlier prompt - it did not start from scratch." when it did not read whole, or "Over {span}, the one item had to read its prompt whole, with nothing saved from before." when it did. Reader chose "the one item" over `plural()` from `frontend/src/lib/format.ts` so a single item is never named "1 items" |
| 2 | The subtitle's words come from one pure function of the window's `ItemCost`, in `frontend/src/lib/console/prompt-cache-subtitle.ts`, and the page prints what it returns, as the note under the share has since L15 (#1368). So a test pins Reader's words on rows it builds | Plan author, 2026-10-07, from row L15 |
| 3 | The three faults are row L15's findings. The search for the old title found two more pages that name it, `console-machine.md` and `telemetry-series.md`, so this row corrects all three pages | Row L15's report; plan author, 2026-10-07 |
| 4 | L23 waits for L15, which edited the note under the share, the home route's page and the prompt-cache section | The owner, 2026-10-07 |
| 5 | Level 1: the words of one subtitle on one route, and three pages; a wrong version is obvious and local | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The page names a Hardware panel that is not drawn, says the share is drawn under a heading that says it is not, and the subtitle says every article's instructions stay in memory while the panel prints how many items had nothing in memory | Nothing to build, and three pages and one subtitle that a reader can check and find false | Row L15's report; the owner, 2026-10-07 |
| 2 | Change the words in the page, with no function | No test can read them without the canary's page, so their test would rest on what the canary holds (Table D, D3), or they would have none | One file fewer, and words no test pins | Plan author, 2026-10-07 |

### Row #L24 - The bundle gate does not fail a published ledger that is not packed yet

- **Scope:** When a site build holds none of a published ledger's files, the bundle gate reports that ledger's index key as not weighed and names the ledger instead of failing, so CI passes and a push to `main` publishes while the ledger is not packed yet. Every other payload key that names nothing in the build still fails the gate. Level 2.
- **Files touched** (found by a search on `main` at 3d56802ea for `bundle-gate`, for "names nothing" and "matches nothing", and for `payload_ceilings_bytes`):
  - `frontend/scripts/bundle-gate.mjs` (its payload loop adds each key whose path holds no file to `namesNothing`, which fails the gate with "{key} is capped at {size}, and no file in the build is at that path", and the comment above the loop says a key that matches nothing fails. The loop moves out; decision 3)
  - `frontend/scripts/payload-ceilings.mjs` (new: the payload check as one function, which the gate calls; decision 3)
  - `frontend/tests/payload-ceilings.spec.ts` (new, under `logic`: the Oracle, on build trees the test writes)
  - `frontend/scripts/test-groups.ts` (names the new spec under `logic`)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (its paragraph on what the indexes weigh says that a ledger not packed yet fails the gate, so CI fails and a push to `main` does not publish; row L7 wrote it)
  - `docs/concepts/config/run-limits.md` (its `page_weight.payload_ceilings_bytes` line says a key matching nothing fails the gate; found by the search, not named in row L7's report)
  - `backend/idhazh/contracts/knobs/page_weight.py` (the `payload_ceilings_bytes` description says a key that matches no file in the build fails the gate; found by the search, not named in row L7's report; decision 5)
  - Left as they are: `backend/tests/contracts/test_page_ceilings.py`, which requires one index key for each published ledger and none for another ledger; `backend/utilities/publish_decision.py`; `docs/architecture/publishing/console-site-size.md` and `docs/architecture/publishing/console-payloads.md`, whose key that would match nothing names `source-health.json`, which is no ledger; `docs/how-to/run-the-gates.md`, whose sections on the gate say nothing of a key that names nothing; `frontend/tests/published-ledgers.spec.ts` (Table B, B7)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec payload-ceilings.spec.ts`; `npm --prefix frontend run check`; ruff, mypy and the backend tests that `test:changed -- --list` selects for `page_weight.py`; `doc_load.py` on the two pages; the gate on a copy of a finished build with one published ledger's `state/compact/<ledger>/` and `state/raw/<ledger>/` folders deleted, as the site copy leaves a ledger not packed yet: it exits 0 and names that ledger, where row L7 measured exit 1 on such a build. CI: the `site` job runs the gate on a real build of the committed data; what `ciAnswer` selects, then every group on the merge push.
- **Oracle:** in `payload-ceilings.spec.ts`, on build trees the test writes, against written-out verdicts (Table D, D3). A published ledger whose build holds none of its files passes, and the answer names it as not weighed. A key that names nothing and belongs to no published ledger still fails. A published ledger with some of its files in the build and nothing at its index key still fails. It cannot settle that `bundle-gate.mjs` prints and fails from what the function returns; the local gate run above and CI's `site` job, which runs the gate on every code change, cover that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault: since L7 the site build goes on for a published ledger with no compact folder, but the bundle gate fails on any payload key that names nothing in the build, and `backend/tests/contracts/test_page_ceilings.py` requires such a key for every published ledger. On row L7's build check the gate said "state/compact/feed-retirements/index/ is capped at 2.2 KB, and no file in the build is at that path". CI runs the gate on every code change, and a push to `main` publishes only after CI passes (`backend/utilities/publish_decision.py`). So while a published ledger is not packed yet, CI stays red, merges wait and pushes do not publish. The daily run still publishes, because Pages publishes what it landed whatever its conclusion, though its own run of the gate in `.github/workflows/digest.yml` ends its job red | Row L7's report (#1370), 2026-10-07; the daily run's red job, plan author, 2026-10-07 |
| 2 | The gate reports a published ledger's index key as not weighed, and names the ledger, when the build holds none of that ledger's files. Every other key that names nothing still fails, the index key of a published ledger with some of its files in the build included. As in the site build since L7, a compact folder deleted by accident then reads as a ledger not packed yet: the build log and the gate each name it, and nothing fails. About an hour of work, by row L7's estimate | Plan owner, 2026-10-07 (option A1 of row L7's report) |
| 3 | The check moves into one function that a logic test runs on a build tree the test writes, because the gate has no test. The function is in `frontend/scripts/payload-ceilings.mjs` (new), which the gate imports: `bundle-gate.mjs` runs every check and exits when it is loaded, so a test cannot import a function from it. The site copy is split the same way: `copy-visuals.mjs` runs it, and `ledger-copy.spec.ts` tests `ledgerCopy` from `published-ledgers.mjs` | Plan owner, 2026-10-07 (option A1 of row L7's report); the new file, plan author, 2026-10-07 |
| 4 | A ledger's files in a build are the paths the site copy stages for it, under `state/compact/<ledger>/` and `state/raw/<ledger>/` (`ledgerCopy` in `frontend/scripts/published-ledgers.mjs`). The function checks those two named paths, so its read does not grow with the build (Guardrail #12). It takes the published ledgers from `ledger.published` in `config/idhazh.json`, the file the gate already reads | Plan author, 2026-10-07 |
| 5 | Only the words of the `payload_ceilings_bytes` description in `page_weight.py` change. It describes a config knob, not a persisted shape, so Table C, C1 does not fire, as for the `today_anchor` description that L5 changed | Plan author, 2026-10-07 |
| 6 | L24 waits for L7 (#1370): before it, the site build stopped for such a ledger before the gate ran | Plan owner, 2026-10-07 |
| 7 | Level 2: the gate's verdict changes, and every CI run, and so every publish of a push, depends on it | Plan owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the gate as it is, and add a ledger to `ledger.published` only after it is packed (option A2 of row L7's report) | It gives up what L7 turned down its rejected alternative 1 for: a ledger's start is a normal state and stops nothing. Whenever that order slips, CI stays red, merges wait and pushes do not publish until the ledger is packed | Nothing to build, and an order a person must keep each time a ledger joins `ledger.published` | Plan owner, 2026-10-07 |
| 2 | Fold the fix into #1370 (option A3 of row L7's report) | L7 would grow past its brief by three files and a new spec, which gives up a focused review | One merge instead of two | Plan owner, 2026-10-07 |
| 3 | Export the function from `bundle-gate.mjs`, and run its checks only when node starts it, as `frontend/scripts/test-scope.ts` does | Every check in the gate moves inside one function so that a test can reach one of them | No new file, and a change to most lines of the gate | Plan author, 2026-10-07 |

### Row #L25 - Hardware's platform-mix panel says the machine record is not packed yet

- **Scope:** When the door answers `missing` for the machine record, the platform-mix panel on the Hardware route no longer says the record has not been published: since L7 a published record with no compact folder answers `missing`, and it is one that is not packed yet (Table F, F1). Level 1.
- **Files touched** (found by a search on `main` at 3d56802ea for "has not been published yet", for the panel's other empty-state sentences, for `machineRecordState` and for the panel's id, `platform-mix`):
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte` (line 127 prints "The machine record has not been published yet." when the door answers `missing`; no other file under `frontend/src/` says "has not been published yet")
  - `frontend/tests/console-query-door.spec.ts` (its `missing` case answers the record's index requests with 404 through `frontend/tests/support/machine-record-state.ts`, and checks only that the panel prints a sentence; the Oracle. Found by the search, not named in row L7's report)
  - `frontend/tests/panel-sufficiency.spec.ts` (only if decision 2 leaves the panel no line of its own: its test that the panel's four empty states draw four different pictures puts the panel into `missing` the same way; found by the search, not named in row L7's report). Not touched: decision 2 keeps the panel's own line
  - Left as they are: `frontend/tests/platform-mix.spec.ts`, a logic spec of what the panel draws from the door's rows, which loads no page, so it cannot reach `missing` and pins none of the panel's empty states; `frontend/tests/support/machine-record-state.ts`; `frontend/src/lib/console/recording.ts`, whose note on the route already says the record has not been packed yet. No page under `docs/` quotes the panel's empty states
  - `docs/how-to/run-the-gates.md` (found during execution: its example names the base-commit copy by `$env:TEMP`, and a canary build in a copy named by a short 8.3 path stops in the telemetry step; the example now takes the long name, and one sentence gives the reason and the tell)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-query-door.spec.ts`, with `--spec panel-sufficiency.spec.ts` if decision 2 leaves the panel no line of its own; `npm --prefix frontend run check`; the browser smoke of the console's Hardware route with the machine record's index requests answered 404. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console-query-door.spec.ts`, on a site whose published machine record has no compact folder, which the test serves by answering that record's index requests with 404 (Table D, D3): the panel never says the record is not published, and prints the words Reader chooses, or no sentence of its own if decision 2 leaves it to the route's note. On `main` it says "The machine record has not been published yet.", which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 1); the test pins the words Reader chooses.
- **Follow-ups** (found during execution):
  - The door's module comments in `frontend/src/lib/data/ledger-reach.ts` and `frontend/src/lib/data/slice-reader.ts` still say that `missing` means "there is no `daily.json`, so the ledger is not published". Since L7, a published ledger that is not packed yet answers `missing` too. A Level 0 row.
  - `docs/concepts/console-design.md`, which row L22 holds, has no line for the rule decision 2 applies: a panel built on a record keeps its own line for a nothing that the route's note also states, says it in the note's words, and never points at the note. The plan owner carries it.
  - `main()` in `backend/idhazh/telemetry/publish/public_telemetry.py` prints each path relative to `config.REPO_ROOT` without resolving it first, so a canary build in a checkout named by a short 8.3 path stops with `ValueError: ... is not in the subpath of ...`. The line in `docs/how-to/run-the-gates.md` steers around it; resolving the path removes it. A Level 1 row.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words (CLAUDE.md section 14): "The machine record is not packed yet." They are the route's note's own words, so the page says one fact twice, and "is not packed" stays true for a compact folder deleted by accident, where "has not been packed" would be false | Reader, 2026-10-07 |
| 2 | Jony rules whether the panel keeps a line of its own for `missing` or leaves the route's note to say it (CLAUDE.md section 14): the panel keeps a line of its own. The route's note sits five panels above (2,086 px above the panel at 1,440 px wide and 3,464 px at 390 px, about four phone screens, measured on a build with the record's compact folder removed) and comes from the site build's read, not from the browser's request to the record, so it is not always on the page when the box is empty, as on the test's page; and each panel on the route already says its own nothing. The line is one sentence of at most 13 words, the length of the panel's failure line. It uses the note's words "the machine record" and "packed" and never "published", does not point at the note, never says there were no jobs, and asks for no action | Jony, 2026-10-07 |
| 3 | The fault: the panel prints "The machine record has not been published yet." when the door answers `missing`. Since L7 a published ledger with no compact folder answers `missing`, so the sentence is false for it. On row L7's build check, with the machine record's compact folder removed, the Hardware route's note said "The machine record has not been packed yet..." above the panel saying it has not been published | Row L7's report (#1370), 2026-10-07 |
| 4 | L25 waits for L7 (#1370), which turned such a record from a stopped build into a `missing` answer, and for L17, which holds the panel and its spec, `PlatformMixPanel.svelte` and `platform-mix.spec.ts` | Plan owner, 2026-10-07 |
| 5 | Level 1: the words of one line on one panel; a wrong version is obvious and local | Plan owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The panel says the record has not been published under a route note that says it has not been packed yet, and the panel's sentence is false | Nothing to build, and a false line on the Hardware route whenever the machine record is published and not packed yet | Row L7's report (#1370); plan owner, 2026-10-07 |
| 2 | No line of its own and no box: in `missing` the panel shows only its title and subtitle, and the route's note says why | A reader at the sixth panel loses the only words near the empty chart, and the panel shrinks, so the page below it moves when the answer arrives | A `missing` branch in `PlatformMixPanel.svelte` that draws no box, against the rule in `EmptyState.svelte` that the box keeps the chart's height in every state. In return the page says the fact once | Jony, 2026-10-07 |
| 3 | No line of its own, in a blank box at the chart's height | A box with no words is the one picture where not packed, quiet and broken look the same | A change to `emptyState()` in `frontend/src/lib/charts/d3/empty.ts` and to `EmptyState.svelte`, which every console chart shares and which refuse a nothing with no words | Jony, 2026-10-07 |

### Row #L26 - Every console sentence reads right at the one-day window

- **Scope:** At the 1-day preset, every console sentence that prints no day count today reads right under Reader's rule that a one-day sentence must not need a second day, and every count of other days that still prints "1 days" when it is 1 reads "1 day" instead. Level 1.
- **Files touched** (found by a search on `main` at d653ec214 for the phrases row L17's follow-ups name; search again at dispatch):
  - `frontend/src/lib/console/machine/DiskReadsPanel.svelte` (the legend "How far the memory holding disk copies fell, {first} to {last}", a one-day range at the 1-day preset; and, found during execution, the labels of its two strips, "one day a column. Left and Right read a day ...", "one tile a day" and "the same days")
  - `frontend/src/lib/console/machine/TailTrendPanel.svelte` (the latency chart's label, a range of run dates that is one day)
  - `frontend/src/lib/components/ThroughputTrend.svelte` ("oldest day on the left"; and, found during execution, "One day so far. A second day gives it something to move against." at the 1-day window, where no second day comes)
  - `frontend/src/routes/console/RunHealthPanel.svelte` ("Left and Right step through the days, Escape returns to the newest."; unchanged, found during execution: its hint and its heading follow the one rule in `ChartReadout.svelte`)
  - `frontend/src/lib/console/machine/MemoryHeldPanel.svelte` ("no run that wrote these days"; "Read over {n} days" and "over {n} days of ledger", two of the second follow-up's three counts; and, found during execution, "Every day here splits ...")
  - `frontend/src/routes/console/+page.svelte` ("on the busiest day", Pipelines cards; "one point a day over {countDays(windowDays)}", extraction; the "{rule.minutesDays}/{rule.coverageDays} measured days" sentence, the second follow-up's third count; and, found during execution, the cards' line "Point at a card's bars to read a day.", "Show these figures day by day" and the flow's note that quotes it, the table's "One row per day in the open window, newest first.", and the per-article cost panel's label, its note's "on each published day ... Over 1 day." and its horizon's "a median of N articles a published day")
  - `frontend/src/routes/console/model/+page.svelte` ("per day, over {countDays(windowDays)}", doubt reasons; and, found during execution, the faithfulness label "per day ... One line is each day's middle summary", its intro, and "Show these figures day by day")
  - `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte` ("a day, over {countDays(windowDays)}", merged stories)
  - `frontend/src/lib/console/machine/CounterfactualCostPanel.svelte` ("one column a day, over {nameSpan(windowDays)}"; and, found during execution, "the busiest day", "the tallest day" and "the columns carry no bands")
  - `frontend/src/lib/charts/cost.ts` ("added up day by day"; "one column a day")
  - `frontend/src/lib/charts/glance.ts` ("no day published anything", the chart-drawing verdict; its `minutesDays`/`coverageDays` computation; and, found during execution, the cards' label and the per-article cost panel's sentences, written there so a test pins them)
  - `frontend/src/lib/console/span-words.ts` (`countDays`, the helper both counts of other days go through; it gains the word for which days, so "1 measured day")
  - `frontend/tests/span-words.spec.ts`, `frontend/tests/span-sentences.spec.ts` (the Oracle row L17 built, extended for the new sentences and counts)
  - `frontend/tests/console-window.spec.ts` (its loop over windowed surfaces gains the sentences that print no day count today)
  - `frontend/src/lib/components/ChartReadout.svelte` (found during execution (owner fold from row L27's report): the strips' default hint "Left and Right step through them". It now holds the one rule for every strip of one column, so the Judgement strips' resting headings ", the newest day" and ", the newest published day", the record strip's hint, and every other day strip on the four routes follow it with no edit of their own)
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte`, `frontend/src/routes/console/judgement/MergeLinePlot.svelte`, `frontend/src/routes/console/judgement/RecordGates.svelte` (found during execution (owner fold from row L27's report): the agreement chart's label "..., a day"; the merge line's label "The merge line a day, ..." and its note "The shaded band at each day ..."; the record strip's label "What the record did with each day. ..." and, found during execution, the record panel's note "The squares are one a day: ...")
  - `frontend/src/lib/charts/Chart.svelte` (found during execution: a browser-drawn chart's empty box says "The newest day's numbers are below."; a chart that follows the window takes the window's days from its route, and the two Pipelines charts that draw every day the page holds take none)
  - `frontend/src/lib/charts/d3/DateSeries.svelte`, `frontend/src/lib/console/machine/FleetDots.svelte`, `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, `frontend/src/lib/charts/fleet.ts` (found during execution: the machines panel's strip still opens its job list at one column, so it says only that, through the two drawing wrappers)
  - `frontend/src/lib/components/FailureList.svelte` (found during execution: a cause row's and a source row's "last on the newest day in view")
  - `frontend/src/lib/charts/extraction-trend.ts`, `frontend/src/lib/console/doubt-reasons.ts`, `frontend/src/lib/console/eval-instruments.ts`, `frontend/src/lib/console/daily-figures.ts` (new) (found during execution: the extraction, doubt-reasons and faithfulness labels, the faithfulness intro, and the words around each route's table of daily figures, each written by a function so a test pins them)
  - `docs/concepts/console-design.md`, `docs/concepts/console-design/the-rules-every-console-chart-obeys.md` (found during execution: the one-day rule for a sentence that prints no day count, and the strip's rule for one column)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; the browser smoke of every named route at the 1-day preset. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on data the test builds (Table D, D3): each named sentence is read at the 1-day preset and found to need no second day, and each of the three counts reads "1 day" rather than "1 days" when it is 1. It cannot settle the words a sentence with no day count today should gain, if any; Reader rules.
- **Follow-ups** (found during execution):
  - Voices: its two record strips still say ", its newest day" and "Left and Right step through a feed's days" (and "a source's days") at the 1-day window. A strip read one record at a time is outside the one-column rule. A Level 1 row with Reader's words.
  - Hardware's processor-lost strip, also read one record at a time, says ", the newest day" at one day, and its tiles' label says "one tile a day ... Arrow keys read a tile"; the stage timings chart on Pipelines says "Median per item, each day." Level 1, with the Voices strips or in a row of their own.
  - Panel titles and a control that say "day by day" ("Which machines ran our jobs, day by day", "Summary faithfulness, day by day", the cost switch's "Day by day") stay at one day: a title names the panel, not the days on screen. Reader to rule whether that holds.
  - At one day a line chart draws a point, and two notes still speak of lines: "One line is how often ..." on the judge panel and "The solid line ... The dotted line ..." on the merge line. A Level 1 row with Reader's words.
  - On Pipelines, "What is failing, by stage" and "Where an item's time went" draw every day the page holds, not the window: at the 1-day preset the canary drew 12 and 3 columns, so their strips rightly name a newest day and keys. Neither is on the list of surfaces that do not follow the span (`docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md`), and neither says so on the page. A Level 2 row: follow the window, or say why not.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words for the sentences that print no day count today (CLAUDE.md section 14) | Reader, 2026-10-07, in one ruling and two follow-ups, with nothing left split. Words that say "this one day" name the window, so they print only at the 1-day window. A strip of one column heads its column alone, "15 Jun 2030", and its hint names no keys, at any window; where one column still offers an action it says only that, "Click or Enter lists this one day's jobs." ("Click or Enter lists the day's jobs." at a longer window). A browser-drawn chart's empty box: "This chart is loading. This one day's numbers are below." Labels: "Articles published in this one day, 300"; "..., one point for this one day"; "Minutes per visual, over 1 measured day"; "Why summaries were doubted in this one day. The column's height is ..."; "Summary faithfulness in this one day, as a percentage. One point is the day's middle summary ...", with the intro "Both points are this one day."; "Model tokens per second, 15 Jun 2030"; the latency label names its one date with no count; "How often the judge disagreed with its own second reading, in this one day"; "Stories folded into another in this one day"; "The merge line for this one day, ..."; "What the record did with this one day."; "Payload bytes per article in this one day"; "The counterfactual cost of this one day, one column, ..." and "..., in total. ...". Sentences: "This one day has no minutes on record, and did not publish anything to put a visual on."; "Show these figures for this one day"; "One row for this one day."; 'Open "Show these figures for this one day" below for each stage's count.'; "sources hit: 2 of 5", with no "last" clause, and a source row drops the same clause; "How far the memory holding disk copies fell, 2026-10-06"; "Read over 1 day."; no "reading begins" line over one day of ledger; "This one day splits the held part ..." and "This one day draws one held part ..., because no run that wrote the day recorded ..."; "Nothing split in this one day, so the column carries no bands."; "... percent of the column ..."; "The shaded band is as far as the line was allowed to fall that day."; "The square is what the record did with this one day."; "Bytes the committed payload tree gained in this one day, over the articles the day published."; "At 300 articles a published day, this one day's count, that is about ..."; and the speed line waits for no second day. Every sentence is written out whole in `span-sentences.spec.ts` and `console-window.spec.ts` |
| 2 | Level 1: a wrong version is obvious and local, one sentence or one count at a time | Plan owner, 2026-10-07 |
| 3 | Jony rules whether a strip's hint line keeps its room at one column (CLAUDE.md section 14): it keeps it, blank and hidden from screen readers, so no strip changes height with the window | Jony, 2026-10-07 |
| 4 | One rule in `ChartReadout.svelte` for every strip of one column, keyed on the strip's own column count, rather than an edit to each of about 25 strips. So it also holds at a longer window that drew one column, as Reader's ruling scopes it | Found during execution; Reader, 2026-10-07 |
| 5 | The failure-cause lines take no one-column hint, though Reader ruled words for one ("Point at a cause to read it. Up and Down step causes, Escape returns to the worst cause."): a line of one point is no line, so their strip never draws one column | Found during execution |
| 6 | The Oracle: the logic specs call each function that writes a changed sentence, at one day and at seven; 23 cases in `console-window.spec.ts` render the strip and ten panels with their real children, from data the test builds, and check each changed sentence, label and strip heading written out whole. A sentence on a route page is written by a function, so a test pins it without the route | Found during execution (Table D, D3) |
| 7 | Owner folds: the one-day sentences on Judgement that print no day count belong to this row (row L27's fourth follow-up), and rejected alternative 1 cites row L17's report, not row 20's | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the sentences that print no day count as they are | They still break Reader's one-day rule at the 1-day preset; found during execution (row L17 report) | Nothing to build, and a false or misleading reading at one day | Plan owner, 2026-10-07 |
| 2 | Give every strip of one column a hint with words, such as "Point at the day to read it." | Pointing at the only column changes nothing on screen, so the line promises an action that does nothing | One sentence a strip, at one day | Reader, 2026-10-07 |
| 3 | Close the hint line up at one column | The merged-stories panel would be a line shorter with a day to show than with none, and the strips with their own hint would stand a line taller than the rest | About 18 px less a strip, at one day | Jony, 2026-10-07 |
| 4 | Edit each of about 25 strips' heading and hint for one day | One rule written in 25 places, and every new strip would need its own copy | 25 edits and their tests | Found during execution |

### Row #L27 - Judgement's windowed surfaces name their span

- **Scope:** The Judgement route gains a window oracle in `console-window.spec.ts`, and the three of its four windowed surfaces that can name no span in words gain one: `judge-agreement` (always), `record-gates` (when no line was fitted), and `merge-line` (when no fitted day is in the window). Level 1.
- **Files touched** (found by a search on `main` at d653ec214 for `judge-agreement`, `record-gates` and `merge-line`'s window reads; search again at dispatch):
  - `frontend/tests/console-window.spec.ts` (the window oracle row L17 built gains the Judgement route's four windowed surfaces)
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (prints no day count; gains the span, Reader's words)
  - `frontend/src/routes/console/judgement/RecordGates.svelte` (prints no span when no line was fitted; gains one for that case)
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte` (found during execution: the sentence for no fitted day in the window is in its template, and so is the dashed rule's label; both take Reader's words)
  - `frontend/tests/console-judgement-agreement.spec.ts`, `frontend/tests/console-judgement-line.spec.ts` (found during execution: they pinned the old sentences, each with an all-time "yet", on the canary)
  - Unchanged, found during execution: `frontend/src/lib/console/merge-line.ts` (its sentences already name the span; the one this row names is in `MergeLinePlot.svelte`) and `frontend/src/lib/console/span-words.ts` (reused: `nameSpan` and `countDays`)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on data the test builds (Table D, D3): at the 1- and 7-day presets each of `judge-agreement`, `record-gates` (no line fitted) and `merge-line` (no fitted day in the window) names its span in words. On the canary all three print no day count at 1 and at 7 days today, which is what lets this check fail. It cannot settle the words; Reader rules.
- **Follow-ups** (found during execution):
  - With no fitted day in the window, the merge line's dashed rule is drawn at the committed floor, `floor_min` in `config/idhazh.json`, and labelled the line the newest day was built with. A build uses the newest fitted line of the 7 days before it (`applied_line()` in `backend/idhazh/similarity/applied.py`), so at the 1-day window, after a line was fitted in those days, the rule and its sentence name the wrong line. The route already hands `VerdictSplit` and `HoldoutMargin` the newest applied line it read. Latent while `adaptive_dedup_threshold.enabled` is false. A Level 2 row.
  - The record's three bars read the newest row inside the window, so a window with no row on its days draws all three at zero while the running record still holds what earlier rows counted. The panel's own header says falling bars mean a record that emptied. A Level 2 row.
  - Reader's: in the state "too few to report a share", the strip above the sentence prints a share of fewer than 5 pairs, such as "25% of 4 pairs". A Level 1 row with Reader's words.
  - One-day sentences on Judgement that print no day count, the kind row L26 takes, are not in L26's Files touched: the resting heading ", the newest day" on three panels' strips and ", the newest published day" on the merged stories; the record strip's hint "Left and Right step through the days, Escape returns to the newest." and its label "What the record did with each day. ..."; the strips' default hint "Left and Right step through them" in `ChartReadout.svelte`; the agreement chart's label "..., a day"; the merge line's label "The merge line a day, ..." and its panel note "The shaded band at each day ...". Add them to L26, or give them a row of their own.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words (CLAUDE.md section 14) | Reader, 2026-10-07, in one ruling with nothing left split. Every all-time "yet" goes, and each sentence names the days on screen through `span-words.ts`: "No pair was read twice in these 7 days, so there is nothing to compare."; "1 pair was read twice in this one day. That is too few to report a share, so the counts are above." (the strip with the counts sits above the sentence); "The two readings disagreed on {share} in these 7 days. No line was fitted on 2 of 7 days, because a rate was past its mark on those days." (the share over all the days need not be past the mark, and a day can be held because too many readings could not tell); "In these 7 days, {share} disagreed with their own second reading, and {share} could not tell. Both rates are inside the marks."; "Nothing was judged in this one day. The three bars are what the record needs before a line may be fitted at all."; the record's other three states end "No line was fitted in these 7 days.", where "A line was fitted on {k} of 7 days." stands when one was; the merge line says "No line was fitted in these 7 days.", the same words, and at one day its sentence and its dashed rule's label say "the line this one day was built with", not "the newest day" |
| 2 | Level 1: a wrong version is obvious and local, one surface at a time | Plan owner, 2026-10-07 |
| 3 | The Oracle is twenty-one cases in `console-window.spec.ts`, one a state and a window, that render each of the three panels with its real children from days the test builds and check Reader's sentences written out whole. A twenty-second holds the record's fitted-line sentence, whose words did not change but whose branch this row rewrote. The Judgement route also joins the loop the other four routes run, which holds for any data and reaches only the states the canary draws | Found during execution (Table D, D3) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the three surfaces silent on their span | On the canary all three print no day count at 1 and at 7 days; found during execution (row L17 report) | Nothing to build, and no window oracle for the Judgement route | Plan owner, 2026-10-07 |

### Row #L28 - Hardware's notes say only what its records hold

- **Scope:** On Hardware, a run made of article rows alone is no longer counted or dated as one that committed the server's own counters, a failed read of the score record is named instead of dropping the change markers with no note, and the server's counters no longer take the scorer's sampling rate, so no one-sided line prints while a sampled line does. Level 2.
- **The three faults** (row L22's follow-ups, 2026-10-07):
  1. A run made of article rows alone counts as one the server's counters wrote. `machineCounters` forms a run from either record, and `mergeHost([])` gives a run with no machine-record row empty cells. So in the 30- and 90-day windows the intro counts the runs of 30 Aug to 16 Sep 2026 as runs that "committed counters the model server wrote itself", and the started line dates the server's counters from 30 Aug, though the machine record holds rows only from 17 Sep (Fowler).
  2. Hardware ignores how its read of the score record went. Its change markers take the rows of `evalRows(readSpan)` and drop the read's state, so when that read fails, the markers disappear with no note (Fowler).
  3. Hardware hands the scorer's `observability.sample_rate` to the server's counters, which nothing samples: only `observability.host_fingerprint` turns them off. Below 1.0 the page would print "Measured on 1 run in 4" over figures nothing sampled. And while a sampled line prints, no one-sided line may print, because below a rate of 1.0 most days have no score row on purpose (row L22, decision 10). This must land before anyone sets `observability.sample_rate` below 1.0 (Jony and Reader).
- **Files touched** (found by a search on `main` at 6861bbd21 for `machineCounters`, `sample_rate`, `evalRows(readSpan)` and the intro's words; search again at dispatch):
  - `frontend/src/lib/server/machine-counters.ts` (`machineCounters` and `mergeHost`; fault 1)
  - `frontend/src/routes/console/machine/+page.server.ts` (`counterDays` from those runs, fault 1; `recordingNotes` handed `rate: observability.sample_rate`, fault 3; `modelChanges` from the rows of `evalRows(readSpan)`, fault 2)
  - `frontend/src/routes/console/machine/+page.svelte` (the intro, "{n} runs in {span} committed counters the model server wrote itself."; fault 1)
  - `frontend/src/lib/console/recording.ts` (`recordingNotes` writes the started line, the sampled line and the one-sided lines; faults 1 and 3)
  - `frontend/tests/console-chrome.spec.ts` (pins the sampled line, "Measured on 1 run in 4. ...", and row L22's one-sided lines)
  - `frontend/tests/ledger-rows.spec.ts` (row L16's Oracle for the started line)
  - `docs/concepts/console-design.md` (the states with fixed wording and who chose each one's words, and its `## Design rationale` entry on Hardware's one-sided line)
  - `frontend/src/lib/server/server-counter-notes.ts` (new, found during execution: `describeServerCounters` writes the intro, the "Measurement is off" line and the server counters' recording notes for one window, so a test reaches what the route hands them; decision 3)
  - `frontend/src/lib/server/model-work.ts` (found during execution: `listManifestDays`, the days a run manifest names, by the rule `pipelineChanges` reads; listed before as left as it is, and `pipelineChanges` does not change)
  - `frontend/src/lib/console/machine/ContextCostPanel.svelte` and `frontend/src/lib/console/machine/TailTrendPanel.svelte` (found during execution: the two charts that draw the change markers print the line for a score read that did not read, in place of "Nothing changed ..."; decision 2. `TailTrendPanel.svelte` was held by row L26, so its edit landed after L26 merged as #1400; decision 8)
  - Left as it is: `frontend/src/routes/console/model/+page.server.ts`, which hands the scorer's rate to the scorer's own lines, which that rate does sample; Summaries' started line takes its new opening words from `recording.ts`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-chrome.spec.ts --spec ledger-rows.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of Hardware and Summaries at each window preset, and of Hardware with the score record absent. CI: the pull request runs the console specs, because the change is the console's own; every group runs on the merge push.
- **Oracle:** in `console-chrome.spec.ts` and `ledger-rows.spec.ts`, on facts the test builds (Table D, D3): article rows alone, on days before the machine record's first row, are never counted as runs that committed the server's counters, and no started line dates those counters before the machine record's first day; a score read that did not read is named on the page, never silent; and at a sampling rate below 1.0, Hardware prints no sampled line about the server's counters, and neither route prints a one-sided line while its sampled line prints. On `main` each case prints what its fault says, which is what lets this check fail. It cannot settle the words, which Reader and Jony choose (decision 2); the test pins the words they choose.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The three faults are one row, because they answer one question, what Hardware's notes may claim from the records it holds, as row L22's three faults did | The owner, 2026-10-07 |
| 2 | Reader and Jony chose the words, in one debate round. The intro: "{n} runs in these {N} days, {m} of them with figures from the model server itself. {dates}", with "each with" and "none with", "with" or "with no" for one run, and "No run in these {N} days is on record." for none; at one day "This one day had {n} runs, ..." and "This one day has no run on record.". The line for a score read that did not read: "This chart cannot show whether the setup changed on {days}, because {cause}. {kind} This chart shows every change on the other days.", the cause in the record notes' own words for each of its five states, the kind "That is a step not yet run." or "This is a fault to fix.", and where every day on screen is one of them, the window's own words and no last sentence. Its place is Jony's: on both charts that draw the change markers, after the sentence about the dashed rule, and in place of "Nothing changed about how the summaries are written inside {span}." while it prints (Reader's condition). The started line opens on what started: "Server figures started on", "The machine record started on" and "Quality figures started on", because the 30-day window now shows two started lines with two dates. Each accepted the other's text in the round, so the crossing words were settled by responsibility: the words are Reader's last, the place is Jony's | Reader and Jony, 2026-10-07 |
| 3 | Fowler ruled the reads. A run carries the server's counters only where a shard reported `server_prompt_tokens` or `server_prompt_seconds` (`carriesServerCounters` in `machine-counters.ts`): on the real records the runs of 17 to 19 Sep 2026 hold the probe and the clocks and neither cell. The started line, row L22's line and the "Measurement is off" line take those runs' days; the off line, found to take every run's days as well, is the same fault. The intro keeps every run as its first number, opening "{n} run(s) in these" for the test row L26 holds, and adds the runs with the counters as its second; the snapshot panels stay on every run. The counters' notes read the machine record alone, which amends row L16 decision 10. A score read that did not read is named once for each window by `describeMissingMarkers` in `recording.ts`, only where the window shows a day with a run that no run manifest names (`listManifestDays`) and that comes before the first day a manifest names, because from then on the score rows carry no digest. The browser smoke found the second condition: 19 Sep 2026 published nothing, so no manifest names it, and its score rows carry no digest, so the first rule named it with a cause that could not be true for it. A day before that first day run again later would read as the changeover, a limit the function's comment states. The route keeps that read's state beside its rows and reads nothing new. `describeServerCounters` in the new `server-counter-notes.ts` writes the intro, the off line and the counters' notes, reads only `host_fingerprint` and hands no rate | Fowler, 2026-10-07 |
| 4 | It lands before anyone sets `observability.sample_rate` below 1.0, the condition on which Reader accepted row L22's split | Reader, 2026-10-07 (row L22, decision 10) |
| 5 | L28 waits for L22 (#1385), which put both one-sided lines in `recordingNotes` and hands it the article record's days as `coveredElsewhere` | The owner, 2026-10-07 |
| 6 | Level 2: what three lines on Hardware take to mean the server's counters ran, and a rule that `recordingNotes` applies on two routes | The owner, 2026-10-07 |
| 7 | Three commits: the counters' start read from the machine record alone; a move of today's lines into the new module with today's rules, `describeMissingMarkers` saying nothing as `main` does; then the rules and the words. On the base commit the oracle's specs stop at import, because the module is new, so the move commit is where each case shows its own fault | Fowler, 2026-10-07 (found during execution) |
| 8 | The edit to `TailTrendPanel.svelte`, held by row L26, waits for L26 to merge. Then this branch merges `origin/main`, adds the prop and the branch so that no chart prints "Nothing changed ..." while the score-read line prints, runs its checks and pushes. The pull request is not ready for review before that. Done after L26 merged as #1400 | The owner, 2026-10-07 (option A2) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Faults 1 and 2 leave a false line or a silent gap on Hardware today, and fault 3 waits for the first change to `observability.sample_rate` | Nothing to build, and two false lines in the 30- and 90-day windows | Row L22's report; the owner, 2026-10-07 |
| 2 | A row for each fault | Each row would decide again what Hardware may claim from its records, and three rulings on one question can disagree | Three smaller reviews | The owner, 2026-10-07 |
| 3 | Count a run as one with the server's counters where the machine record holds a row for it (Fowler's A1) | The runs of 17 to 19 Sep 2026 hold the probe and the clocks and no server cell, so the lines would claim figures nobody wrote | Three days that read as having the server's figures | Fowler, 2026-10-07 |
| 4 | Lead the intro with the runs that have the server's counters (Fowler's I2) | The first number would not count the runs the panels draw, and the test row L26 holds needs the first number to grow from the 7- to the 90-day window on the canary, whose two runs 40 days back have no server counters | One number in the intro, and an edit in a file row L26 holds | Fowler, 2026-10-07 |
| 5 | Hand the score record to Hardware's record notes (Fowler's B1 and B2) | Their words say nothing below that uses the record has anything to show, false while the charts draw; B1 adds five notes about a record Hardware draws no figure from, and B2 prints where no marker is lost | No new function | Fowler, 2026-10-07 |
| 6 | Tie the sampling rate to the instrument in `recordingNotes`' facts type, or only edit the route (Fowler's C2 and C3) | C2 ties sampling to `missing`, a field that means something else, and still leaves what Hardware hands untested; C3 leaves the Hardware half with no test that can fail | No new module | Fowler, 2026-10-07 |
| 7 | Say a lost marker once, at the top of the page (Jony's P1) | The gap matters only at the two charts' rules, in two groups far below the intro, and Hardware uses the score record for nothing else | One line instead of one on each chart | Jony, 2026-10-07 |

### Row #L29 - Hardware's refused-runs box says what reads a refused run

- **Scope:** Hardware's refused-runs box says only what is true of what reads a refused run. The row measures first, and changes the box's words only if the measurement shows them false. Level 1.
- **The fault** (row L22's fourth follow-up, reasoned from the code and not measured, 2026-10-07): the box says a refused run is "left out of every windowed figure on this page" and that "nothing here reads the run at all", but the route hands the figures built on the article record their rows by date alone. `healthRows` in `frontend/src/routes/console/machine/+page.server.ts` keeps every article row in the window, and `readAgainstWritten` in `frontend/src/lib/charts/machine.ts` keeps every row with token counts, whatever its run. In the canary build the days row L22's line names on Hardware are exactly the refused runs' days, so if the box is false, two lines on one screen disagree.
- **Files touched** (found by a search on `main` at 6861bbd21 for the box's words, `healthRows` and `readAgainstWritten`; searched again at dispatch, on `main` at 3b83c0951, after L28: the same files, and `healthRows` still feeds the same six figures):
  - `frontend/src/routes/console/machine/+page.svelte` (the box: "{n} runs are left out of every windowed figure on this page." and "... so nothing here reads the run at all."; changed only if the measurement shows them false. Changed: it prints the words `describeRefusedRuns` returns; decision 5)
  - `frontend/tests/console-machine.spec.ts` (the measurement, beside its `readAgainstWritten` cases, and the two cases that check the box's words against it)
  - `frontend/src/lib/console/machine/refused-runs.ts` (new, found during execution: `describeRefusedRuns` writes the box's words from the open window's refused runs, so a test reads them; decision 5)
  - `docs/concepts/console-design.md` (found during execution: what the box may claim, and who chose its words)
  - Left as they are, unless the measurement shows otherwise: `frontend/src/routes/console/machine/+page.server.ts`, which hands the box `counters.refused` and hands `healthRows` to `readAgainstWritten`, `contextCost`, `articleCost`, `processorLostOverDays`, `diskReads` and `promptReuse`; `frontend/src/lib/charts/machine.ts`; `frontend/src/lib/server/machine-counters.ts`, which refuses a run. All three are left as they are: the row fixed the words, not the figures
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-machine.spec.ts`; if the box changes, `npm --prefix frontend run check` and the browser smoke of Hardware on the canary build, whose refused runs show the box. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-machine.spec.ts`, on rows the test builds (Table D, D3): a run that `machineCounters` refuses, whose article rows carry token counts, is handed to each figure the route builds from `healthRows`, and the box's words are checked against which of them count it. By the code, `readAgainstWritten` counts it while the box says nothing reads it, which is what lets this check fail if the reasoning holds. It cannot settle the words, which Reader chooses (decision 2).
- **The measurement** (2026-10-07, on rows the test builds): one run that `machineCounters` refuses, because shard 1 filed two machine records that disagree, and one run it accepts, on one day. Each of the six figures took the article rows of both runs, then of the accepted run alone. All six count the refused run, so the box was false. What a run reads against what it writes gives it a run of its own, 10,000 tokens read and 600 written. The reading limit's never-used share falls from 73 to 23 percent, and its cut-off calls rise from 0 to 2. The cost of one article takes its highest processor time (60 to 120 processor-seconds), model time (23 to 42 seconds) and memory step (100 MB to 400 MB) from it. The processor lost to other tenants names the day for a share only the refused run's article lost, 12 percent. The waits for the disk rise from 0 to 4,100, and the refused run counts as one that did not hold the model's memory down. The prompt reuse takes its floor from it, 80 percent down to 0. On the base commit the oracle's spec stops at import, because `refused-runs.ts` is new; with that module holding `main`'s words, its two box cases fail and the seven measurement cases pass.
- **Follow-ups** (found during execution):
  - Row L22's line "No server figures were written down for {days}." is false on a day whose only run the counters refuse while its machine record holds server figures: they were written down, twice, and disagree. Measured with a throwaway case on built rows: with shard 0 of the only run on 14 Jun 2030 filing two machine records that disagree, the line named 14 Jun. Its day rule takes the server's recorded days from the runs the counters keep. Reader found the same, and said the row that owns that line should fix it (Reader, 2026-10-07).
  - The cost of one article joins each article to its shard's processor count with no run left out. Where a refused shard's two machine records name different counts, the join keeps whichever comes last, which is the pick between two servers that the refusal exists to refuse. A candidate for a figure that should leave refused runs out. Reasoned from the code, not measured; not ruled.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measure first. If no figure the route builds from the article record counts a refused run, the box is true: the row closes with the measurement and changes nothing | The owner, 2026-10-07 |
| 2 | Reader chose the words. The head: "1 run has records that do not fit together. The run count above does not include it. Figures that pick articles by date still include the articles of this run.", and for several "{n} runs have records that do not fit together. The run count above does not include them. Figures that pick articles by date still include the articles of these runs." After each run id, in bold: "has {rows} rows: {why}.", or "has 1 row: {why}.". "Summing them would report a machine that never existed" goes: it does not fit two of the six reasons, and it suggests the page adds up nothing from the run. The box stays where it is, because "the run count above" is true only under the first line; no place moved, so Jony was not asked | Reader, 2026-10-07 |
| 3 | L29 waits for L22 (#1385), whose worker found the fault and whose line names the refused runs' days on the canary | The owner, 2026-10-07 |
| 4 | Level 1: the words of one box on one route; a wrong version is obvious and local | The owner, 2026-10-07 |
| 5 | The words move out of the page into `describeRefusedRuns` in the new `refused-runs.ts`, which the page calls with the open window's refused runs, so a test reads them: a route's server module may export only its load, and no test can read a template (row L22, decision 3). The route's server module does not change. Two commits: the move with today's words, then Reader's words with the cases that check them | This row's worker, on row L22's decision 3, 2026-10-07 (found during execution) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The finding is reasoned and not measured, and if it holds, the box and row L22's line disagree on one screen | Nothing to build, and a box that may say something false | Row L22's report; the owner, 2026-10-07 |
| 2 | Change the words without measuring | The box may be true, and new words would then make it false | One sentence changed blind | The owner, 2026-10-07 |

### Row #L30 - The merge line's no-fit rule names the line a build used

- **Scope:** With no fitted day in the window, Judgement's merge line panel draws its dashed rule at the line a build used and labels it so, instead of at the committed floor. Level 1.
- **The fault** (row L27's first follow-up, 2026-10-07): with no fitted day in the window, `MergeLinePlot.svelte` draws the dashed rule at `configuredLine`, the committed floor, `floor_min` in `config/idhazh.json`, and labels it the line the newest day was built with. A build uses the newest line a fit applied in the `applied_lookback_days` days before it, skipping a held day, and the committed floor only when there is none (`applied_line()` in `backend/idhazh/similarity/applied.py`). So at the 1-day window, after a line was fitted in those days, the rule and its sentence name the wrong line. While `adaptive_dedup_threshold.enabled` is false, every build uses the committed floor, so today the rule shows nothing wrong.
- **Files touched** (found by a search on `main` at 6861bbd21 for `configuredLine`, `ruleDay`, `committedFloor` and `applied_line`; search again at dispatch):
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte` (the dashed rule at `configuredLine`, its label "The line {ruleDay} was built with", and the sentence "No line was fitted in {span}. The rule is the line {ruleDay} was built ...")
  - `frontend/src/routes/console/judgement/+page.svelte` (hands `MergeLinePlot` `configuredLine={data.configuredLine}`; unchanged, found during execution: it already hands `knobs={data.similarity}`, which carries the switch and the lookback)
  - `frontend/src/routes/console/judgement/+page.server.ts` (`configuredLine` is `committedFloor()`; `lines` carry each fitted day's `applied` and `heldReason` over the widest preset; `similarity` is `similarityConfig()`, which reads the committed `adaptive_dedup_threshold` block, `enabled` and `applied_lookback_days` with it)
  - `frontend/src/lib/server/config.ts` (found during execution: `SimilarityConfig` now declares `enabled` and `applied_lookback_days`, which `similarityConfig()` already carried, so the panel can read them typed; their defaults are the contract's, off and 7)
  - `frontend/tests/console-window.spec.ts` (row L27's built `merge-line` cases; held by L26 while it runs)
  - Left as they are: `backend/idhazh/similarity/applied.py`, whose `applied_line()` is the rule a build follows; `config/idhazh.json`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on days the test builds (Table D, D3): with the flag on, a 1-day window with no fitted day, 3 days after a day that fitted a line it did not hold, draws the rule at that day's applied line; with no fitted line in the lookback, at the committed floor; and with the flag off, at the committed floor whatever the record holds. On `main` the first case draws the rule at the committed floor, which is what lets this check fail. It cannot settle what a build did on a given day; the rule follows `applied_line()`'s rule, not a build's own record.
- **Follow-ups** (found during execution):
  - `VerdictSplit.svelte` and `HoldoutMargin.svelte` call their `applied` "The line the newest day was built with", and the route hands them `data.lines.at(-1)?.applied`, the newest row's line, whatever the switch says. With the switch off, every build uses the committed floor; with it on, a held newest row, or one older than the lookback, is not the line a build used. Latent while every row applies the floor, as every committed row does today. A Level 1 row: hand both the line `applied_line()` gives the newest published day.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L27's first follow-up | Row L27's report; the owner, 2026-10-07 |
| 2 | The rule takes the line `applied_line()` gives a build on the window's last day: with the flag on, the newest line a fit applied in the `applied_lookback_days` days before it, skipping a held day; otherwise the committed floor | Plan author, 2026-10-07, from row L27's report |
| 3 | The label and the sentence keep row L27's words (row L27, decision 1), which this row makes true; a sentence that must change goes to Reader (CLAUDE.md section 14) | Plan author, 2026-10-07 |
| 4 | L30 waits for L27 (#1388), which wrote the label and the sentence and built the `merge-line` cases in `console-window.spec.ts`, and for L26, which holds that spec | The owner, 2026-10-07 |
| 5 | Level 1: one rule on one panel, and it shows nothing wrong while the merge flag is off, because every build then uses the committed floor. Row L27's report proposed Level 2 | The owner, 2026-10-07 |
| 6 | The panel works the line out itself, from the rows, the switch and the lookback it is handed and the window's last day. A build reads its own day and the `applied_lookback_days` before it, as `days_in_window` names both ends, so 7 is 8 days | Found during execution |
| 7 | The Oracle is four cases in `console-window.spec.ts`, each the 1-day window on 15 Jun 2030 with a lookback of 7, a floor of 0.94 and written-out lines: the switch on and a line fitted 3 days before (the rule at 0.937); a line fitted 7 days before, the first day the build read (0.937); the one fitted line 8 days before and a held day inside the lookback (0.940); the switch off and a line fitted 3 days before (0.940). Each also checks the label and the sentence word for word. On `main` at 28893944f the first two fail with the rule at 0.940; on this branch all four pass | Found during execution (Table D, D3) |
| 8 | No persona was asked: no word changed, and each fork in Rejected alternatives 4 and 5 changes nothing while every committed row applies the floor | Found during execution |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Once the flag is on, a window with no fitted day names the committed floor as the line a build used, while the build used a fitted one | Nothing to build, and a wrong line named on Judgement from the day the flag is switched on | Row L27's report; the owner, 2026-10-07 |
| 2 | Draw the rule at the line the route hands `VerdictSplit` and `HoldoutMargin`, `data.lines.at(-1)?.applied` | It is the newest fitted row over the widest preset, which can be older than the `applied_lookback_days` a build reads, so it can name a line no build used | One expression, and three panels that name one line | Plan author, 2026-10-07 |
| 3 | Work the line out on the route and hand the panel one number | The window is chosen in the browser, so its last day is the panel's to know, and the Oracle reaches the rule only through the props it builds | One number on the route, and a rule no built case can drive | Found during execution |
| 4 | Read every run of each date, as `applied_line()` does | The route keeps the newest run of each date, the run the panel draws, and the two differ only when a date fitted, then was held on a re-run. A re-run writes the same row unless the record's inputs changed between the two nights (`set_merge_line.py`) | One field on `fittedLines` and one prop on the panel | Found during execution |
| 5 | Widen the route's read of the fitted rows to `applied_lookback_days + 1` days where the widest preset is shorter | The read of the widest preset holds every row the lookback reads while `applied_lookback_days` is under that preset, 7 under 90 today, because no row is dated after the newest published day | `Math.max` on one read, and two panels, `VerdictSplit` and `HoldoutMargin`, then reading rows older than the widest preset | Found during execution |

### Row #L31 - The record's bars say when a window holds no row

- **Scope:** When the open window holds no row of the record, Judgement's record panel says so, instead of drawing its three bars at zero, the picture its header comment keeps for a record that emptied. Level 2.
- **The fault** (row L27's second follow-up, 2026-10-07): the three bars read the newest row inside the window, `newest` in `RecordGates.svelte`, through `gateNeeds` in `frontend/src/lib/console/merge-line.ts`. So a window with no row draws all three at zero, while the running record still holds what earlier rows counted. The panel's header comment says that bars falling back to zero are the one picture of a record that emptied, because a weight moved and the fit archived it.
- **Files touched** (found by a search on `main` at 6861bbd21 for `gateNeeds` and `newest` in the record panel; search again at dispatch):
  - `frontend/src/routes/console/judgement/RecordGates.svelte` (`newest`, the newest row inside the window; the header comment on falling bars; found during execution: the bars read `standing`, the newest row on or before the window's last day, and the note gains a state of its own, `earlier`)
  - `frontend/src/lib/console/merge-line.ts` (`gateNeeds` gives three zeros for no row; found during execution: `gateNeeds` is unchanged, as decision 3 needs, and the file gains `findNewestRow`, the row the bars read, and `describeEarlierRow`, the note's words)
  - `frontend/tests/merge-line.spec.ts` ("a record with nothing in it still draws three bars at zero" holds `gateNeeds(null, ...)` at zero; found during execution: unchanged, and a test each for `findNewestRow` and `describeEarlierRow` joins it)
  - `frontend/tests/console-window.spec.ts` (row L27's built `record-gates` cases; held by L26 while it runs)
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` (found during execution: the bars now read one row at every preset, so the panel joins the table of surfaces that do not simply follow the span, and the rulings go into its design rationale)
  - `docs/reference/agent-notes/gates-and-builds.md` (found during execution: a spec run in a copy of the base commit needs SvelteKit's generated paths first, or every `$lib` import fails)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts --spec merge-line.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on days the test builds (Table D, D3): a 1-day window on a day with no row, after earlier rows counted readings, days and pairs, does not draw three bars at zero and says what Reader rules; a record that never held a row still draws three bars at zero; and a window whose newest row counts zero, a record that emptied, still draws zero. On `main` the first draws three bars at zero, which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L27's second follow-up | Row L27's report; the owner, 2026-10-07 |
| 2 | Reader chooses the words, and Jony rules what the bars draw for a window that holds no row, where two answers would lead to different code (CLAUDE.md section 14) | Jony, then Reader, 2026-10-07, after one debate round, with nothing left split. Jony: the bars read the record's newest row dated on or before the window's last day, with their normal fill, because the record changes only when a run writes a row, so that row is what it holds; `gateNeeds` and `TargetBar` do not change; the strip and the count of fitted days still read only the window's rows; the note gains one state, which names that row's day, says no run has recorded anything since, and counts no quiet days; "Nothing was judged" stays for a panel handed no row at all; the header comment says the bars stand on that row, and only a record that empties or never held a row draws them at zero. Reader: "The bars show what the record held on 14 Jun 2030, before this one day. No run has recorded anything since." ("..., before these 7 days." at 7 days), the same words when that row has what it needs, and "The record was started again on 14 Jun 2030, before this one day. No run has recorded anything since." only where that row's hold reason says so, because zeros alone do not prove it. No "No line was fitted" sentence and no counts in words: the bars print them. The debate round added "before {span}": Reader's first words named no window, and row L27's window oracle needs every windowed panel's body to name its days |
| 3 | Three bars at zero stay the picture of a record that never held a row, as `merge-line.spec.ts` holds: a panel that waits for data before it draws teaches an operator that the measurement does not exist | Plan author, 2026-10-07, from the test's own reason |
| 4 | L31 waits for L27 (#1388), which wrote the record panel's sentences and built the `record-gates` cases in `console-window.spec.ts`, and for L26, which holds that spec | The owner, 2026-10-07 |
| 5 | Level 2: what the bars draw for no row is held by a test of its own, and the panel's header comment reads bars at zero as a record that emptied. Row L27's report proposed it | The owner, 2026-10-07 |
| 6 | The bars now read one row at every preset, because every window ends on the newest published day, so the panel joins the table of surfaces that do not simply follow the span in `which-console-surfaces-follow-the-window-and-which-say-why-not.md`, whose design rationale records the rulings. No line of `docs/concepts/console-design.md` changes | Found during execution |
| 7 | The Oracle: three cases in `console-window.spec.ts` render the panel with its real children from days the test builds, and check the three bars' counts and the note written out whole: a 1-day window with no row after rows on 12 and 14 Jun 2030 (120, 6 and 12), a record that never held a row (0, 0 and 0), and a record that emptied on the window's day (0, 0 and 0). Row L27's 1-day case of a window with no row takes Reader's words, and a 7-day case joins it | Found during execution (Table D, D3) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | A window with no row draws the picture the header comment keeps for a record that emptied | Nothing to build, and a false picture on Judgement at every window that holds no row | Row L27's report; the owner, 2026-10-07 |
| 2 | Dash the bars: each prints "-" and a line in place of its track, the target bar's own state for a value nobody measured | The operator loses how far the record is from each gate, the panel's one question, although the page holds the exact count | A second kind of empty in `gateNeeds`, and the same line under three bars | Jony, 2026-10-07 |
| 3 | Draw the earlier counts in a muted fill | It makes an exact value look doubtful, to say what the date already says | A second kind of target bar, which every other target bar on the console would have to stay apart from | Jony, 2026-10-07 |
| 4 | Draw no bars while the window holds no row | It breaks "the empty state is the panel", and the panel changes height with the window | One branch less | Jony, 2026-10-07 |
| 5 | A note that names no window (Reader's first words) | Row L27's window oracle needs the body of every windowed panel to name its days, and nothing else in the body does in this state | Three words fewer | Reader, 2026-10-07, in the debate round |

### Row #L32 - Judgement's agreement strip prints no share below five pairs

- **Scope:** On Judgement's agreement panel, the strip prints no share for a day that read fewer pairs than `console.min_attempts_for_rate` (5), the floor under which the sentence below it already prints no share. Level 1.
- **The fault** (row L27's third follow-up, Reader's, 2026-10-07): in the state "too few to report a share", the strip above the sentence prints a share of fewer than 5 pairs, such as "25% of 4 pairs". The strip's two series in `JudgeAgreement.svelte` print each day that read a pair as "{share} of {n} pairs", while `rateWithDenominator` in `frontend/src/lib/console/merge-line.ts`, which the sentence uses, gives no share under the floor, because a share over four pairs is not a measurement.
- **Files touched** (found by a search on `main` at 6861bbd21 for "too few to report a share", `rateWithDenominator` and the strip's `format`; search again at dispatch):
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (the strip's two `format` functions; `attemptsFloor`, which is `console.min_attempts_for_rate`; and, found during execution, `daySentence`, the accessible name of each day's dots, which printed the same share. One function, `readingsOf`, now writes the strip's words and the dots' name together)
  - `frontend/tests/console-window.spec.ts` (row L27's built `judge-agreement` cases; held by L26 while it runs; six new cases beside them, decision 8)
  - Left as it is: `frontend/src/lib/console/merge-line.ts`, whose `rateWithDenominator` holds the floor's rule
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on days the test builds (Table D, D3): a day that read 4 pairs prints no share in the strip, in Reader's words, and a day that read 5 prints its share; the sentence under the strip does not change. On `main` the 4-pair day prints "25% of 4 pairs", which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 2).
- **Follow-ups** (found during execution):
  - Above the floor, "Could not tell" names the wrong denominator. Its share is of the pairs whose two readings agreed (`unclear_rate` in `backend/idhazh/stages/set_merge_line.py`), but the strip prints it as "{share} of {pairs read twice} pairs", and the sentence under the strip weights each day's share by the pairs read twice. The agreed count is on the fitted row (`pairsUsable` in `frontend/src/lib/server/similarity-ledger.ts`) and not on `JudgeDay`; `readingsOf` works it out for a day under the floor. Reader's words for the strip: "0% of the 38 that agreed". A Level 2 row, with Reader's words for the sentence.
  - The chart still draws a day under the floor at its two shares' heights, and both lines pass through it, so the axis reads "25%" where the strip says "1 of 4 pairs". The failure chart breaks its line at such a day (`docs/architecture/publishing/console-charts.md`). Jony to rule whether such a day's dots are drawn, drawn hollow or left out. A Level 1 row.
  - The live Judgement page reads no fitted row. `dayShardFiles` in `frontend/src/lib/server/payload.ts` takes only a day folder of writer files, `YYYY/MM/DD/<writer>.csv`, while the committed fitted-threshold files and their entries in `frontend/public/publication.json` are `YYYY/MM/DD.csv`. On 2026-10-07 the live page said "No pair was read twice in these 14 days" while the ledger held 57 pairs on 5 Oct and 46 on 6 Oct, and the merge line and the record panel read no row either. Plan 59's fitted-threshold row lists `similarity-ledger.ts` and `readDayShards`. A Level 2 row, or that row; the owner places it.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is Reader's own follow-up in row L27 | Reader, 2026-10-07 (row L27's report) |
| 2 | Reader chooses the words (CLAUDE.md section 14) | Reader, 2026-10-07, in one ruling with nothing left split. A day of fewer than 5 pairs prints its counts and no share, in the same words at every window. "Disagreed with the second reading" reads "1 of 4 pairs", and "1 of 1 pair" for one pair. "Could not tell" reads "0 of the 3 that agreed", counted against the pairs whose two readings agreed, the pairs its share is taken over; where every pair disagreed it reads "not counted, no pair agreed", because a 0 there may be false. The dots' accessible name: "15 Jun: 1 of 4 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell."; where no pair agreed, "15 Jun: 1 of 1 pair disagreed with the second reading. Could not tell: not counted, no pair agreed." A day of 5 pairs or more keeps its share, "5% of 40 pairs". Reader's reason: under 5 pairs a percent claims more than a few pairs can show, and the counts make the sentence's "so the counts are above" true. Every value is written out whole in `console-window.spec.ts` |
| 3 | The strip's floor is `console.min_attempts_for_rate`, the one the sentence under it uses, so the two never disagree about when a share is a measurement | Plan author, 2026-10-07 |
| 4 | L32 waits for L27 (#1388), which wrote the sentence and built the `judge-agreement` cases in `console-window.spec.ts`, and for L26, which holds that spec | The owner, 2026-10-07 |
| 5 | Level 1: the words of one strip on one panel; a wrong version is obvious and local | The owner, 2026-10-07 |
| 6 | The dots' accessible name follows the strip under the floor. The panel's own comment says the strip and the dots carry the same words, and a screen reader would otherwise still hear "25% of 4 pairs". One function writes both | Found during execution; Reader, 2026-10-07 |
| 7 | The counts come from the day's own row, with no field added to `JudgeDay`: disagreed is its share times the pairs read twice; agreed is the pairs read twice less those that disagreed, because a pair agrees exactly when its two readings match (`usable` in `backend/idhazh/contracts/story_similarity_pair.py`, and the shares in `backend/idhazh/stages/set_merge_line.py`); could not tell is its share times agreed | Found during execution |
| 8 | The Oracle is six cases in `console-window.spec.ts`, beside row L27's `judge-agreement` cases, that render the panel with its real children from days the test builds. Each checks, written out whole, the strip's heading and two entries, the name of every drawn day's dots, and the sentence under the strip. At the 1-day window: a day of 4 pairs, of 5 pairs, of 1 pair whose two readings disagreed, and of 4 pairs where 1 of the 2 that agreed could not tell. At the 7-day window: a newest day of 4 pairs in a window of 44, and a window of 3 pairs. On `main` the five cases under the floor fail, printing shares such as "25% of 4 pairs" and "0% of 1 pairs", and the 5-pair case passes | Found during execution (Table D, D3) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The strip prints a share that the sentence under it calls too few to report | Nothing to build, and two readings of one day on one panel that disagree | Row L27's report; the owner, 2026-10-07 |
| 2 | A floor of the strip's own | Two floors for one rule drift apart, and the strip and the sentence would disagree again | A second knob in `config/` | Plan author, 2026-10-07 |

### Row #L33 - Every sentence for a record the door answers missing says it is not packed yet

- **Scope:** Every sentence the console prints for a published record or ledger that the door answers `missing` says it is not packed yet, never that it is not published or not on this site; a ledger outside `ledger.published` keeps the words that say it is not on this site. Level 1.
- **The fault** (row L25's ruling, 2026-10-07): since L7 (#1370), a published ledger with no compact folder answers `missing`, so for a published record `missing` means not packed yet (Table F, F1). Row L25 fixed the platform-mix panel's line. A search of `frontend/src/` on `main` at 6861bbd21 finds three more:
  1. `faultLine` in `frontend/src/lib/data/slice-reader.ts` (line 153), the browser-console line for `not-packed`: "it is not there: this record is not packed, or not published. Turn on whichever is off, or wait for the next upkeep run." A slice or a reach is read for a panel, which reads only published ledgers, or at build time, which reads every committed ledger, so "not published" is never why.
  2. `statusSentence` in `frontend/src/lib/console/explorer/status.ts` (line 67), the data explorer's action line for `missing`: "Did not run. {ledger} is not on this site yet." The page prints it for every `missing` answer (`+page.svelte` line 166), while the answer under it says "{ledger} has no days on this site yet." for a published ledger (`explorerMissingSentence` in `frontend/src/lib/console/waiting.ts`).
  3. The data explorer's chart panel for a `missing` answer (`frontend/src/routes/console/data-explorer/+page.svelte` line 647): "Part of the data is not on this site, so nothing to draw."
- **Files touched** (found by a search on `main` at 6861bbd21 under `frontend/src/` for "not published", "unpublished" and "not on this site", and for the tests and pages that pin those sentences; search again at dispatch):
  - `frontend/src/lib/data/slice-reader.ts` (sentence 1)
  - `frontend/src/lib/console/explorer/status.ts` (sentence 2)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (hands `statusSentence` the `missing` ledger, and holds sentence 3)
  - `frontend/tests/console-data-explorer-still.spec.ts` (pins sentence 2 for a ledger named `published`)
  - `frontend/tests/ledger-door.spec.ts` (the door's `missing` and `not-packed` cases; no test reads sentence 1 today)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (lines 49 and 199 say a panel's `missing` is a ledger that "is not published, or it is published and not packed yet")
  - Left as they are: `frontend/src/lib/console/waiting.ts`, whose `explorerMissingSentence` already says "has no days on this site yet" for a published ledger and "is not on this site yet" only for one that is not; `frontend/src/lib/console/explorer/LedgerList.svelte`, which says "not on this site" only for a ledger outside `ledger.published`; `frontend/src/lib/console/explorer/days-read.ts`, which speaks of days the site copy trimmed; `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, row L25's line; `frontend/src/lib/console/recording.ts`, whose route note says the record has not been packed yet
  - Row L21 lists `status.ts`, the explorer page and `console-data-explorer-still.spec.ts` too, so the two rows run one at a time (Table A, A6)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-data-explorer-still.spec.ts --spec ledger-door.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the data explorer and of the Hardware route with a published ledger's index requests answered 404, reading the page and its browser console. CI: the pull request runs what `ciAnswer` selects; every group runs on the merge push.
- **Oracle:** in `ledger-door.spec.ts` and `console-data-explorer-still.spec.ts`, on answers the test builds (Table D, D3): the `not-packed` console line says the record is not packed yet and never "not published"; the explorer's action line for a published ledger that the door answers `missing` never says it is not on this site, and for a ledger outside `ledger.published` still does. On `main` the first says "not packed, or not published" and the second says "is not on this site yet" for both, which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | For a published record, `missing` means not packed yet, never not published, since L7 (#1370) | Row L25, decisions 1 and 3; the owner, 2026-10-07 |
| 2 | Reader chooses the words (CLAUDE.md section 14), as row L25's "The machine record is not packed yet." did, in the route note's own words and never "published", and rules whether sentence 3 reads as not published | To be ruled at dispatch (Reader) |
| 3 | L33 waits for L25 (#1384), which settled what `missing` means and fixed the platform-mix panel's line | The owner, 2026-10-07 |
| 4 | Level 1: the words of three lines; a wrong version is obvious and local | The owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The console line tells an operator that a published record may not be published, and the explorer's action line says a published ledger is not on this site above an answer that says it has no days here yet | Nothing to build, and two lines that point a person at the wrong fix | Row L25's report; the owner, 2026-10-07 |

### Row #L34 - The rest of the console reads right at the one-day window

- **Scope:** At the 1-day window, the console surfaces that row L26 left read right under the one-day rule in `docs/concepts/console-design.md`, in Reader's words: Voices' two record strips, Hardware's processor-lost strip, the stage timings note on Pipelines, the titles and the cost switch that say "day by day", and two notes on Judgement that speak of lines. Level 1.
- **The sentences** (row L26's follow-ups, each found on its smoke at the 1-day window, 2026-10-07; read again on `main` at 7ba988fc2):
  1. Voices' two record strips, in `frontend/src/routes/console/voices/+page.svelte`, rest on ", its newest day", and their hints say "Left and Right step through a feed's days" and "Left and Right step through a source's days". Each `ChartReadout` is handed one record at a time, so the one-column rule in `frontend/src/lib/components/ChartReadout.svelte`, which counts the strip's own columns, does not reach it.
  2. Hardware's processor-lost strip, in `frontend/src/lib/console/machine/ProcessorLostPanel.svelte`, is also handed one record at a time. It rests on ", the newest day" when its verdict names no day, its hint says "Up and Down move between days and shards", and the tiles' label says "one tile a day and one a shard of the newest run. Arrow keys read a tile, Escape returns to rest."
  3. The stage timings chart on Pipelines, in `frontend/src/lib/components/StageTimings.svelte`, says "Median per item, each day."
  4. Two titles and a control say "day by day": "Which machines ran our jobs, day by day" (`frontend/src/lib/console/machine/PlatformMixPanel.svelte`); "Summary faithfulness, day by day" (the heading in `frontend/src/routes/console/model/+page.svelte`, and `EVAL_PANELS` in `frontend/src/lib/console/eval-instruments.ts`); and the cost switch's "Day by day" (`COST_SHAPES` in `frontend/src/lib/charts/cost.ts`, drawn on Hardware by `frontend/src/lib/console/machine/CounterfactualCostPanel.svelte`). Row L26 held that a title names the panel, not the days on screen; Reader rules whether that holds.
  5. Two notes speak of lines where one day draws a point: "One line is how often the two readings differed. The other is how often the reading could not tell." (`frontend/src/routes/console/judgement/JudgeAgreement.svelte`) and "The solid line is ... The dotted line is ..." (`frontend/src/routes/console/judgement/MergeLinePlot.svelte`).
- **Files touched** (from a search on `main` at 7ba988fc2 for the words above and the tests that pin them; search again at dispatch):
  - `frontend/src/routes/console/voices/+page.svelte` (sentence 1)
  - `frontend/src/lib/components/ChartReadout.svelte` (sentences 1 and 2, only if a strip handed one record at a time joins its one-column rule)
  - `frontend/src/lib/console/machine/ProcessorLostPanel.svelte` (sentence 2)
  - `frontend/src/lib/components/StageTimings.svelte` (sentence 3)
  - `frontend/src/lib/console/machine/PlatformMixPanel.svelte`, `frontend/src/routes/console/model/+page.svelte`, `frontend/src/lib/console/eval-instruments.ts` and `frontend/src/lib/charts/cost.ts` (sentence 4, only where Reader changes a title or the switch)
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (sentence 5; held by L32 while it runs)
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte` (sentence 5; held by L30 while it runs)
  - `frontend/tests/console-window.spec.ts` (row L26's built cases, one of which pins the merge line's note; held by L30, L31 and L32 while they run)
  - `frontend/tests/span-sentences.spec.ts` (row L26's logic cases, for a sentence a function writes)
  - `frontend/tests/console-machine-panels.spec.ts` (pins "Which machines ran our jobs, day by day")
  - `docs/concepts/console-design.md` (the one-day rule, where Reader's ruling adds to it)
  - Left as they are, unless Reader rules otherwise: the data explorer's example "Summaries scored, day by day" (`config/appearance.json`, with its default copies in `backend/idhazh/contracts/knobs/console.py` and `frontend/src/lib/server/config.ts`), which opens at its own 14 days; `frontend/src/lib/charts/glance.ts`, whose "day by day" already drops at one measured day
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; `doc_load.py` on the page if it changes; the browser smoke of Voices, Hardware, Pipelines, Summaries and Judgement at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts` and `span-sentences.spec.ts`, on data the test builds (Table D, D3): at the 1-day preset each surface above reads right under the one-day rule, in Reader's words written out whole, and at 7 days each is unchanged. On `main` the 1-day cases print the words above, such as ", its newest day" on Voices and "One line is how often ..." on Judgement, which is what lets this check fail. It cannot settle the words, or whether a title keeps "day by day"; Reader rules (decision 1).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words, and rules whether a title or the cost switch that says "day by day" keeps it at one day (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 2 | The surfaces are row L26's follow-ups, each found on its smoke at the 1-day window | Row L26's report; plan owner, 2026-10-07 |
| 3 | L34 waits for L26 (#1400), which set the one-day rule and the one-column rule in `ChartReadout.svelte`, and for L30, L31 and L32, which hold files it touches (the Depends-on cell names each) | Plan owner, 2026-10-07 |
| 4 | Level 1: words on panels, one surface at a time; a wrong version is obvious and local | Plan owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | At the 1-day window these surfaces still name a newest day, keys that need a second day, or lines where one day draws a point | Nothing to build, and readings at one day that need a second day | Row L26's report; plan owner, 2026-10-07 |
| 2 | A row for each surface | Each row would ask Reader to apply one rule again, and five rulings on one rule can disagree | Five smaller reviews | Plan owner, 2026-10-07 |

### Row #L35 - Pipelines' failure and time-split panels follow the window or say why not

- **Scope:** On Pipelines, "What is failing, by stage" and "Where an item's time went" either draw the window's days or say on the page why they draw more, as Jony rules, and `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` names whichever is true. Level 2.
- **The fault** (row L26's follow-up, found on its smoke, 2026-10-07; read again on `main` at 7ba988fc2): both panels draw every day the page holds, not the window. In `frontend/src/routes/console/+page.svelte`, `mixSeries` is `failureSeriesFor(rows)` and `timeDays` is `timeSplit` over `datesIn(rows)`, where `rows` is every row the page holds (`holdRows(hold)`) and the window's rows are `rowsInView`. At the 1-day preset the canary drew 12 and 3 columns, so the strips' newest-day headings and keys are true of what they draw. Neither panel is in the window page's table of surfaces that do not simply follow the span, neither says so on the page, and `docs/architecture/publishing/what-the-pipelines-route-draws.md` says of the failure mix that a window holding one day is one column.
- **Files touched** (from a search on `main` at 7ba988fc2 for the two titles, `mixSeries`, `timeDays`, `rowsInView` and the window page's table; search again at dispatch):
  - `frontend/src/routes/console/+page.svelte` (`failureSeriesFor`, `mixSeries` and `timeDays`, and the two panels' snippets, `failureMixPanel` and `itemTimeSplitPanel`)
  - `frontend/src/lib/charts/Chart.svelte` (since L26, a chart that follows the window takes the window's days from its route, and these two take none)
  - `frontend/tests/console-window.spec.ts` (its exact list of surfaces that declare `data-windowed`, or a built case for the sentence that says why not; held by L30, L31 and L32 while they run)
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` (the page that names the answer; its table of surfaces that do not simply follow the span holds one on Pipelines today)
  - `docs/architecture/publishing/what-the-pipelines-route-draws.md` (its section "What is failing, by stage")
  - Read, no change unless the ruling needs one: `frontend/src/lib/charts/glance.ts` (`failureMix`, `failureMixColumns`, `timeSplitChart` and `timeSplitColumns`) and `frontend/src/lib/charts/series.ts` (`timeSplit`, `datesIn` and `rowsInWindow`)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list`, then the specs it selects for the changed files; `npm --prefix frontend run check`; `doc_load.py` on the two pages; the browser smoke of Pipelines at the 1- and 7-day presets, and with its fetched data answered 404. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on data the test builds (Table D, D3): on a page that holds more days than the 1-day window, each panel either draws one column or prints the sentence that says why it draws more, as Jony rules, and at 7 days the same holds for seven. On `main` both draw every day the page holds and say nothing of it, which is what lets this check fail. It cannot settle which answer is right; Jony rules (decision 1).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Jony rules whether the two panels follow the window or say on the page why not (CLAUDE.md section 14). This row decides neither | To be ruled at dispatch (Jony) |
| 2 | Whichever Jony rules, `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` names it, as it names every surface that does not simply follow the span | Plan owner, 2026-10-07 |
| 3 | Reader chooses any words the ruling needs (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 4 | L35 waits for L26 (#1400), whose smoke found the two panels and whose `Chart.svelte` gives them no window's days, and for L30, L31 and L32, which hold `frontend/tests/console-window.spec.ts` | Plan owner, 2026-10-07 |
| 5 | Level 2: either answer changes what two panels draw or say, and `console-window.spec.ts` holds the exact list of surfaces that declare the window | Plan owner, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | At the 1-day window two panels draw 12 and 3 columns, the page does not say they read more than the window, and the window page does not list them | Nothing to build, and two panels that disagree with the window without saying so | Row L26's report; plan owner, 2026-10-07 |

### Row #L36 - Hardware's one-sided line leaves out a day whose only run was refused

- **Scope:** On Hardware, row L22's one-sided line, "No server figures were written down for {days}.", names no day whose only run the counters refuse while its machine records hold server figures. Level 1.
- **The fault** (row L29's first follow-up, 2026-10-07, measured on rows the test built; Reader found the same): such a day's server figures were written down, twice, and disagree, so the line is false for it. With shard 0 of the only run on 14 Jun 2030 filing two machine records that disagree, the line named 14 Jun. `describeServerCounters` in `frontend/src/lib/server/server-counter-notes.ts` takes the days the server's figures were written down from the runs the counters keep, which leave a refused run out, and hands `recordingNotes` every day the article record holds as `coveredElsewhere`. So a day whose only run was refused reads as a day with no server figures.
- **Files touched** (found by a search on `main` at 3ba1b39b8 for the line's words, `coveredElsewhere`, `describeServerCounters` and `carriesServerCounters`; search again at dispatch):
  - `frontend/src/lib/server/server-counter-notes.ts` (`describeServerCounters`: the days the server's figures were written down come from `facts.runs`, refused runs left out. Changed: it takes the refused runs as `refused`, and the days also take each refused run whose records hold the server's figures; found during execution, the first line takes Reader's words for a window with no kept run and a refused one, decision 2)
  - `frontend/src/routes/console/machine/+page.server.ts` (hands `describeServerCounters` `counters.runs`, and the refused-runs box `counters.refused`. Changed: it hands `describeServerCounters` `counters.refused` too)
  - `frontend/src/lib/console/recording.ts` (`coveredElsewhereDays` picks the days the line names, and `coveredElsewhereSentence` holds its words; changed only if Fowler's rule or Reader's words land here. Not changed: its rule was right, and the days it was handed were too few)
  - `frontend/tests/console-machine.spec.ts` (the Oracle, in row L29's block "a run the counters refuse, handed to every figure built from article rows", which builds a refused run and hands it to `describeServerCounters`. Found during execution: two cases on `serverCountersWritten` in that block, and a block of its own beside it for the Oracle, the case that settles decision 1, the started line, the "Measurement is off" line and Reader's words for the first line)
  - `frontend/tests/console-chrome.spec.ts` (pins the line's words; changed only if Reader changes them. Changed, found during execution: its Hardware cases hand `describeServerCounters` `refused: []`, which it now requires; no expected value moved)
  - `docs/concepts/console-design.md` (the paragraph of its `## Design rationale` that opens "A line about days one instrument covered alone names its days", which says which days Hardware's line names. Found during execution: also the paragraph on which runs carry the server's figures, and the refused-runs box's paragraph, which holds the first line's words for 0 runs)
  - Read, no change unless the ruling needs one: `frontend/src/lib/server/machine-counters.ts`, whose `machineCounters` refuses a run and whose `carriesServerCounters` says which runs carry the server's figures. Changed, found during execution: the ruling needs it. `RefusedRun` carries `serverCountersWritten`, set in `oneRun`, and `carriesServerCounters` answers for a refused run too (decision 1)
  - `frontend/tests/ledger-rows.spec.ts` (found during execution: row L28's Oracle hands `describeServerCounters` `refused: []`, which it now requires; no expected value moved. Its spec joins the row's local gate)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-machine.spec.ts --spec console-chrome.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of Hardware at each window preset on the canary build, whose refused runs show the box. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-machine.spec.ts`, beside row L29's cases, on rows the test builds (Table D, D3): a day whose only run the counters refuse, because one shard filed two machine records that disagree and both hold server figures, is not named by the line; a day the article record holds with no machine record row, after the first day the server's figures were written down, is still named. On `main` the first day is named, as row L29's throwaway case measured, which is what lets this check fail. It cannot settle which runs' days the line may take, which Fowler rules (decision 1), or any new words, which Reader chooses (decision 2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fowler ruled the days. A run the counters refuse follows the same rule as a run they keep: it has the server's own figures where one of its machine records holds `server_prompt_tokens` or `server_prompt_seconds`. `oneRun` in `machine-counters.ts` records this on every refused run as `serverCountersWritten`, reading the run's own machine rows as `mergeHost` reads them, and `carriesServerCounters` answers for either kind of run. The route hands `describeServerCounters` the whole read's refused runs as `refused`, a required field. The days the server's figures were written down are the dates of the kept and refused runs that carry them; a refused run's day is the `date` the refused-runs box files it under. The first line's two numbers still count kept runs only. The started line, row L22's line and the "Measurement is off" line read those days, so all three change in this row (found during execution): one list feeds them, as in row L28. A day whose only run was refused and whose records hold no server cell is still named, because the line is true there. Leaving out every day whose only run was refused was rejected: it hides that true line, still names a false day where a kept run with no server cell shares the day with a refused one, and leaves the other two lines false. Taking the days from the machine record's rows was rejected: it builds one fact twice, beside the run count. No new read: the machine record's rows are already in hand | Fowler, 2026-10-08 |
| 2 | Reader chose the words. The started line, row L22's line and the "Measurement is off" line need none: each is true with the box on the same screen, and a clause saying the count leaves the run out would repeat the box. The first line needs words in one state, a window that holds no run the count takes but one the box names (found during execution): "0 runs in these {N} days. {start} to {end}." and, at one day, "This one day had 0 runs. {day}.", in place of "No run in these {N} days is on record." and "This one day has no run on record.", which deny the run the box names, and which the "Measurement is off" line would contradict once it names that run's day. Elsewhere the first line keeps its words. Fowler had found no words needed and left them to Reader, whose they are, so no word was left split | Reader, 2026-10-08 |
| 3 | The fault is row L29's first follow-up. Reader found it too, and said the row that owns the line should fix it | Row L29's report; Reader, 2026-10-07 |
| 4 | L36 waits for L28 (#1401), which ruled which runs carry the server's figures and wrote `server-counter-notes.ts`, and for L29 (#1412), which built the refused run in `console-machine.spec.ts` | Plan owner, 2026-10-08 |
| 5 | Level 1: the days one line names on one route; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The line says no server figures were written down for a day whose machine records hold them twice | Nothing to build, and a false line on Hardware for every day whose only run the counters refuse while its machine records hold server figures | Row L29's report; plan owner, 2026-10-08 |

### Row #L37 - Article cost names a refused shard's processor time or leaves it out

- **Scope:** The cost of one article on Hardware no longer takes a refused shard's processor count from whichever of its two machine records comes last: it leaves that shard's processor time out, or the panel says it cannot pick, as Fowler rules. The row measures first, and changes nothing if the join does not pick. Level 1.
- **The fault** (row L29's second follow-up, 2026-10-07, reasoned from the code and not measured): the cost of one article joins each article to its shard's processor count with no run left out. `processorsByShard` in `frontend/src/lib/console/machine/article-cost.ts` keys each machine record by date, run and shard, so a later record for one shard replaces an earlier one, and the route hands `articleCost` every machine record in the span, `inSpan(fingerprints)`, a refused run's records included. So where a refused shard's two machine records name different processor counts, the join keeps whichever comes last: the pick between two servers that the refusal exists to refuse.
- **Files touched** (found by a search on `main` at 3ba1b39b8 for `articleCost`, `MachineProcessors`, `processorsByShard` and `fingerprintsOf`, and under `docs/` for the processor-time join; search again at dispatch):
  - `frontend/src/lib/console/machine/article-cost.ts` (`processorsByShard` and `processorTime`, the join; changed only if the measurement shows it picks)
  - `frontend/src/routes/console/machine/+page.server.ts` (hands `articleCost` `inSpan(fingerprints)`, and the refused-runs box `counters.refused`; changed only if Fowler rules that the route hands the join the refused shards)
  - `frontend/src/lib/console/machine/ArticleCostPanel.svelte` (prints the processor figure; changed only if Fowler rules that the panel says it cannot pick)
  - `frontend/tests/console-machine.spec.ts` (the measurement, beside row L29's case "the cost of one article counts it")
  - `frontend/tests/console-article-cost.spec.ts` (the cost of one article's own cases, on machine records they write; changed only if the join changes)
  - `docs/architecture/publishing/console-machine.md` (says processor time takes the processors the machine record names, and prints a dash where no record names a count; changed only if the join changes)
  - Left as they are: `frontend/src/lib/server/host-fingerprint.ts`, whose `fingerprintsOf` reads every machine record row; `frontend/src/lib/server/machine-counters.ts`, whose `machineCounters` refuses a run
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-machine.spec.ts --spec console-article-cost.spec.ts`; if the join or the panel changes, `npm --prefix frontend run check`, `doc_load.py` on the page and the browser smoke of Hardware on the canary build. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-machine.spec.ts`, beside row L29's case "the cost of one article counts it", on rows the test builds (Table D, D3): one shard of a run that `machineCounters` refuses filed two machine records that disagree and name 4 and 8 logical processors, and `articleCost` is handed that shard's article rows with the two records in one order, then in the other. If the processor time is the same in both orders, the join does not pick, and the row closes with the measurement (decision 1). If it follows the order, the fault holds, and after the fix both orders give what Fowler rules. By the code it follows the order, which is what lets this check fail if the reasoning holds. It cannot settle the words, which Reader chooses (decision 3).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measure first, on rows the test builds. If the join does not keep whichever of a refused shard's two machine records comes last, the row closes with the measurement and changes nothing | Plan owner, 2026-10-08 |
| 2 | If it does, Fowler rules whether the join leaves a refused shard's processor time out or the panel says it cannot pick (CLAUDE.md section 14) | To be ruled at dispatch (Fowler) |
| 3 | If the panel says it cannot pick, Reader chooses the words (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 4 | The fault is row L29's second follow-up | Row L29's report; plan owner, 2026-10-08 |
| 5 | L37 waits for L29 (#1412), whose measurement built the refused run in `console-machine.spec.ts` | Plan owner, 2026-10-08 |
| 6 | Level 1: one figure on one panel; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | If the reasoning holds, a refused shard's articles take the processor count of whichever of its two records comes last, the pick the refusal exists to refuse | Nothing to build, and a processor figure that can move with the order of two records | Row L29's report; plan owner, 2026-10-08 |
| 2 | Change the join without measuring | The join may not pick, and a change would then fix nothing | One join changed blind | Plan owner, 2026-10-08 |

### Row #L38 - Judgement's verdict split and holdout margin name the line a build used

- **Scope:** Judgement's verdict split and holdout margin take the line a build used on the newest published day, from the rule row L30 built for the merge line, instead of the newest fitted row's line. Level 1.
- **The fault** (row L30's follow-up, 2026-10-07): the Judgement route's page, `frontend/src/routes/console/judgement/+page.svelte`, hands `VerdictSplit` and `HoldoutMargin` `data.lines.at(-1)?.applied ?? data.configuredLine`, the newest fitted row's line, whatever the merge switch says, and each panel calls it "The line the newest day was built with". With the switch off, every build uses the committed floor; with it on, a held newest row, or one older than the lookback, is not the line a build used. It is the fault row L30 fixed on the merge line, and it shows nothing wrong today, because the switch is off and every committed row applies the floor.
- **Files touched** (found by a search on `main` at 3ba1b39b8 for `VerdictSplit`, `HoldoutMargin`, `lines.at(-1)`, "newest day was built with" and `ruleLine`; search again at dispatch):
  - `frontend/src/routes/console/judgement/+page.svelte` (hands both panels `data.lines.at(-1)?.applied ?? data.configuredLine`; `data.windowDay` is the newest published day)
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte` (`ruleLine`, the rule row L30 built: the line `applied_line()` gives a build on the window's last day. It moves out; decision 2)
  - `frontend/src/lib/console/applied-line.ts` (new: the line a build used on a given day, the frontend's one copy of that rule; decision 2)
  - `frontend/tests/applied-line.spec.ts` (new, under `logic`: the Oracle)
  - `frontend/scripts/test-groups.ts` (names the new spec under `logic`)
  - `docs/concepts/console-design/the-rules-every-console-chart-obeys.md` (its holdout section drew the axis around `floor_min`, which is the line only while the switch is off; it now names the line the newest published day was built with in both states, and links the rule; found during execution)
  - Left as they are: `frontend/src/routes/console/judgement/VerdictSplit.svelte` and `frontend/src/routes/console/judgement/HoldoutMargin.svelte`, whose `applied` prop each calls "The line the newest day was built with", which this row makes true; `frontend/src/lib/console/verdict-split.ts` and `frontend/src/lib/console/holdout.ts`, which take the line they are handed; `frontend/src/routes/console/judgement/+page.server.ts`, which hands the page `lines`, `similarity` and `configuredLine`; `frontend/tests/console-window.spec.ts`, whose four merge-line cases from row L30 hold the merge line's rule and run unchanged; `frontend/tests/console-judgement-verdict.spec.ts` and `frontend/tests/console-judgement-holdout.spec.ts`, which read the canary page, whose switch is off; `backend/idhazh/similarity/applied.py`, whose `applied_line()` is the rule a build follows
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec applied-line.spec.ts --spec console-window.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `applied-line.spec.ts`, on rows the test builds (Table D, D3), with row L30's lookback of 7 and floor of 0.94, for the newest published day: with the switch off and a line of 0.937 fitted 3 days before, the floor, 0.940; with the switch on and that line fitted 8 days before as the only fitted row, the floor, 0.940; and with the switch on and that line fitted 3 days before, 0.937. Row L30's four cases in `console-window.spec.ts` pass unchanged, so the merge line keeps its rule. On `main` the spec stops at import, because the module is new; the page's own choice, `data.lines.at(-1)?.applied`, gives 0.937 in the first two cases, which is the fault. It cannot settle that the page hands both panels what the function returns, because no test renders the Judgement page on rows it builds; review reads the two `applied` props in `+page.svelte`.
- **Follow-ups** (found during execution):
  - The rule reads every fitted row the site holds, and the council files the row dated the day before the newest published day at 22:00 UTC, after that day's builds ran. A site built again before the next morning's first publish, as Pages does after every CI-verified push to `main`, then names that row's line for a day whose builds could not read it. Row L30's merge line shares this limit. The run record already holds the line each build grouped at, `same_story_floor_applied` on `RunManifest` (`backend/idhazh/contracts/run_manifest.py`), and the console reads none of it; reading it would name what a build did rather than what the rule says it did. Nothing shows wrong while the switch is off. A row of its own if the owner wants it priced.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L30's follow-up | Row L30's report; plan owner, 2026-10-08 |
| 2 | Both panels take the line from the rule row L30 built: the line `applied_line()` gives a build on a given day. The merge line asks it for the window's last day, as it does now; the two panels ask it for the newest published day, the route's `windowDay`, the day their words name. That rule must not become a second copy. It moves out of `MergeLinePlot.svelte` into one function in `frontend/src/lib/console/applied-line.ts` (new), which the merge line and the page both call, so the three panels read one rule and a logic test drives it on rows it builds. A new file, because the first sentence of `merge-line.ts` says it answers how many stories a day folded into another, and the line a build used is a second question (CLAUDE.md section 1a) | Plan owner, 2026-10-08 (one rule); plan author, 2026-10-08 (the file and the two days) |
| 3 | The panels' words do not change: each calls its line "The line the newest day was built with", which this row makes true. A sentence that must change goes to Reader (CLAUDE.md section 14) | Plan author, 2026-10-08, as row L30, decision 3 |
| 4 | L38 waits for L30 (#1408), which built the rule | Plan owner, 2026-10-08 |
| 5 | Level 1: the line two panels on one route are handed; it shows nothing wrong while the switch is off and every committed row applies the floor | Plan owner, 2026-10-08 |
| 6 | The Oracle's three cases are joined by two, on rows the test writes: a line fitted 7 days before, the first day the build read (0.937), which holds the far end of the lookback in the function's own spec; and a held newest published day that kept a line fitted 14 days before (0.940), the held newest row the fault names. On `main` at 4ed116b2f the spec stops at import, and the page's own choice gives 0.937 to both panels in the first, second and fifth cases, where a build used 0.940. On this branch all five pass, and row L30's four cases in `console-window.spec.ts` pass unchanged | Found during execution (Table D, D3) |
| 7 | No persona was asked: no word on a panel changed (decision 3), and the docs sentence only says which line the holdout axis is drawn around | Found during execution |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Once the switch is on, or a row applies a line while it is off, both panels name a line no build used | Nothing to build, and two panels on Judgement that can name the wrong line from the day the switch is on | Row L30's report; plan owner, 2026-10-08 |
| 2 | A second copy of the rule, in the page, beside the one in `MergeLinePlot.svelte` | Two copies of one rule drift apart, and the three panels would then disagree about which line a build used | No new file, and the rule written twice | Plan owner, 2026-10-08 |
| 3 | The page works the line out once and hands it to all three panels, `MergeLinePlot.svelte` included | The rule would sit in a page, where no logic test reaches it, and row L30's four cases, which hand the merge line the rows, the switch and the lookback (row L30, decision 6), would be written again | One copy of the rule and no new file, and a rule no built case drives | Plan author, 2026-10-08 |
| 4 | The function in `frontend/src/lib/console/merge-line.ts` | That file answers how many stories a day folded into another, and the line a build used is a second question (CLAUDE.md section 1a) | No new file, and a file that answers two questions | Plan author, 2026-10-08 |

### Row #L39 - Judgement's "could not tell" counts against the pairs that agreed

- **Scope:** On Judgement's agreement panel, "could not tell" is counted against the pairs whose two readings agreed, in the strip above the floor and in the sentence under it, from an agreed count that each `JudgeDay` carries. Level 2.
- **The fault** (row L32's first follow-up, 2026-10-07): above the floor, the share of "could not tell" is a share of the pairs whose two readings agreed (`unclear_rate` in `backend/idhazh/stages/set_merge_line.py`), but the strip prints it as "{share} of {pairs read twice} pairs", and the sentence under the strip weights each day's share by the pairs read twice. Row L32's smoke printed "3% of 45 pairs could not tell" where 1 of the 41 pairs that agreed could not tell. `JudgeDay` in `frontend/src/lib/console/merge-line.ts` carries no agreed count; the fitted row carries one, `pairsUsable` in `frontend/src/lib/server/similarity-ledger.ts`, and the route hands it only to the newest day's three counts.
- **Files touched** (found by a search on `main` at 3ba1b39b8 for `JudgeDay`, `pairsUsable`, `unclearRate` and "could not tell"; searched again at dispatch, on `main` at 88d33488e, which found no other builder of `JudgeDay`):
  - `frontend/src/lib/console/merge-line.ts` (`JudgeDay`, which gains the agreed count; held by L31 while it runs; found during execution: it gains `describeUnclear`, which writes "could not tell" against the pairs that agreed, and the comment on `pairsJudged` no longer says both rates are shares of it)
  - `frontend/src/routes/console/judgement/+page.server.ts` (builds each `JudgeDay` from the fitted row, and takes `pairsUsable` only for the newest day's `figures.usable`)
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (`readingsOf` prints "could not tell" above the floor as "{share} of {pairs read twice} pairs" and works the agreed count out under it; `unclear` and `unclearShare` weight each day's share by the pairs read twice; found during execution: the sentence gains two states, `few-agreed` and `none-agreed`, and the header comment no longer says the two rates share a denominator)
  - `frontend/tests/console-window.spec.ts` (the Oracle, beside row L27's and row L32's `judge-agreement` cases, which pin the strip, the dots' names and the sentence, and build each `JudgeDay` with `judgeDay()`; held by L31 while it runs; found during execution: every built day that reads pairs writes out how many agreed, so the counts nest as the run writes them)
  - `frontend/tests/merge-line.spec.ts` (its own `judgeDay()` builds a `JudgeDay`; held by L31 while it runs; found during execution: a test of `describeUnclear` joins it)
  - `frontend/src/lib/server/similarity-ledger.ts` (found during execution: a comment only. It said both rates are shares of `pairsJudged`, the belief behind the fault; it now names the rate each count is the denominator of)
  - `docs/concepts/console-design.md` (found during execution: its fifth rule says the count beside a share is the one the share is taken over, and that the floor counts it)
  - Left as they are: `frontend/src/routes/console/judgement/RecordGates.svelte`, which reads no rate off `JudgeDay` (held by L31 while it runs); `backend/idhazh/stages/set_merge_line.py`, which writes the rates
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts --spec merge-line.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1- and 7-day presets, on a build with fitted rows planted for the smoke, as row L32's smoke did. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, beside row L32's cases, on days the test builds (Table D, D3): a day of 40 pairs read twice, 2 of which disagreed and none of the 38 that agreed could not tell, prints "0% of the 38 that agreed" in the strip; and a window of row L32's smoke days - 40 pairs with 2 that disagreed and none unclear, 1 pair that disagreed, and 4 pairs with 1 that disagreed and 1 of the 3 that agreed unclear - puts its share, 2 percent, against the 41 that agreed in its sentence, in Reader's words. On `main` the strip prints "0% of 40 pairs" and the sentence "3% of 45 pairs", which is what lets this check fail. It cannot settle the sentence's words, which Reader chooses (decision 2).
- **Follow-ups** (found during execution):
  - "Both rates are inside the marks." prints whenever no day in the window was held because of the judge. The run checks first whether the record holds enough to fit on, and every real day so far was held for that, so the sentence can stand beside a share past its mark. Reader ruled that a verdict follows the rates it judges, and settled the words; which row builds them is the owner's call. A disagreed share past its mark ends "The 20% that disagreed is past its mark.", as in "In these 7 days, 20% of 45 pairs disagreed with their own second reading, and 3% of the 36 that agreed could not tell. The 20% that disagreed is past its mark."; a "could not tell" share past its mark ends "The 39% that could not tell is past its mark."; both past end "Both rates are past their marks."; at 1 day only the span words change. Reader asks that `docs/concepts/console-design.md` then record the lasting rule: a verdict word ("inside", "past") follows the rates it judges, never the reason a day was held. A Level 1 row.
  - Reader: the panel's note calls the two dashed lines "rules" while its sentences call them "marks", and it says "line" both for a line on the chart and for the line a run moves. A Level 1 row, with Reader's words.
  - `rateWithDenominator` in `frontend/src/lib/console/merge-line.ts` prints `0%` where a disagreed share that is not zero rounds below one percent, such as 1 of 300 pairs, against the console's `<1` rule, which `describeUnclear` and the merge share keep. A Level 1 row.
  - For row L40: the floor of "could not tell" now counts the pairs that agreed (decision 4), so one day can hold a disagreed share and no "could not tell" share. In the planted smoke, 19 Sep read 5 pairs twice and 3 agreed: its strip and dots print "40% of 5 pairs" and "0 of the 3 that agreed", while the chart draws its "could not tell" dot at 0%. Whatever L40 rules for a day under the floor applies to each of a day's two dots by its own count.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L32's first follow-up | Row L32's report; plan owner, 2026-10-08 |
| 2 | Reader's words for the strip are "{share} of the {agreed} that agreed", such as "0% of the 38 that agreed". Reader chooses the sentence's words, the name of each day's dots above the floor, and the words for a day or a window whose pairs read twice reach the floor while the pairs that agreed do not (CLAUDE.md section 14). Ruled: the dots, "15 Jun: 5% of 40 pairs disagreed with the second reading, and 0% of the 38 that agreed could not tell."; the sentence, "In these 7 days, 9% of 45 pairs disagreed with their own second reading, and 2% of the 41 that agreed could not tell. Both rates are inside the marks."; with at least 5 pairs read twice and 1 to 4 that agreed, the strip "0 of the 3 that agreed", the dots "15 Jun: 40% of 5 pairs disagreed with the second reading, and 0 of the 3 that agreed could not tell." and the sentence "In this one day, 40% of 5 pairs disagreed with their own second reading, and 0 of the 3 that agreed could not tell. The 40% that disagreed is past its mark, and 3 is too few to report a share.", with "inside" for "past" where the share is inside its mark; where no pair agreed, the strip "not counted, no pair agreed", the dots "15 Jun: 100% of 5 pairs disagreed with the second reading. Could not tell: not counted, no pair agreed." and the sentence "In this one day, 100% of 5 pairs disagreed with their own second reading. Could not tell: not counted, no pair agreed. The 100% that disagreed is past its mark." At 7 days only the span words change. Reader's reason: each figure names the pairs it was counted over, and a sentence with its own counts never points at a strip that may be off a phone's screen | Reader, 2026-10-07, for the strip (row L32's report); Reader, 2026-10-08, for the rest, in one ruling with nothing left split, so no debate round ran |
| 3 | `JudgeDay` gains the agreed count from the fitted row's `pairsUsable`, read as the route reads `pairsJudged`; the contract requires both and nests them (`pairs_usable` at most `pairs_judged`, in `backend/idhazh/contracts/fitted_similarity_threshold.py`). `readingsOf` reads it under the floor too, instead of working it out from the disagreed share (row L32, decision 7), so the panel holds one agreed count. `JudgeDay` is the route's run-time answer, written into the page it builds and read by no later run, so Table C, C1 does not fire | Plan author, 2026-10-08, from row L32's first follow-up |
| 4 | The floor counts the pairs a share is taken over, so "could not tell" prints a share only where at least `console.min_attempts_for_rate` pairs agreed: the fifth rule of `docs/concepts/console-design.md`, applied to its own denominator | Plan author, 2026-10-08 |
| 5 | L39 waits for L32 (#1409), which wrote the strip's counts under the floor and built six of the cases, and for L31 (#1414), which edited `merge-line.ts`, `merge-line.spec.ts` and `console-window.spec.ts` | Plan owner, 2026-10-08 |
| 6 | Level 2: a field every `JudgeDay` carries, and the strip, the dots' names and the sentence that read it | Plan owner, 2026-10-08 |
| 7 | "Could not tell" prints `<1` where a share that is not zero rounds below one percent, the console's rule for every number (`docs/concepts/console-design.md`) that the merge share already keeps, so 1 of 467 pairs that agreed reads `<1% of the 467 that agreed`, never `0%` | Found during execution |
| 8 | In the two new states the verdict judges the disagreed share against its mark, read off the share, as Reader's words need. The sentence that prints both shares keeps "Both rates are inside the marks.", chosen by why a day was held: Reader ruled that a verdict follows the rates it judges, and that changing this sentence goes beyond this row (Follow-ups) | Reader, 2026-10-08 |
| 9 | The Oracle: six cases join row L32's six in `console-window.spec.ts`, on days the test builds, each checking the strip's heading and two entries, every drawn day's dots' name and the sentence, written out whole: at 1 day, 40 pairs where none of the 38 that agreed could not tell; at 7 days, row L32's smoke days (45 read twice, 41 agreed, 1 of them could not tell); 5 pairs of which 3 agreed, at 1 and at 7 days; 5 pairs of which 4 agreed, with the disagreed mark moved to 25%; and 5 pairs that all disagreed. Two of row L32's cases and two of row L27's sentence cases take Reader's new words, and every built day that reads pairs writes out how many agreed. A logic test of `describeUnclear` joins `merge-line.spec.ts` | Found during execution (Table D, D3) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The strip names the wrong denominator above the floor, and the sentence weights each day's share by pairs it was not taken over | Nothing to build, and a "could not tell" figure that disagrees with the rate the run gates on | Row L32's report; plan owner, 2026-10-08 |
| 2 | Work the agreed count out on the panel from the disagreed share, as `readingsOf` does under the floor | A count the panel derives from a rounded share can drift from the count the fitted row holds | No new field on `JudgeDay`, and no change in a file L31 holds | Plan author, 2026-10-08 |

### Row #L40 - A day under the floor is not drawn at its shares' heights

- **Scope:** On Judgement's agreement chart, a day that read fewer pairs than `console.min_attempts_for_rate` is not drawn at its two shares' heights, and Jony rules what it draws instead. Level 1.
- **The fault** (row L32's second follow-up, 2026-10-07): since L32 the strip prints such a day's counts and no share, but the chart still draws its two dots at their shares' heights, and both lines pass through them. A day that read 1 pair whose two readings disagreed sits at the top of the axis, while the strip says "1 of 1 pair". The failure chart breaks its line at a day under the same floor (`docs/architecture/publishing/console-charts.md`).
- **Files touched** (found by a search on `main` at 3ba1b39b8 for the chart's marks and lines in `JudgeAgreement.svelte`, and under `docs/` for `min_attempts_for_rate`; search again at dispatch):
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (`marks` places every day that read a pair at its two shares' heights, and `disagreePath` and `unclearPath` pass through each; `attemptsFloor` is the floor)
  - `frontend/tests/console-window.spec.ts` (the Oracle, beside row L32's six cases, which render the panel from days the test builds; held by L31 while it runs)
  - `docs/architecture/publishing/console-charts.md` (its rule for the failure chart below `console.min_attempts_for_rate`: counts only, and a break in the rate line. The agreement chart's rule joins it once Jony rules)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of the Judgement route at the 1- and 7-day presets, on a build with fitted rows planted for the smoke, as row L32's smoke did. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, beside row L32's cases, on days the test builds (Table D, D3): a window that holds a day of 40 pairs, a day of 1 pair whose readings disagreed and a day of 4 pairs draws the two days under the floor as Jony rules, never at their shares' heights, and the 40-pair day at its shares' heights, as today. On `main` the 1-pair day's dot sits at the top of the axis, which is what lets this check fail. It cannot settle what such a day draws instead, which Jony rules (decision 1).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Jony rules what the chart draws for a day under the floor, and whether the two lines break there (CLAUDE.md section 14). It is never a dot at the day's shares' heights, which the strip above says are not a measurement | To be ruled at dispatch (Jony) |
| 2 | Reader chooses any words the ruling needs (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 3 | The fault is row L32's second follow-up | Row L32's report; plan owner, 2026-10-08 |
| 4 | The floor is `console.min_attempts_for_rate`, the one the strip and the sentence use (row L32, decision 3) | Plan author, 2026-10-08 |
| 5 | L40 waits for L32 (#1409), which wrote the strip's counts under the floor and built the six cases, and for L31 (#1414), which edited `console-window.spec.ts` | Plan owner, 2026-10-08 |
| 6 | Level 1: what one chart draws for one kind of day; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The chart places a share the strip above it calls too few to report: a 1-pair day sits at the top of the axis where the strip says "1 of 1 pair" | Nothing to build, and two readings of one day on one panel that disagree | Row L32's report; plan owner, 2026-10-08 |

### Row #L41 - The Judgement route reads its committed fitted lines and holdout scores

- **Scope:** The Judgement route's two ledger readers, `fittedLines` and `mergeLineHoldoutScore`, read the `<YYYY>/<MM>/<DD>.csv` day files their writers commit, so the merge line, the agreement strip, the record panel and the holdout margin draw the days the publication inventory names. Level 2.
- **The fault** (row L32's third follow-up, 2026-10-07; found again by row L31's worker; confirmed by the plan owner on `main` at 3b39c3c09): `dayShardFiles` in `frontend/src/lib/server/payload.ts` kept an inventory entry only when it matched `^(\d{4})\/(\d{2})\/(\d{2})\/[^/]+\.csv$`, a day folder of writer files, which is grain `tree` in `config/ledgers.json`. Its one caller, `readDayShards`, serves only `fittedLines` (`frontend/src/lib/server/similarity-ledger.ts`) and `mergeLineHoldoutScore` (`frontend/src/lib/server/similarity-holdout.ts`). Their ledgers, `fitted-thresholds` and `merge-line-holdout-scores`, are grain `day`: each writer files one `<YYYY>/<MM>/<DD>.csv` a day (`backend/idhazh/ledger/paths.py`). So no file matched, and the route built `lines: []`, `judge: []` and `scored: null` on the live site. #1068 (2026-09-23) caused it: it removed the walk's `<DD>.csv` branch while three judge ledgers still filed one `<DD>.csv` a day. #1050 (2026-09-22) had taught the walk both layouts, and #1233 (2026-10-03) carried the folder-only rule into the inventory pattern.
- **Files touched** (found by a search on `main` at 1fa8e76f1 for `dayShardFiles`, `readDayShards`, `day-shards`, `fitted-thresholds` and `merge-line-holdout-scores` under `frontend/`, `docs/`, `backend/` and `TODO/`):
  - `frontend/src/lib/server/payload.ts` (`dayShardFiles`: the pattern is `<YYYY>/<MM>/<DD>.csv`, and it looks on disk only for the days its cover keeps; its comment and `DayShard`'s)
  - `frontend/tests/similarity-ledgers.spec.ts` (new, group `logic`: the Oracle)
  - `frontend/scripts/test-groups.ts` (`similarity-ledgers` joins the `logic` list, and `day-shards` leaves it)
  - `frontend/tests/day-shards.spec.ts` and `frontend/tests/fixtures/day-shards/` (deleted: they pinned a folder layout no writer files, and their case "a <DD>.csv beside the day directories is not a recorded day" pinned this fault)
  - `docs/concepts/growing-reads.md` (the read's line in "A cover that is not a clock", the passage "A day is a directory of writer-owned files", now "A day is one file", and the residue sentence)
  - Left as they are: `frontend/src/lib/server/similarity-ledger.ts` and `frontend/src/lib/server/similarity-holdout.ts`, whose comments already name `<YYYY>/<MM>/<DD>.csv`; `frontend/src/routes/console/judgement/+page.server.ts`; the writers under `backend/`, the files under `state/` and `frontend/public/publication.json`; `docs/architecture/contracts/ledger-registry.md`, whose line for `readDayShards` stays true; plan 59's row "The CSV ledger code, the migrator and their pages are deleted", which still lists the deleted spec and fixture (Follow-ups)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list` selects every frontend group, because `payload.ts` and `test-groups.ts` are shared inputs, and the test tooling. So the spec of the changed files ran alone through `playwright.logic.config.ts`, 5 passed, and `npm --prefix frontend run test:tooling` ran for the group list, 61 passed; `npm --prefix frontend run check`, 0 errors and 0 warnings; `doc_load.py` on the two pages. The browser smoke of the Judgement route at the 1-, 7-, 14- and 30-day presets, at 1280 and 390 px, on a build from the committed data with 8 Oct the newest published day: every preset drew the fitted days the inventory names, 18 Sep and 20 Sep to 2 Oct, and the holdout score of 21 Sep, with no console error or warning, no failed request and nothing wider than the page at 390 px; the Follow-ups name what reads false. CI: every frontend group.
- **Oracle:** in `frontend/tests/similarity-ledgers.spec.ts`, on a state tree and publication inventory each case builds under its own temporary folder, in the writers' `<YYYY>/<MM>/<DD>.csv` layout, with every expected value written out (Table D, D3): `fittedLines` returns one row a date, the newest run where a date holds two, and leaves out an older day outside its cover; `mergeLineHoldoutScore` returns the newest row written; a named day inside the cover that the disk lacks stops the read and names the file; a named holdout day outside the cover that the disk lacks does not; and `config/ledgers.json` holds both ledgers to grain `day`, suffix `.csv` and the folders the cases write. On `main` at 1fa8e76f1 the four reader cases fail, `fittedLines` returning `[]` and `mergeLineHoldoutScore` returning `null`, and the registry case passes, as a guard against drift should. On the first commit, the case for the holdout day outside the cover fails on the missing 20 Sep file. It cannot settle what the live page shows for a day the inventory does not name (Follow-ups).
- **Follow-ups** (found during execution):
  - The council does not commit the inventory. `COMMITTED_PATHS` in `backend/idhazh/similarity/tenant.py` holds only `state/content-similarity-judge`, so the `publication.record_state_files` calls in `set_merge_line.py` and `score_merge_line_holdout.py` update a `frontend/public/publication.json` that `.github/workflows/llm-council.yml` never commits. The inventory names the fitted days #1233 named once, 18 Sep to 2 Oct; `state/` also holds 3 to 7 Oct, with 57 pairs on 5 Oct and 46 on 6 Oct. Until it is fixed, the page draws fitted days up to 2 Oct only: at 7 days the agreement strip says "No pair was read twice in these 7 days", at 1 day the record says "No run has recorded anything since" 2 Oct, and the bars show 4 days and 49 pairs above the line where the newest row, 7 Oct, holds 6 and 61. Fowler: Level 3 on its own; leave it to plan 59's rows "The fitted merge line is saved through the door" and "The merge line's holdout score is saved through the door", whose readers do not use the inventory, and write it into their scope: each deletes its writer's `record_state_files` call or makes the council commit the file. For a sooner fix, `backend/utilities/commit_and_push.py` already rebuilds a conflicted inventory from the files a run named, so the council fix is cheaper than it looks. The owner places it.
  - The merge line says "Nothing was fitted on {k} of {N} days." through `heldNote` in `frontend/src/lib/console/merge-line.ts`, which counts only the held days that hold a row. Where no day in the window fitted, it reads as if the other days did, while the record panel on the same page says "No line was fitted in these {N} days." The smoke printed "Nothing was fitted on 1 of 7 days." A Level 1 row, with Reader's words.
  - The record's sentence in its `filling` state (`RecordGates.svelte`) prints "49 of 30 pairs above the line" once one count passes its mark while another has not, which reads as a share over one. A Level 1 row, with Reader's words.
  - At 14 and 30 days the merge line's strip rests on "2 Oct, the newest day" while the window, and the record's strip under it, end on 8 Oct: "the newest day" names the newest column drawn, not the window's newest day. Reader rules whether it joins row L34 or takes a Level 1 row of its own.
  - Plan 59's row "The CSV ledger code, the migrator and their pages are deleted" can drop `frontend/tests/day-shards.spec.ts` and `frontend/tests/fixtures/day-shards/` from its list: this row deleted both.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L32's third follow-up, which row L31's worker found too | Plan owner, 2026-10-08 (row L32's report) |
| 2 | The reader takes `<YYYY>/<MM>/<DD>.csv` only. No ledger read this way files a folder of files a day (`DAY_TREES` in `backend/idhazh/contracts/ledger_name.py` is empty), so a folder branch would serve no writer, and taking both would count a day twice where both stood | Fowler, 2026-10-08 |
| 3 | A logic test binds the layout to `config/ledgers.json`, with its values written out. The reader's layout is a hand copy of what the registry tells the backend writer, and a named test is how this project keeps a copy in step (Guardrail #3); review missed this drift at #1068 and at #1233 | Fowler, 2026-10-08 |
| 4 | The Oracle is a new `logic` spec of the two readers, so it outlives plan 59's move and gives that plan's rows one file to rewrite. `day-shards.spec.ts` and its fixture go, and one of their rules stays: a named day inside the cover that the disk lacks stops the read and names the file | Fowler, 2026-10-08 |
| 5 | The reader looks on disk only for the days its cover keeps. That makes "a day outside the window is not read" observable for the holdout reader, whose newest-row answer hides an extra read, and ends a check that grew by one file a recorded day (Guardrail #12) | Fowler, 2026-10-08 |
| 6 | Two commits: the layout with its four cases, then the disk check with its own case | Fowler, 2026-10-08 |
| 7 | The cases build days with no gap, so the cover's count of recorded days and a count of calendar days give one answer. Which of the two a day reader counts is not this row's decision | Fowler, 2026-10-08 |
| 8 | The reader changes and nothing else: not the writers, not the files on disk and not `frontend/public/publication.json`, so plan 59's move rows meet the read as they planned it | Plan owner, 2026-10-08 (the row's brief) |
| 9 | Level 2: a shared reader that two Judgement readers depend on | Plan owner, 2026-10-08 |
| 10 | Depends on nothing. Plan 59's rows "The fitted merge line is saved through the door", "The merge line's holdout score is saved through the door" and "The committed judge rows move onto the door, and the old CSV files go" later replace this read, and its row "The CSV ledger code, the migrator and their pages are deleted" deletes `readDayShards`. The row's brief counted that last row as plan 59's row 9; it is row 10 there | Plan owner, 2026-10-08; found during execution |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The Judgement page draws its never-fitted state while the inventory names 14 fitted days and a holdout score | Nothing to build, and four panels that say no line was ever fitted or scored | Row L32's report; plan owner, 2026-10-08 |
| 2 | Take both layouts | No writer files a folder of files a day for a ledger read this way, and a reader that took both would count a day twice where both stood | One more branch in the pattern, and a test for a layout nobody writes | Fowler, 2026-10-08 |
| 3 | A frontend reader of `config/ledgers.json` that hands `readDayShards` each ledger's folder and suffix and refuses any grain but `day` by name | It builds a reader for two callers that plan 59 replaces and then deletes, edits files that plan's rows rewrite, and guards a change only those rows make, which the registry case catches first in their own pull requests | About 40 lines and their test, and both call sites changed from a folder to a ledger name | Fowler, 2026-10-08 |
| 4 | Change only the pattern, with a comment naming `Grain.DAY_FILE` | Review is then the only check, and review missed this drift twice | Nothing new to write | Fowler, 2026-10-08 |
| 5 | Rewrite `day-shards.spec.ts` and its fixture in the day-file layout | It moves fixtures with no reader into a new shape for plan 59's last row to delete | A second spec over the same reader | Fowler, 2026-10-08 |
| 6 | Show the holdout cover with an entry the reader cannot open, such as a folder named `20.csv` | It disguises a folder as a file to catch a side effect of today's code, and keeps the check that grows by one file a day | No change to the reader | Fowler, 2026-10-08 |
| 7 | Find the day files from the window by date arithmetic, without the inventory | #1233 made the inventory the site's one list of files, and the row's Oracle reads through it | A second way to find a file, beside the inventory every other build-time read uses | #1233; plan owner, 2026-10-08 (the row's brief) |

### Row #L42 - The days control shows the window the panels draw after moving between console routes

- **Scope:** After a move from one console route to another by a tab, the days control shows the window the route's panels draw. Level 1.
- **The fault** (row L31's report, 2026-10-07): on Pipelines, pick 1 day, then click the Judgement tab: the days control shows 14 checked, while every Judgement panel draws 1 day. After a full page load of Judgement the two agree: 1 day on the control and 1 in every panel. `console-window.spec.ts` checks the shared window only through full page loads - "THE ORACLE: the span picked on one console route is the span the next one opens on" moves with `page.goto` - so no test sees it.
- **Files touched** (found by a search on `main` at 3ba1b39b8 for the days control, `fillWindowSlot`, `WindowControlSource` and `idhazh:console-window`; search again at dispatch):
  - `frontend/src/routes/console/+layout.svelte` (draws the days control from the window the route under it hands up, and the configured window until one does)
  - `frontend/src/lib/console/window-slot.ts` (the slot a route fills and the layout reads; on a move between routes the next route fills it and the last one clears it, in an order that is not promised)
  - `frontend/src/lib/components/WindowControlSource.svelte` (the route's half, which hands the route's window up)
  - `frontend/src/lib/components/WindowControl.svelte` (the control, which publishes `data-window-days`)
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/judgement/+page.svelte`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/src/routes/console/model/+page.svelte` and `frontend/src/routes/console/voices/+page.svelte` (each holds its window, reads `idhazh:console-window` once it is mounted and hands its window up; each changed only if the fix is in a route's own read of the key)
  - `frontend/tests/console-window.spec.ts` (the Oracle, beside "THE ORACLE: the span picked on one console route is the span the next one opens on"; held by L31 while it runs)
  - `docs/architecture/publishing/which-console-surfaces-follow-the-window-and-which-say-why-not.md` (says a span picked on Pipelines is the span Hardware opens on, and that `console-window.spec.ts` drives it both ways; it gains the move by a tab. Held by L31 while it runs)
  - Read, no change unless the fix needs one: `frontend/src/lib/components/ConsoleNav.svelte`, whose tabs are real links that the router follows without a page load
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the page; the browser smoke of every console route reached by a tab from Pipelines at the 1-day preset, and by a page load. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, beside "THE ORACLE: the span picked on one console route is the span the next one opens on": open Pipelines, pick 1 day and click the Judgement tab, and the days control holds 1 day, the day count every windowed Judgement surface reports; then pick 7 days on Judgement and click the Pipelines tab, and the control holds 7 days, as every windowed Pipelines surface does. Like that test, it compares the control with what the page draws, so it holds for any data (Table D, D3). On `main` the control holds 14 after the first click, which is what lets this check fail. It cannot settle a move by the browser's back and forward buttons, which the case does not take.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is in row L31's report | Row L31's report; plan owner, 2026-10-08 |
| 2 | The Oracle moves between routes by clicking a tab, as an operator does; the page load is the move the existing test already takes | Plan owner, 2026-10-08 |
| 3 | L42 waits for L31 (#1414), which edited `console-window.spec.ts` and the page that says which console surfaces follow the window | Plan owner, 2026-10-08 |
| 4 | Level 1: what one control shows after one kind of move; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | After a tab click an operator reads 14 days on the control above panels that draw 1 | Nothing to build, and a control that disagrees with the page after a tab click that carries a stored span | Row L31's report; plan owner, 2026-10-08 |
| 2 | Make every tab load its page in full | It hides the fault rather than fixing it (CLAUDE.md Guardrail #5), and every move between routes then costs a page load | One attribute on the tabs, and a slower move between routes | Plan author, 2026-10-08 |

### Row #L43 - Every console route sets its own page title

- **Scope:** Every console route sets its own page title, in Reader's words, so the browser's title names the route on screen after a tab click and after a page load. Level 1.
- **The fault** (row L31's report, 2026-10-07): the Judgement route sets no page title, so after a tab click from Pipelines the browser's title still reads "Console: Pipelines". A search of `frontend/src/routes/console/` for `<title>` finds three routes that set one, Pipelines, Hardware and Summaries, and three that set none: Judgement, Voices and Data explorer.
- **Files touched** (found by a search on `main` at 3ba1b39b8 under `frontend/src/routes/console/` for `<title>` and `svelte:head`, under `frontend/tests/` for `toHaveTitle`, `page.title()` and "Console: ", and under `docs/` for the three titles; search again at dispatch):
  - `frontend/src/routes/console/judgement/+page.svelte` (sets no title)
  - `frontend/src/routes/console/voices/+page.svelte` (sets no title)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (sets no title; plan 55's row "The Data explorer reaches the reference's density" (#1357), still open, edits this file too; decision 3)
  - `frontend/tests/console-nav.spec.ts` (the Oracle; no test reads a page title today)
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/machine/+page.svelte` and `frontend/src/routes/console/model/+page.svelte`, which set "Console: Pipelines", "Console: Hardware" and "Console: Summaries", each followed by `&mdash;` and the site's title. Listed to be left as they were unless Reader changed their words; Reader did (decision 1), so each title line changes (found during execution)
  - `docs/architecture/publishing/what-sits-above-every-console-route.md` (no page under `docs/` named the titles; Reader asked for the pattern to be written down, and this page owns what every console route shares; found during execution)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-nav.spec.ts`; `npm --prefix frontend run check`; the browser smoke of each console route by a page load and by a tab click from Pipelines, reading the browser's title. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-nav.spec.ts`: each console route's title names that route, in Reader's words, on a page load and after a tab click from another route, and no two routes share a title. A title names the route, not what it draws, so the check holds for any data (Table D, D3). On `main` the Judgement route's title after a tab click from Pipelines reads "Console: Pipelines", which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 1).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words of the three titles, and whether the three that exist keep theirs (CLAUDE.md section 14) | Reader, 2026-10-08: every console route's title is its tab label, then `Console`, then the site's title, joined by `&mdash;` (`Judgement &mdash; Console &mdash; {data.ui.site_title}`), so Pipelines, Hardware and Summaries change too. A narrow browser tab shows only the start of a title, and the site's other titles put the most specific part first |
| 2 | The fault is in row L31's report; the search found two more routes with no title, Voices and Data explorer | Row L31's report; plan owner, 2026-10-08 |
| 3 | L43 does not wait for plan 55's row "The Data explorer reaches the reference's density" (#1357), though both edit the data explorer page. Row L21 waits for that row because it rewrites the line #1357 reshapes and whose words plan 55 declares; a page title shares neither, so whichever of the two merges second merges `main` into its branch and takes the other's change (CLAUDE.md section 8) | Plan author, 2026-10-08. Plan 55's owner, 2026-10-08: ship now; #1357 takes the block |
| 4 | Level 1: six routes each change one line in their head; a wrong version is obvious and local | Plan owner, 2026-10-08 (row L43's report, finding 5) |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Three routes set no title, so the browser's title names the last route that set one | Nothing to build, and a title that names the wrong route in the browser's tab list and its history | Row L31's report; plan owner, 2026-10-08 |
| 2 | Wait for #1357, as row L21 does | A title shares no line with what #1357 reshapes, and #1357 has no merge date, so all three routes would wait for their titles with no end named | No merge of `main` in the data explorer page, and three routes titled only after #1357 merges | Plan author, 2026-10-08 |

### Row #L44 - The publication inventory names every fitted-line and holdout day the council commits

- **Scope:** L44 changes no file of its own. Plan 59's row "The fitted merge line is saved through the door" removes the fault, and when it merges the plan owner marks L44 COLLAPSED with that row's pull request (decision 2). Level 3.
- **The fault** (row L41's report, finding 1; checked by the plan owner on `main` on 2026-10-08, and again on `origin/main` at 702b00be7): `frontend/public/publication.json` names the `content-similarity-judge/fitted-thresholds` day files only through `2026/10/02.csv`, while the committed files run through `2026/10/07.csv`. Since row L41 the Judgement route reads the days the inventory names, so it reads no fitted day after 2 Oct. On the committed data this makes row L31's note "No run has recorded anything since" false, and the record's bars show 4 days and 49 pairs where the newest row, 7 Oct, holds 6 and 61. The two council stages that write these files, `backend/idhazh/stages/set_merge_line.py` and `backend/idhazh/stages/score_merge_line_holdout.py`, each name their day file in the inventory through `publication.record_state_files`, but the council commits only `state/content-similarity-judge`: `COMMITTED_PATHS` in `backend/idhazh/similarity/tenant.py` (line 47), which `.github/workflows/llm-council.yml` hands to `backend/utilities/commit_and_push.py` (lines 408 to 414). The daily run, which commits `frontend/public/publication.json` from `.github/workflows/digest.yml`, has not picked up 3 to 7 Oct either, because its stages name only their own files. `backend/idhazh/build_publication.py`, which `idhazh site-weight` runs in the same workflow, writes the built site's own inventory beside the build for the size gate, and never names a `state` file. The holdout scores show no gap today: their one committed file, `2026/09/21.csv`, is named.
- **The cause** (plan 59's owner, 2026-10-08; the plan owner checked it on `origin/main` at 43fbaec37): both Judgement reads, `fittedLines` in `frontend/src/lib/server/similarity-ledger.ts` and the holdout read, `mergeLineHoldoutScore` in `frontend/src/lib/server/similarity-holdout.ts`, went through `readDayShards`, whose `dayShardFiles` in `frontend/src/lib/server/payload.ts` lists their days from the publication inventory, which the council never commits. #1352, plan 59's row "The merge line's holdout score is saved through the door", moved the holdout read to `sliceFromDisk` on 2026-10-08, so on `origin/main` at 4ed116b2f `fittedLines` is the one read left that takes its days from the inventory.
- **Files touched:** none; the row changes no file. The list below records where the fault sat (found by a search on `origin/main` at 702b00be7 for `COMMITTED_PATHS`, `committed_paths`, `record_state_files`, `publication.json`, `fitted-thresholds` and `merge-line-holdout-scores` under `backend/`, `.github/`, `docs/` and `frontend/public/`):
  - `backend/idhazh/similarity/tenant.py` (`COMMITTED_PATHS` names only `state/content-similarity-judge`)
  - `.github/workflows/llm-council.yml` (the commit step hands `COMMITTED_PATHS` to `commit_and_push.py`)
  - `backend/idhazh/stages/set_merge_line.py` (`publication.record_state_files` names each fitted day's file in an inventory the council does not commit)
  - `backend/idhazh/stages/score_merge_line_holdout.py` (the same for a holdout score; held by #1352)
  - `backend/idhazh/path_classes.py` (`DERIVED` names `frontend/public/publication.json`, which a job hands back to the tip and rebuilds before it rebases; held by #1352)
  - `frontend/public/publication.json` (names fitted days through `2026/10/02.csv`)
  - `docs/architecture/publishing/publication-inventory.md` (says each writer that changes a published file commits `publication.json` with it, and that the merge-line and holdout-score stages name their day files; held by #1352)
  - `docs/architecture/publishing/llm-council.md` (what the council's commit step stages, `committed_paths`)
  - `backend/tests/test_similarity_tenant.py` (holds the judge's `committed_paths` to its folder)
  - `backend/tests/workflows/test_llm_council_workflow.py` (holds the commit step to `$COMMITTED_PATHS`)
  - `backend/tests/test_similarity_fit.py` and `backend/tests/test_merge_line_holdout.py` (each seeds an inventory before its stage runs; `test_merge_line_holdout.py` is held by #1352)
  - Read, no change unless the ruled shape needs one: `backend/idhazh/publication.py` (`record_state_files`); `backend/utilities/commit_and_push.py` and `backend/utilities/publication_conflict.py`, which rebuild a conflicted inventory from origin's copy and the files a run named; `backend/idhazh/council/tenancy.py`, whose tenant protocol declares `committed_paths`; `backend/utilities/council_matrix.py`, which joins every tenant's `committed_paths` into the commit step's list; the council tests that build tenants with `committed_paths`, `backend/tests/council/_tenants.py`, `backend/tests/council/test_council_matrix.py`, `backend/tests/council/test_deadline.py`, `backend/tests/council/test_metrics_sink.py` and `backend/tests/council/test_registry.py`; `backend/tests/test_publication_inventory.py` and `backend/tests/workflows/test_publication_conflict.py`; `.github/workflows/digest.yml`, whose plan job ("Commit what the plan saw") and assemble job commit the inventory; `backend/idhazh/build_publication.py`
- **Acceptance gates:** none of its own.
- **Oracle:** none of its own. What closes the row: plan 59's row "The fitted merge line is saved through the door" merging, and the Judgement page reading fitted days after 2 Oct on the committed data once the gardener has packed the first phase of plan 59's row "The committed judge rows move onto the door, and the old CSV files go", its copy of the committed judge rows. Row L45 reads the page then (its decision 3).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is row L41's first Follow-up, finding 1 of its report, and the plan owner checked it on `main` | Row L41's report; plan owner, 2026-10-08 |
| 2 | Plan 59 removes the fault. Plan 59's owner answered on 2026-10-08, and plan 59 is moving: #1420, its row "The CSV code no ledger uses any more is deleted", merged that day. Its row "The fitted merge line is saved through the door" moves the fitted-line read to `sliceFromDisk` (`frontend/src/lib/server/ledger-disk.ts`), which reads the compact index the gardener publishes and never the publication inventory. Its row "The merge line's holdout score is saved through the door" moved the holdout read (#1352, merged 2026-10-08), and its row "The CSV ledger code, the migrator and their pages are deleted" deletes `readDayShards` | Plan 59's owner, 2026-10-08; plan owner, 2026-10-08 |
| 3 | Find why first, then fix it. Fowler rules the shape; row L41's Follow-up names two: each writer's `record_state_files` call goes, or the council commits the inventory | Not ruled: plan 59's row "The fitted merge line is saved through the door" moves the read (decision 2), plan owner, 2026-10-08 |
| 4 | Until plan 59's row "The fitted merge line is saved through the door" merges, L44 changes nothing and stays off #1352's four files and `Tenant.committed_paths` | Plan 59's owner, 2026-10-08 |
| 5 | Level 3: it crosses a boundary, from the council's workflow and writers to the published inventory the site build reads | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The merge line, the agreement strip and the record panel stop at 2 Oct while `state/` holds 3 to 7 Oct, and the record's note says no run has recorded anything since | Nothing to build, and three Judgement panels a day further behind after every council night | Row L41's report; plan owner, 2026-10-08 |
| 2 | Name 3 to 7 Oct in `frontend/public/publication.json` by hand | The next council night leaves its day out again, because nothing commits the inventory with the file: a temporary fix (Guardrail #5) | One commit now, and one more after every council night | Plan author, 2026-10-08 |
| 3 | Plan 62 fixes it now, outside #1352's files: the council commits the inventory | Plan 59's row "The fitted merge line is saved through the door" removes the read in about a day (an estimate, plan 59's owner), and its row "The CSV ledger code, the migrator and their pages are deleted" deletes `readDayShards`, so that commit would be deleted again | A Level 3 change to the council's tenant and workflow, for a Judgement page current about a day sooner | Plan 59's owner; plan owner, 2026-10-08 |

### Row #L45 - Judgement's sentences agree with the days and counts it draws

- **Scope:** Three sentences on the Judgement route agree with the days and counts the page draws, in Reader's words: the merge line's held note, the record's sentence while it fills, and the merge line strip's resting heading. Level 1.
- **The faults** (row L41's smoke on the committed data, 2026-10-08; each sentence found again by a search on `origin/main` at 702b00be7):
  1. The merge line says "Nothing was fitted on 1 of 7 days." beside the record panel's "No line was fitted in these 7 days." `heldNote` in `frontend/src/lib/console/merge-line.ts` counts only the held days that hold a row, and `MergeLinePlot.svelte` prints it beside the clamp note whenever the window draws a row. So where no day in the window fitted, it reads as if the other days did.
  2. The record's sentence while it fills, the `filling` state of `RecordGates.svelte`, prints "49 of 30 pairs above the line" once one count passes its mark while another has not, which reads as a share over one.
  3. At the 14- and 30-day presets the merge line's strip rests on "2 Oct, the newest day" while the window, and the record's strip under it, end on 8 Oct. `MergeLinePlot.svelte` hands `ChartReadout` the resting note ", the newest day", which follows the newest column drawn, not the window's newest day. The stale inventory may cause this one (L44): 2 Oct is the newest fitted day it names. So this row's worker re-reads it once the Judgement page reads fitted days after 2 Oct (decision 3), and fixes it here only if it is still false.
- **Files touched** (found by a search on `origin/main` at 702b00be7 under `frontend/src/` and `frontend/tests/` for each sentence's words, `heldNote`, `data-gates-state` and `restingNote`; search again at dispatch):
  - `frontend/src/lib/console/merge-line.ts` (`heldNote`)
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte` (prints the held note; its strip's resting note)
  - `frontend/src/routes/console/judgement/RecordGates.svelte` (the `filling` sentence, and "No line was fitted in {span}." beside it)
  - `frontend/tests/merge-line.spec.ts` (`heldNote`: "Nothing was fitted on 1 of 30 days.")
  - `frontend/tests/span-sentences.spec.ts` (`heldNote` at 1 and 7 days)
  - `frontend/tests/console-window.spec.ts` (the Oracle, beside the built `record-gates` cases, which pin the `filling` sentence, and the `merge-line` cases; held by L34, L35, L39, L40 and L42 while each runs)
  - `frontend/tests/console-judgement-line.spec.ts` ("the resting heading separates the date from the note" holds the merge line's heading to end ", the newest day")
  - Read, no change unless Reader's words reach them: `frontend/src/lib/components/ChartReadout.svelte`, which joins the newest column's date to the resting note; `frontend/src/routes/console/judgement/JudgeAgreement.svelte` and `frontend/tests/console-judgement-agreement.spec.ts`, whose strip also rests on ", the newest day"
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts --spec merge-line.spec.ts --spec span-sentences.spec.ts --spec console-judgement-line.spec.ts`; `npm --prefix frontend run check`; the browser smoke of the Judgement route at the 1-, 7-, 14- and 30-day presets. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-window.spec.ts`, on days each case builds (Table D, D3), with Reader's sentences written out whole: a 7-day window whose one row was held and whose other days hold no row, where the merge line's note and the record's line agree; a record whose pairs above the line passed their mark while its readings have not, where the sentence while it fills prints no count past its mark as a share; and, at the 14- and 30-day presets, a window whose newest fitted day is before its last day, where the merge line strip's resting heading does not call that day the window's newest. On `origin/main` each case prints the sentence quoted under The faults, which is what lets this check fail. It cannot settle the words, which Reader chooses (decision 2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The faults are row L41's Follow-ups, from its smoke on the committed data | Row L41's report; plan owner, 2026-10-08 |
| 2 | Reader chooses the words of the three sentences (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 3 | The first two faults do not depend on the inventory, so they wait for nothing. The third may be the stale inventory's, so its worker re-reads it once the Judgement page reads fitted days after 2 Oct. That happens once plan 59's row "The fitted merge line is saved through the door" and the first phase of its row "The committed judge rows move onto the door, and the old CSV files go" have merged and the gardener has packed once since | Plan owner, 2026-10-08 (plan 59's owner's answer) |
| 4 | The third fault is this row's, not row L34's (rejected alternative 2); row L41's Follow-up had left that choice to Reader | Plan owner, 2026-10-08 |
| 5 | Level 1: three sentences on one route; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The merge line says some days fitted when none did, the record prints a count past its mark as a share, and the merge line's strip calls a day the newest that is not the window's newest | Nothing to build, and three sentences that disagree with what the page draws | Row L41's report; plan owner, 2026-10-08 |
| 2 | Put the third fault in row L34 | Row L34 reads the console at the one-day window, and this fault shows at the 14- and 30-day presets | Row L34 takes one more sentence, and window cases at two more presets | Plan owner, 2026-10-08 |

### Row #L46 - The site build bakes the raw days the data explorer may read

- **Scope:** The site build hands the data explorer the newest raw day it staged for each ledger, so a question reads the writers' files of the days not packed yet. Level 2.
- **The fault** (the report of plan 60's row "The console can read the gardener ledger", 2026-10-08; confirmed by the plan owner and by plan 55's owner on `main` at f2ccfa46d): `rawListedThrough()` in `frontend/scripts/raw-listed-through.mjs` took its default folder, `frontend/static`, relative to the working folder. `frontend/vite.config.ts` calls it with no argument, and the site build runs in `frontend/`, so it looked in `frontend/frontend/static`, found nothing and returned `{}`. Every build, CI's included, baked `__RAW_LISTED_THROUGH__` as `{}` (that row's client bundle held `var br={}`), so `rawListedThrough()` in `frontend/src/lib/data/ledger.ts` read no writer's raw day. On a real build the explorer read packed days through 6 Oct, asked for none of the 12 raw files of 7 and 8 Oct, and still said it read through 8 Oct. The fault came in with plan 55's row "The door answers a written question, on the engine plan 51 shipped" (#1201). No test called the function as the build does: `raw-listed-through.spec.ts` and `published-ledgers.spec.ts` each hand it a folder.
- **Files touched** (found by a search for `rawListedThrough`, `raw-listed-through` and `__RAW_LISTED_THROUGH__` under `frontend/`, `docs/`, `backend/`, `.github/` and `TODO/`, on `main` at f2ccfa46d and again at 463774499):
  - `frontend/scripts/raw-listed-through.mjs` (finds `frontend/static/` from its own place; a static folder that is not there stops the build)
  - `frontend/tests/raw-listed-through.spec.ts` (the Oracle, and the case of a static folder that is not there; the case with no staged listing makes its folder first)
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md` (the writers' tier says where the build reads the listings, and its design rationale says why)
  - Left as they are: `frontend/vite.config.ts`, which still calls the function with no argument; `frontend/src/lib/data/ledger.ts` and `frontend/src/app.d.ts`, which read and declare the constant; `frontend/scripts/test-groups.ts`, which already names the spec under `logic`; `frontend/tests/published-ledgers.spec.ts`, which hands the function `frontend/static/` (decision 5); `frontend/tests/explorer-boundary.spec.ts` and `frontend/tests/support/ledger-lifecycle.ts`, which set the constant to `{}` for the pages they build; plan 55's and plan 60's text, which describe the read as it was
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list` selects every frontend group and the tooling tests, because `raw-listed-through.mjs` is a shared build input. So these ran: `raw-listed-through.spec.ts` alone through `playwright.logic.config.ts`, 4 passed; `ledger-lifecycle.spec.ts` the same way, 32 passed; `console-data-explorer.spec.ts` on a canary build of this branch, whose client bundle holds `var br={"item-health":"2026-08-21"}`, 33 passed (31 in one run; the 2 that waited past 60 s for Run at 100 percent processor load passed when run alone); `npm --prefix frontend run check`, 0 errors and 0 warnings; `doc_load.py` on the two pages. `test:changed` itself stopped at its first failure, in the `offline` project the console specs depend on, where `service-worker.spec.ts` "leaves what the pipeline published out of the shell cache" got no answer for a file the build holds; alone it passed. The browser smoke, on a real build of the committed data with 8 Oct the newest published day: the build baked 8 Oct for each of the 7 ledgers with staged raw days. At 1280 and 390 px, the data explorer's 7-day question over `gardener`, `SELECT covers, count(*) AS rows FROM "gardener" GROUP BY covers ORDER BY covers`, answered the 5 packed days and 7 Oct with 23 rows and 8 Oct with 24, fetched both raw listings and all 12 raw files, each file once and every one answered 200, and printed "Read from 7 UTC days, 2 Oct 2026 to 8 Oct 2026.", whose last day is the last day it read. No console error or warning, no failed request, and nothing wider than the page; `/console/` the same. CI: every frontend group.
- **Oracle:** in `frontend/tests/raw-listed-through.spec.ts`, on a tree the test builds (Table D, D3): the real script is copied to `<tree>/frontend/scripts/`, one listing a day is staged under `<tree>/frontend/static/state/raw/` for two ledgers with two days each, and a Node process whose working folder is `<tree>/frontend` calls the script with no argument, as the site build calls it. It names `item-health` through 2030-06-15 and `seen` through 2030-06-13. In a copy of `main` at f2ccfa46d the same case gets `{}`, and the case of a static folder that is not there fails because nothing is thrown; the other two cases pass on both. It cannot settle that `vite.config.ts` keeps calling the function with no argument: a call that hands it another folder would bake that folder's days, and only a build shows it (the smoke).
- **Follow-ups** (found during execution):
  - For the row Table B, B7 names: `published-ledgers.spec.ts`'s test "raw-day listings are complete, bounded and become the baked listed-through value" hands the function `frontend/static/`, so it never called the function as the build does, and it compares the listings with a second reading of them rather than with the value the build baked (Fowler, 2026-10-08).
  - Before a run, the smoke's data explorer fetched each of the `gardener` ledger's three indexes and each of its two raw listings twice, at both widths and with no answer from the service worker, while `frontend/src/lib/data/ledger.ts` says each index is read once a page; each data file came once. The indexes take code this row does not change, so that part predates it (reasoned, not measured on `main`); the listings take the same path now that they are read. A row of its own, after plan 55's row "The Data explorer reaches the reference's density" (#1357), which holds `ledger.ts` and the explorer page.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The fault is the one plan 60's row "The console can read the gardener ledger" reported, and plan 62 takes it | Plan owner, 2026-10-08 (plan 60 row 28's report); plan 55's owner ruled on 2026-10-08 that plan 62 takes it |
| 2 | The script finds `frontend/static/` from its own place, `import.meta.url`, and `vite.config.ts` keeps its call with no argument, so the build reads the same folder from any working folder. `published-ledgers.mjs` and `asset-base.js` find their files the same way; `src/lib/server/config.ts`, which feeds 8 of the 13 build constants, still finds `config/` from the working folder | Fowler, 2026-10-08 |
| 3 | A static folder that is not there throws and names the folder, and `{}` means a static folder that holds no staged raw listing. `frontend/static/` is committed, so only a wrong path misses it; on `main` this check would have stopped the first build | Fowler, 2026-10-08 |
| 4 | The Oracle copies the real script into a tree it builds and calls it with no argument from a child Node process whose working folder is that tree's `frontend/`: the fault depended on the working folder, and only a child process sets its own without moving the test runner's. One case from `frontend/` is enough, because a case from another folder tests a call the build never makes. Two ledgers with two days each show that the newest day is picked, not the only one | Fowler, 2026-10-08 |
| 5 | `published-ledgers.spec.ts` is left as it is: after the fix both of its calls read `frontend/static/`, so the edit would prove nothing new, and Table B, B7 gives that spec's rewrite to a later row | Fowler, 2026-10-08 |
| 6 | The read has a fixed-size input (Guardrail #12). It lists names and opens no file. It reads what the last `copy-visuals.mjs` run staged, which `vite dev` and `vite preview` read too, and that run empties `static/state/` first and stages only the ledgers `ledger.published` names (`config/idhazh.json`), each with at most `max(console.window_presets)` listings (`config/appearance.json`) after its newest packed day. So at most 9 folder listings, the raw folder and one for each of the 8 published ledgers, and at most 720 names, 8 ledgers times 90 days. More history cannot widen it | Fowler, 2026-10-08 |
| 7 | Level 2: on every build the data explorer starts fetching raw-day files it never fetched | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Every build bakes `{}`, so the explorer reads no writer's raw day | Nothing to build, and an explorer that on 2026-10-08 read nothing after 6 Oct | Plan 60 row 28's report; plan owner, 2026-10-08 |
| 2 | `vite.config.ts` hands the function a folder found from its own place, and the argument becomes required (Fowler's option B) | No logic test can read what `vite.config.ts` hands the function without loading the whole config, which reads the real `frontend/static/`, so the build's own call stays untested, which is how this fault hid | One changed line in `vite.config.ts` and one in the script; a build is then the only check of the call | Fowler, 2026-10-08 |
| 3 | The default becomes `static`, relative to the working folder, as `copy-visuals.mjs` writes it (Fowler's option C) | It is right only while every caller runs in `frontend/` | One changed default, and the same Oracle without a copied script | Fowler, 2026-10-08 |
| 4 | `published-ledgers.spec.ts` calls the function with no argument | After the fix both calls read the same folder, so it proves nothing new, and that spec reads the canary (Table B, B7) | Two changed calls in a spec a later row rewrites | Fowler, 2026-10-08 |

### Row #L47 - Hardware's started line counts a day whose only run is machine records alone

- **Scope:** On Hardware, the started line counts a day whose only run is a refused run made of machine records alone, once a measurement on rows the test builds shows that the line leaves such a day out. Level 1.
- **The fault** (Fowler, during row L36, 2026-10-08; reasoned, not measured): the route's list of days with a run, `dates` in `frontend/src/routes/console/machine/+page.server.ts`, joins the dates of the runs the counters keep and the days the article record holds, so a run the counters refuse that is made of machine records alone adds no day to it. `describeServerCounters` hands that list to `recordingNotes` as `window`, and the started line counts, from it, the days the window shows before the first day the server's figures were written down (`before` in `frontend/src/lib/console/recording.ts`). So the started line could count one day too few. The machine record's own notes and `describeMissingMarkers` take the same list.
- **Files touched** (found by a search on `origin/main` at 68a707d9f for `dates` in the route, `ran:`, `window: dates`, `recordingNotes`, `describeMissingMarkers` and `RefusedRun`; search again at dispatch):
  - `frontend/src/routes/console/machine/+page.server.ts` (`dates`, which the route hands to `describeServerCounters` as `ran`, to the machine record's `recordingNotes` as `window` and to `describeMissingMarkers` as `ran`; held by L37 while it runs)
  - `frontend/tests/console-machine.spec.ts` (the measurement and the Oracle, beside row L36's block on rows the test builds, whose `ran` is built by the same rule as `dates`; held by L37 while it runs)
  - Read, no change unless the measurement and the ruling need one: `frontend/src/lib/server/server-counter-notes.ts`, which hands `ran` to `recordingNotes` as `window`; `frontend/src/lib/console/recording.ts`, whose `recordingNotes` counts the days before the first recorded day from `window`, and whose `describeMissingMarkers` takes `ran`; `frontend/src/lib/server/machine-counters.ts`, whose `RefusedRun` carries the `date` the refused-runs box files a run under; `frontend/tests/console-chrome.spec.ts` and `frontend/tests/ledger-rows.spec.ts`, which hand these functions `ran` lists they build; `docs/concepts/console-design.md`, whose `## Design rationale` says which days Hardware's lines read
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-machine.spec.ts`; `npm --prefix frontend run check`; when the row changes the route, the browser smoke of Hardware at each window preset on the canary build. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-machine.spec.ts`, beside row L36's block, on rows the test builds (Table D, D3): a window that holds a day whose only run is a refused run of machine records alone, before the first day the server's figures were written down. The measurement comes first: whether the started line counts that day. If it does not, the Oracle is that the started line counts it, with any words Reader rules; on `origin/main` it does not, which is what lets this check fail. If it does, the measurement is the row's record, and nothing changes. It cannot settle any words, which Reader chooses (decision 2).

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measure first, on rows the test builds. If no such day is left out, the row closes with the measurement and changes nothing | Plan owner, 2026-10-08 |
| 2 | Reader chooses any words a change needs (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 3 | The fault is Fowler's, reasoned during row L36 and not measured. Row L36 left it out, because which days had a run is a different question from which days the server's figures were written down | Fowler, 2026-10-08 (row L36's report) |
| 4 | L47 waits for L36 (#1421), which changed the days the started line reads and built the refused runs in `console-machine.spec.ts` that this row measures beside | Plan owner, 2026-10-08 |
| 5 | Level 1: the days one line counts on one route; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The started line may count one day too few where a day's only run is a refused run of machine records alone | Nothing to build, and possibly a started line one day short | Fowler, 2026-10-08 (row L36's report) |
| 2 | Change `dates` without measuring | The fault is reasoned, not measured, and the list feeds three lines, so a change could move all three for a case no rows have shown | One change to the route's list, with no measurement behind it | Plan owner, 2026-10-08 |

### Row #L48 - The Data explorer's line under an answer ends on the last day it read

- **Scope:** The line under a Data explorer answer, "Read from {n} UTC days, {first} to {last}.", ends on the last day the explorer read, not on the window's last day, and counts the days up to that day. Level 2.
- **The fault** (row L46's report, 2026-10-08; plan 55's owner, 2026-10-08; the line's source read on `origin/main` at 4ed116b2f): row L12 (#1364) wrote the line. It takes its last day from the window, not from the days the explorer read: `+page.svelte` hands `describeDaysRead` the window's last day, `runSpan.to`, and an `ok` answer names only the first day it read, `readFrom`. On a build before L46 (#1427) the line named 8 Oct while the explorer read only through 6 Oct. Since L46 it holds on the committed data only because every ledger's raw listing reaches 8 Oct. A ledger's newest listed day is the later of the newest day its indexes name and the newest raw day the build listed for it, its `through` in `frontend/src/lib/data/ask-reader.ts`. So whenever every chosen ledger's newest listed day is before the window's last day, the line names a day the explorer never read.
- **Files touched** (found by a search on `origin/main` at 4ed116b2f for the line's words "Read from", `describeDaysRead`, `days-read`, `AnswerTable`, `spanText`, `readFrom` and `firstDayRead` under `frontend/`, `docs/`, `backend/` and `.github/`; search again at dispatch):
  - `frontend/src/lib/console/explorer/days-read.ts` (`describeDaysRead(from, to)` writes the line and counts its days; its comment says `to` is the window's last day)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (hands `describeDaysRead` the answer's `readFrom` and `runSpan.to`, the window's last day; it already holds `cost.through`, how far each chosen ledger reaches, from the estimate before a run; held by plan 55's row "The reader chooses the chart and the columns it draws", decision 3)
  - `frontend/tests/console-data-explorer.spec.ts` (the Oracle, beside L12's "THE ORACLE: an answer over two ledgers that began on different days names each with its own first day, counts the days it read, and keeps that line when the window moves before the next Run"; it pins the line; held by plan 55's row "The reader chooses the chart and the columns it draws")
  - `frontend/tests/ledger-lifecycle.spec.ts` (pins the line in the reader's cases: `daysReadLines` hands `describeDaysRead` a last day each case passes in, as the page hands it the window's last day)
  - `frontend/tests/explorer-boundary.spec.ts` (pins the line in L1's browser case)
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md` (says the line's last day is the window's)
  - `docs/how-to/query-a-ledger-from-the-console.md` (quotes the line and says which days it counts)
  - `frontend/src/lib/data/ask-reader.ts` and `frontend/src/lib/data/slice-shapes.ts`, only if the answer must say which day it read through (decision 5): `readAsk` names `readFrom` through `firstDayRead`, each ledger's plan holds its `through`, and the `ok` answer of `AskResult` carries no last day
  - Read, no change: `frontend/src/lib/console/explorer/AnswerTable.svelte`, which prints the line it is handed, `spanText`, in its `.answer-note`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-data-explorer.spec.ts --spec ledger-lifecycle.spec.ts --spec explorer-boundary.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on the two pages; the browser smoke of the data explorer. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** in `console-data-explorer.spec.ts`, beside L12's oracle, on ledgers the test builds (Table D, D3), with a window that ends after one ledger's newest listed day: chosen alone, the line names that ledger's newest listed day as its last day and counts the days up to it; chosen beside a second built ledger that reaches the window's last day, the line names the window's last day. On `origin/main` the first case names the window's last day, which is what lets this check fail; the second passes on both, and fails a fix that takes the earlier of the two ledgers' last days. It cannot settle a newest listed day that only a raw listing names, because `serveToPage` in `frontend/tests/support/ledger-lifecycle.ts` serves packed days and bakes no raw listing.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Plan 62 takes the row, because its row L12 wrote the line | Plan owner, 2026-10-08; plan 55's owner agreed, 2026-10-08 |
| 2 | Reader chooses the words if the sentence changes form (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 3 | L48 waits for plan 55's row "The reader chooses the chart and the columns it draws", which edits `+page.svelte` and `console-data-explorer.spec.ts` but not `days-read.ts` or `AnswerTable.svelte`. A change in `days-read.ts` alone could go now, but it cannot fix the line: `+page.svelte` hands it the window's last day, and an `ok` answer names no last day read, so the fix changes `+page.svelte` | Plan 55's owner, 2026-10-08 (what waits); plan author, 2026-10-08 (the search) |
| 4 | If the fix needs the data layer under `frontend/src/lib/data/`, `ledger.ts`, `ask-reader.ts`, `slice-shapes.ts` or `page-keeper.ts`, to say which days an answer read, the row's worker tells plan 55's owner before starting | Plan 55's owner, 2026-10-08 |
| 5 | If the data layer must change, Fowler rules where the last day read comes from. The page already holds `cost.through`, how far each chosen ledger reaches, from the estimate before a run; an `ok` answer carries only `readFrom` | To be ruled at dispatch (Fowler) |
| 6 | Level 2: the line under every explorer answer changes, three specs pin it and two pages describe it, and the fix may change `readAsk` in `ask-reader.ts`, through which every explorer question reads | Plan author, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The line names a day the explorer never read whenever every chosen ledger's newest listed day is before the window's last day | Nothing to build, and a line that can claim a day no ledger gave the answer | Row L46's report; plan owner, 2026-10-08 |
| 2 | Fix it in L46 | L46's fault was the bake, and the line held on the data L46 smoked: every ledger's raw listing reached 8 Oct, the window's last day | L46 would have changed `+page.svelte` too, and its bake fix would have waited for plan 55's row "The reader chooses the chart and the columns it draws" | Plan owner, 2026-10-08 |

### Row #L49 - Every console route asks search engines not to list it

- **Scope:** Every console route carries `<meta name="robots" content="noindex" />` in its head, so a search engine that crawls it does not list it. Level to be set from the search below.
- **The gap** (row L43's report, finding 1, 2026-10-08): a search of `frontend/src/routes/console/` for `noindex` finds it on three routes, Pipelines, Hardware and Summaries, and finds it on none of Judgement, Voices and Data explorer; the site ships no `frontend/static/robots.txt`. A search engine that crawls the console may list those three routes.
- **Why CI did not catch it:** `.github/workflows/ci.yml`'s `robots` job runs `pytest backend/tests/test_extract.py`, which checks the article extractor's own RFC 9309 `robots.txt` parsing for sources this project crawls. It reads nothing under `frontend/src/routes/console/` and asserts no console-route meta tag, so a console route with no `noindex` tag passes that job every time.
- **Files touched** (found by a search on `origin/main` at 3ba1b39b8 for `noindex` under `frontend/src/routes/console/`, for `robots` under `.github/workflows/` and `backend/tests/`, and for `robots.txt` under `frontend/static/`; search again at dispatch):
  - `frontend/src/routes/console/judgement/+page.svelte` (sets no `noindex`; held by L38)
  - `frontend/src/routes/console/voices/+page.svelte` (sets no `noindex`)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (sets no `noindex`; held by plan 55's row "The reader chooses the chart and the columns it draws")
  - `frontend/src/routes/console/+layout.svelte` (a candidate home for one shared tag, if Fowler rules for it; L42 changes this file for the days control, so coordinate before dispatch)
  - `frontend/src/routes/console/+page.svelte`, `frontend/src/routes/console/machine/+page.svelte`, `frontend/src/routes/console/model/+page.svelte` (already set `noindex`; read, to confirm the pattern a shared or per-page fix follows)
  - `.github/workflows/ci.yml` (the `robots` job; read, to say why it did not catch this)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list` for the affected specs; `npm --prefix frontend run check`; the browser smoke of each console route, reading its rendered head. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on a page the test builds, or on the canary page: every console route's rendered head carries `<meta name="robots" content="noindex" />`. On `origin/main` Judgement, Voices and Data explorer carry no such tag, which is what lets this check fail.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fowler rules the shape: one tag in a shared place such as `console/+layout.svelte`, or one tag on each page | To be ruled at dispatch (Fowler) |
| 2 | Level set from the search: a missing tag on three pages, fixed by one line each or by one shared line, following a pattern three other pages already set; a wrong version is obvious and local | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | A search engine that crawls the console may list Judgement, Voices or Data explorer, pages built for no reader who does not already use this console | Nothing to build, and three routes a search engine may index | Row L43's report, finding 1 |

### Row #L50 - Two console tests prove what they claim

- **Scope:** Two console test assertions are fixed to catch the fault each claims to catch. Level 1.
- **Finding 2** (row L43's report, 2026-10-08): `frontend/tests/console-chart-lifetime.spec.ts`, near line 357, asserts `performance.getEntriesByType('navigation').length === 1` to prove a tab click did not reload the page. Measured with Playwright 1.62.1 on Chromium, that count is also 1 after a full page load; the spec's own comment says a full page load "resets it and proves nothing," yet the assertion cannot tell the two apart, because it reads the same value either way. `performance.timeOrigin` does: a reload sets a new origin, where an in-page navigation keeps the one the first load set.
- **Finding 3** (row L43's report, 2026-10-08): `frontend/tests/console-nav.spec.ts`'s strip-reading helper, `tabs(page)`, is called straight after `page.goto` with no wait for the strip's own tabs to appear. On the client-drawn Data explorer route, on a busy machine, the read once found no tabs; a re-run passed. Waiting for the strip's first tab before reading it closes the race.
- **Files touched** (found by a search on `origin/main` at 3ba1b39b8; search again at dispatch):
  - `frontend/tests/console-chart-lifetime.spec.ts` (the "no reload" assertion near line 357; the Oracle for finding 2)
  - `frontend/tests/console-nav.spec.ts` (the `tabs(page)` helper and its callers; the Oracle for finding 3)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-chart-lifetime.spec.ts --spec console-nav.spec.ts`; `npm --prefix frontend run check`. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** (a) the "no reload" check fails when the test is changed to force a full page load on purpose, which it cannot do today. (b) `tabs(page)` waits for the strip's first tab to appear before it reads the strip, so a slow-drawn strip no longer reads as empty.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Level 1: two test assertions, each read in one file, each fixed by comparing against a value the test can observe or by adding one wait | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The "no reload" check cannot fail, so a regression that reloads the page on a tab click ships unnoticed; the strip read can flake on a busy machine and hide a real drawing fault behind a re-run | Nothing to build, and two checks that do not catch what they claim to | Row L43's report, findings 2 and 3 |

### Row #L51 - Judgement's agreement panel words follow the rates they judge

- **Scope:** Judgement's agreement panel reads right in every case Reader named, the panel's note uses one word for a dashed line and one word for each of a chart line and a run's progress, and a disagreed share that rounds to 0% but is not zero prints under the console's `<1` rule. Level 1.
- **The fault** (row L39's report, Follow-ups 1 to 3, 2026-10-08):
  1. The sentence "Both rates are inside the marks." follows why a day was held, not the rates themselves, so it can print beside a share that is past its own mark. Reader settled the words for the three cases in L39's Follow-up 1: a verdict word such as "inside" or "past" follows the rates it judges, never the reason a day was held.
  2. The panel's note calls the two dashed lines "rules" where its own sentences call them "marks", and it uses "line" both for a line the chart draws and for the line a run moves. Reader's words for this follow-up are in L39's Follow-up 2.
  3. `rateWithDenominator` in `frontend/src/lib/console/merge-line.ts` prints `0%` for a disagreed share that is not zero but rounds below one percent, such as 1 of 300 pairs, against the console's rule that such a share prints `<1%`, which `describeUnclear` and the merge share already keep.
- **Files touched** (found by a search on `origin/main` at 3ba1b39b8 for the fault's words under `frontend/src/lib/console/` and `frontend/src/routes/console/judgement/`; search again at dispatch):
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte` (the panel; held by L40, PENDING)
  - `frontend/src/lib/console/merge-line.ts` (`rateWithDenominator`; held by L39, merged as #1428)
  - `frontend/tests/console-window.spec.ts` (pins the panel's cases; held by L39 and L40)
  - `docs/concepts/console-design.md` (Reader asks it to record that a verdict word follows the rates it judges, never the reason a day was held)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --spec console-window.spec.ts`; `npm --prefix frontend run check`; `doc_load.py` on `console-design.md`. CI: the pull request runs the console specs; every group runs on the merge push.
- **Oracle:** on built days (Table D, D3), with Reader's sentences held whole: each of the three cases Reader named prints the sentence Reader settled, the panel's note says "marks" throughout and "line" for one thing only, and a disagreed share of 1 of 300 pairs prints `<1%`. On `origin/main` each case prints the sentence quoted in the fault, which is what lets this check fail.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader rules any words in this row not already settled by L39's Follow-ups (CLAUDE.md section 14) | To be ruled at dispatch (Reader) |
| 2 | Level 1: three narrow word and rounding fixes in two files, each pinned by an existing test | Plan owner, 2026-10-08 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | A verdict word can print beside a rate it does not judge, the panel's note names one thing two ways, and a non-zero share can print `0%` against the console's own `<1` rule | Nothing to build, and a panel whose words can read false | Row L39's report, Follow-ups 1 to 3 |
