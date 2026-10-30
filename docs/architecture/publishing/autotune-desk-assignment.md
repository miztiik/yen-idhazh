# What decides an article's desk and lens

**Last Updated**: 2026-09-23

What puts an article on one desk rather than another, and which lenses it
carries - and what would make those boundaries fit themselves instead of being
drawn by hand.

**Status: semantic assignment runs; an autotuning loop is not built.** What is
below is the current hand-set state and the shape a fitted version would take.
Anything stated as future is an intention, not a design of record.

## What is hand-set today

Every vertical in `config/taxonomy.json` carries a `definition`, a `floor`, a
`ceiling` and a collection feed floor, and every one of those is a person's judgement
written down. A lens is a named rule in the same file. Nothing measures whether a
definition is still drawing the line where a reader would draw it.

[../../concepts/taxonomy.md](../../concepts/taxonomy.md) defines what a vertical,
a desk, a lens and an event **are**. This page is about what **moves** them.
Those are two questions and they must not be answered twice.

## Similarity is not assignment quality

[../../concepts/classification.md](../../concepts/classification.md) opens with
the rule: **a classification is a label, not a grade.** The current classifier
uses similarity to compare an article with configured desk descriptions; that
score is not evidence that the assignment is correct. A fitted version would
move a *boundary* - where one desk stops and the next begins, and how confident
a label has to be before it is used.

## What would have to be true before a boundary is fitted

- A judged sample of articles whose desk a person agreed, held separately from anything the fit reads.
- A statement of what a wrong desk costs a reader, because that is what sets how cautious the fit may be.
- A rule that a desk below its collection feed floor is never fitted onto, since a run already refuses to plan for one.

## A vocabulary edit reaches the classifier and the search index

The article classifier reads the current configured comparison groups and builds
target vectors in memory at the start of each work run. It does not read or
rebuild a committed taxonomy-vector file. An active vocabulary edit therefore
reaches new work on its next run without a manual asset-generation step.

The published monthly search index is still a separate derived file. It carries
published article data and item vectors, and the daily run rebuilds only the
month it is publishing into. Older days are not silently reclassified when a
vertical, lens or event changes.

| id | File or representation | Who writes it | What a vocabulary edit does |
| --- | --- | --- | --- |
| A1 | Classification target vectors in memory | The work stage, once per consuming run | The next run encodes the current selected entries; nothing is persisted |
| A2 | `frontend/public/assist/index/<YYYY-MM>.json` and its `.bin` | The daily run, for the month it is publishing into | Earlier months keep their existing article labels and item vectors |

**A1 has no stale-file tripwire.** The source entries are re-read and validated
from their configured JSON files, and their vectors live only for that work
process. Thresholds remain separate config values, and no article comparison
scores or target vectors enter telemetry or published payloads.

**A2 still has a bounded update problem.** A month's index is derived from its
published days. Nothing records which taxonomy version shaped each article's
labels, and walking every shard to find changes is a read that grows with the
archive ([`../../../CLAUDE.md`](../../../CLAUDE.md) Guardrail #12). An automated
boundary change would need a bounded rule for which old days or month shards to
rewrite; current semantic assignment applies to newly processed articles only.

**Delta remains the shape of the open design question.** A1 is handled by
re-encoding the fixed configured target lists once per work run. A2 is bounded
inside one month and unbounded across the archive, so a safe historical update
must name the shards to touch rather than scan the tree. The precedent is
`stages.backfill_vectors`, which rewrites only the month containing a day it was
dispatched to backfill.
### What a fitted version owes before it moves a word

- A judged sample of articles held apart from any data used to choose the boundary.
- A stated cost for a wrong desk and a conservative rule for an uncertain match.
- A bounded rule for any older month shards that need reclassification, without scanning the archive.
- A clear account of how feed vertical provenance remains unchanged when semantic desk assignment moves.

## See also

- [../../concepts/taxonomy.md](../../concepts/taxonomy.md) - what a vertical, desk, lens and event are, and how they differ.
- [../../concepts/classification.md](../../concepts/classification.md) - how an article is labelled today, and why a label is not a grade.
- [../../concepts/partitions.md](../../concepts/partitions.md) - which collections are sharded how, and when a shard is closed.
- [../../how-to/measure-a-classifier.md](../../how-to/measure-a-classifier.md) - how the reference dataset behind an accuracy figure is built.
- [llm-council.md](llm-council.md) - the room a fitted boundary would be judged in.
- [autotune-entity-linking.md](autotune-entity-linking.md) - the sibling question: when a mention is a known entity.
- [autotune-search-quality.md](autotune-search-quality.md) - the separate search index and how a moving vocabulary changes its metric.
