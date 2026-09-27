# The gardener

**Last Updated**: 2026-09-27

How the one program that deletes and rewrites what this repository keeps is put
together: where its tasks come from, how a wake is split into shards, what a
shard checks before and after its tasks run, and how its one record lands on
`main` however many shards race it. What each knob means is
[../../concepts/config/idhazh-gardener.md](../../concepts/config/idhazh-gardener.md);
the workflow that wakes it is not written yet.

## What runs

The gardener runs **tasks**. A task is two things that land together:

- **a declaration**, one file under `config/gardener/`, named for the task. It
  says what the task owns, how far back it keeps, whether it may delete at all
  (`dry_run`), and which kind it is;
- **a module** under `backend/idhazh/gardener/tasks/`, holding exactly two
  names: `KIND`, the kind it serves, and `run`, which takes a `TaskContext` and
  returns a `Pass`.

There is no list of tasks anywhere. `registry.discover()` imports every module
in `tasks/`, and `registry.bind()` finds the module that runs one declaration in
two lookups: the module named for the task (hyphens become underscores), else
the module named for its kind. A config value never names a module, so text in
a file cannot choose which code runs (Guardrail #11).

**Today the folder holds no module and `config/gardener/` does not exist**, so
every command below answers "no tasks". The first tasks arrive with their
modules.

## A wake, in order

| Step | Who | What it does |
| --- | --- | --- |
| 1 | `backend/utilities/gardener_shards.py` | Splits the active tasks into shards and prints the plan. Standard library only, reads `config/` alone |
| 2 | `backend/utilities/gardener_publish.py --shard N` | Reads the commit the checkout is at, loads the declarations through the typed loader, finds the modules, and runs the pre-flight |
| 3 | the runner | Runs every task of the shard, one after another, timing each |
| 4 | the runner | Holds every path each task touched to what that task owns |
| 5 | the runner | Writes the shard's one record through `ledger.persist`, and hands back what to land |
| 6 | `gardener_publish.publish` | Stages exactly what the shard wrote and deleted, commits, pushes, and tries again on a newer tip if it lost |

**The split is round-robin over sorted names.** Every task the matrix runs - an
active one whose kind is not `history`, which has a job of its own - is sorted by
name and dealt to shard `position % shard_count`, where `shard_count` is the
smaller of `shards` and the number of tasks. The same declarations always give
the same shards, no shard is empty, and every task is in exactly one. How much
work a task holds is not read: one owned folder can hold one file or ten
thousand, so counting folders would balance nothing.

**A shard checks out the folders its tasks own**, joined into one
newline-separated string (`cone`) because that is what a sparse checkout reads.
A task that owns everything else under a root adds no folder: it reads what it
needs from git.

**The plan is written twice.** The plan job runs before anything of ours is
installed, so `gardener_shards.py` cannot import the typed planner in
`idhazh.gardener.shards`. The two emit one payload for one config, byte for byte,
and `backend/tests/contracts/test_gardener_plan.py` holds them to it and to the
`GardenerPlan` model. With no task for the matrix the payload is the empty
shape, on one line:
`{"any_active_task":false,"matrix":{"include":[]},"shard_count":0,"shards":[]}`.

## What stops a shard

| Exit | What it means | Retried |
| --- | --- | --- |
| 0 | every task ran and the record landed, or had already landed | - |
| 1 | a task failed. Its row says `failed`, its siblings still ran, and the record still landed | at the next wake |
| 2 | ownership or integrity: a module that cannot serve, a path outside what a task owns, a record outside the gardener's ledger, or one record path with two sets of bytes | never; a person fixes it |
| 3 | the push kept losing for every attempt | at the next wake |

A shard reports the worst code it earned, in the order 2, 3, 1, 0.

**The pre-flight is the two refusals that need the modules.** A declaration no
module serves, and a module no active or paused declaration uses, are both exit 2
before any task runs. A module whose `KIND` disagrees with the declaration it
would serve is refused the same way, because it would be handed a declaration it
cannot read. So is a module that raises while it is imported, a module that
declares no task, and two modules that would serve one name (`old-days.py` beside
`old_days.py`). None of these is caught and skipped: a skipped task is a task
that silently stopped deleting.

**Every path a task touched must sit inside what it owns.** What it took and
what it wrote are both checked, on a dry run too, because the check reads the
selection rather than what was deleted. The complement form owns every folder
under its roots that no other task owns, whatever that task's status, and that
no ledger family or ledger root claims. A collection task is checked on what it
wrote alone: what it takes lives on GitHub. The record the shard writes is the
one write no task owns.

## The record

One record per shard, always. Every task adds its row - a
[`CollectionPruneRow`](../contracts/state-ledgers.md#the-gardener) - a dry run
included, so a shard of nothing but dry runs still writes one file and still
pushes it. The record goes through the ledger door into the gardener's own ledger,
`state/raw/gardener/<YYYY>/<MM>/<DD>/<file_id>.parquet`, and the runner refuses
it with exit 2 if it went anywhere else.

Each row names the run that wrote it: `run_id`, `attempt`, `job` and `shard`, the
task's own `duration_ms`, and `work_ended_at`, the instant the shard finished
working and began to publish. A slow push is therefore never read as a slow task.

## Landing the commit

`backend/utilities/gardener_publish.py` is the only code that pushes. It is the
entry point a shard runs: it reads the commit the checkout is at, calls the
runner, and lands the `Shard` the runner hands back - the record, every path the
shard's live tasks wrote and deleted, and the commit message. Each attempt
fetches `main`, resets the index to it with `--mixed`, stages exactly those
writes and deletions, checks what it staged, commits as
`miztiik <miztiik@users.noreply.github.com>` and pushes. A lost push waits a
random time - up to 1, 2, 4, 8 and then 8 seconds - and tries again on the new
tip. No wait follows the last attempt.

**The record decides whether the shard already landed.** Its bytes are unique to
the shard, so `main` holding that path with those bytes means an earlier attempt
landed and this one stops with 0; the same path with other bytes is exit 2.

**Three checks run over what was staged, before every commit.** Nothing outside
the shard's writes and deletions is staged. Every write is staged, unless its
bytes already equal `main`'s, which is a write that already landed. And a
deletion that staged nothing is an error only while `main` still holds the
path, because a path already gone is a deletion somebody finished. A deletion
that names a folder is refused before anything stages.

**`idhazh gardener run-task` never pushes.** It runs the same tasks and writes
the same record into the checkout, and stops there, so running a task on a
developer's machine cannot reset their branch or push to main. It takes the
commit as `--git-sha`, because the package does not start git to read it. The
utility takes the same line without that flag, and both are built from one
parser in `idhazh.gardener.cli`.

## Design rationale

**2026-09-27: `attempts` must be above `shards`.** Every shard of one wake pushes
to one branch at once, so the shard that lands last has lost a race to every
other shard first. `attempts - shards` is how many pushes from outside the wake,
or failed pushes, one wave can absorb. The committed pair is 6 and 5; the
longest a shard can wait is about 23 seconds of backoff, about 40 seconds in all,
an estimate (Fowler and Carmack).

**2026-09-27: the split is round-robin, and history is not in the matrix.** The
plan job reads `lifecycle_status`, `kind` and `owns` and nothing else. A key
that placed one task after another was considered and dropped: nothing else in
the design orders tasks, and it would make the split depend on something other
than the names (Fowler and Carmack).

**2026-09-27: the hand-run collection utility writes no record.**
`backend/utilities/prune_artifacts.py --record` wrote one pass to a file nothing
read. A record now names the run, attempt, job and shard that made it, and a pass
a person runs by hand is none of those, so the flag went rather than invent an
identity (Fowler and Carmack).

**2026-09-27: the commit loop lives outside the package.** The loop runs git,
and `backend/tests/test_canaries.py` refuses `subprocess` anywhere under
`backend/idhazh/`: the package that reads the open web holds none of the
machinery an injected instruction would need to act (CLAUDE.md Guardrail #11).
Every other git call in this repository already lives under `backend/utilities/`
for the same reason. So the runner writes the record and hands back the paths,
and `gardener_publish.py` reads the commit, calls it and lands them. A task that
must run git itself - the corpus rewrite is one - has the same limit, and the
design for it is still to be written.

## See also

- [../../concepts/config/idhazh-gardener.md](../../concepts/config/idhazh-gardener.md) - every knob, and every refusal the loader makes.
- [committing.md](committing.md) - how every other job commits, and why the gardener stages its own files.
- [../contracts/state-ledgers.md](../contracts/state-ledgers.md) - the gardener's ledger, and what one of its rows holds.
- [../contracts/ledger-registry.md](../contracts/ledger-registry.md) - the grain that ledger files at, and the builders that refuse it.
- [../../concepts/atomic-deletes.md](../../concepts/atomic-deletes.md) - what one delete at a time buys.
