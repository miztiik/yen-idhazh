"""Every visual decision one day made, listed so a person can look at them.

The question this surface exists to answer is the one nothing has asked yet:
**is the visual the machine kept the visual a human would have kept?** It gates
nothing. No publish decision reads it, and no later row may make one read it
(`CLAUDE.md` section 0a).

**Never committed, and never under `frontend/public/`.** The tree is written to
`backend/var/review/<date>/`, which `.gitignore` already covers, and reaches a
person as a workflow artifact with a finite life. A review surface that quietly
became a published one is the failure this whole shape is arranged against, so
the writer refuses an output directory inside the published tree rather than
trusting a path scan to notice afterwards.

**Why a contract at all**, when the file is gitignored and a re-run rebuilds it:
it crosses a process boundary and usually a machine boundary, which is what makes
a shape a payload rather than a local variable (section 1a). It is written on a
runner and read on a reviewer's laptop after a zip, which is the same test
`EvidenceItem` already answered the same way. The reviewing tools rows 2 and 3
add have to be able to refuse a queue they cannot trust, and refusing needs a
shape to check against.

**It is a contract under Guardrail #3 and not a migration surface under section 11.**
Nothing this payload was ever written into survives: the oldest copy that can
exist is a workflow artifact a week old, and a re-run rebuilds it. So a shape
change here owes a re-run, never a read-side migration.

**Three populations, because three have a producer.** A fourth - a second
configuration's render of the same day, the config-B arm - is named by the plan
that asked for this surface and nothing in this build can produce one. A member
for it would be a word nobody can write, nobody can retire and nobody can tell
from a bug, which is the rule `NoneReason` already states for the same reason.
It arrives with the row that builds the second arm.

Every text field here is untrusted (Guardrail #11). It came off the open web or out
of a model, it is bounded by `UntrustedLine`, and the renderer escapes it on the
way into HTML. None of it ever becomes a path, a prompt or a URL to fetch.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    RelPath,
    Timestamp,
    Url,
    UrlKey,
)
from idhazh.contracts.visual_decision import NoneReason, VisualState


class ReviewPopulation(StrEnum):
    """Which of the three outcomes an item landed in.

    The split is read off the decision and never off the published day: the day
    payload carries `visual: null` for every item that got no picture, so from
    it alone a chart the validator refused and a story nobody drafted one for
    are the same absence. Telling those two apart is most of the point.
    """

    #: A chart was drawn and the day publishes it.
    PUBLISHED = "published"
    #: A chart was drafted and the item carries none anyway - the validator
    #: refused the plan, or the render failed after it passed.
    REJECTED = "rejected"
    #: No chart was ever drafted. `none_reason` says which gate decided it, and
    #: this is the majority outcome by design.
    NONE = "none"


class ReviewRow(Model):
    """One item as a reviewer meets it."""

    item_id: ItemId
    url_key: UrlKey
    population: ReviewPopulation
    title: UntrustedLine | None = None
    source_url: Url
    visual_state: VisualState
    none_reason: NoneReason | None = Field(
        default=None,
        description=(
            "Which gate decided this item carries no picture. Null on a published row, "
            "and null on a decision written before the field existed."
        ),
    )
    rationale: UntrustedLine | None = None
    alt_text: UntrustedLine | None = None
    asset_relpath: RelPath | None = Field(
        default=None,
        description=(
            "Where this row's drawing sits inside the review tree, relative to this "
            "file. A copy, so the tree is readable with the repository absent. Null "
            "on every row that carries no drawing."
        ),
    )

    @model_validator(mode="after")
    def _a_drawing_and_a_population_cannot_disagree(self) -> Self:
        if (self.population is ReviewPopulation.PUBLISHED) != (
            self.visual_state is VisualState.RENDERED
        ):
            raise ValueError("a published row is the rendered one, and only it")
        if self.asset_relpath is not None and self.population is not ReviewPopulation.PUBLISHED:
            raise ValueError("only a published row carries a drawing")
        if self.none_reason is not None and self.population is ReviewPopulation.PUBLISHED:
            raise ValueError("only an item with no picture records the gate that refused it")
        return self


class ReviewCensus(Model):
    """How big a population was, beside how much of it this queue carries.

    Both numbers, never one. The budget below caps each population in
    proportion rather than truncating one of them, and a kept count on its own
    reads identically on a day that fitted and a day that was cut - so only the
    pair says which happened.
    """

    population: ReviewPopulation
    seen: int = Field(ge=0, description="Decisions this population held, before any cap.")
    kept: int = Field(ge=0, description="Rows this queue carries for it.")

    @model_validator(mode="after")
    def _a_queue_cannot_hold_more_than_it_saw(self) -> Self:
        if self.kept > self.seen:
            raise ValueError("kept cannot exceed seen")
        return self


class ReviewQueue(Contract):
    """One day's review tree, as a machine reads it."""

    __schema_stem__: ClassVar[str] = "review-queue"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Initial shape: the three populations that have a producer, one row an "
                "item, and a census carrying each population's true size beside the "
                "number of rows kept."
            ),
            why=(
                "Contracts before logic - the review tree's renderer and the reviewing "
                "tools that read it back are written against a fixed payload (Guardrail #3). "
                "The file is gitignored and rebuilt by a re-run, and it is a contract for "
                "the reason EvidenceItem is one: it is written on a runner and read on a "
                "reviewer's machine, so the reader has to be able to refuse a queue it "
                "cannot trust."
            ),
        ),
    )

    date: DateStamp
    built_at: Timestamp
    budget_bytes: int = Field(
        gt=0,
        description=(
            "What the tree was allowed to weigh. The writer caps each population in "
            "proportion rather than failing, because the job that builds this one also "
            "publishes the day."
        ),
    )
    bytes_written: int = Field(
        ge=0,
        description=(
            "What the sheet and its drawings weigh. This file is not counted, because a "
            "number inside a document cannot include its own length - writing it twice to "
            "make it fit would only produce a figure that is wrong by the difference."
        ),
    )
    census: list[ReviewCensus]
    rows: list[ReviewRow]

    @model_validator(mode="after")
    def _the_census_covers_every_population_once(self) -> Self:
        named = [entry.population for entry in self.census]
        if len(named) != len(set(named)):
            raise ValueError("a population is counted once")
        if set(named) != set(ReviewPopulation):
            raise ValueError("the census names every population, including an empty one")
        kept = dict.fromkeys(ReviewPopulation, 0)
        for row in self.rows:
            kept[row.population] += 1
        for entry in self.census:
            if entry.kept != kept[entry.population]:
                raise ValueError(
                    f"census says {entry.kept} {entry.population} rows and the queue holds "
                    f"{kept[entry.population]}"
                )
        return self
