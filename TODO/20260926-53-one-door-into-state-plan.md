# Plan 53 - One door into `state/`

**Last Updated**: 2026-09-26

**Level**: 5 for the decision, 3 for every row (CLAUDE.md section 6). Level 5 because what is settled here binds every producer added after it: `backend/idhazh/ledger/` is the one door into `state/` and `backend/idhazh/store/` never exists. Level 3 per row because each crosses a subsystem boundary and none can break published data.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## 0. Operating contract

**Chain** (CLAUDE.md section 0d). **Intent**: a producer should have one way to put a row into `state/` and one way to read it back (section "The intent this plan serves"). **Contract**: section 4 declares every type, table, signature and destination a worker must not invent. **Code**: the six rows.

| Field | Value |
| --- | --- |
| Why this plan exists | A producer has four ways to write `state/` and four to read it, and plan 50 was about to add a fifth in a second vocabulary. This makes `backend/idhazh/ledger/` the one door, splits the 2,342-line `ledger.py` into modules that each answer one question, and retires the word `store` so one thing has one name. |
| Hard scope - in | see the bullets below |
| Hard scope - out | see the table below |
| ESCALATE triggers | see the enumerated list below |
| Chosen strategy | Retire the word, promote the file to a package behind a stable facade, mint the vocabulary, then move one concern per pull request - reader before writer, behaviour unchanged, no byte on disk moved. Ruled by Fowler (CLAUDE.md section 14). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. **Parallel N = 2.** The extraction is serial on `ledger/__init__.py`; the second slot exists for the one disjoint code row (row 4). Not 4, because there is one disjoint row to run beside the chain and no more. |
| Blocks | **Plan 50's row titled "The payload ledger, the two roots, and the arrow mapping" is unblocked once rows 2 and 3 merge** - it needs a package to live in and a `LedgerName` to type its first argument. It then edits `ledger/__init__.py` to export `persist`, so landing all six rows first is the recommendation: an open branch against a file the extraction rows are still moving is a branch that gets redone. |

### Hard scope - in

- `backend/idhazh/ledger.py`, 2,342 lines and about 120 top-level names, becomes the package `backend/idhazh/ledger/`, each module answering one question.
- The word `store` leaves the repository. Under `state/` it becomes **ledger**; under `frontend/public/` it becomes **collection** (glossary decision, 2026-09-26).
- `SegmentLedger` (a 9-member enum) and the 25 `*_DIRNAME` constants collapse into one `LedgerName` `StrEnum` in `backend/idhazh/contracts/`, with a `DAY_TREES` subset for the nine a writer files a segment into.
- 42 hand-written path functions collapse into one `LedgerPath` table and two builders in `ledger/paths.py`.
- `backend/idhazh/paths.py` becomes `path_classes.py`, the name its own test already carries.

### Hard scope - out

| Not here | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Parquet, the envelope, the two tiers, compaction | `state/` stays CSV end to end; nothing about how a file is encoded changes | Plan 50's row titled "The payload ledger, the two roots, and the arrow mapping", which lands `persist.py` / `parquet.py` **inside** `ledger/` |
| Moving any committed byte | **This whole plan writes nothing to disk.** Every file under `state/` keeps its path, its name and its bytes | Plan 50's ledger-migration rows |
| Any change to `write_segment` / `extend_segment` behaviour | Both move verbatim to `ledger/rows.py` in row 6 - same signature, same `int` return, same routing of a row under the day its own `date` cell names. Plan 50's frozen `persist` stands on that behaviour | Plan 50, which is frozen from a design point of view; this plan does not touch it |
| `HEALTH_WINDOW_DAYS: Final = 31` | A hardcoded tunable survives among siblings that read their window from config | Its own one-line pull request. It is Guardrail #6, not this plan's question |
| The retention windows, the prune passes, the gardener | Untouched | Plan 50 |

### ESCALATE triggers

1. **A row cannot finish without a behaviour change.** Every row here is structural - no signature, default, return type or on-disk byte moves. A row that finds it cannot preserve behaviour has found a defect: stop, and give the defect its own pull request (CLAUDE.md section 5; do not interleave structural and behavioural change).
2. **`write_segment` or `extend_segment` cannot move verbatim** (row 6). Their exact behaviour is what plan 50's frozen `persist` stands on. Stop before the commit.
3. **`LedgerName` is about to enter a persisted `contracts/` payload before row 3 lands.** That makes row 3 Level 5 - pause for sign-off (CLAUDE.md section 6).
4. **The `store` ratchet would have to allow a word outside row 1's fenced block.** The sweep missed a real occurrence; surface it, do not widen the allow-list.

### The intent this plan serves

**A producer should have one way to put rows into `state/` and one way to get them back.** Today it has four, and plan 50 was about to build a fifth.

