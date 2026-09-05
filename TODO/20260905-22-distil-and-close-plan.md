# 22 - Close it out

**Last Updated**: 2026-09-05
**Level**: 2 (documentation, and the deletion of two working documents)

**Chain**: previous [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md). **Last plan of the group.**
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the document this row deletes, and O40 in particular.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | `TODO/` is non-authoritative and dies at distill. Two working documents carry decisions, corrections, gap findings and measured numbers that nothing in `docs/` holds, and when they are deleted those facts go with them unless this plan moves them first. **A durable fact left only in a working document is a fact this project has decided to forget** |
| Hard scope - in | Moving every durable finding into the living doc that owns it; re-measuring the numbers the group changed; deleting the pseudo-plan and the proposal and repointing every inbound link |
| Hard scope - out | Any code change. Any new decision - if a decision is still open at this point it is a new plan, not a closure row. Deleting anything under `docs/` |
| ESCALATE triggers | 1. A durable finding has no living doc that owns it and creating one is not obviously right - that is a documentation-structure question. 2. A decision recorded in the pseudo-plan turns out never to have been implemented, which means the group is not finished. 3. An inbound link points at a section that no longer exists anywhere |
| Chosen strategy | Verify before writing. The closure of the last comparable programme found that most of what it was told to record was **already** in the living docs, and the useful output was the re-measured numbers and the corrections |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | What is durable, and where it already lives | - | A | PENDING | - | - | - |
| 2 | The numbers, taken again on the tree that shipped | 1 | B | PENDING | - | - | - |
| 3 | The two documents go, and nothing links to a ghost | 2 | C | PENDING | - | - | - |

---

## 2. Row #1 - What is durable, and where it already lives

- **Scope:** Walk both working documents; for every durable finding, check whether the living doc already holds it, and write the ones that do not.
- **Files touched:** `docs/concepts/digest.md`, `docs/concepts/design-system.md`, `docs/concepts/evaluation.md`, `docs/concepts/telemetry.md`, `docs/concepts/adaptive-pruning.md`, `docs/architecture/**`, `docs/reference/agent-notes.md`, `docs/reference/measurements.md`
- **Acceptance gates:** the full suite; the docs cross-link check; `test_contracts.py`'s ASCII and LF check.
- **Oracle:** Every owner decision, correction, gap and contradiction in the pseudo-plan is accounted for by exactly one of: **implemented** (name the plan and the PR), **recorded** (name the living doc and the section), or **superseded** (name what replaced it). A table with no fourth column - because a fourth column is where a lost decision hides.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Verify before writing.** The last comparable closure found every ruling it was told to record was already in the living docs, and its real output was one dangling link plus a stale sentence. Budget this row for checking, not for prose | Recorded lesson |
| 2 | **Deviation A must land in `docs/concepts/digest.md` under the visual rule** - the model assigns what a number means and nothing verifies it. It is accepted as permanent, so it has to outlive the document that accepted it | O40 |
| 3 | The number and unit normalisation rule splits by kind: the formatting half to the design system, the conversion half to the Derived Value contract. **Neither may live only in a working document** | O47, section 7.5 |
| 4 | Execution craft learned during the group goes to `docs/reference/agent-notes.md`. A worker cannot write that file when it is outside its row's file list, so lessons pile up across a whole programme and die - **this row is where they get paid off** | Recorded lesson |
| 5 | A decision that was never implemented is not distilled. It is surfaced, because it means the group is not finished | Fowler |
| 6 | **The governing principle goes with them**: the visual complements the article at high information compression - it is not "a chart". Every plan in this group served that sentence and no living doc states it, so deleting the working documents would delete the reason all twenty-two existed | O1 |
| 7 | O42 is **superseded, not lost**: the potential classifier stopped being its own plan-doc when O46 split it into a query and two lexicons. The distil table records it as superseded and names what replaced it | O42, O46 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Archive the working documents instead of deleting them | Then two non-authoritative copies of the contract sit beside the real one, which is what `docs/` is the memory means to prevent | CLAUDE.md Rule #4 |
| 2 | Copy the documents wholesale into `docs/` | They are a decision **record**, not a living doc. Most of their content is argument that has already been settled | Fowler |

---

## 3. Row #2 - The numbers, taken again on the tree that shipped

- **Scope:** Re-measure everything the group moved, on the tree that actually shipped, and record it with hardware, date and spread.
- **Files touched:** `docs/reference/measurements.md`, `config/idhazh.json` (any ceiling whose runway has expired)
- **Acceptance gates:** `bundle-gate`; `idhazh site-weight`; the full suite; the browser suite.
- **Oracle:** Every number recorded carries the hardware, the date and the spread, and any figure quoted from the working documents is either reproduced or **corrected with the correction stated**. A closure that reprints an old number without re-taking it has recorded a claim about a tree nobody built.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Re-measure even the corrections. On the last comparable closure a figure it was told to fix was wrong in the fix as well | Recorded lesson |
| 2 | A ceiling is re-recorded because its **runway** expires, not because a gate went red. Say that plainly or a reader thinks something failed | Recorded lesson |
| 3 | The whole-day measurement from plans 12 and 18 is taken once more here, because this is the last tree in the group | Susan |
| 4 | The counterfactual cost figure, if the console shows one, is checked to still print the rate it used and to still be labelled a counterfactual. **We are not billed, and presenting it as a bill is the one way to make it a lie** | CLAUDE.md Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Carry the working documents' numbers forward | They were measured across twenty-two plans on trees that no longer exist | Rule #10 |

---

## 4. Row #3 - The two documents go, and nothing links to a ghost

- **Scope:** Delete the pseudo-plan and the proposal; repoint every inbound link; leave the numbered plan-docs to be deleted by their own closures.
- **Files touched:** `TODO/20260902-visual-planner-pseudo-plan.md` (deleted), `TODO/20260902-yen-idhazh-visual-planning-architecture.md` (deleted), every file `git grep` finds naming either, `AGENTS.md`
- **Acceptance gates:** the full suite; the docs cross-link check.
- **Oracle:** `git grep` for both filenames and for the group's own slug returns **zero** hits outside git history, and every page that previously linked to them now links to the living doc that received the content. Each hit is enumerated in the PR body with where it was repointed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The only real cost of deleting a plan-doc is its inbound links**, and they are found with one grep. Re-read each hit for staleness as well as for the link - the last closure found its single inbound link was also describing a decision that had since been made | Recorded lesson |
| 2 | `git rm` is done **last** in the commit sequence. It stages the deletion immediately, so a later `git add` of unrelated paths sweeps it into a commit whose message describes something else | Recorded lesson |
| 3 | Check `git ls-files --error-unmatch` first. A plan-doc that was never committed makes "delete the plan-doc" a no-op and the PR fails with no commits between the branches | Recorded lesson |
| 4 | `AGENTS.md` names the open plan-docs and must be updated in the same commit, or it points at files that no longer exist | AGENTS.md |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Delete the numbered plan-docs here too | Each is deleted by its own closure, when its rows have merged. Deleting them centrally hides which ones actually finished | Fowler |
| 2 | Keep the pseudo-plan as a historical record | Git history is the immutable record of when a decision changed. A second copy on the default branch is a second source of truth | CLAUDE.md section 5 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes, and which this plan deletes.
- [`20260905-21-human-judgement-plan.md`](20260905-21-human-judgement-plan.md) - the previous plan.
- [`20260905-01-visible-chart-plan.md`](20260905-01-visible-chart-plan.md) - the first plan of the group.
- [`../docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - the closure ritual this plan follows.
