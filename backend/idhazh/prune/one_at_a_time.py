"""How do I delete a collection's members one at a time, safely, resumably, under a ceiling?

Nothing here knows what a member is. A caller hands in three callables - list,
describe, delete - a window and a ceiling, and gets back a record of what the
pass took and where the next pass starts. That is the whole surface, and it is
what lets one piece of code prune a store's day files, GitHub's workflow
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

**A refusal is by name, with a reason.** A collection missing from a vocabulary
reads as an oversight; a collection refused with a sentence reads as a decision.
Somebody who typed a refused word is holding a real question, and the answer
they need is why the answer is no.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta

from idhazh.contracts.collection_prune import StopReason


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


@dataclass(frozen=True, slots=True)
class Collection[Raw]:
    """One collection, as three callables and a name.

    `Raw` is whatever the caller's listing yields - a page of JSON, a `Path`.
    This module never looks inside one: it passes it to the caller's own
    `describe`, and back to the caller's own `delete`.

    `listing` yields members and is walked once, lazily. `describe` reads one
    raw member into a `Member`. `delete` removes exactly one and returns when it
    is gone - it takes the raw member rather than the description, so a driver
    deletes the thing it listed rather than rebuilding it from an id.
    Splitting the three is what makes a collection something a caller supplies
    rather than something this module has to know.
    """

    name: str
    listing: Callable[[], Iterable[Raw]]
    describe: Callable[[Raw], Member]
    delete: Callable[[Raw], None]


@dataclass(frozen=True, slots=True)
class Pass:
    """What one pass saw, took, and left for the next one.

    `taken` is the ids in the order they went, and it is the same list on both
    sides of `dry_run` - named as the pass walks, so the list a dry run prints is
    the list a live pass removes, member for member. That list is the deliverable
    of a dry run, which is why a count would not do.
    """

    collection: str
    since: str | None
    until: str | None
    ceiling: int
    dry_run: bool
    seen: int
    selected: int
    taken: tuple[str, ...]
    bytes_freed: int
    stopped_because: StopReason
    resume_from: str | None

    @property
    def changed(self) -> bool:
        return bool(self.taken) and not self.dry_run

    @property
    def more_to_do(self) -> bool:
        """Whether running this again would take anything else."""
        return self.resume_from is not None


class PruneInterruptedError(Exception):
    """A delete failed part way. `so_far` says what had already gone.

    Raised rather than returned, because a delete that failed is a failure and
    swallowing it would report a clean pass over a collection this could not
    touch. Carried rather than bare, because the caller still has to know that
    members 1 to N are gone and which one to retry - an exception with no record
    would leave an operator unable to answer either.
    """

    def __init__(self, so_far: Pass) -> None:
        super().__init__(
            f"{so_far.collection}: a delete failed after {len(so_far.taken)} members. "
            f"Those are gone; the next pass resumes at {so_far.resume_from}"
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

    `noun` is what the caller's vocabulary is made of. A store and a GitHub
    collection are the same shape and not the same word, and an operator reading
    a refusal should see the word they typed a name of.
    """
    if name in allowed:
        return name
    if name in refused:
        raise ValueError(
            f"{name} is refused: {refused[name]}. This prunes {', '.join(allowed)}"
        )
    raise ValueError(
        f"a prune takes the name of a {noun}, not {name!r}. A path is never a "
        f"name here, because a deletion primitive that resolved its argument against "
        f"the file system is the one accident nobody can undo. This prunes "
        f"{', '.join(allowed)}"
        + (f"; {', '.join(refused)} are refused by name" if refused else "")
    )


def take[Raw](
    collection: Collection[Raw],
    *,
    window: Window,
    ceiling: int,
    dry_run: bool = True,
) -> Pass:
    """Delete up to `ceiling` members the window holds, one at a time, in listing order.

    This walks what it is given and does not sort, because sorting is holding
    the collection. A caller whose order matters yields in that order.

    The window is tested before the ceiling, which is what makes the resume
    point honest. Tested the other way round, a pass that had filled its ceiling
    would stop at the next member it saw and name it - and that member might be
    one the window never held, so the next pass would start from a member it has
    no business deleting.
    """
    if ceiling < 0:
        raise ValueError(f"a ceiling is a count of members, not {ceiling}")

    seen = 0
    selected = 0
    taken: list[str] = []
    freed = 0

    def stopped(because: StopReason, resume_from: str | None) -> Pass:
        """The record, built in one place so three exits cannot describe a pass differently."""
        return Pass(
            collection=collection.name,
            since=window.since,
            until=window.until,
            ceiling=ceiling,
            dry_run=dry_run,
            seen=seen,
            selected=selected,
            taken=tuple(taken),
            bytes_freed=freed,
            stopped_because=because,
            resume_from=resume_from,
        )

    for raw in collection.listing():
        seen += 1
        member = collection.describe(raw)
        if not window.holds(member.day):
            continue
        selected += 1

        if len(taken) >= ceiling:
            return stopped(StopReason.CEILING, member.id)

        if not dry_run:
            try:
                collection.delete(raw)
            except Exception as failure:
                raise PruneInterruptedError(stopped(StopReason.FAILED, member.id)) from failure
        taken.append(member.id)
        freed += member.size_bytes

    return stopped(StopReason.EXHAUSTED, None)


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
