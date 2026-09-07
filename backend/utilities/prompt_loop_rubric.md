# The Editor rubric for the offline prompt loop

**Last Updated**: 2026-09-07

This is the standard the model judge critiques a candidate summariser prompt
against, inside `backend/utilities/prompt_loop.py`. The Editor owns it: it is the
demand side of the loop - what a good summary is for - and it is committed so a
run can be read back.

It has no authority to promote anything. A candidate prompt replaces the
incumbent only when it beats the incumbent on the deterministic, model-free
scorers over the frozen article set. This rubric shapes what the model judge
proposes; the scorers decide what wins. The judge proposes, the scorers dispose.

## What a line has to earn

Every line in a summary earns its place or it is cut. A line earns its place when
it carries a fact the reader would miss without it. A line that restates a line
already written earns nothing, and it is the cheapest thing to cut.

- **The lead survives.** News prose puts the who, the what and the how-much in
  the first sentences. A summary that drops the opening's names and figures has
  dropped the story, and no later sentence buys that back.
- **A number is the source's number.** A figure in the summary that is nowhere in
  the article is the most damaging thing the summary can carry. A number is
  copied, never rounded into a new one and never invented to round out a
  sentence.
- **A hedge is kept.** When the article says a thing is reported, alleged or may
  happen, the summary says so too. A rumour written as a fact is a new claim the
  reporting never made.
- **The summary is not the article.** A stretch copied whole from the source has
  summarised nothing. The words are the summary's own; the facts are the
  source's.

## What the rubric does not do

- **It sets no word count.** Length is a property of the story, not of the
  source. A three-paragraph rate decision can be complete; a long feature can be
  padded. The length bands in `summarize.bands` already size the prose by the
  source's length - the rubric judges whether each line inside that size earns
  its place, never whether the summary hit a number.
- **It never trades the lead's facts, a hedge, or the attribution** for
  brevity. Those are the limits; a candidate that reads more smoothly by dropping
  one of them is worse, not better.

## What the judge may and may not do

The model judge reads the current prompt, this rubric and the deterministic
scores, and proposes a revised prompt. That is model-assisted authoring of an
offline maintenance artefact, and it is all the judge does. It never grades a
published summary, never grades a published visual, and never selects what
publishes. Nothing it produces reaches a reader unless a human, reading the
deterministic scores, commits the winning prompt by hand.

## See also

- [`../../docs/concepts/evaluation.md`](../../docs/concepts/evaluation.md) - the deterministic scorers and why they, not a judge, decide.
- [`../../.github/agents/editor.agent.md`](../../.github/agents/editor.agent.md) - the Editor, who owns this rubric.
