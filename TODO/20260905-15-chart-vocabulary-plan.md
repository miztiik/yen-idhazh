# 15 - Charts, plus the two the reader asked for

**Last Updated**: 2026-10-25
**Level**: 5 for persisted-contract design; 3 for the approved implementation sequence.

**Chain**: previous work delivered in the [chart contract](../docs/architecture/publishing/where-a-drawing-becomes-pixels.md) | next [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md).
**Reference**: [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - O13, rows 38, 39, 41, 48, 49, sections 7.2, 12.8 X1, 12.12 G26.

The maintainer authorised Row 1 planning and delivery on 2026-10-25 UTC and
approved its [concrete delivery design](20261025-chart-vocabulary-row1-plan.md),
including the requested-versus-delivered metric. On 2026-10-25, the maintainer
authorised execution of the remaining rows. Follow the current
[execution guide](../docs/how-to/execute-a-plan.md); any further persisted-design
change beyond the plan's approved scope still requires maintainer approval under
CLAUDE.md section 6.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Story publication supports bars. Shared D3 renderers and source-span extraction exist elsewhere, but they do not complete the other story types. Reuse those foundations to answer each story's question with a suitable visual |
| Hard scope - in | Config selects from the full declared vocabulary; code owns correctness rules. Complete story delivery for `bar`, `dot`, `slope`, `line`, `scatter`, `stacked_bar`, `comparison` and `quotecard`. Record safe fallback or refusal |
| Hard scope - out | `area` pending a separately approved source-evidence design. `pie`, `bubble`, `histogram` and derived-value producers (plan 16). `callout`, `whowhat`, `keyfacts` (plan 17). Diagrams (plan 18). Any change to the validator's universal checks |
| ESCALATE triggers | 1. A type without validator rules and a supported compiler is allowed to render. It may be named, not rendered. 2. Requested/rendered accounting cannot compute `wasted_decode_rate`. 3. A fallback changes the question or facts. 4. Any further scope, functionality or acceptance change is proposed, however small |
| Chosen strategy | Declare the whole vocabulary, build the families in order of what the planner actually chooses, and make a day that would otherwise be one shape impossible |
| Execution | One meaningful PR phase per row, in the dependency order below, after execution approval. No fixed worker count or automatic merge instruction |

**The rule that prevents misleading repetition.** A bar fallback is allowed
only for a magnitude comparison. A supported replacement must preserve the
question and source facts and pass the target's validation. Otherwise the story
retains its text without a visual, with the reason recorded. A type-diversity
quota must never force an unsuitable visual.

### Maintainer-approved reconciliation

The maintainer approved these decisions on 2026-10-25 UTC in this session:

| ID | Decision | Change from the September plan |
| --- | --- | --- |
| R1 | Config selects types; code validates names and owns correctness rules | Retains config control; reconcile the current code-only vocabulary documentation before implementation |
| R2 | Separate default-off switches | Replaces default-on features controlled by one `disabled_features` list. Agree and document each switch's declaring line and removal condition |
| R3 | Safe supported replacement or no visual, with the reason recorded | Removes the guarantee that every unbuilt type has a rendered neighbour |
| R4 | A stacked bar that fails its declared-whole check leaves text without a visual | Removes grouped-bar fallback and its grouping implementation from this plan |
| R5 | Focused integration checks plus representative browser coverage | Replaces every-type browser checks at both widths; retain source-derived correctness and width behavior checks below the browser tier |
| R6 | Bounded mixed fixture only | Removes the real committed-day diversity demonstration and its release evidence step |
| R7 | D3.js; no prerendering; shared reusable patterns; no magic numbers | Explicit user requirements. No separate chart engine, build-time drawing, per-page special cases or source-fixed tunables |
| R8 | Row 3 delivers `line` only; `area` is deferred to a separately approved phase | Owner decision 2026-10-25; the current free-form measure label cannot prove stock or cumulative magnitude rather than a rate |

No other scope or functionality change is approved. Existing current-renderer-only
chart compatibility follows the maintainer ruling already in CLAUDE.md section 11;
this plan does not restore historical redraw or migration machinery.

### Shared implementation and evidence rules

- Use the Data explorer's shared chart-builder/component pattern, not a second
  story-only chart engine. Its current composition is
  `frontend/src/lib/console/explorer/ShapePanel.svelte`; shared D3 builders live
  under `frontend/src/lib/charts/d3/`.
- Reuse geometry, scales, formatting, measured width, typography and tokens.
  Reuse does not import a consumer's unsuitable data policy: dropping scatter
  pairs or summing supplied parts is not valid story evidence.
- Put tunable appearance and behavior in shared validated config/tokens.
  Naming a source literal does not make it configurable. Do not expand this
  work into a whole-site cleanup.
- Render visuals in the browser from validated published data. Do not add
  build-time SVG/image output or restore retired prerendering.
- Keep native payload ownership, current schema stamps, changelogs and binding
  tests. Follow the chart compatibility exception, not an obsolete migration
  assumption. Config selection must remain bound to the native type names.
- Use named bounded fixtures loaded inside tests. Derive geometry expectations
  from source elements, not snapshots of the current drawing. Keep width
  behavior evidence for the original narrow/wide cases below the browser tier;
  read their dimensions from shared test configuration.
- Use the current shared test selector and gates in
  [run-the-gates](../docs/how-to/run-the-gates.md). Replace retired export/drift
  commands with current on-demand schema and binding checks, not a weaker
  contract-consistency obligation. CI owns the full-suite merge gate.
- Browser rendering and interaction use representative coverage under
  CLAUDE.md section 13, plus section 12 smoke when the site changes.
- The inherited legibility and density floors remain obligations. Resolve their
  current canonical definitions before implementation; do not invent a density
  threshold or substitute a minimum point count. Removing or changing either
  floor requires maintainer approval.
- Other inherited whole-day correctness obligations remain. Maintainer R6 removes
  the real-day diversity proof, not unrelated publication or correctness rules.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The whole vocabulary is declarable, and an unbuilt type steps down | - | A | DONE | chart-vocabulary-plan | - | - |
| 2 | Position and length: bar, dot, slope | 1 | B | DONE | supreme-sniffle / chart-position-and-length | #1738 | Copilot session 6c107b16-1860-4e47-9bba-c8b401dd96e7 |
| 3 | Trend and magnitude: line, area | 2 | C | PENDING | - | - | - |
| 4 | Relationship: scatter | 3 | D | PENDING | - | - | - |
| 5 | Parts as bars: stacked_bar, with its own question | 4 | E | PENDING | - | - | - |
| 6 | The two the reader asked for | 5 | F | PENDING | - | - | - |

Row 1 is authorised and in flight under the
[approved delivery design](20261025-chart-vocabulary-row1-plan.md).
Other rows remain PENDING. Existing parts are reuse evidence, not completed
end-to-end delivery.

### Current delivery evidence

Susan reviewed the current code on 2026-10-25 UTC. These are inspected
implementation/test references, not a claim that tests were run.

| ID | Row | Existing parts | Remaining delivery |
| --- | --- | --- | --- |
| E1 | 1 | Type enum in `backend/idhazh/contracts/visual.py`; rules/edges in `backend/idhazh/visual_vocabulary.py`; validator and ladder tests | Config selection, bounded production fallback input, compiler-aware replacement, requested/rendered accounting and metric. `backend/idhazh/stages/two_calls.py` passes an empty floor population; shipped config disables the ladder |
| E2 | 2 | Story bar compiler in `backend/idhazh/render/chart.py`, reader guard in `frontend/src/lib/payload/drawing.ts`, drawing in `frontend/src/lib/visual/bar.ts` and `frontend/src/lib/components/ItemVisual.svelte`; compiler and publication tests | Dot and slope story delivery; shared configurable geometry. Console `rankedList.ts` is bars, not dots; `paired.ts` is normalised before/after comparison, not the required slope |
| E3 | 3 | Time/quantity role rules; shared `frontend/src/lib/charts/d3/dateSeries.ts` | Story line/area compilation and rendering; stock/cumulative-versus-rate evidence and refusal. A spread band is not the required cumulative-area chart |
| E4 | 4 | Scatter role rules and `frontend/src/lib/charts/d3/pairedScatter.ts` | Required relationship purpose, complete entity pairs, story compilation and rendering. Shared scatter omission of incomplete pairs must not bypass story refusal |
| E5 | 5 | Stacked-bar role rule; stacking in `frontend/src/lib/charts/d3/partsOfOne.ts` | Independently declared-whole evidence and exhaustiveness validation; story compilation/rendering; recorded text-only outcome on refusal. Summing the supplied parts is not proof of the whole |
| E6 | 6 | Quote/claim source ranges in `backend/idhazh/classify/calls.py`; shared item typography and loading | Comparison/quote rules, suitable published payloads, browser markup, source re-slicing and bounded mixed-fixture evidence. The current measured-quantity payload is not a text-only quote contract |

---

## 2. Row #1 - The whole vocabulary is declarable, and an unbuilt type steps down

- **Scope:** Config selects from the full vocabulary, validated against native type names. An unbuilt type remains declarable. Choose a supported replacement deterministically only when it preserves purpose and facts and passes target validation; otherwise retain text without a visual. Record the reason and both requested and rendered outcomes. Supply bounded production inputs rather than an empty floor population.
- **Current files:** `config/idhazh.json`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/visual.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/stages/two_calls.py`, named fixtures/tests and the current vocabulary/config documentation.
- **Acceptance gates:** Current selected lint, strict type, config, schema and binding checks; bounded integration evidence; full suite in CI.
- **Oracle:** A fixture requesting an unbuilt type records the request and either a safe supported replacement or a reasoned no-visual outcome. A separate purpose-mismatch fixture proves that bar fallback is refused. `wasted_decode_rate` is defined in the owning contract/doc and computable from recorded outcomes, including refused outcomes; do not invent a new formula silently.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Full vocabulary selectable in config.** Config selection is validated against native names; code owns correctness rules. Declared-but-unbuilt types remain possible | 12.8 X1; maintainer R1 |
| 2 | This does not cross the non-goal about types arriving without rules. **That governs what may render; this governs what may be named.** An unbuilt type never reaches a reader | 12.8 X1 |
| 3 | Record observed requested-type frequency to inform build order. Keep this plan's dependency order unless the maintainer approves a change; counts do not authorise dropping a family | Row 48; section 0 |
| 4 | `planned_type` and `rendered_type` are both recorded, always | Row 48, P.D2 |
| 5 | **Separate default-off switches.** Document activation behavior and a removal condition for each switch; this plan update enables nothing | Maintainer R2, replacing O15's switch model |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Restrict the enum to built types | Makes the downgrade unreachable and the metric identically zero, and refutes the rule that derives the build order | 12.8 X1 |
| 2 | Hardcode the list in Python | Guardrail #6 | Fowler |

---

## 3. Row #2 - Position and length: bar, dot, slope

- **Scope:** Complete bar, dot and slope through source data, validation, compilation and browser rendering. Reuse the existing story bar and shared D3 patterns instead of three bespoke page implementations.
- **Current files:** `backend/idhazh/render/chart.py`, `backend/idhazh/visual_vocabulary.py`, applicable native published contracts, `frontend/src/lib/payload/drawing.ts`, `frontend/src/lib/visual/bar.ts`, `frontend/src/lib/charts/d3/`, `frontend/src/lib/components/ItemVisual.svelte`, named tests and current chart/design docs.
- **Acceptance gates:** Current frontend check, build and bundle gate; native-reader bindings; both inherited legibility/density floors; representative browser coverage and section 12 smoke.
- **Oracle:** For each type, focused integration tests re-derive geometry from bounded source elements and check drawn attributes and narrow/wide behavior. Representative browser evidence checks actual browser integration. Do not multiply browser cases by type and width (maintainer R5).

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

- **Scope:** `line` for a trend over time. Complete source evidence, validation, compilation and browser drawing using shared D3 date/series patterns. `area` is deferred to a separately approved phase under owner decision R8.
- **Current files:** `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/render/chart.py`, applicable native contracts, `frontend/src/lib/charts/d3/dateSeries.ts`, shared reader/drawing components, named fixtures/tests and current chart docs.
- **Acceptance gates:** as row 2.
- **Oracle:** A line plan with unordered categories or a non-date time element is refused by the validator; a valid date/quantity series compiles to source-backed marks and draws in the browser.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A time axis needs the `date` kind, which plan 08 built. A trend over unordered categories is a bar | Plan 08 |
| 2 | `area` may draw only when source evidence proves a stock or cumulative measure, never a rate. This evidence rule is not implemented in Row 3 | Section 7.2; owner decision R8 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Infer the area gate from the current free-form measure label | It cannot prove that a measure is a stock or cumulative total, or catch every rate | Owner decision R8 |

---

## 5. Row #4 - Relationship: scatter

- **Scope:** `scatter` for two measures over a shared set of entities, with required relationship purpose and complete pairs. Validate before reusing shared D3 scatter geometry; do not inherit incomplete-pair filtering.
- **Current files:** `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/render/chart.py`, applicable native contracts, `frontend/src/lib/charts/d3/pairedScatter.ts`, shared reader/drawing components, named fixtures/tests and current chart docs.
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

- **Scope:** `stacked_bar` with **its own** exhaustiveness gate against an independently declared whole, not merely as the thing `pie` falls back to. Reuse shared D3 stacking, not a computed sum as evidence of completeness.
- **Current files:** `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/render/chart.py`, applicable native contracts, `frontend/src/lib/charts/d3/partsOfOne.ts`, shared reader/drawing components, named fixtures/tests and current chart docs.
- **Acceptance gates:** as row 2.
- **Oracle:** A `stacked_bar` whose parts are not exhaustive against a **declared** whole is refused, records the reason and retains story text without a visual. Test direct requests and an upstream fallback so refusal cannot be bypassed. Grouped-bar fallback is removed by maintainer R4.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **`stacked_bar` has its own gate.** Without one, a `pie` refused for summing its whole rather than reading a declared one lands in a `stacked_bar` that never re-asks the question, and the refusal buys nothing | 12.12 G26 |
| 2 | This is the shape the downgrade ladder's re-validation rule needs: a downgrade target with no predicate makes re-entering the validator pointless | 12.7 G8, 12.12 G26 |
| 3 | Failed declared-whole validation produces no visual, not grouped bars | Maintainer R4 |

### Rejected alternatives

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Treat it only as pie's fallback | Then the refusal is laundered into a different drawing of the same wrong claim | Fowler |

---

## 7. Row #6 - The two the reader asked for

- **Scope:** `comparison` - a rectangular grid of span-anchored cells - and `quotecard`, restricted to a quote the semantic pass identified. Use shared typography and typeset browser markup, with native payloads suitable for text rather than fake measured quantities.
- **Current files:** `backend/idhazh/classify/calls.py`, `backend/idhazh/visual_vocabulary.py`, `backend/idhazh/visual_validator.py`, `backend/idhazh/contracts/visual_data.py`, publication/reader boundaries, shared item markup and typography, named fixtures/tests and current chart/design docs.
- **Acceptance gates:** as row 2, plus a bounded mixed fixture. The real committed-day demonstration and recurring mutable-data check are removed by maintainer R6.
- **Oracle:** A bounded mixed fixture proves more than one rendered type without forcing unsuitable visuals. Every `quotecard` renders a quote whose span slices to the drawn text from the article's own bytes - re-sliced in the test, not compared to a stored string.

### Decisions

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These two are pulled forward from the infographic plan **specifically** so the first vocabulary plan cannot publish a wall of bars. The reader named these two as the ones they would actually want | Susan, Reader, 2026-09-05 |
| 2 | `quotecard` is restricted to quotes the semantic pass identified and capped at `summarize.max_verbatim_words`. It is **not** applied to every article | O13, row 39 |
| 3 | Jony dissents on `quotecard` as craft - "one sentence in a bigger font with a border". The maintainer overruled, and the dissent is recorded rather than erased | Row 39, section 4.F |
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
- [`20260905-16-composition-vocabulary-plan.md`](20260905-16-composition-vocabulary-plan.md) - the next plan.
