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

**A task that stops still has a row, and the row says why.** Every error a task
meets is read once for what it means (`error_cause`). A code defect ends its row
`failed` with the fault `raised`; an explicit refusal only a person can settle
ends it `failed` with `manual-action`. A cause outside the code - GitHub's API
that did not answer, or a period waiting for a later wake or a named repair -
ends it `deferred` with a word that names it. Its siblings still run either
way, and what it had already done is on the row, because the core carries it
out of any stop part way. **Only a failed row, or a shard over its download
budget, makes the shard exit 1**; a deferred one leaves the exit code as it was.

**Every task is handed the folders it walks, judged against the commit.** A
folder the commit holds is walked whether the checkout holds it or not, because
a task learns its members from the commit's names and fetches only what it
reads. A declared folder the commit does not hold yet is left out, and the
task's `TaskPlanned` event names it: nothing has written one, and the task's
first write makes it. A complement task is answered only from the commit, so a
caller that could not read it is refused before any task runs.

**Each task is said twice in the log, before it runs and when it ends.**
`TaskPlanned` names its run and every knob of its declaration;
`TaskFinished`, logged the moment the task returns, says how it ended in one
word, what it took and wrote, and what happens next (`report.finished`). A
later refusal of the whole shard cannot hide how a task ended. The exception
that stopped a task is kept beside its row, so its event names the type and
where it was raised, and never its text. Each `TaskFinished` also goes back on
the `Outcome`, with what the tasks downloaded and whether that passed the
budget, so the publisher's summary of the shard reads the same events the log
holds.

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
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh import ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason, stop_for
from idhazh.contracts.file_envelope import Format, WriterIdentity
from idhazh.contracts.gardener_events import TaskFinished, TaskOutcome, TaskPlanned
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.knobs.gardener import (
    CollectionTaskPolicy,
    CompactionPolicy,
    TaskKind,
    TaskLifecycleStatus,
    TaskPolicy,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import error_cause, event_log, ownership, registry, report, shards
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.context import TaskContext
from idhazh.gardener.error_cause import ErrorCause
from idhazh.gardener.file_listing import FileListing, OverBudgetError
from idhazh.gardener.one_at_a_time import Pass, PruneInterruptedError
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome, Shard
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range
from idhazh.ledger import staging
from idhazh.site_weight import BYTES_PER_MB
from idhazh.telemetry import job_machine

#: The name the record's writer carries in its envelope. This module writes it.
PRODUCER: Final = "gardener.runner"
VENUE_LEDGERS: Final = (LedgerName.GARDENER, LedgerName.HOST_FINGERPRINT)

#: The timestamp shape every instant in a record takes: UTC, to the second.
_INSTANT: Final = "%Y-%m-%dT%H:%M:%SZ"

#: How many of a shard's folders an over-weight message names, heaviest first.
_HEAVIEST_NAMED: Final = 3

#: The one program that runs a history task, named in the refusal to run one here.
HISTORY_PROGRAM: Final = "backend/utilities/corpus_history.py"

#: The keys of a declaration a task's planned event leaves out: what it is, the
#: folders it may touch and the ledgers it may file into, and its prose. Every
#: other key is a knob.
_NOT_KNOBS: Final = frozenset({"kind", "owns", "reads", "appends_to", "prune_refusal"})

#: The level a task's finished event is logged at: a defect is an error, a
#: cause outside the code a warning, and every other ending is information.
_LEVELS: Final = {TaskOutcome.FAILED: logging.ERROR, TaskOutcome.DEFERRED: logging.WARNING}


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
    for name, module in bound.items():
        try:
            ownership.owned_prefixes(tasks[name], module.owned_ledgers)
        except ValueError as error:
            raise registry.DiscoveryError(f"{name}: {error}") from error
    return bound


def _nested(path: str, folder: str) -> bool:
    """Whether `path` is `folder` or sits inside it, compared segment by segment."""
    inner, outer = PurePosixPath(path).parts, PurePosixPath(folder).parts
    return inner[: len(outer)] == outer


def owner_of(
    name: str,
    tasks: Mapping[str, TaskPolicy],
    declared: tuple[LedgerName, ...] = (),
) -> Callable[[str], bool]:
    """Whether a path sits inside one of this task's configured folders."""
    folders = ownership.owned_prefixes(tasks[name], declared)
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


def _nothing_reached(name: str, policy: TaskPolicy, fault: GardenerFault) -> Pass:
    """The pass of a task that stopped before it reached a single member, for this cause."""
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
        stopped_because=stop_for(fault),
        resume_from=None,
        fault=fault,
    )


