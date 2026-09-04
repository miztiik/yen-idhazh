# 18 - Diagrams

**Last Updated**: 2026-09-05
**Level**: 5 (a drawn arrow is a causal or sequential claim, so this plan extends the trust boundary)

**Chain**: previous [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md) | next [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O46, rows 46, 47, sections 7.2, 7.3, 12.4 Q6, 12.11 G16, 12.12 G24, 12.15 G46, P.R10.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | A process story has no series to chart and no whole to divide. It has steps. This plan draws them - and it is the plan where a drawn mark stops being a number and becomes a **claim**, because an arrow asserts that one thing led to another. It also completes the denominator: the two potential classes that are language rather than numbers land here, with the word-lists that produce them |
| Hard scope - in | The contrastive and sequencing lexicons; the edge decision procedure; the two remaining potential classes; `flow`, `hierarchy`, `state`, `mindmap`; span-anchored edges with no exception; the cycle predicate; layout determinism; the whole-day check repeated |
| Hard scope - out | Any new element kind. Any change to the validator's universal checks. Migrating the console. Any edge whose anchor is "the paragraphs are adjacent" |
| ESCALATE triggers | 1. An edge is proposed with no span. **There is no exception to this** and a proposal for one is a Level-5 stop. 2. The layout is not reproducible across processes. 3. The sequencing lexicon cannot be authored without a model, which would put the denominator inside Deviation A |
| Chosen strategy | Author the language artefact once and use it at both ends - the gate that decides whether a diagram is attempted at all, and the rule that decides whether each arrow is legal. Writing them apart gets them written twice and disagreeing |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

**Why the word-lists are here and not in plan 08.** They are needed by exactly one thing: the gate that keeps the diagram family from costing every non-process article a model call. Measured 2026-08-25 with diagrams enabled, **145 of 145 items reached the model and the stage spent its whole budget on 10 of 11 runs.** The gate is not a refinement; it is what makes the family affordable.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The words that mean "then", and the words that mean "against" | - | A | PENDING | - | - | - |
| 2 | The last two classes, and a denominator that finally names five | 1 | B | PENDING | - | - | - |
| 3 | Steps with arrows nobody invented: flow | 2 | C | PENDING | - | - | - |
| 4 | A layout that draws the same twice | 3 | D | PENDING | - | - | - |
| 5 | Trees, states and branches | 4 | E | PENDING | - | - | - |
| 6 | A whole day, once more | 5 | F | PENDING | - | - | - |

---

## 2. Row #1 - The words that mean "then", and the words that mean "against"

- **Scope:** Two versioned lexicons - contrastive and sequencing - and the written procedure that decides whether a span asserts an edge.
- **Files touched:** `config/` (the lexicons, versioned), `backend/idhazh/contracts/app_config.py` or a lexicon contract, `schemas/*.schema.json`, `backend/idhazh/potential.py` or the element module, `backend/tests/**`, `docs/concepts/**` (the procedure), `docs/architecture/extraction/**`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** The procedure is applied by hand to a labelled fixture set and by code to the same set, and the two agree. **A written rule nobody can apply consistently is not a rule**, and hand-versus-code agreement is the only way to find that out before it ships.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **These are one linguistic artefact seen from two ends.** The sequencing list gates whether the family is attempted; the edge procedure gates whether each arrow is legal. Written apart they get written twice and disagree | 12.15 G46, Andre |
| 2 | The honest difficulty is stated: natural language asserts sequence at many strengths. "Then" is explicit, "subsequently" is weaker, **paragraph adjacency asserts nothing.** So this is a written rule about which spans count, not a threshold | P.3.4.2, 12.15 G46 |
| 3 | The lexicons are **versioned config**, so a later change to what counts as a sequence marker is visible in the record and every rate it feeds can be re-based | Rule #6 |
| 4 | Authored by hand, not by a model. A model-authored lexicon would put the denominator for every rate inside Deviation A | Andre, O46 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A model decides whether a span asserts an edge | Then the load-bearing rule of the whole family is unverifiable, and it is the rule row 47 refuses to compromise on | Editor |
| 2 | Skip the lexicon and attempt a diagram on every article | Measured: 145 of 145 items reached the model and the stage spent its whole budget on 10 of 11 runs | Row 46 |

---

## 3. Row #2 - The last two classes, and a denominator that finally names five

- **Scope:** `comparative` and `processual` join `chartable` and `narrative`, so every rate can be reported over the full class set.
- **Files touched:** `backend/idhazh/potential.py`, `backend/idhazh/contracts/potential.py` or the element module, `schemas/*.schema.json`, `backend/idhazh/evals/metrics.py`, `frontend/src/routes/console/**`, `backend/tests/**`, `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `npm run check`; build; the browser suite.
- **Oracle:** Every published rate names **five** classes, and the sum of the class counts equals the item count - so a class that silently swallows the residue fails.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Plan 08 shipped the two classes derivable from the element table as a query. **These two are language, not numbers**, which is why they wait for the lexicons | O46 |
| 2 | Until this row lands, every rate reported per class names **three** classes and says so. That was written into plan 08 rather than left as a silent gap | O46, plan 08 |
| 3 | `narrative` records **why** it is narrative. Otherwise an extraction outage reads as a quiet month of unvisualisable news | Row 57 |
| 4 | Without a denominator of what was possible, 4 percent on narrative articles and 4 percent on chartable articles are the same number | Row 56 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Build all five classes in plan 08 | Four of the seven signals read call-1 output, which did not exist then | Andre, O46 |
| 2 | Ship the seven-signal classifier as its own subsystem | A new contract, a new config block and a version stamp to produce what a query already answers for two of the five | Fowler, O46 |

---

## 4. Row #3 - Steps with arrows nobody invented: flow

- **Scope:** `flow` - a process drawn as nodes and edges, every edge anchored to a span, with a cycle predicate.
- **Files touched:** `frontend/src/lib/charts/types/flow.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `npm run check`; build; `bundle-gate`; the browser suite; both floors; the section 12 smoke.
- **Oracle:** Every drawn edge re-slices to a span in the article, checked per edge, and a plan asserting a **cycle** the article does not assert is refused. The cycle case needs its own fixture because it lays out cleanly and therefore fails silently.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Span-anchored edges, no exception.** An unanchored arrow is an ordering or causal claim the article did not make. Reader: wrong once, and I stop believing every summary on the page | Row 47 |
| 2 | **A cyclic graph is not a rendering error.** It lays out cleanly and reads as an assertion, so an invented feedback loop is an invented claim - and this is the family where each edge anchors perfectly well on its own while their sum does not | 12.12 G24 |
| 3 | Edges are Tier 2 with a span; the decision procedure is published, and edges are sampled for human audit. **Edge anchoring is never described as deterministic** | P.R10, 12.4 Q6 |
| 4 | The `processual` gate from row 2 is what admits the family at all | Row 46 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Infer an edge from paragraph order | Paragraph adjacency asserts nothing, and this is the single easiest way to draw a causal claim nobody made | Editor |
| 2 | Allow cycles freely | An invented feedback loop is an invented claim, and it is invisible to every per-edge check | Fowler |

---

## 5. Row #4 - A layout that draws the same twice

- **Scope:** Deterministic force layout for the node-edge family.
- **Files touched:** `frontend/src/lib/charts/types/flow.ts`, `frontend/package.json` (exact pin), `config/idhazh.json` (the tick count), `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** `npm run check`; build; the browser suite.
- **Oracle:** The same input rendered twice in one process **and once in a fresh process** is byte-identical after rounding. One process cannot prove this.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The non-determinism people hit is the **wall-clock timer**, not the algorithm. Construct with the simulation stopped and never let the internal timer run | Section 7.3 |
| 2 | Sort nodes and links by `element_id` before construction - iteration order changes the result | Section 7.3 |
| 3 | Never carry coordinates in from a previous run or a cached plan; run exactly N ticks synchronously, N from `config/`; round output to a fixed precision so float drift is not a diff | Section 7.3 |
| 4 | Exact-pin the layout module and record it in `renderer_version` | Section 7.3, row 24 |
| 5 | Cost is an **estimate, not a measurement**: roughly 5 to 20 ms per graph on 4 vCPU at a 30-node cap, about a second of build time a day at the current rate. Measure it in this row and replace the estimate | Section 7.3, Rule #10 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A hand-written layout | Already tried and deleted - the previous one discarded edges, so two different graphs drew identically | Row 63 |

---

## 6. Row #5 - Trees, states and branches

- **Scope:** `hierarchy`, `state` and `mindmap`, each with its own validator rules.
- **Files touched:** `frontend/src/lib/charts/types/{hierarchy,state,mindmap}.ts`, `backend/idhazh/contracts/visual.py`, `frontend/tests/**`, `docs/architecture/publishing/**`
- **Acceptance gates:** as row 3.
- **Oracle:** Each type refuses a graph whose shape contradicts it - a `hierarchy` with a node having two parents, a `state` with an unreachable state - asserted one fixture per rule.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each gets its **own** validator rules rather than sharing `flow`'s. A tree and a state machine make different claims about the same nodes | Row 46 |
| 2 | A chain or a tree uses the hierarchy layout, not the force layout - force is for genuinely branching graphs | Section 7.2 |
| 3 | `decision: diagram` is **not** a chart type and is never aggregated into the chart distribution. A blended distribution is uninterpretable | 12.12 G23 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One diagram template with a shape parameter | Then no per-type rule can exist, and the rules are the whole safety argument | Fowler |

---

## 7. Row #6 - A whole day, once more

- **Scope:** The whole-day browser check re-run with every vocabulary family live.
- **Files touched:** `frontend/tests/whole-day.spec.ts`, `docs/how-to/run-the-gates.md`, `docs/reference/measurements.md`
- **Acceptance gates:** the browser suite; the section 12 smoke; `idhazh site-weight`.
- **Oracle:** On the heaviest committed day with every family enabled: zero console errors, zero responses at 400 or above, zero horizontal overflow, every visual clearing both floors, more than one rendered type, and the page settling within a stated time.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | This is the second of the two whole-day checks. The first ran against one family; this one runs against all of them, which is the only state that can show a page pulling in six directions | Susan, 2026-09-05 |
| 2 | The site-weight reading is taken here because this is the plan after which the vocabulary stops growing | Carmack |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rely on the check from plan 12 | It ran when one family existed. The failure this catches only appears when six do | Susan |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-17-infographic-vocabulary-plan.md`](20260905-17-infographic-vocabulary-plan.md) - the previous plan.
- [`20260905-19-visual-telemetry-plan.md`](20260905-19-visual-telemetry-plan.md) - the next plan.
- [`20260905-08-element-table-plan.md`](20260905-08-element-table-plan.md) - where the first two potential classes landed.
