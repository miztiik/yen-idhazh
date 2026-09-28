"""How does one gardener shard, or one named task, run from start to its written record?

In order, and each step before the next: the declarations are loaded and the
task modules found, then the pre-flight checks the two against each other both
ways, then every task runs, then what each one touched is held to what it owns,
then one record is written, and the paths to land are handed back.

**Nothing here stages, commits or pushes.** Landing runs git, and nothing under
`backend/idhazh/` may start a process, so the commit loop is
`backend/utilities/gardener_publish.py`, which calls `run` and lands the `Shard`
it hands back. For the same reason the commit this checkout is at arrives as an
argument rather than being read here.

**The pre-flight is the two refusals that need the modules.** A declaration no
module serves, and a module no declaration uses, are both exit 2 before any
task runs. Every other refusal was made while the declarations loaded
(`idhazh.config.load_gardener`).

**A history task never runs here.** It rewrites history in a job of its own,
and `backend/utilities/corpus_history.py` binds it itself; run here, it would
only stamp the day it last ran and hold off the next real rewrite by a whole
cadence. So a shard or a hand run that names one is exit 2 before anything runs.

**A shard's weight is an alarm, not a gate.** What the folders its tasks own
weighed at its commit arrives as data, read by the program that runs git, and
lands on every row as `cone_bytes`. Over `max_cone_mb` the shard says so,
naming its three heaviest folders, still runs every task and lands its record,
and exits 1: stopping would save nothing the checkout has not already paid for,
and it would stop the very passes that could shrink the tree.

**A task that fails still has a row.** Its row says `failed`, its siblings still
run, and the shard exits 1 when nothing worse happened. What it had already done
is on the row, because the core carries it out of any failure part way.

**Every task is handed the folders it walks, judged against the commit.** A
folder the commit holds and the checkout lacks fails the task, because a wrong
checkout would otherwise report a silent zero. A declared folder the commit does
not hold yet is left out and logged: nothing has written one, and the task's
first write makes it. A complement task is answered only from the commit, so a
caller that could not read it is refused before any task runs.

**What a task touched must sit inside what it owns.** Every path it took and
every file it wrote is checked, on a dry run too, because the check is over the
selection rather than over what was deleted. A path outside is exit 2, and
nothing is handed on to land. A collection task is checked on what it wrote
alone: what it takes lives on GitHub, not in this repository. A report a task
files through the ledger door, into a ledger its declaration `appends_to`, is
held to that ledger and the wake's day instead, and it lands on a dry run too.

**One record per shard, always.** Every task adds its row, a dry run included,
so a shard of nothing but dry runs still writes one file and still lands it.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh import ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.file_envelope import Format, WriterIdentity
from idhazh.contracts.knobs.gardener import TaskKind, TaskLifecycleStatus, TaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import registry, report, shards
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass, PruneInterruptedError
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome, Shard
from idhazh.site_weight import BYTES_PER_MB

logger = logging.getLogger(__name__)

#: The name the record's writer carries in its envelope. This module writes it.
PRODUCER: Final = "gardener.runner"

#: The timestamp shape every instant in a record takes: UTC, to the second.
_INSTANT: Final = "%Y-%m-%dT%H:%M:%SZ"

#: How many of a shard's folders an over-weight message names, heaviest first.
_HEAVIEST_NAMED: Final = 3

#: The one program that runs a history task, named in the refusal to run one here.
HISTORY_PROGRAM: Final = "backend/utilities/corpus_history.py"


class ShardRefusedError(Exception):
    """Something the shard cannot run past. The runner exits 2 on it."""


def utc_now() -> datetime:
    """The clock a run reads when none is handed in: now, in UTC."""
    return datetime.now(UTC)


def preflight(
    tasks: Mapping[str, TaskPolicy], modules: Mapping[str, registry.TaskModule]
) -> dict[str, registry.TaskModule]:
    """Every active and paused declaration's module, checked against the modules both ways.

    One way, every such declaration is served by exactly one module. The other
    way, every module serves at least one of them - a module only retired tasks
    point at is a module nothing will run, and it goes.
    """
    bound = {
        name: registry.bind(name, TaskKind(policy.kind), modules)
        for name, policy in tasks.items()
        if policy.lifecycle_status is not TaskLifecycleStatus.RETIRED
    }
    unused = sorted(set(modules) - {held.stem for held in bound.values()})
    if unused:
        raise registry.DiscoveryError(
            f"tasks/{', tasks/'.join(f'{stem}.py' for stem in unused)} serves no active or "
            "paused declaration. Declare the task it runs, or delete the module"
        )
    return bound


def _nested(path: str, folder: str) -> bool:
    """Whether `path` is `folder` or sits inside it, compared segment by segment."""
    inner, outer = PurePosixPath(path).parts, PurePosixPath(folder).parts
    return inner[: len(outer)] == outer


def owner_of(name: str, tasks: Mapping[str, TaskPolicy]) -> Callable[[str], bool]:
    """Whether a path is one this task owns: inside its folders, or in its complement.

    The complement is every path under the task's roots that no other task owns,
    whatever that task's status, and that no ledger family or ledger root claims,
    so a sweep over `state/` can never reach a ledger's own tree.
    """
    policy = tasks[name]
    if policy.owns is not None:
        folders = tuple(policy.owns)
        return lambda path: any(_nested(path, folder) for folder in folders)
    roots = tuple(policy.owns_everything_else_under or ())
    others = tuple(
        folder
        for other, declared in tasks.items()
        if other != name
        for folder in declared.owns or ()
    )
    claimed = ledger.claimed_roots()

    def in_the_complement(path: str) -> bool:
        parts = PurePosixPath(path).parts
        for root in roots:
            below = PurePosixPath(root).parts
            if parts[: len(below)] != below or len(parts) <= len(below):
                continue
            if root == ledger.STATE_DIRNAME and parts[len(below)] in claimed:
                return False
            return not any(_nested(path, folder) for folder in others)
        return False

    return in_the_complement


@dataclass(frozen=True, slots=True)
class Folders:
    """The folders one task walks, worked out before it runs, and the two kinds it cannot."""

    #: What the task walks, in the order it walks them.
    walk: tuple[str, ...]
    #: Folders the commit holds and this checkout lacks. A checkout that left out
    #: a folder it should have held turns every deletion under it into a silent
    #: zero, so the task fails rather than report one.
    missing: tuple[str, ...]
    #: Declared folders the commit does not hold yet, because nothing has written
    #: one. There is nothing there to walk, and the task's first write makes it.
    absent: tuple[str, ...]


def _a_child_of(folder: str, roots: Sequence[str]) -> bool:
    parent = PurePosixPath(folder).parent
    return any(parent == PurePosixPath(root) for root in roots)


def folders_of(
    name: str,
    tasks: Mapping[str, TaskPolicy],
    repo_root: Path,
    committed: frozenset[str] | None,
) -> Folders:
    """Which folders a task walks, judged against the commit when the caller could read it.

    `committed` is every folder the commit holds that a declaration names, and
    every folder directly under `state/`, read by the program that runs git.
    None means nobody could read the commit - `idhazh gardener run-task` starts
    no process - and the checkout is then taken as it stands.

    A complement task cannot be answered without the commit. What it owns is
    whatever nothing else claims, and read off a working tree that set would
    include a folder somebody left there and never committed.
    """
    policy = tasks[name]
    if policy.owns is None:
        if committed is None:
            raise ShardRefusedError(
                f"{name} owns everything else under {', '.join(policy.claims())}, and only the "
                "commit can say what that is. Run it through backend/utilities/"
                "gardener_publish.py, which reads the commit"
            )
        owns = owner_of(name, tasks)
        swept = tuple(
            sorted(
                folder
                for folder in committed
                if _a_child_of(folder, policy.claims()) and owns(folder)
            )
        )
        here = [folder for folder in swept if (repo_root / folder).is_dir()]
        gone = [folder for folder in swept if not (repo_root / folder).is_dir()]
        return Folders(walk=tuple(here), missing=tuple(gone), absent=())
    walk: list[str] = []
    missing: list[str] = []
    absent: list[str] = []
    for folder in policy.owns:
        present = (repo_root / folder).is_dir()
        if committed is not None and folder not in committed:
            absent.append(folder)
        elif present:
            walk.append(folder)
        elif committed is None:
            absent.append(folder)
        else:
            missing.append(folder)
    return Folders(walk=tuple(walk), missing=tuple(missing), absent=tuple(absent))


def _nothing_reached(name: str, policy: TaskPolicy) -> Pass:
    """The pass of a task that failed before it reached a single member."""
    return Pass(
        collection=name,
        since=None,
        until=None,
        ceiling=policy.max_deletes_per_run,
        dry_run=policy.dry_run,
        seen=0,
        selected=0,
        taken=(),
        written=(),
        bytes_freed=0,
        stopped_because=StopReason.FAILED,
        resume_from=None,
    )


@dataclass(frozen=True, slots=True)
class _Ran:
    name: str
    context: TaskContext
    outcome: Pass
    duration_ms: int
    failed: bool


def _run_one(
    name: str, held: registry.TaskModule, context: TaskContext, folders: Folders
) -> _Ran:
    """One task, timed, with any failure turned into the row that says so."""
    started = time.monotonic()
    failed = True
    for folder in folders.absent:
        logger.info(
            "%s owns %s, which the commit does not hold yet, so it walks none", name, folder
        )
    if folders.missing:
        logger.error(
            "%s owns %s, which the commit holds and this checkout does not",
            name,
            ", ".join(folders.missing),
        )
        outcome = _nothing_reached(name, context.policy)
    else:
        try:
            outcome = held.run(context)
            failed = outcome.stopped_because is StopReason.FAILED
        except PruneInterruptedError as stop:
            logger.error("%s failed part way: %s", name, stop)
            outcome = stop.so_far
        except Exception:
            logger.exception("%s failed before it reached a member", name)
            outcome = _nothing_reached(name, context.policy)
    elapsed = int((time.monotonic() - started) * 1000)
    return _Ran(name=name, context=context, outcome=outcome, duration_ms=elapsed, failed=failed)


def _touched(ran: _Ran) -> tuple[str, ...]:
    """Every repository path a task touched: what it wrote, and what it took from the tree."""
    taken = () if ran.context.policy.kind == TaskKind.COLLECTION else ran.outcome.taken
    return (*taken, *ran.outcome.written)


def _refuse_a_path_outside(ran: _Ran, tasks: Mapping[str, TaskPolicy]) -> None:
    owns = owner_of(ran.name, tasks)
    outside = [path for path in _touched(ran) if not owns(path)]
    if outside:
        raise ShardRefusedError(
            f"{ran.name} touched {outside[0]}, which it does not own. Nothing is staged: a "
            "task that reaches outside what it owns could be deleting another task's files"
        )


def _refuse_an_append_outside(ran: _Ran, today: str) -> None:
    """Every report a task filed is a fresh raw file of a ledger it declared, under the wake's day.

    Held the way the shard's own record is held, because it is the same kind of
    write: one new file the ledger door named, which can overwrite nothing.
    """
    context = ran.context
    for appended in ran.outcome.appended:
        path = context.repo_root / appended
        for which in context.policy.appends_to:
            try:
                expected = ledger.raw_path(
                    context.state_dir,
                    which,
                    today,
                    uuid.UUID(path.stem),
                    fmt=Format(path.suffix.removeprefix(".")),
                )
            except ValueError:
                continue
            if expected == path:
                break
        else:
            raise ShardRefusedError(
                f"{ran.name} filed {appended}, which is not a report of a ledger it appends "
                "to under today's day. Nothing is staged"
            )


def _record(
    ran: Sequence[_Ran],
    *,
    state_dir: Path,
    today: str,
    identity: WriterIdentity,
    ended: str,
    cone_bytes: int | None,
) -> Path:
    """The shard's one record: every task's row, in one file under the gardener's ledger."""
    rows: list[CollectionPruneRow] = [
        report.row(
            each.outcome,
            task=each.name,
            context=each.context,
            duration_ms=each.duration_ms,
            work_ended_at=ended,
            cone_bytes=cone_bytes,
        )
        for each in ran
    ]
    written = ledger.persist(
        state_dir, rows, ledger=LedgerName.GARDENER, covers=today, identity=identity
    )
    if len(written) != 1:
        raise ShardRefusedError(
            f"the shard's rows went to {len(written)} files, and a shard writes one record"
        )
    record = written[0]
    try:
        expected = ledger.raw_path(
            state_dir,
            LedgerName.GARDENER,
            today,
            uuid.UUID(record.stem),
            fmt=Format(record.suffix.removeprefix(".")),
        )
    except ValueError as error:
        raise ShardRefusedError(f"{record.name} is not a record's name: {error}") from error
    if record != expected:
        raise ShardRefusedError(
            f"the record went to {record.name}, outside the gardener's own raw ledger"
        )
    return record


