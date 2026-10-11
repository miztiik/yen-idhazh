# Summary-fidelity judge: the hard look (review record, 2026-10-11)

**Record**: the two reviews the owner asked for on 2026-10-11 - "a hard look at what matters, how we measure it, and what is measured and judged upon" - after ruling that the judge must judge summary quality across the digest, not per site. Andre (evaluation) designed what is judged, the test and the composite, on the 50 daily records under state/day-metrics/ and the research record TODO/20261011-summary-quality-metrics-research-record.md. Fowler (architecture) reviewed the structure, the split with plan 36 and the council plan's coverage of the gardener's strengths. Both are advice; the owner's rulings are in Table P of plan 65 (TODO/20261011-65-summary-fidelity-judge-plan.md).

Paths beginning review/, hardlook/ or council_src/ name the reviewers' working copies of the repository files of the same name (for example hardlook/plan36.md is plan 36, TODO/20260918-36-summary-quality-autotune-plan.md until 2026-10-11 and Section 5 of plan 65 since); the analysis code is not committed.

---

# Hard look: what the summary-fidelity judge measures, and what it judges

Andre (evaluation), 2026-10-11. Advice to the owner through the plan author. No plan file was edited.

Evidence: the 50 day records 2026-08-21..2026-10-10 (state/day-metrics/, 2026-09-19 absent), the design of
record (council_src/autotune-summary-quality.md), summary-metrics.md, checker.md, metrics.py, eval_row.py,
evaluation.txt, plan36.md and the current judge plan. Per-item rows are parquet and unreadable here, so where a
test needs items they are SIMULATED from each day's min/p25/p50/p75/max plus the band counts at HHEM 0.50 and
0.80; the day-to-day noise in every result is the real days' own. Every simulation draws fresh OS entropy; no
seed is fixed, so a re-run moves the last digit. Hardware: one shared vCPU, numpy 2.5, no scipy. Code and raw
outputs: hardlook/andre_hardlook_code/.

Lower-case ids (r1..r4, u1..u6, w1..w4) and member slugs are this report's; upper-case ids are the current
plan's tables and rows. Regimes found in the record (section 5.1): r1 qwen3-8b 08-22..08-26; r2 qwen3.5-9b
08-27..09-06; r3 09-07..09-23 (the step; internal movement near 09-15); r4 09-24..10-10 (metrics-4, shorter
summaries).

## 0. Answer first

| # | Finding | Where |
| --- | --- | --- |
| A | The owner is right: the site is the wrong unit for judging summary quality. Judge the whole digest's summaries, per production series, over the last 7 days against the trailing 28. | 1.1, 5 |
| B | Two corrections. The design-of-record's four metrics are Faithfulness, Coverage, Coherence and Fluency; "conciseness" is not one and no eval column measures it. Per-source extraction rot is a real reader failure that no summary metric sees at any unit; once row #1 deletes drift.py nothing watches it, so it needs an owner outside this judge. | 1.2, 1.3 |
| C | Digest-level daily statistics are quiet: day-to-day spread is about what binomial sampling predicts (overdispersion 0.5 to 1.25 in r2 and r4), because the per-source cap makes each day a quota sample. The day is still the right exchangeable unit (r3 runs up to 3.4 times binomial). | 3.3, 5.2 |
| D | Measured power, 7 vs 28 days, q 0.05: 5 or 10 percent of summaries turning unfaithful 1.00; one 10-a-day source turning unfaithful 0.86; coherence median -0.02 1.00; coverage one bucket down 1.00. No-change nights cross 4.6 to 4.9 percent of the time; 1.3 false stretches a month (0.2 at q 0.01). | 5.4, 5.6 |
| E | The replay flags the 2026-09-07 step from 2026-09-11, on copying, not on faithfulness: the median summary copied 60 percent more 4-grams and HHEM rose with it. The step is within-source (99 shared sources: -0.101 in the not-high share against -0.103 overall), so it is a pipeline change, not mix. | 5.3 |
| F | Composite: Benjamini-Hochberg over the members plus one positive-part composite row. Non-compensatory and calibrated; it adds 3 to 4 points of power on broad weak shifts and nothing elsewhere. Weights move little at this volume because each member is already well powered alone. | 4, 5.7 |
| G | Plan 36: this judge supplies the per-metric fleet alarms (one alarm per metric); plan 36 drops its fold and fit (rows 1, 2, 4, 5) and keeps the gate, G-Eval, the rejects ledger and the console. | 6 |
| H | Autocorrelation is the main calibration risk: at lag-1 0.3 a member's false rate at the single-row BH cut (p <= 0.0033) is 0.016, about 5 times nominal; an AR(1) factor from the baseline brings it to 0.006, about 2 times. Build it in. | 4.1, 5.4 |

## 1. The owner's critique

### 1.1 Verdict on the unit: the owner is right

