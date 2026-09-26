# Plan 53 - One door into `state/`

**Last Updated**: 2026-09-26

## 0. Operating contract

| | |
| --- | --- |
| Correction level | **5 for the decision, 3 for every row.** Level 5 because what is settled here is that `backend/idhazh/ledger/` is the one door into `state/` and that `backend/idhazh/store/` never exists - it binds every producer added after it. Level 3 per row because each crosses a subsystem boundary and none can break published data |
| Parallel N | **1. This is a chain and saying otherwise would be an invention.** Every row hands the next one a surface it needs. Rows are small on purpose so the chain is short, not so it can be split |
| Hard scope - in | - `backend/idhazh/ledger.py`, 2,342 lines and about 120 top-level names, becomes `backend/idhazh/ledger/`, twelve modules each answering one question.<br>- The word `store` leaves the repository. Under `state/` it becomes **ledger**; under `frontend/public/` it becomes **collection**.<br>- `SegmentLedger`, `STORE_DIRNAMES` and the 25 `*_DIRNAME` constants collapse into one `LedgerName` in `backend/idhazh/contracts/`.<br>- 42 hand-written path functions collapse into one table and two builders.<br>- `backend/idhazh/paths.py` becomes `path_classes.py`, which is what its own test has called it all along |
| Hard scope - out | see the table below |
| Blocks | **Plan 50 row 2 cannot start until rows 2 and 3 here have merged.** It needs a package to live in and an enum to type its first argument |
| Authoring | **AUTHOR AND STOP.** No code until a person says go |

### Hard scope - out

| Not here | What stays true meanwhile | Where it goes |
| --- | --- | --- |
| Parquet, the envelope, the two tiers, compaction | `state/` stays CSV end to end. Nothing about how a file is encoded changes in this plan | [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) row 2, which lands **inside** `ledger/` rather than creating a package of its own |
| Moving any committed byte | Every file under `state/` keeps its path, its name and its bytes. **Rows 1 to 8 write nothing to disk** | Plan 50 rows 3, 9 and 10 |
| `HEALTH_WINDOW_DAYS: Final = 31` | A hardcoded tunable survives in a module whose siblings all read their window from config | Its own one-line pull request. It is Guardrail #6 and it is not this plan's question |
| The retention windows, the prune passes, the gardener | Untouched | Plan 50 rows 4 to 8 |

### The intent this plan serves

**A producer should have one way to put rows into `state/` and one way to get them back.** Today it has four, and plan 50 was about to build a fifth.

The four are visible in one signature comparison. `ledger.write_segment(state_dir, ledger, rows, *, run_id, attempt, job, shard, date=None)` and plan 50's drafted `persist(rows, *, dataset, covers, identity, tier, period, built_from, fmt)` carry **the same six facts in two spellings**. Shipping the second beside the first would have meant twenty-odd producers each knowing which door they were, and a reader of `state/` needing both vocabularies to read one directory.

The second half of the intent is the file that made this invisible. `backend/idhazh/ledger.py` is 2,342 lines and answers at least eleven questions: what the directories are called, what makes two rows the same record, where each ledger's file lives, how a CSV is read, how an old header is migrated, what a segment filename means, how each of twenty ledgers is appended to and loaded, how duplicates are dropped, how a feed's reliability is computed, and what a month window is. CLAUDE.md section 1a says a source file answers one narrow question and that **if answering it needs a long file, the question is too broad**. This file is the standing counter-example, and every plan that has touched it has had to read all of it to change one thing.

**What a reader gets: one word for one thing, and a file whose first sentence tells them whether to keep reading.**

## 1. Status Reckoner

| Row | What it does | Hat | Status |
| --- | --- | --- | --- |
| 1 | The word `store` leaves | structural | not started |
| 2 | `ledger.py` becomes `ledger/__init__.py` | structural | not started |
| 3 | One name for one ledger | structural | not started |
| 4 | Where a ledger's file lives | structural | not started |
| 5 | The 42 wrappers go | structural | not started |
| 6 | What settles two rows | structural | not started |
| 7 | What a writer's file is called | structural | not started |
| 8 | Reading and writing a CSV ledger, and three things leave | structural | not started |

