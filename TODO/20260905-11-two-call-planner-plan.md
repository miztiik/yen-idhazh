# 11 - One model, two calls

**Last Updated**: 2026-09-05
**Level**: 5 (the model pick, the trust boundary, and the call structure every later plan rests on)

**Chain**: previous [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) | next [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O3, O17, O37, O43, rows 4, 5, 9, 10, 11, 17, 50, sections 10.1, 10.1a, 10.1b, 10.2, 10.3, 10.3a, 10.6, 11.3, 11.4, 14.5, E5, 12.6 G1 G2 G4, 12.7 G8.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The visual is drafted today by a small model reading a lossy summary. This is the architectural change the whole group exists for: one capable model reads the **article**, labels what code already found, points at what code missed, and then summarises and plans against the elements rather than against prose. It also retires a whole model, a whole CI job and 2.33 GiB of cache |
| Hard scope - in | The planner module; call 1 and the four model-anchored element producers; call 2 appended to call 1's message array; the reachability gate; the downgrade ladder; retiring the small model with its job in the same commit as the flag flip; one chart drawn end to end |
| Hard scope - out | The renderer swap (plan 12). Any new visual type. Any human review surface. **A third call** - splitting call 2 into two requests needs a measured timeout rate first, and until that measurement exists it is out of scope, not open |
| ESCALATE triggers | 1. `cached_tokens` on call 2 is below call 1's prompt token count - the prompt was built in the wrong order and the whole cost model is wrong. 2. The worst shard passes 180 minutes against the 200-minute timeout. 3. A retry is proposed that perturbs nothing. 4. Any design that lets the model emit a character a reader sees |
| Chosen strategy | Behind a flag, off, until the whole path works - then one commit flips it, deletes the job and retires the role together. The small model may not retire before call 2 works, because call 2 is what replaces it |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Exactly two model calls per item. Always.** Call 1 labels; call 2 writes the summary **and** the plan. Call 2 runs for every item that publishes, because it is the call that writes the summary - a gate may suppress the plan fields inside it and may never skip it. The deterministic pass before call 1 is **the candidate pass**, never "call 0"; a document that spells three things "call" cannot say "two calls" and be counted.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Call 1 reads the article and points at it | - | A | PENDING | - | - | - |
| 2 | The four kinds only a model can find | 1 | B | PENDING | - | - | - |
| 3 | Call 2 summarises and plans, and the article is read once | 2 | C | PENDING | - | - | - |
| 4 | The gate that refuses before the plan is drafted, and the ladder that steps down | 3 | D | PENDING | - | - | - |
| 5 | One chart, drawn end to end | 4 | E | PENDING | - | - | - |
| 6 | The small model, its job and its cache go | 5 | F | PENDING | - | - | - |

---

## 2. Row #1 - Call 1 reads the article and points at it

- **Scope:** `visual_planner.py` builds call 1: the system rules, the title, the fenced article, and the candidate table indexed by `element_id`. The reply labels, proposes and names - and can emit no number at all.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/prompts/**`, `backend/idhazh/contracts/element.py`, `schemas/*.schema.json`, `backend/idhazh/cli.py`, `backend/tests/test_visual_planner.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a recorded-response replay with no network.
- **Oracle:** **No field of call 1's schema accepts a number, a span or a character offset.** Asserted against the generated schema, so authorship is impossible by grammar rather than caught by a check downstream. Plus: a reply citing an unknown `element_id` drops that label and keeps its siblings.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Extraction first, summary second.** Using a lossy summary as the planner's source is the defect that produced this whole design | Owner, overruling Andre; section 10 |
| 2 | Field order is decode order. Labels are committed **before** the type is chosen, or the reason becomes a rationalisation of a choice already made - measured on this codebase once | Row 12 |
| 3 | `proposed` is the escape hatch for a figure the regex missed: the model names a **sentence**, code searches only that sentence, demands exactly one hit, and re-parses value and unit from the article's own bytes. Stamped `extractor="model_proposed"`, capped per article | Section 10.1a |
| 4 | A spelled-out number and a relative change stay refused - there is nothing for code to parse | Section 10.1a |
| 5 | The accepted extra signals are salience, attribution type, hedge marker, keyphrases and lede/quote indices - about 140 output tokens, 12.5 minutes of shard wall clock at 20 items. Question-answer pairs, coreference, sentiment and embeddings are refused, each for its own reason | Section 10.6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | The model emits a verbatim surface for every element, adjudicated by exact search | A number the model types is a number the model authored. Exact search cannot tell a real number from a real number pointed at the wrong sentence | Andre, section 10.1a |
| 2 | Only the regex may discover a quantity | Closing authorship is right; closing discovery is not. The regex deletes the series a trend chart exists to show | Andre, section 10.1a |

---

## 3. Row #2 - The four kinds only a model can find

- **Scope:** The producers for `entity`, `place`, `quote` and `claim` - a different anchoring rule per kind.
- **Files touched:** `backend/idhazh/elements.py`, `backend/idhazh/visual_planner.py`, `backend/tests/test_elements.py`, `tests/fixtures/**`, `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** For every surviving element of every kind, `article.text[span_start:span_end] == span_excerpt`. **And** no element's drawn label is ever its Tier 2 `name` - asserted by checking that the label equals one of the element's surviving mentions.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An **entity name is never searched for.** An article writes "Vestas Wind Systems A/S" once and "Vestas" four times, and the canonical name may appear nowhere verbatim. The `name` is Tier 2 and a grouping key; the **mention** is Tier 1 and is what draws | Section 10.1a |
| 2 | Each mention's surface must occur **exactly once inside its own named sentence**. Ambiguity is a rejection rather than a coin toss. Zero surviving mentions drops the element | Section 10.1a |
| 3 | A quote or a claim is **sentence indices only, never text.** Exact search over a long string rejects a real quote over one changed word, silently, which is worse than no check | Section 10.1a |
| 4 | Every actor and object in an event or relation must resolve to a surviving entity element, or the row is dropped. An unanchored arrow is a claim the article did not make | Row 47 |
| 5 | A rejection is **per element, never per article** | Section 10.1b invariant 3 |
| 6 | Two failures no anchoring check can see are recorded rather than papered over: **mis-pointing** (the span is real, just the wrong one) and **mis-labelling** (right number, wrong meaning). This is Deviation A and it is accepted as permanent | O40, section 10.1a |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Exact search for every kind | Confuses a location with a label; it is precisely what a semantic model is good at and string matching is bad at | Andre |
| 2 | Model-supplied coreference chains | Exact and prefix matching over spans code already holds does most of it, and the model's version cannot be span-validated | Section 10.6 |

---

## 4. Row #3 - Call 2 summarises and plans, and the article is read once

- **Scope:** Call 2 appended to call 1's message array, emitting `{summary, visual}` in that order, with the output budget re-derived from the contract's own bounds.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/summarize.py`, `backend/idhazh/llm/server.py`, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/*.schema.json`, `backend/tests/**`, `docs/architecture/summarize/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; one dispatch reading `cached_tokens`.
- **Oracle:** Two assertions, because the two halves fail for different reasons. **The floor that must hold:** `cached_tokens` on call 2 is at least call 1's prompt token count - the system turn and the article are byte-identical and come first, so they prefill once or the prompt was built wrong. **The target that must be measured, not assumed:** whether call 1's *generated* tokens also cache, since call 2 re-renders them through the chat template. Record both.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The two calls are **adjacent per item**. `n_parallel` is 1, so there is one cache slot; running all call-1s then all call-2s evicts the prefix every time, with no error | Row 10 |
| 2 | Assert `cached_tokens`, never a `prefill_ms` ratio. A ratio confounds cache reuse with delta length and reads as partial success when the prompt was built in the wrong order | Row 11 |
| 3 | **The planner's source is the article and the element table, not the summary.** The summary is in context because decoding is autoregressive, so it *conditions* the plan; it cannot *source* it, because `element_ids` may cite only an anchored element | Section 10.3a |
| 4 | If `information_delta` collapses after the cutover, this ordering is the first suspect - a plan can drift toward illustrating the sentences | Section 10.3a |
| 5 | On a reply cut by the output budget, code recovers the closed `summary` object from the returned bytes and publishes the item with `decision = none`. Zero extra seconds, no second request. **A contract test asserts `summary` precedes `visual` in the generated schema**, because the recovery boundary is the property order | E5 |
| 6 | The output budget is **derived** from the contract's bounds, not picked, and re-derived whenever a bound changes | Row 13, section 11.3 |
| 7 | `context_exceeded` degrades to a **chunked read**, not to nothing. Element extraction is naturally chunkable because an element is local to its span | Row 20, section 11.4 |
| 8 | A retry must perturb the **input**. Where no input perturbation applies, do not retry - under greedy decoding a retry against identical input is bit-identical and costs a full decode | Row 17 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A different system prompt for call 2 | The common prefix would end at the template header and the whole article would re-prefill - roughly double | Section 10.2 |
| 2 | Three calls | Needs a measured timeout rate first. Out of scope until that measurement exists | O43, E5 |
| 3 | Temperature jitter on retry | Breaks the `seed: 0`, `temperature: 0.0` determinism contract - a re-run stops being a re-run | Row 17 |

---

## 5. Row #4 - The gate that refuses before the plan is drafted, and the ladder that steps down

- **Scope:** The reachability gate, `none_reason` as a typed enum, and the downgrade ladder with its four invariance rules.
- **Files touched:** `backend/idhazh/visual_planner.py`, `backend/idhazh/contracts/visual.py`, `schemas/*.schema.json`, `config/idhazh.json`, `backend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Every route to `none` carries a distinct `none_reason`, asserted by driving each gate independently and collecting the set - it must equal the enum exactly. A gate whose refusal is indistinguishable from another's leaves the largest number on the console explaining nothing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The gate suppresses the plan fields inside call 2; it never skips the call**, because call 2 writes the summary. What is saved is the plan's decode, not the call | O43, section 14.5 |
| 2 | The old "21 measured seconds" saving was for skipping a whole call, which cannot happen. **The figure is withdrawn** rather than re-used; the plan-decode saving is a different number and this row measures it | Section 14.5 |
| 3 | Four invariance rules on the ladder: element set unchanged, purpose survives, escalating floor, and **re-validation** - a downgraded plan re-enters the **same** validator and the **same** compiler, and a depth that fails falls to the next depth rather than publishing | Row 50, 12.7 G8 |
| 4 | Depths 2 and 3 need their percentiles named; the source document ships a ladder with one named rung | 12.6 G2 |
| 5 | A **static allow-list of legal downgrade edges**, or the ladder can walk a comparison into a timeline and record it as legal. The cross-family ban is what "purpose survives" implies and never states | 12.6 G4 |
| 6 | Floors are computed from depth-0 published visuals only | Row 50 |
| 7 | The ladder's kill criterion is pre-committed here: if downgraded visuals are kept materially less often than depth-0 ones, **the flag goes off and the ladder is deleted, not tuned** | 12.13 G30 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A repair retry instead of a ladder | Chosen against already, and it is why no validator failure re-calls the model | P.L7 |
| 2 | Let a downgrade skip re-validation | Then a downgrade can publish the thing the original plan was refused for | 12.7 G8 |

---

## 6. Row #5 - One chart, drawn end to end

- **Scope:** One `bar` rendered from a compiled plan through an inline SVG path, so this plan ends with something visible rather than a contract nobody can see.
- **Files touched:** `backend/idhazh/render/**`, `frontend/src/lib/components/ItemVisual.svelte`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the whole-day check from plan 01; the section 12 smoke.
- **Oracle:** A published item's drawn bar heights are re-derived in the test from the committed element table and compared to the drawn attributes - so the chart is proved to be showing the article's numbers rather than merely showing numbers.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This row exists because a plan contract with no rendered output delivers nothing a person can check. One type, end to end, is the smallest honest proof | Fowler, 2026-09-05 |
| 2 | It reuses plan 01's inline carrier rather than inventing a second one | Plan 01 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Wait for plan 12 to draw anything | Then plan 11 merges with no evidence the plan it emits can become a picture | Fowler |

---

## 7. Row #6 - The small model, its job and its cache go

- **Scope:** The flag flips, the small model's role leaves config, the CI job is deleted, the prompt file goes, and `finetune.student`/`teacher` are re-pointed - **all in one commit**.
- **Files touched:** `config/idhazh.json`, `.github/workflows/digest.yml`, `backend/idhazh/prompts/**`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_workflows.py`, `backend/tests/**`, `docs/**`
- **Acceptance gates:** the full suite; `shellcheck`; one dispatch of `digest.yml` end to end; `idhazh site-weight`.
- **Oracle:** The dispatched run completes with **no** job between `work` and `assemble`, the repo cache falls from roughly 82 percent of the 10 GB ceiling to roughly 57, and the worst shard stays under 180 minutes. Three independent numbers, because a retirement that only removes a config key has not retired anything.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The small model may not retire before call 2 works**, because call 2 is what replaces it. This is the last row for that reason | Carmack, 2026-09-05 |
| 2 | Retired completely: config entry, cache role, workflow job, env vars, prompt file, tests. **No half job** | O17 |
| 3 | `finetune.student` is `route` and `finetune.teacher` is `summarize` today - a distillation setup for the model being retired. That configuration is dead the moment this row lands and must be re-pointed in the same commit | Section 10.4 |
| 4 | `run.route_budget_minutes` is re-derived or deleted here. It exists because the old job ran 51 to 60 minutes against a 60-minute bound, and folding into `work` invalidates the number | Row 69 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Retire the model in an earlier plan | Nothing would draft a visual until this plan lands - a reader-visible regression for several plans | Carmack |
| 2 | Keep the small model as a fallback | A second model to keep qualified, cached and measured, for a path the design says is replaced | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) - the previous plan.
- [`20260905-12-readable-visuals-plan.md`](20260905-12-readable-visuals-plan.md) - the next plan.
