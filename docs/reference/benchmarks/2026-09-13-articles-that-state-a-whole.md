# How often an article states a whole its parts add up to, 2026-09-13

**Last Updated**: 2026-09-13

Frozen. This is one run on one day; it is not updated when a later run
disagrees. A later run gets its own record.

`pie` may only be drawn against a whole the article **declared**, never one the
planner summed
([`../../architecture/publishing/visuals.md`](../../architecture/publishing/visuals.md),
[`../../../TODO/20260905-16-composition-vocabulary-plan.md`](../../../TODO/20260905-16-composition-vocabulary-plan.md)
row #3). Nobody had counted how often an article declares one, so the template
was about to be sized against a guess. This is that count. It **sizes** the
template and does not gate it: the owner has already ruled that `pie` ships
whichever way the number falls (plan 16 row #1 decision 2).

**The definition is the artefact here, not the number.** A count with no
definition is a figure a later reader can neither reproduce nor argue with, so
the definition is written first and the count follows it.

## The definition

An article **states a whole** when all five of these are true.

| # | Rule | Why it is there |
| --- | --- | --- |
| 1 | It writes a total and, in the same unit, writes two to five parts | Two, because one part and a total is not a composition. Five, because beyond that an angle is unreadable and `pie` is refused anyway |
| 2 | The written parts add up to the written total, within 0.5 percent of the total | Articles round their own figures. Three shares written to one decimal need not total exactly |
| 3 | Every part is larger than nothing and smaller than the total | Without it, the tolerance admits `85% = 85% + 0.26%`, which is a composition of nothing |
| 4 | The total and every part sit inside 600 characters of each other | About a paragraph of news prose. A total in the first line and a part in the last is not something a reader meets as one statement |
| 5 | One of the article's own joining words sits between the first of them and the last | `comprises`, `of which`, `plus`, `made up of`, `out of`, `the rest`, `total`, `respectively` and twenty more, in one closed list. Declaring is a thing the prose does, not a thing arithmetic does |

Every number is the article's own characters. Nothing is converted between
units - a dollar figure never joins a rupee figure - nothing is inferred, and
**no model reads anything**. The test is arithmetic over numbers a regular
expression found, plus a word list.

**What it counts.** From `corpus/corpus.jsonl`, a community fund story:
`GBP 100,000 = GBP 80,000 + GBP 20,000`, written as "a GBP 100,000 community
benefit fund ... Of the total fund, GBP 80,000 will be administered by Point
North ...". One total, two parts, one unit, one paragraph, and "Of the total
fund" joining them.

**What it does not count.** From the same corpus, a market report: "the Nifty 50
closed 33 points, or 0.14%, lower ... The Nifty Midcap 150 index inched up by
0.07%, while the Smallcap 250 index declined 0.21%". `0.14 + 0.07 = 0.21` is
true and means nothing - three separate indices. This one **does** pass the
screen, which is the finding below rather than an aside.

## Conditions

| | |
| --- | --- |
| Instrument | `backend/utilities/measure_declared_wholes.py`, `--sweep` |
| Runtime | CPython 3.14.2, Windows 11 (26200) |
| Box | A developer machine, not a runner, with four other agents working on it |
| Population | `corpus/corpus.jsonl` - 1,444 articles, 14,544,738 bytes, harvested 2026-08-23 to 2026-09-10 |
| Found in it | 11,573 quantities, 8.0 an article |
| Null seed | `20260913` |

**The corpus is the population because it is the only one that can answer the
question.** The question is about the **article**, and the article's own text is
in `corpus/corpus.jsonl` and nowhere else a reader can reach: a published day
under `frontend/public/digest/` carries our summary and a link, never the source
body ([`../../../CLAUDE.md`](../../../CLAUDE.md) section 0a). The visual planner
reads the article too, so this is also the text the `pie` gate would see.

**Two things the population is not.** It is not every article the pipeline
fetched: `corpus.keeps_its_counterweights` drops a row whose summary hedged, went
unfaithful to a number, or came from a suspect extraction, so the corpus is a
sample of articles that summarised **well**. One of those filters is
`unsupported_numbers == 0`, which a number-dense article is likelier to trip, so
if the sample is biased at all it is biased **against** the articles this count is
looking for. And it is a rolling window rather than an archive - `corpus.roll`
evicts the oldest on every harvest - so this is 19 days of articles and not all
of them.

## The sweep

Rule 4's window, swept. `stated` is the definition above. `implied percent`
counts two to five percentages adding to 100 where the article never writes the
100. `null` is each arm re-run with every value re-dealt at random from the pool
for its own unit, keeping every character position, every unit, every article's
quantity count and every joining word exactly where it was.

| Window | stated | its null | ratio | implied percent | its null |
| --- | --- | --- | --- | --- | --- |
| 150 characters | 21 (1.45%) | 6 (0.42%) | 3.5x | 1 (0.07%) | 5 (0.35%) |
| 300 characters | 37 (2.56%) | 9 (0.62%) | 4.1x | 6 (0.42%) | 11 (0.76%) |
| **600 characters** | **72 (4.99%)** | **14 (0.97%)** | **5.1x** | 22 (1.52%) | 17 (1.18%) |
| 1200 characters | 96 (6.65%) | 26 (1.80%) | 3.7x | 49 (3.39%) | 29 (2.01%) |
| the whole article | 154 (10.66%) | 64 (4.43%) | 2.4x | 124 (8.59%) | 73 (5.06%) |

At 600 characters the 72 articles split by unit as percent 27, US dollar 17,
rupee 13, megawatt 4, and eleven units once each. They split by part count as
**50 with two parts, 15 with three, 4 with four and 3 with five** - so the
articles with the three or more parts a circle is actually for are **22 of
1,444, 1.5 percent**. Thirteen unit groups across the corpus were too large to
search and were skipped rather than counted as misses.

### What rule 5 bought

| At 600 characters | stated | its null | ratio |
| --- | --- | --- | --- |
| rules 1 to 4 only | 117 (8.10%) | 50 (3.46%) | 2.3x |
| rules 1 to 5 | 72 (4.99%) | 14 (0.97%) | 5.1x |

The joining words removed **72 percent of the null hits against 38 percent of
the measured hits**. A rule that cut both alike would be an arbitrary trim; one
that cuts chance harder than signal is tracking something real.

**Rule 5 was added after the first run**, when the arithmetic-only screen came
back mostly coincidence. The list was then written in one pass from what
composition means, and no entry has been added since to rescue a hit the screen
was missing. Only the author can say which of those two happened, so it is said
here.

### What the tolerance costs

The same sweep with rule 2 set to exact rather than 0.5 percent:

| At 600 characters | stated | its null | ratio |
| --- | --- | --- | --- |
| within 0.5 percent | 72 (4.99%) | 14 (0.97%) | 5.1x |
| exact | 56 (3.88%) | 11 (0.76%) | 5.1x |

The tolerance buys 16 articles and 3 coincidences and moves the ratio not at
all, so nothing in this record turns on it.

## What it settles

**At most one article in twenty writes a whole this definition can see** - 72 of
1,444, 4.99 percent - and at most one in sixty-six writes one with the three or
more parts a circle is for. Both are **upper bounds** and neither is the rate.

**The implied-percent arm is refused, and the measurement is why.** Below 600
characters it finds fewer articles than its own coincidence floor - 1 against 5,
then 6 against 11 - so it is detecting nothing. A set of percentages adding to
100 is what percentages do. Ruling it in would also have the planner assert
exhaustiveness the article never claimed, which is plan 16's own escalation
trigger reached by a side door. What the reader loses is real and worth naming:
the survey and vote breakdowns that write "45 percent, 30 percent, 25 percent"
and never write "100 percent" get no circle. They keep the story and the numbers;
they lose the picture. (Editor, 2026-09-13.)

**The window stays at 600 characters.** Two of the three hits that read as
genuine put the total in one sentence and the parts in the next, so a
one-sentence reach cuts the shape the honest cases have. Tightening to 150
characters leaves 15 articles above the floor instead of 58 and buys a precision
the floor says is not there; loosening to 1200 adds 24 hits while the floor
nearly doubles. (Editor, 2026-09-13.)

## What it does not settle

**How many of the 72 are real. This is the important one.** The screen cannot
tell a stated composition from a numeric coincidence that happens to share a
paragraph with a joining word, and the examples show it failing at exactly that.
Of the first twelve hits in corpus order, **three read as genuine** - the
compound-interest balance, a combined GDP figure, and the community fund above.
The other nine are three unrelated stock indices, a list of twenty-one separate
IPO premiums, a man's body weight.

**That three-of-twelve is an agent observation and not a measurement.** An agent
read twelve printed excerpts on 2026-09-13 and judged them: n is 12, the sample
is the first twelve rather than a random twelve, there was one rater, the rater
was not blind, and the rater is a model. It satisfies
[`../../../CLAUDE.md`](../../../CLAUDE.md) section 0a - it grades no published
summary, grades no published visual, and selects nothing to publish - but two
things follow from the label and bind: **no threshold, config value or template
decision may rest on it**, and it may never be re-run as a scorer over the hit
list, because the moment it decides which hits count it has started selecting.
(Andre, 2026-09-13.)

**The null under-states chance rather than estimating it.** Inside one article
the quantities of a unit have correlated magnitudes - twenty-one IPO premiums are
all small percentages - and drawing replacements from the whole corpus breaks
that correlation, so a null article is arithmetically easier to pass than a real
one. Every ratio in the sweep is therefore an upper bound on the signal.

**Nothing about recall.** "Upper bound on the true rate" holds only if the screen
finds nearly every real declaration, and nothing here tested that. The unit
regular expression, the closed cue list and the group cap all leak, and a
composition written in words rather than digits is invisible to all of them.

**The 5.1x is a maximum over five windows**, chosen as the best of the family it
was measured against, so it flatters the signal by an amount nobody has measured.

**Nothing about a runner, and nothing that needs one.** The counts are arithmetic
over committed bytes and travel unchanged; a re-run on any box prints the same
numbers for the same seed.

## What would settle it, and what it costs

**One person marks all 72 hits genuine or not against the definition above.** The
instrument already emits them - `--window 600 --examples 72 --json` - so it needs
no new code, costs one to two hours of one person's attention, and converts the
headline directly: the true rate is 4.99 percent times the precision it measures.
Record the count with a Wilson interval. Until somebody takes it, this record's
three figures are quoted side by side and never one alone: **4.99 percent as the
screen's hit rate, 0.97 percent as a coincidence floor that under-states chance,
and the twelve-example reading with its label.**

## The read, and what it cost

This opens `corpus/corpus.jsonl`, which a run appends to, so it is a growing read
under [`../../concepts/growing-reads.md`](../../concepts/growing-reads.md) and it
is taken under Guardrail #12's escape hatch. It opens **one file, 1,444 rows,
14,544,738 bytes**, reads every one of them, and its cost rises with every
harvest. A bounded input cannot answer it: the question is the rate over the
whole window, so a sample would answer a different question and carry a spread
nobody asked for. It is run by hand, it is not on the daily path, and **no test
repeats it** - `backend/utilities/` is outside `testpaths`, so pytest never
collects it ([`../../../CLAUDE.md`](../../../CLAUDE.md) section 13).

Parsing the 1,444 articles took **0.43 s at best and 3.21 s at worst over six
separate invocations**, spread 2.78 s, and a whole sweep of five windows and four
arms finished inside four seconds on the quiet runs. Those are developer-machine
durations and an order-of-magnitude check and nothing more
([`../measurements.md`](../measurements.md)), taken on **Windows 11 build 26200
with four other agents working on the box**, which is most of why the worst
reading is seven times the best. The point they support is only that this is a
thing a person runs while waiting, not a thing that needs a job.

## See also

- [`../measurements.md`](../measurements.md) - the instrument log, which carries the figure now in force and links here.
- [`../../architecture/publishing/visuals.md`](../../architecture/publishing/visuals.md) - the declared-whole rule this count sizes, and `share_of_declared_whole`.
- [`../../concepts/growing-reads.md`](../../concepts/growing-reads.md) - what a read over a growing collection declares.
- [`../../../TODO/20260905-16-composition-vocabulary-plan.md`](../../../TODO/20260905-16-composition-vocabulary-plan.md) - the plan this row belongs to, and the owner decision that `pie` ships either way.
