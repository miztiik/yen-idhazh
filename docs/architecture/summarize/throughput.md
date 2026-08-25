# Model throughput and why it drifts inside a run

**Last Updated**: 2026-08-25

What the two model rates mean, why the slow half of a run is slow, and what a
change in either number is allowed to prove.

The rates are recorded per item on the item-health ledger and drawn on the
console. The columns and how a rate is derived from them are owned by
[`../sources/item-health.md`](../sources/item-health.md); this page owns the
behaviour.

## Two rates, not one

The runtime charges a summary in two parts, and they run at different speeds:

| Name | What it is | Measured 2026-08-24 |
| --- | --- | --- |
| **read** (prefill) | The model taking the article in. Batched, so the machine works on many tokens at once. | 10.95 tok/s, 91.3 ms per token |
| **write** (decode) | The model producing the summary. One token at a time, each conditioned on all the ones before it. | 5.05 tok/s, 198 ms per token |

Read is about 2.2x write. That ratio is a property of how the two phases work,
not of this model, and it is why `summarize_ms` was split: one blended number
cannot say whether a slow day was long articles or long summaries.

Measurements, with hardware and date, are in
[`../../reference/measurements.md`](../../reference/measurements.md).

## Nothing carries over between articles

A common wrong reading of the logs is that the run "warms up" or "clogs up" -
that each summary leaves something behind that slows the next one. It does not.

Each item is one request. The runtime holds one prompt at a time in a slot, and
the next request overwrites it. The only thing that survives between two
requests is the **shared prefix of the system prompt**, and that is a saving,
not a cost: the runtime skips re-reading the tokens the two prompts have in
common, which is why the read rate is computed over `input_tokens -
cached_tokens` rather than the whole prompt.

So an article is never charged for the article before it.

## The write rate still falls through a run, and the cause is the ordering

Measured on run `32742672105`, all four workers, first half of each job against
its second half:

| Job | Context tokens, median | Summary tokens, median | Write tok/s, median |
| --- | --- | --- | --- |
| `work (0)` | 1712 -> 2382 | 242 -> 298 | 5.53 -> 5.13 |
| `work (1)` | 1651 -> 2552 | 244 -> 316 | 5.35 -> 4.70 |
| `work (2)` | 1612 -> 2527 | 233 -> 296 | 5.38 -> 4.81 |
| `work (3)` | 1688 -> 2694 | 245 -> 315 | 5.41 -> 4.78 |

The read rate stays flat across the same split. Only writing slows.

The cause is our own ordering. `stage_work` sorts a worker's items by prompt
band before the model loop, so **every worker summarises its shortest articles
first and its longest last**. By the second half of a job each request is
carrying a bigger prompt and is asked for a longer summary, and both make
writing slower per token:

- **A bigger prompt.** Every generated token attends over everything already in
  the context. A 2700-token context costs more per generated token than an
  1100-token one, within that one request.
- **A longer summary.** The cost per token climbs as the reply grows, for the
  same reason, so a 300-token summary has a lower average rate than a 170-token
  one even at identical prompt length.

Both are per-request effects. Run the same articles in the opposite order and
the drift reverses.

## What this means when reading the chart

- **A wide candle is normal.** The spread inside a day is the article mix,
  because the day contains both release notes and long reads.
- **Compare like with like.** A day's median moves with what the news was that
  day. The whole-day figure under the chart - total tokens over total
  milliseconds - is the one weighted by work actually done.
- **A model swap should move the whole candle,** both ends together. A change in
  one end only is more likely a change in the article mix.
- **Check the reuse line before blaming the model.** The read rate is computed
  over the tokens the machine actually read. If prompt reuse jumps, the read
  rate moves without the model changing at all.

**The chart has one day on it.** Counted 2026-08-25: the token columns landed on
2026-08-24, so `2026-08-25` is the only date with any `prefill_ms`, 145 rows of
it. Every reading rule above is therefore a rule about a chart nobody has yet
read across days. The multi-day trend, the gap-breaking in the reuse line and
the like-with-like comparison are all unexercised against real data. Re-check
the console after a few more days before trusting any of them.

**A model-swap mark is not built, and today it would draw nothing.** The rule
above tells a reader to attribute a whole-candle move to a swap, but the chart
does not say where a swap happened - so the reader has to know. `loadManifests()`
already returns each day's model ids, so the join is small. What is missing is a
way to prove it: all five published days ran `qwen3-8b-q4-k-m` and nothing else,
so the mark cannot fire, the browser suite cannot see it, and the frontend has no
unit-test runner to test the swap-detection in isolation. Build it with the first
swap, or with a pure module and a runner to test it - not before, or it ships
unverified.

## Design rationale

**Why the band sort stays, even though it makes the run look like it degrades.**
Grouping same-band prompts together is what lets consecutive requests share a
prefix, because the band's numbers are substituted into the system prompt. The
alternative - the original discovery order - breaks the shared prefix at almost
every item. The ordering is a cache decision that has a reporting side effect,
and the fix is to explain the side effect rather than to give up the cache.
The files are addressed by item id, not by processing order, so the ordering
changes cache locality and never the output
([`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md)).

**Why the console draws a spread rather than a line.** A day drawn as one point
answers "is it faster" and hides "did the two ends move apart". Since the
ordering guarantees a wide spread, a single point invites the reader to treat
normal variation as a regression. The candle makes the spread the subject.

**Why a day, and not a run.** The ledger carries `run_id`, so a per-run candle
is available, and each candle's tooltip lists its runs' medians. It is not the
default because four runs a day over a 30-day window is 120 candles in about
300 pixels, which is a smear rather than a chart. The day is the unit that fits
the window every other console chart already uses.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Plot milliseconds per token on a second axis | It is `1000 / tokens per second`. The same fact, mirrored, for twice the ink. |
| Encode milliseconds as marker size | Same reciprocal, less legible than a position. |
| Sort items by discovery order to flatten the drift | Trades a real prefix-cache saving for a prettier chart. |
| Report one blended `summarize_ms` rate | Cannot separate a long-article day from a long-summary day, which is the question the chart exists for. |
| Average the per-item rates for the day figure | A rate is a ratio. Averaging weighs a 60-word release note the same as a 2000-word feature. |

## See also

- [`../sources/item-health.md`](../sources/item-health.md) - the columns, and how a rate is derived.
- [`prompt.md`](prompt.md) - the bands, and why the ask changes with article length.
- [`../../reference/measurements.md`](../../reference/measurements.md) - every number here, with hardware and date.
- [`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md) - why a worker may reorder inside its shard.
