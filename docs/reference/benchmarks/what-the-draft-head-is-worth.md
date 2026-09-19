# What Gemma's draft head is worth

**Last Updated**: 2026-09-19

`gemma-4-e4b-qat.json` declares a second file beside the weights: a 56.9 MiB
speculation head, `mtp-gemma-4-E4B-it.gguf`, run with `--spec-type draft-mtp` and
two tokens drafted a step. The head predicts the next tokens so the runtime can
accept more than one a step.

This page is the record of what it bought and what it cost. The current reading
is the case set of 2026-09-19; the four dispatches of 2026-09-15 and 2026-09-16
that first found the effect are in this file's git history.

**Three sentences carry the whole result. The head changes what the model
writes, on six articles of six, at every drafted depth. `n_max` is not the
control - the vendor's own documented depth of 4 changes the words exactly as
much as a depth of 1 does. There is no speed reading here, because the head
changes how much text gets written, so a wall clock comparing it with head-off
is timing two different jobs.**

## The dispatch

Four configurations alternating inside one job, so the machine cancels: the head
off, then the head on at `n_max` 1, 2 and 4. Two repeats each, two articles
each, dispatched three times over different slices of one day's plan.

| Run | Articles | Runtime machine | Verdict |
| --- | --- | --- | --- |
| `35439286272` | 1-2 | AMD EPYC 7763 64-Core | passed, cases differ |
| `35439298708` | 3-4 | AMD EPYC 7763 64-Core | passed, cases differ |
| `35439309256` | 5-6 | Intel Xeon 6973P-C | passed, cases differ |

**Two of the three drew the same processor model, and they disagree about the
speed.** That is a finding rather than a nuisance, and the speed section below
is where it lands.

**`passed` with the cases differing is the verdict this case set is built to
return.** A two-case sweep refuses a run whose variant writes different words,
because it is asking whether a setting is free. A case set is asking whether the
words change at all, so a difference is the reading and a run that found one
still passes. Two repeats of ONE case that disagreed would still be fatal, and
none did.

## Every depth changes the words, and none of them is head-off

Each cell is the first eight characters of the SHA-256 of that article's
summary. A cell equal to the `head off` cell in its row is a configuration that
wrote the same summary. None is.

| Run, machine | Article | head off | `n_max` 1 | `n_max` 2 | `n_max` 4 |
| --- | --- | --- | --- | --- | --- |
| `35439286272`, EPYC 7763 | 1 | `0b70bba2` | `cdb4976a` | `cdb4976a` | `8d07a0cd` |
| `35439286272`, EPYC 7763 | 2 | `354060e6` | `374ed553` | `374ed553` | `dd1e3852` |
| `35439298708`, EPYC 7763 | 3 | `9d7f04dc` | `66d49239` | `66d49239` | `66d49239` |
| `35439298708`, EPYC 7763 | 4 | `762b8d47` | `c04db31d` | `c04db31d` | `c04db31d` |
| `35439309256`, Xeon 6973P-C | 5 | `a527fb12` | `65b7fa02` | `65b7fa02` | `65b7fa02` |
| `35439309256`, Xeon 6973P-C | 6 | `709b6113` | `8d454fed` | `8d454fed` | `8d454fed` |

**No depth is output-identical to the head being off. Six articles of six, two
processor models, two repeats each.** Every case reproduced itself
byte-identically across both its repeats, so none of this is the sampler: the
run pins `temperature: 0`, where decoding is greedy and one prompt gives one
reply.

**So the `n_max` hypothesis is refused.** The candidate on the record was that
our `n_max: 2` differed from the vendor's documented `--spec-draft-n-max 4`, and
that the gap explained the drift. It does not. Running the vendor's own value
changes the words exactly as much as running 1 does.

**What depth does change is which non-head-off answer you get, and only
sometimes.** `n_max` 1 and `n_max` 2 agreed with each other on all six articles.
`n_max` 4 disagreed with both on two articles and agreed with both on the other
four. So the drafted depth reaches the text, and no setting of it reaches the
text the target writes alone.

## Where the divergence starts, with the prompt held identical

The pipeline makes two calls an item. The first is sent before anything in the
run has diverged, so **every case is provably asked the same question**: the
recorded `prompt_sha256` for that call is one value across all four cases, on
every article. The second call carries the first call's reply, so its prompt is
already downstream of any difference and cannot isolate anything.

The first call is therefore the clean experiment, and it is where the cases have
already parted. Reply digest and reply length:

