# Every Read Over A Growing Collection Carries A Window

**Last Updated**: 2026-09-07
**Level**: 5 (a persisted contract, a partition layout, a repo-wide rule, and a reader-facing guarantee that gains a switch)

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md): one worktree-isolated worker per row, personas consulted on ambiguity, AUTO-merge on green gates, parallel N = 2. Honour the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Rule #12 refuses a cost that rises when nobody wrote any code, and names review as the only control. Review is a person remembering to ask. This plan makes the question mechanical: a read over a growing collection takes a window, and `-1` is how a person says out loud that they chose not to bound it. |
| Hard scope - in | The window rule and its inventory. Every unwindowed read named in the inventory below that no other plan owns. `state/published.csv` is the first worked example and carries rows 2 to 8. |
| Hard scope - out | The two surfaces [the constant-cost plan](20260906-constant-cost-reads-plan.md) already owns - telemetry publication (its row 19) and source health (its row 20). Content fingerprints and semantic dedup. Retention or pruning of any published row - **there is none, ever**. Changing the article ID format. Every frontend and browser read, which is that plan's ranks 1 and 10. |
| ESCALATE triggers | (a) Any row that would delete a committed row from any ledger. (b) Any row that would ship a finite window - **every window in this plan ships at `-1`**. (c) Row 7 running while a scheduled digest is in flight. (d) Any row that cannot hold its Oracle without weakening a guarantee. (e) A finite window less than or equal to the sight window it must outlive. |
| Chosen strategy | State the rule, take the inventory, then convert one surface end to end as the worked example before touching the rest. Ship every horizon switched off, so the machinery lands and turning it on is a config edit a person makes on evidence. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

### The decision, and who ruled on it

Four personas were consulted on 2026-09-07. Three refused a bounded repeat guard outright. This plan ships their objection as the default rather than overriding it.

| Persona | Ruling | What this plan did with it |
| --- | --- | --- |
| Carmack | Approve month shards, veto day shards, 120 days floored above the sight window - but the measured cost is a materialising read, not the layout, so fix that first | Row 2 lands the streaming read before any layout change. Month grain, not day. |
| Fowler | Veto. The partition key is not the lookup key, and the cutover loses a day's push when the migration deletes the flat file under a running job | Rows 4-6 are his expand-migrate-contract sequence. The reader tolerates both shapes before the flat file is ever removed. |
| Editor | No horizon. Every case where re-planning helps happens within days; every case where it hurts happens after months, so a clock inverts the useful window | Default `-1`. The knob exists; the horizon does not fire. |
| Reader | "It feels like being lied to about the date." Ranked a republished story above a dead link as a trust failure, and would not notice the speed at all | Row 7's Oracle is that with `-1` the guard is bit-identical to today's. |

**Owner decision, 2026-09-07, under CLAUDE.md section 0:** the layout ships, the knob ships, the horizon does not. `-1` means unbounded and is the committed default. A finite value is a later decision a person takes on row 1's evidence, and section 0 of this document makes it an ESCALATE trigger for any agent.

**Deferred, and named so it is not lost.** The owner's actual intent - "republish when something underlying changed" - is a content fingerprint, not a clock. A clock cannot tell a developed story from a forgotten one. That is a separate feature over a title-carrying surface and it is out of scope here.

## 0a - The rule, and the inventory it applies to

**A read over a collection a run appends to takes a window. A window of `-1` means unbounded, and it is how a person says out loud that they chose not to bound this one.**

This is not a second Rule #12. It is Rule #12's escape hatch made mechanical. Rule #12 already permits a growing read where a person agrees and says why; today that agreement is a paragraph in a docstring, so it is invisible to everything except a reviewer's memory. A `-1` in `config/` is the same agreement written where a diff can see it, a schema can bound it, and a test can name it.

