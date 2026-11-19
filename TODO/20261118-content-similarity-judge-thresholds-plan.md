# Content-similarity judge: new pairs only, follow both thresholds, canary pairs

**Last Updated**: 2026-11-18
**Level**: 5 - rows 3, 4 and 5 declare, write or retire persisted shapes and row 8 deletes committed data. Row 1 is Level 3, row 2 Level 2, rows 6 and 7 Level 3, row 8 Level 4.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The nightly judge re-judges pairs it already judged, spends as much on near-certain pairs as on doubtful ones, never tests a score below 0.88, fits one line from a cumulative record that cannot follow a change, and has no known-answer check. It is replaced by a draw of new pairs only, sampled by score slice at known chances, that follows a lower and an upper bound threshold, stores every number behind each move, and checks the judge against six known pairs once per run. |
| A2 | Hard scope - in | Row 1 new pairs only. Row 2 config versions. Row 3 ledgers `pair-verdicts` and `threshold-history`. Row 4 weighted draw and pair verdicts. Row 5 find and move both thresholds. Row 6 canary pairs. Row 7 Judgement page without the retired data. Row 8 retire the old record, fit, knobs and six ledgers. Docs: one architecture page (vocabulary, nightly flow, formulae with a worked night, stored columns, design rationale) written across rows 4 to 8. |
| A3 | Hard scope - out | Table B. |
| A4 | ESCALATE triggers | 1. A change to what publishes, including `floor_min` or any use of the thresholds by assemble. 2. A change to the judge model, prompt, grammar or sampler. 3. Article text sent anywhere but the committed model server. 4. A stored column beyond Table E. 5. Anything that reacts to a wrong canary answer by holding, re-running or stopping a night. 6. Weights used inside the curve fit. 7. A new dependency in the default install. |
| A5 | Chosen strategy | Judge only new pairs, sample by score slice at known chances, estimate each threshold from the last 7 nights with a steepness-pulled curve, widen fast and narrow slowly, store every number, and check the judge against known pairs. Andre ruled sampling, formulae, share levels and canaries. Fowler ruled ledgers, contracts and order. |
| A6 | Level 5 rows | Rows 3 to 5 change persisted shapes. Their design was settled by consultation before this plan was written. |
| A7 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight (rows 1 to 3 are disjoint, rows 4 to 8 run in dependency order), refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. Files touched of rows 7 and 8 come from searches for each retired name and are re-run at dispatch. |

Table B - Scope boundaries

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Using a threshold to decide what publishes. The site keeps its fixed `floor_min`, and assemble is unchanged | The site merges at a fixed score while the judge tracks the evidence | A request naming which threshold the site follows and which mistake costs more, merging two stories or publishing a duplicate; then a plan |
| B2 | Reacting to a wrong canary answer by holding, re-running or stopping a night | A wrong answer is logged and stored; the night proceeds | A request naming what a failure should do and what a wrongly held night costs |
| B3 | A new Judgement-page panel for threshold history or canary answers | History is read in the Data explorer | A request naming the question the panel answers, then a design consult |
| B4 | Versioning the other config files | The judge's rows name its own config files only | A plan giving every config file a version field and a bump rule |
| B5 | Explorer consent for the seven other eligible ledgers | They stay out of the Data explorer | A request; price it by summing the sizes under `state/compact/` against `retention.site_budget_mb` in `config/idhazh.json` |
| B6 | Independent accuracy evidence beyond six canary pairs, such as hand marks scored against the thresholds | No accuracy rate against people | A person or labelling resource, run through `docs/how-to/evaluate-content-similarity-judge.md` |
| B7 | A re-run judging only what it lacks | A re-run re-judges the whole night; the fit counts each pair once | A re-run share of judgments above 10%, counted from `pair-verdicts` by run |
| B8 | Re-measuring the plan-time yardstick in `similarity/budget.py` | The guard stays conservative against the measured seconds a pair | 14 nights of `decode_seconds_total` in `threshold-history` |

Table C - Words this plan and the docs use

| Id | Word | Meaning |
| --- | --- | --- |
| C1 | same-story share | Of the judged pairs at a score, the fraction the judge calls the same story |
| C2 | usable pair | A judged pair whose two readings, in file order and swapped, agree |
| C3 | lower bound threshold | The score where the same-story share is `lower_share_level`; below it pairs are fully dissimilar |
| C4 | upper bound threshold | The score where the same-story share is `upper_share_level`; above it pairs are fully similar |
| C5 | ambiguous bucket | Scores between the two thresholds. Its thin slices sit at each threshold; its coarse slices fill the middle |
| C6 | fully similar bucket, fully dissimilar bucket | Pairs above the upper or below the lower threshold, sampled lightly as live canaries |
| C7 | slice | A narrow score range with its own sampling chance |
| C8 | sampling chance, weight | Usable pairs over available pairs in a slice that night; the weight of a pair is 1 over its chance |
| C9 | canary pair | One of the known-answer pairs in config, judged once per run |
| C10 | widening, narrowing | Moving a threshold out (lower down, upper up) or in; widening makes the ambiguous bucket larger |
| C11 | ignore range | A gap this small or smaller is not acted on |

Table D - Settings in `config/judges/content-similarity-judge.json` (the one home for these numbers)

| Id | Keys and defaults | Meaning |
| --- | --- | --- |
| D1 | `draw.pair_budget` 150 | Live pairs judged a night; canary pairs come on top |
| D2 | `draw.slice_width` 0.01, `draw.thin_slices_each_end` 6, `draw.coarse_slice_width` 0.04 | Slice sizes; edges sit on a grid of `slice_width` |
| D3 | `draw.bucket_weights` lower_thin 40, upper_thin 30, middle_coarse 20 | Shares of what remains after the two lightly sampled buckets |
| D4 | `draw.fully_similar` weight 6, minimum 2, maximum 6; `draw.fully_dissimilar` weight 4, minimum 1, maximum 4 | The weight sets the target; the minimum and maximum bound it |
| D5 | `draw.thresholds_lookback_days` 14 | The newest `threshold-history` row inside this many days sets the thresholds in force |
| D6 | `thresholds.lower_start` 0.70, `thresholds.upper_start` 0.93 | Used when no row is inside the lookback |
| D7 | `thresholds.lower_share_level` 0.05, `thresholds.upper_share_level` 0.90 | The same-story share that defines each threshold |
| D8 | `thresholds.window_nights` 7, `thresholds.near_threshold_width` 0.06, `thresholds.minimum_usable_pairs` 240 | The evidence read for each threshold |
| D9 | `thresholds.ignore_range` 0.01, `thresholds.nights_running_required` 2 | When a gap counts |
| D10 | `thresholds.widening_step` 0.02, `thresholds.narrowing_step` 0.005, `thresholds.far_gap` 0.06, `thresholds.far_gap_step` 0.02 | The largest move in a night |
| D11 | `thresholds.lowest_lower_threshold` 0.50, `thresholds.highest_upper_threshold` 0.99, `thresholds.smallest_gap` 0.12 | Limits on the two thresholds |
| D12 | `thresholds.pull_start_steepness` 24.6, `thresholds.pull_spread` 8.0, `thresholds.pull_window_nights` 28, `thresholds.pull_minimum_nights` 7 | The pull on the curve's steepness |
| D13 | Source of every default | Andre's simulation over replayed pools of 2026-11-09 to 2026-11-16, when nothing below 0.88 had been judged. Provisional until the first 7 real nights. A value changes by editing the file and its `version` |

