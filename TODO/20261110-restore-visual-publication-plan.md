# Restore source-backed visual publication

**Last Updated**: 2026-11-12
**Level**: 3 for numeric publication repair; row #9 retires the actor-grid contracts and their unused label output with explicit read-side compatibility.

## 0. Operating contract

Table A - Scope and execution

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Restore useful numeric chart generation by repairing the evidence passed to the planner, preserving exact refusals and proving the complete publication path; abandon and remove the Who/What grid |
| A2 | Hard scope - in | Finalized numeric evidence handoff; article-specific reference grammar; rule-derived chart guidance; context accounting; existing refusal diagnostics; numeric publication and reader verification; nine implemented numeric types or no visual; retained-Article verification on the existing controlled test runtime; reversible sentence addressing; complete actor-grid retirement and safe historical reading |
| A3 | Hard scope - out | Table B distinguishes abandoned types and unchosen format changes from active repair work; abandoned types are not a delivery queue |
| A4 | Chosen strategy | Remove the actor-grid end to end, then remove unconsumed label work; preserve numeric extraction, publication, lifecycle recovery and truthful historical metadata. Numeric generation/publication remains an open roll-up |
| A5 | Contracts | Row #9 removes the grid payload and current range observations, stamps the affected native contracts and projection together, and preserves strict named legacy readers. Keep `Article`, numeric `VisualData`, renderer/unit-table versions, captures/provenance, source text/offsets and historical outcome facts unchanged. Retained-input selections remain ephemeral CLI inputs |
| A6 | ESCALATE triggers | 1. A persisted change beyond row #9's named retirement/migrations is needed. 2. A third model call, different model, larger context window or changed fallback policy is proposed. 3. Source text would become an instruction, path or destination. 4. A warranted numeric example still cannot produce a valid visual and the proposed remedy is to weaken evidence validation or force publication. 5. A row revives an abandoned type or changes the scope in Table B. 6. Article-admission behavior or the recorded meaning of a context refusal must change |
| A7 | Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`; parallel N = 4, with rows serialized by their dependencies and shared files |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

Table B - Separate work and its cost

| ID | What is separate | Cost of leaving it separate | What brings it into delivery |
| --- | --- | --- | --- |
| B1 | Abandoned types: area, timeline, table, flow, comparison, callout, quotecard, keyfacts and whowhat | These forms are not offered for new requests; row #9 removes the actor-grid implementation rather than retaining it behind a flag. Unsupported evidence produces no visual | No revival row in this plan; revival requires a separate product and design decision |
| B2 | Deleting historical type names or rewriting old payloads | Native readers retain the abandoned names so existing stored records still load | A separately designed, verified read-side migration; restricting new requests does not require historical deletion |
| B3 | Other diagram families and their supporting classification | Process and relationship stories remain without those illustrations; retirement of flow does not decide the lifecycle of other undeclared diagram forms | A separate source-backed diagram design; none is introduced by this repair |
| B4 | Fallback activation; historical redraw | Fallback stays off, and old text-only items do not gain visuals; active type selection is changed by row #1 | A separate fallback or revision decision; direct deliveries first supply the fallback population that is currently absent |
| B5 | The unfinished article-classification roadmap | This work does not deliver article-kind, stance, sentiment or classification-ledger features | Reconcile that roadmap with the current classifier and execute its remaining outcomes independently |
| B6 | Claim-coverage, source-range production and future claim-format work | The abandoned actor-grid has no current consumer for claims, quotes, keyphrases or lede addresses; row #9 removes their production and retains only strict legacy raw-reply validation | A separate capability with a real consumer and a new design; no capture-format change or historical-capture edit belongs to this retirement |

## 1. Status Reckoner

Table C - Repair increments and the restored-generation roll-up

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Give the visual planner usable source evidence | - | A | DONE | fantastic-garbanzo | - | 0b1cac34-83e8-494c-99fc-6539f5299bdc |
| C2 | 2 | Preserve the exact reason a visual was refused | 1 | B | DONE | shiny-spoon | - | ef9d68ad-ccf4-417d-9a05-fe0305ef21c7 |
| C3 | 3 | Prove generated numeric visuals reach publication and the reader | 1, 2, 4, 5, 7, 8, 9 | C | PENDING | fuzzy-bassoon | - | 094b8d19-fd66-47ce-b6ff-72d8af8f39d7 |
| C4 | 4 | Replay retained articles on the controlled test runtime | 1, 2 | D | DONE | miniature-giggle | - | 98c0f7b2-33d5-487f-b893-37ef59cbb8c9 |
| C5 | 5 | Correct literal sentence addressing | 1, 2 | D | DONE; claim-coverage work retired by row #9 | cautious-tribble | - | e7392204-404e-484d-9cf5-5811294c4553 |
| C6 | 6 | Show complete source-backed claims to the reader | 1, 2 | E | COLLAPSED - Abandoned by row #9; prior reader correction delivered | effective-guide | - | 96eb1442-fd7b-4734-b9a4-98d815cf9919 |
| C7 | 7 | Install native Pages build validation prerequisites | - | F | DONE | fuzzy-succotash | - | 68150591-c6fc-4b82-864c-3aee606bc27e |
| C8 | 8 | Restrict requested labels to usable native references | 1, 5, 7 | G | DONE; range production retired by row #9 | shiny-happiness | - | aeb6859c-ce2e-40c6-8afb-a7c83e841531 |
| C9 | 9 | Retire the actor-grid and unused label work | 1, 2, 5, 7, 8 | H | DONE | silver-enigma | - | 619fd6bf-b638-4d89-b3bc-825bd94ecfa6 |

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
| D4 | Derive the type/role guide from the existing vocabulary and configured floors for active selected types only. Give compact numeric-chart and legitimate-decline examples; row #9 removes the former grid guide. Do not present abandoned forms as request options or future work | [Visual rule](../docs/concepts/digest.md#the-visual-rule); Table B |
| D5 | Include the added menu and guide in context accounting, including the bounded additions made by anchoring. Reuse the configured model's tokenizer or existing bounded sizing mechanism; do not invent a token rate, silently discard evidence or raise context limits | [Two-call context accounting](../docs/architecture/summarize/prompt.md#the-output-budget-is-derived-not-picked) |
| D6 | Update the measurement utility and all direct builder callers with the same finalized evidence. Keep static schema/budget inspection possible without a live article, but require the production request to receive its real table | Verified callers in `classify/calls.py`, `stages/two_calls.py` and `utilities/measure_two_calls.py` |
| D7 | Keep summary-first recovery, legitimate no-visual outcomes and existing evidence validators. Do not rely on unsupported JSON Schema conditionals to enforce cross-field rules | [Summary-first contract](../docs/architecture/summarize/prompt.md#summary-before-visual) |
| D8 | Offer only implemented numeric chart types in committed configuration, defaults, effective selection and request schemas, including policy-off paths. Keep fallback off. Historical type names remain inert compatibility vocabulary, not production choices | Table A; row #9 |

Table E - Rejected request shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Only rewrite the prompt | Better wording still cannot expose ids omitted from the request | Continued invisible nonnumeric evidence and no structural reference-membership control | Fowler consultation |
| E2 | Retain the former rejection of numeric-only operation | Superseded: the actor-grid is abandoned and row #9 removes it end to end | Keeping an unwanted producer, compiler and reader solely for an abandoned goal | Table A; Table S |

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

## 4. Row #3 - Prove generated numeric visuals reach publication and the reader

- **Scope:** Retain the completed deterministic reader coverage while closing the remaining gap to fresh, source-backed model generation and ordinary publication.
- **Files touched:**
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/utilities/build_canary_day.py`
  - `frontend/src/lib/visual/viewport.ts`
  - `frontend/tests/reading-page.spec.ts`
  - `frontend/tests/visual-legibility.spec.ts`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-the-gates.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/how-a-story-chart-is-drawn-and-what-refuses-one.md`
- **Acceptance gates:** Use the shared selector for the named backend publication cases and one representative reader journey. Extend existing tests instead of adding duplicate journeys. CI owns the complete suite. The manual real-model observation below is required evidence before claiming generation is restored, not a test that writes production data.
- **Oracle:** With only serialized worker outputs crossing into an isolated publisher tree, normal assembly creates the named numeric asset, the digest and inventory reference it, and the reader accepts that same artifact. This proves transport and rendering; authored or recorded model replies alone do not prove present-day model generation.

Table H - Delivery decisions

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | Exercise anchoring, the actual request builder, numeric validation/compilation, worker serialization and normal assembly. Do not hand-construct a successful digest in place of assembly or pass the worker's public directory to the publisher | Existing numeric publication boundary |
| H2 | Reuse existing source-backed fixtures or minimal in-memory inputs. Keep network access and real inference out of automated tests; do not add fixture files or mock internal business logic | `CLAUDE.md` sections 1 and 12 |
| H3 | Verify one representative numeric phone journey and a legitimate no-visual item. Include navigation/reload, missing/empty numeric data, one cross-page smoke and inspection for new errors or unexpected 404s; preserve numeric observer lifecycle regression coverage | `CLAUDE.md` sections 11 and 12 |
| H4 | Separately observe a bounded run with the committed model and production request path over named source-backed positive numeric examples and a negative example. Inspect actual captured requests, replies, decisions and assets. Row #9 runs no inference, model load, production writer or workflow dispatch | [Pipeline-test limits](../docs/reference/github-actions.md#pipeline-tests); Table S |
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
| J1 | Serialized numeric worker -> ordinary assembly -> native reader and stable recovery journey | DONE in [#2018](https://github.com/miztiik/yen-idhazh/pull/2018); row #9 preserves numeric coverage while removing actor coverage. This does not establish model generation |
| J2 | Safe fixed-input model verification without production writes | Row #4 delivered in [#2023](https://github.com/miztiik/yen-idhazh/pull/2023); the retained observation verified isolation, provenance and truthful failures, not positive generation |
| J3 | Reversible first-call addressing and usable numeric references | Rows #5 and #8 delivered addressing/reference enforcement; row #9 retains it while retiring range and claim-coverage requirements |
| J4 | Fresh warranted numeric chart and legitimate no-visual outputs | Still unproved: the retained numeric call timed out. Actor outcomes are abandoned, not replacement evidence for a numeric positive |
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
| L1 | Use the random article draw as fixed positive proof | It may contain no warranted numeric chart and mutable source pages do not isolate a producer change | Continued uncertainty or repeated uncontrolled dispatches | Actual generation observation; Table H |
| L2 | Start a full model in unsafe local memory or use another model | It risks unrelated work and does not verify the committed production model | A separate resource/model decision and non-comparable evidence | Configured runtime and runner boundary |
| L3 | Duplicate the producer or add a new workflow as a detour | A second inference path can pass while production still fails | Additional drift, maintenance and proof that never reaches the requested path | Focused Fowler design |

## 6. Row #5 - Correct literal sentence addressing

- **Scope:** Retain the delivered reversible first-call sentence presentation and exact source anchoring; row #9 retires claim coverage and its unused output fields.
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
| M2 | Keep literal printed-address copying and the exact unique within-sentence locator for current numeric labels and entity/place mentions; never search a neighbouring sentence to rescue a wrong address | Existing attribution/anchoring contract |
| M3 | Row #9 replaces current range production with four consumed fields and validates historical retired fields before discarding them. Historical raw captures stay unchanged | Table B6; Table S |
| M4 | Preserve historical element-kind meanings without retaining a current claim/quote producer or reader | Table S |
| M5 | Keep compatible native width arithmetic, derived allowances, actual configured response/context caps and early admission unchanged. Retokenize complete actual requests for diagnostics; add no production tokenization call, capacity guard, forced visual or policy switch | [Prompt budget contract](../docs/architecture/summarize/prompt.md#the-output-budget-is-derived-not-picked) |
| M6 | Use row #4's controlled retained-input mode separately for warranted numeric candidates and a verified negative. Retain both fresh calls and verify native validation, output data and source provenance; the generator receives no expected kind | Table H; Table J |
| M7 | Claim-coverage/range expansion is abandoned with the actor-grid; retain no speculative claim-format requirement | Table B6 |

Table N - Rejected producer shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N1 | Add precise claim citations or new capture metadata | The only proposed claim reader is abandoned | Unconsumed output, versioned capture migration and a separate capability decision | Table B6 |
| N2 | Rescue a wrong address by searching neighbouring sentences or the whole article | It turns an invalid model reference into an apparently valid source claim | A changed grounding/safety policy and weaker provenance | Existing exact within-sentence locator |
| N3 | Declare restoration from successful summaries or authored visual replies | It repeats the failure that left normal production without visuals | Missing actual positive generation and public-delivery evidence | Table J |

## 7. Row #6 - Show complete source-backed claims to the reader

- **Scope:** COLLAPSED - Abandoned with the actor-grid in row #9; the prior full-claim reader correction was delivered but is not an active capability or generation outcome.
- **Files touched:**
  - `TODO/20261110-restore-visual-publication-plan.md`
  - `frontend/src/lib/visual/WhowhatVisual.svelte`
  - `frontend/tests/whowhat-visual.spec.ts`
  - `frontend/tests/reading-page.spec.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
