# Content-similarity judge nightly check: known pairs, new pairs only, graded by score, lower-band sample

**Last Updated**: 2026-11-17
**Level**: 5 - rows 1, 3 and 6 move persisted shapes (Table C). Rows 2, 4 and 5 are Level 3.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The nightly judge check re-judges pairs it already judged, spends the same effort on near-certain pairs as on doubtful ones, never looks below a similarity score of 0.88, and never checks that the judge still answers known pairs correctly. |
| A2 | In plain English | The judge reads two summaries and answers YES (same story), NO (different stories) or UNCLEAR (a summary is too vague to say). After this plan each runner first answers six pairs whose answers are known; each night judges only pairs that include one of that night's own stories; the share of pairs judged falls as the score rises; and a small fixed sample of low-scoring pairs is judged so the score where "same story" fades out can be read each night. |
| A3 | Plan state | Draft for refinement. Each row's `Files touched` comes from reading and is re-derived by search when the row is dispatched. Every measured figure carries its date and is re-derived before it is relied on. |
| A4 | Hard scope - in | Rows 1 to 6. |
| A5 | Hard scope - out | Table B. |
| A6 | Contracts moved | Table C. Nothing else persisted changes. |
| A7 | ESCALATE triggers | 1. A persisted shape not in Table C. 2. A change to what publishes, including the 0.94 line. 3. A change to the model, prompt, grammar or sampler. 4. Article text sent anywhere except the committed model server. 5. A step that needs a person's mark or approval. 6. A change to `band_low`, `band_high` or `bin_width` (scope out B8). |
| A8 | Chosen strategy | Known pairs first, because they start the 14-night record row 6 needs; then judge new pairs only, grade the share judged by score, sample the lower band and report where it starts. No person in any step. Fowler ruled the draw, contracts and tests; Andre ruled the sampling, the known pairs and the failure rule. |
| A9 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; parallel N = 1 because every row edits the nightly-check page and most edit the judge's tenant, settings and knob files, so no two rows are ready together; row 1 goes first because row 6 waits on 14 nights of its record; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes. |

Table B - Scope boundaries

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Replacing the old line-fit and its 3% rule | The fitted line stays unreliable: it moves with the band's bottom edge and rests on judge mistakes, and once pairs are sampled by score its counts stop being evidence. Nothing publishes from it (it is switched off). | Rows 1 to 5 run clean for 14 nights; a plan then picks the publishing line from weighted verdicts and decides whether to reset the record. |
| B2 | A person marking verdicts | The judge's own wrong NOs near the line cannot be told from real false merges. | A person or an independent labelling resource exists and its marks are recorded with their origin. |
| B3 | A larger known-answer accuracy run (the 200 labelled pairs, about 2.3 model-hours) | No accuracy rates beyond six known pairs. | A runner slot or local model host, run through the existing offline evaluation procedure, with model-origin labels named as such. |
| B4 | Changing the judge's question or prompt | The question ("do these report the exact same event") is stricter than the merge decision, so false NOs continue. | B3 measures the false-NO rate, or the known unclear pairs are answered with anything but UNCLEAR on most nights. |
| B5 | A console page for the lower band | Reading it needs a command or the planning-job log. | Row 5 has run 14 nights; a design consult on the page follows. |
| B6 | Resume on re-run: a re-run night judges only the pairs it lacks | A re-run re-judges the whole night (20% of judgments from 2026-11-03 to 2026-11-16). | Re-runs stay above 10% of judgments after the lost-runner cause is found. |
| B7 | Raising `pair_budget` above 200 | Rows 3 and 4 together exceed 200 on 2 of 8 replayed nights (2026-11-09 and 2026-11-13); the lower-band sample gives way on those nights. | The lower-band sample is cut on 3 of 10 nights. |
| B8 | Moving `band_low`, `band_high` or `bin_width` | The record counts nothing below 0.88; lower-band verdicts live only in the pair rows and the row 5 report. | A plan that replaces the line-fit; the move changes the record's slot layout and stamp, so the record is archived and restarted (Level 5). |

Table C - Contracts moved

