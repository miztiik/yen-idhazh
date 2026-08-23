# Freshness and Identity

**Last Updated**: 2026-08-23

How often the pipeline runs, what makes an article worth today's slot, what stops the same article being published twice, and how an item keeps its name across the runs of one day. This page owns the decisions the planning step makes before any model loads.

## The run happens every six hours

Four runs a day, at `20 */6 * * *`. The digest is a thing you open in the morning and again after lunch, and a once-a-day run makes the afternoon read stale by construction.

Twenty past the hour, not the top of it. GitHub queues scheduled jobs by load, and the top of every hour is when everyone else asks.

Four runs share one day. They append to the same dated digest rather than replacing it, so the day grows through the day. That is only safe because an item's identity does not depend on its rank - see below.

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

Neither ledger is ever rewritten. A mutable `published` flag on a seen row would turn an append into a read-modify-write over the whole file, and two runs racing on that would lose rows.

## An item's name comes from its address

`item_id` is `<vertical>-<ten digits>`, derived from the URL key and nothing else.

It used to be the rank position. That broke the moment a day had more than one run: run 2 re-ranked the same stories, every id shifted, and an article that moved one place arrived as a new item and published twice. Deriving the id from the address means a later run recognises the work the earlier one already did.

A collision - two addresses landing on the same ten digits - is rare and is a contract failure that stops the run, so the second one steps forward until it finds a free number. Resolved in address order, so the answer depends on the pool and never on the ranking.

## Supply decides the size of the day, not a cap

There is no daily item cap and no per-vertical cap. What a day publishes is what survives the score and `max_per_source` (2), which stops one prolific outlet filling a vertical.

`run.safety_ceiling_per_run` (200) exists and is not a cap. It is a crash guard: if a feed change or a canonicalisation bug ever produces thousands of candidates, the run stops rather than spending six hours discovering it. A normal day is nowhere near it. If a run ever hits it, the answer is to find the bug, not to raise the number.

## Design rationale

The daily cap was removed because it was answering a question nobody had asked. It decided in advance that twenty articles was the right number of good articles for a day, which is not a thing that can be known in advance - some days have thirty worth reading and some have six. The score already orders them; a cap only truncates the order at an arbitrary point. Supply and the score are the honest answer, and the ceiling catches the failure mode a cap was accidentally also catching.

**Reader dissented, and the dissent stays on the record.** Their case: 146 feeds produce roughly 60 fresh items a day, AI holds about a third of them, and with no per-vertical ceiling AI eats the page. They named this the one change in the set that cannot be patched later, and they brought evidence rather than a worry - the 2026-08-21 page published four items, all AI, and the words Energy, India, World and Business do not appear on it. The counter is that `max_per_source` and each vertical's own `min_feeds` floor already spread a day, and that if the prediction holds the correction is a number in `config/taxonomy.json` rather than a code change. The test is falsifiable and worth running: **if most days come out one-vertical, Reader was right, and the fix belongs in the source list rather than in a cap.**

The age rule went the same way for the same reason. A 24-hour cutoff and a decay curve agree on every ordinary day, and disagree exactly on the days that matter: the quiet ones, where the cutoff empties a vertical and the curve publishes the best thing available. Losing a good item to a rule that was meant to protect quality is the worst outcome available.

Both first-sighting and the published ledger are append-only files under `state/`, committed by CI. That is not a preference - it is the only shape available. There is no database (Holy Law #1), and anything a later run must read has to survive as a committed file.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| A 24-hour freshness window | Empties a vertical on a quiet day and costs the digest its best item. The decay already ranks fresh news first without ever losing anything. |
| A daily item cap | Decides how many good articles a day is allowed to have before knowing what the day contains. |
| Treating an undated article as brand new every run | It would win the top slot every six hours forever. First sighting is the fix, and it costs one append-only row. |
| A `published` boolean on the seen row | Turns an append into a read-modify-write over the whole history, and two runs racing on it lose rows. |
| Rejecting any future date outright | Clock skew between a publisher and the runner is normal and small. A zero tolerance would drop real articles for being three minutes early. |
| Keeping rank position as the item id | Run 2 of a day renumbers every story, and anything that moved one place publishes twice. |
| Writing the published ledger at plan time | A run that dies mid-way would leave behind a claim it published something it did not, and the article would never be publishable again. |

## See also

- [discovery.md](discovery.md) - what the sources are, how they are tiered, and how the score is built.
- [health.md](health.md) - the record of what every feed did, and the quarantine that reads it.
- [../contracts/determinism.md](../contracts/determinism.md) - the fingerprint that makes "this re-run changed nothing" checkable.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages, and which of them see the whole day.
- [../../concepts/config.md](../../concepts/config.md) - where these knobs live and the knob-versus-fact rule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract.
