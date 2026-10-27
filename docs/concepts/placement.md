# Placement

**Last Updated**: 2026-10-10

How admitted stories are ordered and filed in a published day. [Discovery](../architecture/sources/discovery.md#ranking-is-arithmetic-not-judgement) owns the selection score; [placement.py](../../backend/idhazh/placement.py) applies the page's ordering and desk rules.

## Why this story is above that one

Selection scores use feed trust and reliability, repeated carriage of the same link, watchlist matches, subject weights and freshness. Ranking runs before the article is fetched, so these are selection signals rather than a model's judgment of the article.

Repeated carriage earns one fixed addition, not a multiplier. Several feeds carrying one link do not establish independent reporting. A story uses its highest matching lens weight, not the sum. A lens is a weighted subject; a desk is the section in which the reader finds the story.

Admission and order are separate. Only `collect.max_age_hours` in the table below refuses an old candidate. Placement does not remove an admitted story because it aged.

### The numeric controls and where they live

The table names the live controls. Their values stay in configuration and are
not copied here.

| What it measures | Where the number lives |
| --- | --- |
| Trust assigned to each source tier | `taxonomy.source_tiers[].weight` |
| What one more feed carrying the same link is worth | `collect.carriage_step` |
| Naming a company or person we follow | `collect.watchlist_bonus` |
| How far freshness may move a score | `collect.recency_weight` |
| The hours in which that freshness halves | `collect.recency_half_life_hours` |
| The age past which a story may not be added at all | `collect.max_age_hours` |
| The lowest a feed's record may drag it | `collect.reliability_floor` |
| The days of record that reliability reads | `collect.reliability_window_days` |
| A subject several sources named, in the leading block | `ui.lead_shared_subject_weight` |
| Sources that have to name it before it counts | `ui.lead_cluster_floor` |
| How much of a lead's score the selection number is | `ui.lead_rank_weight` |
| What each other source carrying the story adds | `ui.lead_also_covered_weight` |
| Hours a leading story keeps its full score before age counts | `placement.freshness_offset_hours` |
| Hours past that at which it reaches the share below | `placement.freshness_scale_hours` |
| Score share retained at that age | `placement.freshness_decay_at_scale` |

Per-feed weights live in `config/sources.json`; per-lens weights live in `config/taxonomy.json`. The scoring code reads their current values when it ranks a story. Reliability comes from recent feed outcomes, stays between its configured floor and 1.0, and treats a feed with no recent record as fully reliable.

## A worked example

The real scorer runs against [worked-example.json](../../tests/fixtures/rank/worked-example.json), whose fixed clock is 2026-09-13 at 12:00 UTC. The test checks the names, scores and order below.

| Story | How its number is built | Score |
| --- | --- | ---: |
| A trade-press scoop on a watchlist company | trust 0.6, one feed, plus 0.8 of bonuses, plus 0.58 for being one hour old | 1.977334 |
| A ministry statement a wire service also carried | trust 1.0, plus 0.25 because a second feed carried it, plus 0.48 for being six hours old | 1.72622 |
| A community post on a feed we turned down | trust 0.3, cut to 0.12 by the feed's own weight and its record, plus 0.28 for being twenty hours old | 0.397762 |

The first story's subject and freshness bonuses outweigh the second story's stronger source. This example explains the arithmetic; it does not establish that the first story is editorially better.

## One order inside what a run added

Sort each run's new stories by `rank_score` descending, then story time, then address. A missing score sorts last rather than becoming zero. Use stable ordering and deterministic tie-breaks.

Keep run blocks in publication order. `introduced_by_run` must never decrease down the day's items. Sorting the whole day would move stories a reader had already read, so sorting and head constraints apply within each run's block.

The leading block is separate. Assemble chooses it across the finished day and may refresh it each run without reordering the stream. It combines the selection score with shared-subject and coverage signals, then applies the story's current age. [The published order](../architecture/publishing/how-a-day-is-ordered-and-what-each-desk-published.md#the-weighted-score-that-chooses-the-leading-block) owns that formula.

### The leading score's Gaussian age multiplier

`placement.freshness_multiplier` applies a Gaussian curve with a flat shoulder.
Age is the hours from the item's `published_at` to the run's `generated_at`, both
UTC. The leading block is chosen during backend assembly; a browser reads those
stored leads and does not choose them again from its own clock.

Inside `freshness_offset_hours` the multiplier is exactly 1.0. Past that offset,
the calculation is:

```text
past_offset = age_hours - freshness_offset_hours
sigma_squared = -(freshness_scale_hours * freshness_scale_hours)
                / (2 * log(freshness_decay_at_scale))
multiplier = exp(-(past_offset * past_offset) / (2 * sigma_squared))
```

At `freshness_scale_hours` past the offset, the multiplier equals
`freshness_decay_at_scale`. With the committed settings, a story keeps its full
score for six hours and half its score at thirty hours old. The curve approaches
zero; it has no finite cutoff. A missing date or a future date receives 1.0.
Setting `freshness_decay_at_scale` to 1.0 disables the curve exactly.

Age multiplies the weighted leading score; it is not an added bonus. It changes
neither grouping nor the fixed story stream. The separate plan-time recency
bonus decides which candidates earn a slot before extraction.
[test_freshness_curve.py](../../backend/tests/placement/test_freshness_curve.py)
checks the shoulder, the derived width and the disabled case;
[test_leading_stories.py](../../backend/tests/test_leading_stories.py) checks
that later assembly can change the leads without changing the stored rank scores.

## The frame, and the three things it may never do

The frame spreads the first stories across desks and feeds.

| Knob | Value | Meaning |
| --- | ---: | --- |
| `placement.head_items` | 20 | Number of first slots governed by the frame |
| `placement.max_desk_in_head` | 5 | Maximum slots one desk normally takes there |
| `placement.head_no_repeat` | 10 | First slots in which a feed should not repeat |

- A cap displaces a story within the block; it never drops it or shortens the list.
- The first slot remains the ranker's first pick.
- If the constraints cannot fill the head, admit the best held story. A single-desk block keeps the score's order.

Count the desk the reader sees: the article's classified desk when available, otherwise its feed's vertical.

## What a desk may not fall below, and may not rise above

Desk floors and ceilings live in `config/taxonomy.json`. A floor is a story count; a ceiling is a share of the day. Refiling runs over the whole day, not just the head.

- Refile only stories already admitted to this day. Do not bypass a gate or borrow from a previous day.
- Do not send a story to a desk that this run will not render.
- Do not take a donor desk below its own floor to fill another.
- If a desk cannot be filled, leave it thin and retain the reason in the day's record.
- If a ceiling has no eligible destination, leave the story where it is. Never shorten the day to meet a share.

### A story's second desk, and where the overflow goes

A story may have one eligible second desk. Use the article's classification, with the source desk as the fallback where applicable. The second desk must differ from the filed desk and must be available in this run.

Cross-filing changes the desk assignment, not the story count. The story appears once in the stream. Without eligible alternate assignments, the bounds cannot force redistribution.

### What the number on a pill promises

A desk pill counts exactly the set its page lists. The current set is stories filed under that desk, not every secondary association. Change the count and the page's filter together.

## Design rationale

Stable run blocks preserve a reader's place. A separate leading block can still surface the day's strongest current stories. Diversity constraints reorder rather than delete, so presentation rules cannot silently reduce coverage. Desk floors use counts because a section needs enough stories to be useful; ceilings use shares because crowding depends on the size of the day.

## See also

- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - scoring and candidate selection.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - admission by age.
- [../architecture/publishing/how-a-day-is-ordered-and-what-each-desk-published.md](../architecture/publishing/how-a-day-is-ordered-and-what-each-desk-published.md) - published order and leading stories.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - verification.
