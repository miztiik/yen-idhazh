# Remove workflow-file tests

**Last Updated**: 2026-11-08
**Level**: 2 - test coverage and its documented dependants change.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Remove tests that inspect or execute the contents of workflow files while retaining functional tests of the programs they invoke. |
| Hard scope - in | Every workflow in `.github/workflows/`; direct and shared workflow-file checks, including tests embedded in mixed modules; obsolete workflow-test harness and documentation references. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | 1. A functional test cannot be retained without changing production behavior. 2. A persisted contract, workflow, security boundary, or mandatory platform limit must change. 3. The only feasible solution requires deleting tests of local actions independently of workflow files. |
| Chosen strategy | Remove workflow-dependent assertions and workflow-derived execution; preserve independent application and action tests and test-selection behavior. |
| Execution | One serial row because the shared harness and mixed tests overlap. |

| What is out | Cost of leaving it out | What brings it in |
| --- | --- | --- |
| Editing workflow or local action declarations | Their existing behavior and any errors remain unchanged. | A separate request to change a declaration. |
| Removing standalone tests of application programs or local actions | Those tests retain their maintenance cost. | A separate decision to remove that functional coverage. |
| Adding another workflow-file lint or test gate | Workflow wiring and embedded scripts will not receive equivalent automated validation. | A separate decision to introduce a replacement gate. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates only where delegation pays; parallel N = 1 because all changes share test infrastructure; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

## 1. Status reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Remove workflow-file checks without removing functional coverage | - | A | IN-FLIGHT | - | - | - |

## 2. Row #1 - Remove workflow-file checks without removing functional coverage