@dataclass(frozen=True, slots=True)
class _Ran:
    name: str
    context: TaskContext
    outcome: Pass
    duration_ms: int
    #: Whether the task's row says `failed`: a code defect, the one stop that
    #: turns the shard's exit code to 1.
    failed: bool
    #: The exception that stopped the task, which its event names by type and
    #: place. None when nothing raised.
    failure: BaseException | None = None


def _run_one(name: str, held: registry.TaskModule, context: TaskContext) -> _Ran:
    """One task, timed, with any error read for what it means and turned into its row.

    The error itself is kept beside the row, so the task's event can name its
    type and where it was raised; its text goes nowhere.
    """
    started = time.monotonic()
    failure: BaseException | None = None
    try:
        outcome = (
            _run_compaction_roots(held, context)
            if isinstance(context.policy, CompactionPolicy)
            and context.policy.state_roots != ["state"]
            else held.run(context)
        )
    except PruneInterruptedError as stop:
        outcome, failure = stop.so_far, stop.__cause__
    except Exception as caught:
        fault = error_cause.fault_of(error_cause.classify(caught))
        outcome, failure = _nothing_reached(name, context.policy, fault), caught
    elapsed = int((time.monotonic() - started) * 1000)
    return _Ran(
        name=name,
        context=context,
        outcome=outcome,
        duration_ms=elapsed,
        failed=outcome.stopped_because is StopReason.FAILED,
        failure=failure,
    )


def _run_compaction_roots(held: registry.TaskModule, context: TaskContext) -> Pass:
    """Run one pass per declared root, stopping when the first root needs another wake.

    A trial root is a segment path spliced after the tier, not a directory the
    pass enters: `state_dir` stays `state/` for every root, and what changes
    per root is which registry `path`/`raw_root`/`tree_root` fall back to
    (`ledger.use_registry`, `ledger.overlay_registry`) - so a trial's files sit
    at `state/raw/<segments>/<ledger>`, beside every other ledger's
    `state/raw/<ledger>`, rather than under a root of their own.
    """
    from idhazh.contracts.gardener_events import PeriodsTaken

    policy = context.policy
    if not isinstance(policy, CompactionPolicy):
        raise ValueError("a compaction root pass needs a compaction declaration")
    outcomes: list[Pass] = []
    for state_root in policy.state_roots:
        segments = PurePosixPath(state_root).relative_to("state").parts
        owns = tuple(
            folder
            for folder in policy.owns
            if (parts := PurePosixPath(folder).parts)[:1] == ("state",)
            and parts[1:2] in (("raw",), ("compact",))
            and parts[2 : 2 + len(segments)] == segments
        )
        if not owns:
            raise ValueError(f"{state_root} has no owned folders for {policy.ledger.value}")
        root_context = replace(
            context,
            owned_folders=tuple(folder for folder in context.owned_folders if folder in owns),
            listing=context.listing.within(owns),
        )
        with ledger.use_registry(ledger.overlay_registry(segments)):
            outcome = held.run(root_context)
        outcomes.append(outcome)
        if outcome.more_to_do:
            break

    first, last = outcomes[0], outcomes[-1]
    period_data = first.periods.model_dump() if first.periods is not None else None
    if period_data is not None:
        for outcome in outcomes[1:]:
            if outcome.periods is None:
                continue
            next_data = outcome.periods.model_dump()
            for field in ("daily_mark", "monthly_mark", "yearly_mark"):
                values = [value for value in (period_data[field], next_data[field]) if value]
                period_data[field] = max(values, default=None)
            for field, values in next_data.items():
                if isinstance(values, list):
                    period_data[field] = list(dict.fromkeys([*period_data[field], *values]))
        periods = PeriodsTaken.model_validate(period_data)
    else:
        periods = None
    return replace(
        last,
        since=first.since,
        until=first.until,
        seen=sum(outcome.seen for outcome in outcomes),
        selected=sum(outcome.selected for outcome in outcomes),
        taken=tuple(dict.fromkeys(path for outcome in outcomes for path in outcome.taken)),
        written=tuple(dict.fromkeys(path for outcome in outcomes for path in outcome.written)),
        bytes_freed=sum(outcome.bytes_freed for outcome in outcomes),
        appended=tuple(dict.fromkeys(path for outcome in outcomes for path in outcome.appended)),
        handled_through=next(
            (outcome.handled_through for outcome in reversed(outcomes) if outcome.handled_through),
            None,
        ),
        recovered=tuple(note for outcome in outcomes for note in outcome.recovered),
        pages_read=(
            None
            if any(outcome.pages_read is None for outcome in outcomes)
            else sum(outcome.pages_read or 0 for outcome in outcomes)
        ),
        periods=periods,
    )


