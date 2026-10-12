# Record the work shards a run dispatched

**Last Updated**: 2026-10-12

**Level**: 5 - a persisted contract changes: `RunPlan` gains a field and `RunRecord.shards` holds the dispatched count ([CLAUDE.md section 6](../CLAUDE.md#6-correction-levels)). The owner settled the design on 2026-10-12 (Tables I and K); execution waits for the user's authorization (Table C, C1).

## 0. Operating contract

Table A - operating contract

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | A manual dispatch starts the operator's worker count while assembly records a recount from the plan, so Hardware and the console band refuse or misread manual runs; each run must record the count it dispatched (known defect "The manifest shard count can differ from the dispatched worker matrix"). |
| A2 | Hard scope - in | Row 1: move `shard_count` out of the command router. Row 2: add the nullable `RunPlan.shards`. Row 3: the plan step decides and records the count, and the fan-out reads only that. Row 4: assembly and the fresh-base rebuild record it, and the Hardware count contract is amended. |
| A3 | Hard scope - out | Table B. |
| A4 | ESCALATE triggers | Table C. |
| A5 | Chosen strategy | Decide the count once, store it on the run's plan, read it everywhere: Move Function, then Expand on `RunPlan`, then a writer correction in place on `RunRecord.shards`. Fowler, 2026-10-12, under the owner's rulings of the same day. |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4; only rows 1 and 2 can be in flight together, and rows 3 and 4 both edit `backend/idhazh/cli.py`, so they run in order. |
| A7 | Source inspected | main at `72569d67`; every receipt below is at that commit. Re-run the dispatch checks of execute-a-plan.md against the execution checkout. |

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table B - exclusions and their cost

| ID | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Rewriting or backfilling the counts of runs recorded before Row 4 lands | Those records keep the count assembly recomputed; a manual dispatch among them stays refused, or shows shards as missing, on Hardware until it leaves the console's widest window | A record of what each past run dispatched; none exists, and observed host rows are not a substitute (Table L, L4) |
| B2 | Rows from two plans under one run id after a full re-run that planned again | Hardware and the band refuse such a run; a re-run that stops before assembly can show two plans as one run | The first step of the known defect "A full re-run that plans again leaves the earlier plan's rows under the same run id", then an owner ruling on its options (Table L, L2 and L3) |
| B3 | A count on the speed benchmark's cut-down plan (`freeze_corpus` in `backend/utilities/runtime_sweep.py`) | The cut keeps the count its plan decided, which nothing reads, because `.github/workflows/measure.yml` never assembles | A benchmark step that assembles, or any reader of the cut's count |
| B4 | A count on pipeline-test plans (`backend/utilities/pipeline_draw.py`) | Their plans read None; the pipeline tests pass their own `--shards` and never assemble | A pipeline-test step that assembles or calls `idhazh shards` |
| B5 | Workers reading the count from the plan instead of `--shards` | One hand-off stays, the plan job's output, which is what the fan-out printed; Table I, I9 holds it | A row that drops `--shards` from the work and record steps and reads `RunPlan.shards` there |
| B6 | A re-run started after the plan artifact expired | The plan artifact's `retention-days` in `digest.yml` ends before GitHub's re-run window does, so such a re-run fails at the download and records nothing; no wrong count is written | Reading the committed plan from the tip when the artifact is gone, as a row of its own |
| B7 | Any change to Hardware, band or `frontend/src/lib/server/payload.ts` arithmetic or wording | None: those readers already treat the value as the run's denominator, and "planned shards" stays true (Table K, K9) | A later wording change with its own design review |

Table C - ESCALATE triggers

| ID | Trigger | Required response |
| --- | --- | --- |
| C1 | The user has not authorized execution | AUTHOR-AND-STOP: every row stays PENDING. |
| C2 | A row needs a persisted change beyond Table G, G1 to G3 and Table K, K5 to K6: another field, a `RunShards` stamp, or a rewrite of committed files | Stop for a Level 5 consultation with the owner (CLAUDE.md section 6). |
| C3 | The dispatch-time search finds an importer of `shard_count`, a caller passing `shards=` to `stage_assemble`, or a caller of `idhazh shards` that the row's `Files touched` does not list | Add it to the row's list and Depends-on before dispatch; never edit an unlisted file silently. |
| C4 | A check passes only by recounting a missing count, by reading observed host rows, or by relaxing a Hardware or band refusal | Stop and report; each would rebuild the defect or overturn a ruling (Tables K and L). |
| C5 | Committed `run.max_parallel` exceeds the largest `shards` dispatch choice when Row 3 starts | Stop; the owner chooses between widening the choice list and lowering the knob. |
| C6 | Observed GitHub behaviour contradicts the re-run facts in Table K, K2 | Report the evidence and re-price Row 4 before continuing. |
| C7 | A scope change, an unresolved advisor conflict, or a cost three times the row's size | Follow [handle-scope-change.md](../docs/how-to/handle-scope-change.md). |

## 1. Status Reckoner

Table D - authoritative execution queue

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Move the shard count formula out of the command router | - | A | PENDING | - | - | - |
| D2 | 2 | Let a run plan carry its dispatched shard count | - | A | PENDING | - | - | - |
| D3 | 3 | Decide the count once in the plan step and fan out from it | 1, 2 | B | PENDING | - | - | - |
| D4 | 4 | Record the plan's count at assembly and in the fresh-base rebuild | 3 | C | PENDING | - | - | - |

## 2. Row #1 - Move the shard count formula out of the command router

- **Scope:** Move `shard_count` unchanged from `backend/idhazh/cli.py` into a new `backend/idhazh/fan_out.py`, so the plan stage can call it without importing the router; no behaviour changes.
- **Files touched:**
  - `backend/idhazh/fan_out.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/digest_assemble.py`
  - `backend/tests/test_plan.py`
  - `backend/tests/pipeline/test_a_stage_reads_its_own_runs_plan.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `TODO/20261012-dispatched-shard-count-plan.md`
- **Acceptance gates - local:** From `frontend/`, `npm run test:changed -- --list`, then `npm run test:changed` (the backend group runs the named tests, ruff and mypy). Focused: `python -m pytest -n 0 backend/tests/test_plan.py -k "shard_count or fan_out or records_the_count" backend/tests/pipeline/test_a_stage_reads_its_own_runs_plan.py backend/tests/workflows/test_digest_publication.py`. Record the selection and its results.
- **Acceptance gates - CI:** The full suite on the merge candidate (CLAUDE.md section 9).
- **Oracle:** This row's value is that behaviour does not change, so what must be able to fail is an importer left on the old path: the existing `shard_count` cases in `backend/tests/test_plan.py` pass with only their import changed, and a search of the tree finds `shard_count` imported from `idhazh.fan_out` and from `idhazh.cli` nowhere. It cannot show which count a run records (Rows 3 and 4).

Table E - Row 1 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| E1 | Move, not copy: one definition in `backend/idhazh/fan_out.py`, whose first sentence is "How many work jobs one run dispatches."; `cli.py` imports it from there. The module holds `shard_count` alone; `shard_of` stays in `backend/idhazh/stages/common.py`. | Fowler, 2026-10-12; CLAUDE.md section 1a (one question per file). |
| E2 | The move is required by Row 3, not tidying: the plan stage needs the formula, and the `backend/idhazh/stages/__init__.py` docstring states that nothing under `stages/` imports the router. | Fowler; `stages/__init__.py` at 72569d67. |
| E3 | The docstring moves verbatim; its wording changes in Row 3, with the behaviour it describes. | Fowler (a commit is structural or behavioural, never both). |
| E4 | `Files touched` comes from a search for `shard_count` over `backend/idhazh`, `backend/utilities`, `backend/tests`, `docs`, `TODO` and `.github` at 72569d67. Functions of the same name in the council, the gardener and the pipeline-test settings are different functions and stay untouched. `docs/architecture/sources/i-feed.md` names the function without its module and stays true. | Search at 72569d67; [author-a-plan.md](../docs/how-to/author-a-plan.md) (a move gets its files from a search). |

Table F - Row 1 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Keep `shard_count` in `cli.py` and import the router from the plan stage | Breaks the rule that stages never import the router, and `cli.py` already imports `stages.plan`, so the two would import each other | A documented exception in `stages/__init__.py` plus a deferred import inside `stage_plan` | Fowler |
| F2 | Put it in `backend/idhazh/stages/common.py` beside `shard_of` | `common.py` already answers several questions; one more answer makes it longer, not clearer | One function moved again when `common.py` is split; no runtime cost | Fowler |
| F3 | Fold the move into Row 3 | Mixes a structural and a behavioural change in one commit | One review of a mixed diff, and a revert that cannot keep the move | Fowler |

## 3. Row #2 - Let a run plan carry its dispatched shard count

- **Scope:** Add the nullable field `RunPlan.shards`, with its stamp, changelog line and fixture, so a plan can record the work shards its run dispatches; nothing writes it yet.
- **Files touched:**
  - `backend/idhazh/contracts/run_plan.py`
  - `tests/fixtures/contracts/run-plan/one-day.json`
  - `backend/tests/contracts/test_run_plan.py`
  - `TODO/20261012-dispatched-shard-count-plan.md`
- **Acceptance gates - local:** The selector as in Row 1. Focused: `python -m pytest -n 0 backend/tests/contracts/test_run_plan.py backend/tests/contracts/test_schema_drift.py backend/tests/contracts/test_changelog_shape.py`. The tests that read the run-plan fixture through `RunPlan` - among them `backend/tests/contracts/test_desks.py`, `backend/tests/workflows/test_bench_targets.py` and every user of `backend/tests/pipeline/_builders.py` - pass unchanged. Record the selection and its results.
- **Acceptance gates - CI:** The full suite on the merge candidate.
- **Oracle:** A run-plan payload with no `shards` key validates with `shards` None, and the fixture carrying `"shards": null` round-trips byte-identically (`test_fixture_round_trips_byte_identically` in `backend/tests/contracts/test_schema_drift.py`). It cannot show that anything writes the field (Row 3).

Table G - Row 2 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| G1 | Declared last in `RunPlan`, after `items`: `shards: int \| None = Field(default=None, ge=1, strict=True, description=...)`. Description: "Work shards this run dispatches, decided once when the plan is made: an operator's dispatch count when one was given, otherwise `shard_count` over this plan's items. Every later job reads it here. Null on a plan written before the count was recorded, which is unknown and never recomputed." | Owner ruling, 2026-10-12 (Table I, I2); Fowler; mirrors `RunShards.shards` in `backend/idhazh/contracts/run_shards.py`. |
| G2 | Stamp: the commit's UTC date, extended to the minute if another `RunPlan` change lands the same day. Changelog entry, one line a field: `change="A plan records the work shards its run dispatches."` and `why="Assembly recounted the shards and missed an operator's dispatch count."`. Drop the `2026-09-02T23:00` entry, so the list keeps four changes and the `2026-08-21T04:00` pointer. | CLAUDE.md section 11; `backend/tests/contracts/test_changelog_shape.py`. |
| G3 | Widening, with no read-side migration code: a plan row filed before the field has no such column and reads None, and no committed file is rewritten. | [schemas.md](../docs/architecture/contracts/schemas.md), "Widening a row ledger writes an empty cell, never a value invented today". |
| G4 | The fixture gains `"shards": null` in sorted key order, because the writer emits every key. The contract test proves the old read by deleting the key from the parsed fixture, as `backend/tests/contracts/test_run_manifest.py` does for its removed cells, and refuses 0, -1, True, 1.5 and "3". | `test_schema_drift.py` at 72569d67; Guardrail #7. |
| G5 | An older build still running - a run triggered at an older commit, or its re-run - skips a newer-stamped plan file of another run with a warning and reads its own plan; `run-plan` is not a published ledger. Reasoned from the code, not measured. | `_stored_or_skipped` in `backend/idhazh/ledger/ledger_files.py` and `ledger.published` in `config/idhazh.json` at 72569d67. |

Table H - Row 2 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Keep the count off the plan and hand the plan job's output to assembly | The owner chose the plan as the one stored place the count is decided and read (Table I, I2) | Priced in Table J, J3 | Owner, 2026-10-12 |
| H2 | Make the field required | Every committed plan row lacks it and would stop reading | A read-side migration that invents a count for every old plan, which the widening rule forbids | schemas.md |

## 4. Row #3 - Decide the count once in the plan step and fan out from it

- **Scope:** The plan step records the operator's dispatch count, or the derived count when none was given, as `RunPlan.shards`; `idhazh shards` prints that recorded count; the workflow hands the operator's input to the plan step and the fan-out reads only `idhazh shards`; the shell clamp goes; a test holds `run.max_parallel` at or below the largest dispatch choice.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/fan_out.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/plan.py`
  - `backend/tests/test_plan.py`
  - `backend/tests/pipeline/test_a_stage_reads_its_own_runs_plan.py`
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_shard_fan_out.py`
  - `docs/concepts/config/run-limits.md`
  - `docs/how-to/run-the-pipeline.md`
  - `TODO/20261012-dispatched-shard-count-plan.md`
- **Acceptance gates - local:** The selector as in Row 1. Focused: `python -m pytest -n 0 backend/tests/test_plan.py backend/tests/pipeline/test_a_stage_reads_its_own_runs_plan.py backend/tests/workflows/test_shard_fan_out.py backend/tests/workflows/test_workflow_inputs.py backend/tests/workflows/test_plan_handoff.py`. Record the selection and its results.
- **Acceptance gates - CI:** The full suite on the merge candidate, including the workflow group.
- **Oracle:** `stage_plan` given a count files that count even where `fan_out.shard_count` over the same items is smaller; given none, it files `fan_out.shard_count`; `idhazh shards` prints the filed count; and the fan-out step turns every dispatch choice it is printed into exactly the shard indexes from 0 to that count minus 1, and refuses anything else. It cannot show what assembly records (Row 4), and it dispatches no live workflow.

Table I - Row 3 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| I1 | Owner ruling, 2026-10-12: a run records the work-shard count its matrix dispatched, and a manual dispatch keeps the operator's choice from the `shards` input. | Owner, 2026-10-12. |
| I2 | Owner ruling, 2026-10-12: the plan step decides the count once and stores it as `RunPlan.shards` (Table G, G1); the fan-out, assembly, the fresh-base rebuild and `idhazh shards` read it there; the shell clamp goes; a test holds `run.max_parallel` at or below the largest dispatch choice. | Owner, 2026-10-12. |
| I3 | `stage_plan(..., shards: int \| None = None)` sets `RunPlan.shards` to `shards` when given, else to `fan_out.shard_count(len(items), run=settings.app.run)` over the plan's final items, after every ceiling. A given count wins even above the formula, because an operator may start more workers than the day earns. | Fowler; the `shard_count` docstring at 72569d67. |
| I4 | Command line: `--shards` keeps `type=int` and loses its default of 1. `plan` passes it as given (absent means derive) and refuses a value below 1 through `parser.error` before any feed is read. `run` passes the given count, or 1, to both its plan and its work, so one process records the one worker it ran. `work`, `record`, `qualify` and `council-shard` read an absent value as 1, as today. | Fowler; the `--shards` argument and its four readers in `cli.py` at 72569d67. |
| I5 | `idhazh shards` prints `RunPlan.shards` of the run `--execution` names; a plan with no count stops through `parser.error`, naming the run; nothing recomputes it. | Fowler; the recount was the defect (Table K, K3). |
| I6 | The `Plan the day` step of `digest.yml`: add `DISPATCH_SHARDS: ${{ inputs.shards }}` to its `env` (blank on a schedule); in its script set `SHARD_ARGS=()`, then `SHARD_ARGS=(--shards "$DISPATCH_SHARDS")` when `${DISPATCH_SHARDS:-}` is not empty, and pass `"${SHARD_ARGS[@]}"` to `run plan` after `"${LIMIT[@]}"`. | The step's own rule at 72569d67: pass dispatch input as data, not interpolated shell code. |
| I7 | The `fanout` step: keep `SHARD_PATTERN='^[1-8]$'`, run `SHARDS=$(python -m idhazh shards --date ... --execution ...)` unconditionally with today's arguments, and keep the guard block and the `shards=` and `matrix=` output lines; delete `SHARDS="${{ inputs.shards }}"`, the empty-input branch and the clamp loop. The work, record, assemble and commit steps do not change. | Fowler; the `fanout` step at 72569d67. |
| I8 | Three checks bound the count to what the workflow can start: the dispatch choice list on the operator side, the config test on the derived side (I10), and the fan-out guard at run time over what Python printed. One shared ceiling is not available, because a dispatch choice list is static YAML; the guard stays as the only runtime check, and a config above the ceiling now fails CI instead of being clamped. | Fowler; author-a-plan.md step 5 (count the mechanisms holding one property). |
| I9 | Harness: `_evaluate_shard_matrix(script, printed)` asserts the step's exact lines and returns the matrix for a printed count, or None where the guard refuses. `test_shard_fan_out.py` covers every dispatch choice, refuses `0`, `9`, `12`, `04`, a blank and non-digits, holds I6 and I7 by reading the two steps, and replaces the derived-12 clamp case with I10. | Fowler; `_harness.py` and `test_shard_fan_out.py` at 72569d67. |
| I10 | Config test: committed `run.max_parallel` in `config/idhazh.json` is at or below the largest `shards` option of `digest.yml`, read from those two named files. | Owner ruling I2; Guardrails #6 and #12. |
| I11 | The `fan_out.shard_count` docstring says the plan step calls it when no operator count is given, and that its answer is recorded on the plan. | Fowler. |
| I12 | Docs: `docs/concepts/config/run-limits.md`, which states the derivation and the operator's count, says the plan step records whichever count the run dispatches; `docs/how-to/run-the-pipeline.md` corrects its worker-count sentence, which still names a ceiling and a default of four, and links to run-limits instead of restating the numbers. | Guardrail #4; both pages at 72569d67. |
| I13 | Tests: in `test_plan.py`, a plan given a count files it, a plan given none files the formula, and `plan --shards 0` is refused before any feed is read; in `test_a_stage_reads_its_own_runs_plan.py`, the two filed plans carry different counts, `shards` prints its own run's count, and a plan with no count is refused naming its run. | Fowler; Guardrail #9. |

Table J - Row 3 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Delete the `shards` dispatch input, so every run derives its count | Removes the operator's choice, which `docs/concepts/config/run-limits.md` and the `run.max_parallel` description promise, and which lets a short test run start every worker the workflow allows | Two commits (workflow, harness, dispatch-input reference) and no persisted change | Owner, 2026-10-12 |
| J2 | Leave the mismatch and document manual runs as unreadable | Hardware and the band keep refusing or misreading every manual run | No work; the console stays wrong for manual runs | Owner, 2026-10-12 |
| J3 | Keep deciding in the workflow and pass `needs.plan.outputs.shards` to `run assemble` and to the commit step | Two call sites to bind; the decision stays in shell; the count lives only in job outputs until `run.json` | Two command-line flags, two workflow edits, one binding test, and another source for `idhazh run` | Owner, 2026-10-12 |
| J4 | Clamp a derived count in Python to a ceiling copied from the YAML | A second spelling of the workflow's ceiling (Guardrail #6) | One config knob and a test binding it to the choice list | Fowler |
| J5 | Refuse a worker whose `--shards` differs from the plan's count | Turns a mislabelled console count into a run that publishes nothing | One guard and one test; I9 already holds the hand-off by reading the workflow | Fowler |

## 5. Row #4 - Record the plan's count at assembly and in the fresh-base rebuild

- **Scope:** Assembly and the fresh-base rebuild record `RunPlan.shards` as `RunRecord.shards`, and so in the `run-shards` ledger; the field description, the manifest stamp and the Hardware count contract say what the value now is.
- **Files touched:**
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/digest_assemble.py`
  - `backend/idhazh/contracts/run_manifest.py`
  - `backend/idhazh/telemetry/publish/console_band.py`
  - `backend/tests/pipeline/test_run_shards.py`
  - `backend/tests/workflows/test_dispatched_shard_count.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `backend/tests/test_plan.py`
  - `docs/architecture/publishing/console-machine.md`
  - `TODO/20260823-known-defects-plan.md`
  - `TODO/20261012-dispatched-shard-count-plan.md`
- **Acceptance gates - local:** The selector as in Row 1. Focused: `python -m pytest -n 0 backend/tests/workflows/test_dispatched_shard_count.py backend/tests/workflows/test_digest_publication.py backend/tests/pipeline/test_run_shards.py backend/tests/test_plan.py backend/tests/contracts/test_run_manifest.py backend/tests/contracts/test_changelog_shape.py backend/tests/contracts/test_schema_drift.py backend/tests/test_console_payloads_producer.py`. Record the selection and its results.
- **Acceptance gates - CI:** The full suite on the merge candidate. No frontend file changes, so the browser groups run only where the selector widens.
- **Oracle:** On the real run-plan fixture filed with a count that differs from `fan_out.shard_count` over its items, the fan-out matrix, the written `run.json` `shards` and the settled `run-shards` row are one number, and assembly with `regenerate_only=True` on the same plan files no new count file. On the Row 3 tree it fails, because assembly still recounts. It cannot settle rows left under one run id by an earlier plan (Table B, B2), nor the counts recorded before this row (B1).

Table K - Row 4 decisions

| ID | Decision | Authority |
| --- | --- | --- |
| K1 | Owner ruling, 2026-10-12: the change is made in place. `RunRecord.shards`, and so `RunShards.shards`, holds the dispatched count from this change on; key, type, ledger schema, settlement and readers stay; the last paragraph of "A narrow recorded shard count" in `docs/architecture/publishing/console-machine.md` is amended when this row lands. | Owner, 2026-10-12. |
| K2 | Owner ruling, 2026-10-12: a full re-run that plans again records its newer plan's count, and the existing settlement keeps that later number; Hardware and the band keep refusing a run whose rows come from two plans; the row mixing is a known defect of its own (Table B, B2). It rests on three facts: GitHub keeps the run id and the commit across re-runs, a partial re-run reuses the plan job's outputs, and the ledger door keeps the highest attempt of each writer. | Owner, 2026-10-12; `backend/idhazh/run_context.py` and `settle_rows` in `backend/idhazh/ledger/raw_files.py` at 72569d67; [GitHub re-run docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs); [actions/runner issue 1961](https://github.com/actions/runner/issues/1961). |
| K3 | `stage_assemble` loses its `shards` parameter and passes `plan.shards` to `build_manifest`, and its docstring says the count is the plan's; the assemble branch of `cli.py` and `preparation` in `digest_assemble.py` stop calling `shard_count`, and the latter drops its import; `build_manifest` keeps its `shards` parameter. A plan with no count records None, and nothing recomputes it. | Fowler; the two recount sites at 72569d67. |
| K4 | The rebuild reads the plan that `preparation` already loads once from the job's own state (`common._load_plan(date, original.identity.run_id)`), so the assemble step and every rebuild attempt record the same number. | `preparation` in `backend/utilities/digest_assemble.py` at 72569d67. |
| K5 | `RunRecord.shards` description: "Work shards this run dispatched: the count its plan decided and its matrix fanned out on, an operator's dispatch count included. It is the denominator for `N shards reported nothing`, and it has to come from the plan: a denominator counted off the same rows as the numerator can never disagree with them. Null when the plan recorded none, or on a manifest written before the cell existed. A record written before YYYY-MM-DD (this row's stamp) holds the count assembly recomputed from its plan, which a manual dispatch could exceed or undercut." | Fowler; CLAUDE.md section 0b. |
| K6 | `RunManifest` stamp: the commit's UTC date, later than its current newest entry. Changelog entry: `change="shards holds the count the plan decided and the matrix dispatched."` and `why="A recount at assembly missed an operator's dispatch count."`; drop the `2026-09-22` entry and keep the `2026-09-20` pointer. No key moves, so every committed `run.json` reads; an older-stamped one takes the existing vertical-count path in `_load_manifest` (`backend/idhazh/stages/common.py`) on its next read, as at every stamp. `RunShards` keeps its stamp and description. | CLAUDE.md section 11; schemas.md (a description edit carries a stamp). |
| K7 | No historical record is rewritten or backfilled, and there is no read-side migration code: no shape moved, and nothing records what a past manual dispatch ran (Table B, B1). | Owner ruling K1; "A narrow recorded shard count" (observed host counts are never substitutes). |
| K8 | Settlement is unchanged (`_settle_run_shards` in `backend/idhazh/ledger/raw_files.py`, `_persist` in `backend/idhazh/telemetry/run_shards.py`): a new run files one row with its dispatched count; a partial re-run files nothing; a re-plan files one correction; the rebuild adds a correction only under that day's count scope and never over existing bytes. | Code at 72569d67; "A narrow recorded shard count". |
| K9 | Readers are unchanged: `shardCounts` in `frontend/src/lib/console/machine/records.ts`, the refusal and `outOf` in `counters.ts` beside it, `_one_run` and `machine_candidates` in `backend/idhazh/telemetry/publish/console_band.py`, and `frontend/src/lib/server/payload.ts`. "planned shards" stays true, because the plan decides the count. Only the word "derived" in the band producer's `MachineFacts` docstring becomes "decided". | Owner ruling K1. |
| K10 | New `backend/tests/workflows/test_dispatched_shard_count.py`, on `tests/fixtures/contracts/run-plan/one-day.json` through `plan` and `isolate_ledgers` in `backend/tests/pipeline/_builders.py`, the real ledger door, the command line and the harness of Table I, I9; no network, no model, no mock. Case a: a plan filed through `plan_stage.plan_writer` with a dispatch choice other than `fan_out.shard_count` over its items - `idhazh shards` prints it, the fan-out yields its shard indexes, `stage_assemble` writes it to `run.json` and the `run-shards` row, and `stage_assemble(..., regenerate_only=True)` files no new count file. Case b: with `GITHUB_RUN_ATTEMPT` at 2, a cut of that plan, its verticals recounted as `freeze_corpus` does, filed by the same writer under the same run id with another dispatch choice, then assembled - `_load_plan` returns the cut, the record and the settled row follow it, and exactly one new raw count file appears. Case c: a plan object with no count, assembled after case a, records None in `run.json` and leaves the settled row at the earlier number. | Guardrail #7; the defect's oracle: a real dispatch fixture with a changed plan distinguishes the dispatched and recomputed counts. |
| K11 | `test_digest_publication.py` files `plan()` with a count that differs from the formula and expects that count in the published `run.json`, so the real fresh-base publication path holds it. `test_run_shards.py` sets each count on the plan instead of passing it to `stage_assemble`. The docstring of `test_the_manifest_records_the_count_it_was_handed_and_never_a_derived_one` in `test_plan.py` says the plan step decides the count. | Fowler. |
| K12 | `console-machine.md`: keep the sentence that observed host count, maximum shard index, current settings and workflow matrix size are never substitutes; replace the rest of that paragraph with what the count is and who decides it, how a partial and a full re-run record it, that records before the stamp keep the recount, and the owner ruling of 2026-10-12. | Owner ruling K1; Guardrail #4. |
| K13 | `TODO/20260823-known-defects-plan.md`: the row and the section of "The manifest shard count can differ from the dispatched worker matrix" read CLOSED with the landing date; the pull request number is read from the merge. | The known-defects plan's convention for a closed row. |

Table L - Row 4 rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Additive: keep a recounted `shards` and add `dispatched_shards` to `RunRecord` and `RunShards` | Two numbers for one fact, one of them with no reader; a new key and a `RunShards` stamp make runs at an older commit fail to read that day's files | Two stored values, a two-value settlement rule, four reader changes, an update to `backend/tests/contracts/test_panel_queries.py`, and a compatibility window as long as GitHub's re-run window | Owner, 2026-10-12 |
| L2 | Record the plan's attempt beside the count, and have readers drop rows filed by earlier attempts | Widens the narrow count row, and still misreads a newer attempt that stops before assembly | One field on `RunShards` and `RunRecord`, the `attempt` cell on two Hardware queries, a band filter and their tests | Owner, 2026-10-12 |
| L3 | Give a re-run that plans again a run id of its own | Changes the run identity every ledger and `run.json` carry; a Level 5 change of its own | The first count named in Table B, B2, then a design consultation | Owner, 2026-10-12 |
| L4 | Fill historical counts from observed host rows | "A narrow recorded shard count" rules observed counts out as substitutes | Nothing to build; it would publish a guess as a record | Owner ruling, 2026-10-11 |
| L5 | Recompute a missing count at assembly | Rebuilds the two-rule defect for any plan without a count | One fallback line, and a second rule that can drift from the first | Fowler |

## See also

- [Fowler advisor](../.github/agents/fowler.agent.md) - contracts and the order of safe changes.
- [What the Hardware route draws](../docs/architecture/publishing/console-machine.md#a-narrow-recorded-shard-count) - the count contract Row 4 amends.
- [Guards, alarms and limits](../docs/concepts/config/run-limits.md) - the run-shape knobs Row 3 updates.
- [Contracts and schemas](../docs/architecture/contracts/schemas.md) - stamps, changelogs and widening.
- [Known defects](20260823-known-defects-plan.md) - the defect this plan closes and the one it files.
- [Author a plan](../docs/how-to/author-a-plan.md) and [execute a plan](../docs/how-to/execute-a-plan.md) - structure and the execution contract.
- [Run the gates](../docs/how-to/run-the-gates.md) - the selector and the focused checks.
