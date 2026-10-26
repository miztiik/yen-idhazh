# Configurable visual requests and safe fallback

**Last Updated**: 2026-10-25
**Level**: 3 for implementation under the approved persisted design.

## 0. Operating contract

Table A

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Complete the initial visual-request phase without implementing another chart family |
| A2 | Governing contract | [Visual-plan rules and refusal](../docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) |
| A3 | Hard scope - in | Config selection from the full native vocabulary; compiler-aware safe replacement; measured production fallback inputs; persisted requested and delivered outcomes; bounded tests; owning documentation |
| A4 | Hard scope - out | Table B |
| A5 | ESCALATE triggers | Unapproved persisted design or metric; changed question or source facts; unsupported rendering; missing production input silently replaced with empty evidence; any change to the approved Row 1 scope |
| A6 | Chosen strategy | Extend the existing decision and item-health path rather than introduce the later visual-attempt ledger; Fowler consultation, 2026-10-25 UTC |
| A7 | Design approval | the maintainer approved the recorded A1 design and delivery on 2026-10-25 UTC |
| A8 | Execution | One maintainer, one Row 1 implementation PR phase, no parallel rows and no automatic merge authority; Rows 2-5 are complete and Row 6 is collapsed |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries this dependent phase; consult only on a material ambiguity; pause for Level 5 design approval; no automatic merge.

Table B

| ID | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | New chart renderers and text visual types | This phase adds no renderer; Rows 2-5 delivered their chart families and Row 6 was abandoned | A separately approved implementation phase |
| B2 | A new visual-attempt ledger or dashboard | No new visual-specific historical panel | Its separately approved delivery plan; existing item-health retains this phase's outcomes |
| B3 | Historical redraw or inferred outcome backfill | Older rows remain unmeasured | A separate maintainer-approved requirement |
| B4 | Production activation | New policies remain off after delivery | An explicit config activation decision |

## 1. Status Reckoner

Table C

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Configurable visual requests with safe measured fallback | - | A | IN-FLIGHT | chart-vocabulary-plan | - | - |

## 2. Row #1 - Configurable visual requests with safe measured fallback

- **Scope:** Complete the parent phase through the existing request, validation, compilation, recording and ledger paths.
- **Files touched:**
  - `backend/idhazh/contracts/visual_decision.py`
  - `backend/idhazh/contracts/visual_type.py` (new native enum home; old import remains available)
  - `backend/idhazh/contracts/visual_outcome.py` (new shared invariant)
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `backend/idhazh/contracts/visual.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/visual_planner.py`
  - `backend/idhazh/visual_vocabulary.py`
  - `backend/idhazh/visual_population.py` (new)
  - `backend/idhazh/visual_outcomes.py` (new)
  - `backend/idhazh/render/chart.py`
  - `backend/idhazh/render/write.py`
  - `backend/idhazh/render/__init__.py`
  - `backend/idhazh/stages/two_calls.py`
  - `backend/idhazh/stages/work.py`
  - `backend/idhazh/telemetry/record.py`
  - `backend/idhazh/telemetry/events.py`
  - `frontend/src/lib/server/ledger-rows.ts`
  - `frontend/scripts/build-canary.mjs`
  - `config/idhazh.json`
  - `backend/tests/contracts/test_visual_outcomes.py` (new)
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_ledger_columns.py`
  - `backend/tests/contracts/test_panel_queries.py`
  - `backend/tests/contracts/test_visual_reader.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_visual_validator.py`
  - `backend/tests/test_render.py`
  - `backend/tests/test_visual_population.py` (new)
  - `backend/tests/test_chart_vocabulary.py` (new)
  - `tests/fixtures/chart-vocabulary/row1.json` (new)
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/contracts/item-health-row/extract-too-short.json`
  - `tests/fixtures/contracts/item-health-row/published-with-elements.json`
  - `tests/fixtures/contracts/item-health-row/published.json`
  - `tests/fixtures/contracts/item-health-row/summarize-model-unreachable.json`
  - `tests/fixtures/contracts/visual-decision/chart-render-failed.json`
  - `tests/fixtures/contracts/visual-decision/chart-rendered.json`
  - `tests/fixtures/contracts/visual-decision/none-the-gate-refused.json`
  - `tests/fixtures/contracts/visual-decision/none.json`
  - `docs/architecture/publishing/visuals.md`
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
  - `TODO/20261025-chart-vocabulary-row1-plan.md`
