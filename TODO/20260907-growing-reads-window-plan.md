# Every Read Over A Growing Collection Carries A Window

**Last Updated**: 2026-09-07
**Level**: 5 (a persisted contract, a partition layout, a repo-wide rule, and a reader-facing guarantee that gains a switch)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): one worktree-isolated worker per row, personas consulted on ambiguity, AUTO-merge on green gates, parallel N = 3. Honour the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Rule #12 refuses a cost that rises when nobody wrote any code, and names review as the only control. Review is a person remembering to ask. This plan makes the question mechanical: a read over a growing collection declares what it covers, and `-1` is how a person says out loud that they chose not to bound it. |
| Hard scope - in | The rule, its inventory of 21 reads, and every row below. `state/published.csv` becomes a day tree and is the worked example. |
| Hard scope - out | The two reads [the constant-cost plan](20260906-constant-cost-reads-plan.md) owns - telemetry publication (its row 19) and source health (its row 20). Every frontend and browser read, which is that plan's ranks 1 and 10. Content fingerprints and semantic dedup. Deleting any committed row from any ledger. |
| ESCALATE triggers | (a) Any row that would delete a committed row. (b) Any row that would ship a finite window - **every window here ships at `-1` or is bounded by construction**. (c) Row 7 running while a scheduled digest is in flight. (d) Any row that cannot hold its Oracle without weakening a guarantee. (e) A finite window less than or equal to `collect.seen_window_days`. |
| Chosen strategy | State the rule, take the inventory, convert one surface end to end as the worked example, then the rest. Ship every horizon switched off so the machinery lands and turning it on is a config edit a person makes on evidence. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

### The rule

**A read over a collection a run appends to declares what it covers. `-1` means unbounded, and it is how a person says out loud that they chose not to bound this one.**

This is not a second Rule #12. It is Rule #12's escape hatch made mechanical. Rule #12 already permits a growing read where a person agrees and says why; today that agreement is a paragraph in a docstring, invisible to everything except a reviewer's memory. A `-1` in `config/` is the same agreement written where a diff can see it, a schema can bound it, and a test can name it.

**A declared cover is not always a clock.** It can be a span of days, the files this run staged, one run, or one payload. The smallest honest one wins. Where a clock would be semantically wrong - row 8 is the worked case - the answer is a cheaper representation, not a shorter memory.

It composes with the shard rule in [docs/architecture/contracts/schemas.md](../docs/architecture/contracts/schemas.md) rather than replacing it. Partitioning still follows from windowing, so nothing partitions for its own sake.

### Personas, 2026-09-07

Four were consulted. Three refused a bounded repeat guard. This plan ships their objection as the default rather than overriding it.

| Persona | Ruling | What this plan did with it |
| --- | --- | --- |
| Carmack | Approve shards, veto day shards, fix the materialising read first | Row 2 lands first. Day grain overruled by the owner on structural grounds - see below |
| Fowler | Veto the horizon. The cutover loses a day's push if the migration deletes the flat file under a running job | Rows 4-7 are his expand-migrate-contract sequence |
| Editor | No horizon. Every case where re-planning helps happens within days; every case where it hurts happens after months | Default `-1`. The knob exists; the horizon does not fire |
| Reader | "It feels like being lied to about the date." Ranked a republished story above a dead link as a trust failure | Row 7's Oracle is that with `-1` the guard is bit-identical to today's |

**Owner decisions, 2026-09-07, under CLAUDE.md section 0.** Day grain for the published ledger, overriding Carmack's veto - his veto was against the claim that day files load faster, which is false, and the owner's reason is structural instead. The horizon ships off. A finite value is a later decision on row 1's evidence, and section 0 makes it an ESCALATE trigger for any agent.

**Deferred, and named so it is not lost.** The owner's actual intent - republish when something underlying changed - is a content fingerprint, not a clock. A clock cannot tell a developed story from a forgotten one. Separate feature, out of scope.

## 0a - What was measured

Everything below was taken on this checkout, 2026-09-07, on an Intel Core i7-1265U.

### The published ledger today

7,243 rows, 756 KB, **106.9 B a row**, 7,162 distinct addresses, 15 published days - **483 rows a day**. `load_published` takes **37.0 ms best, 69.0 ms worst, 32.0 ms spread** over five runs, and peaks at **500.9 B a row** while reading, which is 3.63 MB. Projected at the measured rate: 18.8 MB and 88 MB of peak at one year, 56.5 MB and 265 MB at three.

**81 addresses carry more than one row and every one of those gaps is zero days.** No address in the committed ledger was published and then published again on a later date. Read that as evidence the guard works, not that it is idle - the ledger cannot show a repeat the guard blocked.

