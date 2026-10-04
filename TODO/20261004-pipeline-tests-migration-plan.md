# Pipeline-test state moves through reusable migration phases

**Last Updated**: 2026-10-04
**Level**: 5 for the approved root and legacy-summary design; 2 for the first tooling phase.
**Status**: Row 1 is committed on branch `pipeline-tests-migration`; no pull request is open. No committed data has moved. Rows 2 to 5 wait for the user's authorization.

## 0. Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Put every pipeline-test state tree under one parent, use raw and compact ledger files, preserve recorded values, and reuse the migration commands for later ledgers. |
| A2 | Hard scope - in | Reusable preview, write, verify and retire operations; nested case roots; bounded readers; trial compaction; exact CSV conversion; producers, artifact validation, gardener consumers, fixtures and owning docs. |
| A3 | Chosen strategy | Fowler: extend the existing migration tool and compaction engine. Keep case identity in separate roots, not in changed writer envelopes. |
| A4 | Approved design | The user approved (2026-10-04) nested cases with both tiers, explicit trial compaction roots (C7, C8) and the restored legacy summary (C11, C12). Losing a CSV cell is not approved. |
| A5 | Execution | Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP for rows 2 to 5 until the user authorizes them. |
| A6 | First phase authorization | The user requested that the reusable tooling be built now. Its worker may change the migration utility, its focused helpers and tests, and its runbook. It must not move committed data. |
| A7 | ESCALATE triggers | Pause only for: a persisted-contract change other than the approved C4, C7, C8, C11 and C12 shapes; a change to `WriterIdentity`, `unit_id` or a settlement key; enabling expiry or shortening any retention; a ledger a trial root can commit that no declaration covers; a writer or gardener run queued or running at data cutover; a source cell that cannot be preserved. |
| A8 | Evidence | Plan 58 closed in pull request #1242. Its current implementation and [migration runbook](../docs/how-to/move-a-ledger-to-parquet.md), not the removed plan, are the reuse authority. |
| A9 | Local and CI gates | Inspect `npm --prefix frontend run test:changed -- --list`, then run the selected local checks and each row's focused oracle. Record inputs and results in the pull request description. CI runs full suites on each merge candidate; do not repeat an unchanged worker check. |
| A10 | Documentation rule | Update owning docs with their code phase. Run `python backend/utilities/doc_load.py` with every changed Markdown path before and after. Apply the split test to the page receiving material. |
| A11 | Searched names | Each row's Files touched holds the matches it edits from a whole-tree search for `pipeline-tests-`, `TRIAL_STATE_PREFIX`, `TRIAL_STATE`, `BENCH_TRIAL_STATE`, `trial_state_dirname`, `trial_case_dirname`, `_TRIAL_ROOT_PREFIX`, `trial_day`, `span-rollup`, `span_rollup`, `SpanRollupRow`, `RollupSpan` and `SPAN_ROLLUP`. No row edits these matches: the published folder `frontend/public/span-rollup` in `backend/utilities/commit_and_push.py`, `docs/architecture/publishing/committing.md` and `frontend/tests/console-pipeline-timeline.spec.ts`; the bench-only uses in `backend/utilities/candidate_pointer.py`, `backend/tests/workflows/test_bench_targets.py` and `docs/how-to/test-models-locally.md`; and older plans under `TODO/`, whose mentions describe completed work or stay true. Repeat the search at dispatch. |

Table B - Scope limits and their costs

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Moving every other CSV ledger now | Those ledgers remain on their current layout until their own producer and reader phases land. | A named ledger migration row after its contracts and compaction declaration are ready. |
| B2 | Changing published pages | No new operator view of trial data. | A separately requested surface with its own reader and design checks. |
| B3 | Enabling trial age deletion | Old trial data remains while the policy reports proposed expiry. | Review a named dry-run result and obtain explicit permission to enable deletion. |
| B4 | Shared main-checkout edits or history rewrites | Cutover occurs through reviewed worktree changes, not an immediate workstation move. | Normal merge and checkout update; history rewriting requires separate permission. |
| B5 | The four production `span-rollup` CSV files under `state/span-rollup/2026/10/02/` | They stay CSV until Plan 59 rules on them (M2). | The ruling in Plan 59 row "The person rules on what blocks each ledger left on CSV" choosing migration, with a production `compact-span-rollup` that keeps them for ever. |