| Id | Shape | Change | Read-side rule | Row | Level |
| --- | --- | --- | --- | --- | --- |
| C1 | `StorySimilarityPair` in `backend/idhazh/contracts/story_similarity_pair.py` | One optional field `draw_share`: above 0 and at most 1, the judged pairs of this pair's score range that night divided by the pairs that range held. | Null by default. A row, CSV cell or ledger partition without it reads as share 1. New changelog entry; version stamped. | 3 | 5 |
| C2 | `ContentSimilarityJudgeConfig` in `backend/idhazh/contracts/knobs/content_similarity_judge.py`, file `config/judges/content-similarity-judge.json` | Knobs `graded_shares` (row 3), `low_band` (row 4: floor, range width, pairs per range) and `lower_band_report` (row 5: nights, share, minimum pairs). | The committed file lists every knob (a config test compares the file with the model); each knob has a default so an older file still loads. A validator refuses a share table that rises with the score. None enters the record's stamp. | 3, 4, 5 | 3 |
| C3 | New `ContentSimilarityCanaryConfig` in `backend/idhazh/contracts/knobs/content_similarity_canaries.py`, file `config/judges/content-similarity-canaries.json` | Per pair: `canary_id`, `kind` (same, different, unclear), `expected` (YES, NO, UNCLEAR), both summaries, `origin` (published or synthetic), source references, `labelled_by`, `basis`; row 6 adds `holds_a_night`. Set fields: `enabled`, `enforced`. | New file; no earlier reader. Written as ASCII JSON, with non-ASCII characters escaped as the published day payloads are. | 1, 6 | 5 |
| C4 | `ContentSimilarityJudgeMetrics` in `backend/idhazh/contracts/content_similarity_judge_metrics.py` | Four optional fields: `canary_set_digest`, `canary_pairs_asked`, `canary_pairs_right`, `canary_outcomes`. | Null by default; an older row reads; new changelog entry. | 1 | 5 |
| C5 | `HeldReason` in `backend/idhazh/contracts/fitted_similarity_threshold.py` | New value `canary_failed`. | Older rows never carry it; the console's copy of the vocabulary gains it in the same change. | 6 | 5 |

## 1. Status Reckoner

Table D - Status Reckoner

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Run six known pairs every night, record only | - | A | PENDING | - | - | - |
| D2 | 2 | Judge only new pairs | - | B | PENDING | - | - | - |
| D3 | 3 | Judge fewer pairs as the score rises | 2 | B | PENDING | - | - | - |
| D4 | 4 | Sample the lower band every night | 3 | B | PENDING | - | - | - |
| D5 | 5 | Say where the lower band is | 4 | B | PENDING | - | - | - |
| D6 | 6 | Hold a night when the known pairs fail | 1 | A | PENDING | - | - | - |

## 2. The known pairs

### Row #1 - Run six known pairs every night, record only

