# Encoder comparison 1

**Built**: 2026-10-08

A measurement, not a dataset. It answers one question for plan 63: of the
encoders that could run on this project's hardware, which one best tells two
summaries of the same event from two summaries of different events.

`readings/encoders.md` is the answer. Read "What the numbers mean" before
quoting one.

## Why this exists

The pipeline decides two articles report one story when their summaries sit at
cosine 0.94 or above inside 36 hours. Over the 45 published days that grouped
212 articles out of 15,122, which is **1.4 percent**. Everything downstream of
that decision depends on the numbers an encoder produces, and nobody had
measured which encoder produces the best ones for this job.

**This is not the search encoder.** `backend/idhazh/embed.py` runs a quantized
`all-MiniLM-L6-v2` whose vectors a reader's browser compares against a query it
embeds in the tab. That encoder is sized by what a visitor downloads - 23 MB -
and the runner and the browser deliberately load the same file so the two
agree. The grouping encoder never reaches a browser, so its size is free and
its choice is open. Changing one does not change the other.

## What it is

| | |
| --- | --- |
| Measured by | `backend/utilities/compare_summary_encoders.py`, run by `.github/workflows/encoder-comparison.yml` |
| Hardware | A GitHub `ubuntu-latest` runner: 4 processor threads, 16 GB, no graphics card |
| Read from | the committed digest archive, `frontend/public/digest/` |
| Encoders asked | `config/encoder-comparison.json` |
| The answer | `readings/encoders.md` for a person, `readings/encoders.json` for a program |
| What ran | `manifest.json` - commit, run, runner, input counts, which encoders reported |
| The input | `pairs.json` - the pair set every encoder scored |
| What each shard printed | `logs/` |

## Who wrote the labels

**Nobody. There are none.** This set has no human judgement in it at all, and
that changes what every number on it means.

The run needs to know which pairs of articles report one event. It has no such
list, so it builds a stand-in from a signal the encoders never see - the
generated title. A title in this pipeline is actor plus action with the hype
removed, so the words two titles share carry a real signal about whether they
cover one story.

### Three buckets, not two

A comparison that asks only "can you tell an obvious match from an obvious
mismatch" is one every encoder passes. It would also repeat a fault this project
has already found in its own duplicate judge: that judge is only ever shown
pairs scoring 0.88 or above, so it never sees the error that matters - two
reports of one event written so differently that nothing flags them.

So every pair is sorted by how much of their subject two titles share, and the
middle band is kept.

| Bucket | Rule | Treated as |
| --- | --- | --- |
| Same event | Shares **0.30 or more** of its subject words | A match the encoder should score high |
| Uncertain | Shares **0.10 up to 0.30** | Neither. Never scored right or wrong |
| Different events | Shares **less than 0.10** | A mismatch the encoder should score low |

Every pair in all three buckets is from **two different outlets**, published the
same day or a day apart. One outlet repeating itself is a different question,
so those pairs are dropped.

### Where the thresholds came from

The lower bound is the one that matters, and it was chosen by counting. Over the
44 published days, at a floor of 0.34 the archive yields 3,762 matching pairs;
at 0.30 it yields more than 8,000. The project asked for at least 5,000, so the
floor sits at **0.30** and the caps in `config/encoder-comparison.json` decide
how many of them are used - not the floor, which would otherwise quietly set the
count.

The 0.10 line is where a shared word stops meaning anything: below it, two
titles usually share only a country or a company name that half the corpus
mentions.

### What the middle band reports

Nobody knows whether an uncertain pair matches, so it is never counted right or
wrong. What it reports is a **lean**: the share of those pairs an encoder scores
above the halfway mark between its matching and mismatching averages.

- A **high** lean means the encoder pulls doubtful pairs towards "same". In
  production it will join stories that should stay apart.
- A **low** lean means it pushes them towards "different". In production it will
  leave one story in several pieces, which is the failure the current 1.4
  percent already shows.

Two encoders can separate the easy cases equally well and lean very differently.
That difference is invisible to a two-bucket test and it is the one that decides
what the reader sees.

### What this set cannot tell you

Both outer buckets contain mistakes. Two outlets can write near-identical titles
about genuinely different events, and one event can draw two titles with no
words in common. **So no number here is an accuracy.**

What the stand-in can do is rank. Every encoder scores the identical pairs, so
an encoder that handles the hard cases better scores higher, even though none of
them can be scored absolutely. That is the whole claim.

Plan 63 row R14 builds the set that does carry human judgement. When it lands,
this comparison is worth re-running against it.

## If a shard runs out of time

The reading is written before the first article is encoded and rewritten every
512 articles, each time to a temporary file that is then renamed - so a reader
only ever sees a whole file, and a shard killed at the six-hour limit leaves
behind how far it got and how fast it was going.

`state` says which happened:

| State | What it means |
| --- | --- |
| `loading` | Weights were still downloading. Nothing encoded |
| `encoding` | Stopped partway. `articles_done` and `articles_a_second` are real |
| `measured` | Finished. Every number is there |
| `unavailable` | The model would not load. `reason` carries what the runtime said |
| `stopped` | The encode raised. `reason` carries it |

An encoder that cannot finish inside six hours has answered the cost question
even though it never answered the quality one, and the table says so rather than
leaving the row blank.

## What the numbers mean

**Separation** is the one to read. Pick one likely-same pair and one
likely-different pair at random: how often does this encoder score the
same-event one higher? 1.0 is perfect, 0.5 is a coin toss.

It is used instead of the gap between two averages, because encoders put their
scores on different scales. An earlier attempt at this comparison, run on a
laptop, reported `all-MiniLM-L6-v2` ahead of `bge-base-en-v1.5` on a gap of
0.720 against 0.431 - but bge places unrelated pairs at 0.456 where MiniLM
places them at 0.105, so the gap was measuring the scale and not the skill. A
rank cannot be fooled that way.

**Spread** is kept beside it because it decides something separate. Two encoders
can separate equally well while one leaves far more room between the two groups
for a decision to sit in. A compressed scale makes any fixed cut-off harder to
place and more fragile when the corpus shifts.

**Articles a second** was taken on the runner, under the same four threads
production gets. The two projected minutes follow from it: one for re-encoding
all 15,122 published articles once, one for a normal day's 337. Both matter -
GitHub stops a job at 6 hours, and the day's job also has to summarize.

**Peak memory** is the whole process against the runner's 16 GB.

## What was removed

Nothing. Every article in the named range that has a title, a summary and an
address is eligible. An article the pair builder never paired is simply not
encoded, because encoding an article no pair touches would cost time and answer
nothing.

## How to read a shard that did not report

A model that will not load is recorded as `unavailable` with its reason, and the
run continues. A gated model, a renamed one, or one needing a library version
the runner does not have all land there. That is a finding about the model's
availability, not about its quality, and the row says so rather than going
missing.
