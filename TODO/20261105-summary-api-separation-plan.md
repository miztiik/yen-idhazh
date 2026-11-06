# Summary API separation

**Last Updated**: 2026-11-05
**Level**: 5 - service responsibilities and live request, health and saved-workflow contracts.

## 0. Operating contract

**Table A - Operating contract**

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Each API does its named job. A workflow calls independent generation, evaluation and machine APIs, then writes its report. |
| A2 | Hard scope - in | Separate generation from evaluation; name and divide the evaluator package; bring the older coverage scorer into it; rename the TypeScript API and separate its full-analysis caller; retain prompt overrides and fresh independent requests; centralize the named prompts; group evaluation configuration; standardize every first-party TypeScript HTTP route; update callers, tests, CI, docs and reports in each cutover. |
| A3 | Hard scope - out | Table B prices the exclusions. None is permission to reduce the requested separation. |
| A4 | Chosen strategy | Fowler: one evaluation application with independent HHEM, native UniEval and source-coverage children and workers; independent native llama-server; the existing workflow is the orchestrator, meaning the caller that runs the steps in order. |
| A5 | Plan state | Execution in progress. Table E records each implementation and merge; unfinished rows retain their declared gates. |
| A6 | ESCALATE triggers | 1. A removed input, output or route has an unnamed caller. 2. A move causes a score, error, schema or identity change not declared here. 3. A saved format needs a compatibility rule not declared in Table G. 4. A change discards classifications, source fallback, legacy coverage scores or report evidence instead of relocating or explicitly pricing it. 5. An external required-check setting prevents a CI name change. 6. A model, dependency family, service deployment or runtime destination not declared here is needed. |
| A7 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A8 | Why parallel N is lower | The PRs share CI and the gate guide. The evaluator PRs also change the same callers and test helpers. Serial writing avoids conflicting cutovers; it does not add a dependency between independent APIs. |
| A9 | Canonical pages | The composition page follows move K11. Other authorities: [HHEM](../docs/reference/hhem-evaluation-api.md), [UniEval](../docs/reference/unieval-api.md), [workflow](../docs/reference/summary-evaluation-workflow.md), [summarizer](../docs/reference/summarizer-api.md), [saved experiment events](../docs/reference/workflow-pipeline-events.md). |
| A10 | Verification record | Record the source revision, selected tests, result and platform for each PR. Follow [the gate guide](../docs/how-to/run-the-gates.md): complete model-free evaluator/workflow suites run through the manual, read-only `summary-evaluator-checks.yml` Linux gate, separate from ordinary `ci.yml`. Reuse passed evidence while its tested inputs are unchanged. Ordinary CI retains its backend, native TypeScript and saved-handoff gates. Do not dispatch a live production workflow as a merge gate. Windows results do not replace Linux evidence. |
| A11 | Native request boundary | Do not introduce a Pydantic or Zod model of llama-server's request fields. Forward its configured JSON fields and server flags without an enumerated field list. Validate only the settings this repository computes on, its own API products, the committed destination, transport bounds and protected decoding controls. Adding a supported native setting outside those protected controls must not require source or test-fixture edits. |
| A12 | Repeated generation calls | The generator accepts repeated independent requests. Each builds a fresh system/user request; it carries no earlier answer, conversation history or server session. Keeping the model process or its prefix cache alive is not conversation continuation. The production digest's existing two-call continuation is a separate flow and stays unchanged. |
| A13 | Prompt control | The configured generator prompt is a default, not a restriction. A nonblank request-level `system_prompt` replaces that default without a restart or config edit. Record the effective prompt's digest and origin; never append hidden classification instructions to the override. Table W declares the prompt sources and destinations. |

**Table B - Exclusions and their cost**

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Changing scorer algorithms, question wording, model choices, window policies or numerical precision | Existing quality limits remain. Moving a prompt must preserve its rendered text; this cleanup does not establish that either scorer's numbers are correct for every article. | A separate quality finding with recorded inputs and a stated scoring change. |
| B2 | Separate HHEM and UniEval HTTP deployments | Restarting the shared evaluation application still interrupts both APIs; their model workers and queues remain separate. | Evidence that shared HTTP-process failure isolation is needed; price another listener, lifecycle and report stream. |
| B3 | A new llama wrapper or a new orchestration framework | Native generation and the existing workflow remain the integration points. There is no extra common API address. | A capability the existing native API or workflow cannot provide, with its added process and maintenance cost. |
| B4 | Replacing the older UniEval coverage method with native UniEval | Two scoring methods remain. The older method retains its sentence explanations and source-section coverage; it does not acquire native reference-based relevance. | A separate migration decision naming the independent reference input and what replaces or removes the old coverage and explanation fields. |
| B5 | New machine measurements for the older experiment | Its new evaluator responses no longer provide CPU, memory or swap readings. Reports must say these readings were not collected, not show zero. | An experiment requirement to call the existing host APIs and name the measured process and interval. |
| B6 | Rewriting recordings, historical logs or scores | Historical artifact names can retain HHEM or the former server name. They remain evidence of what actually ran. | A declared reader migration, never a cosmetic rewrite of provenance. |
| B7 | Published-site changes and unrelated planner/host behavior changes | The site and domain calculations stay unchanged. Their HTTP paths and named callers do change under Table Z; sharing an HTTP listener remains allowed. | A concrete domain defect beyond the route migration, with its own acceptance condition. |
| B8 | Changes to `CLAUDE.md` or `AGENTS.md` | The existing engineering contract remains in force. | A separate explicit request to change those files. |
| B9 | Replacing the digest's label-then-summary continuation with fresh calls | Its existing prefix reuse, label context and summary/visual output remain intact; moving its prompt files does not make it use the generator API. | An explicit production-flow change with a replacement for the carried labels and prefix behavior. |
| B10 | Changing the comparison workflow's body-free native-log policy | Raw model-server output remains suppressed there. Its lifecycle log cannot provide the detailed native counters and text available in the digest's private runtime artifact. | A separate private-capture requirement naming content controls, bounds and retention; copying a verbosity flag alone is not that design. |
| B11 | Full-analysis fields in the Yen summary-only report | That report no longer has sentiment, stance or machine readings. Full analysis and its report remain available through C12's separate CLI. Native token counts from the actual summary call remain response metadata, not summary fields. | An explicit additional analysis or host call, with its own receipt and runtime cost. Do not invent these fields from a summary-only response. |

**Table C - Final names and responsibilities**

| Id | Artifact | Final name and path | Its job |
| --- | --- | --- | --- |
| C1 | Evaluation product and project | `summary-evaluator`; `services/summary_evaluator/` | Evaluate supplied summaries. The Python distribution is named `summary_evaluator`; packaging tools normalize distribution separators. It never generates summaries or calls a generation server. |
| C2 | Python import package | `summary_evaluator`; `services/summary_evaluator/src/summary_evaluator/` | The outer directory holds the environment, manifest, scripts and tests; `src` holds the installed package. Python does not require the outer directory to use dashes. This is one application, not nested APIs. |
| C3 | HTTP serving package | `serve_http/` | Receive requests, apply safety checks, route work to the named scorers, and provide health and schema responses. Assemble the listener and its diagnostic events; do not implement scoring. This is a code directory, not another API or a URL prefix. |
| C4 | Common mechanism child | `shared/` | Typed primitives, bounded body/pipe transport, queue mechanics, asset helpers, process identity and validated record delivery. No scorer or generation imports. |
| C5 | HHEM child | `hhem/`, with `hhem/contracts/` | HHEM requests, settings, scoring, events, queue controller and worker policy. |
| C6 | UniEval child | `unieval/`, with `unieval/contracts/` | Native UniEval requests, settings, resources, scoring, reductions, queue controller and worker policy. |
| C7 | Generation API | Existing native `llama-server`, at committed `model_server.base_url` | Model generation and its own readiness. No `services/llama-server/` wrapper is created. |
| C8 | Generation/evaluation workflow | `.github/scripts/summary-eval-tests/summary_eval_pipeline/` | Prepare inputs; call generation; save the exact answer; call evaluators; collect host evidence; own processes; publish the report. |
| C9 | Workflow test package | `.github/scripts/summary-eval-tests/summary_eval_tests/` | Workflow, process ownership, same-run handoff, machine collection and report checks. Its distinct package name avoids another generic Python `tests` package. |
| C10 | Scorer and application test support | `services/summary_evaluator/tests/summary_evaluator_cases/` | One copy of the real evaluator recording and process harness used by service and workflow integration tests. It is not shipped in the distribution. |
| C11 | TypeScript generation API and package | `summary-generator`; `services/summary-generator/` | Turn supplied text into a structured summary with a configured or request-supplied prompt. It does not acquire URLs, classify attitudes, sample the machine or publish job reports. |
| C12 | TypeScript full-analysis caller and tests | `.github/scripts/summary-generator-tests/` | Preserve the existing CLI's extraction, fallback, classifications, measurements, saved events and private report outside the summary API. This is a script-directory name; it does not rename the distinct comparison workflow or silently replace either existing workflow file. |
| C13 | Source-coverage evaluation operation | `source_coverage/` inside C2 | Bring the older UniEval-backed coverage method into the evaluation application as a distinct operation and worker. Delete its standalone script and old route after switching callers; do not relabel its scores as native UniEval. |
| C14 | Evaluation configuration | `config/summary-evals/`; exact moves in Table K | Shared listener and workflow settings live in the parent. HHEM and UniEval settings live in their named child directories. These are repository-authored settings, not downloaded model configuration. |
| C15 | Prompt files | `config/prompts/{verb-noun}.txt`; exact map in Table W | One canonical file per declared task. Readers use explicit configured paths, not a directory scan; source text never selects a prompt file. |

```text
services/
  summary_evaluator/
    pyproject.toml
    src/summary_evaluator/
      __main__.py
      serve_http/contracts/
      shared/contracts/
      hhem/contracts/
      unieval/contracts/
      source_coverage/contracts/
    scripts/
    tests/summary_evaluator_cases/
  summary-generator/
    src/api/
    src/schemas/
    src/services/
.github/scripts/
  summary-eval-tests/
    summary_eval_pipeline/
    summary_eval_tests/
  summary-generator-tests/
    contracts/
    test/
config/
  summary-evals/
    api.json
    workflow.json
    hhem-evaluator/settings.json
    unieval-evaluator/settings.json
    unieval-evaluator/coverage.json
  summary-generator/
    api.json
    workflow.json
  prompts/
    generate-summary.txt
    request-json.txt
    analyze-article.txt
    generate-labels.txt
    write-digest-summary.txt
    plan-visual.txt
    continue-summary.txt
    summarize-article.txt
    compare-articles.txt
    generate-evaluation-summary.txt
    evaluate-fluency.txt
    evaluate-coherence.txt
    evaluate-consistency.txt
    evaluate-relevance.txt
```

**Table D - Before/after control flow and functionality**

| Id | API or boundary | Before: current code | After: proposed flow and location | Change and PR |
| --- | --- | --- | --- | --- |
| D1 | Python application | One HHEM-named distribution assembles HHEM, native UniEval and a llama generation proxy. Each scorer already has its own queue and worker. | One evaluation application at C1-C6 and C13 assembles three distinct evaluation methods. Native generation remains a separate server. | Remove an unrelated route, rename/divide ownership and absorb the coverage server; PRs 1-3 and 5. No wrong-score defect has been established. |
| D2 | HHEM operation | Supplied source and summary -> validation and queue -> every planned word window -> HHEM model -> largest completed window score. Optional full-source comparison adds a full score and primary-minus-full difference. Results also carry work counts, identities, timings and safe failures. | The same request, scoring, partial-result and worker behavior lives in C5. It does not generate a summary or call UniEval or llama-server, before or after. | Ownership change, not a scoring change; PR 3. |
| D3 | Native UniEval operation | Supplied source, summary and independent reference -> its own queue/worker -> fluency, coherence, consistency and relevance. Consistency supports all-source-window and full-source-prompt modes. Results retain complete dimensions when other work fails. | The same behavior lives in C6, without imports of HHEM-specific settings, failures or model helpers. It never creates or substitutes the reference. | Remove code coupling; preserve all dimensions and meanings; PR 3. |
| D4 | Native llama generation | The binary is already a separate process. The comparison workflow calls its template and model-identity operations directly but sends completion through the Python proxy. The native response includes answer/reasoning content and available usage/timing data. | The workflow calls the same native completion API directly. The selected origin remains `model_server.base_url` in repository-authored `config/idhazh.json`; the declaration selected by that file supplies weights and request controls. | Delete the proxy, not the native generation capability; PRs 1-2. |
| D5 | Comparison-workflow input and model selection | Input byte limits, logging settings and the native-origin/deadline type are borrowed from the evaluator package. Same-run input reading loads HHEM settings. | C8 reads workflow-owned bounds and native settings. It validates source/reference/model identity without needing evaluator configuration during generation. Evaluator asset preparation remains a workflow task. | Move caller concerns before retiring their old imports; PR 1. |
| D6 | Generation process flow | Workflow starts native llama, Python with only its generation route enabled, and the host collector -> generates and saves the answer -> closes the three owned roles. No evaluator model worker runs during generation. | Workflow starts native llama and the host collector -> generates and saves the answer -> closes those roles. No Python evaluation application starts and no exit is invented for it. | Remove a process and change saved evidence truthfully under G1; PR 1. |
| D7 | Evaluation process flow | After generation and native shutdown, the workflow starts the Python evaluation application, its independent scorer workers and host collection -> sends the saved source/answer to each scorer; only UniEval receives the independent reference -> retains each real result and cleanup outcome. | The same order and independent scoring calls use C1. Neither scorer calls generation or the other scorer. A failed scorer does not erase its completed sibling. | Retain orchestration and score evidence; remove the obsolete generation-API dependency; PRs 1-3. |
| D8 | Comparison-workflow reports | The workflow, not HHEM scoring code, already reads saved run/answer/evaluation files and writes combined JSON, escaped Markdown and the job summary. Generation currently has a real Python-server outcome because that process starts. | The report stays in C8. Generation reports only native and host roles; evaluation still reports its actual application and workers. Unstarted roles and missing readings are not represented by successful flags or zeroes. | Correct evidence after the process removal; PR 1. |
| D9 | TypeScript summary HTTP operation | URL or direct text -> URL extraction/fallback -> first 6000 words at most -> prompt for summary, sentiment and stance classifications -> one fresh model call plus machine sampling -> enriched result, private events and optional job-summary publication. URL-only parsing currently has the documented adapter defect. | C11 takes prepared text, uses the configured default or exact prompt override, and returns the summary product in Table Q. Each request is fresh. Source acquisition, fallback, input shortening, classification, private event storage, machine readings and reporting move to C12. No hidden word cap remains in HTTP. | A real request/result change and product rename; PR 4. |
| D10 | TypeScript full-analysis CLI | CLI and HTTP share the same full pipeline, result schemas, sampling and report function inside the service. | The full pipeline moves to C12, preserving its old analysis output and preparation behavior. The documented URL parser defect is repaired and checked there. This caller is not inserted into the comparison workflow. | Relocate an existing capability rather than delete it; PR 4. |
| D11 | TypeScript operational endpoints | Health includes process memory; a diagnostics endpoint returns memory and cache observations. | Summary health reports availability. The summary service no longer exposes machine inspection; existing host APIs retain that job. | Remove unrelated HTTP fields/operation; PR 4. |
| D12 | Older UniEval scoring operation | Source and summary -> sentence/source-chunk retrieval -> legacy consistency, coherence and fluency plus source-section coverage, sentence explanations and uncovered sections. It does not use native UniEval's independent-reference relevance calculation. | The same method moves to C13 with its own contracts, bounded worker and dated operation. It returns the metrics-only success response in G7. The old script, listener and `/v1/evaluate` route are removed. | Preserve scoring; consolidate deployment and change the route/envelope; PR 5. |
| D13 | Older UniEval side work | Its request handler also samples CPU/memory/swap and writes a duplicate private evaluation event file. The caller separately saves its own completion event and publishes the report. | The API no longer samples the machine or writes the private event file. The existing caller keeps its event/report duties. New legacy machine readings are unavailable: this plan does not add a host-API replacement for them. | Delete duplicate publication and give up those readings as priced in B5; PR 5. |
| D14 | Tests | Workflow, host-compatibility and report tests live under the evaluator project with scorer tests and shared helpers. | Scorer/application tests stay with C1; workflow tests move to C9; the single reusable evaluator harness lives at C10. Real model recordings retain their existing fixture paths and provenance. | Rehome tests, repair imports/child paths and keep both suites selected in CI; PR 3. |
| D15 | Host fingerprint/probe APIs | Dedicated native APIs provide machine identity, samples, task profiles and cache measurements. The comparison workflow already calls the shared TypeScript application's machine group. | They remain the machine-data providers. Their routes and clients use Table Z; measurements, process ownership and payload meanings stay unchanged. | HTTP route cleanup, not a measurement redesign; PR 7. |
| D16 | Feed planning and shared TypeScript hosting | Domain routers provide planning, delivery and machine operations through explicitly selected modules. Some paths already have date versions; several operation names are nouns, bare verbs or nested commands. | Shared hosting remains. First-party operation, health and schema paths follow one documented convention. Planner/delivery route changes do not change their calculations or persistence rules. | Shared readiness and machine routes in PR 7; planner/delivery routes in PR 8. |
| D17 | Prompt ownership | The Yen workflow supplies a short instruction; TypeScript appends a hardcoded output/classification prompt; its CLI repeats the default. Digest and article-comparison prompts live under the Python package. Native UniEval question templates sit inline in its root-level settings file. | Table W names each canonical text file and its existing source. The generator default comes from the effective Yen prompt, not the digest's different task. Prompt overrides remain supported; UniEval keeps its own question-based model input. | Generator/default extraction in PR 4; production and UniEval file relocation in PR 6. |
| D18 | Native settings and ports | Yen and the digest already share the model-server action, Python argument builder, committed origin and selected model declaration. The TypeScript listener repeats its port in an environment default and workflow commands; the comparison workflow separately suppresses raw native logs. | Reuse the native server/request dictionaries unchanged. Put the generator listener and transport/logging controls in its own config; retain separate native, generation, evaluation and shared-TypeScript listener roles. No closed native request schema or new llama wrapper appears. | PRs 1 and 4; settings details in S6-S9. |

