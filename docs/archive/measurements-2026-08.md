# Retired measurements, August 2026

**Last Updated**: 2026-09-10

Moved out of [../reference/measurements.md](../reference/measurements.md) on
2026-08-30, and added to on 2026-09-10. Every number here was true when it was
taken, on the hardware and date its own section names. None of it is read by
`config/`, by a test or by a live doc, and several sections measure a gate or a
cap that no longer exists.

**What lands here, and what is deleted instead.** This page is for a finished
experiment whose method or corpus a later reader would reproduce - a closed
window, a retired model, a source list that has since changed. It is **not** for
an older reading of a quantity the live page still carries: that is deleted,
because git holds the bytes and `git log -p config/idhazh.json` holds the value
that was in force, which is the better record because it cannot disagree with
the running system.

**Do not size anything against a figure on this page without re-measuring.**
That is true of the live page too, and more so here.

## Prompt cache reuse

**Measured 2026-08-23** on GitHub-hosted `ubuntu-latest`, 4 vCPU, run
`32648218952`, job `work (3)`. The job log did not name the CPU model or the
llama.cpp build. It used `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record) through `llama-server` with
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
band. Because `band_for` changes the rendered prompt, only the roughly
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
`32742672105`, job `work (0)`, `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record) through `llama-server`
with `--ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4`. The job
log did not name the CPU model or the llama.cpp build.

The section above concluded the log could not prove prefix reuse. That was a
reading of the workflow's summary step, not of the log. The step greps for
`kv cache rm [`, which this build never emits. The uploaded `runtime-log-0`
artifact carries the line that settles it:

```text
slot get_availabl: id 3 | task -1 | selected slot by LRU, t_last = -1
slot get_availabl: id 3 | task -1 | selected slot by LCP similarity, f_sim_best = 0.923 (> 0.100 thold), f_keep = 0.811
slot print_timing: id 3 | task 172 | prompt eval time = 7119.70 ms / 75 tokens
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


## The two source word counts, 2026-08-27

**Measured 2026-08-27** on `state/scores.csv` at commit `860e7cd`, n=2,566.
Method: Python `csv.DictReader` over the committed ledger. Deterministic
arithmetic, so hardware and spread are not applicable.

The same reading was taken twice earlier the same day, at n=2,232 and n=2,346
([../concepts/evaluation.md](../concepts/evaluation.md)). The scheduled pipeline
adds rows several times an hour, so each is correct for the file in front of it.
The numbers below are the ones the migration acted on.

| Reading | Rows | Share |
| --- | --- | --- |
| `source_seen_word_count` **greater** than `source_word_count` | 610 | 23.8% |
| seen less than full | 1,450 | 56.5% |
| the two equal | 506 | 19.7% |
| sitting exactly on the 1,923-word cap | 157 | 6.1% |

The first row is the finding. If one string is a cut of the other, the seen
count cannot be the larger one, so 610 rows read in a direction that is
arithmetically impossible. The cause was not truncation: `source_word_count` was
`len(_WORD.findall(article.text))` and `source_seen_word_count` was
`len(article.text.split)` - two counters over one post-cap string. The gap
between them was tokenisation noise.

**The fix is visible as a natural experiment in this same file.** 2,346 rows
were written by the old writer and 220 by the one `ad630f7` shipped. **All 610
impossible rows sit in the 2,346. None sit in the 220.**

**The real truncation rate is 6.1 percent, not 87.** A rate derived from the
pair reads as 87 percent of items truncated and is wrong by about 14x. The
honest count is the rows sitting exactly on `int(2500 / 1.3) = 1923`, the only
truncation cap this repository has ever committed. No row in the ledger exceeds
it and only 6 rows sit in the 1,900-to-1,922 range, so the cluster at the cap is
the cut and not the distribution.

The ledger was rewritten in the same commit as the contract change:

| Rows | What the migration did |
| --- | --- |
| 2,204 | given the article's own length - it sat below the cap, so it is the text the model saw and the two counts are equal by construction |
| 142 | emptied - it sat on the cap, and extract discarded that body |
| 220 | left alone, because their own `version` stamp says the fixed writer produced them |

Header identical, row count identical, and every cell outside the migrated
column byte-identical.

**A CSV ledger must not be auto-merged.** Rebasing this rewrite onto a main that
had appended 220 rows produced a file git called a clean merge and which held
**2,569 rows against main's 2,566**, with 2 impossible rows surviving. The
line-based merge interleaved three rows that no reader would have questioned.
The safe move is to take the incoming file whole and re-run the migration over
it, which is what the committed file is.


## Evaluation ledger re-band

**Measured 2026-08-23** on `state/scores.csv` at commit `6c332c7`, n=156.
Method: Python `csv.DictReader` over the committed ledger, with today's
`EvaluationConfig` and `backend/idhazh/evals/score.py::band`. This is
deterministic ledger arithmetic, so hardware and spread are not applicable.

The recorded `band` column predates the counterweight caps. It is the scorer's
time-of-write output, not the current distribution.

| Band | Recorded | Re-banded with today's `band` |
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

| Band | Recorded | Re-banded with today's `band` |
| --- | --- | --- |
| high | 285 (63.8%) | 258 (57.7%) |
| medium | 81 (18.1%) | 108 (24.2%) |
| low | 81 (18.1%) | 81 (18.1%) |

Still exactly 27 rows move, and with the same split: 11 lead coverage, 11 dropped
hedge, 5 both. Every row written since the caps landed is already banded with
them, so the gap between the two columns is a fixed historical residue rather
than a rate that grows. It is 6.0% of the ledger now and shrinks with every run.


## The one-slot production observation

**Observed 2026-08-24** on GitHub-hosted `ubuntu-latest`, 4 vCPU, across two
consecutive `digest` runs, `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record) through `llama-server` with
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
same `model_id` (`qwen3-8b-q4-k-m`, the retired incumbent - historical record).
Comparing the `output_digest` written into
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
[agent-notes.md](../reference/agent-notes.md).

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
llama-batched-bench -c 8192 -b 512 -ub 512 -t 4 \
 -npp 900 -ntg 300 -npl 1,2,4 \
 -m backend/models/Qwen3-8B-Q4_K_M.gguf # the retired incumbent; historical record
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
| PP | TG | B | N_KV | T_PP s | S_PP t/s | T_TG s | S_TG t/s | T s | S t/s |
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
`Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record), 5,027,783,488 bytes,
sha256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`, from
`Qwen/Qwen3-8B-GGUF` (retired incumbent, historical record), fetched fresh
(`gguf_cache_hit=false`). Settings:
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


## The site, page by page, after the payload narrowing (2026-08-27)

Everything in this section was measured on an **,
node 24.12.0, CPython 3.12.12, on 2026-08-27**, over the six committed days and
2,237 items, against `origin/main` before and after PR #171. Two full builds per
arm plus the restore is three builds; the page figures are the **heaviest of
five builds** per arm, because a mean fires on half of all builds.

### What a reader downloads

`gzip -9` over the prerendered HTML, which is what the page-weight gate uses.

| Route | Before | After | Saved | Share |
| --- | ---: | ---: | ---: | ---: |
| `/<date>/` | 581,557 | 349,259 | 232,298 | 39.9 percent |
| `/<date>/<topic>/` | 581,034 | 348,566 | 232,468 | 40.0 percent |
| `/` | 499,670 | 302,122 | 197,548 | 39.5 percent |

**A dated page costs a reader 40 percent less than it did.** On the 10 Mbit
reference line that is 0.19 seconds off a 0.47-second document.

**The words on the page did not change.** All 36 prerendered pages match by
sha256 over their visible text, 309,999 characters in both arms. The raw HTML
across those 36 pages went from 34,167,655 to 26,673,278 bytes - 21.9 percent -
so what left was markup and inlined data, not sentences.

### What the whole site costs

| Quantity | Before | After | Saved |
| --- | ---: | ---: | ---: |
| The built site | 146,696,452 | 128,064,853 | 18,631,599 (12.7 percent) |
| One published day | 22,200,123 +/- 1,785,970 | 16,641,956 +/- 1,294,368 | 5,558,167 (25.0 percent) |
| Days to the 1 GB cap | 41 | 56 | 15 |
| The date it lands | 2026-10-07 | 2026-10-22 | 15 days |

**The 12.7 percent off the site bought 0.8 of a day. The 25 percent off the
per-day rate bought the other 14.2.** Same commit, and the useful number is the
one on the rate.

The local total agreed with CI's own `du -sb build` on the same commit to
**0.0006 percent**, which is what makes a developer-machine site measurement
usable at all.

### What the staged tree costs

`frontend/static/digest/` is the day payloads staged for a search result to
render from ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).

| Quantity | Before | After |
| --- | ---: | ---: |
| The staged tree | 6,976,807 | 3,620,375 |
| Its `digest.json` half | 5,921,207 | 2,564,775 |
| The remaining floor | 1,055,600 | 1,055,600 |

**The floor is 87 rendered SVG images, and no projection touches them.** They are
copied whole because a chart is already a file; narrowing a payload cannot make
one smaller. Shrinking that 1.06 MB is an image question, not a payload one.

### What is left, and where it is

**The dated route trees are 39.5 percent of the site and they are the growth
driver.** 65,197,022 bytes before (44.4 percent) and 50,598,258 after
(39.5 percent). That is twelve prerendered documents per published day - six
HTML and six `__data.json` twins - and it is what actually decides the cap date.
No row has addressed it. It is recorded as a follow-up in
[../architecture/publishing/layout.md](../architecture/publishing/layout.md).


## Sizing the archive index

Four numbers the archive plan needs before it can choose a shape. All four were
estimates. These replace them, and two of them change what the plan assumed.

Toolchain: CPython 3.12.12,
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
| Hugging Face, `model_quantized.onnx` | `application/octet-stream` | 22,972,370 | 22,972,370 | **none** | **0%** |
| Hugging Face, `tokenizer.json` | `application/json` | 711,661 | 212,991 | `gzip` | 70.1% |

**The two Hugging Face rows were added on 2026-09-10 so the origins read against
each other**, and they are the reason the encoder stayed here. They were measured
on 2026-09-09 by the same method against
`https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/`, n=3 per file,
spread zero ([../reference/measurements.md](../reference/measurements.md), "What
the encoder costs on the wire from Hugging Face"). **The hub compresses the
tokenizer to within 3,059 bytes of what this origin does and does not compress
the weights at all**, so a first search from the hub costs 28.4 MB against 21.6
MB here - the 6.75 MB is exactly the 29.4 percent the row above it saves.

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
Both halves of that product are optimistic: the ceiling is reached on every run
(see the section above), and the cron is asked for five times a day and
delivered fewer, so this bounds a month rather than describing one.

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


## First-load JavaScript per route

**Retired 2026-08-30.** The gate these numbers fed - a per-route ratchet against
`frontend/bundle-baseline.json` - was deleted along with that file. It had no
requirement behind it, could not be read on a developer box inside its own
64-byte tolerance, and made every branch re-record a number its own change had
not moved. The derivation below is kept as the record of what was measured and
why 64 bytes was the noise floor; nothing reads it now. See
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md).


Date: 2026-08-25. Method: `npm run
build`, then `frontend/scripts/bundle-gate.mjs` gzips each module a route
declares `rel="modulepreload"` at level 9 and sums them - per file, never over a
concatenation. A concatenation is order-sensitive, so the number would move when
the bundler reorders the preloads, and it would under-report the wire cost. The
script is the gate, so the number quoted is the number that fails a build.

