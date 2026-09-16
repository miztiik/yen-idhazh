# What processor a run draws, and what it does to a reading

**Last Updated**: 2026-09-16

GitHub gives a job whatever machine is free. This page is the record of what that
choice is worth, measured over thirteen bench dispatches between 2026-08-23 and
2026-09-16.

**The short answer: it is worth more than any difference between our candidate
models.** The same weights, the same llama.cpp build and the same synthetic
prompt read 3.7 times faster on one machine than on another. So a throughput
number quoted without its processor is not a reading, and two models compared
across two runs have not been compared at all.

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

## The four machines GitHub has given us

| Processor | Draws | What it is |
| --- | --- | --- |
| AMD EPYC 7763 64-Core | 7 | Milan, the one we draw most |
| AMD EPYC 9V45 96-Core | 2 | Genoa, the fastest at reading |
| AMD EPYC 9V74 80-Core | 2 | Genoa, and it reads like the Milan |
| Intel Xeon Platinum 8573C | 2 | Emerald Rapids, fast at reading and slow at writing |

Nothing selects between them and nothing ever will. `ubuntu-latest` is one label
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

## What it does not settle

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