The four are visible in one signature comparison. `ledger.write_segment(state_dir, ledger, rows, *, run_id, attempt, job, shard, date=None)` and plan 50's drafted `persist(rows, *, dataset, covers, identity, tier, period, built_from, fmt)` carry **the same six facts in two spellings**. Shipping the second beside the first would have meant twenty-odd producers each knowing which door they were, and a reader of `state/` needing both vocabularies to read one directory.

The second half of the intent is the file that made this invisible. `backend/idhazh/ledger.py` is 2,342 lines and answers at least eleven questions: what the directories are called, what makes two rows the same record, where each ledger's file lives, how a CSV is read, how an old header is migrated, what a segment filename means, how each of twenty ledgers is appended to and loaded, how duplicates are dropped, how a feed's reliability is computed, and what a month window is. CLAUDE.md section 1a says a source file answers one narrow question and that **if answering it needs a long file, the question is too broad**. This file is the standing counter-example, and every plan that has touched it has had to read all of it to change one thing.

**What a reader gets: one word for one thing, and a file whose first sentence tells them whether to keep reading.**

## 1. Status Reckoner

One row is one pull request. **Six rows, not eight.** The extraction funnels through one facade file, so smaller rows add pull requests without buying parallelism - they were combined (Fowler, Carmack: the machine is one box, and a parallel edit to `ledger/__init__.py` costs an unreviewed merge, not wall-clock).

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The retired word `store` leaves | - | A | PENDING | - | - | - |
| 2 | `ledger.py` becomes the package, and its docstring becomes a page | 1 | B | PENDING | - | - | - |
| 3 | One `LedgerName` for one ledger | 2 | C | PENDING | - | - | - |
| 4 | `paths.py` becomes `path_classes.py` | 2 | P | PENDING | - | - | - |
| 5 | One `LedgerPath` table replaces 42 path functions | 3, 4 | D | PENDING | - | - | - |
| 6 | The rest of the module splits, and the facade becomes provably empty | 5 | E | PENDING | - | - | - |

**Every row wears one hat and it is the structural one.** No signature, default or return-type changes, and no byte on disk moves. A row that finds itself wanting a behaviour change has found a defect, and the defect gets its own pull request (ESCALATE trigger 1).

**The critical path is 1 -> 2 -> 3 -> 5 -> 6, five pull requests.** Row 4 is the one disjoint code row and fills the second slot.

**Rows 3, 5 and 6 each edit `ledger/__init__.py`, so they are serial whatever their letters say** (execute-a-plan.md: rows that share one surface do not parallelise). That is why Parallel N is 2 and not 4.

**Row 4 shares exactly two test files with rows 3 and 6** - `backend/tests/workflows/test_worker_ledgers.py` and `backend/tests/workflows/test_daily_commit_steps.py`, which both name `idhazh.paths` and `SegmentLedger`. The pool holds row 4 while row 3 or row 6 is in flight and runs it in the gap; readiness is the file-disjointness test, never the letter. Everywhere else row 4 is disjoint - `ledger.py` never imports `idhazh.paths`, it only mentions it in one comment.

**The plan-doc is excluded from the disjointness diff.** Every row stamps its own Reckoner line in its own change (execute-a-plan.md), so the file is in every row's real set.

## 2. What is measured, 2026-09-26

| | |
| --- | --- |
| `backend/idhazh/ledger.py` | **2,342 lines**, about 120 top-level names, **no `__all__` today** (row 2 adds it) |
| Files importing it | **108**, all as `from idhazh import ledger` or `from idhazh.ledger import ...` |
| Call sites that change in row 2 | **zero.** `from idhazh import ledger` resolves identically against `ledger/__init__.py` |
| String literals naming the old file path | **four**: `backend/tests/pipeline/test_day_shards.py` lines 274 and 340, `backend/tests/workflows/test_ledger_staging.py` lines 766 and 773 |
| Files reading `SegmentLedger` | **36** (`backend/idhazh` 11, `backend/utilities` 3, `backend/tests` 22). Row 3 rewires every one; mypy names any it missed |
| Files importing `idhazh.paths` | **`cli.py` plus about seven test files.** `ledger.py` is not one - it mentions `idhazh.paths` in a single comment, so the `path_classes` rename does not touch the extraction chain |
| Eviction homes, all present today | `backend/idhazh/telemetry/source_health.py`, `backend/idhazh/month_partition.py` |
| The word `store` standalone | **1,602 hits in 229 files** (`backend/idhazh` 200, `backend/tests` 399, `backend/utilities` 129, `frontend` 47, `docs` 310, `TODO` 509, `.github` 8) |
| `ledger` / `collection` / `store` | **3,067 / 307 / 931.** `ledger` carries the glossary definition; `store` is defined nowhere |

**A correction to this document's own prose.** An earlier `store`->`ledger` sweep over-applied to the sentences that *name* the retired word, so a prior draft read "the word `ledger` leaves" and "`ledger` / `collection` / `ledger`". Those are corrected above and throughout. Row 1's oracle exists to stop exactly this: the retired word survives only inside a fenced instruction block.

