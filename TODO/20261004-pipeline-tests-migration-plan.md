# Pipeline-test state nests under state/pipeline-tests, with a reusable migration tool

**Last Updated**: 2026-10-09
**Level**: 5 for the approved root design; 2 for the first tooling phase.
**Status**: DONE. Rows 1 to 5 shipped a layout this plan approved and row 5 committed, but it put `raw`/`compact` inside each trial root (`state/pipeline-tests/<case>/raw/...`) instead of tier first like every other ledger (`state/raw/<ledger>/...`). The user caught this 2026-10-09 and ordered a correction: tier stays the top segment, and the trial's own bench/case names splice in after it (`state/raw/pipeline-tests/<case>/...`). Section 7 carries the corrected design; rows 6 to 8 (#1443, #1438, #1465) replaced rows 2 to 5's root shape for raw/compact ledgers in code, config and committed data. Row 9 (#1478) moved the four traces to `state/trial-traces/pipeline-tests/<case>/`. The user then ordered row 10 to move those same JSONL files under `state/raw/traces/pipeline-tests/<case>/`; that is the current address. The pipeline-test raw/compact ledgers and traces are tier-first, while the trace files remain JSONL rather than ledger-door files.

## 0. Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Put every pipeline-test state tree under one parent, use raw and compact ledger files, preserve recorded values, and ship the migration commands as a tool later ledgers reuse. |
| A2 | Hard scope - in | Reusable preview, write, verify and retire operations; nested case roots; bounded readers; trial compaction; exact CSV conversion; producers, artifact validation, gardener consumers, fixtures and owning docs; deleting the four orphan trial span-rollup files (A4). |
| A3 | Chosen strategy | Fowler: extend the existing migration tool and compaction engine. Keep case identity in separate roots, not in changed writer envelopes. |
| A4 | Approved design | The user approved (2026-10-04) nested cases with both tiers and explicit trial compaction roots (C7, C8). The user ruled later the same day that span-rollup stays retired as #1189 retired it, with its producer, console reader, published folder, contract and registry entry: its eight orphan CSV files, left by runs that started before #1189 merged, are deleted unconverted (row 5 here and Plan 59), and no summary contract is restored. That ruling reverses the earlier approval to restore `SpanRollupRow`. Losing any other CSV cell is not approved (C11). |
| A5 | Execution | Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. The user authorized rows 2 to 5 on 2026-10-06. |
| A6 | First phase authorization | The user requested that the reusable tooling be built now. Its worker may change the migration utility, its focused helpers and tests, and its runbook. It must not move committed data. |
| A7 | ESCALATE triggers | Pause only for: a persisted-contract change other than the approved C4, C7 and C8 shapes; a change to `WriterIdentity`, `unit_id` or a settlement key; enabling expiry or shortening any retention; a ledger a trial root can commit that no declaration covers; a writer or gardener run queued or running at data cutover; a source cell that cannot be preserved. |
| A8 | Evidence | Plan 58 closed in pull request #1242. Its current implementation and [migration runbook](../docs/how-to/move-a-ledger-to-parquet.md), not the removed plan, are the reuse authority. |
| A9 | Local and CI gates | Inspect `npm --prefix frontend run test:changed -- --list`, then run the selected local checks and each row's focused oracle. Record inputs and results in the pull request description. CI runs full suites on each merge candidate; do not repeat an unchanged worker check. |
| A10 | Documentation rule | Update owning docs with their code phase. Run `python backend/utilities/doc_load.py` with every changed Markdown path before and after. Apply the split test to the page receiving material. |
| A11 | Searched names | Each row's Files touched holds the matches it edits from a whole-tree search for `pipeline-tests-`, `TRIAL_STATE_PREFIX`, `TRIAL_STATE`, `BENCH_TRIAL_STATE`, `trial_state_dirname`, `trial_case_dirname`, `_TRIAL_ROOT_PREFIX`, `trial_day`, `span-rollup` and `span_rollup`. No row edits these matches: the published folder `frontend/public/span-rollup` in `backend/utilities/commit_and_push.py`, `docs/architecture/publishing/committing.md` and `frontend/tests/console-pipeline-timeline.spec.ts`; the bench-only uses in `backend/utilities/candidate_pointer.py`, `backend/tests/workflows/test_bench_targets.py` and `docs/how-to/test-models-locally.md`; `trial_day` in `backend/idhazh/retention.py`, which G1 keeps; the retired module `publish_span_rollup.py`, which `backend/tests/contracts/test_telemetry_surface.py` holds absent; the frozen record `tests/fixtures/gardener/prune-oracle/removals.json`; the schema stem `pipeline-tests-config` in `backend/tests/contracts/_fixtures.py`, which names a contract, not a root; the generated root names in `backend/tests/ledger_migration/`, which any name serves; and older plans under `TODO/`, whose mentions describe completed work or stay true. Repeat the search at dispatch. |

Table B - Scope limits and their costs

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Moving every other CSV ledger now | Those ledgers remain on their current layout until their own producer and reader phases land. | A named ledger migration row after its contracts and compaction declaration are ready. |
| B2 | Changing published pages | No new operator view of trial data. | A separately requested surface with its own reader and design checks. |
| B3 | Enabling trial age deletion | Old trial data remains while the policy reports proposed expiry. | Review a named dry-run result and obtain explicit permission to enable deletion. |
| B4 | Shared main-checkout edits or history rewrites | Cutover occurs through reviewed worktree changes, not an immediate workstation move. | Normal merge and checkout update; history rewriting requires separate permission. |
| B5 | Deleting the four production span-rollup orphans under `state/span-rollup/2026/10/02/` (A4) | They stay on disk, read by nothing, until Plan 59 row "The CSV code no ledger uses any more is deleted" deletes them. | Moving their deletion into row 5 here. |

Table C - Target and invariant declarations

| Id | Subject | Contract |
| --- | --- | --- |
| C1 | State roots | Bench: `state/pipeline-tests`. Cases: `state/pipeline-tests/<case>`, with case names from `config/pipeline-tests.json`. Preserve disabled cases in the declared set. Never flatten case rows into the bench root. |
| C2 | Ledger file grammar | Within each root, reuse the raw, compact and index builders declared in [persistence.md](../docs/architecture/contracts/persistence.md). No second path formula. |
| C3 | Trace logs | Preserve `traces/YYYY/MM/DD/<filename>.jsonl` within each case root. Trace logs have a different stored shape from ledger files; nesting must not rewrite their content. |
| C4 | Case configuration | Keep `run.trial_state_dirname` as a slug. Add nullable `run.trial_case_dirname`, default `null`, and append it only beneath a supplied trial root. Refuse a case without a root and an id C5 reserves. `PipelineTestsConfig` in `backend/idhazh/contracts/pipeline_tests.py` already refuses duplicate case ids. |
| C5 | Reserved case names | A case id may not be a name that `claimed_roots()` in `backend/idhazh/ledger/paths.py` returns: `raw`, `compact` and every registry family, which `LedgersConfig` holds equal to the first prefix segment of each ledger it lists, so `traces` and every CSV prefix are in it. A case root sits in the bench root beside those folders, and the bench writes only under them. `config.load` in `backend/idhazh/config.py` refuses a `run.trial_case_dirname` in that set, so an `idhazh` verb stops before `backend/idhazh/cli.py` moves `common.STATE_ROOT` and before any file is written. The refusal is not in `PipelineTestsConfig`, because a contract may not import the registry (CLAUDE.md section 4). |
| C6 | Root compatibility | Readers accept old sibling roots and C1 roots before writers change. Obtain roots from configuration, never discover cases by walking state. |
| C7 | Compaction declaration | **Superseded 2026-10-09 by section 7 (O2): `owns` is tier-first, not root-first.** Add optional `CompactionPolicy.state_roots: list[str]` with default `["state"]`. Validate unique relative roots without traversal. A trial declaration names C1 roots explicitly. `compaction.run` stays one root a pass. The gardener runs a declaration once per root in `state_roots` order, stops at the first root that does not finish, and files one record row for the task, because the gardener ledger keys a row by `(date, run_id, task)`. Production names and behavior stay unchanged. |
| C8 | Task identity | Keep production `compact-<ledger>` declarations as the governing publication policy. Allow separate `compact-trial-<ledger>` declarations whose `state_roots` name only C1 roots. Do not let the trial policy govern production or bypass ownership overlap checks. |
| C9 | Trial lifecycle | Each trial declaration: `compact_after_days` 1; `daily_keep_days` 31, the least `CompactionPolicy` accepts (GitHub's 30-day re-run limit plus one); `monthly_window` three months with `month_deletes_dry_run` true; `dry_run` false; the per-pass and per-file limits the production compactions share; and a `prune_refusal` sentence, because the field has no default and a reader that ever consulted it should refuse rather than delete (I5). Three months hold at least 89 days, so the pair reaches at least 120 days, past the 90-day window of `config/gardener/trials.json`. Configuration load holds a trial declaration to that window instead of the production floors in `_refuse_a_compaction_that_cuts_its_ledger`, which read production data: past the name rule (C8), its floor check would refuse `compact-trial-item-health`, because item-health's floor is the full-grain series of `telemetry-aggregate`, whose months reach further back than 120 days. These are proposed defaults, not permission to enable expiry. |
| C10 | Compaction mode | Packing may replace raw files only after compact readback proves complete row and identity parity. The reporting-only age window must not prevent packing or authorize expiry. Keep trace retention `dry_run: true`. |
| C11 | Migration proof | Compare every source cell - every filled CSV cell, read through the ledger's declared old headings (`CsvLedger.old_headings` in `backend/utilities/ledger_migration/csv_layouts.py`) - after declared version normalization, each source key, row identities where already present, and retained non-source rows. An undeclared filled heading or a ragged row is refused, never dropped, and no ledger declares an old heading dropped (user ruling 2026-10-04). Source-derived expectations must not be built from potentially corrupted target rows. Verify indexes and period selection, not just raw file presence. No raw listing (`raw/<ledger>/index/<day>.json`) exists in `state/`, and no code reads one. |
| C12 | Migration operations | Explicit named roots, ledgers and UTC months. Read-only preview; write without retiring source; read-only verify; retire only after fresh in-process verification of every named input. A command with no mode flag still runs the complete chain. No persisted migration journal or manifest. |
| C13 | Artifact trust | Downloaded artifacts may supply validated raw files and traces, not compact results. A separate verifier checks committed trial state for named roots, ledgers and UTC months through row 1's stored-output check (`check_raw_day` and `check_compact_period` in `backend/idhazh/ledger/stored_output.py`), which checks raw and compact files, their envelopes and the compact indexes. A root containing compact data is not accepted as a runner artifact merely because its path is valid. |
| C14 | Retry and rollback | Repeated writes settle to the same intended rows; minted filenames need not be byte-identical. Preserve old-layout readers through cutover. Revert data and writer changes in reverse order without disabling readers. No migration source is deleted before proof; the span-rollup orphans are deleted by ruling, not migrated (A4). |
| C15 | Fixed inputs | Tools receive named roots and months; gardener passes receive named periods and configured roots; tests use fixtures or trees they generate. No normal reader or test enumerates committed history. |

## 1. Status Reckoner

Table D - PR phases

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Reusable migration operations ship | - | A | DONE #1265 | - | #1265 | phased-migration-tool |
| D2 | 2 | Readers understand nested trial roots | 1 | B | DONE | pt-row-2 | - | Fowler |
| D3 | 3 | Trial roots compact under their own declarations | 1, 2 | C | DONE #1405 | trial-root-compaction | #1405 | Fowler |
| D4 | 4 | Pipeline-test writers use separate nested cases | 3 | D | DONE #1413 | nested-pipeline-test-cases | #1413 | Fowler |
| D5 | 5 | Committed trial files move to the nested roots, and the orphan span summaries are deleted | 4 | E | DONE | pt-row-5 | - | Fowler |
| D6 | 6 | Path builders carry a swappable trial registry, with no production call site changed | 5 | F | DONE #1443 | pipeline-tests-tier-roots-fix-phase1 | #1443 | Fowler |
| D7 | 7 | Compaction and config move to tier-first `owns`; the gardener swaps the registry, not the state root | 6 | G | DONE #1438 | pipeline-tests-tier-roots-fix | #1438 | Fowler |
| D8 | 8 | Committed trial files move again, byte for byte, from root-first to tier-first | 7 | H | DONE #1465 | pipeline-tests-phase3-data-relocation | #1465 | Fowler |
| D9 | 9 | Traces move off the root-first address, to a sibling tier root | 8 | I | DONE #1478 | pipeline-tests-row9-traces-tier-first | #1478 | Fowler |
| D10 | 10 | Trial traces move under the raw tier, beside production traces | 9 | J | DONE (local) | pipeline-tests-migration-rows-2-to-5 | - | - |

## 2. Row #1 - Reusable migration operations ship

- **Scope:** Split Plan 58's migration utility into the package `backend/utilities/ledger_migration/`, one question a module, with the C12 operations, and keep the command and its complete chain (E5).
- **Files touched:**
  - `backend/utilities/migrate_to_parquet.py` (the command only)
  - `backend/utilities/ledger_migration/__init__.py` (new)
  - `backend/utilities/ledger_migration/refusals.py` (new)
  - `backend/utilities/ledger_migration/path_labels.py` (new)
  - `backend/utilities/ledger_migration/identity.py` (new)
  - `backend/utilities/ledger_migration/inputs.py` (new)
  - `backend/utilities/ledger_migration/csv_layouts.py` (new)
  - `backend/utilities/ledger_migration/csv_files.py` (new)
  - `backend/utilities/ledger_migration/csv_cells.py` (new)
  - `backend/utilities/ledger_migration/fold.py` (new)
  - `backend/utilities/ledger_migration/readback.py` (new)
  - `backend/utilities/ledger_migration/packing_files.py` (new)
  - `backend/utilities/ledger_migration/packing.py` (new)
  - `backend/utilities/ledger_migration/planning.py` (new)
  - `backend/utilities/ledger_migration/proof.py` (new)
  - `backend/utilities/ledger_migration/phases.py` (new)
  - `backend/utilities/ledger_migration/report_lines.py` (new)
  - `backend/idhazh/ledger/stored_output.py` (new: the door's stored-output checks)
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/config.py`
  - `backend/tests/ledger_migration/__init__.py` (new)
  - `backend/tests/ledger_migration/_fixtures.py` (new)
  - `backend/tests/ledger_migration/test_csv_layouts.py` (new)
  - `backend/tests/ledger_migration/test_csv_files.py` (new)
  - `backend/tests/ledger_migration/test_csv_cells.py` (new)
  - `backend/tests/ledger_migration/test_planning.py` (new)
  - `backend/tests/ledger_migration/test_readback.py` (new)
  - `backend/tests/ledger_migration/test_proof.py` (new)
  - `backend/tests/ledger_migration/test_packing_governance.py` (new)
  - `backend/tests/ledger_migration/test_packing_parity.py` (new)
  - `backend/tests/ledger_migration/test_packing_scope.py` (new)
  - `backend/tests/ledger_migration/test_phases.py` (new)
  - `backend/tests/ledger_migration/test_full_chain.py` (new)
  - `backend/tests/ledger_migration/test_command.py` (new)
  - `backend/tests/ledger_migration/test_path_labels.py` (new)
  - `backend/tests/ledger/test_migrate_to_parquet.py` (deleted)
  - `backend/tests/ledger/test_stored_output.py` (new)
  - `backend/tests/test_ledger.py`
  - `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:** Local: `npm --prefix frontend run test:changed -- --list`, then the selected checks; ruff and mypy on the changed Python files; the tests above; `python backend/utilities/doc_load.py` on every changed page. Those tests show that preview and verify leave generated fixture bytes unchanged, that the mode flags are mutually exclusive, and that a call with no mode still runs the complete chain. CI: the full backend suite and the selected checks on the merge candidate.
- **Oracle:** On generated roots, `--retire` deletes no CSV file in any named root unless every filled source cell of every named root reads back through the door in that same process; `--plan` and `--verify` delete nothing; and `--write` deletes no CSV file, though the compaction it runs still replaces and deletes the raw and compact files it absorbs. This cannot prove a layout `CSV_LEDGERS` does not declare, or packing at a trial root (row 3).

Table E - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| E1 | Use existing plan, write, pack and proof mechanisms; extract focused helpers rather than build a second migration framework. | Fowler; user requested reusable tooling. |
| E2 | Do not add a persisted journal. Source files remain the pending inputs; every retire revalidates current bytes. | Fowler. |
| E3 | Keep current supported ledgers and production packing eligibility in this row. Row 3 widens packing to declared trial roots (C7, I3); this plan adds no supported ledger. | Fowler; approved phased implementation. |
| E4 | Another ledger joins the tool with: a contract that reads and writes its CSV row (`csv_row`, `from_csv_row`); its key and contract in `_DOOR_SHAPES` (`backend/idhazh/ledger/keys.py`); its `config/ledgers.json` entry set to `raw-and-compact`; a compaction declaration governing each root it moves into; and one `CsvLedger` entry in `CSV_LEDGERS` (`backend/utilities/ledger_migration/csv_layouts.py`) naming its old layout, the window that kept it, and each old heading its CSV used with the field that now holds it (C11). The runbook lists them. The tool reads per-writer day trees and shared day files only. A family-nested prefix such as `content-similarity-judge/scored-pairs` waits for Plan 59 row "The person rules on what blocks each ledger left on CSV" and moves in its row "The judge ledgers with a union driver move to the door"; a month file such as `item-health-summary` is its row "The item health summary moves to the door, or stays CSV by ruling". This plan adds no ledger to the table and no layout. | Fowler; user-requested reuse. |
| E5 | The tool is the package `backend/utilities/ledger_migration/`, one question a module. It replaces `backend/utilities/csv_ledgers.py` and `backend/utilities/migration_phases.py`, which this branch created and main never held, so neither appears in the row's diff. The command stays `backend/utilities/migrate_to_parquet.py`; its tests move to `backend/tests/ledger_migration/`; the single-root `migrate()` wrapper is deleted, so every caller names its roots. `packing.py` holds the compaction lookup and packing that row 3 makes per root. | User ruling 2026-10-04. |

Table F - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | A pipeline-test-only migration script | Duplicates proof and retirement logic instead of supporting later ledgers. | Maintain a second implementation and its parity tests. | User; Fowler. |
| F2 | Treat `--check` as content verification | It checks remaining CSV paths, not cell parity. | Add content proof; retain the absence command as its separate check. | Existing runbook; Fowler. |

## 3. Row #2 - Readers understand nested trial roots

- **Scope:** Ship the committed-state verifier (C13), prove that the trials task lists and dates a C1 traces folder as it dates an old sibling root (C6, G7), make ledger warnings and refusals name a nested root's real path (G6), and delete the trial utility's dead day-tree branch, without switching producers or deleting data.
- **Files touched:**
  - `backend/utilities/pipeline_test_ledgers.py`
  - `backend/idhazh/ledger/stored_output.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/idhazh/ledger/paths.py`
  - `backend/idhazh/ledger/ledger_files.py`
  - `backend/idhazh/ledger/day_removal.py`
  - `backend/idhazh/telemetry/door_prune.py`
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/tests/ledger/test_stored_output.py`
  - `backend/tests/ledger/test_raw_files.py`
  - `backend/tests/test_pipeline_test_state_verifier.py` (new)
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/gardener/tasks/test_trials_task.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:** Local: `npm --prefix frontend run test:changed -- --list`, then the selected checks; ruff and mypy on the changed Python files; the tests above; `python backend/utilities/doc_load.py docs/concepts/growing-reads.md`. Fixtures: a generated C1 case root with door-written raw and compact files, a case slug holding date-like digits, and one corrupt envelope and one corrupt index. CI: the full backend suite.
- **Oracle:** On a generated C1 case root holding door-written raw and compact files, the verifier accepts the tree and refuses each single corruption of an envelope or a compact index. This cannot prove that a live workflow used the intended ref.

Table G - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | A trial file is dated by the unchanged `retention.trial_day`, from its path below the folder the task owns. G3 keeps every case slug inside that folder's own path, so no slug reaches the match. | Fowler; one mechanism per property. |
| G2 | Preserve artifact validation separately from committed-state verification. | Fowler; trust boundary. |
| G3 | Accept both layouts before writers change. The trials task owns only folders whose path already holds the case slug - an old sibling root, or `<case>/traces` under the bench root - and never the bench root itself, whose case subtrees hold folders the compaction declarations own: `_nested` in `backend/idhazh/config.py` refuses that overlap. | Fowler; existing overlap predicate. |
| G4 | Delete the day-tree branch of `backend/utilities/pipeline_test_ledgers.py` in a structural commit before the verifier. It accepts nothing since `DAY_TREES` emptied, and rows 2 and 4 would otherwise carry it through their nested-root changes. Plan 59 deletes `DAY_TREES` after this row lands (M2). | Fowler; tidy first. |
| G5 | The verifier imports row 1's stored-output check (C13), so this row depends on row 1. | Fowler. |
| G6 | Six helpers named `_shown` - in `raw_files.py`, `paths.py`, `ledger_files.py` and `day_removal.py` under `backend/idhazh/ledger/`, and in `door_prune.py` and `silicon.py` under `backend/idhazh/telemetry/` - each write `state/` before a path taken relative to the root they were given, so a file under a nested root reads as `state/raw/...`, a production path. One function in `backend/idhazh/ledger/paths.py` names the path from the `state` folder that holds the root (CLAUDE.md section 2), and all six callers use it; at `state/` itself the output is unchanged. `backend/tests/ledger/test_raw_files.py` asserts that a warning and a refusal under a nested root name its real path. | Tooling review (Fowler); one function per property. |
| G7 | `period_inputs.paths_for_task` lists a C1 `<case>/traces` folder through its generic dated-tree branch, `_dated_paths`, because the folder does not start with `_TRIAL_ROOT_PREFIX` (`state/pipeline-tests-`); that branch names each day folder the window holds, which is what a traces folder needs. A test in `backend/tests/gardener/test_period_inputs.py` asserts that every named day folder of such a folder is listed, so a change that skips it fails. A test in `test_trials_task.py` cannot catch that skip: its `_task` helper builds the listing without `paths_for_task`. Row 5 deletes the old-root branch (M4). | Fowler; reader before writer. |

Table H - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Discover every case and day with a tree walk | Input grows with committed history and hides undeclared cases. | A separately approved bounded inventory design, including its contract and maintenance. | Repository fixed-input rule. |
| H2 | Accept compact files in downloaded artifacts | A path check is not authority for replacement of an entire period. | A new trusted producer and proof design requiring separate approval. | Fowler. |
| H3 | Rewrite `retention.trial_day` to match only after a declared tier or trace prefix | Under G3 no owned folder's relative path holds a slug or an earlier date-like segment, so the change has no reachable failure, and it would change how the frozen trials oracle dates legacy paths. | The matcher change, its tests, and an update to `backend/tests/gardener/tasks/test_every_task_takes_what_its_pass_took.py`. | Fowler. |

## 4. Row #3 - Trial roots compact under their own declarations

- **Scope:** Implement the approved C7-C10 design, so each trial root compacts under its own declaration through the existing door writes, settlement, indexes and compaction, while production behavior stays as it is.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/gardener.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/idhazh/telemetry/prune.py`
  - `backend/utilities/ledger_migration/packing.py`
  - `backend/utilities/ledger_migration/planning.py`
  - `backend/utilities/ledger_migration/phases.py`
  - `config/idhazh_gardener.json`
  - `config/gardener/compact-trial-item-health.json` (new)
  - `config/gardener/compact-trial-host-fingerprint.json` (new)
  - `config/gardener/compact-trial-candidate-models.json` (new)
  - `config/gardener/trials.json`
  - `.github/workflows/validate.yml`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/ledger_migration/test_packing_governance.py`
  - `backend/tests/ledger_migration/test_packing_scope.py`
  - `backend/tests/ledger_migration/test_planning.py`
  - `backend/tests/ledger_migration/test_phases.py`
  - `backend/tests/ledger_migration/test_command.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_cli.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/workflows/test_validation_state_root.py`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/idhazh-gardener.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/adaptive-pruning.md`
  - `docs/concepts/partitions.md`
  - `docs/concepts/growing-reads.md`
  - `docs/reference/host-metrics.md`
  - `docs/how-to/move-a-ledger-to-parquet.md`
- **Acceptance gates:** Local: `npm --prefix frontend run test:changed -- --list`, then the selected checks; ruff and mypy on the changed Python files; the tests above; `python backend/utilities/doc_load.py` on every changed page. CI: the full backend suite and the binding checks. Before declaring roots, derive the ledgers each root can commit: a case runs `idhazh work` and `idhazh record` (`backend/utilities/pipeline_test_case.py`), whose writers are the `REGISTRY` rows labelled `work` in `backend/idhazh/ledger/staging.py`, and the bench commits what the commit steps of `measure.yml` and `validate.yml` stage. Committed cases hold item-health and traces; the bench steps stage host-fingerprint and candidate-models. Declare no ownership without evidence that a root commits that ledger, and escalate a committed ledger no declaration covers.
- **Oracle:** On a generated repository holding production `state/` and two C1 case roots with door-written item-health raw files, one gardener wake through `runner.run` with no injected listing, so that `paths_for_task` names each root's periods (I2), packs each trial root's due days into that root's compact folder with unchanged settled rows and identities, files one record row per trial task, and leaves every production file byte-identical. This cannot establish live-run duration or permission to enable expiry.

Table I - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Root-scoped trial tasks use C7-C10; production publication policy continues to resolve its original declaration. | User-approved Fowler design. |
| I2 | `period_inputs.paths_for_task` names a trial declaration's periods under each root in its `state_roots`. `_ledger_paths` there knows a raw folder only by the prefix `state/raw/` and builds compact and index paths under `repo_root / "state"`, so today a C1 root's raw days would go unlisted and its compact paths would name production's. Validate paired ownership; do not disable existing overlap safety to admit nested tasks. | Fowler. |
| I3 | `backend/utilities/ledger_migration/packing.py` governs each named root and ledger by the one `CompactionPolicy` whose `ledger` is that ledger and whose `state_roots` holds the root's path relative to `config_dir.parent`; `planning.py` and `phases.py` carry that policy per root. It packs that root with `config_dir.parent` as the repository root and only that root's raw and compact pair as owned folders, never `state_dir.parent`. A root no declaration names for the ledger is filed raw, as today, under the ledger's production `compact-<ledger>`; with none, the ledger is refused at that root. The CSV-window reach check stays on production declarations; a trial declaration's reach is checked at configuration load (C9). `packs_here` keeps its one-root question, now answered from `state_roots`, so the command is not edited. No CSV in this plan needs it; it serves E4, a later ledger the tool moves into a trial root. | Fowler; tooling review. |
| I4 | `config/gardener/trials.json` adds `state/pipeline-tests/<case>/traces` for every case `config/pipeline-tests.json` declares, before writers switch in row 4, and keeps the old sibling roots until row 5. Each trial declaration is listed in `task_names` of `config/idhazh_gardener.json`. | Fowler; reader before writer. |
| I5 | A reader that asks which declaration governs a production ledger finds it by its name, `compact-<ledger>`, as `_governing` in `backend/idhazh/config.py` does. `door_refusals` in `backend/idhazh/telemetry/prune.py` keys every `CompactionPolicy` by its ledger, so `compact-trial-item-health`, read after `compact-item-health`, would decide whether `idhazh telemetry prune` may take production's item-health days. It reads `compact-<ledger>` instead, and so does `compaction_of` in `backend/tests/retention/test_prune_range.py`, which expects one declaration a ledger. | Fowler; C8. |

Table J - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Use production retention for trials | Changes the trial promise silently. | Price and approve a new trial lifecycle, with calendar-boundary tests. | User; Fowler. |
| J2 | File one gardener record row per trial root | Rows of one task in one wake collide on the key `(date, run_id, task)`, and settlement keeps one of them. | A settlement-key change to `CollectionPruneRow` and its readers, which is an ESCALATE trigger. | Fowler. |

## 5. Row #4 - Pipeline-test writers use separate nested cases

- **Scope:** Switch case producers and artifact placement to C1-C5, preserving case separation and bench paths.
- **Files touched:**
  - `backend/idhazh/contracts/pipeline_tests.py`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/stages/common.py`
  - `backend/utilities/pipeline_test_case.py`
  - `backend/utilities/pipeline_test_case_config.py`
  - `backend/utilities/pipeline_test_ledgers.py`
  - `config/idhazh.json`
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `.github/actions/candidate-config/action.yml`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/workflows/test_validation_state_root.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/test_named_utility_inputs.py`
  - `backend/tests/test_candidate_pointer.py`
  - `docs/reference/repository-layout.md`
  - `docs/reference/github-actions.md`
  - `docs/how-to/evaluate-new-summarizer-model.md`
  - `docs/concepts/glossary.md`
  - `docs/concepts/config/retention-ages.md`
- **Acceptance gates:** Local: `npm --prefix frontend run test:changed -- --list`, then the selected checks; ruff and mypy on the changed Python files; the workflow, config and placement tests above; `python backend/utilities/doc_load.py` on every changed page. CI: the full backend suite and the workflow checks. Not a gate: read the named output paths of the next authorized trial run, and answer a wrong root by reverting this row, not by deleting data.
- **Oracle:** Two generated cases whose run, job and shard identities are equal land in separate C1 roots through gather, check and place, and each root's door reads back only its own rows. This cannot prove that a queued old-ref job will not later write its old layout.

Table K - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| K1 | Separate path slugs implement nesting without changing envelope identity or allowing separators in a slug. | Fowler. |
| K2 | Keep artifact labels and bench workflow paths when they are not state-root references. | Fowler; surgical scope. |
| K3 | Read lookup paths relative to each explicit case root; rebuild raw paths with that same root. | Existing door invariant. |
| K4 | Both bench commit steps stay as they are. `measure.yml` stages `state/pipeline-tests/raw/host-fingerprint` alone. `validate.yml` stages `state/pipeline-tests` whole, and nesting adds nothing to that: its decide job's state root is the bench root, the job does not take state from the tip, so no case subtree is dirty on that runner. `test_validation_state_root.py` asserts that the decide stage writes nothing under a declared case root. | Fowler; read `measure.yml`, `validate.yml` and `backend/utilities/commit_and_push.py`. |

Table L - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Flatten all cases into one ledger root | Shared unit identities settle one case over another; trace filenames collide. | Add case identity to persisted envelopes and migrate existing identities and traces. | Fowler. |
| L2 | Store a nested path in the slug field | Weakens the existing single-component validation. | Introduce a separately validated relative-path setting and migrate every caller. | Fowler. |
| L3 | Narrow `validate.yml`'s commit to `state/pipeline-tests/raw/candidate-models` | `git add` on a missing folder aborts the step, so it needs `measure.yml`'s `if [ -d ... ]` guard, to stop a case-subtree write the decide job cannot make. | One guarded step, a `COMMIT_STAGED_PATHS` entry in `backend/tests/workflows/_harness.py` and its test. | Fowler. |

## 6. Row #5 - Committed trial files move to the nested roots, and the orphan span summaries are deleted

- **Scope:** Move the committed raw files and traces byte for byte from the old sibling roots into their C1 roots, delete the four orphan trial span-rollup CSV files unconverted (A4), and retire the old roots' ownership; no migration runs.
- **Files touched:**
  - `state/pipeline-tests-production-settings/raw/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet`
  - `state/pipeline-tests-no-visual-plan/raw/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet`
  - `state/pipeline-tests-production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests-production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests-no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests-no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests-production-settings/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-00.csv` (deleted)
  - `state/pipeline-tests-production-settings/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-01.csv` (deleted)
  - `state/pipeline-tests-no-visual-plan/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-00.csv` (deleted)
  - `state/pipeline-tests-no-visual-plan/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-01.csv` (deleted)
  - `state/pipeline-tests/production-settings/raw/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet`
  - `state/pipeline-tests/no-visual-plan/raw/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet`
  - `state/pipeline-tests/production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests/production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests/no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests/no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `config/gardener/trials.json`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/tasks/trials.py`
  - `tests/fixtures/gardener/garden/trials.json`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/gardener/tasks/test_trials_task.py`
  - `backend/tests/gardener/tasks/_oracle_tree.py`
  - `backend/tests/gardener/tasks/test_every_task_takes_what_its_pass_took.py`
  - `backend/tests/gardener/test_cli.py`
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_sparse_shard.py`
  - `backend/tests/gardener/test_period_inputs.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/concepts/glossary.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:** Local, in order: (1) confirm no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running, or pause and name the run; (2) `git mv` each old raw and trace file to its C1 path, comparing every file's SHA-256 before and after, and `git rm` the four trial span-rollup CSV files; (3) run row 2's verifier over both case roots and the bench root for the ledgers their declarations name, month 2026-09; (4) `npm --prefix frontend run test:changed -- --list` and the selected checks, the tests above, `git diff --cached --name-only` against Files touched, and the doc report. Re-derive the named files against the merge base before dispatch instead of trusting this snapshot. CI: the full merge-candidate checks.
- **Oracle:** Each moved raw and trace file has the same SHA-256 at its C1 path, no file is left under an old sibling root, and row 2's verifier accepts both case roots and the bench root. This cannot recover a file an unrelated concurrent writer deleted.

Table M - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| M1 | This row deletes the four trial span-rollup CSV files unconverted (A4); Plan 59 row 3 deletes the four production ones. | User ruling 2026-10-04. |
| M2 | Plan 59 row "The CSV code no ledger uses any more is deleted" does not edit `backend/utilities/pipeline_test_ledgers.py`; it deletes `DAY_TREES` after row 2 here lands (G4). This row deletes Plan 59's pointer to it once the trial files are gone. | Fowler. |
| M3 | Roll back by reverting this row's pull request, which restores the data, the old roots' ownership and their period paths together. Rows 2 to 4 keep both layouts readable until this row merges. | Fowler. |
| M4 | With the old sibling roots gone from `config/gardener/trials.json`, `_TRIAL_ROOT_PREFIX` and `_trial_paths` in `backend/idhazh/gardener/period_inputs.py` match no owned folder and are deleted; every C1 traces folder keeps the generic dated-tree listing (G7). | Fowler; delete what has no caller. |

Table N - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Restore the span summary's contract and ledger, and convert the eight orphan files | The user ruled the retirement #1189 began finished (A4): nothing reads the summary, and its producer, reader, contract and registry entry are gone. | The contract, its registry entry and door key, a trial compaction, changelog entries on the four persisted shapes whose `ledger` field is a `LedgerName`, the frontend's copies of that vocabulary, and a new ruling from the user. | User ruling 2026-10-04. |

## 7. Correction - tier-first roots

Rows 1 to 5 put a trial root's own name ahead of `raw`/`compact`: `state/pipeline-tests/<case>/raw/item-health/...`. Every other ledger in this project, and every reader that walks `state/raw/` or `state/compact/` looking for a ledger's folder, puts the tier first: `state/raw/<ledger>/...`. The user caught this 2026-10-09 and ordered the layout corrected to `state/raw/pipeline-tests/<case>/item-health/...` - tier first, then the trial's own bench and case names, then the ledger's own folder. This section's three rows replace rows 2 to 5's root shape; they do not reopen row 1's migration tool or row 5's span-rollup deletion, which stand as before.

**Traces moved in row 9.** The row-7 implementation found that nesting a trace file under `state/traces/` - the production trace tier, pruned by the gardener's 7-day retention window - would put a trial's trace file inside that same window, where production's own retention task could sweep it before the trial's own report-only policy (`config/gardener/trials.json`) ever looks at it. Rows 6 to 8 left a trace file exempt from the tier-first move, at its row-5 address `state/pipeline-tests/<case>/traces/`. Row 9 finishes the correction: a trace file keeps its own 90-day window by moving to a new sibling top-level root, `state/trial-traces/pipeline-tests/<case>/`, beside `state/traces/` rather than inside it, so `state/pipeline-tests/` holds nothing at all.

Table O - Corrected design

| Id | Subject | Contract |
| --- | --- | --- |
| O1 | Why tier stays first | `state/raw/` and `state/compact/` are the only two folders a door ledger's compaction and readers ever walk looking for a ledger (`claimed_roots()`, `ledger/paths.py`). A trial name ahead of the tier is a third root no reader expects; a trial name after the tier, inside the ledger's own folder, is exactly the address the existing raw/compact/index builders already build for every production ledger, so no reader needs a second path formula (restates C2). |
| O2 | How a trial's name reaches an address | `ledger.overlay_registry(segments)` returns a registry with every entry's `prefix` rewritten: a door ledger's segments go in front of its single-element prefix (`("pipeline-tests", "no-visual-plan", "item-health")`, because its tier already comes first from `raw_root`/`compact_folder`); every other ledger's segments go in behind its own top-level folder (`("traces", "pipeline-tests", "no-visual-plan")`). `ledger.use_registry(registry)` makes that the registry every path builder falls back to, for one `with` block, restoring the enclosing registry (not `None`) on exit. Both are additions to `ledger/paths.py`; no builder's signature loses a call site that did not already accept `registry=None`. |
| O3 | Who swaps the registry | Only `gardener.runner._run_compaction_roots`, once per `state_root` in a trial compaction declaration's `state_roots` list, for the span of that root's pass. No stage, no producer, no trial writer calls `use_registry` or `overlay_registry` directly: they call the same builders production code calls, with no `registry=` argument, and the active override answers for them while a trial pass holds it. |
| O4 | What `owns` means now | `CompactionPolicy.owns` for a trial declaration is `state/<tier>/<segments>/<ledger-prefix>` for `tier` in `raw`, `compact` - the same formula `overlay_registry` builds, computed once in `config._refuse_a_compaction_declaration` to check the declaration and once in `gardener.runner` to filter which of a policy's owned folders this pass's root claims. `state_roots` keeps its existing values (`state/pipeline-tests`, `state/pipeline-tests/<case>`) unchanged; only what a root's string is used for changes, from a literal directory `compaction.run` swaps `state_dir` to, to a segment path `overlay_registry` splices in while `state_dir` stays `state/`. |
| O5 | Traces | **Superseded by row 9.** A trace file does not nest under `state/traces/` - production's own 7-day retention window would let production's prune remove a trial's trace file before this task's own 90-day, report-only policy (`config/gardener/trials.json`) ever sees it. Row 9 gives it a sibling top-level root instead, `state/trial-traces/pipeline-tests/<case>/`, rather than leaving it at its row-5 root-first address under `state/pipeline-tests/<case>/traces/`. |
| O6 | No gap between cutover and data move | A gardener wake between row 7 merging and row 8 moving the data finds nothing yet at the new address: a harmless no-op (`idhazh` degrades, it does not fail), because the old files still sit at their row-5 address until row 8 moves them. Row 8 still coordinates a quiet window for the `git mv` itself, so no scheduled workflow run writes a new file mid-move. |
| O7 | Who else touches these door files during this correction | Plan 59 (session `cecbda0b-9e6f-4c7c-b204-7a8187ea1e04`) has rows in flight editing `ledger/keys.py`, `ledger/staging.py`, `config/ledgers.json`, `config/idhazh_gardener.json`, `frontend/src/lib/data/slice-shapes.ts` and `backend/tests/contracts/test_gardener_config.py`. Rows 6 to 8 here keep both sides on a merge conflict rather than reverting Plan 59's edits. Plan 59's own data commits are confined to `state/raw/content-similarity-judge/`, which rows 6 to 8 never touch; row 8 announces its data-move window to that session before it starts and after it lands, per that session's request. |
| O8 | What is not reopened | Row 1's migration tool, its C11 to C13 proof and artifact-trust rules, and row 5's span-rollup deletion. Row 7 does not build on `backend/utilities/ledger_migration/` or `packing.policies_for_roots`: Plan 59 row 10 deletes that package after the judge CSV retirement, and this correction does not need a CSV-to-Parquet conversion, only a Parquet/JSON/JSONL move already at its target shape. |

### Row #6 - Path builders carry a swappable trial registry, with no production call site changed

- **Scope:** Add `ledger.use_registry` and `ledger.overlay_registry` (O2) to `ledger/paths.py`, give `path`, `relpath`, `tree_root` and `tree_relpath` the `registry=` keyword the other six builders already had, and export both names. No caller outside the new tests passes a registry; production behavior is unchanged because `_registry(None)` still returns the committed table whenever no trial pass has swapped it.
- **Files touched:** `backend/idhazh/ledger/paths.py`; `backend/idhazh/ledger/__init__.py`; `backend/tests/contracts/test_ledger_trial_overlay.py` (new).
- **Acceptance gates:** `ruff check`, `mypy` on both source files; the new unit tests; the full `backend/tests/test_ledger.py`, `backend/tests/contracts/test_ledger_registry.py`, `backend/tests/contracts/test_ledger_door_fixture.py`, `backend/tests/ledger/test_ledger_files.py` and `backend/tests/test_ledger_families.py` suites green with no change to their assertions.
- **Oracle:** Outside any `use_registry` block every builder answers exactly what it answered before this row; inside one, a door ledger's segments land ahead of its prefix and a tree ledger's land behind its own top-level folder; a nested block restores the enclosing override, not `None`, on exit, including on an exception.
- **Status:** DONE, pull request #1443.

### Row #7 - Compaction and config move to tier-first `owns`; the gardener swaps the registry, not the state root

- **Scope:** `gardener.runner._run_compaction_roots` stops swapping `context.state_dir` per `state_root`; it computes `segments` from the root, filters `policy.owns` to the tier-first addresses O4 names, and wraps the pass in `ledger.use_registry(ledger.overlay_registry(segments))` instead, so `state_dir` stays `state/` for every root. `config._refuse_a_compaction_declaration` checks a trial declaration's `owns` against the same tier-first formula. The three raw/compact trial gardener configs (`compact-trial-item-health.json`, `compact-trial-host-fingerprint.json`, `compact-trial-candidate-models.json`) get tier-first `owns` values; `state_roots` keeps its existing strings. `trials.json` (trace retention) is unchanged (O5): its `owns` keeps the row-5 address, because a trace file does not move. `CompactionPolicy.state_roots`'s docstring in `contracts/knobs/gardener.py` is corrected to say a root is a segment path spliced after the tier, not a directory `compaction.run` enters. `pipeline_test_ledgers.py`'s `gather`/`place` read and write raw ledger files through the same registry overlay, with a trace file read/written at its unmoved address. `.github/workflows/idhazh-pipeline-tests.yaml`, `validate.yml` and `measure.yml`'s hardcoded `state/pipeline-tests/raw/...` references move to `state/raw/pipeline-tests/...`.
- **Files touched:** `backend/idhazh/gardener/runner.py`; `backend/idhazh/config.py`; `backend/idhazh/contracts/knobs/gardener.py`; `backend/utilities/pipeline_test_ledgers.py`; `backend/utilities/pipeline_test_case.py`; `backend/idhazh/ledger/paths.py` (`_ACTIVE_OVERRIDE` hardened to a `contextvars.ContextVar`); `config/gardener/compact-trial-item-health.json`; `config/gardener/compact-trial-host-fingerprint.json`; `config/gardener/compact-trial-candidate-models.json`; `backend/tests/contracts/test_gardener_config.py`; `backend/tests/gardener/test_runner.py`; `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`; `backend/tests/workflows/test_pipeline_tests_workflow.py`; `backend/tests/workflows/test_plan_handoff.py`; `.github/workflows/idhazh-pipeline-tests.yaml`; `.github/workflows/validate.yml`; `.github/workflows/measure.yml`; `docs/reference/repository-layout.md`; `docs/concepts/growing-reads.md`.
- **Acceptance gates:** Local: `ruff check`, `mypy` on touched backend files; the updated and new tests above; `npm --prefix frontend run test:changed -- --list` (expected empty - no frontend file touched). CI: full merge-candidate checks.
- **Oracle:** A trial compaction pass run against a fixture tree reads and writes at the tier-first address, not the old root-first one; `config.load` accepts the three corrected trial declarations and refuses one whose `owns` still names a root-first path; `trials.json`'s declaration and a trace file's address are both unchanged; no production `compact-<ledger>` declaration's behavior changes; concurrent case/shard writers each see only their own registry overlay, proven by a `ContextVar`-isolation regression test.
- **Status:** DONE, pull request #1438.

### Row #8 - Committed trial files move again, byte for byte, from root-first to tier-first

- **Scope:** `git mv` the six raw/compact files row 5 committed from their row-5 (root-first) address to the corrected tier-first address, comparing SHA-256 before and after; coordinate the quiet window with Plan 59 (O7) before the move and announce when it ends. The four trace files stay at their row-5 address (O5) - no move, no rename.
- **Files touched:**
  - `state/pipeline-tests/compact/host-fingerprint/daily/2026/09/19.parquet` -> `state/compact/pipeline-tests/host-fingerprint/daily/2026/09/19.parquet`
  - `state/pipeline-tests/compact/host-fingerprint/index/daily.json` -> `state/compact/pipeline-tests/host-fingerprint/index/daily.json`
  - `state/pipeline-tests/compact/host-fingerprint/index/monthly.json` -> `state/compact/pipeline-tests/host-fingerprint/index/monthly.json`
  - `state/pipeline-tests/compact/host-fingerprint/index/yearly.json` -> `state/compact/pipeline-tests/host-fingerprint/index/yearly.json`
  - `state/pipeline-tests/no-visual-plan/raw/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet` -> `state/raw/pipeline-tests/no-visual-plan/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet`
  - `state/pipeline-tests/production-settings/raw/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet` -> `state/raw/pipeline-tests/production-settings/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet`
  - Not moved (O5): `state/pipeline-tests/no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`, `...-work-01.jsonl`, `state/pipeline-tests/production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`, `...-work-01.jsonl`
- **Acceptance gates:** Local, in order: (1) confirm no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running, or pause and name the run; (2) `git mv` each raw/compact file, comparing SHA-256 before and after; (3) a compaction/read smoke against the new addresses using the corrected builders; (4) the full test and doc gates. CI: full merge-candidate checks.
- **Oracle:** Each moved file has the same SHA-256 at its tier-first path; no file is left at the row-5 root-first address; the four trace files are byte-identical and untouched at their row-5 address; a read through the corrected builders at the new address returns the same rows row 5's verifier accepted.
- **Status:** DONE, pull request #1465 (squash SHA `f27df00e084caa30c24fb5384be76c3314416386`), merged into `main`. The six files are `git mv`'d (SHA-256 and git blob SHA confirmed identical pre/post against `origin/main`); gate (1) cleared (all five named workflows confirmed not queued/running); CI (scope/gates/robots/site/browser) green. Note: three stale `measure.yml` comments (still describing the old whole-state-root-swap model) could not be included in that PR - the pushing worktree's token lacked the `workflow` OAuth scope needed to push workflow-file changes - and remain deferred to a follow-up comment-only PR from a token with that scope. No functional/command text in `measure.yml` is wrong; only those three comments are stale.

### Row #9 - Traces move off the root-first address, to a sibling tier root

A trace file was the one thing rows 6 to 8 left at its row-5, root-first address (O5), because nesting it under production's own `state/traces/` would put it inside that tier's 7-day retention window - a trial trace needs 90 days, and production's prune does not know the difference between the two. The user confirmed this row's design directly: a new sibling top-level root, `state/trial-traces/`, beside `state/traces/` rather than inside it, so the two folders keep different retention windows and never share a claim. `config._refuse_overlapping_claims` is untouched by this row: the two roots are siblings, not nested, so their claims do not overlap and there is nothing for that guard to refuse.

- **Scope:** Add `TRIAL_TRACES_DIRNAME = "trial-traces"` to `ledger/paths.py`; give `overlay_registry()`'s TRACES branch its own formula, `(TRIAL_TRACES_DIRNAME, *segments)`, replacing the committed `("traces",)` prefix outright rather than appending to it (every other door ledger's formula is unchanged); add it to `claimed_roots()`. `pipeline_test_ledgers.py`'s `gather`/`place` target `state/trial-traces/pipeline-tests/<case>/` instead of `state/pipeline-tests/<case>/traces/`; the artifact's own internal shape (`<case>/traces/<YYYY>/<MM>/<DD>/<name>.jsonl`) does not change. `config/gardener/trials.json`'s `owns` list moves to the three new sibling-root addresses. The four committed `.jsonl` trace files `git mv` from their row-5 address to `state/trial-traces/pipeline-tests/<case>/<YYYY>/<MM>/<DD>/`, byte for byte.
- **Files touched:** `backend/idhazh/ledger/paths.py`; `backend/utilities/pipeline_test_ledgers.py`; `config/gardener/trials.json`; `backend/tests/ledger/test_trial_roots.py`; `backend/tests/contracts/test_ledger_trial_overlay.py`; `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`; `backend/tests/contracts/test_ledger_registry.py`; `backend/tests/gardener/test_cli.py`; `backend/tests/gardener/test_runner.py`; `backend/tests/gardener/test_sparse_shard.py`; `backend/tests/gardener/test_period_inputs.py`; `backend/tests/gardener/tasks/_oracle_tree.py`; `backend/tests/gardener/tasks/test_trials_task.py`; `backend/tests/test_named_utility_inputs.py`; `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`; `backend/tests/workflows/test_pipeline_tests_workflow.py`; `tests/fixtures/gardener/garden/trials.json`; `docs/architecture/contracts/persistence.md`; `docs/reference/repository-layout.md`; `docs/concepts/growing-reads.md`; `docs/reference/github-actions.md`; `docs/reference/host-metrics.md`; `docs/how-to/evaluate-new-summarizer-model.md`; `docs/concepts/partitions.md`; the four moved `.jsonl` files. **Deferred, not in this row's PR:** a comment-only fix to `.github/workflows/idhazh-pipeline-tests.yaml` (naming the new trace address) and the three pre-existing stale `measure.yml` comments carried from row 8's O7 - the pushing worktree's token again lacked the `workflow` OAuth scope needed to push any `.github/workflows/*.yml` edit, same as row 8. No functional/command text in either file is wrong; only comments are stale, and both remain open follow-ups for a token with that scope.
- **Acceptance gates:** Local, in order: (1) confirm no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running, or pause and name the run; (2) `git mv` each trace file, confirmed by git's own `R100` rename detection against `origin/main`; (3) the full test suite green, including a concurrent-writer isolation regression on the registry override; (4) doc gates (`backend/utilities/doc_load.py` on every changed page). CI: full merge-candidate checks.
- **Oracle:** `git ls-tree -r --name-only origin/main state/pipeline-tests` returns nothing; the four trace files are byte-identical at `state/trial-traces/pipeline-tests/<case>/<YYYY>/<MM>/<DD>/`; `claimed_roots()` includes `trial-traces` beside `traces`, `raw` and `compact`; a read through the corrected builders at the new trace address returns the same rows a reader got at the old one; `_refuse_overlapping_claims` is unchanged and still passes.
- **Status:** DONE, pull request #1478 (squash SHA `827547190ecccdd69efe28ea036b4dc74eae128b`), merged into `main` at 2026-10-09T02:04:35Z. The four trace files are `git mv`'d (SHA-256 confirmed identical pre/post against `origin/main`); gate (1) cleared (all five named workflows confirmed not queued/running before the data commit); CI (scope/gates/robots/site/browser) green. `git ls-tree -r --name-only origin/main state/pipeline-tests` is empty. The two `.github/workflows/*.yml` comment fixes named above remain deferred to a follow-up comment-only PR from a token with the `workflow` scope.

### Row #10 - Trial traces move under the raw tier, beside production traces

The user corrected row 9's destination: trial traces belong at `state/raw/traces/pipeline-tests/<case>/`, not `state/trial-traces/`. The production tree remains `state/traces/`, so the two retention claims stay separate. The files remain JSONL spans; `raw/traces` is a path tier here, not a conversion to raw ledger-door files.

- **Scope:** Update the trace registry overlay and trial trace gather/place paths to use `state/raw/traces/<segments>`; update the trial retention roots, tests, workflow comment and owning docs; move the four committed trace files from `state/trial-traces/pipeline-tests/<case>/<YYYY>/<MM>/<DD>/` without changing their bytes. Do not change production trace paths or retention, and do not convert the trace format.
- **Files touched:** `backend/idhazh/ledger/paths.py`; `backend/utilities/pipeline_test_ledgers.py`; `config/gardener/trials.json`; the trial trace path, gardener, workflow, and contract tests listed in this change; `.github/workflows/idhazh-pipeline-tests.yaml`; `docs/architecture/contracts/persistence.md`; `docs/concepts/growing-reads.md`; `docs/reference/github-actions.md`; `docs/reference/repository-layout.md`; the four moved `.jsonl` files.
- **Acceptance gates:** The full backend suite, `ruff`, `mypy`, and `doc_load` pass. All four destination files have the same Git blob as their original committed source, and no file or empty directory remains under `state/trial-traces/`. The broad browser check is not a required site smoke because this row changes no frontend code or published page; its unrelated console suite timed out locally after 580 tests passed.
- **Oracle:** The registry resolves each trial trace to `state/raw/traces/pipeline-tests/<case>/`; the trial retention config owns those case roots; production still owns `state/traces/`; the four JSONL blobs are unchanged; no active code, config or docs declaration uses `state/trial-traces/`. Earlier plan sections keep that address only to record row 9's now-replaced result.
- **Status:** DONE locally on branch `pipeline-tests-migration-rows-2-to-5`; no commit or pull request was requested.

## See also

- [Migration operations](../docs/how-to/move-a-ledger-to-parquet.md)
- [Ledger persistence](../docs/architecture/contracts/persistence.md)
- [Ledger registry](../docs/architecture/contracts/ledger-registry.md)
- [Retention safeguards](../docs/architecture/publishing/retention.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Local gates](../docs/how-to/run-the-gates.md)
- [Agent notes](../docs/reference/agent-notes.md)
