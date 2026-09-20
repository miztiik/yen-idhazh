# Summary Metrics

**Last Updated**: 2026-09-18

What one number about one summary means, and what it cannot see.

Somebody arrives here holding a column name - `self_repetition`, `verbatim_run`,
`extractiveness`, `truncation_flagged` - off `state/scores.csv`, off `EvalRow`,
or off a console panel, and wants the sentence that defines it. That is the whole
question this page answers.

**Faithfulness is not here.** It is the one number with a scorer behind it rather
than an arithmetic definition, and how it is windowed is inseparable from what it
means, so it stays on [evaluation.md](evaluation.md#faithfulness-scored-twice)
with the rest of the judgement. Every column below exists because faithfulness
alone cannot see the failure it names.

**A qualification diagnostic is not here either.** `wording_spread` and the
corpus rows mean nothing without the run that produced them and the gate they
deliberately are not, so they live on
[qualification.md](qualification.md).

## Why faithfulness alone is not enough

Faithfulness measures **consistency with the source, not informativeness**. Two failure modes score beautifully on it:

- *"This article discusses technology."* Perfectly faithful. Says nothing.
- A verbatim quote of the first three paragraphs. Perfectly faithful. Has not summarized anything.

Optimising for faithfulness alone therefore drives the system toward bland copying. It is paired with deterministic counterweights that see what it cannot:

| Counterweight | What it catches |
| --- | --- |
| **Lead coverage** | Whether the names and figures in the source's opening lines survived into the summary. This is the direct instrument for *selective omission* - the thing faithfulness structurally cannot see, because omitting a fact is perfectly consistent with the source. It is anchored on the lead rather than the whole article for a reason given below. A line break is an entity boundary, so a title line cannot glue itself to the first capitalised word of the body. |
| **Unsupported numbers** | A figure the summary asserts that appears nowhere in the full article. Coverage sees an *omitted* number and is structurally blind to an *invented* one, and a wrong figure is the most damaging thing a news summary can carry. |
| **Dropped hedge** | The source said "reportedly" and the summary said it flat. A rumour became a fact. Faithfulness marks this generously, because the entity and the relation are both present - only the uncertainty went missing. |
| **Extractiveness** | How much of the summary is lifted verbatim, as 4-gram overlap plus the longest unbroken copied run. High extractiveness *plus* high faithfulness means copying, not summarizing. |
| **Self-repetition** | How much of the summary is a phrase the summary already used. Every counterweight above reads our summary against the *article*; this one reads it against *itself*. **Recorded, never flagged** - see below. |
| **Compression** | Summary length over source length. **Recorded, never flagged** - see below. |

These are deterministic and cost effectively nothing, which is why they are preferred over an additional model pass. They also run whether or not a faithfulness model is available, which makes them the floor the whole instrument rests on rather than an accessory to it.

## The one column that reads the summary against itself

Every metric above compares our summary to the article, so a summary that says the same clause three times scores clean on all of them. It is the only defect here that reads *better* on every other instrument the worse it gets: a repeated sentence is still perfectly supported by the source, so faithfulness rises, and the repeat is still not copied from the article, so extractiveness does not move.

A model in a loop is what makes it possible, and the temperature decides how a loop ends rather than whether one starts. At temperature zero a model that falls into a loop has no sampling noise to break out of it, so it says the same clause again until the token budget runs out - which is the failure Qwen's own model card names from the other side when it says of thinking mode "DO NOT use greedy decoding, as it can lead to performance degradation and endless repetitions". Every entry pins temperature 0.2 since 2026-09-17, so a loop is likelier to end on its own and this column stays exactly as useful.

**`self_repetition` is the share of the summary's four-word windows that repeat a window it already used.** In plain words: how much of what you are reading, you have already read. Zero means every four-word window in the summary is different, which is what ordinary prose looks like - it is the value a good summary and a bad-but-varied summary both get, so the direction that is bad is *up*.

The window is four words, the same size as extractiveness, because two n-gram sizes in one file are two numbers a reader has to reconcile.

What the numbers mean, measured 2026-08-26 on the fixtures in `backend/tests/test_evals.py`:

| Summary | `self_repetition` | What it is |
| --- | --- | --- |
| Ordinary prose | **0.000** | The zero point. Nothing is said twice. |
| One four-word phrase said three times in 100 words | **0.021** | Two of 97 windows on repeat. A wobble. |
| One six-word clause said three times in 26 words | **0.391** | A loop. This is what the column exists for. |

**It is recorded and never banded.** No threshold reads it and no reader sees it. The moment a band reads the column it becomes a promise to a reader, and re-cutting a band is a separate decision that needs human labels the ledger does not have yet - see [The human labels](evaluation.md#the-human-labels-the-instrument-and-what-it-still-needs).

**It did not move `metrics-3`.** The scorer version folds `METRICS_VERSION` in, and this page requires ten distinct run-days at one `scorer_version` before any threshold moves. A column that no band and no derived column reads changes nothing a row written under `metrics-3` says, so bumping would have spent a banked run-day to record a fact about nothing. `compression` is the precedent: recorded, diagnostic, and not a pass/fail input.

**This is not the ranker's carriage step, and the names used to collide.** `collect.carriage_step` in [config.md](config.md) is a *ranking* knob: `backend/idhazh/rank.py` adds it once to a story more than one of our feeds carried, so it rewards a story that **several sources** carried. That is repetition across the web. `self_repetition` is repetition inside one summary we wrote. They shared a word until 2026-09-13, when the ranking knob was renamed from `collect.repetition_weight` with the multiplier it weighted, and they now share nothing at all.

## Two columns that score the article, not the summary

Everything so far scores our summary - against the article, or against itself. None of it asks what the article was worth. A faithful, well-covered, correctly-hedged summary of an unsourced rumour scores high on all of them and is still an unsourced rumour.

Two columns measure the source itself. Both are marker counts over the article's own words, and both are recorded rather than banded:

| Column | What it counts |
| --- | --- |
| **Evidential density** | Reportative markers - "according to", "reportedly", "sources say". How often the article says *how it knows*. These are the evidence a claim rests on, not a weakness in it. |
| **Speculative density** | Epistemic markers - "may", "could", "expected to", "unconfirmed". The claim itself is unresolved, future, or merely possible. Nobody is being cited. |

**They are read against each other, never alone.** High speculation with high attribution is a well-sourced story about something that has not happened yet, which is legitimate work. High speculation with *low* attribution is the fragile case: claims nobody has been named for.

This is deliberately not a fragility score, and it is not a reader-facing signal. It is two numbers on an operator's row, and what they mean together is a calibration question that needs rows before it can be answered.

**Why these are two columns and not one hedge count.** "Reportedly" and "may" are both hedges, and a summary that drops either has published a rumour as a fact - so `hedge_dropped` wants them in one bucket and still gets them in one bucket. But asked about the *article* they say opposite things. Counting them together produces one number that rises for a well-sourced report and for pure speculation alike, which is a number that means nothing.

**What a lexicon cannot do.** These are surface markers. An article can attribute everything to one anonymous source, or make a firm false claim with no marker at all, and neither is visible here. What the columns catch is the article that hedges constantly and cites nobody, which is a real and common shape. Anything more requires corroboration across sources, which this pipeline does not do yet.

## Two rates that score the run, not a summary

Everything above reads one summary or one article. These two read a day's own
counts, they are free, they need no labels, and they answer a question nothing
else here can: **when published charts fall, which half of the pipeline moved?**

Every article is read for the quantities and dates it states, before the visual
planner sees it ([elements.md](../architecture/extraction/elements.md)). That
reading puts three cells on the item-health census row - whether every span
still cut its own characters, how many facts were kept, and which of three
classes the article's numbers put it in - and
[`backend/idhazh/telemetry/publish/day_metrics.py`](../../backend/idhazh/telemetry/publish/day_metrics.py)
folds them into the day record's `extraction` block, joined against the
published day so a chartable article that never published is not counted as one
the planner passed over.

| Rate | What it is | What a move means |
| --- | --- | --- |
| **`extractable_but_unused_rate`** | published articles that could carry a chart and carry none, over published articles that could carry one | it climbs and the planner is passing over material it was given |
| **`span_integrity_rate`** | articles whose every element span still cut its own characters, over articles the pass ran on | it falls and an article's text moved under a fact we kept, so that article degrades on its own |

**The denominator is the point.** Without it a fall in published charts reads
the same whether the planner stopped choosing charts or the extractor stopped
finding numbers, and those have different fixes. The two are told apart by
reading the rate against the count beside it: the rate moving is the planner,
`chartable` moving is the reading.

**Three classes, and it will say three until the diagram plan lands.**
`chartable` is an article stating at least `visuals.min_chart_points` distinct
quantities that share a unit; `narrative` is an article stating no quantity at
all; `unclassified` is everything between. `comparative` and `processual` are
claims about how an article is written rather than about its numbers, so no
query here can reach them. Anything that reports per class names three and says
so, on the page as well as here - an operator who read three as the whole
taxonomy would read `unclassified` as a defect rather than as a question nobody
has asked yet.

**The threshold is the planner's own knob and not a second one.**
`visuals.min_chart_points` decides both whether a chart is reachable and whether
an article is called chartable. Mint a second knob and the console can call an
article chartable while the planner refuses to draw it, and the rate then
measures two knobs drifting apart rather than measuring the planner.

**Neither rate gates anything, and `span_integrity_rate` is the reporting face
of an invariant that degrades one item.** A day of 500 stories does not fail
because one article's text moved. That is the ruling on
[elements.md](../architecture/extraction/elements.md): break the build on what
our own code can get wrong, degrade the item on what one article's data can.

**`METRICS_VERSION` did not move for either.** No band and no derived column
reads them, so every row written under `metrics-3` still says exactly what it
said - the same reason it did not move for `self_repetition`, `compression` or
`new_fact_rate`.

### Three definitions that look reasonable and are not

Each of these was specified one way, and the arithmetic says otherwise:

- **Coverage over the whole article is a constant.** A long article carries far more named entities than a short summary can hold, so raw survival lands near the same low value for a good summary and a bad one. A metric with no dynamic range is worse than no metric, because it looks like a measurement. Anchoring on the lead restores the range and points it at the defect that matters - journalism puts the who, the what and the how-much in the opening lines, so a summary that drops them dropped the story.
- **A compression *band* is a length detector.** At a fixed output budget, the ratio is dominated by how long the article was. A band on it would flag every short article forever, for a reason that is never about the summary. The ratio is recorded as a diagnostic; the real failures - a headline, or a copy - are detected directly by absolute word bounds.
- **Verbatim overlap must be contiguous.** Measured as a longest common *subsequence*, function words match in order in almost any document, which puts a floor under the score and makes it move with length instead of with copying. Contiguous n-grams and the longest unbroken run do not have that floor.

For a brief item, `verbatim_run > evaluation.brief_compression_ceiling` is the
copying gate the qualification run reads. The default is 0.5. This is the
arithmetic ceiling that makes a 30-word ask possible at a 60-word source floor.
It is not a confidence threshold. The confidence band stays on the faithfulness
axis.

Until 2026-08-29 that same comparison also set `truncation_flagged`. It no
longer does. One column answers one question, and a brief the model copied is a
fact `verbatim_run` and `extractiveness` already carry.

## How often a key point adds a fact

Rows 1 to 3 reordered the key-point decode, moved the count onto the length band,
and dropped a key point that only restated the summary rather than failing the
item. **New-fact rate is the instrument that says whether any of it worked**: the
share of a summary's key points that state a fact the summary prose does not
already carry.

It is the aggregate inverse of `restates_summary`, read at the same distinctness
ceiling `to_summary` drops a key point on (`summarize.key_point_restatement_ceiling`,
0.5). A key point that counts here is exactly one the drop keeps, so the recorded
number and the published item can never disagree about a single line.

**It is reported per length band, never pooled into one figure.** The shortest
band asks for one key point and the longest for five, so a note has little to add
on top of a 40-word summary of a 60-word post and its rate is expected low -
redundancy is structural there, not a prompt defect. Pooling the note's band with
the feature's band would hide the very thing the split exists to show. The console
at `/console/model/` draws one figure a band, over the same window the panels
beside it name.

**The baseline is 11 of 89 key points, 12.4 percent** (section 10.5 of the
2026-09-02 picture disposition), measured over the committed corpus before Rows 1 to 3
took effect. It is a baseline, not a result: the number a later run has to beat,
recomputed from the committed key points and summaries whenever it is quoted
(Guardrail #10). The per-band figure the console draws is a mean of per-item shares
within a band, which is not the pooled key-point rate the baseline quotes; the two
are named apart because a band homogenises item length but does not erase it.

**Nothing acts on it, and that is a standing rule, not a passing convenience.**
Best-of-N against this rate produces key points optimised for lexical difference
from the summary, which is the Goodhart form of this exact metric - the alarm then
stops detecting the thing it was built for. No band reads it, no card sets a tint
from it, and it is never a selection input. It sits with `self_repetition` and the
two densities: measured on every summary, acted on by none.

**This is the lexical reading, and a better one is coming.** A key point that
states the summary's own fact in fresh words scores as new here, because the
measure is four-gram overlap. The element table (plan 08) unlocks the honest
version: a key point whose span-anchored element ids are all already cited by the
summary is a restatement by construction, with no lexical false positive. Until
that ships this is the baseline, and `metrics.py` says so in the function's own
docstring.

**`METRICS_VERSION` did not move for it.** The constant folds into `scorer_version`,
and this page requires ten distinct run-days at one `scorer_version` before any
threshold moves. A column no band and no derived column reads changes nothing a
row written under `metrics-3` says, so bumping would spend a banked run-day to
record a fact about nothing. `self_repetition` and `compression` are the
precedent. Authority: Andre, Fowler.

## The cut flag says the article was cut

`truncation_flagged` is `Article.truncated`: extract found the body longer than
`extract.truncation_cap_tokens` allows and cut it. Nothing else. Extract is the
only stage that cuts, so it is the only stage that knows, and the column carries
that fact rather than inferring it.

**It used to be inferred from the faithfulness gap, and the gap cannot answer
the question.** The rule was `hhem - hhem_full > evaluation.truncation_gap_max`,
defaulting to `0.1`. That reads as sound - a wide gap means the model saw less
than the scorer did - and the chunker makes it false. The score is the best of
overlapping windows, and a cut article's last window is **not** a window of the
whole article, so the two maxima are taken over different premises. The window
sets are not nested and the difference is not a cost.

Measured 2026-08-28 over all 2,683 committed rows of `state/scores.csv`, which
are exact counts over a committed file and so carry no spread:

| What | Count |
| --- | --- |
| Rows genuinely cut - post-cap word count below pre-cap | **22** |
| Of those, rows the old flag fired on | **0** |
| Rows the old flag fired on, in the whole ledger | **1** |
| Words that one row read, of an article that long | **748 of 748** |
| Range of `hhem_delta` over the 22 cut rows | **-0.1235 to +0.0381** |

The threshold it was tested against is `+0.1`, so no cut row could reach it, and
the one row that did fire was never cut - it fired on the brief-copying clause
above. A column that is right about 1 row in 2,683 and wrong about all 22 of the
rows it exists for is not a threshold that needs retuning. Retuning was the
rejected alternative: to catch the widest cut in the ledger the threshold would
have to sit at or below `+0.038`, and at that level it fires on chunk-boundary
noise on articles nobody cut.

**Re-measured 2026-08-30, and the fixed writer now has committed rows to be
judged on.** The ledger holds 3,113 rows and 430 of them are stamped
`2026-08-29T09:00`, written after the change. The same exact counts over the
same committed file:

| What, over the 430 rows on the new side | Count |
| --- | --- |
| Rows genuinely cut | **4** |
| Of those, rows the flag fired on | **4 of 4** |
| Rows where the flag disagrees with the word-count pair | **0 of 430** |
| Rows with no pre-cap length, so no pair to check | **0** |

The 2,683 older rows did not move - still 0 of 22, still the one 748-of-748 row -
because no row was rewritten. So the whole-ledger count of flagged rows is 5, and
5 is the number nobody should quote: 4 of them answer the cut question and 1
answers the old one. That is the version branch earning its keep rather than
being a formality.

**The word-count pair still stays the recommended test**, and the new agreement
does not change that. The flag is right only on rows a reader has to filter for
first; `source_word_count > source_seen_word_count` is right on every row that
carries both, with nothing to remember. What the 430 of 430 buys is confidence
that the two now say the same thing, so a reader who picks either one gets the
same answer on any row written from here.

**`hhem`, `hhem_full` and `hhem_delta` all stay.** They answer what the cut
cost, which is a different question from whether there was a cut, and n=22 is
not a distribution to set a threshold from (Guardrail #10). The knob went with its
last caller in the same commit, so there was never a state where the number
existed and nothing read it.

**A row stamped before `2026-08-29T09:00` is unknown, not false**, and the two
sub-cases are not recoverable from the row. A row before `2026-08-27T20:30`
holds two scores of one text, so its gap could not be non-zero. A row between
the two stamps holds a real gap read by the wrong rule. The published console
therefore counts the column only over rows stamped from `2026-08-28` and prints
absence as absence
([../architecture/publishing/telemetry-series.md](../architecture/publishing/telemetry-series.md)).

**`METRICS_VERSION` did not move.** Nothing in
`backend/idhazh/evals/metrics.py` changed, `truncation_flagged` is not a
`band` input, and no derived column reads it - so every row written under
`metrics-3` still says exactly what it said. Bumping it would restart the
ten-run-day count below to record a change that did not happen to the
counterweights.

## Design rationale

**One column reads the summary against itself (2026-08-26).** Eleven quality columns, and every n-gram machine in `backend/idhazh/evals/metrics.py` intersected the summary's n-grams with the *source's*. Nothing could see a summary that repeated itself, which greedy decoding makes possible and which every other column scores *better* on the worse it gets. Proved on committed fixtures rather than argued: two 26-word summaries of the same article, one saying a clause three times and one saying it once, score exactly equal on `extractiveness` (0.000), `verbatim_run` (0.077) and `coverage` (0.333), and 0.000 against 0.391 on the new one. Authority: Andre's blind-spot finding; nullable and appended, Fowler's layout rule.

**`METRICS_VERSION` did not move for it (2026-08-26).** The constant is folded into `scorer_version`, and a threshold may not move until ten distinct run-days have run at one `scorer_version` ([evaluation.md](evaluation.md#the-human-labels-the-instrument-and-what-it-still-needs)). The count has never reached 10. A column no band and no derived column reads changes nothing that a row written under `metrics-3` says, so bumping would have spent a banked run-day to record a fact about nothing. Authority: Andre.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Bump `METRICS_VERSION` to 4 for `self_repetition` | It sits inside `scorer_version`, so it would restart the ten-run-day count this page requires before any threshold can move - to record a fact no threshold reads. `compression` is the precedent: recorded, diagnostic, not a pass/fail input. | Andre |
| Give `self_repetition` its own n-gram size | Two window sizes in one file are two numbers a reader has to reconcile, and 4 is already the size the extractiveness figure on this page is stated at. | Andre |
| Band `self_repetition`, or alarm on it | The moment a band reads it, it is a promise to a reader and a threshold decision - and no threshold may move until the labels exist. Recorded first, banded later or never. | Andre |
| Detect the loop at generation time and retry at a non-zero temperature | That turns the monitor into the selector, which [evaluation.md](evaluation.md#two-rules-that-are-easy-to-break-by-accident) forbids. It also changes what the digest publishes to fix a fault nobody has counted yet. | Andre |
| Point `verbatim_run` at the summary instead of the source | It is the column that names copying from the article. Repurposing it would delete a measurement to buy a different one and would silently change what every historical row means. | Fowler |
| Put the measurement on the item-health row | Item health records what a stage *did* with an item. This is a property of the words that came out, which is what the eval ledger is. | Fowler |
| Retune `evaluation.truncation_gap_max` down instead of deleting it | Over the 22 cut rows the gap runs -0.1235 to +0.0381, so any cut inside that band fires on chunk-boundary noise rather than on truncation. There is no value that separates the two. | Fowler, corrected by measurement |
| Keep `truncation_flagged` on the gap and add a second column for the cut | The column's name says "was it cut" and its one consumer prints exactly that sentence. Two columns would leave the wrong one wired to the page. | Fowler |
| Add a "the cut cost us" flag now | It needs a threshold with a measured basis. Twenty-two rows is not one, and `hhem_delta` is already recorded for when there are enough. | Fowler |
| Keep the brief-item verbatim clause on the same boolean | `verbatim_run` and `extractiveness` already carry that fact and the console already prints it as "Copied, not rewritten". One predicate per column. | Fowler |
| Move `METRICS_VERSION` to be safe | It is folded into `scorer_version`, so it would restart the ten-run-day count for a column no threshold reads. Nothing in `metrics.py` changed. | Fowler |

## See also

- [evaluation.md](evaluation.md) - how a published summary is judged, and how the judgement is kept honest. Faithfulness, the bands, the human labels and the ledger these columns are written to.
- [qualification.md](qualification.md) - the gates a candidate model must clear. Several read a threshold stated in a column defined here.
- [summary-quality-autotune.md](summary-quality-autotune.md) - the target design in which these thresholds move themselves, with no human in the loop. This page says what a number means; that one says what makes it change.
- [../architecture/publishing/console.md](../architecture/publishing/console.md) - the panels that draw these columns.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #10 (a number carries its hardware, date and spread).