## 1. Status Reckoner

**Table E - PR sequence**

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Call native generation without the evaluator | - | A | IN-FLIGHT | curly-lamp | - | - |
| E2 | 2 | Remove generation from the evaluation API | 1 | A | PENDING | - | - | - |
| E3 | 3 | Rename and divide the evaluator and its tests | 2 | A | PENDING | - | - | - |
| E4 | 4 | Rename and isolate the summary generator and its caller | 2 | B | PENDING | - | - | - |
| E5 | 5 | Consolidate source coverage under the summary evaluator | 3, 4 | C | PENDING | - | - | - |
| E6 | 6 | Centralize production and evaluation prompt files | 3, 4 | D | PENDING | - | - | - |
| E7 | 7 | Standardize host and shared TypeScript routes | 2 | E | PENDING | - | - | - |
| E8 | 8 | Standardize planner and delivery routes | 7 | E | PENDING | - | - | - |

## Row #1 - Call native generation without the evaluator

- **Scope:** The existing workflow generates through llama-server directly, without starting or configuring the Python evaluation API.
- **Tasks:**
  1. Update saved-result readers and validation rules before changing the generation writer, using Table G.
  2. Make input reading and same-run preparation use workflow input bounds, not HHEM listener settings. Keep evaluation asset preparation in the orchestration code.
  3. Call the selected native origin for template rendering, health and completion. Remove generation's `api_origin` argument and imports of evaluator-owned generation result models.
  4. Declare the required native completion/error response subset in `native_response.py`. Move the selected native-origin/deadline type into `model_selection.py` before deleting the evaluator-owned generation settings. Preserve the existing finish-reason, choice-count, model-identity, reasoning/final-answer and exact-text checks.
  5. Split phase supervision by the children actually started. Native generation watches its native child; evaluation watches its evaluation application. Host collection retains its existing independent ownership and failure evidence.
  6. Read native logging and host-process bounds from workflow settings. Extract the existing strict record handler and common lifecycle fields before reusing them; do not make a native log import an HHEM event emitter.
  7. Save an accepted answer before cleanup. Retain the original work error and any later cleanup error independently.
  8. Update report assembly, artifact paths and the living workflow page in this PR. No generation report may claim a Python evaluation application ran.
  9. Advance the disposable workflow version in Python and the real Bun machine bridge together under G1; exercise the serialized cross-language startup/control packets, not only Python validation.
