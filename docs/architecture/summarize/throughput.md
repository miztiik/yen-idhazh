# Model throughput and why it drifts inside a run

**Last Updated**: 2026-08-27

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

**Read is 10.95 tokens the model actually read per second, not 10.95 tokens of
prompt per second.** The two differ by a factor of about 1.8, because roughly
half of every prompt is reused from the cache rather than read. The figure is
`input_tokens - cached_tokens` over `prefill_ms`, and the console draws the same
subtraction. Counting the cached half in would report 19.96 tok/s on a run whose
real rate was 11.09 - a rate the machine never ran at. Whenever this page or the
console prints a read rate, that is the one it means.

Read is about 2.2x write. That ratio is a property of how the two phases work,
not of this model, and it is why `summarize_ms` was split: one blended number
cannot say whether a slow day was long articles or long summaries.

Measurements, with hardware and date, are in
[`../../reference/measurements.md`](../../reference/measurements.md).

## The read rate is checked against the server, and it holds

Every timing above is a field the summarize stage copied out of one model reply.
The model server counts the same work for itself and publishes the totals on
`/metrics`, which is a second instrument that shares none of the first one's
failure modes. Until 2026-08-27 those counters reached only a job log that keeps
them for two days, so this page published a rate nothing committed could check -
and under Rule #10 a number that cannot be reconciled cannot justify a design.

