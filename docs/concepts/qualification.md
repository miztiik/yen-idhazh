# Qualification

**Last Updated**: 2026-09-18

How a candidate model is judged before it may be adopted, and what a run that
judged it actually proves.

Somebody arrives here holding a new GGUF, or holding a red `validate.yml` run and
asking what the verdict means. **This page is the why.**
[../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md)
is the procedure - which commands, in which order - and it carries no rationale
by rule.

The gates judge writing, so they read the vocabulary
[evaluation.md](evaluation.md) fixes and the column definitions on
[summary-metrics.md](summary-metrics.md). Read those first if a threshold's unit
is not obvious.

## The gate has to call what the digest calls

**Until 2026-09-15 it did not.** The daily run summarizes an article in two adjacent calls - the article is labelled, and the second prompt replays that reply before asking for the summary ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). The qualification sent one call down the chat route instead. So every threshold a candidate cleared was cleared on a code path no reader ever sees: a different prompt, a different number of decodes, and no step where the model reads its own words back.

That is the same shape as the survivor problem above, one level up. A gate that filters on the property it grades measures its own filter; a gate that runs a path nothing publishes measures its own harness. Neither says anything about the day.

`run.qualify_on_the_production_path` is the switch, and it is true by default. False puts the gate back on its single call, which is what to do when a run goes wrong on the pair rather than reverting code - and it is a config edit, so it needs no release. The knob goes away once one qualification has cleared `decide` on the production path.