- **Files touched:**
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/artifact_paths.py` - derived validated directories for workflow uploads.
  - `.github/scripts/summary-eval-tests/machine-task.ts`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/contracts.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/control.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/generation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/http.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/inputs.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/llama.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/native_log.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/native_response.py` - new, transient native response reader.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_result.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_services.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phases.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/preparation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_models.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_task.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/run.py` - pass the platform-owned artifact-output file only at the CLI boundary.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/serve_api.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/services.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/settings.py`
  - `.github/workflows/summary-eval-tests.yml`
  - `.github/workflows/summary-evaluator-checks.yml` - manual model-free Linux verification.
  - `.github/actions/check-summary-evaluator/action.yml` - one shared verification implementation.
  - `.github/workflows/ci.yml` - temporary manual-only bootstrap until the checker is registered on the default branch.
  - `config/summary-eval-tests.json`
  - `backend/tests/workflows/_harness.py` - bind artifact expressions to the named workflow settings.
  - `backend/tests/workflows/test_ci_selection.py` - keep the manual verification separate from ordinary CI.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_event.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/lifecycle_fields.py` - new extraction of the existing safe lifecycle fields.
  - `services/hhem-evaluator/src/hhem_evaluator/emit_events.py`
  - `services/hhem-evaluator/src/hhem_evaluator/configure_server.py` - existing strict-writer caller.
  - `services/hhem-evaluator/src/hhem_evaluator/write_event_records.py` - new extraction of the existing strict record handler.
  - `services/hhem-evaluator/tests/generation_cases.py`
  - `services/hhem-evaluator/tests/host-profile-bridge.ts` - explicit caller-owned registry input and safe failure-stage evidence.
  - `services/hhem-evaluator/tests/llama_cases.py`
  - `services/hhem-evaluator/tests/machine_task_cases.py`
  - `services/hhem-evaluator/tests/owned_service_child.py`
  - `services/hhem-evaluator/tests/pipeline_cases.py`
  - `services/hhem-evaluator/tests/test_generation_handoff.py`
  - `services/hhem-evaluator/tests/test_native_generation.py` - direct native transport and fresh-request boundaries.
  - `services/hhem-evaluator/tests/test_machine_task.py`
  - `services/hhem-evaluator/tests/test_manual_workflow.py`
  - `services/hhem-evaluator/tests/test_pipeline_control.py`
  - `services/hhem-evaluator/tests/test_pipeline_evaluation.py`
  - `services/hhem-evaluator/tests/test_pipeline_lifetime.py`
  - `services/hhem-evaluator/tests/test_pipeline_measurement.py`
  - `services/hhem-evaluator/tests/test_pipeline_preparation.py`
  - `services/hhem-evaluator/tests/test_pipeline_report.py`
  - `services/hhem-evaluator/tests/test_server_events.py`
  - `services/hhem-evaluator/tests/test_workflow_outcomes.py`
  - `tests/fixtures/hhem-evaluator/pipeline-evidence.json` - current disposable contract example; model recordings remain unchanged.
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect `npm --prefix .\frontend run test:changed -- --list`; use the independent Python environment and lint/type commands in the gate guide. Run the changed workflow modules together, including generation handoff, preparation, control, lifetime, measurement, outcomes and report tests.
  - Local contract cases: test the exact configured request/response byte limits and one byte above each limit; refuse redirects, invalid encoding, incorrect model identity, incomplete answers and changed same-run source/reference/answer hashes.
  - Linux execution gate: complete model-free evaluator/workflow suites, including actual child ownership, parent loss, joined exit, cancellation and partial-result retention. Preserve the socket guard. Send actual Python startup/control packets through the Bun bridge and reject the previous workflow version.
  - CI: retain actual backend, native TypeScript and saved-handoff coverage; ordinary CI does not run the Python evaluator suites.
  - Report: render a representative successful run and a cleanup-failure run through the production report function. Require real native and host outcomes, absent unstarted evaluator outcomes, escaped source text and explicit failures. Review the changed report against the design requirements before merge.
  - Observation, not a merge gate: on the next intended manual workflow run, read `generation-phase.json`, `generation.json`, native logs and the published job report. An evaluator row or readiness wait during generation is a failed cutover; fix this PR's implementation, not the evidence.
- **Oracle:** Run the real generation phase with recorded native responses, evaluator configuration files absent, and no evaluator child; require the bound answer receipt and truthful native/host shutdown evidence. This does not prove live model quality, weight loading or runner speed.
- **Execution status:** Implementation and Windows-compatible checks are complete. The manual Linux verifier runs the remaining complete evaluator/workflow suites before delivery; Windows results do not satisfy that gate.

**Table F - PR 1 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | Reuse the existing workflow and native process owner. There is already an independent native binary; remove only the extra Python forwarding hop. | Fowler; generation and process-owner call sites |
| F2 | Keep native response status/error handling, disabled environment proxies, refused redirects, bounded reads, deadlines and cancellation. The direct caller must not lose controls previously supplied by the proxy. | Fowler; existing bounded HTTP reader |
| F3 | Add workflow settings `max_input_bytes`, `max_generation_request_bytes`, `max_generation_response_bytes`, `native_logging`, `native_log_directory`, `host_startup_timeout_ms`, `host_shutdown_timeout_ms`, `host_stop_grace_ms` and `host_forced_stop_ms`. Preserve the existing five-second stop grace with `host_stop_grace_ms: 5000`; seed other values from their effective settings. Reuse native deadlines/connect bounds. Do not add a public admission queue for one sequential call. | Caller-boundary design; existing lifecycle budgets |
| F4 | Common lifecycle fields exclude the component selector. The native log declares `llama`/`log`; the evaluation application declares its own components. Preserve the existing serialized lifecycle fields and safe-code checks. | Fowler's shared-mechanism boundary |
| F5 | The native log directory is a committed workflow setting. Upload it with the workflow output, not under an evaluator-labelled artifact path. Keep historical log names and event identities intact. | Workflow/report contract |
| F6 | Replace the caller's evaluator-owned `LlamaSettings` import with workflow-owned `NativeGenerationSettings` in `model_selection.py`. Retain its `base_url`, `request_timeout_ms` and native-origin validation. Model selection and destination still come from the same committed files; no new model or address is introduced. | Existing model-selection reader; caller boundary |
| F7 | Keep the external native request body as an open JSON mapping. The existing request builder already passes sampling entries through; preserve that behavior rather than replacing the removed proxy model with another native request schema. Each generation call starts fresh. | Native protocol boundary; A11-A12 |
| F8 | A ready host gets its advertised lifecycle timeout plus F3's stop grace. Before readiness use the host shutdown timeout; after termination wait the stop grace; after killing use the forced-stop budget for joining. Remove host-path reads of evaluator worker settings without collapsing these different waits. | Existing phase and process-owner shutdown paths |

**Table G - Saved and live compatibility rules**

| Id | Family | Exact change or invariant | Reader/writer order and read rule |
| --- | --- | --- | --- |
| G1 | Same-run workflow packets | Generation has `api_stopped`, `worker_exit_confirmed` and `unieval_worker_exit_confirmed` set to `null`, because those children did not start. Completion requires each actually started child to stop. | Update phase/evaluation/report readers before writers. Stamp Python's `WORKFLOW_VERSION`, its `WorkflowVersion` literal and changelog, and the machine bridge's `VERSION` together. Reject older packets explicitly under the current-only rule. Native machine-evidence formats are separate and do not restamp for this control change. |
| G2 | Same-run identity and retained work | Source, independent reference, selected/loaded model, answer bytes and run remain bound. Removing an unused process is not permission to accept a different answer or start evaluation after failed generation cleanup. | Keep hash and identity checks in all readers. A completed sibling score or accepted answer survives an unrelated later failure. |
| G3 | Server outcomes and reports | Generate a `fastapi-server` outcome only when that process actually started. No zero startup time, success flag or resource reading may stand for an unstarted process. | Update report readers before phase writers. Preserve existing source/type identifiers for processes that still use them; an API display-name change does not rename event history. |
| G4 | Evaluation application live contracts | PR 2 removes generation and changes first-party HTTP paths under Table Z. It removes the `llama` route-selection value, health member, transport settings and generation CLI option. | PR 1 moves the named generation caller first. Switch evaluator paths and their callers together; removed paths return 404 with no permanent alias. Stamp the changed application protocol/changelog. Its native read rule remains current-only. |
| G5 | Scoring contracts and recordings | HHEM and native UniEval request/result fields, scoring schema versions, errors, reductions, event seeds and prediction/identity recording bytes remain unchanged during PRs 1-3. Their HTTP addresses change independently under G4. | Compare generated scoring schemas and serialized recorded cases before/after. Do not rewrite recordings to conceal a path change or rename fixture directories for appearance. |
| G6 | TypeScript summary HTTP contract and caller | PR 4 changes the HTTP product and its Yen caller/report to Table Q. The full-analysis CLI's saved application payload and events move without changing their meaning. | Split the CLI path first, then change the HTTP reader/writer and summary-only caller together. Declare dated native summary API metadata. The summary caller uses the existing metadata envelope and validates its nested API response against that declared contract. Retain the current-only rule for moved full-analysis events; a move alone does not restamp them. |
| G7 | Source-coverage request and response | Use explicit `source_text`/`summary_text` and `{status: "success", metrics: <unchanged metrics>}` without duplicate events or `serverTelemetry`. Failure is `{error: {code, type: "api_error", message}}` through the extracted safe renderer, with U12's fixed policy. No partial metrics or raw exception text accompany failure. | Update the TypeScript request builder and success/failure/report readers before switching the writer. Retain historical foreign-response/measurement readback. No live old route or camelCase alias remains. Valid recorded calculations retain parity; malformed native results now fail rather than become zero scores. |
| G8 | Native llama-server JSON | No new repository schema enumerates its request parameters. Configured native fields remain pass-through, with only application-owned controls, destination and bounded transport checked locally. | Keep a representative forwarding test and existing safety cases. A newly supported sampler or server flag needs only a config edit, not a new field declaration or an expected-key-list update. |
| G9 | Prompt relocation and override | Relocated production/scorer templates keep their rendered text, substitution rules, model output controls and prompt-digest meaning. Generator requests identify the actual default or override used. | Bind readers to the new configured files before retiring old copies. Preserve exact whitespace where it affects rendering; do not silently trim or add a newline to an inline UniEval template. No historical prompt capture is rewritten. |

**Table H - PR 1 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Change the completion URL but retain the Python process and old success predicates | Generation still depends on evaluator settings and cleanup, so the APIs are not independent. | Retains a listener, startup wait, shutdown failure mode and misleading report row. | Fowler; current phase validators |
| H2 | Move the forwarding code into a new service | Moves the responsibility leak rather than removing an unnecessary hop. | Another package, server lifecycle, configuration surface and deployment. | Fowler |
| H3 | Keep old success checks by setting `api_stopped` to true without starting the API | Records a process observation that never occurred. | Invalid evidence and reports that cannot distinguish a real clean exit from no process. | Report contract |

## Row #2 - Remove generation from the evaluation API

- **Scope:** The Python application exposes evaluation and its own operational health only.
- **Tasks:**
  1. Remove the generation router, forwarder, upstream health polling and client lifecycle after PR 1.
  2. Restrict enabled routes to the two scorers. Stop loading generation model configuration or generation transport settings.
  3. Preserve generic safe error rendering currently located in generation-labelled files by extracting it before deletion.
  4. Remove generation-only diagnostics from the application contract. Keep operational logging and readiness for enabled scorers.
  5. Change the application title to the final API name in Table C. Update OpenAPI, configuration, architecture and reference docs together.
  6. Remove obsolete proxy tests only after retaining generic request-guard, malformed-response and shutdown-error coverage in the owning suites.
  7. Publish the routing convention in `docs/reference/api-routing.md` and apply the evaluator entries in Table Z. Change the real workflow client, readiness probes, OpenAPI and named route tests together; do not retain the old paths.
- **Files touched:**
  - `services/hhem-evaluator/src/hhem_evaluator/__main__.py`
  - `services/hhem-evaluator/src/hhem_evaluator/api_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/configure_server.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_health.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_settings.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_contract.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/server_event.py`
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/base.py`
  - `services/hhem-evaluator/src/hhem_evaluator/guard_local_requests.py`
  - `services/hhem-evaluator/src/hhem_evaluator/serve_api.py`
  - `services/hhem-evaluator/src/hhem_evaluator/refuse_request.py` - new, safe generic error renderer extracted from the old forwarder.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/api_error_detail.py` - new, generic error shape extracted from the old generation result module.
  - `services/hhem-evaluator/src/hhem_evaluator/dispatch_llama.py` - delete.
  - `services/hhem-evaluator/src/hhem_evaluator/forward_llama.py` - delete after the generic renderer is extracted.
  - `services/hhem-evaluator/src/hhem_evaluator/llama_router.py` - delete.
  - `services/hhem-evaluator/src/hhem_evaluator/load_llama_settings.py` - delete.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_request.py` - delete.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_result.py` - delete after generic errors and required caller response validation have moved.
  - `services/hhem-evaluator/src/hhem_evaluator/contracts/llama_settings.py` - delete.
  - `services/hhem-evaluator/tests/service_cases.py`
  - `services/hhem-evaluator/tests/llama_cases.py`
  - `services/hhem-evaluator/tests/test_api.py`
  - `services/hhem-evaluator/tests/test_contracts.py`
  - `services/hhem-evaluator/tests/test_settings.py`
  - `services/hhem-evaluator/tests/test_server_events.py`
  - `services/hhem-evaluator/tests/test_server_lifecycle.py`
  - `services/hhem-evaluator/tests/test_llama_api.py` - retire proxy-specific cases; retain generic guard cases in `test_api.py`.
  - `services/hhem-evaluator/tests/test_llama_contracts.py` - retire proxy contracts; caller-native response coverage ships in PR 1.
  - `config/fastapi-server.json`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/serve_api.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluate_pair.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_task.py`
  - `docs/reference/api-routing.md` - new, shared first-party HTTP convention.
  - `docs/architecture/evaluation/local-model-api.md`
  - `docs/reference/fastapi-server.md`
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/unieval-api.md`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: shared selector inspection, service Ruff/mypy and one focused service invocation covering application routes, settings, contracts, events and lifecycle.
  - Contract: the former generation route returns HTTP 404; neither OpenAPI nor aggregate health advertises generation. Old generation-only route values, settings and CLI options are refused, not ignored.
  - Integration: evaluate with generation configuration absent. HHEM-only does not read UniEval configuration; UniEval-only does not read HHEM configuration. Disabled scorers do not construct workers or import optional model libraries.
  - Linux execution gate: complete model-free service/workflow suites. Keep request-body, Host/Origin, disconnect, deadline and shutdown-failure protections. Ordinary CI keeps its existing non-evaluator gates.
- **Oracle:** Start the real evaluation application with no generation configuration or process, obtain both recorded scoring results, and observe no generation route. This does not prove numerical model quality or separate HTTP-process failure isolation.

**Table I - PR 2 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Keep one evaluation listener and separate scorer workers/queues. Cohosting two summary scorers does not make one scorer execute the other. | Fowler |
| I2 | Switch the evaluator's operation, health and schema paths using Table Z. Keep scoring fields, meanings and model identities unchanged. Removing old paths is an intentional HTTP break, not a reason to translate scores. | Routing contract; Table G |
| I3 | Keep HTTPX. Pinned sentence-resource preparation and offline ASGI tests still use it after forwarding is removed. | Fowler; remaining dependency consumers |
| I4 | Preserve safe error bodies for refused local requests, health, OpenAPI and unknown routes. Their current location under generation is an ownership defect, not permission to remove the control. | Fowler; request-guard call sites |
| I5 | Every first-party HTTP operation uses `/api/{YYYY-MM-DD}/{verb-noun-operation}`. The cutover paths in Table Z use declared `2026-11-05` protocol constants; the date is not calculated per request. `2026-11-02` is also a valid date format, not a requirement to backdate every family. Later breaking changes restamp their affected HTTP family. | First-party route convention |
| I6 | Apply the convention to all TypeScript APIs and to evaluation, including operational health and schema paths. Do not retain `/api/summarize`, `/api/diagnostics`, `/health`, `/v1/evaluate` or retired domain paths as first-party aliases. Framework default routes are not external-protocol exceptions. | First-party route convention |
| I7 | Keep upstream-defined llama-server paths, including `/v1/chat/completions`, `/completions`, `/apply-template`, `/props`, `/health`, `/metrics`, `/tokenize` and `/v1/models`. Document their external-protocol reason. Any other first-party deviation requires a maintainer decision before implementation. | External protocol boundary |
| I8 | HTTP route dates, payload schema dates, external protocol versions and package release versions are different identities. Do not change a score schema, CloudEvents `specversion` or historical recording merely to make it equal the new URL date. | Native protocol and saved-data boundaries |

**Table J - PR 2 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Keep a dormant generation route or permanent compatibility proxy | The evaluation application would still contain another API's implementation. | Ongoing generation settings, contracts, security controls and regression coverage inside evaluation. | Fowler |
| J2 | Delete every generation-labelled file before extracting common refusals | Removes a safety control with unrelated forwarding code. | A request-guard regression; the renderer would have to be rebuilt and proved again. | Fowler |

## Row #3 - Rename and divide the evaluator and its tests

- **Scope:** The evaluation distribution, source, configuration and tests have explicit ownership without changing scoring behavior.
- **Tasks:**
  1. In a structural commit, split the mixed modules in Table M while imports still resolve. Preserve concrete worker policies, error mappings and generated schema metadata.
  2. In a separate structural commit, apply Tables K, L and N. Use the existing environment and dependency versions; regenerate the existing lockfile after metadata changes.
  3. Enforce direction: `shared` imports neither scorer nor HTTP serving code; neither scorer imports the other; `serve_http` assembles the enabled scorers. Pass frozen shared settings and closed event-writing functions into scorer code.
  4. Keep service tests in their service and move workflow tests to the named workflow test package. Share the existing evaluator test harness once, through the support package in Table C.
  5. Update every external consumer in the exact file list. Reconstruct the repository root at the new fixed path depth; do not search upward or walk the repository.
  6. Rebuild the environment at the new project location. Do not move `.venv`, delete old caches, or rewrite recordings. Use the new configured cache/log paths; prepare them or relocate only stopped-service disposable caches as an operator action.
  7. Keep API and workflow tests as separately selectable inputs in one locked Python environment. CI must name both, not silently lose the moved workflow tests.
  8. Group configuration using Table K. Retire the root-level workflow filename, not the live transport/lifecycle/output settings it contains. The workflow file remains caller-owned; neither scorer reads it. Prompt text moves out separately in PR 6.
- **Files touched - project, config and documentation moves:**

**Table K - Project and authored-file move map**

| Id | Existing full path | Destination or action |
| --- | --- | --- |
| K1 | `services/hhem-evaluator/.python-version` | `services/summary_evaluator/.python-version` |
| K2 | `services/hhem-evaluator/pyproject.toml` | `services/summary_evaluator/pyproject.toml`; distribution/import metadata, test paths and imports |
| K3 | `services/hhem-evaluator/uv.lock` | `services/summary_evaluator/uv.lock`; regenerate with existing dependency versions |
| K4 | `services/hhem-evaluator/scripts/capture-model-recordings.py` | `services/summary_evaluator/scripts/capture-model-recordings.py` |
| K5 | `services/hhem-evaluator/scripts/capture-unieval-recordings.py` | `services/summary_evaluator/scripts/capture-unieval-recordings.py` |
| K6 | `services/hhem-evaluator/scripts/prepare-unieval-resources.py` | `services/summary_evaluator/scripts/prepare-unieval-resources.py` |
| K7 | `services/hhem-evaluator/scripts/recording_json.py` | `services/summary_evaluator/scripts/recording_json.py` |
| K8 | `config/fastapi-server.json` | `config/summary-evals/api.json`; shared evaluation listener, guards and logging |
| K9 | `config/hhem-evaluator/settings.json` | `config/summary-evals/hhem-evaluator/settings.json` |
| K10 | `config/unieval-evaluator.json` | `config/summary-evals/unieval-evaluator/settings.json`; repository-authored settings, not the model's downloaded `config.json` |
| K11 | `docs/architecture/evaluation/local-model-api.md` | `docs/architecture/evaluation/summary-evaluator.md` |
| K12 | `docs/reference/fastapi-server.md` | `docs/reference/summary-evaluator-api.md` |
| K13 | `config/summary-eval-tests.json` | `config/summary-evals/workflow.json`; preserve workflow-owned bounds, waits, output paths and identity settings; replace inline generation wording with its configured prompt file in PR 6 |

- **Files touched - source moves:** Each source below is a full path. The earlier generation retirements are listed only in PR 2.

**Table L - Source move map**

| Id | Existing full path | Destination full path |
| --- | --- | --- |
| L1 | `services/hhem-evaluator/src/hhem_evaluator/__init__.py` | `services/summary_evaluator/src/summary_evaluator/__init__.py` |
| L2 | `services/hhem-evaluator/src/hhem_evaluator/__main__.py` | `services/summary_evaluator/src/summary_evaluator/__main__.py` |
| L3 | `services/hhem-evaluator/src/hhem_evaluator/api_settings.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/api_settings.py` |
| L4 | `services/hhem-evaluator/src/hhem_evaluator/configure_server.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/configure_server.py` |
| L5 | `services/hhem-evaluator/src/hhem_evaluator/guard_local_requests.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/guard_local_requests.py` |
| L6 | `services/hhem-evaluator/src/hhem_evaluator/run_server.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/run_server.py` |
| L7 | `services/hhem-evaluator/src/hhem_evaluator/serve_api.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/serve_api.py` |
| L8 | `services/hhem-evaluator/src/hhem_evaluator/refuse_request.py` - introduced in PR 2 | `services/summary_evaluator/src/summary_evaluator/serve_http/refuse_request.py` |
| L9 | `services/hhem-evaluator/src/hhem_evaluator/control_service.py` | `services/summary_evaluator/src/summary_evaluator/hhem/control_service.py` |
| L10 | `services/hhem-evaluator/src/hhem_evaluator/fail_evaluation.py` | `services/summary_evaluator/src/summary_evaluator/hhem/fail_evaluation.py` |
| L11 | `services/hhem-evaluator/src/hhem_evaluator/hhem_router.py` | `services/summary_evaluator/src/summary_evaluator/hhem/hhem_router.py` |
| L12 | `services/hhem-evaluator/src/hhem_evaluator/load_settings.py` | `services/summary_evaluator/src/summary_evaluator/hhem/load_settings.py` |
| L13 | `services/hhem-evaluator/src/hhem_evaluator/maintain_worker.py` | `services/summary_evaluator/src/summary_evaluator/hhem/maintain_worker.py` |
| L14 | `services/hhem-evaluator/src/hhem_evaluator/plan_windows.py` | `services/summary_evaluator/src/summary_evaluator/hhem/plan_windows.py` |
| L15 | `services/hhem-evaluator/src/hhem_evaluator/resolve_request.py` | `services/summary_evaluator/src/summary_evaluator/hhem/resolve_request.py` |
| L16 | `services/hhem-evaluator/src/hhem_evaluator/run_worker.py` | `services/summary_evaluator/src/summary_evaluator/hhem/run_worker.py` |
| L17 | `services/hhem-evaluator/src/hhem_evaluator/score_windows.py` | `services/summary_evaluator/src/summary_evaluator/hhem/score_windows.py` |
| L18 | `services/hhem-evaluator/src/hhem_evaluator/control_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/control_unieval.py` |
| L19 | `services/hhem-evaluator/src/hhem_evaluator/dispatch_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/dispatch_unieval.py` |
| L20 | `services/hhem-evaluator/src/hhem_evaluator/fail_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/fail_unieval.py` |
| L21 | `services/hhem-evaluator/src/hhem_evaluator/load_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval.py` |
| L22 | `services/hhem-evaluator/src/hhem_evaluator/load_unieval_resources.py` | `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval_resources.py` |
| L23 | `services/hhem-evaluator/src/hhem_evaluator/load_unieval_settings.py` | `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval_settings.py` |
| L24 | `services/hhem-evaluator/src/hhem_evaluator/maintain_unieval_worker.py` | `services/summary_evaluator/src/summary_evaluator/unieval/maintain_unieval_worker.py` |
| L25 | `services/hhem-evaluator/src/hhem_evaluator/plan_unieval_windows.py` | `services/summary_evaluator/src/summary_evaluator/unieval/plan_unieval_windows.py` |
| L26 | `services/hhem-evaluator/src/hhem_evaluator/prepare_unieval_resources.py` | `services/summary_evaluator/src/summary_evaluator/unieval/prepare_unieval_resources.py` |
| L27 | `services/hhem-evaluator/src/hhem_evaluator/reduce_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/reduce_unieval.py` |
| L28 | `services/hhem-evaluator/src/hhem_evaluator/score_unieval.py` | `services/summary_evaluator/src/summary_evaluator/unieval/score_unieval.py` |
| L29 | `services/hhem-evaluator/src/hhem_evaluator/unieval_router.py` | `services/summary_evaluator/src/summary_evaluator/unieval/unieval_router.py` |
| L30 | `services/hhem-evaluator/src/hhem_evaluator/unieval_worker.py` | `services/summary_evaluator/src/summary_evaluator/unieval/unieval_worker.py` |
| L31 | `services/hhem-evaluator/src/hhem_evaluator/load_model_assets.py` | `services/summary_evaluator/src/summary_evaluator/shared/load_model_assets.py` |
| L32 | `services/hhem-evaluator/src/hhem_evaluator/queue_evaluations.py` | `services/summary_evaluator/src/summary_evaluator/shared/queue_evaluations.py` |
| L33 | `services/hhem-evaluator/src/hhem_evaluator/read_process_identity.py` | `services/summary_evaluator/src/summary_evaluator/shared/read_process_identity.py` |
| L34 | `services/hhem-evaluator/src/hhem_evaluator/read_request_body.py` | `services/summary_evaluator/src/summary_evaluator/shared/read_request_body.py` |
| L35 | `services/hhem-evaluator/src/hhem_evaluator/watch_worker_parent.py` | `services/summary_evaluator/src/summary_evaluator/shared/watch_worker_parent.py` |
| L36 | `services/hhem-evaluator/src/hhem_evaluator/write_event_records.py` - introduced in PR 1 | `services/summary_evaluator/src/summary_evaluator/shared/write_event_records.py` |
| L37 | `services/hhem-evaluator/src/hhem_evaluator/contracts/__init__.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/__init__.py` |
| L38 | `services/hhem-evaluator/src/hhem_evaluator/contracts/api_health.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/api_health.py` |
| L39 | `services/hhem-evaluator/src/hhem_evaluator/contracts/api_settings.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/api_settings.py` |
| L40 | `services/hhem-evaluator/src/hhem_evaluator/contracts/api_error_detail.py` - introduced in PR 2 | `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/error_detail.py` |
| L41 | `services/hhem-evaluator/src/hhem_evaluator/contracts/server_contract.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/server_contract.py` |
| L42 | `services/hhem-evaluator/src/hhem_evaluator/contracts/lifecycle_fields.py` - introduced in PR 1 | `services/summary_evaluator/src/summary_evaluator/shared/contracts/diagnostic_data.py` |
| L43 | `services/hhem-evaluator/src/hhem_evaluator/contracts/worker_identity.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/worker_identity.py` |
| L44 | `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluation_event.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/evaluation_event.py` |
| L45 | `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluation_progress.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/evaluation_progress.py` |
| L46 | `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluation_result.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/evaluation_result.py` |
| L47 | `services/hhem-evaluator/src/hhem_evaluator/contracts/model_identity.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/model_identity.py` |
| L48 | `services/hhem-evaluator/src/hhem_evaluator/contracts/service_health.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/service_health.py` |
| L49 | `services/hhem-evaluator/src/hhem_evaluator/contracts/worker_message.py` | `services/summary_evaluator/src/summary_evaluator/hhem/contracts/worker_message.py` |
| L50 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_contract.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_contract.py` |
| L51 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_error.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_error.py` |
| L52 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_recording.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_recording.py` |
| L53 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_request.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_request.py` |
| L54 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_result.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_result.py` |
| L55 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_settings.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_settings.py` |
| L56 | `services/hhem-evaluator/src/hhem_evaluator/contracts/unieval_worker_message.py` | `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_worker_message.py` |

- **Files touched - mixed modules:** These are splits, not blind moves. Keep model class names stable when they contribute to generated schemas.

**Table M - Mixed-source split map**

| Id | Existing full path | Destination full paths and responsibility |
| --- | --- | --- |
| M1 | `services/hhem-evaluator/src/hhem_evaluator/contracts/base.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/base.py` - strict primitives; `services/summary_evaluator/src/summary_evaluator/shared/contracts/api_paths.py` - dated first-party paths; `services/summary_evaluator/src/summary_evaluator/hhem/contracts/base.py` - unchanged HHEM scoring schema metadata and vocabulary |
| M2 | `services/hhem-evaluator/src/hhem_evaluator/contracts/service_settings.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/service_settings.py` - model assets, listener, logging, queue, evaluation deadlines, worker bounds and startup context; `services/summary_evaluator/src/summary_evaluator/hhem/contracts/service_settings.py` - HHEM model, scoring, response and resolved service settings |
| M3 | `services/hhem-evaluator/src/hhem_evaluator/contracts/error_detail.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/error_policy.py` - fixed codes and HTTP policy; `services/summary_evaluator/src/summary_evaluator/hhem/contracts/error_detail.py` - HHEM public error fields and projection |
| M4 | `services/hhem-evaluator/src/hhem_evaluator/contracts/evaluate_request.py` | `services/summary_evaluator/src/summary_evaluator/shared/contracts/optional_fields.py` - omission helpers; `services/summary_evaluator/src/summary_evaluator/hhem/contracts/evaluate_request.py` - HHEM request and effective settings |
| M5 | `services/hhem-evaluator/src/hhem_evaluator/contracts/server_event.py` | `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/server_event.py` - application diagnostic selector and combined event envelope; common fields already moved by L42 |
| M6 | `services/hhem-evaluator/src/hhem_evaluator/emit_events.py` | `services/summary_evaluator/src/summary_evaluator/hhem/emit_events.py` - HHEM sequence and causal links; `services/summary_evaluator/src/summary_evaluator/serve_http/emit_events.py` - validated application envelopes; remaining common delivery joins `services/summary_evaluator/src/summary_evaluator/shared/write_event_records.py` from L36 |
| M7 | `services/hhem-evaluator/src/hhem_evaluator/exchange_packets.py` | `services/summary_evaluator/src/summary_evaluator/shared/exchange_packets.py` - byte channel and shared escaping bound; `services/summary_evaluator/src/summary_evaluator/hhem/exchange_packets.py` - HHEM packet sizes and packet models |
| M8 | `services/hhem-evaluator/src/hhem_evaluator/load_model.py` | `services/summary_evaluator/src/summary_evaluator/shared/quiet_model_output.py` - output suppression; `services/summary_evaluator/src/summary_evaluator/hhem/load_model.py` - official HHEM predictor |
| M9 | `services/hhem-evaluator/src/hhem_evaluator/resolve_ids.py` | `services/summary_evaluator/src/summary_evaluator/shared/create_execution_id.py` - UUIDv4 generation; `services/summary_evaluator/src/summary_evaluator/hhem/resolve_ids.py` - existing HHEM request/correlation and deterministic event identities |
| M10 | `services/hhem-evaluator/src/hhem_evaluator/dispatch_evaluation.py` | `services/summary_evaluator/src/summary_evaluator/shared/disconnected_response.py` - disconnect response; `services/summary_evaluator/src/summary_evaluator/hhem/dispatch_evaluation.py` - HHEM HTTP execution |
| M11 | No existing module; replace shared mechanisms' HHEM failure dependency | `services/summary_evaluator/src/summary_evaluator/shared/fail_runtime.py` - closed code-only runtime failures; each scorer translates these to its existing public errors |
| M12 | Package initializers created with real modules | `services/summary_evaluator/src/summary_evaluator/serve_http/__init__.py`; `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/__init__.py`; `services/summary_evaluator/src/summary_evaluator/shared/__init__.py`; `services/summary_evaluator/src/summary_evaluator/shared/contracts/__init__.py`; `services/summary_evaluator/src/summary_evaluator/hhem/__init__.py`; `services/summary_evaluator/src/summary_evaluator/unieval/__init__.py`; `services/summary_evaluator/src/summary_evaluator/unieval/contracts/__init__.py` |

- **Files touched - test moves:** Keep basenames except the native generation helper, whose old name describes the removed proxy. Preserve the model recording files under `tests/fixtures/`.

**Table N - Test and helper move map**

| Id | Existing full path | Destination full path |
| --- | --- | --- |
| N1 | `services/hhem-evaluator/tests/__init__.py` | `services/summary_evaluator/tests/__init__.py` |
| N2 | `services/hhem-evaluator/tests/check_uuid_vectors.ts` | `services/summary_evaluator/tests/check_uuid_vectors.ts` |
| N3 | `services/hhem-evaluator/tests/contract_examples.py` | `services/summary_evaluator/tests/summary_evaluator_cases/contract_examples.py` |
| N4 | `services/hhem-evaluator/tests/replay_predictions.py` | `services/summary_evaluator/tests/summary_evaluator_cases/replay_predictions.py` |
| N5 | `services/hhem-evaluator/tests/service_cases.py` | `services/summary_evaluator/tests/summary_evaluator_cases/service_cases.py` |
| N6 | `services/hhem-evaluator/tests/unieval_cases.py` | `services/summary_evaluator/tests/summary_evaluator_cases/unieval_cases.py` |
| N7 | `services/hhem-evaluator/tests/observe_owned_exit.py` | `services/summary_evaluator/tests/summary_evaluator_cases/observe_owned_exit.py` |
| N8 | `services/hhem-evaluator/tests/test_api.py` | `services/summary_evaluator/tests/test_api.py` |
| N9 | `services/hhem-evaluator/tests/test_contracts.py` | `services/summary_evaluator/tests/test_contracts.py` |
| N10 | `services/hhem-evaluator/tests/test_event_ids.py` | `services/summary_evaluator/tests/test_event_ids.py` |
| N11 | `services/hhem-evaluator/tests/test_recording_compatibility.py` | `services/summary_evaluator/tests/test_recording_compatibility.py` |
| N12 | `services/hhem-evaluator/tests/test_scoring.py` | `services/summary_evaluator/tests/test_scoring.py` |
| N13 | `services/hhem-evaluator/tests/test_server_events.py` | `services/summary_evaluator/tests/test_server_events.py` |
| N14 | `services/hhem-evaluator/tests/test_server_lifecycle.py` | `services/summary_evaluator/tests/test_server_lifecycle.py` |
| N15 | `services/hhem-evaluator/tests/test_settings.py` | `services/summary_evaluator/tests/test_settings.py` |
| N16 | `services/hhem-evaluator/tests/test_text_boundaries.py` | `services/summary_evaluator/tests/test_text_boundaries.py` |
| N17 | `services/hhem-evaluator/tests/test_unieval_api.py` | `services/summary_evaluator/tests/test_unieval_api.py` |
| N18 | `services/hhem-evaluator/tests/test_unieval_contracts.py` | `services/summary_evaluator/tests/test_unieval_contracts.py` |
| N19 | `services/hhem-evaluator/tests/test_unieval_reduction.py` | `services/summary_evaluator/tests/test_unieval_reduction.py` |
| N20 | `services/hhem-evaluator/tests/test_unieval_retirement.py` | `services/summary_evaluator/tests/test_unieval_retirement.py` |
| N21 | `services/hhem-evaluator/tests/test_unieval_scoring.py` | `services/summary_evaluator/tests/test_unieval_scoring.py` |
| N22 | `services/hhem-evaluator/tests/test_unieval_windows.py` | `services/summary_evaluator/tests/test_unieval_windows.py` |
| N23 | `services/hhem-evaluator/tests/test_unieval_worker.py` | `services/summary_evaluator/tests/test_unieval_worker.py` |
| N24 | `services/hhem-evaluator/tests/test_windows.py` | `services/summary_evaluator/tests/test_windows.py` |
| N25 | `services/hhem-evaluator/tests/test_worker_lifecycle.py` | `services/summary_evaluator/tests/test_worker_lifecycle.py` |
| N26 | `services/hhem-evaluator/tests/generation_cases.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/generation_cases.py` |
| N27 | `services/hhem-evaluator/tests/llama_cases.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/native_cases.py` |
| N28 | `services/hhem-evaluator/tests/machine_task_cases.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/machine_task_cases.py` |
| N29 | `services/hhem-evaluator/tests/native_launch_child.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/native_launch_child.py` |
| N30 | `services/hhem-evaluator/tests/owned_service_child.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/owned_service_child.py` |
| N31 | `services/hhem-evaluator/tests/pipeline_cases.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/pipeline_cases.py` |
| N32 | `services/hhem-evaluator/tests/host-profile-bridge.ts` | `.github/scripts/summary-eval-tests/summary_eval_tests/host-profile-bridge.ts` |
| N33 | `services/hhem-evaluator/tests/test_evaluator_response_binding.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_evaluator_response_binding.py` |
| N34 | `services/hhem-evaluator/tests/test_generation_handoff.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_generation_handoff.py` |
| N35 | `services/hhem-evaluator/tests/test_host_profile_reader_parity.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_host_profile_reader_parity.py` |
| N36 | `services/hhem-evaluator/tests/test_machine_task.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_machine_task.py` |
| N37 | `services/hhem-evaluator/tests/test_manual_workflow.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_manual_workflow.py` |
| N38 | `services/hhem-evaluator/tests/test_native_launch.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_native_launch.py` |
| N39 | `services/hhem-evaluator/tests/test_pipeline_control.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_control.py` |
| N40 | `services/hhem-evaluator/tests/test_pipeline_evaluation.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_evaluation.py` |
| N41 | `services/hhem-evaluator/tests/test_pipeline_lifetime.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_lifetime.py` |
| N42 | `services/hhem-evaluator/tests/test_pipeline_measurement.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_measurement.py` |
| N43 | `services/hhem-evaluator/tests/test_pipeline_preparation.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_preparation.py` |
| N44 | `services/hhem-evaluator/tests/test_pipeline_report.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_pipeline_report.py` |
| N45 | `services/hhem-evaluator/tests/test_unieval_workflow.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_unieval_workflow.py` |
| N46 | `services/hhem-evaluator/tests/test_unieval_workflow_fixture.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_unieval_workflow_fixture.py` |
| N47 | `services/hhem-evaluator/tests/test_workflow_health_isolation.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_workflow_health_isolation.py` |
| N48 | `services/hhem-evaluator/tests/test_workflow_outcomes.py` | `.github/scripts/summary-eval-tests/summary_eval_tests/test_workflow_outcomes.py` |
| N49 | No existing file | `services/summary_evaluator/tests/summary_evaluator_cases/__init__.py` |
| N50 | No existing file | `.github/scripts/summary-eval-tests/summary_eval_tests/__init__.py` |

- **Files touched - every external old-name reference and semantic documentation consumer:**
  - `.github/scripts/summary-eval-tests/machine-task.ts`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/contracts.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/control.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluate_pair.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/evaluation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/generation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/host_reader.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/inputs.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/llama.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/model_selection.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/native_log.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/native_response.py` - introduced in PR 1.
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_result.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phase_services.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/phases.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/preparation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_models.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/report_task.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/serve_api.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/services.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/settings.py`
  - `.github/workflows/ci.yml` - verify evaluator setup remains excluded; no Python job migration.
  - `.github/workflows/summary-eval-tests.yml`
  - `.gitignore`
  - `backend/tests/workflows/test_ci_selection.py`
  - `TODO/20261103-standardize-typescript-metadata-plan.md` - update current path references; do not rewrite shipped outcomes.
  - `docs/architecture/contracts/identity.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/evaluation/hhem-evaluation-api.md`
  - `docs/architecture/evaluation/unieval-api.md`
  - `docs/how-to/run-hhem-evaluation-api.md`
  - `docs/how-to/run-unieval-evaluation-api.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/reference/hhem-evaluation-api.md`
  - `docs/reference/unieval-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/reference/summary-evaluation-workflow.md`
- **Acceptance gates:**
  - Local inventory: derive the baseline with `git ls-files -- services/hhem-evaluator` and external references with `git grep -l -e hhem-evaluator -e hhem_evaluator -- . ':!services/hhem-evaluator/**'`. These are one-time change-inventory commands, not production/test tree scans. Every returned path must be assigned to PR 2 or this PR.
  - Local: inspect the shared selector; regenerate the lock through uv; install the renamed distribution in its model-free Python environment. Run Ruff/mypy over the moved service, helper packages and workflow; compile the relocated real host bridge with the existing TypeScript compiler.
  - Local parity: compare generated scoring schemas and existing recorded outputs before/after. Cover HHEM primary/full reuse, complete windows, partial retention, all native UniEval dimensions, incomplete dimensions, fixed errors and deterministic HHEM event IDs.
  - Local behavior: run actual installed-package imports and spawned workers, not merely source-tree imports. Verify single-scorer settings isolation and the distinct HHEM replacement/UniEval failure policies.
  - Linux execution gate: run complete service and moved workflow suites with the explicit service pytest configuration. Update the manual workflow's project directory, compiler target and resource preparation, plus the gate guide's lint/type/test commands.
  - CI: update the named workflow-selection test's directory assertion and carry the manual model-free Linux verifier across the moves. Retain the prohibition on evaluator setup in ordinary `ci.yml`, its backend/native coverage and required-check names.
  - Documentation: verify inbound links to moved pages, live launch commands, configured cache/log locations, report config links and fixture provenance. Keep any required historical check/event identifier documented as such, not as a current package path.
- **Oracle:** The complete named recording set produces the same scoring schemas, accepted values, errors and event IDs through the installed renamed application and real workers, with all baseline files assigned to one move or retirement. This does not prove a new model run or remove the shared application's restart boundary.

**Table O - PR 3 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| O1 | One distribution/environment, not a package per scorer. Keep existing Python support and model-library versions, including the independent optional model environment. | Fowler |
| O2 | Shared queue, byte-channel and parent-watch failures become code-only internal failures. Each scorer maps them to its unchanged public error. In particular, retain each worker's current parent-watch failure result. | Fowler; process-failure contract |
| O3 | Preserve inherited schema metadata when extracting primitives. A neutral import location is not permission to change emitted model titles, schema versions or serializer behavior. | Fowler; Table G |
| O4 | The common test harness remains in the service's uniquely named support package; moved workflow tests import it explicitly. Add the service test-support root and workflow package root to the existing test configuration. Do not add another Python environment or duplicate helpers. | Test import inventory |
| O5 | Use configured paths `services/summary_evaluator/var/model-cache`, `services/summary_evaluator/var/unieval-cache` and `services/summary_evaluator/var/server-logs`. Native generation logs use F5 instead. Directory changes affect disposable assets only. | Package/config boundary |
| O6 | Package and import moves do not restamp scoring contracts or rewrite recordings. Version only an actual changed family as specified in Table G. | Fowler; schema compatibility |
| O7 | Keep the installed `src` layout and use underscores for both the outer project and inner import package. Do not flatten the import package into the manifest/test directory merely to remove repeated spelling. | Fowler; installed-package isolation |
| O8 | The root-level workflow config is not redundant: its response/control bounds, waits, lifecycle limits, output paths and run labels are still read. Move those settings to K13, remove inline prompt wording in PR 6, and remove a duplicate only after naming its existing authoritative reader. | Direct workflow settings and native-process inventory |

**Table P - PR 3 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| P1 | Rename the parent directory without separating dependencies | UniEval would still import HHEM settings, failures and model helpers. | The same coupling under a less misleading label. | Fowler |
| P2 | Build a generic evaluator/supervisor framework | HHEM and UniEval have different worker recovery and scoring policies. | New abstraction, policy adapters and process regressions with no required capability gain. | Fowler |
| P3 | Keep workflow tests inside the evaluation package | Hides caller/report regressions among scorer tests and preserves misleading ownership. | Continued mixed gates and harder independent selection. | Test inventory |
| P4 | Copy evaluator fixtures and process helpers into the workflow | Creates two harnesses that can diverge from real process behavior. | Duplicate maintenance and weaker evidence. | Test inventory |

## Row #4 - Rename and isolate the summary generator and its caller

- **Scope:** The renamed API performs fresh text-to-summary requests with configurable prompts; its existing full-analysis CLI and report remain outside the API.
- **Tasks:**
  1. Rename the whole service directory to C11 and its package to `summary-generator`, regenerating the lock. Keep relative path depth unchanged. Then move the full-analysis caller, private contracts, event bus, measurements and report function using Table R; use separate structural and behavioral commits, without a temporary HTTP compatibility implementation.
  2. Declare the pure summary contract in Table Q. Make the private full-analysis model extend the service's summary fields rather than define those fields a second time.
  3. Extract the effective Yen workflow prompt using W1-W3. Put its summary instructions in the configured default and classifications in the full-analysis caller's prompt. Retain the request override under A13. Reuse the request builder, response-content reader and one native HTTP transport; do not model native llama-server request fields.
  4. Make the HTTP handler invoke the summary operation, not the old full pipeline. Preserve per-request operation identity and response carrier headers; do not copy private pipeline history into the response.
  5. Remove HTTP report writing, machine diagnostics and host-memory health data. Read the selected model and destination from committed configuration only. Configure the listener, bounded transport and body-free logging under S6-S9.
  6. Repair the already documented URL parser defect in the relocated extractor, with the real JSDOM instance and no script/resource execution. Do not claim successful URL acquisition merely because broken code moved.
  7. Add the experiment's private manifest/lock and declared check/test commands. Move extraction-only dependencies out of the service. Existing parser dependencies move with the caller; directly declaring its JSDOM peer adds no API runtime feature.
  8. Update the Yen workflow to use the new summary-only caller and report in R16. Prepare URL/fallback input outside HTTP, send a prompt override only when supplied and call the dated operation. Retain actual native token counts under Q2; remove the old `.data.token_metrics` reads. Do not create full-analysis or host fields from this response. Keep both existing workflow filenames.
  9. Separate diagnostic source settings for the API and full-analysis caller. Keep historical event readback, not a current producer falsely named as the other component.
  10. Replace the old mixed handler and loopback-test coupling using S12. Keep recorded native/source responses; do not add a test listener or a fake successful model implementation.
  11. Update CLI invocation, CI, docs, artifact names and report links together. Account for all HTTP consumers before cutover.
- **Files touched - service rename:** Every tracked file below `services/summarizer/` moves to the identical relative path under `services/summary-generator/`, except the splits in Table R. The baseline includes its manifest, lock, TypeScript config, entry points, source modules and test helpers.
- **Files touched - existing service files before that rename:**
  - `services/summarizer/package.json`
  - `services/summarizer/bun.lock`
  - `services/summarizer/tsconfig.json`
  - `services/summarizer/src/index.ts`
  - `services/summarizer/src/api/serve-http-api.ts`
  - `services/summarizer/src/config/load-env-config.ts`
  - `services/summarizer/src/config/load-model-runtime.ts`
  - `services/summarizer/src/declare-event-source.ts`
  - `services/summarizer/src/schemas/export-all-schemas.ts`
  - `services/summarizer/src/schemas/request-payload.schema.ts`
  - `services/summarizer/src/schemas/environment-variable.schema.ts`
  - `services/summarizer/src/services/model-request.service.ts`
  - `services/summarizer/src/services/query-llama.service.ts`
  - `services/summarizer/src/start-api-server.ts`
  - `services/summarizer/test/model-runtime.test.ts`
- **Files touched - new service and configuration files:**
  - `services/summary-generator/src/config/load-generator-config.ts`
  - `services/summary-generator/src/declare-event-source.ts` - retain and update the real producer declaration.
  - `services/summary-generator/src/api/api-paths.ts`
  - `services/summary-generator/src/schemas/summary-result.schema.ts`
  - `services/summary-generator/src/services/summarize-text.service.ts`
  - `services/summary-generator/src/services/request-completion.service.ts` - one bounded native HTTP transport shared by the API and caller; no new HTTP framework.
  - `services/summary-generator/test/summary-api.test.ts`
  - `services/summary-generator/test/summary-contract.test.ts`
  - `config/summary-generator/api.json`
  - `config/summary-generator/workflow.json`
  - `config/prompts/generate-summary.txt`
  - `config/prompts/request-json.txt`
  - `config/prompts/analyze-article.txt`
- **Files touched - move/split map:**

**Table Q - Pure summary HTTP contract**

| Id | Surface | Declared behavior |
| --- | --- | --- |
| Q1 | Generator operation in Table Z | Required nonblank `input_text`; optional nonblank `system_prompt` replaces the configured default. Check that text is nonblank without trimming the value sent to the model. Do not require callers to copy the default. Refuse removed `url`, `server_url`, `model_name`, conversation and session fields by name. These are this API's inputs, not a schema for the native llama request. |
| Q2 | Successful response | Keep `{success: true, data: ...}` with `headline`, `executive_summary` and `key_points`; add `prompt_sha256`, `prompt_source` (`default` or `override`) and `usage` beside `data`. Usage contains `prompt_tokens` and `completion_tokens`, each a nonnegative integer or `null` when the native response did not provide it. Never substitute zero for an absent count. The model produces the summary fields because this API requests them. Preserve nonempty text entries and the allowed empty key-point array. No classifications, source audit, prompts, raw replies or measurements enter `data`. |
| Q3 | Full-analysis CLI | Retain the old URL/direct-text fallback, full structured output, sentiment/stance fields, raw output, source audit, measurements, saved events and report through the moved caller. This is a different product, not an old HTTP compatibility mode. |
| Q4 | Health and diagnostics | Use the dated generator health operation in Table Z for process/configuration availability, not an invented model-readiness claim. Remove hardware diagnostics and health memory output. Native model readiness remains its own upstream endpoint. |
| Q5 | Failures and metadata | Return `{error: <safe message>, code: <safe code>}` with request-local trace carriers. Declare `INVALID_REQUEST` for HTTP 400, `REQUEST_TOO_LARGE` for HTTP 413 at either request-byte boundary, `REQUEST_BODY_TIMEOUT` for HTTP 408, and `GENERATE_SUMMARY_FAILED` for HTTP 500 on native transport, decoding or output failure. No raw bodies or exception strings enter errors. Stamp the changed native API contract/changelog; do not restamp moved full-analysis events. |
| Q6 | Fresh requests and native controls | Each request builds its own complete prompt and makes one generation call. Repeated calls may reuse the running model and native prefix cache, but never inherit earlier answers. Configured native JSON fields remain open under A11; summary output validation is a separate repository-owned boundary. |

**Table R - Full-analysis caller move map**

| Id | Existing full path | Destination or split |
| --- | --- | --- |
| R1 | `services/summarizer/src/execute-cli-pipeline.ts` | `.github/scripts/summary-generator-tests/run.ts` |
| R2 | `services/summarizer/src/pipeline/orchestrate-pipeline.service.ts` | `.github/scripts/summary-generator-tests/orchestrate-analysis.ts` |
| R3 | `services/summarizer/src/reporters/render-github-summary.reporter.ts` | `.github/scripts/summary-generator-tests/render-report.ts` |
| R4 | `services/summarizer/src/services/extract-content.service.ts` | `.github/scripts/summary-generator-tests/extract-content.ts` |
| R5 | `services/summarizer/src/services/collect-telemetry.service.ts` | `.github/scripts/summary-generator-tests/collect-measurements.ts` |
| R6 | `services/summarizer/src/services/dispatch-event.service.ts` | `.github/scripts/summary-generator-tests/publish-events.ts` |
| R7 | `services/summarizer/src/schemas/analysis-result.schema.ts` | `.github/scripts/summary-generator-tests/contracts/analysis-result.schema.ts`; import/extend the pure summary fields |
| R8 | `services/summarizer/src/schemas/system-telemetry.schema.ts` | `.github/scripts/summary-generator-tests/contracts/system-telemetry.schema.ts` |
| R9 | `services/summarizer/src/schemas/pipeline-event.schema.ts` | `.github/scripts/summary-generator-tests/contracts/pipeline-event.schema.ts` |
| R10 | `services/summarizer/src/schemas/request-payload.schema.ts` | `services/summary-generator/src/schemas/request-payload.schema.ts` for Q1; move the old full-analysis shape to `.github/scripts/summary-generator-tests/contracts/analysis-request.schema.ts` |
| R11 | `services/summarizer/src/services/query-llama.service.ts` | `services/summary-generator/src/services/query-llama.service.ts` for summary generation; move full-analysis handling to `.github/scripts/summary-generator-tests/query-analysis.ts`; share transport/helpers |
| R12 | `services/summarizer/test/pipeline-events.test.ts` | Split full-analysis/CLI cases into `.github/scripts/summary-generator-tests/test/analysis-events.test.ts`; pure HTTP cases belong in the new service test named above |
| R13 | `services/summarizer/test/pipeline-recordings.ts` | `.github/scripts/summary-generator-tests/test/pipeline-recordings.ts` |
| R14 | `services/summarizer/test/model-recordings.ts` | `services/summary-generator/test/model-recordings.ts`; remove dependence on moved application schemas and use the single helper from both suites |
| R15 | `services/summarizer/test/model-runtime.test.ts` | `services/summary-generator/test/model-runtime.test.ts`; move full-analysis override/input checks to `.github/scripts/summary-generator-tests/test/analysis-runtime.test.ts` |
| R16 | No existing file | `.github/scripts/summary-generator-tests/package.json`; `.github/scripts/summary-generator-tests/bun.lock`; `.github/scripts/summary-generator-tests/tsconfig.json`; `.github/scripts/summary-generator-tests/load-analysis-config.ts`; `.github/scripts/summary-generator-tests/prepare-api-input.ts`; `.github/scripts/summary-generator-tests/run-summary-api.ts`; `.github/scripts/summary-generator-tests/render-summary-report.ts`; `.github/scripts/summary-generator-tests/test/summary-workflow.test.ts` |
| R17 | `docs/reference/summarizer-api.md` | `docs/reference/summary-generator-api.md`; update inbound links and document the new request/result, prompt and listener ownership |
| R18 | `services/summarizer/src/config/load-env-config.ts`; `services/summarizer/src/schemas/environment-variable.schema.ts` | Move caller-only URL, fallback, analysis override, telemetry and report environment handling to `.github/scripts/summary-generator-tests/load-analysis-config.ts`. Retire the old mixed files after their consumers use the new loaders. The generator keeps only its actual config/runtime inputs; no inactive CLI prompt or port default remains inside the API. |

- **Files touched - callers, CI and docs:**
  - `.github/workflows/ci.yml`
  - `.github/workflows/ai-pipeline-tests.yml`
  - `.github/workflows/yen-ai-pipeline.yml`
  - `.github/scripts/ai-pipeline.ts`
  - `.github/scripts/read-pipeline-events.ts`
  - `.github/scripts/test/workflow-handoff.test.ts`
  - `.github/scripts/summary-generator-tests/declare-event-source.ts` - new, independent caller producer declaration.
  - `TODO/20261103-standardize-typescript-metadata-plan.md` - update moved current paths, not shipped outcomes.
  - `docs/reference/summarizer-api.md` - move R17.
  - `docs/reference/summary-generator-api.md`
  - `docs/reference/api-routing.md`
  - `docs/reference/workflow-pipeline-events.md`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/how-to/run-feed-ingest-plan-test.md`
