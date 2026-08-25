# Measurements

**Last Updated**: 2026-08-25

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

**These figures do not size a production worker.** `run.shard_size = 5` is not
enforced by `digest.yml`; the workflow divides the whole plan among four worker
jobs. Run `32742672105` measured 34 to 41 items per worker. A current day can be
larger. Size request and job bounds from a measured real worker population and
its worst item, never from five-item arithmetic or the 229-second blend.

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

What remains unmeasured:

- candidate prompt tokens and article-token spread;
- candidate-specific worst-case context and derived seconds per article;
- schema-valid non-thinking output at the configured greedy sampler;
- live prompt-injection canaries and deterministic repeated output;
- quality on frozen Article payloads;
- failure rate, counterweights and blind human review; and
- recurrent-state prefix reuse.

The model card publishes no summarization or faithfulness result. Its reasoning,
instruction-following, coding and long-context tables are a prior and not
evidence for this pipeline.

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
60-minute bound. `run.safety_ceiling_per_run` is 200. The two numbers have never
been consistent, and the runs that fit did so because roughly a quarter of the
plan had no `OK` summary and was skipped. **Improving the summarizer breaks the
router.** That coupling is the defect, not the bound.

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

against `run.safety_ceiling_per_run = 200` and a 50-minute stage budget. The
slow host still cannot finish a maximum day, which is why the stage now stops
itself rather than being killed.

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

Each candidate is still pending unless a later runner artifact records hardware,
date and spread:

