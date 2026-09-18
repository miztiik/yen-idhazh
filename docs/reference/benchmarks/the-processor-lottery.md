# What processor a run draws, and what it does to a reading

**Last Updated**: 2026-09-17

GitHub gives a job whatever machine is free. This page is the record of what that
choice is worth, measured over seventeen bench dispatches between 2026-08-23 and
2026-09-16.

**The short answer: it is worth more than any difference between our candidate
models.** The same weights, the same llama.cpp build and the same synthetic
prompt read up to 3.9 times faster on one machine than on another. So a
throughput number quoted without its processor is not a reading, and two models
compared across two runs have not been compared at all.

**And it is a lottery per JOB, not per run.** Sixteen dispatches recorded a
processor for both of their jobs, 32 placements in all, and **twelve of the
sixteen split across two different processors inside one run** - same commit,
same dispatch, seconds apart. On 2026-09-15 four dispatches inside 18 seconds
produced eight placements over four machine kinds; on 2026-09-16 four more,
dispatched together at 10:42 UTC, did the same. Nothing we control reaches that
decision.

## What was measured

`llama-bench` from llama.cpp `b10598` (`56db501e7`), 4 threads, 3 repeats,
prompts of 730, 1,800 and 4,850 tokens and 250 generated tokens. Every dispatch
runs it against whichever weights that dispatch was pointed at, and records the
processor from `/proc/cpuinfo` in the same artifact.

This is a synthetic prompt rather than an article, which is the point: it is
identical in every run, so the only things that move between two rows are the
weights and the machine.

