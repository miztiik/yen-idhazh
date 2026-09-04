# 15 - Charts, plus the two the reader asked for

**Last Updated**: 2026-09-05
**Level**: 3 (the type vocabulary in config, and one compiler template per type)

**Chain**: previous [`20260905-14-sufficiency-bar-plan.md`](20260905-14-sufficiency-bar-plan.md) | next [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O13, rows 38, 39, 41, 48, 49, sections 7.2, 12.8 X1, 12.12 G26.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Until now the planner can say one shape. This gives it the position-and-length family, which is what most quantitative stories need - **and the two types the reader actually named**, so the first vocabulary plan does not publish a wall of identical bars |
| Hard scope - in | The full type vocabulary declared in config with unbuilt types downgrading deterministically; `bar`, `dot`, `slope`, `line`, `area`, `scatter`, `stacked_bar`; and `comparison` and `quotecard` pulled forward from the infographic family |
| Hard scope - out | `pie`, `bubble`, `histogram` and derived-value producers (plan 16). `callout`, `whowhat`, `keyfacts` (plan 17). Diagrams (plan 18). Any change to the validator's universal checks |
| ESCALATE triggers | 1. A type is proposed for the config list without both a validator rule set and a compiler template - it may be **named** but it may not **render**. 2. `wasted_decode_rate` cannot be computed, meaning the downgrade path is not recording what it did. 3. A non-magnitude question is being answered with a bar by fallback |
| Chosen strategy | Declare the whole vocabulary, build the families in order of what the planner actually chooses, and make a day that would otherwise be one shape impossible |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**The rule that stops a grey wall.** An article whose question is not a magnitude comparison gets `none`, **never a bar by fallback**. Row 49 records a single-shape day as a defect rather than gating on it, so a bar-only day is legal - and it is also a wall of grey on 80 items. Two things prevent it: the refusal rule, and shipping `comparison` and `quotecard` here rather than two plans later.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The whole vocabulary is declarable, and an unbuilt type steps down | - | A | PENDING | - | - | - |
| 2 | Position and length: bar, dot, slope | 1 | B | PENDING | - | - | - |
| 3 | Trend and magnitude: line, area | 2 | C | PENDING | - | - | - |
| 4 | Relationship: scatter | 3 | D | PENDING | - | - | - |
| 5 | Parts as bars: stacked_bar, with its own question | 4 | E | PENDING | - | - | - |
| 6 | The two the reader asked for | 5 | F | PENDING | - | - | - |

---

## 2. Row #1 - The whole vocabulary is declarable, and an unbuilt type steps down

- **Scope:** The full type list lives in `config/`, a type with no template is still declarable, and choosing one downgrades deterministically to its nearest built neighbour with the downgrade logged.
- **Files touched:** `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/visual.py`, `schemas/*.schema.json`, `tests/fixtures/**`, `backend/idhazh/visual_planner.py`, `backend/tests/**`, `docs/concepts/config.md`, `docs/architecture/publishing/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** A plan naming a declared-but-unbuilt type publishes its nearest built neighbour **and records both the requested and the rendered type**. `wasted_decode_rate` is then non-zero and computable, which is what makes the next plan's build order evidence rather than a guess.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Full vocabulary, located in config.** Rule #6 puts the list in `config/`; it does not shorten it. Read as "limited to types with templates", the neighbour-downgrade is unreachable, `wasted_decode_rate` is identically zero, and the build order stops being derivable | 12.8 X1 |
| 2 | This does not cross the non-goal about types arriving without rules. **That governs what may render; this governs what may be named.** An unbuilt type never reaches a reader | 12.8 X1 |
| 3 | Template order follows **observed frequency**, not a fixed wave order. Guessing the order is an unmeasured number justifying a design | Row 48 |
| 4 | `planned_type` and `rendered_type` are both recorded, always | Row 48, P.D2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Restrict the enum to built types | Makes the downgrade unreachable and the metric identically zero, and refutes the rule that derives the build order | 12.8 X1 |
| 2 | Hardcode the list in Python | Rule #6 | Fowler |

---

## 3. Row #2 - Position and length: bar, dot, slope

- **Scope:** Three templates whose encodings a reader judges by position or length - the family human perception reads most accurately.
- **Files touched:** `frontend/src/lib/charts/types/{bar,dot,slope}.ts`, `backend/idhazh/contracts/visual.py` (role sets), `frontend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; both floors from plan 12; the section 12 smoke.
- **Oracle:** For each type, drawn geometry is re-derived in the test from the committed element table and compared to the drawn attributes, at 390 and 1440. A chart proved only at one width has not been proved on the surface most readers use.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `bar` is horizontal by default at narrow widths, because a category label has room to be read | Section 7.2 |
| 2 | `dot` is the preferred form for ranking - position on a common scale beats length when the comparison is between items rather than to zero | Section 7.2 |
| 3 | `slope` draws no axis: two labelled columns and the lines between them | Section 7.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship `bar` alone first | One type is a grey wall on an 80-item day, and it is the state row 49 records as a defect | Susan |

---

## 4. Row #3 - Trend and magnitude: line, area

- **Scope:** `line` for a trend over time; `area` for cumulative magnitude, gated so it never draws a rate.
- **Files touched:** `frontend/src/lib/charts/types/{line,area}.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 2.
- **Oracle:** An `area` plan whose measure is a rate rather than a stock is **refused by the validator**, not drawn - asserted with a fixture pair that differs only in the measure.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `area` is gated to stock or cumulative measures. Filling under a rate states a total that is not the sum of the drawn values | Section 7.2 |
| 2 | A time axis needs the `date` kind, which plan 08 built. A trend over unordered categories is a bar | Plan 08 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Let `area` draw any series | The fill reads as a quantity, and under a rate that quantity is meaningless | Jony |

---

## 5. Row #4 - Relationship: scatter

- **Scope:** `scatter` for two measures over a shared set of entities.
- **Files touched:** `frontend/src/lib/charts/types/scatter.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 2.
- **Oracle:** Every drawn point resolves to an entity element carrying **both** measures; a plan where the two measures cover different entity sets is refused rather than drawn with gaps.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A scatter with an unstated relationship is a picture of two columns. The plan's `purpose` must say relationship, and the validator enforces it | Row 15 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Draw partial pairs | A missing point is invisible, so the reader sees a relationship computed over a set they cannot see | Andre |

---

## 6. Row #5 - Parts as bars: stacked_bar, with its own question

- **Scope:** `stacked_bar` with **its own** exhaustiveness gate, not merely as the thing `pie` falls back to.
- **Files touched:** `frontend/src/lib/charts/types/stacked_bar.ts`, `backend/idhazh/contracts/visual.py` (the predicate), `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 2.
- **Oracle:** A `stacked_bar` whose parts are not exhaustive against a **declared** whole downgrades to a grouped `bar`. Asserted directly, because the whole point is that the question is asked here and not only upstream.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`stacked_bar` has its own gate.** Without one, a `pie` refused for summing its whole rather than reading a declared one lands in a `stacked_bar` that never re-asks the question, and the refusal buys nothing | 12.12 G26 |
| 2 | This is the shape the downgrade ladder's re-validation rule needs: a downgrade target with no predicate makes re-entering the validator pointless | 12.7 G8, 12.12 G26 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Treat it only as pie's fallback | Then the refusal is laundered into a different drawing of the same wrong claim | Fowler |

---

## 7. Row #6 - The two the reader asked for

- **Scope:** `comparison` - a rectangular grid of span-anchored cells - and `quotecard`, restricted to a quote the semantic pass identified.
- **Files touched:** `frontend/src/lib/charts/types/{comparison,quotecard}.ts` or typeset HTML components, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`, `docs/concepts/design-system.md`
- **Acceptance gates:** as row 2, plus the whole-day check from plan 12.
- **Oracle:** On a real committed day the page carries **more than one rendered type**, and every `quotecard` renders a quote whose span slices to the drawn text from the article's own bytes - re-sliced in the test, not compared to a stored string.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These two are pulled forward from the infographic plan **specifically** so the first vocabulary plan cannot publish a wall of bars. The reader named these two as the ones they would actually want | Susan, Reader, 2026-09-05 |
| 2 | `quotecard` is restricted to quotes the semantic pass identified and capped at `summarize.max_verbatim_words`. It is **not** applied to every article | O13, row 39 |
| 3 | Jony dissents on `quotecard` as craft - "one sentence in a bigger font with a border". The owner overruled, and the dissent is recorded rather than erased | Row 39, section 4.F |
| 4 | `comparison` is **rectangular**: each cell pairs an entity span and a claim span from the same sentence, or the cell is empty. The rule was stated only on the derived type and is stated here on the base type | Row 41, 12.13 G33 |
| 5 | Neither type needs chart machinery - both are typeset markup | Section 7.2 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave both to the infographic plan | Then two plans publish days that are only bars, on the surface a reader sees | Susan |
| 2 | A `quotecard` on every article | Republishing by another name, and it makes an ordinary sentence look like a finding | Andre, Editor |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-14-sufficiency-bar-plan.md`](20260905-14-sufficiency-bar-plan.md) - the previous plan.
- [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md) - the next plan.
