# Plan 56 - Every summary-quality row is kept, packed by year, and named for what it holds

**Last Updated**: 2026-10-01

**Level**: 5 (CLAUDE.md section 6). It deletes a persisted contract, adds a period to the saved file format, and renames a committed ledger. The person's rulings below are the design consultation; the ESCALATE triggers name what still stops a worker.

**Status**: rows 1 to 5 and 7 are done. The ledger is `summary-quality-evals` and its declaration sets its year-packing wait (R6). Each browser query reads a year file under a fresh address and releases its engine registration afterward. The published-year floor is removed; the declaration's own minimum still applies. The ID files are settled a month at a time from the first upkeep wake after 2026-10-02. Row 6 checks the live site once plan 51 publishes its first `.parquet`.

**Chain** (CLAUDE.md section 0d). **Intent**: the person's rulings of 2026-09-30, section 0. **Contract**: `backend/idhazh/contracts/` and the pages each row names. **Code**: the six rows.

Execute per [docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md). Running pool of two. Settle a design question by asking Fowler and Carmack in parallel. Merge by hand on green CI (GitHub refuses auto-merge here).

## Execution handover (zero-context cold start)

```text
You are the OWNER of TODO/20260930-56-summary-quality-evals-plan.md. Execution is
AUTHORIZED (the person, 2026-09-30). Read CLAUDE.md, docs/how-to/execute-a-plan.md,
docs/how-to/ship-a-pr.md and docs/how-to/run-the-gates.md, then this plan's section 0
and section 1, and each row just before you dispatch it.

Rows 1 to 5 and 7 are done. The person authorized plan 51's owner on 2026-10-01 to
deliver row 7 from a separate branch, p51-prerequisite-fresh-year-reads, without
changing the original p56r7 checkout. Do not deliver the original branch again.
Row 6 waits for plan 51's row 3 to publish the site's first .parquet. Plan 51's
PR #1169 now uses summary-quality-evals and copies all three indexes; #1177 has
merged. Merging
main into a branch older than row 3 takes `git -c merge.directoryRenames=false merge`.
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
| R5 | **Row 2 merges as built, and row 4 follows.** Trigger 4 fired: the browser downloads a whole file, so one month read out of a year file costs 11.97 times that month's own file. Until row 4 lands, a ledger the site reads packs a year only 367 days after it ends, so no console read reaches a year file. Row 4 makes the browser fetch only the byte ranges it needs - measured at 1.03 times the month file outside a browser - and then removes that floor | Holding row 2 until the browser reads byte ranges |
| R6 | **How long a ledger waits before it packs a finished year is a value in that ledger's own declaration, `monthly_keep_days` in `config/gardener/compact-<ledger>.json`, never a number in code. The eval ledger waits 93 days.** Code keeps only the loader's check that the value can take effect: at least `daily_keep_days` plus 32 days, 77 with today's `daily_keep_days` of 45, because no year packs before its next January is absorbed | The 77 days R5 named as the wait, which is only the smallest value the loader accepts |
| R7 | **The door reads each year file under an address the browser has not cached, so no request names an ETag from before a deploy, and then the 367-day floor on a published ledger goes (option A3, 2026-10-01).** The 367 is not a setting: it is the console's widest span, `console.max_window_days` 366, plus `compact_after_days` 1, and lowering the first would cut the console and the telemetry it publishes to the same span. The accepted cost: a page that reads the same year file twice fetches it twice | Keeping the floor, or removing it and letting a page open across a deploy download a whole year file |

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
5. Row 4's measurement, in a real browser: reading one month out of a year file by byte ranges costs more than twice the bytes of that month's own file, or any GET for the year file is answered with 200 rather than 206, or a console panel reading it that way draws later on a throttled connection than it does reading the whole month file today. Row 6's check: GitHub Pages serves a `.parquet` file compressed, so a byte range would count from the compressed body.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The score month summary is retired, and no eval row is ever deleted | - | A | DONE | p56r1 | #1170 | p56-r1-worker |
| 2 | The shared packing gains a year period | - | A | DONE | p56r2 | #1172 | p56-r2-worker |
| 3 | The eval ledger becomes `summary-quality-evals` | 1 | B | DONE | p56r3 | #1179 | p56-r3-worker |
| 4 | The browser reads a year file by byte ranges | 2 | B | DONE | p56r4 | #1178 | p56-r4-worker |
| 5 | The eval ledger's ID files are packed a month at a time | 3 | C | DONE | p56r5 | #1180 | p56-r5-worker |
| 6 | The live site is checked to serve a `.parquet` byte range uncompressed | 4, plan 51 row 3 | C | DONE | p56r6 | - | p56-owner |
| 7 | A year file is read under an address no earlier read used, and a published ledger's declaration sets its own wait | 4 | C | DONE | p51prereq | #1182 | p51-owner |

## 2. Deviations and rulings to date

| # | Row | The plan said | What is true, and why | Authority |
| --- | --- | --- | --- | --- |
| 1 | 2 | Trigger 4 stops row 2 | It fired at 11.97 times the month file, because the browser downloads a whole file. Row 2 merged as built, a published ledger waits 367 days for its year to pack, and row 4 moves the browser to byte ranges | The person, R5 |
| 2 | 2 | A year file sits at `yearly/<YYYY>.parquet` | It sits at `yearly/<YYYY>/<YYYY>.parquet`. Plan 50's row 14 made the upkeep checkout fetch a watermark together with every file beside it, so a year file beside the year watermark would be downloaded on every wake. No year file existed, so nothing moved on disk | Plan owner, forced by #1173 |
| 3 | 2 | `compact-scores.json` turns year packing on | It does not. Row 3 renames that file, so the switch is written once, in `compact-summary-quality-evals.json` | Row 2 worker |
| 4 | 3, 4 | A published ledger's year waits 77 days once row 4 lands | Each ledger's declaration sets its own wait, and the eval ledger's is 93 days. Row 3 writes it; row 4 removes the 367-day floor that would refuse it on a published ledger | The person, R6 |
| 5 | 3, 5 | One row renames the ledger and stops the ID files growing | Two rows. Row 3 renames and moves data, needs the stricter merge window, and is the part plan 51's open pull requests collide with. Row 5 then writes the ID files' packing once, under the final names | Plan owner, on Fowler's ruling at dispatch |
| 6 | 5 | The ID files are packed by month, made a packed ledger, or read from the eval rows | Packed a month at a time by the closed-day fold, which is already live by decision, so no `dry_run` moves (trigger 3). Carmack preferred reading the IDs from the eval rows' key columns: no second copy, but it stops the growth only once plan 57's row 1 switches this ledger's packing live | Plan owner, on Fowler's ruling at dispatch |
| 7 | 4 | The engine's seal must admit the registered address | `main` has no seal. Plan 55 ruled the browser's content policy is the boundary, so there is nothing to keep | Plan owner, from the dispatch check |
| 8 | 4, 6 | Measure with `vite preview`, and check the live site in row 4 | `vite preview` gzips a `.parquet` it has no type for and cannot slow only the data files, so the spec runs its own small server. The live site serves no `.parquet` until plan 51's row 3 publishes one, so that check is row 6. Waiting costs nothing: no year file can exist before 2027-04-04, 93 whole days after 2026 ends, and only once packing is live | Plan owner, on Carmack's ruling at dispatch |
| 9 | 4, 7 | When the measurement holds, row 4 removes the published floor | Trigger 5 fired on a page that holds part of a year file across a deploy: the browser asks for the next part naming the ETag it kept, and Pages answers an ETag it no longer serves with 200 and the whole file (measured on the live site; every file in a deploy carries that deploy's time, so an unchanged file gets a new ETag). Row 4 merged the range reads and kept the floor. Removing it is row 7, after the person rules | Plan owner, on trigger 5 |
| 10 | 4 | Month files move to ranges if the measurement shows a panel draws sooner | One panel drew sooner, 9.5 s against 15.2 s on slow 4G, but a page draws several panels from one month file and no page on `main` calls the door yet. Month files stay whole until a page with its real panels is measured | Plan owner, on the row 4 worker's finding |
| 11 | 3 | 19 raw, 59 compact and 78 ID files move, and a run started before the merge lands its rows in the old folder | 24 raw data files, 59 compact files and 83 ID files moved first, and 8 more after `main` moved. A run started before the merge lands nothing: its push stops at git's folder-rename conflict. Merging `main` into a branch older than the rename takes `git -c merge.directoryRenames=false merge` (`docs/architecture/contracts/persistence.md`) | Row 3 worker |

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

- **Scope (R3).** The compaction in `backend/idhazh/gardener/tasks/` (`compaction.py`, `_compact_tree.py`, `_monthly_period.py`, `_daily_period.py`) gains a third period. When a year is done, its month files are packed into `state/compact/<ledger>/yearly/<YYYY>/<YYYY>.parquet`, the yearly index and watermark are written, and the month files are deleted, in that order, so a pass that dies part way loses nothing. It is written once and serves every ledger; a declaration turns it on.
- **Contract changes:** `Period` in `backend/idhazh/contracts/file_envelope.py` gains `yearly`; the index and watermark shapes in `backend/idhazh/contracts/ledger_index.py` cover it; the path builders in `backend/idhazh/ledger/paths.py` build it; the compaction policy in `backend/idhazh/contracts/knobs/gardener.py` gains the opt-in and its timing. Version stamps and changelog entries where CLAUDE.md section 11 asks for them.
- **The browser's readers** learn year files: `COMPACT_PERIODS` in `frontend/src/lib/data/compact-index.ts`, `slice-reader.ts` and `ledger-reach.ts`, with the tests that bind the frontend copy to the contracts.
- **Measure (ESCALATE trigger 4):** what reading one month out of a year file costs the browser, against reading that month's own file. A year file written with one row group per month is the design to test first.
- **Opt-in:** `config/gardener/compact-scores.json` turns year packing on. No other ledger does.
- **Design questions for dispatch (Fowler and Carmack):** the knob's name and shape; when a year counts as done; whether month files still honour `monthly_window` for a ledger that has not opted in (they must, unchanged).
- **Acceptance gates:** `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/contracts backend/tests/ledger`, and the frontend logic tests for the readers. CI runs the full suite.
- **Oracle:** over a fixture ledger with a whole finished year of month files, one pass writes the year file, and every row the month files held reads back from it; a second pass changes nothing; a ledger that has not opted in keeps its month files exactly as before.

### Row #3 - The eval ledger becomes `summary-quality-evals`

- **Scope (R2).** `LedgerName.SCORES` becomes `LedgerName.SUMMARY_QUALITY_EVALS`, value `summary-quality-evals`; the registry refuses a member not spelled from its value (`contracts/ledgers.py` `_every_member_is_named_for_its_place`). With it move `state/raw/<name>/`, `state/compact/<name>/`, its entry in `config/ledgers.json`, `config/gardener/compact-scores.json` (to `compact-summary-quality-evals.json`), the code that names it (about 40 files), 31 test files and about 65 docs. Every committed file moves, and the migration reads every row back cell for cell before it deletes an old file (ESCALATE trigger 2).
- **The ID folder and its task (Fowler, at dispatch).** `state/score-index/` becomes `state/summary-quality-evals-index/`, with the member `LedgerName.SUMMARY_QUALITY_EVALS_INDEX` and its own family in `config/ledgers.json`. The retention task `config/gardener/scores.json` and `backend/idhazh/gardener/tasks/scores.py` become `summary-quality-evals-index.json` and `summary_quality_evals_index.py`, because the registry pairs a declaration with its module by name. `stages/rebuild_score_index.py` and the `rebuild-score-index` command follow the folder name. Kept: `contracts/observation_index.py` and `ObservationIndexRow` (docstring paths only), `EvalRow`, and `backend/utilities/reband_scores.py`, where "scores" means the numbers.
- **The migration rewrites every file, and no reader accepts the old name (Fowler).** Five saved shapes check the name against the closed list: the file footer, every row's `ledger` cell, the raw day listing, the compact index and the watermark. An alias would be a second registry entry that nothing ever rewrites while every compaction is dry, and old code writing after the merge writes to folders the new build never opens anyway. `unit_id` hashes the ledger name, yet every file keeps its `unit_id`, `file_id`, `written_at_ms` and `attempt`: the reader settles by them, compact rows carry no `producer` to recompute one from, and a re-run of a run started before the rename computes the old id.
  - What it rewrites: 19 raw and 59 compact parquet files (footer `ledger`, every row's `ledger` cell, footer `content_sha256`); the 59 raw day listings and the watermark (`ledger`); the daily compact index (`ledger`, and every entry's `bytes`). It moves the 78 ID files byte for byte, and moves whatever else the old folders hold when it runs, such as an index a later pull request adds.
  - How it proves: the four passes of `backend/utilities/migrate_to_parquet.py` - read everything, write everything, read everything back through the new build's own readers, then delete. Exit 1 deletes nothing, and a second run writes nothing. The read-back requires the same rows in the same order, every cell equal except `ledger`, every footer key equal except `ledger`, `content_sha256` and `writer_version`, and the ledger's settled rows and `recorded_observations` equal before and after.
- **Traps named at dispatch:**
  - The new build refuses `"scores"` in `persist.load_stored`, `FileEnvelope.from_metadata` and `raw_files._held`, so the first read opens the parquet container directly and swaps the name before validation.
  - Refiling through `ledger.persist` stamps a new identity and `unit_id` on every row: add one write function in `backend/idhazh/ledger/persist.py` that keeps the footer and every identity cell and changes only the ledger name.
  - The task name `"scores"` is typed as plain text in five places: `_CONSOLE_READS` in `backend/idhazh/config.py`, where a miss fails silently; `LIVE_BY_DECISION`; the `"scores"` case in `backend/tests/contracts/test_gardener_config.py`; `tests/fixtures/gardener/garden/scores.json`; `tests/fixtures/gardener/prune-oracle/removals.json`. Rename all five and change nothing else about them.
  - `backend/utilities/migrate_to_parquet.py` `csv_root` builds the old CSV folder from the member's value. Pin `"scores"` there until 2026-10-30, the end of GitHub's 30-day re-run window after #1166; the tool may go after that.
  - A digest run started before the merge stages all of `state` and lands its rows in `state/raw/scores/`, and a gardener shard computed before it can write `state/score-index/` back. Run the migration again after any such run, for 30 days after the merge, because a GitHub re-run runs the original commit.
- **Build order (Fowler, at dispatch).** One mechanical commit renames the code, one moves the data, and the last adds the 93 days below, so a conflict is settled by running the rename and the migration again on the merged tree. `config/idhazh.json` is not touched: `main` does not name the ledger there, and both of #1169's entries fail loudly under the old name.
- **Year packing (R3, R6):** the renamed `config/gardener/compact-summary-quality-evals.json` sets `"monthly_keep_days": 93`, the switch row 2 left for this row (deviation 3). The number lives there and nowhere in code. `ledger.published` does not name the ledger on `main`, so the 367-day floor for a published ledger does not apply. If plan 51's #1169 publishes it first, that floor refuses 93 until row 4 removes it, and this commit then waits for row 4.
- **Merge window:** the news run writes these rows every run, so this row merges as plan 50's row 9 did: no `digest.yml` or `idhazh-gardener.yml` run queued or running, and the migration run again just before the merge.
- **Acceptance gates:** as row 1, plus `backend/tests/ledger backend/tests/pipeline backend/tests/test_evals.py`, `svelte-check`, and the frontend specs the shared selector names for every file the rename touches.
- **Oracle:** every row the old folders held reads back from the new ones; no committed path under `state/` contains `/scores/` or `score-index`; the dedupe finds every measurement it found before the move.

### Row #4 - The browser reads a year file by byte ranges

- **Split (deviation 9).** Trigger 5 fired on a page that reads a year file across a deploy, so this row merged the range reads and kept the published floor. Removing the floor is row 7.
- **Scope (R5).** The query door fetches every compact file whole and hands the bytes to the engine (`registerFileBuffer` in `browserEngine`, `frontend/src/lib/data/engine.ts`). A year file is instead registered by its address, so the engine asks the host only for the byte ranges a panel's query needs: the footer, then the row groups of the months asked for. A year file holds one row group per month, so one month's rows are one contiguous range. Day files stay fetched whole. Month files are measured as a third case, and move to ranges only if that measurement shows a panel draws sooner.
- **The call (Carmack, at dispatch; MEASURED in Node on the browser's own engine file).** `db.open({ filesystem: { forceFullHTTPReads: false } })` before `connect()`, then `db.registerFileURL(name, url, DuckDBDataProtocol.HTTP, false)`. The default `forceFullHTTPReads` downloads the whole file in one plain GET and never sends a `Range`. `allowFullHTTPReads` stays on, because Pages answers a `HEAD` carrying a `Range` with 200 and the full length. directIO stays off, so the engine keeps its own block cache: a repeat query made 0 requests. `url` is absolute (`new URL(..., location.href)`), because a `blob:` worker cannot resolve a relative address, and the door builds it from the index path, never from fetched text.
- **What has to keep working:**
  - The build-time reader (`nodeEngine`, used by `frontend/src/lib/server/ledger-disk.ts`) has no HTTP reader and keeps registering whole files from disk, so ranges are browser-only.
  - A range is never read against a different file than the one its footer came from. The registered name is minted per path and version, as the door's cache key already is, because Pages ignores a query string (the same bytes and ETag for `?v=a` and `?v=b`, MEASURED). After the first query over a year file, the size the engine opened (`db.globFiles(name)`, `fileSize`) must equal the index entry's `bytes`, or the panel draws unreachable. A year file is written once and never rewritten in place, and the query door's page says so.
  - `export const DATE_COLUMN = 'date';` stays, unchanged, in `slice-query.ts`, because `backend/tests/contracts/test_frontend_index_shapes.py` reads that line. No field is added to `CompactEntry`, which would be a saved-shape change.
- **Three ways the engine silently reads a whole file (Carmack):** the default `forceFullHTTPReads`; an opening 1-byte GET not answered with 206; and any read answered with 200, on every read. So the browser spec requires 206 on every GET for the year file.
- **Measure in a real browser (trigger 5).** Chromium through Playwright, against a small Node server the spec starts, not `vite preview`, which gzips a `.parquet` it has no type for and cannot slow only the data files. The server serves the built site and the year and month fixtures under `/state/`. It answers a ranged GET with 206 and a `HEAD` with 200, the full length and an ETag of mtime-size, as Pages does. It sends `Content-Type: application/vnd.apache.parquet` uncompressed, slows only `/state/` by 562.5 ms a response and 188,743 bytes a second (Lighthouse's slow-4G constants), and logs one line a request: method, path, `Range`, `Accept-Encoding`, `If-Range`, status and body bytes.
  - Runs: the month file fetched whole, the same month out of the year file by ranges, and the month file by ranges. A fresh browser context each run, alternated, three rounds, medians. The time runs from the door call to its rows, after the engine and its add-on have loaded once, because no panel on `main` calls `slice()` yet. The columns are a real panel's list: all 42 columns by ranges read 2.31 times the month file (ESTIMATE, emulated) and would fire trigger 5.
  - Pass: the year file's body bytes at most twice the month file's; every GET for the year file carried a `Range` and got 206 with no `Content-Encoding`; the median by ranges no later than the median for the whole month file.
  - One more case: the year file's ETag changes but not its bytes between two queries, after the browser's cached copy has gone stale. It passes if every GET is still 206. Every Pages deploy gives every file a new ETag, and an `If-Range` against a changed ETag may be answered with the whole file (ESTIMATE).
- **No flag (Fowler, at dispatch).** Range reads land with no flag: while the floor stands, no console read of a published ledger reaches a year file, and a flag would keep two ways to fetch a file.
- **Measured (#1178, `docs/reference/benchmarks/what-a-month-out-of-a-year-file-costs.md`):** June out of the 29.8 MB year file by ranges, with the model-change panel's 10 columns on slow 4G, took 243,046 bytes in 13 requests and drew in 11.0 s, against 2,490,452 bytes and 15.2 s for the month file whole. Every GET was answered 206. The stale-ETag case fired trigger 5 (deviation 9).
- **Files touched:** `frontend/src/lib/data/engine.ts`, `slice-query.ts`, `slice-reader.ts`, `page-keeper.ts` and `fetched-bytes.ts`; `frontend/scripts/test-groups.ts`; `frontend/tests/ledger-door.spec.ts`, `frontend/tests/ledger-ranges.spec.ts` and its host and page under `frontend/tests/support/`; `backend/idhazh/config.py` (the floor's reason only); the query door's page, the benchmark page and `docs/concepts/config/idhazh-gardener.md`.
- **Acceptance gates:** `ruff check .`, `mypy backend`, `pytest backend/tests/contracts`, `svelte-check`, the logic and browser specs the shared selector names, and the browser smoke of the console (CLAUDE.md section 12).
- **Oracle:** a panel over a month held in the year fixture draws the same rows by ranges as it drew from the whole file, and every request it made for the year file names a byte range.

### Row #5 - The eval ledger's ID files are packed a month at a time

- **Scope (R4, Fowler at dispatch).** The closed-day fold (`backend/idhazh/gardener/closed_day_fold.py` `fold`), which already runs live, gains a month step the ID task opts into in its `fold` block (`FoldPolicy` in `backend/idhazh/contracts/knobs/gardener.py`). Once a month's last day is closed, the fold settles every file of that month into `<tree>/<YYYY>/<MM>/settled.csv` and deletes what it read; a day that arrives late is folded in at the next wake. It runs under the fold switch that is already live by decision, and R4 joins that switch's reason in `LIVE_BY_DECISION`. No `dry_run` moves (trigger 3).
- **What each part changes to:** the digest writer (`evals.writer.file_measurements`) is unchanged, one file a job an open day. The dedupe reader (`evals.writer.indexed_observations`) reads month files and day files alike. The repair command (`evals.writer.rebuild_index`, `_indexed_on`) compares a folded month by month, because an ID row carries no date. The operator prune (`telemetry/prune.py` `_TARGET_LEDGERS`) drops the ID tree: a month file cannot serve a delete of a range of days, and R4 deletes no ID. Its entry in `docs/concepts/growing-reads.md` becomes one file per closed month plus the open month's days.
- **Trap named at dispatch:** both tree walkers refuse a file outside a `YYYY/MM/DD/` folder, the fold's own `_closed_days` included (`backend/idhazh/day_shards.py` `shard_files`, `_one_day`, `date_of`; `backend/idhazh/gardener/named_trees.py` `shard_files`, `_refuse_a_shard`). `backend/tests/gardener/test_named_trees.py` requires the two to agree, so they change together.
- **What it costs (Carmack):** every digest run reads one ID file a day today, 365 / 1,095 / 3,650 files at 1 / 3 / 10 years at about 16 ms a file (MEASURED rate). After this row it reads one a month plus the open month's days, about 43 / 67 / 151 (ESTIMATE). The bytes stay every measurement ever taken, about 76 bytes each, as R4 requires. A year step can follow later with no migration.
- **Files touched (expected):** the modules above; the ID task `backend/idhazh/gardener/tasks/summary_quality_evals_index.py` and its declaration `config/gardener/summary-quality-evals-index.json`; their tests; `docs/concepts/growing-reads.md`, `docs/architecture/publishing/idhazh-gardener.md`, `docs/concepts/config/idhazh-gardener.md`; this plan's Reckoner line.
- **Merge window:** no `idhazh-gardener.yml` run queued or running.
- **Acceptance gates:** `ruff check .`, `mypy backend`, `pytest backend/tests/gardener backend/tests/retention backend/tests/contracts backend/tests/pipeline backend/tests/test_evals.py`, plus every test module the row touches. CI runs the full suite.
- **Oracle:** over a fixture ID tree with a closed month and an open month, one fold writes `<YYYY>/<MM>/settled.csv` holding every ID the closed month's day files held and deletes those files; a second fold changes nothing; `indexed_observations` returns the same set before and after; a late day of a folded month is folded in at the next pass with nothing lost.

### Row #6 - The live site is checked to serve a `.parquet` byte range uncompressed

- **Waits for** row 4, and for plan 51's row 3 (#1169) to publish the site's first `.parquet`. This plan publishes no file only for this check.
- **Scope (trigger 5's last clause).** Six requests against one published `.parquet`: a `HEAD` with `Range: bytes=0-`, a GET with `Range: bytes=0-0`, and a GET for a range in the middle of the file, each once with `Accept-Encoding: gzip` and once with `identity`. It passes if every GET answers 206 with no `Content-Encoding` and the `HEAD` answers the file's true length. The answers go into `docs/architecture/publishing/how-the-query-door-answers-a-panel.md` as a measured fact.
- **Why it can wait (Carmack, ESTIMATE):** mime-db marks `.parquet` not compressible, and a browser sends `Accept-Encoding: identity` with any `Range`. The dangerous case, measured on the live CSV: a `HEAD` carrying a `Range` that accepts gzip answers the compressed length. No year file can exist before 2027-04-04, and only once packing is live.
- **If it fails:** ESCALATE (trigger 5).
- **Files touched:** the page above; this plan's Reckoner line.
- **Oracle:** the six answers, recorded on that page.

### Row #7 - A year file is read under an address no earlier read used, and a published ledger's declaration sets its own wait

- **Scope (R7, R6).** Two parts in one pull request, because the floor exists only for the case the first part closes.
  1. **The door (R7).** Each query over a year file registers it under a name and an address no earlier read used. The address the door builds today, `?v=<rows>-<bytes>`, gains a part unique to that one read, made when the read starts. Pages ignores the query string, so the bytes are the same, while the browser keeps its pieces per address, so a new address holds no piece and the browser sends no `If-Range`. The part is unique across page loads too, never a counter that restarts with each page, or a page opened within Pages' `max-age=600` of an earlier one would share its pieces. The engine drops the name (`dropFile`) when the read ends. Day and month files are unchanged, and the size guard (the engine's `fileSize` equals the entry's `bytes`) stays.
  2. **The floor (R6).** The published floor in `backend/idhazh/config.py` goes (`_refuse_a_published_reach_that_grows_or_falls_short` requires `monthly_keep_days` of at least `console.max_window_days` plus `compact_after_days`, 367 days today). A published ledger then waits what its own declaration says, as every ledger does, and the loader's one remaining check is the knob's own: at least `daily_keep_days` plus 32 days. Its rule that a published ledger keeping its months forever must pack years stays. Its tests in `backend/tests/contracts/test_gardener_config.py` change with it, and no test pins 93: a published fixture ledger at the knob's minimum loads, and one day under it is refused.
- **Still not covered, and the docs say so:** a deploy that lands inside one read, between its first and last request, still sends that read the whole file. A read takes about 11 seconds on a slow mobile link and a deploy came about every 85 minutes (17 in the 24 hours to 2026-10-01 02:00 UTC), so about 1 read in 500 there (ESTIMATE), and fewer on a fast link.
- **The accepted cost (R7), measured:** a page that reads the same year file twice fetches its footer and row groups twice. Two reads of the same month on one page, bytes and time, go into `docs/reference/benchmarks/what-a-month-out-of-a-year-file-costs.md` beside the cases already there.
- **Tests:** in `frontend/tests/ledger-ranges.spec.ts`, the case "a year file whose ETag changed while the browser still holds part of it is still read by byte range" loses its expected-to-fail mark and passes. A second case: a new page, opened while the browser still holds fresh pieces from an earlier page and after the ETag changed, also gets only 206.
- **Files touched (expected):** `frontend/src/lib/data/engine.ts`, `page-keeper.ts` and `slice-reader.ts`, wherever the address and name are made; `frontend/tests/ledger-ranges.spec.ts`; `backend/idhazh/config.py`; `backend/tests/contracts/test_gardener_config.py`; `docs/architecture/publishing/how-the-query-door-answers-a-panel.md`; the benchmark page above; `docs/concepts/config/idhazh-gardener.md`; `docs/architecture/publishing/idhazh-gardener.md`; this plan's Reckoner line.
- **Merge window:** no `idhazh-gardener.yml` run queued or running, because the upkeep run reads `config.py`.
- **Acceptance gates:** `ruff check .`, `mypy`, `pytest backend/tests/contracts`, `svelte-check`, the logic specs and `ledger-ranges.spec.ts`, and the browser smoke of the console (CLAUDE.md section 12).
- **Oracle:** in the browser spec, after the ETag changes, every GET for the year file is answered 206 and none carries an `If-Range` naming an older ETag; a published fixture ledger whose declaration sets `monthly_keep_days` below 367 loads, and one below `daily_keep_days` plus 32 is still refused.

## Dependent plans

- [20260924-50-idhazh-gardener-plan.md](20260924-50-idhazh-gardener-plan.md): its row 15 is withdrawn by R1, and its open question on renaming `scores` is answered by R2. Its row 14 edits the gardener's file walkers beside rows 1 and 3 here.
- [20260924-51-console-fetches-and-draws-its-own-data-plan.md](20260924-51-console-fetches-and-draws-its-own-data-plan.md): its open #1169 publishes this ledger as `scores`, and its open #1177 writes `state/compact/scores/index/monthly.json`. Row 3 has landed, so both must name `summary-quality-evals`. On `main` the loader refuses a published ledger that keeps its months forever and packs no year, and it refuses a wait under 367 days until row 7 lands. So publishing this ledger needs row 7, or a declaration of at least 367 days. #1169's test helper `months_kept` also refuses a forever month window, which year packing makes bounded. Plan 51's owner decides how its rows take this in; this plan edits none of them.
- [20260930-57-upkeep-tasks-switch-on-plan.md](20260930-57-upkeep-tasks-switch-on-plan.md): its row 1 switches this ledger's packing live. Its deviation 2 already follows the rename if row 3 lands first.
- [20260926-52-fifty-panels-move-and-six-projections-go-plan.md](20260926-52-fifty-panels-move-and-six-projections-go-plan.md): its row 7 note on the `scores` rename is answered by R2.
- [20260918-36-summary-quality-autotune-plan.md](20260918-36-summary-quality-autotune-plan.md): keeps `state/summary-quality/` for its fitted thresholds.