### Grain: a synthetic year, 176,295 rows, three layouts

| Layout | Whole history | 120-day window | Opens in window | Bytes read in window |
| --- | --- | --- | --- | --- |
| One file | 2,654 ms | not possible | 1 | 17.1 MB |
| 12 month files | 1,741 ms | 293 ms | 4 | 5,715,970 |
| **365 day files** | 2,514 ms | 587 ms | 121 | 5,673,448 |

Day files read 42 KB **fewer** and take **twice as long**; the extra 294 ms is 117 file opens at about 2.5 ms each on Windows. Parse cost is bytes, not opens. The unbounded read is where day grain hurts most - 2,514 ms with a 1,684 to 18,592 ms spread - and that is the mode shipping as default. Accepted: it is seconds in a job that runs for hours.

### Git does not append, and packing recovers it anyway

60 days, 5 runs a day, 300 commits:

| Layout | Working tree | `.git` before gc | after gc |
| --- | --- | --- | --- |
| One file | 2,757 KB | 3,772 KB | **275 KB** |
| Month files | 2,757 KB | 329 KB | **280 KB** |
| Day files | 2,759 KB | 338 KB | **296 KB** |

Every commit writes a whole new object - there is no append in git - which is why one file is **11 times worse before packing**. Packing recovers essentially all of it, and day files end up **slightly the largest**. **Repository size is not a reason for day files.** Recorded because the opposite is the intuitive answer and it is wrong.

### Why day grain, then

Three reasons survive, none of them speed or size.

1. **One partition rule.** `frontend/public/digest/YYYY/MM/DD/` is already day-partitioned and published rows are derived from exactly those days.
2. **Unpublishing a day becomes a file delete.** With month files, removing a day's rows means editing a month file, and `merge=union` cannot express a row deletion - the removal silently does not happen after a rebase. With day files it is one `rm`, the case the partition doc already blesses.
3. **Smaller merge surface.** Two runs collide on a file only if they are the same day. With month files roughly 150 runs a month share one file.

### The eval ledger

`state/scores/<YYYY-MM>.csv`: 2 shards, 7,617 rows, **6,095 KB**, 36 columns, **800 B a row, 508 rows a day**. That is **406 KB a day and 148 MB a year** - eight times the published ledger and the fastest-growing state collection. Retention folds a month at 14 months, so live settles near **173 MB**; the archive digests then grow for ever at about **11.9 MB a year**.

### The rest of the state tree

| Collection | Files | Size | Grows with runs? |
| --- | --- | --- | --- |
| `state/seen/` | 2 | 5,407 KB | yes, windowed at 90 days |
| `state/scores/` | 2 | 5,870 KB | yes, row 8 |
| `state/item-health/` | 2 | 2,761 KB | yes, windowed |
| `state/feed-health/` | 2 | 1,084 KB | yes, windowed |
| `state/published.csv` | 1 | 756 KB | yes, rows 1-7 |
| `state/runtime-counters.csv` | 1 | 32 KB, 189 rows | yes, row 10 |
| `state/visual-prunes.csv` | 1 | 0.6 KB, 4 rows | yes, row 16 |
| `state/fingerprints.csv` | 1 | 2.4 KB, 3 rows | yes, row 11 |
| `state/feed-retirements.csv` | 1 | 0.1 KB, 0 rows | **no** - grows with configured sources |
| `frontend/public/digest/` | 426 | 23.02 MB | yes, rows 12-15 |
| `corpus/` | 3 | 13,750 KB | **no** - rolling, capped at `finetune.corpus_rows` = 2000, harvested every 7 days |

## 0b - The inventory: 21 reads, every one decided

