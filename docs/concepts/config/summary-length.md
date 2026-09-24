# What gets summarized, and at what length

**Last Updated**: 2026-09-23

The knobs that decide how much of an article is read, whether it is summarized
at all, how many words the summary is asked for, and what refuses one for
copying too much. They are one chain of arithmetic rather than a list: the
truncation cap bounds what the model sees, the band floor asks for a length, and
the compression ceiling derives the floor under both. What a knob is, and what
is not one, is [../config.md](../config.md).

## What extraction records, and what it refuses

Extraction has three shape and access control groups:

- `extract.prose_sentence_min`, `extract.prose_sentence_words_min`,
 `extract.prose_line_count_min` and `extract.prose_line_ratio_min` decide when
 text carries `not_prose`.
- `extract.boilerplate_ratio_max` decides when sibling-shared lines carry
  `boilerplate`. Nothing supplies the sibling lines, so the ratio divides by an
  empty set and this knob has never changed an outcome. A store that fed it
  shipped on 2026-09-17 and was reverted the same day: over a full run it moved
  the signal zero times.
- `extract.paywall_markers` is the fallback when JSON-LD does not declare a
 paywall.

Three enforcement switches default to false: `extract.reject_not_prose`,
`extract.reject_boilerplate` and `extract.reject_too_short`. False means record
the signal and publish, which is Owner override O3. True means reject the item.
There were two until 2026-09-17, and the third's absence was an asymmetry nobody
chose rather than a decision anybody took.