It composes with the shard rule in [docs/architecture/contracts/schemas.md](../docs/architecture/contracts/schemas.md) rather than replacing it. That rule says a ledger partitions **because** its read carries a window. This one says every read declares its window, including the ones that decline to have one - so partitioning still follows from windowing, and nothing partitions for its own sake.

### Where it already holds

Seven reads take a window today, and they are the pattern every row below copies.

| Read | Window it carries |
| --- | --- |
| `ledger.load_seen` | `collect.seen_window_days`, 90 |
| `ledger.load_health` | `ledger.HEALTH_WINDOW_DAYS` |
| `ledger.load_item_health` | the caller's, from `config/` |
| the reliability read in `cli.stage_plan` | `collect.reliability_window_days` |
| the trace read in `cli.stage_assemble` | `observability.trace_window_days` |
| `ledger.load_settled_failures` | one date |
| `ledger.load_source_counts` | one date |

### Where it does not, and who owns each

Measured on this checkout, 2026-09-07.

| Surface | What it reads now | Size today | Owner |
| --- | --- | --- | --- |
| `ledger.load_published` | every row ever published | 7,243 rows, 756 KB | **rows 2-8 here** |
| `evals.writer.recorded_observations` and `ledger_shards` | every live score shard **and** every archived month, before appending one row | 5,870 KB over 2 shards | **row 9** |
| `ledger.keyed_ledgers` | globs every feed-health and item-health shard on every settlement | 3,845 KB over 4 shards | **row 10** |
| `ledger.load_runtime_counters` | the lifetime file, to answer about one run | 189 rows, 32 KB | **row 11** |
| `fingerprint.append_new` | every fingerprint ever recorded | 3 rows, 2.4 KB | **row 12** |
| `cli.stage_validate_days` | every published day, on every publication | 426 files, 23.0 MB | audit 16, deferred - names its bound in row 12 |
| `assemble.site_size`, `retention.visuals_older_than`, `retention.month_shards` | the whole public tree, three separate walks | 23.0 MB | audit 17-19, deferred - same |
| `publish_telemetry.publish` | every telemetry month | 1.05 MB | [constant-cost plan](20260906-constant-cost-reads-plan.md) row 19 |
| `publish_source_health._load_items` | all item history | 2,761 KB | that plan's row 20 |

### Where it must not hold, and why

Naming these is what stops the rule becoming a list nobody can finish. Each is a bound stated rather than a cost hidden.

| Surface | The bound |
| --- | --- |
| `ledger.load_retirements` | One row per permanently dead endpoint. It grows with the number of feeds a person configured, not with runs. 0 rows today. |
| `ledger.load_visual_prunes` | One row a run, and the read is a report on the whole series. Windowing it would answer a different question. 4 rows today. |
| `corpus.scored_from_items`, `render.write` | Bounded to one run's own artefacts. |
| `assemble.days_in_month` | Bounded to one month, which is the unit it publishes. |
| `evals.retrieval.load_corpus` | An explicit operator evaluation, never a pipeline read. |
| `contracts.base.Contract.read` | Fresh arbitrary bytes. A validator cannot skip what it has not read. |

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Stale numbers, and record what the guard drops | - | A | PENDING | - | - |
| 2 | The read stops materialising the file | - | A | PENDING | - | - |
| 3 | The window knob, and the value it refuses | - | A | PENDING | - | - |
| 4 | The reader tolerates both shapes | 2 | B | PENDING | - | - |
| 5 | The writer routes by month | 4 | C | PENDING | - | - |
| 6 | The one-shot split | 5 | D | PENDING | - | - |
| 7 | The window, the fallback deleted, and the docs | 3, 6 | E | PENDING | - | - |
| 8 | The eval writer stops reading every shard | 3 | B | PENDING | - | - |
| 9 | Settlement touches the shards the run wrote | 3 | B | PENDING | - | - |
| 10 | Runtime counters answer about one run | 3 | B | PENDING | - | - |
| 11 | Fingerprints, and the bounds the rest declare | 3 | B | PENDING | - | - |
| 12 | The rule gets its concept doc | 7, 11 | F | PENDING | - | - |