| # | Read | What it costs today | Decision | Row |
| --- | --- | --- | --- | --- |
| 1 | `ledger.load_published` | Every row ever published | Day tree plus a declared cover | 1-7 |
| 2 | `evals.writer.recorded_observations` | Every live score shard **and** every archived month, before one append. 6,095 KB now, ~173 MB at steady state | **A digest index.** A clock is semantically wrong here | 8 |
| 3 | `ledger.keyed_paths` in settlement | Globs every feed-health and item-health shard, plus every score shard | Cover = the files this run staged | 9 |
| 4 | `ledger.load_runtime_counters` | The lifetime file, to answer about one run | Stream it. Cover is already one run | 10 |
| 5 | `fingerprint.append_new` | Every fingerprint ever | Stream it | 11 |
| 6 | `cli.stage_validate_days` | Every published day, every publication | **Never re-validate a frozen day.** Receipt on content plus validator version | 12 |
| 7 | `assemble.site_size` | The whole public tree | Maintained total | 13 |
| 8 | `retention.visuals_older_than` | The whole public tree | Dated directories, no glob | 14 |
| 9 | `retention.month_shards` and the prune inventories | Every partition directory | Due-check from the catalogue | 15 |
| 10 | `ledger.load_visual_prunes` | The whole file. 4 rows now, ~1,825 a year | Day partition, same as the rest | 16 |
| 11 | `ledger.load_seen` | 90-day cover | **Already correct.** The template | none |
| 12 | `ledger.load_health` | `HEALTH_WINDOW_DAYS` | Already correct | none |
| 13 | `ledger.load_item_health` | Caller's cover | Already correct | none |
| 14 | The reliability read in `stage_plan` | `collect.reliability_window_days` | Already correct | none |
| 15 | The trace read in `stage_assemble` | `observability.trace_window_days` | Already correct | none |
| 16 | `ledger.load_settled_failures` | One date | Already correct | none |
| 17 | `ledger.load_source_counts` | One date | Already correct | none |
| 18 | `ledger.load_retirements` | Whole file, 0 rows | **Correctly unbounded and must stay so.** A retirement is permanent; forget it and the pipeline asks a dead server again tomorrow | 11 states the bound |
| 19 | `corpus.scored_from_items`, `render.write`, `assemble.days_in_month` | One run, one run, one month | Bounded by construction | 11 states the bound |
| 20 | The corpus harvest | Rolling window, capped at 2,000 rows, every 7 days | Bounded by design | 11 states the bound |
| 21 | `contracts.base.Contract.read` | One payload, never a collection | **Cannot be bounded and does not grow with history.** A validator cannot skip what it has not read | 11 states the bound |

Two more - telemetry publication and source health - belong to [the constant-cost plan](20260906-constant-cost-reads-plan.md), rows 19 and 20 there.

## 1 - Status Reckoner

| # | Row title | Depends-on | Group | Status | PR |
| --- | --- | --- | --- | --- | --- |
| 1 | Stale numbers, and record what the guard drops | - | A | **DONE** | #499 |
| 2 | The read stops materialising the file | - | A | **DONE** | #488 |
| 3 | The cover setting, and the value it refuses | - | A | **DONE** | #490 |
| 4 | The reader tolerates both shapes | 2 | B | **DONE** | #492 |
| 5 | The writer routes by day | 4 | C | **DONE** | #495 |
| 6 | The one-shot split | 5 | D | **DONE** | #503 |
| 7 | The cover, the fallback deleted, and the docs | 3, 6 | E | **DONE** | #510 |
| 8 | The eval writer reads a digest index | 3 | B | **DONE** | #496 |
| 9 | Settlement touches the files the run staged | 3 | B | **DONE** | #513 |
| 10 | Runtime counters answer about one run | - | A | **DONE** | #498 |
| 11 | Fingerprints, and the four bounds declared | - | A | **DONE** | #493 |
| 12 | A frozen day is never re-validated | 3 | B | **DONE** | #505 |
| 13 | Site size is a maintained total | - | B | **DONE** | #491 |
| 14 | Visual cleanup walks dated directories | 3 | B | **DONE** | #494 |
| 15 | State cleanup asks the catalogue what is due | 3 | B | **DONE** | #504 |
| 16 | Visual prunes get the day layout | 5 | D | **DONE** | #514 |
| 17 | The rule gets its concept doc | 7, 16 | F | **DONE** | #515 |

Every row has landed, so this plan is the record of how the window rule was built rather than a queue of work.

Two rows did not land what this plan asked for, and the reason is recorded rather than smoothed over.

**Row 13 shipped the retraction half only.** Three separate jobs write `frontend/public/digest/`, so a running total one of them kept would silently miss the other two, and carrying one between them needs a new persisted contract. The three remaining walks now state in the code what they read, how the cost grows, and why a bounded input cannot answer it - Rule #12's escape hatch taken in the open rather than by omission.

**Row 15's premise was false.** Measured 2026-09-07 on an Intel Core i7-1265U, a not-due maintenance pass opens 5 directories and 0 shard files, and that count does not move when the tree holds forty-six times more - a month partition is a file, not a directory, so there was no partition directory for a dated walk to skip. Rule #10 says the design changes, so no optimisation was written. The row shipped the deletion bug the measurement uncovered instead: three month-name recognisers disagreed, and `prune_scores` was deleting files the other two protected.

**Inventory item 15 is wrong, and row 17 found it.** There is no windowed trace read in `stage_assemble`. `observability.trace_window_days` drives `retention.prune_traces`, which deletes whole files - so the bound sits on the store, not on a read, and a read of a store already pruned needs no cover of its own. [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) teaches that as its own mechanism.

