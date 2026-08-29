# The summarizer prompt

**Last Updated**: 2026-08-29

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
siblings, and `system_prompt()` substitutes them from `config.summarize` at
render time (Rule #6).

Substitution uses `substitute` and never `safe_substitute`. A renamed knob
raises here. The alternative is rendering the literal `$target_words_max` into a
live system prompt, where a model reads the placeholder as the instruction it
looks like.

## One ask per article length

`config.summarize.bands` holds one length ask per article size, ordered by
`min_source_words`. `band_for()` picks the longest band the article reaches,
unless extraction recorded the item as brief. A brief item always uses band 0.

A release note and a long read asked for the same number of words gives a padded
summary of the first and a thin one of the second.

Band 0 is the brief band: `{0, 30, 45}`. The former first band starts at 60
words and asks for 50 to 90 words. The split is forced by the source floor:
`30 / 0.5 = 60`.

Five rungs, and what a reader gets on each:

| Rung | From | Ask | The item |
| ---: | ---: | --- | --- |
| 0 | 0 | 30-45 | A note. The one fact the post carries, so the reader decides in seconds whether to open it. |
| 1 | 60 | 50-90 | A news report. Who did what, how much, when - carryable into a conversation without opening the source. |
| 2 | 700 | 70-150 | A feature or an analysis. The event, why it matters, the main caveat. |
| 3 | 2000 | 110-200 | A long feature. The event, the evidence, who disputes it, what is still open. |
| 4 | 3000 | 150-230 | An investigation or long read. The distinct things the piece established, named separately, plus the response from whoever it accuses and the qualification it ends on. The one item on the page a reader may finish and treat as read. |

Rung 4 is 2.02 percent of items - 9 of the 445 rows in `state/scores.csv` that
carry a trustworthy length from before the cap, measured 2026-08-29, which is 1
to 4 items a run over four runs of 107 to 117 items.

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

### Design rationale - the ladder tops out at the cut point

**The rung exists because two articles read whole were asked for the same
summary.** At `extract.truncation_cap_tokens` of 5000 the model is handed 3,846
words. A 2,000-word article and a 3,846-word article both arrive whole, and
before this rung both got the identical 110-to-200-word ask: one compressed 10
to 1, the other 19 to 1, for the same 155-word midpoint. The floor is 3000
because 2,923 is the midpoint of that whole-read range and 3000 is the nearest
seam the ledger actually reports.

**Rung 4 is the last rung, and no later rung may sit above the cut point.** An
8,442-word piece and a 3,846-word piece are handed the same 3,846 words, so they
get the same ask and they should. A sixth rung asking 280 words of the
8,442-word piece would pay for text that is not in the fenced block, and the
model would close the gap by elaborating the opening - which reads as
completeness. This is the rule the ladder has to keep, not the number 3000: the
cap moved from 2500 to 5000 on 2026-08-29 and it will move again, so the
assertion reads both sides from `config/` (Rule #6). A test that only checks the
rungs climb passes either way and proves nothing.

**Honesty about a partial read is a sentence, and never a word count.** The
tempting alternative is to ask for *fewer* words when the article was cut. It
tells the reader nothing: they cannot see the article's true length, so a short
summary of a half-read investigation reads as a short article. The instrument is
the sentence the item already carries - "We could only read the first N percent
of this page.", degrading to "We could only read the first part of this page."
when the length before the cut is unknown
([../../concepts/digest.md](../../concepts/digest.md)). Five of the 9 rung-4
items measured on 2026-08-29 are still cut at 3,846 words (4,212; 4,444; 5,314;
8,207; 8,442), so this is the common case on this rung and not the corner.

**The failure this pair is written against.** An investigation puts the response
from whoever it accuses, and the qualification it ends on, in the last third. On
a cut piece the model never saw either. A 230-word summary that reads as
complete and omits the denial is the worst item this pipeline can publish, and
the sentence is what stops it.

**`summarize.key_points_max` stays 5 for every rung.** Seven bullets would suit
an investigation and would be padding on a 700-word analysis, and the knob lives
on `SummarizeConfig` rather than on `SummaryBand`, so it cannot be raised for one
rung without a contract change. The longer prose ask buys the depth instead.

**No existing rung moved.** Rung 2 covers about 30 percent of a day, so re-asking
it would put a measured cost on a third of every run to fix a seam nobody has
measured. Rung 3 across 2,000 to 2,999 words runs 10 to 1 up to 27 to 1, which is
the compression rung 2 already carries at its own top. It was never the broken
one.

## What the fifth rung has not proved yet

Two things are written down here because they are cheap to record now and
expensive to reconstruct later.

**The falsification test, which has not been run.** Summarize the 9 items at
3,000 words and up twice - once at 110-200 and once at 150-230 - and count
**distinct findings**: a fact a reader could act on that the other summary does
not contain. If the longer summary names no more findings on two thirds of them,
the rung buys padding and it should be withdrawn. It is a count, not a score, so
it needs no labels and no grader (`CLAUDE.md` section 0a forbids a model grading
a model). Second observation to take at the same time: if the still-cut pieces
draw every fact from the first 40 percent of what the model read, the extra words
went into elaborating the opening, and those items belong on rung 3.

**A score drop on rung 4 is not a regression.** `hhem` scores a summary against
one window of the article at a time, and a rung-4 summary drawing on both the
opening and the closing of a long piece has no single 900-word window supporting
all of it. This is measured, not feared: over the 117 real evidence pairs of run
`33179908136`, a three-window article scores **0.3986 lower** than the same
article read whole, and a two-window article 0.2178 lower, while the one-window
control reads exactly 0.0000 on 91 of 91
([../../reference/measurements.md](../../reference/measurements.md)). The high
band starts at 0.80 and the medium at 0.50, so a 0.40 drop is wider than the
whole medium band. Every rung-4 article is at least three windows by
construction, because 3,000 words at `evaluation.chunk_words` of 900 cannot be
fewer. **The score is expected to fall while the summary improves.** Read it
against the length bias, or the first run at the new ladder will look like a
quality failure.

## The ask sits inside the gate, and something checks

`config.summarize` is what the prompt requests. `config.evaluation` is what the
pipeline agrees to publish. They are deliberately different numbers: a prompt is
a request and a gate is a rule, and asking for a tighter range than we enforce is
what stops a two-word miss from losing a story.

An `AppConfig` validator checks that every band's ask sits inside the gate. It
lives on `AppConfig` rather than on `SummarizeConfig` because only there are both
blocks visible.

The failure it stops is silent in the worst way: the prompt asks for 300 words,
the model complies, and evaluation drops a correct summary every single run.

## The decoder holds the shape, the prompt does not

The output shape is enforced by grammar-constrained decoding against a schema
generated from `SummaryDraft`, not requested in prose. `SummaryDraft` is closed
to unknown keys, so a planted tool call fails at validation rather than reaching
a payload.

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

The title takes the other route. It is the one field with a working fallback -
the source's own headline - so an address there drops the title and keeps the
item, the same way a title outside the asked range does. The summary has no
fallback, which is why the same leak there is fatal.

## Model compatibility is mechanical

The request sends `chat_template_kwargs.enable_thinking` from
`models.inference.thinking`. The configured value is false. The pipeline does
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
| **Length** | The band's word range, plus `key_points_min` to `key_points_max` key points. Each key point must add something the summary did not say. |
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

It hashes `prompt_inputs()` - the template text plus every number that can be
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
pipeline.

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
