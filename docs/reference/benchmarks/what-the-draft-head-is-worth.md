# What Gemma's draft head is worth

**Last Updated**: 2026-09-16

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

**This configuration is not output-identical, so it is not doing that.** Whether
the cause is the head, the acceptance rule, or this pinned llama.cpp build is
unmeasured.

**The practical consequence: the head is not a speed setting, it is a different
model.** It cannot be switched on after qualification and it cannot be switched
off after it. Whichever configuration is qualified is the one that has to
publish, and qualifying one tells you nothing about the other.

## What this page cannot tell you, and why

**Nobody can read the summaries.** The bench records a SHA-256 of each summary
and nothing else - `runtime_sweep.collect` keeps `output_digest`, and the
`*.summary.json` files are written on the runner and die with it.

So this page can prove the two configurations write **different** summaries and
cannot show **how** they differ. Better, worse, or merely differently worded is
unknown, and four runs have now thrown that evidence away.

**What would settle it:** keep the summary text in the bench artifact, the way
qualification already keeps `samples-{shard}.json`. Then one paired dispatch
produces five pairs a person can read side by side, and the question becomes an
editorial one rather than a cryptographic one.

Until that lands, **the 6.3 percent may not be quoted as a free speedup**, and
the head may not be adopted on the strength of it.

## The records behind this page

Every run id above is a GitHub Actions run in this repository. `35011578538`
carries the paired timings in its `bench-server-no_draft` artifact; the digest
tables come from `runtime-summary.json` in the same artifact.

## See also

- [../models/gemma-4-e4b-qat.md](../models/gemma-4-e4b-qat.md) - the model this head belongs to, and every other reading of it.
- [the-processor-lottery.md](the-processor-lottery.md) - why a comparison across two dispatches says nothing, and why this one had to be paired.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - what a model has to pass before it serves.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (a number carries its hardware, date and spread).
