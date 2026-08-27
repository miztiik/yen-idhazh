# Known defects

**Last Updated**: 2026-08-27

Three defects remain open, and none of the three closes on engineering alone.

Defect 2 needed three engineering repairs before a person could label anything.
All three shipped on 2026-08-27. What is left is 60 human labels and a run-day
window that has never once been met, and neither of those is code.

Defects 16 and 17 were found on 2026-08-27 while shipping defect 2, and both
were found by measuring the committed ledger rather than by reading it. Each
changes what a column means across 2,232 committed rows, so each is a Level-5
call for the owner.

Defect 15 closed on 2026-08-27.

Closed rows are removed after checking their current production code, regression
tests and canonical docs. Git history holds their execution record; the living
docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Rule #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - queue repaired; 0 of 60 labels; 1 of 10 run-days, and 10 has never been reached** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 3 | CLOSED 2026-08-27 (PR #180) |
| 16 | The truncation-gap detector has never been fed, and the run pays twice for the answer | 5 | **OPEN - owner approved 2026-08-27; not yet shipped** |
| 17 | Two different word counters share one string and read as truncation | 5 | **OPEN - owner approved 2026-08-27; not yet shipped** |

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

## 16 - The truncation-gap detector has never been fed (OPEN)

`dual_score` exists to tell two different defects apart. Its own docstring says
the gap between its two numbers "is the only thing that separates them": a model
that invented something, and a model that faithfully summarized the half we gave
it.

Its only production caller hands it the same string twice.

```python
seen = article.text or ""
hhem, hhem_full = dual_score(scorer, seen_text=seen, full_text=seen, summary=...)
```

Measured 2026-08-27 over the whole committed `state/scores.csv`, 2,232 rows:
`hhem_delta` is **exactly 0.0 on 2,232 of 2,232 rows**, and `hhem` equals
`hhem_full` on all 2,232. The detector has never once carried information.

There are two consequences, and the second one pays for the first.

- **`article.text` is post-truncation.** `extract.truncate_to_tokens` returns the
  cut string and `to_article` keeps only that, so the untruncated text is gone
  before the scorer is called. Keeping it in memory through the work stage needs
  no new field and no schema stamp.
- **The run already pays for the wasted pass.** `dual_score` does not
  short-circuit on identical input, so every item is scored twice for an answer
  that cannot differ. Measured on `ubuntu-latest`, 2026-08-26, run
  `2026-08-26-5`: one pass over a 900-word chunk takes 2.88 to 3.08 s (n=5), and
  `score_ms` wraps both passes. The duplicate costs about 2.0 s per item on
  average, which is **21 to 24 minutes of runner wall-clock a day, thrown away**
  at the observed 621 to 731 items.

Carmack ruled on 2026-08-27: fix it properly, and short-circuit as well. About
97 percent of items are untruncated, so the second pass is skipped for almost
all of them and saves roughly 19 minutes a day; the truncated remainder costs 2
to 15 minutes back. **The result is break-even to about 17 minutes a day cheaper
than what runs now**, and the detector starts working. Deleting the three
columns was considered and rejected: they have never carried information because
they have never been fed, which argues for feeding the socket rather than
pulling it out.

The same defect sits in `_score_item` and `stage_validate`, and `_freeze`
digests one string into both `seen_text_sha256` and `full_text_sha256`.

**Why this goes to the owner.** The in-memory plumbing is Level 3. Changing what
`hhem_full` and `hhem_delta` *mean* is a semantic shift on a persisted contract
across 2,232 committed rows: every one of them says "these two numbers were
equal", and after the change that sentence means something else. Section 11 asks
for a version stamp and a read-side migration, and section 6 sends a semantic
shift on a persisted contract to Level 5.

## 17 - Two different word counters share one string (OPEN)

`score.to_eval_row` writes `source_word_count` from `metrics.word_count(full_text)`
and `source_seen_word_count` from `article.word_count`. Both come from the **same
post-cap string**, counted two different ways: `len(_WORD.findall(text))`
against `len(text.split())`. The pair looks like "before truncation" and "after
truncation" and is nothing of the kind.

Measured 2026-08-27 over all 2,232 committed rows:

| What | Rows |
| --- | --- |
| The two counters agree | 287 |
| `source_word_count` is larger - reads as truncation | 1,355 |
| `source_seen_word_count` is larger - **impossible if one is a cut of the other** | **590** |
| `source_seen_word_count` sits exactly on the 1,923-word cap | 141 |

Those 590 rows are the proof. A truncated string cannot hold more words than the
string it was cut from, so a column pair that disagrees in both directions is
measuring two counters, not one cut.

Read the pair as a truncation signal and it says **87 percent of items were
truncated**. Count the rows sitting on the cap and it says **6.3 percent**. The
first number is wrong by a factor of fourteen. It was quoted inside this project
before Carmack caught it, which is the argument for fixing the column rather
than writing the caveat down.

The fix is one line - write `article.source_word_count`, the pre-cap count the
`Article` already carries. It is Level 5 for the same reason as defect 16: it
changes what a column means across every committed row, and anything that has
ever read those two columns as a truncation rate read a number that was not
there.

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the label and calibration contract.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console timing surface defect 15 repaired.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - how closed rows leave this file.
