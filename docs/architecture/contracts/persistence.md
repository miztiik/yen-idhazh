# The Ledger Door: Parquet and JSON Lines Under state/raw and state/compact

**Last Updated**: 2026-09-29

How a contract payload reaches disk under `state/raw/` and `state/compact/`, how it comes back, and how the parquet engine is swapped. The door is `backend/idhazh/ledger/persist.py`; everything a producer needs is two calls, `ledger.persist` and `ledger.load`. The registry and the lifecycle statuses are [ledger-registry.md](ledger-registry.md), the CSV trees are [state-ledgers.md](state-ledgers.md), and the shape of a contract is [schemas.md](schemas.md).

## The two roots

Everything the door writes sits under one of two folders inside `state/`, and nothing else:

```
state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet    many writers, each file written once
state/raw/<ledger>/index/<YYYY-MM-DD>.json               one day's listing
state/compact/<ledger>/daily/<YYYY>/<MM>/<DD>.parquet    one writer: what a compaction left
state/compact/<ledger>/monthly/<YYYY>/<MM>.parquet
state/compact/<ledger>/index/<period>.json
state/compact/<ledger>/<period>/watermark.json
```

`<ledger>` is always the `LedgerName` value. A **tier** is `raw` or `compact` - which root. A **period** is `daily` or `monthly` - how much time one compact file covers. The two words are never swapped.

**A raw file carries a minted name; a compact file carries a date.** Raw has many writers that never coordinate, so the minted `<file_id>` is what stops two of them taking one path. A compact period has exactly one writer, so its path is the period it covers and a reader can compute the address.

Six builders in `backend/idhazh/ledger/paths.py` are the only code that spells these paths: `raw_root` for the folder a reader walks, and `raw_path`, `raw_index_path`, `compact_path`, `compact_index_path` and `watermark_path` for the files. `raw_path` and `raw_index_path` are built from `raw_root`, so the folder a reader walks and the file a writer puts in it cannot disagree. Each takes the state root first, the way every ledger builder does, so a trial run and the test suite write where they point it. **Each refuses a path whose first folder under the state root is neither `raw` nor `compact`**, checked on the resolved path so `raw/../scores` is refused too - a third root is a `ValueError` naming the path and the rule, never a folder somebody forgot. `claimed_roots()` claims both roots, so the gardener's `trials` task never reads them as strays. Claimed means "not a stray", never "not pruned": a compaction bounds what sits in them.

`.gitattributes` gives every data file, index and watermark under the two roots `-merge`, because each has one writer and a text merge could only splice two writers' bytes into a file neither wrote. `*.parquet` is `binary`.

## The door

```python
persist(state_dir, rows, *, ledger, covers, identity, fmt=None) -> list[Path]
persist_period(state_dir, rows, *, model, ledger, period, covers, identity,
               built_from) -> Path
render_period(...) -> PeriodFile      # the same file, built and written nowhere
load(paths, *, model) -> list[rows]
load_stored(paths, *, model) -> list[StoredRow]
read_envelope(path) -> FileEnvelope
```

A producer hands over its rows, the ledger, the period and its writer identity. The door mints the two identifiers, builds the path, assembles the envelope, renders the file and writes it with `atomic_write.write_atomic_bytes` - a temp file in the destination's folder, written whole, then moved onto the target, so a half-written file is never visible under its own name. **A producer never builds a path, never invents a filename and never assembles an envelope**, so moving the next ledger to the door is a change of call site rather than of design. `identity.producer` is the one field a call site must get right: it keeps two producers of one ledger in one job apart.

| Argument | What it means |
| --- | --- |
| `state_dir` | the state root: `common.STATE_ROOT` for a stage |
| `covers` | the day a row with no `date` field is filed under - every other row goes under the day its own `date` names, so a call holding three days writes three files |
| `fmt` | `None` means `config/idhazh.json`'s `ledger.format`, and nothing else |

