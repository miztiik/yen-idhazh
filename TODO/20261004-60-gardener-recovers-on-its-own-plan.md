# Plan 60 - The gardener chooses its own work and recovers on its own

**Last Updated**: 2026-10-05

**Level**: 5 (CLAUDE.md section 6). Rows 8, 10, 19 and 20 change persisted contracts (section 2.4). The owner approved each shape on 2026-10-04.

**Status**: written 2026-10-04 by the session owner from Fowler's design of the same day and the owner's rulings on it. Fowler's review of that design was applied on 2026-10-04, under ESCALATE trigger 6 and owner decision M1. It corrected the rows not yet dispatched, added rows 27 to 29, and changed shapes D1 and D3 after the owner had approved them. #1267 removed the retired raw listings and their code, so step B3 and row 25 are gone (owner decision N1, 2026-10-04).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | On 2026-10-04 seven of the eleven compaction tasks failed and none packed a new day. Since #1240, every compaction step reads one window that was built for the step that deletes old months, so the packing steps look in the wrong months. The run of 2026-10-03, before #1240, packed normally. The owner asked that each step choose its own periods, that no empty file is written, and that a fault is recovered and recorded so the pass moves on |
| Hard scope - in | - Each compaction step chooses its own periods (section 2.1).<br>- An empty day, month or year is an index entry with no file, and nothing is filled in before a ledger's first day (section 2.1, Table D row D1).<br>- Every fault in Table C is designed out or recovered, and the record says which (sections 2.3 and 2.4).<br>- Months close 16 days after they end on every compaction ledger; a late re-run file re-opens its month; `seen` and `counterfactual-scores` keep 3 months.<br>- Each old month is dropped once, and the monthly index is the record of what is left to drop.<br>- workflow-runs and workflow-artifacts read only what is past their line, starting from a mark on their own record.<br>- One run id per workflow run, and job names that list each shard's tasks.<br>- Every gardener log line is one JSON event, each shard writes a summary, and a dry run never says that anything is gone.<br>- `compact-gardener` packs live, and `monthly_window_dry_run` is renamed `month_deletes_dry_run`.<br>- A shard whose paths main changed after its commit lands nothing, and a push that runs out of tries says whether main kept moving (row 27).<br>- The gardener ledger is published, so the console can read it (row 28) |
| Hard scope - out | Table A below |
| ESCALATE triggers | 1. A persisted shape that section 2.4 does not declare.<br>2. A row that would delete a row of `published`, `seen` or `summary-quality-evals`, other than settling a re-opened month by its record key (Table C, C3). Their declarations refuse deletion in `prune_refusal`.<br>3. Fetched text in a log line, a record field, a file path or a URL (Guardrail #11).<br>4. A shard that would run past the 6 h job, or a row whose cost is over 3x its estimate.<br>5. The `dry_run` of workflow-runs or workflow-artifacts moving to `false` (Table A, A1).<br>6. Fowler's answer to the design brief of 2026-10-04 changes a decision in this plan. For a row not yet dispatched, the owner edits the row first. For a row already merged, STOP-AND-SURFACE ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)).<br>7. Two personas still disagree after one debate |
| Chosen strategy | Each step reads the ledger's own indexes and chooses its own periods. A fault the gardener can record is recorded on the period, and the pass moves on. Only a code defect turns a run red. The owner ruled on 2026-10-04, on Fowler's design of the same day |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 12 to 20 share the compaction step modules, so they run one at a time. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table A - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| A1 | Switching workflow-runs and workflow-artifacts to live deletes | Old runs and artifacts stay, as today. GitHub keeps a run's logs and artifacts for 90 days, this repository's setting and the most a public repository allows (read 2026-10-05). So the runs task, whose window is also 90 days, would delete only runs whose logs are already gone: a live pass shortens the Actions history and frees no log | An owner decision. First size `max_deletes_per_run` from a 7-day arrival count: `gh api "repos/miztiik/yen-idhazh/actions/runs?created=>=<today-7>&per_page=1" --jq .total_count`. On 2026-10-04 that read 1,226 runs, about 175 a day, and the declared ceiling is 50 deletes a wake. A day held between 32 and 401 runs from 2026-08-22 to 2026-10-04, and a live pass that its ceiling stops inside a day reads that day again at the next wake (row 10), so a ceiling below a busy day's count takes several wakes to pass it. A count from a search by date stops at 2,500, so a span longer than about two weeks is counted a day at a time |
| A2 | A keep line for years | The yearly index of a ledger that keeps every row gains one entry a year (row 14, decision 3) | A ledger whose declaration lets it forget whole years. `published` and `summary-quality-evals` refuse that in `prune_refusal` |
| A3 | Keying the rules in `backend/idhazh/gardener/period_inputs.py` on a declaration's kind instead of task names | One list of task names stays written in code (Guardrail #6) | A Level 2 row after row 16 |
| A4 | Event logging in `backend/idhazh/cli.py` and `backend/idhazh/telemetry/cli.py` | Those two commands keep free-text logs (CLAUDE.md section 1b) | A Level 2 row each after row 21, reusing `event_log` |
| A5 | Listing switched-off declarations in the plan job | A paused task does not appear in the run log | A request for it |
| A6 | A console panel for the recovery notes | The notes reach the record and the shard summary (row 22), but not the console | Row 28 publishes the gardener ledger; then Jony and Susan rule on the panel |
| A7 | Backend folds telling a lost day from a quiet day | A count over a lost day reads as zero activity, not as unknown | `LedgerFiles` in `backend/idhazh/ledger/ledger_files.py` carries the gaps to each fold: a Level 3 row |
| A8 | Rule L looking further back than its named places (section 2.2) | A ledger whose daily mark stalled for longer than B7's look-back keeps its older day files out of a rebuilt index | Looking back to `first_ledger_year` on every rebuild. That read grows with time (Guardrail #12), so it needs the owner's exception |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Compaction gets its own page | - | A | DONE | fantastic-umbrella | #1273 | Plan 60 row 1: compaction page |
| 2 | A dry run says nothing was deleted | - | A | DONE | literate-parakeet | #1274 | Plan 60 row 2: dry-run wording |
| 3 | A read nobody named fails loudly | - | A | DONE | curly-parakeet | #1277 | Plan 60 row 3: unnamed reads fail |
| 4 | The ledger fault words live in contracts | 1 | A | DONE | special-sniffle | #1276 | Plan 60 row 4: fault words in contracts |
| 5 | A ledger's marks are read in one place | - | A | DONE | silver-dollop | #1279 | Plan 60 row 5: marks in one place |
| 6 | One run id per workflow run | 1 | B | DONE | automatic-adventure | #1278 | Plan 60 row 6: one run id |
| 7 | The month-delete switch is named for what it does | 1 | B | DONE | ubiquitous-journey | #1286 | Plan 60 row 7: rename month switch |
| 8 | The site reads empty, lost and set-aside periods | 4 | B | DONE | refactored-eureka | #1287 | Plan 60 row 8: site reads lost periods |
| 9 | Each job's name says what its shard runs | 6 | C | DONE | miniature-waddle | #1282 | Plan 60 row 9: job names |
| 10 | workflow-runs reads only runs past its line, from its own mark | 2, 7, 9, 12 | C | DONE | didactic-potato | #1307 | Plan 60 row 10: runs read from a mark |
| 11 | workflow-artifacts reads from the oldest end and resumes from its mark | 10 | C | DONE | psychic-potato | - | Plan 60 row 11 |
| 12 | Which months may close | 3, 5, 7, 8, 27, 30 | D | DONE | fuzzy-dollop | #1303 | Plan 60 row 12: which months may close |
| 13 | Which days may be packed | 12 | D | DONE | silver-enigma | #1309 | Plan 60 row 13: which days may be packed |
| 14 | Which years may be packed | 13 | D | DONE | scaling-train | - | Plan 60 row 14 |
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
| 25 | The retired raw listings code goes | 15 | F | COLLAPSED #1267 | - | - | - |
| 26 | doc_load.py reads a web address as a web address | - | A | DONE | stunning-garbanzo | #1285 | Plan 60 row 26: doc_load web links |
| 27 | A shard lands nothing stale, and says why when it cannot land | 3, 9 | C | DONE | urban-spoon | #1291 | Plan 60 row 27: no stale landing |
| 28 | The console can read the gardener ledger | 23 | F | PENDING | - | - | - |
| 29 | doc_load.py measures every named Markdown page | 26 | A | DONE | effective-carnival | #1289 | Plan 60 row 29: doc_load every page |
| 30 | Every reader and rewriter of a compact index keeps an entry's state | 8 | D | DONE | psychic-guide | #1293 | Plan 60 row 30: index readers keep state |
| 31 | Panels say which days have no record | 8 | E | DONE | congenial-waddle | #1301 | Plan 60 row 31: panels show lost days |
| 32 | The explorer's date chart breaks its line at a lost day | 31 | E | PENDING | - | - | - |

## 2. Shared declarations

Rows point here. Each name, shape and rule is declared once.

### 2.1 How each step chooses its periods

Every line is computed from `today`, the wake's UTC day, and from each period's own end (CLAUDE.md section 2). An operator range (`--from` and `--to` on one named task, or the migrator's range) limits every step. The "newest eligible day" is the newest day at least `compact_after_days` whole days past its end, and the "newest eligible month" in B7 is the month that holds it (Fowler, 2026-10-04). The cap is the declaration's `max_periods_per_run`.

Table B - each step

| # | Step | Starts at | Takes | Adds to the listing |
| --- | --- | --- | --- | --- |
| B1 | Drop month files | The oldest monthly entry | Entries older than the keep line, oldest first, up to the cap. Live: delete the month file when the entry has one, delete its raw month folder, then remove the entry. Report-only: keep both and report them | Each month file and its `state/raw/<ledger>/YYYY/MM` folder |
| B2 | Drop raw days | - | Raw day folders older than the keep line, inside the months B1 names. They are deleted by listed path and never parsed | Nothing more |
| B4 | Pack years, only with `monthly_keep_days` | The year after the yearly mark; with none, the year of the oldest monthly entry | Consecutive years whose age line has passed and whose December the monthly mark is strictly past, up to the cap. A ledger that began after January packs its first year from its first month. A year with no row is an entry `empty` with no file. Its months' `lost_days` carry into the year entry | That year's month files, named from the monthly index |
| B5 | Absorb months | The month after the monthly mark; with none, the oldest month the daily index names; with an empty daily index, nothing | Consecutive months at least `daily_keep_days` past their end that the daily mark has passed, up to the cap. A month with a raw day still waiting is held for B6. Completeness counts days from the month's 1st, or from the ledger's first day when the ledger began inside that month. A missing day inside that span is recovered (Table C, C2). A month with no row is an entry `empty` with no file | Each month's daily files and its raw month folder |
| B6 | Pack days | The day after the daily mark | New days up to the earlier of the mark plus the cap and the newest eligible day. Also packed days inside the 30-day re-run span that hold new raw files; they count against the cap. A raw file in a closed month re-opens it (Table C, C3). A day with no row is an entry `empty` with no file | The raw folders and the packed day files of the new days and of the re-run span. Rule R and the re-take read the day files (Fowler, 2026-10-04) |
| B7 | First run: no daily mark | The oldest raw day in the raw month folders from the newest eligible month minus `lookback` months to the newest eligible month, or in the operator range. Never before the keep line when month deletes are live. A daily index with no mark beside it, which a pass cut before its mark landed leaves, starts it at the index's oldest day when that is older; row 19 deletes this case (Fowler, 2026-10-04) | As B6. An indexed day with no raw file keeps its entry, and the mark moves past it. With no raw day, nothing; the outcome is `empty` | Those raw month folders |

Every read has a fixed size (Guardrail #12). A pass names at most: the three indexes, plus the three watermarks until row 19; for each step, the cap times that step's periods; and, only when an index file is absent, the paths Rule L names (section 2.2). Each count comes from config or the calendar. Rule L's yearly paths grow by one a year, as the yearly index does (row 14, decision 3). Step B3, which dropped the retired raw listings, went with #1267 (row 25).

### 2.2 The marks

| # | Mark | Worked out as |
| --- | --- | --- |
| M1 | Daily mark | The newest of: the newest daily entry, the last day of the newest monthly entry, and the last day of the newest yearly entry |
| M2 | Monthly mark | The newest of: the newest monthly entry, and December of the newest yearly entry |
| M3 | Yearly mark | The newest yearly entry |

A mark can be worked out this way only because every period a step has looked at leaves an entry, an empty one included (rows 12, 13 and 14). Until row 19 lands, the watermark files stay, and the steps read them.

An entry can be gone while its packed file is still there, for example after an index is restored from an older commit, and a whole index file can be gone. Two rules adopt such a file instead of recording a gap (Table C, C14). Each reads only named paths.

- **Rule R (row 12).** Before a pass records a period `empty` or `lost`, it looks for that period's own packed file at its named path (`FileListing.name`). If the file is there, the pass adopts it as `packed`: its bytes from the listing, and its rows from the Parquet footer, inside the download budget left. It adds the recovery note `index-rebuilt` for that period. The rule lives in `backend/idhazh/gardener/ledger_marks.py`, whose first sentence already covers which packed files exist.
- **Rule L (row 19).** When an index file is absent, the pass looks only at named places, coarsest period first, and adopts each file it finds as Rule R does. A place with no file writes nothing.
  - Yearly: each year from `first_ledger_year` (Table D, D5) to the newest year old enough to pack.
  - Monthly: the months of a finite window. For a forever window, each month from the January after the newest yearly entry, or from January of `first_ledger_year` when there is none.
  - Daily: each day from the month after the monthly mark to the newest eligible day, or, with no monthly entry, from the first month step B7 starts from. At most 31 paths a month.

### 2.3 Recovery instead of failure

A pass never stops for something it can record. Each fault below is designed out, or recovered on this wake or the next. Only `failed` turns a job red, and it means a code defect, the one case a person must act on.

Table C - each fault

| # | What stopped the pass before | Now | Recorded as | Outcome | Row |
| --- | --- | --- | --- | --- | --- |
| C1 | A month chosen from before the ledger began (`day-missing`) | Designed out. B5 starts at the oldest indexed month, and completeness starts at the ledger's first day | - | - | 12 |
| C2 | A day inside history with no entry (a hole) | Re-packed from its raw files when any are left, or else adopted when its packed file is there (C14). Otherwise it gets an entry `lost`, and the day goes into its month's `lost_days` when the month closes | `repacked-from-raw` or `recorded-lost`, with the day | `done` | 12 |
| C3 | A raw file in a closed month (a late re-run) | The month re-opens. Its rows and the late rows are settled by the ledger's record key, the month file and its entry are rewritten, and the late raw files are deleted | `reopened-month`, with the month | `done` | 17 |
| C4 | More raw files in one day than `max_raw_files_per_period` | The first files by name are packed. The rest stay where they are, and B6's re-run span takes them on the next wake | `carried-over`, with the day | `ceiling` | 18 |
| C5 | A raw file that cannot be read, or is larger than the size ceiling | Moved to `state/raw/<ledger>/set-aside/`, under its path relative to `state/`, and counted in its entry's `set_aside`. The rest of the day packs | `set-aside`, with the day | `done` | 18 |
| C6 | A packed day or month file that cannot be read when its month or year closes | Moved to set-aside as in C5. Its days go into `lost_days`, and the period closes | `set-aside` and `recorded-lost` | `done` | 18 |
| C7 | A raw day past the keep line whose files cannot be parsed | Designed out. B2 deletes by listed path and parses nothing | - | - | 15 |
| C8 | The shard's download ceiling (`over_the_ceiling` in `runner.py`) | Designed out. A step chooses a period only while its listed size fits what is left of the shard's budget | - | `ceiling` | 18 |
| C9 | A watermark without its index (`index-missing`) | Designed out. Each mark is worked out from the indexes (section 2.2), and the watermark files go | - | - | 19 |
| C10 | The job is killed part way through a pass, by a timeout or a cancelled run | Designed out. A shard lands only through its one commit, so a killed pass lands nothing, and the next wake starts from the same marks | - | - | 20 |
| C11 | GitHub's API is unavailable to a collection pass: a 429 or 5xx answer, or a connection that fails or times out, as row 20's error classifier names them. Nothing inside a wake retries | The mark stays, and the next wake resumes from it | fault `api-unavailable` | `deferred` | 20 |
| C12 | An exception that no other row of this table names, including a 4xx answer other than 404, 409, 410, 422 and 429 (row 20) | The task stops at that period. The shard's other tasks still run, and the next wake retries | fault `raised`, the exception's type only and never its text | `failed` | 20 |
| C13 | A packed day or month file that its index names and the tree lacks, when its month or year closes | Treated as unreadable (C6): its days go into `lost_days`, and the period closes. There is no file to set aside | `recorded-lost` | `done` | 18 |
| C14 | An index file that is absent while its period was packed (`index-missing`), or a packed file at its named path that no entry names, which would otherwise be recorded `lost` | Adopted from named paths: an absent index by Rule L, and a file that no entry names by Rule R (section 2.2). Nothing is deleted | `index-rebuilt`, with the period | `done` | 12, 19 |
| C15 | A member GitHub will not delete (collections: a 409 or 422 answer). Today the refused delete stops the pass, and every later pass meets that member first | Recorded with its id. It counts against the delete ceiling, the pass goes on, and the mark may pass it | `not-deletable`, with the member id | `done` | 20 |

`state/raw/<ledger>/set-aside/` is never named by any step, never copied to the site (only `state/compact/` is), and never deleted by the gardener. A person reads it when the console shows a non-zero `set_aside`.

### 2.4 Persisted shapes

Every persisted shape below, D1 to D4, follows CLAUDE.md section 11: a new `version`, one changelog line, at most five lines in the changelog, and a read-side default that reads every older payload. D5 is a config value, which section 11 does not cover (owner ruling, 2026-09-21).

Table D - contract changes

| # | Contract | Change | How older payloads read | Row |
| --- | --- | --- | --- | --- |
| D1 | `CompactEntry` in `CompactIndex`, `backend/idhazh/contracts/ledger_index.py` | `state`: `packed` (the default), `empty` or `lost`. `lost` is a daily state only: a monthly or yearly entry is `packed` or `empty` and lists its lost days in `lost_days`, so no reader handles a lost month or year. An `empty` or `lost` entry holds no file, and its `bytes` and `rows` are 0. `lost_days`: ascending UTC days inside a monthly or yearly entry's period that were recorded lost; empty by default; never on a daily entry. `set_aside`: how many files were moved aside while packing the period; default 0 | The defaults read every committed index as all `packed`, so nothing is rewritten. A zero-row file written before this row stays a valid `packed` entry until its month closes | 8 |
| D2 | `CollectionPruneRow` in `backend/idhazh/contracts/collection_prune.py` | `handled_through`: a UTC day. Every member created on or before that day was handled by a pass with the same `dry_run` value: deleted, recorded as not deletable, or reported. Null when the pass handled nothing | The null default reads every older row | 10 |
| D3 | `CollectionPruneRow`, and new `backend/idhazh/contracts/gardener_fault.py` | `fault`: `raised` or `api-unavailable`, allowed only beside `stopped_because` `failed` or `deferred`. `recovered`: a list of `{note, subject}`. `note` is `repacked-from-raw`, `recorded-lost`, `reopened-month`, `set-aside`, `carried-over`, `index-rebuilt` or `not-deletable`. `subject` is the period or the member id the note is about, typed as `MemberId` in `collection_prune.py`: `MEMBER_ID_PATTERN`, at most 512 characters, which every period string also matches. Each note names one period or member the pass took or adopted, so the list is bounded by the cap, the delete ceiling and Rule L's named paths (section 2.2). `stopped_because` gains `deferred` | Null and empty defaults read every older row | 20 |
| D4 | `Watermark` in `backend/idhazh/contracts/ledger_index.py` | Retired, together with every committed `state/compact/<ledger>/<period>/watermark.json` | Nothing reads them after row 19; section 2.2 replaces them | 19 |
| D5 | `GardenerConfig` in `backend/idhazh/contracts/knobs/gardener.py`, read from `config/idhazh_gardener.json` | `first_ledger_year`: the UTC year from which Rule L looks for yearly and monthly files (section 2.2). The value is 2026: the repository was created on 2026-08-20, so no ledger holds an earlier year | Not a persisted payload. The committed file gains the value in the same change | 19 |

### 2.5 Events and outcome words

Each event is a `Model` in `backend/idhazh/contracts/gardener_events.py` (not persisted; section 11 does not apply). The owner approved the event list on 2026-10-04.

Table E - events

| # | Event | Emitted by | Fields |
| --- | --- | --- | --- |
| E1 | TaskPlanned | The runner, before the task | task, kind, shard, run_id, attempt, today, operator_range, declared: every knob of the declaration as text (thresholds, windows, ceilings, switches), leaving out `owns`, `reads` and prose |
| E2 | WindowChosen | `one_at_a_time.take`, before the first member | collection, since, until, ceiling, dry_run, mark (the `handled_through` it starts from), pages read |
| E3 | PeriodsChosen | Compaction, after it chooses | ledger; marks before; age lines (newest eligible day, newest closable month, keep line, year line); for each step, the span or none, the resume point and the start reason (mark, oldest-indexed, oldest-raw-day, operator-range, keep-line, none); cap; operator range; month deletes live or report-only |
| E4 | PeriodsTaken | Compaction, nested inside E5 | Packed and re-taken days; closed months; packed years; dropped months and raw days; entries written `empty` or `lost`; files set aside; marks after |
| E5 | TaskFinished | The runner, after the task | task, outcome (Table F), dry_run, seen, selected, taken, written, bytes_freed, stopped_because, resume_from, fault, recovered, next (the advice sentence), duration_ms, periods (E4) |
| E6 | ShardPublished | The publisher, after its push loop | shard, run_id, attempt, tasks, failed tasks, landing (the words in `backend/idhazh/contracts/shard_landing.py`, row 27: landed, already-on-main, stale, lost, refused), push try ("n of 6"), exit code and its meaning |

Each event is one line of JSON: `event` first (the kebab-case event name), then the model's fields in order, with `None` left out. It is ASCII only and goes to stderr through the standard `logging` module (CLAUDE.md section 1b). GitHub's runner reads workflow commands from stderr as well as stdout (`actions/runner`, `src/Runner.Worker/Handlers/ScriptHandler.cs`, read 2026-10-04), so nothing moves to stdout. Tests read the payload on the log record, never the text.

Table F - outcome words. `report.classify` picks the first that holds, in this order, and otherwise the pass's idle outcome.

| # | Word | Means |
| --- | --- | --- |
| F1 | `failed` | A code defect stopped the task (`fault: raised`). The only outcome that turns the job red |
| F2 | `deferred` | Stopped because GitHub's API was unavailable (`api-unavailable`), a cause outside the code. The next wake resumes |
| F3 | `dry-run` | Found work and only reported it |
| F4 | `ceiling` | Did work, and more is left; `resume_from` says where the next wake starts |
| F5 | `done` | Did work, and nothing is left. Recovered notes do not change this |
| F6 | `empty` | The ledger has nothing to work on |
| F7 | `not-due` | Nothing has reached its line yet. The default idle outcome |
| F8 | `outside-range` | Nothing eligible is inside the operator range, and nothing before the range blocks it. When a step's first period is ready and the range starts after it, the range is refused at that period instead (row 12) |

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
| 2 | The link to Delta Lake's PROTOCOL.md stays: it is a web address that `doc_load.py` reads as a path in this repository (found during execution; row 26 fixes the tool) | The owner, 2026-10-04 |

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
  - `docs/architecture/publishing/ledger-compaction.md` (found during execution)
  - `frontend/src/lib/data/slice-shapes.ts` (found during execution)
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
- **Files touched** - corrected during execution (Fowler review 2026-10-04), from a search for `monthly_window_dry_run` at dispatch:
  - every compaction declaration, `config/gardener/compact-*.json`, `compact-run-plan.json` included
  - `backend/idhazh/contracts/knobs/gardener.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/utilities/ledger_migration/packing.py`
  - `tests/fixtures/gardener/runner/compact-gardener.json`
  - `tests/fixtures/gardener/garden/compact-gardener.json`
  - `tests/fixtures/gardener/garden/compact-feed-health.json`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/ledger_migration/test_packing_governance.py`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/config/retention-ages.md`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `TODO/20260928-55-one-page-queries-every-ledger-plan.md`
  - `TODO/20261004-pipeline-tests-migration-plan.md`
  - attempts description: carried from row 27 (#1291), owner 2026-10-04
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_gardener_config.py backend/tests/gardener/tasks/test_compaction.py backend/tests/gardener/tasks/test_compaction_years.py backend/tests/ledger_migration/` (the migration tests' path corrected during execution (Fowler review 2026-10-04)); ruff; mypy; `doc_load.py` on the changed docs. CI: the full suite.
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
  - `backend/tests/contracts/_fixtures.py` (found during execution: the round-trip list names each fixture)
  - `tests/fixtures/contracts/compact-index/` (new: an `empty` day, a `lost` day, a month with `lost_days`, an index written before this row)
  - `frontend/src/lib/data/compact-index.ts`
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/slice.ts`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `frontend/src/lib/data/ledger-reach.ts` (read, no change: it counts an entry by its `covers` alone)
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/console/recording.ts` (read, no change: it never reads an entry)
  - `frontend/scripts/published-ledgers.mjs` (found during execution, and asked for again by the Fowler review 2026-10-04: the site build named a file for every entry)
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-ranges.spec.ts`
  - `frontend/tests/ledger-copy.spec.ts` (found during execution, and asked for again by the Fowler review 2026-10-04)
  - `frontend/tests/published-ledgers.spec.ts` (found during execution)
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md` (the `ENTRY_STATES` binding this row adds)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (found during execution)
  - `backend/idhazh/ledger/ledger_files.py` (corrected during execution (Fowler review 2026-10-04))
  - `backend/idhazh/evals/observation_migration.py` (corrected during execution (Fowler review 2026-10-04))
  - `backend/tests/ledger/test_ledger_files.py` (corrected during execution (Fowler review 2026-10-04))
  - `backend/tests/evals/test_observation_migration.py` (corrected during execution (Fowler review 2026-10-04))
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
  - `backend/idhazh/contracts/knobs/gardener.py` (`CollectionTaskPolicy.mark_lookback_days`; the row named `CollectionPolicy`, which does not exist)
  - `config/gardener/workflow-runs.json`
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/tasks/test_collection_task.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/contracts/test_collection_prune_row.py`
  - `tests/fixtures/contracts/collection-prune-row/` (new: a row with `handled_through`; the three rows already there gain `handled_through: null`, found during execution)
  - `tests/fixtures/github-collections/` (new files: recorded pages for one created day, a day whose `total_count` is 1,001, and the repository's own answer with its `created_at`; `runs-page-1.json` deleted, because nothing reads it once the runs are searched by day, found during execution)
  - `docs/architecture/publishing/idhazh-gardener.md` (collections)
  - `backend/idhazh/gardener/collection_mark.py` (new; first sentence "Through which UTC day has a collection task's walk handled every member, by its own record?"; found during execution, Fowler's ruling)
  - `backend/tests/gardener/test_collection_mark.py` (new; found during execution)
  - `backend/tests/gardener/_records.py` (new; files a record row through the ledger door for both test modules; found during execution)
  - `backend/tests/gardener/test_report.py` (a dry walk's ceiling line; found during execution, Fowler's ruling)
  - `backend/tests/contracts/_fixtures.py` and `backend/tests/ledger/_fixtures.py` (they name the new row; found during execution)
  - `docs/concepts/config/idhazh-gardener.md`, `docs/architecture/contracts/state-ledgers.md` and `docs/how-to/prune-a-collection.md` (the knob, the row's new cell, the record's first reader, and the dry walk's ceiling line; found during execution)
- **How it works:**
  - The task reads its own record rows from the `gardener` ledger, over the last `mark_lookback_days` named UTC days, with `ledger.load_days`, and takes the latest `handled_through` among them (decision 5). It names those day paths at run time with `FileListing.name` (row 12). A row written by a pass with a different `dry_run` value is not used.
  - With a mark: for each UTC day after the mark, up to the line's day, one query `created=YYYY-MM-DDT00:00:00Z..YYYY-MM-DDT23:59:59Z`. Both bounds carry `Z`, so the day's time zone is never left to GitHub. A day whose `total_count` is over 1,000 is split into 24 hourly queries, because one search returns at most 1,000 results. A day is handled whole, and then the mark moves to that day; a split day moves it only after all 24 queries. The pass stops at the ceiling, and the mark stays on the last whole day.
  - Each query's pages are read from the last to the first, so a live delete never moves a run the pass has not read yet (Fowler, 2026-10-04).
  - With no mark: the task reads the repository's `created_at` once (`GET /repos/{owner}/{repo}`). If the line is before it, no run is older than the line, and the mark starts at the line's day. Otherwise the task finds the oldest day with a run by halving the span from `created_at` to the line, one query `created=<=D` with `per_page=1` a step, testing `total_count > 0`: about 9 queries for a year of days. The walk starts on that day.
  - A dry run reports at most the ceiling's worth of members and counts the rest of each day, so a dry run also moves at least one whole day a wake.
  - Every member is still checked against the line before it is taken.
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/test_github_collections.py backend/tests/gardener/tasks/test_collection_task.py backend/tests/gardener/test_one_at_a_time.py`, and `-m contract backend/tests/contracts/test_collection_prune_row.py`; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** with recorded pages, a pass on 2026-10-04 with a 90-day window and a mark of 2026-06-30 sends `created=2026-07-01T00:00:00Z..2026-07-01T23:59:59Z` first. A recorded day with `total_count` 1,001 sends 24 hourly queries, and the mark passes that day only after all of them. A pass that hits the ceiling partway through a day leaves the mark on the day before. A live pass ignores a mark written by a dry run. With no mark and a repository created after the line, no page of runs is read; with no mark and an older repository, the halving finds the oldest day from recorded `total_count` answers. A run newer than the line in a recorded page is still refused. It cannot settle GitHub's own `created` filter; the member check stays as the safety line.
- **Found during execution:** the repository's oldest run is from 2026-08-22 (read from GitHub on 2026-10-04), so runs first reach the 90-day line on 2026-11-20, not on about 2026-11-18 as decision 4 estimated from the day the repository was created. `ledger.load_days` lists every raw day folder of a ledger on disk before it keeps the named days (`raw_files._day_folders`), so on a full checkout its read grows with the repository (Guardrail #12); on a runner the checkout holds only the days the task fetched. It is filed as defect 59 in `TODO/20260823-known-defects-plan.md`, because the read is the ledger door's and every caller of `ledger.load_days` shares it.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A persisted mark, kept on the task's own record row, which lands under `state/raw/gardener/` every wake. A separate file there would sit inside a folder that `compact-gardener` owns, and the config loader refuses two owners | The owner (O2, "persist it under state/raw"), 2026-10-04; place by plan author |
| 2 | One UTC day per query, with `Z` on both bounds. A day is far below GitHub's cap of 1,000 results a search today, about 175 runs a day on 2026-10-04, but nothing holds it there, so a day over the cap is split into 24 hourly queries rather than losing runs while the mark moves past them | Plan author, 2026-10-04; the bounds and the split Fowler review, 2026-10-04 |
| 3 | `mark_lookback_days` is a knob with a default of 7. With no row in reach, the task starts with no mark, which is correct and only slower | Plan author, 2026-10-04 |
| 4 | With no mark, the walk starts from the repository's `created_at` or from the halving, never from `total_count`, which is a count and cannot name the oldest run. On 2026-10-04 the 90-day line, 2026-07-06, fell before the repository existed, so such a pass reads no page of runs; runs first reach the line on about 2026-11-18 | Fowler review, 2026-10-04 |
| 5 | The mark is the latest `handled_through` on the task's own rows with the same `dry_run`, because a day stays true once written; a row with none is passed over. A pass that finishes no new day carries the day it started from forward, so null means a task that keeps no mark, or a pass that failed before its walk began | Fowler, 2026-10-04 (row 10 worker's consult) |
| 6 | Each query is read from its last page back | Fowler, 2026-10-04 (row 10 worker's consult) |
| 7 | A dry walk past its ceiling keeps `stopped_because: ceiling`, and `resume_from` names where a live pass would stop; its line says the rest of the day was counted, not listed | Fowler, 2026-10-04 (row 10 worker's consult) |
| 8 | `handled_through` is refused on or after the row's `date`, the bound that always holds. No bound against `until`: a lengthened window moves the line behind a mark already reached | Fowler, 2026-10-04 (row 10 worker's consult) |
| 9 | A run from an earlier day than one before it: the pass goes on, and its mark stays where it started. An hour GitHub counts over 1,000 fails the pass, with the mark on the last whole day | Fowler, 2026-10-04 (row 10 worker's consult) |
| 10 | The mark is read in a module of its own, and `collection_named` and `BUILDERS` went in a structural commit first, because the runs listing now takes its walk's days | Fowler, 2026-10-04 (row 10 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | The date filter alone (decision O1) | In a dry run, or with a backlog, the same runs are read again every wake | Nothing to build; repeated reads | The owner, 2026-10-04 |
| 2 | A mark file under `state/raw/gardener/marks/` | Two tasks would own one folder | A change to the ownership rule in `backend/idhazh/config.py` | Plan author, 2026-10-04 |
| 3 | A new folder `state/gardener/marks/` | Not under `state/raw/` as the owner asked, and a new root in `docs/reference/repository-layout.md` | One owned path per task and one new contract | Plan author, 2026-10-04 |
| 4 | With no mark, read the oldest run from `total_count`, and walk newest first when it is above 1,000 (this row as first written) | A count is not a date, so it cannot name the oldest run, and the newest-first branch existed only because of that | Nothing to build; a first pass that cannot say where it starts | Fowler review, 2026-10-04 |
| 5 | Read the 1,000 runs one search returns for an hour over the limit, and keep the mark on the day before | 1,000 runs in an hour is about 140 times today's rate, an estimate from about 175 runs a day, and a failed pass names the hour | It recovers on its own in a live pass, as deletes thin the hour, but needs the way of holding a mark that row 11 builds | Fowler, 2026-10-04 (row 10 worker's consult) |
| 6 | Read each query front to back, as the artifacts are | A live pass that deletes as it reads moves later runs onto pages already read, and the mark then passes them for good | Nothing to build | Fowler, 2026-10-04 (row 10 worker's consult) |
| 7 | The newest row's mark, rather than the latest day | A row whose pass failed before its walk began would send the next pass back to the halving | Nothing to build; a first walk repeated | Fowler, 2026-10-04 (row 10 worker's consult) |

### Row #11 - workflow-artifacts reads from the oldest end and resumes from its mark

- **Scope:** The artifacts task reads pages from the last one backwards and stops at the first artifact newer than its line. Each page is checked against the order the walk relies on, against the mark, and against the first page's `total_count`. Every page is read only when the order check fails. Level 3.
- **Follow-ups:**
  - Row 10 built the walk this row needs. `collection_mark.last_mark` reads the mark for any collection task. `one_at_a_time.take(mark=...)` passes over what the mark covers, moves the mark a whole day at a time, counts the rest of a day on a dry run past its ceiling, and keeps the mark where it was when a member arrives out of day order. So this row hands `take` its artifacts oldest day first, and writes none of those rules again. `workflow-artifacts.json` names `state/raw/gardener` and `state/compact/gardener` under `reads`, and `mark_lookback_days`, as `workflow-runs.json` does; found during execution (row 10 report), 2026-10-05.
  - A count from a search by date stops at 2,500: on 2026-10-05 the runs created on or before 2026-09-20 counted 2,500, where their days add up to 4,404. The artifacts list is not a search, but this row finds its last page and checks for shifted pages from `total_count`, so it first confirms the count is exact for the artifacts list; found during execution (row 10 report), 2026-10-05.
- **Files touched:**
  - `backend/idhazh/gardener/github_collections.py`
  - `backend/idhazh/gardener/tasks/collection.py`
  - `config/gardener/workflow-artifacts.json` (gains `reads` and `mark_lookback_days`, as the first follow-up says)
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/tasks/test_collection_task.py`
  - `tests/fixtures/github-collections/` (new: `artifacts-oldest-pages.json`, GitHub's last four pages of the 1,613 artifacts it listed on 2026-10-05, served as pages 1 to 4 of 313. The page out of order and the count that grows are built in the tests from it, one field changed. `artifacts-page-1.json` deleted: it was not GitHub's order, and three of its artifacts were older than the repository; found during execution, Fowler's ruling)
  - `docs/architecture/publishing/idhazh-gardener.md` (collections)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Collection.listing_intact`; found during execution, Fowler's ruling)
  - `backend/tests/gardener/test_one_at_a_time.py` (found during execution)
  - `docs/concepts/config/idhazh-gardener.md`, `docs/how-to/prune-a-collection.md` and `docs/architecture/contracts/state-ledgers.md` (each said only `workflow-runs` keeps a mark; found during execution)
- **How it works:**
  - The first page gives `total_count`, and that gives the last page.
  - Pages are read from the last page backwards. Each page is sorted by `created_at`, and the oldest UTC day on each page must be at or after the newest UTC day on every page read before it, so the walk is oldest first by day (found during execution: GitHub orders by id, and `created_at` runs up to 76 minutes out of that order). The next page is read and checked before any artifact of the page in hand is taken.
  - Artifacts created on or before the mark day are skipped. Those after it, and on or before the line's day, are handled. The mark moves to a day only once every artifact of that day is handled.
  - When a page breaks the order, the pass reads every page as today, logs that the order check failed, and does not move the mark.
  - Each page's `total_count` must equal the first page's, less the artifacts this pass deleted. An artifact created during the read pushes every older one a place down, so one can move from a page not yet read onto a page already read while the order still holds. When the count differs, the pass handles what it read and does not move the mark.
  - The list must end where the first page's count says: the last page holds what is left of the count, and when that page is full, the page after it is read, never handed on, and must be empty. When it does not, the pass handles what it read and does not move the mark (decision 10, the second follow-up).
- **Acceptance gates:** local: pytest on the two test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** with recorded pages in GitHub's current order, a pass reads the last page and one more, and handles the oldest artifacts first. With one page out of order, it reads every page and leaves the mark where it was. With pages whose `total_count` grows between two reads, the mark stays. Safety never depends on the order, because each artifact is checked against the line before it is taken; completeness does, and the `total_count` check guards it. It cannot settle GitHub changing its order; the check catches that on the first wake after a change. Nor can it settle a shift that leaves the count unchanged, such as one artifact created and one expired between two reads; GitHub's own retention, 90 days by default and a repository setting to read at dispatch, deletes an artifact missed that way at most 60 days after the 30-day line.
- **Found during execution:** read on 2026-10-05 with `gh api`, GitHub held 1,613 artifacts on 17 pages, listed by id, newest first, strictly. An id and its `created_at` disagreed by up to 4,534 seconds (76 minutes). Compared by instant, as this row was first written, the order check failed at 9 of the 16 page boundaries, so the walk would have read every page and kept its mark on about half of all wakes. Compared by UTC day, each page sorted by `created_at`, all 16 held, with no day out of order. The second follow-up is settled for today's size: every one of the 17 pages counted 1,613, and together they held 1,613 distinct artifacts, so the artifacts list's count was exact. Above 2,500 it cannot be read yet. A third of today's artifacts are kept 90 days, so with `dry_run` on the list may pass 2,500 within weeks (an estimate), and decision 10 checks the end of the list at every wake instead. Run on today's main, the new tests fail 24 of 87: main reads every page front to back, hands on the newest artifact first, deletes the newest in the window first, and keeps no mark on any artifacts pass. `RecordedApi`, which row 20's oracle names, went with this row: it answered every request with one page, which no walk from the last page can read. Its refused delete is `RecordedAnswers(fails_at=...)` now.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Combine a read from the oldest end (P2) with a stored mark (P3). The mark is a day, never a page number, because pages shift as artifacts expire | The owner, 2026-10-04 |
| 2 | The order is checked on every page, so an undocumented order lowers the cost and never decides what is deleted | Plan author, 2026-10-04 |
| 3 | The mark moves only while every page's `total_count` equals the first page's, less this pass's deletes, because a shifted page can carry an artifact onto a page already read | Fowler review, 2026-10-04 |
| 4 | The order is checked by UTC day, each page sorted by `created_at` first, because the mark, the line and `take` all count days, and the instant check failed at 9 of 16 real boundaries | Fowler, 2026-10-05 (row 11 worker's consult) |
| 5 | A listing that may have missed a member says so through `Collection.listing_intact`, and `take`'s one record builder keeps the mark at every exit, a failed one included | Fowler, 2026-10-05 (row 11 worker's consult) |
| 6 | With no mark in reach, the first walk starts after the day before the repository was created, or at the line when that is earlier. `first_mark` became `first_runs_mark` beside `first_artifacts_mark`, with the read of the repository's day shared, in a structural commit first | Fowler, 2026-10-05 (row 11 worker's consult) |
| 7 | A count that differs keeps the mark, and the walk goes on to its line: a missed artifact costs completeness, never safety | Fowler, 2026-10-05 (row 11 worker's consult) |
| 8 | After the order breaks, the walk reads every remaining page, each once and still from the last back, with no stop at the line, so a live delete moves only artifacts already read (row 10, decision 6) | Fowler, 2026-10-05 (row 11 worker's consult) |
| 9 | Page p-1 is read and checked before any artifact of page p reaches `take`, so a pass that ends inside a page never ends past an unchecked boundary | Fowler, 2026-10-05 (row 11 worker's consult) |
| 10 | The list must end where the first page's count says: the last page holds what is left of it, and a full last page has an empty page after it. Otherwise the count is not trusted, the mark stays, and the walk goes on. One more request on a wake whose last page is full; a re-measure past 2,500 would prove the count only at that size, and only once someone noticed | Fowler, 2026-10-05 (row 11 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Read every page, as today (P1) | 14 pages every wake, about 7 seconds (an estimate) | Nothing to build | The owner, 2026-10-04 |
| 2 | Reach artifacts through each old run | One request for every run, including runs with no artifact, about 175 a day | A request per run | Plan author, 2026-10-04 |
| 3 | Check the order by instant, as this row was first written | Failed at 9 of 16 real page boundaries on 2026-10-05: the walk would read every page and keep its mark on about half of all wakes | Nothing to build; a mark that rarely moves | Fowler, 2026-10-05 (row 11 worker's consult) |
| 4 | Walk and check by id, GitHub's own order | 19 artifacts came after one from a later day, each in the half hour before a midnight, so `take` would hold the mark there; and a stop at the line could leave a later-made, lower-day artifact unread | Nothing to build | Fowler, 2026-10-05 (row 11 worker's consult) |
| 5 | The task replaces `handled_through` on the returned pass | Splits the rule that holds a mark over two modules, and misses the record a failed pass raises with | Nothing to build | Fowler, 2026-10-05 (row 11 worker's consult) |

### Row #12 - Which months may close

- **Scope:** A new module chooses the months the absorb step takes (Table B, B5). Completeness counts from the ledger's first day. A missing day is re-packed from raw files, adopted when its packed file is there (Rule R, section 2.2), or recorded lost (Table C, C2), and a month with no row becomes an entry with no file. `FileListing.files_under` and `paths_under` refuse a folder no step named, as `holds`, `size_of` and `fetch` do since row 3. The other steps keep the shared window until their own rows. Level 3; it writes the shapes row 8 declared.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py` (new; first sentence "Which periods each compaction step may take on this wake"; the month rule only)
  - `backend/idhazh/contracts/gardener_events.py` (new; `PeriodsChosen` only)
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/file_listing.py` (`name`, with an injected lister; `files_under` and `paths_under` refuse a folder no step named)
  - `backend/idhazh/gardener/ledger_marks.py` (Rule R)
  - `backend/idhazh/gardener/named_trees.py` (it calls `files_under` on whole folders)
  - `backend/utilities/gardener_publish.py` (passes a lister over `git ls-tree` for the checked-out commit)
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (new)
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py`
  - `backend/tests/gardener/test_sparse_shard.py`
  - `backend/tests/gardener/test_download_ceiling.py`
  - `backend/tests/gardener/test_file_listing.py`
  - `backend/tests/gardener/test_ledger_marks.py`
  - `backend/tests/gardener/test_named_trees.py`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/architecture/publishing/idhazh-gardener.md` (its sentence that a folder a task neither owns nor reads "is refused rather than answered empty" gains the named-path rule)
  - `backend/idhazh/contracts/gardener_fault.py` (new; the recovery-note words, persisted from row 20; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/context.py` (`operator_range`, so the month step tells a person's range from the scheduled window; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/schedule.py` (`newest_eligible_month`; found during execution)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`name_months`; found during execution)
  - `backend/idhazh/ledger/persist.py`, `backend/idhazh/ledger/parquet.py` and `backend/idhazh/ledger/__init__.py` (`read_footer`, Rule R's rows and envelope from the footer; found during execution)
  - `tests/fixtures/gardener/task_packages/fixture_day_files.py` (it walked a whole folder; found during execution)
  - `backend/tests/gardener/tasks/test_compaction_batch.py` (`absorb` takes its choice; found during execution)
- **Acceptance gates:** local: pytest on the test files above; ruff; mypy; `doc_load.py` on both pages. CI: the full suite.
- **Oracle:**
  - Unit: the daily spans of the seven ledgers that failed on 2026-10-04, written into the test as literals, with today 2026-10-04: no chosen month is older than the oldest indexed month, and no pass ends `failed`.
  - Integration in `tmp_path`, built with the helpers in `backend/tests/gardener/tasks/_task.py`: a ledger indexed from 2026-09-12 to 2026-10-01 with no monthly entry and `daily_keep_days` 45 closes 2026-09 on 2026-11-15 and not on 2026-11-14, counting from 2026-09-12. With 2026-09-20 missing and its raw files present, the day is re-packed. With no raw files, the day is in `lost_days`, and the month entry is `packed` or `empty`, never `lost`. With 2026-09-25's entry removed and its packed file kept, the day is adopted as `packed` with the note `index-rebuilt`, not recorded `lost`. A month with no row gets an `empty` entry and no file.
  - Unit: `files_under` on a folder no step named is refused by name, as `holds` is.
  - It cannot settle the real ledgers. The first scheduled run after the merge is read: the seven tasks that failed on 2026-10-04 must not end `failed`. If one does, the owner reopens this row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each step chooses its own periods, and the month step goes first | Fowler, 2026-10-04 |
| 2 | Completeness starts at the ledger's first day (decision N2); nothing is filled in before it | The owner, 2026-10-04 |
| 3 | A missing day is re-packed or recorded lost, and the pass never stops for it | The owner, 2026-10-04 (recovery theme) |
| 4 | `PeriodsChosen` is both the steps' parameter object and a log event; it is not persisted | Fowler, 2026-10-04 |
| 5 | The task names the paths it chose at run time through `FileListing.name`, so the step rules live in one place | Fowler, 2026-10-04 |
| 6 | Rule R (section 2.2): before a period is recorded `empty` or `lost`, its own packed file at its named path is adopted, so a file on disk is never recorded lost | Fowler review, 2026-10-04 |
| 7 | `files_under` and `paths_under` refuse a folder no step named. An empty or partial answer there is the same silent read row 3 closed for three other methods | Plan author, 2026-10-04 (found during execution) |

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
  - `backend/tests/ledger_migration/test_packing_parity.py` (its parity case expects a file for every day from the 1st of the month, the days with no row packed as zero-row files)
  - `docs/architecture/publishing/ledger-compaction.md`
  - `backend/idhazh/contracts/gardener_events.py` (`PeriodsChosen` gains `newest_eligible_day`, `keep_line`, `days` and `rerun_span`; `StartReason` gains `oldest-raw-day` and `keep-line`; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`name_days`, `name_raw_months` and one naming helper they share with `name_months`; `note_recovery`, moved from `_monthly_period`; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/_monthly_period.py` (calls `note_recovery`; found during execution)
  - `backend/idhazh/ledger/ledger_files.py` (a docstring said a quiet day is a zero-row file; found during execution)
  - `backend/tests/gardener/tasks/_task.py` (`wake`: the listing a scheduled wake builds; found during execution)
  - `backend/tests/gardener/tasks/test_telemetry_aggregate_task.py` (the knobs it spreads into `run_task` are typed, now that `run_task` also takes `wake`; found during execution)
  - `backend/tests/ledger_migration/test_full_chain.py` and `backend/tests/test_canary_packing.py` (each pinned the fill from the 1st; found during execution)
  - `backend/tests/ledger_migration/test_packing_scope.py` (named months that leave out the day after the mark are now refused at that day; found during execution)
  - `backend/tests/ledger/_every_tier.py` (its first pass looks back four months; found during execution)
  - `docs/concepts/config/idhazh-gardener.md` (`lookback` for a compaction; found during execution)
- **Acceptance gates:** local: pytest on the test files above; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:**
  - Unit: a mark of 2026-09-16, cap 8, `compact_after_days` 1 and today 2026-10-04 give new days 2026-09-17 to 2026-09-24, resuming at 2026-09-25.
  - Integration: raw days 2026-09-17 to 2026-10-02 reach 2026-10-02 in two passes. An empty ledger, using the committed declaration `config/gardener/compact-gardener.json` with `dry_run` set false in the test, writes nothing and ends `empty` (corrected 2026-10-05: this line first named `tests/fixtures/gardener/runner/compact-gardener.json`, which owns only `state/compact/gardener`, so a real pass is refused before it reads a raw day; Fowler, 2026-10-04). A day with no row writes no file and an `empty` entry. A first run that starts mid-month writes no entry before the first raw day. The case in `test_compaction.py` that pins a fill from the 1st is turned around to pin that no fill happens, and so is the parity case in `test_packing_parity.py`.
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
- **Follow-ups:**
  - The year step accepts the `empty` month entries that the month step writes since row 12 (#1303); found during execution (row 12 report), owner 2026-10-04.
  - `_yearly_period._pack` refuses an `empty` month, and `_finish` an `empty` year, as `file-missing`. Both accept every entry state in Table D, D1 instead; found during execution (row 30 report), owner 2026-10-04.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `docs/architecture/publishing/ledger-compaction.md` (and a `## Design rationale` entry for decision 3)
  - `backend/idhazh/contracts/gardener_events.py` (`PeriodsChosen` gains `newest_packable_year` and `years`, both None when the declaration packs no year; `operator-range` also names a range that holds no whole year; found at dispatch by the owner, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`name_years`, beside `name_months` and `name_days`; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/schedule.py` (`newest_eligible_year`; `is_year_eligible` and `year_ended_at` deleted once nothing calls them; found during execution, Fowler's ruling)
  - `docs/how-to/execute-a-plan.md` and `docs/how-to/run-the-gates.md` (how to run a new test against the base commit without stashing, and the false pass a copy without `pyproject.toml` gives; found during execution, the user's instruction of 2026-10-05 that what a session learns goes to `docs/`)
- **Acceptance gates:** local: pytest on the two test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a monthly index from 2026-01 to 2027-01, a monthly mark of 2027-01, `daily_keep_days` 31 and `monthly_keep_days` 63 make 2026 ready on 2027-03-05 and not on 2027-03-04. 63 is the lowest value the contract accepts before row 24, `daily_keep_days` + 32, and the index holds 2027-01 because that month is also old enough to close on both dates. With the monthly mark at 2026-12, 2026 is not ready. A ledger that began in 2026-05 packs 2026 from May. It cannot settle a real year; the first one packs in 2027.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One readiness test, with a strict `>` past December in every branch | Fowler, 2026-10-04 |
| 2 | A ledger that began after January packs its first year from its first month | Fowler, 2026-10-04 |
| 3 | Each yearly index gains one entry a year, about 15 bytes after gzip. That growth is a named exception to Guardrail #12, and the bundle gate is its alarm: the gate refuses any file under `state/compact/<ledger>/index/` over 2,200 gzipped bytes, which the entries reach in about 140 to 160 years. That alarm covers only a published ledger: `compact-run-plan`, added on 2026-10-04, also packs years and is not published, so its yearly index has no alarm yet. A `## Design rationale` entry on the compaction page records the exception | Fowler review, 2026-10-04; owner to confirm |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A keep line for years | `published` and `summary-quality-evals` refuse deletion in `prune_refusal` | A knob, and deleting a whole year of rows from the ledgers that allow it | Plan author, 2026-10-04 |
| 2 | Pack years into decades | The index still grows, one level up | A fourth period kind across the contracts and the site | Plan author, 2026-10-04 |
| 3 | Keep only a first and a last year in the index | A Level 5 change to every index reader, to save about 60 bytes a year | The site's reader and the binding tests change | Plan author, 2026-10-04 |

### Row #15 - Each old month is dropped once

- **Scope:** The drop steps follow Table B, B1 and B2. The monthly index is the record of what is left to drop, and a raw day past the line is deleted by its listed path without being parsed. A month entry with no file is dropped without a missing-file warning. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/contracts/knobs/gardener.py` (the `max_periods_per_run` description now covers drops)
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `docs/architecture/publishing/ledger-compaction.md`
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a monthly index from 2025-01 to 2026-09, a keep line of 2025-10 and cap 8: B1 takes 2025-01 to 2025-08 and resumes at 2025-09. A live pass deletes those files and entries, and the next pass names no month older than the line. A report-only pass keeps them and reports them again. A raw day past the line whose file cannot be parsed is still deleted. An `empty` month entry past the line is dropped with no `FILE_MISSING` warning, and a `packed` entry whose file is absent still warns. It cannot settle the first live drop on a real ledger; `compact-gardener`'s first drop is due around November 2027.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The monthly index is the record of what is left to drop: a dropped month leaves the index and is never looked at again (decision L1) | The owner, 2026-10-04 |
| 2 | A drop deletes by listed path and parses nothing, so an unreadable file past the line cannot stop it (Table C, C7) | Plan author, 2026-10-04 |
| 3 | `_monthly_period.drop` warns `FILE_MISSING` only for a `packed` entry whose file is absent. An `empty` entry has no file to miss | Fowler review, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A separate cleaned-through file (decision L2) | A second record that can disagree with the index | A new contract | The owner, 2026-10-04 |
| 2 | Keep looking at the three months just past the line (decision L3) | A month that slides past those three is never dropped | Nothing to build | The owner, 2026-10-04 |

### Row #16 - The shared window is gone

- **Scope:** `scheduled_range` returns nothing for compaction, `paths_for_task` names only the marks, and the code that served the shared window is deleted. Level 2.
- **Follow-ups:**
  - For compaction, `TaskContext.period_range` and `operator_range` become one range. Row 12 added `operator_range` beside the scheduled `period_range`, and once `scheduled_range` returns nothing for compaction the two hold the same range; found during execution (row 12 report), owner 2026-10-04.
- **Files touched:**
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/context.py` (`TaskContext.period_range` and `operator_range`; found during execution (row 12 report), owner 2026-10-04)
  - `backend/utilities/ledger_migration/packing.py` (`pack` passes `months` to `compaction.run`)
  - `backend/idhazh/contracts/knobs/gardener.py` (the `lookback` description)
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py`
  - `backend/tests/ledger_migration/test_packing_scope.py` (its cases that pack only named months)
- **Acceptance gates:** local: pytest on the four test files and the gardener tests the selector lists; ruff; mypy. CI: the full suite.
- **Oracle:** this row removes code, and the property that could break is what each task names: `test_period_inputs.py` requires exactly the marks for every compaction task. The cases in `test_packing_scope.py` that pack only named months still pass, with the months passed as the operator range. It cannot settle anything the earlier rows did not already test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The `months` parameter leaves `compaction.run` and `CompactTree.read`; the migrator passes its first and last month as the operator range | Fowler, 2026-10-04 |
| 2 | The unused stamp in `_ledger_paths` is deleted (defect W7). `packing_paths` in `backend/utilities/ledger_migration/packing_files.py` stays: defect W6 named it `_packing_paths`, its name before #1265, and the migrator still calls it | Fowler, 2026-10-04; W6 withdrawn by the plan author, 2026-10-04, from #1281 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the window as a fallback | A second implementation that nothing should use | It stays and drifts | Fowler, 2026-10-04 |

### Row #17 - A late file re-opens its month

- **Scope:** A raw file that lands in a month already closed re-opens that month (Table C, C3). The month's rows and the late rows are settled by the ledger's record key, the month file and its entry are rewritten, and the late raw files are deleted. Level 3.
- **Follow-ups:**
  - The day step's refusal "raw files sit in a month already absorbed" compares a raw day's month with the monthly mark alone, so it also catches a raw day in a month before the ledger's first packed month, which no month entry names and which never closed. A first run that looks back `lookback` months (B7) can leave such a day behind. It is not a late re-run, so re-opening never treats its month as closed; found during execution (row 13 report), owner 2026-10-05.
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

- **Scope:** Table C, rows C4, C5, C6, C8 and C13. A file that cannot be read, or is too large, goes to `state/raw/<ledger>/set-aside/` and is counted on its entry. A packed file that its index names and the tree lacks is treated as unreadable, with nothing to move. A day with more raw files than the cap packs the first files and leaves the rest for the next wake. A step chooses periods only while their listed sizes fit the shard's budget. Level 3; it writes the `set_aside` field row 8 declared.
- **Follow-ups:**
  - Rule R's downloads (`ledger_marks.adopt`, row 12) count against the shard's download budget, as the periods a step chooses do (Table C, C8); found during execution (row 12 report), owner 2026-10-04.
  - The day step's re-take of a packed day builds a fresh `CompactEntry`, which drops the day's `set_aside`. The re-take keeps it; found during execution (row 30 report), owner 2026-10-04.
  - A set-aside file goes to `state/raw/<ledger>/set-aside/` (Table C, C5), the folder the console names to a person since row 31 (#1301); found during execution (row 31 report), owner 2026-10-04.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py` (`over_the_ceiling` becomes a check that a correct choice never trips; tripping it is a code defect)
  - `backend/idhazh/gardener/ledger_marks.py` (`adopt`; found during execution (row 12 report), owner 2026-10-04)
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/gardener/test_download_ceiling.py`
  - `backend/tests/gardener/test_ledger_marks.py` (found during execution (row 12 report), owner 2026-10-04)
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/reference/repository-layout.md` (the set-aside folder)
- **Acceptance gates:** local: pytest on the test files above; ruff; mypy; `doc_load.py` on both pages. CI: the full suite.
- **Oracle:**
  - A day with one unreadable raw file packs its other files. The bad file is under `set-aside/` at its old path, and the entry says `set_aside: 1`.
  - A month whose index names a day file the tree lacks closes with that day in `lost_days` and the note `recorded-lost`.
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

- **Scope:** Each mark is worked out from the three indexes (section 2.2), and an absent index is rebuilt from named paths by Rule L. The `Watermark` contract and every committed `state/compact/<ledger>/<period>/watermark.json` are deleted (Table D, D4), so a watermark without its index can no longer happen (Table C, C9), and `index-missing` can no longer stop a pass (C14). Level 5.
- **Follow-ups:**
  - Delete the first-run case in `_compaction_periods._days` that starts at the oldest day a daily index names when no daily mark is beside it (Table B, B7). Once the daily mark is worked out from the indexes, an index that names a day always gives a mark, so the case can no longer happen; found during execution (row 13 report, Fowler 2026-10-04), owner 2026-10-05.
- **Files touched** (from a search for `watermark` in any case, `daily_through`, `monthly_through` and `yearly_through`, 2026-10-04, after #1267 merged; search again at dispatch, `TODO/` and `state/compact/` included. The benchmark record of what a compaction pass costs describes the pass it measured, and it stays as it is, as do the matches that mean another thing, such as a stream's `highWaterMark`):
  - `.gitattributes` (its `-merge` line for `state/compact/*/*/watermark.json`)
  - `config/idhazh_gardener.json` (`first_ledger_year`, Table D, D5)
  - `backend/idhazh/contracts/knobs/gardener.py` (`GardenerConfig.first_ledger_year`)
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/ledger/paths.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/day_removal.py` (its docstring names the watermark)
  - `backend/idhazh/gardener/ledger_marks.py` (Rule L)
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/gardener/tasks/_compaction_periods.py` (the first-run case that starts at the oldest indexed day; found during execution (row 13 report), owner 2026-10-05)
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/named_trees.py`
  - `backend/idhazh/telemetry/door_prune.py`
  - `backend/utilities/ledger_migration/packing_files.py` (its docstring names a watermark; it names the marks through `ledger_marks.name_marks` since #1281)
  - `backend/utilities/benchmark_compaction.py` (it times `write_watermark`)
  - `frontend/scripts/published-ledgers.mjs` (its comment on keeping `daily/watermark.json` off the site)
  - `backend/tests/contracts/test_ledger_index.py`
  - `backend/tests/contracts/test_gardener_config.py` (`first_ledger_year`)
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/gardener/test_named_trees.py`
  - `backend/tests/gardener/test_file_listing.py`
  - `backend/tests/gardener/test_ledger_marks.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_batch.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (the same case's unit test; found during execution (row 13 report), owner 2026-10-05)
  - `backend/tests/gardener/tasks/test_compaction_years.py`
  - `backend/tests/ledger/test_ledger_files.py`
  - `backend/tests/ledger/test_trial_roots.py`
  - `backend/tests/ledger_migration/test_packing_parity.py` (its watermark reads)
  - `backend/tests/ledger_migration/test_packing_scope.py` (its watermark writes and checks)
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/test_canary_packing.py`
  - `frontend/tests/ledger-copy.spec.ts`
  - `frontend/tests/published-ledgers.spec.ts`
  - `tests/fixtures/contracts/watermark/` (deleted)
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `docs/architecture/publishing/idhazh-gardener.md` (its wake diagram still draws one `watermark.json` per period)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (it says the watermark stays off the site)
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `docs/concepts/config/idhazh-gardener.md` (`first_ledger_year`)
  - `TODO/20260930-57-upkeep-tasks-switch-on-plan.md` (its row "The eval ledger is packed live, and every scores window stays forever" reads its oracle from a watermark file)
  - `TODO/20261004-pipeline-tests-migration-plan.md` (its lines C2, C13 and I2, and its row "Readers understand nested trial roots", name the watermark builders, paths and files)
  - every committed `state/compact/<ledger>/<period>/watermark.json`
- **Acceptance gates:** local: pytest on the test files above that the selector lists, `-m contract` included, and the specs it lists; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** for the committed indexes of every compaction ledger, read once at dispatch and written into the test as literals, the marks worked out from the indexes equal the `through` of each committed watermark file. A ledger with an index and no watermark resumes where its index ends. Integration under `tmp_path`, built with the helpers in `backend/tests/gardener/tasks/_task.py`: with `index/daily.json` removed and the day files kept, the pass rebuilds the index from named paths, notes `index-rebuilt` and deletes nothing. It cannot settle a watermark that was already wrong; this oracle would show it as a mismatch, and that mismatch is reported, not forced to agree.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Design the fault out instead of recovering from it: the indexes already say what each watermark says, once every empty period has an entry (rows 12 to 14) | The owner, 2026-10-04 (recovery theme); shape by plan author |
| 2 | Reader before writer: steps read marks from the indexes, then the files and the contract go, in this one row, because nothing outside the gardener reads a watermark (the site works out `through` from `daily.json`) | Plan author, 2026-10-04 |
| 3 | Rules R and L (section 2.2): an absent index is rebuilt from named paths, so `index-missing` can no longer stop a pass and the watermarks can go. Every read stays bounded: at most 31 named paths a month, and the yearly part grows by one a year (row 14, decision 3). A ledger whose daily mark stalled for longer than B7's look-back keeps older day files out of a rebuilt index (Table A, A8) | Fowler review, 2026-10-04 (ESCALATE trigger 6) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the watermarks, and rebuild a missing index from the files the marks name | Two records that can disagree, plus a repair path for that | A bounded rebuild per ledger | Plan author, 2026-10-04 |
| 2 | Keep failing with `index-missing` | Manual work | Nothing to build | The owner, 2026-10-04 (recovery theme) |

### Row #20 - The record says what was recovered and why a pass stopped

- **Scope:** Each task's record row carries its `recovered` notes and, only for a pass that stopped, one closed `fault` word (Table D, D3). One pure function maps an error to its result, so a code defect is always `raised`, and a member GitHub will not delete is recorded and passed (Table C, C15). The sentence a person reads is rendered from them when the row is read and is never stored. `deferred` ends a pass without turning the job red. Level 5, approved by the owner on 2026-10-04 (decision S2 and the recovery theme).
- **Follow-ups:**
  - The operator-range refusal that row 12 added ends the task `failed` today. It is not a code defect, so it gets a fault word of its own in Table D, D3 and does not turn the job red; found during execution (row 12 report), owner 2026-10-04.
  - The day step writes the note `repacked-from-raw` when it packs a day inside history that had no entry (Table C, C2). Row 12 wired only `index-rebuilt` and `recorded-lost`; found during execution (row 12 report), owner 2026-10-04.
  - The outcome `outside-range` follows Table F, F8, whose meaning row 12 narrowed: a range that a ready period before it blocks is the refusal above, never `outside-range`; found during execution (row 12 report), owner 2026-10-04.
- **Files touched:**
  - `backend/idhazh/contracts/collection_prune.py`
  - `backend/idhazh/contracts/gardener_fault.py` (new; first sentence "Why a gardener pass stopped, and what it recovered instead of stopping")
  - `backend/idhazh/contracts/gardener_events.py` (`StepChoice` records the operator-range refusal as `failed`; found during execution (row 12 report), owner 2026-10-04)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Stop` and `Pass` gain `fault` and `recovered`; `PruneInterruptedError` carries the classified cause)
  - `backend/idhazh/gardener/closed_day_fold.py` (`FoldInterruptedError` carries the classified cause)
  - `backend/idhazh/gardener/report.py`
  - `backend/idhazh/gardener/runner.py` (each task's fault comes from the classifier; only `failed` sets the shard's failed exit code)
  - `backend/idhazh/gardener/github_collections.py` (the error classifier)
  - `backend/idhazh/telemetry/door_prune.py` (it also raises `PruneInterruptedError`)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/_compaction_periods.py` (the operator-range refusal; found during execution (row 12 report), owner 2026-10-04)
  - `backend/tests/contracts/test_collection_prune_row.py`
  - `tests/fixtures/contracts/collection-prune-row/` (new: a `deferred` row with a fault, and a `done` row with recovered notes, one of them `not-deletable` with a member id)
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (found during execution (row 12 report), owner 2026-10-04)
  - `docs/architecture/publishing/idhazh-gardener.md` (the record)
  - `docs/architecture/publishing/ledger-compaction.md` (the recovery notes)
- **How it works:** one pure function in `github_collections.py` maps an error to a result. It tests `HTTPError` first, because `HTTPError` is a kind of `URLError`, which is a kind of `OSError`.
  - 404 or 410: the member is already gone, and counts as deleted.
  - 409 or 422: the member is recorded `not-deletable` with its id (Table C, C15). It counts against the delete ceiling, and the pass goes on.
  - 429, any 5xx, `URLError`, `TimeoutError` or `ConnectionError`: fault `api-unavailable`, outcome `deferred` (C11). The mark stays, and the next wake retries.
  - Any other 4xx, or any other exception: fault `raised`, outcome `failed` (C12). It is a code or permission defect, and the job turns red.
  - `PruneInterruptedError` and `FoldInterruptedError` carry the classified cause, and never relabel a code defect.
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_collection_prune_row.py`, and pytest on the other test files above; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** the new fixtures round-trip. A `fault` beside `stopped_because: exhausted` is refused. `ceiling-reached.json`, which has no `fault`, still reads. Each recovery in Table C writes its note, and each stop writes its fault. The classifier maps each case above, built from real `HTTPError` and `URLError` objects. With `RecordedApi` answering 503, the outcome is `deferred`, the mark does not move, and the shard's other tasks run. With member 2 of 3 answering 422, members 1 and 3 are deleted, and the record holds one `not-deletable` note naming member 2. A shard whose only non-green task is `deferred` exits 0. It cannot settle wording; the sentence is rendered and can change with no migration. Nor can it settle what GitHub answers for a member it will not delete (decision 6).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A closed word plus the existing `resume_from`; the sentence is rendered when read (decision S2) | The owner, 2026-10-04 |
| 2 | What was recovered is a note, not a fault, so a recovered pass is `done` | The owner, 2026-10-04 (recovery theme) |
| 3 | Exception text is never stored, because it can carry fetched row text (Guardrail #11) | Fowler, 2026-10-04 |
| 4 | No fault word for an interruption. A killed process lands nothing (Table C, C10), and both wrappers caught every exception, so a code defect would have been recorded as an interruption, ended `deferred` and left the job green | Fowler review, 2026-10-04 |
| 5 | A member GitHub will not delete is recorded `not-deletable` with its id, and the mark may pass it. Before, one refused member stopped every later pass, so nothing behind it was ever deleted | Fowler review, 2026-10-04 |
| 6 | 409 and 422 mean a member GitHub will not delete. That is a reading of GitHub's documentation, not a measurement: when a pass first meets such an answer, its response is recorded as a test fixture | Fowler review, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A stored free-text reason (decision S1) | Fetched text could reach the record, and no reader can act on prose | A sanitizer and a length cap | Fowler, 2026-10-04 |
| 2 | Every stop red, as today | A recoverable stop asks a person for work | Nothing to build | The owner, 2026-10-04 |
| 3 | Retry inside one wake with a retry library | The next wake already retries, and nothing yet says how often GitHub's API is unavailable | A dependency and its tests; priced by how often `deferred` appears on the record | Fowler review, 2026-10-04 |
| 4 | Keep the fault word `interrupted` for a wrapped exception | A code defect would read as an interruption, end `deferred` and leave the job green | Nothing to build; a defect nobody sees | Fowler review, 2026-10-04 |

### Row #21 - Every gardener log line is one JSON event

- **Scope:** The events of Table E become models, `event_log.py` writes each one as one JSON line (section 2.5), and the free-text log lines of the gardener are deleted. Level 3.
- **Files touched:**
  - `backend/idhazh/contracts/gardener_events.py`
  - `backend/idhazh/gardener/event_log.py` (new; first sentence "How a gardener event becomes one log line")
  - `backend/idhazh/gardener/report.py` (`classify`)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Pass.idle_outcome`; WindowChosen in `take`; the message of `PruneInterruptedError`)
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
- **Oracle:** unit: each event renders as one line of valid ASCII JSON with `event` first, `None` left out and nested models kept nested. Integration in `tmp_path`: one ledger for each outcome word in Table F. TaskPlanned comes before TaskFinished, and each carries its fields; tests read the payload on the record, not the text. A dry run whose listing fails part way never logs that anything is gone: today `one_at_a_time.PruneInterruptedError` says "Those are gone" for a dry run too, and `runner._run_one` logs it. It cannot settle how readable JSON is in GitHub's log viewer; row 22's summary is the view for a person.

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
- **Follow-ups:**
  - A first run looks back `lookback` months (default 2) before the month that holds the newest eligible day (Table B, B7). The gardener ledger's oldest raw day was 2026-09-30 on 2026-10-05, and from the wake of 2026-12-03 it falls outside that look-back, so a first live pass from then on would leave its older raw days raw. Before switching on, check the oldest raw day against the look-back and, when it falls outside, raise `lookback` in the same change so the first live pass reaches it. `compact-visual-prunes` (oldest raw day 2026-09-06, outside from 2026-12-03) and `compact-run-plan` (2026-10-04, outside from 2027-01-03) have never packed either and need the same check when they switch on; found during execution (row 13 report), owner 2026-10-05.
  - Since #1309 a first run starts at its oldest raw day and writes no zero-row file, so the cost named in rejected option 1 below no longer holds; Fowler's order for readable first-pass logs still does; found during execution (row 13 report), owner 2026-10-05.
- **Files touched:**
  - `config/gardener/compact-gardener.json`
  - `backend/tests/contracts/test_gardener_config.py` (both of its switches in `LIVE_BY_DECISION`, with the owner's decision as the reason)
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/architecture/publishing/ledger-compaction.md` (its intro counts six compaction tasks, two packing live and one packing years. On 2026-10-04 `config/gardener/` held 12, 7 with `dry_run: false` and 4 that set `monthly_keep_days`; count again at dispatch)
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

- **Scope:** `daily_keep_days` becomes 16 in every compaction declaration, and its floor becomes 1. `seen` and `counterfactual-scores` keep a 3-month window so their readers keep 90 days. A late re-run file is handled by row 17. `docs/concepts/config/idhazh-gardener.md` gains a `compact-run-plan` row (#1284) in its table of compactions that ship, and names that task in its sentence on the month-delete switch; found during execution (row 7 report), owner 2026-10-04. Level 4: months closed at 16 days are not re-opened by going back.
- **Files touched:**
  - every `config/gardener/compact-*.json` that `task_names` in `config/idhazh_gardener.json` names, read at dispatch (12 on 2026-10-04)
  - `backend/idhazh/contracts/knobs/gardener.py` (the `GITHUB_RERUN_DAYS` comment, the `daily_keep_days` floor and its description)
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_page_ceilings.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py` (module docstring)
  - `backend/idhazh/ledger/ledger_files.py` (module docstring: a late raw file re-opens its month)
  - `docs/concepts/config/idhazh-gardener.md` (the `compact-item-health` and `compact-host-fingerprint` rows that keep day files for 31 to 62 days, the `daily_keep_days` row that says at least 31, and the refusal row for `daily_keep_days` below 31. Its table of compactions that ship gains a `compact-run-plan` row, and its sentence on the month-delete switch names `compact-run-plan`; found during execution (row 7 report), owner 2026-10-04)
  - `docs/architecture/publishing/ledger-compaction.md` (each sentence that states the 31-day rule: the intro's 31-day wait for the two ledgers packed live, the re-run section, the floor of 31 in the day and year rules, the entry of 2026-09-28 and the entry on the two live ledgers. A `## Design rationale` entry replaces the one of 2026-09-28: what a late re-run costs now)
  - `TODO/20261004-pipeline-tests-migration-plan.md` (its line C9 calls `daily_keep_days` 31 the least `CompactionPolicy` accepts)
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_gardener_config.py backend/tests/contracts/test_page_ceilings.py`, and pytest on `test_compaction.py`; `doc_load.py`. CI: the full suite.
- **Oracle:** every compaction declares 16; a 0-day keep is refused; the config check `refuse_what_the_declarations_break` in `backend/idhazh/config.py` still refuses a reach below a reader's need and passes for `seen` and `counterfactual-scores`, whose reach is at least 16 + 89 = 105 days against the 90 their readers need. `monthly_keep_days` must stay at least `daily_keep_days` + 32 = 48 days, and every declaration that sets it uses 93. A published daily index holds at most `daily_keep_days` + 31 entries, so it shrinks from at most 76 to at most 47, and the page-weight checks only get easier. It cannot settle how often a re-run lands late; 2 of 214 digest runs were re-run, at 4 and 13 hours.

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

- **Collapsed:** the listings and their code were removed by #1267, so the row has nothing left to do, and step B3 of Table B went with them (owner decision N1, 2026-10-04).
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

### Row #26 - doc_load.py reads a web address as a web address

- **Scope:** When `doc_load.py` looks for links to pages that are not there, it skips a target that starts with a scheme such as `https:`. A link to a document on another site is then no longer reported as a missing page. Level 1. Found while running row 1 on 2026-10-04: the compaction page links to Delta Lake's `PROTOCOL.md` on GitHub, and the tool reported it as missing.
- **Files touched:**
  - `backend/utilities/doc_load.py`
  - `backend/tests/test_doc_load.py`
- **Acceptance gates:** local: `python -m pytest -n 0 backend/tests/test_doc_load.py`; ruff; mypy; `python backend/utilities/doc_load.py docs/architecture/publishing/ledger-compaction.md` no longer reports the Delta Lake link. CI: the full suite.
- **Oracle:** a page body that holds `](https://example.org/a/PROTOCOL.md)` and `](missing.md)` reports only `missing.md`; today it reports both. It cannot settle whether a remote page exists, because the tool never reads the network (CLAUDE.md section 13).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A target with a scheme is outside the repository, so the tool does not judge it | The owner, 2026-10-04 (on row 1's report) |
| 2 | Only the missing-page checks skip such a target; the check that a "See also" section holds a link keeps counting it | Plan author, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Remove the link | The only source for the Delta Lake claim goes, to quiet a wrong report | One line | The owner, 2026-10-04 |
| 2 | Fix the tool inside row 1 | Row 1 is documentation only | Code gates on a documentation row | The owner, 2026-10-04 |

### Row #27 - A shard lands nothing stale, and says why when it cannot land

- **Scope:** The publisher decides how a shard's commit came to rest on main from facts it reads, never from push text: a shard whose paths main changed after the shard's own commit lands nothing, and a push that runs out of tries is `lost` when main kept moving and `refused` when it did not. Level 3.
- **Files touched** (from a search for `EXIT_PUSH_KEPT_LOSING`, `def stage` and `def publish`, 2026-10-04; search again at dispatch):
  - `backend/utilities/gardener_publish.py` (`Checkout.stage` and `publish`)
  - `backend/idhazh/gardener/outcome.py` (the exit codes)
  - `backend/idhazh/contracts/shard_landing.py` (new; first sentence "How one gardener shard's commit came to rest on main")
  - `backend/tests/gardener/test_publish.py`
  - `.github/workflows/idhazh-gardener.yml` (the comment on the exit codes)
  - `docs/architecture/publishing/idhazh-gardener.md` (the exit table)
- **How it works:**
  - After each fetch, `git diff-tree -r --no-renames --name-only HEAD origin/main -- <paths>` runs over the shard's written and deleted paths, its record left out, in batches. HEAD is the commit the shard ran on, so each path it lists is one that main changed after that commit, and the shard's version of it is stale. The shard then lands nothing, its record included, logs a `::warning` that names the first such paths, and exits 0. The next wake does the work again on the new main. The command compares trees only, so the `blob:none` clone downloads no file.
  - A failed push is tried again as today. After the last try, the publisher reads main's tip once more. When the tip moved since the last base, other writers are landing: `lost`, a `::warning`, exit 0. When it did not move, main refused this push: `refused`, exit 3, red. Exit 3 is renamed from "the push kept losing" to "the push was refused".
  - The landing words `landed`, `already-on-main`, `stale`, `lost` and `refused` live in `backend/idhazh/contracts/shard_landing.py`. They are not persisted, because a record cannot describe its own landing. Row 22's `ShardPublished` imports them (Table E, E6).
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/test_publish.py backend/tests/workflows/test_gardener_workflow.py`; ruff; mypy; `npm --prefix frontend run test:changed -- --list` selects no frontend check; `python backend/utilities/doc_load.py docs/architecture/publishing/idhazh-gardener.md`. CI: the full suite.
- **Oracle:** the real bare-repository harness in `test_publish.py`.
  - Stale: a commit on main changes one of the shard's paths first. The shard lands nothing and exits 0.
  - Refused: a pre-receive hook exits 1 and leaves main where it was. Exit 3.
  - Lost: on every try a pre-receive hook moves main to a prepared commit and exits 1. Exit 0. The hook unsets `GIT_QUARANTINE_PATH`, `GIT_OBJECT_DIRECTORY` and `GIT_ALTERNATE_OBJECT_DIRECTORIES`, then runs `git update-ref refs/heads/main <sha>`, with one `refs/race/<n>` a try, picked by a counter file. This hook was checked on Git for Windows in a temp folder on 2026-10-04.
  - It cannot settle what GitHub answers for a protected branch. The rule reads how the tip moved, so it does not need to.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `lost` or `refused` is decided by whether main's tip moved after the last try, never by push text. A GitHub outage across every try gives one false red | Fowler review, 2026-10-04 |
| 2 | A stale shard lands nothing, not even its record; the next wake does the work again on the new main | Fowler review, 2026-10-04 |
| 3 | The landing words are a contract module and are not persisted | Fowler review, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Land stale files anyway, as today | `publish` checks only whether the shard's record is on main, and `Checkout.stage` lays the shard's paths over main's tree. A re-run checks out its run's first commit, so it lands old indexes over newer ones, and its record has a new file id, so that check does not catch it. The next wake then reads a ledger that forgot work | Nothing; it is the defect | Fowler review, 2026-10-04 |
| 2 | Refuse a re-run of a run from an earlier day | It misses a stale re-run on the same day, and refuses a good one whose paths nobody touched | One date comparison | Fowler review, 2026-10-04 |
| 3 | Run the tasks again inside the push loop | It repeats minutes of work and the download budget on every lost try | A loop around the runner | Fowler review, 2026-10-04 |
| 4 | Read the push's error text | Git's text is not a contract: it changes with versions and languages, and a misread is silent | One regular expression | Fowler review, 2026-10-04 |

### Row #28 - The console can read the gardener ledger

- **Scope:** The `gardener` ledger is published through the existing query door, so the console can show why a ledger is behind and what a pass recovered. Level 3.
- **Precondition:** at dispatch, `state/compact/gardener/index/daily.json` is on `origin/main`, which first happens at the first live wake after row 23. Before that the build stops: a published ledger with no index stops the copy in `frontend/scripts/published-ledgers.mjs`, and a ceiling key that matches no file fails the bundle gate in `frontend/scripts/bundle-gate.mjs`.
- **Files touched:**
  - `config/idhazh.json` (`gardener` in `ledger.published`, and the key `"state/compact/gardener/index/": 2200` in `page_weight.payload_ceilings_bytes`)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (the list of published ledgers)
  - `docs/architecture/publishing/idhazh-gardener.md`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_page_ceilings.py`; `npm --prefix frontend run test:changed -- --list` and the checks it selects; `npm run bundle-gate` from `frontend/`; the browser smoke in [run-the-gates.md](../docs/how-to/run-the-gates.md) on one console page (CLAUDE.md section 12); `doc_load.py` on the two pages. CI: the full suite.
- **Oracle:** `test_every_published_ledger_bounds_its_indexes_at_twice_their_longest` in `backend/tests/contracts/test_page_ceilings.py` fails on a half revert: the ledger published without its key, or the key without the ledger. No new test: this is one config value, and its readers are tested for every published ledger. It cannot settle whether the console shows the notes; that panel is out of scope (Table A, A6).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Publish the existing ledger through the existing door; no new payload | Fowler review, 2026-10-04 |
| 2 | Dispatch waits until the gardener's indexes are on main | Fowler review, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A separate console payload | A second copy of the record, with a second writer | A new contract, a writer and its tests | Fowler review, 2026-10-04 |
| 2 | Leave the gardener ledger unpublished | The console cannot show why a ledger is behind; the recovery notes reach only the shard summary | Nothing | Fowler review, 2026-10-04 |

### Row #29 - doc_load.py measures every named Markdown page

- **Scope:** `doc_load.py` prints a row for any named Markdown file inside the repository, not only for `docs/` and the three root pages, and AGENTS.md step 3 stops saying that the tool prints the bootstrap load. The required-elements check, `faults`, stays limited to `docs/`, which it already filters to itself. Level 1.
- **Files touched:**
  - `backend/utilities/doc_load.py` (`pages_under`)
  - `backend/tests/test_doc_load.py`
  - `AGENTS.md` (step 3)
  - `docs/reference/documentation-structure.md` (widened by the owner, 2026-10-04)
  - `frontend/scripts/test-scope.ts` (widened by the owner, 2026-10-04)
  - `frontend/scripts/tests/test-scope.test.mjs` (widened by the owner, 2026-10-04)
  - `docs/reference/test-selection.md` (the page that owns the selector's mappings, changed with the owner's widening)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/test_doc_load.py`; ruff; mypy; `python backend/utilities/doc_load.py TODO/20261004-60-gardener-recovers-on-its-own-plan.md` prints one row. CI: the full suite.
- **Oracle:** a test builds a page under `tmp_path/TODO/` and expects one row from `measure` and no fault from `faults`. It fails if the `docs/`-only filter comes back. The existing test that a deleted page is skipped still holds. It cannot settle whether `top h2` means anything for a plan, whose rows sit in one section by design.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measure any named Markdown file inside the repository; hold only `docs/` to the required elements | Fowler review, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Print one line naming each skipped path | A plan still gets no row, and AGENTS.md step 3 asks for one row for each named page | A few lines | Fowler review, 2026-10-04 |
| 2 | Leave it | Every plan check prints nothing, and AGENTS.md keeps a wrong sentence | Nothing | Fowler review, 2026-10-04 |

### Row #30 - Every reader and rewriter of a compact index keeps an entry's state

- **Scope:** Two code paths outside the compaction misread the fields row 8 added to `CompactEntry` (Table D, D1); found by row 8, owner 2026-10-04. `check_compact_period` in `backend/idhazh/ledger/stored_output.py`, which the ledger migration's readback runs, refused an `empty` or `lost` entry as having 0 files where it expected one. It now passes such an entry while no file is at its path, and refuses a file there. The named prune in `backend/idhazh/telemetry/door_prune.py` rebuilt a pruned file's entry from what it covers, its rows and its bytes alone, so a prune dropped `state`, `lost_days` and `set_aside` and erased the record of a gap. It now changes only `rows` and `bytes`. A search of `backend/` outside the tests for every `CompactEntry(` and every read of a compact index's entries found no other reader or rewriter outside the compaction that loses a field or looks for a file an entry does not name. Reader before writer: this row lands before row 12 writes these shapes. Level 2.
- **Files touched:**
  - `backend/idhazh/ledger/stored_output.py` (`check_compact_period`)
  - `backend/idhazh/telemetry/door_prune.py` (`_changes`)
  - `backend/tests/ledger/test_stored_output.py`
  - `backend/tests/retention/test_prune_range.py`
  - `docs/architecture/contracts/persistence.md`
  - `backend/utilities/ledger_migration/readback.py` (read, no change: it reads the check's answer, and a recorded period with no file is not missing output)
  - `backend/idhazh/ledger/day_removal.py` (read, no change: it names a file only for an entry that counts a row, and an entry with no file counts none)
  - `backend/idhazh/ledger/ledger_files.py` (read, no change: row 8 taught it `names_file`)
  - `backend/idhazh/gardener/ledger_marks.py` and `backend/idhazh/gardener/tasks/_compact_tree.py` (read, no change: each carries every entry whole)
  - `backend/idhazh/gardener/tasks/_daily_period.py`, `_monthly_period.py` and `_yearly_period.py` (read, no change: decision 3)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/ledger/test_stored_output.py backend/tests/retention/test_prune_range.py backend/tests/ledger_migration/test_readback.py`; ruff; mypy; `npm --prefix frontend run test:changed -- --list` and the checks it selects; `python backend/utilities/doc_load.py docs/architecture/contracts/persistence.md`. CI: the full suite.
- **Oracle:**
  - Contract: `check_compact_period` over row 8's samples `an-empty-day`, `a-lost-day` and `a-month-with-lost-days`. The entry with no file passes while no file is at its path, and a real compact file there is refused. On the base tree all three fail with "0 files, expected one". Deleting the branch that reads `names_file` makes the test fail again, and deleting only the refusal makes its second half fail with "DID NOT RAISE".
  - Contract: the named prune over `a-month-with-lost-days`, its packed month built from census rows filed through the door. Taking one day rebuilds the month file, and the month's entry keeps its two lost days and its one set-aside file, with the new row count and size. The empty month beside it is carried as it was. On the base tree the rebuilt entry has no lost day and nothing set aside. Building the entry from `CompactEntry(covers=..., rows=..., bytes=...)` again makes the test fail.
  - It cannot settle what a compaction step does with an entry that has no file. That is the writer rows' work (decision 3).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An entry with no file passes the check while no file is at its path, and a file at its path is refused | The owner, 2026-10-04 (row 30 brief) |
| 2 | A rewrite copies the entry and changes only `rows` and `bytes`, so a field added to `CompactEntry` later is carried too | The owner, 2026-10-04 (row 30 brief) |
| 3 | The compaction steps are not changed here: they write these shapes, and rows 12 to 18 change them. Each place a step opens a period's file meets an entry with no file once a writer row lands, and that row handles it. `_daily_period._take` refuses a re-run on an `empty` or `lost` day as `file-missing` (rows 12 and 13), and a re-take builds a fresh entry that drops `set_aside` (row 18). `_monthly_period.absorb` and `_finish` refuse an `empty` or `lost` day and an `empty` month as `file-missing` (rows 12 and 13). `_yearly_period._pack` and `_finish` refuse an `empty` month and an `empty` year the same way (row 14). Row 15 decision 3 already covers `_monthly_period.drop` | The owner, 2026-10-04 (row 30 brief) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Count an entry with no file as absent in the check | The readback would call a period the index records "migrated output is missing", where a zero-row file counted as present before | Nothing to build | Row 30 worker, 2026-10-04 |
| 2 | Name the three new fields in the prune's rewrite | A field added to `CompactEntry` later would be dropped again, and no test would say so | One line a field | Row 30 worker, 2026-10-04 |
| 3 | Teach the compaction steps `names_file` in this row | Some of those reads cannot change apart from a write. A month that closes over a lost day has to list it in `lost_days`, or the close erases the record, and row 12 writes `lost_days` | Edits in three step modules that rows 12 to 18 rewrite | The owner, 2026-10-04 (row 30 brief) |

### Row #31 - Panels say which days have no record

- **Scope:** The console says which days have no record and how many files were set aside, wherever it shows a ledger's coverage. Every console route names, in a plain record note, each day its records' indexes record lost and each file their packing set aside, with the folder `state/raw/<ledger>/set-aside/`. A recording note dates an instrument's start by a lost day, never after it (Hardware and Summaries). The data explorer names each selected ledger's lost days and set-aside files under its span line, in an answer with rows and in a quiet one. The explorer's address reads a day such as `2026-08-32` with the door's `isDay()`, so the link shows its notice instead of throwing. Level 2: frontend only; `set_aside` was already declared (Table D, D1). Found by row 8's browser smoke, owner 2026-10-04.
- **Files touched:**
  - `frontend/src/lib/data/compact-index.ts` (the guard checks `set_aside` and hands it on)
  - `frontend/src/lib/data/slice.ts` (`filesFor` returns `setAside`)
  - `frontend/src/lib/data/slice-shapes.ts` (`SetAsideFiles`; `SliceResult` carries `setAside`; `SpanGap`; `AskResult` carries `gaps`)
  - `frontend/src/lib/data/slice-reader.ts`
  - `frontend/src/lib/data/ask-reader.ts`
  - `frontend/src/lib/data/ledger.ts` (re-exports the two new types)
  - `frontend/src/lib/server/ledger-rows.ts` (`newestRows` carries lost days and set-aside files)
  - `frontend/src/lib/console/recording.ts` (`noRecordSentence`, `setAsideSentence`, record notes `lost` and `set-aside`, `daysWithNoRecord`)
  - `frontend/src/lib/console/RecordNotes.svelte` (comment only)
  - `frontend/src/lib/console/explorer/gaps.ts` (new)
  - `frontend/src/lib/console/explorer/address.ts`
  - `frontend/src/routes/console/data-explorer/+page.svelte`
  - `frontend/src/routes/console/machine/+page.server.ts`
  - `frontend/src/routes/console/model/+page.server.ts` (found during execution: the Summaries note dated its start the same way)
  - `frontend/src/routes/console/+page.server.ts` and `frontend/src/routes/console/voices/+page.server.ts` (comment only: what their record notes say)
  - `frontend/scripts/test-groups.ts`
  - `frontend/tests/ledger-door.spec.ts`
  - `frontend/tests/ledger-rows.spec.ts`
  - `frontend/tests/console-chrome.spec.ts`
  - `frontend/tests/console-data-explorer.spec.ts`
  - `frontend/tests/console-data-explorer-address.spec.ts`
  - `frontend/tests/console-data-explorer-gaps.spec.ts` (new)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md`
  - `docs/architecture/publishing/console-payloads.md`
  - `docs/how-to/query-a-ledger-from-the-console.md`
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list` and the checks it selects; `npm --prefix frontend run check`; the browser smoke in [run-the-gates.md](../docs/how-to/run-the-gates.md) on the Hardware page and the explorer, built from the canary state with a lost and an empty day, including a missing and an empty index (CLAUDE.md section 12); `doc_load.py` on the changed pages. CI: the full suite.
- **Oracle:** each case fails on the main this row started from. The disk read of a tree with an `empty` day, a `lost` day and set-aside files names them (`ledger-rows.spec.ts`), and the Hardware oracle in that file prints the lost day as a plain record note and never dates the start after it. `console-chrome.spec.ts` dates the start by a lost day and by a destroyed one. `ledger-door.spec.ts` reads row 8's contract samples under `tests/fixtures/contracts/compact-index/` and counts their set-aside files by period, refuses a `set_aside` that is not a count, and names each ledger's gaps in a written answer. In the browser, `console-data-explorer.spec.ts` serves item-health's index with a lost day and two set-aside files and reads both lines under the answer, then the quiet answer for the lost day alone; and a link with `from=2026-08-32` shows the span notice and loads the ledgers. It cannot settle what the gardener writes: no committed index holds a lost day or a set-aside file until rows 12 and 18 land.
- **Found during execution:** the explorer's date chart draws the days either side of a lost day next to each other, because its axis holds only days with rows (`dateSeries.ts`); a lost day the answer has no row for could sit on the axis with no value, so the line breaks there (Jony, 2026-10-04: a separate change). The explorer page's `validStoredDay` still accepts a stored `2026-08-32`, which reads as a span of no days rather than a notice. Row 18 must move a set-aside file to `state/raw/<ledger>/set-aside/`, the folder the console names (Table C, C5).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The explorer says it once, under its span line, in the answer with rows and in the quiet one; one plain paragraph a ledger and a state, lost days first; nothing under the chart | Jony, 2026-10-04 |
| 2 | A set-aside line counts files and says "when this data was packed", never "these days", because a month counts every file it set aside; it never ends on the folder | Jony, 2026-10-04 |
| 3 | A console route names a lost day and set-aside files as plain record notes, one a record and a state, beside "packed as far as" | `RecordNotes.svelte`'s rule, one sentence a record and a state; Jony raised no objection, 2026-10-04 |
| 4 | An instrument ran on a day its record lost, so that day dates its start. A day the record destroyed takes the same rule, and the start is no longer dated the day after it | Row 8, decision 3; worker, 2026-10-04 |
| 5 | Set-aside files are counted over the periods a read takes, keyed by period, so two reads that meet one month count its files once | Worker, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A note under the explorer's chart only | A reader of the table and a quiet answer, which draws no chart, would not see it | The same lines in the chart panel | Jony, 2026-10-04 |
| 2 | The note in both explorer panels | One fact said twice on one screen | A second render of the same lines | Jony, 2026-10-04 |
| 3 | Name lost days only in the Hardware route's windowed recording notes | The article and score records would stay silent on every other route, and one lost machine-record day would need a sentence from each of the route's two instruments | A field and a sentence for each instrument | Worker, 2026-10-04 |
| 4 | A whole-ledger set-aside total from the reach | It would count files no panel on the route reads, and a day's count and its month's count could both be summed | One sum over the indexes the reach already reads | Worker, 2026-10-04 |

### Row #32 - The explorer's date chart breaks its line at a lost day

- **Scope:** The data explorer's date chart draws its line straight across a day whose record was lost, as if that day held data, because its axis holds only the days the answer has rows for. It breaks the line at a lost day instead, by the rule the console's date charts already follow: a quiet day is a zero, and a day with no record is no value (`frontend/src/lib/charts/d3/dateSeries.ts`). The explorer page's `validStoredDay` refuses a stored day that is not on the calendar, such as `2026-08-32`, which it accepts today. Level 3.
- **Files touched** (from a search under `frontend/src` for the explorer's chart, `dateSeries` and `validStoredDay`, 2026-10-04; the other callers of `dateSeries` draw other panels and are not touched; search again at dispatch):
  - `frontend/src/lib/console/explorer/ShapePanel.svelte` (the date chart; it builds each series from the answer's rows alone, so a lost day never reaches the axis)
  - `frontend/src/lib/console/explorer/shape.ts` (`dateSeriesShape`)
  - `frontend/src/routes/console/data-explorer/+page.svelte` (`validStoredDay`; the page holds the answer's `gaps` and hands `ShapePanel` only the rows)
  - `frontend/src/lib/charts/d3/dateSeries.ts` (read, no change: it breaks a line at a day on its axis that has no value)
  - `frontend/src/lib/data/slice-shapes.ts` (read, no change: `isDay()`, which the explorer's address reads a day with since row 31)
  - `frontend/tests/console-data-explorer.spec.ts` (the lost-day answer, the chart cases and the questions kept in browser storage)
  - `frontend/tests/console-data-explorer-shape.spec.ts`
- **Acceptance gates:** local: the two specs above, as `npm --prefix frontend run test:changed -- --list` selects them; `npm --prefix frontend run check` (svelte-check); the browser smoke in [run-the-gates.md](../docs/how-to/run-the-gates.md) on the data explorer, with a count by day across a lost day (CLAUDE.md section 12). CI: the full suite.
- **Oracle:** in the browser, a count by day across a lost day draws its line in two segments, not one, and a saved question or recent run stored with the day `2026-08-32` is refused when the page reads browser storage. Each case fails on today's main. It cannot settle how the gap looks; Jony and Susan rule on that only if two layouts lead to different code.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Break the line at a lost day, in a change separate from row 31 | Jony, through row 31's report, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Draw the lost day as zero | It would show a lost day as a quiet day | Nothing to build | The owner, 2026-10-04 (row 8, decision 3) |
