# Report actual text-analysis results in GitHub Summary

**Last Updated**: 2026-11-09
**Level**: 5 - retire the workflow receipt contract and its dedicated live-verification reader without changing either API.

## 0 - Operating contract

Table A

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Show the submitted source and actual provider results instead of verification assertions. |
| A2 | Hard scope - in | Replace the manual workflow's test execution with caller-owned collection and reporting; use the same source for both providers; delete dedicated live-check machinery; keep the APIs independent of workflow output. |
| A3 | Chosen strategy | One coherent replacement PR, with process supervision, HTTP collection and Markdown rendering under `tools/text-analysis-caller/`. |
| A4 | ESCALATE triggers | Stop if implementation requires API/runtime changes, different source text for a provider, additional inference calls, new persistent response fields, or deletion of unrelated service/host unit coverage. |
| A5 | Execution | Execute per docs/how-to/execute-a-plan.md; one row shares one workflow and removal boundary. Open a PR and leave merge to a separate decision. |

Table B

| Id | Out of scope | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Provider implementation or HTTP contract changes | Existing provider behavior and output limitations remain. | A separately specified API requirement. |
| B2 | GLiNER classification calls | This report shows named-entity extraction, not desk/lens/event assignments; classification remains available in the API. | An explicit request for classification results and its additional inference call. |
| B3 | Deleting independent model-free service/host tests | Those files remain in the repository, but none execute in this manual reporting workflow. | A separately scoped test-removal request. |
| B4 | A dashboard, benchmark, grading system or replacement live-check suite | Results are inspected directly; the workflow makes no quality, concurrency or performance claim. | A separate measurable requirement. |

## 1 - Status Reckoner

Table C

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Replace verification with same-source result reporting | - | A | IN-FLIGHT | studious-garbanzo | - | - |

## 2 - Proposed report and execution shape

Table D

| Id | Surface | Shape |
| --- | --- | --- |
| D1 | Summary order | `Source text`, then `spaCy results`, then `GLiNER results`. Show the unchanged source once, expanded, as escaped preformatted text. |
| D2 | Result disclosure | Interpret twist-open tables as GitHub-supported `<details><summary>...</summary>` blocks containing Markdown tables. Use no JavaScript or custom web UI. |
| D3 | spaCy default results | Separate collapsible Named Entities and Important Terms tables. Entity columns: row id, text, type, occurrences. Term columns: row id, phrase, native YAKE score, occurrences. Explain that lower YAKE scores rank higher; they are not confidence probabilities. |
| D4 | spaCy optional results | Render every selected feature in response order. Raw entities: text, label, offsets, sentence. Sentences/noun phrases: text, offsets, sentence. Relations: action, actors, objects, times, places, sentence. Tokens: text, offsets, sentence, lemma, part of speech, dependency, head, morphology. Metrics: metric, native value. Include row ids in every table. |
| D5 | GLiNER results | One collapsible entities table with row id, exact mention, requested label, native score and offsets. Preserve response order and native score; do not aggregate, invent a spaCy confidence, or imply cross-provider score calibration. Show the requested labels beside the table. |
| D6 | Result context | Show only useful model/profile/language/selected-feature context outside the tables. Do not copy run identifiers, commit links, PASS/FAIL banners, check lists, cleanup receipts or timings into the report. GitHub already supplies run status and identity. |
| D7 | Empty and failed results | A successful empty collection says no results were returned. A failed feature shows its API error code/message without hiding completed siblings. A provider/startup/transport/invalid-response failure is explicit, never an empty success. Attempt the other provider if it remains available; exit nonzero after writing available results. Preserve native partial status; do not label it complete. |
| D8 | Safe rendering and size | Escape source and result text, pipes, newlines and HTML so content cannot break tables or close disclosure blocks. Offsets remain zero-based, half-open Unicode code points. If the full UTF-8 report exceeds GitHub's 1 MiB per-step limit, retain it as an artifact and publish an explicit size notice, not silently truncated results. |
| D9 | Data flow | Dispatch event on stdin -> validate inputs -> start existing shared API assembly -> bounded readiness -> one spaCy analysis POST -> one GLiNER NER POST -> stop owned process group in finally -> render saved outcomes -> publish summary and artifacts -> return execution status. |
| D10 | Request controls | Preserve English and existing spaCy profile/feature inputs. Default mode omits `features`; all/custom resolve from native capabilities. GLiNER labels are the distinct configured presentation types in `config/text-analysis/settings.json` `named_entities.label_map`, preserving configuration order. Refuse an empty label selection; do not add another hardcoded vocabulary. |
| D11 | Readiness versus tests | Readiness GETs and guaranteed process cleanup are operational necessities, not inference tests. Bound readiness and shutdown with existing listener settings. No schema probing, retired-route calls, invalid inputs, language probes, concurrency traffic, BUSY checks, warm repeats or automatic inference retries. |
| D12 | API boundary | Reuse existing request/result/error contracts and HTTPX. No report imports in either API, no report endpoints, no API file writes and no provider runtime changes. The workflow launches the existing shared assembly as a child; the caller never invokes extraction internals. |
| D13 | Artifacts | Keep exact per-provider `request.json` and `response.json` under fixed provider subdirectories, plus the complete `report.md`, inside one run-owned runner-temporary directory. Write files atomically. Keep diagnostic stderr in workflow logs, not in result tables. Upload available files even after failure. |
| D14 | Contract retirement | Stop producing `report.json`, verification health files and assertion-oriented event artifacts. No new report-envelope schema is needed: requests/responses retain their native contracts and Markdown is a projection. Old uploaded artifacts remain unchanged; no active downstream consumer of the retired receipt was found outside its dedicated harness/tests. |

