"""What does one pass say to a person, and what does it write down?

Two readings of the same `one_at_a_time.Pass`, kept together because they have
to agree. `lines` is what an operator sees; `row` is the `CollectionPruneRow` a
caller may keep. Split between the core and the CLI, they would drift the day
somebody added a field to one and not the other.

**Both say where it stopped, and that is the sentence that matters.** A pass
that deleted 50 and a pass that cleared the backlog both print 50. Only the
resume point tells them apart, so it is on the first line rather than buried
under a list.
"""

from __future__ import annotations

from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.prune.one_at_a_time import Pass


def row(outcome: Pass, *, date: str) -> CollectionPruneRow:
    """The pass as the persisted shape, with today's date on it."""
    return CollectionPruneRow(
        version=CollectionPruneRow.schema_version(),
        date=date,
        collection=outcome.collection,
        since=outcome.since,
        until=outcome.until,
        max_deletes_per_run=outcome.ceiling,
        dry_run=outcome.dry_run,
        candidates_seen=outcome.seen,
        selected=outcome.selected,
        deleted=len(outcome.taken),
        bytes_freed=outcome.bytes_freed,
        stopped_because=outcome.stopped_because,
        resume_from=outcome.resume_from,
    )


def lines(outcome: Pass) -> list[str]:
    """What happened, as the lines a command prints, one member per line.

    The members themselves rather than a count: this is what a person reads
    before passing `--no-dry-run`, and a count says a deletion happened and
    nothing about what it took.
    """
    span = _span(outcome)
    verb = "would delete" if outcome.dry_run else "deleted"
    if not outcome.taken:
        nothing = f"{outcome.collection}: nothing {span}, out of {outcome.seen} members read"
        return [nothing, *_what_next(outcome)]

    head = (
        f"{outcome.collection}: {verb} {len(outcome.taken)} members {span}, "
        f"{outcome.bytes_freed} bytes, out of {outcome.seen} members read"
    )
    return [head, *(f"  {member}" for member in outcome.taken), *_what_next(outcome)]


def _span(outcome: Pass) -> str:
    """The window in the words an operator used to ask for it."""
    if outcome.since is not None and outcome.until is not None:
        return f"between {outcome.since} and {outcome.until}"
    if outcome.until is not None:
        return f"created on or before {outcome.until}"
    return f"created on or after {outcome.since}"


def _what_next(outcome: Pass) -> list[str]:
    """One line saying whether to run this again, and one saying how to make it real."""
    said: list[str] = []
    if outcome.stopped_because is StopReason.CEILING:
        said.append(
            f"  the ceiling of {outcome.ceiling} stopped this pass at {outcome.resume_from} - "
            "there is more, so run it again"
        )
    elif outcome.stopped_because is StopReason.FAILED:
        said.append(
            f"  a delete failed at {outcome.resume_from} - the members above are gone, "
            "and the next pass retries that one"
        )
    else:
        said.append("  the collection is exhausted: nothing else is inside the window")
    if outcome.dry_run and outcome.taken:
        said.append("  nothing was deleted - pass --no-dry-run to delete these")
    return said
