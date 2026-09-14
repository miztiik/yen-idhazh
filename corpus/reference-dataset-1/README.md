# Reference dataset 1

**Built**: 2026-09-13
**Labelled**: 2026-09-13, all rows. **Read "Who wrote the labels" below before
quoting any number taken on this set** - it is not a person-written set, and that
changes what the number means.
**Cleaned**: 2026-09-14. 34 rows left the set; see "What was removed".

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
| Labels | all 607 rows. 500 taken 2026-09-13 against `config/taxonomy.json` `2026-09-12`, 107 re-taken 2026-09-14 against `2026-09-14`. Written by `backend/utilities/label_reference_dataset.py` |
| Removed | `removed.tsv`, one line an article that left the set and why |

## What is in it

Measured 2026-09-13 by `build_reference_dataset.py verify`, on the set as
committed.

| | Rows | Registrable domains | Article words, median | p10 | p90 | Longest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `dev` | 312 | 55 | 717 | 244 | 2,280 | 9,155 |
| `test` | 295 | 52 | 866 | 305 | 2,365 | 7,572 |
| **Total** | **607** | **107** | | | | |

- **607 article files** under `articles/`, one a row. The set was built with 641
  and 34 were removed on 2026-09-14.
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

- Comparing two classifiers on the identical rows. This is the strongest thing it
  supports today.
- Measuring how well a model reads a desk, a lens, an article kind, a stance or a
  sentiment off an article, **against the labels committed here** - which as of
  2026-09-13 a model wrote. See "Who wrote the labels".
- Measuring human-human agreement, once a second, independent person has labelled
  part of it. Nothing committed here supports that yet.

## What it may not be used for

- **Training anything.** There is no train split, and an article that reaches the
  fine-tuning window has to leave this set or the measurement is worthless.
- **Faithfulness.** `labels.reference_summary` carries the labeller's own summary
  from 2026-09-13. It is a reference for classification labels and is never a
  faithfulness reference (owner decision, 2026-09-10).
- **A claim about agreement between raters.** `second_labels` is one labeller's
  alternative reading, not an independent second rating, so no Cohen's kappa may
  be computed from it.
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

## Who wrote the labels

**Agents wrote them, at the owner's direction and on the owner's behalf, and the
owner ruled that the rows record `labelled_by` of `human`** (owner decision,
2026-09-13, `CLAUDE.md` section 0). Each article was read in full from
`articles/<url_key>.txt`; no label was taken from a title. This paragraph exists
because who wrote a label is the single fact every number taken on this set
depends on, and a datasheet that leaves it to be inferred is the datasheet that
gets quoted wrongly.

**What it costs, stated rather than implied.** Plan 23 row #18 measures this
project's classifier against these labels. Both sides of that comparison are now
model-written, so the figure says how well a small local model reproduces a large
one's reading - not how well it reproduces a person's. **It is a ranking
instrument between classifiers, and it is not an accuracy claim against human
judgement.** A person relabelling any part of this set turns that part back into
the stronger measurement, and the dev split is free to relabel.

**There is no Cohen's kappa, and there cannot be one from this set.**
`second_labels` is filled on 367 rows, but it is the *same* labeller's
alternative reading - the second-best answer where one genuinely existed - not an
independent second rating. Agreement between one reader and itself measures
consistency, not whether a question is answerable. So plan 23 row #11's kill
criterion, which needs human-human kappa above 0.6 on 60 dev items, **remains
un-evaluated**, and row #11 may not ship on the strength of anything here.

## What the labels say

Whole set, 607 rows, after the 2026-09-14 clean and re-label.

| Field | Distribution |
| --- | --- |
| `desk` | `ai` 187 (30.8%), `energy` 130 (21.4%), `business-economy` 101 (16.6%), `world` 87 (14.3%), `india` 60 (9.9%), `science` 26 (4.3%), `climate` 16 (2.6%) |
| `lenses` | empty on 469 (77.3%); `markets` 33, `china` 29, `war` 29, `trade` 21, `cyber` 18, `chips` 16, `climate` 14 |
| `definition_version` | `2026-09-12` on 500 rows, `2026-09-14` on the 107 re-read when the vocabulary changed |

`article_kind`, `sentiment` and `stances` are as they were on 2026-09-13:
`report` about 54 percent, `announcement` about 18, sentiment null on about 80,
and the political gate shut on every `report`, `research` paper and company
`announcement`.

**The read desk disagrees with the feed's declared vertical on 186 of 607 rows -
agreement is 69.4 percent**, down from 73.3 on 2026-09-13. It fell because the
two new desks are ones **no feed declares**, so all 42 rows on `science` and
`climate` disagree by construction. That is the gap plan 23 exists to close, and
it is now larger and more honest than it was.

**The feed says 84.4 percent of published items are `reporting`. Read from the
text it is about 54 percent `report`**, with about 18 percent `announcement` -
vendor blogs, ministry notices and press releases the feed files as journalism.

## What was removed, and why

34 of the original 641 rows left the set on 2026-09-14. `removed.tsv` carries one
line each with the reason, the split it was on, its outlet and a sentence of
evidence; the article text went with it and git holds both.

| Reason | Rows | What it means |
| --- | --- | --- |
| `truncated` | 17 | Something the piece promised is absent - a list that opens and stops, a comparison that covers one side, the event the title names |
| `many-articles` | 14 | The file concatenated two or more unrelated stories, each with its own lede. Mostly live blogs, newsletter editions and video-brief pages |
| `no-article` | 2 | No reporting at all. One is seven "About NVIDIA" boilerplate blocks; one is sixty bare headlines |
| `title-mismatch` | 1 | The file's subject is a different story from the one the title names |

