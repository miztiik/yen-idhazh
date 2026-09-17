"""What one prune pass over one collection saw, took, and left for the next pass.

One row per invocation of `idhazh.prune.one_at_a_time.take`, whatever the
collection was - GitHub's workflow artifacts, GitHub's workflow runs, or a
store's day files under `state/`. It is written where the caller asks for it
and nowhere by default, so this shape adds no ledger and no growing read
(Guardrail #12).

**`resume_from` is the field this row exists for.** `deleted` reads the same on
a pass that cleared its backlog and on one that could not get near it: 50 either
way. Only `resume_from` says which. Empty means the collection is exhausted and
there is nothing left inside the window; a member id means there is more and
names where the next pass begins.

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
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Slug,
)

#: A member's id, as its own collection spells it. A GitHub artifact is a
#: decimal number and a day file is `state/<store>/<YYYY>/<MM>/<DD>.csv`, so the
#: class admits both and nothing that could be read as an instruction. It is
#: declared here rather than in `base.py` because no other shape holds one: a
#: pattern in `base.py` is a spelling several shapes share, and this is one
#: shape's own vocabulary.
MEMBER_ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._/-]*$"
MemberId = Annotated[str, StringConstraints(pattern=MEMBER_ID_PATTERN, max_length=512)]


class StopReason(StrEnum):
    """Why a pass stopped, which is what decides whether to run it again."""

    #: The listing ran out. Everything inside the window has been taken.
    EXHAUSTED = "exhausted"
    #: The ceiling was reached. There is more, and `resume_from` names it.
    CEILING = "ceiling"
    #: A delete raised. `resume_from` names the member that failed, so the next
    #: pass retries it rather than stepping over it.
    FAILED = "failed"


class CollectionPruneRow(Contract):
    """One pass, one row."""

    __schema_stem__: ClassVar[str] = "collection-prune-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-17",
            change="Initial shape: the collection, the window, the ceiling, where it stopped.",
            why="Deleting one member at a time needs a record of where the next pass starts.",
        ),
    )

    date: DateStamp = Field(description="The day the pass ran.")
    collection: Slug = Field(
        description=(
            "Which collection this pass walked. A word from a closed vocabulary - "
            "`prune.PrunableCollection` for what GitHub holds, a store name for what "
            "`state/` holds - and never a path."
        )
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
    max_deletes_per_run: int = Field(
        ge=0,
        description=(
            "The ceiling in force. 0 is a survey: it reports the first member the "
            "window holds and takes nothing."
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
            "The member the next pass begins at. Empty when the collection is "
            "exhausted, which is the one cell that says the backlog is cleared."
        ),
    )

    @model_validator(mode="after")
    def _the_arithmetic_holds(self) -> Self:
        """Five cross-field rules, each one a way a hand-written row could lie."""
        if self.selected > self.candidates_seen:
            raise ValueError("the window cannot hold more members than the listing yielded")
        if self.deleted > self.selected:
            raise ValueError("a pass cannot delete a member the window did not hold")
        if self.max_deletes_per_run and self.deleted > self.max_deletes_per_run:
            raise ValueError("deleted must not exceed the ceiling that was in force")
        if (self.stopped_because is StopReason.EXHAUSTED) != (self.resume_from is None):
            raise ValueError(
                "an exhausted pass has nothing to resume from, and any other pass names "
                "where the next one begins"
            )
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("since is after until, so the window names no day")
        return self
