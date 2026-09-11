# 24 - Five ledgers file by day

**Last Updated**: 2026-09-11
**Level**: 5 (a persisted layout every stage writes, the retention path that deletes, and the mirrors a reader fetches)

**Chain**: split out of [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) section 0, which named this work and refused it: thirteen-plus modules, three published mirrors and a shared reader-facing control, and not one line of it about what an article is about.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 2**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

**Eight rows in six groups, and two of the six hold two.** Every row's `Files touched` list names files rather than globs, and section 1 carries the table that proves no two rows in one group write the same one. **Four of the six groups hold one row, and the reason is a file conflict rather than a dependency** - section 1 counts it rather than dressing it up.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Five `state/` ledgers file one calendar month to a file while the pipeline runs, measures and publishes by day. Owner instruction, 2026-09-10: metrics sit per day, not per month, and item-health and everything beside it shard to a day file. Three collections already do it - `state/published/`, `state/day-metrics/`, `state/visual-prunes/` - so this plan copies a layout that is already in the repository rather than inventing one |
| Hard scope - in | `state/item-health/`, `state/feed-health/`, `state/scores/`, `state/seen/` and `state/score-index/` move from `<YYYY-MM>.csv` to `<YYYY>/<MM>/<DD>.csv`; the shared day-tree module; the migration of committed history; every backend reader, every prune, every publisher and every build-time site read that addresses a month stem of those five; the cover rows in [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) |
| Hard scope - out | **The seven published mirrors stay monthly** (section 0.2). **The four unsharded ledgers stay unsharded** - `state/fingerprints.csv`, `state/runtime-counters.csv`, `state/feed-retirements.csv`, `state/day-validations.csv` (section 0.2), and the first of those is deleted by plan 23 row #1b rather than ruled on here. `state/telemetry-aggregate/` and `state/score-archive/` are ruled monthly for the day they exist - **neither directory is on disk today**, because `retention.dry_run` is `true` and nothing has ever folded a month away (verified 2026-09-11). Flipping `retention.dry_run` is a decision about the whole repository and is nobody's row here |
| ESCALATE triggers | 1. **A row cannot write the two-sided prune oracle for its store**, and the only assertion available is that nothing was deleted. That is the silent no-op this plan exists to prevent, and the row stops. 2. A row proposes to change the grain of a directory under `frontend/public/`. Section 0.2 rules them monthly; changing that changes what a browser fetches and what [`../frontend/src/lib/components/WindowControl.svelte`](../frontend/src/lib/components/WindowControl.svelte) prices, and it is the owner's call. 3. **Row #1's measurement shows a windowed read slower at day grain than at month grain by more than its own spread** at the widest committed window. Section 0.3 says why that is the number to watch and why the file count alone is not. 4. A row proposes to shard one of the four unsharded ledgers, or to leave one of the five at month grain. 5. **A row cannot migrate its ledger's committed history and proposes a dual read side instead.** Section 0.4 ruled that out; reversing it buys a permanent shape and is the owner's call. 6. `retention.dry_run` is proposed for a flip |
| Chosen strategy | The shared module and the measurement first, then the migration utility, then one ledger a row - each row moving its own readers, its own prune, its own publisher, its own committed bytes and its own docs in one commit |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

### 0.1 Standing rules, and they bind every row

**Delivering the intent of this plan matters more than delivering the letter of a row. A structural fix matters more than a small diff. Where a row cannot be done correctly inside its stated scope, expand the scope and say so in the pull request - do not ship a band-aid to stay inside a file list.** [`../CLAUDE.md`](../CLAUDE.md) Rule #5 is the authority; this sentence is here because a row's file list reads like a fence and is meant to read like a start.

**No prisoners.** A row that removes something takes its code, its tests, its fixtures, its config keys, its schema fields and its docs with it, **in the same commit**. Git is the backup. A row that retires a month reader and leaves a doc paragraph describing it has not finished, and its acceptance gate says so.

**Verify every fact this plan hands you against the tree before acting on it.** Every number below was re-measured in a worktree cut from `origin/main` on 2026-09-11, and the brief this plan was written from was wrong about four of them - section 11 lists which. **A row that discovers a wrong fact fixes the plan in the same pull request**, in the row that carried it, and says so in the body.

**A widened file list is re-checked against the row's own group before the pull request opens.** Section 1's group table is composed by diffing the rows' `Files touched` lists, so a row that grows one invalidates the diff.

**A row that adds a backend test module classifies it in the same commit.** [`../backend/tests/test_marks.py`](../backend/tests/test_marks.py) fails naming any module that no registered mark selects and that its own exemption set does not name. There is no `unit` mark, so a plain unit-test module goes in the exemption set - and then `test_marks.py` is in the row's file list, because it is a file the row writes.

