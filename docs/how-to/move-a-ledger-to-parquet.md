# Move a ledger to Parquet

**Last Updated**: 2026-10-04

How do I move one ledger from CSV to the ledger door without losing a row?

This procedure is project-specific because it names this repository's ledger contract and migration command. A move has two commits. The code commit changes the writer and reader. The migration commit moves the committed data after the code is on `main`. The migration commit is last, and it is made in a quiet window when no pipeline or upkeep run can write another CSV file.

## Complete the code change

Read the ledger's contract, its registry entry, its CSV writer and readers, and its compaction declaration. The ledger's registry entry must use `raw-and-compact`. Its `compact-<ledger>` declaration must exist and retain at least the old CSV retention window. The migrator refuses a missing door entry, a missing compaction, or a compaction that could discard data the CSV window kept.

A move is complete only when every applicable part below holds.

| Part | Complete when | Check |
| --- | --- | --- |
| Registry | The ledger has the intended entry in `config/ledgers.json`. | `backend/tests/contracts/test_ledger_registry.py` |
| Door table | `backend/idhazh/ledger/keys.py` declares the ledger, and neither legacy tree table names it. | The registry and door-shape tests in `backend/tests/ledger/` |
| CSV layout | To add another ledger, give its contract `csv_row()` and, for a day tree, `from_csv_row()`; declare its door key in `backend/idhazh/ledger/keys.py`, registry grain `raw-and-compact`, and `compact-<ledger>` declaration listed in `task_names` of `config/idhazh_gardener.json`. Add one `CsvLedger` entry to `CSV_LEDGERS` in `backend/utilities/ledger_migration/csv_layouts.py` naming its old day-tree or shared-day-file layout, retention window and `old_headings` map from old headings to current columns. Reuse the contract's rename map. Family-nested prefixes, month files and all other layouts are refused by name for now. | `backend/tests/ledger_migration/test_csv_layouts.py` |
| Writers | Every writer uses `ledger.persist` with its writer identity. Each workflow command that writes passes `--commit`. | `backend/tests/workflows/test_ledger_door_jobs.py` |
| Backend readers | Each reader uses the door and keeps its existing answer. | The ledger's row tests |
| Console readers | Every declared ledger is already in `LEDGER_NAMES`; a page may read one once `ledger.published` names it. | `backend/tests/contracts/test_frontend_index_shapes.py` |
| Compaction | `config/gardener/compact-<ledger>.json` declares the ledger's periods and windows. | `config.load_gardener()` and the compaction tests |
| Migration | Every CSV day in `state/` and each named trial root reads back cell for cell before any CSV is deleted. | `backend/tests/ledger_migration/` and `--check` |
| Retention | The old retention declaration, task and tests are removed when they no longer have a reader. | The retention and contract tests |
| Union | A retired CSV union entry is removed when the ledger no longer needs it. | `backend/tests/workflows/test_daily_commit_steps.py` and union tests |
| Prune | The prune command reaches the ledger, or its declaration refuses pruning by name. | The prune tests |
| CSV code, tests and docs | No live code or documentation describes the ledger's old CSV path or reader. | Search the row's named old-layout terms |
| Packing | Migration packs every period the declaration admits, the live window only reports drops, and the next upkeep wake succeeds. | Compaction tests and the owner's first-wake read |

A test reads a bounded fixture under `tmp_path`, not the growing production state tree. It uses real row and file contracts, and it does not access the network.

## Move the committed files

The code pull request does not contain migrated production data. Merge the code first. The owner then makes the data commit last, after checking that no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running. Check again just before the merge. If a run is active, wait for it and repeat the migration against the final code.

Run the migrator from the checked-out code commit. Name the roots and UTC months to migrate. `--state-dir`, `--ledger` and the required `--month YYYY-MM` all repeat. The run id is the UTC date of the migration commit followed by `-1`; the SHA is the full commit id of the code being run.

