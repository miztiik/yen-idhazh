# What processor a run draws, and what it does to a reading

**Last Updated**: 2026-09-16T12:00

GitHub gives a job whatever machine is free. This page is the record of what that
choice is worth, measured over thirteen bench dispatches between 2026-08-23 and
2026-09-16.

**The short answer: it is worth more than any difference between our candidate
models.** The same weights, the same llama.cpp build and the same synthetic
prompt read 3.7 times faster on one machine than on another. So a throughput
number quoted without its processor is not a reading, and two models compared
across two runs have not been compared at all.

**And it is a lottery per JOB, not per run.** Twelve dispatches gave 24 job
placements, and **nine of the twelve split across two different processors
inside one run** - same commit, same dispatch, seconds apart. On 2026-09-15 four
dispatches inside 18 seconds produced eight placements across four machine types.
Nothing we control reaches that decision.

## What was measured

`llama-bench` from llama.cpp `b10598` (`56db501e7`), 4 threads, 3 repeats,
prompts of 730, 1,800 and 4,850 tokens and 250 generated tokens. Every dispatch
runs it against whichever weights that dispatch was pointed at, and records the
processor from `/proc/cpuinfo` in the same artifact.

This is a synthetic prompt rather than an article, which is the point: it is
identical in every run, so the only things that move between two rows are the
weights and the machine.

**The wall-clock readings in the model dossiers are not on this page and cannot
be added to it.** Each of those ran over five articles drawn from that day's
feeds, so two of them differ by their articles as well as their machine.

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

**The machine we draw most has no AVX-512 at all.** The EPYC 7763 took 13 of 24
placements and is the slowest at prefill. It is the machine most of our numbers
were taken on.

**Every one is two physical cores with two threads.** Core count is a constant
across the fleet. Only the instruction set and the cache change, which is why
those are the columns.

**BogoMIPS predicts nothing.** The highest number in the table belongs to a
machine that is not fast. It is recorded because it is the figure people reach
for first, and it is worth knowing that it is useless here.

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
| Gemma 4 E4B | AMD EPYC 9V45 | `34905960781` | 75.453 +/- 0.147 | 15.516 +/- 0.086 |
| Gemma 4 E4B | AMD EPYC 9V45 | `34941400155` | 74.637 +/- 0.192 | 15.744 +/- 0.056 |
| Gemma 4 E4B | Intel Xeon 8573C | `35011547415` | 59.322 +/- 0.348 | 10.212 +/- 0.019 |
| Ornith 1.5 9B | AMD EPYC 7763 | `34901484508` | 6.226 +/- 0.001 | 4.412 +/- 0.030 |
| Ornith 1.5 9B | AMD EPYC 7763 | `34938565911` | 6.195 +/- 0.004 | 4.538 +/- 0.011 |
| Ornith 1.5 9B | AMD EPYC 9V74 | `35011557915` | 6.374 +/- 0.008 | 4.696 +/- 0.004 |
| Qwen3.5 9B | AMD EPYC 7763 | `35011568497` | 10.047 +/- 0.006 | 5.985 +/- 0.028 |
| Qwen3.5 9B | AMD EPYC 9V74 | 2026-08-23 | 10.14 +/- 0.01 | 6.01 +/- 0.11 |
| Qwen3.5 9B | Intel Xeon 8573C | `34812096911` | 39.653 +/- 0.371 | 3.906 +/- 0.019 |

Seven of these thirteen dispatches had their server case fail. The `llama-bench`
job succeeded in every one, so a failed dispatch still contributes its row here -
which is why this page has thirteen and the dossiers have fewer.

## What it settles

### The machine is worth more than the model

Gemma reads at 20.5 tokens a second on the EPYC 7763 and 75.0 on the EPYC 9V45.
**That is 3.7 times, from nothing but which machine was free.** Qwen3.5 reads at
10.0 on the EPYC 7763 and 39.7 on the Xeon - 3.9 times.

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

Four Gemma draws landed on an EPYC 7763. Their prefill readings span **half a
percent**, 20.466 to 20.564. Their decode readings span **8.8 percent**, 9.676 to
10.532 - seventeen times wider, on the same weights and the same reported
processor.

The spread inside a single run does not show this: each of those four reported a
decode spread under 0.1 tokens a second and then disagreed with its siblings by
0.86. **A spread computed inside one run is a reading of that run, not of the
instrument.** Two runs on the same processor model are still two machines, and
`/proc/cpuinfo` cannot tell them apart.

