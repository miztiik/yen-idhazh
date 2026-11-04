# UniEval API integration plan

**Last Updated**: 2026-11-04
**Level**: 5 - API implementation complete; workflow integration waits for its named prerequisites.

## 0. Operating contract

Table A - Intent and execution

| Id | Field | Direction |
| --- | --- | --- |
| A1 | Intent | Produce all four UniEval scores for the exact generated source/summary pair used by HHEM, checking the complete supplied source without shortening the saved summary. Relevance uses an independently supplied reference summary. |
| A2 | Hard scope - in | A real UniEval router/worker; native four-score contracts; one required reference-summary input in the existing summary workflow; report integration and live proof. |
| A3 | Chosen strategy | Extend the shared app with an independent worker. Default to all-source-window consistency, original fluency, full-source coherence and full-reference relevance under Table D. Reuse the generation receipt; never give the reference to generation. |
| A4 | Inherited design | The [server lifecycle plan](20261103-pipeline-server-lifecycle-plan.md), sections 0.1-0.5, owns server addresses, model-file selection and its default, generation handoff, machine APIs, logs and artifacts. This plan specifies only the UniEval extension. |
| A5 | Delivery | Two PRs: a usable real API, then workflow/report integration. The API PR does not claim workflow completion; neither PR ships a placeholder scorer. |
| A6 | Start condition | Verify Table C's relevant merged prerequisites and materialize Table D's declarations before logic. Refresh file inventories against those merged contracts; serialize changes to files still in use by the prerequisite plans. |
| A7 | Read rule | New service and workflow data are same-run artifacts, not inputs to later runs. Update their native readers before writers in the same PR; keep no old-route alias, dual schema or legacy scorer fallback. Do not change committed ledger contracts. |
| A8 | Verification | Offline checks prove validation, composition, score retention and process ownership. Only real model requests in the registered summary workflow prove the delivered capability; no capacity study or score threshold gates it. |
| A9 | ESCALATE | 1. The declared model, calculation, four required dimensions or frozen HHEM runtime must change. 2. The reference must be generated/substituted, another workflow/server or committed payload must change, or article text needs another destination. 3. The merged prerequisites cannot support this scope. Context-limit partial results never authorize a reduced success contract. |
| A10 | Execution | One maintainer; parallel N = 1 because the API and integration rows share native contracts, process handling and gate documentation. |
| A11 | Protected files | Do not modify `CLAUDE.md` or `AGENTS.md`. Keep approval narratives and personal attributions out of code and documentation. |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan; parallel N = 1 because the rows share integration files; honor the ESCALATE triggers in section 0.

Table B - Scope boundaries

| Id | Exclusion | Cost of leaving it out | What brings it in |
| --- | --- | --- | --- |
| B1 | Migrating or deleting `.github/workflows/ai-pipeline-tests.yml` and `.github/scripts/serve-evaluator.py` | Their old UniEval implementation remains separate; it is inspection evidence, not the new API's runtime dependency. | A separately named retirement or migration. |
| B2 | Changing production digest, feed ingestion, HHEM scoring or summarization algorithms | Their existing behavior and score meanings remain unchanged. The lifecycle plan, not this extension, owns the feed migration. | A separate behavior requirement. |
| B3 | A published dashboard, ledger fields, quality bands or a combined quality score | Operators receive distinct evaluator results in the existing report, not a new publication rule or a claim that the scores are interchangeable. | A separate content or reporting decision. |
| B4 | A service framework, new logging policy or capacity/quality study | No plugin system, model-capacity promise or measured quality claim ships. | A concrete requirement that prices that additional work; functional failures are fixed in the real execution path. |

Table C - External prerequisites, referenced by row title

| Id | Prerequisite | Required before | Supplied boundary |
| --- | --- | --- | --- |
| C1 | `TODO/20261103-standardize-typescript-metadata-plan.md`: "Define shared event and operation metadata", "Convert the planner and every planner caller", and "Convert host profiling without breaking Python control" | Adopting machine APIs or TypeScript operation metadata in row 2 | Use the relevant merged schemas and helpers. Do not copy the in-flight field names or introduce Python machine collection. |
| C2 | Server lifecycle plan: "Serve HHEM and llama through one FastAPI application" | Row 1 | The composed app, explicit router selection, native Python identity/error contracts, real readiness and shared logging. |
| C3 | Server lifecycle plan: "Serve TypeScript APIs together in the feed workflow" | Row 2 | The shared Bun machine APIs and `config/hono-server.json`; no UniEval-specific collector or Bun listener. |
| C4 | Server lifecycle plan: "Deliver the live summary-eval-tests workflow" | Row 2 | The named workflow, selected summarizer, generation receipt, phase ownership and HHEM-only live proof. This prerequisite must finish without UniEval; its report may say UniEval was not run. It does not depend on either row below. |

