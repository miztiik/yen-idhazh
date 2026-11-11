# Restore source-backed visual publication

**Last Updated**: 2026-11-10
**Level**: 3; new persisted contracts, visual semantics or runtime changes escalate to Level 5.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Restore useful chart and Who/What grid generation by repairing the evidence passed to the planner, preserving exact refusals and proving the complete publication path |
| A2 | Hard scope - in | Finalized evidence handoff; article-specific reference grammar; rule-derived visual guidance; context accounting; existing refusal diagnostics; chart/grid publication and reader verification; active type selection restricted to implemented chart and Who/What types |
| A3 | Hard scope - out | Table B distinguishes abandoned types from separate policy work; abandoned types are not a delivery queue |
| A4 | Chosen strategy | Repair the existing two-call path and existing payload families before adding renderers; Fowler architectural consultation |
| A5 | Contracts | Reuse `ElementTable`, `VisualPlan`, `VisualDecision`, `ItemHealthRow` and `VisualAttemptRow`; request-only projections do not become another persisted format. Retain historical type names for old-record compatibility, not as active request choices |
| A6 | ESCALATE triggers | 1. A persisted field, enum meaning, visual role or published shape must change. 2. A third model call, different model, larger context window or changed fallback policy is proposed. 3. Source text would become an instruction, path or destination. 4. A warranted example still cannot produce a valid visual and the proposed remedy is to weaken evidence validation or force publication. 5. A row revives an abandoned type or changes the scope in Table B. 6. Article-admission behavior or the recorded meaning of a context refusal must change |
| A7 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`; parallel N = 4, with rows serialized by their dependencies and shared files |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

Table B - Separate work and its cost

| ID | What is separate | Cost of leaving it separate | What brings it into delivery |
| --- | --- | --- | --- |
| B1 | Abandoned types: area, timeline, table, flow, comparison, callout, quotecard and keyfacts | These forms are neither offered for new production requests nor implemented; their contexts use an active supported form only when it preserves the evidence and purpose, otherwise no visual | No delivery row in this plan; revival requires a new product and design decision |
| B2 | Deleting historical type names or rewriting old payloads | Native readers retain the abandoned names so existing stored records still load | A separately designed, verified read-side migration; restricting new requests does not require historical deletion |
| B3 | Other diagram families and their supporting classification | Process and relationship stories remain without those illustrations; retirement of flow does not decide the lifecycle of other undeclared diagram forms | A separate source-backed diagram design; none is introduced by this repair |
| B4 | Fallback activation; historical redraw | Fallback stays off, and old text-only items do not gain visuals; active type selection is changed by row #1 | A separate fallback or revision decision; direct deliveries first supply the fallback population that is currently absent |
| B5 | The unfinished article-classification roadmap | This work does not deliver article-kind, stance, sentiment or classification-ledger features | Reconcile that roadmap with the current classifier and execute its remaining outcomes independently |

## 1. Status Reckoner

Table C - One row per repair PR

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Give the visual planner usable source evidence | - | A | DONE | fantastic-garbanzo | - | 0b1cac34-83e8-494c-99fc-6539f5299bdc |
| C2 | 2 | Preserve the exact reason a visual was refused | 1 | B | PENDING | - | - | - |
| C3 | 3 | Prove generated visuals reach publication and the reader | 1, 2 | C | PENDING | - | - | - |

## 2. Row #1 - Give the visual planner usable source evidence

- **Scope:** Make the planning request expose the finalized source elements and their usable visual roles without changing persisted shapes, the model or the number of calls.
- **Files touched:**
  - `backend/idhazh/classify/plan_visual_request.py` (new; owns the bounded evidence menu, reference-schema projection and rule-derived guide)
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/dag.py`
  - `backend/idhazh/contracts/visual_type.py` (documentation of historical names versus active selection)
  - `backend/idhazh/stages/two_calls.py`
  - `backend/utilities/measure_two_calls.py`
  - `config/idhazh.json`
  - `config/prompts/plan-visual.txt`
  - `config/prompts/continue-summary.txt`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_prompt_files.py`
  - `backend/tests/test_measure_two_calls.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
- **Acceptance gates:** Inspect the shared `test:changed` selection from `frontend/`; locally run the selected lint/type checks and the named request, prompt, context and grammar cases needed for the oracle. CI owns the complete suite. No live dispatch or publication is required while authoring this plan.
- **Oracle:** For a plannable in-memory article, the references offered by the request grammar equal the finalized table's ids and every such id is visible in the request, including model-anchored nonnumeric elements; a foreign id cannot decode. This proves input completeness and reference membership, not that a real model will select a useful visual.

