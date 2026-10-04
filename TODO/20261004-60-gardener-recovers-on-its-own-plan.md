# Plan 60 - The gardener chooses its own work and recovers on its own

**Last Updated**: 2026-10-04

**Level**: 5 (CLAUDE.md section 6). Rows 8, 10, 19 and 20 change persisted contracts (section 2.4). The owner approved each shape on 2026-10-04.

**Status**: written 2026-10-04 by the session owner from Fowler's design of the same day and the owner's rulings on it. Fowler's review of the recovery design (section 2.3) was still running when this was written; ESCALATE trigger 6 says what its answer can change.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | On 2026-10-04 seven of the eleven compaction tasks failed and none packed a new day. Since #1240, every compaction step reads one window that was built for the step that deletes old months, so the packing steps look in the wrong months. The run of 2026-10-03, before #1240, packed normally. The owner asked that each step choose its own periods, that no empty file is written, and that a fault is recovered and recorded so the pass moves on |
| Hard scope - in | - Each compaction step chooses its own periods (section 2.1).<br>- An empty day, month or year is an index entry with no file, and nothing is filled in before a ledger's first day (section 2.1, Table D row D1).<br>- Every fault in Table C is designed out or recovered, and the record says which (sections 2.3 and 2.4).<br>- Months close 16 days after they end on all 11 compaction ledgers; a late re-run file re-opens its month; `seen` and `counterfactual-scores` keep 3 months.<br>- Each old month is dropped once, and the monthly index is the record of what is left to drop.<br>- workflow-runs and workflow-artifacts read only what is past their line, starting from a mark on their own record.<br>- One run id per workflow run, and job names that list each shard's tasks.<br>- Every gardener log line is one JSON event, each shard writes a summary, and a dry run never says that anything is gone.<br>- `compact-gardener` packs live, and `monthly_window_dry_run` is renamed `month_deletes_dry_run` |
| Hard scope - out | Table A below |
| ESCALATE triggers | 1. A persisted shape that section 2.4 does not declare.<br>2. A row that would delete a row of `published`, `seen` or `summary-quality-evals`, other than settling a re-opened month by its record key (Table C, C3). Their declarations refuse deletion in `prune_refusal`.<br>3. Fetched text in a log line, a record field, a file path or a URL (Guardrail #11).<br>4. A shard that would run past the 6 h job, or a row whose cost is over 3x its estimate.<br>5. The `dry_run` of workflow-runs or workflow-artifacts moving to `false` (Table A, A1).<br>6. Fowler's answer to the design brief of 2026-10-04 changes a decision in this plan. For a row not yet dispatched, the owner edits the row first. For a row already merged, STOP-AND-SURFACE ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)).<br>7. Two personas still disagree after one debate |
| Chosen strategy | Each step reads the ledger's own indexes and chooses its own periods. A fault the gardener can record is recorded on the period, and the pass moves on. Only a code defect turns a run red. The owner ruled on 2026-10-04, on Fowler's design of the same day |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 12 to 20 share the compaction step modules, so they run one at a time. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table A - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| A1 | Switching workflow-runs and workflow-artifacts to live deletes | Old runs and artifacts stay, as today | An owner decision. First size `max_deletes_per_run` from a 7-day arrival count: `gh api "repos/miztiik/yen-idhazh/actions/runs?created=>=<today-7>&per_page=1" --jq .total_count`. On 2026-10-04 that read 1,226 runs, about 175 a day, and the declared ceiling is 50 deletes a wake |
| A2 | A keep line for years | The yearly index of a ledger that keeps every row gains one entry a year (row 14, decision 3) | A ledger whose declaration lets it forget whole years. `published` and `summary-quality-evals` refuse that in `prune_refusal` |
| A3 | Keying the rules in `backend/idhazh/gardener/period_inputs.py` on a declaration's kind instead of task names | One list of task names stays written in code (Guardrail #6) | A Level 2 row after row 16 |
| A4 | Event logging in `backend/idhazh/cli.py` and `backend/idhazh/telemetry/cli.py` | Those two commands keep free-text logs (CLAUDE.md section 1b) | A Level 2 row each after row 21, reusing `event_log` |
| A5 | Listing switched-off declarations in the plan job | A paused task does not appear in the run log | A request for it |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Compaction gets its own page | - | A | PENDING | - | - | - |
| 2 | A dry run says nothing was deleted | - | A | DONE | literate-parakeet | - | Plan 60 row 2: dry-run wording |
| 3 | A read nobody named fails loudly | - | A | PENDING | - | - | - |
| 4 | The ledger fault words live in contracts | - | A | PENDING | - | - | - |
| 5 | A ledger's marks are read in one place | - | A | PENDING | - | - | - |
| 6 | One run id per workflow run | 1 | B | PENDING | - | - | - |
| 7 | The month-delete switch is named for what it does | 1 | B | PENDING | - | - | - |
| 8 | The site reads empty, lost and set-aside periods | 4 | B | PENDING | - | - | - |
| 9 | Each job's name says what its shard runs | 6 | C | PENDING | - | - | - |
| 10 | workflow-runs reads only runs past its line, from its own mark | 2, 7, 9, 12 | C | PENDING | - | - | - |
| 11 | workflow-artifacts reads from the oldest end and resumes from its mark | 10 | C | PENDING | - | - | - |
| 12 | Which months may close | 3, 5, 7, 8 | D | PENDING | - | - | - |
| 13 | Which days may be packed | 12 | D | PENDING | - | - | - |
| 14 | Which years may be packed | 13 | D | PENDING | - | - | - |
| 15 | Each old month is dropped once | 14 | D | PENDING | - | - | - |
| 16 | The shared window is gone | 15 | D | PENDING | - | - | - |
| 17 | A late file re-opens its month | 16 | D | PENDING | - | - | - |
| 18 | An unreadable file is set aside, and extra files wait | 17 | D | PENDING | - | - | - |
| 19 | The marks are worked out from the indexes, and the watermark files go | 8, 18 | D | PENDING | - | - | - |
| 20 | The record says what was recovered and why a pass stopped | 4, 11, 19 | E | PENDING | - | - | - |
| 21 | Every gardener log line is one JSON event | 2, 20 | E | PENDING | - | - | - |
| 22 | A person reads a shard at a glance | 21 | E | PENDING | - | - | - |
| 23 | The gardener ledger is packed live | 16, 22 | F | PENDING | - | - | - |
| 24 | Months close 16 days after they end | 7, 17, 23 | F | PENDING | - | - | - |
| 25 | The retired raw listings code goes | 15 | F | PENDING | - | - | - |

## 2. Shared declarations

Rows point here. Each name, shape and rule is declared once.

### 2.1 How each step chooses its periods

Every line is computed from `today`, the wake's UTC day, and from each period's own end (CLAUDE.md section 2). An operator range (`--from` and `--to` on one named task, or the migrator's range) limits every step. The "newest eligible day" is the newest day at least `compact_after_days` whole days past its end. The cap is the declaration's `max_periods_per_run`.

Table B - each step

| # | Step | Starts at | Takes | Adds to the listing |
| --- | --- | --- | --- | --- |
| B1 | Drop month files | The oldest monthly entry | Entries older than the keep line, oldest first, up to the cap. Live: delete the month file when the entry has one, delete its raw month folder, then remove the entry. Report-only: keep both and report them | Each month file and its `state/raw/<ledger>/YYYY/MM` folder |
| B2 | Drop raw days | - | Raw day folders older than the keep line, inside the months B1 names. They are deleted by listed path and never parsed | Nothing more |
| B3 | Drop retired listings | - | Every file in `state/raw/<ledger>/index/`. Nothing writes there now, so it only shrinks | That folder |
| B4 | Pack years, only with `monthly_keep_days` | The year after the yearly mark; with none, the year of the oldest monthly entry | Consecutive years whose age line has passed and whose December the monthly mark is strictly past, up to the cap. A ledger that began after January packs its first year from its first month. A year with no row is an entry `empty` with no file. Its months' `lost_days` carry into the year entry | That year's month files, named from the monthly index |
| B5 | Absorb months | The month after the monthly mark; with none, the oldest month the daily index names; with an empty daily index, nothing | Consecutive months at least `daily_keep_days` past their end that the daily mark has passed, up to the cap. A month with a raw day still waiting is held for B6. Completeness counts days from the month's 1st, or from the ledger's first day when the ledger began inside that month. A missing day inside that span is recovered (Table C, C2). A month with no row is an entry `empty` with no file | Each month's daily files and its raw month folder |
| B6 | Pack days | The day after the daily mark | New days up to the earlier of the mark plus the cap and the newest eligible day. Also packed days inside the 30-day re-run span that hold new raw files; they count against the cap. A raw file in a closed month re-opens it (Table C, C3). A day with no row is an entry `empty` with no file | The raw folders of the new days and of the re-run span |
| B7 | First run: no daily mark | The oldest raw day in the raw month folders from the newest eligible month minus `lookback` months to the newest eligible month, or in the operator range. Never before the keep line when month deletes are live | As B6. With no raw day, nothing; the outcome is `empty` | Those raw month folders |

Every read has a fixed size (Guardrail #12). A pass names at most: the three indexes, plus the three watermarks until row 19; one retired-listings folder until row 25; and for each step, the cap times that step's periods. Each count comes from config or the calendar.

### 2.2 The marks

| # | Mark | Worked out as |
| --- | --- | --- |
| M1 | Daily mark | The newest of: the newest daily entry, the last day of the newest monthly entry, and the last day of the newest yearly entry |
| M2 | Monthly mark | The newest of: the newest monthly entry, and December of the newest yearly entry |
| M3 | Yearly mark | The newest yearly entry |

A mark can be worked out this way only because every period a step has looked at leaves an entry, an empty one included (rows 12, 13 and 14). Until row 19 lands, the watermark files stay, and the steps read them.

### 2.3 Recovery instead of failure

A pass never stops for something it can record. Each fault below is designed out, or recovered on this wake or the next. Only `failed` turns a job red, and it means a code defect, the one case a person must act on.

Table C - each fault

| # | What stopped the pass before | Now | Recorded as | Outcome | Row |
| --- | --- | --- | --- | --- | --- |
| C1 | A month chosen from before the ledger began (`day-missing`) | Designed out. B5 starts at the oldest indexed month, and completeness starts at the ledger's first day | - | - | 12 |
| C2 | A day inside history with no entry (a hole) | Re-packed from its raw files when any are left. Otherwise it gets an entry `lost`, and the day goes into its month's `lost_days` when the month closes | `repacked-from-raw` or `recorded-lost`, with the day | `done` | 12 |
| C3 | A raw file in a closed month (a late re-run) | The month re-opens. Its rows and the late rows are settled by the ledger's record key, the month file and its entry are rewritten, and the late raw files are deleted | `reopened-month`, with the month | `done` | 17 |
| C4 | More raw files in one day than `max_raw_files_per_period` | The first files by name are packed. The rest stay where they are, and B6's re-run span takes them on the next wake | `carried-over`, with the day | `ceiling` | 18 |
| C5 | A raw file that cannot be read, or is larger than the size ceiling | Moved to `state/raw/<ledger>/set-aside/`, under its path relative to `state/`, and counted in its entry's `set_aside`. The rest of the day packs | `set-aside`, with the day | `done` | 18 |
| C6 | A packed day or month file that cannot be read when its month or year closes | Moved to set-aside as in C5. Its days go into `lost_days`, and the period closes | `set-aside` and `recorded-lost` | `done` | 18 |
| C7 | A raw day past the keep line whose files cannot be parsed | Designed out. B2 deletes by listed path and parses nothing | - | - | 15 |
| C8 | The shard's download ceiling (`over_the_ceiling` in `runner.py`) | Designed out. A step chooses a period only while its listed size fits what is left of the shard's budget | - | `ceiling` | 18 |
| C9 | A watermark without its index (`index-missing`) | Designed out. Each mark is worked out from the indexes (section 2.2), and the watermark files go | - | - | 19 |
| C10 | The pass is interrupted | Writes are atomic and indexes are written last, so the next wake resumes | fault `interrupted` | `deferred` | 20 |
| C11 | GitHub's API fails after the HTTP client's retries (collections). Only errors the client treats as retryable: 429, 5xx and timeouts | The mark stays, and the next wake resumes from it | fault `api-unavailable` | `deferred` | 20 |
| C12 | An exception that nothing above names | The task stops at that period. The shard's other tasks still run, and the next wake retries | fault `raised`, the exception's type only and never its text | `failed` | 20 |

`state/raw/<ledger>/set-aside/` is never named by any step, never copied to the site (only `state/compact/` is), and never deleted by the gardener. A person reads it when the console shows a non-zero `set_aside`.

### 2.4 Persisted shapes

Every shape below follows CLAUDE.md section 11: a new `version`, one changelog line, at most five lines in the changelog, and a read-side default that reads every older payload.

Table D - contract changes

| # | Contract | Change | How older payloads read | Row |
| --- | --- | --- | --- | --- |
| D1 | `CompactEntry` in `CompactIndex`, `backend/idhazh/contracts/ledger_index.py` | `state`: `packed` (the default), `empty` or `lost`. An `empty` or `lost` entry holds no file, and its `bytes` and `rows` are 0. `lost_days`: ascending UTC days inside a monthly or yearly entry's period that were recorded lost; empty by default; never on a daily entry. `set_aside`: how many files were moved aside while packing the period; default 0 | The defaults read every committed index as all `packed`, so nothing is rewritten. A zero-row file written before this row stays a valid `packed` entry until its month closes | 8 |
| D2 | `CollectionPruneRow` in `backend/idhazh/contracts/collection_prune.py` | `handled_through`: a UTC day. Every member created on or before that day was handled by a pass with the same `dry_run` value: deleted, recorded as not deletable, or reported. Null when the pass handled nothing | The null default reads every older row | 10 |
| D3 | `CollectionPruneRow`, and new `backend/idhazh/contracts/gardener_fault.py` | `fault`: `raised`, `interrupted` or `api-unavailable`, allowed only beside `stopped_because` `failed` or `deferred`. `recovered`: a list of `{note, period}`, where `note` is `repacked-from-raw`, `recorded-lost`, `reopened-month`, `set-aside` or `carried-over`; a pass writes at most one note per period it took, so the list is bounded by the cap. `stopped_because` gains `deferred` | Null and empty defaults read every older row | 20 |
| D4 | `Watermark` in `backend/idhazh/contracts/ledger_index.py` | Retired, together with every committed `state/compact/<ledger>/<period>/watermark.json` | Nothing reads them after row 19; section 2.2 replaces them | 19 |

### 2.5 Events and outcome words

Each event is a `Model` in `backend/idhazh/contracts/gardener_events.py` (not persisted; section 11 does not apply). The owner approved the event list on 2026-10-04.

Table E - events

| # | Event | Emitted by | Fields |
| --- | --- | --- | --- |
| E1 | TaskPlanned | The runner, before the task | task, kind, shard, run_id, attempt, today, operator_range, declared: every knob of the declaration as text (thresholds, windows, ceilings, switches), leaving out `owns`, `reads` and prose |
| E2 | WindowChosen | `one_at_a_time.take`, before the first member | collection, since, until, ceiling, dry_run, mark (the `handled_through` it starts from), pages read |
| E3 | PeriodsChosen | Compaction, after it chooses | ledger; marks before; age lines (newest eligible day, newest closable month, keep line, year line); for each step, the span or none, the resume point and the start reason (mark, oldest-indexed, oldest-raw-day, operator-range, keep-line, none); cap; operator range; month deletes live or report-only |
| E4 | PeriodsTaken | Compaction, nested inside E5 | Packed and re-taken days; closed months; packed years; dropped months and raw days; dropped listings; entries written `empty` or `lost`; files set aside; marks after |
| E5 | TaskFinished | The runner, after the task | task, outcome (Table F), dry_run, seen, selected, taken, written, bytes_freed, stopped_because, resume_from, fault, recovered, next (the advice sentence), duration_ms, periods (E4) |
| E6 | ShardPublished | The publisher, after its push loop | shard, run_id, attempt, tasks, failed tasks, landing (landed, already-on-main, lost, refused), push try ("n of 6"), exit code and its meaning |

Each event is one line of JSON: `event` first (the kebab-case event name), then the model's fields in order, with `None` left out. It is ASCII only and goes to stderr through the standard `logging` module (CLAUDE.md section 1b). GitHub's runner reads workflow commands from stderr as well as stdout (`actions/runner`, `src/Runner.Worker/Handlers/ScriptHandler.cs`, read 2026-10-04), so nothing moves to stdout. Tests read the payload on the log record, never the text.

Table F - outcome words. `report.classify` picks the first that holds, in this order, and otherwise the pass's idle outcome.

| # | Word | Means |
| --- | --- | --- |
| F1 | `failed` | A code defect stopped the task (`fault: raised`). The only outcome that turns the job red |
| F2 | `deferred` | Stopped for a cause outside the code (`interrupted`, `api-unavailable`). The next wake resumes |
| F3 | `dry-run` | Found work and only reported it |
| F4 | `ceiling` | Did work, and more is left; `resume_from` says where the next wake starts |
| F5 | `done` | Did work, and nothing is left. Recovered notes do not change this |
| F6 | `empty` | The ledger has nothing to work on |
| F7 | `not-due` | Nothing has reached its line yet. The default idle outcome |
| F8 | `outside-range` | The operator range excludes every eligible period |

### 2.6 Gates every row runs

Every row runs what [run-the-gates.md](../docs/how-to/run-the-gates.md) selects for its changed files (`npm --prefix frontend run test:changed -- --list`), takes the expensive gates through the lock that page names, and records the inputs and results in its report. A row that changes Markdown runs `python backend/utilities/doc_load.py` on each changed page, before and after. CI runs the full suite once on the merge candidate. Each row below names only its focused checks.

## 3. The rows

### Row #1 - Compaction gets its own page

- **Scope:** The compaction section of the gardener page moves to a new page whose first sentence is "How a ledger's daily, monthly and yearly files are packed and dropped", and every link to a moved anchor is fixed. Level 0.
- **Files touched:**
  - `docs/architecture/publishing/idhazh-gardener.md`
  - `docs/architecture/publishing/ledger-compaction.md` (new)
  - `docs/agents/bootstrap.md`
  - every file that links to an anchor that moves, from a search at dispatch for `idhazh-gardener.md#` in `docs/`, `TODO/`, `backend/`, `frontend/src/`, `.github/`, `CLAUDE.md` and `AGENTS.md`
- **Acceptance gates:** local: `doc_load.py` on every changed page, before and after; a search for each moved anchor finds no link left pointing at the old page. CI: the full suite.
- **Oracle:** every link that named a moved anchor resolves on the new page. It cannot settle whether the split reads well; the `doc_load.py` rows are the evidence for that.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The section moves whole, with its tables and its `## Design rationale` entries; the gardener page keeps a two-line pointer | Fowler, 2026-10-04 |
| 2 | The link to a PROTOCOL.md that does not exist is removed | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep compaction on the gardener page | Rows 7 and 12 to 24 edit it, and the page would answer two questions | Nothing now; every later row edits a longer page | Fowler, 2026-10-04 |

### Row #2 - A dry run says nothing was deleted

- **Scope:** The report tells a dry run from a live one, and names the setting to change instead of a flag the command does not have. Level 1.
- **Files touched:**
  - `backend/idhazh/gardener/report.py`
  - `backend/tests/gardener/test_report.py` (new)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/test_report.py`; ruff; mypy. CI: the full suite.
- **Oracle:** a dry-run pass that took members renders neither "gone" nor `--no-dry-run`, and names `dry_run: false` in `config/gardener/<task>.json`; a live pass still renders "gone". It cannot settle whether a person finds the words clear.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `_what_next` branches on `dry_run`. A dry run says a live run would delete the members above and that nothing was deleted | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One sentence for both | A dry run reports data as gone while it still exists | Nothing | Fowler, 2026-10-04 |

### Row #3 - A read nobody named fails loudly

- **Scope:** `FileListing.holds`, `size_of` and `fetch` refuse, by name, a path inside a declared folder that no step named, instead of answering "not held". Level 2.
- **Files touched:**
  - `backend/idhazh/gardener/file_listing.py`
  - `backend/tests/gardener/test_file_listing.py`
  - any test this row shows to be reading silently, fixed in this row. If the fix needs a file that a row in flight lists, the worker stops and reports, and the owner orders the two rows.
- **Acceptance gates:** local: pytest on `backend/tests/gardener/test_file_listing.py` and the gardener tests the selector lists; ruff; mypy. CI: the full suite.
- **Oracle:** a test names one path, asks about a sibling path in the same folder, and gets a refusal that names both. It cannot settle reads that do not go through `FileListing`.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An answer of "not held" for a path nobody named is a defect: it hid the shared-window fault for a week | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Log a warning and go on | A wrong answer still reaches the step | Nothing | Fowler, 2026-10-04 |

### Row #4 - The ledger fault words live in contracts

- **Scope:** `LedgerFault` moves from `backend/idhazh/ledger/faults.py` to `backend/idhazh/contracts/ledger_fault.py`, because a persisted record will name it and contracts import no other subpackage (CLAUDE.md section 4). Level 2.
- **Files touched** (from a search for `idhazh.ledger.faults` and `ledger/faults`, 2026-10-04):
  - `backend/idhazh/ledger/faults.py` (deleted)
  - `backend/idhazh/contracts/ledger_fault.py` (new)
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/ledger_files.py`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `backend/tests/council/_imports.py`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 -m contract backend/tests/contracts/test_frontend_index_shapes.py`, the ledger tests the selector lists; ruff; mypy. CI: the full suite.
- **Oracle:** this is a move, so behaviour does not change. The property that could break is the binding: the test still holds `LedgerFault` name for name to `frontend/src/lib/data/slice-shapes.ts`. It cannot settle callers outside the repository.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `ledger/__init__.py` keeps exporting `LedgerFault`, so the callers that use `ledger.LedgerFault` do not change | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it in `ledger/` | A contract would import a subpackage | Nothing | Fowler, 2026-10-04 |

### Row #5 - A ledger's marks are read in one place

- **Scope:** New `backend/idhazh/gardener/ledger_marks.py`, first sentence "What a ledger's marks say: which packed files exist and how far each step has packed", names and reads the three indexes and the three watermarks; `CompactTree.read` and `period_inputs` use it. No behaviour changes. Level 2.
- **Files touched:**
  - `backend/idhazh/gardener/ledger_marks.py` (new)
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/tests/gardener/test_ledger_marks.py` (new)
  - `backend/tests/gardener/test_period_inputs.py`
- **Acceptance gates:** local: pytest on the two test files and the gardener tests the selector lists; ruff; mypy. CI: the full suite.
- **Oracle:** this is a refactor, so the gardener tests pass unchanged before and after. What could break is the set of paths a task names, and `test_period_inputs.py` pins that set. The new unit test pins the refusal `index-missing` for a watermark without its index, which row 19 later removes. It cannot settle anything beyond reading.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Extract first, so rows 12 to 19 change the rules in one place | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Change the rules where the marks are read today | The same reads are written in two modules | Every later row edits both | Fowler, 2026-10-04 |

### Row #6 - One run id per workflow run

- **Scope:** The history job uses the plan job's run id, and builds its own only when the plan job left none. Level 2.
- **Files touched:**
  - `.github/workflows/idhazh-gardener.yml`
  - `backend/tests/workflows/test_gardener_workflow.py`
  - `docs/architecture/publishing/idhazh-gardener.md` (the history job, one sentence)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 -m workflow backend/tests/workflows/test_gardener_workflow.py`; `doc_load.py` on the page. CI: the full suite.
- **Oracle:** the workflow test reads the one named workflow file and requires that the history step's `RUN_ID` names `needs.plan.outputs.run_id` first and that `TODAY` still reads `steps.due.outputs.today`. It fails if the line reverts. It cannot settle a run that crosses 00:00 UTC; the records of such a run show one id.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `RUN_ID: ${{ needs.plan.outputs.run_id \|\| format('{0}-{1}', steps.due.outputs.today, github.run_id) }}` | The owner, 2026-10-04 (decision Q2) |
| 2 | `--today` stays the history job's own UTC day, so the due check reads the clock of the job that acts (CLAUDE.md section 2) | The owner, 2026-10-04 (decision Q2) |
| 3 | The fallback is needed: the history job has `needs: [plan, run-tasks]` and `if: ${{ !cancelled() }}`, so it runs even when the plan job failed | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Take both the run id and `--today` from the plan job | The due check would use another job's clock | One expression, and a breach of CLAUDE.md section 2 | The owner, 2026-10-04 |
| 2 | Leave it | One run has two ids across midnight, so its records cannot be joined | Nothing | The owner, 2026-10-04 |

### Row #7 - The month-delete switch is named for what it does

- **Scope:** `monthly_window_dry_run` becomes `month_deletes_dry_run: bool` everywhere in one change, and a declaration that still carries the old key is refused by name. Level 2.
- **Files touched** (from a search for `monthly_window_dry_run`, 2026-10-04; search again at dispatch):
  - the 11 files `config/gardener/compact-*.json`
  - `backend/idhazh/contracts/knobs/gardener.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/utilities/migrate_to_parquet.py`
  - `tests/fixtures/gardener/runner/compact-gardener.json`
  - `tests/fixtures/gardener/garden/compact-gardener.json`
  - `tests/fixtures/gardener/garden/compact-feed-health.json`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/config/retention-ages.md`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `TODO/20260928-55-one-page-queries-every-ledger-plan.md`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_gardener_config.py backend/tests/gardener/tasks/test_compaction.py backend/tests/gardener/tasks/test_compaction_years.py backend/tests/ledger/test_migrate_to_parquet.py`; ruff; mypy; `doc_load.py` on the changed docs. CI: the full suite.
- **Oracle:** a declaration that carries the old key fails to load, and the error names the key (`extra="forbid"`). A search for the old name finds only git history. It cannot settle a copy of the name outside the repository.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Rename in place in one change, with no alias | The owner, 2026-10-04 |
| 2 | A config file is not a persisted payload, so CLAUDE.md section 11 does not apply | Owner ruling, 2026-09-21 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Accept both names for a while | A second spelling that nothing needs | One alias field and its removal later | Fowler, 2026-10-04 |

### Row #8 - The site reads empty, lost and set-aside periods

- **Scope:** `CompactEntry` gains `state`, `lost_days` and `set_aside` (Table D, D1), and the site reads them. It never fetches a file for an `empty` or `lost` period, shows a `lost` day as having no record, and still renders every other period. Level 5, approved by the owner on 2026-10-04.
- **Files touched:**
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_frontend_index_shapes.py`
  - `tests/fixtures/contracts/compact-index/` (new: an `empty` day, a `lost` day, a month with `lost_days`, an index written before this row)
  - `frontend/src/lib/data/compact-index.ts`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/slice.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/data/ledger-reach.ts`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/console/recording.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-ranges.spec.ts`
  - `docs/architecture/contracts/persistence.md`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 -m contract backend/tests/contracts/test_ledger_index.py backend/tests/contracts/test_frontend_index_shapes.py`; the specs the selector lists; the browser smoke in run-the-gates.md on a ledger page served from a fixture with an `empty` and a `lost` day (CLAUDE.md section 12, including a missing index); `doc_load.py`. CI: the full suite.
- **Oracle:** contract: an index written before this row reads as all `packed`; an `empty` entry with `bytes` above 0 is refused; a `lost_days` day outside its entry's period is refused; the field-set and vocabulary tests hold the frontend copy in step. Site: a slice across a `lost` day returns the other days' rows and names the lost day, and fetches no file for an `empty` or `lost` period. It cannot settle how a panel words the gap; Jony and Susan rule on that only if two layouts lead to different code.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader before writer: this row lands before any gardener row writes `empty`, `lost` or `set_aside` | Fowler, 2026-10-04 (contract order) |
| 2 | An empty period is an index entry with no file (decision M2) | The owner, 2026-10-04 |
| 3 | A lost day reaches a reader as "no record for this day", never as zero rows, so the site keeps going with enough context to say what is missing | The owner, 2026-10-04 (recovery theme) |
| 4 | `state` names whether a file exists. `bytes: null` is not used, because one null would mean two things | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep zero-row files (decision M1) | The owner ruled them waste | About 5 KB a file, kept until its month closes | The owner, 2026-10-04 |
| 2 | Read a missing entry as empty (decision M3) | A real loss would read as a quiet day | Nothing to build; a wrong answer on every hole | Fowler, 2026-10-04 |

### Row #9 - Each job's name says what its shard runs

- **Scope:** Each matrix leg carries its task names, and the job name formats them, so a run lists what every shard did without opening it. Level 3.
- **Files touched:**
  - `backend/idhazh/contracts/gardener_plan.py`
  - `backend/utilities/gardener_shards.py`
  - `backend/idhazh/gardener/shards.py`
  - `.github/workflows/idhazh-gardener.yml`
  - `backend/tests/contracts/test_gardener_plan.py`
  - `backend/tests/contracts/test_gardener_plan_matrix.py`
  - `backend/tests/workflows/test_gardener_workflow.py`
  - `docs/architecture/publishing/idhazh-gardener.md` (shards)
- **Acceptance gates:** local: pytest on the three test files, with `-m contract` and `-m workflow` where marked; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** the parity test keeps both planners byte-identical with the new `task_names` key, and the matrix test refuses a job name that reads a matrix key the contract does not declare. It cannot settle how GitHub shortens a long name on screen; the shard summary (row 22) lists every task in full.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `MatrixLeg` gains `task_names`, sorted and never empty, and both planners emit it from the same deal | The owner, 2026-10-04 (decision R1) |
| 2 | `name: "shard ${{ matrix.shard }}: ${{ join(matrix.task_names, ', ') }}"`. The workflow holds a format, never a list of names | The owner, 2026-10-04 (decision R1) |
| 3 | `GardenerPlan` is not persisted, so CLAUDE.md section 11 does not apply | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A composed `activity` string on each leg | A second spelling of the names, built in two planners | One field | Fowler, 2026-10-04 |
| 2 | Names by kind, such as "compaction x3" | It hides which ledgers ran | Nothing | Fowler, 2026-10-04 |

### Row #10 - workflow-runs reads only runs past its line, from its own mark

- **Scope:** The runs task asks GitHub only for runs created after its mark and on or before its line, one UTC day at a time, oldest day first. Its own record row carries the mark forward (Table D, D2). Level 5, approved by the owner on 2026-10-04 (decision O2).
- **Files touched:**
  - `backend/idhazh/gardener/github_collections.py`
  - `backend/idhazh/gardener/tasks/collection.py`
  - `backend/idhazh/gardener/one_at_a_time.py`
  - `backend/idhazh/gardener/report.py`
  - `backend/idhazh/contracts/collection_prune.py`
  - `backend/idhazh/contracts/knobs/gardener.py` (`CollectionPolicy.mark_lookback_days`)
  - `config/gardener/workflow-runs.json`
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/tasks/test_collection_task.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/contracts/test_collection_prune_row.py`
  - `tests/fixtures/contracts/collection-prune-row/` (new: a row with `handled_through`)
  - `tests/fixtures/github-collections/` (new: recorded pages for one created day)
  - `docs/architecture/publishing/idhazh-gardener.md` (collections)
- **How it works:**
  - The task reads its own newest record row from the `gardener` ledger, over the last `mark_lookback_days` named UTC days, with `ledger.load_days`. It names those day paths at run time with `FileListing.name` (row 12). A row written by a pass with a different `dry_run` value is not used.
  - With a mark: for each UTC day after the mark, up to the line's day, one query `created=<day>`. A day is handled whole, and then the mark moves to that day. The pass stops at the ceiling, and the mark stays on the last whole day.
  - With no mark: one query `created=<=<line>` with `per_page=1` finds the oldest run past the line from `total_count`. The walk starts on that run's day. When `total_count` is above 1,000, the oldest run is beyond GitHub's cap, so the pass handles members newest first and leaves the mark unset until a later wake finds 1,000 or fewer.
  - A dry run reports at most the ceiling's worth of members and counts the rest of each day, so a dry run also moves at least one whole day a wake.
  - Every member is still checked against the line before it is taken.
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/test_github_collections.py backend/tests/gardener/tasks/test_collection_task.py backend/tests/gardener/test_one_at_a_time.py`, and `-m contract backend/tests/contracts/test_collection_prune_row.py`; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** with recorded pages, a pass on 2026-10-04 with a 90-day window and a mark of 2026-06-30 sends `created=2026-07-01` first. A pass that hits the ceiling partway through a day leaves the mark on the day before. A live pass ignores a mark written by a dry run. A run newer than the line in a recorded page is still refused. It cannot settle GitHub's own `created` filter; the member check stays as the safety line.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A persisted mark, kept on the task's own record row, which lands under `state/raw/gardener/` every wake. A separate file there would sit inside a folder that `compact-gardener` owns, and the config loader refuses two owners | The owner (O2, "persist it under state/raw"), 2026-10-04; place by plan author |
| 2 | One UTC day per query keeps every search far below GitHub's 1,000-result cap, so the oldest runs are always reachable | Plan author, 2026-10-04 |
| 3 | `mark_lookback_days` is a knob with a default of 7. With no row in reach, the task starts with no mark, which is correct and only slower | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | The date filter alone (decision O1) | In a dry run, or with a backlog, the same runs are read again every wake | Nothing to build; repeated reads | The owner, 2026-10-04 |
| 2 | A mark file under `state/raw/gardener/marks/` | Two tasks would own one folder | A change to the ownership rule in `backend/idhazh/config.py` | Plan author, 2026-10-04 |
| 3 | A new folder `state/gardener/marks/` | Not under `state/raw/` as the owner asked, and a new root in `docs/reference/repository-layout.md` | One owned path per task and one new contract | Plan author, 2026-10-04 |

### Row #11 - workflow-artifacts reads from the oldest end and resumes from its mark

- **Scope:** The artifacts task reads pages from the last one backwards and stops at the first artifact newer than its line. Each page is checked against the order the walk relies on, and against the mark. Every page is read only when that check fails. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/github_collections.py`
  - `backend/idhazh/gardener/tasks/collection.py`
  - `config/gardener/workflow-artifacts.json`
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/tasks/test_collection_task.py`
  - `tests/fixtures/github-collections/` (new: recorded artifact pages, one out of order)
  - `docs/architecture/publishing/idhazh-gardener.md` (collections)
- **How it works:**
  - The first page gives `total_count`, and that gives the last page.
  - Pages are read from the last page backwards. On each page, every `created_at` must be at or before every `created_at` on the page read next, so the walk is oldest first.
  - Artifacts created on or before the mark day are skipped. Those after it, and on or before the line's day, are handled. The mark moves to a day only once every artifact of that day is handled.
  - When a page breaks the order, the pass reads every page as today, logs that the order check failed, and does not move the mark.
- **Acceptance gates:** local: pytest on the two test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** with recorded pages in GitHub's current order, a pass reads the last page and one more, and handles the oldest artifacts first. With one page out of order, it reads every page and leaves the mark where it was. Correctness never depends on the order; only the cost does. It cannot settle GitHub changing its order; the check catches that on the first wake after a change.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Combine a read from the oldest end (P2) with a stored mark (P3). The mark is a day, never a page number, because pages shift as artifacts expire | The owner, 2026-10-04 |
| 2 | The order is checked on every page, so an undocumented order lowers the cost and never decides what is deleted | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Read every page, as today (P1) | 14 pages every wake, about 7 seconds (an estimate) | Nothing to build | The owner, 2026-10-04 |
| 2 | Reach artifacts through each old run | One request for every run, including runs with no artifact, about 175 a day | A request per run | Plan author, 2026-10-04 |

### Row #12 - Which months may close

- **Scope:** A new module chooses the months the absorb step takes (Table B, B5). Completeness counts from the ledger's first day. A missing day is re-packed from raw files or recorded lost (Table C, C2), and a month with no row becomes an entry with no file. The other steps keep the shared window until their own rows. Level 3; it writes the shapes row 8 declared.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py` (new; first sentence "Which periods each compaction step may take on this wake"; the month rule only)
  - `backend/idhazh/contracts/gardener_events.py` (new; `PeriodsChosen` only)
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/file_listing.py` (`name`, with an injected lister)
  - `backend/utilities/gardener_publish.py` (passes a lister over `git ls-tree` for the checked-out commit)
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (new)
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py`
  - `backend/tests/gardener/test_sparse_shard.py`
  - `backend/tests/gardener/test_download_ceiling.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the five test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:**
  - Unit: the daily spans of the seven ledgers that failed on 2026-10-04, written into the test as literals, with today 2026-10-04: no chosen month is older than the oldest indexed month, and no pass ends `failed`.
  - Integration in `tmp_path`: a ledger indexed from 2026-09-12 to 2026-10-01 with no monthly entry and `daily_keep_days` 45 closes 2026-09 on 2026-11-20, counting from 2026-09-12. With 2026-09-20 missing and its raw files present, the day is re-packed. With no raw files, the day is in `lost_days`. A month with no row gets an `empty` entry and no file.
  - It cannot settle the real ledgers. The first scheduled run after the merge is read: the seven tasks that failed on 2026-10-04 must not end `failed`. If one does, the owner reopens this row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each step chooses its own periods, and the month step goes first | Fowler, 2026-10-04 |
| 2 | Completeness starts at the ledger's first day (decision N2); nothing is filled in before it | The owner, 2026-10-04 |
| 3 | A missing day is re-packed or recorded lost, and the pass never stops for it | The owner, 2026-10-04 (recovery theme) |
| 4 | `PeriodsChosen` is both the steps' parameter object and a log event; it is not persisted | Fowler, 2026-10-04 |
| 5 | The task names the paths it chose at run time through `FileListing.name`, so the step rules live in one place | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Fill a ledger's first month from the 1st with zero-row days (decision N1) | The owner ruled it waste | Up to 30 files a ledger, once | The owner, 2026-10-04 |
| 2 | Keep failing with `day-missing` and ask a person to restore the day | Manual work for a gap the gardener can record | Nothing to build; a red run per hole | The owner, 2026-10-04 |
| 3 | The planner reads the marks first and plans every path | The step rules in two places, and one ledger's fault fails the whole shard | A second pass over the marks | Fowler, 2026-10-04 |

### Row #13 - Which days may be packed

- **Scope:** Day packing follows Table B, B6 and B7: it starts after the daily mark, re-takes packed days in the re-run span, starts a first run at the oldest raw day, and records a day with no row as an entry with no file. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_batch.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:**
  - Unit: a mark of 2026-09-16, cap 8, `compact_after_days` 1 and today 2026-10-04 give new days 2026-09-17 to 2026-09-24, resuming at 2026-09-25.
  - Integration: raw days 2026-09-17 to 2026-10-02 reach 2026-10-02 in two passes. An empty ledger, using the declaration from `tests/fixtures/gardener/runner/compact-gardener.json` with `dry_run` set false in the test, writes nothing and ends `empty`. A day with no row writes no file and an `empty` entry. A first run that starts mid-month writes no entry before the first raw day. The case in `test_compaction.py` that pins a fill from the 1st is turned around to pin that no fill happens.
  - It cannot settle when GitHub re-runs a job; rows 17 and 24 cover late files.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A first run starts at the oldest raw day, not on the 1st of its month (decision N2) | The owner, 2026-10-04 |
| 2 | A day with no row is an entry with no file (decision M2) | The owner, 2026-10-04 |
| 3 | The re-run span is 30 days (`GITHUB_RERUN_DAYS`), because GitHub allows a re-run for 30 days | Fowler, 2026-10-04 |
| 4 | `lookback` now means the first run's look-back in months | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | New days limited to the months of one window, as before this plan | It stopped every compaction from packing new days | Nothing to build; no new day packed | Fowler, 2026-10-04 |
| 2 | Zero-row daily files (decision M1) | The owner ruled them waste | About 5 KB a day | The owner, 2026-10-04 |

### Row #14 - Which years may be packed

- **Scope:** Year packing follows Table B, B4: it starts after the yearly mark, waits until the monthly mark is strictly past December, carries its months' `lost_days`, and records a year with no row as an entry with no file. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the two test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a monthly index from 2026-01 to 2026-12, a monthly mark of 2027-01 and `monthly_keep_days` 48 make 2026 ready on 2027-02-18 and not on 2027-02-17; with the monthly mark at 2026-12, it is not ready. A ledger that began in 2026-05 packs 2026 from May. It cannot settle a real year; the first one packs in 2027.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One readiness test, with a strict `>` past December in every branch | Fowler, 2026-10-04 |
| 2 | A ledger that began after January packs its first year from its first month | Fowler, 2026-10-04 |
| 3 | The yearly index of a ledger that keeps every row gains one entry a year, and that is accepted. A `## Design rationale` entry on the compaction page says so | Plan author, 2026-10-04; the owner asked how to bound it, and the answer to that question confirms or replaces this decision |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A keep line for years | `published` and `summary-quality-evals` refuse deletion in `prune_refusal` | A knob, and deleting a whole year of rows from the ledgers that allow it | Plan author, 2026-10-04 |
| 2 | Pack years into decades | The index still grows, one level up | A fourth period kind across the contracts and the site | Plan author, 2026-10-04 |
| 3 | Keep only a first and a last year in the index | A Level 5 change to every index reader, to save about 60 bytes a year | The site's reader and the binding tests change | Plan author, 2026-10-04 |

### Row #15 - Each old month is dropped once

- **Scope:** The drop steps follow Table B, B1 to B3. The monthly index is the record of what is left to drop, a raw day past the line is deleted by its listed path without being parsed, and every retired raw listing goes. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/contracts/knobs/gardener.py` (the `max_periods_per_run` description now covers drops)
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_period_inputs.py` (turn `test_compaction_inputs_do_not_name_retired_raw_indexes` around so it requires the listings folder)
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a monthly index from 2025-01 to 2026-09, a keep line of 2025-10 and cap 8: B1 takes 2025-01 to 2025-08 and resumes at 2025-09. A live pass deletes those files and entries, and the next pass names no month older than the line. A report-only pass keeps them and reports them again. A raw day past the line whose file cannot be parsed is still deleted. It cannot settle the first live drop on a real ledger; `compact-gardener`'s first drop is due around November 2027.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The monthly index is the record of what is left to drop: a dropped month leaves the index and is never looked at again (decision L1) | The owner, 2026-10-04 |
| 2 | A drop deletes by listed path and parses nothing, so an unreadable file past the line cannot stop it (Table C, C7) | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A separate cleaned-through file (decision L2) | A second record that can disagree with the index | A new contract | The owner, 2026-10-04 |
| 2 | Keep looking at the three months just past the line (decision L3) | A month that slides past those three is never dropped | Nothing to build | The owner, 2026-10-04 |

### Row #16 - The shared window is gone

- **Scope:** `scheduled_range` returns nothing for compaction, `paths_for_task` names only the marks and the retired-listings folder, and the code that served the shared window is deleted. Level 2.
- **Files touched:**
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/utilities/migrate_to_parquet.py`
  - `backend/idhazh/contracts/knobs/gardener.py` (the `lookback` description)
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py`
  - `backend/tests/ledger/test_migrate_to_parquet.py`
- **Acceptance gates:** local: pytest on the four test files and the gardener tests the selector lists; ruff; mypy. CI: the full suite.
- **Oracle:** this row removes code, and the property that could break is what each task names: `test_period_inputs.py` requires exactly the marks and the listings folder for every compaction task. It cannot settle anything the earlier rows did not already test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The `months` parameter leaves `compaction.run` and `CompactTree.read`; the migrator passes its first and last month as the operator range | Fowler, 2026-10-04 |
| 2 | `_packing_paths` and the unused stamp in `_ledger_paths` are deleted (defects W6 and W7) | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the window as a fallback | A second implementation that nothing should use | It stays and drifts | Fowler, 2026-10-04 |

### Row #17 - A late file re-opens its month

- **Scope:** A raw file that lands in a month already closed re-opens that month (Table C, C3). The month's rows and the late rows are settled by the ledger's record key, the month file and its entry are rewritten, and the late raw files are deleted. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on `backend/tests/gardener/tasks/test_compaction.py` and the gardener tests the selector lists; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a month closed with rows for two work units, then a late raw file from one unit's re-run with the same record keys. After the pass, the month file holds each key once, with the value the ledger's settle rule picks. The late file is gone, the outcome is `done`, and the note is `reopened-month`. Other days of the pass still pack. It cannot settle a re-run more than 30 days late; GitHub does not allow one.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A late file re-opens its month, and the next pass re-packs it (decision J2) | The owner, 2026-10-04 |
| 2 | The merge uses the ledger's existing settle rule, the same record key and preference that day packing uses (`backend/idhazh/ledger/keys.py`), so a re-opened month holds what packing the late day first would have held | Plan author, 2026-10-04 |
| 3 | A month inside a packed year never re-opens: a year packs no earlier than `daily_keep_days` + 32 days after its December, and a re-run lands within 30 days | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Fail the task with `raw-in-absorbed-month` and keep the file (decision J3) | A red run until a person acts | Nothing to build | The owner, 2026-10-04 |
| 2 | Writers refuse to write into a closed month (decision J4) | The re-run's rows are lost, and every writer learns compaction state | Every writer changes | Fowler, 2026-10-04 |

### Row #18 - An unreadable file is set aside, and extra files wait

- **Scope:** Table C, rows C4, C5, C6 and C8. A file that cannot be read, or is too large, goes to `state/raw/<ledger>/set-aside/` and is counted on its entry. A day with more raw files than the cap packs the first files and leaves the rest for the next wake. A step chooses periods only while their listed sizes fit the shard's budget. Level 3; it writes the `set_aside` field row 8 declared.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py` (`over_the_ceiling` becomes a check that a correct choice never trips; tripping it is a code defect)
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/gardener/test_download_ceiling.py`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/reference/repository-layout.md` (the set-aside folder)
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py` on both pages. CI: the full suite.
- **Oracle:**
  - A day with one unreadable raw file packs its other files. The bad file is under `set-aside/` at its old path, and the entry says `set_aside: 1`.
  - A day with cap + 3 raw files packs the cap and ends `ceiling`; the next pass packs the 3, and the outcome is `done`.
  - A shard budget smaller than the chosen periods stops the choice early with `ceiling`, and `over_the_ceiling` is never reached.
  - It cannot settle real corruption, which has not been seen.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A set-aside file is moved, never deleted, under the raw tier, because the site copies only `state/compact/` | Plan author, 2026-10-04 |
| 2 | Extra files are carried by the re-run span of row 13; there is no second mechanism | Plan author, 2026-10-04 |
| 3 | The ceiling is applied when periods are chosen, from sizes the listing already holds | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep failing with `unreadable`, `too-many-raw-files` and `file-too-large` | A red run and manual work for something the gardener can record | Nothing to build | The owner, 2026-10-04 (recovery theme) |
| 2 | Leave a bad file in its day folder | The re-run span re-reads it on every wake for 30 days | Nothing to build; repeated reads | Plan author, 2026-10-04 |

### Row #19 - The marks are worked out from the indexes, and the watermark files go

- **Scope:** Each mark is worked out from the three indexes (section 2.2). The `Watermark` contract and every committed `state/compact/<ledger>/<period>/watermark.json` are deleted (Table D, D4), so a watermark without its index can no longer happen (Table C, C9). Level 5.
- **Files touched** (from a search for `Watermark`, `watermark_path`, `daily_through`, `monthly_through`, `yearly_through` and `watermark.json`, 2026-10-04; search again at dispatch, `TODO/` and `state/compact/` included):
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/ledger/paths.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/gardener/ledger_marks.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/named_trees.py`
  - `backend/idhazh/telemetry/door_prune.py`
  - `backend/idhazh/evals/observation_migration.py`
  - `backend/utilities/migrate_to_parquet.py`
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/gardener/test_named_trees.py`
  - `backend/tests/gardener/test_file_listing.py`
  - `backend/tests/gardener/test_ledger_marks.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_batch.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/ledger/test_ledger_files.py`
  - `backend/tests/ledger/test_migrate_to_parquet.py`
  - `backend/tests/ledger/test_trial_roots.py`
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/evals/test_observation_migration.py`
  - `backend/tests/test_canary_packing.py`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `TODO/20260930-57-upkeep-tasks-switch-on-plan.md` (its row "The eval ledger is packed live, and every scores window stays forever" reads its oracle from a watermark file)
  - every committed `state/compact/<ledger>/<period>/watermark.json`
- **Acceptance gates:** local: pytest on the test files above that the selector lists, `-m contract` included; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** for the committed indexes of every compaction ledger, read once at dispatch and written into the test as literals, the marks worked out from the indexes equal the `through` of each committed watermark file. A ledger with an index and no watermark resumes where its index ends. It cannot settle a watermark that was already wrong; this oracle would show it as a mismatch, and that mismatch is reported, not forced to agree.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Design the fault out instead of recovering from it: the indexes already say what each watermark says, once every empty period has an entry (rows 12 to 14) | The owner, 2026-10-04 (recovery theme); shape by plan author |
| 2 | Reader before writer: steps read marks from the indexes, then the files and the contract go, in this one row, because nothing outside the gardener reads a watermark (the site works out `through` from `daily.json`) | Plan author, 2026-10-04 |
| 3 | Before dispatch, Fowler confirms section 2.2 covers every case in Table C. If not, this row becomes: rebuild a missing index from named files, and keep the watermarks | Plan author, 2026-10-04 (ESCALATE trigger 6) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the watermarks, and rebuild a missing index from the files the marks name | Two records that can disagree, plus a repair path for that | A bounded rebuild per ledger | Plan author, 2026-10-04 |
| 2 | Keep failing with `index-missing` | Manual work | Nothing to build | The owner, 2026-10-04 (recovery theme) |

### Row #20 - The record says what was recovered and why a pass stopped

- **Scope:** Each task's record row carries its `recovered` notes and, only for a pass that stopped, one closed `fault` word (Table D, D3). The sentence a person reads is rendered from them when the row is read and is never stored. `deferred` ends a pass without turning the job red. Level 5, approved by the owner on 2026-10-04 (decision S2 and the recovery theme).
- **Files touched:**
  - `backend/idhazh/contracts/collection_prune.py`
  - `backend/idhazh/contracts/gardener_fault.py` (new; first sentence "Why a gardener pass stopped, and what it recovered instead of stopping")
  - `backend/idhazh/gardener/one_at_a_time.py` (`Stop` and `Pass` gain `fault` and `recovered`)
  - `backend/idhazh/gardener/report.py`
  - `backend/idhazh/gardener/runner.py` (an interruption maps to `interrupted`, any other exception to `raised`; only `failed` sets the shard's failed exit code)
  - `backend/idhazh/gardener/github_collections.py` (a retryable error after the client's retries maps to `api-unavailable`)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/tests/contracts/test_collection_prune_row.py`
  - `tests/fixtures/contracts/collection-prune-row/` (new: a `deferred` row with a fault, a `done` row with recovered notes)
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `docs/architecture/publishing/idhazh-gardener.md` (the record)
  - `docs/architecture/publishing/ledger-compaction.md` (the recovery notes)
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_collection_prune_row.py`, and pytest on the other three test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** the new fixtures round-trip. A `fault` beside `stopped_because: exhausted` is refused. `ceiling-reached.json`, which has no `fault`, still reads. Each recovery in Table C writes its note, and each stop writes its fault. A shard whose only non-green task is `deferred` exits 0. It cannot settle wording; the sentence is rendered and can change with no migration.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A closed word plus the existing `resume_from`; the sentence is rendered when read (decision S2) | The owner, 2026-10-04 |
| 2 | What was recovered is a note, not a fault, so a recovered pass is `done` | The owner, 2026-10-04 (recovery theme) |
| 3 | Exception text is never stored, because it can carry fetched row text (Guardrail #11) | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A stored free-text reason (decision S1) | Fetched text could reach the record, and no reader can act on prose | A sanitizer and a length cap | Fowler, 2026-10-04 |
| 2 | Every stop red, as today | A recoverable stop asks a person for work | Nothing to build | The owner, 2026-10-04 |

### Row #21 - Every gardener log line is one JSON event

- **Scope:** The events of Table E become models, `event_log.py` writes each one as one JSON line (section 2.5), and the free-text log lines of the gardener are deleted. Level 3.
- **Files touched:**
  - `backend/idhazh/contracts/gardener_events.py`
  - `backend/idhazh/gardener/event_log.py` (new; first sentence "How a gardener event becomes one log line")
  - `backend/idhazh/gardener/report.py` (`classify`)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Pass.idle_outcome`; WindowChosen in `take`)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/cli.py` (`settings_or_none` installs the handler once)
  - `backend/tests/gardener/test_event_log.py` (new)
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/gardener/tasks/test_visual_prune_task.py`
  - `backend/tests/gardener/tasks/test_names_only_shard.py`
  - every test that reads gardener log text with `caplog`, from a search for `caplog` under `backend/tests/gardener/` at dispatch
  - `docs/architecture/publishing/idhazh-gardener.md` (logging)
- **Acceptance gates:** local: pytest on the listed test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** unit: each event renders as one line of valid ASCII JSON with `event` first, `None` left out and nested models kept nested. Integration in `tmp_path`: one ledger for each outcome word in Table F. TaskPlanned comes before TaskFinished, and each carries its fields; tests read the payload on the record, not the text. It cannot settle how readable JSON is in GitHub's log viewer; row 22's summary is the view for a person.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | JSON lines (decision T2) | The owner, 2026-10-04 |
| 2 | One handler on stderr, its level from config (CLAUDE.md section 1b) | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One `key=value` line per event (decision T1) | The owner chose JSON | Nothing | The owner, 2026-10-04 |
| 2 | JSON plus a readable line for each event (decision T3) | Two renderings to keep in step | Twice the lines | Fowler, 2026-10-04 |

### Row #22 - A person reads a shard at a glance

- **Scope:** When it runs on GitHub, each task's lines fold into one group, a `failed` task adds one error line, and each shard writes a summary to its job page whether it passes or fails. The summary says where the record went, what the exit code means, and one line per task. Level 2.
- **Files touched:**
  - `backend/idhazh/gardener/event_log.py` (GitHub mode)
  - `backend/idhazh/gardener/run_summary.py` (new; first sentence "What one shard did, as Markdown for the job's summary page")
  - `backend/idhazh/contracts/gardener_events.py` (ShardPublished)
  - `backend/idhazh/gardener/runner.py` (`Outcome.finished_tasks`)
  - `backend/utilities/gardener_publish.py` (writes the summary in `try/finally`; its push lines fold into ShardPublished)
  - `backend/tests/gardener/test_run_summary.py` (new)
  - `backend/tests/gardener/test_event_log.py`
  - `backend/tests/gardener/test_publish.py`
  - `docs/architecture/publishing/idhazh-gardener.md` (the summary)
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py`. The sufficiency checks in `docs/concepts/design-system.md` apply to the summary, or a `## Design rationale` entry says why not. CI: the full suite.
- **Oracle:** a shard with one `failed` task whose record landed writes a summary with the landing line and the failed row, and still exits 1. A shard with only `deferred` and `done` tasks writes its summary and exits 0. An error line escapes `%`, CR and LF. It cannot settle how GitHub draws the summary; the first scheduled run after the merge shows it.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `::group::<task> (<kind>)` before TaskPlanned and `::endgroup::` after TaskFinished; a `failed` task adds `::error title=<task>::<fault> at <resume_from>: <advice>` | Fowler, 2026-10-04 |
| 2 | The summary is written in `try/finally`, so it exists on pass or fail | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A shared helper for `$GITHUB_STEP_SUMMARY` | Two writers do not earn one | A module | Fowler, 2026-10-04 |

### Row #23 - The gardener ledger is packed live

- **Scope:** `config/gardener/compact-gardener.json` gets `dry_run: false`, so the gardener's own records are packed into one file a day and then one a month. Level 2.
- **Files touched:**
  - `config/gardener/compact-gardener.json`
  - `backend/tests/contracts/test_gardener_config.py` (both of its switches in `LIVE_BY_DECISION`, with the owner's decision as the reason)
  - `docs/concepts/config/idhazh-gardener.md`
  - `TODO/20260930-57-upkeep-tasks-switch-on-plan.md` (its row "The upkeep record, the picture cleanup's record and the feed retirements are packed live" names this row by title for `compact-gardener`)
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_gardener_config.py`; `doc_load.py`. CI: the full suite.
- **Oracle:** `test_gardener_config.py` refuses a live switch with no decision, and accepts this one. The first scheduled run after the merge is read: `compact-gardener` ends `done` or `ceiling`, writes no zero-row file and no entry before the ledger's first day. If not, the owner sets `dry_run` back to `true` in a pull request at once. It cannot settle the first drop, due around November 2027.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Switch it on after rows 16 and 22, so its first live pass uses the new rules and is easy to read | The owner, 2026-10-04 (the gardener ledger is compacted); order by Fowler |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Switch it on now | Its first pass would fill its first month from the 1st under the old rules | About 29 zero-row files, about 155 KB (an estimate) | Fowler, 2026-10-04 |

### Row #24 - Months close 16 days after they end

- **Scope:** `daily_keep_days` becomes 16 in all 11 compaction declarations, and its floor becomes 1. `seen` and `counterfactual-scores` keep a 3-month window so their readers keep 90 days. A late re-run file is handled by row 17. Level 4: months closed at 16 days are not re-opened by going back.
- **Files touched:**
  - the 11 files `config/gardener/compact-*.json`
  - `backend/idhazh/contracts/knobs/gardener.py` (the `GITHUB_RERUN_DAYS` comment, the `daily_keep_days` floor and its description)
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py` (module docstring)
  - `backend/idhazh/ledger/ledger_files.py` (module docstring: a late raw file re-opens its month)
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/architecture/publishing/ledger-compaction.md` (a `## Design rationale` entry replacing the one of 2026-09-28: what a late re-run costs now)
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_gardener_config.py backend/tests/contracts/test_page_ceilings.py`, and pytest on `test_compaction.py`; `doc_load.py`. CI: the full suite.
- **Oracle:** every compaction declares 16; a 0-day keep is refused; the config check `refuse_what_the_declarations_break` in `backend/idhazh/config.py` still refuses a reach below a reader's need and passes for `seen` and `counterfactual-scores`, whose reach is at least 16 + 89 = 105 days against the 90 their readers need. `monthly_keep_days` must stay at least `daily_keep_days` + 32 = 48 days, and every declaration that sets it uses 93. It cannot settle how often a re-run lands late; 2 of 214 digest runs were re-run, at 4 and 13 hours.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Close months 16 days after they end, on every ledger | The owner, 2026-10-04 |
| 2 | `seen` and `counterfactual-scores` move from a 2-month to a 3-month window (decision K1) | The owner, 2026-10-04 |
| 3 | The floor drops to 1, because row 17 makes a late file safe at any keep | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep 31 days or more (decision J1) | Not what the owner asked | Nothing | The owner, 2026-10-04 |
| 2 | Keep those two ledgers at 31 days (decision K2) | Two rules instead of one | Nothing | The owner, 2026-10-04 |

### Row #25 - The retired raw listings code goes

- **Scope:** `drop_listings`, row B3 and the listings folder in `paths_for_task` are deleted once no ledger holds a retired listing. Level 1.
- **Precondition:** at dispatch, `git ls-tree --name-only origin/main state/raw/<ledger>/index/` lists nothing for each ledger a compaction declaration names. Until then the row waits; B3 empties the folders on live passes.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the two test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** no compaction task names a listings folder, and the compaction tests pass. It cannot settle a listing written after the precondition was read; nothing writes one since #1237.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Delete the code when its last input is gone, not before | Fowler, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Delete the listings by hand now | A one-off commit outside the gardener, for files the gardener already deletes | One commit | Fowler, 2026-10-04 |
