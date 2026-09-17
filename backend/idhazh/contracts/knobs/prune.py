"""Which collections may a prune pass take from, how old is old enough, and how many go at once?

A prune pass deletes members of a collection one at a time under a ceiling
(`idhazh.prune.one_at_a_time`). This block is what an operator sets to decide
which collections it may point at and where each one's line falls.

**Every default reports and deletes nothing**, because `dry_run` is true. That
is the same promise `RetentionConfig` makes and for the same reason: a fresh
clone that starts deleting on its first run is a clone nobody can try out. A
collection still names an age here, so the first evidence of what the window
selects arrives before any deletion rather than after it.

**The collections are held by GitHub, not by this repository.** Nothing under
`state/` or `frontend/public/` is named here - those are day files and rendered
visuals, and `idhazh telemetry prune` and `retention` already own them. What is
named here is the workflow artifacts and workflow runs the Actions platform
keeps on our behalf, which no file in this repository represents and which
therefore no other retention rule can reach.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import Field

from idhazh.contracts.base import Model


class PrunableCollection(StrEnum):
    """Every collection a pass may take from, and the word an operator types.

    A closed vocabulary, so a word outside it is refused with the whole list
    rather than resolved against anything. The same rule `idhazh telemetry
    prune` holds for its stores: a deletion command whose destination is an
    arbitrary string is a deletion primitive pointed at whatever the caller
    happened to pass (Guardrail #11).
    """

    #: The files a job uploaded with `actions/upload-artifact`. Each one has its
    #: own bytes and its own id, and deleting one cannot damage another.
    WORKFLOW_ARTIFACTS = "workflow-artifacts"
    #: A whole workflow run and the logs it holds. Deleting one removes the run
    #: from the Actions history, so its age wants to outlive any question
    #: somebody still asks of a failure.
    WORKFLOW_RUNS = "workflow-runs"


#: How many members one pass takes when a collection names no ceiling of its
#: own. An estimate and not a measurement (Guardrail #10): each delete is one
#: REST call, and GitHub publishes no number for how many deletes a minute it
#: will accept before it applies a secondary rate limit. Fifty is chosen to sit
#: far under any plausible burst limit and to finish inside a step nobody is
#: waiting on. What would settle it is a run that deletes in a loop until the
#: API answers 403 with a `Retry-After` header, and reads the count off that.
DEFAULT_CEILING: Final = 50


class CollectionPolicy(Model):
    """One collection's line: how old a member must be, and how many go in a pass."""

    retain_days: int = Field(
        ge=1,
        description=(
            "How many days a member is kept before a pass may take it. Whole days and "
            "never zero: a window that includes today would delete the artifact the "
            "running job just uploaded."
        ),
    )
    max_deletes_per_run: int = Field(
        default=DEFAULT_CEILING,
        ge=0,
        description=(
            "The ceiling. One pass deletes at most this many and then stops cleanly, "
            "naming where the next pass resumes. 0 surveys: it reports the first "
            "member the window holds and deletes nothing, which is how an operator "
            "sees what a window selects without committing to a number."
        ),
    )


def default_collections() -> dict[PrunableCollection, CollectionPolicy]:
    """Both collections, with a line drawn for each, taking nothing until dry_run is off.

    The two ages differ because the two questions differ. An artifact is bytes a
    job wrote for the next job, and once the run that produced it is read there
    is nothing left to ask of it. A run is the record that the work happened,
    and somebody reading a regression three months later still wants it.
    """
    return {
        PrunableCollection.WORKFLOW_ARTIFACTS: CollectionPolicy(retain_days=30),
        PrunableCollection.WORKFLOW_RUNS: CollectionPolicy(retain_days=90),
    }


class PruneConfig(Model):
    """The collections a pass may take from, and whether it may take anything at all."""

    dry_run: bool = Field(
        default=True,
        description=(
            "Report what a live pass would delete and delete nothing. True by default, "
            "so a fresh clone removes nothing it was not asked twice for. The CLI's "
            "--no-dry-run is the second word."
        ),
    )
    collections: dict[PrunableCollection, CollectionPolicy] = Field(
        default_factory=default_collections,
        description=(
            "One policy per collection this may be pointed at. A collection absent "
            "from this map is refused by name: the vocabulary says the word exists and "
            "the map says whether this repository has drawn a line for it."
        ),
    )
