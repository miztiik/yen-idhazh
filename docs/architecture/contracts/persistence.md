# The Ledger Door: Parquet and JSON Lines Under state/raw and state/compact

**Last Updated**: 2026-10-08

How a contract payload reaches disk under `state/raw/` and `state/compact/`, how it comes back, and how the parquet engine is swapped. The door is `backend/idhazh/ledger/persist.py`; everything a producer needs is two calls, `ledger.persist` and `ledger.load`. The registry and the lifecycle statuses are [ledger-registry.md](ledger-registry.md), the CSV trees are [state-ledgers.md](state-ledgers.md), and the shape of a contract is [schemas.md](schemas.md).

## The two roots

Everything the door writes sits under one of two folders inside `state/`, and nothing else:

```
state/raw/<folders>/<YYYY>/<MM>/<DD>/<file_id>.parquet    many writers, each file written once
state/compact/<folders>/daily/<YYYY>/<MM>/<DD>.parquet    one writer: what a compaction left
state/compact/<folders>/monthly/<YYYY>/<MM>.parquet
state/compact/<folders>/yearly/<YYYY>/<YYYY>.parquet      only where the compaction packs years
state/compact/<folders>/index/<period>.json
```

`<folders>` is the registry `prefix` for that ledger inside the door root. Most door ledgers' prefix is their `LedgerName` value. A ledger inside a family files under the family's folder: the similarity judge's scored pairs file under `content-similarity-judge/scored-pairs` while the file envelope still says `scored-pairs`. A **tier** is `raw` or `compact` - which root. A **period** is `daily`, `monthly` or `yearly` - how much time one compact file covers. The two words are never swapped.

**A raw file carries a minted name; a compact file carries a date.** Raw has many writers that never coordinate, so the minted `<file_id>` is what stops two of them taking one path. A compact period has exactly one writer, so its path is the period it covers and a reader can compute the address.

Six builders in `backend/idhazh/ledger/paths.py` are the only code that spells these paths: `raw_root`, `compact_folder` and `compact_root` for the folders, and `raw_path`, `compact_path` and `compact_index_path` for the files. `compact_folder` is the folder that holds everything one ledger packed, and `compact_root` and `compact_index_path` are built from the same spelling of it. `raw_path` is built from `raw_root` and `compact_path` from `compact_root`, so the folder a reader walks and the file a writer puts in it cannot disagree. Each takes the state root first, the way every ledger builder does, so a trial run and the test suite write where they point it. **Each refuses a path whose first folder under the state root is neither `raw` nor `compact`**, checked on the resolved path so `raw/../scores` is refused too - a third root is a `ValueError` naming the path and the rule, never a folder somebody forgot. `claimed_roots()` claims both roots, so the gardener's `trials` task never reads them as strays. Claimed means "not a stray", never "not pruned": a compaction bounds what sits in them.

The repository's production root is `state/`. A trial compaction may name
additional state roots in `CompactionPolicy.state_roots`; below each one, the
same builders write `raw/<folders>/` and `compact/<folders>/`. A
`compact-trial-<folder>` declaration owns exactly those two folders for its
ledger, where `<folder>` is the ledger's door folder with `/` written `-`. The
production `compact-<folder>` declaration still governs production
retention and prune refusals.

`.gitattributes` gives every data file and index under the two roots `-merge`, because each has one writer and a text merge could only splice two writers' bytes into a file neither wrote. `*.parquet` is `binary`.

The path builders resolve each absolute state root once per process. The root's
location must stay fixed for that process. Candidate paths are still resolved
on every check, so a cached root never permits `raw/../scores` or a symlink
that takes a candidate outside the two roots. Error paths use the same cached
root. The persistence renderer does not resolve paths itself.

## The door

