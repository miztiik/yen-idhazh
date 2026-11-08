# Simplify reference-free UniEval evaluation

**Last Updated**: 2026-11-08
**Level**: 5 - native scoring and saved workflow contracts.

## 0 - Operating contract

**Table A - Scope and execution**

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Evaluate ordinary source/summary pairs without a reference, make relevance independently optional, and use full-source consistency without removing safe handling of oversized articles. |
| A2 | Hard scope - in | Native API, owned worker, selected scorer configuration, manual comparison workflow, saved-result readers, reports, existing recorded-prediction support, directly affected tests and canonical documentation. |
| A3 | Chosen strategy | Fowler's architecture consultation: explicit relevance opt-in, nullable skipped relevance, existing full-source consistency as the default, explicit windows, specific size diagnostics and unchanged process-safety controls. |
| A4 | Delivery | Each reckoner row is one independently verifiable PR. Reader compatibility precedes changed writers inside a PR; rows ship in dependency order. |
| A5 | ESCALATE triggers | 1. Surface a new Level-5 design decision not settled by this plan. 2. Stop if preserving a supported saved artifact requires changing its original meaning or bytes. 3. Surface any change to weights, scoring questions, numeric resource allowances, trust boundaries or production publication. 4. Surface an unresolved contract decision or required file outside a row's verified scope. |
| A6 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight because the rows share native contracts, workflow consumers and documentation; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

**Table B - Scope boundaries and their costs**

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Restoring the retired coverage audit or adding source-only relevance | No numerical claim about whether every important source fact appears in the summary. | A separately defined completeness measure, its intended use and an evaluation method that distinguishes omission from unsupported claims. |
| B2 | Wiring this API into production article publication or restoring evaluation in the independent inference experiment | The simplified API and manual workflow do not themselves add a production scorer or automatically consume another workflow's output. | A named production caller and its publication, failure and runtime requirements. |
| B3 | Raising or removing the configured token allowance; changing model weights or runtime libraries | Inputs above the current resource policy still receive an explicit refusal unless explicit consistency windows fit. | A bounded real-model observation of the proposed allowance, measured memory and elapsed time on the target runner, followed by a separate configuration decision. |
| B4 | Replacing process supervision, transport bounds, identities or cleanup | The service retains the existing safety-related implementation size. | A specific failing safety invariant or an independently justified replacement that preserves its tests. |
| B5 | Changing the published frontend or its evaluator contracts | No new reader-facing score panel is delivered. | A named published surface and its data producer; that would add a separate integration outcome. |

## 1 - Status reckoner

**Table C - PR-shaped outcomes**

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Optional relevance across API and saved workflow | - | A | DONE | fantastic-happiness | - | Optional UniEval relevance |
| C2 | 2 | Full-source consistency by default | 1 | B | DONE | legendary-train | - | Full-source UniEval defaults |
| C3 | 3 | Specific model-input and window-budget errors | 2 | C | PENDING | - | - | - |

## 2 - Row #1 - Optional relevance across API and saved workflow

