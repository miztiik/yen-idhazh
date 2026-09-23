# What decides an article's desk and lens

**Last Updated**: 2026-09-23

What puts an article on one desk rather than another, and which lenses it
carries - and what would make those boundaries fit themselves instead of being
drawn by hand.

**Status: a stub. Nothing here is built, and no plan builds it yet.** What is
below is the current hand-set state and the shape a fitted version would take.
Anything stated as future is an intention, not a design of record.

## What is hand-set today

Every vertical in `config/taxonomy.json` carries a `definition`, a `floor`, a
`ceiling` and a `min_feeds`, and every one of those is a person's judgement
written down. A lens is a named rule in the same file. Nothing measures whether a
definition is still drawing the line where a reader would draw it.

[../../concepts/taxonomy.md](../../concepts/taxonomy.md) defines what a vertical,
a desk, a lens and an event **are**. This page is about what **moves** them.
Those are two questions and they must not be answered twice.

## The word this page may not use

[../../concepts/classification.md](../../concepts/classification.md) opens with
the rule: **a classification is a label, not a grade.** So nothing here scores a
desk. What a fitted version would move is a *boundary* - where one desk stops and
the next begins, and how confident a label has to be before it is used.

## What would have to be true before a boundary is fitted

- A judged sample of articles whose desk a person agreed, held separately from anything the fit reads.
- A statement of what a wrong desk costs a reader, because that is what sets how cautious the fit may be.
- A rule that a desk below its `min_feeds` floor is never fitted onto, since a run already refuses to plan for one.

## A fit that moves a word has to rebuild two files, and today neither is rebuilt

**No page owns this rebuild, and this entry says one has to.** A person edits
[`../../../config/taxonomy.json`](../../../config/taxonomy.json) today, so a
person is also there to run the rebuild that the edit makes necessary. A fit has
nobody standing by. Whatever moves a vertical, a desk or a lens without a person
has to move these two files with it.

| id | File | Who writes it today | What a vocabulary edit does to it |
| --- | --- | --- | --- |
| A1 | `config/taxonomy-vectors.bin` | a person, running `python backend/utilities/build_taxonomy_vectors.py` and committing the result | it goes stale, and the next run **stops and names the file** |
| A2 | `frontend/public/assist/index/<YYYY-MM>.json` and its `.bin` | the daily run, for the month it is publishing into | earlier months keep what they held, and only a person-dispatched backfill goes back for them |

**A1 is a tripwire, not a build step, and that is the whole of the tie.** The
file's header carries a digest of exactly the label sentences that were encoded
and the reference of the encoder that encoded them, so a run reading a file built
under a different vocabulary refuses. That is the right failure: a stale file
compares today's stories against last month's lenses and returns a number that
looks exactly like a real one
([`../../concepts/classification.md`](../../concepts/classification.md)). But a
refusal only tells somebody to go and type a command. It rebuilds nothing, and
under a fit there is nobody to tell.

**What moves that digest is wider than it reads.** The text encoded is the
display name and the definition of every active vertical and every active lens
(`assemble.label_vector_texts`) - 11 sentences in 4,307 committed bytes today. So
a display name, a definition sentence, a new vertical, a new lens and a
retirement each move it. An event does not, because events are not encoded, and
an edit to an already-retired entry does not either.

**A2 does not refuse, which is the harder half.** A month's index is derived from
the committed days of that month, and the daily run rebuilds only the month it is
publishing into ([`../../concepts/partitions.md`](../../concepts/partitions.md)).
Nothing records which vocabulary a shard was built under, so nothing can say a
shard is behind. Rebuilding every shard would answer it and is a read that grows
with the archive, which is the read this project does not take
([`../../../CLAUDE.md`](../../../CLAUDE.md) Guardrail #12).

**Delta is the shape, and that is why this is a design question rather than a
command somebody forgot to run.** A1 carries no label ids on purpose, so nothing
addresses a single label and the file is re-encoded whole or not at all - cheap
at 11 sentences, and it rises with the vocabulary. A2 is bounded inside one month
and unbounded across the archive, so its delta has to be a record of which shards
were built under which vocabulary, not a pass that opens them all to find out.

**The precedent to copy is `stages.backfill_vectors`**, the only thing that
rebuilds an earlier month today, and it does so only for a month it rewrote a day
inside. It answers the same question for stale item vectors: a cheap check per
day, a rewrite of only what differs, then a rebuild of only the months it
touched. Two parts of it a fitted version cannot inherit - a person dispatches
it, and it opens every published day to decide.

### What a fitted version owes before it moves a word

- A record of which vocabulary each derived file was built under, so "behind" is a fact rather than a guess.
- A rebuild the run performs for A1, in place of the refusal it raises now.
- A bounded rule for A2 that names the shards to touch without opening the rest.
- A statement of what a reader gets while one file is behind the other, because a word that moves mid-day leaves the two out of step.

## See also

- [../../concepts/taxonomy.md](../../concepts/taxonomy.md) - what a vertical, desk, lens and event are, and how they differ.
- [../../concepts/classification.md](../../concepts/classification.md) - how an article is labelled today, and why a label is not a grade.
- [../../concepts/partitions.md](../../concepts/partitions.md) - which collections are sharded how, and when a shard is closed.
- [../../how-to/measure-a-classifier.md](../../how-to/measure-a-classifier.md) - how the reference dataset behind an accuracy figure is built.
- [llm-council.md](llm-council.md) - the room a fitted boundary would be judged in.
- [autotune-entity-linking.md](autotune-entity-linking.md) - the sibling question: when a mention is a known entity.
- [autotune-search-quality.md](autotune-search-quality.md) - the search index this page's rebuild question covers, and how a moving vocabulary breaks its metric.
