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
that is 400 model calls. A pair costs a measured 110.98 seconds at its worst,
so the cap is **6 hours 10 minutes of model time run serially**, and a GitHub
job is killed at 6 hours with nothing written (`CLAUDE.md` Guardrail #2). At the
average pair, 94.53 seconds, it is 5 hours 15 minutes - which clears the ceiling
by 45 minutes, and a bound has to survive a bad night rather than an average one
([what a judge pair costs](../../reference/benchmarks/what-a-judge-pair-costs.md)).

**Today's median day is 33 pairs, and it would fit inside `digest.yml`
comfortably.** That is the argument for the split rather than against it: sizing
the shape off the median means the first busy day crosses the ceiling and writes
nothing at all.

## Three verbs, and all three are the council's own

The workflow runs `council-prepare`, `council-shard` and `council-settle`, and
nothing else. Each one resolves the slugs in `council.tenants`, calls the
matching member of the tenancy protocol on every tenant it got, and files what
comes back. **Until 2026-09-21 it ran one judge's four commands instead**, and
the command router imported that judge's four stage modules at the top of the
file - so deleting the judge broke every council verb, and the venue's whole
runtime was one tenant's vocabulary.

| The verb | What it does | When |
| --- | --- | --- |
| `council-prepare` | every tenant picks its own work | once a date, in the planning job, before any unit runs |
| `council-shard` | one tenant runs one unit of that work, under the venue's clock | one job a cell of the matrix |
| `council-settle` | every tenant counts, fits, or does nothing | once a date, in the collecting job, after every unit has reported |

**Removing the imports was not the whole cut.** The four verb names also sat in
the router's own tuple of what it accepts, in a flag's help text, and in four
dispatch branches. A check that parses import statements goes green over a verb
name spelled as a string, so the strings went with the imports. Measured on this
repository: importing the router used to pull twelve of the judge's modules into
memory and now pulls two, and both of those arrive through the digest
pipeline's own use of the applied merge line rather than through anything the
council runs.

## The tenant list, and why it is empty

`council.tenants` is an ordered list of slugs in `config/idhazh.json`. It is the
one place a judge is registered, and it ships **empty**.

A slug resolves to the module that declares it: the council reads the directory
listing of its own package, finds each subpackage that has a `tenant` module in
it, and imports one until a declared slug matches. **Every one of those imports
happens inside a function**, so no council module carries a judge in its import
closure - and a package with no `tenant` module is never imported at all, so one
tenant's broken import cannot hide another tenant's slug.

Three things follow, and each is the reason a simpler design was refused.

- **No list in Python.** A map from slug to module would make adding a judge a
  code change, and it would be a roster of who may exist - which is what the
  central judge identifier was deleted for.
- **A slug nothing declares is refused by name.** Skipping it would run every
  step, report nothing wrong, and judge less than the config asked for.
- **Removing a judge is a config edit and a directory delete.** Never a router
  edit.

### Resolving is also when a tenant may refuse the night

A tenant module may declare
`refuse_a_night_this_tenant_cannot_finish`, and the resolver calls it on the
tenant that answered to the slug - on that one and on no other. A tenant nobody
registered cannot stop a night it is not in, even though the search has to import
it to read its slug.

**The planning job resolves every registered slug before it can build its
matrix**, so a refusal lands there: before the matrix exists, before any job is
dispatched, and before a runner has restored a model's weights. "Before a model
call" would be a weaker claim - it is also true of a point after a cache restore
and a server start, which is most of what a wasted job costs.

**It is not an eighth member of the tenancy protocol.** The protocol is what a
tenant presents while it runs; this is asked before it does. A tenant whose work
has no cost to weigh against the venue's clock declares nothing and is asked
nothing.

The content-similarity judge is what declares one today, in
[../../../backend/idhazh/similarity/budget.py](../../../backend/idhazh/similarity/budget.py):
its draw of pairs, at its own measured per-pair cost, against the window below.
The number is that judge's reading, so the check is that judge's too. Until
2026-09-21 it was a validator on `AppConfig`, which put one judge's measurement
in the import closure of every module that reads config - the council's own
included. Owner ruling, 2026-09-21.

## The matrix is a flat list of cells

The planning job asks
[../../../backend/utilities/council_matrix.py](../../../backend/utilities/council_matrix.py)
what the night fans out to, and publishes the answer as job outputs. A cell
carries four values - the tenant, the date, the shard, and **that tenant's own
width**.

**Not a cross product of three vectors.** A per-tenant width is not a third
axis: a product would hand every tenant the widest tenant's width, and a tenant
that runs no model would pay four weights cache restores for work that uses none
of them. So the width travels on the cell that uses it.

**The wave is the cell count under the platform's own twenty-job ceiling, never
the shard width.** Bound to the width, two tenants over two dates would be
sixteen cells in four waves - about 5.4 hours of wall clock for 81 minutes of
work, finishing after the next digest cron and across the scheduled prune. Bound
to the cell count it is one wave.

**An empty matrix reds the run rather than skipping quietly**, so the judging
job carries `if: needs.draw.outputs.matrix != '[]'`. No workflow here had ever
built a zero-width matrix, so there was no pattern to copy: Actions refuses to
evaluate a strategy with no values, and without the guard the legal night above
would fail on an error nobody could read. The collecting job keeps `always()`.

## Units judge, and only the collecting job writes

Units run in parallel, one `llama-server` each, and **none of them commits
anything**. A `collect` job downloads every unit's output and makes one commit call,
over every path the night's tenants named. Two processes never share a path.

`fail-fast` is off. **A unit that dies costs its own work and nothing else** -
the settle runs anyway and keeps everything the surviving units produced.

**The venue spells no store path.** A list of one tenant's paths is a list that
never commits a second tenant's output, so the paths come back from
`committed_paths` on the protocol and reach the commit step as one job output. A
night with no tenant registered stages nothing, and the step is skipped: `git
add` with no path is an error rather than a no-op.

There is no regeneration command on that call. The council is the only writer of
a tenant's own store and `concurrency` runs one council at a time, so a lost
race is a race against a digest run - which writes none of these paths. Replaying
what this run wrote onto the new base is the whole of what is needed.

## The clock a unit stops on, and the upload that runs either way

**The venue owns every clock here, because the venue owns the runner.** The job
timeout, the checkout, the install and the weights restore are all the council's
and no tenant can see any of them, so `council.shard_timeout_minutes`,
`council.shard_preamble_minutes` and `council.shard_wrap_up_minutes` sit in the
council's own config block. The first is how long GitHub lets a unit hold a
runner. The second is what the venue has already spent before the judging
process starts. The third is the reserve: how much a unit keeps back for writing
its records and getting its artifact away.

**What crosses to a tenant is one instant, not three knobs.**
[../../../backend/idhazh/council/deadline.py](../../../backend/idhazh/council/deadline.py)
subtracts the preamble and the reserve from the bound, adds what is left to the
instant the unit's own process began, and hands the result over. A tenant handed
an instant needs no config block and no config reader to stop on time, which is
how a judge with neither can still be stopped - and how the clock is gated
against a four-line fake instead of a model.

At the committed numbers the arithmetic is 200 minus 13 minus 12, so a unit has
175 minutes to work in. The judging process starts about 13 minutes into the
job's own 200, so its deadline lands at about minute 188 - twelve minutes before
GitHub would kill it, which is exactly the reserve.

**175 minutes is also what a tenant's own fit check weighs its draw against.**
It reads the window from the same function the clock does rather than from a
second copy of the subtraction. Until 2026-09-21 the check compared against the
whole 200, so a draw that fit the bound and not the work was accepted at config
load and cut off at runtime - the 25 minutes between the two is the gap that
admitted it.

### Design rationale: the preamble is a clock, not a bigger bound

Until 2026-09-21 the window was the bound less the reserve, and the zero was the
process. Those two do not meet: the platform starts counting at provisioning and
the process starts after a checkout, a weights cache restore, a checksum verify
and a health poll. So the in-process deadline landed **after** GitHub's own kill
whenever the model was slow to load, and the protection was inert on the one
night it was for.

The fix is a third clock rather than a bigger bound. Measured worst case for
those four steps is about 12.1 minutes - provisioning 0.41, cache restore 0.63
to 1.58, checksum verify 0.12, and a health poll bounded at 10 - so the default
is 13, one minute above it.

**`council.shard_timeout_minutes` stays at 200 and no council number is derived
from a judge's throughput.** How long the venue lets one unit occupy a runner is
the council's policy, set against the platform's 6 h job ceiling and the nightly
schedule. A bound derived from a measured per-pair cost would be the coupling
this page exists to refuse, one layer down: a second judge with different
economics would move a number that is not its to move. A tenant that cannot fit
inside the window is refused by its own fit check, raised when the planning job
resolves it. Owner ruling, 2026-09-21.

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

Owner ruling, 2026-09-18. The shards split a list today and never confer, so
`judges` is the more literal word for what is on disk right now.

**What is coming is not one question.** This loop argues a case, and a case needs
something to adjudicate it - a model, a panel, or a plain heuristic - and some of
those paths put a person in the loop. One roof for all of them, named for the
room rather than for the one job being done in it this month.

`CLAUDE.md` section 1a permits this: a model verdict may run in a production
workflow and may determine publication.

**The test every name here has to pass.** A word earns a name only when its
ordinary English meaning is what the thing does. Where a reader has to know
which other field a word was borrowed from, it is a second name for something
that already has one, and the fix is to delete it rather than to find a better
borrowing. `council` passes on the plain meaning: a council is a room where a
case is heard.

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

**That sentence is worth nothing unless a reviewer can fail a change on it**, so
it is five conditions and each one names what fails.

| # | The condition | What fails a change |
| --- | --- | --- |
| 1 | Nothing under `backend/idhazh/council/` imports a judge | a new import of a judge's module or a judge's contract, anywhere in that directory. The precedent is `CLAUDE.md` section 4, where the contracts package imports no sibling of its own |
| 2 | No judge module is reachable from a council verb, however many imports away | a council verb that imports a judge at module scope, or imports something that does. A check scoped to the directory cannot see this: the command router used to import four judge stages at module scope, so deleting the judge broke every council verb while the directory itself stayed clean |
| 3 | Every council contract declares, builds and round-trips with no judge in the repository | a council contract that names a judge's type, or whose field description names a judge's unit of work. A description is published in the generated schema, so a judge's word in one is a judge's word in the venue's own public contract |
| 4 | Every council test passes with no judge's test module present | a council test that imports a judge's fixture, and a council change that cannot be merged until a judge change is. Council tests live in `backend/tests/council/` |
| 5 | A judge is reached only through the protocol the council declares, and only from config | the council opening a judge's store, reading a judge's stamp, or naming a judge's type. Registration points a judge at the council and never the other way: the config names slugs, and the resolver imports a judge only when it has been asked for one |

**What the rule costs, stated rather than implied.** The council's own row
records the tenant's slug as plain text with no membership check, so a typo
files a row under a name nobody owns and a group-by hands it back. That is a
reporting nuisance, and it is the price of the rule: a central list of who may
exist would change the venue's published contract every time a tenant moved in,
and a repository with no judge in it could not import the council's own record
at all. The slug reaches the council from the tenant's own module constant, so a
typo is a source edit a reviewer sees.

Four layers - three of them the council's and one the tenant's - and which one a
reading belongs to is decided by what the reading is ABOUT, never by what
executed it.

| Layer | Owns | Stored |
| --- | --- | --- |
| Council pipeline observability | Did the pipeline work - which units started, which finished, which stopped on their own clock, what each cost | `state/llm-council/` |
| The tenancy protocol | The shape a judge presents: its slug, how many ways its work splits, the store paths it commits, the nights it is behind on, and three units of work. Declared by the council, implemented by each judge, and it names no judge | code, not data |
| The shipping capability | The plumbing only. Takes a validated row a judge hands it and gets it committed. Declares nothing about what is in it | code, not data |
| Judge metrics | Entirely the judge's - its units, its funnel, its own contract | under that judge's own slug |

A judge that runs no model files a row with no model columns, and the council's
record is unchanged.

**Why the separation is not a matter of taste.** A first draft put a judge's
funnel and its first-token margin on the council's own row. That margin means
"the grammar chose and the model did not" for a judge whose emitted token is the
answer, and "a legitimate middle score" for a judge whose spread of scores is the
answer. One column, two instruments, and any total taken over it adds them
together. So a shared judge-metrics contract is refused rather than deferred:
the column would not be wrong on the day it was added, it would go wrong on the
day a second judge filled it.

Which store each reading lands in, and the one reading that is filed under a
judge although the council is what runs it, is
[../../concepts/telemetry.md](../../concepts/telemetry.md#where-a-judging-night-files-what-it-measured).

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

## The venue keeps its own record of every unit it ran

The council starts a clock, calls the tenant, and files one row of its own on
the way out - into
[../../../backend/idhazh/ledger.py](../../../backend/idhazh/ledger.py)'s
`state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv`, through the same
shipping path a tenant's own row travels on. The row says which unit ran, for
which tenant, under which name, how it ended, how long it took, and what the
work inside it cost the model. It says nothing that needs a name for the unit of
work, so it reads the same whether the tenant made four hundred model calls or
none.

**Five units a tenant, not four.** Picking the work and counting what came back
are units too, and both can die. They file at reserved numbers below zero, `-1`
and `-2`, carrying the run's real width - so a night whose count died leaves a
row saying so instead of leaving the venue blind.

**The cost cells come off what the tenant handed back, and out of nothing else.**
The council opens no store of a tenant's and reads no field of a tenant's own
contract. A tenant with no model hands back empty cells, and empty is not zero:
zero would read as a model that answered nothing, which is a different fact and
only one of the two is a defect.

**A unit that died files nothing, and that is the record.** The outcome
vocabulary is three words - `completed`, `stopped_on_deadline`, `nothing_to_do` -
and none of them says "this died". A unit the platform killed could not write
one anyway. What says it is the missing row read against the `shards` cell its
siblings carry: three rows that each say the work was split four ways is a night
with one unit missing, and an operator needs nothing else to see it. A unit that
ran out of its own clock is the opposite case and does file a row, because it
stopped itself and had something to report.

**The store is seeded with a `.gitkeep` and never with a header-only day file.**
A header with no rows under it is a real day to the partition walker, so one
would put a permanent day in the prune target and the day inventory that no
council run ever had. A night with nothing to record therefore writes no file at
all, and the commit step still finds its directory.

### Design rationale: the venue files the row, not the tenant

An earlier draft had the judge's own stages write this row. That made the
venue's record of a unit depend on a tenant's diligence: a judge that forgot the
line, or died before reaching it, left nothing behind at the one moment the
record mattered. The council owns the invocation, so it owns the outcome - the
row is filed in a `finally`, and it survives anything that goes wrong after the
tenant handed its result back. Owner ruling, 2026-09-21.

**`judge_id` is in the settlement key**, beside the date, the run and the unit
number. One council run has one run id, so on a night hosting two tenants,
tenant A's first unit and tenant B's first unit carry the same three cells - and
the pass that drops repeated rows after a merge would delete one of them. The
slug is what tells them apart. It is recorded rather than checked: the council
writes down who ran and never declares who may exist.

**No machine is recorded per unit.** The runner pool is already characterised by
the digest pipeline, and the bandwidth probe that would fingerprint it wants
1.9 GiB on a job whose two processes already hold up to 9.02 GiB of anonymous
memory in 16 GB. The council's data is discardable, so the reading is not worth
the only memory risk in the design. Carmack, 2026-09-21.

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

## Design rationale: the night names itself

Every row this workflow writes carries a `run_id`. Until 2026-09-21 the council
had none, so the draw and the fit both read one off the published day's run
manifest - and a council row was filed under the digest run that published the
day it read. That run never drew a pair, never called a model, ran on a
different machine, and opened on a different day.

**The council mints its own name now.** Once, in the planning job, from the day
the council RUNS and the run id the platform gave the run:
`2026-09-21-35534060762`. It is published as a job output and every verb that
writes a row is handed it, the same way the shard bound and the model refs
already cross.
[../../../backend/idhazh/council/run_identity.py](../../../backend/idhazh/council/run_identity.py)
holds the one function that makes it, and nothing in it names a judge, opens a
store or resolves an ordinal.

Three things about the shape, each of which reads as the obvious answer and is
not.

- **The prefix is the day the council runs, never the day it judges.** A reader
  takes a run id's first ten characters as the day its run opened and measures
  the lag to publication from them, so a judged-date prefix would publish a
  standing lag of a day that nothing waited. The judged date is the `date`
  column, which is what routes a row to its store.
- **It is the platform's run id, never its run number.** The number starts again
  in each workflow, so a council name would eventually equal a digest run's id
  in a column that carries both meanings.
- **It is minted once, never per job.** The prefix is a day, so four jobs each
  reading the platform's value would split a run that crossed midnight across
  two addresses with nothing able to say the two were one night.

### Two meanings in one column, and how a reader tells them apart

`run_id` on a row written before this change means **the run that published the
day**. On a row written after it, it means **the run that judged it**. Two
stores carry both across time: the judged pairs and the fitted lines. On
2026-09-21 that was 82 pair rows and 1 fitted row, all under
`2026-09-18-35339202390`.

The **`version` stamp every row already carries is the discriminator** (owner
ruling, 2026-09-21). It costs nothing, because the row carries it either way.

There is a second test that needs no stamp at all, and it is exact rather than
approximate. **A digest run's id is prefixed with the day it published, so on
every row written the old way `run_id` starts with that row's own `date`.** A
council name is prefixed with the day the council ran, which is the day after
the one it judges. So `run_id[:10] == date` is the old meaning and
`run_id[:10] > date` is the new one, on both stores, with nothing to look up.

**What this does not change.** The judged date is still the `date` column and
still decides which file a row lands in. And the pair row's own contract already
said `run_id` was "the run that scored the pair" - the code was what disagreed
with it.

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
- [../../concepts/telemetry.md](../../concepts/telemetry.md#where-a-judging-night-files-what-it-measured) - which committed store each of a judging night's readings goes in.
- [../../reference/github-actions.md](../../reference/github-actions.md) - every workflow, its trigger and its schedule.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #2 (the 6 h job ceiling) and section 1a (what a model verdict may decide).
