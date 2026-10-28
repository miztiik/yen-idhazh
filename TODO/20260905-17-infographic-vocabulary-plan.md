# 17 - Source text and the whowhat grid

**Last Updated**: 2026-10-28
**Level**: 5 (Row 3 adds a persisted `WhowhatGridData` payload; Row 1 is independently executable)

**Chain**: the composition family is delivered in [the visual-plan rules](../docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) | diagrams are [deferred](../docs/architecture/publishing/visuals.md#diagrams-deferred).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - row 41, 12.11 G18, 12.13 G33, 14.3, P.L32.

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates each implementation row to a nested worker in its own worktree and pull request; dispatch Row 1 first; dispatch Row 3 only after Row 1 is DONE; keep Parallel N = 1 because Row 3 depends on Row 1; consult a persona only where two answers would lead to different code; leave implementation pull requests open for review and merge only with explicit user authorization; honor section 0 ESCALATE triggers.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Stories without a series or breakdown still need source-preserving text fit and an evidence-backed one-attribute actor/claim grid. |
| Hard scope - in | Row 1: deterministic source-prefix truncation with an appended `...`. Row 3: a one-attribute `whowhat` grid with same-sentence evidence, in a separate persisted `WhowhatGridData` format and reader. |
| Hard scope - out | See the scope-out table below. |
| ESCALATE triggers | 1. Row 1 proposes model rewriting instead of deterministic source-prefix truncation. 2. Row 3 cannot prove each filled cell from source spans in one sentence. 3. Row 3 would change the existing chart `VisualData` payload or its renderer version, or send grid decisions through `write_charts_from_decisions()`. |
| Chosen strategy | Rows 1 and 3 are approved for delivery by user ruling, 2026-10-27; their status stays PENDING until each implementation pull request is complete. Deliver Row 1 first, then Row 3 in its own pull request after Row 1 is DONE. Row 3 uses a separate versioned `WhowhatGridData` contract, writer and browser reader. Keep chart `VisualData`, its renderer version and its reader unchanged. |
| Execution | Autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 1 because Row 3 depends on Row 1; no further design ruling is pending. |

| Out of scope | Cost of leaving it out | What would bring it in |
| --- | --- | --- |
| Row 2 callout card; collapsed below | No single-figure callout ships; readers rely on the story text and existing visuals. | A new user ruling with an objective, article-verifiable selection rule. Model judgment and ranking are not substitutes. |
| Row 4 `keyfacts` card; collapsed below | No standalone `keyfacts` visual ships; summary fields remain unchanged. | A new explicit user ruling. No reason for the abandonment was recorded. |
| Diagrams | Diagram forms remain in the next plan. | Work scoped and authorized in the diagram plan. |
| Changes to `key_points` | The summary field and its current behavior remain unchanged. | A separate user-approved scope and plan. |
| Model rewriting of claims or quotes | Long text is clipped rather than paraphrased, so some wording is not shown in full. | A new user ruling and a separately checked source-attribution design. |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A real sentence made to fit, without anyone re-writing it | - | A | PENDING | plan-17-row-1-labels | - | - |
| 2 | One striking figure: callout | - | - | COLLAPSED | - | - | - |
| 3 | Who did what: whowhat | 1 | B | PENDING | - | - | - |
| 4 | Three to five takeaways, and the switch that kills them | - | - | COLLAPSED | - | - | - |

---

## 2. Row #1 - A real sentence made to fit, without anyone re-writing it

- **Scope:** Where a source-backed chart label must be shortened to fit, the compiler truncates deterministically and appends `...`. The model never rewrites it.
- **Files touched:**
  - `backend/idhazh/render/chart.py`
  - `backend/idhazh/text_fit.py` (new)
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `config/idhazh.json`
  - `backend/tests/test_chart_text_fit.py` (new)
  - `backend/tests/contracts/_fixtures.py`
  - `tests/fixtures/visual-validator/articles/text-fit.txt` (new)
  - `tests/fixtures/visual-validator/articles/text-fit-collision.txt` (new)
  - `tests/fixtures/visual-validator/tables/text-fit.json` (new)
  - `tests/fixtures/visual-validator/tables/text-fit-collision.json` (new)
  - `tests/fixtures/visual-validator/plans/text-fit.json` (new)
  - `tests/fixtures/visual-validator/plans/text-fit-collision-bar.json` (new)
  - `tests/fixtures/visual-validator/plans/text-fit-collision-line.json` (new)
  - `tests/fixtures/contracts/visual-data/text-fit.json` (new)
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `frontend/src/lib/visual/bar.ts`
  - `frontend/tests/item-visual.spec.ts`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
  - `docs/concepts/design-system.md`
- **Acceptance gates:** Local: inspect the shared selection with `npm run test:changed -- --list`, run `npm run test:changed` and `npm run check`, and complete the section 12 browser smoke. CI: full backend and frontend suites.
- **Oracle:** Repeated compilation gives the same output. For truncated output, removing the appended `...` leaves a prefix of the exact source span; otherwise the output equals that full span. Distinct labels that collide after shortening refuse the chart. Stacked-bar labels remain uncapped. This proves source fidelity and determinism, not that the published reader gives the text enough space; the browser smoke checks the rendered result.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **A cap rejects; truncation renders.** `summarize.max_verbatim_words` governs summary reuse, not the display length of a source-backed chart label. | 12.11 G18, section 14.3 |
| 2 | Plan 11 makes claims and quotes sentence-index-only, so source sentences remain the unit; text fitting preserves their wording. | 12.11 G18 |
| 3 | Model rewriting is not allowed; rewritten output cannot be checked by the source-prefix oracle. | P.L32, 12.11 G18 |
| 4 | A chart-independent helper owns deterministic prefix-plus-ellipsis fitting so later compilers can reuse it without importing chart code. Row 1 does not implement grid behavior. | User ruling, 2026-10-28 |
| 5 | Refuse a chart when distinct source labels become identical after shortening. | User ruling |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Let the model shorten the sentence | Rewritten words cannot be verified by checking that the visible text is a source prefix. | It loses direct source attribution; retaining it would require a separate check for every changed word. | Andre |
| 2 | Refuse anything that does not fit | Real sentences are rarely card-shaped, so the family would almost never fire. | Eligible spans beyond the configured boundary disappear; their count in the fixed fixture corpus measures the loss. | Editor |

---

## 3. Collapsed row #2 - One striking figure: callout

- **Status:** COLLAPSED; not executable.
- **Ruling:** User ruling, 2026-10-27: choosing a singular callout figure requires subjective selection. Model judgment and ranking are not substitutes.

---

## 4. Row #3 - Who did what: whowhat

- **Scope:** Deliver `whowhat` as a one-attribute actor/claim grid. Every populated cell must come from entity and claim spans in the same sentence. Store it in the separate versioned `WhowhatGridData` format at the item's existing `DigestVisual.data_path`. Reuse `asset_relpath()` and atomic-write behavior, but route `WHOWHAT` decisions through a dedicated grid writer, not `write_charts_from_decisions()`. Project `DigestVisual.kind` to a new `WhowhatVisual` browser reader; a served visual without `kind` keeps the existing chart path. Leave chart `VisualData`, its renderer version and chart reader unchanged. Bump `PLAN_VOCABULARY_VERSION` when the `WHOWHAT` rules become active.
- **Files touched:**
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/digest_day.py`
  - `backend/idhazh/contracts/digest_view.py`
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `backend/idhazh/contracts/visual_decision.py`
  - `backend/idhazh/contracts/whowhat_grid.py` (new)
  - `backend/idhazh/render/__init__.py`
  - `backend/idhazh/render/whowhat_grid.py` (new)
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/two_calls.py`
  - `backend/idhazh/visual_planner.py`
  - `backend/idhazh/visual_vocabulary.py`
  - `backend/idhazh/visual_validator.py`
  - `config/idhazh.json`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_served_day.py`
  - `backend/tests/contracts/test_whowhat_grid.py` (new)
  - `backend/tests/pipeline/test_published_whowhat_grids.py` (new)
  - `backend/tests/test_canary_day.py`
  - `backend/tests/test_render.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/test_visual_validator.py`
  - `backend/tests/test_whowhat_grid.py` (new)
  - `tests/fixtures/contracts/whowhat-grid/whowhat.json` (new)
  - `tests/fixtures/visual-validator/articles/whowhat.txt` (new)
  - `tests/fixtures/visual-validator/plans/whowhat.json` (new)
  - `tests/fixtures/visual-validator/tables/whowhat.json` (new)
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/src/lib/payload/whowhat-grid.ts` (new)
  - `frontend/src/lib/payload/project.ts`
  - `frontend/src/lib/payload/types.ts`
  - `frontend/src/lib/visual/WhowhatVisual.svelte` (new)
  - `frontend/tests/item-visual.spec.ts`
  - `frontend/tests/visual-legibility.spec.ts`
  - `frontend/tests/whowhat-visual.spec.ts` (new)
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
  - `docs/architecture/publishing/where-a-drawing-becomes-pixels.md`
  - `docs/architecture/publishing/visuals.md`
  - `docs/concepts/design-system.md`
- **Existing code reused:** `backend/idhazh/render/write.py` provides `asset_relpath()` and `write_bytes_atomic()`. Assembly sends chart decisions only to `write_charts_from_decisions()` and sends `WHOWHAT` decisions only to the dedicated grid writer.
- **Versioning:** Give `WhowhatGridData` its own date-stamped version and changelog; stamp and changelog changes to `VisualDecision`, `DigestDay` and `DigestView`. Bump `PLAN_VOCABULARY_VERSION` when the `WHOWHAT` rules become active.
- **Acceptance gates:** After Row 1 is DONE, inspect the shared selection with `npm run test:changed -- --list`, run `npm run test:changed` and `npm run check`, including the new grid-contract tests. CI: full backend and frontend suites plus applicable payload and bundle gates. Complete the section 12 browser smoke.
- **Oracle:** Every populated cell pairs entity and claim spans from the same sentence and re-slices both against the fixture article; a cell without that pair is empty. Grid files validate against `WhowhatGridData` and its reader. Grid decisions never pass through the chart writer. Existing chart files continue through `VisualData`, its unchanged renderer version and its unchanged reader.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The reader shows one-attribute actor/claim pairs as a comparison grid, not a bespoke actor-role template. | Row 41 |
| 2 | The same-sentence rule stops the grid asserting that an actor said something they did not. | Row 41 |
| 3 | The displayed grid is rectangular; it does not assume the persisted shape of the abandoned Row 6 comparison type. | 12.13 G33 |
| 4 | A2: store grids in a separate versioned `WhowhatGridData` payload and use a dedicated writer and `WhowhatVisual` browser reader. Reuse the item's existing `DigestVisual.data_path`, `asset_relpath()` and atomic-write behavior, without routing grid decisions through `write_charts_from_decisions()`. Keep chart `VisualData`, its renderer version and its reader unchanged. | User ruling, 2026-10-27; read-only architecture refinement |
| 5 | Project `DigestVisual.kind` so `WHOWHAT` reaches its reader; an older served visual with no `kind` keeps the chart path. Bump `PLAN_VOCABULARY_VERSION` when the `WHOWHAT` rules become active. | Read-only architecture refinement |

### Rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Add a text-grid variant to `VisualData` | Grid cells are text, while the existing chart payload requires measured quantities for emphasis. The user chose a separate format to keep the chart payload and renderer version unchanged. | It would require stored-shape and reader-version changes, causing the current reader to refuse older chart files while leaving their story text intact. | User ruling, 2026-10-27 |
| 2 | A bespoke actor-role template | It adds a second grid engine for one purpose, against the shared comparison-grid presentation. | It adds another renderer and test path; count the new branches and tests against the shared grid before taking it. | Jony |

---

## 5. Collapsed row #4 - Three to five takeaways, and the switch that kills them

- **Status:** COLLAPSED; not executable.
- **Ruling:** User ruling, 2026-10-27. The user abandoned this row; no reason was recorded.

---

## See also

- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - source decisions for the retained rows.
- [Composition chart rules](../docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md) - the delivered composition family.
- [Diagrams deferred](../docs/architecture/publishing/visuals.md#diagrams-deferred) - current scope and retained reader intent.