- **Scope:** Remove tests dependent on actual workflow files, preserve independently testable behavior, and update the surviving test harness and its documentation.
- **Files touched:** Candidate paths below are the named investigation set, not permission to change files that do not need an edit. Search dependants of any removed symbol or path before editing; include necessary discovered dependants in the same change.
  - `backend/tests/workflows/_harness.py`
  - `backend/tests/workflows/test_a_job_that_plans_nothing_records_its_machine.py`
  - `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`
  - `backend/tests/workflows/test_ci_selection.py`
  - `backend/tests/workflows/test_commit_script.py`
  - `backend/tests/workflows/test_corpus_squash_due.py`
  - `backend/tests/workflows/test_council_job_timeouts.py`
  - `backend/tests/workflows/test_crash_trace.py`
  - `backend/tests/workflows/test_daily_commit_steps.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `backend/tests/workflows/test_digest_recovery.py`
  - `backend/tests/workflows/test_dispatched_shard_count.py`
  - `backend/tests/workflows/test_encoder_publisher.py`
  - `backend/tests/workflows/test_extra_publishers.py`
  - `backend/tests/workflows/test_gardener_crash_trace.py`
  - `backend/tests/workflows/test_gardener_workflow.py`
  - `backend/tests/workflows/test_inline_python_imports.py`
  - `backend/tests/workflows/test_ledger_door_jobs.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/workflows/test_model_server_jobs.py`
  - `backend/tests/workflows/test_pinned_versions.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py`
  - `backend/tests/workflows/test_plan_handoff.py`
  - `backend/tests/workflows/test_plan_publication.py`
  - `backend/tests/workflows/test_prune_push.py`
  - `backend/tests/workflows/test_publication_conflict.py`
  - `backend/tests/workflows/test_publish_decision.py`
  - `backend/tests/workflows/test_publish_ordering.py`
  - `backend/tests/workflows/test_shard_fan_out.py`
  - `backend/tests/workflows/test_staged_paths.py`
  - `backend/tests/workflows/test_state_from_the_tip.py`
  - `backend/tests/workflows/test_stdlib_only_programs.py`
  - `backend/tests/workflows/test_telemetry_cli.py`
  - `backend/tests/workflows/test_triggers.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/test_worker_ledgers.py`
  - `backend/tests/workflows/test_workflow_inputs.py`
  - `backend/tests/contracts/test_gardener_plan_matrix.py`
  - `backend/tests/council/test_metrics_sink.py`
  - `backend/tests/test_drift.py`
  - `backend/tests/test_evidence.py`
  - `backend/tests/test_selected_encoder_comparison.py`
  - `backend/tests/test_story_runner.py`
  - `backend/tests/test_summarize.py`
  - `services/feed-ingest-plan/test/feed-ingest-plan-workflow.test.ts`
  - `tools/summary-eval/summary_eval_tests/test_manual_workflow.py`
  - `tools/summary-eval/summary_eval_tests/host-profile-bridge.ts`
  - `backend/idhazh/ledger/staging.py`
  - `frontend/scripts/test-scope.ts`
  - `pyproject.toml`
  - `docs/how-to/run-the-gates.md`
  - `docs/reference/ci-dispatch-inputs.md`
  - `docs/reference/github-actions.md`
  - `docs/reference/benchmarks/push-retry-tests.md`
  - `docs/reference/benchmarks/what-the-suite-costs.md`
  - `docs/reference/benchmarks/what-the-suite-paid-to-re-read-the-archive.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/publishing/console-payloads.md`
  - `docs/architecture/publishing/idhazh-gardener.md`
  - `docs/architecture/publishing/llm-council.md`
  - `docs/architecture/sources/item-health.md`
  - `docs/concepts/config/model-file.md`
- **Implementation:**
  1. Search all test roots for workflow paths, workflow readers, indirect bridge calls, parameterized workflow lists and shared harness helpers. Classify each test or assertion by whether it depends on workflow-file contents, rather than by its filename or marker.
  2. Remove workflow-content assertions and tests that load or execute commands extracted from workflow files. For mixed tests, retain the independent functional assertions; separate them where necessary without adding substitutes that merely restate workflow contents. Preserve standalone selector tests that use workflow paths as input values.
  3. Remove unused workflow-reader code and constants only after checking every remaining harness consumer. Keep helpers still used by functional tests. The named reader currently includes an absent `spacy-tests.yml`; do not recreate or rename a workflow to satisfy it.
  4. Remove or correct references to deleted tests and obsolete claims of workflow verification in the owning docs, source comments and test-selection configuration. Retain historical benchmark evidence as history, but do not present removed tests as current gates. Do not edit `CLAUDE.md` or `AGENTS.md`.
  5. Confirm no persisted payload or config shape changes. No workflow, local action, runtime behavior, dependency or replacement gate is introduced.
- **Acceptance gates:** Locally, inspect the diff and run the applicable existing lint and type checks from `docs/how-to/run-the-gates.md`; collect the retained affected Python and Bun tests with their existing runners and verify no deleted target is selected. Run a focused retained test only if debugging requires it. In CI, run the existing full merge-candidate suite. Do not dispatch data-writing workflows for this change.
- **Oracle:** Review every test-root match for a workflow-file path or workflow reader and trace indirect helper calls; each remaining match must be either a functional selector test using a path as data, a non-test production reference, or a test independent of workflow contents. This review cannot prove that the retained workflows are correctly wired or that their inline commands work on a hosted runner.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Apply the same rule to every workflow, including shared and mixed tests. | Request scope |
| 2 | Preserve tests of application behavior and local actions that do not depend on workflow-file contents. | Functional coverage boundary |
| 3 | Remove only dead harness and documentation references; retain existing selection behavior and CI suites. | Existing test architecture |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Delete the entire workflow test directory. | It contains real application and utility tests. | Loss of functional regression coverage and later reconstruction of tests. | Functional coverage boundary |
| 2 | Replace workflow tests with a new workflow linter. | It preserves the file-testing strategy this plan removes. | A dependency and a new gate to maintain. | Request scope |
| 3 | Keep workflow checks only for publication or safety. | It leaves selected workflow files under the same testing strategy. | Continued maintenance of those checks; reverting the selection requires a separate decision. | Request scope |
