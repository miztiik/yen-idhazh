"""What one run of a date published, as that run and nobody else wrote it.

`state/digest-fragments/<YYYY>/<MM>/<DD>/<run_id>.json`, one file per run. The
name is the run's own id, so two runs of one date never reach for the same path
and there is nothing for git to merge - which is the whole reason this shape
exists. The published day is assembled from every fragment of its date.

**It is not published.** Everything under `frontend/public/` is copied verbatim
into the deploy, so a fragment filed there would be a second full copy of every
story on a site Pages refuses over 1 GB, crawlable and landable. What keeps a
reader off it is that it has no address at all.

A fragment records what its run did and never what the day now holds. It carries
no `partial` and no failure count for that reason: an article that failed at
02:20 and landed at 06:20 failed for this run and did not fail for the day, and
only something reading every fragment can tell the difference.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Timestamp,
)
from idhazh.contracts.digest_day import DigestEmbeddings, DigestItem
from idhazh.contracts.run_plan import VerticalPlan


class DigestRunFragment(Contract):
    """One run's block of a published day, before anything folds it in."""

    __schema_stem__: ClassVar[str] = "digest-run-fragment"
    #: What orders the blocks on the page, and the only order that keeps the
    #: never-reshuffle promise: a run's block lands where it landed. Both parts
    #: are required - two runs can finish in the same second, and the id is what
    #: separates them so the assembly is reproducible rather than arbitrary.
    __sort_key__: ClassVar[tuple[str, str]] = ("completed_at", "run_id")
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-22",
            change="First version.",
            why="A file with one writer needs no merge, and two runs of a day had one.",
        ),
    )

    date: DateStamp = Field(description="The published date this block belongs to.")
    run_id: RunId
    completed_at: Timestamp = Field(
        description="When the run finished writing this block. Half the sort key."
    )
    items: list[DigestItem] = Field(
        description=(
            "The stories this run published, in the order it published them. A story "
            "an earlier run already published is not here: the first block to carry a "
            "story keeps it."
        )
    )
    verticals: list[VerticalPlan] = Field(
        description=(
            "What this run planned per topic, kept so the day can say why a desk ran "
            "thin without the config that produced the plan."
        )
    )
    items_planned: int = Field(ge=0, description="How many stories this run set out to write.")
    failed_item_ids: list[ItemId] = Field(
        default_factory=list,
        description=(
            "Stories this run did not finish. A later run can still publish one, so "
            "this is a fact about the run and never about the day."
        ),
    )
    embeddings: DigestEmbeddings | None = Field(
        default=None, description="This run's vectors, for the duplicate pass over the whole day."
    )
