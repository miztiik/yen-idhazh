# Move a ledger to Parquet

**Last Updated**: 2026-10-08

How do I move one ledger from CSV to the ledger door without losing a row?

This procedure is project-specific because it names this repository's ledger contract and migration command. A move has an online copy phase and a later retirement phase. The code change lands first. The online copy keeps the CSV source and old writer available while raw ledger files are written, packed and proved. Final retirement needs fresh proof and either evidence that no old writer can return or a named owner ruling on that risk.

## Complete the code change

Read the ledger's contract, its registry entry, its CSV writer and readers, and its compaction declaration. The ledger's registry entry must use `raw-and-compact`. Its `compact-<folder>` declaration must exist and retain at least the old CSV retention window, where `<folder>` is the ledger's door folder with `/` written `-`. The migrator refuses a missing door entry, a missing compaction, or a compaction that could discard data the CSV window kept. A person may decide that the door keeps a ledger for less time than its CSV did. That decision goes in the ledger's `CsvLedger` entry as `shorter_by`, which names who decided and when; it is the only way past that last refusal.

A move is complete only when every applicable part below holds.

| Part | Complete when | Check |
| --- | --- | --- |
| Registry | The ledger has the intended entry in `config/ledgers.json`. | `backend/tests/contracts/test_ledger_registry.py` |
| Door table | `backend/idhazh/ledger/keys.py` declares the ledger, and neither legacy tree table names it. | The registry and door-shape tests in `backend/tests/ledger/` |
| CSV layout | To add another ledger, give its contract `csv_row()` and, for a day tree, `from_csv_row()`; declare its door key in `backend/idhazh/ledger/keys.py`, registry grain `raw-and-compact`, and `compact-<folder>` declaration listed in `task_names` of `config/idhazh_gardener.json`. Add one `CsvLedger` entry to `CSV_LEDGERS` in `backend/utilities/ledger_migration/csv_layouts.py` naming its old day-tree or shared-day-file layout, retention window and `old_headings` map from old headings to current columns. Reuse the contract's rename map. Declared prefixes may contain more than one folder. Month files and all other layouts are refused by name for now. | `backend/tests/ledger_migration/test_csv_layouts.py` |
| Writers | Every writer uses `ledger.persist` with its writer identity. Each workflow command that writes passes `--commit`. | `backend/tests/workflows/test_ledger_door_jobs.py` |
| Backend readers | Each reader uses the door and keeps its existing answer. | The ledger's row tests |
| Console readers | Every declared ledger is already in `LEDGER_NAMES`; a page may read one once `ledger.published` names it. | `backend/tests/contracts/test_frontend_index_shapes.py` |
| Compaction | `config/gardener/compact-<folder>.json` declares the ledger's periods and windows. | `config.load_gardener()` and the compaction tests |
| Migration | Every CSV day in `state/` and each named trial root reads back cell for cell before any CSV is deleted. | `backend/tests/ledger_migration/` and `--check` |
| Retention | The old retention declaration, task and tests are removed when they no longer have a reader. | The retention and contract tests |
| Union | A retired CSV union entry is removed when the ledger no longer needs it. | `backend/tests/workflows/test_daily_commit_steps.py` and union tests |
| Prune | The prune command reaches the ledger, or its declaration refuses pruning by name. | The prune tests |
| CSV code, tests and docs | No live code or documentation describes the ledger's old CSV path or reader. | Search the row's named old-layout terms |
| Packing | Migration packs every period the declaration admits, the live window only reports drops, and the next upkeep wake succeeds. | Compaction tests and the owner's first-wake read |

A test reads a bounded fixture under `tmp_path`, not the growing production state tree. It uses real row and file contracts, and it does not access the network.

## Copy while writers continue

The code pull request does not contain migrated production data. Merge the code first. Keep the CSV files, old writer and its registered family. Do not wait for unrelated workflows to stop, run `--retire`, or use the full command that deletes CSV.

Run the migrator from the checked-out code commit. Name the roots and UTC months to migrate. `--state-dir`, `--ledger` and the required `--month YYYY-MM` all repeat. The run id is the UTC date of the migration commit followed by `-1`; the SHA is the full commit id of the code being run.