Table E - What each ledger stores (names are the columns)

| Id | Ledger and part | Columns |
| --- | --- | --- |
| E1 | `pair-verdicts`, one row per pair put to the judge | Today's pair row, except: dropped `judge_id`, `judged_by_run_id` and the retired-heading shims; renamed `composite_score` to `similarity_score` and `usable` to `readings_agree`; `similarity_score` and `cosine` run -1 to 1, because the draw now meets pairs below 0. Added: `bucket`, `slice_low`, `slice_high`, `slice_pairs_available`, `slice_pairs_judged`, `slice_pairs_usable`, `sampling_chance`, `lower_threshold_in_force`, `upper_threshold_in_force`, `config_versions`. The draw file keeps the one-shape-for-both rule: judge columns, `slice_pairs_usable` and `sampling_chance` stay empty until judged and collected |
| E2 | `threshold-history`, identity and meaning | `date`, `run_id`, `scorer_model`, `cosine_weight`, `judge_model`, `judge_policy_version`, `config_versions` |
| E3 | `threshold-history`, once for each of `lower_` and `upper_` | `threshold_before`, `share_level`, `nights_used`, `usable_pairs_used`, `window_first_date`, `curve_intercept`, `curve_steepness`, `pull_centre`, `pull_spread`, `estimate`, `gap`, `nights_beyond_ignore_range`, `move`, `move_limited_by`, `held_because`, `threshold_after` |
| E4 | `threshold-history`, once a night | `above_upper_pairs_available`, `above_upper_pairs_usable`, `above_upper_same_story_estimated`, `below_lower_pairs_available`, `below_lower_pairs_usable`, `below_lower_different_story_estimated`, `runners_expected`, `runners_reported`, `pairs_dealt`, `pairs_valid`, `pairs_agreed`, `pairs_unreadable`, `pairs_refused`, `pairs_abandoned`, `disagreement_rate`, `unclear_rate`, `decode_seconds_total`, `decode_seconds_slowest_runner`, `canary_answers` |
| E5 | The two closed vocabularies | `move_limited_by`: none, widening_step, narrowing_step, far_gap_step, lowest_allowed, highest_allowed, smallest_gap. `held_because`: none, not_enough_evidence, fit_failed, within_ignore_range, waiting_for_second_night |
| E6 | `canary_answers` and `config_versions` | Each is one JSON text. `canary_answers` is an object keyed by canary id whose value lists the answer in file order, the answer swapped, the two first-token margins, the prompt tokens and the runner index, with null for a missing reading, for example `{"same-1":["YES","YES",0.981,0.993,812,2]}`. `config_versions` is an object keyed by config path relative to `config/`, sorted keys, no spaces |
| E7 | The runner's reading (a scratch row shipped between jobs, not a ledger) | Today's `ContentSimilarityJudgeMetrics` columns, plus from row 6 one nullable JSON text column `canary_answers` holding the answers of the canary pairs that runner judged. From row 8 it is `StorySimilarityRunnerReport`, with `judge_id` dropped and `pairs_read` renamed `pairs_valid` |

Table F - Formulae (ASCII; `s` is a score, `y` is 1 for YES and 0 for NO or UNCLEAR)

| Id | Step | Formula |
| --- | --- | --- |
| F1 | Chance and weight of a pair in slice k | `c_k = u_k / m_k` and `w = 1 / c_k`, where `m_k` is the pairs available in the slice that night and `u_k` the usable pairs judged in it |
| F2 | Evidence for one threshold | Usable pairs scoring within `near_threshold_width` of `threshold_before`, over the last `window_nights` nights, carrying tonight's meaning stamp, newest filed row per `pair_key` |
| F3 | Curve | `P(y=1 given s) = 1 / (1 + exp(-(a + b*s)))`, with `(a, b)` maximising `sum_i ln P(y_i given s_i) - (b - b0)^2 / (2 * sigma^2)`. `b0` is the median of that threshold's `curve_steepness` over the last `pull_window_nights` rows (at least `pull_minimum_nights` values, else `pull_start_steepness`); `sigma` is `pull_spread`. Unweighted |
| F4 | Estimate and gap | `estimate = (ln(p / (1 - p)) - a) / b` with `p` the threshold's share level; `gap = estimate - threshold_before` |
| F5 | Move | When `abs(gap)` exceeds `ignore_range` on `nights_running_required` nights in a row with the same sign and the evidence minimum is met, `threshold_after = threshold_before + gap`, limited to at most `widening_step` (outward) or `narrowing_step` (inward), or `far_gap_step` either way when `abs(gap)` exceeds `far_gap`; then limited by the lowest, highest and smallest-gap settings. Otherwise it holds, and `held_because` says why |
| F6 | Weighted totals | `above_upper_same_story_estimated = sum of w_i * y_i` over usable pairs above the upper threshold; `below_lower_different_story_estimated = sum of w_i * (1 - y_i)` over usable pairs below the lower threshold. With a handful of pairs a night it is an alarm and never moves a threshold |

## 1. Status Reckoner

Table G - Status Reckoner

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | 1 | Judge only new pairs | - | A | PENDING | - | - | - |
| G2 | 2 | Version the judge's config files | - | A | DONE | urban-memory | - | - |
| G3 | 3 | Declare the two new ledgers | - | A | DONE | musical-happiness | - | - |
| G4 | 4 | Draw by weighted slice and file pair verdicts | 1, 2, 3 | B | PENDING | - | - | - |
| G5 | 5 | Find and move both thresholds | 4 | C | PENDING | - | - | - |
| G6 | 6 | Judge canary pairs once per run | 5 | D | PENDING | - | - | - |
| G7 | 7 | Judgement page without the retired data | 4 | E | PENDING | - | - | - |
| G8 | 8 | Retire the old record, fit, knobs and ledgers | 5, 6, 7 | F | PENDING | - | - | - |

## 2. The draw

### Row #1 - Judge only new pairs