Rows 1, 2, 3, 10 and 11 are disjoint and run together. Rows 4 to 7 are strictly serial - each is only safe because the one before it landed. Rows 8, 9, 12, 13, 14, 15 are independent of the published cutover and of each other. Row 17 is written last, because a rule with worked examples behind it says something a rule with none cannot.

### Defects found during planning

| Defect | Closes in |
| --- | --- |
| [ledger.py](../backend/idhazh/ledger.py) sizes the ledger at 214.9 B a row and 1,000 rows a day. The row has been 106.9 B since 2026-08-26 and the measured rate is 483; `run.safety_ceiling_per_run` is 80, not 200 | Row 1 |

## 2 - Row #1 - Stale numbers, and record what the guard drops

- **Scope:** Correct the ledger's own arithmetic, and make visible the one number this design turns on. Today [cli.py](../backend/idhazh/cli.py) logs `addresses this run will not plan published=%s` to stderr and nothing commits it, so nobody can say how often the guard fires or how old the addresses it refuses are.
- **Files:** `backend/idhazh/ledger.py` (docstring), `backend/idhazh/cli.py`, `backend/idhazh/contracts/run_plan.py`, `schemas/run-plan.schema.json`, `backend/tests/test_plan.py`, `backend/tests/test_contracts.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** a plan built over a fixture ledger holding one address published 200 days ago and one yesterday records `dropped_published = 2` and an age histogram naming both buckets. Assert on the built fixture, never on the committed ledger.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Additive and optional, so a plan payload an earlier run wrote still validates. Section 11: date-stamped `version`, a `changelog` entry, no read-side migration needed | Fowler |
| 2 | Record the **age distribution**, not only the count. A count says the guard fired; the distribution says whether a 120-day horizon would have let any through. That is the number Editor named as the one that would change his ruling | Editor |
| 3 | The corrected docstring quotes 2026-09-07 on an Intel Core i7-1265U with hardware, date and spread | Rule #10 |

## 3 - Row #2 - The read stops materialising the file

- **Scope:** `ledger._read_rows` builds a list of the whole file before `load_published` reduces it - 500.9 B of peak per row, 3.63 MB today, 265 MB projected at year three. Stream instead and keep only the mapping.
- **Files:** `backend/idhazh/ledger.py`, `backend/tests/test_ledger.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** hold the answer still and double the file. Two built fixtures over the same 20,000 addresses, one with 40,000 rows and one with 80,000; peak must not follow the rows.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Lands before any layout change and is independently valuable. Level 1, no contract, and if it takes peak far enough down the case for a horizon weakens rather than strengthens - which must be reported, not buried | Carmack, condition 1 |
| 2 | A threshold in bytes a row would pass for the wrong reason, because what a reduction legitimately keeps is its mapping. The property is asserted directly instead | this plan |
| 3 | Both fixtures are built in the test. Rule #12 and section 13: a test's cost belongs to the code it checks | CLAUDE.md section 13 |

## 4 - Row #3 - The cover setting, and the value it refuses

- **Scope:** `collect.published_window_days`, default `-1`. The validator's job is to make one specific mistake impossible.
- **Files:** `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_contracts.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** the contract refuses `0`, `89` and `90`; accepts `-1`, `91` and `120`; the refusal message names `collect.seen_window_days` and its current value; a test asserts the committed config carries `-1`.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `-1` is the only sentinel. Not `0`, not `null`, not a very large number - a large number is a cover that silently becomes finite when the archive outgrows it | Owner, 2026-09-07 |
| 2 | Accepts `-1` **or** strictly greater than `collect.seen_window_days`, refusing everything between including 90. Equal is the hole: an undated address whose sight row expires the same week reads as first-seen-today and republishes as new. Asserted in the contract, not in prose | Editor, Carmack |
| 3 | A cross-field validator, so it re-runs whenever either value moves. Raising the sight window past a finite cover fails the config rather than opening the hole quietly | Fowler |

## 5 - Row #4 - The reader tolerates both shapes

- **Scope:** `load_published` reads the flat `state/published.csv` **and** any `state/published/YYYY/MM/DD.csv`, returning the union with the earliest date per address. No writer changes, no behaviour changes. This row exists so rows 5 and 6 cannot lose a row.
- **Files:** `backend/idhazh/ledger.py`, `backend/tests/test_ledger.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** five arms over built fixtures - flat only, days only, both with disjoint addresses, both holding the same address on different dates (the earlier wins), and a stem that is not a date (raises).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No glob.** The enumerator walks `state/published/YYYY/MM/` and accepts a stem only if it matches `\d{2}` under `\d{4}/\d{2}`. Anything else raises rather than being skipped - a file nobody can explain in a state directory is a fault, and silently ignoring it is how a reader starts missing rows | Owner, 2026-09-07 |
| 2 | `state/published/` beside the flat file rather than replacing it in place. A reader that enumerates a directory reads every file it finds as that directory's shape | [ledger.py](../backend/idhazh/ledger.py) |
| 3 | A missing directory and a missing flat file both mean "no history", which is what a fresh clone has. Neither is an error | [ledger.py](../backend/idhazh/ledger.py) |

