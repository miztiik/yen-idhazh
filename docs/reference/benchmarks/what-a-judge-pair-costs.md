# What one judged pair costs

**Last Updated**: 2026-09-21

**The short answer: 94.53 seconds for an average pair, and 110.98 seconds for the
slowest one.** That is a whole pair - both readings of it, the second with the
two summaries swapped - and not one model call.

Measured on 2026-09-18 over the 82 pairs of run `2026-09-18-35339202390`, on four
stock `ubuntu-latest` runners, on `Qwen3.5-9B-Q4_K_M`. The rows are committed at
`state/content-similarity-judge/scored-pairs/2026/09/18.csv`, so every figure below can
be recomputed from the repository.

Before this run the judge's budget was sized from 77.6 seconds a call, which is a
number taken from summarising articles rather than from judging pairs
([pipeline-cost.md](../pipeline-cost.md)). Doubled for the two readings it said a
pair costs 155.2 seconds. The real average pair is 39 percent cheaper than that
and the worst one is 28 percent cheaper, so the old figure was not a safety
margin anybody chose - it was an unlabelled 1.64x guess.

## What was measured

One column, `decode_seconds`, on each judged pair row. It is wall clock inside
the model calls for that pair: the two readings added together, and nothing else
the shard did.

The run is an ordinary scheduled night, not a synthetic probe. Four shards judged
82 pairs between them off the published day of 2026-09-18, each shard on its own
runner with its own `llama-server`. 72 of the 82 pairs came back usable - the two
readings agreed - and an unusable pair costs the same two calls as a usable one,
so all 82 are in every figure here.

**A pair is a fair unit and a call is not.** The second reading re-sends the same
system turn and the same two summaries in the other order, so the server's prompt
cache serves part of it. Halving a pair figure to get a call figure would
therefore be wrong in a direction we know and by an amount we have not measured.

## Every figure, over all 82 pairs

| Reading | Seconds |
| --- | --- |
| Fastest pair | 72.80 |
| Median pair | 94.92 |
| **Average pair** | **94.53** |
| 90th percentile | 104.39 |
| 95th percentile | 107.95 |
| **Slowest pair** | **110.98** |
| Population standard deviation | 7.84 |

The slowest pair is 17.4 percent above the average. That is the spread one night
of real articles produces on one set of weights, and it is the reason a budget
sized on the average is a budget that fails on a hard night.

## The four shards did not agree

Each shard drew its own runner, and the machine a runner gives you is a lottery
([what processor a run draws](the-processor-lottery.md)).

| Shard | Pairs | Fastest | Average | Slowest |
| --- | --- | --- | --- | --- |
| 0 | 21 | 85.38 | 94.24 | 107.60 |
| 1 | 21 | 80.29 | 95.69 | 109.45 |
| 2 | 20 | 72.80 | **88.24** | 104.48 |
| 3 | 20 | 88.61 | **99.89** | 110.98 |

**The luckiest shard averaged 88.24 seconds a pair and the unluckiest 99.89 - 13.2
percent apart, on the same night, on the same weights, minutes apart.** Nothing we
control reaches that choice. A per-pair figure taken from one shard would be off
by up to that much before any article is read.

## What this settles

**A shard's own budget.** At the committed cap of 200 pairs over four shards, one
shard draws 50 pairs. That is 78.8 minutes of model time at the average pair and
92.5 minutes at the slowest one, against the 175 minutes a unit has to work in -
the 200-minute bound less the 13 the venue spends before the judging process
starts and the 12 it keeps back for the records and the upload. So the committed
budget uses 45 percent of its window at the average pair and 53 percent at the
slowest, and the clock is not what limits how many pairs a night may judge.

**Why the judging night is a workflow of its own.** All 200 pairs in one job is
5 hours 15 minutes at the average pair and 6 hours 10 minutes at the slowest,
against the 6-hour ceiling GitHub kills a job at. One job is a coin toss against
that ceiling before the digest pipeline's own work is counted at all.

## What this does not settle

**How a different model would read.** Every figure is `Qwen3.5-9B-Q4_K_M` on the
committed judging prompt. Change either and the number is gone, not scaled.

**What one call costs.** The prompt cache makes the two readings of a pair cost
different amounts, and this run did not time them apart.

**Whether a night at the cap behaves the same.** 82 pairs is what that night drew.
The cap is 200, no night has reached it, and nothing schedules one - so the
average over a full night is unmeasured. The spread above is what argues it would
not move far.

**What the judge costs when it is not the only thing running.** These four shards
had their runners to themselves.

## How to take this reading again

The column is written by every judging night, so a later run needs no new
instrument - only a different day file:

```powershell
python -c "import csv,statistics as s; v=[float(r['decode_seconds']) for r in csv.DictReader(open('state/content-similarity-judge/scored-pairs/2026/09/18.csv',newline='',encoding='utf-8'))]; print(len(v), min(v), s.fmean(v), max(v), s.pstdev(v))"
```

A re-run replaces this page rather than adding a second one.

## See also

- [what processor a run draws, and what it does to a reading](the-processor-lottery.md) - why two shards of one night disagree by 13.2 percent.
- [pipeline-cost.md](../pipeline-cost.md) - the 9.85 tokens a second reading the old derived figure came from.
- [autotune-content-similarity.md](../../architecture/publishing/autotune-content-similarity.md) - what the judge is for, and what the pair budget buys.
