"""What does one pass say to a person, and what does it write down?

Two readings of the same `one_at_a_time.Pass`, kept together because they have
to agree. `finished` is the `TaskFinished` event an operator reads in the log;
`row` is the `CollectionPruneRow` the gardener lands in its record. Split
between the core and the runner, they would drift the day somebody added a
field to one and not the other.

**Both say why it stopped, and that is the word that matters.** A pass that
deleted 50 and a pass that cleared the backlog both took 50. Only why it
stopped tells them apart, so the event leads with how the task ended, in one
word (`classify`), before the list of what it took.

**The row names the run that wrote it, and the pass cannot.** A pass knows what
it walked; which run, attempt, job and shard it ran in, which task declared it,
how long it took, when the shard finished its work, what the shard's owned
folders weighed and what it downloaded are the runner's to say, so the runner
hands them in. The day a walk handled through is the pass's own, and the row
carries it for the task's next pass to start after.

**What happens next is one fixed sentence, and none says a member is gone.**
A dry run names the setting that makes a task live: `dry_run` in the task's own
declaration, because the gardener takes no flag for that. The same sentence ties
a compaction's old months and raw days to `month_deletes_dry_run`, because a
live compaction whose monthly window only reports ends `dry-run` too, and a page
says each word once. A pass that stopped for a fault says why, in the fault's
own sentence. No sentence carries a value: the event's fields carry those, so a
sentence can never disagree with them.

**Why a pass stopped, and what it recovered, are words on the row and
sentences here.** The row stores one closed word and one note a period or
member; the sentence a person reads is written in this module and is never
stored, so the wording can change with no migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.gardener_events import TaskFinished, TaskOutcome
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.contracts.knobs.gardener import PrunableCollection
from idhazh.gardener import event_log
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

#: What a person reads for each fault word, beside where the pass stopped.
WHY: Final[Mapping[GardenerFault, str]] = {
    GardenerFault.RAISED: "a code defect stopped it, and the log names the error",
    GardenerFault.MANUAL_ACTION: (
        "a known refusal needs a person's action before the next wake can continue"
    ),
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
    RecoveryNote.CARRIED_OVER: (
        "too many raw files for one pass, so the newest wait for the next wake"
    ),
    RecoveryNote.NOT_DELETABLE: "GitHub would not delete it, so the pass went on",
}

#: What happens next, for each way a task can end. A task a fault stopped is
#: told its fault's own sentence instead (`WHY`).
NEXT: Final[Mapping[TaskOutcome, str]] = {
    TaskOutcome.FAILED: "a code defect stopped it, and the next wake tries again",
    TaskOutcome.DEFERRED: "a cause outside the code stopped it, and the next wake resumes",
    TaskOutcome.DRY_RUN: (
        "nothing was changed: it only named the work it found. Set dry_run: false in "
        "config/gardener/<task>.json to let it do that work, except that a compaction keeps "
        "the old months and raw days it found until month_deletes_dry_run: false is set there "
        "too"
    ),
    TaskOutcome.CEILING: "it stopped at its ceiling, and the next wake goes on from there",
    TaskOutcome.DONE: (
        "it finished its work for this wake, and the next wake takes what reaches its line by "
        "then"
    ),
    TaskOutcome.EMPTY: "the ledger holds nothing to work on yet",
    TaskOutcome.NOT_DUE: "nothing has reached its line yet",
    TaskOutcome.OUTSIDE_RANGE: (
        "nothing that may be taken is inside the range named; widen it, or run the task "
        "without one"
    ),
}


def classify(outcome: Pass) -> TaskOutcome:
    """The one word for how a task ended: the first of the outcome words that holds.

    A fault first, then work only reported, then the ceiling, then work done.
    Work was found when the window held a member, or the pass wrote or would
    write a file; it was carried out when a live pass took, wrote or recovered
    something. A report the task files every pass is not work. Otherwise the
    pass's own idle word.
    """
    stopped = outcome.stopped_because
    if stopped is StopReason.FAILED:
        return TaskOutcome.FAILED
    if stopped is StopReason.DEFERRED:
        return TaskOutcome.DEFERRED
    found = outcome.selected > 0 or bool(outcome.written)
    carried = not outcome.dry_run and bool(outcome.taken or outcome.written or outcome.recovered)
    if found and not carried:
        return TaskOutcome.DRY_RUN
    if stopped is StopReason.CEILING:
        return TaskOutcome.CEILING
    if found:
        return TaskOutcome.DONE
    return outcome.idle_outcome


def next_step(word: TaskOutcome, fault: GardenerFault | None) -> str:
    """What happens next, for a person: the fault's own sentence when one stopped the task."""
    return NEXT[word] if fault is None else WHY[fault]


def finished(
    outcome: Pass,
    *,
    task: str,
    duration_ms: int,
    failure: BaseException | None,
    collection: PrunableCollection | None = None,
) -> TaskFinished:
    """The pass as the event that says how its task ended.

    `failure` is the exception that stopped the task, if one did: the event
    names its type and its place in this package's code, never its text.
    `collection` is the GitHub collection a collection task takes from, which
    says that `taken` holds its member ids rather than files.
    """
    word = classify(outcome)
    error, where = event_log.cause_of(failure)
    return TaskFinished(
        task=task,
        outcome=word,
        dry_run=outcome.dry_run,
        seen=outcome.seen,
        selected=outcome.selected,
        collection=collection,
        taken=list(outcome.taken),
        written=list(outcome.written),
        bytes_freed=outcome.bytes_freed,
        stopped_because=outcome.stopped_because,
        resume_from=outcome.resume_from,
        handled_through=outcome.handled_through,
        fault=outcome.fault,
        error=error,
        where=where,
        recovered=list(outcome.recovered),
        next=next_step(word, outcome.fault),
        pages_read=outcome.pages_read,
        duration_ms=duration_ms,
        periods=outcome.periods,
    )


def row(
    outcome: Pass,
    *,
    task: str,
    context: TaskContext,
    duration_ms: int,
    work_ended_at: str,
    cone_bytes: int | None,
    downloaded_bytes: int | None,
) -> CollectionPruneRow:
    """The pass as the persisted shape, under the name and identity of the run that took it."""
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
        stopped_because=outcome.stopped_because,
        fault=outcome.fault,
        recovered=list(outcome.recovered),
        resume_from=outcome.resume_from,
        handled_through=outcome.handled_through,
        duration_ms=duration_ms,
        work_ended_at=work_ended_at,
        cone_bytes=cone_bytes,
        downloaded_bytes=downloaded_bytes,
    )
