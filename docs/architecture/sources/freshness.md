# Freshness and Identity

**Last Updated**: 2026-08-26

How often the pipeline runs, what makes an article worth today's slot, what stops the same article being published twice, and how an item keeps its name across the runs of one day. This page owns the decisions the planning step makes before any model loads.

## The run happens five times each day

The runs start at 02:20, 06:20, 10:20, 14:20, and 18:20 UTC, expressed as
`20 2,6,10,14,18 * * *`. The digest is a thing you open in the morning and again
after lunch, and a once-a-day run makes the afternoon read stale by
construction. The exact workflow trigger contract is
[../../reference/github-actions.md](../../reference/github-actions.md).

**The 02:20 slot exists so the morning read is not waiting on the pipeline.** A
scheduled run starts 40 to 70 minutes after its cron minute, then takes 164 to
184 minutes end to end (`ubuntu-latest`, 2026-08-23/24, n=3). A first slot at
06:20 therefore did not publish until about 10:30. At 02:20 it publishes before
06:30. The slot also closes the gap after 18:20, so a story that broke late in
the evening is read at the top of the next day rather than eight hours into it.

Twenty past the hour, not the top of it. GitHub queues scheduled jobs by load, and the top of every hour is when everyone else asks.

The slots are four hours apart and a run takes under three, so two runs do not
overlap. If one ever did, the `digest` concurrency group queues the next rather
than cancelling it, because a run that is halfway through the day's items has
already paid for its weights.

Five runs share one day. They append to the same dated digest rather than replacing it, so the day grows through the day. That is only safe because an item's identity does not depend on its rank - see below.

## Age is a weight, never a gate

An article's age moves its score. It never removes it from the pool.

```
recency_bonus = recency_weight * 0.5 ** (age_hours / recency_half_life_hours)
```

With the shipped values (`recency_weight` 0.6, `recency_half_life_hours` 18.0) a brand-new article carries +0.6, an 18-hour-old one +0.3, a three-day-old one +0.02. A week-old piece is worth almost nothing and is still allowed to win if nothing else that day comes close.

**There is no age cutoff.** A hard window throws away the best item on a quiet day for being nine hours too old, and the reader gets a thin digest instead of a good one that happens to be from yesterday. The decay already puts fresh news on top; a cutoff only adds a way to lose.

## An undated article still has an age

Plenty of feeds carry no publish date, and the ones that omit it omit it consistently. For those the only honest age is the first time we saw the address, so the planning step writes one down.

`state/seen/<YYYY-MM>.csv` is append-only: the URL key, the canonical address, the timestamp, and the run that saw it first. An address seen for the first time is treated as new, which is the truth as far as we can check it. Every run after that reads its real first-sighting.

The shard is monthly and the lookback is `seen_window_days` (90). An address older than the window is not worth a lookup - its recency bonus has already decayed to nothing.

## A date in the future is ignored

A feed that stamps tomorrow on today's article takes the top slot every single run, forever. `max_future_hours` (6.0) is the tolerance: a publish date more than six hours ahead of now is discarded, and the item falls back to first-sighting like any undated one.

Six hours, not zero. Clock skew between a publisher and the runner is real and small; an embargo stamp is real and large. Six hours separates them without needing to know which is which.

## Publishing twice is prevented by a record, not by a window

An article published at 23:00 on Monday is seven hours old at 06:00 on Tuesday. Any freshness rule you can write will happily plan it a second time.

So the assemble stage appends to `state/published.csv`, and the planning step skips any address already in it. **The assemble stage writes it, not the planning step** - until a digest is committed, nothing was published, and a run that dies mid-way must not leave behind a claim that it finished.

No run ever rewrites either ledger. A mutable `published` flag on a seen row would turn an append into a read-modify-write over the whole file, and two runs racing on that would lose rows. A one-shot migration by an operator is the one exception, and it has happened once - see below.

### The published ledger is one file, and the read has no window

`state/seen/` and `state/feed-health/` shard by month. `state/published.csv` does
not, and its dedupe read is not windowed either. Both follow from the question
it answers: **published is forever.** "Have we ever published this address?" has
no time bound, so every row has to be read on every run. Sharding a file you
always read whole adds file opens and removes nothing, and filtering rows after
reading them saves no I/O at all. The general rule is in
[../contracts/schemas.md](../contracts/schemas.md).