- **Acceptance gates:** Historical disposition only; row #9 deletes the component, state, dedicated tests and active design guidance. Numeric reader lifecycle/recovery coverage remains required by Table H3.
- **Oracle:** No current actor-grid is requested, compiled, published or rendered. Historical actor outcomes remain facts in records but project to no visual; numeric generation remains unresolved in Table J.

## 8. Row #7 - Install native Pages build validation prerequisites

- **Scope:** Repair the demonstrated Pages build prerequisite failure by preparing the supported Python environment and installing the declared backend package before native frontend build validation. Keep publication static-only and preserve the existing triggers, decision/evidence rules, concurrency, permissions, native appearance validation and build/deploy flow.
- **Files touched:**
  - `.github/workflows/pages.yml`
  - `docs/reference/github-actions.md`
  - `TODO/20261110-restore-visual-publication-plan.md`
- **Acceptance gates:** Inspect the shared `test:changed -- --list` selection, run applicable existing lint and whitespace checks, and leave the full suite to exact-head PR CI. Use an isolated Python environment and the declared package install to verify the native appearance/build prerequisites without relying on preinstalled local packages. Do not add workflow-text tests, fixtures, mocks or dependencies. The implementation worker opens one PR and follows CI without merging or dispatching workflows.
- **Oracle:** Pages run `42990317413` on `2ed07ebc0f4f39f254d0a84fd7a0a58991fd6770` passed `decide`, failed build job `130421503658` at `build-frame-css.mjs` with `ModuleNotFoundError: No module named 'pydantic'`, and skipped deployment. After the declared package install, the real native appearance validation and static build must pass, with exact-head CI confirming the candidate. Local setup and PR CI do not prove a Pages deployment; C3 and Table J remain incomplete until the separate static deployment and served-site inspection.
- **Decisions:** Reuse Python 3.12 and `pip install -e .` from the existing publishing workflows rather than copying a dependency subset into YAML. The beneficiary is native build-time validation of committed appearance configuration; no producer, source-page fetch or model execution is added. Document the prerequisite in the existing Pages section because it answers that section's current workflow question. Preserve all earlier complete row sections and unresolved generation/publication outcomes.
- **Rejected alternatives:** Bypassing Pydantic or native validation would hide invalid configuration. Expanding the shared publication runtime without a demonstrated dependency boundary would widen this repair. Prompt/model/cap changes and manufactured visual outputs cannot prove this build prerequisite or close generation.