- **Scope:** Level 5 (C3, C4). Six real known-answer pairs (two same, two different, two unclear) kept in judge config are judged by every runner through the live judge path, and the answers are recorded on the metrics row; nothing is held.
- **Files touched:**
  - `config/judges/content-similarity-canaries.json`
  - `backend/idhazh/contracts/knobs/content_similarity_canaries.py`
  - `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/stages/judge_canary_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/similarity/budget.py`
  - `backend/tests/contracts/test_content_similarity_canary_config.py`
  - `backend/tests/test_judge_canary_pairs.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/workflows/_harness.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: run the new and changed tests through the project's test selector ([run the gates](../docs/how-to/run-the-gates.md)); ruff and mypy on the touched Python files; `python backend/utilities/doc_load.py` on the new page and the edited pages.
  - Contract tests, in memory: the config is refused for a set with no pair of one kind, duplicate ids, an expected answer that disagrees with its kind, an empty summary, more than 12 pairs, or a synthetic pair whose id lacks the `canary-synthetic-` prefix; the committed file is read as bytes (one named file) and holds no non-ASCII byte.
  - Stage tests: with a recorded-response client a wrong answer counts wrong and an order disagreement counts inconclusive; the request bytes for a known pair equal the bytes the live path builds for the same two summaries; a known pair never appears in the draw file, the verdict files, the pair ledger or the record; the metrics row carries the four fields and an older row still reads; the plan-time guard counts the nine known-pair judgments a runner makes.
  - CI: the required checks are authoritative; no full local suite.
  - Named observation: on the next council run read each runner's metrics row (four fields present) and note any known pair that every runner answered differently from its label.
- **Oracle:** the request bytes for a known pair equal those of a live pair with the same two summaries, so the judge cannot tell them apart. It cannot settle whether the agent-written labels are right; the first 14 nights show where the judge and the labels disagree.
- **Starting set** (found in the published digest and labelled from the summaries alone on 2026-11-17; re-verify against the published day files at dispatch, then copy each summary into the config so a retired day cannot orphan a pair):

Table E - Starting known pairs

| Id | Kind | Left (date, item id) | Right (date, item id) | Expected | Basis |
| --- | --- | --- | --- | --- | --- |
| E1 | same | 2026-11-07, `india-4at2refk8ng9fhy3` | 2026-11-07, `india-689nbq3f7gm8ja9d` | YES | One company filing: one director retires on one date on reaching one age under one governance rule, and both say the filing covers only that company. Score 0.971. The judge answered YES on 3 of 3 nights (2026-11-07 to 2026-11-09) at first-reading margin 0.98 or more. |
| E2 | same | 2026-11-11, `india-6zsc86d0xcfnqvx8` | 2026-11-11, `india-aeeq7vvdytycwhwr` | YES | One technology firm ends visa and green-card sponsorship for one division, with a year-end deadline, and both cite the same decline in visa petitions. Score 0.928, inside the band. YES on 3 of 3 nights (4 rows, 2026-11-11 to 2026-11-13) at margin 0.94 or more. |
| E3 | different | 2026-11-04, `world-0dc4qgdn09ta6vae` | 2026-11-04, `business-economy-2nhmc06msp85an7w` | NO | A school graduation in Rio de Janeiro and a company's data-centre investment in Malaysia: no actor, place or topic in common. Never judged. |
| E4 | different | 2026-11-10, `world-7pcx0fkda710c87y` | 2026-11-08, `india-w7s3sydgkhr0bkna` | NO | A climate summit opening and a youth cricket match in Oman: no actor, place or topic in common. Never judged. |
| E5 | unclear | 2026-11-07, `ai-gp9n67v36c3r4t64` | 2026-10-24, `ai-q5vhq5s6p62e7sb2` | UNCLEAR | Two one-line cartoon captions; neither summary says what happened, so by the prompt's rule (UNCLEAR is about the text) neither names an event. Same source, which the judge never sees. Never judged. |
| E6 | unclear | 2026-11-07, `ai-act5etj22gy5jvdn` | 2026-11-07, `world-t4n61hawy70wkg6h` | UNCLEAR | A one-line cartoon caption on the aftermath of an election beside a specific report from that aftermath (a senior appointment); the caption names no event, so sameness cannot be decided. Never judged. |

- **Decisions:**

Table F - Row 1 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| F1 | The executing agent finds and labels the pairs; no person is asked. Same: two outlets, same actors, same action, same occasion. Different: no actor, place or topic in common. Unclear: at least one summary is too vague to name what happened, which is the judge prompt's own definition. Each pair records `labelled_by` (the agent, never a person) and a one-line `basis`. A pair is kept only if its label follows from the two summaries alone. | Andre |
| F2 | Pairs are real published summaries. A hand-built pair is allowed only with a `canary-synthetic-` id and `origin` synthetic, named where it sits; the starting set has none. | Andre |
| F3 | The unclear pairs use real caption-only summaries. The judge has never answered UNCLEAR on a real pair (0 of 4,943 judged rows, checked 2026-11-17), so these are the first exercise of that answer; 31 of 17,249 published summaries from October and November say their source gave no further detail, found by searching for phrases such as "offers no figures" and "single-line caption" (re-derive). | Andre |
| F4 | A known pair travels the same fence and request body as a live pair, with no marker. The comparison with the known answer is code. | Andre; Fowler |
| F5 | Each runner judges all six before its live pairs (a broken server is found before the shard spends its window) and one of each kind (three) after them (decay late in a run is found). The tenant builds one reader for both stages. A pair that was not asked is recorded as not asked and never counts as wrong. | Andre; Fowler |
| F6 | A known pair is never a pair row, so it cannot enter the draw, the verdict files, the pair ledger, the record or the fit. Results go on the metrics row (C4): the set's digest, how many were asked, how many were right, and each answer. | Fowler |
| F7 | The summary text lives in the config file, so a retired published day cannot orphan a pair. The set holds at most 12 pairs and every kind. It changes only by a reviewed edit of the file; the digest on each metrics row names the set a night ran. There is no automatic refresh, because an automatic refresh would put fetched text into the judge's reference set unreviewed. | Fowler |
| F8 | The plan-time guard adds the nine known-pair judgments per runner (each costs the same as a live pair, both orders) to a shard's pairs; the 110.98 s yardstick stays. 50 + 9 = 59 pairs at 110.98 s is 109 minutes against the 175-minute window; at the measured 41 s a pair it is 40 minutes. | Fowler |
| F9 | What a wrong answer would catch: a changed model, a runtime build or flag change that breaks the constrained answer, an edit of the prompt or grammar that changes what the judge says, and memory-pressure garbage late in a run (the after-run set). What it cannot catch: a slow loss of accuracy on pairs unlike these six, a changed score ruler (the scorer sits upstream), or a wrong summary upstream. | Andre |
| F10 | Revert path: `enabled` false in the canary file stops the stage; the four metrics fields stay null. | Fowler |
| F11 | This row creates `docs/architecture/publishing/content-similarity-nightly-check.md` (R6) with its Design rationale section; later rows add their sections to it, and the autotune page gets links and only the corrections named in H5 and J6. | Fowler |

- **Rejected alternatives:**

Table G - Row 1 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G1 | A planted fake article that travels from the feed to the draw | It tests the whole chain. | It would publish into the digest, against static-first publication; price by the digest change it needs. | Fowler |
| G2 | A person confirms the labels | Independent of the judge. | A reviewer; price by the minutes to read 12 pairs once. | Andre |
| G3 | Reuse the private evaluation set contract | An existing shape. | Couples the nightly read to a private harness that may change; price by that harness's changelog. | Fowler |
| G4 | More pairs now (up to 12) | A finer reading per class. | About 1.4 more minutes a runner for each three pairs at 41 s a pair; price by 14 nights of the six first. | Andre |

## 3. The draw

### Row #2 - Judge only new pairs

- **Scope:** Level 3. The nightly draw stops scoring and judging pairs whose two stories both come from the two earlier days, and every comment and page that says the window reaches one earlier day says two.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/stages/assemble.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/tests/test_same_story.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/concepts/growing-reads.md`
- **Acceptance gates:**
  - Local: run `backend/tests/test_same_story.py` and `backend/tests/test_similarity_selection.py` through the project's test selector; ruff and mypy on the touched Python files; `python backend/utilities/doc_load.py` on the edited pages.
  - New test, in memory, no disk fixture: one story from the night's own day and two cross-outlet stories from the earlier days, equal vectors, distinct addresses. The two pairs that include the night's own story are yielded; the pair of the two earlier stories is not.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run read the draw file and the night's own published payload (two named files); every drawn pair names at least one item of that payload. If one does not, revert the guard commit.
