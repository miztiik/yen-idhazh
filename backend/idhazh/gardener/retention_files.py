"""How does a retention task take files from its own folders, one at a time, under its ceiling?

Every retention task walks files - a published month copy, a digest fragment,
a trace, a published picture. Which files are old enough is each task's own question, and
it is answered in the task. What they share is here: each file is one member of
`one_at_a_time.take`, named by its repository path, dated by the day it records,
and deleted with any empty folder it leaves behind.

**A task hands on only the files past its boundary.** `take` reads each member
before it holds it to the window, and each task walks its listing the way the
pass it replaced walked the disk and yields only what is old enough, so the
records stay what they were. A member's size is the listing's, so nothing is
opened to weigh it.

**A window becomes one day: the oldest one kept.** A month window keeps whole
calendar months back to `month_partition.oldest_month_kept`; a day window is
counted the way the ledger's own reader counts it, which the task says; a window
that keeps for ever takes nothing at all.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from idhazh import month_partition
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.gardener_events import TaskOutcome
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
    readers disagree and each prune has always matched its own reader: a day's
    digest fragments are kept for `today` and the window's days before it, while
    a trace is kept while it is less than seven days old.
    """
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return days_back(window.value)
    return date.fromisoformat(f"{month_partition.oldest_month_kept(today, window.value)}-01")


def first_kept_month(window: Window, today: date) -> str | None:
    """The oldest `YYYY-MM` a window keeps whole. None keeps every month.

    A window of days keeps the whole month its oldest day falls in, so a month
    is still taken whole or not at all.
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


def first_day_of(month: str | None) -> date | None:
    """The first day of a `YYYY-MM` month, or None for no month at all."""
    return None if month is None else date.fromisoformat(f"{month}-01")


def take_files(
    context: TaskContext,
    aged: Iterable[Aged],
    *,
    collection: str,
    first_kept: date | None,
    after_delete: Callable[[Path], None] = _nothing,
    before_delete: Callable[[Aged], None] | None = None,
) -> Pass:
    """Delete each aged file in the order given, up to the declaration's ceiling.

    `first_kept` is the oldest day the window keeps, so the record's `until` is
    the day before it and says which days the window held. Every file handed in
    is already older than that, so the window only confirms it. None is a window
    that keeps every day, which takes nothing and reads nothing.

    `before_delete` runs ahead of each delete of a live pass and may refuse it by
    raising: a task that writes a summary before the files it replaces go writes
    it there, so a summary that will not read back stops the pass with those
    files still in place.
    """
    idle_outcome = (
        TaskOutcome.OUTSIDE_RANGE
        if context.operator_range is not None
        else TaskOutcome.NOT_DUE
    )
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
            idle_outcome=idle_outcome,
        )
    root = context.repo_root

    def describe(item: Aged) -> Member:
        return Member(
            id=item.path.relative_to(root).as_posix(),
            day=item.day,
            size_bytes=context.listing.size_of(item.path),
            label=item.path.name,
        )

    def delete(item: Aged) -> None:
        if before_delete is not None:
            before_delete(item)
        # A file decided on by its name alone may never have been downloaded. The
        # deletion lands from its name, so there may be nothing on disk to remove.
        item.path.unlink(missing_ok=True)
        after_delete(item.path)

    if context.period_range is None:
        span = Span(until=(first_kept - timedelta(days=1)).isoformat())
    else:
        start, end = context.period_range
        if month_partition.is_month_stem(start):
            first_day, last_day = month_partition.day_bounds(start, end)
            span = Span(since=first_day, until=last_day)
        else:
            span = Span(since=start, until=end)
    return replace(
        take(
            Collection(name=collection, listing=lambda: aged, describe=describe, delete=delete),
            window=span,
            ceiling=context.policy.max_deletes_per_run,
            dry_run=context.policy.dry_run,
        ),
        idle_outcome=idle_outcome,
    )
