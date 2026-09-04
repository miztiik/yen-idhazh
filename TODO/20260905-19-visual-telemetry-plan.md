# 19 - Every attempt is recorded

**Last Updated**: 2026-09-05
**Level**: 4 (a new committed ledger whose fold key is irreversible, plus the store a corpus re-render depends on)

**Chain**: previous [`20260905-18-diagram-vocabulary-plan.md`](20260905-18-diagram-vocabulary-plan.md) | next [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - rows 54, 55, sections 12.6 G1, 12.7 G7, G10, G11, 12.9 G12, 12.13 G37, 12.14 G40, G41, section 9.2, 9.3.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 1; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Everything from plan 11 onward gates publication on machine judgement, and none of it is recorded. Today "no visual was possible" and "the visual stage broke" are the same row. **`none` is the majority outcome by design**, so a majority outcome with no cause breakdown means the largest number an operator sees explains nothing |
| Hard scope - in | A visual pipeline stage; a ledger with **one row per attempt**; a typed reason for every refusal; the join key a human label needs; the fold key, settled before the first row is written; the store a whole-day re-render needs |
| Hard scope - out | The console panels (plan 20). Any human review surface (plan 21). Any change to what publishes |
| ESCALATE triggers | 1. The ledger is proposed as one row per **published** visual - that leaves every refusal uncommitted and the machine loop stops being auditable while still being the gate. 2. A route to `none` exists that carries no reason. 3. The fold key is settled without the stratum terms - **the fold is irreversible and a key settled narrow cannot be widened later against data that no longer exists** |
| Chosen strategy | Settle the fold key first, because it is the only decision here that cannot be revised. Then the stage, then the ledger, then the store |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The fold key, decided before anything writes a row | - | A | PENDING | - | - | - |
| 2 | A stage of its own | 1 | B | PENDING | - | - | - |
| 3 | One row per attempt, and a reason for every refusal | 2 | C | PENDING | - | - | - |
| 4 | What a re-render needs, and where a rejected plan lives | 3 | D | PENDING | - | - | - |

---

## 2. Row #1 - The fold key, decided before anything writes a row

- **Scope:** The group key `state/visuals/` folds to at the window edge, and the shape of the folded row.
- **Files touched:** `backend/idhazh/contracts/visual_telemetry.py` (the schema description), `backend/idhazh/retention.py`, `config/idhazh.json` (the named window), `docs/concepts/adaptive-pruning.md`, `docs/concepts/telemetry.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Folding a fixture month and then asking the aggregate the four questions the console must answer - which gate refused most, how keep rate moved with downgrade depth, how the classes differ, how the distribution is shaped - returns an answer for all four. **A fold that loses one of them has lost it for ever.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The key carries at minimum `(date, decision, none_reason, rejection_reason)` **plus** `potential_primary`, `family` and an element-count band. The first four keep the cause breakdown; the last three keep the stratum | 12.9 G12, 12.13 G37 |
| 2 | The row carries a **distribution, not a mean** - at minimum a count, a median and the two outer quartiles. **A bimodal distribution is the interesting finding and a mean hides it** | 12.13 G37 |
| 3 | `state/visuals/` declares its key **in the schema description**, the way the existing aggregate store already does | 12.9 G12 |
| 4 | The window is one of the six named per-store windows. The old shared knob no longer exists | Section 9.2 correction |
| 5 | This is row 1 because the fold deletes the full-grain shard. Every other decision in this plan can be revised; this one cannot | Fowler |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold on date alone | Deletes the cause breakdown and the strata at the window edge, which is the half that decides whether the reason enum was worth building | 12.9 G12 |
| 2 | Decide the key when the first fold is due | By then the full-grain rows outside the window are gone | Fowler |

---

## 3. Row #2 - A stage of its own

- **Scope:** `ItemStage.VISUAL`, so the pipeline can distinguish "no visual was possible" from "the visual stage broke".
- **Files touched:** `backend/idhazh/contracts/item_health.py`, `schemas/item-health-row.schema.json`, `backend/idhazh/telemetry.py`, `backend/idhazh/cli.py`, `tests/fixtures/**`, `frontend/scripts/build-canary.mjs`, `backend/tests/**`, `docs/architecture/sources/item-health.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; the canary build.
- **Oracle:** Every failure code is mapped to the stage it can occur at, and a fixture writer exists for each - the existing parametrized test, extended. A new stage with codes and no producer raises rather than passing.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Additive: one changelog entry, no migration. `ItemStage` is `PLAN`, `FETCH`, `EXTRACT`, `SUMMARIZE`, `PUBLISH` today | Row 54, verified 2026-09-05 |
| 2 | Adding a stage or a failure code is **not** a contracts-only change - a parametrized test walks every code and needs a real fixture writer for each | Recorded trap |
| 3 | The canary writer restates the item-health header in JavaScript and must be widened in the same commit, or every backend gate passes and the site build fails | Recorded trap |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Record visual failures under `PUBLISH` | Then a broken renderer and a correct refusal are the same row, which is the defect | Fowler |

---

## 4. Row #3 - One row per attempt, and a reason for every refusal

- **Scope:** `state/visuals/<YYYY-MM>.csv`: one row per **attempt**, carrying `decision`, `none_reason`, `visual_id` and the full outcome family.
- **Files touched:** `backend/idhazh/contracts/visual_telemetry.py`, `schemas/*.schema.json`, `backend/idhazh/visual_planner.py`, `state/visuals/` (header committed), `.github/scripts/commit-and-push.sh`, `.github/workflows/digest.yml`, `tests/fixtures/**`, `backend/tests/**`, `docs/concepts/telemetry.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; `shellcheck`; the full suite; one dispatch writing rows.
- **Oracle:** Drive every gate independently and collect the reasons observed; the set must **equal the enum exactly**. A gate whose refusal is indistinguishable from another's, or an enum member no gate can produce, both fail.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One row per attempt, not per publication.** A per-publication ledger leaves every refusal, every `none` and every typed rejection reason uncommitted - the machine loop stops being auditable while still being the gate, and a later run cannot tell a refused visual from one never attempted | 12.7 G7, row 55 |
| 2 | `none_reason` covers **all six gates**, not only the ones the validator sees. The pre-model refusal is the cheapest gate and therefore the most common, so it would otherwise be the least explained | 12.6 G1, 12.7 G11 |
| 3 | `visual_id` is the join key. **Without it there is no overlap to compute reviewer agreement from, and by the project's own rule no keep rate is quotable** | 12.14 G41 |
| 4 | `gate_floor_applied` becomes real only once the ladder's depth-2 and depth-3 percentiles exist, which plan 11 settled | 12.7 |
| 5 | No query surface. There is no server | Row 55, Rule #1 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One row per published visual | See decision 1 - it is the failure this row exists to prevent | Fowler |
| 2 | Free-text refusal reasons | Unaggregatable, and a free-text cell is a `merge=union` hazard on a ledger eight shards append to | Carmack |

---

## 5. Row #4 - What a re-render needs, and where a rejected plan lives

- **Scope:** The stored plan and element set a whole-day re-render reads, and a home for a rejected plan's body.
- **Files touched:** `backend/idhazh/assemble.py`, `frontend/public/digest/**` or a `state/` store, `backend/idhazh/retention.py`, `config/idhazh.json`, `docs/concepts/adaptive-pruning.md` (the register), `backend/tests/**`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `idhazh site-weight`; `idhazh validate-days`.
- **Oracle:** A published day is re-rendered **from the committed store alone**, with no re-run of any model, and the output matches the committed visuals byte for byte. That is the only proof the store holds enough.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A CSV cell cannot hold a plan.** Three things already depend on this store: a renderer bump re-renders whole days or none, the migration's corpus re-render pass, and the blast-radius query. All three had nothing to read | 12.14 G40, row 35 |
| 2 | Re-rendering needs the **elements** as much as the plan, and the register names no element store today. Whether they live in the day payload - registered and never deleted - or in their own store is this row's call; what is not open is leaving it unregistered | 12.14 G40 |
| 3 | A **rejected** plan's body is a lookup: it answers no question outside its review window, so it deletes rather than folds, on a short window, with a register row and a sampling ratio in config | 12.7 G10, section 9.2 |
| 4 | The register in `docs/concepts/adaptive-pruning.md` claims to name every artefact this project writes. Each new store here gets a row, or that claim is false | Section 9.3 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep only the ledger row | Then a renderer bump can re-render nothing, and the whole-day rule that stops two drawing styles in one scroll is unenforceable | 12.14 G40 |
| 2 | Keep every rejected plan for ever | Unbounded growth for evidence with a review-window life | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [`20260905-18-diagram-vocabulary-plan.md`](20260905-18-diagram-vocabulary-plan.md) - the previous plan.
- [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md) - the next plan.