**`reject_too_short` carries a guard the other two do not need: it never rejects
a feed a curator registered as `abstract`.** That feed publishes abstracts
because a person said so, and an abstract is short by definition - rejecting one
would delete a source on the strength of the property it was registered for.
Measured 2026-09-17: at 34 words both forms carry `too_short`, so the declared
form is the only thing that can tell a curator's abstract from a truncated
article. The signal is recorded on the row either way; what the form changes is
the consequence, never the fact. Which feeds declare that form is
[source-lifecycle.md](source-lifecycle.md#a-curator-may-declare-a-feed-publishes-abstracts).

`extract.min_source_words` marks the brief tier. It does not reject the item.

## The brief floor is derived, not chosen

`extract.min_source_words` is
`summarize.bands[0].target_words_min / evaluation.brief_compression_ceiling`.
With the defaults, that is `30 / 0.5 = 60`. An `AppConfig` validator refuses a
config where the three values disagree.

`config.summarize.bands` starts with the brief band `{0, 30, 45}`. The next band
starts at 60 words. `summarize.length_policy.absolute_floor_words` is 25, so the
decoder's summary floor is 125 characters. `evaluation.brief_compression_ceiling`
is 0.5; it caps `verbatim_run` for brief items and derives the floor above.
The band a summary is asked for is chosen by the article's length, not by its
quality, so no counterweight threshold reads it.
That lets a brief stop naturally instead of padding toward the old 40-word gate.

`evaluation.verbatim_reject_ceiling` is 0.75, and it is deliberately a different
number from `evaluation.brief_compression_ceiling`. The compression ceiling is a
gate: it reads the scores a run wrote and fails the run when a brief copied too
much. The reject ceiling is a rule inside the summarize stage: above it the item
is refused and never scored at all. Give the two one value and the gate has
nothing left to read, because every item it could have failed was dropped before
it looked - and a gate that stops failing reads exactly like a pipeline that
stopped copying. An `EvaluationConfig` validator refuses any reject ceiling at or
below the gate's, so an operator cannot collapse them by editing one line.

0.75 is a starting point and not a calibrated threshold (Guardrail #10). It is the
midpoint of the empty band that eight brief items left on 2026-08-26 (run
33016222069): seven scored at or below 0.241 and the eighth scored 1.000, so
every value between those two selects the same single item and nothing in the
data prefers one over another. The floor is fixed at 0.5 by the validator above.
Eight items is not a distribution.

Every `min_source_words` in this file - `extract.min_source_words` and each
`summarize.bands[].min_source_words` - counts the **source body**, before
`extract.truncation_cap_tokens` cuts it. One name, one meaning. Reading the top
band off the post-cap count is what left it empty until 2026-08-26, because at
the cap of 2500 committed then that count stopped at `int(2500 / 1.3) = 1923`
words and that band started at 2000
([../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md)).
No rung floor may ever sit above `int(truncation_cap_tokens / 1.3)` - the model
is handed that many words and a rung above it would ask for a summary of text it
never saw.

## The ladder, and the copy of it the console keeps

**The ladder has five rungs, and the count has moved three times.** It gained a
fifth rung at 3000 words on 2026-08-29 and a sixth at 5000 on 2026-09-09, and on
2026-09-10 the two longest collapsed into one that starts at 4000 - so five
again, at different places. The reshape was editorial rather than mechanical:
the rungs above 700 were set by asking what an abstract is worth at each source
length, not by dividing the cut point, and the top of the ladder came down from
230 words to 200. Above 4000 words every article gets the same evidence anyway,
because the cut point hands the model 7,692 words whatever the source holds
([../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md#design-rationale---the-ladder-is-editorial-and-200-words-governs-it)).

**The same change deleted `evaluation.summary_words_min` and
`evaluation.summary_words_max`.** They were a single global range every band's
ask had to fit inside, so the ladder could only ever request what the widest
global window already allowed, and a summary outside that window was thrown
away. Length now belongs to the band that asked for it, and
`summarize.length_policy` holds the five knobs that say what happens when a
reply misses: `overshoot_ratio`, `overshoot_words`, `undershoot_ratio`,
`absolute_floor_words` and `floor_applies_above_source_words`. A config still
carrying the two old keys loads - an `EvaluationConfig` before-validator drops
them - so a payload an earlier run wrote is still readable.

**The published surface keeps a second copy of that ladder, and it drifted.**
`SUMMARIZE_DEFAULTS` in `frontend/src/lib/server/config.ts` is the value the
console falls back to when `config/idhazh.json` cannot be read, and those bands
draw the compression plot's target zone and set its y axis. Until 2026-08-29 it
carried **three** rungs against the real five, and the first of them started at
0 words asking for 50 to 90:

| | `config/idhazh.json` on 2026-08-29 | `SUMMARIZE_DEFAULTS` before 2026-08-29 |
| --- | --- | --- |
| rungs | 5 | 3 |
| first rung | 0 words -> 30-45 | 0 words -> 50-90 |
| brief band | present | **absent** |
| top rung | 3000 words -> 150-230 | 2000 words -> 110-200 |

So under the fallback a 30-word note was asked for 50 to 90 words - more words
than the article holds - and the two longest rungs collapsed into one. It had
never fired, because the file it stands in for is committed and read at build
time, which is exactly why nothing noticed.

**This is the drift the rejected-alternatives table on
[../config.md](../config.md#rejected-alternatives) already forbids**, in
the row that refuses copying config into the published directory because two
copies of one file are free to drift with nothing gating them. The copy is in
code rather than in a published file, so no gate caught it. The rungs were
corrected as of 2026-08-29, went to six on 2026-09-09 and back to five on
2026-09-10, and the copy is now pinned:
`backend/tests/contracts/test_taxonomy_and_prompts.py::test_the_console_fallback_bands_match_the_committed_ladder`
reads the committed bands and the `SUMMARIZE_DEFAULTS` literal and fails when
they disagree, printing both ladders. The guard sits with the writer because a
frontend test cannot import that module without dragging in the SvelteKit
runtime - it reads `node:fs`.

**Whether the fallback should exist at all is still open.** Section 1a of
`CLAUDE.md` says a fresh clone runs on the defaults, so it stays. One question
settles it: does any build ever run with `config/idhazh.json` unreadable? If the
answer is no, `summarizeConfig` should throw rather than guess, and the
defaults go with it - a value pinned to the file it stands in for is a
consolation prize next to not needing the copy.

## What shape a qualification corpus has to come out

`evaluation.qualification_pool_multiple` sizes how wide a qualification shard
casts before it selects. It is a floor and not a cap: a shard whose slice has not
yet offered every length tier keeps walking. Raising it buys fetch seconds and
never model minutes, because the model still sees `corpus_per_shard` articles.

`evaluation.qualification_min_per_band`, `qualification_min_over_cap` and
`qualification_min_brief` say what shape that corpus should come out. They
describe the measuring stick rather than the candidate, so a run that falls short
records the shortfall on its verdict and keeps going - the gate that refuses a
run with too little evidence is `scored_denominator`, which counts what was
actually scored. They were literals in `evals/qualify.py` until 2026-09-18, the
only qualification thresholds that were not config, and the only ones that could
end a run before it wrote anything down.

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../evaluation.md](../evaluation.md) - the bands and thresholds these knobs feed.
- [../summary-metrics.md](../summary-metrics.md) - what a column on the eval row means.
- [../../architecture/summarize/prompt.md](../../architecture/summarize/prompt.md) - the prompt the ladder is asked through.
- [../../architecture/extraction/](../../architecture/extraction/) - where the signals above are computed.
- [model-file.md](model-file.md) - the window and the decode settings, which are per model where the ladder is not.
