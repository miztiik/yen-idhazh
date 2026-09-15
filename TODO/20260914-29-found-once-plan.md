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
| E1 | **Count an outlet once, not once per feed** | Trivial | Removes a false sentence | Measured: 3 of 43 groups were CGTN with CGTN. Row #2 |
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
| 1 | Stop printing "Only one of our sources carried this" | - | A | DONE | - | #782 | - |
| 2 | Two feeds of one outlet are one source | - | A | DONE | - | #782 | - |
| 3 | Measure: title signal against the committed days | - | A | DONE | - | #782 | - |
| 4 | Correct the token-share number defect 22 shipped | - | A | PENDING | - | - | p29-plan |
| 5 | Draw the collapse, with a publisher stack that links | - | B | PENDING | - | - | - |
| 6 | An article we could not read never becomes a card | - | B | PENDING | - | - | - |
| 7 | One outlet never runs the identical piece twice | - | B | PENDING | - | - | - |
| 8 | A ceiling on the day, beside the ceiling on a run | - | B | PENDING | - | - | - |
| 9 | The same story is one story for 36 hours, not one day | - | C | PENDING | - | - | - |
| 10 | A story that has been running ranks below one that broke today | - | C | PENDING | - | - | - |
| 11 | The lead is a weighted score, and the page says how | 10 | C | PENDING | - | - | - |
| 12 | Label the sheet, then set the floor | 9 | D | PENDING | - | - | - |

**Owner decisions, 2026-09-15.** Rows 5 to 12 are approved with the contracts
below. The contracts are the owner's; a worker implements them and decides
nothing. Five candidates were refused and are recorded under `Rejected` so
nobody re-proposes them.

**The comparison is over our own summary, and that is a bet the owner is
making on purpose.** "Assuming the summariser has done the job properly, that
is the premise of the app - let us bet it did and compare on that." Every row
below reads `title. summary`, which is what the pass already encodes. No row
reads an article body.

## Row #1 - stop printing the sentence we cannot support

- **Scope:** `coverage()` in `frontend/src/lib/components/ItemMeta.svelte` returns
  null at 0 as well as at null. Nothing else changes; `also_covered_by` keeps
  its meaning and the projection keeps the field.
- **Why:** printed **5,299 times** over the committed days against 93 for the
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
  Straits Times. Measured 2026-09-15: **3 of the 43 groups** on the committed
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

## Row #5 - draw the collapse, with a publisher stack

**Intent.** A reader sees one card per story, and that card says which
newsrooms ran it. Today the grouping is computed, persisted and deliberately
withheld from the page, so every detection gain is invisible.

**Contract.**

- `DigestViewItem` carries `same_story_as`, which the projection drops today,
  and gains `covered_by: list[DigestCoverage]` - **outlet names, not a count**,
  each carrying the name and the member's own item id, ordered by `rank_score`,
  capped at three plus a remainder.
- An item whose `same_story_as` is set **is not drawn as its own card**. The
  anchor draws one card carrying a stack of publisher pills.
- **Every pill is a link to that publisher's own item page**, which carries our
  summary of their piece and its `Read the original` link. It links to our page
  rather than straight out: a reader who wanted the publisher's version still
  reaches it in one more click, and a reader who wanted ours does not lose it.
  Nothing is removed - each member keeps its address, its archive entry and its
  month search entry. This is the reachability answer that pulled the collapse
  the first time, and it is not optional.
- `ui.draw_same_story`, default **true**, removal condition on the declaring
  line. It is the revert path.
- `also_covered_by` keeps its meaning and stays on the wire, because the count
  and the names answer different questions.

**Why the names and the fold ship together.** The fold is what makes a false
merge expensive - a story goes behind a pill instead of printing a wrong number.
The names are what make it recoverable. Shipping the fold first would be the
worst order available.

**Oracle.** A reading-page test on a built day with a known group: the anchor
draws once, the members do not draw as cards, every member's address still
resolves, and every member appears in the month index. A second arm with
`ui.draw_same_story` off restores one card per item.

**What the reader loses, stated.** On a false merge, a story is one click away
instead of on the page. That is the trade the owner took on 2026-09-14.

## Row #6 - an article we could not read never becomes a card

**Intent.** A card whose headline is `Article fails to load due to technical
issues` is not a story. It should never have cost a summarize call either.

**Contract.**

