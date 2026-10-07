# Plan 61 - The council's own record moves to the ledger door

**Last Updated**: 2026-10-07

**Level**: 5 (CLAUDE.md section 6): the plan replaces a persisted row contract and moves a committed ledger. The owner approved the shapes and the names on 2026-10-04 and set rows 1, 2 and 3 at Levels 2, 3 and 4; row 4 is Level 2.

**Status**: all six rows are DONE. Row 4 re-proved and retired the named CSV sources and removed the old family and compatibility. Owner @kumarsnaveen_microsoft ruled on 2026-10-07 that legacy run `37402604801` will not be rerun ("it wont be run just do your job deliver"), waived the rerun-window wait in section 2.5/Table J, and authorized delivery while pipelines continue. Obsolete branch and open-PR writers are recorded as information, not blockers. No run was cancelled, workflow disabled, history deleted or execution prohibited. Keep this plan for the requested retirement evidence; closure deletion remains with the coordinator.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The council writes one row for each piece of its own work into a CSV ledger, `state/llm-council/shard-outcomes/`, and numbers each piece with `shard`: -1 for picking the work, -2 for counting the results, and 0 upward for each part of the split. The ledger door, which every moved ledger goes through, uses `shard` for the shard of the job that wrote a row, refuses a value below 0, and lets a row's own field of that name replace its column. So this ledger cannot move to the door as it is. The owner approved on 2026-10-04 a new ledger whose rows name their step and their part, saved by the council's save job through the door |
| A2 | Hard scope - in | - The row contract `CouncilRunRecord` and the step enum `EvaluationStep` (Table E), with a reader for every committed old row (Table F).<br>- The rule every judge ledger follows, written into the registry page (Table H).<br>- The ledger `council-run-records`, declared and written through the door by the save job (Table G), with its compaction, staging row, prune target, migrator entry and the two frontend names.<br>- Migration writes only records it owns; a raw-only write mode leaves CSV and compact files unchanged.<br>- Explicit historical compaction ranges reach imported records behind the normal look-back window.<br>- Every committed council CSV record copied and proved without stopping workflows.<br>- Source files, the old family and compatibility removed together only under the retirement gate in section 2.5 |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Keep both storage paths, copy and prove the records, then remove the old path. Fowler, approved by the owner on 2026-10-07 |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 5 and 6 share the compaction documentation and run in order; then rows 3 and 4 follow. Row 3 is carried by the plan's owner, never delegated; unrelated workflows and agents continue. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table B - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Moving the judge ledgers `scored-pairs`, `fitted-thresholds`, `metrics` and `merge-line-holdout-scores` onto the door, and renaming `shard` on `metrics` and `scored-pairs` | Their CSV writers, union lines, `UNION_SAFE` entries and CSV prune targets stay until each moves. Table H binds each move | Plan 59's row "The judge ledgers with a union driver move to the door" (`TODO/20261003-59-csv-ledgers-left-plan.md`), after its row "The person rules on what blocks each ledger left on CSV" |
| B2 | The ruling on the filled cells that the judge ledgers' CSV files hold under headings their contracts dropped, such as `key_point` and `key_point_weight`: 500 cells at 9165a9f75 (492 in `scored-pairs`, 7 in `fitted-thresholds`, 1 in `merge-line-holdout-scores`). Recount by summing the filled cells under each contract's `DROPPED_CELLS` headings across that ledger's committed CSV files | The migrator refuses a filled cell under a heading its `old_headings` does not declare, so none of those three ledgers can move until a person rules. This plan's ledger has no such cell: every committed `host_model` cell is empty | A person's ruling, then one `old_headings` entry mapped to `None` per dropped heading, in the plan that moves those ledgers (Plan 59) |
| B3 | Renaming `ShardOutcome` and `ShardResult` to step names | The outcome enum and the tenant's result keep "shard" in their names while the row says step. Nothing behaves differently | A structural row after row 2 (Rename Class), when a reader asks for it |
| B4 | Renaming the judge job's matrix cell, `Tenant.run_shard(shard, shards)`, `council.shards` and `--shard` | None: matrix cell k is shard k of the judge job, which is what the door means by `shard` (Table D, D14) | A change to what one matrix cell is |
| B5 | `Tenant.settle` taking the council's writer identity (Table H, H4) | Nothing today: no judge ledger writes through the door | The first judge ledger's move (Plan 59) |
| B6 | Recording the machine for each council step, which `host_model` was for | A slow night and a slower processor read the same on this ledger. The digest pipeline already characterises the runner pool ([llm-council.md](../docs/architecture/publishing/llm-council.md), "No machine is recorded per unit") | A person reverses the 2026-10-04 ruling; then a new nullable field and a writer that fills it |
| B7 | The known-defects row "A shard is called a `unit` in the council's workflow and its tests" | The workflow comments and the test names keep the word `unit` | That row of `TODO/20260823-known-defects-plan.md` |

### ESCALATE triggers

Table C - when to stop and ask

| # | Trigger | What happens, and the options |
| --- | --- | --- |
| C1 | The old family must remain claimed while obsolete writers can return; a family needs its ledger member and registry/staging entries | Keep the family, member and entries through row 3. Row 4 removes them with the proved CSV sources under section 2.5. Owner ruling, 2026-10-07, replaces the earlier row-3 deletion timing |
| C2 | **Ruled 2026-10-04: (a), because the owner named the save job `save_council_results` (Table D, D8).** `ServerJob` says every value is a job's own id in its workflow file (its docstring, and `docs/reference/host-metrics.md`). The save step runs in `llm-council.yml`'s job `collect`, and the approved value is `save_council_results` | (a) **Chosen.** Rename that job id from `collect` to `save_council_results` in row 2. Cost: the job key, the `collect` references in `backend/tests/workflows/test_llm_council_workflow.py`, and one sentence of `llm-council.md`. (b) Keep `collect`, and write the exception into the `ServerJob` docstring and `docs/reference/host-metrics.md`. Cost: a reader needs a lookup to go from a row's job to the steps that wrote it |
| C3 | **Ruled 2026-10-04: (a), a construction choice by Fowler, so the page states only true facts.** Table H says `run_id` on a judge row is the council run (H1) and that the save job files the rows (H4). `merge-line-holdout-scores` is filed by a person's own `score-merge-line-holdout --run-id` run, never by a council run | (a) **Chosen.** Write the rule as approved, with one sentence that this ledger's `run_id` is the run of the person who files it, which is also the door's column, and that H4 does not reach it. (b) Write the rule word for word. Cost: the page states one false fact, which Plan 59's move of that ledger meets |
| C4 | A persisted shape that section 2 does not declare, or a change to a name in Table D | Stop and surface ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)). The names are the owner's |
| C5 | A committed council row that Table F cannot read: a `shard` below -2, a filled `host_model`, or a row whose `date` is not its file's day | Row 3 stops. No row is dropped, edited or mapped by hand |
| C6 | Two personas still disagree after one debate | Stop and surface |
| C7 | A failed save has unaccounted records, or fresh source-cell proof fails | Recover captured output or re-import and prove changed sources. The owner's 2026-10-07 ruling waives the rerun wait and makes obsolete refs informational; it does not waive source-cell proof or authorize cancellation, disablement or history deletion |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The council's run record has its own contract, and it reads every old row | - | A | DONE #1294 | cautious-adventure | #1294 | Plan 61 row 1: council run record contra |
| 2 | The council saves its run records through the ledger door | 1; Plan 60 "Which months may close", shipped in #1303 | B | DONE | plan-row-status | #1323 | Council ledger writer |
| 3 | The committed council records are copied and proved while workflows continue | 2, 5, 6 | E | DONE | probable-giggle | - | owner |
| 4 | The old-row reader and the migrator's council entry are deleted | 3; section 2.5 retirement gate as ruled 2026-10-07 | F | DONE | retire-legacy-council-records | - | owner |
| 5 | Migration preserves writer ownership and can write raw files without packing | 2 | C | DONE | - | - | - |
| 6 | Explicit historical packing reaches imported records outside the rerun window | 5 | D | DONE | supreme-pancake | - | owner |

