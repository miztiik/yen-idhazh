# 16 - Parts of a whole

**Last Updated**: 2026-10-25
**Level**: 5 for persisted composition and review contracts; 3 for the
implementation phases.

**Chain**: previous [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) | next [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O45, O47, rows 43, 44, 45, sections 7.2, 12.2 L3, 12.12 G27, M7.

kumarsnaveen approved this alignment on 2026-10-25 UTC. Execute per
docs/how-to/execute-a-plan.md; one meaningful implementation PR phase per
renderer or contract. CONSULT the relevant advisor where two answers lead to
different code; no automatic merge.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Some stories are a breakdown - a vote, a budget split, a spread of values. The chart family plan 15 built cannot show a part-of-whole read or a distribution at all. This plan adds the three types that can, and with them the first producers of a value the article did not write in so many words |
| Hard scope - in | `pie` under its gate; `bubble` as a relationship visual under its area and legibility gates; `histogram` with deterministic versioned binning; the four closed derived-value producers; a separate human keep-rate ledger that can compare pie and bubble |
| Hard scope - out | The Derived Value **contract** - plan 10 built it and plan 16 resolves its producers; any fifth allow-list function; diagrams; the infographic family; machine labels pooled with human labels |
| ESCALATE triggers | 1. A derived value is produced whose provenance chain does not name its function, its version and every input element. 2. A `pie` or `stacked_bar` is drawn against a whole that was **summed** rather than independently declared. 3. `bubble` cannot clear its configured legibility floor, which means it cannot ship on the surface most readers use |
| Chosen strategy | Align the live contracts first, then deliver one type at a time - gate first, produce second, measure keep rate third; Fowler and Susan validate the contract and reader surface |
| Execution | One meaningful PR phase per type or contract; parallel N = 4 only where the same code and contract files remain disjoint; no automatic merge authority |

**Why this plan exists at all, recorded because it was nearly dropped.** Carmack proposed dropping the family on the grounds that derived values "let the planner state a number the article never did". **Overruled by the owner on 2026-09-05, and the reasoning is now O45.** The planner states nothing: every value is arithmetic **code** performs over Tier 1 elements **code** extracted, through a closed list whose members the model cannot name, cannot supply an operand to, and cannot express in its schema. The metric that objection reached for measures whether a summary bullet says something the summary prose does not - a prose instrument, unrelated to a chart's arithmetic.

### Owner-approved reconciliation

kumarsnaveen approved these decisions on 2026-10-25 UTC:

| ID | Decision | Change from the September plan |
| --- | --- | --- |
| R1 | Bubble is a relationship visual with `quantity_x`, `quantity` and `size`; the bubble-to-scatter edge remains | Removes bubble from the composition-purpose group and adds a square-root area channel |
| R2 | The configurable bubble legibility floor defaults to 390 CSS px | Keeps the original floor as the default and moves it under config control |
| R3 | Add `declared_whole_element_id` to the visual plan and published visual data | Gives pie and stacked bar an independent article element for the whole instead of inferring it from parts |
| R4 | Keep exact machine requested/delivered outcomes and build a separate human pie/bubble keep-rate ledger | Does not mix human labels with machine records or duplicate machine type fields with a boolean |
| R5 | Histogram keeps at least 3 cited values and draws 3 configurable equal-width bins by default, inside the existing 2-8 mark window | Keeps remote-main defaults and retains model-independent versioned binning |

No other scope or functionality change is approved. Existing current-renderer-only
chart compatibility, the derived-value closed allow-list and no-value-on-degrade
rules remain unchanged.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | How often does an article actually state a whole | - | A | DONE #654 | p16-1 | #654 | worker |
| 2 | The four ways code may reach a number the article did not write | 1 | B | DONE #537, #538 | - | #537, #538 | worker |
| 3 | A declared whole: pie | 2 | C | PENDING | - | - | - |
| 4 | Three numbers at once: bubble | 2 | D | PENDING | - | - | - |
| 5 | A spread of values: histogram | 2 | E | PENDING | - | - | - |
| 6 | Human pie and bubble keep-rate evidence | 3, 4 | F | PENDING | - | - | - |

### Current delivery evidence

Fowler and Susan reviewed remote main on 2026-10-25 UTC. These are inspected
implementation facts, not claims that later rows passed.

| ID | Row | Existing delivery | Remaining delivery |
| --- | --- | --- | --- |
| E1 | 1 | `#654` added the bounded measurement and benchmark record | None |
| E2 | 2 | `#537` added the closed derived-value contract and producers; `#538` added the histogram bin and resolver corrections | No story-only producers need changing |
| E3 | 3 | Pie is declarable, shares the pie-to-stacked-bar edge, and has resolver arithmetic | Independent whole evidence, public compiler and pie renderer remain |
| E4 | 4 | Bubble is declarable with relationship purpose and a bubble-to-scatter edge | Square-root area, configurable legibility floor and story delivery remain |
| E5 | 5 | Histogram role rules, equal-width binning, count provenance and empty-bin refusal exist | Story compiler and browser renderer remain |
| E6 | 6 | Machine outcomes record exact planned and delivered types | A separate human keep-rate ledger and visual join key remain |

---

## 2. Row #1 - How often does an article actually state a whole

- **Scope:** Count, over the committed corpus, how often an article states a total that its parts are meant to sum to.
- **Files touched:** `TODO/20260905-16-composition-vocabulary-plan.md`, `backend/utilities/measure_declared_wholes.py`, `docs/reference/benchmarks/articles-that-state-a-whole.md`, `docs/reference/measurements.md`
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
| 1 | Four functions are closed in remote main. **The shortness remains the guarantee** | O45, O47 |
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

- **Scope:** `pie` under a gate: composition purpose, five parts or fewer, a separately cited **declared** whole, one canonical measure, one unit, and a stacked-bar downgrade that re-enters the same composition checks.
- **Files touched:** `backend/idhazh/contracts/visual.py`, `backend/idhazh/contracts/visual_data.py`, `backend/idhazh/contracts/knobs/visuals.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/derived_values.py`, `backend/idhazh/render/chart.py`, `frontend/src/lib/payload/drawing.ts`, `frontend/src/lib/payload/types.ts`, `frontend/src/lib/charts/d3/partsOfOne.ts`, `frontend/src/lib/components/ItemVisual.svelte`, named contract and browser fixtures/tests, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; both floors; the section 12 smoke.
- **Oracle:** A plan whose whole is **summed rather than declared** downgrades to `stacked_bar` and **re-enters plan 15's exhaustiveness gate**, which then rules on it. The chain is asserted end to end, because a downgrade into a type with no predicate would launder the refusal.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `pie` ships as a declarable and buildable type. Jony would build no pie at all and route composition to a stacked bar; the owner wanted the type, so **both**: pie under its gate, stacked bar as its downgrade target rather than its replacement | Row 43, section 4.F |
| 2 | A **declared** whole, never a summed one. `declared_whole_element_id` names the independent article element, and summing the parts cannot establish it | Owner R3; Row 43 |
| 3 | Five parts or fewer. Beyond that an angle is unreadable and the type is doing worse than the bar it displaced | Section 7.2 |
| 4 | Direct and fallback composition require the same canonical measure, the same unit and independent whole evidence | Plan 15 owner R4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | No pie template, route composition to a stacked bar | Jony's position. Overruled by the owner, and recorded rather than erased | Section 4.F |

---

## 5. Row #4 - Three numbers at once: bubble

- **Scope:** `bubble` under the relationship gate, with three measured channels and a configurable legibility floor, using square-root radius for area.
- **Files touched:** `backend/idhazh/contracts/visual.py`, `backend/idhazh/contracts/visual_data.py`, `backend/idhazh/contracts/knobs/visuals.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/render/chart.py`, `frontend/src/lib/payload/drawing.ts`, `frontend/src/lib/payload/types.ts`, `frontend/src/lib/visual/bubble.ts`, `frontend/src/lib/components/ItemVisual.svelte`, named contract and browser fixtures/tests, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** Current frontend check and build; native-reader binding; relationship-purpose fixtures; square-root geometry over three points; narrow-width browser coverage at the configured default; section 12 smoke.
- **Oracle:** The drawn radius is proportional to the **square root** of the value - asserted over at least three points, because two points fit both a linear and a square-root scale.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A square-root radius scale is **mandatory**. A linear radius misstates area, which is the channel the reader is actually reading | Section 7.2 |
| 2 | The plan keeps three measured channels: x position, y position and area; no composition purpose or declared whole is implied | Owner R1; row 44 |
| 3 | Reader's objection is recorded and not erased: three numbers judged by circle area at a narrow width are a lot to ask | Row 44 |
| 4 | It must clear the configurable legibility floor, default 390 CSS px, and a failed floor yields no picture | Owner R2; row 44; plan 12 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Drop `bubble` on Reader's objection | The objection is about a hard case, not the type. The floor is the honest test, and it fires per visual rather than per type | Owner, O16 |

---

## 6. Row #5 - A spread of values: histogram

- **Scope:** `histogram` with deterministic, versioned binning.
- **Files touched:** `backend/idhazh/contracts/visual.py`, `backend/idhazh/contracts/visual_data.py`, `backend/idhazh/contracts/knobs/visuals.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/derived_values.py`, `backend/idhazh/render/chart.py`, `frontend/src/lib/payload/drawing.ts`, `frontend/src/lib/payload/types.ts`, `frontend/src/lib/visual/histogram.ts`, `frontend/src/lib/components/ItemVisual.svelte`, config and named fixtures/tests, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** as row 3, plus `ruff`, `mypy --strict`, export + drift.
- **Oracle:** The same values binned twice - once in one process, once fresh - produce identical bin edges and counts, and the bin edges are recorded in the provenance chain so a redraw a year later reproduces the same picture.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The binning rule is **versioned config, never model-chosen**. The default is 3 equal-width bins with at least 3 cited values; both limits stay inside the existing mark window | Owner R5; Row 45 |
| 2 | Bin counts are `count` derived values and carry the same provenance as any other | Row 45 |
| 3 | Empty or crowded bins refuse the picture rather than publishing a bar that states no source count | `idhazh.derived_values` resolver check |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let the planner propose bins | The single easiest way to make a distribution say anything you like | Andre |

---

## 7. Row #6 - Human pie and bubble keep-rate evidence

- **Scope:** Join published visual evidence to a separate human label ledger, then compare pie and bubble keep rates by exact type without mixing machine and human verdicts.
- **Files touched:** The owner-approved visual identifier contract, a dedicated human visual-label contract and ledger, review queue integration, schema and fixtures, `backend/tests/**`, `docs/concepts/evaluation.md` and its owning plan references.
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Pie and bubble each have an exact type join, and a fixture keep-rate query separates them without pooling human labels with machine outcomes. A rate is not accepted without the inter-reviewer agreement required by Plan 21.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Use exact `planned_type` and `rendered_type` for machine outcomes; type fields need no new pie/bubble boolean | Owner R4 |
| 2 | Keep human labels in a dedicated ledger and never feed them into publication gates | Owner R4; Plan 21 |
| 3 | Publish pie and bubble keep rates only with their visual join key and inter-reviewer agreement | Plan 19 row 3; Plan 21 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rely on the general type distribution | It pools these two with types nobody doubts, so the comparison the doubt needs cannot be made | Andre |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-15-chart-vocabulary-plan.md`](20260905-15-chart-vocabulary-plan.md) - the previous plan.
- [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md) - the next plan.
- [Where every drawn figure came from](../docs/architecture/publishing/where-every-drawn-figure-came-from.md) - the arithmetic contract and its source evidence.
