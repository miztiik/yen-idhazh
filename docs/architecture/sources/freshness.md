# Freshness and Identity

**Last Updated**: 2026-09-06

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

## Age is a gate first and a weight second

An article older than `max_age_hours` (24.0) is not added. It is not ranked, not summarized, and never reaches a reader.

Inside that window age still moves the score:

```
recency_bonus = recency_weight * 0.5 ** (age_hours / recency_half_life_hours)
```

With the shipped values (`recency_weight` 0.6, `recency_half_life_hours` 18.0) a brand-new article carries +0.6, an 18-hour-old one +0.3, and one at the edge of the window +0.23. The gate decides what may be published; the bonus decides the order of what is left.

**This reverses the rule that stood until 2026-08-30**, and the entry under "Design rationale" says what the measurement was.

The gate reads the date the run believes, not the date the feed printed - so a future stamp cannot buy an item its way past the gate, and an undated article is judged on when we first saw it.

## An undated article still has an age

Plenty of feeds carry no publish date, and the ones that omit it omit it consistently. For those the only honest age is the first time we saw the address, so the planning step writes one down.

`state/seen/<YYYY-MM>.csv` is append-only: the URL key, the timestamp, and the run that saw it first. It carries no address, because `ledger.load_seen` opens the key and the timestamp and nothing else - the address was 49.1 percent of the file for no reader, and it came off on 2026-08-31 for the reason `PublishedRow` shed its own on 2026-08-26. An address seen for the first time is treated as new, which is the truth as far as we can check it. Every run after that reads its real first-sighting.

**An undated article is therefore never refused for age on the day we find it, and is always refused a day later.** Dropping it on sight would silently retire every feed that omits a date, which is a different decision from refusing a back catalogue, and it is not the one taken here.

The shard is monthly and the lookback is `seen_window_days` (90). An address older than the window is not worth a lookup - it is past the gate several times over. A shard below that window is therefore deleted rather than kept: `retention.prune_seen` takes its floor from `ledger.shards_in_window`, the same function the read uses, so the two cannot drift. It deletes what is *older* than the oldest month that helper names and never merely what is outside the window - the window is drawn around whatever date the prune is handed, and a run given a date in the past would otherwise delete the live shard. Measured over 366 anchor dates at a 90-day window, what survives reaches back 90 to 120 days: a whole shard is kept if any of its days is in the window.

## A date in the future is ignored

A feed that stamps tomorrow on today's article takes the top slot every single run, forever. `max_future_hours` (6.0) is the tolerance: a publish date more than six hours ahead of now is discarded, and the item falls back to first-sighting like any undated one.

Six hours, not zero. Clock skew between a publisher and the runner is real and small; an embargo stamp is real and large. Six hours separates them without needing to know which is which.

### A date the payload cannot spell

`0001-01-01` is what several content systems send for a date nobody set, and `feedparser` reads it as an ordinary year 1. The year is padded where the stamp is written, rather than left to `strftime`, which pads a year below 1000 on Windows and leaves it short on Linux. On 2026-08-29 one such entry left discovery as `1-01-01T00:00:00Z`; ranking reads only a four-digit year, so one entry of 6,220 stopped the whole day before a single article was read (run 33259315735).

The placeholder then reads as two thousand years old, so the age gate refuses it and the vertical counts it in `too_old`. That is the answer a back catalogue gets, and the plan says which gate refused it. It is not the answer an undated article gets, which is first sighting. Treating an implausible year as no date at all is the better answer, and it needs a floor - see the rejected alternatives.

### The item says which of the two clocks answered

`rank.appeared_at` returns the time **and** the clock that produced it, and both travel to the reader. Three answers: `feed`, `first_seen`, and `unknown` where neither had a time. The label leaves the function with the value rather than being derived again downstream, because once the two are in one field nothing can tell them apart - a stamp we wrote and a stamp a publisher wrote are the same kind of string.