The migrator must import this checkout's code; set the import path to this worktree's backend as described in [Git fixtures and child producers](../reference/agent-notes.md#git-fixtures-and-child-producers).

```text
python backend/utilities/migrate_to_parquet.py --state-dir state --state-dir state/pipeline-tests --state-dir state/pipeline-tests-no-visual-plan --state-dir state/pipeline-tests-production-settings --month <YYYY-MM> --run-id <UTC-DATE>-1 --git-sha <FULL-CODE-COMMIT-SHA> --ledger <LEDGER-NAME>
```

To move the same inputs in separate phases, add exactly one of `--plan`,
`--write`, `--verify` or `--retire` to that command. Keep the roots, ledgers,
months, run id and code SHA the same between phases.

1. `--plan` validates each CSV day and previews its row count, whether it needs
   writing, and whether its root can be packed. It writes nothing. A named
   ledger with no CSV in the selected months reports that fact.
2. `--write` writes raw rows and runs the existing eligible compaction. It
   never deletes CSV. Compaction can replace or delete raw and compact files
   it absorbs; keeping CSV does not make this phase read-only.
3. `--verify` reads the CSV again and proves the rows the ledger reader serves.
   It writes nothing. It refuses missing output for nonempty days, unreadable relevant raw files,
   missing or invalid compact entries and indexes, and incorrect compact row
   counts or sizes. It checks raw files even when a compact file serves the day.
4. `--retire` re-plans and re-verifies every named root and day in the same
   process, then deletes CSV. One refused day leaves every CSV in every root
   untouched. It does not trust a previous proof, saved plan or command result.

With no mode, the command retains the full plan, write, pack, prove and delete
sequence. It uses the same independent source-cell proof before deleting any
CSV across the named roots. `--check` is mutually exclusive with every phase. It checks only
CSV absence; it does not prove output parity.

Every phase exits zero when its named operation completes, including when no
CSV inputs remain. Plan, write, verify, retire and the default full command
exit one on a refusal or failed proof. Check exits one if CSV remains or a
named CSV tree cannot be read. Invalid arguments and combined modes exit two
before any phase runs.
Every mode refuses a named root that is not an existing directory, with exit one.

Only the eight layouts in `CSV_LEDGERS` are supported: `item-health`,
`summary-quality-evals` (old CSV folder `scores`), `host-fingerprint`,
`counterfactual-scores`, `candidate-models`, `feed-health`, `seen` and
`published`. This tool does not migrate `span-rollup` or an undeclared CSV
layout. Moving another shape requires its own contract and reader design first.
Family-nested prefixes such as `content-similarity-judge/scored-pairs` are
supported by the door, but this migrator still does not move committed files at
that depth. `item-health-summary` moved without a migrator entry because no
committed file existed.

Both CSV layouts refuse a filled cell under an unknown heading, a value with
no heading, and conflicting filled values under an old heading and its current
column. Empty cells under unknown headings are allowed. A dropped heading
requires an explicit `old_headings` entry mapped to `None`, added by a person
in a reviewed commit. There are no such declarations for `runner_name`,
`cgroup_peak_bytes`, `max_output_tokens`, `coverage` or `new_fact_rate`.
Their filled CSV cells are refused, even if the contract's legacy reader
would otherwise ignore them.

Verification uses CSV rows as independent evidence for filled cells on the
same record key. A joined row uses the newest contributing row's schema stamp;
verification validates that stamp rather than requiring an older source stamp.
Rows with other keys and cells the CSV left empty can be
retained from existing output. A changed filled source cell cannot pass merely
because planning folded the target back into its expected rows. When the
ledger's preference rule keeps a conflicting target cell instead, verification,
retirement and the default full command all refuse it. Investigate that conflict;
do not delete CSV on the strength of a row count. Without a stored baseline,
these phases cannot prove the original values of retained rows absent from CSV
or cells CSV never supplied.

A raw row from another work unit can also win the ledger's first-row rule over
the migration's merged row. Verification refuses that lost source cell. This
tool does not change the ledger's union rules or another writer's identity.

A repeat with unchanged rows writes no new raw file. A changed or late CSV
uses the same migration work identity and is folded into existing rows. Raw
file ids use the write clock, so this is a row and work-identity guarantee,
not a promise of identical file ids or bytes after a new write.

List only trial roots that hold this ledger. A root other than the repository's `state/` is written raw and is never packed. The state root runs the declared compaction task over only the named months, with packing live and its monthly deletion window in report-only mode. The migrator repeats that task until a pass writes and deletes no selected period. Year packing requires all twelve months of that year to be named. Include a ledger with no CSV in the selected months when it still needs those months' existing raw or compact files packed.

The listing names the selected months' raw and daily folders, their monthly and yearly files, and the fixed index and watermark files, whether each is there or not, and weighs what it finds under them. It never discovers other years or months, and a question about a path it did not name stops the pass. A gap after the daily watermark is refused: include the intervening months instead of advancing the watermark past unprocessed days. Monthly and yearly watermarks cannot skip older periods that still need packing. Name those months too; a completed indexed period outside the selection remains untouched.

The migrator reads each layout it declares: a day tree, `YYYY/MM/DD/*.csv`, or a shared day file, `YYYY/MM/DD.csv`. A row with a date must name the day in its path. A row without a date uses the day in its path. Any other layout or invalid row stops the run. The migrator reads back every named day through the ledger door and compares every cell with the planned rows. It deletes no CSV in any root until every day in every root passes.

Keep writers stopped throughout retirement. The proof does not lock a tree
against another process, and filesystem deletion is not a transaction. A
deletion error can stop cleanup after earlier proven files have been removed.
A header-only CSV day needs no stored output when both the CSV and the door
hold zero rows. Verification passes that same empty-day proof in every mode,
and retirement or the default full command can delete the header-only file.

Run the same roots, months and ledger list with `--check` after migration. It must print `0 CSV file(s) left` and exit 0. Run a dry compaction pass for each ledger moved in `state/`; it must have no period left to pack. Stage only the intended CSV deletions and new `state/raw/` and `state/compact/` files. Do not add trial-root compact files. Push the data commit and wait for its selected CI checks to pass.

After the merge, run `--check` again over `state/` and every trial root in the next quiet window. A CSV file found then belongs in a follow-up migration commit under the same row and run id.

## See also

- [The ledger door](../architecture/contracts/persistence.md) - what the door writes and reads.
- [The ledger registry](../architecture/contracts/ledger-registry.md) - each ledger's address and lifecycle.
- [Run the gates](run-the-gates.md) - local checks and CI coverage.
- [Ship a pull request](ship-a-pr.md) - branch, commit and review steps.
- [Documentation structure](../reference/documentation-structure.md) - where current rules belong.
- [CLAUDE.md](../../CLAUDE.md) - sections 2, 8, 9, 11 and 13.