## 9. Row #8 - Restrict requested labels to usable native references

- **Scope:** Retain the delivered printed candidate, date and citation-address restrictions for one native Article; row #9 removes range request specialization with its unused producers.
- **Files touched:**
  - `backend/idhazh/classify/label_request.py` (new; owns the bounded request projection)
  - `backend/idhazh/classify/calls.py`
  - `backend/tests/test_label_request.py` (new focused request/anchoring cases)
  - `backend/tests/test_classify.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `tests/fixtures/planner/recorded-call-payloads.json` (first request schema only)
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
  - `docs/reference/retained-article-verification.md` (coordinator correction to the native provenance filename)
  - `TODO/20261110-restore-visual-publication-plan.md`
- **Acceptance gates:** Use the shared selector and the smallest applicable lint, strict-type, request, anchoring and historical-reading cases; CI owns the complete suite. Compile the actual projected request through the pinned runtime's native C++ schema converter and stock complete-object grammar validator without loading model weights. Inspect the validator's explicit verdict rather than its exit code alone. Measure dense source-cap schema/grammar size, compilation/initialization and peak memory separately from prompt capacity, using the current configured extraction cap. Keep those manual native receipts outside the repository; no test downloads, new dependencies, fixtures, parser or inference engine.
- **Oracle:** The projected current request offers only printed candidate ids, printed DATE ids or the native empty string for time, and printed sentence ids for citations. Exact source anchoring and empty selections remain valid. Row #9 removes the old range-production oracle and retains only strict historical range-structure/bounds validation; current native shape and budgets follow Table S.

Table Q - Native request projection decisions

| ID | Decision | Authority |
| --- | --- | --- |
| Q1 | Keep a thin request wrapper beside the native label builder and put projection mechanics in a focused sibling without importing the builder back into it | Native request projection precedent and module boundary |
| Q2 | Bind label ids to printed candidates, time ids to printed DATE elements plus the native empty string, and current citation addresses to printed sentence ids. Only code-minted addresses enter the grammar | Existing source-span and trust contracts |
| Q3 | Range endpoint specialization is retired with the claim/quote producer; the saved legacy validator checks old structures and bounds without reconstructing a current range menu | Table S |
| Q4 | Preserve empty lists and well-formed unreachable definitions when a pool is empty. Do not invent sentinels, force coverage or silently change the empty-source presentation | Native reply and source-presentation contracts |
| Q5 | Keep current `Citation`, exact anchoring, sanitizer, finalized menu, model/runtime, effective caps/context/timeout, admission and fallback unchanged. Row #9 changes the native label shape and derives its budgets anew, while strict legacy reading and existing capture envelopes remain compatible | Tables B6 and S |
| Q6 | Exercise actual pinned native grammar acceptance, not only JSON Schema validation or one sampled valid reply. Treat any schema factoring as unproved until equivalent native enforcement is demonstrated | Runtime/model boundary |
| Q7 | After the real producer increment, use the existing retained-input path for a fresh bounded observation on the named controls. Record both actual request token counts and prefix continuity, source/current identities, native products and actual usefulness. A timeout supplies no missing second-call evidence | Tables H and J |
| Q8 | Legal references do not prove useful numeric generation. Keep C3 pending until a useful native numeric output and ordinary publication are observed; no quota, third call, decline retry or precise-fragment substitution | Table J |

Table R - Rejected projection shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| R1 | Add prompt wording instead of keeping reference membership structural | Guidance cannot prevent unknown ids | Another semantic change without enforcing the printed menu | Table Q |
| R2 | Replace native readers with the article-specific request schema | Historical replies are not governed by today's article choices | A saved-format compatibility break and Level 5 design decision | Table Q5 |
| R3 | Claim restoration from zero invalid references or green grammar tests | Valid selections can still decline every numeric visual | Continued absence of actual positive generation and publication evidence | Table Q8 |

## 10. Row #9 - Retire the actor-grid and unused label work

- **Scope:** Remove active actor-grid generation, compilation, publication, rendering, UI state, guidance and dedicated evidence while keeping numeric charts, strict historical reading and truthful outcome records.
- **Files touched - delete:**
  - `backend/idhazh/contracts/whowhat_grid.py`
  - `backend/idhazh/render/whowhat_grid.py`
  - `backend/tests/contracts/test_whowhat_grid.py`
  - `backend/tests/pipeline/test_published_whowhat_grids.py`
  - `backend/tests/test_whowhat_grid.py`
  - `frontend/src/lib/visual/WhowhatVisual.svelte`
  - `frontend/src/lib/visual/whowhat-state.ts`
  - `frontend/src/lib/payload/whowhat-grid.ts`
  - `frontend/tests/whowhat-visual.spec.ts`
  - `tests/fixtures/contracts/whowhat-grid/whowhat.json`
  - `tests/fixtures/visual-validator/articles/whowhat.txt`
  - `tests/fixtures/visual-validator/plans/whowhat.json`
  - `tests/fixtures/visual-validator/tables/whowhat.json`
- **Files touched - dependencies and compatibility:**
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `backend/idhazh/contracts/visual_decision.py`
  - `backend/idhazh/contracts/visual_type.py`
  - `backend/idhazh/contracts/digest_day.py`
  - `backend/idhazh/contracts/digest_view.py`
  - `backend/idhazh/visual_vocabulary.py`
  - `backend/idhazh/visual_planner.py`
  - `backend/idhazh/visual_validator.py`
  - `backend/idhazh/render/__init__.py`
  - `backend/idhazh/render/write.py`
  - `backend/idhazh/stages/two_calls.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/label_request.py`
  - `backend/idhazh/classify/plan_visual_request.py`
  - `backend/idhazh/config.py`
  - `backend/utilities/build_canary_day.py`
  - `backend/utilities/measure_two_calls.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_served_day.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `backend/tests/contracts/test_visual_plan.py`
  - `backend/tests/contracts/test_visual_outcomes.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_chart_bubble.py`
  - `backend/tests/test_chart_scatter.py`
  - `backend/tests/test_chart_text_fit.py`
  - `backend/tests/test_chart_evidence.py`
  - `backend/tests/test_derived_values.py`
  - `backend/tests/support/visual_plans.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_label_request.py`
  - `backend/tests/test_measure_two_calls.py`
  - `backend/tests/test_prompt_files.py`
  - `backend/tests/test_render.py`
  - `backend/tests/test_replay_article_calls.py`
  - `backend/tests/test_visual_attempt_report.py`
  - `backend/tests/test_visual_attempts.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_visual_validator.py`
  - `frontend/scripts/test-groups.ts`
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/src/lib/components/DigestItem.svelte`
  - `frontend/src/lib/payload/types.ts`
  - `frontend/src/lib/payload/project.ts`
  - `frontend/src/lib/assist/day.ts`
  - `frontend/tests/item-visual.spec.ts`
  - `frontend/tests/reading-page.spec.ts`
  - `frontend/tests/served-day.spec.ts`
  - `frontend/tests/payload-state.spec.ts`
  - `frontend/tests/support/day-loader.ts`
  - `frontend/tests/visual-legibility.spec.ts`
  - `config/idhazh.json`
  - `config/prompts/generate-labels.txt`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/prompts/label.txt`
  - `tests/fixtures/prompts/summarize-and-plan.txt`
  - `tests/fixtures/planner/recorded-call-payloads.json` (current request expectations only)
  - `README.md`
  - `docs/architecture/extraction/elements.md`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
  - `docs/concepts/design-system.md`
  - `docs/concepts/digest.md`
  - `docs/concepts/telemetry.md`
  - `docs/reference/github-actions.md`
  - `docs/reference/retained-article-verification.md`
  - `TODO/20261110-restore-visual-publication-plan.md`