What this costs, concretely: a decode difference smaller than 8.8 percent cannot
be established by comparing two runs, however tight each one looks. It needs both
cases inside one job. [The Gemma dossier's draft-head
section](../models/gemma-4-e4b-qat.md#what-the-draft-head-is-worth) is the worked
example - a 5.3 percent difference that two runs could not establish and one
paired run settled.

### Ornith's narrow range is a gap in the sample, not a property

Ornith's three draws span 2.6 percent, which looks like a model that does not
care what machine it gets. It is not. **Ornith has only ever drawn the EPYC 7763
and the EPYC 9V74, which are the two machines that read at the same speed as each
other.** It has never met a 9V45 or a Xeon.

This is the trap the whole page exists to name: a narrow range over an unlucky
sample looks exactly like a narrow range over a representative one.

## The hypotheses, and what would settle each

Everything in this section is a guess with a measurement attached. None of it is
established, and a row here may not be quoted as a finding. It is written down so
the next person spends their runner time on the question that is still open
rather than on one somebody already closed.

### H1. The instruction set is what moves prefill

The EPYC 7763 has no AVX-512 and reads Gemma at 20.5 tokens a second. The EPYC
9V45 has AVX-512 with bf16 and reads it at 75.0. That is the biggest single
correlation in the table and it has an obvious mechanism: llama.cpp picks a
different kernel when the wider instructions are there.

**What would settle it:** the same weights on one machine with the wider kernels
switched off at build time. llama.cpp can be compiled without them, so this is
one bench dispatch against two binaries on one host - a paired case, which is the
only shape that cancels the machine.

**What already argues against a simple version of it:** H2.

### H2. The flag says the instruction exists, not how fast it runs

The 9V74 and the 9V45 both report `avx512f` and `avx512_bf16`. Qwen reads at 10.1
on the 9V74 and Gemma reads at 75.0 on the 9V45. If the flag alone decided it,
those two machines would behave alike and they do not.

The only difference either host reports is the family number, 25 against 26. A
processor can implement a wide instruction on a narrower datapath and run it in
two passes - the flag is still true and the throughput is half.

**What would settle it:** one model, benched on a 9V74 and a 9V45. We have never
run the same weights on both, so the comparison does not exist yet. Until it
does, H1 and H2 are indistinguishable from our data.

### H3. Decode is bandwidth bound and nothing we recorded measured bandwidth

Prefill swings by 3.7 times across the fleet; decode swings by 1.6. Prefill works
on a whole prompt at once and is limited by arithmetic. Decode produces one token
at a time and is limited by how fast weights stream out of memory. That would
explain why the Xeon 8573C reads Qwen 3.9 times faster and writes it 35 percent
slower.

**What would settle it:** a memory-bandwidth figure beside every throughput
figure. **This one is now instrumented**: every job records a large-block copy
rate, so the next several runs build the scatter this needs
([telemetry.md](../../concepts/telemetry.md)).

### H4. L3 size is why the two Intel parts read fast

The Xeon 8573C reports 260 MiB of L3 and the 6973P-C reports 480 MiB, against 32
MiB on every AMD part. A prompt's weights working set may fit in the larger cache
and not in the smaller.

**What would settle it:** the bandwidth probe at two sizes, one below the
reported L3 and one above. The gap between them is the cache effect, measured on
the machine rather than argued from a datasheet. The probe already records the
buffer size it used, so this is a config change and no code.

### H5. A pooled machine is slower than a fresh one

A runner handed to us after other work may have a cold page cache, a warm one, or
a noisy neighbour. Nothing we have recorded could tell those apart.

**What would settle it:** uptime at the moment the job starts, against the
throughput that job produced. **Now instrumented** - every fingerprint row
carries how long the machine had been up.

### H6. Placement follows something we could read

The placement is per job and resolves in seconds, which rules out anything we
control. But the platform names its own decision - a machine size, a region, a
zone, a fault domain - and we have never asked for any of it.

**What would settle it:** the instance metadata service, which every job now
queries. If the pools turn out to be separable by size or region, "a lottery"
becomes "which pools we draw from", and that is a different conversation.

## What could be done about it, and what each costs

| Approach | Cost | What it buys |
| --- | --- | --- |
| Probe in one job, gate the expensive job on the result | one short job a dispatch | **nothing** - the expensive job is a different job and draws again. Nine of twelve is the measurement that refuses this |
| Self-probe: the working job reads its own processor first and exits early on a slow one | about a minute a rejected dispatch | the same machine it probed, so this one works |
| `ubuntu-24.04-arm` | one bench dispatch to find out | the only label that genuinely selects hardware, and free on public repositories |
| Larger runners | billed, including on a public repository | pins a machine family, against this project's constraints (Guardrail #2) |
| Accept it, and pair every comparison inside one job | nothing | comparison is already solved this way; only the wall clock still pays |

**The self-probe is the only one of these that works, and it is not recommended
for the daily run.** Burning dispatches to chase a machine is reasonable for a
bench somebody runs twice. As a standing part of the publishing path it is a
retry loop that makes a run non-deterministic and hides a capacity problem behind
a retry.

- **Which machine we will draw next.** Thirteen draws over four machine types is
  not a distribution anybody should quote a probability from. The counts in the
  table above are what happened, not a rate.
- **Whether two machines reporting the same model string are the same machine.**
  The 8.8 percent decode spread across four EPYC 7763 draws says they are not,
  and says nothing about why - host load, memory population and silicon stepping
  are all unmeasured here.
- **What any of this costs a published digest.** These are synthetic prompts. The
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

## The records behind this page

Every run id in the table above is a GitHub Actions run in this repository,
holding a `bench-raw` artifact with the `llama-bench` output and the
`/proc/cpuinfo` line beside it.

## See also

- [../models.md](../models.md) - one row a model, and what each dossier holds.
- [../models/gemma-4-e4b-qat.md](../models/gemma-4-e4b-qat.md) - Gemma's draws and what its draft head is worth.
- [../models/ornith-1.5-9b-q5km.md](../models/ornith-1.5-9b-q5km.md) - Ornith's draws.
- [../models/qwen3.5-9b-q4km.md](../models/qwen3.5-9b-q4km.md) - the incumbent's draws.
- [../measurements.md](../measurements.md) - the instrument log.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #10 (a number carries its hardware, date and spread).
