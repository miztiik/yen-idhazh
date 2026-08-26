# Measurements

**Last Updated**: 2026-08-26

Every number this project's design rests on, with the hardware it was taken on,
the date, and the spread. Rule #10 in one page: **an unmeasured number is
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
llama.cpp `b10580`, 3 repeats. These are the `llama-bench` numbers a design
decision may cite for article-length prefill and decode. They are not the
prompt-cache cost in the live digest path; use
[Prompt cache reuse](#prompt-cache-reuse) for that. The laptop tables below are
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

### Runner thread scaling

**Measured 2026-08-23** on GitHub-hosted `ubuntu-latest`, run `32672629352`:
AMD EPYC 7763, 2 physical cores, 2 threads per core, 4 online logical CPUs,
cpuset `0-3`, llama.cpp `b10598` (`56db501e7`), Qwen3-8B-Q4_K_M, 3 repeats.
Both thread counts ran in the same job against the same 5,027,783,488-byte GGUF
(`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`).

| Threads | 730 tok | 1800 tok | 4850 tok | decode (250) | Full bench wall |
| --- | --- | --- | --- | --- | --- |
| 4 | 12.48 +/- 0.01 | 12.06 +/- 0.01 | 10.83 +/- 0.04 | **7.21 +/- 0.02** | **2727.13 s** |
| 8 | 12.31 +/- 0.02 | 11.88 +/- 0.01 | 10.77 +/- 0.02 | **6.06 +/- 0.01** | **2771.53 s** |

Eight software workers did not expose four more hardware threads. The guest had
four logical CPUs already: CPUs 0-1 were siblings on core 0, and CPUs 2-3 were
siblings on core 1. Eight threads made prefill 0.6-1.5% slower, decode 16% slower
and the complete benchmark 1.6% slower. Cgroup CPU use averaged 3.99 CPUs at four
threads and 3.92 at eight; throttled time stayed zero. CPU pressure `some` rose
from roughly 39% after the four-thread point to roughly 75% after the
eight-thread point.

**Decision: keep `n_threads = 4`.** The raw screen rejected eight threads at
every measured workload, so the five-article server A/B would spend runner time
on a candidate that already failed its prerequisite.

### Derived seconds per article

Derived from the runner table by `backend/utilities/summarise_bench.py`, using
the **measured** length buckets in [Corpus shape](#corpus-shape). Derived, not
measured: they inherit both the throughput spread and the bucket error.

| Model | short | medium | long | blended | worst long |
| --- | --- | --- | --- | --- | --- |
| Qwen3-4B-Q4_K_M | 79s | 166s | 198s | **130s** | 198s |
| Qwen3-8B-Q4_K_M | 142s | 291s | 342s | **229s** | 342s |

The blended figures were first published as 128s and 196s -> corrected to 112s
and 196s when the bucket shares were replaced by the measured ones -> corrected
again to 130s and 229s when the tool's hardcoded 200-token prompt was removed
and article tokens were clamped at the production 2500-token cap. The prompt
measured 801 tokens at the time and now measures at most 879. The table uses the
current maximum. A derived time now requires an explicit model-specific prompt
count and truncation cap; without them the tool prints raw throughput only.

**These figures do not size a production worker.** From 2026-08-26 `digest.yml`
derives the worker count as `min(ceil(items / run.shard_size), run.max_parallel)`,
so `run.shard_size` decides how few workers a small day is worth, not how big a
shard is. `run.max_parallel` is four, so an automatic run still fans out to at
most the four this page has measured; a dispatch may ask for up to eight. At
`run.safety_ceiling_per_run` a worker draws 40 items, not five. Run
`32742672105` measured 34 to 41 items per worker across four. A current day can
be larger. Size request and job bounds from a measured real worker population
and its worst item, never from five-item arithmetic or the 229-second blend.

### Candidate: Qwen3.5-9B-Q4_K_M (measured; adoption work incomplete)

**Measured 2026-08-23** on `ubuntu-latest`: AMD EPYC 9V74 80-Core, 4 threads,
llama.cpp `b10598` (`56db501e7`), 3 repeats, `llama-bench` at the same three
input lengths. Exact candidate:

| Field | Value |
| --- | --- |
| Repository | `unsloth/Qwen3.5-9B-GGUF` |
| Repository revision observed 2026-08-25 | `3885219b6810b007914f3a7950a8d1b469d598a5` |
| File | `Qwen3.5-9B-Q4_K_M.gguf` |
| Quantisation | `Q4_K_M` |
| Bytes | 5,680,522,464 (5.29 GiB) |
| SHA-256 / Hugging Face LFS oid | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| Licence | Apache-2.0 |

The repository revision is mutable metadata about the repository snapshot. The
GGUF SHA-256 identifies the actual candidate bytes.

| Model | 730 tok | 1800 tok | 4850 tok | decode (250) |
| --- | --- | --- | --- | --- |
| Qwen3-8B-Q4_K_M (incumbent, b10580) | 12.1 +/- 0.0 | 11.6 +/- 0.0 | 10.4 +/- 0.0 | **7.28 +/- 0.01** |
| Qwen3.5-9B-Q4_K_M (candidate, b10598) | 10.14 +/- 0.01 | 10.06 +/- 0.01 | 9.84 +/- 0.01 | **6.01 +/- 0.11** |

These rows were not taken in the same job or on the same CPU model, and the
incumbent used `b10580`. They establish candidate throughput and fit. They do not
establish an exact candidate-to-incumbent delta.

The old 99 / 258 / 433 / 222 / 639-second derived figures are withdrawn. They
used the tool's former hardcoded 200-token prompt and did not apply the
production truncation cap. The Qwen3.5 prompt and article-token counts have not
been measured under its tokenizer, so no replacement derived time is valid yet.

Within the candidate run, prefill fell 3.0% from 730 to 4850 tokens (10.14 ->
9.84). Qwen3.5 is a hybrid Gated DeltaNet plus attention architecture, and
llama.cpp reports `qwen35`. The separate incumbent observation fell 14%, but the
two runs used different CPUs and runtime builds, so the difference cannot be
attributed to architecture. The same limitation applies to the separate 6.01
and 7.28 tok/s decode observations.

**Weight download, cache miss:** 5.29 GiB in **118s**, `n=1`; spread unavailable.
It may not be compared as a rate to the 8B's separate download observation.

**Raw cache screen:** candidate plus the 4B router is 7.616 GiB of weight files.
That is below the nominal 10 GB repository ceiling and is not proof that the
Actions cache fits: runtime copies, metadata and archive representation are
unmeasured. Candidate + incumbent + router is 12.299 GiB before runtime files,
so even the raw transition cannot fit. Measure actual cache entries, delete only
the old summary-model cache before the first production run, and keep the router
cache.

### The qualification budget, derived 2026-08-26

Derived, not measured, and the design is built so the verdict does not depend on
the derivation being right.

The starting point is a live production observation, not a bench: run
`32742672105` on 2026-08-24 spent 232.7 minutes in prefill and 135.7 in decode
across four workers over roughly 150 articles, which is **147 s of model time an
article** on the incumbent, with the shared system prompt already cached.

Scaling that to the candidate uses the two `llama-bench` rows above - prefill
12.1 -> 10.14 tok/s and decode 7.28 -> 6.01 tok/s, so 1.193x and 1.211x the
time. Those rows were taken on different CPUs and runtime builds, so the ratio
is an estimate and is labelled one:

```text
147 s x (0.632 x 1.193 + 0.368 x 1.211) = 176 s an article
```

`.github/workflows/validate.yml` runs three capture-and-replay shards of ten
frozen articles at three repeats, which is 30 inference calls a shard:

| Cost, per shard | Derived |
| --- | --- |
| 30 replay calls at 176 s | 88 min |
| 5 injection canaries, shard 0 only | 15 min |
| Checkout, Python, `pip install -e ".[faithfulness]"` | 4 min |
| llama.cpp plus 5.29 GiB of weights on a cache miss | 3 min |
| Server start and health | 1 min |
| Fetch and extract up to 30 addresses | 2 min |
| HHEM load and 10 items scored | 2 min |
| **Worst shard** | **115 min against a 330-minute bound** |

Margin 215 minutes, 65 percent of the bound. **At twice the derived per-item
cost the worst shard is 218 minutes and still inside**, which is the point of
sharding it: the design survives the estimate being wrong by 100 percent
(Rule #2, Rule #10).

The production projection uses the same 176 s. `digest.yml` derives workers as
`min(ceil(items / run.shard_size), run.max_parallel)`, so at
`run.safety_ceiling_per_run` a worst worker draws `160 / 4 = 40` items:
40 x 176 s = 117 minutes of model time, about 130 minutes with the fixed costs,
against the `work` job's 330. For comparison, the measured incumbent worst
worker was 58.8 minutes after PR #110.

### The faithfulness scorer, pinned 2026-08-26

| Field | Value |
| --- | --- |
| Model | `vectara/hallucination_evaluation_model` |
| Revision | `8e4a2e6e96c708cc76c2344f7e4757df2515292c` |
| Read from | the Hugging Face model API, 2026-08-26 |
| Repository last modified | 2025-10-20 |
| Parameters | 109,630,082, all F32 |
| Licence | Apache-2.0 |

`HHEM_REVISION` was the literal string `main` until this date, and
`weights_digest` hashed `name@revision` - the label the loader was handed, not
the bytes it came back with. Two different checkpoints behind one branch name
produced one digest, and the derived `scorer_version` said the instrument had
not changed. It now walks the loaded state dict in key order and digests the
actual parameter bytes. Every faithfulness number taken before this date was
measured with an instrument nobody can name afterwards.

What remains unmeasured:

- candidate prompt tokens and article-token spread;
- candidate-specific worst-case context and derived seconds per article;
- schema-valid non-thinking output at the configured greedy sampler;
- live prompt-injection canaries and deterministic repeated output;
- quality on frozen Article payloads;
- failure rate, counterweights and blind human review; and
- recurrent-state prefix reuse.

Every line above except the last two is what `.github/workflows/validate.yml`
was rebuilt to measure on 2026-08-26. They stay on this list until a dispatched
run answers them; an instrument that exists is not a measurement.

The model card publishes no summarization or faithfulness result. Its reasoning,
instruction-following, coding and long-context tables are a prior and not
evidence for this pipeline. That absence is recorded as a `not_reported`
leaderboard provenance on the validation row, never as `0.0`.

#### Estimate: what one work shard costs on the candidate

**Every figure in this subsection is an estimate, not a measurement, and none of
them may settle a design on its own (Rule #10).** Derived 2026-08-25 from the
`llama-bench` figures measured 2026-08-23 on `ubuntu-latest` / AMD EPYC 9V74 /
4 threads / llama.cpp `b10598` / n=3, using the Qwen3-8B prompt token count as an
unmeasured substitute for the 9B's.

Both derivations start from the same base - the derived Qwen3-8B **worst long
article of 342 s** - because a timeout is set by the worst item and not by a
blend. That base is itself derived, so this is an estimate resting on an
estimate. It decomposes as 879 prompt tokens plus the 2500-token truncation cap,
3379 tokens prefilled at 10.98 tok/s (interpolated between the 1800- and
4850-token rows) for 307.8 s, plus 250 decoded tokens at 7.28 tok/s for 34.3 s.
The two derivations differ in how they carry that across to the candidate:

- **Interpolation** scales each part by the candidate's own rate at that length -
  prefill 10.98 -> 9.95 tok/s and decode 7.28 -> 6.01 tok/s. It gives 381 s an
  article.
- **Decode ratio** scales the whole 342 s by the decode observation alone
  (7.28 -> 6.01 tok/s). It gives 414 s an article, and is the pessimistic one
  because prefill degrades far less than decode on this candidate.

The two rates were taken in separate jobs on different CPU models, so the ratio
between them is an observation and not a controlled delta.

An automatic run fans out to `run.max_parallel` workers, which is four, so the
ceiling divided by four is what one worker draws in the worst case. A dispatch
may ask for up to eight and would halve these figures; nothing here rests on
that, because a scheduled run is the path a reader depends on.

| Ceiling | Items a shard draws at four workers | Interpolation | Decode ratio | Against the 330-minute `work` bound |
| --- | --- | --- | --- | --- |
| 200 (until 2026-08-26) | 50 | 318 min (96%) | 345 min (105%) | busts one method and has no margin on the other |
| **160 (today)** | **40** | **254 min (77%)** | **276 min (84%)** | **clears both** |

160 is the ceiling because it clears the bound under both methods and because it
absorbs the one input nobody has measured: the prompt is counted with the 8B's
tokenizer. If the 9B renders the same prompt 20% longer - 3554 tokens rather than
3379, at 399 s an article - 40 items still clears at 266 min while 50 items busts
at 333 min. The largest day ever planned is 149 items (run `32742672105`,
2026-08-24), so 160 removes nothing that has ever been read.

Replace this table with a measurement as soon as one exists. The measurement that
settles it is one candidate `work` shard on `ubuntu-latest` reporting its own
`prefill_ms` and `decode_ms` per item.

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

### Local 4-vs-8 thread screen

**Measured 2026-08-23** on Windows 11, Intel Core i7-1265U (10 physical cores,
12 logical processors), Qwen3-8B-Q4_K_M, llama.cpp `b10444` (`5f754ea0e`), 3
repeats. The bounded screen used 730 prompt tokens and 64 decode tokens.

| Threads | Prefill tok/s | Decode tok/s | Combined benchmark wall-clock |
| --- | --- | --- | --- |
| 4 | 9.44 +/- 0.44 | 3.44 +/- 0.31 | 375.06 s |
| 8 | 11.17 +/- 0.13 | 3.91 +/- 0.19 | 318.67 s |

Eight threads improved this laptop's prefill by 18% and decode by 14%; combined
wall-clock fell 15%. The laptop exposes 12 logical processors, so this does not
answer whether eight software workers help a four-vCPU VM. That answer must come
from the hosted sweep on the same model and runtime build.

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
| **Current four-band prompt, including the brief tier** | **658** | **877-879** |

The terseness pass removed 183 words and **232 tokens, 22.5%**, without removing
a rule. The later brief tier and fourth output band brought the current prompt
to 658 words. Its four variants measure 877, 877, 878 and 879 tokens, so the
spread is two tokens. What went in the terseness pass was justification,
restatement, and one line the decoder already enforced. See
[../architecture/summarize/prompt.md](../architecture/summarize/prompt.md).

The old nominal context arithmetic was:

| Component | Tokens |
| --- | --- |
| System prompt | 879 |
| Article, at the 2500-token truncation cap | 2500 |
| Output budget | 900 |
| **Nominal sum** | **4279; not a complete request measurement** |

This is not a context-fit result. It omits chat-template tokens, source-form
text, feed title, fences and generation suffix. The 2500 cap is applied through
a words-to-tokens estimate before exact model tokenization, so exact article
tokens can exceed it.

Three notes worth keeping:

- **Measure the prompt with the line endings the model is sent.** The same
  rendered prompt tokenizes at 801 with LF and 880 with CRLF - a 79-token, 10%
  difference from nothing but a file write. Python's default text mode
  translates on Windows, so a measurement taken that way overstates the prompt
  by a tenth.
- **The prompt-cost estimate is superseded for live digest runs.** The old
  derived value used 801 tokens at the `llama-bench` 730-token rate of 12.1
  tok/s, or 66.2 s. Run `32648218952` measured the live digest path at 34.23
  tok/s median, so the same 801 tokens cost 23.4 s median. Use the prompt-cache
  table below for prompt-reorder decisions.
- **The `fits_context` margin is not fully measured.** It approximates the
  658-word system prompt as 1316 tokens, 437 above the measured system-prompt
  maximum of 879. That says nothing about omitted chat framing or exact
  candidate article tokens. Tokenize the complete request before claiming fit.

## Prompt cache reuse

**Measured 2026-08-23** on GitHub-hosted `ubuntu-latest`, 4 vCPU, run
`32648218952`, job `work (3)`. The job log did not name the CPU model or the
llama.cpp build. It used `Qwen3-8B-Q4_K_M.gguf` through `llama-server` with
`--ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4 --no-warmup`.

The run refutes the suspected context-splitting defect for this build. The log
said:

```text
srv load_model: initializing, n_slots = 4, n_ctx_slot = 8192, kv_unified = 'true'
```

Current llama.cpp source names the same quantity `n_ctx_seq`: when `kv_unified`
is true, `n_ctx_seq = n_ctx`; when it is false, `n_ctx_seq = n_ctx / n_seq_max`.
This log uses the older `n_ctx_slot` name. The value is 8192 per slot, so the run
refutes context splitting. It does not prove the maximum complete request fits;
that request has not been tokenized end to end.

The run does **not** settle whether the prompt prefix was reused. The grep
emitted no `kv cache rm [p0, end)` line. The only emitted instrument was
`prompt eval time = X ms / N tokens`, and `N` varies with article length and
band. Because `band_for()` changes the rendered prompt, only the roughly
315-token head is invariant across all bands. A same-band hit could reuse more,
but the log did not print the band or article token count beside each timing
line.

**Superseded 2026-08-24.** The log did carry the proof; the workflow's summary
step was not grepping for it. See "Reuse settled" below.

| Slot | Prompt-eval tokens, in task order |
| --- | --- |
| 2 | 2441, 580, 654, 781, 862, 621, 738, 1195, 1064, 1883 |
| 3 | 2485, 2545, 1146, 2284, 1035, 1423, 1945, 850, 373, 1260, 1015, 1131, 440, 1136, 636, 888, 572, 444, 1179, 1426, 485, 1380, 2565, 1687, 607, 730 |

No fixed subtraction of about 315 or 801 tokens is visible within either slot.
That is evidence that the current log cannot prove reuse, not evidence that a
cache miss happened. To settle it, log the slot id, item id, band id, rendered
system-prompt tokens, article tokens, full prompt tokens, evaluated prompt tokens
and any llama.cpp reused-prefix field such as `p0` or `n_past`.

| Quantity | Value |
| --- | --- |
| Sample | 36 `print_timing` lines from `work (3)` |
| Prefill throughput | min 29.24 tok/s, max 37.92 tok/s, median 34.23 tok/s |
| Spread | 8.68 tok/s |
| 801-token re-prefill cost | 23.4 s median; observed range 21.1-27.4 s |
| 315-token invariant-head cost | 9.2 s median; observed range 8.3-10.8 s |

This supersedes the derived 66.2 s per 801-token re-prefill above for live
`digest` runs. That older number came from `llama-bench` on an EPYC 9V74 runner
and remains useful history. This run measured the actual `digest` path on a
GitHub-hosted `ubuntu-latest` runner, and it was about 2.8x faster at the median.

The row 9 prize changes. The old arithmetic was `13 x 66.2 s = 14.4 min` of CPU,
or about 4.4 min wall clock across four shards. This run says `13 x 23.4 s =
5.1 min` of CPU for a full 801-token prefix, or about 1.3 min wall clock across
four shards. For the invariant head, the ceiling is `13 x 9.2 s = 2.0 min` of
CPU, or about 0.5 min wall clock. Row 9 should not reorder the prompt on the old
66.2 s premise. It should first add the instrumentation above, then run an A/B
measurement on the runner and keep the change only if the measured wall-clock
gain pays for the prompt risk.

Row 9 collapsed the prompt reorder on this measurement. It did not move the
band-varying numbers to the tail of the system prompt, because the live runner
showed a 1-2% wall-clock ceiling, and the existing log cannot prove the reuse
the change was meant to buy. Reopen the reorder only with runner A/B evidence
that logs slot id, item id, band id, rendered system-prompt tokens, article
tokens, full prompt tokens, evaluated prompt tokens, and a reused-prefix field
such as `p0` or `n_past`; the golden set's `output_digest` values must stay
unchanged.

### Reuse settled: the log did prove it, the grep hid it

**Measured 2026-08-24** on GitHub-hosted `ubuntu-latest`, 4 vCPU, run
`32742672105`, job `work (0)`, `Qwen3-8B-Q4_K_M.gguf` through `llama-server`
with `--ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4`. The job
log did not name the CPU model or the llama.cpp build.

The section above concluded the log could not prove prefix reuse. That was a
reading of the workflow's summary step, not of the log. The step greps for
`kv cache rm [`, which this build never emits. The uploaded `runtime-log-0`
artifact carries the line that settles it:

```text
slot get_availabl: id  3 | task -1 | selected slot by LRU, t_last = -1
slot get_availabl: id  3 | task -1 | selected slot by LCP similarity, f_sim_best = 0.923 (> 0.100 thold), f_keep = 0.811
slot print_timing: id  3 | task 172 | prompt eval time = 7119.70 ms / 75 tokens
```

`f_sim_best` is the longest common prefix divided by the incoming prompt, and
`f_keep` is the same prefix divided by what the slot already held. On that
request about 900 of roughly 975 prompt tokens were reused and 75 were
evaluated: 7.1 s instead of about 88 s.

| Quantity | `work (0)` |
| --- | --- |
| Requests | 34 |
| Cold, selected by LRU | 1 |
| Selected by LCP similarity | 33 |
| Prompt tokens evaluated | 31,714 |
| Prompt tokens reused (approx.) | 28,700 |

Two requests fell to `f_sim_best` 0.29 and 0.14. Both sit where the worker
crosses a prompt band, which is the reorder question above seen from the other
side: the band-varying numbers sit early in the system prompt, so a band change
truncates the shared prefix. That is now a measured cost, not a suspicion.

Only one of the four slots was ever used. That run passed no `-np`, so
llama.cpp built its default four, and the worker sends one request at a time.
`n_parallel` is 1 from 2026-08-24, so later runs stand up one slot and the
`selected slot by LRU` line no longer has a choice to make. Prefix reuse is
unaffected: it is a property of the slot's retained prompt, not of how many
slots exist.

Correction to record: only the workflow's summary step was blind. Nothing about
the earlier `32648218952` throughput figures changes.

## Model throughput across the four workers

**Measured 2026-08-24** on GitHub-hosted `ubuntu-latest`, 4 vCPU, run
`32742672105`, all four `work` jobs, `Qwen3-8B-Q4_K_M.gguf`, settings as above.
Taken from the four `runtime-log-*` artifacts. Each figure is that job's total
tokens divided by its total milliseconds, not a median of per-request rates,
because a rate is a ratio.

| Job | Articles | Prefill tok/s | Prefill ms/tok | Decode tok/s | Decode ms/tok |
| --- | --- | --- | --- | --- | --- |
| `work (0)` | 34 | 11.05 | 90.5 | 5.23 | 191 |
| `work (1)` | 35 | 10.91 | 91.7 | 4.93 | 203 |
| `work (2)` | 39 | 10.92 | 91.6 | 5.02 | 199 |
| `work (3)` | 41 | 10.94 | 91.4 | 5.04 | 198 |
| **All four** | **149** | **10.95** | **91.3** | **5.05** | **198** |

Totals: 152,933 prompt tokens evaluated in 232.7 min, 41,098 tokens written in
135.7 min.

Two readings hold:

- **The four workers agree.** Prefill spreads 1.3% across jobs and decode 6%.
  There is no slow runner in this run, so a shard that finishes late is carrying
  longer articles rather than worse hardware.
- **Decode slows inside a job; prefill does not.** Median decode falls about 11%
  from the first half of a job to the second (5.4 to 4.8 tok/s) in all four,
  while prefill stays flat. Nothing carries over between articles - each request
  overwrites the slot's prompt. The cause is our own ordering: `stage_work`
  sorts a worker's items by prompt band, so the short articles are summarised
  first and the long ones last, and the second half of every job is therefore
  carrying bigger prompts and being asked for longer summaries. Both raise the
  cost per generated token within that one request.

| Job | Context tokens, median | Summary tokens, median | Decode tok/s, median |
| --- | --- | --- | --- |
| `work (0)` | 1712 -> 2382 | 242 -> 298 | 5.53 -> 5.13 |
| `work (1)` | 1651 -> 2552 | 244 -> 316 | 5.35 -> 4.70 |
| `work (2)` | 1612 -> 2527 | 233 -> 296 | 5.38 -> 4.81 |
| `work (3)` | 1688 -> 2694 | 245 -> 315 | 5.41 -> 4.78 |

First half of each job against its second half. The consequence for planning is
that a job's remaining time cannot be extrapolated from its first few items -
those are the cheapest ones it will do. See
[../architecture/summarize/throughput.md](../architecture/summarize/throughput.md).

Prefill runs about 2.2x the decode rate, which is the reason `prefill_ms` and
`decode_ms` are separate columns on the item-health row rather than one
`summarize_ms`. From this run on, every run records its own figures, so this
table stops being the only copy - see
[../architecture/sources/item-health.md](../architecture/sources/item-health.md).

### The prompt token counts, from the tokenizer

**Measured 2026-08-23.** Method: `backend/bin/llama-tokenize` against
`backend/models/Qwen3-8B-Q4_K_M.gguf`, over the system prompt rendered from the
committed `config/` for every band. A token count is a property of the tokenizer
and the text, so it does not vary with the machine that counted it.

Every earlier figure for this prompt came from a word-share count, not a
tokenizer, and every one of them was wrong:

| Quantity | Earlier estimate | Measured |
| --- | --- | --- |
| Full system prompt | 801 tokens | **877-879 tokens** |
| Invariant shared prefix | about 315 tokens | **381 tokens** (296 words) |
| Distinct rendered prompts | 3 | **4** |

The prefix ends exactly where `band_for()` substitutes the word range, at
`Length:\n\n- Write one summary of `. The fourth distinct prompt is the brief
band that row 8 added; the earlier count of three predates it.

Re-running the row 9 arithmetic on the measured head and the measured prefill
throughput of 34.23 tok/s: 381 tokens costs **11.1 s** per item, so 13
recoverable items is **2.4 min** of CPU, or about **0.6 min** of wall clock
across four shards. That is 21 percent more than the 315-token estimate implied,
and it does not change the decision - the ceiling is still 1-2 percent of a run.
**Row 9's collapse survives its own correction.**

## Evaluation ledger re-band

**Measured 2026-08-23** on `state/scores.csv` at commit `6c332c7`, n=156.
Method: Python `csv.DictReader` over the committed ledger, with today's
`EvaluationConfig` and `backend/idhazh/evals/score.py::band()`. This is
deterministic ledger arithmetic, so hardware and spread are not applicable.

The recorded `band` column predates the counterweight caps. It is the scorer's
time-of-write output, not the current distribution.

| Band | Recorded | Re-banded with today's `band()` |
| --- | --- | --- |
| high | 112 (71.8%) | 85 (54.5%) |
| medium | 19 (12.2%) | 46 (29.5%) |
| low | 25 (16.0%) | 25 (16.0%) |

Twenty-seven rows, 17.3%, move from `high` to `medium`.

| Move reason | Rows |
| --- | --- |
| Lead coverage alone | 11 |
| Dropped hedge alone | 11 |
| Lead coverage and dropped hedge | 5 |

Only four rows have `unsupported_numbers > 0`. In the 600-1000 source-word
stratum, n=50, two positives sit below `hhem = 0.80` and none sit above it. That
is too few events to set a threshold.

The ledger is one run, not two days. `run_id` `2026-08-23-3` owns 137 of 156
rows. The remaining 19 rows sit under a different `pipeline_fingerprint`. Five
source URLs appear under both fingerprints. Every one moved downward: -0.105,
-0.595, -0.114, -0.079 and -0.034. That uniform shift points at a producer
change in a way scattered noise would not. The largest observed item-level HHEM
move is 0.595: the Google biomarker article moved from 0.9578 (`high`) to 0.3626
(`low`) with no model or scorer change recorded.

**Re-measured 2026-08-24** on the same ledger at n=447, same method.

| Band | Recorded | Re-banded with today's `band()` |
| --- | --- | --- |
| high | 285 (63.8%) | 258 (57.7%) |
| medium | 81 (18.1%) | 108 (24.2%) |
| low | 81 (18.1%) | 81 (18.1%) |

Still exactly 27 rows move, and with the same split: 11 lead coverage, 11 dropped
hedge, 5 both. Every row written since the caps landed is already banded with
them, so the gap between the two columns is a fixed historical residue rather
than a rate that grows. It is 6.0% of the ledger now and shrinks with every run.

## The route job's budget

**Measured 2026-08-24 on `ubuntu-latest` (4 vCPU, 16 GB), run `32742672105`.**
Per-item inference owns the time. Model load, cache and orchestration do not.

| What | Value |
| --- | --- |
| Fixed cost: set-up, checkout, Python, cache restore, llama-server start, pip install, artifact download | **47 s** (17:01:24 -> 17:02:11) |
| `Route and render` step | **3155 s** (52.6 min) |
| Items routed | 149 |
| Per-item wall-clock | mean **21.0 s**, min 8.1 s, max 56.0 s, n=148 gaps |
| Kinds chosen | 15 chart (10.1%), 134 none (89.9%), **0 diagram** |

The fixed cost is 1.5% of the job. That settles the first of the three questions
this row opened: it is not model loading.

The derived ceiling: `(3600 - 47) / 21.0` = **169 routable items** inside the
60-minute bound. `run.safety_ceiling_per_run` was 200 when this was measured, and
moved to 160 on 2026-08-26. The two numbers had never been consistent, and the
runs that fit did so because roughly a quarter of the plan had no `OK` summary
and was skipped. **Improving the summarizer breaks the router.** That coupling is
the defect, not the bound.

Job wall-clock across the eight real runs since the daily size moved from 17
items to 200 on 2026-08-23:

| Run | `route` minutes | Outcome |
| --- | --- | --- |
| `32634191910` | 8.0 | success, 17 items planned |
| `32648218952` | 60.3 | cancelled at the bound |
| `32661273335` | 60.3 | cancelled |
| `32671663130` | 60.3 | cancelled |
| `32680268454` | 60.3 | cancelled |
| `32701966659` | 51.2 | success |
| `32719349248` | 60.4 | cancelled |
| `32742672105` | 53.5 | success |

Read the five cancellations as killed, not as measured: they all report 60.3 to
60.4 because that is where the runner stopped them. Only 8.0, 51.2 and 53.5 are
observations.

What changed on the back of this: the router now skips the model for an item no
enabled visual kind could serve, and the stage has its own request timeout. It
had been borrowing `run.shard_timeout_minutes` - 150 minutes against a 60-minute
job, so it could never fire. See
[../architecture/publishing/visuals.md](../architecture/publishing/visuals.md).

### Re-measured across six runs, 2026-08-25

The single-run figure above was not the whole picture. Six `route` jobs on
`ubuntu-latest` between 2026-08-24 07:32 and 2026-08-25 03:14, 703 routed items.
Method: parse the `item routed` lines out of each job log; per-item cost is the
recorded `route_ms` where the run wrote one and the gap between consecutive log
timestamps where it did not. The two agree on the runs that carry both.

| Run | slots | n | mean | median | min | max | span | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `32701966659` | 4 | 145 | **20.7 s** | 17.8 s | 8.0 | 53.5 | 49.7 min | success |
| `32719349248` | 4 | 93 | **38.2 s** | 35.6 s | 11.9 | 78.8 | 58.6 min | cancelled |
| `32742672105` | 4 | 149 | **21.0 s** | 18.1 s | 8.1 | 56.0 | 51.7 min | success |
| `32766098026` | 4 | 95 | **37.2 s** | 33.3 s | 12.2 | 79.5 | 58.2 min | cancelled |
| `32772221068` | 1 | 133 | **26.6 s** | 24.2 s | 9.2 | 59.0 | 58.1 min | cancelled |
| `32804437110` | 1 | 88 | **40.3 s** | 38.0 s | 12.5 | 76.5 | 58.1 min | cancelled |

Three readings, and the second and third are the ones that matter:

- **The cost is bimodal between runs, not drifting.** Every run is either about
  21 s an item or about 38 s. The spread *within* a run is far smaller than the
  spread *between* runs. The job's fate is decided by which host it drew.
- **`n_slots` does not explain it.** Both 21 s runs and two of the 38 s runs ran
  four auto-selected slots; the two one-slot runs sit at 26.6 s and 40.3 s. The
  `-np 1` production trial is not what moved this number.
- **The pre-filter had never fired.** `asked=False` appears **zero times in all
  703 items**. `diagram` was in `visuals.enabled_kinds`, a diagram is reachable
  for every item by construction, so `reachable_kinds` never returned empty.

### What the pre-filter removes, measured offline

**Measured 2026-08-25** on the 145 items with an `OK` summary from run
`32804437110`. No model, no network, no runner: the `items-*` artifacts were
downloaded and `route.reachable_kinds` was asked the same question
`_route_one` asks. This is the row `measurements.md` had listed as free to
measure and still unmeasured.

| `enabled_kinds` | Model asked | Model skipped |
| --- | --- | --- |
| `[chart, diagram]` (as shipped until 2026-08-25) | 145 (100%) | 0 |
| `[chart]` | 77 (53.1%) | **68 (46.9%)** |

Distribution behind it: median 7 quantities per article (mean 7.8), median
widest unit group 3 (mean 2.9, max 14), median 621 article words (mean 732, max
1923). The widest-unit-group histogram, where `min_chart_points` is 3:

| Widest group | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 14 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Articles | 13 | 30 | 25 | 31 | 19 | 12 | 4 | 3 | 5 | 1 | 1 | 1 |

### What the model actually asked for

Run `32804437110` is the first to log the draft kind beside the final kind:
**17 chart drafts, 71 `none` drafts, 0 diagram drafts in 88 items.** Nine of the
17 chart drafts survived the same-unit and distinct-bar checks. Across all six
runs above, `diagram` was the final kind **zero times in 703 items**. The arm was
switched off on the strength of this.

### Where the per-item cost actually goes

**Measured 2026-08-25** from llama-server's own `print_timing` lines in each
run's `router-log` artifact - the runtime's numbers, not ours. Same six runs,
608 requests.

| Run | slots | Per item | Prefill | Decode | Prefill share | Prompt | Reply |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `32701966659` | 4 | 20.7 s | **62.9 tok/s** | 5.5 tok/s | 56% | 696 tok | 38 tok |
| `32719349248` | 4 | 38.2 s | **20.2 tok/s** | 8.7 tok/s | 86% | 622 tok | 38 tok |
| `32742672105` | 4 | 21.0 s | **60.6 tok/s** | 5.5 tok/s | 56% | 659 tok | 38 tok |
| `32766098026` | 4 | 37.2 s | **21.0 tok/s** | 9.1 tok/s | 86% | 623 tok | 39 tok |
| `32772221068` | 1 | 26.6 s | **31.5 tok/s** | 8.7 tok/s | 81% | 628 tok | 38 tok |
| `32804437110` | 1 | 40.3 s | **21.3 tok/s** | 9.0 tok/s | 85% | 700 tok | 39 tok |

Rates are day totals - tokens summed, milliseconds summed, divided once - not
the mean of per-item rates. Prompt and reply are medians.

Four candidate causes die here and one survives:

- **Not the article mix.** The median prompt is 622-700 tokens on every run and
  the median reply is 38-39. The work per item did not change.
- **Not `n_slots`.** Four-slot runs appear at both 62.9 and 20.2 tok/s, and
  one-slot runs at both 31.5 and 21.3. The `-np 1` production trial is not what
  moved this.
- **Not decode, and not a generally slower machine.** Decode moves the *other
  way*: 5.5 tok/s on the fast runs against 8.7-9.3 on the slow ones. A slower
  host would slow both.
- **Not a truncated request.** `visuals.request_timeout_minutes` is 2.0 and the
  slowest item measured 79.5 s.
- **It is the prefill rate, and only the prefill rate.** It swings 3.1x, and
  because prefill is 56% to 86% of a request, the whole per-item figure follows
  it. What differs between hosts to produce a 3x prompt-eval swing alongside a
  *faster* decode is not recorded, because nothing logged the CPU. The `route`
  job now prints `/proc/cpuinfo` model name, `nproc` and llama-server's
  `system_info` line, so the next slow run answers it.

The lever this points at is the prompt, not the runtime: `visuals.lead_words`
(150) is most of each request's prefill, and prefill is most of the stage. It has
never been swept.

### Why a cancelled run published nothing

A job cancelled at its timeout skips every step without an explicit condition.
Step 15 of run `32804437110`'s `route` job - the `routes` artifact upload - is
recorded as `skipped`, while `Upload router log` (which carries `if: always()`)
ran. So 88 routing decisions and 9 rendered charts existed on that runner and
none of them left it. `assemble` downloaded no routes artifact and published 145
items with zero visuals.

The derived ceiling, restated for both hosts and both configurations:

| Per-item | `[chart, diagram]` | `[chart]` |
| --- | --- | --- |
| 20.7 s (fast host) | 172 items | 324 items |
| 40.3 s (slow host) | 88 items | 166 items |

against a 50-minute stage budget. `run.safety_ceiling_per_run` was 200 when this
was measured and moved to 160 on 2026-08-26 for the `work` job's sake. 160 is the
first ceiling a slow host clears with `enabled_kinds: [chart]` - 166 items
against 160 - so the plan ceiling and the router's capacity now agree where at
200 they never did. A slow host still cannot finish a maximum day with the
diagram arm on, which is why the stage stops itself rather than being killed.

## The one-slot production observation

**Observed 2026-08-24** on GitHub-hosted `ubuntu-latest`, 4 vCPU, across two
consecutive `digest` runs, `Qwen3-8B-Q4_K_M.gguf` through `llama-server` with
`--ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4`. Taken from the
eight `runtime-log-*` artifacts. Each figure is that job's total tokens divided
by its total milliseconds, not a median of per-request rates, because a rate is
a ratio.

| Run | `work` jobs started | `-np` | `n_slots` | `kv_unified` |
| --- | --- | --- | --- | --- |
| `32766098026` | 2026-08-24 19:08 UTC | omitted | 4 | `'true'` |
| `32772221068` | 2026-08-24 21:57 UTC | `1` | 1 | `'false'` |

**This comparison cannot answer the question.** It is two real content
refreshes, not a controlled A/B. Three hardware profiles appear across the eight
jobs, prefill spans 3.4x between them, and the two runs did not draw the same
mix. Nothing below says `-np 1` is free. It says the observation has no power.

| Run `32766098026`, four auto slots | Requests | Prefill tok/s | Decode tok/s | Whole job tok/s |
| --- | --- | --- | --- | --- |
| `work (0)` | 37 | 10.85 | 4.93 | 8.74 |
| `work (1)` | 36 | 11.43 | 5.26 | 9.07 |
| `work (2)` | 32 | 11.32 | 5.16 | 9.08 |
| `work (3)` | 40 | 36.42 | 3.36 | 11.56 |
| **All four** | **145** | **13.67** | **4.47** | **9.52** |

| Run `32772221068`, one slot | Requests | Prefill tok/s | Decode tok/s | Whole job tok/s |
| --- | --- | --- | --- | --- |
| `work (0)` | 37 | 14.18 | 3.58 | 8.68 |
| `work (1)` | 42 | 11.49 | 5.46 | 9.05 |
| `work (2)` | 38 | 10.93 | 4.99 | 8.83 |
| `work (3)` | 31 | 37.24 | 3.30 | 11.61 |
| **All four** | **148** | **14.10** | **4.21** | **9.33** |

Six findings. The first three are why the comparison has no power. The next two
are facts it did settle. The last is a gap it exposed.

**Three hardware profiles, and the runs drew different mixes.** Per-request
prefill clusters tightly inside each job and not at all across jobs: five jobs
sit near 11 tok/s, one at 14.2, and two at 36.4 and 37.2. The clusters do not
touch. The slowest request on a fast-prefill host measured 30.7 tok/s, above the
fastest request on any other host at 15.5. Across all eight jobs prefill spans
10.85 to 37.24 tok/s, **3.4x**. The four-slot run drew three slow hosts and one
fast; the one-slot run drew two slow, one middle and one fast. The runs differ
in hardware before they differ in flags. Decode moves the other way, exactly as
it did in the `route` stage: the two fast-prefill jobs wrote at 3.36 and 3.30
tok/s while the slow-prefill jobs wrote at 4.93 to 5.46. A host that is simply
faster would speed both.

**The run-level figure, and the two ways to compute it.** By the ratio this page
uses - tokens summed, milliseconds summed, divided once - the runs are **9.52**
and **9.33** tok/s, a 2.0 percent fall. The 2026-08-25 observation reported
**9.61** and **9.54**, a 0.7 percent fall. Both pairs are recorded so that
neither is later quoted as a null result. The gap between them is arithmetic:
9.61 and 9.54 are the unweighted mean of the four per-shard ratios, which weighs
a 31-request job the same as a 42-request one. A rate is a ratio, so 9.52 and
9.33 are the pair to cite.

**The comparison is too loose to exclude anything.** The 2026-08-25 observation
put the effect bound at **18.4 percent**. That figure does not reproduce from
the eight artifacts by the method above, and it is recorded here only as stated
on that date. What does reproduce, from the eight `items-*` artifacts rather
than the runtime logs: 95 items appear in both runs and 93 of those had
byte-identical extracted text. Pairing those 93 by item and reading
`input_tokens + output_tokens` over `summarize_ms`, which counts the cached
prefix as read and so is a higher basis than the whole-job rate above, the
four-slot run pools to 15.06 tok/s. The mean paired difference against it is
-0.05 tok/s, 95 percent interval -4.7 to +4.0 percent. Over the 36 pairs that
ran on a slow host in both runs the base is 13.95 tok/s and the difference is
+0.67 tok/s, interval -1.2 to +10.8 percent. The interval is the mean paired
difference plus and minus 1.96 standard errors. The comparison therefore
excludes nothing smaller than about 11 percent, and what it measured is 2
percent.

**The `kv_unified` flip is cosmetic.** `-np 1` sets `n_seq_max = 1`, and the
server then prints `kv_unified = 'false'`. The quantity that decides whether the
context is split is `n_ctx_seq`: unified KV gives `n_ctx_seq = n_ctx`, and
non-unified gives `n_ctx_seq = n_ctx / n_seq_max`. At `n_seq_max = 1` that is
`8192 / 1 = 8192`, the same number. All eight jobs logged `n_ctx_slot = 8192`.
The flag changed; the context each request gets did not. Do not reopen this.

**Identical declared inputs produced different words on different hardware.**
Both runs carry the same `pipeline_fingerprint`
(`969b1917d38f4b44344dc818559122547bcbaf1aa37c836fbfc2eec6d1d2b945`) and the
same `model_id` (`qwen3-8b-q4-k-m`). Comparing the `output_digest` written into
the `items-*` artifacts, over the 93 pairs with byte-identical extracted text:

| Host profile | Pairs | Identical `output_digest` |
| --- | --- | --- |
| Same in both runs | 43 | 40 (93.0%) |
| Different | 50 | 2 (4.0%) |

The 2026-08-25 observation put the cross-profile figure at 10 percent; the
artifacts give 4.0 percent. This is the field confirmation of why `host_cpu` is
recorded on the ledger row and kept out of the fingerprint. It is the only field
that explains a divergence, and digesting it would hide the divergence instead
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

**The llama.cpp build is UNKNOWN for both runs.** Verified 2026-08-25: no build
line and no CPU line appears in any of the eight artifacts. Do not assert that
the two runs shared a binary, and do not assert that they did not. The workflow
cache makes this harder rather than easier, and that trap is recorded in
[agent-notes.md](agent-notes.md).

The consequence for the sweep table below is that `np1` stays pending. A flag
whose measured effect is smaller than the noise floor of the comparison has not
been measured.

## llama-server runtime sweep

**Status 2026-08-24:** the controlled sweep has not run. By user approval,
production now pins `-np 1` for an observational trial across real content
refreshes. These runs show operational behaviour, but changing article mixes
and runner hosts mean they do not isolate the flag's effect. `startup_warmup =
true` records the behaviour that PR #24 already put in `digest.yml`.

The `runtime` job in `.github/workflows/measure.yml` runs one dispatch per
candidate flag. It creates a fixed five-article run plan for that dispatch, then
runs a same-dispatch baseline three times and the selected candidate three
times. It records wall-clock, startup time, per-item timings, server RSS samples,
cgroup memory peak, the full `server_argv`, and parsed server facts such as
`n_slots`, `n_ctx_slot` and `kv_unified`. It reports medians, spreads, and
whether the candidate beat the baseline outside the measured spread. It rejects a
candidate when any `output_digest` differs between repeats or from the baseline.

The controlled-sweep baseline remains:

```text
--model --alias --ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4 --port 8080
```

Each candidate is pending unless a runner artifact records hardware, date and
spread. Two are settled: `threads` was rejected at the screen, and
`np2_inflight` is dead.

| Candidate | Flag under test | Status |
| --- | --- | --- |
| `np1` | `-np 1` | Production observation started 2026-08-24 by user approval. Run `32648218952` established that omitted `-np` selected four auto slots with `n_ctx_slot = 8192` and unified KV. Two full runs were then compared and the comparison had no power: see [The one-slot production observation](#the-one-slot-production-observation). Still pending, because real refreshes are not a controlled A/B. |
| `batch2048` | `-b 2048` | Pending. Hypothesis: the current `--batch-size 512` may throttle prefill. Use the measured live-digest prefill median of 34.23 tok/s, range 29.24-37.92, spread 8.68 from run `32648218952`, not the older derived 12.1 tok/s figure. |
| `no_startup_warmup` | restore `--no-warmup` | Pending reversal check. PR #24 already made startup warmup the digest default after a golden-set check. The harness records server startup and shard wall-clock separately. |
| `flash_attention_on` | `-fa on` | Pending. Different attention math is allowed only if every golden `output_digest` is unchanged. |
| `load_mode_mmap_mlock` | `-lm mmap+mlock` | Pending. Hypothesis: pinning the 4.68 GiB weights may avoid page-out. The harness records RSS and cgroup memory peak. |
| `kv_q8` | `-ctk q8_0 -ctv q8_0` | Pending. Quantised KV changes numeric paths. It is rejected outright if the digest map changes. |
| `np2_inflight` | `-np 2` plus two in-flight workers and `-c 16384` | **Dead, 2026-08-25.** Its prerequisite was whether aggregate decode rises at all with a second sequence. It rises 1.055x against a 1.4x gate, worth about 1.9 percent of a run's wall-clock ([Parallel decode on 4 vCPU](#parallel-decode-on-4-vcpu)). The row stays so nobody asks the question twice. |
| `prio_poll` | `--prio 2 --poll 100` | Pending. Hypothesis: higher priority and polling may help after install work stops competing for CPU. |
| `threads` | `--threads N` | Rejected at the screen. Run `32672629352`: the VM exposed 2 cores x 2 SMT threads = 4 logical CPUs. Eight workers were slower at every prompt length and 16% slower at decode, so production stays at 4 and the server A/B does not run. |
| `threads_batch` | `-tb N` | Pending. Only worth interpreting if `batch2048` shows prefill is the bottleneck. |

The current llama-server verbosity emits no `kv cache rm` lines, so this harness
does not claim to observe prompt-cache reuse directly. Absence of that line is a
logging limit, not evidence that reuse did or did not happen.

## Parallel decode on 4 vCPU

**Measured 2026-08-25. The gate was 1.4x. The measurement is 1.055x. Parallel
decode on 4 vCPU is dead.** A second sequence buys 5.5 percent more aggregate
decode, worth about 1.9 percent of a run's wall-clock. The whole `-np` line of
work stops here: no `-np 2` production arm, no in-flight rewrite of the worker,
no paired A-B-A run. The numbers, and what they do and do not close, are under
[Result](#result).

The question was a single number. Two sequences decoding together share one pass
over the weights, so aggregate decode may rise. On 4 vCPU it may instead just
divide the same cores. `llama-batched-bench` answers it directly: it reports
aggregate decode throughput at each parallel level, in one table, from one
process.

The bench is `Measurements` with `target = batched`, and it ran once, as run
`32855163822`. The arm lives in `.github/workflows/measure.yml`, runs on
`ubuntu-latest` against the same pinned `b10598` build every other llama.cpp job
uses, and repeats the whole bench three times inside one job. All three levels
and all three repeats stay on one host on purpose: prefill spans 3.4x between
runner hosts
([The one-slot production observation](#the-one-slot-production-observation)),
so a matrix would compare hardware and report it as batching.

### The invocation

```text
llama-batched-bench -m backend/models/Qwen3-8B-Q4_K_M.gguf \
  -c 8192 -b 512 -ub 512 -t 4 \
  -npp 900 -ntg 300 -npl 1,2,4
```

`-c`, `-b`, `-ub` and `-t` are read from `config/idhazh.json`
(`models.inference`) when the job runs, so the bench always takes the shape
production takes; the numbers above are what that config held on 2026-08-25.

`-npp 900` and `-ntg 300` are fixed in the workflow. They round the medians the
2026-08-25 ruling took from the two runs in
[The one-slot production observation](#the-one-slot-production-observation) -
prompt p50 877 and generated p50 279 over their 293 requests (145 + 148),
2026-08-24. Read them with two cautions:

- The generated figure agrees with what is recorded elsewhere: summary-token
  medians of 233 to 316 across the four workers of run `32742672105`.
- **The prompt figure is not the whole context a request carries.** That
  measured 1612 to 2694 tokens on the same run. 877 is the shorter quantity -
  what prefill evaluates once the shared system prompt is cached. A bench at the
  full context would leave decode attending over roughly twice the KV, so this
  arm reads the ratio at the light end. It is an operating point, not a
  measurement of the ratio's sensitivity to prompt length.

### Which two numbers a reader divides

The bench prints one row per parallel level:

```text
|    PP |     TG |    B |   N_KV |   T_PP s | S_PP t/s |   T_TG s | S_TG t/s |      T s |    S t/s |
```

`B` is the parallel level. `S_TG t/s` is **aggregate** decode throughput,
`B * TG / T_TG`. It already counts every sequence, so it answers "did the
machine do more work", not "did one sequence go faster".

**The result is `S_TG t/s` on the `B = 2` row divided by `S_TG t/s` on the
`B = 1` row, within one repeat file.** Do that in each of `repeat-1.txt`,
`repeat-2.txt` and `repeat-3.txt`, then take the median of the three ratios. The
job prints that line and writes it to `batched-summary.json` under
`paired_decode_ratios."2_over_1"`, so the reading needs no arithmetic - and the
raw tables ship in the `bench-batched` artifact so it can be checked by hand.

### The gate is 1.4x

Decode is **36.8 percent** of model time: 232.7 minutes prefill against 135.7
minutes decode, run `32742672105`, 2026-08-24. A speed-up in decode alone
therefore buys only decode's share of the run.

| Aggregate decode at `B = 2` | Wall-clock a run saves |
| --- | --- |
| 1.5x | 12.3 percent |
| 2.0x | 18.4 percent |

**Below 1.4x the whole `-np` line of work is dead** and no follow-up row runs. At
or above it, the follow-up earns its runner time.

That table was written before the dispatch. The measurement came in at
**1.055x**, which is 1.9 percent: [Result](#result).

### What this bench does not settle

- **Not prefill.** `--ubatch-size 512` already hands a 512-column GEMM to 4
  threads, and two concurrent prefills share those same 4 threads. There is no
  headroom to win. `S_PP t/s` is recorded for completeness and is not an
  argument for anything.
- **Not a second mechanism.** "One request decodes while another prefills" is
  the same shared weight pass as batched decode. Counting continuous batching
  separately would count this gain twice.
- **`B = 4` is a read, not a target.** The bench gives it away free. Four
  sequences at `--threads 4` oversubscribe 4 vCPU, so that row describes the
  shape of the curve rather than a setting worth adopting.
- **Not the ratio at any other prompt length.** The bench runs one operating
  point: 900 prefill tokens and 300 generated. The direction of that untested
  sensitivity is known even though its magnitude is not - reading 5 under
  [Result](#result) states it.

### Result

| Host | Date | `B = 1` | `B = 2` | `B = 4` | `B = 2` / `B = 1` | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| GitHub-hosted `ubuntu-latest`, AMD EPYC 9V74, 4 vCPU, 15 GB | 2026-08-25 | 5.77 tok/s, spread 0.17 | 6.07 tok/s, spread 0.07 | 6.54 tok/s, spread 0.04 | **1.055**, spread 0.022 | **dead** |

Run `32855163822`, artifact `bench-batched`. The host is 2 cores x 2 SMT threads
in 1 socket and 1 NUMA node, L3 32 MiB, under a Microsoft hypervisor with AMD-V,
`ubuntu24` image `20260816.277.1`. llama.cpp `b10598`, archive sha256
`d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c`,
`llama-batched-bench` sha256
`3b70e62c5c5cf43c8c436622a845ad4b80c01837d6ba3a10c90e39b219bbd2ab`.
`Qwen3-8B-Q4_K_M.gguf`, 5,027,783,488 bytes, sha256
`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`, from
`Qwen/Qwen3-8B-GGUF`, fetched fresh (`gguf_cache_hit=false`). Settings:
`n_ctx 8192`, `n_batch 512`, `n_ubatch 512`, `threads 4`, `-npp 900`,
`-ntg 300`, `-npl 1,2,4`, 3 repeats, gate 1.4.

Aggregate decode, `S_TG t/s`, and the paired ratios each repeat produced:

| Quantity | Repeat 1 | Repeat 2 | Repeat 3 | Median | Spread |
| --- | --- | --- | --- | --- | --- |
| Decode, `B = 1` | 5.65 | 5.77 | 5.82 | 5.77 | 0.17 |
| Decode, `B = 2` | 6.07 | 6.07 | 6.14 | 6.07 | 0.07 |
| Decode, `B = 4` | 6.58 | 6.54 | 6.54 | 6.54 | 0.04 |
| `B = 2` / `B = 1` | 1.0743 | 1.0520 | 1.0550 | **1.055** | 0.022 |
| `B = 4` / `B = 1` | 1.1646 | 1.1334 | 1.1237 | 1.133 | 0.041 |

Aggregate prefill, `S_PP t/s`: 11.98 at `B = 1` (spread 0.11), 11.96 at `B = 2`
(spread 0.05), 11.96 at `B = 4` (spread 0.04).

Five readings.

**1. The gate fails by a wide margin.** 1.055 against 1.4. The three repeats
spread 0.022, so this is not a sample that wants to be bigger. The measurement
is tight and the answer is no.

**2. What it is worth in wall-clock: about 1.9 percent.** Decode is 36.8 percent
of model time - 232.7 minutes prefill against 135.7 minutes decode over 368.4
minutes total, run `32742672105`, 2026-08-24. At 1.055x, decode takes
`135.7 / 1.055 = 128.6` minutes, so the run saves 7.1 minutes of 368.4. That is
1.9 percent. The table above wanted 12.3 percent at 1.5x.

**3. Prefill is flat, exactly as predicted.** 11.98, 11.96 and 11.96 tok/s at
`B = 1`, `2` and `4`, spreads of 0.11 or less. `--ubatch-size 512` already hands
a 512-column GEMM to 4 threads, so two concurrent prefills share those same 4
threads and there is no headroom to win. That prediction was written into
[What this bench does not settle](#what-this-bench-does-not-settle) before the
dispatch, and the measurement agrees with it. The reasoning holds and can be
reused.

**4. No parallel level on this runner clears the gate.** `B = 4` reaches 1.133x,
worth 4.3 percent of wall-clock by the arithmetic in reading 2, and it
oversubscribes 4 vCPU to get there. The curve is flat, not merely short at
`B = 2`. That closes the question, not only the `-np 2` case.

**5. What it does not settle, and which way the gap points.** The bench ran one
prompt length, 900 prefill tokens, and one generation length, 300. The whole
request on run `32742672105` measured 1612 to 2694 tokens, so a bench at full
context would leave decode attending over roughly twice the KV. Batching
amortises the pass over the weights; it does not amortise attention over each
sequence's own KV. More KV per generated token therefore makes the ratio worse,
not better. The magnitude of that sensitivity is unmeasured. Its direction is
not, and it strengthens the ruling.

**What is cancelled - not deferred.**

- The `np2_inflight` candidate in
  [llama-server runtime sweep](#llama-server-runtime-sweep).
- Rewriting the worker to keep two requests in flight.
- A paired A-B-A production measurement of `-np 2`.

Reopening any of them needs a new reason: different hardware, a different
runtime, or a mechanism this bench did not test. A repeat of this bench on this
runner is not a reason. `-np 1` is a separate question about slot count and KV
layout, and this result says nothing about it.

One row per dispatch. Take the host from `hardware.txt`, the date from
`batched-summary.json`, each level's median and spread of `S_TG t/s` over the
three repeats from `aggregate_by_parallel_level`, the median paired ratio and
its spread from `paired_decode_ratios`, and `alive` or `dead` against the 1.4x
gate.

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

### The prerendered page, on the wire

Hardware: Intel Core i7-1265U, Windows, node 24.12.0. Date: 2026-08-26. Method:
`gzip -9` over each prerendered `index.html` in `frontend/build`, heaviest page
per route class. One tree, six published days, built three times.

These are the numbers behind `page_weight.ceilings_bytes` in
`config/idhazh.json`, which
[../how-to/run-the-gates.md](../how-to/run-the-gates.md) explains.

**Superseded 2026-08-26: only `/404` and `/evals/` are still enforced.** The
`/archive/` and `/console/` ceilings below were removed from the committed
config after they behaved as the countdowns this section already documents -
firing on ordinary publishes and being raised to silence them rather than
catching any regression. Both routes grow with the published corpus and the
ledger, so their growth is covered by the marker count in
`frontend/tests/payload-weight.spec.ts` and, for `/archive/`, by its own plan.
The tables that follow stay as the dated record of what those ceilings were and
why a fixed byte number could not hold them (Rule #10).

| Route | Build 1 | Build 2 | Build 3 | Range | Ceiling committed |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/404` | 1,060 | 1,062 | 1,062 | 2 | **1,127** |
| `/evals/` | 2,411 | 2,408 | 2,411 | 3 | **2,475** |
| `/console/` | 123,266 | 123,260 | 123,265 | 6 | **123,330** |
| `/archive/` | 1,124,597 | 1,124,599 | 1,124,596 | 3 | **1,124,663** |
| `/` | 229,772 | 229,772 | 229,772 | 0 | not capped |
| `/<date>/` | 396,993 | 396,995 | 396,995 | 2 | not capped |
| `/<date>/<topic>/` | 395,866 | 395,867 | 395,869 | 3 | not capped |

Each ceiling is the heaviest observed build plus 64 bytes, and the 64 is the
noise floor already derived in `frontend/bundle-baseline.json`. **A ceiling
inside its own noise floor is a coin toss, not a measurement**: the range above
is up to 8 bytes over three builds because SvelteKit stamps a version string
into the markup and different digits compress differently, so a ceiling set at
exactly the heaviest build would fail on a rebuild of an unchanged tree. 64
bytes is 8x the widest range measured here, and the regression these ceilings
exist to catch is 313,000 bytes, so the allowance costs the gate nothing. The
`/404` ceiling keeps the 1,063 seen on an earlier tree the same day rather than
tightening onto 1,062.

**Confirmed on node 22, which is what CI runs.** Same tree, node 22.23.2 win-x64
from `nodejs.org/dist`: `/404` 1,061, `/evals/` 2,413, `/console/` 123,265,
`/archive/` 1,124,602. Every route stays under its ceiling with 61 to 66 bytes
spare, so the toolchain moves these numbers by less than the noise floor
absorbs. The JavaScript ratchet is the part that does care: on node 24 the `/`
route reads 65 bytes under its node-22 record, one byte outside the +/-64
tolerance, so `npm run bundle-gate` fails locally on node 24 for a reason that
is not the change.

**The last three rows are deliberately uncapped.** A day page weighs what the
day published, so a number over it would cap the news rather than catch a
regression. `frontend/tests/payload-weight.spec.ts` covers those by counting a
marker instead, which is the same promise in a unit that does not move when the
pipeline publishes.

**A ceiling here fires on a published day, and that was watched happening
within the hour.** The table above is the second measurement. The first, taken
on the same day against the same tree less than an hour earlier, read
`/archive/` 1,022,379 and `/console/` 114,161. Between the two, `digest:
2026-08-26` re-ran the day and grew `frontend/public/digest/2026/08/26/digest.json`
from 380,272 to 727,978 bytes. `/archive/` rose 102,222 bytes and `/console/`
9,105, and `npm run bundle-gate` failed on both.

`/archive/` inlines every committed day to feed the on-device search, so it
grows about 170 KB per published day: 822.0 KB over five days on 2026-08-26
(PR #119, same method), 1,022.4 KB over six, 1,124.6 KB after that day was
re-run. `/console/` grows with the ledger its charts read, and plateaus once the
prerendered window is full. Neither ceiling is a steady bound. **When one fires
on a publish, the fix is the archive plan under `TODO/`, not a bigger number.**

### The vector backfill, and the one raise the archive plan cannot absorb

Hardware: Intel Core i7-1265U, Windows, node 24.12.0, onnxruntime 1.29.0. Date:
2026-08-26. Method: as above, three builds of one tree.

The backfill filled every closed day's vectors, and 1,175 new vectors are bytes
`/archive/` carries. The ceilings were raised, and this is the one case the
"archive plan, not a bigger number" rule above does not cover: that plan is
blocked on this backfill by its own preconditions, so it cannot land first.

Taken on the final rebased tree, seven published days:

| Route | Build 1 | Build 2 | Build 3 | Range | Ceiling committed |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/404` | 1,061 | 1,061 | 1,059 | 2 | **1,127** (unchanged) |
| `/evals/` | 2,411 | 2,411 | 2,406 | 5 | **2,475** (unchanged) |
| `/console/` | 136,702 | 136,708 | 136,708 | 6 | **136,772** |
| `/archive/` | 1,675,982 | 1,675,983 | 1,675,984 | 2 | **1,676,048** |

**Two causes, and they are not the same size.** The backfill's own share was
isolated an hour earlier, on the tree before the last rebase, by building
`origin/main` untouched and then building it again with the repair applied:

| Route | Ceiling before | `origin/main` untouched | With the backfill | The backfill's share |
| --- | ---: | ---: | ---: | ---: |
| `/archive/` | 1,124,663 | 1,213,246 | 1,583,734 | **+370,488** |
| `/console/` | 123,330 | 129,598 | 129,602 | **+4** |

So `/archive/` was already 88,583 bytes over its ceiling and `/console/` 6,268
over, on a tree nobody had touched - the scheduled pipeline published more of
2026-08-26 after PR #126 measured them, which is the countdown behaviour that
section describes, watched a third time. The CI `site` job was already failing
on `main` at 6535e52 for exactly this, before this row existed. The gap between
1,583,734 and the 1,675,984 in the table above is the same countdown running
again during the row: `digest: 2026-08-26` grew the live day from 385 items to
505 while the gates were running. **A ceiling measured before the final rebase
is already wrong.**

370,488 bytes for 1,175 vectors is 315 bytes a vector on the wire, against 512
base64 characters raw - so gzip returns about 38 percent of what base64 costs.
That figure sizes the archive plan's shards and replaces its 35 percent
estimate. **It has since been measured directly**, over the vectors themselves
rather than inferred from how much the page around them grew: 322.55 bytes for
the same base64 shape and 249.82 for a raw `.bin`
([Sizing the archive index](#sizing-the-archive-index)). Quote those.

**A day page carries its own vectors and never reads them.** `/<date>/` went
from 396,997 to 581,552 bytes gzipped over the same backfill - 184,555 bytes a
reader downloads to read one day's stories. Search lives on `/archive/`; the
in-page filter on a day is a lowercased substring test that needs no vector at
all. Nothing was measuring this before, because a day route is deliberately
uncapped and the block was nearly empty. This is a defect in the day route's
load, not in the backfill: a day payload the archive reads whole is the same
file the day page renders, and only the archive needs the block.

**What a reader pays.** `/archive/` is 1.68 MB gzipped. That is the cost of
holding the whole corpus on one page, and it is the reason the archive plan
exists rather than a reason to leave the corpus empty: before the backfill,
1,175 of the 1,614 items a reader can search for had no vector at all, so the
page was heavy AND could not find them.

### The encoder reproduces itself, and the committed days did not

Hardware: Intel Core i7-1265U, Windows, onnxruntime 1.29.0. Date: 2026-08-26.
Method: decode each committed vector, re-encode its item's `title. summary`
through `idhazh.embed`, and compare - cosine on the decoded pair, and the item's
top-10 neighbours within its own day computed from each side.

| Day | Vectors compared | Cosine min | Cosine median | At or above 0.9999 | Byte-identical | Max byte delta | Top-10 moved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-08-21 | 4 | 0.992538 | 0.994693 | 0/4 | 0/4 | 2 | 0/4 |
| 2026-08-22 | 10 | 0.991415 | 0.993853 | 0/10 | 0/10 | 3 | 6/10 |
| 2026-08-23 | 137 | 0.988646 | 0.993482 | 0/137 | 0/137 | 3 | 134/137 |
| 2026-08-24 | 145 | 0.987867 | 0.993621 | 1/145 | 1/145 | 3 | 138/145 |
| 2026-08-25 | 143 | 0.989480 | 0.993632 | 0/143 | 0/143 | 3 | 135/143 |
| **2026-08-26** (CI wrote it that day) | 80 | 0.996260 | **1.000000** | 58/80 | 54/80 | 2 | not measured |

The last row is the control, and it is what makes the other five readable. A
Windows re-encode reproduces the day CI had written hours earlier at a median
cosine of exactly 1.000000, with 54 of 80 vectors byte-identical - so the
machine is not the variable. Every closed day predates `a995b18`, the commit
that stopped `encode` padding its input and batching it, so those vectors carry
an arithmetic the browser's query encoder no longer uses. That is why a short
day is re-encoded whole rather than topped up.

After the repair, the same test over the repaired days reads cosine 1.000000,
60 of 60 byte-identical, maximum byte delta 0 and zero rank movement on each of
2026-08-23, 2026-08-24 and 2026-08-25. The only vectors still below the bar are
the 14 on 2026-08-21 and 2026-08-22, which already had one for every item they
earned and were therefore skipped.

Encode cost: 0.16 s an item, one sequence per forward pass. 1,602 items in
511 s, single-threaded, on a loaded machine.

#### The console section, on top of that raise

Two more runs of 2026-08-26 landed after PR #126 set the first ceilings, and the
console draws the ledger they append to. Six builds, same hardware, same method,
`origin/main` at `85fbc16`:

| Tree | `/console/` | `/archive/` |
| --- | ---: | ---: |
| `origin/main` source over the payload at `bd1b3c9` | 123,265 | 1,124,600 |
| `origin/main` minus the Charts table (#122) | 135,784 | 1,306,343 |
| `origin/main` | 136,704 | 1,306,339 |
| `What the model did`, build 1 | **137,501** | 1,306,338 |
| `What the model did`, build 2 | 137,494 | 1,306,343 |
| `What the model did`, build 3 | 137,496 | 1,306,341 |

**The first row is the control.** It puts `origin/main`'s frontend source over
the payload as it stood at `bd1b3c9` - the commit that set the ceilings - and
reads 123,265 against the 123,266 recorded above, one byte apart. The frontend
source is byte-identical between `bd1b3c9` and `origin/main`, so that row varies
the payload and nothing else. Without a control that reproduces the number being
replaced, a re-measurement cannot be told apart from a different measurement.

The 14,235 bytes between the ceiling #126 set and the one this measurement asks
for split two ways:

| What the bytes buy | Bytes | Share |
| --- | ---: | ---: |
| Two further runs of 2026-08-26 in the ledger the console draws | 13,439 | 94.4% |
| The `What the model did` section | 797 | 5.6% |
| The Charts table (#122) | 0 | already inside the old ceiling |

**The Charts table is not part of the raise.** It costs 920 bytes at that
payload, and none of them are new: #122 landed before #126 measured 123,266, so
the old ceiling already carried it. Between that measurement and this one,
`run.json` for 2026-08-26 went from 2 runs to 4, `telemetry/2026-08.csv` from
2,393 rows to 2,713, and that day's item count from 273 to 505. The console
draws a mark per item, so its document grows with the day's own re-runs, which
is what the fourteen kilobytes are.

**Re-measured after the final rebase**, over the seven published days and the
backfilled vectors, on the tree that carries both:

| Tree | `/console/` | `/archive/` |
| --- | ---: | ---: |
| `origin/main` source, same payload | 136,707 | 1,675,980 |
| `What the model did`, build 1 | 137,502 | 1,675,978 |
| `What the model did`, build 2 | **137,503** | 1,675,982 |
| `What the model did`, build 3 | 137,496 | 1,675,982 |

The committed ceiling is 137,503 + 64 = **137,567**. The section costs 796 bytes
here against 797 on the tree before the rebase, so its own figure is stable
while everything under it moved by fourteen kilobytes - which is the point of
measuring the two separately.

**`/archive/` is untouched by the section.** It reads within 2 bytes of the
`origin/main` build over the same payload, inside the spread over three builds
of one tree, and stays under the 1,676,048 the backfill row set.

### Days to the 1 GB Pages ceiling

The image rows below are historical. They were the arithmetic that made Row #9's
retention question urgent, and they are kept because the ordering they revealed
still holds for any raster we ever add. **Since 2026-08-23 the live scenario is
the last row**: images do not fit the runner, so no run produces one
([Images do not fit the runner](#images-do-not-fit-the-runner)).

Every row divides 1 GiB (1,048,576 KB) by that scenario's daily bytes, starting
from an empty site. The image rows are unmeasured arithmetic from 2026-08-21.
The last row is measured.

| Scenario | KB/day | days to 1 GB |
| --- | --- | --- |
| PNG, an image on every item | 8,537 | 123 (4 months) |
| WebP, an image on every item | 1,567 | 669 (22 months) |
| WebP, an image on one item in three | 547 | 1,917 (5.25 years) |
| **no images - what actually ships** | **1,767** | **593** |

**Measured 2026-08-25** on a developer machine (i7-1265U, Windows), by summing
every file in `frontend/public/digest/2026/08/24/`, the largest committed day.
That is 1,809,818 B: `digest.json` at 1,570,461 B (1,533.7 KB), 20 rendered
SVGs at 227,711 B, and `run.json`. n=1. The four other committed days measure
15.8, 40.4, 387.1 and 1,466.3 KB, so the spread across days is the day itself -
4 items against 731 - and not measurement error.

**The old 37 KB/day and 28,340 days were wrong by 48x.** 37 KB was a 17-item day
priced from the 2.2 KB-per-item fixture estimate, and the day has since grown to
731 items. 28,340 days was 77 years of headroom; the measured figure is under
two.

Two corrections a reader of that row needs:

- **The site is not empty.** The whole build measured 133.8 MB on 2026-08-25
  ([First-load JavaScript per route](#first-load-javascript-per-route)), most of
  it the committed sentence-encoder under `frontend/static/` at 45.3 MB. Against
  the remaining headroom, 1,767 KB/day is **516 days**, not 593.
- **1,767 KB/day is not a growth rate yet.** It is one day's bytes, and days
  have run 4, 10, 147, 731 and 581 items. Quote it as the current worst day, and
  re-measure over a longer stretch before anyone plans against it.

The ordering of the levers falls straight out of this: encoding buys 5.6x,
honouring the visual rule buys another 2.9x, and retention is what remains
after both. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md).

### Where the alarm fires, and what it buys

`retention.site_budget_mb` is the size at which a run logs a warning. It is an
alarm and not a gate: it fails no build and deletes nothing
([../concepts/config.md](../concepts/config.md)). This section is the only home
for why it sits where it does.

**Derived from the table above, not measured separately.** Days of warning is
`(1024 - alarm_mb) * 1024 / KB_per_day`, on the same binary megabyte the code
uses. Whole days, rounded down - a partial day is not a day of warning.

| Alarm point | Headroom | PNG every item (8,537) | WebP every item (1,567) | WebP one in three (547) | no images (37) |
| --- | --- | --- | --- | --- | --- |
| 600 MB | 424 MB | 50 | 277 | 793 | 11,734 |
| 700 MB | 324 MB | 38 | 211 | 606 | 8,966 |
| **800 MB (shipped)** | **224 MB** | **26** | **146** | **419** | **6,199** |
| 900 MB | 124 MB | 14 | 81 | 232 | 3,431 |
| 1000 MB | 24 MB | 2 | 15 | 44 | 664 |
| 1023 MB | 1 MB | 0 | 0 | 1 | 27 |

**The target is 14 days under the fastest measured growth, and the target is a
judgement (Rule #10).** Nothing here measures how long one maintainer takes to
read one issue, so nothing here can ground it. Two things around it are
measured, and they bound the window rather than set it: the pipeline runs five
times a day, so the site is measured every four hours and the alarm is never
more than a few hours late, and the fix - a config edit and a redeploy - costs
about 25 minutes of CI ([CI and publish wall-clock](#ci-and-publish-wall-clock)).
Every remaining day in the window is a person noticing. Fourteen days is chosen
so a maintainer can be away for a week and still have a week to act. That is a
statement about a person, and it is labelled as one.

**The shipped 800 MB clears the target 1.9x, so the number stays.** It buys 26
days at 8,537 KB/day, and the two neighbours say why it is not moved: 900 MB
lands exactly on the target with no margin under a rate observed once, and
600 MB buys 24 more days in a scenario that does not exist while reading as
"nearly full" on a site that is not.

**Derive against the fastest measured growth, not the live one.** The live rate
is 37 KB/day, which puts the alarm 18,438 days away from the current 133.8 MB
build - about fifty years. An alarm sized on that rate would be sized on the
assumption that nothing ever changes, which is the one day an alarm exists for.
The reverse limit is just as real: 8,537 KB/day is the fastest rate that has
been measured, not the fastest that is possible, and a growth faster than any
row above needs a new measurement and a re-derivation before the alarm point can
be said to cover it.

**Why the alarm point cannot be checked by size alone.** A test that only asks
whether the alarm sits below 1,024 MB passes at 1,023 MB, which is the last row
of the table and zero days of warning. `backend/tests/test_retention.py` pins the
days instead, against the rates above.

## Sizing the archive index

Four numbers the archive plan needs before it can choose a shape. All four were
estimates. These replace them, and two of them change what the plan assumed.

Hardware: Intel Core i7-1265U, Windows 11, 12 logical CPUs, CPython 3.12.12,
node 24.12.0. Date: 2026-08-26. Method: `backend/utilities/index_sizing.py`,
which reads every committed day under `frontend/public/digest/`, plus one
`curl` pass against the live Pages origin for the compression question. Corpus:
the six committed days at digest-tree commit `d0eed4e` (`HEAD` `6ae7128`) -
**2,121 items, 2,119 of which carry a vector, 99.91 percent.** Days ran 4, 10,
147, 731, 724 and 505 items, so items a day is 353.5 +/- 342.2 and the spread
is the corpus growing, not measurement error.

**The sha is part of the measurement.** A byte count taken against
`frontend/public/digest/` goes stale within the hour, because the scheduled
pipeline rewrites a day and pushes it.

### GitHub Pages compresses an octet-stream, and it never sends brotli

The question was whether a raw `.bin` sibling file transfers at raw size. It
does not. Each row is one `curl` GET against `https://miztiik.github.io/yen-idhazh/`,
once with `Accept-Encoding: gzip, br, zstd` and once with `identity`, on
HTTP/1.1. Deterministic bytes, so no spread; n=1 per row.

| Asset | `Content-Type` | `identity` bytes | Bytes with encodings offered | Returned | Saved |
| --- | ---: | ---: | ---: | --- | ---: |
| `/` | `text/html` | 1,237,958 | 418,637 | `gzip` | 66.2% |
| `tokenizer.json` | `application/json` | 711,661 | 209,932 | `gzip` | 70.5% |
| **`model_quantized.onnx`** | **`application/octet-stream`** | **22,972,370** | **16,222,259** | **`gzip`** | **29.4%** |
| `ort-wasm-simd-threaded.jsep.wasm` | `application/wasm` | 21,596,019 | 5,179,184 | `gzip` | 76.0% |

**Brotli is never served.** `Accept-Encoding: br` on its own returned all
711,661 bytes with no `Content-Encoding` header at all; `br, gzip` returned
gzip. So the fallback the plan reserved - a committed pre-compressed file
decoded with `DecompressionStream` - is not needed for an octet-stream, and
brotli figures below are for the record rather than for the wire.

**The edge compresses at level 5, and that is now the unit these numbers use.**
Fastly served the 22,972,370-byte encoder as 16,222,259 bytes. Local `gzip -5`
of the same file gives **16,222,259 - the same number to the byte** (`-1` gives
16,638,186, `-6` gives 16,217,077, `-9` gives 16,212,805). Every page-weight
figure elsewhere on this page is `gzip -9`, which is the gate's unit; a transfer
figure has to be level 5, and both are reported below so the two can be read
against each other.

### What the committed int8 vectors actually compress to

Deterministic file arithmetic over the 2,119 committed vectors, so the spread is
zero. Both shapes are built from the same bytes: `.bin` is raw int8 laid end to
end, and `json` is the same vectors as base64 inside a JSON object keyed by
date and item id, which is what a day payload carries today.

| Shape | Raw bytes | Raw per item | `gzip -5` | Per item | `gzip -9` per item | brotli-11 per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **`.bin`, raw int8** | 813,696 | 384.00 | **529,365** | **249.82** | 249.82 | 229.00 |
| base64 inside JSON | 1,156,054 | 545.57 | 683,493 | 322.55 | 322.35 | 301.29 |

**The vectors compress by 34.9 percent, and the plan's "about 35 percent" was
right.** 813,696 raw becomes 529,365 on the wire. The plan's earlier claim that
they do not compress at all was wrong by a third of the file.

**gzip level does not matter for the `.bin` and does for the text.** `-5` and
`-9` give 529,365 bytes for the raw int8 either way - quantised embedding bytes
are close enough to random that the extra search finds nothing - while the
browse entries below cost about 2.7 percent more at level 5 than at level 9.

**The decision this settles: a raw `.bin` transfers 22.5 percent less than
base64 inside JSON, not 40 percent.** 249.82 bytes an item against 322.55. On a
month at the structural ceiling below that is 5.72 MB against 7.38 MB, so the
saving is 1.66 MB.

**And the plan's stated failure mode was backwards.** It expected compression to
protect the `.bin` margin and feared the margin would collapse to about 10
percent without it. Uncompressed the gap is 29.6 percent (384.00 against
545.57); compressed it is 22.5 percent. gzip claws back part of what base64
wastes, so compression **shrinks** the advantage rather than creating it. The
margin never approaches 10 percent and never reaches 40.

**The comparison is fair on keys.** The JSON form pays for its own keys because
it needs them; the `.bin` pays for none because the browse index already names
every item in order, and an ordinal costs nothing.

**The per-item rate holds as the blob grows**, which is what lets it be applied
to a month larger than the whole archive. Over a quarter, a half and all of the
corpus: 249.56, 249.65 and 249.82 gzipped bytes a vector - a drift of 0.1
percent across a 4x range.

### Items a month, observed and at the structural ceiling

Two rates, because only one of them is a design input. The observed rate is what
six committed days did. The structural ceiling is the cron in
`.github/workflows/digest.yml` - `20 2,6,10,14,18 * * *`, **five slots a day** -
times `run.safety_ceiling_per_run` in `config/idhazh.json`, currently **160**.
The ceiling is a crash guard rather than an editorial cap
([../architecture/sources/freshness.md](../architecture/sources/freshness.md)),
so it bounds a month without describing one.

A month is 30 days. A browse entry is the real thing, built from real committed
items - item id, date, vertical, title - not an estimated field width.

| Rate | Items a day | Items a month | Browse index (`gzip -5`) | Over 300 KB? | Vector file (`gzip -5`) | Over 4 MB? |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| observed | 353.5 | 10,605 | **482,421** (471 KB) | **yes, 1.57x** | 2,649,341 (2.53 MB) | no, 0.63x |
| structural ceiling | 800 | 24,000 | **1,091,760** (1.04 MB) | **yes, 3.55x** | **5,995,680** (5.72 MB) | **yes, 1.43x** |

Per item, over the whole corpus: a browse entry is **45.49** gzipped bytes flat
(133.31 raw, 44.29 at `gzip -9`, 33.64 brotli). Lifting the date to a key and
dropping the vertical - which is already the item id's own prefix - gives 41.51,
which is 8.7 percent less and still over the trigger at every rate.

**A month browse index is over 300 KB at both rates, and no shape measured gets
under it.** 300 KB buys about 6,750 entries at 45.49 bytes each, which is 19
days at the observed rate and 8 days at the ceiling. So a month shard and a
300 KB index budget cannot both hold; one of the two has to move, and that is a
question for whoever chooses the shard granularity rather than a fact this page
can settle.

**A month vector file clears 4 MB at the observed rate and busts it at the
ceiling.** 2.53 MB against 5.72 MB. The trigger is crossed by the guard's
arithmetic, not by anything six days have done.

**Browse entries and vectors are not the same problem, and the numbers say so.**
A month of browse entries is 471 KB and a month of vectors is 2.53 MB - 5.5
times more - so a design that gives them one shared scope is sized by the
vectors and pays for it in the index. They can be scoped separately at no cost,
because they are separate files either way.

### What the ranking loop costs

Search ranks by an exhaustive dot product over int8 vectors, decoding each one
inside the loop and dropping it (`frontend/src/lib/assist/search.ts`). The
measurement runs `decodeVector` and `cosine` unchanged on **node 24.12.0**,
which is the same V8 a Chromium browser runs.

**Method, and what it does not cover.** Six runs of seven timed repeats, so 42
samples per scope, on a shared developer machine with other agents working. The
committed vectors are indexed modulo the corpus to reach a scope larger than the
archive; per-item work is identical because the loop decodes and scores exactly
one vector per iteration regardless of its content. Not covered: a real browser,
a phone-class CPU, a live DOM competing for the main thread, and the per-day
`searchable` check, the map lookup and the final sort that the real `rank` also
does. **So this is the ranking arithmetic and a lower bound on the whole call.**

| Scope | Vectors | Fastest sample | Slowest sample | Fastest, microseconds a vector |
| --- | ---: | ---: | ---: | ---: |
| 1 month, observed | 10,605 | **74.2 ms** | 219.0 ms | 7.00 |
| 3 months, observed | 31,815 | 224.2 ms | 2,031.2 ms | 7.05 |
| 12 months, observed | 127,260 | 890.1 ms | 2,568.0 ms | 6.99 |
| 1 month, ceiling | 24,000 | **158.9 ms** | 646.8 ms | 6.62 |
| 3 months, ceiling | 72,000 | 476.1 ms | 1,783.2 ms | 6.61 |
| 12 months, ceiling | 288,000 | **1,971.1 ms** | 6,401.9 ms | 6.84 |

**The cost is linear and it is about 6.9 microseconds a vector.** The fastest
per-vector figure varies only between 6.61 and 7.05 across a 27x range of scope
sizes, which is the check that the loop has no term that grows faster than the
count.

**The spread is the machine, not the code.** The slowest sample at each scope is
2.9 to 9.1 times the fastest, and the machine had four other agents building and
testing on it throughout. Take the fastest sample as the uncontended cost and
the slowest as what a busy CPU does to it; every conclusion below survives
either.

**The download is what a reader waits for, by 9x to 30x.** At a 10 Mbit line -
a chosen reference, not a measurement of anybody's connection - the vector file
alone costs:

| Scope | Vector bytes | Fetch at 10 Mbit | Ranking, fastest | Fetch is larger by |
| --- | ---: | ---: | ---: | ---: |
| 1 month, observed | 2.53 MB | 2.1 s | 74 ms | 29x |
| 1 month, ceiling | 5.72 MB | 4.8 s | 159 ms | 30x |
| 3 months, ceiling | 17.2 MB | 14.4 s | 476 ms | 30x |
| 12 months, ceiling | 68.6 MB | 57.6 s | 1,971 ms | 29x |

Even against the slowest contended ranking sample the fetch is still 9x larger
at 12 months. **So a search-scope knob buys download seconds, not compute
seconds**, and one month is the only scope in this table whose first search
starts inside about five seconds on that line.

### What these numbers replace

The `/archive/` page arithmetic further up this section put a vector at 315
bytes on the wire, inferred from how much the whole prerendered page grew when
1,175 vectors landed in it. The direct measurement here is 322.55 bytes for the
same base64-in-JSON shape - 2.4 percent apart, which is the page's own markup
between them. Use 322.55 for a JSON shape and 249.82 for a `.bin`; the 315 was
a good indirect read and is not the one to quote.

## The published ledger

**Measured 2026-08-25** on a developer machine (i7-1265U, Windows, CPython
3.14), over the committed `state/published.csv`. This is deterministic file
arithmetic, so the spread is zero and the hardware matters only for the
in-memory figure at the end.

| Quantity | Value | Method |
| --- | --- | --- |
| Rows | 1,449 | `csv.DictReader` |
| Bytes | 311,325 (304.0 KB) | `stat` |
| Mean row | **214.9 B** | bytes / rows |
| `version` share | 24,633 B, 7.9% | field-width sum, one separator per cell |
| `url_key` share | 94,185 B, 30.3% | same |
| **`canonical_url` share** | **150,937 B, 48.5%** | same |
| `published_on` share | 15,939 B, 5.1% | same |
| `item_id` share | 25,580 B, 8.2% | same |

Projected forward at 214.9 B a row:

| Rows a day | A year of rows | A year of bytes |
| --- | --- | --- |
| 295, the observed mean over five committed days | 107,675 | **23.1 MB** |
| 1,000, the structural ceiling below | 365,000 | **78.4 MB** |
| 200, one run's worth | 73,000 | **15.7 MB** |

The observed mean is 1,473 items over the five committed days of
`frontend/public/digest/2026/08/`: 4, 10, 147, 731 and 581. A five-day mean over
a corpus that went from 4 items to 731 inside it is a description, not a
forecast. The ceiling row is the one to design against.

**What it costs to read.** `ledger.load_published` parses the whole file into a
list of dicts and then folds it into one map. `tracemalloc` peak over the
committed ledger is **1,037,214 B**, 716 B a row, for 1,449 rows. At the
365,000-row structural ceiling that is **261 MB**, or 1.6 percent of the
runner's 16 GB (Rule #2). The per-row figure is CPython 3.14 string and dict
overhead on this machine and will differ on the runner's interpreter build; the
conclusion - that a year of this file is a rounding error against 16 GB - does
not depend on which side of 300 MB it lands.

The plan stage is also the job that loads no model, so this allocation never
sits beside 4.68 GiB of weights.

**`canonical_url` is read by nothing on the read path.** `load_published` reads
`url_key` and `published_on` by name; no other reader exists. It is 104.2 B of
the 214.9 B row, so removing it would save about **11 MB a year** at the
observed mean and 38 MB at the structural ceiling. It is recoverable forever by
joining `item_id` and `published_on` against the day payload's `source_url`.
What it buys is that a person can grep the ledger by address. What that means
for the contract, and why the column stays, is
[../architecture/sources/freshness.md](../architecture/sources/freshness.md).

## The safety ceiling fires on every run

**Measured 2026-08-25** by reading `items_planned` out of every run record in
the five committed `run.json` files under `frontend/public/digest/2026/08/`.
Deterministic; no spread.

| Digest day | Runs | `items_planned` per run |
| --- | --- | --- |
| 2026-08-21 | 2 | 5, 5 |
| 2026-08-22 | 1 | 17 |
| 2026-08-23 | 3 | 17, 17, **200** |
| 2026-08-24 | 5 | **200, 200, 200, 200, 200** |
| 2026-08-25 | 4 | **200, 200, 200, 200** |

`run.safety_ceiling_per_run` moved from 17 to 200 on 2026-08-23. **Every one of
the ten runs since has planned exactly 200**, which is the ceiling value.
`cli._within_ceiling` drops the lowest-scoring stories across every vertical
when the pool is larger, so a plan that lands on the ceiling ten times running
is a plan that was cut ten times running. The job log's
`safety ceiling reached planned=N ceiling=200` line names the pool size directly
and is the reading to take next.

**This is a fact about the guard, not a proposal about the number.** What it
costs the reader, and whether 200 should move, is a `config/` question that this
page does not answer - see
[../concepts/config.md](../concepts/config.md) on why a guard sitting in the
working range stops being a guard.

## First-load JavaScript per route

Hardware: Intel Core i7-1265U, Windows. Date: 2026-08-25. Method: `npm run
build`, then `frontend/scripts/bundle-gate.mjs` gzips each module a route
declares `rel="modulepreload"` at level 9 and sums them - per file, never over a
concatenation. A concatenation is order-sensitive, so the number would move when
the bundler reorders the preloads, and it would under-report the wire cost. The
script is the gate, so the number quoted is the number that fails a build.

**The per-route bytes are deliberately not copied here.** They live in
[frontend/bundle-baseline.json](../../frontend/bundle-baseline.json), one record
per route class carrying the byte count, the date it was measured and a sentence
saying what those bytes buy. Two copies of one number are free to drift
(Rule #4), and the copy the gate reads is the one that decides a build. The
toolchain is pinned in that file, because `gzip -9` is deterministic for given
input bytes: the CPU is irrelevant and the Node major is not.

| Quantity | Value | Basis |
| --- | --- | --- |
| Build-to-build spread, route `/` | **12 B** | Four builds of byte-identical source, 2026-08-25, this repo: 49,193 / 49,198 / 49,198 / 49,205 B. SvelteKit stamps the app version into the entry chunk, so two builds of one tree are never quite the same bytes. A difference smaller than this is not a result. |
| Gate tolerance, every route, both directions | **64 B** | **Derived, not measured**: 5.3x the observed range. Four samples underestimate a true range, so the multiple is the margin. A build that ever fails inside 64 B re-derives this from more builds and more routes rather than nudging it. |
| Node 22 against Node 24, same build | **0 B on all seven routes** | Measured 2026-08-25 on one build, i7-1265U, Windows. Node 22.23.2 (zlib `1.3.1-e00f703`) and Node 24.12.0 (zlib `1.3.1-470d3a2`) summed identically to the byte on every route class. The zlib build hashes differ and the output does not, so a baseline taken on a developer machine reproduces on the CI runner. This is two Node majors, not a proof about a third. |

The whole build is 133.8 MB against the 1 GB Pages ceiling (Rule #2).

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

### What the robots policy cost

#### On the runner (authoritative)

**Measured 2026-08-23** on `ubuntu-latest`, by running the same day twice: run
1 (`32624081323`) on the old policy, run 2 (`32634191910`) on the new one, same
date, same config, same feed list. Comparing two real plan passes is a better
check than any script, because it exercises exactly what runs daily.

| Quantity | Before | After |
| --- | --- | --- |
| Feeds read | 115 | **132** |
| Feeds refused | 31 | **14** |
| Items published | 8 | 9 |
| Eval rows written | 0 | **9** |

**17 feeds recovered.** The 14 that still refuse are the check on the change:
the policy keeps refusing when a host serves a file that says no, and keeps
refusing when nobody answers at all.

The published count moved by only one because the daily cap, not the feed
count, decides how many items a reader gets. What a wider pool buys is
**choice**: 17 items are now selected from a larger candidate set, so the
ranking has more to rank. Feed count is an input to quality, not to volume.

The eval-row column measures a different fault fixed in the same commit: the
scorer had been disabled on every scheduled run, so the ledger had never once
been written by automation. Nine rows is the first time it has.

#### On a developer machine (kept for the IP contrast)

**Measured 2026-08-23** (i7-1265U, Windows), n=1 per feed, against the 26 feeds
run 1 recorded as `robots_denied`, driving the real fetcher.

| Outcome after the change | Feeds |
| --- | --- |
| **Recovered** | **19** |
| Still refused - a served `robots.txt` disallows the path | 2 |
| Still refused - the article itself answered HTTP 403 | 4 |
| Still refused - the host reset the `robots.txt` connection | 1 |

Ten of the nineteen serve no `robots.txt` at all and answered 404. Reading
"no such file" as a refusal was a rule we invented and the host never wrote,
and it was silently costing the digest most of its `business-economy` and
`world` candidates.

This page predicted the runner would recover fewer than 19 because a developer
IP is not a runner IP, and several of the 403s were a WAF answering a
datacentre address. The runner recovered 17. **The laptop over-counted by two,
in the direction predicted** - which is the reason the runner table sits above
this one and the laptop table is kept only for the contrast.

### Why the other items failed

**Measured 2026-08-23** on a developer machine (i7-1265U, Windows), by
re-fetching all 9 failures of run 1 and comparing what the extractor returned
against the prose actually present in the markup.

| Items | Source | Extracted | Cause |
| --- | --- | --- | --- |
| 2 | GitHub release tag | 51, 162 words | The page is a list of binary names. The largest prose block in the markup is GitHub's own "You signed in with another tab" furniture |
| 2 | NBER paper page | 128, 178 words | The extractor returned **the abstract, correctly**. The paper is a PDF |
| 1 | Marginal Revolution | 229 words | The post is 277 words. The extractor got 83% of it |
| 2 | Japan Times | 86, 111 words | Metered paywall |
| 2 | IAEA | never fetched | HTTP 403 at the WAF |

Fetches took **0.45-0.80 s**, and no item failed on a timeout or a retry
budget. Two hypotheses are ruled out by this table: the sources are not slow,
and they are not JavaScript shells hiding their text from the extractor.

**The extractor is behaving correctly.** The 250-word floor is rejecting
short-form sources that were extracted properly - a release tag, an abstract,
a short blog post. That makes the low count a **source-selection** result
rather than an extraction defect, and it is why raising the floor's pass rate
belongs in `config/sources.json` and not in `extract.py`.

### Lead coverage newline boundary

**Measured 2026-08-23** on a developer machine (Windows, Python 3.12.12), by
extracting the 17 committed `tests/fixtures/short-sources/` HTML fixtures with
`to_article()`, comparing the old capitalised-run expression against the fixed
metric, and scoring five hand-written `publish_brief` summaries through
`score.band()` at `hhem = 0.95`. Spread is not available because this is a
deterministic string metric.

| Check | Before | After |
| --- | --- | --- |
| Fixtures with a glued newline entity | 6 of 17 | 0 of 17 |
| Extractable fixtures in the pass | 15 of 17 | 15 of 17 |
| Hand-written `publish_brief` rows moved by the fixed metric | 1 of 5 | 0 remaining wrongly capped |

The glued entities were: `ai2\nglenn matlin`,
`published\nus president donald trump`, `student researcher\nwe`,
`xcframework\nlinux`, `gender-specific parental investment\nwe`, and
`biodiversity loss\nwe`.

| Fixture | Coverage before | Band before | Coverage after | Band after |
| --- | --- | --- | --- | --- |
| `llama-cpp-releases-01` | 0.625000 | high | 0.636364 | high |
| `llama-cpp-releases-02` | 0.857143 | high | 0.857143 | high |
| `marginal-revolution-01` | 1.000000 | high | 1.000000 | high |
| `nber-new-01` | 0.833333 | high | 1.000000 | high |
| `nber-new-02` | 0.000000 | medium | 0.500000 | high |

The committed `state/scores.csv` had 156 rows, but no source-text or summary-text
columns. The stored `coverage` column cannot be recomputed honestly from that
ledger alone, so this pass reports 0 computable re-bands rather than inventing a
movement count.

## CI and publish wall-clock

**Measured 2026-08-23** on GitHub-hosted `ubuntu-latest`. Single observed run
per gate; values are rounded wall-clock durations. Spread is not available for
this row because each gate has one observation.

| Gate | Duration | Spread |
| --- | --- | --- |
| `ci` | about 2 min | n=1; not available |
| `site` | about 2 min | n=1; not available |
| `pages` | about 50 s | n=1; not available |
| `digest` | about 25 min | n=1; not available |

The publish path is the long pole. Orchestrators should not serialize
independent work on these gates; the merge gate still waits for green checks.

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

## The length tier a qualification corpus can actually reach

**Measured 2026-08-26**, one developer machine (Windows, 4 cores), over the
first 150 addresses of that day's run plan - 160 items, itself capped from 206
by `run.safety_ceiling_per_run`. Each address was fetched and extracted exactly
as the pipeline does; **109 extracted, 41 did not** (dead links, robots, no
prose). Bodies counted before `extract.truncation_cap_tokens` cut them.

| Statistic | Words in the source body |
| --- | --- |
| p50 | 548 |
| p90 | 1278 |
| max | 3449 |
| mean | 674 |

Which `summarize.bands` tier those 109 landed in, under each rule:

| Rule the band came from | band 0 (0) | band 1 (60) | band 2 (700) | band 3 (2000) |
| --- | --- | --- | --- | --- |
| post-cap count, shipped until this date | 5 | 67 | 37 | **0** |
| source body, from 2026-08-26 | 5 | 67 | 34 | **3** |

**The top tier was unreachable, and not because of the day.** The post-cap count
cannot pass `int(2500 / 1.3) = 1923` words, so no article of any length could
enter a band that starts at 2000. That is what emptied it in qualification run
32998603233, which died on `band 3 (min_source_words 2000) has 0, needs 3`
before a single quality or safety gate ran.

**The top tier is real but thin: 3 in 109, under 3 in 100.** A whole 160-address
plan yields about 116 extracted articles and so about **3.2 items in the top
tier, against the 3 the corpus definition asks for**. That margin is a quarter of
one article. A qualification run can still come up short on supply, and when it
does the corpus adequacy check names the tier and the run is repeated - which is
what Row #10 says a thin corpus is. It is not a reason to move the boundary.

One address costs **2.1 s** to fetch and extract (317 s over 150). Walking a
whole 160-address plan therefore costs about **5.6 minutes**, or **1.9 minutes
per shard at three shards**, against a 330-minute job bound and a worst shard
measured at 115 minutes. Model calls do not move: the corpus is still
`corpus_per_shard` articles replayed `repeats` times.

**This does not agree with the 2026-08-22 row above, and both are right.** That
one sampled 20 links taken straight off the feeds and found 25 percent above
2000 words. This one sampled 150 addresses of the ranked, deduplicated plan and
found 2.8 percent. They measure different populations - the plan is what a
qualification run draws from, so it is the number that sizes the corpus, and n=20
against n=109 is the other half of the gap.

## The image measurement killed the runner

**Attempted 2026-08-22**, `ubuntu-latest`, the `image` job timing Z-Image-Turbo
on CPU at float32. It ran for 48 minutes inside a 120-minute budget and then:

```
##[error]The runner has received a shutdown signal.
```

That is not a timeout. The job had 72 minutes left. A shutdown signal with time
on the clock is the runner agent being taken down underneath the job, which on a
16 GB machine running CPU diffusion is what memory exhaustion looks like from
the inside.

It settled that float32 does not run, and nothing else. The bfloat16 re-run the
next day is the measurement, and it is in
[Images do not fit the runner](#images-do-not-fit-the-runner) below.

## Images do not fit the runner

**Measured 2026-08-23 on `ubuntu-latest` (4 vCPU, 16 GB), run `32654562728`,
`Tongyi-MAI/Z-Image-Turbo` at bfloat16, 512x512, 9 steps, 4 threads.**

| Quantity | Value |
| --- | --- |
| Model load | 159.2 s |
| Resident memory after load | **9.2 GB** of 16 |
| Denoising step | **527 s**, steps 1-7, spread 528.4 down to 525.9 |
| One 512px image | **~79 min** extrapolated from 7 of 9 steps |
| 768px | never reached |
| PNG bytes, WebP bytes | never reached |

The job was cancelled at step 7 of 9 after 61 min 26 s. A single image at the
smallest useful resolution costs more than the whole `route` job's 60-minute
bound. A day of 149 items would cost about 196 hours, against a 6-hour job limit.

The second candidate is not a candidate. `alpha-vllm/Anima-2.9B` answers
**401 Repository Not Found** from the Hugging Face API - it does not exist. Row
#9's "measure both, choose on cost" gate had one leg from the start.

The earlier float32 attempt on 2026-08-22 (`32565677038`) was killed by a runner
shutdown signal with 72 minutes still on its clock, which on a 16 GB machine is
what memory exhaustion looks like from inside a job. That attempt settled nothing
except that float32 does not run. This one settles the question.

**Consequence: Row #9's ESCALATE trigger fired and the image renderer is
descoped.** Rule #2 says the budget is the platform, not a preference. No step
count or resolution reduction reaches a usable number from 527 s per step: at one
step the image is noise, and at three it is still 26 minutes. Narrative items
publish without a visual, which the pipeline already handles - `none` is the
common and correct answer for nine items in ten.

The harness now prints each step as it lands. Both earlier attempts died before
the image completed and left no number behind them, which is a defect in the
instrument rather than in the model.

## What a job log names

Every `work` shard and the `route` job print six identifying lines before the
stage starts, under `if: always()` so a job that was cancelled or that failed
still names the machine it drew. Until 2026-08-25 `work` printed none of them
and `route` printed the first three, which is why several tables above have to
say the job log did not name the CPU model or the build.

| Line | Answers |
| --- | --- |
| `model name` from `/proc/cpuinfo` | which CPU the job drew |
| `nproc` | how many logical CPUs it saw |
| llama-server `system_info` | the instruction sets the build uses |
| `llama-server --version` | the build the binary reports about itself |
| `sha256sum backend/bin/llama-server` | the exact binary bytes |
| `sha256sum` of the weights file | the exact weight bytes |

The step also echoes `LLAMA_CPP_BUILD`, so a disagreement between the pin and
what the binary says about itself is visible on one screen. The two digests are
what let a number on this page name the bytes that produced it (Rule #10); the
run manifest still records `runtime_build` as a fixed string and does not.

Two more instruments landed beside them.

**The log summary greps `^(srv|slot) `, not a list of expected lines**, plus
both the `n_ctx_slot` and `n_ctx_seq` spellings of the one field llama.cpp has
renamed. A fixed list reports what it expects: the old one looked for a
`kv cache rm` line this build never emits, and that is exactly what hid the
prefix-reuse proof described under
[Reuse settled](#reuse-settled-the-log-did-prove-it-the-grep-hid-it) for two
runs. The step also prints the `f_sim_best` and `f_keep` distribution - n, min,
median, max and ten buckets - because under one slot a reuse loss shows in the
spread rather than in whether the line was printed at all.

**Every `work` shard now samples memory.** `VmRSS` and `VmHWM` for llama-server
and the summed `VmRSS` of every python process, every 15 s, plus
`/sys/fs/cgroup/memory.peak` read at job end. `measure.yml` already recorded
exactly this and the daily path did not, so no run behind any table above says
how close a 16 GB runner came to its limit. The samples upload inside
`runtime-log-<shard>` beside the server log.

The sampler's artifact cost is bounded, not estimated: a row is five
tab-separated fields and at most about 60 bytes. The `work` job's configured
bound is 330 minutes, so one shard writes at most 1,320 rows, about 79 KB; four
shards at most about 317 KB and eight at most about 634 KB - 0.06% and 0.13% of
the 500 MB artifact budget (Rule #2). A 105-minute shard writes about a third of
that. Raising the shard ceiling scales this term with the shard count and leaves
the `items-*` total flat, because the plan is divided between workers rather
than copied to each of them.

## Eight work shards

**Measured 2026-08-25** on GitHub-hosted `ubuntu-latest` (4 vCPU, 16 GB), run
`32869125768` - a `Content refresh` dispatch at `shards = 8` and
`faithfulness = true`, commit `5773762`, eight `work` jobs,
`Qwen3-8B-Q4_K_M.gguf` through `llama-server`, llama.cpp `b10598`,
`n_slots = 1`, `n_ctx_slot = 8192`, `kv_unified = 'false'`.

**The slowest worker halved: 113.1 minutes at four shards, 58.8 at eight.
That is 1.92x, and the last worker is what the rest of the run waits for.**
Doubling the fan-out was expected to buy about 2x, because it halves the work
each shard carries. The measurement is consistent with that. It is not a
controlled proof of it, for the four reasons under
[Not a paired measurement](#not-a-paired-measurement).

The dispatch queued at 15:58 UTC and `plan` did not start until 17:45, 1 h 47
min later, behind a scheduled run. Every figure here is taken from job
timestamps, so that queue is not inside any of them.

### What changed, and what did not

`digest.yml` held the fan-out at four with a regex, `^[1-4]$`, and a matching
`max-parallel: 4`. Both now read eight. Rule #2 allows 20 concurrent jobs, so
four was a choice and not a platform limit. Every shard restores the same cache
key, so the change adds cache restores and model loads, never cache bytes.

The scheduled run is unchanged. It passes no inputs, so it gets the four workers
it has always had - through the plan job's own `SHARDS=4` fallback when this ran,
and through `run.max_parallel` since 2026-08-26. This measurement does not move
it - see
[Does this move the scheduled default](#does-this-move-the-scheduled-default-to-eight).

### The baseline to compare against

Run `32742672105`, 2026-08-24, GitHub-hosted `ubuntu-latest` (4 vCPU, 16 GB),
four `work` jobs, `Qwen3-8B-Q4_K_M.gguf`, llama.cpp `b10598`. Every row is
already on this page under
[Model throughput across the four workers](#model-throughput-across-the-four-workers).

| Quantity | Four shards |
| --- | --- |
| Articles | 149 |
| Items per worker | 34, 35, 39, 41 |
| Aggregate prefill | 10.95 tok/s |
| Aggregate decode | 5.05 tok/s |
| Prompt tokens evaluated | 152,933 in 232.7 min |
| Tokens written | 41,098 in 135.7 min |

Its per-job wall-clock was not on this page. Read from the jobs API on
2026-08-25, it is:

| Job | Four shards, run `32742672105` | Eight shards, run `32869125768` |
| --- | --- | --- |
| `plan` | 3.2 min | 3.2 min |
| slowest `work` | **113.1 min** | **58.8 min** |
| fastest `work` | 83.2 min | 36.5 min |
| `route` | 53.5 min | 41.5 min |
| `assemble` | 0.5 min, success | 1.2 min, **failed** |
| `plan` start to last job end | 170.4 min | 104.8 min |

### The clock, shard by shard

`route` cannot start until the last worker finishes, so the slowest shard is
the one that sets the wall-clock. Everything else in this table is context for
it.

| Shard | Wall-clock | Items given | Items summarized | Cache restore |
| --- | --- | --- | --- | --- |
| `work (0)` | 41.1 min | 25 | 15 | 30 s |
| `work (1)` | 50.7 min | 25 | 16 | 73 s |
| `work (2)` | 48.6 min | 25 | 19 | 41 s |
| `work (3)` | 51.4 min | 25 | 19 | 70 s |
| `work (4)` | 43.1 min | 25 | 19 | 49 s |
| `work (5)` | **58.8 min** | 25 | 21 | 37 s |
| `work (6)` | **36.5 min** | 25 | 19 | 52 s |
| `work (7)` | 55.3 min | 25 | 19 | 37 s |
| All eight | 58.8 min, the slowest | 200 | 147 | 30-73 s, median 45 |

**Items per worker is exactly 25, not the file count.** The eight `items-*`
artifacts hold 494 JSON files between them, and 494 is not the number of items.
Each item writes up to three files - `<id>.article.json`, `<id>.summary.json`
and `<id>.eval.json` - so the count that means anything is the number of
distinct file stems. That is 25 on every shard: 200 article files, 147 summary
files and 147 eval files, and nothing else. The plan job logged the same 200:
`safety ceiling reached planned=221 ceiling=200`, then
`planned date=2026-08-25 items=200 feeds=122`. The 55-to-67 file spread between
shards is how many of each shard's 25 items produced a summary - 15 to 21 - not
a difference in how much work a shard was handed. The fan-out divided the day
evenly, which had to be true before any wall-clock comparison meant anything.

### Which machine a shard drew moved its rate 3.4x

Throughput per shard, from llama-server's own `/metrics` counters in each
`runtime-log-<shard>` artifact: tokens summed and seconds summed, divided once.
Peak resident set is the highest single 15-second sample of llama-server plus
every Python process in that job, from `rss-samples.tsv`.

| Shard | CPU it drew | Prefill | Decode | Peak resident set |
| --- | --- | --- | --- | --- |
| `work (0)` | AMD EPYC 7763 | 11.34 tok/s | 5.25 tok/s | 13.85 GiB |
| `work (1)` | AMD EPYC 7763 | 11.30 | 5.01 | 13.77 GiB |
| `work (2)` | AMD EPYC 9V74 | 10.98 | 5.15 | 13.65 GiB |
| `work (3)` | AMD EPYC 7763 | 11.28 | 4.79 | 13.52 GiB |
| `work (4)` | Intel Xeon Platinum 8573C | **37.50** | 3.29 | 14.33 GiB |
| `work (5)` | AMD EPYC 9V74 | 10.98 | 5.00 | 14.39 GiB |
| `work (6)` | Intel Xeon 6973P-C | **37.71** | 3.48 | 14.06 GiB |
| `work (7)` | AMD EPYC 9V74 | 10.65 | 4.98 | 14.24 GiB |
| All eight | four CPU models | 13.25 | 4.45 | - |

Totals: 149,444 prompt tokens evaluated in 188.0 min, 117,016 further prompt
tokens reused from the slot's prefix (43.9% of all prompt tokens), 41,192 tokens
written in 154.2 min.

**The two Intel hosts prefill 3.4x faster than the six AMD hosts and decode
about a third slower.** Group averages: 37.6 against 11.09 tok/s reading a
prompt, 3.39 against 5.03 tok/s writing a summary. Same day, same build, same
weights, same prompt, same one-slot server, eight jobs running at once - so this
is the most controlled look this project has had at a swing it has been chasing
for a week. It is the same shape as the `route` finding already on this page:
reading speed moves 3x and writing speed moves the *other* way. It is one
observation per CPU model, so it names a suspect rather than proving a cause.

It also means a shard's wall-clock does not follow its reading speed.
`work (6)` drew a fast host and finished first at 36.5 minutes. `work (4)` drew
an equally fast host and still came third at 43.1, because the fast hosts are
the slow writers and writing is where a summary's time goes: `work (4)` spent
28.8 of its 43.1 minutes writing 5,690 tokens at 3.29 tok/s.

### Not a paired measurement

Read 1.92x as consistent with the prediction, never as proof of it. Four things
differ between the two runs besides the shard count:

- **Different days, different articles.** 2026-08-24 against 2026-08-25.
  Neither run chose its own corpus.
- **Different hosts.** The eight shards drew four CPU models and their prefill
  rates span 3.5x within the one run - 10.65 tok/s on the slowest shard against
  37.71 on the fastest. This page already records that the host alone moves
  prefill 3.4x. A two-run comparison sits inside that spread.
- **Different server configuration.** The baseline ran four slots with
  `kv_unified = 'true'`; this run ran one slot with `kv_unified = 'false'`.
- **Different instruments.** The baseline's tok/s came from parsing per-request
  lines out of the server log. This run's came from llama-server's `/metrics`
  counters, which the baseline did not publish.

What *is* close between the two runs is the size of the job the model was asked
to do: **41,192 tokens written here against 41,098 in the baseline, and 149,444
prompt tokens evaluated against 152,933.** Two days apart, the model was asked
for nearly the same amount of work and the slowest worker finished it in a
little under half the time. That similarity is the reason to believe the 1.92x,
not the arithmetic of dividing by two.

### The run did not publish

`assemble` failed 1.2 minutes after `route` finished. **No digest for
2026-08-25 was published from this run.** The day was lost.

The cause is in the commit step and has nothing to do with the fan-out. The
day's published directory already held
`frontend/public/digest/2026/08/25/india-07.svg` from an earlier run, this run
wrote different bytes to the same path, and the rebase onto the moved `main`
stopped on `CONFLICT (add/add)`. The job then reported `could not push the day
after three attempts` and exited 1. That is the published-asset-name defect -
the asset ordinal comes from a per-process counter - and it is being fixed in
its own change.

**All eight `work` jobs succeeded and so did `route`.** Eight shards did not
cause this, and the same day at four shards would have hit the same conflict.
Everything measured above is the `work` phase, which completed.

### `route` is now the larger share of what is left

`route` is not sharded. It ran 41.5 minutes after the last worker finished, and
it stopped itself at its own 40-minute budget with
`routed=93 unrouted=54 mean_ms=26239` - 93 of the day's 147 summarized items
got a visual decision at a mean of 26.2 s each, and 54 got none.

Of the clock after `plan` finishes:

| | `work` | `route` | Sum | `route` share |
| --- | --- | --- | --- | --- |
| Four shards | 113.1 min | 53.5 min | 166.6 min | 32% |
| Eight shards | 58.8 min | 41.5 min | 100.3 min | **41%** |

Halving the workers again would put a 29.4-minute `work` phase beside the same
unsharded `route`: 70.9 minutes, and `route` becomes 59% of it. The first
halving took 66 minutes off the pair; a second would take 29. `route` already
owns more of the remaining clock than any further worker fan-out can give back,
and it is the stage that dropped 54 items.

### Cache, memory and artifacts against Rule #2

**Cache restore is 30 to 73 seconds per shard**, median 45, mean 49 - from the
`Cache weights and runtime` step timing on each job. This page had asserted
about 90 s. Each restore runs inside its own job in parallel with the other
seven, so eight restores instead of four cost the run no wall-clock at all;
they cost about three quarters of a minute inside jobs that run 36 to 59
minutes.

**Cache bytes did not move, and that was the design claim.** All eight shards
restored the one entry `llm-Qwen3-8B-Q4_K_M.gguf-b10598-v3`, 4,943,540,782 bytes
(4.60 GiB). Read on 2026-08-25 after the run, the repository held eight cache
entries totalling 10,585,631,000 bytes against the 10 GB ceiling in Rule #2 -
at the ceiling, but not because of this change. What fills it is a stale 4B
entry under an old key plus duplicated Python and npm entries. More shards
restore the same key and never add a byte.

**Artifacts are 0.33% of the budget.** Nineteen artifacts, 1,740,473 bytes in
total - 1.66 MB against the 500 MB in Rule #2. The eight `items-*` artifacts are
709,603 bytes together and the eight `runtime-log-*` are 83,050; `routes` at
906,169 bytes is the single largest. Doubling the worker count left the
`items-*` total flat, exactly as predicted: the plan is divided between the
workers, never copied to each of them.

**The memory peak is not readable from this run.**
`cgroup_memory_peak_bytes=unavailable` on all eight shards -
`/sys/fs/cgroup/memory.peak` does not exist on a GitHub-hosted runner, so the
step that was meant to answer this printed a placeholder. Not readable, not
estimated (Rule #10).

The RSS sampler beside it did work. llama-server's resident set is 9.0 GiB when
the weights finish loading and climbs to 12.1-13.5 GiB by the end of a job;
adding the Python processes running in the same 15-second sample, the highest
simultaneous total is 13.52 GiB on the lightest shard and **14.39 GiB on
`work (5)`, against the 16 GB the runner has.** Two things that does not say.
Most of that resident set is the memory-mapped weights file, which the kernel
can drop under pressure, so a resident set near the host's memory is not the
same as demand the host cannot meet. And the shard count does not move this
number: each shard is its own runner VM with its own 16 GB, so eight shards are
eight machines rather than more pressure on one. The four-shard baseline
predates the sampler, so there is no four-against-eight memory comparison to
make.

### Does this move the scheduled default to eight?

Not yet, and what blocks it is not the fan-out.

Three of the four conditions this section had set are met. The slowest `work`
job fell from 113.1 to 58.8 minutes. The whole run finished in 104.8 minutes
against the job's `timeout-minutes: 330`. Artifacts and cache bytes are inside
Rule #2. The fourth - every shard's memory peak clear of 16 GB - is unread
rather than failed, and the resident-set figure that stands in for it is a
per-machine number the shard count does not change.

Three things have to hold before `run.max_parallel` moves - the plan job's
`SHARDS=4` fallback when this was written, and the config knob the derivation
clamps by since 2026-08-26:

1. **A day at eight shards has to publish.** This one did not. Raising the
   fan-out on the path a reader depends on, on the strength of a run that lost
   its day at the last step, is the wrong order. The asset-name fix lands first.
2. **A second run at eight, on a different day, that reaches `assemble`.** One
   run cannot separate a fan-out effect from the host lottery this same run
   shows at 3.4x.
3. **`route` gets an answer.** At eight shards `route` is already 41% of the
   clock and it stopped with 54 of 147 items unrouted. Making the workers
   faster while `route` drops a third of the day's visuals moves the failure
   rather than removing it.

Then `run.max_parallel` moves, in its own commit, naming the run it rests on.
This section does not move it.

## Still unmeasured

Each line names the measurement that would settle it. Nothing here may be cited
to justify a design decision.

| Quantity | Current basis | What settles it |
| --- | --- | --- |
| **Archive search latency in a real browser, and on a phone** | **measured on node 24 / V8 at 6.9 microseconds a vector; no browser figure exists** | the ranking clock in [Sizing the archive index](#sizing-the-archive-index) runs the real `decodeVector` and `cosine` on the same engine a browser uses, but with no DOM, no page and no phone. Drive the same loop from a Playwright page over a real day payload, and again on a throttled CPU, so the scope default is chosen against what a reader on a phone feels rather than against a desktop lower bound. |
| **Whether a day at eight work shards publishes** | **the work phase is measured, the day was not published** | run `32869125768` halved the slowest worker and then lost the day when `assemble` hit an asset-name conflict ([Eight work shards](#eight-work-shards)). A second dispatch at `shards = 8`, after the asset-name fix, that reaches `assemble` and commits its day. |
| **How many candidates a run produces before the ceiling cuts it** | **unmeasured; only the post-cut figure of 200 is on record** | `cli._within_ceiling` logs `safety ceiling reached planned=N ceiling=200` whenever it fires, and it has fired on all ten runs since 2026-08-23 ([The safety ceiling fires on every run](#the-safety-ceiling-fires-on-every-run)). Read `N` out of a `plan` job log. Until then nobody knows whether the pool is 210 or 2,100, and that is the number that decides whether 200 is a guard or a cap. |
| **The published site's growth rate over more than one day** | **one day measured: 1,767 KB on 2026-08-24** | the five committed days span 4 to 731 items, so a mean over them describes a corpus that was still growing. Re-read the day-directory totals once the day size has been stable for a fortnight ([Days to the 1 GB Pages ceiling](#days-to-the-1-gb-pages-ceiling)). |
| **Faithfulness scoring seconds per item** | **unmeasured** | **a timed pass over 20 fixture pairs at the three premise lengths; it decides whether the scorer is a census or is sampled** |
| **What makes a route host 21 s or 38 s an item** | **narrowed to the prefill rate, and now to the CPU part; one observation per part** | it is a 3.1x swing in prompt-eval throughput (20.2 to 62.9 tok/s) with the prompt size, the reply size and `n_slots` all ruled out, and decode moving the *other* way. Nothing logged the CPU when those six runs ran. The `work` job shows the same swing, 3.4x with the same inverted decode ([The one-slot production observation](#the-one-slot-production-observation)). Both inference jobs now print the six lines under [What a job log names](#what-a-job-log-names). The first run to use them narrows it further: in run `32869125768` the two `work` shards on Intel Xeon parts prefilled at 37.5 and 37.7 tok/s while the six on AMD EPYC parts prefilled at 10.7 to 11.3, same day, same build, same weights, same prompt, with decode again moving the other way ([Eight work shards](#eight-work-shards)). That is one observation per CPU model, so it names a suspect rather than proving a cause; a `route` job on each part, on the same day, would settle it. |
| **What a sharded `route` job would cost** | **arithmetic only** | four shards divide the stage but each pays the fixed cost and each needs a collision-free asset path. Blocked behind moving the published asset name off a directory-scanned ordinal; not citable until a real matrix run records it. |
| **Whether Qwen3.5 recurrent state preserves incumbent-style prefix reuse** | **unmeasured; Qwen3 incumbent reuse is proven above** | serve the candidate through a real ordered worker and read its LCP/recurrent-state log fields plus evaluated prompt tokens for item 1 and items 2..N; record band crossings separately |
| **`max_output_tokens` and `truncation_cap_tokens` as wall-clock levers** | **unswept** | the `runtime` job in `measure.yml` sweeps llama-server runtime flags only. These two set how much text is prefilled and how much is decoded per item, which is the tail of a run rather than its median. Sweep them the same way: one value at a time, 3 repeats, fixed shard, golden `output_digest` unchanged. |
| Exact complete-request context for the configured summarizer | **unmeasured; 877-879 covers only the system prompt** | render system prompt + source form + title + fences + exact sanitized model-visible text through the embedded chat template, count the generation suffix, add output budget, and record the maximum by band |
| A production day payload | fixture figure above | the first real pipeline run |
| HHEM scoring seconds per item on CPU | unmeasured | lands with the eval harness |
| Whether 1-2 bit quantisation changes the fit | unevaluated | open question 4 in the plan-doc |
| A `work` job's true memory peak | **not readable; the instrument prints a placeholder** | every shard of run `32869125768` wrote `cgroup_memory_peak_bytes=unavailable`, because `/sys/fs/cgroup/memory.peak` does not exist on a GitHub-hosted runner. Read the job's own cgroup path out of `/proc/self/cgroup` and take `memory.peak` from there, or fall back to the lowest `MemAvailable` in `/proc/meminfo` over the job. The RSS sampler's 14.39 GiB high point is a resident set, not a demand ([Eight work shards](#eight-work-shards)). |
| Qwen3.5-9B complete-request tokens and worst-case context | **unmeasured; Qwen3 counts do not transfer** | render system prompt + source form + title + fences + exact sanitized model-visible text through the embedded chat template, count the generation suffix with `Qwen3.5-9B-Q4_K_M.gguf`, add output budget, and record the maximum by band |
| Qwen3.5-9B live non-thinking, schema and canary compatibility | **unmeasured; parser controls exist, candidate behaviour does not** | serve the exact candidate under the configured greedy sampler; run short/medium/long/brief inputs plus all injection canaries; require empty reasoning channels, `finish_reason=stop`, valid schema and repeat-stable published words |
| Whether Qwen3.5-9B summarizes faithfully through our prompt | **throughput measured, quality unmeasured** | first replace the current validation workflow with a cache-safe replay over frozen Article payloads; then require at least `validation_articles` common successful pairs, full attempted denominators, paired metric spread and a pre-registered blind human selector |

## How to add a row here

Run the measurement, then record the quantity, the value, the spread, the
hardware and the date. If a number arrives without those four, it is an
estimate and belongs in the table above rather than in the tables below it.

When a measurement contradicts a design, the design changes - that has already
happened three times on this page.

## See also

- [../../CLAUDE.md](../../CLAUDE.md) - Rule #2 (the runner is the architecture) and #10 (measured, not estimated).
- [github-actions.md](github-actions.md) - the workflows that print and upload the lines above, take these measurements, and how to dispatch one.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the published-size arithmetic these numbers feed.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the published ledger these ledger figures size, and the per-run ceiling.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the rule that decides which ledgers shard.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - the batch-size rule these numbers set.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - the prompt the token count above measures.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the procedure these measurements gate.
- [../how-to/set-up-local-inference.md](../how-to/set-up-local-inference.md) - reproducing the local runs.