- **Acceptance gates:** Locally, use `frontend`'s shared `test:changed` selector, inspect its selection, and run its lint, strict typing, contract bindings and selected tests. During implementation run the named outcome, population, request and fallback tests together. CI owns the full-suite merge gate. No published-page behavior is added in this phase.
- **Oracle:** A bounded recorded request passes through the real request-schema and decision path, then the real ledger writer and reader: an unbuilt magnitude comparison either delivers an exactly source-derived supported replacement or a recorded refusal; a purpose mismatch cannot become bars. Recompute the requested counts and metric from delivered and refused records. This cannot establish the quality of future renderers or reader demand for them.

### Persisted outcomes

Table D

| ID | Field | Meaning |
| --- | --- | --- |
| D1 | `planned_type: VisualType \| None` | The original typed visual request, including one later refused |
| D2 | `rendered_type: VisualType \| None` | The compiled type after its data file was successfully written; this is pipeline delivery, not browser observation |
| D3 | `downgrade_depth: int \| None` | Nonnegative selected replacement depth; zero when no replacement was selected, including a direct refusal |
| D4 | `marks: int \| None` | Actual delivered mark count; positive only after successful writing, not the size of the flat mark pool |

Table E

| ID | Decision | Authority |
| --- | --- | --- |
| E1 | Add Table D fields to `VisualDecision` and append their projection to `ItemHealthRow`. The final decision computes them once; the worker copies them before sealing the item record | Fowler design; the maintainer approval, 2026-10-25 UTC |
| E2 | Defaults are null. Historical payloads remain readable and unmeasured; never infer their requested type, success, depth or count from a historical spec | CLAUDE.md section 11; Fowler proposal |
| E3 | All fields are null without a known typed request. A measured refusal has a requested type and a depth but no delivered type or marks. Direct delivery has equal types and zero depth; replacement delivery has different types and positive depth. A selected depth survives later compile/write failure | Approved design |
| E4 | Existing `rationale`, `none_reason` and `failure_detail` record the cause. A replacement's rationale states the original refusal, the replacement and applied floor; no new free-text reason column | Parent R3; Fowler proposal |
| E5 | Stamp and changelog both changed payload contracts. Keep their old fields readable and synchronise the frontend column-name copy and its bindings | CLAUDE.md sections 9 and 11 |
| E6 | `wasted_decode_rate`: typed measured requests not delivered in their requested form divided by all typed measured requests. A different delivered type or no delivered type counts; empty denominator is null. Exclude declines, unknown/cut/unparseable types and historical unmeasured rows | Maintainer selected A1, 2026-10-25 UTC |
| E7 | Compute the metric and requested-type counts from terminal item records in the shard report; do not persist a second derived measurement or introduce a dashboard | Approved design |

### Config and bounded evidence

Table F

| ID | Config key | Default and behavior |
| --- | --- | --- |
| F1 | `visuals.type_selection_enabled` | `false`; off preserves today's complete grammar and reachability behavior; remove only after maintainer approval makes selection unconditional |
| F2 | `visuals.enabled_types` | Every native `VisualType` value in enum order; nonempty and unique; unruled and unbuilt names remain valid selections |
| F3 | `visuals.downgrade_enabled` | `false`; off performs no history read and no rescue; remove only after maintainer approval makes rescue unconditional |
| F4 | `visuals.downgrade_floor_percentiles` | `[50, 75]`: median mark count at the first replacement depth and the 75th percentile at the second; strictly increasing, nonempty when rescue is on |
| F5 | `visuals.downgrade_lookback_days` | `30` preceding UTC days, excluding the current publication day |
| F6 | `visuals.downgrade_max_samples_per_type` | `256` most recent qualifying rows per target type; positive and config-driven |

Table G

