# Summary-fidelity judge: the hard look at plan 65 (proposals, 2026-10-12)

**Last Updated**: 2026-10-12

**Proposals only; nothing here is ruled.** Plan 65 (TODO/20261011-65-summary-fidelity-judge-plan.md) holds every ruling. Plan 65.2 takes a change from this record only after the owner rules on it (plan 65, Table Q, Q57).

How the review was asked, so its cuts can be read fairly. Two reviewers - Fowler (architecture, contracts, process safety) and Andre (model quality and evaluation) - were given a lean copy of plan 65 (plan 65.1, withdrawn by the owner on 2026-10-12 and kept in git history), the ground truth in section 4, and a brief that said the owner suspected over-engineering, asked them to sort each part into substance, over-engineering or ceremony, and let them recommend reversing a ruling. The brief did not say which parts the owner calls core - automatic tuning, charts, the second checker, automation first - and it did not carry the owner's intent of 2026-10-12 (plan 65, Table Q, Q58). They then settled the points they disagreed on in one debate (section 3).

Row numbers are plan 65's. Table and row ids are local to each section.

## 1. Fowler - hard look at plan 65.1

Table A - verdict per row

| # | Row | Verdict | What changes | What is lost, and what would bring it back |
| --- | --- | --- | --- | --- |
| A1 | #1 Delete drift review | KEEP | As drafted | The weekly per-site report (rated useless) and its per-source length check; nothing brings it back (C2) |
| A2 | #3 drift-evals, tenant | KEEP | The one new stored record kept; shape per B1 | - |
| A3 | #4 Settings, declarations | KEEP | Ten members at landing earn the registry (P13); fields per B2 | - |
| A4 | #7 Values, mix adjustment | KEEP | The #1270 fix; its length bands sit on the scorer's window edges (RC8), so it also removes the long-article mark-down (0.22 at 2 windows, 0.40 at 3) from the judge; B3 | - |
| A5 | #15 Whole-day test | SIMPLIFY; reverses P4 | One setting, reshuffles 9,999 (whole-day deals a night), replaces the stop rule and cap (B4) | Nothing |
| A6 | #8 Step and replay | KEEP | Faults: RD4's four, not one per member (M1.7); no engine shared with cut rows (M1.6). Built first | - |
| A7 | #9 Switch | KEEP | Also puts drift-evals in ledger.published (from #12) for the data explorer | - |
| A8 | #12 Judge panel | DEFER until an alarm issue proves too thin; reverses QQ14 | Saves six hand-copied closed sets and their contract tests | A crossings view; the issue (#34) and the data explorer carry it |
| A9 | #13 Combined score | SIMPLIFY; reverses QQ8 (levels only) | Fixed weights (QQ9 start: faithfulness 1 each, numbers 3, hedges 2) and rho from #8's replay, in config. reading_levels.py shrinks to the one rule #34 acts on | Watch and evaluator-check labels. Back with #12 |
| A10 | #14 Anchor | DEFER until a slow decline is suspected; reverses QQ18 | Without #42's restarts a frozen anchor crosses for ever after the first harmful change; with #33 cut nothing promotes it | A slow-decline check; the record shows none (RD5). Back: one comparison module through #4's seam, with a reset rule |
| A11 | #42 Series boundaries | SIMPLIFY; reverses QQ19 | Keep recorded_changes.py for inputs_changed; restart only on a new model or instrument (P14); cut series.py, expected_shifts, new_series. Changes land about every 9 days (RD5) and each undeclared one blinds every member 14 nights. The replay with 09-07 and 09-24 as restarts (l15_replay.txt) tested 8 of 31 nights and crossed none: RD1 and RD2 vanish | An accepted trade-off reads as drift up to 35 days (P35); its issue closes itself |
| A12 | #18 Eval-row stamp | KEEP | As drafted (expand-only, defaults) | - |
| A13 | #22 Record-only stamps | KEEP | As drafted; the owner reads its record-only weeks before listing a line (A15, C1) | - |
| A14 | #27 Withheld kept, fence | SIMPLIFY; reverses QQ13 in part | Keep the corpus fence. Keep no withheld text: nothing left reads an entry (O5.4) | The withheld summary's text; its scores and stamp stay. Back with #29 |
| A15 | #23 Gate withholds | SIMPLIFY; reverses QQ12 (self-switching) | One list, evaluation.publish_gate.withholding_lines (empty: record-only), replaces withhold_failing_summaries and the agreement guard (A25) with its three settings. The breaker stays: a date with over 0.25 of summaries marked (withhold_share_ceiling) makes the next run record-only. The switch record keeps only state and reason (O3.4, O3.6 go) | Self-switching. A line is listed once, not regularly; then the breaker and numbers_unsupported watch the mark rate |
| A16 | #24 Gate panel | DEFER until a line withholds; reverses QQ14 | Not built | Daily shares by reason: one data explorer query on the published summary-quality-evals |
| A17 | #28 Shared judge guards | DEFER until a new model judge lands; reverses QQ25 | One judge would remain; one caller earns no shared module, and no failure is on record | Thinking-off canary and in-position tokens for the similarity judge. Back with the next model judge; shared at the third |
| A18 | #29 Kept article text | DEFER with #30, #35; reverses QQ4, QQ30 | Nothing left reads it; spares a second section 0a article-text exception | 30 articles a day for 31 days. Back with the first night judge that reads them |
| A19 | #30 Completeness judge | DEFER until a judge from another model family fits the council; reverses QQ4 | Fluency was dropped because a model favours its own text (RE5), yet this grades completeness with the same model; the method reached only 0.571 correlation with people with GPT-4 listing facts; 30 a day, paused at weight 0 | Completeness and conciseness unmeasured; they could not alarm for 4 to 8 weeks anyway |
| A20 | #31 Planted omissions | CUT; reverses QQ4 (pilot) | It feeds #33's promotion; a returning #30 carries its planted test in its oracle | Nightly omission checks; back with #30 |
| A21 | #32 Auto-tuning | CUT; reverses QQ27 | A night takes the latest applied tuning row and never writes the settings file (X4.6), so editing config stops changing a weight (Guardrail #6's substitution test). Remove Middle Man. Weights move detection, never the false rate (P17) | Re-tuning every 28 days. Back: weights and rho stay config, set from #8's replay by the row that adds a member |
| A22 | #33 Auto-promotion | CUT; reverses QQ28 | Same split source of truth, for status (X5.6), and nothing to promote: #8's base rates settle RA6, RA7; the rest wait | Promotion with no edit. Back: status is config, set after #8's replay by the row adding a member |
| A23 | #34 Alarm responses | SIMPLIFY; reverses QQ29 (larger sample) | The issue and auto_respond_to_drift stay (B5). The larger key-fact sample (H3.30, RC21) goes: it acts on nothing until key-fact members exist, and it makes the digest read the judge's output | - |
| A24 | #40 Pin checker model | DEFER with #35; reverses QQ16 | 4.94 GB beside the 5.68 GB summarizer passes the 10 GB cache, so it downloads nightly; served_model and a checker slot reshape the council for one judge | See A25 |
| A25 | #35 Grounding judge | DEFER until a checker clears the gate's line on news; reverses QQ16 | Its consumer, #23's guard, is blind: one unsupported sentence confirms a summary (X7.8); at 0.669 balanced accuracy on news about one call in three is wrong, so a faithful 3-sentence summary is confirmed about 70 percent of the time (1 - 0.67^3, estimate): the guard's own line | A second opinion on 8 summaries a night; the disagreement chart |
| A26 | #36 Measure sentence cost | KEEP | Its number (35 to 40 against 12.5 scorer-minutes a day) decides whether #37 fits the shards | - |
| A27 | #37 Eval-row change | SIMPLIFY; reverses QQ15 in part | Append sentence_faithfulness_mean, sentence_faithfulness_min, faithfulness_instrument. Drop the hhem rename: structure mixed into behaviour, and RENAMED_CELLS would read old names for the ledger's 36 months. Drop the name and date checks: unmeasured, paused, no failure on record. B6 | A scorer-neutral name; name and date checks. Back: each its own change when a reader needs it |
| A28 | #38 Switchover | DEFER until #37 holds 63 valid days (a baseline and a week); reverses QQ15 in part | #7 already takes the long-article mark-down out of the judge; replaces, auto-retire and QQ31's inheritance go with #33 | Per-sentence members. Back: one config commit swaps RA1-RA3 for RA16-RA18 with #8's replay numbers |
| A29 | #39 Gate sentence line | KEEP | Stamps and fences from landing; withholds only once listed in withholding_lines (A15) | - |
| A30 | #41 Failures by source | DEFER until the feed-quality plan's judge exists; reverses QQ32 | TODO/ holds no such plan; the counts derive from summary-quality-evals joined to item-health, #7's join; they would not have seen extraction break (RD6) | Per-source history before that judge's first night |

