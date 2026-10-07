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
hands them in. The day a walk handled through is the pass's own, and the row
carries it for the task's next pass to start after.

**A task's fold is said beside its pass, on the same row.** It has a switch of
its own, so its lines say whether it was live, and a fold that stopped part way
turns the row's `stopped_because` to the stop its fault ends a pass with - the
task stopped, whichever half of it did.

**A dry run never says a member is gone.** One that found members says nothing
was deleted, and names the setting that makes the task live: `dry_run` in the
task's own declaration. The gardener takes no flag for that, so a line that
named one would send a person looking for a switch that does not exist. A dry
run that walks from a mark does not stop inside a day, so past its ceiling it
says where a live pass would stop, and that the rest of the day was counted.

**Why a pass stopped, and what it recovered, are words on the row and
sentences here.** The row stores one closed word and one note a period or
member; the sentence a person reads is rendered from them in this module and is
never stored, so the wording can change with no migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason, stop_for
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.gardener.closed_day_fold import Folded
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

#: What a person reads for each fault word, beside where the pass stopped.
WHY: Final[Mapping[GardenerFault, str]] = {
    GardenerFault.RAISED: "a code defect stopped it, and the log names the error",
    GardenerFault.API_UNAVAILABLE: "GitHub's API did not answer, so the next wake asks again",
    GardenerFault.RANGE_STARTS_LATE: (
        "the range named starts after a period that is ready before it; widen the range to "
        "include it"
    ),
    GardenerFault.NO_MONTH_TO_REOPEN: (
        "a raw day sits in a month no monthly entry names, so there is no month to re-open; "
        "its files wait for a person"
    ),
    GardenerFault.PACKED_FILE_UNREADABLE: (
        "a packed file it would settle a re-run or a late file into cannot be read or is not "
        "there; restore it from git history"
    ),
}

#: What a person reads for each recovery note, beside the period or member it names.
NOTED: Final[Mapping[RecoveryNote, str]] = {
    RecoveryNote.REPACKED_FROM_RAW: "packed again from its raw files, because no index named it",
    RecoveryNote.RECORDED_LOST: "recorded lost, because nothing was left to rebuild it from",
    RecoveryNote.REOPENED_MONTH: "re-opened to settle raw files that landed after it closed",
    RecoveryNote.INDEX_REBUILT: "its own packed file adopted, because no index named it",
    RecoveryNote.SET_ASIDE: "a file it could not read moved to the set-aside folder",
    RecoveryNote.CARRIED_OVER: "its newest raw files left for the next wake",
    RecoveryNote.NOT_DELETABLE: "GitHub would not delete it, so the pass went on",
}


def ended(outcome: Pass, folded: Folded | None) -> tuple[StopReason, GardenerFault | None]:
    """How a task ended, and why: its fold's stop when the fold stopped, else its pass's."""
    if folded is not None and folded.fault is not None:
        return stop_for(folded.fault), folded.fault
    return outcome.stopped_because, outcome.fault


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
    stopped, fault = ended(outcome, folded)
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
        fault=fault,
        recovered=list(outcome.recovered),
        resume_from=outcome.resume_from,
        handled_through=outcome.handled_through,
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
    if folded.fault is not None:
        said.append(
            f"  the fold stopped part way ({folded.fault.value}) - the months and days above are "
            "settled, and the next wake starts again from the oldest still waiting"
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
    """Why the pass stopped, what the next one does, what it recovered, and how to make it real."""
    said: list[str] = []
    if outcome.stopped_because is StopReason.CEILING:
        if outcome.dry_run and outcome.handled_through is not None:
            said.append(
                f"  the ceiling of {outcome.ceiling} would stop a live pass at "
                f"{outcome.resume_from}; the rest of that day was counted, not listed, and "
                f"the next pass starts after {outcome.handled_through}"
            )
        else:
            said.append(
                f"  the ceiling of {outcome.ceiling} stopped this pass at {outcome.resume_from} - "
                "there is more, so run it again"
            )
    elif outcome.stopped_because in (StopReason.FAILED, StopReason.DEFERRED):
        if outcome.resume_from is None:
            where = f"after {len(outcome.taken)} members, before it could name the next one"
            then = "the next pass starts again from the oldest member the window holds"
        else:
            where = f"at {outcome.resume_from}"
            then = "the next pass retries that one"
        how = "failed" if outcome.stopped_because is StopReason.FAILED else "was deferred"
        gone = "" if outcome.dry_run else "the members above are gone, and "
        said.append(f"  the pass {how} {where} - {gone}{then}")
        if outcome.fault is not None:
            said.append(f"  {outcome.fault.value}: {WHY[outcome.fault]}")
    else:
        said.append("  the collection is exhausted: nothing else is inside the window")
    said.extend(
        f"  {each.note.value} {each.subject}: {NOTED[each.note]}" for each in outcome.recovered
    )
    if outcome.dry_run and outcome.taken:
        said.append(
            "  nothing was deleted - a live run would delete the members above; set "
            "dry_run: false in config/gardener/<task>.json to make the task live"
        )
    return said
