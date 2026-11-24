# Trial the content-similarity judge charts in production

**Last Updated**: 2026-11-24
**Level**: 3 - the Console adds bounded reads of already published data; no persisted ledger or producer changes.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Give the operator a short production trial that shows what the judge answered, where the sample came from, and where score decisions agreed with it. |
| A2 | Hard scope - in | The ten individual drawings in Table B, including the existing PSI line and three separate verdict heatmaps; one shared UTC digest selection; a reversible Pages release and removal after use. |
| A3 | Chosen strategy | Separate the full draw from recorded verdicts and the full eligible pool. Native static reads, browser-only drawing, and one trial switch keep the views removable. Susan owns presentation; the existing Council contracts own the evidence. |
| A4 | Authorities | The [Console surface](../docs/architecture/publishing/console.md#judgement-draws-the-published-merges-and-the-holdout-labels), [published read boundary](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md), [judge measurements](../docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md#what-threshold-history-stores), and [chart vocabulary](../docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md) govern the rows below. The plan changes decisions in those living pages with the corresponding code, not by treating this plan as a runtime contract. |
| A5 | Identity and availability | Reuse the current latest run then greatest attempt per UTC digest; all date details and pair reads must match that exact `(date, run_id, attempt)`. Keep loading, failed read, not yet packed, not recorded, no eligible evidence, and measured zero distinct. Do not select an older attempt to fill a gap. Data in other charts stays visible when one source fails. |
| A6 | Invariants | No change to model calls, sampling, fitted bounds, article grouping, production gates, source consent, compaction, or archive destination. Read only staged compact Parquet using the panel door and declared columns. Do not expose URLs, pair keys, or article content in the chart or logs. |
| A7 | ESCALATE triggers | 1. A chart requires a new persisted writer, ledger field or trust-boundary change.<br>2. Staged data cannot support a requested definition without substituting a cohort.<br>3. The bounded read cannot fit the existing site budget or a new dependency is required.<br>4. A scope change, unresolved design conflict or cost overrun meets the execution contract's pause rule. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates where it pays; parallel N = 1 because all rows edit the same route, docs and Reckoner; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

Table B - Chart inventory (ten individual drawings; existing daily coverage stays)

| Id | No. | Chart type and question | Grain and source | Row |
| --- | ---: | --- | --- | --- |
| B1 | 1 | **100% stacked horizontal bar chart** - What came back in each original score slice? | Selected digest, all pairs drawn per saved slice in `threshold-history`. | 1 |
| B2 | 2 | **Date x score-band YES heatmap** - Where did both orders say same story? | UTC digest and fixed score band, recorded exact-attempt `pair-verdicts`. | 2 |
| B3 | 3 | **Date x score-band NO heatmap** - Where did both orders say different stories? | Same cohort as B2. | 2 |
| B4 | 4 | **Date x score-band split heatmap** - Where did reversing the order change the answer? | Same cohort as B2; split is not an agreed `UNCLEAR`. | 2 |
| B5 | 5 | **Score-by-date interval plot with three-color ticks and stepped bounds** - Where was the draw, how large was it, and what did it return? | Window, actual saved slice edges and bounds in `threshold-history`. | 1 |
| B6 | 6 | **3 x 3 agreement matrix** - How do the judge outcomes line up with the pipeline score zones? | Selected digest, exact `pair-verdicts` and recorded in-force bounds; no claim about published grouping or human truth. | 3 |
| B7 | 7 | **Full-pool histogram** - Where did the scores fall before any sampling? | Selected digest, stored `score_pool_histogram` counts and edges from `threshold-history`. | 4 |
| B8 | 8 | **PSI line chart with gaps** - How far did the full pool move from its saved reference? | Window, stored `score_psi`; retains the existing line and guides and links its selected digest to B7. | 4 |
| B9 | 9 | **Precision-recall scatterplot with filled cutoff markers** - What would another cutoff trade away? | Point in time: one selected UTC digest and exact attempt, agreed binary `pair-verdicts` only. | 3 |
| B10 | 10 | **Shannon entropy heatmap** - Where does the mix of YES, MAYBE and NO spread across outcomes? | Same time/band grid as B2, using only two valid orders per pair. | 2 |

Table C - Metrics inventory beyond the drawings

| Id | Metric family | Disposition in this trial |
| --- | --- | --- |
| C1 | Ranked agreement: average precision, F0.5, precision and achieved recall at the saved 90% recall point | Add to the selected-date cutoff readout. Use the existing saved values, not another trend. Keep reporting- and upper-cutoff disagreement, precision, recall and hard-decision Brier alongside. |
| C2 | Fit provenance: lower and upper estimates, fitted window and usable pairs, hold reason and step limit | Show these in the selected-date interval readout alongside the bounds used and decided. The curve coefficients and weighted head/tail estimates stay in Data explorer; the tails can have very little judged support. |
| C3 | Sample and runner health: draws, returns, valid pairs, split, unclear, refusals, unreadable, deadline losses and runner coverage | Keep the daily coverage plot and current readout. Decode time in total and for the slowest runner are stored, not charted in this trial. |
| C4 | Repeatability diagnostics: first-token margin and probabilities, pair-order split rates, grammar and decode evidence | B4 shows where splits occur; a margin-versus-split plot and per-pair diagnostic details stay outside this chart count. Their source is `pair-verdicts`. |
| C5 | Drift and probability checks: baseline source dates, binned KS and Wasserstein, prior-fit Brier, comparison Brier and expected calibration error | Keep the drift distances with B8 and prior-fit metrics with their existing selected-date support and unavailable reasons. Do not draw metrics that were not measured. |
| C6 | Known-answer controls: expected key, both orders, match count and kappa | Keep the existing detailed list with support. The saved model-labelled key is not a human reference set. |

Table D - Scope boundaries

| Id | What stays out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| D1 | New stored bins, reconstructed draw totals for old verdict-only dates, and backfill | Cross-date cells show the returned cohort, and full-draw intervals are blank on dates without that evidence. | A decision that needs fixed-bin coverage for unreturned draws, with a priced, compatible writer and reader change. |
| D2 | Calling score-zone or cutoff agreement accuracy, or using the trial to move thresholds | There is no independent error rate or recommendation to change publication policy. | An independently labelled evaluation and a separate judgement about its fit to publication. |
| D3 | Extra charts for Table C, cross-digest precision-recall curves, and new usage telemetry | Comparison of model performance over time and automatic usage counts are unavailable. | A concrete decision the current views cannot answer, plus comparable cohorts or explicit permission for measurement. |

## 1. Status Reckoner

Table E - Trial outcomes

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| E1 | 1 | Show the saved draw and its answer mix | - | A | DONE | - | - | - |
| E2 | 2 | Compare recorded verdicts and entropy across dates | 1 | B | DONE | - | - | - |
| E3 | 3 | Inspect score zones and cutoff trade-offs for one digest | 2 | C | DONE | - | - | - |
| E4 | 4 | Separate incoming score shape from pool drift | 3 | D | DONE | - | - | - |
| E5 | 5 | Release all ten drawings behind the trial switch | 4 | E | DONE | - | - | - |
| E6 | 6 | End the production trial and remove unused views | 5 | F | PENDING | - | - | - |

## 2. Saved draw

### Row #1 - Show the saved draw and its answer mix

- **Scope:** Implement B1 and B5 behind a default-off trial switch without replacing the existing view when it is off.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `config/console/judgement.json`
  - `frontend/src/lib/console/route-console.ts`
  - `frontend/src/lib/console/judge-draw.ts` (new)
  - `frontend/src/lib/console/judge-observations.ts`
  - `frontend/src/lib/console/judge-trial-read.svelte.ts` (new)
  - `frontend/src/lib/console/queries/judgement.ts`
  - `frontend/src/lib/charts/d3/PartsOfOne.svelte`
  - `frontend/src/lib/charts/d3/scoreIntervals.ts` (new)
  - `frontend/src/lib/charts/d3/ScoreIntervals.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte`
  - `frontend/src/routes/console/judgement/JudgeScoreRanges.svelte`
  - `frontend/src/routes/console/judgement/JudgePercentStacks.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeDrawIntervals.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeVisualTrial.svelte` (new)
  - `frontend/src/routes/console/judgement/judge-trial-style.ts` (new)
  - `frontend/scripts/test-groups.ts`
  - `frontend/tests/console-judge-visual-trial.spec.ts` (new)
  - `frontend/tests/support/console-sources.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
- **Acceptance gates:** Local: `npm run test:changed -- --spec console-judge-visual-trial.spec.ts` from `frontend/`; integrated browser smoke with a measured day, a legacy gap and an unchanged cross-page view. CI: panel and native-field bindings, chart vocabulary, full suite and Pages weight.
- **Oracle:** For a saved slice with both returns and unreturned draws, the normalized segments account for every draw and the interval tick shows the same support at its exact saved edges; legacy nulls produce no intervals, and a settlement move cannot redraw the bounds used. This does not measure pair-order repeatability beyond the filed sample.

Table F - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | Add `knobs.judge_visual_trial_enabled` to the existing numeric route config; checked values are 0 and 1, missing means 0. Keep it off through row 4. Gate mounting **and reads**, not only visibility. Keep current chart, links, keyboard controls and coverage unchanged when off. | Console route contract |
| F2 | B1 uses the shared `partsOfOne` geometry with normalized shares and exact standing counts. In ascending score order, segment YES, NO, agreed UNCLEAR, split, refused and no return; the last is drawn minus returned. Support is visible beside each bar. A gap in measured slices is `Not drawn`; an unavailable row is not a gap between measured slices. | Susan; `SliceOutcome` |
| F3 | B5 uses a true score axis and UTC dates. Draw a capped vertical interval at each saved low/high; place a horizontal tick at its midpoint, with total width proportional to draws on one window-wide scale. YES, NO and MAYBE occupy their share of that width over all drawn pairs; MAYBE means agreed UNCLEAR or two valid orders that disagree. The remaining width stays neutral for refused and missing returns, with exact breakdown in the readout. Keep signed scores reachable; a zoom or underflow marker must retain the full interval and never claim all of a crossing slice fell below zero. | Susan; `SliceOutcome` |
| F4 | Read B5 from the literal `judgeDrawTrialQuery` over `threshold-history`: `date`, `run_id`, `attempt`, `pairs_drawn`, `pairs_returned`, `sample_status`, `slice_outcomes`, and both `*_threshold_before` and `*_threshold_after`. Solid steps are recorded bounds **used**; open markers are changed bounds decided after the draw. Break steps where values are unknown. Never substitute the merge floor or recompute historical thresholds. Row 3 adds C2 to this view's selected-date readout. | Native threshold row |
| F5 | Keep app hues consistent across the trial: cobalt YES (`--chart-2`), cyan NO (`--chart-1`), berry split or combined MAYBE (`--chart-3`), orchid agreed UNCLEAR when separate (`--chart-6`), separate charcoal and neutral-grey for refusal and no return (`--chart-4`, `--chart-8`). Use existing theme values and exact labels, not hue alone. Add the `scoreIntervals` chart vocabulary entry with its geometry before wiring it. | Susan; design system |

Table G - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | Normalize by returned pairs or place all returns as individual dots | Both hide work that never returned. | A separate, explicitly named returned-only plot; it cannot replace the draw view. | Susan |

## 3. Verdicts and entropy over time

### Row #2 - Compare recorded verdicts and entropy across dates

- **Scope:** Implement B2-B4 and B10 with one capped, shared pair read and fixed bands.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `config/console/judgement.json`
  - `frontend/src/lib/console/route-console.ts`
  - `frontend/src/lib/console/queries/judgement.ts`
  - `frontend/src/lib/console/judge-pair-evidence.ts` (new)
  - `frontend/src/lib/charts/d3/diagnosticGrid.ts` (new)
  - `frontend/src/lib/charts/d3/DiagnosticGrid.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte`
  - `frontend/src/routes/console/judgement/JudgePairEvidence.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeVerdictHeatmaps.svelte` (new)
  - `frontend/tests/console-judge-visual-trial.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
- **Acceptance gates:** Use the row 1 local selection and its integrated browser smoke for linked selection, visible gap, theme ramps and narrow-width readout. CI: named-column/field/vocabulary bindings, chart vocabulary, full suite and Pages weight.
- **Oracle:** Every classified pair from the selected exact attempt is assigned to one fixed band and contributes once; a different attempt, refusal and empty band cannot create a classified verdict or entropy value. Entropy is zero for a pure outcome, one bit for an even two-way split and `log2(3)` bits for an even three-way mix, within floating-point rounding error of `1e-12` bits. It does not show why a mix changes.

Table H - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | Add the literal `judgePairTrialQuery` for `pair-verdicts`: `date`, `run_id`, `attempt`, `pair_key`, `similarity_score`, `verdict`, `verdict_swapped`, both `*_threshold_in_force`, `scorer_model`, `cosine_weight`, `judge_model`, `prompt_digest`, `grammar_digest`, `judge_policy_version`, `judge_temperature`. Bind names to `StorySimilarityPairVerdict` and the compact attempt in the existing contract check. Use the shared page keeper, session and retry; no explorer/raw URL or separate transport. | Panel door |
| H2 | Gate `JudgePairEvidence` on the trial and start its read once near the viewport via `whenNear`. Intersect the current window with both packed reaches and cap pairs to its most recent `default_window_days`. State the actual span. Read a selected digest outside that span with one one-day request; otherwise reuse the already held answer. Render no pair analytics from duplicates in an exact attempt or from a refused ledger read. Use the core date picker and preserve the usable results of independent reads. | Bounded read; Console |
| H3 | Fixed bands use `knobs.judge_visual_trial_score_bins` equal-width bands on `[0, 1]`, default 10, validated as a positive whole number up to the native histogram's bin ceiling; reserve `[-1, 0)` for underflow. Interior edges belong to the higher band and the final one includes 1. Draw separate YES/NO/split ramps from the theme's measured-zero neutral to the class hues in F5, each with a common 0-100% scale. Divide each count by the band's exact recorded rows, including refusals. UNCLEAR and refused are distinct in the exact breakdown. Print support for the selected date/band and mark thin support with the existing judge sample floor. A measured 0% is distinct from an empty band. | Susan; pair score contract |
| H4 | B10 uses the F3 MAYBE rule and denominator YES + MAYBE + NO, excluding refusals and unreturned pairs. Sum `-p * log2(p)` over nonzero shares, in bits. A pure MAYBE band is also zero entropy: show its MAYBE share and counts, not a certainty badge. Use a single cool-to-warm ramp from theme tokens on a fixed zero-to-`log2(3)` domain. An ambiguity ridge can reflect sample, input or settings changes; it is not proof of judge drift. | Metric definition |
| H5 | Keep pair heatmaps aligned on UTC dates and fixed bins, with date selection via pointer and keyboard and a readable narrow fallback. Mark an adjacent dated change only when known, uniform saved judge/scorer settings differ; mark mixed or unknown settings explicitly and do not infer a change across a gap. Add `diagnosticGrid` once to the chart vocabulary; reuse it for B6. | Susan; saved settings |

Table I - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Split historical draw intervals across fixed bins in proportion to their width | Where the unreturned pairs scored is unknown. | Record the original all-drawn bin counts prospectively; no guessed backfill. | Native evidence |

## 4. Score decisions

### Row #3 - Inspect score zones and cutoff trade-offs for one digest

- **Scope:** Implement B6 and B9 together over the same selected exact-attempt pair projection.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `frontend/src/lib/console/queries/judgement.ts`
  - `frontend/src/lib/console/judge-cutoff-evidence.ts` (new)
  - `frontend/src/lib/charts/d3/precisionRecall.ts` (new)
  - `frontend/src/lib/charts/d3/PrecisionRecall.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte`
  - `frontend/src/routes/console/judgement/JudgeDrawIntervals.svelte`
  - `frontend/src/routes/console/judgement/JudgePairEvidence.svelte`
  - `frontend/src/routes/console/judgement/JudgeCutoffDiagnostics.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeVisualTrial.svelte`
  - `frontend/tests/console-judge-visual-trial.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
- **Acceptance gates:** Use the row 1 local selection and its integrated browser smoke for point readout, matrix counts and shared digest changes. CI: named-column bindings, chart vocabulary, full suite and Pages weight.
- **Oracle:** At the saved reporting cutoff, the scatter's TP, FP, FN and TN derived over agreed binary pairs match that attempt's filed counts when those counts are recorded and the pair answer is complete; equal scores advance together. The matrix partitions every pair with two valid answers once, including MAYBE, and reports what it excluded. Neither validates human accuracy.

Table J - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | B6 uses **Judge outcome (both orders)** rows and **Pipeline score zone (draw bounds)** columns. Judge MAYBE follows F3 and its exact readout separates UNCLEAR from split. A score below the recorded lower bound is NO, at or above the recorded upper bound is YES, and otherwise MAYBE. These are continuous score zones, not rounded sampler buckets. Reject conflicting bounds within one attempt; do not use settled bounds or today's config. Exclude refusals, and list excluded or unknown support separately. | Native pair contract |
| J2 | Use one labelled 3 x 3 grid with exact counts and row shares, plus row denominators. Use class colors in the headers and row-share tint in the cells; mark diagonal matches with a border rather than painting correct/incorrect with red/green. A measured zero is `0`; a row with no support has no percentage. Keep the existing binary cutoff readout distinct. | Susan; reference grid |
| J3 | B9 uses point-in-time precision on Y and recall on X, fixed 0-100% axes, one observed cutoff dot per group of equal scores and no fitted line. Use filled down/up triangles for the lower/upper draw bounds, a filled square for the saved reporting cutoff, and a filled diamond for the saved first point at or above 90% recall. Label the markers and keep every cutoff in a standing readout even when markers overlap. Use score >= cutoff; precision is matches over predictions and recall is matches over agreed YES. Leave a point or marker absent where either denominator is zero. | Susan; native ranking definition |
| J4 | Add the literal `judgeCutoffTrialQuery` for the selected day over `threshold-history`: `date`, `run_id`, `attempt`, `sample_f0_5`, `sample_average_precision`, `sample_precision_at_recall_90`, `sample_recall_90_cutoff`, `sample_recall_at_recall_90_cutoff`, and both fit fields for `estimate`, `nights_used`, `usable_pairs_used`, `held_because` and `move_limited_by`. Use its exact-attempt row for C1 and C2 without changing the existing detail query. Preserve missing older readings and do not show a saved marker when its cutoff is null. Keep sample size and excluded counts visible. Add `precisionRecall` with the chart vocabulary entry before wiring; do not bend `pairedScatter`'s subject floors or free axes. | Console chart contract |

Table K - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | A smooth cutoff curve or automatic score threshold | It interpolates unsupported operating points or promotes sample agreement into a decision about publication. | A separate independent evaluation and publication decision; a fitted curve must then be labelled as such. | Measurement boundary |

## 5. Incoming score pool

### Row #4 - Separate incoming score shape from pool drift

- **Scope:** Implement B7 and link it to B8 without inventing drift history.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `frontend/src/lib/console/queries/judgement.ts`
  - `frontend/src/lib/console/judge-score-pool.ts` (new)
  - `frontend/src/lib/charts/d3/distribution.ts`
  - `frontend/src/lib/charts/d3/Distribution.svelte`
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte`
  - `frontend/src/routes/console/judgement/JudgePoolHistogram.svelte` (new)
  - `frontend/tests/console-judge-visual-trial.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
- **Acceptance gates:** Use the row 1 local selection and its integrated browser smoke for a real histogram with no baseline and the existing recorded PSI check for a measured point. CI: diagnostic shape bindings, full suite and Pages weight.
- **Oracle:** The histogram uses each stored bin edge/count exactly once and its counts sum to the eligible pool; when the baseline is insufficient the histogram remains visible but no PSI point is plotted. On a measured zero, the point appears at zero; a missing day breaks the line. This does not identify a cause of drift.

Table L - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Add the literal `judgePoolTrialQuery` over `threshold-history`: `date`, `run_id`, `attempt`, `score_pool_histogram`. Validate the saved `stamp`, `edges` and `counts` against the native histogram, including bounds, monotonic edges, safe counts and positive total for a plotted series. Reuse distribution geometry for pre-binned input without expanding counts into pairs, rebinning, or changing the old chart callers. Display the signed score range and percentage of the total per bin, with exact count and eligible total in the readout. | Native histogram contract |
| L2 | Keep B8's line, configured guides, recorded score and baseline status. The selected digest and summary are shared with B7. Show progress from the saved source count and required days, not the displayed window. Do not turn zero comparable days, missing histograms or empty pools into a PSI reading. KS and Wasserstein remain accompanying metrics, not more charts. | Native drift contract |
| L3 | Share the L1 result between the selected date and baseline over the same date cap as H2, scoped to `threshold-history` reach alone; a selected date outside the cap uses one exact-day read of the same projection. On a measured digest, overlay the baseline only when every named source matches date, run, SHA-256 of the stored UTF-8 histogram text, stamp and edges. Sum one histogram per source before computing shares. Do not chase missing references; show the current histogram and keep the saved PSI intact with an explicit reference-unavailable note. | Native baseline contract |

Table M - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Compute PSI from pair verdicts, or treat a threshold move as a PSI reset | The sample is not the full pool; comparability belongs to the saved score/pool definition. | An alternative explicitly named sample diagnostic; it cannot stand in for PSI. | Native drift contract |

## 6. Production trial

### Row #5 - Release all ten drawings behind the trial switch

- **Scope:** Enable the trial on the regular Pages publication path only after the chart rows are green.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `config/console/judgement.json`
  - `docs/architecture/publishing/console.md`
- **Acceptance gates:** Local: `npm run check`, the Pages-base-path build and the integrated-browser smoke in CLAUDE.md section 11. Have Susan review one wide and one narrow view before release; include a named judge input absent from an isolated preview. CI: merge candidate green once and existing site-weight limits unchanged. After the normal Pages deploy, read a named packed measured digest and a real unavailable state in the integrated browser and confirm no new console errors or judge-data 404s. This is observation, not a Council, gardener, or recovery dispatch.
- **Oracle:** All Table B drawings render when their data supports them, and unsupported readings carry the named reason; with the flag off, the current Judgement surface returns without the extra network reads. This does not decide which views operators find useful.

Table N - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | Set the switch on in the release PR. Keep the current coverage chart and published grouping independent. In the browser check compare the cold load to the existing console budget and the deferred named pair read to its selected packed shard bytes. The seven named 15-21Nov daily pair shards are a reference workload, not a budget or a hard-coded input. | Site-weight contract |
| N2 | Review after three completed UTC days following the first enabled deployment. Use operator feedback against each numbered drawing and the decisions it helped; collect no new usage telemetry. | Trial scope |

Table O - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Dispatch a producer or raise budgets to make every view nonempty on release | New data is not needed to prove correct empty states; budgets protect the published site. | Separately authorized production work or a measured smaller read. | Publication boundary |

## 7. Trial removal

### Row #6 - End the production trial and remove unused views

- **Scope:** Disable the trial after the review window and remove the trial views unless specifically selected to keep.
- **Files touched:**
  - `TODO/20261124-content-similarity-judge-visual-trial-plan.md`
  - `config/console/judgement.json`
  - `frontend/src/lib/console/route-console.ts`
  - `frontend/src/lib/console/judge-draw.ts`
  - `frontend/src/lib/console/judge-observations.ts`
  - `frontend/src/lib/console/judge-trial-read.svelte.ts`
  - `frontend/src/lib/console/queries/judgement.ts`
  - `frontend/src/lib/console/judge-pair-evidence.ts`
  - `frontend/src/lib/console/judge-cutoff-evidence.ts`
  - `frontend/src/lib/console/judge-score-pool.ts`
  - `frontend/src/lib/charts/d3/scoreIntervals.ts`
  - `frontend/src/lib/charts/d3/ScoreIntervals.svelte`
  - `frontend/src/lib/charts/d3/diagnosticGrid.ts`
  - `frontend/src/lib/charts/d3/DiagnosticGrid.svelte`
  - `frontend/src/lib/charts/d3/precisionRecall.ts`
  - `frontend/src/lib/charts/d3/PrecisionRecall.svelte`
  - `frontend/src/lib/charts/d3/distribution.ts`
  - `frontend/src/lib/charts/d3/Distribution.svelte`
  - `frontend/src/lib/charts/d3/PartsOfOne.svelte`
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte`
  - `frontend/src/routes/console/judgement/JudgeScoreRanges.svelte`
  - `frontend/src/routes/console/judgement/JudgePercentStacks.svelte`
  - `frontend/src/routes/console/judgement/JudgeDrawIntervals.svelte`
  - `frontend/src/routes/console/judgement/JudgePairEvidence.svelte`
  - `frontend/src/routes/console/judgement/JudgeVerdictHeatmaps.svelte`
  - `frontend/src/routes/console/judgement/JudgeCutoffDiagnostics.svelte`
  - `frontend/src/routes/console/judgement/JudgePoolHistogram.svelte`
  - `frontend/src/routes/console/judgement/JudgeVisualTrial.svelte`
  - `frontend/src/routes/console/judgement/judge-trial-style.ts`
  - `frontend/scripts/test-groups.ts`
  - `frontend/tests/console-judge-visual-trial.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `backend/tests/contracts/test_panel_queries.py`
  - `docs/architecture/publishing/console.md`
  - `docs/concepts/console-design/the-mark-shapes-a-panel-may-reach-for.md`
- **Acceptance gates:** Local: verify the named removal paths against their live references, then run `npm run check` and the smallest retained Judgement selection from the gate guide. CI: full suite and Pages weight. After normal deployment, use the integrated browser to confirm both Judgement's remaining charts and a cross-page view render without new errors or 404s.
- **Oracle:** An unretained drawing, its exclusive query, its config and its vocabulary entry are all absent from the shipped surface; the existing PSI and coverage remain usable and surviving shared behavior keeps its tests. This does not establish a permanent design for any chart chosen to stay.

Table P - Decisions

| Id | Decision | Authority |
| --- | --- | --- |
| P1 | The switch is the immediate rollback. Default to removing all trial-only variants at expiry; keep the pre-existing views. If a drawing is selected to stay, retain only the code, query and tests it needs and document its reason on the Console page. Search names against the tree before deleting and do not discard unrelated changes. Close this plan per the execution contract after the cleanup deployment. | Trial lifecycle |

Table Q - Rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Leave inactive trial code and data readers indefinitely | Disabled code still carries maintenance and dependency costs. | A renewed trial with a named decision, owner and end condition. | Trial lifecycle |
