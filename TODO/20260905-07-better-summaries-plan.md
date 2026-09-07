# 07 - Better summaries

**Last Updated**: 2026-09-05
**Level**: 3 (the summary prompt and its decode order, a contract field move, a new instrument, and an offline tool)

**Chain**: previous [`20260905-06-fewer-better-articles-plan.md`](20260905-06-fewer-better-articles-plan.md) | next [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O28, O33, section 10.4, 10.5, 14.4d, 16.2, 16.5.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Summaries are extractive, they pad, and a key point restates the summary seven times in eight. This is very likely the largest reader-visible win in the whole programme, and it is a **prompt** defect, not a model-capability defect - the evidence is mechanical and is in section 10.5 |
| Hard scope - in | Key points decoded before the prose; `key_points_max` moved onto the band; a restating key point dropped rather than the item failed; the new-fact rate as an instrument; the offline prompt-iteration loop and its deterministic gate |
| Hard scope - out | Fine-tuning (a separate plan-doc). Any change to the model entry. Any use of a model to judge **published** output - the loop judges a candidate prompt at development time and nothing it produces reaches a reader |
| ESCALATE triggers | 1. The loop would run in the daily pipeline rather than on a manual dispatch. 2. A candidate prompt wins on the model judge while losing on the deterministic scorers - the deterministic suite disposes and a disagreement is a stop. 3. Best-of-N selection against the new-fact rate is proposed - that is the Goodhart form of this exact metric and it destroys the instrument |
| Chosen strategy | Fix the structure first, measure second, and only then iterate the wording. Fine-tuning or a model swap before the prompt fix trains a model to reproduce a prompt defect |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Read this before dispatching row 5.** Plan 11 changes what the summariser reads - an article plus an anchored element table rather than an article. **The harness, the frozen set, the rubric and the deterministic gate all survive that; the prompt text and its numbers do not.** Label everything this plan measures a **baseline**, not a result. Its value is that plan 11's cutover has a tuned baseline to be judged against - run the loop only after plan 11 and you can never tell whether the architecture helped or the wording did.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The facts are found before the prose that connects them | - | A | DONE | - | #474 | w1 |
| 2 | A short article stops being asked for five key points | - | A | PENDING | - | - | - |
| 3 | A restating key point is dropped, not the item | 1, 2 | B | PENDING | - | - | - |
| 4 | How often a key point says something new | 3 | C | PENDING | - | - | - |
| 5 | The prompt stops being argued about and starts being measured | 4 | D | PENDING | - | - | - |

---

## 2. Row #1 - The facts are found before the prose that connects them

- **Scope:** `key_points` decodes **before** `summary` in the reply schema, so the model finds facts first and writes prose that connects them.
- **Files touched:** `backend/idhazh/summarize.py`, `backend/idhazh/prompts/summarize.txt`, `backend/idhazh/contracts/summary.py` if the draft shape moves, `schemas/summary.schema.json`, `tests/fixtures/contracts/summary/*.json`, `backend/tests/test_summarize.py`, `docs/architecture/summarize/prompt.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; a replay over the committed canary corpus.
- **Oracle:** A contract test asserts `key_points` precedes `summary` in the **generated schema's** property order, because the decoder follows that order and nothing else pins it. Plus: over the frozen set, the new-fact rate does not fall.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Decode order is the defect. Asking a model to write something **unlike** the text it has just written is the least likely continuation | Section 10.5 |
| 2 | The reply's property order is load-bearing and is asserted, not assumed. llama.cpp's order-preserving grammar is not something this project pins | E5's obligation, applied here |
| 3 | This ordering survives plan 11: call 2 still decodes `summary` before `visual`, and the order **inside** `summary` is untouched | Andre, 2026-09-05 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ask for key points in a second call | Doubles the model work for a field reorder | Carmack |
| 2 | Strengthen the instruction and leave the order | The instruction is already there and the rate is 7 in 8. Order beats exhortation | Andre |

---

## 3. Row #2 - A short article stops being asked for five key points

- **Scope:** `key_points_max` moves from `SummarizeConfig` onto `SummaryBand`, so the shortest band asks for fewer.
- **Files touched:** `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/idhazh/summarize.py`, `frontend/src/lib/server/config.ts`, `backend/tests/test_contracts.py`, `backend/tests/test_corpus.py`, `backend/tests/test_qualify.py`, `docs/architecture/summarize/prompt.md`, `docs/concepts/config.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `bundle-gate`.
- **Oracle:** For every band, the requested key-point count is less than or equal to the count of distinct facts the band's own word budget can carry - asserted per band, so a future band cannot be added at five by accident.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Redundancy is structurally guaranteed at the shortest band today.** `key_points_max` is 5 for every band, so a 40-word summary of a 60-word post is asked for five key points on top of it. That is a request for facts that are not in the article | Section 10.5, verified 2026-09-05 |
| 2 | A band change **is** a published-site change: `/console/` reads `summarize.bands` at build time, so section 12 applies even though no frontend file is edited | Recorded trap |
| 3 | Derive every band-count assertion from `SUMMARIZE.bands`, never from a hardcoded index. Three test files pin "the top tier is band N" and only the full suite finds them | Recorded trap |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Lower `key_points_max` globally | The longest band genuinely carries five, and lowering it there loses real facts | Editor |

---

## 4. Row #3 - A restating key point is dropped, not the item

- **Scope:** A deterministic check in `to_summary` that removes a key point which restates the summary, with the ceiling in `config/`.
- **Files touched:** `backend/idhazh/summarize.py`, `backend/idhazh/evals/metrics.py`, `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `schemas/app-config.schema.json`, `tests/fixtures/contracts/app-config/tuned.json`, `backend/tests/test_summarize.py`, `docs/architecture/summarize/prompt.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A reply whose every key point restates the summary publishes the item with **fewer key points**, not a failure code. The item is never lost to this check - that is the whole difference from a rejection.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is the `verbatim_run` pattern the codebase already uses: a deterministic post-check with a config ceiling, dropping the offending part rather than the item | Section 10.5 |
| 2 | "Restates" must be computable. An instruction saying a restating key point is a wasted line gives the model no definition it can apply | Section 10.5 |
| 3 | The rule is a **floor on distinctness**, not a word ban. A key point may share words with the summary and still add a fact | Editor |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fail the item | Degrade, do not fail. A restating key point is a thin line, not a wrong one | CLAUDE.md section 1a |

---

## 5. Row #4 - How often a key point says something new

- **Scope:** The new-fact rate - the share of key points stating a fact the summary does not contain - computed per band and published to the console.
- **Files touched:** `backend/idhazh/evals/metrics.py`, `backend/idhazh/contracts/eval_row.py` or the public projection, `schemas/*.schema.json`, `frontend/src/routes/console/model/**`, `backend/tests/test_metrics.py`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `npm run check`; build; `bundle-gate`; the browser suite.
- **Oracle:** Recomputing the rate over the committed corpus reproduces the recorded baseline, and the baseline is reported **per band** - a single figure pools the band where redundancy is structural with the band where it is not.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Baseline to beat: **11 of 89, 12.4 percent**, from section 10.5. Re-measure it before quoting it | Section 10.5 |
| 2 | **Never use this rate to select.** Best-of-N against it produces key points optimised for lexical difference, which is the Goodhart form of this exact metric, and the alarm then stops detecting the thing it was built for | Section 10.5, standing trap |
| 3 | Plan 08 unlocks a strictly better version - element-id disjointness, with no lexical false positives. This row builds the lexical one and says so in its docstring | Section 10.5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Wait for plan 08's element ids | Then rows 1 to 3 ship with nothing measuring whether they worked | Andre |

---

## 6. Row #5 - The prompt stops being argued about and starts being measured

- **Scope:** An offline write-critique-revise loop bounded by `finetune.prompt_iterations`, judged by two judges and **gated by the deterministic scorers**, run on a developer machine or a manual dispatch.
- **Files touched:** `backend/utilities/prompt_loop.py` (new), `backend/idhazh/prompts/summarize.txt`, `backend/idhazh/evals/metrics.py`, `config/idhazh.json`, `CLAUDE.md` (section 0a amendment), `backend/tests/test_prompt_loop.py`, `docs/concepts/evaluation.md`, `docs/how-to/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the loop run end to end on the committed canary corpus with no network.
- **Oracle:** A candidate prompt is promoted **only** when it beats the incumbent on `unsupported_number`, `lead_missing` and `hedge_dropped` over the frozen set. A run where the model judge prefers a candidate the deterministic suite refuses must end with the incumbent still in place, and that arm is asserted.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `CLAUDE.md` section 0a is amended in the same commit, narrowly: offline prompt iteration is permitted; a model judging a **published** summary or visual, or selecting what publishes, stays banned | O28, E1 |
| 2 | **The gate is deterministic, not the judge.** The model judge proposes; the deterministic suite disposes | O28 |
| 3 | The three steering targets are model-free, need no labels, and are computable on committed data today. HHEM is the slow backstop, not the steering wheel | O33, section 14.4d |
| 4 | A regex cross-check of `unsupported_number` against the source ships with it. That tests **the checker**, and nothing has ever verified the checker | O33 |
| 5 | **No hard word limits in the rubric.** `summarize.bands` already sizes prose by source length; the rubric judges whether a line earns its place | Owner, section 16.2 |
| 6 | Two judges, not one. A single judge sharing the writer's failure modes is the thing section 0a warns about; two disagreeing judges surface it | O28 |
| 7 | Committed: the winning prompt, the rubric, every candidate's scores and the seed. Not the transcripts | O28 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Steer by HHEM | Slow, needs the scorer, and it cannot see a dropped hedge or a missing lead at all | Owner, O33 |
| 2 | Run the loop inside the daily pipeline | It is development-time tooling and would put a model judge on the critical path | Andre |
| 3 | Swap the model first | Re-run the same twenty items on the same weights through the fixed prompt first. Fine-tuning before the prompt fix trains a model to reproduce a prompt defect | Section 10.5 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-06-fewer-better-articles-plan.md`](20260905-06-fewer-better-articles-plan.md) - the previous plan.
- [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) - the next plan.