The paths come back ascending by the day each file covers, never by path string. An empty call writes nothing and returns an empty list. Every file is built before the first is written, so a row refused on its third day leaves no file for the first two.

**`persist` writes raw files only; a compaction writes a compact file through `persist_period`.** Its rows come from `load_stored` and each keeps the identity cells its raw file gave it - `ledger`, `covers`, `run_id`, `attempt`, `job`, `shard` and `unit_id`, declared once as `RowIdentity` in `backend/idhazh/contracts/file_envelope.py`. So a compact file says which writer first filed each row, never that the compaction did, and a re-run's second attempt can still replace its first after the day was compacted. The compaction's own identity goes in the envelope, which says who wrote the file. `covers` is the one period the file covers - `YYYY-MM-DD` for daily, `YYYY-MM` for monthly - and a row filed outside it, or into another ledger, is refused, because a compact write replaces the whole period and a stray would overwrite a finished one. `model` is passed rather than read off a row, so a period that held nothing is still a file with every column, and `built_from` records how many files were read to make it. `render_period` builds the same file and writes nothing, which is what a dry run reports from.

**A raw write into a paused or retired family from a pipeline job writes nothing**, returns an empty list and logs one warning, through `ledger.accepts_new_rows` ([ledger-registry.md](ledger-registry.md)). A `persist_period` write, and a raw write from `migrate`, `run-tasks` or `history` - the members of `MAINTENANCE_JOBS` beside `ServerJob` - are never skipped, because each files rows again that were already recorded.