- **Acceptance gates:**
  - Local: shared selector inspection; frozen Bun installs for changed manifests only; declared type checks and focused tests in the service and the new experiment package; existing workflow-handoff tests.
  - API integration: send standard in-memory requests through the real HTTP handler with the recorded model boundary, without opening test sockets. Require only the summary product, truthful health, request isolation and explicit refusal of removed inputs. Verify text longer than the old preparation cap is not silently shortened in the native request. Set a real temporary step-summary path and require that HTTP does not change it.
  - Prompt/config integration: exercise default, changed default and exact request override; bind `prompt_sha256` to the actual resolved text. Send two different independent requests and require no earlier answer in the second native body. Forward a supported native setting absent from the default config without changing any field-list schema. Check the configured listener and exact byte limits, including one byte above each limit.
  - Transport integration: recorded-boundary cases refuse redirects and stalled bodies, propagate request cancellation, and confirm body cancellation on refusal. The selected-model deadline covers complete response consumption and decoding, not only headers.
  - Producer integration: exercise the actual API and caller emitters against their own declared sources and retain historical event readback. Do not recreate the retired event-source registry.
  - Caller integration: direct text, failed-URL fallback, classifications, full saved-output validation and report rendering still use the real moved functions and named recordings. Keep extraction callbacks and operation links.
  - Summary-workflow integration: run the new caller with a response from the real fixture-backed summary handler. Its saved envelope/report retain the summary, prompt identity, trace and supplied native token counts. Missing counts and uncollected classification/machine readings are not zeroes or inferred scores.
  - Extractor integration: use the named readable-article fixture and the real parser. Require substantive title/text, only the main document request, no script effects, no extra resources and a closed window, as specified by the existing summarizer reference.
  - CI: add the new named suite to the existing native checks; retain the full service, experiment and saved-handoff coverage. No new browser matrix or live inference gate.
  - Report: compare a representative private CLI report and saved data before/after. Review only changed packaging/absence states; do not use incidental text or exact geometry as the correctness test.
