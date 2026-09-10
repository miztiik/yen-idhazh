# Evaluation

**Last Updated**: 2026-09-08

How a summary is judged, why one number is never enough, and the rule that keeps the measurement honest. This page fixes the vocabulary; the concrete metric implementations, thresholds and the golden-set contents are owned by the plan-doc and the eval subsystem doc, and the tunable bands live in [config.md](config.md).

**Whether archive search finds the right story is a different instrument and lives in [search-quality.md](search-quality.md).** The two share no data, no metric and no config knob, and a person arrives holding one question or the other.

## The problem being solved

Every summary reads equally confident. A wrong one is not visibly different from a right one - that is what makes generated text useful and what makes it dangerous. A reader cannot audit it, and the person who built the pipeline stops reading the output within a week. So the system has to measure its own work on **every item whose inputs changed**, continuously, and the measurement has to be committed rather than recomputed on demand.

That qualifier is the only legitimate way to do less work. The fingerprint
contract defines a future skip for an unchanged item, but production does not
wire the ledger or classifier yet
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).
Do not read missing rows today as proof that an unchanged item was skipped.
Sampling is a different thing entirely, and it is not done - see the rationale
below.

The failure this guards against is not dramatic. It is a slow one: extraction quietly breaks on a site redesign, summaries start describing navigation chrome, and every score stays healthy because the summary is perfectly faithful to the garbage it was given.

## Faithfulness, scored twice

The primary measure is **faithfulness**: does the summary assert things the source actually said? It is scored twice on purpose:

- against the text the model **actually saw** (post-truncation), and
- against the **full article**.

A single score cannot distinguish "the model invented something" from "the model faithfully summarized the half of the article we gave it". The **gap between the two** is the cost of truncation, and it is invisible unless you measure both. A large gap flags the item as a truncation artifact rather than a hallucination - a different defect with a different fix.

### The gap, and the 2,232 rows that never measured it

