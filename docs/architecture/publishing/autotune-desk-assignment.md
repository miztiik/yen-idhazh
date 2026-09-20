# What decides an article's desk and lens

**Last Updated**: 2026-09-20

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

## See also

- [../../concepts/taxonomy.md](../../concepts/taxonomy.md) - what a vertical, desk, lens and event are, and how they differ.
- [../../concepts/classification.md](../../concepts/classification.md) - how an article is labelled today, and why a label is not a grade.
- [../../how-to/measure-a-classifier.md](../../how-to/measure-a-classifier.md) - how the reference dataset behind an accuracy figure is built.
- [llm-council.md](llm-council.md) - the room a fitted boundary would be judged in.
- [autotune-entity-linking.md](autotune-entity-linking.md) - the sibling question: when a mention is a known entity.