- **Oracle:** The same real HTTP entry point yields only the declared summary product, while the moved CLI reads back the unchanged full-analysis recording and private report data. This does not establish quality of a newly generated summary or successful live source access.

**Table S - PR 4 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| S1 | Keep a pure summary API and a separate full-analysis caller. Do not silently delete existing classifications or hide them in a summary-only API. | Fowler's boundary recommendation; caller inventory |
| S2 | The pure summary schema owns its fields once. Full analysis extends it in the caller; request transport and final-content parsing are reused without a generic pipeline framework. | Contract and duplication boundary |
| S3 | Move private extraction/report dependencies with their beneficiary. Directly declare the existing parser's JSDOM peer for correct extraction; remove the obsolete DOM dependency only after its final caller moves. Record install/lock impact in the PR; no dependency is added to the published site. | Existing documented extraction defect |
| S4 | The older `.github/scripts/ai-pipeline.ts` experiment has its own `analytic_synthesis` shape. Do not convert it to the moved CLI's `executive_summary` shape as part of this cleanup. | Existing saved-handoff contract |
| S5 | Existing input shortening moves with the full-analysis caller. The pure HTTP summary operation submits the supplied text without that hidden word cap; a model/context refusal remains an explicit failure, not a shortened-input retry. | Input preparation moves outside the summary API under the chosen boundary |
| S6 | `config/summary-generator/api.json` owns `hostname`, `port`, `prompt_file`, `max_request_bytes`, `max_native_request_bytes`, `max_native_response_bytes`, `body_read_timeout_ms` and `logging`. Defaults: loopback `127.0.0.1`, port `9932`, prompt path `prompts/generate-summary.txt`; each byte limit `1048576`, meaning one MiB; body deadline `5000` milliseconds, meaning five seconds; logging `level: INFO` and `max_event_bytes: 4096`, meaning a four-KiB envelope cap. The byte/deadline/log values come from the existing evaluation guards. Model-request deadlines remain selected-model settings. Remove duplicated `PORT` settings and workflow URLs. | Listener/transport boundary; current guard values |
| S7 | Native generation remains at committed `model_server.base_url`, currently loopback port `8080`; the evaluator keeps port `3010` in K8; shared TypeScript hosting keeps port `8787` in `config/hono-server.json`. Retire the separate coverage listener on port `9933` in PR 5. These are different listeners, not alternative names for one API. | Actual listener inventory |
| S8 | Yen already uses the digest's model-server action and Python request-declaration exporter. Keep model `server`, `sampling` and template dictionaries pass-through; do not create a second flag list or native request schema in TypeScript. Guard only fields this application consumes and the controls that belong to its own operation. | Shared production model boundary; A11 |
| S9 | Native verbosity/metrics belong to the selected model's `server` block. API logs contain operation identities, safe codes, elapsed time and prompt digests, not source bodies, prompts, raw replies, secrets or raw exception text. The caller owns private captures and reports under the existing capture settings; the API does not write those files. | Existing production logging/capture split |
| S10 | The private caller package is `summary-generator-tests`. Its `config/summary-generator/workflow.json` owns `max_input_words: 6000`, meaning the existing preparation cap, and S6's native request/response byte-limit keys and defaults, independent of listener settings. Full-analysis defaults are `base_prompt_file: prompts/request-json.txt` and `analysis_prompt_file: prompts/analyze-article.txt`; keep its base `PROMPT` override and W3 composition. Move current capture/report controls with their readers. Remove the Yen dispatch default; blank workflow input omits the API override. R16 owns its summary-only report; the CLI retains full analysis. No extra model call is silently added. | Product, prompt and fresh-request boundaries |
| S11 | The API's `src/declare-event-source.ts` declares `SUMMARY_GENERATOR_EVENT_SOURCE = "/services/summary-generator"`; the caller's own module declares `SUMMARY_GENERATOR_TESTS_EVENT_SOURCE = "/workflows/summary-generator-tests"`. Bind each actual emitter to its declaration. These are logical producer URI references, not filesystem paths. Preserve historical readback; do not restore a registry or configuration loader. | Current per-producer declarations; G3 and G6 |
| S12 | Use a standard `Request`/`Response` handler, the existing Bun adapter, native `fetch` with `redirect: "error"` and one bounded decoder. Keep the selected-model deadline active through complete body consumption/decoding; propagate caller cancellation and cancel the body on refusal. Shared transport stays Node/tsx-compatible; only the adapter uses Bun APIs. Recorded handler/stream tests need no network. Direct Bun development types benefit server checking, without new runtime libraries or site bytes. | Existing transport protections and runtimes |

