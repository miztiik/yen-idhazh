# Content-similarity judge nightly check: new pairs only, score buckets, lower-band report, canary pairs

**Last Updated**: 2026-11-18
**Level**: 5 - row 4 adds one stored column. Rows 1 and 2 are Level 3, row 3 is Level 2; none of them stores anything new.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Each night the judge re-judges pairs it already judged, spends as much on near-certain pairs as on doubtful ones, never looks below a similarity score of 0.88, and has no check that it still answers a known pair correctly. |
| A2 | What changes | Judge only pairs that include one of tonight's own stories (row 1). Judge fewer pairs as the score rises, and a small fixed sample from every 0.02 bucket between 0.70 and 0.88 (row 2, Table C). Print where "same story" fades out (row 3). Judge six known pairs once per run, spread over the runners (row 4). |
| A3 | What is stored | One new optional column on each runner's existing metrics row: its known-pair answers (row 4). Nothing is added to the pair rows, the record or the console. |
| A4 | Hard scope - out | Table B. |
| A5 | Measured figures | Every figure carries its date and is re-derived before it is relied on. Each row's `Files touched` comes from reading and is checked by search at dispatch. |
| A6 | ESCALATE triggers | 1. A stored shape beyond A3. 2. A change to what publishes, including the 0.94 line. 3. A change to the model, prompt, grammar or sampler. 4. Article text sent anywhere but the committed model server. 5. Anything that reacts to a wrong known-pair answer by holding, re-running or stopping a night. 6. A move of the record's band edges or bin width (B6). |
| A7 | Chosen strategy | Judge only what is new, test less as the score rises, sample the unseen lower band, check the judge against known pairs, and only record the result. Fowler ruled the draw and what is stored; Andre ruled the sampling and the known pairs. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the plan and delegates a row where delegation pays; parallel N = 1 because the rows share the judge's tenant, settings, knob and docs files; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes. |

Table B - Scope boundaries

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Replacing the old line-fit and its 3% rule | Its fitted line stays unreliable, and from row 2 on its high-score counts are thinner. Nothing publishes from it (it is switched off). | Rows 1 to 4 run clean for 14 nights; a plan then picks the publishing line from the new evidence. |
| B2 | Acting on a wrong known-pair answer: holding or re-running a night | A wrong answer is logged and stored; nothing stops. | A request naming what a failure should do, and what a wrongly held night costs. |
| B3 | Independent accuracy evidence: a person's marks, or the 200 labelled pairs (about 2.3 model-hours) | No accuracy rate beyond the six known pairs. | A person or labelling resource exists, run through the offline evaluation procedure with model-origin labels named as such. |
| B4 | A stored nightly lower-band reading and a console chart | The edge is read from a command and the planning log, and any past night can be recomputed. | 14 nights of reports exist, and a design consult on the page is done. |
| B5 | Resume on re-run: a re-run judges only what it lacks | A re-run re-judges the whole night: 20% of judgments from 2026-11-03 to 2026-11-16. | Re-runs stay above 10% of judgments once the lost-runner cause is found. |
| B6 | Moving `band_low`, `band_high` or `bin_width` | The record counts nothing below 0.88; lower-band verdicts live only in the pair rows and the report. | A plan that replaces the line-fit; a move restarts the record (Level 5). |

Table C - Score buckets (row 2). "New pairs" include one of the night's own stories; averaged over 2026-11-09 to 2026-11-16.

| Id | Score bucket | What the judge does | New pairs a night | Judged a night |
| --- | --- | --- | --- | --- |
| C1 | 0.70 to 0.72 | 4 pairs, first by the draw's hash | 478 | 4 |
| C2 | 0.72 to 0.74 | 4 pairs | 439 | 4 |
| C3 | 0.74 to 0.76 | 4 pairs | 412 | 4 |
| C4 | 0.76 to 0.78 | 4 pairs | 369 | 4 |
| C5 | 0.78 to 0.80 | 4 pairs | 331 | 4 |
| C6 | 0.80 to 0.82 | 4 pairs | 282 | 4 |
| C7 | 0.82 to 0.84 | 4 pairs | 225 | 4 |
| C8 | 0.84 to 0.86 | 4 pairs | 165 | 4 |
| C9 | 0.86 to 0.88 | 4 pairs | 118 | 4 |
| C10 | 0.88 to 0.92 | Every pair | 100 | 100 |
| C11 | 0.92 to 0.94 | 3 pairs in 4 | 15 | about 11 |
| C12 | 0.94 to 0.96 | 1 pair in 2 | 6 | about 3 |
| C13 | 0.96 to 1.00 | 1 pair in 4 | 1 | under 1 |
| C14 | Identical headlines (score 1.0) | Every pair | 2 | 2 |
| C15 | Total | Plus 6 known pairs (row 4) | 2,945 | about 153 (today: 179, repeats included) |

