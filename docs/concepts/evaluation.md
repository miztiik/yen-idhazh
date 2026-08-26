# Evaluation

**Last Updated**: 2026-08-26

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

### Current implementation gap

The production and validation callers currently pass `article.text` as both the
model-visible text and the full text. `Article` persists only the truncated
model-visible body. The two HHEM inputs are therefore identical and the
documented truncation gap is zero by construction.

Do not use `hhem_delta` as truncation evidence until extraction carries the
sanitized full body to the scorer without sending it to the summarizer or
publishing it. A model-adoption comparison must capture both forms once and
replay the same bytes for every candidate.

Evaluator identity also needs repair. `HHEM_REVISION` is the mutable string
`main`, and `weights_digest()` hashes the model name plus that string rather than
the loaded weight bytes. A scorer version can therefore stay constant while the
Hub serves different weights. Pin an immutable revision and observe the loaded
weights before using HHEM to select a model.

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
| **Compression** | Summary length over source length. **Recorded, never flagged** - see below. |

These are deterministic and cost effectively nothing, which is why they are preferred over an additional model pass. They also run whether or not a faithfulness model is available, which makes them the floor the whole instrument rests on rather than an accessory to it.

## Two columns that score the article, not the summary

Every metric above compares our summary to the article. None of them asks what the article was worth. A faithful, well-covered, correctly-hedged summary of an unsourced rumour scores high on all of them and is still an unsourced rumour.

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

### Current label-queue implementation gap

The current queue cannot show the evidence this section requires.
`state/scores.csv` carries neither summary text nor extracted article text, and
`label_queue.py` prints a missing-summary fallback. The draw is emitted in
sequential HHEM-decile blocks, which leaks the hidden score gradient through
order.

Calibration is blocked until the queue joins to a frozen local evidence package
containing exact source and summary text plus source digest, and globally
shuffles the selected rows before display. Article bodies remain local and
uncommitted.

**The exact remaining requirement**, counted on the committed ledger 2026-08-24:

| What | Have | Need |
| --- | --- | --- |
| Labels | **0** | 60 |
| Distinct run-days at one `scorer_version` AND one `pipeline_fingerprint` | **1** (`2026-08-24`) | 10 |
| Eligible rows | 731 | not the constraint |

Fixed `scorer_version`:
`hhem-2.1-open@6a30c896;weights-cffb0b41;metrics-3;bands=0.80/0.50;lead=0.30`.
Fixed `pipeline_fingerprint`: `969b1917...d2b945`. Note the band values sit
**inside** the scorer version string, so moving a threshold mints a new scorer
version and restarts the count. That is correct, and it is also why a cut cannot
move halfway through a collection.

**Nothing here may move a threshold.** The instrument exists; the labels do not.
Until both the label count and the run-day count are met, any re-cut is a number
chosen so a chart looks humbler.

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

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Let lead coverage or a dropped hedge force `low` | It overcorrects. A good summary of a badly-extracted or narrow source can miss the lead and still be faithful to what it says. | owner |
| Re-cut the faithfulness band thresholds to reduce the `high` share | A band share is not an error rate. Choosing 0.90 over 0.80 would choose how much of the digest is called `high` and only then discover what `high` means. The decision needs human labels, not more unlabelled rows. It also changes nothing the reader sees: `high` prints no item-level copy. | Andre, Reader |
| Delete the four duplicate rows the old writer left in the ledger | They are an honest record of a run that really did re-summarize those items. The ledger is append-only, and rewriting history to make a denominator tidier is the band-aid, not the fix. | Fowler |
| Store `band_reason` on the eval row as well | It is derivable from four columns already on the row, and adding a column to a committed append-only CSV is a migration bought for nothing. | Fowler |
| Print both reasons when both counterweights fail | Two sentences on one item in a meta row is a paragraph. A reader gets one thing to check. | Reader |

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

It produces **zero queries**, because no published item carries an entity slug.
`DigestItem.entities` is copied from `Article.entities` and no stage in the
pipeline ever writes that field - nor `lenses`, nor `events`. Three declared
taxonomy dimensions are empty on all 2,121 committed items. The tier is built to
its specification anyway, so that it becomes the instrument it was designed to be
on the day entities are populated, and a test asserts the emptiness by name so
that the day it stops being true somebody is told.

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
