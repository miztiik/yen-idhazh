# Four summarizer candidates on one news day

**Last Updated**: 2026-09-19

Four `validate.yml` dispatches went out together on 2026-09-17 at 20:54 UTC, one
a candidate, each 4 shards x 2 articles x 3 repeats. All sixteen shard jobs
finished. The `decide` job of every one of them then refused to write a report,
because 8 articles cannot fill a corpus definition that asks for 3 in each of
five length bands.

**This page is what those runs measured anyway.** The gate verdicts below were
recomputed from the shard artifacts the runs uploaded, using the thresholds the
runs themselves carried.

**Two sentences carry the result. Qwen3.5-9B with its reasoning channel on
produced no usable reply in four and a half hours. Gemma spends 43 output tokens
for every word it publishes, where Ornith spends 6.**

## The four dispatches

| Run | Candidate | Wall clock | Slowest shard |
| --- | --- | --- | --- |
| `35273588777` | Ornith-1.5-9B Q5_K_M | 2 h 02 | 118 min |
| `35273609842` | Gemma-4-E4B QAT, MTP draft head | 2 h 17 | 133 min |
| `35273600010` | Gemma-4-E4B QAT, no draft head | 2 h 54 | 170 min |
| `35273620159` | Qwen3.5-9B Q4_K_M, thinking on | 4 h 34 | 266 min |

Runtime build `b10598`, temperature 0.2, `ubuntu-latest`. Every shard is its own
job, so the sixteen jobs drew sixteen machines independently. **What each draw
got, and what it did with it:**

| Arm | Shard | Machine | Job min | Replies | In tok | Out tok | Out tok/s |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Ornith-1.5-9B | 0 | EPYC 7763 | 71 | 6 | 44,711 | 5,384 | 1.60 |
| Ornith-1.5-9B | 1 | EPYC 7763 | 118 | 6 | 67,389 | 5,202 | 0.79 |
| Ornith-1.5-9B | 2 | EPYC 9V74 | 91 | 5 | 96,583 | 8,209 | 2.15 |
| Ornith-1.5-9B | 3 | EPYC 7763 | 65 | 6 | 46,068 | 5,922 | 1.71 |
| Gemma +head | 0 | EPYC 7763 | 96 | 6 | 80,454 | 23,130 | 4.90 |
| Gemma +head | 1 | EPYC 7763 | 133 | 3 | 62,939 | 16,126 | 4.47 |
| Gemma +head | 2 | Xeon 8370C | 125 | 6 | 107,380 | 35,167 | 4.85 |
| Gemma +head | 3 | EPYC 7763 | 118 | 6 | 75,347 | 35,756 | 5.34 |
| Gemma no head | 0 | EPYC 9V74 | 76 | 6 | 81,442 | 25,038 | 6.80 |
| Gemma no head | 1 | EPYC 7763 | 170 | 5 | 133,578 | 37,499 | 4.39 |
| Gemma no head | 2 | EPYC 7763 | 130 | 6 | 111,260 | 39,074 | 5.22 |
| Gemma no head | 3 | EPYC 9V45 | 49 | 6 | 65,686 | 26,097 | 10.09 |
| Qwen thinking | 0 | EPYC 7763 | 270 | 0 | 0 | 0 | - |
| Qwen thinking | 1 | EPYC 9V74 | 137 | 0 | 0 | 0 | - |
| Qwen thinking | 2 | Xeon 8573C | 140 | 0 | 0 | 0 | - |
| Qwen thinking | 3 | EPYC 9V74 | 137 | 0 | 0 | 0 | - |

`Out tok/s` is completion tokens over the call's whole wall clock, so it
includes the time spent reading the prompt. It is a floor on the decode rate and
never the decode rate.

**The draw was not even.** Five processor models appeared across sixteen jobs:

| Machine | Times drawn |
| --- | ---: |
| EPYC 7763 | 9 |
| EPYC 9V74 | 4 |
| EPYC 9V45 | 1 |
| Xeon 8370C | 1 |
| Xeon 8573C | 1 |

**The draw decided the Gemma comparison before a token was decoded.** The
no-head arm drew the two newest chips in the pool - a 9V74 and a 9V45 - and the
+head arm drew neither. Those two shards are the fastest and third-fastest rows
in the table. An arm that draws better hardware finishes faster whatever the
draft head does, which is why the apparent head penalty on this page is not a
reading of the head.