The bound this costs, measured 2026-08-26 and recorded in
[../../reference/measurements.md](../../reference/measurements.md): 2,097 rows
at 110.7 B, so 40.4 MB a year at the structural ceiling of 1,000 rows a day.
`load_published` peaks at 500.5 B a row while it reads, which is 183 MB at that
ceiling - 1.1 percent of the runner's 16 GB, in the one job that loads no model.

**`canonical_url` was 48.6 percent of the row, and it is gone.**
`load_published` reads `url_key` and `published_on` by name, and nothing else
opens the file, so the column was paying for a lookup no run ever made. It left
on 2026-08-26: the contract narrowed, and
`backend/utilities/migrate_published_ledger.py` rewrote the committed ledger in
the same commit. The file went from 451,509 B to 232,114 B - 219,395 B and
104.6 B off every row - on a ledger that has no time bound and therefore never
stops growing. That is 20.0 MB a year at the rate the ledger itself records and
38.2 MB at the structural ceiling. The saving was worth taking only because the
ledger is unbounded and the migration was one file and one pass; the same
arithmetic over a file that stops growing would not have earned a contract
break.

**One commit, because the reader never cared and the writer never bargains.**
`load_published` maps cells by name, so it returns the same mapping from a
five-column file and from a four-column one - measured 2026-08-26 over two
fixtures of eleven real rows in
`backend/tests/test_ledger.py::test_load_published_answers_the_same_from_either_header`.
The check that does care is `require_matching_header`, and it is called from
`_append` and from nothing on the read path: a run that tried to append a
four-column row onto a five-column file raises `Migrate the ledger before
appending to it`. So the shape change and the file rewrite are one atomic act,
and there was no read-side transition to stage.

**What it cost, and how to get an address back.** What the column bought was
that a person could grep the ledger for an address and get the day and the item
id back. That look is now a two-step join, and the answer is exact:

1. Find the row in `state/published.csv`. It gives `published_on` and `item_id`.
2. Open `frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json` for that date and
   read `source_url` off the item with that `item_id`.

Worked, on a real row:

```text
2026-08-26,india-4491424356
-> frontend/public/digest/2026/08/26/digest.json
-> https://newslaundry.com/2026/08/26/knives-pistols-and-aura-farming-inside-delhis-teen-gangs
```

The join holds for the whole ledger rather than in principle: all 2,097
committed rows resolve to a `source_url`, with no absent day and no absent item
(measured 2026-08-26). It keeps holding because retention may never touch a
day's JSON payload ([../publishing/layout.md](../publishing/layout.md)) - it
deletes old visuals and nothing else. The direction that got harder is address
to row: that now needs the sha256 of the canonicalised URL computed first, which
is a tool run rather than a grep
([../../how-to/troubleshoot-one-url.md](../../how-to/troubleshoot-one-url.md)
shows how much canonicalisation sits between a pasted URL and its key).

## An item's name comes from its address

`item_id` is `<vertical>-<ten digits>`, derived from the URL key and nothing else.

It used to be the rank position. That broke the moment a day had more than one run: run 2 re-ranked the same stories, every id shifted, and an article that moved one place arrived as a new item and published twice. Deriving the id from the address means a later run recognises the work the earlier one already did.

A collision - two addresses landing on the same ten digits - is rare and is a contract failure that stops the run, so the second one steps forward until it finds a free number. Resolved in address order, so the answer depends on the pool and never on the ranking.

## Supply decides the size of the day, not a cap

There is no daily item cap and no per-vertical cap. What a day publishes is what survives the score and `max_per_source` (2), which stops one prolific outlet filling a vertical.

`run.safety_ceiling_per_run` (160) exists and is not a cap. It is a crash guard: if a feed change or a canonicalisation bug ever produces thousands of candidates, the run stops rather than spending six hours discovering it. A normal day is nowhere near it - the largest ever planned is 149 items. If a run ever hits it, the answer is to find the bug, not to raise the number. What sets the number is the worst case the `work` and `route` jobs both have to finish, not an editorial view of how long a day should be ([../../concepts/config.md](../../concepts/config.md)).