The migrator must import this checkout's code; set the import path to this worktree's backend as described in [Git fixtures and child producers](../reference/agent-notes.md#git-fixtures-and-child-producers).

```text
python backend/utilities/migrate_to_parquet.py --state-dir state --state-dir state/pipeline-tests --state-dir state/pipeline-tests/production-settings --state-dir state/pipeline-tests/no-visual-plan --month <YYYY-MM> --run-id <UTC-DATE>-1 --git-sha <FULL-CODE-COMMIT-SHA> --ledger <LEDGER-NAME>
```

To move the same inputs in separate phases, add exactly one of `--plan`,
`--write`, `--verify` or `--retire` to that command. Keep the roots, ledgers,
months and run id the same on repeats. Use the current code SHA each time.

1. `--plan` validates each CSV day and previews its row count, whether it needs
   writing, and whether its root can be packed. It writes nothing. A named
   ledger with no CSV in the selected months reports that fact.
2. `--write --raw-only` writes only the migration-owned raw rows. It keeps every
   CSV byte and leaves every compact file unchanged, including under the
   production `state/` root. Use this for the online copy. The option is valid
   only with explicit `--write`; every other combination exits 2 before a
   phase runs. Its success report says that packing and parity proof remain
   outstanding. A raw-only write does not prove that the normal reader serves
   the imported rows.
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

After raw-only writing, pack through the existing guarded gardener publication
path. Then run `--verify` against the fresh committed state. If a relevant CSV
source changes, repeat the import with the same run id and the current code
SHA, pack again, and prove again. Keep the CSV and old writer until the final
retirement gate below passes.

Every phase exits zero when its named operation completes, including when no
CSV inputs remain. Plan, write, verify, retire and the default full command
exit one on a refusal or failed proof. Check exits one if CSV remains or a
named CSV tree cannot be read. Invalid arguments and combined modes exit two
before any phase runs.
Every mode refuses a named root that is not an existing directory, with exit one.

Only the eleven layouts in `CSV_LEDGERS` are supported: `item-health`,
`summary-quality-evals` (old CSV folder `scores`), `host-fingerprint`,
`counterfactual-scores`, `candidate-models`, `feed-health`, `seen`,
`published`, and three of the similarity judge's ledgers, each one shared file
a day inside its family's folder:
`content-similarity-judge/merge-line-holdout-scores`,
`content-similarity-judge/scored-pairs` and `content-similarity-judge/metrics`.
This tool does not migrate `council-run-records`, `span-rollup` or an
undeclared CSV layout. Moving another shape requires its own contract and
reader design first. The reader supports a declared day tree or shared day file
under a multi-folder prefix. It does not infer an undeclared layout.
`item-health-summary` moved without a migrator entry because no committed file
existed.

Both CSV layouts refuse a filled cell under an unknown heading, a value with
no heading, and conflicting filled values under an old heading and its current
column. Empty cells under unknown headings are allowed. A dropped heading
requires an explicit `old_headings` entry mapped to `None`, added by a person
in a reviewed commit. The scored-pairs entry has three: `decode_digest`,
`key_point` and `key_point_weight`, the headings its contract stopped naming.
There are no such declarations for `runner_name`,
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

List only trial roots that hold this ledger. `state/` uses the production
`compact-<folder>` declaration; another root is packed only when
`compact-trial-<folder>` names it in `state_roots`. A root with no matching
trial declaration is written raw. Each declared compaction runs over only the
named months, with packing live and its monthly deletion window in report-only
mode. The migrator repeats that task until a pass writes and deletes no selected
period. Year packing requires all twelve months of that year to be named.
Include a ledger with no CSV in the selected months when it still needs those
months' existing raw or compact files packed.

The listing names the selected months' raw and daily folders, their monthly and yearly files, and the three index files, whether each is there or not, and weighs what it finds under them. It never discovers other years or months, and a question about a path it did not name stops the pass. A gap after the daily mark, the newest day the indexes give, is refused: include the intervening months instead of moving the mark past unprocessed days. The monthly and yearly marks cannot skip older periods that still need packing either. Name those months too; a completed indexed period outside the selection remains untouched.

The migrator reads each layout it declares: a day tree, `YYYY/MM/DD/*.csv`, or a shared day file, `YYYY/MM/DD.csv`. A row with a date must name the day in its path. A row without a date uses the day in its path. Any other layout or invalid row stops the run. The migrator reads back every named day through the ledger door and compares every cell with the planned rows. It deletes no CSV in any root until every day in every root passes.

## Retire CSV after the old writer is retired

The online copy does not authorize deletion. First satisfy the ledger's
retirement gate: old-code writers have finished, captured output has been
accounted for, and the current source has been imported, packed and proved.
Also establish that an old writer cannot return, or record the owner's explicit
approval to retire without that wait. Keep the CSV, family and old-row reader
until the evidence and any required ruling are complete.

When a council run fails, inspect the failed stage and recover any completed
output before its artifacts expire. A failed run does not prove that its results
were saved; report parity as unavailable if the output cannot be recovered.

Keep obsolete CSV writers stopped throughout retirement; current door writers may continue. The proof does not lock a tree
against another process, and filesystem deletion is not a transaction. A
deletion error can stop cleanup after earlier proven files have been removed.
A header-only CSV day needs no stored output when both the CSV and the door
hold zero rows. Verification passes that same empty-day proof in every mode,
and retirement or the default full command can delete the header-only file.

Run `--retire` with the named roots, months and ledgers. It re-reads and proves
all named sources in one process before deleting any CSV. Then run the same
roots, months and ledger list with `--check`. It must print `0 CSV file(s) left`
and exit 0. Run a dry compaction pass for each ledger moved in `state/`; it must
have no period left to pack. Stage only the intended CSV deletions and new
raw and compact files under the named roots.
Push the data commit and wait for its selected CI checks to pass.

After the merge, inspect the same explicit source paths again. Use `--check`
while the converter remains available, not a default list that omits a retired
entry. A CSV file found then needs recovery with the proved converter from
history under the same row and run id; do not silently delete it.

## See also

- [The ledger door](../architecture/contracts/persistence.md) - what the door writes and reads.
- [The ledger registry](../architecture/contracts/ledger-registry.md) - each ledger's address and lifecycle.
- [Run the gates](run-the-gates.md) - local checks and CI coverage.
- [Ship a pull request](ship-a-pr.md) - branch, commit and review steps.
- [Documentation structure](../reference/documentation-structure.md) - where current rules belong.
- [CLAUDE.md](../../CLAUDE.md) - sections 2, 8, 9, 11 and 13.