## 1. Status Reckoner

Table D - Status Reckoner

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 1 | Judge only new pairs | - | A | PENDING | - | - | - |
| D2 | 2 | Judge by score bucket | 1 | A | PENDING | - | - | - |
| D3 | 3 | Report where the lower band is | 2 | A | PENDING | - | - | - |
| D4 | 4 | Run six canary pairs once per run | - | B | PENDING | - | - | - |

## 2. The draw

### Row #1 - Judge only new pairs

- **Scope:** Level 3. The nightly draw skips pairs whose two stories are both from the two earlier days, because they were judged on the night they were new.
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
  - Local: run `backend/tests/test_same_story.py` through the project's test selector ([run the gates](../docs/how-to/run-the-gates.md)); ruff and mypy on the touched Python files; `python backend/utilities/doc_load.py` on the new and edited pages.
  - New test, in memory: one story from the night and two cross-outlet stories from the earlier days with equal vectors. The two pairs that include the night's story come out; the pair of the two earlier stories does not.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run every drawn pair names at least one item of the night's published payload; if one does not, revert the guard.
- **Oracle:** every pair `cross_source_pairs` yields has a story from the night's own day, which is exactly the set the merge pass can use. It cannot settle whether a story published after the council's checkout is missed (E4).
- **Decisions:**

Table E - Row 1 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| E1 | A pair of two earlier-day stories is never judged. The merge pass only joins the night's own stories to groups, so such a pair cannot change what publishes. Measured 2026-11-17 by replaying the repo's draw functions over 2026-11-03 to 2026-11-16: 0 of 733 drawn pairs with a story from the night's own day had been judged before; 772 of 1,046 drawn pairs of two earlier-day stories had. Nothing new is stored. | Fowler |
| E2 | A failed night is re-run by the existing repair path. Earlier-day repeats used to count some of a failed night's pairs a second time (71 of the record's 790 pairs); they no longer do. | Fowler |
| E3 | The window reaches `ceil(window_hours / 24)` days, two at 36 hours. The four docstrings and two doc lines that say one are corrected, and the `cross_source_pairs` docstring (it promises exactly the pairs the merge pass weighs) becomes true. | Fowler |
| E4 | A story published after the council's checkout would be undrawn. The replay matched the committed draw size on 14 of 14 nights, so no action now; a mismatch in the named observation reopens it. | Fowler |

- **Rejected alternatives:**

Table F - Row 1 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F1 | A memory of judged pairs, read from the last two nights' ledger rows | It would catch republished addresses and same-date re-runs, neither seen in 14 nights, and leaves earlier-day pairs in the pool. | A bounded two-night read plus stamp matching; price it by counting repeats over 10 nights after this row. | Fowler |
| F2 | Leave as is | 54% of 2,323 judgments since 2026-11-03 were repeats (34% across nights, 20% re-runs). | Nothing to build; price the delay by the nightly share of repeats. | Plan intent |

### Row #2 - Judge by score bucket

- **Scope:** Level 3. The draw judges every new pair from 0.88 to 0.92, a falling share above that, and a fixed handful from each 0.02 bucket from 0.70 to 0.88 (Table C). The record, the pair rows and the 0.94 line are untouched.
- **Files touched:**
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/idhazh/similarity/selection.py`
  - `backend/idhazh/similarity/published_line.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `backend/idhazh/similarity/budget.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_published_line.py`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:**
  - Local: selection tests (each bucket follows its rule; the same night drawn twice gives the same pairs; a lower bucket gives the smaller of 4 and its pool; identical-headline pairs are always judged; over 200 pairs from 0.88 up the cut falls on the 0.88 to 0.92 buckets by hash; a share table that rises with the score is refused); `set_merge_line` numbers identical with and without below-band rows; the committed config file lists every new knob; the plan-time guard counts the extra pairs; doc check.
  - Before merge: replay the last 8 nights through the new draw and record pairs judged a night against today's 179 (Table C expects about 153).
  - CI: the required checks are authoritative.
  - Named observation: the next council run's draw file holds rows below 0.88, and the fitted row's numbers keep their meaning.
