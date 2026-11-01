# 22 - Close it out

**Last Updated**: 2026-11-01
**Level**: 2 (documentation, and the deletion of two working documents)

**Chain**: delivered [visual-attempt reporting](../docs/how-to/report-visual-attempts.md); the human-review and automatic-tuning work is [closed](../docs/concepts/telemetry.md#visual-design-attempts). **Last plan of the group.**
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the document this row deletes, and O40 in particular.

Execute per docs/how-to/execute-a-plan.md. This C1 pass opens a documentation-only pull request after its checks; it does not merge the pull request or close this plan. Keep unfinished decisions visible for the final closure.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The pseudo-plan and proposal are decision records, not lasting documentation. Before removing them, verify which findings already live in `docs/`, add only what is missing, and preserve the source-to-page mapping in the C1 pull request |
| Hard scope - in | Auditing both working documents; adding only missing durable rules to existing canonical pages; deleting both working documents and this plan at closure; repointing every inbound link |
| Hard scope - out | Remeasurement (abandoned). Any code change. Any new decision - if a decision is still open, it is separate unfinished work, not a closure row. Deleting anything under `docs/` |
| ESCALATE triggers | 1. A durable finding has no living doc that owns it and creating one is not obviously right - that is a documentation-structure question. 2. A decision recorded in the pseudo-plan turns out never to have been implemented, which means the group is not finished. 3. An inbound link points at a section that no longer exists anywhere |
| Chosen strategy | Verify before writing. There is no separate findings document: use existing canonical pages and put the three-outcome audit table in the C1 pull request |
| Execution | `docs/how-to/execute-a-plan.md`; C1 delivers the audit and repairs without merging or deleting the source records. |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | What is durable, and where it already lives | - | A | IN PROGRESS | - | #1873 | - |
| 2 | The numbers, taken again on the tree that shipped | 1 | B | ABANDONED | - | - | - |
| 3 | The two documents go, and nothing links to a ghost | 1 | C | PENDING | - | - | - |

---

## 2. Row #1 - What is durable, and where it already lives

- **Open documentation-check decision:** The proposal would check that a working document names its owning `docs/` page and that the page links back. The current contract requires decisions to live on their owning pages, not to link back to temporary records. This check and any `CLAUDE.md` change are outside C1; decide whether the check is wanted and what it must prove before final closure.

- **Scope:** Audit both working documents; verify each durable finding against current code and the existing page that covers it; add only missing current rules.
- **Tasks:**
  1. Read `TODO/20260902-visual-planner-pseudo-plan.md` and `TODO/20260902-yen-idhazh-visual-planning-architecture.md` as source records. Inventory durable decisions, corrections, gaps, contradictions and execution lessons; leave speculation and per-pull-request history out.
  2. Check each item against current code and `docs/`. Do not repeat a rule that already has a current canonical page.
  3. Put the complete inventory in a three-column table in the C1 pull request: `Source item`, `Outcome`, `Evidence`. Use exactly one outcome per accounted item: **implemented** (plan and pull request), **recorded** (existing doc and section), or **superseded** (what replaced it). List unimplemented decisions separately as closure blockers. Do not create a separate findings document or a fourth outcome.
  4. For **recorded**, edit only the existing page that defines the rule and only when its current wording is missing. Verify O40 in the digest visual rule; O47 formatting in the design system and unit conversion in the Derived Value contract; O1 in the digest's visual rule; and new execution lessons in the agent-notes reference.
  5. Record O42 as **superseded** by O46: the query ships with the element table; the contrast and sequence lexicons remain deferred with diagram delivery. Name both dispositions in the audit table.
  6. If a decision was never implemented, stop final closure and surface the unfinished work. Do not classify it as a new outcome or delete its only source.
  7. If a durable finding has no clear canonical page, stop final closure and resolve the documentation-structure question; do not create an archive by default. Safe C1 repairs to clearly owned pages may proceed.
- **Files touched:** `docs/concepts/digest.md`, `docs/concepts/design-system.md`, `docs/concepts/evaluation.md`, `docs/concepts/telemetry.md`, `docs/concepts/adaptive-pruning.md`, `docs/architecture/**`, `docs/reference/agent-notes.md`, `docs/reference/pipeline-cost.md`
- **Acceptance gates:** direct documentation link checks; ASCII and LF checks for changed Markdown; the shared changed-file selector. Application suites are not run for this documentation-only row.
- **Oracle:** Every accounted durable decision, correction, gap, contradiction and execution lesson in either source document appears exactly once in the C1 pull request's three-column audit table, with one of the three outcomes above and its evidence. Unimplemented items remain separate closure blockers. There is no fourth outcome and no separate findings document.

### Remaining closure blockers

- The conservative, reviewed, versioned alias map is not implemented. Current classification matches known watchlist names only; the alias-map requirement and its scoring/version rules are recorded in [the element page](../docs/architecture/extraction/elements.md).
- Pre-shard semantic duplicate removal remains unresolved (pseudo-plan O25/O27 and row 52). Current `collapse_same_story` groups items during assembly but removes none, so it cannot avoid earlier planning or model work. Decide whether the proposed plan-stage cut remains in scope before final closure ([current grouping rule](../docs/architecture/publishing/autotune-content-similarity.md)).
- Diagram support remains deferred. The contrast and sequence word lists and the rule for deciding whether source text supports an edge are not implemented; no reader-facing diagram is claimed ([visual planning](../docs/architecture/publishing/visuals.md#diagrams-deferred)).
- [Plan 19 row 4](20260905-19-visual-telemetry-plan.md) remains deferred. Whole-day reconstruction still needs committed complete plans and elements, and refused plan bodies need a registered expiring home. `VisualAttemptRow` stores outcomes and counts, not those inputs; the local review card cannot show a refused drawing.
- Cross-day visual repetition remains unresolved (pseudo-plan P.R18/G43). The current within-day type-diversity measure does not tell whether a continuing story repeats the same visual while its figures stay unchanged; no `(element set, type)` fingerprint or `visual_repetition_rate` exists. Decide whether this rule remains in scope and where it belongs before final closure.
- Model grading of finished visuals remains unresolved (pseudo-plan O41). Current visual-label rows are human `KEEP`/`DISCARD` answers; the [evaluation page](../docs/concepts/evaluation.md) says a model-written verdict needs a separate contract and decision.
- The proposed documentation check remains undecided: should a working record name its owning `docs/` page, and should that page link back? The current contract requires decisions on their owning pages. No check or `CLAUDE.md` change is part of C1.

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
| 1 | Archive the working documents instead of deleting them | Then two non-authoritative copies of the contract sit beside the real one, which is what `docs/` is the memory means to prevent | CLAUDE.md Guardrail #4 |
| 2 | Copy the documents wholesale into `docs/` | They are a decision **record**, not a living doc. Most of their content is argument that has already been settled | Fowler |

---

## 3. Row #2 - The numbers, taken again on the tree that shipped

- **Status:** ABANDONED. Remeasurement is not possible; no new measurements will be taken. The original scope, gates and decisions below are context only, not execution requirements. Do not present an old reading as current.
- **Scope:** Re-measure everything the group moved, on the tree that actually shipped, and record it with hardware, date and spread.
- **Files touched:** `docs/reference/pipeline-cost.md`, `config/idhazh.json` (any ceiling whose runway has expired)
- **Acceptance gates:** `bundle-gate`; `idhazh site-weight`; the full suite; the browser suite.
- **Oracle:** Every number recorded carries the hardware, the date and the spread, and any figure quoted from the working documents is either reproduced or **corrected with the correction stated**. A closure that reprints an old number without re-taking it has recorded a claim about a tree nobody built.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Re-measure even the corrections. On the last comparable closure a figure it was told to fix was wrong in the fix as well | Recorded lesson |
| 2 | A ceiling is re-recorded because its **runway** expires, not because a gate went red. Say that plainly or a reader thinks something failed | Recorded lesson |
| 3 | The whole-day measurement from plans 12 and 18 is taken once more here, because this is the last tree in the group | Susan |
| 4 | The counterfactual cost figure, if the console shows one, is checked to still print the rate it used and to still be labelled a counterfactual. **We are not billed, and presenting it as a bill is the one way to make it a lie** | CLAUDE.md Guardrail #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Carry the working documents' numbers forward | They were measured across twenty-two plans on trees that no longer exist | Guardrail #10 |

---

## 4. Row #3 - The two documents go, and nothing links to a ghost

- **Scope:** After Row #1 accounts for every durable item, delete the pseudo-plan and proposal; repoint every inbound link to its canonical destination; delete this plan through the distillation procedure when the final row closes.
- **Files touched:** `TODO/20260902-visual-planner-pseudo-plan.md` (deleted), `TODO/20260902-yen-idhazh-visual-planning-architecture.md` (deleted), `TODO/20260905-19-visual-telemetry-plan.md`, `TODO/20260905-22-distil-and-close-plan.md` (deleted), `TODO/20260910-23-article-classification-plan.md`, `TODO/20260911-classification-research-record.md`, `TODO/20260915-30-decoder-stalls-handover.md`, `docs/architecture/publishing/visuals.md`, `docs/concepts/adaptive-pruning.md`
- **Acceptance gates:** the full suite; the docs cross-link check.
- **Oracle:** `git grep` for both filenames and for the group's own slug returns **zero** hits outside git history, and every page that previously linked to them now links to the living doc that received the content. Each hit is enumerated in the PR body with where it was repointed.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The only real cost of deleting a plan-doc is its inbound links**, and they are found with one grep. Re-read each hit for staleness as well as for the link - the last closure found its single inbound link was also describing a decision that had since been made | Recorded lesson |
| 2 | `git rm` is done **last** in the commit sequence. It stages the deletion immediately, so a later `git add` of unrelated paths sweeps it into a commit whose message describes something else | Recorded lesson |
| 3 | Check `git ls-files --error-unmatch` first. A plan-doc that was never committed makes "delete the plan-doc" a no-op and the PR fails with no commits between the branches | Recorded lesson |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Delete the numbered plan-docs here too | Each is deleted by its own closure, when its rows have merged. Deleting them centrally hides which ones actually finished | Fowler |
| 2 | Keep the pseudo-plan as a historical record | Git history is the immutable record of when a decision changed. A second copy on the default branch is a second source of truth | CLAUDE.md section 5 |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes, and which this plan deletes.
- [Recorded visual attempts](../docs/concepts/telemetry.md#visual-design-attempts) - delivered reporting and closed review/tuning scope.
- [The published frontend](../docs/architecture/publishing/frontend.md) - the delivered chart carrier and day loading.
- [`../docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - the closure ritual this plan follows.
