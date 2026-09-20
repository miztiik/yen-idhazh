# The LLM-COUNCIL, and why judging has its own clock

**Last Updated**: 2026-09-20

The room a model verdict is taken in. `LLM-COUNCIL` is a workflow of its own -
[../../../.github/workflows/llm-council.yml](../../../.github/workflows/llm-council.yml) -
that runs at 22:00 UTC and reads yesterday. This page says what the venue is and
what it obliges; what each judge decides is on the page that owns that judge.

**This page does not hold a verdict rule.** The same-story fold, its slots, its
walk and its damping are
[autotune-content-similarity.md](autotune-content-similarity.md). This page is
the room, and that page is the one case being heard in it today.

## It is a separate workflow because of the budget, not the schedule

At the cap the same-story block permits - 200 pairs, judged in both orders -
that is 400 model calls. At 77.6 seconds a call it is **8.6 hours of model time
run serially**, and a GitHub job is killed at 6 hours with nothing written
(`CLAUDE.md` Guardrail #2).

**Today's median day is 33 pairs, and it would fit inside `digest.yml`
comfortably.** That is the argument for the split rather than against it: sizing
the shape off the median means the first busy day crosses the ceiling and writes
nothing at all.

## Legs judge, and only the fold writes

Four legs run in parallel, one `llama-server` each, and **none of them commits
anything**. A `fold` job downloads every leg's verdicts and makes the writes, so
two processes never share a path.

`fail-fast` is off. **A leg that dies costs its own pairs and nothing else** -
the fold runs anyway and keeps every row the surviving legs produced. What it
will not do is fold a day into the record with a leg missing, because the record
counts what was looked at.

## Design rationale: named for the room, not for this month's job

Owner ruling, 2026-09-18. The legs shard a list today and never confer, so
`judges` is the more literal word for what is on disk right now.

**What is coming is not one question.** This loop argues a case, and a case needs
something to adjudicate it - a model, a panel, or a plain heuristic - and some of
those paths put a person in the loop. One roof for all of them, named for the
room rather than for the one job being done in it this month.

`CLAUDE.md` section 1a permits this: a model verdict may run in a production
workflow and may determine publication.

## What is heard here

| Case | Decides | Status |
| --- | --- | --- |
| Same-story pairs | where the merge line should have been | ships today, [autotune-content-similarity.md](autotune-content-similarity.md) |
| Summary fluency | a 1-5 readability score, summary only, sampled | design of record, [autotune-summary-quality.md](autotune-summary-quality.md) |

Every page named in the See also below describes a knob a person sets by hand
today. Where one of them gains a fitted line, this is the room it is fitted in.

## See also

- [autotune-content-similarity.md](autotune-content-similarity.md) - the one case heard here today: the merge line, its fold, and how it moves.
- [autotune-summary-quality.md](autotune-summary-quality.md) - the next-day fluency judge, and the loop it feeds.
- [autotune-story-prominence.md](autotune-story-prominence.md) - what decides a story's position, hand-set today.
- [autotune-feed-reliability.md](autotune-feed-reliability.md) - what decides how much a feed is trusted, hand-set today.
- [autotune-desk-assignment.md](autotune-desk-assignment.md) - what decides an article's desk and lens, hand-set today.
- [autotune-entity-linking.md](autotune-entity-linking.md) - what decides that a mention is an entity, hand-set today.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the two loops, and where this one sits against the digest.
- [../../reference/github-actions.md](../../reference/github-actions.md) - every workflow, its trigger and its schedule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the 6 h job ceiling) and section 1a (what a model verdict may decide).