Table B - ceremony inside rows that stay

| # | Row | What to strip | Why it is ceremony |
| --- | --- | --- | --- |
| B1 | #3 DriftEval | The eight settings copied onto every row (H3.6, H3.17) and check_definition (H3.22); with their rows, tuning_version, series_started_by, keyfact_sample_multiplier and outcome new_series; reverses QQ10 in part | settings_digest (H3.28) names the settings file and the envelope carries git_sha; no kept row reads them; a slug never changes meaning (G1.4), so check_definition repeats its declaration |
| B2 | #4 MemberDeclaration | transform, tuning_pinned, replaces, and their refusals | Statistic logit_mean already says logit; the other two serve only #32, #33, #38 |
| B3 | #7, Table RA | RA12's shown rows; RA11 scored_nulls and the evaluator-check level; reverses QQ2 in part | RA12 stores nightly, with a p-value nothing acts on, what the data explorer reads from summary-quality-evals and item-health (both published). RA11 guards a failure not on record: an unloaded faithfulness scorer writes no row, so the day reads thin |
| B4 | #15 | reshuffle_stop_hits, reshuffle_cap_floor, reshuffle_cap_multiple, reshuffle_hits | Sized for hundreds of per-site checks (P4). A family now tests about 10 rows: its smallest step line, 0.05/10 = 0.005, is 50 times the 0.0001 that 9,999 deals reach, in under a second (estimate) |
| B5 | #34 | The GitHub client in the judge's package (injected transport, recorded responses); issues: write on save_council_results | Separate Query from Modifier: settle files the alarm; a later job with issues: write runs gh on a body file from a fixed template. No hand-rolled HTTP client (Guardrail #8); the job running every judge's settle gains no permission |
| B6 | #37 | sentences_under_050/080 (Y7.6), sentence_winning_windows (Y7.7), metrics_version (Y7.11), coherence_instrument (Y7.12), the faithfulness_scorer block | No kept row reads them; the scorer move to config is a tidy with no next change behind it |