- **Oracle:** every pair `cross_source_pairs` yields has at least one story from the night's own day, which is exactly the set `collapse_same_story` can weigh. It cannot settle whether a story published after the council's checkout is missed (H4).
- **Decisions:**

Table H - Row 2 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| H1 | A pair of two earlier-day stories is never judged tonight. The merge pass only joins the night's own stories to groups, so such a pair cannot change what publishes, and it was judged (or cut by the cap) on the night it was new. Measured 2026-11-17 by replaying the repo's own draw functions against the committed ledger over 2026-11-03 to 2026-11-16: 0 of 733 drawn pairs with a story from the night's own day had been judged on an earlier night; 772 of 1,046 drawn both-earlier pairs had. Re-derive before dispatch. | Fowler |
| H2 | No memory of judged pairs and no new persisted state; the guard reads only the day's own addresses. | Fowler |
| H3 | A night that fails is re-run by the existing repair path. Both-earlier repeats used to count some of a failed night's pairs a second time (71 of the record's 790 pairs got in that way); they no longer do. | Fowler |
| H4 | A story published after the council's checkout would be undrawn. The replay on final payloads matched the committed draw size on 14 of 14 nights, so no action now; a mismatch seen in the named observation reopens it. | Fowler |
| H5 | The window reaches `ceil(window_hours / 24)` days, two at 36 hours. The four docstrings and two doc lines that say one are corrected, and the `cross_source_pairs` docstring, which promises exactly the pairs the grouping pass weighs, becomes true. | Fowler |