Each `work` shard now commits its server's counters as one row of
`state/runtime-counters.csv`, and
`backend/utilities/reconcile_prefill.py` pools both sides of one run and prints
the gap. **Measured on run `2026-08-26-5`: the ledger says 11.1755 tok/s and the
server says 11.1796, which is 0.037 percent apart against a 5 percent bound
written down before either side was read.** Tokens read, tokens reused and
tokens written match to the token on both sides. The full figures are under
[The ledger and the server agree about the read rate](../../reference/measurements.md#the-ledger-and-the-server-agree-about-the-read-rate).

Two things follow for anyone reading a number off this page:

- **The ledger was never the suspect.** The premise this work started from was
  "we cannot tell", not "the ledger is wrong", and the reconciliation says the
  ledger is right.
- **A run figure is a sum over a sum.** Each shard has its own row, and the run
  rate is the total tokens over the total seconds. A mean of the four shard
  rates would weigh a shard that read 23,411 tokens the same as one that read
  30,538.

One run is an observation, not a property. Re-run the utility after a few more
days, and especially after a day where a shard died mid-item.

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

## Concurrency inside a shard is not a lever, but shard count is

**Measured 2026-08-25** on a GitHub-hosted `ubuntu-latest` (AMD EPYC 9V74,
4 vCPU, 15 GB), `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record) through
`llama-batched-bench` on llama.cpp `b10598`, three repeats. Running two sequences through the model at
once raises **aggregate** write from 5.77 to 6.07 tok/s. That is **1.055x**,
spread 0.022, against a gate of 1.4x set before the run. Four sequences reach
1.133x and oversubscribe the 4 vCPU, so no parallel level on this runner clears
the gate.

Read does not move at all: 11.98, 11.96 and 11.96 tok/s across the three levels.
`--ubatch-size 512` already hands a 512-column matrix to all 4 threads, so two
concurrent reads share the same 4 threads and there is nothing to win.

These are bench rates at a fixed 900-token prompt and a fixed 300-token reply on
one host. They are not the production rates in the table at the top of this page,
and the two are not comparable item for item. What the bench measures is the
ratio between its own levels, which is the only quantity it exists to give.

Write is 36.8 percent of model time - 232.7 minutes read against 135.7 minutes
write on run `32742672105`, 2026-08-24 - so 1.055x buys about 1.9 percent of a
run's wall-clock. **A second in-flight request inside one worker is therefore not
a throughput lever on this hardware, and that line of work is closed**
([Parallel decode on 4 vCPU](../../reference/measurements.md#parallel-decode-on-4-vcpu)).

The lever that remains is the number of shards. Each shard is its own runner
with its own 4 vCPU, so raising the shard count adds cores rather than dividing
them, and it widens the part of the stage that is already parallel. `digest.yml`
raised its ceiling from four shards to eight on 2026-08-25 for that reason. One
run has now used it: the slowest worker fell from 113.1 minutes to 58.8, which
is 1.92x, on a day whose total tokens were within 1 percent of the four-shard
baseline's. It is not a paired measurement and it did not publish - the caveats
and every other figure are under
[Eight work shards](../../reference/measurements.md#eight-work-shards).

## What this means when reading the chart

- **A wide candle is normal.** The spread inside a day is the article mix,
  because the day contains both release notes and long reads.
- **Compare like with like.** A day's median moves with what the news was that
  day. The whole-day figure under the chart - total tokens over total
  milliseconds - is the one weighted by work actually done.
- **A model swap should move the whole candle,** both ends together. A change in
  one end only is more likely a change in the article mix.
- **The axis starts at the slowest rate drawn, not at zero,** and both ends are
  printed. What a reader compares on this chart is a distance between two
  candles, so the axis carries only the range the run actually reached.
- **Check prompt reuse before blaming the model.** The read rate is computed
  over the tokens the machine actually read. If prompt reuse jumps, the read
  rate moves without the model changing at all. The figure is in the legend
  under `prompt reused`; it is a cache statistic and is not drawn.
- **Check the host before blaming anything.** The runner host moves the read
  rate further than any knob we set. Measured 2026-08-24 across eight `work`
  jobs, the read rate clustered at about 11, 14 and 37 tok/s - a 3.4x span with
  one model, one set of settings and one day's articles. Nothing records which
  host a job drew, so two days are comparable only if their host mix matched,
  and today nothing proves it did.

**The write rate moves the opposite way from the read rate when the host
changes.** In the same eight jobs the two fastest-reading jobs were the two
slowest-writing ones: they read at 36.4 and 37.2 tok/s and wrote at 3.36 and
3.30, while the jobs that read near 11 wrote at 4.93 to 5.46. A host that is
simply faster would move both ends together, so a day where the two ends move
apart is a host difference and not a model one. The figures, and what they do
and do not settle, are in
[`../../reference/measurements.md`](../../reference/measurements.md).

**The chart has one day on it.** Counted 2026-08-25: the token columns landed on
2026-08-24, so `2026-08-25` is the only date with any `prefill_ms`, 145 rows of
it. Every reading rule above is therefore a rule about a chart nobody has yet
read across days. The multi-day trend and the like-with-like comparison are both
unexercised against real data. Re-check the console after a few more days before
trusting either. A one-day window still draws its candle: min, p25, median, p75
and max is five numbers and a real shape. It drops the date cadence, which one
column cannot carry, and prints the date as one label instead.

**A model-swap mark is not built, and the thing that blocked it has now
happened.** The rule above tells a reader to attribute a whole-candle move to a
swap, but the chart does not say where a swap happened - so the reader has to
know. `loadManifests()` already returns each day's model ids, so the join is
small. What was missing was a way to prove it: every published day up to
2026-08-27 ran `qwen3-8b-q4-k-m` and nothing else, so the mark could not fire
and the browser suite could not see it. `qwen3-5-9b-q4-k-m` became the
configured summarizer on 2026-08-27, so the first day it publishes gives the
mark a real transition to draw and the suite a real fixture. Build it then, or
with a pure module and a runner to test it - not before, or it ships unverified.

**Nothing on this chart is evidence that the swap improved anything.** No
comparison against the retired model was ever run
([`../../concepts/evaluation.md`](../../concepts/evaluation.md)), and a candle
that moves the day a model changes is a change in rate, not a change in quality.
The two are different measurements and this chart takes only one of them.

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

**Why the axis is not anchored at zero (2026-08-25).** Zero belongs on an axis
when the length of the mark encodes the value, as it does on a bar. A candle
encodes by position, so what a reader reads off it is the distance between two
candles, and an anchor nothing ran near spends the plot on empty space. Measured
on the published console the same day: zero-anchored, the read whisker occupied
17.5% of the plot height and the interquartile box 3.7%. The domain is now the
drawn extent rounded outward by `.nice()`, and both ends are printed so the
reader can still place a number. Authority: Jony.

**Why the prompt-reuse line was deleted (2026-08-25).** It was drawn against a
second y axis, 0 to 100%, on a chart whose own axis is tokens per second. Two
scales on one plot invite a reader to correlate the two series, and these two do
not share a unit or a cause - reuse is a property of the prompt cache, not of
how fast the model runs. The number is a statistic and stays in the legend.
Authority: Jony.

**Why the chart draws in CSS pixels (2026-08-25).** It used to draw into a fixed
360-unit `viewBox` and stretch to the column. A `viewBox` is a scale factor, so
at a 1057px window the chart rendered 598px wide, which put `font-size="10"` on
screen at 16.6px and `stroke-width="1"` at 1.66px. It now draws through
[`frontend/src/lib/charts/frame.ts`](../../../frontend/src/lib/charts/frame.ts)
at the width it occupies, so one unit is one pixel. The server draws at
`console.chart_width` and the browser redraws once it has measured the element.

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Plot milliseconds per token on a second axis | It is `1000 / tokens per second`. The same fact, mirrored, for twice the ink. |
| Encode milliseconds as marker size | Same reciprocal, less legible than a position. |
| Sort items by discovery order to flatten the drift | Trades a real prefix-cache saving for a prettier chart. |
| Keep two requests in flight per worker to overlap read and write | Measured 2026-08-25: aggregate write rises 1.055x for a second sequence, spread 0.022, against a 1.4x gate. That is about 1.9 percent of a run. Four sequences reach 1.133x and oversubscribe the 4 vCPU. Cancelled, not deferred. |
| Report one blended `summarize_ms` rate | Cannot separate a long-article day from a long-summary day, which is the question the chart exists for. |
| Average the per-item rates for the day figure | A rate is a ratio. Averaging weighs a 60-word release note the same as a 2000-word feature. |
| Raise `retention-days` on `runtime-log-*` and reconcile the read rate by hand | Two days becomes thirty and the answer still expires. Rule #10 wants the evidence to survive with the claim, and a committed row is the only thing that does. |
| Trust the ledger and delete the metrics scrape | The ledger sums a client-side field per request. The server's counters are the independent instrument, and deleting the second instrument to end a disagreement is how a wrong number becomes permanent. |
| Put the counter snapshot on `RunManifest` | Wrong grain (a manifest run record is one run, a snapshot is one shard), wrong producer (the manifest is written hours later in another job, so the numbers would have to survive an artifact that expires in a day and is skipped on cancel), and wrong audience (`run.json` is a payload a reader fetches; this is measurement evidence and belongs under `state/`). |
| Scrape the counters per request instead of once at job end | Both counters are cumulative, so a per-request scrape adds requests to the thing it measures and still reports only the last one. |
| Keep the zero-anchored domain | Spends most of the plot on rates nothing ran at. Zero on a candle chart is not a landmark, it is padding. |
| Draw prompt reuse as a single marker on a one-day window | One point compares to nothing. |
| Hide the chart until two days exist | Five order statistics is a real shape on day one. |
| Delete the per-mark `<title>` for a pinned readout | A tooltip redesign is a separate change, and the browser suite binds to this text. Deferred, not overlooked. |

## See also

- [`../sources/item-health.md`](../sources/item-health.md) - the columns, and how a rate is derived.
- [`../contracts/schemas.md`](../contracts/schemas.md) - `RuntimeCountersRow`, and why the snapshot is its own contract.
- [`prompt.md`](prompt.md) - the bands, and why the ask changes with article length.
- [`../../reference/measurements.md`](../../reference/measurements.md) - every number here, with hardware and date.
- [`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md) - why a worker may reorder inside its shard.