Table C - missing

| # | What | Why | Smallest row that does it |
| --- | --- | --- | --- |
| C1 | False marks of the number check | The first line that may withhold; precision unmeasured. _checkable_numbers (evals/metrics.py) only strips commas and trailing zeros, so "1.5 million" against "1,500,000", or "about 1,300" against "1,320", reads unsupported | Before #9 (a fix moves METRICS_VERSION): a unit test over those spellings, each fixed or accepted by name; the owner reads the record-only marks once before listing the line |
| C2 | A source whose extraction breaks | RD6: no summary metric sees it, and extraction_suspect read 0 on all 50 days; #1 deletes the only per-source check; TODO/ has no feed-quality plan | A fixture test that extraction_suspect fires on a known page-furniture extraction (if it cannot, "0 on 50 days" proves nothing), and a TODO entry handing the gap to the feed-quality plan (QQ17) |
| C3 | The published band reads the biased score | The band (high from 0.80, medium from 0.50) reads the whole-summary score, 0.22 low at 2 windows and 0.40 at 3, so faithful long-article summaries show a lower band. QA4 keeps it: two scores run for ever, 48 to 53 scorer-minutes a day against 12.5 now | After #37, one row moves the band to the per-sentence score (a reader-facing ruling; the model-quality reviewer picks the statistic); with #38 the old score retires |

Bottom line

