# What a published item says about itself

**Last Updated**: 2026-09-23

Beyond its words, a published story carries five fields saying why it is on the
page and whose clock its time came off, plus two saying whether another source
ran it. This page holds what each one means, what an absent one means, and the
two fields that exist for a revision no run has ever made. Where the payload
sits and what a reader's address looks like is [layout.md](layout.md).

## An item says why it is here, and whose clock its time is

The planning step scores every story before a single model loads ([../sources/discovery.md](../sources/discovery.md#ranking-is-arithmetic-not-judgement)), and until 2026-08-31 the whole of that arithmetic was thrown away at the end of the plan job. The published item now carries five fields. **Nothing new is computed for them**: four were the score's own terms when they landed, and the fifth is a choice `rank.appeared_at` was already making and discarding one line later. **Two of the four have since stopped being terms**, and both are still published - `on_front_page` since 2026-09-13, and `carried_by` still buys a place but a much smaller one.

| Field | What it says | What it is not | What it buys in the order |
| --- | --- | --- | --- |
| `carried_by` | How many feeds carried **this one address** today. | Not "also covered by N sources". Two outlets writing their own piece produce two addresses and both read 1. The honest cross-outlet version is a different measurement. | A flat `collect.carriage_step`, 0.25, **once**, at two carriers or more. Three carriers buy the same as two, and six buy the same as two. The count is published and only the fact is paid for. |
| `watchlist_hit` | The story names an entity on the watchlist. | Not an importance grade. It is one bonus term of several. | `collect.watchlist_bonus`, 0.5 - the fourth and smallest of the four ranked terms. |
| `on_front_page` | An aggregator voted for it. | A vote, never a discovery - a salience feed never puts a new address in the pool. | **Nothing, since 2026-09-13.** It fired on 8 of 5,682 published stories while being worth more than a tier step, so it was retired as a term and kept as a fact. |
| `rank_score` | What the planning step scored the story at. Comparable across the whole day, because every desk uses one scale. | Not a quality score and not a confidence band. `band` is the quality signal and it is measured somewhere else entirely ([../../concepts/evaluation.md](../../concepts/evaluation.md)). | It **is** the order. Which shape of arithmetic produced it is `RunRecord.rank_version`. |
| `time_source` | Which clock `published_at` came from: `feed`, `first_seen`, or `unknown`. | Not a second timestamp. There is one time on the item and this says whose it is. | Nothing directly. `published_at` feeds the recency term and this says whose clock it came off. |

**`carried_by` bought a great deal more until 2026-09-13, and what it bought was a claim the page refuses in words.** The term multiplied a story's authority by `1 + repetition_weight * (carried_by - 1)`, so two feeds doubled it and three tripled it, with no ceiling. Because the field counts feeds carrying **one address** it measures syndication rather than agreement, so what the ranker was paying for was the same wire copy arriving twice - while [../../concepts/digest.md](../../concepts/digest.md) already refused to print "three sources covered this" on the grounds that the number does not support the claim. Measured 2026-09-13 over the 13 committed days that carry `rank_score`: a second feed carries 5.7 percent of the stream and those stories held 20.8 percent of the head; at a flat step they hold 7.7 percent. **The field is written and read exactly as before** - no payload schema moved - and only what the ranker pays for it changed.

**All five are optional, and an absent one reads as unknown.** Every day published before the fields existed omits all five - 11 days and 3,596 items when they landed, counted 2026-08-31 - and not one of them was rewritten (`CLAUDE.md` section 11). A reader of the payload - our own page included - must not fill an absent field with a default, because every plausible default is a false claim: `0` for `carried_by` says no feed carried the story, `false` for `on_front_page` denies a vote that was never counted, and `0.0` for `rank_score` puts the story at the bottom of its desk. `null` is the only honest answer and the contract test over every committed day asserts it.

`time_source` earns its place because the fallback it names is silent. `published_at` is the feed's own date where the feed gave a usable one, and our first sight of the address where it did not ([../sources/freshness.md](../sources/freshness.md)). Both are the same kind of string, so a page printing the time cannot say whose it is without this field. Measured 2026-08-31 on the committed 2026-08-30 payload - the newest day that had finished publishing - 431 items: 305 distinct `HH:mm` values, and 5 stamps, 1.2 percent, within two minutes of a run stamp. **That last figure is an upper bound on the fallback and not a count of it**, because until this field shipped nothing committed recorded the choice, and a feed's own stamp can land near a run by chance. The fallback is rare either way, which is exactly why it needs naming: a reader has no way to spot the 1 percent.

### The item's own stamp is what reads it, and what it can and cannot say

The day's stream orders by `published_at`, newest first, and every story prints its own stamp beside its heading. So `time_source` stopped being a field with no reader and became the thing that decides how a story's stamp is drawn ([../../concepts/ui-shell.md](../../concepts/ui-shell.md)). Re-counted 2026-09-12 on a developer machine / Python 3.14.2 over every committed day - 22 days, 8,922 stories:

| `time_source` | Stories | Share | What the item prints |
| --- | --- | --- | --- |
| `feed` | 5,171 | 58.0 percent | the clock, unmarked |
| `first_seen` | 18 | 0.2 percent | the clock, with a mark |
| `unknown` | 0 | 0 | nothing - there is no number to print |
| absent | 3,733 | 41.8 percent | the clock, unattributed and unmarked |

**Two of those four numbers move and the third does not, and the difference is the point.** The absent count is **frozen at 3,733** - every day published since the field landed carries it, so that column cannot grow - while its *share* falls with every run. A share read off this table more than a few days old is a reading of that morning.

The item prints digits only, from 2026-09-06: a clock, and a date in front of it when the stamp is not from the day being read. The mark is what carries the `first_seen` case now that no word does.

**Where the stamp is drawn.** The stamp is the **fourth and last child of the item's eyebrow**, in the eyebrow's own type, and on a dated page it takes the slot the day link held. A search result keeps the day link there and draws no clock: that list spans days, and two dates on a line capped at four things is a duplicate. A shared rail down the stream's leading edge was the alternative and it is not used: it grouped stories into hour-wide runs and drew one marker per run, so most stories carried no time at all.

Three things follow from that table and each one moved the design.

**The absent case is the archive, not an edge case.** Two items in five predate the field. A story there carries a stamp `rank.appeared_at` chose the same way it chooses one today - only the label was thrown away - so the honest render is the stamp with no claim attached. Printing it as a feed time would be a claim the run never recorded; refusing to print it would delete a fact from 3,733 stories and leave ten of the first twelve committed days with no time on them at all.

**`unknown` has never happened** - 0 of 8,922 - so the branch is carried by the canary day, which plants one story of every state on purpose. A branch no fixture reaches ships with no test at all, and this one decides whether a story with no time still renders.

**"The feed gave a date and no clock" is not expressible, and no heuristic was invented for it.** `discover._published_at` reads `feedparser`'s parsed struct, which fills 00:00:00 for a date-only feed date - and a story genuinely published at midnight parses to the same thing. 47 of the 4,713 stories committed by 2026-09-02 are stamped exactly `T00:00:00Z`, 1.0 percent, and the payload cannot say which of the two each one is. Reading midnight as "no clock given" would mislabel a real midnight story, which is the invented-label failure this whole rule exists to avoid. The string stays in the vocabulary for the day a feed's own granularity is recorded; until then it prints only where the payload says there is no time at all.

## The same story from several sources says so

A day runs the same story from more than one of our feeds, and the published item
carries two fields that say so. The rule that decides it - the score, the headline
joiner, the figure veto, the window past midnight and what each costs - is
[autotune-content-similarity.md](autotune-content-similarity.md).

## The two revision fields stay, unwritten

**"A revision is visible or it does not happen" is a rule a revision would have
to meet, and never a description of shipped code.** No run can revise an item, so
nothing has ever had the chance to be visible or silent.

**Deleting the fields is not the cheap option it looks like.** Every persisted model is `extra="forbid"`, so a model without the two fields rejects every payload that carries them. Measured on this checkout, 2026-08-26: six committed days, 2,121 items, 2,121 carrying `updated_at`, 2,107 carrying `updated_by_run`, and **zero** carrying a value in either. Removal costs a read-side migration that strips two keys from every day forever, or a rewrite of all six committed payloads. Retention deletes nothing today (`retention.dry_run` is on, and the 13-month window `image_months` took on 2026-09-13 reaches no committed day), so waiting for the old payloads to age out is not available either. That is the whole price, and the reader gets nothing for it.

**The named trigger that would revive revision is a summarizer model swap, and it fired on 2026-08-27** ([../../concepts/evaluation.md](../../concepts/evaluation.md)). A better summarizer is the one event that makes words already published worth rewriting; a bug fix in the pipeline is not, and neither is a new field. Nothing was revised, and that is the correct answer here rather than an oversight: no comparison against the retired model was ever run, so nothing measured says the new summaries are better, and rewriting published words on an unmeasured hunch is the move Guardrail #10 forbids. What the swap does change is the run-manifest join the two fields exist for - from the first day the new model publishes, a day can hold summaries from two different models, so the join now has something to join.

**The promise is pinned by a test, not by this paragraph.** `backend/tests/pipeline/` asserts that a second run over an item the day already holds leaves its words, its `updated_at` and its `updated_by_run` untouched. A sentence on a page drifted once; the test fails the day the gates stop holding, which forces this page to be corrected in the same commit.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Filling an absent field with a default | Every plausible default is a false claim: `0` for `carried_by` says no feed carried the story, `false` for `on_front_page` denies a vote nobody counted, and `0.0` for `rank_score` puts the story at the bottom of its desk. `null` is the only honest answer. |
| Reading a `T00:00:00Z` stamp as "the feed gave a date and no clock" | A story genuinely published at midnight parses to the same thing - 47 of 4,713 committed stories are stamped exactly that - so the heuristic would mislabel a real midnight story. |
| A shared time rail down the stream's leading edge | It groups stories into hour-wide runs and draws one marker per run, so most stories carry no time at all. |
| Deleting `updated_at` and `updated_by_run` | Every persisted model is `extra="forbid"`, so removal costs a read-side migration that strips two keys from every day forever, or a rewrite of every committed payload - and the reader gets nothing for it. |
| Rewriting published summaries after the 2026-08-27 model swap | No comparison against the retired model was ever run, so nothing measured says the new summaries are better, and rewriting published words on an unmeasured hunch is the move Guardrail #10 forbids. |

## See also

- [layout.md](layout.md) - where the payload sits, and what a reader's address looks like.
- [how-a-day-is-ordered-and-what-each-desk-published.md](how-a-day-is-ordered-and-what-each-desk-published.md) - what `rank_score` is the order of, and what each desk's counts mean.
- [autotune-content-similarity.md](autotune-content-similarity.md) - when two items are one story.
- [../sources/discovery.md](../sources/discovery.md#ranking-is-arithmetic-not-judgement) - the arithmetic four of these fields were terms in.
- [../sources/freshness.md](../sources/freshness.md) - where an item's id and its `published_at` come from.
- [../../concepts/placement.md](../../concepts/placement.md) - the one order this payload carries.
- [../../concepts/ui-shell.md](../../concepts/ui-shell.md) - how the stamp is drawn.
- [../contracts/schemas.md](../contracts/schemas.md) - `DigestItem` and the versioning rule an absent field rests on.
