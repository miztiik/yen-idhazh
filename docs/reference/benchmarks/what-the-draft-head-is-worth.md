# What Gemma's draft head is worth

**Last Updated**: 2026-09-19

`gemma-4-e4b-qat.json` declares a second file beside the weights: a 56.9 MiB
speculation head, `mtp-gemma-4-E4B-it.gguf`, run with `--spec-type draft-mtp` and
two tokens drafted a step. The head predicts the next tokens so the runtime can
accept more than one a step.

This page is the record of what it bought and what it cost, across four
dispatches between 2026-09-15 and 2026-09-16.

**Two sentences carry the whole result. The head is 6.3 percent faster. It
changes every summary it touches.**

## The four dispatches

| Run | Shape | Runtime machine | Verdict |
| --- | --- | --- | --- |
| `34972996987` | Head on, solo dispatch | AMD EPYC 7763 | rejected, input drift |
| `34973005911` | Head off, separate dispatch | AMD EPYC 9V74 | rejected, input drift |
| `35011578538` | **Both cases alternating in one job** | AMD EPYC 9V74 | rejected, output drift |
| `35062767082` | Both cases, one job, different articles | Intel Xeon 6973P-C | rejected, input drift |

**Every one of the four was rejected, and three of the four still produced a
result.** A rejection here says the comparison the harness was asked to certify
does not hold; it does not throw away what the run measured. Which rejection
matters is the point of the next two sections.

## The speed, from the paired run

The first two dispatches could not answer this and were right not to try. GitHub
put them on different processors, they differed by 5.3 percent, and two runs on
machines both reporting one processor model differ by 8.8 percent anyway ([the
processor lottery](the-processor-lottery.md)). A 5.3 percent difference read
across two runs is silence.

**Run `35011578538` ran both cases inside one job**, alternating, so the machine
cancels.

| Case | A whole repeat over five articles, median | Spread over 2 repeats |
| --- | --- | --- |
| Head on | 2,937,218 ms | +/- 13,131 |
| Head off | 3,122,864 ms | +/- 6,409 |

**The head saves 185,646 ms - 3 minutes 6 seconds over five articles, or 6.3
percent.** The gap is fourteen times the wider of the two spreads, so it is not
noise.

That is the only speed reading on this page and it is one run. It has not been
repeated, because the re-run was rejected for input drift before it reached its
timing.

## The cost, which replicates

Run `35011578538` was rejected with `rejected_output_drift`: **all five articles
got a different summary with the head than without it.**

Sampling is deterministic, which is what makes that a finding rather than noise.
Each case reproduced its own five summaries byte-identically across both of its
repeats, and the two cases disagreed on all five.

**Run `35062767082` repeated it on a different five articles and a different
machine.** That run was rejected for input drift - a publisher edited one of the
five mid-run - but the other four articles are decisive:

| Case | Article 2 | Article 3 | Article 4 | Article 5 |
| --- | --- | --- | --- | --- |
| Head on, repeat 1 | `c61e90c1` | `4129c5f9` | `5843a084` | `2b1eb89b` |
| Head on, repeat 2 | `c61e90c1` | `4129c5f9` | `5843a084` | `2b1eb89b` |
| Head off, repeat 1 | `36a9fa55` | `bf15edc0` | `863a59f5` | `ca66d361` |
| Head off, repeat 2 | `36a9fa55` | `bf15edc0` | `863a59f5` | `ca66d361` |

Each case reproduces itself exactly. The two cases agree on nothing. **So the
output change is the mechanism, not those five articles.**

## What that means

A speculative decoder that accepts a draft token only when it matches what the
main model would have produced is output-identical by construction. That is the
usual claim for speculative decoding and it is why it is normally free.

**The repository these bytes come from makes exactly that claim, and this run
refuses it.** Verbatim, from
[unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF)
read on 2026-09-19, the repository `config/models/gemma-4-e4b-qat.json` pulls at
revision `8c5a9e4fd548`: *"The drafter shares the target's KV cache and does not
change the output (the target verifies every drafted token)."* The same page
names the drafter this entry declares, `mtp-gemma-4-E4B-it.gguf`, and the flag it
runs under, `--spec-type draft-mtp`. **The publisher is describing our exact
setup, not speculative decoding in general.** There is no version of this where
we are outside what the claim covers.

