# 20 - The operator can see whether it worked

**Last Updated**: 2026-09-05
**Level**: 3 (operator surface, plus the rules that decide what may be alarmed and what may be killed)

**Chain**: previous [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md) | next [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O11, O34, rows 49, 56, 70, sections 12.6 G3, 12.7 G9, 12.9 G14, G15, 12.12 G23, 12.13 G30, G39, 12.14 G43, 14.5.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 19 records every attempt. This is what makes the record answerable: **the ability to tell whether the visual work worked at all.** Without it the group ends with a large committed ledger and no way to say whether the digest got better |
| Hard scope - in | The required panels; the rule that no measure is alarmed alone; the rule that the three families are never pooled; the guard against quoting an invented industry benchmark; and the pre-committed criteria for killing a feature |
| Hard scope - out | Any human review surface (plan 21). Any new metric - every number here is written by plan 19 or earlier. Any alarm threshold set from a guess |
| ESCALATE triggers | 1. A composite quality index is proposed as a **gate** rather than a diagnostic. 2. A panel pools chart, diagram and infographic types into one distribution. 3. A target is set from a figure quoted from outside this repository |
| Chosen strategy | Panels first so the numbers are visible, then the rules that constrain how they may be read, then the criteria that let a feature be retired without a fresh argument |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The ban that has to be stated rather than assumed.** The quality index is a **diagnostic and never a gate** - not until the correlation between the machine components and human keep rate has been measured. A composite of unvalidated components is a number that looks like a judgement. This was stated twice in the source document and carried into the plan-doc set only as the word "accepted", which reads as an oversight to fix rather than a rule to keep.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The two funnels | - | A | PENDING | - | - | - |
| 2 | Why it was refused, and what happened when it stepped down | 1 | B | PENDING | - | - | - |
| 3 | The rules for reading any of it | 2 | C | PENDING | - | - | - |
| 4 | How each feature gets retired without a fresh argument | 3 | D | PENDING | - | - | - |

---

## 2. Row #1 - The two funnels

- **Scope:** The pipeline funnel per potential class, and the downgrade funnel end to end.
- **Files touched:** `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/**`, `frontend/src/lib/console/**`, `config/idhazh.json` (the ceiling this grows), `frontend/tests/console-visual-*.spec.ts` (new), `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke including a truncated-ledger arm.
- **Oracle:** Each funnel's stages are re-derived in the spec from the committed ledger and compared to the drawn values, and the stages are **monotonic or the non-monotonic case is drawn explicitly** - committed chart counts are already known not to be monotonic per day, so a funnel that assumes it will lie.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These two were ranked first in the source document's own build order and appeared in **no** panel list. The downgrade funnel is the one panel that renders the refusal reason end to end; the pipeline funnel is the only panel the per-class denominator ever reaches | 12.9 G14 |
| 2 | Every rate is reported **per potential class**. Without a denominator of what was possible, 4 percent on narrative and 4 percent on chartable are the same number | Row 56 |
| 3 | The class set is five only after plan 18. Before that a panel names three and says so | O46 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One combined funnel | Pools the reason a visual was never attempted with the reason one was refused, which are different failures with different fixes | Andre |

---

## 3. Row #2 - Why it was refused, and what happened when it stepped down

- **Scope:** Rejection reason over time; keep rate by downgrade depth; `planned_type` against `rendered_type`; and the cross-day repetition instrument.
- **Files touched:** as row 1, plus `backend/idhazh/contracts/visual_telemetry.py` if the repetition fingerprint needs a column
- **Acceptance gates:** as row 1, plus `ruff`, `mypy --strict`, export + drift.
- **Oracle:** `visual_repetition_rate` is computed from a `(element set, type)` fingerprint over a rolling window and re-derived in the test. **The rule it enforces - a running story's visual repeats only when its numbers moved - is unenforceable without it, because nothing else computes whether they moved.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Cross-day repetition and within-day sameness are **different axes** and both are real. The source document closed the cross-day risk against the within-day rule, which is a closure against the wrong thing | 12.14 G43 |
| 2 | A day publishing a single rendered type is a recorded **defect**, read jointly with keep rate. It is not a diversity target | Row 49 |
| 3 | `planned_type` against `rendered_type` is what makes the vocabulary build order evidence rather than a guess | Row 48 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rely on the within-day diversity rule | Orthogonal axis. It cannot see the same visual five days running | 12.14 G43 |

---

## 4. Row #3 - The rules for reading any of it

- **Scope:** Three rules stated once, beside the panels they constrain.
- **Files touched:** `docs/concepts/evaluation.md`, `docs/architecture/publishing/frontend.md`, `frontend/src/lib/console/**` (where a rule is mechanical), `frontend/tests/**`
- **Acceptance gates:** `npm run check`; build; the browser suite; the full suite.
- **Oracle:** A test asserts that **no panel pools the three families into one distribution** - enumerated over the panel map, so a panel added later fails rather than being noticed by eye.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Never alarm on a measure that can be improved by giving up.** Every such measure is paired with a diversity or coverage counter. Stated as a **rule**, because a rule generates the next pair and three example panels do not | 12.9 G15 |
| 2 | **The three families are never blended.** A panel titled "type distribution" pooling a bar, a flow and a quote card is a reasonable thing to write, is uninterpretable, and nothing else would stop it | 12.12 G23 |
| 3 | **There is no published industry average for chart keep rate or any composite visual-quality score**, so any figure quoted from outside as a benchmark for them is quoting nothing. One sentence, and it stops a future target being set from a blog post | 12.13 G39 |
| 4 | The human loop is kept pointed at the output, never at the metrics - already honoured by the rule that a reviewer is never shown the machine's reasoning | 12.9 G15 |
| 5 | Every alarm ships **record-only**. An alarm set on a guess is worse than no alarm | M5 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Carry the rules as three example panels | A rule generates the next pair. The next metric added would get no counterweight and nobody would notice | 12.9 G15 |

---

## 5. Row #4 - How each feature gets retired without a fresh argument

- **Scope:** Pre-committed kill criteria, written as numbers, for the downgrade ladder and for `keyfacts`.
- **Files touched:** `docs/concepts/evaluation.md`, `config/idhazh.json` (the flags), `frontend/src/routes/console/**`, `backend/tests/**`
- **Acceptance gates:** `npm run check`; build; the browser suite; the full suite.
- **Oracle:** Each criterion is computable from the committed ledger today, asserted by computing it over fixtures and returning a verdict. **A kill criterion that cannot be computed is a promise, not a criterion.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The ladder's criterion: if downgraded visuals are kept materially less often than depth-0 ones, **the flag goes off and the ladder is deleted, not tuned.** A ladder carrying four invariance rules, two percentiles and an edge table is a substantial mechanism to maintain on faith | 12.13 G30 |
| 2 | `keyfacts` already has its per-item gate from plan 17; this row writes its type-level retirement number | Row 42 |
| 3 | Pre-committing now is cheaper than defending later, which is the source document's own reasoning and the reason `keyfacts` survived four vetoes | 12.13 G30 |
| 4 | The quality index stays a **diagnostic**. Weight fitting produces weights **for a diagnostic**, and it does not become a gate until `information_delta` is shown to predict keep rate | 12.7 G9 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Decide when the data arrives | Then the decision is made by whoever is most attached to the feature | Andre |
| 2 | Let the composite score gate publication | A composite of unvalidated components is a number that looks like a judgement | 12.7 G9 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md) - the previous plan.
- [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md) - the next plan.
