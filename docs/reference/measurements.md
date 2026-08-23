# Measurements

**Last Updated**: 2026-08-23

Every number this project's design rests on, with the hardware it was taken on,
the date, and the spread. Holy Law #10 in one page: **an unmeasured number is
labelled an estimate and may not be used to justify a design.**

Two rules govern this page:

- A figure is either **measured** - and then it carries hardware, date and
  spread - or it is listed under [Still unmeasured](#still-unmeasured) with the
  measurement that would settle it. There is no third category.
- **A laptop measures the laptop.** Every figure below taken on an i7-1265U is
  an order-of-magnitude check, not a runner figure. The runner has a different
  core topology, different memory bandwidth, and a shared host. Nothing here
  substitutes for `.github/workflows/measure.yml` running on `ubuntu-latest`.

## Inference throughput

`llama-bench -m <model> -p 730,1800,4850 -n 250 -t 4`, at the three input
lengths a short, medium and long article actually produce.

### On the runner (authoritative)

**Measured 2026-08-22** on `ubuntu-latest`: AMD EPYC 9V74 80-Core, 4 threads,
llama.cpp `b10580`, 3 repeats. This is the hardware the pipeline runs on, so
these are the numbers a design decision may cite. The laptop tables below are
kept only to show how far a laptop misleads.

| Model | 730 tok | 1800 tok | 4850 tok | decode (250) |
| --- | --- | --- | --- | --- |
| Qwen3-4B-Q4_K_M | 22.1 +/- 0.2 | 20.8 +/- 0.0 | 17.1 +/- 0.1 | **13.00 +/- 0.03** |
| Qwen3-8B-Q4_K_M | 12.1 +/- 0.0 | 11.6 +/- 0.0 | 10.4 +/- 0.0 | **7.28 +/- 0.01** |

The spread collapsed against the laptop: stddev on the runner is 0.0-0.2 tok/s
where the laptop showed up to 4.49. A shared laptop with thermal throttling was
measuring its own scheduler as much as the model.

**The 8B is 1.8x slower to decode, not 3.3x.** The laptop's 3.3x was the
headline number behind "the 8B may not fit". On real hardware the gap is roughly
half that, and the 8B fits comfortably.

**Weight download, cache miss:** 4B 2.4 GB in 32s, 8B 4.7 GB in 180s. Both are
one-off per cache key; the 10 GB cache holds both.

### Derived seconds per article

Derived from the runner table by `backend/utilities/summarise_bench.py`, using
the **measured** length buckets in [Corpus shape](#corpus-shape). Derived, not
measured: they inherit both the throughput spread and the bucket error.

| Model | short | medium | long | blended | worst long |
| --- | --- | --- | --- | --- | --- |
| Qwen3-4B-Q4_K_M | 45s | 127s | 232s | **112s** | 363s |
| Qwen3-8B-Q4_K_M | 82s | 225s | 393s | **196s** | 597s |

The blended figures were first published as 128s and 196s -> corrected to 112s
and 196s when the bucket shares were replaced by the measured ones. A blended
number is a statement about a corpus; blending against a corpus that was
disproved the same day is arithmetic on a fiction.

**The shard timeout stays worst-case.** A 5-item shard drawing five long
articles on the 8B is 5 x 597s = 50 minutes. `digest.yml` sets 330 minutes,
which is generous - and a timeout should be. It must never be re-derived from
the 196s blend, which would set it at 17 minutes and kill healthy shards that
happened to draw long articles.

### On a laptop (kept only as a warning)

### Qwen3-4B-Q4_K_M

Hardware: Intel Core i7-1265U, 4 threads. Date: 2026-08-15. Repeats: 3.

| n_prompt | prefill tok/s | stddev |
| --- | --- | --- |
| 730 | 24.05 | 1.46 |
| 1800 | 18.35 | 4.49 |
| 4850 | 12.34 | 3.02 |
| decode (250) | 6.07 | 0.15 |

### Qwen3-8B-Q4_K_M

Hardware: Intel Core i7-1265U, 4 threads. Date: 2026-08-15. Repeats: 2.

| n_prompt | prefill tok/s | stddev | vs 4B |
| --- | --- | --- | --- |
| 730 | 9.30 | 0.80 | 2.6x slower |
| 1800 | 8.40 | 2.00 | 2.2x slower |
| 4850 | 6.30 | 0.30 | 2.0x slower |
| decode (250) | 1.84 | 0.17 | **3.3x slower** |

### Derived seconds per article, on the laptop

Superseded by the runner table above. Kept because the gap between the two is
the finding: this said the 8B cost 2.9x a short article, and the runner says
1.8x. Nothing here may be cited.
| bucket | 4B typical | 8B typical | multiple |
| --- | --- | --- | --- |
| short | 55 s | 160 s | 2.9x |
| medium | 131 s | 323 s | 2.5x |
| long | 435 s | 906 s | 2.1x |
| blended | 173 s | 399 s | 2.3x |

Worst case matters more than the blend for one decision: a single long article
on the 8B is 1223 s worst, so a five-URL shard that draws five long articles is
roughly 102 minutes. Job timeouts are set from that number, not from 399 s.

**Three findings that changed the design**, all of which contradicted an
estimate:

1. **Prefill tok/s degrades with context length** (24.1 -> 18.3 -> 12.3 on the
   4B). The estimate assumed a constant rate; attention is quadratic, so the
   long bucket came out 4.5x worse than predicted while short was only 1.9x
   worse. Any future length estimate has to model prefill as a function of
   context length.
2. **Decode degrades worse than prefill on the larger model** (3.3x against
   2.0x) despite roughly 2x the weights. Decode is memory-bandwidth-bound and
   4.68 GiB streams from RAM with no reuse, while prefill still gets arithmetic
   intensity from batching. Output length is therefore a first-class cost lever
   on the 8B: 250 tokens at 1.84 tok/s is 136 s of pure decode.
3. **Truncation is a performance lever, not only a safety cap.** Capping at
   2500 instead of 6000 input tokens takes a long 8B article from ~906 s to
   ~450 s and the blended figure from 399 s to ~308 s.

The stddev is ~25% of the mean at 1800 and 4850 tokens, which is thermal
throttling on a laptop. A shared-host runner may be better or worse; the CI run
must report its own spread rather than inherit this one.

## The summarizer prompt in tokens

**Measured 2026-08-23**, `llama-tokenize` against `Qwen3-8B-Q4_K_M.gguf` on a
developer machine, on the rendered prompt with LF line endings. Tokenization is
deterministic, so the spread is zero and the hardware does not matter - the
tokenizer does. A different model file gives a different count.

| Prompt | Words | Tokens |
| --- | --- | --- |
| Before the Title section | 653 | 864 |
| With the Title section | 781 | 1033 |
| **After the terseness pass** | **598** | **801** |

The terseness pass removed 183 words and **232 tokens, 22.5%**, without removing
a rule. What went was justification, restatement, and one line the decoder
already enforced. See
[../architecture/summarize/prompt.md](../architecture/summarize/prompt.md).

Against the 8192 `n_ctx` the pipeline runs at:

| Component | Tokens |
| --- | --- |
| System prompt | 801 |
| Article, at the 2500-token truncation cap | 2500 |
| Output budget | 900 |
| **Worst case** | **4201 of 8192** |

Three notes worth keeping:

- **Measure the prompt with the line endings the model is sent.** The same
  rendered prompt tokenizes at 801 with LF and 880 with CRLF - a 79-token, 10%
  difference from nothing but a file write. Python's default text mode
  translates on Windows, so a measurement taken that way overstates the prompt
  by a tenth.
- **The prompt is the cheap half.** *Derived*, not measured: 801 tokens of
  prefill at the runner's measured 12.1 tok/s is roughly 66 s, paid once per
  article regardless of the article's length. A rule that earns its place costs
  a few seconds; a rule that crowds out the article costs the whole long bucket.
- **`fits_context` over-reserves and does so on purpose.** It approximates the
  prompt as `words x 2`, which is 1196 against the measured 801. It errs by
  395 tokens in the safe direction, and the alternative - tokenizing the prompt
  per item to save context we are not short of - buys nothing.

## Weights on disk

Hardware: local filesystem. Date: 2026-08-21. Method: `stat`.

| File | Bytes | GiB |
| --- | --- | --- |
| `Qwen3-4B-Q4_K_M.gguf` | 2,497,280,256 | 2.33 |
| `Qwen3-8B-Q4_K_M.gguf` | 5,027,783,488 | 4.68 |
| both | 7,525,063,744 | 7.01 |

This is why the weights are cached rather than committed: GitHub hard-rejects
any file over 100 MB, and both files sit inside the 10 GB repository cache with
under 3 GB to spare.

## Published payload size

### Prose compression

Hardware: Intel Core i7-1265U. Date: 2026-08-20. Method: gzip over 32 prose
files, 276,887 B -> 94,690 B.

**2.92x.** This is the ratio the day-payload arithmetic uses.

### The day payload

Hardware: Intel Core i7-1265U. Date: 2026-08-21. Method: gzip level 9 over
`tests/fixtures/contracts/digest-day/two-runs.json`.

| Quantity | Value |
| --- | --- |
| Fixture day, 3 items | 3,650 B raw, 1,078 B gzipped (3.39x) |
| Per item, raw | 1,217 B |

**Read this as the contract's overhead, not as a production day.** The fixture
carries three items with short summaries, and gzip over 3.6 KB has barely
warmed its dictionary. It replaces the earlier ~2.2 KB-per-item estimate as an
order-of-magnitude check on the *shape*; a real 17-item day is measured after
the first pipeline run, not before it.

### Days to the 1 GB Pages ceiling

Derived from the above plus the image estimates below, which are the weak link -
see [Still unmeasured](#still-unmeasured).

| Scenario | KB/day | days to 1 GB |
| --- | --- | --- |
| PNG, an image on every item | 8,537 | 123 (4 months) |
| WebP, an image on every item | 1,567 | 669 (22 months) |
| WebP, an image on one item in three | 547 | 1,917 (5.25 years) |
| no images | 37 | 28,340 |

The ordering of the levers falls straight out of this: encoding buys 5.6x,
honouring the visual rule buys another 2.9x, and retention is what remains
after both. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md).

## Feed availability

**Measured** on a developer machine (i7-1265U, Windows, 2026-08-21) by running
the real plan stage against the ratified `ai` list - a better check than a
bespoke script, because it exercises the code that will do it daily.

| Quantity | Value |
| --- | --- |
| Feeds configured | 36 |
| Resolved on the first pass | 26 |
| Recovered by finding the real feed URL | 5 |
| **Live after correction** | **31, against a floor of 25** |
| Retired: `robots.txt` forbids or is unreadable | 4 |
| Retired: the publisher declares no feed at all | 1 |

Two of the retirements are permanent by the host's own instruction rather than
defects to fix. One publisher (`ai.meta.com`) is a JavaScript application that
declares no feed on any path, which is a category the plan did not anticipate:
a source can be real, active and unreachable by RSS.

Two figures from the same runs, both single observations and both a laptop
rather than a runner: **one feed read takes roughly 0.5-4 s including its
`robots.txt`**, and a whole 36-feed plan pass finishes in **under a minute**.
That matters only as a shape: the planning step loads no weights, so fanning out
afterwards is what costs, not deciding the day.

**Summarization, Qwen3-4B-Q4_K_M, 4 threads, i7-1265U, 2026-08-21, n=1:** a
2,557-token article took **89 s** end to end for 179 output tokens. One
observation on a laptop, recorded because it is the first real per-article
number this project has; it is not a runner figure and may not be used as one.

## Corpus shape

**Measured 2026-08-22**, `ubuntu-latest` (4 vCPU), the `corpus` job in
`.github/workflows/measure.yml`, over 20 live articles pulled from the
configured feeds and extracted the way the pipeline extracts them.

| Statistic | Words |
| --- | --- |
| mean | 1323.5 (+/- 1297.6) |
| p10 | 248 |
| p50 | 978 |
| p90 | 2769 |
| max | 5077 |

| Bucket | n | Share | Median words |
| --- | --- | --- | --- |
| short | 10 | 0.50 | 411 |
| medium | 5 | 0.25 | 1546 |
| long | 5 | 0.25 | 2769 |

**This contradicts the design's assumption, so the design moves.** The cost
model assumed 400 / 1200 / 3500 words at a 25 / 55 / 20 share. The real share is
50 / 25 / 25: the corpus is far more bimodal than assumed, with twice as many
short articles and a quarter rather than a fifth long. The standard deviation is
roughly the mean, so "the average article" is not a thing that exists here - any
per-article figure multiplied by a mean is describing a corpus we do not have.

Two consequences, stated before anyone re-derives them:

- **Blended throughput estimates were too pessimistic.** Half the corpus is in
  the cheapest bucket, not a quarter of it.
- **Worst-case shard timeouts were too optimistic.** The long bucket is bigger
  than assumed and p90 sits at 2769 words. The timeout must keep coming from the
  worst case, never from the blend.

Caveat, stated rather than buried: n=20, one sample, one day. It settles that
the old buckets were wrong. It does not settle what the right ones are.

## The image measurement killed the runner

**Attempted 2026-08-22**, `ubuntu-latest`, the `image` job timing Z-Image-Turbo
on CPU. It ran for 48 minutes inside a 120-minute budget and then:

```
##[error]The runner has received a shutdown signal.
```

That is not a timeout. The job had 72 minutes left. A shutdown signal with time
on the clock is the runner agent being taken down underneath the job, which on a
16 GB machine running CPU diffusion is what memory exhaustion looks like from
the inside.

**This is itself evidence for Row #9.** The question that row asks is whether
generated images fit the published budget. Before reaching the byte count, the
measurement could not survive the machine. A feature whose *benchmark* cannot
complete in a job is not a feature that belongs on a 4 vCPU runner without
something changing first.

It does not settle the byte question, and it must not be cited as if it did. It
settles that the current approach to answering it does not run.

## Still unmeasured

Each line names the measurement that would settle it. Nothing here may be cited
to justify a design decision.

| Quantity | Current basis | What settles it |
| --- | --- | --- |
| **Faithfulness scoring seconds per item** | **unmeasured** | **a timed pass over 20 fixture pairs at the three premise lengths; it decides whether the scorer is a census or is sampled** |
| Cache-restore time per job, cache-hit | ~90 s, asserted | the same artifact, on a second run |
| Image render seconds at 512 and 768 | the job cannot complete | a smaller model, a smaller resolution, or a machine that survives it |
| Image bytes, PNG at 768 | ~500 KB, estimate | the `image` job writes the file; measure it |
| Image bytes, WebP q80 at 768 | ~90 KB, estimate | re-encode the same file and measure |
| A production day payload | fixture figure above | the first real pipeline run |
| HHEM scoring seconds per item on CPU | unmeasured | lands with the eval harness |
| Whether 1-2 bit quantisation changes the fit | unevaluated | open question 4 in the plan-doc |

## How to add a row here

Run the measurement, then record the quantity, the value, the spread, the
hardware and the date. If a number arrives without those four, it is an
estimate and belongs in the table above rather than in the tables below it.

When a measurement contradicts a design, the design changes - that has already
happened three times on this page.

## See also

- [../../CLAUDE.md](../../CLAUDE.md) - Holy Law #2 (the runner is the architecture) and #10 (measured, not estimated).
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the published-size arithmetic these numbers feed.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - the batch-size rule these numbers set.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - the prompt the token count above measures.
- [../how-to/set-up-local-inference.md](../how-to/set-up-local-inference.md) - reproducing the local runs.
