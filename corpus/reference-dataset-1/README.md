# Reference dataset 1

**Built**: 2026-09-13
**State**: built and unlabelled. Every label field is empty.

A frozen set of news articles, drawn from what this pipeline published, with the
article text beside each row. It exists so that an accuracy figure for the
article labels - the desk, the lenses, the article kind, and the stances and
sentiment that follow - means something a month after it was taken.

This is the datasheet. `docs/how-to/measure-a-classifier.md` is the procedure.

## What it is

| | |
| --- | --- |
| Built by | `backend/utilities/build_reference_dataset.py`, run by hand |
| Drawn from | the committed digest archive, `frontend/public/digest/` |
| Article text | `articles/<url_key>.txt`, one file an article |
| Rows | `dataset.jsonl`, one JSON object a line, shaped by `backend/idhazh/contracts/reference_dataset.py` |
| Splits | `splits/dev.txt` and `splits/test.txt`, committed lists of `url_key` |
| Labels | none yet. A person writes them - plan 23 row #P3 |

## What is in it

Measured 2026-09-13 by `build_reference_dataset.py verify`, on the set as
committed.

| | Rows | Registrable domains | Article words, median | p10 | p90 | Longest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 321 | 55 | 717 | 244 | 2,280 | 9,155 |
| `test` | 320 | 55 | 866 | 305 | 2,365 | 7,572 |
| **Total** | **641** | **110** | | | | |

- **4,657,791 bytes of article text**, in 641 files under `articles/`.
- Articles published **2026-08-21 to 2026-09-12**.
- The floors it was built to, from `config/idhazh.json`: 200 rows and 20
  registrable domains a side. Both sides clear both with room.
- **No outlet holds more than 7 rows**, which is 2.2 percent of either side.
  The largest is `hindustantimes.com` on `dev` and `amazon.science` on `test`.
- **All five verticals appear on both sides.** The commonest is `ai`, at 30.5
  percent of `dev` and 37.8 percent of `test`.

Two asymmetries worth knowing before quoting a number off this set. The `test`
side's articles are longer - a median of 866 words against 717, because the
split is drawn on the outlet and outlets differ in house length. And `ai` is 7.3
points heavier on `test` than on `dev`, for the same reason. Neither was tuned
away: levelling the two sides on the pipeline's own vertical would make them
agree by construction, which is the one property a measurement set must not
have.

**How it was drawn, in numbers.** `plan` read 23 committed days and 9,266
distinct articles, subtracted the 1,444 in the fine-tuning window and the 125 in
its holdout, and took at most 7 articles from each registrable domain - 735
candidates over 122 domains. `fetch` attempted all 735 in 28.9 minutes and 641
came back usable, which is **87.2 percent**; the other 94 were a robots refusal,
a paywall, a dead link or too little text to label. Twelve domains produced
nothing usable, which is why 110 domains are in the set and 122 were asked.



## How the split was drawn

**On the registrable domain, and an outlet lands wholly on one side.**

Two articles from one outlet share boilerplate, a house style and often the same
wire original. A split that separated rows rather than outlets would put
near-duplicates on both sides, and every number taken on it would come out better
than the classifier is - with nothing in the number saying so.

The registrable domain is the name somebody registered, read through the public
suffix list: `bbc.co.uk` stays whole, `economictimes.indiatimes.com` and
`timesofindia.indiatimes.com` are both `indiatimes.com`, and every newsletter on
`substack.com` counts as one outlet. Collapsing is the safe direction - it can
only move articles off one side, never spread one outlet across both.

Domains are then dealt out largest first, each to whichever side is behind on
row count. It is deterministic and there is no seed: the split is committed as
two lists and never recomputed, because a recomputed split moves when the row
order moves, and then last month's number and this month's number were taken on
different sets.

**There is no `train` split.** A train split in this directory would invite
fine-tuning on the measurement set, and that contamination is silent (owner
decision, 2026-09-10).

## What was checked before it was written

The builder refuses to write anything if any of these fails, and
`build_reference_dataset.py verify` asks the same questions of what is committed.

| Check | Why it is here |
| --- | --- |
| No `url_key` on both sides | The plain leak |
| No registrable domain on both sides | The leak that hides inside a passing row-level check |
| The two lists partition `dataset.jsonl` exactly | A row in no split is a row nobody measures |
| No `url_key` shared with `corpus/corpus.jsonl` | That file is the rolling fine-tuning window. An article in both was **trained on and then measured on** |
| No `url_key` shared with `corpus/holdout.txt` | The keys a fine-tune never trains on. An article in both spends one holdout twice |
| Each side clears its row floor and its domain floor | **A disjointness check passes on an empty set.** A builder that wrote everything to one side would pass every check above |
| Every article file matches the digest on its row | A label is a reading of a text. Edit the text and the label is a reading of nothing |

The floors are `reference_dataset` in `config/idhazh.json`, not literals, so the
set can be rebuilt at another size without a code change.

