# Event pairs, read and judged

**Built**: 2026-10-09
**Read**: 2026-10-09

A set of news-summary pairs, each carrying a verdict on whether the two report
the same real-world event. It exists so that the choice of encoder for event
grouping rests on something better than a rule about shared title words.

`pairs.json` is the set. Read "Who wrote the verdicts" before quoting any
number taken on it.

## Why it exists

The pipeline groups two articles as one story when their summaries sit close
enough together. Over the 45 published days that grouped 212 articles out of
15,122, which is **1.4 percent** - in a corpus where five Indian outlets
republish the same wire copy daily. Every attempt to improve it runs into the
same wall: there is no answer key, so no change can be shown to be an
improvement.

An earlier attempt built an answer key from the pipeline's own generated
titles - two titles sharing enough words were called one event. Eight encoders
scored between 0.9905 and 0.9925 on it, an ordering that puts a 22-million
parameter model above a 568-million one. Two independent reviews of that design
reached the same conclusion: the question was too easy to separate the
candidates, and the numbers were being read as a ranking when they were not
one.

The three faults that set this work going:

- **The negatives were easy.** Pairs whose titles shared almost nothing -
  different stories in different words. Telling those apart is free. The
  decision the pipeline actually makes is between one event and its near
  neighbour, and nothing measured that.
- **The labels came from the same place as the text.** One model wrote both the
  title that made the label and the summary that was measured. They agree
  partly because the event is the same and partly because one model wrote both,
  and nothing separates those two reasons.
- **One threshold was chosen to produce a round number.** The title-overlap
  line moved from 0.34 to 0.30 because 0.30 yielded about five thousand pairs
  and five thousand was the figure asked for. That is choosing the ruler to
  suit the answer.

Only a person reading the two summaries - and the two articles behind them when
the summaries do not settle it - escapes all three.

## What it is

| | |
| --- | --- |
| Built by | `backend/utilities/choose_pairs_to_judge.py` |
| Drawn from | the committed digest archive, `frontend/public/digest/` |
| Days covered | 2026-08-23 to 2026-10-05 |
| Pairs | `pairs.json`, one object a pair |
| Verdicts | `same`, `different`, `cannot_tell` |
| Repeated | about one pair in ten appears twice, unmarked and far apart |

## Who wrote the verdicts

**Not a person-written set**, in the sense `corpus/reference-dataset-1` uses
that phrase, and the same warning applies: it changes what a number taken on
this set means.

The verdicts were produced by reading each pair under the rules below - the two
summaries first, and the two source articles where the summaries left the
question open. They are a first pass whose purpose is to be corrected, not a
settled answer.

The `confirmed` field on each pair carries that correction. It is empty until a
person reads the pair and either agrees or replaces the verdict. **A number
quoted from this set says which population it was computed on: all verdicts, or
only confirmed ones.** Those are two different measurements, and the gap
between them is itself worth reporting.

This matters beyond bookkeeping. The verdicts were produced by a language
model, and the summaries being judged were written by a language model. Those
are different models doing different jobs, but a measurement whose answer key
and whose subject are both model output cannot be the thing that proves model
output adequate. Confirmation is what breaks that circle, and until a pair is
confirmed it carries the weaker claim.

## How a pair was judged

**Same event** - one occurrence, however differently told. Wire copy
republished by five outlets is one event. A story told at two lengths, or from
two angles, or in two registers, is one event.

**Different events** - separate occurrences, however alike they read. Two
launches by one agency. Two quarterly results from one company. A match preview
and the match result. Two hearings in one case. Shared actors and a shared
subject do not make a shared occasion.

**Cannot tell** - the summaries do not carry enough to decide, even after
reading the sources. These are counted and kept. A high rate in any group is a
finding about what the summaries leave out, which is worth more than a guess.

## How the pairs were chosen

Not evenly. A thousand decisions spent evenly over the corpus would spend
almost all of them confirming that unrelated stories are unrelated. They were
drawn where the answer is in doubt, and where the encoders disagree with each
other, because that is where a decision between encoders is actually made.

| Group | What it holds | Share |
| --- | --- | --- |
| Encoders differ | One encoder calls it a match, another does not | 35 percent |
| Hard mismatch | Same actors, same subject, different occasion | 20 percent |
| Hard match | One event told two ways, few words in common | 15 percent |
| Settled match | Two outlets, near-identical titles, one day | 10 percent |
| Settled mismatch | Nothing in common | 10 percent |
| No publication time | Neither article carries a usable timestamp | 10 percent |

The two settled groups fix what the top and bottom of the scale mean. The other
four are where the reading time earns its keep.

The group a pair came from is recorded but was not shown while judging. Knowing
a pair was drawn as a hard mismatch is a nudge towards calling it one.

## Reading the same pair twice

About one pair in ten appears twice, shuffled far apart and carrying no sign of
it. Reading the same pair twice and answering differently sets a ceiling on how
steady any verdict on this set can be, and therefore on every number computed
from it.

That figure is reported beside any result quoted from this set. **A measurement
cannot be more reliable than the agreement of its own answer key with itself.**

## What this set cannot do

It does not establish the true rate of same-event pairs in the corpus, because
it is deliberately not a representative sample. Weighting back to corpus
proportions needs the group sizes, which `pairs.json` records for that purpose.

It does not settle whether a follow-up from one outlet should be merged with
the story it follows. That is a question about what a reader should see, not
about what is true, and it is decided elsewhere.
