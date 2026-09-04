# 16 - Parts of a whole

**Last Updated**: 2026-09-05
**Level**: 3 (three templates and the first producers of values the article did not write)

**Chain**: previous [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) | next [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O45, O47, rows 43, 44, 45, sections 7.2, 12.2 L3, 12.12 G27, M7.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Some stories are a breakdown - a vote, a budget split, a spread of values. The chart family plan 15 built cannot show a part-of-whole read or a distribution at all. This plan adds the three types that can, and with them the first producers of a value the article did not write in so many words |
| Hard scope - in | `pie` under its gate; `bubble` under its gate and the legibility floor; `histogram` with versioned binning; the `count`, `sum`, `share_of_declared_whole` and `convert` producers; the telemetry flag that makes the pie question decidable later |
| Hard scope - out | The Derived Value **contract** - plan 10 built it, this plan builds the producers. Any fifth allow-list function. Diagrams. The infographic family |
| ESCALATE triggers | 1. A derived value is produced whose provenance chain does not name its function, its version and every input element. 2. A `pie` is drawn against a whole that was **summed** rather than **declared**. 3. `bubble` cannot clear the legibility floor at 390 CSS px, which means it cannot ship on the surface most readers use |
| Chosen strategy | Gate first, produce second, flag third - so that when someone re-argues the pie question in six months there is data rather than opinion |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Why this plan exists at all, recorded because it was nearly dropped.** Carmack proposed dropping the family on the grounds that derived values "let the planner state a number the article never did". **Overruled by the owner on 2026-09-05, and the reasoning is now O45.** The planner states nothing: every value is arithmetic **code** performs over Tier 1 elements **code** extracted, through a closed list whose members the model cannot name, cannot supply an operand to, and cannot express in its schema. The metric that objection reached for measures whether a summary bullet says something the summary prose does not - a prose instrument, unrelated to a chart's arithmetic.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | How often does an article actually state a whole | - | A | PENDING | - | - | - |
| 2 | The four ways code may reach a number the article did not write | 1 | B | PENDING | - | - | - |
| 3 | A declared whole: pie | 2 | C | PENDING | - | - | - |
| 4 | Three numbers at once: bubble | 3 | D | PENDING | - | - | - |
| 5 | A spread of values: histogram | 4 | E | PENDING | - | - | - |
| 6 | The flag that settles the pie question later | 3, 4 | F | PENDING | - | - | - |

---

## 2. Row #1 - How often does an article actually state a whole

- **Scope:** Count, over the committed corpus, how often an article states a total that its parts are meant to sum to.
- **Files touched:** `docs/reference/measurements.md`
- **Acceptance gates:** the docs check; no code moves.
- **Oracle:** The figure carries the corpus, the date and the definition of "states a whole" that was counted, so a later count can be compared to this one rather than merely disagreeing with it.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is one command over committed data and it **sizes** the pie template rather than gating it. It has been outstanding since the design was written and nobody has taken it | M7 |
| 2 | If the answer is small, `pie` still ships - it simply fires rarely, which is what a gate is for | Owner, O45 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Use this as a gate on the whole plan | The owner ruled the family ships. A measurement that sizes a template is not a veto on it | Owner |

---

## 3. Row #2 - The four ways code may reach a number the article did not write

- **Scope:** The producers behind the allow-list: `count`, `sum`, `share_of_declared_whole`, `convert` - each with its provenance chain and its version.
- **Files touched:** `backend/idhazh/visual_planner.py` or a derived-value module, `backend/idhazh/contracts/visual.py`, `config/idhazh.json` (the unit table version), `schemas/*.schema.json`, `backend/tests/**`, `tests/fixtures/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Walking every compiled plan on the canary corpus, **every displayed value** resolves either to a Tier 1 element or to a derived value whose chain names its function, its version and every input element. Zero values with neither, and the count of each kind printed so a zero cannot come from walking nothing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Four functions, closed. **The shortness is the guarantee** | O45, O47 |
| 2 | `convert` reads a **versioned** unit table and records the source and target units. The version is stamped on every value it produces, so a later table change cannot silently re-interpret an old chart | O47 |
| 3 | The element's Tier 1 `surface` is never overwritten. The axis draws the readable form; the provenance carries the article's own characters | O47 |
| 4 | `derived_value_rate` and `trusted_data_ratio` are reported separately. Skipping either loses the guarantee unnoticed | 12.11 G21, P.L22 |
| 5 | Formatting is **not** a derived value and produces no chain. `2000000` drawn as `2M` moved no quantity | O47 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Drop the family and the producers | The reader loses the part-of-whole read. Overruled: the objection confused a number code computed with a number a model invented | Owner, O45 |
| 2 | Let the model choose the function | It cannot name one - the schema has no field for it. That is the design, not a check | Andre |

---

## 4. Row #3 - A declared whole: pie

- **Scope:** `pie` under a gate: composition purpose, five parts or fewer, a **declared** whole, one canonical measure, one unit.
- **Files touched:** `frontend/src/lib/charts/types/pie.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; both floors; the section 12 smoke.
- **Oracle:** A plan whose whole is **summed rather than declared** downgrades to `stacked_bar` and **re-enters plan 15's exhaustiveness gate**, which then rules on it. The chain is asserted end to end, because a downgrade into a type with no predicate would launder the refusal.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `pie` ships as a declarable and buildable type. Jony would build no pie at all and route composition to a stacked bar; the owner wanted the type, so **both**: pie under its gate, stacked bar as its downgrade target rather than its replacement | Row 43, section 4.F |
| 2 | A **declared** whole, never a summed one. Summing the parts and calling the total the whole asserts exhaustiveness the article did not | Row 43 |
| 3 | Five parts or fewer. Beyond that an angle is unreadable and the type is doing worse than the bar it displaced | Section 7.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | No pie template, route composition to a stacked bar | Jony's position. Overruled by the owner, and recorded rather than erased | Section 4.F |

---

## 5. Row #4 - Three numbers at once: bubble

- **Scope:** `bubble` under the same composition gate plus the legibility floor, with area encoded correctly.
- **Files touched:** `frontend/src/lib/charts/types/bubble.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 3.
- **Oracle:** The drawn radius is proportional to the **square root** of the value - asserted over at least three points, because two points fit both a linear and a square-root scale.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A square-root radius scale is **mandatory**. A linear radius misstates area, which is the channel the reader is actually reading | Section 7.2 |
| 2 | Reader's objection is recorded and not erased: three numbers judged by circle area on a 360px screen is a lot to ask | Row 44 |
| 3 | It must clear plan 12's legibility floor at 390 CSS px like any other type, and that is where the objection becomes checkable | Row 44, plan 12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Drop `bubble` on Reader's objection | The objection is about a hard case, not the type. The floor is the honest test, and it fires per visual rather than per type | Owner, O16 |

---

## 6. Row #5 - A spread of values: histogram

- **Scope:** `histogram` with deterministic, versioned binning.
- **Files touched:** `frontend/src/lib/charts/types/histogram.ts`, `backend/idhazh/contracts/visual.py`, `config/idhazh.json` (the binning rule and its version), `backend/idhazh/contracts/app_config.py`, `schemas/*.schema.json`, `tests/fixtures/**`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 3, plus `ruff`, `mypy --strict`, export + drift.
- **Oracle:** The same values binned twice - once in one process, once fresh - produce identical bin edges and counts, and the bin edges are recorded in the provenance chain so a redraw a year later reproduces the same picture.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The binning rule is **versioned config, never model-chosen**. A model choosing bins is a model choosing what the distribution looks like | Row 45 |
| 2 | Bin counts are `count` derived values and carry the same provenance as any other | Row 45 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let the planner propose bins | The single easiest way to make a distribution say anything you like | Andre |

---

## 7. Row #6 - The flag that settles the pie question later

- **Scope:** `pie` and `bubble` are flagged in telemetry so their keep rate can be compared directly against the position-and-length types.
- **Files touched:** `backend/idhazh/contracts/visual_telemetry.py` or the visual ledger contract, `schemas/*.schema.json`, `tests/fixtures/**`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A keep rate can be computed for the flagged set and the unflagged set separately from the committed ledger - asserted by computing both over fixtures, so the comparison is proved possible rather than promised.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **This flag is what makes the pie question decidable rather than re-arguable.** If `pie` under-performs over a meaningful sample that is an empirical result, not an argument - and without the flag it can only ever be re-argued | 12.12 G27 |
| 2 | The pie decision was the lowest-confidence row in the source document, and it is exactly where the audit found two gaps. That is the reason this flag exists | Section 12.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rely on the general type distribution | It pools these two with types nobody doubts, so the comparison the doubt needs cannot be made | Andre |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) - the previous plan.
- [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md) - the next plan.
- [`20260905-10-visual-plan-contract-plan.md`](20260905-10-visual-plan-contract-plan.md) - where the Derived Value contract was written.
