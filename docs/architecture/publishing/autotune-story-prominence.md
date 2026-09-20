# What decides a story's prominence

**Last Updated**: 2026-09-20

What puts one story above another on the page, and what would make those weights
fit themselves instead of being chosen by hand.

**Status: a stub. Nothing here is built, and no plan builds it yet.** What is
below is the current hand-set state and the shape a fitted version would take.
Anything stated as future is an intention, not a design of record.

## What is hand-set today

The leading block is a weighted sum, and every weight in it is a number a person
chose. [layout.md](layout.md) owns the table and what each term means; these are
the values in `config/idhazh.json` as this stub is written:

| Knob | Ships at | What it weighs |
| --- | ---: | --- |
| `ui.lead_rank_weight` | 1.0 | the plan-time score every story carries |
| `ui.lead_shared_subject_weight` | 0.2 | a flat step where enough sources named one entity |
| `ui.lead_also_covered_weight` | 0.0 | other sources carrying the story, per source |
| `placement.freshness_decay_at_scale` | 0.5 | how much age has cost by the scale hour |
| `collect.carriage_step` | 0.25 | a flat step at two carriers or more |
| `collect.watchlist_bonus` | 0.5 | the story names a watchlist entity |

## What this page must not claim

**We cannot measure trending, and we cannot measure popularity.** There is no
analytics SDK and `CLAUDE.md` section 10 forbids one, so nothing here knows what
a reader read. What the pipeline knows is how many of **our own feeds** carried a
story and how many named the same entity - a fact about our feed set, never a
claim about the world.

So the honest subject of this page is **prominence**: how high a story sits,
which we choose. A page named for popularity would tell a reader we know
something we do not (`CLAUDE.md` section 0b).

## What would have to be true before a line is fitted

- A signal that is measured rather than chosen, and a written statement of what it is a fact about.
- A judged sample the fit is scored against, in the venue that already exists ([llm-council.md](llm-council.md)).
- A rule for how far the weights may move in a day, because the published order is what a reader sees.

## See also

- [layout.md](layout.md) - where the page order comes from, and the weighted score this page would tune.
- [../../concepts/placement.md](../../concepts/placement.md) - the reading order inside a frame, and the freshness curve.
- [llm-council.md](llm-council.md) - the room a fitted line would be judged in.
- [autotune-content-similarity.md](autotune-content-similarity.md) - the one line that already fits itself, and the shape any other would copy.
- [../../concepts/config.md](../../concepts/config.md) - what belongs in a knob, and why a hand-set number is not a defect on its own.