**Table T - PR 4 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T1 | Only move the report call out of the HTTP handler | URL acquisition, classification and host sampling would still run inside a summary request. | Retains the main responsibility leak and its heavy response/dependency surface. | Fowler; actual HTTP pipeline |
| T2 | Drop the full-analysis CLI output and classifications | Removes an existing experiment capability not required by summary API separation. | Lost saved-event fields, report content and a different model task. A separate content decision would be required. | Scope boundary |
| T3 | Move the URL extractor unchanged and call the move complete | Its documented DOM/adapter mismatch remains broken. | Continued failure of URL-only input and no successful extraction evidence. | Existing summarizer reference |
| T4 | Permit prompt edits only through a fixed file | Removes existing request-by-request prompt experiments. | A config edit/restart for every experiment and loss of the workflow's prompt override. | Prompt control contract |
| T5 | Rebuild llama-server's JSON field schema locally | Makes a new native option a source/schema/test-maintenance task. | A second protocol definition that drifts with the external runtime. | Native protocol boundary |
| T6 | Keep the old full-analysis Yen report from a summary-only response | Classification and machine fields cannot be obtained from that response. | Separate analysis/host calls and receipts, or a return to the mixed API. Preserve the full-analysis CLI instead of inventing report fields. | Actual response/report boundary; B11 |

## Row #5 - Consolidate source coverage under the summary evaluator

- **Scope:** Move the older coverage calculation into its own evaluation child and worker; retire the separate listener, duplicate publication and machine sampling.
- **Tasks:**
  1. Make the current model-call boundary explicit without changing its calculation. Capture actual dimension-call inputs/results and final metrics for bounded named inputs before moving the algorithm. Record resource revisions and effective settings; a fabricated final-response fixture cannot prove calculation parity.
  2. Declare G7's transient request/response and worker messages in the new child's contracts. Declare the persisted recording once under backend contracts; do not create a second backend copy of the HTTP models.
  3. Extract preparation, retrieval, loading and calculation using U6-U9 in a structural commit. Then add U12's invalid-model-output validation in a separate behavioral commit with its failure cases. Keep defaults and valid recorded calculations unchanged; the native UniEval method remains independent.
  4. Add an explicitly selected `coverage` route component with one bounded worker and queue, using shared transport and parent/process ownership. Keep all-or-error coverage results; never fill failed model work with a successful score. Disabled coverage constructs no model. Do not silently add another model to the normal two-scorer run.
  5. Prepare pinned code, model and tokenizer resources before serving. Declare real dependencies in the existing evaluator environment and remove the import shim, unpinned workflow installs and `/tmp` checkout. Prove the pinned legacy backend works before deleting its entry point; use A6 if the environment requires a different model or dependency family.
  6. Update the caller/readers before switching the workflow writer. Send only the declared scoring input; keep URL, title, runner/shard identity, saved event and report metadata in the caller. Use the dated coverage and health operations in Table Z.
  7. Replace standalone startup with `summary_evaluator` running the coverage component. Preserve the workflow's existing order: generation finishes and native llama stops before coverage starts. Remove the old script, port, camelCase HTTP aliases, duplicate event writer, hardware sampler, raw traceback responses and event-file upload.
  8. Keep historical foreign-response/measurement readback. New reports show uncollected machine readings as unavailable, not zero; their caller already writes the completion event.
  9. Document method differences, resource ownership, response changes, the removed measurements and the extraction's technical reason in the living references.
- **Files touched:**
  - `.github/scripts/serve-evaluator.py` - extract then delete.
  - `.github/scripts/prepare-evaluation-request.ts`
  - `.github/scripts/read-pipeline-events.ts`
  - `.github/scripts/ai-pipeline.ts`
  - `.github/scripts/test/workflow-handoff.test.ts`
  - `.github/workflows/ai-pipeline-tests.yml`
  - `.github/workflows/ci.yml`
  - `services/summary_evaluator/pyproject.toml`
  - `services/summary_evaluator/uv.lock`
  - `services/summary_evaluator/src/summary_evaluator/__main__.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/api_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/serve_api.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/guard_local_requests.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/api_health.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/api_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/contracts/server_event.py`
  - `services/summary_evaluator/src/summary_evaluator/shared/contracts/api_paths.py`
  - `services/summary_evaluator/src/summary_evaluator/shared/contracts/server_contract.py`
  - `services/summary_evaluator/src/summary_evaluator/shared/contracts/error_policy.py`
  - `services/summary_evaluator/src/summary_evaluator/serve_http/refuse_request.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/__init__.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/contracts/__init__.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/contracts/evaluate_request.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/contracts/evaluation_result.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/contracts/service_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/contracts/worker_message.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/prepare_text.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/retrieve_evidence.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/load_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/load_model.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/prepare_resources.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/score_coverage.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/fail_evaluation.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/control_evaluation.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/dispatch_evaluation.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/run_worker.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/maintain_worker.py`
  - `services/summary_evaluator/src/summary_evaluator/source_coverage/coverage_router.py`
  - `services/summary_evaluator/scripts/capture-coverage-recordings.py`
  - `services/summary_evaluator/scripts/prepare-coverage-resources.py`
  - `services/summary_evaluator/tests/test_coverage_contracts.py`
  - `services/summary_evaluator/tests/test_coverage_scoring.py`
  - `services/summary_evaluator/tests/test_coverage_api.py`
  - `services/summary_evaluator/tests/test_coverage_worker.py`
  - `services/summary_evaluator/tests/test_api.py`
  - `services/summary_evaluator/tests/test_server_lifecycle.py`
  - `services/summary_evaluator/tests/test_server_events.py`
  - `backend/idhazh/contracts/coverage_model_recording.py` - new, persisted real model-call recording and provenance, not another HTTP model.
  - `backend/tests/test_coverage_model_recording.py`
  - `tests/fixtures/summary-evaluation/coverage-recording-inputs.json`
  - `tests/fixtures/summary-evaluation/coverage-model-recording.json`
  - `config/summary-evals/api.json`
  - `config/summary-evals/unieval-evaluator/coverage.json`
  - `docs/reference/workflow-pipeline-events.md`
  - `docs/reference/unieval-api.md`
  - `docs/reference/summary-evaluator-api.md`
  - `docs/reference/api-routing.md`
  - `docs/architecture/evaluation/summary-evaluator.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:**
  - Local: inspect the shared selector; frozen-sync the changed evaluator manifest and run its declared lint/type checks, focused coverage tests and existing evaluator/application cases. Run the new backend recording-contract case and `bun test ./.github/scripts/test/workflow-handoff.test.ts`.
  - Calculation parity: replay real recorded model-call results through the actual text preparation, retrieval and reduction. Require exact final metrics, three-decimal score rounding, one-decimal coverage rounding, sentence/chunk links and evidence text for unchanged settings. The saved final-response fixture alone is not this oracle.
  - Contract: bind Python output to the real TypeScript reader using `tests/fixtures/typescript-metadata/evaluator-response.json`, without rewriting it. Verify the new body shape and removed live aliases separately from historical readback.
  - Application/process integration: exercise the real route with the recording-driven model boundary, real queue/worker ownership and configured byte limits. Check disabled-worker absence, overload, not-ready, timeout, cancellation, parent exit, safe failures and cleanup. An enabled source-coverage worker failing must not stop or borrow a completed native scorer result.
  - Invalid-model boundary: require the returned batch cardinality and requested dimension values, and reject nonfinite or missing scores before reduction. Missing results/keys produce `INVALID_MODEL_OUTPUT`, not zero. Genuine zero scores remain valid; exercise U12's status/body policy through the actual handler and caller.
  - Report: render metrics-only and historical measured responses through the actual caller/report path. Keep scores and coverage; label new machine readings unavailable, not zero. Failed evaluation remains a failed target.
  - Linux execution gate: complete model-free evaluator/workflow suites, including new coverage cases. CI runs its actual backend/native/saved-handoff suites. No test downloads models or code; resource preparation/recording is a separate utility action.
  - Observation, not a merge gate: on the next intended manual experiment, inspect the real response/report and owned-process cleanup. No new `eval-events.jsonl` or fabricated server readings may appear. A missing score is a defect, not permission to substitute native UniEval.
- **Oracle:** Recorded model calls replay through the relocated real algorithm to exactly the captured metrics and evidence, and that response crosses the real HTTP/TypeScript/report boundary. This does not establish model quality, fresh-run numeric reproducibility or a replacement for removed machine measurements.

**Table U - PR 5 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| U1 | Preserve the source-coverage calculation, not the old HTTP aliases or deployment. Native relevance needs an independent reference; the older workflow does not provide one and reports different evidence. | Direct legacy/native caller comparison; Fowler |
| U2 | The new response uses G7. The existing foreign-response reader already accepts that form; prepare report absence handling before removing the server writer. | Existing response reader; Table G |
| U3 | The child declares the exact existing metric vocabulary: `overall_consistency`, `coherence`, `fluency`, `document_chunks_total`, `document_chunks_covered`, `chunk_coverage_percent`, `sentence_breakdown`, and optional `uncovered_sections`. Retain nested fields and meanings; bind their field sets to the existing reader without duplicating models in backend contracts. | Existing writer and read validators |
| U4 | New reports give up the older API's machine readings, not its scores. Calling the dedicated host APIs is a separate measurement capability priced in B5, not a score-shaped or zero-valued fallback. | API responsibility boundary |
| U5 | Delete the script after callers use the new application component. Keep one evaluator distribution/environment and no old live listener. | Fowler; explicit consolidation boundary |
| U6 | Move `split_sentences`, `chunk_document` and `extract_macro_skeleton` to `source_coverage/prepare_text.py`; preserve their text rules and effective defaults. Declare existing preparation limits in the coverage config rather than introduce new truncation. | Existing algorithm |
| U7 | Move `EvidenceRetriever` to `source_coverage/retrieve_evidence.py`. Install its actual dependencies and prepare named resources. Retained tokenizer/retrieval fallbacks emit safe warnings. This allowance does not include zero substitution for absent or malformed model results; U12 governs that boundary. | Existing algorithm; explicit degraded behavior |
| U8 | Move `compute_unieval_sync` to `source_coverage/score_coverage.py` with an explicit model-call boundary. Preserve deduplication, retrieval order, thresholds, valid reductions, rounding and evidence. Validate native batches before reduction under U12. Hardware sampling, report metadata and file output stay outside this function. | Recorded valid calculation and invalid-output boundary |
| U9 | Move `get_evaluator`/`convert_to_json` loading to `source_coverage/load_model.py` in the owned child process. Pin the exact code/model/tokenizer revisions used for the retained baseline; do not assume the native scorer's pin proves legacy compatibility. Preparation resolves named assets before HTTP starts. | Existing upstream backend and recording provenance |
| U10 | Use `coverage` for route selection, application health and diagnostics; its Python child is `source_coverage`. Select it explicitly. Its single worker adds resident model memory when all methods are enabled; it is not free model sharing. Use bounded admission and fail-closed lifecycle, with no generation or native-UniEval fallback. | Process isolation and model ownership |
| U11 | Only the new persisted recording family lives in `backend/idhazh/contracts/`. Its version, UTC capture instant, model/code identities, effective settings, bounded inputs, ordered actual model-call inputs/results and final expected metrics make replay checkable. Transient request/result/worker contracts stay with the child. | Persisted contract authority; G7 |
| U12 | Reuse the fixed error policy and safe renderer: `QUEUE_FULL` -> 429; queue timeout or unavailable service -> 503; `EVALUATION_TIMEOUT` -> 504; malformed model output or worker failure -> 500. Keep existing request-refusal mappings. Require batch cardinality, all requested dimensions and finite scores before reduction. Replace missing-result/key zero substitution with `INVALID_MODEL_OUTPUT`; valid zero stays valid. No partial-success fallback. | Existing safe policies; explicit behavioral correction |

**Table V - PR 5 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| V1 | Point the old client at native UniEval and rename returned fields | The methods, reference requirement and coverage/explanation meanings differ. | A new reference input and an explicit redesign or removal of legacy report evidence. | Native and legacy contracts |
| V2 | Keep machine sampling because it is already inside the scoring handler | Retains the identified second responsibility. | Continued OS-specific collection, unrelated request cost and mixed report semantics. | Direct handler trace |
| V3 | Copy the server's private event writer into another module | The caller already saves the evaluation-completed event. | Duplicate records and another artifact lifecycle without a required capability gain. | Existing caller event writer |
| V4 | Retain a standalone coverage server because its algorithm differs | Separate algorithms need separate children, not an unexplained extra package/listener. | Another startup path, port, resource installation and lifecycle to maintain. | Consolidated evaluator boundary |

## Row #6 - Centralize production and evaluation prompt files

- **Scope:** Move the remaining named task templates into configurable prompt files without changing production control flow, scorer wording or rendered prompt identities.
- **Tasks:**
  1. Complete Table W's moves after PR 4 has established the generator and caller defaults. Do not copy one task's output instructions into a different task merely because both produce summaries.
  2. Add the production `prompt_files` block under X1. Validate paths when configuration loads; read task text only when that task needs it. Replace source-relative prompt directories and update every renderer, digest/stamp reader and utility named below.
  3. Replace native UniEval's inline question templates with declared file paths. Resolve them into its existing effective prompt model before placeholder validation, worker handoff and identity calculation. Keep positive/negative answer settings and all scoring controls unchanged.
  4. Move the comparison workflow's generation instruction out of its shared workflow JSON. Preserve its different output contract, native log policy and independently saved generation/evaluation flow.
  5. Preserve each reader's actual newline, substitution, role placement, sanitizer and digest behavior. Remove old prompt copies only after all named readers use the new paths.
  6. Keep candidate configuration isolated: relative prompt paths resolve against the selected `CONFIG_ROOT`, not the original checkout's config. The existing candidate action already copies `config/`; do not add another prompt copy or a repository scan.
  7. Update canonical prompt/config references and current path links. Historical benchmark tables retain the filenames and measurements that actually ran; add a short current-location pointer rather than rewrite their provenance.
- **Files touched - production declarations, loaders and callers:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/knobs/prompts.py` - new, only the configured production task paths.
  - `backend/idhazh/load_prompt_text.py` - new, one named configured text file, not a registry or directory walker.
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/summarize.py`
  - `backend/idhazh/similarity/prompt.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/corpus.py`
  - `backend/utilities/prompt_loop.py`
  - `backend/utilities/data_wrangler.py`
  - `backend/utilities/reference_set.py`
  - `backend/utilities/measure_two_calls.py`
  - `backend/utilities/measure_judge_call.py`
- **Files touched - exact production moves:**
  - `backend/idhazh/prompts/label_article_elements.txt`
  - `backend/idhazh/prompts/summarize_and_plan_visual.txt`
  - `backend/idhazh/prompts/plan_visual.txt`
  - `backend/idhazh/prompts/write_about_the_item.txt`
  - `backend/idhazh/prompts/summarize.txt`
  - `backend/idhazh/prompts/judge_same_story.txt`
  - `config/prompts/generate-labels.txt`
  - `config/prompts/write-digest-summary.txt`
  - `config/prompts/plan-visual.txt`
  - `config/prompts/continue-summary.txt`
  - `config/prompts/summarize-article.txt`
  - `config/prompts/compare-articles.txt`
- **Files touched - evaluation templates and readers:**
  - `config/summary-evals/workflow.json`
  - `config/summary-evals/unieval-evaluator/settings.json`
  - `config/prompts/generate-evaluation-summary.txt`
  - `config/prompts/evaluate-fluency.txt`
  - `config/prompts/evaluate-coherence.txt`
  - `config/prompts/evaluate-consistency.txt`
  - `config/prompts/evaluate-relevance.txt`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/settings.py`
  - `.github/scripts/summary-eval-tests/summary_eval_pipeline/generation.py`
  - `.github/scripts/summary-eval-tests/summary_eval_tests/test_generation_handoff.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/load_unieval_settings.py`
  - `services/summary_evaluator/src/summary_evaluator/unieval/contracts/unieval_settings.py`
  - `services/summary_evaluator/tests/test_unieval_contracts.py`
  - `services/summary_evaluator/tests/test_unieval_scoring.py`
