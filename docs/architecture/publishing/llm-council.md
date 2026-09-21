# The LLM-COUNCIL, and why judging has its own clock

**Last Updated**: 2026-09-21

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

## The clock a unit stops on, and the upload that runs either way

**The venue owns both clocks, because the venue owns the runner.** The job
timeout, the checkout, the install and the weights restore are all the council's
and no tenant can see any of them, so `council.shard_timeout_minutes` and
`council.shard_wrap_up_minutes` sit in the council's own config block. The
second is the reserve: how much of the bound a unit keeps back for writing its
records and getting its artifact away.

**What crosses to a tenant is one instant, not two knobs.**
[../../../backend/idhazh/council/deadline.py](../../../backend/idhazh/council/deadline.py)
subtracts the reserve from the bound, adds it to the instant the unit's own
process began, and hands the result over. A tenant handed an instant needs no
config block and no config reader to stop on time, which is how a judge with
neither can still be stopped - and how the clock is gated against a four-line
fake instead of a model.

The zero is the process rather than the job, because only the process knows when
it began: the job's clock started before a checkout, an install and a weights
restore that this reading is not about.

**Nothing in the council checks the instant it handed over.** Only the tenant
knows what a unit of work is and where stopping leaves a readable result, so the
tenant reports which outcome it reached and the council files that answer rather
than inferring one from its own clock. A tenant that ignores the instant is not
stopped early - it is killed on the platform's clock instead, which is the case
the reserve exists to avoid.

**And the upload runs whatever happened to the unit.** It carries `always()`,
because the exposure was never the collecting job dying - it is a unit dying.
Without it a unit that spent most of `council.shard_timeout_minutes` and judged
every pair it reached ships none of them, and tomorrow's run pays for that work
a second time.

## Design rationale: named for the room, not for this month's job

Owner ruling, 2026-09-18. The legs shard a list today and never confer, so
`judges` is the more literal word for what is on disk right now.

**What is coming is not one question.** This loop argues a case, and a case needs
something to adjudicate it - a model, a panel, or a plain heuristic - and some of
those paths put a person in the loop. One roof for all of them, named for the
room rather than for the one job being done in it this month.

`CLAUDE.md` section 1a permits this: a model verdict may run in a production
workflow and may determine publication.

## The venue and its tenants are separate things

**The council runs one judge or many - in sequence, in parallel, or chained -
and depends on none of them.** A judge's development does not wait on the
council, and the council's does not wait on a judge. Owner ruling, 2026-09-21.

`backend/idhazh/council/` is where that sentence is kept true. Nothing under it
imports a judge or names one: a judge is reached through the protocol in
[../../../backend/idhazh/council/tenancy.py](../../../backend/idhazh/council/tenancy.py)
and hands its rows to
[../../../backend/idhazh/council/metrics_sink.py](../../../backend/idhazh/council/metrics_sink.py).
The council records which tenant ran; it never declares which tenants may exist.

Three layers, and which one a reading belongs to is decided by what the reading
is ABOUT, never by what executed it.

| Layer | Owns | Stored |
| --- | --- | --- |
| Council pipeline observability | Did the pipeline work - which units started, which finished, which stopped on their own clock, what each cost | `state/llm-council/` |
| The tenancy protocol | The shape a judge presents: its slug, how many ways its work splits, the store paths it commits, the nights it is behind on, and three units of work. Declared by the council, implemented by each judge, and it names no judge | code, not data |
| The shipping capability | The plumbing only. Takes a validated row a judge hands it and gets it committed. Declares nothing about what is in it | code, not data |
| Judge metrics | Entirely the judge's - its units, its funnel, its own contract | under that judge's own slug |

A judge that runs no model files a row with no model columns, and the council's
record is unchanged.

## A unit uploads what it measured, and the collecting job commits it

Each unit writes one file on its own runner, the workflow uploads that
directory, and the collecting job downloads every one of them and appends each
row to the store the tenant named.

**An artifact rather than a commit, and the reason is that a commit would not
reach the reader.** Every checkout in this workflow names no ref, so each job is
pinned to the commit the run was triggered at. A unit that commits its rows at
22:40 puts them where a collecting job checked out at 22:00 cannot see them, and
the counting step decides whether every unit reported by counting the files it
downloaded. Moving the rows into the tree does not make them safer; it makes
them unreachable.

The tenant's own slug is a directory level inside each upload, so two tenants'
first unit land beside each other rather than on top of each other.

## Design rationale: the council's own path, not the segment store

The digest pipeline files rows through `state/segments/` and a compaction verb
folds them into a head. The council does not, for two reasons.

**Segments solve a conflict this workflow does not have.** They exist for the
case where more than one job commits into one ledger file - the digest pipeline
has four to eight committing units on one day file. The council has one
committing writer, and its day file is already settled on every write by a key
carrying the run id, which is the property segments exist to provide.

**And the compaction verb takes no filter.** It folds every waiting segment,
whatever ledger it belongs to, and then deletes the files it read. The digest
run's own segments are often still waiting when the council starts - 21 files
across five ledgers, measured on `origin/main` on 2026-09-20 - so a council run
that compacted and then committed only its own folders would delete the digest
pipeline's transit copies while leaving the files they were folded into
uncommitted.

**What would change the answer**, stated as a condition rather than a
preference: a unit whose output is too large for an artifact, or which must
survive the artifact's 24-hour retention. Neither is true today. Adopting
segments then also needs the collecting job to see commits made during its own
run, which it has no way to do.

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
