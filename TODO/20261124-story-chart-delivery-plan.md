# Story chart delivery

**Last Updated**: 2026-11-24
**Level**: 3 for chart tracking and browser presentation; 5 for the reason and source-evidence contracts.

## 0. Operating contract

Table A - Delivery

| ID | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Give readers an intelligible chart grounded in the story, and give operators honest counts and a short explanation of what the model chose. |
| A2 | Hard scope - in | Restore the work-to-assembly boundary and chart counts; fix orientation and labels in the shared browser chart; record a bounded reason in the existing attempt ledger; replace number matching with source evidence in one producer PR. |
| A3 | Hard scope - out | Table B prices the alternatives. |
| A4 | Chosen strategy | Separate counting, presentation, decision explanation, and evidence. Use the reading surface's measured text fit for orientation and the pipeline's existing one-call and assembly boundaries for evidence and delivery. |
| A5 | Execution | Merge this plan to `main` before code. One row per PR. Use one writing slot because every row changes the shared reckoner and the producer rows share the call path. The row changes only its own reckoner line. |
| A6 | ESCALATE triggers | Stop before either Level 5 row writes a contract without design sign-off. Also stop if the change requires another model call, a different model or destination, a wider runtime window, a publisher permission change, a break to current chart readers, or any of the scope changes that [require a decision](../docs/how-to/handle-scope-change.md). |

Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight because the rows update the same reckoner; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0.

Table B - Outside this plan

| ID | Out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Rewriting past editions or backfilling past reasons | A retained chart keeps the evidence available when it was written; known tracking holes and missing explanations stay visible. | A separately scoped correction with retained evidence, an exact edition list and a publication plan. |
| B2 | New timeline renderer, chart quotas, per-story toggles or alternate chart types substituted by code | Some stories can only earn their timeline in prose; a popular chart type may remain popular. | A supported reader need and separate evidence, delivery and design contracts. |
| B3 | New calls, retries, judges, model or window changes | Evidence-poor or over-budget chart requests can still become summary-only. | Measured need after the one-call path is delivered and a separate runtime decision. |
| B4 | New ledger, public reason field or relaxation of commit permissions | Operators use the existing attempt data and may wait for compaction. | A demonstrated need for broader delivery and a named data-access decision. |

## 1. Status Reckoner

Table C - Delivery rows

| ID | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Restore chart tracking | - | A | DONE | shiny-waffle | - | 7d4dc3a9-8ea5-44d3-a6f4-e456abd87961 |
| C2 | 2 | Draw comparisons with matching labels | - | A | DONE | symmetrical-system | - | 1647f5a7-d3f4-4b05-9a47-776083f50bb7 |
| C3 | 3 | Record the model's decision reason | 1 | B | DONE | fuzzy-fishstick | - | 8e587782-d3a9-4a5e-8b41-74632f21dadd |
| C4 | 4 | Ground chart decisions in source evidence | 2, 3 | C | DONE | - | - | - |

## 2. Row #1 - Restore chart tracking

- **Scope:** Let work commit tracking even when it saves a chart, and show separate proposed, worker-saved and published counts by type in the existing Pipelines chart panel.
- **Files touched:**
  - `backend/idhazh/stages/work.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/workflows/test_digest_publication.py`
  - `backend/tests/contracts/test_frontend_console_lists.py`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/lib/server/chart-days.ts`
  - `frontend/src/lib/server/ledger-rows.ts`
  - `frontend/src/lib/console/pipelines/visual-attempts.ts`
  - `frontend/src/lib/console/pipelines/chart-drawing.ts`
  - `frontend/src/lib/console/pipelines/ChartDrawing.svelte`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console-chart-days.spec.ts`
  - `frontend/tests/console-visual-attempts.spec.ts`
  - `frontend/tests/console-charts-rule.spec.ts`
  - `docs/architecture/publishing/how-chart-drawing-is-reported-and-the-rule-it-is-judged-against.md`
  - `docs/architecture/publishing/visuals.md`
  - `TODO/20261124-story-chart-delivery-plan.md`
