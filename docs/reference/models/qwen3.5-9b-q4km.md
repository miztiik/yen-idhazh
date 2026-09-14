# Qwen3.5-9B-Q4_K_M

**Last Updated**: 2026-09-14

**Status: incumbent.** It has summarized every published item since 2026-08-27.
`incumbent` is one of three words a dossier's status line may hold - `evaluated`,
`incumbent`, `superseded` - and this line is the only place this model's
lifecycle is written ([models.md](../models.md)).

One model, one page. Every figure below is a reading of **these weights**, it is
the only reading of that quantity in force, and it carries the hardware that took
it, the date and the spread. Nothing here was re-derived and nothing was rounded:
each figure is the one the instrument log recorded, moved rather than restated.

**A reading taken against other weights is not on this page at all.** A token
count, a prefill rate and a decode rate all belong to a tokenizer and an
architecture, so a swap retires every one of them at a stroke. The retired
Qwen3-8B-Q4_K_M's figures stay where they were taken, in the instrument log,
labelled as the retired incumbent's
([measurements.md](../measurements.md)).

## Identity

`config/models/qwen3.5-9b-q4km.json` is where these fields are declared, and
`config/idhazh.json` names that file in one line, `models_file`. The
digest identifies the bytes the runtime opened; the repository revision
identifies the snapshot they came from and is pinned rather than a branch, so the
file, the alias, the revision and the expected digest move together or not at
all.

| Field | Value |
| --- | --- |
| Configuration id | `qwen3-5-9b-q4-k-m` |
| Repository | `unsloth/Qwen3.5-9B-GGUF` |
| Repository revision | `3885219b6810b007914f3a7950a8d1b469d598a5` |
| Base repository | `Qwen/Qwen3.5-9B` |
| File | `Qwen3.5-9B-Q4_K_M.gguf` |
| Quantisation | `Q4_K_M` |
| SHA-256, and the Hugging Face LFS oid | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
| Bytes | 5,680,522,464 (5.29 GiB) |
| Licence | `Apache-2.0` |
| Architecture | `qwen35` - a hybrid Gated DeltaNet plus attention design, as llama.cpp names it |

**The digest was observed, not copied.** The qualification run read it off the
file the runtime opened rather than reading it back out of config, which is what
makes it evidence about the bytes rather than a restatement of the setting. The
repository revision is mutable metadata about a repository snapshot; the digest
identifies the actual weights.

**Two of these fields have no config key.** `Licence` is an SPDX identifier with
one human reader and no validator, because a check over a licence string asserts
a legal judgement a schema cannot make (Andre, 2026-09-13). `Architecture` is
what llama.cpp reported when it loaded the file; the model file has no
`arch` key today, so the value here comes from the loader's own report.

## On disk, and what it costs the cache

One copy of these weights is the `Bytes` row above.

| Quantity | Reading |
| --- | --- |
| The total the Actions cache holds | 10 GB, which is GitHub's limit and not ours (CLAUDE.md Guardrail #2) |
| First download, cache miss | 5.29 GiB in **118 s**, `n = 1`, spread unavailable, on GitHub-hosted `ubuntu-latest`, 2026-08-23 |

The download figure is one observation and may not be read as a rate, so it may
not be compared with any other model's separate download observation.