- **Acceptance gates:** Inspect the shared selector and run the smallest selected native unit/contract/integration checks, applicable lint and strict types locally; exact-head CI owns the full suite. Update existing tests with minimal in-memory literals, no new fixtures/mocks/network/dependencies/workflow-text tests. Verify the current decoder cannot request retired forms even with selection policy off; current labels have exactly four consumed fields; valid legacy labels load but malformed retired fields and unrelated unknown keys still fail before continuation replay. Preserve serialized numeric worker -> ordinary assembly -> asset/inventory -> TypeScript reader and valid-decline coverage. Use one integrated-browser numeric phone journey with navigation, reload, a cross-page smoke and missing/empty numeric data degradation. Review the retained surface once with synthetic/compiler numeric data; stop scoped preview helpers. Open one removal PR; do not merge or dispatch a workflow.
- **Oracle:** Current request/producer/renderer paths support only nine numeric types or no visual, while a legacy actor decision retains its requested/delivered/state/marks/identity facts but produces no view in backend projection, TypeScript projection or cached-day ingestion. Absent/null historical kinds still follow the chart path. Strict legacy label parsing validates retired field structure and bounds before discarding them, so removing unconsumed output cannot turn malformed historical replies into accepted evidence or replay unvalidated raw bytes. This proves retirement, compatibility and numeric transport, not present-day positive numeric generation.