**This configuration is not output-identical, so it is not doing that.** Whether
the cause is the head, the acceptance rule, or this pinned llama.cpp build is
unmeasured. **What is measured is that the vendor's claim does not hold here**,
across two runs, on nine of nine articles.

**A re-run today would not reproduce this, and the reason is not the head.**
Every reading on this page was taken at `temperature: 0`, where one prompt gives
one reply and a changed digest can only be the head. Every committed entry has
pinned `temperature: 0.2` since 2026-09-17, and at 0.2 two readings of one
article differ anyway - Gemma reworded six of seven articles across repeats of
one run on 2026-09-17
([four-candidates-on-one-news-day.md](four-candidates-on-one-news-day.md)). So
**anyone re-testing the head must pin temperature 0 in the scratch config first**,
or the sampler's noise and the head's effect arrive as one number that cannot be
split.

One difference between their setup and ours is on the record and is a candidate
rather than a finding: the card's command passes `--spec-draft-n-max 4` and this
entry pins `n_max: 2`. Nobody has run 4 to see whether the drift follows it.

**The case that would settle it now exists and has not been dispatched.**
`runtime_candidate=draft_depth` runs four configurations inside one job - the
head off, then `n_max` at 1, 2 and 4 - and reads the three against the head-off
case rather than against a baseline, so no runner time is spent re-measuring the
shipped configuration. **It pins `temperature: 0` on every case itself**, which
is how a re-run today keeps the control every reading above was taken with. The
pin sits in the case set rather than in the operator's hands, so a dispatch
cannot forget it and three cases pinned with one forgotten cannot happen.
[../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md#the-cheapest-check-is-the-pipeline-tests-and-it-uses-the-real-prompts)
carries the dispatch and what each argument is for.

**Until it runs, every reading on this page stands as written.** What that
dispatch can answer is which `n_max`, if any, is output-identical to the head
being off; whether the drift scales with the drafted depth; or whether the head
itself is the cause and the depth is irrelevant.

**The practical consequence: the head is not a speed setting, it is a different
model.** It cannot be switched on after qualification and it cannot be switched
off after it. Whichever configuration is qualified is the one that has to
publish, and qualifying one tells you nothing about the other.

## What this page cannot tell you, and why

**Nobody can read these four runs' summaries.** The bench recorded a SHA-256 of
each summary and nothing else - `runtime_sweep.collect` kept `output_digest`, and
the `*.summary.json` files were written on the runner and died with it.

So this page can prove the two configurations write **different** summaries and
cannot show **how** they differ. Better, worse, or merely differently worded is
unknown, and four runs threw that evidence away.

**That was fixed on 2026-09-17: the bench artifact now carries the summary text**
([../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md#13-bench-it---how-fast)).
One paired dispatch from that day forward produces five pairs a person can read
side by side, and the question becomes an editorial one rather than a
cryptographic one. No such dispatch has been read yet, so **the 6.3 percent may
not be quoted as a free speedup**, and the head may not be adopted on the strength
of it.

**That fix was half of one, and the other half landed on 2026-09-19.** The
summary text reached the artifact; the prompts did not, and neither did any way
to tell one repeat's text from another's. `idhazh work` has always written both
halves of every call, but it names a capture for the item and the call alone - so
the second repeat overwrote the first, the next case overwrote that, and none of
it was in the directory the workflow uploads. A reader of one of those artifacts
could see what a case wrote and not what it was asked.

Each repeat's captures are now moved under `captures/<case>-<repeat>/` before the
next one starts, so a dispatch carries every prompt and every reply, per case,
per repeat. **This is the difference between proving two configurations disagree
and being able to say how**, which is the thing four dispatches on this page
could not do.

## The records behind this page

Every run id above is a GitHub Actions run in this repository. `35011578538`
carries the paired timings in its `bench-server-no_draft` artifact; the digest
tables come from `runtime-summary.json` in the same artifact.

## See also

- [../models/gemma-4-e4b-qat.md](../models/gemma-4-e4b-qat.md) - the model this head belongs to, and every other reading of it.
- [../../architecture/summarize/model-boundary.md](../../architecture/summarize/model-boundary.md#a-second-smaller-model-that-guesses-ahead) - how a draft head is declared and what it was supposed to guarantee about the text. The measurement below refuses that guarantee, so read the two together.
- [the-processor-lottery.md](the-processor-lottery.md) - why a comparison across two dispatches says nothing, and why this one had to be paired.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - what a model has to pass before it serves.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (a number carries its hardware, date and spread).