## 6 - Row #5 - The writer routes by day

- **Scope:** `append_published` takes a date and appends to `state/published/YYYY/MM/DD.csv`, mirroring `frontend/public/digest/YYYY/MM/DD/`. The flat file is no longer written and is still read. `published_path` gains a date parameter; `published_relpath` is added to match every other partitioned collection.
- **Files:** `backend/idhazh/ledger.py`, `backend/idhazh/cli.py`, `.gitattributes`, `.github/workflows/digest.yml`, `backend/tests/test_ledger.py`, `backend/tests/test_workflows.py`, `backend/tests/rebuild_day.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, plus `backend/tests/test_workflows.py` run directly. CI - full suite.
- **Oracle:** a run on `2026-09-07` writes `state/published/2026/09/07.csv` and touches no other file; a run on `2026-10-01` leaves September byte-identical. `REFRESH_PATHS` and its mirror in `test_workflows.py` both name `state/published` and are asserted equal.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`.gitattributes` gets an explicit line for `state/published/**/*.csv`**, not the existing `state/**/*.csv` catch-all. The catch-all would already cover it, and that is the problem: a merge rule a new collection inherits without anyone choosing it is the same defect as a growing cost nobody chose | Owner, 2026-09-07 |
| 2 | `merge=union` stays correct for the reason the existing comment gives - rows are independent and the reader keeps the earliest of two. Restated at the new line rather than assumed from the neighbour | Fowler |
| 3 | `REFRESH_PATHS` names the directory `state/published`, matching `state/scores` and `state/item-health`. The mirror in `test_workflows.py` reds in CI if the two drift - move both in one commit | Fowler |
| 4 | A run whose date falls in a closed day performs a correction, the case `append_seen` already handles and the freeze rule already permits | [partitions.md](../docs/concepts/partitions.md) |

## 7 - Row #6 - The one-shot split

- **Scope:** `backend/utilities/split_published_ledger.py` reads the flat file, writes every row into its day file, verifies, and removes the flat file. Modelled on `migrate_published_ledger.py`, the worked precedent.
- **Files:** `backend/utilities/split_published_ledger.py` (new), `state/published.csv` (removed), `state/published/2026/08/**.csv` and `state/published/2026/09/**.csv` (new), `backend/tests/test_ledger.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite. **Plus a reconciliation the utility prints and a person reads.**
- **Oracle:** before and after, `load_published` over the real `state/` returns identical keys and identical values. The utility prints rows in, rows out, day-file count and the mapping digest, and refuses to remove the flat file unless in equals out.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Runs when no scheduled digest is in flight**, as a deliberate act. `merge=union` is a content driver and cannot resolve a delete against a modify, so a split racing a running job conflicts, burns the retry budget, and loses the whole day's push | Fowler |
| 2 | The race is survivable rather than merely avoided, and that is why row 4 came first: if the flat file returns through a merge the reader still reads it and no address is lost. The next split removes it again. A cutover whose failure mode is redundancy rather than loss is the only kind worth running against a live schedule | Fowler |
| 3 | Rows are copied, never rewritten. Same cells, same order, same bytes; only the file they live in changes. The `version` cell travels with the row | Section 11 |
| 4 | The utility stays committed after it runs, as `migrate_published_ledger.py` did, so a person with an old checkout can run it | [partitions.md](../docs/concepts/partitions.md) |

## 8 - Row #7 - The cover, the fallback deleted, and the docs

- **Scope:** `load_published` gains `today` and `within_days`, drops the flat-file fallback, and reads the day files its cover names. Every doc that describes the old shape moves in the same commit.
- **Files:** `backend/idhazh/ledger.py`, `backend/idhazh/cli.py`, `backend/idhazh/contracts/seen.py`, `backend/idhazh/contracts/digest_day.py`, `schemas/published-row.schema.json`, `schemas/digest-day.schema.json`, `backend/tests/test_ledger.py`, `backend/tests/test_plan.py`, `backend/tests/test_discover.py`, `backend/tests/test_pipeline.py`, and 13 docs: `docs/architecture/contracts/schemas.md`, `docs/architecture/sources/freshness.md`, `docs/architecture/publishing/layout.md`, `docs/architecture/sources/discovery.md`, `docs/concepts/partitions.md`, `docs/concepts/pipeline-loop.md`, `docs/concepts/evaluation.md`, `docs/how-to/run-the-pipeline.md`, `docs/reference/measurements.md`, `docs/reference/data-growth-audit.md`, `docs/reference/repository-layout.md`, `docs/architecture/sources/item-health.md`, `AGENTS.md`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** with the committed config the mapping is **equal cell-for-cell to what it returned before this plan started** - the guarantee is untouched, which is the whole point of shipping `-1`. A second arm sets 120 over a built fixture spanning six months and proves the older day files are not opened, by counting file reads rather than by timing them.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`-1` enumerates; a finite cover names days.** The unbounded path walks the tree validating every stem; the bounded path asks for the dates in range and opens only those. Two paths, two tests, neither one a glob | Owner, 2026-09-07 |
| 2 | `freshness.md` currently argues at length that this file must not shard, and lists the shard as a rejected alternative. That section is **rewritten to say what changed and why**, not deleted. A reversed decision whose reasoning vanishes is how the same argument gets had twice | CLAUDE.md section 4 |
| 3 | `partitions.md` moves the published row into the partition table and states the coupling to `seen_window_days` next to it. It also gains the day grain as a second partition unit, which the digest tree already uses | Carmack |
| 4 | `measurements.md` gains the 2026-09-07 figures, including the two that went **against** the design - day files take twice the wall clock of month files, and after packing they are the largest in git. A measurement that contradicts the design is recorded, not dropped | Rule #10 |
| 5 | `docs/archive/measurements-2026-08.md` is history and is **not** edited | Fowler |

## 9 - Row #8 - The eval writer reads a digest index

- **Scope:** `evals.writer.append` builds `recorded_observations` before writing one row, and that set is the union of every live score shard and every archived month - 6,095 KB now, about 173 MB at steady state.
- **Files:** `backend/idhazh/evals/writer.py`, `backend/idhazh/evals/archive.py`, `backend/idhazh/contracts/` (the index shape), `schemas/`, `backend/tests/test_evals.py`, `backend/tests/test_contracts.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** an append refuses exactly the observations it refuses today, including one whose only record is an archived digest. Over a built fixture of 200,000 observations the writer reads bytes proportional to the index, not to the rows.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A clock is semantically wrong here.** `OBSERVATION_KEY` is `url_key, pipeline_fingerprint, output_digest, scorer_version` and carries **no date, deliberately**. The same address, pipeline, output and scorer is the same measurement whenever re-taken. A cover in days would let a January observation back in February, turning "how many measurements do we hold" into "how many times did the pipeline look" - the one thing the ledger promises it is not | [writer.py](../backend/idhazh/evals/writer.py) |
| 2 | **So the answer is a cheaper representation, not a shorter memory.** Maintain the archive's own digest index for live months too. 64 bytes an observation instead of 800 - **11.9 MB a year instead of 148 MB**, a 12-fold cut - exact, no clock, nothing forgotten. The raw score rows stop being read by the writer at all | this plan |
| 3 | The archived half is never bounded. A month past retention has no rows left, so the digest is the only record its measurements happened. Drop it and every measurement in that month reads as new the day the shard was deleted | [writer.py](../backend/idhazh/evals/writer.py) |
| 4 | This is the row that proves the rule is not "put a clock on everything". The declared cover here is "every observation identity", and the honesty is in saying so and paying 64 bytes for it | this plan |

## 10 - Row #9 - Settlement touches the files the run staged

- **Scope:** after a push race, git's union merge concatenates both sides of a state CSV and a keyed row appears twice. `stage_dedupe_ledgers` runs after the rebase and rewrites each keyed file without repeats. It currently globs every feed-health shard, every item-health shard and every score shard - 9,715 KB today, and the shard count rises every month.
- **Files:** `backend/idhazh/cli.py`, `backend/idhazh/ledger.py`, `backend/idhazh/evals/writer.py`, `backend/tests/test_ledger.py`, `backend/tests/test_workflows.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, plus `backend/tests/test_workflows.py` run directly. CI - full suite.
- **Oracle:** the real-Git race tests still settle a duplicated row correctly, and a settlement after a run on `2026-09-07` opens no file from an earlier month.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The cover is not a clock, it is the files this run staged.** A run appends only to its own date's shard, so a duplicate can only exist in a file this run wrote to. The staged set is already known; nothing needs computing. This is the one row that ships a real cover rather than `-1`, because it has no reader-facing risk | Owner, 2026-09-07 |
| 2 | What we lose, stated: if an **earlier** run left a duplicate that was never settled - because the settle step itself failed - a later run no longer cleans it up silently. The full settle stays available as an operator command a person runs on demand | this plan |
| 3 | The real-Git tests run directly rather than through the selector, because this is the row most likely to be found wrong by them | [agent-notes.md](../docs/reference/agent-notes.md) |

## 11 - Row #10 - Runtime counters answer about one run

- **Scope:** `load_runtime_counters(state_dir, *, run_id)` already asks about one run, then reads the whole lifetime file to find it - 189 rows and 32 KB today, growing by about 40 rows a day.
- **Files:** `backend/idhazh/ledger.py`, `backend/tests/test_ledger.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** the rows returned for a run are identical before and after, and peak follows the run's own rows rather than the file, proved the way row 2 proves it.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Stream, do not partition.** A `run_id` already names its date, so this read is bounded by construction the moment it stops materialising. Partitioning 32 KB adds a layout for no answer it does not already have | Carmack |
| 2 | This is the row that shows the rule is not "shard everything". A declared cover can be one run | Carmack |

## 12 - Row #11 - Fingerprints, and the four bounds declared

- **Scope:** `fingerprint.append_new` rebuilds every recorded identity before adding a few - 3 rows and 2.4 KB today. Stream it. The second half is the more valuable one: write down, next to each read that is deliberately unbounded, what bounds it and why.
- **Files:** `backend/idhazh/fingerprint.py`, `backend/idhazh/ledger.py` (comment at `load_retirements`), `backend/idhazh/corpus.py`, `backend/idhazh/contracts/base.py`, `backend/tests/test_fingerprint.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** a repeated identity is still refused, and each of the four deliberately-unbounded reads carries one line naming what it reads and why a cover is not the answer.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four are inventory items 18 to 21: **retirements** (permanent, forgetting one wakes a dead server), **per-run and per-month reads** (bounded by construction), **the corpus** (rolling, capped at 2,000 rows, every 7 days), and **contract validation** (one payload, and a validator cannot skip what it has not read) | this plan |
| 2 | Three rows in a lifetime file is not a growth problem, and saying so plainly is worth more than converting it. What changes is that the read declares its cover; the value is `-1` and the reason sits beside it | Carmack |

## 13 - Row #12 - A frozen day is never re-validated

- **Scope:** `cli.stage_validate_days` parses and validates every published day against both shapes on every scheduled publication - 426 files and 23.02 MB today.
- **Files:** `backend/idhazh/cli.py`, `backend/idhazh/contracts/` (the receipt shape), `schemas/`, `backend/tests/test_pipeline.py`, `backend/tests/test_contracts.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** three arms - a new day is validated fully; an unchanged day with an unchanged validator is not opened; and changing the validator identity invalidates every receipt so the whole archive is validated once.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Not a clock - a receipt.** A published day is a frozen artefact; nothing about it can change except deletion. So do not re-validate it on a window, do not re-validate it at all. Validate once at write. Re-validate only when the validator itself changes, and then re-validate everything, once | Owner, 2026-09-07 |
| 2 | The receipt keys on content **and** validator-plus-projector version. Mtime alone would reuse a stale result; content alone would miss a rule change | Fowler |

## 14 - Row #13 - Site size is a maintained total

- **Scope:** `assemble.site_size` walks the whole public tree on every assembly; `retention.measure` and `count_published_items` walk it again separately.
- **Files:** `backend/idhazh/assemble.py`, `backend/idhazh/retention.py`, `backend/tests/test_retention.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** the total after a build equals an independent full walk of the same tree, including after a deletion. Growing the tree does not grow what the ordinary path reads.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The total is accumulated as output is written and retracted on deletion. A full independent walk stays available where certification genuinely needs one | Carmack |
| 2 | Committed-tree bytes and built-tree bytes stay separate measurements. They are different questions and mixing them was already a defect | [audit finding 17](../docs/reference/data-growth-audit.md) |

## 15 - Row #14 - Visual cleanup walks dated directories

- **Scope:** `retention.visuals_older_than` sorts the entire public tree before selecting expired assets. The deletion fuse caps removals, not the scan.
- **Files:** `backend/idhazh/retention.py`, `backend/tests/test_retention.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** expiry over a built tree of 400 days returns the same set as the full sort, and opens only the dated directories its policy names.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No globbing per day.** Walk `YYYY/MM/` and select the days in range by name. A directory entry that is not a date raises | Owner, 2026-09-07 |
| 2 | Exact candidate counts, suffix exclusions, backdated-run safety and fuse behaviour are unchanged. Stopping at the fuse would lose the backlog count | [audit finding 18](../docs/reference/data-growth-audit.md) |

## 16 - Row #15 - State cleanup asks the catalogue what is due

- **Scope:** `retention.month_shards` and the prune inventories list and sort every partition directory across every store, on every maintenance pass, including passes where nothing is due.
- **Files:** `backend/idhazh/retention.py`, `backend/tests/test_retention.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** a not-due pass opens no partition. A due pass touches exactly the partitions past their age and no others. Dry-run output is identical to today's.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The keep-set is still derived from `shards_in_window`, which is what makes it impossible to delete a shard a later read would have opened | [ledger.py](../backend/idhazh/ledger.py) |
| 2 | Backdated-run safety and the deletion fuses are unchanged | [audit finding 19](../docs/reference/data-growth-audit.md) |

## 17 - Row #16 - Visual prunes get the day layout

- **Scope:** `state/visual-prunes.csv` is one row per run - 4 rows now, about 1,825 a year. It does grow with runs. Give it the day layout row 5 built.
- **Files:** `backend/idhazh/ledger.py`, `backend/idhazh/cli.py`, `.gitattributes`, `.github/workflows/digest.yml`, `backend/utilities/split_visual_prunes.py` (new), `backend/tests/test_ledger.py`
- **Gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** the report over the whole series is identical before and after the split, and a run writes only its own day's file.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It grows with runs, so it takes the same layout as everything else that does. Consistency is worth more here than the 274 KB a year it saves | Owner, 2026-09-07 |
| 2 | The **read** stays unbounded at `-1`, because the report is about the whole series and a cover would answer a different question. The layout changes; the question does not | this plan |

## 18 - Row #17 - The rule gets its concept doc

- **Scope:** `docs/concepts/growing-reads.md` - the rule, the inventory, the three tiers, and how `-1` relates to Rule #12's escape hatch. Written last so it describes what shipped.
- **Files:** `docs/concepts/growing-reads.md` (new), `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `CLAUDE.md`, `docs/reference/documentation-structure.md`
- **Gates:** doc checks only; this row changes no application code. CI - full suite.
- **Oracle:** every read in the inventory appears with its declared cover or its stated bound, and the count in the doc matches the count in the code. A person reading only that page can answer "does this read need a cover" for a collection invented tomorrow.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A property, not a list.** The doc states the question - does this read cost more when a run appended more - and the inventory is a dated example table underneath it. The archive guard deleted on 2026-09-06 failed precisely because it was a list of paths pretending to be a rule | [CLAUDE.md](../CLAUDE.md) Rule #12 design rationale |
| 2 | It names the three shapes a cover can take - a span of days, the files a run staged, one run or one payload - so the next reader does not reach for a clock by reflex. Rows 8, 9 and 10 are the worked examples of each | this plan |
| 3 | `docs/concepts/`, beside [partitions.md](../docs/concepts/partitions.md): that page says what a layout obliges a writer to do, this says what a growing collection obliges a reader to declare | [documentation-structure.md](../docs/reference/documentation-structure.md) |
| 4 | CLAUDE.md gains a paragraph rather than a new rule. Rule #12 already forbids the growing cost nobody chose; this only says where the choosing is now written down | Owner, 2026-09-07 |

## What this plan does not fix

- **No finding is closed by shipping `-1`.** Every read still opens what it opened before, except rows 8 to 16 which are exact rather than windowed. What lands is the layout, the knob and the declaration. Closing a finding is a person setting a finite value on evidence.
- **The lookup key is still not the partition key** for the published ledger. Fowler's objection stands. A key-ordered index remains the answer if this ever becomes a measured cost - and after row 2, it very likely will not.
- **Nothing is ever pruned** from the published ledger. 365 files a year, kept for ever. A cover buys read time, never bytes.
- **The frontend and the browser are untouched.** Those are ranks 1 and 10 of the audit and belong to [the constant-cost plan](20260906-constant-cost-reads-plan.md).

## See also

- [../docs/reference/data-growth-audit.md](../docs/reference/data-growth-audit.md) - finding 1 and the Indexed State package this plan takes a slice of.
- [../docs/concepts/partitions.md](../docs/concepts/partitions.md) - the pattern, the freeze rule, and the four cases an append-only layout gets wrong.
- [../docs/architecture/sources/freshness.md](../docs/architecture/sources/freshness.md) - why publishing twice is prevented by a record rather than a window.
- [20260906-constant-cost-reads-plan.md](20260906-constant-cost-reads-plan.md) - ranks 1 and 10 of the same audit, in flight.