1. Judge: #1, #3, #4, #7, #15, #8, #9, then #42 (labels only), #13 (fixed weights), #34 (issue only).
2. Gate: #18, #22, #27 (fence only), #23 (withholding_lines plus the ceiling breaker); C1 before any line is listed.
3. Faithfulness: #36, #37 (three columns), #39; C3 for the band.
4. 17 of 30 rows; 1 of 6 new stored records; 1 of 3 new judges; no new served model, no new article-text exception, no ledger overriding config.
5. Deferred with triggers: #12, #14, #24, #28, #29, #30, #35, #38, #40, #41. Cut: #31, #32, #33.
6. Build first: the computing core (#7, #15, #8's step) with the replay utility as its first caller, on real eval rows, before #3 persists a shape. Table RD came from daily aggregates with stand-ins (simulated items, band-reason shares, a 28-day baseline, the replaced two-row composite, per the replay's README): this is the design's first real run.

## 2. Andre - hard look at plan 65.1

Table A - verdict per row

| # | Row | Verdict | What changes | What is lost, and what would bring it back |
| --- | --- | --- | --- | --- |
| A1 | #1 drift review deleted | KEEP | Its one finding on record, #1270, was a false alarm (B7). | - |
| A2 | #3 ledger and tenant | SIMPLIFY | Ledger, tenant and paused registration stay; DriftEval loses B1 and B2. | Per-row copies of settings; settings_digest still names them. |
| A3 | #4 settings and members | SIMPLIFY | A member declares column, statistic, line, transform, direction, adjust_by, role, rho, status; B4 goes. | Fields that serve cut rows. |
| A4 | #7 values, mix adjustment | KEEP | Length is a measured confound (2- and 3-window articles score 0.22 and 0.40 lower, Y9.6); source mix moved (08-27 added 31 sources, 17.8 percent of the next week). | - |
| A5 | #15 whole-day test | SIMPLIFY | A fixed 20,000 deals a night; rho fixed per member from #8's pooled lag-1 (0.28 for faith_below_080, at most 0.12 elsewhere). Whole days stay: r3's day spread ran 1.4 to 3.4 times binomial. Recency weights stay: they read 09-07 two nights sooner (SP6). | The three reshuffle stop settings (F1.6 to F1.8): adaptive stopping saves milliseconds (estimate). |
| A6 | #8 false-discovery step, replay | KEEP | Oracle gains C2; crossings_budget goes (B3). RD1 to RD4 came from day-record stand-ins, a 28-day baseline, series split at the model switch only and a dropped composite (review record section 9, SP6). | - |
| A7 | #9 switch | KEEP | Waits for C2, not the reading budget. | - |
| A8 | #12 checks on Summaries page | SIMPLIFY (reverses QQ14) | Only ledger.published gains drift-evals; the Data explorer is already the first view (T1.1). | The panel, which the draft cannot say is read. Bring back when an alarm issue plus the explorer leave what moved unclear. |
| A9 | #13 combined score, levels | MERGE into #34 (reverses QQ8, QQ9, QQ31) | The level rule (a judged member crossing 2 nights running) moves to #34; combined_score, combine_weight and the correlation matrix go. | Detection of a uniform slip of every member falls 0.685 -> 0.630 at 0.5 day-SD, 0.958 -> 0.932 at 0.75, SE 0.02 ("not where detection comes from", review record 5.7). Bring back: a recorded slip no member crossed. |
| A10 | #14 anchor | DEFER until a series holds 120 valid days on one instrument (reverses QQ18) | - | Needs 63 valid days of one series plus 28 to promote; under the drafted restarts it never runs, and before day 120 it overlaps the trailing baseline. Guards a slow decline nobody has seen (RD5). |
| A11 | #42 series boundaries | SIMPLIFY (reverses QQ19; narrows QQ1) | A member restarts only when its own instrument stamp moves; model, prompt, quantisation and runtime changes fill inputs_changed, never restart. An undeclared change blinds every member 14 nights, changes came every 9 days, a model change always restarts (Y6.2), and every crossing on record came from such a change (RD5): as drafted the judge rarely judges and never compares a new model with the old. | An accepted quality drop keeps the issue open until the baseline absorbs it (5 to 7 weeks, estimate). |
| A12 | #18 eval-row stamp | KEEP | The stamp is the record-only measurement and the fence's input. | - |
| A13 | #22 record-only stamping | KEEP | Drop RA13 (B6). 1.7 percent of summaries, about 5.6 a day, carry an unsupported number; none was ever held back (A1). | - |
| A14 | #27 withheld text, fence | SIMPLIFY (reverses QQ13 A1) | Fence only, from the stamp. The judge still reads every scored row (O1.1), so the selector never blinds the alarm. | The withheld-text store and a second section 0a exception; nothing reads it (O5.4). Bring back: a week of record-only, read on the site. |
| A15 | #23 gate goes live | SIMPLIFY (reverses QQ12's agreement guard) | A line goes live when a per-line setting names it, set once after its C3 read; withhold_share_ceiling still returns all lines to record-only; withhold_failing_summaries stays the off switch; no wait for #35. | Self-switching on; replaced by one decision per line in the plan's life, not a regular step. |
| A16 | #24 gate panel | DEFER until a line is live (reverses QQ14) | - | The panel; stamps and the switch record stay queryable. |
| A17 | #28 judge guards | SIMPLIFY | Content-similarity judge only: thinking off asserted by a canary (a reasoning span would sit where its first-token answer is read), no trailing space, answer ids built in position. | The planted-instruction canary: no article-reading judge remains; returns with one. |
| A18 | #29 sampled article text | CUT (reverses QQ30; QQ4 in part) | - | 30 articles a day of committed text; both readers (#30, #35) go. |
| A19 | #30 key-fact judge | CUT (reverses QQ4; its drop of fluency stays) | - | Completeness and conciseness. The method tracked people at 0.571 correlation even with GPT-4 listing facts; here the writer grades itself, and the judge changes with every summarizer swap (X2.6), so it never compares across one. Bring back: a pinned independent judge, read as a paired before/after at a change. |
| A20 | #31 planted omissions | CUT | - | Goes with #30; it tests the fault it plants, not real omission (its own Cannot settle). |
| A21 | #32 automatic tuning | CUT (reverses QQ27) | - | No weights left; they were tuned and scored on the plan's own fault library (eval contamination), gains inside noise (SE 0.02). Rho from 9-day quiet stretches has SE about 0.3 (review record 5.2). Replaced by fixed rho (A5). |
| A22 | #33 automatic promotion | CUT (reverses QQ28) | - | Runtime promotion. Replaced by: a member joins active by a config commit whose pull request records #8's replay passing both tests (reshuffled false-alarm rate <= q; own planted fault caught >= 0.8). |
| A23 | #34 alarm response | SIMPLIFY (reverses QQ29 in part) | The self-closing issue stays: the only path from a crossing to a person. Stored rows are the diagnosis; B8 goes. | The doubled key-fact sample: no key-fact judge. |
| A24 | #40 pin Granite Guardian | CUT (reverses QQ16) | - | Serves only #35: a 4.94 GB fetch every night, never cached, plus model-serving plumbing. |
| A25 | #35 grounding judge | CUT (reverses QQ16) | - | Its guard cannot read the gate's precision. Agreement = precision x catch rate + (1 - precision) x false-confirm rate, and nothing measures false confirms: planted variants measure catches only, and the 6 real checks a night go to marked summaries first. If its per-sentence error matches its news score (0.669), a summary of 3 faithful sentences is confirmed 70 percent of the time (any sentence counts, X7.8): the 0.7 line passes about half the time on marks that are all wrong (SE 0.08 at 30 checks). Bring back: check only the flagged sentence, with blind unmarked controls. |
| A26 | #36 per-sentence cost | KEEP | Its report adds C4. | - |
| A27 | #37 eval-row change | SIMPLIFY | Only sentence_faithfulness_mean and _min, sentences_under_050/080 and faithfulness_instrument (B10), built only if #36's flag rates and minutes allow. Both scores run for good (QA4): about 48 to 53 scorer-minutes a day against 12.5 (estimate). | Name and date checks: unmeasured lexical checks that withhold nothing and feed only paused members. Bring back with a C3 read. |
| A28 | #38 switchover | CUT (reverses QQ15 C1, QQ31) | - | Drift members stay on the whole-summary score, which #7's length bands already compare like with like: no 14-night restart, no 4 to 8 weeks of paired members, no inherited weights. Bring back: a replay where per-sentence members catch a planted fault the others miss. |
| A29 | #39 per-sentence gate line | SIMPLIFY | Stamps record-only once #37 lands; goes live as #23 does, after its own C3 read; no wait for #35. | - |
| A30 | #41 failures by source | DEFER until the feed-quality plan's judge asks for a shape (reverses QQ32) | - | About 2 summaries a source a day (327 over 158 active sources), so nightly counts of a 1.7 percent failure are almost all zero; the eval ledger (36 months) and item-health hold every input. |

Table B - ceremony inside rows that stay

| # | Row | What to strip | Why it is ceremony |
| --- | --- | --- | --- |
| B1 | #3 | H3.6 and H3.17: window and test settings on every row | settings_digest (H3.28) names the file in force; git holds it (Guardrail #10). |
| B2 | #3 | H3.18, H3.20 to H3.24, H3.26, H3.27, H3.30 | Derivable from the declaration at settings_digest, fixed by A5, or written for cut rows. |
| B3 | #4, #8, #9 | crossings_budget (F1.12) and C5's reading-budget gate | At about 10 checks a night it is "probably never binding" (review record); the reshuffled false-alarm rate is the real gate. |
| B4 | #4 | combine_weight, replaces, tuning_pinned, per-member min_day_rows, the comparison list | Serve #13, #14, #31 to #33 and #38. |
| B5 | #7 | p-values on RA12's shown rows | An uncorrected p beside corrected q invites a reading no rule acts on; keep the values. |
| B6 | #22 | RA13 withheld_share | Watched, never raised, and repeats #23's ceiling. |
| B7 | #23 | gate_trial_days, gate_min_agreement, gate_min_checks, the agreement readings in Table O3 | Leave with the agreement guard. |
| B8 | #34 | drift_sample_multiplier, keyfact_sample_multiplier, the keep stage reading the council's stamp | Feed the cut key-fact judge. |
| B9 | #42 | expected_shifts (RC33), its refusals (Y6.7), the straddling-day split (Y6.8), the three author-instruction docs | Serve restarts on pipeline changes; they also let a change's author pick which members its change can alarm (Goodharting the alarm). |
| B10 | #37 | hhem -> summary_faithfulness renames, RENAMED_CELLS, sentence_winning_windows, coherence_instrument, unsupported_names, unsupported_dates | A rename changes no number; the rest lose their readers with their members and panels. |

Table C - missing

| # | What | Why | Smallest row that does it |
| --- | --- | --- | --- |
| C1 | A regression alarm across a model or prompt change | Every crossing on record came from a dated change (RD5), yet with the drafted restarts no row compares new with old | #42 as A11 simplifies it; no new row |
| C2 | The judge's own eval on its only labelled positives | 09-07 and 09-24 (RD1, RD2) are the only real events; #9 checks only a reading budget; baseline_days 56 was never replayed | #8: on item-level eval rows, at baseline_days 28 and 56, the as-built rule crosses within 4 nights of 09-07 (copying) and 09-24 (length), and on reshuffled no-change nights no more than RD3's 2.4 percent; otherwise stop before #9 |
| C3 | Precision of each withholding line | Unmeasured (ground truth); the agreement guard cannot measure it (A25) | #23 and #39: once per line, read 50 record-only flags on the site against their source pages (about an hour, estimate; precision to within 0.11 to 0.14); false-flag classes become number-normaliser fixes in backend/idhazh/evals/metrics.py |
| C4 | Flag rates before a faithfulness line | Y9.6 measured a mean bias, not how many summaries a line flags; a lowest-of-k score flags summaries with more sentences more often | #36's report: share under 0.50, whole and lowest sentence, by article windows and summary sentence count |
| C5 | Proof extraction_suspect can fire | It read 0 on all 50 days (RD6), and #7 drops flagged rows on its word | A planted broken-page fixture in the extractor's tests; feed-quality plan (QQ17) |

Bottom line

1. Judge: #4 -> #7 -> #15 -> #8 (with C2) -> #3 -> #1 -> #9 -> #42 -> #34 (with #13's level rule) -> #12 (published line only).
2. Gate: #18 -> #22 -> #27 (fence) -> #23 (ceiling guard, one C3 read per line).
3. Faithfulness: #36 (with C4) -> #37 (columns only) -> #39. Plus #28 for the content-similarity judge.
4. Out: #13's score, #14, #24, #29 to #33, #35, #38, #40, #41.
5. Build first: #8's replay of the as-built rule on item-level eval rows. The drafted design was never measured (A6); only C2 shows whether #42's restarts hide the two real events.

## 3. Fowler and Andre - converged proposals, not owner rulings

Table A - rulings

| # | Point | Converged proposal (exact: names the fields, settings and rows) | Who conceded what, and why (one line, from evidence) |
| --- | --- | --- | --- |
| D1 | Row #13: the combined score | Cut row #13 (reverses QQ8, QQ9): no combined_score.py, reading_levels.py, combined_score row, combine_weight, correlation matrix, multi-member planted faults or Table RA weight column; rows #8 and #15 drop their combined-score clauses. #34's quality_alarm.py holds the one rule: an active judged member crossed on drift_consecutive_nights (RC6, 2; moves to #34's files) consecutive nights; watched members are stored, never raised; #34 depends on #9. Back on a recorded broad slip that no member crossed | Fowler: review record 5.7 put the signed score at +0.055 catch rate with every axis 0.5 day-SD worse (0.630 -> 0.685), +0.026 at 0.75, -0.008 on one unfaithful source, standard error 0.02 a cell ("not where detection comes from"); the drift decision the owner asked for (Q16) survives as #34's rule |
| D2 | Row #42: does a new model restart? | No (reverses P14's model clause in Y6.2 and QQ19 in part; QQ1's per-model series becomes a recorded model_id). Only a move in a member's own instrument stamp restarts it; windows.py keeps that member's days on its current stamp; series.py is not built. A new model_id or model_sha256 is named in inputs_changed (H3.29) like any change. H3.8 model_id: the model of the night's newest run. Row #8's family: one per (run_id, date). Cost: a kept model trade-off crosses until the 56-day baseline absorbs it (up to about 7 weeks for a large shift, estimate), then its issue closes itself | Fowler: the one model switch on record (08-27, review record 5.3) left 13 nights blind, and its cross-model read (copying 0.088 -> 0.108, 102 -> 77 words, HHEM p25 0.76 -> 0.80, better) lands on watched members; H2.4 retired the old-vs-new row, so a restart compares nothing; every crossing traces to a dated change (RD5) |
| D3 | Row #28: judge guards | Keep for the content-similarity judge only, no shared module (reverses QQ25 in part): backend/idhazh/llm/server.py (judge requests carry thinking off); backend/idhazh/similarity/judge.py (read_once refuses a prompt ending in a space before the call, and records a completion with a reasoning span as not a verdict); backend/idhazh/similarity/prompt.py (first_token_openings in position); its tests on recorded fixtures; docs/architecture/summarize/model-boundary.md. Out: judge_guards.py, O6.6's planted-instruction canary, the trust-boundary.md edit. Depends on nothing; a shared module waits for a third model judge | Fowler: the fault is silent by construction (the verdict shifts "and the output still parses", plan 36 row #13), so "no failure on record" proves nothing, and model-output requirements are Andre's; Andre: one caller earns no module, and no judge reads article text |
| D4 | Row #37: eval-row fields | Append only sentence_faithfulness_mean (Y7.4), sentence_faithfulness_min (Y7.5), faithfulness_instrument (Y7.10). Keep the faithfulness_scorer block (Y2.5). Drop the renames (Y7.1 to Y7.3, RENAMED_CELLS), Y7.6 to Y7.9, Y7.11, Y7.12 (reverses QQ15 B1 in part); METRICS_VERSION stays 4. From #37, RA1 to RA3 take faithfulness_instrument as instrument (reverses Y2.10, QA11): one 14-night restart, then a METRICS_VERSION or band move no longer restarts them and a scorer-library upgrade does (B10). RA4 to RA10 take scorer_version's metrics- part from landing (narrows G1.7), read by one function beside metrics.scorer_version() (review record 3) | Fowler: the owner asked for a replaceable scorer (Q15, P38) and CLAUDE.md section 10 puts model references in config; Andre: research record 4.2 offers "the minimum, or the count" as one gate (min < 0.50 iff sentences_under_050 >= 1), no kept row reads the count, #36's report counts without a column; both: metrics_version is scorer_version's metrics- part, and with #38 out RA1 to RA3 never retire, so QA11's reason lapses |
| D5 | Row #7, Table RA: RA11, RA12 | Drop RA11 scored_nulls, RA12 (values and p-values), roles evaluator and shown (Role: judged, watched), the evaluator level and RC10 trailing_line_quantile (reverses QQ2 in part). daily_values.py makes member values only; windows.py leaves a null cell out, counting nothing; extraction_suspect rows still leave judged members (G1.10); row #3's contract refuses a paused row with a q_value | Andre: no kept reader (#12 deferred; #34's issue prints crossed members, X6.2); raw and adjusted effects carry the mix; summary-quality-evals is in ledger.published (review record A2); the evaluator role was built for checker disagreement and parse rate (review record I3, I4), gone with #30 and #35; an unloaded scorer writes no eval row (O2.9) |
| D6 | Row #4: member fields | MemberDeclaration: slug, lifecycle_status, role, column, statistic, line, harm_direction, adjust_by, instrument, rho. Drop transform (Transform and its G1.3 refusal), combine_weight (with D1, and the combined_score and weight refusals), replaces, tuning_pinned, per-member min_day_rows (RC4's clause), comparisons (Comparison; trailing only) | Andre: logit_mean already carries the only transform any member uses, fixed per slug (G1.4); Fowler: combine_weight goes with D1, and one-value comparisons and the key-fact day minimum serve cut rows (#14, #30); #14's return re-adds comparisons, defaulting to trailing |
| D7 | Row #3: DriftEval fields | Drop H3.6, H3.17, H3.18, H3.20 to H3.24, H3.26, H3.27, H3.30, and new_series from H3.19, which keeps threshold_crossed, threshold_not_crossed, too_few_days, paused (reverses QQ10 in part). H4.5 key: run_id, date, check_name, model_id, instrument. With D1, D5: H3.9 loses combined_score; H3.11 is judged or watched; H3.12, H3.14, H3.25 lose combined clauses; the contract checks outcome against p_value and q_value | Fowler: G1.4 (a slug never changes meaning) covers statistic and value_unit as it did check_definition; reshuffles is a setting and hits follow from p_value; rho is config; z_value fed only the combined score; one comparison. Andre: with D2 only an instrument move restarts, and too_few_days plus instrument say what new_series said |
| D8 | New row: band on the per-sentence score | Owner decides (B1): the band is what readers see. Converged shape: row #43 after #37; score.verdict's faithfulness band reads sentence_faithfulness_min at unchanged cuts (high from 0.80, medium from 0.50), so band and #39's line read one number; hhem keeps running for RA1 to RA3 until #38 returns | Andre: #7's adjustment never reaches the band, so keeping both scores for good (QA4) keeps the 0.22 and 0.40 long-article mark-down in front of readers; Fowler: nothing retires inside 65.1, so the row moves only the band; the min is Andre's pick, the research's per-summary gate (4.2) |

Table B - points that stay open for the owner

| # | Point | Option 1 | Option 2 | Recommended |
| --- | --- | --- | --- | --- |
| B1 | D8: which score the published band reads | Band stays on hhem (QA4): no published change; faithful summaries of 2- and 3-window articles keep a band read 0.22 and 0.40 low; both scores run for good (48 to 53 scorer-minutes a day against 12.5 today, estimate) | Row #43 (Level 5): the band reads sentence_faithfulness_min at 0.80 and 0.50 from its merge; past days unchanged; both scores still run until #38 returns | Option 2, if #36's day shows the share whose lowest sentence is under 0.50 flat, within binomial noise, across article windows (1, 2, 3+) and summary sentence counts; otherwise Option 1 |

## 4. The ground truth the reviewers were given

Facts only. Each names where it comes from. Plan 65 is TODO/20261011-65-summary-fidelity-judge-plan.md.

### The project

- yen-idhazh is a daily news digest built on GitHub Actions. Each day the digest run fetches articles, summarizes each with a local open-weights model (Qwen 3.5 9B, Q4_K_M, 5.68 GB, served by a pinned llama.cpp build on 16 GB stock runners), scores each summary, and publishes a static site.
- Each summary gets an eval row (the eval ledger, kept 36 months): faithfulness from the HHEM scorer (column hhem, 0 to 1: the whole summary against its best window of the article text the model saw), counterweights (compression, extractiveness, verbatim_run, unsupported_numbers, hedge_dropped, self_repetition, densities, semantic_coverage, extraction_suspect) and coherence (scored every day since 2026-09-24). The published band reads hhem: high from 0.80, medium from 0.50. A summary that copies too much is already refused (verbatim_reject_ceiling 0.75).
- A nightly workflow, the LLM council, runs judges over committed records. One judge runs today (content-similarity-judge). Judges register by config: config/llm_council.json lists judge_names; each judge has config/judges/<slug>.json with lifecycle_status and runs_model. 4 shards a night, 200 minutes each. The council serves one model, the summarizer's. The Actions cache allows 10 GB.
- One owner. Code is written by autonomous agents from plans. The owner's driving principle (plan 65, A7): little to no regular human step; every automatic step bounded, recorded, with an off switch.

### Why plan 65 exists

- The weekly drift review (drift.py, its own workflow) compared per-site medians to fixed percentage thresholds. In issue #1270 a site's change in mix of story types moved a median between two page kinds and read as drift. It ignored sample size, and its results lived only in a GitHub issue. The owner rated its output useless (plan 65, B7).
- Plan 65 absorbed plan 36 (fitted floors per metric, a self-graded fluency judge, a publish gate), then took 32 owner rulings (plan 65 Table QQ). It has 42 rows: 12 collapsed, 30 pending. Nothing of it is built.

### What the data says

- About 327 scored summaries a day (2026-09-24 to 2026-10-10).
- Faithfulness under 0.50: 5.6 percent of summaries in that period; 11.7 percent in an earlier period (late August, plan 65 RC27). At least one unsupported number: 1.7 percent.
- The whole-summary score marks long articles down: a summary of a 2-window article scores 0.22 lower, and of a 3-window article 0.40 lower, than the same summary read against the article whole (plan 65, Y9.6). So a faithfulness line on today's score would hold back faithful summaries of long articles.
- Replay of the proposed judge on 50 days of the real record (plan 65, Table RD):
  - RD1: a 2026-09-07 change read as watch from 09-09 (more copying) and drift from 09-12; faithfulness rose because summaries copied more.
  - RD2: a 2026-09-24 change read as drift from 09-26 (shorter summaries, more dropped hedges; part of the hedge rise was an artefact).
  - RD3: stable nights, 0 of 8 crossed; with no change, 2.4 percent of nights cross a row, and drift is read 0.10 times a month at q 0.05.
  - RD4: detection over a full week: 5 percent of summaries unfaithful, 1.00; 2 percent, 0.72; one 10-a-day source unfaithful, 0.95; unsupported numbers doubled, 0.74; dropped hedges up 3 points, 0.29.
  - RD5: the pipeline changed about every 9 days (all dated changes), and every crossing on record traces to a dated change.
  - RD6: no summary metric sees extraction breaking on one source; extraction_suspect was 0 on all 50 days.
- Arithmetic from plan 65's own settings: after a series restarts, the first night that can be judged is about 14 nights later (the baseline ends 8 days back and needs 7 valid days; row #42, Y6.4). A per-sentence member needs 28 usable days before promotion (RC18), so it judges 4 to 8 weeks after it lands.

### What the model judges cost and how good they are

- HHEM today: about 12.5 scorer-minutes a day. Per-sentence scoring: an estimate of 35 to 40 minutes a day, 48 to 53 while both run (row #36 measures it).
- Completeness from key facts (FineSurE's method): tracked people at 0.571 Pearson even with GPT-4 listing the facts. Plan 65 runs it with the summarizer's own 9B model judging its own summaries, 30 a day.
- Granite Guardian 3.3 8B (the second faithfulness checker): 0.761 balanced accuracy on the LLM-AggreFact average, 0.669 on its news subset (AggreFact-CNN), no-think mode; 4.94 GB, so it and the summarizer together pass the 10 GB cache. 8 checks a night, 40 minutes.
- Unsupported numbers are a lexical check (a number in the summary that the full article does not state). Its precision has not been measured.

### The owner's rulings, one line each (plan 65 Table QQ has the full text)

QQ1 judge the whole digest per model series, length and source only adjust. QQ2 judged: faithfulness (mean, shares under 0.50 and 0.80), unsupported numbers, dropped hedges; copying and length watched. QQ3 the nightly test replaces fitted floors. QQ4 a sampled key-fact check (completeness, conciseness) replaces self-graded fluency; keep sampled article text. QQ5 recency-weighted week against a baseline, whole days reshuffled, every number configurable. QQ6 56-day baseline ending 8 days back. QQ7 false-discovery rate 0.05. QQ8 one signed, correlation-adjusted combined score. QQ9 weights from reader harm, tuned on planted faults. QQ10 the drift-evals row shape. QQ11 names. QQ12 publish gate: record-only first, withholds by itself once an independent check agrees with 0.7 of its marks over 28 days, back to record-only when a guard fails; unsupported numbers may withhold from the start, faithfulness only on the per-sentence score. QQ13 withheld text kept, corpus fence reads the stamp. QQ14 panels on the Summaries page. QQ15 per-sentence faithfulness, name and date checks, per-column stamps, replaceable scorer, inside plan 65. QQ16 second checker at night, Granite Guardian, 8 a night, 40 minutes. QQ17 per-source extraction health belongs to another plan; plan 65 only records. QQ18 frozen anchor per series. QQ19 every recorded change is a series boundary; declared expected shifts restart only listed members; undeclared restarts all (14-night blind spot accepted). QQ20 no scipy. QQ21 no memory reading for the drift judge. QQ22 a model judge counts only once checked on planted faults. QQ23 docs are the memory. QQ24 coherence row collapsed. QQ25 one set of model-judge guards. QQ26 one approval. QQ27 automatic tuning within guards, off switch. QQ28 automatic promotion and pausing, off switch. QQ29 on a quality alarm: store a diagnosis, double the key-fact sample, one self-closing GitHub issue, off switch. QQ30 the other stored records. QQ31 a replacement inherits its predecessor's weight. QQ32 a per-source failure ledger for the feed-quality plan.
