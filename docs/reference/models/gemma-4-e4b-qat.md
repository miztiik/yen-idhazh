# Gemma-4-E4B-it-qat-UD-Q4_K_XL

**Last Updated**: 2026-09-19
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

## Sampling: what we set, against what the publisher asks for

Read on 2026-09-19 from the repository this entry pulls,
[unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF#best-practices)
at revision `8c5a9e4fd548`, which reproduces Google's card in full. The
publisher's own is
[google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it#best-practices).
**Gemma publishes one recipe and says to use it everywhere** - verbatim,
*"Use the following standardized sampling configuration across all use
cases"*. There is no task-specific variant to argue we fall under.

| | temperature | top_p | top_k |
| --- | ---: | ---: | ---: |
| The card, all use cases | 1.0 | 0.95 | 64 |
| **both `gemma-4-e4b-qat*.json` entries** | **0.2** | **1.00** | unset |

**This is the widest gap of the three candidates.** Qwen and Ornith each publish
a low-temperature variant at 0.6; Gemma publishes 1.0 and nothing else. The
owner pinned 0.2 across every committed entry on 2026-09-17
([../../architecture/contracts/determinism.md](../../architecture/contracts/determinism.md)),
which is a decision on the record - but nobody has read this model at 1.0
against 0.2 on one corpus, so what the gap buys or costs is unmeasured.

**Thinking is a system-prompt token here, not a sampler setting.** The card:
thinking is enabled by including `<|think|>` at the start of the system prompt,
and the reply is then `<|channel>thought\n` ... `<channel|>` before the answer.
Both entries pin `thinking_close: "<channel|>"`, which is that closing token, so
this repository is configured to expect a thinking span from these weights.

**E4B behaves differently from its siblings when thinking is off**, and the card
is explicit: every Gemma 4 model *except* E2B and E4B still emits the tags with
an empty thought block. On E4B the tags simply do not appear. A test written
against another size's behaviour would be wrong here.

**One recorded number is consistent with the span being where the tokens go.**
On 2026-09-17 this model spent a median 4,692 output tokens to publish a
110-word summary - 43 tokens a word, against Ornith's 6 - while the
`reasoning_leakage` gate passed with zero non-empty think blocks
([../benchmarks/four-candidates-on-one-news-day.md](../benchmarks/four-candidates-on-one-news-day.md)).
A correctly split thinking span would produce exactly that pair. **It is a
reading consistent with a hypothesis and not a measurement of one**: nothing has
counted the span's tokens directly, and a `captures-*` artifact from a run after
2026-09-18 would.

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
| AMD EPYC 7763 64-Core | 6 | 20.433 to 20.564 | 20.137 to 20.228 | 19.532 to 19.622 | 9.676 to 10.532 |
| AMD EPYC 9V45 96-Core | 3 | 73.595 to 75.453 | 72.198 to 74.926 | 68.082 to 71.377 | 15.014 to 15.744 |
| Intel Xeon Platinum 8573C | 1 | 59.322 +/- 0.348 | 55.483 +/- 0.238 | 51.433 +/- 0.174 | 10.212 +/- 0.019 |

All figures are tokens a second. A row with more than one draw shows the range
across them; the one-draw row shows that draw's own spread.

**Which machine a run draws is worth more than any model choice.** The prefill
median is 3.6 times higher on the 9V45 than on the 7763 - the same weights, the
same build, the same prompt. **So no figure on this page may be compared with a
figure on another model's page unless both carry the same processor.**

Two rows are worth reading twice. **Prefill on the 7763 repeats to within 0.6
percent across six draws, and decode on the same six spans 8.8 percent** - so a
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

**It changes what the model writes, at every drafted depth, and whether it is
faster is unmeasured.** The output finding comes from dispatches where every
configuration alternated inside one job, so the machine cancels - which it has
to, because the platform places each job separately and a comparison across two
dispatches says nothing.

**`n_max` is not the control.** The vendor's own documented `--spec-draft-n-max
4` changes the words exactly as much as a depth of 1 does, so the difference
between their setting and ours never explained the drift. No depth is
output-identical to the head being off, on six articles of six across two
processor models, with every case reproducing itself byte-identically at
`temperature: 0`.

**There is no speedup figure here, and the 6.3 percent that circulated is
withdrawn.** The head
changes how much text gets written - on one article it wrote 3.4 times as much -
so a wall clock against head-off is timing two different jobs rather than
measuring a rate. Two runs on one processor model then disagree about the sign:
one is 17 percent faster, the other 40 percent slower. The acceptance rate the
server already publishes at `/metrics` is the reading that would settle it, and
no run has recorded it.

**What follows from it: the head is not a speed setting, it is a different
model.** Whichever configuration is qualified is the one that has to publish.

Every dispatch, the timings, the digest tables and the summaries a person can
now read are in [what the draft head is
worth](../benchmarks/what-the-draft-head-is-worth.md).

## What this page still owes

- **The qualification verdict.** Nothing here says the model writes a faithful
  summary. Until the qualification case has run, this model may not be adopted.
- **The licence row.** Gemma ships under its own terms rather than an SPDX
  identifier, and nobody has read them against this project's use yet.
- **The tokenizer cost.** Tokens a word decides how much article fits the window,
  and it belongs to this tokenizer rather than to the incumbent's.
- **Why the draft head changes the output.** Narrowed on 2026-09-19 and still
  open. It is not the drafted depth, not the prompt and not the sampler - each
  is excluded by a control in the run. What is left is the acceptance rule or
  this pinned llama.cpp build, and the same corpus on a second build is the
  instrument that would tell those two apart. It decides whether a lossless
  configuration exists at all.
- **What the head costs or saves.** Withdrawn rather than answered: the two
  configurations write different amounts of text, so the wall clock is not a
  rate. A run at fixed output length recording the draft acceptance rate is the
  instrument.

## The records behind this page

| What | Where |
| --- | --- |
| The publisher's sampling recipe and the MTP claim, read 2026-09-19 | [unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF#best-practices), the repository this entry pulls |
| What the draft head is worth, every dispatch behind it | [../benchmarks/what-the-draft-head-is-worth.md](../benchmarks/what-the-draft-head-is-worth.md) |
| Every prefill and decode draw, with its processor | [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) |
| The wall-clock and memory readings above | GitHub Actions run `34972996987`, 2026-09-15 |
| The paired draft-head case | GitHub Actions runs `35439286272`, `35439298708` and `35439309256`, 2026-09-19 |
| The recorded `--spec-type` list the pinned build accepts | `tests/fixtures/runtime/b10598-llama-server-help.txt`, from run `34971210901` |
| The declared identity | `config/models/gemma-4-e4b-qat.json` |

## See also

- [../models.md](../models.md) - one row a model, and what the status word means.
- [../benchmarks/four-candidates-on-one-news-day.md](../benchmarks/four-candidates-on-one-news-day.md) - both configurations of this model beside two others on 2026-09-17, and the token cost per published word that run found. No row moved here from it: the corpus was too thin to rank anything.
- [../benchmarks/the-processor-lottery.md](../benchmarks/the-processor-lottery.md) - what machine a run draws, and what it does to a reading.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - how a candidate gets measured and what has to pass before it serves.
- [../pipeline-cost.md](../pipeline-cost.md) - the instrument log.
