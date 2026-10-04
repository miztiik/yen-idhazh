"""What does one pass say to a person, and what does it write down?

Two readings of the same `one_at_a_time.Pass`, kept together because they have
to agree. `lines` is what an operator sees; `row` is the `CollectionPruneRow`
the gardener lands in its record. Split between the core and the CLI, they
would drift the day somebody added a field to one and not the other.

**Both say where it stopped, and that is the sentence that matters.** A pass
that deleted 50 and a pass that cleared the backlog both print 50. Only why it
stopped tells them apart, so it is on the first line rather than buried under a
list.

**The row names the run that wrote it, and the pass cannot.** A pass knows what
it walked; which run, attempt, job and shard it ran in, which task declared it,
how long it took, when the shard finished its work, what the shard's owned
folders weighed and what it downloaded are the runner's to say, so the runner
hands them in.

**A task's fold is said beside its pass, on the same row.** It has a switch of
its own, so its lines say whether it was live, and a fold that stopped part way
turns the row's `stopped_because` to `failed` - the task failed, whichever half
of it did.

**A dry run never says a member is gone.** One that found members says nothing
was deleted, and names the setting that makes the task live: `dry_run` in the
task's own declaration. The gardener takes no flag for that, so a line that
named one would send a person looking for a switch that does not exist.
"""

from __future__ import annotations

from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.gardener.closed_day_fold import Folded
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass


def row(
    outcome: Pass,
    *,
    task: str,
    context: TaskContext,
    duration_ms: int,
    work_ended_at: str,
    cone_bytes: int | None,
    downloaded_bytes: int | None,
    folded: Folded | None = None,
) -> CollectionPruneRow:
    """The pass as the persisted shape, under the name and identity of the run that took it."""
    stopped = (
        StopReason.FAILED if folded is not None and folded.failed else outcome.stopped_because
    )
    return CollectionPruneRow(
        version=CollectionPruneRow.schema_version(),
        date=context.today.isoformat(),
        task=task,
        run_id=context.run_id,
        attempt=context.attempt,
        job=context.job,
        shard=context.shard,
        since=outcome.since,
        until=outcome.until,
        max_deletes_per_run=outcome.ceiling,
        dry_run=outcome.dry_run,
        candidates_seen=outcome.seen,
        selected=outcome.selected,
        deleted=len(outcome.taken),
        bytes_freed=outcome.bytes_freed,
        stopped_because=stopped,
        resume_from=outcome.resume_from,
        duration_ms=duration_ms,
        work_ended_at=work_ended_at,
        cone_bytes=cone_bytes,
        downloaded_bytes=downloaded_bytes,
        fold_dry_run=None if folded is None else folded.dry_run,
        folded_days=None if folded is None else len(folded.days),
        folded_files=None if folded is None else folded.files,
        folded_months=None if folded is None else len(folded.months),
    )


def fold_lines(task: str, folded: Folded) -> list[str]:
    """What a task's fold did, one settled month or day folder per line, and whether it was live."""
    verb = "would settle" if folded.dry_run else "settled"
    head = (
        f"{task} fold: {verb} {len(folded.months)} closed months and {len(folded.days)} closed "
        f"days, replacing {folded.files} files with one settled.csv each"
    )
    months = [
        f"  {month.tree.value} {month.month}: {len(month.replaced)} files"
        for month in folded.months
    ]
    days = [f"  {day.tree.value} {day.day}: {len(day.replaced)} files" for day in folded.days]
    said = [head, *months, *days]
    if folded.failed:
        said.append(
            "  the fold stopped part way - the months and days above are settled, and the "
            "next wake starts again from the oldest still waiting"
        )
    elif folded.dry_run and (folded.months or folded.days):
        said.append("  nothing was written - set the fold's dry_run to false to settle these")
    return said


def lines(outcome: Pass) -> list[str]:
    """What happened, as the lines a command prints, one member per line.

    The members themselves rather than a count: this is what a person reads
    before setting a task's `dry_run` to false, and a count says a deletion
    happened and nothing about what it took.
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
    """Why the pass stopped and what the next one does, and on a dry run how to make it real."""
    said: list[str] = []
    if outcome.stopped_because is StopReason.CEILING:
        said.append(
            f"  the ceiling of {outcome.ceiling} stopped this pass at {outcome.resume_from} - "
            "there is more, so run it again"
        )
    elif outcome.stopped_because is StopReason.FAILED:
        if outcome.resume_from is None:
            where = f"after {len(outcome.taken)} members, before it could name the next one"
            then = "the next pass starts again from the oldest member the window holds"
        else:
            where = f"at {outcome.resume_from}"
            then = "the next pass retries that one"
        gone = "" if outcome.dry_run else "the members above are gone, and "
        said.append(f"  the pass failed {where} - {gone}{then}")
    else:
        said.append("  the collection is exhausted: nothing else is inside the window")
    if outcome.dry_run and outcome.taken:
        said.append(
            "  nothing was deleted - a live run would delete the members above; set "
            "dry_run: false in config/gardener/<task>.json to make the task live"
        )
    return said