- **Scope:** Level 3. The nightly draw skips pairs whose two stories are both from earlier days: they were judged the night they were new, and the merge pass cannot use them.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/tests/test_same_story.py`
  - `backend/tests/pipeline/test_same_story_window.py`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:**
  - Local: `backend/tests/test_same_story.py` and `backend/tests/pipeline/test_same_story_window.py` through the project's test selector ([run the gates](../docs/how-to/run-the-gates.md)); ruff and mypy on the touched Python files; `python backend/utilities/doc_load.py` on the edited pages. New in-memory test: one story from the night and two cross-outlet stories from earlier days with equal vectors; the two pairs that include the night's story come out and the pair of the two earlier stories does not.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run every drawn pair names at least one item of the night's published payload; if one does not, revert the guard.
- **Oracle:** every pair `cross_source_pairs` yields has a story from the night's own day, which is exactly the set the merge pass can use. It cannot settle whether a story published after the council's checkout is missed (H3).
- **Decisions:**

Table H - Row 1 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | A pair of two earlier-day stories is never drawn. The merge pass only joins the night's own stories, so such a pair cannot change what publishes. Replaying the repo's draw functions over 2026-11-03 to 2026-11-16 found 0 of 733 drawn pairs with a story from the night's own day already judged, against 772 of 1,046 drawn pairs of two earlier-day stories | Fowler |
| H2 | The window reaches `ceil(window_hours / 24)` earlier days, two at 36 hours. The docstrings in the three stage files and in `collapse_same_story`, the window test's name and the `growing-reads.md` line say one; they are corrected, and the `cross_source_pairs` docstring (it promises exactly the pairs the merge pass weighs) becomes true | Fowler |
| H3 | A story published after the council's checkout would go undrawn. The replay matched the committed draw size on 14 of 14 nights, so no action; a mismatch in the named observation reopens it | Fowler |

- **Rejected alternatives:**

Table I - Row 1 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | A memory of judged pairs, read from the last nights' ledger rows | It would catch republished addresses and same-date re-runs, neither seen in 14 nights, and it leaves earlier-day pairs in the pool | A bounded two-night read plus stamp matching; price it by counting repeats over 10 nights after this row | Fowler |
| I2 | Leave as is | Over half of 2,323 judgments since 2026-11-03 were repeats | Nothing to build; price the delay by the nightly share of repeats | Plan intent |

### Row #2 - Version the judge's config files

- **Scope:** Level 2. The judge's config file carries a `version` revision date, and one function returns the versions a night used as the JSON text both ledgers store.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `backend/tests/test_similarity_budget.py`
  - `docs/concepts/config.md`
- **Acceptance gates:**
  - Local: the config contract test (a missing, malformed or future `version` is refused; `config_versions()` returns the one-line ASCII JSON of Table E for the config directory it was handed); ruff and mypy; doc check.
  - CI: the required checks are authoritative.
- **Oracle:** a hand-built config directory returns exactly the expected JSON text. It cannot settle that a maintainer bumps `version` when a value changes; the rule lives in `docs/concepts/config.md`.
- **Decisions:**

Table J - Row 2 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | `version` is the UTC date of the last edit that changed a value, bumped in the same commit. A date, never an integer | Fowler |
| J2 | `config_versions` is one JSON text (Table E) naming every judge-owned config file the night read: one now, two after row 6. A new config file then needs no new column | Fowler |
| J3 | `docs/concepts/config.md` states the rule for the judge's files and says the other files do not carry it yet (B4) | Fowler |
| J4 | `version` is a required field of the judge's model, so the loader refuses a missing or malformed one at its first read. That it is a real calendar date no later than today (UTC) is checked in `settings.py`, the only place the clock is read, so the contract stays the same on every day. `config_versions()` takes the config directory and builds its text from the loader, naming the file by one module constant that row 6's canary loader reuses beside the same date check | Fowler |

- **Rejected alternatives:**

Table K - Row 2 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | One version column per config file | A new config file would change both contracts | A contract change per file; price it by counting the config files a night reads | Fowler |
| K2 | Reuse the shape `version` in `config/idhazh.json` | It moves only when the shape changes, so it cannot say which tuning a night used | A `revised_on` field and a bump rule for that shared file; price it by counting judge keys left in it after row 8 | Fowler |

### Row #3 - Declare the two new ledgers

- **Scope:** Level 5. Ledgers `pair-verdicts` and `threshold-history` are registered with their contracts, keys, loaders, staging, retention and explorer consent; nothing writes them yet and the old ledgers stay.
- **Files touched:**
  - `backend/idhazh/contracts/story_similarity_pair_verdict.py`
  - `backend/idhazh/contracts/story_similarity_threshold_history_row.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/content_similarity_judge/ledger_reads.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/staging.py`
  - `config/ledgers.json`
  - `config/gardener/compact-content-similarity-judge-pair-verdicts.json`
  - `config/gardener/compact-content-similarity-judge-threshold-history.json`
  - `config/gardener/config/idhazh_gardener.json`
  - `config/idhazh.json`
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `tests/fixtures/contracts/story-similarity-pair-verdict/a-judged-pair-with-its-slice-and-chance.json`
  - `tests/fixtures/contracts/story-similarity-threshold-history-row/a-night-that-held-both-thresholds.json`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_story_similarity_pair_verdict.py`
  - `backend/tests/contracts/test_story_similarity_threshold_history_row.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/test_content_similarity_judge_ledger_reads.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/gardener/_garden.py`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/concepts/partitions.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/glossary.md`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:**
  - Local: the new contract tests (round trip through `ledger.persist` and the loaders in a temporary state directory; refusals: slice edges inverted, a chance outside 0 to 1, a non-zero `move` with `held_because` other than none, a held threshold whose `threshold_after` differs from `threshold_before`, a non-JSON `canary_answers` or `config_versions`); the registry, gardener, schema-drift (every contract has a fixture), no-CSV and council-import tests; the frontend catalog spec and the vocabulary tests through the test selector; ruff, mypy and the TypeScript typecheck; doc check.
  - CI: the required checks are authoritative, including the bundle gate on the two consented ledgers.
- **Oracle:** the registry load check (every `LedgerName` member is in exactly one family entry, and the typed name is spelled from family and value) accepts both ledgers and refuses a copy with one edit missing. It cannot settle that the columns suffice to recompute a night; row 5's oracle does.
- **Decisions:**

Table L - Row 3 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Values `pair-verdicts` and `threshold-history` in family `content-similarity-judge`; members `CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS` and `CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY`; contract classes `StorySimilarityPairVerdict` and `StorySimilarityThresholdHistoryRow`. A value says what the ledger holds and never the kind of thing it is, and the family folder scopes it to this judge | Fowler |
| L2 | Both are raw-and-compact with explorer consent on, retention on the committed chain (packed after 1 day, daily files 45 days, monthly 93 days, yearly 36 months), one compaction declaration each, both named in the gardener's task list | Fowler |
| L3 | Judge-ledger door rules: the row names none of the door's own columns; the pair row names its part `work_part_index`; keys are (date, run_id, work_part_index, pair_key) and (date, run_id); rows file under the judged date. Contract versions are the date the row lands, with a one-line changelog and no read-side shim, because neither shape has an earlier row | Fowler |
| L4 | Reader before writer: this row lands the contracts, registry entries and loaders `load_pair_verdicts` and `load_threshold_history`, each taking the named days to read; callers pass at most `window_nights` and `pull_window_nights` days. No writer lands before row 4 | Fowler |
| L5 | The loaders live in the judge's own package, not in `ledger/rows.py`: the council's import test lets exactly three old judge contracts cross into a council verb and nothing else, and the new contracts join the judge-only list. Row 8 deletes the three crossing contracts and empties that list | Fowler |
| L6 | The shared vocabulary (verdict words, refusal reasons, model id types, stamp digests) stays in `story_similarity_pair.py` until row 8 moves it into the new pair module; the new module imports it from there | Fowler |
| L7 | `similarity_score` and `cosine` run -1 to 1. The old floor of 0 held only while the draw never looked below 0.88; the fully dissimilar bucket can meet a negative cosine | Fowler |
| L8 | Explorer consent copies both ledgers' compact indexes into the site; the bundle gate is the alarm on index size | Fowler |

- **Rejected alternatives:**

Table M - Row 3 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Keep `scored-pairs` and `fitted-thresholds` under new row shapes | A changed shape under an old name is a breaking change in place and needs a read-side shim; new names start clean | Fewer registry edits; price it by this row's diff against the last ledger addition's about 30 files | Fowler |
| M2 | One ledger with a row-type column | Each row would leave about half its columns empty, or repeat the night's numbers on every pair row | One registry entry fewer; price it by the nightly pair-row count times the night's column count | Fowler |

### Row #4 - Draw by weighted slice and file pair verdicts

- **Scope:** Level 5. The nightly draw sorts new pairs into slices and buckets and takes pairs at known chances (Tables C and D), the judge runs them, and the collecting job files each as a `pair-verdicts` row with its sampling chance; the old pair, record and fit stages leave the nightly flow, and the thresholds in force are the newest `threshold-history` row's or the configured starts.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/similarity/slices.py`
  - `backend/idhazh/similarity/draw_allocation.py`
  - `backend/idhazh/similarity/sampling_chance.py`
  - `backend/idhazh/similarity/selection.py`
  - `backend/idhazh/similarity/budget.py`
  - `backend/idhazh/similarity/counting.py`
  - `backend/idhazh/similarity/fit.py`
  - `backend/idhazh/similarity/published_line.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/file_pair_verdicts.py`
  - `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `backend/utilities/sample_sheet.py`
  - `backend/tests/test_similarity_slices.py`
  - `backend/tests/test_similarity_draw_allocation.py`
  - `backend/tests/test_similarity_sampling_chance.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_tenant.py`
  - `backend/tests/test_similarity_budget.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_counting.py`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/test_similarity_published_line.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/test_holdout_marks.py`
  - `backend/tests/test_named_utility_inputs.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `docs/concepts/growing-reads.md`
  - `docs/concepts/glossary.md`
- **Acceptance gates:**
  - Local: the new and edited tests through the test selector. In-memory tests: each bucket's pair count follows Tables C and D and the allocation rule (N2); every non-empty slice gets at least one pair and none more than its pool; the same night drawn twice gives the same pairs; a pair scoring below 0 is drawn and filed; every filed row carries `sampling_chance` equal to usable over available for its slice; no `threshold-history` row inside the lookback gives the configured starts and a newer row's `threshold_after` wins; the scheduler names a night with no `pair-verdicts` row and no other; the draw and verdict files read back through the contract; a night with a lost runner files its surviving rows; the council's judge-module lists name the new stage and no deleted one. Ruff, mypy, doc check.
  - Before merge: replay 2026-11-09 to 2026-11-16 through the new draw with the configured starts and record pairs judged a night per bucket against Table D's budget.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run the draw rows carry slice columns, `pair-verdicts` holds the night's rows with chances, and nothing is written to the old ledgers.
- **Oracle:** on a fixed in-memory night the per-slice judged counts and every stored sampling chance equal a hand-worked table. It cannot settle whether the budget gives each threshold its evidence minimum; the first 7 nights of row 5 show it.
- **Decisions:**

Table N - Row 4 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | Slices and buckets follow Tables C and D. Slice edges sit on a grid of `draw.slice_width`; the draw rounds the lower threshold down and the upper up to the grid, and each stored row keeps the thresholds in force unrounded beside its slice edges | Andre (grid), Fowler (rounding) |
| N2 | Allocation: the two lightly sampled buckets first (their weight share of the budget, limited to their minimum, maximum and pool); the remainder splits by the three ambiguous weights; inside a sub-bucket every slice gets an equal share and at least one pair when it has any; a slice's unspent share goes to its sub-bucket's other slices, then to the other ambiguous sub-buckets in weight order; the night judges fewer than the budget only when every ambiguous slice is spent. Pairs within a slice go in the draw's hash order of date, scorer stamp and ids, with no seed | Andre |
| N3 | Sampling chance is usable over available for the slice, computed when the night's rows are filed, because a draw cannot know which pairs will agree. The weight 1 over chance is used in the weighted totals only (F6) | Andre |
| N4 | A partly judged night files the pairs its runners returned. A night is read for the scheduler once it has any `pair-verdicts` row, so the scheduler names only nights with none; the old rule of counting a date once, only when every runner reported, goes with the record | Fowler |
| N5 | The runner's reading stays what it is today (`ContentSimilarityJudgeMetrics`), a scratch row shipped to the collecting job, and is no longer filed into a ledger. Until row 5 the collecting job logs its totals; row 5 folds them into the night's row; row 8 renames it `StorySimilarityRunnerReport` when its ledger goes. `council/metrics_sink.collect_judge_metrics` has no judge caller after this row and stays as the council's generic capability (Y6) | Fowler |
| N6 | `budget.py` counts the budget and, after row 6, the canary pairs; it no longer reads `adaptive_dedup_threshold`. The yardstick is untouched (B8) | Fowler |
| N7 | The old nightly flow (`count_verdicts`, `set_merge_line`, `counting`, `fit`, `published_line`) is deleted here because nothing may feed it once the draw changes. The old ledgers' registration and the console readers stay until rows 7 and 8, so the console shows the last night the old fit ran | Fowler |
| N8 | The tenant's `publication_inputs` returns no path in this row: the collecting job reads only tonight's verdict files, so the sparse checkout needs nothing from earlier nights. The scheduler reads `pair-verdicts` by named days inside the council's window | Fowler |

- **Rejected alternatives:**

Table O - Row 4 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Keep the old record running beside the new draw for a while | Its fit assumes the old draw, so it is wrong from the first night, and a second writer is the debt this plan removes | Nothing to build; price it by running both for 7 nights and comparing lines | Fowler |
| O2 | Weights from the budget alone, with no per-slice chance stored | The chance needs each night's available and usable counts, which only the collecting job has | A guess at 1 over the sampled fraction; price it by comparing against the stored chance on 7 nights | Andre |

### Row #5 - Find and move both thresholds

- **Scope:** Level 5. After the pair rows are filed, the night reads the last `window_nights` nights of `pair-verdicts`, estimates both thresholds (Table F), and files one `threshold-history` row holding every number of the computation, the runner totals and the weighted totals; the next night's draw reads its `threshold_after` columns.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/ledger/rows.py`
  - `backend/idhazh/similarity/threshold_evidence.py`
  - `backend/idhazh/similarity/threshold_curve.py`
  - `backend/idhazh/similarity/threshold_move.py`
  - `backend/idhazh/similarity/statistics.py`
  - `backend/idhazh/stages/review_thresholds.py`
  - `backend/idhazh/stages/file_pair_verdicts.py`
  - `backend/tests/test_similarity_threshold_evidence.py`
  - `backend/tests/test_similarity_threshold_curve.py`
  - `backend/tests/test_similarity_threshold_move.py`
  - `backend/tests/test_similarity_statistics.py`
  - `backend/tests/test_review_thresholds.py`
  - `backend/tests/test_similarity_tenant.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
  - `docs/concepts/growing-reads.md`
  - `docs/concepts/glossary.md`
- **Acceptance gates:**
  - Local: the new tests through the test selector. Curve test: the Newton fit equals a brute-force grid maximiser of the same penalised likelihood on a hand-built table, to 1e-4. Move tests: every `move_limited_by` and `held_because` value is reachable; a 0.05 shift in synthetic evidence first moves a threshold on night 3 or 4 of the shift and has caught up within 8 nights; widening is faster than narrowing for both thresholds; a gap over `far_gap` takes `far_gap_step` both ways; a changed meaning stamp restarts the window; a re-run's duplicate rows count once; the pull centre is the start value until `pull_minimum_nights` values exist; the tenant's `publication_inputs` names exactly the day folders, compact files and indexes the loaders read for `window_nights` and `pull_window_nights` nights. Ruff, mypy, doc check.
  - CI: the required checks are authoritative.
  - Named observation: on the first 7 real nights read `threshold-history` and say per threshold whether `usable_pairs_used` reached `minimum_usable_pairs` and where the curve's estimate sits against the start.
- **Oracle:** for every night of a 14-night in-memory run, recomputing the estimate from the stored curve columns, and the move and `threshold_after` from the stored estimate, thresholds and counts, reproduces every stored value, so a night can be recomputed by hand from its row and `pair-verdicts`. It cannot settle that the curve shape holds on the real judge below 0.88; the first 7 real nights show that.
- **Decisions:**

Table P - Row 5 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| P1 | Formulae are Table F with the Table D defaults, which are simulated values (D13) | Andre |
| P2 | Widening is fast and narrowing slow for both thresholds, because a threshold sitting too far inside the uncertain range leaves wrong answers in a bucket the draw barely checks. Lower: falls up to `widening_step`, rises up to `narrowing_step`. Upper: rises up to `widening_step`, falls up to `narrowing_step`. A gap over `far_gap` takes `far_gap_step` both ways, so a bad start is found in about 6 nights, not 15. This is the opposite of the site's rule for `floor_min` (falling fast), which governs what publishes and stays out of scope (B1) | Andre |
| P3 | Weights are used only for the weighted totals (F6). In the curve they hurt: in simulation the share of lower-threshold estimates off by more than 0.02 went from 4% to 42% with weights, and to 8% with weights capped at three times the median; chance depends only on score, so the curve needs none | Andre |
| P4 | The curve is fitted in pure Python by Newton steps with step halving on the penalised log-likelihood (two parameters, about 1,100 points at most, at most 50 iterations). A fit that does not converge, or returns steepness not above zero, holds the threshold with `held_because` `fit_failed`. No dependency is added: scikit-learn and scipy sit in the dev extra, and scikit-learn's penalty is centred on zero rather than on the pull centre | Fowler |
| P5 | The evidence keeps only rows with tonight's meaning stamp (judge model, prompt digest, grammar digest, scorer model, cosine weight, judge policy version), so a change restarts the window by itself and `nights_used` shows it. A re-run's duplicate rows count once (newest filed row per `pair_key`). A night settled out of order is filed under its own date and later nights are not recomputed | Andre, Fowler |
| P6 | `held_because` precedence: `not_enough_evidence`, then `fit_failed`, then `within_ignore_range`, then `waiting_for_second_night`. A held threshold keeps `threshold_after` equal to `threshold_before`, and its estimate is still stored | Fowler |
| P7 | "Nights in a row" counts consecutive nights with a gap beyond the ignore range and the same sign, read from the previous row's stored `gap`; a move does not reset the count | Andre |
| P8 | The night's row carries the runner totals folded from the shipped runner readings (sums, and the slowest runner's seconds; `pairs_read` becomes `pairs_valid`) and `canary_answers`, empty until row 6 | Fowler |
| P9 | The collecting job reads from a sparse checkout, so the tenant's `publication_inputs` declares the day folders, compact files and indexes of `pair-verdicts` for `window_nights` nights and of `threshold-history` for `pull_window_nights` nights, using the same window arithmetic as the loaders; an input the loaders read and the declaration omits fails the collecting job | Fowler |

- **Rejected alternatives:**

Table Q - Row 5 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | The median of each night's own estimate instead of pooling the window | A single night's estimate is off by more than 0.02 in about a third of simulated nights, against 4% for the 7-night pool | Nothing to build; price it by the share of single-night estimates off by more than 0.02 in the first 14 real nights | Andre |
| Q2 | Widen automatically after a few held nights | On thin evidence a "widen after 3 held nights" rule walked the lower threshold to 0.26 instead of 0.69 in 100 of 100 simulated runs | A rule with a measured guard; price it by simulating it against the first 14 real nights | Andre |

## 3. The canary pairs

### Row #6 - Judge canary pairs once per run

- **Scope:** Level 3. Six known pairs in a new config file are judged once per run, dealt over the runners and shifted one runner each night; their answers are stored as the night's `canary_answers`, a wrong answer is logged and stored, and nothing else reacts.
- **Files touched:**
  - `config/judges/content-similarity-canaries.json`
  - `backend/idhazh/contracts/knobs/content_similarity_canaries.py`
  - `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/budget.py`
  - `backend/idhazh/stages/judge_canary_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/review_thresholds.py`
  - `backend/tests/contracts/test_content_similarity_canary_config.py`
  - `backend/tests/test_judge_canary_pairs.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_tenant.py`
  - `backend/tests/test_similarity_budget.py`
  - `backend/tests/contracts/test_content_similarity_judge_metrics.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
  - `docs/concepts/config.md`
  - `docs/concepts/glossary.md`