- **Scope:** Source and summary alone complete the applicable UniEval evaluation; optional relevance and reference inputs remain bound through the real worker, manual workflow and saved report.
- **Files touched:**
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_contract.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_request.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_result.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_recording.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_worker_contract.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_worker_message.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/previous_unieval_result.py` - new frozen saved-result reader.
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/previous_unieval_recording.py` - new frozen recording reader.
  - `services/summary_evaluator/src/summary_evaluator/unieval/resolve_unieval_selection.py` - new shared request-selection helper.
  - `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/score_unieval.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/reduce_unieval.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/unieval_worker.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/exchange_packets.py`
  - `services/summary_evaluator/scripts/capture-unieval-recordings.py`
  - `services/summary_evaluator/tests/summary_evaluator_cases/unieval_cases.py`
  - `services/summary_evaluator/tests/summary_evaluator_cases/contract_examples.py`
  - `services/summary_evaluator/tests/test_unieval_contracts.py`
  - `services/summary_evaluator/tests/test_unieval_api.py`
  - `services/summary_evaluator/tests/test_unieval_scoring.py`
  - `services/summary_evaluator/tests/test_unieval_reduction.py`
  - `services/summary_evaluator/tests/test_unieval_windows.py`
  - `services/summary_evaluator/tests/test_unieval_retirement.py`
  - `services/summary_evaluator/tests/test_unieval_worker.py`
  - `services/summary_evaluator/tests/test_unieval_prompt_files.py`
  - `services/summary_evaluator/tests/test_worker_trace_contracts.py`
  - `services/summary_evaluator/tests/test_scorer_trace_isolation.py`
  - `services/summary_evaluator/tests/test_api.py`
  - `services/summary_evaluator/tests/test_component_registration.py`
  - `tools/summary-eval/summary_eval_pipeline/contracts.py`
  - `tools/summary-eval/summary_eval_pipeline/run_contracts.py` - new current preparation/receipt models.
  - `tools/summary-eval/summary_eval_pipeline/previous_phase_contracts.py` - new frozen independent-phase reader.
  - `tools/summary-eval/summary_eval_pipeline/previous_report_contracts.py` - new frozen independent-report reader.
  - `tools/summary-eval/summary_eval_pipeline/inputs.py`
  - `tools/summary-eval/summary_eval_pipeline/preparation.py`
  - `tools/summary-eval/summary_eval_pipeline/generation.py`
  - `tools/summary-eval/summary_eval_pipeline/llama.py`
  - `tools/summary-eval/summary_eval_pipeline/evaluation.py`
  - `tools/summary-eval/summary_eval_pipeline/evaluate_pair.py`
  - `tools/summary-eval/summary_eval_pipeline/phases.py`
  - `tools/summary-eval/summary_eval_pipeline/phase_contracts.py`
  - `tools/summary-eval/summary_eval_pipeline/phase_result.py`
  - `tools/summary-eval/summary_eval_pipeline/report_contracts.py`
  - `tools/summary-eval/summary_eval_pipeline/scorer_evidence.py`
  - `tools/summary-eval/summary_eval_pipeline/report_task.py`
  - `tools/summary-eval/summary_eval_pipeline/report.py`
  - `tools/summary-eval/summary_eval_pipeline/report_models.py`
  - `tools/summary-eval/summary_eval_pipeline/storage.py`
  - `tools/summary-eval/summary_eval_tests/generation_cases.py`
  - `tools/summary-eval/summary_eval_tests/owned_scorer_child.py`
  - `tools/summary-eval/summary_eval_tests/scorer_evidence_cases.py`
  - `tools/summary-eval/summary_eval_tests/test_generation_handoff.py`
  - `tools/summary-eval/summary_eval_tests/test_pipeline_preparation.py`
  - `tools/summary-eval/summary_eval_tests/test_native_generation.py`
  - `tools/summary-eval/summary_eval_tests/test_generation_prompt_files.py`
  - `tools/summary-eval/summary_eval_tests/test_manual_workflow.py`
  - `tools/summary-eval/summary_eval_tests/test_pipeline_report.py`
  - `tools/summary-eval/summary_eval_tests/test_workflow_outcomes.py`
  - `tools/summary-eval/summary_eval_tests/test_scorer_callers.py`
  - `tools/summary-eval/summary_eval_tests/test_scorer_trace_continuity.py`
  - `tools/summary-eval/summary_eval_tests/test_unieval_workflow.py`
  - `tools/summary-eval/summary_eval_tests/test_unieval_workflow_fixture.py`
  - `tools/summary-eval/summary_eval_tests/test_evaluator_response_binding.py`
  - `.github/workflows/summary-eval-tests.yml`
  - `config/summary-evals/unieval-evaluator/settings.json`
  - `tests/fixtures/unieval-evaluator/workflow-inputs.json`
  - `docs/reference/unieval-api.md`
  - `docs/architecture/evaluation/unieval-api.md`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-unieval-evaluation-api.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates - local:** Inspect the shared selector with `npm --prefix frontend run test:changed -- --list`; use the existing frozen evaluator environment and the lint/type commands in [the gate guide](../docs/how-to/run-the-gates.md#independent-python-service-contracts). Run selected portable contract/reader tests only when needed for debugging; preserve successful unchanged check records.
- **Acceptance gates - CI:** The merge candidate's existing `model-free` job must run the complete native service and manual-workflow suites. Named focused checks include the changed contract, reduction, worker-trace, response-binding, generation-handoff, workflow-outcome and report tests listed above. Workflow edits also select the existing workflow-input and trigger checks through the shared selector. Preserve both scorer-isolation directions and their current socket guard.
- **Acceptance gates - operator surface:** Review one representative escaped report against [the design requirements](../docs/concepts/design-system.md), including the distinction between skipped and failed. Use the existing real manual workflow for one read-only reference-free model observation; retain its exact revision, result artifact and confirmed API/worker exits. Do not multiply live runs across skip states; cover those branches offline.
- **Oracle:** Add `test_reference_free_pair_completes_without_relevance_work` to the existing native-pair workflow test: the real ASGI worker and recorded prediction boundary must yield applicable numeric scores, an authorized relevance skip, no relevance comparisons and a complete bound saved-result round trip. This does not establish model accuracy or arbitrary-length runtime capacity.

**Table D - Contracts and implementation decisions**

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| D1 | 1 | `UnievalRequest` keeps required nonblank source and summary. `reference_summary_text` becomes omittable; a supplied null or blank value is invalid. Preserve supplied UTF-8 bytes rather than trimming them. | Native input validation; Fowler contract consultation. |
| D2 | 2 | Add omittable strict-boolean `evaluate_relevance`. Omission resolves the same-named setting under validated `scoring`, whose committed default is false. Explicit false overrides a configured true; reference presence never enables it. Record the resolved boolean in effective controls. | Explicit opt-in strategy; config-driven defaults. |
| D3 | 3 | Add required nullable `relevance_skip_reason`, with the closed values `disabled` and `reference_not_supplied`. Disabled selection wins regardless of reference presence. Enabled selection without a reference uses the second reason; enabled selection with a reference plans relevance and has no skip reason, including when scoring fails. Invalid requests establish no skip reason. | Fowler contract consultation. |
| D4 | 4 | Keep the four nullable score fields. A relevance skip has a null score, no plan and zero completed comparisons. The parent derives allowed relevance work from its validated request and resolved controls; it rejects an unauthorized skip, prediction or changed selection. Use the new helper only for this selection, not a generic dimension framework. | Exact worker progress validation; Fowler contract consultation. |
| D5 | 5 | `complete` requires every applicable score and no errors; three successful scores with a relevance skip return HTTP 200. Real attempted/planned failures remain `partial` when numeric scores survive, otherwise `failed`. A computed zero remains numeric data. | Existing partial-result guarantees extended to applicability. |
| D6 | 6 | `reference_summary_sha256` is nullable only when reference input is absent or invalid. Hash every valid supplied reference even when relevance is disabled; do not interpret that hash as evidence of scoring. No non-relevance score requires it. | Exact-input provenance; Fowler contract consultation. |
| D7 | 7 | Current preparation, generation-receipt and phase evidence carry the resolved selection and nullable reference identity. Bind reference presence/hash and selection consistently through preparation, generation and evaluation. Changing either after preparation fails receipt validation. Reference text never enters generation or HHEM. | Same-run input binding. |
| D8 | 8 | The dispatch form has an optional reference and an optional boolean checkbox with a false default. At this platform boundary only, an empty reference form value means absent; nonempty whitespace remains invalid. Decode only canonical platform boolean values, then run strict model validation. The supplied-reference recording explicitly opts in so its intended four-score journey remains real. | Native/platform boundary separation. |
| D9 | 9 | Freeze the prior embedded native result and the supported shared/independent phase and report validators before replacing their live dependencies. Keep the existing old preparation/receipt models in their current module; add current models separately. Add exact version-dispatched readers for named run, receipt, phase and combined files. Preserve old bytes, versions, hashes, score meaning and shared/independent process evidence. Invalid current evidence never retries through an older reader. | Reader-before-writer contract migration. |
| D10 | 10 | Preserve the existing recording family's schema, genuine prediction hashes and fixture bytes. Read its nested old request/controls with frozen models, then derive an explicit current four-score execution only at the replay/capture boundary. Do not write that selection into historical recordings or relabel old predictions. Current request omission/skip tests use minimal in-memory inputs and unchanged recorded prompt predictions. | Existing model-boundary provenance; test policy. |
| D11 | 11 | Stamp changed native result, authored/effective controls, private worker and saved-artifact families with the implementation UTC date and concise changelogs. Keep health, routing, machine-startup and scorer-control families unchanged; separate incidental shared version constants where needed instead of advancing unrelated protocols. Old recordings and read-only saved evidence retain their own versions. | Independent contract-family versioning. |
| D12 | 12 | Update current documentation in its owning pages: input applicability, skipped versus failed outcomes, report denominators and reference disclosure. Reports show completed versus applicable dimensions, not a fixed four-score denominator, and display a supplied-but-unused reference as such. Do not copy design reasons into procedure pages. | Documentation and operator-facing status accuracy. |
| D13 | 13 | Keep prior code tests that intentionally exercise four-score behavior explicit about selection. Do not turn those tests into default reference-free cases or delete their failure/isolation assertions. Reuse only exact recorded predictions; introduce no replacement model implementation. | Changed-behavior tests and retained safety guarantees. |

**Table E - Rejected alternatives**

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| E1 | 1 | Automatically score relevance whenever reference text exists | Reference presence would again select work independently of the explicit control. | Change selection semantics and every caller/report binding; re-open the explicit opt-in decision. | Selected API behavior. |
| E2 | 2 | Substitute source text or generate a reference | This changes reference agreement into another measure or creates a second generated answer as an unverified target. | Define and validate that separate measure, or pay for an independently judged reference-generation stage. | Native relevance semantics. |
| E3 | 3 | Add a general requested-dimension list and per-dimension state framework | Only relevance has a new selection/prerequisite; the other dimensions remain required. | Additional schema states, validation combinations and caller controls without a current consumer. | Fowler's minimal contract. |
| E4 | 4 | Change only the HTTP request field | Unconditional hashing, completion checks, receipts and workflow inputs would still reject or misreport reference-free work. | The same consumer migration would remain necessary before the capability works end to end. | Verified producer/consumer bindings. |
| E5 | 5 | Relax old validators or rewrite old artifacts into the new shape | It erases the distinction between four-score evidence and intentional skipped relevance. | A separately authorized historical migration with provenance-preserving rules. | Saved-result compatibility. |

## 3 - Row #2 - Full-source consistency by default

- **Scope:** The configured default evaluates every summary sentence against the complete source, while explicit source windows remain available without silent fallback.
- **Files touched:**
  - `config/summary-evals/unieval-evaluator/settings.json`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_request.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/resolve_unieval_selection.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/score_unieval.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/reduce_unieval.py`
  - `services/summary_evaluator/tests/test_unieval_contracts.py`
  - `services/summary_evaluator/tests/test_unieval_windows.py`
  - `services/summary_evaluator/tests/test_unieval_scoring.py`
  - `services/summary_evaluator/tests/test_unieval_reduction.py`
  - `tools/summary-eval/summary_eval_pipeline/inputs.py`
  - `tools/summary-eval/summary_eval_pipeline/evaluation.py`
  - `tools/summary-eval/summary_eval_pipeline/evaluate_pair.py`
  - `tools/summary-eval/summary_eval_pipeline/report_models.py`
  - `tools/summary-eval/summary_eval_tests/test_manual_workflow.py`
  - `tools/summary-eval/summary_eval_tests/test_unieval_workflow.py`
  - `tools/summary-eval/summary_eval_tests/test_unieval_workflow_fixture.py`
  - `tools/summary-eval/summary_eval_tests/test_evaluator_response_binding.py`
  - `.github/workflows/summary-eval-tests.yml`
  - `docs/reference/unieval-api.md`
  - `docs/architecture/evaluation/unieval-api.md`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/how-to/run-unieval-evaluation-api.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates - local:** Use the shared selector and unchanged frozen lint/type procedures from row #1; select the named source-plan, reduction and caller-binding tests when debugging.
- **Acceptance gates - CI:** Existing complete Linux model-free service/workflow suites; contract default binding, explicit override, no truncation, source-end coverage and preserved failed-dimension/sibling outcomes.
- **Acceptance gates - operator surface:** The existing report displays the actual selected mode and comparison counts. The manual form exposes the override defined in F3. No benchmark or additional model download is a prerequisite for switching to the already implemented mode.
- **Oracle:** Add `test_default_full_source_has_one_consistency_comparison_per_summary_sentence` to the existing window/planning tests. Use a bounded in-memory article whose actual tokenized source exceeds the configured window target but whose full comparisons fit the configured allowance; require one full-source span and the native sentence comparison count, then require the explicit window override to retain its complete-source plan. This proves selection and work geometry, not that full-source inference is faster or more accurate.

**Table F - Source handling and token-policy decisions**

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| F1 | 1 | Set the existing `consistency_source_mode` default to `full_source_prompt`. Keep summary sentence splitting and the mean of complete sentence scores; do not replace it with one question over the whole summary. | Upstream summarization calculation; Fowler consultation. |
| F2 | 2 | Retain `all_source_windows` only as an explicit request or committed configuration selection. Preserve its sentence-by-window comparisons, per-sentence maximum reduction, original-character spans, overlap and complete-work validation. Never select it automatically after an oversized full-source input. | Existing independently named scoring modes. |
| F3 | 3 | Add an optional string mode override to the manual workflow. Empty form input follows scorer configuration; either existing mode spelling is valid and every other nonempty value fails validation. Bind the response's mode to the resolved request, not merely the configured default. | Config substitution and actual request/response binding. |
| F4 | 4 | Coherence remains a full-source/full-summary question. Explicit consistency windows do not make oversized coherence fit and do not change relevance or fluency. Retain completed sibling dimensions when a required dimension cannot fit. | Native dimension meanings. |
| F5 | 5 | The pinned upstream scorer constructor defaults to 1,024 input tokens and passes truncation to its tokenizer. That is a configurable implementation default, not a proven architectural maximum. The pinned tokenizer metadata advertises 512 tokens; the selected model configuration uses relative attention and declares no fixed input-position ceiling. Derive those receipts from the committed asset/code revisions, not a moving upstream branch. | Verified pinned upstream scorer, tokenizer and model configuration. |
| F6 | 6 | Keep `max_input_tokens` as an operator-configured resource allowance. Its current committed value is 4,096, above the upstream constructor default; do not describe it, the constructor default or tokenizer metadata as the model's fixed context limit. Changing the existing value requires no source edit, but this row does not tune it or claim arbitrary-length accuracy/capacity. | Verified native non-truncating predictor; bounded runtime policy. |
| F7 | 7 | Count the complete assembled question plus the relevant text and special tokens with the actual tokenizer. Do not count words, apply the tokenizer's advisory metadata as a second cap, silently clip source text or add automatic mode retries. | Existing non-truncating input invariant. |
| F8 | 8 | Reuse existing full-source and windowed implementation paths. Remove only branches or repeated selection logic made unnecessary by D4; keep process ownership, timeouts, queue/byte bounds, exact metadata validation and cleanup tests. | Fowler's simplification boundary. |

**Table G - Rejected alternatives**

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| G1 | 1 | Remove windows entirely | Oversized sources lose their explicit consistency option. | Narrow supported source handling and migrate callers that deliberately select windows. | Retained explicit mode. |
| G2 | 2 | Automatically retry using windows or truncate | The same request would silently change the article or score calculation. | A new explicit fallback policy, response provenance and caller behavior; clipping still cannot satisfy complete-source scoring. | No silent input/mode change. |
| G3 | 3 | Treat every accepted long input as evidence of reliable evaluation | Mechanical execution does not establish scoring quality; longer calls can also cost more than several shorter ones. | A bounded labeled comparison and target-runner measurements answering a specific tuning decision. | Evaluation evidence requirements. |
| G4 | 4 | Replace sentence-level consistency with a single whole-summary score | It changes the upstream summarization reduction rather than simplifying orchestration. | A differently named measure and quality comparison against the native sentence mean. | Native consistency meaning. |

## 4 - Row #3 - Specific model-input and window-budget errors

- **Scope:** Oversized evaluations identify the affected dimension and measured assembled-input size, while impossible window geometry is reported separately from an oversized summary sentence.
- **Files touched:**
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_contract.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_error.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_worker_contract.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_worker_message.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/check_unieval_input_size.py` - new shared token-refusal helper.
  - `services/summary_evaluator/src/summary_evaluator/unieval/score_unieval.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/plan_unieval_windows.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/unieval_worker.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/reduce_unieval.py`
  - `services/summary_evaluator/tests/test_unieval_contracts.py`
  - `services/summary_evaluator/tests/test_unieval_windows.py`
  - `services/summary_evaluator/tests/test_unieval_reduction.py`
  - `services/summary_evaluator/tests/test_worker_trace_contracts.py`
  - `tools/summary-eval/summary_eval_pipeline/report.py`
  - `tools/summary-eval/summary_eval_tests/test_pipeline_report.py`
  - `tools/summary-eval/summary_eval_tests/test_unieval_workflow.py`
  - `docs/reference/unieval-api.md`
  - `docs/architecture/evaluation/unieval-api.md`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/how-to/run-unieval-evaluation-api.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
- **Acceptance gates - local:** Use the existing frozen lint/type checks and the shared selector. Selected tokenizer-boundary and error-projection tests may run locally for debugging; no live model or network is necessary to verify a refused input.
- **Acceptance gates - CI:** Complete existing Linux model-free suites, including intact byte-bound and worker-identity checks. Version-bound old artifact readers from row #1 must still accept previously valid errors and reject invalid current packets.
- **Acceptance gates - operator surface:** The report displays actual input tokens against the configured allowance beside the affected score; an absent historical measurement is unavailable, not reconstructed. Fixed messages describe which text was involved without including source, summary, reference, prompt contents or raw exceptions.
- **Oracle:** Add a parameterized real-tokenizer regression to the existing window/planning tests for an input exactly at its configured allowance and one token over it, across each applicable dimension. Exercise the shared refusal helper and worker projection as well as planning; require the same measured sizes and the correct dimension after bounded packet round trip. This does not measure feasible memory use or judging quality above the current allowance.

**Table H - Error-contract decisions**

| ID | # | Decision | Authority |
| --- | --- | --- | --- |
| H1 | 1 | Add paired nullable error fields `input_tokens` and `allowed_tokens`. When present, they describe actual assembled-input tokens and the configured allowance, with the former greater than the latter. Other errors and older saved observations may omit both. New assembled-input refusals always populate both; never manufacture component totals. | Specific, body-free measured diagnostics. |
| H2 | 2 | Add a neutral internal `MODEL_INPUT_TOO_LONG` code for predictor-level refusal. The existing dimension-aware comparison boundary maps it to the existing public size code for the actual dimension and preserves its measurements and comparison index. Do not label every predictor overflow as consistency. | Verified predictor error misclassification. |
| H3 | 3 | Use the new helper for the shared size predicate and code mapping. Check size before optional heavy model execution/import where needed so a refused input can be tested with real tokenization and no model substitute. Planning and predictor defense both remain; they protect different boundaries. | DRY without removing boundary defense. |
| H4 | 4 | Add `WINDOW_BUDGET_INSUFFICIENT` for a consistency plan that cannot reserve positive source progress and required overlap while the sentence/question itself fits. Keep genuinely oversized sentence/question failures distinct. The fixed message names source window/overlap geometry; do not claim that the source text or summary exceeded its allowance without a measured oversized assembled input. | Verified window planner's misleading summary-size refusal. |
| H5 | 5 | Retain whole-character progress, complete-source coverage and finite-plan checks for explicit windows. Preserve the original planning cause when it cannot advance; do not weaken overlap or truncate to make the plan succeed. Existing window/count limit errors remain separate from token errors. | Existing complete-source plan invariants. |
| H6 | 6 | Preserve numeric error data through worker factories, serialization, parent reduction and the escaped report. Retain completed dimensions and HHEM outcomes after a size failure, and do not change error HTTP behavior merely to show better diagnostics. | End-to-end failure provenance. |
| H7 | 7 | Stamp changed error/native/private-worker schema families; preserve historical readers. Same-UTC-day additions may use the current day's changelog entry only when older same-day saved payloads remain readable without inventing missing measurements. Do not advance unchanged health or startup contracts. | Date-only versioning and read-side compatibility. |
| H8 | 8 | Update the owning API and workflow references and their existing design rationale. Retain one explanation distinguishing the short question from its complete model input; replace obsolete instructions rather than append a second procedure. | Documentation split/delete test. |

**Table I - Rejected alternatives**

| ID | # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- | --- |
| I1 | 1 | Return only a generic prompt-too-long message | It conceals the affected dimension and whether the actual problem is source text, reference text or window geometry. | Continued operator diagnosis from configuration and reproduction of the failure. | Requested error clarity. |
| I2 | 2 | Log the failing text or raw tokenizer/model exception | It breaches the existing body-free diagnostic boundary. | A different disclosure policy and reader-safety review; numeric diagnostics already answer the size question. | Diagnostic trust boundary. |
| I3 | 3 | Add per-component token counts that are assumed to sum to the whole input | Tokenization across concatenation boundaries need not equal separately tokenized components. | Explicit count semantics and additional fields/tests, without improving the authoritative assembled-size comparison. | Minimal measured error contract. |
| I4 | 4 | Remove queue, deadline or worker cleanup controls while simplifying scores | Those controls protect consumers from stalled models and abandoned processes, not from scoring-policy complexity. | A separately justified supervision replacement with equivalent process tests. | Fowler's retained safety boundary. |