Table D - Request decisions

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | Pass the exact post-anchoring table used by reachability and validation into the request builder. Preserve source spans, kinds, values, units and relevant existing label metadata; do not reconstruct ids from the raw label reply | Fowler consultation; [current handoff gap](../docs/architecture/summarize/prompt.md#the-second-call-writes-this-summary-and-the-article-is-read-once) |
| D2 | Put the menu after the reusable prompt prefix as fenced item data. Keep shared instructions independent of the article and keep the two calls adjacent | [Prompt contract](../docs/architecture/summarize/prompt.md) |
| D3 | Narrow reference fields in the derived request grammar to the visible ids. Retain the native persisted schema for historical reading. Handle an empty reference set with empty arrays and a null optional whole, not an invalid empty enum or an invented id | Fowler consultation; [native plan rules](../docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) |
| D4 | Derive the type/role guide from the existing vocabulary and configured floors for active selected types only. Explain the grid's actor/claim pairing and give compact chart, grid and legitimate-decline examples. Do not present abandoned forms as request options or future work | [Visual rule](../docs/concepts/digest.md#the-visual-rule); Table B |
| D5 | Include the added menu and guide in context accounting, including the bounded additions made by anchoring. Reuse the configured model's tokenizer or existing bounded sizing mechanism; do not invent a token rate, silently discard evidence or raise context limits | [Two-call context accounting](../docs/architecture/summarize/prompt.md#the-output-budget-is-derived-not-picked) |
| D6 | Update the measurement utility and all direct builder callers with the same finalized evidence. Keep static schema/budget inspection possible without a live article, but require the production request to receive its real table | Verified callers in `classify/calls.py`, `stages/two_calls.py` and `utilities/measure_two_calls.py` |
| D7 | Keep summary-first recovery, legitimate no-visual outcomes and existing evidence validators. Do not rely on unsupported JSON Schema conditionals to enforce cross-field rules | [Summary-first contract](../docs/architecture/summarize/prompt.md#summary-before-visual) |
| D8 | Set the committed `enabled_types` to the implemented chart types and `whowhat`, and enable the existing type-selection policy so the actual request grammar enforces that selection. Keep fallback off. Native enum members remain available only for generic validation and historical compatibility, not as additional production choices | Table A; existing configuration mechanism |

Table E - Rejected request shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Only rewrite the prompt | Better wording still cannot expose ids omitted from the request | Continued invisible nonnumeric evidence and no structural reference-membership control | Fowler consultation |
| E2 | Offer numeric charts only | It excludes the implemented source-backed text grid instead of repairing its inputs | Loss of the supported nonnumeric visual family | [Request vocabulary](../docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#config-selects-requests-code-owns-correctness) |

## 3. Row #2 - Preserve the exact reason a visual was refused

- **Scope:** Retain native shape-error field/rule details and distinguish them from evidence, configuration and compiler refusals using the existing diagnostic fields and decision rationale.
- **Files touched:**
  - `backend/idhazh/contracts/visual.py`
  - `backend/idhazh/stages/two_calls.py`
  - `backend/tests/contracts/test_visual_plan.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_visual_attempts.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
- **Acceptance gates:** Use the shared selector for lint/type checks and the smallest named plan-validation, recording and refusal cases. CI owns the complete suite. Confirm that payload fields, accepted values and historical read behavior remain unchanged; otherwise trigger A6 before implementing a contract change.
- **Oracle:** Minimal real inputs produce distinguishable persisted diagnostics for a malformed decline, a native evidence rejection and a valid request with no compiler, without inventing a validator rejection or a requested type. This proves truthful recording, not the editorial correctness of a model's decline.

Table F - Refusal decisions

| ID | Decision | Authority |
| --- | --- | --- |
| F1 | Give existing cross-field plan validators structured native errors that identify the offending field and rule. Project those details through the existing `failed_field` and `failed_rule` fields without parsing English error messages or changing which plans validate | Fowler consultation; existing native validation and `_shape_cells()` |
| F2 | Preserve bounded, sanitized shape diagnostics in the decision rationale when the summary remains publishable. Do not mark the whole item failed or put a failure detail on a successful item-health row | Existing worker success invariant |
| F3 | Keep `rejection_reason` exclusively for a real `ValidatorCheck`. Preserve the original type only after a typed plan is valid; malformed or suppressed requests remain unknown | [Recorded refusal semantics](../docs/architecture/publishing/visuals.md#every-none-says-which-gate-refused-it) |
| F4 | Keep fallback activation and cold-start rules unchanged. A missing direct-delivery population is evidence to report, not a population to manufacture | Fowler consultation; `visual_population.py` and `depth_floor()` |
| F5 | Execute after row #1 because the request builder, stage, tests and owning page are shared integration surfaces | Verified file-set overlap |

Table G - Rejected refusal shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Clear contradictory fields from a declining plan and accept it | It changes an invalid model answer into apparent success | A separate acceptance-policy change and loss of the original defect | Existing native plan invariant |
| G2 | Add a new refusal taxonomy during implementation without design | It changes persisted meaning rather than merely retaining available diagnostics | Level 5 consultation, versioned models, writer/reader updates and historical compatibility | `CLAUDE.md` sections 6 and 10 |

## 4. Row #3 - Prove generated visuals reach publication and the reader

- **Scope:** Close the gap between a successful canned-plan test and a real request producing a source-backed chart or grid that survives ordinary assembly and renders.
- **Files touched:**
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/pipeline/test_published_whowhat_grids.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/utilities/build_canary_day.py`
  - `frontend/tests/reading-page.spec.ts`
  - `frontend/tests/whowhat-visual.spec.ts`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/publishing/visuals.md`
- **Acceptance gates:** Use the shared selector for the named backend publication cases and one representative reader journey. Extend existing tests instead of adding duplicate journeys. CI owns the complete suite. The manual real-model observation below is required evidence before claiming generation is restored, not a test that writes production data.
- **Oracle:** With only serialized worker outputs crossing into an isolated publisher tree, normal assembly creates the named chart/grid asset, the digest and inventory reference it, and the reader accepts that same artifact. This proves transport and rendering; authored or recorded model replies alone do not prove present-day model generation.

Table H - Delivery decisions

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | Exercise anchoring, the actual request builder, validation, compilation, worker serialization and normal assembly. Do not hand-construct a successful digest in place of assembly or pass the worker's public directory to the publisher | Fowler consultation; existing chart/grid publication boundary |
| H2 | Reuse existing source-backed fixtures or minimal in-memory inputs. Keep network access and real inference out of automated tests; do not add fixture files or mock internal business logic | `CLAUDE.md` sections 1 and 12 |
| H3 | Verify one reader journey containing a chart, a grid and a legitimate no-visual item. Include missing/empty visual data, one cross-page smoke and inspection for new errors or 404s; do not multiply themes or viewport journeys by default | `CLAUDE.md` sections 11 and 12 |
| H4 | Observe a bounded run with the committed model and production request path over named source-backed positive chart/grid examples and a negative example. Inspect actual captured requests, model replies, decisions and resulting assets. Use isolated outputs and the existing model/runtime tooling, not a new inference path or public test data | Fowler consultation; [pipeline-test limits](../docs/reference/github-actions.md#pipeline-tests) |
| H5 | Keep real-model observations separate from deterministic coverage. If a warranted example still declines or malforms, use its retained inputs to revise the request repair; do not call the capability restored because authored replies pass. Record the model, code revision and runner conditions rather than an invented visual-rate target | `CLAUDE.md` section 1, Guardrail 10 |
| H6 | After delivery, inspect the next scheduled content run's decisions, named assets, inventory and served day. A random pipeline-test draw proves execution only; an observed decline is not automatically a failure unless that input warranted a visual | [Workflow contract](../docs/reference/github-actions.md#pipeline-tests) |
| H7 | Keep the current owning pages whole: these edits describe their existing prompt, refusal and publication questions, not a second subsystem | [Documentation split test](../docs/reference/documentation-structure.md#a-page-answers-one-question-and-length-is-a-symptom-rather-than-the-fault) |

Table I - Rejected delivery shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Treat any successful summary as proof of visual generation | It passes when every visual is absent | Continued false confidence and no evidence that the repair reaches a reader | Verified production failure mode |
| I2 | Force a visual or impose a publication quota | Source evidence and reader usefulness do not follow a quota | Misleading or decorative output and a separate editorial-policy change | [Visual rule](../docs/concepts/digest.md#the-visual-rule) |