| Candidate | Flag under test | Status |
| --- | --- | --- |
| `np1` | `-np 1` | Production observation started 2026-08-24 by user approval. Run `32648218952` established that omitted `-np` selected four auto slots with `n_ctx_slot = 8192` and unified KV. Two full runs were then compared and the comparison had no power: see [The one-slot production observation](#the-one-slot-production-observation). Still pending, because real refreshes are not a controlled A/B. |
| `batch2048` | `-b 2048` | Pending. Hypothesis: the current `--batch-size 512` may throttle prefill. Use the measured live-digest prefill median of 34.23 tok/s, range 29.24-37.92, spread 8.68 from run `32648218952`, not the older derived 12.1 tok/s figure. |
| `no_startup_warmup` | restore `--no-warmup` | Pending reversal check. PR #24 already made startup warmup the digest default after a golden-set check. The harness records server startup and shard wall-clock separately. |
| `flash_attention_on` | `-fa on` | Pending. Different attention math is allowed only if every golden `output_digest` is unchanged. |
| `load_mode_mmap_mlock` | `-lm mmap+mlock` | Pending. Hypothesis: pinning the 4.68 GiB weights may avoid page-out. The harness records RSS and cgroup memory peak. |
| `kv_q8` | `-ctk q8_0 -ctv q8_0` | Pending. Quantised KV changes numeric paths. It is rejected outright if the digest map changes. |
| `np2_inflight` | `-np 2` plus two in-flight workers and `-c 16384` | Pending composite scenario. It is labelled composite because it is not a pure one-flag test. |
| `prio_poll` | `--prio 2 --poll 100` | Pending. Hypothesis: higher priority and polling may help after install work stops competing for CPU. |
| `threads` | `--threads N` | Rejected at the screen. Run `32672629352`: the VM exposed 2 cores x 2 SMT threads = 4 logical CPUs. Eight workers were slower at every prompt length and 16% slower at decode, so production stays at 4 and the server A/B does not run. |
| `threads_batch` | `-tb N` | Pending. Only worth interpreting if `batch2048` shows prefill is the bottleneck. |

The current llama-server verbosity emits no `kv cache rm` lines, so this harness
does not claim to observe prompt-cache reuse directly. Absence of that line is a
logging limit, not evidence that reuse did or did not happen.

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

The image rows below are historical. They were the arithmetic that made Row #9's
retention question urgent, and they are kept because the ordering they revealed
still holds for any raster we ever add. **Since 2026-08-23 the live scenario is
the last row**: images do not fit the runner, so no run produces one
([Images do not fit the runner](#images-do-not-fit-the-runner)).

| Scenario | KB/day | days to 1 GB |
| --- | --- | --- |
| PNG, an image on every item | 8,537 | 123 (4 months) |
| WebP, an image on every item | 1,567 | 669 (22 months) |
| WebP, an image on one item in three | 547 | 1,917 (5.25 years) |
| **no images - what actually ships** | **37** | **28,340** |

The ordering of the levers falls straight out of this: encoding buys 5.6x,
honouring the visual rule buys another 2.9x, and retention is what remains
after both. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md).

## First-load JavaScript per route

Hardware: Intel Core i7-1265U, Windows, Node 24.12. Date: 2026-08-25. Method:
`npm run build`, then `frontend/scripts/bundle-gate.mjs` gzips each module a
route declares `rel="modulepreload"` at level 9 and sums them. Each module is
compressed on its own because that is how it arrives - one response, one
encoding. The script is the gate, so the number that is quoted is the number
that fails a build.

**The measurement has a floor of about 12 B.** Four builds of byte-identical
source produced `/` at 49,193 / 49,198 / 49,198 / 49,205 B. SvelteKit stamps the
app version into the entry chunk, so two builds of one tree are never quite the
same bytes. A difference smaller than this is not a result.

Before is the tree at `8867518`. After adds `d3-scale`, `d3-array` and
`frontend/src/lib/charts/frame.ts`. Both columns are one build; the spread is
the range over four after-builds.

| Route class | Before | After | Spread over 4 builds | Verdict |
| --- | --- | --- | --- | --- |
| `/` | 49,201 B | 49,198 B | 12 B | unchanged |
| `/<date>/` | 49,071 B | 49,068 B | 12 B | unchanged |
| `/<date>/<topic>/` | 49,164 B | 49,161 B | 11 B | unchanged |
| `/archive/` | 44,476 B | 44,474 B | 7 B | unchanged |
| `/evals/` | 41,883 B | 41,881 B | 8 B | unchanged |
| `/404` | 40,925 B | 40,923 B | 6 B | unchanged |
| `/console/` | 54,180 B | 54,179 B | 6 B | unchanged |

Every before-figure sits inside the after-range, so no route gained first-load
JavaScript.

**The console delta is zero by construction, not by arithmetic**: nothing draws
through the frame yet, the module is tree-shaken out of every bundle, and
`scaleLinear` appears in no built file. The dependency is declared, locked and
priced; the bytes are spent by the row that draws through it, against the
ceilings in `bundle-gate.mjs` - the measured baseline above plus 1 KB on a
reader route and 10 KB on the console.

The console's own route chunk is `nodes/4.*.js`: 38,308 B raw, 12,746 B gzipped.
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

## Still unmeasured

Each line names the measurement that would settle it. Nothing here may be cited
to justify a design decision.

| Quantity | Current basis | What settles it |
| --- | --- | --- |
| **Faithfulness scoring seconds per item** | **unmeasured** | **a timed pass over 20 fixture pairs at the three premise lengths; it decides whether the scorer is a census or is sampled** |
| **What makes a route host 21 s or 38 s an item** | **narrowed to the prefill rate; the cause is not recorded** | it is a 3.1x swing in prompt-eval throughput (20.2 to 62.9 tok/s) with the prompt size, the reply size and `n_slots` all ruled out, and decode moving the *other* way. Nothing logged the CPU, so the host difference has no name. The `route` job now prints `/proc/cpuinfo` model name, `nproc` and llama-server's `system_info`; read those against the next fast run and the next slow one. The `work` job shows the same swing, 3.4x with the same inverted decode ([The one-slot production observation](#the-one-slot-production-observation)), and wants the same three lines. It does not have them. |
| **What a sharded `route` job would cost** | **arithmetic only** | four shards divide the stage but each pays the fixed cost and each needs a collision-free asset path. Blocked behind moving the published asset name off a directory-scanned ordinal; not citable until a real matrix run records it. |
| **Whether Qwen3.5 recurrent state preserves incumbent-style prefix reuse** | **unmeasured; Qwen3 incumbent reuse is proven above** | serve the candidate through a real ordered worker and read its LCP/recurrent-state log fields plus evaluated prompt tokens for item 1 and items 2..N; record band crossings separately |
| **`max_output_tokens` and `truncation_cap_tokens` as wall-clock levers** | **unswept** | the `runtime` job in `measure.yml` sweeps llama-server runtime flags only. These two set how much text is prefilled and how much is decoded per item, which is the tail of a run rather than its median. Sweep them the same way: one value at a time, 3 repeats, fixed shard, golden `output_digest` unchanged. |
| Exact complete-request context for the configured summarizer | **unmeasured; 877-879 covers only the system prompt** | render system prompt + source form + title + fences + exact sanitized model-visible text through the embedded chat template, count the generation suffix, add output budget, and record the maximum by band |
| Cache-restore time per job, cache-hit | ~90 s, asserted | the same artifact, on a second run |
| A production day payload | fixture figure above | the first real pipeline run |
| HHEM scoring seconds per item on CPU | unmeasured | lands with the eval harness |
| Whether 1-2 bit quantisation changes the fit | unevaluated | open question 4 in the plan-doc |
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
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the published-size arithmetic these numbers feed.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - the batch-size rule these numbers set.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - the prompt the token count above measures.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the procedure these measurements gate.
- [../how-to/set-up-local-inference.md](../how-to/set-up-local-inference.md) - reproducing the local runs.
