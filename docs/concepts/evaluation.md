# Evaluation

**Last Updated**: 2026-08-27

How a summary is judged, how archive search is judged, why one number is never enough, and the rule that keeps the measurement honest. This page fixes the vocabulary; the concrete metric implementations, thresholds and the golden-set contents are owned by the plan-doc and the eval subsystem doc, and the tunable bands live in [config.md](config.md).

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
`weights_digest()` hashes the loaded tensors rather than a model name.
`scorer_version` carries both observations. A scorer that has not loaded cannot
name its weights and fails instead of minting a plausible identity.

### The two source word counts are one counter, before and after the cap

`source_word_count` is `Article.source_word_count`, the words in the extracted
body before `extract.truncation_cap_tokens` cut it. `source_seen_word_count` is
`Article.word_count`, the same counter applied to what survived. The difference
between them is the cut, and nothing else.

**A row stamped before `2026-08-27T20:00` measured something else.** Both cells
came off the post-cap string through two different counters -
`len(_WORD.findall(t))` against `len(t.split())` - so the difference measured
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

### Three definitions that look reasonable and are not

Each of these was specified one way, and the arithmetic says otherwise:

- **Coverage over the whole article is a constant.** A long article carries far more named entities than a short summary can hold, so raw survival lands near the same low value for a good summary and a bad one. A metric with no dynamic range is worse than no metric, because it looks like a measurement. Anchoring on the lead restores the range and points it at the defect that matters - journalism puts the who, the what and the how-much in the opening lines, so a summary that drops them dropped the story.
- **A compression *band* is a length detector.** At a fixed output budget, the ratio is dominated by how long the article was. A band on it would flag every short article forever, for a reason that is never about the summary. The ratio is recorded as a diagnostic; the real failures - a headline, or a copy - are detected directly by absolute word bounds.
- **Verbatim overlap must be contiguous.** Measured as a longest common *subsequence*, function words match in order in almost any document, which puts a floor under the score and makes it move with length instead of with copying. Contiguous n-grams and the longest unbroken run do not have that floor.

For a brief item, `verbatim_run > evaluation.brief_compression_ceiling` flags
truncation. The default is 0.5. This is the arithmetic ceiling that makes a
30-word ask possible at a 60-word source floor. It is not a confidence threshold.
The confidence band stays on the faithfulness axis.

## Two rules that are easy to break by accident

**1. The metric that selects can no longer alarm.** It is tempting to generate several candidate summaries and keep the one that scores best. Doing so destroys the score's value as a monitor: once it is the selector, it can no longer tell you that outputs are getting worse, because it is being optimised against by construction. This is Goodhart's law with a concrete cost. The selector and the alarm stay separate.

**2. The model does not grade the model.** LLM-as-judge is a project non-goal ([../../CLAUDE.md](../../CLAUDE.md) section 0a). A judge built from the same technology shares the failure modes of the thing it is judging, and agrees with it for exactly the reasons you needed an independent check. The substitute is a purpose-built scorer, plus the deterministic counterweights above, plus a small recurring human spot-check whose only job is to keep the automated scores calibrated.

Discouragement is not a control, so four things make it structurally hard rather than merely forbidden. `LabelRow` has no author field a model could fill and no nullable one it could leave blank - `labeller` is required and checked against `evaluation.labellers`. The writer is a human-paced CLI with no `--from-file`, no `--model` and no stdin path, so generating labels from a model means writing a second writer in a diff in a pull request. `seconds_spent` has a floor. And the draw module may not import `idhazh.llm` or the scorer, asserted by a test, so the loop cannot close on itself after a refactor by somebody who never read this paragraph.

Not to be done: seeding the queue with model pre-labels for a human to confirm. Confirmation is anchoring, and it turns an independent measurement into an expensive agreement rate with the model - LLM-as-judge with a rubber stamp.

### Current qualification-gate implementation gap

**The `publishable_length` gate cannot fail, and this is not fixed.** It grades
the survivors of the rule it is grading, so the only answer its arithmetic
allows is "none outside the range". Rule 1 above is broken here inside our own
instrument rather than by a model: the word range is the selector, and the same
word range is the alarm.

