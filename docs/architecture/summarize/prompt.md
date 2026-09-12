# The summarizer prompt

**Last Updated**: 2026-09-10

What the Summarize stage asks a model for, and where every number in that ask
comes from.

Two things the prompt is deliberately not responsible for. The **output shape**
is held by the decoder, and the **trust boundary** is held by the sanitizer and
the fence. A prompt asking a model to behave is not a control, and neither of
those depends on one.

The stage itself is described in
[`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md). This page
owns the prompt.

## The prompt is a template, not a text

`backend/idhazh/prompts/summarize.txt` holds no numbers. It holds
`$target_words_min`, `$title_words_max`, `$max_verbatim_words` and their
siblings, and `system_prompt` substitutes them from `config.summarize` at
render time (Rule #6).

Substitution uses `substitute` and never `safe_substitute`. A renamed knob
raises here. The alternative is rendering the literal `$target_words_max` into a
live system prompt, where a model reads the placeholder as the instruction it
looks like.

## One ask per article length

`config.summarize.bands` holds one length ask per article size, ordered by
`min_source_words`. `band_for` picks the longest band the article reaches,
unless extraction recorded the item as brief. A brief item always uses band 0.

A release note and a long read asked for the same number of words gives a padded
summary of the first and a thin one of the second.

Band 0 is the brief band: `{0, 30, 45}`. The former first band starts at 60
words and asks for 50 to 90 words. The split is forced by the source floor:
`30 / 0.5 = 60`.

Five rungs, and what a reader gets on each:

| Rung | From | Ask | Over-long | The item |
| ---: | ---: | --- | --- | --- |
| 0 | 0 | 30-45 | trim | A note. The one fact the post carries, so the reader decides in seconds whether to open it. |
| 1 | 60 | 45-80 | trim | A news report. Who did what, how much, when - carryable into a conversation without opening the source. |
| 2 | 700 | 70-130 | trim | A feature or an analysis. The event, why it matters, the main caveat. |
| 3 | 2000 | 95-160 | publish | A long feature. The event, the evidence, who disputes it, what is still open. |
| 4 | 4000 | 120-200 | publish | A long read. The distinct things the piece established, named separately, plus the response from whoever it accuses and the qualification it ends on. The one item on the page a reader may finish and treat as read. |

Three rules make band selection safe rather than approximate:

- The first band must start at zero, so selection is total and no article falls
 through with no ask at all.
- Bands must climb, and no two may start at the same length. A config whose
 bands do not climb is refused at load, because `band_for` would otherwise
 return the wrong ask instead of failing.
- **No band floor may sit above the cut point**, which is
 `int(extract.truncation_cap_tokens / TOKENS_PER_WORD)`.
 `test_no_rung_floor_ever_sits_above_the_cut_point` reads both sides from
 `config/` and fails on a ladder that breaks it.

The band is chosen from the length of the **source body**, before
`extract.truncation_cap_tokens` cut it. `Article.source_word_count` carries that
number and `Article.band_source_words` reads it, falling back to the post-cap
count on a payload written before the field existed.

### Design rationale - why the band left the post-cap count

Until 2026-08-26 the band came from the post-cap count, on the argument that
asking for a summary of words the model never saw is asking it to invent them.
Two things were wrong with it.

The argument is about content, and a band sets only the target length. The
fenced block still holds the visible text and nothing else, so a longer ask
cannot reach words the model was not given.

The rule also could not work. The post-cap count cannot pass
`int(truncation_cap_tokens / TOKENS_PER_WORD)`, which at the cap of 2500
committed then was **1923 words** - below the top band's 2000. That band never fired once,
and its longer ask was dead configuration. Measured 2026-08-26 over 109 articles
extracted live from that day's plan: the post-cap rule put 0 of them in the top
band, and the source-body rule put 3 there.

The knob's own name settles which count it wants. `extract.min_source_words`
already compares against the full body, and `summarize.bands[].min_source_words`
is the same name for the same thing. Two meanings for one name was the defect.

The rejected alternative was to lower the top band's boundary under 1923. That
makes the number fit the code instead of making the code mean the number, and it
moves a threshold to make a corpus pass - which Row #10 decision 3 forbids.

### Design rationale - the ladder is editorial, and 200 words governs it

**The ceiling is 200 words, and every other number is built down from it.** An
adult reads non-fiction at about 240 words a minute, so the two minutes this
digest asks for is roughly 480 words. Thirty titles at 8 to 10 words spend 250
to 300 of them being scanned. What is left buys two summaries at 90 words or one
at 200 - and a 200-word item is already 50 seconds on one story out of thirty.
Past that the digest stops helping a reader decide whether to click through and
starts being the article, badly.

**The ask grows with the source logarithmically, not in proportion to it.**
Doubling an article does not double its distinct claims; it adds scene-setting
and repetition. Outside practice says this twice. An informative abstract is
capped near 250 words whether the paper is 4,000 words or 40,000 (ANSI/NISO
Z39.14). The executive summary's "five to ten percent" rule is always overridden
by "never more than two pages". Every trade that abstracts at scale opens with a
ratio and closes with a ceiling, and so does this ladder.

**The top rung is at 4,000 rather than at the cut point.** At the
`extract.truncation_cap_tokens` of 10000 committed now the model is handed 7,692
words, so a 16,000-word piece and a 7,692-word piece are handed the same words
and get the same ask, which is right. Every source past 4,000 arrives with much
the same evidence for the same reason, so a rung nearer the cut point would grade
articles by a length nobody read - and the model would close the gap by
elaborating the opening, which reads as completeness. This is the rule the
ladder has to keep, not the number 4000: the cap moved from 2500 to 5000 on
2026-08-29 and from 5000 to 10000 on 2026-09-09, and it will move again, so
`test_no_rung_floor_ever_sits_above_the_cut_point` reads both sides from
`config/` (Rule #6). A test that only checks the rungs climb passes either way
and proves nothing.

**None of these numbers came from `state/scores/`, deliberately.** The
summariser prompt is being tuned and a fine-tune is in flight, so our own length
figures describe a pipeline mid-repair. An earlier version of this page argued
the ladder from them and reached a circular answer: the model had never been
asked for more than 230 words, so the fact that it had never produced more than
223 was the ask talking back to itself - and it was quoted as evidence that a
higher ceiling would buy nothing. It proves nothing in either direction. The
ladder is argued from editorial practice and from the reader's two minutes
instead, and it should be re-derived against our own numbers once they describe
a settled system (Rule #10).

**What the rungs at 3000 and 5000 cost, stated rather than hidden.** They were
added on 2026-08-29 and 2026-09-09 and collapsed into one rung at 4000 on
2026-09-10. The second raised only the floor of its ask and kept the rung
below's ceiling, so the top of the ladder carried two rungs that differed by 30
words of floor and nothing else - which is not a rung, it is a rounding. The
collapse also gives the canary day's top rung two marks: its eight items place
one under each of the four lower zones and two under the rung at 4000.

## What happens when a reply misses the ask

The ask is a request. `summarize.length_policy` is the rule, and the two are
deliberately different: a prompt that asked for exactly what the pipeline
accepted would lose a story every time the model rounded.

| Miss | What happens |
| --- | --- |
| Inside `target_words_max` plus the allowance | Published untouched. |
| Past it, rungs 0 to 2 | Trimmed at the last complete sentence that fits. |
| Past it, rungs 3 and 4 | Published over-length. |
| Under `target_words_min` | Published. A thin summary still tells the reader something. |
| Under `absolute_floor_words`, from a source past `floor_applies_above_source_words` | **Failed.** The only length that still drops an item. |

The allowance is the larger of `overshoot_ratio x target_words_max` and
`overshoot_words`. The ratio alone is useless on a short rung - 20 percent of 45
words is nine, which is one clause - and the flat count alone is meaningless on a
long one. Whichever is larger applies, and
`test_the_wider_of_the_two_overshoot_allowances_wins` pins both sides of that
boundary, because it is the clause most likely to be read backwards later.

**The floor reads the article, not only the reply.** Twenty words from a
3,000-word source is a failed extraction wearing a summary's clothes. The same
twenty words from a 50-word note is the correct answer, and failing it would
lose a story to arithmetic. `floor_applies_above_source_words` is what separates
them.

**Why a long rung publishes over-length where a short rung trims.** Wire-shaped
prose front-loads, so cutting the tail of a note is safe. On a feature the
qualification lands last, and cutting it is how a summary stops being true. The
choice is per band (`SummaryBand.over_length_action`) rather than global, because
it is the one thing here that genuinely differs by rung. The trimmer never makes
a mid-sentence cut: a summary with no sentence end inside the budget is published
whole, because a dangling half-clause reads as a bug where an over-long paragraph
reads only as an over-long paragraph.

**Nothing is dropped for running long, and that is the point.** Until
2026-09-10 `evaluation.summary_words_min` and `summary_words_max` were two
integers applied to all five rungs of a ladder they could not see, and a reply
outside them returned `LENGTH_OUT_OF_RANGE` - which deletes the item from that
day's digest, with no second attempt. A 210-word reply to a 200-word ask cost
the reader the story. Length is the one property a reader can judge unaided: a
summary that is too long is one they stop reading, and a summary that is missing
is nothing at all. So length may not be the property that silently removes a
story.

**There is no retry, on purpose.** Asking the model again is the obvious fourth
outcome, and here it is dead code: `models.summarize.inference` pins
`temperature=0.0` and `top_p=1.0`, and the `seed` field's own description says it
is dead under greedy decoding. An identical payload returns an identical reply,
so a retry loop would spend a second inference call on the tail of every run to
receive the same words. It can be built the day decoding stops being greedy, and
not before.

**The decoder rail is the trap in this design.**
`SummarizeConfig.decoder_words_max` is deliberately the loosest number in the
file - the widest ask plus its allowance - because the rail is enforced as a
character budget during decoding. A reply past it fails to parse, and a reply
that cannot parse never reaches the verdict that would have trimmed it or
published it long. Tighten the rail and every overshoot turns back into the lost
item this policy exists to prevent.
`test_the_decoder_rail_never_catches_a_summary_the_verdict_would_publish` holds
it open.

**Honesty about a partial read is a sentence, and never a word count.** The
tempting alternative is to ask for *fewer* words when the article was cut. It
tells the reader nothing: they cannot see the article's true length, so a short
summary of a half-read investigation reads as a short article. The instrument is
the sentence the item already carries - "We could only read the first N percent
of this page.", degrading to "We could only read the first part of this page."
when the length before the cut is unknown
([../../concepts/digest.md](../../concepts/digest.md)). Five of the 9 items past
3,000 words measured on 2026-08-29 are still cut at 3,846 words (4,212; 4,444;
5,314; 8,207; 8,442), so this is the common case on the top rung and not the
corner.

**The failure this pair is written against.** An investigation puts the response
from whoever it accuses, and the qualification it ends on, in the last third. On
a cut piece the model never saw either. A 200-word summary that reads as
complete and omits the denial is the worst item this pipeline can publish, and
the sentence is what stops it.

**`summarize.bands[].key_points_max` grades with the rung: 1, 2, 3, 4, 5 from
the brief band to the longest whole read.** The count moved off `SummarizeConfig`
and onto `SummaryBand` on 2026-09-07, so each rung asks for its own. The shortest
asks for one, because a 30-to-45-word note carries about one distinct fact, and
asking it for five requests facts the article does not hold - the extra bullets
then restate the summary. The top rung keeps five, where a long read genuinely
carries that many. `key_points_min` moved with it - 1 at the brief band, 2 from
rung 2 up - because the prompt reads both numbers off the band, and the shortest
rung's ceiling of one sits below the old global floor of two. The decoder is held
to the same per-band range, so the ceiling is a control and not a request: a note
cannot emit the five bullets that would pad it.

Each rung is checked against a simple bound: a key point is one sentence of about
20 words, so a summary of W words carries about W/20 distinct facts, and no rung
may ask for more key points than that. At the five committed rungs that bound is
2, 4, 6, 8 and 10 facts against asks of 1, 2, 3, 4 and 5, so every rung sits
under it with room to spare.
`test_no_band_asks_for_more_key_points_than_its_summary_can_carry` reads the
ladder from `config/` and asserts it per band, so a sixth rung cannot be added
over its own bound by accident.

**Every rung above the brief tier moved on 2026-09-10.** An earlier version of
this section said no existing rung had moved, and defended each new rung against
the one below it. That was true while the ladder was being extended a rung at a
time; it stopped being true when the whole ladder was re-derived from editorial
practice rather than from the cut point. What survives from that argument is the
observation it was built on - rung 2 covers about 30 percent of a day, so its ask
is the one that costs the most to get wrong.

## What the top rung has not proved yet

Two things are written down here because they are cheap to record now and
expensive to reconstruct later. Both were written for the rungs at 3000 and 5000
and both apply unchanged to the single rung at 4000 they collapsed into.

**The falsification test, which has not been run.** Summarize the items past
4,000 words twice - once at the ask below and once at the top rung's own ask -
and count **distinct findings**: a fact a reader could act on that the other
summary does not contain. If the longer summary names no more findings on two
thirds of them, the rung buys padding and it should be withdrawn. It is a count,
not a score, so it needs no labels and no grader (`CLAUDE.md` section 0a forbids
a model grading a model). Second observation to take at the same time: if the
still-cut pieces draw every fact from the first 40 percent of what the model
read, the extra words went into elaborating the opening, and those items belong
a rung lower.

**A score drop on the top two rungs is not a regression.** `hhem` scores a
summary against one window of the article at a time, and a summary drawing on
both the opening and the closing of a long piece has no single 900-word window
supporting all of it. This is measured, not feared: over
the 117 real evidence pairs of run
`33179908136`, a three-window article scores **0.3986 lower** than the same
article read whole, and a two-window article 0.2178 lower, while the one-window
control reads exactly 0.0000 on 91 of 91
([../../reference/measurements.md](../../reference/measurements.md)). The high
band starts at 0.80 and the medium at 0.50, so a 0.40 drop is wider than the
whole medium band. Every rung-3 article is at least three windows by
construction, because 2,000 words at `evaluation.chunk_words` of 900 cannot be
fewer, and a rung-4 article is at least five. **The score is expected to fall
while the summary improves.** Read it
against the length bias, or the first run at the new ladder will look like a
quality failure.

## The ask is a request, and the rule is separate

`summarize.bands[]` is what the prompt requests. `summarize.length_policy` is
what the pipeline does when the reply misses. They are deliberately different
numbers: a prompt is a request and a rule is a rule, and asking for a tighter
range than we enforce is what stops a two-word miss from losing a story.

**Until 2026-09-10 the rule was two global integers and a validator held every
band inside them.** `evaluation.summary_words_min` and `summary_words_max` were
the same pair for all five rungs, and `AppConfig._the_ask_sits_inside_the_gate`
refused any band that asked outside them. The validator was correct and the
shape it was validating was the defect: the whole ladder was hostage to the one
global window, a rung could not ask for more than the window allowed however
long the article, and the enforcement was a deletion. Both keys and that
validator are gone. The policy is per band, the tolerance is derived from the
band's own ceiling, and the only remaining refusal is the absolute floor above.

One validator survives, renamed `_the_ladder_and_the_extract_floor_agree`: it
checks that `extract.min_source_words` really is
`bands[0].target_words_min / evaluation.brief_compression_ceiling`, because that
floor is derived and an operator editing one of the three numbers alone would
silently break the brief tier. A second lives on `SummarizeConfig`:
`absolute_floor_words` must sit below every band's `target_words_min`, or the
one rule that still drops an item would be firing on summaries the ladder asked
for.

## The decoder holds the shape, the prompt does not

The output shape is enforced by grammar-constrained decoding against a schema
generated from `SummaryDraft`, not requested in prose. `SummaryDraft` is closed
to unknown keys, so a planted tool call fails at validation rather than reaching
a payload.

## The second call writes this summary, and the article is read once

A second prompt is being built beside this one.
`backend/idhazh/prompts/label_article_elements.txt` asks a model what an
article's already-extracted quantities and dates mean;
`backend/idhazh/prompts/summarize_and_plan_visual.txt` then asks the same model,
in the same conversation, for this page's summary and for a plan for one
picture. Neither is dispatched by any stage yet - the gate in front of them and
the picture they lead to are later rows of
[`../../../TODO/20260905-11-two-call-planner-plan.md`](../../../TODO/20260905-11-two-call-planner-plan.md).
What is settled, and what this section owns, is why the second call is shaped
the way it is.

**Call 2 appends to call 1's message array, and reuses call 1's system prompt.**
The request is built from call 1's own payload rather than rendered again, so
the system turn and the article-carrying user turn are the same bytes and not
merely the same intent. A prefix cache reuses the longest common prefix of the
tokenised prompt, so a system prompt of call 2's own would end the shared prefix
at the chat template's header and prefill the whole article a second time -
roughly double, for a wording whose benefit nobody could measure. The reuse is
asserted on the bytes and never on a `prefill_ms` ratio, which would confound
cache reuse with how long the new turn is and would read as partial success when
the prompt had been built in the wrong order.

**The two calls belong adjacent, per item.** `models.summarize.inference` pins
`n_parallel` to 1, so the server holds one cache slot. Every call 1 first and
every call 2 afterwards would evict the prefix before it was reused, every time,
and nothing in any log would say so.

### What the cache actually reused, and the four tokens it did not

`backend/utilities/measure_two_calls.py` starts a real server, sends the two
calls adjacent on one slot, and reads `timings.cache_n` off call 2's reply.

**12th Gen Intel Core i7-1265U, Windows 11, four threads, `n_ctx` 16384, flash
attention on, `Qwen3-8B-Q4_K_M.gguf` through `llama-server`, 2026-09-10, one
run.** The token counts are exact and are a property of the template and the
tokenizer; the milliseconds are this laptop with other work on it and are not a
runner figure.

| | call 1 | call 2 |
| --- | --- | --- |
| prompt tokens | 1,497 | 2,389 |
| **cached tokens** | 0 | **1,493** |
| completion tokens | 205 | 567 |
| prefill | 214.1 s | 186.8 s |
| decode | 88.8 s | 292.6 s |

**The article and the system turn prefilled once, and the reuse stops four
tokens short of call 1's whole prompt.** Those four are
`<think>\n\n</think>\n\n`, which tokenizes to `[151667, 271, 151668, 271]`
against the same weights on the same day. Qwen3's chat template writes an empty
think block into the **generation prompt** under `enable_thinking: false` and
drops it when the same turn is replayed as **history**, so the two renderings
diverge at exactly that point. Nothing in this repository renders it and no
change to how the prompt is built moves it.

**What those four tokens cost is not four tokens.** A prefix cache reuses a
prefix, so the divergence ends the reuse and everything behind it is processed
again: 1,493 cached against the 1,702 that call 1's prompt and its own reply
come to, which is 209 tokens re-prefilled - the four, plus the whole 205-token
reply. That answers the second half of the question this measurement was taken
to answer: **call 1's generated tokens do not cache**, and the reason is
upstream of them.

The weights measured are not the configured ones. `models.summarize` names
`Qwen3.5-9B-Q4_K_M.gguf`; `Qwen3-8B-Q4_K_M.gguf` is the retired incumbent and is
what this machine holds. The result is about a chat template rather than about
weights, but a template ships with its weights, so it is re-measured when the
model moves.

**209 re-prefilled tokens is not a runner number, and the run that will price it
is nameable.** It was taken on a developer laptop, against the retired 8B weights
rather than the configured 9B, in one run with no spread - so it says the reuse
stops short, and it sizes nothing. Nothing new has to be built to price it on the
runner: `Completion.cached_tokens` comes off `timings.cache_n` in
[`../../../backend/idhazh/llm/server.py`](../../../backend/idhazh/llm/server.py),
`Summary.cached_tokens` persists it per item, and
[`../../../backend/idhazh/publish_day_metrics.py`](../../../backend/idhazh/publish_day_metrics.py)
already derives `input_tokens - cached_tokens`, which is the count of tokens the
server actually read again. What is missing is a call 2 to read it from. No daily
run produces a call-2 row yet, because nothing dispatches either call:
`build_call_one_request`, `parse_call_one`, `build_call_two_request` and
`parse_call_two` are referenced only inside `classify/calls.py` and its tests,
and `cli.py` never calls them. The wiring is row 6 of
[`../../../TODO/20260905-11-two-call-planner-plan.md`](../../../TODO/20260905-11-two-call-planner-plan.md),
so **the trigger is the first daily run after row 6 lands** - not the next
content refresh. Re-read the figure then, and again when plan 11 is distilled per
[`../../how-to/distill-a-plan.md`](../../how-to/distill-a-plan.md).

**Open gap, owned by nobody: the prompt loop still refines the prompt that is
retiring.** `backend/utilities/prompt_loop.py` today refines the single-call
summariser prompt, `prompts/summarize.txt`. Once call 2 writes both the summary
and the plan, the loop's target must become
`prompts/summarize_and_plan_visual.txt`. This is owned by no row of plan 11 and
no row of plan 12. It is written here so the distill picks it up.

**Which prompt asks what.** Call 1 labels what is in the item - what its
already-extracted quantities and dates mean - and never asks for a picture. Call
2 asks for two things in one reply, in this order: the summary first, then the
plan for one picture. `prompts/visual_planner.txt` and `prompts/summarize.txt`
are the single-call pair these two replace, and row 6 of plan 11 deletes them.

**A prompt file is named for what it asks the model to produce, not for its
position in the sequence.** Both files carried their call number as their name
until 2026-09-10. The calls keep their numbers - the order is what the
prefix-cache argument above rests on - but a filename carries no order, so it
says what the prompt asks for.

### `summary` is decoded before `visual`, and that order is the recovery

Field order is decode order, so the summary is written and closed before the
plan is started. Two things follow and neither is cosmetic.

**A reply the output budget cuts is cut in the plan.** The bytes come back on an
ordinary HTTP 200 and a grammar-constrained decoder closes each sub-object as it
finishes it, so the summary in front of the cut is closed, balanced and
independently parseable. `classify.calls.recovered_completion` reads it out with
`json.JSONDecoder().raw_decode` and hands back something shaped exactly like a
single-call reply - so the length verdict, the copied-source reject, the address
reject and the restatement drop above all still run on it, unchanged. The item
publishes with its summary and no picture, at no extra seconds and with no
second request. Reversed, the same cut would lose the summary, which is the part
a reader came for. `to_summary` used to fail such an item on `finish_reason`
without reading the bytes at all.

**The plan is drafted with the summary already in context, and that is
conditioning rather than sourcing.** The plan may cite only an element the
article's own table carries, so a picture cannot draw a figure the summary
happened to mention and the table does not hold. The risk this ordering does
carry is the other direction: a plan can drift toward illustrating the sentences
the summary chose rather than the article. **If `information_delta` collapses
after this ordering goes live, this is the first thing to suspect.**

### The output budget is derived, not picked

Call 2 decodes the summary and the plan through one ceiling, and that number is
arithmetic over the two shapes' own bounds. Every array in them carries a
`maxItems` and every decoded string a `maxLength` - which is why
`summarize.key_point_words_max` exists at all, since a key point was the one
decoded string in the reply with no upper end and a derivation with an unbounded
term in it is not a derivation.

`classify.calls.call_two_output_tokens` runs the arithmetic on every import and
raises when the recorded number no longer matches, so a bound cannot move
without the budget moving with it. The two halves convert differently, because
one rule would be wrong about one of them:

| Part | Bound | Converted at |
| --- | --- | --- |
| `title`, `key_points`, `summary` | word counts from `config/`, spent as characters at 12 a word | 1.3 tokens a word, which is what `extract.approx_tokens` already spends the truncation cap at |
| everything else - keys, punctuation, element addresses, closed vocabularies | characters, from the generated schema | one token a character, because a token spans at least one |

Against the committed bounds on 2026-09-10 the widest reply is 11,692
characters: 7,848 of prose, which is 850 tokens, and 3,844 of structure, of
which the visual plan alone is 3,767. **The budget is 4,694 tokens and it is
mostly the picture.**

**What that guarantees, and what it does not.** The structural half is a true
ceiling. The prose half is a sizing: a reply that spent its whole character rail
on twelve-character words would cost more tokens than 1.3 a word. That is
deliberate, and it is why the recovery above exists - the budget is the brake
and the recovery is the seatbelt. A budget large enough to be an unbreakable
ceiling would leave no window for the article it is summarising.

**A budget is also a clock, and this one is close to a bound.** At the 6.01
tokens a second the configured summarizer decodes at on `ubuntu-latest`
(2026-08-23), 4,694 tokens is 13.0 minutes, against a
`models.summarize.inference.request_timeout_minutes` of 22.1 and a
`run.visual_planner_budget_minutes` of 40. So a single reply that ran to the
brake would not trip the request timeout, and three of them would spend the
whole stage budget. The grammar closes the object long before that on every
reply seen so far - the two committed plan fixtures are a fifth and a tenth of
the plan's own ceiling - but the wiring row is where that stops being a
reassurance and starts being something to watch.

**A retry must perturb the input, or it must not happen.** Decoding is
`temperature 0.0` with `seed 0`, so a second call against an identical prompt
returns identical bytes and costs a full decode for them. That is the same
argument the copied-source reject above makes, and it is why a reply cut by the
budget is recovered rather than re-requested.

## The shape is not the whole check

A reply can hold its shape perfectly and still be something we may not publish.
Those failures are refused in `to_summary` after the reply parses, never asked
for in the prompt - a prompt is written in the same channel as an attack and
loses to a better-worded one.

**A copy.** `verbatim_run` measures the longest unbroken stretch our summary
lifted from the article. Above `evaluation.verbatim_reject_ceiling` the item is
refused with `copied_source`. Republishing an article body is a non-goal
(`CLAUDE.md` section 0a), so this is a rule and not a score: the levers that make
a copy less likely - a longer target, a higher source floor - only change the
odds, and a non-goal is not a tuning target.

The check reads `article.text`, which is the text the model was shown. For a
brief that is the whole article. On a truncated item it is less, so a run
measured here can only under-report the copying, which is the safe direction.

It is a reject and not a retry. Decoding is deterministic (`temperature` is 0.0)
and run 33016222069 recorded an identical `output_digest` across all three
repeats of the item that copied, so a second call returns the same words and
costs a second inference. A retry that changed the ask would be a prompt change,
and the attempt budget it would need has no home in `config/` (Rule #6).

The reader sees nothing. The item is absent like any other failed item, and
`state/item-health/` carries the census row that says which code dropped it and
how many words it had.

**An address.** No published word of ours may carry a URL. Above the fence the
sanitizer already replaced every address in the source with `[link]`, so a
summary or a key point holding one is refused with `leaked_address`, and so is
one still holding the `[link]` marker. `sanitize` owns what an address looks
like and this reject reads it rather than writing a second pattern, so one pass
over our own words answers both questions: a marker already there was lifted out
of the fenced source, and a marker that only appears after the pass was a live
address.

Two controls, not one. The sanitizer runs before the model on text it has seen;
this runs after the model on text it wrote. A page can still ask for a beacon,
and the address now has to survive both.

The title takes the other path. It is the one field with a working fallback -
the source's own headline - so an address there drops the title and keeps the
item, the same way a title outside the asked range does. The summary has no
fallback, which is why the same leak there is fatal.

**A restatement is dropped, not refused.** This is the one post-parse check that
removes a part rather than the whole item. A key point that only restates the
summary is a thin line, not a wrong one, so `to_summary` drops that key point and
keeps the item - it degrades, it does not fail (`CLAUDE.md` section 1a).

`restates_summary` is the `verbatim_run` idea pointed at our own summary instead
of the article: the share of a key point's four-word phrases already in the
summary. Above `summarize.key_point_restatement_ceiling` - `0.5` today, a
starting point and not a calibrated threshold (Rule #10) - the key point carries
more of the summary's phrasing than a fact of its own and is dropped. It is a
floor on distinctness and never a word ban: only the overlap ratio counts, so a
key point may reuse the summary's words and still add a fact. Measured 2026-09-07
on the one well-formed reply fixture, its three distinct key points score 0.00,
0.11 and 0.14 while a verbatim slice of the summary scores 1.00, so the ceiling
sits in the wide gap between a new fact and a copy.

The drop never removes the last key point. The published payload requires at
least one, and each band carries its own `key_points_min`, so when every key
point restates the least-restating up to that floor stay and the item still
publishes with fewer key points. The knob lives in `summarize` rather than
`evaluation` because the floor it must respect - the band's `key_points_min` -
lives there too.

The prompt still asks for this - "a key point that restates the summary is a
wasted line" - but a prompt gives the model no definition of "restates" it can
compute, and the restatement rate ran at seven in eight before the check
existed. The deterministic drop is the control; the prompt sentence is the
request it now backs, and tuning that sentence is a measured loop this change did
not open.

## Model compatibility is mechanical

The request sends `chat_template_kwargs.enable_thinking` from
`models.summarize.inference.thinking`. The configured value is false. The pipeline does
not rely on `/nothink` or another instruction in the untrusted user turn.

The control rejects reasoning in either channel:

- a non-empty inline `<think>...</think>` block; or
- non-empty `message.reasoning_content`.

Both are rejected today. `split_thinking` reads every inline block, not the
first. It read only the first until 2026-08-25, and stripped every block
afterwards, so an empty opening block hid a second block that reasoned and
nothing downstream could see it. A guard that asserts an absence has to look
everywhere the thing can be.

The split-channel check matters because llama.cpp can move reasoning out of
`message.content`; reading only content would make a thinking model look
compliant. A new model must pass this live check under its own embedded chat
template. Recorded incumbent completion fixtures prove the parser and do not
prove candidate behaviour.

Prompt-token counts are also model-specific. Every candidate re-tokenizes all
rendered bands and the complete chat-templated request. A count from the
configured model cannot justify context or timing claims for another tokenizer.

The decoder's character rails are **derived from the accept gate**, never pinned:

| Rail | Derived from | Why |
| --- | --- | --- |
| Summary floor | `summary_words_min x 5` | A generation control as much as a check. The decoder reads the floor and keeps writing, so a summary that stops after two sentences is prevented rather than caught. Five is below real English, so a genuine summary at the gate's floor clears it and fails on words if it fails at all. With the 25-word gate, this rail is 125 characters. |
| Summary ceiling | `summary_words_max x 12` | Loose. It only stops a runaway decode. |
| Title ceiling | `title_words_max x 12` | The same loose ceiling. |
| Title floor | none | The floor exists to stop a long field ending early. A headline does not have that failure mode, and a floor applied to one would only pad a good short line into a bad long one. |

Deriving rather than pinning is what stops a widened gate from leaving a rail
behind that quietly keeps enforcing the old one.

**The rail counts characters and the gate counts words.** They are different
instruments and both are load-bearing. Forty short words clear a 168-character
title ceiling and are still not a headline. The word gate in `to_summary` is
what decides publishability, and it is the only rule that can name the real cause
in a failure detail.

## What the prompt asks for, section by section

| Section | What it is for |
| --- | --- |
| **Framing** | Names the task as epistemological, then says in plain words what that means to do: a reader must be able to tell, from the summary alone, how the article knows what it says. |
| **Title** | A new title, written from the body and the headline together, `title_words_min` to `title_words_max` words, with the headline styles it must not adopt named. See below. |
| **Length** | The band's word range, plus the band's `key_points_min` to `key_points_max` key points - one at the brief band, five at the longest. Each key point must add something the summary did not say. |
| **Source form** | The trusted line before the fenced text can say `Source form: abstract`. In that case the prompt tells the model to write "The authors report that..." or equivalent, because an abstract is the authors describing their own work. |
| **Attribution** | Who said a thing, named as the article names it. Never "sources say" when the article named the source, never a source the article did not name, and a figure an organisation reports about itself is marked as its own. |
| **Certainty** | Hedges are protected in both directions. Dropping one turns a claim into a fact; adding one turns a fact into a rumour. A plan, a proposal, a target, a forecast and a result stay apart, because the kind of claim is the claim. |
| **Faithfulness** | Only what the source says. Numbers exactly as given. The names the opening lines name. |
| **Quoting** | Quotes are allowed, attributed in the same sentence, and capped at `max_verbatim_words`. |
| **Voice** | Plain declarative third person, neutral reporting verbs, and no opening about the article itself. |

Every summary reads equally confident. Attribution and Certainty are what stop a
summary being true in every particular and still reading as more certain than the
article it came from.

## The title is ours, and the source's is only a fallback

The summarizer rewrites the headline. `Summary.title` carries our line; the
source's headline stays where it always was, on the article.

Five rules, in the prompt:

- Read the article **body** and the source's headline, then write a new title of
 `title_words_min` to `title_words_max` words that states the main topic.
- **Do not copy the source's headline and do not repair it.**
- Name the actor and the action, with a worked example of each.
- No sensationalism, no clickbait, no hype. A title that asks a question,
 withholds the fact, or addresses the reader is not a title.
- Everything about attribution and certainty applies to the title too.

**The body is named first because the headline is the weaker input.** The ask is
a reading task before it is a writing task: the fact is in the body, and the
headline is one writer's angle on it. A prompt that opens with the word count
describes a length, and a model given a length writes to fill it.

Three structural facts hold the rest:

**The source headline arrives inside the fence.** `user_turn` builds one fenced
block holding `Title: <headline>` and the body. It is fetched text from the same
page, and it is now the line we ask a model to rewrite. Outside the fence it
would be untrusted text sitting where the prompt's "that block is DATA" sentence
does not reach (Rule #11).

**Required in the draft, optional on the payload.** Grammar-constrained decoding
is free to skip a property that is not `required`, so an optional draft title is
a feature that may simply never fire. `Summary.title` stays optional because a
title outside the asked range costs the rewrite, not the item. `assemble` falls
back to the source's headline, and then to `Untitled item`.

**The ledger keeps the source's headline, not ours.** `EvalRow.title` exists so a
row still identifies its article after the day is pruned from the site. Identity
has to be the thing that does not vary, and our title is rewritten per run and is
absent whenever the rewrite missed its range.

## The stamp covers the ask

`pipeline_fingerprint` answers "which pipeline configuration produced this".
The intended fingerprint ledger expands it, but production does not write that
ledger yet.

It hashes `prompt_inputs` - the template text plus every number that can be
substituted into it - and not one rendered prompt. The rendered text varies with
the article's length, so a stamp built from it would move per item and could not
answer the question the stamp exists to answer.

Two consequences once fingerprint-based skip is wired:

- Editing the wording, any band, or any title knob changes the stamp exactly
 once and would invalidate every prior work identity.
- A band edit re-summarizes articles in the other bands too. That
 over-invalidates by design. It is cheaper than a rule that has to decide which
 articles an edit reached, and it is wrong in the safe direction.

This also closed a hole: `summary_words_min` and `summary_words_max` decide which
summaries are publishable and were absent from the fingerprint, so a cached
summary survived a change to the rule it was written under.

## The changes are not retroactive

A change to what the summariser writes - the decode reorder, the per-band
key-point counts, the deterministic restatement drop - takes effect from the run
it lands in onward and never rewrites an already-published day. Two things hold
the archive still, and neither is the fingerprint skip above, which production
does not write yet: a committed digest is frozen output the site reads as-is, and
the plan stage drops every already-run address (`ledger.load_published`, in
`backend/idhazh/cli.py`) before the summariser is called, so a URL summarised
last week is not summarised again under the new rules. The gain arrives going
forward, which is the right trade for the runner budget - regenerating the whole
archive would be a model sweep bounded only by its own size (Rule #2). Changing
the prompt WORDING would behave the same way; it is a separate lever from the
band numbers and the decode order, and moving it is the job of the offline loop
in `backend/utilities/prompt_loop.py`, not a hand edit.

## A rule, not the argument for it

The prompt is instructions to a decoder, not documentation for a person. A
sentence that explains *why* a rule exists reads well and changes nothing the
model emits - it is this page's job, not the prompt's.

One terseness pass removed **183 words and 232 tokens, 22.5%**, and removed no
rule. Every cut fell into one of four classes:

| Class | What it means | Example cut |
| --- | --- | --- |
| **Redundant** | Another line already says it. | "It says what happened", said three times across Title, Length and Voice. Kept once, in Voice. |
| **Decoder-enforced** | The constrained decoder already guarantees it. | "Reply with a single JSON object and nothing else." `request_payload` sets `response_format` to `json_schema` with `strict`, and `parse_draft` strips a fence anyway. |
| **Unactionable** | The model cannot condition on it. | "This range is set by how long this article is." Pipeline mechanics. The model has the range; where it came from is our business. |
| **Prose** | It argues for the rule instead of stating it. | "A quote with no speaker is borrowed text, not a quotation." The rule above it already says to name the speaker. |

Three expensive lines were considered and **kept**, because each does work no
other line does:

- **The worked example** - "Example Grid orders four reactors from Northwind
 Atomics" against "A major move in the nuclear sector". 26 words, and the only
 few-shot signal in the file.
- **The five hedge terms** - "reportedly", "is expected to", "could", "may",
 "according to". Every one is a literal member of the lexicons in
 `backend/idhazh/evals/metrics.py`. The prompt and the alarm share a vocabulary
 on purpose; cutting the list decouples them.
- **"The summary is prose."** - four words that stop a bulleted summary.

**Length is not the measure of a prompt; conditioning is.** A cut is safe when
another line, the decoder, or a metric still carries the behaviour, and a gamble
when nothing does. Both kinds are in the pass above:

| Cut | If it regresses | Would a metric see it |
| --- | --- | --- |
| The title reframe | A topic label instead of an event | **No.** Nothing in `backend/idhazh/evals/metrics.py` scores our title. |
| "Never turn a claim into a fact" | A hedged claim published flat | **Yes.** `hedge_dropped` fires when the source's lead hedged and the summary did not. |
| The quoting justifications | Longer copied runs | **Yes.** `verbatim_run` and `extractiveness`. |
| "Each key point adds something" | Key points restate the summary | **No.** Nothing compares a key point to the summary. |
| The loaded-verb justification | "Slammed" comes back | **No.** No lexicon scores tone. The ban list itself survives verbatim, and it is what does the work. |

**Three of those five have no alarm.** That is the price of the pass, written
down rather than discovered later. Each survives on a sibling line rather than
on a measurement, and a human spot-check is the only thing that would catch the
drift.

**One of the three has now had that spot-check, and the line is not being
obeyed.** Measured 2026-09-02 over twenty items drawn from the two longest
summary bands, ninety key points read one at a time: **78 of 89 clear verdicts
restate a claim the summary already makes**, and thirteen of the twenty items
add nothing at all
([../../archive/measurements-2026-08.md](../../archive/measurements-2026-08.md#whether-an-items-key-points-repeat-its-own-summary-2026-09-02)).
The instruction survives the terseness pass on the same argument as before - it
is one line and the failure it prevents is worse than the failure it allows -
but nobody may now claim the behaviour is intact. Nothing in the pipeline reads
this count, and one hand count is not a gate.

**The same reading found a defect in the summaries themselves, and it is the
larger of the two.** Of the 110 items eligible for that draw, **20 came back
shorter than the word floor of their own band - 18.2 percent**, and 13 of the 20
are in the longest band. The worst is a 3,195-word source in a band asking for
150 to 230 words that produced a 49-word summary, about a third of its floor.
Those band figures are the ladder as it stood on 2026-09-02, not the one above -
that source draws the rung at 2000 today and would be asked for 95 to 160.

**What was done about it, and what was not.** The 2026-09-10 length policy rules
that a summary under its band's floor **publishes** rather than failing, so the
20 items reach the reader marked by nothing. That is a deliberate choice and not
a fix: a thin summary still tells the reader something, and dropping it tells
them nothing at all. What is still missing is the instrument. The decoder floor
in the next section is `absolute_floor_words x 5` characters, which is far below
real English and is there to stop a summary ending after two sentences - it is
not the band's word target, and a summary a third of its band clears it easily.
No eval column scores a summary against its own band either, so the 18.2 percent
is a hand count from one day and cannot be tracked. Read it as a hazard, not as
a rate.

## Cost

**Measured 2026-08-23**, `llama-tokenize` against `Qwen3-8B-Q4_K_M.gguf` (retired incumbent, historical record), LF line endings. Tokenization is deterministic, so the spread is zero. Recorded in
[`../../reference/measurements.md`](../../reference/measurements.md).

| Quantity | Value |
| --- | --- |
| Before the Title section | 653 words / 864 tokens |
| With the Title section | 781 words / 1033 tokens |
| After the terseness pass | **598 words / 801 tokens** |
| Current four-band prompt, including the brief tier | **658 words / 877-879 tokens** |
| Old nominal arithmetic: system prompt + 2500 + 900 | **4279; not a complete request measurement** |

The 877-879 count measures only the rendered system prompt. The old 4279 sum
omits chat-template tokens, source-form text, feed title, fences and generation
suffix, and treats an estimated extraction cap as exact tokenizer output. It is
withdrawn as a context proof.

`fits_context` approximates the 658-word system prompt as 1316 tokens. The
437-token difference against 879 is a system-prompt margin only. Prove context
fit by tokenizing the complete request under the configured model; do not infer
it from this table.

`test_the_biggest_article_the_extractor_hands_over_still_fits` pins the prompt
against the truncation cap. A prompt grows a rule at a time, and one that crowds
out the article does not fail - it quietly drops every long read from the day.

`test_the_biggest_article_the_extractor_hands_over_still_fits` pins the prompt
against the truncation cap. A prompt grows a rule at a time, and one that crowds
out the article does not fail - it quietly drops every long read from the day.

## Design rationale

**Why the numbers moved to config.** Every number the prompt stated was a literal
inside the prompt text, where no schema could see it and nothing checked it
against the range the pipeline accepts. Rule #6 is the rule; the concrete
failure is that the prompt and the gate disagree, and nobody notices for a
month.

**Why the rare word stays.** "Epistemological" is not plain language, and section
0b asks for plain language. It stays because it names the class of error in one
word, and the sentence immediately after it is the instruction in plain English.
The reader of this line is a model choosing between two framings, and the rare
word is the sharper signal. No reader-facing string carries it.

**Why hedges are protected in both directions.** The obvious rule is "keep the
source's hedges". A model told only that will hedge everything, because hedging
is the safe direction under that instruction. Making a firm statement sound
tentative is the same error as making a rumour sound firm, and only one of the
two has an obvious name.

**Why a key point must add something.** Three restatements of the summary are
three lines a reader skips, and they cost decode time on the slowest stage in the
pipeline. That is also what the model does most of the time: seven key points in
eight restate, measured 2026-09-02 on ninety points from twenty long-source
items. The published item does not draw them, so today the cost is decode time
rather than reader time - which is why the reading page refuses to render them
([../../concepts/digest.md](../../concepts/digest.md#the-key-points-stay-off-the-item-and-the-count-is-why)).

**Why the title is rewritten rather than cleaned up.** A repaired clickbait
headline is still the clickbait writer's framing. "A major move in the nuclear
sector" cannot be repaired into "Example Grid orders four reactors from Northwind
Atomics" - the fact was never in it. Repair also gives the model the source's
line as an anchor, which is the thing we are trying to leave behind.

**Why the ask names the body before the word count.** The first version opened
"Write one title of N to M words". That describes a length, and a model given a
length writes to fill it. The fact that makes a title worth reading is in the
body, not in the headline, so the ask now names both inputs and puts the body
first. The word count moved to where it belongs: a constraint on the output,
not the description of the task.

**Why the banned styles are named rather than implied.** "Say what happened" is
satisfied by a question that gestures at what happened. Naming sensationalism,
clickbait, hype, the question headline, the withheld fact and the second person
gives the model six recognisable classes instead of one abstraction. This is the
same reason the loaded verbs in Voice are listed by name.

**Why the title's blind spot is written down.** No metric in
`backend/idhazh/evals/metrics.py` scores our title. `EvalRow.title` is the
source's headline, and `_publishable_title` only checks a word range. The title
is the one line every reader sees and the least measured thing the pipeline
produces. Saying so here is what stops the next person reading the green ledger
as coverage.

**Why a bad title is not a failed item.** A title is the only part of the payload
with a working fallback. The summary has none, which is why the same miss there
is fatal (section 1a, degrade do not fail).

**Why the band-varying numbers were not moved to the prompt tail.** The proposed
reorder depended on a 66.2 s per-item re-prefill estimate. Run `32648218952`
measured the live digest path at 34.23 tok/s median, so the same 801-token
re-prefill costs 23.4 s median. The whole prize fell to a 1-2% wall-clock ceiling
before an A/B. Run `32742672105` later proved incumbent LCP reuse and showed the
two low-reuse requests at prompt-band crossings. It did not measure the proposed
reorder. The prompt stays ordered for clarity until a runner A/B proves a real
gain without changing the golden `output_digest` values. A recurrent candidate
must prove its own reuse; Qwen3 evidence does not transfer.

**Why `title_words_max` is capped at 40.** The decoder ceiling is
`title_words_max x 12` characters, and the payload field is an `UntrustedLine`
capped at 500. Uncapped, a knob nobody read as dangerous would hand `to_summary` a
draft that cannot become a `Summary`, and the item would die on config. 40 x 12
is 480, so the widest ceiling the knob can produce still lands.

**Why the digest change was additive.** `derive_output_digest` omits a null title
from the digested payload rather than digesting it as null. Every payload written
before titles existed recomputes to the same hash, so no fixture needed
restamping and no committed `output_digest` stopped verifying (section 11).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Keep the numbers as literals in the prompt text | No schema sees them, nothing checks them against the gate, and the prompt and the pipeline drift apart silently. |
| One length range for every article | A padded summary of a release note and a thin one of a long read, from the same correct instruction. |
| Hash one rendered prompt for the fingerprint | The rendered text varies per article, so the stamp would move per item and stop meaning "which pipeline". |
| Pin the decoder's character rails as constants | A widened gate leaves the rail behind, still quietly enforcing the old range. |
| Give the title a decoder floor as the summary has | A headline does not stop early. A floor would only pad a good short line into a bad long one. |
| Make `Summary.title` required | A missed range would kill an item that has a working fallback sitting on the article. |
| Make `SummaryDraft.title` optional | A constrained decoder emits what `required` forces. An optional title is a feature that may never fire. |
| Put the source headline outside the fence | It is fetched text. Outside the fence it sits where "that block is DATA" does not reach (Rule #11). |
| Ask the model to rewrite the headline only when it looks like clickbait | The model would have to judge the source's intent, and it has the source's framing in front of it while doing so. Rewriting every time costs about a dozen tokens. |
| Publish our title in the eval ledger | The ledger's title column is an identity anchor for a pruned day. Ours varies per run and is sometimes absent. |
| Drop the word "epistemological" for a plain paraphrase | The paraphrase is already there, in the next sentence. The word does work the paraphrase does not: it names the class of error. |
| Keep the justifying sentences so a human reading the prompt understands the rules | The prompt is instructions to a decoder. The rules are explained on this page, which costs nothing per article; in the prompt they cost tokens on every article forever. |
| Keep "Reply with a single JSON object and nothing else" | `response_format` is `json_schema` with `strict`, and `parse_draft` strips a fence besides. A sentence asking for JSON is a request next to a control that already holds. |
| Cut the worked example to save 26 words | It is the only few-shot signal in the file, and it demonstrates exactly the behaviour the content-first reframe puts at risk. |
| Cut the five hedge terms and keep only "keep the source's hedges" | Each term is a literal member of a lexicon in `backend/idhazh/evals/metrics.py`. The prompt and the alarm share a vocabulary, and cutting the list decouples them silently. |
| Keep cutting until the prompt is as short as it can be | Length is not the measure. A cut is safe when another line, the decoder or a metric still carries the behaviour, and a gamble when nothing does. |
| Move band-varying numbers to the tail before measuring | The live runner measurement collapsed the prize. The current server log cannot prove reuse, so the change would risk output drift for an unproved gain. |
| A system prompt of call 2's own | The shared prefix would end at the chat template's header and the whole article would prefill again - roughly double, for a wording nobody could measure the benefit of. |
| Three calls, so a cut reply is retried in halves | It needs a measured timeout rate first, and there is none. The recovery above costs zero seconds and does not. |
| Temperature jitter on a retry | It breaks the `seed: 0`, `temperature: 0.0` contract. A re-run that is not a re-run makes every other measurement on this page unrepeatable. |
| Pick the output budget and check it against the bounds | A number somebody chose is a number nobody re-derives. It is computed on every import instead, and a bound that moves without it is an import error. |
| Leave a key point unbounded and derive the budget from the rest | Then the derivation has a term with no upper end in it, which is a guess with a table next to it. |
| Bound a key point at the longest one ever published | A `maxLength` is a hard grammar stop. The next slightly longer key point becomes a parse failure for the whole item. |

## See also

- [`../../concepts/pipeline-loop.md`](../../concepts/pipeline-loop.md) - where Summarize sits and what it emits.
- [`throughput.md`](throughput.md) - what a summary costs the model, and why the band sort makes a run look like it degrades.
- [`../../how-to/evaluate-new-summarizer-model.md`](../../how-to/evaluate-new-summarizer-model.md) - the candidate compatibility and tokenizer checks.
- [`../../concepts/evaluation.md`](../../concepts/evaluation.md) - what measures the summary this prompt produces, and the two columns that measure the article.
- [`../../concepts/config.md`](../../concepts/config.md) - what belongs in a knob.
- [`../../concepts/digest.md`](../../concepts/digest.md) - the title as a reader-facing element.
- [`../sources/trust-boundary.md`](../sources/trust-boundary.md) - why article text, including its headline, is data.
- [`../contracts/determinism.md`](../contracts/determinism.md) - the fingerprint this prompt is part of.
- [`../../reference/measurements.md`](../../reference/measurements.md) - the token cost.
- [`../../../.github/agents/andre.agent.md`](../../../.github/agents/andre.agent.md) - the persona who owns prompt strategy.
