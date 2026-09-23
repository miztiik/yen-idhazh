# What the two calls cost at the truncation cap, 2026-09-13

**Last Updated**: 2026-09-15
Living, one question one answer. The reading below was taken on one day and
the date is in the title; a re-run of this measurement REPLACES this page and
moves **Last Updated**, and git history holds what it said.

Plan 11 row #3f had to raise `--ctx-size` on the summarize entry so both calls
fit at the truncation cap, and it was dispatched with a table measured on one
cap-length article. This session re-measured the whole sequence on eight, took
the memory reading at three windows, and decomposed the label call's prompt into the
three things that pay for it. It supersedes the sizing half of
[`two-call-re-read.md`](two-call-re-read.md); that record's
re-read findings stand and are not touched here.

## Conditions

| | |
| --- | --- |
| Weights | `backend/models/Qwen3.5-9B-Q4_K_M.gguf`, 5,680,522,464 bytes, hashed against `models.summarizer.declared_for` |
| Server flags | From `server_argv` and `config/` alone: `--ctx-size <case> --no-context-shift --batch-size 512 --ubatch-size 512 --threads 4 -np 1 -fa on -lv 4 --metrics` |
| Instrument | The server's own `POST /tokenize`. No decode ran in this session at all |
| Hardware | A developer laptop: i7-1265U, 12 logical CPUs, 32 GiB, Windows, with four other agents live and 2.0 to 3.1 GB free at each case's start |
| Prose | The 1,444 rows of `corpus/corpus.jsonl`, the one place in this repository that commits source text |
| Config read | `extract.truncation_cap_tokens` 10,000, `elements.max_per_article` 256, `--ctx-size` on the summarize entry 16,384 at the start |

**Why the hardware bounds nothing here.** A tokenizer reading is not a timing.
The same weights return the same token counts on any machine, and the llama.cpp
buffer sizes are arithmetic over the model's own architecture. The one number
below that is a property of this box is peak working set, and it is labelled.

**The cap-length article has to be built.** The corpus's longest body is 3,846
words against a cut point of 7,692, so no committed row reaches the cap - its
longest is `int(5000 / 1.3)` under the cap in force until 2026-09-09. Eight
articles were joined out of corpus prose and cut by `truncate_to_tokens` itself:
longest-first, densest-first by element density, that order reversed, and five
seeded shuffles. `CLAUDE.md` section 13 is the rule - where the awkward shape is
the point, the shape is built, because a built one carries the case the archive
has never produced.

## The sequence, and which build you measure decides the answer

| Build, all 7,692 words | Menu rows | The label call's prompt | The pair | vs 32,768 | vs 65,536 |
| --- | --- | --- | --- | --- | --- |
| densest first | 256 | 26,252 | **37,495** | over by 4,727 | 28,041 spare |
| shuffled, seed 2 | 254 | 23,954 | **35,197** | over by 2,429 | 30,339 spare |
| shuffled, seed 4 | 237 | 21,924 | **33,167** | over by 399 | 32,369 spare |
| shuffled, seed 5 | 178 | 19,778 | 31,021 | 1,747 spare | 34,515 spare |
| shuffled, seed 1 | 157 | 19,589 | 30,832 | 1,936 spare | 34,704 spare |
| shuffled, seed 3 | 136 | 18,455 | 29,698 | 3,070 spare | 35,838 spare |
| longest first | 35 | 15,007 | 26,250 | 6,518 spare | 39,286 spare |
| densest first, reversed | 0 | 13,422 | 24,665 | 8,103 spare | 40,871 spare |

The pair is `the label prompt + 6,491 + 58 + 4,694`: the label call's own output budget
from `label_budget_tokens()`, the seam the summarize-and-plan call adds in front of its reply, and
the reply the summarize-and-plan call's grammar may write from `summarize_and_plan_budget_tokens()`.

**Three of eight exceed 32,768, and two of those three are seeded shuffles.**
That is the finding. The table plan 11 row #3f carried until this session said
26,189 with 6,579 spare at 32,768, and re-measured that build is 26,250 - so the
arithmetic was right and the sample was one, and it was the mildest of the eight.

**What the assertion uses is the worst of each term rather than the worst build.**
Densest-first is worst on the article and seed 2 is worst per menu row, so the
sized worst case is 28,041 of prompt and **39,284 for the pair** - 245 tokens
past the worst single build, which is the price of not assuming one article is
worst at everything.

## Where the label call's prompt goes

| Build | Elements | Body | Sentence addresses | Menu | Tokens a menu row | Body tokens a word |
| --- | --- | --- | --- | --- | --- | --- |
| longest first | 35 | 9,885 | 1,839 | 1,141 | 32.60 | 1.285 |
| densest first | 256 | 15,014 | 2,127 | 6,954 | 27.16 | 1.952 |
| shuffled, seed 1 | 157 | 10,288 | 1,839 | 5,302 | 33.77 | 1.337 |
| shuffled, seed 2 | 254 | 11,289 | 1,857 | 8,665 | 34.11 | 1.468 |
| shuffled, seed 3 | 136 | 10,005 | 1,761 | 4,539 | 33.38 | 1.301 |
| shuffled, seed 4 | 237 | 10,062 | 1,963 | 7,751 | 32.70 | 1.308 |
| shuffled, seed 5 | 178 | 10,118 | 1,869 | 5,639 | 31.68 | 1.315 |