- **Acceptance gates:** Use `npm run test:changed -- --list` in `frontend/`; run the named receipt, worker/assembly and count cases, applicable lint and types, and integrated console/browser smoke. CI owns the full suite. Observe the next scheduled content refresh after merge by reading the same run's work receipt, attempt row and assembly output; do not dispatch a production writer as a merge gate.
- **Oracle:** For a chart-producing worker, the existing publisher can land the exact `rendered_type` attempt row and cannot land the chart asset; fresh assembly from the item handoff creates the exact asset and names it in the final inventory. Console cases distinguish a known zero from a lost or not-yet-packed cohort. This does not measure chart quality.

Table D - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| D1 | Save worker chart bytes in the run's private scratch, outside the receipt's production roots and outside the uploaded item directory. Keep the serialized decision's bytes, `data_path`, status and attempt identity unchanged. Assembly alone writes the public asset; the receipt and permission checks still reject unrelated unauthorized paths. | Existing work/assembly contract |
| D2 | Use the packed attempt reader for `planned_type` and `rendered_type`; do not serve raw attempts. Label these as counts for the assembled-run cohort. Check per-run distinct settled identities against the decision count in its `run.json`, respect lost, set-aside and unobserved days, and do not infer a type from old untyped rows. A published asset with no corresponding saved attempt in that cohort makes tracking incomplete. A window with any incomplete day does not get a zero or an unlabelled partial total. | Work attempt and assembly run manifest producers |
| D3 | Count published types independently from the final digest's chart references, matching named inventory entries and readable assets of the same item. Use only the selected bounded window. A missing or unreadable expected asset is missing evidence, not a zero. Do not equate proposed minus published with validator refusals. Use existing contracts and a table, not a new ledger or chart. | Publication inventory and console design |

Table E - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Grant work publication authority for charts | Assembly is the public asset owner, and chart files must not leak into worker commits. | A new ownership and concurrency design; it would broaden what work can publish. | Publication boundary |
| E2 | Derive chart types from the digest's generic `chart` token or count only surviving attempts | Neither says what the model proposed or whether unrecorded attempts are missing. | Counts that are quick to display but cannot answer the operator's question. | Existing persisted evidence |

## 3. Row #2 - Draw comparisons with matching labels

- **Scope:** Draw vertical bars and dots when labels and readings fit, use horizontal rows when that reads better, and make the visible labels describe the drawing without changing the chosen marks or type.
- **Files touched:**
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/src/lib/visual/comparison.ts`
  - `frontend/src/lib/visual/ComparisonChart.svelte`
  - `frontend/src/lib/visual/bar.ts`
  - `frontend/src/lib/visual/viewport.ts`
  - `frontend/tests/item-visual.spec.ts`
  - `frontend/tests/visual-legibility.spec.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/how-a-story-chart-is-drawn-and-what-refuses-one.md`
  - `TODO/20261124-story-chart-delivery-plan.md`
- **Acceptance gates:** Use the shared selector with `item-visual.spec.ts` and `visual-legibility.spec.ts`; check one representative chart in the integrated browser at desktop and the existing phone viewport, with one dark-theme check, cross-page smoke and the existing missing-data case. Check console, label/mark pairing, text floor and page overflow. CI owns the full suite.
- **Oracle:** The same comparison draws vertically when the measured columns fit and horizontally when they do not, and both expose the same exact row label, displayed quantity and reported unit without hover. The browser check cannot decide whether a comparison was worth publishing.

Table F - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| F1 | Use vertical bars and dots when the actual drawing area holds each category/series label and exact reading at the existing type floor. Otherwise retain measured horizontal rows; on narrow cards keep the label and value together. Do not rotate or truncate text to win a fit. Preserve bar order, zero baseline, dot-domain disclosure and focus description in either orientation. | Reader design system; chart choice and craft review |
| F2 | Replace the blanket axis caption with labels derived from the drawn channels. For old bar/dot data, row labels and quantity marks are authoritative; their model-written `x` and `y` titles are not reliable measure names. Print exact, unit-bearing readings near their marks or labels, without treating formatted ticks as exact values. If an authoritative name or unit is absent, omit it and report what the producer would need to supply; never infer currency or a measure from prose. Show a series key only when otherwise ambiguous distinct series need it. | Existing chart payload; no Python or prompt change |

Table G - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Force vertical everywhere, or flip at a device breakpoint | Fit depends on content, not the device label. | Wrapped or clipped categorical labels, cramped values or avoidable horizontal charts. | Reader design system |
| G2 | Swap every old `x` and `y` title | Some stored titles already describe the horizontal geometry correctly; swapping blindly keeps the defect. | False measure labels and a payload migration with no reliable input. | Current chart data |

## 4. Row #3 - Record the model's decision reason

- **Scope:** Ask for a short separate explanation in the existing model response and carry it into the existing attempt ledger without affecting the summary or chart decision.
- **Files touched:**
  - `config/prompts/plan-visual.txt`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/stages/summarize_one_item.py`
  - `backend/idhazh/contracts/visual_decision.py`
  - `backend/idhazh/contracts/visual_telemetry.py`
  - `backend/idhazh/telemetry/visual_attempts.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_visual_attempts.py`
  - `backend/tests/test_visual_telemetry.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `backend/tests/gardener/tasks/test_visual_attempt_retention.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `TODO/20261124-story-chart-delivery-plan.md`
