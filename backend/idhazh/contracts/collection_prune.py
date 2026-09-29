"""What one gardener task saw, took, and left for the next pass, in the run that ran it.

One row per task per wake, whatever the task walked - GitHub's workflow
artifacts, GitHub's workflow runs, or a ledger's day files under `state/`. The
gardener lands every row a shard produced in that shard's one record, a file
under the gardener's own ledger, so a run that deleted nothing still says so.

**`stopped_because` and `resume_from` are the fields this row exists for.**
`deleted` reads the same on a pass that cleared its backlog and on one that
could not get near it: 50 either way. `stopped_because` says which. An
exhausted pass has nothing left inside its window and no resume point; a pass
its ceiling stopped names the member the next pass begins at; a failed pass
names the member it failed at when it had reached one.

It is `VisualPruneRow.skipped_by_fuse` arrived at from the other side, and the
difference is the whole reason this shape is not that one. That field counts a
backlog, which means materialising every candidate before deleting the first.
A pass here walks a collection one page at a time and never holds it, so it
genuinely does not know how many it did not reach - and a count it cannot take
honestly is better replaced by the pointer it can.

**`deleted` and `bytes_freed` mean the same thing on a dry run as on a live
one**: what this pass took, or would have taken. `dry_run` is the cell that says
whether it happened. Reading them as zero on a dry run would make the preview
say nothing about the run it is previewing, which is the only job a preview has.
That is the rule `idhazh.telemetry.prune.Outcome` already holds, and the two
agree on purpose.

**The run that wrote the row is on the row.** The run, its attempt, the job and
the shard say which of a wake's records this is; `duration_ms` is this task's
own wall clock and `work_ended_at` is the instant its shard finished working and
started to publish, so a slow push is never read as a slow task. `cone_bytes`
is what the shard's owned folders weighed at the commit it checked out, the
same on every row of one record, so where the weight sits is read off the
record rather than measured again.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    ServerJob,
    Slug,
    Timestamp,
)

#: A member's id, as its own collection spells it. A GitHub artifact is a
#: decimal number and a day file is `state/<ledger>/<YYYY>/<MM>/<DD>.csv`, so the
#: class admits both and nothing that could be read as an instruction. It is
#: declared here rather than in `base.py` because no other shape holds one: a
#: pattern in `base.py` is a spelling several shapes share, and this is one
#: shape's own vocabulary.
MEMBER_ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"
MemberId = Annotated[str, StringConstraints(pattern=MEMBER_ID_PATTERN, max_length=512)]

#: The two jobs that run a task: the matrix job every wake runs, and the one job
#: that rewrites history. No other job runs a task, so no other job writes a row.
TASK_JOBS: Final = frozenset({ServerJob.RUN_TASKS, ServerJob.HISTORY})


class StopReason(StrEnum):
    """Why a pass stopped, which is what decides whether to run it again."""

    #: The listing ran out. Everything inside the window has been taken.
    EXHAUSTED = "exhausted"
    #: The ceiling was reached. There is more, and `resume_from` names it.
    CEILING = "ceiling"
    #: The pass raised - a delete, the listing, or the task itself. `resume_from`
    #: names the member it failed at when it had reached one, so the next pass
    #: retries it rather than stepping over it, and is empty when it failed
    #: before it could name any.
    FAILED = "failed"


class CollectionPruneRow(Contract):
    """One task, one wake, one row."""

    __schema_stem__: ClassVar[str] = "collection-prune-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-28",
            change="cone_bytes, additive: what the shard's owned folders weighed; None if unread.",
            why="A shard's checkout is bounded, and the record says what each one weighed.",
        ),
        ChangelogEntry(
            version="2026-09-27",
            change="collection is task; run identity, timing and a null ceiling added.",
            why="The gardener lands one row per task per wake in the record of its shard.",
        ),
        ChangelogEntry(
            version="2026-09-17",
            change="Initial shape: the collection, the window, the ceiling, where it stopped.",
            why="Deleting one member at a time needs a record of where the next pass starts.",
        ),
    )

    date: DateStamp = Field(description="The UTC day the pass ran.")
    task: Slug = Field(
        description=(
            "Which task this row is for: the name of its declaration, which is the "
            "file's stem under `config/gardener/`. A word, never a path."
        )
    )
    run_id: RunId = Field(description="The run this pass ran in.")
    attempt: int = Field(
        ge=1, description="Which attempt of that run. A re-run keeps its run and counts up."
    )
    job: ServerJob = Field(
        description=(
            "The job that ran the task: `run-tasks`, which every wake runs as a matrix, "
            "or `history`, the one job that rewrites history."
        )
    )
    shard: int = Field(
        ge=0,
        description=(
            "Which shard of that job. Two shards of one run each land a record of "
            "their own, so this is what tells them apart."
        ),
    )
    since: DateStamp | None = Field(
        default=None,
        description=(
            "The oldest day a member could be created on and still qualify. Empty when "
            "the window has no lower end, which is what an age-based window means: "
            "everything older than the line qualifies, however old."
        ),
    )
    until: DateStamp | None = Field(
        default=None,
        description=(
            "The newest day a member could be created on and still qualify, inclusive. "
            "Empty when the window has no upper end."
        ),
    )
    max_deletes_per_run: int | None = Field(
        ge=0,
        description=(
            "The ceiling in force. Empty is no ceiling at all. 0 is a survey: it "
            "reports the first member the window holds and takes nothing."
        ),
    )
    dry_run: bool = Field(
        description="True when this pass was only reporting. Nothing was deleted."
    )
    candidates_seen: int = Field(
        ge=0,
        description=(
            "Members the listing yielded before the pass stopped. Never the size of the "
            "collection: a pass that stops on its ceiling stops listing too."
        ),
    )
    selected: int = Field(
        ge=0, description="Of those, how many the window held. The rest were the wrong age."
    )
    deleted: int = Field(
        ge=0,
        description=(
            "How many this pass removed, or would have removed on a dry run. Never "
            "above the ceiling when the ceiling is above 0."
        ),
    )
    bytes_freed: int = Field(
        ge=0,
        description=(
            "What those deletes freed, or would free. 0 is honest for a collection "
            "whose members have no size we can read - a workflow run's logs are one."
        ),
    )
    stopped_because: StopReason = Field(description="Why the pass ended.")
    resume_from: MemberId | None = Field(
        default=None,
        description=(
            "The member the next pass begins at. Empty on an exhausted pass, which is "
            "the one reading that says the backlog is cleared, and empty on a failed "
            "pass that failed before it could name a member. `stopped_because` says "
            "which."
        ),
    )
    duration_ms: int = Field(
        ge=0,
        description=(
            "This task's own wall clock, in milliseconds. Not the shard's, and not the "
            "push: a shard runs several tasks and publishes once after all of them."
        ),
    )
    work_ended_at: Timestamp = Field(
        description=(
            "The UTC instant the shard finished its work and began to publish. Every "
            "row of one record carries the same instant."
        )
    )
    cone_bytes: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What the folders the shard's tasks own weighed at the commit it checked "
            "out, in bytes, read once a shard and written on every row of its record. "
            "The code every shard checks out is not counted. Empty when nobody read "
            "the commit: a task run by hand in a checkout reads none."
        ),
    )

    @model_validator(mode="after")
    def _the_arithmetic_holds(self) -> Self:
        """Seven cross-field rules, each one a way a hand-written row could lie."""
        if self.job not in TASK_JOBS:
            raise ValueError(
                f"job {self.job.value} runs no task. A row is written by "
                f"{' or '.join(sorted(job.value for job in TASK_JOBS))}"
            )
        if self.selected > self.candidates_seen:
            raise ValueError("the window cannot hold more members than the listing yielded")
        if self.deleted > self.selected:
            raise ValueError("a pass cannot delete a member the window did not hold")
        if self.max_deletes_per_run and self.deleted > self.max_deletes_per_run:
            raise ValueError("deleted must not exceed the ceiling that was in force")
        if self.stopped_because is StopReason.EXHAUSTED and self.resume_from is not None:
            raise ValueError("an exhausted pass has nothing left to resume from")
        if self.stopped_because is StopReason.CEILING and self.resume_from is None:
            raise ValueError("a pass its ceiling stopped names where the next one begins")
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("since is after until, so the window names no day")
        return self
