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

**What a shard downloads is held to `max_downloaded_mb`.** What the folders its
tasks own weighed at its commit arrives as data, read by the program that runs
git, and lands on every row as `cone_bytes`. What its tasks downloaded to read
lands beside it as `downloaded_bytes`. A compaction step takes a period only
while what it downloads fits what is left of that budget, so a correct choice
never passes it. Over it the shard says so, naming its three heaviest folders,
lands its record, and exits 1: a task downloaded without choosing by the
budget, which is a code defect. The downloads are paid for by the time the
number is known, so stopping then would only stop the passes that shrink the
tree.

**A task that fails still has a row.** Its row says `failed`, its siblings still
run, and the shard exits 1 when nothing worse happened. What it had already done
is on the row, because the core carries it out of any failure part way.

**Every task is handed the folders it walks, judged against the commit.** A
folder the commit holds is walked whether the checkout holds it or not, because
a task learns its members from the commit's names and fetches only what it
reads. A declared folder the commit does not hold yet is left out and logged:
nothing has written one, and the task's first write makes it. A complement task
is answered only from the commit, so a caller that could not read it is refused
before any task runs.

**Every task is handed the listing of the files under its folders.** One
listing a shard, of every folder its tasks own or read, handed in by whoever
built it or read off the disk here when nobody did; each task sees the part
that covers its own folders, and learns what is there from it rather than from
the disk. After each task the listing takes in what that task deleted and
wrote, so a later task reading the same folder sees the tree the shard will
commit.

**What a task touched must sit inside what it owns.** Every path it took and
every file it wrote is checked, on a dry run too, because the check is over the
selection rather than over what was deleted. A path outside is exit 2, and
nothing is handed on to land. A collection task is checked on what it wrote
alone: what it takes lives on GitHub, not in this repository. A raw file a task
writes through the ledger door, into a ledger its declaration `appends_to`, is
held to that ledger and its row date instead. A report filed on dry run lands
through `appended`, and must be under the wake day.

**One record per shard, always.** Every task adds its row, a dry run included,
so a shard of nothing but dry runs still writes one file and still lands it.

