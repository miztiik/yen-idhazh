# Plan 60 - The gardener chooses its own work and recovers on its own

**Last Updated**: 2026-10-08

**Level**: 5 (CLAUDE.md section 6). Rows 8, 10, 19 and 20 change persisted contracts (section 2.4). The owner approved each shape on 2026-10-04.

**Status**: written 2026-10-04 by the session owner from Fowler's design of the same day and the owner's rulings on it. Fowler's review of that design was applied on 2026-10-04, under ESCALATE trigger 6 and owner decision M1. It corrected the rows not yet dispatched, added rows 27 to 29, and changed shapes D1 and D3 after the owner had approved them. #1267 removed the retired raw listings and their code, so step B3 and row 25 are gone (owner decision N1, 2026-10-04).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | On 2026-10-04 seven of the eleven compaction tasks failed and none packed a new day. Since #1240, every compaction step reads one window that was built for the step that deletes old months, so the packing steps look in the wrong months. The run of 2026-10-03, before #1240, packed normally. The owner asked that each step choose its own periods, that no empty file is written, and that a fault is recovered and recorded so the pass moves on |
| Hard scope - in | - Each compaction step chooses its own periods (section 2.1).<br>- An empty day, month or year is an index entry with no file, and nothing is filled in before a ledger's first day (section 2.1, Table D row D1).<br>- Every fault in Table C is designed out or recovered, and the record says which (sections 2.3 and 2.4).<br>- Months close 16 days after they end on every compaction ledger; a late re-run file re-opens its month; `seen` and `counterfactual-scores` keep 3 months.<br>- Each old month is dropped once, and the monthly index is the record of what is left to drop.<br>- workflow-runs and workflow-artifacts read only what is past their line, starting from a mark on their own record.<br>- One run id per workflow run, and job names that list each shard's tasks.<br>- Every gardener log line is one JSON event, each shard writes a summary, and a dry run never says that anything is gone.<br>- `compact-gardener` packs live, and `monthly_window_dry_run` is renamed `month_deletes_dry_run`.<br>- A shard whose paths main changed after its commit lands nothing, and a push that runs out of tries says whether main kept moving (row 27).<br>- The gardener ledger is published, so the console can read it (row 28) |
| Hard scope - out | Table A below |
| ESCALATE triggers | 1. A persisted shape that section 2.4 does not declare.<br>2. A row that would delete a row of `published`, `seen` or `summary-quality-evals` other than by the approved yearly expiry, or by settling a re-opened month by its record key (Table C, C3). The owner approved on 2026-10-07 that every ledger's yearly files expire 36 calendar months after the year's UTC end, the first on 2030-01-01 UTC (#1382). That approval replaced the rules that kept `published` and `summary-quality-evals` for ever. The `prune_refusal` of all three still refuses a prune of days that a person names (`idhazh telemetry prune`).<br>3. Fetched text in a log line, a record field, a file path or a URL (Guardrail #11).<br>4. A shard that would run past the 6 h job, or a row whose cost is over 3x its estimate.<br>5. The `dry_run` of workflow-runs or workflow-artifacts moving to `false` (Table A, A1).<br>6. Fowler's answer to the design brief of 2026-10-04 changes a decision in this plan. For a row not yet dispatched, the owner edits the row first. For a row already merged, STOP-AND-SURFACE ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)).<br>7. Two personas still disagree after one debate |
| Waiting on the owner | Four decisions: A, B and C sent 2026-10-07, and D sent 2026-10-08. A and B point to row 20's Found during execution, C to row 24 and #1382, and D to row 37's Found during execution.<br>A. Whether a 403 that carries `x-ratelimit-remaining: 0` or `retry-after` reads `api-unavailable` instead of `raised`, changing the approved 403 mapping. Recommended: yes, one small new row (Fowler). Rejected so far: keep the approved mapping. No row until the owner rules.<br>B. What word records the eight refusals that a person, not a code change, must settle; today they end `raised`/`failed` with no word of their own in Table D, D3 (ESCALATE trigger 1). Row 20's Found during execution names seven. The eighth is the refusal of a missing yearly index (Table C, C14), which #1382 added: with `yearly_prune_enable` on and the ledger's compact folder present, the task ends `failed`/`raised` until a person restores the index. Since row 21 (#1387), a refused period's sentence, such as a year file's size, is no longer logged: its `period-refused` line keeps the step, the period, the fault words, the error type and the code place, and B's word would say why (row 21 report). Recommended, B2: a new word paired with `failed`, so the run still turns red and the record says why. Other options: keep `raised`; a new word paired with `deferred`, so the run stays green. Row 22's Reader asked for a `::warning` on the run page for a deferred task that waits for a person; Fowler rejected it as beyond row 22, and the summary's heading names every deferred task instead. Option B2 would turn those cases red (row 22 report). No row until the owner rules<br>C. Row 24, "Months close 16 days after they end" (owner, 2026-10-04, not built), conflicts with #1382, under which daily files pack 45 days after their month ends (owner, 2026-10-07, merged and live). The plan owner sent it to the owner as a section 0c decision request. Recommended, C1: the later approval stands at 45 days. Row 24 collapses, and its parts that do not depend on 16 days move to a small row: the wording of `month_deletes_dry_run` in `docs/concepts/config/idhazh-gardener.md` and in `backend/idhazh/contracts/knobs/gardener.py`, and the entry "The two ledgers packed live wait 31 days, not 45" in `docs/architecture/publishing/ledger-compaction.md`. The other option, C2: row 24 runs as written and sets 16 on every declaration. Found while recording C: since #1382, `seen` and `counterfactual-scores` pack years, and a ledger that packs years needs a forever monthly window, so row 24's 3-month window for them (its decision 2) applies under neither option. No row until the owner rules<br>D. Whether every other `idhazh` command's crash output drops the error's text, as the gardener's does. `idhazh work` handles fetched text, and a validation error quotes its input (Fowler; not measured), while every local crash would lose its message. Options sent: a new row of this plan that first tests whether `idhazh work` can print fetched text on a crash, and only if it can, makes every command print only where it broke (recommended); every command now; as today. Nothing waits on D |
| Chosen strategy | Each step reads the ledger's own indexes and chooses its own periods. A fault the gardener can record is recorded on the period, and the pass moves on. Only a code defect turns a run red. The owner ruled on 2026-10-04, on Fowler's design of the same day |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 12 to 20 share the compaction step modules, so they run one at a time. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table A - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| A1 | Switching workflow-runs and workflow-artifacts to live deletes | Old runs and artifacts stay, as today. GitHub keeps a run's logs and artifacts for 90 days, this repository's setting and the most a public repository allows (read 2026-10-05). So the runs task, whose window is also 90 days, would delete only runs whose logs are already gone: a live pass shortens the Actions history and frees no log. A dry run deletes nothing, so the artifacts walk reads again from the last page to its line on every wake. The dry list may pass 2,500 artifacts within weeks (an estimate, row 11's report, 2026-10-05). The end-of-list check that row 11 added logs a count that stops short | An owner decision. First size `max_deletes_per_run` from a 7-day arrival count: `gh api "repos/miztiik/yen-idhazh/actions/runs?created=>=<today-7>&per_page=1" --jq .total_count`. On 2026-10-04 that read 1,226 runs, about 175 a day, and the declared ceiling is 50 deletes a wake. A day held between 32 and 401 runs from 2026-08-22 to 2026-10-04, and a live pass that its ceiling stops inside a day reads that day again at the next wake (row 10), so a ceiling below a busy day's count takes several wakes to pass it. A count from a search by date stops at 2,500, so a span longer than about two weeks is counted a day at a time |
| A2 | A keep line for years, built by a row of this plan | Nothing: #1382 built it outside this plan, on the owner's approval of 2026-10-07. Every ledger's yearly files expire 36 calendar months after the year's UTC end, so 2026 expires on 2030-01-01 UTC; each compaction declaration sets this with `yearly_keep_months` and `yearly_prune_enable`. The approval replaced the rules that kept `published` and `summary-quality-evals` for ever, and their `prune_refusal` refuses only a prune of days that a person names | Already in, through #1382. A change to the approved expiry is the owner's (ESCALATE trigger 2) |
| A3 | Keying the rules in `backend/idhazh/gardener/period_inputs.py` on a declaration's kind instead of task names | One list of task names stays written in code (Guardrail #6). Since #1330 the name checks left in `period_inputs.py` are `trials` and `visual-prune` in `paths_for_task` (row 16 report), and `digest-fragments` with `visual-prune` in `_day_window` | A Level 2 row after row 16 |
| A4 | Event logging in `backend/idhazh/cli.py` and `backend/idhazh/telemetry/cli.py` | Those two commands keep free-text logs (CLAUDE.md section 1b) | A Level 2 row each after row 21, reusing `event_log` |
| A5 | Listing switched-off declarations in the plan job | A paused task does not appear in the run log | A request for it |
| A6 | A console panel for the recovery notes | The notes reach the record and the shard summary (row 22), but not the console | Row 28 publishes the gardener ledger; then Jony and Susan rule on the panel |
| A7 | Backend folds telling a lost day from a quiet day | A count over a lost day reads as zero activity, not as unknown | `LedgerFiles` in `backend/idhazh/ledger/ledger_files.py` carries the gaps to each fold: a Level 3 row |
| A8 | Rule L looking further back than its named places (section 2.2) | A ledger whose daily mark stalled for longer than B7's look-back keeps its older day files out of a rebuilt index | Starting a daily rebuild with no monthly mark at January of `first_ledger_year`. Rule L names one folder a year (row 19, decision 7), so that adds one folder a year, inside decision 3's bound, and needs no exception: a Level 2 row |
| A9 | The gardener's other tasks choosing by the download budget | `telemetry_aggregate`, `closed_day_fold` and `collection_mark` still fetch through `FileListing.fetch`, so two fetch paths stay: `fetch`, and the compaction's `fetch_within_budget` | A row after row 18 that makes those three choose by the budget, then makes `fetch` itself refuse past the budget and deletes `fetch_within_budget` (Fowler, row 18 report) |

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
| 11 | workflow-artifacts reads from the oldest end and resumes from its mark | 10 | C | DONE | psychic-potato | #1317 | Plan 60 row 11 |
| 12 | Which months may close | 3, 5, 7, 8, 27, 30 | D | DONE | fuzzy-dollop | #1303 | Plan 60 row 12: which months may close |
| 13 | Which days may be packed | 12 | D | DONE | silver-enigma | #1309 | Plan 60 row 13: which days may be packed |
| 14 | Which years may be packed | 13 | D | DONE | scaling-train | #1316 | Plan 60 row 14 |
| 15 | Each old month is dropped once | 14 | D | DONE | redesigned-spoon | #1322 | Plan 60 row 15 |
| 16 | The shared window is gone | 15 | D | DONE | jubilant-waffle | #1330 | Plan 60 row 16 |
| 17 | A late file re-opens its month | 16 | D | DONE | curly-fiesta | #1331 | Plan 60 row 17 |
| 18 | An unreadable file is set aside, and extra files wait | 17 | D | DONE | special-succotash | #1335 | Plan 60 row 18 |
| 19 | The marks are worked out from the indexes, and the watermark files go | 8, 18 | D | DONE | legendary-fortnight | #1339 | Plan 60 row 19 |
| 20 | The record says what was recovered and why a pass stopped | 4, 11, 19 | E | DONE | shiny-system | #1373 | Plan 60 row 20 |
| 21 | Every gardener log line is one JSON event | 2, 20 | E | DONE | reimagined-winner | #1387 | Plan 60 row 21 |
| 22 | A person reads a shard at a glance | 21 | E | DONE | didactic-spork | #1395 | Plan 60 row 22 |
| 23 | The gardener ledger is packed live | 16, 22 | F | DONE | supreme-tribble | #1402 | Plan 60 row 23 |
| 24 | Months close 16 days after they end | 7, 17, 23 | F | PENDING | - | - | - |
| 25 | The retired raw listings code goes | 15 | F | COLLAPSED #1267 | - | - | - |
| 26 | doc_load.py reads a web address as a web address | - | A | DONE | stunning-garbanzo | #1285 | Plan 60 row 26: doc_load web links |
| 27 | A shard lands nothing stale, and says why when it cannot land | 3, 9 | C | DONE | urban-spoon | #1291 | Plan 60 row 27: no stale landing |
| 28 | The console can read the gardener ledger | 23 | F | DONE | solid-goggles | #1419 | Plan 60 row 28 |
| 29 | doc_load.py measures every named Markdown page | 26 | A | DONE | effective-carnival | #1289 | Plan 60 row 29: doc_load every page |
| 30 | Every reader and rewriter of a compact index keeps an entry's state | 8 | D | DONE | psychic-guide | #1293 | Plan 60 row 30: index readers keep state |
| 31 | Panels say which days have no record | 8 | E | DONE | congenial-waddle | #1301 | Plan 60 row 31: panels show lost days |
| 32 | The explorer's date chart breaks its line at a lost day | 31 | E | DONE | symmetrical-parakeet | #1318 | Plan 60 row 32 |
| 33 | A log line never quotes a ledger row's values | 21 | E | DONE | fictional-telegram | #1393 | Plan 60 row 33 |
| 34 | A gardener crash prints where it broke, never the error's text | 22 | E | DONE | upgraded-meme | #1404 | Plan 60 row 34 |
| 35 | The yearly expiry logs an event of its own | 21 | G | DONE | super-fiesta | #1417 | Plan 60 row 35 |
| 36 | The plan job's config refusals keep their sentence | 34 | G | DONE | turbo-guide | #1411 | Plan 60 row 36 |
| 37 | Operator gardener commands print where they broke, never the error's text | 34 | H | DONE | cuddly-carnival | #1426 | Plan 60 row 37 |
| 38 | An expired year reaches the job summary | 35 | H | DONE | silver-train | #1434 | Plan 60 row 38 |
| 39 | The job summary says plainly when nothing is left and what a dry run holds back | 38 | I | DONE | fuzzy-barnacle | #1440 | Plan 60 row 39 |

## 2. Shared declarations

Rows point here. Each name, shape and rule is declared once.

### 2.1 How each step chooses its periods

Every line is computed from `today`, the wake's UTC day, and from each period's own end (CLAUDE.md section 2). An operator range (`--from` and `--to` on one named task, or the migrator's range) limits every step. The "newest eligible day" is the newest day at least `compact_after_days` whole days past its end, and the "newest eligible month" in B7 is the month that holds it (Fowler, 2026-10-04). The cap is the declaration's `max_periods_per_run`.

Table B - each step

| # | Step | Starts at | Takes | Adds to the listing |
| --- | --- | --- | --- | --- |
| B0 | Expire years, only with `yearly_prune_enable` and `yearly_keep_months` | The oldest yearly entry | Yearly entries whose year has expired by the wake's UTC day, oldest first, up to the cap. A year expires `yearly_keep_months` calendar months after 00:00 UTC on the January after it, so at 36 months 2026 expires on 2030-01-01. An `empty` entry expires too. The step reads the yearly index alone and opens no file. Live: delete each of the year's files that the listing holds, remove the entry, and set the yearly index's `expired_through` to the year (Table D, D6). A dry run reports the same paths and deletes nothing. An operator range takes only whole years, and a range that would skip an older indexed year stops the step `deferred`, with the fault `range-starts-late`, at the oldest indexed year: an operator-range refusal is not a code defect, so it does not turn the job red (the owner's ruling of 2026-10-04, row 20's follow-up; row 35). The owner approved the step on 2026-10-07 (#1382) | Each chosen year's file at its path in both formats of `Format`, `parquet` and `json`. Neither is fetched: the step deletes by name |
| B1 | Drop month files | The oldest monthly entry | Entries older than the keep line, oldest first, up to the cap. Live: delete the month file when the entry has one, delete its raw month folder, then remove the entry. Report-only: keep both and report them | Each month file and its `state/raw/<ledger>/YYYY/MM` folder |
| B2 | Drop raw days | - | Raw day folders older than the keep line, inside the months B1 names or a first run looked back over (Fowler, row 15 report). They are deleted by listed path and never parsed | Nothing more |
| B4 | Pack years, only with `monthly_keep_days` | The year after the yearly mark; with none, the year of the oldest monthly entry | Consecutive years whose age line has passed and whose December the monthly mark is strictly past, up to the cap. A ledger that began after January packs its first year from its first month. A year with no row is an entry `empty` with no file. Its months' `lost_days` carry into the year entry | That year's month files, named from the monthly index |
| B5 | Absorb months | The month after the monthly mark; with none, the oldest month the daily index names; with an empty daily index, nothing | Consecutive months at least `daily_keep_days` past their end that the daily mark has passed, up to the cap. A month with a raw day still waiting is held for B6. Completeness counts days from the month's 1st, or from the ledger's first day when the ledger began inside that month. A missing day inside that span is recovered (Table C, C2). A month with no row is an entry `empty` with no file | Each month's daily files and its raw month folder |
| B6 | Pack days | The day after the daily mark | New days up to the earlier of the mark plus the cap and the newest eligible day. Also packed days inside the 30-day re-run span that hold new raw files; they count against the cap. A raw file in a closed month re-opens it (Table C, C3). A re-opened month counts once against the cap, and the step re-opens months before it takes any day (Fowler, row 17 report). A day with no row is an entry `empty` with no file | The raw folders and the packed day files of the new days and of the re-run span. Rule R and the re-take read the day files (Fowler, 2026-10-04) |
| B7 | First run: no daily mark | The oldest raw day in the raw month folders from the newest eligible month minus `lookback` months to the newest eligible month, or in the operator range. Never before the keep line when month deletes are live. A daily index with no mark beside it, which a pass cut before its mark landed leaves, starts it at the index's oldest day when that is older; row 19 deletes this case (Fowler, 2026-10-04) | As B6. An indexed day with no raw file keeps its entry, and the mark moves past it. With no raw day, nothing; the outcome is `empty` | Those raw month folders |

Every read has a fixed size (Guardrail #12). A pass names at most: the three indexes, plus the three watermarks until row 19; for each step, the cap times that step's periods; for the year expiry (B0), at most the cap's years, each named at one path for each format in `Format` (`backend/idhazh/contracts/file_envelope.py`: `parquet` and `json`, read 2026-10-07), so at most twice the cap, and none of them fetched; and, only when an index file is absent, the paths Rule L names (section 2.2). Each count comes from config or the calendar. Rule L names one folder a year for each index it rebuilds, so its count grows by at most one a year, and it names nothing for a ledger with no compact folder (row 19, decisions 7 and 12). Step B3, which dropped the retired raw listings, went with #1267 (row 25).

### 2.2 The marks

| # | Mark | Worked out as |
| --- | --- | --- |
| M1 | Daily mark | The newest of: the newest daily entry, the last day of the newest monthly entry, and the last day of the newest yearly entry |
| M2 | Monthly mark | The newest of: the newest monthly entry, and December of the newest yearly entry |
| M3 | Yearly mark | The newer of the newest yearly entry and the yearly index's `expired_through` (Table D, D6) |

A mark can be worked out this way only because every period a step has looked at leaves an entry, an empty one included (rows 12, 13 and 14). Until row 19 lands, the watermark files stay, and the steps read them.

An entry can be gone while its packed file is still there, for example after an index is restored from an older commit, and a whole index file can be gone. Two rules adopt such a file instead of recording a gap (Table C, C14). Each reads only named paths.

- **Rule R (row 12).** Before a pass records a period `empty` or `lost`, it looks for that period's own packed file at its named path (`FileListing.name`). If the file is there, the pass adopts it as `packed`: its bytes from the listing, and its rows from the Parquet footer, inside the download budget left. It adds the recovery note `index-rebuilt` for that period. The rule lives in `backend/idhazh/gardener/ledger_marks.py`, whose first sentence already covers which packed files exist.
- **Rule L (row 19).** When an index file is absent, the pass looks only at named places, coarsest period first, and adopts each file it finds as Rule R does. A place with no file writes nothing.
  - Yearly: each year from `first_ledger_year` (Table D, D5) to the newest year old enough to pack. Since #1382, a ledger with `yearly_prune_enable` whose compact folder exists refuses an absent yearly index by name instead, because no file can rebuild `expired_through`.
  - Monthly: the months of a finite window. For a window that keeps every month - a forever window, one whose deletes only report, or a dry run - each month from the January after the yearly mark (M3), or from January of `first_ledger_year` when there is none.
  - Daily: each day from the month after the monthly mark to the newest eligible day, or, with no monthly entry, from the first month step B7 starts from. Each index is searched in one folder a year.

### 2.3 Recovery instead of failure

A pass never stops for something it can record. Each fault below is designed out, or recovered on this wake or the next. Only `failed` turns a job red, and it means a code defect; a period that waits for a person ends `deferred` and says so in its fault word (row 20).

Table C - each fault

| # | What stopped the pass before | Now | Recorded as | Outcome | Row |
| --- | --- | --- | --- | --- | --- |
| C1 | A month chosen from before the ledger began (`day-missing`) | Designed out. B5 starts at the oldest indexed month, and completeness starts at the ledger's first day | - | - | 12 |
| C2 | A day inside history with no entry (a hole) | Re-packed from its raw files when any are left, or else adopted when its packed file is there (C14). Otherwise it gets an entry `lost`, and the day goes into its month's `lost_days` when the month closes | `repacked-from-raw` or `recorded-lost`, with the day | `done` | 12 |
| C3 | A raw file in a closed month (a late re-run) | The month re-opens. Its rows and the late rows are settled by the ledger's record key, the month file and its entry are rewritten, and the late raw files are deleted | `reopened-month`, with the month | `done` | 17 |
| C4 | More raw files in one day than `max_raw_files_per_period` | The first files by name are packed. The rest stay where they are, and B6's re-run span takes them on the next wake | `carried-over`, with the day | `ceiling` | 18 |
| C5 | A raw file that cannot be read | Moved to `state/raw/<ledger>/set-aside/`, under its path relative to `state/`, and counted in its entry's `set_aside`. The rest of the day packs. The size ceiling is the shard's download budget (C8), so no file is set aside for its size. A period larger than the whole budget fails by name, with its bytes and `max_downloaded_mb` (Fowler, row 18 report) | `set-aside`, with the day | `done` | 18 |
| C6 | A packed day or month file that cannot be read when its month or year closes | Moved to set-aside as in C5. Its days go into `lost_days`, and the period closes | `set-aside` and `recorded-lost` | `done` | 18 |
| C7 | A raw day past the keep line whose files cannot be parsed | Designed out. B2 deletes by listed path and parses nothing | - | - | 15 |
| C8 | The shard's download ceiling (`over_the_ceiling` in `runner.py`) | Designed out. A step chooses a period only while its listed size fits what is left of the shard's budget | - | `ceiling` | 18 |
| C9 | A watermark without its index (`index-missing`) | Designed out. Each mark is worked out from the indexes (section 2.2), and the watermark files go | - | - | 19 |
| C10 | The job is killed part way through a pass, by a timeout or a cancelled run | Designed out. A shard lands only through its one commit, so a killed pass lands nothing, and the next wake starts from the same marks | - | - | 20 |
| C11 | GitHub's API is unavailable to a collection pass: a 429 or 5xx answer, or a connection that fails or times out, as row 20's error classifier names them. Nothing inside a wake retries | The mark stays, and the next wake resumes from it | fault `api-unavailable` | `deferred` | 20 |
| C12 | An exception that no other row of this table names, including a 4xx answer other than 404, 409, 410, 422 and 429 (row 20) | The task stops at that period. The shard's other tasks still run, and the next wake retries | fault `raised`; the exception's type goes to the log line, and its text never to the record | `failed` | 20 |
| C13 | A packed day or month file that its index names and the tree lacks, when its month or year closes | Treated as unreadable (C6): its days go into `lost_days`, and the period closes. There is no file to set aside | `recorded-lost` | `done` | 18 |
| C14 | An index file that is absent while its period was packed (`index-missing`), or a packed file at its named path that no entry names, which would otherwise be recorded `lost` | Adopted from named paths: an absent index by Rule L, and a file that no entry names by Rule R (section 2.2). Nothing is deleted. Since #1382, Rule L refuses an absent yearly index instead when the ledger has `yearly_prune_enable` and its compact folder exists, and that task ends `failed` with `raised` until a person restores the index | `index-rebuilt`, with the period | `done` | 12, 19 |
| C15 | A member GitHub will not delete (collections: a 409 or 422 answer). Today the refused delete stops the pass, and every later pass meets that member first | Recorded with its id. It counts against the delete ceiling, the pass goes on, and the mark may pass it | `not-deletable`, with the member id | `done` | 20 |

`state/raw/<ledger>/set-aside/` is never named by any step, never copied to the site (only `state/compact/` is), and never deleted by the gardener. A person reads it when the console shows a non-zero `set_aside`.

### 2.4 Persisted shapes

Every persisted shape below, D1 to D4 and D6, follows CLAUDE.md section 11: a new `version`, one changelog line, at most five lines in the changelog, and a read-side default that reads every older payload. D5 is a config value, which section 11 does not cover (owner ruling, 2026-09-21).

Table D - contract changes

| # | Contract | Change | How older payloads read | Row |
| --- | --- | --- | --- | --- |
| D1 | `CompactEntry` in `CompactIndex`, `backend/idhazh/contracts/ledger_index.py` | `state`: `packed` (the default), `empty` or `lost`. `lost` is a daily state only: a monthly or yearly entry is `packed` or `empty` and lists its lost days in `lost_days`, so no reader handles a lost month or year. An `empty` or `lost` entry holds no file, and its `bytes` and `rows` are 0. `lost_days`: ascending UTC days inside a monthly or yearly entry's period that were recorded lost; empty by default; never on a daily entry. `set_aside`: how many files were moved aside while packing the period; default 0 | The defaults read every committed index as all `packed`, so nothing is rewritten. A zero-row file written before this row stays a valid `packed` entry until its month closes | 8 |
| D2 | `CollectionPruneRow` in `backend/idhazh/contracts/collection_prune.py` | `handled_through`: a UTC day. Every member created on or before that day was handled by a pass with the same `dry_run` value: deleted, recorded as not deletable, or reported. Null when the pass handled nothing | The null default reads every older row | 10 |
| D3 | `CollectionPruneRow`, and new `backend/idhazh/contracts/gardener_fault.py` | `fault`: `raised` or `api-unavailable`, allowed only beside `stopped_because` `failed` or `deferred`; row 20's follow-ups add `range-starts-late`, `no-month-to-reopen` and `packed-file-unreadable` (words by Fowler, 2026-10-07). `raised` pairs with `failed` and every other word with `deferred`, and a `deferred` row names one. `recovered`: a list of `{note, subject}`. `note` is `repacked-from-raw`, `recorded-lost`, `reopened-month`, `set-aside`, `carried-over`, `index-rebuilt` or `not-deletable`. `subject` is the period or the member id the note is about, typed as `MemberId` in `collection_prune.py`: `MEMBER_ID_PATTERN`, at most 512 characters, which every period string also matches. Each note names one period or member the pass took or adopted, so the list is bounded by the cap, the delete ceiling and Rule L's named paths (section 2.2). `stopped_because` gains `deferred` | Null and empty defaults read every older row | 20 |
| D4 | `Watermark` in `backend/idhazh/contracts/ledger_index.py` | Retired, together with every committed `state/compact/<ledger>/<period>/watermark.json` | Nothing reads them after row 19; section 2.2 replaces them | 19 |
| D5 | `GardenerConfig` in `backend/idhazh/contracts/knobs/gardener.py`, read from `config/idhazh_gardener.json` | `first_ledger_year`: the UTC year from which Rule L looks for yearly and monthly files (section 2.2). The value is 2026: the repository was created on 2026-08-20, so no ledger holds an earlier year | Not a persisted payload. The committed file gains the value in the same change | 19 |
| D6 | `CompactIndex` in `backend/idhazh/contracts/ledger_index.py` | `expired_through`: the newest UTC year whose file the yearly expiry deleted. Only a yearly index may set it, and no entry may cover that year or an earlier one. It is a stored boundary that keeps the expiry's progress after every yearly entry is removed: the yearly mark counts it (section 2.2, M3), so no rebuild adopts or packs an expired year again. A writer leaves it out until a year expires. The frontend copy in `frontend/src/lib/data/compact-index.ts` reads it with the same two refusals, and `COMPACT_INDEX_STAMP` moved with the version | An index with no `expired_through` reads it as null, so every older index reads unchanged | #1382 (owner approval, 2026-10-07) |

### 2.5 Events and outcome words

Each event is a `Model` in `backend/idhazh/contracts/gardener_events.py` (not persisted; section 11 does not apply), and `backend/idhazh/gardener/event_log.py` writes it as one line. The owner approved E1 to E6 on 2026-10-04. Fowler added E7 to E15 on 2026-10-07, one small model for each fact (row 21, decision 4), and E16 on the same day (row 35, decision 1). What each line tells a person is in [idhazh-gardener.md](../docs/architecture/publishing/idhazh-gardener.md#what-a-shard-logs).

Table E - events. Beside each model is the name its line carries, the model's name in kebab case. E4 is never a line of its own, and E6 is row 22's. After where an event is emitted comes its line's `level`.

| # | Event | Emitted by | Fields |
| --- | --- | --- | --- |
| E1 | TaskPlanned, `task-planned` | The runner, before the task; `info` | task, kind, shard, run_id, attempt, today, operator_range (the range a person named, never the scheduled window), declared: the declaration as it dumps, leaving out `kind`, `owns`, `reads`, `appends_to` and the prose of `prune_refusal`, with a null knob kept null; absent: the declared folders the commit does not hold yet |
| E2 | WindowChosen, `window-chosen` | `one_at_a_time.take`, at its top, before the listing is read, so a walk that fails at once has already said its window; `info` | collection, since, until, ceiling, dry_run, mark (the `handled_through` it starts from). The pages read are known only at the end, so the pass counts them and E5 reports them |
| E3 | PeriodsChosen, `periods-chosen` | Compaction, after it chooses and before the steps run; `info` | ledger; marks before; age lines (newest eligible day, newest closable month, keep line, year line); for each step, the span or none, where it stops and resumes when the cap or a late range stops it, and the start reason (mark, oldest-indexed, oldest-raw-day, operator-range, keep-line, none); cap; operator range; month deletes live or report-only; the re-run span |
| E4 | PeriodsTaken | Compaction. It travels on `Pass.periods` and is nested inside E5 as `periods` | Packed and re-taken days; closed months; packed years; years expired, oldest first (row 38; a pass over several roots lists each year once, merged by `runner._run_compaction_roots`); dropped months and raw days; periods written `empty`; days recorded lost; files set aside, by path; marks after. Built from the indexes the pass read compared with the end, plus the lists the drop steps and `set_aside` keep |
| E5 | TaskFinished, `task-finished` | The runner, after the task; `error` for `failed`, `warning` for `deferred`, `info` otherwise | task, outcome (Table F), dry_run, seen, selected, collection (what `taken` holds: the member ids of `workflow-runs` or `workflow-artifacts`, and none when it holds files), taken, written, bytes_freed, stopped_because, resume_from, handled_through, fault, error, where, recovered, next (one fixed sentence for each outcome word, or the fault's own sentence; none carries a value or says a member is gone), pages_read, duration_ms, fold (what the task's fold settled), periods (E4). `collection`: Fowler, 2026-10-07 (row 22) |
| E6 | ShardPublished, `shard-published` | The publisher, once for every ending, a crash included (`run_and_land` in `backend/utilities/gardener_publish.py`); `error` when the exit code is not 0, `warning` for `stale` or `lost`, `info` otherwise | shard, run_id, attempt, tasks, failed_tasks; landing (the words in `backend/idhazh/contracts/shard_landing.py`, row 27: landed, already-on-main, stale, lost, refused) or stopped_because (`ShardStop`, declared beside the event: listing-failed, check-refused, crashed), exactly one of the two; push_try (the try a landing came to rest on) and push_tries (`attempts` in the publisher's config); record; stale_paths (exactly when `landing` is `stale`); downloaded_bytes, over_budget and max_downloaded_mb; exit_code and means (its sentence from `MEANS` in `backend/idhazh/gardener/outcome.py`); error and where (exactly when a listing failed or a crash stopped the shard). Fowler, 2026-10-07 (row 22) |
| E7 | MemberOutOfOrder, `member-out-of-order` | `one_at_a_time.take`, when a walk from a mark meets a member from an earlier day than one before it; `warning` | collection, day, after. The mark stays |
| E8 | PageOutOfOrder, `page-out-of-order` | `_ArtifactWalk` in `github_collections.py`, when a page holds a member from a day before one on a page read earlier; `warning` | collection, page. Every page is read |
| E9 | PageCountChanged, `page-count-changed` | `_ArtifactWalk`, when a page counts other than the first page less the walk's deletes; `warning` | collection, page, counted, expected. The mark stays |
| E10 | ListEndMissing, `list-end-missing` | `_ArtifactWalk`, when the list does not end where the first page's count says; `warning` | collection, page, first_count. The mark stays |
| E11 | PeriodRefused, `period-refused` | A compaction step, through `CompactTree.refuse`, when it will not take a period; `error` when `fault` is `raised`, `warning` otherwise. The yearly expiry emits it at `warning`, with `range-starts-late`, at the oldest indexed year when a person's range would skip it (plan owner, 2026-10-08, from the owner's ruling of 2026-10-04) | ledger, step (row 35 added `expire-years`, the yearly expiry's word), period, fault (the record's `GardenerFault` word), ledger_fault (the ledger's own `LedgerFault` word, when a file is missing), error, where. Two keys, so the record's word and the ledger's word never share one |
| E12 | DownloadOverBudget, `download-over-budget` | A compaction step, through `stop_over_budget`, where what it would download no longer fits the shard's budget; `error` when the period is larger than the whole budget (`failed`), `info` when a later wake has room (`ceiling`) | ledger, resume_from, needed_bytes, room_bytes, max_downloaded_mb, stopped_because |
| E13 | LedgerFaultMet, `ledger-fault-met` | The drop step, when a dropped month's file is already gone; `warning` | ledger, step, period, ledger_fault |
| E14 | RawFileSkipped, `raw-file-skipped` | `named_trees.raw_days`, for a file under a ledger's raw folder that sits in no UTC day folder, so no step reads it; `warning` | path |
| E15 | LoggedText, `logged-text` | `OneJsonLine` in `event_log.py`, for a record another module logs as text while a task runs; the record's own level | logger, message (as that module said it), error, where |
| E16 | ExpiredYearsChosen, `expired-years-chosen` | The yearly expiry (`_yearly_expiry.drop`, Table B, B0), after the range check and the cap and before any delete, on every pass whose declaration sets `yearly_prune_enable` and `yearly_keep_months`, unless it refuses a person's range (E11); `info` | ledger, years (the expired indexed UTC years the pass takes, oldest first: at most the cap, only whole years inside an operator range; empty when none is due). Fowler, 2026-10-07 (row 35) |

Each event is one line of JSON: `event` (the name beside its model above), then `at` (the instant the record was made, in UTC, ISO-8601 to the millisecond with `Z`), then `level` (`info`, `warning` or `error`), then the model's fields in the order it declares them, with `None` left out and a nested model kept nested. No event declares a field named `event`, `at` or `level`. The record's message is the same JSON, so a command that writes its records as text still prints the event, and `install` is `logging.basicConfig`, so a second call adds no second handler. No field holds an exception's text, because the text can carry a ledger row fetched from the open web (Guardrail #11): `error` is the exception's type and `where` the deepest `module:line` of this package it passed through, both checked by pattern. A `logged-text` line keeps another module's message as that module said it; row 21's Found during execution names the two places in `idhazh.ledger` whose message carries an exception's text (ESCALATE trigger 3). A task's ending is said once, in `task-finished`: the runner's printed per-task report was a second rendering of it (decision T3) and is gone, and the shard's own printed lines stay for row 22. The line is ASCII only and goes to stderr through the standard `logging` module (CLAUDE.md section 1b). GitHub's runner reads workflow commands from stderr as well as stdout (`actions/runner`, `src/Runner.Worker/Handlers/ScriptHandler.cs`, read 2026-10-04), so nothing moves to stdout, and JSON escapes every line break, so no text inside an event can start a line GitHub reads as a workflow command. Tests read the payload on the log record, never the text. Fowler, 2026-10-07 (row 21).

Table F - outcome words. `report.classify` picks the first that holds, in this order, and otherwise the pass's idle outcome. A pass found work when its window held a member, it wrote or would write a file, or its fold found a closed day or month; it carried the work out when a live pass took, wrote or recovered something, or a live fold settled one; work found and not carried out is `dry-run`. The compaction's idle word is `outside-range` whenever a person named a range, `empty` when every step starts at `none`, and `not-due` otherwise; every other task's is `not-due` (known defect 65). Fowler, 2026-10-07 (row 21).

| # | Word | Means |
| --- | --- | --- |
| F1 | `failed` | A code defect stopped the task (`fault: raised`). The only outcome that turns the job red |
| F2 | `deferred` | Stopped for a cause outside the code: GitHub's API was unavailable (`api-unavailable`), or a period waits for a range that starts earlier or for a person (`range-starts-late`, `no-month-to-reopen`, `packed-file-unreadable`, row 20). The job stays green, and the next wake resumes |
| F3 | `dry-run` | Found work and only reported it |
| F4 | `ceiling` | Did work, and more is left; `resume_from` says where the next wake starts |
| F5 | `done` | Did work, and finished its work for this wake without stopping at its ceiling; the next wake takes what reaches its line by then. What it recovered, and what a monthly window that only reports kept, do not change this (row 39) |
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
- **Fixed after merge:** #1309 exposed a Data explorer fault on the canary: a window that began before a ledger's first day sent those days to the archive, which called them missing, and ten console tests went red on `main`. The owner ruled A1 on 2026-10-05: days before a ledger began are cut from the selected window, and the archive is asked only for days the site copy trimmed. #1327 is Fowler's phase L1.
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
| 3 | Keep only a first and a last year in the index | A Level 5 change to every index reader, to save one entry a year, about 14 bytes after gzip and 104 raw, as row 14's worker measured on 2026-10-05 | The site's reader and the binding tests change | Plan author, 2026-10-04 |

### Row #15 - Each old month is dropped once

- **Scope:** The drop steps follow Table B, B1 and B2. The monthly index is the record of what is left to drop, and a raw day past the line is deleted by its listed path without being parsed. A month entry with no file is dropped without a missing-file warning. Level 3.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/period_inputs.py` (not changed: no choice reads the planner's window after this row, and row 16 deletes it whole; changing its months-window branch first would have the planner name the month the month step's wake test must name itself; found during execution, Fowler's ruling)
  - `backend/idhazh/contracts/knobs/gardener.py` (the `max_periods_per_run` description now covers drops)
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_period_inputs.py` (not changed, for the same reason; found during execution, Fowler's ruling)
  - `docs/architecture/publishing/ledger-compaction.md`
  - `backend/idhazh/contracts/gardener_events.py` (`PeriodsChosen` gains `drops`, None exactly when the window keeps every month; `oldest-indexed` also names where the drop step starts; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`name_drops`, beside `name_years`, `name_months` and `name_days`; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/compaction.py` (hands step 1 its choice, and step 2 the months step 1 takes and those a first day run looked back over; found during execution, Fowler's ruling)
  - `docs/concepts/config/idhazh-gardener.md` (`max_periods_per_run` and `month_deletes_dry_run`; found during execution)
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
  - `backend/idhazh/gardener/context.py` (`TaskContext.period_range` and `operator_range`; found during execution (row 12 report), owner 2026-10-04. `operator_range` is deleted, and a compaction reads `period_range` as its range; Fowler's ruling, 2026-10-05)
  - `backend/utilities/ledger_migration/packing.py` (`pack` passes `months` to `compaction.run`)
  - `backend/idhazh/contracts/knobs/gardener.py` (the `lookback` description)
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py` (not changed: no case there names what a compaction's listing holds; found during execution)
  - `backend/tests/ledger_migration/test_packing_scope.py` (its cases that pack only named months; not changed: they pass as they stand, with the months passed as the range; found during execution)
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (the seven ledgers of 2026-10-04 run over a wake's listing, Fowler's ruling; the `lookback` case moves here from `test_period_inputs.py`, because a first run is now the only reader of a compaction's `lookback`; found during execution)
  - `backend/tests/gardener/tasks/test_compaction_years.py`, `backend/tests/gardener/test_sparse_shard.py` and `backend/tests/gardener/tasks/_task.py` (docstrings that described the planner's window; found during execution)
  - `backend/idhazh/gardener/file_listing.py` and `backend/tests/gardener/test_file_listing.py` (`saw_any_of`, which `_refuse_unnamed` reuses: a wake names no raw folder of a compaction, so `CompactTree.read` takes in only the raw days the listing already names, and none when it names none; found during execution, Fowler's ruling)
  - `tests/fixtures/gardener/task_packages/garden_tasks_ok/compaction.py` (it fetched its owned folder without naming it, which only the planner's window had made work; it names the folder first, as a compaction step does; found during execution)
  - `docs/how-to/run-the-gates.md` (what a canary build in a base-commit copy needs beyond a test run: `frontend`, the root `.gitignore`, a commit, `node_modules`, and which two fields are clocks; found during execution, the user's instruction of 2026-10-05 that what a session learns goes to `docs/`)
  - `docs/architecture/publishing/ledger-compaction.md`, `docs/architecture/publishing/idhazh-gardener.md` and `docs/concepts/config/idhazh-gardener.md` (sentences that described the planner's window, and `lookback` for a compaction; found during execution)
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
  - `backend/idhazh/gardener/tasks/_monthly_period.py` (not changed: the re-open went to `_reopened_month.py`, because this module already answers two questions, absorb and drop; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `backend/idhazh/contracts/gardener_fault.py` (`RecoveryNote` gains `reopened-month`; log-only until row 20 persists the words; found at dispatch by the owner)
  - `backend/idhazh/gardener/tasks/_reopened_month.py` (new; first sentence "How a closed month takes in raw files that land after it closed"; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`raw_files`, the raw-day read the day step and the re-open share, so row 18 changes one place; `name_months` says "a step"; found during execution, Fowler's ruling)
  - `backend/tests/gardener/tasks/test_compaction_batch.py` (its direct call to the day step passes the keep line; found during execution)
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
  - The year step looks for its own year file by Rule R before its C13 step. Otherwise it records as lost the days that an adopted year file holds (Fowler); found during execution (row 14 report), owner 2026-10-05.
  - When a year's months hold rows, `_yearly_period._pack` writes over a year file that sits at its path with no index entry. The month step refuses that case. Fowler rules whether the year step refuses it too or adopts the file by Rule R; found during execution (row 14 report), owner 2026-10-05.
  - A month with no monthly entry inside a ready year is refused as `day-missing`, and Table C names no recovery for it. Rows 18 and 19 decide whether it gets one; found during execution (row 14 report), owner 2026-10-05.
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
  - `backend/idhazh/gardener/tasks/_reopened_month.py` (a late raw file that cannot be read is set aside, and a late day's extra files wait; found during execution)
  - `backend/idhazh/gardener/file_listing.py` (`budget`, `room`, `cost`, `fetch_within_budget` and `OverBudgetError`, with `cost` and `fetch` sharing one helper; found during execution, Fowler's ruling)
  - `backend/utilities/gardener_publish.py` (passes `max_downloaded_mb` into the listing; found during execution, Fowler's ruling)
  - `backend/idhazh/ledger/raw_files.py` (`read_day_folder`, which names each unreadable file beside the rest; found during execution)
  - `backend/idhazh/ledger/paths.py` and `backend/idhazh/ledger/__init__.py` (`set_aside_path`; found during execution)
  - `backend/idhazh/contracts/gardener_fault.py` (`RecoveryNote` gains `set-aside` and `carried-over`, log-only until row 20 persists the words; found at dispatch by the owner)
  - `backend/idhazh/contracts/knobs/gardener.py` (the descriptions of `max_raw_files_per_period` and `max_downloaded_mb`; found during execution)
  - `backend/tests/gardener/test_file_listing.py` and `backend/tests/ledger/test_raw_files.py` (found during execution)
  - `docs/architecture/publishing/idhazh-gardener.md` and `docs/concepts/config/idhazh-gardener.md` (what the download ceiling now means, and how it is reset; found during execution, Fowler's ruling)
- **Acceptance gates:** local: pytest on the test files above; ruff; mypy; `doc_load.py` on both pages. CI: the full suite.
- **Oracle:**
  - A day with one unreadable raw file packs its other files. The bad file is under `set-aside/` at its old path, and the entry says `set_aside: 1`.
  - A month whose index names a day file the tree lacks closes with that day in `lost_days` and the note `recorded-lost`.
  - A day with cap + 3 raw files packs the cap and ends `ceiling`; the next pass packs the 3, and the outcome is `done`.
  - A shard budget smaller than the chosen periods stops the choice early with `ceiling`, and `over_the_ceiling` is never reached.
  - It cannot settle real corruption, which has not been seen.
- **Not in this row:** the description of `CompactEntry.set_aside` in `backend/idhazh/contracts/ledger_index.py` still says the files "could not be read or were too large", though no file is set aside for its size (decision 4). Rewording a persisted field's description changes the `CompactIndex` version stamp and the console's `COMPACT_INDEX_STAMP`, so "or were too large" goes at the next change to the `CompactIndex` shape (row 18 report).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A set-aside file is moved, never deleted, under the raw tier, because the site copies only `state/compact/` | Plan author, 2026-10-04 |
| 2 | Extra files are carried by the re-run span of row 13; there is no second mechanism | Plan author, 2026-10-04 |
| 3 | The ceiling is applied when periods are chosen, from sizes the listing already holds | Plan author, 2026-10-04 |
| 4 | C5's "larger than the size ceiling" is the shard's download budget, which is C8's case: nothing is set aside for its size, and no knob is added. A period larger than the whole budget is refused by name as `failed`, naming its bytes and `max_downloaded_mb`, because no wake could take it | Fowler, 2026-10-06 |
| 5 | The compaction steps, Rule R and the marks take every download through one listing method that refuses past the budget; `fetch` stays as it is for the three other tasks that download, so the runner's check after the tasks stays, and its message now calls a shard over it a code defect. The publisher passes the budget into the listing | Fowler, 2026-10-06 |
| 6 | The year step adopts its own unindexed file before it reads, or records lost, any month (follow-ups 4 and 5) | Fowler, 2026-10-06 |
| 7 | A month no entry names in a ready year adopts its own file; with none, its days are recorded lost when nothing of it is left, and the year is refused as `day-missing` while a day file, a raw file or a daily entry of it remains (follow-up 6) | Fowler, 2026-10-06 |
| 8 | A note names the period whose file was lost or moved. A month file costs its year every day of its month. Rule R comes before C13 at a month close too. Every month and year entry carries the `set_aside` of the periods it replaces | Fowler, 2026-10-06 |
| 9 | A move is a delete of size 0 at the old path, so `bytes_freed` stays what the deletes free | Fowler, 2026-10-06 |
| 10 | A day's extra raw files are the newest by the order settling uses (day, write instant, file id), so a carried file is newer than every packed one and the next wake settles the day as one pass would have; a file's name is not its write order | Worker, 2026-10-06, from `settle_rows` in `backend/idhazh/ledger/raw_files.py` |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep failing with `unreadable`, `too-many-raw-files` and `file-too-large` | A red run and manual work for something the gardener can record | Nothing to build | The owner, 2026-10-04 (recovery theme) |
| 2 | Leave a bad file in its day folder | The re-run span re-reads it on every wake for 30 days | Nothing to build; repeated reads | Plan author, 2026-10-04 |

### Row #19 - The marks are worked out from the indexes, and the watermark files go

- **Scope:** Each mark is worked out from the three indexes (section 2.2), and an absent index is rebuilt from named paths by Rule L. The `Watermark` contract and every committed `state/compact/<ledger>/<period>/watermark.json` are deleted (Table D, D4), so a watermark without its index can no longer happen (Table C, C9), and `index-missing` can no longer stop a pass (C14). Level 5.
- **Follow-ups:**
  - Delete the first-run case in `_compaction_periods._days` that starts at the oldest day a daily index names when no daily mark is beside it (Table B, B7). Once the daily mark is worked out from the indexes, an index that names a day always gives a mark, so the case can no longer happen; found during execution (row 13 report, Fowler 2026-10-04), owner 2026-10-05.
  - A ledger with monthly entries and no monthly watermark made the month step start at its oldest entry, and that step then adopted again a month the drop step had removed in the same pass. A monthly mark worked out from the index removes the case, and a test pins it; found during execution (row 15 report, Fowler), owner 2026-10-06.
  - `backend/tests/gardener/test_period_inputs.py` named the three watermark files for each compaction task; they go there; found during execution (row 16 report), owner 2026-10-06.
- **Files touched** (from a search for `watermark` in any case, `daily_through`, `monthly_through` and `yearly_through`, 2026-10-04, after #1267 merged; search again at dispatch, `TODO/` and `state/compact/` included. The benchmark record of what a compaction pass costs describes the pass it measured, and it stays as it is, as do the matches that mean another thing, such as a stream's `highWaterMark`):
  - `.gitattributes` (its `-merge` line for `state/compact/*/*/watermark.json`)
  - `config/idhazh_gardener.json` (`first_ledger_year`, Table D, D5)
  - `backend/idhazh/contracts/knobs/gardener.py` (`GardenerConfig.first_ledger_year`)
  - `backend/idhazh/contracts/ledger_index.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/ledger/paths.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/day_removal.py` (its docstring names the watermark)
  - `backend/idhazh/gardener/ledger_marks.py` (`work_out_marks`, and `adopt`, which Rule L calls; Rule L's places and order are in `_absent_indexes.py` below; found during execution, Fowler's ruling)
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
  - `backend/idhazh/gardener/tasks/_absent_indexes.py` (new: Rule L names the places, fetches each index's files in one download and adopts what it finds; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/context.py` and `backend/idhazh/gardener/runner.py` (`TaskContext.first_ledger_year`, filled from the gardener config; found during execution, Fowler's ruling)
  - `backend/utilities/ledger_migration/packing.py`, `backend/utilities/ledger_migration/phases.py`, `backend/utilities/build_canary_day.py` and `backend/utilities/corpus_history.py` (each builds a `TaskContext`, so each passes `first_ledger_year`; found during execution)
  - `backend/tests/gardener/tasks/_task.py` (its context carries `first_ledger_year`; found during execution)
  - `backend/tests/gardener/tasks/_marks.py` and `backend/tests/gardener/tasks/test_absent_indexes.py` (new; found during execution)
  - `backend/tests/gardener/test_sparse_shard.py` and `docs/how-to/run-the-gates.md` (found by the search at dispatch)
  - Left as they are: `TODO/20260928-55-one-page-queries-every-ledger-plan.md` names a closed plan's row title, and `TODO/20261003-59-csv-ledgers-left-plan.md` names the watermark builder in its row 11, which is `DONE`, and in its declaration D11; both record what was done and decided then (found by the search at dispatch)
- **Acceptance gates:** local: pytest on the test files above that the selector lists, `-m contract` included, and the specs it lists; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** once at dispatch, before the files were deleted, a one-off script compared the marks worked out from the committed indexes of every compaction ledger with the `through` of each committed watermark file: all 9 were equal on 2026-10-06. It is not a test, because a test never computes its answer from committed data (the owner's testing ruling, 2026-10-05). The tests are built under `tmp_path` with the helpers in `backend/tests/gardener/tasks/_task.py`, with literal expected values. A ledger with an index and no watermark resumes where its index ends. With `index/daily.json` removed and the day files kept, the pass rebuilds the index from named paths, notes `index-rebuilt` and deletes nothing. It cannot settle a watermark that was already wrong; the comparison would show it as a mismatch, and that mismatch is reported, not forced to agree.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Design the fault out instead of recovering from it: the indexes already say what each watermark says, once every empty period has an entry (rows 12 to 14) | The owner, 2026-10-04 (recovery theme); shape by plan author |
| 2 | Reader before writer: steps read marks from the indexes, then the files and the contract go, in this one row, because nothing outside the gardener reads a watermark (the site works out `through` from `daily.json`) | Plan author, 2026-10-04 |
| 3 | Rules R and L (section 2.2): an absent index is rebuilt from named paths, so `index-missing` can no longer stop a pass and the watermarks can go. Every read stays bounded: at most 31 named paths a month, and the yearly part grows by one a year (row 14, decision 3). A ledger whose daily mark stalled for longer than B7's look-back keeps older day files out of a rebuilt index (Table A, A8) | Fowler review, 2026-10-04 (ESCALATE trigger 6) |
| 4 | `first_ledger_year` is a `YYYY` string with no default, so the loader refuses a config that leaves it out, and every `TaskContext` carries it from the loader | Fowler, 2026-10-06 |
| 5 | Rule L is its own module, `tasks/_absent_indexes.py`. It rebuilds every absent index, coarsest first, before any step runs, and fetches each index's files in one download inside the shard's budget, so a rebuild larger than the whole budget fails by name. `ledger_marks` keeps `adopt` and gains `work_out_marks` | Fowler, 2026-10-06 |
| 6 | The tree works out its marks when it is read and again after each rebuilt index; within a pass the steps only move them forward, so a month the drop step removes never moves the monthly mark back | Fowler, 2026-10-06 |
| 7 | Rule L names one folder a year for each index it rebuilds: `daily/<YYYY>`, `monthly/<YYYY>` or `yearly/<YYYY>` under the ledger's compact folder, once for each year the periods it looks for fall in. Git lists every file inside, and the pass adopts only the files of those periods. So a rebuild names at most one more folder each year, inside decision 3's bound, and needs no exception. A window that keeps every month - kept for ever, deletes that only report, or a task that is a dry run - is searched from the January after the newest yearly entry, or January of `first_ledger_year`, so no month a person has not approved deleting is hidden. Its rebuild downloads up to twelve more month files each year, the rows one packed year file holds. An operator range never narrows where the rebuild looks, because a rebuilt index is written whole and no later pass looks again. A pass reads these folders only when an index is absent | Fowler, 2026-10-07, replacing Fowler, 2026-10-06 |
| 8 | A file at a Rule L place whose envelope names another ledger or period fails the task by name; nothing is guessed | Fowler, 2026-10-06 |
| 9 | A pass on a person's machine cut between its indexes and its deletes is no longer finished by the next pass: `_finish` goes from the month and year steps, and the page says to restore `state/compact/` and `state/raw/` from git. A runner lands a whole shard in one commit, so `main` never holds that state. The owner may overturn this | Fowler, 2026-10-06 |
| 10 | `compact_root(state_dir, ledger, period)` names a period's folder and `compact_path` is built from it; `watermark_path` goes. The compaction reads no wall clock once the watermark's stamp is gone, and the benchmark stops counting `write_watermark` | Fowler, 2026-10-06 |
| 11 | `LedgerFault.INDEX_MISSING` stays: the console and the ledger reader still name a missing index; only the compaction no longer stops on it | Fowler, 2026-10-06 |
| 12 | A ledger whose compact folder the commit does not hold has packed nothing, so the rebuild looks nowhere and reads nothing. The answer is `TaskContext.owned_folders`, which the runner reads from the commit before any task runs. A builder that hands a task every declared folder looks as before and loses only the saving | Fowler, 2026-10-07 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the watermarks, and rebuild a missing index from the files the marks name | Two records that can disagree, plus a repair path for that | A bounded rebuild per ledger | Plan author, 2026-10-04 |
| 2 | Keep failing with `index-missing` | Manual work | Nothing to build | The owner, 2026-10-04 (recovery theme) |
| 3 | Each pass also lists the newest closed periods' folders for the files a cut local pass left | Every wake pays a listing for a fault only a local run can cause | A bounded listing every wake, and code that deletes what it finds | Fowler, 2026-10-06 |

### Row #20 - The record says what was recovered and why a pass stopped

- **Scope:** Each task's record row carries its `recovered` notes and, only for a pass that stopped, one closed `fault` word (Table D, D3). One pure function maps an error to its result, so a code defect is always `raised`, and a member GitHub will not delete is recorded and passed (Table C, C15). The sentence a person reads is rendered from them when the row is read and is never stored. `deferred` ends a pass without turning the job red. Level 5, approved by the owner on 2026-10-04 (decision S2 and the recovery theme).
- **Follow-ups:**
  - The operator-range refusal that row 12 added ends the task `failed` today. It is not a code defect, so it gets a fault word of its own in Table D, D3 and does not turn the job red; found during execution (row 12 report), owner 2026-10-04.
  - The day step writes the note `repacked-from-raw` when it packs a day inside history that had no entry (Table C, C2). Row 12 wired only `index-rebuilt` and `recorded-lost`; found during execution (row 12 report), owner 2026-10-04.
  - The outcome `outside-range` follows Table F, F8, whose meaning row 12 narrowed: a range that a ready period before it blocks is the refusal above, never `outside-range`; found during execution (row 12 report), owner 2026-10-04.
  - `RecordedApi` is gone since row 11 (#1317): it answered every request with the same page, which a walk from the last page cannot read. The oracle names `RecordedAnswers`, whose `fails_at` makes a delete refuse; corrected from row 11's report, owner 2026-10-05.
  - The day step still refuses, by name, a raw day in a month that the monthly mark is past and no monthly entry names. Row 17 (#1331) changed that refusal's message from "raw files sit in a month already absorbed" to one that begins "no monthly entry names its month". It is not a code defect, so it gets a fault word of its own in Table D, D3; found during execution (row 17 report, Fowler), owner 2026-10-06.
  - Two cases still refuse their period by name, and Table C names no recovery for either: a day file that cannot be read when a re-run is taken into it, and a month file that cannot be read when a late file re-opens it. Row 20 gives each a fault word, or adds a recovery for it to Table C; found during execution (row 18 report), owner 2026-10-06.
- **Files touched:**
  - `backend/idhazh/contracts/collection_prune.py` (`StopReason.DEFERRED`, `stop_for`, `Recovery`, `fault`, `recovered`)
  - `backend/idhazh/contracts/gardener_fault.py` (not new: row 12 made it for the recovery notes. Its first sentence becomes "Why a gardener pass stopped, and what it recovered instead of stopping"; it gains `GardenerFault`, and `RecoveryNote` gains `repacked-from-raw` and `not-deletable`; found during execution)
  - `backend/idhazh/contracts/gardener_events.py` (`StepChoice` records the operator-range refusal as `deferred`, no longer `failed`; found during execution (row 12 report), owner 2026-10-04; the stop by Fowler, 2026-10-07)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Pass` gains `fault` and `recovered`; `take` classifies every error it catches and records a member its collection will not delete; `PruneInterruptedError` carries the classified cause. `Stop` lives in `tasks/_compact_tree.py`, below; found during execution)
  - `backend/idhazh/gardener/closed_day_fold.py` (`Folded.fault` replaces `failed`; `FoldInterruptedError` carries the classified cause)
  - `backend/idhazh/gardener/report.py` (`ended`; the row's `fault` and `recovered`; the sentence for each word, rendered and never stored)
  - `backend/idhazh/gardener/runner.py` (each task's fault comes from the classifier; only a failed row, or a shard over its download budget, sets the shard's failed exit code)
  - `backend/idhazh/gardener/github_collections.py` (`_remove_member`: a member already gone counts as deleted, and `RestApi.remove` stops swallowing 404 itself. The classifier went to `error_cause.py`, below; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/error_cause.py` (new; first sentence "What does an error a gardener pass meets mean: a member already gone, one GitHub will not delete, an API that is down, a download budget spent, or a code defect?"; found during execution, Fowler's ruling)
  - `backend/idhazh/gardener/__init__.py` (names `error_cause`; found during execution)
  - `backend/idhazh/telemetry/door_prune.py` (it also raises `PruneInterruptedError`)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_daily_period.py`
  - `backend/idhazh/gardener/tasks/_monthly_period.py`
  - `backend/idhazh/gardener/tasks/_yearly_period.py`
  - `backend/idhazh/gardener/tasks/_compaction_periods.py` (the operator-range refusal; found during execution (row 12 report), owner 2026-10-04)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`Stop.fault`, `CompactTree.recovered`, and `stop_over_budget` asks the classifier; found during execution)
  - `backend/idhazh/gardener/tasks/_reopened_month.py` (its refusals take a fault word; found during execution)
  - `backend/idhazh/gardener/tasks/_absent_indexes.py` (not changed: its `index-rebuilt` notes reach the record through `CompactTree.note_recovery`; found during execution)
  - `backend/utilities/ledger_migration/packing.py` (the migrator reads any stop that names a fault as a refusal, so a deferred range refusal still stops it; found during execution)
  - `backend/tests/contracts/test_collection_prune_row.py`
  - `backend/tests/contracts/_fixtures.py` and `backend/tests/ledger/_fixtures.py` (they name the new rows; found during execution)
  - `backend/tests/council/_imports.py` (the council's named import list names `gardener_fault`, which `collection_prune` now imports; found during execution, by CI)
  - `tests/fixtures/contracts/collection-prune-row/` (new: a `deferred` row with a fault, and two `done` rows with recovered notes - one `not-deletable` with a member id, and one of three periods - because no one pass meets both. The four rows already there gain an empty `fault` and `recovered`; found during execution)
  - `tests/fixtures/gardener/breaks/defect.json` and `tests/fixtures/gardener/task_packages/garden_tasks_breaks/` (`defect.py`, a task whose code is wrong, beside `broken.py`, whose service is down; found during execution)
  - `backend/tests/gardener/test_error_cause.py` (new; found during execution)
  - `backend/tests/gardener/test_github_collections.py`
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/_garden.py` (the breaks set names `defect.json`; found during execution)
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/gardener/test_report.py` and `backend/tests/gardener/test_download_ceiling.py` (found during execution)
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/gardener/tasks/test_collection_task.py` (the oracle's 503 and 422 cases on the task's own record; found during execution)
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py` (found during execution (row 12 report), owner 2026-10-04)
  - `backend/tests/gardener/tasks/test_compaction_years.py` and `backend/tests/gardener/tasks/test_absent_indexes.py` (their notes are read from the record; found during execution)
  - `docs/architecture/publishing/idhazh-gardener.md` (the record)
  - `docs/architecture/publishing/ledger-compaction.md` (the recovery notes)
  - `docs/architecture/contracts/state-ledgers.md` and `docs/how-to/prune-a-collection.md` (what a row holds, and the lines a pass prints; found during execution)
- **How it works:** one pure function, `classify` in `error_cause.py` (in `github_collections.py` as first written; moved by Fowler's ruling, decision 7), maps an error to a result. It tests `HTTPError` first, because `HTTPError` is a kind of `URLError`, which is a kind of `OSError`.
  - 404 or 410: the member is already gone, and counts as deleted.
  - 409 or 422: the member is recorded `not-deletable` with its id (Table C, C15). It counts against the delete ceiling, and the pass goes on.
  - 429, any 5xx, `URLError`, `TimeoutError` or `ConnectionError`: fault `api-unavailable`, outcome `deferred` (C11). The mark stays, and the next wake retries.
  - Any other 4xx, or any other exception: fault `raised`, outcome `failed` (C12). It is a code or permission defect, and the job turns red.
  - `PruneInterruptedError` and `FoldInterruptedError` carry the classified cause, and never relabel a code defect.
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_collection_prune_row.py`, and pytest on the other test files above; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** the new fixtures round-trip. A `fault` beside `stopped_because: exhausted` is refused. `ceiling-reached.json`, which has no `fault`, still reads. Each recovery in Table C writes its note, and each stop writes its fault. The classifier maps each case above, built from real `HTTPError` and `URLError` objects. With `RecordedAnswers` answering 503, the outcome is `deferred`, the mark does not move, and the shard's other tasks run. With member 2 of 3 answering 422, members 1 and 3 are deleted, and the record holds one `not-deletable` note naming member 2. A shard whose only non-green task is `deferred` exits 0. It cannot settle wording; the sentence is rendered and can change with no migration. Nor can it settle what GitHub answers for a member it will not delete (decision 6).
- **Found during execution:** the oracle's 503 and 422 cases run through the real collection task and its own record row (`test_collection_task.py`), and the shard's other tasks through `broken.py`, whose service is down, beside a new `defect.py`, whose code is wrong: the first is `deferred` and leaves the shard at exit 0, the second is `failed` and exits 1. `ceiling-reached.json` gains the two empty cells, because every committed fixture round-trips byte for byte; the older row is read with both removed, which is what a row written before this change is. The 404 rule was not new: `RestApi.remove` held it, and it moved to `_remove_member` so `classify` holds it once; a 410 counts as deleted for the first time. Run on the base commit 606a53e10, in a copy outside this checkout, the 13 changed test modules fail to import (`GardenerFault`, `Recovery`, `stop_for` and `error_cause` are absent), and the base code refuses the three new rows, ends a 503 `failed` with no fault, stops at the 422 member and never deletes member 3, ends a 410 `failed`, and records the range refusal `failed`. The migrator read a refusal as `failed` only, and three of its tests went red until it read any stop that names a fault. Seven refusals still end `failed` with `raised` though a person, not a code change, settles them: a year with a month that never closed (`day-missing`), a year file over GitHub's large-file line, a month's own unindexed file holding other rows than its days, a Rule R or L file whose envelope names another ledger or period, an index this build cannot trust, a raw-folder entry that is not a file, and a period larger than the whole download budget. Each would need a word of its own in Table D, D3 to end `deferred` (ESCALATE trigger 1), so they are reported to the owner rather than given one. A 403 is `raised` as the mapping says, but GitHub answers a spent rate limit with 403 or 429; reading a 403 that carries `x-ratelimit-remaining: 0` or `retry-after` as `api-unavailable` is one header test and changes the approved mapping, so it is the owner's call (Fowler, 2026-10-07).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A closed word plus the existing `resume_from`; the sentence is rendered when read (decision S2) | The owner, 2026-10-04 |
| 2 | What was recovered is a note, not a fault, so a recovered pass is `done` | The owner, 2026-10-04 (recovery theme) |
| 3 | Exception text is never stored, because it can carry fetched row text (Guardrail #11) | Fowler, 2026-10-04 |
| 4 | No fault word for an interruption. A killed process lands nothing (Table C, C10), and both wrappers caught every exception, so a code defect would have been recorded as an interruption, ended `deferred` and left the job green | Fowler review, 2026-10-04 |
| 5 | A member GitHub will not delete is recorded `not-deletable` with its id, and the mark may pass it. Before, one refused member stopped every later pass, so nothing behind it was ever deleted | Fowler review, 2026-10-04 |
| 6 | 409 and 422 mean a member GitHub will not delete. That is a reading of GitHub's documentation, not a measurement: when a pass first meets such an answer, its response is recorded as a test fixture | Fowler review, 2026-10-04 |
| 7 | The classifier is a module of its own, `error_cause.py`, not part of `github_collections.py`: `take` must call it and the driver imports `take`, and the runner, the fold, the ledger prune and the compaction's budget ask it too. It gives `GONE`, `NOT_DELETABLE`, `API_UNAVAILABLE`, `BUDGET_SPENT` or `RAISED`; a stop records `api-unavailable`, or else `raised`, so a 404 on a read is a defect. A member already gone is absorbed by `github_collections._remove_member`, so the artifacts walk still counts the delete | Fowler, 2026-10-07 (row 20 worker's consult) |
| 8 | The four refusals the follow-ups name end `deferred`: `range-starts-late`, `no-month-to-reopen`, and `packed-file-unreadable` for a day file a re-run is taken into or a month file a late file re-opens that cannot be read or is not there, because C13 already treats a packed file the tree lacks as unreadable. A fault word, not a set-aside, because the entry would then call the period whole while it holds only the rows that ran again. `StepChoice` records the range refusal `deferred` with no new field. A step a fault stopped holds the daily mark below its day either way | Fowler, 2026-10-07 (row 20 worker's consult); the follow-ups, owner 2026-10-04 and 2026-10-06 |
| 9 | `error_cause.classify` decides both download-budget cases by one rule, that more than the whole budget is a defect: an `OverBudgetError` for a period larger than the budget ends its step `failed` with `raised` and a smaller one ends it at `ceiling` for a wake with room, and a shard whose downloads passed the budget exits 1 with no task row marked, because no row can say which task downloaded past it | Fowler, 2026-10-07, on the owner's note of 2026-10-07 |
| 10 | `repacked-from-raw` is noted only when the day is at or below the mark, no entry named it, nothing was adopted for it, and raw files packed it, so the note never depends on which step adopted a file first | Fowler, 2026-10-07 (row 20 worker's consult) |
| 11 | `raised` pairs with `failed` and every other word with `deferred` (`stop_for`); a `deferred` row names its fault, and a `failed` row written before 2026-10-07 reads with none. Only a failed row, or a shard over its download budget, sets the failed exit code. A fold's fault decides the row when the fold stopped, and the fold is skipped after any stop. The changelog drops its 2026-09-30 entry to stay at five | Fowler, 2026-10-07 (row 20 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A stored free-text reason (decision S1) | Fetched text could reach the record, and no reader can act on prose | A sanitizer and a length cap | Fowler, 2026-10-04 |
| 2 | Every stop red, as today | A recoverable stop asks a person for work | Nothing to build | The owner, 2026-10-04 |
| 3 | Retry inside one wake with a retry library | The next wake already retries, and nothing yet says how often GitHub's API is unavailable | A dependency and its tests; priced by how often `deferred` appears on the record | Fowler review, 2026-10-04 |
| 4 | Keep the fault word `interrupted` for a wrapped exception | A code defect would read as an interruption, end `deferred` and leave the job green | Nothing to build; a defect nobody sees | Fowler review, 2026-10-04 |

### Row #21 - Every gardener log line is one JSON event

- **Scope:** The events of Table E become models, `event_log.py` writes each one as one JSON line (section 2.5), and the free-text log lines of the gardener are deleted. Level 3.
- **Follow-ups:**
  - Row 11 (#1317) added three warning lines that become events here: the order check failed, a page's count differs from the first page's, and the list does not end where the count says. E2's pages read is filled from the walk; found during execution (row 11 report), owner 2026-10-05.
  - `PruneInterruptedError` said "Those are gone" on a dry run as well as a live one; that is the oracle's dry-run case. A dry run's message now says it deleted none, and `FoldInterruptedError` says the same of a dry-run fold (found by Fowler). Source: row 20's report, owner, 2026-10-07.
  - The compaction's refusal lines (`_refused`, `_kept`) logged the ledger's own fault word under `fault=` at error level, while the record's fault is a `GardenerFault` word. The `period-refused` event gives the two words two keys, `fault` and `ledger_fault`, and a refusal that ends `deferred` is a warning, not an error. Source: row 20's report, owner, 2026-10-07.
  - `CompactTree.note_recovery` logged one warning line for each note. The line is gone: the notes are on the record and in `task-finished`. Source: row 20's report, owner, 2026-10-07.
  - `report.WHY` and `report.NOTED` hold one sentence for each fault word and each note word. `task-finished`'s `next` takes `WHY` when a fault stopped the task; `NOTED` stays for row 22's summary. Source: row 20's report, owner, 2026-10-07.
  - Fewer tests read `caplog` since row 20, because the notes are read from the record; every test left that read gardener log text now reads the event on the record. Source: row 20's report, owner, 2026-10-07.
  - Known defect 61: `cli.py` formatted records with `%(asctime)s` on the local clock. Every line the new handler writes carries `at`, the record's instant in UTC with `Z`, and `test_event_log.py` pins it under a zone that is not UTC. Defect 61's entry says the gardener's part is fixed; the other two command lines stay open. Source: `TODO/20260823-known-defects-plan.md`, owner, 2026-10-07.
  - A line that starts with a workflow command stays raw and unwrapped; row 22 owns its words. The gardener's only such lines are the publisher's `::warning::` for a `stale` or `lost` landing, printed on stdout. `.github/workflows/idhazh-gardener.yml`, the one workflow that runs the gardener, reads no gardener log text: its `run-tasks` step pipes nothing, and the two steps that write `$GITHUB_OUTPUT` read `gardener_shards.py` and `corpus_squash_due.py`, which install no gardener handler. Source: the owner's brief, owner, 2026-10-07.
- **Files touched:**
  - `backend/idhazh/contracts/gardener_events.py`
  - `backend/idhazh/gardener/event_log.py` (new; first sentence "How a gardener event becomes one log line")
  - `backend/idhazh/gardener/report.py` (`classify`; `next_step` and `finished` beside `row`; `lines`, `_span`, `_what_next` and `fold_lines` deleted; found during execution, Fowler)
  - `backend/idhazh/gardener/one_at_a_time.py` (`Pass.idle_outcome`; WindowChosen in `take`; the message of `PruneInterruptedError`; `Pass.pages_read` and `Pass.periods`, `Collection.pages_read`, and `MemberOutOfOrder`; found during execution, Fowler)
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/cli.py` (`settings_or_none` installs the handler once)
  - `backend/idhazh/gardener/__init__.py`, `closed_day_fold.py` (the dry-run fold's message), `github_collections.py` (row 11's three warnings become events; both walks count their pages) and `named_trees.py` (`RawFileSkipped`) (found during execution)
  - `backend/idhazh/gardener/tasks/_compact_tree.py`, `_daily_period.py`, `_monthly_period.py`, `_yearly_period.py`, `_reopened_month.py` and `_compaction_periods.py` (refusals, the budget stop, E4 and the idle word; the unused `why` text and the module loggers deleted; found during execution)
  - `backend/idhazh/gardener/tasks/telemetry_aggregate.py` and `visual_prune.py` (their summary lines deleted; found during execution)
  - `backend/tests/gardener/test_event_log.py` (new)
  - `backend/tests/gardener/_events.py` (new: reads events off records; found during execution)
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_one_at_a_time.py`
  - `backend/tests/gardener/test_report.py` (`report.lines` is gone; found during execution)
  - `backend/tests/gardener/tasks/test_visual_prune_task.py`
  - `backend/tests/gardener/tasks/test_names_only_shard.py`
  - every test that reads gardener log text with `caplog`, from a search for `caplog` under `backend/tests/gardener/` at dispatch: `test_download_ceiling.py`, `test_github_collections.py`, `tasks/test_compaction.py` (with `test_compaction_periods.py` through its `chosen_on`) and `tasks/test_compaction_years.py`
  - `docs/architecture/publishing/idhazh-gardener.md` (logging)
  - `docs/architecture/publishing/ledger-compaction.md`, `docs/how-to/prune-a-collection.md` and `docs/how-to/run-the-pipeline.md` (each described a line that is gone; found during execution)
  - `TODO/20260823-known-defects-plan.md` (defect 61; the owner's fold)
- **Acceptance gates:** local: pytest on the listed test files; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** unit: each event renders as one line of valid ASCII JSON with `event` first, `None` left out and nested models kept nested. Integration in `tmp_path`: one ledger for each outcome word in Table F. TaskPlanned comes before TaskFinished, and each carries its fields; tests read the payload on the record, not the text. A dry run whose listing fails part way never logs that anything is gone: today `one_at_a_time.PruneInterruptedError` says "Those are gone" for a dry run too, and `runner._run_one` logs it. It cannot settle how readable JSON is in GitHub's log viewer; row 22's summary is the view for a person.
- **Found during execution:** the line carries `at` and `level` after `event` and before the event's fields, so section 2.5's sentence on the line format, and Table E, which names none of the events this row added (decision 4), are the owner's to update; this row edits only its own section. Run on the base commit 0bde65e46, in a copy outside this checkout, 9 of the 10 changed test modules fail at import (`TaskOutcome`, `TaskFinished`, `CompactionStep` and the other new events are absent); the tenth reads the visual-prune report row, which the base already writes. A probe drove the base code for each case of the oracle: a dry run whose listing fails part way says "Those are gone"; the runner's records carry no event, its lines are free text ("periods chosen {...}", "compaction of visual-prunes: 4 files written, ..."), and the report goes to stdout as printed lines; and the line for 09:46:00.500 UTC reads "2026-10-07 15:16:00,500 WARNING ..." under a zone five and a half hours east. On this branch each case gives the opposite. The canary, built on the base and then on this branch through the gate lock, holds the same 45 files: 28 identical, and 17 packed files whose 155 rows and 89 index entries are identical and whose only differing keys are the write clocks `file_id` and `written_at_ms`. A refused period's sentence is gone with its line, so a person reading a `raised` refusal sees its step, period, words, and the exception's type and code place, but not the numbers the sentence held, such as a year file's size; the fault words row 20 sent to the owner are the fix. Known gap: a retention task run with `--from` and `--to` that finds nothing ends `not-due`, because `TaskContext` holds the person's range and the scheduled window in one field; `task-planned` shows the range all the same (Fowler, 2026-10-07). `idhazh.ledger` logs an exception's text in two places, `raw_files._skip` and the "skipped a ledger file" warning in `ledger_files.py`, and the compaction calls both; a pydantic error there prints row values, so this is ESCALATE trigger 3 from before this row, reported to the owner with a proposed Level 2 row that logs the exception's type instead. This row does not widen it: a `logged-text` line keeps that message as it was, and three gardener sources of the same kind are gone.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | JSON lines (decision T2) | The owner, 2026-10-04 |
| 2 | One handler on stderr, its level from config (CLAUDE.md section 1b) | Fowler, 2026-10-04 |
| 3 | A line is `event`, then `at` (the record's own instant, UTC, to the millisecond, with `Z`), then `level`, then the fields; the record's message is the event's JSON too, so a command that formats records as text still prints it; `install` is `logging.basicConfig`, so a second call adds nothing; no event declares a field named `event`, `at` or `level` | Fowler, 2026-10-07 (row 21 worker's consult); `at` from the owner's fold on defect 61 |
| 4 | Events beyond Table E, one small model for each fact: `member-out-of-order`, `page-out-of-order`, `page-count-changed` and `list-end-missing` for the walk checks; `period-refused` (step, period, `fault`, `ledger_fault`, error type, code place), `download-over-budget`, `ledger-fault-met` and `raw-file-skipped` for the compaction; `logged-text` wraps a record another module logs as text | Fowler, 2026-10-07 (row 21 worker's consult) |
| 5 | No field holds an exception's text: `error` is its type and `where` the deepest `module:line` of this package it passed through, both checked by pattern | Fowler, 2026-10-07 (row 21 worker's consult); row 20, decision 3 |
| 6 | The runner's printed per-task report (`report.lines`, `fold_lines`) is a second rendering of `task-finished`, rejected as T3, so it is deleted; the shard's own printed lines stay for row 22 | Fowler, 2026-10-07 (row 21 worker's consult) |
| 7 | E2 is said at the top of `take`, before the listing is read, so a walk that fails at once has already said its window; the total pages read moves to the pass and to `task-finished`, because it is only known at the end | Fowler, 2026-10-07 (row 21 worker's consult) |
| 8 | `next` is one fixed sentence for each outcome word, or the fault's own sentence; no sentence carries a value or says a member is gone | Fowler, 2026-10-07 (row 21 worker's consult) |
| 9 | `classify`: work is found when the window held a member, a file was or would be written, or the fold found a day or month; carried out when a live pass took, wrote or recovered something, or a live fold found something; `dry-run` is found and not carried out. The compaction's idle word is `outside-range` whenever a person named a range, `empty` when every step starts at `none`, else `not-due` | Fowler, 2026-10-07 (row 21 worker's consult) |
| 10 | E4 is built from the indexes the pass read compared with the end, plus the lists the drop steps and `set_aside` keep, and travels on `Pass.periods`; `task-finished` also carries `handled_through`, the fold, and the exception's type and place | Fowler, 2026-10-07 (row 21 worker's consult) |
| 11 | `declared` is the declaration as it dumps, without `kind`, `owns`, `reads`, `appends_to` and the prose of `prune_refusal`; a null knob stays null | Fowler, 2026-10-07 (row 21 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One `key=value` line per event (decision T1) | The owner chose JSON | Nothing | The owner, 2026-10-04 |
| 2 | JSON plus a readable line for each event (decision T3) | Two renderings to keep in step | Twice the lines | Fowler, 2026-10-04 |
| 3 | Keep a refusal's sentence in its event | The large-file sentence and a pydantic error that prints a row arrive through one `except ValueError`, so keeping one keeps the other | A new exception type every refusal site must use | Fowler, 2026-10-07 (row 21 worker's consult) |
| 4 | Refusals as a list inside E4 | A refusal happens at a moment and has its own level; a task that crashed after it would lose it | Nothing to build | Fowler, 2026-10-07 (row 21 worker's consult) |

### Row #22 - A person reads a shard at a glance

- **Scope:** When it runs on GitHub, each task's lines fold into one group, a `failed` task adds one error line, and each shard writes a summary to its job page whether it passes or fails. The summary says where the record went, what the exit code means, and one line per task. Level 2.
- **Follow-ups:**
  - A deferred row is green, so the summary lists it with its word. The `::error` line can use the GardenerFault word `raised` and the sentence in `report.WHY`. A shard over its download budget exits 1 with no failed row, so the summary needs its own line for that case; found during execution (row 20 report), owner 2026-10-07.
  - These lines are still printed, and they are row 22's: the runner's exit-2 refusals, the over-budget message, `run-task`'s "shard N: wrote X and pushed nothing" line, and every publisher line, including the `::warning::` lines for a stale or lost landing; found during execution (row 21 report), owner 2026-10-07.
  - The summary can read `task-finished`'s outcome word, periods, fold and next, and `report.WHY` and `report.NOTED` hold one sentence for each fault word and each note word; found during execution (row 21 report), owner 2026-10-07.
  - A `task-finished` that ends `failed` carries `error`, the exception's type, and `where`, its `module:line`, so an `::error` line can name the place; found during execution (row 21 report), owner 2026-10-07.
  - Trust boundary (ESCALATE trigger 3, Guardrail #11): the summary, the `::error` lines and every line printed carry closed words, counts, periods, member ids, the exception's type and its code place, and never an exception's message or a row's value, because a message can quote fetched text. A test pins it with a failure whose exception message carries a marker, and `backend/idhazh/ledger/` is left to the row that fixes its log lines; found during execution (row 21 report), owner 2026-10-07.
  - Decision 1's `::error` form uses the fault word and the `report.WHY` sentence, never the exception's text; found during execution (row 21 report), owner 2026-10-07.
- **Files touched:**
  - `backend/idhazh/gardener/event_log.py` (GitHub mode: `GitHubLines`, and `install` takes `github`)
  - `backend/idhazh/gardener/workflow_commands.py` (new; first sentence "Which workflow commands does GitHub read beside a gardener event, and how is each escaped?"; found during execution, Fowler)
  - `backend/idhazh/gardener/run_summary.py` (new; first sentence "What one shard did, as Markdown for the job's summary page")
  - `backend/idhazh/contracts/gardener_events.py` (ShardPublished; `ShardStop` and `TaskFinished.collection` found during execution, Fowler)
  - `backend/idhazh/gardener/outcome.py` (`Outcome.finished_tasks`, `downloaded_bytes` and `over_budget`, and `MEANS` beside the exit codes: `Outcome` lives here, not in `runner.py`; found during execution, Fowler)
  - `backend/idhazh/gardener/runner.py` (fills those three; its record-name refusal no longer prints an exception's text; found during execution)
  - `backend/idhazh/gardener/report.py` (`finished` takes the collection; Reader's carried-over sentence; found during execution)
  - `backend/idhazh/gardener/cli.py` (`settings_or_none` takes `github`) and `backend/idhazh/gardener/__init__.py` (names the two new modules) (found during execution)
  - `backend/utilities/gardener_publish.py` (says how the shard ended once, on every ending, with its summary; its push lines fold into ShardPublished; `main` reads `GITHUB_ACTIONS` and `GITHUB_STEP_SUMMARY`; the listing line names the exception's type, not its text)
  - `backend/tests/gardener/test_run_summary.py` (new)
  - `backend/tests/gardener/test_workflow_commands.py` (new; found during execution, Fowler)
  - `backend/tests/gardener/test_event_log.py`
  - `backend/tests/gardener/test_publish.py`
  - `backend/tests/gardener/test_runner.py` (a shard refused after a task ran still says how it ended; found during execution)
  - `backend/tests/gardener/_garden.py` (`quiet_git` also clears `GITHUB_STEP_SUMMARY` and `GITHUB_ACTIONS`, which CI's own step sets; found during execution)
  - `backend/tests/gardener/test_sparse_shard.py` (the listing line no longer quotes its exception; found during execution)
  - `tests/fixtures/gardener/task_packages/garden_tasks_breaks/defect.py` (its exception quotes a row, the marker; found during execution)
  - `docs/architecture/publishing/idhazh-gardener.md` (the summary)
- **Acceptance gates:** local: pytest on the three test files; ruff; mypy; `doc_load.py`. The sufficiency checks in `docs/concepts/design-system.md` apply to the summary, or a `## Design rationale` entry says why not. CI: the full suite.
- **Oracle:** a shard with one `failed` task whose record landed writes a summary with the landing line and the failed row, and still exits 1. A shard with only `deferred` and `done` tasks writes its summary and exits 0. An error line escapes `%`, CR and LF. It cannot settle how GitHub draws the summary; the first scheduled run after the merge shows it.
- **Found during execution:** `Outcome` lives in `outcome.py`, so `finished_tasks` is declared there and the runner fills it. The listing-failure line printed its exception's text, and `test_sparse_shard.py` asserted that text; the line now names the type and place, and the test checks that instead. A compaction's `months_dropped` and `raw_days_dropped` list both the months it deleted and the months a report-only monthly window only named, so the summary says "found past the keep line", not "deleted". Run on the base commit fa6379737, in a copy outside this checkout:
  - `test_run_summary.py` and `test_workflow_commands.py` fail at import, because `ShardPublished` is absent, and `test_publish.py` fails at import, because `PushOutcome` is absent.
  - In `test_event_log.py`, the two GitHub-mode tests fail: there is no `GitHubLines`, and `settings_or_none` takes no `github`.
  - The listing test of `test_sparse_shard.py` fails, because the base prints "GitHub did not report a size for blob ...".
  - A probe drove the base through each oracle case. A shard with a failed task exits 1, and a shard with a deferred and a done task exits 0. Both print "shard 0: landed on main, try 1 of 6", write no summary although `GITHUB_STEP_SUMMARY` names a file, and log no `shard-published`. A listing whose range is not a date prints "Invalid isoformat string: 'Breaking: click https://example.invalid/now'", the planted text.

  On this branch every case gives the opposite. The canary was built on the base and then on this branch, through the gate lock. Its `state/` holds 45 files on both:
  - 28 are byte-identical;
  - 16 are packed files whose 155 rows are identical, and the only keys that differ are the write clocks `file_id` and `written_at_ms`;
  - one raw item-health file's name holds its write time, and its one row is identical.

  The site build at the end fails on both after `state/` is complete, because this machine has no `frontend/node_modules`. Table E is the owner's to update, as for row 21. E6, `shard-published`, now fires on every ending, a crash included. It logs at `error` when the exit code is not 0, at `warning` for `stale` or `lost`, and at `info` otherwise, and it carries the fields in decision 3. E5 gains `collection` (decision 8). When an exception escapes the publisher, Python's own traceback prints the exception's text. That was already so before this row. A crash there has already passed every task's own error handling, so the fault is in the runner or publisher code, and removing the traceback would take the stack out of the job log. It is reported to the owner under ESCALATE trigger 3 rather than changed (Fowler, 2026-10-07). Reader also asked for a `::warning` on the run page for a deferred task that waits for a person. Fowler rejected it as more than the row needs (rejected option 2); the heading names every deferred task instead.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `::group::<task> (<kind>)` before TaskPlanned and `::endgroup::` after TaskFinished; a `failed` task adds `::error title=<task>::<fault> at <resume_from>: <advice>` | Fowler, 2026-10-04 |
| 2 | The summary is written in `try/finally`, so it exists on pass or fail | Fowler, 2026-10-04 |
| 3 | ShardPublished is said once for every ending, a crash included, so the summary has one input: `landing`, or `stopped_because` (`listing-failed`, `check-refused`, `crashed`, declared beside the event), never both; `means`, `failed_tasks`, `stale_paths`, `downloaded_bytes`, `over_budget`, `max_downloaded_mb`. An error when the exit code is not 0, a warning for `stale` or `lost`, information otherwise | Fowler, 2026-10-07 (row 22 worker's consult) |
| 4 | Decision 2 as Extract Function: `run_and_land` says how the shard ended when its body returns, and in `except Exception` before it raises again; a cancel or `SystemExit` has no exit 1 to report | Fowler, 2026-10-07 (row 22 worker's consult) |
| 5 | The exit codes' sentences (`MEANS`) sit beside the codes in `outcome.py`; only the code that builds the event reads them, and the summary reads `means` | Fowler, 2026-10-07 (row 22 worker's consult) |
| 6 | The commands around an event are `workflow_commands.py`, which imports only contracts; `::error` comes after `::endgroup::`, so it shows while the group is folded, and reads `<fault> while it worked on <resume_from> (<error> at <where>): <next>`, the event's own `next`, each part dropped when absent | Fowler, 2026-10-07 (row 22 worker's consult); "while it worked on" by Reader, because "at 2026-09-20" read as the date of the error |
| 7 | `gardener_publish.main` alone reads `GITHUB_ACTIONS` and `GITHUB_STEP_SUMMARY` and passes both down; the workflow does not change | Fowler, 2026-10-07 (row 22 worker's consult) |
| 8 | `TaskFinished.collection` says what `taken` holds, so the summary names files, runs or artifacts | Fowler, 2026-10-07, on Reader's ruling |
| 9 | The summary's form: one H3 heading, meaning first and the exit code last; three columns, Task, How it ended, What it did, in run order; each `next` sentence once, below the table; only `failed` bold, and words for every state; the downloads against the budget on every measured shard; what was handled without stopping last | Susan, 2026-10-07 |
| 10 | The summary's sentences: the heading words, where the record went for each landing and stop, the download and crash lines, "Handled without stopping", the carried-over sentence, and the name of what a task took; the heading names a deferred task, because a deferral that waits for a person exits 0 behind a green tick | Reader, 2026-10-07 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A shared helper for `$GITHUB_STEP_SUMMARY` | Two writers do not earn one | A module | Fowler, 2026-10-04 |
| 2 | A `::warning` for a deferred task, and an `::error` for a shard over its budget or a refused push | The summary and the job's colour say them already | One line each in `workflow_commands.py`, and for the deferral a list of which faults wait for a person | Fowler, 2026-10-07; Reader asked for the deferral's warning, sent to the owner |
| 3 | `--summary` and `--github` flags on the command line | A workflow edit and a workflow-test edit, and nothing gained | Two flags | Fowler, 2026-10-07 |
| 4 | An emoji or an HTML-entity glyph beside a failed row | GitHub draws no emoji shortcode in a summary, and a glyph breaks the ASCII rule | One entity a word | Susan, 2026-10-07 |

### Row #23 - The gardener ledger is packed live

- **Scope:** `config/gardener/compact-gardener.json` gets `dry_run: false`, so the gardener's own records are packed into one file a day and then one a month. Level 2.
- **Follow-ups:**
  - A first run looks back `lookback` months (default 2) before the month that holds the newest eligible day (Table B, B7). The gardener ledger's oldest raw day was 2026-09-30 on 2026-10-05, and from the wake of 2026-12-03 it falls outside that look-back, so a first live pass from then on would leave its older raw days raw. Before switching on, check the oldest raw day against the look-back and, when it falls outside, raise `lookback` in the same change so the first live pass reaches it. `compact-visual-prunes` (oldest raw day 2026-09-06, outside from 2026-12-03) and `compact-run-plan` (2026-10-04, outside from 2027-01-03) have never packed either and need the same check when they switch on; found during execution (row 13 report), owner 2026-10-05.
  - Since #1309 a first run starts at its oldest raw day and writes no zero-row file, so the cost named in rejected option 1 below no longer holds; Fowler's order for readable first-pass logs still does; found during execution (row 13 report), owner 2026-10-05.
  - The gardener ledger's days written before 2026-10-07 read with no fault and no notes and pack under today's columns, so its first live pass needs nothing from row 20; found during execution (row 20 report), owner 2026-10-07.
- **Files touched:**
  - `config/gardener/compact-gardener.json` (not changed: #1382 set `dry_run: false` on 2026-10-07, and the look-back needs no raise; found during execution)
  - `backend/tests/contracts/test_gardener_config.py` (both of its switches in `LIVE_BY_DECISION`, with the owner's decision as the reason. Not changed: #1382 named both, and `yearly_prune_enable`, with the owner's approval of 2026-10-07 as the reason; found during execution)
  - `docs/concepts/config/idhazh-gardener.md` (the list of live switches the contract test names, which left out every switch #1382 turned live; found during execution)
  - `docs/architecture/publishing/ledger-compaction.md` (its intro counts six compaction tasks, two packing live and one packing years. On 2026-10-04 `config/gardener/` held 12, 7 with `dry_run: false` and 4 that set `monthly_keep_days`; count again at dispatch. At dispatch #1382 had rewritten the intro for fourteen; the intro now says all fourteen pack live, and the diagram's dry-run box no longer names three report-only compactions; found during execution)
  - `TODO/20260930-57-upkeep-tasks-switch-on-plan.md` (its row "The upkeep record, the picture cleanup's record and the feed retirements are packed live" names this row by title for `compact-gardener`. It never named this row; that row's Scope line names `compact-gardener`, and it now says the switch is done; found during execution)
- **Acceptance gates:** local: `-m contract backend/tests/contracts/test_gardener_config.py`; `doc_load.py`. CI: the full suite.
- **Oracle:** `test_gardener_config.py` refuses a live switch with no decision, and accepts this one. The first scheduled run after the merge is read: `compact-gardener` ends `done` or `ceiling`, writes no zero-row file and no entry before the ledger's first day. If not, the owner sets `dry_run` back to `true` in a pull request at once. It cannot settle the first drop, due around November 2027.
- **Found during execution:** #1382, merged on 2026-10-07 at 17:09 UTC before this row started, already set `dry_run: false` here and in every other compaction, under the owner's approval of that day. It also named this task's `dry_run`, `month_deletes_dry_run` and `yearly_prune_enable` in `LIVE_BY_DECISION`, with that approval as the reason. So this row changes no config and no test. The reason stays the approval of 2026-10-07, not the ruling of 2026-10-04 in decision 1, because it is the decision that turned the switch live and it covers this ledger. No wake has run since #1382, so the wake of 2026-10-08 is the first live pass whenever this row merges, and it is the run the oracle reads.
  - Oracle: `-m contract backend/tests/contracts/test_gardener_config.py` passes 129 tests on the base commit 7dc127c5d, in a copy outside this checkout, and on this branch, because #1382 already carries the switch and its decision. With the copy's entry for this task's `dry_run` deleted, the switch test fails and names `('compact-gardener', 'dry_run')` as live with no decision.
  - Look-back: the oldest raw day on `main` is 2026-09-30, read by name (`git ls-tree origin/main state/raw/gardener/`, then `2026/` and `2026/09/`). At the wake of 2026-10-08 the newest due day is 2026-10-06, so a first run looks back over 2026-08 to 2026-10, and 2026-09-30 is inside. `lookback` keeps its default of 2. The day would fall outside from the wake of 2026-12-03, and once a pass lands the daily index, no first run looks back again.
  - Preview, through `runner.run` as a shard runs the task, on copies of `origin/main` at 55045f5d7 outside this checkout. With `dry_run` forced on, at the clock of 2026-10-07 it would pack 2026-09-30 to 2026-10-05 and delete 40 raw files, 390,935 bytes; at the next wake's clock, 2026-09-30 to 2026-10-06 and 45 raw files, 440,771 bytes. Neither refuses a period or closes a month. Run live at the next wake's clock in a throwaway copy, it ends `done`: seven day files, each `packed` with 18 to 57 rows, no `empty` or `lost` entry and none before 2026-09-30, and empty monthly and yearly indexes. `load_days` reads the same 169 rows before and after. `workflow-runs`, which runs after it in shard 0, and `workflow-artifacts` read the same marks from the packed ledger as from the raw one, 2026-07-09 and 2026-09-07.
  - The canary build packs only the published ledgers and `feed-health`, so it never runs this task, and there is no canary tree to compare.
  - The oracle's last sentence is out of date: since #1382 every monthly window is forever, so no month is dropped, and the first rows deleted are the year 2026's, when it expires on 2030-01-01.
  - Every compaction pass logs one `logged-text` line, "yearly expiry ledger=<ledger> years=[...]", from `backend/idhazh/gardener/tasks/_yearly_expiry.py`, which #1382 added after row 21. Table E has no event for it. It carries no fetched text.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Switch it on after rows 16 and 22, so its first live pass uses the new rules and is easy to read | The owner, 2026-10-04 (the gardener ledger is compacted); order by Fowler |
| 2 | The `LIVE_BY_DECISION` entry for this task's `dry_run` keeps #1382's reason, the owner's approval of 2026-10-07, not the ruling of 2026-10-04 in decision 1, because that approval turned the switch live and covers this ledger (option B1 of row 23's report) | Plan owner, 2026-10-07 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Switch it on now | Its first pass would fill its first month from the 1st under the old rules | About 29 zero-row files, about 155 KB (an estimate) | Fowler, 2026-10-04 |

### Row #24 - Months close 16 days after they end

- **Waiting:** for decision C (section 0, Waiting on the owner). Not dispatched until the owner rules.
- **Scope:** `daily_keep_days` becomes 16 in every compaction declaration, and its floor becomes 1. `seen` and `counterfactual-scores` keep a 3-month window so their readers keep 90 days. A late re-run file is handled by row 17. `docs/concepts/config/idhazh-gardener.md` gains a `compact-run-plan` row (#1284) in its table of compactions that ship, and names that task in its sentence on the month-delete switch; found during execution (row 7 report), owner 2026-10-04. Level 4: months closed at 16 days are not re-opened by going back.
- **Follow-ups:**
  - The re-run span starts 30 days before the wake. Two kinds of re-run fall outside it at the next wake: one made on the 30th day after its run that lands after that day's wake, and one that writes rows dated before its run's own day. At a 16-day keep, the file of either would sit unseen in a closed month. A span one day longer, or one counted from each day's own run, closes the gap; found during execution (row 17 report, Fowler), owner 2026-10-06.
  - `docs/concepts/config/idhazh-gardener.md` and the field description of `month_deletes_dry_run` in `backend/idhazh/contracts/knobs/gardener.py` say that `true` keeps a raw day in a month past the window "and packs those days and months like the rest". Both should say instead that a raw day in a closed month past the line stays where it is. Row 24 already edits both files; found during execution (row 17 report), owner 2026-10-06.
  - Two items in row 24's scope landed early in #1321 and leave it: the `compact-run-plan` row in the config page's table of compactions that ship, and that page's sentence on the month-delete switch, which now names `compact-run-plan`; corrected from #1321's report, owner 2026-10-06.
  - At a 16-day keep, a late file is likely to meet a closed month more often (an estimate). Each such refusal now ends `deferred` with `no-month-to-reopen` or `packed-file-unreadable`, so it is green and named on the record. The span gap in row 24's own follow-up still writes nothing, because no pass sees that file; found during execution (row 20 report), owner 2026-10-07.
  - To say "deleted" rather than "found past the keep line" for old months in the shard summary, `PeriodsTaken` (Table E, E4) needs one field that says whether the month deletes were live. That is a small change to an event that is not persisted; found during execution (row 22 report), owner 2026-10-07.
  - #1382 set `daily_keep_days` to 45 on all fourteen compactions, under the owner's approval of 2026-10-07, so this row's 16 days waits for decision C (section 0); found during execution (row 23 report), owner 2026-10-07.
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
- **Follow-ups:**
  - `shard-published` (Table E, E6) is not persisted, so the console can show only the record rows, not landings or exit codes. The sentences for each fault and note word (`report.WHY` and `report.NOTED` in `backend/idhazh/gardener/report.py`) and the phrase for each task's work (`backend/idhazh/gardener/run_summary.py`) are Python, so a console panel needs its own copies, and Jony and Susan rule on that panel (Table A, A6); found during execution (row 22 report), owner 2026-10-07.
  - The precondition above should hold once the wake of 2026-10-08 lands, because that wake is the first live pass of `compact-gardener`; found during execution (row 23 report), owner 2026-10-07.
- **Files touched:**
  - `config/idhazh.json` (`gardener` in `ledger.published`, and the key `"state/compact/gardener/index/": 2064` in `page_weight.payload_ceilings_bytes`. 2,064 is what the rule of `test_every_published_ledger_bounds_its_indexes_at_twice_their_longest` gives for `compact-gardener.json`: twice its longest index, a day index of 45 + 31 = 76 entries that weighs 1,032 bytes at gzip -5, where 17 month entries weigh 374. Not 2,200 as first written; found during execution)
  - `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` (the list of published ledgers, and the sentence that gave every index key 2,200 bytes; the second found during execution)
  - `docs/architecture/publishing/idhazh-gardener.md` (the record is published, and what each of its cells can hold)
  - `TODO/20261004-60-gardener-recovers-on-its-own-plan.md` (this row's line in the Status Reckoner, and decision 2's Authority)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_page_ceilings.py`; `npm --prefix frontend run test:changed -- --list` and the checks it selects; `npm run bundle-gate` from `frontend/`; the browser smoke in [run-the-gates.md](../docs/how-to/run-the-gates.md) on one console page (CLAUDE.md section 12); `doc_load.py` on the two pages. CI: the full suite.
- **Oracle:** `test_every_published_ledger_bounds_its_indexes_at_twice_their_longest` in `backend/tests/contracts/test_page_ceilings.py` fails on a half revert: the ledger published without its key, or the key without the ledger. No new test: this is one config value, and its readers are tested for every published ledger. It cannot settle whether the console shows the notes; that panel is out of scope (Table A, A6).
- **Found during execution:**
  - The key's value comes from the test's own rule, applied to `compact-gardener.json`: 45 + 31 = 76 day entries weigh 1,032 bytes at gzip -5, and 12 + 5 = 17 month entries weigh 374, so the key is 2 x 1,032 = 2,064. Node 24.12.0 and Node 22.23.3, the major CI installs, give the same sizes. With the key at 2,063 the test fails with `assert 2063 >= (2 * 1032)`.
  - Oracle, on this branch: with the ledger published and no key, and with the key and the ledger not published, the test fails at its key-set assertion; with both, `test_page_ceilings.py` passes 9 tests.
  - Column check, ESCALATE trigger 3: none fires. The site serves 31 columns: the 28 of `CollectionPruneRow`, its `version` included, and `ledger`, `covers` and `unit_id` from `RowIdentity`. Each holds a closed word, a count, a flag, a UTC day or instant, the identity of the run that wrote the row, a task's name from `config/gardener/`, or a member. A member (`resume_from`, and each `recovered` note's `subject`) is a UTC period, a path under `state/` that the code names, or the number GitHub gives a workflow run or artifact (`str(raw["id"])` in `github_collections.py`). The name GitHub gives one (`Member.label`) is read by no code and never reaches the row, and `MEMBER_ID_PATTERN` refuses a space, a colon and `?`, so no member can be a web address.
  - The canary holds no gardener row. Its packing writes the ledger's three indexes empty (Rule L), so the canary publishes an empty gardener ledger, and `frontend/tests/published-ledgers.spec.ts`, which plan 62's Table B, B7 says expects all three indexes of every published ledger, finds them.
  - No question in `explorer_examples` in `config/appearance.json` reads the gardener ledger, so the smoke typed one. An example question is a console change, for Jony and Susan with the panel (Table A, A6).
  - The site build stages the raw days after each published ledger's newest packed day, and no browser reads them. `frontend/vite.config.ts` bakes `__RAW_LISTED_THROUGH__` from `rawListedThrough()` in `frontend/scripts/raw-listed-through.mjs`, whose default folder, `frontend/static`, is read from the build's working folder, `frontend/`, so every build bakes `{}`: this branch's client bundle holds `var br={}`. The smoke's explorer read the 7 packed days, 169 rows, asked for none of the 12 raw files of 7 and 8 October, and said it read through 8 October. It predates this row (plan 55 row 2, #1201) and lies outside its files, so it is not fixed here: a Level 2 row resolves the default from the module's own address, with a test that reads the baked value. Plan 62's row L46, "The site build bakes the raw days the data explorer may read", fixed it in #1427 (merged 2026-10-08).
  - `how-the-query-door-answers-a-panel.md` names `backend/tests/contracts/test_published_ledgers_cover_the_panels.py`, which #1228 deleted, and gives the registry key 3,200 bytes, where `config/idhazh.json` sets 3,400. Neither is changed here.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Publish the existing ledger through the existing door; no new payload | Fowler review, 2026-10-04 |
| 2 | Dispatch waits until the gardener's indexes are on main | Fowler review, 2026-10-04. It held at dispatch: the first live pass of `compact-gardener` ran in gardener run 37738488838 at 06:35 UTC on 2026-10-08, and `state/compact/gardener/index/daily.json`, `monthly.json` and `yearly.json` were on `origin/main` at 7a9361d69, `daily.json` holding 7 packed days, 2026-09-30 to 2026-10-06, 169 rows (plan owner, 2026-10-08) |

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
  - `docs/architecture/publishing/how-the-query-door-answers-a-written-question.md` (found during execution: it owns what the explorer shows for a lost day and how it reads a kept question)
  - `docs/how-to/query-a-ledger-from-the-console.md` (found during execution: how an operator reads a result)
- **Acceptance gates:** local: the two specs above, as `npm --prefix frontend run test:changed -- --list` selects them; `npm --prefix frontend run check` (svelte-check); the browser smoke in [run-the-gates.md](../docs/how-to/run-the-gates.md) on the data explorer, with a count by day across a lost day (CLAUDE.md section 12). CI: the full suite.
- **Oracle:** in the browser, a count by day across a lost day draws its line in two segments, not one, and a saved question or recent run stored with the day `2026-08-32` is refused when the page reads browser storage. Each case fails on today's main. It cannot settle how the gap looks; Jony and Susan rule on that only if two layouts lead to different code.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Break the line at a lost day, in a change separate from row 31 | Jony, through row 31's report, 2026-10-04 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Draw the lost day as zero | It would show a lost day as a quiet day | Nothing to build | The owner, 2026-10-04 (row 8, decision 3) |

### Row #33 - A log line never quotes a ledger row's values

- **Scope:** `backend/idhazh/ledger/ledger_files.py` (lines 377 and 453) and `backend/idhazh/ledger/raw_files.py`'s `_skip` (called at lines 173 and 308 in row 21's report) all log a malformed file's refusal reason as `logger.warning("... reason=%s", ..., reason)`. The one place that reason is built is `backend/idhazh/ledger/persist.py`'s `load_stored`, whose `except ValidationError` wrap embedded pydantic's `ValidationError.__str__()` whole - which quotes each failing field's `input_value`, so a corrupted cell holding fetched text (an article's title or address) reached a log line through any of the three call sites. Row 21 removed three gardener sources of the same kind; this leak predates it and row 21 did not touch the ledger package. The fix is at the one raise site: `load_stored` now builds its `ValueError` from a new `_refusal_facts` helper that keeps only each failing field's dotted `loc` (filtered to a name `RowIdentity` or the contract model declares, else `?`) and its pydantic error `type`, capped at the first 5 with the total shown only when truncated - never `msg`, `input`, `ctx` or `url`. The three existing catch sites need no code change: the `ValueError` they already log is sanitized before they see it. Level 2 (log content changes for the gardener and the daily run, which share the ledger package).
- **Files touched:**
  - `backend/idhazh/ledger/persist.py` (`_refusal_facts`, `_REFUSAL_FIELDS_SHOWN`, `load_stored`'s except-block and docstring invariant)
  - `backend/tests/ledger/test_persist.py` (`_row_rewritten`; the row's own value never reaching the message, the 5-field cap with a total shown, an unlisted nested-model key shown as `?`)
  - `backend/tests/ledger/test_ledger_files.py` (`_row_rewritten`; the raw-file warning at line 377 and the compact-file warning at line 453, each end to end through `load_visual_prunes` / `load_days`)
  - `backend/tests/ledger/test_raw_files.py` (`_row_rewritten`; `_skip`'s risky caller, `load_current_rows`, end to end)
- **Follow-ups:**
  - `backend/idhazh/ledger/headers.py`'s `_refile()` helper (inside `migrate_header`, around line 99) builds `f"line {number} has {len(cells)} cells and cannot be read: {exc}"`, the same unsanitized pattern. Reachable only through the operator CLI `backend/utilities/widen_ledger_header.py`, which `print()`s rather than logs, on operator-typed input - out of this row's scope (a log line, not an operator's own prompt), but the same fix shape applies: keep `"line N has K cells"`, replace `{exc}` with `type(exc).__name__`. Found during execution, Fowler's ruling, 2026-10-07.
  - `backend/idhazh/ledger/persist.py`'s `render_renamed` (around line 622) carries an identical unsanitized `{refusal}` pattern. It has no caller anywhere in the repository and no test coverage, so it is not a log line today - nothing calls it and nothing logs what it would raise. The same fix is needed before any future caller wires it up. Found during execution, not fixed here (untested, unreachable code with no oracle), 2026-10-07.
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe backend\utilities\gate_lock.py -- python -m pytest -n 0 backend/tests/ledger/` (191 passed); `.\.venv\Scripts\python.exe -m ruff check backend/idhazh/ledger/persist.py backend/tests/ledger/test_persist.py backend/tests/ledger/test_ledger_files.py backend/tests/ledger/test_raw_files.py`; `.\.venv\Scripts\python.exe -m mypy` on the same four files. `npm --prefix frontend run test:changed -- --list` selects nothing (no frontend file touched). CI: the full suite.
- **Oracle:** a ledger file whose one row carries a marker string in a field the contract refuses (`payload_bytes_before` set to a non-numeric string) fails to load, read through each of the four call sites above (`load_stored` directly, the raw-day and compact-day paths in `ledger_files.py`, and `raw_files.py`'s `_skip`); the marker appears nowhere in the raised message or the captured log, and the failing field's name with its error kind does appear. Run in a copy of the base commit (`b421b0e4b`, `git archive` into `%TEMP%\plan60row33-base-commit`, this branch's four new test files copied in), all four new tests fail - the marker is quoted inside the pydantic `ValidationError` text each one captures. On this branch, the same four tests pass.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row exists: a malformed ledger file's fetched text can reach a log line through the ledger package's three skip/refusal warnings, the leak predates row 21 and row 21 did not touch it, so it is ESCALATE trigger 3 work needing its own row | Plan owner, 2026-10-07 (ESCALATE trigger 3, row 21 report) |
| 2 | Keep the file path plus, per failing field, its dotted `loc` (filtered to a declared name or a list index, else `?`) and its pydantic error `type`; cap at 5 entries with the total shown only when truncated; drop `input`, `msg`, `ctx` and `url` entirely - `msg` is not closed, since a custom validator's message can echo the input | Fowler, 2026-10-07 |
| 3 | Fix the one raise site, `persist.load_stored`'s `except ValidationError` wrap, with an Extract Function helper; the three existing `logger.warning` call sites need zero code changes, and `load_stored`'s docstring gains the invariant that every `ValueError` it raises names closed facts only | Fowler, 2026-10-07 |
| 4 | Do not duplicate or move row 21's `cause_of` into `idhazh.ledger`: the ledger package owns exactly one raise site, not a traceback-walking problem like the gardener's, and "two consumers do not earn a shared module; three would" | Fowler, 2026-10-07 |
| 5 | Defer `headers.py`'s `_refile()` leak to a Follow-up rather than fixing it here; it is reachable only through an operator CLI that `print()`s, not `logging`, on operator-typed input | Fowler, 2026-10-07 |
| 6 | Raise `load_stored`'s `ValueError` `from None` instead of `from refusal`: raised `from refusal`, the original `ValidationError` survives as `__cause__` and `traceback.format_exception` prints it whole, so an uncaught crash or a future `logger.exception` call would still quote the row's value even though the three warnings that format with `%s` never saw it; no caller reads `__cause__`/`__context__` on this exception, so suppressing it costs nothing | Plan owner, 2026-10-07 (pre-merge review of #1393) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Fix each of the three `logger.warning` call sites to sanitize `reason` before logging it | The leak is in what `reason` already is by the time any of the three sees it; fixing three call sites for one root cause is three places to keep in step instead of one | Three call-site edits instead of one helper | Fowler, 2026-10-07 |
| 2 | Keep the exception's type name in the outer message, beside the per-field facts | Redundant: a reader asking what kind of file problem this is already gets it per field, and the file name plus "a row this build refuses" already says it is a validation refusal | Nothing to build; a slightly longer line that repeats itself | Fowler, 2026-10-07 |
| 3 | Reuse row 21's `Cause` / `cause_of` / `LoggedText` shapes from `idhazh.gardener.event_log` | `idhazh.gardener` depends on `idhazh.ledger`, never the reverse (CLAUDE.md section 4); importing gardener code from ledger code would invert the dependency | A layering violation the gates would catch | Fowler, 2026-10-07 |
| 4 | Fix `render_renamed`'s identical pattern in this row | It is dead code: no caller anywhere in the repository and no test exercises it, so there is no oracle to prove a fix correct or to prove the leak exists today | Removing or fixing untested code with nothing to validate the change | Fowler, 2026-10-07 |

### Row #34 - A gardener crash prints where it broke, never the error's text

- **Scope:** When an exception ends a program that `.github/workflows/idhazh-gardener.yml` runs - `gardener_shards.py`, `gardener_publish.py`, `corpus_squash_due.py` or `corpus_history.py`, all under `backend/utilities/` - the trace in the job's log names the exception and each exception chained to it by its type, and each frame by its module and line, and never a message, an argument or a local, and the exit code stays Python's own; `corpus_history.py` prints the same trace for a run it cannot record, then exits 2. Level 2.
- **Follow-ups:**
  - Three other entry points run gardener code outside this workflow and are left as they are (owner's scope, 2026-10-07): `idhazh gardener list-tasks | plan-shards | run-task` (`backend/idhazh/gardener/cli.py`, through the `idhazh` console script in `backend/idhazh/cli.py`); `idhazh telemetry prune`, which runs `one_at_a_time.take` (`backend/idhazh/telemetry/prune.py` and `door_prune.py`); and the ledger migrator, `backend/utilities/migrate_to_parquet.py`, which packs through the compaction task (`backend/utilities/ledger_migration/packing.py`). A crash in any of them still prints Python's own trace, text included. Covering them is a Level 2 row; for the two `idhazh` commands the printer must be reachable from the package, which imports nothing from `backend/utilities/`. Found during execution, 2026-10-07.
  - A refusal a program prints on purpose keeps its words. Those that quote an exception's text quote a config file of this repository (`gardener_publish.py`'s config refusal, and `corpus_history.py`'s "nothing was rewritten"), git about this repository's own history (`corpus_history.py`'s "nothing was pushed"), or the squash's own declaration and stamp (`corpus_squash_due.py`). None carries fetched text, so none is ESCALATE trigger 3. Found during execution, 2026-10-07.
  - `gardener_shards.py` raises its three refusals of `config/idhazh_gardener.json` - task names that are not a list of slugs, a task named twice, a declaration missing - as `ValueError` from `main`, so the plan job's log now names the type and the line that raised, not the sentence. Ending each on `SystemExit` with its sentence, as the planner's `_key` refusal already does, gives the words back: a Level 1 row, if wanted. Found during execution, 2026-10-07.
  - The base-commit copy in `docs/how-to/run-the-gates.md` archives `backend`, `config`, `tests` and `pyproject.toml`, so a copied test that reads a workflow fails there on a missing `.github` file, a failure the base did not cause. This row added `.github` to its copy; one sentence in that section would say so. Found during execution, 2026-10-07.
- **Files touched:**
  - `backend/utilities/crash_trace.py` (new; first sentence "What does a gardener program print when an exception ends it?")
  - `backend/utilities/gardener_shards.py` (its `__main__` block installs the trace)
  - `backend/utilities/gardener_publish.py` (its `__main__` block installs the trace; the docstring says what a crash prints)
  - `backend/utilities/corpus_squash_due.py` (its `__main__` block installs the trace)
  - `backend/utilities/corpus_history.py` (its `__main__` block installs the trace; a run it cannot record prints it in place of `traceback.print_exc()`; the docstring)
  - `backend/tests/workflows/test_crash_trace.py` (new)
  - `backend/tests/workflows/test_gardener_crash_trace.py` (new)
  - `backend/tests/workflows/_harness.py` (`GARDENER_SHARD_MODULE` and `CRASH_TRACE_MODULE`)
  - `backend/tests/workflows/test_stdlib_only_programs.py` (the trace is held to the standard library)
  - `backend/tests/contracts/test_gardener_plan.py` (the bare run holds the trace beside the planner, as the plan job's checkout does)
  - `backend/tests/gardener/test_corpus_history.py` (a run it cannot record)
  - `docs/architecture/publishing/idhazh-gardener.md` (what a crash prints, under "What a shard logs", and a design rationale entry)
- **Acceptance gates:** local: `npm --prefix frontend run test:changed -- --list` selects the full suite, because every `backend/utilities/` file and `_harness.py` count as shared input, so CI runs it. `-n 0` on the five test modules this row adds or changes: 56 passed. `-n 4` on the publisher's, runner's and workflow's existing tests (`test_publish.py`, `test_runner.py`, `test_run_summary.py`, `test_cli.py`, `test_sparse_shard.py`, `test_gardener_workflow.py`, `test_corpus_squash_due.py`, `test_prune_push.py`, `test_staged_paths.py`, `test_gardener_plan_matrix.py`, `test_corpus_meta.py`): 164 passed. `ruff check .` and `mypy` clean; `doc_load.py` on the two pages. CI: the full suite.
- **Oracle:** `test_gardener_crash_trace.py`. For each of the four programs, a driver raises `LookupError` carrying planted text and, while it handles that one, runs the program with `runpy` as `__main__` on real input its own code cannot read: a config folder with no `idhazh_gardener.json`, or for the due check a stamp that is a folder, at a path that carries the planted text. So the exception that ends the program quotes it, and so does the exception chained to it. On this branch each run exits 1, every line of its trace is a header, a `module:line` frame, a linking sentence, a type or a blank, the program's own `main()` call is a frame, the type that ended it is the last line, and the planted text is in neither stdout nor stderr. Run in a copy of the base commit 55045f5d7 under the long form of `TEMP`, with this row's six test files copied in: the four cases fail, because Python's own trace prints the planted text twice, in the `LookupError` line and in the path of the error that ended the program; the new case in `test_corpus_history.py` fails, because `traceback.print_exc()` prints pydantic's error, which quotes `input_value='Breaking: click https://example.invalid/now'`; `test_crash_trace.py` fails at import; the two cases that read `crash_trace.py` fail because it is absent; and the workflow test passes, because the workflow did not change. It cannot settle an exception raised while a program imports its own modules, before it installs the trace; nothing those imports run reads fetched text.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row exists: when an exception escapes a gardener entry point that `idhazh-gardener.yml` runs, the top level prints, for the exception and each chained cause, its type and each frame's module and line, never a message, an argument or a local, and then exits with the same non-zero code as today | Plan owner, 2026-10-07 (ESCALATE trigger 3, row 22 report) |
| 2 | The form keeps the stack, which was the reason to keep the traceback: Python's own layout, each frame as `module:line`, the form an event's `where` takes, and no function name, because a module and a line at the commit the job checked out point to exactly one line | Fowler, 2026-10-07 (row 34 worker's consult) |
| 3 | The printer never raises: a module's name is read only when it is a plain string, else `?`, pinned by an exception raised inside `exec(code, {})`. A printer that raised would make Python print its own trace of the crash, text included (Fowler measured it, Windows, Python 3.14.2) | Fowler, 2026-10-07 (row 34 worker's consult) |
| 4 | `sys.excepthook`, installed in each program's `__main__` block before its `main`, so the interpreter still picks the exit code: 1 for an exception, and an interrupt's own code, with or without the hook (measured 2026-10-07, Windows, Python 3.14.2). A `SystemExit` refusal never reaches it and keeps its words | Fowler, 2026-10-07 (row 34 worker's consult) |
| 5 | The printer is `backend/utilities/crash_trace.py`, the standard library alone, imported inside each `__main__` block once `backend/` is on `sys.path`, and named in `STANDALONE_PROGRAMS`. It crosses no CLAUDE.md section 4 boundary, and it is the one place all four programs reach: the plan job checks out only `config` and `backend/utilities`, and two of the programs run before any install | Fowler, 2026-10-07 (row 34 worker's consult) |
| 6 | `corpus_history.py`'s `traceback.print_exc()`, for a run it cannot record, prints the same trace in this row, because it put the same text into the same job's log. The test plants its text in `prompt_digest`, because the due check stops the job on a `last_run` that is not a day before the squash runs | Fowler, 2026-10-07 (row 34 worker's consult) |
| 7 | The oracle's chained exception comes from a driver that raises one and, while handling it, runs the program on real input, so nothing is replaced (Guardrail #7). It finds the program's own `main()` frame by its line in the program file, because the driver's frames are `__main__` too, and runs the plan and due programs with `-I -S`, because without `-S` the editable install would put `backend/` on the path and hide a wrong path entry | Fowler, 2026-10-07 (row 34 worker's consult) |
| 8 | A test holds the four programs to every command in `idhazh-gardener.yml` that starts Python - `python`, `python3` or the `idhazh` console script - so a fifth cannot land without a crash case | Fowler, 2026-10-07 (row 34 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep Python's full traceback (Fowler's first recommendation, row 22) | It prints every message of the chain, and one can quote what GitHub's API or a file returned: ESCALATE trigger 3 | Nothing to build; the text stays in the log of all four programs | Plan owner, 2026-10-07 |
| 2 | Print nothing for a crash, or only its type | A crash has passed every task's own handling, so the fault is in the runner or a program, and the frames are what a person needs to find it | Less than this row: one hook that prints a line. It gives up every frame, and three of the four programs log no event that names even one place | Plan owner, 2026-10-07 |
| 3 | The printer in `backend/idhazh/` | The plan job checks out only `config` and `backend/utilities` and installs nothing | Widening that job's checkout to the package, and a path entry all the same | Fowler, 2026-10-07 (row 34 worker's consult) |
| 4 | Import the printer at module top, as `commit_and_push.py` imports its sibling | Three programs are held to standard-library imports at module scope, and a test that imports a program would put `backend/` on its path | One rule widened in `test_stdlib_only_programs.py` | Fowler, 2026-10-07 (row 34 worker's consult) |

### Row #35 - The yearly expiry logs an event of its own

- **Scope:** The yearly expiry says what it chose as an event declared in `backend/idhazh/contracts/gardener_events.py`, as row 21 made every other gardener line, instead of a line of text that the handler wraps as `logged-text` (Table E, E15). Level 1.
- **The line** (row 23's Found during execution, 2026-10-07): `backend/idhazh/gardener/tasks/_yearly_expiry.py`, which #1382 added after row 21, logs `yearly expiry ledger=<ledger> years=[...]` at `info` on every pass of a ledger that sets `yearly_prune_enable` and `yearly_keep_months`, also when no year is due. Since #1382 every compaction sets both, apart from the `compact-trial-*` declarations that #1405 added later, so every other compaction pass logs it, and Table E has no event for it. It carries a ledger's name and UTC years, and no fetched text. A pass whose operator range would skip an earlier indexed year logs the module's other line instead, at `error`, and that line is text too.
- **Files touched** (from a search on `origin/main` at 7ba988fc2 for `_yearly_expiry`, the two lines' words and the helpers that read events; search again at dispatch, after decision 2):
  - `backend/idhazh/gardener/tasks/_yearly_expiry.py` (the `info` line on every pass, and the `error` line for a range that skips an earlier indexed year)
  - `backend/idhazh/contracts/gardener_events.py` (the new model; `CompactionStep` names no expiry step, and `PeriodsTaken` holds no expired year)
  - `backend/tests/gardener/tasks/test_yearly_expiry.py` (reads the event off the record with `backend/tests/gardener/_events.py`)
  - `docs/architecture/publishing/idhazh-gardener.md` (the table of events under "What a shard logs")
  - `docs/architecture/publishing/ledger-compaction.md` ("Yearly expiry", which names no event)
  - Read, no change: `backend/idhazh/gardener/tasks/compaction.py`, which runs the expiry before it emits `periods-chosen`; `backend/idhazh/gardener/event_log.py`, whose `emit` writes an event and whose handler wraps a line of text as `logged-text`; `backend/idhazh/gardener/tasks/_compact_tree.py`, whose `refuse` the range refusal now calls (found during execution)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/tasks/test_yearly_expiry.py`; ruff; mypy; `doc_load.py` on the two pages. CI: the full suite.
- **Oracle:** in `test_yearly_expiry.py`, on a tree the test builds under `tmp_path`: a pass at 2030-01-01 UTC over an indexed 2026 logs the new event once, with 2026 as the year it chose, and no `logged-text` line from `idhazh.gardener.tasks._yearly_expiry`. On `origin/main` the same pass logs one `logged-text` line whose message starts `yearly expiry ledger=`, which is what lets this check fail. It cannot settle how a person reads the event in GitHub's log viewer; row 22's summary is the view for a person.
- **Found during execution:**
  - At dispatch, on `origin/main` at f4faa94f4, the files above held, and `_compact_tree.py` is read for `refuse`. No open pull request touched `_yearly_expiry.py` or `gardener_events.py`; #1352, the one open change to `ledger-compaction.md`, edits only its introduction.
  - No test covered the range refusal before this row; the new test is its first. On the base it ended the pass `failed` with no fault word, so a person's range turned the job red. It now ends `deferred` with `range-starts-late`, and the job stays green (decision 8).
  - An expired year reaches no summary (decision 7). `PeriodsTaken` lists no expired year and the job summary counts none, so a live pass whose only work is to expire a year ends `done`, and its summary says it did nothing, although it deleted that year's files. Proposed row (Fowler): "`PeriodsTaken` gains `years_expired`, and the job summary counts it, so a pass whose only work is an expired year no longer says it did nothing." All 14 committed declarations that switch the expiry on keep years 36 months, so no year expires before 2030-01-01 UTC, and the row has until then.
  - Oracle on the base commit f4faa94f4, in a copy outside this checkout: the changed `test_yearly_expiry.py` fails at import, because `ExpiredYearsChosen` is absent. A probe drove the base code through the oracle's pass with the base's own test helpers: it logged one record with no event, which the handler writes as `{"event":"logged-text",...,"level":"info","logger":"idhazh.gardener.tasks._yearly_expiry","message":"yearly expiry ledger=visual-prunes years=['2026']"}`. Its range case logged one `error` record of text, "yearly expiry range skips an earlier indexed year ledger=visual-prunes year=2026", and no `period-refused`. On this branch the same pass logs one `expired-years-chosen` event with `["2026"]` and no text, and the range case logs one `period-refused` at `warning`, with `expire-years`, 2026 and `range-starts-late`, and ends `deferred`. The range case as decision 8 has it fails on this branch's first head, 2694d8cc3, whose pass ended `failed` with `raised`, and passes after the change.
  - The canary build runs the expiry: it packs the published ledgers and `feed-health` through `compaction.run` under their declarations, which all switch it on, and no year is due on its day, 2026-08-22. Built on the base and on this branch, each in a copy, through the gate lock, its `state/` holds 45 files on both: 28 byte-identical, among them 24 indexes with 89 entries; 16 packed files whose 155 rows are identical and whose only differing keys are the write clocks `file_id` and `written_at_ms`; and one raw item-health file whose name holds its write time, with its one row identical. The site build at the end stops on both after `state/` is complete, because neither copy has `frontend/node_modules` or git history.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The event is `ExpiredYearsChosen`, whose line is `expired-years-chosen`, with two fields: `ledger`, and `years`, the expired indexed UTC years the pass takes, oldest first, at most `max_periods_per_run` and only whole years inside an operator range. A live pass deletes each year's files and its entry; a dry run only names them, so the name says what was chosen, never that anything is gone (row 2). It is emitted where the `info` line was, after the range check and the cap and before any delete, at `info`, and the module's logger goes. No other field: `task-planned` carries the knobs, `dry_run` and the range, and `task-finished` the stop. Not a field on `PeriodsChosen`: the expiry chooses and acts before `choose` runs, so its choice would have to move into `_compaction_periods`. Fowler's second reason, that `StepChoice` cannot hold B0's `failed` stop, fell with decision 8 | Fowler, 2026-10-07 (row 35 worker's consult) |
| 2 | Before dispatch, ask the session that wrote #1382, the ledger-retention-policy session, whether it is still changing `_yearly_expiry.py` | Plan owner, 2026-10-07: the #1382 session is archived; no open PR touches the module |
| 3 | The plan owner adds the event to Table E (section 2.5) when the row lands, as for rows 21 and 22 | Plan owner, 2026-10-07 |
| 4 | Level 1: one line of text becomes one event, and it carries no fetched text, so it is not ESCALATE trigger 3 | Plan owner, 2026-10-07 |
| 5 | A pass with no year due logs the event with `years: []`, as `window-chosen` and `periods-chosen` are logged on every pass, so the line still fires when the text line did. A declaration without both knobs logs neither line, and a pass the range refuses logs `period-refused` instead | Fowler, 2026-10-07 (row 35 worker's consult) |
| 6 | The range refusal is `period-refused`, through `CompactTree.refuse`, with the new step word `expire-years`, declared first in `CompactionStep` because it is step 0 (Table B, B0). `CompactionStep` is read only by events, so its new word is not ESCALATE trigger 1. Fowler also ruled the fault `raised`, which kept B0's `failed` as #1382 wrote it; decision 8 replaced that part | Fowler, 2026-10-07 (row 35 worker's consult) |
| 7 | Expired years in `PeriodsTaken` (Table E, E4) and in the job summary stay out of this row: the summary's words are Reader's, so that is a Level 2 row of its own (Found during execution) | Fowler, 2026-10-07 (row 35 worker's consult) |
| 8 | The range refusal ends `deferred` with the fault `range-starts-late`, not `failed` with `raised`. An operator-range refusal is not a code defect: it gets a fault word of its own and does not turn the job red, and row 20 applied that to every other step. B0's `failed` came from #1382, which predates that rule's reach, so B0 changes, not the rule. The record's `fault` is `range-starts-late`, the `period-refused` event is a warning, `next` is `report.WHY[range-starts-late]`, the task ends `deferred`, and the shard's exit code stays 0; nothing is deleted, and `resume_from` stays the oldest indexed year | Plan owner, 2026-10-08, from the owner's ruling of 2026-10-04 (row 20's follow-up) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | Each compaction pass that sets the expiry writes a line that no test reads by its fields, against row 21's rule that every gardener line is one event | Nothing to build; one line of text on each such pass | Plan owner, 2026-10-07 (row 23 report) |
| 2 | Name the event `years-expired` | A dry run takes the same years and deletes none, and a line that says they expired would say something is gone (row 2) | Nothing | Fowler, 2026-10-07 (row 35 worker's consult) |
| 3 | The expiry's choice as a field of `PeriodsChosen` | The expiry chooses and acts before `choose` runs, so the field would move code and change a contract this row does not own. The second reason, that `StepChoice` cannot hold a `failed` stop, fell with decision 8: a `deferred` stop with no span is one `StepChoice` holds | Moving the expiry's choice into `_compaction_periods` and a new kind of `StepChoice` | Fowler, 2026-10-07 (row 35 worker's consult) |
| 4 | End the range refusal `failed`, with the fault `raised`, as #1382 wrote B0 and as Fowler first ruled | A person's range is not a code defect, so it would turn the job red for a range a person widens; every other step's range refusal ends `deferred` with `range-starts-late` (the owner's ruling of 2026-10-04, row 20's follow-up) | Nothing to build: it was this row's first head, 2694d8cc3 | Plan owner, 2026-10-08 |

### Row #36 - The plan job's config refusals keep their sentence

- **Scope:** `backend/utilities/gardener_shards.py` ends each of its three refusals of `config/idhazh_gardener.json` on `SystemExit` with its sentence, instead of raising `ValueError`, so the plan job's log prints the sentence, which row 34's printer leaves as written. Level 1.
- **The refusals** (row 34's Follow-ups, 2026-10-07): since row 34 (#1404), an exception that ends the planner prints only its type and each frame's `module:line`. `declarations` raises three refusals as `ValueError`, so the plan job's log names `ValueError` and the line that raised it, not which refusal it was. A `SystemExit` never reaches the printer and keeps its words (row 34, decision 4), as the planner's own `_key` refusal already shows. Each sentence quotes only this repository's config, so none carries fetched text. The three raise sites, in `declarations` on `origin/main` at 7ba988fc2:
  1. `task_names` that is not a list of slugs: `config/idhazh_gardener.json task_names must be a list of task slugs` (line 64).
  2. A task named twice: `config/idhazh_gardener.json task_names repeats a task` (line 66).
  3. A named declaration that is missing: `config/gardener/<name>.json is missing`, where the name has already matched the slug pattern (line 69).
- **Files touched** (from a search on `origin/main` at 7ba988fc2 for the three sentences, `gardener_shards` and `declarations`; search again at dispatch):
  - `backend/utilities/gardener_shards.py` (`declarations`, its three `raise ValueError`)
  - `backend/tests/contracts/test_gardener_plan.py` (`test_both_loaders_refuse_bad_named_lists` expects `ValueError` from `gardener_shards.plan` for a missing declaration and a repeated task)
  - Read, no change: `backend/idhazh/config.py` and `backend/idhazh/contracts/knobs/gardener.py`, the typed loader's matching refusals; `backend/idhazh/gardener/cli.py`, whose `settings_or_none` catches them and prints their sentence; `backend/tests/workflows/test_gardener_workflow.py`, which calls `declarations` and `plan` only on configs that load; `docs/architecture/publishing/idhazh-gardener.md`, whose sentence that a refusal a program ends on with a sentence of its own keeps its words already covers these three
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_gardener_plan.py`; ruff; mypy. CI: the full suite.
- **Oracle:** in `test_gardener_plan.py`, on a config the test builds under `tmp_path`, one for each refusal: the planner, run as the plan job runs it (`-I -S`, in a bare folder beside `crash_trace.py`, as `test_the_script_runs_with_the_standard_library_alone` does), exits 1, prints that refusal's sentence on stderr and prints no `Traceback` line, and `test_both_loaders_refuse_bad_named_lists` still holds both loaders to the same words. On `origin/main` the run prints the trace of a `ValueError` and no sentence, which is what lets this check fail. It cannot settle a config that is not JSON or names no `task_names`: each still ends as a crash, which prints its type and line and no sentence.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each refusal ends on `SystemExit` with its sentence, as `_key` already does: the sentence quotes only this repository's config, so it is not ESCALATE trigger 3, and the exit code stays 1 | Plan owner, 2026-10-07 (row 34 report) |
| 2 | The typed loader keeps `ValueError`: it does not run in the plan job, and `idhazh gardener` catches it and prints its sentence | Plan owner, 2026-10-07 |
| 3 | Level 1: three raise sites in one program, and a wrong version is obvious and local | Plan owner, 2026-10-07 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The plan job's log names `ValueError` and a line, so a person opens the source at that line to learn which of three refusals stopped the plan | Nothing to build | Plan owner, 2026-10-07 (row 34 report) |
| 2 | Let row 34's printer print a `ValueError`'s message when the planner itself raised it | The printer would have to tell the program's own `ValueError` from one that quotes a file or an API answer, the line row 34 drew at never printing a message (row 34, decision 1) | A rule in `backend/utilities/crash_trace.py` and its tests | Plan owner, 2026-10-07 |

### Row #37 - Operator gardener commands print where they broke, never the error's text

- **Scope:** When an exception ends `idhazh gardener list-tasks`, `plan-shards` or `run-task`, `idhazh telemetry prune`, or the ledger migrator, the trace names each exception by its type and each frame by its module and line, never a message, as row 34 made it for the four programs the gardener workflow runs. Level 2.
- **The entry points** (row 34's Follow-ups, 2026-10-07): no workflow runs them; each runs when a person or an agent starts it. `run-task`, the prune and the migrator run gardener code that reads ledger rows or GitHub's answers, and `list-tasks` and `plan-shards` share `run-task`'s `main`. A crash in any of them still prints Python's own trace, text included. For the two `idhazh` commands the printer, `backend/utilities/crash_trace.py`, must be reachable from the package, which imports nothing from `backend/utilities/` on `origin/main` at 7ba988fc2.
  1. `idhazh gardener list-tasks | plan-shards | run-task`: one `main` in `backend/idhazh/gardener/cli.py`, reached through the `idhazh` console script, `main` in `backend/idhazh/cli.py`.
  2. `idhazh telemetry prune`: `main` in `backend/idhazh/telemetry/cli.py`, which runs `one_at_a_time.take` through `backend/idhazh/telemetry/prune.py` and `backend/idhazh/telemetry/door_prune.py`.
  3. The ledger migrator, `backend/utilities/migrate_to_parquet.py`, which packs through the compaction task (`backend/utilities/ledger_migration/packing.py`).
- **Files touched** (from a search on `origin/main` at 7ba988fc2 for the entry points' `main`, `crash_trace` and `CRASH_TRACE_MODULE`; searched again at dispatch on 124be54be):
  - `backend/idhazh/cli.py` (read, no change: the hand-over stays unread, decision 6)
  - `backend/idhazh/gardener/cli.py` (`main`, for `list-tasks`, `plan-shards` and `run-task`, installs the printer first)
  - `backend/idhazh/telemetry/cli.py` (`main` installs the printer for `prune` alone)
  - `backend/utilities/migrate_to_parquet.py` (its `__main__` block)
  - `backend/utilities/crash_trace.py`, moved unchanged to `backend/idhazh/crash_trace.py` (decision 1); its docstring names the commands
  - `backend/tests/workflows/test_crash_trace.py` (imports the printer from `idhazh`)
  - `backend/tests/workflows/test_gardener_crash_trace.py` (row 34's crash cases, beside which this row's go)
  - `backend/tests/workflows/test_stdlib_only_programs.py` and `backend/tests/workflows/_harness.py` (`CRASH_TRACE_MODULE` names the new path; `PACKAGE_INIT_MODULE` holds `backend/idhazh/__init__.py` to the standard library; a relative import counts as outside it)
  - `docs/architecture/publishing/idhazh-gardener.md` (under "What a shard logs", the paragraph on what a crash prints, and its Design rationale entry)
  - The printer moved, so: `backend/utilities/gardener_shards.py`, `backend/utilities/gardener_publish.py`, `backend/utilities/corpus_squash_due.py` and `backend/utilities/corpus_history.py`, whose `__main__` blocks import it, and `backend/tests/contracts/test_gardener_plan.py`, whose bare run copies the package's `__init__.py` and `crash_trace.py` beside the planner
  - `.github/workflows/idhazh-gardener.yml` (the plan job's sparse checkout gains `backend/idhazh`, decision 1; found during execution)
  - `backend/tests/workflows/test_gardener_workflow.py` (read, no change: `test_the_plan_jobs_checkout_holds_every_folder_its_reader_opens` failed on files under `backend/idhazh/` before the workflow line and passes with it; found during execution)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0` on the test modules this row changes; ruff; mypy; `doc_load.py` on the page. CI: the full suite.
- **Oracle:** in `test_gardener_crash_trace.py`, built as row 34's oracle is (row 34, decision 7): for `idhazh gardener run-task`, whose `main` the other two subcommands share, for `idhazh telemetry prune` and for the migrator, a run on real input the test builds that the command's own code cannot read, at a path that carries planted text, exits 1; every line of its trace is a header, a `module:line` frame, a linking sentence, a type or a blank; and the planted text is in neither stdout nor stderr. On `origin/main` each prints Python's own trace with the planted text, which is what lets this check fail. It cannot settle an exception raised while a command imports its own modules, before the printer is installed.
- **Found during execution:**
  - At dispatch, on `origin/main` at 124be54be, the files above held. One open pull request touches one of them: #1425 changes one line inside the migrator's `main`, away from this row's lines.
  - The workflow file is a file this row did not list. With the printer in the package, the plan job also checks out `backend/idhazh` (decision 1). Fowler accepted that cost to keep one copy, and the plan owner accepted the line on 2026-10-08, so the fallback, rejected option 2, is not needed. Before the line, `test_the_plan_jobs_checkout_holds_every_folder_its_reader_opens` failed on `backend/idhazh/__pycache__/__init__.cpython-314.pyc`, `backend/idhazh/crash_trace.py` and their folder; with it, the test passes.
  - The migrator turns a fault in what it reads into a refusal it prints on purpose, so the first exception real input makes escape is in what it writes: a valid `item-health` CSV day, filed by `--write` into a door that holds a file where that day's folder goes. Making the folder raises `FileExistsError`, which names the path, from `idhazh.atomic_write` under `ledger.persist`, and nothing catches it.
  - The refusals the three commands print on purpose keep their words (decision 3). They quote this repository's config (`idhazh gardener`); a person's arguments, a declaration's `prune_refusal` and any other `ValueError` its pass raises (`idhazh telemetry prune`); and the cells of a CSV row that a read refused (the migrator's `refused` and `not proven` lines). A ledger row holds only this project's own words by its contract, such as `FeedHealthRow.detail`, "Never the response body", so none is ESCALATE trigger 3.
  - Importing `idhazh.cli` and the migrator reads one file that is not code, `config/ledgers.json` (an audit hook, 2026-10-08, Windows, Python 3.14.2), so nothing the commands' imports run reads fetched text, as row 34 found for the workflow programs.
  - Every other `idhazh` verb still prints Python's own trace, including `idhazh telemetry show`, `census`, `publish` and `item`. `idhazh work` handles fetched text directly, so a crash there may print it, because a validation error quotes its input (Fowler; not measured). Covering them is the plan owner's call, as a row of its own; after this row it is one line in the top router. The plan owner sent it to the owner on 2026-10-08 as decision D, under "Waiting on the owner" in section 0.
  - Each command exits 1 for a crash on `main` and on this branch, run as a person runs it on the oracle's inputs: `python -m idhazh` on a copy of 124be54be and on this branch, and the `idhazh` console script on this branch. On `main` each prints Python's own trace, which ends in `FileNotFoundError` naming `<planted>/idhazh_gardener.json` (`run-task`), `<planted>/idhazh.json` (`prune`) or `FileExistsError` naming `<planted>/state/raw/item-health/2026/09/02` (the migrator); on this branch each prints the header, `module:line` frames and the type alone.
  - Checks. `npm --prefix frontend run test:changed -- --list` selects the full suite, because the workflow file, `_harness.py` and every changed `backend/utilities/` file count as shared input, so CI runs it. `-n 0` on nine modules (`test_crash_trace.py`, `test_gardener_crash_trace.py`, `test_stdlib_only_programs.py`, `test_gardener_plan.py`, `test_gardener_workflow.py`, `test_corpus_history.py`, `gardener/test_cli.py`, `test_telemetry_cli.py`, `ledger_migration/test_command.py`): 128 passed on a copy of 124be54be, 129 after the move (the `__init__.py` pin) and 132 at the end (the three new cases). `ruff check .` and `mypy` (723 files) clean. `doc_load.py` on `idhazh-gardener.md`: 17,905 tokens before, 18,264 after, 13 sections, no missing element; no section was added.
  - Oracle on the base commit 124be54be, in a copy outside this checkout under the long form of `TEMP`, with `.github` and this row's five changed test files copied in: 8 failed, 27 passed, 1 error. The three new cases each exit 1 and fail because the planted text is printed; `test_crash_trace.py` fails at import, and the `crash_trace.py` case of the standard-library test and the four bare runs of the planner fail, because the printer is not in the package on the base. On this branch every one passes. On the move's own commit the three new cases fail the same way and the four workflow cases pass.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Fowler rules where the printer lives so that the package can reach it, and where each command installs it (CLAUDE.md section 4). The four workflow programs must still reach it from `backend/utilities/`, because the plan job checks out only `config` and `backend/utilities` and installs nothing (row 34, decision 5). Ruled: the printer moves unchanged into the package, as `backend/idhazh/crash_trace.py`, the standard library alone, and so is `backend/idhazh/__init__.py`, which a test now holds to it. The package imports nothing from `backend/utilities/` and its wheel holds only `backend/idhazh`, so that is the one place both sides reach. The four workflow programs import it from `idhazh` after the same `backend/` path entry, and the plan job's sparse checkout gains `backend/idhazh`: 287 files, 3.77 MB, estimated at a second or two of a job allowed 5 minutes, until the job's own step time replaces the estimate. This replaces row 34's decision 5 and its rejected option 3, whose cost Fowler now accepts to keep one copy, so the reason this decision's second sentence gives no longer holds | Fowler, 2026-10-08 (row 37 worker's consult). The plan owner accepted the plan job's sparse checkout gaining `backend/idhazh` in `.github/workflows/idhazh-gardener.yml` on 2026-10-08: about a second or two of a 5-minute job, for one copy of the printer |
| 2 | The form is row 34's: each exception and each one chained to it by its type, each frame as `module:line`, never a message, an argument or a local, and the exit code stays Python's own (row 34, decisions 2 to 4) | Plan owner, 2026-10-07 |
| 3 | A refusal a command prints on purpose keeps its words, such as the config refusal `settings_or_none` prints in `backend/idhazh/gardener/cli.py`; only an exception that escapes changes what it prints | Plan owner, 2026-10-07 |
| 4 | Level 2: three commands change what a crash prints, and the printer that four workflow programs import may move | Plan owner, 2026-10-07 |
| 5 | Each command installs the printer in its own `main`. `idhazh gardener` installs it as the first statement of `main` in `backend/idhazh/gardener/cli.py`, so its three subcommands share it. `idhazh telemetry` installs it right after `parse_args` when the subcommand is `prune`, before `config.load`, so its other four subcommands keep Python's own trace. The migrator imports it with its other `idhazh` imports and installs it in its `__main__` block before `main()`. Each install line carries its reason in one line. An in-process test that calls one of these lines leaves the hook set in its pytest worker; nothing reads it, and both `main`s already set process-wide logging the same way | Fowler, 2026-10-08 (row 37 worker's consult) |
| 6 | `backend/idhazh/cli.py` and `backend/idhazh/__main__.py` do not change: the top router hands a line over unread | Fowler, 2026-10-08 (row 37 worker's consult) |
| 7 | Two commits: the move, which changes no behaviour, so row 34's crash cases pass unchanged; then the installs, the new cases and the docs | Fowler, 2026-10-08 (row 37 worker's consult) |
| 8 | The oracle runs the two `idhazh` commands through row 34's driver on `backend/idhazh/__main__.py` with `PYTHONPATH=backend`: the console script and `python -m idhazh` both call `idhazh.cli.main()`, and only a driver that wraps the program can chain an exception to it. `--repo-root` and `--state-root` point into the test's folder. The migrator's text is planted in a folder above `--state-dir`, because it prints a root outside the checkout by its last folder name on purpose, and its exception is a real one that escapes, never a planted `raise` | Fowler, 2026-10-08 (row 37 worker's consult) |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | A crash in any of the three prints Python's own trace, and a message in it can quote a ledger row or what GitHub's API returned (Guardrail #11), to whoever ran the command, a person or an agent | Nothing to build | Plan owner, 2026-10-07 (row 34 report) |
| 2 | The printer directly in `backend/`, as `backend/crash_trace.py` | The package would import a file its wheel does not hold unless the build config names it; it adds a third top-level module name; and the plan job would get the file only through git's rule that a sparse checkout also writes the files directly inside each listed folder's parent folders, which no workflow line names | No workflow line; a build-config line, and the checkout test learning that rule. The fallback if the owner refuses the workflow line | Fowler, 2026-10-08 (row 37 worker's consult) |
| 3 | The printer stays in `backend/utilities/` and the package imports it | The package would depend on the tooling that depends on it, and a wheel could not reach the printer | Nothing to move | Fowler, 2026-10-08 (row 37 worker's consult) |
| 4 | The plan job checks out only the two package files | Needs git's other sparse mode, which git's own manual calls deprecated, and a second pattern model in the checkout test | About 3.8 MB less for the plan job | Fowler, 2026-10-08 (row 37 worker's consult) |
| 5 | Install in the top router, where it hands the line over | Tests call the top router too, so it saves nothing, and the router would read a telemetry subcommand name it hands over unread by design | One line in `backend/idhazh/cli.py` | Fowler, 2026-10-08 (row 37 worker's consult) |
| 6 | Install only when `main` reads the process's own command line | Needs option 5's read or a true/false argument into both `main`s, and depends on how the console script calls `main`, which no test pins | A flag no reader needs | Fowler, 2026-10-08 (row 37 worker's consult) |
| 7 | A separate function as the console script's target | Changes the packaging, an existing install keeps the old target until reinstalled, and it would cover every verb, beyond this row | A `pyproject.toml` line and a reinstall | Fowler, 2026-10-08 (row 37 worker's consult) |

### Row #38 - An expired year reaches the job summary

- **Scope:** `PeriodsTaken` gains `years_expired`, the UTC years the yearly expiry took on the pass, or would take on a dry run, and the job summary counts them, so a pass whose only work is an expired year no longer says it did nothing. Level 2.
- **The gap** (row 35's Found during execution; Fowler's proposal, 2026-10-07): `PeriodsTaken` in `backend/idhazh/contracts/gardener_events.py` (Table E, E4) lists no expired year, and the job summary, `backend/idhazh/gardener/run_summary.py`, counts what a compaction did from `PeriodsTaken` alone. So a live pass whose only work is to expire a year ends `done`, and its summary row says "nothing", although the pass deleted that year's files. All 14 committed declarations that switch the expiry on keep years 36 months, so the first year expires on 2030-01-01 UTC, and this row must land before then. `PeriodsTaken` belongs to the `task-finished` log event (E5) and is not persisted: the gardener's record, `CollectionPruneRow` in `backend/idhazh/contracts/collection_prune.py`, has no field that holds it, and `row` in `backend/idhazh/gardener/report.py`, which builds the record, does not read `periods` (checked on `origin/main` at 702b00be7). So the new field is not a persisted-shape change, and neither CLAUDE.md section 11 nor ESCALATE trigger 1 applies.
- **Files touched** (from a search on `origin/main` at 702b00be7 for `PeriodsTaken`, `years_packed`, `periods_taken`, `_periods_work`, `dropped_months` and `_yearly_expiry`; search again at dispatch):
  - `backend/idhazh/contracts/gardener_events.py` (`PeriodsTaken`, which gains `years_expired`)
  - `backend/idhazh/gardener/tasks/_yearly_expiry.py` (`drop` deletes each expired year's files and its entry, and keeps no list of the years it took)
  - `backend/idhazh/gardener/tasks/_compact_tree.py` (`periods_taken` builds `PeriodsTaken` from the indexes the pass read and from the lists the steps keep, such as `dropped_months`; an expired year leaves no entry to compare, so it needs a list of its own)
  - `backend/idhazh/gardener/run_summary.py` (`_periods_work`, the counts in the "What it did" cell, names no expired year, so `_did` says "nothing")
  - `backend/tests/gardener/tasks/test_yearly_expiry.py` (the Oracle)
  - `backend/tests/gardener/test_run_summary.py` (`periods` names every field of `PeriodsTaken`; a case for the summary's words)
  - `backend/tests/gardener/test_event_log.py` (builds a `PeriodsTaken` with every field)
  - `docs/architecture/publishing/idhazh-gardener.md` (under "What a person reads on the job page", what a task did names days, months and years, and no expired year)
  - Read, no change: `backend/idhazh/gardener/runner.py`, whose `_run_compaction_roots` merges each list field of `PeriodsTaken` by name, so a new list joins with no edit; `backend/idhazh/gardener/report.py`, whose `finished` hands `periods` to `TaskFinished`; `backend/idhazh/gardener/one_at_a_time.py`, whose `Pass.periods` carries it; `backend/idhazh/gardener/tasks/compaction.py`, which hands the pass `tree.periods_taken(read)`; `backend/idhazh/gardener/tasks/_monthly_period.py`, whose drop steps fill `dropped_months`, the list a new one copies; `backend/tests/gardener/tasks/test_compaction_years.py`, which reads `years_packed`
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/tasks/test_yearly_expiry.py backend/tests/gardener/test_run_summary.py backend/tests/gardener/test_event_log.py`; ruff; mypy; `doc_load.py` on the page. The sufficiency checks in `docs/concepts/design-system.md` apply to the summary, as for row 22. CI: the full suite.
- **Oracle:** in `test_yearly_expiry.py`, on a tree the test builds under `tmp_path`: a live pass at 2030-01-01 UTC over an indexed 2026 ends `done`, its `task-finished` event lists 2026 in `periods.years_expired`, and the row `run_summary` renders from that event says, in Reader's words, that the pass expired one year, not "nothing"; a dry run over the same tree lists the year the same way, and its row says only that the pass would. On `origin/main` the same pass's `periods` names no expired year and its row says "nothing", which is what lets this check fail. It cannot settle how GitHub draws the summary; the first wake on or after 2030-01-01 UTC shows it.
- **Found during execution:**
  - At dispatch, on `origin/main` at 7df6a74d9, the files above held, and decision 2 held: `CollectionPruneRow` has no field that holds `periods`, and `report.row` reads none.
  - The Oracle's tree holds more than 2026. The marks are worked out from the newest entries, so over an index that names 2026 alone the day step starts at 2027-01-01 and records empty days, and the row would not have said "nothing" on `origin/main`. The tree the test builds also names 2027 and 2028 as empty years, 2029-01 to 2029-10 as empty months, and 2029-11-01 to 2029-12-30 as empty days, so at the 2030-01-01 wake the expiry is the only step with a period to take. The pass runs through `runner.run`, so the `task-finished` event the test reads is the one the runner logs.
  - The dependants (decision 5). `run_summary.py` counts `years_expired` first in the "What it did" cell. `report.finished` hands `periods` to `TaskFinished` whole, so the event carries the new list with no edit. `runner._run_compaction_roots` merges every list field of `PeriodsTaken` by name, so each root's expired years join in order, each year once, with no edit: a year expired under two roots counts once, as a day packed under two roots already does. No committed declaration has both: the three `compact-trial-*` declarations with several roots switch the expiry off.
  - Table E, E4 lists no expired year. It is the plan owner's to update, as for rows 21, 22 and 35.
  - Reader's follow-ups, which can wait until 2030-01-01 and are not this row's: under the table, "done: nothing is left" can read for a moment as "no data is left"; and the dry-run sentence offers `month_deletes_dry_run`, a switch that holds back months only, never a year.
  - Checks. `npm --prefix frontend run test:changed -- --list` selects the full suite, because `gardener_events.py` and `test_yearly_expiry.py` count as shared input, so CI runs it. The row's three test files, `-n 0` through the gate lock: 61 passed before, 65 after (the two Oracle cases and two summary cases). The dependants' modules, `test_runner.py` (whose trial compaction runs `_run_compaction_roots`), `test_report.py`, `tasks/test_compaction.py` and `tasks/test_compaction_years.py`: 124 passed. `ruff check .` and `mypy` (722 files) clean before and after. `doc_load.py` on `idhazh-gardener.md`: about 17,327 tokens before and 17,600 after, 12 sections, no missing element; no section was added.
  - Oracle on the base commit 7df6a74d9, in a copy outside this checkout under the long form of `TEMP`, with this row's three test files copied in and `--continue-on-collection-errors`, because `test_run_summary.py` stops at collection there: its cases build a `PeriodsTaken` with `years_expired`, which the base refuses as an unknown field. 5 failed, 30 passed, 1 error. Both Oracle cases fail for the row's reason: the live pass deletes 2026's file, frees 45 bytes and ends `done`, its `periods` names no expired year, and its row reads "| `compact-visual-prunes` | done | nothing |"; the dry run's row reads "| `compact-visual-prunes` | dry-run | nothing |". The three `test_event_log.py` failures are the same refusal. On this branch every case passes, and the two rows end "deleted 1 expired year" and "would delete 1 expired year".
  - Sufficiency ([design-system.md](../docs/concepts/design-system.md#sufficiency-is-a-gate-not-a-taste)), as for row 22: gates 1, 2 and 5 to 10 have nothing to measure on GitHub's Markdown page. Gate 3 holds: each page the Oracle's passes render has one heading, and `test_every_summary_has_one_heading_and_is_ascii` holds the pages it builds to one. Gate 4 holds: the delete, the one part of a pass nobody can undo, leads its row, and a row that said "nothing" for a pass that deleted a year now says what went.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `PeriodsTaken` gains `years_expired`, and the job summary counts it. Expired years stayed out of row 35 because the summary's words are Reader's, so this is a row of its own | Fowler, 2026-10-07 (row 35, decision 7, and its Found during execution) |
| 2 | Not a persisted-shape change: `PeriodsTaken` belongs to the `task-finished` log event, and the persisted record, `CollectionPruneRow`, holds no `periods` (read in `collection_prune.py` and in `report.row` on `origin/main` at 702b00be7) | Plan owner, 2026-10-08 |
| 3 | Reader chooses the summary's words for an expired year, on a live pass and on a dry run | Reader, 2026-10-08: "deleted 1 expired year" and "deleted 2 expired years" on a live pass, "would delete 1 expired year" on a dry run, first in the "What it did" cell. "Deleted" is the table's word for what is gone for good and "expired" says why, while "expired 1 year" reads as "a year went by" and hides the delete; an empty year counts the same, because the noun is the year, not its file; first, because no later wake can undo it |
| 4 | It lands before 2030-01-01 UTC, the first day any year expires: each of the 14 committed declarations that switch the expiry on keeps years 36 months (counted again on `origin/main` at 702b00be7) | Fowler, 2026-10-07 (row 35's Found during execution); plan owner, 2026-10-08 |
| 5 | Level 2: the job summary and the `task-finished` event already read `PeriodsTaken`, so the dependants to check by name are `run_summary.py`, `report.finished` and `runner._run_compaction_roots` | Plan owner, 2026-10-08 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | From 2030-01-01 UTC, a live pass whose only work is to expire a year ends `done`, and its summary says it did nothing, although it deleted that year's files | Nothing to build, and a summary that hides a delete | Fowler, 2026-10-07 (row 35's Found during execution) |
| 2 | Count the expired years in row 35 | The summary's words are Reader's, and row 35 turned one log line into one event | Row 35 waiting for Reader's words | Fowler, 2026-10-07 (row 35, decision 7) |

### Row #39 - The job summary says plainly when nothing is left and what a dry run holds back

- **Scope:** The job summary's two fixed sentences read plainly: the `done` sentence no longer admits "no data is left" as a second reading, and the `dry-run` sentence, on a pass that would delete a year, names a switch that actually holds that delete back. Level 1.
- **The gap** (row 38's report, Reader, 2026-10-08): two of the fixed sentences in `NEXT`, `backend/idhazh/gardener/report.py`, are shared by every gardener task through `runner.py`'s single call to `report.finished`, so every task that ends `done` or `dry-run` prints them today. (a) `TaskOutcome.DONE`'s sentence, "nothing is left, and the next wake takes what reaches its line by then", can read for a moment as "no data is left", where it means only that nothing has reached its line yet. (b) `TaskOutcome.DRY_RUN`'s sentence offers one switch to make a dry run live, `month_deletes_dry_run: false`, but that switch holds back a month's delete only, never a year's: from 2030-01-01 UTC (row 38), a dry run whose only held-back work is an expired year names a switch that does not hold that delete back.
- **Files touched** (found by a search on `origin/main` at 350988cf0 for `nothing is left`, `month_deletes_dry_run` and the `NEXT` mapping under `backend/idhazh/gardener/`; search again at dispatch):
  - `backend/idhazh/gardener/report.py` (`NEXT`: the `TaskOutcome.DONE` and `TaskOutcome.DRY_RUN` sentences; the module docstring says why one dry-run sentence names both switches, found during execution, Fowler)
  - `backend/tests/gardener/test_run_summary.py` (the Oracle; pins both sentences, the `done` one twice and the `dry-run` one once, now through `DONE_LINE` and `DRY_RUN_LINE`; a page with both kinds of dry run, found during execution, Fowler; `passing()` gives its `done` task the `repacked-from-raw` note instead of `carried-over`, found during execution, Fowler)
  - `backend/idhazh/contracts/gardener_events.py` (the `#:` comment on `TaskOutcome.DONE` said "nothing is left"; found during execution, Fowler: the search under `backend/idhazh/gardener/` did not reach `contracts/`)
  - Read, no change (found during execution): `backend/tests/gardener/tasks/test_yearly_expiry.py`, whose `caught_up`, `run_by_the_runner` and `summary_of` build the Oracle's tree and page; `backend/tests/gardener/test_report.py`, which pins that the dry-run sentence says "nothing was changed" and names "dry_run: false in config/gardener/<task>.json", and that no sentence says "gone", all three kept by Reader's words; `backend/tests/gardener/test_workflow_commands.py`, which reads `NEXT[TaskOutcome.DONE]` by name; `docs/architecture/publishing/idhazh-gardener.md`, which quotes neither sentence, so it does not change
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/gardener/test_run_summary.py`; ruff; mypy. CI: the full suite.
- **Oracle:** in `test_run_summary.py`, on a tree the test builds under `tmp_path`: a dry run whose only held-back work is an expired year renders, in Reader's words, a sentence that names the switch that would let the year go; a `done` pass renders a sentence that cannot be misread as a claim about data. On `origin/main` the dry-run sentence still offers only `month_deletes_dry_run: false`, and the `done` sentence still reads "nothing is left" plain, which is what lets this check fail. It cannot settle the exact words, which Reader chooses.
- **Found during execution:**
  - At dispatch, on `origin/main` at 60462700a, the files above held, with the additions marked found during execution.
  - The gap (b), read against the code: on `origin/main` the dry-run sentence names two switches, not one. `dry_run: false` does let an expired year go; the sentence then offered `month_deletes_dry_run: false` after "or", as a second way to let the work happen. That switch holds back old months and their raw days only, never a year, and changes nothing while `dry_run` is true. An expired year has no switch that only reports: `yearly_prune_enable: false` neither deletes nor names a year (`_yearly_expiry.drop`), so a dry run that names one has the expiry on, and `dry_run` is the only switch that holds that delete back. So the gap is the "or", and the Oracle's "still offers only `month_deletes_dry_run: false`" reads as "still offers `month_deletes_dry_run: false` as another way to let the work happen".
  - A `dry-run` ending has two sources, and both can share one page under one word: a declaration that says `dry_run: true` (today every retention task and both collection tasks), and a live compaction whose monthly window only reports and whose only work at the wake was old months past its keep line (today the three `compact-trial-*` declarations, with a 3-month window). So the one line names both switches, each tied to what it holds back (decisions 1 and 4).
  - Reader's first reason for the `done` words, that a `done` task's newest raw files wait for the next wake, came from `passing()`, an event `test_run_summary.py` builds by hand: a real pass with the `carried-over` note stops `ceiling` (`_daily_period.py`, `_reopened_month.py`). The second reason holds: a live compaction whose window only reports can end `done` with old months kept. `passing()` now carries a note a `done` pass can carry (decision 6).
  - Table F, F5 ("Did work, and nothing is left") is the plan owner's to update, as for rows 21, 22 and 35; the contract's comment now reads as decision 5 says.
  - Checks. `npm --prefix frontend run test:changed -- --list` selects the full suite, because `gardener_events.py` counts as shared input, so CI runs it. The row's test file with the two others that pin or read either sentence, `test_run_summary.py`, `test_report.py` and `test_workflow_commands.py`, `-n 0` through the gate lock: 57 passed before, 60 after (the page with both kinds of dry run and the two Oracle cases). `ruff check .` and `mypy` (722 files) clean before and after. `doc_load.py` on this plan: about 69,368 tokens before and 71,388 after, 4 sections; no section was added.
  - Oracle on the base commit 60462700a, in a copy outside this checkout under the long form of `TEMP` (pytest's `rootdir` the copy), with this row's `test_run_summary.py` copied in: 5 failed, 28 passed. Both Oracle cases fail for the row's reason, at the line under the table, while the row above it reads the same on both versions: under "deleted 1 expired year" the base says "- *done*: nothing is left, and the next wake takes what reaches its line by then", and under "would delete 1 expired year" it says "... to make the task live, or month\_deletes\_dry\_run: false to let a compaction drop months". The other three failures are the two picture pages and the page with both kinds of dry run, which pin the same lines. On this branch every case passes.
  - Sufficiency ([design-system.md](../docs/concepts/design-system.md#sufficiency-is-a-gate-not-a-taste)), as for rows 22 and 38: gates 1, 2 and 5 to 10 have nothing to measure on GitHub's Markdown page. Gate 3 holds: `test_every_summary_has_one_heading_and_is_ascii` holds every page it builds to one heading. Gate 4 holds: each row still says what its task did, and the line under the table no longer claims what the row does not show.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reader chooses the words for both sentences | Reader, 2026-10-08: `done` reads "it finished its work for this wake, and the next wake takes what reaches its line by then", because it starts with the work, not "nothing", so beside "deleted 1 expired year" it cannot read as "no data is left", and it stops promising that nothing due is left. `dry-run` reads "nothing was changed: it only named the work it found. Set dry_run: false in config/gardener/<task>.json to let it do that work, except that a compaction keeps the old months and raw days it found until month_deletes_dry_run: false is set there too", because `dry_run: false` lets the task do whatever its row says it would, an expired year included; `month_deletes_dry_run` is named as the one exception, for old months and raw days alone, so nobody reaches for it to let a year go, and the owner of a live compaction whose window only reports is sent to the switch that keeps those months; "what a live pass would do" became "the work it found", because a pass that was live can end `dry-run` |
| 2 | Part (b) must land before 2030-01-01 UTC, the first day any year expires (row 38, decision 4) | Plan owner, 2026-10-08 |
| 3 | Level 1: two fixed sentences in one mapping, shared by every task through one call site; a wrong version is obvious and local | Plan owner, 2026-10-08 |
| 4 | `NEXT` stays one fixed sentence per word, and the dry-run sentence names both switches. A page says each word once and can show both kinds of dry run under it, so its line has to be true beside every row; the event cannot tell the two kinds apart (`periods.months_dropped` lists months dropped and months only named, and `month_deletes_dry_run` is only on `PeriodsChosen`); `next` is a log field and is never stored, so a sentence chosen per case stays possible later with no migration | Fowler, 2026-10-08 |
| 5 | `done`'s meaning does not change: `classify` is its definition and is not touched. The `#:` comment on `TaskOutcome.DONE` changes in the same commit as the sentence, to "It did work and finished its work for this wake, without stopping at its ceiling. What it recovered, and what a monthly window that only reports kept, do not change this." No version stamp: `TaskOutcome` is an enum on a log event, and a `#:` comment is in no schema | Fowler, 2026-10-08 |
| 6 | `passing()` gives its `done` task the `repacked-from-raw` note, which a `done` pass carries, in a test-only commit before the sentences, so the sentence commit changes only the words; `report.py`'s docstring says why one dry-run sentence names both switches | Fowler, 2026-10-08 |

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | As today | The `done` sentence can be misread, and from 2030-01-01 UTC the `dry-run` sentence can name a switch that does not hold back the delete it is read beside | Nothing to build, and two sentences that can mislead a reader of the job page | Row 38's report (Reader, 2026-10-08) |
| 2 | Fold it into row 38 | Row 38 merged before Reader raised these; both follow-ups were explicitly left for a row of their own | Reopening a merged row, #1434 | Row 38's report (Reader, 2026-10-08) |
| 3 | Choose the dry-run sentence by what the pass held back, by `TaskFinished.dry_run` or by `periods` | Telling a dry run from a live compaction whose window only reports needs a second place that decides what a dry run is, and one word would carry two meanings on one page | A new `TaskFinished` field or an inference beside `classify`, and `_words` keyed by sentence as well as word | Fowler, 2026-10-08 |
| 4 | Keep "nothing is left" true, so a task with kept old months stops ending `done` | Waiting raw files already end `ceiling`, and kept months are not unfinished work: a window that only reports finds the same months at every wake, so a `compact-trial-*` task would never end `done` again | A change to `classify` that makes the word say less | Reader named it as Fowler's call, 2026-10-08; Fowler, 2026-10-08 |