Rows 1 to 3 touch disjoint files and run together. Rows 4 to 7 are strictly serial: each one is only safe because the one before it landed. Rows 8 to 11 are independent of the published cutover and of each other; they wait only on the knob shape in row 3. Row 12 is written last, because a rule with two worked examples behind it says something a rule with none cannot.

**Rows 8 to 11 each ship at `-1`.** None of them changes what any read returns. What they change is that the read now has to say what it covers.

### Defects found during execution

| Found in | Defect | Closes in |
| --- | --- | --- |
| Planning | [ledger.py](../backend/idhazh/ledger.py) sizes the ledger at 214.9 B a row and 1,000 rows a day. The row has been 106.9 B since 2026-08-26 and the measured rate is 483 a day; `run.safety_ceiling_per_run` is 80, not 200 | Row 1 |

## 2 - Row #1 - Stale numbers, and record what the guard drops

- **Scope:** Correct the ledger's own arithmetic, and make the one number this design turns on visible without reading a CI log. Today [cli.py](../backend/idhazh/cli.py) logs `addresses this run will not plan published=%s` to stderr and nothing commits it, so nobody can say how often the guard fires or how old the addresses it refuses are.
- **Files touched:**
  - `backend/idhazh/ledger.py` (module docstring only)
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/run_plan.py`
  - `schemas/run-plan.schema.json`
  - `backend/tests/test_plan.py`
  - `backend/tests/test_contracts.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** a plan built over a fixture ledger holding one address published 200 days ago and one published yesterday records `dropped_published = 2` and an age histogram naming both buckets. Assert on the built fixture, never on the committed ledger.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The field is additive and optional, so a plan payload an earlier run wrote still validates. Section 11: date-stamped `version`, a `changelog` entry, and no read-side migration needed because the field is nullable | Fowler |
| 2 | Record the **age distribution**, not only the count. A count says the guard fired; the distribution says whether a 120-day horizon would have let any of them through. That is the number Editor named as the one that would change his ruling | Editor |
| 3 | The corrected docstring quotes what was measured on 2026-09-07 - 7,243 rows, 106.9 B a row, 483 a day, 37.0 ms to read with a 32.0 ms spread - and carries the hardware and the date, per Rule #10 | Carmack |

## 3 - Row #2 - The read stops materialising the file

- **Scope:** `ledger._read_rows` builds a `list[dict]` of the whole file before `load_published` reduces it. Measured 2026-09-07 on an Intel Core i7-1265U: 500.9 B of peak per row, which is 3.63 MB today and projects to 265 MB in year three. Stream the rows instead and keep only the mapping.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** over a **built** fixture of 50,000 rows, `tracemalloc` peak is under 40 B a row, and the returned mapping is equal cell-for-cell to what the current reader returns over the same fixture. Both arms in one test, so the comparison cannot drift.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This lands before any layout change and is independently valuable. It is Level 1, changes no contract, and if it takes peak below 10 MB at the one-year projection the case for the window weakens rather than strengthens - which is the honest outcome and must be reported, not buried | Carmack, condition 1 |
| 2 | The fixture is built in the test, not read from `state/`. Rule #12 and section 13: a test's cost belongs to the code it checks | CLAUDE.md section 13 |

## 4 - Row #3 - The window knob, and the value it refuses

