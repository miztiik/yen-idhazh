# What gets summarized

**Last Updated**: 2026-11-18

The knobs that decide how much of an article is read, whether it is summarized
at all, and which length ratio a training candidate must clear. Nothing here
asks the model for a length: the truncation cap bounds what the model sees, and
the summary and the headline publish exactly as the model wrote them. What a
knob is, and what is not one, is [../config.md](../config.md).

## What extraction records, and what it refuses

Extraction has three shape and access control groups:

- `extract.prose_sentence_min`, `extract.prose_sentence_words_min`,
 `extract.prose_line_count_min` and `extract.prose_line_ratio_min` decide when
 text carries `not_prose`.
- `extract.boilerplate_ratio_max` decides when sibling-shared lines carry
  `boilerplate`. Nothing supplies the sibling lines, so the ratio divides by an
  empty set and this knob has never changed an outcome. A ledger that fed it
  shipped on 2026-09-17 and was reverted the same day: over a full run it moved
  the signal zero times.
- `extract.paywall_markers` is the fallback when JSON-LD does not declare a
 paywall.

Three enforcement switches default to false: `extract.reject_not_prose`,
`extract.reject_boilerplate` and `extract.reject_too_short`. False means record
the signal and publish, which is Maintainer override O3. True means reject the item.
There were two until 2026-09-17, and the third's absence was an asymmetry nobody
chose rather than a decision anybody took.

**The committed `config/idhazh.json` turns `reject_too_short` on.** The default
stays false, because O3 is about the default and a fresh clone still publishes a
short item. Turning one on is the decision O3 left a curator, not an override of
it. What it costs, measured over the 31 days to 2026-09-24: 196 short items
published, and 159 of them came from three hosts that are now retired. The live
cost is the other 37 - about one card a day out of 343, from 17 feeds, none of
them losing more than 5 over the month. Every one of those bodies held between
35 and 59 words against `extract.min_source_words` of 60, so the card carried a headline and
almost no article. None were on a feed declared `abstract`, so the guard below
spared nothing; it is insurance for a feed nobody has registered yet.

**`reject_too_short` carries a guard the other two do not need: it never rejects
a feed a curator registered as `abstract`.** That feed publishes abstracts
because a person said so, and an abstract is short by definition - rejecting one
would delete a source on the strength of the property it was registered for.
Measured 2026-09-17: at 34 words both forms carry `too_short`, so the declared
form is the only thing that can tell a curator's abstract from a truncated
article. The signal is recorded on the row either way; what the form changes is
the consequence, never the fact. Which feeds declare that form is
[source-lifecycle.md](source-lifecycle.md#a-curator-may-declare-a-feed-publishes-abstracts).

`extract.min_source_words` is the shortest body, in words, that stops carrying
`too_short`. A shorter one is also recorded as `brief` on its article, which
nothing reads. It is a plain number: nothing derives it from another setting. It
counts the **source body**, before `extract.truncation_cap_tokens` cuts it.

## What training reads

`evaluation.corpus_compression_ceiling` retains the existing training cutoff:
a candidate's summary/source word ratio must be strictly below 0.75. Equality
still fails. This does not reject a published summary or measure copied text.
Historical `verbatim_reject_ceiling` configuration reads under the new name,
preserving its value; a current name takes precedence when both are present.

## No length decides what publishes

A reply is published exactly as the model wrote it. The prompt states no length,
nothing trims a reply, nothing fails one for being short or long, and the
decoder's grammar bounds neither the summary nor the headline. A reply ends
early only at the model file's response limit
([../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md#a-reply-is-published-as-the-model-wrote-it)).

The published console draws how long summaries came out as a plain
distribution, per run, with no target to measure it against
([../console-design/what-the-quality-and-source-panels-draw.md](../console-design/what-the-quality-and-source-panels-draw.md)).

## What the prompt states

The one number the summary prompt states is `summarize.max_verbatim_words`, the
longest quotation it allows. It is an instruction to the model, not a measurement
of copied text and not a rejection threshold. Whether the call asks for a plan at
all is `visuals.enabled_kinds`: a pipeline-test case that runs the summary-only
path sets that list empty, and an empty list is what takes the plan fields off the
call's grammar.

## Design rationale

**No length is asked of the model and none is checked.** Replaying one CI run's
66 real replies through the length rules the build then had (2026-11-16, each
article's band estimated from its prompt text): 11 were dropped for passing the
character cap, 38 of the 55 that published were trimmed to a median 47 percent of
their text, and 7 headlines were replaced for falling outside 6 to 14 words. Each
cut deleted words the model wrote, and the reader could not see that anything
was missing. A band nobody asks the model for indicates nothing, so the per-size
bands, the overshoot policy and the title word range were deleted rather than
kept as hints. Rejected: keeping the bands as a line on the console, which would
be a number with no producer behind it.

**One setting answers whether the call plans a picture.** `summarize.asks_for_a_visual_plan`
was a second spelling of `visuals.enabled_kinds`: only the prompt stamp read it, and an
empty kinds list already takes the plan off the grammar by itself. It is gone, and a config
that still spells it is refused by name with a pointer to `visuals.enabled_kinds`, so nobody
keeps a switch that does nothing. The stamp counts the kinds instead
([prompt.md](../../architecture/summarize/prompt.md#the-record-covers-the-ask)).

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../evaluation.md](../evaluation.md) - the confidence bands and the thresholds a summary is scored against.
- [../summary-metrics.md](../summary-metrics.md) - what a column on the eval row means.
- [../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md) - the prompt and what it asks.
- [../../architecture/extraction/](../../architecture/extraction/) - where the signals above are computed.
- [model-file.md](model-file.md) - the window, the response limit and the decode settings, which are per model.