- **Acceptance gates:**
  - Local: the config contract refuses a set missing a kind, with duplicate ids, an expected answer that does not match its kind, an empty or non-ASCII summary, over 12 pairs, a synthetic pair without its id prefix, or a missing `version`; the committed file is ASCII. Stage tests with a recorded-response client: a wrong answer is logged and stored as given; disagreeing orders are stored as given; the request bytes equal a live pair's for the same two summaries; the runner for pair i is `(i + date ordinal) mod runners`; no canary id reaches the draw, the verdict files, `pair-verdicts` or the curve evidence; `canary_answers` round-trips as Table E6 says; the budget guard counts the canary pairs. Ruff, mypy, doc check.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run `threshold-history.canary_answers` holds all six ids exactly once; read each answer against its expected one.
- **Oracle:** the request bytes for a canary pair equal those of a live pair with the same two summaries, so the judge cannot tell them apart. It cannot settle whether the agent-written labels are right, or whether the judge is right on pairs unlike these six.
- **Starting set** (found in the published digest and labelled from the summaries alone on 2026-11-17; re-verify each against the published day files at dispatch, then copy each summary into the config):

Table R - Starting canary pairs

| Id | Canary id | Kind | Left (date, item id) | Right (date, item id) | Expected | Why |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | `same-1` | same | 2026-11-07, `india-4at2refk8ng9fhy3` | 2026-11-07, `india-689nbq3f7gm8ja9d` | YES | One listed company's filing: a director retires on one date at one age under one governance rule |
| R2 | `same-2` | same | 2026-11-11, `india-6zsc86d0xcfnqvx8` | 2026-11-11, `india-aeeq7vvdytycwhwr` | YES | One technology firm ends visa sponsorship for one division, with a year-end deadline |
| R3 | `different-1` | different | 2026-11-04, `world-0dc4qgdn09ta6vae` | 2026-11-04, `business-economy-2nhmc06msp85an7w` | NO | A school graduation and a company's data-centre investment: nothing in common |
| R4 | `different-2` | different | 2026-11-10, `world-7pcx0fkda710c87y` | 2026-11-08, `india-w7s3sydgkhr0bkna` | NO | A climate summit opening and a youth cricket match: nothing in common |
| R5 | `unclear-1` | unclear | 2026-11-07, `ai-gp9n67v36c3r4t64` | 2026-10-24, `ai-q5vhq5s6p62e7sb2` | UNCLEAR | Two one-line cartoon captions; neither says what happened |
| R6 | `unclear-2` | unclear | 2026-11-07, `ai-act5etj22gy5jvdn` | 2026-11-07, `world-t4n61hawy70wkg6h` | UNCLEAR | A one-line cartoon caption on an election's aftermath beside a specific report from it; the caption names no event |

