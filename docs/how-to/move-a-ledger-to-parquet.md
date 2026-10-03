# Move a ledger to Parquet

**Last Updated**: 2026-10-02

How do I move one ledger from CSV to the ledger door without losing a row?

This procedure is project-specific because it names this repository's ledger contract and migration command. A move has two commits. The code commit changes the writer and reader. The migration commit moves the committed data after the code is on `main`. The migration commit is last, and it is made in a quiet window when no pipeline or upkeep run can write another CSV file.

## Complete the code change

Read the ledger's contract, its registry entry, its CSV writer and readers, and its compaction declaration. The ledger's registry entry must use `raw-and-compact`. Its `compact-<ledger>` declaration must exist and retain at least the old CSV retention window. The migrator refuses a missing door entry, a missing compaction, or a compaction that could discard data the CSV window kept.

A move is complete only when every applicable part below holds.

| Part | Complete when | Check |
| --- | --- | --- |
| Registry | The ledger has the intended entry in `config/ledgers.json`. | `backend/tests/contracts/test_ledger_registry.py` |
| Door table | `backend/idhazh/ledger/keys.py` declares the ledger, and neither legacy tree table names it. | The registry and door-shape tests in `backend/tests/ledger/` |
| Writers | Every writer uses `ledger.persist` with its writer identity. Each workflow command that writes passes `--commit`. | `backend/tests/workflows/test_ledger_door_jobs.py` |
| Backend readers | Each reader uses the door and keeps its existing answer. | The ledger's row tests |
| Console readers | Every declared ledger is already in `LEDGER_NAMES`; a page may read one once `ledger.published` names it. | `backend/tests/contracts/test_frontend_index_shapes.py` |
| Compaction | `config/gardener/compact-<ledger>.json` declares the ledger's periods and windows. | `config.load_gardener()` and the compaction tests |
| Migration | Every CSV day in `state/` and each named trial root reads back cell for cell before any CSV is deleted. | `backend/tests/ledger/test_migrate_to_parquet.py` and `--check` |
| Retention | The old retention declaration, task and tests are removed when they no longer have a reader. | The retention and contract tests |
| Union | A retired CSV union entry is removed when the ledger no longer needs it. | `backend/tests/workflows/test_daily_commit_steps.py` and union tests |
| Prune | The prune command reaches the ledger, or its declaration refuses pruning by name. | The prune tests |
| CSV code, tests and docs | No live code or documentation describes the ledger's old CSV path or reader. | Search the row's named old-layout terms |
| Packing | Migration packs every period the declaration admits, the live window only reports drops, and the next upkeep wake succeeds. | Compaction tests and the owner's first-wake read |

A test reads a bounded fixture under `tmp_path`, not the growing production state tree. It uses real row and file contracts, and it does not access the network.

## Move the committed files

The code pull request does not contain migrated production data. Merge the code first. The owner then makes the data commit last, after checking that no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running. Check again just before the merge. If a run is active, wait for it and repeat the migration against the final code.

Run the migrator from the checked-out code commit. Pass every root that can still hold this ledger's CSV. `--state-dir` and `--ledger` both repeat. The run id is the UTC date of the migration commit followed by `-1`; the SHA is the full commit id of the code being run.

```text
python backend/utilities/migrate_to_parquet.py --state-dir state --state-dir state/pipeline-tests --state-dir state/pipeline-tests-no-visual-plan --state-dir state/pipeline-tests-production-settings --run-id <UTC-DATE>-1 --git-sha <FULL-CODE-COMMIT-SHA> --ledger <LEDGER-NAME>
```

List only trial roots that hold this ledger. A root other than the repository's `state/` is written raw and is never packed. The state root runs the declared compaction task with packing live and its monthly deletion window in report-only mode. The migrator repeats that task until a pass writes and deletes no period. This packs admitted days, months and years without pruning ledger rows. Include a ledger with no CSV in `state/` when it still needs its existing raw or compact files packed.

The migrator reads each layout it declares: a day tree, `YYYY/MM/DD/*.csv`, or a shared day file, `YYYY/MM/DD.csv`. A row with a date must name the day in its path. A row without a date uses the day in its path. Any other layout or invalid row stops the run. The migrator reads back every named day through the ledger door and compares every cell with the planned rows. It deletes no CSV in any root until every day in every root passes.

Run the same roots and ledger list with `--check` after migration. It must print `0 CSV file(s) left` and exit 0. Run a dry compaction pass for each ledger moved in `state/`; it must have no period left to pack. Stage only the intended CSV deletions and new `state/raw/` and `state/compact/` files. Do not add trial-root compact files. Push the data commit and wait for its selected CI checks to pass.

After the merge, run `--check` again over `state/` and every trial root in the next quiet window. A CSV file found then belongs in a follow-up migration commit under the same row and run id.

## See also

- [The ledger door](../architecture/contracts/persistence.md) - what the door writes and reads.
- [The ledger registry](../architecture/contracts/ledger-registry.md) - each ledger's address and lifecycle.
- [Run the gates](run-the-gates.md) - local checks and CI coverage.
- [Ship a pull request](ship-a-pr.md) - branch, commit and review steps.
- [Documentation structure](../reference/documentation-structure.md) - where current rules belong.
- [CLAUDE.md](../../CLAUDE.md) - sections 2, 8, 9, 11 and 13.
