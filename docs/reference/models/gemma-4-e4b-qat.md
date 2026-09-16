# Gemma-4-E4B-it-qat-UD-Q4_K_XL

**Last Updated**: 2026-09-16
**Status: evaluated.** It has been benched and it has never served a published
item. `evaluated` is one of three words a dossier's status line may hold -
`evaluated`, `incumbent`, `superseded` - and this line is the only place this
model's lifecycle is written ([models.md](../models.md)).

One model, one page. Every figure below is a reading of **these weights**, it is
the only reading of that quantity in force, and it carries the hardware that took
it, the date and the spread. Nothing here was re-derived and nothing was rounded:
each figure is the one the instrument recorded, moved rather than restated.

**Where a quantity depends on which runner GitHub gave the job, the reading in
force is the spread across machines rather than one number.** That is still one
reading of one quantity - the quantity is what these weights do on the fleet we
actually get, and a single figure would answer a question nobody can ask, since
nothing selects the machine ([the processor
lottery](../benchmarks/the-processor-lottery.md), owner ruling 2026-09-15).

**This page says how fast, and it does not say how good.** The bench reads
throughput, memory and wall-clock. It does not grade a summary and it does not
decide whether this model publishes - that is the qualification case, which runs
separately and has not run against these weights. Read every number here as a
cost, never as a recommendation.

## Identity

`config/models/gemma-4-e4b-qat.json` is where these fields are declared. The
digest identifies the bytes the runtime opened; the repository revision
identifies the snapshot they came from and is pinned rather than a branch, so the
file, the alias, the revision and the expected digest move together or not at
all.

| Field | Value |
| --- | --- |
| Configuration id | `gemma-4-e4b-it-qat-ud-q4-k-xl` |
| Repository | `unsloth/gemma-4-E4B-it-qat-GGUF` |
| Repository revision | `8c5a9e4fd5482e2be20fe0bf013b4c262a8f4265` |
| Base repository | `google/gemma-4-E4B-it-qat-q4_0-unquantized` |
| File | `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` |
| Quantisation | `UD-Q4_K_XL` |
| SHA-256 | `df0fd4ee07072c607c29a0a1cb4f98918426cca12f45a2776bdd6ee6d09a4de3` |
| Bytes | 4,215,695,776 (3.93 GiB) |
| Architecture | `gemma4` - what llama.cpp reported when it loaded the file |
| Parameters | 7,463,013,674, as the loader counted them |

### The draft head

This entry declares a second file. The main model is quantisation-aware trained,
and the head speculates ahead of it so the runtime can accept more than one token
a step.

| Field | Value |
| --- | --- |
| File | `mtp-gemma-4-E4B-it.gguf` |
| SHA-256 | `423074e537504b4f9ec5eafed5c639fac82c96631626efccacdd3c4039b20605` |
| Bytes | 59,678,016 (56.9 MiB) |
| Speculation type | `draft-mtp` |
| Tokens drafted a step | 2 |

**`draft-mtp` is accepted by the pinned runtime, and that is recorded rather than
assumed.** Build `b10598` lists eleven values for `--spec-type`, and
`tests/fixtures/runtime/b10598-llama-server-help.txt` is the recorded help text a
test holds the contract against.

**It declares both halves or neither.** A draft entry naming a file with no
digest is refused before the download, by the daily run as well as by the two
bench workflows.

## Prefill and decode

llama.cpp `b10598` (`56db501e7`), 4 threads, 3 repeats, `llama-bench`. Prefill
falls as the prompt grows, so one tokens-per-second figure would be wrong at both
ends.

**`llama-bench` does not load the draft head**, so every reading here is the main
model decoding alone. What the head is worth is a different question, answered
further down.

**The reading is the spread across machines, not one number.** GitHub gives a job
whatever runner is free, and these weights have landed on three different
processors. A single figure would be a reading of one lucky draw rather than of
this model, so every draw is below with the machine that took it (owner ruling,
2026-09-15). What the fleet does to a number is
[the processor lottery](../benchmarks/the-processor-lottery.md).

| Processor | Draws | Prefill, 730 | Prefill, 1,800 | Prefill, 4,850 | Decode, 250 |
| --- | --- | --- | --- | --- | --- |
| AMD EPYC 7763 64-Core | 4 | 20.466 to 20.564 | 20.137 to 20.228 | 19.532 to 19.622 | 9.676 to 10.532 |
| AMD EPYC 9V45 96-Core | 2 | 74.637 to 75.453 | 73.033 to 74.926 | 69.929 to 71.377 | 15.516 to 15.744 |
| Intel Xeon Platinum 8573C | 1 | 59.322 +/- 0.348 | 55.483 +/- 0.238 | 51.433 +/- 0.174 | 10.212 +/- 0.019 |

All figures are tokens a second. A row with more than one draw shows the range
across them; the one-draw row shows that draw's own spread.

**Which machine a run draws is worth more than any model choice.** Reading is 3.7
times faster on the 9V45 than on the 7763 - the same weights, the same build, the
same prompt. **So no figure on this page may be compared with a figure on another
model's page unless both carry the same processor.**