- **Scope:** `collect.published_window_days`, default `-1`. The validator's job is to make one specific mistake impossible.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json`
  - `tests/fixtures/contracts/app-config/tuned.json`
  - `backend/tests/test_contracts.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** the contract refuses `0`, refuses `90`, refuses `89`, accepts `-1`, accepts `91`, and accepts `120`; and the refusal message names `collect.seen_window_days` and its current value. A test asserts the committed config carries `-1`.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `-1` means unbounded and is the only sentinel. Not `0`, not `null`, not a very large number - a large number is a window that silently becomes finite when the archive outgrows it | Owner, 2026-09-07 |
| 2 | The validator accepts `-1` **or** a value strictly greater than `collect.seen_window_days`, and refuses everything between. Equal is the hole: an undated address whose sight row expires the same week reads as first-seen-today and republishes as new. This is asserted in the contract, not written in prose | Editor, Carmack condition 3 |
| 3 | The knob is a cross-field validator, so it re-runs whenever either value moves. Raising `seen_window_days` past a finite `published_window_days` fails the config rather than opening the hole quietly | Fowler |

## 5 - Row #4 - The reader tolerates both shapes

- **Scope:** `load_published` reads the flat `state/published.csv` **and** any `state/published/<YYYY-MM>.csv` shard, and returns the union with the earliest date per address. No writer changes. No behaviour changes. This row exists so that rows 5 and 6 cannot lose a row.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** four arms over built fixtures - flat file only, shards only, both holding disjoint addresses, and both holding the same address on different dates. The fourth arm returns the earlier date. A fifth arm proves the refusal below.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **No glob.** The shard enumerator lists `state/published/` and accepts a stem only if it matches `\d{4}-\d{2}`. Anything else raises rather than being skipped - a file nobody can explain in a state directory is a fault, and silently ignoring it is how a reader starts missing rows | Owner, 2026-09-07 |
| 2 | The directory gets its own name, `state/published/`, beside the flat file rather than replacing it in place. `telemetry_aggregate_path` records why a shard directory is never shared: a reader that enumerates a directory reads every file it finds as that directory's shape | [ledger.py](../backend/idhazh/ledger.py) |
| 3 | A missing directory and a missing flat file both mean "no history", which is what a fresh clone has. Neither is an error | [ledger.py](../backend/idhazh/ledger.py) module docstring |

## 6 - Row #5 - The writer routes by month

- **Scope:** `append_published` takes a date and appends to `state/published/<YYYY-MM>.csv`, exactly as `append_seen` does. The flat file is no longer written and is still read. `published_path` gains a date parameter; `published_relpath` is added to match every other partitioned collection.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/cli.py`
  - `.gitattributes`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_workflows.py`
  - `backend/tests/rebuild_day.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, plus `backend/tests/test_workflows.py` run directly. CI - full suite.
- **Oracle:** a run on `2026-09-07` writes `state/published/2026-09.csv` and touches no other file; a run on `2026-10-01` writes `2026-10.csv` and leaves September byte-identical. The workflow's `REFRESH_PATHS` and its mirror in `test_workflows.py` name `state/published` and both are asserted equal.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`.gitattributes` gets an explicit line for `state/published/*.csv`**, not the existing `state/**/*.csv` catch-all. The catch-all would already cover it, and that is the problem: a merge rule a new collection inherits without anyone choosing it is the same defect as a growing cost nobody chose | Owner, 2026-09-07 |
| 2 | `merge=union` is correct for these shards for the reason the existing comment gives - the rows are independent and the reader keeps the earliest of two. That reason is restated at the new line rather than assumed from the neighbour | Fowler |
| 3 | `REFRESH_PATHS` names the directory `state/published`, which is what the other partitioned ledgers already do (`state/scores`, `state/item-health`). `test_workflows.py` mirrors the literal and reds in CI if the two drift - move both in one commit | Fowler |
| 4 | A run whose date falls in a closed month performs a correction, which is the same case `append_seen` already handles and the freeze rule already permits | [month-partitions.md](../docs/concepts/month-partitions.md) |

## 7 - Row #6 - The one-shot split