- **Acceptance gates:** Obtain Level 5 design sign-off first. Select the named grammar, result, ledger and compaction cases plus applicable lint and types. CI owns the full suite. No change to a reader or production data is part of this row.
- **Oracle:** A recorded chart and a decline each keep their own valid reason after worker projection and Parquet packing; an invalid, missing or cut reason leaves the same otherwise usable chart or summary and a null cell. Recorded replies prove isolation and delivery, not which reasons a live model will write.

Table H - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| H1 | In chart-capable replies, put `model_reason` after `summary` and `visual`, at the top level, and ask for it for both a chart and `null`. Use one plain-text line of at most 20 words, split on whitespace, additionally bounded by the existing untrusted-line character limit. Validate strict text independently from the summary and visual. Recovery may retain a structurally closed visual before an incomplete reason; it must not admit an incomplete visual or a failed summary. Summary-only requests and unfurnished or invalid reasons produce null. | One-call summary recovery and reason requirements |
| H2 | Add nullable `model_reason` to `VisualDecision` and `VisualAttemptRow` only, with dated schema changes, legacy null reads and compatibility through compact Parquet. Update readers before projecting new values in the same PR. Do not change attempt keys, refusal codes or diagnostic prose; do not add the text to public chart data, digest, console data or logs. Treat it as untrusted text, not an instruction, source fact or validator verdict. | Existing work handoff and attempt ledger |

Table I - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Require a valid reason before accepting the response | A late or malformed explanation must not discard an otherwise usable chart or summary. | More lost displays with no additional evidence of correctness. | One-call recovery |
| I2 | Reuse the automated rationale field or refusal code | Code diagnostics and model explanations answer different questions. | Operators lose the ability to distinguish what the model chose from why code refused it. | Attempt record semantics |

## 5. Row #4 - Ground chart decisions in source evidence