Every intersection is on `url_key` and never on article text. A near-duplicate
the two collections hold under two different addresses is a different problem,
and nothing here claims to catch it.

## What it may be used for

- Measuring how well a model reads a desk, a lens, an article kind, a stance or a
  sentiment off an article, against labels a person wrote.
- Comparing two classifiers on the identical rows.
- Measuring human-human agreement, which is what says whether a question is
  answerable at all.

## What it may not be used for

- **Training anything.** There is no train split, and an article that reaches the
  fine-tuning window has to leave this set or the measurement is worthless.
- **Faithfulness.** `labels.reference_summary` is a kept shape with no writer. A
  model-written summary is a legitimate reference for classification labels a
  person confirmed and is never a faithfulness reference (owner decision,
  2026-09-10).
- **An absolute accuracy claim.** See the next section.
- **A second pass over the test split.** Correcting a label on `dev` is free.
  Re-opening `test` - to settle a disagreement, to apply a sharpened definition -
  turns the held-out number into a tuned one, silently and without anybody
  choosing it.

## How to read a number taken on this set

Three rules, and none of them is optional.

- **Print the majority-class score beside every accuracy figure.** That is the
  score you get by always answering the commonest label on that same side. In the
  published archive, 84.4 percent of items carry `reporting` as their article
  kind (measured over 8,478 items, 2026-09-10). Without the baseline beside it,
  "84 percent accurate" reads as a result when it is the floor.
- **The independent unit is the outlet, not the article.** Rows from one outlet
  are not independent of each other, so a confidence interval computed from the
  row count is **too narrow**. Print the domain count beside the row count and
  say the interval is optimistic.
- **Treat it as a ranking instrument, not an accuracy meter.** At 200 rows and a
  true rate near 0.8 the 95 percent interval is about plus or minus 5.5 points
  (normal approximation; Wilson 73.9 to 85.0) - a window that straddles the
  majority-class floor. Two classifiers judged on the identical rows are compared
  with a paired test over the rows where they disagree, which is far more
  sensitive than either absolute number.

And one rule about small classes: **for any label with fewer than 10 rows on a
side, print the row count and no accuracy at all.**

## What it is not a fair sample of

Stated here because a number that does not carry its caveats gets quoted without
them.

- **It is what the pipeline published, not what the feeds carried.** `rank.py`
  selects up to `run.safety_ceiling_per_run` items a run out of a larger pool, so
  the set inherits every judgement in the selection score.
- **The fine-tuning window was subtracted, and that window is not a random
  sample.** `corpus/corpus.jsonl` is rejection-sampled on summary quality, and
  one of its filters is `unsupported_numbers == 0`. So the remainder this set was
  drawn from is **enriched in articles whose summaries failed that filter**. That
  cuts against flattery rather than towards it: the set is, if anything, harder
  than the published average.
- **It is one window of the news**, from the committed days that were in
  retention when it was built, in those languages, from those outlets.
- **Robots and paywalls removed articles, and not at random.** The outlets most
  likely to refuse a crawler are the ones most likely to be behind a paywall.
- **A rare label can land wholly on one side.** The split is drawn on the outlet
  and the outlet predicts the label: a preprint aggregator gives `research`, a
  ministry site gives `announcement`. The per-side spread of the pipeline's own
  vertical is printed above as the closest proxy that exists before anybody has
  labelled anything.

## This directory is public

This repository is public, so every article text under `corpus/` is readable by
anyone. That cost was taken on 2026-08-28 for the training corpus and is restated
here rather than assumed (`CLAUDE.md` section 0a). Nothing renders this text,
links to it, or serves it: no reader-facing page reads `corpus/`, and the
published site is built from `frontend/public/` alone.

## No model wrote any of this

A model writes no field of `dataset.jsonl`. The labels are a person's and
`labels.labelled_by` records whose. There is no model verdict in this set to
weigh against `CLAUDE.md` section 0a.

## What a person does next

Plan 23 row #P3. Read every article in both splits and write the labels, against
the committed definition text in `config/taxonomy.json`, recording which version.
A second person independently labels 60 items of `dev`, and the two labellings
are compared with **Cohen's kappa** - two raters, a nominal scale, per field -
with the raw agreement percentage reported beside it and never instead of it.

When that pass lands, this datasheet gains: who labelled, when, against which
definition version, and the kappa and the raw agreement as a pair.

## See also

- [`../../docs/how-to/measure-a-classifier.md`](../../docs/how-to/measure-a-classifier.md) - the procedure, and the four verbs that built this.
- [`../../docs/how-to/fine-tune-a-model.md`](../../docs/how-to/fine-tune-a-model.md) - `corpus/corpus.jsonl` and `corpus/holdout.txt`, the two collections this set must not overlap.
- [`../../TODO/20260910-23-article-classification-plan.md`](../../TODO/20260910-23-article-classification-plan.md) - rows #P2 and #P3.