- **Scope:** `backend/utilities/split_published_ledger.py` reads the flat file, writes every row into its month shard, verifies, and removes the flat file. Modelled on `migrate_published_ledger.py`, which is the worked precedent.
- **Files touched:**
  - `backend/utilities/split_published_ledger.py` (new)
  - `state/published.csv` (removed)
  - `state/published/2026-08.csv`, `state/published/2026-09.csv` (new)
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite. **Plus a reconciliation the utility prints and a person reads.**
- **Oracle:** before and after, `load_published` over the real `state/` returns a mapping with identical keys and identical values. The utility prints the row count in, the row count out, the shard count and the mapping digest, and refuses to remove the flat file unless in equals out.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This runs when no scheduled digest is in flight**, as a deliberate act by a person. `merge=union` is a content driver and cannot resolve a delete against a modify, so a split racing a running job conflicts, burns the retry budget in `commit-and-push.sh`, and loses the whole day's push | Fowler |
| 2 | The race is survivable rather than merely avoided, and that is why row 4 came first: if the flat file returns through a merge, the reader still reads it and no address is lost. The next split removes it again. A cutover whose failure mode is redundancy rather than loss is the only kind worth running against a live schedule | Fowler |
| 3 | Rows are copied, never rewritten. Same cells, same order, same bytes - only the file they live in changes. The `version` cell travels with the row | Section 11 |
| 4 | The utility stays committed after it runs. `migrate_published_ledger.py` set that precedent: a one-shot conversion is a committed artefact so a person with an old checkout can run it | [month-partitions.md](../docs/concepts/month-partitions.md) |

## 8 - Row #7 - The window, the fallback deleted, and the docs

- **Scope:** `load_published` gains `today` and `within_days`, drops the flat-file fallback, and reads the stems `shards_in_window` names when the window is finite. Every doc that describes the old shape moves in the same commit.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/seen.py`
  - `backend/idhazh/contracts/digest_day.py`
  - `schemas/published-row.schema.json`, `schemas/digest-day.schema.json`
  - `backend/tests/test_ledger.py`, `backend/tests/test_plan.py`, `backend/tests/test_discover.py`, `backend/tests/test_pipeline.py`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/sources/freshness.md`
  - `docs/architecture/publishing/layout.md`
  - `docs/architecture/sources/discovery.md`
  - `docs/concepts/month-partitions.md`
  - `docs/concepts/pipeline-loop.md`
  - `docs/concepts/evaluation.md`
  - `docs/how-to/run-the-pipeline.md`
  - `docs/reference/measurements.md`
  - `docs/reference/data-growth-audit.md`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** with the committed config, the mapping `load_published` returns is **equal cell-for-cell to what it returned before this plan started** - the guarantee is untouched, which is the whole point of shipping `-1`. A second arm sets the window to 120 over a built fixture spanning six months and proves the older shards are not opened, by counting file reads rather than by timing them.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`-1` enumerates; a finite window names stems.** The unbounded path lists the directory and validates every stem; the bounded path asks `shards_in_window` and opens only what it named. Two paths, two tests, neither one a glob | Owner, 2026-09-07 |
| 2 | `docs/architecture/sources/freshness.md` currently argues at length that this file must not shard, and lists the shard as a rejected alternative. That section is **rewritten to say what changed and why**, not deleted. A reversed decision whose reasoning vanishes is how the same argument gets had twice | CLAUDE.md section 4 |
| 3 | `docs/concepts/month-partitions.md` moves the published row out of "What is not partitioned" and into the partition table, and states the coupling to `seen_window_days` next to it | Carmack |
| 4 | `docs/reference/measurements.md` gains the 2026-09-07 numbers: 37.0 ms best, 69.0 ms worst, 32.0 ms spread, 500.9 B of peak a row, over 7,243 rows on an Intel Core i7-1265U | Rule #10 |
| 5 | `docs/archive/measurements-2026-08.md` is history and is **not** edited | Fowler |

## 9 - Row #8 - The eval writer stops reading every shard