- **Oracle:** on a fixed in-memory night each bucket's judged count follows its rule exactly, and adding below-band rows leaves the fitted row's numbers unchanged. It cannot settle whether 4 pairs a night per bucket is enough to see the fade (a week gives up to 28 per bucket).
- **Decisions:**

Table G - Row 2 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| G1 | Buckets, shares, the lower floor (0.70), bucket width (0.02) and pairs per lower bucket (4) are config values with the Table C defaults. They are fixed scores, never tied to the published line, so a moving line cannot move the draw. A share table may only fall as the score rises. | Plan intent |
| G2 | Within a bucket pairs are ordered by the draw's own hash (no seed) and the share or count is taken from the front, so a re-run of a night judges the same pairs. | Fowler |
| G3 | Identical-headline pairs (about 2 a night) stay judged every night. They audit the headline rule, which the score buckets do not describe. | Fowler |
| G4 | The 200 cap stays and counts only pairs from 0.88 up; the lower sample (36 at most) comes on top. The plan-time guard adds the lower sample and the 6 known pairs: (200 + 36 + 6) / 4 = 61 pairs a runner, 113 minutes at its 110.98 s yardstick against a 175-minute window, 42 minutes at the measured 41 s a pair. | Fowler |
| G5 | Nothing is added to the pair rows. The report counts judged pairs per bucket without weights; a bucket's share is the committed table's value for that night, and the draw can be replayed from committed payloads if a weight is ever needed. | Fowler |
| G6 | Pairs below 0.88 are ordinary pair rows. The record ignores them and its band edges and bin width do not move, so it is not reset. `set_merge_line` limits its day rows to the band, so `pairs_in_band` and the disagreement and unclear rates keep describing the band. No console reader reads pair rows (checked 2026-11-18). | Fowler |
| G7 | The old line-fit is untouched. `select` stops reading the published line; if a search at dispatch finds `pick_item_pairs` is the only caller of `read_published_line`, the function and its test are deleted. | Fowler |
| G8 | Revert path: 0 pairs per lower bucket turns the lower sample off; a share of 1 in a bucket restores full judging there. | Fowler |

- **Rejected alternatives:**

Table H - Row 2 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H1 | Judge every pair above the line | Spends compute on pairs that are nearly always the same story. | Nothing to build; price it by the pairs scoring 0.92 or more (about 23 new ones a night). | Plan intent |
| H2 | Judge every new pair below 0.88 | 313 to 6,080 new pairs a night: 0.9 to 17 hours per runner against a 175-minute window. | A larger window or more runners; price it by the replayed pool sizes. | Fowler |

### Row #3 - Report where the lower band is

- **Scope:** Level 2. A command and a planning-log line print, for each 0.02 bucket over the last 7 counted nights, how many pairs were judged and what share were the same story, different, or unclear, and the score below which same-story pairs stay under 20%. Nothing is stored and nothing is drawn in the console.
- **Files touched:**
  - `backend/idhazh/similarity/lower_band.py`
  - `backend/idhazh/stages/report_lower_band.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `config/judges/content-similarity-judge.json`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/tests/test_similarity_lower_band.py`
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
- **Acceptance gates:**
  - Local: a hand-built 7-night table returns the edge worked out by hand; a bucket with fewer judged pairs than the minimum reports "not enough pairs"; an empty window reports "no reading"; a night the record did not count is never read; a row with another stamp is dropped; the read opens only the named nights (Guardrail 12); doc check.
  - CI: the required checks are authoritative.
  - Named observation: the next night's planning log prints the table and the one-sentence edge.
- **Oracle:** the hand-built table gives the edge computed by hand. It cannot settle that the edge is the world's boundary; it describes this judge's answers.
- **Decisions:**

Table I - Row 3 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| I1 | The reading is recomputed from saved pair rows and stored nowhere. It takes the last `nights` (default 7) in the record's list of counted nights, reads each night's pair rows through the existing day-named reader, and drops rows with another stamp. `--date` recomputes the reading as of any past night, which is how it is tracked. | Fowler |
| I2 | The edge is the lowest bucket from which every higher bucket has a same-story share of at least `share` (default 20%) over at least `minimum_pairs` (default 12) judged pairs; otherwise "not enough pairs yet". A pair counts when both readings agree, and the unclear share is shown beside it. The three defaults are config values. | Andre |
| I3 | A night the record did not count (lost or failed) is never read, so it cannot colour the reading. | Fowler |

