# How a run's rows reach the repository

**Last Updated**: 2026-09-20

Ten jobs of one run commit to one branch, and every one of them can lose the
push race. This page owns what they run to win it: the three-attempt rebase
loop, which job may rebuild what it commits, and how two runs of one day are
stopped from writing different bytes to one path.

The workflows these jobs belong to are in
[../../reference/github-actions.md](../../reference/github-actions.md).

## The commit steps push through a rebase, and the one that can rebuild rebuilds

The plan job, each work shard and the assemble job commit, then push in a loop of
three attempts. The bench's `runtime` job does too. All of them
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
is nothing for `git rebase --abort` to abort, and the loop spends all three
attempts on the first one. A shard that writes a `state/` path its commit step
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
`state/segments/host-fingerprint/<run>-<attempt>-<job>-<shard>.csv` instead - a
name no second writer can take - the work job stages `state/segments` rather than
the head, and `idhazh compact` inside `assemble` folds the segments into the day.
The head has one writer per run, which is what the rebase loop was never able to
give it. Ledger by ledger, so one revert takes one ledger.

**There are two ways to lose the push race, and they need different answers.**

The plan job only records what it saw, and so does a work shard. Every path they
write has one writer: a head is filled by the compaction inside one job, and a
shard's rows go to `state/segments/<ledger>/<run>-<attempt>-<job>-<shard>.csv`,
which names the one writer that can take it. Two sides of a lost race are
therefore two different paths, and the rebase applies both whole.

**Until 2026-09-19 those files were shared and `.gitattributes` gave every one of
them a union merge driver**, which resolved the rebase by concatenating both sides. That
is the right answer for two runs writing different rows and the wrong one for two
attempts writing the same row, and an appending stage cannot tell them apart: it
filters against the file it checked out, and `actions/checkout` pins the job to
the commit its run was triggered at. A settling pass ran after each rebase to
take the repeats back out. Both are gone: the union driver is off every head, no
commit step settles anything, and a second attempt that really does race its own
first attempt now stops at the rebase instead of landing a row twice. Only
`state/published/**` and `state/visual-prunes/**` keep a union driver, and each
has one writing job.

A shard's two steps carry `continue-on-error`, so neither can fail the shard. The
shard owes the run its items artifact, and assemble writes the same census again,
so a ledger that will not push costs this run an early copy of rows it gets
anyway - while a failed shard costs the day a whole worker. Eight shards racing
one branch is the contention case the loop's three attempts exist for.

The assemble job rebuilds what it commits, so it rebuilds. `actions/checkout@v6`
carries no `ref`, so the job takes main's tip at trigger time, and a run takes
164-184 min - the day is always built on a base up to three hours old, and the
push is the first thing to find out. On a rejected push the loop hands the
derived paths back to origin's tip and runs `python -m idhazh assemble` again
against it. That stage already loads the previous day and appends to it, so it
is the conflict resolver; it was being run once against a stale base and then
thrown at `git merge-file`. A text merge of two digests produces a payload no
producer would ever write.

`REFRESH_PATHS` names what the rebuild owns: the day's `digest.json` and
`run.json`, `frontend/public/telemetry/`, and the four ledgers the workers and
assemble append to. It never names the day's directory. The `shard-visuals-*`
artifacts unpack this run's rendered charts into that same directory and no producer in
the assemble job can make them again, so the two payload files are named one at a
time. `frontend/public/telemetry/` is a full rewrite of `state/item-health/`,
which is why it is regenerated and not unioned: a union of two rewrites is a file
with every row twice.

**The charts in that directory are the other way to lose the day, and they get
their own answer.** A chart used to be filed as `<vertical>-<NN>.svg`, numbered
from the day's directory, and two runs of one day overlap by hours - so both read
the same highest number and both wrote `energy-03.svg` for different items. Git
cannot rebase two adds of one path, so that run died at this step on
`CONFLICT (add/add)`. `REFRESH_PATHS` cannot help: hand-back would delete this
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
progress, and ends on the three-attempt message.

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

## See also

- [../../reference/github-actions.md](../../reference/github-actions.md) - which workflows exist, when each runs, and what each does.
- [visuals.md](visuals.md) - why a raced chart is dropped rather than merged, refreshed or renamed.
- [../contracts/schemas.md](../contracts/schemas.md) - the row contracts under `state/`, and the rule that decides when a ledger shards.
- [retention.md](retention.md) - what the committed record keeps once the artifacts are gone.
- [../../../CLAUDE.md](../../../CLAUDE.md) - section 8 on git hygiene, section 11 on persisted contracts.
