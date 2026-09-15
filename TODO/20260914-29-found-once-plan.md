# Plan 29 - the same story, found once

**Last Updated**: 2026-09-14

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Guardrail #4).

## Why this plan exists

Defect 22 closed on 2026-09-14 and fixed the visible tip of the problem, not the
problem. The pass now groups two items whose published headlines say the same
thing, which took the one-headline cross-source groups still left apart from 27
of 42 down to 1 over the committed days.

**Then the Editor read a full day by hand and the picture changed.** On
2026-09-12 - 356 items, 61 sources - about **95 items, 27 percent of the day**,
sit in a cross-source cluster. The pass found 12, and 4 of those were one outlet
counted twice, so the true figure was **8 of 95**. Byte-identical headlines were
never most of the duplication; nine outlets writing nine different headlines
about the New Delhi Declaration is.

**Owner ruling, 2026-09-14: a duplicate is worse than a miss.** "Having
duplicates is worse than having none - as app owner. It wastes readers' time and
loses attention and interest span." This reverses the lean recorded in
[`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md)
under `What chose 0.94`, which set the threshold high because a false merge
costs a story nobody can see is missing. That reasoning still holds **the day
the collapse is drawn**, and until then the ruling stands: reach for recall.

## What the rest of the world does

Read on 2026-09-14. Two papers carry the load and one of them contradicts the
design we have.

**Miranda et al., "Multilingual Clustering of Streaming News", EMNLP 2018**
([arXiv:1809.00540](https://arxiv.org/abs/1809.00540)). The reference online
news clustering system, and the closest match to our problem shape.

| What they do | What it means here |
| --- | --- |
| A document is **not one vector**. It is several TF-IDF sub-vectors - words, lemmas, named entities - and **each is repeated for the title, the body, and both together**. | Our single `title. summary` vector is the thing their design exists to avoid. A title sub-vector is not an optimisation, it is the baseline. |
| Similarity is a **weighted sum of the per-sub-vector cosines**, weights learned by SVM-rank. | One threshold over one cosine is the weakest form of what they built. |
| **Three timestamp features** - Gaussian decay against the newest, mean and oldest document in the cluster, sigma 72 hours. | Adding them moved English F1 92.7 to 94.1, German 90.7 to 97.1, Spanish 88.8 to 94.2. We group within one published day and use no time signal at all. |
| **Embeddings did worse than TF-IDF** for same-language clustering: F1 **74.8 against 92.7**. | Directly contradicts our approach. Worth testing on our data before buying a second encoder. |
| A learned classifier decides when to open a new cluster, beating a tuned threshold: F1 **82.8 to 94.1**. | The "is this a new story" decision is a different question from "how similar are these two", and we answer both with one number. |
| Evaluation is **pairwise** precision, recall and F1 over clustered-together pairs. | The protocol below is theirs. |

**Liu et al., "Growing Story Forest Online from Massive Breaking News", CIKM
2017** ([arXiv:1803.00189](https://arxiv.org/abs/1803.00189)). Tencent's
production system over 60 GB of news. Two layers: cluster **keywords** into a
keyword graph first, then documents into events inside that graph, then events
into story trees. It exists because their stream "contains highly redundant
information" - the same problem in the same words. The transferable idea is the
**two-stage shape**: a cheap blocking pass that proposes candidates, then an
expensive pass that judges only those.

Ground News and Event Registry (Leban et al., WWW 2014) publish no method, but
both are centroid clustering over entity-and-token features with a time window,
which is the same family.

### Easy to hard, with what each buys

| id | Move | Effort | What it buys | Evidence it works |
| --- | --- | --- | --- | --- |
| E1 | **Count an outlet once, not once per feed** | Trivial | Removes a false sentence | Measured: 3 of 42 groups were CGTN with CGTN. Row #2 |
| E2 | **Stop printing the sentence we cannot support** | Trivial | Removes a false sentence | Row #1 |
| E3 | **TF-IDF over headline words, per day** | Half a day, no encoder, no new field | Miranda's own best monolingual feature | F1 92.7 against 74.8 for embeddings, in their data. Untested in ours - row #3 measures it |
| E4 | **Title-only encoder vector** | Half a day, one new persisted field | The labelled false pair drops 0.9317 to 0.7824; two missed true pairs go to 1.0000 and 0.9706 | Row #3 measures it |
| E5 | **Weighted sum of several similarities** instead of one cosine | Days | Miranda's core result | Needs the labels row #3 produces |
| E6 | **Two-stage: cheap blocking, then a judge on the survivors** | Days | Story Forest's shape; also the only way off the quadratic in note 28 | A cross-encoder over ~25 candidate pairs a day fits the runner easily |
| E7 | **Time-decay features** | Days | Their single largest single gain | We group within one day, so the gain is smaller here. Unmeasured |
| E8 | **A canonical "what happened" line from the summariser**, encoded instead of the summary | Weeks | Reaches pairs whose headlines genuinely differ | Cannot be backfilled - no committed day can measure it |

## Status Reckoner

| # | Row | Depends on | Wave | Status | Worker | PR | Worktree |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Stop printing "Only one of our sources carried this" | - | A | PENDING | - | - | dedup2 |
| 2 | Two feeds of one outlet are one source | - | A | PENDING | - | - | dedup2 |
| 3 | Measure: title signal against the committed days | - | A | PENDING | - | - | dedup2 |
| 4 | Correct the token-share number defect 22 shipped | - | A | PENDING | - | - | - |
| 5 | The title arm, at a floor row #3 sets | 3 | B | PENDING | - | - | - |
| 6 | Draw the collapse | 3, 5 | C | PENDING | - | - | - |

Rows 1, 2 and 3 are written and gated in the `dedup2` worktree; they flip to
DONE with a PR number once that merges. Row #3's machine half is finished and
its numbers are below - what is outstanding is the human labelling pass.

## Row #1 - stop printing the sentence we cannot support

- **Scope:** `coverage()` in `frontend/src/lib/components/ItemMeta.svelte` returns
  null at 0 as well as at null. Nothing else changes; `also_covered_by` keeps
  its meaning and the projection keeps the field.
- **Why:** printed **5,176 times** over the committed days against 91 for the
  positive form. The Editor's read of 2026-09-12 says roughly a quarter of the
  items carrying it were on the page more than once. On 2026-09-03 five cards
  said it about an acquisition that ran 13 times on the same page, while three
  other cards on that page said the story was covered twice.
- **What the reader loses, stated:** the genuine signal that a story is an
  exclusive. It comes back when row #3 has measured recall.
- **Oracle:** a reading-page test asserts nothing is drawn at 0, and the existing
  assertions at 1 and at N stay.

## Row #2 - two feeds of one outlet are one source

- **Scope:** `outlet_of` in `backend/idhazh/assemble.py`, used by the
  across-sources refusal and by the `also_covered_by` count.
- **Why:** `source_id` is a feed. Four of our feeds are CGTN and two are The
  Straits Times. Measured 2026-09-14: **3 of the 42 groups** on the committed
  days were one outlet grouped with itself, each printing a corroboration the
  reader did not have.
- **Where the line falls:** `source_name` is the masthead and separates 143 of
  160 feeds. It deliberately does not fold two mastheads of one owner - The
  Hindu and The Hindu BusinessLine are different papers with different desks.
- **Oracle:** two tests, one either side of that line, and the first fails when
  the rule is reverted to `source_id`.

## Row #3 - measure the title signal

- **Scope:** three frozen days named before scoring - 2026-08-24 (730 items),
  2026-08-29 (366), 2026-08-30 (431), the last because it holds the one pair a
  person has labelled TWO STORIES. Four scorers over the same cross-outlet
  pairs: the combined cosine we already have, the same encoder over the headline
  alone, per-day TF-IDF over headline words, and the shipped headline rule.
- **Protocol:** one person labels a shuffled sheet carrying only the two
  outlets and the two headlines - **no scores, no indication of which rule fired**.
  Three verdicts: SAME EVENT, RELATED BUT DIFFERENT, UNRELATED.
- **Read-out:** a precision curve per scorer, and the first honest precision
  figure for the rule that shipped.
- **What it does not measure:** recall. Every candidate is found by a rule, so
  the denominator is missing. The Editor's position is that recall needs a
  hand-labelled **full day**, not a pair sample. That is a second measurement.

### What the machine half already says

Measured 2026-09-14 on a developer machine / Python 3.14.2, 1,527 items over the
three frozen days, **597 candidate cross-outlet pairs** - every pair scoring 0.70
or more on any of the three scorers, plus every pair the shipped rule fires on.
The counts are deterministic and have no spread.

| Scorer | Floor | Pairs found | New, against the rule that ships today |
| --- | ---: | ---: | ---: |
| **The rule that ships today** | - | **16** | - |
| combined `title. summary` | 0.95 | 7 | 0 |
| combined | 0.90 | 67 | 54 |
| combined | 0.85 | 154 | 139 |
| combined | 0.80 | 279 | 264 |
| **title, same encoder** | **0.95** | **21** | **6** |
| title, same encoder | 0.90 | 50 | 35 |
| title, same encoder | 0.85 | 86 | 71 |
| title, per-day TF-IDF | 0.80 | 18 | 4 |
| title, per-day TF-IDF | 0.75 | 26 | 12 |
| title, per-day TF-IDF | 0.70 | 38 | 23 |

**Three things this says before anybody labels anything.**

The combined vector cannot be tuned. Between 0.95 and 0.90 it goes from 7 pairs
to 67, and it is already known to be wrong on most of what it adds - the
labelled two-stories pair sits at 0.9317, inside that jump. There is no floor
with both volume and margin.

**The title scorers are tunable and the combined one is not.** Both title
scorers move smoothly and both concentrate: the title encoder at 0.90 proposes
50 pairs over three days against the combined vector's 67, and it is the one
whose known-bad pair scores 0.7824 rather than 0.9317.

**All of them are still short of what the Editor counted by hand.** The best
tunable setting measured here proposes about 29 pairs a day. The Editor's read
of one day counted about 95 items in cross-source clusters. Pairs and items are
different units, but not by enough to close that gap - so precision is what the
labels will settle, and recall needs the full-day count the Editor asked for.

**The blind sheet exists**: 597 pairs, shuffled with a fixed seed, carrying only
the date, the two outlets and the two headlines. No score, no indication of
which rule fired, no hint of which side is which. At roughly ten seconds a pair
that is about two hours, which is the price Andre named for a number that can be
called recall.

## Row #4 - correct the token-share number

Defect 22 shipped the claim that the summary is "roughly nineteen words in
twenty" of the encoded string, in `story_key`'s neighbourhood, in
`AssembleConfig.group_identical_titles`, in the changelog and in
`docs/architecture/publishing/layout.md`. It was never measured. Andre measured
it on 2026-09-14 with the committed tokenizer over 75 items of the 2026-09-13
day: the title is a median **16 tokens** and title-plus-summary a median **121**,
so the summary is **87 percent of the tokens** and the headline is about one
part in eight. Guardrail #10: an unmeasured number may not justify a design, and
this one is now measured and wrong.

## Limits nobody trades

From the Editor's ruling, 2026-09-14. Each is a rule a grouping change has to
honour, not a preference.

- **A reaction is never merged into its event.** The reaction is the newer news.
  This is the 0.9317 pair.
- **An analysis piece is never merged into a reporting piece.** `source_kind`
  already records which is which. It is 5 percent of the day and the most
  distinctive 5 percent.
- **A round-up or live blog is never grouped, in either direction.**
- **Two feeds of one outlet are one source.** Row #2.
- **No sentence on a card may state as fact something the same page
  contradicts.** Silence is always available.
- **Grouping never crosses days.**
- **Nothing is removed from the page until recall is measured.**

## Out of scope

- Drawing the collapse. Row #6, and it waits on row #3.
- Day size. The Editor rules 356 items is the bigger failure and that perfect
  dedup only takes a day to about 290, 18 percent shorter. It is a different
  plan.
- Cross-day grouping. A follow-up is a new development, so it is a new story.
- The browser gate failing on `main` at `malformed-day.spec.ts`. Another worker
  holds it.

## See also

- [`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md) - the rule, the flowchart and the measurements.
- [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md) - defect 22, which this plan continues.
- [`20260906-data-growth-research.md`](20260906-data-growth-research.md) - note 28, the quadratic this pass is.