This is the fix for a real hazard, not tidiness. Both fallbacks above - an undated article and a date too far ahead - replace the publisher's time with ours **silently**. A page that prints the time without the label is repeating our own clock as though it were the source's, which is the same class of mistake as forwarding a feed's future stamp. What the published field means and what an absent one means is [../publishing/layout.md](../publishing/layout.md#an-item-says-why-it-is-here-and-whose-clock-its-time-is).

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
[../../reference/measurements.md](../../reference/measurements.md): 2,213 rows
at 110.7 B, so 40.4 MB a year at the structural ceiling of 1,000 rows a day.
`load_published` peaks at 498.1 B a row while it reads, which is 182 MB at that
ceiling - 1.1 percent of the runner's 16 GB, in the one job that loads no model.

**`canonical_url` was 48.6 percent of the row, and it is gone.**
`load_published` reads `url_key` and `published_on` by name, and nothing else
opens the file, so the column was paying for a lookup no run ever made. It left
on 2026-08-26: the contract narrowed, and
`backend/utilities/migrate_published_ledger.py` rewrote the committed ledger in
the same commit. The file went from 476,809 B to 244,910 B - 231,899 B and
104.8 B off every row - on a ledger that has no time bound and therefore never
stops growing. That is 21.2 MB a year at the rate the ledger itself records and
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

The join holds for the whole ledger rather than in principle: all 2,213
committed rows resolve to a `source_url`, with no absent day and no absent item
(measured 2026-08-26). It keeps holding because retention may never touch a
day's JSON payload ([../publishing/layout.md](../publishing/layout.md)) - it
deletes old visuals and nothing else. The direction that got harder is address
to row: that now needs the sha256 of the canonicalised URL computed first, which
is a tool run rather than a grep
([../../how-to/troubleshoot-one-url.md](../../how-to/troubleshoot-one-url.md)
shows how much canonicalisation sits between a pasted URL and its key).

## A failure that cannot change today is remembered too

The published ledger stops a repeat of a **success**. It cannot stop a repeat of
a **failure**, because a failure is never published - so every later run of the
same day planned the same paywall again and got the same paywall.

Measured over 2026-08-24 to 2026-08-29: **233 addresses were attempted more than
once inside one day, 231 of them never succeeded on any attempt, and 403 repeat
attempts bought 2 items.** On a five-run day, runs 2 to 5 each spent 8 to 41 of
their 160 slots re-reading a locked door.

So the planning step now reads today's rows of `state/item-health/<YYYY-MM>.csv`
and drops any address that failed today with a code in
`collect.settled_failure_codes`. The `work` job commits that ledger the moment an
item settles, so the next run of the day sees it.

**The list is the codes that will not change before tomorrow**, and that is the
whole rule: a robots refusal, a 404, a paywall, a page with no prose. Absent from
the list, and therefore retried, are `http_rate_limited`, `network_error`,
`http_server_error`, `model_unreachable` and `context_exceeded` - a rate limit
answers differently at 18:20 than it did at 02:20, and a run that treated it as
final would throw away an article for being briefly unlucky.

The window is the day, not the address's lifetime. A metered paywall resets, a
site is redesigned, a 404 becomes a 200. Tomorrow asks again.

The two sets are kept apart in `rank.plan_vertical` rather than merged into one
drop list. They are different facts - one says we already gave this to a reader,
the other says we tried today and could not - and an operator reading
`considered` has to be able to tell which one cost a slot.

## An item's name comes from its address

`item_id` is `<vertical>-<ten digits>`, derived from the URL key and nothing else.

It used to be the rank position. That broke the moment a day had more than one run: run 2 re-ranked the same stories, every id shifted, and an article that moved one place arrived as a new item and published twice. Deriving the id from the address means a later run recognises the work the earlier one already did.

A collision - two addresses landing on the same ten digits - is rare and is a contract failure that stops the run, so the second one steps forward until it finds a free number. Resolved in address order, so the answer depends on the pool and never on the ranking.

## What sizes a run

