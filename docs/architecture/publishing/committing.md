# How a run's rows reach the repository

**Last Updated**: 2026-09-23

Ten jobs of one run commit to one branch, and every one of them can lose the
push race. This page owns what they run to win it: the rebase loop and the clock
that bounds it, which job may rebuild what it commits, and how two runs of one
day are stopped from writing different bytes to one path.

The workflows these jobs belong to are in
[../../reference/github-actions.md](../../reference/github-actions.md).

## The commit steps push through a rebase, and the one that can rebuild rebuilds

The plan job, each work shard and the assemble job commit, then push in a loop
bounded by a wall clock. The bench's `runtime` job does too. All of them
run one script,
[`.github/scripts/commit-and-push.sh`](../../../.github/scripts/commit-and-push.sh).
Two copies of the loop were a loop no test could execute.

**A ledger reaches the repository only when the job that wrote it stages it.** No
other job can stand in. Each one runs on its own runner with its own checkout, so
the `state` assemble stages whole carries nothing a work shard wrote. A ledger
written in Python and staged in YAML is a pair no single test used to read, so a
store could be written for days and staged by nobody without a test going red.
[`backend/tests/workflows/test_ledger_staging.py`](../../../backend/tests/workflows/test_ledger_staging.py)
reads both. It takes every store from the `*_relpath` helpers the store modules
already export, charges each one to the job whose `python -m idhazh <verb>` step
reaches its writer, and fails naming the store, the job, the workflow file and
the step to add the path to. A ledger is written by an `append_*` call, the trace
tree by a file sink opened on its own path helper, and a head by the compaction
reading its own declared table of them; all three count, because all three die
with the runner. It names no store itself, so a thirteenth one is covered the
day its writer lands rather than the day somebody remembers to add it to a list.

The same file holds the second half of that. A ledger that declares a key must be
in `ledger.keyed_paths`, the registry that pairs each ledger with what makes two
of its rows one record, and a ledger that declares none must be absent from it.
The two sides are compared as sets rather than as a subset, so the registry's one
deliberate absence has to stay the one its own docstring claims.

**A rebase refuses to start while a tracked file is modified.** A file committed
with CRLF against a `text eol=lf` attribute is the trap: every Linux checkout
sees it modified before any step runs, so the loop finds a dirty tree it did not
create and can throw away a day that plan, the shards and assemble had all
finished.

The work is already in a commit when the loop begins, so anything left in the
working tree is runner noise. The loop prints what is dirty and discards it
before the rebase. `--autostash` was removed - it stashes the noise and then
fails the step when the stash will not reapply, which is the failure it looks
like it prevents.

**An untracked file stops a rebase too.** A rebase detaches HEAD onto the tip
first, and that checkout refuses when a file the incoming commits add is already
sitting untracked in the working tree: `error: The following untracked working
tree files would be overwritten by checkout`. The rebase never starts, so there
is nothing for `git rebase --abort` to abort, and the loop spends its whole
budget on the first attempt. A shard that writes a `state/` path its commit step
does not stage leaves exactly that file untracked, and a sibling shard pushing
the same path is enough to trigger it.

The staging list is written by hand, so a new `state/` writer can arrive without
it, and that has happened. So the loop also clears, before each
rebase, exactly the untracked files the tip is about to write - and names each
one in the run log. **A path this job did not stage is a path it is not pushing**,
so removing it costs the push nothing it was going to carry, and every path that
WAS staged still lands. Everything else untracked survives: `llama-server.log`
and the memory samples are untracked, and later steps upload them.

**Staging a path ten jobs share is a repair, not a fix, and the machine record is
where that was settled.** A head that ten jobs of one run stage, commit and push
is a head no rebase loop can give a single writer. Each job writes
`state/host-fingerprint/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.csv`
instead - a name no second writer can take - and the work job stages the day
directory. Ledger by ledger, so one revert takes one ledger.

**Since 2026-09-22 there is no head above it.** The day directory used to be a
staging area called `state/segments/` that a later fold read into a `<DD>.csv`
head, which left every ledger with one path two runs of one day both computed
bytes for. The day directory is now the ledger itself, and `state/segments/` is
gone.

**There are two ways to lose the push race, and they need different answers.**