## 2. Shared declarations

Rows point here. Each name, shape and rule is declared once.

### 2.1 Names

Table D - names. The owner approved D1 to D8, D14 and D15 on 2026-10-04. D9 to D11 are the design's code names for them, and D12, D13 and D16 follow from them.

| # | Thing | Name | Replaces |
| --- | --- | --- | --- |
| D1 | Family and ledger | `council-run-records` | `llm-council/shard-outcomes` |
| D2 | Row field: which step | `evaluation_step` | - |
| D3 | Step: pick the work, once a date | `select_judge_work` | `shard` -1 (the session's `prepare`) |
| D4 | Step: one part of the split | `evaluate_work_part` | `shard` k >= 0 (the session's `run_shard`) |
| D5 | Step: count the results, once a date | `combine_judge_results` | `shard` -2 (the session's `settle`) |
| D6 | Row field: which part | `work_part_index`: an int >= 0, empty on the two once-a-date steps | `shard` k >= 0 |
| D7 | Row field: how many parts | `work_part_count`: an int >= 1 | `shards` |
| D8 | Writer job | `ServerJob.SAVE_COUNCIL_RESULTS`, value `save_council_results` (Table C, C2) | - |
| D9 | Row contract | `CouncilRunRecord`, schema stem `council-run-record`, in `backend/idhazh/contracts/council_run_record.py` | `CouncilShardOutcome`, stem `council-shard-outcome`, in `backend/idhazh/contracts/council_shard_outcome.py` |
| D10 | Step enum | `EvaluationStep`, a `StrEnum` in the same module: the parquet column mapper takes a `StrEnum` and refuses a `Literal` | `SELECTION_UNIT` and `SETTLEMENT_UNIT` |
| D11 | Ledger member | `LedgerName.COUNCIL_RUN_RECORDS` | `LedgerName.LLM_COUNCIL_SHARD_OUTCOMES` |
| D12 | Door key | `COUNCIL_RUN_RECORD_KEY`, in `backend/idhazh/ledger/keys.py` | `COUNCIL_SHARD_OUTCOME_KEY` |
| D13 | Compaction task | `compact-council-run-records`, in `config/gardener/compact-council-run-records.json` | - |
| D14 | `shard` | Only the shard of the job that wrote a row: the door's own column. No council or judge row contract declares `shard`, `job`, `attempt`, `unit_id`, `ledger` or `covers` with another meaning; the precedent is item health's `machine_shard`. The judge job's matrix cell keeps the name `shard`, because cell k is shard k of that job | - |
| D15 | Dropped column | `host_model`: empty in every committed row, and nothing writes it | - |
| D16 | Shipped file names | A part's file is named by its index (`0`, `1`, ...). A once-a-date step's file is named by its value with `_` written `-` (`select-judge-work`, `combine-judge-results`) | `-1` and `-2` |

### 2.2 The row contract

Table E - `CouncilRunRecord`, in field order. Every instant is UTC (CLAUDE.md section 2).

| # | Field | Type and rule |
| --- | --- | --- |
| E1 | `version` | The schema stamp. A migrated row keeps the stamp it carries, `2026-09-21T12:00` |
| E2 | `date` | `DateStamp`: the digest date the step worked on. The door files the row under it |
| E3 | `run_id` | `RunId`: the council run, minted once in the planning job by `backend/idhazh/council/run_identity.py`. The same run's save job files the row, so it matches the door's `run_id` column |
| E4 | `judge_id` | `Slug`, at most `JUDGE_ID_MAX_LENGTH` (64) characters. Recorded, never checked against a list |
| E5 | `evaluation_step` | `EvaluationStep`: `select_judge_work`, `evaluate_work_part` or `combine_judge_results` (D3 to D5) |
| E6 | `work_part_index` | An int >= 0, or empty |
| E7 | `work_part_count` | An int >= 1. Every row of a date carries the date's width, so fewer `evaluate_work_part` rows than the count shows a part that never reported |
| E8 | `outcome` | `ShardOutcome`: `completed`, `stopped_on_deadline` or `nothing_to_do`, unchanged |
| E9 | `started_at` | `Timestamp`, UTC |
| E10 | `seconds_spent` | A float >= 0: the step's wall clock |
| E11 | `model_calls`, `tokens_in`, `tokens_out` | An int >= 0, or empty. Empty, not 0, when the tenant runs no model |
| E12 | `model_seconds` | A float >= 0, or empty |
| E13 | Validator | `work_part_index` is filled exactly when `evaluation_step` is `evaluate_work_part`, and it is less than `work_part_count` |
| E14 | CSV methods | `csv_columns`, `csv_row` and `from_csv_row`, as `CouncilShardOutcome` has them. The session ships each row between jobs as one CSV file through `metrics_sink` (the `JudgeRow` protocol), and the migrator reads old rows through `from_csv_row`. An empty cell is an absent value, never 0 |
| E15 | Changelog | A new newest entry, dated the UTC day row 1 is written, above `CouncilShardOutcome`'s two entries, so the stamp a migrated row keeps names a shape this changelog describes |

### 2.3 How an old row is read

Table F - one row of an old `state/llm-council/shard-outcomes/YYYY/MM/DD.csv` file, whose heading is `version,date,run_id,judge_id,shard,shards,outcome,started_at,seconds_spent,model_calls,tokens_in,tokens_out,model_seconds,host_model`. The migrator's `read_csv_cells` refuses a filled heading the contract does not declare, drops an empty one, and hands a heading that `old_headings` names to `from_csv_row` under its old name. So the mapping below is the contract's own, inside `from_csv_row`. Each old value maps to a distinct new pair, so a test maps every pair back.

| # | Old cell | Read as |
| --- | --- | --- |
| F1 | `shard` -1 | `evaluation_step` `select_judge_work`, `work_part_index` empty |
| F2 | `shard` -2 | `evaluation_step` `combine_judge_results`, `work_part_index` empty |
| F3 | `shard` k, k >= 0 | `evaluation_step` `evaluate_work_part`, `work_part_index` k |
| F4 | `shard` with any other value, or empty | Refused, naming the cell |
| F5 | `shards` n | `work_part_count` n |
| F6 | `shard` beside a filled `evaluation_step` | Refused: one row in two shapes |
| F7 | `host_model` empty | Dropped by the migrator before the contract reads the row. Not declared |
| F8 | `host_model` filled | Refused by the migrator. None at 9165a9f75 |
| F9 | `version` | Kept |
| F10 | Any other declared field | Read under its own name |
| F11 | A heading no field declares and F1 to F9 do not name | Refused by the model (`extra="forbid"`) |

### 2.4 The ledger and its writer

Table G - `council-run-records`

| # | What | Declaration |
| --- | --- | --- |
| G1 | Family | `council-run-records` in `config/ledgers.json`, after `run-plan`: `lifecycle_status` `active`, the description "How each step of the nightly judging workflow ended, and what it cost.", `onboarded` the UTC day row 2 is written, and one ledger of the same name with grain `raw-and-compact`, prefix `["council-run-records"]`, and `stem` and `suffix` null. The prefix starts with the family's name, as the registry requires |
| G2 | Member | `LedgerName.COUNCIL_RUN_RECORDS = "council-run-records"`, after `RUN_PLAN` |
| G3 | Key | `COUNCIL_RUN_RECORD_KEY = ("date", "run_id", "judge_id", "evaluation_step", "work_part_index")`, paired with `CouncilRunRecord` in the door table `_DOOR_SHAPES`. It has no preference, so the first row of a key wins. Key cells compare as text (`raw_files.settle_rows`), so an empty `work_part_index` settles the same way on every read |
| G4 | Writer | `_collect` in `backend/idhazh/council/session.py`, still called from the `finally` of `settle`. One `ledger.persist` call per judged date, with `covers` that date and the rows read back from the shipped files through `CouncilRunRecord` |
| G5 | Writer identity | `run_id` the council run; `attempt` from `run_context.run_attempt()`; `job` `ServerJob.SAVE_COUNCIL_RESULTS`; `shard` 0; `producer` `council.session`, the module name without `idhazh.`, as every stage spells it; `git_sha` the CLI's `--commit`, which the settle step in `llm-council.yml` passes as `"${{ github.sha }}"` |
| G6 | Files | One raw file per judged date per run. A re-run of the job is a higher `attempt` at the same `unit_id`, so its file replaces the first on every read |
| G7 | Compaction | `config/gardener/compact-council-run-records.json` is `compact-candidate-models.json` as `main` holds it at dispatch, with `ledger` and `owns` changed and the four values the owner approved held: packing live (`dry_run` false), monthly files kept for ever (`monthly_window` forever), `monthly_keep_days` 93 and `prune_refusal` null. It is listed in `task_names` of `config/idhazh_gardener.json` |
| G8 | Staging | A `staging.REGISTRY` row naming `idhazh.council.session._collect`, with no digest job labels. `council_matrix.COUNCIL_LEDGER` becomes `staging.staged_path(LedgerName.COUNCIL_RUN_RECORDS)`, which is `state/raw/council-run-records`. `commit_and_push.py` skips that path while nothing is on disk or tracked under it |
| G9 | Prune | A door prune target with no edit, because `prune.DOOR_LEDGERS` reads the registry. The CSV target goes |
| G10 | Migrator | A `CsvLedger` entry keyed `LedgerName.COUNCIL_RUN_RECORDS`: the old entry is a shared day file (grain `day`, suffix `.csv`) under the two folders `llm-council/shard-outcomes`, the old window is `ForeverWindow`, and `old_headings` is `{"shard": "work_part_index", "shards": "work_part_count"}`. `host_model` is not declared. `require_layout` accepts a declared prefix of more than one folder |
| G11 | Shipping | `metrics_sink.ship_judge_metrics` takes `name: str`, refused unless it is a slug, instead of `shard: int`. The tenant passes `str(shard)`, so its file names do not change. The session passes D16's names |
| G12 | Frontend | `LEDGER_NAMES` in `frontend/src/lib/data/slice-shapes.ts` gains `council-run-records` and loses `shard-outcomes` (Table C, C1). `SERVER_JOB` in `frontend/src/lib/server/host-fingerprint.ts` gains `save_council_results`. Each follows its enum's order, which its binding test compares |
| G13 | Door names on the row | `ENVELOPE_NAMED_FIELDS` in `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py` lists `{"run_id"}` for the ledger: its only door name, meaning the council run that the writer identity also carries |

### 2.5 The rule every judge ledger follows

Table H - written into `docs/architecture/contracts/ledger-registry.md` by row 1, with the one exception Table C, C3 rules.

| # | Rule |
| --- | --- |
| H1 | Declare none of the door's names; `run_id` only as the council run. The one exception is `merge-line-holdout-scores`, whose `run_id` is the run of the person who files it, which is also the door's column |
| H2 | A per-part row names its part `work_part_index`, and `work_part_count` if it needs the width. `metrics` and `scored-pairs` rename `shard` when each moves (Plan 59); `fitted-thresholds` and `merge-line-holdout-scores` have no `shard` field |
| H3 | The key includes `run_id`, and `work_part_index` if the row is per part |
| H4 | The save job files the rows through `ledger.persist`. When the first judge ledger moves, `Tenant.settle` takes the council's writer identity. A person files `merge-line-holdout-scores`, so H4 does not reach it |
| H5 | Rows are filed under the judged date |
| H6 | A field is renamed in the same change that moves its ledger: a CSV append under a changed header is refused (`require_matching_header` in `backend/idhazh/ledger/csv_file.py`) |

### 2.6 Gates every row runs

Every row runs what [run-the-gates.md](../docs/how-to/run-the-gates.md) selects for its changed files (`npm --prefix frontend run test:changed -- --list`, then the selected checks), takes the expensive gates through the lock that page names, and records the inputs and results in its report. Python runs as `.\.venv\Scripts\python.exe`, with `PYTHONPATH` set to the row's own worktree `backend` ([agent-notes.md](../docs/reference/agent-notes.md#git-fixtures-and-child-producers)). A row that changes Python runs ruff and mypy. A row that changes Markdown runs `python backend/utilities/doc_load.py` on each changed page, before and after. CI runs the full suite once on the merge candidate. Each row below names only its focused checks.

## 3. The rows

### Row #1 - The council's run record has its own contract, and it reads every old row

- **Scope:** `CouncilRunRecord` and `EvaluationStep` (Tables D and E) join the contracts with fixtures and tests, `from_csv_row` reads every old row by Table F, and Table H is written into the registry page. Nothing writes the contract yet. Level 2.
- **Files touched** (from a whole-tree search at 9165a9f75 for every name the row adds, D2 to D7, D9 and D10, which found none; search again at dispatch):
  - `backend/idhazh/contracts/council_run_record.py` (new: Tables E and F)
  - `backend/idhazh/contracts/__init__.py` (`CONTRACTS` gains `CouncilRunRecord`)
  - `tests/fixtures/contracts/council-run-record/a-part-that-ran-the-model.json` (new)
  - `tests/fixtures/contracts/council-run-record/a-selection-that-ran-no-model.json` (new)
  - `tests/fixtures/contracts/council-run-record/a-migrated-count-that-had-nothing-to-do.json` (new, stamped `2026-09-21T12:00` as a migrated row is)
  - `backend/tests/contracts/_fixtures.py` (`FIXTURE_FILES` names the three)
  - `backend/tests/contracts/test_council_run_record.py` (new)
  - `docs/architecture/contracts/ledger-registry.md` (Table H)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/contracts/test_council_run_record.py backend/tests/contracts/test_schema_drift.py backend/tests/contracts/test_cell_shapes.py backend/tests/contracts/test_stamped_boundary.py`; ruff; mypy; `doc_load.py` on `ledger-registry.md`. CI: the full suite.
- **Oracle:** a bijection in `test_council_run_record.py`. For `shards` n of 1 and of 4 (4 is the width of every committed row), each `shard` in -1, -2 and 0 to n-1, in an old row as the migrator hands it over (Table F, F7: no `host_model` cell), reads through `from_csv_row` as a distinct (`evaluation_step`, `work_part_index`) with `work_part_count` n, and mapping each pair back gives the `shard` it came from. `shard` -3, `shard` n, an empty `shard`, and `shard` beside a filled `evaluation_step` are refused. It fails if an old value is lost, merged with another, or read as the wrong step. It cannot settle whether a committed file holds a value outside that set; row 3's `--plan` reads every committed row.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Table F lives in `from_csv_row`. The migrator's `read_csv_cells` is the only path an old row arrives on, and it hands `shard` and `shards` over under their old names. The precedent is `ItemHealthRow.from_csv_row` | Fowler, 2026-10-04 |
| 2 | `from_csv_row` passes every heading it does not map to the model, so an undeclared heading is refused (Table F, F11) rather than dropped. An empty `host_model` never reaches it (F7) | Fowler, 2026-10-04 |
| 3 | `ShardOutcome` and `JUDGE_ID_MAX_LENGTH` are imported from `council_shard_outcome.py` in this row and move in row 2, so this row only adds | Fowler, 2026-10-04 |
| 4 | The changelog keeps `CouncilShardOutcome`'s two entries under the new one (Table E, E15) | Fowler, 2026-10-04 |
| 5 | Table H goes on `ledger-registry.md` under "Ledgers outside raw and compact" and settles the open question in its "`run_id` and `shard`" bullet, because that map is where every judge ledger's move starts. H1 and H4 are worded once C3 is ruled | Fowler, 2026-10-04 |
| 6 | Level 2: nothing reads or writes the contract until row 2 | The owner, 2026-10-04 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep `shard`, with -1 and -2 | The door refuses a `shard` below 0 (`RowIdentity.shard`) and lets a row field of that name replace its column | Every once-a-date row refused, 30 of the 46 committed rows at 9165a9f75, and every part row claiming the filing job's shard | The owner, 2026-10-04 |
| 2 | Rename it to a part number and keep -1 and -2 | A number still stands for a step | Every reader learns two special values | The owner, 2026-10-04 |
| 3 | A part number >= 0 on every row, 0 on the once-a-date steps | A select row claims a split that never existed | A false part on every once-a-date row | The owner, 2026-10-04 |
| 4 | One text field, `unit` | Queries split text, and it sits beside the door's `unit_id` | A string parse in every query that groups by part | The owner, 2026-10-04 |
| 5 | Call the step column `task`, the gardener's word | One name with two lists across two ledgers | A reader joining the two ledgers meets two vocabularies under one name | The owner, 2026-10-04 |
| 6 | Put `job`, `shard` and `attempt` on the row with each step's own values | It is the contradiction this design removes | Three cells that disagree with the file that holds them | The owner, 2026-10-04 |
| 7 | Keep `host_model` | Nothing writes it | A column nothing can fill, carried onto the door | The owner, 2026-10-04 |
| 8 | Rename the judge ledgers' `shard` now, while they are CSV | A CSV append under a changed header is refused (Table H, H6) | The next council night fails the header check until every committed day file of `metrics` and `scored-pairs` is rewritten | The owner, 2026-10-04 |
| 9 | Read old rows in a before-validator, on every path | The door's `load` would accept the old shape too | A stray `shard` cell on a door row silently becomes a step | Fowler, 2026-10-04 |
| 10 | Declare the outcome enum and the length bound again in the new module | Two definitions of one thing for the life of one row | Two `ShardOutcome` classes that a type check treats as different | Fowler, 2026-10-04 |
| 11 | Write Table H on `llm-council.md` | The person moving a judge ledger reads the registry map, not the council page | One more page to find from Plan 59 | Fowler, 2026-10-04 |

### Row #2 - The council saves its run records through the ledger door

- **Scope:** the ledger of Table G is declared, the session names each row by its step and part and saves each date's rows through `ledger.persist` with the identity in G5, `metrics_sink` ships by name, and the CSV path is deleted. Level 3.
- **Files touched** (from a whole-tree search at 9165a9f75 for every name the row adds, renames or deletes: D8, D11, D12, `council_shard_outcome`, `CouncilShardOutcome`, `council-shard-outcome`, `SELECTION_UNIT`, `SETTLEMENT_UNIT`, `LLM_COUNCIL_SHARD_OUTCOMES`, `shard-outcomes`, `llm-council/`, `append_council_shard_outcomes`, `COUNCIL_SHARD_OUTCOME_KEY`, `ShardOutcome`, `JUDGE_ID_MAX_LENGTH`, `host_model`, `ProcessorName` and `ship_judge_metrics`. Apply the rulings on C1 and C2 first, then search again at dispatch):
  - `backend/idhazh/contracts/base.py` (D8)
  - `backend/idhazh/contracts/ledger_name.py` (G2; the old member per C1)
  - `backend/idhazh/contracts/council_run_record.py` (`ShardOutcome` and `JUDGE_ID_MAX_LENGTH` move in)
  - `backend/idhazh/contracts/council_shard_outcome.py` (deleted)
  - `backend/idhazh/contracts/__init__.py` (`CouncilShardOutcome` leaves `CONTRACTS`)
  - `backend/idhazh/council/session.py` (the steps, D16, G4 and G5)
  - `backend/idhazh/council/metrics_sink.py` (G11)
  - `backend/idhazh/council/tenancy.py` (the `ShardOutcome` import)
  - `backend/idhazh/similarity/tenant.py` (the `ShardOutcome` import; `name=str(shard)`)
  - `backend/idhazh/stages/judge_item_pairs.py` (the `ShardOutcome` import)
  - `backend/idhazh/cli.py` (`council-settle` hands `--commit` to `settle`)
  - `backend/idhazh/ledger/keys.py` (G3; `COUNCIL_SHARD_OUTCOME_KEY` deleted)
  - `backend/idhazh/ledger/rows.py` (`append_council_shard_outcomes` deleted)
  - `backend/idhazh/ledger/settle.py` (the council's two `KeyedLedger` entries deleted)
  - `backend/idhazh/ledger/__init__.py` (the two exports deleted)
  - `backend/idhazh/ledger/staging.py` (G8; the old row per C1)
  - `backend/idhazh/telemetry/prune.py` (the CSV target and its comment deleted)
  - `backend/idhazh/path_classes.py` (the `UNION_SAFE` entry deleted)
  - `backend/utilities/council_matrix.py` (G8)
  - `backend/utilities/ledger_migration/csv_layouts.py` (G10)
  - `config/ledgers.json` (G1; the `llm-council` family per C1)
  - `config/gardener/compact-council-run-records.json` (new, G7)
  - `config/idhazh_gardener.json` (G7)
  - `config/appearance.json` (`explorer_query_max_chars`, decision 9)
  - `.gitattributes` (the council's union lines deleted)
  - `.github/workflows/llm-council.yml` (`--commit "${{ github.sha }}"` on `council-settle`; the job id per C2)
  - `frontend/src/lib/data/slice-shapes.ts` (G12)
  - `frontend/src/lib/server/host-fingerprint.ts` (G12)
  - `backend/tests/contracts/test_council_shard_outcome.py` (deleted)
  - `tests/fixtures/contracts/council-shard-outcome/a-unit-that-ran-no-model.json` (deleted)
  - `tests/fixtures/contracts/council-shard-outcome/a-unit-that-stopped-on-its-own-clock.json` (deleted)
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py` (G13)
  - `backend/tests/council/_imports.py` (gains `idhazh.contracts.council_run_record` and `idhazh.run_context`; loses `idhazh.contracts.council_shard_outcome`)
  - `backend/tests/council/_tenants.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/council/test_deadline.py`
  - `backend/tests/council/test_metrics_sink.py`
  - `backend/tests/council/test_session.py` (the Oracle)
  - `backend/tests/ledger/_fixtures.py` (`FIXTURE_NAMES` names the `council-run-record` fixtures)
  - `backend/tests/ledger/test_lifecycle.py`
  - `backend/tests/ledger/test_persist.py` (`LEDGER_OF` gains `CouncilRunRecord`)
  - `backend/tests/ledger_migration/test_csv_layouts.py` (the two-folder layout, decision 8)
  - `backend/tests/retention/test_prune_range.py` (`DAY_PATHS`)
  - `backend/tests/retention/test_union_safe_repeats.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_counting.py`
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/workflows/test_ledger_staging.py` (`LEDGER_KEYS`)
  - `backend/tests/workflows/test_ledger_door_jobs.py` (`DOOR_WRITING_VERBS` gains `council-settle`)
  - `backend/tests/workflows/test_llm_council_workflow.py` (decision 7; the job id per C2)
  - `docs/architecture/publishing/llm-council.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/contracts/state-ledgers.md`
  - `docs/concepts/partitions.md`
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `TODO/20260823-known-defects-plan.md` (decision 11)
  - `TODO/20261003-59-csv-ledgers-left-plan.md` (its sentences that name `llm-council/shard-outcomes` point at this plan, if they still stand at dispatch)
- **Acceptance gates:** local: `.\.venv\Scripts\python.exe -m pytest -n 0` on `backend/tests/council`, `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`, `backend/tests/contracts/test_ledger_registry.py`, `backend/tests/contracts/test_frontend_index_shapes.py`, `backend/tests/contracts/test_frontend_vocabularies.py`, `backend/tests/contracts/test_schema_drift.py`, `backend/tests/contracts/test_gardener_config.py`, `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/workflows/test_ledger_door_jobs.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`, `backend/tests/ledger/test_persist.py`, `backend/tests/ledger/test_lifecycle.py`, `backend/tests/ledger_migration/test_csv_layouts.py`, `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`, `backend/tests/retention/test_prune_range.py`, `backend/tests/retention/test_union_safe_repeats.py`, `backend/tests/test_ledger.py`, `backend/tests/test_similarity_judge.py`, `backend/tests/test_similarity_counting.py` and `backend/tests/test_similarity_fit.py`; `npm --prefix frontend run test:changed -- --spec console-data-explorer-address.spec.ts`; the browser smoke of the Records page (CLAUDE.md section 12): its ledger list offers `council-run-records`, the page renders while that ledger has no file, and the console shows no new error and no new 404; `doc_load.py` on every changed page. CI: the full suite. Named observation, not a gate: the first scheduled `llm-council.yml` run after the merge commits one raw file per judged date under `state/raw/council-run-records/` and nothing under `state/llm-council/`. A CSV row it commits means it checked out code from before the merge, and row 3 moves that row.
- **Oracle:** an integration test in `backend/tests/council/test_session.py`. `council-prepare`, `council-shard` for each part and `council-settle --commit <sha>` for one fixture tenant over a temporary state root leave exactly one raw file for the judged date under `state/raw/council-run-records/`. Its rows read back through `ledger.load_days` as one `select_judge_work`, one `evaluate_work_part` per part and one `combine_judge_results`, each carrying job `save_council_results`, shard 0 and the council run id, and its envelope names producer `council.session` and the commit passed. Run again with `GITHUB_RUN_ATTEMPT` 2, the read keeps only the second attempt's rows. It fails today because `settle` appends a CSV row under `state/llm-council/` and the door holds nothing. It cannot settle the trip a row takes between the three jobs of a real night; the named observation reads that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four commits, one hat each: (1) structural, Move Class: `ShardOutcome` and `JUDGE_ID_MAX_LENGTH` move into `council_run_record.py` and every importer follows; (2) structural, Change Function Declaration: `ship_judge_metrics` takes a name, with D16's names; (3) behavioural: the ledger of Table G is declared and the session saves through the door; (4) structural, Remove Dead Code: the CSV path goes. The docs go with (3) and (4) | Fowler, 2026-10-04 |
| 2 | The save step keeps its name, `_collect`, and the staging row names it (G8). The precedent is the gardener's `idhazh.gardener.runner._record` | Fowler, 2026-10-04 |
| 3 | `ShardOutcome` and `JUDGE_ID_MAX_LENGTH` keep their names when they move (Table B, B3) | The owner, 2026-10-04 |
| 4 | D16: the ship function's name is slug-checked, a slug has no `_`, and nothing reads a shipped file's name, so a once-a-date step's file takes its value with `_` written `-` | Fowler, 2026-10-04 |
| 5 | D8 and D11 are appended to their enums and G1 to the registry. `LEDGER_NAMES` and `SERVER_JOB` follow their enum's order, because their binding tests compare in order | Fowler, 2026-10-04 |
| 6 | G7 copies `compact-candidate-models.json` as `main` holds it at dispatch, apart from the four approved values, so the new file carries whichever spelling of the month-delete switch `main` has then. Plan 60's row "The month-delete switch is named for what it does" renames that switch in every compaction declaration | Fowler, 2026-10-04 |
| 7 | `test_every_path_a_registered_tenant_names_exists_in_a_fresh_checkout` checks the tenants' paths only, as its name says. The venue's own path is absent until the first save, and `commit_and_push.py`'s `_stage_named_paths` skips a path with nothing on disk and nothing tracked, which `test_a_path_the_tip_retired_does_not_stop_the_retry` holds. Its docstring's premise, that a missing path aborts the step, stopped being true when that skip landed | Fowler, 2026-10-04 |
| 8 | `require_layout` accepts a declared prefix of more than one folder, and still only the day-tree and shared day-file layouts. `test_csv_layouts.py` reads a shared day file under two folders with Table F's headings, and a filled `host_model` there is refused | The owner, 2026-10-04 |
| 9 | `explorer_query_max_chars` is recomputed so that `console-data-explorer-address.spec.ts` passes at the value and fails at one more. It is the longest question that fits the request target with every ledger selected, and the ledger list changes | Fowler, 2026-10-04 |
| 10 | `council-settle` joins `DOOR_WRITING_VERBS`, so every workflow step that runs it must pass `--commit` | Fowler, 2026-10-04 |
| 11 | The known-defects row "`host_model` is a column nothing fills, and two rulings disagree about whether it should" is stamped DONE in this change: the owner ruled on 2026-10-04 to drop the column, and this change removes its last declaration | The owner, 2026-10-04 |
| 12 | Plan 59's row "The CSV code no ledger uses any more is deleted" also edits `backend/idhazh/ledger/rows.py`, `backend/idhazh/ledger/keys.py`, `backend/idhazh/contracts/ledger_name.py` and `ledger-registry.md`. Whichever of the two is dispatched second waits for the first to merge | Fowler, 2026-10-04 |
| 13 | Level 3: it crosses the council, the ledger door, the workflow and the frontend | The owner, 2026-10-04 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the nested `shard-outcomes` address | The registry, the path builders, the `.gitattributes` patterns and every `owns` list would need a nested-folder rule | A rule in four places for one ledger | The owner, 2026-10-04 |
| 2 | Each step files its own row on its own machine | More job names, uploads carrying `state/raw`, and `unit_id` clashes | N + 2 files per tenant per date, where N is the part count, instead of one per date | The owner, 2026-10-04 |
| 3 | File under the day the run started, plus a `judged_date` field | A rename, derived values for old rows, and two dates in one job sharing one `unit_id` | A second date field and a derived value on every old row | The owner, 2026-10-04 |
| 4 | Write the CSV and the door ledger side by side for a while | Nothing reads the council's rows yet, so there is no reader to move across | Two records of every night, and the union driver kept | Fowler, 2026-10-04 |
| 5 | Rename `_collect` to a save name | A rename with no behaviour change, mixed into a behavioural row | One rename and its references, for no reader | Fowler, 2026-10-04 |
| 6 | Seed `state/raw/council-run-records/` with a `.gitkeep` so the existence check passes | The door's folders hold only files the door names | A file every reader of that folder has to skip | Fowler, 2026-10-04 |
| 7 | Name a once-a-date step's shipped file by its value as it is | The name is slug-checked, and a slug has no `_` | A second, looser name check for one caller | Fowler, 2026-10-04 |

### Row #3 - The committed council records are copied and proved while workflows continue

- **Scope:** copy every selected council CSV record through raw-only migration, pack through the gardener's guarded publication path, and prove source-cell parity while keeping CSV and its registered family. Level 4.
- **Files touched** (from the migrator's `--plan` output and a whole-tree search at 9165a9f75 for `llm-council` as a folder and a family):
  - `state/raw/council-run-records/` (new raw files, one for each migrated day)
  - `state/compact/council-run-records/` (only the gardener's guarded follow-up commits)
  - `TODO/20261004-61-council-run-records-plan.md` (this row's status and evidence)
- **Acceptance gates:** use the input declaration below. Run the migrator with `--plan`, then `--write --raw-only`; both exit 0. The data PR contains new raw files and this row's plan update, no CSV deletions or compact changes. After it merges, run the named council compaction with explicit `--from` and `--to` months through `backend/utilities/gardener_publish.py`, using its existing task/run/config arguments. Repeat capped or stale passes on current main. Run migration `--verify` against fresh committed state; every selected CSV key and filled cell must read back. Record the source commit and proof commit in the PR evidence. A relevant change to source months, row contract, registry, migration or compaction inputs requires another import/packing/proof pass; unrelated changes do not. CI: full suites on the actual candidates. No global idle check, `--retire`, CSV-absence check or global zero-backlog gate.
- **Oracle:** independent CSV source-cell proof through the normal ledger reader, plus the row 5 attempt-replacement test. It cannot prove records an obsolete run has not yet saved; late sources stay covered by this row until row 4 retires them.
- **Completion evidence (2026-10-07 UTC):** source/code `c4c242a99b8c0ffc7b44e75085a4571559f5d7eb`; additive copy merged at `9cb9b704c5ccafc9f4697be8021f764613ba7d38`. Run identity `2026-10-07-1`, production root `state`, ledger `council-run-records`, months `2026-09` and `2026-10`. The fresh recount found 16 CSV days, 9,414 bytes and 56 reader records. Raw-only writing imported 50 migration-owned records; six native records already held on October 5 retained their original rows and writer identities.
- **Packing and proof:** the guarded publisher's forced depth-one fetch hid ancestry from the local privacy hook. The separate structural correction merged at `abf57d20a4c5d23729ac99c6633ef76a2497caac`, without changing the hook or cutoff. Explicit historical passes landed at `e9ae324125c8b61b71ba4a0fef7b3b37ac00612b` and `09486008783a9210c561375f9b5ea2fc2ff216b5`; the second exhausted the selected inputs. On the latter committed state, `--verify` exited 0 with source-cell parity proven and `--plan` reported every selected day's rows already held. October 6's six native raw records remained byte-identical and readable. CSV, `.gitkeep` and legacy-family references remain unchanged.
- **Retirement ruling:** legacy run `37402604801`, created `2026-10-06T02:07:30Z`, is technically eligible for rerun until `2026-11-05T02:07:30Z`. Its collection succeeded even though selection failed. Owner @kumarsnaveen_microsoft waived waiting for that date on 2026-10-07 and authorized row 4 now, without workflow restrictions. Table J holds the current evidence.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Inputs: `--state-dir state --ledger council-run-records --month 2026-09 --month 2026-10 --run-id <UTC-DATE>-1 --git-sha <FULL-CODE-COMMIT-SHA>`. Add another explicitly named month only when a late source names it. Keep the same migration run identity on repeats; record the actual executing code SHA each time | Fowler; owner approval, 2026-10-07 |
| 2 | CSV, `.gitkeep`, the family and old member references stay through row 3. Their deletion belongs to row 4 | Owner, 2026-10-07 |
| 3 | Different native raw filenames may arrive while packing. Guarded gardener publication rejects changed output paths; a raw arrival missed by an earlier pass remains and is packed by a later explicit pass | Fowler, 2026-10-07 |
| 4 | A failed council run is not evidence that its results were saved. Inspect its failed stage and recover any completed output before its artifacts expire; report unavailable output instead of claiming parity | Fowler, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Wait for every pipeline to stop | Unrelated writes do not protect these records, and continual work prevents delivery | Indefinite delay | Owner, 2026-10-07 |
| 2 | Pack and delete in the migration PR | Adds a competing compact writer and removes recovery before legacy writers are retired | A guarded publication/regeneration implementation for all migration inputs and outputs | Fowler, 2026-10-07 |

### Row #4 - The old-row reader and the migrator's council entry are deleted

- **Scope:** after the retirement gate below, import any late sources, prove and retire CSV using the still-present converter, then delete the old family and compatibility together. Level 4 for source retirement; no persisted row shape changes.
- **Files touched** (from a whole-tree search for Table F's old names, `shard` and `shards`, in the contract and its test, and for `CSV_LEDGERS` entries keyed `LedgerName.COUNCIL_RUN_RECORDS`; search again at dispatch):
  - `backend/idhazh/contracts/council_run_record.py`
  - `backend/utilities/ledger_migration/csv_layouts.py`
  - `backend/tests/contracts/test_council_run_record.py` (the bijection becomes a refusal of `shard`)
  - `backend/tests/ledger_migration/test_csv_layouts.py` (the two-folder case declares a table entry of its own)
  - `docs/how-to/move-a-ledger-to-parquet.md` (the list of supported layouts)
  - `state/llm-council/shard-outcomes/` (only named, proved CSV sources and `.gitkeep`)
  - `config/ledgers.json`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/staging.py`
  - `frontend/src/lib/data/slice-shapes.ts`
  - `config/appearance.json`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_frontend_vocabularies.py`
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/council/test_metrics_sink.py`
  - `docs/reference/repository-layout.md`
  - `TODO/20261004-61-council-run-records-plan.md`
- **Acceptance gates:** first satisfy section 2.5. With the converter still present, repeat row 3 for changed source inputs, run `--verify`, then `--retire`, then `--check` with its explicit ledger/root/month arguments; all exit 0 and check reports no CSV. Only then remove the converter and family. Before merge, inspect those same old paths on the current merge candidate; do not use a default ledger list which now omits the removed entry. Relevant source changes invalidate retirement evidence. Local: selector-listed checks plus council contract, migration layout, persist, registry and frontend vocabulary tests; `doc_load.py` on changed Markdown. CI: full suite on the cleanup candidate.
- **Oracle:** fresh source-cell parity before retirement, zero CSV on explicitly named paths after retirement, and the migrated old-stamp fixture round-trip through raw and compact formats. These checks cannot forbid a later dispatch of obsolete code; the owner's 2026-10-07 ruling accepts that risk without prohibiting execution.
- **Retirement evidence (2026-10-07 UTC):** executing code/source commit `23254f4ff1c72c66e055cf0ff9fa242f3758d761`; explicit root `state`, ledger `council-run-records`, months `2026-09` and `2026-10`, stable migration run `2026-10-07-1`. `--verify` exited 0: 16 CSV days, 9,414 source bytes, 56 reader records and source-cell parity proven. `--retire` re-proved those inputs and deleted the 16 CSV files; `--check` then exited 0 with `0 CSV file(s) left`, before converter removal. `.gitkeep` was removed with the family. Retirement changed no raw or compact bytes.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Keep the old schema stamp and history readable; removing a CSV conversion path does not change the persisted Parquet row | Fowler, 2026-10-04 |
| 2 | Keep the general nested-layout reader; only the council entry is removed | Fowler, 2026-10-04 |
| 3 | One successful scheduled run proves the new writer works, not that obsolete writers cannot return | Fowler, 2026-10-07 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the old-row reader | A second shape the contract accepts, with no file left to read | A stray `shard` cell would silently become a step, for ever | The owner, 2026-10-04 |
| 2 | Delete it in row 3 | A council run that checked out code from before row 2 can commit one CSV row after row 3, and moving that row needs the reader | A CSV row nothing could move | The owner, 2026-10-04 |
| 3 | Remove the two-folder layout with the entry | Plan 59 needs it for every judge ledger it moves | The same change written again in Plan 59 | Fowler, 2026-10-04 |

### 2.5 Retirement gate for row 4

Table J - retirement evidence under owner @kumarsnaveen_microsoft's 2026-10-07 ruling

| # | Evidence | Action |
| --- | --- | --- |
| J1 | Cutover is #1323, `a348e004e0109b493e58d7961cacee78c2b14782`. Bounded UTC window 2026-10-04 through 2026-10-07 names legacy runs `37164837568`, `37248064576`, `37402604801`, each attempt 1, completed: draw failed, judge skipped, collect succeeded. Current-writer run `37556313016`, attempt 1, completed successfully. No queued job in these attempts | Finished attempts; no cancellation or workflow change |
| J2 | Run `37402604801` remains eligible until `2026-11-05T02:07:30Z`. Owner says it will not be rerun and waives the wait, quoted in Status above | Deliver now; do not retain the waived wait as a blocker |
| J3 | Remote branch snapshot names obsolete `append_council_shard_outcomes` in `console-chart-freshness`, `pipeline-tests-row-2-nested-trial-readers` (open #1350), and `plan-59-row-6-holdout-score-door` (open #1352). Other open PRs #1357, #1381 and #1382 have no obsolete writer. The only remote tag, `pre-msg-rewrite-2026-08-29`, predates the council module | Information only under the owner's ruling. Do not delete refs or prohibit execution |
| J4 | Run `37402604801` logs show selection failed on a pair with identical address keys, upload skipped, judge skipped, collect settled both judged dates and committed five files with seven inserted lines. Artifact list is empty; no captured evaluation output is available. All three named legacy saves succeeded; a failed draw is not evidence of lost saved rows | No failed legacy save in the named window; fresh CSV source proof remains mandatory |
| J5 | At `23254f4ff1c72c66e055cf0ff9fa242f3758d761`, explicit September/October verify, retire and check passed: 16 CSV days, 9,414 bytes, 56 reader records; zero CSV remained before converter removal | Inspect the same explicit source paths on the candidate and after merge. Re-prove any relevant source change; preserve native rows and identities |

### Row #5 - Migration preserves writer ownership and can write raw files without packing

- **Scope:** separate reader expectations from migration-owned rows, and add a production raw-only write option without changing existing default packing behavior. Level 3.
- **Files touched:**
  - `backend/utilities/ledger_migration/planning.py`
  - `backend/utilities/ledger_migration/phases.py`
  - `backend/utilities/ledger_migration/inputs.py`
  - `backend/utilities/ledger_migration/readback.py`
  - `backend/utilities/ledger_migration/report_lines.py`
  - `backend/utilities/migrate_to_parquet.py`
  - `backend/tests/ledger_migration/test_planning.py`
  - `backend/tests/ledger_migration/test_phases.py`
  - `backend/tests/ledger_migration/test_command.py`
  - `backend/tests/ledger_migration/test_proof.py`
  - `backend/tests/ledger_migration/test_full_chain.py`
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `TODO/20261004-61-council-run-records-plan.md`
- **Acceptance gates:** run the shared selector's listing, then its selected local checks and the named migration tests. Use real generated state and contracts, no network or mocks. Exercise native attempt 1, migration of another CSV key on the same day, then native attempt 2 before packing. Native attempt 2 must win. Inspect raw envelopes: migration must not own the native key. Repeat migration with changed CSV, retaining earlier migration-owned records absent from the later source. Production-root CLI tests assert CSV and compact bytes are unchanged by raw-only writing. Default/full-chain behavior remains covered. CI: full suite.
- **Oracle:** writer-ownership and attempt-replacement test through real persist/load, followed by independent source-cell proof. It cannot prove an unpacked historical import visible when a compact index already owns its day; row 6 and row 3 settle that.

Table K - decisions

| # | Decision | Authority |
| --- | --- | --- |
| K1 | `--raw-only` is valid only with explicit `--write`; other combinations exit 2 before any write. Success reports raw writing complete, CSV kept, packing/proof outstanding; no success-shaped parity claim | Fowler design; owner approval, 2026-10-07 |
| K2 | Retain the migration work identity across repeats. Separate its source-derived snapshot from native records and from the expected reader result. Read only named day/period files with the existing envelope and ledger helpers; if compact output no longer exposes required identity, refuse explicitly rather than guess ownership | Fowler design; owner approval, 2026-10-07 |
| K3 | Existing `planning._plan` folds all target rows into `models`, and `write_roots` persists those models under migration identity. Correct that ownership defect without changing the ledger's general key or attempt rules | Verified at e32768441, 2026-10-07 |
| K4 | Update the canonical migration runbook with separate online-copy and final-retirement procedures. Apply its split test before editing; this plan adds no new page because all rows answer delivery of one council migration | Owner approval, 2026-10-07 |

Table L - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Disguise production as a trial root or use copied config to suppress packing | Bypasses the actual production predicate instead of providing a supported operation | Misleading proof and unsupported operational setup | Fowler, 2026-10-07 |
| L2 | Copy native records into migration identity | Can preserve an older attempt under another identity and defeat replacement | Incorrect results despite apparently complete row counts | Fowler, 2026-10-07 |

### Row #6 - Explicit historical packing reaches imported records outside the rerun window

- **Scope:** make an explicit operator month range include its historical raw arrivals, without widening the ordinary scheduled rerun window. Level 2.
- **Files touched:**
  - `backend/idhazh/gardener/tasks/_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction_periods.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_publish.py`
  - `docs/architecture/publishing/ledger-compaction.md`
  - `TODO/20261004-61-council-run-records-plan.md`
- **Acceptance gates:** inspect selector listing and run selected checks plus named compaction/publish tests. Generate an indexed historical day with a later raw arrival outside the normal rerun window. Explicit selected months must include it and preserve source values after packing; ordinary schedule remains bounded as before. Use real local bare Git fixtures to test both orders: overlapping compact changes reject stale gardener publication, and a distinct raw arrival survives a stale successful pass and becomes readable after the next named pass. CI: full suite.
- **Oracle:** historical raw-arrival parity through the normal reader after an explicitly bounded pass, including both Git arrival orders. It cannot retire old writers or guarantee a future pass has already run.

Table M - decisions

| # | Decision | Authority |
| --- | --- | --- |
| M1 | `_rerun_span` currently intersects explicit ranges with the normal 30-day window. Explicit bounds replace that look-back bound while still respecting the daily mark, selected periods, policy limits and named inputs | Verified at e32768441; owner approval, 2026-10-07 |
| M2 | Reuse the gardener's existing guarded publication and explicit period arguments. A stale result lands nothing; repeat on current main. Do not text-merge compact indexes or choose one binary conflict side | Fowler, 2026-10-07 |
| M3 | Scheduled packing limits, retention and deletion permissions stay unchanged | Owner approval, 2026-10-07 |

Table N - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Widen every scheduled look-back | Charges every later wake for a one-time historical import | More repeated input reads without changing the scheduled question | Fowler, 2026-10-07 |
| N2 | Add a repository-wide lock or freeze | Existing guarded publication protects overlapping compact writes | Cross-workflow coordination and blocked unrelated delivery | Fowler, 2026-10-07 |
