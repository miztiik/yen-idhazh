"""How does a retention task take files from its own folders, one at a time, under its ceiling?

Every retention task walks files - a day file, a writer's segment, a trace, a
published picture. Which files are old enough is each task's own question, and
it is answered in the task. What they share is here: each file is one member of
`one_at_a_time.take`, named by its repository path, dated by the day it records,
and deleted with any empty folder it leaves behind.

**A task hands on only the files past its boundary.** `take` reads each member
before it holds it to the window, and reading a file here is a `stat`, so a
listing of the whole tree would weigh the whole tree on every wake. Each task
walks what the pass it replaced walked and yields only what is old enough, so
the cost follows the backlog rather than the archive (Guardrail #12).

**A window becomes one day: the oldest one kept.** A month window keeps whole
calendar months back to `month_partition.oldest_month_kept`; a day window is
counted the way the ledger's own reader counts it, which the task says; a window
that keeps for ever takes nothing at all.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from idhazh import month_partition
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow, Window
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Collection, Member, Pass, take
from idhazh.gardener.one_at_a_time import Window as Span


@dataclass(frozen=True, slots=True)
class Aged:
    """One file past the boundary, and the `YYYY-MM-DD` day it records."""

    path: Path
    day: str


def _nothing(_: Path) -> None:
    """What happens after a delete when the tree keeps no folder per day."""


def first_kept_day(
    window: Window, today: date, *, days_back: Callable[[int], date]
) -> date | None:
    """The oldest day a window keeps, or None when it keeps every day there will ever be.

    `days_back` is how this task's ledger counts a window of days, because the
    readers disagree and each prune has always matched its own reader: the seen
    planner opens `today` and the ninety days before it, while a trace is kept
    while it is less than seven days old.
    """
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return days_back(window.value)
    return date.fromisoformat(f"{month_partition.oldest_month_kept(today, window.value)}-01")


def first_kept_month(window: Window, today: date) -> str | None:
    """The oldest `YYYY-MM` a month-grain ledger keeps whole. None keeps every month.

    A window of days on such a ledger keeps the whole month its oldest day falls
    in, so a month is still taken whole or not at all.
    """
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return (today - timedelta(days=window.value)).isoformat()[:7]
    return month_partition.oldest_month_kept(today, window.value)


def owned_tree(context: TaskContext, tree: Path) -> Path | None:
    """`tree`, when the runner handed it to this task to walk, else None.

    The runner leaves out a declared folder the commit does not hold yet, so a
    task never walks a folder it was not given - not even its own ledger's.
    """
    relative = tree.relative_to(context.repo_root).as_posix()
    return tree if relative in context.owned_folders else None


def take_files(
    context: TaskContext,
    aged: Iterable[Aged],
    *,
    collection: str,
    first_kept: date | None,
    after_delete: Callable[[Path], None] = _nothing,
) -> Pass:
    """Delete each aged file in the order given, up to the declaration's ceiling.

    `first_kept` is the oldest day the window keeps, so the record's `until` is
    the day before it and says which days the window held. Every file handed in
    is already older than that, so the window only confirms it. None is a window
    that keeps every day, which takes nothing and reads nothing.
    """
    if first_kept is None:
        return Pass(
            collection=collection,
            since=None,
            until=None,
            ceiling=context.policy.max_deletes_per_run,
            dry_run=context.policy.dry_run,
            seen=0,
            selected=0,
            taken=(),
            written=(),
            bytes_freed=0,
            stopped_because=StopReason.EXHAUSTED,
            resume_from=None,
        )
    root = context.repo_root

    def describe(item: Aged) -> Member:
        return Member(
            id=item.path.relative_to(root).as_posix(),
            day=item.day,
            size_bytes=item.path.stat().st_size,
            label=item.path.name,
        )

    def delete(item: Aged) -> None:
        item.path.unlink()
        after_delete(item.path)

    return take(
        Collection(name=collection, listing=lambda: aged, describe=describe, delete=delete),
        window=Span(until=(first_kept - timedelta(days=1)).isoformat()),
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
    )
