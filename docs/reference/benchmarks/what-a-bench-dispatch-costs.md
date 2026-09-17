# What a bench dispatch costs

**Last Updated**: 2026-09-17

Where the time in a bench dispatch goes, and whether any of it is a slow path
worth fixing.

**The answer in one sentence: 98 percent of it is the model, split almost exactly
in half between reading the prompt and writing the answer, and there is no slow
path hiding anywhere.**

## What was measured

The `runtime` job of run `35086403868`: **161.0 minutes on an AMD EPYC 7763,
2026-09-16.** Warm cache, 3 repeats, 5 articles, Gemma 4 E4B.

Every figure below comes from one of three places - GitHub's own job and step
timestamps, the `runtime-summary.json` inside each `bench-server-*` artifact, and
the `prompt eval time` and `total time` lines llama-server writes into
`baseline-N.llama-server.log`.

Two words carry most of the page. **Prefill** is the model reading the prompt.
**Decode** is the model writing the answer.

## Where the 161.0 minutes went

| Phase | Wall-clock | Share | Measured or estimated |
| --- | ---: | ---: | --- |
| Provisioning, checkout, Python, editable install | 0.41 min | 0.25% | measured |
| Cache restore, 4.28 GB of weights plus runtime | 0.73 min | 0.45% | measured |
| SHA-256 verify, twice over 4.28 GB | 0.12 min | 0.07% | measured |
| Build the fixed five-article corpus | 1.73 min | 1.07% | measured |
| Model load, 3 server starts at 5.0 s each | 0.25 min | 0.16% | measured |
| Fetch the five articles, 3 times | 0.16 min | 0.10% | measured |
| Extract and sanitize, 3 times | 0.01 min | 0.01% | measured |
| **Prefill**, 29,768 evaluated prompt tokens a repeat at 19.20 tok/s | **77.55 min** | **48.2%** | measured |
| **Decode**, 12,691 generated tokens a repeat at 7.94 tok/s | **79.77 min** | **49.5%** | measured |
| Emit the dossier, upload artifacts | 0.07 min | 0.04% | measured |
| Python between calls, unattributed | 0.13 min | 0.08% | derived |

The last row is what the job's wall clock has left over once every measured phase
is subtracted. It is labelled derived rather than measured because nothing timed
it directly.

## The three things it says

### Ninety-eight percent of the job is the model

Prefill is 48.2 percent and decode 49.5 percent, so the two halves sit within 1.3
points of each other. **Everything else adds to 3.61 minutes of 161.0 - 2.2
percent** - and the largest single line in that 3.61 is building the corpus, at
1.73 minutes. The wall-clock column and the share column agree on both figures.

So there is nothing to tune outside the model. Halving every other phase in the
table would return 1.8 minutes of a 161-minute job, which is about 1 percent.
**The only lever that moves this job is the number of tokens the model reads and
writes.**

### The prompt cache already pays for itself

The five articles present **48,305 logical prompt tokens**. The server evaluates
**29,768**, because the shared prefix - the instructions in front of every
article - stays in the key-value cache between calls rather than being read
again.

**That is 38.4 percent of prefill already free**, and prefill is half the job, so
the cache is worth about 19 percent of the whole dispatch. It needs no
configuration and it is already on.

### The truncation cap never bound

`truncation_cap_tokens` is **20,000** in `config/idhazh.json`. The dearest of the
five articles presented **12,585** tokens, which is 63 percent of the cap.

So the cap did not cut anything in this dispatch, and lowering it to 12,000 would
be the first change that did. It is not a throughput lever at its current value
and no figure on this page is a reading of it.

## The four dispatches of 2026-09-16

All four were dispatched at 10:42 UTC with a warm cache, 3 repeats and the same
5 articles.

| Run | Model | `llama-bench` job processor / `runtime` job processor | `llama-bench` job | `runtime` job | Dispatch |
| --- | --- | --- | ---: | ---: | ---: |
| `35086403868` | Gemma 4 E4B | EPYC 7763 / EPYC 7763 | 26.7 min | 161.0 min | 188.5 min |
| `35086407071` | Gemma 4 E4B | EPYC 9V45 / EPYC 7763 | 9.1 min | 160.6 min | 170.6 min |
| `35086409972` | Gemma 4 E4B | EPYC 7763 / Xeon 8573C | 27.2 min | 85.5 min | 113.6 min |
| `35086412536` | Ornith 1.5 9B Q5_K_M | EPYC 7763 / EPYC 9V74 | 87.6 min | 199.5 min | 287.8 min |