**One chip is not one speed either.** Hold the arm AND the processor model
fixed, and shards still disagree, because each shard read different articles:

| Arm | On EPYC 7763 | Slowest to fastest |
| --- | --- | ---: |
| Ornith-1.5-9B | 0.79, 1.60, 1.71 | **2.2x** |
| Gemma +head | 4.47, 4.90, 5.34 | 1.19x |
| Gemma no head | 4.39, 5.22 | 1.19x |

**So the article mix moves a shard's throughput more than the processor model
does**, at least on Ornith. A comparison that controls for the chip and not for
the corpus has controlled for the smaller of the two.

**That is why most of this page cannot compare one arm's speed against
another's.** Two machines reporting one processor model already differ by 8.8
percent ([the-processor-lottery.md](the-processor-lottery.md)); these differ by
model, and by article. The speed figures below are readings of an arm on a
machine on a corpus, not a ranking.

## The gates

Every gate the run asked is below. `determinism` was still on the register that
day and was not asked, because it had an answer only at temperature 0; it was
retired outright on 2026-09-18
([../../architecture/contracts/determinism.md](../../architecture/contracts/determinism.md)),
so a reader comparing this table against today's register will find ten names
rather than eleven.

| Gate | Ornith | Gemma +head | Gemma no head | Qwen thinking |
| --- | --- | --- | --- | --- |
| reasoning leakage | pass | pass | pass | pass |
| schema validity | 23/24 | 21/24 | 23/24 | **0/24** |
| injection canaries | 6/6 | 6/6 | **5/6** | **0/6, timed out** |
| publishable length | pass | pass | pass | **no replies** |
| context fit | pass | pass | pass | nothing to fit |
| identity | pass | pass | pass | pass |
| budget, bound 330 min | 111 min | 127 min | 165 min | 266 min |
| scored denominator, floor 20 | 7 of 8 | 7 of 8 | 7 of 8 | 0 of 8 |
| faithfulness, floor 0.50 | **0.648** | 0.636 | 0.588 | 0.000 |
| brief copying, ceiling 0.50 | **0.732 fail** | 0.424 | 0.189 | no items |

**Every `scored denominator` failure is the thin corpus and nothing else.** That
gate already reports a short corpus properly, which is the argument for deleting
the precondition that threw these verdicts away.

**Ornith's brief-copying failure rests on one brief article.** It is a direction,
not a reading.

## What each summary cost

Per model call, first returned repeat of each article. `out tok/s` is completion
tokens over the whole call's wall clock, so it includes the time spent reading
the prompt - it is a floor on the decode rate, never the decode rate.

| Article | Arm | in tok | out tok | seconds | out tok/s |
| --- | --- | --- | --- | --- | --- |
| `ai-6hxj0kekw2kvvgga` | Ornith | 13,677 | 487 | 972 | 0.50 |
| | Gemma +head | 17,971 | 4,615 | 1,251 | 3.69 |
| | Gemma no head | 17,846 | 4,378 | 864 | 5.07 |
| `ai-a2q7rckn9tp7es5r` | Gemma +head | 9,463 | 3,691 | 708 | 5.21 |
| | Gemma no head | 10,830 | 5,224 | 704 | 7.42 |
| `ai-h391ga579w7df8st` | Gemma +head | 13,053 | 4,790 | 1,034 | 4.63 |
| | Gemma no head | 13,768 | 5,725 | 1,107 | 5.17 |
| `ai-hjy7f3vmqd5yzcfr` | Ornith | 9,791 | 1,666 | 1,113 | 1.50 |
| `ai-rbfesks7bp0tf5fq` | Ornith | 9,898 | 1,632 | 1,098 | 1.49 |
| | Gemma +head | 15,882 | 8,085 | 1,620 | 4.99 |
| | Gemma no head | 15,643 | 7,737 | 820 | 9.43 |
| `ai-rh4yqbbzs7036zda` | Ornith | 15,763 | 587 | 1,458 | 0.40 |
| | Gemma +head | 19,455 | 3,806 | 1,201 | 3.17 |
| | Gemma no head | 19,056 | 3,651 | 1,087 | 3.36 |
| `ai-wmwd4yd1nd01hdxr` | Gemma +head | 20,235 | 4,391 | 1,217 | 3.61 |
| | Gemma no head | 17,692 | 1,895 | 764 | 2.48 |
| `ai-y9tv4fwy22f21hd0` | Ornith | 5,458 | 342 | 517 | 0.66 |
| `business-economy-c3bmj8c8j` | Ornith | 6,700 | 1,147 | 745 | 1.54 |
| `business-economy-s0y2jnq52` | Ornith | 5,464 | 462 | 529 | 0.87 |
| | Gemma +head | 8,371 | 3,227 | 593 | 5.44 |
| | Gemma no head | 7,943 | 2,798 | 276 | 10.12 |