The range is enforced twice, off the same two knobs. `summarize.to_summary`
counts the drafted words and refuses anything outside
`evaluation.summary_words_min` to `evaluation.summary_words_max` with
`length_out_of_range`, returning a payload whose status is `failed` and whose
summary text is unset. `cli._observe` sets both `ok` and `schema_valid` from that
status, and takes `summary_word_count` from the summary text - zero for a refused
reply, never the count the model actually wrote. `evals/qualify.py` then grades
`[o for o in observations if o.ok]` against those same two knobs. Every reply
that could fail the gate was refused before the gate looked.

Run 33016222069 reported 0 of 90 replies outside the range, and passed
([../reference/measurements.md](../reference/measurements.md#the-configured-summarizer-qwen35-9b-q4_k_m)).
Zero is the only number that arithmetic can return, on any model and at any
threshold, so the result is not evidence that this summarizer writes publishable
lengths. Read the gate as "not measured", never as "passed".

**The fix is to record the measurement instead of dropping the item, and it has
not been written.** `stage_qualify` already appends an observation for every
call, refused ones included, so the only thing missing is the number: `_observe`
would carry the words the reply actually held, and the gate would read every
reply rather than the survivors. That widens the persisted `ItemObservation`
contract, which makes it a Level 3 change ([../../CLAUDE.md](../../CLAUDE.md)
section 6) needing its own schema stamp, changelog entry and review. Nothing
here does it.

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

## Bands, not raw numbers

Scores are bucketed into a small number of confidence bands, and the band - not the number - is what drives behaviour: what gets retried, what publishes with a visible low-confidence marker, and what a reader sees. Bands are tunable ([config.md](config.md)) and are re-calibrated against the human spot-checks rather than being fixed by taste.

The absolute summary gate starts at `evaluation.summary_words_min = 25`. That
lets the brief band ask for 30 to 45 words without the decoder padding a short
source to the old floor.

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
`band()` would cap them at `medium`. Re-band the ledger with the current function
before using the bands as a distribution. Measured 2026-08-24 on the committed
`state/scores.csv` at 447 rows: recorded 63.8 / 18.1 / 18.1, re-banded
57.7 / 24.2 / 18.1. Twenty-seven rows move, all of them written before the caps
landed - 11 on lead coverage, 11 on a dropped hedge, 5 on both.

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

**The draw leaked the hidden score gradient through its order.** `draw()`
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
not a filter it applies (owner decision, 2026-08-27).** `eligible()`, `draw()`
and `run_days()` require the scorer with no default, because the cuts being
calibrated live inside that string: a row read by a different instrument answers
a different question. `pipeline_fingerprint` is optional, and omitting it is the
normal case. `strata()` splits the drawn rows by producer, and the tool prints
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
what that costs are in [Design rationale](#design-rationale) below.

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

## Per-item scores cannot see drift

Per-item scores measure variance *within a day*. Drift is a movement *across months*: the model runtime changed, a source redesigned its pages, a prompt was edited. Those are invisible in single-item scores and require a second instrument - a fixed set re-run on a schedule, producing a dated row, with alert thresholds on the aggregate.

Two design consequences:

- **Every drift row is version-stamped** with the runtime build, the model file hash and the scorer version. A deterministic output can change because the runtime changed, not because the model did, and a benchmark that cannot tell those apart raises false alarms.
- **The fixed set is refreshed on a schedule.** A frozen golden set stops representing the live corpus and quietly becomes a museum.

A drift detector that has never fired has not been shown to work; it is tested by replaying the set against a deliberately degraded input and confirming the alert fires.

### Current drift implementation gap

`drift.yml` currently compares windows in the live eval ledger. It does not
replay a fixed set, persist a drift row, or segment model-dependent metrics by
`model_id`. The version-stamped fixed-set rules above are the intended
instrument, not current workflow behaviour. A model swap must start a new
model-dependent series rather than appearing as ordinary drift in the old one.

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

## Why this is a census and not a sample

Scoring every changed item costs something, and the obvious economy is to score a sample instead - every third day, say, or only the sources that are easiest to work with. It was proposed, examined and rejected. The reasons are worth keeping, because the proposal will look sensible again in six months.

**A per-item claim to a reader cannot be backed by a sample.** Every item on the page carries a confidence signal, and a low-confidence item publishes *marked*. If most items are never scored, most items have no signal, and there are only three things to do with them: render them unmarked, which silently turns "not measured" into "fine" on the reader's page; mark them "unchecked", which puts a caveat on almost the whole digest; or delete the signal. All three are worse than paying for the measurement.

**Sampling by source is the one axis guaranteed to bias the result.** The sources that are cleanest to work with - institutions publishing one column of semantic HTML, in plain declarative prose - are exactly the ones the pipeline finds easiest. Scoring only those measures the system where it cannot fail. Worse, it disarms specific instruments: dropped hedges essentially never occur in institutional prose, so that metric would report zero forever and read as a passing test. And extraction rot - the slow failure this whole page exists to catch - concentrates on the messy sources a clean-source sample never fetches. That is a smoke detector installed in the room that cannot catch fire.

**The economics do not justify it.** The deterministic counterweights are string operations - a rounding error against the cost of generating the summary in the first place. Only the faithfulness model costs anything real, and rationing it is a decision that should follow a measurement rather than precede one. The rule: measure the faithfulness scorer's share of per-item wall-clock, and if it exceeds a stated share of the budget, sample *it* alone - stratified across source tiers, drawn within every day rather than on alternate days, selected deterministically, and never below the rate at which a month-over-month comparison stays valid. The counterweights are never sampled.

**If a sample is ever taken, it is recorded on a written row, never as an absent
one.** Production fingerprint skip is not wired, so a missing row today cannot
prove that work was skipped. Any future skip or sample reason must be explicit.
And any aggregate built on a sample states its denominator in the open: a count
that describes part of the digest may never be displayed as though it described
all of it.

**One thing to do regardless:** the reader-facing confidence signal is driven by the counterweights, which are a census by construction and cost nothing. The faithfulness score is the operator-facing instrument that calibrates the bands. That split keeps a reader-facing promise off the most expensive metric in the system.

## Retrieval: does archive search find the right thing?

Everything above scores a summary. This section scores a different promise: that
a reader who searches the archive on their own device gets back the items they
were looking for. Until 2026-08-26 nothing measured it at all, and the only
thing that looked like a measurement - five hand-written queries driven through
a browser - is a wiring check. At n=5 the standard error at recall 0.8 is 0.18,
so it cannot see a ten-point regression. It stays exactly what it is and its bar
is never raised.

The instrument is [`backend/idhazh/evals/retrieval.py`](../../backend/idhazh/evals/retrieval.py),
run by the backend test suite. It is not a browser test. The quality question
has nothing to do with a browser, and the browser path pays the whole encoder
download on every run.

### Two tiers, and only one of them exists today

**Tier one is free and needs no labeller.** One query per entity slug carried by
three or more items; the relevant set is exactly the items carrying that slug.
Nobody's judgement is in it, so nothing can bias it, and it fires the moment the
encoder or the committed vectors break.

It produced **zero queries** for its first five days, because no published item
carried an entity slug. `DigestItem.entities` is copied from `Article.entities`
and no stage in the pipeline ever wrote that field - nor `lenses`, nor `events`.
Three declared taxonomy dimensions were empty on every committed item.

**A deterministic tagger now writes all three (2026-08-26).** The rule and its
measured coverage live in
[`../architecture/sources/discovery.md`](../architecture/sources/discovery.md).
What it means for this tier, measured on the committed corpus by running the
real `entity_queries` over items the matcher had tagged: **0 queries becomes
25**, covering **616 of 2,237 items**, from `entity-asml` at 3 items to
`entity-google` at 105.

**That is what the corpus supports, not what the tier reports today.** The
tagger only touches items published from now on; no committed payload was
rewritten, so the tier stays at zero and climbs as new days land. Read the 25 as
the instrument being live rather than as a score.

Two properties of the tier survive the change and are worth restating, because
they are why it was built before it could fire: the relevant set is exactly the
items carrying the slug, so no labeller can bias it, and a slug is assigned by a
whole-word match on a curated alias rather than by a model, so a page cannot
choose which query it answers.

**Tier two is 60 hand-labelled intent queries** in
[`tests/fixtures/search/retrieval-queries.json`](../../tests/fixtures/search/retrieval-queries.json),
carrying 297 relevance judgements. A query is a question in a reader's words; the
relevant set is every published item that answers it, addressed by
`(date, item_id)` because an item id is unique only within a day and is reused
across days. Relevance is binary and a query has many right answers on purpose: a
topic question does, and single-gold labelling makes a working system read as
broken.

No model wrote, ranked or selected those queries. The digest's own summarizer is
the thing being retrieved, so letting it generate the query set would be
LLM-as-judge under another name (`CLAUDE.md` section 0a).

### recall@10 is the gate; reciprocal rank is a diagnostic

The surface is a flat capped list with no rank cue. Rewarding first place would
measure a claim the product does not make, so mean reciprocal rank is computed,
reported, and never gated on.

**The denominator is capped at the ten slots that exist.** A topic query has more
right answers than a ten-item list can hold, so `found / len(gold)` would report
a retriever that filled every slot correctly as a failure, and would move the
score whenever a labeller was generous. `found / min(gold, 10)` asks the question
the surface can answer: of the right answers you could have shown in the slots
you have, how many did you show. The uncapped figure is reported beside it.

**A miss and an absence are different failures, and conflating them makes the
instrument lie.** An item with no vector cannot be retrieved at any threshold.
Every result therefore carries two numbers: the reader-facing one over all
labelled answers, and the ranking one over the answers that carry a vector. Only
the second is gated (`assist.recall_min`), because failing this gate for a gap in
the embedding stage would point at the wrong code.

### The baseline, 2026-08-26

Measured on Windows 11, 12 logical CPUs, `onnxruntime` 1.29.0, against the
committed archive after the vector backfill - 2,121 published items of which
2,119 carry a vector (99.9%), 60 queries, floor 0.35, ten slots.

| Number | Value | What it says |
| --- | --- | --- |
| recall@10, all labelled answers | **0.767 +/- 0.036** (n=60) | What a reader gets today. |
| recall@10, answers that carry a vector | **0.767 +/- 0.036** (n=60) | The same number now. |
| Queries with no embedded answer at all | 0 of 60 | Every question is answerable. |
| Coverage of labelled answers | 100% | The coverage failure is closed. |
| Mean reciprocal rank | 0.842 | Diagnostic. A found answer is usually first. |
| Filled slots holding an unjudged item | 65.6% | Why the number above is a lower bound. |

**The coverage failure is fixed and the ranking number fell, and neither of
those is a surprise once you hold one thing constant at a time.** The bar was
0.85, set from 0.931 on an archive where 44.5% of items carried a vector. The
backfill took that to 99.9% and the gate failed at 0.767. Four measurements,
same 47 queries, same labels, same ranking code, separate the causes:

| Arm | recall@10 | Effect |
| --- | --- | --- |
| A - archive before the backfill | 0.902 +/- 0.036 | the old baseline, reproduced |
| A' - same 944 items, today's re-encoded vectors | 0.910 +/- 0.034 | re-encode **+0.007** |
| B - whole archive, old labels, old denominator | 0.761 +/- 0.055 | competition **-0.142** |
| C - whole archive, as gated | 0.743 +/- 0.042 | denominator **-0.018** |

**There is no ranking regression.** Holding the corpus to the same 944 addresses
and swapping in the re-encoded vectors moves the number *up* by 0.007, which is
a fifth of a standard error. The entire drop is 1,175 items that the index could
not see before, now competing for the same ten slots, plus a denominator that
grew with coverage: the summed ceiling over those 47 queries went from 85 slots
to 246.

**The 0.767 is a lower bound on recall, not recall.** The labels were pooled
from an index that could see 44.5% of the corpus, so a right answer with no
vector could not be found by the labeller and could not be labelled. It can be
retrieved now, and the metric counts it as a wrong answer. Measured: of the 382
unlabelled items occupying a slot, 212 - **55.5%** - were unembedded on
labelling day. `crude-oil-price` scores 0.000 and is the clearest case: the five
items above its gold are US commercial crude inventories, record US crude
production, EIA crude stocks, Q2 petroleum market volatility and the Brent
price. Every one of them answers the query's own written intent, "items about
crude output, crude imports or the crude price". None of them is labelled. The
labels are incomplete, not wrong, and no label was changed to raise the score.

**This is pooling bias, and it is the correction the earlier text got wrong.**
The previous version of this page said the number "drifts down as the archive
grows, and that is correct", on the reasoning that a new day can only add
distractors. The measurement says otherwise: most of what takes a slot from a
labelled answer is another right answer nobody judged. So the drift is partly an
artifact, and the bar will keep sliding for a reason that is not a regression.

**The instrument prints its own blindness on every run.** `RetrievalReport`
carries `unlabelled_share` - the share of filled slots holding an item no
labeller judged either way - and a test asserts it is above zero, so the day the
labels catch up somebody is told to delete this caveat.

### Moving search to the month index cost nothing, 2026-08-27

The archive stopped carrying every committed day and started fetching
`index/<YYYY-MM>.json` with its sibling vector file. That is 1.7 MB off
the page, and the question a byte saving can never answer on its own is whether
the index lost information the day payload carried.

Measured on the same checkout, same 60 queries, same labels, same ranking, same
embedded queries - the only difference is which file the vectors came out of:

| Arm | recall@10 | MRR | Corpus |
| --- | ---: | ---: | --- |
| Day payloads, the surface being deleted | 0.756 +/- 0.037 | 0.816 | 2,235 of 2,237 carry a vector |
| Month index, the surface being shipped | 0.756 +/- 0.037 | 0.816 | 2,235 of 2,237 carry a vector |

**Identical to three decimals on every number the report carries.** That is the
expected result rather than a lucky one: the index projects the same int8 bytes
the day payload held, and it decodes them with the `scale` its own header states
rather than a constant, so nothing about the arithmetic changed.

**The reader-facing number moved from 0.767 to 0.756, and the index is not
why.** The baseline above was taken over 2,121 published items; this checkout
holds 2,237. Both arms moved together, which is exactly the pooling drift the
paragraphs above predict - 116 more items competing for the same ten slots
against a frozen label set, and 66.6 percent of filled slots now hold an item no
labeller judged, up from 65.6 percent. 0.756 is 0.3 standard errors under the
baseline and 0.066 above the `assist.recall_min` bar.

`backend/tests/test_retrieval_eval.py` holds the comparison rather than this
page: it fails when the two arms disagree by more than one standard error, so
the day the index starts losing something, a gate says so instead of a byte
count looking like a win.

### The bar, and what it is worth

`assist.recall_min` is **0.69**, two standard errors below 0.767. It still
catches what a bar is for: a ranking change that costs more than about seven
points fires it. What it cannot do is tell a real regression from the archive
growing under a frozen label set, and it has about 0.077 of room before that
matters.

**Archive search does clear a defensible bar, and the bar is lower than it
looked.** 0.767 over 60 questions with a fully embedded corpus is an honest
number for a 384-dimension quantised encoder running in a browser, and it is a
floor rather than a ceiling. What is not defensible is the old 0.85: it was
measured on the 37% of the corpus that happened to have vectors, which is an
easier question than the one a reader asks.

**Completing the labels is the fix, and it belongs in its own commit.** Judging
only the items the ranker put in the ten slots would raise recall by
construction - the metric choosing its own ground truth, which destroys the
alarm. A sound re-label pools deeper than the slot count from two retrievers, a
dense one and a lexical one, judges every candidate against the written intent
by one rule, and lands separately so the bar's movement is attributable to
labels or to the system but never to both at once.

### The similarity floor is a selector, measured

Below the floor a result is not shown at all. It is never reported to a reader as
a quality signal, and no page prints a score.

Re-measured 2026-08-26 against the backfilled archive (2,119 embedded items):
**126,843** same-domain non-answer pairs - a real question against a real item
that does not answer it - score a mean of 0.0761, a p95 of 0.2716 and a p99 of
0.3992. The 297 right answers score a p10 of 0.3753 and a median of 0.5314. The
two distributions overlap, so there is no clean cut, and any floor trades a
right answer against a wrong one.

**The noise did not move when the corpus did.** The earlier reading over 34,715
pairs was mean 0.074, p95 0.269, p99 0.399. At 3.7 times the pairs the numbers
agree to three decimal places. The floor therefore stays at 0.35, which is the
p98.12 of same-domain noise.

| Floor | Non-answers surviving | Right answers kept | recall@10 |
| --- | --- | --- | --- |
| 0.20 (was shipped) | 11.68% | 98.7% | 0.770 |
| 0.30 | 3.55% | 96.0% | 0.770 |
| **0.35 (shipped)** | **1.88%** | **93.6%** | **0.767** |
| 0.40 | 0.99% | 85.2% | 0.747 |
| 0.45 | 0.50% | 76.4% | 0.694 |

0.45 would buy silence on every probe below for 0.073 of recall, which is two
standard errors and so a measurable loss. It is not bought.

**A probe stops being a probe when the archive grows into it.** Four off-domain
questions assert that the empty state can fire. One of them, "restoring a 1960s
mechanical wristwatch movement", stopped being off-domain the moment the
backfill made the archive's smartwatch items reachable: it returned a Pebble
Time 2 review at 0.413 and a Garmin deal at 0.360. Those are wristwatches. The
probe is retired and recorded here rather than deleted quietly, and replaced
with "hand-stitching a leather saddle", which scores 0.194. The four now in the
test score 0.235, 0.295, 0.258 and 0.194, so the tightest has 0.055 of margin
under the floor.

**And a probe set can always be softened, so it is not the only assertion.** A
second test scores every query against every item that does not answer it and
requires the floor to clear the p95 of that distribution. No choice of probe
can dodge it, and it fires if the archive ever grows noisier than the selector.

### Design rationale

**The eval lives in the backend suite (2026-08-26).** The browser test that
existed measured whether search runs, not whether it works, and it paid a 43 MB
encoder download to do it. Retrieval quality is arithmetic over committed vectors
and needs no page. Authority: Andre.

**The gate is on the reachable number, and the reader-facing number is reported
beside it every run (2026-08-26).** A gate that fires on another stage's defect
teaches people to ignore gates. A report that hides the reader's experience is
worse. Both are printed by the same test on every run. Authority: Andre.

**The floor moved on evidence, not on taste (2026-08-26).** The estimate before
measuring was 0.35 to 0.45. The measurement put it at the bottom of that range
and said why: past 0.35 the cost in right answers becomes larger than this
instrument's own spread. Authority: Andre, Rule #10.

**The bar was re-derived rather than lowered, and the difference is the four
arms above (2026-08-26).** A gate that fails after a fix landed can be met two
ways: move the number until it passes, or find out what changed. Holding the
corpus, the labels and the vectors constant one at a time showed the ranking had
not moved at all, so 0.85 was never the system's number - it was the number of
an archive with 44.5% of its vectors. Authority: Andre, Rule #10.

**The floor stayed where it was because the noise did (2026-08-26).** The
corpus grew 3.7x in scored pairs and the same-domain noise distribution did not
shift past the third decimal. Raising a floor the measurement says is correct,
in order to silence one probe, is fitting the knob to the test. The probe was
what broke, and it is recorded rather than removed. Authority: Andre.

**The label set is not repaired in the same commit as the bar (2026-08-26).**
Judging only the items the ranker put in the ten slots can only raise recall -
the metric would be choosing its own ground truth, and the alarm would be gone.
A sound re-label pools deeper than the slot count from a dense and a lexical
retriever and lands on its own, so a reader of the history can tell whether the
number moved because the labels moved or because the system did. Authority:
Andre, Fowler.

### Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Raise the five-query browser fixture's bar and call it the instrument | At n=5 the standard error at recall 0.8 is 0.18. It cannot see a ten-point regression, so raising its bar would buy noise. | Andre |
| Gate on mean reciprocal rank | The result list is flat and capped and carries no rank cue. Rewarding first place would measure a claim the product does not make. | Andre, Jony |
| One right answer per query | A topic query has many. Single-gold labelling reports a working system as broken and makes the number a function of which answer the labeller happened to pick. | Andre |
| `found / len(gold)` with no cap | Twenty right answers cannot fit in ten slots, so a perfect retriever would score 0.5 and a stingy labeller would score higher than a thorough one. | Andre |
| Substitute the vertical for the missing entity slug in tier one | A vertical holds 72 to 168 items, which caps recall@10 at 0.06 and measures nothing. Substituting a different grouping would also manufacture a green number from a dimension the product does not use. | Andre |
| Use an item's own key points as a free query | The summarizer wrote them. A query generated by the model whose output is being retrieved shares its failure modes, which is the LLM-as-judge ban in `CLAUDE.md` section 0a. | Andre |
| Freeze a corpus snapshot into the fixture so the number never moves | It would duplicate 300 KB of already-committed vectors and would stop the eval from noticing the archive. Published days are immutable, so a labelled answer cannot vanish - and a separate test says so loudly if one does. | Fowler |
| Lower the labels or raise the floor until recall passes 0.5 | The brief for this work said not to, and it was right: an instrument that reports bad news is doing its job. | owner |
| Lower `recall_min` until the failing gate goes green | It is the same move as the row above, with a different knob. The bar has to come from a measurement of what the system does now, and that measurement had to separate a coverage change from a ranking change before any number could be written down. | Andre |
| Drop the 13 newly answerable queries, or the queries that score worst | The queries did not change; the corpus did. Removing `crude-oil-price` because it scores 0.000 would delete the single clearest piece of evidence that the labels are incomplete. | Andre |
| Count an unlabelled item in a slot as correct because it looks relevant | That is the metric grading itself. Relevance has to be judged against a written intent by a rule applied to every candidate, in a pool deeper than the slots, or the number means nothing. | Andre |
| Raise the floor to 0.42 so every probe returns nothing | 0.42 silences the smartwatch match and does not silence "competitive bridge bidding" matching an offshore wind auction, which needs 0.44 and 0.073 of recall. The floor would be set by whichever probe happened to be written down rather than by the noise it exists to cut. | Andre |
| Assert "at most one hit" per probe instead of none | It converts a promise the empty state makes into a promise it usually makes. Either the archive has nothing close or it does. | Reader |

## The ledger

Every item produces one row, appended to a committed CSV. It is appended by CI, read by the dashboard, and never recomputed at read time (Rule #1). The row shape is a contract like any other, versioned and changelogged ([../../CLAUDE.md](../../CLAUDE.md) section 11).

Committing the scores rather than deriving them is what makes a claim about last quarter a lookup instead of a re-run against a model that has since changed.

The ledger header is part of the contract. A writer now refuses to append when the committed header no longer matches `EvalRow.csv_columns()`. A contract test also parses every committed `state/*.csv` with Python's `csv` module and fails if any data row has a different cell count from its header. This protects the file itself, not only the append path.

**The ledger records measurements, not runs.** The writer refuses a row whose
address, pipeline fingerprint, output words and scorer version all match a row
the file already holds. Nothing in that recorded measurement identity changed,
so a second row would only inflate the denominator every rate is computed
against. Article-input identity is not part of this de-duplication key.
`item_id` is deliberately absent too: it is a slot on a page, not the item.

Any of the four differing makes it a new measurement and it lands: different words under identical inputs is the determinism violation the ledger exists to catch, and the same words read by a different scorer is a reading worth keeping.

Four rows written before this rule are still committed - four items on 2026-08-23 that a second day re-summarized because `state/published.csv` had no record of the day before. They are honest history and stay. Anything counting the whole ledger de-duplicates on those four columns first.

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
reached a reply, and none did; and `sanitize()` runs before the request is built
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

## See also

- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the controlled procedure for testing and adopting a challenger.
- [pipeline-loop.md](pipeline-loop.md) - where the Evaluate stage sits.
- [digest.md](digest.md) - how a confidence band reaches a reader.
- [config.md](config.md) - the band thresholds and retry budget.
- [principles.md](principles.md) - principle 6, the belief this page implements.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the prompt asks for, including the hedges these metrics check.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the eval-row contract.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the stamp every row carries, and why an unchanged item writes none.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the published surface, including the search the retrieval section measures.
- [../../.github/agents/andre.agent.md](../../.github/agents/andre.agent.md) - the persona who owns metric choice.