The plan job only records what it saw, and so does a work shard. Every row they
append has one writer: a shard's rows go to
`state/<ledger>/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.csv`, which names
the one writer that can take it. Two sides of a lost race are therefore two
different paths, and the rebase applies both whole.

**No path in the plan job is a derived `state/` ledger any more, and that closes
the exception this section used to carry.** A day head was derived from the
segment store by a catch-up fold, so two jobs that folded the same segments
wrote the same head from different bases - two derived versions of one file,
which is the shape no rebase can settle and no merge rule should. The gap that
made it possible is not a race at all: `actions/checkout` restores the commit
the run was TRIGGERED at, and nothing bounds how far origin moves before the job
starts. Run `35660521768` is the record. It was created at 22:02 and
started here at 22:48, five commits behind, and one of those five was the run
ahead's own fold. It re-folded segments that run had already folded and deleted,
rewrote the five heads it had already written, and the rebase then held two
versions of each with no way to choose. The whole day went at the push. **The
head is what made that possible, and the head is gone.**

That 46-minute gap was a wait in a concurrency group this workflow no longer has
([below](#two-runs-of-one-day-work-at-the-same-time-and-nothing-queues-them)).
The gap itself did not go with it. It is now whatever a run working alongside
this one has committed since the trigger, which is why the step below still
runs.

The answer is a current base rather than a merge rule. The job runs
[`.github/scripts/take-state-from-the-tip.sh`](../../../.github/scripts/take-state-from-the-tip.sh)
ahead of the fold: `state` is emptied and then taken from origin's tip, so a
segment the run ahead drained is gone before the fold can read it. Restoring the
tip's `state` on its own would not do it - git writes what the tip HAS and says
nothing about what it does not carry, and the drained segment is precisely what
it does not carry. **Only `state` moves.** The code the job runs stays on the
trigger commit, so a run cannot change its own behaviour halfway through and no
log line would have said which build did what. And it goes ahead of every other
step in the job that writes under `state/`, because taken after one of them it
discards what that step wrote.

**Until 2026-09-19 those files were shared and `.gitattributes` gave every one of
them a union merge driver**, which resolved the rebase by concatenating both sides. That
is the right answer for two runs writing different rows and the wrong one for two
attempts writing the same row, and an appending stage cannot tell them apart: it
filters against the file it checked out, and `actions/checkout` pins the job to
the commit its run was triggered at. A settling pass ran after each rebase to
take the repeats back out. Both are gone: the union driver is off every head, no
commit step settles anything, and a second attempt that really does race its own
first attempt now stops at the rebase instead of landing a row twice. Only
`state/published/**`, `state/visual-prunes/**` and `state/seen/**` keep a union
driver, and each has one writing job. `state/seen/` is the one that never moved
to a segment - it is a whole day file that `plan` appends to, so two runs of one
day that both met a new address used to conflict at the push over a file neither
of them disagreed about. `ledger.load_seen` keeps the earliest stamp per
address, so a row the union brings twice costs bytes and moves no age.

A shard's two steps carry `continue-on-error`, so neither can fail the shard. The
shard owes the run its items artifact, and assemble writes the same census again,
so a ledger that will not push costs this run an early copy of rows it gets
anyway - while a failed shard costs the day a whole worker. Eight shards racing
one branch is the contention case the loop's deadline exists for.

The assemble job rebuilds what it commits, so it rebuilds. `actions/checkout@v6`
carries no `ref`, so the job takes main's tip at trigger time, and a run takes
164-184 min - the day is always built on a base up to three hours old, and the
push is the first thing to find out. On a rejected push the loop hands the
derived paths back to origin's tip and runs `python -m idhazh assemble` again
against it. That stage already loads the previous day and appends to it, so it
is the conflict resolver; it was being run once against a stale base and then
thrown at `git merge-file`. A text merge of two digests produces a payload no
producer would ever write.

**`DERIVED` names what the rebuild owns, and after 2026-09-22 that is almost
nothing under `state/`.** It carries the day's `digest.json` and `run.json`, the
published projections under `frontend/public/`, `state/day-metrics` and the
closed-day fold. The list lives in
[`backend/idhazh/paths.py`](../../../backend/idhazh/paths.py) and the
`Say which committed paths a rebuild owns` step prints it into `$GITHUB_OUTPUT`;
it was a space-split string in the workflow, under a header warning that no path
in it may carry a space, and the workflow tests held a second copy of the same
list. It never names the day's directory. The `shard-visuals-*`
artifacts unpack this run's rendered charts into that same directory and no producer in
the assemble job can make them again, so the two payload files are named one at a
time. `frontend/public/telemetry/` is a full rewrite of `state/item-health/`,
which is why it is regenerated and not unioned: a union of two rewrites is a file
with every row twice.

**Eight `state/` paths left this list on 2026-09-22 and the reason is the same
for all of them.** Seven are written once - item-health, host-fingerprint,
scores, score-index, span-rollup, traces and segments, which is gone - so each
now names its file for the single writer that wrote it, two runs never compute
different bytes for one path, and there is nothing to hand back.
`state/published` left beside them for a different reason: it is union-safe, and
the hand-back was discarding this run's appended rows before the union driver
could ever fire, leaving the publication record dependent on a rebuild
succeeding. **What the eight buy is correctness, not time**: against a 5-second
rebuild in an 11-second step there is no time to win.

**`state/day-metrics` is the one that stays**, and it is the reason `hand_back`
still touches a `state/` path at all. It is one whole-file-per-day JSON that
assemble rewrites from the day's rows, so two runs of one day do land on one
path, a text merge of two JSON objects is not JSON, and the rebuild answers the
race in milliseconds. The closed-day fold stays for the same reason and is the
one entry the rebuild command leaves out: `idhazh assemble` re-emits no fold, so
a job that handed it back would delete it rather than rebuild it.

**The charts in that directory are the other way to lose the day, and they get
their own answer.** A chart used to be filed as `<vertical>-<NN>.svg`, numbered
from the day's directory, and two runs of one day overlap by hours - so both read
the same highest number and both wrote `energy-03.svg` for different items. Git
cannot rebase two adds of one path, so that run died at this step on
`CONFLICT (add/add)`. The rebuild list cannot help: hand-back would delete this
run's charts while the rebuilt `digest.json` still names them.

A chart is now filed under its item's own id, so two stories can no
longer land on one path at all. What is left is two runs **compiling** the same
item to different bytes, and `DROP_RACED_ASSETS_COMMAND` is the answer to that.
Nothing renders at build time: the reader's browser draws the chart, and what a
run writes is the marks. A renderer's non-determinism is therefore not in play,
so an item compiled twice from unchanged inputs writes identical bytes and git
merges those without a conflict. The race is not gone with it: the marks come
from an article re-fetched from the open web, so a source page that moved between
two runs' fetches still puts two different blobs on one path. Before
each rebase attempt the loop lists the asset paths the tip already publishes -
`git ls-tree -r --name-only FETCH_HEAD` over the same staged paths - and pipes
them to that command, which deletes this run's copy of any of them. The tip's
file never moves: it is published, a reader may already hold that address, and
the rebuild keeps the tip's item over this run's in any case - so this run's copy
is the one nothing would have referenced. The decision payload keeps naming the
same path, because the tip's file is sitting at it after the rebase, so the
rebuilt day
still names a file that is really in the tree. `DROP_RACED_ASSETS_COMMAND` without
`REGENERATE_COMMAND` is rejected at startup, because only a job that rebuilds can
commit the drops. Why it is a drop and not a merge side, a refresh or a rename is
in [`../architecture/publishing/visuals.md`](visuals.md).

**Every command in the loop is guarded.** An unguarded command ends the script
inside attempt 1 under `bash -e`: no attempt 2, no failure message, no day, and a
checkout left mid-rebase. A guarded failure says what it was, leaves no rebase in
progress, and ends on the caller's own message plus the attempt it reached.

## A conflicted path is settled by who wrote it, never by which side it came from

Git's own names for the two sides of a conflict invert between a rebase and a
merge, so a design that reasons in them is a design nobody can check. The
writer's identity is already in the filename instead.
`state/<ledger>/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.csv` names the
run, the try at that run, the job and the shard inside it, and GitHub allocates
the execution number inside the run id, so no second writer can take that name.

**The script looks for that identity anywhere in the name, not only at the
front.** A run id is `<date>-<execution>`, and the date is the plan job's to
choose, so the runner never hands a commit step the whole of it. What the runner
does hand over is the execution number, which is eleven digits nothing else in a
committed filename produces - so the execution number with the attempt, the job
and the shard behind it names one writer just as exactly as a match from the
first character would. Off a runner there is no execution number at all, and the
script answers "not mine" before it compares anything: a checkout that is not a
job owns nothing.

So a conflicted filename that carries this job's own four values is this
job's work, and what this job wrote is kept. **Every other conflicted path stops
the push and names the path and this job.** There is no third answer. Retrying
cannot make another writer's file this job's, and taking the tip's copy instead
would delete that writer's rows and exit 0 - a loss no gate can see. A path the
job rebuilds cannot reach the resolver at all, because it was handed back to the
tip before the rebase, so one that does is a gap in `DERIVED` and the same
refusal names it.

**The rule should never fire**, and it is bought anyway. Two writers cannot name
one file, so a conflict on one means two jobs claimed one identity - a defect to
report rather than a race to settle - and this is the only thing that turns the
next one into a message instead of a silent loss.

**A file this job wrote that the tip has deleted stops the push too**, and that
case needs a second read of the index to catch. Git's spelling for keeping one
side of a conflict exits 0 and changes nothing when the side it is asked for is
the deleted one, so the path is left unmerged with no error anywhere and
`set -euo pipefail` walks straight past it into a rebase that cannot continue.
Nothing but retention, the closed-day fold or a person can have taken a file
named for this job, so putting it back is not a resolution this script may make.
The message prints one identity, because one is all there is: a second field
would always be empty.

**A conflicted closed-day fold is refused whole, and the refusal is the
mechanism rather than a gap in it.** `settled.csv` carries no writer's name, so
the rule above answers no and the push stops. Settling it per path is what loses
rows: taking the tip's copy leaves this job's *deletion* of a straggler file
standing - a deletion is not a conflict, so git keeps it - and the straggler's
rows then exist in no file at all, at exit 0. Refusing means the whole fold
commit dies with the runner, the tip keeps both its `settled.csv` and the
straggler, and the next run folds that day again. The step is
`continue-on-error: true`, so the job carries on. What a refused fold costs is
the telemetry month fold that shares the step, and that month is folded on the
next run.

Two things were considered and neither is taken. A file listing what each job
owns restates the identity the filename already carries and gives it somewhere
to drift. A lock taken before the push is not a lock at all - two jobs both read
"free" from their own stale checkouts and both take it, which is the same
read-modify-write race that broke the shared heads. **The only compare-and-swap
this platform offers is the ref update itself**, and the loop above already uses
it.

## The loop stops on a clock, and says what each attempt spent

**A fixed number of attempts is spent at once however high the number is.** Three
was the number until 2026-09-22, and under several runs committing together each
loser spent its three while the tip kept moving. An optimistic rebase-and-push
converges in expectation at any commit rate; a counter does not. So the loop runs
until `run.push_deadline_seconds` is gone, waiting `min(2^(k-1), 8)` seconds
between attempts for k failures so far, drawn against U(0.5, 1.5) - the spread
widens with the backoff, so collisions fall as more runs contend.

**300 s is 25 percent of the assemble job's 20-minute timeout.** Measured on run
`35701213155`, that job used 1.8 of its 20 minutes, so 18.2 minutes were spare.
The work shard is the one caller that overrides it, with 120 s in its own `env:`
block: the whole of what a shard keeps back for everything after its last item is
`run.shard_wrap_up_minutes`, which is 12 minutes, and 300 s would be 5 of them.

**Each attempt prints six stamps**, to the job log and to the step summary:

```
push attempt=2 job=assemble shard=none outcome=landed window_ms= fetch_ms= handback_ms= rebase_ms= rebuild_ms= push_ms=
```

The split is the point. A single figure cannot tell a slow rebuild from a slow
push, and which of the two the deadline is being spent on is what decides whether
300 s is the right number. **Attempt 1 has no window in the retry sense**:
nothing fetches before the first push, so its exposure is the whole job -
checkout to push, two to three hours - which is not a retry parameter, and its
zeros are the truth about it. What measures attempt 1 is the share of runs whose
first push lands. Above 95 percent means the deadline is almost never spent and
the number can rise; below 80 percent means no deadline is the right answer for
what is going wrong.

**The number is not committed to a ledger.** Both candidate rows are written by
Python before the commit step runs, so neither can carry a figure that does not
exist until after the push.

## A rebase here never guesses that a drained directory was renamed

Git reads a directory whose files all moved away as having been RENAMED to
wherever they went, and applies that guess to a file the other side added into
the emptied directory. The closed-day fold drains a day directory every time it
runs, so a sibling writing a brand-new file into that day is read as writing
into a directory that no longer exists, and the rebase stops with
`CONFLICT (file location)` over a tree that was correct. The segment store was
the first place this bit; deleting it moved the drain rather than removing it.

So every rebase in the script runs with `-c merge.directoryRenames=false`. Proved
in a scratch repository on 2026-09-22: the same replay conflicts with the guess
on and reports `Successfully rebased` with it off, losing nothing. It is a
per-invocation flag rather than a runner-wide setting, because the runner's
config is not the repository's and a behaviour a reader cannot see from the
script is one nobody will find.

A workflow contract test pins this shape, and executes the script against real
local repositories - including a scripted origin that gains both another run of
the same day and an unrelated pull-request merge while the job works, and one
where both sides rendered a chart onto the same path. CI never runs `digest.yml`,
so a change to the loop still needs a dispatched run to verify end to end.

## The rebuild reads its own mid-flight payloads with whatever code main now holds

**A contract change merged while a run is in flight breaks that run**, and the
error names neither the cause nor the fix. The rebuild above re-runs
`python -m idhazh assemble` against `origin/main` after a lost push race. It
re-runs the code at the tip, and the per-item payloads on the runner's disk were
written hours earlier by the code the run started with. If the two disagree about
a field, the reader raises where nothing is wrong with the data.

**The window is most of the day.** Five scheduled runs, each 164 to 184 minutes,
so a merge lands inside a live run more often than not. Two consequences:

- **Check for an in-flight run before merging a contract change.**
 `gh run list --workflow digest.yml --status in_progress` answers it. A change
 that removes, renames or retypes a field on any payload under `backend/var/`
 waits for the run to finish.
- **The failure is loud and the day is lost, not corrupted.** `assemble` raises
 rather than publishing a half-read day, and the next scheduled run rebuilds
 from its own payloads under the new contract. So the cost is one digest, and
 the answer is to time the merge rather than to build a general guard - that
 guard would have to read every old shape, which is the migration `CLAUDE.md`
 section 11 requires when a payload is committed. These are not. The one case
 where the old shape is already written down is covered below, and reading it
 cost nothing.

**The error names the condition, which is a smaller claim than fixing it.**
Every read of a payload one job of a run wrote and a later job reads goes
through `Contract.read`, which compares the stamp on the payload against the one
the running build declares before parsing rules on anything. When the two differ
and the payload will not load, it raises `StalePayloadError` carrying both
stamps and the remedy, instead of a list of fields that are not wrong. A payload
stamped with the build's own version still raises the parser's own error
untouched - that is a defect and dressing it up would hide every real bug behind
a story about timing. The bullet above still holds: the day is lost, the next
scheduled run rebuilds it, and timing the merge is the thing that prevents it.

**A column the contract says it dropped is dropped on the way in.** One slice of
this is not a timing problem at all. `ItemHealthRow` already declares, in
`DROPPED_CELLS`, every heading it stopped naming that nothing replaced - it has
to, because `ledger.migrate_header` refuses to append to a committed day file
whose heading is neither a current column nor one the reader says it carries. So
the committed side of that row has read those headings since the day each one
left. The per-item payload a work shard seals did not, and run 35537015073 lost
its digest to the gap: `cgroup_peak_bytes` left the row at 22:22, the rebuild at
23:24 read payloads sealed at 20:54, and `extra="forbid"` refused a key the
same contract had already promised to tolerate. The row now reads both sides off
that one set, so a removal declared once is honoured wherever the row is read.

This is narrow on purpose, and the narrowness is the whole of its safety. A
dropped column has no replacement by definition, so dropping the cell loses the
only thing it could lose. A column that MOVED is in `RETIRED_CELLS` instead, is
not in this set, and still raises - a reader that silently dropped one of those
would publish a row missing a value that exists. A rename, a retype, a new
required field and a removal nobody declared all still stop the run and still
name both stamps.

Four wider fixes were considered and none is taken.

| Option | Why rejected |
| --- | --- |
| Fail a pull request that touches `backend/idhazh/contracts/` while a run is live | Built, measured, and removed the same day. Five scheduled runs at 3 h 34 min each occupy 74 percent of the day, so the check would redden three contract pull requests in four and ask for a manual re-run each time - to prevent a failure that costs one digest and repairs itself on the next run. The information is worth a person's `gh run list`; it is not worth a red check. Owner decision, 2026-09-21 |
| Extend `CLAUDE.md` section 11 to cover every payload under `backend/var/` | It would close the hole rather than report it - a rename would ship a reader for the old shape and the straddling run would publish. The cost is that every rename on those shapes becomes expand-migrate-contract, two commits and a window of hours where both shapes are read. That is a change to a persisted-contract rule, so it is Level 5 and the owner's, not a fix PR's. What shipped above is the one case that needs none of that: the old shape is already declared, and reading it is a deletion rather than a second reader |
| Re-run the producer instead of the assembler | `assemble` is what merges the day with what is already published, so skipping it is not an option, and re-running the whole day costs the run again |
| Degrade the item, as section 1a would otherwise reach for | The three cases that principle names are all the outside world failing; this is the build and the disk disagreeing. Degrading would publish a day quietly missing N items because somebody merged a rename, and nothing would come back to correct it |

## Two runs of one day work at the same time, and nothing queues them

`digest.yml` declares no `concurrency` group. Two content refresh runs of the
same day may work at once, and that is what everything above is for.

**What makes it safe is the filename.** Every committed path a job of this
workflow writes carries that run's own identity -
`state/<ledger>/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.csv`, and
`state/digest-fragments/<YYYY>/<MM>/<DD>/<run>.json` for the published day. Two
runs at once therefore name two files rather than one, the rebase applies both
whole, and the read settles them: a ledger through its day directory, the
published day by folding one block per run in `("completed_at", "run_id")`
order. Nothing derived is left on a shared path, and a conflicted path is
resolved only by the job whose identity the name carries.

**The group it replaced bought no safety, and it cost two things.** GitHub keeps
one pending run per group and cancels the older, so a dispatch fired while a run
was going disappeared with no error in the run list - the operator saw a
cancelled run and no reason. And a run that did wait read a store its own wait
had made stale: run `35660521768` waited 46 minutes, folded a 46-minute-old
store and lost the whole day at the push, which is the incident this page is
largely about. A queue that manufactures staleness is not a guard.

**A narrower group per date was considered and rejected.** Two runs of one day
are exactly the case that has to work: five scheduled runs share a day and each
one adds to it. A group per date would queue precisely the pair this design is
for. A lock file was rejected too, for a plainer reason - two jobs read "free"
from their own stale checkouts and both take it. The only compare-and-swap this
platform offers is the ref update itself, and the push loop already uses it.

**What is proved here, and what a person watches.**
[`backend/tests/workflows/test_triggers.py`](../../../backend/tests/workflows/test_triggers.py)
holds that no group comes back, at the workflow level or on any job, and that
every other workflow committing a ledger still declares one. What no test can
take is the live pair: two runs dispatched to overlap both reaching a green
`assemble`, both publishing, and neither losing a block. That is an observation
on the schedule, and the attempt line the push loop prints is where the cost of
it is collected over time.

## See also

- [../../reference/github-actions.md](../../reference/github-actions.md) - which workflows exist, when each runs, and what each does.
- [../../concepts/partitions.md](../../concepts/partitions.md) - the three classes every committed path is one of, and the layout each one obliges its writer to keep.
- [visuals.md](visuals.md) - why a raced chart is dropped rather than merged, refreshed or renamed.
- [../contracts/schemas.md](../contracts/schemas.md) - the row contracts under `state/`, and the rule that decides when a ledger shards.
- [retention.md](retention.md) - what the committed record keeps once the artifacts are gone.
- [../../../CLAUDE.md](../../../CLAUDE.md) - section 8 on git hygiene, section 11 on persisted contracts.