def history_tasks_among(names: Sequence[str], tasks: Mapping[str, TaskPolicy]) -> list[str]:
    """Which of these names are history tasks, which only their own job may run."""
    return [
        name
        for name in names
        if (policy := tasks.get(name)) is not None and policy.kind == TaskKind.HISTORY
    ]


def over_the_ceiling(
    cone_bytes: Mapping[str, int], *, ceiling_mb: int, shard: int
) -> str | None:
    """What a shard over `max_cone_mb` says, naming its heaviest folders, or None when under.

    Over means strictly more than the ceiling: a shard that weighs exactly the
    ceiling is inside it.
    """
    total = sum(cone_bytes.values())
    if total <= ceiling_mb * BYTES_PER_MB:
        return None
    heaviest = sorted(cone_bytes.items(), key=lambda held: (-held[1], held[0]))
    named = ", ".join(
        f"{folder} {weight / BYTES_PER_MB:.1f} MB" for folder, weight in heaviest[:_HEAVIEST_NAMED]
    )
    return (
        f"shard {shard}: its owned folders weigh {total / BYTES_PER_MB:.1f} MB ({total:,} "
        f"bytes) at this commit, over max_cone_mb {ceiling_mb} in "
        f"config/idhazh_gardener.json. The heaviest: {named}. Its tasks still run and its "
        "record still lands, and the shard exits 1"
    )


