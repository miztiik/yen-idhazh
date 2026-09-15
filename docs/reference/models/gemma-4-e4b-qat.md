# Gemma-4-E4B-it-qat-UD-Q4_K_XL

**Last Updated**: 2026-09-15
**Status: evaluated.** It has been benched and it has never served a published
item. `evaluated` is one of three words a dossier's status line may hold -
`evaluated`, `incumbent`, `superseded` - and this line is the only place this
model's lifecycle is written ([models.md](../models.md)).

One model, one page. Every figure below is a reading of **these weights**, it is
the only reading of that quantity in force, and it carries the hardware that took
it, the date and the spread. Nothing here was re-derived and nothing was rounded:
each figure is the one the instrument recorded, moved rather than restated.

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

Measured 2026-09-15 on **AMD EPYC 7763 64-Core Processor**, 4 threads,
llama.cpp `b10598` (`56db501e7`), 3 repeats, `llama-bench`. Prefill falls as the
prompt grows, so one tokens-per-second figure would be wrong at both ends.

**`llama-bench` does not load the draft head**, so these four readings are the
main model decoding alone. What the head is worth is a different question and
this page does not answer it - see below.

| Reading | Value | Runs |
| --- | --- | --- |
| Prefill, 730-token prompt | **20.564 +/- 0.035** tok/s | n = 3 |
| Prefill, 1,800-token prompt | **20.228 +/- 0.017** tok/s | n = 3 |
| Prefill, 4,850-token prompt | **19.570 +/- 0.037** tok/s | n = 3 |
| Decode, 250 tokens | **9.676 +/- 0.083** tok/s | n = 3 |

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

## What the draft head is worth: not measured

A second dispatch of the same weights with `draft` set to null ran 5 seconds
later on 2026-09-15. It is not on this page as a comparison, and the reason is
the instrument rather than the result.

| Case | Processor | A whole repeat, median |
| --- | --- | --- |
| With the `draft-mtp` head | AMD EPYC 7763 | 3,970 s |
| With no draft head | AMD EPYC 9V74 | 4,192 s |

**GitHub put the two cases on different processors, so the 5.3 percent between
them is not attributable to the head.** The size of the confound is measurable
and was measured: the same `llama-bench` decode test, on the same weights, on
two machines both reporting EPYC 7763, differed by 8.8 percent between these two
runs - 9.676 against 10.532 tok/s. A 5.3 percent difference read across two runs
sits under an 8.8 percent between-run spread, so this pair says nothing.

**The instrument that could answer it is a paired case**: both configurations
alternating inside one job, on one machine, which cancels the machine. The bench
already runs that shape - `runtime_candidate` alternates a baseline against a
named variant - but every variant it offers today is an `inference` knob, and the
draft head is a sibling of `inference` rather than a knob inside it. No second
download is needed, because both cases open the same weights file.

Until that runs, this project has no reading of what the draft head is worth, and
none may be quoted.

## What this page still owes

- **The qualification verdict.** Nothing here says the model writes a faithful
  summary. Until the qualification case has run, this model may not be adopted.
- **The licence row.** Gemma ships under its own terms rather than an SPDX
  identifier, and nobody has read them against this project's use yet.
- **The tokenizer cost.** Tokens a word decides how much article fits the window,
  and it belongs to this tokenizer rather than to the incumbent's.
- **What the draft head is worth**, per the section above.

## The records behind this page

| What | Where |
| --- | --- |
| The bench dispatch behind every reading above | GitHub Actions run `34972996987`, 2026-09-15 |
| The no-draft case quoted and set aside | GitHub Actions run `34973005911`, 2026-09-15 |
| The recorded `--spec-type` list the pinned build accepts | `tests/fixtures/runtime/b10598-llama-server-help.txt`, from run `34971210901` |
| The declared identity | `config/models/gemma-4-e4b-qat.json` |

## See also

- [../models.md](../models.md) - one row a model, and what the status word means.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - how a candidate gets measured and what has to pass before it serves.
- [../measurements.md](../measurements.md) - the instrument log.