Table D - Selected model, source handling and score meanings

| Id | Item | Declaration | Limit or verification |
| --- | --- | --- | --- |
| D1 | Existing summarization weights | Retain the checkpoint selected by upstream `SumEvaluator`, not the separate factuality-only checkpoint. Pin reference code to `d33e7b6cfebe97b2bafe435adbd818230d5a416a` and model/tokenizer files to `ed8da5a8aa01b19d49a5f8738d382ced54b73ad0`. Required files are `config.json`, `pytorch_model.bin`, `special_tokens_map.json`, `spiece.model`, `tokenizer.json` and `tokenizer_config.json`. | These revisions and filenames were verified from upstream metadata, not by loading weights. Named downloads total about 3.14 GB; this is download size, not a RAM forecast. Fetch only the named files, never optimizer/training state. Row 1 verifies actual loading and freezes required sentence-splitter resources in the existing model environment. |
| D2 | Four dimensions and values | Return exactly `fluency` (natural wording), `coherence` (logical flow in the source/summary pair), `consistency` (support for summary claims) and `relevance` (agreement with the supplied reference summary). Use pinned question formats, native sentence splitting and Yes/No normalization. Values are finite from zero to one; keep original precision until display. | All four are required for completion. No overall grade, chunk-support percentage or important-fact coverage claim is produced. The factuality-only model returns consistency alone with different weights; it cannot provide this four-score capability. |
| D3 | API mode | Optional strict, non-null `consistency_source_mode` accepts `all_source_windows` or `full_source_prompt`; omission uses committed default `all_source_windows`. Return the resolved mode with every scored result. | No retrieved-passage, clipped-prefix, automatic-switch or summary-shortening mode. The control affects consistency only; the remaining dimensions keep D2's calculations. No alternate source/summary or comparison flag is needed. |
| D4 | Startup controls | Declare initial `max_input_tokens=4096` total model input units, `source_window_tokens=512` target source units per window and `source_overlap_tokens=64` shared source units between neighboring windows. Count templates, texts and special tokens together. | These are provisional config defaults, not accuracy/capacity measurements. The larger total allowance is intended for complete coherence/reference prompts while consistency keeps shorter windows. Verify it through the real CPU workflow; adjust committed settings from actual execution, never through an automatic fallback or hidden clipping. |
| D5 | All-source window plan | Build overlapping original-source spans with the actual tokenizer. The effective source budget is the smaller of the configured target and the space remaining after the template, special tokens and longest summary sentence. Re-tokenize every final prompt without clipping; require full source-span coverage, including its end. | Record actual budget/spans; require overlap below the effective budget. If no plan fits, or a sentence itself cannot fit, return an explicit dimension error rather than shortening text, dropping a sentence or skipping a window. |
| D6 | Segmented consistency | Internally split the complete summary into native sentence units. Score every sentence against every planned source window. After every required pair completes, take the best window score for each sentence, then average those sentence scores without scoring-time rounding. | Do not take one best window against the whole summary: different sentences may be supported in different sections. This calculation checks all windows but cannot combine evidence split across windows and can overlook contradictions outside the best match. Label it as segmented, not original whole-source UniEval. |
| D7 | Full-source consistency | For `full_source_prompt`, pair each complete summary sentence with the entire supplied source and use the original sentence mean. Admit no clipped prompt. | This preserves the original calculation and cross-passage context when it fits. CPU/RAM cost and judging accuracy at longer inputs are not established by increasing the setting. Oversized work gets a named error, not a change to the requested mode. |
| D8 | Fluency, coherence and relevance | Fluency uses native summary-sentence scores and their mean, without article windows. Coherence uses one unchanged full-summary/full-source prompt. Relevance uses one unchanged full-summary/full-reference prompt; it does not compare the answer to the article instead. | Oversized complete prompts produce `COHERENCE_INPUT_TOO_LONG` or `RELEVANCE_INPUT_TOO_LONG`, null affected scores and an error-status partial result retaining completed dimensions. Do not average these dimensions across windows, select excerpts or label fewer than four completed scores as complete. |
| D9 | Completion and failures | Plan counts before scoring and retain validated progress in the parent. A dimension receives a score only after all of its required work finishes. An incomplete consistency matrix has no aggregate, even if an interim maximum is high. | Preserve completed dimensions and the other evaluator's result. Unknown/uncomputed values remain null; an actual computed zero remains data. Malformed input is refused before model work; dimension context failures do not prevent independent admissible dimensions from finishing. |
| D10 | Evidence and proof | The [original evaluator paper](https://arxiv.org/abs/2210.07197) and pinned code define native behavior. A [long-document study](https://arxiv.org/html/2511.07689v1#S3.SS2) uses retrieved evidence and a maximum-then-mean calculation with factuality-only weights. | That study does not validate these summarization weights or the all-window calculation. No verified UniEval-specific larger-input accuracy or runner-capacity result was found. Real execution must establish capability; it is not a quality certificate or a separate study gate. |
| D11 | Independent reference | Require nonblank UTF-8 `reference_summary_text` from the operator, supplied for that source before generation. Capture its SHA-256 identity from the bounded platform event; do not send its text to the summarizer. Keep it unchanged for evaluation and escaped reporting. | No generated-answer/self-reference fallback, source-as-reference substitution or automatic reference generation. Independence is input provenance, not string inequality: an independently supplied reference may happen to equal the generated answer. Missing/invalid reference prevents generation/scoring rather than silently dropping relevance. |

Table E - Inputs, native ownership and result meaning

| Id | Surface | Contract |
| --- | --- | --- |
| E1 | Native ownership | UniEval's Pydantic models live in `services/hhem-evaluator/src/hhem_evaluator/contracts/`, alongside the existing transient service contracts. Extend the main plan's `summary_eval_pipeline/contracts.py` for combined same-run evidence, importing native evaluator results rather than copying their fields. Version/changelog changed models and update every named reader/writer together. No backend, TypeScript or ledger copy is introduced. |
| E2 | API input | Add `POST {API_PREFIX}/summary-eval-unieval` under the merged native prefix. Require D11's reference alongside nonblank UTF-8 `source_text` and `summary_text`, unchanged by validation. Add D3's omittable control and reuse optional native `request_id`/`correlation_id` rules. Accept no title, URL, model selector, path, alternate summary or extra full-source text. |
| E3 | API result | A body-free native result contains `version`, `status`, `execution_id`, `request_id`, `correlation_id`, `reference_summary_sha256`, `model`, `worker`, `effective_settings`, `scores`, `work`, `timings_ms` and `errors`. Compute the reference hash from its exact UTF-8 input. `model` records configured/loaded asset identities, reference-code revision and observed library versions; reuse the native worker identity. `scores` has D2's four nullable fields. `effective_settings` records D3-D4 and D5's budget. `work` has per-dimension planned/completed counts, sentence/window counts and source spans as zero-based, end-exclusive Unicode code-point offsets. Unobserved values stay null; no input text or generic events are scores. |
| E4 | Score and error truth | `complete` requires all four dimensions with valid outputs and no error; `partial` retains at least one completed dimension; `failed` has none. Apply D8-D9 without making any dimension optional to obtain success. Reject missing, duplicate, nonfinite, out-of-range or wrong-cardinality replies. Return safe dimension errors with an error HTTP status, including 400 for context/input limits, 504 for evaluation timeout and the existing native process/model failure policy. Read error-status bodies to preserve completed work. |
| E5 | Configuration and assets | `config/unieval-evaluator.json` owns D's assets, controls, model-protocol settings and process deadlines; `config/fastapi-server.json` owns listener/router selection. Keep the existing development-only selection mechanism and its removal condition, not another enable flag. Use the existing frozen T5 model/tokenizer libraries and selected weights, with pinned upstream behavior as reference, not an external server/checkout dependency. Freeze the required sentence splitter and named resources with their cost. Scoring uses local assets; request text cannot select code, files, models or destinations. |
| E6 | Model execution and readiness | One independently owned process performs UniEval scoring off the HTTP event loop. HHEM retains its own worker, admission and result state; no server-wide scoring lock is added. Lifespan owns enabled workers; readiness identifies the actual loaded component and owned service instance. A failed UniEval component must not erase HHEM's ready state or result. Cancellation, parent loss and shutdown stop and join the actual owned process within configured waits; cancelling a thread future is not exit evidence. Reuse applicable process primitives without turning HHEM into a generic evaluator framework. |
| E7 | Generated-pair handoff | Extend the existing native generation receipt with `reference_summary_sha256`, captured before the model call; never include reference text in that call. Verify current run/attempt, selected/loaded summarizer, final answer, source identity and the reference hash against the bounded event and UniEval response. Both evaluators use the unchanged generated pair; only UniEval also receives the reference. Update receipt readers/writer/version together, not a second receipt format. No regeneration, stale result or supplied-answer fallback. |
| E8 | Workflow outcome | Failed, absent, empty, incomplete or mismatched generation leaves both evaluators explicitly not run, without scores or durations. Otherwise retain each evaluator's real outcome independently, including completed zero scores, completed dimensions and original errors. Combined success requires the main plan's generation, measurement and confirmed-cleanup conditions plus both complete evaluators. When required work fails, the workflow is partial if either evaluator has a completed score, otherwise failed. One failed evaluator cannot erase the other's result or make the workflow successful. Keep cleanup errors separate. |
| E9 | Diagnostics and disclosure | Reuse the main plan's CloudEvents stderr/file path, named logs and default retention. Emit safe identities, counts and outcomes, never source, generated summary, reference text, raw model diagnostics or another event file. Mirror failure warns without cancelling scoring. Keep the answer in its declared generation result; render input/reference disclosures as escaped literal report text read from the bounded event, never diagnostic logs. |

## 1. Status Reckoner

Table F - PR sequence

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 1 | Add a real UniEval route to the Python API | - | A | DONE #1909 | didactic-memory | #1909 | - |
| F2 | 2 | Run UniEval in the existing summary workflow | 1 | B | IN-FLIGHT - live proof pending | unieval-workflow-integration | - | - |

## 2. Row #1 - Add a real UniEval route to the Python API

- **Scope:** Ship Table D's real full-source scorer through the shared app with native results, independent process ownership and focused offline coverage.
- **Correction level:** 5; execute only after C2 and the plan's execution authorization; do not substitute another model, prompt or reduction.
- **Files touched - target inventory to confirm against merged C2:**
  - `services/hhem-evaluator/pyproject.toml`
  - `services/hhem-evaluator/uv.lock`
  - `services/hhem-evaluator/src/hhem_evaluator/__main__.py`
  - `services/hhem-evaluator/src/hhem_evaluator/serve_api.py`
  - `services/hhem-evaluator/src/hhem_evaluator/guard_local_requests.py`
  - `services/hhem-evaluator/src/hhem_evaluator/unieval_router.py`
  - `services/hhem-evaluator/src/hhem_evaluator/control_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/dispatch_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/fail_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_model.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_model_assets.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_unieval_resources.py`
  - `services/hhem-evaluator/src/hhem_evaluator/load_unieval_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/maintain_unieval_worker.py`
  - `services/hhem-evaluator/src/hhem_evaluator/plan_unieval_windows.py`
  - `services/hhem-evaluator/src/hhem_evaluator/prepare_unieval_resources.py`
  - `services/hhem-evaluator/src/hhem_evaluator/reduce_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/run_worker.py`
  - `services/hhem-evaluator/src/hhem_evaluator/score_unieval.py`
  - `services/hhem-evaluator/src/hhem_evaluator/unieval_worker.py`
  - `services/hhem-evaluator/src/hhem_evaluator/watch_worker_parent.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_health.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_contract.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_event.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_contract.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_error.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_recording.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_request.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_result.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_worker_message.py`
  - `services/hhem-evaluator/tests/test_server_events.py`
  - `services/hhem-evaluator/tests/test_settings.py`
  - `services/hhem-evaluator/tests/unieval_cases.py`
  - `services/hhem-evaluator/tests/test_unieval_contracts.py`
  - `services/hhem-evaluator/tests/test_unieval_api.py`
  - `services/hhem-evaluator/tests/test_unieval_scoring.py`
  - `services/hhem-evaluator/tests/test_unieval_reduction.py`
  - `services/hhem-evaluator/tests/test_unieval_windows.py`
  - `services/hhem-evaluator/tests/test_unieval_worker.py`
  - `services/hhem-evaluator/scripts/prepare-unieval-resources.py`
  - `services/hhem-evaluator/scripts/capture-unieval-recordings.py`
  - `tests/fixtures/unieval-evaluator/model-inputs.json`
  - `tests/fixtures/unieval-evaluator/model-predictions.json`
  - `tests/fixtures/unieval-evaluator/model-identity.json`
  - `config/unieval-evaluator.json`
  - `config/fastapi-server.json`
  - `.github/workflows/ci.yml`
  - `docs/architecture/evaluation/unieval-api.md`
  - `docs/architecture/evaluation/local-model-api.md`
  - `docs/reference/unieval-api.md`
  - `docs/reference/fastapi-server.md`
  - `docs/how-to/run-unieval-evaluation-api.md`
  - `docs/architecture/contracts/identity.md`
  - `docs/how-to/run-the-gates.md`

Table G - API tasks

| Id | Task | Completion condition |
| --- | --- | --- |
| G1 | Materialize Table D before scoring logic. | Declare controls, selected assets, score/result invariants and native sentence-splitter resource pins. Verify locked CPU compatibility without upgrading HHEM. Prepare only named tokenizer/splitter resources before offline tests, using lightweight frozen dependencies without Torch/weights; never download inside pytest. Record algorithm rationale on the architecture page and exact API/config fields on the reference page. No model/scoring-choice row is handed to implementation. |
| G2 | Declare E's request, result, worker packets and settings. | Strict validation rejects undeclared fields/invalid outputs without echoing input. Replies identify request, worker generation, dimension, sentence and source span so duplicate/stale cells cannot complete a score. The result reader preserves partial dimensions under E4 before a writer emits them. |
| G3 | Load the real selected model and implement D's calculations. | Use the existing official T5 loader/tokenizer and CPU runtime; preserve pinned prompt, sentence and Yes/No rules with native-parity fixtures. Add only the declared window planning/reduction, not a model implementation. No dynamic checkout imports, dependency shim, fabricated text, fallback tokenizer/retrieval, source clipping or zero-on-missing result. Do not load models for disabled routes. |
| G4 | Register the router and independent worker in the merged app. | Implement E6 and E9 with explicit lifespan ownership and component readiness. Keep routing separate from scoring. A disabled component does not import/load its model; a scoring failure does not block unrelated health or destroy another evaluator's completed state. |
| G5 | Capture bounded fixtures and test actual composition. | The named capture script uses D1 and project-authored source/answer/reference cases, recording tokenizer plans, predictions and identity together. Offline tests use real tokenizer planning, prompt-fit checks, four-score/native parity and app/worker cleanup with local resources and recorded model-call responses. Cover tail evidence, different windows supporting different sentences, overlap, exact input limits, oversized sentences/reference, unavailable dimensions, failed cells and real zeros. No fabricated predictions, network reads or HTTP listeners in ordinary tests. |

- **Acceptance gates - local:** Inspect `npm run test:changed -- --list` from `frontend/`. Follow the merged [service gate guide](../docs/how-to/run-the-gates.md#independent-python-service-contracts) for frozen Ruff/mypy. Combine the new contract/window/scoring/API/worker modules with affected API/lifetime checks in one pytest selection. Verify every source span and every required matrix cell, not a whole-summary best-window shortcut. Keep Windows socket-guard limits assigned to Linux CI.
- **Acceptance gates - CI:** The existing isolated job prepares the named lightweight resources, then runs the full service suite offline without the model extra or weight downloads. Preserve HHEM results/lifecycle checks; selected checks do not replace merge-candidate CI.
- **Oracle:** The actual app/worker matches all four native scores on a fitting recorded case; a multi-window case yields the exact mean of completed sentence maxima and full source coverage. Failed cells or oversized coherence/reference prompts preserve other completed dimensions without reporting completion. Worker exit is confirmed. This proves calculation/process correctness, not live model loading, factual accuracy or runner capacity.

Table H - API decisions

| Id | Decision | Basis |
| --- | --- | --- |
| H1 | Reuse the shared app and native Python contracts; do not generalize the HHEM scorer. | C2 and E1-E6. Shared transport and lifetime are reusable; HHEM window semantics are not UniEval semantics. |
| H2 | Default to all-source-window consistency, without cutting the summary. | D3-D6. Every source section is scored for every summary sentence; retrieval does not provide that coverage. |
| H3 | Require four scores with an independent reference, retaining native non-consistency calculations. | D2 and D8-D11. Source-window averaging cannot manufacture coherence/relevance, and a missing required dimension is not complete. |

Table I - API alternatives not selected

| Id | Alternative | Why not selected | Cost to take it | Basis |
| --- | --- | --- | --- | --- |
| I1 | Mount the old script or add its standalone server as a dependency | Imports its separate listener, collector, logging, shim and invalid fallback behavior. | Separate operational ownership and replacement of the invalid failure paths. | A3-A4, B1 and Table D. |
| I2 | Add a placeholder route or lock all evaluators behind one worker | The former provides no capability; the latter couples cancellation and readiness across engines. | A disposable implementation, or a shared scheduling/result protocol not needed for independent workers. | A5 and E6. |
| I3 | Ship `retrieved_source_passages` or a clipped-prefix default | Selected passages or a source prefix do not satisfy every-section checking. | A retrieval dependency, separately named score meaning and an explicitly reduced coverage promise. | A1 and D3-D6. |
| I4 | Synthesize coherence from window scores | No declared window reduction preserves native full-source coherence. | A new metric and its evidence, not a field renamed to the existing dimension. | D8. |

## 3. Row #2 - Run UniEval in the existing summary workflow

- **Scope:** Run both real evaluators on the existing generated pair and report their distinct outcomes without another workflow or generation path.
- **Correction level:** 3 under row 1's settled contracts; pause if an additional model, scoring or native-contract design change is needed.
- **External prerequisites:** C1, C3 and C4; row 1 supplies the real API. None of those upstream rows waits for this extension.
- **Files touched - target inventory to refresh after C4:**
  - `.github/workflows/summary-eval-tests.yml`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/contracts.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/control.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluate_pair.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/generation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/inputs.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/failures.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/http.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/services.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/serve_api.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/settings.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/run.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_models.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_task.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/preparation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phases.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_result.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_services.py`
  - `config/fastapi-server.json`
  - `config/summary-eval-tests.json`
  - `services/hhem-evaluator/tests/pipeline_cases.py`
  - `services/hhem-evaluator/tests/owned_service_child.py`
  - `services/hhem-evaluator/tests/test_manual_workflow.py`
  - `services/hhem-evaluator/tests/test_generation_handoff.py`
  - `services/hhem-evaluator/tests/test_pipeline_evaluation.py`
  - `services/hhem-evaluator/tests/test_pipeline_lifetime.py`
  - `services/hhem-evaluator/tests/test_pipeline_report.py`
  - `services/hhem-evaluator/tests/test_pipeline_preparation.py`
  - `services/hhem-evaluator/tests/test_evaluator_response_binding.py`
  - `services/hhem-evaluator/tests/test_unieval_workflow.py`
  - `services/hhem-evaluator/tests/test_unieval_workflow_fixture.py`
  - `services/hhem-evaluator/tests/test_workflow_outcomes.py`
  - `services/hhem-evaluator/tests/test_workflow_health_isolation.py`
  - `tests/fixtures/hhem-evaluator/pipeline-evidence.json`
  - `tests/fixtures/unieval-evaluator/workflow-inputs.json`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
  - `docs/how-to/run-the-gates.md`

Table J - Workflow tasks

| Id | Task | Completion condition |
| --- | --- | --- |
| J1 | Extend the existing combined evidence and control readers before writers. | Replace the not-run marker with typed evaluator results, resolved mode, complete-source work counts and all four dimensions. Declare D11's reference identity before writing combined evidence. Record actual readiness/exit for each worker. Preserve generation/measurement evidence and reject success when any dimension is missing. |
| J2 | Add the independent reference input and make E7's real requests. | Add a required reference-summary textbox to the existing workflow; update the bounded input reader and named workflow tests together. Capture it before generation but never include it in generation instructions. HHEM/UniEval still receive the identical generated pair; only UniEval gets the reference. Verify hashes/request identities and all generation-refusal cases. Preserve the inherited model-file default and one summarizer per dispatch; no repository resolver or second generation. |
| J3 | Run independent evaluators after confirmed summarizer shutdown. | Enable both workers on the shared app and collect their outcomes independently; an exception must not cancel or discard a sibling's completed response. If real execution cannot sustain concurrent workers, change to explicit stop/start evaluation phases on that same app/address and same-run receipt. Retain the failed run honestly; add no automatic resource probe, restart daemon or hidden retry-to-success path. |
| J4 | Extend report and failure handling, not the publication model. | Show the selected/loaded summarizer, generated answer and independent reference separately from evaluator identities. Display every D2 score, actual consistency mode, source/sentence counts and declared limitations. Missing coherence/relevance keeps its reason and partial status. Retain completed HHEM/UniEval work and separate cleanup errors. Keep diagnostics body-free; no invented grade or relabelled published metric. |
| J5 | Finish and inspect the real registered workflow. | Acquire row 1's named assets in the existing preparation phase. Preserve normal artifact uploads on success/failure, error/cancellation log uploads and default retention. Record the source revision, actual run link and result; remove E5's development-only exclusion after that proof, retaining normal per-phase router selection. Fix failures in these real tasks; offline recordings or workflow registration cannot complete the live proof. |

- **Acceptance gates - local:** Use the shared selector and frozen workflow lint/type commands from the gate guide. One selection covers `test_generation_handoff.py`, `test_pipeline_evaluation.py`, `test_pipeline_lifetime.py`, `test_pipeline_report.py` and `test_manual_workflow.py`. Prove exact-pair/reference binding, rejection of missing reference before generation, reference exclusion from generation, all-four completion, valid zero scores, incomplete dimensions, sibling failures and escaped disclosures. Use real code and recorded model-call responses.
- **Acceptance gates - CI:** Existing service and affected named-workflow suites on the merge candidate. Keep ordinary tests offline and model-free; do not add a quality threshold or resource-capacity gate.
- **Live proof:** Dispatch the existing workflow with the independent reference and one summarizer. Use a named source needing multiple windows, with tail evidence and a complete native coherence prompt longer than the upstream 1024-token cutoff but within the configured total allowance. Prove all four actual scores, full span/pair completion, reference isolation and worker exit. A partial/three-score run or an unexercised larger setting cannot complete this row. Context-failure cases remain focused tests. Fix real capacity failures through declared settings or visible service phases, not clipping or a separate study. Each dispatch generates once; no model matrix/loop.
- **Oracle:** One real run binds complete HHEM and all four UniEval scores to the current generated pair and independent reference identity, confirms multiple source windows with every planned pair completed, exercises the longer native coherence prompt and confirms owned-worker exit. Partial-result retention is proved by the focused tests, not substituted for this successful run. This proves execution, not cross-window reasoning, factual accuracy or a performance target.

Table K - Workflow decisions

| Id | Decision | Basis |
| --- | --- | --- |
| K1 | Extend the new summary workflow only after its HHEM-only delivery. | C4. This avoids duplicate workflows and a dependency cycle with the lifecycle plan's explicit UniEval deferral. |
| K2 | Choose concurrent or explicit phased execution from real functional execution, not a separate study. | J3. The same saved generation input survives service shutdown; unsuccessful attempts remain unsuccessful. |
| K3 | Preserve native results independently of diagnostic and sibling failures. | E4 and E8-E9. A completed zero is data, a missing score is null, and neither a failed log mirror nor another engine may rewrite that fact. |

Table L - Workflow alternatives not selected

| Id | Alternative | Why not selected | Cost to take it | Basis |
| --- | --- | --- | --- | --- |
| L1 | Add another workflow, model selector or generated summary for UniEval | Duplicates orchestration or makes the evaluator comparison use different answers. | Another environment/report path, or a different comparison contract. | A1-A4 and E7. |
| L2 | Gate construction on a model leaderboard, capacity study or synthetic success | Does not demonstrate the required real API/workflow capability. | Additional experiment design and runner time before the actual functional request. | A8 and J5. |

## See also

- [Server lifecycle and workflow plan](20261103-pipeline-server-lifecycle-plan.md)
- [Canonical identity contract](../docs/architecture/contracts/identity.md)
- [Plan authoring](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [HHEM process ownership](../docs/architecture/evaluation/hhem-evaluation-api.md)
- [HHEM native API](../docs/reference/hhem-evaluation-api.md)
- [Summary workflow](../docs/reference/summary-evaluation-workflow.md)
- [Model-file selection](../docs/concepts/config/model-file.md)
- [Published summary metrics](../docs/concepts/summary-metrics.md)