**A wall-clock reading may be set beside another only when the two ran over the
same source text.** That is a check and not a judgement: the bench records a
digest of each article's extracted text, and two dispatches on different days
differ by their articles as well as their machine. The four dispatches of
2026-09-16 are the first shown to match - the same five item ids over five
identical source digests - so [what the wall clock
did](#what-the-wall-clock-did-over-one-fixed-corpus) is a reading of the machine
and not of the news. No other pair of dispatches has passed that check.

## The six machines GitHub has given us

Every column here is the host's own report, from `lscpu` and `/proc/cpuinfo`. No
row carries a marketing codename, because no machine reports one and a codename
somebody remembered is not a reading (Guardrail #10).

| Processor | family/model/step | AVX-512 | AMX | L3 | BogoMIPS |
| --- | --- | --- | --- | --- | --- |
| AMD EPYC 7763 64-Core | 25/1/1 | **none** | no | 32 MiB | 4,891 |
| AMD EPYC 9V74 80-Core | 25/17/1 | yes, with bf16 | no | 32 MiB | 5,192 |
| AMD EPYC 9V45 96-Core | **26**/2/1 | yes, with bf16 and `avx_vnni` | no | 32 MiB | 5,192 |
| Intel Xeon Platinum 8370C | 6/106/6 | partial, no bf16 | no | 48 MiB | 5,587 |
| Intel Xeon Platinum 8573C | 6/207/2 | yes, with bf16 and fp16 | **yes** | 260 MiB | 4,600 |
| Intel Xeon 6973P-C | 6/173/1 | yes, with bf16 and fp16 | **yes** | 480 MiB | 5,200 |

Three facts worth pulling out of that table.

**The machine we draw most has no AVX-512 at all.** The EPYC 7763 took 18 of 32
placements and is the slowest at prefill. It is the machine most of our numbers
were taken on.

**Every one is two physical cores with two threads.** Core count is a constant
across the fleet. Only the instruction set and the cache change, which is why
those are the columns.

**BogoMIPS predicts nothing.** The highest number in the table belongs to a
machine that is not fast. It is recorded because it is the figure people reach
for first, and it is worth knowing that it is useless here.

**Six kinds is the count on 2026-09-16, and the four dispatches of that day added
none.** They drew the EPYC 7763, the EPYC 9V45, the EPYC 9V74 and the Xeon 8573C
- four of the six already here. Neither the Xeon 8370C nor the Xeon 6973P-C
appeared.

Nothing selects between these and nothing ever will. `ubuntu-latest` is one label
over a fleet, and a job takes what is free.

## Every draw

Prefill is reading the prompt. Decode is writing the answer. Both are tokens a
second, and higher is faster.

| Model | Processor | Run | Prefill, 730 | Decode, 250 |
| --- | --- | --- | --- | --- |
| Gemma 4 E4B | AMD EPYC 7763 | `34901487530` | 20.510 +/- 0.021 | 10.488 +/- 0.018 |
| Gemma 4 E4B | AMD EPYC 7763 | `34972996987` | 20.564 +/- 0.035 | 9.676 +/- 0.083 |
| Gemma 4 E4B | AMD EPYC 7763 | `34973005911` | 20.502 +/- 0.063 | 10.532 +/- 0.014 |
| Gemma 4 E4B | AMD EPYC 7763 | `35011578538` | 20.466 +/- 0.044 | 10.466 +/- 0.045 |
| Gemma 4 E4B | AMD EPYC 7763 | `35086403868` | 20.480 +/- 0.078 | 10.195 +/- 0.087 |
| Gemma 4 E4B | AMD EPYC 7763 | `35086409972` | 20.433 +/- 0.100 | 10.226 +/- 0.065 |
| Gemma 4 E4B | AMD EPYC 9V45 | `34905960781` | 75.453 +/- 0.147 | 15.516 +/- 0.086 |
| Gemma 4 E4B | AMD EPYC 9V45 | `34941400155` | 74.637 +/- 0.192 | 15.744 +/- 0.056 |
| Gemma 4 E4B | AMD EPYC 9V45 | `35086407071` | 73.595 +/- 0.166 | 15.014 +/- 0.129 |
| Gemma 4 E4B | Intel Xeon 8573C | `35011547415` | 59.322 +/- 0.348 | 10.212 +/- 0.019 |
| Ornith 1.5 9B | AMD EPYC 7763 | `34901484508` | 6.226 +/- 0.001 | 4.412 +/- 0.030 |
| Ornith 1.5 9B | AMD EPYC 7763 | `34938565911` | 6.195 +/- 0.004 | 4.538 +/- 0.011 |
| Ornith 1.5 9B | AMD EPYC 7763 | `35086412536` | 6.224 +/- 0.002 | 4.640 +/- 0.012 |
| Ornith 1.5 9B | AMD EPYC 9V74 | `35011557915` | 6.374 +/- 0.008 | 4.696 +/- 0.004 |
| Qwen3.5 9B | AMD EPYC 7763 | `35011568497` | 10.047 +/- 0.006 | 5.985 +/- 0.028 |
| Qwen3.5 9B | AMD EPYC 9V74 | 2026-08-23 | 10.14 +/- 0.01 | 6.01 +/- 0.11 |
| Qwen3.5 9B | Intel Xeon 8573C | `34812096911` | 39.653 +/- 0.371 | 3.906 +/- 0.019 |

Seven of these seventeen dispatches had their server case fail. The `llama-bench`
job succeeded in every one, so a failed dispatch still contributes its row here -
which is why this page has seventeen and the dossiers have fewer.

### The other job in the same dispatch

`llama-bench` is one job. The server case is another, and the platform places it
separately. Below are the four dispatches of 2026-09-16, the set for which both
placements and every server reading are on record. **Each row's fourth column is
the server job's own machine, never the `llama-bench` machine beside it.**

| Run | Model | `llama-bench` drew | The server job drew | Summarize, median | Peak resident set |
| --- | --- | --- | --- | --- | --- |
| `35086403868` | Gemma 4 E4B | AMD EPYC 7763 | AMD EPYC 7763 | 670.381 +/- 1.483 s | 8.647 +/- 0.049 GiB |
| `35086407071` | Gemma 4 E4B | AMD EPYC 9V45 | AMD EPYC 7763 | 675.401 +/- 11.358 s | 8.598 +/- 0.007 GiB |
| `35086409972` | Gemma 4 E4B | AMD EPYC 7763 | Intel Xeon 8573C | 359.993 +/- 15.062 s | 8.624 +/- 0.003 GiB |
| `35086412536` | Ornith 1.5 9B | AMD EPYC 7763 | AMD EPYC 9V74 | 781.256 +/- 11.885 s | 9.280 +/- 0.018 GiB |

Every reading is n = 3. The longest single summarize call in each, same row
order: 715.698 +/- 0.977 s, 716.912 +/- 6.510 s, 396.924 +/- 25.573 s and
1,065.284 +/- 9.910 s.

**Three of the four split. `35086403868` is the one that did not** - and what it
reports is that both of its jobs drew a machine calling itself an AMD EPYC 7763,
which this page has already measured is not the same claim as one machine.

Cold model load was 5,023 ms in three of the four and 5,019 ms in `35086409972`,
each n = 1 and no spread. Warm load was 5,002 +/- 0 ms in all but `35086407071`,
which read 7,503 +/- 5,002 ms over n = 2 - a spread the size of the figure, so
that is two readings rather than one.

`35086412536` also timed a cold weights download, 134.368 s for 6.19 GiB on
n = 1. **That measures the network, not the processor**, so it belongs in Ornith's
dossier and is not a row here.

## What it settles

### The machine is worth more than the model

Gemma's prefill median is 20.491 tokens a second on the EPYC 7763 over n = 6, and
74.637 on the EPYC 9V45 over n = 3, both to 2026-09-16. **That is 3.6 times, from
nothing but which machine was free.** Qwen3.5 reads at 10.047 on the EPYC 7763 and
39.653 on the Xeon 8573C, n = 1 each - 3.9 times, and the widest gap recorded.

For comparison, the whole gap this project was trying to measure between two
candidate models is a few percent. **Any single-run comparison between two models
is measuring the fleet.**

### Reading fast does not mean writing fast

The Xeon reads a Qwen3.5 prompt 3.9 times faster than the EPYC 7763 does, and
writes the answer **35 percent slower** - 3.906 against 5.985 tokens a second.

The two phases are limited by different things. Prefill works on the whole prompt
at once and is limited by how fast the cores multiply. Decode produces one token
at a time and is limited by how fast the machine can stream the weights out of
memory. A machine can be good at one and ordinary at the other, and the Xeon is.

**So there is no such thing as the fast runner.** It depends which half of the
work you are asking about, and our pipeline spends most of its time in decode.

### Prefill repeats. Decode does not

Six Gemma draws landed on an EPYC 7763. Their prefill readings span **0.6
percent**, 20.433 to 20.564. Their decode readings span **8.8 percent**, 9.676 to
10.532 - fourteen times wider, on the same weights and the same reported
processor.

The spread inside a single run does not show this: each of those six reported a
decode spread under 0.1 tokens a second and then disagreed with its siblings by
0.86. **A spread computed inside one run is a reading of that run, not of the
instrument.** Two runs on the same processor model are still two machines, and
`/proc/cpuinfo` cannot tell them apart.

The two draws added on 2026-09-16 moved the prefill floor from 20.466 to 20.433
and left both ends of the decode range exactly where they were. **Fifty percent
more sample widened the tight reading and not the loose one**, which is what a
reading limited by the instrument rather than by the machine looks like.

What this costs, concretely: a decode difference smaller than 8.8 percent cannot
be established by comparing two runs, however tight each one looks. It needs both
cases inside one job. [The Gemma dossier's draft-head
section](../models/gemma-4-e4b-qat.md#what-the-draft-head-is-worth) is the worked
example - a 5.3 percent difference that two runs could not establish and one
paired run settled.

### Ornith's narrow range is a gap in the sample, not a property

Ornith's four draws span **2.9 percent**, 6.195 to 6.374, which looks like a
model that does not care what machine it gets. It is not. **Ornith's
`llama-bench` job has only ever drawn the EPYC 7763 and the EPYC 9V74, which are
the two machines that read at the same speed as each other.** It has never met a
9V45 or a Xeon.

The fourth draw, `35086412536` on 2026-09-16, was a third EPYC 7763 at 6.224 -
inside the range already there, so it widened the sample and not the question.

This is the trap the whole page exists to name: a narrow range over an unlucky
sample looks exactly like a narrow range over a representative one.

### What the wall clock did over one fixed corpus

Every reading above is a synthetic prompt. On 2026-09-16 four dispatches read the
same five articles - the same five item ids, and five source-text digests that
matched across all four - so for the first time a wall-clock reading on this page
is about the machine rather than about the news.

Two of them were Gemma with the server job on an EPYC 7763. Their summarize
medians were 670.381 +/- 1.483 s and 675.401 +/- 11.358 s, n = 3 each - **0.75
percent apart**, and they wrote byte-identical summaries. The third was Gemma
with the server job on an Intel Xeon 8573C, and its median was 359.993 +/- 15.062
s: **46 percent faster than those two.**

**Name the confound before quoting that.** The Xeon case did not write the same
summaries. On the longest of the five items it produced 2,402 output tokens
against 2,048 on each EPYC case, 17 percent more, and still finished that item in
347 s against 672 and 690. More tokens cost more decode time, so the machine is
worth at least what the ratio shows and not less. What it is worth exactly, these
three runs cannot say.

**It follows decode, but only when decode is read off the machine that did the
work.** `llama-bench` puts Gemma's decode within 0.014 tokens a second on the two
machines - 10.226 on the EPYC 7763 in this very dispatch, and 10.212 on a Xeon
8573C drawn by `35011547415` on another day, a ratio of 1.0014. On that reading
the halving is unexplained, and until 2026-09-17 this page said so.

**It said so because `llama-bench` did not run on the machine that wrote these
summaries.** The server's own counters, taken inside the `runtime` job, read 7.94
tokens a second a decode on the EPYC 7763 and 14.66 on the Xeon - **1.85 times,
against a wall-clock ratio of 1.86 to 1.88.** The next section is why the two
instruments disagree and which one to believe.

That still does not close it. The Xeon case wrote 17 percent more tokens on the
longest item, so a full accounting has to divide the extra work out first, and
three runs cannot do that.

### The instrument is split across two machines, and one of its halves is the wrong one

**The `llama-bench` job and the `runtime` job of one dispatch landed on different
processors in 3 of the 4 dispatches on 2026-09-16** - 9V45 against 7763, 7763
against Xeon 8573C, and 7763 against 9V74.

That is not only a fact about placement. It is a defect in what the bench
publishes. In `35086409972` the emitted dossier attributes its prefill and decode
rates to an EPYC 7763, while the seconds-an-item table printed beside them came
from an Intel Xeon 8573C. On the server's own counters that Xeon reads **2.27
times faster** - 43.58 tokens a second against 19.20. **So the published rate and
the published wall clock in that dossier describe two different machines.**

**The right machine's rates are already free.** The `runtime` job writes its own
server counters, so no new run is needed to fix this - only a different column to
read. The speed case's own run summary now names the processor it drew and says
in as many words that the other job may have drawn a different one, which is this
finding turned into a line a reader sees without opening an artifact.

| Run | The `runtime` job drew | Server prefill | Server decode |
| --- | --- | ---: | ---: |
| `35086403868` | AMD EPYC 7763 | 19.20 tok/s | 7.94 tok/s |
| `35086407071` | AMD EPYC 7763 | 19.20 tok/s | 7.93 tok/s |
| `35086409972` | Intel Xeon 8573C | 43.58 tok/s | 14.66 tok/s |

Each is the median of three repeats, and the three agreed to **0.05 percent on
prefill and 0.25 percent on decode**.

**And the server's rate travels between dispatches, so it is usable.** Prefill
falls only **4.2 percent over a 6.6-times change in prompt length** - 20.48
tokens a second at 730 tokens against 19.61 at 4,850 - so two dispatches over
different articles are still comparable to within a few percent. That is far
tighter than the **127 percent** machine gap the reading has to resolve, which is
what makes the server counter the right instrument and `llama-bench` on the other
job the wrong one.

### What the lottery costs in dispatches

A median's standard error is about `1.2533 * sd / sqrt(n)`, so the dispatches
needed to resolve a difference `d` is `ceil((1.2533 * cv / d) ** 2)`, where `cv`
is the coefficient of variation - the spread as a share of the reading. Two
samples give two values of `cv`, and both are on this page:

- **Gemma prefill on the synthetic bench: 64.9 percent**, n = 10, every Gemma row
  of [Every draw](#every-draw) above, 2026-08-23 to 2026-09-16.
- **Gemma `runtime` job wall clock: 32.0 percent**, n = 3, the three Gemma
  dispatches of 2026-09-16 at 161.0, 160.6 and 85.5 minutes.

| Difference to resolve | Dispatches at 32.0% | Dispatches at 64.9% | Runner hours at 188.5 min a dispatch |
| --- | ---: | ---: | ---: |
| 20 percent | 5 | 17 | 16 to 53 h |
| 10 percent | 17 | 67 | 53 to 210 h |
| 5.3 percent, the draft-head difference already settled | 58 | 236 | 182 to 741 h |
| Any of those, **paired inside one job** | **1** | **1** | **3.1 h** |

**The sentence that matters**: the bench already alternates both cases inside one
job, and for the differences this project actually has to resolve - 10 percent,
and the 5.3 percent draft head - that pairing is worth a factor of **17 to 236**
against comparing two dispatches.

So a change that makes a dispatch cheaper does not automatically make the
measurement cheaper. **A dispatch made 33 percent cheaper that then has to be
repeated 17 times is 11 times more expensive, not cheaper.** Where a dispatch's
time actually goes is [what a bench dispatch
costs](what-a-bench-dispatch-costs.md).

## The hypotheses, and what would settle each

Everything in this section is a guess with a measurement attached. None of it is
established, and a row here may not be quoted as a finding. It is written down so
the next person spends their runner time on the question that is still open
rather than on one somebody already closed.

**All six were checked against the four dispatches of 2026-09-16 and none was
settled. H3 is the only one those dispatches moved, and re-reading them on
2026-09-17 moved it a second time - by retiring its verdict rather than
narrowing it.** The reason four of the six could not move is worth stating once
rather than six times: **the readings H3, H4, H5 and H6 wait on are fingerprint
columns, and a bench dispatch does not write a fingerprint row.** Only `digest.yml` runs
`idhazh fingerprint`, so no bench artifact carries a bandwidth rate, an uptime, a
machine size or a region - the four bench artifacts of 2026-09-16 carry none of
them. Each verdict sits with its hypothesis below.

### H1. The instruction set is what moves prefill

The EPYC 7763 has no AVX-512 and reads Gemma at a median 20.491 tokens a second.
The EPYC 9V45 has AVX-512 with bf16 and reads it at a median 74.637. That is the
biggest single correlation in the table and it has an obvious mechanism:
llama.cpp picks a different kernel when the wider instructions are there.

**What would settle it:** the same weights on one machine with the wider kernels
switched off at build time. llama.cpp can be compiled without them, so this is
one bench dispatch against two binaries on one host - a paired case, which is the
only shape that cancels the machine.

**What already argues against a simple version of it:** H2.

**2026-09-16: no change.** All four dispatches ran the same stock binary, so the
paired build this needs has still never run.

### H2. The flag says the instruction exists, not how fast it runs

The 9V74 and the 9V45 both report `avx512f` and `avx512_bf16`. Qwen reads at 10.1
on the 9V74 and Gemma reads at 74.6 on the 9V45. If the flag alone decided it,
those two machines would behave alike and they do not.

The only difference either host reports is the family number, 25 against 26. A
processor can implement a wide instruction on a narrower datapath and run it in
two passes - the flag is still true and the throughput is half.

**What would settle it:** one model, benched on a 9V74 and a 9V45. We have never
run the same weights on both, so the comparison does not exist yet. Until it
does, H1 and H2 are indistinguishable from our data.

**2026-09-16: still the same gap.** `35086407071` put Gemma on a 9V45 and
`35086412536` put Ornith's server job on a 9V74, so the day drew both machines -
but not the same weights through `llama-bench` on both, which is the only shape
that answers this.

### H3. Decode is bandwidth bound and nothing we recorded measured bandwidth

Prefill swings by up to 3.9 times across the fleet; decode by 1.6. Prefill works
on a whole prompt at once and is limited by arithmetic. Decode produces one token
at a time and is limited by how fast weights stream out of memory. That would
explain why the Xeon 8573C reads Qwen 3.9 times faster and writes it 35 percent
slower.

**What would settle it:** a memory-bandwidth figure beside every throughput
figure. **This one is now instrumented**: every job records a large-block copy
rate, so the next several runs build the scatter this needs
([telemetry.md](../../concepts/telemetry.md)).

**2026-09-17: still open, and the verdict it carried is retired.** This page read
the 2026-09-16 halving as evidence that decode does not explain the wall clock.
That rested on a decode figure taken by `llama-bench` on the other job's machine.
On the server's own counters the two machines differ by **1.85 times at decode
against a wall clock of 1.86 to 1.88**, so decode does explain the wall clock and
always did. What is still missing is the bandwidth figure that would say why
decode differs, and that is a fingerprint column no bench artifact carries - the
scatter has to come from daily runs.

### H4. L3 size is why the two Intel parts read fast

The Xeon 8573C reports 260 MiB of L3 and the 6973P-C reports 480 MiB, against 32
MiB on every AMD part. A prompt's weights working set may fit in the larger cache
and not in the smaller.

**What would settle it:** the bandwidth probe at two sizes, one below the
reported L3 and one above. The gap between them is the cache effect, measured on
the machine rather than argued from a datasheet. The probe already records the
buffer size it used, so this is a config change and no code.

**2026-09-16: no change.** The probe has not been run at two buffer sizes, and
neither Intel part was drawn by `llama-bench` that day.

### H5. A pooled machine is slower than a fresh one

A runner handed to us after other work may have a cold page cache, a warm one, or
a noisy neighbour. Nothing we have recorded could tell those apart.

**What would settle it:** uptime at the moment the job starts, against the
throughput that job produced. **Now instrumented** - every fingerprint row
carries how long the machine had been up.

**2026-09-16: no change, and no bench run will ever move it.** Uptime is a
fingerprint column and the bench writes no fingerprint row. A daily run is the
only instrument for this.

### H6. Placement follows something we could read

The placement is per job and resolves in seconds, which rules out anything we
control. But the platform names its own decision - a machine size, a region, a
zone, a fault domain - and we have never asked for any of it.

**What would settle it:** the instance metadata service, which every job now
queries. If the pools turn out to be separable by size or region, "a lottery"
becomes "which pools we draw from", and that is a different conversation.

**2026-09-16: no change, for the same reason as H5.** The four artifacts carry no
machine size, region, zone or fault domain, because the bench does not query the
metadata service.

## What could be done about it, and what each costs

| Approach | Cost | What it buys |
| --- | --- | --- |
| Probe in one job, gate the expensive job on the result | one short job a dispatch | **nothing** - the expensive job is a different job and draws again. Twelve of sixteen is the measurement that refuses this |
| Self-probe: the working job reads its own processor first and exits early on a slow one | about a minute a rejected dispatch | the same machine it probed, so this one works |
| `ubuntu-24.04-arm` | one bench dispatch to find out | the only label that genuinely selects hardware, and free on public repositories |
| Larger runners | billed, including on a public repository | pins a machine family, against this project's constraints (Guardrail #2) |
| Accept it, and pair every comparison inside one job | nothing | comparison is already solved this way; only the wall clock still pays |

**The self-probe is the only one of these that works, and it is not recommended
for the daily run.** Burning dispatches to chase a machine is reasonable for a
bench somebody runs twice. As a standing part of the publishing path it is a
retry loop that makes a run non-deterministic and hides a capacity problem behind
a retry.

## What it does not settle

- **Which machine we will draw next.** Seventeen draws over four machine kinds is
  not a distribution anybody should quote a probability from. The counts in the
  tables above are what happened, not a rate.
- **Whether two machines reporting the same model string are the same machine.**
  The 8.8 percent decode spread across six EPYC 7763 draws says they are not,
  and says nothing about why - host load, memory population and silicon stepping
  are all unmeasured here.
- **What any of this costs a published digest.** These are synthetic prompts, and
  the one fixed-corpus comparison above is five articles on one day. The
  wall-clock cost of a real item is in each model's dossier, over that day's
  articles.

## What to do about it

1. **Never print a throughput number without its processor.** This is Guardrail
   #10 and this page is the reason it is not a formality.
2. **Never compare two models across two runs.** Compare them on one machine, or
   do not compare them.
3. **When a difference must be measured, put both cases in one job.** The bench
   already runs that shape: `runtime_candidate` alternates a baseline against a
   named variant inside one dispatch, which cancels the machine.
4. **Read a distribution, not an average.** The owner ruled on 2026-09-15 that
   every draw is recorded with its processor, because the spread is the finding.
   A median over four machine types answers no question anybody has.
5. **A dossier names a machine per section, not per page.** `llama-bench` and the
   server case are separate jobs and the platform places each one on its own, so
   a single processor stamped at the top is wrong for half the numbers under it.
   A person caught that: the Gemma page said EPYC 7763 for readings taken on a
   9V74.
6. **Half of it is fixed in the tool, and the other half is still hand work.**
   The sweep records the processor it drew into `runtime-summary.json`, and the
   emitted `dossier.md` prints it in the prefill section that job produced. The
   Memory, Model load and Seconds-an-item sections still say only
   `ubuntu-latest`, so the server job's machine has to be read out of the
   `hardware.txt` inside `bench-server-baseline`. That is how the four rows above
   were built.

## The records behind this page

Every run id in the tables above is a GitHub Actions run in this repository. The
`bench-raw` artifact holds the `llama-bench` output and the `lscpu` dump of the
machine that job drew. `bench-server-baseline` holds the server job's own `lscpu`
dump, its `readings.json`, and the `dossier.md` the emitter wrote.

**An artifact expires 90 days after its run.** A figure that is not on this page
is a figure that stops existing on a date nobody chose.

## See also

- [../models.md](../models.md) - one row a model, and what each dossier holds.
- [what-a-bench-dispatch-costs.md](what-a-bench-dispatch-costs.md) - where a dispatch's 188.5 minutes go, and why cutting the non-model part buys almost nothing.
- [what-the-draft-head-is-worth.md](what-the-draft-head-is-worth.md) - the worked example of a difference two dispatches could not establish and one paired job settled.
- [../host-metrics.md](../host-metrics.md) - what every job now records about the machine it drew.
- [../models/gemma-4-e4b-qat.md](../models/gemma-4-e4b-qat.md) - Gemma's draws and what its draft head is worth.
- [../models/ornith-1.5-9b-q5km.md](../models/ornith-1.5-9b-q5km.md) - Ornith's draws.
- [../models/qwen3.5-9b-q4km.md](../models/qwen3.5-9b-q4km.md) - the incumbent's draws.
- [../pipeline-cost.md](../pipeline-cost.md) - the instrument log.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #10 (a number carries its hardware, date and spread).