**No test walks a growing collection** ([`../CLAUDE.md`](../CLAUDE.md) Rule #12, section 13). Every oracle below is driven from a tree the test builds, from `tests/fixtures/`, or from `backend/var/canary/`. A migration is proved on a fixture that carries a case the committed ledgers have never produced; the committed ledgers are then migrated once, by an operator command, and checked by their own read-back.

**The migration is re-run after every merge and every rebase.** `state/*.csv` and `state/**/*.csv` are `merge=union` in [`../.gitattributes`](../.gitattributes). Union merge keeps every line from both sides, which is right for an append and wrong for a file whose every line moved - and it has no conflict state, so `git merge origin/main` over a migrated tree exits 0 and leaves a directory holding both grains. Restore from `origin/main` and re-run the utility; do not resolve by hand. [`../docs/reference/agent-notes/git-and-github.md`](../docs/reference/agent-notes/git-and-github.md) records the 2026-08-27 occurrence.

**A `digest.yml` run in flight rewrites what your row migrated.** The scheduled pipeline appends to `state/` several times a day from a checkout pinned to its start sha, so a run that started before your row merges appends to the **month** shard your row deleted. Check `gh run list --workflow digest.yml --limit 3` before merging and wait it out, then re-run the migration.

**Every number carries its hardware, its date and its spread** ([`../CLAUDE.md`](../CLAUDE.md) Rule #10). Row #1 takes the one measurement this plan is priced against; no other row may quote an unmeasured throughput claim to justify a grain.

### 0.1a The gate sets, written out once so a row can name one

Every row's acceptance gate names one or more of these sets **and then lists what that row adds**. The commands are the literal ones from [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md), copied here on 2026-09-11 so a worker reading one row in an isolated worktree does not have to open another file to know what to type. Where the two disagree, the gate guide wins and the row that noticed fixes this block.

**`GATE-PY`** - every row that changes a `.py` file. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/<the modules this row names>
```

**`GATE-SUITE`** - the whole backend suite, which is what CI runs. Run it locally only when you cannot push:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**`GATE-WEB`** - every row that changes anything under `frontend/src/`. From `frontend/`:

```powershell
npm run check
npm run build
npm run bundle-gate
python -m idhazh site-weight --site-tree build
```

**`GATE-BROWSER`** - every row that changes what a reader or an operator sees. The canary day is the fixture; the real digest is not:

```powershell
.\.venv\Scripts\python.exe backend\utilities\build_canary_day.py
cd frontend
npm run test:logic
npm run build:canary
npm run test:browser
```

**`GATE-DAYS`** - every row that changes a published payload shape:

```powershell
python -m idhazh validate-days --day 2026-08-30 --day 2026-08-31
```

**Not a gate, in this plan or anywhere in this repository: `ruff format`.** It rewrites dozens of files nobody in this plan authored - 73 on one 2026-09-08 run. Format the files you wrote, or leave formatting alone.

### 0.2 The two grains, ruled here so no row re-argues them

**`state/` files by day. `frontend/public/` files by month. They are different questions and this plan answers both.**

A `state/` shard's grain follows **what a run writes and what a removal takes away**. A run writes one day, two runs collide on a file only when they are the same day, and taking a day back is one `rm` rather than an edit inside a shared shard - which `merge=union` cannot express. That is the reason [`../backend/idhazh/ledger.py`](../backend/idhazh/ledger.py) already gives for `state/published/` and `state/visual-prunes/`, and it is the reason the five follow them.

A `frontend/public/` mirror's grain follows **what a browser fetches**. It is rewritten wholesale by its publisher, which compares bytes and writes only what changed, so neither the collision argument nor the removal argument reaches it. What does reach it is the console: `console.window_presets` is `[1, 7, 14, 30, 90]` in [`../config/appearance.json`](../config/appearance.json), and the 90-day preset fetches at most `shardMonths(90)` = 5 files today. At day grain that preset is up to 90 requests, and the control that prices it in month files would be telling an operator a number that is no longer true.

| Collection | Grain after this plan | Why |
| --- | --- | --- |
| `state/item-health/`, `state/feed-health/`, `state/scores/`, `state/seen/`, `state/score-index/` | **day** | a run writes one day and a removal takes one day |
| `state/published/`, `state/day-metrics/`, `state/visual-prunes/` | day, already | the pattern the five copy |
| `state/telemetry-aggregate/`, `state/score-archive/` | month, when they exist | each summarises a month; a day file of a month's totals is a shape nothing consumes. **Neither directory exists on disk today** - `retention.dry_run` is `true`, so nothing has ever folded a month away and nothing has written either of them (verified 2026-09-11). The ruling is for the day they are created |
| `state/fingerprints.csv`, `state/runtime-counters.csv`, `state/feed-retirements.csv`, `state/day-validations.csv` | **one file, unsharded** | see below. **`state/fingerprints.csv` is deleted outright by [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #1b**, so it is three files after that row lands rather than four |
| `frontend/public/telemetry/`, `scores/`, `feed-health/`, `span-rollup/`, `run-days/`, `day-metrics/`, `machine/` | **month** | the grain follows the fetch, and the fetch is a window priced in files |

**The four unsharded ledgers are not "not yet migrated". They are correctly unsharded, and the burden is on a change that shards them.** The rule is already written down in [`../docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md): a ledger partitions only when its read carries a window, because without a window every shard gets opened anyway - the same bytes through more file handles, plus a directory walk a single `open` does not need. None of the four's read carries a window. `feed-retirements.csv` is read whole and a retirement is permanent. **`fingerprints.csv` is not a live ledger and this plan does not rule on it**: plan 23 row #1a stops it being read at all and **plan 23 row #1b deletes the file, its contract and its schema**, so a grain ruling on it would be a ruling on something that will not be there. `runtime-counters.csv` is read for one run, and [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) already records the ruling that one file handle beats N. `day-validations.csv` is a receipt file read once a run.

**The "otherwise migrated twice" argument does not reach them**, and that is the whole of the answer. It applies to a collection that is going to move anyway; none of the four is. What is true of two of them - `runtime-counters.csv` and `day-validations.csv` grow for ever with no prune - is a Rule #12 question about retention, not a question about grain, and section 11 names it rather than smuggling it into a row here.

### 0.3 The numbers this plan is priced against

Measured 2026-09-11 in a worktree cut from `origin/main` at `3c880832`, by reading the committed tree. Counts and byte totals are arithmetic and have no spread; the one figure with a spread is row #1's, and it is the one that has not been taken yet.

| Figure | Value | Read from |
| --- | --- | --- |
| The five ledgers today | **10 files, 19.64 MB** | `state/{item-health,feed-health,scores,seen,score-index}/` |
| `state/` in total today | **60 files, 20.84 MB** | `state/**` |
| Rows, and the days they fall on | item-health 10,423 rows / 18 days; feed-health 12,006 / 19; scores 8,784 / 20; seen 64,315 / 19 | the committed shards |
| Rows whose day falls outside the month shard holding them | **0, in all four** | the same pass |
| `state/score-index/` columns | **`version,observation_digest`** - no date on any row | `state/score-index/2026-09.csv` |
| The five after migration, today | **about 96 files** - 18 + 19 + 20 + 19 for the four, and the index regenerated to match the ledger | derived |
| The five after migration, a year in | **1,825 files and 60 directories** | derived, 5 x 365 |
| CSV header bytes an ledger row | item-health 316, feed-health 144, scores 465, seen 45, score-index 27 | the committed headers |
| **Header duplication, a year** | **355.4 KB at day grain against 11.7 KB at month grain** - a delta of 343.7 KB a year | derived from the line above |
| Published days committed | **19**, 2026-08-23 to 2026-09-10 | `state/published/**` |
| `frontend/public/` in total | 526 files, 39.12 MB, against a 1 GB cap | `frontend/public/**` |
| Console window presets | `[1, 7, 14, 30, 90]`, default 30, max 366 | `config/appearance.json` |
| `retention.dry_run` | **`true`** - every prune in this repository is already a no-op | `config/idhazh.json` |
| Modules that import `ledger` | **38** | `backend/**/*.py` |
| `ledger.py` / `retention.py` / `payload.ts` | 1,094 / 1,152 / 1,026 lines | the files |

**The file count is the wrong thing to be frightened of, and the byte cost says why.** 343.7 KB a year of duplicated headers is 1.7 percent of what the five ledgers already weigh, against a `state/` tree that is not published and a repository whose history is squashed on a schedule. The number worth watching is the other one.

**What a windowed read costs, stated as a trade rather than as a win.** `collect.seen_window_days` is 90, so `ledger.load_seen` opens at most 4 month files today and would open at most 91 day files. It also reads **fewer rows**: 4 month shards can hold up to 120 days of rows where 91 day files hold exactly 90. So the day grain trades **more file handles for fewer bytes**, and which way that lands on a runner is a measurement nobody has taken. **Row #1 takes it, before any ledger moves**, and ESCALATE trigger 3 fires on it.

### 0.4 Committed history is migrated. There is no dual read side.

**Ruled here so no row re-opens it.** Each row rewrites its own ledger's committed months into day files, in the same commit that moves its readers, and deletes the month shards.

Four facts decide it, and all four were checked on 2026-09-11 rather than assumed:

1. **Every row already knows its day.** item-health, feed-health and scores carry a `date` column; seen carries `first_seen_run`, whose first ten characters are the run's digest date - which is the date `ledger.append_seen` files by today. Nothing has to be guessed.
2. **No row crosses a shard boundary.** Over all four ledgers, **0 rows of 95,528** fall on a day outside the month shard holding them. The migration is a pure split, not a re-filing.
3. **The fifth is derived, not migrated.** `state/score-index/` rows are `version,observation_digest` and carry no date at all, so nothing in the file says which day a row belongs to. It is not split - it is **regenerated** from the ledger beside it, which is what `evals.writer.refresh_index` already does for a partition with no index. Row #2 gives that a repair path and row #8 uses it.
4. **The corpus is one pass.** 19.64 MB in ten files.

**A dual read side was the alternative and it is refused.** It buys a permanent shape - a reader that understands two layouts, kept for ever, tested for ever, and re-derived by anybody who later adds a sixth ledger - in exchange for not rewriting 19.64 MB once. Plan 23's row #1a records the same trade being refused from the other side, where the data genuinely could not be rewritten because a published day is frozen. Here it can be, so the permanent shape has nothing to buy.

**What it costs, stated rather than implied.** `git blame` on any row of those ten files stops at the migration commit. The migration commit is large: ten files deleted, about 96 added, 19.64 MB rewritten. And `prune.yml` force-pushes `main` on a schedule ([`../CLAUDE.md`](../CLAUDE.md) section 8), so the old bytes leave history within `finetune.prune_keep_days` whatever this plan does.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | One answer to what a day file is, and what a day window costs | - | A | DONE #609 | p24-r1 | #609 | worker |
| 2 | The score index can be rebuilt from the ledger it indexes | - | A | PENDING | - | - | - |
| 3 | The migration utility, and it refuses to write a tree it cannot read back | 1 | B | PENDING | - | - | - |
| 4 | The telemetry publisher declares the cover it already has | - | B | PENDING | - | - | - |
| 5 | `state/item-health/` files by day | 1, 3, 4 | C | PENDING | - | - | - |
| 6 | `state/feed-health/` files by day | 1, 3 | D | PENDING | - | - | - |
| 7 | `state/seen/` files by day | 1, 3 | E | PENDING | - | - | - |
| 8 | `state/scores/` and `state/score-index/` file by day | 1, 2, 3 | F | PENDING | - | - | - |

**What a parallel group means, stated so a worker can check it.** **Within one group, no two rows may write the same file.** A glob counts as every file it covers, so there are no globs in this plan. Where a row names a directory it says what it creates in it, and nothing else in the plan writes there.

### The file sets, which are what prove it

Derived from the rows' own `Files touched` lists on 2026-09-11. **It is derived rather than authoritative**: a worker checks a group by diffing the two rows' lists in section 2 and onwards, never by trusting this table.

| Group | Rows | What the first row writes | What the second row writes | Where they come closest |
| --- | --- | --- | --- | --- |
| A | 1, 2 | `backend/idhazh/day_partition.py`, `backend/idhazh/ledger.py`, `backend/idhazh/publish_telemetry.py`, `backend/utilities/measure_day_window.py`, `backend/tests/{test_day_partition,test_ledger,test_marks}.py`, `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/publishing/{layout,telemetry-series,console-payloads}.md`, `docs/reference/measurements.md`, `docs/reference/benchmarks/2026-09-11-day-window-read.md`, the three plan-docs that link or name the renamed page | `backend/idhazh/evals/writer.py`, `backend/idhazh/cli.py`, `backend/tests/test_evals.py`, `tests/fixtures/evals/index-rebuild/`, `docs/concepts/evaluation.md` | Both write a module under `backend/idhazh/` and a page under `docs/concepts/`. Different modules, different pages. Row #2 writes `cli.py`; row #1 does not. **Re-checked 2026-09-11 after row #1 widened its list** by `TODO/20260911-execution-order.md` and the benchmark record, and dropped `tests/fixtures/day-partition/`: neither side gains a shared file |
| B | 3, 4 | `backend/utilities/migrate_to_day_shards.py`, `backend/tests/{test_migrate_to_day_shards,test_marks}.py`, `tests/fixtures/day-shard-migration/`, `docs/concepts/partitions.md` | `backend/idhazh/publish_telemetry.py`, `backend/tests/test_publish_telemetry.py`, `docs/concepts/growing-reads.md` | Both write a `backend/tests/` module and a `docs/concepts/` page. Two different modules and two different pages. Row #3 writes no file under `backend/idhazh/` |
| C | 5 | singleton - it writes `ledger.py`, `retention.py`, `payload.ts` and three `docs/` pages that rows #6, #7 and #8 also write | - | - |
| D | 6 | singleton, same four collisions | - | - |
| E | 7 | singleton, same four collisions | - | - |
| F | 8 | singleton, same four collisions | - | - |

**Four singletons, and here the cause is a file conflict rather than a dependency.** Rows #5, #6, #7 and #8 have no ordering constraint between them - each moves a different ledger - and all four write `backend/idhazh/retention.py`, `backend/tests/test_retention.py`, `docs/concepts/growing-reads.md` and `docs/architecture/contracts/schemas.md`. Three of the four also write `backend/idhazh/ledger.py` and `frontend/src/lib/server/payload.ts`. **This plan counts that rather than dressing it up.** Splitting the modules was considered and refused; the rejected-alternatives table under row #1 carries the count that decided it.

**`backend/idhazh/retention.py` is also written by four rows of [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md)** - its rows #14, #16, #17 and #21 each add a prune for a new day-sharded collection. **That is a cross-plan collision and section 1's within-group rule does not catch it.** Rows #5 to #8 here each re-read `retention.py` against the tree before editing it, and name in their pull request which of plan 23's four prunes were already in it. Found 2026-09-11; neither plan named it before.

**This table is the schedule; the numbered sections below are the drafting order and are not.** A worker takes its position from the Depends-on and Parallel-group columns and never from a section number.

---

## 2. Row #1 - One answer to what a day file is, and what a day window costs

- **Scope:** `backend/idhazh/day_partition.py` becomes the peer of `backend/idhazh/month_partition.py`. It owns what a `<YYYY>/<MM>/<DD>.csv` tree is, which names it refuses, and which days a window of `n` days names. `ledger._day_files`, `ledger._refuse_stray` and `ledger._days_in_window` move into it. **No collection changes grain in this row**, and the one measurement this plan is priced against is taken here.
- **A fourth responsibility was in this sentence and was dropped on 2026-09-11**: "which day an age in months keeps". It has no caller until rows #5 to #8, which are four singleton groups, so exactly one of them lands first and writes it with its caller in the same commit. Fowler ruled it belongs beside `month_partition.oldest_month_kept` rather than in `day_partition`, because the boundary stays a month and a month-anchored boundary is not what a day tree is.
- **Files touched:** `backend/idhazh/day_partition.py` (new, created by this row; row #7 later folds `shards_in_window` into it), `backend/idhazh/ledger.py`, `backend/idhazh/publish_telemetry.py`, `backend/tests/test_day_partition.py` (new), `backend/tests/test_ledger.py`, `backend/tests/test_marks.py`, `backend/utilities/measure_day_window.py` (new), `docs/concepts/month-partitions.md` renamed to `docs/concepts/partitions.md`, `docs/reference/benchmarks/2026-09-11-day-window-read.md` (new; this row creates the directory), `docs/architecture/contracts/schemas.md`, `docs/architecture/publishing/layout.md`, `docs/architecture/publishing/telemetry-series.md`, `docs/architecture/publishing/console-payloads.md`, `docs/concepts/growing-reads.md`, `docs/reference/measurements.md`, `TODO/20260906-constant-cost-reads-plan.md`, `TODO/20260907-growing-reads-window-plan.md`, `TODO/20260910-24-day-sharded-ledgers-plan.md`, `TODO/20260911-execution-order.md`
- **`tests/fixtures/day-partition/` was in this list and was dropped on 2026-09-11.** The oracle's tree is built under `tmp_path` from constants in `backend/tests/test_day_partition.py`, which is exactly what the month twin already does - `test_retention.py` builds its trees from `NOT_MONTHS` and `OTHER_STRAYS`, Arabic-Indic stem included. Rule #7 is satisfied by real directories and a real walk, and no non-ASCII filename is committed ([`../CLAUDE.md`](../CLAUDE.md) section 5). Fowler, 2026-09-11.
- **`TODO/20260911-execution-order.md` joined the list on 2026-09-11**, because it names the renamed page twice and carried a wrong link count. `docs/reference/benchmarks/` joined it because [`../docs/reference/measurements.md`](../docs/reference/measurements.md) and [`../docs/reference/documentation-structure.md`](../docs/reference/documentation-structure.md) both refuse a two-arm race as an append to the instrument log; the log carries the figure in force and links to the record.
- **`backend/idhazh/publish_telemetry.py` and this plan's own doc joined the list on 2026-09-11**, because both name the renamed page and the gate below asks for every mention to move. `publish_telemetry.py` is also row #4's file and the two rows sit in different groups, so the pair holds. **Row #4 is in group B and this row in group A**, so whichever lands second re-reads the module.
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_day_partition.py` and `backend/tests/test_ledger.py`, `GATE-SUITE`. Plus, in this row:
  - `backend/tests/test_marks.py` passes, which means the new module is classified;
  - every relative link in the repository that named `month-partitions.md` names `partitions.md` and resolves - **14 links in 7 files, and 39 mentions in 12 files, re-measured 2026-09-11 at `03c130c9`** - and a link whose visible text ends `.md` names the same basename as the file it opens. **An earlier draft said 17 links; it was counting mentions, and the two numbers matter differently**: a link that does not resolve is a broken page, while a mention in a docstring is prose. **The link count held exactly at 14 in 7; the mention count moved from 36 in 11**, because `TODO/20260911-execution-order.md` was written after this plan and names the page twice. **Three of the twelve files are Python** - `backend/idhazh/ledger.py`, `backend/idhazh/publish_telemetry.py` and `backend/tests/test_ledger.py` - and their docstrings are corrected in this row too, because a module pointing a reader at a page that does not exist is the same defect one directory over. **Three of the twelve keep the old name on purpose**, because the sentence is about the rename rather than about the page: this plan, the execution-order doc, and row #10 of the constant-cost-reads plan, which records having created the page under its first name;
  - `docs/reference/measurements.md` carries the day-window reading with its hardware, its date and its spread.
- **Oracle:** **One function decides what a day file is, and a tree it cannot place stops the read rather than being skipped.** **Driven from trees the test builds under `tmp_path`** - one holding `2026/09/07.csv`, then that tree again with each of `2026/13/01.csv`, `2026/09/32.csv`, a day stem in Arabic-Indic digits and a `notes.txt` - and every reader of a `<YYYY>/<MM>/<DD>.csv` tree under `state/` is driven over them, asserting all of them name the same one day and raise on the same four. One tree cannot carry all five, because the walk stops on the first stray it meets and then names no good file at all. **Behaviour rather than identity**, because two names can point at one object and still be called from a third place that reimplemented the check. It is the day-side twin of `test_the_month_readers_all_agree_on_what_a_month_is`, which caught three disagreeing month readers on 2026-09-08 and one file that was left alone in one store and deleted in another.

  **The set is the `state/` day-FILE readers, and that was wrong here until 2026-09-11.** It said "every day-tree reader in the repository". There is one other day walk and it is out of the set by design: `retention._dated_days` reads `frontend/public/digest/`, where a day is a DIRECTORY holding a payload rather than a CSV file, and at its root it skips a name it cannot read instead of refusing it. Driven over these trees it would refuse the good day file too, because `07.csv` is not a day directory. A different shape answering a different question is not a disagreement, and this row does not change it.

  **"Every day-tree reader in the repository" is a moving set, and [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) adds four to it.** Its rows #14, #16, #17 and #21 create `state/classifications/`, `state/vertical-proposals/`, `state/lens-weights/` and `state/counterfactual-scores/`, each `<YYYY>/<MM>/<DD>.csv`, and its section 0.1 puts all four behind this row so they use `day_partition` rather than re-implementing the walk. **This row lands first by that rule; if one of the four has landed anyway, its reader joins the oracle's list in the same commit**, because a reader the oracle does not drive is the disagreeing reader it exists to catch. Found 2026-09-11; neither plan named it before.
- **The measurement, and it is the plan's price.** `backend/utilities/measure_day_window.py` builds a fixture ledger of 120 consecutive days at both grains from the same rows, then reads a 90-day window from each, **alternately in one process** so the page cache cannot favour one arm ([`../docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md), where the same bounded reads came out 16.6 percent apart on identical work). It reports three numbers an arm: files opened, rows read, and wall clock with its spread. The first two are arithmetic and settle it if the third is a wash.
- **What this row does not do:** it moves no data, changes no grain, touches no file under `state/`, and adds no `Cover:` declaration to a read whose cover has not changed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `day_partition.py` is a **peer** of `month_partition.py`, not a replacement. `state/telemetry-aggregate/`, `state/score-archive/` and all seven published mirrors stay monthly, so both modules stay live and each owns one question | Section 0.2 |
| 2 | The page is renamed `docs/concepts/partitions.md`. After this plan **eight collections partition by day and nine by month**, so a page titled for months is the page a reader looking for the day rule does not open - which is the failure `CLAUDE.md` section 5 names. Its opening paragraph already covers both grains, so the title is the only thing that lies | `CLAUDE.md` section 5 |
| 2a | **Two of the seven files holding links are another plan's doc, and one of those is open work.** [`20260907-growing-reads-window-plan.md`](20260907-growing-reads-window-plan.md) carries four of the fourteen links and eleven of the thirty-six mentions, so a worker executing that plan concurrently collides with this row. Read `git worktree list` before staging, and if the other plan has a row in flight this one waits rather than resolving by hand | Section 0.1 |
| 3 | `ledger._day_files` moves rather than being copied. Two collections read day trees today through that one private helper; five more join them, and a private helper imported from seven places is exactly the shape `month_partition` was created on 2026-09-08 to end | `CLAUDE.md` Rule #5 |
| 4 | The measurement is taken **before** any ledger moves, because it is what ESCALATE trigger 3 fires on, and a measurement taken after the fourth row has landed cannot stop anything | `CLAUDE.md` Rule #10 |
| 5 | The four unsharded ledgers are named in `docs/architecture/contracts/schemas.md` as deliberately unsharded, with the reason, so the next reader does not read them as work left undone | Section 0.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Split `backend/idhazh/ledger.py` into a package first, one module a store, so rows #5, #6 and #7 could run together | **38 modules import `ledger`** (measured 2026-09-11), so the split is a 38-file rename before any of this plan's work begins. It also removes only one of the four collisions: rows #5 to #8 would still all write `retention.py`, `test_retention.py`, `growing-reads.md` and `schemas.md`. Plan 23 scheduled its `classify/` split on seven rows against one module and a collision the split fully removed; neither holds here | Fowler; section 1 |
| 2 | Split `backend/idhazh/retention.py` as well | Same arithmetic and the same residue. Two large pure-move rows to unpair four rows that are each about a day of work is a net loss with added risk | Fowler |
| 3 | Keep the page named `month-partitions.md` and extend it | 14 links stay correct and the title stays wrong for eight of seventeen partitioned collections. The link repoint is mechanical and a checker proves it; a title nobody trusts is not repaired by anything | `CLAUDE.md` section 5 |
| 4 | Fold the day rule into `month_partition.py` and rename that module | A module rename is a different change with its own blast radius, and the two rules are genuinely different - a month stem is a filename, a day is a path of three segments with a walk that refuses what it cannot place | Fowler |
| 5 | Skip the measurement and take the file count as the answer | The file count is certain to rise and says nothing about what the read costs. The trade is more handles for fewer bytes (section 0.3), and only a measurement settles which side wins | `CLAUDE.md` Rule #10 |

