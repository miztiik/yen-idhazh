# Known defects

**Last Updated**: 2026-08-27

**One defect remains open, and it does not close on engineering.** Defect 2
needed three repairs before a person could label anything, and all three
shipped. The owner settled the counting rule on 2026-08-27, which took the
draw from 32 of 60 to 60 of 60. What is left is **60 human labels** and eight
more run-days at one scorer. Neither is code, so **this file cannot be deleted
by writing more of it.**

Defects 15, 16 and 17 closed on 2026-08-27.

Closed rows are removed after checking their current production code, regression
tests and canonical docs. Git history holds their execution record; the living
docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Rule #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - queue repaired, counting rule settled; 0 of 60 labels; 2 of 10 run-days** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 3 | CLOSED 2026-08-27 (PR #180) |
| 16 | The truncation-gap detector has never been fed, and the run pays twice for the answer | 5 | CLOSED 2026-08-27 |
| 17 | Two different word counters share one string and read as truncation | 5 | CLOSED 2026-08-27 |

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

**2 of 10 run-days.** The owner settled the counting rule on 2026-08-27: count
run-days at one `scorer_version`, and carry `pipeline_fingerprint` as a reported
stratum rather than a disqualification. The pair rule it replaced was
unreachable - the stamp digests seventeen inputs, so a reworded prompt or a
sanitizer fix reset the count, and no pair ever held for more than three
consecutive run-days. Measured effect on the same ledger: the drawable sample
went from 32 of 60 with seven deciles short to **60 of 60**, over 450 eligible
rows at `hhem-2.1-open@8e4a2e6e`. What it gives up is stated wherever a result
prints: a rate over a pooled draw is a prior with wide bounds, and a stratum
under `evaluation.label_min_stratum_rows` may not move a threshold. The rule,
the rejected freeze and the measured reset rate are stated once, in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).

**The evidence packages are not on this machine.** `label_queue.py` reports
`labellable 0 of 60`: 34 rows have no package here, and 26 predate the
`source_digest` column and can never be proved against their article. The run
writes packages to `backend/var/evidence/<date>/` and the `work` job uploads
them, so a labeller downloads that artifact before starting. Nothing is broken;
the evidence simply lives where the run put it.

Remaining steps, in order:

1. Download the evidence artifact for the run-days in the draw.
2. Draw and label 60 rows, six per HHEM decile. Keep the score, band,
   counterweights, model identity, fingerprint and running tally hidden.
3. Collect the remaining run-days at `hhem-2.1-open@8e4a2e6e`.
4. Re-test the cuts by stratum. Move a threshold only when the labels support
   the new cut, and never on a stratum under the floor.

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
