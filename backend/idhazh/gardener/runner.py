"""How does one gardener shard, or one named task, run from start to its landed record?

In order, and each step before the next: the declarations are loaded and the
task modules found, then the pre-flight checks the two against each other both
ways, then every task runs, then what each one touched is held to what it owns,
then one record is written, and only then is anything staged.

**The pre-flight is the two refusals that need the modules.** A declaration no
module serves, and a module no declaration uses, are both exit 2 before any
task runs. Every other refusal was made while the declarations loaded
(`idhazh.config.load_gardener`).

**A task that fails still has a row.** Its row says `failed`, its siblings still
run, and the shard exits 1 when nothing worse happened. What it had already done
is on the row, because the core carries it out of any failure part way.

**What a task touched must sit inside what it owns.** Every path it took and
every file it wrote is checked, on a dry run too, because the check is over the
selection rather than over what was deleted. A path outside is exit 2, and
nothing is staged. A collection task is checked on what it wrote alone: what it
takes lives on GitHub, not in this repository.

**One record per shard, always.** Every task adds its row, a dry run included,
so a shard of nothing but dry runs still writes one file and still pushes it.
"""

from __future__ import annotations

import logging
import subprocess
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
from idhazh.gardener import publish, registry, report, shards
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass, PruneInterruptedError
from idhazh.gardener.publish import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Shard

logger = logging.getLogger(__name__)

#: The name the record's writer carries in its envelope. This module writes it.
PRODUCER: Final = "gardener.runner"

#: The timestamp shape every instant in a record takes: UTC, to the second.
_INSTANT: Final = "%Y-%m-%dT%H:%M:%SZ"


class ShardRefusedError(Exception):
    """Something the shard cannot run past. The runner exits 2 on it."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one run of the runner came to: its exit code and its record, if it wrote one."""

    exit_code: int
    record: Path | None


def _utc_now() -> datetime:
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


def _missing_folders(policy: TaskPolicy, repo_root: Path) -> list[str]:
    """The owned folders that are not in this checkout. The complement form owns no named one."""
    return [folder for folder in policy.owns or () if not (repo_root / folder).is_dir()]


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


def _run_one(name: str, held: registry.TaskModule, context: TaskContext) -> _Ran:
    """One task, timed, with any failure turned into the row that says so."""
    started = time.monotonic()
    missing = _missing_folders(context.policy, context.repo_root)
    failed = True
    if missing:
        logger.error("%s owns %s, and this checkout has none of it", name, ", ".join(missing))
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


def _git_sha(repo_root: Path) -> str:
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise ShardRefusedError(f"{repo_root.name} is not a git checkout, so no record can name it")
    return done.stdout.strip()


def _record(
    ran: Sequence[_Ran], *, state_dir: Path, today: str, identity: WriterIdentity, ended: str
) -> Path:
    """The shard's one record: every task's row, in one file under the gardener's ledger."""
    rows: list[CollectionPruneRow] = [
        report.row(
            each.outcome,
            task=each.name,
            context=each.context,
            duration_ms=each.duration_ms,
            work_ended_at=ended,
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


def run(
    names: Sequence[str],
    *,
    settings: GardenerSettings,
    repo_root: Path,
    run_id: str,
    attempt: int,
    shard: int,
    publish_it: bool,
    package: ModuleType = shipped_tasks,
    clock: Callable[[], datetime] = _utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Run these tasks as one shard, write its record, and land it when asked to."""
    state_dir = repo_root / ledger.STATE_DIRNAME
    try:
        bound = preflight(settings.tasks, registry.discover(package))
        git_sha = _git_sha(repo_root)
    except (registry.DiscoveryError, ShardRefusedError) as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None)

    started = clock()
    today = started.date()
    kinds = {TaskKind(settings.tasks[name].kind) for name in names}
    job = ServerJob.HISTORY if kinds == {TaskKind.HISTORY} else ServerJob.RUN_TASKS
    ran: list[_Ran] = []
    try:
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
            )
            done = _run_one(name, bound[name], context)
            _refuse_a_path_outside(done, settings.tasks)
            ran.append(done)
        ended = clock().strftime(_INSTANT)
        identity = WriterIdentity(
            run_id=run_id,
            attempt=attempt,
            job=job,
            shard=shard,
            producer=PRODUCER,
            git_sha=git_sha,
        )
        record = _record(
            ran, state_dir=state_dir, today=today.isoformat(), identity=identity, ended=ended
        )
    except ShardRefusedError as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None)

    for each in ran:
        for line in report.lines(each.outcome):
            say(line)
    tasks_code = EXIT_TASK_FAILED if any(each.failed for each in ran) else EXIT_OK
    if not publish_it:
        say(f"shard {shard}: wrote {record.relative_to(repo_root).as_posix()} and pushed nothing")
        return Outcome(exit_code=tasks_code, record=record)

    live = [each for each in ran if not each.context.policy.dry_run]
    recorded = record.relative_to(repo_root).as_posix()
    wrote = {path for each in live for path in each.outcome.written}
    landing = Shard(
        index=shard,
        task_names=tuple(names),
        record_path=recorded,
        written_paths=frozenset({recorded, *wrote}),
        deleted_paths=frozenset(
            path
            for each in live
            if each.context.policy.kind != TaskKind.COLLECTION
            for path in each.outcome.taken
        ),
    )
    pushed = publish.publish(
        landing,
        f"gardener: {', '.join(names)} on {today.isoformat()}",
        attempts=settings.config.attempts,
        repo=repo_root,
        say=say,
    )
    return Outcome(exit_code=publish.worst(tasks_code, pushed), record=record)


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
