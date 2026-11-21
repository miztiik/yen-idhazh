# Record and chart the nightly similarity judge

**Last Updated**: 2026-11-21
**Level**: 5 - new persisted fields and a preparation payload, followed by their writers and Console reader.

## 0. Operating contract

Table A - Scope and execution

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Give the operator a nightly record of work returned, agreement with the judge at a cutoff, changes in the incoming score mix, and checks on the judge's predictions and known-answer pairs. |
| A2 | In | Persist the readings in Table D automatically in the existing Council collector; draw the three panels and selected-date details in Table L; expose the saved readings to Data explorer through its existing ledger. |
| A3 | Strategy | Keep pair facts in `pair-verdicts` and one observation per digest date and Council run in `threshold-history`. The picker measures the full pool once; the collector uses exact-attempt results. Fowler owns the seams, Andre the measurement, and Susan the presentation. |
| A4 | Boundaries | The diagnostic cutoff starts at 0.87. The moving upper bound guides sampling. The publication settings change lowers `assemble.same_story.floor_min` from 0.94 to 0.85; the all-pairs grouping rule remains in force. None of the metrics changes a draw, a threshold move, a published group, a prompt, a model call, a canary action, or a job outcome. The PSI bands describe a reading; they do not page, fail, retrain or recalibrate anything. |
| A5 | Read first | [Judge flow](../docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md), [publication rule](../docs/architecture/publishing/autotune-content-similarity.md), [row compatibility](../docs/architecture/contracts/schemas.md), [Judgement](../docs/architecture/publishing/console.md#judgement-draws-the-published-merges-and-the-hand-marks), [chart reads](../docs/concepts/console-design/how-a-console-chart-gets-its-data.md) and [chart rules](../docs/concepts/console-design/the-rules-every-console-chart-obeys.md). |
| A6 | Handoff | Land this plan with the separate publication settings PR before cutting the metrics worktrees. For each delegated row, use a separate nested worktree session from current main. Give it this file, the assigned row and its cited tables, and the delivered predecessor PRs. No two workers share a checkout or edit another row's Reckoner line. |
| A7 | ESCALATE triggers | 1. Stop before widening the Level 5 contracts beyond Table E. 2. Stop before changing the ledger key, receipt integrity, sampling, threshold fit or movement, publisher beyond the named floor, labels, trust boundary or model calls. 3. Surface an unresolved contract or design conflict, or a 3x cost overrun, before widening scope or withholding an in-scope metric. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates each row to its own nested session; keep parallel N = 1 because producer rows share the review seam and the Console needs their real outputs; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |

Table B - Scope boundaries

| Id | What stays out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Human labelling, independent accuracy claims, and a larger nightly control set | There is no independent truth for live pairs. The six shipped controls check repeatability against an agent-labelled key, not general accuracy. | An independently labelled set and a decision that needs accuracy rather than judge agreement. |
| B2 | Winner-picking at 95% precision, automatic thresholds for publication, or further publication floor changes | The charts help inspect a cutoff but do not decide which stories readers see together. | A separate grouping replay with evidence about wrong folds and missed duplicates. |
| B3 | Backfill, manual production dispatch, new alerts, and a new ledger or archive reader | Older dates remain unmeasured; the charts follow the existing scheduled compaction and Pages publication. | A recovery or alert request naming its consumers, history, and side effects. |

## 1. Status Reckoner

Table C - PR order

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Declare compatible judge diagnostic records | - | A | PENDING | - | - | - |
| C2 | 2 | File sampled agreement and canary readings | 1 | B | PENDING | - | - | - |
| C3 | 3 | File drift across the full score pool | 2 | C | PENDING | - | - | - |
| C4 | 4 | File Brier and ECE against a prior fit | 3 | D | PENDING | - | - | - |
| C5 | 5 | Draw the nightly evidence in Judgement | 4 | E | PENDING | - | - | - |

## 2. Row #1 - Declare compatible judge diagnostic records

- **Scope:** Level 5; land additive row, config and transport contracts before any producer populates them.
- **Files touched:**
  - `TODO/20261121-nightly-judge-metrics-plan.md`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/story_similarity_threshold_history_row.py`
  - `backend/idhazh/contracts/story_similarity_diagnostics.py` (new)
  - `backend/idhazh/contracts/story_similarity_score_pool.py` (new)
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `config/judges/content-similarity-judge.json`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_story_similarity_threshold_history_row.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `tests/fixtures/contracts/story-similarity-score-pool/small-pool.json` (new, schema only)
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: select checks with `npm run test:changed -- --list` in `frontend/`; run the focused contract cases and the raw-to-compact oracle from the selected backend group. Use the existing history fixture for the legacy row and minimal in-memory values for edge cases.
  - CI: required backend contract, typing and lint gates plus applicable site checks. No production state edits or runs.
- **Oracle:** Compact a legacy history file whose Parquet schema physically lacks the new columns with a file written by the widened contract, then read the named period through the real ledger: the old stamp and nulls survive, and the populated proof round-trips without a changed count or identity. This proves compatibility, not metric accuracy.
- **Decisions:**

Table D - Metric inventory and PR scope (`TH` means `threshold-history`; `PV` means `pair-verdicts`)

| Id | Reading | Inputs today? | Nightly? | Ledger and exact column(s) | Console? |
| --- | --- | --- | --- | --- | --- |
| D1 | Full draw and actual returned rows | Yes at collection; no durable full-draw total. PV has returned rows. | Yes | TH: `pairs_drawn`, `pairs_returned`; return share derived. | Yes |
| D2 | Runner coverage, order agreement, refusals, unavailable summaries, deadline loss and UNCLEAR | Yes | Yes, existing runner readings | TH: `runners_reported`, `runners_expected`, `pairs_dealt`, `pairs_valid`, `pairs_agreed`, `disagreement_rate`, `pairs_refused`, `pairs_unreadable`, `pairs_abandoned`, `unclear_rate`. Derive sample usability as agreed YES/NO/UNCLEAR out of returned from D3. | Yes, selected-date readout |
| D3 | YES and NO by sampled score range; non-binary and unreturned counts | Yes, from draw plus PV | Yes | TH: `slice_outcomes`; `sample_status` distinguishes measured from unavailable. YES share derived from counts. | Yes |
| D4 | Confusion counts, precision and recall at diagnostic cutoff | Yes against the judge, no human truth | Yes | TH: `evaluated_cutoff`, `sample_tp`, `sample_fp`, `sample_fn`, `sample_tn`, `sample_precision`, `sample_recall`. | Yes, selected-date readout |
| D5 | Wrong-match share and hard-decision Brier at the upper bound used for that draw | Yes, PV and `upper_threshold_before` | Yes | TH: `upper_cutoff_false_match_share`, `upper_cutoff_sample_size`, `upper_cutoff_brier_score`. | Yes, selected-date readout |
| D6 | Hard-decision Brier at the diagnostic cutoff (fraction of decisions that differ from the judge) | Yes against the judge | Yes | TH: `cutoff_brier_score`. | Yes, beside D4 |
| D7 | F0.5, average precision, and precision at 90% recall | Yes on the sample | Yes | TH: `sample_f0_5`, `sample_average_precision`, `sample_precision_at_recall_90`, `sample_recall_90_cutoff`, `sample_recall_at_recall_90_cutoff`. | No dedicated Console display; Data explorer |
| D8 | Fixed-bin score mix, PSI, binned Wasserstein distance, binned KS distance | No fixed-bin pool record; picker already scores every eligible pair | Yes after the baseline is ready | TH: `score_pool_histogram`, `score_drift_baseline`, `score_drift_status`, `score_psi`, `score_wasserstein_distance`, `score_ks_distance`. | Yes, PSI trend and other values in readout |
| D9 | Probability Brier and ECE against fresh judge answers | Curve coefficients and answers exist; exact training membership/support do not | Yes when a compatible earlier fit and eligible answers exist | TH: `upper_fit_evidence`, `judge_probability_evidence`, `judge_probability_status`, `judge_probability_brier_score`, `judge_probability_baseline_brier_score`, `judge_probability_ece`. | Yes, selected-date readout; no trend or probability gates |
| D10 | Known-answer outcomes and three-class Cohen's kappa | Yes, six expected answers in config and both observed answers in TH | Yes, kappa only for complete agreed controls | TH: existing `canary_answers`; add `canary_expectations`, `canary_kappa`, `canary_kappa_pairs`. | Yes, selected-date details, not a trend |
| D11 | Human-reference accuracy, Gwet AC1, nightly control expansion, 95%-precision operating cutoff | No independent evidence for those accuracy claims; AC1 is computable but does not enlarge the control set | No | None. The existing `holdout-pairs` is not the nightly reference. | No |

Table E - Native shapes and defaults

| Id | Contract | Exact shape or invariant | Authority |
| --- | --- | --- | --- |
| E1 | Nightly row | Add nullable fields from Table D to `StorySimilarityThresholdHistoryRow`, stamp with UTC ship date and changelog. Keep `(date, run_id)`, the existing writer envelope's `attempt`, and every existing field and legacy stamp. Counts are nonnegative safe integers; shares, Brier values, ECE, AP and KS are finite in `[0,1]`; kappa is finite in `[-1,1]`; PSI is finite and nonnegative, Wasserstein in `[0,2]`; score cutoffs are finite in `[-1,1]`. A diagnostic group may be entirely absent even on a new-stamp row: the reader lands before the writer. No backfill or computed zero on a legacy row. Roll back a writer without removing the compatible reader. | Fowler |
| E2 | Grouped evidence | Keep columns scalar for Parquet/browser compatibility. Validate the named nested objects as typed models before writing them as canonical compact JSON text using the existing `canonical_compact_object` pattern: sorted keys, ASCII-escaped, no extra fields, separator spaces or trailing newline. No article text is stored. `slice_outcomes` is `{slices: [...]}`; each row is `{bucket, low, high, available, drawn, yes, no, unclear, split, refused}`. Use the same bucket enum and edges as PV. Edges are finite, ordered and nonoverlapping; drawn is positive and at most available. Sum of outcome counts is at most drawn. | Fowler |
| E3 | Histogram and baseline | `score_pool_histogram` is `{stamp, edges, counts}`. `stamp` is a SHA-256 of the score/pool recipe (D8 producer rule in Table I); `edges` strictly increase from -1 to 1, `counts` has one nonnegative integer per interval. `score_drift_baseline` is `{sources, required_days, share_floor}` with `sources` newest first, distinct earlier digest dates, entries `{date, run_id, histogram_sha256}`. `score_drift_status` is `measured`, `no_histogram`, `empty_pool` or `insufficient_baseline`. The three distances co-exist only for `measured`, which requires exactly `required_days` sources. Keeping the count on the row lets the UI explain warm-up without reading a later config. | Fowler / Andre |
| E4 | Fit and calibration evidence | `upper_fit_evidence` is `{meaning_stamp, judge_temperature, pair_keys, low, high, yes}`. `meaning_stamp` carries exactly `judge_model`, `prompt_digest`, `grammar_digest`, `scorer_model`, `cosine_weight`, `judge_policy_version`; names/digests must be present. `pair_keys` are sorted, unique SHA-256 keys; `low/high` are observed inclusive score bounds; `yes` is the training YES count. `judge_probability_evidence` is `{source_date, source_run_id, fit_sha256, pairs, yes, bins}` with `bins` the ECE bin count; `pairs`/`yes` describe evaluation, not training. `judge_probability_status` is `measured`, `no_reference_fit` or `no_eligible_pairs`. A chosen source with no eligible pairs keeps its reference and `pairs=0`, but no scores. An absent reference keeps the evidence null. | Fowler / Andre |
| E5 | Coverage and canary pairing | `sample_status` is `measured`, `not_filed` or `draw_mismatch`. For `measured`, `pairs_returned <= pairs_drawn`, the drawn/returned slice sums match the two totals, and the four confusion cells exhaust binary agreements. Unknown counts stay null when diagnostics cannot match the batch. For valid canaries, `canary_expectations` is an object from stable id to expected verdict; use the canary contract's id, verdict and size limits. `canary_kappa_pairs` counts controls with two valid agreeing answers; kappa is null unless every expected pair qualified and its chance denominator is nonzero. | Fowler / Andre |
| E6 | Judge config | Add `diagnostics` to `config/judges/content-similarity-judge.json`: `cutoff: 0.87`, `score_bins: 40`, `score_baseline_days: 7`, `score_baseline_lookback_days: 28`, `score_psi_share_floor: 0.000001`, `probability_bins: 10`, `fit_pair_limit: 1050`. These are diagnostics only; stamp the file's UTC revision. Give legacy config the same validated defaults. Bounds: cutoff `[-1,1]`; score bins integer 2-200; `1 <= score_baseline_days <= score_baseline_lookback_days <= 90`; finite `0 < score_psi_share_floor < 1 / score_bins`; probability bins integer 2-50; fit pair limit integer 1-1050. The share floor keeps empty PSI bins finite without letting pool size itself create drift. The key cap keeps one fit's exact keys at roughly 70 KB before packing; never truncate the fit. P@R90's 90% defines the named reading, not a setting. | Measurement design / Fowler |
| E7 | Preparation payload | New date-versioned `ContentSimilarityScorePool` contract: `date`, `run_id`, positive `attempt` and `histogram` of E3. Register the contract and named fixture. It is one opaque file in the existing preparation receipt, not another ledger or a new column on judged pairs. Once a diagnostic group is populated, require matching status and evidence; the shape-only PR must still accept outputs from writers that do not populate it. | Fowler |

- **Rejected alternatives:**

Table F - Storage alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | Leave the new readings only in logs or rederive them all on the page | Expired draws lose coverage; returned pairs cannot recreate the full pool; recalculating past measures can silently change their meaning. | A separate retained artifact service or extra reads plus missing evidence that still cannot be recovered. | Fowler |
| F2 | Add a metrics ledger or repeat aggregates on every pair | The observations already belong to one digest/run, the grain of TH. | Another publication/compaction lifecycle, or duplicated values and inconsistent readers. | Fowler |

## 3. Row #2 - File sampled agreement and canary readings

- **Scope:** Level 3; write D1-D7 and D10 from the current draw, exact filing batch and known-answer reports during existing settlement.
- **Files touched:**
  - `TODO/20261121-nightly-judge-metrics-plan.md`
  - `backend/idhazh/stages/file_pair_verdicts.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/stages/review_thresholds.py`
  - `backend/idhazh/similarity/sample_diagnostics.py` (new)
  - `backend/idhazh/similarity/canary_diagnostics.py` (new)
  - `backend/tests/test_review_thresholds_stage.py`
  - `backend/tests/test_similarity_sampling_chance.py`
  - `backend/tests/test_judge_canary_pairs.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
- **Acceptance gates:**
  - Local: shared changed-test selector plus the real settlement oracle. Include an empty retry after earlier rows, verdicts without a runner report, a completely unreturned drawn slice, score ties and cutoff equality, and the existing canary report path.
  - CI: required backend checks. After the first ordinary Council settlement, read the named TH partition and compare D1-D4 to that run's draw and verdicts while available. A mismatch warrants inspection of identity/filing, not a workflow dispatch as a merge gate.
- **Oracle:** The same named draw plus current-attempt returns file the hand-counted confusion matrix and close every per-slice funnel in TH, including a lost slice; older returns do not populate a shorter or empty retry. For a binary sample with TP/FP/FN/TN of 2/1/1/2, the cutoff Brier is 2 errors out of 6, not 2 out of all drawn pairs. This proves sample accounting, not population accuracy.
- **Decisions:**

Table G - Sample and control rules

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Add `filed_rows` to `FileReport`: a tuple of the exact validated rows written by this call with final sampling fields; empty for no incoming rows and null if a nonempty batch did not file. `tenant.settle` passes that value to `stage_review_thresholds`; its existing writer identity supplies the attempt. Null means `not_filed`, not zero returns. Keep the existing fit's ledger reread and rule unchanged. For the diagnostic join, require the draw and returns to name this date/run, unique keys, and agreeing score, shard and slice metadata. A diagnostic-only mismatch logs a named reason and leaves dependent counts null; existing integrity refusals still refuse. | Fowler |
| G2 | Count one draw row per key and one filed row per key. A returned row with an invalid answer is `refused`; two valid different answers are `split`; otherwise use agreed YES, NO or UNCLEAR. `unreturned = drawn - returned`, for each actually drawn range including a range with no returned rows. Do not invent counts for undrawn ranges. Unreadable and deadline totals remain runner facts, not additional disjoint pieces of this funnel. A runner report is not proof of a returned pair or vice versa. Keep the existing header-only/no-work behavior and distinguish a missing draw artifact. | Fowler |
| G3 | For binary metrics use only pairs that agreed on YES or NO in both orders, unweighted, with both tails included. Predict YES at `similarity_score >= evaluated_cutoff`. TP/FP are judged YES/NO among predicted YES; FN/TN are judged YES/NO among predicted NO. Precision is TP / (TP + FP); recall is TP / (TP + FN); hard Brier is (FP + FN) / all binary agreements. Do not treat UNCLEAR, refusal, split or absence as NO. A zero denominator gives null. For D5 repeat at `upper_threshold_before`; support is TP + FP there, and wrong-match share is FP divided by that support. Call it disagreement with the judge, not a verified false fold. | Andre |
| G4 | On the same binary sample as G3, F0.5 is `5*TP / (5*TP + 4*FP + FN)` at the diagnostic cutoff, null for zero denominator. For AP and P@R90 sweep distinct stored scores descending in whole tied groups, independent of order. AP is the sum of each recall gain times precision at the end of that group. For P@R90 stop at the first group with `10*TP >= 9*all YES`; keep inclusive score and achieved recall. No interpolation. Both ranking readings are null with no YES. Do not weight by `sampling_chance`. | Andre |
| G5 | Take the expected id/answer snapshot from the same committed canary config the runner used. Compare one observed verdict against the key per id only after both orders give the same valid verdict. For kappa, observed agreement is the matched fraction; chance agreement is the sum over YES, NO and UNCLEAR of the expected and observed class shares multiplied. Subtract chance from observed and divide by one minus chance. Any absent, refused or split pair makes the score null; keep its actual status and the number that qualified. The same answer key read in two orders is not two independent raters. No new calls or enforcement. | Andre |

- **Rejected alternatives:**

Table H - Accounting alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Call reporting runners' `pairs_dealt` the total draw, or pick previous rows by pair id alone | A missing runner hides work and an empty retry can borrow stale labels. | An inaccurate coverage chart and a second correction to the same contract. | Fowler |
| H2 | Calculate these as population accuracy or tell the publisher to use the best sample cutoff | Draw probabilities are unequal, and unresolved cases and label quality are not measured by these readings. | Design-based estimates with sufficient coverage and separate evidence about actual grouping errors. | Andre |

## 4. Row #3 - File drift across the full score pool

- **Scope:** Level 3; save the fixed-bin count and all three label-free distances using existing scoring, preparation and collection.
- **Files touched:**
  - `TODO/20261121-nightly-judge-metrics-plan.md`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/content_similarity_judge/ledger_reads.py`
  - `backend/idhazh/stages/review_thresholds.py`
  - `backend/idhazh/similarity/score_pool_drift.py` (new)
  - `backend/tests/test_similarity_handoff.py`
  - `backend/tests/test_content_similarity_judge_ledger_reads.py`
  - `backend/tests/test_review_thresholds_stage.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:**
  - Local: shared selector and the real handoff oracle. In-memory cases cover equal shares at different pool sizes, empty bins, disjoint occupied bins, inclusive endpoints, insufficient history, wrong bin/scorer stamps, same-run repair and a valid real zero. Exercise the receipt path with an isolated write/read, not a workflow-file test.
  - CI: required backend checks. On a normal run, verify the histogram total equals the picker's distinct eligible total. When a baseline fills, check that it names only the configured number of earlier comparable dates; before that, absence is expected.
- **Oracle:** The planner's real deduplicated pool produces the same draw with and without observation, and its receipt-carried histogram produces the hand-computed distances against the same named historical inputs after collection. This cannot tell whether the judge or the quality of merges changed.
- **Decisions:**

Table I - Drift rules

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | Materialize the output already returned by `selection.one_pair_a_key`, and pass that same list to `selection.select`. Count it once before sampling: one score for every eligible cross-outlet canonical pair, at least one item from the digest day. No rescoring, no draw-slice reuse. Use equal-width fixed intervals over `[-1,1]`; edge belongs to the higher bin, except 1 is in the last bin. Apply the existing unit-range rounding rule at the ends. Histogram sum equals the deduplicated pool size, not the sample size. | Andre |
| I2 | Stamp the pool with the named version of its scoring/pair-selection recipe plus actual configured scorer model, encoder revision, cosine weight, headline-match setting, and earlier-day time window. Use stable canonical JSON before hashing. Bump the recipe identifier if scoring or eligible membership rules change. Baselines require identical stamp and edges, not identical moving draw cuts, judge prompt, sample size, or source mix. | Fowler / Andre |
| I3 | Write the validated E7 payload atomically beside the draw, with `session.unit_file` in the selection slot and a distinct `.score-pool.json` suffix. In `prepare`, attach it only if produced and name it via `session.artifact_path`; in `settle`, only accept that named file from `prepared.files` and match digest, run and attempt. No generic Council changes. An older receipt/no histogram or a typed metrics payload that cannot be read after verified transfer leaves drift blank with a reason. A missing or tampered file declared in a receipt is still an integrity failure under the existing check, not permission to use other bytes. No new history row for existing no-work cases. | Fowler |
| I4 | Extend the TH portion of `review_days` only via the same `publication_inputs` path: use the maximum of the existing lookbacks and E6's drift lookback; keep the pair-verdict window unchanged. Use the existing bounded TH door at the pinned checkout: a repair to a packed digest becomes visible there after repacking, not through a new raw overlay. For earlier digest dates, consider only rows with earlier Council run identities (compare UTC prefixes, then numeric run suffix). Keep the newest earlier run per date before comparing pool stamps and edges; exclude the same Council run even if it repaired an earlier digest. Take the configured number of newest compatible, nonempty days inside the lookback. Pool their counts (each pair contributes once per digest, not equal weight per day); store the dated run ids and canonical histogram digests. Too few dates means no distances yet, not zero or a scan farther back. | Fowler / Andre |
| I5 | PSI: divide each vector by its own total, floor each share at the recorded `share_floor`, renormalize each vector to sum to one, and sum `(target_share - baseline_share) * ln(target_share / baseline_share)`. Equal score shares at different pool sizes give zero. KS: maximum absolute gap between cumulative unsmoothed shares at bin edges. Wasserstein: put unsmoothed bin mass at each midpoint; sum the absolute cumulative gap times the distance to the next midpoint. Save the actual values; label both distances as binned, with no KS p-value or implied test of significance. A raw zero-mass pool produces no distances. The Council does not read the Console's interpretation cutoffs. | Measurement design / Andre |

- **Rejected alternatives:**

Table J - Drift alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Compare changing sample buckets, or synthesize a full histogram from returned rows | A change in the draw can move those distributions even if incoming scores did not change. | A separately justified estimator with complete slice coverage; it still cannot split old counts at unseen edges. | Andre |
| J2 | Read old digests again or store every score | The one pre-draw tally answers the question; repeated scoring and full-pair history grow bytes or work needlessly. | Another scorer pass and additional raw/packed bytes; measure that only if a consumer needs exact, rather than binned, distances. | Fowler |

## 5. Row #4 - File Brier and ECE against a prior fit

- **Scope:** Level 3; retain exact training membership for the existing upper curve, and score its probabilities only against eligible later answers.
- **Files touched:**
  - `TODO/20261121-nightly-judge-metrics-plan.md`
  - `backend/idhazh/similarity/threshold_evidence.py`
  - `backend/idhazh/similarity/threshold_curve.py`
  - `backend/idhazh/similarity/probability_diagnostics.py` (new)
  - `backend/idhazh/stages/review_thresholds.py`
  - `backend/tests/test_similarity_threshold_evidence.py`
  - `backend/tests/test_review_thresholds.py`
  - `backend/tests/test_review_thresholds_stage.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
- **Acceptance gates:**
  - Local: shared selector and focused fit/readback oracle. Include a reappearing pair with a changed score, an agreed UNCLEAR, exact support edges, a mixed or changed stamp, a legacy fit without exact keys, an oversized fit and empty evaluation support. Verify existing threshold results are identical.
  - CI: required backend checks. On the first eligible subsequent date, verify the retained source predates the evaluated date and is not the same run; absence before that is expected. Measure the added bytes on named packed periods, including day or month files the browser fetches whole. The key cap bounds raw size; savings from packing are unmeasured. Do not raise a site budget in this row.
- **Oracle:** For the same earlier real fit and later named batch, hand-calculated Brier/ECE agree with the stored values after dropping overlaps and unsupported scores, and the threshold columns match the same run without the diagnostics. This proves agreement on pairs absent from the direct fit, not human accuracy or independence from the rolling fit prior or from similar events.
- **Decisions:**

Table K - Calibration and alternatives

| Id | Kind | Decision | Authority |
| --- | --- | --- | --- |
| K1 | Decision | From the exact ordered rows selected by `evidence_near`, carry their pair keys and temperature to review without changing the scorer inputs, order or answers supplied to the upper fitter. Retain E4's key set, observed support, training YES count and recorded stamp only when coefficients were returned, the stamp and temperature are known and uniform, and the exact set fits E6's cap. Require its key count to equal `upper_usable_pairs_used`. If it cannot be retained, leave provenance absent and log the named reason; do not change or truncate the fit. Reuse its stable sigmoid with its existing intercept and slope. | Andre / Fowler |
| K2 | Decision | Use the same TH view as I4, restricted to the configured draw lookback even if more days were loaded for other readings. Choose the newest eligible recorded upper fit with both an earlier digest date and an earlier, different Council run, complete provenance, and matching meaning stamp and temperature. Use the current batch's reading identity, not its labels or coverage, to choose. Order by digest date and then the run order used in I4. Hash the canonical source evidence and coefficients for the reference. Do not replace the chosen source with another if support is empty. | Andre |
| K3 | Decision | On exact-attempt current rows, use only valid agreeing answers with matching stamp and temperature, scores inside the source's observed `[low,high]`, and keys not in its training set. Match the existing curve's target: YES is 1; agreed NO or UNCLEAR is 0. No weighting. Brier is the mean squared difference between the prior YES probability and this outcome; compute the constant baseline on the same cohort using the source YES rate. For ECE, place predictions in the configured equal-width probability bins (right-edge rule as I1, inclusive 1), and sum each populated bin's share of evaluated pairs times its absolute mean-probability minus observed YES-share gap. Store values, evaluation counts and source; null for no eligible rows. | Andre |
| K4 | Rejected | Raw cosine as a probability, or fitting and scoring on the same answers, gives a number with the wrong meaning. Pricing real probability accuracy would need a separate labelled reference; the prior-fit comparison answers the narrower question without new calls. | Andre |
| K5 | Rejected | Rebuild an old fit's membership from today's compact/raw rows. Late repairs can change which rows are visible and retained files can disappear, so exact membership is not known. It would need preserved source snapshots or proof of complete original coverage. Keep the bounded exact list instead; never request it in a Console panel query. | Fowler |

## 6. Row #5 - Draw the nightly evidence in Judgement

- **Scope:** Level 3; make the three saved diagnostic views readable and actionable without giving them control of publication.
- **Files touched:**
  - `TODO/20261121-nightly-judge-metrics-plan.md`
  - `config/console/judgement.json`
  - `frontend/src/lib/console/route-console.ts`
  - `frontend/src/lib/console/queries/judgement.ts` (new)
  - `frontend/src/lib/console/judge-observations.ts` (new)
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/judgement/JudgeObservations.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeCoverage.svelte` (new)
  - `frontend/src/routes/console/judgement/JudgeScoreRanges.svelte` (new)
  - `frontend/src/routes/console/judgement/PairScoreDrift.svelte` (new)
  - `backend/tests/contracts/test_panel_queries.py`
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/console-judgement-nothings.spec.ts`
  - `frontend/tests/console-panel-queries.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `frontend/tests/support/console-expect/console-window/judgement.ts`
  - `docs/architecture/publishing/console.md`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
- **Acceptance gates:**
  - Local: shared selector and the named panel/column, compatibility, config, and selected-date tests. Extend `test_panel_queries.py` with TH's native fields plus the ledger identity's `attempt` column; bind the frontend's compact detail fields and status vocabulary to the producer contract. For the positive browser case, settle a bounded recorded draw and verdict batch into isolated temporary state, pack it and stage the exact output through the ordinary publication path. In-memory inputs can exercise PSI boundaries without waiting for production history; do not seed the production ledger or substitute a test API.
  - Browser: one built Judgement journey and one unchanged neighboring route. Inspect in a batch at desktop and 390px, including keyboard/hover/tap parity and real absent/empty data. See Table L for what must be visible. Confirm dark/light token behavior on the same layout, no new console error or unexpected missing request, and no clipping. Consult Susan on the finished surface; use the existing visual check and tooling, not a new test framework.
  - CI: required site, backend contract and browser gates; existing payload/Pages size checks with packed history. On the next normal Pages publish after compaction, verify the dated points match TH and show the packed reach rather than the Council's wall-clock date.
- **Oracle:** The browser's named columns from one real compacted TH payload drive exactly the dated plot marks, selected digest and legend with keyboard and pointer; the PSI guides use the authored config and don't clip larger readings. Legacy and absent values never become bars or zero points. This proves faithful rendering, not judge quality.
- **Decisions:**

Table L - Panel drawings and reading order

| Id | Panel or detail | Visual and interaction | Authority |
| --- | --- | --- | --- |
| L1 | Judgement route | Keep existing published merge and holdout panels in their own full-width `Published grouping` section. Follow with full-width `Judge observations` in L2-L4 order. In the route config, keep group id `judgement`, add `judge-observations`, and register its panels in the route's `judged` list. Reuse the existing panel frame, typography, tokens and D3 components; explicitly decline the summary-settings comparison rule for these panels. The visible scope line says `These observations do not change what the site merges.` Keep the Data explorer link for raw rows and ledger-only metrics. | Susan / Fowler |
| L2 | `judge-coverage`: **Pairs drawn and returned** | UTC digest date on x, pair counts from zero on y. Shared `dateSeries` stacked columns, fixed order: agreed YES or NO (sum of D4's cells), other returned, did not return. No fabricated parts when a denominator is absent. Standing readout leads with `returned of drawn`, then binary agreement and reported/expected runners. Selected-day notes show sample usability as a separate reading, distinguish split, UNCLEAR and refusal from missing pairs, and name unreadable/deadline counts as reported-runner facts. Enter or tap a date to hold it for all three panels; arrows inspect and a visible outlined selection identifies the held date. | Susan |
| L3 | `judge-score-ranges`: **Judge answers by score range** | Selected digest only. One ranked-by-score, not ranked-by-rate, row per actual drawn interval, labelled from its recorded bounds in ascending order. Shared `partsOfOne` count stacks in fixed YES / NO / other returned / not returned order on a common scale. Print the exact YES and NO counts and YES out of both; distinguish undealt gaps and wholly lost ranges. Below, show D4-D6 with cutoff, counts and denominators, including the upper draw bound separately. Use the Console's `judge_thin_sample_pairs: 20` default to describe thin support; never drop counts to make a thin rate look complete. Neither cutoff is drawn as a probability or the published line. | Susan / Andre |
| L4 | `pair-score-drift`: **Pair-score drift over time** | One saved PSI point per UTC digest date. `dateSeries` with nonnegative niced linear axis, guides from L5 included in the domain, visible dashed guide labels, a date selection guide and the same held date as L2. Give null calendar days explicit null points so the line breaks. An isolated value gets a dot. Readout `Date / PSI / Interpretation` has scope, baseline first/last source date and number of source days. Under that readout put binned Wasserstein in score units and binned KS as a cumulative-share gap, not separate axes or charts. A breach must plot above the upper guide. | Susan |
| L5 | Console defaults and PSI guide copy | In `route-console.ts`, require the new knobs when these panels are configured: finite `0 < psi_moderate_min < psi_significant_above` and a positive safe integer `judge_thin_sample_pairs`. Set PSI defaults in `config/console/judgement.json` to `psi_moderate_min: 0.10` and `psi_significant_above: 0.25`; L3 owns the thin-sample default. Generate the visible rule from the config: `PSI below {low}: No significant drift. PSI from {low} through {high}: Moderate drift (investigation needed). PSI above {high}: Significant drift (retrain or re-calibrate).` Append `These are rules of thumb for changes in the incoming score mix. Verify quality before retraining or recalibrating.` Exactly either cutoff is Moderate. Classify the stored unrounded number; print enough precision near a guide to avoid displaying a contradictory value. No alarm palette, badge, or job action. | Susan / Andre |
| L6 | Selected-day details | Two quiet text sections under the drift panel, still available when the selected day has no PSI. `How close were the prior probabilities to this judge?` shows probability Brier/ECE, reference, same-sample baseline Brier and support; distinguish `No comparable prior fit` from `No new agreed pairs in the prior fit's score range`. `What did the judge say on the known-answer pairs?` shows one compact row per recorded expected id with expected, both answers, and matched / differed / split / refused / missing in words. Lead with matches and number expected; put kappa second with its denominator or absence reason. Old rows may show observed answers without grading when the expected key was not recorded. Never call these human labels. No tooltip-only facts or color-only status. | Susan / Andre |
| L7 | Loading, gaps and narrow width | Use shared route status and empty frame, not a blank chart or measured zeros. Show `Not recorded` for legacy readings, `Not published yet` for named days beyond packed reach, and `Not measured` with the reason for present null metrics. Retain valid partial coverage. Keep the selected date when it is in the next window; otherwise choose the newest available row. Ignore stale async answers. Standing readouts wrap without horizontal page scroll; arrows, Enter and tap expose the same named values, with a visible focus/selection outline. Use the shared date and number formatters. | Susan |
| L8 | Static data path | Declare `judgeHistoryQuery` and `judgeDayQuery` as literal `PanelQuery` objects in `queries/judgement.ts`, both over TH, `span: 'window'`. History selects `date`, `run_id`, `attempt`, D1, the four D4 confusion cells and `score_psi`. Ask for the intersection of the route's displayed UTC window and packed ledger reach; do not anchor the visible route to the end of a packed month or run-id date. Detail selects the same identity plus the displayed D1-D6 fields, D8 except the histogram, D9 except fit provenance, D10 and `upper_threshold_before`. Call it with a one-day `Range` (`from` and `to` both the selected UTC digest), not a dynamic query per run, and filter that result to exact run and attempt. Latest compact reading per digest uses `compareRuns` then highest attempt; never combine runs or borrow data from an older one. Reuse `routeReach`, `sliceOnce`, bounded memo, `readSession` and retry; a glyph or legend does not initiate its own read. No new server loader, raw URL, external reader or build-time telemetry inline. | Fowler |

**Layout reference (placement only, no metric data):**

```text
Judgement                                                   [Window]
  Published grouping
    Published merges
    Holdout margin
  Judge observations  |  These observations do not change what the site merges.
    Pairs drawn and returned
    [Daily count stacks --------------------------------------------]
    Selected digest  |  Returned of drawn  |  Binary agreements  |  Runners
    Judge answers by score range                     [Same selected digest]
    Score interval     YES / NO / Other returned / Not returned
    Cutoff comparison  |  Wrong matches  |  Missed matches  |  Brier
    Pair-score drift over time
    [Daily PSI line; two guides; breaks for unavailable days -------]
    Rule of thumb (visible)  |  Selected digest and baseline (wrap below)
    Binned Wasserstein and KS
    Prior-fit Brier and ECE  |  Known-answer pairs and kappa
```

- **Rejected alternatives:**

Table M - Console alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Three competing drift charts, a default trend of sample accuracy, or a large new dashboard | The numbers answer different questions; an accuracy-looking trend turns changes in pairs or coverage into fake quality changes. | More plot space and comparative evidence for each trend; add a view only for a named operator decision. | Susan / Andre |
| M2 | Embed the ledger in rendered HTML, read pair rows for every date, or bypass the query door | Broader data and a second transport, even though the history and details are now filed. | Extra bytes per view, a growing read, and separate failure/retry semantics. | Fowler |
