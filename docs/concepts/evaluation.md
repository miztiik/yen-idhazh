# Evaluation

**Last Updated**: 2026-08-23

How a summary is judged, why one number is never enough, and the rule that keeps the measurement honest. This page fixes the vocabulary; the concrete metric implementations, thresholds and the golden-set contents are owned by the plan-doc and the eval subsystem doc, and the tunable bands live in [config.md](config.md).

## The problem being solved

Every summary reads equally confident. A wrong one is not visibly different from a right one - that is what makes generated text useful and what makes it dangerous. A reader cannot audit it, and the person who built the pipeline stops reading the output within a week. So the system has to measure its own work on **every item whose inputs changed**, continuously, and the measurement has to be committed rather than recomputed on demand.

That qualifier is the only legitimate way to do less work, and it is free: an item whose pipeline fingerprint matches was not re-summarized, so there is nothing new to measure ([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)). Sampling is a different thing entirely, and it is not done - see the rationale below.

The failure this guards against is not dramatic. It is a slow one: extraction quietly breaks on a site redesign, summaries start describing navigation chrome, and every score stays healthy because the summary is perfectly faithful to the garbage it was given.

## Faithfulness, scored twice

The primary measure is **faithfulness**: does the summary assert things the source actually said? It is scored twice on purpose:

- against the text the model **actually saw** (post-truncation), and
- against the **full article**.

A single score cannot distinguish "the model invented something" from "the model faithfully summarized the half of the article we gave it". The **gap between the two** is the cost of truncation, and it is invisible unless you measure both. A large gap flags the item as a truncation artifact rather than a hallucination - a different defect with a different fix.

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
before using the bands as a distribution.

## Per-item scores cannot see drift

Per-item scores measure variance *within a day*. Drift is a movement *across months*: the model runtime changed, a source redesigned its pages, a prompt was edited. Those are invisible in single-item scores and require a second instrument - a fixed set re-run on a schedule, producing a dated row, with alert thresholds on the aggregate.

Two design consequences:

- **Every drift row is version-stamped** with the runtime build, the model file hash and the scorer version. A deterministic output can change because the runtime changed, not because the model did, and a benchmark that cannot tell those apart raises false alarms.
- **The fixed set is refreshed on a schedule.** A frozen golden set stops representing the live corpus and quietly becomes a museum.

A drift detector that has never fired has not been shown to work; it is tested by replaying the set against a deliberately degraded input and confirming the alert fires.

## Design rationale

**The band is one function (2026-08-23).** The old code had one function for rows with a faithfulness score and another function for rows without one. Only the first path wrote the eval row, so `lead_coverage` and `hedge_dropped` were measured and then ignored by the reader-facing band. One function removes that split. Authority: Fowler.

**Failed counterweights cap at `medium` (2026-08-23).** A low lead-coverage score or a dropped hedge reduces confidence, but it does not prove the whole summary false. Unsupported numbers still force `low`, because a wrong figure is a direct false claim. Authority: owner, resolving the known-defects open question.

**Lead entities do not cross line breaks (2026-08-23).** The source's title and body can be adjacent without sentence punctuation. Treating the newline as ordinary whitespace created impossible entities such as `biodiversity loss\nwe`, which counted against the summary and could never match it. A line break now ends the entity run while spaces and tabs still join names inside one line, such as `US President Donald Trump`. Authority: Andre's metric boundary, implemented as a structural bug fix.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Let lead coverage or a dropped hedge force `low` | It overcorrects. A good summary of a badly-extracted or narrow source can miss the lead and still be faithful to what it says. | owner |
| Re-cut the faithfulness band thresholds to reduce the `high` share | A band share is not an error rate. Choosing 0.90 over 0.80 would choose how much of the digest is called `high` and only then discover what `high` means. The decision needs human labels, not more unlabelled rows. It also changes nothing the reader sees: `high` prints no item-level copy. | Andre, Reader |

## Why this is a census and not a sample

Scoring every changed item costs something, and the obvious economy is to score a sample instead - every third day, say, or only the sources that are easiest to work with. It was proposed, examined and rejected. The reasons are worth keeping, because the proposal will look sensible again in six months.

**A per-item claim to a reader cannot be backed by a sample.** Every item on the page carries a confidence signal, and a low-confidence item publishes *marked*. If most items are never scored, most items have no signal, and there are only three things to do with them: render them unmarked, which silently turns "not measured" into "fine" on the reader's page; mark them "unchecked", which puts a caveat on almost the whole digest; or delete the signal. All three are worse than paying for the measurement.

**Sampling by source is the one axis guaranteed to bias the result.** The sources that are cleanest to work with - institutions publishing one column of semantic HTML, in plain declarative prose - are exactly the ones the pipeline finds easiest. Scoring only those measures the system where it cannot fail. Worse, it disarms specific instruments: dropped hedges essentially never occur in institutional prose, so that metric would report zero forever and read as a passing test. And extraction rot - the slow failure this whole page exists to catch - concentrates on the messy sources a clean-source sample never fetches. That is a smoke detector installed in the room that cannot catch fire.