What the cache actually held on the day this model replaced the last one, entry
by entry, is a dated record of that transition rather than a property of these
weights: [The cache transition](../measurements.md#the-cache-transition-measured-2026-08-27).

## What the tokenizer costs

Three counts of **our own text** in this model's vocabulary. Each sizes a budget
the pipeline spends before it reads a single article word, so each one moves when
the weights move.

**Taken 2026-09-14** against these weights, by
`python backend/utilities/measure_budgets.py read`, which asks the running
`llama-server` to tokenize the exact text the pipeline sends.

| Quantity | Reading | Taken over | What it measures |
| --- | --- | --- | --- |
| `DEFINITION_SENTENCE_TOKENS` | 658 tokens | 20 definition sentences, 2,929 characters | Every taxonomy definition sentence together - the fixed part of a labelling prompt |
| `EMPTY_ROLE_TOKENS` | 30 tokens | 9 encoding roles | The nine empty encoding roles on a visual plan that declines |
| `TOKENS_A_WORD_AT_THE_CUT` | 1.3628 tokens a word | 200 articles, 153,613 words | Spends a token cap as a word count at the cut |

**Spread is 0 on all three, and is printed rather than left out.** A tokenizer
over fixed text returns the identical count every time, so there is nothing to
repeat - but a reading with no spread field would read as one that forgot to take
it (Guardrail #10).

### Each reading is a point in time, and the weights are only half of why

**These three are the only figures on this page that may be compared with the
retired model's.** A tokenizer count is exact and deterministic, so the same text
on two vocabularies is a real comparison - unlike the throughput rows below,
where the job, the CPU and the llama.cpp build all moved and no delta was ever
measured.

On that comparison, **this vocabulary spends 18 percent fewer tokens on our
taxonomy than the retired Qwen3-8B did**: 805 tokens on 2026-09-11, 658 on
2026-09-14, over a definition block that did not change by one byte between those
dates - 20 entries, 2,929 characters both times. That is 3.64 characters a token
then and 4.45 now.

**The check that establishes it is the `Taken over` column, and that is what the
column is for.** The count is of our text in this vocabulary, so it moves when
our text moves, with no model change at all. A total quoted without its probe
size cannot tell a cheaper tokenizer from a shorter taxonomy, and the two call
for opposite responses. So a retake is dated on this page, the size sits beside
the value, and neither is quoted alone.

The values themselves live in [`backend/idhazh/measured.py`](../../../backend/idhazh/measured.py)
with the probe text each was taken over and the two counts each was derived from.
`measure_budgets.py check` exits non-zero when any of the three names weights this
repository no longer runs, and `measure_budgets.py read` prints this section ready
to replace.

## Prefill and decode

**Measured 2026-08-23** on a GitHub-hosted `ubuntu-latest`, AMD EPYC 9V74
80-Core, 4 threads, llama.cpp `b10598` (`56db501e7`), 3 repeats, with
`llama-bench -m <model> -p 730,1800,4850 -n 250 -t 4`. The three prompt lengths
are what a short, a medium and a long article produce.

| Quantity | Reading, tokens a second |
| --- | --- |
| Prefill, 730-token prompt | 10.14 +/- 0.01 |
| Prefill, 1,800-token prompt | 10.06 +/- 0.01 |
| Prefill, 4,850-token prompt | 9.84 +/- 0.01 |
| Decode, 250 tokens | **6.01 +/- 0.11** |

**Prefill fell 3.0 percent from 730 to 4,850 tokens** inside that one run, so the
rate barely moves with prompt length - a long article costs about as much a token
to read as a short one. Reading is faster than writing on these weights at every
measured length.

**The live digest path corroborates the 4,850-token row** over 4,117 real items
across nine days, which is the strongest corroboration on this page
([How often the truncation cap actually bites](../measurements.md#how-often-the-truncation-cap-actually-bites-2026-09-09)).

**This is not a comparison with the retired model.** The retired incumbent's rows
were taken in a different job, on a different CPU model and on llama.cpp
`b10580`. They establish that model's throughput and this one's; they do not
establish a delta between them, and **no such delta was ever measured**
([Still unmeasured](../measurements.md#still-unmeasured)).

## Memory

**Peak resident set, measured 2026-09-08** from this repository's four committed
captures of run `2026-08-29-3` -
`tests/fixtures/runtime/2026-08-29-3-shard-*.rss-samples.tsv`, 291 to 383 samples
a shard, taken every 15 seconds on a GitHub-hosted `ubuntu-latest`, 4 vCPU,
16 GB, on 2026-08-29.

| Shard | llama-server alone | llama-server and the shard's python, at one instant |
| --- | --- | --- |
| 3 | 13.16 GiB | **14.31 GiB (96.0%)** |
| 2 | 12.94 GiB | 14.15 GiB (95.0%) |
| 0 | 12.57 GiB | 13.93 GiB (93.5%) |
| 1 | 12.65 GiB | 13.86 GiB (93.0%) |

Spread across the four shards is 0.45 GiB on the first column, and the worst
shard holds the worst figure in both columns, so the two do not cancel. Read the
second column: llama-server's mark alone is not what the job held, and by how
much is on the instrument log with the argument that needs it.

**A resident set says how large the mark got, not how near the edge the job
came.** Most of it is mapped weight pages the kernel can drop under pressure, so
subtracting it from the machine's total does not yield headroom. That subtraction
was published once and is retracted; the retraction, and what would settle the
question, are on the instrument log
([Summed RSS reaches 14.31 GiB](../measurements.md#summed-rss-reaches-1431-gib-and-that-does-not-say-how-near-the-edge-the-job-came)).

**The committed ledger's own peak column is not a reading of this model.**
`state/runtime-counters.csv` carries no column naming the weights and its rows
span both this model and the retired one, so its range is a reading of the job
([The ledger's own worst row](../measurements.md#the-ledgers-own-worst-row-moved-to-1382-gib)).

### Model load time

| Quantity | Reading |
| --- | --- |
| Model load, four shards of run `2026-08-29-3` | **3,789.5 / 3,820.3 / 4,158.0 / 3,797.6 ms** |

So these weights open in about four seconds. Read from the `runtime-log-*`
artifacts of run `33274853468`, on GitHub-hosted `ubuntu-latest`, before the
ledger had a cell to hold it.

**The instrument log does not carry this reading.** It is the one quantity on
this page whose only record is archived
([../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md)),
and it is repeated here because a dossier a reader has to leave to learn how long
its model takes to open is not doing its job. A current reading comes from
`model_load_ms` in `state/runtime-counters.csv`, which every `work` shard has
filed since 2026-08-30 - reading it needs no new instrument, only a query.

## Seconds an item

**Measured 2026-09-09** over the 4,117 `publish` rows of
`state/item-health/2026-09.csv`, one month shard covering 2026-09-01 to
2026-09-09, written by stock GitHub-hosted `ubuntu-latest` runners, 4 vCPU, no
GPU. These weights served every one of those rows.

| Quantity | Reading |
| --- | --- |
| A summarize call, median | **114.6 s** |
| A summarize call, 95th percentile | **312.7 s** |
| A summarize call, longest | **800.9 s** |

Read as a day: the median item takes just under two minutes of a worker, and the
worst item on record takes over thirteen.

**Five older derived figures for this model are withdrawn** - 99, 258, 433, 222
and 639 seconds. They came from the bench tool's former hardcoded 200-token
prompt and did not apply the production truncation cap, so they describe a
workload the pipeline never ran. The prompt-token readings taken against these
weights are pinned, with their provenance, in
[`../../../backend/idhazh/measured.py`](../../../backend/idhazh/measured.py).

## The qualification verdict

**Run `33016222069`, 2026-08-26**, on `ubuntu-latest`. A frozen, pre-registered
corpus of 30 captured Article payloads, replayed at 3 deterministic repeats - 90
attempts. One model.

**Nine of the eleven registered gates passed. Two failed. The model was adopted
anyway, knowingly, by owner decision** ([../../../CLAUDE.md](../../../CLAUDE.md)
section 0) on 2026-08-27.

| Gate | Reading | Bar | Verdict |
| --- | --- | --- | --- |
| `reasoning_leakage` | none found | none | pass |
| Schema validity | 90 of 90 | 90 of 90 | pass |
| Determinism | 0 violations | 0 | pass |
| `publishable_length` | 0 of 90 outside the band | 0 outside | pass |
| `context_fit` | widest 3,775-token prompt plus 900 output, 0 overflowed | 0 overflowed | pass |
| Identity | digest observed off the opened file | the declared digest | pass |
| Budget | slowest job 95.2 min, slowest item 449 s | a 330-minute bound | pass |
| Scored denominator | 30 of 30, drawn from 160 addresses | 30 | pass |
| Faithfulness | mean hhem **0.7149**, spread 0.0173 to 0.9762, `hhem_delta_mean` 0.0000 | the registered floor | pass |
| `injection_canaries` | **4 of 5** | 5 of 5 | **FAIL** |
| `brief_copying_ceiling` | longest verbatim run **1.000** over 8 brief items | <= 0.5 (`evaluation.brief_compression_ceiling`) | **FAIL** |

Band counts across `min_source_words` 0 / 60 / 700 / 2000: **6 / 11 / 10 / 3**.
The top band is populated because the band comes from the source body rather than
the post-truncation count.

**No comparison arm was run.** Nothing above was measured against the retired
incumbent Qwen3-8B-Q4_K_M: no paired corpus, no side-by-side scores, no human
review. The faithfulness mean in that table is one model on one corpus and is not
a delta, and nothing on this page may be cited as if it were (Guardrail #10).
What would settle it is written down
([Still unmeasured](../measurements.md#still-unmeasured)).

**The `injection_canaries` failure is not a security finding about this model.**
The fifth canary was never exercised: the sanitizer stripped every marker before
the prompt was built, and the gate failed on the model returning no summary. The
correction, and why it is a lesson about the instrument rather than about the
weights, is on the instrument log
([The fifth canary was never exercised](../measurements.md#the-fifth-canary-was-never-exercised)).

## The records behind this page

Three benchmark records were taken against these weights. Each is one question
with one answer, and a re-run replaces its page rather than adding a second one.

| Record | What it settles |
| --- | --- |
| [Moving the instructions in front of the article](../benchmarks/instructions-in-front.md) | what a prefix cache can reach once call 2's question sits ahead of the article |
| [Where call 2's re-read tokens go](../benchmarks/two-call-re-read.md) | how much of call 2's prompt the server answers from cache |
| [What the two calls cost at the truncation cap](../benchmarks/two-call-window-sizing.md) | what both calls cost at a cap-length article, and the memory reading at three windows |

## See also

- [../models.md](../models.md) - the index, one row a model.
- [../measurements.md](../measurements.md) - the instrument log: everything measured that is not a property of one model.
- [../../../config/models/qwen3.5-9b-q4km.json](../../../config/models/qwen3.5-9b-q4km.json) - where the identity above is declared. `config/idhazh.json` names this file in one line, `models_file`, and that line is the whole of a swap.
- [../../../backend/idhazh/measured.py](../../../backend/idhazh/measured.py) - the readings a gate or a test reads, including which are pinned to these weights.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - the procedure that produced the verdict above.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what the gates mean and why a model may not grade a published summary.
- [../../architecture/summarize/model-boundary.md](../../architecture/summarize/model-boundary.md) - what a swap costs and what it invalidates.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the runner is the architecture) and Guardrail #10 (measured, not estimated).