Table C - Target and invariant declarations

| Id | Subject | Contract |
| --- | --- | --- |
| C1 | State roots | Bench: `state/pipeline-tests`. Cases: `state/pipeline-tests/<case>`, with case names from `config/pipeline-tests.json`. Preserve disabled cases in the declared set. Never flatten case rows into the bench root. |
| C2 | Ledger file grammar | Within each root, reuse the raw, compact, index and watermark builders declared in [persistence.md](../docs/architecture/contracts/persistence.md). No second path formula. |
| C3 | Trace logs | Preserve `traces/YYYY/MM/DD/<filename>.jsonl` within each case root. Trace logs have a different stored shape from ledger files; nesting must not rewrite their content. |
| C4 | Case configuration | Keep `run.trial_state_dirname` as a slug. Add nullable `run.trial_case_dirname`, default `null`, and append it only beneath a supplied trial root. Refuse a case without a root, duplicate case ids, and ids reserved by the root grammar. |
| C5 | Reserved case names | A case id may not be `raw`, `compact` or the first prefix segment of any `config/ledgers.json` entry, because a case root sits in the bench root beside those folders. Derive the set from the registry and the tier folder names at configuration load, not after files are written; do not hand-list it. |
| C6 | Root compatibility | Readers accept old sibling roots and C1 roots before writers change. Obtain roots from configuration, never discover cases by walking state. |
| C7 | Compaction declaration | Add optional `CompactionPolicy.state_roots: list[str]` with default `["state"]`. Validate unique relative roots without traversal. A trial declaration names C1 roots explicitly, and its `owns` must equal its ledger's raw and compact folder under each root, as the existing path builders spell them. `compaction.run` stays one root a pass. The gardener runs a declaration once per root in `state_roots` order, stops at the first root that does not finish, and files one record row for the task, because the gardener ledger keys a row by `(date, run_id, task)`. Production names and behavior stay unchanged. |
| C8 | Task identity | Keep production `compact-<ledger>` declarations as the governing publication policy. Allow separate `compact-trial-<ledger>` declarations whose `state_roots` name only C1 roots. Do not let the trial policy govern production or bypass ownership overlap checks. |
| C9 | Trial lifecycle | Each trial declaration: `compact_after_days` 1; `daily_keep_days` 31, the least `CompactionPolicy` accepts (GitHub's 30-day re-run limit plus one); `monthly_window` three months with `monthly_window_dry_run` true; `dry_run` false; and the per-pass and per-file limits the production compactions share. Three months hold at least 89 days, so the pair reaches at least 120 days, past the 90-day window of `config/gardener/trials.json`. Configuration load holds a trial declaration to that window instead of the production floors in `_refuse_a_compaction_that_cuts_its_ledger`: those read production data, and today they refuse `compact-trial-item-health`, because the full-grain series of `telemetry-aggregate` is item-health's floor. These are proposed defaults, not permission to enable expiry. |
| C10 | Compaction mode | Packing may replace raw files only after compact readback proves complete row and identity parity. The reporting-only age window must not prevent packing or authorize expiry. Keep trace retention `dry_run: true`. |
| C11 | Legacy summary shape | Restore `RollupSpan` and `SpanRollupRow` from the contract #1189 removed, with fields, validator, CSV methods, schema stem and changelog unchanged: the shape did not change, and the committed rows carry its newest stamp. So `version`, `date`, `run_id`, `shard`, `span_name`, `count`, `total_ms` and `unattributed_ms` keep their meanings, and the committed CSV heading reads with no rename. `run_id` and `shard` stay the row's own columns: a field named like an envelope key is that column, and only `attempt` and `unit_id` must match the writer (`_RANKED_CELLS` in `backend/idhazh/ledger/persist.py`), so the migrator's identity cannot overwrite them, as with `HostFingerprintRow`. Rewrite only the module docstring, which describes the removed writer. Do not infer missing wall-clock data from traces. |
| C12 | Legacy summary ledger | `LedgerName.SPAN_ROLLUP` is `span-rollup`. `config/ledgers.json` gains a `span-rollup` family, `retired` because nothing writes new rows, holding one ledger of grain `raw-and-compact` and prefix `["span-rollup"]`; the migrator (`job=migrate`) and compaction (`job=run-tasks`) still write there, because a retired family accepts writes from `MAINTENANCE_JOBS`. Its door key is `(date, run_id, shard, span_name)`. `backend/idhazh/ledger/staging.py` gains a `REGISTRY` row with no symbol and no job labels, because every `LedgerName` needs one. `CSV_LEDGERS` gains `_tree(LedgerName.SPAN_ROLLUP)` with `ForeverWindow`: the per-writer day tree and the window that the registry entry and `config/gardener/span-rollup.json` declared before #1189. Its one compaction is `compact-trial-span-rollup` over the case roots; this plan declares no production `compact-span-rollup` (B5). `arrow_schema.py` needs no change, because `RollupSpan` is a `StrEnum` and maps to a string column. No age deletion. |
| C13 | Migration proof | Compare every source cell after declared version normalization, each source key, row identities where already present, and retained non-source rows. Source-derived expectations must not be built from potentially corrupted target rows. Verify indexes and period selection, not just raw file presence. A raw listing under `state/` (`raw/<ledger>/index/<day>.json`) is never proof: the compaction no longer writes one there (`RawDayIndex` in `backend/idhazh/contracts/ledger_index.py`) and no reader opens one there, so a stale listing naming packed and deleted files neither refuses a day nor stands in for reading the files. |
| C14 | Migration operations | Explicit named roots, ledgers and UTC months. Read-only preview; write without retiring source; read-only verify; retire only after fresh in-process verification of every named input. The existing all-in-one mode remains compatible. No persisted migration journal or manifest. |
| C15 | Artifact trust | Downloaded artifacts may supply validated raw files and traces, not compact results. A separate verifier checks committed trial state for named roots, ledgers and UTC months through row 1's stored-output check (`check_raw_day` and `check_compact_period` in `backend/idhazh/ledger/stored_output.py`), which checks raw and compact files, their envelopes and the compact indexes, and which row 2 extends to parse each period watermark. A root containing compact data is not accepted as a runner artifact merely because its path is valid. |
| C16 | Retry and rollback | Repeated writes settle to the same intended rows; minted filenames need not be byte-identical. Preserve old-layout readers through cutover. Revert data and writer changes in reverse order without disabling readers. No source deletion before proof. |
| C17 | Fixed inputs | Tools receive named roots and months; gardener passes receive named periods and configured roots; tests use fixtures or trees they generate. No normal reader or test enumerates committed history. |

## 1. Status Reckoner

Table D - PR phases

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Reusable migration operations ship | - | A | IN-FLIGHT | - | - | phased-migration-tool |
| D2 | 2 | Readers understand nested trial roots | 1 | B | PENDING | - | - | - |
| D3 | 3 | Trial compaction and summary contracts ship | 1, 2 | C | PENDING | - | - | - |
| D4 | 4 | Pipeline-test writers use separate nested cases | 3 | D | PENDING | - | - | - |
| D5 | 5 | Named data moves and CSV retires after proof | 4 | E | PENDING | - | - | - |

## 2. Row #1 - Reusable migration operations ship

- **Scope:** Extend Plan 58's migration utility with C14 operations and preserve its existing complete migration behavior.
- **Files touched:**
  - `backend/utilities/migrate_to_parquet.py` (the command only)
  - `backend/utilities/csv_ledgers.py` (new: CSV layouts and day readers)
  - `backend/utilities/migration_phases.py` (new: fold, pack, prove and the phases)
  - `backend/idhazh/ledger/stored_output.py` (new: the door's stored-output checks)
  - `backend/idhazh/ledger/raw_files.py` (docstring)
  - `backend/idhazh/config.py`
  - `backend/tests/ledger/test_migrate_to_parquet.py`
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
- **Oracle:** On generated roots, `--retire` deletes no CSV file in any named root unless every filled source cell of every named root reads back through the door in that same process; `--plan`, `--write` and `--verify` delete nothing; and a stale raw listing, an older compaction's `raw/<ledger>/index/<day>.json` naming packed and deleted files, never refuses a day (C13). This cannot prove a layout `CSV_LEDGERS` does not declare, or packing at a trial root (row 3).

Table E - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| E1 | Use existing plan, write, pack and proof mechanisms; extract focused helpers rather than build a second migration framework. | Fowler; user requested reusable tooling. |
| E2 | Do not add a persisted journal. Source files remain the pending inputs; every retire revalidates current bytes. | Fowler. |
| E3 | Keep current supported ledgers and production packing eligibility in this phase. C7 and C12 expand them later, not through silent fallback. | Fowler; approved phased implementation. |
| E4 | Another ledger joins the tool with: a contract that reads and writes its CSV row (`csv_row`, `from_csv_row`); its key and contract in `_DOOR_SHAPES` (`backend/idhazh/ledger/keys.py`); its `config/ledgers.json` entry set to `raw-and-compact`; a compaction declaration governing each root it moves into; and one `CsvLedger` entry in `CSV_LEDGERS` (`backend/utilities/csv_ledgers.py`) naming its old layout and the window that kept it. The runbook lists them. The tool reads per-writer day trees and shared day files only. A family-nested prefix such as `content-similarity-judge/scored-pairs` waits for Plan 59 row "The person rules on what blocks each ledger left on CSV" and moves in its row "The five ledgers with a union driver move to the door"; a month file such as `item-health-summary` is its row "The item health summary moves to the door, or stays CSV by ruling". This plan adds no layout, because `span-rollup` is a per-writer day tree. | Fowler; user-requested reuse. |

Table F - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | A pipeline-test-only migration script | Duplicates proof and retirement logic instead of supporting later ledgers. | Maintain a second implementation and its parity tests. | User; Fowler. |
| F2 | Treat `--check` as content verification | It checks remaining CSV paths, not cell parity. | Add content proof; retain the absence command as its separate check. | Existing runbook; Fowler. |

## 3. Row #2 - Readers understand nested trial roots

- **Scope:** Ship the committed-state verifier (C15), prove the trials task dates a C1 traces folder as it dates an old sibling root (C6), make raw-file warnings and refusals name a nested root's real path, and delete the trial utility's dead day-tree branch, without switching producers or deleting data.
- **Files touched:**
  - `backend/utilities/pipeline_test_ledgers.py`
  - `backend/idhazh/ledger/stored_output.py`
  - `backend/idhazh/ledger/raw_files.py`
  - `backend/tests/ledger/test_stored_output.py`
  - `backend/tests/ledger/test_raw_files.py`
  - `backend/tests/test_pipeline_test_state_verifier.py` (new)
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/gardener/tasks/test_trials_task.py`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:** Local: `npm --prefix frontend run test:changed -- --list`, then the selected checks; ruff and mypy on the changed Python files; the tests above; `python backend/utilities/doc_load.py docs/concepts/growing-reads.md`. Fixtures: a generated C1 case root with door-written raw and compact files, a case slug holding date-like digits, and one corrupt envelope, index and watermark each. CI: the full backend suite.
- **Oracle:** On a generated C1 case root holding door-written raw and compact files, the verifier accepts the tree and refuses each single corruption of an envelope, a compact index or a watermark. This cannot prove that a live workflow used the intended ref.

Table G - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | A trial file is dated by the unchanged `retention.trial_day`, from its path below the folder the task owns. G3 keeps every case slug inside that folder's own path, so no slug reaches the match. | Fowler; one mechanism per property. |
| G2 | Preserve artifact validation separately from committed-state verification. | Fowler; trust boundary. |
| G3 | Accept both layouts before writers change. The trials task owns only folders whose path already holds the case slug - an old sibling root, or `<case>/traces` under the bench root - and never the bench root itself, whose case subtrees hold folders the compaction declarations own: `_nested` in `backend/idhazh/config.py` refuses that overlap. | Fowler; existing overlap predicate. |
| G4 | Delete the day-tree branch of `backend/utilities/pipeline_test_ledgers.py` in a structural commit before the verifier. It accepts nothing since `DAY_TREES` emptied, and rows 2 and 4 would otherwise carry it through their nested-root changes. Plan 59 deletes `DAY_TREES` after this row lands (M2). | Fowler; tidy first. |
| G5 | The verifier imports row 1's stored-output check (C15), so this row depends on row 1. | Fowler. |
| G6 | `raw_files._shown` writes `state/` before a path taken relative to the root it was given, so a skipped or refused file under a nested root reads as `state/raw/...`, a production path. It names the file's path from the repository root instead (CLAUDE.md section 2). | Tooling review (Fowler). |

Table H - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Discover every case and day with a tree walk | Input grows with committed history and hides undeclared cases. | A separately approved bounded inventory design, including its contract and maintenance. | Repository fixed-input rule. |
| H2 | Accept compact files in downloaded artifacts | A path check is not authority for replacement of an entire period. | A new trusted producer and proof design requiring separate approval. | Fowler. |
| H3 | Rewrite `retention.trial_day` to match only after a declared tier or trace prefix | Under G3 no owned folder's relative path holds a slug or an earlier date-like segment, so the change has no reachable failure, and it would change how the frozen trials oracle dates legacy paths. | The matcher change, its tests, and an update to `backend/tests/gardener/tasks/test_every_task_takes_what_its_pass_took.py`. | Fowler. |

## 4. Row #3 - Trial compaction and summary contracts ship

- **Scope:** Implement the approved C7-C13 design using existing door writes, settlement, indexes and compaction, while preserving production behavior.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/gardener.py`
  - `backend/idhazh/contracts/span_rollup.py` (restored)
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/idhazh/gardener/runner.py`
  - `backend/idhazh/gardener/period_inputs.py`
  - `backend/idhazh/gardener/tasks/compaction.py`
  - `backend/idhazh/gardener/tasks/_compact_tree.py`
  - `backend/utilities/migration_phases.py`
  - `backend/utilities/csv_ledgers.py`
  - `config/ledgers.json`
  - `config/idhazh_gardener.json`
  - `config/gardener/compact-trial-item-health.json` (new)
  - `config/gardener/compact-trial-host-fingerprint.json` (new)
  - `config/gardener/compact-trial-candidate-models.json` (new)
  - `config/gardener/compact-trial-span-rollup.json` (new)
  - `config/gardener/trials.json`
  - `.github/workflows/validate.yml`
  - `tests/fixtures/contracts/span-rollup-row/the-item-row-carries-the-residual.json` (new)
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_span_rollup.py` (new)
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/ledger/test_migrate_to_parquet.py`
  - `backend/tests/gardener/tasks/test_compaction.py`
  - `backend/tests/gardener/test_runner.py`
  - `backend/tests/gardener/test_cli.py`
  - `backend/tests/workflows/test_validation_state_root.py`
  - `docs/architecture/contracts/ledger-registry.md`
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
- **Oracle:** On a generated repository holding production `state/` and two C1 case roots with span-rollup CSV, the migrator converts every summary cell, `unattributed_ms` included, into each case root; one gardener wake then packs each trial root's due days into that root's compact folder with unchanged settled rows and identities, files one record row per trial task, and leaves every production file byte-identical. This cannot establish live-run duration or permission to enable expiry.

Table I - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Root-scoped trial tasks use C7-C10; production publication policy continues to resolve its original declaration. | User-approved Fowler design. |
| I2 | Validate paired ownership and bound each root's periods; do not disable existing overlap safety to admit nested tasks. | Fowler. |
| I3 | Restore the legacy summary contract and migrate cells rather than synthesize missing timestamps or discard residual elapsed time. | User-approved lossless migration. |
| I4 | `backend/utilities/migration_phases.py` governs each named root and ledger by the one `CompactionPolicy` whose `ledger` is that ledger and whose `state_roots` holds the root's path relative to `config_dir.parent`. It packs that root with `config_dir.parent` as the repository root and only that root's raw and compact pair as owned folders, never `state_dir.parent`. A root no declaration names for the ledger is filed raw, as today, under the ledger's production `compact-<ledger>`; with none, the ledger is refused at that root. The CSV-window reach check stays on production declarations; a trial declaration's reach is checked at configuration load (C9). `packs_here` keeps its one-root question, now answered from `state_roots`, so the command module is not edited. | Fowler; tooling review. |
| I5 | Contract schemas are computed on demand; no generated schema file is added. | Current schema owner doc. |
| I6 | `config/gardener/trials.json` adds `state/pipeline-tests/<case>/traces` for every case `config/pipeline-tests.json` declares, before writers switch in row 4, and keeps the old sibling roots until row 5. Each trial declaration is listed in `task_names` of `config/idhazh_gardener.json`. | Fowler; reader before writer. |

Table J - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Use production retention for trials | Changes the trial promise silently. | Price and approve a new trial lifecycle, with calendar-boundary tests. | User; Fowler. |
| J2 | Convert residual elapsed time into a synthetic trace event | Required event timestamps and identity are not in the CSV. | A declared new event meaning and source data sufficient to reconstruct it. | Fowler. |
| J3 | Keep residual values only in Git history | Does not preserve them in the migrated dataset; history cleanup can remove them. | Explicit user authorization to discard those values. | User's preservation approval. |
| J4 | File one gardener record row per trial root | Rows of one task in one wake collide on the key `(date, run_id, task)`, and settlement keeps one of them. | A settlement-key change to `CollectionPruneRow` and its readers, which is an ESCALATE trigger. | Fowler. |

## 5. Row #4 - Pipeline-test writers use separate nested cases

- **Scope:** Switch case producers and artifact placement to C1-C5, preserving case separation and bench paths.
- **Files touched:**
  - `backend/idhazh/contracts/pipeline_tests.py`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/common.py`
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
  - `backend/tests/test_named_utility_inputs.py`
  - `backend/tests/test_candidate_pointer.py`
  - `backend/tests/ledger/test_migrate_to_parquet.py`
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

## 6. Row #5 - Named data moves and CSV retires after proof

- **Scope:** Move existing raw files, traces and summary CSV byte for byte into C1 roots, convert the summaries there through row 1's operations, then retire the CSV and the old roots' ownership after C13 proof.
- **Files touched:**
  - `state/pipeline-tests-production-settings/raw/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet`
  - `state/pipeline-tests-no-visual-plan/raw/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet`
  - `state/pipeline-tests-production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests-production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests-no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests-no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests-production-settings/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-00.csv`
  - `state/pipeline-tests-production-settings/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-01.csv`
  - `state/pipeline-tests-no-visual-plan/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-00.csv`
  - `state/pipeline-tests-no-visual-plan/span-rollup/2026/09/29/2026-09-29-36540131911-1-work-01.csv`
  - `state/pipeline-tests/production-settings/raw/item-health/2026/09/29/01a0fb85-c00d-8e8c-a090-3980eafa5cb1.parquet`
  - `state/pipeline-tests/no-visual-plan/raw/item-health/2026/09/29/01a0fb85-bff9-87c8-b881-773892395dff.parquet`
  - `state/pipeline-tests/production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests/production-settings/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests/no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-00.jsonl`
  - `state/pipeline-tests/no-visual-plan/traces/2026/09/29/2026-09-29-36540131911-1-work-01.jsonl`
  - `state/pipeline-tests/production-settings/raw/span-rollup/` (new folder: the migration writes it, and its minted file ids cannot be known in advance)
  - `state/pipeline-tests/production-settings/compact/span-rollup/` (new folder, same reason)
  - `state/pipeline-tests/no-visual-plan/raw/span-rollup/` (new folder, same reason)
  - `state/pipeline-tests/no-visual-plan/compact/span-rollup/` (new folder, same reason)
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
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `TODO/20261003-59-csv-ledgers-left-plan.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/move-a-ledger-to-parquet.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/concepts/glossary.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:** Local, in order: (1) confirm no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml` is queued or running, or pause and name the run; (2) `git mv` each old raw and trace file to its C1 path and each summary CSV to `state/pipeline-tests/<case>/span-rollup/2026/09/29/`, comparing every file's SHA-256 before and after; (3) set the import path to this checkout's `backend/` (M5), then run `backend/utilities/migrate_to_parquet.py` with `--state-dir state/pipeline-tests/production-settings --state-dir state/pipeline-tests/no-visual-plan --ledger span-rollup --month 2026-09`, the runbook's run id and the code commit's sha, through `--plan`, `--write`, `--verify` and `--retire`; (4) run row 2's verifier over both case roots and the bench root for the ledgers their declarations name, month 2026-09; (5) `npm --prefix frontend run test:changed -- --list` and the selected checks, the tests above, `git diff --cached --name-only` against Files touched, and the doc report. Re-derive the named files against the merge base before dispatch instead of trusting this snapshot. CI: the full merge-candidate checks.
- **Oracle:** Each moved raw and trace file has the same SHA-256 at its C1 path, and every summary cell, `unattributed_ms` included, reads back through the door at its case root before any CSV is deleted. This cannot recover a source deleted by an unrelated concurrent writer.

Table M - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| M1 | This row converts the four trial summaries only; the four production summaries are B5. | User's pipeline-test scope. |
| M2 | Plan 59 row "The CSV code no ledger uses any more is deleted" deletes no `span-rollup` file and does not edit `backend/utilities/pipeline_test_ledgers.py`; it deletes `DAY_TREES` after row 2 here lands (G4). Plan 59 row "The person rules on what blocks each ledger left on CSV" carries B5 with both options. Plan 59 already says both; this row deletes its pointer to this row once the trial CSVs are retired. | Fowler; the user's ruling that no CSV cell is lost. |
| M3 | Convert the summaries at their C1 roots, where `compact-trial-span-rollup` governs them. At an old sibling root the migrator refuses span-rollup (I4): no declaration names that root, and no production `compact-span-rollup` exists. | Fowler. |
| M4 | Roll back by reverting this row's pull request, which restores the data, the old roots' ownership and their period paths together. Rows 2 to 4 keep both layouts readable until this row merges. | Fowler. |
| M5 | The runbook's command sets the import path to the `backend/` of the checkout it runs from, as the [agent-notes](../docs/reference/agent-notes.md) entry "Pytest imports the producer; its child process cannot find `idhazh`" shows, so `idhazh` and `utilities` load this checkout's code rather than another checkout's install. The command names no workstation path. | Tooling review (Fowler). |

Table N - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Delete CSV because nothing currently reads it | Lack of a reader is not proof that its values survived. | Explicit approval of cell loss; otherwise use the exact conversion already declared. | User's lossless design approval. |
| N2 | Migrate the four production summaries in this row | They are Plan 59's ruling (B5), and this plan declares no production `compact-span-rollup` that keeps them for ever. | That declaration and its tests, plus the ruling in Plan 59 row "The person rules on what blocks each ledger left on CSV". | Fowler. |
| N3 | Convert at the old sibling roots, then move the output | The migrator refuses there (M3), and naming an old root in a trial declaration claims a folder the trials task owns. | Add the old roots to `compact-trial-span-rollup` and narrow the trials task around them for one migration. | Fowler. |

## See also

- [Migration operations](../docs/how-to/move-a-ledger-to-parquet.md)
- [Ledger persistence](../docs/architecture/contracts/persistence.md)
- [Ledger registry](../docs/architecture/contracts/ledger-registry.md)
- [Retention safeguards](../docs/architecture/publishing/retention.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Local gates](../docs/how-to/run-the-gates.md)
- [Agent notes](../docs/reference/agent-notes.md)
