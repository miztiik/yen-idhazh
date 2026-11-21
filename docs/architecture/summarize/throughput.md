# Model throughput and why it drifts inside a run

**Last Updated**: 2026-11-18
What the two model rates mean, why the slow half of a run is slow, and what a
change in either number is allowed to prove.

The rates are recorded per item on the item-health ledger and drawn on the
console. The columns and how a rate is derived from them are owned by
[`../sources/item-health.md`](../sources/item-health.md); this page owns the
behaviour.

**Every figure on this page was taken at `extract.truncation_cap_tokens` = 2500,
which reads at most 1,923 words of an article.** The cap is a throughput lever,
so a rate taken at another cap is not comparable item for item with anything
here. **The configured cap has moved twice since - to 5000 on 2026-08-29 and to
10,000 on 2026-09-09** - so every rate on this page is a cap-2500 rate and is two
moves behind the running config. The two conditions that revert the first move
are in
[Truncation measurement](../../reference/benchmarks/how-often-the-truncation-cap-bites.md),
and what that run has to record is in
[Recording a current measurement](../../reference/pipeline-cost.md#how-to-add-a-reading).
What the move to 10,000 cost is measured in
[How often the truncation cap bites](../../reference/benchmarks/how-often-the-truncation-cap-bites.md).
**Read is the end that moves.** A longer article is more prompt to take in. At
the cap-2500 measurement write did not move, because the summary length asked
for followed the article's length from before the cap cut it; the ask has since
been removed, and no reading has been taken without it.

## What a thinking span costs, and the one part that is still an estimate

A call is decoded as an unconstrained thinking span and then the
schema-constrained answer whenever `models.<role>.thinking_close` is
declared. The incumbent declares none, so every figure on this page is a
no-thinking figure and stays comparable. What follows is what turning it on
costs.

**No budget is sent, and none can be set.** The two decode caps left
the entry's settings on 2026-09-21, so the span ends where the model writes
its closing marker and the window is the only other thing that stops it. Maintainer
ruling, 2026-09-17: the 256 that used to sit there was carried over from no
reading of any of these weights, it was below every published thinking budget we
could find, and it landed in the band where a thought is cut rather than
finished - which scores worse than no thought at the same budget
([arxiv 2504.09858](https://arxiv.org/abs/2504.09858)). A cap chosen that way
prices nothing; it only decides where the thought gets cut. Every committed
entry had already left it null, so the field went with the answer cap beside it
rather than waiting for a reading nobody was going to take.

**The cost of a span is unmeasured.** The measured rate is **6.01 +/- 0.11
tokens a second** (2026-08-23, `ubuntu-latest`, EPYC 9V74, llama.cpp build
b10598, three repeats). The number of tokens these weights spend before closing
the block is not measured and belongs to the weights rather than a knob. Against
the 900-token answer worst case of 149.8 seconds, every 100 tokens of thinking
is **16.6 seconds**. An item makes one call, so it pays one span.

**The risk the null cap carries, named.** With no cap, a model that never writes
its closing marker decodes to `n_ctx` - and the answer span's prompt is the
thinking span's prompt plus what it wrote, so that item fails on the window
rather than returning a cut summary. That is a louder failure than the one the
cap prevented and a slower one. It is the reason the closing marker has to be
the bytes the model actually writes rather than a plausible guess
([prompt.md](prompt.md#two-spans-on-one-call)).

**One part is an estimate and is labelled one** (Guardrail #10). Whether the
answer span re-pays prefill on the thinking tokens has not been read. The slot
should hold - span two's prompt is span one's extended, `cache_prompt` is
requested, and case 2 of the start-up probe refuses a run whose second call
re-read a prompt the first one filled. If it misses, the estimated cost is
**25.6 seconds an item more**. **What settles it**: the dispatch logs span two's
evaluated tokens beside its cached tokens on every item, and their difference is
what the answer span really prefilled. One run with thinking declared answers it.

**The shard bound was re-derived rather than carried forward.** The worst of the
80 shard rows on 2026-09-02 used 135.4 minutes and carried 40 items, so the
worst measured item is 203.1 s. A worker now draws 20 items
(`run.safety_ceiling_per_run` 80 over `run.max_parallel` 4). On 2026-09-14, for
the two calls an item then made, two thinking spans added 85.2 s, so the derived
worst item was 288.3 s and the derived worst shard 96.1 minutes. An item now
makes one call and pays one span, 42.6 s, so the same inputs derive a worst item
of **245.7 s** and a worst shard of **81.9 minutes**.
`run.shard_timeout_minutes` stays at 200, which holds that with 2.4 times over.
`run.shard_size` stays at 5: the fan-out is
`min(ceil(80 / 5), 4)`, so `max_parallel` binds and the size would have to rise
above 20 to move anything - and a worker carrying more items is the opposite of
what a longer item wants.

## Two rates, not one

The runtime charges a summary in two parts, and they run at different speeds:

| Name | What it is | Measured 2026-08-24 |
| --- | --- | --- |
| **read** (prefill) | The model taking the article in. Batched, so the machine works on many tokens at once. | 10.95 tok/s, 91.3 ms per token |
| **write** (decode) | The model producing the summary. One token at a time, each conditioned on all the ones before it. | 5.05 tok/s, 198 ms per token |

**Both rates were taken on a model that is no longer configured, and the read
rate is no longer the one to quote.** They come from run `32742672105` on
2026-08-24, 149 articles on `Qwen3-8B-Q4_K_M.gguf`, and the summarizer moved to
`Qwen3.5-9B-Q4_K_M` on 2026-08-27. On the configured 9B, read runs at a median
**9.85 tokens a second**, slowest timed item 8.25 and fastest 44.71, measured
2026-09-09 over the timed items of 2026-09-01 to 2026-09-09 on GitHub-hosted
`ubuntu-latest`, 4 vCPU, no GPU
([What the wall clock pays](../../reference/benchmarks/how-often-the-truncation-cap-bites.md#what-the-wall-clock-pays)).
**Do not subtract those two numbers.** They differ by model, by cap and by which
processor their shards drew, and the last of those three is worth 4.2 times on
its own - see
[The processor a shard draws](#the-processor-a-shard-draws-moves-read-four-times-harder-than-any-knob)
below. The retired figures stay on this page because the ratio between read and
write is what the page is about, and that ratio is a property of the two phases
rather than of the model.

**Read is 10.95 tokens the model actually read per second, not 10.95 tokens of
prompt per second.** The two differ by a factor of about 1.8, because roughly
half of every prompt is reused from the cache rather than read. The figure is
`input_tokens - cached_tokens` over `prefill_ms`, and the console draws the same
subtraction. Counting the cached half in would report 19.96 tok/s on a run whose
real rate was 11.09 - a rate the machine never ran at. Whenever this page or the
console prints a read rate, that is the one it means.

**The two per-call columns said that and did the other thing, from 2026-09-12 to
2026-09-15.** `label_prefill_tokens_per_s` and `summary_prefill_tokens_per_s`
divided the whole prompt by the prefill clock. On the label call the error is
small, because that call caches little. On the summarize-and-plan call it is
enormous, because that call reuses the label prompt almost whole: one item on
2026-09-14 published **787.46 tokens a second** on a prefill that evaluated 52
new tokens in 6,206 ms, which is **8.4**. A reader comparing the two calls read
a server that was 93 times faster on the second one. Corrected in the same
commit as the element-id bound; both columns carry a `2026-09-15T19:40` stamp,
and a row from before it may not be put on the same axis as a row from after.
Nothing needs re-deriving from the committed rows: `cache_pct` and the token
counts are on the same row, so an old rate can be recomputed from its own
neighbours.

Read is about 2.2x write. That ratio is a property of how the two phases work,
not of this model, and it is why `summarize_ms` was split: one blended number
cannot say whether a slow day was long articles or long summaries.

## Each call is charged on its own, and the item is their sum

From 2026-09-12 `Summary`, the item-health ledger and the published projection
record the five cost numbers per call as well as for the item, and an item made
two calls until 2026-11-17. It makes one now, recorded in the second slot so the
`summary_*` series stays continuous, and a row written while it made two stays
readable. **The five flat cells are the sum over the
calls the row records**, which is what keeps every reader that pools them -
`day_metrics`, `console_band`, `backend/utilities/reconcile_prefill.py`
and the console's own rates - correct with no edit of its own however many calls
a row records. The contract refuses a row where they are
not, so the property is enforced rather than described.

Why the split exists is one number. Measured 2026-09-12 on a developer laptop,
one run and no spread, `Qwen3-8B-Q4_K_M.gguf` on llama-server with
`--threads 4 --ctx-size 16384 --batch-size 512 -np 1 -fa on` - an
order-of-magnitude check and not a runner reading:

| Quantity | The label call | The summarize-and-plan call | Folded |
| --- | --- | --- | --- |
| `input_tokens` | 1,497 | 2,389 | 3,886 |
| `cached_tokens` | 0 | 1,493 | 1,493 |
| Share of its own prompt reused | 0 percent | 62 percent | 38 percent |
| `prefill_ms` | 214,122 | 186,750 | 400,872 |
| `output_tokens` | 205 | 567 | 772 |
| `decode_ms` | 88,795 | 292,626 | 381,421 |

The folded column is the whole argument: 38 percent is neither call's answer,
and it is the number the console printed as the item's. The first call reads the
article on a cold slot and reuses nothing; the second replays it and is answered
for almost all of it.

**A per-call `prefill_ms` is a duration and never a rate.** The summarize-and-plan call read at 4.80
tok/s against the label call's 6.99 in the same second on the same machine, 31 percent
apart, because the summarize-and-plan call's tokens sit at context positions 1,493 to 2,389 and
attend to everything before them - a prompt token costs more the deeper into the
context it sits. The 31 percent is measured; that attribution is an estimate,
and a sweep of new-turn length against `prefill_ms` at a fixed prefix length
would settle it. The item's blended rate, summed over summed, is the only read
rate that composes, and it is the one this page and the console mean.

**The projection publishes the first call and the item total, not both calls.**
The second is the remainder, exactly, because the totals are the sum and the
arithmetic is integers; `model_calls` says how many calls that remainder covers,
so a third could not be absorbed in silence. Publishing both would have cost
more than the split is worth to a file a browser fetches: measured 2026-09-12 on
the two committed shards with every timed row populated, twelve cells cost
**72.9 and 80.1 percent more gzipped** against **35.3 and 40.8 percent** for the
seven that ship.

**The picture costs nothing outside these cells.** The summarize-and-plan call writes the summary and
the answer about a chart in one reply, so what a picture cost is already inside that call's
columns; there is no second model call for an item, and no second job.

**The split accounts for all but 0.066 percent of the call.** `summarize_ms` is
our stopwatch around the HTTP request; `prefill_ms + decode_ms` is what the
server said the same request cost. Over the 2,317 committed rows that carry all
three the difference - transport, JSON and validation - has a median of **79 ms
against a median call of 122,432 ms**, and **0 of the 2,317 are negative**
([Checking the request and server measurements](../../reference/pipeline-cost.md#the-ledger-and-the-server-agree-about-the-read-rate)).
So a slow day is the model and not the client, and there is no unnamed third
phase hiding inside `summarize_ms`.

**Since 2026-09-16 each call has that same pair, and the wait is the
subtraction.** `label_ms` and `summary_ms` are a stopwatch opened before their
own request and stopped when the reply is in hand, so `label_ms` minus
`label_prefill_ms` minus `label_decode_ms` is what the server did not claim for
that call: transport, and any time it spent queuing the request without saying
so. Until this row both columns were `prefill_ms + decode_ms` for their slot -
a column that agrees with its two neighbours by construction, so the
subtraction gave zero on every row ever written and a server that made an item
wait read exactly like a server that answered at once. The item-level residual
above could not stand in for it: one number over a pair of calls cannot say
which of the two waited.

**The rates are still taken over the server's own clocks, and `model_wait_ms`
is still the item-level residual.** A decode rate charged the queue would read
as a slower model, which is the misattribution the split exists to prevent, so
`label_decode_tokens_per_s` divides by `label_decode_ms` and never by
`label_ms`. `model_wait_ms` subtracts the four per-call prefill and decode
cells from `summarize_ms` for the same reason: it is named for the wait, and
subtracting the two stopwatches instead would leave it holding this process's
own render, parse and draw under a name that says model.

Measurements, with hardware and date, are in
[`../../reference/pipeline-cost.md`](../../reference/pipeline-cost.md).

## The read rate is checked against the server, and it holds

Every timing above is a field the summarize stage copied out of one model reply.
The model server counts the same work for itself and publishes the totals on
`/metrics`, which is a second instrument that shares none of the first one's
failure modes. Until 2026-08-27 those counters reached only a job log that keeps
them for two days, so this page published a rate nothing committed could check -
and under Guardrail #10 a number that cannot be reconciled cannot justify a design.

Each `work` shard now commits its server's counters onto its own row of
the host-fingerprint ledger, and
`backend/utilities/reconcile_prefill.py` pools both sides of one run and prints
the gap. **Measured on run `2026-08-26-5`: the ledger says 11.1755 tok/s and the
server says 11.1796, which is 0.037 percent apart against a 5 percent bound
written down before either side was read.** Tokens read, tokens reused and
tokens written match to the token on both sides. The full figures are under
[The ledger and the server agree about the read rate](../../reference/pipeline-cost.md#the-ledger-and-the-server-agree-about-the-read-rate).

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

### A reply the stage refused used to be missing from one side of this check

The gap this check reports is not all noise, and until 2026-09-13 one named
cause sat inside it. A reply that failed its shape wrote a summary whose five
cost cells were the model's defaults of zero, and the census row dropped them
entirely - so the server counted that request and `pool_ledger`, which skips a
row with an empty `prefill_ms` or `input_tokens` cell, pooled none of it.

**Measured on the committed ledger, 2026-09-13, three runs on the stock runner.**
Run `2026-09-12-34717684802` carries one refused reply, and it is the whole of
that run's disagreement: the ledger read 72,739 tokens over 3,918.41 s against
the server's 73,616 over 3,936.07 s, which is **0.746 percent apart - one
article consuming 15 percent of the 5 percent tolerance**. The two neighbouring
runs carry no refused reply and match the server **to the token** (81,173 and
72,219 on both sides), at 0.051 and 0.070 percent. Across the whole committed
ledger 93 of 93 failed summarize rows carried no cost at all.

The stage now hands the reply to the failure path and the census row carries the
same five cells an ok row does, so a refused reply is pooled rather than skipped.
What that costs a reader of a trend: the ledger's token and second totals step up
on 2026-09-13 against the days before it, on the failure rate rather than on
anything the model did. A cost cell left empty on a failed row written before
that date means never recorded, not free.

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

**The shared prefix is worth naming.** The system turn is byte-identical on
every item, so the one-slot cache answers it from the previous item while the
article behind it reads from cold. Measured 2026-09-12, when an item made two
calls, item 2 of a run reused **1,362 tokens** of its first prompt with no work -
that system turn - and the run destroyed the previous item's copy of the rest,
which is what a one-slot cache is supposed to do
([`../../reference/benchmarks/two-call-re-read.md`](../../reference/benchmarks/two-call-re-read.md)).
What an instruction placed behind the article costs, and why the instructions
sit in the system turn in front of it, is measured in
[`../../reference/benchmarks/instructions-in-front.md`](../../reference/benchmarks/instructions-in-front.md).

## Which stage sends the call

`work` sends one call an item: it reads the article and writes the summary and,
when source readings are available, the answer about a chart. Until 2026-11-17 it sent two,
adjacently - a call that labelled names and places, then the summary-and-plan
call - and the adjacency was a correctness rule: the summarize entry pins
`n_parallel` to 1, so the server holds one cache slot, and every first call
before every second call would have evicted the prefix before it was reused. The
first call took 52 percent of model time on 66 captured articles and fed a chart
planner that published no chart, so it went
([prompt.md](prompt.md#design-rationale)).

**There is no flag and no second path.** `run.two_calls_per_item` once switched
between one call and two, for one day. Plan 11 row #6 deleted the knob, the small
model, the `visuals` job and the single-call branch of `stage_work` in one commit
on 2026-09-13, and the stage has had one path since. Maintainer ruling,
2026-09-13: move forward, no rollback.

**The pipeline stamp digests the prompt the call renders.** The stamp
hashes the chat template read off `/props`, and the call renders its own
bytes, so that template no longer reaches what the model reads and
`models.summarizer.turns` does. `classify.calls.prompt_inputs`
is what the stamp hashes instead: both turns rendered through the same helpers
the live request uses, with the headline and article empty and fixed example
data references with the enabled capabilities
([why each is there](prompt.md#the-record-covers-the-ask)). Editing a marker moves the stamp,
which is the state `Observation.DETERMINISM_VIOLATION` exists to make visible -
and it is the only route the envelope takes into a run record, because
`run.json` carries the recorded model reference and the markers sit on the
declared entry.

## The window is checked before the call is sent

`backend/idhazh/classify/dag.py` answers one question: does this article's call
fit the window. The window has to hold the prompt - the instructions, the article
and the data references - and then the longest reply the model file lets
the call write. `dag.call_tokens` is that sum: an estimate of the prompt, built
from two readings in `idhazh.measured` (the fixed scaffold and the tokens a word)
that were taken on a longer prompt than the one sent and so sit above it, plus the
UTF-8 bytes of the references shown, plus `sampling.max_tokens`. **References are counted
a token a byte**: a token spans at least one byte of the text the tokenizer reads, so the
bytes shown are a ceiling that needs no reading of the tokenizer. A count in characters
would not be one, because a rare character can cost several byte-level tokens. The
contract test and the production refusal read the same function.

**An article the window cannot hold is refused before the call is sent.**
`dag.fits_the_window` is the check, run on the article alone first, and
`FailureCode.CONTEXT_EXCEEDED` is what the item lands as. Admitting it would cost the
picture rather than the item:
`--no-context-shift` means the decode stops at the wall on an ordinary HTTP 200,
`recovered_completion` salvages the summary, and the item publishes with
`window_exhausted` recorded where the picture would have been - after the whole
decode has been paid for. Refusing it up front is still the better answer,
because that whole decode is spent before the reason can be written.

**The data references are optional where the article is not.** When the article
fits and its references would not, one warning is logged, the chart question is
left off, and the decision records `not_reachable`.

**How many items the window refuses, and it is none.** Over the trailing 30 days
ending 2026-09-13, 8,938 items carry a recorded prompt: the median is 1,672
tokens, the 95th percentile 3,378 and the worst 8,741. Read once from
`ledger.load_item_health` with a 30-day cover, 2026-09-13; that reader is
`ledger.load_days` over the same 30 days now. Behind the prompt the call holds a
fixed 8,192 tokens, the model file's response limit. The longest article the
extractor passes (26,000 tokens) sums to 52,874 tokens with that limit and no data references,
against the 65,536-token window (computed 2026-11-18 from the committed window and
cap), so no committed article is refused. That leaves 12,662 tokens, so data references of up to
12,662 bytes, for such an article, and a model file that names a larger `max_tokens` narrows
them one token for one. How often references are dropped for want of room is not measured here;
the logged warning counts it.

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

The cause is our own ordering. `stage_work` sorts a worker's items by source
length before the model loop (by prompt band until 2026-11-17), so **every worker
summarises its shortest articles first and its longest last**. By the second half
of a job each request is carrying a bigger prompt and the summary it writes is
longer, and both make writing slower per token:

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
([Current throughput measurement rules](../../reference/pipeline-cost.md#inference-throughput)).

The lever that remains is the number of shards. Each shard is its own runner
with its own 4 vCPU, so raising the shard count adds cores rather than dividing
them, and it widens the part of the stage that is already parallel. `digest.yml`
raised its ceiling from four shards to eight on 2026-08-25 for that reason. One
run has now used it: the slowest worker fell from 113.1 minutes to 58.8, which
is 1.92x, on a day whose total tokens were within 1 percent of the four-shard
baseline's. It is not a paired measurement and it did not publish - the caveats
and every other figure are under
[Sizing parallel work](../../reference/pipeline-cost.md#where-the-work-jobs-bound-comes-from).

## The processor a shard draws moves read four times harder than any knob

**Measured 2026-09-09** across run `2026-09-09-34379502244` and its same-day
baseline `2026-09-09-34323771996`, on stock GitHub-hosted `ubuntu-latest`,
4 vCPU, no GPU. Uncached read on the Intel Xeon Platinum 8573C shards ran at a
median **41.00 tokens a second** against **9.86** on AMD EPYC 9V74. **That is 4.2
times faster on the same job at the same settings.**

| Read, uncached tokens a second | items | min | median | max |
| --- | --- | --- | --- | --- |
| baseline, Intel Xeon Platinum 8573C | 35 | 33.34 | **41.00** | 43.94 |
| baseline, AMD EPYC 9V74 | 38 | 9.70 | 9.97 | 14.60 |
| priced, AMD EPYC 9V74 | 35 | 9.79 | **9.86** | 9.98 |
| priced, AMD EPYC 7763 | 35 | 9.43 | 9.76 | 9.84 |

**Which processor a shard lands on is a larger term in its read time than any
knob in `config/`, and no knob touches it.** GitHub assigns the host. The two
runs above drew different mixes of processor on the same day, so one shard can
read about four times faster than its sibling in the same run.

Three things follow for anyone reading a rate off this page or the console:

- **A rate that moved between two runs is not evidence of a change we made**
 until both runs are known to have drawn the same processor. `cpu_model` is a
 committed per-shard cell on the host-fingerprint ledger, so that check costs
 a column read.
- **Compare within a processor, never across one.** Every paired figure in
 [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) that prices a
 runtime setting is matched on EPYC 9V74 for this reason. Doubling `n_ctx` moved
 read by about 1 percent; the processor moves it by 4.2 times.
- **A whole-run median hides it.** The month figure of 9.85 tokens a second runs
 from 8.25 to 44.71, and a 5.4x spread in one column is not measurement noise.
 The table above is what is in it.

**This is not a lever we can pull**, which is why it sits beside the levers
rather than among them. It is on this page because it is the largest single term
in a shard's read time, and a page about what moves throughput that leaves out
the biggest mover teaches the wrong model of the machine
([The cap cut nothing, and the rate it was priced at did not move](../../reference/benchmarks/a-run-at-the-doubled-window-and-cap.md#the-cap-cut-nothing-and-the-rate-it-was-priced-at-did-not-move)).

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
 under `prompt tokens reused`; it is a cache statistic and is not drawn.
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
[`../../reference/pipeline-cost.md`](../../reference/pipeline-cost.md).

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
know. `loadManifests` already returns each day's model ids, so the join is
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

**Why the length sort stays, even though it makes the run look like it degrades.**
Shortest source first means a shard that runs out of its own clock leaves its
longest items unworked rather than its quickest, so more items finish in the
time there is. The files are addressed by item id, not by processing order, so
the ordering changes what is worked first and never the output
([`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md)). Until
2026-11-17 the sort was by prompt band, on the argument that same-band prompts
share a prefix because the band's numbers were substituted into the system
prompt. The system turn is the same bytes for every item now, so that argument
is gone and the order does not touch the cache.

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
drawn extent rounded outward by `.nice`, and both ends are printed so the
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
| Sort items by discovery order to flatten the drift | Trades the shortest-first order, which leaves a clock-limited shard's longest items unworked rather than its quickest, for a prettier chart. |
| Keep two requests in flight per worker to overlap read and write | Measured 2026-08-25: aggregate write rises 1.055x for a second sequence, spread 0.022, against a 1.4x gate. That is about 1.9 percent of a run. Four sequences reach 1.133x and oversubscribe the 4 vCPU. Cancelled, not deferred. |
| Report one blended `summarize_ms` rate | Cannot separate a long-article day from a long-summary day, which is the question the chart exists for. |
| Average the per-item rates for the day figure | A rate is a ratio. Averaging weighs a 60-word release note the same as a 2000-word feature. |
| Raise `retention-days` on `runtime-log-*` and reconcile the read rate by hand | Two days becomes thirty and the answer still expires. Guardrail #10 wants the evidence to survive with the claim, and a committed row is the only thing that does. |
| Trust the ledger and delete the metrics scrape | The ledger sums a client-side field per request. The server's counters are the independent instrument, and deleting the second instrument to end a disagreement is how a wrong number becomes permanent. |
| Put the counter snapshot on `RunManifest` | Wrong grain (a manifest run record is one run, a snapshot is one shard), wrong producer (the manifest is written later in another job, so the numbers would travel through an expiring artifact; [digest.yml](../../../.github/workflows/digest.yml) declares its retention), and wrong audience (`run.json` is a payload a reader fetches; this is measurement evidence and belongs under `state/`). |
| Scrape the counters per request instead of once at job end | Both counters are cumulative, so a per-request scrape adds requests to the thing it measures and still reports only the last one. |
| Keep the zero-anchored domain | Spends most of the plot on rates nothing ran at. Zero on a candle chart is not a landmark, it is padding. |
| Draw prompt reuse as a single marker on a one-day window | One point compares to nothing. |
| Hide the chart until two days exist | Five order statistics is a real shape on day one. |
| Delete the per-mark `<title>` for a pinned readout | A tooltip redesign is a separate change, and the browser suite binds to this text. Deferred, not overlooked. |

## See also

- [`../sources/item-health.md`](../sources/item-health.md) - the columns, and how a rate is derived.
- [`../contracts/schemas.md`](../contracts/schemas.md) - `HostFingerprintRow`, and why a job-grain fact is its own contract.
- [`prompt.md`](prompt.md) - the prompt, the reply shape and the output budget.
- [`../../reference/pipeline-cost.md`](../../reference/pipeline-cost.md) - every number here, with hardware and date.
- [`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md) - why a worker may reorder inside its shard.