- **Decisions:**

Table S - Row 6 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| S1 | Once per run, not once per runner: six judgments replace 24 to 36. Pair i goes to runner `(i + date ordinal) mod runners`, so over a few nights every pair has run on every runner | Andre |
| S2 | Ids are unique across runs, stable, and never reused for different text or a different expected answer; a corrected pair gets a new id. One pair's history reads down the nights of `threshold-history` | Andre |
| S3 | Stored only as `canary_answers` (Table E6) on the night's row. Each runner's scratch reading carries its own pairs' answers in the column Table E7 names, and the collecting job merges them. The expected answer lives in the config under the id and code compares the two. A canary pair is never a `pair-verdicts` row | Fowler |
| S4 | A wrong answer (not the expected one, a split between the two orders, or a refused reading) is logged as a warning naming the id. Nothing holds, re-runs or stops (B2) | Andre |
| S5 | The agent finds and labels the pairs; no person marks them. Same: same actors, action and occasion. Different: no actor, place or topic in common. Unclear: at least one summary too vague to name what happened, the judge prompt's own definition. Real published summaries only; a hand-built pair carries the id prefix `synthetic-` and `origin` synthetic, named where it sits. Each pair records `labelled_by` and a one-line `basis` | Andre |
| S6 | The judge had never answered UNCLEAR on a real pair when checked on 2026-11-17, so the two unclear pairs may answer NO every night. That is a finding about the judge, not a fault in the check | Andre |
| S7 | Summary text lives in the config file (ASCII JSON) so a retired published day cannot orphan a pair. At most 12 pairs, every kind present, changed only by a reviewed edit that bumps `version`; no automatic refresh, because that would put fetched text into the reference set unreviewed. A runner judges its canary pairs before its live pairs, which finds a wrong model, a runtime change that breaks the constrained answer, and a prompt or grammar edit; it cannot find decay late in a run | Fowler |
| S8 | A canary pair goes through the same request builder as live text and is never presented as an instruction; `judge_pair` takes two summaries instead of two digest items | Fowler |