def run(
    names: Sequence[str],
    *,
    settings: GardenerSettings,
    repo_root: Path,
    run_id: str,
    attempt: int,
    shard: int,
    git_sha: str,
    committed_folders: frozenset[str] | None,
    cone_bytes: Mapping[str, int] | None,
    package: ModuleType = shipped_tasks,
    clock: Callable[[], datetime] = utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Run these tasks as one shard, write its record, and hand back what is left to land.

    `git_sha` is the commit this checkout is at, which the record's envelope
    names. `committed_folders` is what that commit holds of the folders these
    tasks own, and every folder directly under `state/` (`folders_of`).
    `cone_bytes` is what each of those owned folders weighs at that commit. All
    three are read by whoever calls this, before any task runs, because reading
    them starts git; None for the last two means nobody could read the commit.
    """
    refused = history_tasks_among(names, settings.tasks)
    if refused:
        say(
            f"shard {shard}: {', '.join(refused)} rewrites history, and a history task runs "
            f"only in its own job: {HISTORY_PROGRAM} binds and runs it. Nothing ran"
        )
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    state_dir = repo_root / ledger.STATE_DIRNAME
    try:
        bound = preflight(settings.tasks, registry.discover(package))
    except registry.DiscoveryError as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)

    weighed = None if cone_bytes is None else sum(cone_bytes.values())
    too_heavy = (
        None
        if cone_bytes is None
        else over_the_ceiling(cone_bytes, ceiling_mb=settings.config.max_cone_mb, shard=shard)
    )
    if too_heavy is not None:
        say(too_heavy)
    started = clock()
    today = started.date()
    job = ServerJob.RUN_TASKS
    identity = WriterIdentity(
        run_id=run_id,
        attempt=attempt,
        job=job,
        shard=shard,
        producer=PRODUCER,
        git_sha=git_sha,
    )
    ran: list[_Ran] = []
    try:
        # Every task's folders before the first task runs, so a task the commit
        # cannot answer for stops the shard with nothing yet done.
        resolved = {
            name: folders_of(name, settings.tasks, repo_root, committed_folders) for name in names
        }
        for name in names:
            context = TaskContext(
                state_dir=state_dir,
                repo_root=repo_root,
                today=today,
                policy=settings.tasks[name],
                run_id=run_id,
                attempt=attempt,
                job=job,
                shard=shard,
                git_sha=git_sha,
                owned_folders=resolved[name].walk,
            )
            done = _run_one(name, bound[name], context, resolved[name])
            _refuse_a_path_outside(done, settings.tasks)
            _refuse_an_append_outside(done, today.isoformat())
            ran.append(done)
        ended = clock().strftime(_INSTANT)
        record = _record(
            ran,
            state_dir=state_dir,
            today=today.isoformat(),
            identity=identity,
            ended=ended,
            cone_bytes=weighed,
        )
    except ShardRefusedError as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)

    for each in ran:
        for line in report.lines(each.outcome):
            say(line)
    live = [each for each in ran if not each.context.policy.dry_run]
    recorded = record.relative_to(repo_root).as_posix()
    wrote = {path for each in live for path in each.outcome.written}
    # A report lands dry run or not: it is what a dry run exists to produce.
    reported = {path for each in ran for path in each.outcome.appended}
    landing = Shard(
        index=shard,
        task_names=tuple(names),
        record_path=recorded,
        written_paths=frozenset({recorded, *wrote, *reported}),
        deleted_paths=frozenset(
            path
            for each in live
            if each.context.policy.kind != TaskKind.COLLECTION
            for path in each.outcome.taken
        ),
        message=f"gardener: {', '.join(names)} on {today.isoformat()}",
    )
    failed = any(each.failed for each in ran) or too_heavy is not None
    tasks_code = EXIT_TASK_FAILED if failed else EXIT_OK
    return Outcome(exit_code=tasks_code, record=record, landing=landing)


def tasks_of_shard(settings: GardenerSettings, index: int) -> tuple[str, ...]:
    """The tasks one shard of this wake runs, split the way the plan job splits them."""
    planned = shards.plan(settings)
    if not 0 <= index < planned.shard_count:
        raise ValueError(
            f"this wake has {planned.shard_count} shards, numbered from 0, so there is no "
            f"shard {index}"
        )
    return planned.shards[index].task_names


def runnable(settings: GardenerSettings, name: str) -> str:
    """One task by name, refused unless it is declared and active."""
    policy = settings.tasks.get(name)
    if policy is None:
        raise ValueError(f"no task is called {name}: there is no config/gardener/{name}.json")
    if policy.lifecycle_status is not TaskLifecycleStatus.ACTIVE:
        raise ValueError(
            f"{name} is {policy.lifecycle_status.value}, and only an active task runs. Set it "
            "active in its declaration first"
        )
    return name
