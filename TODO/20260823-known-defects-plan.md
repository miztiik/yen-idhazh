# Known defects

**Last Updated**: 2026-08-28

**Two defects are open and neither closes on more of the same code.** Defect 2
needed three repairs before a person could label anything, and all three
shipped. What is left is 60 human labels, nine more run-days at one scorer and
one pipeline, and one owner ruling on how that window is counted. None of the
three is code. Defect 18 is the opposite shape: the code now works and the
measurement it produces still cannot fire, so what it needs is a decision about
which instrument to keep.

Defects 15, 16 and 17 closed on 2026-08-27.

Closed rows are removed after checking their current production code, regression
tests and canonical docs. Git history holds their execution record; the living
docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Rule #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - queue repaired; 0 of 60 labels; 1 of 10 run-days, and 10 has never been reached** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 3 | CLOSED 2026-08-27 (PR #180) |
| 16 | The truncation-gap detector has never been fed, and the run pays twice for the answer | 5 | CLOSED 2026-08-27 |
| 17 | Two different word counters share one string and read as truncation | 5 | CLOSED 2026-08-27 |
| 18 | The truncation flag still cannot fire, now for a different reason | 5 | **OPEN - not measurable without the scorer weights** |

## 18 - The truncation flag still cannot fire, now for a different reason (OPEN)

Row 16 fed the scorer the real pre-cap body, so `hhem_full` now reads a
different text from `hhem`. The flag built on the gap between them still cannot
fire, and the reason is the aggregation rather than the input.

`score_over_chunks` takes the **maximum** over 900-word windows at a step of
750. The seen text is a prefix of the full text, so the full pass sees the same
first windows, one of them lengthened, plus every window after the cut. A
maximum over a superset cannot be smaller than a maximum over the subset. So
`hhem_full >= hhem` in almost every case, `hhem_delta = hhem - hhem_full` is
zero or negative, and `truncation_flagged = delta > evaluation.truncation_gap_max`
never clears a positive threshold.

Two consequences follow, and only the first is certain:

- The run pays a second cross-encoder pass on every truncated item for a number
  that is negative by construction. At the measured 6.1 percent truncation rate
  that is small, and it is not the argument for changing anything.
- The console's "Article read only in part" counter reads `truncation_flagged`.
  It said **1** when the committed ledger held **157** rows sitting on the cap.
  `Article.truncated` is already persisted and answers that question exactly.