**The economics do not justify it.** The deterministic counterweights are string operations - a rounding error against the cost of generating the summary in the first place. Only the faithfulness model costs anything real, and rationing it is a decision that should follow a measurement rather than precede one. The rule: measure the faithfulness scorer's share of per-item wall-clock, and if it exceeds a stated share of the budget, sample *it* alone - stratified across source tiers, drawn within every day rather than on alternate days, selected deterministically, and never below the rate at which a month-over-month comparison stays valid. The counterweights are never sampled.

**If a sample is ever taken, it is recorded on a written row, never as an absent one.** The ledger already has exactly one legitimate reason for a missing row - the fingerprint matched, so nothing was measured. A second reason would make the two indistinguishable and the ledger uninterpretable. And any aggregate built on a sample states its denominator in the open: a count that describes part of the digest may never be displayed as though it described all of it.

**One thing to do regardless:** the reader-facing confidence signal is driven by the counterweights, which are a census by construction and cost nothing. The faithfulness score is the operator-facing instrument that calibrates the bands. That split keeps a reader-facing promise off the most expensive metric in the system.

## The ledger

Every item produces one row, appended to a committed CSV. It is appended by CI, read by the dashboard, and never recomputed at read time (Rule #1). The row shape is a contract like any other, versioned and changelogged ([../../CLAUDE.md](../../CLAUDE.md) section 11).

Committing the scores rather than deriving them is what makes a claim about last quarter a lookup instead of a re-run against a model that has since changed.

The ledger header is part of the contract. A writer now refuses to append when the committed header no longer matches `EvalRow.csv_columns()`. A contract test also parses every committed `state/*.csv` with Python's `csv` module and fails if any data row has a different cell count from its header. This protects the file itself, not only the append path.

The 2026-08-23 repair kept positions stable. It measured `state/scores.csv` with Python's `csv` module: 33 header names and 19 data rows, all with 33 cells. Ten historical rows predated `score_ms`, so they now carry the contract default `0`. All 19 rows predated `evidential_density` and `speculative_density`, so those cells stay empty as CSV nulls.

**The row is self-describing.** It carries the date, the source link and the title, not only the scores - so that a row still means something after the day it describes has been pruned from the published site. Those columns exist from the first row, because adding them after a prune cannot recover what was already lost.

That title is the **source's** headline, not the one the summarizer wrote ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). An identity anchor has to be the thing that does not vary, and ours is rewritten every run and absent whenever the rewrite missed its range.

**Run-level facts are not ledger rows.** How many items a run planned, finished and failed is a property of the run, not of any item, and it lives in the run manifest - which is committed, dated and published alongside the day. Widening the per-item row to carry a second kind of row would leave every item row with columns that are blank for it and would break the dashboard's one honest question: group the rows by band and count them.

**An item whose inputs did not change writes no row at all.** A re-run that changed nothing measured nothing, and a ledger padded with re-observations of the same summary makes every trend a function of how often the job ran. What counts as unchanged is the pipeline fingerprint ([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)), which is stamped on every row so a trend can be attributed to the inputs that produced it.

## Choosing the model is also a measurement

A published leaderboard ranks models against its own prompt, its own extraction
and its own corpus. Three variables sit between that number and ours, so the
ranking is a better prior than a guess and it is not evidence about this
pipeline. The pick is therefore re-derived here, against our golden set, and the
rule that judges it carries numbers rather than adjectives.

| Condition | Verdict |
| --- | --- |
| The incumbent measures more than `validation_drop_max` (0.10) below its leaderboard number | `rescore_candidates` - the ranking was not describing us, so score the others too |
| A challenger beats the incumbent by at least `validation_switch_margin` (0.05) on our corpus | `switch_and_pause` |
| Neither | `confirmed` |

Three things about this are deliberate:

- **A mean over three articles is not a mean.** A candidate scored on fewer than
  `validation_articles` is ignored, on both sides: an undersampled challenger
  cannot win and an undersampled incumbent cannot be confirmed.
- **Better is not enough.** A model swap changes a persisted contract and
  re-goldens every fixture, so a challenger that is merely ahead changes
  nothing. It has to be ahead by the margin.
- **The rule never applies a switch.** It returns `switch_and_pause` and stops.
  That pause is the whole point of the gate.

The ledger records every candidate rather than only the winner, because a ledger
holding only the winner cannot answer the question someone asks six months
later: was the runner-up close?

## See also

- [pipeline-loop.md](pipeline-loop.md) - where the Evaluate stage sits.
- [digest.md](digest.md) - how a confidence band reaches a reader.
- [config.md](config.md) - the band thresholds and retry budget.
- [principles.md](principles.md) - principle 6, the belief this page implements.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the prompt asks for, including the hedges these metrics check.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the eval-row contract.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the stamp every row carries, and why an unchanged item writes none.
- [../../.github/agents/andre.agent.md](../../.github/agents/andre.agent.md) - the persona who owns metric choice.