## Design rationale

The fifth slot was added at 02:20 rather than 22:20. Both are one more attempt
and both cost the same runner time. A 22:20 slot would add to a UTC day that is
about to end, so its work is visible for under two hours before the date rolls.
02:20 puts the same work at the front of the day a reader is about to open, and
the articles it would have caught at 22:20 are still in the pool the next
morning because age is a weight and not a gate.

The daily cap was removed because it was answering a question nobody had asked. It decided in advance that twenty articles was the right number of good articles for a day, which is not a thing that can be known in advance - some days have thirty worth reading and some have six. The score already orders them; a cap only truncates the order at an arbitrary point. Supply and the score are the honest answer, and the ceiling catches the failure mode a cap was accidentally also catching.

**Reader dissented, and the dissent stays on the record.** Their case: 146 feeds produce roughly 60 fresh items a day, AI holds about a third of them, and with no per-vertical ceiling AI eats the page. They named this the one change in the set that cannot be patched later, and they brought evidence rather than a worry - the 2026-08-21 page published four items, all AI, and the words Energy, India, World and Business do not appear on it. The counter is that `max_per_source` and each vertical's own `min_feeds` floor already spread a day, and that if the prediction holds the correction is a number in `config/taxonomy.json` rather than a code change. The test is falsifiable and worth running: **if most days come out one-vertical, Reader was right, and the fix belongs in the source list rather than in a cap.**

The supply premise in that dissent is superseded. It was written when a day was
four items. On 2026-08-24 the day published 731 and every run planned 200, so
"roughly 60 fresh items a day" is now low by an order of magnitude. Read the
dissent for its argument about vertical mix, not for its volume figure.

The age rule went the same way for the same reason. A 24-hour cutoff and a decay curve agree on every ordinary day, and disagree exactly on the days that matter: the quiet ones, where the cutoff empties a vertical and the curve publishes the best thing available. Losing a good item to a rule that was meant to protect quality is the worst outcome available.

