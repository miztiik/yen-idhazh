# 19 - Every attempt is recorded

**Last Updated**: 2026-10-29
**Level**: 5 contract decisions authorized for delivery; row 4 remains deferred.

**Current ruling, 2026-10-29 UTC:** the maintainer authorized implementation
and stacked PR delivery. Row 3 uses the registered name
`visual-design-attempts`, one row per actual attempt, including none/refusal
and render failure. No aggregate store, fold writer, permanent summary or
custom retry feature is authorized. Standard lossless compaction is storage
packing, not an aggregate. These rulings supersede the historical aggregate
design in row 1 and the older read-only scope below. Plans 20 and 22 are not
closed by this work.

**Chain**: diagrams are [deferred](../docs/architecture/publishing/visuals.md#diagrams-deferred), not a prerequisite | next [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - rows 54, 55, sections 12.6 G1, 12.7 G7, G10, G11, 12.9 G12, 12.13 G37, 12.14 G40, G41, section 9.2, 9.3.

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Everything from plan 11 onward gates publication on machine judgement, and none of it is recorded. Today "no visual was possible" and "the visual stage broke" are the same row. **`none` is the majority outcome by design**, so a majority outcome with no cause breakdown means the largest number an operator sees explains nothing |
| Hard scope - in | Row 3: a registered ledger with one row per actual visual-design attempt, typed refusal causes, exact visual identity, full-grain retention and standard lossless packing |
| Hard scope - out | The console panels (plan 20). Any human review surface (plan 21). Any change to what publishes |
| ESCALATE triggers | Attempts are replaced by publications; a current refusal loses its typed cause; an aggregate, permanent summary or custom retry feature is proposed |
| Chosen strategy | Producer evidence first, then registered persistence, publication ownership and bounded retention. Whole-day re-rendering and rejected-plan bodies remain row 4 |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The fold key, decided before anything writes a row | - | A | DONE #686 | p19-r1 | #686 | worker |
| 2 | A stage of its own | 1 | B | DONE #695 | p19-r2 | #695 | worker |
| 3 | One row per attempt, and a reason for every refusal | 2 | C | IMPLEMENTED; local gates and stacked PR delivery in progress; full CI required before merge | visual-design-attempt-ledger | - | - |
| 4 | What a re-render needs, and where a rejected plan lives | 3 | D | DEFERRED | - | - | - |

---

## 2. Row #1 - The fold key, decided before anything writes a row

- **Scope:** The group key `state/visuals/` folds to at the window edge, and the shape of the folded row.
- **Files touched:** `backend/idhazh/contracts/visual_telemetry.py` (**new** - the contract and its schema description), `backend/idhazh/contracts/export.py` (the new contract is registered here or no schema is generated), `backend/idhazh/retention.py`, `config/idhazh.json` (the named window), `docs/concepts/adaptive-pruning.md`, `docs/concepts/telemetry.md`
- **Checked against the tree, 2026-09-13.** Neither `backend/idhazh/contracts/visual_telemetry.py` nor `state/visuals/` exists - the row reads as if the contract were already there and it is not, so this row writes it. The eight directories under `state/` today are `day-metrics`, `feed-health`, `item-health`, `published`, `score-index`, `scores`, `seen` and `visual-prunes`. `backend/idhazh/contracts/export.py` was missing from the list: `CONTRACTS` there is a hand-written tuple with one import line per contract, so a contract absent from it generates no schema and the drift gate stays green while proving nothing.
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite.
- **Oracle:** Folding a fixture month and then asking the aggregate the four questions the console must answer - which gate refused most, how keep rate moved with downgrade depth, how the classes differ, how the distribution is shaped - returns an answer for all four. **A fold that loses one of them has lost it for ever.**

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The key carries at minimum `(date, decision, none_reason, rejection_reason)` **plus** `potential_primary`, `family` and an element-count band. The first four keep the cause breakdown; the last three keep the stratum | 12.9 G12, 12.13 G37 |
| 2 | The row carries a **distribution, not a mean** - at minimum a count, a median and the two outer quartiles. **A bimodal distribution is the interesting finding and a mean hides it** | 12.13 G37 |
| 3 | `state/visuals/` declares its key **in the schema description**, the way the existing aggregate ledger already does | 12.9 G12 |
| 4 | The window is one of the six named per-ledger windows. The old shared knob no longer exists | Section 9.2 correction |
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

- **Scope:** `state/raw/visual-design-attempts/` and `state/compact/visual-design-attempts/`: each actual attempt, including none/refusal and render failure; no attempt for work that never reached visual planning.
- **Implementation:** `VisualAttemptRow`, shared `telemetry.visual_attempts` mapping, worker settlement, native ledger name/key/staging registry, compaction declaration and gardener enrollment. The publisher is `backend/utilities/digest_publish.py`; no hand-written CSV or second assemble writer. JSON Schema is computed on demand, not committed under `schemas/`.
- **Acceptance gates:** changed-file Ruff and strict mypy, shared changed-test selector, bounded producer/store/read/compact/expiry and workflow-ownership tests; full CI on the merge candidate.
- **Oracle:** Real producer decisions map to registered raw Parquet, read back and survive standard lossless packing. The observed refusal set equals the five implemented `NoneReason` members; call sites may intentionally share a gate. Completed attempts survive later work failure.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **One row per attempt, not per publication.** A per-publication ledger leaves every refusal, every `none` and every typed rejection reason uncommitted - the machine loop stops being auditable while still being the gate, and a later run cannot tell a refused visual from one never attempted | 12.7 G7, row 55 |
| 2 | `none_reason` covers the five implemented gate members. Shape, configuration and compiler refusal may share `validation_failed`; no future gate is invented | Current production path |
| 3 | `visual_id` is copied exactly from the decision. Requested/delivered types and delivered marks are evidence of file delivery, not proof of publication or a human keep rate | Maintainer ruling, 2026-10-29 UTC |
| 4 | `gate_floor_applied` is a nullable boolean: true if an evaluated floor excluded a candidate, false if evaluated floors excluded none, null if no floor was evaluated. The ladder remains disabled by existing config | Producer contract |
| 5 | No query surface. There is no server | Row 55, Guardrail #1 |
| 6 | Attempt `downgrade_depth` means the deepest searched rung, including refusal; copy `deepest_downgrade_depth`, not the selected replacement depth | Existing attempt meaning |
| 7 | Full records stay for the compaction declaration's 14-month window plus its daily tier, then expire with no aggregate or permanent summary. No custom retry feature | Maintainer ruling, 2026-10-29 UTC |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One row per published visual | See decision 1 - it is the failure this row exists to prevent | Fowler |
| 2 | Free-text-only refusal reasons | Typed gates and first validator checks support reliable comparisons without parsing prose | Current contract |
| 3 | Aggregate storage or permanent summary retention | Rejected as waste; full-grain records expire instead | Maintainer ruling, 2026-10-29 UTC |

---

## 5. Row #4 - What a re-render needs, and where a rejected plan lives

- **Scope:** The stored plan and element set a whole-day re-render reads, and a home for a rejected plan's body.
- **Files touched:** `backend/idhazh/assemble.py`, `frontend/public/digest/**` or a `state/` ledger, `backend/idhazh/retention.py`, `config/idhazh.json`, `docs/concepts/adaptive-pruning.md` (the register), `backend/tests/**`, `docs/architecture/publishing/layout.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; export + drift; the full suite; `idhazh site-weight`; `idhazh check-publication`.
- **Oracle:** A published day is re-rendered **from the committed ledger alone**, with no re-run of any model, and the output matches the committed visuals byte for byte. That is the only proof the ledger holds enough.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A CSV cell cannot hold a plan.** Three things already depend on this ledger: a renderer bump re-renders whole days or none, the migration's corpus re-render pass, and the blast-radius query. All three had nothing to read | 12.14 G40, row 35 |
| 2 | Re-rendering needs the **elements** as much as the plan, and the register names no element ledger today. Whether they live in the day payload - registered and never deleted - or in their own ledger is this row's call; what is not open is leaving it unregistered | 12.14 G40 |
| 3 | A **rejected** plan's body is a lookup: it answers no question outside its review window, so it deletes rather than folds, on a short window, with a register row and a sampling ratio in config | 12.7 G10, section 9.2 |
| 4 | The register in `docs/concepts/adaptive-pruning.md` claims to name every artefact this project writes. Each new ledger here gets a row, or that claim is false | Section 9.3 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep only the ledger row | Then a renderer bump can re-render nothing, and the whole-day rule that stops two drawing styles in one scroll is unenforceable | 12.14 G40 |
| 2 | Keep every rejected plan for ever | Unbounded growth for evidence with a review-window life | Carmack |

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - the decision record this group executes.
- [Diagrams deferred](../docs/architecture/publishing/visuals.md#diagrams-deferred) - not a prerequisite for visual telemetry.
- [`20260905-20-visual-console-plan.md`](20260905-20-visual-console-plan.md) - the next plan.