---

## 3. Row #2 - The score index can be rebuilt from the ledger it indexes

- **Scope:** `evals.writer.refresh_index` gains a repair path: drop the index for a named partition and write it again from the ledger rows beside it. Today it only fills a partition that has **no** index at all, so an index that drifted, or one written at a grain the ledger no longer uses, has no repair and no check.
- **Files touched:** `backend/idhazh/evals/writer.py`, `backend/idhazh/cli.py`, `backend/tests/test_evals.py`, `tests/fixtures/evals/index-rebuild/` (created by this row; nothing else in the plan writes there), `docs/concepts/evaluation.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_evals.py`, `GATE-SUITE`. Plus, in this row: the rebuild is reachable from the CLI as an operator command and is **not** a step of any scheduled stage.
- **Oracle:** **A rebuilt index holds exactly the digests the ledger's rows produce - no more and no fewer.** **Driven from `tests/fixtures/evals/index-rebuild/`**, a two-partition fixture whose committed index holds one digest the ledger cannot produce and is missing one it can. The test rebuilds and then asserts set equality **in both directions** against `{observation_digest(row) for row in the ledger partitions}`. A one-directional assertion passes on an index that only ever grows, and an index that only grows is what a repeated dedupe over a re-scored item looks like.
- **What this row does not do:** it changes no grain, writes no day file and moves no committed byte. It is the mechanism row #8 uses, built and proved a group early so that the thing that changes the index's grain and the thing that checks the index are not the same commit.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The rebuild is an explicit operator command and never a step of the daily run. An index that silently rebuilt itself would hide the drift it exists to reveal, and `recorded_observations` is what stops a measurement being counted twice | Fowler |
| 2 | It reads the ledger partitions and nothing else. `state/score-archive/` is not a source: a digest whose rows were folded away and deleted cannot be re-derived, which is precisely why the archive keeps digests | `docs/concepts/evaluation.md` |
| 3 | Row #8 depends on this rather than carrying it, because `state/score-index/` rows carry no date and so cannot be split. Regeneration is the only path, and it needs a repair that a test can drive | Section 0.4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Delete the index files and let `refresh_index` refill them | That recipe already exists and nothing checks its result, so a partial refill reads as a success and the next dedupe silently admits a measurement the ledger already holds. What is missing is not the refill, it is the assertion | Fowler |
| 2 | Fold the rebuild into row #8 | Then one commit changes the index's grain and writes the check that says the grain change was correct. The check is worth more than the commit it saves | `CLAUDE.md` section 13 |