**`load` is the inverse of `persist` and nothing else.** It reads each file's container from the file's own first bytes, never from its suffix, and refuses a file whose envelope names a different writer. It refuses a file written under a newer shape of the contract than this build declares, naming the file, the stamp it holds and the stamp this build reads. `load_stored` is the same read with each row's identity cells kept beside it. Neither removes duplicates: choosing which rows are current is the reader's half, in [Reading a raw ledger](#reading-a-raw-ledger).

## The two identifiers

**One file carries two identifiers, because it answers two questions.**

| | `unit_id` | `file_id`, the filename |
| --- | --- | --- |
| Answers | which work unit | which file |
| Kind | version 5 UUID, no clock | version 8 UUID, clock first |
| Seeded from | ledger, covers, run, job, shard, producer | the write clock in epoch milliseconds, then a hash of `unit_id`, attempt and that clock |
| Same across two attempts | yes | no |

**A union over any set of files keeps, for each `unit_id`, the rows of one file: the last file holding its highest `attempt`.** GitHub re-runs a failed job into the original run id, so the re-run's files share their `unit_id` with the first attempt's and the first attempt drops out. A re-run replaces its attempt rather than adding to it, and one attempt that wrote a unit twice is its later write. `attempt` is only in `file_id` and `producer` only in `unit_id`; put `attempt` into `unit_id` and both attempts would survive the union. Within one millisecond the order of two `file_id`s is arbitrary.

**The union reads `attempt` and `unit_id` from each row's own cells, not from the file's envelope**, because a compact file holds rows of many units and many attempts under one envelope. So the door refuses a row whose own `attempt` or `unit_id` is not its writer's: the union would keep or drop it for a try that never wrote it.

## Reading a raw ledger

`backend/idhazh/ledger/raw_files.py` is the reader's half of the union above, written once so no reader invents its own:

| Call | What it answers |
| --- | --- |
| `list_raw_files(state_dir, ledger, days=None)` | every file under `raw/<ledger>/<YYYY>/<MM>/<DD>/` whose envelope this build can read, oldest first; `days` names the only days to open |
| `read_day_files(state_dir, ledger, day)` | one day's files, oldest first, or a `ValueError` naming the first one it cannot read - for the compaction, which deletes what it read and so may not skip a file |
| `raw_days(state_dir, ledger)`, `listed_days(state_dir, ledger)` | which days have a raw folder holding something, and which have a listing under `index/`, from folder and file names alone |
| `settle_rows(files, key)` | the current rows of a union, each file's rows passed on their own, oldest file first: one file's rows per `unit_id`, then the first row of each `key` |
| `load_current_rows(state_dir, ledger, model=, key=, days=None)` | the raw files' rows, settled |

**Oldest first is an explicit sort, read from each file's envelope**: the day it covers, then `written_at_ms`, then `file_id`. A directory listing agrees today only because a `file_id` starts with its clock, and a reader that leaned on it would change its answer the day the name grammar did. Every file in a day folder is read whatever its suffix, because `ledger.format` may be JSON lines, and `index/` beside the years is passed over, because a listing is not a row.

**The first row of a key wins, unless the key declares a preference.** Every ledger that reads this way keeps one record per key: a retirement per `endpoint_key`, a cleanup pass per `(date, run_id)`, a gardener task's pass per `(date, run_id, task)`, a census row per `(date, run_id, item_id)`, a measurement per `(url_key, output_digest, scorer_version)`, and a machine row per `(date, run_id, job, shard)`. Two stale checkouts can each file one address, as two work units, and the earlier one is kept. A key that declares a preference in `ledger/keys.py` keeps the later row where the preference says so. Item-health's does: a work shard files a census row as the item settles and assemble files one for the whole day afterwards, and the row that names the machine that ran the item, `machine_job`, is kept. Either way a row is kept or dropped whole, and a cell only the dropped row filled is named in a warning.

**A file this build cannot read is skipped, with one warning that names it**: a newer row shape, a row today's model refuses, a file that is not a ledger file, or one whose envelope names another ledger or another day than the folder it sits in. Only `ValueError` is caught. A missing parquet engine raises `ImportError`, and that stops the run, because skipping every file for it would read as a ledger with no history. For the retirements the direction is the safe one: a skipped file costs one request to an address that is probably still gone, and the next run files it again. **The compaction never skips**: `read_day_files` stops that day, because a file it could not read would be deleted unread.

## Reading a whole ledger

**A ledger the compaction tends is read from three kinds of file, and each date from exactly one.** `backend/idhazh/ledger/ledger_files.py` asks the two compact indexes what exists: a date whose month `index/monthly.json` names is read from that month's file; else a date `index/daily.json` names is read from that day's file; else it is read from that day's raw files. The raw files of a day an index already names are a re-run's, waiting for the next compaction, and are not read. A date both indexes name is read from its month, with a warning, so a pass that stopped between writing a month and deleting its days cannot count a row twice.

| Call | What it answers |
| --- | --- |
| `list_ledger_files(state_dir, ledger)` | every source a ledger is read from, oldest first - one compact file, or one raw day's files - and the holes |
| `load_ledger_rows(state_dir, ledger, model=)` | the rows of every source, settled once by `settle_rows`. `model` and the key come from the door table in `ledger/keys.py`, so a reader cannot settle a ledger by another ledger's rule |
| `load_days(state_dir, ledger, days, model=)` | the named UTC days' current rows, oldest day first - the bounded read. It opens the two indexes, the one compact file that serves each day, and the raw files of only the days no index names |
| `held_days(state_dir, ledger)`, `held_months(state_dir, ledger)` | which days and months the ledger holds rows for, read from the indexes and the raw folder names alone, so no data file is opened |
| `month_days(month)` | every UTC day of a `YYYY-MM` month, for a caller that reads a month through `load_days` |

**`load_days` settles each day on its own**, as the CSV reader settled a day. So a key that carries no date - the eval ledger's - is settled within a day and never across days. The writer is what keeps one measurement off two days: it files a measurement only once.

**A hole is served and reported.** From the first day the compact periods cover to the newest day `index/daily.json` names, every day must be named. A day that is not is a hole: its rows went somewhere no reader finds them. It is logged by name, and any raw files it still has are read. An index this build cannot read is read as absent, with a warning, so the reader serves the raw files it can still find rather than nothing.

`ledger.load_retirements` and `ledger.load_visual_prunes` read this way and keep their signatures. Both ask about their ledger's whole history, so a window would answer a different question, and [growing-reads.md](../../concepts/growing-reads.md) lists both. A reader of item-health, scores or host-fingerprint names its days and calls `load_days`; one that calls `load_ledger_rows` is asking about the whole history, and growing-reads.md lists it too.

## The envelope inside the file

**A filename carries identity, never meaning.** What a file holds is written inside it, as `FileEnvelope` (`backend/idhazh/contracts/file_envelope.py`): the parquet footer's key-value metadata, or the first line of a JSON-lines file. Every value is a string, `attempt` and `shard` are zero-padded to two digits, and `period` and `built_from` are absent on a raw file. `row_count` is not a key: the parquet footer carries it already.

**A key is also a column only when a query filters or groups on it.** Row-group statistics let a reader skip a whole file on such a column without decompressing it. Measured 2026-09-24: a column that never varies costs about 250 bytes whatever the row count, so the eight identity columns cost about 2,000 bytes - 26 percent of a 3-row raw file, 6 percent of a 420-row month file. The columns are the row's own `version`, then `ledger`, `covers`, `run_id`, `attempt`, `job`, `shard` and `unit_id`. **A contract field of the same name as one of them is that column instead**, so a row's own value is never overwritten, and the envelope still carries the writer's. Four contracts declare such a field: `HostFingerprintRow` its `run_id`, `job` and `shard`, and `VisualPruneRow`, `EvalRow` and `ItemHealthRow` their `run_id`. **A field that would mean something else under one of those names was renamed before its ledger moved.** The union ranks on each row's `attempt` cell, so `EvalRow`'s own attempt - which try at the summary produced the text - is `summary_attempt`. The envelope's `job` and `shard` name the writer, and assemble files census rows for items it did not run, so the machine that took an item's readings is `ItemHealthRow`'s `machine_job` and `machine_shard`. A committed CSV heading with an old name still reads, through each model's `from_csv_row`.

`content_sha256` is taken over the rows as canonical JSON lines whatever the container, so a copy can be proven a copy after a rename.

## Two formats behind one door

| | parquet | JSON lines |
| --- | --- | --- |
| Written by | `ledger/parquet.py`, the only module that imports pyarrow | `ledger/json_lines.py` |
| Envelope | the footer's key-value metadata | line one, an object of strings |
| Compression | `ledger.compression_raw` (snappy) or `ledger.compression_compact` (zstd) | `none` - it is plain text |
| For | every ledger by default | a payload a person reads in a pull request |

The `ledger` block of `config/idhazh.json` holds five knobs: `format` (default `parquet`), `compression_raw` (default `snappy`, which every reader opens without a plugin), `compression_compact` (default `zstd`, about 2.2 times smaller at a thousand rows), `published`, the ledgers a browser may fetch, and `engine_extension_repository`, where the query engine that reads them downloads its add-ons (default DuckDB's own host, [../publishing/how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md)). **`published` ships empty**, because no page reads a compact file yet.

### The column types

`backend/idhazh/ledger/arrow_schema.py` is a literal table, never inference from the first row: a nullable column whose first row is null would infer as a null type and refuse the second row.

| Python annotation | Column type | Nullable |
| --- | --- | --- |
| `str`, and every constrained string alias in `contracts/base.py` | string | no |
| `int` | int64 | no |
| `float` | float64 | no |
| `bool` | bool | no |
| any of those `\| None` | the same | yes |
| a `StrEnum` | string, never a dictionary column | as annotated |
| an `IntEnum` | int64 | as annotated |
| `tuple[str, ...]`, of `str` or any alias or `StrEnum` | list of string | as annotated |
| anything else | a `TypeError` naming the field | - |

A date stays a string: it is a stamp a person reads in a diff and in a path, and a second type would be a second spelling of one value. The tuple row is there for `FeedRetirementRow`, whose evidence is a tuple of run ids and a tuple of dates. An `IntEnum` - `ItemHealthRow`'s `tier` is one - stays its number, the value its JSON form already carries, so a query filters on the number a person reads in the contract.

## Swapping the engine

**pyarrow is imported in exactly one statement, in `ledger/parquet.py`**, and `backend/tests/ledger/test_single_engine_import.py` fails the build if a second module imports it. So a swap - duckdb is the named candidate - is a change to that one file:

1. Rewrite `render`, `read`, `read_envelope` and `engine_version` in `ledger/parquet.py` against the new engine. Keep their signatures.
2. Keep the envelope as the file's key-value metadata, and keep the column types `arrow_schema.py` names.
3. Update the one-module rule in the single-engine test to the new engine's import name, and the `parquet` extra in `pyproject.toml`.
4. Run `backend/tests/ledger`. The round-trip test reads back every model in both formats, and the committed files under `tests/fixtures/parquet/` are what an earlier engine wrote, so a swap that cannot read them fails there.

**A footer records its engine's version, so two engines never write identical bytes.** That breaks nothing: nothing compares a data file's bytes, only whether a path exists.

## Moving a ledger onto the door

Five ledgers have moved, producer and reader together. Two moved on 2026-09-28: `state/feed-retirements.csv` and the `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` day files. Their registry entries switched to `raw-and-compact`, and their `merge=union` lines in `.gitattributes` and `path_classes.UNION_SAFE` went, because a file with one writer has nothing for a union to settle. The other three are the ledgers the console reads: the `state/item-health/`, `state/scores/` and `state/host-fingerprint/` day trees, which filed one CSV per writer under each day and were settled on every read. Their registry entries switched to `raw-and-compact` as well.

| Ledger | Writer now | Reader now | Files under |
| --- | --- | --- | --- |
| feed retirements | `telemetry.source_health.file_retirements`, the one writer, called by the plan stage (`410 Gone`) and the assemble stage (low yield) | `ledger.load_retirements` | the day each address was retired, because the row has no `date` field |
| visual cleanup record | the gardener's `visual-prune` task, through `ledger.persist` | `ledger.load_visual_prunes` | the day its `date` names |
| item-health, the census | `stages.record` in each work shard as its items settle, and `stages.assemble` for the whole day afterwards, both through `ledger.persist` | `ledger.load_days` for named days, and `ledger.load_ledger_rows` where the question is the whole history | the day its `date` names |
| scores, the eval ledger | `evals.writer.file_measurements`, called by the same two stages. It files a measurement only once, and writes the `state/score-index/` CSV day tree beside it | the same two | the day its `date` names |
| host-fingerprint, the machine record | `telemetry.silicon`: `idhazh fingerprint` files the job's row when the job starts, and `idhazh job-clock` files it again with the job-end cells under the same writer, so the later file replaces the first | the same two | the day its `date` names |

Each writer names the commit its run checked out, which is why `idhazh plan`, `record`, `fingerprint` and `job-clock` take `--commit` as `idhazh assemble` always did, and a gardener run takes `--git-sha`. Every workflow job that reaches one of these ledgers installs `.[parquet]`. A test holds both for every step that runs an `idhazh` command: `backend/tests/workflows/test_ledger_door_jobs.py`. It does not follow a script under `backend/utilities/`, so a job that reaches a ledger only through one is held by reading it: `drift.yml`, whose report reads the eval ledger, and `ci.yml`'s browser job, whose canary day builder files the census, machine and eval rows, install `.[parquet]` for that reason.

**The first two ledgers' committed CSV moved once, on 2026-09-28, through a one-shot migration.** It read the CSV, wrote one file per day through the door, read each file back field for field and cell for cell against the CSV row it came from, and only then deleted the CSV. The files it wrote carry `job=migrate`, `attempt=1`, `shard=0` and `producer=utilities.migrate_csv`, which is why `ServerJob` keeps `migrate`: a reader names those files' writer from it. No CSV of either ledger is left on `main`, and a run that checked out the CSV layout cannot push its append over the deleted file, so the program had nothing left to move and was deleted on 2026-09-28; git history holds it.

**The three console ledgers move through `backend/utilities/migrate_to_parquet.py`.** For each ledger and each CSV day, it takes the rows today's CSV reader returns for that day (`day_shards.settled_day`) and files them as one raw file through the door. Then the compaction's own daily step packs every finished day its rule admits, and writes each day's file, `index/daily.json` and the daily watermark as a live pass would, so a packing task turned on later resumes from the right day. A day the rule does not admit yet stays a raw file. **Nothing is deleted until everything is proven**: every day is read back through `load_days`, from whichever file now serves it, and compared cell for cell with the rows it was built from before any CSV of that ledger is removed. A day that does not read back leaves every CSV where it was, and the program exits 1.

Running it again is safe. Every file it writes carries `job=migrate`, `attempt=1`, `shard=0` and `producer=utilities.migrate_to_parquet`, so a second run files a day under the same work unit, and a day with nothing new is not written again. A CSV file that lands after the first run - from a run created before the merge and pushing after it - is folded onto what the door holds for its day, and the day is packed again. `--check` exits 1 while any CSV of the three is left. **Delete the program when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`.** The three packing tasks ship report-only, which is what a person turns on next ([../publishing/idhazh-gardener.md](../publishing/idhazh-gardener.md#the-compaction)).

## What it costs to install

pyarrow is the largest thing the project installs, so it is the `parquet` optional extra rather than a runtime dependency: only a job that touches a parquet file installs `.[parquet]`, and `dev` pulls it in for the suite. **Its install time on ubuntu-latest was not measured before the first workflow job installed it**, by owner ruling (2026-09-27); the first digest run that installs it is where that reading comes from, and it is written here when it is taken. The reading in hand is from Windows, whose wheel bundles different shared objects, so it is not quoted.

The jobs that install it share `setup-python`'s pip cache key with the jobs that do not, because that action keys on the OS, the interpreter and the dependency file and offers no input that names the extras. A cache saved by a job without the engine costs the next job that needs it a download of pyarrow, never a failed run.

## Design rationale

**pyarrow, with duckdb named as the swap.** pyarrow is the reference implementation, so everything else reads what it writes, and its column interface maps onto a contract's fields. duckdb installs smaller but writes through SQL and brings a query engine where a writer is wanted. polars cost 186.7 MiB and 32.1 s for a dataframe surface nothing here uses; fastparquet took 123.2 s to install because it compiles against numpy. The one-import rule is what keeps the choice cheap to reverse. Measured 2026-09-24.

**The state root is an argument, not a module global.** Every ledger verb already takes one, and `common.STATE_ROOT` is what a trial run and the test suite redirect. A door that wrote relative to the working directory would write the real tree from a test, and a second global root would be a second redirect to keep in step.

**A JSON-lines file records `none` for compression.** The key says what was done to the file, never what the config asked for; a reader that picked a decompressor from a false value would fail on every JSON file.

**The door ships before any committed byte moves.** Moving a ledger's committed data is one-way, and keeping it out of the change that lays the door lets either be reverted alone.

**2026-09-28: the union ranks on each row, and a compact file keeps each row's writer.** A compact file holds many work units under one envelope, so ranking on the file's `attempt` would rank the compaction rather than the writers. Each row keeps the identity cells its raw file gave it, the one settlement - `raw_files.settle_rows` - reads them, and the door refuses a row whose own cells contradict its writer's. The file-level pick it replaced is gone, so a raw union and a compact rebuild cannot disagree (Fowler).

## See also

- [ledger-registry.md](ledger-registry.md) - the registry, the lifecycle statuses and the check every writer asks.
- [state-ledgers.md](state-ledgers.md) - the CSV trees: what each ledger answers, and why it files at the grain it does.
- [schemas.md](schemas.md) - how a contract is declared, versioned and read back.
- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - why `state/` moves to parquet under two roots.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3, Guardrail #8, Guardrail #11, sections 2 and 11.