```python
persist(state_dir, rows, *, ledger, covers, identity, fmt=None) -> list[Path]
persist_period(state_dir, rows, *, model, ledger, period, covers, identity,
               built_from) -> Path
render_period(...) -> PeriodFile      # the same file, built and written nowhere
render_grouped_period(state_dir, groups, ...) -> PeriodFile   # one row group a group
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

**`persist` writes raw files only; a compaction writes a compact file through `persist_period`.** Its rows come from `load_stored` and each keeps the identity cells its raw file gave it - `ledger`, `covers`, `run_id`, `attempt`, `job`, `shard` and `unit_id`, declared once as `RowIdentity` in `backend/idhazh/contracts/file_envelope.py`. So a compact file says which writer first filed each row, never that the compaction did, and a re-run's second attempt can still replace its first after the day was compacted. The compaction's own identity goes in the envelope, which says who wrote the file. `covers` is the one period the file covers - `YYYY-MM-DD` for daily, `YYYY-MM` for monthly, `YYYY` for yearly - and a row filed outside it, or into another ledger, is refused, because a compact write replaces the whole period and a stray would overwrite a finished one. `model` is passed rather than read off a row, so a period that held nothing is still a file with every column, and `built_from` records how many files were read to make it. `render_period` builds the same file and writes nothing, which is what a dry run reports from. **`render_grouped_period` builds one from groups of rows, held one group at a time**, and in parquet each group that holds a row is one row group. The compaction packs a year with it, a month a group, so the pass never holds a whole year's rows and a reader that filters on a date can skip the other months. It adds the envelope to the footer after the last row group, because only then is the digest known, so `load` reads a parquet envelope from the file's key-value metadata, where every writer puts it.

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

**A file keeps the name it was written under.** The door mints `file_id` once, as it writes the file, and a push that is tried again stages that same file under that same name. So the gardener reads its record's path on `main` as the answer to whether a try landed: the same bytes there are its own earlier try, and other bytes are two writers on one name, which stops the shard and is never tried again ([Landing the commit](../publishing/idhazh-gardener.md#landing-the-commit)).

## Reading a raw ledger

`backend/idhazh/ledger/raw_files.py` is the reader's half of the union above, written once so no reader invents its own:

| Call | What it answers |
| --- | --- |
| `list_raw_files(state_dir, ledger, days=None)` | every file under `raw/<folders>/<YYYY>/<MM>/<DD>/` whose envelope this build can read, oldest first; `days` names the only days to open |
| `read_day_files(state_dir, ledger, day)` | one day's files, oldest first, or a `ValueError` naming the first one it cannot read - for the compaction, which deletes what it read and so may not skip a file |
| `raw_days(state_dir, ledger)` | which days have a raw folder holding something, from folder names alone |
| `settle_rows(files, key)` | the current rows of a union, each file's rows passed on their own, oldest file first: one file's rows per `unit_id`, then the first row of each `key` |
| `load_current_rows(state_dir, ledger, model=, key=, days=None)` | the raw files' rows, settled |

**Oldest first is an explicit sort, read from each file's envelope**: the day it covers, then `written_at_ms`, then `file_id`. A directory listing agrees today only because a `file_id` starts with its clock, and a reader that leaned on it would change its answer the day the name grammar did. Every file in a day folder is read whatever its suffix, because `ledger.format` may be JSON lines.

**The first row of a key wins, unless the key declares a preference.** Every ledger that reads this way keeps one record per key: a retirement per `endpoint_key`, a cleanup pass per `(date, run_id)`, a gardener task's pass per `(date, run_id, task)`, a census row per `(date, run_id, item_id)`, a measurement per `(url_key, output_digest, scorer_version)`, and a machine row per `(date, run_id, job, shard)`. Two stale checkouts can each file one address, as two work units, and the earlier one is kept. A key that declares a preference in `ledger/keys.py` keeps the later row where the preference says so. Item-health's does: a work shard files a census row as the item settles and assemble files one for the whole day afterwards, and the row that names the machine that ran the item, `machine_job`, is kept. Either way a row is kept or dropped whole, and a cell only the dropped row filled is named in a warning.

**A file this build cannot read is skipped, with one warning that names it**: a newer row shape, a row today's model refuses, a file that is not a ledger file, or one whose envelope names another ledger or another day than the folder it sits in. Only `ValueError` is caught. A missing parquet engine raises `ImportError`, and that stops the run, because skipping every file for it would read as a ledger with no history. For the retirements the direction is the safe one: a skipped file costs one request to an address that is probably still gone, and the next run files it again. **The compaction never skips**: `read_day_files` stops that day, because a file it could not read would be deleted unread.

## What an index entry says

`state/compact/<folders>/index/<period>.json` is a `CompactIndex`, declared in `backend/idhazh/contracts/ledger_index.py`: the ledger, the period, and one entry for each period the packing recorded, ascending by what it covers. One entry carries six fields. The nullable `expired_through` field records the newest deleted UTC year on a yearly index only; writers omit an absent mark, older payloads read it as null, and entries at or before it are refused. The indexes are also the only record of how far a compaction has packed: it works out where the next pass starts from their newest entries and this expiry mark ([ledger-compaction.md](../publishing/ledger-compaction.md#yearly-expiry)).

| Field | What it says |
| --- | --- |
| `covers` | The UTC day, month or year the entry is for, at the index's own period |
| `rows`, `bytes` | How many rows the period's file holds and its size, so a reader can check a file before it reads it. Both are 0 for an entry with no file |
| `state` | `packed`: the period's rows are in its file. `empty`: the period held no row, so no file was written. `lost`: the day's rows could not be recovered, so it has no file and no record. Only a daily entry is `lost`; a month or a year lists the days it lost in `lost_days` |
| `lost_days` | The UTC days inside a monthly or yearly entry whose rows were recorded lost, ascending. Always empty on a daily entry, where a lost day is a `lost` entry of its own |
| `set_aside` | How many files were moved aside unread while the period was packed. The period's file holds every other row |

**An empty or a lost period is an entry with no file, never a missing entry.** So a reader tells three things apart without opening a file: a quiet day (`empty`, or `rows: 0`), a day with no record (`lost`, or listed in its month's or year's `lost_days`), and a hole - a day between packed days that no entry names, which is a fault ([ledger-compaction.md](../publishing/ledger-compaction.md#the-three-indexes-and-a-file-that-is-missing)). A lost day reaches a panel as a day with no record, never as a day with no rows ([how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md#which-files-a-span-reads)). Which entries each stage of a ledger's life leaves, from declared and never packed to stopped, is [ledger-lifecycle.md](ledger-lifecycle.md).

**An index written before entries had a state reads as all `packed`.** The three later fields default to `packed`, no lost day and nothing set aside, so no committed index is rewritten, and a zero-row file written earlier stays a valid `packed` entry. The contract refuses an `empty` or `lost` entry that counts rows or bytes, a `lost` month or year, `lost_days` on a daily entry, and a lost day outside its entry's period, out of order or named twice.

**A rewrite of an entry changes only what it measured again.** When the named prune rebuilds a file without the days it takes ([retention.md](../publishing/retention.md#a-named-prune-one-ledger-one-range-of-days)), the file's entry takes the new `rows` and `bytes` and keeps its `state`, `lost_days` and `set_aside` as they were, so a prune never erases the record of a gap.

## Reading a whole ledger

**A ledger the compaction tends is read from up to four kinds of file, and each date from exactly one.** `backend/idhazh/ledger/ledger_files.py` asks the compact indexes what exists: a date whose year `index/yearly.json` names is read from that year's file; else a date whose month `index/monthly.json` names is read from that month's file; else a date `index/daily.json` names is read from that day's file; else it is read from that day's raw files. The raw files of a day an index already names are a re-run's, waiting for the next compaction, and are not read. A date two indexes name is read from the coarser, with a warning, so a pass that stopped between writing a period and deleting what it absorbed cannot count a row twice.

| Call | What it answers |
| --- | --- |
| `list_ledger_files(state_dir, ledger)` | every source a ledger is read from, oldest first - one compact file, or one raw day's files - and the holes |
| `load_ledger_rows(state_dir, ledger, model=)` | the rows of every source, settled once by `settle_rows`. `model` and the key come from the door table in `ledger/keys.py`, so a reader cannot settle a ledger by another ledger's rule |
| `load_days(state_dir, ledger, days, model=)` | the named UTC days' current rows, oldest day first - the bounded read. It opens the three indexes, the one compact file that serves each day, and the raw files of only the days no index names. A day of a packed year opens that year's whole file, once |
| `held_days(state_dir, ledger)`, `held_months(state_dir, ledger)` | which days and months the ledger holds rows for, read from the indexes and the raw folder names alone, so no data file is opened. A packed year names all its months and days |
| `month_days(month)` | every UTC day of a `YYYY-MM` month, for a caller that reads a month through `load_days` |

**`load_days` settles each day on its own**, as the CSV reader settled a day. So a key that carries no date - the eval ledger's - is settled within a day and never across days. The writer is what keeps one measurement off two days: it files a measurement only once.

**A hole is served and reported.** From the first day the compact periods cover to the newest day they reach, every day must be named. A day that is not is a hole: its rows went somewhere no reader finds them. It is logged by name, and any raw files it still has are read. An index this build cannot read is read as absent, with a warning, so the reader serves the raw files it can still find rather than nothing.

**An entry with no file serves its days with no rows.** The reader looks for no file for an `empty` period or a `lost` day, so neither is `file-missing`, and neither is a hole, because an index names it. A day an index records lost is one warning a read, naming the days, because nothing is missing that a re-pack could restore. `CompactEntry.names_file` is the one reading of whether an entry has a file. The migration's check in `backend/idhazh/ledger/stored_output.py` takes it too: it counts an entry with no file as a recorded period, and refuses a compact file found at that period's path.

`ledger.load_retirements` and `ledger.load_visual_prunes` read this way and keep their signatures. Both ask about their ledger's whole history, which violates the fixed-size input rule in [CLAUDE.md](../../../CLAUDE.md) Guardrail #12. A reader of item-health, summary-quality-evals or host-fingerprint names its days and calls `load_days`; one that calls `load_ledger_rows` is asking about the whole history and must use a fixed-size input.

## The envelope inside the file

**A filename carries identity, never meaning.** What a file holds is written inside it, as `FileEnvelope` (`backend/idhazh/contracts/file_envelope.py`): the parquet footer's key-value metadata, or the first line of a JSON-lines file. Every value is a string, `attempt` and `shard` are zero-padded to two digits, and `period` and `built_from` are absent on a raw file. `row_count` is not a key: the parquet footer carries it already.

**The envelope refuses a key it does not declare**, and it looks for one before it looks for a missing key. So a file that still carries a retired key is refused by that key's name, and never read as a file that is only missing a key.

**A key is also a column only when a query filters or groups on it.** Row-group statistics let a reader skip a whole file on such a column without decompressing it. Measured 2026-09-24: a column that never varies costs about 250 bytes whatever the row count, so the eight identity columns cost about 2,000 bytes - 26 percent of a 3-row raw file, 6 percent of a 420-row month file. The columns are the row's own `version`, then `ledger`, `covers`, `run_id`, `attempt`, `job`, `shard` and `unit_id`. **A contract field of the same name as one of them is that column instead**, so a row's own value is never overwritten, and the envelope still carries the writer's. Four contracts declare such a field: `HostFingerprintRow` its `run_id`, `job` and `shard`, and `VisualPruneRow`, `EvalRow` and `ItemHealthRow` their `run_id`. **A field that would mean something else under one of those names was renamed before its ledger moved.** The union ranks on each row's `attempt` cell, so `EvalRow`'s own attempt - which try at the summary produced the text - is `summary_attempt`. The envelope's `job` and `shard` name the writer, and assemble files census rows for items it did not run, so the machine that took an item's readings is `ItemHealthRow`'s `machine_job` and `machine_shard`. A committed CSV heading with an old name still reads, through each model's `from_csv_row`.

`content_sha256` is taken over the rows as canonical JSON lines whatever the container, so a copy can be proven a copy after a rename.

## Two formats behind one door

| | parquet | JSON lines |
| --- | --- | --- |
| Written by | `ledger/parquet.py`, the only module that imports pyarrow | `ledger/json_lines.py` |
| Envelope | the footer's key-value metadata | line one, an object of strings |
| Compression | `ledger.compression_raw` (snappy) or `ledger.compression_compact` (zstd) | `none` - it is plain text |
| For | every ledger by default | a payload a person reads in a pull request |

`parquet.read` closes its file reader and in-memory byte source before returning
the materialized rows. A short-lived process must not leave native reader
resources for interpreter shutdown to collect; the process-exit regression reads
a committed fixture in a fresh interpreter.

The `ledger` block of `config/idhazh.json` holds five knobs: `format` (default `parquet`), `compression_raw` (default `snappy`, which every reader opens without a plugin), `compression_compact` (default `zstd`, about 2.2 times smaller than snappy at a thousand rows, in [what a parquet file costs](../../reference/benchmarks/what-a-parquet-file-costs.md)), `published`, the ledgers a browser may fetch, and `engine_extension_repository`, where the query engine that reads them downloads its add-ons (default DuckDB's own host, [../publishing/how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md)). **`published` names the three console ledgers**, `host-fingerprint`, `item-health` and `summary-quality-evals`: the site build copies each one's indexes and compact files into the site for the browser's query door ([../publishing/how-the-query-door-answers-a-panel.md](../publishing/how-the-query-door-answers-a-panel.md#what-the-site-holds-for-the-door)). The four console routes still read the same packed files while the site is built, from `state/` on disk, until a panel moves onto the door.

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
| a `Literal[...]` whose every choice is a plain `str` | string | as annotated |
| a `Literal[...]` whose every choice is a plain `int` | int64 | as annotated |
| anything else | a `TypeError` naming the field | - |

A date stays a string: it is a stamp a person reads in a diff and in a path, and a second type would be a second spelling of one value. The tuple row is there for `FeedRetirementRow`, whose evidence is a tuple of run ids and a tuple of dates. An `IntEnum` - `ItemHealthRow`'s `tier` is one - stays its number, the value its JSON form already carries, so a query filters on the number a person reads in the contract. A fixed choice, such as the judge's model name, is stored as its value. A choice set that mixes types, or holds a `bool`, `None` or an enum member, is refused by name: its column would not say what it holds.

## Swapping the engine

**pyarrow is imported in exactly one statement, in `ledger/parquet.py`**, and `backend/tests/ledger/test_single_engine_import.py` fails the build if a second module imports it. So a swap - duckdb is the named candidate - is a change to that one file:

1. Rewrite `render`, `read`, `read_envelope` and `engine_version` in `ledger/parquet.py` against the new engine. Keep their signatures.
2. Keep the envelope as the file's key-value metadata, and keep the column types `arrow_schema.py` names.
3. Update the one-module rule in the single-engine test to the new engine's import name, and the engine's line in `pyproject.toml`'s base dependencies.
4. Run `backend/tests/ledger`. The round-trip test reads back every model in both formats, and the committed files under `tests/fixtures/parquet/` are what an earlier engine wrote, so a swap that cannot read them fails there.

**A footer records its engine's version, so two engines never write identical bytes.** That breaks nothing: nothing compares a data file's bytes, only whether a path exists.

## Moving a ledger onto the door

Fifteen ledgers now file through the door, with their writers and readers moving together. Two moved on 2026-09-28: `state/feed-retirements.csv` and the `state/visual-prunes/<YYYY>/<MM>/<DD>.csv` day files. Their registry entries switched to `raw-and-compact`, and their `merge=union` lines in `.gitattributes` and `path_classes.UNION_SAFE` went, because a file with one writer has nothing for a union to settle. The next three are the ledgers the console reads: the `state/item-health/`, `state/scores/` and `state/host-fingerprint/` day trees, which filed one CSV per writer under each day and were settled on every read. Their registry entries switched to `raw-and-compact` as well. The next five moved between 2026-10-01 and 2026-10-03 through the program below: `counterfactual-scores` and `candidate-models`, which no reader depended on; `seen` and `published`, whose union drivers went with them; and `feed-health`, which the Voices page reads from its packed files. `run-plan` is the plan-stage handoff ledger. The council now files `council-run-records` through the door in its save job, and the similarity judge's scored pairs and metrics followed it into that job. The ledgers still on CSV, and what blocks each one, are in [ledger-registry.md](ledger-registry.md#ledgers-outside-raw-and-compact).

| Ledger | Writer now | Reader now | Files under |
| --- | --- | --- | --- |
| feed retirements | `telemetry.source_health.file_retirements`, the one writer, called by the plan stage (`410 Gone`) and the assemble stage (low yield) | `ledger.load_retirements` | the day each address was retired, because the row has no `date` field |
| visual cleanup record | the gardener's `visual-prune` task, through `ledger.persist` | `ledger.load_visual_prunes` | the day its `date` names |
| item-health, the census | `stages.record` in each work shard as its items settle, and `stages.assemble` for the whole day afterwards, both through `ledger.persist` | `ledger.load_days` for named days, and `ledger.load_ledger_rows` where the question is the whole history | the day its `date` names |
| summary-quality-evals, the eval ledger | `evals.writer.file_measurements`, called by the same two stages, through `ledger.persist`; a read keeps one row per measurement a day ([evaluation.md](../../concepts/evaluation.md#the-ledger)) | the same two | the day its `date` names |
| host-fingerprint, the machine record | `telemetry.silicon`: `idhazh fingerprint` files the job's row when the job starts, and `idhazh job-clock` files it again with the job-end cells under the same writer, so the later file replaces the first | the same two | the day its `date` names |
| counterfactual scores | `stages.plan`, through `ledger.persist` | nothing yet | the day its `date` names |
| candidate-model verdicts | `stages.decide` and `stages.qualify_decide`, through `ledger.persist` | nothing yet | the day its `date` names |
| seen addresses | `ledger.append_seen`, called by the plan stage | `ledger.load_seen` | the day the plan stage ran for, because the row has no `date` field |
| published items | `ledger.append_published`, called by the assemble stage | `ledger.load_published`, one month at a time when it reads every published day | the digest day it is given, because the row has no `date` field |
| feed health | `stages.plan`, through `ledger.persist` | `ledger.load_health`, and the Voices page through `feedHealthRows` in `frontend/src/lib/server/ledger-rows.ts` | the day its `date` names |
| run plans | `stages.plan`, through `ledger.persist` | `stages.common._load_plan`, through `ledger.load_days` for one named UTC day, keeping the plan of the run `--execution` names | the day its `date` names |
| council run records | `council.session._collect`, through `ledger.persist` in the `save_council_results` job | the Records explorer, through the ledger door | the judged day its `date` names |
| similarity judge's scored pairs | `stages.count_verdicts`, through `ledger.persist` in the `save_council_results` job, under the council's writer identity | `stages.set_merge_line`, through `ledger.load_story_similarity_pairs` for the judged day | the judged day its `date` names |
| similarity judge's metrics | `council.metrics_sink.collect_judge_metrics`, called by `stages.count_verdicts` in the same job and under the same identity | nothing yet | the judged day its `date` names |

Each writer names the commit its run checked out, which is why `idhazh plan`, `record`, `fingerprint` and `job-clock` take `--commit` as `idhazh assemble` always did, and a gardener run takes `--git-sha`. `backend/tests/workflows/test_ledger_door_jobs.py` holds that for every step that runs an `idhazh` command. No job has to ask for the parquet engine to reach these ledgers, because pyarrow is part of the base install ([What it costs to install](#what-it-costs-to-install)).

`council-settle` passes its workflow commit SHA to `council.session._collect`.
The save job records its workflow attempt, job name and council run in the file
envelope, while the row names the judged date, tenant, step and part. A retry's
later attempt wins when the reader settles rows by `unit_id`. The same identity
reaches each tenant through `Tenant.settle`, and a tenant changes only the
producer, so the judge's files name the same run, attempt and commit.

**The first two ledgers' committed CSV moved once, on 2026-09-28, through a one-shot migration.** It read the CSV, wrote one file per day through the door, read each file back field for field and cell for cell against the CSV row it came from, and only then deleted the CSV. The files it wrote carry `job=migrate`, `attempt=1`, `shard=0` and `producer=utilities.migrate_csv`, which is why `ServerJob` keeps `migrate`: a reader names those files' writer from it. No CSV of either ledger is left on `main`, and a run that checked out the CSV layout cannot push its append over the deleted file, so the program had nothing left to move and was deleted on 2026-09-28; git history holds it.

**One command moves named months of a ledger's CSV onto the door: `backend/utilities/migrate_to_parquet.py`.** The `CSV_LEDGERS` table in `backend/utilities/ledger_migration/csv_layouts.py` records each old path and retention window. It reads both the per-writer day tree and the shared `YYYY/MM/DD.csv` layout in required, repeated `--month YYYY-MM` inputs. The other modules of `backend/utilities/ledger_migration/` validate each selected row, file it through the door, and prove the CSV's filled cells before any CSV is deleted. `backend/idhazh/ledger/stored_output.py` checks actual raw files and relevant indexed compact periods. The command accepts repeated `--state-dir` roots. The repository's `state/` root packs only those months through the production `compact-<folder>` declaration; packing is live and the monthly deletion window only reports. A trial root packs only when `compact-trial-<folder>` names that exact root in `state_roots`; otherwise the migrator files it raw. Year packing requires all twelve months to be named. The reusable move procedure and completion checks are in [Move a ledger to Parquet](../../how-to/move-a-ledger-to-parquet.md).

**It refuses a ledger that cannot move yet, before it reads a file**, with exit 1 and the reason: a ledger the registry still files as CSV, which has no door to move into; a ledger with no `compact-<folder>` declaration, so nothing says which days are packed; and one whose compaction keeps less than its CSV was kept, which would delete at its first live pass days the CSV still held. `--ledger` repeats. With none named, a run or a `--check` takes every ledger in the table that the registry files as `raw-and-compact`, so a check passes while the ledgers still on CSV keep writing it.

Running it again is safe. Every raw file carries `job=migrate`, `attempt=1`, `shard=0` and `producer=utilities.migrate_to_parquet`, so the same run id replaces its earlier write. A late CSV file in a named month is folded onto the rows the door already holds and is proven again. `--check` exits 1 while a CSV file of a named ledger remains in any supplied root and month. **The table, program and tests are deleted when no ledger a program writes is left on CSV**: the map in [ledger-registry.md](ledger-registry.md#ledgers-outside-raw-and-compact) lists none, and the owner's named-month checks find no remaining CSV. A file a person edits by hand, such as `holdout-pairs.csv`, does not hold the program back.

**The eval ledger moved as `scores` and was renamed `summary-quality-evals` afterwards** ([ledger-registry.md](ledger-registry.md#design-rationale)). The one-shot migration moved `state/raw/scores/`, `state/compact/scores/` and `state/score-index/` to their new names. It read every old file, wrote every new one, read each back through this build's own readers, and only then deleted the old files. It proved that ledger rows, settled days and recorded measurements stayed equal. The migration is complete, and its utility and tests were removed on 2026-10-02.

**Git moves a file added under an old folder into the new one.** A merge or a rebase that meets the rename treats the folder as renamed, so a file another branch added under `state/raw/scores/` lands under `state/raw/summary-quality-evals/` still naming the old ledger, marked as a conflict. A person merging `main` into a branch that predates the rename runs `git -c merge.directoryRenames=false merge`, which leaves the file where it was filed for the program to move; a file merged any other way is found by its envelope and rewritten where it lies. The pipeline's commit step cannot do either: a run that started before the rename and pushes after it stops at that conflict, because the moved path is not one its own name lets it keep, so nothing it wrote lands. That is why the rename merges while no run is queued or running.

## What it costs to install

pyarrow is the largest thing the project installs, and it is a base dependency: `pip install -e .` installs it for every job, whether or not that job opens a parquet file. Its beneficiary is the one module that writes and reads parquet, `ledger/parquet.py`. **An optional extra that only the jobs reaching the door install is the smaller install, and it is the one this project could not hold.** A check that follows a job's imports misses the next way in - a Node script that starts Python, or a verb held in a variable - and a job it misses fails at its first read of the door. A base dependency cannot be missed.

**What that costs is an estimate from GitHub's own step timings on ubuntu-latest (2026-09-29), not a paired measurement.** A plain install took 10 to 16 seconds (mean 12.9, over 13 runs) and an install with the engine 13 to 22 seconds (mean 15.2, over 10 runs). So the engine adds about 2 seconds to an average install - inside the spread between runs - and about 12 seconds at the widest, on each of about 12 installs that never open a parquet file. pyarrow 25.0.1 declares no dependencies of its own, so it moves no version the project already installs. A reading taken on Windows is not quoted, because that wheel bundles different shared objects.

**Installed everywhere is not imported everywhere.** pyarrow is imported in `ledger/parquet.py` and nowhere else, and `ledger/persist.py` loads that module only inside the calls that write or read a parquet file, so importing the door loads no engine. `backend/tests/ledger/test_single_engine_import.py` holds the first half, and `test_the_facade_does_not_load_pyarrow` in `backend/tests/contracts/test_ledger_package.py` holds the second.

Every job installs the same set, so whichever job saves `setup-python`'s pip cache saves pyarrow in it.

## Design rationale

**pyarrow, with duckdb named as the swap.** pyarrow is the reference implementation, so everything else reads what it writes, and its column interface maps onto a contract's fields. duckdb installs smaller but writes through SQL and brings a query engine where a writer is wanted. polars cost 186.7 MiB and 32.1 s for a dataframe surface nothing here uses; fastparquet took 123.2 s to install because it compiles against numpy. The one-import rule is what keeps the choice cheap to reverse. Measured 2026-09-24.

**The state root is an argument, not a module global.** Every ledger verb already takes one, and `common.STATE_ROOT` is what a trial run and the test suite redirect. A door that wrote relative to the working directory would write the real tree from a test, and a second global root would be a second redirect to keep in step.

**A JSON-lines file records `none` for compression.** The key says what was done to the file, never what the config asked for; a reader that picked a decompressor from a false value would fail on every JSON file.

**The door ships before any committed byte moves.** Moving a ledger's committed data is one-way, and keeping it out of the change that lays the door lets either be reverted alone.

**2026-09-28: the union ranks on each row, and a compact file keeps each row's writer.** A compact file holds many work units under one envelope, so ranking on the file's `attempt` would rank the compaction rather than the writers. Each row keeps the identity cells its raw file gave it, the one settlement - `raw_files.settle_rows` - reads them, and the door refuses a row whose own cells contradict its writer's. The file-level pick it replaced is gone, so a raw union and a compact rebuild cannot disagree (Fowler).

## See also

- [ledger-registry.md](ledger-registry.md) - the registry, the lifecycle statuses and the check every writer asks.
- [ledger-lifecycle.md](ledger-lifecycle.md) - which entries each stage of a ledger's life leaves in its indexes.
- [state-ledgers.md](state-ledgers.md) - the CSV trees: what each ledger answers, and why it files at the grain it does.
- [schemas.md](schemas.md) - how a contract is declared, versioned and read back.
- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - why `state/` moves to parquet under two roots.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3, Guardrail #8, Guardrail #11, sections 2 and 11.