Two rows are worth reading twice. **Prefill on the 7763 repeats to within half a
percent across four draws, and decode on the same four spans 8.8 percent** - so a
decode difference under 8.8 percent cannot be shown by comparing two runs. And
the Xeon reads 2.9 times faster than the 7763 while decoding at the same speed,
which is why a fast runner is not a thing.

## Memory

Sampled once a second across 3 repeats on `ubuntu-latest`, against the 16 GB the
runner has. What this does NOT split is anonymous from file-backed pages, so it
cannot say how much of the peak a second process would have to compete for.

| Reading | Value | Runs |
| --- | --- | --- |
| Peak resident set, `llama-server` plus the draft head | **8.786 +/- 0.002** GiB | n = 3 |

That is 55 percent of the runner's 16 GB. The weights on disk are 3.93 GiB, so
most of this peak is the 64K context window rather than the model.

### Model load time

Cold is the first server start of the job, with the page cache holding none of
the weights. Warm is every start after it. Both numbers include loading the draft
head.

| Reading | Value | Runs |
| --- | --- | --- |
| Cold, the first start of the job | **5,023** ms | n = 1, spread unavailable |
| Warm, every start after it | **5,002 +/- 0** ms | n = 2 |

## Seconds an item

Five articles, 3 repeats, on `ubuntu-latest`, **AMD EPYC 7763 64-Core
Processor**, with the draft head loaded and the pipeline's own two-call path.

| Reading | Value | Runs |
| --- | --- | --- |
| A summarize call, median | **804.8 +/- 4.5** s | n = 3 |
| A summarize call, longest | **942.8 +/- 6.2** s | n = 3 |
| A whole repeat, five articles | **3,988 +/- 28** s | n = 3 |

**These three readings come from a run the bench itself rejected**, and they are
published with that label rather than left out. The bench refuses a comparison
whose inputs moved, and two of the five articles were edited by their publishers
between the first repeat and the second - over a 3.3-hour run, that is ordinary.
The timings stand because each repeat is a complete pass over whatever text it
fetched, and the three totals agree to within 1.4 percent. What the rejection
correctly forbids is reading them against another run's.

## What the draft head is worth

**The head is 6.3 percent faster, and it changes every summary.** Both halves of
that sentence come from one paired dispatch, run `35011578538` on 2026-09-15, on
an AMD EPYC 7763. The two configurations alternated inside that one job, so the
machine is cancelled and the comparison holds.

| Case | A whole repeat over five articles, median | Spread over 2 repeats |
| --- | --- | --- |
| With the `draft-mtp` head | 2,937,218 ms | +/- 13,131 |
| With no draft head | 3,122,864 ms | +/- 6,409 |

The head saves **185,646 ms, which is 3 minutes 6 seconds over five articles, or
6.3 percent.** The gap is fourteen times the wider of the two spreads, so it is
not noise.

**An earlier attempt could not establish this and was right not to try.** Two
separate dispatches put the cases on different processors and differed by 5.3
percent, which sits under the 8.8 percent that two runs on one processor model
differ by anyway ([the processor
lottery](../benchmarks/the-processor-lottery.md)). The instrument that answered
it was the paired case, and it is the only shape that can.

### The head is not free: it changes the output

The bench refused this dispatch, with `rejected_output_drift`, and the refusal is
the more important half of the result. **All five articles got a different
summary with the head than without it.**

Sampling is deterministic here, which is what makes that a finding rather than
noise: each case reproduced its own five summaries byte-identically across both
its repeats, and the two cases disagreed on all five.

A speculative decoder that accepts a draft token only when it matches what the
main model would have produced is output-identical by construction. **This one is
not, so `draft-mtp` on this build is doing something other than lossless
speculation.** Whether that is the head, the acceptance rule or the pinned build
is unmeasured.

**What it means for adoption: the 6.3 percent is not a free speedup, it is a
different model.** The head cannot be switched on after qualification and it
cannot be switched off after it - whichever configuration is qualified is the one
that has to publish.

## What this page still owes

- **The qualification verdict.** Nothing here says the model writes a faithful
  summary. Until the qualification case has run, this model may not be adopted.
- **The licence row.** Gemma ships under its own terms rather than an SPDX
  identifier, and nobody has read them against this project's use yet.
- **The tokenizer cost.** Tokens a word decides how much article fits the window,
  and it belongs to this tokenizer rather than to the incumbent's.
- **Why the draft head changes the output.** The section above establishes that it
  does. Whether the cause is the head, the acceptance rule or the pinned build is
  unmeasured, and it decides whether a lossless configuration exists at all.

## The records behind this page

| What | Where |
| --- | --- |
| Every prefill and decode draw, with its processor | [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) |
| The wall-clock and memory readings above | GitHub Actions run `34972996987`, 2026-09-15 |
| The paired draft-head case | GitHub Actions run `35011578538`, 2026-09-15 |
| The recorded `--spec-type` list the pinned build accepts | `tests/fixtures/runtime/b10598-llama-server-help.txt`, from run `34971210901` |
| The declared identity | `config/models/gemma-4-e4b-qat.json` |

## See also

- [../models.md](../models.md) - one row a model, and what the status word means.
- [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) - what machine a run draws, and what it does to a reading.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - how a candidate gets measured and what has to pass before it serves.
- [../measurements.md](../measurements.md) - the instrument log.