- **Rejected alternatives:**

Table J - Row 3 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J1 | Store a nightly edge (a new field or ledger) and draw it in the console | The edge could be watched over weeks. | A stored shape (Level 5) plus a chart; registering a ledger took about 30 files the last time (2026-10-29), so price it by that diff. | Fowler |

## 3. The canary pairs

### Row #4 - Run six canary pairs once per run

- **Scope:** Level 5. Six known pairs (two same, two different, two unclear) in a new config file are judged once per run, spread over the runners; each runner stores its answers on its metrics row under each pair's fixed id, and a wrong answer is logged. Nothing else reacts to it.
- **Files touched:**
  - `config/judges/content-similarity-canaries.json`
  - `backend/idhazh/contracts/knobs/content_similarity_canaries.py`
  - `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/idhazh/content_similarity_judge/model_reader.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/stages/judge_canary_pairs.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/report_canaries.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/similarity/budget.py`
  - `backend/tests/contracts/test_content_similarity_canary_config.py`
  - `backend/tests/contracts/test_content_similarity_judge_metrics.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/test_judge_canary_pairs.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_tenant.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/workflows/_harness.py`
  - `docs/architecture/publishing/content-similarity-nightly-check.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/concepts/glossary.md`
- **Acceptance gates:**
  - Local: the config contract refuses a set missing a kind, with duplicate ids, a mismatched expected answer, an empty summary, over 12 pairs, or a synthetic pair without its id prefix; the committed file is ASCII. Stage tests with a recorded-response client: a wrong answer is reported wrong and disagreeing orders SPLIT; the request bytes equal a live pair's for the same two summaries; pairs are dealt over the runners and shift one runner each night; no known pair reaches the draw, the verdict files, the pair ledger or the record. Contract tests: `canary_answers` round-trips and an older row still reads. The plan-time guard counts the extra pairs; doc check.
  - CI: the required checks are authoritative.
  - Named observation: on the next council run the runners' metrics rows together hold all six ids exactly once; run `report-canaries` and read the grid.
- **Oracle:** the request bytes for a known pair equal those of a live pair with the same two summaries, so the judge cannot tell them apart. It cannot settle whether the agent-written labels are right, or whether the judge is right on pairs unlike these six; the first nights show where the judge and the labels disagree.
- **Starting set** (found in the published digest and labelled from the summaries alone on 2026-11-17; re-verify against the published day files at dispatch, then copy each summary into the config):

Table K - Starting canary pairs

| Id | Canary id | Kind | Left (date, item id) | Right (date, item id) | Expected | Why |
| --- | --- | --- | --- | --- | --- | --- |
| K1 | `same-1` | same | 2026-11-07, `india-4at2refk8ng9fhy3` | 2026-11-07, `india-689nbq3f7gm8ja9d` | YES | One listed company's filing: a director retires on one date at one age under one governance rule. Score 0.971; judged YES on 3 of 3 nights. |
| K2 | `same-2` | same | 2026-11-11, `india-6zsc86d0xcfnqvx8` | 2026-11-11, `india-aeeq7vvdytycwhwr` | YES | One technology firm ends visa sponsorship for one division, with a year-end deadline. Score 0.928, inside the band; judged YES on 3 of 3 nights. |
| K3 | `different-1` | different | 2026-11-04, `world-0dc4qgdn09ta6vae` | 2026-11-04, `business-economy-2nhmc06msp85an7w` | NO | A school graduation and a company's data-centre investment: nothing in common. Never judged. |
| K4 | `different-2` | different | 2026-11-10, `world-7pcx0fkda710c87y` | 2026-11-08, `india-w7s3sydgkhr0bkna` | NO | A climate summit opening and a youth cricket match: nothing in common. Never judged. |
| K5 | `unclear-1` | unclear | 2026-11-07, `ai-gp9n67v36c3r4t64` | 2026-10-24, `ai-q5vhq5s6p62e7sb2` | UNCLEAR | Two one-line cartoon captions; neither says what happened. Never judged. |
| K6 | `unclear-2` | unclear | 2026-11-07, `ai-act5etj22gy5jvdn` | 2026-11-07, `world-t4n61hawy70wkg6h` | UNCLEAR | A one-line cartoon caption on an election's aftermath beside a specific report from it; the caption names no event. Never judged. |

- **Decisions:**

