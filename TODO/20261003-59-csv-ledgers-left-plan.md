# The ledgers left on CSV move to the door, and the CSV code with no user goes

**Status**: draft, opened 2026-10-03 when the plan "Five ledgers leave CSV" closed, to receive what that plan handed on. It is not execution-ready. Before any row is dispatched, the owner makes it execution-ready with the prepare-plan skill (`.claude/skills/prepare-plan/SKILL.md`), and the person answers the rulings row 3 lists.

**What it is for.** Ten ledgers now write through the ledger door. Seven are still stored as CSV files, and some shared CSV code has no user left. Both are mapped in [ledger-registry.md](../docs/architecture/contracts/ledger-registry.md#ledgers-outside-raw-and-compact): each ledger with what blocks its move, and each piece of CSV code with the user it waits for. This plan is where that map becomes work.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The first upkeep run after feed health moved is read | - | A | PENDING | - | - | - |
| 2 | The CSV code no ledger uses any more is deleted | - | A | PENDING | - | - | - |
| 3 | The person rules on what blocks each ledger left on CSV | - | A | PENDING | - | - | - |
| 4 | The five ledgers with a union driver move to the door | 3 | B | PENDING | - | - | - |
| 5 | The item health summary moves to the door, or stays CSV by ruling | 3 | B | PENDING | - | - | - |

## 2. The rows

### Row #1 - The first upkeep run after feed health moved is read

Feed health moved to the door in #1207, merged 2026-10-03T21:00:51Z. Its compaction, `config/gardener/compact-feed-health.json`, has not run yet: the first scheduled `idhazh-gardener.yml` run after the merge is its first. The owner reads that run's `compact-feed-health` record from the `gardener` ledger, the way the other moves were read: packing live (`dry_run` false), no failure, and the 14-month window only reporting. Then `migrate_to_parquet.py --check`, over `state` and the three trial roots for every UTC month they hold, must still print `0 CSV file(s) left`. A digest run that checked out code from before the merge can still commit one CSV file of feed health; that file is migrated under run id `2026-10-03-1`, as [move-a-ledger-to-parquet.md](../docs/how-to/move-a-ledger-to-parquet.md) says, and `frontend/public/publication.json` loses its path.

### Row #2 - The CSV code no ledger uses any more is deleted

Since feed health moved, no ledger files its rows as a day tree, so `DAY_TREES` is empty, and no retention declaration asks for a fold. These pieces have no user: `ledger.write_segment`, `ledger.extend_segment` and `ledger.day_shard_relpath` in `backend/idhazh/ledger/rows.py`, `DAY_TREES` in `backend/idhazh/contracts/ledger_name.py`, `_TREE_SHAPES` in `backend/idhazh/ledger/keys.py`, and `backend/idhazh/gardener/closed_day_fold.py` with the fold branch in `backend/idhazh/gardener/runner.py`. Only their own tests and the two utilities that walk day trees, `backend/utilities/pipeline_test_ledgers.py` and `backend/utilities/widen_ledger_header.py`, still name them. The row deletes them, their tests and the pages that describe them, except the day-tree branch of `backend/utilities/pipeline_test_ledgers.py`: the plan "Pipeline-test state nests under state/pipeline-tests, with a reusable migration tool" (`TODO/20261004-pipeline-tests-migration-plan.md`) deletes that branch in its row "Readers understand nested trial roots" and edits the utility again in its row "Pipeline-test writers use separate nested cases". So this row deletes `DAY_TREES` only after the first of those rows lands, and does not edit the utility.

This row also deletes the four `span-rollup` CSV files under `state/span-rollup/2026/10/02/`. #1189 retired the span summary on purpose, with its producer, its console reader, its published folder, its contract and its registry entry; these files are what runs that started before it merged left behind, and nothing reads them. The person ruled on 2026-10-04 that they go unconverted. The four in the two trial roots go in that plan's row "Committed trial files move to the nested roots, and the orphan span summaries are deleted".

### Row #3 - The person rules on what blocks each ledger left on CSV

What each ruling decides is in the map. In short:

- **Field names the file envelope reserves.** Every door file records the `run_id` and `shard` of the job that wrote it. `scored-pairs`, `metrics` and `shard-outcomes` carry `run_id` and `shard` fields of their own, and `fitted-thresholds` and `merge-line-holdout-scores` carry `run_id`. For each, the person rules whether the field means what the envelope means. A field that means something else must be renamed, which changes a persisted contract (CLAUDE.md section 6, Level 5).
- **The nested folder name.** The five sit one folder below their family, as in `content-similarity-judge/scored-pairs`, and the door files a ledger under its own name. The registry needs a rule for that name before any of them moves.
- **`item-health-summary`.** One writer rewrites a whole month file on each run, and the migrator reads only day files. Moving it needs a month layout in the migrator, or a ruling that it stays CSV.
- **`content-similarity-judge/holdout-pairs.csv`** stays CSV while a person edits it by hand. It moves only if the person rules that a program writes it.

### Row #4 - The five ledgers with a union driver move to the door

`content-similarity-judge/scored-pairs`, `fitted-thresholds`, `metrics` and `merge-line-holdout-scores`, and `llm-council/shard-outcomes`, each moved by the procedure in [move-a-ledger-to-parquet.md](../docs/how-to/move-a-ledger-to-parquet.md). The parquet column mapper, `backend/idhazh/ledger/arrow_schema.py`, learns the fixed-choice (`Literal`) fields four of them carry. As each moves, its `merge=union` line and its `UNION_SAFE` entry go, and the prune verb's `_TARGET_LEDGERS` empties. `extend_ledger_file`, the frontend's `readDayShards` and `backend/idhazh/day_shards.py` go with their last user.

### Row #5 - The item health summary moves to the door, or stays CSV by ruling

Whichever row 3 rules. When no ledger a program writes is left on CSV, the migrator, its table and its tests are deleted, as [persistence.md](../docs/architecture/contracts/persistence.md#moving-a-ledger-onto-the-door) says.