There is no daily item cap and no per-vertical cap. What a day publishes is what survives the score, `max_per_source` (2), which stops one prolific outlet filling a vertical in one run, and `max_source_share_per_day` (0.05), which stops one filling the day.

**`run.safety_ceiling_per_run` (160) is what sizes a run, and saying otherwise
was wrong.** This page used to call it a crash guard that a normal day was
nowhere near, and quoted 149 as the largest day ever planned. Both statements
were false by 2026-08-25 and stayed here: `items_planned` has been **exactly the
ceiling on every run since**, first at 200 and now at 160
([../../reference/measurements.md](../../reference/measurements.md)). Supply
overtook the guard, and a guard sitting inside the working range is a cap.

It is now a cap on purpose. Owner decision, 2026-08-29: the number stays at 160
rather than rising, and the gain comes from spending those 160 slots on articles
that can actually be read - the source sweep in
[discovery.md](discovery.md) and the same-day failure memory above. Raising it
is a separate question with a separate risk, because `run.shard_timeout_minutes`
kills a worker that overruns and **a killed worker uploads nothing**, so the run
loses every item it held. Nobody has measured a run at the new yield yet, so
nobody may set that number yet (Rule #10).

What still bounds the number from above is the worst case the `work` and `visuals`
jobs both have to finish ([../../concepts/config.md](../../concepts/config.md)).
What it is *for* has changed, and this paragraph is the record of that change
rather than a quiet re-derivation.

## How much of a day one publication may be

`max_per_source` counts a desk in a run. A feed is configured against exactly
one vertical, so a feed's ceiling for a whole day is that count times the runs
the day had - two per run, five runs, ten items - and until 2026-08-31 nothing
counted it and nothing turned it into a share.

**A fixed count is a moving share, and that is the whole reason for the second
knob.** Measured 2026-08-31 over the eleven committed days:

| Day | Items | Heaviest feed | Its share |
| --- | --- | --- | --- |
| 2026-08-30 | 431 | 10 (21 feeds tied) | 2.32 percent |
| 2026-08-29 | 366 | 8 (7 feeds tied) | 2.19 percent |
| 2026-08-24 | 731 | 10 | 1.37 percent |
| 2026-08-22 | 10 | 2 | 20.0 percent |
| 2026-08-21 | 4 | 1 | 25.0 percent |

The count is the same rule on every row: it is the days that move. Ten items is
a rounding error on a 431-item day and a quarter of a four-item one, so the
number that needs bounding is the share.

`collect.max_source_share_per_day` is that bound. The plan job turns it into a
count once per run - the items today's earlier runs published, plus the items
this run's own first pass planned, times the share - and then re-plans against
it. It never goes below `max_per_source`: a day ceiling under that would tighten
what one desk may take in one run, which is a decision about a desk rather than
about a day, and it was refused because it starves a desk where one publication
is genuinely the best source while still not bounding the day.

**A capped story is displaced, never deleted.** The slot goes to the best
candidate `max_per_source` was already holding down on the same desk. Where the
desk has nothing held down, the story comes back and the feed keeps its place -
a shorter day is the one thing this may not buy, because a reader can see a
summary that is wrong and cannot see a story that never ran.

**The shipped value of 0.05 displaces nothing that has ever been published**,
and that is deliberate. It is above the largest full-day share ever measured by
a factor of 2.2, so it is a bound on the thin day rather than a change to the
busy one. Any value tight enough to bind on 2026-08-30 would have displaced 126
of its 431 items, and the runs of that day planned 106, 99, 93, 88 and 79 items
against a 160 ceiling - so there was no reserve to repay them with. Setting the
number lower is the owner's call and needs a run measured at it first
(Rule #10).

## A feed that publishes badly stops scoring as though it did not

`authority` was the source's tier scaled by that feed's hand-set `weight`, and nothing else. So a feed that failed its reads, or returned 200 and parsed to nothing, kept the full authority of its tier - it scored as though it had published. A second factor now scales it: the feed's **reliability**, derived from its own recent record rather than set by hand.

Reliability is `productive / evidence-bearing` over a trailing window, clamped to `[reliability_floor, 1.0]`:

- **Evidence-bearing** is every read that did not preserve the streak - so a rest and a robots answer are set aside, because neither asked the feed whether it works. A fetch, a silent reshape to zero items, and an address we could not reach all count.
- **Productive** is the read that came back carrying entries (`FeedHealthRow.answered`).

It is applied inside `authority`, the same place and the same way `weight` is: `tier_weight * weight * reliability`. Multiplying rather than adding keeps a badly-publishing feed below a dependable one of the same tier, which is the point. Because it multiplies the authority term, it scales before reach and before the watchlist, front-page, theme and recency bonuses - a feed's record dims the story it carried, it does not touch a bonus the story earned elsewhere.

Two knobs, both under `collect`, both bounded so the factor can only ever reduce a score and never remove a feed:

- `reliability_window_days` (30) is the trailing window. A feed publishes a few times a day at most, so thirty days is dozens of reads - enough that one bad afternoon cannot set the factor. The read is bounded by this window and never the whole ledger (Rule #12).
- `reliability_floor` (0.5) is the lowest the factor may reach. A feed with a record of nothing but dead reads scores 0.0 raw and is clamped up to 0.5, so the worst its record can do is **halve its authority - a two-to-one cut, never more**. That is why this factor alone can never empty a desk: a `min_feeds` floor counts configured feeds, and a multiplier scales a score without removing a feed from the count.

A feed with no evidence-bearing read in the window - brand new, or only ever rested and politely refused - scores 1.0. **Unknown is not the same as bad**, so an untested feed is never punished; it simply carries its tier until it has a record. The map of factors is built once per run by `ledger.reliability` off the committed feed-health shards and read inside `authority`; a feed absent from the map reads 1.0.

## The same story at two addresses is planned once

The exact-address collapse joins two feeds carrying the identical URL. It does nothing for one story told by two outlets, which is two addresses and two `url_key`s - the CBC and the Guardian on one announcement are one story to a reader and two rows to the plan.

A semantic pass at the plan stage records these. After the day's desks are planned and the exact-address duplicates are collapsed, every planned story is embedded on the runner's own ONNX encoder - its headline and up to 200 characters of the feed's lead. Walking the day in descending rank, a story whose vector sits within `collect.dedup_similarity_min` (0.94) of a higher-ranked story **from a different source** is recorded as a duplicate of it. The walk is honest about a cut it has not made: a story already recorded as a would-cut is not itself offered as a match for a later one, so the count is what enforcing would remove rather than an over-count.

Two rules bound what it touches. **A feed's own near-identical repeats are not its business** - a same-source pair is left to `max_per_source`, which already bounds one feed inside one desk. **A desk's only story is never a duplicate**, whatever it resembles: a single-carrier story scores lowest by construction, so a pass that cut the weakest would cut the exclusive story first.

It ships **record-only**. `collect.dedup_enforce` is false, so the pass writes each would-collapse pair to the run log against the story it matched and removes nothing - a day's duplicate rate is measured before any cut is turned on. Turning the flag on cuts the lower-ranked telling of each pair, before the safety ceiling and with nothing else changed, so enforcing is a config edit rather than a code change. A record pass never stops a run: an encoder that will not load costs the run its duplicate record, never its plan.

## Design rationale

The fifth slot was added at 02:20 rather than 22:20. Both are one more attempt
and both cost the same runner time. A 22:20 slot would add to a UTC day that is
about to end, so its work is visible for under two hours before the date rolls.
02:20 puts the same work at the front of the day a reader is about to open, and
the articles it would have caught at 22:20 are still in the pool four hours
later, well inside `max_age_hours`.

The daily cap was removed because it was answering a question nobody had asked. It decided in advance that twenty articles was the right number of good articles for a day, which is not a thing that can be known in advance - some days have thirty worth reading and some have six. The score already orders them; a cap only truncates the order at an arbitrary point. Supply and the score are the honest answer, and the ceiling catches the failure mode a cap was accidentally also catching.

**Reader dissented, and the dissent stays on the record.** Their case: 146 feeds produce roughly 60 fresh items a day, AI holds about a third of them, and with no per-vertical ceiling AI eats the page. They named this the one change in the set that cannot be patched later, and they brought evidence rather than a worry - the 2026-08-21 page published four items, all AI, and the words Energy, India, World and Business do not appear on it. The counter is that `max_per_source` and each vertical's own `min_feeds` floor already spread a day, and that if the prediction holds the correction is a number in `config/taxonomy.json` rather than a code change. The test is falsifiable and worth running: **if most days come out one-vertical, Reader was right, and the fix belongs in the source list rather than in a cap.**

The supply premise in that dissent is superseded. It was written when a day was
four items. On 2026-08-24 the day published 731 and every run planned 200, so
"roughly 60 fresh items a day" is now low by an order of magnitude. Read the
dissent for its argument about vertical mix, not for its volume figure.

The age rule went the same way for the same reason. A 24-hour cutoff and a decay curve agree on every ordinary day, and disagree exactly on the days that matter: the quiet ones, where the cutoff empties a vertical and the curve publishes the best thing available. Losing a good item to a rule that was meant to protect quality is the worst outcome available.

### A feed's reliability multiplies its authority, and only ever reduces it

The factor is applied multiplicatively, `tier_weight * weight * reliability`, and an additive penalty was rejected. A subtracted penalty has no natural scale against the tier weights - institution is 1.0 and community is 0.3, so one penalty value either barely touches an institution or wipes out a community feed, and the two cannot be reconciled with a single number. Multiplying scales with the tier exactly the way the hand-set `weight` already does, keeps the tier ordering intact, and lands the factor in a bounded, readable range where 0.5 means "half" whatever the tier.

The clamp to `[reliability_floor, 1.0]` is what makes the change safe to ship without a second guard. Because the factor can never exceed 1.0 it can only ever reduce a score, and because it can never reach 0 it can never zero a feed out; and because it scales a score rather than removing a feed, it cannot change `eligible_feeds`, which is what a vertical's `min_feeds` floor counts. So the factor alone can neither move a score by more than the floor allows nor take a desk under its floor - the two failure modes the plan named. A floor of 0.5 caps the worst cut at two-to-one.

Measured over the committed 30-day window ending 2026-09-06 (Intel Core i7-1265U / Windows 11): 184 feeds carried evidence-bearing reads. 157 scored a full 1.0 - dependable across the window - and 27, about one in seven, were dimmed below it, 15 of them sitting at the 0.5 floor because their record was worse than one good read in two. The median feed was untouched at 1.0, and no factor fell below the floor, so neither failure mode was anywhere near firing. The factor is a real signal - it moves 27 feeds - and a bounded one.

### The plan-stage duplicate pass ships record-only, and does not yet read the published past

The pass records what it would collapse before it cuts anything, because a cut nobody has read the record of is a cut nobody can defend. The first scheduled run writes the day's would-collapse count to the log; the number the pass would remove on a live day is knowable from that log, not asserted here (Rule #10). The within-day count is bounded by the day's plan and never by the archive - the safety ceiling caps the stories walked, and the vectors are the day's own (Rule #12).

**It compares a day against itself, and not against the days already published - deliberately, and for now.** The design called for a second comparison: embed the stories published in a trailing window, decayed by recency, and drop today's story if it repeats one, so a re-run of the same day cannot publish the same story twice. That step is deferred, because the store it would read cannot answer it. `state/published.csv` carries `item_id`, `published_on` and `url_key` and no title, and `ledger.load_published` is never windowed - published is forever. Embedding a trailing window of published stories needs a bounded, title-carrying published surface that does not exist, and creating one is a new retention surface this plan refused. The within-day collapse is the honest part today's committed state supports; the cross-day part waits for a surface that carries the text and bounds the read (Rule #12).

**Two knobs shipped, not four.** The deferred cross-day step needs a window length and a recency half-life; both are added when that step lands, not before, because a config knob no code reads is a knob nobody can trust. The threshold reuses `assemble.duplicate_similarity_min` rather than minting a second number for the same question one stage earlier: both ask whether two of a day's stories are one, both score cosine over MiniLM vectors, and 0.94 was set by hand labels for exactly that question (measured 2026-09-01, i7-1265U, 3,978 items). The text each embeds differs - a feed's lead here, our own summary at assemble - so the reused number is the labelled answer to the same question, not a claim the inputs are identical.

### Age became a hard gate on 2026-08-30, and the argument above is the thing it overturned

That paragraph has one load-bearing premise: quiet days, where a cutoff empties a
vertical and nothing is waiting to take the slot. **There are no quiet days.**
Every run since 2026-08-25 has planned exactly `safety_ceiling_per_run` items,
so supply has exceeded the slots on every single run and the ranking has been
choosing which good candidate to leave out, not whether to publish at all. A
dropped old item was never a lost slot; it was a slot a fresher item took.

What that cost, measured 2026-08-30 over the 2,900 items published between
2026-08-22 and 2026-08-29, each aged at the moment its own run planned it:

| | |
| --- | --- |
| median age | 5.5 hours |
| 90th percentile | 856.1 hours (35.7 days) |
| 99th percentile | 6,246.2 hours (260.3 days) |
| oldest published | **155,383.6 hours (6,474.3 days, 17.7 years)** |
| over one day old | 826 items, 28.5 percent |

The oldest item the digest has ever published is a stock note dated 2008-12-05.

The mechanism is the score, not a bug. `authority` is the best tier that carried
the story, and an institution feed is 1.0 at any age. A three-day-old
trade-press story scores 0.6 plus a decayed bonus of 0.04. So an item from a
research lab's archive outranked three-day-old news, and the feeds that serve a
whole back catalogue - mistral-news, google-research-blog, deepmind-blog,
huggingface-blog, nist-news - filled the slots.

The gate is not free and the cost is not spread evenly. At 24 hours over the
same window:

| desk | survives | loses |
| --- | --- | --- |
| `world` | 95.7 percent | 28 |
| `india` | 95.1 percent | 33 |
| `business-economy` | 76.1 percent | 76 |
| `energy` | 65.1 percent | 166 |
| `ai` | **32.4 percent** | **523** |

`ai` loses two thirds of its supply because two thirds of what it was
publishing was a back catalogue. That is the finding, not a side effect: the
gate did not thin the AI desk, it revealed how thin the AI desk's *news* supply
already was. Ten of 104 sources publish nothing at all under the gate.

Authority: owner, 2026-08-30, over the alternatives of 48 hours (drops 745
rather than 826 - it keeps a second bite at a story every top feed already
carried) and of leaving the rule alone. The owner's argument was the one the
old paragraph has no answer to: **if a story matters, a top feed carries it
today**, so an old item in the pool is a signal about the feed list rather than
about the story. `too_old` on each vertical's plan summary is what makes that
checkable - a desk that thins can say whether a gate or a dead feed did it.
The threshold is `collect.max_age_hours` and moving it is a config edit.

Both first-sighting and the published ledger are append-only files under `state/`, committed by CI. That is not a preference - it is the only shape available. There is no database (Rule #1), and anything a later run must read has to survive as a committed file.

### A per-run reading budget was proposed on 2026-08-25 and refused

Authority: Carmack and Fowler. The proposal was a new knob at the planning step,
capping how many items one run may plan for reading, separate from the crash
guard. The value floated was about 59 items - the 40-minute visual planner clock
divided by the slowest measured per-item planning cost, `2400 / 40.3`. Four facts
refused it.

| Why it was refused | The evidence |
| --- | --- |
| The bound it adds already exists one stage later, and it is a clock rather than a count | `cli.stage_visual_planner` stops its loop at `run.visual_planner_budget_minutes` (40 minutes), inside the `visuals` job's 50-minute timeout. A count has to be set for the worst host, so the number that fits a slow host leaves a fast one idle. The planner-side version of the same proposal was refused for the same reason - see [../publishing/visuals.md](../publishing/visuals.md). |
| The loss it answered is already prevented | The `visuals` artifact upload in `.github/workflows/digest.yml` carries `if: always()`. A visuals stage that runs out of clock still hands over every decision it made. What cost four of the six runs on 2026-08-24/25 their visuals was a cancelled job skipping an upload step that had no condition on it. That step has one now. |
| The number behind it is contaminated | The 20.7 s and 40.3 s per-item planning figures were measured over 703 items that all ran with `diagram` in `visuals.enabled_kinds`, so the model was asked about every one of them: `asked=False` appears zero times in all 703. `diagram` is off now, and with it off a measured 68 of 145 items (46.9 percent) never reach the model at all. |
| It throttles the wrong stage, and a reader pays for it | A plan-stage budget bounds what `summarize` is handed, in order to protect `visuals`. `summarize` runs as four worker jobs by default, eight at the ceiling, and has no stage clock at all - its only bound is the `work` job's timeout, which is `run.shard_timeout_minutes` and is 150 minutes. `visuals` is one job with a 40-minute stage clock. On 2026-08-24 the committed digest carries **731 items**; a 59-item budget over five runs caps that day at 295 and deletes about 436 of them. |

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
| Treating a placeholder date as no date at all | The better answer, and it needs a number nobody has measured: "implausible year" is a floor, and a floor guessed here would silently drop or admit real articles. The crash is fixed without one, and the age gate already refuses the placeholder and says so in `too_old`. |
| Keeping rank position as the item id | Run 2 of a day renumbers every story, and anything that moved one place publishes twice. |
| Writing the published ledger at plan time | A run that dies mid-way would leave behind a claim it published something it did not, and the article would never be publishable again. |
| A per-run reading budget at the planning step | Refused 2026-08-25 by Carmack and Fowler. The bound already exists one stage later and is a clock; the artifact loss it answered already carries `if: always()`; its value came from a measurement taken before `diagram` was switched off; and it deletes about 436 items from a 731-item day. See the design rationale above. |
| A score floor set now rather than measured | A floor is the right control and the wrong thing to guess. It waits on the retrieval eval, which is the instrument that can say what a score is worth. |
| Sharding `state/published.csv` by month | The question has no time bound, so every shard is opened on every run. It adds file opens and removes nothing. |
| Windowing the dedupe read without sharding the file | Filtering rows after reading them saves no I/O. A window pays only when it can decide which files to skip. |
| Pruning the published ledger | It is the only record of what a digest carried. Pruning makes a re-publish look new, which is the exact failure the ledger exists to stop. |
| Keeping `canonical_url` on the published row for forensics | Dropped 2026-08-26. It was 48.6 percent of a row on a ledger with no time bound, no reader ever opened it, and all 2,213 committed rows recover their address by joining `item_id` and `published_on` against a day payload retention may not touch. |

## See also

- [discovery.md](discovery.md) - what the sources are, how they are tiered, and how the score is built.
- [../contracts/schemas.md](../contracts/schemas.md) - the row contracts under `state/`, and the rule that decides when a ledger shards.
- [../../reference/measurements.md](../../reference/measurements.md) - the ledger sizes, the read cost, and the ceiling measurement quoted above.
- [health.md](health.md) - the record of what every feed did, and the quarantine that reads it.
- [../contracts/determinism.md](../contracts/determinism.md) - the fingerprint that makes "this re-run changed nothing" checkable.
- [../publishing/visuals.md](../publishing/visuals.md) - the visual planner's clock, and the planner-side version of the budget refused above.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages, and which of them see the whole day.
- [../../concepts/config.md](../../concepts/config.md) - where these knobs live and the knob-versus-fact rule.
- [../../reference/github-actions.md](../../reference/github-actions.md) - workflow names and exact triggers.
- [../../../CLAUDE.md](../../../CLAUDE.md) - the engineering contract.
