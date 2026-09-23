# Evaluation

**Last Updated**: 2026-09-22

How a published summary is judged, and how the judgement is kept honest. This page fixes the vocabulary; the tunable bands live in [config/summary-length.md](config/summary-length.md).

**It is one of three, and a person arrives holding one question of the three:**

| Page | The question |
| --- | --- |
| this page | how is a published summary judged, and how is the judgement kept honest |
| [summary-metrics.md](summary-metrics.md) | what does one number about one summary mean, and what can it not see |
| [qualification.md](qualification.md) | how is a candidate model judged before it may be adopted |

**Whether archive search finds the right story is a different instrument and lives in [search-quality.md](search-quality.md).** The two share no data, no metric and no config knob, and a person arrives holding one question or the other.

## The problem being solved

Every summary reads equally confident. A wrong one is not visibly different from a right one - that is what makes generated text useful and what makes it dangerous. A reader cannot audit it, and the person who built the pipeline stops reading the output within a week. So the system has to measure its own work on **every item whose inputs changed**, continuously, and the measurement has to be committed rather than recomputed on demand.

That qualifier is now the whole of the story rather than a promise: **there is no
skip.** The stamp that was going to define one was deleted on 2026-09-12 along
with the unwired classifier and its ledger, and nothing has asked for a skip
since
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).
A run measures every item it produces. Do not read a missing row as proof that an
unchanged item was skipped - nothing skips.
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
form is ever republished (Guardrail #1).

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

**The committed rows were rewritten**, by a one-shot utility retired on
2026-09-13 with the month layout it addressed, in the commit that added the rule
(`CLAUDE.md` section 11). It recovered rather than guessed. An article under the
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
would show only that the number moves (Guardrail #10). **Read that zero as an
instrument nobody could run, not as a question nobody wants answered.**
`evaluation.labellers` was an empty list until 2026-09-22, and an empty roster
refuses every write by name. Moving this knob is a measurement this project has
not yet taken, not a tuning nobody got around to.

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
**0 of 60, on a roster that was empty until 2026-09-22**. What has changed is
that `evaluation.chunk_words` can no longer be called a neutral number nobody
needs to look at.

**What it does settle is the cost.** A single 1,923-word pass costs **less** than
today's two or three 900-word passes, not more: 4.278 s against 4.815 s a pass on
the hardware in the reference page. Whichever way the label queue eventually
points, a one-slice window is affordable.

## Two rules that are easy to break by accident

**1. The metric that selects can no longer alarm.** It is tempting to generate several candidate summaries and keep the one that scores best. Doing so destroys the score's value as a monitor: once it is the selector, it can no longer tell you that outputs are getting worse, because it is being optimised against by construction. This is Goodhart's law with a concrete cost. The selector and the alarm stay separate.

**2. LLM-as-judge is primary evaluation where applicable.** A model verdict may run in a production workflow, may score live content, and may determine publication ([../../CLAUDE.md](../../CLAUDE.md) section 1a).

Discouragement is not a control, so four things make it structurally hard rather than merely forbidden. `LabelRow` has no author field a model could fill and no nullable one it could leave blank - `labeller` is required and checked against `evaluation.labellers`. The writer is a human-paced CLI with no `--from-file`, no `--model` and no stdin path, so generating labels from a model means writing a second writer in a diff in a pull request. `seconds_spent` has a floor. And the draw module may not import `idhazh.llm` or the scorer, asserted by a test, so the loop cannot close on itself after a refactor by somebody who never read this paragraph.

Not to be done: seeding the queue with model pre-labels for a human to confirm. Confirmation is anchoring, and it turns an independent measurement into an expensive agreement rate with the model - LLM-as-judge with a rubber stamp.

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
frozen committed article set, on all four gate targets. The gate is a Pareto
beat - no worse on every target, strictly better on at least one - not a
weighted sum and not an optimiser. The judge's preference is recorded and
promotes nothing.

The four are `unsupported_numbers`, `lead_missing_rate`, `hedge_dropped_rate`
and `verbatim_run` - `prompt_loop.GATE_TARGETS`, at line 96 of
[../../backend/utilities/prompt_loop.py](../../backend/utilities/prompt_loop.py).
They are computed by `metrics.unsupported_numbers`, by `metrics.lead_coverage`
compared against `evaluation.lead_coverage_min`, by `metrics.hedge_dropped` and
by `metrics.verbatim_run`.

**There is no `metrics.lead_missing`.** `lead_missing` is a `BandReason` member,
declared at line 58 of
[../../backend/idhazh/contracts/eval_row.py](../../backend/idhazh/contracts/eval_row.py)
and returned by the band rule at line 77 of
[../../backend/idhazh/evals/score.py](../../backend/idhazh/evals/score.py). It is
a different thing, in a different file, from the gate target whose name it nearly
is. `CLAUDE.md` called it a scorer until 2026-09-11, so a reader arriving from
that sentence will look for a function that was never there.

That is how it honours both rules at once. **Rule 2** no longer bans a model
judge at all - [../../CLAUDE.md](../../CLAUDE.md) section 1a made LLM-as-judge
primary evaluation - and the loop still keeps the judge off the gate: it authors
a maintenance artefact, never a verdict on a published summary or visual, and
selects nothing that publishes.
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

Scores are bucketed into a small number of confidence bands, and the band - not the number - is what drives behaviour: what gets retried, what publishes with a visible low-confidence marker, and what a reader sees. Bands are tunable ([config/summary-length.md](config/summary-length.md)) and are re-calibrated against the human spot-checks rather than being fixed by taste.

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
source through `url_key` on `state/item-health/<YYYY>/<MM>/<DD>/`. Measured
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

### The label queue, and the four rules that hold a draw honest

**A labeller sees the exact premise the scorer read, or the row is not
labellable.** The run writes that premise and the summary to
`backend/var/evidence/<date>/` and records a `source_digest` on the eval row; the
CLI refuses any row whose text does not match its digest. **All 2,232 rows
written before 2026-08-27 predate that column and are marked not labellable
rather than guessed at** - which is the correct state, not a defect to repair.

**The strata are how rows are chosen, never how they are ordered.** An order that
walks the deciles leaks the hidden score gradient: the number is hidden and the
stratum is not. `draw` returns one global `label_id` sort, and `label_id` is
already a sha256 over the address, the inputs, the words, the instrument and the
draw, so the shuffle needs no seed and two labellers can compare notes by
position. Measured over the 38 rows at `draw_id=d1`: 9 runs of equal decile
before, 28 after.

**A global hash shuffle does not balance a prefix, and the first version of this
rule said it did.** Over those same 38 rows the first ten deciles run 9, 9, 8, 9,
9, 9, 5, 8, 9, 7. Balance is a property in expectation, not per draw. Stopping
early gives a roughly balanced sample, and **a partial draw may not be reported
as stratified.**

**One draw is one `scorer_version`, and that is the whole of the pool rule**
(owner decision, 2026-08-27; completed 2026-09-12). `eligible`, `draw` and
`run_days` require the scorer with no default, because the cuts being calibrated
live inside that string: a row read by a different instrument answers a different
question. **The pipeline stamp left the draw entirely on 2026-09-12**: nothing
writes it, so `strata`, the per-producer mix and
`evaluation.label_min_stratum_rows` went with it, and a draw is one pool whose
figure is read rather than withheld.

Requiring both was unreachable rather than strict - the stamp digests seventeen
inputs, so a reworded prompt or a llama.cpp rebuild resets the count to zero, and
no pair has ever held for more than three consecutive run-days. The trade is
stated rather than hidden: **a rate read off a pooled draw is a prior with wide
bounds, never a calibration.** The tool refuses to let the split go unprinted,
and an empty pool exits non-zero listing every pair with its rows and dates.
Article bodies remain local and uncommitted.

**The exact remaining requirement**, taken by
[`../../backend/utilities/label_queue.py`](../../backend/utilities/label_queue.py)
against the committed ledger on 2026-09-22. These are exact counts over
committed files rather than a timing, so there is no spread: the same commit
gives the same numbers on any machine.

| What | Have | Need |
| --- | --- | --- |
| Labels | **0** | 60 |
| Distinct run-days at the current `scorer_version` | **25** (`2026-08-29` to `2026-09-22`) | 10 |
| Eligible rows at that scorer | 9,402 | not the constraint |
| Rows the draw can fill | **60 of 60**, no decile short | 60 |
| Names in `evaluation.labellers` | **1** | at least 1 |

**The run-day gate is met, and the roster was the thing holding this up.** Every
version of this page before 2026-09-22 read 2 of 10, because the count was taken
on 2026-08-28, four days after a geometry change reset it. It has since run 25
consecutive days at one `scorer_version` - the longest this ledger has ever
held, against a previous record of 3. So the labels are what is missing, and
until 2026-09-22 nothing could collect them: `evaluation.labellers` was `[]`,
and an empty roster refuses every write by name. The list now carries one name.

The current scorer is
`hhem-2.1-open@8e4a2e6e;weights-841b70e0;metrics-3;window=900/150/anchored;bands=0.80/0.50;lead=0.30`.
The band values sit **inside** that string, so moving a threshold also mints a
new scorer version and restarts the run-day count. That is correct, and it is
why a cut cannot move halfway through a collection. What sends the count back to
zero, and what that costs, is in [Design rationale](#design-rationale) below.

**A sitting needs the evidence package too, and that is not in git.** The draw
names 60 rows, and a row is labellable only if `backend/var/evidence/` holds the
premise the scorer read. That directory is gitignored, so on a machine that has
not run the pipeline the queue reports `labellable 0 of 60` and says so before
anybody starts. The package comes from a local run, or from the workflow
artifact for the day being labelled.

**Nothing here may move a threshold.** The run-days are banked; the labels are
not collected. Until they are, any re-cut is a number chosen so a chart looks
humbler.

## The review tree: where a person looks at a day's visuals

The label queue above asks whether a summary is faithful. **The review tree asks
the other half: is the visual the machine kept the visual a person would have
kept?** Nothing has asked it yet, and this is the place to.

It gates nothing, the same way the label queue gates nothing. No publish
decision reads it, nothing downloads it back into a run, and no later row may
make one. **The verdict here is a person's by choice, not by rule.** `CLAUDE.md`
section 1a would now let a model grade a published visual; nobody has asked a
person the question yet, and a person is the instrument that answers it first.

`backend/utilities/review_queue.py` builds one day's tree under
`backend/var/review/<date>/`: a contact sheet a reviewer scrolls, a copy of every
drawing it names, and `queue.json`, the shape the reviewing tools read back.

**Three populations, because three have a producer.**

| Population | What it holds | What a reviewer is judging |
| --- | --- | --- |
| `published` | a chart was drawn and the day publishes it | whether it earned its place |
| `rejected` | a chart was drafted and the item carries none anyway - the validator refused the plan, or the render failed after it passed | whether the machine threw away something worth keeping |
| `none` | no chart was ever drafted. The majority answer by design | whether the story had a picture in it nobody drew |

**The split is read off the run's own decisions, never off the published day.**
A day payload carries `visual: null` for every item without a picture, so from
it alone a chart the validator refused and a story nobody drafted one for are
the same absence. Telling those two apart is most of the point, and
`backend/var/run/<date>/items/*.visual.json` is the only place it can be done.

**A rejected row has no picture to show, and that is the contract rather than a
gap.** `VisualDecision` refuses a spec on an item decided to nothing, so a plan
the validator threw out survives as `drafted_chart` and a `none_reason` and
never as a drawing. The card names the gate that refused it; it cannot show what
the drawing would have looked like.

**A fourth population is named by the plan that asked for this surface and has
no producer.** A config-B case is a second configuration's render of the same
day, and nothing in this build can select one. There is no member for it and no
empty section pretending otherwise, for the reason `NoneReason` already gives
about its own vocabulary: a word nobody can write is a word nobody can retire
and nobody can tell from a bug. It arrives with the row that builds the second
case.

### How a reviewer gets the tree

**Two doors, and they produce the same thing** - the same shape the evidence
package already uses, because it is the same person's evening.

1. **The artifact.** The `assemble` job of `Content refresh` builds the tree and
   uploads it as `review`, kept for seven days.
   `gh run download <run-id> --repo <owner>/<repo> --pattern review --dir /tmp/review`,
   then open `index.html`.
2. **A day you ran yourself.** `python backend/utilities/review_queue.py --date <YYYY-MM-DD>`
   reads the day under `frontend/public/digest/` and the run payloads under
   `backend/var/run/`, which are the defaults, and writes the same tree to the
   same place.

**There is no dispatch of its own, and that is the decision this surface owed.**
A `Content refresh` run is 164 to 184 minutes, and a queued dispatch is
cancelled without an error by the next scheduled run
([github-actions.md](../reference/github-actions.md)) - an expensive and
unreliable way to obtain a contact sheet that the scheduled runs already
produce. What refusing it costs, stated rather than implied: a reviewer cannot
conjure a tree for a day whose artifact has aged out, and has to re-run that day
locally. The seven-day retention is the answer to that, not a dispatch button.
Ruled by Carmack and Fowler, 2026-09-13.

**The tree is a build artifact and was never a page.** Never committed, never
under `frontend/public/`, and bounded by the 500 MB artifact ceiling
(Guardrail #2). The writer refuses an output directory that resolves inside
`frontend/public/` or `frontend/build/` rather than trusting a later scan to
notice, because `backend/var/` is gitignored and a path that drifted under the
published tree would appear in no diff.

**Three mechanisms written for a shipped review surface are now moot, and saying
so is what stops a later plan-doc implementing them.** The proposal this surface
comes from would have served `review/` from the published site, and guarded it
by excluding it from indexing, from sitemaps and from feeds. **There is nothing
to exclude.** A build artifact is never on the origin, so a `noindex`, a sitemap
rule and a feed filter would each be a control over a page that does not exist -
three things to keep correct that protect nothing.

**It degrades rather than failing.** The job that builds the tree also publishes
the day, so `--budget-mb` caps every population in proportion and records each
population's true size beside the number of rows kept. Truncating one
population's tail would produce an artifact that looks complete and is a biased
sample, which is worse than a smaller honest one because nobody can see it
happened.

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
(Guardrail #10). Three days aging out of the widest console window costs less.

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
matching `model_id` and `scorer_version` values. A
missing identity is not a match. After a model or scorer change, a
series with too few earlier articles reports insufficient evidence.

**The pipeline stamp was a third part of that identity until 2026-09-12, and it
is what made the comparison unreachable**: it moved on any of seventeen inputs,
so a reworded prompt inside a window split the window in two and both halves fell
under the minimum. Nothing was compared, and nothing compared reads as no drift
at every call site.

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

**The reason is an identifier and the sentence is copy (2026-08-24).** The published item carries `band_reason`; the site owns the words. Rewording a reader-facing sentence must not need a schema change, and the same identifier can read differently on a phone and in a feed. Authority: the identifier discipline in `docs/architecture/contracts/schemas.md`.

**A re-observation writes no row (2026-08-24).** The page has said since it was written that an item whose inputs did not change writes no row at all, and the writer did not enforce it. The rule was the better one - a ledger of measurements, not of times the pipeline looked - so the code changed. Authority: Fowler, closing known defect 6.

**One column reads the summary against itself (2026-08-26).** Eleven quality columns, and every n-gram machine in `backend/idhazh/evals/metrics.py` intersected the summary's n-grams with the *source's*. Nothing could see a summary that repeated itself, which greedy decoding makes possible and which every other column scores *better* on the worse it gets. Proved on committed fixtures rather than argued: two 26-word summaries of the same article, one saying a clause three times and one saying it once, score exactly equal on `extractiveness` (0.000), `verbatim_run` (0.077) and `coverage` (0.333), and 0.000 against 0.391 on the new one. Authority: Andre's blind-spot finding; nullable and appended, Fowler's layout rule.

**`METRICS_VERSION` did not move for it (2026-08-26).** The constant is folded into `scorer_version`, and this page requires ten distinct run-days at one `scorer_version` before a threshold can move. The count is stated once, in [The human labels](#the-human-labels-the-instrument-and-what-it-still-needs), and it had not once reached 10 when this was decided. A column no band and no derived column reads changes nothing that a row written under `metrics-3` says, so bumping would have spent a banked run-day to record a fact about nothing. Authority: Andre.

**A fingerprint change restarts the run-day count at zero (2026-08-27).** The requirement above has asked for ten run-days at one `scorer_version` and one `pipeline_fingerprint` since it was written, and the page never said what happens when one of the two moves. The count goes back to zero, and it has to. The fingerprint exists so that ten days of scores are ten days of the *same* pipeline; a count carried across a model swap would average two different systems and present the result as one measurement. This is not a policy bolted on afterwards. `model_sha256` is a declared field of `PipelineInputs` in [`../../backend/idhazh/contracts/fingerprint.py`](../../backend/idhazh/contracts/fingerprint.py), and the stamp was a digest over that model's own serialization, so a model swap could not leave the stamp still - and neither could a reworded prompt, a llama.cpp rebuild, a changed truncation cap, or any other declared input. **Nothing has written that column since 2026-09-12 and the method that produced it went on 2026-09-21**, so this rule now describes the rows already committed rather than a stamp a run still takes; what a live run records instead is named values, one per input ([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)). Authority: the determinism contract, read rather than argued.

**The measured reset rate (2026-08-27, `state/scores.csv` and `state/fingerprints.csv` at commit `c08d8b5`).** 2,232 eval rows, written by 18 runs across **5 scored run-days** (`2026-08-22` to `2026-08-26`), carry **5 distinct `pipeline_fingerprint` values** and **4 distinct `scorer_version` values** - one new pipeline stamp per scored day, on average. `2026-08-26` alone carried three different (`scorer_version`, `pipeline_fingerprint`) pairs: the stamp moved at that day's second run and again at its fifth, and the scorer version moved at the fifth with it. Every one of those 2,232 rows names the same `model_id`, `qwen3-8b-q4-k-m` - the model did not change once and the stamp still moved four times, so a model swap is *one* cause of a reset rather than the cause. `state/fingerprints.csv` holds a single row, because the ledger that expands a stamp into its inputs only started on 2026-08-26; four of the five stamps can no longer be expanded at all. Authority: measurement.

**The consequence, and how it was resolved (2026-08-27).** The longest run of consecutive run-days under a single (`scorer_version`, `pipeline_fingerprint`) pair is **3** - `2026-08-24` to `2026-08-26`, under `969b1917...d2b945` - and the pair survived only the first of five runs on the third of those days. Three of ten, once, in the ledger's whole history. Adopting Qwen3.5-9B-Q4_K_M (commit `5d8ba60`, 2026-08-27) moved `model_sha256` and `chat_template_sha256` together, which is the one reset `state/fingerprints.csv` can expand into its cause. At the observed rate of pipeline change, every model or runtime improvement spent the whole window, so the pair requirement was unreachable rather than strict - a live tension between shipping a better pipeline and measuring the one already running. **The owner resolved it on 2026-08-27: count run-days at one `scorer_version`, and carry `pipeline_fingerprint` as a reported stratum rather than a disqualification.** The rejected alternative was to freeze the pipeline for ten days; it was declined because the claim it buys expires at the next prompt change, so the freeze would be paid repeatedly, and because a repository shipping several fixes a day cannot stand still that long. What the chosen rule gives up is stated wherever a result is printed: a rate over a pooled draw is a prior with wide bounds, not a calibration, and a stratum under `evaluation.label_min_stratum_rows` may not move a threshold at all. Measured effect on the same ledger: the drawable sample went from 32 of 60 with seven deciles short to **60 of 60**. Nothing here moves a threshold. Authority: owner. **Completed 2026-09-12**: the stamp stopped being written at all, so the reported stratum, the mix and `evaluation.label_min_stratum_rows` went with it and a draw is one pool.

**How a faithfulness sample is drawn (2026-09-22).** Sixty rows, `evaluation.label_draw_per_decile` from each of ten `hhem` deciles, picked by [`../../backend/idhazh/evals/labels.py`](../../backend/idhazh/evals/labels.py) and by nothing else. Four properties carry the design, and each is there for its own reason. **Uniform across deciles, not crowded at the cuts.** The first question these labels answer is a level question - what does `high` mean at all - and a boundary-weighted draw would speak about 0.75 to 0.85 and stay silent about the rest of the ledger. A uniform draw can be re-weighted to the live distribution afterwards; the reverse is not available. **Deterministic by hash** over the address, the words, the instrument and the draw id, so the same ledger and the same draw id give the same sixty rows on any machine. A draw is reproducible rather than remembered, which is what lets two labellers compare notes by position. **One `scorer_version` is the whole pool**, because the cuts being calibrated are spelled inside that string, so a row read by another instrument answers a different question. **A short decile contributes all it has and the shortfall is printed**, because a stratum that quietly borrows from its neighbour is not the stratum it is named after. The strata pick the rows and never order them: the queue comes back in one global `label_id` sort, so the sequence leaks no gradient. What sixty rows cannot buy is a calibration - a rate over a pooled draw is a prior with wide bounds, and the counts it needs first are in the table above. Authority: Andre.

**The roster carries a name, and an agent still does not fill the ledger (2026-09-22).** `evaluation.labellers` was `[]` from the day the instrument was written. The required `labeller` check refused every write, so no label has ever been recorded, and that is what the **0 of 60** on this page has always measured - the roster, never the demand. The list now carries `miztiik`, the one identity this repository commits under ([../../CLAUDE.md](../../CLAUDE.md) section 8). The owner changes it by editing one line of `config/idhazh.json`, and no schema moves when they do: the field default is still an empty list, so a clone that supplies its own config still cannot record a verdict. **Adding a name does not make the first sitting an agent's job.** `state/labels.csv` is the only file this project treats as ground truth, and a fabricated row in it would be indistinguishable from a real one - worse than no row, because the whole value of the file is that a machine did not write it. So the change that made the queue runnable wrote no row. It proved the write path end to end against a temporary state root instead, which is what [`../../backend/tests/test_labels.py`](../../backend/tests/test_labels.py) now holds. The first sitting is sixty rows at roughly 90 s each, about 90 minutes in one pass - an estimate, because `seconds_spent` is the only pace this project has ever recorded (Guardrail #10). Authority: owner.

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

**The economics do not justify it.** The deterministic counterweights are string operations - a rounding error against the cost of generating the summary in the first place. Only the faithfulness model costs anything real, and rationing it is a decision that should follow a measurement rather than precede one. The rule: measure the faithfulness scorer's share of per-item wall-clock, and if it exceeds a stated share of the budget, sample *it* alone, selected deterministically, and never below the rate at which a month-over-month comparison stays valid. The counterweights are never sampled. That rationing now exists, and it is drawn per run rather than within a day - see [The scorer is sampled by run, and nothing else is](#the-scorer-is-sampled-by-run-and-nothing-else-is) for why the earlier wording changed.

**If a sample is ever taken, it is recorded and never left as an absence.**
Nothing skips, so a missing row today cannot
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

Every item produces one row, appended to a committed CSV. It is appended by CI, read by the dashboard, and never recomputed at read time (Guardrail #1). The row shape is a contract like any other, versioned and changelogged ([../../CLAUDE.md](../../CLAUDE.md) section 11).

Committing the scores rather than deriving them is what makes a claim about last quarter a lookup instead of a re-run against a model that has since changed.

The ledger header is part of the contract. A writer now refuses to append when the committed header no longer matches `EvalRow.csv_columns`. A contract test also parses every committed `state/*.csv` with Python's `csv` module and fails if any data row has a different cell count from its header. This protects the file itself, not only the append path.

**The ledger records measurements, not runs.** The writer refuses a row whose
address, output words and scorer version all match a row
the file already holds. Nothing in that recorded measurement identity changed,
so a second row would only inflate the denominator every rate is computed
against. Article-input identity is not part of this de-duplication key, and the
pipeline stamp left it on 2026-09-12: it stopped being written, so keeping it
would have left a constant empty component in every digest.
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
address, output words and scorer version after work has
run. That is ledger de-duplication, not proof that production skipped inference;
nothing skips
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

### The dedupe is answered by an index, and an index can be wrong

The writer does not read the score rows to answer *do we already hold this
measurement*. It reads `state/score-index/<YYYY>/<MM>/<DD>/`, which keeps one
fixed-width digest a measurement beside the day file it describes - a read an order
of magnitude smaller than the rows, exact, with nothing forgotten
([growing-reads.md](growing-reads.md)). **It files by the ledger's own day since
2026-09-13**, because the fill below takes a partition with no index and the rows
beside it, so two grains in one relationship would be a mapping somebody
maintains. Its rows carry no date, so the committed history was regenerated by
`idhazh rebuild-score-index` rather than split.

**Nothing compares an index that exists against the rows beside it.** Comparing
means reading those rows, which is the bill the index removes, so the writer
fills a partition that has **no** index and leaves every other one alone. That is
a deliberate trade and it leaves one hole: an index that drifted stands for
ever, and the next dedupe admits a measurement the ledger already holds - which
turns a count of measurements back into a count of times the pipeline looked,
and that is the one thing this ledger promises it is not.

Three things put an index out of step and all three are real. A fill a crash cut
short leaves a file that exists and is short, which every later run skips. A
shard grown behind the index's back - rows appended by a branch that merged a
`main` older than the index - leaves digests missing. And an index left at a
grain the ledger no longer uses is not read at all, because a partition name the
rule does not recognise is ignored rather than refused
([partitions.md](partitions.md)).

**The repair is `idhazh rebuild-score-index`, and it checks its own result.** It
drops the index for each month it is named, writes it again from the rows beside
it, then reads the new file back and compares it against the rows in **both
directions**. A rebuilt index holding a digest the rows cannot produce fails as
loudly as one missing a digest they do: a one-directional check passes on an
index that only ever grows, and an index that only grows is what a repeated
dedupe over a re-scored item looks like. It reports what each month had wrong
before it rewrote it, so drift is named rather than quietly absorbed.

It writes the file the partition rule names today and removes no other, so the
third case above is the one it cannot repair on its own: a file at a grain no
reader recognises is invisible to the comparison as well, and a change of grain
has to take its own old files away.

**It is never a step of a run**, for two reasons rather than one. It reads every
score row of every month it is given, which is the read the index exists to
avoid ([`../../CLAUDE.md`](../../CLAUDE.md) Guardrail #12) - so the cover is stated,
never defaulted: `--month` names the months and `--every-shard` is the full pass
over the archive, and the command refuses to run with neither, so a caller that
named neither gets an error rather than the archive. And an index
that repaired itself on a schedule would hide the drift it exists to reveal -
the dedupe would go on being right while nobody learned that something had made
it wrong. Authority: Fowler, 2026-09-12.

A month with no committed shard exits non-zero rather than reporting a clean
pass over nothing, and the refusal comes before any file is touched, so the
months named beside a typo keep the index they had.

**`state/score-archive/` is not a source for a rebuild.** A month past
`observability.scores_full_grain_months` has no rows left to derive anything
from, which is precisely why the archive keeps those digests itself.

### A month past fourteen becomes a summary, and the dedupe survives it

`state/scores/` is the largest store under `state/` - measured 2026-09-03, 5,335
rows in 4,266,655 bytes over two monthly shards - and nothing bounded it. Sharding
by month bounds one file, not the tree.

Deleting an old shard outright would answer the bytes and break two things. Every
published quality claim about that month would lose the rows behind it, and Guardrail
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
- one cohort per (date, run, row version, model, scorer
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
had always been that size. Authority: Andre, under Guardrail #10.

**Measured 2026-09-03** on a developer machine,
 (build 26200), CPython 3.14.2, over both committed shards with three
reads each: 4,266,655 bytes of shard become 557,290 bytes of archive, **13.1
percent**. Three reads gave byte-identical archives, so the spread is zero -
reading a committed file is deterministic. Two thirds of the archive is the digest
index, which is the price of keeping the dedupe exact. What the ratio buys in
years is in
[../architecture/publishing/retention.md](../architecture/publishing/retention.md#what-bounds-the-committed-state-tree).

**It ships in dry run.** `.github/workflows/prune.yml` force-pushes `main` on a
schedule, so a file deleted here stops being recoverable once that prune passes
over it (`CLAUDE.md` section 8). The step prints what a live run would remove and
removes nothing; turning it on is a one-line commit somebody takes after reading
that list. The first files it would take are the day files under
`state/scores/2026/08/` on 2027-10-01.

## See also

- [summary-metrics.md](summary-metrics.md) - what each column on the eval row means, and what it cannot see. Arrive there holding a column name.
- [../architecture/publishing/autotune-summary-quality.md](../architecture/publishing/autotune-summary-quality.md) - the design of record for the other three axes and the loop that would move these thresholds without a person.
- [qualification.md](qualification.md) - the gates a candidate model clears before it may serve, and what a run that judged one proves.
- [search-quality.md](search-quality.md) - the other instrument: whether archive search finds the right story.
- [../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md) - the controlled procedure for testing and adopting a challenger.
- [pipeline-loop.md](pipeline-loop.md) - where the Evaluate stage sits.
- [digest.md](digest.md) - how a confidence band reaches a reader.
- [config/summary-length.md](config/summary-length.md) - the band thresholds and retry budget.
- [growing-reads.md](growing-reads.md) - what the observation index costs, and the cover every read over a growing collection declares.
- [partitions.md](partitions.md) - what a partition file is called, and what a name the rule does not recognise does.
- [principles.md](principles.md) - principle 6, the belief this page implements.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the prompt asks for, including the hedges these metrics check.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the eval-row contract.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the stamp every row carries, and why an unchanged item writes none.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the published surface a confidence band reaches.
- [../../.github/agents/andre.agent.md](../../.github/agents/andre.agent.md) - the persona who owns metric choice.