Table S - Retirement contract and order

| ID | Decision | Authority |
| --- | --- | --- |
| S1 | Abandon `whowhat` rather than disable it. Delete the dedicated feature contract/compiler/reader/state/tests/fixtures/canary and its rules, guides, routing, flags and selection. Offer only the implemented numeric types in defaults, effective selection and all request schemas | Tables A and B; canonical visual capability contract |
| S2 | Reader before writer: remove the nested grid feature contract through a named legacy decision migration, preserving all historical outcome metadata. Retain only inert type/kind tokens and historical ledger family mapping; do not rewrite old records as declines or edit captures | Native persisted consumers and strict compatibility boundary |
| S3 | Project historical actor pointers to no visual at backend, staged TypeScript and cached-day browser boundaries. Positive chart selection prevents retired kinds falling through. Absent/null historical kinds remain legacy charts | Native served-day projection parity |
| S4 | Current label output contains only `labels`, `proposed`, `entity_mentions` and `place_mentions`. Delete unused range producers/request specialization and exclusive bounds/tests; retain strict read-only legacy label DTO validation before discard/replay and reject unrelated unknown keys | Current numeric consumers and raw continuation replay boundary |
| S5 | Recompute `ANCHORED_MAX`, widest label shape and shape-derived label/context budgets. Stamp/changelog `VisualDecision`, `AppConfig`, `DigestDay`, `DigestView`, `VIEW_VERSION`, planning vocabulary and label pass; keep numeric data/renderer/unit-table versions and effective configured caps/context/timeout unchanged | Native shape-derived budget and compatibility rules |
| S6 | Preserve numeric entity/place/category/time/series/relationship evidence, exact anchoring, chart validation/source grounding/sanitizer, viewport lifecycle repair, atomic paths, replay input checks and private render/capture isolation | Existing numeric behavior and safety boundaries |
| S7 | Carry one coherent removal PR, optionally two behavioral commits: actor retirement plus compatibility, then unused label work. Preserve every unrelated complete section/status and leave actual numeric generation/publication pending | Tables C and J |

Table T - Rejected retirement shortcuts

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T1 | Keep a disabled grid implementation or retain unconsumed range output | It leaves the abandoned capability and its maintenance/runtime cost in place | Continued feature contracts, prompts, code, tests and response/context work without a consumer | Table S1 and S4 |
| T2 | Drop four arbitrary legacy raw values before parsing | Malformed old replies could become accepted evidence and the continuation replays the first raw reply | A weakened trust/compatibility boundary; validate the retired structure and bounds first instead | Table S4 |
| T3 | Delete historical enum facts, broadly ignore unknown keys or rewrite actor outcomes as declines | It loses real persisted meaning and conceals malformed input | A history rewrite or unrelated acceptance-policy change | Table S2 |
| T4 | Repair numeric generation, change prompts' placement/model/runtime, enable fallback, redraw history or dispatch production | None is needed to remove the actor-grid | Coupled experiments, production side effects and an unverified claim that numeric generation is restored | Tables B and J |