## 3. The shape this plan builds

```
backend/idhazh/
    contracts/
        ledger_name.py        LedgerName + DAY_TREES live HERE, not in the package
    ledger/
        __init__.py           imports and __all__, no definition of any kind
        paths.py              where one ledger's file lives: the LedgerPath table
        keys.py               what makes two rows one record, and the day-tree shapes
        filenames.py          what one writer's file is called
        csv_file.py           how rows are read out of and written into a CSV
        headers.py            how a file under an older header is read
        rows.py               how a caller puts rows in and gets them back
        settle.py             which rows repeat a key, and what dropping them costs
        persist.py            <- plan 50, NOT built here
        parquet.py            <- plan 50, the only pyarrow importer, never eagerly re-exported
        json_lines.py         <- plan 50
        arrow_schema.py       <- plan 50
    path_classes.py           was paths.py; how git settles two runs on one path
```

**`LedgerName` is in `contracts/`, not in the package.** `FileEnvelope` (plan 50) is typed by it, and CLAUDE.md section 4 forbids `contracts/` from importing another `idhazh` subpackage. Contracts are the bottom of the graph, so the vocabulary lives there.

**Two tables, not one.** Where a file lives - prefix, grain, filename - is a different question from what settles two of its rows - key, preference, contract. `paths.py` owns the first (row 5) and `keys.py` owns the second (row 6), each keyed on `LedgerName`. A single merged table would make row 6 edit the structure row 5 built, re-coupling the two concerns the split exists to separate, and would force `paths.py` to import `keys.py` for a type it does not otherwise need. Rejected: the merged `LedgerShape` an earlier draft drew (Fowler, section 4.2).

**The facade never eagerly re-exports the pyarrow module.** When plan 50 adds `parquet.py`, the 108 files that do `from idhazh import ledger` must not pay a pyarrow import to reach a CSV path. Row 6 writes that rule into the facade contract while the facade is being defined (Carmack, section 4.5).

**Submodules import each other by module path** - `from idhazh.ledger import paths` - and never import the package, or loading one submodule pulls the whole facade.

## 4. The contracts a worker must not invent

Everything a worker needs to build is declared here. Where a shape is derived from the existing code, the derivation rule and the oracle that proves it are given rather than a hand-typed list that could drift; where a shape is new, it is written out in full.

### 4.1 `LedgerName` and `DAY_TREES` - `backend/idhazh/contracts/ledger_name.py`

One `StrEnum`, one member per ledger currently addressed under `state/`, the value being the on-disk name exactly. It replaces **three** spellings of one vocabulary: `SegmentLedger`, `STORE_DIRNAMES` (renamed `LEDGER_DIRNAMES` in row 1), and the 25 `*_DIRNAME` constants.

- **Membership is derived, not invented.** Every `*_DIRNAME` constant in `ledger.py` becomes one member whose value is that constant's string; every nested ledger a path function addresses (for example `llm-council/shard-outcomes`, `content-similarity-judge/scored-pairs`) becomes one member too. The nesting is carried by `LedgerPath.prefix` (section 4.2), not by the member value.
- **The coverage oracle is what proves completeness.** `LEDGER_DIRNAMES` is recomputed from the enum with a comprehension and must equal the old `STORE_DIRNAMES` set plus the nested names, computed both ways from git. Row 5's exact-parity test then proves every old path function has a member that reproduces its path.

```python
DAY_TREES: Final[frozenset[LedgerName]] = frozenset({...})   # the nine, no more
```

