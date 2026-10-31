# 20 - The operator can see whether it worked

**Last Updated**: 2026-10-31
**Level**: 3 (operator console over committed telemetry)

**Chain**: previous [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md) | next [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O11, O34, rows 49, 56, 70, sections 12.6 G3, 12.7 G9, 12.9 G14, G15, 12.12 G23, 12.13 G30, G39, 12.14 G43, 14.5.

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 19 records every visual attempt. This plan gives operators console views of pipeline progress, refusals, and requested versus written visual types without adding measurements |
| Hard scope - in | The two funnels in row 1 and the two views in row 2, using existing committed records |
| Hard scope - out | Human review (plan 21), new telemetry collection or ledger fields, alarms, retirement criteria, and publication gates |
| ESCALATE triggers | 1. A human-review surface or verdict is added. 2. New telemetry collection or a ledger field is proposed. 3. A metric is proposed as a publication gate |
| Chosen strategy | Build the four console views from existing records; add no telemetry collection, human judgments, or publication decisions |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The two funnels | - | A | PENDING | - | - | - |
| 2 | Refusal reasons and written visual type | 1 | B | PENDING | - | - | - |
| 3 | The rules for reading any of it | 2 | C | COLLAPSED (maintainer, 2026-10-31: row 1 owns its denominator rules; revised row 2 adds no human keep rate, family distribution, alarm, or composite score) | - | - | - |
| 4 | How each feature gets retired without a fresh argument | 3 | D | COLLAPSED (maintainer, 2026-10-31: `keyfacts` is no longer generated; the downgrade ladder is disabled and its keep-rate evidence is unavailable) | - | - | - |

---

## 2. Row #1 - The two funnels

- **Scope:** The pipeline funnel per potential class, and the downgrade funnel end to end.
- **Files touched:** `frontend/src/lib/server/payload.ts`, `frontend/src/routes/console/**`, `frontend/src/lib/console/**`, `config/idhazh.json` (the ceiling this grows), `frontend/tests/console-visual-*.spec.ts` (new), `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; the section 12 smoke including a truncated-ledger check.
- **Oracle:** Each funnel's stages are re-derived in the spec from the committed ledger and compared to the drawn values, and the stages are **monotonic or the non-monotonic case is drawn explicitly** - committed chart counts are already known not to be monotonic per day, so a funnel that assumes it will lie.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These two were ranked first in the source document's own build order and appeared in **no** panel list. The downgrade funnel is the one panel that renders the refusal reason end to end; the pipeline funnel is the only panel the per-class denominator ever reaches | 12.9 G14 |
| 2 | Every rate is reported **per potential class**. Without a denominator of what was possible, 4 percent on narrative and 4 percent on chartable are the same number | Row 56 |
| 3 | Panels name the current three classes. The two additional classes are [deferred with diagrams](../docs/architecture/publishing/visuals.md#diagrams-deferred), not a prerequisite for this plan | Current visual scope |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One combined funnel | Pools the reason a visual was never attempted with the reason one was refused, which are different failures with different fixes | Andre |

---

## 3. Row #2 - Refusal reasons and written visual type

- **Scope:** Show recorded refusal reasons over time and compare the planned visual type with the type successfully written. Read the existing Plan 19 attempt records; add no human keep-rate measure, cross-day repetition measure, or single-type-day defect.
- **Files touched:** as row 1. No backend contract or ledger changes.
- **Acceptance gates:** as row 1.
- **Oracle:** Against named fixtures, refusal counts by UTC date and `planned_type` to `rendered_type` counts match calculations from the existing `visual-design-attempts` rows. `rendered_type` means successfully written, not necessarily published. Missing or truncated records remain visibly incomplete under row 1's reader rules.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Reuse the existing `visual-design-attempts` records. `rejection_reason`, `planned_type`, and `rendered_type` provide this row's evidence; add no ledger, column, or producer logic | Plan 19; maintainer ruling, 2026-10-31 |
| 2 | Keep rate by downgrade depth is not part of this plan. It needs linked human verdicts and a depth actually selected; this row creates no human review surface | Maintainer ruling, 2026-10-31 |
| 3 | Do not add a cross-day repetition fingerprint or metric | Maintainer ruling, 2026-10-31 |
| 4 | A day with one successfully written visual type is not a defect and is not alarmed | Maintainer ruling, 2026-10-31 |

---

## 4. Row #3 - The rules for reading any of it

**Status: COLLAPSED.** Row 1 defines the funnel populations. Revised row 2 adds no human keep rate, family distribution, alarm, or composite score that needs a separate reading rule. Human review remains in plan 21. Existing project rules remain in force; this plan adds no documentation, console code, or tests for this row.

---

## 5. Row #4 - How each feature gets retired without a fresh argument

**Status: COLLAPSED.** `keyfacts` is no longer generated. The downgrade ladder is disabled, and its proposed retirement test needs human keep verdicts by selected depth that are not available in this plan. There is no active feature or evidence for a retirement threshold. If either feature is reintroduced, define a measurable criterion in a new plan row.

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md) - the previous plan.
- [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md) - the next plan.