The work stage carries the sanitized article twice: the cut text it shows the
summarizer, and the whole body it shows the scorer. The whole body stays in the
process that extracted it - `Article` persists only the cut text, and neither
form is ever republished (Rule #1).

That was not true until 2026-08-27. Both the production and the validation
callers passed `article.text` as both inputs, so the two HHEM scores read one
string and the documented gap was zero by construction. Measured over the whole
committed ledger at that date, `hhem_delta` is exactly 0.0 on **2,232 of 2,232
rows** and `hhem` equals `hhem_full` on every one.

**A row stamped before `2026-08-27T20:30` recorded two scores of one text.** On
those rows a zero gap means the gap was never measured, and reading them as
evidence that truncation costs nothing is reading an instrument that was not
plugged in.

The scorer is deterministic, so identical texts are now scored once and the
answer reused. About 97 percent of items are never cut, so most items pay one
pass instead of two.

Evaluator identity is pinned. `HHEM_REVISION` is a full immutable commit, and
`weights_digest` hashes the loaded tensors rather than a model name.
`scorer_version` carries both observations. A scorer that has not loaded cannot
name its weights and fails instead of minting a plausible identity.

### The two source word counts are one counter, before and after the cap

`source_word_count` is `Article.source_word_count`, the words in the extracted
body before `extract.truncation_cap_tokens` cut it. `source_seen_word_count` is
`Article.word_count`, the same counter applied to what survived. The difference
between them is the cut, and nothing else.

**A row stamped before `2026-08-27T20:00` measured something else.** Both cells
came off the post-cap string through two different counters -
`len(_WORD.findall(t))` against `len(t.split)` - so the difference measured
the counters. Over the 2,232 rows written before that stamp the two agree on
287, `source_word_count` is larger on 1,355, and `source_seen_word_count` is
larger on **590**, which is impossible when one string is a cut of the other.
Read as a truncation signal the pair said 87 percent of items were truncated;
counting the rows sitting on the 1,923-word cap says 6.3 percent. The first
number is wrong by a factor of fourteen, and it was quoted inside this project
before anyone checked the impossible direction.

**Two things now stop it happening again.** `EvalRow` refuses a row whose seen
count exceeds its full count, mirroring the rule `Article` already enforces -
the pair could only stay wrong while nothing compared the two cells. And
`source_word_count` is nullable, so a row can say it does not know instead of
naming a number nobody measured.

**The committed rows were rewritten**, by
`backend/utilities/migrate_score_ledger.py`, in the commit that added the rule
(`CLAUDE.md` section 11). It recovers rather than guesses. An article under the
cap **is** the text the model saw - `truncate_to_tokens` returns the body
unchanged, and `Article.word_count` counts that same string - so its full length
equals its recorded seen length exactly, and **2,204 rows got a real number
back**. The **142** rows sitting on the cap were emptied: extract discarded that
body, and copying the seen count into them would have replaced a wrong number
with a different wrong number. Null is the fact; zero would say the article was
empty. Rows are selected by their own `version` stamp, so the **220** rows the
fixed writer had already produced were left alone.

Two readers were taught what an empty cell means in the same commit. The drift
benchmark keeps such a row and steps over it only in the length rule, so its
faithfulness and extractiveness still count. The label queue stopped reading the
column at all - a labeller judges the summary against the premise in front of
them, which is the truncated text, so `LabelRow` carries
`source_seen_word_count` and can never be handed a blank.

### The runtime must refuse, not shift

A llama.cpp server shifts an oversized prompt by default. It drops the middle
and answers about a document it no longer holds. HHEM then scores a faithful
summary of text we never sent as a hallucination, and names the wrong cause -
the same defect this page exists to catch, arriving from the runtime instead of
the extractor. The server therefore runs with `--no-context-shift`, so a prompt
that does not fit is refused, and the item records `context_exceeded` rather
than a score nobody can read
([../architecture/sources/item-health.md](../architecture/sources/item-health.md)).

### The window a score was measured over

An article longer than one window is read in overlapping windows and the score
is the **best** window, never the average. A claim is supported if any part of
the article supports it, and a mean would drive the score down as the article
got longer - which would manufacture a large truncation gap on exactly the
longest articles and invert the flag that exists to catch it.

The geometry is two knobs, `evaluation.chunk_words` (900) and
`evaluation.chunk_overlap_words` (150). They were constants in code until
2026-08-28.

**Neither default moves today.** HHEM-2.1-Open has no maximum input length, so a
wider window is mechanically allowed. What is missing is a reason to pick a
number: **0 of 60 drawn rows carry a human label**, so nothing here can say
whether a wider window scores more truthfully or just differently, and a sweep
would show only that the number moves (Rule #10). Moving it is a measurement
this project cannot yet take, not a tuning nobody got around to.

**Every window is now the full window, the last one included.** Until 2026-08-28
the walk stepped past the end of the article and the final window was whatever
remained. That window was short on **every** premise longer than one window -
3,100 of 3,100 lengths from 901 to 4,000 words, as little as one word and 370
words on average against 900-word rivals. Because the aggregation is a max, a
partial premise competed against full ones on every long article, and it could
win: a stray window holding one supporting sentence and nothing to contradict it
scores high on almost anything. The last window is now anchored to the end of the
article, so it holds the same 900 words every other window does.

Anchoring buys correctness now and time later. At the cap of 2500 committed when
this was written, the cut point was 1,923 words and an article took 3 windows
either way. At 3,846 words it takes 6 windows unanchored and 5 anchored, which is
16.7 percent less scorer work on a full-length item - a saving that arrives when
the cap does. The cap reached 3,846 words on 2026-08-29 and 7,692 words on
2026-09-09, so the saving has arrived and it grows with every move: `hhem` reads
the post-cap text, so its window count doubles with the cap, while `hhem_full`
reads the body before the cut and is unchanged by any of this.

**Anchoring does not restore `hhem_full >= hhem`.** The two window sets are still
not nested: a cut article's last window is not a window of the whole article, so
the two maxima are taken over different premises and the gap can still come out
positive. Anchoring removes the runt as one cause of that. Only re-scoring the
cut items says what is left.

**What this reset cost, stated rather than implied.** `scorer_version` now spells
the geometry as `window=900/150/anchored`, between the instrument's identity and
the thresholds read off it. That is a new string, and the ten-run-day gate below
counts run-days at **one** `scorer_version`, so the count goes back to **zero of
ten**. Measured by `backend/utilities/label_queue.py` on 2026-08-28, immediately
before the change: **3 run-days of 10** (2026-08-26, 2026-08-27, 2026-08-28) over
567 eligible rows. Those 3 days are the price. It is a real cost and a small one:
the gate has never once been met, the longest run at any one scorer is 3 days,
and 0 of the 60 drawn rows is labellable, so nothing that was going to be decided
this week is delayed. The alternative - leaving the geometry out of the string -
is worse, because rows measured over a 900-word premise and rows measured over a
runt would pool silently and nobody could tell them apart afterwards.

`METRICS_VERSION` did **not** move, and stays at `3`. It names the deterministic
counterweights in `backend/idhazh/evals/metrics.py`, and none of their
definitions changed when the chunker did. Bumping it would assert a change that
did not happen.

### Slicing costs a long article 0.40 of its score, and the direction is now measured

The window is a knob, and until 2026-08-29 nobody knew which way it pushed. Two
biases ride on the number of windows and they pull opposite ways: the
aggregation is a max, so more windows is more chances at a high draw, and no
single window holds the evidence for a summary that draws on the article's
opening and its closing, so every window is marked down for the half it cannot
see. **The mark-down wins, and it is not close.**

**Measured 2026-08-29** over the 117 (premise, summary) pairs the 2026-08-28
production run scored, each pair scored twice and nothing else varied - once at
today's `900/150/anchored` geometry, once at a 1,923-word window that holds every
premise whole. Taken by `backend/utilities/grader_length_bias.py`; the figures,
the hardware and the spread are in
[../archive/measurements-2026-08.md](../archive/measurements-2026-08.md#which-way-the-graders-length-bias-runs).

| Windows the article takes today | Items | Today's score minus the whole-article score |
| --- | ---: | ---: |
| 1 | 91 | **exactly 0.0000** |
| 2 | 16 | **-0.2178** |
| 3 | 10 | **-0.3986** |

**A three-window article scores 0.40 lower than the same article read whole.**
The bands start at 0.80 and 0.50, so 0.40 is wider than the entire medium band -
the geometry alone can carry one item from high to low, and it does it to the
longest articles only. The best-of-N effect is real and tiny: the largest
positive difference anywhere is **+0.0353**, against a largest negative of
**-0.8783**, so it is 25 times smaller than the thing it is fighting.

**This is the Editor's warning, now a number rather than a worry.** A summary
that draws on more of an article scores *lower* under this geometry while being
a better summary. A score that drops when a summary improves is not a regression
to chase.

**The number that says the comparison is sound is the 0.0000.** An article short
enough to be one window under both geometries is scored over the identical text
twice, and the scorer is deterministic, so its difference must be exactly zero -
91 of 91 were. Whitespace was ruled out separately: the chunker re-joins windows
on single spaces while the whole-article pass reads the premise as it stands, and
scoring 5 at-cap premises both ways moved the number by 0.000000 every time.

**No default moves, and this measurement does not say one should.** It says the
instrument moves with slicing; it does not say the whole-article reading is the
truer one. That still needs the human labels this page has been waiting on -
**0 of 60**. What has changed is that `evaluation.chunk_words` can no longer be
called a neutral number nobody needs to look at.

**What it does settle is the cost.** A single 1,923-word pass costs **less** than
today's two or three 900-word passes, not more: 4.278 s against 4.815 s a pass on
the hardware in the reference page. Whichever way the label queue eventually
points, a one-slice window is affordable.

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

Greedy decoding is what makes it possible. At temperature zero a model that falls into a loop has no sampling noise to break out of it, so it says the same clause again until the token budget runs out.

**`self_repetition` is the share of the summary's four-word windows that repeat a window it already used.** In plain words: how much of what you are reading, you have already read. Zero means every four-word window in the summary is different, which is what ordinary prose looks like - it is the value a good summary and a bad-but-varied summary both get, so the direction that is bad is *up*.

The window is four words, the same size as extractiveness, because two n-gram sizes in one file are two numbers a reader has to reconcile.

What the numbers mean, measured 2026-08-26 on the fixtures in `backend/tests/test_evals.py`:

| Summary | `self_repetition` | What it is |
| --- | --- | --- |
| Ordinary prose | **0.000** | The zero point. Nothing is said twice. |
| One four-word phrase said three times in 100 words | **0.021** | Two of 97 windows on repeat. A wobble. |
| One six-word clause said three times in 26 words | **0.391** | A loop. This is what the column exists for. |

**It is recorded and never banded.** No threshold reads it and no reader sees it. The moment a band reads the column it becomes a promise to a reader, and re-cutting a band is a separate decision that needs human labels the ledger does not have yet - see [The human labels](#the-human-labels-the-instrument-and-what-it-still-needs).

**It did not move `metrics-3`.** The scorer version folds `METRICS_VERSION` in, and this page requires ten distinct run-days at one `scorer_version` before any threshold moves. A column that no band and no derived column reads changes nothing a row written under `metrics-3` says, so bumping would have spent a banked run-day to record a fact about nothing. `compression` is the precedent: recorded, diagnostic, and not a pass/fail input.

**This is not the ranker's `repetition_weight`, and the names collide.** `collect.repetition_weight` in [config.md](config.md) is a *ranking* knob: `backend/idhazh/rank.py` multiplies a story's authority by `1 + repetition_weight * (carriers - 1)`, so it rewards a story that **several sources** carried. That is repetition across the web. `self_repetition` is repetition inside one summary we wrote. They share a word and nothing else.

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
[`backend/idhazh/publish_day_metrics.py`](../../backend/idhazh/publish_day_metrics.py)
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
visual-planner disposition), measured over the committed corpus before Rows 1 to 3
took effect. It is a baseline, not a result: the number a later run has to beat,
recomputed from the committed key points and summaries whenever it is quoted
(Rule #10). The per-band figure the console draws is a mean of per-item shares
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
not a distribution to set a threshold from (Rule #10). The knob went with its
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

## Two rules that are easy to break by accident

**1. The metric that selects can no longer alarm.** It is tempting to generate several candidate summaries and keep the one that scores best. Doing so destroys the score's value as a monitor: once it is the selector, it can no longer tell you that outputs are getting worse, because it is being optimised against by construction. This is Goodhart's law with a concrete cost. The selector and the alarm stay separate.

**2. The model does not grade the model.** LLM-as-judge is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a). A judge built from the same technology shares the failure modes of the thing it is judging, and agrees with it for exactly the reasons you needed an independent check. The substitute is a purpose-built scorer, plus the deterministic counterweights above, plus a small recurring human spot-check whose only job is to keep the automated scores calibrated.

Discouragement is not a control, so four things make it structurally hard rather than merely forbidden. `LabelRow` has no author field a model could fill and no nullable one it could leave blank - `labeller` is required and checked against `evaluation.labellers`. The writer is a human-paced CLI with no `--from-file`, no `--model` and no stdin path, so generating labels from a model means writing a second writer in a diff in a pull request. `seconds_spent` has a floor. And the draw module may not import `idhazh.llm` or the scorer, asserted by a test, so the loop cannot close on itself after a refactor by somebody who never read this paragraph.

Not to be done: seeding the queue with model pre-labels for a human to confirm. Confirmation is anchoring, and it turns an independent measurement into an expensive agreement rate with the model - LLM-as-judge with a rubber stamp.

### Current qualification-gate implementation gap

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
summary text is unset. `cli._observe` sets both `ok` and `schema_valid` from that
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

## The prompt loop: the judge proposes, the scorers dispose

The summariser prompt used to be argued in prose and never measured, so every
change to it was a matter of taste - the exact thing rule 2 above warns against,
seen from the other side. The offline prompt loop
([../../backend/utilities/prompt_loop.py](../../backend/utilities/prompt_loop.py))
turns the argument into a measurement, and it is built so that neither of the two
rules is broken.

It runs write-critique-revise, bounded by `finetune.prompt_iterations`. A model
judge and the Editor rubric
([../../backend/utilities/prompt_loop_rubric.md](../../backend/utilities/prompt_loop_rubric.md))
**propose** a revised prompt. The deterministic, model-free scorers above
**dispose**: a candidate replaces the incumbent only when it beats it, over a
frozen committed article set, on `unsupported_numbers`, `lead_missing`,
`hedge_dropped` and `verbatim_run`. The gate is a Pareto beat - no worse on every
target, strictly better on at least one - not a weighted sum and not an optimiser.
The judge's preference is recorded and promotes nothing.

That is how it honours both rules at once. **Rule 2** - the model does not grade
the model - takes a narrow, offline-only exception: the judge authors a
maintenance artefact, never a verdict on a published summary or visual, and
selects nothing that publishes ([../../CLAUDE.md](../../CLAUDE.md) section 0a).
**Rule 1** - the metric that selects can no longer alarm - is why the gate reads
those four defect rates and not the new-fact rate. New-fact rate is recorded for
every candidate, because a run's scores are its evidence, but acting on it is the
Goodhart form its own section forbids, so it steers nothing here either.

Nothing the loop produces reaches a reader. It runs on a developer machine or a
manual dispatch, never in the daily pipeline, and it never edits the live prompt
itself: promoting a winner into `backend/idhazh/prompts/summarize.txt` is a human
act, taken after reading the committed scores. The committed artefacts are the
winning prompt, the rubric, the scores of every candidate and the seed - never the
transcripts.

The load-bearing guard is a test, not a sentence. When the model judge prefers a
candidate the deterministic scorers refuse, the incumbent stands
([../../backend/tests/test_prompt_loop.py](../../backend/tests/test_prompt_loop.py)).
A disagreement between the judge and the scorers is always a stop, never a
promotion - which is the whole reason a model is allowed to propose at all.

## Bands, not raw numbers

Scores are bucketed into a small number of confidence bands, and the band - not the number - is what drives behaviour: what gets retried, what publishes with a visible low-confidence marker, and what a reader sees. Bands are tunable ([config.md](config.md)) and are re-calibrated against the human spot-checks rather than being fixed by taste.

The absolute summary gate starts at
`summarize.length_policy.absolute_floor_words = 25`. That lets the brief band ask
for 30 to 45 words without the decoder padding a short source to the old floor.

A low-confidence item still publishes, marked. Hiding it would make the digest look better than it is, which is the opposite of the point.

There is one band function. It reads the faithfulness score when one exists, plus the deterministic counterweights that are written to the eval row. A row with no faithfulness score can never claim `high`; it starts at `medium` unless it asserts an unsupported number.

The counterweights have different force:

| Counterweight | Band effect |
| --- | --- |
| Unsupported numbers | Force `low`. A wrong figure is a direct false claim. |
| Lead coverage below `evaluation.lead_coverage_min` | Cap `high` at `medium`. The summary missed the lead, but it may still match what it did say. |
| Dropped hedge | Cap `high` at `medium`. The summary flattened uncertainty, but that defect does not erase every faithful sentence. |

The cap is deliberate. A faithful summary that missed the lead deserves less
confidence, not no confidence. Re-cutting the `high` and `medium` thresholds is
a separate Level 5 decision. The current rows have no human labels, so they do
not supply an error rate for any cut.

Historical `band` cells are a time-of-write record, not a live distribution.
Rows written before the counterweight caps may record `high` even though today's
`band` would cap them at `medium`. Re-band the ledger with the current function
before using the bands as a distribution. Measured 2026-08-24 on the committed
`state/scores.csv` at 447 rows: recorded 63.8 / 18.1 / 18.1, re-banded
57.7 / 24.2 / 18.1. Twenty-seven rows move, all of them written before the caps
landed - 11 on lead coverage, 11 on a dropped hedge, 5 on both.

## Which sources the checker doubts

A doubted summary is one the checker stopped on for any of three reasons: the
band came out `low`, the summary asserted a figure the article never gave, or it
turned the article's hedge into a fact. The Summaries route ranks sources by how
many of their summaries carry at least one of the three, over the window in
force, capped at `console.doubt_rows`.

**Three counts, never a blend.** The three have different causes and different
fixes - a low band is the grader's own confidence, an unsupported number is a
fabrication, and a dropped hedge is a certainty the article did not have - so the
row prints all three beside the count and the page never adds them into a score.
A summary can carry more than one, so the three do not sum to the row's own
count, which is also why they are never stacked into a bar. `doubted` in
[frontend/src/lib/server/model-work.ts](../../frontend/src/lib/server/model-work.ts)
is the one predicate; the model-change panel below reads the same one, so the
list and the panel cannot disagree about what a doubt is.

**The order is the count, and the page says so.** A share sort puts a source
with 2 doubted of 3 above one with 40 of 400, and it is the forty that reached a
reader. Every row carries its own denominator for the same reason, and a source
under `console.min_attempts_for_rate` summaries prints no share at all - a share
over three summaries is the second summary. A tie goes to the source's own name:
a second criterion would be a second ranking nobody declared.

**No source is tinted.** The grader has a measured length bias (see the slicing
section above), so a colour on a publisher's row would publish a verdict off an
instrument still being calibrated. The order is the ranking; nothing else on the
row is a judgement.

**The source is a join, and the join is printed when it fails.** The eval ledger
records the address and the title and never the feed, so a summary reaches a
source through `url_key` on `state/item-health/<YYYY-MM>.csv`. Measured
2026-09-01 over the committed ledgers, 3,959 of 4,110 scored rows join, and every
day from 2026-08-24 joins at 100 percent - the 151 that do not are the two oldest
scored days, written before item-health carried them. Rows that do not join are
counted in a sentence under the list rather than dropped, because a denominator
that quietly shrinks is how a rate starts lying.

Measured 2026-09-01 over a thirty-day window on the committed ledger: 123 sources
scored something, 112 of them carry at least one doubt, 1,047 summaries of 3,959
were doubted, and the worst ten hold 266 of those. The tail is sources with a
single doubt in a month, which is what the cap exists to leave out.

## The human labels: the instrument, and what it still needs

The thresholds are a promise to a reader and nothing has measured their error
rate. `state/labels.csv` is where that measurement would live, and
`backend/utilities/label_queue.py` is how a person fills it.

**The draw.** Six rows from each `hhem` decile, deterministic by hash over the
address, the inputs, the words, the scorer and the draw id. Sixty rows. Uniform
across deciles rather than crowded at the cuts, because the first question is a
level question - what does `high` mean at all - and a boundary-weighted draw
would speak about 0.75 to 0.85 and stay silent about the rest of the ledger. A
uniform draw re-weights to the live distribution; the reverse is not available.

**A label is a fact about a (summary, article) pair, not about a score.**
`output_digest` pins the exact words judged. The scorer's number at draw time is
recorded and hidden - recorded so an analysis can refuse to mix instruments,
hidden so it cannot anchor the labeller. When the scorer moves, the label stays
valid as a label and stops being evidence about that scorer's numbers, so the
read side re-joins on `output_digest` and takes the live score from this ledger.

**Hidden from the labeller, without exception:** `hhem`, `hhem_full`,
`hhem_delta`, the band, the band reason, every counterweight, `model_id`,
`attempt`, `pipeline_fingerprint`, `scorer_version`, any other row's label, the
running tally, and the row's decile. The queue is never ordered by score - that
would leak the gradient off the sequence.

**Shown:** our summary as published, the source's own headline, the date, the
link, and the extracted article text. The extracted text is the authority for the
verdict; the link exists to decide whether that text is the article at all. URL
alone would have the labeller judging a page that has since changed. Extracted
text alone would hide the case where the extractor grabbed navigation chrome,
which is what the `not_the_article` tag is for.

**One binary verdict plus one closed tag.** Every tag names a defect with a
different fix, so two tags leading to one code change would be one tag.
`invented_fact`, `wrong_number`, `overstated`, `wrong_subject`,
`not_the_article`, `unjudgeable`, and `none` for a supported summary. Three of
them mirror a counterweight the pipeline already computes, which buys that
counterweight's own precision and recall out of the same sixty labels.

**Those three counterweights are copied onto the label row from 2026-09-03, and
that is a change of policy rather than of shape.** The read side used to re-join
`unsupported_numbers`, `hedge_dropped` and `extraction_suspect` from
`state/scores/` on `output_digest`, and that ledger now keeps
`observability.scores_full_grain_months` months of item-level rows before a month
becomes a summary. A label outlives its source row, so a re-join is a promise the
ledger stops being able to keep - and what would be lost is exactly the precision
and recall the sixty labels are drawn to buy. `LabelRow` carries the three as
nullable columns filled by the queue; null means a row written before this stamp,
which is re-joined from the ledger while its month is still there, and never
means "the counterweight was read and did not fire". Nothing else moved: there is
still nowhere on this row to put a machine verdict, and `model_id` is still
absent by name. Authority: Andre.

Short-source rows stay in the pool. They are extraction failures rather than
summary defects, and dropping them would bias the sample toward well-extracted
items - the sampling error this whole page argues against. `unjudgeable` carries
them, and the rate is reported with and without.

### The label queue: three repairs, and what they left

The queue could not be used by a person until 2026-08-27. Three things were
wrong with it, and all three are now fixed.

**It never showed the labeller the article.** `state/scores.csv` carries no
summary text and no source text, so `label_queue.py` printed a missing-summary
fallback on every row. That fallback was not a degradation - it was the only
branch that could ever run, because `summary` is not a column in that file at
all. The run now writes the exact premise the scorer read, plus the summary, to
`backend/var/evidence/<date>/`, and records a `source_digest` on the eval row.
The CLI shows both texts and refuses any row whose text does not match its
recorded digest, so a labeller cannot judge text the scorer did not read. A row
scored before that column existed is marked not labellable rather than guessed
at, and all 2,232 rows written before 2026-08-27 are in that state.

**The draw leaked the hidden score gradient through its order.** `draw`
returned rows in sequential HHEM-decile blocks. The number was hidden and the
stratum was not. It now returns one global `label_id` sort. `label_id` is
already a sha256 over the address, the inputs, the words, the instrument and the
draw, so the shuffle needs no seed and stays reproducible - two labellers can
compare notes by position. **The strata are how rows are chosen, never how they
are ordered.** Measured over the 38 rows at `draw_id=d1`: 9 runs of equal decile
before, 28 after.

**A global hash shuffle does not balance a prefix, and the first version of this
rule said it did.** Over those same 38 rows the first ten deciles run 9, 9, 8, 9,
9, 9, 5, 8, 9, 7. Balance is a property in expectation, not per draw. Stopping
early gives a roughly balanced sample, not a guaranteed one, and a partial draw
may not be reported as stratified.

**One draw is one `scorer_version`. The pipeline is a covariate the draw reports,
not a filter it applies (owner decision, 2026-08-27).** `eligible`, `draw`
and `run_days` require the scorer with no default, because the cuts being
calibrated live inside that string: a row read by a different instrument answers
a different question. `pipeline_fingerprint` is optional, and omitting it is the
normal case. `strata` splits the drawn rows by producer, and the tool prints
that split with any stratum under `evaluation.label_min_stratum_rows` marked too
thin to cut on.

Requiring both was unreachable rather than strict. The stamp digests seventeen
inputs, so a reworded prompt, a llama.cpp rebuild or a sanitizer fix reset the
count to zero, and no pair has ever held for more than three consecutive
run-days. The trade is stated rather than hidden: **a rate read off a pooled
draw is a prior with wide bounds, never a calibration.** Report it split by
stratum. The tool says so on any draw carrying more than one producer, and it
refuses to let the split go unprinted. An empty pool still exits non-zero and
prints every pair in the ledger with its rows and dates. Article bodies remain
local and uncommitted.

**The exact remaining requirement**, checked against the committed ledger and
current code on 2026-08-28. These are exact counts over committed files rather
than a timing, so there is no spread: the same commit gives the same numbers on
any machine.

| What | Have | Need |
| --- | --- | --- |
| Labels | **0** | 60 |
| Distinct run-days at the current `scorer_version` | **2** (`2026-08-26`, `2026-08-27`) | 10 |
| Longest run of consecutive run-days at any one pair, ever reached | **3** (`2026-08-24` to `2026-08-26`) | 10 |
| Eligible rows at that scorer | 450 | not the constraint |
| Rows the draw can fill | **60 of 60**, no decile short | 60 |

The current scorer is
`hhem-2.1-open@8e4a2e6e;weights-841b70e0;metrics-3;bands=0.80/0.50;lead=0.30`.
Two producers wrote those rows: `6a23e277` (the configured Qwen3.5-9B, 48 of the
60 drawn) and `f0d4ecc7` (12 drawn, under the floor and marked). Under the old
rule the same ledger filled 32 of 60 with seven deciles short, which is the
measured cost of the pair requirement. The band
values sit **inside** the scorer version string, so moving a threshold also
mints a new scorer version and restarts the count. That is correct, and it is
why a cut cannot move halfway through a collection.

Read the second row and the third one together before reading the shortfall as
patience. Ten is not ten days away. No pair in the ledger's whole history has
ever held for more than three consecutive run-days, so the gate has never once
been met. What sends the count back to zero, how often it has gone back, and
what that costs are in [Design rationale](search-quality.md#design-rationale) below.

**Nothing here may move a threshold.** The queue is usable now; the labels are
not collected and the run-days are not banked. Until both counts are met, any
re-cut is a number chosen so a chart looks humbler.

## The band says what is missing, not how good the item is

A band on its own is a grade. `medium` used to print "Mostly matches the source",
which tells a reader an item is worse without telling them what to look for when
they click through - the only thing they can actually do about it. Both things
that cap an item at `medium` were already computed, and neither reached the page.

One function now returns the band **and** the one reason that explains it, so a
page can never show a band decided by one code path next to a reason decided by
another. The reason is a closed identifier on the published item; the sentence a
reader sees is copy owned by the site, and can be rewritten without a schema
change.

| Reason | What it means |
| --- | --- |
| `unsupported_number` | The summary asserts a figure that appears nowhere in the article. Forces `low`. |
| `not_scored` | No faithfulness score exists, so the item cannot claim the top band. |
| `lead_missing` | The names and figures in the article's opening did not survive. |
| `hedge_dropped` | The article hedged and the summary asserted. |
| `faithfulness` | The faithfulness score itself put the item where it is. |

A `high` item carries no reason. There is nothing to explain, and copy about the
absence of a problem is ink a reader cannot act on.

When both counterweights fail together - 5 of the 27 re-banded rows - the missing
lead is named. Dropped facts are the larger loss: a flattened hedge changes how a
sentence reads, and a missing lead means the story's who, what and how-much never
arrived.

### The reason lives on the published item, not in the score ledger

The console plots these five since 2026-09-05, and the panel had to read them
from the committed day payloads under `frontend/public/digest/`. **`band_reason`
is not a column of `state/scores/`.** The ledger's 35 columns carry the inputs
the reason is decided from - `hhem`, `coverage`, `unsupported_numbers`,
`hedge_dropped` - and the band, and no reason. `verdict` decides it,
`assemble.build_day` writes it onto the item, and that is the only place on disk
it exists.

Re-deriving it from the ledger's inputs was the rejected alternative. It would
put a second copy of `verdict` in a second language, and the day the two
disagree the console is wrong about the item a reader was shown - which is the
one failure this instrument exists to prevent.

**Each item carries at most one reason**, because `verdict` returns exactly
one. That is what lets the five be added: a stacked column of the five is the
count of summaries the checker wrote a reason on, with nothing counted twice.

### What the five reasons look like today

Measured 2026-09-05 over all 16 committed day payloads, 6,633 published
summaries. Exact counts over committed files, so there is no spread.

| Reason | Summaries | Share of published |
| --- | ---: | ---: |
| none - the item reached `high` | 4,124 | 62.2% |
| `faithfulness` | 1,312 | 19.8% |
| `hedge_dropped` | 533 | 8.0% |
| `lead_missing` | 453 | 6.8% |
| `unsupported_number` | 211 | 3.2% |
| `not_scored` | **0** | **0%** |

**One summary in five is doubted because it does not line up with the article,
and that is the largest single fault by a factor of two and a half.** The bands
behind it are `high` 3,755, `medium` 1,817 and `low` 1,061.

Two of those rows are worth reading twice.

**`not_scored` has never fired.** It is drawn when no faithfulness score exists,
and the scorer has run on every production item so far. The panel still declares
it, and names it in a sentence under the plot rather than drawing an invisible
line - a reader cannot otherwise tell a fault that never happened from one nobody
looked for. The day the scorer is switched off, the line appears by itself.

**`high` carries a reason on 0 of 3,755 items**, which is the rule above holding
in the committed record rather than only in the function.

### 369 summaries are doubted with no reason, and every one predates the field

The five reasons total 2,509 while `medium` and `low` together total 2,878, so
**369 doubtful summaries name nothing**. Measured per day, all 369 sit on three
days: 2026-08-21 (4 of its 4 doubtful summaries), 2026-08-23 (52) and 2026-08-24
(313). Every day from 2026-08-25 onward has **zero**. The two oldest days do not
carry the `band_reason` key at all, and the next two carry it null on every item
- the field was added to `DigestItem` after they were published.

So the gap is a record we did not keep, not a reason the checker failed to give.
The console says exactly that, in the panel, with the count: a column missing
them is short by that much rather than clean. Reading a short column there as a
quiet day is the same mistake as reading a zero as an absence, and this page has
made that one before - see the 2,232 rows above that never measured the
truncation gap.

**Nothing is backfilled.** The band was written by a run that had already
decided the reason and thrown it away, so recomputing one now would mean
re-scoring those 369 items against today's scorer and stamping the answer onto a
day another scorer banded. That publishes a number nobody measured on those items
(Rule #10). Three days aging out of the widest console window costs less.

## Per-item scores cannot see drift

Per-item scores measure variance *within a day*. Drift is a movement *across months*: the model runtime changed, a source redesigned its pages, a prompt was edited. Those are invisible in single-item scores and require a second instrument - a fixed set re-run on a schedule, producing a dated row, with alert thresholds on the aggregate.

Two design consequences:

- **Every drift row is version-stamped** with the runtime build, the model file hash and the scorer version. A deterministic output can change because the runtime changed, not because the model did, and a benchmark that cannot tell those apart raises false alarms.
- **The fixed set is refreshed on a schedule.** A frozen golden set stops representing the live corpus and quietly becomes a museum.

A drift detector that has never fired has not been shown to work; it is tested by replaying the set against a deliberately degraded input and confirming the alert fires.

### A review that compared nothing is not a clean review

An empty finding list can mean either no detected change or no comparison.
The workflow calls `drift.report`, which reports the coverage as well as the
findings. An absent ledger, a window below `drift.min_window_rows`, or no
eligible domain metric returns a failing exit code. A partial review names
every skipped comparison and never counts it as healthy.

The scheduled review uses seven completed UTC days and the preceding 28 days.
Today and future dates are excluded. `read_windows` derives the month paths
from those dates instead of walking the whole ledger directory. Malformed
in-window rows fail with their shard and row number; they are not silently
dropped. Missing metric cells stay unknown and are counted within each window.

### Comparable domain samples

Each domain and each metric must have `drift.min_domain_rows` distinct
measured articles on both sides. The default is 20, with a schema minimum of
two. This is a provisional sample floor, not a measured confidence level.
One busy domain cannot supply another domain's missing evidence. Repeated
observations of an article count once, by `url_key`, or by its URL when the key
is absent. The latest row that measured the required metric wins; timestamp
ties keep the first row.

Source length uses every known pre-cap length, including rows without a
faithfulness score. Copying and the combined length/faithfulness warning need
matching `model_id`, `scorer_version` and `pipeline_fingerprint` values. A
missing identity is not a match. After a model, prompt or setting change, a
series with too few earlier articles reports insufficient evidence.

The length threshold is `drift.source_word_count_drop`. The copying threshold
is `drift.extractiveness_rise`, an absolute increase in the share of copied
four-word phrases. Their existing values were moved into config without
loosening them. The combined warning uses articles with both a length and a
faithfulness score, rather than comparing two different measured subsets.

`scoring_chrome` remains the alert identifier, but its text says **possible
non-article text**. Shorter sources with steady faithfulness warrant inspection;
they do not prove that extraction failed. Short news and video introductions
can be valid. Removing player notices also makes an extraction shorter while
improving it. See the [issue 438 replay](../archive/measurements-2026-08.md#drift-review-and-source-extraction-2026-09-08)
for the sample counts and the confirmed extraction defect.

### Current drift implementation gap

`drift.yml` compares windows in the live eval ledger and segments model-dependent
metrics by the recorded identities. Its text report names `DRIFT_VERSION`, date
windows, thresholds, sample counts, findings and skipped comparisons. It does
not persist a new drift-row contract or replay a fixed model benchmark.

The workflow prints the complete report in its run log. Its GitHub issue keeps
the findings and coverage counts, with a link to that log instead of repeating
every skipped comparison. GitHub limits an issue body to 65,536 bytes. If the
findings alone exceed that limit, the issue explicitly directs the operator to
the full log. No finding is silently cut and no comparison changes to fit the
message. The detail remains available for the run log's retention period,
rather than the issue's lifetime.

The fixed-set rules above remain the intended instrument. Offline captured-page
regressions protect extraction code; they do not replace a scheduled model
benchmark or prove that every live source still has the captured layout.

## Design rationale

**The band is one function (2026-08-23).** The old code had one function for rows with a faithfulness score and another function for rows without one. Only the first path wrote the eval row, so `lead_coverage` and `hedge_dropped` were measured and then ignored by the reader-facing band. One function removes that split. Authority: Fowler.

**Failed counterweights cap at `medium` (2026-08-23).** A low lead-coverage score or a dropped hedge reduces confidence, but it does not prove the whole summary false. Unsupported numbers still force `low`, because a wrong figure is a direct false claim. Authority: owner, resolving the known-defects open question.

**Lead entities do not cross line breaks (2026-08-23).** The source's title and body can be adjacent without sentence punctuation. Treating the newline as ordinary whitespace created impossible entities such as `biodiversity loss\nwe`, which counted against the summary and could never match it. A line break now ends the entity run while spaces and tabs still join names inside one line, such as `US President Donald Trump`. Authority: Andre's metric boundary, implemented as a structural bug fix.

**The band and its reason are one function (2026-08-24).** Returning them separately would let a page print a reason that is not why. They travel together as one value, and the band-only helper is a wrapper with no logic of its own. Authority: Fowler.

**The reason is an identifier and the sentence is copy (2026-08-24).** The published item carries `band_reason`; the site owns the words. Rewording a reader-facing sentence must not need a schema change, and the same identifier can read differently on a phone and in a feed. Authority: the identifier discipline in `docs/agents/guardrails.md`.

**A re-observation writes no row (2026-08-24).** The page has said since it was written that an item whose inputs did not change writes no row at all, and the writer did not enforce it. The rule was the better one - a ledger of measurements, not of times the pipeline looked - so the code changed. Authority: Fowler, closing known defect 6.

**One column reads the summary against itself (2026-08-26).** Eleven quality columns, and every n-gram machine in `backend/idhazh/evals/metrics.py` intersected the summary's n-grams with the *source's*. Nothing could see a summary that repeated itself, which greedy decoding makes possible and which every other column scores *better* on the worse it gets. Proved on committed fixtures rather than argued: two 26-word summaries of the same article, one saying a clause three times and one saying it once, score exactly equal on `extractiveness` (0.000), `verbatim_run` (0.077) and `coverage` (0.333), and 0.000 against 0.391 on the new one. Authority: Andre's blind-spot finding; nullable and appended, Fowler's layout rule.

**`METRICS_VERSION` did not move for it (2026-08-26).** The constant is folded into `scorer_version`, and this page requires ten distinct run-days at one `scorer_version` before a threshold can move. The count is stated once, in [The human labels](#the-human-labels-the-instrument-and-what-it-still-needs), and it has never reached 10. A column no band and no derived column reads changes nothing that a row written under `metrics-3` says, so bumping would have spent a banked run-day to record a fact about nothing. Authority: Andre.

**A fingerprint change restarts the run-day count at zero (2026-08-27).** The requirement above has asked for ten run-days at one `scorer_version` and one `pipeline_fingerprint` since it was written, and the page never said what happens when one of the two moves. The count goes back to zero, and it has to. The fingerprint exists so that ten days of scores are ten days of the *same* pipeline; a count carried across a model swap would average two different systems and present the result as one measurement. This is not a policy bolted on afterwards. `model_sha256` is a declared field of `PipelineInputs` in [`../../backend/idhazh/contracts/fingerprint.py`](../../backend/idhazh/contracts/fingerprint.py), and the stamp is a digest over that model's own serialization, so a model swap cannot leave the stamp still - and neither can a reworded prompt, a llama.cpp rebuild, a changed truncation cap, or any other declared input. Authority: the determinism contract, read rather than argued.

**The measured reset rate (2026-08-27, `state/scores.csv` and `state/fingerprints.csv` at commit `c08d8b5`).** 2,232 eval rows, written by 18 runs across **5 scored run-days** (`2026-08-22` to `2026-08-26`), carry **5 distinct `pipeline_fingerprint` values** and **4 distinct `scorer_version` values** - one new pipeline stamp per scored day, on average. `2026-08-26` alone carried three different (`scorer_version`, `pipeline_fingerprint`) pairs: the stamp moved at that day's second run and again at its fifth, and the scorer version moved at the fifth with it. Every one of those 2,232 rows names the same `model_id`, `qwen3-8b-q4-k-m` - the model did not change once and the stamp still moved four times, so a model swap is *one* cause of a reset rather than the cause. `state/fingerprints.csv` holds a single row, because the ledger that expands a stamp into its inputs only started on 2026-08-26; four of the five stamps can no longer be expanded at all. Authority: measurement.

**The consequence, and how it was resolved (2026-08-27).** The longest run of consecutive run-days under a single (`scorer_version`, `pipeline_fingerprint`) pair is **3** - `2026-08-24` to `2026-08-26`, under `969b1917...d2b945` - and the pair survived only the first of five runs on the third of those days. Three of ten, once, in the ledger's whole history. Adopting Qwen3.5-9B-Q4_K_M (commit `5d8ba60`, 2026-08-27) moved `model_sha256` and `chat_template_sha256` together, which is the one reset `state/fingerprints.csv` can expand into its cause. At the observed rate of pipeline change, every model or runtime improvement spent the whole window, so the pair requirement was unreachable rather than strict - a live tension between shipping a better pipeline and measuring the one already running. **The owner resolved it on 2026-08-27: count run-days at one `scorer_version`, and carry `pipeline_fingerprint` as a reported stratum rather than a disqualification.** The rejected alternative was to freeze the pipeline for ten days; it was declined because the claim it buys expires at the next prompt change, so the freeze would be paid repeatedly, and because a repository shipping several fixes a day cannot stand still that long. What the chosen rule gives up is stated wherever a result is printed: a rate over a pooled draw is a prior with wide bounds, not a calibration, and a stratum under `evaluation.label_min_stratum_rows` may not move a threshold at all. Measured effect on the same ledger: the drawable sample went from 32 of 60 with seven deciles short to **60 of 60**. Nothing here moves a threshold. Authority: owner.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Let lead coverage or a dropped hedge force `low` | It overcorrects. A good summary of a badly-extracted or narrow source can miss the lead and still be faithful to what it says. | owner |
| Re-cut the faithfulness band thresholds to reduce the `high` share | A band share is not an error rate. Choosing 0.90 over 0.80 would choose how much of the digest is called `high` and only then discover what `high` means. The decision needs human labels, not more unlabelled rows. It also changes nothing the reader sees: `high` prints no item-level copy. | Andre, Reader |
| Delete the four duplicate rows the old writer left in the ledger | They are an honest record of a run that really did re-summarize those items. The ledger is append-only, and rewriting history to make a denominator tidier is the band-aid, not the fix. | Fowler |
| Store `band_reason` on the eval row as well | It is derivable from four columns already on the row, and adding a column to a committed append-only CSV is a migration bought for nothing. | Fowler |
| Print both reasons when both counterweights fail | Two sentences on one item in a meta row is a paragraph. A reader gets one thing to check. | Reader |
| Bump `METRICS_VERSION` to 4 for `self_repetition` | It sits inside `scorer_version`, so it would restart the ten-run-day count this page requires before any threshold can move - to record a fact no threshold reads. `compression` is the precedent: recorded, diagnostic, not a pass/fail input. | Andre |
| Give `self_repetition` its own n-gram size | Two window sizes in one file are two numbers a reader has to reconcile, and 4 is already the size the extractiveness figure on this page is stated at. | Andre |
| Band `self_repetition`, or alarm on it | The moment a band reads it, it is a promise to a reader and a threshold decision - and no threshold may move until the labels exist. Recorded first, banded later or never. | Andre |
| Detect the loop at generation time and retry at a non-zero temperature | That turns the monitor into the selector, which is the first of the two rules above. It also changes what the digest publishes to fix a fault nobody has counted yet. | Andre |
| Point `verbatim_run` at the summary instead of the source | It is the column that names copying from the article. Repurposing it would delete a measurement to buy a different one and would silently change what every historical row means. | Fowler |
| Put the measurement on the item-health row | Item health records what a stage *did* with an item. This is a property of the words that came out, which is what the eval ledger is. | Fowler |
| Retune `evaluation.truncation_gap_max` down instead of deleting it | Over the 22 cut rows the gap runs -0.1235 to +0.0381, so any cut inside that band fires on chunk-boundary noise rather than on truncation. There is no value that separates the two. | Fowler, corrected by measurement |
| Keep `truncation_flagged` on the gap and add a second column for the cut | The column's name says "was it cut" and its one consumer prints exactly that sentence. Two columns would leave the wrong one wired to the page. | Fowler |
| Add a "the cut cost us" flag now | It needs a threshold with a measured basis. Twenty-two rows is not one, and `hhem_delta` is already recorded for when there are enough. | Fowler |
| Keep the brief-item verbatim clause on the same boolean | `verbatim_run` and `extractiveness` already carry that fact and the console already prints it as "Copied, not rewritten". One predicate per column. | Fowler |
| Move `METRICS_VERSION` to be safe | It is folded into `scorer_version`, so it would restart the ten-run-day count for a column no threshold reads. Nothing in `metrics.py` changed. | Fowler |

## Why this is a census and not a sample

Scoring every changed item costs something, and the obvious economy is to score a sample instead - every third day, say, or only the sources that are easiest to work with. It was proposed, examined and rejected. The reasons are worth keeping, because the proposal will look sensible again in six months.

**A per-item claim to a reader cannot be backed by a sample.** Every item on the page carries a confidence signal, and a low-confidence item publishes *marked*. If most items are never scored, most items have no signal, and there are only three things to do with them: render them unmarked, which silently turns "not measured" into "fine" on the reader's page; mark them "unchecked", which puts a caveat on almost the whole digest; or delete the signal. All three are worse than paying for the measurement.

**Sampling by source is the one axis guaranteed to bias the result.** The sources that are cleanest to work with - institutions publishing one column of semantic HTML, in plain declarative prose - are exactly the ones the pipeline finds easiest. Scoring only those measures the system where it cannot fail. Worse, it disarms specific instruments: dropped hedges essentially never occur in institutional prose, so that metric would report zero forever and read as a passing test. And extraction rot - the slow failure this whole page exists to catch - concentrates on the messy sources a clean-source sample never fetches. That is a smoke detector installed in the room that cannot catch fire.

**The economics do not justify it.** The deterministic counterweights are string operations - a rounding error against the cost of generating the summary in the first place. Only the faithfulness model costs anything real, and rationing it is a decision that should follow a measurement rather than precede one. The rule: measure the faithfulness scorer's share of per-item wall-clock, and if it exceeds a stated share of the budget, sample *it* alone, selected deterministically, and never below the rate at which a month-over-month comparison stays valid. The counterweights are never sampled. That rationing now exists, and it is drawn per run rather than within a day - see [The scorer is sampled by run, and nothing else is](#the-scorer-is-sampled-by-run-and-nothing-else-is) for why the earlier wording changed.

**If a sample is ever taken, it is recorded and never left as an absence.**
Production fingerprint skip is not wired, so a missing row today cannot
prove that work was skipped. Any future skip or sample reason must be explicit.
And any aggregate built on a sample states its denominator in the open: a count
that describes part of the digest may never be displayed as though it described
all of it. Where that record lives followed the unit being sampled: a per-item
draw would have needed a column on every row, and the per-run draw needs one cell
on the run.

**One thing to do regardless:** the reader-facing confidence signal is driven by the counterweights, which are a census by construction and cost nothing. The faithfulness score is the operator-facing instrument that calibrates the bands. That split keeps a reader-facing promise off the most expensive metric in the system.

### The scorer is sampled by run, and nothing else is

The rule above said that if the faithfulness scorer ever had to be rationed it
would be drawn *within* every day. The owner ruled otherwise on 2026-08-30, the
coarser design is the safer one, and the earlier wording is corrected here rather
than left to disagree with the code.

**The unit is the run.** `observability.sample_rate` is the fraction of runs
whose scorer runs - never the fraction of items, and never the fraction of
shards. A run scores every item it summarized, or it scores none. A day with
three of four shards scored has a wrong denominator for that day and nothing on
any page could name it, so a whole-run decision is what keeps a day internally
consistent: a per-day figure is a complete measurement of that day or it is
absent.

**The draw is a digest of the run id**
([`../../backend/idhazh/evals/sampling.py`](../../backend/idhazh/evals/sampling.py)).
The id is hashed, its first eight bytes are read as a position in `[0, 1)`, and
the run is drawn when that position falls below the rate. Three things follow.
It is reproducible from the committed manifest a year later with no state kept
anywhere. It is blind to the run's content, so it cannot thin the ledger towards
the days that happened to score well. And raising the rate only ever adds runs,
so a series never develops a hole where it used to carry a reading.

**The thinning happens at collection, not at display.** An unsampled run is never
scored, so its rows do not exist. Nothing is filtered in a browser and no page
has a second, hidden population behind it.

**Every run records the rate and the draw, whichever way the draw went.**
`RunRecord` carries `evaluation_enabled`, `evaluation_sample_rate`,
`evaluation_sampled` and `scorer_version`
([`../../backend/idhazh/contracts/run_manifest.py`](../../backend/idhazh/contracts/run_manifest.py)).
Four facts, because an empty ledger has four causes and an absence looks
identical for all of them: the switch was off, the run was not drawn, the weights
would not load, or the run never reached the scorer. `scorer_version` is null
exactly when no row was written. Without the rate on every run - not only on the
runs where it bit - a reader cannot tell 800 rows of 1,000 from 800 rows of 800.

**A published RATE comes from the item-health census and from nothing else.** The
census is never sampled. It is the denominator under every rate on every page, so
thinning it would not make a measurement cheaper, it would make every other
measurement unreadable. The sampled ledger publishes distributions instead -
medians, spreads, histograms - because a median survives a sample and a rate does
not. **There is deliberately no scaling formula anywhere.** A formula is a thing
somebody forgets to apply, and a rate quietly multiplied back up reads exactly
like a rate that was measured.

**Never sampled, each for its own reason:** the item-health census, because it is
the denominator; `state/seen/` and `state/published/`, because they are what
stops a repeat; `state/feed-health/`, because quarantine fires at
`collect.availability_strikes_before_rest` consecutive failures and a missing row
moves that count; and the canary suite, because a canary that runs sometimes is
not a canary.

## The ledger

Every item produces one row, appended to a committed CSV. It is appended by CI, read by the dashboard, and never recomputed at read time (Rule #1). The row shape is a contract like any other, versioned and changelogged ([../../CLAUDE.md](../../CLAUDE.md) section 11).

Committing the scores rather than deriving them is what makes a claim about last quarter a lookup instead of a re-run against a model that has since changed.

The ledger header is part of the contract. A writer now refuses to append when the committed header no longer matches `EvalRow.csv_columns`. A contract test also parses every committed `state/*.csv` with Python's `csv` module and fails if any data row has a different cell count from its header. This protects the file itself, not only the append path.

**The ledger records measurements, not runs.** The writer refuses a row whose
address, pipeline fingerprint, output words and scorer version all match a row
the file already holds. Nothing in that recorded measurement identity changed,
so a second row would only inflate the denominator every rate is computed
against. Article-input identity is not part of this de-duplication key.
`item_id` is deliberately absent too: it is a slot on a page, not the item.

### Every column is answered for by exactly one console panel

A measurement nobody can look at is a measurement nobody acts on. Counted
2026-09-06, ten of the ledger's twenty measured columns had no reader anywhere
in the published site - including `hhem` and `coverage`, the two the checker has
written on every summary since the first published day. Nothing was broken and
nothing failed; the columns were simply never projected, for two weeks.

So the projection is now declared and tested. `DRAWN_BY` in
[../../frontend/src/lib/console/eval-instruments.ts](../../frontend/src/lib/console/eval-instruments.ts)
assigns each measured column one owning panel, `NOT_A_MEASUREMENT` gives each
identity and provenance column a one-line reason, and
[../../frontend/tests/console-model-instruments.spec.ts](../../frontend/tests/console-model-instruments.spec.ts)
compares the two against this schema's property list. **Adding a column to
`EvalRow` without deciding where it is shown now fails a test in the
ninety-second gate.** The failure names the column and says what to do: give it a
panel, or write the sentence saying why it is not a measurement.

Where each one is drawn is recorded in
[../architecture/publishing/frontend.md](../architecture/publishing/frontend.md);
this page stays about what the columns mean.

Authority: row 4 of
[../../TODO/20260905-03-console-backfill-plan.md](../../TODO/20260905-03-console-backfill-plan.md),
2026-09-06.

Any of the four differing makes it a new measurement and it lands: different words under identical inputs is the determinism violation the ledger exists to catch, and the same words read by a different scorer is a reading worth keeping.

Four rows written before this rule are still committed - four items on 2026-08-23 that a second day re-summarized because the published ledger had no record of the day before. They are honest history and stay. Anything counting the whole ledger de-duplicates on those four columns first.

The 2026-08-23 repair kept positions stable. It measured `state/scores.csv` with Python's `csv` module: 33 header names and 19 data rows, all with 33 cells. Ten historical rows predated `score_ms`, so they now carry the contract default `0`. All 19 rows predated `evidential_density` and `speculative_density`, so those cells stay empty as CSV nulls.

**Adding a column is a data migration, every time.** `self_repetition` landed on 2026-08-26 and the committed ledger moved with it in the same commit: one name on the header line and one empty cell on each of 2,116 data rows. Measured before and after - the file went from 1,548,111 to 1,550,243 bytes, which is 2,117 commas plus the 15 characters of the column name and not one byte more, and the line count did not change. The rows are padded rather than left short because the contract test above fails a row whose cell count differs from its header, and empty is the honest cell: those rows were scored by a build that never measured the thing.

**The row is self-describing.** It carries the date, the source link and the title, not only the scores - so that a row still means something after the day it describes has been pruned from the published site. Those columns exist from the first row, because adding them after a prune cannot recover what was already lost.

That title is the **source's** headline, not the one the summarizer wrote ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). An identity anchor has to be the thing that does not vary, and ours is rewritten every run and absent whenever the rewrite missed its range.

**Run-level facts are not ledger rows.** How many items a run planned, finished and failed is a property of the run, not of any item, and it lives in the run manifest - which is committed, dated and published alongside the day. Widening the per-item row to carry a second kind of row would leave every item row with columns that are blank for it and would break the dashboard's one honest question: group the rows by band and count them.

**A duplicate measurement writes no second row.** The writer de-duplicates on
address, pipeline fingerprint, output words and scorer version after work has
run. That is ledger de-duplication, not proof that production skipped inference.
The current pipeline fingerprint also lacks article-input identity, so it cannot
establish that a publisher left the source bytes unchanged
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

### A month past fourteen becomes a summary, and the dedupe survives it

`state/scores/` is the largest store under `state/` - measured 2026-09-03, 5,335
rows in 4,266,655 bytes over two monthly shards - and nothing bounded it. Sharding
by month bounds one file, not the tree.

Deleting an old shard outright would answer the bytes and break two things. Every
published quality claim about that month would lose the rows behind it, and Rule
#10 then forbids citing the number at all. And the dedupe above works by reading
the rows, so the day a shard is deleted every measurement in it becomes new
again - which turns a count over the ledger from a count of items into a count of
times the pipeline looked, and that is the one thing this ledger promises it is
not.

So a month past `observability.scores_full_grain_months` is turned into
`state/score-archive/<YYYY-MM>.json` first, and the shard is unlinked only after
that file has been written temp-then-rename, read back through its contract, and
reconciled field by field against a second reading of the shard. The archive
carries:

- the shard's SHA-256 and its row count, which is what says WHICH file it
 summarises rather than what was in it;
- one digest per distinct measurement it held, sorted -
 `evals.writer.recorded_observations` unions these with the live rows, which is
 how the promise above keeps holding for a month whose rows are gone;
- one cohort per (date, run, row version, model, pipeline fingerprint, scorer
 version), each carrying its row count, ten faithfulness deciles, three bands,
 the boolean signal counts, the known and actual cut counts, the premise-digest
 counts, and `{n, sum, sum_squares, min, max}` for every numeric column.

Five numbers a column and not a mean and a standard deviation, because a stored
mean cannot be re-added into a total and a stored spread cannot be pooled across
cohorts. These can do both. `n` counts the rows that carried a value rather than
the rows in the cohort, so a column added mid-month reads as never measured on
the rows before it rather than as zero.

**What is deliberately lost:** item-level lookup, a late draw into the label
queue, re-banding those rows under new thresholds, an exact percentile,
correlating two columns against each other, and any slice the cohort key does not
name. **What survives:** totals, rates, distributions, ranges, spread, signal
counts, cut counts and exact dedupe. Every utility that needs an item-level row -
`label_queue.py`, `reband_scores.py`, `data_wrangler.py refill` and
`grader_length_bias.py` - names the fourteen-month limit and says which months it
can no longer reach, rather than reporting a smaller number as though the ledger
had always been that size. Authority: Andre, under Rule #10.

**Measured 2026-09-03** on a developer machine,
 (build 26200), CPython 3.14.2, over both committed shards with three
reads each: 4,266,655 bytes of shard become 557,290 bytes of archive, **13.1
percent**. Three reads gave byte-identical archives, so the spread is zero -
reading a committed file is deterministic. Two thirds of the archive is the digest
index, which is the price of keeping the dedupe exact. What the ratio buys in
years is in
[../architecture/publishing/layout.md](../architecture/publishing/layout.md#what-bounds-the-committed-state-tree).

**It ships in dry run.** `.github/workflows/prune.yml` force-pushes `main` on a
schedule, so a shard deleted here stops being recoverable once that prune passes
over it (`CLAUDE.md` section 8). The step prints what a live run would remove and
removes nothing; turning it on is a one-line commit somebody takes after reading
that list. The first shard it would take is `state/scores/2026-08.csv` on
2027-10-01.

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
in [Two rules that are easy to break by accident](#two-rules-that-are-easy-to-break-by-accident).
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
scored 4 of 5 against a Rule #11 threshold of all five, because
`exfiltration-via-url` returned no summary at all; and one brief-band item was
reproduced word for word, a verbatim run of 1.000 against a ceiling of 0.5. No
comparison against the retired incumbent Qwen3-8B-Q4_K_M was run - no paired
corpus, no side-by-side scores, no human review - so nothing here shows its
summaries are better or worse than the retired model's.

Qualification run `33016222069`, 2026-08-26, on `ubuntu-latest`. One model, three
deterministic repeats, no side-by-side arm. Every gate outcome, the band counts,
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

**Rule #11 held. Rule #10 broke.** Fetched text is data and never instruction,
and the sanitizer plus the schema are the controls that rule names - both did
their job. What failed is the measurement. The gate reported `4/5 passed,
failing: exfiltration-via-url`, a string with no measurement in it, and two
pages read it as a security finding. The gate is being given a failure code so a
reader can tell a breach from a blank reply.

**The consequence for this page is bigger than the reply failure: Rule #11 has
no live evidence today.** An instrument that cannot separate a breach from a
blank reply can never confirm the rule it exists to confirm. Eight gates still
measure what they claim to. The canary arm does not, and cannot until the
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
re-run the canary arm alone against the configured 9B - five calls, no corpus
freeze, no repeats.

### The alarm that watches the swap

Both limbs are arithmetic over committed rows. Neither runs a model.

| Limb | What is read | Trips when |
| --- | --- | --- |
| Unsupported numbers | share of `state/scores.csv` rows with `unsupported_numbers > 0` | the rate doubles, or rises 5 points absolute |
| Copying without a faithfulness cost | mean `extractiveness` and mean `hhem` | extractiveness up 0.10 or more while hhem is flat or up |

Segment by `pipeline_fingerprint`, at one fixed `scorer_version`, over a rolling
14 run-days against the last 14 days the 8B produced.

**The segment key is `pipeline_fingerprint`, not `model_id`.** A slug holds still
while the prompt, the truncation cap and the llama.cpp build move, and all three
move the score, so a slug attributes a changed score to an unchanged pipeline
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).
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
arrived on `state/item-health/<YYYY-MM>.csv` part way through its life, so a
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

- [search-quality.md](search-quality.md) - the other instrument: whether archive search finds the right story.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the controlled procedure for testing and adopting a challenger.
- [pipeline-loop.md](pipeline-loop.md) - where the Evaluate stage sits.
- [digest.md](digest.md) - how a confidence band reaches a reader.
- [config.md](config.md) - the band thresholds and retry budget.
- [principles.md](principles.md) - principle 6, the belief this page implements.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the prompt asks for, including the hedges these metrics check.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the eval-row contract.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the stamp every row carries, and why an unchanged item writes none.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the published surface a confidence band reaches.
- [../../.github/agents/andre.agent.md](../../.github/agents/andre.agent.md) - the persona who owns metric choice.
