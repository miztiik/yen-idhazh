"""How do I delete a collection's members one at a time, safely, resumably, under a ceiling?

Nothing here knows what a member is. A caller hands in three callables - list,
describe, delete - a window and a ceiling, and gets back a record of what the
pass took and where the next pass starts. That is the whole surface, and it is
what lets one piece of code prune a ledger's day files, GitHub's workflow
artifacts and anything added later.

**Atomic means per member, and it is not the same word `idhazh.telemetry.prune`
used until 2026-09-17.** That module collected a whole range, renamed every file
into a scratch directory, and removed the directory once every rename had
worked - all of them or none of them, with a rollback if a rename failed. This
one deletes member 1, then member 2, then member 3. An interruption after member
N leaves members 1 to N deleted and N+1 onward untouched. Nothing is half-done,
because one delete is the unit and a delete either happened or it did not.

**No rollback, on purpose.** A rollback is a second write path, it can fail
while it is undoing, and it holds every earlier member hostage to the last one.
The price of losing it is that a failed pass is not a no-op. That is the right
trade for a delete: nothing here is recoverable anyway once the scheduled
history prune has passed over it, so "the tree is exactly as you found it" was
never a promise this could keep - only a promise about one process.

**The ceiling is the point, not a safety valve.** One pass deletes at most
`ceiling` members and then stops cleanly, saying where to resume. A pass that
tried to clear a backlog of 612 in one go would hold a rate limit, a job
timeout and a half-finished collection all at once. A pass that takes 50 and
names the 51st can be run again, or scheduled, and each run is the same shape
and the same cost.

**The listing is never held.** It is an iterable that the pass walks and drops.
A caller that pages an API yields one page at a time; a caller that walks a
directory yields one path at a time. Neither builds a list, so the memory a pass
costs is its ceiling and not its collection (Guardrail #12).

**A walk from a mark resumes the day after it.** A caller whose listing yields
members oldest day first, and only those created after a day every earlier
member was handled through, hands that day in as `mark`. The pass says on its
record the newest day it handled whole, and the next pass starts after that.
A dry run never stops part way through a day: it deletes nothing, so it would
report the same members again on every wake. Past its ceiling it counts the
rest of that day without naming them, and its mark moves to that day. A
listing that can see it may have missed a member - pages that shifted under it,
or an order it checks that broke - says so, and the mark stays where it was.

**A refusal is by name, with a reason.** A collection missing from a vocabulary
reads as an oversight; a collection refused with a sentence reads as a decision.
Somebody who typed a refused word is holding a real question, and the answer
they need is why the answer is no.

**A pass says its window before it lists a member.** `take` logs one
`WindowChosen` event once its arguments are checked, so a pass that stops part
way has already said what it was holding members to. A listing that pages says
how many pages it read through `Collection.pages_read`, and the pass carries
the count on its record.

**An error part way is read for what it means, and never relabelled.** Every
error the pass catches is classified once (`error_cause.classify`): a code
defect stops it `failed`, an API that did not answer stops it `deferred`, and
on a delete a member its collection will not let go of is recorded by its id,
counted against the ceiling, and passed. The pass goes on to the next member,
and the mark may pass it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta

from idhazh.contracts.collection_prune import Recovery, StopReason, stop_for
from idhazh.contracts.gardener_events import (
    MemberOutOfOrder,
    PeriodsTaken,
    TaskOutcome,
    WindowChosen,
)
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.gardener import error_cause, event_log
from idhazh.gardener.error_cause import ErrorCause


@dataclass(frozen=True, slots=True)
class Member:
    """One member of a collection, described the one way this module can compare two.

    Four facts and no more. An id to name it by and to resume from, a day to
    hold against the window, a size so a pass can say what it freed, and a label
    a person reads. Anything else a caller needs it already has, because it is
    the one that produced the member.
    """

    #: The member's own id, as its collection spells it. It becomes `resume_from`
    #: on the record, so it has to survive a round trip through JSON as text.
    id: str
    #: `YYYY-MM-DD`, the day the member was created. Text rather than a `date`
    #: because an ISO day sorts chronologically as text, which is how every
    #: other date comparison in this tree works.
    day: str
    #: What deleting this member frees. 0 is honest where the collection does
    #: not publish a size - a workflow run's logs are one.
    size_bytes: int
    #: What a person would call it. Printed, never matched on.
    label: str


@dataclass(frozen=True, slots=True)
class Window:
    """Which members qualify, by the day they were created.

    Both ends are inclusive and either may be absent, but not both: a window
    that holds every member is not a window, it is a prune of the collection,
    and this refuses to be handed one.
    """

    since: str | None = None
    until: str | None = None

    def __post_init__(self) -> None:
        for end, flag in ((self.since, "since"), (self.until, "until")):
            if end is not None and not _is_a_day(end):
                raise ValueError(f"{flag} takes a YYYY-MM-DD day, not {end!r}")
        if self.since is None and self.until is None:
            raise ValueError(
                "a window with neither end named holds every member, which is not a "
                "window. Name an age with Window.older_than, or name both days"
            )
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError(
                f"since {self.since} is after until {self.until}, so the window names no day"
            )

    @classmethod
    def older_than(cls, *, today: str, days: int) -> Window:
        """Everything created more than `days` ago, however old.

        The upper end is `today - days` and it is inclusive, so `days=30` on the
        17th holds the 18th of last month and everything before it. There is no
        lower end: an age policy has no floor, and inventing one would quietly
        strand whatever fell under it.
        """
        if not _is_a_day(today):
            raise ValueError(f"today takes a YYYY-MM-DD day, not {today!r}")
        if days < 1:
            raise ValueError(
                f"an age window is at least one whole day, not {days}. A window that "
                "includes today would delete what the running job just wrote"
            )
        line = date_type.fromisoformat(today) - timedelta(days=days)
        return cls(until=line.isoformat())

    def holds(self, day: str) -> bool:
        """Whether a member created on `day` qualifies."""
        if self.since is not None and day < self.since:
            return False
        return not (self.until is not None and day > self.until)


def _always_intact() -> bool:
    """A listing that cannot see a gap of its own has none to report."""
    return True


def _no_pages() -> int | None:
    """A listing that reads no pages has no count of them."""
    return None


@dataclass(frozen=True, slots=True)
class Collection[Raw]:
    """One collection, as three callables and a name, and two more that may report on the listing.

    `Raw` is whatever the caller's listing yields - a page of JSON, a `Path`.
    This module never looks inside one: it passes it to the caller's own
    `describe`, and back to the caller's own `delete`.

    `listing` yields members and is walked once, lazily. `describe` reads one
    raw member into a `Member`. `delete` removes exactly one and returns when it
    is gone - it takes the raw member rather than the description, so a driver
    deletes the thing it listed rather than rebuilding it from an id.
    Splitting the three is what makes a collection something a caller supplies
    rather than something this module has to know.

    `listing_intact` says whether the listing, as far as it has been walked,
    has yielded every member of each day it reached, in day order. A listing
    that checks itself - pages counted against each other, an order it relies
    on - turns it false when a check fails, and a walk from a mark then keeps its
    mark. A listing that checks nothing leaves the default, which is always true.

    `pages_read` says how many pages the listing has read so far, for one that
    reads an API a page at a time, and None for one that has no pages.
    """

    name: str
    listing: Callable[[], Iterable[Raw]]
    describe: Callable[[Raw], Member]
    delete: Callable[[Raw], None]
    listing_intact: Callable[[], bool] = _always_intact
    pages_read: Callable[[], int | None] = _no_pages


@dataclass(frozen=True, slots=True)
class Pass:
    """What one pass saw, took, and left for the next one.

    `taken` is the ids in the order they went, and it is the same list on both
    sides of `dry_run` - named as the pass walks, so the list a dry run prints is
    the list a live pass removes, member for member. That list is the deliverable
    of a dry run, which is why a count would not do.

    `written` is the files the pass wrote, or would have written on a dry run,
    as repository-relative POSIX paths. A pass that only deletes writes nothing,
    so `take` always leaves it empty; a task that writes a file of its own fills
    it, and the runner holds every path in it to what the task owns.

    `appended` is the raw report files a task filed through the ledger door into
    a ledger its declaration `appends_to`, on a dry run too. They are held to
    that ledger's wake-day folder rather than to what the task owns, and they land
    whatever `dry_run` says, because a report is what a dry run is for. A task
    that writes a non-report row through `appends_to` names it in `written`; dry
    run reports that path without landing it.

    `handled_through` is the newest UTC day through which every member was
    handled, by this pass or the ones before it, on a pass that walked from a
    mark. It is None on every other pass.

    `fault` is why the pass stopped when a fault stopped it: `raised` on a
    failed pass, every other word on a deferred one, and None on a pass that
    ran out or met its ceiling. `recovered` is every fault it recorded instead
    of stopping, in the order it met them: a member its collection would not
    delete, or a period a compaction rebuilt, moved aside or recorded lost.

    `idle_outcome` is the word for a pass that found nothing to do, which only
    the pass can choose: nothing has reached its line yet, the ledger holds
    nothing, or a range a person named holds nothing that may be taken.
    `pages_read` is how many pages its listing read, or None for a listing with
    no pages. `periods` is what a compaction did, period by period, and None
    for every other pass.
    """

    collection: str
    since: str | None
    until: str | None
    #: The most one pass may take. None is no ceiling at all, and 0 is a survey.
    ceiling: int | None
    dry_run: bool
    seen: int
    selected: int
    taken: tuple[str, ...]
    written: tuple[str, ...]
    bytes_freed: int
    stopped_because: StopReason
    resume_from: str | None
    appended: tuple[str, ...] = ()
    handled_through: str | None = None
    fault: GardenerFault | None = None
    recovered: tuple[Recovery, ...] = ()
    idle_outcome: TaskOutcome = TaskOutcome.NOT_DUE
    pages_read: int | None = None
    periods: PeriodsTaken | None = None

    @property
    def changed(self) -> bool:
        return bool(self.taken) and not self.dry_run

    @property
    def more_to_do(self) -> bool:
        """Whether running this again would take anything else.

        Read off why the pass stopped rather than off the resume point: a pass
        that failed before it could name a member has no resume point and still
        has everything left to do.
        """
        return self.stopped_because is not StopReason.EXHAUSTED


class PruneInterruptedError(Exception):
    """A pass stopped part way. `so_far` says what it had already taken, and why it stopped.

    Raised rather than returned, because a stopped pass is not a clean one and
    swallowing it would report a clean pass over a collection this could not
    touch. Carried rather than bare, because the caller still has to know that
    members 1 to N are gone and which one to retry - an exception with no record
    would leave an operator unable to answer either. `so_far` carries the
    classified cause in `fault`, so a code defect is never read as an outage.
    A dry run deleted none of the members it named, and its message says so.

    A delete is not the only thing that fails. The listing can raise part way
    through a walk and `describe` can raise on one member, and either can happen
    after some members are already gone - so both are carried the same way.
    """

    def __init__(self, so_far: Pass) -> None:
        where = (
            f"the next pass resumes at {so_far.resume_from}"
            if so_far.resume_from is not None
            else "the next pass starts again from the oldest member the window holds"
        )
        how = "failed" if so_far.stopped_because is StopReason.FAILED else "was deferred"
        cause = "" if so_far.fault is None else f" ({so_far.fault.value})"
        kept = "It was a dry run, so none was deleted" if so_far.dry_run else "Those are gone"
        super().__init__(
            f"{so_far.collection}: the pass {how}{cause} after {len(so_far.taken)} members. "
            f"{kept}; {where}"
        )
        self.so_far = so_far


def refuse_by_name(
    name: str,
    *,
    allowed: Sequence[str],
    refused: Mapping[str, str],
    noun: str = "collection",
) -> str:
    """The collection this name points at, or a refusal that says why.

    One place a vocabulary is checked, so a parser, a body and any later caller
    cannot disagree about which words are collections. A word outside the
    vocabulary and a word refused by name are different answers and this is
    where the distinction is drawn - collapsing both into "invalid choice" loses
    the reason, which is the only useful half of a refusal.

    `noun` is what the caller's vocabulary is made of. A ledger and a GitHub
    collection are the same shape and not the same word, and an operator reading
    a refusal should see the word they typed a name of.
    """
    if name in allowed:
        return name
    if name in refused:
        raise ValueError(f"{name} is refused: {refused[name]}. This prunes {', '.join(allowed)}")
    raise ValueError(
        f"a prune takes the name of a {noun}, not {name!r}. A path is never a "
        f"name here, because a deletion primitive that resolved its argument against "
        f"the file system is the one accident nobody can undo. This prunes "
        f"{', '.join(allowed)}" + (f"; {', '.join(refused)} are refused by name" if refused else "")
    )


def take[Raw](
    collection: Collection[Raw],
    *,
    window: Window,
    ceiling: int | None,
    dry_run: bool = True,
    mark: str | None = None,
) -> Pass:
    """Delete up to `ceiling` members the window holds, one at a time, in listing order.

    This walks what it is given and does not sort, because sorting is holding
    the collection. A caller whose order matters yields in that order.

    The window is tested before the ceiling, which is what makes the resume
    point honest. Tested the other way round, a pass that had filled its ceiling
    would stop at the next member it saw and name it - and that member might be
    one the window never held, so the next pass would start from a member it has
    no business deleting.

    A ceiling of None takes every member the window holds. It is a real answer
    rather than a large number standing in for one, so the record can say "no
    ceiling" instead of printing a number nobody chose.

    **Anything that raises part way is carried, not just a delete.** A listing
    that fails on its third page, or a member `describe` cannot read, can come
    after members are already gone. Raised bare, that failure would reach the
    caller with no record of them, and the row it wrote would say nothing was
    deleted. Neither failure has a member to name, so the record's resume point
    is empty and the next pass starts again from the oldest member the window
    holds. What stopped the pass is classified once (`error_cause`): a code
    defect ends it `failed`, an API that did not answer ends it `deferred`.

    **A member its collection will not delete is recorded and passed.** The
    delete's answer says so (`NOT_DELETABLE`): the member's id becomes a
    `not-deletable` note, it counts against the ceiling as a delete would, and
    the pass goes on. Its day is handled all the same, so the mark may pass it.
    Before, one refused member stopped every later pass, and nothing behind it
    was ever deleted.

    **With a `mark`, the listing is a walk of whole days, oldest first.** Every
    member created on or before the mark was handled by an earlier pass, so one
    that arrives is passed over, and the listing yields the rest in day order up
    to the window's last day. `handled_through` is then the day before the
    newest day a member arrived from, and the window's last day once the
    listing ends. A pass whose mark is already that day reads nothing. A member
    from an earlier day than one before it means the listing is out of order:
    the pass goes on, every member still held to the window, but which days are
    whole can no longer be said, so the mark stays where the pass started, and
    the pass says so once (`MemberOutOfOrder`). A
    listing that reports a gap of its own through `listing_intact` keeps the
    mark there too, whichever way the pass ends.
    """
    if ceiling is not None and ceiling < 0:
        raise ValueError(f"a ceiling is a count of members, not {ceiling}")
    line = window.until
    if mark is not None:
        if not _is_a_day(mark):
            raise ValueError(f"a mark takes a YYYY-MM-DD day, not {mark!r}")
        if line is None:
            raise ValueError("a walk from a mark ends at the window's last day, and it has none")
    event_log.emit(
        WindowChosen(
            collection=collection.name,
            since=window.since,
            until=window.until,
            ceiling=ceiling,
            dry_run=dry_run,
            mark=mark,
        )
    )

    seen = 0
    selected = 0
    taken: list[str] = []
    #: The members the collection would not delete, by id, in the order met.
    kept: list[str] = []
    freed = 0
    through = mark
    newest: str | None = None
    in_order = True
    #: On a dry run past its ceiling, the first member it did not name: the rest
    #: of that member's day is counted, and the pass stops at the next day.
    over: Member | None = None

    def stopped(
        because: StopReason, resume_from: str | None, fault: GardenerFault | None = None
    ) -> Pass:
        """The record, built in one place so every exit describes a pass the same way."""
        return Pass(
            collection=collection.name,
            since=window.since,
            until=window.until,
            ceiling=ceiling,
            dry_run=dry_run,
            seen=seen,
            selected=selected,
            taken=tuple(taken),
            written=(),
            bytes_freed=freed,
            stopped_because=because,
            resume_from=resume_from,
            handled_through=through if collection.listing_intact() else mark,
            fault=fault,
            recovered=tuple(
                Recovery(note=RecoveryNote.NOT_DELETABLE, subject=member) for member in kept
            ),
            pages_read=collection.pages_read(),
        )

    def interrupted(failure: Exception, resume_from: str | None) -> PruneInterruptedError:
        """The pass so far, stopped by `failure` for what it means and never for less."""
        fault = error_cause.fault_of(error_cause.classify(failure))
        return PruneInterruptedError(stopped(stop_for(fault), resume_from, fault))

    if mark is not None and line is not None and mark >= line:
        return stopped(StopReason.EXHAUSTED, None)
    try:
        members = iter(collection.listing())
    except Exception as failure:
        raise interrupted(failure, None) from failure
    while True:
        try:
            raw = next(members)
        except StopIteration:
            break
        except Exception as failure:
            raise interrupted(failure, None) from failure
        seen += 1
        try:
            member = collection.describe(raw)
        except Exception as failure:
            raise interrupted(failure, None) from failure
        if not window.holds(member.day):
            continue
        if mark is not None:
            if member.day <= mark:
                continue
            try:
                before = _day_before(member.day)
            except ValueError as failure:
                raise interrupted(failure, None) from failure
            if in_order and newest is not None and member.day < newest:
                event_log.emit(
                    MemberOutOfOrder(collection=collection.name, day=member.day, after=newest),
                    level=logging.WARNING,
                )
                in_order, through = False, mark
            newest = member.day if newest is None else max(newest, member.day)
            if in_order:
                through = before
        selected += 1

        if over is not None:
            if member.day == over.day:
                continue
            return stopped(StopReason.CEILING, over.id)
        if ceiling is not None and len(taken) + len(kept) >= ceiling:
            if mark is not None and dry_run:
                over = member
                continue
            return stopped(StopReason.CEILING, member.id)

        if not dry_run:
            try:
                collection.delete(raw)
            except Exception as failure:
                if error_cause.classify(failure) is ErrorCause.NOT_DELETABLE:
                    kept.append(member.id)
                    continue
                raise interrupted(failure, member.id) from failure
        taken.append(member.id)
        freed += member.size_bytes

    if mark is not None and in_order:
        through = line
    if over is not None:
        return stopped(StopReason.CEILING, over.id)
    return stopped(StopReason.EXHAUSTED, None)


def _day_before(day: str) -> str:
    """The UTC day before a `YYYY-MM-DD` day, or a refusal for anything that is not one."""
    if not _is_a_day(day):
        raise ValueError(f"a member's day is a YYYY-MM-DD day, not {day!r}")
    return (date_type.fromisoformat(day) - timedelta(days=1)).isoformat()


def _is_a_day(value: str) -> bool:
    """`YYYY-MM-DD` and nothing else, width checked as well as parse.

    `date.fromisoformat` accepts `20260824` from Python 3.11, and a window
    compared as text would then put that day outside every window it belongs in.
    """
    if len(value) != 10:
        return False
    try:
        date_type.fromisoformat(value)
    except ValueError:
        return False
    return True