---

## 4. Row #3 - The migration utility, and it refuses to write a tree it cannot read back

- **Scope:** `backend/utilities/migrate_to_day_shards.py` rewrites one month-sharded ledger directory into `<YYYY>/<MM>/<DD>.csv`, filing each row by a named column. It is idempotent, it refuses to unlink a month shard until the day files it wrote read back as the rows it read, and it names what it did in POSIX relative paths.
- **Files touched:** `backend/utilities/migrate_to_day_shards.py` (new), `backend/tests/test_migrate_to_day_shards.py` (new), `backend/tests/test_marks.py`, `tests/fixtures/day-shard-migration/` (created by this row; nothing else in the plan writes there), `docs/concepts/partitions.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_migrate_to_day_shards.py`, `GATE-SUITE`. Plus, in this row:
  - `backend/tests/test_marks.py` passes;
  - no argparse option in the new module is spelled like a llama-server flag. `test_summarize.test_exactly_one_function_spells_a_llama_server_flag` globs `backend/**/*.py` for the literal `"--port"` and its siblings, so a tool that takes one fails a test about the inference server. Use `--server-port` or a name that is not in that set.
- **Oracle:** **Every row that went in comes out once, in the day file its own date names - and the month shard is still there if it does not.** **Driven from `tests/fixtures/day-shard-migration/`**, a two-month fixture carrying a row on the first day of a month, a row on the last day of a month, a row whose date cell is empty, and a row whose date cell is not a date. The test asserts three things: the multiset of rows read back from the day tree equals the multiset read from the month shards; the two bad rows stopped the run with **both** trees intact and nothing unlinked; and a second run over the migrated tree changes no byte.

  **The refusal is the load-bearing half.** A migration that writes an empty tree and unlinks its source is a delete with exit 0, and the two bad rows are the shape a real ledger eventually holds - a run interrupted mid-append, a header migration half applied. The committed ledgers carry neither case today, which is why the fixture has to.