Qwen with thinking on returned no row for any article.

**No article was read by all four arms.** Each dispatch planned independently
and each arm lost different articles to fetch failures, so the overlap is 7
articles between the two Gemma arms and 4 between Ornith and Gemma.

## What a token buys

| Arm | out tokens, median | published words, median | tokens per published word |
| --- | --- | --- | --- |
| Ornith-1.5-9B | 587 | 92 | 6.4 |
| Gemma-4-E4B +head | 4,692 | 110 | 42.7 |
| Gemma-4-E4B no head | 5,033 | 111 | 45.3 |

**This is the largest difference on the page and it is not a speed reading**, so
the processor lottery does not touch it. Both Gemma arms emit roughly seven
times the tokens Ornith does to publish a summary of the same length, on the
same call, against the same schema. The leakage gate saw no reasoning channel
and no think block, so whatever those tokens are, they are inside the structured
reply.

**What they are cannot be read from these runs.** The shard keeps the summary
text and the token count, not the reply, so the other 4,500 tokens are
unaccounted for. A `captures-*` artifact would show them
([../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md)),
and these dispatches did not write one.

## Prefill and decode, which this run did not record

**`ItemObservation` has no prefill field and no decode field.** It keeps
`prompt_tokens`, `completion_tokens` and one `summarize_seconds` for the whole
call. The production path records the split - `ItemHealthRow.summary_prefill_ms`
and `summary_decode_ms` are filled from the server's own `timings` by the
`ItemRecorder` that `two_calls_one_item` accepts - and `stages/qualify.py` calls
that function without a recorder.

So the split below is a **least-squares fit** over every returned call of an arm,
solving `seconds = prompt/prefill_rate + completion/decode_rate`. It is an
estimate in the Guardrail #10 sense and it is labelled one.

| Arm | calls | prefill tok/s | decode tok/s | fit quality |
| --- | --- | --- | --- | --- |
| Ornith-1.5-9B | 23 | 17 | 23.1 | R2 0.274 |
| Gemma-4-E4B +head | 21 | 43 | 7.5 | R2 0.912 |
| Gemma-4-E4B no head | 23 | 25 | 15.3 | R2 0.840 |
| Qwen thinking | 0 | - | - | no call returned |

**Only the two Gemma rows are worth reading, and only within an arm.** Ornith's
fit explains a quarter of its variance, which means the model behind it is wrong
for that arm - most likely because its calls vary in ways prompt and completion
length do not capture. Each arm's calls are also spread over three or four
different processors, so a cross-arm comparison of these rates is the lottery
again.

**The measurement that would settle it** is passing an `ItemRecorder` into the
qualify call, or adding the two timing fields to `ItemObservation`. The
server already returns them on every reply; nothing has to be re-run to start
collecting them.

## What the draft head did here, which is nothing readable

Comparing the two Gemma arms on the 7 articles both read gives the head a
29 percent penalty. **That number is the processor lottery and must not be
quoted.** Only one of the seven article pairs drew the same processor in both
arms, and on that pair the head costs 6 percent - inside the 8.8 percent two
machines of one model differ by anyway. The per-shard draw above says the same
thing from the other direction: the no-head arm drew the 9V74 and the 9V45, the
+head arm drew neither.