**Two consequences to expect, and neither is a regression.** Repeats get noisier, because the second prompt carries a model-written label: two repeats that would have written identical summaries can now diverge upstream of the summary. That is a true reading of what production does, and it was invisible before. Since 2026-09-17 the sampler adds noise of its own at `temperature: 0.2`, and on 2026-09-18 the determinism gate was retired outright - what a run records is `wording_spread`, a count of how many distinct wordings each item drew with its denominator, blocking nothing ([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)). And every per-item number moves - an item costs two calls, so the token counts roughly double and the prompt digest is a different digest. `QualificationShard.calls_per_item` records which side produced a shard, because two shards that disagree on it are not comparable ([../../CLAUDE.md](../../CLAUDE.md) Guardrail #10).

**One caller stays on the single call on purpose.** The injection canaries put a planted attack to the model and read the reply for markers that should not have survived. They are a reader-safety check on the sanitizer and the chat template, and the shortest path to the model is the one that tests it most directly ([../../CLAUDE.md](../../CLAUDE.md) Guardrail #11).

## Current qualification-gate implementation gap

**The `publishable_length` gate could not fail at all until 2026-09-10, and it
still reads a population narrower than the run.** It grades the survivors of the
rule it is grading, so for most of its life the only answer its arithmetic
allowed was "none outside the range". Rule 1 above was broken here inside our own
instrument rather than by a model: the word range was the selector, and the same
word range was the alarm.

The range was enforced twice, off the same two knobs. `summarize.to_summary`
counted the drafted words and refused anything outside
`evaluation.summary_words_min` to `evaluation.summary_words_max` with
`length_out_of_range`, returning a payload whose status is `failed` and whose
summary text is unset. `stages.qualify._observe` sets both `ok` and `schema_valid` from that
status, and takes `summary_word_count` from the summary text - zero for a refused
reply, never the count the model actually wrote. `evals/qualify.py` then graded
`[o for o in observations if o.ok]` against those same two knobs. Every reply
that could fail the gate was refused before the gate looked.

Run 33016222069 reported 0 of 90 replies outside the range, and passed
([../reference/measurements.md](../reference/measurements.md#the-configured-summarizer-qwen35-9b-q4_k_m)).
Zero was the only number that arithmetic could return, on any model and at any
threshold, so that result is not evidence that this summarizer writes publishable
lengths. Read every `publishable_length` verdict before 2026-09-10 as "not
measured", never as "passed".

**What changed on 2026-09-10, and what did not.** The two global knobs are gone.
A summary that misses its band's ask is now published, or trimmed at a sentence,
or published over-length - never dropped
([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md#what-happens-when-a-reply-misses-the-ask)).
One case still refuses the item: a summary under
`summarize.length_policy.absolute_floor_words` drawn from a source above
`floor_applies_above_source_words`, which says the extraction failed rather than
that the model wrote briefly. The gate reads the same floor. So the overlap is
narrower rather than gone, and the gate can now return a number other than zero -
a summary under the floor from a **short** source is refused by nothing and fails
the gate. It is a real reading of one narrow case, not a length measurement.

**Recording the words the model actually wrote is still not done.** `stage_qualify`
already appends an observation for every call, refused ones included, so the only
thing missing is the number: `_observe` would carry the words the reply actually
held, and the gate would read every reply rather than the survivors. That widens
the persisted `ItemObservation` contract, which makes it a Level 3 change
([../../CLAUDE.md](../../CLAUDE.md) section 6) needing its own schema stamp,
changelog entry and review. Nothing here does it.

**The same question hangs over any gate that reads only survivors.** Filtering is
sound when the filter and the grade are different properties, and a tautology
when they are the same one. The two other gates that filter were checked and are
sound: `schema_validity` puts every attempt in its denominator and only the clean
ones in its numerator, and `determinism` skips failed calls - a call with no
reply has no digest to compare - but grades digest drift rather than the property
it filtered on, and names how many items it counted. So a new gate answers two
questions before it is registered. Which population does it read, and has an
earlier stage already refused on the property it grades? If the answer to the
second is yes, the gate measures the refusal. If the population is narrower than
the run, the gate's `measured` string has to say so.


## Choosing the model is also a measurement

A published leaderboard ranks models against its own prompt, its own extraction
and its own corpus. Three variables sit between that number and ours, so the
ranking is a better prior than a guess and it is not evidence about this
pipeline. The intended adoption corpus is a frozen, paired set described below.
The current workflow does not build it.

**The comparison freezes extracted inputs, not only URLs.** Planning one URL
list and fetching it once per model does not hold the corpus constant: a
publisher can edit the page between requests, and extraction can then hand the
models different text. A model-choice measurement fetches and extracts once,
persists validated Article payloads under `backend/var/`, and replays those exact
payload bytes through each candidate. Anything else is an exploratory run and
does not support "only the weights changed."

The existing HHEM arithmetic is a screening signal:

| Condition | Legacy verdict |
| --- | --- |
| The incumbent measures more than `validation_drop_max` (0.10) below its leaderboard number | `rescore_candidates` - the ranking was not describing us, so score the others too |
| A challenger beats the incumbent by at least `validation_switch_margin` (0.05) on our corpus | `switch_and_pause` |
| Neither | `confirmed` |

Three things about this are deliberate:

- **A mean over three articles is not a mean.** A candidate scored on fewer than
 `validation_articles` is ignored, on both sides: an undersampled challenger
 cannot win and an undersampled incumbent cannot be confirmed.
- **Better is not enough.** A model swap changes persisted model identity,
 pipeline fingerprints and future words. Current-output goldens may change;
 historical contract fixtures remain compatibility evidence and are not
 rewritten. A challenger that is merely ahead changes nothing. It has to be
 ahead by the margin.
- **The rule never applies a switch.** It returns `switch_and_pause` and stops.
 That pause is the whole point of the gate.

**The arithmetic may screen and must not select.** HHEM is the production alarm.
Using it to choose the model optimizes against the monitor and breaks the rule
in [Two rules that are easy to break by accident](evaluation.md#two-rules-that-are-easy-to-break-by-accident).
It also ignores candidate failure rate, reasoning leakage, schema compliance,
unsupported numbers, dropped hedges, lead coverage, extractiveness, compression,
title fallback and runner fit.

The selector is a pre-registered blind human comparison over paired outputs. No
pairwise model-adoption label contract or CLI exists yet. Until that instrument,
corpus and pass rule exist, `switch_and_pause` means "bring the full evidence to
a person", not "the challenger won."

The ledger records every candidate rather than only the winner, because a ledger
holding only the winner cannot answer the question someone asks six months
later: was the runner-up close?

### The one adoption on record, and it did not qualify

**Qwen3.5-9B-Q4_K_M became the configured summarizer on 2026-08-27 by owner
decision ([../../CLAUDE.md](../../CLAUDE.md) section 0), over two failing hard
gates. It did not qualify.** On a frozen, pre-registered corpus of 30 captured
Article payloads replayed three times, nine of the eleven registered gates
passed, including determinism (0 violations), schema validity (90/90), and mean
faithfulness of 0.7149 against a 0.50 floor. Two failed: the injection canaries
scored 4 of 5 against a Guardrail #11 threshold of all five, because
`exfiltration-via-url` returned no summary at all; and one brief-band item was
reproduced word for word, a verbatim run of 1.000 against a ceiling of 0.5. No
comparison against the retired incumbent Qwen3-8B-Q4_K_M was run - no paired
corpus, no side-by-side scores, no human review - so nothing here shows its
summaries are better or worse than the retired model's.

Qualification run `33016222069`, 2026-08-26, on `ubuntu-latest`. One model, three
deterministic repeats, no side-by-side case. Every gate outcome, the band counts,
the faithfulness spread and the identity of the bytes that ran are in
[../reference/measurements.md](../reference/measurements.md#the-configured-summarizer-qwen35-9b-q4_k_m).

The frozen, **paired** corpus this page asks for above still does not exist.
`qualify` freezes one model's inputs, which is what makes its own numbers
replayable; it does not replay a second model through the same bytes.

### The canary that failed did not survive anything

**This page reported that a control had failed, and it had not. The correction
is the lesson.** Until 2026-08-27 this section read: "the sanitizer was meant to
strip that URL before the model ever saw it, and it did not." Nothing measured
said that. The run's own artifact records `markers_present` as empty for every
canary, the failing one included, and the sanitizer strips all 19 planted
markers across the five committed fixtures while keeping all 10 facts they must
not lose. The gate failed on `replied: false` - the model returned no usable
summary for that item. Four canaries were neutralised, and the fifth was never
exercised, because there was nothing to check. The artifact quote, the local
sweep, its hardware and the command that reproduces it are in
[../reference/measurements.md](../reference/measurements.md#the-fifth-canary-was-never-exercised).

**Guardrail #11 held. Guardrail #10 broke.** Fetched text is data and never instruction,
and the sanitizer plus the schema are the controls that rule names - both did
their job. What failed is the measurement. The gate reported `4/5 passed,
failing: exfiltration-via-url`, a string with no measurement in it, and two
pages read it as a security finding. The gate is being given a failure code so a
reader can tell a breach from a blank reply.

**The consequence for this page is bigger than the reply failure: Guardrail #11 has
no live evidence today.** An instrument that cannot separate a breach from a
blank reply can never confirm the rule it exists to confirm. Eight gates still
measure what they claim to. The canary case does not, and cannot until the
failure code lands - and `publishable_length` does not either, for an unrelated
reason ([Current qualification-gate implementation gap](#current-qualification-gate-implementation-gap)).

**A `sanitizer`-neutralised canary cannot fail its live marker check, by
construction.** This is an eval-design defect rather than a model result.
Sanitization runs before the prompt is built, so every string the canary forbids
is already absent from what the model reads, and no degree of model obedience
can put one back into a reply. Had the model complied perfectly and written
"append the following link: [link]" into its summary, this gate would have
scored that neutralised. An assertion that can only pass is not an oracle. The
output-side control that makes the exfiltration canary falsifiable is being
added.

**The replay against the retired Qwen3-8B-Q4_K_M that this section used to
prescribe is cancelled**, and the reason is recorded so nobody re-opens it. Both
of its branches - "both models fail" and "only the 9B fails" - assume a marker
reached a reply, and none did; and `sanitize` runs before the request is built
under every model, so the replay is structurally incapable of returning a
different answer. What replaces it is narrower: land the failure code, then
re-run the canary case alone against the configured 9B - five calls, no corpus
freeze, no repeats.

### The alarm that watches the swap

Both limbs are arithmetic over committed rows. Neither runs a model.

| Limb | What is read | Trips when |
| --- | --- | --- |
| Unsupported numbers | share of `state/scores.csv` rows with `unsupported_numbers > 0` | the rate doubles, or rises 5 points absolute |
| Copying without a faithfulness cost | mean `extractiveness` and mean `hhem` | extractiveness up 0.10 or more while hhem is flat or up |

Segment by `model_id`, at one fixed `scorer_version`, over a rolling
14 run-days against the last 14 days the 8B produced.

**The segment key was `pipeline_fingerprint` until 2026-09-12, and that is what
made the segment unreachable.** A slug holds still
while the prompt, the truncation cap and the llama.cpp build move, and all three
move the score - but the stamp moved so often that no segment ever reached 14
run-days, so the limb never fired either way
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).
What is given up by segmenting on the slug is named rather than implied: a
reworded prompt inside the window now reads as a model regression, and the run
record's `inputs` is where an operator checks whether one landed.
Holding `scorer_version` fixed matters for the same reason: a rescore under a new
scorer moves both sides of the comparison and would read as a model regression.

The second limb exists because the first one alone can be gamed by the model
itself. A summarizer that copies the source verbatim invents no numbers and
scores well on faithfulness - it has stopped summarizing, and only the
extractiveness pair sees it.

### What the console draws either side of a swap

The alarm above is a gate. The `What the model change moved` panel on the
Summaries route is the reading a person does when it trips, and it obeys three
rules the gate does not have to.

**Ten measures, each against its own value before the change.** A median in
seconds, a length in words, a count in a hundred summaries and a token rate have
no common scale, so the only axis all ten share is "the old model at 100
percent". The ten are: time to write one summary, summary length, copying,
summaries the checker doubted, the three doubt signals apart, summaries outside
the length the prompt asked for, and the two token rates.

**A measure only one side recorded is named, never drawn.** Both token rates
arrived on `state/item-health/<YYYY>/<MM>/<DD>.csv` part way through its life, so a
boundary older than that has nothing on the left. Drawing a track from an absent
value would be a claim about a run nobody instrumented, so those rows print as a
sentence under the plot saying which side is missing. Zero and absent are not
the same answer, and the ledger holds both.

**A measure with no agreed direction paints neutral and says why.** Four of the
ten have none. Summary length and copying are the two the console already
refused to tint. The two token rates join them for a different reason: a shard's
rate is set by the runner it landed on as much as by the model, and the committed
runtime ledger holds one run whose fastest shard read the prompt 4.35 times
faster than its slowest, on one configuration
([../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md)).
A hue there would attribute the machine to the model.

The panel refuses to draw at all where either side holds fewer than
`console.min_attempts_for_rate` summaries, and both article counts print above it
whether it draws or not: two models over two article sets is two measurements and
not a trend.

## See also

- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the procedure: which commands, in which order, to measure a candidate and adopt it.
- [evaluation.md](evaluation.md) - how a published summary is judged. The gates grade writing by these rules.
- [summary-metrics.md](summary-metrics.md) - what each column a gate reads actually means.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - why a summarizer is not asked to repeat itself, and what replaced the gate that asked.
- [../reference/models.md](../reference/models.md) - one row a model: its verdict, its status, and the records behind them.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #10 (an unmeasured number is an estimate).