- **Scope:** In one producer PR, replace bare value/unit choices with bounded, source-addressed readings and carry selected interpretations through compilation and normal publication.
- **Files touched:**
  - `config/idhazh.json`
  - `config/prompts/plan-visual.txt`
  - `backend/idhazh/ask_text_analysis.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/classify/chart_candidates.py`
  - `backend/idhazh/classify/chart_reply.py`
  - `backend/idhazh/classify/prepare_chart_plan.py`
  - `backend/idhazh/contracts/knobs/visuals.py`
  - `backend/idhazh/contracts/visual.py`
  - `backend/idhazh/contracts/derived.py`
  - `backend/idhazh/contracts/visual_data.py`
  - `backend/idhazh/derived_values.py`
  - `backend/idhazh/render/chart.py`
  - `backend/idhazh/stages/summarize_one_item.py`
  - `backend/idhazh/stages/work.py`
  - `backend/utilities/replay_article_calls.py`
  - `backend/utilities/report_digest_prompt_budget.py`
  - `backend/utilities/prove_the_entry.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_prompt_files.py`
  - `backend/tests/test_chart_vocabulary.py`
  - `backend/tests/test_text_analysis_client.py`
  - `backend/tests/test_derived_values.py`
  - `backend/tests/test_replay_article_calls.py`
  - `backend/tests/test_visual_attempts.py`
  - `backend/tests/test_visual_planner.py`
  - `backend/tests/contracts/test_decoder_grammar.py`
  - `backend/tests/contracts/test_visual_plan.py`
  - `backend/tests/pipeline/_builders.py`
  - `backend/tests/pipeline/test_published_charts.py`
  - `backend/tests/pipeline/test_work_records.py`
  - `backend/tests/support/analysis_service.py`
  - `backend/tests/support/prompts.py`
  - `frontend/src/lib/payload/types.ts`
  - `frontend/src/lib/payload/drawing.ts`
  - `frontend/tests/item-visual.spec.ts`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/publishing/where-every-drawn-figure-came-from.md`
  - `docs/architecture/publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md`
  - `docs/architecture/text-analysis/text-analysis-api.md`
  - `docs/concepts/config/run-limits.md`
  - `TODO/20261124-story-chart-delivery-plan.md`
- **Acceptance gates:** Obtain Level 5 design sign-off first. Use the shared selector for named request, grammar, budget, source, compile and worker-to-reader cases; check applicable lint, types and binding tests. Exercise compact in-memory counterparts of both failures: dates misused as categories with an unsigned decline, and incomparable reference prices; pair them with a genuine time series and a valid comparison. Verify historical chart files still read. CI owns the full suite. A claim about live model judgment needs an artifact-only [retained-article run](../docs/reference/retained-article-verification.md); recorded replies establish only plumbing. Do not claim that judgment from fixture output.
- **Oracle:** Two textually equal readings have different IDs, and the published mark can be followed to the exact selected occurrence and its model-selected sign; a declined or malformed visual still leaves the complete summary usable. The mapping cannot establish whether the model's interpretation was correct.

Table J - Decisions

| ID | Decision | Authority |
| --- | --- | --- |
| J1 | Request existing spaCy sentence offsets and mentions in the same analysis request. Check ranges and text against the exact sanitized article used for summary; ignore unusable spans and preserve usable mentions. Offer deduplicated, contiguous verbatim passages in a separate untrusted block, with short, unique occurrence IDs tied to validated quantity or date elements. Leave the article block unchanged. Select in source order; omit passages that cannot fit as whole sentences rather than dropping qualifiers. Bound the rendered block with `visuals.evidence_max_chars` (default 3,200 characters including IDs and framing) and `visuals.evidence_max_readings` (default 24 quantity/date occurrences); retain the caller's full-request fit check and use summary-only if fewer than two quantities can be offered or the combined request cannot fit. | Existing spaCy service and one-call fit policy |
| J2 | The visual answer is `null` or one already supported type. Use a typed reading reference `{evidence_id, interpretation}` with `as_stated` or `negative_magnitude`, and distinct date IDs for time roles. Name the comparison basis for bar, dot and slope in short model wording; ask for true time roles when chronology is the point and a decline when evidence, direction, unit or comparison basis is unclear. Summary text can guide relevance, not supply a chart fact. Validate only shape, allowed roles, references, safe text and renderability; never infer direction, compare prose for meaning or silently downgrade a rejected type. Remove the old value/unit matcher and duplicate binding. | Source evidence and model responsibilities |
| J3 | `VisualPlan.negative_magnitude_element_ids` is an optional/default-empty set of cited quantity element IDs. One reading has one interpretation within a plan. The compiler applies `-abs` to the exact decimal selected by the model, with source wording and element ID retained in `DerivedFunction.negative_magnitude`. If the existing exact unit normalization is required, the same one-input chain names its source unit and conversion table; otherwise both are absent. Existing positivity and renderability checks still apply to the compiled values. Version the plan and visual-data contracts, extend the reader guard before the new producer writes, and keep the rendering format and currently readable assets compatible. Do not publish evidence passages or IDs from the request. | Existing visual and arithmetic provenance contracts |

Table K - Rejected alternatives

| ID | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Inline source markers or a second call over an indexed article | Markers can leak into the summary; a second call repeats input and can exhaust the item budget. [HiLight](https://arxiv.org/abs/2604.22565v2) motivates pointing at evidence, not changing the article. The separate block is not attention isolation. | Summary regressions or another inference and runtime budget. | One-call and summary requirements |
| K2 | Infer signs, units, dates or comparison suitability from Python rules | Spans locate words; they do not prove which reading answers the question. | A second editorial engine with opaque errors and unsupported guesses. | Source and model responsibility boundary |