- **Scope:** `evals.writer.append` builds `recorded_observations` before it writes one row, and that set is the union of every live score shard and every archived month. Measured 2026-09-07: 5,870 KB over two shards, and the archive grows for ever by design because a digest is what survives a shard's deletion. The row that found this handed it back as "belongs to the Indexed State package"; this is that package's first slice.
- **Files touched:**
  - `backend/idhazh/evals/writer.py`
  - `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`
  - `backend/tests/test_evals.py`, `backend/tests/test_contracts.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, the contract drift gate. CI - full suite.
- **Oracle:** with `-1`, an append refuses exactly the observations it refuses today, including one whose only record is an archived digest. With a finite window over a built six-month fixture, the shards outside it are not opened - counted by file reads, not by timing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The archived half can never be windowed away.** A month past the full-grain window has no rows left, so the digest is the only record that its measurements happened. Dropping it would call every measurement in that month new the day the shard was deleted, which is the one thing the ledger promises it is not. So the knob bounds the **live shard** read only, and the archive is always read whole | [writer.py](../backend/idhazh/evals/writer.py) |
| 2 | That asymmetry is the reason this row exists rather than being folded into row 3. Two collections, one bounded and one not, behind one call - and the docstring is the only place that says so today | Fowler |

## 10 - Row #9 - Settlement touches the shards the run wrote

- **Scope:** `ledger.keyed_ledgers` globs every committed feed-health and item-health shard, and `drop_repeated_rows` rewrites each one, every time a push race triggers settlement. Measured 2026-09-07: 3,845 KB over four shards, and the shard count rises by two a month for ever.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/cli.py`
  - `backend/tests/test_ledger.py`, `backend/tests/test_workflows.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector, plus `backend/tests/test_workflows.py` run directly. CI - full suite.
- **Oracle:** the real-Git race tests still settle a duplicated row correctly, and a settlement after a run on `2026-09-07` opens no shard from an earlier month.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The window here is not a clock, it is **the months this run wrote to**. A run appends to its own date's shard and to nothing else, so a settlement that rewrites January is repairing damage no run in flight could have done | [month-partitions.md](../docs/concepts/month-partitions.md) freeze rule |
| 2 | The glob keeps its stem validation and gains a refusal: a file in the directory that is not a month stem raises rather than being skipped, matching row 4's rule | Owner, 2026-09-07 |
| 3 | This is the row most likely to be found wrong by the real-Git tests, so those run directly rather than through the selector | [agent-notes.md](../docs/reference/agent-notes.md) |

## 11 - Row #10 - Runtime counters answer about one run

- **Scope:** `ledger.load_runtime_counters(state_dir, *, run_id)` already asks about one run, then reads the whole lifetime file to find it. Measured 2026-09-07: 189 rows, 32 KB, growing by about 40 rows a day.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** the rows returned for a run are identical before and after, and the read streams - peak follows the run's own rows rather than the file, proved the way row 2 proves it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Stream, do not shard.** A `run_id` already names its date, so this read is bounded by construction the moment it stops materialising. Partitioning 32 KB would add a layout for no answer it does not already have | Carmack |
| 2 | This is the row that shows the rule is not "shard everything". The window a read declares can be one run, one day or one month, and the smallest honest one wins | Carmack |

## 12 - Row #11 - Fingerprints, and the bounds the rest declare

- **Scope:** `fingerprint.append_new` rebuilds every recorded identity before adding a few. It is 3 rows and 2.4 KB today, so this row is mostly the second half: write down, next to each read the inventory defers, what bounds it and why a window is not the answer yet.
- **Files touched:**
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/assemble.py`, `backend/idhazh/retention.py`, `backend/idhazh/cli.py` (comments only, at the four deferred walks)
  - `backend/tests/test_fingerprint.py`