- **Rejected alternatives:**

Table I - Row 2 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I1 | Memory of judged pairs read from the previous two dates' ledger rows and matched on the instrument stamp | Catches republished addresses and same-date re-runs, neither seen in 14 nights; leaves both-earlier pairs in the pool; adds a read path to the planning job. | A bounded two-date ledger read (Guardrail 12) plus stamp matching; price it by counting repeated pairs over 10 nights after this row. | Fowler |
| I2 | A persisted pair-memory file | Solves a problem the guard removes and adds a contract. | A declared contract, version and read-side rule; price it by the same 10-night repeat count. | Fowler |
| I3 | Leave as is | 54% of 2,323 judgments since 2026-11-03 were repeats (34% across nights, 20% re-runs). | Nothing to build; price the delay by the nightly share of repeated judgments. | Plan intent |

### Row #3 - Judge fewer pairs as the score rises

- **Scope:** Level 5 (C1), with C2. The draw judges every new pair between 0.88 and 0.92 and a falling share above that, chosen by the draw's own hash, and each judged pair records the share it was drawn with.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/similarity/selection.py`
  - `backend/idhazh/similarity/published_line.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_published_line.py`
  - `backend/tests/contracts/test_story_similarity.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `backend/tests/ledger/test_arrow_schema.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: selection tests (a range judges `ceil(share x pool)` pairs; the same night drawn twice gives the same pairs; over the ceiling the top range is cut first; the validator refuses a rising share table); contract tests (`draw_share` round trip; null; a CSV and a ledger partition without the column still read; 0 and values above 1 refused); the ledger schema test with a day written before the column and a day written after; the config test with the new knob listed in the committed file; doc check on the edited pages.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run the draw file has a `draw_share` column and fewer pairs at or above 0.92 than the replay of the old rule.
- **Oracle:** on a fixed in-memory night, the judged count of each score range times its 1 / `draw_share` equals the range's pool exactly. It cannot settle whether these shares suit real nights (R1).
- **Decisions:**

Table J - Row 3 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Default shares by score: 0.88 to 0.92 all; 0.92 to 0.94 three in four; 0.94 to 0.96 half; 0.96 to 0.98 a quarter; 0.98 and above one in eight. The higher the score, the fewer pairs are judged, because the answer is nearly always the same. On the replays of 2026-11-09 to 2026-11-16 this saves 9.7 of 124.6 new in-band pairs a night on average (19.8% of new pairs score 0.92 or more); the larger saving comes from row 2. Re-derive before dispatch. | Plan intent; Andre |
| J2 | Ranges are fixed scores, not tied to the published line, so a moving line cannot move the draw. | Fowler |
| J3 | Each range judges its `ceil(share x pool)` pairs with the smallest hash values, the hash the draw already uses (no seed), so a re-run of a night judges the same pairs and the share is exact. | Fowler |
| J4 | `draw_share` (C1) is the judged pairs of the pair's range divided by the new pairs the range held, after any cut. Its inverse is the weight a later reading gives the pair; an older row reads as share 1. The old record keeps counting raw verdicts. | Fowler |
| J5 | `pair_budget` stays the ceiling on a night's pairs, and the existing plan-time guard keeps its meaning. Over the ceiling the draw cuts from the top score range down, because those pairs tell least. The old rule that keeps every pair at or above the line past the budget ends, and the `select` docstring that calls those pairs the whole of the precision measurement is rewritten: the measurement is now the weighted verdicts of the graded pairs. | Fowler |
| J6 | The old line-fit is unchanged and its counts stop being evidence once pairs at or above 0.92 are sampled; the nightly-check page and the autotune page's Design rationale say so (scope out B1). `select` stops reading the published line; `pick_item_pairs` is the only production caller of `read_published_line` (read 2026-11-17), so if a search at dispatch still finds only that caller the function and its test file are deleted in this row, otherwise the function stays. | Fowler |
| J7 | No new knob enters the record's stamp (`band_low`, `band_high`, `bin_width` and the judge settings are untouched), so the record is neither archived nor reset. | Fowler |