- **Rejected alternatives:**

Table T - Row 6 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T1 | The same six pairs on every runner | It shows the runners agree with each other, not that the judge is right | Nothing to build; price it at 24 judgments a night | Andre |
| T2 | One ledger row per canary pair per run | Easiest to query | A third ledger (Table M's diff); price it by that diff | Fowler |

## 4. The console and the retirement

### Row #7 - Judgement page without the retired data

- **Scope:** Level 3. The Judgement page stops reading the old fitted line, the record and the hand-mark scores: panels whose data is gone are removed, the hand-marks panel stays, and nothing new is drawn (B3).
- **Files touched:**
  - `frontend/src/routes/console/judgement/+page.server.ts`
  - `frontend/src/routes/console/judgement/+page.svelte`
  - `frontend/src/routes/console/judgement/HoldoutMargin.svelte`
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte`
  - `frontend/src/routes/console/judgement/MergeLinePlot.svelte`
  - `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`
  - `frontend/src/routes/console/judgement/RecordGates.svelte`
  - `frontend/src/routes/console/judgement/VerdictSplit.svelte`
  - `frontend/src/lib/server/content-similarity-judge.ts`
  - `frontend/src/lib/server/content-similarity-holdout.ts`
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/server/recorded-line.ts`
  - `frontend/src/lib/console/applied-line.ts`
  - `frontend/src/lib/console/holdout.ts`
  - `frontend/src/lib/console/judgement-evidence.ts`
  - `frontend/src/lib/console/merge-line.ts`
  - `frontend/src/lib/console/verdict-split.ts`
  - `frontend/tests/applied-line.spec.ts`
  - `frontend/tests/appearance-config.spec.ts`
  - `frontend/tests/console-judgement-nothings.spec.ts`
  - `frontend/tests/holdout-domain.spec.ts`
  - `frontend/tests/holdout.spec.ts`
  - `frontend/tests/judgement-evidence.spec.ts`
  - `frontend/tests/ledger-rows.spec.ts`
  - `frontend/tests/merge-line.spec.ts`
  - `frontend/tests/similarity-ledgers.spec.ts`
  - `frontend/tests/span-sentences.spec.ts`
  - `frontend/tests/verdict-split.spec.ts`
  - `frontend/tests/support/console-sources.ts`
  - `frontend/tests/support/number-format.ts`
  - `frontend/tests/support/console-expect/console-window/judgement.ts`
  - `frontend/tests/support/console-window/judgement-fixtures.ts`
  - `frontend/scripts/canary-inventory.mjs`
  - `frontend/scripts/test-groups.ts`
  - `frontend/scripts/tests/canary-inventory.test.mjs`
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `backend/utilities/build_canary_day.py`
  - `backend/tests/test_console_payloads_producer.py`
  - `backend/tests/contracts/test_frontend_recorded_line.py`
  - `backend/tests/contracts/test_frontend_console_lists.py`
  - `docs/architecture/publishing/console.md`
  - `docs/architecture/publishing/console-site-size.md`
  - `docs/architecture/publishing/frontend.md`
  - `docs/concepts/console-design/the-rules-every-console-chart-obeys.md`
- **Acceptance gates:**
  - Local: the frontend specs and scripts above through the test selector; the backend tests that hold the hand-copied column lists in step; ruff, mypy, TypeScript typecheck; doc check.
  - Browser smoke on the integrated browser: the Judgement page with the hand marks present, then with every judge ledger absent, plus one cross-page visit; zero new console errors and zero new 404s.
  - Design review of the changed page against `docs/concepts/design-system.md`, on one representative view.
  - CI: the required checks are authoritative.
- **Oracle:** the page renders with every judge ledger absent and with only hand marks present. It cannot settle whether the page is good enough to ship; the design review does.
- **Decisions:**

Table U - Row 7 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| U1 | A panel is removed when its only data is the old fitted line, the cumulative record or the hand-mark scores of the old line. The hand-marks panel reads `holdout-pairs`, which stays | Fowler |
| U2 | The page says where the new ledgers are read: the Data explorer, where both carry consent (Table L2) | Fowler |
| U3 | The hand-copied column lists for the old ledgers and their binding tests are deleted with their panels; no list is added for the new ledgers, because no ordinary panel reads them | Fowler |

- **Rejected alternatives:**

Table V - Row 7 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| V1 | Rebuild the old panels on the new ledgers | Nobody asked for new panels (B3), and the old line panels describe a line that no longer exists | A page design and the hand-copied column lists; price it by the panels' current file count | Jony |

### Row #8 - Retire the old record, fit, knobs and ledgers

- **Scope:** Level 4. The six old ledgers, the cumulative record, the archive, the old line-fit settings and the disabled switch that lets assemble read a fitted line are deleted with their code, tests, registrations, committed state and docs, and the shared vocabulary moves into the new pair contract module.
- **Files touched:**
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/content_similarity_judge/evaluation_events.py`
  - `backend/idhazh/content_similarity_judge/run_evaluation.py`
  - `backend/idhazh/content_similarity_judge/score_evaluation.py`
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/content_similarity_judge_evaluation.py`
  - `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/contracts/story_similarity_runner_report.py`
  - `backend/idhazh/contracts/fitted_similarity_threshold.py`
  - `backend/idhazh/contracts/story_similarity_distribution.py`
  - `backend/idhazh/contracts/merge_line_holdout_score.py`
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `backend/idhazh/contracts/story_similarity_pair_verdict.py`
  - `backend/idhazh/contracts/ledger_name.py`
  - `backend/idhazh/contracts/knobs/placement.py`
  - `backend/idhazh/contracts/knobs/console.py`
  - `backend/idhazh/ledger/__init__.py`
  - `backend/idhazh/ledger/keys.py`
  - `backend/idhazh/ledger/paths.py`
  - `backend/idhazh/ledger/rows.py`
  - `backend/idhazh/ledger/staging.py`
  - `backend/idhazh/similarity/applied.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/prompt.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/score_merge_line_holdout.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/measure_judge_call.py`
  - `backend/utilities/sample_sheet.py`
  - `config/ledgers.json`
  - `config/idhazh.json`
  - `config/gardener/compact-content-similarity-judge-scored-pairs.json`
  - `config/gardener/compact-content-similarity-judge-fitted-thresholds.json`
  - `config/gardener/compact-content-similarity-judge-metrics.json`
  - `config/gardener/compact-content-similarity-judge-merge-line-holdout-scores.json`
  - `config/gardener/config/idhazh_gardener.json`
  - `packages/common-contracts/src/schemas/envelope.schema.ts`
  - `frontend/tests/ledger-catalog.spec.ts`
  - `services/feed-ingest-plan/src/metrics/publication-evidence.ts`
  - `tests/fixtures/feed-ingest-plan/publication-evidence.json`
  - `tests/fixtures/ledger-door/nested-prefixes.json`
  - `tests/fixtures/state/scored-pairs-before-the-stamp.csv`
  - `tests/fixtures/contracts/story-similarity-pair/scored-but-not-yet-judged.json`
  - `tests/fixtures/contracts/story-similarity-pair/judged-the-same-in-both-orders.json`
  - `tests/fixtures/contracts/story-similarity-pair/a-headline-match-scores-one.json`
  - `tests/fixtures/contracts/content-similarity-judge-merge-line-holdout-score/a-holdout-retention-has-eaten-into.json`
  - `tests/fixtures/contracts/content-similarity-judge-merge-line-holdout-score/a-line-scored-against-the-holdout.json`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/gardener/pre-yearly-retention/config/idhazh.json`
  - `tests/fixtures/gardener/pre-yearly-retention/config/ledgers.json`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/contracts/test_content_similarity_judge_evaluation.py`
  - `backend/tests/contracts/test_content_similarity_judge_metrics.py`
  - `backend/tests/contracts/test_story_similarity_runner_report.py`
  - `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`
  - `backend/tests/contracts/test_gardener_config.py`
  - `backend/tests/contracts/test_ledger_registry.py`
  - `backend/tests/contracts/test_merge_line_holdout_score.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_story_similarity.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/council/test_lifecycle.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/gardener/_garden.py`
  - `backend/tests/ledger/_fixtures.py`
  - `backend/tests/ledger/test_arrow_schema.py`
  - `backend/tests/ledger/test_ledger_files.py`
  - `backend/tests/ledger/test_lifecycle.py`
  - `backend/tests/ledger/test_nested_door_folder.py`
  - `backend/tests/retention/test_prune_range.py`
  - `backend/tests/test_completion_evidence.py`
  - `backend/tests/test_content_similarity_judge_evaluation.py`
  - `backend/tests/test_content_similarity_judge_evaluation_events.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_ledger_families.py`
  - `backend/tests/test_merge_line_holdout.py`
  - `backend/tests/test_similarity_applied.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_statistics.py`
  - `backend/tests/test_similarity_tenant.py`
  - `state/raw/content-similarity-judge/scored-pairs/`
  - `state/raw/content-similarity-judge/fitted-thresholds/`
  - `state/raw/content-similarity-judge/metrics/`
  - `state/compact/content-similarity-judge/scored-pairs/`
  - `state/compact/content-similarity-judge/fitted-thresholds/`
  - `state/compact/content-similarity-judge/metrics/`
  - `state/compact/content-similarity-judge/merge-line-holdout-scores/`
  - `state/content-similarity-judge/score-distribution.json`
  - `state/content-similarity-judge/archive/`
  - `docs/architecture/publishing/how-the-content-similarity-judge-follows-its-thresholds.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/publishing/autotune-search-quality.md`
  - `docs/architecture/publishing/llm-council.md`
  - `docs/architecture/publishing/publication-inventory.md`
  - `docs/architecture/contracts/ledger-registry.md`
  - `docs/architecture/contracts/persistence.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/concepts/config.md`
  - `docs/concepts/config/idhazh-gardener.md`
  - `docs/concepts/config/run-limits.md`
  - `docs/concepts/evaluation.md`
  - `docs/concepts/glossary.md`
  - `docs/concepts/growing-reads.md`
  - `docs/concepts/partitions.md`
  - `docs/concepts/pipeline-loop.md`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `docs/how-to/prune-a-collection.md`
  - `docs/reference/benchmarks/what-a-judge-pair-costs.md`
  - `docs/reference/benchmarks/what-the-margin-rule-changes.md`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:**
  - Local: a search of the whole tree for each retired name (the six ledger values and members, the contract classes and modules, the stage and similarity module names, `adaptive_dedup_threshold`, `applied_line`, `read_published_line`) finds history only; the registry loads; the existing same-story and assemble tests pass unchanged; the judge's backend tests, the frontend catalog spec and the frontend tests of row 7 through the test selector; ruff, mypy, TypeScript typecheck; doc check on every edited page.
  - CI: the required checks are authoritative.
  - Named observation: the next gardener run lists two compaction tasks for this family beside the hand-marks task, and the next council run files `pair-verdicts` and `threshold-history` rows only.
- **Oracle:** the registry load check passes with the six ledgers gone and the retired-name search is empty. It cannot settle that a checkout of an older commit still reads the state it wrote; git history keeps both together.
- **Decisions:**

Table W - Row 8 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| W1 | Nothing is migrated: old rows, the record and the archive are deleted with their folders, and no read-side shim is kept. The hand marks (`holdout-pairs`, its contract and the offline evaluation) stay | Fowler |
| W2 | The vocabulary L6 left behind moves into the new pair contract module and every importer is re-pointed, so the old pair module can be deleted | Fowler |
| W3 | The disabled `adaptive_dedup_threshold` switch and its readers are deleted, not re-pointed: nothing reads a fitted line. `stages/assemble.py` reads the configured `same_story` directly, so the published day is unchanged because the switch was off, and the site keeps its fixed `floor_min` (B1) | Fowler |
| W4 | The ledger that scored the old merge line against the hand marks is deleted with that line, and its command in `cli.py` and its how-to are removed | Fowler |
| W5 | The feed planner's `RecordedEventPairSchema` and its fixture copy the old pair columns and have no reader (searched 2026-11-18); both are deleted, or re-pointed if a reader exists at dispatch | Fowler |
| W6 | Tests and fixtures that used a retired ledger as their sample (the nested-folder tests, the gardener fixtures) switch to a surviving nested ledger | Fowler |
| W7 | The runner's scratch reading is renamed `StorySimilarityRunnerReport` when its ledger goes: `judge_id` dropped, `pairs_read` renamed `pairs_valid`. The council's shipping helper is untouched | Fowler |
| W8 | The council's import test empties its list of judge contracts allowed to cross into a council verb, because the three old crossing contracts are gone and the new ones are judge-only (L5) | Fowler |

- **Rejected alternatives:**

Table X - Row 8 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| X1 | Leave the old ledgers registered and empty | Six dead registry entries, six gardener tasks and their tests for nothing that reads them | Nothing to build; price it by the files rows 3 to 8 would not touch | Fowler |
| X2 | Re-point the disabled switch at the new upper bound threshold | Builds an unrequested feature that changes what publishes (B1) | The switch, a reader and tests; price it by the files W3 deletes | Fowler |

## 5. Open questions

Table Y - Open questions

| Id | Question | Recommended answer | Row it blocks |
| --- | --- | --- | --- |
| Y1 | Does the draw round the thresholds to the slice grid (lower down, upper up)? | Yes (N1); Andre confirms at dispatch | 4 |
| Y2 | Is a hand-written two-parameter fit acceptable in place of a new dependency? | Yes (P4) | 5 |
| Y3 | Does the Judgement page need a replacement panel for threshold history and canary answers? | No (B3): the Data explorer holds both | 7 |
| Y4 | Should the seven other eligible ledgers join the Data explorer? | Not here (B5) | - |
| Y5 | Lower share level 0.05 or 0.10? | 0.05; move to 0.10 if the fully dissimilar bucket shows the judge says YES on more than 1 in 20 clearly different pairs in the first week | 5 |
| Y6 | Delete `council/metrics_sink.collect_judge_metrics`, which no judge calls after row 4? | Keep it as the council's generic capability (N5) | 4 |
| Y7 | Is the two-nights-in-a-row confirmation worth its column? | Keep `nights_running_required` at 2; in simulation it cuts false moves only from 17 to 14 per 100 steady nights, so set it to 1 if the first 14 real nights show no false moves | 5 |

## See also

- [Similarity rule and instrument identity](../docs/architecture/publishing/autotune-content-similarity.md)
- [The ledger registry](../docs/architecture/contracts/ledger-registry.md)
- [Native contract compatibility](../docs/architecture/contracts/schemas.md)
- [Evaluate the judge offline](../docs/how-to/evaluate-content-similarity-judge.md)
- [Run the gates](../docs/how-to/run-the-gates.md)
- [Author a plan](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