- The refusal reads **our own recorded extraction outcome**, never the fetched
  text. Matching on phrases inside the body would be a rule driven by untrusted
  input (Guardrail #11) and a source could steer it.
- The refusal lands **before summarize**, so the run does not pay to write prose
  about an error page. Measured: about 83 s of decode per item.
- The item is recorded as refused with its reason, exactly as other refusals
  are, so the operator surfaces can still count it.

**Oracle.** A built fixture whose extraction failed never reaches summarize and
never reaches the day. A second arm with a successful extraction of the same
shape publishes normally.

**What the reader loses.** A link to an article we could not read and had no
summary for.

## Row #7 - one outlet never runs the identical piece twice

**Intent.** The same piece from one outlet appears once.

**Contract.**

- A deterministic same-outlet, same-identity check at **plan** time, so the
  second copy is never summarised.
- It is **not** part of `collapse_same_story`. That pass refuses same-outlet
  pairs by design and therefore can never catch this; adding it there would
  break the across-outlets rule row #2 just repaired.

**Oracle.** A built plan carrying one outlet's piece twice plans it once. A
second arm with two different outlets plans both.

## Row #8 - a ceiling on the day, beside the ceiling on a run

**Intent.** Two different things need bounding and one knob is doing both
badly. A run has to finish inside its shard. A day has to be readable.

**Contract.**

- `run.safety_ceiling_per_run` stays, and its reason is narrowed in writing: it
  protects the worker from its timeout.
- `run.safety_ceiling_per_day` is added. It bounds what the day publishes across
  every run.
- **Both are guardrails, not rules.** They only ever refuse. Neither chooses
  content, ranks it, or reorders it; they bound how much the content-picker may
  hand over. A day under the ceiling is untouched.
- Numbers are the owner's and are recorded on the line that declares them.

**Why both.** The per-run cap is 80 and the day runs about five times, so a
number a person set at 80 publishes about 356. Anybody reading `80` and picturing
an 80-item day is wrong by a factor of four and a half.

**Oracle.** A built multi-run day stops at the day ceiling with runs still
under their own. A second arm stops a single run at the run ceiling with the day
still under its own.

## Row #9 - the same story is one story for 36 hours, not one day

**Intent.** A story that breaks at 23:00 and is picked up at 07:00 is one story.
Today grouping sees one published day and stops at midnight, so it is two.

**Contract.**

- `assemble.same_story_window_hours`, **default 36**, configurable so the number
  can move without a source edit. 36 covers an evening break picked up the next
  morning and refuses a genuine follow-up two days later.
- The pass reads the current day plus **only** those earlier days the window can
  still reach - at 36 hours that is one earlier day, and the read is bounded by
  the window rather than by how much archive exists (Guardrail #12). The
  declaration goes beside the code and names what it reads and why a single day
  cannot answer the question.
- **Nothing in an already-published day is rewritten.** A day that has been
  published is finished. When today's item matches yesterday's, the grouping is
  recorded on **today's** item only, and it points at yesterday's id.
- `same_story_as` therefore has to carry a date as well as an id. That is a
  persisted contract change: stamp `version`, append the changelog entry, and
  ship the read-side migration in the same commit - an item written before this
  carries a bare id and means "today".
- The card's wording changes when the match is older: the pill says the outlet
  and that it ran earlier, rather than implying it ran today.

**What this costs, to be measured before it lands.** One extra day of items and
vectors loaded per run, and the pair count rises with the square of the items in
the window. On a 356-item day that is about four times the pairs. The pass uses
0.23 percent of the assemble budget today, so four times is still about 1
percent - but that is arithmetic on a measured number, not a measurement, and
the row takes the reading before it claims it.

**Oracle.** A built pair 30 hours apart groups; the same pair 40 hours apart does
not; the window set to 0 restores today's same-day behaviour exactly. A built
earlier day is byte-identical before and after the later run.

## Row #10 - a story that has been running ranks below one that broke today

**Intent.** Freshness is a ranking signal we already have the data for and do
not use.

**Contract.**

- A derived decay term over `published_at`, which every item already carries.
  No model, no new persisted field, no fetch.
- It feeds **ranking**, never grouping. A story's age changes where it sits, not
  whether it is the same story as another.
- The shape and its constant are config, with a sane default, so the behaviour
  changes without a source edit.

**Oracle.** Two items alike in every other signal, one published today and one
two days ago, rank in that order; with the knob at zero they rank as they do
today.

## Row #11 - the lead is a weighted score, and the page says how

**Intent.** The day's leading stories are chosen by one score today. They should
be chosen by several signals with declared weights, and a reader should be able
to find out what those are.

**Contract.**

- A composite score over signals the payload already carries. At minimum: the
  existing `rank_score`, how many outlets ran it (`also_covered_by`), and the
  freshness term from row #10.
- **Every weight is config with a sane default.** Change the config and the lead
  order changes with no source edit (Guardrail #6). No weight is a literal.
- The composite is **deterministic and model-free**. It reads numbers the
  pipeline already wrote; no model ranks anything.
- **`also_covered_by` enters the composite only above a floor the owner sets**,
  because at today's recall the count is zero on most genuinely multi-source
  stories. Below that floor its weight is zero and the lead behaves as it does
  now. Row #12 supplies the recall figure that sets the floor.

**The documentation is part of the row, not a follow-up.** A page under
`docs/architecture/publishing/` owns the composite and carries a mermaid diagram
showing, in one picture: what signals enter, where each is computed, how the
same-story pass folds a group, and how the leading stories are chosen over the
folded day. The existing same-story flowchart in
[`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md)
is one half of it and is linked rather than copied.

**Oracle.** A built day where the top item by `rank_score` alone is not the top
item by the composite, proving the weights bind. A second arm with every weight
but `rank_score` set to zero reproduces today's order exactly.

## Row #12 - label the sheet, then set the floor

**Intent.** No floor is chosen by taste, and no weight in row #11 is either.

**What labelling is, since it has been asked.** It is **not** training a model
and it produces no model. A person reads two headlines and says whether they are
the same story. With a few hundred of those answers, we can count - for any
candidate floor - how many pairs the rule gets right and how many it gets wrong.
That is how the number is chosen instead of guessed. Nothing about it assigns a
score to a publisher; it scores the **rule**.

**Contract.**

- The sheet, its answer key and the script that builds it live under
  `test-results/same-story-labels/`, which git ignores. They are working
  material, not a published artefact.
- Blind: date, two outlet names, two headlines. No scores, no indication of
  which rule fired, shuffled with a recorded seed.
- Three verdicts: SAME EVENT, RELATED BUT DIFFERENT, UNRELATED.
- Regenerate the sheet **after** row #9, so the window's new pairs are in it.
- **Precision is not recall.** Every candidate is found by a rule, so the sheet
  measures precision only. Draw 200 further pairs at random from **below** the
  candidate filter and label those too; if none is SAME EVENT, the filter's own
  recall is at least 98.5 percent and the study may use the word recall. If any
  is, it reports a lower bound and names what it could not see.

**A question this row should answer while it has the labels.** The vector is
built over `title. summary`. Three cheap variants can be scored on the same
labels at no extra cost: the summary alone, the title alone, and the item's
`key_points` joined. If one separates better than what ships, that is a free
improvement and the measurement is already paid for.

## Rejected, 2026-09-15

Recorded so nobody proposes them again. Each is a dated decision, not a law
(section 0a) - what would reopen it is named.

| Proposal | Why it was refused | What would reopen it |
| --- | --- | --- |
| Cut the day to 90-120 items | The digest is a self-curating feed of digests, not a fixed-size bulletin. Content chooses its position and its relevance; we do not choose content, and more desks are coming rather than fewer | Nothing on the present design. The day is bounded by row #8's ceilings, which refuse without choosing |
| Per-day TF-IDF over headline words | Refused as a dependency, and that reason was wrong - it is about twenty lines of `collections.Counter` and `math.log`, no install and no shipped bytes. It stands refused because the comparison this project bets on is semantic and over the summary, and a word-overlap score is neither | Row #12 measuring it beating the shipped scorer on the same labels |

| A canonical "what happened" line from the summariser | Cannot be backfilled, so no committed day can measure it | A measured failure that only a rewritten summary could reach |
| Encode the article's lede and compare that | Proposed on 2026-09-15 and refused the same day. It serves no purpose the summary does not already serve, and the premise of this project is that the summariser did its job - so the comparison is over what the summariser wrote. The encoder's 256-token window meant it was never the whole article either | A measurement showing our summaries of one story diverge in a way the articles do not |
| Rebalance which desks get space | Same ruling as the day size: content chooses its position | Nothing on the present design |
| Let the cross-source count pick the day's leads | Not refused - **taken**, as row #11, with the count gated behind a recall floor so it cannot feed noise into the most valuable slots on the page | - |


## Limits nobody trades

From the Editor's ruling, 2026-09-14, except where the owner has since moved
one. Each is a rule a grouping change has to honour, not a preference.

- **A reaction is never merged into its event.** The reaction is the newer news.
  This is the 0.9317 pair.
- **An analysis piece is never merged into a reporting piece.** `source_kind`
  already records which is which. It is 5 percent of the day and the most
  distinctive 5 percent.
- **A round-up or live blog is never grouped, in either direction.**
- **Two feeds of one outlet are one source.** Row #2, landed.
- **No sentence on a card may state as fact something the same page
  contradicts.** Silence is always available.
- **A published day is never rewritten.** Row #9 crosses days by recording the
  match on the newer item only.
- ~~Grouping never crosses days.~~ **Overruled by the owner, 2026-09-15.** A
  story that breaks at 23:00 and is picked up at 07:00 is one story, and the
  window is `assemble.same_story_window_hours`, default 36.

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

- **Two-stage blocking** - bucket items on a cheap key, compare only inside a
  bucket. The premise is a cost problem we do not have: the pass spends 0.23
  percent of the assemble budget on a typical day and 0.97 percent on the
  largest ever published. Row #9 raises the pair count about fourfold, which is
  still around 1 percent, so this stays out until a reading says otherwise.
- **Time decay inside the grouping pass.** Row #9 makes the window 36 hours
  rather than weighting by age inside it: a pair is inside the window or it is
  not. A decay curve would add a second number to tune for no measured gain.
  Row #10 takes the half of the idea that pays, in the ranker.
- **Rewriting a published day.** Row #9 records a cross-day match on the newer
  item only. A finished day stays finished.
- Day size and desk balance - both refused above.

## See also

- [`../docs/architecture/publishing/layout.md`](../docs/architecture/publishing/layout.md) - the rule, the flowchart and the measurements.
- [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md) - defect 22, which this plan continues.
- [`20260906-data-growth-research.md`](20260906-data-growth-research.md) - note 28, the quadratic this pass is.
