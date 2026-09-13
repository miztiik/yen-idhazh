# Measure a classifier

**Last Updated**: 2026-09-13

How `corpus/reference-dataset-1/` is built, why it is built that way, and what a
person does with it. It exists so that an accuracy figure for the article
labels means something a month after it was taken.

Labelling itself is not here. What a desk, a lens or an article kind means is
[`../concepts/classification.md`](../concepts/classification.md) and
[`../concepts/taxonomy.md`](../concepts/taxonomy.md).

## What exists today

| Piece | Where | Who runs it |
| --- | --- | --- |
| The row shape | `backend/idhazh/contracts/reference_dataset.py` | nothing; it is a contract |
| The floors the set is built to | `config/idhazh.json`, block `reference_dataset` | read by the builder |
| The builder, four verbs | `backend/utilities/build_reference_dataset.py` | a person, by hand |
| The frozen set | `corpus/reference-dataset-1/` | written once, then labelled |
| The labelling pass | a person | plan 23 row #P3 |

## Why a frozen set rather than the archive

The committed archive grows every four hours and carries no label. A number
taken over a moving set cannot be compared with itself: the figure moves when
the classifier moves **and** when the week's news moves, and nothing on the
number says which happened. Reading the archive once an item is also a
`CLAUDE.md` Guardrail #12 breach.

So the set is drawn once, the articles are copied into it, and it does not
change. Every accuracy figure names the set and the definition text it was taken
against.

## The one rule the whole thing is built around

**No source outlet appears on both sides of the split.**

Two articles from one outlet share boilerplate, a house style and often the same
wire original. A split that separates rows rather than outlets therefore puts
near-duplicates on both sides, and every number taken on it comes out better
than the classifier is. Nothing about that failure is visible in the number.

So the unit of the split is the **registrable domain** - the name somebody
registered, read through the public suffix list, so `bbc.co.uk` stays whole and
every newsletter on `substack.com` counts as one outlet. An outlet lands wholly
on one side. `build_reference_dataset.py split` refuses to write a set where any
domain reaches both.

**A disjointness check passes on an empty set**, which is why it is never the
only check. A builder that wrote every article to `dev.txt` and left `test.txt`
empty satisfies "no domain on both sides" perfectly. The floors are what it
cannot satisfy: `reference_dataset.rows_per_split_min` rows and
`reference_dataset.domains_per_split_min` registrable domains on **each** side.

## The three collections this set must not overlap

Each is the same contamination arriving by a different door, and each is checked
on `url_key` rather than on article text.

| Collection | What an overlap would mean |
| --- | --- |
| `dev` and `test` | The plain case. A figure on the held-out side was taken on an article the dev side was tuned against |
| `corpus/corpus.jsonl` | The rolling fine-tuning window. An article in both was **trained on and then measured on**, and every figure comes out flattering with nothing in the record saying why |
| `corpus/holdout.txt` | The keys a fine-tune never trains on. An article in both spends one holdout twice |

A near-duplicate the two collections hold under two different addresses is a
different problem, and none of these checks claims to catch it.

**There is no `train/` split.** A train split in the same directory invites
fine-tuning on the measurement set, and that contamination is silent (owner
decision, 2026-09-10).

## Building it

From the root of a checkout, in this order. Only `plan` reads the archive, and
only `fetch` touches the network.

```powershell
python backend/utilities/build_reference_dataset.py plan
python backend/utilities/build_reference_dataset.py fetch
python backend/utilities/build_reference_dataset.py split
python backend/utilities/build_reference_dataset.py verify
```

- **`plan`** walks every committed day, subtracts the fine-tuning window and its
  holdout, and takes at most `reference_dataset.rows_per_domain_max` articles
  from each registrable domain, round-robin. Without that cap the set is the two
  largest wire services and a tail.
- **`fetch`** takes each article's text, honouring `robots.txt`, one request at a
  time with `reference_dataset.request_delay_seconds` between them. It is
  resumable: an article already on disk is skipped, so an interrupted pass is
  restarted rather than redone. The text crosses the trust boundary once, through
  the same trafilatura-plus-sanitizer path the pipeline uses (Guardrail #11).
- **`split`** draws the split and **refuses to write anything** if any check
  above fails. It names what failed.
- **`verify`** re-runs every check over what is committed, and adds one more: the
  digest of every article file against the digest its row carries. A label is a
  reading of a text, so a text edited in place makes its label a reading of
  nothing.

`plan` is the one growing read and it is a verb a person types, never a step
anything schedules (Guardrail #12). Measured 2026-09-13 on an Intel Core
i7-1265U: 23 committed days, 24,244,409 bytes, 9,278 items, 1.3 seconds. It
rises by about one day and 1 MB every day the pipeline runs. Nothing repeats it:
the tests are driven from `tests/fixtures/reference-dataset/`, and `verify`
reads only the frozen set and the capped fine-tuning window.

## What the set is not a fair sample of

Stated here and on the set's own datasheet, because a number that does not carry
its caveats gets quoted without them.

- **It is what the pipeline published**, not what the feeds carried. `rank.py`
  selects up to `run.safety_ceiling_per_run` items a run out of a larger
  candidate pool, so the set inherits every judgement in the selection score.
- **The fine-tuning window was subtracted**, and that window is rejection-sampled
  on summary quality - one of its filters is `unsupported_numbers == 0`. So the
  remainder is **enriched in articles whose summaries failed that filter**. That
  cuts the other way from the usual worry: the set is, if anything, harder than
  the published average rather than easier.
- **It is one window of the news.** The articles come from the committed days
  that were in retention when it was built. A model measured on it is measured on
  that period's stories, in those languages, from those outlets.
- **Robots and paywalls removed articles from it**, and they are not removed at
  random: the outlets most likely to refuse a crawler are the ones most likely to
  be behind a paywall.

## What a person does next

Row #P3 of [`../../TODO/20260910-23-article-classification-plan.md`](../../TODO/20260910-23-article-classification-plan.md).
A person reads every article in both splits and writes the labels; an agent may
prepare the tooling and the sheet, and may not supply the labels.

Two rules bind that pass:

- **Labels are taken against the committed definition text**, and the row records
  which version. A label taken against last month's definition measures a
  different question.
- **The test split is opened once.** Correcting a label on the dev split is free.
  A second pass over the test split - to settle a disagreement, to apply a
  sharpened definition - turns the held-out number into a tuned one, silently and
  without anybody choosing it. When the definition text changes, every figure
  taken against the old text is marked stale rather than deleted, because the
  before-and-after is the interesting comparison.

Agreement between two people is reported as **Cohen's kappa** - two raters, a
nominal scale, computed per field - with the raw agreement percentage beside it
and never instead of it. On a mostly-`not_applicable` scale two raters who both
decline every time reach about 80 percent raw agreement at a kappa near zero.

## No model verdict is in this set

A model writes no field of `dataset.jsonl`. The labels are a person's and
`labels.labelled_by` records whose. That keeps the set clear of `CLAUDE.md`
section 0a without having to lean on the property it states: there is no model
verdict here to test against it.

## See also

- [`../../CLAUDE.md`](../../CLAUDE.md) - Guardrail #10 for what a number owes, Guardrail #12 for the growing read, section 13 for why no test walks this set.
- [`../concepts/evaluation.md`](../concepts/evaluation.md) - how quality is measured in this project, and what a judge may not do.
- [`../concepts/growing-reads.md`](../concepts/growing-reads.md) - the escape hatch `plan` is taken under.
- [`fine-tune-a-model.md`](fine-tune-a-model.md) - `corpus/corpus.jsonl` and `corpus/holdout.txt`, the two collections this set must not overlap.