The label call's system turn is **2,055 tokens** on its own, and the whole prompt over a
seven-word article with an empty menu is **2,167** - so the title line, the two
section headers and the fences are the other 112.

**The menu is 22 percent of the sequence at its cap.** 256 rows at 34.115 tokens
is 8,733, and a row is `[element_id] excerpt = value unit (sentence sNN)`.

**A cap-length article reaches that cap, and the corpus says so rather than the
build.** Element density over all 1,444 rows: median 0.0167 a word,
95th percentile 0.0659, highest 0.3512. At 7,692 words those are 128, **507** and
2,702 elements against a cap of 256. One real row already reaches 256. So better
than one cap-length article in twenty pays the full 8,733.

## What three windows cost in memory

| `n_ctx` | KV buffer | Recurrent state | Compute buffer | Model buffers | Total | Peak working set |
| --- | --- | --- | --- | --- | --- | --- |
| 16,384 | 512.00 MiB | 50.25 MiB | 112.02 MiB | 8,024.61 MiB | 8,698.88 MiB = 8.49 GiB | 6,491,164,672 B |
| 32,768 | 1,024.00 MiB | 50.25 MiB | 128.02 MiB | 8,024.61 MiB | 9,226.88 MiB = 9.01 GiB | 9,091,088,384 B |
| 65,536 | 2,048.00 MiB | 50.25 MiB | 160.02 MiB | 8,024.61 MiB | 10,282.88 MiB = 10.04 GiB | 10,167,992,320 B |

**KV is exactly 32 KiB a token and the projection in
[`../pipeline-cost.md`](../pipeline-cost.md) was exact.** It runs over **8
attention layers of 32** - the other 24 are recurrent and carry a fixed 50.25 MiB
whatever the window is, which is why doubling the window does not double the
footprint.

So **65,536 costs 1,584 MiB more than 16,384**, against the runner's measured
low-water free of 6.84 GiB and a 1.0 GiB bar. `n_ctx_train` is 262,144, so none
of these cases scaled RoPE. **65,536 is the window `config/` carries**, so the
reading for it is measured here rather than interpolated.

**Peak working set is the weaker of the two numbers.** It counts the
memory-mapped weights, which the OS may evict, and it moves with what else the
box was doing - and this box had four other agents on it. The llama.cpp buffer
sizes are the ones that carry to a runner.

## What this says about the cap, which is not this record's question

**The densest build's body measured 15,014 real tokens under a 10,000-token
cap.** `truncate_to_tokens` cuts at `words x 1.3`, and that prose tokenizes at
1.952 a word - so the cap over-runs by 50 percent on number-dense text. It is
the same defect `idhazh.measured.WORST_TOKENS_A_WORD` records at 1.585, and this
is one more article that beat it. Nothing here fixes it; row #3f does not lower
the cap or change the extractor.

**And a cap-length prompt may not be affordable at all.** The one 8,741-token
prompt the pipeline has actually sent cost 927 s of prefill on the runner
([`../pipeline-cost.md`](../pipeline-cost.md)). A 28,041-token label-call prompt is
3.2 times that. The window costs memory; the tokens cost time, and the same
tokens cost the same time at any window - so this is plan 11 row #5b's question
and the cap's, not the window's.

## What was taken with

Three throwaway scripts, gitignored under `.tmp_*` and not committed, built on
`backend/utilities/measure_two_calls.py`'s own `corpus_samples`,
`sample_at_the_cap` and `Tokenizer`. The four numbers that outlive them are
`LABEL_SCAFFOLD_TOKENS`, `LABEL_BODY_TOKENS_A_WORD`,
`LABEL_MENU_TOKENS_A_ROW` and `SUMMARIZE_AND_PLAN_SEAM_TOKENS` in
[`../../../backend/idhazh/measured.py`](../../../backend/idhazh/measured.py),
each carrying its own method and what to do when it moves.

**One defect found in `measure_two_calls.py` and not fixed here.** Its printed
ceiling subtracts the retired `max_output_tokens` as the label call's
decode budget, which stopped being the label call's budget when row #3g derived it from
the grammar on 2026-09-12: 900 against 6,491. The ceiling it prints is therefore
5,591 tokens too generous. It is an operator tool that nothing in CI calls, and
the row that owns it is row #3d's.

## See also

- [`two-call-re-read.md`](two-call-re-read.md) - where the summarize-and-plan call's re-read tokens go. Its sizing table is superseded by this record; its re-read findings are not.
- [`../../architecture/summarize/prompt.md`](../../architecture/summarize/prompt.md) - the page that owns the window, and what the assertion reads.
- [`../pipeline-cost.md`](../pipeline-cost.md) - the instrument log, which carries the memory table above.