`DAY_TREES` is the subset a writer files a segment into - exactly the nine `SegmentLedger` had. It is what `write_segment`, `segment_contract` and the tree-shape table key on (section 4.3), and what every `for tree in SegmentLedger` loop becomes (`telemetry/prune.py`'s `WRITER_OWNED_LEDGERS`, `stages/compact.py`, and the tests). **Its coverage oracle**: `{m.value for m in DAY_TREES}` equals the old `SegmentLedger` value set, computed from git.

**`SegmentLedger` is deleted, not aliased.** A second enum whose members duplicate a `LedgerName` subset is the defect this plan removes. One enum, one typed subset, one coverage test each.

**Why one type and a subset, not two types.** `SegmentLedger` and `LedgerName` answered the same question and drew their strings from the same constants; the only difference was which members carried a settlement shape, and that is a subset, not a second type. Collapsing to one type widens the segment functions from a 9-member argument to a 21-member one, so they gain a **named runtime refusal**: `write_segment(state_dir, LedgerName.PUBLISHED, ...)` no longer fails to type-check, so it must raise at the call, quoting the ledger and its grain (section 4.3). A runtime refusal is the right trade for a build-time producer - a wrong call is a failed CI job, not a served error - but only paired with `DAY_TREES` and its coverage test (Fowler).

### 4.2 `LedgerPath` and the path table - `backend/idhazh/ledger/paths.py`

The 42 path functions are 21 hand-written pairs: `X_relpath(date)` and `X_path(state_dir, date)` differ only in return type and whether the caller holds the state directory. One table and two builders replace them. **The table carries where a file lives and nothing else** - no dedup key, no preference, no contract. Those are a different question and live in `keys.py` (section 4.3).

```python
class Grain(StrEnum):
    """How much time one of this ledger's files covers, and therefore its name."""
    FLAT = "flat"        # feed-retirements.csv - one file, no date in the path
    DAY_FILE = "day"     # seen/<YYYY>/<MM>/<DD>.csv - one file per day
    DAY_TREE = "tree"    # item-health/<YYYY>/<MM>/<DD>/<writer>.csv - many writers
    MONTH_FILE = "month" # telemetry-aggregate/<YYYY-MM>.csv
    STAMPED = "stamp"    # score-distribution/archive/<stamp>.csv


class LedgerPath(NamedTuple):
    """Where one ledger's file for one period lives. Nothing about settling it."""
    prefix: tuple[str, ...]   # ("llm-council", "shard-outcomes") for a nested one
    grain: Grain
    filename: str | None      # only when grain is FLAT; None otherwise


LEDGER_PATHS: Final[Mapping[LedgerName, LedgerPath]] = {...}   # every member, no gaps
```

Two builders replace forty-two:

```python
def path(state_dir: Path, ledger: LedgerName, covers: str | None = None) -> Path
def relpath(ledger: LedgerName, covers: str | None = None) -> str
```

`covers` is the period the caller wants - a `YYYY-MM-DD` day for a `DAY_FILE` or `DAY_TREE`, a `YYYY-MM` month for `MONTH_FILE`, a stamp for `STAMPED`, and `None` for `FLAT`. A grain that needs a `covers` and is handed `None` raises, naming the ledger and the grain; a `FLAT` ledger handed a `covers` raises the same way.

**Two oracles bind this table.** Coverage: iterating `LedgerName` refuses a member with no row, by name. Exact parity: for every member and a fixed date, `path` and `relpath` return exactly what the old function returned - both spellings - so a transcription error fails rather than ships (row 5).

### 4.3 The settlement structures - `backend/idhazh/ledger/keys.py`

What settles two rows is a separate question from where a file lives, so it is a separate module keyed on `LedgerName`. `keys.py` takes, verbatim, every name that answers it:

- The 15 `*_KEY` tuples (`FEED_HEALTH_KEY` through `DAY_VALIDATION_KEY`), the `Preference` type alias, the three `_*_rule` functions and their `*_RULE` aliases, `_PREFERENCES`, and `preference_for`.
- The tree-shape table `_TREE_SHAPES` and `_TreeShape`, plus `segment_contract`, `segment_key`, `segment_carried`, and the `ITEM_HEALTH_CARRIED` / `SCORES_CARRIED` frozensets they read.
- `DAY_TREES` is imported here from `contracts/ledger_name.py`; `_TREE_SHAPES` is re-keyed from `SegmentLedger` onto `LedgerName` and its keys must equal `DAY_TREES` (the coverage oracle). `segment_contract` / `segment_key` / `segment_carried` and the `write_segment` family (in `rows.py`) raise the named refusal of section 4.1 for a `LedgerName` not in `DAY_TREES`.

### 4.4 The remaining modules - which name goes where

Each module takes the names below verbatim. **The oracle for every one is the same**: `pytest --collect-only -q` is byte-identical before and after, the moved-name set is recomputed from the two files rather than hand-listed, and every moved module-level constant is asserted value-identical (a moved regex or tuple that changed is what `collect-only` cannot see - Fowler).

| Module | Answers | Takes |
| --- | --- | --- |
| `ledger/filenames.py` | what one writer's file is called | `SegmentName`, `SEGMENT_NAME`, `SEGMENT_SUFFIX`, `BEFORE_PARTITION_NAME`, `PRE_IDENTITY_TRACE`, `REPAIR_NAME`, `REPAIR_STAMP`, `repair_name`, `is_repair`, `segment_name`, `parse_segment_name`, `day_shard_path`, `day_shard_relpath` |
| `ledger/csv_file.py` | how a CSV is read and written | `CsvRecord`, `CsvContract`, `read_header`, `require_matching_header`, `_csv_line`, `render_file`, `_read_rows`, `_stream_rows`, `extend_ledger_file` |
| `ledger/headers.py` | how a file under an older header is read | `refiler`, `_headings`, `_unplaceable`, `_refile`, `migrate_header` |
| `ledger/rows.py` | how a caller puts rows in and gets them back | every `append_*` / `load_*` / `recorded_*` verb, `write_telemetry_aggregate`, plus `write_segment`, `extend_segment` and `_dated_rows` **verbatim** (Hard scope - out; plan 50 stands on them) |
| `ledger/settle.py` | which rows repeat a key, and what dropping them costs | `KeyedLedger`, `keyed_paths`, `drop_repeated_rows`, `repeated_keys` |

### 4.5 `ledger/__init__.py` - the facade, and what keeps it honest

The 108 call sites do not change: `ledger.append_seen(...)` reads better than `rows.append_seen(...)`. The split is for the maintainer, not the caller.

- `__init__.py` holds imports and `__all__` and **no definition of any kind**. An AST walk asserts zero top-level `FunctionDef` and zero top-level `ClassDef` (row 6). This is the property that keeps a facade from silently growing a body.
- `__all__` is grouped by the module each name comes from, one comment per group, so the file reads as an index. `mypy` runs with `no_implicit_reexport`, so `__all__` is load-bearing.
- **The facade never eagerly re-exports the pyarrow module.** When plan 50 lands `parquet.py`, it is lazy-loaded or left off `__all__`, so `from idhazh import ledger` - done by 108 files that mostly never touch parquet - does not pull pyarrow. Row 6 writes this into the facade contract now, while the facade is being defined (Carmack).

### 4.6 Three things leave the package and do not come back

Each has one destination, decided here so a worker never invents one:

| What | Why it is not a ledger question | Destination |
| --- | --- | --- |
| `feed_reliability`, `reliability`, `_run_n` | Arithmetic that reads a ledger to answer "how reliable is this feed" - a question about feeds, not about `state/`. Boundary hygiene, not a perf change (Carmack) | `backend/idhazh/telemetry/source_health.py` |
| `shards_in_window` | Its own docstring says no ledger is read with it any more; it returns month stems for a knob comparison | `backend/idhazh/month_partition.py` |
| `HEALTH_WINDOW_DAYS` | A hardcoded tunable among siblings that read config | Stays. Out of scope, its own pull request (Guardrail #6) |

## 5. The naming collisions this plan settles

| # | Collision | Settled as |
| --- | --- | --- |
| 1 | `ledger/paths.py` beside the existing `backend/idhazh/paths.py` | The top-level one becomes `path_classes.py` (row 4). It answers "how does git settle two runs on one path", which is not a path question, and its own test is already `test_path_classes.py` |
| 2 | `ledger` in `docs/concepts/partitions.md` does not all mean `ledger` | That page lists `frontend/public/digest/<YYYY>/<MM>/<DD>/`, which nothing reads as a later run's memory. **Under `state/` it is a ledger; under `frontend/public/` it is a collection.** The test is the reader, never the shape on disk |
| 3 | The glossary rows for `ledger` and `segment` both link to `backend/idhazh/ledger.py` | Repointed in row 2 to `ledger/__init__.py` and `ledger/filenames.py`. The glossary's rule is that the link is the definition, so a broken link is a broken definition |

---

## Row #1 - The retired word `store` leaves

**This row is the one place in the repository allowed to spell the retired word, because it is the row that removes it.** The ratchet in the oracle allow-lists exactly this section and nothing else. Everywhere the old spelling is needed it sits inside a fenced block, so a later sweep cannot quietly flatten the instructions into `X -> X`.

- **Scope:** 1,602 occurrences across 229 files. No file moves and no identifier outside the block below changes.
- **The rule, applied per occurrence:** under `state/` it becomes **ledger**; under `frontend/public/` it becomes **collection**; where the word is the ordinary English verb it is **left alone**.

```text
LEFT ALONE - the ordinary English verb, not the vocabulary
  restore  restores  restored  restoreAnchor  storedChoice  storedDates
  store_true  store_false
  test_the_row_stores_counts_and_leaves_every_rate_to_be_derived
  test_the_manifest_stores_the_publisher_map_it_froze

IDENTIFIERS THAT CHANGE
  STORE_DIRNAMES            -> LEDGER_DIRNAMES   (row 3 then deletes it outright;
                                                  renamed here so row 3 has one
                                                  thing to delete, not two)
  WRITER_OWNED_STORES       -> WRITER_OWNED_LEDGERS
  STORES_NO_JOB_WRITES      -> LEDGERS_NO_JOB_WRITES
  STORES_NOTHING_FILLS_YET  -> LEDGERS_NOTHING_FILLS_YET
  STORES_NO_RUN_FILLS       -> LEDGERS_NO_RUN_FILLS
  COUNCIL_STORE             -> COUNCIL_LEDGER
  RETIRED_STORE_SWEEP       -> RETIRED_LEDGER_SWEEP
  RETIRED_STORE_PATH        -> RETIRED_LEDGER_PATH

FILES THAT RENAME
  backend/utilities/check_seeded_stores.py -> check_seeded_ledgers.py
      class Store        -> class Ledger
      seeded_stores()    -> seeded_ledgers()
  backend/tests/test_check_seeded_stores.py -> test_check_seeded_ledgers.py

SIGNATURES AND MEMBERS THAT CHANGE
  backend/utilities/empty_column_census.py
      class Store(NamedTuple) -> class Ledger(NamedTuple)
      STORES                  -> LEDGERS
      census(root, store)     -> census(root, ledger)
  backend/idhazh/telemetry/prune.py
      day_collection(state_root, store: str) -> (state_root, ledger: str)
      as_outcome(store: str, ...)            -> as_outcome(ledger: str, ...)

ABOUT THIRTY TEST FUNCTION NAMES carrying the word, listed by the sweep
```

- **Files touched:** the 229 measured, plus `.github/` where the renamed utility is called, plus [docs/concepts/glossary.md](../docs/concepts/glossary.md) (already done, 2026-09-26) and the four plan-docs under `TODO/` (**done 2026-09-26: 313 of the 1,602 were the plans' own prose**).
- **Acceptance gates:** `ruff check .`, `mypy backend`, the full `pytest backend/tests`, and the frontend selector. **A test function rename is zero-risk** - pytest discovers by prefix - so the suite is the check that nothing else moved.
- **Oracle:** a ratchet test. The retired word appears **zero** times outside this row and a third-party quotation, counted with `(?<![A-Za-z0-9_])[Ss]tores?(?![A-Za-z0-9_])` over `backend/`, `frontend/src/`, `frontend/tests/`, `config/`, `docs/`, `TODO/` and `.github/`. **Without the ratchet the word walks back in** - it was already swept out of the plans once and would return with the next draft.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `ledger` rather than `dataset`, `collection` or a new word. Measured: `ledger` 3,067 uses with a glossary definition against `store` 931 with none. **Deleting a duplicate is cheaper than minting a fourth name** | Owner, 2026-09-26 |
  | 2 | The ratchet is a test and not a review habit. A review habit is what let three words coexist | Fowler |
  | 3 | This row ships before the package move, so row 2's rename carries no identifier changes - only the file move and its docstring | Fowler, Tidy First |

---

## Row #2 - `ledger.py` becomes the package, and its docstring becomes a page

- **Scope:** `git mv ledger.py -> ledger/__init__.py`, add `__all__`, move the 90-line state-layout docstring to a docs page, fix four string literals, repoint two glossary rows.
- **Files touched:**
  - `backend/idhazh/ledger.py` -> `backend/idhazh/ledger/__init__.py`
  - `backend/tests/pipeline/test_day_shards.py` lines 274 and 340, `backend/tests/workflows/test_ledger_staging.py` lines 766 and 773 - the four literals naming the old path
  - `docs/concepts/glossary.md` - the `ledger` and `segment` rows repoint to `ledger/__init__.py` and `ledger/filenames.py`
  - `docs/architecture/contracts/` - the new page carrying the module docstring
- **Acceptance gates:** `ruff check .`, `mypy backend`, the changed-file selector locally; full `pytest backend/tests` on CI.
- **Oracle:** `pytest --collect-only -q` is byte-identical before and after, AND `git` reports the move as a rename (the docstring is about 4% of the file, well inside the rename threshold), AND an import-graph assertion - no `ledger/*` submodule imports the package, and `contracts/` imports nothing from `ledger`. Collect-only cannot see an order-dependent import cycle, which packaging can introduce (Fowler).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Zero call sites change. `from idhazh import ledger` resolves identically against `ledger/__init__.py` | Fowler, Branch by Abstraction: the facade is the stable seam while modules move underneath it |
  | 2 | **The 90-line docstring moves in this same row, not a later one.** It is the best explanation the project has of its own state directory - why `state/published` files by day, what a read costs on real hardware, why `visual-prunes` is the declared partition exception. It belongs in `docs/architecture/contracts/` (Guardrail #4), and folding it into the git-mv keeps the plan at minimal pull requests without breaking the rename signal. Row 2 is not done until the page exists | Owner, reconciling Fowler (keep the move clean) with the minimal-PR goal |
  | 3 | `__all__` is grouped by the module each name will end up in, one comment per group, so `__init__.py` reads as an index | Fowler |

---

## Row #3 - One `LedgerName` for one ledger

- **Scope:** mint `LedgerName` and `DAY_TREES` in `contracts/`, collapse `SegmentLedger` into them across 36 files, and re-type the segment functions on `LedgerName` with the named refusal. The 25 `*_DIRNAME` constants stay - their users are the path functions, which do not move until row 5. **This row unblocks plan 50.**
- **Files touched:**
  - `backend/idhazh/contracts/ledger_name.py` (new), `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/ledger/__init__.py` - re-type `write_segment`, `extend_segment`, `segment_contract`, `segment_key`, `segment_carried`, `segment_name`, `day_shard_path`, `_dated_rows` on `LedgerName`; re-key `_TREE_SHAPES`; add the `DAY_TREES` refusal; delete `SegmentLedger`
  - the 11 production readers (`evals/writer.py`, `stages/{assemble,compact,decide,plan,qualify_decide,record,validate_days,work}.py`, `telemetry/{prune,silicon}.py`), the 3 utilities (`build_canary_day.py`, `pipeline_test_ledgers.py`, `widen_ledger_header.py`), and the ~22 test files that name `SegmentLedger` - each `ledger.SegmentLedger.X` becomes `LedgerName.X`, each `for x in SegmentLedger` becomes `for x in DAY_TREES`, and `WRITER_OWNED_LEDGERS` reads `DAY_TREES`
- **Acceptance gates:** `ruff check .`, `mypy backend`, the changed-file selector locally; full `pytest backend/tests` on CI.
- **Oracle:** `{m.value for m in DAY_TREES}` equals the old `SegmentLedger` value set, computed from git; `_TREE_SHAPES.keys()` equals `DAY_TREES` (coverage); `write_segment` with a `LedgerName` not in `DAY_TREES` raises, naming the ledger and the grain. **mypy is the completeness oracle for the rewire** - a deleted `SegmentLedger` with a live reader is a type error, not a silent default. Wide and shallow: 36 files, one mechanical substitution each.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One type and a typed subset, not two types. `SegmentLedger` is deleted, not aliased; `DAY_TREES` is the nine it named | Fowler |
  | 2 | The widened segment functions gain a **named runtime refusal** for a non-day-tree member - the right trade for a build-time producer, paired with the `DAY_TREES` coverage test | Fowler |
  | 3 | `LedgerName` lives in `contracts/` because `FileEnvelope` (plan 50) is typed by it and CLAUDE.md section 4 forbids `contracts/` importing another subpackage | CLAUDE.md section 4 |
  | 4 | The 25 `*_DIRNAME` constants are NOT deleted here - their users, the 42 path functions, are still in `__init__.py` until row 5. Row 5 deletes them once the path table replaces their users | Fowler, dependency order |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | Mint `LedgerName` only, defer the `SegmentLedger` collapse | Leaves two enums naming the day-trees for several rows - the "two spellings live" state this plan ends | One extra pull request and a longer window of duplicate vocabulary | Fowler |
  | 2 | Keep `SegmentLedger` as a `LedgerName` subset alias | An alias whose members duplicate a subset is a second spelling by another name | Nothing saved; the defect persists under a new keyword | Fowler |

---

## Row #4 - `paths.py` becomes `path_classes.py`

- **Scope:** rename `backend/idhazh/paths.py` to `path_classes.py` and update its importers. The one code row disjoint from the extraction chain.
- **Files touched:**
  - `backend/idhazh/paths.py` -> `backend/idhazh/path_classes.py`
  - `backend/idhazh/cli.py` (the `refresh_paths` call site)
  - `backend/tests/contracts/test_derived_paths.py`, `backend/tests/contracts/test_path_classes.py`, and the other test files that `from idhazh import paths` (`retention/test_union_safe_repeats.py`, `workflows/_harness.py`, `workflows/test_daily_commit_steps.py`, `workflows/test_staged_paths.py`, `workflows/test_worker_ledgers.py`)
- **Acceptance gates:** `ruff check .`, `mypy backend`, the changed-file selector locally; full `pytest backend/tests` on CI.
- **Oracle:** `pytest --collect-only -q` byte-identical; mypy names any importer left on the old name. `ledger.py` is untouched - it never imports `idhazh.paths`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | It answers "how does git settle two runs on one path", which is not a path-building question; `path_classes` is the name its own test already carries | Fowler |
  | 2 | Depends on row 2 only, but the pool holds it while row 3 or row 6 is in flight, because it shares `test_worker_ledgers.py` and `test_daily_commit_steps.py` with them | execute-a-plan.md, file-disjointness |

---

## Row #5 - One `LedgerPath` table replaces 42 path functions

- **Scope:** build `ledger/paths.py` (section 4.2), migrate every call site to `paths.path()` / `paths.relpath()`, delete the 42 wrappers, and delete the 25 now-unused `*_DIRNAME` constants.
- **Files touched:**
  - `backend/idhazh/ledger/paths.py` (new)
  - `backend/idhazh/ledger/__init__.py` - delete the 42 functions and the 25 constants, re-export from `paths.py`, cut `__all__`
  - every caller mypy names when the wrappers go
- **Acceptance gates:** `ruff check .`, `mypy backend`, the changed-file selector locally; full `pytest backend/tests` on CI.
- **Oracle:** **exact parity** - for every `LedgerName` member and a fixed date, the old function and the new builder return equal values, both the `Path` and the `relpath` spelling; a grain that needs a `covers` and gets `None` raises. This is the property this move can break, and the one oracle in the plan that catches it. mypy then proves no caller was left on a deleted name.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Build the table and delete the 42 wrappers in one pull request. Both are structural (one hat); Tidy First separates structural from behavioural, not structural from structural. Staging leaves two spellings live | Fowler |
  | 2 | The table carries `prefix` as a tuple, because `content-similarity-judge/scored-pairs/` and `llm-council/shard-outcomes/` nest | Fowler |
  | 3 | The 25 `*_DIRNAME` constants are deleted here, their only users now gone. `LEDGER_DIRNAMES` is re-derived from `LedgerName`, so `prune-state` keeps working | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | The merged `LedgerShape` table (path shape plus dedup key plus preference in one row) | Re-couples the two concerns rows 5 and 6 separately own, forces `paths.py` to import `keys.py`, and cannot carry `_TREE_SHAPES`'s `model`/`carried` | A god-table and a cross-module import for a type `paths.py` does not need | Fowler |

---

## Row #6 - The rest of the module splits, and the facade becomes provably empty

- **Scope:** extract `keys.py`, `filenames.py`, `csv_file.py`, `headers.py`, `rows.py` and `settle.py` (sections 4.3-4.4); evict `feed_reliability`/`reliability`/`_run_n` to `source_health.py` and `shards_in_window` to `month_partition.py` (section 4.6); make `ledger/__init__.py` imports-and-`__all__` only, with the pyarrow-lazy rule in its contract.
- **Files touched:**
  - `backend/idhazh/ledger/keys.py`, `filenames.py`, `csv_file.py`, `headers.py`, `rows.py`, `settle.py` (all new)
  - `backend/idhazh/ledger/__init__.py` - now imports and `__all__` and no definition
  - `backend/idhazh/telemetry/source_health.py`, `backend/idhazh/month_partition.py` - the evicted names and their readers
  - `docs/concepts/glossary.md` - the `segment` row's link, if row 2 left it on `__init__.py`
- **Acceptance gates:** `ruff check .`, `mypy backend`, the changed-file selector locally; full `pytest backend/tests` on CI. May land as two commits in one pull request - the settlement/naming half, then the read/write half - if the diff reads too large.
- **Oracle:** `pytest --collect-only -q` byte-identical; the moved-name set recomputed from the source and destination files rather than hand-listed; every moved module-level constant asserted value-identical (a moved regex or key tuple that changed is what collect-only cannot see); and an **AST walk on `__init__.py` asserting zero top-level `FunctionDef` and zero top-level `ClassDef`** - where the facade first becomes provably a facade.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `write_segment`, `extend_segment` and `_dated_rows` move to `rows.py` **verbatim** - same signature, same `int` return, same per-`date` routing. Plan 50's frozen `persist` stands on that behaviour (ESCALATE trigger 2) | Owner, CLAUDE.md section 0d |
  | 2 | The facade never eagerly re-exports the future `parquet.py`; the rule goes into the facade contract now, so `from idhazh import ledger` never pulls pyarrow for a CSV path | Carmack |
  | 3 | `feed_reliability` and `shards_in_window` leave because they answer questions about feeds and about knobs, not about `state/`. Boundary hygiene, priced as such and not as a perf change | Fowler, Carmack |

---

## Relationship to plan 50

Plan 50 is frozen from a design point of view; this plan does not change it. What this plan hands it:

- A package `backend/idhazh/ledger/` for `persist.py`, `parquet.py`, `json_lines.py` and `arrow_schema.py` to live in.
- A `LedgerName` enum in `contracts/` to type `FileEnvelope` and `persist`'s first argument.
- `write_segment` and `extend_segment` moved verbatim, so plan 50's `persist` stands on the behaviour it was designed against.

**The minimum that unblocks plan 50 is rows 2 and 3.** Landing all six first is the recommendation: plan 50's persist row edits `ledger/__init__.py`, and an open branch against a file the extraction rows are still moving is a branch that gets redone - measured once on this repository, on `app_config.py`, which collected 54 commits of divergence in a day.

## What this costs

| # | Cost | What softens it |
| --- | --- | --- |
| 1 | **The 90-line module docstring** - the best explanation the project has of its own state directory - has to move without being lost | Row 2 folds it into a `docs/architecture/contracts/` page in the same pull request, and row 2 is not done until the page exists |
| 2 | **Six merge surfaces where there was one.** Two branches that once conflicted visibly in one file can now auto-merge across modules, leaving a tree where a key moved and its path did not | Serial execution on `ledger/__init__.py` (Parallel N = 2), and row 6's value-identity oracle that a moved constant must equal its old self |
| 3 | A reader following `ledger.X` has one extra hop, because the facade hides which module holds it | `__all__` grouped by source module, one comment per group |
| 4 | `__init__.py` becomes the thing that can rot back into a body | The AST shape test in row 6; somebody has to not delete it |
| 5 | Row 3 is 36 files | Each is one mechanical `SegmentLedger` -> `LedgerName` substitution, and mypy names any that was missed |

## See also

- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) - the frozen plan this one unblocks.
- [`../docs/concepts/glossary.md`](../docs/concepts/glossary.md) - where the `store` -> `ledger` / `collection` decision is written down.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan's Status Reckoner stamps.
- [`../CLAUDE.md`](../CLAUDE.md) - section 1a for the one-question rule, section 4 for why `LedgerName` is in `contracts/`, section 6 for the correction level.