Table L - Row 4 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | Once per run, not once per runner: each known pair is judged exactly once a night, so six judgments replace the 24 to 36 of a per-runner design. Pairs are dealt over the runners the way live pairs are, starting one runner later each night, so over a few nights every pair has run on every runner. | Plan intent |
| L2 | Each pair has a fixed id (`same-1`, `same-2`, `different-1`, `different-2`, `unclear-1`, `unclear-2`), never reused for different text or a different expected answer: a corrected pair gets a new id. Each answer is stored with its id on the runner's row, which already carries the run, the runner, and the model, prompt and grammar identity, so one pair's history reads down the nights and a wrong answer is tied to what gave it. | Plan intent |
| L3 | Stored: one optional column `canary_answers` on the metrics row, holding space-separated `id=ANSWER` tokens for the pairs that runner judged. ANSWER is YES, NO, UNCLEAR, SPLIT (the two orders disagree) or REFUSED. Absent reads as none. The contract version is stamped with a one-line changelog entry. | Fowler |
| L4 | A wrong answer (not the expected one, SPLIT or REFUSED) is logged as a warning with the pair's id. The night is judged and counted as usual: nothing holds, re-runs or stops, and the metrics row stays a record and never an alarm. | Plan intent |
| L5 | The executing agent finds and labels the pairs; no person marks them. Same: same actors, same action, same occasion. Different: no actor, place or topic in common. Unclear: at least one summary is too vague to name what happened (the judge prompt's own definition). Real published summaries only; a hand-built pair needs a `canary-synthetic-` id and `origin` synthetic, named where it sits. Each pair records `labelled_by` (the agent) and a one-line `basis`. | Andre |
| L6 | The judge has never answered UNCLEAR on a real pair (0 of 4,943 judged rows, checked 2026-11-17), so the two unclear pairs may be answered NO every night. That is a finding about the judge, not a fault in the check. | Andre |
| L7 | A known pair goes through the same reader and request as a live pair, with no marker, so the judge cannot tell it apart; code compares the answer with the expected one. It is never a pair row, so it cannot enter the draw, the pair ledger, the record or the lower-band reading. A runner judges its known pairs before its live pairs. This finds a wrong model, a runtime change that breaks the constrained answer, and a prompt or grammar edit; it cannot find decay late in a run or lost accuracy on pairs unlike these six. | Andre; Fowler |
| L8 | The summary text lives in the config file (ASCII JSON, non-ASCII letters escaped) so a retired published day cannot orphan a pair. At most 12 pairs, every kind present, changed only by a reviewed edit; no automatic refresh, because that would put fetched text into the judge's reference set unreviewed. `enabled` false stops the stage. | Fowler |
| L9 | `report-canaries` prints each pair's answers over the last 14 nights from the metrics rows (named nights, Guardrail 12). It reads only. | Plan intent |

- **Rejected alternatives:**

Table M - Row 4 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | The same six pairs on every runner | It shows the runners agree with each other, not that the judge is right. | Nothing to build; price it at 24 judgments a night (about 4 model-minutes a runner at 41 s). | Plan intent |
| M2 | A new ledger with one row per pair per run | Easiest to query. | About 30 files the last time a ledger was added (2026-10-29); price it by that diff. | Fowler |

## 4. Open questions

Table N - Open questions for refinement

| Id | Question | Recommended answer | Row it blocks |
| --- | --- | --- | --- |
| N1 | Is one column on the runner's existing metrics row enough for the known-pair history, or should each answer be its own row in a new ledger? | One column (L3): about 30 files cheaper, and the row already carries the run, the runner and the model, prompt and grammar identity. | 4 |
| N2 | Should the lower-band edge be stored nightly and charted in the console? | Not yet (B4): read it from the command for 14 nights, then decide. | 3 |
| N3 | What same-story share marks the end of the lower band? | 20% (I2); it is a config value. | 3 |
| N4 | Are the shares above 0.92 right? | Table C: 3 in 4, 1 in 2, 1 in 4. | 2 |
| N5 | Should a wrong known-pair answer turn the run red? | No (L4): record and warn only. | 4 |

## See also

- [Similarity rule and instrument identity](../docs/architecture/publishing/autotune-content-similarity.md)
- [Native contract compatibility](../docs/architecture/contracts/schemas.md)
- [Evaluate the judge offline](../docs/how-to/evaluate-content-similarity-judge.md)
- [Run the gates](../docs/how-to/run-the-gates.md)
- [Author a plan](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