**The per-route bytes are deliberately not copied here.** They live in
`frontend/bundle-baseline.json` (deleted 2026-08-30), one record
per route class carrying the byte count, the date it was measured and a sentence
saying what those bytes buy. Two copies of one number are free to drift
(Rule #4), and the copy the gate reads is the one that decides a build. The
toolchain is pinned in that file, because `gzip -9` is deterministic for given
input bytes: the CPU is irrelevant and the Node major is not.

| Quantity | Value | Basis |
| --- | --- | --- |
| Build-to-build spread, route `/` | **12 B** | Four builds of byte-identical source, 2026-08-25, this repo: 49,193 / 49,198 / 49,198 / 49,205 B. SvelteKit stamps the app version into the entry chunk, so two builds of one tree are never quite the same bytes. A difference smaller than this is not a result. |
| Gate tolerance, every route, both directions | **64 B** | **Derived, not measured**: 5.3x the observed range. Four samples underestimate a true range, so the multiple is the margin. A build that ever fails inside 64 B re-derives this from more builds and more routes rather than nudging it. |
| Node 22 against Node 24, same build | **0 B on all seven routes** | Measured 2026-08-25 on one build, a developer machine, Windows. Node 22.23.2 (zlib `1.3.1-e00f703`) and Node 24.12.0 (zlib `1.3.1-470d3a2`) summed identically to the byte on every route class. The zlib build hashes differ and the output does not, so a baseline taken on a developer machine reproduces on the CI runner. This is two Node majors, not a proof about a third. |

The whole build is 133.8 MB against the 1 GB Pages ceiling (Rule #2).


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
stage starts, under `if: always` so a job that was cancelled or that failed
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

**Five of the six print. `system_info` does not.** Measured 2026-08-27 over the
nine `route` jobs that carry the step: `grep -m1 'system_info' router.log`
matched **zero times in nine runs**, because llama.cpp `b10598` writes no line
holding that string. The row is kept in the table because the question it
answers - which instruction sets the build uses - is still the open one, and
because an instrument that silently returns nothing is worth naming. See
[The CPU model does not sort the route job's per-item cost](#the-cpu-model-does-not-sort-the-per-item-cost-of-the-visuals-job)
for what that costs.

The step also echoes `LLAMA_CPP_BUILD`, so a disagreement between the pin and
what the binary says about itself is visible on one screen. The two digests are
what let a number on this page name the bytes that produced it (Rule #10); the
run manifest still records `runtime_build` as a fixed string and does not.

Three more instruments landed beside them.

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
bound is 150 minutes, so one shard writes at most 600 rows, about 36 KB; four
shards at most about 144 KB and eight at most about 288 KB - 0.03% and 0.06% of
the 500 MB artifact budget (Rule #2). A 105-minute shard writes about two thirds
of that. Raising the shard ceiling scales this term with the shard count and
leaves the `items-*` total flat, because the plan is divided between workers
rather than copied to each of them.

**And the server's own counters stopped expiring with the log.** The `/metrics`
scrape has printed `llamacpp:` lines into the job log since 2026-08-25, and the
raw body has ridden in `runtime-log-<shard>` for two days. From 2026-08-27 each
shard also files the counters as one row of `state/runtime-counters.csv`, which
is what turned the read rate from a reported number into a checked one - see
[The ledger and the server agree about the read rate](../reference/measurements.md#the-ledger-and-the-server-agree-about-the-read-rate)
for the arithmetic, the reconciliation and the storage cost.


## The first run at cap 5000, and the two triggers that revert it

**No figure in this section is measured yet, and that is the point.**
`extract.truncation_cap_tokens` moves from 2500 to 5000 in a later commit, and
the first scheduled `digest.yml` run after it is what takes the numbers. The
method and the two conditions that revert the change are written down first,
because a rollback rule written after the run it judges is not a rule - it is a
reading of that run.

### How the figures here are taken

**Hardware.** GitHub-hosted `ubuntu-latest`, 4 vCPU, 16 GB, no GPU.
`Qwen3.5-9B-Q4_K_M.gguf` summarizing through `llama-server`,
`Qwen3-4B-Q4_K_M.gguf` routing, llama.cpp `b10598`. From 2026-08-29 each `work`
job records the processor it drew in its own `state/runtime-counters.csv` row,
so the covariate this comparison used to be unable to hold is now readable per
shard. The `route` job still has no such row
([Still unmeasured](../reference/measurements.md#still-unmeasured)).

**Date.** **2026-08-29.** The first scheduled run at cap 5000 is run
`33244705103`, ledger run id `2026-08-29-2`, head commit `fa53634`, started
2026-08-29T09:06:26Z. The cap landed on `main` at 04:28 UTC that morning, so
run `2026-08-29-1` earlier the same day is the last run at cap 2500 and is the
control every comparison below uses.

**n.** One run, four `work` jobs, 160 items planned, 40 items a worker.
`run.max_parallel` is 4 and `run.safety_ceiling_per_run` is 160, so a scheduled
run cannot hand a worker more. That is the same load
[The first scheduled day on the configured model](../reference/measurements.md#the-first-scheduled-day-on-the-configured-model-2026-08-27)
carried, which is what makes its 85.6 minutes a like-for-like baseline rather
than a number off a differently shaped day.

**The query, for every wall-clock figure.** Each `work` job now files its own
clock, so the first read is a committed file. `state/runtime-counters.csv` holds
one row per shard per run, and `job_seconds` is that shard job's clock:

```python
import csv

rows = [r for r in csv.DictReader(open("state/runtime-counters.csv", encoding="utf-8"))
 if r["run_id"] == "<the run>"]
clocked = [r for r in rows if r["job_seconds"]]

print("shards:", len(rows), "clocked:", len(clocked))
for row in sorted(clocked, key=lambda r: -int(r["job_seconds"])):
 print(row["shard"], "%.1f min" % (int(row["job_seconds"]) / 60), row["cpu_model"])
```

**`job_seconds` is a floor on the job's wall-clock, and the gap is 13 to 17
seconds.** It starts at the job's first step and stops at the counters scrape,
so the ledger push, the two log summaries and the artifact uploads that follow
are outside it. Measured 2026-08-29 over all four shards of run `33244705103`,
against the same jobs from the API: **13, 15, 15 and 17 seconds, which is 0.3 to
0.6 percent of the shard's clock**. So the committed cell can be read as the
job's clock without an API call - at 70 minutes the gap is a quarter of a
minute. A `job_seconds` over 110 minutes has fired
[Trigger A](#trigger-a---the-shard-clock) on its own, and the API remains the
authority for anything closer than half a minute to the line.

**The API is still the authority, and it is now the second read.** Job records
live outside this repository and drop with the run, which is the whole reason
the clock became a committed cell. Find the runs, then read one run's jobs:

```
gh run list --repo miztiik/yen-idhazh --workflow digest.yml --branch main \
 --event schedule --limit 5 --json databaseId,createdAt,conclusion

gh api "repos/miztiik/yen-idhazh/actions/runs/<id>/jobs?per_page=100" \
 --jq '.jobs[]
 | select(.name | startswith("work"))
 | [.name,.conclusion,
 ((.completed_at | fromdateiso8601)
 - (.started_at | fromdateiso8601)) / 60]
 | @tsv'
```

Wall-clock is `completed_at - started_at` for the job, so no queue time is
inside any figure. A four-worker run holds seven jobs, so one page returns them
all. Every figure on this page taken before 2026-08-29 came from this query and
from nothing else.

**The query, for every ledger figure.** `state/item-health/<YYYY-MM>.csv` is one
row per planned item per run. Save this and run it with `python`, naming the
month file the run landed in:

```python
import csv

rows = list(csv.DictReader(open("state/item-health/2026-09.csv", encoding="utf-8")))
past_old_cap = [r for r in rows if r["source_words"] and int(r["source_words"]) > 1923]
lost = [r for r in rows if r["code"] == "context_exceeded"]

print("read past the old cap:", len(past_old_cap))
print("context_exceeded:", len(lost))
for row in lost:
 print(row["date"], row["run_id"], row["item_id"], row["source_id"], row["source_words"])
```

Both triggers read those two numbers, and the first one is what stops a run that
exercised nothing from reading as a pass.

### Trigger A - the shard clock

**Revert if the slowest `work` job exceeds 110 minutes on two of three
consecutive scheduled runs.**

110 minutes is 24.4 minutes above the only measurement of the configured model -
85.6 minutes, run `33073809079`, 2026-08-27 - and 40 minutes below
`run.shard_timeout_minutes`, which is 150 in `config/idhazh.json` and reaches
the job through `needs.plan.outputs.shard_timeout_minutes` in `digest.yml`.
Between those two it sits above every projected cost of the cap change except
the pathological one, and below the point where a worker is killed and its
whole share of the day is lost.

| The slowest worker at | Minutes | Against the 110-minute trigger |
| --- | ---: | --- |
| today's cap, measured 2026-08-27 | 85.6 | 24.4 below |
| the typical extra cost, +3.6 | 89.2 | 20.8 below |
| a bad draw, +10.9 | 96.5 | 13.5 below |
| the pathological draw, +43 to +46 | 128.6 to 131.6 | **18.6 to 21.6 above**, and still 18.4 to 21.4 below the 150-minute bound |

**The three extra costs are projections, not measurements (Rule #10).** An
at-cap item picks up about 1,312 extra input tokens at cap 5000, which is 1.8
minutes at the 12.05 tok/s uncached read rate. Two such items on the heaviest
shard is +3.6 minutes, six is +10.9, and the pathological case is all 12 landing
on one shard with every one still clamped: 1,923 extra words each at the 1.35 to
1.44 tokens a word this project has measured, so +43 to +46. Wall-clock moves by
the slowest shard alone, because the run waits for the last worker.

**Two of three, because one run is a draw.** The four workers of run
`33073809079` spanned 62.6 to 85.6 minutes - 1.37x, on one day, one model and
one item count. A single run over 110 is inside that lottery. Two of three is
not.

**A run counts as one of the three only if it exercised the change.** All four
conditions, or the run is not evidence and the count does not advance:

| Condition | Read from | Why it is there |
| --- | --- | --- |
| `items_planned` is 160 | `runs[].items_planned` in `frontend/public/digest/<Y>/<M>/<D>/run.json` | A smaller day hands a worker fewer than 40 items, so its clock is short for a reason that is not the cap. |
| exactly four `work` jobs | `shards` in `state/runtime-counters.csv`, one row per shard | An eight-shard dispatch carries 20 items a worker and halves the clock on its own ([Eight work shards, paired](#eight-work-shards-paired-2026-08-27)). |
| every `work` job concluded `success` | the jobs query above | A job that was cancelled, or that hit its bound, has a clock that means nothing. The counters row is written under `always`, so it exists either way and cannot answer this. |
| `read past the old cap` is 1 or more | the ledger query above | A run that read nothing longer than 1,923 words never exercised the new cap, so its clock is a cap-2500 clock. |

**That last table is the whole reason this trigger is checkable.** Without it a
cancelled run, a quiet news day and an eight-shard dispatch all turn in a short
slowest worker, and a short worker reads as a pass.

### Trigger B - a lost item

**Revert on the first row in `state/item-health/<YYYY-MM>.csv` with
`code = context_exceeded`.** One occurrence is the finding, and one run is
enough.

`context_exceeded` is the summarize stage recording that the served context
window refused a prompt - `n_ctx` is 8192 and the prompt plus the reply budget
did not fit. It is a member of `FailureCode` in
`backend/idhazh/contracts/item_health.py` and a value of the ledger's `code`
column. **It has never appeared.** Counted 2026-08-28 over
`state/item-health/2026-08.csv`: 2,527 items published and 985 failed across 19
runs, and not one `context_exceeded` row among them.

**It is written as a positive event on purpose.** "Zero `context_exceeded` rows
on the first run" is the obvious test and it is the wrong one, because zero is
the expected count whether the cap is safe or not. About 8 items a run sit at
the cap - counted 2026-08-28, 153 rows at the cap over 19 runs, 8.1 a run, range
1 to 12 - and at the new cap one of those overflows only at 1.59 tokens a word
or worse, which is 10 to 21 percent above the worst prose measured here. An
absence test on an event that will not fire passes on a run that did nothing,
and this project has published that mistake once already, when a canary that
returned no summary at all was written up as a sanitizer failure
([The fifth canary was never exercised](../reference/measurements.md#the-fifth-canary-was-never-exercised)).

**What makes it fail on a run that exercised nothing.** The ledger's
`source_words` is the post-cap count, and it cannot exceed
`int(truncation_cap_tokens / 1.3)` - 1,923 words at cap 2500, 3,846 at cap 5000.
Measured 2026-08-28 over the 2,541 rows in `state/item-health/2026-08.csv` that
carry a length: the maximum is exactly 1,923, 153 rows sit on it, and none is
above it. So the `read past the old cap` count is positive proof the new cap was
read. **If it is zero, the `context_exceeded` count means nothing and this
trigger has not been checked.**

### The rollback action

`extract.truncation_cap_tokens` back to `2500` in `config/idhazh.json`. One
line, and nothing else moves - not `n_ctx`, not `request_timeout_minutes`, not
`run.shard_timeout_minutes`.

The cap is a field of `PipelineInputs`
(`backend/idhazh/contracts/fingerprint.py`), so the change and the rollback each
re-stamp the pipeline fingerprint. **That does not re-summarize anything.**
`rank.plan_vertical` drops every `url_key` in `already_published`, a gate that
reads `state/published.csv` and never consults a fingerprint, and
`fingerprint.classify` is not wired into `cli.py`. **Measured 2026-08-29 over `state/scores.csv`:** 6 distinct fingerprints across
2,791 rows, and 6 of 2,781 distinct addresses ever scored under more than one -
0.22 percent. The rollback costs the items of the run it lands on, and nothing
else
([What the first run at cap 5000 must record](#what-the-first-run-at-cap-5000-must-record)).

### The instrument Trigger A reads

**Every `work` job files its own clock and its own host, in the row it already
wrote for the tokens it read.** `state/runtime-counters.csv` is one row per shard
per run, and it carries five cells about the job rather than about the model
server - two from 2026-08-29 and three more from 2026-08-30:

| Cell | Holds | Empty means |
| --- | --- | --- |
| `job_seconds` | seconds from the shard job's first step to the counters scrape | no stamp reached the step - a re-run of one shard, or a stage run by hand. Never zero seconds. |
| `cpu_model` | the host's `/proc/cpuinfo` `model name` line | the host published no such line |
| `cpu_busy_pct` | busy processor time as a share of the processor time available, between the same two instants, from the aggregate `cpu` line of `/proc/stat` | one end of the window never ran |
| `peak_rss_bytes` | the highest `VmHWM` llama-server reached over every sample `rss-samples.tsv` holds | the sampler wrote no file, or its column moved |
| `model_load_ms` | milliseconds between the two lines llama-server brackets its own model load with | llama.cpp renamed a line, or logged without timestamps |

**What the last three are for, one question each.** `cpu_busy_pct` separates a
shard that was short of processor from one that was waiting: the cgroup ran 3.99
of 4 processors the one time anyone measured it by hand (run `32672629352`,
2026-08-23), so the expected reading is at or near 100 and a **drop** is the
signal. `peak_rss_bytes` answers what a qualification cannot - whether a
candidate model can be *served* on the runner's 16 GB at `n_ctx` 8192 with
headroom - and until it existed a run either survived or the runner killed it.
`model_load_ms` is the fixed cost `run.shard_size` exists to amortise.

**Read against `/proc/stat`, not against a cgroup file.** Two cgroup files this
repository has read are absent on a GitHub-hosted runner:
`/sys/fs/cgroup/memory.peak` printed `unavailable` on every shard of run
`32869125768`, and `/sys/fs/cgroup/cpu.max` printed nothing at all in run
`32672629352`. `/sys/fs/cgroup/cpu.stat` is readable and reports the same thing
`/proc/stat` does - `usage_usec 34944000` against 3,429 busy ticks, 34.94 s
against 34.29 s on one probe - because both count the whole machine since boot.
So either needs two reads and a difference, and `/proc/stat` carries idle in the
same line, which makes the denominator free.

**The `/proc/stat` pair proves its own window.** Measured 2026-08-30 on a
GitHub-hosted `ubuntu-latest`: two reads 20 s apart differ by **7,991 ticks**
against the 8,000 that 20 seconds of 4 processors at 100 Hz has to be - 0.11
percent. That is the check no hand-written fixture can pass, and it is why
`backend/tests/test_contracts.py` parses a real capture.

**First readings, run `2026-08-29-3`, four shards** (from the `runtime-log-*`
artifacts of run `33274853468`, before the cells existed to hold them):
model load **3,789.5 / 3,820.3 / 4,158.0 / 3,797.6 ms** - so a 9B opens in about
four seconds, which is **1.1 to 1.5 percent** of the 284-447 s fixed cost a
worker pays. The fixed cost is somewhere else. Peak `VmHWM` **12.57, 12.65,
12.94 and 13.16 GiB** against the runner's 16 GB, so the worst shard left 2.84
GiB. `cpu_busy_pct` has no reading yet: every committed row predates the cell.

**How to read it.** The query is in
[How the figures here are taken](#how-the-figures-here-are-taken) above. Sort a
run's rows by `job_seconds` and the slowest worker is the first one; that is the
number [Trigger A](#trigger-a---the-shard-clock) compares against 110 minutes.
Read `cpu_model` in the same row, because this page has measured a 3.1x swing in
prompt-reading throughput between hosts, so two clocks on two different parts
are not a comparison (Rule #10).

**It is a floor, and the gap is 13 to 17 seconds.** The scrape happens before
the ledger push, the two log summaries and the artifact uploads, so `job_seconds`
under-reports what the jobs API calls the job. Measured over all four shards of
run `33244705103` on 2026-08-29: 13, 15, 15 and 17 seconds, **0.3 to 0.6 percent
of the shard's clock**. Nothing a run has to decide turns on a quarter of a
minute, so the committed cell stands on its own.

**Where the clock comes from.** The `work` job's first step - ahead of the
checkout - writes an epoch second and the CPU model to the job environment, and
the counters step passes both to `python -m idhazh counters`. First, so the
number covers the cache restore and the weight load: those are the largest fixed
cost in the job, and a clock that starts after them is not the job's clock.

**Why this row and not the run manifest.** The manifest is one row per run and a
run draws up to eight hosts, so a per-job fact would have to become a
variable-length list keyed by shard - which is what this ledger already is. The
manifest is also written by `assemble`, hours later and in another job, and it is
a published payload a reader's browser fetches rather than measurement evidence
under `state/` ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)).
That reasoning does not reach the `route` job, which runs no shards and files no
counters row, so which processor a `route` job drew is still unrecorded
([Still unmeasured](../reference/measurements.md#still-unmeasured)).


## What the first run at cap 5000 must record

**Measured over run `33244705103`, 2026-08-29 - the first scheduled run at cap
5000.** Ledger run id `2026-08-29-2`, head commit `fa53634`, four `work` jobs,
160 items planned, all four jobs `success`. Every value cell below is a
measurement taken from that run.

**Both triggers passed and the cap stays at 5000.** `context_exceeded` is 0 of
160 planned rows and the slowest worker took 70.4 minutes against the
110-minute line - 39.6 minutes of room. The widest complete request the server
saw was 4,925 tokens against the 7,800 that would bring the cap down to 4000,
so the escalation in step 7 did not fire either.

**What the run did not get to test.** Its longest article was 2,772 words, so
**no item reached the new 3,846-word cap** and none reached the fifth summary
rung's 3,000-word floor. Six items were read past the old 1,923-word ceiling and
all six were read whole. Rows 6 and 7 ask about at-cap items and there were
none, so they report what the run does say instead, and each says which
question it could not answer. **Both arrived later the same day.** Runs `2026-08-29-3`
and `2026-08-29-4` each read one article to the full 3,846-word ceiling, so an
at-cap item now exists - one article, three rows ([Three figures the ledgers
already held](#three-figures-the-ledgers-already-held-2026-08-30)).

**The proof it ran at the new cap is committed, not inferred.** Every eval row
of `2026-08-29-2` carries pipeline fingerprint `5e608717`; every row of
`2026-08-29-1` earlier the same day carries `6a23e277`. The cap is a field of
`PipelineInputs`, so the stamp moved because the cap moved.

The section above,
[The first run at cap 5000](#the-first-run-at-cap-5000-and-the-two-triggers-that-revert-it),
owns the two conditions that revert the change. This one owns what the run has to
record either way. The two share four numbers - 85.6 minutes, the 150-minute
bound, 1,923 words at the old cap and 3,846 at the new one, and the +3.6 and
+10.9 minute projections - and they agree on all four.

**Why a blank sheet is committed before the run.** A measurement sheet written
after the run it measures is a reading of that run, not a method. The same
argument put Trigger A and Trigger B on the page before the cap moved.

### What fills each row

Three instruments, and each row below names which one it needs.

**Job wall-clock** comes from `state/runtime-counters.csv`, whose `job_seconds`
cell is the shard job's own clock up to the counters scrape, and from the jobs
API for the part after it. Both queries are in
[the section above](#the-first-run-at-cap-5000-and-the-two-triggers-that-revert-it),
and what the committed cell leaves out is in
[The instrument Trigger A reads](#the-instrument-trigger-a-reads).

**Per-item figures** come from `state/item-health/<YYYY-MM>.csv`, one row per
planned item per run. `source_words` is the post-cap count and cannot exceed
`int(truncation_cap_tokens / 1.3)`, so **`source_words` above 1923 is the proof
the new cap was read**:

```python
import csv, statistics

rows = [r for r in csv.DictReader(open("state/item-health/2026-09.csv", encoding="utf-8"))
 if r["run_id"] == "<the run>"]
sized = [r for r in rows if r["source_words"]]
at_cap = [r for r in sized if int(r["source_words"]) == 3846]

print("read past the old cap:", len([r for r in sized if int(r["source_words"]) > 1923]))
print("at the new cap:", len(at_cap))
print("context_exceeded:", len([r for r in rows if r["code"] == "context_exceeded"]))

read = sum(int(r["input_tokens"]) - int(r["cached_tokens"] or 0) for r in rows if r["prefill_ms"])
secs = sum(int(r["prefill_ms"]) for r in rows if r["prefill_ms"]) / 1000
print("read tok/s: %.2f" % (read / secs))
print("output tokens at cap, median:",
 statistics.median([int(r["output_tokens"]) for r in at_cap if r["output_tokens"]]))
```

**Server-side totals** come from `state/runtime-counters.csv`, one row per shard.
`n_tokens_max` is the widest complete request the server saw, and it is the only
instrument that answers the context-fit question, because it counts prompt plus
reply as the server assembled them rather than as we estimated them. The same
row carries `job_seconds` and `cpu_model`, which is why rows 1 and 2 below now
read a committed file instead of an API.

### The rows

| # | What to record | Against what | Reading |
| --- | --- | --- | --- |
| 1 | Slowest `work` job, minutes, from `job_seconds` and from the jobs API. **Record both**: the gap between them is what the committed cell leaves out, and no run has measured it yet | 85.6 min measured 2026-08-27, and `run.shard_timeout_minutes` of 150 | **70.1 min** from `job_seconds` (4,208 s, shard 0) and **70.4 min** from the API (4,223 s). Over all four shards the gap is **13 to 17 s, which is 0.3 to 0.6 percent of the shard's clock**. 15.2 min faster than the 85.6 on record, and 79.6 min under the 150-minute bound |
| 2 | Fixed cost per worker: the part of a worker's clock that is not model time (cache restore, weight load, warmup). `job_seconds` minus the server's own `prompt_seconds_total` plus `tokens_predicted_seconds_total`, in the same row | no prior on record; this run establishes it | **284, 346, 366 and 447 s - 4.7 to 7.5 minutes, 8.7 to 12.4 percent of the shard's clock.** The slowest shard carries the largest fixed cost as well as the largest model time, so the two do not trade off |
| 3 | Items at the new cap, per run and per shard | 7.8 a run at the old cap (155 rows at exactly 1,923 words over 20 runs, `state/item-health/2026-08.csv`, counted 2026-08-29) | **0, on every shard.** The run's longest article was 2,772 words against a 3,846-word cap, so nothing reached it. **6 items were read past the old 1,923-word ceiling** and all six were read whole. Against 7.8 a run before: the cap stopped binding rather than binding higher up |
| 4 | Extra input tokens actually read, against the run before it | the projection of 10,300 to 11,000 a run | **About 3,000 tokens, a quarter of the projection.** The 6 items past the old ceiling carry 2,172 words the old cap would have dropped - 362 an item - which is 2,824 tokens at the 1.3 placement estimate and 3,013 at the 1.387 rate row 10 measures. The projection assumed 7.8 items sitting on the cap and this run had none. Run totals were 119,516 uncached tokens against 118,812 the run before, and that difference is a different article mix, not the cap |
| 5 | Read rate, uncached, tok/s | 12.05 tok/s, the rate the projection used | **16.19 tok/s** over the 104 items with a prefill clock, against 11.88 on run `2026-08-29-1` the same day. **This is not the cap making reading faster.** The two runs drew different hosts, and run 1 recorded no CPU model at all, so the covariate cannot be held (Rule #10) |
| 6 | Decode rate on at-cap items, tok/s | 4.89 tok/s over 25 at-cap items on the configured model, counted 2026-08-29. **n=25 is one number, not a distribution** | **No at-cap item exists, so this row has nothing of its own to measure.** Over the 6 items read past the old ceiling it is **6.65 tok/s**, and over the whole run **6.35**, against 4.88 on run 1. The instrument is there and the population is not: it needs a run whose longest article is 3,846 words or more |
| 7 | Output tokens on at-cap items, median. **This is now expected to rise** | 331 tokens over the same 25 items. A cap change alone cannot move the ask, because the band comes from `band_source_words` and that is pre-cap. The fifth summary rung, landed 2026-08-29, does move it: its floor is 3,000 words and every at-cap item is 3,846 words or more, so every one of them left the 110-200 ask for 150-230. Expect about **+45 tokens**, and read a move of that size as the new rung rather than as a fault | **The fifth rung never fired: no item reached 3,000 words**, so the +45 cannot be looked for. What the run does answer is the half that catches a mistake - median output on items **below** 3,000 words is **248 tokens over 104 items**, against **251.5 over 108** on run 1. It did not rise, so the 2026-08-26 band defect has not come back |
| 8 | Slowest single item, seconds | 449 s on record, against the 1,326 s bound (`models.inference.request_timeout_minutes` of 22.1) | **337.3 s**, the slowest `summarize_ms` of the run - 25.4 percent of the bound. Run `2026-08-29-1` the same day held a 503.3 s item, so this run's tail is shorter than the cap-2500 run before it |
| 9 | Widest complete request, prompt plus output tokens, from `n_tokens_max` | 3,775 + 900 measured, against `n_ctx` of 8,192. **Above 7,800 the cap comes down to 4000 and `n_ctx` does not move** | **4,925 tokens**, shard 2. The four shards read 3,122, 4,178, 4,570 and 4,925. **2,875 below the 7,800 line and 3,267 below the window** - step 7 did not fire and the cap stays at 5000 |
| 10 | Implied tokens per word on the widest item | 1.35 to 1.44 measured on this project's prose; 1.59 or worse is what it takes to overflow | **1.387 tokens an article word over the run, and 1.352 on the widest item.** Regressing `input_tokens` on `source_words` over the 104 sized items gives a slope of 1.387 and a fixed prompt of 951 tokens, with a residual spread of 119 tokens. On the widest item - 2,772 words, 4,698 prompt tokens - the article's own share is 3,747 tokens. Both sit inside the measured band and well under the 1.59 that would overflow. **Superseded 2026-08-30 by a wider population**: over all 413 rows written at cap 5000 the slope is **1.2999** and the fixed prompt 998 tokens ([Three figures the ledgers already held](#three-figures-the-ledgers-already-held-2026-08-30)). The 1.387 here is this one run and it reproduces exactly; the two runs after it read an article to the full 3,846-word ceiling and the widest point is what sets a slope. 1.2999 sits *below* the 1.35 to 1.44 band this row checks against, so the band is superseded rather than confirmed, and 1.2999 is 18.2 percent under the 1.59 that overflows |
| 11 | `context_exceeded` rows | 0 over 3,672 rows of `state/item-health/2026-08.csv`, counted 2026-08-29. Read it beside row 3 - a zero here means nothing if nothing was read past 1,923 words | **0 of 160 planned rows.** It is a measurement rather than an absence, because row 3 says 6 items were read past the old ceiling on this run |
| 12 | Peak resident set per worker | 14.39 GiB high point on record, against 16 GB on the runner | **12.56, 12.64, 12.70 and 13.55 GiB** for `llama-server`, plus 1.43 to 1.98 GiB for the Python worker, over 167 to 260 samples a shard. Under the 14.39 on record and 2.45 GiB under the runner's 16 GB at the worst shard. `cgroup_memory_peak_bytes` printed `unavailable` on all four, so that instrument is still broken ([Still unmeasured](../reference/measurements.md#still-unmeasured)) |
| 13 | `route`: `items_prefiltered`, `items_asked`, `unrouted` | 18 unrouted is the median of the runs on record. A longer body yields more quantities, so **prefiltered should fall and unrouted should rise**. It costs charts, not clock - the stage self-stops at `run.route_budget_minutes` of 40 | **58 prefiltered, 46 asked, 0 unrouted** over the 104 items the stage decided, with 10 charts drafted and 8 kept. It spent 37.0 of its 40 minutes, so it just fit. **The prediction did not hold, and this run cannot test it**: prefiltered rose from 44.1 percent on run 1 (41 of 93) to 55.8 percent, and unrouted fell from a median of 18 to zero. Only 6 items got any extra text at all, so nothing here is attributable to the cap |
| 14 | `hhem` against `hhem_full` on items that would have been cut at the old cap | `hhem_delta` runs -0.1235 to +0.0381 over the 24 cut items on record. **This row is an observation, not a gate.** Nothing measured says a longer read produces a better summary | **`hhem_delta` is 0.0000 on all 6.** That is the ledger being unable to answer rather than an answer: `cli.stage_work` passes `article.text` as both `seen_text` and `full_text`, so the two scores are one score and the column is structurally zero in production. The instrument that can answer is the offline re-score over committed evidence pairs ([Which way the grader's length bias runs](#which-way-the-graders-length-bias-runs)) |

**The four shards named three different processors, and the slowest took 1.51
times the fastest.** This is the first run where every worker recorded its host,
so it is the first time the covariate can be read rather than assumed. One run,
one plan of 160 items split four ways:

| Shard | `job_seconds` | Model seconds | Processor |
| ---: | ---: | ---: | --- |
| 3 | 2,785 (46.4 min) | 2,439 | AMD EPYC 9V45 |
| 2 | 3,086 (51.4 min) | 2,720 | AMD EPYC 9V45 |
| 1 | 3,283 (54.7 min) | 2,999 | AMD EPYC 9V74 |
| 0 | 4,208 (70.1 min) | 3,761 | AMD EPYC 7763 |

**The spread is in the model seconds and not in the fixed cost** - model time
runs 1.54x across the four while the clock runs 1.51x. And the processor does
not explain all of it: the two shards on the identical `9V45` string are still
1.11x apart. That is the shape
[the `route` job's per-item cost](#the-cpu-model-does-not-sort-the-per-item-cost-of-the-visuals-job)
already has, now measured on the stage that decides the run's wall-clock. What
it means for [Trigger A](#trigger-a---the-shard-clock): the run waits for the
last worker, so drawing a `7763` for one shard costs 24 minutes more than
drawing two `9V45`s, and that is the host lottery rather than anything the cap
did.

**Row 7 is the one that catches a mistake in this change, and the fifth summary
rung changed what a mistake looks like.** Rows 1 to 5 all move by design, so a
surprise there is a matter of degree. The output length used to be the row that
had to stay still, because a cap change alone cannot move the ask - the band
comes from `band_source_words` and that count is pre-cap. Since 2026-08-29 the
fifth rung moves it on purpose and by a stated amount: about +45 tokens, on
at-cap items and on those alone.

So the question this row asks is no longer "did it move" but **"did it move where
the rung reaches"**. A rise of about 45 tokens on items at 3,000 words and up is
the rung working. A rise on items **below** 3,000 words is the defect
[the band's design rationale](../architecture/summarize/prompt.md) records being
fixed on 2026-08-26 - the band selection reading the post-cap count somewhere -
and that is what this row still exists to catch.

**The first run answered only half of it, and that is the useful half.** No
article reached 3,000 words, so the rung never fired and the +45 could not be
looked for. The half that catches a mistake did run: the median output on items
below 3,000 words was 248 tokens against 251.5 on the run before, so the band
selection is still reading the pre-cap count. **The rung's own effect stays
unmeasured until a run draws an article of 3,000 words or more.** Six of the 24
cut items on record are that long, so it is a matter of waiting rather than of
changing anything.

**Row 14 is the row this change does not get to claim.** The cap buys more
article read, and that is all it is measured to buy. Whether the summary is
better is a different measurement with a different instrument, and the instrument
that would say has never returned a real number
([Still unmeasured](../reference/measurements.md#still-unmeasured)).

**The run also showed the ledger cannot answer row 14 at all.** `hhem_delta` is
0.0000 on all six items the old cap would have cut, because production hands the
same string to both scorers - so the column is structurally zero and reading it
as "no difference" would be reading an instrument that is not connected.

### What was counted on 2026-08-29, before the cap moved

These are measured, unlike the table above. They are the baseline the first run
gets compared against, taken over the committed ledgers at commit `4f53690`.

**Every count here is a snapshot.** The scheduled pipeline appends to these files
several times a day, so a re-count tomorrow returns different totals. Two of
these rows moved while this change was being written.

| Quantity | Value | Source |
| --- | ---: | --- |
| Items whose body was cut, with both counts recorded | 24 | `state/scores.csv`, `source_word_count > source_seen_word_count` |
| Extra words a cap of 5000 keeps, summed over them | 24,951 | `min(pre_cap, 3846) - 1923` |
| Mean extra words per cut item | 1,039.6 | the same 24 items, which is 1,352 tokens at 1.3 |
| Of those, read whole at cap 5000 | 19 of 24 | pre-cap length at or under 3,846 words |
| Still cut at cap 5000, pre-cap words | 4,212; 4,444; 5,314; 8,207; 8,442 | reading all five whole needs a cap near 11,000 tokens, which does not fit `n_ctx` |
| Items at the old cap, per run | 7.8 | 155 rows at exactly 1,923 words over 20 runs, `state/item-health/2026-08.csv` |
| Extra input tokens a run, implied | about 10,500 | 7.8 items at 1,352 tokens, inside the 10,300 to 11,000 projection |
| Scored items a run | 121.3 | 2,791 rows over 23 runs, `state/scores.csv` |
| `context_exceeded` rows, all August | 0 | `state/item-health/2026-08.csv`, 3,672 rows |

**1.3 tokens a word is a placement estimate and not a measurement.**
`extract.TOKENS_PER_WORD` exists to put a cut point in the same place every time.
The decoder enforces the real budget, and the measured range on this project's
prose is 1.35 to 1.44. Every "tokens" figure derived from a word count on this
page carries that estimate inside it.

### What the cap change does not do

**It does not re-summarize the archive.** The cap is a field of `PipelineInputs`
(`backend/idhazh/contracts/fingerprint.py`), so moving it re-stamps the pipeline
fingerprint. That does not reach the published corpus, because
`rank.plan_vertical` drops every `url_key` in `already_published` and that gate
reads `state/published.csv` alone - it never consults a fingerprint.
`fingerprint.classify` and `SKIPPABLE` are not wired into `cli.py`.

**Measured 2026-08-29 at commit `4f53690`:** `state/scores.csv` holds
2,791 rows under **6 distinct pipeline fingerprints**, and **6 of its 2,781
distinct `url_key` values have ever been scored under more than one** - 0.22
percent. Six fingerprint changes have already happened, including the
2026-08-27 summarizer swap, which is the largest one available. Together they
added 6 re-scored rows, not 2,781.

So the first run at the new cap appends what any run appends: 137 rows at the
median, 149 at the most, over the 23 runs on record.

**Measured by `npm run bundle-gate` on this checkout, 2026-08-29, three times.**
The branch merged `origin/main` twice while the change was being written, so the
builds are a paired measurement of what the ledger costs the page:

| Build | What landed between | `/console/` prerendered HTML | Spare under the 301,580 ceiling |
| --- | --- | ---: | ---: |
| `e05ef99` | - | 170,732 B | 130,848 B |
| `4f53690` | 55 scored rows, nothing else `/console/` renders | 171,471 B | 130,109 B |
| `d782a9d` | the 2026-08-29 day published | 176,576 B | 125,004 B |

**739 bytes for 55 rows is 13.4 gzipped bytes a scored item**, not the 60 the
ceiling's headroom was sized with. A median run of 137 rows costs about **1,840
bytes: 1.4 percent of the spare, and about 68 runs of margin** at the 125,004
bytes left. **The cap change contributes none of those bytes**, because it adds
no rows of its own.

**68 runs was 24 to 27 days, and the days are the number that decided it.**
Counted 2026-08-29 over `state/scores.csv`: 2,791 rows across 23 runs on 8
dates, so the pipeline runs 2.88 times a day and scores 349 items a day at the
mean. At 13.4 bytes a row that is 4,675 bytes a day and 27 days of margin; at
the median run of 137 rows it is 5,287 bytes a day and 24. The measured cost
being 4.5x below the sizing did not buy an open-ended margin - **it bought about
a month**, because the page inlined one point per scored row and nothing removed
one.

**That countdown ended on 2026-08-29.** The compression scatter now reads the
published telemetry shards instead of the whole score ledger, so `/console/`
carries one window of item telemetry rather than every row ever scored. The same
paired-build method read the prerendered page at **175,892 B before and 148,800
B after, -27,092 B**. The page now grows with `console.default_window_days` and
the day's item count, and stops growing once the window fills.

**Two rates, and they answer different questions.** 13.4 bytes is what the NEXT
55 rows cost - the marginal figure, and the right one for a countdown. Removing
the whole 2,647-point array measured **10.2 bytes a point** - the average over
an array that compresses against itself. Neither is wrong and neither substitutes
for the other. Rows compress against their neighbours, so 55 similar rows
appended to 2,736 are close to the cheapest 55 that file will ever take, and the
5,105 bytes the published day cost is one day that was still publishing when it
was measured.

That margin is the reason this was checked before the cap moved rather than
after. Until 2026-08-29 `digest.yml` ran `bundle-gate` in its `assemble` job
before it committed the day, so a page-weight failure stopped the publish. It
runs after the commit now: the build still gates the publish, because a payload
the site cannot build must not ship, but the weight ratchet no longer costs a
reader the day
([layout.md](../architecture/publishing/layout.md) records why).

**It does not move `scorer_version`.** That string is built by
`evals.metrics.scorer_version` from the scorer id and revision, the weights
digest, `METRICS_VERSION`, `evaluation.chunk_words`,
`evaluation.chunk_overlap_words`, the chunk anchor, the two band floors and
`evaluation.lead_coverage_min`. The truncation cap is not among them.

### The order to check it in

Eight steps, and the order matters: steps 2 and 3 can disqualify the run, and
running them last means filling fourteen rows off a run that proved nothing. The
queries are the ones already on this page; nothing below needs deriving.

| # | Step | Pass condition | If it does not pass |
| --- | --- | --- | --- |
| 1 | Find the first scheduled `digest.yml` run on `main` at cap 5000. Take its run id and the month file its rows landed in | a run id and a `state/item-health/<YYYY-MM>.csv` | the cap has not run yet; stop |
| 2 | Prove the run exercised the change: `read past the old cap` is 1 or more | at least one row with `source_words` above 1923 | **the run is not evidence.** Wait for the next one. Every figure below would be a cap-2500 figure |
| 3 | Prove the run is comparable: `items_planned` is 160, exactly four `work` jobs, every one concluded `success` | all three | the clock means nothing; wait for a run that meets all four conditions of [Trigger A](#trigger-a---the-shard-clock) |
| 4 | **Trigger B.** Count `code = context_exceeded` in the month file for that run | 0 | **revert.** One row is the finding; take [the rollback action](#the-rollback-action) |
| 5 | **Trigger A.** Read the slowest `work` job's wall-clock from the jobs API | at or under 110 minutes | one run over is inside the host lottery. Record it and watch the next two - **revert on two of three** |
| 6 | Fill rows 1 to 14 of [the sheet](#the-rows), replacing `not yet measured` with the value and the date | fourteen values | a row you cannot fill names its instrument in the table; say which one was missing rather than leaving the row reading `not yet measured` |
| 7 | Read row 9 against the context bound | `n_tokens_max` at or under 7,800 | **the cap comes down to 4000 and `n_ctx` does not move.** This is ESCALATE trigger 4 |
| 8 | Read row 7 against the fifth rung, not against zero | a rise near +45 tokens, on items at 3,000 words and up | a rise on items **below** 3,000 words is the 2026-08-26 band defect, not the rung |

**Steps 4 and 5 are the two that can revert the change, and they fail in
opposite ways.** Trigger B is one row and one run - it needs no repeat, because
at cap 2500 that row was impossible by arithmetic. Trigger A is a clock in a
lottery that moved a shard 1.37x within one run, so it needs two of three.

**When every step passes, say so on this page.** Replace the sheet's opening
sentence - the one that says no value is measured yet - with the run id and the
date, and strike the `truncation_cap_tokens` half of the
[Still unmeasured](../reference/measurements.md#still-unmeasured) row in the same commit. A sheet that stays
blank after its run has happened reads as a run that never happened.


## Eight work shards

**Measured 2026-08-25** on GitHub-hosted `ubuntu-latest` (4 vCPU, 16 GB), run
`32869125768` - a `Content refresh` dispatch at `shards = 8` and
`faithfulness = true`, commit `5773762`, eight `work` jobs,
`Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record) through `llama-server`,
llama.cpp `b10598`,
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
four `work` jobs, `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record), llama.cpp `b10598`.
Every row is
already on this page under
[Model throughput across the four workers](../reference/measurements.md#model-throughput-across-the-four-workers).

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
restored the one entry `llm-Qwen3-8B-Q4_K_M.gguf-b10598-v3` (retired incumbent, historical record),
4,943,540,782 bytes
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

**Superseded on 2026-08-27.** The dispatch this section was waiting for was
authorized by the owner, fired, and published. Everything below is kept as the
state of the argument before that run; the run itself is
[Eight work shards, paired](#eight-work-shards-paired-2026-08-27), and that is
the section to cite.

Three of the four conditions this section had set were met by the run above. The
slowest `work` job fell from 113.1 to 58.8 minutes. The whole run finished in
104.8 minutes against the job's `timeout-minutes: 330`. Artifacts and cache bytes
are inside Rule #2. The fourth - every shard's memory peak clear of 16 GB - is
unread rather than failed, and the resident-set figure that stands in for it is a
per-machine number the shard count does not change.

**The measurement above is on a model that no longer runs.** Both arms of the
1.92x - the four-shard baseline of 2026-08-24 and the eight-shard run of
2026-08-25 - are `Qwen3-8B-Q4_K_M`, retired on 2026-08-27. Nothing about the
fan-out argument depends on the weights, but every number in it does, and a
number measured on retired weights may not size a live config (Rule #10). That
is why the paired run was worth its runner time.

Three things had to hold before `run.max_parallel` could move, and all three are
now answered:

1. **A day at eight shards has to publish.** **Met.** Run `33114410534`
 published the 2026-08-27 day with every chart it names present. Run
 `32869125768` had lost its day at the commit step to an asset-name conflict,
 and that cause was removed the same day: a rendered chart is filed under its
 item's own id, so two runs cannot pick one path for two stories
 ([../architecture/publishing/visuals.md](../architecture/publishing/visuals.md)).
2. **A second run at eight, on a different day, that reaches `assemble`.**
 **Met, and better than asked.** The same date and the same model as its
 four-worker baseline, which removes the confound this condition was written
 to avoid rather than merely repeating the observation.
3. **`route` gets an answer.** **Answered, and the answer is that the question
 was mis-scoped.** It assumed the fan-out and the router were coupled. They are
 not: `route` is one unsharded job that starts after every worker finishes and
 cannot observe the worker count. What the eleven runs on record show is a
 stage bounded by a clock that usually runs out, independent of anything the
 workers do
 ([The route stage's per-item cost](#the-route-stages-per-item-cost-over-every-run)).

What is left is a decision rather than a measurement, and it is written up under
[What is left to decide](#what-is-left-to-decide).


## Eight work shards, paired (2026-08-27)

**Measured 2026-08-28** from the GitHub jobs API and the day's committed
`run.json`. Two runs of **one date, one model, one plan size** - which is what
the 2026-08-25 pair above could not offer:

- Run `33073809079`, scheduled, four `work` jobs, 40 items each.
- Run `33114410534`, a `Content refresh` dispatch at `shards = 8` and
 `faithfulness = true`, commit `ad630f7`, eight `work` jobs, 20 items each.

Both on GitHub-hosted `ubuntu-latest` (4 vCPU, 16 GB), `Qwen3.5-9B-Q4_K_M.gguf`
summarizing through `llama-server`, `Qwen3-4B-Q4_K_M.gguf` routing, llama.cpp
`b10598`, 160 items planned.

| Job | Four workers | Eight workers |
| --- | ---: | ---: |
| `plan` | 3.2 min | 3.1 min |
| slowest `work` | **85.6 min** | **53.4 min** |
| fastest `work` | 62.6 min | 29.0 min |
| all `work` | 76.7 +/- 10.1 min | 43.1 +/- 8.6 min |
| `route` | 22.1 min | 41.6 min |
| `assemble` | 1.2 min, success | 1.2 min, success |
| `plan` start to last job end | 112.2 min | 99.4 min |

**The slowest worker fell 32.2 minutes, which is 1.60x - not the 1.92x the
unpaired comparison gave.** Both are consistent with halving the work each
worker carries and neither reaches 2x. The paired figure is the lower one
because **halving the items does not halve the fixed cost**: checkout,
`pip install`, the cache restore and the weights load are paid once per worker
whatever it carries. Per item the eight-worker run is therefore *worse* - 2.14
minutes an item at four workers, 2.67 at eight. Eight workers buy wall-clock by
spending more machine time in total, which on a public repository costs nothing
(Rule #2).

**The spread inside the eight-worker run is 1.84x**, 29.0 to 53.4 minutes,
against 1.37x inside the four-worker run. Two points sampled across a spread
that wide do not support fitting a fixed cost, so none is quoted here.

### The day published, and both asset-name shapes coexist in it

This is the first eight-worker day that ever reached a reader.

The published 2026-08-27 day carries **25 charts over 25 distinct paths, and 25
SVG files are in the tree** - no path names a missing file, and no file is
unnamed. Ten carry the retired `<vertical>-<NN>` name, written by run 1 before
the naming change merged; fifteen carry the `<item_id>` name. One directory, two
shapes, no collision. That is what "the path is stored, not derived" means in
practice, and it is the check the 2026-08-25 failure would not have survived.

### The fan-out did not cost the day any visuals

Read this before citing the two `route` rows above against each other. **It
would be wrong to conclude that eight workers cost the day 18 unrouted items,
and that conclusion was drawn once before this paragraph existed.**

`route` is one unsharded job that starts after every worker has finished. It
cannot observe the worker count, and it is bounded by a wall-clock budget rather
than by a share of anything. So the two rows are not a before and an after -
they are two draws from
[The route stage's per-item cost](#the-route-stages-per-item-cost-over-every-run).
Against the eleven runs on record, the eight-worker run left **18 items
unrouted, which is exactly the median**, and the four-worker run left **0, which
two of eleven runs manage**, while turning in the fastest per-item cost ever
measured. **The four-worker run is the outlier of that pair, not the baseline.**

### What is left to decide

Not a measurement. Eight workers make the day ready about half an hour sooner,
publish correctly, and stay inside every Rule #2 budget. What they do not do is
make `route` faster, because nothing a worker does reaches it.

Sharding `route` is the lever that would, and the asset-name change unblocked it
on 2026-08-27. What it costs in extra cache restores and model loads against
what the split saves is unmeasured, and that measurement is the work.

`run.max_parallel` moves in its own commit, naming this run, when somebody
decides it should.


## The route stage's per-item cost, over every run

**Measured 2026-08-28** over every committed `run.json` that routed anything -
**11 runs across 2026-08-25, -26 and -27** - on GitHub-hosted `ubuntu-latest`,
`Qwen3-4B-Q4_K_M.gguf` through `llama-server`, llama.cpp `b10598`.

Cost is `route_ms / (items_routed - items_prefiltered)`. A pre-filtered item is
decided from the article's own numbers without posting to the model, so dividing
by `items_routed` would report a rate for work that never happened.

| Quantity, over 11 runs | Lowest | Median | Highest |
| --- | ---: | ---: | ---: |
| Seconds per asked item | 19.8 | **48.9** | 54.8 |
| Items left unrouted | 0 | **18** | 49 |
| Share of the 40-minute budget spent | 51% | **100%** | 126% |

**The stage spends its whole budget on 10 of the 11 runs, and leaves items
unrouted on 9 of them.** That is the shape of this stage rather than a fault in
any run: it is bounded by a clock, and the clock runs out. A run that finishes
early is the exception, and there is one.

**One run's figure is a draw, not a rate.** The 19.8-second low is run
`2026-08-27-1`, 1.7 times faster per item than the next-fastest run on record.
Quoting it - or any single run - as "what `route` costs" is how an ordinary run
comes to look like a regression, which is exactly what happened when the
eight-worker run was first read against it. Size a design against the
distribution, never against one draw (Rule #10).

**The spread has a suspect and it is not proved here.** This page already
records that the host moves prompt-reading throughput 3.1x to 3.4x between CPU
models, and `route` draws its host the same way `work` does. That is one
observation per part, so it names a cause rather than establishing one.

**Nothing committed records which CPU a `route` job drew.** The run manifest
carries `runner: ubuntu-latest`, which is the label and not the part.
`state/fingerprints.csv` does carry a CPU model, but it is the `work` job's, it
is appended only when the pipeline fingerprint changes - two rows in this
project's history - and it exists to pin reproducibility rather than to measure
throughput. The console reads neither. **The `work` job stopped having this
problem on 2026-08-29**, when every shard began filing its own `cpu_model` in
`state/runtime-counters.csv` ([The instrument Trigger A reads](#the-instrument-trigger-a-reads)),
and that fix does not reach here: `route` runs no shards and writes no counters
row. So the swing above can be observed and cannot yet be attributed. A
committed row at `route` grain is what would change that, and it has not been
built.


## Which way the grader's length bias runs

**Measured 2026-08-29** on an a developer machine laptop (10 cores, 12 logical, 31.8 GB
RAM, Python 3.14.2, torch 2.13.0 CPU, transformers 4.57.6), over the
**117** (premise, summary) pairs the production run of 2026-08-28 actually
scored - run `33179908136`, all four `evidence-*` artifacts. Taken by
`backend/utilities/grader_length_bias.py`.

**Each item is its own control.** The same premise and the same summary are
scored twice and nothing else varies: once at today's `900/150/anchored`
geometry, once at a 1,923-word window that holds every premise in the corpus
whole. The obvious query - mean `hhem` above and below 900 words - cannot answer
this, because long articles may simply be more summarizable and that confound is
inseparable from the instrument.

**A note on which half of this is a laptop figure.** The score differences are
not: HHEM-2.1-Open runs deterministic on CPU, so the same two texts produce the
same two numbers on any machine. The seconds are, and the rule at the top of this
page applies to them.

### The difference, by how many windows the article takes today

| Windows today | Items | Mean (today - whole-article) | Lowest | Highest | Stdev |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 91 | **+0.0000** | +0.0000 | +0.0000 | 0.0000 |
| 2 | 16 | **-0.2178** | -0.7769 | +0.0014 | 0.2720 |
| 3 | 10 | **-0.3986** | -0.8783 | +0.0353 | 0.3526 |

**Systematically negative, and it deepens with the window count: the mark-down
for depth wins and best-of-N over-scoring loses.** A three-window article scores
**0.40 lower** than the same article read whole, on the 0-to-1 scale whose high
band starts at 0.80 and whose medium band starts at 0.50 - a drop wider than the
whole medium band, applied only to the longest articles. The best-of-N effect is
present and small: the largest positive difference in the corpus is **+0.0353**
against a largest negative of **-0.8783**, so it is 25 times smaller than the
effect it is fighting.

**The 1-slice row is the control and it must read exactly zero.** An article
short enough to be one window under both geometries is scored over the identical
string twice, so a deterministic scorer cannot differ - 91 of 91 read
`+0.0000` to four decimals. A non-zero there would mean the harness compared two
different things and no other row could be read.

### The split by whether the article was cut does not separate the two effects

| Article | Items | Mean | Lowest | Highest | Stdev |
| --- | ---: | ---: | ---: | ---: | ---: |
| was cut | 7 | -0.3104 | -0.7798 | +0.0353 | 0.2886 |
| was not cut | 110 | -0.0482 | -0.8783 | +0.0014 | 0.1699 |

**Read these two rows as slice counts wearing a different label.** A cut article
sits on the 1,923-word cap, which is 3 windows, so all 7 cut rows are 3-window
rows and their -0.3104 is what 3 windows cost rather than what a cut costs. The
110 uncut rows include the 91 one-window zeros, which is most of why their mean
is near zero. Separating the cut from the window count needs cut and uncut items
at the same window count, and there are 7 and 3 of those - too few to say
anything (Rule #10). The cut is what a bigger `extract.truncation_cap_tokens`
would change, so this split has to be re-taken when the cap moves.

Cut status is read as the arithmetic and not the flag: `source_word_count`
minus `source_seen_word_count`, which is the cut and nothing else
([../concepts/evaluation.md](../concepts/evaluation.md#the-two-source-word-counts-are-one-counter-before-and-after-the-cap)).
`truncation_flagged` changed meaning on 2026-08-28 and is true on one row in the
whole ledger, so splitting on it would split on something else.

### Seconds a pass, at each window size

| Geometry | Passes | Mean | Lowest | Highest | Stdev |
| --- | ---: | ---: | ---: | ---: | ---: |
| Today: 900/150 anchored, 1 to 3 windows | 117 | **4.815 s** | 0.230 s | 18.954 s | 4.802 |
| One 1,923-word window | 117 | **4.278 s** | 0.250 s | 19.395 s | 4.297 |

**A whole-article window is cheaper than today's slicing, by 11 percent, not
dearer.** One 1,923-word forward pass costs less than the two or three 900-word
passes it replaces, because attention has not yet reached the length where its
quadratic term beats three lots of fixed per-call cost. **91 of the 117 items
score the identical text in both columns**, so the whole of the gap comes from
the 26 multi-window items and the figure understates the per-long-item saving.

The stdev is nearly as large as the mean in both columns because premise length
runs from 3 words to 1,923 in this corpus. It is the spread of the corpus, not
noise in the clock.

**HHEM has no working maximum input length, confirmed by observation.** The
tokenizer prints `Token indices sequence length is longer than the specified
maximum sequence length for this model (893 > 512)` and the model returns a
score anyway, at 893 tokens for a 900-word window and roughly 2,500 for a
1,923-word one. The 512 in the config is vestigial; `predict` never passes
`truncation=True`. This is what makes the wide arm of the comparison possible at
all.

### What this measurement does not say

It says the instrument moves with slicing. It does **not** say the whole-article
number is the truer one - that needs the human labels, and **0 of 60** are drawn
(Rule #10). No default moved in the commit that recorded this:
`evaluation.chunk_words` is still 900.

**One corpus, one day, one run.** 117 items from 2026-08-28, of which only 26
take more than one window. Re-take it on a second day before treating -0.3986 as
the value rather than the direction.

### How it was taken, and how to take it again

The pairs are gitignored (`CLAUDE.md` section 0a - an article body is not ours to
republish) and reach the tool as a workflow artifact with 14 days of life:

```
gh run download <digest-run-id> --pattern 'evidence-*' --dir <dir>
python backend/utilities/grader_length_bias.py --evidence <dir>
```

The tool refuses an absent or empty package instead of printing zeros, because a
report of `0.0` over no data is indistinguishable from a real zero and this
project has published a figure that way once before (the 2,232 rows that never
measured the truncation gap). Running it needs the `faithfulness` extra and about
1 GB of model download; the scoring itself took 95 minutes for 234 passes on the
laptop above.

**One confound was ruled out rather than assumed.** `chunks` re-joins a
window's words on single spaces while the whole-article pass reads the premise as
it stands, so the two arms differ in whitespace on multi-window items, and the
1-slice control cannot see that. Scoring 5 at-cap premises raw and
whitespace-collapsed moved the score by **0.000000** every time (n=5,
2026-08-29), which is what SentencePiece collapsing whitespace predicts and is
now observed rather than assumed.


## What rewriting the published truncation notes would buy

**22 sentences of 154, so the archive keeps the sentence it shipped.** The cut
note gained a scale on 2026-08-29 - `We could only read the first 36 percent of
this page.` in place of `We could only read the first part of this page.` -
and `assemble` writes it once, when the day is built. Nothing re-assembles a
published day, so every item published before that date still carries the older
sentence.

Counted 2026-08-29 over every `frontend/public/digest/**/digest.json`:

| Quantity | Value |
| --- | ---: |
| Published items carrying the old sentence | 154 entries, **153 distinct item ids**, over 8 days |
| Published items carrying the new sentence | 2 |
| Of the 153, joined to a row of `state/scores.csv` | 153 |
| Of those, a share that could be recomputed | **22** |

**The 22 is the whole decision.** A share needs the length before the cut, and
`source_word_count` only became that number on rows stamped `2026-08-27T20:30`
or later - before that it was the post-cap count read through a second counter,
which [evaluation.md](../concepts/evaluation.md) records. By ledger stamp the 153
split 2 / 128 / 1 / 22 across `2026-08-21T03:00`, `2026-08-23`, `2026-08-26` and
`2026-08-27T20:30`. **Re-running `assemble` over the other 131 would regenerate
the sentence they already carry**, because `read_share` returns `None` without a
pre-cap length and the note degrades to exactly the old string.

So a backfill rewrites 8 committed days to change 14 percent of the notes it
touches. That is not worth a payload rewrite, and the count is here so the next
person does not re-derive it to reach the same answer.


## How much of a plot a chart readout covers

**40 to 55 percent on `ThroughputTrend`, and about a quarter on
`CompressionScatter`, from the same treatment.** Both draw the readout as
`absolute inset-x-3 top-3` over a plot of `console.chart_height`, which
`config/appearance.json` sets to 220 px. The difference is the copy, not the
position.

Measured 2026-08-29 over the committed `state/scores.csv`. `ThroughputTrend`'s
`caption` appends one median per run of the day, and the day's run count is
what drives the length:

| Quantity | Value |
| --- | ---: |
| Caption characters, median over the 8 days | **171** |
| Caption characters, longest day | **221** (three days, five runs each) |
| Captions stacked in the readout | 2, one per series |
| Rendered lines at 12 px in the card's width | 4 to 6 |
| Readout box height, including its padding and its 12 px offset | 88 to 121 px |
| Share of a 220 px plot | **40 to 55 percent** |

`CompressionScatter` prints two short lines through the same markup and covers
about a quarter. **That pair is the finding**: a readout whose text grows one
clause per run of the day has no bound, so a length rule belongs on the rendered
box rather than on the sentence.

It was recorded rather than patched, because the console's chart engine was
being decided at the time and whichever engine won would own the readout. The
engine landed days later and the rule landed with it: `chart.readout_max_share`
in `config/appearance.json` holds a readout to 0.33 of the plot it sits on,
measured on the rendered box, so it binds a hand-written strip and the engine's
own tooltip alike. The run medians left the caption in the same change. Jony's
ruling that a readout is pinned to the top of the plot and never to the pointer
was not what was wrong here and stands. The rule as it stands today is in
[../concepts/design-system.md](../concepts/design-system.md).


## What the design-system reset cost, and what a page uses of the screen (2026-08-29)

Rule #10 had been applied to everything the runner touches and to nothing the
reader sees, which is part of why the reset was needed. These are the numbers
that did not exist.

**Hardware and method.** One Windows machine, node 24, Chromium via Playwright,
commit at the close of the twelve-row reset. First-load JS is the sum of `gzip -9`
over each module in a route's `modulepreload` list, taken as the HEAVIEST of five
builds of identical source rather than the mean - a mean fires on half of all
builds. The spread across those five was 13 to 15 B per route, against a 64 B
tolerance.

### How much of the screen a page uses

Measured before the reset and after, same pages, same browser.

| Viewport | Before | After |
| --- | --- | --- |
| 1536 px | 40.6 percent | 83.3 percent |
| 1209 px | 51.6 percent | 99.0 percent |
| 1024 px | 60.9 percent | 98.8 percent |
| 614 px | 91.5 percent | 98.0 percent |
| 312 px | 83.3 percent | 96.2 percent |

The measure holds at 68ch from 819px upward, so the line length a reader gets is
unchanged - what moved is everything that is not prose. The single
`max-w-2xl` at 672px on the layout was the whole cause, and it was the only
`max-w-*` in the frontend.

### First-load JS per route, at the close

| Route | Bytes |
| --- | --- |
| `/` | 52,474 |
| `/<date>/` | 51,707 |
| `/<date>/<topic>/` | 51,801 |
| `/archive/` | 53,109 |
| `/console/` | 76,716 |
| `/evals/` | 43,687 |
| `/404` | 42,736 |

The chart engine is NOT in any of these. It is a lazy chunk of 153,204 B
gzipped, fetched only when a chart hydrates, and no page preloads it -
`frontend/tests/charts.spec.ts` fails the build if one ever does. Importing the
same package whole instead of registering only the chart types in use read
345,959 B for the same one chart, so the registration list is worth 56 percent
of that download.

### The console frame

| What | Before | After |
| --- | --- | --- |
| Containers that must scroll sideways at 1440px | 7 | 0 |
| Narrowest chart | 164 px | 380 px |
| Run-strip day column inside a 1,217px frame | 16 px | grows to 34 px |
| Page height | 6,562 px | 8,794 px |

The height went UP, and the reason is that the same plan added a funnel, a KPI
strip, a growth waterfall and a failure-mix chart to that page. A row cannot
both add the vocabulary and remove the height it costs. The seven scrollbars
were gone before the console row started - the fluid frame removed them.

### Days to the 1 GB Pages ceiling, re-derived

Built site on 2026-08-29: **143,717,288 B**, 137.1 MB, leaving 886.9 MB.

Per published day, route tree plus staged payload, over the nine days in the
tree:

| Date | Items | Bytes |
| --- | --- | --- |
| 2026-08-21 | 4 | 85,879 |
| 2026-08-22 | 10 | 401,722 |
| 2026-08-23 | 147 | 3,901,093 |
| 2026-08-24 | 731 | 17,258,646 |
| 2026-08-25 | 724 | 17,400,157 |
| 2026-08-26 | 621 | 15,201,991 |
| 2026-08-27 | 334 | 7,703,972 |
| 2026-08-28 | 117 | 2,973,406 |
| 2026-08-29 | 212 | 4,982,587 |

**Bytes per day is the wrong unit and bytes per item is the right one.** Over
the seven mature days (100 items or more) the day cost runs 2.97 MB to 17.4 MB,
a factor of 5.9 - because the item count runs 117 to 731. Divide it out and the
per-item cost is **24,378 B, spread 23,066 to 26,538**, a 14 percent range. The
day rate is a function of the item ceiling, which is a knob in `config/`; the
per-item cost is a property of the site.

At the current mix the mean mature day is 9,917,407 B, which puts the cap at
about **94 published days from 2026-08-29, near 2026-11-30**. That is later than
the 2026-10-22 recorded on 2026-08-27, and the difference is not this plan
making the site smaller - it is the two most recent days carrying 117 and 212
items where the days behind them carried 731. **A cap date computed from a day
rate moves when the item ceiling moves.** Anyone re-deriving it should divide
the per-item cost by the ceiling in force rather than averaging whatever days
happen to be on disk.


## Three figures the ledgers already held (2026-08-30)

**Measured 2026-08-30** over the committed ledgers at `origin/main` `57a930e`:
`state/runtime-counters.csv` (34 rows, 7 runs), `state/item-health/2026-08.csv`
(4,167 rows, 23 runs) and `state/scores.csv`. Deterministic arithmetic over
committed files, so hardware does not apply and the spread quoted is the spread
of the rows themselves. Every figure below re-derives with
`python backend/utilities/measure_ledgers.py`, which is the code that produced
them.

Nothing was instrumented to take these. All three are arithmetic over cells the
pipeline had already been writing for days, and none of the three had been done.

### The model is busy for 89 percent of a work shard

Run `2026-08-29-2` is the only run whose two ledgers can be joined: four shards,
four clocks, one execution each.

| Where the shard clocks went | Seconds | Share |
| --- | --- | --- |
| summarizing | 11,929.8 | **89.3 percent** |
| fetching | 86.6 | 0.65 percent |
| extracting | 5.0 | 0.04 percent |
| everything else | **1,340.6** | **10.0 percent** |
| four shard jobs, summed | 13,362 | 100 percent |

**"Everything else" is 335.1 s a shard - 5.6 minutes** of cache restore, `pip
install`, weight load, warmup and commit, repeated once per shard.

**What that decides: shard count is a real lever.** Nine tenths of a shard is
the model working, so splitting a run across more machines moves nearly all of
it. The price is that the 5.6 minutes is paid again by each new shard: at four
shards the fixed cost is 10.0 percent of the run's clock, and eight shards
against the same model time would put it near 18 percent. That is the cost side
of the question [Eight work shards](#eight-work-shards) measures from the other
end.

**The figure is computed twice and the difference is named.** The item ledger
gives `13,362 - (86.6 + 5.0 + 11,929.8) = 1,340.6 s`. The server's own counters
give `13,362 - (prompt_seconds_total + tokens_predicted_seconds_total) =
1,443.7 s`, which is 284, 346, 366 and 447 s over the four shards and is row 2
of [What the first run at cap 5000 must record](#what-the-first-run-at-cap-5000-must-record).
The 103.1 s between them is accounted for rather than left over: fetching
(86.6 s), extracting (5.0 s), the summed clock residual of the next figure
(7.3 s) and 4.1 s from three items that recorded a stopwatch but no server
timings. That is 103.0 s of 103.1.

**Per SHARD has the instrument and not yet the population.** `shard` landed on
`ItemHealthRow` on 2026-08-30, hours after these figures were taken, and **0 of
the 4,167 committed rows carry a value** - a column is null on every row written
before it existed. So every figure above is a whole run, which averages the
shards together, and the split arrives with the next scheduled run. That matters
because the read rate spreads 2.30x between shards inside one run, which is
exactly the variance a per-run figure hides. `measure_ledgers.py` reads the
column and splits on it as soon as a run's rows carry one; nothing else has to
change.

**The other clocked run cannot be read at all, and that is a defect worth
filing.** Run `2026-08-29-3` filed **six counter rows for four shards** - shards
1 and 3 were each scraped twice, about two hours apart (21:06 and 23:15, 21:10
and 23:38 UTC). Its item ledger holds **212 rows for 168 distinct items**: 44
rows duplicate the ledger's own `(date, run_id, item_id)` key, because both
executions append and `state/*.csv` merges line by line, so neither execution
can see the other's rows. Summed anyway the run reports **-394 s unaccounted**,
which is summarizing at 100.3 percent of the shard clocks and is impossible. All
123 items of run `2026-08-29-4` appear in run `2026-08-29-3` as well. None of
that is a measurement; it is the record of a day that ran twice.

**24 of 34 counter rows carry no clock at all.** `job_seconds` and `cpu_model`
landed on 2026-08-29, so the six runs before that date cannot be read this way
and never will be.

### Our stopwatch and the server's own clocks agree to 0.066 percent

`summarize_ms` is the pipeline's stopwatch around the HTTP call.
`prefill_ms + decode_ms` is what the model server said the same call cost. Over
the 2,317 committed rows that carry all three, from run `2026-08-25-1` to
`2026-08-29-4`:

| Residual, `summarize_ms - (prefill_ms + decode_ms)` | Value |
| --- | --- |
| minimum | 6 ms |
| median | 79 ms |
| 95th percentile | 236 ms |
| maximum | 2,639 ms |
| negative | **0 of 2,317** |

**The median residual is 0.065 percent of the median summarize call** - 79 ms
against 122,432 ms. Summed over the ledger it is 220.5 s of 334,944.8 s, which
is **0.066 percent**; the worst single item spent 1.698 percent of its call
outside the model's own clocks.

**What that decides: when a day is slow it is the model, not us.** Transport,
JSON and validation are two thirds of one tenth of one percent of what
summarizing costs, so there is no room in the client for a slow day to hide. It
also says the split `summarize_ms` was given is complete - `prefill_ms` and
`decode_ms` account for 99.934 percent of the wall clock we measure around the
call, and the part they do not name is 79 ms.

**Zero negatives, against an expectation of "occasionally".** The measurement
was ordered on the understanding that a negative residual turns up now and then,
from the two clocks rounding the same way. It has never happened: the smallest
residual in 2,317 rows is +6 ms. The threshold this was to earn - a column of
its own if the alarm fires more than once - has fired zero times, so the
residual stays a figure on this page and is not published.

**It halved on 2026-08-27, and nothing here says why:**

| Runs | Rows | Median | 95th percentile | Maximum |
| --- | --- | --- | --- | --- |
| `2026-08-25-1` to `2026-08-26-5` | 1,345 | 114 ms | 279 ms | 2,639 ms |
| `2026-08-27-1` to `2026-08-29-4` | 972 | 52 ms | 174 ms | 1,293 ms |

The boundary is the day the configured 9B replaced the retired 8B
(`pipeline_fingerprint` `f0d4ecc7` to `6a23e277`). A residual is our side of the
call, so the model is an odd cause for it, and more than one thing changed that
day. It is recorded as a boundary and not as an attribution (Rule #10).

### The extractor's 1.3 tokens a word is right to 0.01 percent

`input_tokens` regressed on `source_words` - **regressed, never divided** - over
every committed row written at `extract.truncation_cap_tokens` = 5000:

| Quantity | Value |
| --- | --- |
| rows | **413** |
| runs | `2026-08-29-2` (104), `2026-08-29-3` (194), `2026-08-29-4` (115) |
| slope | **1.2999 tokens an article word** |
| intercept | **998 tokens**, which is the fixed prompt |
| residual spread | 93 tokens |
| r-squared | 0.9876 |
| article widths covered | 35 to 3,846 words, median 623 |

**`extract.TOKENS_PER_WORD` is 1.3 and the measured rate is 1.2999.** That
constant is what places the cut, and it is right to 0.01 percent. It is the
answer to whether the cap and the tokenizer agree, and nobody had checked it
since the cap moved on 2026-08-29.

**How the 413 rows were chosen, and it is two proofs rather than one.** A run
counts as running at the configured cap if either instrument says so, and where
both apply they agree:

- **The eval ledger.** `state/scores.csv` carries `pipeline_fingerprint`, and
 the cap is a field of the payload that stamp is taken over, so the stamp moved
 when the cap moved. Live means the stamp on the newest committed row, the same
 rule `label_queue.py` uses for `scorer_version`. It admits `2026-08-29-2` and
 `2026-08-29-3`.
- **The item ledger itself.** `source_words` is post-cap and cannot exceed
 `int(5000 / 1.3) = 3846`, so a row sitting exactly on 3,846 with a larger
 `source_words_before_cap` is physical proof the configured cap did the
 cutting. It admits `2026-08-29-3` and `2026-08-29-4`.

Neither alone is enough, and that is the point. Run `2026-08-29-4` has no eval
rows committed at all, so it has no stamp; run `2026-08-29-2` never had an
article long enough to cut, so it cut nothing. Either instrument on its own
would have dropped about a quarter of the population for want of the other.

**The widest article the cap has ever produced.** One article,
`business-economy-0152846431`, 6,562 words before the cap and 3,846 after it,
cost **5,757 prompt tokens**. With `models.inference.max_output_tokens` of 900
that is **6,657 tokens of an `n_ctx` of 8,192 - 81.3 percent used, 1,535
spare**. It is the first item ever to reach the 3,846-word ceiling. It appears
three times in the ledger, twice in run `2026-08-29-3` and once in
`2026-08-29-4`, because that day ran twice - so the at-cap population is three
rows and one article, and n=1 article is a sighting rather than a distribution.

**Dividing would have read 1.497 tokens a word on that item**, 15.2 percent
above the regression, because the ratio carries the 998-token fixed prompt
inside it. Pooled over all 413 rows the ratio is 2.625, twice the true rate,
because most articles are short and the fixed prompt dominates them. That is the
whole reason this is a regression.

**Two corrections to the record, both to row 10 of
[What the first run at cap 5000 must record](#what-the-first-run-at-cap-5000-must-record).**

1. That row reads **1.387 tokens an article word, intercept 951, residual spread
 119, over 104 items**. Re-derived here it reproduces exactly - for run
 `2026-08-29-2` alone, which is what it measured. That run's longest article
 was 2,772 words; the two runs after it reached 3,846, and the widest point is
 what sets a slope. Over all three runs the slope is **1.2999**, 6.3 percent
 below the one-run figure, and 413 rows is the better estimate.
2. That row checks the result against "1.35 to 1.44 measured on this project's
 prose". **1.2999 sits below that band**, so the band is superseded rather
 than confirmed. What survives unchanged is the conclusion it was there to
 support: 1.59 tokens a word is what it takes to overflow the window, and
 1.2999 is **18.2 percent under it**.

**And the population rows 6 and 7 of that sheet could not find has arrived.**
The one at-cap article was summarised three times, at 296, 353 and 353 output
tokens over 58.6, 90.5 and 90.5 s of decode - 5.05, 3.90 and 3.90 tokens a
second, against 4.89 tok/s over 25 at-cap items at the old cap. One article is
not a rate. What it does settle is that an at-cap item now exists, so the rows
have an instrument and a population for the first time.

## How old the digest was publishing, 2026-08-30

Source: the 2,900 items in the committed day payloads under
`frontend/public/digest/` for 2026-08-22 to 2026-08-29. Each item's age is
`runs[introduced_by_run].at - published_at`, so it is the age at the moment the
run added it, not the age today. `published_at` on a committed item is the date
the run believed, so a future stamp is already resolved to first sight. Every
one of the 2,900 carried a date; none fell back.

| statistic | age when added |
| --- | --- |
| minimum | -3.3 h (inside the 6 h forward tolerance) |
| median | 5.5 h |
| 90th percentile | 856.1 h (35.7 days) |
| 99th percentile | 6,246.2 h (260.3 days) |
| maximum | 155,383.6 h (6,474.3 days, 17.7 years) |

The oldest is `et-default`, "Prabhudas Lilladher downgrades Infosys to reduce
with Rs 1,246 target", dated 2008-12-05 and published in a 2026 digest.

What each candidate window would have kept:

| window | keeps | drops |
| --- | --- | --- |
| 24 h | 2,074 (71.5%) | 826 (28.5%) |
| 48 h | 2,155 (74.3%) | 745 (25.7%) |
| 72 h | 2,237 (77.1%) | 663 (22.9%) |
| 7 days | 2,411 (83.1%) | 489 (16.9%) |

The curve is almost flat between 24 h and 7 days: a week only buys back 337
items over a day, because what sits past 24 hours is not two-day-old news, it is
a back catalogue. That is the number that made 24 the shipped value - the
wider windows pay a real freshness cost and recover almost nothing.

At 24 hours the loss is concentrated:

| desk | survives | loses |
| --- | --- | --- |
| `world` | 624 of 652 (95.7%) | 28 |
| `india` | 647 of 680 (95.1%) | 33 |
| `business-economy` | 242 of 318 (76.1%) | 76 |
| `energy` | 310 of 476 (65.1%) | 166 |
| `ai` | 251 of 774 (32.4%) | 523 |

The ten feeds that lose the most are archive-style research and institution
blogs: `mistral-news` (43 of 44), `google-research-blog` (42 of 47),
`deepmind-blog` (41 of 43), `huggingface-blog` (39 of 44), `mit-news-ai`
(36 of 39), `nist-news` (36 of 37), `nvidia-technical-blog` (33 of 47),
`amazon-science` (25 of 27), `ai2-blog` (25 of 27), `simon-willison` (20 of 28).
Ten of 104 sources lose every item they published.

**What to re-read after a week of the gate.** Three numbers, in this order.
First, whether a run still reaches `safety_ceiling_per_run` - if it stops
binding, supply rather than the ceiling now sizes the day and the ceiling
argument in [`freshness.md`](../architecture/sources/freshness.md) needs
re-deriving. Second, `too_old` summed per vertical from the committed plans,
against the shares above. Third, whether `ai` recovers as its news feeds are
read more often, or stays near a third - if it stays, the AI feed list is the
thing to fix and no threshold will do it.

## What every source yielded, 2026-08-24 to 2026-08-29

**Measured 2026-08-29** over `state/item-health/2026-08.csv` at `origin/main`,
which carries one row per planned article per run. 21 runs, 3,832 planned
articles. Deterministic over a committed file; no spread.

| Quantity | Value |
| --- | --- |
| Source ids that appeared at all | 122 |
| Articles planned | 3,832 |
| Articles published | 2,739 (**71.5 percent**) |
| Articles lost | 1,093 (**28.5 percent**) |
| **Sources that published nothing, not once** | **24** |
| Failures owned by those 24 | 910, which is **83.3 percent of every failure** |
| Slots they consumed per run | **43.3 of 160**, so 27 percent of a run bought nothing |

The loss rate is steady across all six days, which is what makes it a property
of the source list rather than a bad week.

### Where the losses happen

| Stage | Share of the 1,093 |
| --- | --- |
| Fetch: the page answers 4xx, a robots file forbids it, or the host resets | 60 percent |
| Extract: a paywall, or no readable prose on the page | 38 percent |
| Summarize | 2 percent |

Two codes dominate: `http_client_error` (518) and `paywalled` (330). Neither is
a defect in this repository.

### What reaches a reader, by kind of source

**Measured 2026-08-29** over the 1,284 items published between 2026-08-26 and
2026-08-29.

| Tier | Published | Share |
| --- | --- | --- |
| 1, the institution that IS the fact | 194 | 15.1 percent |
| 2, trade press and news outlets | 1,073 | **83.6 percent** |
| 3, community and independent writing | 17 | **1.3 percent** |

94 of the 138 configured feeds contributed at least one item.

### The per-feed cap decides the day, not the score

**Measured 2026-08-29** over the six runs of 2026-08-27 to 2026-08-29.

| Run | Slots | Distinct feeds drawn from | Feeds sitting on the 2-item cap |
| --- | --- | --- | --- |
| 2026-08-27-1 | 160 | 87 | 73 |
| 2026-08-27-2 | 160 | 85 | 75 |
| 2026-08-27-3 | 160 | 85 | 75 |
| 2026-08-28-1 | 160 | 87 | 73 |
| 2026-08-29-1 | 160 | 86 | 74 |
| 2026-08-29-2 | 160 | 82 | 78 |

**Between 73 and 78 of the roughly 85 working feeds hit `max_per_source` in
every run.** The corroborating figure: the fifteen feeds that published most
between 2026-08-26 and 2026-08-29 each published **exactly 22**, which is two
per run across eleven runs.

What this means, said plainly: with 160 slots and two allowed per feed, the list
fills itself from about 80 feeds and the score only decides which handful of
feeds miss out. "A story three independent sources carried is the day's story"
is the stated design ([../architecture/sources/discovery.md](../architecture/sources/discovery.md))
and it is not what is happening. **This is a source-supply result, not a ranking
defect** - the cap stops binding as soon as the pool of working feeds is
comfortably larger than 80.

### A failed address is retried all day and fails again

**Measured 2026-08-29** over the same ledger. The published ledger stops a
repeat; a *failure* is not published, so the next run of the same day plans the
same address again.

| Quantity | Value |
| --- | --- |
| Addresses attempted more than once inside one day | 233 |
| Of those, addresses that never succeeded on any attempt | 231 |
| Repeat attempts that produced nothing | **401** |
| Repeat attempts that produced something | **2** |

Per run the waste is 8 to 41 slots, and it is zero on run 1 of a day by
construction. 403 repeat attempts bought 2 items. Their failure codes are the
ones that cannot change within a day: `http_client_error` (112), `paywalled`
(59), `no_text` (21), `robots_denied` (11).

### Probing the 40 non-producing sources

**Measured 2026-08-29** on a developer machine by fetching
each configured feed URL and one article behind it, with the pipeline's own user
agent. n=1 per feed.

| Finding | Feeds |
| --- | --- |
| Refused from a developer machine **and** from the runner: paywall, robots, or an outright block | 22 |
| Returned a valid feed to a developer machine and 403 to the runner | 7 |
| Answered with a web page and no feed at all - our configured URL is not a feed | 3 |
| Judgement calls: PDF-only articles, connection resets, rate limiting | 8 |

The seven in row two are the reason this table exists. `indianexpress.com`
served **200 headlines** to a laptop while the runner recorded HTTP 403 on every
attempt for weeks. A developer IP is not a runner IP, and this page has recorded
that contrast in the opposite direction before (see the robots policy row
above). A source that fails only on the runner is blocked by address, not
broken.

The three in row three are ours: `anthropic-news`, `cohere-blog` and
`stanford-hai` were configured with the address of an HTML page. Every fetch
returned HTTP 200 and zero items, so feed health recorded a read that succeeded
and a pool that gained nothing. **A feed read can succeed and still be worthless,
and no gate in this repository noticed for weeks.**

### The feed floor counts configured feeds, not working ones

**Measured 2026-08-29** by applying the retirement to `config/sources.json` and
comparing each vertical against its `min_feeds` in `config/taxonomy.json`.

| Vertical | Feeds configured | Feeds that ever produced an item | `min_feeds` |
| --- | --- | --- | --- |
| `ai` | 38 | **28** | 35 |
| `business-economy` | 22 | **12** | 21 |
| `energy` | 24 | **20** | 21 |
| `india` | 27 | **19** | 21 |
| `world` | 27 | **19** | 21 |

`rank.plan_vertical` refuses to plan anything for a vertical below its floor, so
a vertical that drops under it publishes nothing at all.

**Every one of the five verticals is under its floor on the count that matters,
and every one of them passes on the count the gate reads.** `ai` published 52
items on 2026-08-29 from an effective 28 feeds against a floor of 35, so a floor
that is meant to stop a thin desk reaching a reader has been passing a desk it
would have failed. The gate is not wrong about the number it reads; it is
reading a number that stopped describing the source pool.



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

### The CPU model does not sort the per-item cost of the visuals job

**Measured 2026-08-27** from the `route` job log of every `digest.yml` run this
repository holds - 27 runs, 2026-08-22 to 2026-08-26. Method:
`gh run view --repo miztiik/yen-idhazh --job <id> --log` for each `route` job,
then the `model name` line out of `/proc/cpuinfo` and the `route_ms` field of
every `item routed` line that says `asked=True`. Skipped items are left out
because a pre-filtered item costs 0 to 3 ms and would deflate the mean. The
method reproduces the table above: it returns 40.3 s for run `32804437110`,
which is the figure that row already carries.

**None of the six runs above can ever be attributed a CPU.** The
`What this runner is` step landed on 2026-08-25, after all six had run, and no
line naming a processor appears anywhere in their job logs - checked across all
27. Job logs outlive artifacts here, so this is not a retention problem that
waiting would fix. The nine runs below are the whole of the evidence.

| Run | Started (UTC) | CPU | `nproc` | `n_slots` | Items asked | Per item, mean | Median | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `32839359536` | 2026-08-25 10:51 | AMD EPYC 7763 64-Core | 4 | 1 | 62 | **48.9 s** | 47.3 s | 22.2 s | 72.0 s |
| `32863921985` | 2026-08-25 15:08 | Intel Xeon Platinum 8573C | 4 | 1 | 54 | **44.4 s** | 44.7 s | 27.3 s | 79.2 s |
| `32869125768` | 2026-08-25 15:58 | AMD EPYC 9V74 80-Core | 4 | 1 | 49 | **49.8 s** | 50.6 s | 32.6 s | 73.6 s |
| `32887038177` | 2026-08-25 18:59 | AMD EPYC 9V74 80-Core | 4 | 1 | 70 | **34.2 s** | 33.2 s | 19.0 s | 64.0 s |
| `32926523936` | 2026-08-26 03:27 | AMD EPYC 9V74 80-Core | 4 | 1 | 47 | **51.1 s** | 49.9 s | 27.7 s | 88.5 s |
| `32941554666` | 2026-08-26 07:11 | AMD EPYC 9V74 80-Core | 4 | 1 | 44 | **54.8 s** | 54.2 s | 28.5 s | 87.5 s |
| `32960510065` | 2026-08-26 10:53 | AMD EPYC 9V74 80-Core | 4 | 1 | 46 | **52.5 s** | 50.6 s | 30.8 s | 106.3 s |
| `32986307407` | 2026-08-26 15:54 | AMD EPYC 9V74 80-Core | 4 | 1 | 48 | **50.1 s** | 51.3 s | 29.1 s | 80.7 s |
| `33008629212` | 2026-08-26 20:05 | AMD EPYC 9V74 80-Core | 4 | 1 | 48 | **50.8 s** | 47.2 s | 27.5 s | 94.0 s |

**One CPU string covers most of the swing, so the CPU string is not the
answer.** Seven of the nine drew the same part, `AMD EPYC 9V74 80-Core
Processor`, and their per-item means run 34.2 s to 54.8 s - **1.60x on a single
CPU string**, against the 1.92x (21.0 s to 40.3 s) that opened this question.
The other two parts land inside that band rather than outside it: the EPYC 7763
run at 48.9 s and the Xeon 8573C run at 44.4 s. Group the nine by CPU and the
groups overlap completely. Everything else a host could vary was held and read
rather than assumed, because the job log prints it: `nproc` 4 and `n_slots` 1 on
all nine, llama.cpp build 10598 commit `56db501e7` with `llama-server` sha256
`9bcaf7569a1b...`, and weights `Qwen3-4B-Q4_K_M.gguf` sha256 `7485fe6f11af...`,
the exact value `config/idhazh.json` pins.

**This cuts against the suspect the `work` job named.**
[Eight work shards](../archive/measurements-2026-08.md#eight-work-shards) found two Intel Xeon shards prefilling
3.4x faster than six AMD EPYC ones on one day. Prefill is 85 percent of a planner
request in the slow mode, so if that vendor split reached this stage an Intel
job would cost about 40 percent of an AMD one - near 20 s an item, which
is exactly the fast mode. The one Intel job on record cost **44.4 s**, the
middle of the AMD band. Either the split does not reach this stage, or that
Xeon job was not in the fast mode. Nothing here separates the two.

**Only one of these jobs has ever carried both a CPU model and a prefill rate.**
Run `32839359536`: AMD EPYC 7763, **21.09 tok/s prefill** over 62 requests,
median prompt 898 tokens, 48.9 s an item. 21.09 tok/s is the slow mode - the six
runs above span 20.2 to 62.9 - and at 898 tokens prefill alone is 42.6 s of the
48.9, which is 87 percent and matches the 85 to 86 percent the slow runs show.
One observation in one group proves nothing about a group it cannot compare
against.

**The fast mode has not recurred.** Every one of the nine costs 34.2 s or more
an item; the fast mode was 20.7 to 21.0 s. Nine consecutive runs over 33 hours
and not one was fast. The comparison this question needs - a fast run and a slow
run that both name their CPU - has nine observations on the slow side and none
on the fast side.

**Do not average these nine with the six above; they are different regimes.**
`visuals.enabled_kinds` dropped to `[chart]` on 2026-08-25, which switched the
pre-filter on: 35 to 73 items a run are now skipped with no model call, and the
items still asked are the chart-eligible ones, which carry more numbers and more
text. The one new run whose prompt size is readable medians 898 tokens against
622 to 700 on the six - 28 percent more prompt, so 28 percent more prefill, and
40.3 s x 898/700 is 51.7 s. That sits inside the 49.8 to 54.8 s band six of the
nine occupy. The nine read as the slow mode carrying a bigger prompt, not as a
new effect.

**Two instruments added to answer this question did not work. Both are now
explained, and only one of them was a fault.** Both were checked on all nine
runs:

- `grep -m1 'system_info' router.log` **has matched zero times in nine runs.**
 llama.cpp `b10598` writes no line containing that string, so the one line that
 names the instruction sets - AVX2 against AVX-512, the obvious way two hosts
 sharing a CPU model string could differ 3x on prefill - has never been
 captured. The other five lines under
 [What a job log names](../archive/measurements-2026-08.md#what-a-job-log-names) do print. **This was never a
 grep fault**: the line is not printed at all below verbosity 4, so the pattern
 was right and the line was not there
 ([What llama-server reports about its own runtime settings](../reference/measurements.md#what-llama-server-reports-about-its-own-runtime-settings-2026-09-09)).
- The log summary's `grep -E '^(srv|slot) '` **could not match this build's
 output, and that one was a fault.** Every line starts with a timestamp and a
 level, as in
 `0.02.841.335 I srv load_model: initializing, n_slots = 1`, so the anchor
 never fired; the one line that did reach the job log matched on the
 `n_ctx_slot` alternative instead. `slot print_timing:`, which carries
 `prompt eval time`, stopped reaching the job log when the older unanchored
 `grep 'prompt eval time ='` was replaced. Measured 2026-09-09 over the four
 committed captures: 1 line of 40 found, and the corrected anchor
 `^[0-9.]+ [A-Z] (srv|slot) ` finds 38 of 40, the two it leaves being the
 common-args block. Fixed in both jobs the same day, so those timings reach a
 job log again from the next run rather than surviving only inside the
 two-day artifact.

**The unmet prerequisite, exactly.** With the anchor fixed and the verbosity
understood: **two `route` runs carrying a prefill rate on each CPU model, at
least one of them in the fast mode.** Today that count is 1 on the EPYC 7763, 0
on the EPYC 9V74 and 0 on the Xeon 8573C, so it is five more observations at
minimum. No date goes with that number - which CPU a job draws is not ours to
choose, and no fast run has appeared in nine.

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
 job began printing `/proc/cpuinfo` model name, `nproc` and llama-server's
 `system_info` line on 2026-08-25, after all six of these runs. The nine runs
 that do name their CPU are read in
 [The CPU model does not sort the per-item cost of the visuals job](../archive/measurements-2026-08.md#the-cpu-model-does-not-sort-the-per-item-cost-of-the-visuals-job),
 and they rule the CPU model out rather than confirming it.

The lever this points at is the prompt, not the runtime: `visuals.lead_words`
(150) is most of each request's prefill, and prefill is most of the stage. It has
never been swept.

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
`min(ceil(items / run.shard_size), run.max_parallel)`, so at the 160-item
`run.safety_ceiling_per_run` then in force a worst worker drew `160 / 4 = 40`
items: 40 x 176 s = 117 minutes of model time, about 130 minutes with the fixed
costs, against the `work` job's 330. For comparison, the measured incumbent worst
worker was 58.8 minutes after PR #110.

**What the run actually cost, measured 2026-08-26.** Run `33016222069`: the
slowest job took **95.2 minutes** against the 330-minute bound it ran under, and
the slowest single item took **449 s**. The derivation said 115 minutes for the
worst shard, so it over-predicted by 21 percent - in the safe direction, and
close enough that the sharding margin was never tested.

**That is a qualification job, not a production worker.** The two run different
work against different bounds: 30 replay calls at 3 repeats on frozen payloads,
against up to 40 live items with fetch, extraction, routing and scoring around
them, under the `work` job's 150-minute bound. The configured model has never
run a production day, so its worst worker is still unmeasured
([Where the work job's bound comes from](../reference/measurements.md#where-the-work-jobs-bound-comes-from)).

### The vector backfill, and the one raise the archive plan cannot absorb

Toolchain: node 24.12.0, onnxruntime 1.29.0. Date:
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
([Sizing the archive index](../archive/measurements-2026-08.md#sizing-the-archive-index)). Quote those.

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

#### The instrument prints the runway now, and it prints a floor (2026-08-30)

Every figure above was worked out by hand on this page, three times, and got the
wrong answer twice. `idhazh site-weight` now prints it from the tree it just
measured. Toolchain: node v24.12.0. Date:
2026-08-30, `origin/main` at `76cdc72`, nine published days, 3,054 items.
Method: `npm run build` then `python -m idhazh site-weight --site-tree build`.
n=1; a byte count over a fixed tree has no spread to report.

```text
site-weight build: 141.1 MB in 311 files, 883 MB left to the 1024 MB Pages cap
site-weight by directory: assist 43.2 MB, _app 22.3 MB, 2026-08-24 15.6 MB,
 2026-08-25 15.5 MB, 2026-08-26 13.4 MB, 2026-08-29 7.4 MB
site-weight rate: 48457 B per published item over 3054 items,
 so 7.39 MB a published day at the 160 item ceiling
site-weight runway: 89 published days to the 800 MB alarm point, 119 to the 1024 MB Pages cap
```

Exactly: **147,986,756 bytes in 311 files**, 141.13 MiB of a 1,024 MiB cap -
13.8 percent used - and **119.4 published days** to the cap, **89.1** to the
alarm point.

**The printed rate is an average that charges the fixed directories to the
items, so the runway is a floor.** Nothing in the tree is only per-item: the
on-device encoder under `assist/` and the JavaScript under `_app/` cost the same
whether a day publishes 4 items or 160.

| Part of the tree | Bytes | Share | Moves with items? |
| --- | ---: | ---: | --- |
| `assist/` - the on-device encoder | 45,328,441 | 30.6 percent | no |
| `_app/` - the built JavaScript | 23,367,156 | 15.8 percent | no |
| `fonts/`, `icons/`, `404.html`, manifest, favicon | 109,159 | 0.1 percent | no |
| everything else - day routes, payloads, index, console | 79,182,000 | 53.5 percent | yes |

**46.5 percent of the site does not grow with a published day.** Divide only the
part that does and the rate is **25,927 bytes an item**, which is 3.96 MiB a day
at the 160-item ceiling and **223 published days** to the cap. That figure is
derived from the split above, not separately measured - but it lands within 6.4
percent of the 24,378 bytes an item measured independently on 2026-08-29 over
seven mature days, from a different tree state and a different method.

**So the honest reading of the printed line is "at least 119 days, and about
223".** The instrument prints the conservative one on purpose: a runway that
assumes the model directory is bought again every day is wrong in the direction
that costs nobody a site. `by_directory` is on the same output precisely so a
reader can do the sum above rather than take the floor as the answer.

**Where the bytes actually are.** `assist/` is the largest single directory in
the published site and it is a feature no digest assertion depends on
(CLAUDE.md section 0a). Deleting it would give back 30.6 percent of the site and
buy nothing on the rate, which is the same lesson PR #171 taught one level down:
a one-off saving buys a fraction of a day forever, and only the rate moves a
date.

### The day grain, and the two numbers that argued against it

**Measured 2026-09-07** on a developer machine, over this checkout. Every
figure above this heading was taken over the flat `state/published.csv`, which
`backend/utilities/split_published_ledger.py` moved into
`state/published/YYYY/MM/DD.csv` on 2026-09-08.

The ledger that day: **7,243 rows, 756 KB, 106.9 B a row**, 7,162 distinct
addresses over 15 published days - **483 rows a day**. `load_published` took
**37.0 ms at best and 69.0 ms at worst over five runs, a spread of 32.0 ms**,
which is most of the reading: the same code is nearly twice as slow when another
job shares the box, so a wall clock here measures the machine as much as the
file. It peaked at **500.9 B a row while reading, 3.63 MB**. At the measured rate
that is 18.8 MB on disk and 88 MB of peak after a year, 56.5 MB and 265 MB after
three.

**81 addresses carry more than one row, and every one of those gaps is zero
days.** No address in the committed ledger was published and then published
again on a later date. Read that as evidence the guard works rather than that it
is idle - the ledger cannot show a repeat the guard blocked.

**A synthetic year, 176,295 rows, three layouts.** The window column is a
120-day cover, the shape `collect.published_window_days` now expresses.

| Layout | Whole history | 120-day window | Opens in window | Bytes read in window |
| --- | --- | --- | --- | --- |
| One file | 2,654 ms | not possible | 1 | 17.1 MB |
| 12 month files | 1,741 ms | 293 ms | 4 | 5,715,970 |
| **365 day files** | 2,514 ms | 587 ms | 121 | 5,673,448 |

**Day files went the wrong way on speed, and it is recorded rather than
dropped.** For the same 120-day window they read 42 KB fewer than month files
and take **587 ms against 293 ms - twice as long**. The extra 294 ms is 117 more
file opens at about 2.5 ms each on Windows. Parse cost follows bytes; the rest
follows opens. The unbounded read is where the grain hurts most, 2,514 ms with a
1,684 to 18,592 ms spread, and that is the mode shipping today. Accepted,
because it is seconds inside a job that runs for hours.

**And repository size went the wrong way too.** 60 days, 5 runs a day, 300
commits:

| Layout | Working tree | `.git` before gc | after gc |
| --- | --- | --- | --- |
| One file | 2,757 KB | 3,772 KB | **275 KB** |
| Month files | 2,757 KB | 329 KB | **280 KB** |
| Day files | 2,759 KB | 338 KB | **296 KB** |

Git has no append: every commit writes a whole new object, which is why one file
is **eleven times worse before packing**. Packing recovers essentially all of it,
and day files finish **21 KB larger than one file and 16 KB larger than month
files - the largest of the three**. So **repository size is not a reason for day
files**, and it is written down here because the opposite is the intuitive
answer and the intuitive answer is wrong.

What did earn the grain is in
[../architecture/sources/freshness.md](../architecture/sources/freshness.md):
one partition rule shared with the digest tree, a day removal that is one `rm`
rather than an edit `merge=union` cannot express, and a merge surface of one day
rather than about 150 runs.

### The full days, run by run

Sixteen runs planned a full day - 100 items or more - between 2026-08-23 15:23
and 2026-08-26 20:09 UTC. Every one fanned out to four workers, so this is one
shard count and not a mixture. `Items a worker` is
`ceil(items_planned / 4)`, and `items_planned` is read from that day's committed
`run.json` rather than from a log. Five of the sixteen runs ended `cancelled` or
were dispatches, but all 64 `work` jobs concluded `success`, so every clock here
is a worker that finished its share.

| Run | Plan started (UTC) | Items planned | Items a worker | Slowest worker | Minutes an item |
| --- | --- | --- | --- | --- | --- |
| `33008629212` | 2026-08-26 20:09 | 160 | 40 | 83.5 min | 2.09 |
| `32986307407` | 2026-08-26 15:57 | 160 | 40 | **94.5 min** | **2.36** |
| `32960510065` | 2026-08-26 10:56 | 160 | 40 | 92.5 min | 2.31 |
| `32941554666` | 2026-08-26 07:15 | 194 | 49 | 88.7 min | 1.81 |
| `32926523936` | 2026-08-26 03:30 | 198 | 50 | 107.7 min | 2.15 |
| `32887038177` | 2026-08-25 19:33 | 200 | 50 | 103.8 min | 2.08 |
| `32863921985` | 2026-08-25 15:11 | 200 | 50 | 110.6 min | 2.21 |
| `32839359536` | 2026-08-25 10:55 | 200 | 50 | 102.4 min | 2.05 |
| `32820339599` | 2026-08-25 07:14 | 200 | 50 | 93.6 min | 1.87 |
| `32804437110` | 2026-08-25 03:17 | 200 | 50 | 106.9 min | 2.14 |
| `32766098026` | 2026-08-24 19:08 | 200 | 50 | 105.3 min | 2.11 |
| `32742672105` | 2026-08-24 15:08 | 200 | 50 | 113.1 min | 2.26 |
| `32719349248` | 2026-08-24 11:00 | 200 | 50 | **117.5 min** | 2.35 |
| `32701966659` | 2026-08-24 07:35 | 200 | 50 | 108.9 min | 2.18 |
| `32680268454` | 2026-08-24 01:38 | 200 | 50 | 98.3 min | 1.97 |
| `32648218952` | 2026-08-23 15:23 | 200 | 50 | 114.7 min | 2.29 |

| Quantity, over those 16 runs | Lowest | Median | Highest |
| --- | --- | --- | --- |
| Slowest worker of the run | 83.5 min | 104.5 min | **117.5 min** |
| Minutes that worker spent an item | 1.81 | 2.15 | **2.36** |

**The spread on the per-item rate is 1.30x, not the 3.4x the host lottery moves
prefill by.** A worker is prefill plus decode, and this page already records that
the hosts which read a prompt fastest write a summary slowest, so the two swings
partly cancel over 40 items. That is why a shard clock is a steadier thing to
size a bound against than a tokens-a-second figure.

## Three console routes, three ceilings, and a day priced on each (2026-08-31)

Toolchain: node v24.12.0. Date:
2026-08-31. Tree: `feat/the-console-becomes-three-routes` merged up to
`origin/main` at `fb67faf`, ten published days, 3,544 scored rows, 4,632
telemetry rows. Method: `npm run build` then
`gzipSync(readFileSync(page), { level: 9 }).length`, which is the byte the gate
itself takes.

**Five builds of the same tree, heaviest per route, never a mean:**

| Route | 1 | 2 | 3 | 4 | 5 | heaviest | spread |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/console/` | 115,825 | 115,825 | 115,827 | 115,829 | 115,820 | **115,829** | 9 |
| `/console/model/` | 13,503 | 13,501 | 13,501 | 13,508 | 13,498 | **13,508** | 10 |
| `/console/machine/` | 5,329 | 5,327 | 5,327 | 5,328 | 5,328 | **5,329** | 2 |

The spread is 9, 10 and 2 bytes on routes of 115,829, 13,508 and 5,329 - well
inside the 64-byte noise floor every other ceiling on this site carries.

**A published day was priced by removing a real one**, the same method the
2026-08-29 section used and for the same reason a clone scan cannot be used:
2026-08-25 was dropped from `state/scores.csv`, `state/item-health/`,
`state/feed-health/`, `frontend/public/telemetry/` and its own directory under
`frontend/public/digest/`, reached through `STATE_ROOT`, `TELEMETRY_ROOT` and
`DIGEST_ROOT`, and the tree rebuilt. That is 724 scored rows, 1,000 item-health
rows, 828 feed-health rows, 1,000 telemetry rows and 29 files of published day.
The day dropped is neither the newest nor the oldest, so the window anchor never
moves. Paired against build 1, which is the same source and the same command:

| Route | ten days | without 2026-08-25 | cost of that day |
| --- | ---: | ---: | ---: |
| `/console/` | 115,825 | 96,575 | **19,250** |
| `/console/model/` | 13,503 | 12,773 | **730** |
| `/console/machine/` | 5,329 | 5,332 | **0** (-3, inside the 9-byte spread) |

**`/console/machine/` costs zero, and that is the useful reading.** It renders no
ledger at all today, so a 20 percent cut to every ledger the console reads moved
it three bytes the wrong way, which is build noise - and that is also the control
saying the root redirection itself is not a variable.

**The Model route grows per published day, not per item.** It inlines one row a
day from `modelWork` and one from `throughputDays`, and no per-item array. At 730
bytes a day against `/console/`'s 19,250 it is 3.8 percent of the Pipelines cost,
and that ratio is the point of the split: the term that grows is almost all on
one route, and now only one ceiling has to carry it.

The ceilings follow the method already written down for `/console/` - heaviest of
five builds, plus seven mature published days, plus the 64-byte build noise
floor:

```text
/console/ 115,829 + 7 x 19,250 + 64 = 250,643
/console/model/ 13,508 + 7 x 730 + 64 = 18,682
/console/machine/ 5,329 + 3 x 502 + 64 = 6,899
```

**Machine's allowance is not days, because a day costs it nothing.** What varies
on that route is the band's three sentences, the strip's three worst states and
its own carry - 502 characters of ledger-derived text, read off the built page -
so the allowance is three publishes' worth of rewriting every one of them,
502 x 3 = 1,506. That is a bound on text length rather than a measured growth,
and gzip never charges a whole byte a character in a document this compressible,
so it is a strict over-estimate. It is labelled as one.

**Every one of the three gates is tighter than the single one it replaces.** The
regression a console ceiling exists to catch is a day payload inlined by a
layout, measured 2026-08-26 at 313,300 gzipped bytes. The slack here is 134,814,
5,174 and 1,570 bytes, so that regression is 2.32x, 60.6x and 199.6x the slack -
and `/console/` alone is 250,643 against the 259,908 it replaces, on a page that
lost its model panels to a route of its own. A single key over three surfaces
would fail without saying which surface failed, which is the decisive argument
for routes over tabs and the reason there are three keys.

**What each ceiling buys, in publishes.** Seven published days on `/console/` and
on `/console/model/`; three publishes' worth of complete text rewriting on
`/console/machine/`. All three are meant to expire. Rows 13 to 19 of the
observability plan add panels to every one of them, and each of those rows
re-derives the ceiling it crosses and records what the bytes bought - it never
cuts a panel to stay under a number (owner ruling, 2026-08-31). The Machine
ceiling expired the same day; see the next section.

**The lazy chart chunk did not move.** `DIuPWcXJ.js`, 585,481 raw and 197,561
gzipped bytes, byte for byte what it measured before the split, against the
200,000 escalate trigger. No new echarts type was registered and none was needed.
The one larger lazy chunk in the build is the assist encoder at 901,929 raw and
234,135 gzipped, which is a different artifact and carries no chart trigger.

## Moved here on 2026-09-10

Five finished readings from [../reference/measurements.md](../reference/measurements.md).
Each records a completed experiment, a level something later superseded, or a
guard whose value has since moved. Nothing in `config/`, a test or a live doc
reads any of them.

## Drift review and source extraction, 2026-09-08

**One length warning remains from issue 438; the other flagged domains lack
enough comparable evidence.** This is a correction to the comparison, not
proof that every source is healthy. Rules and limits live in
[evaluation.md](../concepts/evaluation.md#comparable-domain-samples).

**Method.** build
26200, CPython 3.14.2. Read the August and September score shards from commit
`2dd5f7bfb8acd7b17a03b2a8517762a4ce5bc0c4`, the input to
[run 34031948924](https://github.com/miztiik/yen-idhazh/actions/runs/34031948924).
No model ran and no score was recomputed. Two deterministic reassessments of
the completed-day windows produced identical results: zero replay spread.
This does not measure a false-positive rate or calibrate the sample floor.

The original review included September 6's partial day. It compared 3,078
baseline rows with 4,010 recent rows. The baseline mixed two models, five scorer
versions and seven pipeline identities. The recent side used one of each.
Eight of the ten flagged domains had four or fewer scored rows on at least
one side. All 141 unknown article lengths belong to August 22-27; those lost
pre-cap measurements remain unknown.

The corrected windows are August 30 through September 5 and August 2 through
August 29. Recorded baseline rows begin on August 22. The corrected recent
window has 3,888 rows. The review completes 35 domain/metric comparisons and
reports 300 comparisons as lacking sufficient evidence or identity.

Length samples for the domains named by
[issue 438](https://github.com/miztiik/yen-idhazh/issues/438): repeated articles
count once and unknown lengths do not count toward the length floor.

| Domain | Baseline articles with length | Recent articles with length | Length result |
| --- | --- | --- | --- |
| econbrowser.com | 1 | 15 | Insufficient evidence |
| france24.com | 43 | 64 | Median 391 -> 161 words; inspect extraction |
| microsoft.com | 7 | 1 | Insufficient evidence |
| newslaundry.com | 13 | 21 | Insufficient evidence |
| qz.com | 2 | 44 | Insufficient evidence |
| research.ibm.com | 18 | 1 | Insufficient evidence |
| scmp.com | 3 | 1 | Insufficient evidence |
| scroll.in | 2 | 68 | Insufficient evidence |
| semafor.com | 2 | 53 | Insufficient evidence |
| the-decoder.com | 2 | 21 | Insufficient evidence |

Keeping the original date membership while applying only the evidence rules
also leaves France24 as the sole warning, at 391 -> 154 words over 43 baseline
and 68 recent articles. Thus excluding the partial day does not explain the
other warnings disappearing. Microsoft's copying warning compared one 9B
summary with ten 8B summaries and is not a like-for-like model comparison.

### Saved source-page replay

The production fetcher sampled both feeds on September 8 at 07:10 UTC from this
developer machine. Both robots checks allowed access. These captures do not
establish what a GitHub runner would receive. Replaying each saved response
twice gave identical extracted text: zero replay spread. No source list or
publication threshold changed.

| Captured page | Original words | Cleaned words | Result |
| --- | --- | --- | --- |
| France24, Nepal hydropower report | 511 | 470 | Two player notices removed |
| France24, live-update page | 1,382 | 1,382 | Unchanged |
| France24, sports-video introduction | 81 | 40 | Two player notices removed; short article kept |
| Newslaundry, March 2019 article | 1,002 | 1,002 | Unchanged |

The reduced player fixture comes from
[the sports-video page](https://france24.com/en/tv-shows/sports/20260908-before-champions-league-kylian-mbapp%C3%A9-campaigns-for-ballon-d-or).
It retains the relevant DOM wrappers and a short text excerpt, with non-ASCII
characters encoded as HTML entities. Running the original extraction call on
that fixture includes both notices; the corrected call excludes both and keeps
the article. This is a bounded offline code regression, not a scan of published
content. The other France24 captures were
[the Nepal report](https://france24.com/en/asia-pacific/20260908-nepal-rescuers-race-to-free-dozens-trapped-in-hydropower-tunnels)
and [the live-update page](https://france24.com/en/europe/20260908-live-russia-resumes-strikes-on-kyiv-after-three-day-halt).

The Newslaundry feed returned only
[one article from 2019](https://newslaundry.com/2019/03/01/welcome-back-abhinandan-varthaman).
Its text extracted, but that does not make the feed fresh. This is a separate
source finding, not an extraction fix. A historical 465-word score row exists
for September 2, but the downloaded evidence shard inspected for this work did
not contain that article. No claim about that historical article's completeness
is made. The source needs a fresh-feed check before any replacement or retirement.

## How long we go quiet about a registry name, 2026-08-31

**We never go quiet. The longest silence about any of the 30 registry names, in
the whole committed record, is three days - and it happened twice in 163
chances.** A per-subject fade rate needs silence to act on, so on today's
registry it has nothing to act on.

Taken by `python backend/utilities/entity_gap.py` at commit `e0d6724`, over the
11 published days from 2026-08-21 to 2026-08-31 and the 3,596 items in
`frontend/public/digest/`. a developer machine,
Python 3.14.2, 2026-08-31. **No spread, because there is nothing to vary.** The
report is a pure function of the committed tree, so two runs at one commit print
the same bytes - checked by SHA-256 in `backend/tests/test_entity_gap.py`. Any
machine at `e0d6724` gets these figures; the hardware is here because Rule #10
asks, not because it moved anything.

### Two arms, because the record disagrees with itself

Both arms use one matcher - `tag.tags` against `Watchlist.entity_terms`, the
same function and the same terms the pipeline tags an item with. They differ
only in which words they read.

| Arm | Reads | Live on |
| --- | --- | --- |
| **As published** | the `entities` list each run wrote, over the article's title and whole body | 5 of 11 days, 2026-08-27 to 2026-08-31 |
| **Re-matched** | the same matcher over the title, the summary and the key points | 10 of 11 days, 2026-08-22 to 2026-08-31 |

The published field was declared on day one and read nowhere until 2026-08-26,
so it is empty on the first six days. **A zero there is an instrument that was
switched off, not a subject nobody mentioned**, which is why the second arm
exists. The second arm reads far less text, and the price of that is measured
rather than claimed: over the five days both are live, of 952 item-entity pairs
the run wrote, the summary carries 514 and drops **438 - 46.0 percent**. Four
more pairs go the other way, where the summary names a company the capped body
did not. **A dropped mention lengthens a gap, so the re-matched arm reports the
longer of the two readings, never the shorter.** Both arms still say the same
thing.

### Every gap, pooled

A gap of 1 day means we mentioned the name on consecutive days - no silence at
all. Days of silence is the gap minus one.

| Gap | Days of silence | As published | Re-matched |
| --- | --- | --- | --- |
| 1 day | 0 | 72 of 84 (85.7%) | 137 of 163 (84.0%) |
| 2 days | 1 | 12 of 84 (14.3%) | 23 of 163 (14.1%) |
| 3 days | 2 | 0 | 1 of 163 (0.6%) |
| 4 days | 3 | 0 | 2 of 163 (1.2%) |

**The pipeline's own field never recorded a silence longer than one day.**

### Every entry, by its own median gap

`n` mentions give `n - 1` gaps, so the denominators are not the same. On the
published arm, 28 of 30 entries were mentioned twice or more and have a gap at
all; `adani` and `asml` were mentioned once each and have none. On the
re-matched arm all 30 have a gap.

| Median gap | Days of silence | As published | Re-matched |
| --- | --- | --- | --- |
| 1.0 days | 0 | 20 of 30 | 18 of 30 |
| 1.5 days | 0 or 1 | 5 of 30 | 6 of 30 |
| 2.0 days | 1 | 3 of 30 | 3 of 30 |
| 2.5 days | 1 or 2 | 0 | 1 of 30 (`ecb`) |
| 3.0 days | 2 | 0 | 2 of 30 (`adani`, `ftc`) |
| no gap | - | 2 of 30 | 0 |

**24 of 30 entries sit at 1.5 days or less. Not one reaches four.** The three
slowest - `adani` at 2 mentions, `ftc` at 3, `ecb` at 3 - are also the three
with the fewest mentions, so their medians rest on one, two and two gaps. The
utility prints the full per-entry table; it is not repeated here because it
re-derives from any checkout at this commit.

### What bounds all of it

**891 of 3,596 items carry a registry name - 24.8 percent.** Three items in four
mention nothing the registry holds, and a subject in that 75.2 percent cannot
appear in any figure above. Per day the share runs 15.5 percent (2026-08-30) to
42.8 percent (2026-08-27), with one day at zero (2026-08-21, 4 items).

Two further limits, stated rather than implied:

- **The record is 11 days, so the longest gap it can express is 10.** A fade
 rate longer than that is unsupported by this record whatever a table says. A
 subject that goes quiet for a month cannot be observed here at all.
- **The complementary question cannot be answered, only bounded.** "Is there a
 subject with a long enough gap that the registry does not name?" needs an
 entity recogniser this repository does not have. What is measured is the size
 of the blind spot: 75.2 percent of items, and every one of them unlabelled.

### What this settles

A half-life is the number of days our silence about a subject may last before a
new story on it stops reading as the next instalment. Our silence about a
registry name lasts **zero days at the median and three days at the worst
observed**. A rate set anywhere in that range fires on every name every day,
which is the same as not having one; a rate set above it never fires. **The
registry has to hold a subject that goes quiet before a fade rate does anything
at all**, and today it holds 30 standing organisations - 25 companies and 5
institutions - and no subjects.

Re-run `python backend/utilities/entity_gap.py` after the registry gains its
first subject, and read the gap for that entry alone. Thirty companies cannot
answer the question, and averaging them with a subject would hide it.

## Whether an item's key points repeat its own summary, 2026-09-02

Toolchain: Python 3.14.2. Date: 2026-09-02.
Method: read every `frontend/public/digest/**/digest.json` and every
`state/scores/*.csv`, keep the items the eval ledger puts in the top two summary
bands, draw twenty of them, and read all ninety of their key points against
their own summaries.

**Spread is two different things here and they must not be reported as one.**
The population counts are committed bytes and a join, so they repeat exactly.
The ninety verdicts are one person's reading against a rule written down before
the sample was drawn; another reader would not land on the same ninety. The
mechanical word overlap at the end is the part that does repeat, and it is
reported as a cross-check rather than as the answer.

This measurement was taken before any feature code was written, and the answer
is what stopped the feature: key points on long items were dropped rather than
built
([../concepts/digest.md](../concepts/digest.md#the-key-points-stay-off-the-item-and-the-count-is-why)).

### The rule, written before the sample was drawn

- **Restates** - the point's main claim, meaning its subject plus what is said
 about it and any figure, name or date the claim turns on, is already in the
 summary in some wording. A different order, a shorter form and a longer form
 all still restate.
- **Adds** - the main claim is absent from the summary. A reader who read only
 the summary would not know it.
- **Borderline** - counted in neither column and reported separately. Three
 shapes qualify: the summary carries the point's subject but not the specific
 thing said about it; the claim is there only by implication; or the point
 makes no checkable claim at all.

Two clarifications, both fixed before counting. An attribution is not a claim,
so a point that names the outlet a figure came from, where the summary already
carries the figure, still restates. A fact is, so a point that repeats a summary
clause and carries one new fact beside it counts as an addition.

### The population and the sample

An item is eligible when its eval row's `source_word_count` - the article length
before the truncation cap, which is the count that picks the band - is 2,000
words or more, and it has at least one key point. That was `summarize.bands[3]`
and `bands[4]` in `config/idhazh.json` on the day of the draw, asking for 110 to
200 and 150 to 230 words. The ladder was reshaped on 2026-09-10 and those two
rungs are now one, so re-running this draw against today's config selects the
same articles but reads a different ask against them.

| Quantity | Value |
| --- | --- |
| items in the 12 committed days | 4,713 |
| eligible | **110** |
|... band 3, source 2,000 to 2,999 words | 66 |
|... band 4, source 3,000 words and over | 44 |
| eligible summary length | median 154 words, 34 to 223 |
| sampled | 20 items, 90 key points |

The sample is the eligible list sorted by `item_id` - a content hash, so that
order is arbitrary with respect to day, source and length - taking the twenty
evenly spaced positions `round(i * 109 / 19)`. No seed and no hand-picking, so a
re-run draws the same twenty.

### Seven points in eight restate: 78 of 89

| Verdict | Points | Share |
| --- | --- | --- |
| **Restates** | **78** | **87.6 percent of the 89 clear verdicts** |
| Adds | 11 | 12.4 percent of the 89 |
|... a claim the summary does not carry at all | 6 | 6.7 percent of all 90 points |
|... a summary claim carrying one new fact | 5 | - |
| Borderline | 1 | counted in neither column |

**Thirteen of the twenty items add nothing at all.** Every point on them is a
sentence the reader has already read one paragraph higher. Four of the twenty
carry a claim a summary-only reader would not have, and six points out of ninety
is the whole of what those four items are worth.

On all thirteen the points are a strict subset: the summary carries facts the
points drop, and never the other way round. One is worth naming. Its summary
reports a pilot emissions market that cut factory pollution by 20 to 30 percent,
and not one of its four key points mentions it - so a reader given only the
points would be worse informed than one given only the summary.

### The summary's own length does not predict it

This is the finding that kills the row's premise, which was that a long article
compressed hard leaves things the points have to carry.

| Group | Items | Median summary |
| --- | --- | --- |
| carries at least one addition | 7 | 154 words |
| carries none | 13 | 146 words |

Eight words apart on a sample of twenty. The longest summary drawn, at 210
words, produced one addition and it was a restated claim with one fact beside
it.

**The one item where the points did real work has the shortest summary in the
sample, not the longest.** It is a 3,195-word source in band 4, which asks for
150 to 230 words, and its summary is **49 words** - a third of the floor. Three
of its four points carry claims the summary never made. The points were doing
the summary's job because the summary did not do it, which is a summarizer
defect and not an argument for a second list under every item.

That defect is not rare. Across the 110 eligible items, **20 summaries, 18.2
percent, are shorter than their own band's floor**, and 13 of those 20 are band
4 items that came back under 150 words.

This is one hand count on one day, taken while the summariser prompt was being
tuned, and no eval column tracks it - so it cannot be re-read without repeating
the draw by hand. On 2026-09-10 the length policy ruled that a summary under its
band's floor publishes rather than failing
([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md#what-happens-when-a-reply-misses-the-ask)),
which changes what happens to these items and measures nothing new about them.

### The mechanical cross-check

Word overlap between a point and its summary, stop words removed, as a share of
the point's own words. It is not the verdict - every point was read - but it
separates the two columns cleanly enough to say the reading was not arbitrary:

| Ruled | Mean | Median | Min | Max |
| --- | --- | --- | --- | --- |
| Restates | 0.77 | 0.79 | 0.29 | 1.00 |
| Adds | 0.36 | 0.36 | 0.08 | 0.69 |

Thirteen of the ninety points score 1.00, meaning every word of the point that
is not a stop word is already in the summary. Every one of the thirteen was
ruled a restatement.

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

## All three console ceilings, re-derived on the backfill's tree (2026-09-06)

Toolchain: node 24.12.0. Date:
2026-09-06. Method: `frontend/scripts/bundle-gate.mjs`, which is `gzip -9` over
each prerendered `index.html` in `frontend/build`, heaviest page per route class.
One tree at `76c2d27c`, sixteen published days, eight builds. Another agent ran
the backend suite in a sibling worktree for part of the run, which moved one
build from 47 s to 255 s and moved no byte: gzip over the same input is the same
output whatever else the box is doing.

**Two of the three had spent their runway and the third had not.** Nothing had
fired. The pages read 222,819, 44,956 and 35,822 against committed ceilings of
277,195, 56,385 and 39,743, so every route was under. But a ceiling here is the
page plus seven published days of growth, and at the rates measured below the
slack on `/console/` was **3.39 publishes** and on `/console/machine/` **3.12**.
`/console/model/` was at **6.99**, because it was derived one commit earlier by
this same method on this same tree, so it is left alone.

**Five builds of one tree, heaviest per route, never a mean.** A mean fires on
half of all builds:

| Route | 1 | 2 | 3 | 4 | 5 | heaviest | spread |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/console/` | 222,812 | 222,819 | 222,817 | 222,818 | 222,816 | **222,819** | 7 |
| `/console/model/` | 44,945 | 44,956 | 44,953 | 44,951 | 44,950 | **44,956** | 11 |
| `/console/machine/` | 35,821 | 35,819 | 35,819 | 35,822 | 35,816 | **35,822** | 6 |

**The control arm says the copied payload roots build the same site.** Both
removal arms read their ledgers through `STATE_ROOT`, `TELEMETRY_ROOT` and
`DIGEST_ROOT` off a copy in the temp directory, so a copy that built a different
site would price a day against nothing. A sixth build off that copy with **no day
removed** read 222,810, 44,945 and 35,813 - 2, 0 and 3 bytes below the bottom of
the five-build range, so the honest spread is 9, 11 and 9 bytes on pages of 222.8,
45.0 and 35.8 KB. All three are inside the 64-byte build noise floor. The three
capped routes no arm can reach moved the same way: `/404` spanned 1,593 to 1,598
and `/evals/` 3,103 to 3,107 across the five, with the control inside both.

**Two removal arms, and each one prices all three routes.** A published day is
priced by removing a real one, never by cloning one: a clone reads about 18
percent cheap because gzip sees a near-copy of a block it already holds. Both
arms drop a mature day - neither the newest nor the oldest, so the 30-day window
anchor never moves - from the published ledger, `state/scores/`,
`state/item-health/`, `state/feed-health/`, `state/runtime-counters.csv`,
`frontend/public/telemetry/` and the day's own directory under
`frontend/public/digest/`. `frontend/public/assist/` and `source-health.json` are
copied beside `digest/` in each arm, because `INDEX_ROOT` and
`SOURCE_HEALTH_PATH` are derived from `DIGEST_ROOT` and have no switch of their
own. Both are paired against the control, the same source and the same command.

| Arm | What it removed | `/console/` | `/console/model/` | `/console/machine/` |
| --- | --- | ---: | ---: | ---: |
| sixteen days (control) | - | 222,810 | 44,945 | 35,813 |
| A: without 2026-08-31 | 601 published, 601 scored, 639 item-health, 710 feed-health, 639 telemetry rows, **20 counter rows over 5 runs** | 208,413 | 43,320 | 34,653 |
| **cost of that day** | | 14,397 | 1,625 | 1,160, so 232 a run |
| B: without 2026-09-01 | 627 published, 627 scored, 676 item-health, 710 feed-health, 676 telemetry rows, **20 counter rows over 5 runs** | 206,786 | 43,311 | 34,554 |
| **cost of that day** | | **16,024** | **1,634** | **1,259, so 252 a run** |

**Both arms carry counters, which the last pair could not manage, so the run rate
and the day rate come off the same tree.** On 2026-08-31 the heavy day predated
the counters entirely and a second, lighter day had to be dropped to get a
per-run figure at all. Every mature day now runs three to five times, so both
arms price all three routes and the larger of the two readings is taken on each -
arm B on all three. Arm A's day is the one row #4 priced on 2026-09-06, and it
returns 1,625 bytes against the 1,624 recorded there, which is the method
reproducing itself to one byte.

The ceilings follow the method that owns them - heaviest build, plus seven
publishes, plus the 64-byte build noise floor - with Machine priced per run at
the observed maximum of five runs a day:

```text
 222,819 + 7 x 16,024 + 64 = 335,051 /console/
 44,956 + 7 x 1,634 + 64 = 56,458 /console/model/, NOT taken
 35,822 + 7 x 5 x 252 + 64 = 44,706 /console/machine/
```

**`/console/model/` is left at 56,385 and that is a result, not an omission.**
The re-derivation lands 73 bytes above the committed number, which is 0.13
percent of a 56 KB ceiling and one byte a day of rate. The committed ceiling
already carries 11,429 bytes of slack, which is **6.99 publishes** at the
conservative rate - the seven this method asks for. Row #4 derived it one commit
ago, on this tree, by this method. Moving it 73 bytes would buy 0.04 of a publish
and would be a number raised for symmetry with its two siblings.

**The raise decomposes exactly into a page term and a rate term, on both routes
that moved.** The totals are +57,856 and +4,963 bytes, and the two halves sum to
each:

| Route | page since its ceiling was set | a day, or a run, since then | seven publishes of that | total |
| --- | ---: | ---: | ---: | ---: |
| `/console/` | 163,472 -> 222,819, **+59,347** | 16,237 -> 16,024 a day, **-213** | -1,491 | **+57,856** |
| `/console/machine/` | 29,599 -> 35,822, **+6,223** | 288 -> 252 a run, **-36** | -1,260 | **+4,963** |

**Both rates FELL and both raises are entirely page.** `/console/`'s day rate is
213 bytes cheaper than the 16,237 the 2026-09-03 derivation used, and that is
partly a change of method rather than a change of page: 16,237 was 9.38 bytes a
ledger row extrapolated to the heaviest day on record, where 16,024 is a heavy
mature day removed and measured. A measured day replaces an extrapolated one
(Rule #10). `/console/machine/`'s run rate fell 36 bytes because the counter
strip now reads one row per run where it read several.

**Seven publishes, when the recorded rule would allow nine.** The horizon rule in
[the gate this fires from](../how-to/run-the-gates.md#the-console-ceiling-is-a-tripwire-and-what-to-do-when-it-fires)
is the largest whole number of measured publishes that keeps the 313,300-byte
regression above 2x the slack. At today's rate that is nine on `/console/`:

| Publishes | slack | regression / slack | slack as a share of the page |
| ---: | ---: | ---: | ---: |
| 7 | 112,232 | 2.79x | 50 percent |
| 8 | 128,256 | 2.44x | 58 percent |
| 9 | 144,280 | 2.17x | 65 percent |
| 10 | 160,304 | 1.95x | 72 percent |

Seven is taken instead. Nine publishes is 144,216 bytes on a 222,819-byte page,
so the gate would stay silent while the page grew by two thirds - and the
regression it exists to catch is one day payload, which is 313,300. A tripwire
that lets a page absorb nearly half of one before it speaks is not a tripwire.
Seven also keeps one horizon over all three routes, so "the runway expired" stays
a single statement about the console rather than three.

**What the three slacks are worth against that regression.** 112,232 on
`/console/`, 11,429 on `/console/model/` and 8,884 on `/console/machine/`, so the
313,300 is 2.79x, 27.4x and 35.3x each. The tightest is `/console/`, at 2.79x
against 2.32x when it was last derived.

**The 16,024 is not a rate for ever, and the fourteenth publish from here is
where it stops.** `console.default_window_days` is 30 and sixteen days are
committed, so a new day is still added to the seed rather than pushed through it.
Once the ledger passes the window a new day drops the oldest out of the document
and the marginal cost falls toward zero. Two more re-derivations at this rate and
the third one should read a much smaller number - a ceiling raised at the
un-windowed rate expires sooner rather than later, which is the safe direction
and is what a ratchet is for.

**The contract test's bound moved with them.**
`test_contracts.py::test_the_committed_config_carries_the_capped_routes` holds
every console ceiling under a constant that stands in for the page it cannot see:
the heaviest console document plus the 313,300. That was 433,000 while the
document was 119,700; the document is 222,819 now, so the constant is 536,000. At
433,000 the next ordinary re-derivation of `/console/` would have crossed it -
the page after seven publishes is about 335,000 and its ceiling about 447,000 -
which is a contract test with a countdown in it. It is re-derived in the commit
that re-derives the ceilings, for the same reason and on the same cadence.

