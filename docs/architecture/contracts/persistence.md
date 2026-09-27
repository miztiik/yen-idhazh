# The Ledger Door: Parquet and JSON Lines Under state/raw and state/compact

**Last Updated**: 2026-09-27

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

Five builders in `backend/idhazh/ledger/paths.py` are the only code that spells these paths: `raw_path`, `raw_index_path`, `compact_path`, `compact_index_path` and `watermark_path`. Each takes the state root first, the way every ledger builder does, so a trial run and the test suite write where they point it. **Each refuses a path whose first folder under the state root is neither `raw` nor `compact`**, checked on the resolved path so `raw/../scores` is refused too - a third root is a `ValueError` naming the path and the rule, never a folder somebody forgot. `claimed_roots()` claims both roots, so the trial-tree sweep in `prune-state` never reads them as strays. Claimed means "not a stray", never "not pruned": a compaction bounds what sits in them.

`.gitattributes` gives every data file, index and watermark under the two roots `-merge`, because each has one writer and a text merge could only splice two writers' bytes into a file neither wrote. `*.parquet` is `binary`.

## The door

```python
persist(state_dir, rows, *, ledger, covers, identity, tier=Tier.RAW,
        period=None, built_from=None, fmt=None) -> list[Path]
load(paths, *, model) -> list[rows]
read_envelope(path) -> FileEnvelope
```

A producer hands over its rows, the ledger, the period and its writer identity. The door mints the two identifiers, builds the path, assembles the envelope, renders the file and writes it with `atomic_write.write_atomic_bytes` - a temp file in the destination's folder, written whole, then moved onto the target, so a half-written file is never visible under its own name. **A producer never builds a path, never invents a filename and never assembles an envelope**, so moving the next ledger to the door is a change of call site rather than of design. `identity.producer` is the one field a call site must get right: it keeps two producers of one ledger in one job apart.

| Argument | What it means |
| --- | --- |
| `state_dir` | the state root: `common.STATE_ROOT` for a stage |
| `covers` | on the raw tier, the day a row with no `date` field is filed under - every other row goes under the day its own `date` names, so a call holding three days writes three files. On the compact tier, the one period the file covers: a row outside it is refused, because a compact write replaces the whole period and a stray would overwrite a finished one |
| `tier`, `period` | `period` is required on the compact tier and refused on the raw one, and it must match `covers`: daily needs `YYYY-MM-DD`, monthly needs `YYYY-MM` |
| `built_from` | on a compact file, how many files were read to make it. Refused on raw |
| `fmt` | `None` means `config/idhazh.json`'s `ledger.format`, and nothing else |

The paths come back ascending by the period each file covers, never by path string. An empty call writes nothing and returns an empty list.

**A raw write into a paused or retired family from a pipeline job writes nothing**, returns an empty list and logs one warning, through `ledger.accepts_new_rows` ([ledger-registry.md](ledger-registry.md)). A compact-tier write and a write from `migrate`, `run-tasks` or `history` - the members of `MAINTENANCE_JOBS` beside `ServerJob` - are never skipped, because each files rows again that were already recorded.

**`load` is the inverse of `persist` and nothing else.** It reads each file's container from the file's own first bytes, never from its suffix, and refuses a file whose envelope names a different writer. It refuses a file written under a newer shape of the contract than this build declares, naming the file, the stamp it holds and the stamp this build reads. It does not remove duplicates.

## The two identifiers

**One file carries two identifiers, because it answers two questions.**

| | `unit_id` | `file_id`, the filename |
| --- | --- | --- |
| Answers | which work unit | which file |
| Kind | version 5 UUID, no clock | version 8 UUID, clock first |
| Seeded from | ledger, covers, run, job, shard, producer | the write clock in epoch milliseconds, then a hash of `unit_id`, attempt and that clock |
| Same across two attempts | yes | no |

**A union over any set of files keeps, for each `unit_id`, the rows of the highest `attempt`.** GitHub re-runs a failed job into the original run id, so the re-run's files share their `unit_id` with the first attempt's and the first attempt drops out. A re-run replaces its attempt rather than adding to it. `attempt` is only in `file_id` and `producer` only in `unit_id`; put `attempt` into `unit_id` and both attempts would survive the union. Within one millisecond the order of two `file_id`s is arbitrary.

## The envelope inside the file

**A filename carries identity, never meaning.** What a file holds is written inside it, as `FileEnvelope` (`backend/idhazh/contracts/file_envelope.py`): the parquet footer's key-value metadata, or the first line of a JSON-lines file. Every value is a string, `attempt` and `shard` are zero-padded to two digits, and `period` and `built_from` are absent on a raw file. `row_count` is not a key: the parquet footer carries it already.