- **Files touched - focused tests and documentation:**
  - `backend/tests/test_prompt_files.py` - new, configured task text, isolation and refusal cases.
  - `backend/tests/test_candidate_pointer.py`
  - `backend/tests/test_tag.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_visual_planner.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/concepts/classification.md`
  - `docs/concepts/evaluation.md`
  - `docs/reference/unieval-api.md`
  - `docs/reference/summary-evaluation-workflow.md`
  - `docs/reference/summary-generator-api.md`
  - `docs/reference/repository-layout.md`
  - `docs/reference/benchmarks/instructions-in-front.md`
  - `docs/reference/benchmarks/two-call-re-read.md`
- **Acceptance gates:**
  - Local: inspect the shared selector; run backend lint/type checks and selected prompt/classify/similarity/candidate cases, the evaluator's native-UniEval prompt cases and the workflow generation-handoff case.
  - Render parity: compare the full rendered text and existing prompt/schema identities before/after for each moved existing template. Include production labels plus continued summary/visual output, standalone summary, both article-comparison orders and every native UniEval dimension. A path-only move permits no text/digest difference.
  - Config isolation: use two generated config roots with different named prompt files. Require each real consumer to use its selected root; switching roots must not reuse a globally cached template. Missing files, invalid UTF-8, undeclared substitutions and invalid paths fail by name.
  - Model/config boundary: the selected-model description command still works without unrelated task prompt files. A scratch candidate config changes only the already permitted pointer/state settings; named prompt files and controls remain intact.
  - Scope: the generator still honors the exact request override; its fresh-request tests remain in PR 4. The production digest still carries the validated label answer into its next call. Do not substitute one behavior for the other.
  - Linux execution gate: complete model-free evaluator/workflow suites, including moved prompt cases. CI retains actual backend and generator/native suites. Read only named files or generated roots; no prompt-directory inventory test.
- **Oracle:** For unchanged task instructions, the real renderers produce exactly the same model input and identity under the moved files, while a changed configured file changes only its intended task. This does not compare the quality of different instructions or authorize a production-flow change.

**Table W - Prompt source, destination and owning reader**

| Id | Existing source | Canonical file or retained source | Reader and preservation rule |
| --- | --- | --- | --- |
| W1 | Yen workflow's default plus the summary part of `buildInferencePrompt` | `config/prompts/generate-summary.txt`; established in PR 4 | Generator default. Preserve the existing headline, executive-summary and key-point instructions; remove classification instructions because they are a different task. Do not substitute a digest prompt with different output fields. |
| W2 | Repeated short default in the Yen dispatch input and CLI environment schema | `config/prompts/request-json.txt`; established in PR 4 | Relocated full-analysis caller's default base instructions. Its existing `PROMPT` override remains a base-instruction override. Yen's generator override is instead the complete API prompt under A13. |
| W3 | Existing appended analysis JSON instructions and classification definitions in `buildInferencePrompt` | `config/prompts/analyze-article.txt`; established in PR 4 | Relocated caller reads this instruction suffix and combines it with W2 or its existing base override using the current separator. Preserve the full rendered analysis prompt, output fields and definitions. The summary API never appends this file. |
| W4 | `backend/idhazh/prompts/label_article_elements.txt` | `config/prompts/generate-labels.txt` | Production digest's first model call; labels article elements. Preserve its template and its place before article data. |
| W5 | `backend/idhazh/prompts/summarize_and_plan_visual.txt` | `config/prompts/write-digest-summary.txt` | Production summary half of the shared system instructions. Preserve substitutions and the separate visual half; do not turn it into the generator API's output contract. |
| W6 | `backend/idhazh/prompts/plan_visual.txt` | `config/prompts/plan-visual.txt` | Production visual half. Preserve conditional composition and grammar ownership. |
| W7 | `backend/idhazh/prompts/write_about_the_item.txt` | `config/prompts/continue-summary.txt` | Production's short continuation after the label answer. Preserve its target-word substitutions and continued-call behavior. |
| W8 | `backend/idhazh/prompts/summarize.txt` | `config/prompts/summarize-article.txt` | Standalone production summary renderer and its prompt-loop/reference/corpus utilities. Preserve their current product and substitutions. |
| W9 | `backend/idhazh/prompts/judge_same_story.txt` | `config/prompts/compare-articles.txt` | Article-comparison judge's system template. Keep its existing safe user-block assembly, labels, repeated question, grammar and full rendered-text digest; the file move does not rewrite those controls. |
| W10 | `generation_instruction` in the old workflow config, then K13 | `config/prompts/generate-evaluation-summary.txt` | Comparison workflow's default instruction. Its `title`/`summary` answer shape is not the generator API's product; preserve it. |
| W11 | UniEval `prompts.fluency` | `config/prompts/evaluate-fluency.txt` | Native UniEval's own model receives the unchanged question with `{summary}`. No llama-server call. |
| W12 | UniEval `prompts.coherence` | `config/prompts/evaluate-coherence.txt` | Preserve `{summary}`/`{source}` and exact rendered whitespace. |
| W13 | UniEval `prompts.consistency` | `config/prompts/evaluate-consistency.txt` | Preserve `{summary}`/`{source}`, source-window modes and exact rendered whitespace. |
| W14 | UniEval `prompts.relevance` | `config/prompts/evaluate-relevance.txt` | Preserve `{summary}`/`{reference}`. The independently supplied reference remains required. |
| W15 | Coverage backend's pinned upstream question construction | Pinned backend code, not a new local copy | Preserve the upstream method under U9. Do not borrow the native scorer's templates or claim these questions are llama requests. |

**Table X - PR 6 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| X1 | Production `config/idhazh.json.prompt_files` names W4-W9 using `generate_labels`, `write_digest_summary`, `plan_visual`, `continue_summary`, `summarize_article` and `compare_articles`. Paths are relative to the selected config root, such as `prompts/generate-labels.txt`, not absolute or prefixed with the checkout's `config/`. Only committed configuration selects them. | Config and prompt ownership |
| X2 | Prompt paths are relative POSIX paths under `prompts/` in the selected config root. Refuse absolute paths, URLs, backslashes and parent traversal. Validate declarations without eagerly reading all task text. A narrow loader reads only the requested file and hands its unchanged text to the consumer. Native startup/model description must not acquire unrelated prompt-file dependencies. | Actual model-runtime caller; fixed-size reads |
| X3 | Native UniEval's authored settings use `prompt_files` for W11-W14. Keep its existing answer-token settings in JSON; resolve the files into the existing effective prompt values before validation, scoring and hashing. Do not hash a path as if it were changed model behavior. | Existing effective UniEval prompt contract |
| X4 | Mechanically extract the old inline UniEval strings. Do not add a final newline absent from those strings, trim other whitespace, or normalize all task templates through a new policy. The real rendered-text/identity check decides preservation. | Recorded score provenance |
| X5 | The workflow replaces inline `generation_instruction` with `generation_prompt_file`. Retain its nonduplicate lifecycle, control/response bounds and body-free logging settings in K13. The old root filename disappears; orchestration configuration does not. | Existing workflow reader; O8 |
| X6 | PR 4 owns the generator/caller templates W1-W3. PR 6 moves the remaining existing templates only; it does not merge their products or remove either kind of override. | Exact prompt/caller split |
| X7 | Record the new locations and configuration reason on the existing prompt/config reference pages. Keep historical benchmark identities as evidence and link them to the new location. | Documentation and provenance boundaries |

**Table Y - PR 6 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Y1 | One summary prompt for every caller | These callers request different fields and use different control flow. | Redesign each consumer/output contract and the digest's carried label context; a shared filename alone cannot provide compatibility. | Actual rendered products |
| Y2 | Keep a canonical file plus embedded default text | Editing the file would leave another active default behind. | Continued drift between API, CLI and workflow behavior. | One active default per task |
| Y3 | Build a generic prompt registry and scan its directory | All required readers already know their task. | Another configuration/index lifecycle and reads that grow with repository contents. | Named-task and fixed-size-read boundary |

## Row #7 - Standardize host and shared TypeScript routes

- **Scope:** Give the host operations and shared application's health operation dated verb-noun paths while retaining native measurements, payloads and owned-child readiness.
- **Tasks:**
  1. Apply Table Z's host/shared entries at the existing exported route constants. Keep their symbols usable by the real clients; do not create another wrapper or route registry.
  2. Change shared health through its existing constant. Preserve exact nonce, PID, configured port, group, enablement, module controls, uncached response and selected native identity checks.
  3. Update native/shared route tests and direct URL examples. Replace the planner's negative old-host-health check with the current host path; do not accidentally mount host operations on the standalone planner.
  4. Verify the comparison workflow's real machine bridge still uses the exported native paths. Keep sampling periods, profile handles, counters, failure/cleanup outcomes and private evidence unchanged.
  5. Remove old route matches, not redirect them. Update the canonical references and routing page; preserve native llama readiness as an external exception.
- **Files touched - authorities and named consumers:**
  - `services/host-fingerprints/src/api/server.ts`
  - `services/host-probes/src/api/server.ts`
  - `services/serve-pipeline-apis/src/api-startup.ts`
  - `services/serve-pipeline-apis/src/create-api-app.ts`
  - `services/serve-pipeline-apis/src/read-api-readiness.ts`
  - `services/host-fingerprints/test/fingerprint.test.ts`
  - `services/host-probes/test/probe.test.ts`
  - `services/feed-ingest-plan/test/serve-feed-apis.test.ts`
  - `services/feed-ingest-plan/test/retain-api-profiles.test.ts`
  - `services/host-probes/test/serve-machine-apis.test.ts`
  - `services/serve-pipeline-apis/test/api-routing.test.ts` - new, the bounded host/shared export and dispatch contract.
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `.github/scripts/summary-eval-tests/machine-task.ts` - verify imported constants and preserve the bridge contract; no replacement client.
  - `docs/reference/host-metrics.md`
  - `docs/reference/host-probe-api.md`
  - `docs/reference/host-cache-probes.md`
  - `docs/reference/serve-pipeline-apis.md`
  - `docs/reference/api-routing.md`
  - `docs/architecture/sources/feed-operator-api.md`
