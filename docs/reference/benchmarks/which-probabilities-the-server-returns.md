# Which probabilities llama-server returns under a grammar, 2026-09-21

**Last Updated**: 2026-09-21
Living, one question one answer. The reading below was taken on one day and the
date is in the title; a re-run of this measurement REPLACES this page and moves
**Last Updated**, and git history holds what it said.

**The numbers that come back are the model's own, before the grammar touched
them.** A window of 25 carries 17 tokens the grammar forbids, and the window a
grammar-constrained call returns is identical to the one the same call returns
with the grammar taken off - the same tokens in the same order at the same
logprobs, to the last printed digit. So renormalising over the legal openings is
not a no-op, and a margin taken over them can still say the grammar chose a word
the model did not.

**The build honours `n_probs: 25`.** Twenty-five came back, three runs, zero
spread.

**`post_sampling_probs: true` returns no window at all.** Not a reshaped
distribution - nothing. The reply parses, carries its word, and drops
`completion_probabilities` outright, on all three runs. A caller that flips the
flag loses the column with no error to read.

## Conditions

| | |
| --- | --- |
| Instrument | `backend/utilities/measure_probability_mode.py`, defaults - 3 runs a mode, `n_probs: 25` |
| Weights | `Qwen3.5-9B-Q4_K_M.gguf`, sha256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` - the file `models.summarizer` declares, and the tool refuses a file the config does not name |
| Build | `b10444-5f754ea0e`, read off `/props` on the running process |
| Flags | `idhazh.llm.server.server_argv` off the configured entry, so they are the run's own |
| Grammar | `root ::= "YES" \| "NO" \| "UNCLEAR"` |
| Prompt | Two headlines and one question, rendered through the entry's own turn markers |
| Machine | 12th Gen Intel Core i7-1265U, 10 cores and 12 threads, 31.8 GiB. **Not the production runner** - what a build does with a request field is not a property of the host, so a developer box answers this question and could not answer a throughput one (Guardrail #2) |
| Date | 2026-09-21. Weights loaded in 20.7 s |
| Spread | Zero. Three runs a mode returned identical logprobs to sixteen significant figures, which is what temperature 0.0 and a fixed seed should give |

## The window, and why it is the model's own

The five likeliest tokens at the answer's opening position, under the grammar:

| Rank | Token | logprob | probability |
| --- | --- | --- | --- |
| 1 | `YES` | -0.2870 | 0.7505 |
| 2 | `UNC` | -1.9769 | 0.1385 |
| 3 | `NO` | -2.2715 | 0.1032 |
| 4 | `UN` | -6.2504 | 0.0019 |
| 5 | `Yes` | -6.5206 | 0.0015 |

Ranks 4 and 5 settle it on their own. `UN` and `Yes` are not legal openings of
`YES`, `NO` or `UNCLEAR`, and they are in the window. Seventeen of the
twenty-five are in that class - `No`, `Yes`, `NOT`, `NONE`, `UNK`, `Unc`, `yes`
and nine more. A post-grammar distribution would carry three entries summing to
1; this one carries twenty-five summing to 0.9981, which is a top-25 slice of
the whole vocabulary.

**The same call without the grammar returns the same window.** The grammar
changes which word is emitted and changes nothing about what is reported beside
it.

## What this settles, and for whom

**Renormalising is real work, and it is small here.** The three legal openings
hold 0.9922 of the returned mass, so renormalising moves `YES` from 0.7505 to
0.7564 - six tenths of a percentage point on this reply. The correction is worth
taking because it is the difference between a number over the whole vocabulary
and a number over the answers the caller allowed, and those are different
questions. It is not worth taking for its size.

**The signal a margin column exists for is readable.** Rank 1 minus rank 2 over
the legal openings is 0.6168 here, which is a model that agreed with the grammar.
A reply where the likeliest legal opening is a long way down the window is the
opposite case, and nothing in this reading hides it - the window is wide enough
and unshaped enough to show one.

**`post_sampling_probs` stays false, and it is sent rather than left out.** The
mode is a decision, no workflow pins a llama.cpp build, and a build that changed
its default would move every margin at once with nothing red. Sending `false`
puts the answer in the recorded body. Sending `true` on this build is worse than
a different number: it is no number, and a nullable column filled with nothing
reads downstream as a server that did not say.

## What this cannot settle

It is one build, one set of weights and one prompt. A build that starts shaping
the window under a grammar would need this page re-run, which costs one server
start and about a minute. The instrument refuses weights the config does not
name, so the one failure mode that matters - a reading quoted against a model
that has since been swapped - cannot happen quietly.

It says nothing about what a margin THRESHOLD should be. That is a judge's
reading over its own replies, not a property of the server.

## See also

- [`../../architecture/summarize/model-boundary.md`](../../architecture/summarize/model-boundary.md) - why the layer hands back the raw window and computes no margin.
- [`what-llama-server-reports-about-itself.md`](what-llama-server-reports-about-itself.md) - the other reading taken off `/props` and the server's own log.
- [`../../architecture/publishing/autotune-content-similarity.md`](../../architecture/publishing/autotune-content-similarity.md) - the margin rule that rests on this reading, and what it does with an unattributable token.