| Article | +head processor | no-head processor | +head tok/s | no-head tok/s |
| --- | --- | --- | --- | --- |
| `ai-6hxj0kekw2kvvgga` | EPYC 7763 | EPYC 9V74 | 3.69 | 5.07 |
| `ai-a2q7rckn9tp7es5r` | EPYC 7763 | EPYC 9V74 | 5.21 | 7.42 |
| `ai-h391ga579w7df8st` | Xeon 8370C | EPYC 7763 | 4.63 | 5.17 |
| `ai-rbfesks7bp0tf5fq` | EPYC 7763 | EPYC 9V45 | 4.99 | 9.43 |
| `ai-rh4yqbbzs7036zda` | **EPYC 7763** | **EPYC 7763** | **3.17** | **3.36** |
| `ai-wmwd4yd1nd01hdxr` | Xeon 8370C | EPYC 7763 | 3.61 | 2.48 |
| `business-economy-s0y2jnq52` | EPYC 7763 | EPYC 9V45 | 5.44 | 10.12 |

**Four separate dispatches cannot price a draft head, and that is a property of
the design rather than of these four.** The only reading that ever could is a
paired one inside a single job, which is what
[what-the-draft-head-is-worth.md](what-the-draft-head-is-worth.md) holds. This
page supersedes nothing there.

## What the summaries read like

Three findings survive the lottery because none of them is a speed reading.

**Gemma spells numerals out as words.** On the Huawei story it wrote "the Ascend
nine six zero DT chip", "late two thousand twenty-seven" and "one hundred sixty
thousand", where Ornith wrote "Ascend 960DT" and "2027" from the same article.
Both Gemma arms did it, on every article carrying a model number or a year. This
is a reader-facing defect and no gate on the page catches it.

**Gemma opens by describing the document rather than the news.** "The provided
text compiles several reports detailing current trends..." begins two of its
summaries. A reader came for the story.

**Faithfulness swings hard on one article.** The Federal Reserve story scored
0.950 with the draft head and 0.267 without it, on the same weights. The Huawei
story scored 0.947 from Ornith, 0.327 and 0.218 from the two Gemma arms.

One pair, whole, for the Huawei story:

> **Ornith**, faithfulness 0.947 - Huawei is accelerating the launch of its
> next-generation Ascend 960DT AI chip to the first quarter of 2027, several
> months earlier than the late-2027 date originally planned [...]

> **Gemma +head**, faithfulness 0.327 - Huawei Technologies is accelerating the
> debut of its next-generation artificial intelligence chip [...] the flagship
> Ascend nine six zero DT chip, originally slated for commercial availability in
> late two thousand twenty-seven, will now be launched in the first quarter.

**A defect these runs found that belongs to no model.** Every arm wrote
`Huawei`, a byte that is not ASCII, then `s` where the source had a possessive
apostrophe - the same corruption on `world` and `company` and `Apple`. That is
a right single quote mis-decoded during extraction, and all three models copied
it into the summary faithfully. The character is left out of this sentence
because repository text is ASCII only; the affected summaries are in the
`qualification-samples-*` artifacts named below.

## What this page settles

- **Qwen3.5-9B with thinking on is not a candidate.** Zero valid replies in 24
  attempts, all six injection probes timed out, 266 minutes spent. This is a
  verdict, not a thin-corpus artifact.
- **The corpus precondition throws away evidence it does not need to.** Nine of
  the ten gates were computable on 8 articles and were computed, then discarded
  unwritten.
- **Gemma's token cost per published word is seven times Ornith's**, and where
  those tokens go is unrecorded.

## What it does not settle

- Which model to adopt. The corpus was a third of the floor, so no arm's
  faithfulness mean rests on enough articles to rank them.
- Any speed comparison between arms, or the draft head's price.
- What Gemma emits in the 4,500 tokens that are not the summary.

## The records behind this page

Every run id above is a GitHub Actions run in this repository. The gate verdicts
come from the `qualification-0` through `qualification-3` artifacts of each run;
the summary text comes from `qualification-samples-0` through
`qualification-samples-3`; the processor models come from each shard job's
`What this runner is` step.

## See also

- [what-the-draft-head-is-worth.md](what-the-draft-head-is-worth.md) - the paired reading this page cannot supersede.
- [the-processor-lottery.md](the-processor-lottery.md) - why four dispatches cannot be raced against each other.
- [../models.md](../models.md) - one row a candidate, and the dossier behind it.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - what a model has to pass before it serves.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (a number carries its hardware, date and spread; an unmeasured number is an estimate).