- **What this row does not do:** it migrates no committed ledger and touches no file under `state/`. Each ledger row runs it on its own directory.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One utility with a `--date-column`, driven per ledger by the row that moves it. Four copies of a split is four places for the read-back refusal to stop being exact, and the refusal is the only thing standing between this plan and a silent delete | `CLAUDE.md` Rule #5 |
| 2 | `state/seen/` files by `first_seen_run[:10]`, **not** by `first_seen_at[:10]`. `ledger.append_seen` files by the run's digest date, so the run id reproduces the writer's own filing exactly; `first_seen_at` is a wall-clock stamp that crosses midnight independently of the run it belongs to | Verified 2026-09-11 against `ledger.append_seen` and the committed rows |
| 3 | It writes into a temporary tree and renames, and it unlinks a month shard only after the day tree it wrote reads back equal. Temp-file-plus-rename is the repository's atomic-unit rule | `CLAUDE.md` section 1a |
| 4 | **`state/score-index/` is not a client of this utility.** Its rows are `version,observation_digest` and carry no date, so nothing in the file says which day a row belongs to. It is regenerated by row #2's rebuild instead | Section 0.4, verified 2026-09-11 |
| 5 | It is a utility under `backend/utilities/` rather than a CLI stage. A one-way rewrite an operator runs once a ledger is not a step the pipeline repeats every four hours | `CLAUDE.md` section 3 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A dual read side that understands both grains, and leave the committed months in place | A permanent shape, kept and tested for ever, bought to avoid rewriting 19.64 MB once. Section 0.4 carries the four facts that make the rewrite cheap. It is also not merely inert: `_day_files` refuses a name it cannot place, so a month shard sitting in a day tree would **stop every read** rather than be ignored | Section 0.4 |
| 2 | Migrate all five ledgers in one commit | Then one row holds four behaviour changes and the readers of four ledgers, and a revert takes all four back. Each ledger's readers, prune, publisher and docs are one reviewable unit | `CLAUDE.md` section 6 |
| 3 | Write the day tree and keep the month shards as a backup | Git is the backup (section 0.1), and a backup inside the directory the reader walks is not a backup | `CLAUDE.md` section 0.1 |

---

## 5. Row #4 - The telemetry publisher declares the cover it already has