## 3 - Row #1 - Replace verification with same-source result reporting

- **Scope:** Ship the reporting caller and workflow switch together, remove the displaced live-verification code, and update the documentation that describes that execution path.
- **Files touched - add:**
  - `tools/text-analysis-caller/run_analysis.py` - route collection, cleanup, report writing and final exit status; contain no execution implementation.
  - `tools/text-analysis-caller/supervise_apis.py` - own the existing shared assembly child, bounded readiness and exact process-group cleanup.
  - `tools/text-analysis-caller/collect_results.py` - validate dispatch input, prepare native requests, make the analysis calls and retain exact provider payloads.
  - `tools/text-analysis-caller/render_report.py` - pure escaped Markdown projection implementing Table D.
- **Files touched - edit:**
  - `.github/workflows/ner-tests.yml`
  - `services/text_analysis/gliner/tests/test_api.py`
  - `docs/how-to/run-spacy-tests.md`
  - `docs/how-to/run-ner-api-tests.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/reference/github-actions.md`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/text-analysis/text-analysis-api.md`
  - `docs/architecture/text-analysis/gliner-api.md`
  - `TODO/20261109-ner-pipeline-reporting-plan.md`
- **Files touched - delete:**
  - `services/text_analysis/spacy/scripts/run-spacy-test.py`
  - `services/text_analysis/spacy/scripts/probe-text-analysis.ts`
  - `services/text_analysis/spacy/scripts/declare_spacy_verification.py`
  - `services/text_analysis/spacy/scripts/validate-evidence-spans.ts`
  - `services/text_analysis/spacy/scripts/validate-evidence-spans.test.ts`
  - `services/text_analysis/spacy/tests/test_spacy_verification.py`
- **Workflow changes:**
  - Keep the registered workflow filename and current dispatch controls; change display/job/step labels from tests to result analysis.
  - Remove every Bun/test/pytest/unittest/JUnit step and the shared TypeScript-contract installation used only by the removed probe.
  - Remove host-regression invocation from this workflow, not the host tests themselves.
  - Keep frozen environment setup, required model preparation and installation compatibility checking; do not confuse model preparation with live API assertions.
  - Prepare both providers before starting the shared assembly; invoke the new caller through the existing GLiNER environment.
  - Replace separate test-evidence uploads with one results upload; retain existing retention policy and runner-temporary isolation.
  - Keep ordinary required CI independent of this manual inference workflow; do not add a replacement test workflow or workflow-file tests.
- **Live-test deletion boundary:**
  - In the edited GLiNER test file, delete `test_real_prepared_model_api`, `_verify_cancelled_native_ownership`, their test-only protocols and imports that become unused.
  - Retain model-free contract, normalization, diagnostics, composition and shutdown tests. They do not execute in the reporting workflow.
  - Keep both model-preparation scripts and all API `src` files unchanged. Their installation/startup validation is not the displaced live-check suite.
  - Replace claims that this workflow proves API correctness with its actual result-inspection purpose in the named documentation. Keep existing guide paths to avoid unrelated link churn.
- **Acceptance gates - local:**
  - Plan-only authoring runs no application tests.
  - During implementation, inspect the shared selector with `npm run test:changed -- --list` from `frontend/`; follow the documented no-local-provider-execution boundary.
  - Run `git diff --check`; confirm explicit changed paths and removal references. Do not install or run either model on the developer host.
- **Acceptance gates - CI and observation:**
  - Applicable existing lint/type checks and ordinary required CI remain merge gates. Do not restore tests to the manual reporting workflow.
  - Dispatch the actual candidate once on Linux as a result observation, not a reinstated live-check suite. Inspect the rendered GitHub Summary and exact saved requests/responses.
  - Confirm the report layout, escaping, empty/error distinction and oversize handling through direct in-memory renderer invocations; add no replacement live harness, model mocks or disk fixtures.
  - Before merging the operator-facing report, request one representative Susan review of its actual rendered summary, limited to Table D.
- **Oracle:** For a successful candidate dispatch, the saved requests have identical source text and exactly one analysis request per provider; every returned selected feature/entity appears faithfully in the corresponding rendered section, with no synthetic probe output. This proves provenance and report completeness, not recognition quality or concurrency behavior.

Table E

| Id | Decision | Authority |
| --- | --- | --- |
| E1 | Replace the behavior in one PR because switching the workflow without its collector/report would leave an incomplete operational path. | Engineering proposal |
| E2 | Keep reporting in a caller-side utility directory, following the existing summary caller separation; reuse native contracts rather than copying API models. | Existing boundary and engineering proposal |
| E3 | Remove dedicated live checks and their tests, not merely hide their output; preserve only the lifecycle work necessary to obtain results safely. | Requested scope |
| E4 | Use the dispatch source for GLiNER instead of the current prepared-model test's separate reference sentence. | Requested same-source result presentation |
| E5 | Derive caller-defined GLiNER labels from the existing configured presentation types; the providers still have different recognition semantics. | Engineering proposal |
| E6 | Retire the unused verification receipt rather than grow it into a reporting contract; exact native payloads remain the evidence. | Level-5 proposal |

Table F

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Add report generation or collation inside the APIs | Couples inference to workflow storage and presentation. | API dependencies, result persistence and lifecycle changes for no inference benefit. | Requested separation |
| F2 | Keep the old probes but remove their summary sections | Still spends inference on synthetic and repeated requests and leaves the unwanted machinery. | Continued multi-request runtime, test maintenance and assertion artifacts. | Requested deletion |
| F3 | Split the caller and workflow switch into separate PRs | Adds an unused intermediate tool and delays the actual reporting outcome. | Another review/delivery cycle; useful only if separate consumers emerge. | Engineering proposal |
| F4 | Raw JSON only | Retains evidence but does not provide readable result tables in GitHub Summary. | Less renderer code, but every inspection requires manual JSON reading. | Requested report surface |

## See also

- [Text-analysis architecture](../docs/architecture/text-analysis/text-analysis-api.md)
- [Native GLiNER architecture](../docs/architecture/text-analysis/gliner-api.md)
- [Current dispatch procedure](../docs/how-to/run-spacy-tests.md)
- [Gate and execution boundaries](../docs/how-to/run-the-gates.md)
