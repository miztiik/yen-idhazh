# What decides that a mention is a known entity

**Last Updated**: 2026-09-20

When a name in an article is the entity we already know about, when two entities
are related, and what would make those thresholds fit themselves instead of being
set by hand.

**Status: a stub. Nothing here is built, and no plan builds it yet.** What is
below is the current hand-set state and the shape a fitted version would take.
Anything stated as future is an intention, not a design of record.

## What is hand-set today

`config/watchlist.json` is the registry, written by a person. A story that names
an entity on it takes `collect.watchlist_bonus` (0.5), a flat step somebody
chose. Matching is by term, so an alias nobody wrote down is an entity nobody
finds. [../sources/discovery.md](../sources/discovery.md) owns how the match
reaches the ranking arithmetic.

## Relationships have no owner yet, and that is the larger gap

Nothing in `docs/` says what a relationship between two entities **is** - what
writes one, what it means, or whether a reader ever sees one. **That definition
is owed before anything can be fitted to it**, and it belongs beside the registry
rather than here: a fitted threshold over an undefined thing is a number with
nothing behind it.

Note also that `entities` reach no published page today - they are stripped on
the way out ([../../concepts/classification.md](../../concepts/classification.md)),
so any work here starts as an operator surface rather than a reader-facing one.

## What would have to be true before a threshold is fitted

- A written definition of a relationship, and of what a reader would be told by one.
- A judged sample of matches and non-matches, including the aliases and the near-misses a term list cannot see.
- A rule for what a false match costs, because a wrong entity on a story is a claim we made about a person.

## See also

- [../sources/discovery.md](../sources/discovery.md) - the three primitives, the watchlist match, and the bonus it buys.
- [../../concepts/taxonomy.md](../../concepts/taxonomy.md) - what an entity is, and how it differs from a desk and a lens.
- [../../concepts/classification.md](../../concepts/classification.md) - what is labelled today, and which fields never reach a reader.
- [llm-council.md](llm-council.md) - the room a fitted threshold would be judged in.
- [autotune-desk-assignment.md](autotune-desk-assignment.md) - the sibling question: which desk an article belongs on.