**A task that folds folds after its window, on a switch of its own.** A
retention task whose declaration carries a `fold` block settles the closed days
of the CSV day trees it walks (`closed_day_fold`), once its window's pass has
returned, skipping every day folder that pass took. What the fold writes and
deletes is held to what the task owns like everything else, and it lands when
the fold is live whatever the window's `dry_run` says - a live fold inside a
dry task would otherwise change the disk and stage nothing. A window that
failed stops the fold for that wake: what it took is then a list nothing has
checked, and a closed day loses nothing by waiting.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh import ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.file_envelope import Format, WriterIdentity
from idhazh.contracts.knobs.gardener import (
    RetentionPolicy,
    TaskKind,
    TaskLifecycleStatus,
    TaskPolicy,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import closed_day_fold, registry, report, shards
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.one_at_a_time import Pass, PruneInterruptedError
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome, Shard
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range
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
    """Whether a path sits inside one of this task's configured folders."""
    folders = tuple(tasks[name].owns)
    return lambda path: any(_nested(path, folder) for folder in folders)


@dataclass(frozen=True, slots=True)
class Folders:
    """The folders one task walks, worked out before it runs, and the ones nothing has made yet."""

    #: What the task walks, in the order it walks them.
    walk: tuple[str, ...]
    #: Declared folders the commit does not hold yet, because nothing has written
    #: one. There is nothing there to walk, and the task's first write makes it.
    absent: tuple[str, ...]


def folders_of(
    name: str,
    tasks: Mapping[str, TaskPolicy],
    repo_root: Path,
    committed: frozenset[str] | None,
) -> Folders:
    """Which folders a task walks, judged against the commit when the caller could read it.

    `committed` is every exact folder a declaration names, read by the program
    that runs git. A folder it holds is walked whatever the checkout holds,
    because the task's names come from the commit. None means nobody could read
    the commit - `idhazh gardener run-task` starts no process - and the checkout
    is then taken as it stands.
    """
    policy = tasks[name]
    walk: list[str] = []
    absent: list[str] = []
    for folder in (*policy.owns, *policy.reads):
        held = (repo_root / folder).is_dir() if committed is None else folder in committed
        if not held:
            absent.append(folder)
        elif folder in policy.owns:
            walk.append(folder)
    return Folders(walk=tuple(walk), absent=tuple(absent))


def listed_folders(policy: TaskPolicy, folders: Folders) -> tuple[str, ...]:
    """The folders a task's listing covers: every folder it owns or reads.

    A declared folder the commit does not hold is listed too, and answers empty,
    so a task that asks about it learns there is nothing there rather than being
    refused.
    """
    return (*policy.owns, *policy.reads)


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
    #: What the task's fold did. None when it has no fold, or the fold did not run.
    folded: closed_day_fold.Folded | None = None


def _run_one(name: str, held: registry.TaskModule, context: TaskContext, folders: Folders) -> _Ran:
    """One task, timed, with any failure turned into the row that says so."""
    started = time.monotonic()
    failed = True
    folded: closed_day_fold.Folded | None = None
    for folder in folders.absent:
        logger.info(
            "%s names %s, which the commit does not hold yet, so it lists nothing there",
            name,
            folder,
        )
    try:
        outcome = held.run(context)
        failed = outcome.stopped_because is StopReason.FAILED
    except PruneInterruptedError as stop:
        logger.error("%s failed part way: %s", name, stop)
        outcome = stop.so_far
    except Exception:
        logger.exception("%s failed before it reached a member", name)
        outcome = _nothing_reached(name, context.policy)
    policy = context.policy
    if not failed and isinstance(policy, RetentionPolicy) and policy.fold is not None:
        try:
            folded = closed_day_fold.run(context, policy.fold, skip=outcome.taken)
        except closed_day_fold.FoldInterruptedError as stop:
            logger.error("%s's fold failed part way: %s", name, stop)
            folded, failed = stop.so_far, True
        except Exception:
            logger.exception("%s's fold failed before it settled a day", name)
            folded = closed_day_fold.Folded(dry_run=policy.fold.dry_run, failed=True)
            failed = True
    elapsed = int((time.monotonic() - started) * 1000)
    return _Ran(
        name=name,
        context=context,
        outcome=outcome,
        duration_ms=elapsed,
        failed=failed,
        folded=folded,
    )


def _fold_changes(ran: _Ran) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What a task's fold wrote and deleted, or would have, as repository paths."""
    if ran.folded is None:
        return (), ()
    root = ran.context.repo_root
    folders: tuple[closed_day_fold.SettledMonth | closed_day_fold.SettledDay, ...] = (
        *ran.folded.months,
        *ran.folded.days,
    )
    return (
        tuple(each.settled.relative_to(root).as_posix() for each in folders),
        tuple(path.relative_to(root).as_posix() for each in folders for path in each.replaced),
    )


def _touched(ran: _Ran) -> tuple[str, ...]:
    """Every repository path a task touched: what it wrote, what it took, and what it folded."""
    taken = () if ran.context.policy.kind == TaskKind.COLLECTION else ran.outcome.taken
    settled, replaced = _fold_changes(ran)
    return (*taken, *ran.outcome.written, *settled, *replaced)


def _landed(ran: _Ran) -> tuple[set[str], set[str]]:
    """What a task changed in the tree, and so lands: the paths it wrote, and the ones it deleted.

    A dry run's writes and deletions are only reported, so they land nowhere. A
    report lands dry run or not, because it is what a dry run exists to produce,
    and a fold lands on its own switch, so a live fold inside a dry task lands
    too. What a collection task takes lives on GitHub, not in this repository.
    """
    live = not ran.context.policy.dry_run
    folding = ran.folded is not None and not ran.folded.dry_run
    settled, replaced = _fold_changes(ran) if folding else ((), ())
    wrote = {*(ran.outcome.written if live else ()), *ran.outcome.appended, *settled}
    took = ran.outcome.taken if live and ran.context.policy.kind != TaskKind.COLLECTION else ()
    return wrote, {*took, *replaced}


def _append_path_for(ran: _Ran, appended: str, *, today: str | None = None) -> Path | None:
    """The expected raw file for an append path, or None when it is not declared."""
    context = ran.context
    path = context.repo_root / appended
    for which in context.policy.appends_to:
        try:
            root = ledger.raw_root(context.state_dir, which)
            relative = path.relative_to(root)
            year, month, day, filename = relative.parts
            filed_on = today or date.fromisoformat(f"{year}-{month}-{day}").isoformat()
            expected = ledger.raw_path(
                context.state_dir,
                which,
                filed_on,
                uuid.UUID(Path(filename).stem),
                fmt=Format(Path(filename).suffix.removeprefix(".")),
            )
        except (ValueError, TypeError):
            continue
        if expected == path:
            return expected
    return None


def _refuse_a_path_outside(ran: _Ran, tasks: Mapping[str, TaskPolicy]) -> None:
    owns = owner_of(ran.name, tasks)
    outside = [
        path for path in _touched(ran) if not owns(path) and _append_path_for(ran, path) is None
    ]
    if outside:
        raise ShardRefusedError(
            f"{ran.name} touched {outside[0]}, which it does not own. Nothing is staged: a "
            "task that reaches outside what it owns could be deleting another task's files"
        )


def _refuse_an_append_outside(ran: _Ran, today: str) -> None:
    """Every append a task filed is a fresh raw file of a ledger it declared.

    Held the way the shard's own record is held, because it is the same kind of
    write: one new file the ledger door named, which can overwrite nothing.
    """
    for appended in ran.outcome.appended:
        if _append_path_for(ran, appended, today=today) is None:
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
    downloaded_bytes: int | None,
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
            downloaded_bytes=downloaded_bytes,
            folded=each.folded,
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


def over_the_ceiling(downloaded: Mapping[str, int], *, ceiling_mb: int, shard: int) -> str | None:
    """What a shard over `max_downloaded_mb` says, naming its heaviest folders, or None when under.

    `downloaded` is what the shard's tasks downloaded under each folder it
    listed. Over means strictly more than the ceiling: a shard that downloaded
    exactly the ceiling is inside it. A step that chooses its periods by the
    budget never passes it, so a shard over it is a code defect to fix.
    """
    total = sum(downloaded.values())
    if total <= ceiling_mb * BYTES_PER_MB:
        return None
    heaviest = sorted(downloaded.items(), key=lambda held: (-held[1], held[0]))
    named = ", ".join(
        f"{folder} {weight / BYTES_PER_MB:.1f} MB" for folder, weight in heaviest[:_HEAVIEST_NAMED]
    )
    return (
        f"shard {shard}: its tasks downloaded {total / BYTES_PER_MB:.1f} MB ({total:,} bytes) "
        f"of file content, over max_downloaded_mb {ceiling_mb} in "
        f"config/idhazh_gardener.json. The heaviest: {named}. A step that chooses its "
        "periods by the budget never passes it, so a task downloaded without choosing by "
        "it, which is a code defect. Its tasks ran and its record still lands, and the "
        "shard exits 1"
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
    listing: FileListing | None,
    period_range: tuple[str, str] | None = None,
    started_at: datetime | None = None,
    package: ModuleType = shipped_tasks,
    clock: Callable[[], datetime] = utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Run these tasks as one shard, write its record, and hand back what is left to land.

    `git_sha` is the commit this checkout is at, which the record's envelope
    names. `committed_folders` is what that commit holds of the folders these
    tasks own or read, and every folder directly under `state/` (`folders_of`).
    `cone_bytes` is what each of the owned folders weighs at that commit. All
    three are read by whoever calls this, before any task runs, because reading
    them starts git; None for the last two means nobody could read the commit.
    `listing` is the files under every folder the tasks own or read; None lists
    them off the disk here. What the tasks downloaded is read off it once they
    have run. `period_range` is a range a person named for one task: the task
    reads it in place of the window `scheduled_range` builds for a scheduled
    wake. A compaction has no such window, so a named range only limits the
    periods its steps choose.
    """
    refused = history_tasks_among(names, settings.tasks)
    if refused:
        say(
            f"shard {shard}: {', '.join(refused)} rewrites history, and a history task runs "
            f"only in its own job: {HISTORY_PROGRAM} binds and runs it. Nothing ran"
        )
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    if period_range is not None and len(names) != 1:
        say("a named period range runs one task, not a shard")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    state_dir = repo_root / ledger.STATE_DIRNAME
    try:
        bound = preflight(settings.tasks, registry.discover(package, settings.tasks))
    except registry.DiscoveryError as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)

    weighed = None if cone_bytes is None else sum(cone_bytes.values())
    started = started_at or clock()
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
    too_heavy: str | None = None
    try:
        # Every task's folders before the first task runs, so a task the commit
        # cannot answer for stops the shard with nothing yet done.
        resolved = {
            name: folders_of(name, settings.tasks, repo_root, committed_folders) for name in names
        }
        covered = {name: listed_folders(settings.tasks[name], resolved[name]) for name in names}
        period_ranges = {
            name: period_range
            if period_range is not None
            else scheduled_range(name, settings.tasks[name], today)
            for name in names
        }
        if listing is None:
            period_paths = {
                path
                for name in names
                for path in paths_for_task(
                    repo_root,
                    name,
                    settings.tasks[name],
                    period_ranges[name],
                    today=today,
                )
            }
            listing = FileListing.from_disk(
                repo_root,
                {folder for folders in covered.values() for folder in folders},
                paths=period_paths,
            )
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
                listing=listing.within(covered[name]),
                period_range=period_ranges[name],
            )
            done = _run_one(name, bound[name], context, resolved[name])
            _refuse_a_path_outside(done, settings.tasks)
            _refuse_an_append_outside(done, today.isoformat())
            ran.append(done)
            written, taken = _landed(done)
            listing = listing.settled(written=written, deleted=taken)
        downloaded = listing.downloaded()
        if downloaded is not None:
            too_heavy = over_the_ceiling(
                downloaded, ceiling_mb=settings.config.max_downloaded_mb, shard=shard
            )
        ended = clock().strftime(_INSTANT)
        record = _record(
            ran,
            state_dir=state_dir,
            today=today.isoformat(),
            identity=identity,
            ended=ended,
            cone_bytes=weighed,
            downloaded_bytes=None if downloaded is None else sum(downloaded.values()),
        )
    except ShardRefusedError as refusal:
        say(f"shard {shard}: {refusal}")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)

    for each in ran:
        for line in report.lines(each.outcome):
            say(line)
        if each.folded is not None:
            for line in report.fold_lines(each.name, each.folded):
                say(line)
    if too_heavy is not None:
        say(too_heavy)
    recorded = record.relative_to(repo_root).as_posix()
    wrote = {path for each in ran for path in _landed(each)[0]}
    deleted = {path for each in ran for path in _landed(each)[1]}
    landing = Shard(
        index=shard,
        task_names=tuple(names),
        record_path=recorded,
        written_paths=frozenset({recorded, *wrote}),
        deleted_paths=frozenset(deleted),
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