- **Rejected alternatives:**

Table K - Row 3 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Judge every pair above the line | Spends compute on pairs that are nearly always the same story. | Nothing to build; price by counting pairs at or above 0.92 a night in a replay. | Plan intent |
| K2 | No `draw_share` | Smaller change. | Later rates from sampled nights would be biased with no way to correct them; price by re-judging sampled nights. | Fowler |
| K3 | Shares tied to the published line | The draw would move with the applied line, a loop the autotune page rules out. | A replay under a moved line shows how far the draw shifts; price by that replay. | Fowler |
| K4 | A random threshold on each pair's hash instead of a count per range | Needs no pool count. | The judged count and the share vary night to night, so the weight is approximate; price by the spread over 10 replayed nights. | Fowler |

### Row #4 - Sample the lower band every night

- **Scope:** Level 3 (C2). The draw adds a fixed handful of new pairs from each 0.02 score range below the band's bottom, down to a configured floor (default 0.70, 4 pairs a range a night), and the fit's health numbers keep describing the band only.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/similarity/selection.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_counting.py`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
- **Acceptance gates:**
  - Local: a night with pairs in every range draws the smaller of the pool and the configured count per range, deterministically, and each pair's `draw_share` equals taken over pool; over the ceiling the low-band sample is cut before any graded pair; `set_merge_line`'s `pairs_in_band`, disagreement and unclear numbers are identical with and without below-band rows (in memory); `count_day` still ignores below-band rows; a count of 0 per range draws nothing below the band; doc check.
  - Before merge: replay the last 8 committed nights through the new draw and record pairs judged a night against the 200 ceiling and the plan-time guard (L4).
  - CI: the required checks are authoritative.
  - Named observation: the next council run's draw file holds rows below 0.88; the fitted row's numbers keep their meaning.
- **Oracle:** adding below-band rows to a night leaves that night's fitted-row numbers and the record unchanged. It cannot settle whether 4 pairs a night per range is enough to read the fade (a week gives up to 28 per range).
- **Decisions:**

Table L - Row 4 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Pairs below 0.88 are drawn so the score where "same story" stops can be read each night. None has ever been judged (checked 2026-11-17: 0 of 4,948 ledger rows score below 0.88; the lowest slice already answers YES for 84% of pairs). | Plan intent; Andre |
| L2 | The floor, range width and count per range are config values (`low_band`). The draw never reads the computed edge of row 5, so the sample cannot follow its own result. | Fowler |
| L3 | A below-band pair is an ordinary pair row (the pair contract bounds a score only to 0 and 1). The record ignores it, and the fit's day rows are limited to the band so `pairs_in_band` and the disagreement and unclear rates keep describing the band. Known pairs are never rows. | Fowler |
| L4 | Compute stays about level with today. Replayed over 2026-11-09 to 2026-11-16: today's draw averages 178.8 pairs a night (the cap binds on 6 of 8 nights). The new rule averages 115.0 graded pairs plus 36 lower-band pairs, which the 200 ceiling trims to 141.6 on average, plus 36 known-pair judgments from row 1: 177.6 judgments a night. Re-derive by replay before merge. | Fowler |
| L5 | If the lowest range still shows a same-story share above the row 5 threshold, the report says the floor is too high; lowering it is a config edit. | Andre |
| L6 | Revert path: `pairs_per_range` of 0 turns the sample off. | Fowler |

- **Rejected alternatives:**

Table M - Row 4 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | The floor follows the computed edge | A sample shaped by its own result. | Replay a night under a moved floor to price the feedback; it needs a guard like the record's no-feedback rule. | Fowler |
| M2 | Judge every new pair below 0.88 each night | The pool is 313 to 6,080 new pairs a night: 0.9 to 17 hours per runner against a 175-minute window. | A larger window or more runners; price by the replayed pool sizes. | Fowler |
| M3 | A one-off probe only | Cheap (about 108 pairs, about 74 model-minutes) but cannot show how the boundary moves from night to night. | Nothing to build; the nightly sample costs about 25 model-minutes a night. | Andre |

### Row #5 - Say where the lower band is

- **Scope:** Level 3 (C2). A command and a planning-job log line report, for each 0.02 score range over the last 7 counted nights, how many pairs were judged and what share were YES, NO and UNCLEAR (weighted by 1 / `draw_share`), and the lowest range from which "same story" stays above 20%.
- **Files touched:**
  - `backend/idhazh/similarity/lower_band.py`
  - `backend/idhazh/stages/report_lower_band.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/cli.py`
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/tests/test_similarity_lower_band.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
- **Acceptance gates:**
  - Local: a hand-built 7-night weighted table returns the edge worked out by hand; a range with too few pairs reports "not enough pairs" rather than a number; an empty window reports "no reading"; a date the record did not count is never read; a row with another stamp is dropped; the read opens only the named dates (Guardrail 12); doc check.
  - CI: the required checks are authoritative.
  - Named observation: the next night's planning log prints the table and the edge in plain words.
- **Oracle:** the hand-built table gives the edge computed by hand. It cannot settle that the edge is the world's boundary; it describes this judge's answers.
- **Decisions:**

Table N - Row 5 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | The reading is derived, with no new persisted payload: it takes the last `readout_nights` (default 7) dates in the record's counted-date list, reads each date's pair rows through the existing day-named ledger reader, keeps rows that carry the record's stamp, and weights each by 1 / `draw_share`. A date the record did not count (a lost or failed night) is never read, and a stamp change empties the window. | Fowler |
| N2 | Edge rule: the lowest range from which every higher range has a same-story share of at least `lower_band_share` (default 20%) with at least `minimum_pairs_per_range` (default 12) judged pairs; otherwise "not enough pairs". The share is weighted YES over weighted usable pairs; a pair is usable when both readings agree. | Andre |
| N3 | Shown by the command (`python -m idhazh report-lower-band`) and by the planning log in plain words: pairs scoring below X are rarely judged the same story. No console page yet (scope out B5). | Plan intent |
| N4 | The reading includes the UNCLEAR share per range. The judge has never answered UNCLEAR on a real pair, so the known pairs of row 1 are the only exercise of that answer. | Andre |

- **Rejected alternatives:**

Table O - Row 5 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | A new ledger of nightly readings | A persisted time series. | A registered ledger, partitions, compaction and docs; price by the size of the last ledger added. | Fowler |
| O2 | Fields on the fitted row | One number a night. | Mixes this reading with the line-fit's meaning, which scope out B1 replaces; price by the console vocabulary change. | Fowler |

## 4. The hold rule

### Row #6 - Hold a night when the known pairs fail

- **Scope:** Level 5 (C3, C5). After 14 nights of recorded answers, a runner fails a night when a reliable known pair is answered wrongly; a failed night is not counted and is re-run by the existing repair path; the fitted row says `canary_failed`.
- **Start condition:** the metrics ledger holds known-pair answers for 14 nights. Until then the row stays PENDING.
- **Files touched:**
  - `backend/idhazh/contracts/fitted_similarity_threshold.py`
  - `backend/idhazh/contracts/knobs/content_similarity_canaries.py`
  - `config/judges/content-similarity-canaries.json`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `frontend/src/lib/server/content-similarity-judge.ts`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/contracts/test_native_typescript_bindings.py`
  - `backend/tests/contracts/test_content_similarity_canary_config.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: `settle` with one failing runner row leaves the date uncounted and in neither date list, and the fitted row says `canary_failed`; with `enforced` false nothing changes; a pair with `holds_a_night` false never fails a night; the console's copy of the vocabulary and its test hold the new value; the rule replayed over the 14 recorded nights holds none of them; doc check.
  - CI: the required checks are authoritative.
  - Named observation: after merge, read each failed runner-night and whether the repair path cleared it within 7 nights; if a night fails with no wrong answer on a reliable pair, set `enforced` back to false and surface it.
- **Oracle:** replaying the 14 recorded nights through the rule holds none of them. It cannot settle false holds on a night harder than those 14.
- **Decisions:**

Table P - Row 6 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| P1 | No person decides which pairs may hold a night. At row start the executing agent reads the 14 recorded nights and sets `holds_a_night` in the canary file: true for a pair that was right on at least 13 of 14 nights on every runner, false otherwise (disputed: the label or the judge is wrong and the data cannot say which). Disputed pairs are reported every night and never hold. The change is one reviewed diff in this row's pull request, and the runtime reads no history. | Andre |
| P2 | A runner fails a night when it answered a pair with `holds_a_night` true wrongly (usable and different from the expected answer), or when the two orders disagreed on two or more such pairs. A pair that was not asked never fails a night. | Andre |
| P3 | Estimate behind P1 and P2: 253 re-reads of pairs first judged at margin 0.9 or more changed no answer and left 3 unusable (2026-11-17), so a wrong answer on a reliable pair is expected to be rare; the 14-night record replaces this estimate. | Andre |
| P4 | A failed night keeps its rows in the ledger, is not counted into the record, and is re-run by the existing repair path (`repair_dates_a_night` and `repair_window_nights` in `config/llm_council.json`). Row 5 reads only counted dates, so a failed night's rows never reach the lower-band report. No second-failure logic. | Fowler |
| P5 | `enforced` ships true only in the change that passes the oracle; the flag is the revert path. | Fowler |

- **Rejected alternatives:**

Table Q - Row 6 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Hold on the first wrong answer from day one | Simplest. | Unlabelled flakiness would hold real nights; price by the 14-night record. | Andre |
| Q2 | Drop only the failing runner's rows and count the rest | Keeps more evidence. | A partial night cannot be counted and cannot be topped up (the record counts a date once); price by the autotune page's rule. | Fowler |

## 5. Open questions

Table R - Open questions for refinement

| Id | Question | Recommended answer | Row it blocks |
| --- | --- | --- | --- |
| R1 | Which shares by score range? | J1: all to 0.92, then three in four, half, a quarter, one in eight. | 3 |
| R2 | How big is the lower-band sample, and how low does it go? | 4 pairs per 0.02 range from 0.70 to 0.88 (36 a night); lower the floor only if the lowest range still shows 20% same-story. | 4 |
| R3 | Should the lower-band sample sit inside the 200 ceiling? | Yes: it gives way on busy nights (2 of 8 replayed) and the weights correct for unequal nights. | 4 |
| R4 | When is the lower band "found"? | N2: lowest range from which every higher range is at least 20% same-story over 7 counted nights, with at least 12 judged pairs per range. | 5 |
| R5 | How many known pairs, and which? | Six (two of each kind) from Table E; up to 12 allowed. | 1 |
| R6 | Where does the design live? | A new page, `docs/architecture/publishing/content-similarity-nightly-check.md`: the autotune page is about 22,650 tokens over 12 sections, and a page you add to pays the split test first. | 1 |
| R7 | Does the old line-fit get a plan of its own? | Yes, after rows 1 to 5 have run 14 nights (scope out B1). | - |

## See also

- [Similarity rule and instrument identity](../docs/architecture/publishing/autotune-content-similarity.md)
- [Native contract compatibility](../docs/architecture/contracts/schemas.md)
- [Evaluate the judge offline](../docs/how-to/evaluate-content-similarity-judge.md)
- [Run the gates](../docs/how-to/run-the-gates.md)
- [Author a plan](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