- **Acceptance gates:** local - `ruff`, `mypy --strict`, the shared test selector. CI - full suite.
- **Oracle:** a repeated identity is still refused, and each of the four deferred walks carries one line naming what it reads, how the cost grows, and which audit finding owns it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four walks over the published tree - `site_size`, the two retention walks, and `validate_days` - are **not** converted here. They are audit findings 16 to 19 and they belong with an artefact inventory, which is a different design. What this row owes them is the sentence Rule #12's escape hatch requires, so a reviewer can see the cost was chosen | Rule #12 |
| 2 | Three rows in a lifetime file is not a growth problem, and saying so plainly is worth more than converting it. The change here is that the read declares its window; the value it declares is `-1` and the reason is written beside it | Carmack |

## 13 - Row #12 - The rule gets its concept doc

- **Scope:** `docs/concepts/growing-reads.md` - the rule, the inventory, the three tiers, and how `-1` relates to Rule #12's escape hatch. Every row above cites it; it is written last so it describes what shipped rather than what was hoped for.
- **Files touched:**
  - `docs/concepts/growing-reads.md` (new)
  - `docs/architecture/contracts/schemas.md`
  - `docs/concepts/month-partitions.md`
  - `CLAUDE.md` (Rule #12's design rationale gains one paragraph)
  - `docs/reference/documentation-structure.md`
- **Acceptance gates:** local - none beyond the doc checks; this row changes no application code. CI - full suite.
- **Oracle:** every read named in the inventory appears in the doc with its window or its stated bound, and the count in the doc matches the count in the code. A person reading only that page can answer "does this read need a window" for a collection invented tomorrow.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A property, not a list.** The doc states the question - does this read cost more when a run appended more - and the inventory is an example table underneath it, explicitly marked as of a date. The archive-guard deleted on 2026-09-06 failed precisely because it was a list of paths pretending to be a rule | [CLAUDE.md](../CLAUDE.md) Rule #12 design rationale |
| 2 | It goes in `docs/concepts/`, beside [month-partitions.md](../docs/concepts/month-partitions.md), because it is the same altitude: month-partitions says what a layout obliges a writer to do, this says what a growing collection obliges a reader to declare | [documentation-structure.md](../docs/reference/documentation-structure.md) |
| 3 | CLAUDE.md gains a paragraph rather than a new rule. Rule #12 already forbids the growing cost nobody chose; this only says where the choosing is now written down | Owner, 2026-09-07 |

## What this plan does not fix

Stated rather than left implied, because the next person to read the audit will look for these.

- **No finding is closed by shipping `-1`.** Every read here still opens everything it opened before. What lands is the layout, the knob and the declaration. What closes a finding is a person setting a finite value on evidence, and that is deliberately outside this plan.
- **Four walks over the published tree are deferred**, not solved: `site_size`, both retention walks, and `validate_days`. They need an artefact inventory, which is a different design. Row 11 gives each the sentence Rule #12 requires so the cost is visibly chosen.
- **The lookup key is still not the partition key** for `published.csv`. Fowler's objection stands. A `url_key`-keyed index remains the answer if this ever becomes a measured cost - and after row 2, it very likely will not.
- **Nothing is ever pruned.** Twelve files a year for the published ledger, kept for ever. That is the correct trade and it means a window buys read time, never bytes.
- **The frontend and the browser are untouched.** Every read there is ranks 1 and 10 of the audit and belongs to [the constant-cost plan](20260906-constant-cost-reads-plan.md).

## See also

- [../docs/reference/data-growth-audit.md](../docs/reference/data-growth-audit.md) - finding 1, and the Indexed State package this plan takes a slice of.
- [../docs/concepts/month-partitions.md](../docs/concepts/month-partitions.md) - the pattern, the freeze rule, and the four cases an append-only layout gets wrong.
- [../docs/architecture/sources/freshness.md](../docs/architecture/sources/freshness.md) - why publishing twice is prevented by a record rather than a window.
- [20260906-constant-cost-reads-plan.md](20260906-constant-cost-reads-plan.md) - ranks 1 and 10 of the same audit, in flight.
