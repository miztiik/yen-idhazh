# Restore source-backed visual publication

**Last Updated**: 2026-11-11
**Level**: 3; new persisted contracts, visual semantics or runtime changes escalate to Level 5.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Restore useful chart and Who/What grid generation by repairing the evidence passed to the planner, preserving exact refusals and proving the complete publication path |
| A2 | Hard scope - in | Finalized evidence handoff; article-specific reference grammar; rule-derived visual guidance; context accounting; existing refusal diagnostics; chart/grid publication and reader verification; implemented active types; retained-Article verification on the existing controlled test runtime; format-preserving first-call address presentation and coverage |
| A3 | Hard scope - out | Table B distinguishes abandoned types and unchosen format changes from active repair work; abandoned types are not a delivery queue |
| A4 | Chosen strategy | Land independently verified transport/reader increments without claiming restored generation; retain actual generation/publication as an open roll-up; correct first-call addressing before expanding the saved raw-label format |
| A5 | Contracts | Reuse `Article`, `ElementTable`, `LabelReply`, `VisualPlan`, `VisualDecision`, `ItemHealthRow`, `VisualAttemptRow` and existing capture/provenance shapes. Retained-input selections are ephemeral CLI inputs, not a new saved manifest/result family. Preserve historical type/reply reading, source text/offsets and current raw-label/capture fields |
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
| B6 | Precise claim-citation and capture-format expansion | Claims still use existing sentence ranges, so a future case may require finer representation; the currently audited useful whole sentences fit the native bound | A measured representation/readability blocker and a separate Level 5 design, including versioned raw-format metadata and historical capture reading; do not introduce it speculatively |

## 1. Status Reckoner

Table C - Repair increments and the restored-generation roll-up

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Give the visual planner usable source evidence | - | A | DONE | fantastic-garbanzo | - | 0b1cac34-83e8-494c-99fc-6539f5299bdc |
| C2 | 2 | Preserve the exact reason a visual was refused | 1 | B | DONE | shiny-spoon | - | ef9d68ad-ccf4-417d-9a05-fe0305ef21c7 |
| C3 | 3 | Prove generated visuals reach publication and the reader | 1, 2, 4, 5, 6 | C | PENDING | fuzzy-bassoon | - | 094b8d19-fd66-47ce-b6ff-72d8af8f39d7 |
| C4 | 4 | Replay retained articles on the controlled test runtime | 1, 2 | D | IN-FLIGHT | miniature-giggle | - | 98c0f7b2-33d5-487f-b893-37ef59cbb8c9 |
| C5 | 5 | Correct literal sentence addressing and claim coverage | 1, 2 | D | DONE | cautious-tribble | - | e7392204-404e-484d-9cf5-5811294c4553 |
| C6 | 6 | Show complete source-backed claims to the reader | 1, 2 | E | DONE | effective-guide | - | 96eb1442-fd7b-4734-b9a4-98d815cf9919 |

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
  - `backend/tests/test_visual_attempts.py`
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

- **Scope:** Retain the completed deterministic reader coverage while closing the remaining gap to fresh, source-backed model generation and ordinary publication.
- **Files touched:**
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/pipeline/test_published_whowhat_grids.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/utilities/build_canary_day.py`
  - `frontend/src/lib/visual/viewport.ts`
  - `frontend/tests/reading-page.spec.ts`
  - `frontend/tests/visual-legibility.spec.ts`
  - `frontend/tests/whowhat-visual.spec.ts`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/how-a-story-chart-is-drawn-and-what-refuses-one.md`
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

Table J - Roll-up completion evidence