def _planned(
    name: str, context: TaskContext, folders: Folders, operator_range: tuple[str, str] | None
) -> TaskPlanned:
    """What a task is about to run with: its run, its knobs, and folders the commit lacks.

    `operator_range` is the range a person named for this run, never the
    scheduled window a retention task is handed in its place.
    """
    policy = context.policy
    return TaskPlanned(
        task=name,
        kind=TaskKind(policy.kind),
        shard=context.shard,
        run_id=context.run_id,
        attempt=context.attempt,
        today=context.today.isoformat(),
        operator_range=operator_range,
        declared=policy.model_dump(mode="json", exclude=set(_NOT_KNOBS)),
        absent=list(folders.absent),
    )


def _said_finished(ran: _Ran) -> TaskFinished:
    """Log how one task ended, at the level its outcome asks for, and hand the event back."""
    policy = ran.context.policy
    finished = report.finished(
        ran.outcome,
        task=ran.name,
        duration_ms=ran.duration_ms,
        failure=ran.failure,
        collection=policy.collection if isinstance(policy, CollectionTaskPolicy) else None,
    )
    event_log.emit(finished, level=_LEVELS.get(finished.outcome, logging.INFO))
    return finished


def _touched(ran: _Ran) -> tuple[str, ...]:
    """Every repository path a task touched: what it wrote and what it took."""
    taken = () if ran.context.policy.kind == TaskKind.COLLECTION else ran.outcome.taken
    return (*taken, *ran.outcome.written)


def _landed(ran: _Ran) -> tuple[set[str], set[str]]:
    """What a task changed in the tree, and so lands: the paths it wrote, and the ones it deleted.

    A dry run's writes and deletions are only reported, so they land nowhere. A
    report lands dry run or not, because it is what a dry run exists to produce.
    What a collection task takes lives on GitHub, not in this repository.
    """
    live = not ran.context.policy.dry_run
    wrote = {*(ran.outcome.written if live else ()), *ran.outcome.appended}
    took = ran.outcome.taken if live and ran.context.policy.kind != TaskKind.COLLECTION else ()
    return wrote, set(took)


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


