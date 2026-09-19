# Plan 29 - the same story, found once

**Last Updated**: 2026-09-16

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Guardrail #4).

## Start here - the handoff

**You are picking this plan up. Read this section first, then the Status
Reckoner, then the one row you are about to build. Nothing else in this file is
required reading until a row sends you to it.**

**What to read, in this order.**

1. [`../CLAUDE.md`](../CLAUDE.md) - the engineering contract, and it binds you.
   Section 0b is the voice, 0c is how to ask the owner anything, 0d is what to
   do when a limitation blocks the intent, section 9 is done, 11 is schema
   stamping, 12 is the browser smoke, 13 is the test tiers.
2. [`../docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) - it routes you
   to the page that owns whatever you are changing.
3. [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - every
   gate command, and the three traps that make the browser smoke lie.
4. [`../docs/how-to/ship-a-pr.md`](../docs/how-to/ship-a-pr.md) - worktree,
   branch, PR, cleanup.
5. The `## Owner decisions` block below. Those are rulings, not suggestions, and
   **a settled one is never re-asked** (section 0).

**Where this plan's subsystems live.**

| What you are changing | Where it is | The page that owns it |
| --- | --- | --- |
| Whether two published items are one story | `backend/idhazh/assemble.py` - `story_key`, `headlines_match`, `_numbers_clash`, `_pair_terms`, `collapse_same_story` | `docs/architecture/publishing/layout.md` |
| What gets planned, and what gets refused before it is fetched | `backend/idhazh/stages/plan.py` - `_dedupe_planned_items`, `_one_piece_per_outlet`, `_within_ceiling`, `_within_day_ceiling` | `docs/architecture/sources/freshness.md` |
| How a candidate is scored before the day is cut | `backend/idhazh/rank.py` - `recency_bonus`, `authority`, `plan_vertical` | `docs/architecture/sources/freshness.md` |
| The order the published page draws | `backend/idhazh/assemble.py` - `_strength_order`, `leading_stories` | `docs/architecture/publishing/layout.md` |
| Every knob | `backend/idhazh/contracts/knobs/` then `config/idhazh.json` | `docs/concepts/config.md` |
| A feed's record, its rest and its retirement | `backend/idhazh/telemetry/source_health.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/feed_retirement.py` | `docs/architecture/sources/i-feed.md` |
| The operator console | `frontend/src/routes/console/` - `voices/` owns sources, `machine/` the runner, `judgement/` the evals | `docs/architecture/publishing/console.md`, `docs/concepts/console-design.md` |
| The reader's card | `frontend/src/lib/components/DigestItem.svelte`, `ItemMeta.svelte` | `docs/architecture/publishing/layout.md` |

**Four environment traps, each of which costs about an hour.**

- The interpreter is the repository's own `.venv`. It has `idhazh` installed
  **editable against the shared checkout**, so any direct `python -m idhazh.*`
  run from a worktree needs `PYTHONPATH` pointed at that worktree's `backend`
  first, or you silently exercise the wrong code. `pytest` does not need it.
- **Other agents work in this repository at the same time.** A foreground gate
  is killed by a sibling's interrupt about one time in three. Run every long
  command detached, writing its exit codes to a file, and read the file.
- Files are **LF and ASCII only** (section 5). Write LF before the first test
  run; git normalises at `git add`, which is too late.
- **Never force-push and never rebase a pushed branch** (section 8). When main
  moves under you, merge it in. `gh pr create` and `gh pr merge` can exit 1
  having succeeded - check the state, not the exit code.

**How to leave the plan for the next agent.** Set your row's `Status` to `DONE`
in the Status Reckoner and fill its `Worktree`. **Leave `PR` as `-`** - a pull
request number cannot appear in its own diff. If a row's premise turns out to be
wrong, say so in the row, set it `BLOCKED`, and hand the decision back with
options and costs (section 0c). Row #13 is the worked example of that.

## Owner decisions, 2026-09-16

Rulings from the owner under section 0. They supersede anything else in this
file, and none of them is a question any more.

**The day ceiling is 400 and that is settled.** `run.safety_ceiling_per_day` is
five runs at `run.safety_ceiling_per_run`, it changes no day that has ever
published, and it is not to be re-opened. Re-litigating a config value the owner
has already set is the failure this line exists to stop.

**A source's own quality decides its own future, and we only build the
guardrail.** Row #13 stops being a chrome ledger that reports to nobody. It
becomes one loop: measure, publish the measurement to the operator console, and
let a source that stays bad for a declared dwell retire itself. The reason is
supply - a template host or a dead feed will be added again every time the source
list grows, so a rule that needs a person each time is a rule that needs a person
for ever.

**Freshness decays at read time, on a Gaussian with an offset.** Row #10 as
written asked for a decay term that already exists. The defect is one layer
along and the curve is named in that row.

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
| 4 | Correct the token-share number defect 22 shipped | - | A | DONE | - | #785 | - |
| 5 | Draw the collapse, with a publisher stack that links | - | B | DONE | - | - | p29-r5 |
| 6 | Retire the four hosts that serve one page | - | B | DONE | - | #794 | p29-r6b |
| 7 | One outlet never runs the identical piece twice | - | B | DONE | - | - | p29-r7 |
| 8 | A ceiling on the day, beside the ceiling on a run | - | B | DONE | - | - | p29-r8 |
| 9 | The same story is one story for 36 hours, not one day | - | C | DONE | - | - | p29-r9 |
| 10 | A story that has been running ranks below one that broke today | - | C | DONE | - | - | p29-r10 |
| 11 | The lead is a weighted score, and the page says how | 10 | C | DONE | - | - | p29-r11 |
| 12 | Label the sheet, then set the weights | - | C | SUPERSEDED | - | - | - |
| 13 | A source's quality decides its own future | - | C | DONE | - | - | p29-r13 |
| 14 | The composite score, proving it changed nothing | - | C | DONE | - | #799 | p29-r14 |
| 15 | The weights and the 0.88 floor | 12, 14 | D | SUPERSEDED | - | - | - |
| 16 | Refuse boilerplate, on a week of evidence | 13 | D | DESCOPED | - | - | - |
| 17 | Does a short extraction publish at all | - | D | DONE | - | - | p29-r17 |

**Owner decisions, 2026-09-15.** Every row carries its contract. The contracts
are the owner's and Fowler's; a worker implements them and decides nothing.
Six candidates were refused and are recorded under `Rejected` so nobody
re-proposes them.

**The comparison is over our own summary, and that is a bet the owner is
making on purpose.** "Assuming the summariser has done the job properly, that
is the premise of the app - let us bet it did and compare on that." Every row
below reads `title. summary` and `key_points`, which the pass already has. No
row reads an article body at assemble.

**Two contracts were ruled by Fowler on 2026-09-15**, under the owner's standing
instruction that the domain authority leads on a contract question and rules in
alignment with intent even where that means scope expansion. Rows 13 and 14
carry those rulings verbatim, including the expansions and the refusals.

### The whole rule, on one picture

```mermaid
flowchart TD
  fetch["extract: a page is fetched"] --> chrome{"Do this host's own pages<br/>repeat these lines?"}
  chrome -- "yes, over boilerplate_ratio_max" --> flag["record FailureCode.BOILERPLATE<br/>(row 13 records; row 16 refuses)"]
  chrome -- no --> sum["summarize: our headline<br/>and our summary"]
  flag --> sum
  sum --> vec["assemble: encode title. summary"]
  vec --> pairs["every cross-outlet pair<br/>inside the window (row 9, 36 h)"]
  pairs --> veto{"Do their numbers clash?"}
  veto -- yes --> apart["Two stories"]
  veto -- no --> head{"Do the reduced headlines match?"}
  head -- yes --> one["One story"]
  head -- no --> comp["composite = w_cosine x cosine<br/>+ w_points x key-point overlap<br/>(weights sum to 1.0)"]
  comp --> floor{"At or above<br/>same_story.floor_min?"}
  floor -- yes --> one
  floor -- no --> apart
  one --> all{"Does it clear against<br/>EVERY member of the group?"}
  all -- no --> apart
  all -- yes --> group["One group. The strongest is drawn;<br/>the rest become publisher pills (row 5)"]
  group --> lead["leading_stories: a weighted score over<br/>rank_score, also_covered_by, freshness (row 11)"]
```

**Three things the picture is deliberate about.** The numbers veto sits
**before** everything, because a clashing figure is evidence of difference and
no amount of similarity outvotes it. The headline rule stays a threshold-free
joiner **above** the composite rather than a term inside it, so the rule that
landed on 2026-09-14 cannot regress. And the composite's weights sum to 1.0, so
a floor is a number on the cosine's own scale rather than a coincidence.

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

## Row #6 - retire the four hosts that serve one page

**Intent.** Three of these four feeds do not publish articles. They publish one
template with a different URL each time, and we have been summarising it. The
fourth, `energymonitor`, does publish articles, and the count below is what
found that out.

**What was measured, 2026-09-16.** Found from recorded outcomes only - the
`code`, `source_words` and `source_chars` cells on `state/item-health/**` -
never by matching words in a body. 23 day shards, 12,357 rows, 2026-08-24 to
2026-09-15. Cross-checked against the committed digest tree, which holds 26 days
to the same end date and 9,554 published cards.

| Feed | Rows | Items | Published cards | Median body words | Median body chars | What the rows say |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `lemonde-en` | 176 | 169 | 151 | 35 | 209 | `too_short` on 162 rows, `length_out_of_range` on 11. All 173 rows carrying a count say 35 words, and no other value appears. |
| `offshore-wind` | 50 | 45 | 44 | 3 | 18 | `not_prose` on 39 rows. 5 rows carry 219 to 606 words, all on 2026-09-04. |
| `climate-home` | 15 | 13 | 12 | 51 | 331 | `not_prose` on 12 rows. One row carries 2,340 words. |
| `energymonitor` | 34 | 33 | 32 | 357 | 2,474 | **No failure code on 28 of 34 rows.** Those 28 carry 286 to 1,025 words, on 10 separate days. |

260 items, 239 published cards, 2.50 percent of the 9,554 cards in the digest
tree.

**Three of the four had already gone quiet before this row ran.** The last item
each one put in front of the ranker: `offshore-wind` 2026-09-04,
`energymonitor` 2026-09-09, `climate-home` 2026-09-11. Feed health says all four
answered every read to 2026-09-15, so this is the gap health cannot see - the
door opens and nothing recent is behind it. `lemonde-en` alone ran to the last
day.

**The count corrects this row's own table, and one correction is material.**
The estimates it replaces were derived from characters at 6.5 characters a word.
`offshore-wind` at 3 words and `climate-home` at 51 were exact. `lemonde-en` was
9 percent low - 32 estimated, 35 counted - which changes nothing. The item
counts were each a little low: 166, 40 and 12 estimated against 169, 45 and 13
counted.

`energymonitor` was wrong in a way that inverts the finding. The row read 6
items at 398 chars and 61 words and called the signal "none". Those 6 rows are
real, and they are 6 rows out of 34. The other 28 carry no failure code and run
286 to 1,025 words. **Energy Monitor served an article about four times in
five, up to the day it went quiet.** The row's own subset was its failures, and
a feed's failures always look like a template host, because that is what a
failure is.

**It was retired anyway, and the retirement stands on its own facts.** The row
said to retire it and a worker decides nothing (`CLAUDE.md` section 0, section
0d), and Energy Monitor has put nothing in front of the ranker since
2026-09-09 either way. What is handed back is the reason: it was retired as a
template host and it is not one. Un-retiring it is one `retired_on` field and
one `status`. The `energy` desk went from 27 active feeds to 24 on this row
against a floor of 21; putting Energy Monitor back takes it to 25.

**Contract.**

- Each of the four moves from `feeds` to `retired` in `config/sources.json`,
  with `status: retired` and `retired_on` set to the date the row lands. That is
  the tombstone shelf the contract already describes - read by nobody who
  fetches and by everybody who has to put a name on an id.
- **Nothing published is touched.** Their committed items keep their addresses,
  their archive entries and their search entries. A retired feed stops costing a
  request; it does not un-publish a story.
- The `lemonde-en` candidate leaves `config/pipeline-tests.json`, which drops the
  list from 24 to 23 against a floor of 20. A test dispatch resolves a
  candidate's vertical and tier off the live feed list, so an orphan is a
  `KeyError` 40 minutes in.

**What the reader loses, stated.** Three of these are energy feeds and the desk
is already thin. For three of the four the reader loses nothing, because they
never delivered an article. For `energymonitor` the reader loses 32 cards over
26 days - a little over one a day - and that is a real loss rather than a paper
one, even though the feed had already stopped delivering them.

**Oracle.** The four ids appear in `retired` and not in `feeds`; a collect run
asks them for nothing. The existing retirement tests cover the shape.
`test_the_address_list_can_still_answer_a_draw` now reads the live feed list
rather than searching the file's text, which would find a retired id on the
tombstone shelf and pass.

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

**Rewritten 2026-09-16 after the row's own premise was checked and failed.**

**What was wrong with the row as written.** It asked for "a derived decay term
over `published_at`, feeding ranking, config-driven". **That already exists.**
`rank.recency_bonus` halves every `collect.recency_half_life_hours` and is
scaled by `collect.recency_weight`. Building it again is a no-op.

**The defect is one layer along, and it is real.** `rank_score` is computed once,
at the run that planned the item, and the published day sorts on that stored
number - `assemble._strength_order` reads `item.rank_score` and nothing else.
So an item planned at 02:20 carries its 02:20 freshness all day. At 18:20 it is
sixteen hours old, it still holds the full bonus it earned that morning, and it
outranks something that broke an hour ago. **The decay has to be evaluated when
the page is drawn, not when the item was planned.**

**Contract.** Owner ruling, 2026-09-16.

- A **Gaussian decay with an offset**, evaluated at read time, over
  `published_at`. The offset is a flat shoulder so a brand-new story does not
  fall off a cliff before anything else about it is known.

$$
S(t) = \begin{cases}
1.0 & t \le \text{offset} \\[4pt]
\exp\left(-\dfrac{(t - \text{offset})^2}{2\sigma^2}\right) & t > \text{offset}
\end{cases}
$$

- **It multiplies, it does not add.** The page order is
  `rank_score * S(t)`. A multiplier keeps the quality signal's shape and moves
  where it sits in time; an added term would let age outvote quality on its own.
- **Three knobs on `PlacementConfig`, none of them a literal**
  (Guardrail #6): `freshness_offset_hours`, `freshness_scale_hours` and
  `freshness_decay_at_scale`. `sigma` is derived rather than typed, so a person
  sets a sentence they can read - "at `scale` hours a story is worth `decay` of
  what it was" - instead of a variance:
  $\sigma^2 = -\text{scale}^2 / (2\ln(\text{decay}))$.
- **`freshness_decay_at_scale` of 1.0 turns the whole thing off**, exactly,
  and that is the revert path. It ships on, and the row's second oracle arm is
  that off reproduces today's order byte for byte.
- It feeds **ranking**, never grouping. A story's age changes where it sits,
  never whether it is the same story as another.
- **No new persisted field and nothing re-derived.** `published_at` is already
  on the item and `S(t)` is computed from it and the clock. A published day is
  never rewritten (`Limits nobody trades`): the number changes because the
  clock moved, not because we edited a finished day.

**Why this curve and not the other two.** A power law of the Hacker News shape,
`(points - 1) / (t + 2)^1.8`, has the same shoulder idea in its `+2` and is
simpler, but its tail never really ends - a week-old story keeps a visible
share of its score, and this digest publishes a day at a time. The plain
exponential half-life we already have at plan time has no shoulder at all, so
the first hour is where it cuts hardest, which is the opposite of what a digest
wants. The Gaussian-with-offset is what Elasticsearch recommends for exactly
this problem and it is the one that says both things: nothing inside the
shoulder is penalised, and past the shoulder the fall is smooth and finite.

**The interaction with the plan-time bonus is named, not hidden.** After this
lands, age appears twice: `collect.recency_weight` inside the stored
`rank_score`, and `S(t)` over it. That is not double-counting, because the two
answer different questions. **The plan-time bonus decides which items get a slot
at all** - it orders the pool the safety ceilings cut. **`S(t)` decides where a
story that already has a slot sits on the page.** Row #11 owns saying this in
`docs/`, in one picture.

**Oracle.** Two items alike in every other signal, one published an hour ago and
one two days ago, draw in that order. The same pair with
`freshness_decay_at_scale` at 1.0 draws in today's order exactly. An item inside
the offset scores `1.0` and an item at `scale` hours past the offset scores
`freshness_decay_at_scale`, both to floating-point tolerance - which is the test
that the derived sigma is derived correctly.

## Row #11 - the lead is a weighted score, and the page says how

**Intent.** The day's leading stories are chosen by one score today. They should
be chosen by several signals with declared weights, and a reader should be able
to find out what those are.

**Contract.**

- A composite score over signals the payload already carries. At minimum: the
  existing `rank_score`, how many outlets ran it (`also_covered_by`), and the
  freshness term from row #10.
- **Row #10's term multiplies the composite, it does not sit inside the sum.**
  The weighted sum is what the story is worth; `S(t)` is what its age does to
  that. Written as one more weighted term, a fresh but worthless story would
  outrank a strong one, which is the single failure mode this ordering exists to
  refuse.
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

**SUPERSEDED, 2026-09-17, by the adaptive merge line, which has since shipped.**
The owner ruled that the labelling is done by a model rather than a person, that
the line fits itself daily, and that there is no hard floor. That is a subsystem
rather than a row, so it had its own plan; the rule and its rationale now live in
[`../docs/architecture/publishing/same-story.md`](../docs/architecture/publishing/same-story.md).
Row #15 goes with it: the floor is no longer a number somebody picks once.

**What this row got right and the new plan keeps.** No floor is chosen by taste.
The sheet is blind. Precision and recall are different questions and a sample
drawn only from below the line can measure just one of them.

**What it got wrong.** The band it named, `[0.82, 0.94]`, stops at the floor, so
it contains no pair the shipped rule calls positive and cannot measure the
precision of what ships at all. The new plan's band is `[0.88, 1.00]`.

**Intent, as written.** No floor is chosen by taste, and no weight in row #11 is
either.

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

## Row #13 - a source's quality decides its own future

**Ruled by Fowler, 2026-09-15. Correction level 4.** The chrome-ledger contract
in the table below is his, under the owner's standing instruction that structure
fixes matter.

**Amends `backend/idhazh/contracts/feed_retirement.py`.** That file states in
writing that a second `RetirementCause` is a design change. It is now one, and
the same commit updates that docstring - the clause is not deleted, it gains the
dwell and the evidence floors as the answer to the risk it named (section 0).

**Unblocked and widened by the owner, 2026-09-16.** The row was BLOCKED for a
day because the measurement that sold it had been falsified - see
`The example this row was sold on is gone` at the end. The owner's answer was
neither to drop it nor to build it as it stood. It was to close the loop:
**measure, show the measurement, and let a source that stays bad retire
itself.** The chrome ledger becomes one measurement inside that loop rather than
the whole row. Read `The loop` first; the table after it is the store the loop
reads.

**Intent.** A publisher that serves one template for every article is caught the
third time, not the 166th. No length rule can see a 400-word template; only
comparing a host's pages against each other can.

### The loop

**Owner's words, 2026-09-16: "content quality decides its own future. We only
build the guardrails."**

The reason is supply. A template host, a dead feed and a 35-word abstract feed
will arrive again every time the source list grows - row #6 found four of them
in one pass and three had already gone quiet before anybody looked. **A rule that
needs a person each time is a rule that needs a person for ever.** So the row
ships three parts and no part is optional.

| Part | What it does | Where it lives |
| --- | --- | --- |
| **Measure** | The chrome ledger below, plus the yield and body-length evidence `state/item-health/**` already carries. Deterministic, no model | `backend/idhazh/` - the store table below |
| **Show** | One panel on `/console/voices/`, which already owns `Sources we may ask, and what they yield`, retirement, rest and the yield alarm. **Susan owns this panel** - see `What Susan owns` | `frontend/src/routes/console/voices/` |
| **Retire** | A source whose measurement stays under its alarm point for a declared dwell files its own retirement row, through the machinery that already exists | `backend/idhazh/telemetry/source_health.py` |

**The retirement machinery is already built and this row reuses it, not a second
copy of it.** `source_health.retirements` reads a feed's record, compares it to a
`collect.*_before_*` count, and appends a `FeedRetirementRow` to
`state/feed-retirements.csv`. `stage_plan` then stops asking that endpoint. What
is new is a second cause and a dwell, not a second mechanism.

**This amends `RetirementCause`, and that is a deliberate owner decision.** The
enum has one member, `http_410`, and
`backend/idhazh/contracts/feed_retirement.py` says in writing that a second one
is a design change, because "retiring on anything softer than `410 Gone`
eventually removes unique primary or regional reporting over a bad week". The
owner has ruled that it is worth it, and the row carries the safeguard that
answers the objection rather than deleting it:

- **The dwell is long and it is config.** `collect.source_quality_dwell_days`,
  default **14**. A bad week cannot retire anything, which is precisely the
  failure the original clause named.
- **Retirement is filed against the endpoint, never the feed** - unchanged.
  Editing the URL in `config/sources.json` is a new address with no inherited
  retirement, so un-retiring is one curated line.
- **Nothing edits `config/sources.json`.** That stays the registry a person
  curates, exactly as it does today.
- **The evidence floors already exist and they bind here too.**
  `collect.source_yield_min_complete_days` (30) and
  `source_yield_alarm_min_decisions` (30) mean no source is judged on thin
  record. A weekly publisher may never clear them, and that is the correct
  answer for a weekly publisher.
- **The console panel is what makes it reversible.** A retirement a person can
  see coming for fourteen days is a retirement they can stop.

### What to align the new knob with, and the recommendation

The repository already has four families of automatic judgement about a source.
The new dwell joins them and must read like one of them, not like a fifth idiom.

| Knob | Today | What it does when it fires |
| --- | --- | --- |
| `collect.availability_strikes_before_rest` | a count of consecutive failures | Rests the feed. **Lifts on its own** |
| `collect.feed_http_410_runs_before_retirement` | distinct runs reading `410 Gone` | Retires the endpoint. Permanent until a person edits the URL |
| `collect.reliability_window_days` (30), `reliability_floor` (0.5) | a trailing ratio | **Scales** the feed's authority. Never removes it |
| `collect.source_yield_alarm_point` (0.5), `source_yield_min_complete_days` (30), `source_yield_alarm_min_decisions` (30) | a trailing ratio with two evidence floors | **Names the source on the run summary and moves nothing** |

**The fourth family is the one to extend, and the recommendation is to extend it
rather than invent beside it.** It already measures the right thing - the share
of what a source decided that became a story - already has both evidence floors,
and already refuses to act. All this row adds is: *and if it is still under the
alarm point `source_quality_dwell_days` later, retire it.* Three knobs become
four, the alarm keeps its meaning, and nobody has to learn a new vocabulary.

**One knob is worth proposing beyond that, and it is the owner's call.**
`collect.source_quality_auto_retire`, default **false** for the first release.
The loop measures and draws from the day it lands; the retirement arm switches on
once a person has watched the panel for a cycle and agrees with what it is
pointing at. It carries its removal condition on the declaring line
(Guardrail #6): delete the flag once one real retirement has been reviewed and
accepted.

### What Susan owns

**Susan's mandate on this row is the chart, and it is a real mandate, not a
review.** The question she answers is `signal from noise` - a panel that cannot
separate a template host from a quiet week has not earned its bytes, and a panel
that is merely correct has not either (`CLAUDE.md` section 14).

- **Which chart type.** The candidates are the ones the console already speaks:
  the reliability strip `/console/voices/` uses for feeds near a rest, a
  distribution with the alarm point marked on it, and a small-multiple per
  source over the dwell window. **Susan picks one and says what the other two
  lose.** Jony rules whether it survives on the page at all; Susan rules whether
  what survived is good enough to ship.
- **The dwell has to be visible as a dwell.** A source fourteen days into a
  countdown and a source that dipped yesterday are different facts, and a chart
  that renders them the same has failed.
- **The empty and degraded states are part of the panel**, not a follow-up: a
  source under its evidence floors, a source with no record at all, and the day
  the ledger is missing.
- The sufficiency checks in [`../docs/concepts/design-system.md`](../docs/concepts/design-system.md)
  apply, and a surface can fail by being too little.

### The store the loop reads

**REVERTED, 2026-09-17, the day it shipped.** Everything below was built and
merged, then taken back out. The half of row #13 that survives is the retirement
loop and the reliability strip; this store is gone. Three findings killed it, and
they are kept here because they are the price of reviving it.

**It changed nothing.** A full run with the store live produced **zero
`boilerplate` cells in 12,917 committed item-health rows** - the same zero the
defect statement below quotes as the reason to build it. Only 31 lines across 14
hosts cleared the three-page floor; the busiest host had 8, and a page would have
to be 40 percent those 8 lines to trip the ratio.

**It cost 36 files.** A contract, a schema, a module, a ledger key, a prune rule,
a fold in assemble, a read in every shard, three config knobs, and prose on seven
doc pages - for a signal that fired zero times.

**It made a word mean three things.** This repository already used "chrome" for
the console's own furniture and for the browser we smoke-test in, across 31
files. The store added a third sense in the same tree.

**The order was wrong, and that is the lesson.** Guardrail #10 says measure when
a number would change the decision. The number here was cheap - count committed
extractions carrying a line the same host printed on three other pages - and it
was taken after the instrument was built rather than before. Anything reviving
this store takes that count first.

**The defect it was built to close.** `boilerplate_ratio(lines, seen_elsewhere)`
in `backend/idhazh/extract.py` has existed, with an enum value, two config knobs,
tests and documentation on three pages, and **has never fired**: nothing in
production passes `seen_elsewhere`, so it divides by an empty set and returns
0.0. That is still true, and after this revert it is the signal's resting state
rather than a gap waiting on a store.

**Contract.**

| What | Ruling |
| --- | --- |
| Grain | **One row per (host, line hash)**, keyed on the registrable host of `canonical_url` - **not `source_id`**. Chrome belongs to the server template, and keying on the feed both fragments the evidence and re-makes the mistake row #2 repaired |
| Store | **`state/chrome.csv`, one file, unsharded.** The read carries no time window - chrome learned in August is chrome in September - so a partition would open every file anyway |
| Contract file | `backend/idhazh/contracts/chrome_line.py`, plus the import and tuple entry in `contracts/export.py` |
| Schema stem | `chrome-line-row` |
| Fields | `version, host, line_rule, line_hash, pages_seen, first_seen, last_seen`. `line_hash` uses the existing `Sha256` type |
| `line_rule` | **A column, not a comment.** It versions the normaliser (NFKC, whitespace collapsed, casefolded, then sha256) and a read filters to the current rule. Without it a changed normaliser makes every row dead weight that silently never matches |
| Writer | **`assemble`, not `extract`.** Only assemble has the day's whole item set, so only assemble can count distinct pages a host served. A work shard sees `index % shards` of the day, and eight shards incrementing one key through a `merge=union` CSV is a race this repository has already paid for twice |
| Reader | `stages/common._fetch_one`, passing the host's line set into the `seen_elsewhere` parameter that already exists. **`extract.py` does not change at all** |
| Bound | Two config caps **and an eviction order**, and the order is load-bearing: evict by `pages_seen` **ascending**, then `last_seen` ascending. Recency eviction would evict the chrome using the very articles you compare against |
| Knobs | `extract.chrome_lines_per_host_max`, `extract.chrome_forget_days`, `extract.chrome_pages_min` (default 3), on `ExtractConfig` |
| Guardrail #12 | **A declaration is required**, and the shape is a cover enforced on the store rather than on the read - `state/traces/` is the precedent. It says: the read is one streaming scan filtered to the hosts this shard's plan names; the file is bounded by hosts times `chrome_lines_per_host_max`, so it grows with the source registry and stops, never with the archive |
| The pruner | **Ships in the same commit as the writer**, in `stages/prune_state.py` beside `prune_seen`. A store bound with no pruner is prose |
| Read-side migration | **None.** The ledger is new, so no earlier run wrote a shape to migrate. `line_rule` is a forward provision, not a migration |
| `reject_boilerplate` | **Stays false in this commit.** The signal has never fired once, so flipping the refusal in the commit that first makes it fire means nobody can tell a correct refusal from 12,000 wrong ones. That is row #16 |

**What the bodies never do.** Only hashes persist. A chrome line is fetched text,
and a sha256 of it cannot carry an instruction (Guardrail #11). Nothing on the
row is free text, by construction.

**Removals in this row.** `FailureCode.BOILERPLATE` leaves
`SOURCE_NEUTRAL_FAILURE_CODES` in `backend/idhazh/telemetry.py`, and the count
stated in words in `docs/architecture/sources/item-health.md` moves with it.
That set means "a failure that says nothing about the source", and the moment
this fires, `boilerplate` says the host serves a template - the most
source-specific thing a failure can say. Leaving it in credits a host that
served nothing.

**Corrections, not deletions.** Three pages describe the signal as inert and
each becomes wrong when this lands:
`docs/architecture/sources/trust-boundary.md`, `docs/concepts/config.md`,
`docs/concepts/pipeline-loop.md`. **No test is deleted** - the unit tests in
`backend/tests/test_extract.py` cover a function that is about to run for real;
any docstring in them calling the path theoretical is corrected.

**Tests.** Unit: the line normaliser, the eviction order, the fold. Contract:
the new schema, a fixture under `tests/fixtures/contracts/chrome-line-row/`, the
export entry, and the three new keys in **both**
`every-knob-differs-from-the-committed-config.json` and `tuned.json` - only the
full suite catches those. Integration: `to_article_with_source` driven with a
`seen_elsewhere` set built by the real fold from two captured pages under
`tests/fixtures/pages/`, no mocks. End-to-end: one canary arm proving a refused
item still writes an honest item-health row. No test walks `state/` or the
committed days.

**The number this row does NOT claim.** The 5.2 hours of summarize time those
four hosts consumed are **not** this row's to save - row #6 retires them, and
three of the four already carry a length signal.

**The example this row was sold on is gone, and that is why the row changed
shape.** The row said it uniquely catches "the Energy Monitor shape: a host whose
template is long enough that no length rule will ever see it". Row #6's count of
2026-09-16 falsified that: Energy Monitor served an article on 28 of its 34
recorded rows, 286 to 1,025 words, over 10 separate days. It is not a template
host and never was. The row's own reading had looked only at its 6 failure rows,
and a feed's failures always look like a template host, because that is what a
failure is.

**What is still true, and what it is worth, were two different questions.**
`boilerplate_ratio` has never fired once in 12,277 committed item-health rows,
so a signal with an enum value, two config knobs, tests and documentation on
three pages is dead code either way. That is a real defect. What the row lost was
a measured host it would have caught - so the size of the prize was unknown, and
the row was asking for a new contract file, a new store, a new pruner, three
knobs and a Guardrail #12 declaration to chase it.

**The owner's answer, 2026-09-16, was to stop asking what one measurement is
worth and close the loop instead.** Read `The loop` at the top of this row. The
store below is still built exactly as Fowler ruled it; what changed is that its
output now reaches a console panel and, after a declared dwell, a retirement -
so the row stops being a measurement nobody acts on. The prize is no longer "how
many hosts would this have caught in the past". It is "no host of this shape ever
needs a person again".

**Two things this row must do because the loop asks for them, and neither was in
Fowler's table.** The measure part now publishes to `/console/voices/` (Susan's
panel), and the retire part adds a second `RetirementCause` behind
`collect.source_quality_dwell_days` and `collect.source_quality_auto_retire`.
Both are recorded above, with the safeguard for each.

**Row #16 cannot start until this one does**, because it reads the cells this
row writes.

## Row #14 - the composite score, proving it changed nothing

**Ruled by Fowler, 2026-09-15. Correction level 4.** This is the structural half
of the owner's composite ruling; row #15 is the behavioural half.

**Intent.** Replace one cosine and one floor with a weighted score over several
signals, so no signal is traded away for another - and prove the machinery
changed nothing before any weight moves.

**Contract.**

| What | Ruling |
| --- | --- |
| Shape | **An extension of `AssembleConfig`, as a nested `SameStoryConfig`** in `backend/idhazh/contracts/knobs/placement.py`. Nothing new is persisted and no boundary is crossed, so a new contract would be ceremony with no beneficiary. Nested because the weights carry an invariant across them |
| Schema stem | None new. It lands in `schemas/app-config.schema.json` |
| **The invariant** | **The positive weights sum to exactly 1.0, enforced by a `model_validator`, and every term is itself on 0 to 1.** Without it, "floor 0.88" answers nothing - 0.88 of what? With it the composite is on the cosine's own scale, so every threshold already recorded in the docs stays readable |
| Terms | **Two: the cosine over `title. summary`, and key-point overlap.** Cosine separates 100 percent; key-point overlap separates 97.0 percent and is the only other term whose different-pair p99 (0.0962) sits below its same-pair median (0.2419) |
| The numbers clash | **A hard veto, not a negative weight.** It fires on 0.0 percent of same-story pairs - zero of 67 - and a term with no false positives is a rule, not evidence. In a sum, a large enough cosine outvotes it, which is the one case it exists to refuse. A negative weight would also break the sum-to-one invariant |
| The headline rule | **Stays a threshold-free joiner above the composite**, not a term inside it. Inside a sum, a matching-headline pair with a weak cosine could fall below the floor - a regression against the rule that took one-headline groups still apart from 27 of 42 down to 1 |
| Order | numbers clash refuses; identical reduced headlines join; otherwise the composite scores; then complete-link, unchanged |
| `duplicate_similarity_min` | **Retired and refused, not aliased.** `refuse_a_removed_knob("duplicate_similarity_min" -> "same_story.floor_min")`. 0.94 of a cosine and 0.94 of a composite are different quantities, so a silent alias would carry a stale number forward as if it still meant the same thing |
| Interpretability | The weights sum to 1.0; every term is on 0 to 1, validated; **the pass logs the terms that carried each group** at INFO through the existing `telemetry.event` path - about 84 groups a day, no contract needed; and the published field is a **count**, not the score, so the score never reaches a reader |
| Payloads written under the old rule | **Untouched, and nothing re-derives them.** `_validator_identity()` does not hash `collapse_same_story`, so **no day-validation receipt is re-earned** |

**The oracle is the whole point of this row.** It ships with cosine weight 1.0,
key-point weight 0.0 and floor 0.94, and its acceptance is a replay over the
committed days producing the **identical groups**. That proves the machinery
moved nothing. Mixing the mechanism with the weights means a group that moves
cannot be attributed to either.

**Refused from the composite: shared rare title tokens.** Its different-pair p99
is 1.0000, so about one in a hundred different pairs scores a perfect 1.0 - over
9,055 pairs that is roughly 90 wrong pairs each handed a full weight. Its
separation, 35.8 percent, is the weakest of the three and its top end is
actively misleading. What reopens it: the same distribution measured
**conditioned on the cosine already being near the floor**, rather than over
9,055 random pairs of which 99.9 percent are nowhere near the decision.

**Removals in this row.** `assemble.duplicate_similarity_min` from
`config/idhazh.json` and from `contracts/knobs/placement.py`, with its long
`Field(description=...)`; the module constant `DUPLICATE_SIMILARITY_MIN` in
`backend/idhazh/assemble.py`; and the prose in
`docs/architecture/publishing/layout.md` that calls 0.94 a cosine floor. The
labelled table under `What chose 0.94` **stays** as the evidence it is, retitled
to what it measured.

## Row #15 - the weights and the 0.88 floor

**Intent.** The owner's ruling, 2026-09-15: "drop to 0.88, the world is full of
regurgitated stuff, then originality wins on merit."

**Contract.**

- `same_story.floor_min` moves to **0.88**, and the weights move off
  `1.0 / 0.0` to values fitted on the labels row #12 produces. Fitting weights
  against unlabelled marginal distributions is fitting to noise.
- Nothing else changes. Row #14 has already proved the machinery.

**The price, stated once so nobody has to rediscover it.** At floor 0.88 the
cosine admits **7 of 9,055** random cross-outlet pairs, and the pair a person
labelled TWO STORIES scores **0.9317**, so 0.88 merges it. Whether the composite
pulls that pair back under the floor is **unknown** - the measured numbers are
marginal distributions over all pairs, and 99.9 percent of those are nowhere
near the decision. Row #12's labels are what answer it.

**Why now is the cheapest moment.** `same_story_as` is recorded and not drawn, so
today a false merge costs exactly one wrong corroboration count. The day row #5
draws the collapse, a false merge starts costing a story nobody can see is
missing. **Today a false merge is cheap and it will never be this cheap again.**

## Row #16 - refuse boilerplate, on a week of evidence

**DESCOPED, 2026-09-17.** There is nothing left to read. The store this row was
waiting a week on was reverted the day it shipped, so `boilerplate` is back to
dividing by an empty set and no run will ever write a cell for this row to
inspect. Reviving the row means reviving the store first.

**Intent, as written.** Turn the boilerplate signal from a recording into a
refusal, once there are real rows to read.

**Why the evidence never arrived.** A full run with the store live produced
**zero `boilerplate` cells in 12,917 committed item-health rows**. Only 31 lines
across 14 hosts ever cleared the three-page floor, and the busiest host had 8 -
which would have to be 40 percent of an article's lines to trip the ratio.

**What would restart it.** A measurement first, then the store: count how many
committed extractions contain a line the same host printed on three or more other
pages, off the corpus we already hold. If that number is zero again, the signal
itself is the thing to delete rather than the store.

## Row #17 - does a short extraction publish at all

**Surfaced by Fowler and explicitly NOT ruled by him**, because it decides what a
reader gets, which is the Editor's and the owner's altitude (section 14).

**The situation.** `extract.reject_too_short` does not exist. Roughly 200 of the
206 cards in row #6's table were `too_short` and published anyway, because
**Owner override O3** says a shape signal records and lets the item continue.
It is one knob and one branch beside two that exist.

**The premise this row shipped with was wrong, and the correction is the whole
value of the row.** It said "an abstract-form feed gets `brief=True,
failure_code=None` while an article-form feed with 35 words gets `brief=True,
failure_code=TOO_SHORT`, so the two facts are already distinguishable and no
contract change is needed". Measured 2026-09-17 on a developer machine, three
prose sentences totalling 34 words: **both forms carry `too_short`.** The signal
does not read the declared form at all. A `reject_too_short` built on the stated
premise would have silently rejected every feed a curator registered as
`abstract` - the feeds that are short because a person declared them so.

**What shipped, 2026-09-17.** The knob, defaulting **false**, so nothing about
today's output moved and O3 stands. The branch is guarded on the declared form:
a registered `abstract` is never rejected by it whatever it is set to, because
short is the property that feed was registered for. The signal is still recorded
either way - the item IS short and the census says so; the form changes the
consequence, never the fact.

**What is still a decision, and it is smaller than the row thought.** Whether to
set `reject_too_short` true. That overturns O3 and must amend it in the same
commit (section 0). Row #6 already removed the measured benefit by retiring the
four hosts, so what remains is a rule for the next host that does it, against a
cost of roughly **386 genuine short items** dropped. The guard means abstracts
are not part of that cost any more. It is an Editor and owner call (section 14).


## Rejected

Recorded so nobody proposes them again. Each is a dated decision, not a law
(section 0a) - what would reopen it is named.

| Proposal | Why it was refused | What would reopen it |
| --- | --- | --- |
| Cut the day to 90-120 items | The digest is a self-curating feed of digests, not a fixed-size bulletin. Content chooses its position and its relevance; we do not choose content, and more desks are coming rather than fewer | Nothing on the present design. The day is bounded by row #8's ceilings, which refuse without choosing |
| Per-day TF-IDF over headline words | Refused as a dependency, and that reason was wrong - it is about twenty lines of `collections.Counter` and `math.log`, no install and no shipped bytes. It stands refused because the comparison this project bets on is semantic and over the summary, and a word-overlap score is neither | Row #12 measuring it beating the shipped scorer on the same labels |
| A canonical "what happened" line from the summariser | Cannot be backfilled, so no committed day can measure it | A measured failure that only a rewritten summary could reach |
| Encode the article's lede and compare that | Proposed on 2026-09-15 and refused the same day. It serves no purpose the summary does not already serve, and the premise of this project is that the summariser did its job - so the comparison is over what the summariser wrote. The encoder's 256-token window meant it was never the whole article either | A measurement showing our summaries of one story diverge in a way the articles do not |
| Shared rare title tokens as a term in the composite | Its different-pair p99 is 1.0000 - about one different pair in a hundred scores a perfect match, which over 9,055 pairs is roughly 90 wrong pairs each handed a full weight. Separation 35.8 percent, the weakest of the three | The same distribution measured conditioned on the cosine already being near the floor, rather than over random pairs 99.9 percent of which are nowhere near the decision |
| Writing the chrome ledger from the work shards | A shard sees `index % shards` of the day, so it cannot count distinct pages a host served, and eight shards incrementing one key through a `merge=union` CSV is a race already paid for twice | Sharding changing so one host's items land in one shard - which `stages/common.py` deliberately refuses, because it would concentrate long articles on one worker |
| Keying the chrome ledger on `source_id` | Chrome belongs to the server template, not the feed. Keying on the feed fragments the evidence and re-makes the mistake row #2 repaired | A measurement showing two feeds on one host serve different templates |
| Rebalance which desks get space | Same ruling as the day size: content chooses its position | Nothing on the present design |
| Let the cross-source count pick the day's leads | Not refused - **taken**, as row #11, with the count gated behind a recall floor so it cannot feed noise into the most valuable slots on the page | - |


## Which page owns which question

Ruled by Fowler, 2026-09-15. One page answers one question; a page that would
end up holding two gets a split rather than a section.

| Question a person arrives holding | Page | New? |
| --- | --- | --- |
| Why did two items become one story, and on what score? | `docs/architecture/publishing/layout.md`, the same-story section and its flowchart | Existing. `docs/agents/bootstrap.md` already routes here. The flowchart gains the veto box and the composite box |
| What are the weights, and what did the labels say? | Same page, the `What chose 0.94` section, retitled to what it now decides | Existing |
| **Why does a host serve chrome instead of an article, and what do we do about it?** | **`docs/architecture/extraction/chrome.md`** | **New.** That directory holds only `elements.md` today. The question stands alone - somebody arrives holding "why did this host publish 200 empty cards" without needing another page's title in the sentence |
| Where does `state/chrome.csv` live, what is its grain, does its read carry a window? | `docs/architecture/contracts/schemas.md` | Existing - one row |
| Does this read cost more as the repository grows? | `docs/concepts/growing-reads.md`, under `A cover that is not a clock` | Existing - one paragraph beside `state/traces/` |
| What do the three new knobs do? | `docs/concepts/config.md` | Existing |
| What does a `boilerplate` cell in item-health mean now? | `docs/architecture/sources/item-health.md` | Existing |
| What ages out of `state/`, and on what age? | `docs/architecture/publishing/retention.md` | Existing - the chrome prune joins the inventory |
| **Why did a source retire itself, and what did it have to fail for how long?** | `docs/architecture/sources/i-feed.md`, beside the rest and the `410 Gone` retirement it already owns | **Existing.** A second cause on the same page, not a second page - a reader arriving with "why did we stop asking this feed" wants one answer, not two |
| **What does the source-quality panel show, and how do I read it?** | `docs/concepts/console-design.md` | Existing. The panel's own vocabulary joins the console's |
| **Where does the page order come from once age decays at read time?** | `docs/architecture/publishing/layout.md`, the section row #11 adds with its mermaid diagram | Existing |

**The chrome rule does not go in `item-health.md` or `trust-boundary.md`.** Both
already answer their own question, and a chrome subsystem inside either makes a
page hold two answers.

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
- ~~Nothing is removed from the page until recall is measured.~~ **Overruled by
  the owner, 2026-09-14** - a duplicate is worse than a miss. Row #5 folds a
  group's members behind publisher pills before recall is measured, and every
  member keeps its own page, its archive entry and its search entry, so nothing
  is removed. That reachability is what the ruling bought the line back with.

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