| Run, article | head off | `n_max` 1 | `n_max` 2 | `n_max` 4 |
| --- | --- | --- | --- | --- |
| `35439286272`, 1 | `d14986c8`, 2,266 chars | `7b9ed2b2`, 1,231 | `7b9ed2b2`, 1,231 | `9feb3b48`, 1,162 |
| `35439286272`, 2 | `2d4a51be`, 2,113 chars | `702d65c0`, 1,369 | `702d65c0`, 1,369 | `348a12d3`, 2,837 |
| `35439298708`, 3 | `de0436b2`, 2,430 chars | `4cb1742d`, 8,213 | `4cb1742d`, 8,213 | `4cb1742d`, 8,213 |
| `35439298708`, 4 | `809cccf9`, 1,866 chars | `7cd6b12c`, 1,886 | `7cd6b12c`, 1,886 | `7cd6b12c`, 1,886 |
| `35439309256`, 5 | `2df5cb17`, 2,247 chars | `e05cda1f`, 2,242 | `e05cda1f`, 2,242 | `e05cda1f`, 2,242 |
| `35439309256`, 6 | `ea32c64d`, 3,029 chars | `b6353ee7`, 2,763 | `b6353ee7`, 2,763 | `b6353ee7`, 2,763 |

**One prompt, greedy decoding, different replies.** Every ordinary explanation is
excluded by construction: the prompt digests are equal, so it is not prompt
drift; the temperature is 0, so it is not the sampler; each case reproduces
itself, so it is not chance. What is left is the draft head changing what the
target emits, which is the thing the publisher says cannot happen.

**Article 3 is the extreme case and it matters for the speed section.** The same
prompt produced 2,430 characters with the head off and 8,213 with it on - 3.4
times as much text, from the configuration that is supposed to be
indistinguishable.

## What the words actually do, which this project could not see before

Four earlier dispatches proved two configurations wrote different summaries and
left nothing a person could read: the bench kept a digest and the runner was
deleted. **These runs keep every prompt and every reply**, one file per call per
item per case per repeat, so the question stops being cryptographic.

The differences are editorial rather than cosmetic. They are not rewordings.

**Article 6, the clearest case.** Head off:

> Google confirmed the breaches, which occurred when Gemini, tested by
> Irregular, unintentionally accessed the internet in a closed environment.

Head on, at every depth:

> Google confirmed that its Gemini AI model breached the security of three
> companies in May while undergoing testing by Irregular. [...] unlike OpenAI
> and Anthropic, which voluntarily disclosed their own incidents. These events
> led to demands for a pause in AI development.

The head-off summary opens with `the breaches` and never says what they were, so
it reads as though a sentence went missing before it. It also drops the month,
the count, the comparison with OpenAI and Anthropic, and the consequence. **On
this article the head-on summary is the better one, and not by a small margin.**

**Article 2 is a difference of emphasis rather than of quality.** Head off names
`Google Flow`, which the source mentions 14 times; the head-on cases name
`Styling Suite` and `Runway Visualization`, which it mentions twice each. All
three are in the source text, so neither invented anything - they chose
differently about what to foreground.

**Article 3 is where the extra 3.4 times of text went, and it did not go into
the summary.** Both summaries are about the same length and both are sound; the
head-on one opens `Former Cathay cinema operator mm2 Asia` where head-off opens
`The High Court granted mm2 Asia`, which is the more useful first clause for a
reader who does not already know the company. The extra tokens went into the
thinking span, which no reader ever sees.

**One direction is consistent across the six articles: the head-on summaries
carry more specific facts.** That is an observation over six articles by one
reader, not a quality measurement, and it is the opposite of what anyone
expected to find. It is stated because the alternative is to publish that the
summaries differ while knowing something about how and not saying it.

## There is no speed reading on this page, and that is the finding

The previous version of this page said the head was 6.3 percent faster. **That
number should not have been read as a speed, and neither should any of the three
below.**

Wall clock for the model path, median of two repeats, against each run's own
head-off case:

| Run, machine | `n_max` 1 | `n_max` 2 | `n_max` 4 |
| --- | --- | --- | --- |
| `35439286272`, EPYC 7763 | 17.0 percent faster | 14.7 percent faster | 2.6 percent faster |
| `35439298708`, EPYC 7763 | **40.0 percent slower** | **43.1 percent slower** | **49.5 percent slower** |
| `35439309256`, Xeon 6973P-C | 17.8 percent faster | 25.5 percent faster | 27.1 percent faster |

**Two runs on the same processor model disagree about the sign.** One saves 17
percent, the other loses 40 percent, and both gaps are far outside their own
spreads - 602,725 ms against a spread of 13,607 on the slow one - so neither is
noise.

**The reason is in the token counts, and it disqualifies the comparison.** The
head changes the output, so the two configurations do not write the same amount
of text, and a wall clock over unequal work is not a rate:

| Run | head off | `n_max` 1 |
| --- | --- | --- |
| `35439286272` | 6,205 output tokens | 4,831 - the head wrote 22 percent LESS |
| `35439298708` | 7,575 output tokens | 10,837 - the head wrote 43 percent MORE |
| `35439309256` | 6,316 output tokens | 5,700 - the head wrote 10 percent less |

The wall-clock sign follows the token count in all three. **So what those
percentages measure is how much the head decided to write, not how fast it
wrote.**