Both first-sighting and the published ledger are append-only files under `state/`, committed by CI. That is not a preference - it is the only shape available. There is no database (Rule #1), and anything a later run must read has to survive as a committed file.

### A per-run reading budget was proposed on 2026-08-25 and refused

Authority: Carmack and Fowler. The proposal was a new knob at the planning step,
capping how many items one run may plan for reading, separate from the crash
guard. The value floated was about 59 items - the 40-minute route stage clock
divided by the slowest measured per-item routing cost, `2400 / 40.3`. Four facts
refused it.

| Why it was refused | The evidence |
| --- | --- |
| The bound it adds already exists one stage later, and it is a clock rather than a count | `cli.stage_route` stops its loop at `run.route_budget_minutes` (40 minutes), inside the route job's 50-minute timeout. A count has to be set for the worst host, so the number that fits a slow host leaves a fast one idle. The router-side version of the same proposal was refused for the same reason - see [../publishing/visuals.md](../publishing/visuals.md). |
| The loss it answered is already prevented | The `routes` artifact upload in `.github/workflows/digest.yml` carries `if: always()`. A route stage that runs out of clock still hands over every decision it made. What cost four of the six runs on 2026-08-24/25 their visuals was a cancelled job skipping an upload step that had no condition on it. That step has one now. |
| The number behind it is contaminated | The 20.7 s and 40.3 s per-item route figures were measured over 703 items that all ran with `diagram` in `visuals.enabled_kinds`, so the model was asked about every one of them: `asked=False` appears zero times in all 703. `diagram` is off now, and with it off a measured 68 of 145 items (46.9 percent) never reach the model at all. |
| It throttles the wrong stage, and a reader pays for it | A plan-stage budget bounds what `summarize` is handed, in order to protect `route`. `summarize` runs as four worker jobs by default, eight at the ceiling, and has no stage clock at all - its only bound is the `work` job's 330-minute timeout. `route` is one job with a 40-minute stage clock. On 2026-08-24 the committed digest carries **731 items**; a 59-item budget over five runs caps that day at 295 and deletes about 436 of them. |

**The corrected cost, labelled an estimate because that is what it is (Rule
#10).** Multiply the measured per-item cost by the measured share that still
reaches the model: about **11.0 s an item on the fast host and 21.4 s on the slow
one**, which is roughly **218 and 112 items** inside the 40-minute clock. Nobody
has observed either figure. Both are two measurements multiplied together, and
both treat a skipped item as free when it still costs a reachability check and a
file write. The proposal's 59 is about half the slow-host estimate and a quarter
of the fast-host one, so the knob would have been set from a number the
configuration change had already moved.

**The real cause is named here and fixed nowhere.** `rank.plan_vertical` orders
candidates and then admits all of them - `_take` refuses only what
`max_per_source` (2) refuses. **There is no score floor anywhere in the
pipeline.** The only other bound is `run.safety_ceiling_per_run`, and that guard
is already inside the working range rather than above it: the plan job on
2026-08-25 logged `safety ceiling reached planned=221 ceiling=200`, so what
decided the size of that run was the crash guard and not the score
([../../reference/measurements.md](../../reference/measurements.md)). A budget
truncates an ordered list at a second arbitrary point. A score floor rejects an
item for not being worth reading, which is the question actually being asked.
**The trigger:** a floor needs an instrument that can say what a score is worth,
so it waits on the retrieval eval. Until that lands the number would be a guess,
and guessing it is what this refusal is about.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A 24-hour freshness window | Empties a vertical on a quiet day and costs the digest its best item. The decay already ranks fresh news first without ever losing anything. |
| A daily item cap | Decides how many good articles a day is allowed to have before knowing what the day contains. |
| Treating an undated article as brand new every run | It would win the top slot on every run forever. First sighting is the fix, and it costs one append-only row. |
| A `published` boolean on the seen row | Turns an append into a read-modify-write over the whole history, and two runs racing on it lose rows. |
| Rejecting any future date outright | Clock skew between a publisher and the runner is normal and small. A zero tolerance would drop real articles for being three minutes early. |
| Keeping rank position as the item id | Run 2 of a day renumbers every story, and anything that moved one place publishes twice. |
| Writing the published ledger at plan time | A run that dies mid-way would leave behind a claim it published something it did not, and the article would never be publishable again. |
| A per-run reading budget at the planning step | Refused 2026-08-25 by Carmack and Fowler. The bound already exists one stage later and is a clock; the artifact loss it answered already carries `if: always()`; its value came from a measurement taken before `diagram` was switched off; and it deletes about 436 items from a 731-item day. See the design rationale above. |
| A score floor set now rather than measured | A floor is the right control and the wrong thing to guess. It waits on the retrieval eval, which is the instrument that can say what a score is worth. |
| Sharding `state/published.csv` by month | The question has no time bound, so every shard is opened on every run. It adds file opens and removes nothing. |
| Windowing the dedupe read without sharding the file | Filtering rows after reading them saves no I/O. A window pays only when it can decide which files to skip. |
| Pruning the published ledger | It is the only record of what a digest carried. Pruning makes a re-publish look new, which is the exact failure the ledger exists to stop. |
| Keeping `canonical_url` on the published row for forensics | Dropped 2026-08-26. It was 48.6 percent of a row on a ledger with no time bound, no reader ever opened it, and all 2,097 committed rows recover their address by joining `item_id` and `published_on` against a day payload retention may not touch. |

## See also

- [discovery.md](discovery.md) - what the sources are, how they are tiered, and how the score is built.
- [../contracts/schemas.md](../contracts/schemas.md) - the row contracts under `state/`, and the rule that decides when a ledger shards.
- [../../reference/measurements.md](../../reference/measurements.md) - the ledger sizes, the read cost, and the ceiling measurement quoted above.
- [health.md](health.md) - the record of what every feed did, and the quarantine that reads it.
- [../contracts/determinism.md](../contracts/determinism.md) - the fingerprint that makes "this re-run changed nothing" checkable.
- [../publishing/visuals.md](../publishing/visuals.md) - the route stage clock, and the router-side version of the budget refused above.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages, and which of them see the whole day.
- [../../concepts/config.md](../../concepts/config.md) - where these knobs live and the knob-versus-fact rule.
- [../../reference/github-actions.md](../../reference/github-actions.md) - workflow names and exact triggers.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract.
