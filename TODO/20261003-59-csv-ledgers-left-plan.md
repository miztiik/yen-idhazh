# Plan 59 - The ledgers left on CSV move to the door, and the CSV ledger code goes

**Last Updated**: 2026-10-08

**Level**: 5 (CLAUDE.md section 6): the plan teaches the door a folder of any depth, moves five committed ledgers onto it, renames a persisted field on two row contracts and moves committed data. Each row carries its own level below.

**Status**: written 2026-10-05 by Fowler under the owner's directive of 2026-10-05: "no CSV ledger producer, consumer, test or doc is left; only Parquet ones, each with its lifecycle, retention and gardener onboarding". The owner was not reachable, so every ruling the draft of 2026-10-03 left open is made here and recorded as "Fowler, 2026-10-05". Each is a construction choice the owner may reverse before the row that applies it is dispatched. The owner ruled later on 2026-10-05 that a door ledger may sit any number of folders deep, so the judge ledgers keep their names and folders (Table D, row 11). Checked against `main` at c076a221f. The owner authorized execution on 2026-10-05. On 2026-10-08 Fowler brought Table E and row 9 into line with two later changes: the owner's retention approval of 2026-10-07 (#1382), and the copy-while-writers-continue procedure the council's move introduced (#1378).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Ten ledgers write through the ledger door: Parquet files under `state/raw/`, packed under `state/compact/` by the gardener. Seven still write CSV files under `state/`, and the shared CSV ledger code stays alive for them. [ledger-registry.md](../docs/architecture/contracts/ledger-registry.md#ledgers-outside-raw-and-compact) maps each one and what blocks it. The council's own ledger is `council-run-records`; the [registry](../docs/architecture/contracts/ledger-registry.md#a-ledger-under-the-two-roots) records its current address, and the [migration runbook](../docs/how-to/move-a-ledger-to-parquet.md) no longer lists it among supported CSV layouts. This plan moves the other six and then deletes every piece of CSV ledger code, its tests and its pages |
| A2 | Hard scope - in | - The parquet column mapper reads a fixed-choice (`Literal`) field.<br>- The CSV code no ledger uses deleted now, with the four orphan `span-rollup` files under `state/span-rollup/`.<br>- The door files a ledger under its registry folder, however many folders deep (row 11).<br>- Five judge ledgers moved to the door under their family's folder, `content-similarity-judge/<ledger>`, with no name changed (Table D), each with its compaction, staging row, frontend names and migrator entry.<br>- `item-health-summary` written through the door; it has no committed file.<br>- Every committed judge CSV row moved onto the door in one data commit, with no cell lost except the cells Table G drops.<br>- The CSV ledger machinery, the migrator, their tests, fixtures and pages deleted once nothing needs them |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | One writer at a time, readers in the same change, data last, deletion after the data. Each move follows [move-a-ledger-to-parquet.md](../docs/how-to/move-a-ledger-to-parquet.md). The code row comes first. The plan's owner then copies that ledger's committed rows while writers continue. Last, one retirement commit deletes the CSV files of all five judge ledgers, once their old writers have stopped (row 9) |
| A6 | Execution | Autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows 1, 2, 3 and 11 start together. Rows 4 and 5 are one chain, and rows 6 and 7 are another, because in each pair the second edits what the first changed: `set_merge_line.py` and `applied.py`, then `score_merge_line_holdout.py` and `similarity-holdout.ts`. The two chains, row 3 and row 8 share only list files such as `keys.py`, `staging.py` and `config/ledgers.json`, so they run side by side, and the one that merges later keeps both entries. Rows 1 and 9 are carried by the plan's owner and never delegated. Merge with `gh pr merge <n> --squash --delete-branch`; GitHub refuses auto-merge on this repository |

### Hard scope - out

Table B - what is out

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | `council-run-records` | Nothing here: it is already on the door and has no CSV compatibility. Row 10 only retires CSV code used by the remaining ledgers | - |
| B2 | The CSV files a job ships to the next job of the same workflow: the council's per-part metrics and verdict files under `backend/var/council/`, and the draw sheet `backend/var/council/<date>/selection/*.csv` | They are scratch, never committed and never read by a later run, so they are not ledgers (CLAUDE.md Guardrail #3 names a persisted payload a later run reads). The `csv_row` and `from_csv_row` codec on the judge row contracts stays for them. Ruled by Fowler, 2026-10-05, reading the owner's directive as covering ledgers | A ruling that the shipping format is Parquet too; then one row that ships each part's rows as a raw door file and lets the save job read them with `ledger.load` |
| B3 | The browser copies under `frontend/public/`: `machine/YYYY-MM.csv`, `run-timeline/YYYY-MM.csv` and `telemetry/YYYY-MM.csv`, eight files at c076a221f | They are derived published files, rebuilt from door ledgers, not ledgers. The site keeps a CSV reader (`readCsv` in `frontend/src/lib/server/payload.ts`) for them | A plan that publishes those copies in the format `state/compact/` already uses, with the frontend reading them through `ledger-disk.ts` |
| B4 | The four orphan `span-rollup` files in the two trial roots | They stay until the pipeline-tests plan's row "Committed trial files move to the nested roots, and the orphan span summaries are deleted" (`TODO/20261004-pipeline-tests-migration-plan.md`) lands. Row 10 waits for it, so the end state still holds no CSV | - |
| B5 | Renaming the judge job's matrix cell, `Tenant.run_shard(shard, shards)` and `--shard` | None: matrix cell k is shard k of the judge job, which is what the door means by `shard` ([judge-ledger rule](../docs/architecture/contracts/ledger-registry.md#the-rule-a-judge-ledger-follows-when-it-moves)) | A change to what one matrix cell is |
| B6 | The test fixtures that are CSV because the thing they test reads CSV that is not a ledger: `tests/fixtures/resolver/*.csv` while `commit_and_push.py` still resolves a CSV conflict, and `tests/fixtures/evals/scores-reband.csv` | None while their reader stands. Row 10 deletes each one whose reader it deletes | Their reader's removal |

### ESCALATE triggers

Table C - when to stop and ask

| # | Trigger | What happens, and the options |
| --- | --- | --- |
| C1 | A committed judge CSV row the migrator cannot read with the declarations in Tables F and G | Row 9 stops. No row is dropped, edited or mapped by hand |
| C2 | A change to a name in Table D, or a persisted shape section 2 does not declare | Stop and surface ([handle-scope-change.md](../docs/how-to/handle-scope-change.md)). The nested folders are the owner's choice of 2026-10-05 |
| C3 | The door cannot settle one ledger's key as Table E declares it, for example the holdout marks' "newest mark wins" | Stop the row; surface the two options: a preference the door table already offers, or a key the reader settles itself |
| C4 | A workflow writes a judge CSV row after its code row merged and before row 9 | Not a stop. Row 9 copies that ledger again under the same run id, as the procedure says, and the retirement proves every row again |
| C6 | Two personas still disagree after one debate | Stop and surface |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The first upkeep run after feed health moved is read | - | A | DONE | p59-main-read | - | Fowler |
| 2 | The parquet column mapper reads a fixed-choice field | - | A | DONE | p59-row-2 | - | Fowler |
| 3 | The CSV code no ledger uses any more is deleted | pipeline-tests "Readers understand nested trial roots" | A | DONE | p59-row-3 | - | Fowler |
| 4 | The judge's scored pairs and its metrics are saved through the door | 2, 11 | B | PENDING | - | - | - |
| 5 | The fitted merge line is saved through the door | 4 | C | PENDING | - | - | - |
| 6 | The merge line's holdout score is saved through the door | 2, 11 | B | PENDING | - | - | - |
| 7 | The holdout marks are saved through the door | 6 | C | PENDING | - | - | - |
| 8 | The item health summary is saved through the door | 2 | B | DONE | p59-row-8 | - | Fowler |
| 9 | The committed judge rows move onto the door, and the old CSV files go | 5, 7 | F | PENDING | - | - | - |
| 10 | The CSV ledger code, the migrator and their pages are deleted | 8, 9; pipeline-tests "Committed trial files move to the nested roots, and the orphan span summaries are deleted" | G | PENDING | - | - | - |
| 11 | The door files a ledger under a folder of any depth | - | A | DONE | p59-row-11 | - | Fowler |

Cross-plan dependencies name the other plan's row by title. Re-check each title at dispatch.

## 2. Shared declarations

Rows point here. Each name, shape and rule is declared once.

### 2.1 Names

Table D - names and folders. The owner, 2026-10-05: a door ledger sits under its registry folder, and that folder may be any number of folders deep, so the judge ledgers keep their place under `content-similarity-judge/` and no name changes. Row 11 teaches the door the rule. This reverses the draft's five top-level families (row 4, rejected alternative 1).

| # | Ledger | `LedgerName` member and value | Folder inside `state/raw/` and `state/compact/` | Compaction task |
| --- | --- | --- | --- | --- |
| D1 | Scored pairs | `CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS = "scored-pairs"`, unchanged | `content-similarity-judge/scored-pairs` | `compact-content-similarity-judge-scored-pairs` |
| D2 | Judge metrics | `CONTENT_SIMILARITY_JUDGE_METRICS = "metrics"`, unchanged | `content-similarity-judge/metrics` | `compact-content-similarity-judge-metrics` |
| D3 | Fitted merge line | `CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS = "fitted-thresholds"`, unchanged | `content-similarity-judge/fitted-thresholds` | `compact-content-similarity-judge-fitted-thresholds` |
| D4 | Holdout score | `CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES = "merge-line-holdout-scores"`, unchanged | `content-similarity-judge/merge-line-holdout-scores` | `compact-content-similarity-judge-merge-line-holdout-scores` |
| D5 | Holdout marks | `CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS = "holdout-pairs"`, unchanged; was the flat file `holdout-pairs.csv` | `content-similarity-judge/holdout-pairs` | `compact-content-similarity-judge-holdout-pairs` |
| D6 | Item health summary | `ITEM_HEALTH_SUMMARY = "item-health-summary"`, unchanged; was grain `month`, suffix `.csv` | `item-health-summary` | `compact-item-health-summary` |
| D7 | The `content-similarity-judge` family | Holds D1 to D5 on the door, and keeps `score-distribution.json` (grain `flat`) and `archive` (grain `stamp`), both JSON, under `state/content-similarity-judge/` | - | - |
| D8 | A person's own command | `ServerJob.OPERATOR`, value `operator`: a command a person runs on their own machine, outside any workflow. It names the writer of D4 and D5 | - | - |
| D9 | Each compaction | `compact-` and the ledger's folder with each `/` written `-`, in `config/gardener/<task>.json` | - | - |

Table D, continued - the folder rule row 11 declares. The owner, 2026-10-05.

| # | Rule | Why |
| --- | --- | --- |
| D10 | A door ledger's registry `prefix` starts with its family's name, ends with its value, and may hold any number of folders between. A ledger that is its own family has the prefix `[<value>]`, as today | The family check already reads the first folder; the last folder keeps the value the file's envelope carries |
| D11 | Every door path - raw file, raw index, compact file, compact index, watermark, marks - is built from that prefix, never from the value alone | One rule, so no builder can file a nested ledger one folder up |
| D12 | No door ledger's folder sits inside another door ledger's folder | A walk of the outer ledger's day folders would read the inner ledger's files |
| D13 | The frontend reads a door ledger's folder from `LEDGER_FOLDERS` in `frontend/src/lib/data/slice-shapes.ts`, a hand copy of every prefix that is not `[<value>]`, held equal to the registry by `backend/tests/contracts/test_frontend_vocabularies.py` | The browser has no registry, and CLAUDE.md section 1a puts a small hand copy behind a named test |
| D14 | A member nested in a family keeps its spelling: family name, then value, in upper snake case | The members already read that way, so no importer changes |

### 2.2 What each move declares

Table E - per ledger. Every compaction is `config/gardener/compact-candidate-models.json` as `main` holds it at dispatch, with `ledger` and `owns` changed, listed in `task_names` of `config/idhazh_gardener.json`. So each one carries the retention the owner approved for every ledger on 2026-10-07 (#1382): packing is live, and a year's file expires 36 calendar months after that year ends in UTC. Each new task joins `MOVED_LEDGER_TASKS` in `backend/tests/contracts/test_gardener_config.py`. The named decision there cites that approval and the owner's directive of 2026-10-05 (Fowler, 2026-10-08). Every reader's reach stays inside that window; E5's reach of 730 days is 24 months.

| # | Ledger | Key, in `backend/idhazh/ledger/keys.py` `_DOOR_SHAPES` | Writer, and its identity | Readers moved in the same row |
| --- | --- | --- | --- | --- |
| E1 | D1 | `STORY_SIMILARITY_PAIR_KEY` with `work_part_index` added after `run_id` | `stages/count_verdicts.py`, inside `Tenant.settle`, in `llm-council.yml`'s save job: `run_id` the council run, `job` `ServerJob.SAVE_COUNCIL_RESULTS`, `shard` 0, `attempt` from `run_context.run_attempt()`, `producer` `stages.count_verdicts`, `git_sha` the CLI's `--commit` | `stages/set_merge_line.py`, `similarity/applied.py` (through `ledger.load_days`) |
| E2 | D2 | `("date", "run_id", "work_part_index")` | `council/metrics_sink.py`'s save path, called from `count_verdicts._collect_metrics`; identity as E1 | none today |
| E3 | D3 | `STORY_SIMILARITY_THRESHOLD_KEY` | `stages/set_merge_line.py`, inside `Tenant.settle`; identity as E1 with `producer` `stages.set_merge_line` | `similarity/applied.py`; `frontend/src/lib/server/similarity-ledger.ts` (through `sliceFromDisk`) |
| E4 | D4 | `MERGE_LINE_HOLDOUT_SCORE_KEY` | `stages/score_merge_line_holdout.py`, run by a person: `run_id` the `--run-id` given, `job` `operator`, `shard` 0, `attempt` 1, `producer` `stages.score_merge_line_holdout`, `git_sha` the checkout's `HEAD` | `frontend/src/lib/server/similarity-holdout.ts` |
| E5 | D5 | `("left_url", "right_url")`, the newest `marked_on` wins | `backend/utilities/sample_sheet.py --harvest`, run by a person: `covers` the `--labelled-on` day, `run_id` a new `--run-id`, `job` `operator`, as E4 | `similarity/holdout.py`, `frontend/src/lib/server/similarity-holdout.ts`, `backend/utilities/build_canary_day.py` |
| E6 | D6 | `("date", "stage")` | `gardener/tasks/telemetry_aggregate.py`, in the gardener's `run-tasks` job: the gardener's own writer identity, as `gardener.runner._record` builds it | none today |

### 2.3 What changes on a row contract

Table F - contract changes. Each ships its changelog entry and read-side migration in the row that moves the ledger (CLAUDE.md section 11; [the judge-ledger rule](../docs/architecture/contracts/ledger-registry.md#the-rule-a-judge-ledger-follows-when-it-moves)).

| # | Contract | Change | How an old row is read |
| --- | --- | --- | --- |
| F1 | `StorySimilarityPair` | `shard` renamed `work_part_index` ([judge-ledger rule](../docs/architecture/contracts/ledger-registry.md#the-rule-a-judge-ledger-follows-when-it-moves)) | The migrator's `old_headings` `{"shard": "work_part_index"}` |
| F2 | `ContentSimilarityJudgeMetrics` | `shard` renamed `work_part_index` | as F1 |
| F3 | `SimilarityHoldoutPair` | none | - |
| F4 | `FittedSimilarityThreshold`, `MergeLineHoldoutScore`, `ItemHealthSummaryRow` | none | - |
| F5 | `ScorerModelId`, `JudgeModelId`, `ContentSimilarityJudgeId` | none: the mapper learns `Literal` (row 2) | - |

### 2.4 The cells the contracts already dropped

Table G - Fowler, 2026-10-05. At 9165a9f75 the committed judge CSV files held 500 filled cells under headings each contract's `DROPPED_CELLS` names: 492 in scored pairs (`decode_digest`, `key_point`, `key_point_weight`), 7 in the fitted line (`key_point_weight`) and 1 in the holdout score (`key_point_weight`).

| # | Ruling | Why |
| --- | --- | --- |
| G1 | Each dropped heading is an `old_headings` entry mapped to `None`, so the migrator drops the filled cell and reads the row | Each contract dropped the field on purpose, with a changelog entry: `key_point_weight` shipped at zero and never moved a score; `key_point` and `decode_digest` fed only it. The cells stay in git history at every commit before row 9 |
| G2 | Row 9's `--plan` prints the count it drops per heading, and the data commit's message carries them | A reader of the commit sees what went without opening the files |

### 2.5 Gates every row runs

Every row runs what [run-the-gates.md](../docs/how-to/run-the-gates.md) selects for its changed files (`npm --prefix frontend run test:changed -- --list`, then the selected checks), takes the expensive gates through the lock that page names, and records the inputs and results in its report. A row that changes Python runs ruff and mypy. A row that changes Markdown runs `python backend/utilities/doc_load.py` on each changed page, before and after. A row that changes the published site runs the browser smoke (CLAUDE.md section 12). CI runs the full suite once on the merge candidate. Each row below names only its focused checks.

### 2.6 What every move row does

Each of rows 4 to 8 does all of these for its ledger, so no row lists them again. Rows 4 to 7 need row 11 first; row 8's folder is one deep and does not:

1. The ledger's entry in `config/ledgers.json` stays in its family, with grain `raw-and-compact`, the prefix of Table D (D10), and `stem` and `suffix` null. The family keeps `lifecycle_status` `active`; `item-health-summary` keeps its own family.
2. If the prefix is not `[<value>]`, its `LEDGER_FOLDERS` entry (D13). No member is renamed.
3. The key and contract in `_DOOR_SHAPES` (Table E).
4. The writer calls `ledger.persist` with the identity in Table E; the CSV append goes.
5. Each reader in Table E reads through the door in the same change.
6. The compaction (Table E).
7. A `staging.REGISTRY` row naming the writer.
8. `LEDGER_NAMES` in `frontend/src/lib/data/slice-shapes.ts` already holds the value; nothing changes there.
9. The ledger's `merge=union` or `merge=text` line in `.gitattributes`, its `UNION_SAFE` entry in `backend/idhazh/path_classes.py`, and its `_TARGET_LEDGERS` entry in `backend/idhazh/telemetry/prune.py` go.
10. A migrator entry in `backend/utilities/ledger_migration/csv_layouts.py`: the old layout and folders, `ForeverWindow`, and the `old_headings` of Tables F and G.
11. `ENVELOPE_NAMED_FIELDS` in `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py` names the ledger's door names (`run_id` for E1 to E4).
12. The ledger's line on `ledger-registry.md`'s map goes, and its row in `move-a-ledger-to-parquet.md`'s completion table is filled.

## 3. The rows

### Row #1 - The first upkeep run after feed health moved is read

- **Scope:** an observation the owner carries. Feed health moved to the door in #1207 (merged 2026-10-03T21:00:51Z). The owner reads the `compact-feed-health` record of the first scheduled `idhazh-gardener.yml` run after that merge from the `gardener` ledger: packing live (`dry_run` false), no failure, the month window only reporting. Then `python backend/utilities/migrate_to_parquet.py --check` over `state` and the three trial roots prints `0 CSV file(s) left` for feed health. A feed-health CSV file a run committed from code older than the merge is migrated under run id `2026-10-03-1`, as the how-to says. Level 0.
- **Files touched:** none, unless a late CSV file is found; then that file and `frontend/public/publication.json`.
- **Acceptance gates:** the two readings above, quoted in the row's report.
- **Oracle:** the gardener ledger's record for that run. It cannot settle a later run; Plan 60 owns the gardener's health.
- **Readings, 2026-10-06:**
  1. The first scheduled run after the merge, 37182327138 on 2026-10-04, failed in every compaction task, feed health's included, with the month fault "a month is not absorbed" that Plan 60 fixed. Nothing in it is particular to feed health. The next scheduled run, 37271019053 on 2026-10-05, filed this `compact-feed-health` record in the `gardener` ledger: `dry_run` false, `stopped_because` `exhausted`, no failure, and the month window 2025-06-01 to 2025-08-31 only reported, because `month_deletes_dry_run` is true. A dispatched run the same morning, 37286849600, packed 5 raw files live and freed 108463 bytes.
  2. `migrate_to_parquet.py --check --ledger feed-health` over `state` and the three trial roots, months 2025-06 to 2026-10, printed `0 CSV file(s) left` and exited 0. No late CSV file was found, so nothing was migrated.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Kept from the 2026-10-03 draft: every move so far was read the same way | The owner, 2026-10-03 |

### Row #2 - The parquet column mapper reads a fixed-choice field

- **Scope:** `_column_type` and `logical_type_of` in `backend/idhazh/ledger/arrow_schema.py` map a `Literal` whose values are all `str` to the string column and logical type, and one whose values are all `int` to the int column. A `Literal` that mixes types, or holds a `bool`, `None` or enum value, is refused by name. Level 2: no ledger with a `Literal` field is on the door until row 4.
- **Files touched** (from a search at c076a221f for `Literal` under `backend/idhazh/ledger/` and for the mapper's tests; search again at dispatch):
  - `backend/idhazh/ledger/arrow_schema.py`
  - `backend/tests/ledger/test_arrow_schema.py` (extended)
- **Acceptance gates:** local: `python -m pytest -n 0 backend/tests/ledger` ; ruff; mypy. CI: the full suite.
- **Oracle:** a unit test that builds the Arrow schema of `StorySimilarityPair` and of a fixture model with an all-int `Literal`, writes one row of each through `ledger.persist` into `tmp_path`, and reads it back equal. It fails today with `TypeError`. A mixed `Literal` is refused with its field name. It cannot settle the frontend's reading; row 4's oracle does.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Teach the mapper, rather than convert the three persisted aliases to `StrEnum` | Fowler, 2026-10-05: one rule in one place, and the three aliases already have `Literal` schemas |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Convert `ScorerModelId`, `JudgeModelId` and `ContentSimilarityJudgeId` to `StrEnum` | Three contract edits and every importer, for no change in what is stored | Three changelog entries and a schema diff with no new meaning | Fowler, 2026-10-05 |

### Row #3 - The CSV code no ledger uses any more is deleted

- **Scope:** delete `ledger.write_segment`, `ledger.extend_segment` and `ledger.day_shard_relpath` in `backend/idhazh/ledger/rows.py`; `DAY_TREES` in `backend/idhazh/contracts/ledger_name.py`; `_TREE_SHAPES` in `backend/idhazh/ledger/keys.py`; `backend/idhazh/gardener/closed_day_fold.py` and the fold branch in `backend/idhazh/gardener/runner.py`; the day-tree paths of `backend/utilities/widen_ledger_header.py`; their tests and the sentences that describe them. Delete the four orphan files `state/span-rollup/2026/10/02/2026-10-02-36985028637-1-work-0{0..3}.csv`: #1189 retired the span summary, nothing reads them, and the person ruled on 2026-10-04 that they go unconverted. Do not edit `backend/utilities/pipeline_test_ledgers.py`: the pipeline-tests plan owns it. Level 2.
- **Files touched** (from the CSV inventory of 2026-10-05; search at dispatch for each deleted name):
  - `backend/idhazh/ledger/rows.py`, `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/gardener/closed_day_fold.py` (deleted), `backend/idhazh/gardener/runner.py`
  - `backend/utilities/widen_ledger_header.py`, `backend/tests/test_widen_ledger_header.py`
  - each test that names a deleted symbol
  - `state/span-rollup/2026/10/02/` (four files deleted)
  - `docs/architecture/contracts/ledger-registry.md` (the two "now" lines of the shared-code table; the orphan count becomes four)
  - `docs/concepts/partitions.md`, `docs/architecture/contracts/state-ledgers.md` (sentences on the fold and day trees)
- **Acceptance gates:** local: `python -m pytest -n 0` on each test file the row edits, plus `backend/tests/gardener` and `backend/tests/contracts/test_ledger_registry.py`; ruff; mypy; `doc_load.py` on each changed page. CI: the full suite.
- **Oracle:** a whole-tree search for each deleted name returns only `TODO/` and git history; `git ls-files state/span-rollup` is empty. It cannot settle the trial roots; Table B, B4.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 2 | `DAY_TREES` goes only after the pipeline-tests plan's row "Readers understand nested trial roots" lands, because that row deletes the day-tree branch of the utility that still names it | Fowler, 2026-10-04 |
| 3 | The private helpers that served only the named writers go with them: `day_shard_path`, `_dated_rows`, `_TreeShape`, `_refuse_outside_day_trees`, `segment_contract`, `segment_key` and `segment_carried`. Each refused every ledger once `DAY_TREES` was empty | Fowler, 2026-10-08 |
| 4 | The fold's switch goes with the fold: `FoldPolicy`, the `fold` block of a retention declaration, its period windows in `gardener/period_inputs.py`, its month rule in the gardener CLI, `FoldSettled`, `TaskFinished.fold` and the run summary's fold line. A knob nothing obeys is a number somebody believes (Guardrail #6), so a declaration that still carries `fold` is refused by name, and `run.settled_fold_after_days` now says nothing replaces it | Fowler, 2026-10-08 |
| 5 | `CollectionPruneRow` keeps `fold_dry_run`, `folded_days`, `folded_files` and `folded_months`, empty on every new row. Removing a persisted field needs a read-side migration (CLAUDE.md section 11) that this Level 2 deletion does not carry, and committed gardener rows still carry the cells | Fowler, 2026-10-08 |

### Row #4 - The judge's scored pairs and its metrics are saved through the door

- **Scope:** D1 and D2 by section 2.6, with F1, F2 and Table G. `Tenant.settle` gains the council's writer identity and hands it to `count_verdicts` ([judge-ledger rule](../docs/architecture/contracts/ledger-registry.md#the-rule-a-judge-ledger-follows-when-it-moves)). `Tenant.committed_paths` names `state/raw/content-similarity-judge/scored-pairs` and `state/raw/content-similarity-judge/metrics` and loses the two CSV folders. The two ledgers move together because one stage writes both. Level 3.
- **Files touched** (from the inventory; search at dispatch for `CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS`, `CONTENT_SIMILARITY_JUDGE_METRICS`, `scored-pairs`, `append_story_similarity_pairs`, `load_story_similarity_pairs`, `ContentSimilarityJudgeMetrics`, `StorySimilarityPair`, `shard`):
  - `backend/idhazh/contracts/ledger_name.py`, `backend/idhazh/contracts/story_similarity_pair.py`, `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/stages/count_verdicts.py`, `backend/idhazh/stages/set_merge_line.py`, `backend/idhazh/similarity/applied.py`, `backend/idhazh/similarity/tenant.py`, `backend/idhazh/council/metrics_sink.py`, `backend/idhazh/council/session.py` (identity hand-off)
  - `backend/idhazh/ledger/rows.py`, `backend/idhazh/ledger/keys.py`, `backend/idhazh/ledger/settle.py`, `backend/idhazh/ledger/staging.py`, `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/path_classes.py`, `backend/idhazh/telemetry/prune.py`
  - `backend/utilities/ledger_migration/csv_layouts.py`
  - `config/ledgers.json`, `config/gardener/compact-content-similarity-judge-scored-pairs.json` (new), `config/gardener/compact-content-similarity-judge-metrics.json` (new), `config/idhazh_gardener.json`, `.gitattributes`
  - `frontend/src/lib/data/slice-shapes.ts`
  - tests: `backend/tests/contracts/test_story_similarity.py`, `backend/tests/contracts/test_content_similarity_judge_metrics.py`, `backend/tests/council/test_metrics_sink.py`, `backend/tests/test_similarity_counting.py`, `backend/tests/test_similarity_judge.py`, `backend/tests/test_similarity_fit.py`, `backend/tests/ledger/test_lifecycle.py`, `backend/tests/ledger/test_persist.py`, `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`, `backend/tests/contracts/test_ledger_registry.py`, `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/retention/test_union_safe_repeats.py`, `backend/tests/retention/test_prune_range.py`, `backend/tests/ledger_migration/test_csv_layouts.py`, and the contract fixtures under `tests/fixtures/contracts/` for the two contracts
  - docs: `ledger-registry.md`, `move-a-ledger-to-parquet.md`, `schemas.md`, `docs/architecture/publishing/llm-council.md`, `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local: `python -m pytest -n 0` on every test file above plus `backend/tests/council`; `npm --prefix frontend run test:changed -- --list` and the selected specs; ruff; mypy; `doc_load.py`. CI: the full suite. Named observation: the first `llm-council.yml` night after merge commits raw files under `state/raw/content-similarity-judge/scored-pairs/` and `state/raw/content-similarity-judge/metrics/` and no CSV file under `state/content-similarity-judge/`.
- **Oracle:** an integration test in `backend/tests/council/test_session.py` or `backend/tests/test_similarity_counting.py`: a fixture night's `settle` with `--commit <sha>` leaves one raw file per judged date for each ledger, read back through `ledger.load_days` with `work_part_index` per part and the identity of Table E, E1; `set_merge_line` then reads those rows. It fails today because `count_verdicts` appends CSV. It cannot settle a real night; the named observation reads that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Two commits: (1) behavioural: declare, write and read through the door; (2) structural, Remove Dead Code: the CSV writer, loader and settlement entries | Fowler, 2026-10-05 |
| 2 | The rename of `shard` ships here, not earlier ([judge-ledger rule](../docs/architecture/contracts/ledger-registry.md#the-rule-a-judge-ledger-follows-when-it-moves)) | The owner, 2026-10-04 |
| 3 | Does not wait for row 3. Both edit `rows.py`, `keys.py` and `ledger-registry.md`, but neither reads what the other writes, so whichever is ready first merges first and the other merges `main` | Fowler, 2026-10-06 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Five top-level families (`similarity-scored-pairs` and four more), the draft of this plan | The owner chose the nest: the folder layout stays, and the door learns a rule of any depth once (row 11) instead of five families, five renamed members and every importer | Five families in `config/ledgers.json`, five renames, and a layout that no longer groups the judge | The owner, 2026-10-05 |
| 2 | One row for all four judge ledgers | Three different writers and two frontend readers in one review | A diff no reviewer reads whole | Fowler, 2026-10-05 |

### Row #5 - The fitted merge line is saved through the door

- **Scope:** D3 by section 2.6. `set_merge_line` persists with E3's identity; `applied.applied_line` reads through `ledger.load_days` over its lookback; `frontend/src/lib/server/similarity-ledger.ts` reads through `sliceFromDisk`. Level 3.
- **Files touched** (search at dispatch for `CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS`, `fitted-thresholds`, `append_fitted_thresholds`, `load_fitted_thresholds`, `readDayShards`): the shared files of row 4's list that name this ledger; `backend/idhazh/contracts/fitted_similarity_threshold.py` (`DROPPED_CELLS` stays for the migrator until row 10); `backend/idhazh/stages/set_merge_line.py`; `backend/idhazh/similarity/applied.py`; `config/gardener/compact-content-similarity-judge-fitted-thresholds.json` (new); `frontend/src/lib/server/similarity-ledger.ts`; its spec under `frontend/tests/`; the console panel's spec that reads the fitted line.
- **Acceptance gates:** local: the backend tests that name the ledger, `npm --prefix frontend run test:changed` selection; the browser smoke of the console page that shows the fitted line, with and without a compact file; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** a fixture night writes a fitted line through the door, compacts it into `tmp_path`, and the frontend reader returns the same values. It fails today. It cannot settle the days between a write and the gardener's next pack; decision 1 prices that.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The frontend reads packed days only (`sliceFromDisk`), as every door ledger does, so a line is shown from the gardener's next pack, at most one day after it is written | Fowler, 2026-10-05: one read path for every ledger; the line moves once a night |
| 2 | Merges right after a `digest.yml` run ends, and the plan's owner lands this ledger's copy before the next digest or council run (row 9, decision 2) | Fowler, 2026-10-08 |

### Row #6 - The merge line's holdout score is saved through the door

- **Scope:** D4 by section 2.6, with D8. `score_merge_line_holdout._append` becomes one `ledger.persist` call with E4's identity. `similarity-holdout.ts` reads the scores through `sliceFromDisk`. `ServerJob.OPERATOR` and the frontend's `SERVER_JOB` copy gain `operator`. Level 3.
- **Files touched** (search at dispatch for `CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES`, `merge-line-holdout-scores`, `ServerJob`): `backend/idhazh/contracts/base.py`; `backend/idhazh/stages/score_merge_line_holdout.py`; `backend/idhazh/cli.py` (`--commit` for the stage); `frontend/src/lib/server/host-fingerprint.ts`; `frontend/src/lib/server/similarity-holdout.ts`; `config/gardener/compact-content-similarity-judge-merge-line-holdout-scores.json` (new); `docs/reference/host-metrics.md` (`operator`); `docs/how-to/label-the-similarity-holdout.md`; the shared files of section 2.6; `backend/tests/contracts/test_merge_line_holdout_score.py`; `backend/tests/contracts/test_frontend_vocabularies.py`.
- **Acceptance gates:** local: the tests above, the selected frontend specs, the browser smoke of the holdout panel; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** `score-merge-line-holdout --run-id <id> --labeller <name> --commit <sha>` over a fixture state root leaves one raw file read back with job `operator`. It fails today.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `operator` joins `ServerJob` with a docstring line, as `migrate` did: the door names every file's writer from that set, and a person's command has no workflow job | Fowler, 2026-10-05 |
| 2 | Runs beside rows 4 and 5, not after them. The stage reads the fitted line through `applied.effective_same_story` and the marks through `holdout.marked_pairs`, and this row changes only its writer, so it shares no read or write with rows 4 and 5. Row 7 still follows it, because both edit `score_merge_line_holdout.py` and `similarity-holdout.ts` | Fowler, 2026-10-06 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Run the holdout score in a workflow job so it has a job id | A person marks the holdout and chooses when to score it | A new workflow, dispatch inputs for the labeller, and a push from CI | Fowler, 2026-10-05 |

### Row #7 - The holdout marks are saved through the door

- **Scope:** D5 by section 2.6 and E5. The owner's directive rules that a program writes the marks: `sample_sheet --harvest` already writes the whole file from the labels, so it now persists the rows of one harvest with `covers` the `--labelled-on` day and a new required `--run-id`. Readers settle on `(left_url, right_url)` with the newest `marked_on`. `similarity/holdout.marked_pairs` and `similarity-holdout.ts` read the ledger over a configured reach, `similarity.holdout_reach_days` in `config/idhazh.json`, default 730, so the read has a fixed-size input (Guardrail #12); every mark at c076a221f is inside it. The migrator gains a flat-file layout whose day comes from a named column (`marked_on`), used once in row 9. `check_seeded_ledgers.py` loses the holdout check. Level 3.
- **Files touched** (search at dispatch for `holdout-pairs`, `HOLDOUT_PAIRS`, `marked_pairs`, `loadMarkedPairs`, `harvest`): `backend/utilities/sample_sheet.py`; `backend/idhazh/similarity/holdout.py`; `backend/idhazh/stages/score_merge_line_holdout.py`; `backend/utilities/build_canary_day.py`; `backend/utilities/check_seeded_ledgers.py`; `backend/utilities/ledger_migration/` (flat layout); `config/idhazh.json` and its config model; `config/gardener/compact-content-similarity-judge-holdout-pairs.json` (new); `frontend/src/lib/server/similarity-holdout.ts`; `frontend/tests/console.spec.ts`; `backend/tests/test_similarity_judge.py`; `backend/tests/test_sample_sheet.py`; the shared files of section 2.6; `docs/how-to/label-the-similarity-holdout.md`, `docs/architecture/publishing/autotune-content-similarity.md`, `docs/architecture/contracts/schemas.md`, `docs/concepts/growing-reads.md`, `docs/reference/repository-layout.md`, `docs/architecture/contracts/persistence.md`.
- **Acceptance gates:** local: the tests above, the selected frontend specs, the browser smoke of the holdout panel with and without data; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** two harvests on two days over a fixture, the second re-marking one pair, read back through `marked_pairs` as one row per pair with the second mark. It fails today because harvest rewrites a CSV file.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The marks move: a program writes them, and the owner's directive leaves no CSV ledger | Fowler, 2026-10-05, under the owner's directive of 2026-10-05 |
| 2 | A reach of 730 days, not "for ever": a read that grows with the archive is refused (Guardrail #12). A mark older than the reach stops counting until a person re-marks it or widens the knob | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the marks as a hand-edited CSV | The directive leaves no CSV ledger, and no person edits it by hand: `--harvest` writes it | A CSV reader, a `merge=text` line and a seeded-ledger check kept for one file | The owner, 2026-10-05 |
| 2 | A key that includes the day | A re-marked pair would count twice | A wrong holdout score | Fowler, 2026-10-05 |

### Row #8 - The item health summary is saved through the door

- **Scope:** D6 by section 2.6 and E6. `telemetry_aggregate` persists each due month's summary rows; "already summarised" becomes "a raw file of this ledger exists for that month"; the `month` grain leaves the registry entry. No committed file exists, so there is no data commit and no migrator entry. The retention walk of the old public `.csv` month copies (`named_trees.month_files`) stays while Table B, B3 stands. Level 3.
- **Files touched** (search at dispatch for `ITEM_HEALTH_SUMMARY`, `item-health-summary`, `write_item_health_summary`, `load_item_health_summary`): `backend/idhazh/gardener/tasks/telemetry_aggregate.py`; `backend/idhazh/ledger/rows.py`; `backend/idhazh/ledger/keys.py`; `backend/idhazh/ledger/staging.py`; `config/ledgers.json`; `config/gardener/telemetry-aggregate.json`; `config/gardener/compact-item-health-summary.json` (new); `config/idhazh_gardener.json`; `frontend/src/lib/data/slice-shapes.ts`; `backend/tests/gardener/tasks/test_telemetry_aggregate_task.py`; `backend/tests/gardener/test_period_inputs.py`; `backend/tests/gardener/test_named_trees.py`; `docs/concepts/adaptive-pruning.md`; `ledger-registry.md`.
- **Acceptance gates:** local: the tests above plus `backend/tests/contracts/test_gardener_config.py`; ruff; mypy; `doc_load.py`. CI: the full suite.
- **Oracle:** the aggregate task over a fixture state root with one due month writes one raw file per day of that month, read back equal to the summary; a second pass writes nothing. It fails today because the task writes a month CSV.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The summary moves with no month layout in the migrator: it has no committed file | Fowler, 2026-10-05 |
| 2 | Runs before row 3: the dependency was a shared-file merge order, and row 3 waits on work outside this plan | Fowler, 2026-10-06 |

### Row #9 - The committed judge rows move onto the door, and the old CSV files go

- **Scope:** the plan's owner moves the committed judge rows in two phases, by [move-a-ledger-to-parquet.md](../docs/how-to/move-a-ledger-to-parquet.md). Level 4.
  1. **Copy, one ledger at a time, while writers continue** ([the copy](../docs/how-to/move-a-ledger-to-parquet.md#copy-while-writers-continue)). When a ledger's code row merges, `migrate_to_parquet.py --plan` and then `--write --raw-only` copy that ledger's committed CSV months into raw door files. The run id is the copy's UTC date followed by `-1`, and the SHA is the merged code's. Each copy is a pull request of its own. The gardener's next wake packs the copied days, and `--verify` then proves them. No quiet window is needed, because the CSV files and the old writer both stay.
  2. **Retire, all five together** ([the retirement](../docs/how-to/move-a-ledger-to-parquet.md#retire-csv-after-the-old-writer-is-retired)). Retirement waits until four things are true. Rows 4 to 7 have merged. Every copy is proved. No `llm-council.yml` run that started on older code is still running. The pipeline-tests plan's trial-file row is not moving data at the same time. Then `--retire`, and after it `--check` over `state`, prints `0 CSV file(s) left` for each of D1 to D5, in one data commit. The `content-similarity-judge` folder then keeps only D7's two JSON ledgers.
- **Files touched:** the copies add `state/raw/content-similarity-judge/<ledger>/` for D1 to D5, which the gardener packs into `state/compact/content-similarity-judge/<ledger>/`. The retirement removes the CSV files under `state/content-similarity-judge/`: 47 files at f804d8713, which are 20 scored-pairs days, 6 metrics days, 19 fitted-line days, 1 holdout-score day and the marks file. It also changes `frontend/public/publication.json` if that file names a removed path.
- **Acceptance gates:** each copy's pull request quotes its `--plan` and `--write --raw-only` output. Its `--verify` output after the gardener packs is quoted in this row's report. The retirement commit quotes `--retire` and `--check`, with Table G's drop counts (G2). CI runs on each.
- **Oracle:** `--verify` reads every copied row back equal to its CSV row under Tables F and G. It cannot see a CSV row that an older-code run writes after the copy; `--retire` re-proves every source in one process, and that catches it.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Copy first, retire later, as the council's move did, replacing the draft's single data commit in a quiet window. A copy that waits for the last row would leave each moved reader without the history it had | Fowler, 2026-10-08, following [the current procedure](../docs/how-to/move-a-ledger-to-parquet.md) |
| 2 | D3's copy lands before the next `digest.yml` or `llm-council.yml` run after row 5 merges, so row 5 merges right after a digest run ends. Until the copy lands, `applied.applied_line` finds no fitted line in its lookback, a build falls back to the committed floor, and `set_merge_line` measures its next fit from that floor. D1 and D2 have no such gap: `set_merge_line` reads only the scored pairs of the date it judges, and the same night writes those through the door | Fowler, 2026-10-08 |
| 3 | D4 and D5 are written by a person's command, so their old writer is the old code on a person's machine. Their retirement assumes that the person runs the command from `main` at or after the row that moved it | Fowler, 2026-10-08 |

### Row #10 - The CSV ledger code, the migrator and their pages are deleted

- **Scope:** delete what has no user once rows 3 to 9 and the pipeline-tests plan's trial-file row have landed: `ledger.extend_ledger_file` and the CSV ledger parts of `backend/idhazh/ledger/csv_file.py` (the `csv_row` and `from_csv_row` codec stays for Table B, B2); `backend/idhazh/day_shards.py`; the CSV parts of `backend/idhazh/ledger/settle.py`; `_TARGET_LEDGERS` in `telemetry/prune.py`; `UNION_SAFE` and the CSV path classes in `path_classes.py`; the CSV walks of `gardener/named_trees.py` and `gardener/retention_files.py` that no task calls; the grain `day` and `month` and the four builders' CSV branches in `ledger/paths.py` and `contracts/ledgers.py`; `backend/utilities/ledger_migration/`, `backend/utilities/migrate_to_parquet.py`, `backend/tests/ledger_migration/` and `tests/fixtures/day-shard-migration/`; `readDayShards` and `frontend/tests/day-shards.spec.ts` with `frontend/tests/fixtures/day-shards/`; every `DROPPED_CELLS` and `old_headings` entry only the migrator read; each CSV fixture whose only reader goes (Table B, B6); `docs/how-to/move-a-ledger-to-parquet.md`, with every link to it repointed to `persistence.md`; the "Ledgers outside raw and compact" section of `ledger-registry.md`; and the CSV sentences of `persistence.md`, `state-ledgers.md`, `partitions.md`, `telemetry.md`, `telemetry-intent.md` (N1, N6 and N11 met) and `host-metrics.md`. Level 3.
- **Files touched:** the list above; search at dispatch for `extend_ledger_file`, `day_shards`, `readDayShards`, `UNION_SAFE`, `_TARGET_LEDGERS`, `ledger_migration`, `migrate_to_parquet`, `Grain.DAY_FILE`, `Grain.MONTH_FILE`, `merge=union`, `old_headings`, `DROPPED_CELLS` and `.csv`.
- **Acceptance gates:** local: `python -m pytest -n 0` on every test directory the row edits; `npm --prefix frontend run test:changed` selection; ruff; mypy; `doc_load.py` on each changed page. CI: the full suite.
- **Oracle:** a new contract test, `backend/tests/contracts/test_no_csv_ledger_is_left.py`: every ledger in `config/ledgers.json` has grain `raw-and-compact`, `flat` or `stamp`, and none has suffix `.csv`; `.gitattributes` holds no `merge=union` line; `git ls-files "state/*.csv"` is empty in the merge candidate (a named-command read, fixed by the registry, not a walk). It fails today on seven ledgers. It cannot settle Table B's out-of-scope files, which it does not read.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The how-to for moving a ledger goes with the migrator: a procedure nobody can run is a page that misleads | Fowler, 2026-10-05 |
| 2 | Two commits: (1) backend and frontend code with tests; (2) docs | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the migrator for a future ledger | No ledger is left to move, and every new ledger is born on the door | A package, a CLI and a test directory nobody runs | Fowler, 2026-10-05 |

### Row #11 - The door files a ledger under a folder of any depth

- **Scope:** declare D10 to D14 and make every door path follow them. Today `contracts/ledgers.py` line 129 refuses a `raw-and-compact` prefix other than `[<value>]`, and the door's builders join `ledger.value` as one folder. After this row, one function in `backend/idhazh/ledger/paths.py` returns a door ledger's folders from the registry, and every builder, reader and gardener task asks it rather than spelling `ledger.value` into a path. No ledger is moved and no committed file changes: every door ledger today has the prefix `[<value>]`, so every path it builds is the same before and after. Level 3: it changes how the backend, the gardener and the frontend address every door ledger.
- **Files touched** (search at dispatch for `ledger.value`, `ledger_name.value`, `which.value`, `.name.value` and `${ledger}` in a path; the list below is from `main` at c076a221f):
  - `backend/idhazh/contracts/ledgers.py` (the prefix check, D10; the nesting refusal, D12; the member spelling check, D14)
  - `backend/idhazh/ledger/paths.py` (the folder function; `raw_root`, the compact file, index and watermark builders)
  - `backend/idhazh/ledger/persist.py`, `ledger_files.py`, `raw_files.py`, `day_removal.py`, `lifecycle.py`, `keys.py` (each path it spells from the value)
  - `backend/idhazh/gardener/compaction.py`, `ledger_marks.py`, `period_inputs.py` (the folder-to-ledger lookup at line 294 reads the registry rather than `LedgerName(<folder>)`), and `gardener/tasks/_compact_tree.py`, `_daily_period.py`, `_monthly_period.py`, `_yearly_period.py`
  - `frontend/src/lib/data/slice-shapes.ts` (`LEDGER_FOLDERS`, empty until row 4), `frontend/src/lib/data/slice-reader.ts` (the four path builders at lines 79 to 101 read the folder)
  - `.gitattributes` (`state/compact/*/index/*.json` and `state/compact/*/*/watermark.json` become `**` patterns)
  - tests: `backend/tests/contracts/test_ledger_registry.py`, `backend/tests/contracts/test_frontend_vocabularies.py`, `backend/tests/ledger/test_persist.py`, `backend/tests/gardener/` (the compaction tests), `frontend/tests/ledger-door.spec.ts`, and a new `backend/tests/ledger/test_nested_door_folder.py`
  - docs: `docs/architecture/contracts/ledger-registry.md` (the "nested folder name" blocker goes; the prefix rule gains D10 and D12), `docs/architecture/contracts/persistence.md` (the path grammar names `<folders>`, not `<ledger>`)
- **Acceptance gates:** local: `python -m pytest -n 0` on every test file above plus `backend/tests/gardener` and `backend/tests/ledger`; `npm --prefix frontend run test:changed -- --list` and the selected specs; ruff; mypy; `doc_load.py` on each changed page. CI: the full suite.
- **Oracle:** `backend/tests/ledger/test_nested_door_folder.py` loads a fixture registry under `tests/fixtures/ledger-door/` that files `CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS` two folders deep and `CONTENT_SIMILARITY_JUDGE_METRICS` three folders deep (`content-similarity-judge/deep/metrics`). Under `tmp_path`, each ledger persists one day, compacts it and reads it back through `ledger.load_days`, and every file sits under its declared folder and nowhere else. The same file proves that the registry refuses a door ledger inside another door ledger's folder (D12) and a prefix that does not end with the value (D10). It fails today because line 129 refuses both fixture prefixes. It cannot prove the browser reads a nested ledger, because `LEDGER_FOLDERS` is empty here. Row 5's frontend spec proves that over D3, the first nested ledger the site reads.

**Decisions**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | No depth limit: the prefix holds as many folders as the family needs | The owner, 2026-10-05 |
| 2 | The folder comes from the registry, not from a `/` inside the value: the value stays the name the envelope and the frontend vocabulary already carry | Fowler, 2026-10-05 |
| 3 | A row of its own, ahead of row 4: one review reads the rule, and row 4 reads only the move | Fowler, 2026-10-05 |

**Rejected alternatives**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Put the folder in the value (`"content-similarity-judge/scored-pairs"`) | It renames five members' values, every envelope's `ledger` field and the frontend vocabulary, for a path the registry already holds | A persisted-field change on every judge file and a migration | Fowler, 2026-10-05 |
| 2 | Allow exactly one extra folder | The owner ruled out a fixed depth | A second change the day a family needs a third folder | The owner, 2026-10-05 |