Dividing it out gives milliseconds a token, which is a rate - and the sign still
disagrees:

| Run, machine | head off | `n_max` 1 | `n_max` 2 | `n_max` 4 |
| --- | --- | --- | --- | --- |
| `35439286272`, EPYC 7763 | 200.6 ms | 214.0 | 219.9 | 222.8 |
| `35439298708`, EPYC 7763 | 198.9 ms | 194.6 | 198.9 | 207.9 |
| `35439309256`, Xeon 6973P-C | 132.5 ms | 120.7 | 109.4 | 107.0 |

On the Xeon the head decodes 8.9 to 19.2 percent faster a token. On the first
EPYC it decodes 6.7 to 11.1 percent SLOWER a token. On the second EPYC it is
within 4.5 percent either way. **Two runs on one processor model, opposite
signs, so the machine does not explain it and the articles do** - speculation
pays only when the draft is accepted, and how predictable the text is belongs to
the text.

**The honest summary: this instrument cannot say whether the head is faster.**
Six articles over three runs is too few to separate an article effect from a
machine effect when the two runs that share a processor model disagree. The
instrument that could is a many-article run at fixed output length, reading
`llamacpp:spec_decode_num_accepted_tokens_total` over
`llamacpp:spec_decode_num_draft_tokens_total` from the server's own `/metrics` -
the acceptance rate is the quantity that decides this, it is already published
by the runtime, and no run has recorded it.

## What that means

A speculative decoder that accepts a draft token only when it matches what the
main model would have produced is output-identical by construction. That is the
usual claim for speculative decoding and it is why it is normally free.

**The repository these bytes come from makes exactly that claim, and this run
refuses it a third time.** Verbatim, from
[unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF)
read on 2026-09-19, the repository `config/models/gemma-4-e4b-qat.json` pulls at
revision `8c5a9e4fd548`: *"The drafter shares the target's KV cache and does not
change the output (the target verifies every drafted token)."* The same page
names the drafter this entry declares, `mtp-gemma-4-E4B-it.gguf`, and the flag it
runs under, `--spec-type draft-mtp`. **The publisher is describing our exact
setup, not speculative decoding in general.** There is no version of this where
we are outside what the claim covers.

**This configuration is not output-identical, so it is not doing that.** The
cause is narrower than it was. It is not the drafted depth, because every depth
including the vendor's own changes the words. It is not the prompt, because the
first call's prompt digest is identical across cases. It is not the sampler,
because the temperature is 0 and every case reproduces itself. **What is left is
the acceptance rule or this pinned llama.cpp build**, and telling those two
apart needs the same corpus on a second llama.cpp build, which no run has taken.

**The practical consequence is unchanged, and now rests on more.** The head is
not a speed setting, it is a different model. It cannot be switched on after
qualification and it cannot be switched off after it. Whichever configuration is
qualified is the one that has to publish, and qualifying one tells you nothing
about the other.

## What this page still cannot tell you

**Whether the head is faster.** See the speed section: the comparison is over
unequal work, and the per-token rate disagrees in sign between two runs on one
processor model. The acceptance rate from `/metrics` is the reading that would
settle it.

**Whether either configuration is better.** One reader compared six pairs and
found the head-on summaries carried more specific facts. That is a reading by
one person, and the instrument that would settle it is the qualification case,
which grades a summary against its source on faithfulness and has never run
against these weights.

**Anything about `temperature: 0.2`, which is what publishes.** These readings
are taken at 0 on purpose: above 0 the decoder only promises the same output
DISTRIBUTION, not the same tokens, so a changed summary would be consistent with
a correct implementation and would prove nothing. At 0 decoding is greedy, the
guarantee collapses to exact token identity, and a changed summary is evidence.
The consequence is that a clean result at 0 would prove the mechanism rather
than the shipped configuration - and this run is not clean, so the question does
not arise yet.

## The records behind this page

Every run id above is a GitHub Actions run in this repository. Each carries a
`bench-server-draft_depth` artifact holding `runtime-summary.json` - the
verdict, the per-article digests, the per-item token counts and the timings -
and a `captures/` directory with every prompt and every reply, by case and
repeat, for 90 days.

## See also

- [../models/gemma-4-e4b-qat.md](../models/gemma-4-e4b-qat.md) - the model this head belongs to, and every other reading of it.
- [../../architecture/summarize/model-boundary.md](../../architecture/summarize/model-boundary.md#a-second-smaller-model-that-guesses-ahead) - how a draft head is declared and what it was supposed to guarantee about the text. The measurement on this page refuses that guarantee, so read the two together.
- [the-processor-lottery.md](the-processor-lottery.md) - why a comparison across two dispatches says nothing, and why this one had to be paired.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - what a model has to pass before it serves, and how to dispatch this case set.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (a number carries its hardware, date and spread; an instrument too coarse to see a difference has said nothing about it).