**Every row in this plan wears one hat and it is the structural one.** No signature changes, no default changes, no return type changes, and no byte on disk moves. A row that finds itself wanting a behaviour change has found a defect, and the defect gets its own pull request (CLAUDE.md section 5, Kent Beck's rule about not interleaving the two).

## 2. What is measured, 2026-09-26

| | |
| --- | --- |
| `backend/idhazh/ledger.py` | **2,342 lines**, about 120 top-level names |
| Files importing it | **108**, all as `from idhazh import ledger` or `from idhazh.ledger import ...` |
| Call sites that must change in row 2 | **zero.** `from idhazh import ledger` resolves identically against `ledger/__init__.py` |
| String literals naming the file path | **three**: [backend/tests/pipeline/test_day_shards.py](../backend/tests/pipeline/test_day_shards.py) lines 274 and 340, [backend/tests/workflows/test_ledger_staging.py](../backend/tests/workflows/test_ledger_staging.py) lines 766 and 773 |
| Tests that glob the top level | **none.** `test_repo_structure.py` globs `contracts/*.py` and `council/*.py` only. Several tests `rglob("*.py")` over `backend/idhazh`, which picks up package members by itself |
| The word `store` standalone | **1,602 hits in 229 files**: `backend/idhazh` 200/55, `backend/tests` 399/60, `backend/utilities` 129/11, `frontend` 47/26, `docs` 310/51, `TODO` 509/22, `.github` 8/4 |
| `ledger` / `collection` / `store` | **3,067 / 307 / 931** |

**The blast radius reported before this measurement was wrong and is corrected here.** An earlier answer said promoting the module would break `test_repo_structure.py`. It globs two subpackages and never the top level. Nothing in that test is affected.

## 3. The shape this plan builds

```
backend/idhazh/
    contracts/
        ledger_name.py        <- LedgerName lives HERE, not in the package
    ledger/
        __init__.py           imports and __all__, no definition of any kind
        paths.py              where one ledger's file for one period lives
        keys.py               what makes two rows the same record, and which wins
        filenames.py          what one writer's file is called
        csv_file.py           how rows are read out of and written into a CSV
        headers.py            how a file under an older header is read
        rows.py               how a caller puts rows in and gets them back
        settle.py             which rows repeat a key, and what dropping them costs
        persist.py            <- plan 50 row 2 lands here
        parquet.py            <- plan 50 row 2. The only pyarrow importer
        json_lines.py         <- plan 50 row 2
        arrow_schema.py       <- plan 50 row 2
    path_classes.py           was paths.py; how git settles two runs on one path
```

**`LedgerName` is in `contracts/` and not in the package, and this is not a preference.** `FileEnvelope` is typed by it, and CLAUDE.md section 4 forbids `contracts/` from importing any other `idhazh` subpackage. Contracts are the bottom of the graph, so the vocabulary has to be there.

**Submodules import each other by module path** - `from idhazh.ledger import paths` - and never import the package. Otherwise loading one submodule pulls the whole facade.

## 4. The contracts a worker must not invent

### 4.1 `LedgerName` - `backend/idhazh/contracts/ledger_name.py`

One `StrEnum`, one member per directory under `state/`, the value being the directory name exactly as it is on disk today. It replaces **three** closed sets over one vocabulary: `SegmentLedger`, `STORE_DIRNAMES`, and the 25 `*_DIRNAME` constants.

**The 25 constants are deleted, not renamed.** `SEEN_DIRNAME: Final = "seen"` sitting beside `LedgerName.SEEN` is a second spelling of one string, which is the defect this plan exists to remove. `LEDGER_DIRNAMES` is derived from the enum with a comprehension, never hand-listed.

What made `SegmentLedger` and `LedgerName` look like two types is that their members carry different properties - nine are day trees with a settlement key and twelve are not. **Those are cells on a table row, not separate types.**

### 4.2 `LedgerShape` and the `LEDGERS` table - `backend/idhazh/ledger/paths.py`

The 42 path functions are 21 hand-written pairs, and `X_relpath(date)` and `X_path(state_dir, date)` differ only in return type and whether the caller is holding the state directory. That is 21 duplications of one fact. One table replaces them:

```python
class Grain(StrEnum):
    """How much time one of this ledger's files covers, and therefore its name."""
    FLAT = "flat"        # feed-retirements.csv - one file, no date in the path
    DAY_FILE = "day"     # seen/<YYYY>/<MM>/<DD>.csv - one file per day
    DAY_TREE = "tree"    # item-health/<YYYY>/<MM>/<DD>/<writer>.csv - many writers
    MONTH_FILE = "month" # telemetry-aggregate/<YYYY-MM>.csv
    STAMPED = "stamp"    # score-distribution/archive/<stamp>.csv

class LedgerShape(NamedTuple):
    """Everything about where one ledger's rows are written and what settles them."""
    prefix: tuple[str, ...]        # ("llm-council", "shard-outcomes") for a nested one
    grain: Grain
    filename: str | None           # only when grain is FLAT
    key: tuple[str, ...] | None    # the dedup key, None where the ledger has none
    preference: Preference | None  # which duplicate wins, None means keep the first

LEDGERS: Final[Mapping[LedgerName, LedgerShape]] = {...}   # every member, no gaps
```

Two builders replace forty-two:

```python
def path(state_dir: Path, ledger: LedgerName, covers: str | None = None) -> Path
def relpath(ledger: LedgerName, covers: str | None = None) -> str
```

**The table has no gaps and a test proves it**, iterating `LedgerName` and refusing a member with no row by name. A `Grain` that needs a `covers` and is handed `None` raises, naming the ledger and the grain.

### 4.3 `ledger/__init__.py` - a facade, and what keeps it honest

The 108 call sites do not change. `ledger.append_seen(state_dir, date, rows)` reads better at a call site in `stages/plan.py` than `rows.append_seen(...)` would, because `rows` names nothing a caller cares about. The split is for the maintainer of the package, not for its callers.

**The facade is only honest because the collapse happens.** A 120-name `__all__` is a dumping ground with a new filename. Rows 3 to 8 take 42 path functions to 2, about 25 row verbs to 2, 25 directory constants to 1 enum, and 16 key tuples into table cells. A facade over roughly twenty names is a reasonable package surface. **Were this a move with no collapse, the ruling would be the other way and all 108 call sites would name their module.**

Two obligations replace a removal condition, because a facade is not a shim and does not expire:

- `__init__.py` holds imports and `__all__` and **no definition of any kind**. Proved by an AST walk asserting zero top-level `FunctionDef` and `ClassDef` - the same oracle family plan 50 uses for the single-pyarrow rule, and an AST walk rather than a grep for the same reason.
- **Every row that collapses names cuts `__all__` in the same pull request.** The shrink is part of the change that causes it, never a later tidy.

`mypy` runs with `no_implicit_reexport` here, so `__all__` is load-bearing rather than decoration.

### 4.4 Three things leave the package and do not come back

| What | Why it is not a ledger question | Where |
| --- | --- | --- |
| `feed_reliability`, `reliability`, `_run_n` | Domain arithmetic that happens to read a ledger. It answers "how reliable is this feed", which is a question about feeds | Its own module beside [backend/idhazh/telemetry/source_health.py](../backend/idhazh/telemetry/source_health.py) |
| `shards_in_window` | **Its own docstring says so**: "No ledger is read with this any more." It returns month stems, and its only surviving reader sizes `observability.item_health_full_grain_months` against `console.max_window_days` - a knob question | [backend/idhazh/month_partition.py](../backend/idhazh/month_partition.py) or the knob module |
| `HEALTH_WINDOW_DAYS` | A hardcoded tunable among siblings that all read config | Out of scope, own pull request (Guardrail #6) |

## 5. The naming collisions this plan settles

| # | Collision | Settled as |
| --- | --- | --- |
| 1 | `dataset`, plan 50's argument name **and a persisted footer key** | Becomes `ledger`. It is a fourth word for a thing that already had three, and unlike the other three it goes into committed bytes. Nothing has written an envelope yet, so today it is a text edit |
| 2 | `ledger/paths.py` beside the existing `backend/idhazh/paths.py` | The top-level one becomes `path_classes.py`. It answers "how does git settle two runs on one path", which is not a path question, and **its own test is already named `test_path_classes.py`** |
| 3 | Plan 50's `naming.py` | A gerund with no object, so it names no question and fails section 1a. Folds into `ledger/filenames.py` beside `segment_name` and `parse_segment_name`. The CSV grammar's eventual deletion is then a diff in one file |
| 4 | `store` in [docs/concepts/partitions.md](../docs/concepts/partitions.md) does not all mean `ledger` | That page lists `frontend/public/digest/<YYYY>/<MM>/<DD>/`, which nothing reads as a later run's memory. **Under `state/` it is a ledger; under `frontend/public/` it is a collection.** The test is the reader, never the shape on disk |
| 5 | The glossary rows for `ledger` and `segment` both link to `backend/idhazh/ledger.py` | Repointed in row 2, to `ledger/__init__.py` and `ledger/filenames.py`. The glossary's own rule is that the link is the definition, so a broken link is a broken definition |

---

## Row #1 - The word `store` leaves

- **Scope:** 1,602 occurrences across 229 files. No file moves and no identifier that is not listed below changes.
- **The rule, applied per occurrence:** under `state/` it is a **ledger**; under `frontend/public/` it is a **collection**; where the word is the ordinary English verb it is **left alone**.
- **Left alone, by name:** `restore`, `restores`, `restored`, `restoreAnchor`, `storedChoice`, `storedDates`, `store_true`, `store_false`, and every sentence where `stores` is the verb - `test_the_row_stores_counts_and_leaves_every_rate_to_be_derived`, `test_the_manifest_stores_the_publisher_map_it_froze`.
- **Identifiers that change:**
  - `STORE_DIRNAMES` -> `LEDGER_DIRNAMES` (deleted outright in row 3; renamed here so row 3 has one thing to delete rather than two)
  - `WRITER_OWNED_STORES`, `STORES_NO_JOB_WRITES`, `STORES_NOTHING_FILLS_YET`, `STORES_NO_RUN_FILLS`, `COUNCIL_STORE`, `RETIRED_STORE_SWEEP`, `RETIRED_STORE_PATH` -> the `LEDGER` spelling of each
  - `backend/utilities/check_seeded_stores.py` -> `check_seeded_ledgers.py`, with `class Store` -> `class Ledger` and `seeded_stores()` -> `seeded_ledgers()`. Its test file renames with it
  - `backend/utilities/empty_column_census.py`: `class Store(NamedTuple)` -> `class Ledger`, `STORES` -> `LEDGERS`, `census(root, store)` -> `census(root, ledger)`
  - `backend/idhazh/telemetry/prune.py`: `day_collection(state_root, store: str)` and `as_outcome(store: str, ...)` -> `ledger: str`
  - About thirty test function names carrying the word
- **Files touched:** the 229 measured, plus `.github/` where the renamed utility is called, plus [docs/concepts/glossary.md](../docs/concepts/glossary.md) (already done, 2026-09-26) and the three plan-docs under `TODO/`.
- **Acceptance gates:** `ruff check .`, `mypy backend`, the full `pytest backend/tests`, and the frontend selector. **A test function rename is zero-risk** - pytest discovers by prefix - so the suite is the check that nothing else moved.
- **Oracle:** a ratchet test. The standalone word appears **zero** times outside a third-party quotation, counted by the same regex this plan measured with - `(?<![a-zA-Z_])[Ss]tores?(?![a-zA-Z_])` - over `backend/`, `frontend/src/`, `frontend/tests/`, `config/`, `docs/`, `TODO/` and `.github/`. **Without the ratchet the word walks back in**, because plan 50's own drafts are full of it.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `ledger` rather than `dataset`, `collection` or a new word. Measured: `ledger` 3,067 uses with a glossary definition against `store` 931 with none. **Deleting a duplicate is cheaper than minting a fourth name** | Owner, 2026-09-26 |
  | 2 | The ratchet is a test and not a review habit. A review habit is what let three words coexist | Fowler |
  | 3 | This row ships before the package move, so row 2 is a pure `git mv` with nothing else in the diff | Fowler, Tidy First |

---

## Row #2 - `ledger.py` becomes `ledger/__init__.py`

- **Scope:** `git mv`, add `__all__`, fix three string literals, repoint two glossary rows. **Nothing else may be in this diff.**
- **Files touched:**
  - `backend/idhazh/ledger.py` -> `backend/idhazh/ledger/__init__.py`
  - [backend/tests/pipeline/test_day_shards.py](../backend/tests/pipeline/test_day_shards.py) lines 274 and 340, [backend/tests/workflows/test_ledger_staging.py](../backend/tests/workflows/test_ledger_staging.py) lines 766 and 773 - the four string literals naming the old path
  - [docs/concepts/glossary.md](../docs/concepts/glossary.md) - the `ledger` and `segment` rows
  - `docs/architecture/contracts/` - **the new page carrying the module docstring, see decision 2**
- **Acceptance gates:** `ruff check .`, `mypy backend`, full `pytest backend/tests`.
- **Oracle:** `pytest --collect-only -q` produces a **byte-identical** name list before and after. A structural move that changed which tests exist is not a structural move.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Zero call sites change. `from idhazh import ledger` resolves identically | Fowler, Branch by Abstraction. The facade is the stable seam while modules move underneath it |
  | 2 | **`ledger.py`'s opening 90 lines do not get deleted and do not get split.** They are the best explanation this project has of its own state directory - why `state/published` files by day, what reading it costs measured on real hardware, why `visual-prunes` is the declared exception to the partition rule. A twelve-module package cannot hold one docstring and a table cell cannot either, so it becomes a page under `docs/architecture/contracts/` (Guardrail #4). **This row is not done until it has** | Fowler. Named as the largest cost of the whole plan and the one most likely to be skipped |
  | 3 | `__all__` is grouped by the module each name will end up in, one comment per group, so `__init__.py` reads as an index rather than a wall | Fowler |

---

## Row #3 - One name for one ledger

- **Scope:** `LedgerName` is minted in `contracts/`, and three existing spellings of the same vocabulary are deleted.
- **Files touched:** `backend/idhazh/contracts/ledger_name.py` (new), `backend/idhazh/contracts/__init__.py`, `backend/idhazh/ledger/__init__.py` (the 25 constants and `LEDGER_DIRNAMES` go; `SegmentLedger` goes), and every reader of a deleted name.
- **Acceptance gates:** as row 2.
- **Oracle:** every deleted constant's string value appears as **exactly one** `LedgerName` member, checked by recomputing the set from git rather than by a hand-written list. And `LEDGER_DIRNAMES` equals the enum's value set, computed both ways.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One type, not two. `SegmentLedger` and the drafted `LedgerName` answer the same question and draw their strings from the same constants. **Plan 50 rows 9 and 10 were about to add the same four names to both** | Fowler |
  | 2 | The constants are **deleted**, not renamed. A `Final` string beside an enum member of the same value is a second spelling | Fowler, Guardrail #4 |
  | 3 | `LedgerName` lives in `contracts/` because `FileEnvelope` is typed by it and CLAUDE.md section 4 forbids `contracts/` importing another subpackage | CLAUDE.md section 4 |
  | 4 | Day-tree membership and settlement keys are **cells on a table row**, not a reason for a second type. `_TREE_SHAPES` is that table already; it is keyed on nine ledgers and becomes keyed on all of them, with a named refusal for one that is not a day tree | Fowler |

---

## Row #4 - Where a ledger's file lives

- **Scope:** `ledger/paths.py` and the `LEDGERS` table (section 4.2). The 42 functions become one-line wrappers over it and are **not yet deleted**.
- **Files touched:** `backend/idhazh/ledger/paths.py` (new), `backend/idhazh/ledger/__init__.py`, `backend/idhazh/paths.py` -> `backend/idhazh/path_classes.py` and its importers, `backend/tests/contracts/test_path_classes.py` (the name it already has).
- **Acceptance gates:** as row 2.
- **Oracle:** **exact parity.** For every `LedgerName` member and a fixed date, the old function and the new builder return equal values - both the `Path` and the `relpath` spelling. A member whose grain needs a `covers` is also driven with `None` and must raise, naming the ledger.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Wrappers first, deletion in row 5. Two hats otherwise | Fowler, Tidy First |
  | 2 | The table carries a `prefix` tuple rather than a single directory, because `content-similarity-judge/scored-pairs/` nests and `llm-council/shard-outcomes/` nests | Fowler |
  | 3 | Refactorings in play, named so the diff is readable: **Introduce Parameter Object** for `LedgerShape`, then **Replace Conditional with Lookup Table** | Fowler |

---

## Row #5 - The 42 wrappers go

- **Scope:** delete the 42, move the call sites to `paths.path()` and `paths.relpath()`, cut the names from `__all__`.
- **Files touched:** `backend/idhazh/ledger/__init__.py`, plus every caller mypy names.
- **Acceptance gates:** as row 2.
- **Oracle:** **mypy is the oracle.** A deleted name with a live caller is a type error, not a silent default. A row that needs a hand-written list of call sites has not finished.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Inline Function**, all 42 at once. Staging it leaves two spellings live and a reviewer with no way to tell which is current | Fowler |

---

## Row #6 - What settles two rows

- **Scope:** `ledger/keys.py`. Takes the 16 `*_KEY` tuples, `preference_for`, the three `_*_rule` functions, the `Preference` protocol, and `_TreeShape` / `segment_contract` / `segment_key` / `segment_carried`.
- **Files touched:** `backend/idhazh/ledger/keys.py` (new), `backend/idhazh/ledger/__init__.py`.
- **Acceptance gates:** as row 2.
- **Oracle:** as row 2 - `pytest --collect-only -q` byte-identical. The moved name set is **recomputed** from the two files rather than hand-picked, so a name left behind is a failure rather than an omission nobody sees.

---

## Row #7 - What a writer's file is called

- **Scope:** `ledger/filenames.py`. Takes `SegmentName`, `SEGMENT_NAME`, `SEGMENT_SUFFIX`, `BEFORE_PARTITION_NAME`, `PRE_IDENTITY_TRACE`, `REPAIR_NAME`, `REPAIR_STAMP`, `repair_name`, `is_repair`, `segment_name`, `parse_segment_name`, `day_shard_path`, `day_shard_relpath`.
- **Files touched:** `backend/idhazh/ledger/filenames.py` (new), `backend/idhazh/ledger/__init__.py`, [docs/concepts/glossary.md](../docs/concepts/glossary.md) (the `segment` row's link).
- **Acceptance gates:** as row 2.
- **Oracle:** as row 6.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Plan 50's `naming.py` lands here and not beside it.** Both answer "what is this file called"; one in the CSV grammar, one in the parquet one. Keeping them together means the CSV grammar's eventual deletion is a diff in one file | Fowler, collision 3 |

---

## Row #8 - Reading and writing a CSV ledger, and three things leave

- **Scope:** the last four modules, and the three groups that are not ledger questions.
- **Files touched:**
  - `backend/idhazh/ledger/csv_file.py` (new: `read_header`, `require_matching_header`, `_csv_line`, `render_file`, `_read_rows`, `_stream_rows`, `extend_ledger_file`, `CsvRecord`, `CsvContract`)
  - `backend/idhazh/ledger/headers.py` (new: `refiler`, `_headings`, `_unplaceable`, `_refile`, `migrate_header`)
  - `backend/idhazh/ledger/rows.py` (new: the generic half of the append and load verbs, plus `write_segment` and `extend_segment` until plan 50 row 2 takes them)
  - `backend/idhazh/ledger/settle.py` (new: `KeyedLedger`, `keyed_paths`, `drop_repeated_rows`, `repeated_keys`)
  - the three departures of section 4.4, and their new homes
  - `backend/idhazh/ledger/__init__.py`
- **Acceptance gates:** as row 2.
- **Oracle:** as row 6, plus the AST shape test on `__init__.py` - **zero top-level `FunctionDef`, zero top-level `ClassDef`**. This row is where the facade first becomes provably a facade.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `shards_in_window` leaves because **its own docstring already says no ledger is read with it** | Fowler |
  | 2 | `feed_reliability` and `reliability` leave because they answer a question about feeds. A module that reads a ledger is not thereby a ledger module | Fowler |

---

## What plan 50 has to absorb, and one of it is ESCALATE-class

| # | Finding | What plan 50 does |
| --- | --- | --- |
| 1 | **`persist()` cannot return a single `Path`.** `write_segment` routes each row under the day its **own `date` cell** names, so one call writes two files. The rule is spelled once today, in `_dated_rows`: "rows a run left behind three days ago land under that day rather than under today." That is CLAUDE.md section 2 applied, and `persist` cannot replace `write_segment` without it | **Keep the routing, return `list[Path]`.** The alternative is twenty producers each learning to group their own rows by date, which is the same rule written twenty times. **ESCALATE-class correction to plan 50 section 5.9 and row 2** |
| 2 | `backend/idhazh/store/` never exists | Row 2 creates `ledger/persist.py`, `ledger/parquet.py`, `ledger/json_lines.py`, `ledger/arrow_schema.py`. Its `naming.py` folds into `ledger/filenames.py` and its `paths.py` into `ledger/paths.py` |
| 3 | `write_segment` is `persist(fmt=Format.CSV)` | It becomes one, **carrying its removal condition on its declaring line** (Guardrail #6): it goes when no ledger is written as CSV |
| 4 | `dataset` is a fourth word and it reaches committed bytes as envelope key 4 | Becomes `ledger`, in the plan text now and in the contract when row 2 builds it |
| 5 | Rows 9 and 10 add four names to `LedgerName` that `SegmentLedger` already holds | Row 3 here collapses them first, so those rows add nothing |

**The minimum that unblocks plan 50 is rows 2 and 3.** `persist()` needs a package to live in and an enum to type its first argument, and nothing else in this sequence.

**The recommendation is still to land all eight first and fast.** Plan 50 rows 3, 9 and 10 all name `backend/idhazh/ledger.py` in their Files touched. A split branch left open against a file another row is editing is a branch that gets redone - measured on this repository once already, on `app_config.py`, which collected 54 commits of divergence in a day.

## What this costs

| # | Cost | What softens it |
| --- | --- | --- |
| 1 | **The module docstring.** Ninety lines that are the best explanation this project has of its own state directory | Row 2 decision 2. It moves to `docs/architecture/contracts/` and row 2 is not done until it has. **This is the largest cost and the one most likely to be skipped** |
| 2 | **Nine merge surfaces where there was one.** Two branches that used to conflict visibly in one file now auto-merge clean across two modules, producing a tree where a key moved and its path did not | Measured here already: a five-entry `__changelog__` tuple auto-merged to six with no conflict reported. The `LEDGERS` table is the defence - one row per ledger, so a half-move is a missing cell rather than two modules quietly disagreeing |
| 3 | A reader following `ledger.X` has one extra hop, because the facade hides which module | `__all__` grouped by source module, one comment per group |
| 4 | `__init__.py` is now the thing that can rot | The AST shape test in row 8. Somebody has to not delete it |
| 5 | The word `ledger` gains a fourth grain - a committed file, a directory tree, a day directory, and now a package | Small, and `contracts/` and `telemetry/` already set the precedent. Cheaper than the fifth word that finding 4 removes |
| 6 | Plan 50 goes stale in roughly thirty places | One editing pass, before its row 2 starts. **No committed path changes** |

## See also

- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) - the plan this one unblocks; its row 2 is this sequence's ninth pull request.
- [`../docs/concepts/glossary.md`](../docs/concepts/glossary.md) - where the vocabulary decision is written down.
- [`../CLAUDE.md`](../CLAUDE.md) - section 1a for the one-question rule, section 4 for why `LedgerName` is in `contracts/`, section 6 for the correction level.