| # | Reason | Evidence |
| --- | --- | --- |
| u1 | A reader meets summaries in the digest, not by site; one model, one prompt and one decode write every summary, so a summariser regression lands on every site at once | BRIEF (one production model at a time) |
| u2 | Per-site cells are too small to test | The largest source is 1.4 to 3.8 percent of a day (per-source cap 10 to 15 a day; effective number of sources 42 to 81 on days of 100 or more summaries). The 4 Oct review made 71 comparisons and skipped 241 (verified_facts #10) |
| u3 | A shared step hides under every site's threshold | The plan's own P16 evidence: a shared 0.02 step was caught 82 to 97 percent at all-sites level, 6 to 10 percent per site |
| u4 | Every per-site finding on record was mix or source shape, none a summariser regression | #1270 page-type mix; #675 Mongabay length and chrome; #970 japantimes copying 0.12 -> 0.41 (verified_facts #10) |
| u5 | The one summariser-side step on record is within-source and digest-wide | 2026-09-07: the 99 sources present the week before and after (95 percent of summaries) moved -0.101 in the not-high share; the digest moved -0.103 |
| u6 | The digest is cheap to judge well | Daily shares vary about as binomial sampling predicts; source mix explains SD 0.004 to 0.008 of a daily not-high share that moves with SD 0.021 to 0.033 (section 3.5) |

### 1.2 What a digest-level view misses, and who covers it

| Failure | Seen by digest-level summary metrics? | Covered today by | Verdict |
| --- | --- | --- | --- |
| Summariser regression (prompt, model, decode, runtime, chat template) | Yes, best case | This judge | Core job |
| Extraction rot on one source (redesign, chrome, cookie wall, teaser text) | No, at ANY unit: the summary is faithful to the garbage, HHEM stays high (evaluation.txt, "The problem being solved") | Nothing reliable: extraction_suspect is 0 on all 50 day records; drift.py's shorter_sources and scoring_chrome are deleted by row #1; feed-health counts failed or empty reads (rest after 5 strikes), not garbage text | GAP. Needs a source-health owner (Q1) |
| One source's summaries turn unfaithful (paywall stub, wrong language, broken markup) | Partly: the tail share rises by that source's share of the day | This judge, plus a per-source drill-down printed under a crossed member (a sentence, no test) | Power 0.86 for a 10-a-day source over a full week |
| A feed stops or thins | Not a quality failure | feed-health (rest after 5 strikes), item-health census | Out of scope |
| Mix shift (new long-form source, #1270-type page mix) | Raw statistics move; adjusted ones do not | This judge's mix note (raw vs adjusted, section 3.5) | Handled |
| Truncation by the cap | Not a summary failure | truncation_flagged; source_words_before_cap > source_words; hhem_delta | Out of scope |
| One source's copying shape (#970) | Digest moves by at most that source's share | Drill-down only | Accept |

### 1.3 Where the owner is wrong or incomplete

| # | Owner's words | Fact | Consequence |
| --- | --- | --- | --- |
| w1 | "summary quality faithfulness coherence, conciseness - the 4 standard metrics" | The design of record names four: Faithfulness (HHEM), Coverage (semantic_coverage, lexical), Coherence (MiniLM adjacent cosine), Fluency (G-Eval, not built) - SummEval's consistency, relevance, coherence, fluency. Conciseness is not among them. Conciseness is FineSurE's third dimension (faithfulness, completeness, conciseness; Song et al., ACL 2024), defined as the share of summary sentences that carry a key fact - not length. Compression "measures the article's length, not the summary's quality" at a fixed output budget (eval_row.py) | No eval column measures conciseness. Proxies until a key-fact member exists: summary length (two-sided, low weight) and self-repetition (Q6) |
| w2 | "we shouldn't care about within (intra?) domain fidelity" | True for this judge. False for the product: a source whose extraction breaks puts 10 garbage cards a day in front of readers, and no summary metric can see it | Keep a per-source extraction check, but elsewhere (Q1) |
| w3 | "judging based on article length is also stupid, that should be weighted and lower" | Right as a judged quantity. But length is HHEM's main confounder: a 3-window article scores 0.40 lower than the same article read whole (evaluation.txt) | Length becomes a covariate with weight 0 (section 2.3) |
| w4 | "focus on variance of the metrics" | Right that tails matter more than medians: the checker measured the median summary's faithfulness at 88-95 while the lower quarter swung 73-94 (checker.md). Wrong if read literally: HHEM's IQR and p25 correlate -0.98 (r4), and a narrowing distribution reads as change while harming nobody | Judge the harmful side of variance - the share past a line - and keep spread only where it is independent (coherence, paused) |

## 2. What matters: the judged quantities

### 2.1 Reader failures, ranked by harm x frequency

| Rank | Reader failure | Instrument | Size today (r4 means) |
| --- | --- | --- | --- |
| 1 | Invented or contradicted claim | hhem | 5.6 percent of summaries under 0.50; 12.7 percent under 0.80 |
| 2 | Wrong number | unsupported_numbers | 1.7 percent of published summaries carry one |
| 3 | Rumour stated as fact | hedge_dropped | 13.7 percent (band-reason share; inflated, section 5.3) |
| 4 | Missed what the article kept returning to | semantic_coverage | mean 0.51 |
| 5 | Copied instead of summarised (and inflates HHEM) | extractiveness, verbatim_run | median 0.13 of 4-grams copied |
| 6 | Disjointed summary | coherence | median 0.30 |
| 7 | Looped text | self_repetition | rare: daily maximum 0.01 to 0.06 |
| 8 | Too long or headline-only | summary_words | median 65 words |
| 9 | Disfluent text | G-Eval (not built) | unknown; FineSurE omits fluency because modern models are fluent |

### 2.2 The members (declared per P13; status at landing)

Day SD and lag-1 are r4 (16 days of 200 or more rows) unless marked; "*" marks a day-record stand-in for the
production statistic (band-reason shares for the column shares; quantiles for shares past a line).

| Id | Axis | Column | Daily statistic | Reader failure it signals | Reliability | Harm | Day SD (mean) | Lag-1 | Status | Axis weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| faith_below_050 | faithfulness | hhem | share under 0.50 (fixed line) | invented claims | the one instrument the design of record trusts to withhold; length-biased; rewards copying; 0 human labels | up | 0.0129 (0.056)* | -0.09 | active | 3, split 3 ways |
| faith_below_080 | faithfulness | hhem | share under 0.80 (fixed line) | doubtful summaries; sees mild unfaithfulness faith_below_050 cannot | same | up | 0.0142 (0.127)* | +0.28 (r2 +0.31, r3 +0.35) | active | |
| faith_median | faithfulness | hhem | median | level shift | same | down | 0.0024 (0.938) | -0.02 | active | |
| numbers_unsupported | numbers | unsupported_numbers | share with 1 or more | wrong figure | regex: misses spelled numbers, false hits on computed ones; selected on by the prompt loop (Goodhart risk) | up | 0.0058 (0.017)* | -0.04 | active | 3 |
| hedges_dropped | hedges | hedge_dropped | share true, stratified by article hedging (densities > 0) | rumour as fact | lexicon on the lead; base rate follows how much sources hedge; selected on by the prompt loop | up | 0.0192 (0.137)* | +0.47 | active | 2 |
| copy_median | copying | extractiveness | median | lifted, not summarised | deterministic 4-gram precision; moves with summary length and wire briefs | up | 0.0082 (0.132) | +0.27 | active | 1.5, split 2 ways |
| copy_runs | copying | verbatim_run | share over 0.50 (the brief-item copying line, brief_compression_ceiling) | a copied paragraph | deterministic; rare event | up | n/a (p75 stand-in 0.0053) | +0.15 | active | |
| coverage_mean | coverage | semantic_coverage | mean (21 buckets: the median moves in 0.05 jumps) | dropped the main point | lexical; abstraction reads as a miss; length-free (rank corr -0.09) | down | 0.0090 (0.510) | +0.13 | active | 1, split 2 ways |
| coverage_tail | coverage | semantic_coverage | share at or below the baseline's p10 bucket | omissions in the tail | same | up | p25 stand-in 0.0224 | +0.06 | active | |
| coherence_median | coherence | coherence | median | disjointed summary | MiniLM adjacent cosine; repetition reads as coherent; null for one sentence; encoder not stamped on the row | down | 0.0053 (0.305) | -0.17 | active | 0.5, split 2 ways |
| coherence_tail | coherence | coherence | share under the baseline's p10 | incoherent tail | same | up | p25 stand-in 0.0073 | -0.18 | active | |
| coherence_spread | coherence | coherence | IQR | inconsistent quality | partly independent of coherence_median/coherence_tail (r -0.40 with p25) | up | 0.0089 (0.131) | +0.22 | paused | 0 |
| repetition_loops | repetition | self_repetition | share over 0.05 (estimate: a wobble reads 0.021, a loop 0.391) | looped text | deterministic; base rate unknown from day records | up | unknown | - | paused until the replay sets its base rate | 1 |
| length_median | conciseness | summary_words | median, two-sided | too long or headline-only | exact; meaning moves with the length policy | either | 1.18 words (65.1) | -0.24 | active | 0.5 |
| fluency_mean | fluency | geval (plan 36 row 3) | mean of the daily sample | garbled text | self-judge as planned; about 30 a day | down | unknown | - | paused (not built) | 0 |
| withheld_share | gate | publish_decision (plan 36 row 3) | share withheld | thin digest (plan 36 D8) | exact | up | unknown | - | paused until the gate stamps | 0 |

Starting axis weights rank reader harm x instrument reliability: faithfulness 3, numbers 3, hedges 2, copying 1.5,
coverage 1, repetition 1, coherence 0.5, conciseness 0.5, fluency 0. They are a starting point for P17's scoring,
not a measurement.

### 2.3 Source length: a covariate, weight 0

Dropped as a judged member and kept as the stratifier for mix adjustment (section 3.5), because: it is a property
of the article, not the summary; the owner ruled it out; it is HHEM's main confounder (window slicing); at
digest level its daily movement is small (median SD 19.6 words in r4) and correlates with the faithfulness tail
weakly in r3 and r4 (|r| <= 0.35) though +0.64 in r2 (10 days) - so adjustment is a guard against a mix step, not a
noise filter; and as an extraction-rot signal it belongs per source in another instrument (Q1).

### 2.4 Recorded, never judged

| Column | Why not judged |
| --- | --- |
| compression | At a fixed output budget it measures the article's length, not the summary's quality (eval_row.py, metrics.py) |
| source_words, source_words_before_cap | Covariates (2.3) |
| evidential_density, speculative_density | Properties of the article; strata for hedges_dropped |
| hhem_full, hhem_delta | Equal to hhem on 6,959 of 6,966 rows (checker.md) |
| score_ms | Runtime cost, not quality |
| truncation_flagged | An extraction fact |
| extraction_suspect | 0 on all 50 day records; nothing to test |
| band, band_reason | Derived from hhem and the counterweights; the reason's precedence changed meaning on 2026-09-24 (5.3) |
| determinism_violation | Never set in production (B9) |

## 3. How it is measured

| Topic | Decision | Evidence |
| --- | --- | --- |
| Unit judged | The digest's scored summaries (eval rows, one per measurement), all sources together, over the recent window ending on the judged date | 1.1 |
| Series | Production model_id x each member's instrument key: hhem -> scorer@revision + weights + window geometry; counterweights and semantic_coverage -> METRICS_VERSION; coherence -> METRICS_VERSION + encoder ref (not on the row today); fluency -> judge model + rubric digest (not on the row). The bands= component of scorer_version is not an instrument | P14. Under the whole-scorer_version rule (G1.7), 2026-09-24's metrics-4 restarts HHEM's series although HHEM did not change: 13 nights untested |
| How keys are read | One function beside metrics.scorer_version() returns its spelled components; the judge never parses the string | metrics.py spells components "so a row still explains itself" |
| Windows | Recent 7 days, baseline the 28 days before it, whole weeks, same series; a member's series starts on its own first day (coverage and coherence on 09-24); long baseline 52 weeks for slow decline (row #14) | SE factor sqrt(1/7 + 1/28) = 0.42 vs 0.46 at 14 days; replay 5.3 |
| Minimums | A day counts if it has 100 or more eval rows; a member is tested with 4 or more recent and 7 or more baseline days; otherwise "too few days" | 5.5 |
| Day weights | w_d = n_d (scored rows) | Thin days behave as their size predicts (5.5) |
| Exchangeable unit | The day. The null re-deals whole days between the windows, the same re-deal for every member | Overdispersion 1.4 to 3.4 in r3 (item-level re-deals would be anti-conservative there); 0.5 to 1.25 in r2 and r4 (the day costs almost no power) |
| Autocorrelation | Each member's z is divided by sqrt((1 + r) / (1 - r)), r = the baseline's lag-1 clipped to [0, 0.8] | 5.4: at r 0.3 the uncorrected rate at the single-row BH cut (p <= 0.0033) is 0.0163 (0.0020 at r 0); corrected 0.0060 |
| Mix: length | Strata by HHEM window count on source_words (1: <= 900 words; 2: 901 to 1,650; 3+: over 1,650, from chunk 900 / overlap 150); recent statistic re-weighted to the baseline's stratum shares | 3-window articles score 0.40 lower (evaluation.txt) |
| Mix: sources | Share members: expected = sum over recent rows of the row's source baseline rate, shrunk to the digest rate with 10 pseudo-rows; adjusted share = baseline share + (observed - expected) / n | Source mix moves the expected daily not-high share by SD 0.004 to 0.008 (0.0065, 0.0078, 0.0043 in r2, r3, r4); 2026-08-27 added 31 sources carrying 17.8 percent of the next week |
| Raw vs adjusted | Judge adjusted; store raw beside it; raw crossing with adjusted quiet = a mix note, not a crossing | The old page_mix note, at digest level |
| Tails | Daily share past a line: fixed where the project already has one (hhem 0.50 and 0.80, verbatim_run 0.50), trailing elsewhere (the baseline's pooled p10 or p90, at-or-below a bucket for discrete coverage); the line is fixed for the night | Power 5.6: faith_below_050/faith_below_080 beat p25 and p50 on every unfaithfulness injection |
| Spread | Daily IQR, one-sided (wider is worse), only where independent of the tail: coherence (paused) | HHEM IQR vs p25: r -0.98 |
| Not used | Wasserstein, KS or energy distance on pooled items | Two-sided omnibus, overpowered at about 2,500 items a window, mis-calibrated once days share movement; not readable by a person |
| Labels on a crossing | The run records' named input values that differ between the windows (model, prompt, length policy, decode, scorer components) | The 09-07 cause is "not established" today; with this it is a lookup |

## 4. How it is judged: test, family, composite

### 4.1 Per member m, judged date t, series s

```
x_md   = statistic of member m over day d's rows (adjusted per 3.5)
Xbar_mS = sum_{d in S} n_d x_md / sum_{d in S} n_d                 S = R (recent) or B (baseline)
T_m    = h_m (Xbar_mR - Xbar_mB)      h_m = +1 higher is worse, -1 lower is worse; |.| when two-sided
re-deal: N = 20,000 random splits pi of the |R|+|B| days into |R| and |B|, the same pi for every member
z*_m,pi = (T*_m,pi - mean_pi T*_m) / sd_pi T*_m                    (the re-dealt nights)
z_m    = [(T_m - mean_pi T*_m) / sd_pi T*_m] / sqrt((1 + r_m) / (1 - r_m))
         r_m = lag-1 of member m's baseline days, clipped to [0, 0.8]; the factor divides the observed z only
p_m    = (1 + #{pi : z*_m,pi >= z_m}) / (N + 1)
```

### 4.2 The night's family and the decision

```
family F(t, s) = active members tested on t  +  the composite row
Benjamini-Hochberg at q = false_discovery_rate (F1.11, 0.05; 0.01 the lever):
  sort p ascending; k = max{ i : p_(i) <= i q / |F| }; rows ranked 1..k cross
verdict(t, s) = "moved"         if any row crosses
              = "quiet"         if tested and nothing crossed
              = "too few days"  if no member could be tested
              = "new series"    on a model or instrument change (P14; earlier-series rows outside the step)
```

Paused members, covariates and earlier-series rows are stored with p and no q. A crossed row prints its effect in
its own unit (e.g. "share under 0.50: 9.8 vs 5.6 percent"), q, the inputs that changed inside the window, and the
mix note.

### 4.3 The composite (one row in the family)

```
omega_m = W_axis(m) / (number of active members on axis(m))         W from config (P17)
S       = sum_m omega_m max(z_m, 0)          (two-sided members contribute |z_m|)
S*_pi   = sum_m omega_m max(z*_m,pi, 0)      same re-deals as the members
p_S     = (1 + #{pi : S*_pi >= S}) / (N + 1)
display = S and "nights in 1,000 this high with no change" = 1000 p_S
```

| Requirement | How it is met |
| --- | --- |
| Non-compensatory | Every member is its own row with its own threshold, so one collapse crosses alone; max(z, 0) means an improvement never offsets a harm (2026-09-07: HHEM up must not cancel copying up); weights act only inside S, so a mis-set weight cannot blind a member |
| Correlation | The joint re-deal keeps every day-level dependence between members, so p_S and every p_m are valid whatever the correlation; splitting an axis's weight among its members stops a duplicated statistic doubling its axis (HHEM IQR vs p25 r -0.98); the family's effective size is reported (participation ratio 6.8 of 15 in r4). BH holds under positive dependence; under arbitrary dependence the bound is q x 3.3 at 15 rows (Benjamini-Yekutieli); the simulated no-change rate shows no inflation (5.4) |
| Weights from config | W per axis in config/judges/summary-fidelity-judge.json; the replay scores candidate vectors on injected changes and re-dealt dates; a person commits (P17). Because every p comes from re-deals, a weight vector moves power between failure types and never the false-night rate (5.7) |
| New metrics | A declaration names column, statistic, harm, axis, line, adjust_by, instrument key; it lands paused (p, no q, omega 0); the replay adds its injection; the owner activates it and a person commits its axis weight; the axis split renormalises |
| Simplicity | numpy only; scipy's beta-binomial and negative binomial leave with rows #5 and #6 |

Measured value (5.7): the composite row changes the night's decision by 3 to 4 points of power on broad weak
shifts (every axis 0.5 to 0.75 day-SD worse) and by under 1 point elsewhere, at no false-rate cost. A signed
Stouffer row does the same but is compensatory (rejected). Weighted BH (p_m / normalised omega_m) is the
alternative that lets weights steer the decision: +10 points when wrong numbers double, -7 points on a
coordinated shift led by low-weight axes (Q3).

### 4.4 The design-of-record line "a veto chain, never a composite"

It governs the per-item publish gate and stays true there. This judge gates no item and takes no action (B2). Its
member rows are a veto chain at digest level - any one crossing is "moved" - and its composite is one more
calibrated row that never replaces a member, never averages HHEM with anything, and names its top contributors.
Both objections in plan 36 D4 ("dilutes HHEM", "erases which axis fired") are met. Amend the design-of-record
page with one sentence: the judge's composite is a monitor row, not a gate, and feeds no action.

## 5. Replay on the real history

### 5.1 What the record holds

| Date | Change | hhem p25 / p50 | extractiveness p50 | summary words p50 | faithfulness-reason share | Eval rows a day |
| --- | --- | --- | --- | --- | --- | --- |
| r2 08-27..09-06 | qwen3.5-9b | 0.810 / 0.919 | 0.108 | 76 | 0.218 | 334 to 627 |
| r3 09-07..09-23 | unknown pipeline change | 0.888 / 0.940 | 0.171 | 83 | 0.133 | 250 to 427 |
| r4 09-24..10-10 | metrics-4; shorter summaries | 0.885 / 0.938 | 0.132 | 65 | 0.127 | 306 to 480 |

Notes. The brief's "doubts about 130 -> 50 a day" is partly volume: planned items fell from about 650 to 400 a day
from 09-05; as a share the faithfulness reason fell 0.21 -> 0.15. Inside r3, the share under 0.50 dropped from
about 0.09 to about 0.04 on 09-15..09-18 and rose again from 09-20, while the shortest summary rose from about 25
to about 40 words - further movement the record cannot explain. 2026-08-21..08-24 carry no band reasons (the field
did not exist), so reason-based stand-ins start 08-25.

### 5.2 Day-to-day spread and lag-1 autocorrelation (days of 200 or more rows)

| Member | r2 SD | r2 lag-1 | r3 SD | r3 lag-1 | r4 SD | r4 lag-1 |
| --- | --- | --- | --- | --- | --- | --- |
| faith_below_050* | 0.0159 | +0.11 | 0.0261 | +0.28 | 0.0129 | -0.09 |
| faith_below_080* | 0.0143 | +0.31 | 0.0262 | +0.35 | 0.0142 | +0.28 |
| faith_median | 0.0034 | -0.15 | 0.0048 | +0.39 | 0.0024 | -0.02 |
| numbers_unsupported* | 0.0060 | -0.41 | 0.0105 | -0.11 | 0.0058 | -0.04 |
| hedges_dropped* | 0.0142 | -0.17 | 0.0228 | -0.26 | 0.0192 | +0.47 |
| copy_median | 0.0054 | -0.27 | 0.0131 | -0.11 | 0.0082 | +0.27 |
| copy_runs (p75 stand-in)* | 0.0064 | +0.22 | 0.0075 | +0.15 | 0.0053 | +0.15 |
| coverage_mean | - | - | - | - | 0.0090 | +0.13 |
| coherence_median | - | - | - | - | 0.0053 | -0.17 |
| length_median | 3.04 | +0.25 | 3.41 | +0.22 | 1.18 | -0.24 |

Overdispersion (observed day variance / binomial) for the band-reason shares: r2 0.49 to 1.25, r3 1.36 to 3.44,
r4 0.61 to 1.07. Lag-1 on 10 to 16 days has SE about 0.25; only faith_below_080 is consistently near +0.3.

### 5.3 Replay (judged 2026-09-09..10-10, 31 nights; series split at the model switch only)

12 members plus the composite, as available (coverage and coherence on their own days from 09-24), 20,000
re-deals a night, q 0.05, baseline cap 28 days. Runs of identical crossings:

| Nights | Crossed | Read as |
| --- | --- | --- |
| 09-09..09-10 | - | 3 of 7 recent days post-step |
| 09-11..09-23 | copy_median (z 3.1 to 4.2), copy_runs; length_median on 09-13..09-21 | the 09-07 step: copying up, summaries longer; faithfulness improved (one-sided, no crossing) |
| 09-24..09-25 | - | |
| 09-26..10-05 | hedges_dropped (z 2.9 to 4.3); length_median from 09-27; composite on 09-30 | the 09-24 change: summaries 83 -> 65 words, more dropped hedges (part is an artefact, below) |
| 10-06..10-08 | length_median | baseline still holds pre-09-24 days |
| 10-07..10-10 | coverage and coherence tested on their own series: quiet (max z 0.7) | |

| Configuration | Nights with a crossing | New stretches (by member) | First night on the 09-07 step |
| --- | --- | --- | --- |
| cap 28, q 0.05 | 25 of 31 | 8 (copy_median, copy_runs x2, length_median x3, hedges_dropped, composite) | 09-11 |
| cap 28, q 0.01 | 17 of 31 | 5 | 09-11 |
| cap 14, q 0.05 | 16 of 31 | 6, including faith_median median HHEM -0.004 on 09-30..10-01 | 09-11 |
| cap 14, q 0.01 | 15 of 31 | 5 | 09-11 |

Findings.
- Every crossing traces to one of two dated changes; no crossing is unexplained. The pipeline changed about every
  9 days (08-27, 09-07, about 09-15, 09-24), faster than the windows: the judge almost never sees a quiet baseline.
  That makes the input-change label (section 3) the most valuable thing on a crossed row.
- The 09-07 step is caught 4 nights after onset on copying. It is the persona's warning measured: HHEM's lower
  quartile rose 0.81 -> 0.89 because summaries copied more (median 0.11 -> 0.17). A faithfulness-only judge would
  have read an improvement.
- A 28-day baseline that spans two regimes hides a later decline: faith_median (0.942 in r3b, 0.938 in r4)
  crosses only with the 14-day cap, because on 09-30 the 28-day baseline still holds five r2 days at about 0.919.
- The hedges jump on 09-24 (reason share 0.10 -> 0.137) is confounded: until 09-24 an item that both missed the
  lead and dropped a hedge was named lead_missing; lead_missing stopped on 09-24. The judge must read the
  hedge_dropped column, never band reasons.
- Model switch (P14): no in-step comparison until the new series has 7 baseline days - 13 nights blind
  (08-27..09-08). The earlier-series row for 08-27..09-02 against qwen3-8b (4 days) reads: copying 0.088 -> 0.108
  (p 0.0035, the floor of an 11-day re-deal), summaries 102 -> 77 words (p 0.0035), HHEM p25 0.76 -> 0.80
  (better). The new model copied more and wrote 25 fewer words.
- Under per-column instrument keys, 09-24's METRICS_VERSION move restarts the counterweight series (copy_median,
  copy_runs, numbers_unsupported, hedges_dropped), so the 09-26 hedges crossing would be an earlier-series row
  outside the step; HHEM continues.

### 5.4 False crossings with no change

| Set-up | q 0.05 | q 0.01 |
| --- | --- | --- |
| Real stable nights in the replay (09-20..09-23, 10-07..10-10, baseline restarted at 09-07 and 09-24; 8 nights) | 0 of 8 | - |
| Days drawn from the stable stretches (centred), 9 members, 2,000 nights, cap 28 / 14 | 4.6 / 4.1 percent of nights | 1.1 / 0.9 percent |
| Days drawn from r4, 14 members + composite, 2,000 nights, cap 28 / 14 | 4.9 / 4.2 percent | 0.7 / 0.7 percent |
| Nightly judging of 40 no-change series of 60 nights (overlapping windows) | 1.2 nights and 1.3 new stretches per 30 nights | 0.21 and 0.21 |
| AR(1) days, one member, P(p <= 0.0033) (the single-row BH cut at 15 rows) | r 0: 0.0020; r 0.3: 0.0163; r 0.5: 0.0400 | corrected: 0.0032, 0.0060, 0.0063 |

Calibrated with independent days; autocorrelation is the residual risk, which is why 3.3 carries the AR(1) factor.

### 5.5 Low-volume days

Deviation from the stretch mean, in the regular days' SD [and in the day's own sampling SD]:

| Day (eval rows / published) | faith_below_050 | faith_below_080 | numbers_unsupported | hedges_dropped | copy_median | coverage_mean |
| --- | --- | --- | --- | --- | --- | --- |
| 08-28 (117 / 117) | -0.4 [-0.2] | +0.9 [+0.3] | -1.7 [-0.7] | +1.0 [+0.5] | -0.3 [-0.2] | - |
| 09-13 (255 / 75) | -0.1 [-0.1] | +0.0 [+0.0] | -0.5 [-0.4] | +2.5 [+1.2] | -1.2 [-1.5] | - |
| 09-14 (97 / 13) | +0.3 [+0.1] | -2.1 [-0.7] | -1.8 [-0.2] | +5.7 [+1.1] | +0.1 [+0.1] | - |
| 09-18 (138 / 138) | -1.0 [-1.5] | +0.5 [+0.4] | +0.3 [+0.2] | -0.9 [-0.9] | +1.1 [+0.8] | - |
| 10-05 (148 / 148) | -1.2 [-1.0] | +1.1 [+0.5] | -1.8 [-1.5] | +2.7 [+1.6] | +2.5 [+1.9] | +2.7 [+1.5] |

Thin days are noisy exactly as their size predicts (within 2 of their own sampling SD). Weighted by n they move a
window little; unweighted, 10-05 alone would move a week's coverage mean by 0.39 day-SD. Two of the brief's four
counts (13, 75) are published items; the eval ledger holds 97 and 255 rows those days. 09-14 falls under the
100-row floor.

### 5.6 Detection power (pooled stable days, cap 28, q 0.05; [change present on 4 of 7 recent days])

| Injected change | P(the night crosses) | Carried by |
| --- | --- | --- |
| 2 percent of summaries unfaithful (hhem drawn under 0.50) | 0.59 [0.21] | faith_below_050 0.56, faith_below_080 0.45 |
| 5 percent unfaithful | 1.00 [0.76] | faith_below_050 1.00, faith_below_080 1.00, p25 0.81, faith_median 0.77 |
| 10 percent unfaithful | 1.00 [1.00] | all faithfulness members |
| 5 percent mildly unfaithful (0.50 to 0.80) | 1.00 [0.54] | faith_below_080 only (faith_below_050 0.01) |
| One 10-a-day source fully unfaithful (2.8 percent of the day) | 0.86 [0.35] | faith_below_050 0.85 |
| Coherence -0.02 on every summary | 1.00 [0.84] | coherence_median 1.00, coherence_tail 1.00 |
| Coverage one bucket down on every summary | 1.00 [0.95] | coverage_mean |
| Coverage one bucket down on a quarter of summaries | 0.73 [0.22] | coverage_mean 0.71 |
| Extractiveness x 1.3 | 1.00 [0.92] | copy_median |
| Unsupported numbers doubled (1.7 -> 3.4 percent) | 0.71 [0.30] | numbers_unsupported |
| Dropped hedges +3 points | 0.60 [0.23] | hedges_dropped |
| Small coordinated shift (1.5 percent unfaithful, coherence -0.005, 10 percent lose a coverage bucket, copying x 1.05) | 0.86 [0.29] | spread over faith_below_050, coherence_median, copy_median; composite alone 0.23 |

At q 0.01 the marginal cases fall about 20 points (2 percent unfaithful 0.56 -> 0.32; one source 0.86 -> 0.65;
numbers doubled 0.70 -> 0.49; hedges +3 0.61 -> 0.39; a quarter-bucket of coverage 0.70 -> 0.45). Minimum
detectable shift at 80 percent (normal approximation, r4 SDs; estimate): about 1.5 day-SDs - faith_below_050
1.9 points, faith_below_080 2.1 points, faith_median 0.004, numbers_unsupported 0.9 points, hedges_dropped 2.9
points, copy_median 0.012, coverage_mean 0.013, coherence_median 0.008, length_median 1.9 words. r3's spread
doubles these.

### 5.7 Composite forms compared (r4 days, 14 members, 400 nights each)

| Scenario | Members only | + positive-part row (recommended) | Weighted BH | + signed Stouffer row |
| --- | --- | --- | --- | --- |
| No change | 0.052 | 0.050 | 0.055 | 0.050 |
| Coordinated small shift | 0.807 | 0.800 | 0.738 | 0.805 |
| Every axis 0.5 day-SD worse | 0.630 | 0.672 | 0.623 | 0.685 |
| Every axis 0.75 day-SD worse | 0.932 | 0.958 | 0.915 | 0.958 |
| 5 percent unfaithful | 1.000 | 1.000 | 1.000 | 1.000 |
| One source unfaithful | 0.973 | 0.965 | 0.965 | 0.965 |
| Unsupported numbers doubled | 0.810 | 0.802 | 0.912 | 0.805 |

SE about 0.02 per cell. Read: the composite is cheap insurance for broad degradation (a runtime or quantisation
regression touching every axis a little); it is not where detection comes from.

## 6. Plan 36 overlap

Recommendation: one alarm per metric, supplied by this judge. Plan 36's E1 already turned every adaptive floor into
a WATCH-only fleet-rate alarm with no per-item action; a judge member with a re-deal null and a false-discovery
step is that alarm, done properly. Two alarms per metric would disagree and double the reading.

| Plan 36 row | Recommendation | Why |
| --- | --- | --- |
| 1 Fit core | Drop (stays in plan 34) | Its second user was the watch floor |
| 2 MetricScoreDistribution, FittedMetricBand, knob block | Drop both contracts; keep only a per-metric action knob (block or watch) for the gate | No reader left once the gate reads absolute lines |
| 3 EvalRow geval, publish_decision, withheld_reason | Keep | The gate's stamp; members fluency_mean and withheld_share read them |
| 4 Fold | Drop | The judge reads 35 named days through ledger.load_days, a fixed-size read (Guardrail #12) |
| 5 Fit and seed | Drop; move its G14 doc reconciliation to the row 7 commit | The judge's baseline is committed history from night one |
| 6 G-Eval fluency | Keep, change: pin the judge model by file digest, independent of the production summariser, and stamp it on the row | A self-judge restarts its series at every model change (P14) and drifts with the model it judges |
| 7 Veto-chain gate, record-only | Keep; reads absolute lines only (HHEM 0.50, unsupported number); depends on row 3 alone | E1 left no adaptive per-item action |
| 8 Flip the flag | Keep | Unchanged; E5's "about 11 percent withheld" needs re-measuring: the share under 0.50 is about 5.6 percent in r4 (11.7 in r2) |
| 9 Console bands | Change: draw the judge's members with their baselines and crossings, plus the withhold panel | No fitted floors exist |
| 10 Measure a G-Eval call | Keep | |
| 11 Coherence placement | Reconcile first: evaluation.txt (2026-10-10) says coherence runs in the work shard inside to_eval_row (Carmack); plan 36 0e H5 says assemble | The two pages disagree |
| 12 Rejects ledger and corpus fence | Keep | |
| 13 Plan-34 gaps | Keep | |

Good elements taken from the fold-fit loop: the harm direction (low tail is bad); record-only first (paused
members); gates on days and samples (min_day_rows, min days); a baseline seeded from committed history; held
reasons (not-judged outcomes); the instrument sub-identity key (E2 -> per-column keys). Left behind: damping,
clamping and step caps (nothing acts), the rolling histogram (the 35-day read is already bounded), the settled
cadence (the night costs seconds), and a moving p05 floor (replaced by a trailing p10 line recomputed nightly).

## 7. The current judge plan: go, stay, change

| Id | Verdict | Change |
| --- | --- | --- |
| A1 | Change | Why: judge summary quality over the digest; #1270 becomes the history of why the site unit failed |
| A2 | Change | Scope: settings, ledger, members and statistics, day re-deal test, mix adjustment, family and composite, switch, panel, long baseline |
| A3 to A5 | Stay | |
| A6 | Change | Row order follows the new rows |
| B1, B2, B3, B5 to B10 | Stay | |
| B4 | Change | Article count leaves the judge; feed-health and item-health own it |
| B11 | Change | Per-column keys come from scorer_version's components (no eval-row change); stamps are still owed for coherence's encoder and G-Eval's judge (Level 5) |
| B12 (new) | Add | Per-source extraction health is out; gap stated; brought in by Q1 |
| B13 (new) | Add | Key-fact conciseness and completeness (an LLM judge, FineSurE-style) is out; enters later as a paused member |
| C1 to C5, C7 to C10 | Stay | |
| C6 | Change | The fixture becomes a digest-level mix shift (length strata and source composition move, nothing moves within a stratum); an adjusted member must not cross |
| Row #1 | Stay | |
| Row #2 | Change | Settings file stays; site.py, F1.9 and F1.10 go |
| Row #3 | Change | Contract without "Site" in its name; ledger drift-evals (owner); key without site and page_type; new fields below |
| Row #4 | Change | Members with statistic, harm, axis, line, adjust_by, instrument key; one test module (day re-deal); comparisons trailing, long_baseline, combined; page_mix note -> mix note |
| Row #5 | Go | Count kind and article_count (B4, B12) |
| Row #6 | Go | unusually_short and page_furniture: extraction health; extraction_suspect is 0 on all 50 day records |
| Row #7 | Change | "Statistics": tail shares, medians, means, spread; the members of section 2.2; Wasserstein per site goes |
| Row #8 | Change | Step stays; replay gains the injection library of 5.6, the whole-day null, the AR(1) check and weight scoring (P17) |
| Row #9 | Stay | The scipy extra can go (numpy suffices) |
| Rows #10, #11 | Stay collapsed | |
| Row #12 | Change | Panel lists members by axis with effects in their own units; no site column; a per-source drill-down sentence under a crossed member |
| Row #13 | Change | Becomes "Mix adjustment and the composite row"; all-sites is now the only comparison and moves into rows #4 and #7 |
| Row #14 | Stay, widen | From article_length (gone) to faith_below_050, faith_below_080, numbers_unsupported, hedges_dropped, coverage_mean, coherence_median |
| F1.1, F1.2, F1.4, F1.11, F1.12, F1.14, F1.15 | Stay | |
| F1.3 | Change | min_articles -> min_day_rows 100, min_recent_days 4, min_baseline_days 7 |
| F1.5 | Go | Replaced by trailing_line_quantile 0.10 |
| F1.6 to F1.8 | Change | Reshuffles -> whole-day re-deals (20,000 a night) |
| F1.9, F1.10 | Go | Site identity |
| F1.13 | Change | Member fields |
| New settings | Add | axis_weights; fixed lines (hhem 0.50 and 0.80, verbatim_run 0.50, self_repetition 0.05); length strata edges; source shrinkage 10; lag-1 clip 0.8 |
| F2.1, F2.2, F2.6 | Stay | |
| F2.3 to F2.5 | Go | Site keys |
| F3.1, F3.2 | Stay | |
| F3.3, F3.4 | Go | |
| H1.1 to H1.4 | Go | article_count, unusually_short, page_furniture; article_length becomes a covariate |
| H1.5, H1.6 | Change | Digest-level members copy_median, copy_runs and faith_below_050, faith_below_080, faith_median, keyed per column |
| H1.7 | Change | mix note |
| H1.8 | Stay | |
| H1.9 | Change | Composite as 4.3 |
| H1 new rows | Add | numbers_unsupported, hedges_dropped, coverage_mean, coverage_tail, coherence_median, coherence_tail, coherence_spread, repetition_loops, length_median, fluency_mean, withheld_share |
| H2.1, H2.2, H2.4 to H2.6 | Stay | H2.4 reads "earlier series" |
| H2.3 | Change | too_few_days |
| H3.7, H3.8 | Go | site, page_type |
| H3.10 | Change | instrument_key per member |
| H3.11 | Change | Days and rows per side |
| H3.13 | Change | Effect = T_m in the member's unit |
| H3.17 | Change | Settings in force: min_day_rows, lines, q |
| H3.18 | Change | Re-deals |
| H3.20 | Change | statistic instead of test_kind |
| H3.23 | Change | trailing, long_baseline, combined |
| H3 new | Add | raw_value, adjusted (bool), z, lag1, inputs_changed |
| Other H3 | Stay | |
| H4.1 | Change | Ledger drift-evals (owner; site-drift-evals disapproved) |
| H4.5 | Change | Key: run_id, date, member, comparison, model_id, instrument_key |
| Other H4, H5 | Stay | |
| G1.1, G1.4 to G1.6, G1.8, G1.9 | Stay | |
| G1.2 | Change | Statistics plus one day re-deal test |
| G1.3 | Change | Refusals gain statistic, line, axis and instrument-key checks; page-type ones go |
| G1.7 | Change | Per-column keys from scorer_version's components |
| G2 | Stay | |
| I1, I2, J1, J2 | Go | With rows #5 and #6 |
| K1.1 to K1.4, K2 | Go | Wasserstein and page types |
| K1.5 | Stay | OS entropy, no seed; moves to the test module |
| L1.1 | Change | Day re-deal |
| L1.2 | Stay | |
| L1.3 | Change | Minimum days |
| L2 | Stay | History |
| M1, M2 | Stay | |
| N1, N2 | Stay | |
| T1.1, T1.2, T2 | Stay | |
| T1.3 | Change | Composite listed only on a night no member crossed |
| U1.1 | Change | Whole-day re-deal is now every member's null |
| U1.2 to U1.6 | Change | Composite as 4.3, digest-level |
| U2.1, U2.2 | Stay | |
| V1, V2 | Stay | Widened to members |
| P1 | Change | Amend: ledger drift-evals, no site key |
| P2, P3, P12 | Moot | Rows #5 and #6 go |
| P4 | Change | Day re-deals |
| P5, P6, P8 to P10 | Stay | |
| P7 | Change | scipy no longer needed |
| P11 | Moot except H4.9 (stretches) | |
| P13 | Change | Member fields |
| P14 | Change | Per-column instrument keys |
| P15 | Change | Digest-level composite |
| P16 | Change | All-sites becomes the only comparison; long baseline widens |
| P17 to P19 | Stay | |
| R | Stay | History |
| S2 | Change | Ledger name |
| S3 | Go | Wasserstein |
| S4 | Change | 20 articles -> 100 rows a day |
| S5, S6 | Stay | |

## 8. Open questions for the owner

| Q | Question | A | B | C | Recommended |
| --- | --- | --- | --- | --- | --- |
| Q1 | Who owns per-source extraction health once row #1 deletes drift.py? | A source-health check in feed-health/item-health, its own plan: per-source length, short-text share, a chrome detector that actually fires | A second family inside this judge, its own ledger | Accept the gap | A |
| Q2 | Unit of judgment | Digest, per production series and per-column instrument key | Digest plus a per-source "concentration" row (one row per metric) | Per site (disapproved) | A |
| Q3 | How weights decide | BH over members plus the positive-part composite row; weights live in the composite | Weighted BH: weights steer each member's threshold | Members only, no weights | A |
| Q4 | Series splits | Model and instrument changes split (P14); prompt and config changes do not, and a crossing names the inputs that changed | Every declared input change splits | Only scorer changes split | A |
| Q5 | Instrument keys | Read from scorer_version's components through one function; add stamps for coherence's encoder and G-Eval's judge (Level 5) | Whole scorer_version (13 blind nights on any band or metrics move) | Full per-column stamps on the eval row now (B11) | A |
| Q6 | Conciseness | Not judged until a key-fact member exists (lands paused); meanwhile length_median (two-sided, weight 0.5) and repetition_loops | Treat compression as conciseness (it measures article length) | Drop conciseness | A |
| Q7 | Fluency judge | Pinned judge model, independent of the summariser, paused at weight 0 | The summariser judges itself (plan 36 as written) | Do not build | A |
| Q8 | Plan 36 | The judge supplies the per-metric alarms; plan 36 drops rows 1, 2, 4, 5 and keeps the rest (section 6) | Both build alarms | Plan 36 builds them; the judge reads FittedMetricBand | A |
| Q9 | Baseline | 28 days | 14 days (sees a decline inside a regime sooner; z about 9 percent smaller) | Expanding | A |
| Q10 | False-discovery rate | 0.05 with the AR(1) factor; 0.01 if the first month shows over 2 false stretches | 0.01 now (0.2 false stretches a month; marginal power -20 points) | 0.10 | A |
| Q11 | Mix | Judge adjusted (length strata, source standardisation), store raw, note disagreements | Judge raw only | Judge both (doubles the family) | A |
| Q12 | Accepting a change | Later: a person's mark rebases one member's baseline at a date (a row in a marks ledger, B2's path) | Never; the trailing window absorbs it in 5 weeks | Automatic rebase on any input change | A, after the first month |

## 9. Limits

- Item-level rows were not readable; member statistics past a line used day-record stand-ins (band-reason shares,
  quantiles). Production reads eval-row columns, whose spreads will differ.
- Simulating items from five quantiles flattens densities: within-day sampling variance came out up to 2 to 4
  times the observed day-to-day variance for upper quantiles, so power for quantile members is conservative.
- 50 days, four regimes: r4's 16 regular days are the only stretch carrying coverage and coherence; lag-1
  estimates carry SE about 0.25.
- The 09-07 cause and the 09-15 movement are not established here; the run records would establish them.
- repetition_loops, copy_runs and fluency_mean have no measured base rate yet.

## 10. What the literature pass can change

The registry (P13) separates what is measured from how it is tested, so a new metric is a declaration that lands
paused. Candidates the survey may bring - key-fact completeness and conciseness, finer-grained or LLM-judged
faithfulness, attribution - enter as members of an existing or new axis with their own instrument key; nothing in
sections 3 or 4 changes. What the survey cannot change: the unit (the digest), the null (whole days), and the rule
that one member's collapse is never averaged away.

## Second pass: reconciled with the literature survey (2026-10-11)

Read with research_summary_metrics.md (76 sources). New evidence: the real 50-day series replayed under three
tests, and simulations of calibration and detection (OS entropy, no seed; one shared vCPU; numpy 2.5). Code and raw
outputs: hardlook/andre_hardlook_code/ (second-pass files listed in its README). Stand-ins as in the first pass:
day records carry no per-item rows, so the faithfulness index ran on mean HHEM (production: mean of logits), the
copying line on verbatim_run p75, and the rates on band-reason counts.

### SP0. Answer first

| # | Finding | Where |
| --- | --- | --- |
| a | The survey changes WHAT is judged more than HOW. Judged quality: faithfulness (an index and two gate rates), wrong numbers, dropped hedges, loops, headline-only summaries. Copying and length become monitored behaviour, coverage and coherence diagnostics, self-judged fluency is dropped. Completeness and conciseness cannot be judged from today's columns. | SP2 |
| b | Test: keep the whole-day re-deal null and take the survey's EWMA as recency weights inside the 7-day window (lambda 0.15). Reject control limits taken from a reference window alone: in simulation they crossed 4.5 to 53 times their nominal rate (references of 56 down to 7 days); on the real series they crossed on 7 of the 8 nights where both re-deal tests found nothing. | SP4 |
| c | Decision: every member keeps its own row; two calibrated combined rows beside them - quality_worse (positive parts, quality members) and something_changed (T2 over quality and behaviour); Benjamini-Hochberg over the night. Reading levels watch / drift / evaluator check; nothing acts. | SP5 |
| d | Real replay: the 2026-09-07 step reads watch (copying up) from 09-09, two nights before the first pass's first crossing, and drift (something changed) from 09-12; quality_worse never crosses in 50 days (no faithfulness decline on record); 0 of 8 stable nights cross. No-change simulation: 2.4 percent of nights, 0.10 false drift events a month (q 0.05). | SP6 |
| e | Four instrument changes outside the judge, each an owner decision with a cost: sentence-level faithfulness, entity and date checks, a second checker, a sampled key-fact judge in place of plan 36's self-judged fluency. | SP3 |
| f | Approved items: P13 and P15 amended, P7 withdrawn, P14, P16, P17, P18 and P4 kept (P17 sharpened). | SP7 |
| g | Two corrections to the survey: bootstrapping reference days does not cure the estimated-limits problem it cites (Jensen 2006); and "GPT-4-class" holds for MiniCheck and FactCG on LLM-AggreFact, not for AlignScore (70.4), only vendor-reported for HHEM, and contradicted at summary level by UniSumEval. | SP1 |

### SP1. The survey's findings, checked against its sources

| # | Finding (orientation) | What the cited sources support | Verdict | Use here |
| --- | --- | --- | --- | --- |
| s1 | Faithfulness, completeness, conciseness essential; fluency near ceiling; coherence secondary for short summaries | FineSurE, UniSumEval, SEAHORSE; FineSurE omits fluency; BooookScore makes coherence primary only at book length | Holds (HIGH) | SP2 |
| s2 | Adjacent-sentence cosine and top-20-word coverage unvalidated | Steen & Markert 2022 (no reliable automatic coherence measure); no paper validates a top-k word-recall proxy (the survey's inference) | Holds | Both become diagnostics |
| s3 | Self-judged fluency carries every documented judge bias | Zheng 2023; Panickssery 2024 (self-preference, measured on news summaries); Liu-Moosavi-Lin 2024; Stureborg 2024 (preprint); Shen 2023 | Holds | Drop plan 36 row 6 (I5) |
| s4 | Small NLI checkers reach about GPT-4-class balanced accuracy on LLM-AggreFact | MiniCheck-FT5 74.7 to 75.0 and FactCG 75.6 against GPT-4 75.3; AlignScore 70.4; HHEM 76.6 is vendor-reported, on AggreFact-SOTA; UniSumEval: checkers 0.18 to 0.24 summary-level correlation on LLM news summaries, a GPT-4-turbo judge 0.65 | Partly (MODERATE) | HHEM stays the always-on instrument; a second checker buys agreement (I3) |
| s5 | "Only when each summary sentence is scored against its best window" | Wan 2025 (long-form: max over chunks per sentence, then mean); claim-level benchmark protocols. "Only when" overstates: nothing shows the whole-summary score failing on one-window articles (91 of the 117 pairs measured 2026-08-29, evaluation.txt). Our own evidence supports the mechanism on multi-window articles: a 2-window article scores 0.22 and a 3-window article 0.40 below the same article read whole | Mechanism holds for multi-window articles | I1, after a one-day measurement |
| s6 | Entity, number and date checks cheap; a second checker gives agreement; completeness and conciseness need a sampled LLM judge, unproven at 9B | FRANK; Zhao 2020; Nan 2021; FineSurE: Phi-2 at chance (48.1), 27B to 70B strong | Holds (LOW at 9B) | I2, I3, I4 |
| s7 | Length, page type, source are covariates; copying, compression, length are behaviour, never adjusted for | Survey 7.3; Steiner 2000 (risk adjustment) | Holds; the first pass already did this | SP2, SP5 |
| s8 | 09-07 matches "faithfulness rewards copying" | Ladhak 2022; Dreyer 2023 (factuality falls as abstractiveness rises, at a system-dependent rate); UniSumEval finds no such relation for proprietary LLMs | Holds; and the step is within-source (first pass, u5) | SP6 |
| s9 | Charted gate rates; correlation-aware composite C = sum w z / sqrt(w'Rw), w prop. to R^-1 delta, EWMA-smoothed; MEWMA/Hotelling omnibus; between-day spread; lagged reference -63..-8; limits by bootstrapping days; n weights; watch / drift / evaluator check | Lucas & Saccucci 1990; Lowry 1992; Steiner 2000; Jensen 2006 (estimated limits mislead); Alwan & Roberts 1988 | Adapted | Adopted: gate rates as members, between-day spread, n weights, recency weights, an omnibus row, reading levels, R^-1 delta as a starting point for weights. Rejected: reference-only limits, a 56-day reference, a signed composite (SP4, SP5) |

### SP2. The judged set, revised

Day SD from r4 (17 days of 100 or more rows; the same days the simulations draw), lag-1 pooled within stretches; "*" a
day-record stand-in. Weights start from reader harm
(faithfulness 3 split three ways, numbers 3, hedges 2) and are re-set by the replay under P17.

| Member | Role | Today's column and daily statistic | Adjusted for | Worse when | Day SD (r4) | lag-1 setting | Status | combine_weight | Later instrument |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| faith_index | quality | mean of logit(clip(hhem, 0.001, 0.999)) | length band, source | lower | 0.0100 (mean hhem*) | 0.05 | active | 1 | sentence-level mean (I1) |
| faith_below_050 | quality | share of hhem < 0.50 (plan 36's block line) | length band, source | higher | 0.0131* | 0 | active | 1 | sentence minimum (I1) |
| faith_below_080 | quality | share of hhem < 0.80 | length band, source | higher | 0.0142* | 0.28 | active | 1 | sentences below 0.80 (I1) |
| numbers_unsupported | quality | share with unsupported_numbers >= 1 | source | higher | 0.0062* | 0 | active | 3 | with entities and dates (I2) |
| hedges_dropped | quality | share of hedge_dropped | source, article hedging present | higher | 0.0226* | 0.10 | active | 2 | - |
| repetition_loops | quality | share of self_repetition > 0.05 | none | higher | unknown | 0 | paused (base rate first) | 0 | - |
| length_short | quality | share of summary_words < 25 | none | higher | unknown | 0 | paused (base rate first) | 0 | - |
| copy_index | behaviour | mean extractiveness | never | higher | 0.0072 | 0 | active | - (in T2) | - |
| copy_ceiling | behaviour | share of verbatim_run > 0.50 | never | higher | 0.0060 (p75*) | 0.12 | active | - (in T2) | - |
| length_median | behaviour | median summary_words, two-sided | never | either | 1.24 words | 0.05 | active | - (in T2) | - |
| scored_nulls | evaluator | share of rows missing hhem, coherence or semantic_coverage | none | higher | unknown | 0 | active | - | checker disagreement (I3), judge parse rate (I4) |
| coverage_mean, coverage_tail | diagnostic | semantic_coverage mean; share at or below the baseline's p10 bucket | - | lower / higher | 0.0105 (mean) | - | stored with p, outside the step | - | key-fact completeness (I4) |
| coherence_median, coherence_tail, coherence_spread | diagnostic | coherence median; share under the baseline's p10; IQR | - | - | 0.0054 (median) | - | stored with p, outside the step | - | - |
| input mix | diagnostic | length-band shares, source composition, extraction_suspect rate | - | - | - | - | stored | - | a detector that fires (source health, first-pass Q1) |

Covariates, never judged: length band (HHEM window count from source_words), source_id (item-health join on
url_key), article hedging present (evidential or speculative density above 0). Rows flagged extraction_suspect are
left out of quality members. Dropped: compression, hhem_full, hhem_delta, score_ms, band, band_reason,
determinism_violation, and fluency as plan 36 specifies it.

Against the first pass: faith_median becomes faith_index (the survey's mean-of-logits index, tail-sensitive);
copy_median, copy_runs and length_median become behaviour; coverage and coherence become diagnostics; two paused
gates arrive (loops, headline-only).

### SP3. What the first version can do, and the instrument changes it needs elsewhere

First version, today's columns only: every active row of SP2, the two combined rows, the mix adjustment, the
diagnostics. It cannot judge completeness or conciseness, cannot see entity or date errors, cannot separate a
scorer fault from a summary fault, and judges faithfulness on a score that marks down multi-window articles (the
length-band adjustment compares like with like until I1 lands).

| Id | Change | Where | What it buys | Cost | Recommended |
| --- | --- | --- | --- | --- | --- |
| I1 | Sentence-level faithfulness: each summary sentence against every window, best window per sentence; store the mean, the minimum, sentences under 0.50 and 0.80, and the winning window per sentence | eval stage (hhem.py, score.py), EvalRow | removes the multi-window mark-down; a position profile, a free completeness proxy | about 3 sentences, so about 3 times the HHEM pairs: today 12.5 scorer-minutes a day (r4 median; 1.1 s median and 2.0 s mean an item), so about 35 to 40 minutes (estimate; Carmack measures); Level 5 columns; new faithfulness slugs and series (P14); plan 36's 0.50 block line must be re-cut on the new score | Approve, after a one-day measurement |
| I2 | Entity and date checks: capitalised name runs and dates in the summary absent from the full article | metrics.py, EvalRow | FRANK's entity and circumstance errors, unwatched today | milliseconds; Level 5 (two columns); METRICS_VERSION 5 restarts the counterweight series; lexical, so no new dependency | Approve, with I1 in one eval-row change |
| I3 | Second checker (FactCG-DeBERTa-v3-L, 0.4B, or MiniCheck-Flan-T5-L, 0.77B) on I1's sentence-window pairs | same day, where the article exists | an agreement signal for the evaluator check, and an ensemble | several times HHEM per pair (estimate); 1 to 3 GB more RAM beside the summariser and HHEM; a new dependency and weights (C2); licences unverified | Defer until I1; then a 100-a-day stratified trial |
| I4 | Sampled key-fact judge (FineSurE protocol: key facts, completeness, conciseness), 30 to 50 a day stratified by length, one attribute per prompt, not the summariser, parse rate logged | needs the article: same day in the digest job, or a persisted sample for the council (a CLAUDE.md 0a carve-out, like plan 36 J3) | the only route to completeness and conciseness | a second 7B-9B model (about 5 GB) or the summariser with self-preference; about 40 to 90 s an item at plan 36's 4 tokens a second (estimate): 20 to 75 runner-minutes a day | Pilot first: injected omissions on 100 committed pairs; build only if it catches them |
| I5 | Drop plan 36 row 6 (self-judged fluency) and row 10 (its cost measurement) | plan 36 | removes an instrument with every documented judge bias on a near-ceiling dimension | none | Approve |
| I6 | Stamps for coherence's encoder and for any judge model, on the rows they score | EvalRow, judge ledgers | P14 for those members | Level 5 | Approve, inside I1's change |

Order: I5 now; I1, I2 and I6 as one eval-row change (one series restart, not three); the I4 pilot; I3 after I1.

### SP4. Which test: the evidence, and the pick

Three tests on the same members. W: flat 7-day mean against the 28 days before it, whole days re-dealt (first
pass). E: the survey's chart - EWMA of daily z against a lagged reference (gap 7, up to 56 days), null from
bootstrapping reference days. R: the 7-day mean with recency weights lambda (1 - lambda)^age, lambda 0.15, against
the 28 days before it, whole days re-dealt (the pick).

| Evidence | W | E | R |
| --- | --- | --- | --- |
| False rate at p <= 0.0033 (q 0.05 over 15 rows, the strictest cut), Gaussian independent days, reference 7 / 14 / 28 / 56 days; 1000 series a cell, simulation error about 0.002 | 0.0000 / 0.0010 / 0.0040 / 0.0030 | 0.176 / 0.062 / 0.019 / 0.015 | 0.0030 / 0.0010 / 0.0050 / 0.0050 |
| Same at p <= 0.05 | 0.043 to 0.062 | 0.089 to 0.250 | 0.043 to 0.062 |
| Same, lag-1 0.3, at p <= 0.0033 (before the rho widening) | 0.012 to 0.023 | 0.031 to 0.216 | 0.017 to 0.024 |
| Real stable nights (09-20..09-23, 10-07..10-10; 09-07 and 09-24 declared as new series) | 0 of 8 | 7 of 8 (start-up reference 7 days); 3 of 4 charted (14 days) | 0 of 8 |
| Of those, r4 nights 10-07..10-10 only (no change on record) | 0 of 4 | 3 of 4 (7 days); 3 of 3 charted (14 days) | 0 of 4 |
| Real r2 nights before the step (09-03..09-06), self-started | not testable | 4 of 4 crossed | not testable |
| 2026-09-07 step, first crossing | 09-11 | 09-10, its first night with a 7-day lagged reference | 09-09 |
| Simulated 2 SD step: crossed by night 3 / 5 | 0.13 / 0.53 | 0.62 / 0.89, at 4.5 to 53 times the false rate | 0.30 / 0.72 |
| Simulated 4 SD step: by night 2 / 3 | 0.07 / 0.40 | 0.89 / 0.99 | 0.38 / 0.84 |
| 2 percent unfaithful, change on 7 / 4 of 7 recent days | 0.77 / 0.29 | - | 0.72 / 0.43 |
| One source unfaithful, 7 / 4 of 7 | 0.97 / 0.41 | - | 0.95 / 0.64 |
| Numbers doubled, 7 / 4 of 7 | 0.89 / 0.44 | - | 0.74 / 0.60 |
| Dropped hedges +3 points, 7 / 4 of 7 | 0.38 / 0.10 | - | 0.29 / 0.16 |
| Low-volume days | n weights | limits widened by n | n weights |

Pick R. It holds its false rate under exchangeable days at every reference length (within simulation error), which
matters because this pipeline's homogeneous stretches last 5 to 17 days; it recovers part of the EWMA's speed (2 SD
step by night 3: 0.30, against W 0.13 and E 0.62; a change 4 days old: +6 to +23 points over W); it costs 2 to 15
points once a change fills the whole window; it keeps P1's per-night p, q and the false-discovery family. Some of
E's real crossings on 09-20..09-23 may be r3's internal movement near 09-15, which R and W did not call; on r4,
where nothing is on record, E crossed 3 of 4 nights. E's speed is its miscalibration: limits estimated from a short reference are too narrow,
and bootstrapping that same reference cannot widen them - the survey's own Jensen 2006 warning. Repairing E means
re-estimating the limits inside every draw, which is what a whole-day re-deal already does.

Other monitoring advice, decided on the same evidence:

| Advice | Decision | Evidence |
| --- | --- | --- |
| 56-day lagged reference (-63..-8) | 28 days, range 14 to 56 | The pipeline changed about every 9 days (08-27, 09-07, about 09-15, 09-24); a 56-day reference would span every segment on record (five in 50 days), so its mean describes no regime. Slow drift is the 52-week long baseline's job (P16, row #14) |
| CUSUM on gate rates | Not in v1 | One test kind is enough; CUSUM needs a designed shift per member; it can enter later as a kind (P13) |
| Lag-1 estimated nightly | A per-member setting the replay proposes and a person commits | A step inside the baseline pushed the nightly estimate to its clip and ended the 09-07 stretch on 09-15 instead of 09-23; pooled within-stretch lag-1 is 0.28 for faith_below_080 and at most 0.12 on the other judged members |
| Weekday covariate | Not needed now | Weekday means of every member are within noise: F 0.35 to 1.85 on 6 and 36 df, against a 5 percent cut of 2.36 |
| Cauchy combination | Not needed | BH holds under positive dependence, and each combined row carries its own re-deal p |

### SP5. The rule, as a builder implements it

```
Per row i on day d of series s (model_id x the member's instrument key, P14):
  y_mi = member m's per-row value:
         logit(clip(hhem_i, c, 1-c)) | 1[hhem_i < line] | 1[unsupported_numbers_i >= 1] | 1[hedge_dropped_i]
         | 1[self_repetition_i > line] | 1[summary_words_i < line] | extractiveness_i | 1[verbatim_run_i > line]
  rows flagged extraction_suspect are left out of quality members
Expected value, quality members only (fitted on the baseline days B; behaviour is never adjusted):
  mu_m(b)   = mean of y over B rows in length band b
  u_m(src)  = sum over B rows of src of (y - mu_m(band)) / (rows of src in B + k)        k = source_shrinkage_rows
  e_mi      = mu_m(band_i) + u_m(source_i)        (hedges_dropped: bands are "article hedging present / absent")
  r_mi      = y_mi - e_mi;      behaviour: r_mi = y_mi
Daily value: x_md = mean over day d of r_mi (median of y for length_median); n_d = rows of day d; days with
  n_d < min_day_rows are left out and stored as thin
Windows: R = the recent_days ending t, B = the baseline_days before R, same series
  a_d = lambda (1 - lambda)^(t - d) on R
  T_m = h_m [ sum_R a_d n_d x_md / sum_R a_d n_d  -  sum_B n_d x_md / sum_B n_d ]     h_m = +1 / -1; |.| two-sided
Null: N whole-day reshuffles pi (N set by P4's stop and cap) of R u B into |R| recent slots (each slot keeps its a)
  and |B| baseline days;
  the same pi for every member and both combined rows
  z*_m,pi = (T*_m,pi - mean T*_m) / sd T*_m
  z_m     = [(T_m - mean T*_m) / sd T*_m] / sqrt((1 + rho_m) / (1 - rho_m))          rho_m from the declaration
  p_m     = (1 + #{pi : z*_m,pi >= z_m}) / (N + 1)
Combined rows:
  quality_worse:     S = sum over active quality members of omega_m max(z_m, 0);  S* the same on z*
                     p_S = (1 + #{S* >= S}) / (N + 1)
  something_changed: V = covariance of z* over active quality and behaviour members;  T2 = z' V^+ z
                     T2* = z*' V^+ z*;  p_T2 = (1 + #{T2* >= T2}) / (N + 1)
Decision, one family per (run_id, date, series):
  F = active quality, behaviour and evaluator members + quality_worse + something_changed
  Benjamini-Hochberg at q = false_discovery_rate: sort p; k = max{ i : p_(i) <= i q / |F| }; rows ranked <= k cross
  paused members and diagnostics: stored with p, no q, outside F, outside S and T2
Reading levels, derived from stored rows (a person reads; nothing acts, B2):
  evaluator check  an evaluator row crossed - read it before calling anything summary drift
  drift            quality_worse, something_changed or a quality member crossed on drift_consecutive_nights
                   consecutive judged nights (a P18 stretch of that length)
  watch            any other crossing
  quiet / too few days / new series (P14: earlier-series rows outside F)
Every crossed row prints its effect in its unit, raw and adjusted, its q, the inputs that changed inside the window,
and its role.
```

A new metric enters in five steps:
1. Declaration (P13): slug, role, column, statistic, line or transform, harm direction, adjust_by, instrument;
   lifecycle_status paused, combine_weight 0, rho 0.
2. Nightly while paused: computed and stored with p, no q; outside F, S and T2, so it moves no other row.
3. The replay (row #8) runs it over past dates and adds its injected change to the library; prints its no-change
   crossing rate, its pooled lag-1, its power, and (quality only) a proposed combine_weight inside the
   worst-case-best vector below.
4. The owner sets it active; a person commits rho and combine_weight.
5. A new statistic of an existing kind is config (Level 3); a new kind is a module, its tests and a review.

Weights (P17): the replay starts from the axis weights and from clip(R^-1 delta-bar, 0) (R: correlation of the
quality members over the baseline; delta-bar: the mean standardised shift of the injection library: swapped
numbers, entities and dates, negated predicates, dropped hedges, truncation, copied lead, repetition, unfaithful
shares); scores candidate vectors on the simplex by the minimum detection across injection types at the fixed
q; prints the best; a person commits. Calibration does not depend on the weights, because every p comes from the
re-deals. R^-1 delta is a start, not the rule: with R from r4's 17 days it moves weight onto members that did not change
(numbers doubling gave faith_index 0.31 through their -0.22 correlation), and positive parts are not linear.

### SP6. Replay and simulation numbers, second-pass rule

Real series (lambda 0.15, baseline 28, q 0.05, series split at the model switch only):

| Nights | Crossed | Level | Read as |
| --- | --- | --- | --- |
| 09-09..09-10 | copy_index, copy_ceiling | watch | 09-07: copying up |
| 09-11..09-23 | + something_changed; length_median on 5 of the 8 nights 09-11..09-18 | drift from 09-12 | copying and length changed; faithfulness up, no quality row |
| 09-25..10-05 | hedges_dropped, something_changed, length_median | drift from 09-26 | 09-24: shorter summaries, more dropped hedges (part is the band-reason artefact) |
| 10-06..10-10 | length_median, something_changed | drift | baseline still holds pre-09-24 days |

| Configuration | Nights crossed of 31 | First night on the 09-07 step | quality_worse crossed |
| --- | --- | --- | --- |
| R, q 0.05 | 30 (26 at drift level; every night's 35 days span 09-07 or 09-24) | 09-09 | never |
| R, q 0.01 | 21 (18 at drift level) | 09-11 | never |
| W (flat), q 0.05 | 27 (24 at drift level) | 09-11 | never |
| R, 09-07 and 09-24 declared (stable stretches) | 0 of 8 | - | - |

Low-volume days: 10-05 (148 rows) carried 11 percent of its night's recent weight (22 percent with recency weights
alone, 14 percent flat and unweighted); 09-18 (138 rows) enters the same way; 09-14 (97 rows) falls under
min_day_rows and is stored as thin. The brief's 13 and 75 are published counts; the eval ledger held 97 and 255 rows
those days (first pass, 5.5).

No-change simulation (r4 days drawn with replacement; 8 members and the 2 combined rows):

| q | Nights with any crossing | Crossed nights per 30 | New member stretches per 30 | Drift events per 30 |
| --- | --- | --- | --- | --- |
| 0.05 | 2.4 percent | 0.68 | 0.87 | 0.10 |
| 0.01 | 0.6 percent | 0.20 | 0.20 | 0.03 |

Power, rule R (r4 days, baseline 28, q 0.05; change on 7 / 4 of 7 recent days):

| Injected change | Any row | Carried by |
| --- | --- | --- |
| 2 percent of summaries unfaithful | 0.72 / 0.43 | faith_below_050 0.70, faith_index 0.53 |
| 5 percent unfaithful | 1.00 / 0.97 | all faithfulness rows; quality_worse 0.92 |
| 5 percent mildly unfaithful (0.50 to 0.80) | 0.94 / 0.40 | faith_below_080 |
| One 10-a-day source unfaithful | 0.95 / 0.64 | faith_below_050 |
| Unsupported numbers doubled | 0.74 / 0.60 | numbers_unsupported; quality_worse 0.48 |
| Dropped hedges +3 points | 0.29 / 0.16 | hedges_dropped (the weakest: its band-reason stand-in moves 0.023 a day) |
| Copying x 1.3 | 1.00 / 1.00 | copy_index, copy_ceiling; something_changed 0.99 |
| Small coordinated shift | 0.84 / 0.57 | spread; quality_worse 0.46 |
| Every quality axis 0.5 day-SD worse | 0.25 / 0.15 | quality_worse 0.16 |

At q 0.01 the marginal cases lose about 20 points (first pass, flat window). Coherence -0.02 and coverage down one
bucket, judged in the first pass at 1.00, are now diagnostics: still computed and shown, no longer decisive.

### SP7. Approved items

| Item | Verdict | Change, and why |
| --- | --- | --- |
| P1 | Amended through P13 | The row gains role, statistic, recency_lambda, rho, raw and adjusted values, inputs_changed; site and page_type go |
| P4 | Keep | Its numbers now count whole-day re-deals |
| P7 | Withdraw | numpy suffices; no scipy extra in the council's jobs |
| P13 | Amend | Declarations gain role (quality, behaviour, evaluator, diagnostic, covariate) and rho; kinds become statistics (mean of a transform, share past a line, median, IQR); one test module. Why: the survey separates judged quality, monitored behaviour, diagnostics and covariates, and the approved registry has no field to say which, yet the composite must sum quality only |
| P14 | Keep | Per-column instrument keys (first-pass Q5). The survey's extension to prompt and runtime changes is not adopted (Q-h): in this pipeline it would blind the judge 13 nights after every change, about every 9 days |
| P15 | Amend | Two calibrated combined rows (quality_worse, something_changed) instead of one, plus reading levels. Why: the 09-07 step is a behaviour change a quality composite must not call worse, yet a person must see it. Still no automatic actions |
| P16 | Keep, widen | The digest is the only short-term comparison; the 52-week long baseline covers the quality members (the survey's long anchor) |
| P17 | Keep, sharpen | Starting points and the worst-case rule of SP5; rho is set the same way; a person commits |
| P18 | Keep | Drift is a stretch of drift_consecutive_nights |

### SP8. Settings fields (config/judges/summary-fidelity-judge.json)

| Field | Default | Range | Note |
| --- | --- | --- | --- |
| recent_days | 7 | 7 to 14, whole weeks | F1.1, range narrowed |
| baseline_days | 28 | 14 to 56, whole weeks | F1.2, range narrowed |
| recency_lambda | 0.15 | 0 to 0.5 (0 is the flat window) | new |
| min_day_rows | 100 | 20 to 1000 | new; replaces F1.3 min_articles |
| min_recent_days | 4 | 3 to 7 | new |
| min_baseline_days | 7 | 7 to 28 | new |
| min_window_rows | 20 | 1 to 1000 | F1.4 |
| reshuffle_stop_hits | 10 | 1 to 100 | F1.6 and P4, unchanged; a reshuffle now deals whole days |
| reshuffle_cap_floor | 100000 | 1000 to 10000000 | F1.7 and P4, unchanged |
| reshuffle_cap_multiple | 10 | 1 to 100 | F1.8 and P4, unchanged |
| false_discovery_rate | 0.05 | 0.001 to 0.2 | F1.11 |
| crossings_budget | 10 | 1 to 100 | F1.12 |
| drift_consecutive_nights | 2 | 1 to 7 | new, reading level |
| logit_clip | 0.001 | 0.000001 to 0.01 | new, faith_index |
| length_band_edges_words | [900, 1650] | ascending, 100 to 10000 | new; a test holds them to HHEM's window geometry (chunk 900, overlap 150) |
| source_shrinkage_rows | 10 | 0 to 100 | new |
| trailing_line_quantile | 0.10 | 0.01 to 0.25 | new, diagnostic tails |
| long_baseline_weeks | 52 | 12 to 156 | F1.14 |
| long_window_days | 28 | 7 to 91 | F1.15 |
| metrics[].lifecycle_status | paused on landing | active, paused, retired | P13 |
| metrics[].role | - | quality, behaviour, evaluator, diagnostic, covariate | new |
| metrics[].statistic | - | mean, median, share_below, share_above, iqr | new |
| metrics[].line | 0.50 / 0.80 (hhem), 0.50 (verbatim_run), 0.05 (self_repetition), 25 (summary_words) | inside the column's range | new |
| metrics[].transform | none | none, logit | was log1p |
| metrics[].harm_direction | - | higher, lower, either | P13 |
| metrics[].adjust_by | [] | subset of length_band, source, hedging_present; quality only | new |
| metrics[].instrument | - | the stamp field whose change starts a series | P14 |
| metrics[].combine_weight | 0 | 0 to 10 | P17 |
| metrics[].rho | 0 | 0 to 0.8 | new; replay proposes, a person commits |

Removed: F1.5 short_tail_percentile, F1.9 multi_tenant_hosts, F1.10 page_types.

### SP9. Open questions after the second pass

Still open from the first pass: Q1 (who owns per-source extraction health), Q2 (unit: the digest), Q8 (plan 36
division; if Q-g is A, rows 6 and 10 go as well), Q11 (mix), Q12 (accepting a change). Superseded: Q3 by Q-c and
Q-d, Q4 by Q-h, Q5 by I6 and SP7's P14 row, Q6 by Q-f, Q7 by Q-g, Q9 by Q-i, Q10 by Q-j.

| Q | Question | A | B | C | Recommended |
| --- | --- | --- | --- | --- | --- |
| Q-a | Judged set | SP2: quality judged; copying and length behaviour; coverage and coherence diagnostics | The first pass's set | Judge every column | A |
| Q-b | Nightly test | Recency-weighted window, whole days re-dealt, lambda 0.15 | Flat window (lambda 0) | The survey's EWMA with reference-only limits | A |
| Q-c | Combined rows | quality_worse and something_changed (P15 amended) | quality_worse only | Members only | A |
| Q-d | Composite form | Positive parts | Signed, correlation-normalised (the survey's C) | - | A |
| Q-e | Faithfulness instrument | I1, I2 and I6 as one eval-row change, after a one-day measurement | I1 only | Keep whole-summary HHEM | A |
| Q-f | Completeness and conciseness | Pilot the key-fact judge on injected omissions (I4) | Build it now | Never | A |
| Q-g | Plan 36 row 6 (self-judged fluency) | Drop it, with row 10 | Build it as its own tenant | Build it as specified | A |
| Q-h | New series on prompt or runtime changes | Keep P14; label crossings with the changed inputs | Extend P14 to every declared input | No split even on a model change | A |
| Q-i | Baseline | 28 days | 56 days, lagged | 14 days | A |
| Q-j | False-discovery rate | 0.05: 0.10 false drift events a month | 0.01: 0.03 a month, about 20 points less power on marginal changes | 0.10 | A |
| Q-k | Autocorrelation | A per-member rho the replay proposes and a person commits | Estimated nightly from the baseline | None | A |
| Q-l | Second checker | After I1, a 100-a-day trial | Now, every item | Never | A |


---

# Fowler - hard look at the judge plan, plan 36 and the council plan (2026-10-11)

Scope: structure only - contracts, rows, ledgers, process safety, console homes, tracking.
Which quantities the judge tests, the tests themselves and the composite are Andre's (Q20, Q23, Q24);
this report leaves slots for them and decides nothing about them.

Snapshot. Both plan files changed while this review ran (mtime 2026-10-11 07:59:58 UTC; the judge
plan grew from 99,175 to 104,878 bytes). Findings refer to the 07:59:58 versions
(judge plan md5 768eaad8..., council plan md5 7c66eb3c...) unless a line says "01:09 version".
The 07:59:58 judge plan already carries: P13 to P19 approved, the hold on rows #2 and #4 to #14,
the ledger renamed drift-evals with contract DriftEval (stem drift-eval), Table C and F1.5 fixed,
and a new Table Q (requests Q1 to Q27).

Sources read: plan/20261011-summary-fidelity-judge-plan.md, plan/20261011-council-follows-gardener-plan.md,
review/hardlook/plan36.md, review/hardlook/autotune-summary-quality.md, review/hardlook/BRIEF.md,
review/CLAUDE.md, review/fowler.txt, review/gardener_src/ (idhazh-gardener.md, knobs_gardener.py.txt,
gardener_publish.py.txt, gardener_shards.py.txt, committing.md, concept-config-gardener.md,
test_llm_council_workflow.py.txt), review/council_src/ (llm-council.md, council_matrix.py.txt,
session.py.txt), review/ledger_src/ (lname.py.txt, ledgers.py.txt, registrydoc.txt, registry.txt,
keys.py.txt, council_run_record.py.txt, council.txt), review/eval_row.py, review/appconfig.txt,
review/execute-a-plan.md, review/author-a-plan.md, review/hardlook/daymetrics_series.json.

---

## 0. Answer first

- The unit change deletes more than it adds. Of the judge plan's 12 live rows, 4 collapse
  (#2 site identity, #5 count, #6 share kinds, #14 long baseline to Table B), 6 change, 2 stay,
  and 1 is new (#15 location, spread and tail kinds). Net: 3 fewer build rows.
- Nothing has been written to drift-evals yet, so the shape can still be rewritten in the plan with
  no expand-migrate-contract. After row #3 merges, every change costs a migration. Rule the shape
  once - including the composite's fields - before row #3 starts.
- The site field is replaced by the series: model_id (always set; the judge's unit) plus one
  declared instrument stamp (today scorer_version). No stratum on the row: the published eval
  ledger already answers "where did it move" in the console's Data explorer.
- The mix problem does not vanish; it moves up one level. A digest-level faithfulness statistic
  moves when the source mix moves, because HHEM is length-sensitive. #1270 can recur at digest
  level unless Andre's tests adjust for mix. Judge C6 must be rewritten, not deleted.
- Whole days, not single articles, are the re-deal unit for every digest-level test (judge U1.1,
  U2.1: single-article reshuffles crossed about 200 times nominal under a shared day movement;
  Andre's finding, his to confirm per test). Row #6's exact tests (beta-binomial, Fisher) assume
  exchangeable articles and do not carry over.
- Plan 36 and the judge would give two answers to "has metric X drifted". Recommended division:
  the judge owns every fleet-level alarm and the composite; plan 36 keeps per-item actions,
  fluency production and the rejects ledger. Plan 36 rows 1, 2, 4 and 5 collapse (plan 36 E1 made their
  only output a watch-only alarm). One console home: the Model (Summaries) page, as judge P5 ruled.
- Plan 36 carries stale premises that block execution regardless of the division: an EvalRow
  column written next day by another workflow, a G-Eval "leg" in a workflow that names no tenant,
  a new non-door ledger, and a history rewrite outside the gardener's history job.
- drift-evals is legal (values are unique; none collides) but it is a "kind of thing" name, which
  the owner's 2026-09-27 registry rule forbids. Keep it by the owner's newer ruling and write the
  dated exception into ledger-registry.md in row #3.
- Council plan: of 30 gardener strengths, 26 are covered or deliberately deferred, 1 does not
  apply, 3 are missing or partial. Missing: a test holding every active judge to a named decision,
  a worked lifecycle example, telemetry for no-model cells, an operator range for one judge,
  retryable fault words. Add the first two inside row #1; no new row is justified.
- Rendering: two faults in the 01:09 judge plan (Table C delimiter; F1.5 extra cell), both fixed
  at 07:59:58. Zero faults now in either plan. The F1.5 fault was the worse one: it showed a wrong
  value silently.
- Tracker: move Table Q out of the judge plan into one cross-plan file, TODO/owner-requests.md.
  A plan-doc is deleted at closure, so a tracker inside one plan dies with it.

---

## 1. Rows - judge plan, digest per production model series

### 1.1 What the unit change implies for structure

- No consumer needs a site key. site.py, multi_tenant_hosts (judge F1.9) and page_types (F1.10)
  have no reader once neither the unit nor any declaration groups on site.
- The series is the grouping. One production model at a time (qwen3-8b-q4-k-m 2026-08-21 to
  2026-08-26; qwen3-5-9b-q4-k-m from 2026-08-27, daymetrics_series.json). A replaced model or
  instrument starts a new series and compares with the old one outside the step (P14, G1.6).
- The day is the re-deal unit. One day's articles share pipeline state; re-dealing articles across
  days understates the null spread (judge U2.1).
- Mix still matters. "Slicing costs a long article 0.40 of its score" (judge G2.4, citing
  evaluation.md): a change in the digest's length mix moves digest-level HHEM with no change in
  quality. The owner's "should be weighted ... or even per site" is the same point.
- The measured series stamp is coarse. extractiveness p50 fell around 2026-09-24, the day
  coherence and semantic_coverage arrived (plan 36 E2 says plan 35 bumps METRICS_VERSION, which is
  folded into scorer_version). Probable instrument change, not drift; verify against the eval
  ledger's scorer_version before the replay treats it as a known event. This is why the key column
  should name the instrument generically (section 2).

### 1.2 Table A - rows #1 to #14

| # | Row (current title) | Disposition | Why, and what moves where |
| --- | --- | --- | --- |
| A1 | #1 The drift review is deleted | Stays | Independent of the unit. One edit: the SUPERSEDED_APP_NAMES message (row #1 Files touched, app_config.py; E1.3) must not promise that min_articles moved, because the digest-level floors replace it; name the judge and E1.3's moved settings only |
| A2 | #2 The judge's settings file and site identity | Collapses | Site identity deleted: site.py, test_site.py, F1.9, F1.10, F2.3 to F2.5, F3.3, F3.4. The settings file, its model, settings.py, test_settings.py and the judge's doc page merge into #4, the first row that reads a setting (judge F1 caption: each setting lands in the first row that reads it; CLAUDE.md section 10: no empty modules for later). Per-site views return only as diagnosis, which the Data explorer already serves (summary-quality-evals is in ledger.published, appconfig.txt) |
| A3 | #3 The judge's ledger and its tenant module | Changes | Shape changes (section 2): site and page_type leave (H3.7, H3.8), the series fields are always set, the key shrinks (H4.5), the outcome and unit vocabularies change. Still Level 5, judge C1 fires. Add to Files touched: docs/architecture/contracts/ledger-registry.md, a dated line that drift-evals takes a kind name by the owner's 2026-10-11 ruling (section 2.5). Depends also on the owner's shape ruling, which should include the composite's fields so #13 needs no second Level-5 change |
| A4 | #4 Metric declarations, the kind registry and the note kind | Changes, absorbs #2's file | Declarations keep P13's form with grouping replaced by series (section 2.3). The window reader keeps day labels and the newest row per url_key, per series. The window guard (H1.8, G1.8) becomes per series with a per-day floor (thin days: 13, 75, 138, 148 summaries scored). The note kind and page_mix (H1.7) collapse: no page types, and G1.3 refuses a module no declaration uses |
| A5 | #5 Count kind: article count from the item-health census | Collapses | Feed volume per site is not summary quality; feed-health already rests a stopped feed (judge B4); thin days are #4's guard. Judge tables I1 and I2, ruling P3, the scipy.stats.nbinom oracle and item B4 go |
| A6 | #6 Share kinds: unusually short and page furniture | Collapses | unusually_short is an article-length property (the owner: judging on article length is wrong); page_furniture reads extraction_suspect, an extraction property (judge B1 keeps extraction out). A share-of-a-flag statistic survives only if Andre declares a digest-level one (low-band share, doubt reasons, withheld share); it then lands in #15, re-dealt by whole days. Judge tables J1 and J2, ruling P2 and the beta-binomial and Fisher oracles go: both assume exchangeable articles |
| A7 | #7 Distance kind: article length, copied phrases and faithfulness | Changes | Two-sided Wasserstein-1 (judge K1.1, judge S3) stays as one candidate statistic on summary-quality columns, re-dealt by whole days. article_length (H1.4, K1.2) goes; within-page-type rules (K1.3, K1.4) go; the earlier-series comparison (L1.2, L1.3) stays per series. Judge C6's #1270 fixture becomes a digest-level mix fixture: a length-mix shift with unchanged per-length score distributions must not cross, if Andre's tests adjust for mix |
| A8 | #8 One false-discovery step per judged date, and the replay | Changes | Benjamini-Hochberg per (run_id, date) stays (M1.1 to M1.4). The replay re-deals whole days as its main null (the P18 arm becomes the default), injects digest-level shifts per metric (location, spread, tail) and multi-metric slips, and runs 2026-08-21 to 2026-10-10 with the 2026-08-27 model switch and the 2026-09-07 step as named events. The reading budget (judge C5, F1.12, M1.5) is re-derived for about 10 to 20 checks a night per series; it is probably never binding |
| A9 | #9 The switch | Stays | One edit: its observation reads "peak memory on a cell with no model server", which nothing records ("No machine is recorded per unit", llm-council.md). Read run time from council-run-records seconds_spent and drop memory (recommended, Table X) |
| A10 | #10 Scorer reference check, #11 Golden-set check | Collapsed | Unchanged (judge D3, judge B10) |
| A11 | #12 The stored checks on a console page | Changes | Per series and per metric: the latest effect, q_value and stretch, plus the composite line; no site column; T1.3 at series level. Home stays the Model page (P5) unless the owner rules otherwise (Table T). Shares frontend/src/routes/console/model/ files with plan 36 Row 9: serialize. Re-derive at dispatch: config/idhazh.json page_weight.payload_ceilings_bytes holds one index entry per ledger in ledger.published (8 of 8 today), so drift-evals likely needs one |
| A12 | #13 All-sites comparison and combined-measures check | Splits | all_sites collapses: the digest is the unit, and its whole-day re-deal rule (U1.1) moves to G1 as the rule for every kind. combined stays as "The composite drift decision per model series" (U1.2 to U1.6, P15, P17 carried; contents Andre's, Q24) |
| A13 | #14 Long-baseline comparison | Collapses to Table B (recommended, Table O) | A 52-week look needs one production series 56 weeks old; this history changed model after 6 days. A PENDING row gated on about 2027-09 also keeps the plan open a year, because closure needs every row DONE or COLLAPSED (execute-a-plan.md, Closure). Judge F1.14, F1.15 and tables V1 and V2 move into the B-item as evidence. State the blind spot: 7-against-28 trailing windows cannot see a slow decline (V2.1, P16 evidence) |
| A14 | New #15 Location, spread and tail kinds | New | The statistics Andre names (the owner: "focus on variance of the metrics"). One module per kind with its own parameter model; may split into one row per kind |

### 1.3 Table B - every judge-plan table

| # | Table | Disposition |
| --- | --- | --- |
| B1 | A (operating contract) | Changes: A1 states the owner's 2026-10-11 unit ruling; A2 scope list loses site identity, six per-site measures, all-sites and long baseline; A5 strategy becomes the design-of-record metrics per model series plus the survey (Q23), not the 2026-10-10 per-site blueprint; A6 order follows Table C |
| B2 | B (out of scope) | Judge B1 to B3 and B5 to B9 stay; judge B4 collapses with #5; judge B10 and B11 change wording from "per site" to "per series" and drop page_furniture; add judge B12 long baseline, judge B13 per-stratum diagnosis rows (Data explorer covers it), judge B14 per-item actions at absolute floors are plan 36's |
| B3 | C (ESCALATE) | Judge C1 to C4 and C7 to C10 stay; judge C5 re-derived per series; judge C6 rewritten as a digest-level mix fixture; add judge C11 One answer: a row would add a second alarm, a second stored score or a second console home for a summary-quality metric - stop |
| B4 | D (Reckoner) | Changes to this report's Table C |
| B5 | E1, E2 | Stay (E1.3's message decoupled, A1) |
| B6 | F1 (settings) | F1.1, F1.2, F1.4, F1.6 to F1.8, F1.11, F1.12 stay; F1.3 min_articles is replaced by Andre's digest floors (days per window, summaries per day); F1.5, F1.9, F1.10 collapse; F1.13 changes form (section 2.3); F1.14, F1.15 move to judge B12 |
| B7 | F2, F3 | F2.1, F2.2, F2.6 stay; F2.3 to F2.5 collapse; F3.1, F3.2 stay; F3.3, F3.4 collapse as moot; add a rejected alternative: sites or page types as the unit of judgment (owner, 2026-10-11) |
| B8 | H1 (declarations) | Replaced by Andre's declarations; the reserved names window_rows and combined_measures stay, per series |
| B9 | H2 (outcomes) | H2.1, H2.2, H2.4 to H2.6 stay; H2.3 too_few_articles renamed for the digest floor's unit (days or summaries) |
| B10 | H3 (row shape) | Changes: Table E |
| B11 | H4, H5 | H4.5 key changes (section 2.4); every other row stays |
| B12 | G1, G2 | G1.1, G1.4, G1.5, G1.8, G1.9 stay; G1.2, G1.3, G1.6, G1.7 change (kinds, refusals, series, page_furniture dropped); add G1.10 whole days are the re-deal unit (from U1.1); G2.1 to G2.4 stay; G2.5 collapses; add G2.6 per-site unit and G2.7 single-article reshuffles (from U2.1) |
| B13 | I1, I2, J1, J2 | Collapse with #5 and #6 |
| B14 | K1, K2, L1, L2 | Judge K1.1, K1.5, L1.2 and tables K2 and L2 stay; K1.2 to K1.4 collapse; L1.1 merges into judge table K1 (one distance kind); L1.3 per series |
| B15 | M1, M2, N1, N2 | Stay; M1.5 re-derived |
| B16 | T1, T2 | T1.1, T2 stay; T1.2 per Table T; T1.3 per series |
| B17 | U1, U2 | U1.1 moves to G1.10, U2.1 to G2.7; U1.2 to U1.6 and U2.2 stay with the composite, subject to Andre's redesign |
| B18 | V1, V2 | Move into B12 as evidence |
| B19 | P (rulings) | Judge P1, P4 to P10, P13 to P15 and P17 to P19 stay (P13 amended: grouping becomes series); judge P2, P3, P11 and P12 are superseded by the unit ruling; P16 changes (all-sites absorbed by the unit, long baseline deferred) and needs the owner; new P items for this redesign |
| B20 | Q (requests) | Moves to TODO/owner-requests.md (section 6) |
| B21 | R, S | Judge table R stays as history with R5 and R7 marked superseded (owner, 2026-10-11); judge S1 to S3 and S5 stay; judge S4 becomes the digest floors; judge S6 is moot |

### 1.4 Table C - the new row list

| # | Row | Title | Depends-on | Parallel-group | Level |
| --- | --- | --- | --- | --- | --- |
| C1 | 1 | The drift review is deleted | - | A | 3 |
| C2 | 2 | COLLAPSED: settings file merged into #4; site identity deleted (owner, 2026-10-11) | - | - | - |
| C3 | 3 | The judge's ledger and its tenant module | council plan: Judges carry a status and a model need; owner ruling on the digest-level shape | A | 5 |
| C4 | 4 | The settings file, metric declarations and the kind registry, per model series | 3 | B | 3 |
| C5 | 5 | COLLAPSED: count kind (not summary quality; thin days are #4's guard) | - | - | - |
| C6 | 6 | COLLAPSED: share kinds as declared; a flag-share kind, if declared, lands in #15 | - | - | - |
| C7 | 7 | Distance kind on the summary-quality metrics, whole days re-dealt | 4 | C (serial with #15: shared settings file, declaration model, doc page) | 3 |
| C8 | 15 | Location, spread and tail kinds on the summary-quality metrics | 4 | C | 3 |
| C9 | 8 | One false-discovery step per judged date, and the replay | 7, 15 | D | 3 |
| C10 | 9 | The switch: the judge joins the council | 1, 8 | E | 3 |
| C11 | 13 | The composite drift decision per model series | 9 | F | 3 (5 if its fields were not ruled with #3) |
| C12 | 12 | The judge's panel on the console's Model page | 9 (13 adds the composite line) | F | 3 |
| C13 | 14 | COLLAPSED to judge B12: long baseline, until one series holds 56 weeks | - | - | - |
| C14 | 10, 11 | COLLAPSED (unchanged) | - | - | - |

Row numbers of surviving rows are kept stable, as #10 and #11 were, because the judge plan's
Table Q and item B8 and the council plan cite them.

---

## 2. Shape

### 2.1 Table D - names after the site prefix left (all verified in the 07:59:58 row #3)

| # | Item | Was | Now | Rule that forces it |
| --- | --- | --- | --- | --- |
| D1 | Contract module | backend/idhazh/contracts/site_drift_eval.py | backend/idhazh/contracts/drift_eval.py | module named for its class |
| D2 | Class | SiteDriftEval | DriftEval | owner disapproved the site prefix (Q19); unique once row #1 deletes DriftConfig |
| D3 | Schema stem | site-drift-eval | drift-eval | __schema_stem__ pattern (council-run-record, eval-row) |
| D4 | LedgerName member | SUMMARY_FIDELITY_JUDGE_SITE_DRIFT_EVALS | SUMMARY_FIDELITY_JUDGE_DRIFT_EVALS = "drift-evals" | family first, value in upper snake (ledgers.py _every_member_is_named_for_its_place) |
| D5 | config/ledgers.json prefix | ["summary-fidelity-judge", "site-drift-evals"] | ["summary-fidelity-judge", "drift-evals"] | starts with the family, ends with the value (ledgers.py _every_door_prefix_names_one_safe_folder) |
| D6 | Folders | state/raw/summary-fidelity-judge/site-drift-evals/ | state/raw/ and state/compact/ summary-fidelity-judge/drift-evals/ | the prefix inside both door roots (registrydoc) |
| D7 | Gardener compaction task | compact-summary-fidelity-judge-site-drift-evals | compact-summary-fidelity-judge-drift-evals | compact-<folder>, each / written - (concept-config-gardener.md, What the loader refuses) |
| D8 | Lists that name the value | site-drift-evals | drift-evals | task_names, RETENTION_LEDGERS, LEDGER_NAMES, ledger.published, fixture folder |

House precedent, for the record: the similarity judge's generic-valued ledger "metrics" has the
family-prefixed class ContentSimilarityJudgeMetrics (keys.py). DriftEval departs from it; that is
acceptable while the class name is unique, and matches the owner's preference for short names.

### 2.2 Table E - DriftEval fields (replaces judge H3)

| # | Field | Disposition | Meaning |
| --- | --- | --- | --- |
| E1 | run_id, judge_id, date, checked_at, rules_version | Keep | as H3.1 to H3.5 |
| E2 | recent_days, baseline_days, baseline_end | Keep | as H3.6 |
| E3 | site | Remove | the digest is the unit |
| E4 | page_type | Remove | no page types |
| E5 | check_name | Keep | a declared slug with one meaning forever (G1.4), or a reserved name |
| E6 | metric | Add | the declared label that groups one metric's checks on one chart (faithfulness, coverage, coherence, fluency); not in the key |
| E7 | model_id | Change | always set: the production model series that wrote the judged date's summaries; a switch day judges each series present |
| E8 | instrument | Rename of scorer_version (Table Q) | the value of the instrument stamp the declaration names; today scorer_version, later judge B11's per-column stamp; null when the column depends on no scorer |
| E9 | baseline_count, recent_count | Change meaning | summaries read on each side |
| E10 | baseline_days_used, recent_days_used | Add | days that met the per-day floor; the re-deal unit, so the p-value's resolution |
| E11 | baseline_value, recent_value, effect, direction | Keep | definitions per kind (Andre); Direction loses shorter and longer |
| E12 | p_value, q_value, reshuffles, reshuffle_hits, outcome, changed_part | Keep | re-deals are whole days |
| E13 | settings in force (H3.17) | Change | false_discovery_rate stays; min_articles and short_tail_percentile leave; Andre's digest floors join |
| E14 | test_kind | Keep | it is the statistic: the closed word of the kind that made the row (vocabulary per Andre) |
| E15 | value_unit | Keep | score, share, ratio; words and per_day leave |
| E16 | check_definition | Keep | derived; now spells the series, the instrument field, the kind's parameters, transform, harm direction, comparison, and the composite's members and weights |
| E17 | comparison | Keep | trailing_window (was site_window) and combined; long_baseline returns with judge B12; all_sites leaves |

### 2.3 How grouping and statistics are declared now (P13's registry kept)

What stays from P13: declarations in config/judges/summary-fidelity-judge.json (F1.13); one kind
module per statistic family under summary_fidelity/kinds/; one comparison module per comparison
under summary_fidelity/comparisons/; the loader's refusals (G1.3); meaning never edited (G1.4); a
new declaration lands paused (G1.5); a declaration never names a module or path (G2.3).

Table F - one declaration

| # | Key | Change from P13 | Meaning |
| --- | --- | --- | --- |
| F1 | slug | same | the check_name |
| F2 | lifecycle_status | same | active, paused, retired |
| F3 | metric | new | the chart label (E6) |
| F4 | kind, plus that kind's parameters | changed | the statistic and its test, one per declaration; parameters (a fixed line, a quantile, a flag value) are validated by the kind's own model, and a key on the wrong kind is refused by name, as the gardener refuses one (concept-config-gardener.md) |
| F5 | source (ledger, column) | same | a door ledger and a column typed as the kind reads |
| F6 | instrument | replaces grouping | the one stamp field on the source row whose change starts a new series; model_id is implicit, because the series is the judge's unit |
| F7 | transform, unit, harm_direction | same | harm_direction gains both, for spread |
| F8 | comparisons | same | [trailing_window] today |
| F9 | combine_weight | same | 0 to 10, set by the replay and committed by a person (P17) |

Statistics: one statistic per declaration, named by its kind (Table R). Three statistics of
faithfulness are three declarations sharing metric "faithfulness". check_name therefore fixes the
statistic, so the key needs no statistic column. The composite weights attach to exactly these
(metric, statistic) pairs, which is what P17's weights need.

New refusals for G1.3: an instrument field the source row lacks; a source row with no model_id;
a kind parameter the kind does not read.

Comparison modules: trailing_window and combined only. all_sites and long_baseline are not built
(Table A, A12 and A13).

### 2.4 The key (judge H4.5)

Now: run_id, date, site, check_name, comparison, page_type, model_id, scorer_version.
Proposed: run_id, date, check_name, comparison, model_id, instrument - no preference, so packing
keeps every council run of a date; a reader of one judged date takes the run with the latest
checked_at (H4.5's rule, unchanged). It is minimal: check_name fixes metric, kind and statistic;
model_id and instrument fix the series; comparison stays because long_baseline will return.

### 2.5 Ledger-name uniqueness, verified, and what drift-evals costs

Verified rule:
- ledger_src/lname.py.txt: LedgerName is a StrEnum under @verify(UNIQUE); "Two members may not
  share a value"; "A value is one segment, and the nest above it is not part of it."
- ledger_src/ledgers.py.txt: one entry per member, one family per ledger, the prefix ends with the
  value, the Python name is spelled from family and value.
- The bare value is the lookup word everywhere a ledger is named in config or code:
  ledger.published (appconfig.txt), appends_to and CompactionPolicy.ledger (knobs_gardener.py),
  LEDGER_NAMES in the frontend (registrydoc, Onboarding). That is why uniqueness is load-bearing
  and is not just a folder rule.
- drift-evals collides with no existing value (lname.py.txt lists 24 values).

Table G - what drift-evals costs

| # | Cost | Size | Mitigation |
| --- | --- | --- | --- |
| G1 | No other family may ever name a ledger drift-evals | Every later drift ledger takes a longer name | Name it for what it holds (merge-line-drift for the similarity judge) |
| G2 | drift-evals is itself a "kind of thing" name. registrydoc, owner decision 2026-09-27: "The value says what the ledger holds, never the kind of thing it is ... the next ledger of that kind has no name left" | A rule conflict, not a defect | CLAUDE.md section 0: amend in the same commit. Row #3 adds a dated exception line to ledger-registry.md (Table V) |
| G3 | The precedent is already paid once: the similarity judge holds the generic values metrics, archive and score-distribution | None new | - |
| G4 | A second judge filing into drift-evals is not a way out: the ledger sits in this judge's family, and pausing that family would stop the other judge's rows (council E1.4) | - | Keep one writer |

Net: small, if every summary-quality drift check files in drift-evals. Fluency and the withheld
share then arrive as declarations, not as ledgers of their own (section 3).

---

## 3. Plan 36 and the judge - one answer per question

Facts: plan 36 is authorized (2026-09-19) and unstarted. Plan 36's E1 made every adaptive floor a
WATCH-only fleet-rate alarm; its D4 says a displayed overall "feeds no action"; its Row 9 puts
quality bands and a withhold panel on /console/judgement/; judge P5 put the judge's panel on the
console Model page. The design of record says the publish gate is "a veto chain, never a
composite". The owner's composite (Q24) and that sentence do not conflict: the gate decides one
item for a reader; the composite decides fleet drift for a person and acts on nothing (judge B2).

Table H - one answer per question (recommended division, Table S)

| # | Question | The one answer | Owner plan | What it replaces |
| --- | --- | --- | --- | --- |
| H1 | Has metric X drifted for the current production model? | The judge's per-metric rows in drift-evals | Judge | plan 36 rows 1, 2, 4, 5 (adaptive watch floors) and Row 9's withhold-rate alarm |
| H2 | Has summary quality drifted overall? | The judge's composite row per series | Judge #13 | plan 36 Row 7's optional displayed overall |
| H3 | Where does each per-summary score live? | hhem, semantic_coverage, coherence, publish_decision, withheld_reason on the eval row; fluency in the fluency judge's own ledger | Plan 36 rows 3, 6 | the geval column on EvalRow |
| H4 | Does this item publish? | The veto chain on absolute floors (HHEM 0.50, unsupported number), stamped on the eval row, flag flipped by Row 8 | Plan 36 rows 7, 8 | - |
| H5 | What was withheld, and why? | item-health FailureCode and the rejects ledger | Plan 36 rows 8, 9, 12 | - |
| H6 | Where does a person look? | The console Model (Summaries) page | Judge #12 and plan 36 Row 9 | quality views on /console/judgement/ |
| H7 | Where is the design written? | autotune-summary-quality.md keeps the metrics and the gate; its loop section points to the judge's page | Judge #4 (doc edit) | plan 36 G14's loop edits |

Table I - plan 36 rows under the division

| # | Plan 36 row | Disposition | Reason |
| --- | --- | --- | --- |
| I1 | 1 Extract the fit core | Collapses | Its only second user, Row 5, collapses (plan 36 Row 1 decision 1 extracts "at the second user") |
| I2 | 2 Two contracts and the per-metric knob block | Collapses | Consumers were watch floors (plan 36 E1) and band charts (Row 9). Also stale: one file per metric under state/summary-quality/ is a new non-door ledger, and "A new ledger files through the ledger door from its first row" (registrydoc, Onboarding) |
| I3 | 3 EvalRow columns | Changes | Keep publish_decision and withheld_reason. Drop geval: the eval row is written same day by the digest, raw files are immutable (judge H5.1), and a judge's readings belong in its own ledger (llm-council.md, four-layer table). Drop the "state/scores merge=union" HARD WAIT: the eval ledger is a door ledger and no union driver remains (registrydoc) |
| I4 | 4 The fold | Collapses | No fit |
| I5 | 5 The fit and the seed | Collapses | Plan 36 E1 left it a watch-only alarm, which the judge provides with a p-value per series; its design-of-record edits move to judge #4 |
| I6 | 6 G-Eval fluency judge | Changes | A council tenant of its own: entry paused with runs_model true (council row 1), its own family and ledger, its own cells. Not "one leg/step added to llm-judges.yml": the workflow names no tenant (test_this_workflow_runs_the_councils_own_verbs_and_names_no_tenant). Not a step reusing another judge's hot server (plan 36 E9): that puts one judge's work inside another judge's unit, against the council's separation of tenants (llm-council.md, The venue and its tenants are separate things). Lands the paused fluency declaration in config/judges/summary-fidelity-judge.json |
| I7 | 7 Veto-chain gate, record-only | Changes | Reads absolute floors from config only; delete the optional displayed overall; lands a paused withheld-share declaration once it stamps publish_decision |
| I8 | 8 Flip the flag | Stays | - |
| I9 | 9 Console | Changes | Band charts go; the withhold panel (count, about 11 percent baseline, reasons) moves to the Model page as display; its own alarm goes (the judge's withheld-share declaration) |
| I10 | 10 Measure a G-Eval call | Stays | Sizes the fluency tenant's own cells |
| I11 | 11 Coherence placement | Stays | - |
| I12 | 12 Rejects ledger | Changes, needs the owner | Must be registered, or the trials sweep empties state/rejects/ (ledgers.py docstring). Retention through a gardener declaration and history removal through the gardener's history job (CLAUDE.md section 8, History Exception), not prune_state.py and "prune.yml's force-push" (plan 36 J4). A door ledger cannot keep plan 36 J4's 30 days: its compaction absorbs a month only daily_keep_days (at least 31, knobs_gardener.py) after the month ends, and the approved chain keeps 36 months (registrydoc). So it needs a named exception (Table Y) |
| I13 | 13 Retro gaps | Stays | Applies to the fluency tenant |

Side effect: with Row 1 collapsed, plan 36 no longer waits on plan 34's fit core; Rows 3, 6 and 7
wait only on plan 35's EvalRow churn.

What the judge plan must change:
- Judge A2 scope adds "the one drift answer for every summary-quality metric"; judge Table B adds
  item B14 (per-item actions at absolute floors are plan 36's); judge Table C adds trigger C11 One answer.
- #4 declares hhem, semantic_coverage and coherence (the last two scored since 2026-09-24) and edits
  autotune-summary-quality.md's loop section to point at the judge's page.
- Fluency and withheld share arrive paused from plan 36 rows 6 and 7; activation is an owner
  ruling after the judge's replay runs them (G1.5).
- #12 stays on the Model page (P5) and serializes with plan 36 Row 9.

What plan 36 must change: Table I, plus its stale text - "LLM-JUDGES" and llm-judges.yml (now
LLM-COUNCIL), Section 0's strategy line, 0a's transfer table, 0b D1 and D5, 0c E2, E3 and E9,
0d G6 to G8, G10 and G11, and 0e J4.

---

## 4. Council plan - the gardener's strengths, row by row

The owner asked which row brings lifecycle, logging, telemetry and the rest. Short answer:
lifecycle is row #1; logging is row #3; the job page is row #5; telemetry is the council's
existing record plus rows #8 and #9; permissions row #2; refusals row #4; sparse row #6 and council B4;
own dates row #7; commit is already the shared publisher. The council plan's Table S lacks the
telemetry rows, a worked lifecycle example and the named-decision test.

Table J - mapping (council rows cited by title; titles in the 07:59:58 council plan)

| # | Gardener strength (source) | Word | Council today | Council plan | Verdict |
| --- | --- | --- | --- | --- | --- |
| J1 | One declaration a unit; config never names a module (idhazh-gardener.md, What runs) | capability | slug resolves to the module that declares it | row 1 Judges carry a status and a model need; council B3 binding by name | Adapted |
| J2 | The named list is the unit set (task_names) | flexibility | council.tenants | row 1 (ordered entries, each slug once) | Covered |
| J3 | lifecycle_status active, paused, retired, no default; paused keeps its claim; retired stays as the record (knobs_gardener.py TaskLifecycleStatus) | lifecycle | none | row 1 (council E1.1, E1.2 and table E3) | Covered; worked example missing (Table K) |
| J4 | A switch ships safe unless a named decision put it live, held by a test (LIVE_BY_DECISION, test_gardener_config.py; registrydoc) | lifecycle | none | council E1.5 states the rule; no test holds it | Not covered - add to row 1 |
| J5 | dry_run with no default; every default reports and deletes nothing | lifecycle | - | council B1 (council P3: lands paused instead) | Deferred |
| J6 | The loader refuses as one set, naming file and rule | capability | unknown slug refused | rows 1 and 4 | Covered |
| J7 | Module refusals before any task: no module, unused module, kind mismatch, raising import, two modules one name; exit 2 | capability | sorted search | row 4 The council refuses a bad judge set before any unit runs | Covered |
| J8 | Standard-library plan job before install, held to the typed planner by a test (gardener_shards.py) | capability | the planning job installs | council B2 | Deferred |
| J9 | Round-robin split over sorted names | capability | per-tenant width on each cell | - | Not applicable |
| J10 | owns, reads, appends_to; every touched path inside owns; no claim on state/ (gardener_publish.py) | commit | committed_paths, publication_inputs, broad roots refused | council S7; reads for judging cells in council B4 | Covered |
| J11 | Each unit's own window and mark | flexibility | union of every tenant's dates | row 7 Each judge runs over its own outstanding dates | Covered |
| J12 | Operator range for one named unit; a hand run never pushes (idhazh gardener run-task) | flexibility | a dispatched date runs every judge | row 7 lets a dispatched date name one judge; no range | Partial - B-item |
| J13 | Download budget; cone_bytes and downloaded_bytes on every row | sparse, telemetry | none | council B4 | Deferred |
| J14 | One JSON event a line, fixed vocabulary | logging | plain lines | row 3 Council programs log one JSON event a line and exit with one vocabulary | Covered |
| J15 | Exceptions by type and place; the crash printer | logging | council_publish.py prints an exception's text | row 3 | Covered |
| J16 | A log group per unit; an error annotation for a failed unit | logging | none | row 5 The collecting job writes the night's summary on its job page | Covered |
| J17 | Job-page summary rendered from events alone | observability | none | row 5 | Covered |
| J18 | Exit codes 0 to 3, worst code wins, a fixed sentence each | observability | ad hoc | row 3 | Covered |
| J19 | Every stop says why: closed fault words; retryable faults stay green; recovered notes; sentences rendered at read time | observability | three outcomes; a raising unit files nothing | row 8 A unit that raises files a failed council record (failed, fault raised) | Partial - retryable words not covered |
| J20 | One record per unit, always, through the door | telemetry | the venue files a row in a finally | row 8 | Covered |
| J21 | Run identity, duration_ms, work_ended_at on each row | telemetry | run_id, started_at, seconds_spent, model_calls, tokens, model_seconds | existing | Covered; work_ended_at not applicable |
| J22 | Host fingerprint beside the runner | telemetry | HOST_FINGERPRINT venue ledger; collecting job clock stamped | existing; per-cell machine rejected for model cells (llm-council.md) | Covered; no-model cells not covered |
| J23 | The record is published | observability | not published | row 9 The council's record is published for the console | Covered |
| J24 | Shared publisher, exact operations, landing words, never read git's error text (committing.md) | commit | already the shared publisher | council S12; council P7 keeps stale and lost red, exit 1 | Covered (differs by design) |
| J25 | The commit loop lives outside the package | commit | council_publish.py under utilities | existing | Covered |
| J26 | Least privilege per job | commit | contents write on every job | row 2 Each council job holds only the permissions its steps use | Covered |
| J27 | Check out code and config only; list from the commit; fetch named folders; lazy fetch off | sparse | collecting job fetches declared inputs when sparse | row 6 The collecting job checks out code and config and fetches only named inputs; council B4 for judging cells | Covered and deferred |
| J28 | Never list state/ itself; an undeclared folder is refused | sparse | the window is all a tenant is handed | existing | Covered |
| J29 | Trial roots separate from production | flexibility | none | council B1 | Deferred |
| J30 | Every knob bounded; no default for safety keys; a wrong-kind key refused by name | flexibility | council knobs in config | row 1 (none defaulted, unknown keys refused) | Covered |

Not covered at all, and whether to add a row (none needs a new row):

- Named-decision test for active judges (J4). Add inside row 1. Consumer: council E1.5's rule and
  CLAUDE.md section 1 (no agent takes an exception for itself). A table in backend/tests/council/
  naming the owner decision beside each active entry fails a change that flips a judge active
  without one. Same files row 1 already touches.
- Worked lifecycle example (Table K). Add to row 1's llm-council.md edit. The owner asked for it,
  and the gardener's page carries examples of this kind.
- Per-cell telemetry on no-model cells (J22). No row. Carmack's 2026-09-21 reason (a 1.9 GiB probe
  on a 16 GB model cell) does not hold for a no-model cell, but no decision needs the reading: the
  judge reads about 10,000 to 16,000 rows (35 days at 280 to 450 a day). Fix the judge row #9
  observation instead (Table X).
- Operator range for one judge (J12). A new council B-item, B5; brings it in: the owner wants
  the judge's history before its switch (judge B5).
- Retryable fault words (J19). No. No consumer: the repair window already retries a dead night,
  and the window guard row covers a thin date. Brings it in: a judge whose unit can name a
  retryable cause.

### 4.1 Lifecycle example in row 1's shape

One judge's entry through its life (TenantEntry: slug, lifecycle_status, runs_model; none
defaulted; unknown keys refused; each slug once):

```json
{"slug": "summary-fidelity-judge", "lifecycle_status": "paused", "runs_model": false}
{"slug": "summary-fidelity-judge", "lifecycle_status": "active", "runs_model": false}
{"slug": "summary-fidelity-judge", "lifecycle_status": "paused", "runs_model": false}
{"slug": "summary-fidelity-judge", "lifecycle_status": "retired", "runs_model": false}
```

The committed list once judge row #3 lands:

```json
"tenants": [
  {"slug": "content-similarity-judge", "lifecycle_status": "active", "runs_model": true},
  {"slug": "summary-fidelity-judge", "lifecycle_status": "paused", "runs_model": false}
]
```

Table K - what each status does (council E3)

| # | Moment | Entry | What the council does | What keeps running |
| --- | --- | --- | --- | --- |
| K1 | Judge row #3 merges | paused, runs_model false | Nothing: no resolve, no nights_outstanding, no cell, no model server, no council record | Family summary-fidelity-judge is active in config/ledgers.json, but nothing writes it |
| K2 | Judge row #9, the owner's named decision | active, runs_model false | Resolves, asks nights_outstanding, one cell per date with no model server, settle files drift-evals rows | The gardener packs and ages drift-evals; the console reads it |
| K3 | A defect is found | paused | Stops at once; nothing is deleted | Packing, ageing, console reads; back at active it is asked only about nights inside the 7-night repair window |
| K4 | Replaced by a successor | retired | As paused, for good; the slug is never reused, so judge_id keeps one meaning in council-run-records | DriftEval stays while the family keeps rows; the family itself may later be retired in config/ledgers.json |
| K5 | Refused: runs_model missing | {"slug": "summary-fidelity-judge", "lifecycle_status": "active"} | Config load fails, naming the field | - |
| K6 | Refused: unknown status, or one slug twice | "lifecycle_status": "on"; two summary-fidelity-judge entries | Config load fails by name | - |
| K7 | Refused: active judge, paused family | entry active; family summary-fidelity-judge paused in config/ledgers.json | Planning step refuses, naming judge, ledger and family (council E1.4) | - |
| K8 | Refused: no module declares the slug | entry active; package deleted | Planning step exits 2, naming the slug (row 4) | - |

---

## 5. Rendering faults

Method: a parser that splits cells on unescaped pipes, compares header, delimiter and every body
row, flags pipes inside code spans, repeated row ids and tables glued to a text line. GitHub
renders no table when the delimiter's cell count differs from the header's, and it drops extra
body cells without warning.

Table L - findings

| # | Where | Fault | Effect | Status at 07:59:58 |
| --- | --- | --- | --- | --- |
| L1 | Judge plan, Table C (ESCALATE triggers), 01:09 version | Header 4 cells, delimiter 3 | Not a table at all: the block renders as text full of pipes (what the owner saw) | Fixed |
| L2 | Judge plan, Table F1 row F1.5, 01:09 version | 8 cells against 7; the cell "5 \| 6" was an unescaped pipe left by an edit (short_tail_percentile lands in row #6) | Silent wrong value: Lands in showed 5, Source showed 6, and "Blueprint section 1" disappeared | Fixed ("6", "Blueprint section 1"); the row itself collapses with the redesign |
| L3 | Judge plan, 07:59:58 | 38 tables: no count mismatch, no pipe in a code span, no repeated row id, no glued table | - | Clean |
| L4 | Council plan, 07:59:58 | 25 tables: as L3 | - | Clean (01:10 version read by eye, nothing seen) |
| L5 | Plan 36 (not asked) | 26 tables: one escaped pipe (G12), which renders correctly | - | Clean |

Guard: a fix is not a guard. Run the same check in the session's commit script
(.aether/scripts/commit_plan_to_main.py) and refuse to commit a plan with a fault. Not a repository
test: a test over TODO/*.md is a read that grows with the tree (Guardrail #12), and plans come and
go. The check is about 40 lines (Appendix).

---

## 6. Tracking every owner request

Finding: the judge plan's Table Q is the right content in the wrong home.
- A plan-doc is deleted at closure (execute-a-plan.md, Closure), so a tracker inside the judge plan
  dies with the judge plan. Q11, Q13, Q22, Q26 and Q27 already concern other plans and files.
- execute-a-plan.md: "a deferral with no receiving row is a dropped decision." The tracker is where
  a deferral lives until a receiving plan names it (judge B9, B11 and the proposed B12).
- The judge plan's Table Q mixes owner requests with items "raised by the review, not the owner" (Q26, Q27). One
  table, one question (CLAUDE.md section 1a): reviewer items are decision requests and belong in
  the owning plan's rulings table (Table P there); the tracker links to them.
- Precedent for a cross-plan working file: TODO/execution-order.md, deleted when its last plan closes.

Proposal: TODO/owner-requests.md, committed to main.

Table M - columns

| # | Column | Rule |
| --- | --- | --- |
| M1 | # | Q-ids continue from Q27; never reused or renumbered |
| M2 | Date | UTC day the owner asked |
| M3 | Request | the owner's words in double quotes; a paraphrase is marked (paraphrase) |
| M4 | Status | closed words: open, planned, in-flight, done, standing, deferred, out, withdrawn |
| M5 | Where it landed | plan file, row TITLE (never number; author-a-plan.md), table and row id; or a commit |
| M6 | Next step | one action and who takes it (owner rules, agent builds) |
| M7 | Closed by | the ruling id, commit or pull request; required for done, out and withdrawn |

Rules:
- Write-ahead: every owner message that asks for something gets its Q-id before work starts.
  An item is lost when a context cut comes between the request and the write; write-ahead closes that gap.
- At session start read the tracker first, then the plans; at session end commit it with the plans.
- Each plan's rulings table cites the Q-id it answers; each plan's Status line points to the tracker.
- The file is deleted only when every item is done, out or withdrawn, and every out item names the
  living page or plan that holds the decision (Guardrail #4, distill-a-plan.md).
- Optional check in the same commit script: every Q-id a plan cites exists; no done item lacks
  Closed by; no open item lacks a next step.

---

## 7. Decisions for the owner

Situation. The owner disapproved sites as the unit of judgment and named the ledger drift-evals.
Plan 36 is authorized and unstarted. No row of the judge or council plans has started, and
drift-evals holds no row.

Problem. The judge plan's rows, shape and key are built on sites; plan 36 would give a second
answer to every drift question; several structural choices have more than one sound answer.

Impact. Ruling now costs plan edits only. Once judge row #3 merges, every shape change is a
migration; once plan 36 starts, every duplicated alarm is code to delete later.

Table N - the judge plan's rows

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| N1 | Table C as proposed **Recommended** | 3 fewer build rows; every row tests summary quality | One plan rewrite | Per-site and per-length checks |
| N2 | Keep rows #5 to #7, re-declared at digest level | Less rewriting | Rows that test article and extraction properties the owner rejected | Focus |
| N3 | Start a new plan file | Clean text | Loses traceability of judge P1 to P19 and judge table R | History in one place |

Table O - the long baseline (row #14)

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| O1 | Move to the judge plan's Table B, brought in when one series holds 56 weeks **Recommended** | Plan can close when the judge ships; no code that reads nothing for a year | The blind spot to slow decline is stated, not closed | A row kept visible in the Reckoner |
| O2 | Keep a PENDING row gated on the data | Visible | Plan stays open about a year | - |
| O3 | Drop it | Simplest | Slow decline never has an answer | The only planned answer to it |

Table P - a diagnosis stratum on the row

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| P1 | No stratum; diagnose in the Data explorer over the published eval ledger **Recommended** | No field, no key column, no extra rows | A person writes the slice | The judge naming where |
| P2 | Optional stratum field and value, descriptive, written only for crossed checks | The panel names where | Two key columns, conditional rows | Minimal key |
| P3 | Tested rows per stratum | Most detail | Brings back per-site multiplicity | The owner's ruling |

Table Q - the series stamp column

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| Q1 | instrument, holding whichever stamp the declaration names **Recommended** | Judge B11's narrower stamps need no key rename | One more word to define | Same spelling as the eval row |
| Q2 | scorer_version | Same word as the eval row | A Level-5 key rename when judge B11 lands | - |

Table R - how a statistic is declared

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| R1 | One statistic per declaration, named by its kind **Recommended** | P13's shape and key unchanged; weights attach per (metric, statistic) | More declarations | Compact config |
| R2 | A statistics list per declaration | Compact config | statistic joins the key; weights become nested | P13's shape |

Table S - division of work with plan 36

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| S1 | The judge owns every fleet alarm and the composite; plan 36 keeps per-item actions, fluency production and rejects; plan 36 rows 1, 2, 4, 5 collapse (Tables H and I) **Recommended** | One alarm per metric; 4 fewer plan-36 rows; plan 36 stops waiting on plan 34 | Rewrite of plan 36 text; owner narrows an authorized plan | Adaptive bands drawn on the console |
| S2 | Plan 36 owns the alarms; the judge keeps only the composite | Plan 36 stays as authorized | Uncalibrated rolling floors, which follow a slow decline by construction; the judge loses its purpose | The owner's 2026-10-11 direction |
| S3 | Both keep their alarms | No rewrite | Two answers per question | Clarity |
| S4 | Merge the plans | One Reckoner | Mixes an observer with a reader-safety actor | The judge B2 boundary in plain sight |

Table T - the console home

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| T1 | The Model (Summaries) page for every summary-quality view; plan 36 Row 9 moves there **Recommended** | P5 stands; the page already reads the eval and item-health ledgers | Plan 36 Row 9 text | - |
| T2 | /console/judgement/ for every summary-quality view | Plan 36 stands | P5 changes; mixes summary quality with the merge line | P5 |

Table U - where fluency scores live

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| U1 | The fluency judge's own ledger in its own family **Recommended** | One writer per ledger; follows the council's layer rule | A new family and ledger | One table holding every score |
| U2 | A geval column on the eval row (plan 36 Row 3) | One table | A second writer into the eval ledger, next day, against immutable raw files | One writer |

Table V - drift-evals against the 2026-09-27 naming rule

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| V1 | Keep drift-evals; row #3 writes the dated exception into ledger-registry.md **Recommended** | Honors the newer ruling; the rule stays honest | One line | - |
| V2 | Rename to a what-it-holds name | Rule kept without exception | Reverses a ruling made today | The owner's choice |

Table W - council plan additions

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| W1 | Add the named-decision test and the lifecycle example to row 1; add council B5 operator range **Recommended** | Closes the uncovered lifecycle strengths | Small, in files row 1 touches | - |
| W2 | Also add retryable fault words to row 8 | Gardener parity | A contract word with no consumer | Delete-first |
| W3 | No additions | No change | Council E1.5 stays unenforced | The guard |

Table X - judge row #9's memory observation

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| X1 | Drop "peak memory"; read seconds_spent **Recommended** | No instrument needed; no decision depends on memory | - | A reading nobody needs |
| X2 | Record memory on no-model cells | A reading | A council change for one number | Delete-first |

Table Y - plan 36's rejects ledger retention

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| Y1 | A door ledger with an owner-named exception to the approved chain | Follows the born-at-door rule | Even the shortest chain keeps a row about 2 to 3 months (month end, plus at least 31 days, plus at least one month), well past the 30 days the owner set for committed source text (plan 36 J3, J4) | The 30-day bound |
| Y2 | An exception to the born-at-door rule: a day tree with a gardener retention task, as traces is ("kept a short while so an operator can open one", registry.txt) **Recommended** | Exactly 30 days, the owner's condition for committing source text | A second tree-grain ledger delays the Grain enum's removal condition | One pattern for every new ledger |
| Y3 | Defer Row 12 | No exception now | Withheld prose is lost until it lands | Troubleshooting evidence |

Table Z - the tracker home

| # | Option | Benefit | Cost | Gives up |
| --- | --- | --- | --- | --- |
| Z1 | TODO/owner-requests.md, owner requests only (section 6) **Recommended** | Survives every plan's closure; one question per table | One file to keep | Table Q inside the judge plan |
| Z2 | Keep Table Q in the judge plan | Already there | Dies when the judge plan closes; holds other plans' items | Durability |
| Z3 | A JSON file with a utility | Machine checks | A second format; code with one reader | Plain text |

Recommendation:
- N1: every surviving row tests summary quality, and three rows of machinery leave.
- O1: a row that reads nothing for a year should not hold the plan open.
- P1: the published eval ledger already answers "where".
- Q1: one cheap word now avoids a Level-5 key rename later.
- R1: it keeps the approved P13 shape and key.
- S1: one alarm per metric, and the judge's tests are calibrated where plan 36's floors are not.
- T1: P5 stands and the Model page already reads the ledgers involved.
- U1: one writer per ledger, as the council's layer rule requires.
- V1: the owner's newer ruling stands and the registry rule stays honest.
- W1: it closes the lifecycle gap the owner asked about, inside files row 1 already touches.
- X1: no decision depends on a memory reading.
- Y2: the 30-day bound was the owner's condition for committing source text, and traces already serves the same use.
- Z1: a tracker must outlive the plans it tracks.

Not this report's to rule: which metrics and statistics (Andre: the owner's words name
conciseness, which the design-of-record page does not; compression measures article length at a
fixed budget, per the brief), the floors, mix adjustment, and the composite (Q20, Q23, Q24).
Andre should also price one alternative for slow decline: comparing with the first 28 days of the
current series. It catches a slow decline from week 5, but it is a fixed point-in-time reference,
which the owner's standing rule forbids.

---

## Appendix - the table check (for the session's commit script)

```python
import re
DELIM = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$')
def cells(line):
    s = line.strip()
    parts = re.split(r'(?<!\\)\|', s)
    if s.startswith('|'):
        parts = parts[1:]
    if s.endswith('|') and not s.endswith('\\|'):
        parts = parts[:-1]
    return parts
def faults(text):
    out, lines, i, fence = [], text.split('\n'), 0, False
    while i < len(lines):
        if lines[i].strip().startswith('```'):
            fence = not fence; i += 1; continue
        if fence or not lines[i].lstrip().startswith('|'):
            i += 1; continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith('|'):
            j += 1
        block, n = lines[i:j], len(cells(lines[i]))
        if len(block) < 2 or not DELIM.match(block[1]) or len(cells(block[1])) != n:
            out.append((i + 1, 'delimiter does not match header'))
        for k, row in enumerate(block[2:], start=i + 3):
            if len(cells(row)) != n:
                out.append((k, 'row has %d cells, header %d' % (len(cells(row)), n)))
        for k, row in enumerate(block, start=i + 1):
            if any(re.search(r'(?<!\\)\|', m) for m in re.findall(r'`([^`]*)`', row)):
                out.append((k, 'unescaped pipe in a code span'))
        i = j
    return out
```