**Why this is not closed by measurement.** No test may fetch the HHEM weights
(Rule #7), so the monotonicity claim above is an argument about the aggregation
rather than an observation of the scorer. Confirming it needs a run with the
weights present, and the honest first step is to look at `hhem_delta` on the
rows written since row 16 shipped rather than to reason further.

**The decision, when the evidence exists.** Either the second pass earns its
place under a different comparison, or `truncation_flagged` reads
`Article.truncated`, `evaluation.truncation_gap_max` is deleted as a knob
nothing reads, and the console counter is pointed at the flag that moved. The
second changes what a committed column means and what an operator page reports,
so it is Level 5 and needs an owner ruling before any of it is written.

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

No current threshold has a measured human error rate. Re-cutting the bands is a
Level-5 reader-facing decision, so no threshold moves until the evidence exists
(Rule #10).

### The three queue repairs shipped on 2026-08-27

A person could not use the queue. All three gaps are now closed.

- **The labeller was never shown the article.** `state/scores.csv` carries no
  summary text and no source text, so the CLI printed a fallback string on every
  row. The run now writes the exact premise the scorer read, plus the summary,
  to `backend/var/evidence/<date>/`, and the work job uploads it. The CLI shows
  both, and refuses any row whose text does not match its recorded digest. A row
  scored before that column existed is marked not labellable rather than guessed
  at. PR #178 added the `source_digest` column; PR #182 added the package.
- **The draw leaked the score stratum through its order.** `draw()` returned
  rows decile block by decile block, so a labeller working down the queue was
  handed the confidence gradient in order. It now returns one global `label_id`
  sort. Measured over the 38 rows at `draw_id=d1`: 9 runs of equal decile
  before, 28 after. PR #179.
- **A draw could silently mix pipelines.** `eligible()` filtered on
  `scorer_version` only, and warned about mixed fingerprints instead of refusing
  them. Both halves are now required. An empty pool exits non-zero and prints
  every `(scorer_version, pipeline_fingerprint)` pair in the ledger with its row
  count and date range. PR #179.

Measurement corrected one design note. A global hash shuffle removes the
ordering leak but **does not balance a prefix**. Over the same 38 rows the first
ten deciles run 9, 9, 8, 9, 9, 9, 5, 8, 9, 7. Balance holds in expectation, not
per draw, so stopping early gives a roughly balanced sample rather than a
guaranteed one.

### What is left is not engineering

**0 of 60 labels.** No `state/labels.csv` is committed.

**1 of 10 run-days, and 10 has never been reached.** The longest run of
consecutive run-days under a single pair is 3 - `2026-08-24` to `2026-08-26`,
under fingerprint `969b1917...d2b945` - and the stamp moved four times across
the five scored run-days the ledger held before today. The configured summarizer
`qwen3-5-9b-q4-k-m` wrote its first 114 rows on `2026-08-27`, under scorer
`hhem-2.1-open@8e4a2e6e` and fingerprint `6a23e277`, so the current window opened
today at one day. No earlier row can join it: every one of the 2,232 rows before
it was written by the retired `qwen3-8b-q4-k-m`. The reset mechanism, the
measured rate and the two ways out are stated once, in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).

Remaining steps, in order:

1. **The owner decides how the window is counted.** Freeze the pipeline for ten
   days and pay for the window in shipped improvements, or count run-days at one
   `scorer_version` and carry `pipeline_fingerprint` as a reported stratum. The
   first buys a narrow claim about one frozen pipeline, and that claim expires at
   the next fingerprint. The second fills now, but it confounds
   between-pipeline variance into the estimate, so it is a prior with honest wide
   bounds rather than a calibration. Nothing below can start until this is
   answered.
2. Collect the run-days the chosen rule asks for.
3. Draw and label 60 rows, six per HHEM decile. Keep the score, band,
   counterweights, model identity, fingerprint and running tally hidden.
4. Re-test the cuts by stratum. Move a threshold only when the labels support
   the new cut.

The canonical measurement contract lives in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 15 | `median()` returned `0` for an empty sample, so all four stage timings lost the difference between "not measured" and "measured as zero" before the chart saw them. `StageTimings.svelte` reconstructed absence from the value, which is a repair on top of a lost fact. | 2026-08-27, PR #180. `median()` returns `null`, `StageTimingDay` carries `number | null`, and the console reads the null directly. Both a missing timing and a real zero are pinned in `frontend/tests/console.spec.ts`. Recorded in [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md). |
| 16 | `dual_score` exists to tell "the model invented something" from "the model faithfully summarized the half we gave it", and its only production caller handed it `article.text` twice. Measured over the whole committed ledger: `hhem_delta` exactly 0.0 on **2,232 of 2,232 rows**. The run also paid for the duplicate pass - about 2 s an item, 21 to 24 minutes of runner wall-clock a day. | 2026-08-27. `extract.to_article_with_source` returns the payload beside the untruncated body; the body stays in the process that extracted it and is never persisted or republished (Rule #1). The work stage scores against it, and `dual_score` scores identical texts once. About 97 percent of items are never cut, so most now pay one pass instead of two. Stamped `2026-08-27T20:30` with the read-side rule: a row older than that stamp recorded two scores of one text, so its zero means "never measured". Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 17 | `source_word_count` came from `metrics.word_count(full_text)` and `source_seen_word_count` from `article.word_count` - the **same post-cap string** through two different counters. Read as a truncation signal the pair said 87 percent of items were truncated; the real rate is 6.3 percent. The proof is the impossible direction: `source_seen_word_count` was larger on **590 of 2,232 rows**, which cannot happen when one string is a cut of the other. | 2026-08-27. The column is `Article.source_word_count`, the pre-cap count the payload already carried, so one counter produces both numbers and the difference between them is the cut. An article written before that field existed reports its post-cap count rather than inventing a source length. Stamped `2026-08-27T20:00`. Proved by a test that builds its article through the real extractor, so the pair is a genuine cut. Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the label and calibration contract.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console timing surface defect 15 repaired.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - how closed rows leave this file.