**The Ornith row is not comparable to the other three.** It is a different and
larger model - 6.64 GB with no draft head, against Gemma's 4.22 GB plus a 57 MiB
draft head - so its wall clock differs by the weights as well as by the machine.

Each dispatch runs about 0.7 to 0.9 minutes longer than its two jobs added
together. That gap is the queue between them.

**Two jobs, two machines.** Three of these four put the `llama-bench` job and the
`runtime` job on different processors. What that does to a reading is [the
processor lottery](the-processor-lottery.md), and it is the reason this page
names a processor per job rather than per dispatch.

**What the speed case is worth skipping.** Those four `llama-bench` columns are
9.1, 26.7, 27.2 and 87.6 minutes against whole dispatches of 170.6, 188.5, 113.6
and 287.8 - between a tenth and a third. That is the size of what
`bench.run_model_speed_case` and the `model_speed_case` dispatch input buy back
when somebody is exercising the flow rather than measuring a model
([github-actions.md](../github-actions.md#design-rationale)). The job was keyed
`llm` until 2026-09-17; older run pages show that name.

## Two readings about the instrument itself

### Repeats inside one job are almost noise-free

The three repeats of `35086403868` took 3,158.2, 3,156.1 and 3,155.3 seconds.
**They agree to 0.09 percent**, a spread of 2.9 seconds on about 3,157.

That is the case for pairing. A difference of any size can be established inside
one job at n = 3, where the same difference read across two dispatches is buried
by the machine.

### Caching the weights is worth 0.6 percent of a dispatch, which is far less than it looks

A cache restore of 4.28 GB measured **0.63 to 1.58 minutes over eight `runtime`
jobs between 2026-09-14 and 2026-09-16**. A cold download instead adds **57 to
338 seconds, median about 75**.

So the most the cache can ever save is the download it removes: 75 seconds of a
188.5-minute dispatch, which is **0.6 percent** - and that is an upper bound,
because the restore that replaces the download is not free. At a median draw the
restore (38 to 95 seconds) and the download (median 75 seconds) are within
seconds of each other, and the slowest restore measured is slower than the median
download.

**The cache is not on this workflow for speed.** What it is for, and the ceiling
it competes for, are in [ci-caches.md](../ci-caches.md).

## What this does not settle

- **Whether 161.0 minutes is what the next dispatch costs.** It is one job on one
  machine. The same corpus on a Xeon 8573C took 85.5 minutes in the same batch.
  The wall clock of a bench dispatch belongs to the machine that drew it.
- **What any of it costs a published digest.** This is a fixed five-article
  corpus chosen to be identical across dispatches, not a day's feeds.
- **Whether the prompt cache would still return 38.4 percent on a different
  prompt shape.** The figure is a property of how much of the prompt is shared,
  and this corpus has one instruction block in front of five articles.

## The records behind this page

Every run id above is a GitHub Actions run in this repository. The phase
breakdown comes from `35086403868`'s job and step timestamps, its
`bench-server-baseline` artifact, and the llama-server logs inside it.

**An artifact expires 90 days after its run.** A figure that is not written down
here stops existing on a date nobody chose.

## See also

- [the-processor-lottery.md](the-processor-lottery.md) - why the two jobs of one dispatch are two readings, and what a comparison across dispatches costs.
- [what-the-draft-head-is-worth.md](what-the-draft-head-is-worth.md) - the paired-inside-one-job shape this page's repeat figure argues for.
- [../ci-caches.md](../ci-caches.md) - the weights cache, the 10 GB ceiling, and the rule a new cache has to clear.
- [../../architecture/summarize/throughput.md](../../architecture/summarize/throughput.md) - what prefill and decode cost the daily pipeline.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - how a bench dispatch is run and what it has to produce.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the runner budget) and Guardrail #10 (a number carries its hardware, date and spread).
