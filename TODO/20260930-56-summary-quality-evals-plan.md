# Plan 56 - Every summary-quality row is kept, packed by year, and named for what it holds

**Last Updated**: 2026-09-30

**Level**: 5 (CLAUDE.md section 6). It deletes a persisted contract, adds a period to the saved file format, and renames a committed ledger. The person's rulings below are the design consultation; the ESCALATE triggers name what still stops a worker.

**Status**: row 1 is done (#1170). Row 2 is built and merges as built (#1172), by the person's ruling R5 on trigger 4. Row 3 is next. Row 4, added by R5, makes the browser read only the byte ranges it needs, and then shortens the wait before a year a published ledger reads is packed.

**Chain** (CLAUDE.md section 0d). **Intent**: the person's rulings of 2026-09-30, section 0. **Contract**: `backend/idhazh/contracts/` and the pages each row names. **Code**: the three rows.

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Running pool of two. Settle a design question by asking Fowler and Carmack in parallel. Merge by hand on green CI (GitHub refuses auto-merge here).

## Execution handover (zero-context cold start)

```text
You are the OWNER of TODO/20260930-56-summary-quality-evals-plan.md. Execution is
AUTHORIZED (the person, 2026-09-30). Read CLAUDE.md, docs/how-to/execute-a-plan.md,
docs/how-to/ship-a-pr.md and docs/how-to/run-the-gates.md, then this plan's section 0
and section 1, and each row just before you dispatch it.

Rows 1 and 2 share no file and run side by side. Row 3 waits for row 1, and row 4 for row 2. Plan 50's
row 14 (the upkeep checkout fetches names) is in flight in another session and edits
the gardener's file walkers: whichever of the two merges second takes main in first.
Plan 50's row 15 (build the score month summary) is withdrawn by the ruling below.

Push with: git -c credential.helper= -c 'credential.helper=!gh auth git-credential'
push origin <branch>. Merge from outside the repository with gh pr merge <N> --repo
miztiik/yen-idhazh --squash --delete-branch, then confirm with gh pr view.
A worker commits and pushes the moment its gates pass, and measures after.
```

## 0. Operating contract

### The person's rulings, 2026-09-30

| # | Ruling | What it replaces |
| --- | --- | --- |
| R1 | **Every row of the eval ledger is kept for ever.** Nothing summarises a month of it and nothing deletes one of its rows. A chart that wants a monthly number computes it from the rows when it draws | The month summary under `state/score-archive/`, added 2026-09-03 by #382 to allow deleting rows older than 14 months, and plan 50's row 15, which would have rebuilt it |
| R2 | **The ledger `scores` becomes `summary-quality-evals`.** "scores" is one of seven ledger names with "score" in them and says nothing about what is scored | Plan 50's open question "Does `scores` become `summary-quality`?", and plan 52's row 7 note that it stays the owner's call. `summary-quality` alone is kept free for plan 36's fitted quality thresholds |
| R3 | **The shared packing gains a year period.** When a year is done, its month files are packed into one year file and then deleted, and no row is lost. It is written once, and a ledger turns it on in its own declaration | Month files deleted outright once they pass `monthly_window` |
| R4 | **The daily ID files stop growing by one file a day**, with no summary. The dedupe still sees every measurement ever taken | `evals.writer.indexed_observations`, declared unbounded in `docs/concepts/growing-reads.md` until a month summary landed |
| R5 | **Row 2 merges as built, and row 4 follows.** Trigger 4 fired: the browser downloads a whole file, so one month read out of a year file costs 11.97 times that month's own file. Until row 4 lands, a ledger the site reads packs a year only 367 days after it ends, so no console read reaches a year file. Row 4 makes the browser fetch only the byte ranges it needs - measured at 1.03 times the month file outside a browser - and then drops that wait to the 77 days every other ledger waits | Holding row 2 until the browser reads byte ranges |

### Hard scope

| In | Out, and what would bring it in |
| --- | --- |
| Retiring the month summary and its contract, builder, ledger entry and series | Turning any compaction live. Every `compact-*.json` keeps `dry_run: true`; switching one on is the person's call |
| A year period in the shared compaction, its indexes and watermark, and the browser's readers | Opting any ledger other than this one into year packing. One config line each, by the person |
| Renaming the ledger and migrating its committed files | Renaming `EvalRow` or other Python classes, unless Fowler rules it at row 3's dispatch |
| Stopping the ID files' growth | Changing what the dedupe counts as one measurement (`OBSERVATION_KEY`) |

### ESCALATE triggers

1. Any change that would delete a committed row of the eval ledger (R1 says none may).
2. A migration that cannot read every committed row back cell for cell before it deletes the old files.
3. Any `dry_run` moving from `true` to `false` on a compaction or retention task.
4. Row 2's measurement: reading one month out of a year file costs the browser more than twice what reading that month's own file costs today.
5. Row 4's measurement, in a real browser: reading one month out of a year file by byte ranges costs more than twice the bytes of that month's own file, or a console panel reading it that way draws later on a throttled connection than it does reading the whole month file today, or GitHub Pages serves a `.parquet` file compressed, so a byte range would count from the compressed body.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The score month summary is retired, and no eval row is ever deleted | - | A | DONE | p56r1 | #1170 | p56-r1-worker |
| 2 | The shared packing gains a year period | - | A | NOT STARTED | - | - | - |
| 3 | The eval ledger becomes `summary-quality-evals`, and its ID files stop growing | 1 | B | NOT STARTED | - | - | - |
| 4 | The browser reads a year file by byte ranges, and a published ledger's year waits 77 days | 2 | B | NOT STARTED | - | - | - |

## 2. Deviations and rulings to date

| # | Row | The plan said | What is true, and why | Authority |
| --- | --- | --- | --- | --- |

---

### Row #1 - The score month summary is retired, and no eval row is ever deleted

- **Scope (R1).** Delete the month summary and everything that exists only for it:
  - the contract `backend/idhazh/contracts/score_archive.py` and its export in `contracts/__init__.py`;
  - the builder `backend/idhazh/evals/archive.py`;
  - `LedgerName.SCORE_ARCHIVE`, the `score-archive` entry in `config/ledgers.json`, and the `archive` series in `config/gardener/scores.json` and in `_SERIES`, `_SUMMARY_SERIES` and `_CONSOLE_READS` in `backend/idhazh/config.py`;
  - the archive half of `evals.writer.recorded_observations`, which then reads the index alone;
  - every reader of an archive in `backend/utilities/` (`data_wrangler.py`, `grader_length_bias.py`, `label_queue.py`, `reband_scores.py`), `month_partition.py` and `retention.py`.
- **Keep** `DECILES` and `decile_of`: they move into `backend/idhazh/evals/labels.py`, their one remaining reader, and `test_labels.py` keeps passing unchanged.
- **The `scores` retention task deletes nothing.** Its window becomes `{"unit": "forever"}` with no `series`, like `span-rollup`, and its only live action stays the closed-day fold of the index days. **`compact-scores.json`'s `monthly_window` becomes forever**, so the compaction may pack but never drops a month. The floor checks in `config.py` that tied the two to the old 14-month series go with the series.
- **The removed knob's message** in `backend/idhazh/contracts/knobs/observability.py` (`scores_full_grain_months` pointing at `series.archive`) says the rows are kept for ever instead.
- **No migration.** `state/score-archive/` holds no file on `main`, so no payload of the retired contract exists (CLAUDE.md section 11 has nothing to read back).
- **Files touched (expected; the dispatch check confirms them):** the modules above; the tests that name the archive (`backend/tests/retention/test_score_ledger.py`, `test_evals.py`, `pipeline/test_eval_ledger.py`, `pipeline/test_publication_hook.py`, `contracts/test_ledger_registry.py`, `contracts/test_retention_knobs.py`, `contracts/_config.py`, `contracts/test_span_rollup.py`, `gardener/test_publish.py`, `gardener/test_shards.py`, `gardener/tasks/test_every_task_takes_what_its_pass_took.py`, `gardener/tasks/test_every_window_moved_unchanged.py`, `gardener/tasks/test_telemetry_aggregate_task.py`, `test_ledger_families.py`, `workflows/test_ledger_staging.py`); the docs that name it (`docs/architecture/contracts/ledger-registry.md`, `schemas.md`, `state-ledgers.md`, `docs/architecture/publishing/idhazh-gardener.md`, `layout.md`, `retention.md`, `docs/concepts/adaptive-pruning.md`, `config/idhazh-gardener.md`, `config/retention-ages.md`, `evaluation.md`, `growing-reads.md`, `partitions.md`); this plan's Reckoner line.
- **Design rationale** goes into `docs/concepts/evaluation.md` as a `## Design rationale` entry: why the rows are kept rather than summarised (R1), with the person's name and date.
- **Acceptance gates:** `ruff check .`, `mypy backend`, and `pytest` over the test modules above plus `backend/tests/contracts backend/tests/gardener backend/tests/retention`. CI runs the full suite.
- **Oracle:** `git grep -n -E "score_archive|ScoreArchive|SCORE_ARCHIVE|score-archive|archived_observations"` finds nothing outside `docs/archive/` and `TODO/`. Over a fixture index older than any window, the `scores` task selects no file to delete. `config/gardener/compact-scores.json` loads with `monthly_window` forever.
- **Merge window:** it edits `config/gardener/`, which the upkeep run reads, so it merges while no `idhazh-gardener.yml` run is queued or running.

### Row #2 - The shared packing gains a year period

- **Scope (R3).** The compaction in `backend/idhazh/gardener/tasks/` (`compaction.py`, `_compact_tree.py`, `_monthly_period.py`, `_daily_period.py`) gains a third period. When a year is done, its month files are packed into `state/compact/<ledger>/yearly/<YYYY>.parquet`, the yearly index and watermark are written, and the month files are deleted, in that order, so a pass that dies part way loses nothing. It is written once and serves every ledger; a declaration turns it on.
- **Contract changes:** `Period` in `backend/idhazh/contracts/file_envelope.py` gains `yearly`; the index and watermark shapes in `backend/idhazh/contracts/ledger_index.py` cover it; the path builders in `backend/idhazh/ledger/paths.py` build it; the compaction policy in `backend/idhazh/contracts/knobs/gardener.py` gains the opt-in and its timing. Version stamps and changelog entries where CLAUDE.md section 11 asks for them.
- **The browser's readers** learn year files: `COMPACT_PERIODS` in `frontend/src/lib/data/compact-index.ts`, `slice-reader.ts` and `ledger-reach.ts`, with the tests that bind the frontend copy to the contracts.
- **Measure (ESCALATE trigger 4):** what reading one month out of a year file costs the browser, against reading that month's own file. A year file written with one row group per month is the design to test first.
- **Opt-in:** `config/gardener/compact-scores.json` turns year packing on. No other ledger does.
- **Design questions for dispatch (Fowler and Carmack):** the knob's name and shape; when a year counts as done; whether month files still honour `monthly_window` for a ledger that has not opted in (they must, unchanged).
- **Acceptance gates:** `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/contracts backend/tests/ledger`, and the frontend logic tests for the readers. CI runs the full suite.
- **Oracle:** over a fixture ledger with a whole finished year of month files, one pass writes the year file, and every row the month files held reads back from it; a second pass changes nothing; a ledger that has not opted in keeps its month files exactly as before.

### Row #3 - The eval ledger becomes `summary-quality-evals`, and its ID files stop growing

- **Scope (R2, R4).** `LedgerName.SCORES` becomes `summary-quality-evals`: `state/raw/<name>/`, `state/compact/<name>/`, its entry in `config/ledgers.json`, `config/gardener/compact-<name>.json`, the code that names it (about 28 backend modules and 8 frontend files), and the docs. Every committed file moves, and the migration reads every row back cell for cell before it deletes an old file (ESCALATE trigger 2).
- **Design questions for dispatch (Fowler and Carmack):**
  1. Each committed file's envelope names its ledger. Is every file rewritten, or does the reader accept the old name for one release?
  2. Does `unit_id` include the ledger name? If so, every file is filed again under a new name.
  3. The ID files (R4): pack the index days into month files, make the index a ledger the shared packing bounds, or read the IDs straight from the packed rows. The last depends on the compaction being live, which is the person's switch (ESCALATE trigger 3).
  4. The ID folder `state/score-index/` takes the matching name, or goes.
- **Merge window:** the news run writes these rows every run, so this row merges as plan 50's row 9 did: no `digest.yml` or `idhazh-gardener.yml` run queued or running, and the migration run again just before the merge.
- **Acceptance gates:** as row 1, plus the frontend tests of every file the rename touches.
- **Oracle:** every row the old folders held reads back from the new ones; no committed path under `state/` contains `/scores/`; the dedupe finds every measurement it found before the move.

### Row #4 - The browser reads a year file by byte ranges, and a published ledger's year waits 77 days

- **Scope (R5).** The query door (`frontend/src/lib/data/slice-query.ts`) fetches every compact file whole and hands the bytes to the engine (`registerFileBuffer`). A year file is instead registered by its address, so the engine asks the host only for the byte ranges a panel's query needs: the footer, then the row groups of the months asked for. A year file holds one row group per month, so one month's rows are one contiguous range. Day and month files stay fetched whole unless the measurement says ranges pay for them too.
- **What has to keep working:** the engine's seal (`enable_external_access` off, `allowed_directories` naming what may be read) admits the registered address and nothing else. A year file changes only when a pass rewrites it, and a range is never read against a newer file than the one its footer came from; the index entry's rows and bytes are already the file's version (`dataVersion`).
- **Measure in a real browser (trigger 5).** In Chromium through Playwright, with the site served by a server that honours `Range` (for example `vite preview`), one console panel over one month: the bytes and requests of reading that month out of the year fixture by ranges, against fetching the month file whole, and the time to draw with the network throttled to a slow mobile profile. On the live site, one `.parquet` asked for with a range and `Accept-Encoding: gzip`: whether it comes back `206` with no `Content-Encoding`. `ledger.published` is empty today, so the live site may serve no `.parquet`; if it still serves none, ask the person before publishing a file only for this check.
- **When the measurement holds:** the published floor in `backend/idhazh/config.py` goes (`_refuse_a_published_reach_that_grows_or_falls_short` requires `monthly_keep_days` of at least `console.max_window_days` plus `compact_after_days`, 367 days today). A published ledger then waits what every ledger waits, `daily_keep_days` plus 32: 77 days with today's settings. Its tests in `backend/tests/contracts/test_gardener_config.py` change with it.
- **Design questions for dispatch (Fowler and Carmack):** whether day and month files move to ranges too; where the engine's ranges are cached, since the door's own cache holds whole files; how many requests one panel may make before a slow connection pays more than it saves.
- **Files touched (expected):** `frontend/src/lib/data/slice-query.ts`, `slice-reader.ts` and the engine setup beside them; `frontend/tests/ledger-door.spec.ts` and one browser spec that counts requests and bytes; `backend/idhazh/config.py`; `backend/tests/contracts/test_gardener_config.py`; `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/concepts/config/idhazh-gardener.md`; this plan's Reckoner line.
- **Acceptance gates:** `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`, `svelte-check`, the logic and browser specs the shared selector names, and the browser smoke of the console (CLAUDE.md section 12).
- **Oracle:** a panel over a month held in the year fixture draws the same rows by ranges as it drew from the whole file, and every request it made for the year file names a byte range; a published ledger declaring `monthly_keep_days` 77 loads.

## Dependent plans

- [20260924-50-idhazh-gardener-plan.md](20260924-50-idhazh-gardener-plan.md): its row 15 is withdrawn by R1, and its open question on renaming `scores` is answered by R2. Its row 14 edits the gardener's file walkers beside rows 1 and 3 here.
- [20260926-52-fifty-panels-move-and-six-projections-go-plan.md](20260926-52-fifty-panels-move-and-six-projections-go-plan.md): its row 7 note on the `scores` rename is answered by R2.
- [20260918-36-summary-quality-autotune-plan.md](20260918-36-summary-quality-autotune-plan.md): keeps `state/summary-quality/` for its fitted thresholds.