| ID | Outcome | State and evidence |
| --- | --- | --- |
| J1 | Serialized worker -> ordinary assembly -> native reader and stable recovery journey | DONE in [#2018](https://github.com/miztiik/yen-idhazh/pull/2018); this does not establish model generation |
| J2 | Safe fixed-input model verification without production writes | Pending row #4 |
| J3 | Existing-format first-call address/coverage correction | Pending row #5 |
| J4 | Fresh warranted chart, warranted actor/claim grid and legitimate no-visual outputs | Pending rows #4 and #5, using the same named source inputs and both real production calls |
| J5 | Normal asset, digest/inventory and served-reader verification on the merged producer revision | Pending actual publication; workflow success without a delivered visual is not positive proof |

## 5. Row #4 - Replay retained articles on the controlled test runtime

- **Scope:** Add an artifact-only retained-input mode to the existing manual pipeline workflow, calling the real two-call producer on bounded native Article files without refetching or publishing.
- **Files touched:**
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `backend/utilities/replay_article_calls.py` (new; owns bounded retained-input selection, native invocation and serialization)
  - `backend/idhazh/stages/two_calls.py`
  - `backend/tests/test_replay_article_calls.py` (new; marked with the existing relevant tiers)
  - `docs/reference/github-actions.md`
  - `docs/reference/retained-article-verification.md` (new)
- **Acceptance gates:** Inspect the shared selector; run selected Python lint/types, native controller/isolation tests and applicable existing workflow lint. CI owns the complete suite. Do not add tests of workflow-file text. Manually run the retained mode on its exact code revision after delivery, retain its outputs and verify that no commit/deploy job or reader-facing write occurred.
- **Oracle:** A named native Article passes through `two_calls_one_item()` with actual request construction and recorded boundary responses, producing native summary/decision/capture files and any compiled asset only under the isolated output root; invalid or escaping inputs fail before inference. This proves native invocation/isolation, not live model quality.

Table K - Retained-input decisions

| ID | Decision | Authority |
| --- | --- | --- |
| K1 | Add optional `retained_source_run` and `retained_item_ids` workflow inputs. Empty source run preserves the existing random mode. Retained mode requires a positive run id and an explicit, unique list of valid native item ids bounded by the existing configured dispatch size | Existing workflow and native input contracts; bounded verification requirement |
| K2 | Download only the explicitly selected source run's named native artifacts through existing trusted artifact machinery. Load only selected Article files inside the downloaded root; validate payloads, eligibility, identities and paths. No history/tree discovery, refetch, re-extraction or silent input repair | Guardrails 3, 11 and 12; [workflow contract](../docs/reference/github-actions.md#pipeline-tests) |
| K3 | Use the existing model-server setup, committed configured model, operator-controlled destination and production settings. Retained mode runs no experimental case variants and forwards no expected outcome into the model request | [Model boundary](../docs/architecture/summarize/model-boundary.md) |
| K4 | Invoke the actual `two_calls_one_item()` item-major. Retain native inputs, summaries, decisions, compiled data and both actual captures, with existing provenance/logged code/model/runtime/host identities. Do not reproduce inference logic or retry model declines | Focused Fowler design; Table H |
| K5 | If needed for isolation, pass an optional typed render-output root through the existing native call boundary with the current default unchanged. The adapter must supply its private root; do not monkeypatch production globals, mutate committed configuration or create another inference engine | Native file-in/file-out stage boundary |
| K6 | Keep retained mode artifact-only with read-only repository permission and no ledger-commit, deploy or frontend-public path. Validate selected inputs before model work. Fail explicitly on invalid input, genuine model failure or an unmet operator-requested outcome; never fabricate a successful summary or legitimate decline | Existing native statuses and publication boundary |
| K7 | Ephemeral validated CLI selections and native outputs require no new saved replay protocol. If a custom case manifest, expected-outcome schema, result ledger or capture-format change is actually necessary, stop before adding it | Table A6 and B6 |
| K8 | Keep this row's code/doc files disjoint from row #5. Each worker changes only its own Reckoner line; merge reconciliation preserves the complete current plan | [Execution contract](../docs/how-to/execute-a-plan.md#parallel-fan-out) |

Table L - Rejected verification shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L1 | Use the random article draw as fixed positive proof | It may contain no warranted chart/grid and mutable source pages do not isolate a producer change | Continued uncertainty or repeated uncontrolled dispatches | Actual generation observation; Table H |
| L2 | Start a full model in unsafe local memory or use another model | It risks unrelated work and does not verify the committed production model | A separate resource/model decision and non-comparable evidence | Configured runtime and runner boundary |
| L3 | Duplicate the producer or add a new workflow as a detour | A second inference path can pass while production still fails | Additional drift, maintenance and proof that never reaches the requested path | Focused Fowler design |

## 6. Row #5 - Correct literal sentence addressing and claim coverage

- **Scope:** Fix the demonstrated first-call address-presentation/coverage defect while preserving existing label/capture formats, source text and claim meanings.
- **Files touched:**
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/plan_visual_request.py`
  - `config/prompts/generate-labels.txt`
  - `config/prompts/plan-visual.txt`
  - `backend/utilities/measure_two_calls.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_measure_two_calls.py`
  - `tests/fixtures/planner/recorded-call-payloads.json`
  - `tests/fixtures/prompts/label.txt`
  - `tests/fixtures/prompts/summarize-and-plan.txt`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/extraction/elements.md`
  - `docs/architecture/publishing/visuals.md`
- **Acceptance gates:** Use the shared selector for applicable lint/types and the smallest presentation, anchoring, prompt, legacy-reading and budget cases; CI owns the complete suite. After rows #4 and #5 are available, execute fresh fixed retained-input verification on their exact code/model revision. Do not equate unit/fixture success with corrected live label coverage.
- **Oracle:** Each original source sentence has exactly one visible physical addressed line in a reversible presentation; native anchoring still uses the original text/offsets, correct literal references retain valid siblings, and wrong-sentence/missing/duplicate matches remain rejected. This proves presentation/provenance invariants, not that the model will copy every address correctly.

Table M - Format-preserving producer decisions

| ID | Decision | Authority |
| --- | --- | --- |
| M1 | Escape internal line controls through a reversible one-line presentation without changing Article.text, segmentation, offsets or source hashes. Make retained-prompt inspection understand both old and new presentation explicitly; do not flatten source whitespace or silently reinterpret historical prompt bytes | Existing source-span contract; measured address-presentation defect |
| M2 | Clarify literal printed-address copying, distinct actors and source-supported narrated claims in the label prompt. Do not count lines, infer a neighbouring address, paraphrase source spans, merge distinct people merely by surname or weaken the exact unique within-sentence locator | Existing attribution/anchoring contract |
| M3 | Keep `LabelReply.claims` as the existing `SentenceRange`, quotes as ranges and all raw-label/capture fields unchanged. Preserve required fields, list/string bounds, accepted native schemas and historical reply reading. Do not add ClaimCitation in this increment | Table B6; audited useful whole sentences fit the existing bound |
| M4 | Preserve CLAIM versus QUOTE meaning, reporting frames, attribution, hedge and qualifications. A shorter suffix that drops a qualification is not a clean positive. Whole-sentence readability and usefulness must be checked in actual outputs, not assumed from representability | Existing native kind meanings and visual rule |
| M5 | Keep compatible native width arithmetic, derived allowances, actual configured response/context caps and early admission unchanged. Retokenize complete actual requests for diagnostics; add no production tokenization call, capacity guard, forced visual or policy switch | [Prompt budget contract](../docs/architecture/summarize/prompt.md#the-output-budget-is-derived-not-picked) |
| M6 | Use row #4's controlled retained-input mode for named warranted chart/grid candidates and the verified negative. Retain both fresh calls and verify coverage, native validation, output data and source provenance. The generator receives no expected kind | Table H; Table J |
| M7 | If useful in-meaning claims still cannot be represented/read after this smaller correction, preserve the concrete counterexample and price the Level 5 raw-format option. Do not expand response/capture formats, model choices or kind meanings silently | Table A6 and B6 |

Table N - Rejected producer shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Immediately add precise claim citations and capture metadata | Existing ranges can represent the currently audited whole sentences, so that format expansion is not yet a demonstrated prerequisite | Versioned raw/capture models, legacy reading and a Level 5 design decision | Focused Fowler format ruling; newer source audit |
| N2 | Rescue a wrong address by searching neighbouring sentences or the whole article | It turns an invalid model reference into an apparently valid source claim | A changed grounding/safety policy and weaker provenance | Existing exact within-sentence locator |
| N3 | Declare restoration from successful summaries or authored visual replies | It repeats the failure that left normal production without visuals | Missing actual positive generation and public-delivery evidence | Table J |

## 7. Row #6 - Show complete source-backed claims to the reader

- **Scope:** Correct the independent reader defect where a fitted claim prefix hides its action or qualification, using the full validated excerpt already in the grid payload. Keep the existing table, actor labels, paired empty cells and loading/failure/retry behavior.
- **Files touched:**
  - `TODO/20261110-restore-visual-publication-plan.md`
  - `frontend/src/lib/visual/WhowhatVisual.svelte`
  - `frontend/tests/whowhat-visual.spec.ts`
  - `frontend/tests/reading-page.spec.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
- **Acceptance gates:** Inspect the shared selector, run the smallest existing grid-reader and reading-page selections plus applicable Svelte/type and whitespace checks, and leave the full suite to exact-head CI. Confirm the changed oracle fails against an isolated copy of the base component before changing its rendering. Perform an integrated-browser smoke of one representative view: full claim and trailing qualification, keyboard disclosure of a clipped actor, an ordinary actor without disclosure, missing and empty grid data with recovery, and one cross-page smoke. Separate deliberately missing responses from new errors/404s. Complete one bounded Susan readiness check on the finished surface using synthetic content only. Stop private preview helpers after the checks.
- **Oracle:** For a valid grid whose fitted claim ends before the action and final qualification, the What cell shows the exact complete `claim.span_excerpt` by default, wraps without clipping or horizontal overflow, and has no disclosure or tooltip. Who keeps `actor.display_text`; only an actor whose display differs from its full excerpt has native keyboard-operable `details`/`summary` revealing that exact excerpt. Short actors remain plain text and paired empty rows remain empty. Missing/empty grid data leaves story text and the existing retry usable. This proves reader correctness only, not actual model generation or restored publication; C3 and Table J remain incomplete.

Table O - Reader correction decisions

| ID | Decision | Authority |
| --- | --- | --- |
| O1 | Render the bounded full claim excerpt directly in What, preserving every literal word, attribution and qualification | [Reader design contract](../docs/concepts/design-system.md#the-whowhat-grid-keeps-each-actor-beside-its-claim) |
| O2 | Keep the fitted actor label in Who; disclose the full actor excerpt through native details/summary only when the two strings differ | [Native disclosure contract](../docs/concepts/design-system.md#content-on-demand-is-a-details-not-a-button) |
| O3 | Reuse the current two-column layout, wrapping and design tokens. Add no column, claim disclosure, tooltip, style redesign, dependency, tooling or fixture file | Existing reader surface and bounded repair scope |
| O4 | Change no persisted shape, compiler/fit bound, prompt, source range, model, cap, admission rule, fallback or publication policy. Row #4 inference is not a prerequisite for this independent reader repair | Tables A, B and J |

Table P - Rejected reader shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| P1 | Keep claims fitted and hide the rest behind disclosure or a tooltip | The action and qualification would still be absent from the default reading surface | Continued loss of the claim's meaning without an extra interaction | Table O1 |
| P2 | Increase fit limits or alter the producer to repair the reader | Full bounded source excerpts already reach the reader | Unnecessary producer changes and coupled acceptance behavior | Table O4 |
| P3 | Treat a synthetic or fixture grid as actual generation evidence | It proves only the renderer's behavior | The unclosed fresh-generation and ordinary-publication gap in Table J | Table J |