**Why remove rather than flag.** A row whose text does not support its own title,
or stops before its argument lands, cannot be labelled - so a classifier scored
against it is being asked to reproduce a guess. Keeping it and marking it would
mean every later reader re-deciding whether to include it, and the answer would
drift. Removing it costs the set 5.3 percent of its rows and both splits stay
well clear of their floors.

**Every removal was verified against the text by a second reader, and 8 of the 42
proposed removals were cleared.** The labellers' flags were the claim; a
verification pass tested each one and disagreed with about one in five - a short
abstract page called truncated, a related-papers rail called a second article, a
reading-tool artefact mistaken for a truncation marker. Those eight are still in
the set. **That is the reason the pass exists: a row removed on hearsay is worse
than a row left in.**

**The census is not exhaustive.** These 34 are the rows twenty labellers happened
to flag while labelling. Nothing scanned the other 573 for the same defects, and
a detector was not built: the project already measured one - an article ending
without a full stop - calling 198 complete articles truncated.

## The vocabulary gained two desks and a lens on 2026-09-14

`science`, `climate` and a `climate` lens, all committed as **drafts** - defined,
labellable, and offered to no prompt and no page because no feed declares either
word. [`../../docs/concepts/taxonomy.md`](../../docs/concepts/taxonomy.md)
carries the eight tie-breaks that decide them and the four desks nobody has
built.

107 rows were re-read in full against the new vocabulary: the 68 a screening pass
nominated, plus the 39 whose `article_kind` is `research`, which the widened
`science` definition could take. **46 moved and 61 stayed.** Those 107 carry
`definition_version` of `2026-09-14`; the other 500 carry `2026-09-12`, which is
the field doing its job - it says which vocabulary each label was taken against.

**The rows that did not move were not re-read.** A row on `ai` or `india` that
nothing nominated still carries a label taken when five desks existed. The
screen read titles and summaries rather than articles, so it will have missed
some.

## The vocabulary still did not fit about one row in five

Twenty readers labelled this set without seeing each other's work, and they
reported the same holes. The count is how many of the twenty named it.

| Missing | Named by | A row forced by its absence |
| --- | --- | --- |
| ~~a **science** desk~~ | 13 | **Filled 2026-09-14.** A NIST gravitational-constant measurement is now `science`, not `business-economy` |
| ~~a **climate** desk and lens~~ | 11 | **Filled 2026-09-14.** 26 million Canadians facing climate impacts is now `climate`, not `world` |
| a **consumer technology / software** desk | 9 | a Windows 11 update breaking mouse cursors, filed `business-economy` |
| a **culture / sport** desk | 9 | Messi's international retirement, filed `world` |
| a **health** desk | 8 | Pennsylvania measles deaths, filed `world` |
| an **environment** desk that is not climate | 5 | a PFAS contamination settlement - `climate` covers greenhouse gases and this is chemistry |
| a **crime / courts** desk | 5 | a Melbourne murder trial, filed `world` |
| a **privacy / surveillance** lens | 4 | Georgian state face recognition - `cyber` means an attack, not this |
| a **compute build-out** lens | 4 | data-centre grid load, which crosses `ai` and `energy` |

**`business-economy` absorbed most of them**, which is the residual being used as
a shrug. Every such row got the closest legal id and none invented one, so the
set is internally valid - but a classifier scored on those rows is being asked to
reproduce a forced choice. Treat the desk figure as optimistic until the
vocabulary moves.

Also reported: no `article_kind` names an interview, a tutorial, a fact-check, a
link roundup, sponsored content, or a profile. Those landed on `report`,
`analysis`, `announcement` or `opinion` by the who-is-speaking test.

## Two more faults, which removing rows did not fix

The 34 unusable rows are gone. Two things the readers found are still in the set,
because neither is a reason to drop a row.

- **Several rows are wholly in Devanagari.** The ASCII rule and the "every name in
  the summary appears in the article" rule cannot both hold there, so those
  summaries carry transliterated names. The labels are sound; the summaries are
  not literal quotations of the text.
- **Many rows carry publisher furniture inside the article body** - a subscription
  block mid-paragraph, an affiliate advertisement, a donation appeal, an author
  biography, a cookie line. It is noise a summariser reads and it did not stop
  anybody labelling.

**No article tried to instruct a labeller. Zero attempts across all 641 read.**
Several carry reader-directed imperatives - subscription pitches, affiliate
blocks, "add us as a preferred source" - and several quote prompts or attack
techniques as subject matter. One prints a shell command. None was aimed at the
labelling task, and none of it reached a shell, a path or a URL.

## What a person does next

Relabel the dev split, or any part of it, and the measurement it supports becomes
a model-against-person figure rather than a model-against-model one. Corrections
on `dev` are free. **The test split is opened once**, so a second pass over it
turns the held-out number into a tuned one; if it is relabelled, every figure
taken against the current labels is marked stale on the same day rather than
deleted.

A second, independent reader labelling 60 dev items is what unlocks the Cohen's
kappa this set does not have.

## See also

- [`../../docs/how-to/measure-a-classifier.md`](../../docs/how-to/measure-a-classifier.md) - the procedure, and the four verbs that built this.
- [`../../docs/how-to/fine-tune-a-model.md`](../../docs/how-to/fine-tune-a-model.md) - `corpus/corpus.jsonl` and `corpus/holdout.txt`, the two collections this set must not overlap.
- [`../../TODO/20260910-23-article-classification-plan.md`](../../TODO/20260910-23-article-classification-plan.md) - rows #P2 and #P3.