def _refuse_a_path_outside(
    ran: _Ran, tasks: Mapping[str, TaskPolicy], declared: tuple[LedgerName, ...]
) -> None:
    owns = owner_of(ran.name, tasks, declared)
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
        )
        for each in ran
    ]
    written = ledger.persist(
        state_dir, rows, ledger=LedgerName.GARDENER, covers=today, identity=identity
    )
    if len(written) != 1:
        raise ShardRefusedError(
            f"the shard's rows went to {len(written)} files, and a shard writes one record. "
            f"A write that landed nothing means the {LedgerName.GARDENER.value} family is "
            "paused or retired, and the gardener cannot record a wake into a family that "
            "takes no new rows"
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
        raise ShardRefusedError(f"{record.name} is not a record's name") from error
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
    exactly the ceiling is inside it. `error_cause.classify` decides it by the
    rule it decides a single period by, that more than the whole budget is a
    defect: a step that chooses its periods by the budget never passes it, so a
    shard over it is a code defect to fix, and no row can say which task did it.
    """
    total = sum(downloaded.values())
    budget = ceiling_mb * BYTES_PER_MB
    spent = OverBudgetError(needed=total, room=budget - total, budget=budget)
    if error_cause.classify(spent) is not ErrorCause.RAISED:
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
    have run. `period_range` is the effective range the task may read: the
    range a person named, or the window `scheduled_range` builds for a
    scheduled wake. `operator_range` keeps only the range a person named. A
    compaction has no scheduled window, so a named range only limits the
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
    operator_range = period_range
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
    finished: list[TaskFinished] = []
    too_heavy: str | None = None
    downloaded_bytes: int | None = None
    try:
        with job_machine.record(
            date=today.isoformat(),
            run_id=run_id,
            settings=settings,
            state_root=state_dir,
            commit_sha=git_sha,
            job=job,
            shard=shard,
            attempt=attempt,
            started_at=started,
            clock=clock,
        ) as machine:
            # Resolve ownership before the first task runs.
            resolved = {
                name: folders_of(name, settings.tasks, repo_root, committed_folders)
                for name in names
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
                    first_ledger_year=settings.config.first_ledger_year,
                    operator_range=operator_range,
                    period_range=period_ranges[name],
                )
                event_log.emit(_planned(name, context, resolved[name], operator_range))
                done = _run_one(name, bound[name], context)
                finished.append(_said_finished(done))
                _refuse_a_path_outside(done, settings.tasks, bound[name].owned_ledgers)
                _refuse_an_append_outside(done, today.isoformat())
                ran.append(done)
                written, taken = _landed(done)
                listing = listing.settled(written=written, deleted=taken)
            downloaded = listing.downloaded()
            if downloaded is not None:
                downloaded_bytes = sum(downloaded.values())
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
                downloaded_bytes=downloaded_bytes,
            )
    except ShardRefusedError as refusal:
        # An ownership refusal must leave no machine files eligible for a commit.
        for path in machine:
            path.unlink(missing_ok=True)
        say(f"shard {shard}: {refusal}")
        return Outcome(
            exit_code=EXIT_INTEGRITY,
            record=None,
            landing=None,
            finished_tasks=tuple(finished),
            downloaded_bytes=downloaded_bytes,
        )

    if too_heavy is not None:
        say(too_heavy)
    recorded = record.relative_to(repo_root).as_posix()
    machine_paths = {path.relative_to(repo_root).as_posix() for path in machine}
    wrote = {path for each in ran for path in _landed(each)[0]}
    deleted = {path for each in ran for path in _landed(each)[1]}
    landing = Shard(
        index=shard,
        task_names=tuple(names),
        record_path=recorded,
        written_paths=frozenset({recorded, *machine_paths, *wrote}),
        deleted_paths=frozenset(deleted),
        owned_prefixes=frozenset(
            [
                *(staging.staged_path(which) for which in VENUE_LEDGERS),
                *(
                    prefix
                    for name in names
                    for prefix in ownership.owned_prefixes(
                        settings.tasks[name], bound[name].owned_ledgers
                    )
                ),
                *(
                    staging.staged_path(which)
                    for name in names
                    for which in settings.tasks[name].appends_to
                ),
            ]
        ),
        message=f"gardener: {', '.join(names)} on {today.isoformat()}",
    )
    failed = any(each.failed for each in ran) or too_heavy is not None
    tasks_code = EXIT_TASK_FAILED if failed else EXIT_OK
    return Outcome(
        exit_code=tasks_code,
        record=record,
        landing=landing,
        finished_tasks=tuple(finished),
        downloaded_bytes=downloaded_bytes,
        over_budget=too_heavy is not None,
    )


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