**A key is also a column only when a query filters or groups on it.** Row-group statistics let a reader skip a whole file on such a column without decompressing it. Measured 2026-09-24: a column that never varies costs about 250 bytes whatever the row count, so the eight identity columns cost about 2,000 bytes - 26 percent of a 3-row raw file, 6 percent of a 420-row month file. The columns are the row's own `version`, then `ledger`, `covers`, `run_id`, `attempt`, `job`, `shard` and `unit_id`. **A contract field of the same name as one of them is that column instead**, so a row's own value is never overwritten, and the envelope still carries the writer's. Three contracts due to move declare such a field today: `HostFingerprintRow` its `run_id`, `job` and `shard`, `VisualPruneRow` its `run_id`, and `EvalRow` its `run_id` and an `attempt` of its own - so for `scores` the union has to rank on the envelope's `attempt`, never the column's.

`content_sha256` is taken over the rows as canonical JSON lines whatever the container, so a copy can be proven a copy after a rename.

## Two formats behind one door

| | parquet | JSON lines |
| --- | --- | --- |
| Written by | `ledger/parquet.py`, the only module that imports pyarrow | `ledger/json_lines.py` |
| Envelope | the footer's key-value metadata | line one, an object of strings |
| Compression | `ledger.compression_raw` (snappy) or `ledger.compression_compact` (zstd) | `none` - it is plain text |
| For | every ledger by default | a payload a person reads in a pull request |

The `ledger` block of `config/idhazh.json` holds four knobs: `format` (default `parquet`), `compression_raw` (default `snappy`, which every reader opens without a plugin), `compression_compact` (default `zstd`, about 2.2 times smaller at a thousand rows) and `published`, the ledgers a browser may fetch. **`published` ships empty**, because no page reads a compact file yet.

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
| `tuple[str, ...]`, of `str` or any alias or `StrEnum` | list of string | as annotated |
| anything else | a `TypeError` naming the field | - |

A date stays a string: it is a stamp a person reads in a diff and in a path, and a second type would be a second spelling of one value. The tuple row is there for `FeedRetirementRow`, whose evidence is a tuple of run ids and a tuple of dates. An `IntEnum` is not in the table yet, so `ItemHealthRow`, whose `tier` is one, is refused by name until the change that moves it adds the row.

## Swapping the engine

**pyarrow is imported in exactly one statement, in `ledger/parquet.py`**, and `backend/tests/ledger/test_single_engine_import.py` fails the build if a second module imports it. So a swap - duckdb is the named candidate - is a change to that one file:

1. Rewrite `render`, `read`, `read_envelope` and `engine_version` in `ledger/parquet.py` against the new engine. Keep their signatures.
2. Keep the envelope as the file's key-value metadata, and keep the column types `arrow_schema.py` names.
3. Update the one-module rule in the single-engine test to the new engine's import name, and the `parquet` extra in `pyproject.toml`.
4. Run `backend/tests/ledger`. The round-trip test reads back every model in both formats, and the committed files under `tests/fixtures/parquet/` are what an earlier engine wrote, so a swap that cannot read them fails there.

**A footer records its engine's version, so two engines never write identical bytes.** That breaks nothing: nothing compares a data file's bytes, only whether a path exists.

## What it costs to install

pyarrow is the largest thing the project installs, so it is the `parquet` optional extra rather than a runtime dependency: only a job that touches a parquet file installs `.[parquet]`, and `dev` pulls it in for the suite. **Its installed size and install time on ubuntu-latest are measured before any workflow job installs it**, and that figure is written here; the reading in hand is from Windows, whose wheel bundles different shared objects, so it is not quoted.

## Design rationale

**pyarrow, with duckdb named as the swap.** pyarrow is the reference implementation, so everything else reads what it writes, and its column interface maps onto a contract's fields. duckdb installs smaller but writes through SQL and brings a query engine where a writer is wanted. polars cost 186.7 MiB and 32.1 s for a dataframe surface nothing here uses; fastparquet took 123.2 s to install because it compiles against numpy. The one-import rule is what keeps the choice cheap to reverse. Measured 2026-09-24.

**The state root is an argument, not a module global.** Every ledger verb already takes one, and `common.STATE_ROOT` is what a trial run and the test suite redirect. A door that wrote relative to the working directory would write the real tree from a test, and a second global root would be a second redirect to keep in step.

**A JSON-lines file records `none` for compression.** The key says what was done to the file, never what the config asked for; a reader that picked a decompressor from a false value would fail on every JSON file.

**The door ships before any committed byte moves.** Moving a ledger's committed data is one-way, and keeping it out of the change that lays the door lets either be reverted alone.

## See also

- [ledger-registry.md](ledger-registry.md) - the registry, the lifecycle statuses and the check every writer asks.
- [state-ledgers.md](state-ledgers.md) - the CSV trees: what each ledger answers, and why it files at the grain it does.
- [schemas.md](schemas.md) - how a contract is declared, versioned and read back.
- [../../concepts/telemetry-intent.md](../../concepts/telemetry-intent.md) - why `state/` moves to parquet under two roots.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3, Guardrail #8, Guardrail #11, sections 2 and 11.