| ID | Decision | Authority |
| --- | --- | --- |
| G1 | Selection constrains the derived request grammar and post-parse membership, not the complete native plan schema. Restrict ruled reachability to selected types; an unruled selected type cannot be proved unreachable from absent rules | Parent R1; Fowler proposal |
| G2 | Carry effective selection into the existing prompt-input fingerprint. Never modify the cached article/system prefix per item to name types | Existing two-call cache contract |
| G3 | At shard start, load the named previous dates through `ledger.load_days` for the existing item-health ledger; never scan published charts, all history or all item artifacts | CLAUDE.md Guardrail 12; Fowler proposal |
| G4 | Use only settled item rows with outcome `OK`, equal known requested/delivered types, zero replacement depth and positive delivered marks. Keep the most recent configured sample count per type by descending `(date, item_ended_at or "", run_id, item_id)` | Existing percentile floor; Fowler proposal |
| G5 | Freeze mark-count tuples once per shard and pass the same mapping through the item decision path. Enabled rescue requires this explicit input; a missing input is an error, not an empty default | Parent bounded production-input requirement |
| G6 | A genuinely empty target population refuses rescue with a reason. Direct deliveries collect evidence while rescue is off; do not create a synthetic seed or infer older outcomes | Existing empty-population refusal contract |
| G7 | Keep two separate default-off switches. State each removal condition on its declaring line; recording outcomes is unconditional | Parent R2 |

### Safe replacement

Table H

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | Consult the same explicit compiler capability used by compilation; only bar is supported in this phase. Trigger rescue for a rejected request or a valid request without a compiler | Parent Row 1 |
| H2 | A supported target must preserve purpose and source references, pass the unchanged universal validator, satisfy its annotation requirement and clear the measured floor. If selection is active, its target must also be selected | Parent R1 and R3 |
| H3 | Remove `stacked_bar -> bar`; a refused declared-whole request must not escape through direct or chained bar fallback | Maintainer R4, already approved |
| H4 | Add `dot -> bar` only for magnitude comparison, without discarded grouping or another undisplayed channel. It provides a real valid-but-unbuilt recovery case without implementing dot rendering | Approved design |
| H5 | Keep other existing purpose-preserving edges only where their actual target remains safe and supported; an unsupported intermediate cannot be returned as drawable | Parent Row 1 |
| H6 | Keep source identity, quantities, ordering, labels and annotations. Do not fill missing channels, invent values, retry the model or force diversity | Parent operating contract |

### Implementation order and evidence

Table I

| ID | Order | Outcome |
| --- | --- | --- |
| I1 | 1 | Approved payload declarations, backward reading and binding tests before any new writer |
| I2 | 2 | Config selection reaches grammar, reachability, fingerprint and parsed-result checks; off behavior stays covered |
| I3 | 3 | Compiler capability and final delivery accounting reach the existing item-health writer before sealing; real ledger round-trip proves persistence |
| I4 | 4 | Bounded historical population is frozen and passed through the production shard; safe fallback and reasoned refusal use it |
| I5 | 5 | Focused fixtures cover direct delivery, unbuilt recovery, purpose mismatch, stacked-bar refusal, empty evidence, failed write and old rows; metric is re-derived from mixed outcomes |
| I6 | 6 | Update owning docs and the assigned Row 1 record, run selected gates, inspect the intended diff and deliver this phase without starting the next |

### Rejected alternatives

Table J

| ID | Option | Why rejected | Cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | New visual-attempt ledger | The existing committed item ledger already carries terminal outcomes | Register and publish a new ledger and add its complete retention/reader path | Fowler sizing |
| J2 | Only count requests yielding no picture as decode waste | Successful fallback would conceal demand for unbuilt requested forms | Maintainer would change the approved metric intent | Maintainer selected A1 |
| J3 | Seed the floor with synthetic or inferred history | It would report unmeasured evidence as published direct outcomes | Maintainer must approve replacing the inherited empirical floor contract | Existing floor contract |
| J4 | Default-on behavior or a shared feature list | It contradicts the reconciled activation ruling | Maintainer must change R2 | Maintainer R2 |
| J5 | Build a replacement chart family in this phase | It combines separate parent outcomes and changes the approved order | Maintainer must approve the enlarged phase | Parent execution contract |
