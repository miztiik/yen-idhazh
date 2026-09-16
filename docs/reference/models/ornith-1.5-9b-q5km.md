# Ornith-1.5-9B-Q5_K_M

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

`config/models/ornith-1.5-9b-q5km.json` is where these fields are declared. The
digest identifies the bytes the runtime opened; the repository revision
identifies the snapshot they came from and is pinned rather than a branch, so the
file, the alias, the revision and the expected digest move together or not at
all.

| Field | Value |
| --- | --- |
| Configuration id | `ornith-1-5-9b-q5-k-m` |
| Repository | `ornith-ai/Ornith-1.5-9B-GGUF` |
| Repository revision | `abdd624b12ebf020b767fff532ff44fe552b28c3` |
| Base repository | `ornith-ai/Ornith-1.5-9B` |
| File | `Ornith-1.5-9B-Q5_K_M.gguf` |
| Quantisation | `Q5_K_M` |
| SHA-256 | `e4d9634a3b6546a5c00a8680568fe1125f6c98c704ee51ae52ba07650fb4247d` |
| Bytes | 6,642,544,576 (6.19 GiB) |
| Architecture | `qwen35` - what llama.cpp reported when it loaded the file |
| Parameters | 9,197,093,888, as the loader counted them |

**The digest was observed, not copied.** The bench read it off the file the
runtime opened rather than out of config, which is what makes it evidence about
the bytes rather than a restatement of the setting.

**It declares no draft head.** Every decode figure below is this model decoding
on its own.

## Prefill and decode

llama.cpp `b10598` (`56db501e7`), 4 threads, 3 repeats, `llama-bench`. Prefill
falls as the prompt grows, so one tokens-per-second figure would be wrong at both
ends.

**The reading is the spread across machines, not one number.** These weights have
landed on two processors; every draw is below with the machine that took it
(owner ruling, 2026-09-15). What the fleet does to a number is [the processor
lottery](../benchmarks/the-processor-lottery.md).

| Processor | Draws | Prefill, 730 | Prefill, 1,800 | Prefill, 4,850 | Decode, 250 |
| --- | --- | --- | --- | --- | --- |
| AMD EPYC 7763 64-Core | 3 | 6.195 to 6.226 | 6.165 to 6.196 | 6.083 to 6.122 | 4.412 to 4.640 |
| AMD EPYC 9V74 80-Core | 1 | 6.374 +/- 0.008 | 6.355 +/- 0.010 | 6.293 +/- 0.013 | 4.696 +/- 0.004 |

All figures are tokens a second. The three-draw row shows the range across them;
the one-draw row shows that draw's own spread.

**Do not read the narrow range as a model that does not care what machine it
gets.** These four draws span 2.9 percent because **this model has only ever
drawn the two machines that read at the same speed as each other.** It has never
landed on a 9V45 or a Xeon, and both of those read other models three to four
times faster than the 7763 does. The range above is a gap in the sample.

**No figure here may be compared with a figure on another model's page unless
both carry the same processor.**

## Memory

Sampled once a second across 3 repeats on `ubuntu-latest`, against the 16 GB the
runner has. What this does NOT split is anonymous from file-backed pages, so it
cannot say how much of the peak a second process would have to compete for.
`Rss_Anon` and `Rss_File` from `/proc/<pid>/smaps_rollup`, sampled by the same
thread, would settle that; they are unmeasured today.

| Reading | Value | Runs |
| --- | --- | --- |
| Peak resident set, `llama-server` alone | **9.332 +/- 0.0003** GiB | n = 3 |

That is 58 percent of the runner's 16 GB, with the pipeline's own Python process
and the page cache still to fit beside it.

### Model load time

Cold is the first server start of the job, with the page cache holding none of
the weights. Warm is every start after it.

| Reading | Value | Runs |
| --- | --- | --- |
| Cold, the first start of the job | **5,018** ms | n = 1, spread unavailable |
| Warm, every start after it | **5,001 +/- 0** ms | n = 2 |

## Seconds an item

Five articles, 3 repeats, on `ubuntu-latest`, **AMD EPYC 9V74 80-Core
Processor**. There is no 95th percentile here: five articles cannot carry one.
The published ledger over a real day is what gives that number.

**This section's processor is not the one above it.** The two cases are separate
jobs and GitHub places each where it likes, so the throughput readings and these
wall-clock readings were taken on different silicon. That is recorded rather than
smoothed over, because a reader who assumes one machine would divide one by the
other.

| Reading | Value | Runs |
| --- | --- | --- |
| A summarize call, median | **452.7 +/- 0.5** s | n = 3 |
| A summarize call, longest | **922.2 +/- 4.6** s | n = 3 |
| A whole repeat, five articles | **2,573 +/- 15** s | n = 3 |

## What this page still owes

- **The qualification verdict.** Nothing here says the model writes a faithful
  summary. Until the qualification case has run, this model may not be adopted.
- **The licence row.** Every other dossier carries an SPDX identifier. This one
  does not, because nobody has read the repository's licence file yet.
- **The tokenizer cost.** Tokens a word decides how much article fits the
  window, and it belongs to this tokenizer rather than to the incumbent's.

## The records behind this page

| What | Where |
| --- | --- |
| Every prefill and decode draw, with its processor | [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) |
| The bench dispatch that took the wall-clock and memory readings | GitHub Actions run `34938565911`, 2026-09-15 |
| The declared identity | `config/models/ornith-1.5-9b-q5km.json` |

## See also

- [../models.md](../models.md) - one row a model, and what the status word means.
- [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) - what machine a run draws, and what it does to a reading.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - how a candidate gets measured and what has to pass before it serves.
- [../measurements.md](../measurements.md) - the instrument log.