- **Scope:** `publish_telemetry.publish` reads **every shard** of `state/item-health/` on the path where its caller names no months, and it appears in no cover table on [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - verified 2026-09-11, the page does not mention the module at all. It declares its cover in its own docstring, takes its line in the inventory, and a test counts the files it opens. Nothing about its behaviour changes.
- **Files touched:** `backend/idhazh/publish_telemetry.py`, `backend/tests/test_publish_telemetry.py`, `docs/concepts/growing-reads.md`
- **Acceptance gates:** `GATE-PY` with `backend/tests/test_publish_telemetry.py`, `GATE-SUITE`. Plus, in this row: the declaration is on the line that declares the read, in the form the six existing `Cover:` declarations use.
- **Oracle:** **The unbounded path is the one with no cover, and a test says which is which by counting the files it opens.** **Driven from a twelve-partition ledger the test builds under `tmp_path`**: publishing with `months` naming one partition opens one file; publishing with `months=None` opens twelve. The second number is the cover this row declares, and the assertion is what stops the read later being described as bounded when it is not. It also survives row #5 unchanged, which is the point - the count is what goes red if row #5's glob stops finding the ledger.
- **What this row does not do:** it changes no grain, adds no bound and alters no output byte. It is a declaration and a count.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The read stays unbounded on the `months=None` path. A cover on it would leave a fresh clone unable to rebuild a mirror it never published, and the daily caller already passes the one month it appended to | `docs/concepts/growing-reads.md` |
| 2 | What bounds it is the **store**, not the read: `observability.item_health_full_grain_months` is 14, so the ledger holds at most fourteen partitions once `retention.dry_run` is `false`. It is `true` today, and the declaration says so rather than implying a bound that is switched off | Section 0.3; `CLAUDE.md` Rule #12 |
| 3 | This lands before row #5 rather than inside it, so the count that proves row #5's publisher still finds its ledger exists before row #5 is written | `CLAUDE.md` section 13 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Bound the read to the newest `LEDGER_WINDOW_MONTHS` partitions | A fresh clone would then never republish an older mirror, and the mirror is what the console fetches. The bound belongs on the store | Decision 2 |
| 2 | Add the inventory line and skip the test | The inventory is examples rather than the rule, and a line in it that nothing checks is a claim. The count is three assertions and it is the thing that catches row #5's non-recursive glob | `CLAUDE.md` Rule #12 design rationale |

---

## 6. Row #5 - `state/item-health/` files by day

- **Scope:** the item-health ledger moves to `state/item-health/<YYYY>/<MM>/<DD>.csv`, its committed history is migrated, and every reader, prune, publisher and build-time site read moves with it. The mirror under `frontend/public/telemetry/` **stays monthly** and its publisher folds a month from that month's day files.
- **Files touched:** `backend/idhazh/ledger.py`, `backend/idhazh/retention.py`, `backend/idhazh/publish_telemetry.py`, `backend/idhazh/publish_source_health.py`, `backend/idhazh/cli.py`, `backend/utilities/measure_ledgers.py`, `backend/utilities/build_canary_day.py`, `backend/utilities/migrate_item_health.py` (deleted), `frontend/src/lib/server/payload.ts`, `frontend/src/lib/server/runtime-counters.ts`, `frontend/scripts/build-canary.mjs`, `backend/tests/{test_ledger,test_retention,test_publish_telemetry,test_telemetry,test_pipeline,test_measure_ledgers,test_console_payloads_producer}.py`, `frontend/tests/item-health-day.spec.ts`, `state/item-health/2026-08.csv` and `state/item-health/2026-09.csv` (deleted) replaced by the day files the utility writes under `state/item-health/2026/08/` and `state/item-health/2026/09/` - **18 files on 2026-09-11, one a day the ledger holds a row for, and no other row in this plan writes in that directory** - `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/sources/item-health.md`, `docs/architecture/publishing/telemetry-series.md`, `docs/architecture/publishing/retention.md`
- **Acceptance gates:** `GATE-PY` with the seven modules above, `GATE-SUITE`, `GATE-WEB`, `GATE-BROWSER`, `GATE-DAYS`, and the [`../CLAUDE.md`](../CLAUDE.md) section 12 smoke on `/console/` and `/console/machine/`. Plus, in this row:
  - **`publish_telemetry.publish` finds the ledger.** Its glob is `source_dir.glob("*.csv")` today, which is non-recursive, so after the move it matches **zero files** and the month filter then compares a day stem against a set of month names. Row #4's counting test is what goes red; this row is what makes it pass again;
  - the migrated tree reads back equal, and the utility's own read-back refusal was exercised on the real ledger rather than only on the fixture;
  - `git diff --stat -- state/item-health` names two deletions and eighteen additions and nothing else.
- **Oracle:** **The pruner deletes a day past the boundary and keeps the day beside it, on a built day tree, with `dry_run` false.** **Driven from a two-day tree the test builds under `tmp_path`** - one day inside `observability.item_health_full_grain_months` and one day outside - and `prune_telemetry` is called with `dry_run=False`, **the argument**, which is what every prune function already takes and defaults to `False`. `retention.dry_run` is `true` in `config/idhazh.json` and is read only by the CLI stage, so it never enters this test and the pruner under test is not switched off.

  **Two-sided, and that is the whole oracle.** It asserts the expired day is gone, the kept day is still there, and the fold was written and read back before the unlink. A one-sided assertion - "nothing failed", or "`deleted` is a tuple" - passes on an empty tree, and an empty tree is exactly what `retention.month_shards` returns after this move: it matches a **seven-character `YYYY-MM` stem**, a day tree has none, so the store silently stops being pruned and nothing fails. That is the failure `month_partition.py` was written on 2026-09-08 to end, arriving from the other direction.
- **What this row does not do:** it does not move `state/telemetry-aggregate/`, which stays monthly because it summarises a month. It does not change the grain of `frontend/public/telemetry/`, and it changes no schema - the row shape does not move, only which file holds it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `frontend/public/telemetry/` stays monthly, so `publish_telemetry.publish` folds a month from that month's day files. Its input is one month, so the fold opens **at most 31 files** and the read stays a store-bounded one | Section 0.2 |
| 2 | `publish_source_health._recent_item_health` uses the **day** names as its index rather than the month names, and opens the newest `keep` days rather than the newest months behind them. That reads strictly fewer rows for the same answer, because a month name only says a month holds records somewhere | Verified 2026-09-11 against the module's own docstring |
| 3 | `retention.month_shards` is not taught to read a day tree. `day_partition` already answers that question, and one function per grain is what row #1 exists to establish | Row #1 decision 1 |
| 4 | `observability.item_health_full_grain_months` keeps its name and its unit. The boundary stays a month; only the files below it are days, and a day compares against the first day of the oldest month kept. **No `config/` key is renamed by this plan**, so no config contract moves and no schema regenerates | Fowler |
| 5 | `backend/utilities/migrate_item_health.py` is deleted in this commit. It migrates **into** the layout this row retires, so leaving it is a tool that walks a ledger backwards | Section 0.1 |
| 6 | `ledger.load_item_health`, `load_settled_failures` and `load_source_counts` keep their covers and their arguments. Only the path each of them names changes; the cover rows in `growing-reads.md` are rewritten in this commit to say days rather than month shards | Section 0.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the ledger monthly and let the day stay a column | It is already a column. The grain is about which file a run writes and which files a removal takes away, and neither question is answered by a column | Section 0.2 |
| 2 | Leave the two committed month shards in the directory beside the day tree | `_day_files` refuses a name it cannot place, so the month shards would stop every read rather than be skipped. Two grains in one directory is not a compatibility layer, it is a broken directory | Row #3 rejected alternative 1 |
| 3 | Move `frontend/public/telemetry/` to day files in the same commit | The console's 90-day preset would fetch up to 90 files where it fetches 5, and `WindowControl.svelte` prices a preset in month files - so the control would print a number that is no longer true. It is also the owner's call, not a row's (ESCALATE trigger 2) | Section 0.2 |
| 4 | Teach `retention.month_shards` to accept both stems | One function answering two questions is how `2025-13.csv` came to be left alone in one store and deleted in another | `docs/concepts/partitions.md` |

---

## 7. Row #6 - `state/feed-health/` files by day

- **Scope:** the feed-health ledger moves to `state/feed-health/<YYYY>/<MM>/<DD>.csv`, its committed history is migrated, and every reader, its prune, its publisher and the site's build-time read move with it. `frontend/public/feed-health/` stays monthly.
- **Files touched:** `backend/idhazh/ledger.py`, `backend/idhazh/retention.py`, `backend/idhazh/publish_feed_health.py`, `backend/idhazh/publish_console.py`, `backend/idhazh/cli.py`, `backend/utilities/measure_ledgers.py`, `backend/utilities/build_canary_day.py`, `backend/utilities/probe_feeds.py`, `backend/utilities/migrate_feed_health.py` (deleted), `frontend/src/lib/server/payload.ts`, `frontend/src/lib/feed-health.ts`, `backend/tests/{test_ledger,test_retention,test_discover,test_pipeline,test_measure_ledgers}.py`, `frontend/tests/console-feeds.spec.ts`, `state/feed-health/2026-08.csv` and `state/feed-health/2026-09.csv` (deleted) replaced by the day files the utility writes under `state/feed-health/2026/08/` and `state/feed-health/2026/09/` - **19 files on 2026-09-11, and no other row in this plan writes in that directory** - `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/sources/health.md`, `docs/architecture/publishing/retention.md`
- **Acceptance gates:** `GATE-PY` with the five modules above, `GATE-SUITE`, `GATE-WEB`, `GATE-BROWSER`, and the section 12 smoke on `/console/`. Plus, in this row:
  - `prune_feed_health` deletes a day past `observability.feed_health_keep_months` and keeps the day beside it, called with `dry_run=False`, on a tree the test builds. Two-sided, for the reason row #5's oracle gives;
  - `state/feed-retirements.csv` is untouched. It is not in this directory and it is never a candidate: one row is one address a server said was gone, and a run that forgot it would start asking a dead address again;
  - `git diff --stat -- state/feed-health` names two deletions and nineteen additions and nothing else.
- **Oracle:** **`ledger.reliability` and `ledger.load_health` return the same answer at day grain as at month grain, over the same rows.** **Driven from a built 40-day fixture** - wider than `ledger.HEALTH_WINDOW_DAYS` (31) so the window has something to exclude - written once at each grain from one row list, then read at both. The test asserts the two reliability maps are equal key for key and value for value, and that the day arm opens the day files the window names and no others.

  **A parity oracle rather than a prune oracle, because this ledger's risk is different.** Its reads feed a quarantine decision and a published console panel; a prune that stops firing costs bytes, and a reliability figure that moved by a shard boundary costs a feed its place in the run. The prune's two-sidedness is an acceptance gate above rather than the oracle, and both are checked.
- **What this row does not do:** it changes no schema and no config key. It does not touch `state/feed-retirements.csv`, and it does not change what `frontend/public/feed-health/` holds.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `frontend/public/feed-health/` stays monthly; `publish_feed_health.publish` folds a month from that month's day files, opening at most 31 | Section 0.2 |
| 2 | `ledger.HEALTH_WINDOW_DAYS` keeps its value of 31. The window was always in days; only the files it names change, and a 31-day window that opened four month shards now opens 32 day files and reads fewer rows | Section 0.3 |
| 3 | `frontend/src/lib/feed-health.ts` carries a docstring saying the console hands it `feedResults(shardMonths(widest))`. That sentence becomes false in this commit and is rewritten in it, because the console's build-time read moves to days while its fetch stays monthly | Section 0.1 |
| 4 | `backend/utilities/migrate_feed_health.py` is deleted in this commit, for the reason row #5 deletes its sibling | Section 0.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave feed-health monthly because its window is only 31 days | A 31-day window over month shards opens up to two shards holding up to 62 days of rows. The grain is about what a run writes and what a removal takes, not about how wide the window is | Section 0.2 |
| 2 | Take the parity oracle over the committed ledger instead of a fixture | The committed ledger holds 19 days and grows every four hours, so the test would cost more each run for an answer it already had, and it could never carry the 40-day case the window needs to exclude anything | `CLAUDE.md` Rule #12 |

---

## 8. Row #7 - `state/seen/` files by day

- **Scope:** the seen ledger moves to `state/seen/<YYYY>/<MM>/<DD>.csv`, its committed history is migrated, and `ledger.load_seen`, `ledger.append_seen` and `retention.prune_seen` move with it. `ledger.shards_in_window` and `ledger._days_in_window` compute the same set at this grain and become one function in `day_partition` - **verify that against the tree before acting on it**; both were in `ledger.py` on 2026-09-11 and `shards_in_window` was also read by `retention.py`.
- **Files touched:** `backend/idhazh/ledger.py`, `backend/idhazh/day_partition.py`, `backend/idhazh/retention.py`, `backend/idhazh/cli.py`, `backend/utilities/measure_ledgers.py`, `backend/tests/{test_ledger,test_retention,test_discover,test_pipeline}.py`, `state/seen/2026-08.csv` and `state/seen/2026-09.csv` (deleted) replaced by the day files the utility writes under `state/seen/2026/08/` and `state/seen/2026/09/` - **19 files on 2026-09-11, and no other row in this plan writes in that directory** - `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/sources/freshness.md`, `docs/architecture/publishing/retention.md`
- **Acceptance gates:** `GATE-PY` with the four modules above, `GATE-SUITE`. **No `GATE-WEB` and no `GATE-BROWSER`: nothing under `frontend/src/` reads `state/seen/`** - verified 2026-09-11, the site's build-time reads name `feed-health`, `item-health`, `scores` and `span-rollup` and no other state directory. Plus, in this row:
  - the migration files by `first_seen_run[:10]` (row #3 decision 2), and the read-back proves it against the 64,315 committed rows;
  - `git diff --stat -- state/seen` names two deletions and nineteen additions and nothing else.
- **Oracle:** **The set of files the pruner keeps is a superset of the set the reader opens, for a date in the past as well as for today.** **Driven from a built 120-day tree** with the anchor set to a date 40 days before its newest file. `prune_seen(dry_run=False)` runs, then `load_seen` runs at the same anchor, and the test asserts every file `load_seen` would open still exists and that at least one file below the window was deleted.

  **This is the invariant the module's own docstring states, and it is the one a grain change breaks.** `prune_seen` derives its keep-set from the reader's own helper precisely so the two cannot drift; when that helper stops returning month stems and starts returning days, a boundary computed the old way deletes the live file. The past-dated anchor is not decoration - `--date` takes whatever it is given, and deleting everything outside a window rather than everything below it is what would eat the shard the next run appends to.
- **What this row does not do:** it touches no publisher, no `frontend/` file and no schema. `state/seen/` has no published mirror.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `collect.seen_window_days` keeps its value of 90 and its unit. At day grain that window opens **at most 91 files against at most 4 today**, and reads **exactly 90 days of rows rather than up to 120** - more handles, fewer bytes. Row #1's measurement is what says which side wins, and ESCALATE trigger 3 fires on it | Section 0.3 |
| 2 | The two window helpers become one. Two functions computing the same set is how a pruner and a reader drift, and drift here deletes a file the next plan wanted | `CLAUDE.md` Rule #5 |
| 3 | `prune_seen` keeps its no-fuse posture. There is no `max_deletes_per_run` here and there should not be: the worst case is that the pipeline re-learns a first-sight date it had already forgotten, which is not the picture pruner's worst case | `backend/idhazh/retention.py` |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave seen monthly because it is the read that gains the most file handles | It is also the read that drops the most rows, and the trade is unmeasured either way until row #1 measures it. Leaving one of five at month grain also means the repository keeps two answers to the same question, which is the thing the owner's instruction closes | Section 0.2 |
| 2 | Narrow `collect.seen_window_days` at the same time to blunt the handle count | Two changes in one commit, and the second one changes what the pipeline remembers. A window is a product decision about re-planning an address, not a lever to make a layout look cheaper | `CLAUDE.md` Rule #10 |

---

## 9. Row #8 - `state/scores/` and `state/score-index/` file by day

- **Scope:** the eval ledger moves to `state/scores/<YYYY>/<MM>/<DD>.csv` and its index moves with it, because the index is derived from it and carries no date of its own. The ledger's committed history is migrated; the index's is **regenerated** through row #2's rebuild. `frontend/public/scores/` stays monthly and `state/score-archive/` stays monthly.
- **Files touched:** `backend/idhazh/evals/writer.py`, `backend/idhazh/evals/archive.py`, `backend/idhazh/retention.py`, `backend/idhazh/publish_scores.py`, `backend/idhazh/cli.py`, `backend/utilities/measure_ledgers.py`, `backend/utilities/build_canary_day.py`, `backend/utilities/reband_scores.py`, `backend/utilities/label_queue.py`, `backend/utilities/migrate_score_ledger.py` (deleted), `frontend/src/lib/server/payload.ts`, `backend/tests/{test_evals,test_retention,test_labels,test_reband_scores,test_measure_ledgers,test_pipeline}.py`, `frontend/tests/console.spec.ts`, `state/scores/2026-08.csv` and `state/scores/2026-09.csv` (deleted) replaced by the day files the utility writes under `state/scores/2026/08/` and `state/scores/2026/09/` - **20 files on 2026-09-11** - and `state/score-index/2026-08.csv` and `state/score-index/2026-09.csv` (deleted) replaced by the day files the rebuild writes under `state/score-index/2026/08/` and `state/score-index/2026/09/` - **20 files, one beside each ledger day; no other row in this plan writes in either directory** - `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/concepts/evaluation.md`, `docs/architecture/contracts/schemas.md`, `docs/architecture/publishing/retention.md`
- **Acceptance gates:** `GATE-PY` with the six modules above, `GATE-SUITE`, `GATE-WEB`, `GATE-BROWSER`, and the section 12 smoke on `/console/` and `/evals/`. Plus, in this row:
  - `prune_scores` archives a day past `observability.scores_full_grain_months` and deletes it, keeps the day beside it, and the archive read back before the unlink - called with `dry_run=False`, two-sided, on a tree the test builds;
  - **the growing read `recorded_observations` creates is declared with its new count.** It opens one file a partition, and this row turns "one a month for ever" into "one a day for ever". The declaration names the store bound that answers it - `observability.scores_full_grain_months` is 14, so once `retention.dry_run` is `false` the live index holds at most fourteen months of days and everything older is one `score-archive` document a month. It also says plainly that `dry_run` is `true` today, so nothing prunes and the count grows until it is flipped;
  - `git diff --stat -- state/scores state/score-index` names four deletions and forty additions and nothing else.
- **Oracle:** **`recorded_observations` returns the identical set of digests before and after the grain change, and the rebuilt index is exactly what the ledger's rows produce.** **Driven from a two-month fixture the test builds**, written once at each grain from one row list, with one observation deliberately re-taken under a different scorer version so the set is not merely a row count. The test asserts set equality across the grains and, separately, that the day-grain index equals `{observation_digest(row) for row in the day tree}` in both directions.

  **This is the assertion the whole ledger rests on.** `recorded_observations` is what stops one measurement being counted twice; a grain change that dropped digests would turn a count over the ledger into a count of times the pipeline looked, which is the one thing the ledger promises it is not - and it would do it silently, because a shorter set reads as a fresh clone.
- **What this row does not do:** it does not move `state/score-archive/`, which stays monthly because it summarises a month, and it does not change the grain of `frontend/public/scores/`. It changes no schema; `EvalRow` and `ObservationIndexRow` keep their shapes.
- **This row and [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) row #1b both rewrite `state/scores/2026-08.csv` and `state/scores/2026-09.csv`, and `state/**/*.csv` is `merge=union`.** That row drops the `pipeline_fingerprint` column from the ledger and its published mirror; this row splits the same files into day shards. Union merge keeps every line from both sides, so the two cannot be resolved by rebasing one onto the other and neither produces a conflict a person would see. **Whichever lands first wins and the second re-runs against the tree**: if this row lands first, plan 23 row #1b rewrites about twenty day files under `state/scores/2026/08/` and `state/scores/2026/09/` instead of two month shards; if that row lands first, this row migrates a ledger one column narrower and the read-back compares the narrower header. Check `git log origin/main -- state/scores` before starting. Found 2026-09-11; neither plan named it before.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The ledger and its index move in **one row**, because the index is derived from the ledger and carries no date. Split across two rows, one of them would have to read across grains | Section 0.4 |
| 2 | The index is **regenerated, never split**. Row #2 built the repair path a group earlier so that the change and its check are not one commit | Row #2 decision 3 |
| 3 | `prune_scores` archives a **month** of day files into one `state/score-archive/<YYYY-MM>.json`. Its input is one month, so it opens at most 31 files, and the archive keeps the boundary of the thing it replaces | Section 0.2 |
| 4 | `frontend/public/scores/` stays monthly; `publish_scores.publish` folds a month from that month's day files | Section 0.2 |
| 5 | **The growing read gets worse and this row says so rather than hiding it.** `indexed_observations` opens every index partition, so this row turns 2 opens into about 20, and about 365 a year. It is declared under Rule #12's escape hatch with the count named and the store bound that answers it, because the alternative - a bounded index - is a dedupe that would let a January measurement come back in February | `CLAUDE.md` Rule #12; `docs/concepts/growing-reads.md` |
| 6 | `backend/utilities/migrate_score_ledger.py` is deleted in this commit, for the reason rows #5 and #6 delete their siblings | Section 0.1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep `state/score-index/` monthly beside a day-grained ledger | `refresh_index` fills a partition with no index from the ledger rows beside it, so the two would have to agree on what a partition is. Two grains in one relationship is a mapping somebody maintains, and this repository already deleted three disagreeing month readers for less | `docs/concepts/partitions.md` |
| 2 | Bound `recorded_observations` to a window to blunt decision 5 | Then a measurement re-taken outside the window reads as new, and the ledger's count becomes a count of times the pipeline looked. That is the exact defect the unbounded read exists to prevent, and its own docstring says so | `backend/idhazh/evals/writer.py` |
| 3 | Fold the index into the archive and delete it | The archive holds a **month past the full-grain window**; the index holds the live months. Deleting the index means the dedupe reads every score row instead of a 76-byte digest - 819.6 bytes an observation against 76, measured before the index existed | `docs/concepts/evaluation.md` |
| 4 | Migrate the index by pairing its rows against the ledger's | Every row is a digest of four ledger cells, so the pairing is a recomputation dressed as a migration - and a recomputation is what the rebuild already is, with a test | Section 0.4 |

---

## 10. The docs this plan writes

| Page | Exists | Rows | What changes |
| --- | --- | --- | --- |
| `docs/concepts/partitions.md` | as `docs/concepts/month-partitions.md`, 14 links in 7 files and 39 mentions in 12 | 1 renames; 3, 5, 6, 7, 8 extend | The day rule beside the month rule, the per-collection table re-derived a row at a time, and the section on changing a collection's grain |
| `docs/architecture/contracts/schemas.md` | yes | 1, 5, 6, 7, 8 | The shard-rule table: which grain each collection has and why, and the four unsharded ledgers named as deliberately unsharded |
| `docs/concepts/growing-reads.md` | yes | 1, 4, 5, 6, 7, 8 | **The four cover rows that say `LEDGER_WINDOW_MONTHS`, which is `shardMonths(90)` and so 5** - a cover of 5 months is not a cover of 5 days - the backend rows that say "month shards of", and `publish_telemetry.publish`, which the page does not mention at all today |
| `docs/architecture/publishing/retention.md` | yes | 5, 6, 7, 8 | What each prune deletes, at the new grain, and the boundary arithmetic that is still counted in months |
| `docs/architecture/sources/item-health.md` | yes | 5 | The ledger's layout and the mirror's, which are now different and say why |
| `docs/architecture/sources/health.md` | yes | 6 | The same, for feed-health |
| `docs/architecture/sources/freshness.md` | yes | 7 | The seen window at day grain |
| `docs/concepts/evaluation.md` | yes | 2, 8 | The index rebuild, and the index at day grain with the growing read declared |
| `docs/architecture/publishing/telemetry-series.md` | yes | 1, 5 | Where the series comes from now that the state grain and the published grain differ |
| `docs/architecture/publishing/{layout,console-payloads}.md` | yes | 1 | The renamed page, repointed |
| `docs/reference/measurements.md` | yes | 1 | The day-window reading with its hardware, its date and its spread |

**No page is created by this plan and no page is deleted.** One is renamed. Every other change extends or corrects a page that already owns the question.

---

## 11. Facts the repository contradicted, and gaps nobody owns

**Four claims this plan was briefed with were wrong on the tree**, re-measured 2026-09-11 in a worktree cut from `origin/main` at `3c880832`. They are recorded here because the standing rule says a row that finds a wrong fact fixes it where it was carried.

| # | The claim | What the tree says |
| --- | --- | --- |
| 1 | Three published mirrors are month-sharded | **Seven** are: `telemetry`, `scores`, `feed-health`, `span-rollup`, `run-days`, `day-metrics`, `machine`. Three of the seven mirror one of the five ledgers; the other four mirror something else and none of them changes grain |
| 2 | Two utilities address month shards | **Four** do: `measure_ledgers.py`, `migrate_item_health.py`, `migrate_feed_health.py`, `migrate_score_ledger.py`, plus `build_canary_day.py`, `reband_scores.py`, `label_queue.py` and `probe_feeds.py`, which write or read one of the five |
| 3 | `frontend/src/lib/components/WindowControl.svelte` would tell the operator a number that is no longer true | Only if the published mirrors moved. Section 0.2 keeps them monthly, so `monthsFor` stays correct and the control is **not** in any row's file list. The claim was right about the hazard and it is what the ruling is for |
| 4 | Five modules is the real backend count, against thirteen | **Twenty backend modules** build or match a month shard path (`ledger`, `retention`, `month_partition`, `cli`, `drift`, `telemetry`, `publish_console`, `publish_console_band`, `publish_day_metrics`, `publish_feed_health`, `publish_machine`, `publish_span_rollup`, `publish_telemetry`, `publish_source_health`, `evals/writer`, `evals/archive`, four contracts and one utility), and **34 test modules** name one of the five ledgers or a shard helper |

| Gap | What it is | Why it is not a row here |
| --- | --- | --- |
| `state/runtime-counters.csv` and `state/day-validations.csv` grow for ever | Neither has a prune and neither is sharded. `runtime-counters.csv` is 48,276 B and `day-validations.csv` 5,156 B on 2026-09-11, both rising every run | It is a retention question, not a grain question. Sharding them would make their reads worse (section 0.2), so the fix is a prune and nobody owns one |
| `retention.dry_run` is `true` | Every prune in this repository is a no-op, including all four this plan moves. The stores are therefore unbounded in fact whatever their configured `keep_months` says | Flipping it is a decision about the whole repository, not about this plan. Plan 23 section 26 names it too |
| `state/validation-2026-08-22.csv` | A loose model-qualification record at the root of `state/`, matching no collection and no reader in this plan | It is neither sharded nor a ledger. It belongs to whoever owns model qualification |
| `frontend/public/` mirrors have no day-grain question answered for them | Section 0.2 rules them monthly on the fetch argument. If the console ever fetches by day - a chart that wants one day and no more - the argument changes | ESCALATE trigger 2. It is the owner's call and it is not this plan's |

---

## See also

- [`20260911-handover.md`](20260911-handover.md) - how to pick this queue up with no context: the queue reader, the reading order, and the standing traps.
- [`20260911-execution-order.md`](20260911-execution-order.md) - the schedule across the five open plans. **Row #1 here is the second-heaviest constraint in the project**, blocking 17 of the 58 live rows, and rows #5 to #8 are the one place where four rows collide with each other so hard that no arrangement runs two of them together.
- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - the plan this split out of; its section 0 names this work and its section 26 names the same open gaps. **Three edges run between the two plans**: its rows #14, #16, #17 and #21 wait on row #1 here for `backend/idhazh/day_partition.py` and each add a prune to `backend/idhazh/retention.py` that rows #5 to #8 here rewrite; its row #1b and row #8 here both rewrite `state/scores/`; and its row #1b deletes `state/fingerprints.csv`, which section 0.2 here rules on.
- [`20260911-classification-research-record.md`](20260911-classification-research-record.md) - the decision and research record for the conversation this plan split out of, including the measurements its budget arithmetic rests on.
- [`20260907-growing-reads-window-plan.md`](20260907-growing-reads-window-plan.md) - the plan that put a cover on every read over a growing collection; row #1 repoints its links to the renamed partitions page.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection must declare, and the four cover rows this plan rewrites.
- [`../docs/concepts/partitions.md`](../docs/concepts/partitions.md) - the page row #1 renamed from `month-partitions.md` on 2026-09-11; the layout rule it carries is the one every row here obeys. **This link was one of the fourteen row #1 repointed**, and until that row landed it stayed at the name that resolved - a See-also pointing at a file that does not exist is a broken link in every clone.
- [`../docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md) - the shard rule: a ledger partitions only when its read carries a window.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and where the no-two-rows-one-file rule comes from.
- [`../docs/how-to/author-a-plan.md`](../docs/how-to/author-a-plan.md) - the shape every row above is written in.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every gate set in section 0.1a.
