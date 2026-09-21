"""How did one unit of council work end?

Three ways, and a free-text cell would split silently on a typo - `completed`
and `Completed` are two outcomes to a group-by and one outcome to a reader. The
council files the value the hosted work hands back and never infers it, so the
vocabulary is declared here rather than inside whatever decides which member
applies.

It names no judge and needs none. A repository with no judge in it still
imports, instantiates and compares every member.
"""

from __future__ import annotations

from enum import StrEnum


class ShardOutcome(StrEnum):
    """The three ways one unit of hosted work ends."""

    #: The unit reached the end of the work it owned.
    COMPLETED = "completed"

    #: The unit stopped itself before its deadline with work still owned.
    STOPPED_ON_DEADLINE = "stopped_on_deadline"

    #: The unit was given nothing to do. A settle that had nothing to count is
    #: this, the same as any other empty unit.
    NOTHING_TO_DO = "nothing_to_do"