- **Acceptance gates:**
  - Local: inspect the shared selector; run checks in host fingerprints, host probes and shared hosting. Include the current feed-serving, retained-profile and machine-serving tests with focused dispatch/routing cases; retain the record.
  - Native/shared dispatch: call the actual handlers with standard in-memory requests and bounded real fixtures. New paths produce unchanged native payloads; old paths return HTTP 404 and wrong methods retain their proper refusal.
  - Readiness/process integration: retain the existing real owned-child checks for the planner composition. Require the new shared health path to identify the actual child and unchanged native module controls; do not weaken identity checks to a successful socket or any HTTP 200.
  - Machine caller: exercise the existing bridge with real recorded measurements and lifecycle controls. Changed URLs must not change PID binding, profile ownership, periods, counter availability or saved host evidence.
  - CI: existing host, shared-server and planner/native suites. The changed Python workflow bridge remains part of A10's Linux execution gate. No new test network beyond the existing planner loopback boundary, browser matrix or fresh hardware benchmark.
- **Oracle:** Each changed native path yields the same fixture-backed payload through its actual handler and shared composition, while readiness still rejects the wrong owned child. This does not establish live hardware performance or alter any measurement's meaning.

**Table Z - Complete first-party HTTP route cutover**

| Id | API or route-map key | Method | Current path | New path or removal | Owning PR |
| --- | --- | --- | --- | --- | --- |
| Z1 | HHEM evaluation | POST | `/api/2026-11-02/summary-eval-hhem` | `/api/2026-11-05/evaluate-summary-hhem` | 2 |
| Z2 | HHEM health | GET | `/api/2026-11-02/health` | `/api/2026-11-05/get-hhem-health` | 2 |
| Z3 | Native UniEval evaluation | POST | `/api/2026-11-02/summary-eval-unieval` | `/api/2026-11-05/evaluate-summary-unieval` | 2 |
| Z4 | Native UniEval health | GET | `/api/2026-11-02/summary-eval-unieval/health` | `/api/2026-11-05/get-unieval-health` | 2 |
| Z5 | Combined evaluator health | GET | `/health` on the Python application | `/api/2026-11-05/get-summary-evaluator-health` | 2 |
| Z6 | Evaluator OpenAPI JSON | GET | `/api/2026-11-02/openapi.json` | `/api/2026-11-05/get-summary-evaluator-schema` | 2 |
| Z7 | Source-coverage evaluation | POST | `/v1/evaluate` on the old coverage listener | `/api/2026-11-05/evaluate-summary-coverage` | 5 |
| Z8 | Source-coverage health | GET | `/health` on the old coverage listener | `/api/2026-11-05/get-summary-coverage-health` in the evaluation application | 5 |
| Z9 | Summary generation | POST | `/api/summarize` | `/api/2026-11-05/generate-summary` | 4 |
| Z10 | Generator health | GET | `/health` on the generator listener | `/api/2026-11-05/get-summary-generator-health` | 4 |
| Z11 | Generator machine diagnostics | GET | `/api/diagnostics` | Removed, not redirected. Call a dedicated host operation only when the caller needs its measurements. | 4 |
| Z12 | Host fingerprint | POST | `/api/2026-10-20/fingerprint` | `/api/2026-11-05/capture-host-fingerprint` | 7 |
| Z13 | Host fingerprint health | GET | `/api/2026-10-20/health` | `/api/2026-11-05/get-host-fingerprint-health` | 7 |
| Z14 | Host sample | GET | `/api/2026-10-20/sample` | `/api/2026-11-05/sample-host` | 7 |
| Z15 | Start task profile | POST | `/api/2026-10-24/start-task-profile` | `/api/2026-11-05/start-task-profile` | 7 |
| Z16 | Stop task profile | POST | `/api/2026-10-24/stop-task-profile` | `/api/2026-11-05/stop-task-profile` | 7 |
| Z17 | Cache measurement | POST | `/api/2026-10-24/cache/latency` | `/api/2026-11-05/measure-cache-latency` | 7 |
| Z18 | Shared TypeScript health | GET | `/health` on the shared listener | `/api/2026-11-05/get-api-health` | 7 |
| Z19 | Planner `health` | GET | `/api/2026-11-05/health` on the planner module | `/api/2026-11-05/get-feed-planner-health` | 8 |
| Z20 | Planner `plan` | POST | `/api/2026-11-05/plan` | `/api/2026-11-05/plan-feed-ingestion` | 8 |
| Z21 | Planner `fetch` | POST | `/api/2026-11-05/fetch` | `/api/2026-11-05/fetch-document` | 8 |
| Z22 | Planner `parse` | POST | `/api/2026-11-05/parse` | `/api/2026-11-05/parse-document` | 8 |
| Z23 | Planner `startCollection` | POST | `/api/2026-11-05/collections` | `/api/2026-11-05/start-feed-collection` | 8 |
| Z24 | Planner `checkCollection` | POST | `/api/2026-11-05/collections/exists` | `/api/2026-11-05/check-feed-collection` | 8 |
| Z25 | Planner `completeCollection` | POST | `/api/2026-11-05/collections/complete` | `/api/2026-11-05/complete-feed-collection` | 8 |
| Z26 | Planner `cancelCollection` | POST | `/api/2026-11-05/collections/cancel` | `/api/2026-11-05/cancel-feed-collection` | 8 |
| Z27 | Planner `finalizeCollection` | POST | `/api/2026-11-05/collections/finalize` | `/api/2026-11-05/finalize-feed-collection` | 8 |
| Z28 | Planner `releaseCollection` | POST | `/api/2026-11-05/collections/release` | `/api/2026-11-05/release-feed-collection` | 8 |
| Z29 | Planner `updateFeedHealth` | POST | `/api/2026-11-05/feed-health-state` | `/api/2026-11-05/update-feed-health` | 8 |
| Z30 | Planner `selectArticles` | POST | `/api/2026-11-05/select-articles` | Unchanged; already a dated verb-noun operation. | 8, verify |
| Z31 | Planner `partitionArticles` | POST | `/api/2026-11-05/partition-articles` | Unchanged; already a dated verb-noun operation. | 8, verify |
| Z32 | Planner `persistSelectedArticles` | POST | `/api/2026-11-05/persist-selected-articles` | Unchanged; already a dated verb-noun operation. | 8, verify |
| Z33 | Delivery `health` | GET | `/api/2026-11-05/health` on the delivery module | `/api/2026-11-05/get-data-delivery-health` | 8 |
| Z34 | Delivery `persistData` | POST | `/api/2026-11-05/safe-persist-data` | `/api/2026-11-05/persist-data` | 8 |

**Table AA - PR 7 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| AA1 | Shared hosting is permitted: each mounted module still performs its own job. Keep explicit planning, machine and delivery groups; no request selects another module or runtime destination. | Existing composition contract |
| AA2 | Keep exported native route constants as authority for host callers. Changing their values is sufficient for an already correct import; do not edit a client merely to create a diff. Direct literal consumers and tests must change. | Actual native bridge imports |
| AA3 | URLs change; hardware/event schema dates, measurements, lifecycle fields and captured identity meanings do not. Old recordings remain readable. | HTTP versus data identity boundary |
| AA4 | Distinguish shared process health from each native module's readiness. Keep the shared response and the additional native checks rather than replace them with one untyped success flag. | Actual owned-child readiness predicate |

**Table AB - PR 7 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AB1 | Keep unversioned shared health as a permanent convenience | It is first-party behavior and defeats the declared convention. | Another live route and compatibility path with no external dependency requiring it. | Routing convention |
| AB2 | Put every native API behind a new generic HTTP client | Existing callers already import the native path constants and preserve native responses. | Another transport/identity layer without a required capability gain. | Existing native composition |

## Row #8 - Standardize planner and delivery routes

- **Scope:** Cut over planner, collection and data-delivery paths without changing planning calculations, saved contracts, resource ownership or delivery safety.
- **Tasks:**
  1. Declare the planner/delivery suffixes and keys in Z19-Z34 once using AC1. Reuse the current dated prefix; do not compute a version at runtime or restamp unrelated data schemas.
  2. Wire routers, internal stage dispatch, external clients and the native readiness reader to those declarations. Select the planner or delivery health suffix by startup group; keep the shared listener-health check separate. Preserve native identity, body contracts and operation context.
  3. Update the route-to-failure-operation mapping together with its callers. Known changed paths must retain their native failure classifications, not accidentally fall through to a generic planning failure.
  4. Preserve collection startup, conflict, completion, cancellation, finalization and release order. Preserve captured input, reference lifetime, bounded parsing, independent run state, stage persistence and safe final delivery.
  5. Change named route/recording helpers and existing integration cases. Do not rewrite saved ledger paths, serialized operation IDs, output-family versions or old event fixtures because their strings resemble a route.
  6. Remove old route handlers and update current API/control-flow examples. Keep historical plan outcomes as history; only current forward references change.
- **Files touched - shared declarations and actual handlers:**
  - `packages/common-contracts/src/declare-feed-api-paths.ts` - new, only named feed-planning/delivery HTTP suffixes.
  - `packages/common-contracts/src/index.ts`
  - `packages/common-contracts/test/feed-api-paths.test.ts` - new, named route-map contract.
  - `services/feed-ingest-plan/src/api/server.ts`
  - `services/feed-ingest-plan/src/api/routes/health.route.ts`
  - `services/feed-ingest-plan/src/api/routes/plan.route.ts`
  - `services/feed-ingest-plan/src/api/routes/document.route.ts`
  - `services/feed-ingest-plan/src/api/routes/collection.route.ts`
  - `services/feed-ingest-plan/src/api/routes/feed-health-state.route.ts`
  - `services/feed-ingest-plan/src/api/routes/stages.route.ts`
  - `services/feed-ingest-plan/src/api/planner-failure-operation.ts`
  - `services/feed-ingest-plan/src/run-feed-plan.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-http-client.ts`
  - `services/feed-ingest-plan/scripts/feed-ingest-plan-supervisor.ts`
  - `services/feed-ingest-plan/scripts/read-feed-api-readiness.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-api.ts`
  - `services/feed-ingest-plan/scripts/safe-persist-http-client.ts`
  - `services/serve-pipeline-apis/src/read-api-readiness.ts` - verify the separate shared-health check; native checks belong to the feed reader.
- **Files touched - real URI callers in tests/helpers:**
  - `services/feed-ingest-plan/test/plan-api.test.ts`
  - `services/feed-ingest-plan/test/plan-engine.test.ts`
  - `services/feed-ingest-plan/test/collection-http.test.ts`
  - `services/feed-ingest-plan/test/collection-work.test.ts`
  - `services/feed-ingest-plan/test/collection-capacity.test.ts`
  - `services/feed-ingest-plan/test/collection-recordings.ts`
  - `services/feed-ingest-plan/test/candidate-capture-http.test.ts`
  - `services/feed-ingest-plan/test/article-failure-retention.test.ts`
  - `services/feed-ingest-plan/test/article-entities-workflow.test.ts`
  - `services/feed-ingest-plan/test/file-baseline-recording.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-http-client.test.ts`
  - `services/feed-ingest-plan/test/feed-ingest-plan-supervisor.test.ts`
  - `services/feed-ingest-plan/test/safe-persist-http.test.ts`
  - `services/feed-ingest-plan/test/operation-logging.test.ts`
  - `services/feed-ingest-plan/test/network-failure-evidence.test.ts`
  - `services/feed-ingest-plan/test/selection-metrics.test.ts`
  - `services/feed-ingest-plan/test/serve-feed-apis.test.ts`
  - `services/serve-pipeline-apis/test/api-routing.test.ts`
- **Files touched - current documentation and plan pointers:**
  - `docs/architecture/sources/feed-operator-api.md`
  - `docs/architecture/sources/feed-plan-runner.md`
  - `docs/reference/serve-pipeline-apis.md`
  - `docs/reference/api-routing.md`
  - `TODO/20261102-remove-typescript-robots-checks-plan.md` - current route references only; retain shipped historical outcomes.
- **Acceptance gates:**
  - Local: inspect the shared selector; run common-contracts, planner and shared-server checks. Combine the selected existing route/client/collection/delivery/failure cases with the new bounded route-map test.
  - Planner integration: run the existing real in-process and permitted ephemeral-loopback journeys with recorded sources. Require unchanged selected data, failures, trace identity, byte bounds, parser/reference lifetime, collection completion and cleanup order through the new paths.
  - Failure mapping: force existing fixture-backed failure cases through changed operations. Their serialized failure operation, execution identity, diagnostics and partial-result retention must stay unchanged.
  - Delivery integration: use the actual safe-persist handler/writer against generated temporary output. Preserve its validation, metadata binding, atomic delivery and error behavior. Require distinct native health identity and no old delivery route.
  - Route refusal: old paths return HTTP 404 rather than redirect or alias. Already conforming stage paths still dispatch their real operations. Test the named route map and real handlers, not a scan of repository text.
  - CI: existing common-contract, planner, writer and shared-server suites; no extra browser journey or workflow dispatch that writes committed production data.
  - Report/control-flow references: a representative existing report retains the same domain results and failure meanings; only current API links/control-flow labels change.
- **Oracle:** The existing fixture-backed planner/delivery journeys produce unchanged native outputs and safety outcomes through the new route map, with every retired path refused. This does not establish live publisher access or authorize a planner algorithm or persisted-contract change.

**Table AC - PR 8 decisions**

| Id | Decision | Authority |
| --- | --- | --- |
| AC1 | `PLANNER_API_PATHS` and `DELIVERY_API_PATHS` export the suffixes for the keys in Table Z. Router modules mount them beneath the existing `PLANNER_API_PREFIX`; clients append them once. Keep the existing prefix authority in `version.ts`, not another copied date or configurable URL registry. | Current protocol authority; exact route map |
| AC2 | `read-feed-api-readiness.ts` selects the planner or delivery health suffix by startup group and retains its native identity/control checks. `serve-pipeline-apis/read-api-readiness.ts` separately checks Z18's shared listener identity. Planner and delivery health names remain distinct; changing only the shared reader is insufficient. | Actual native and shared readiness callers |
| AC3 | `persist-data` still invokes the existing safe delivery implementation. Its saved `safe_persist_data` operation identity and receipt/ledger formats do not become HTTP aliases or change spelling. | Existing delivery safety and persisted identities |
| AC4 | Only actual URL consumers change. Ledger names, data paths, imports such as `feed-health-state.schema`, and historical recordings are not route definitions. | Direct filtered reference inventory |
| AC5 | The route failure classifier and internal stage calls share the new declarations. Preserve each native failure-operation value; a route rename must not change report classification. | Actual failure-route mapping |

**Table AD - PR 8 rejected alternatives**

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| AD1 | Globally replace every old operation string | The same words identify ledger families, imports and serialized failures. | Unrelated persisted-data changes and incorrect error/report semantics. | Actual route versus data consumers |
| AD2 | Change route names but leave internal calls and readiness alone | The combined plan still calls the old paths and the supervisor still probes old health. | Broken integrated planning/delivery despite passing isolated router checks. | Actual internal HTTP and supervisor flow |
