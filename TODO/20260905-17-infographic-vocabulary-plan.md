# 17 - The rest of the infographics

**Last Updated**: 2026-09-05
**Level**: 3 (three typeset templates and the compiler rule that lets a real sentence fit a card)

**Chain**: previous [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md) | next [`20260905-18-diagram-vocabulary-plan.md`](20260905-18-diagram-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - rows 40, 41, 42, section 4.F, 12.11 G18, 12.13 G33, 14.3, P.L28, P.L33, P.R20.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Some stories carry no series and no breakdown, only one striking figure, a set of actors, or a handful of takeaways. These three types cover them - and the family needs one compiler rule first, because a real sentence is rarely card-shaped |
| Hard scope - in | Deterministic truncation in the compiler; `callout` under a three-part gate; `whowhat` as a one-attribute grid; `keyfacts` with a per-item gate and a pre-committed kill criterion |
| Hard scope - out | Diagrams. Any change to `key_points`, which is a summary field and a different thing from the `keyfacts` infographic. Any model rewriting of text - the compiler shortens, the model never re-words |
| ESCALATE triggers | 1. Truncation is proposed as "let the model tidy the wording slightly" - it will sound reasonable every single time and it is the thing this row exists to refuse. 2. `callout` fires on a figure whose significance rests on our own sort order. 3. `keyfacts` cannot compute its per-item gate on committed data, which would make its kill criterion unfireable |
| Chosen strategy | Build the pressure valve first, then the three types, each with a gate that can fire without a model call and without human labels |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A real sentence made to fit, without anyone re-writing it | - | A | PENDING | - | - | - |
| 2 | One striking figure: callout | 1 | B | PENDING | - | - | - |
| 3 | Who did what: whowhat | 2 | C | PENDING | - | - | - |
| 4 | Three to five takeaways, and the switch that kills them | 3 | D | PENDING | - | - | - |

---

## 2. Row #1 - A real sentence made to fit, without anyone re-writing it

- **Scope:** Where a claim or quote must be shortened to fit a card, the compiler truncates deterministically with an ellipsis. The model never rewrites.
- **Files touched:** the compiler module under `frontend/src/lib/charts/` or its backend counterpart, `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `schemas/app-config.schema.json`, `tests/fixtures/**`, `frontend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `npm run check`; build; the browser suite.
- **Oracle:** Truncating the same claim twice gives the identical string, and the truncated string is a **prefix** of the element's own span text - so no character a reader sees came from anywhere but the article.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A cap rejects; truncation renders.** `summarize.max_verbatim_words` is 20 and is a summary anti-copying cap, so nothing today says what happens to a 40-word claim a plan picked for a card | 12.11 G18, section 14.3 |
| 2 | The valve got **more** necessary, not less: plan 11 made quotes and claims sentence-index-only, which is a better guarantee and yields **whole sentences** - precisely the input truncation exists to handle | 12.11 G18 |
| 3 | "Let it tidy the wording slightly" is refused now, in writing, because it will sound reasonable every time it is proposed | P.L32, 12.11 G18 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let the model shorten the sentence | It becomes the last unguarded prose channel, and nothing can check a re-worded claim against the article | Andre |
| 2 | Refuse anything that does not fit | Real sentences are rarely card-shaped, so the family would almost never fire | Editor |

---

## 3. Row #2 - One striking figure: callout

- **Scope:** `callout` under a three-part gate, all of it checkable with no model call.
- **Files touched:** `frontend/src/lib/charts/types/callout.ts` or a typeset component, `backend/idhazh/contracts/visual.py`, `config/idhazh.json` (the qualifier list and its version), `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; both floors; the section 12 smoke.
- **Oracle:** Four fixtures: one passing each admissible branch of the gate, and one where the only significance signal is our own ranking - which must be **refused**. The refusal case is the one that matters.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The gate: primary class is `singular`; the figure is carried by our own title or standfirst; **and either** a span-anchored significance qualifier from a versioned list within one sentence, **or** the figure is the only quantity in the article | Row 40, Editor |
| 2 | **"Only" is admitted where "biggest" is refused.** Biggest is a fact about our sort order, not about the world | Row 40 |
| 3 | The qualifier list is versioned config, so a later change to what counts as significant is visible in the record | Rule #6 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let the model judge which figure is striking | The judgement is the whole risk, and it is unverifiable | Editor, P.R20 |
| 2 | Fire on the largest number in the article | States a significance the article did not | Editor |

---

## 4. Row #3 - Who did what: whowhat

- **Scope:** `whowhat` as a one-attribute `comparison` grid rather than a separate template.
- **Files touched:** `frontend/src/lib/charts/types/whowhat.ts` or a `comparison` variant, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 2.
- **Oracle:** Every filled cell pairs an entity span and a claim span **from the same sentence**, re-sliced from the article in the test; a cell that cannot is empty rather than filled from elsewhere.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It ships as a variant of `comparison`, not a new template. One grid engine, two purposes | Row 41 |
| 2 | The same-sentence rule is what stops the grid asserting that an actor said a thing they did not | Row 41 |
| 3 | Rectangularity is already stated on the base type in plan 15, so this row inherits it rather than restating it | 12.13 G33, plan 15 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A bespoke actor-role template | A second grid engine for one purpose, against a design system that refuses per-page bespoke components | Jony |

---

## 5. Row #4 - Three to five takeaways, and the switch that kills them

- **Scope:** `keyfacts` with a per-item gate and a pre-committed kill criterion.
- **Files touched:** `frontend/src/lib/charts/types/keyfacts.ts`, `backend/idhazh/contracts/visual.py`, `backend/idhazh/evals/metrics.py`, `config/idhazh.json`, `frontend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** as row 2, plus `ruff`, `mypy --strict`, export + drift.
- **Oracle:** `keyfacts` **does not render** on an item whose new-fact rate is below the configured floor - asserted with a fixture pair straddling the floor. And the kill criterion is written into the doc as a number, so it can fire without a fresh argument.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Four personas voted to kill this type and Andre's diagnosis overruled them, because they aimed at the wrong target.** `key_points` is the summary field nobody proposed removing; `keyfacts` is the infographic that draws them bigger. The 7-in-8 restatement rate is a **prompt** defect, and plan 07 fixed it | Row 42, section 4.F |
| 2 | The veto becomes a **per-item gate**: `keyfacts` may not render on an item whose new-fact rate is below the floor. Machine-checkable on committed data, needs no labels, and it is what "a visual is earned, never granted" means | Row 42, O21 |
| 3 | A type-level veto could not fire without human labels, which is why the objection could not be settled before | Row 42 |
| 4 | Reader's objection is recorded rather than erased: a 3-to-5 bullet box beside a summary that already carries key points is the same thing printed twice - **which is exactly what the per-item gate refuses** | Section 4.F |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Kill the type | The four vetoes were aimed at `key_points`, a different thing, and the measured defect was in the prompt | Andre, row 42 |
| 2 | Ship it ungated | Then it draws the summary twice on the items where it least helps | Reader |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md) - the previous plan.
- [`20260905-18-diagram-vocabulary-plan.md`](20260905-18-diagram-vocabulary-plan.md) - the next plan.
- [`20260905-07-better-summaries-plan.md`](20260905-07-better-summaries-plan.md) - where the new-fact rate this plan gates on was built.
