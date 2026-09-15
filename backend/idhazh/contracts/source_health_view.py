"""The browser-safe source-health view: four facts about each address we ask.

`state/feed-health/`, `state/feed-retirements.csv` and `state/item-health/` are
the private record. They carry a feed's URL, an item's address, our own
diagnostic free text and the status a `robots.txt` answered with, and none of
those may reach a page. This is the narrow shape that does cross, written to
`frontend/public/source-health.json` once per run by
`idhazh.telemetry.publish.source_health`.

**The forbidden fields are absent by construction rather than by filtering.**
There is no field here that could hold a source URL, an item URL, a URL key, an
endpoint digest, a ledger `detail` cell or a robots body, so a writer cannot put
one in and a reviewer does not have to notice that it did not (Guardrail #11). A
projection spelled as a dict of names gains a cell by a one-word edit and
nothing refuses it; a projection spelled as a model fails at import.

**Four facts, and no column combines two of them.** Permission is what a site's
own `robots.txt` said. Availability is whether the address is answering now.
Retirement is the one permanent state, and only a server reporting `410 Gone` on
five distinct runs earns it. The publishing record is what the address yielded
over complete days. One number across the four was refused: they have different
units and different remedies, and a single score tells an operator that
something is wrong and nothing about what to do
(`docs/architecture/sources/health.md`).

**The reliability factor is carried beside those four and is not a fifth
judgement of the same kind.** The four say what the record holds; the factor
says what the run already did about it - the multiplier the ranker applied to
this feed's authority. It is copied from `ledger.feed_reliability` rather than
reduced again here, because a console figure that re-derives a ranking factor is
a second verdict on a question that already has one.

**This file is a projection and never control state.** Nothing in the pipeline
reads it back. Collect keeps deriving every decision from the private ledgers,
so deleting this file costs a console section and changes no run.

**It carries no reader-facing copy.** A state is named here and what a reader
loses while it holds is written on the page, beside the other console copy. A
sentence in a published payload is a string two surfaces would eventually
disagree about, and the console already owns every other word it prints.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    Slug,
    Timestamp,
)

#: The curated title of a source, from `config/sources.json`. A person wrote it
#: and every published item already carries it, so it crosses on terms nothing
#: about this view changes. Bounded because a page renders it in a table cell.
SourceTitle = Annotated[str, StringConstraints(min_length=1, max_length=120)]

#: The one line at the top of the page, computed where the figures are. Bounded
#: at one sentence a person reads without scrolling, and `min_length=1` because
#: an empty headline is a heading that says nothing while looking like it said
#: something - the failure this field exists to make impossible.
HeadlineSentence = Annotated[str, StringConstraints(min_length=1, max_length=200)]

#: Every private cell this view exists to leave behind. Checked at import
#: against the fields below, so a later widening that reaches for one of them
#: fails where it is written rather than in the published tree.
FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "url",
        "canonical_url",
        "feed_url",
        "url_key",
        "endpoint_key",
        "detail",
        "robots_status",
        "robots_body",
        "item_id",
    }
)


class SourcePermission(StrEnum):
    """What the site's own `robots.txt` said about this address.

    Four members where the ledger's `RobotsOutcome` has three, and the fourth is
    the one that matters: a row written before the column existed carries an
    empty cell, and that is not the same fact as `allowed`. Reading absence as a
    refusal would take every desk under its feed floor on the day the column
    landed; reading it as permission would claim a check nobody ran.
    """

    ALLOWED = "allowed"
    DENIED = "denied"
    #: We could not establish permission - a 429, a 5xx, or a transport failure.
    #: Unknown fails closed, so the address is not asked.
    UNREACHABLE = "unreachable"
    #: No run has recorded an answer for this address at all.
    UNRECORDED = "unrecorded"


class SourceAvailability(StrEnum):
    """Whether the address is answering now, by the rule the run rests on.

    Derived from `discover.streak` and `discover.resting` over the settled
    ledger, which is the same loop the quarantine uses. Two reducers would be
    two answers, and a page that disagrees with the run that produced it is
    worse than a page with no answer.
    """

    #: The newest read carried entries.
    ANSWERING = "answering"
    #: Struck at least once since the last read that carried entries, and not
    #: yet resting.
    FAILING = "failing"
    #: The run is holding this feed back. It lifts itself.
    RESTING = "resting"
    #: No run has asked this address. A record of nothing but rests is a rest.
    NEVER_ASKED = "never_asked"


class SourceHealthRow(Model):
    """One configured address, as a page is allowed to read it.

    A nested shape rather than a contract of its own: nothing writes a row on
    its own and nothing reads one out of context, so it travels inside the view
    and is inlined under that schema's `$defs`.
    """

    source_id: Slug
    title: SourceTitle
    vertical: Slug
    permission: SourcePermission
    availability: SourceAvailability
    # There is deliberately no failure count here. The console already draws
    # failures in a row beside a rest threshold, over the same evidence, and a
    # second copy of that number on the same page is a number two panels can
    # disagree about. Availability is the fact this view owns.
    retired: bool = Field(
        description=(
            "Has a run stopped asking this address for good? True only when the "
            "retirement ledger holds its endpoint. The console renders this decision "
            "and never re-derives it."
        )
    )
    retired_on: DateStamp | None = Field(
        default=None,
        description="The day the retirement was filed. Absent unless `retired`.",
    )
    opportunities: int = Field(
        ge=0,
        description=(
            "Distinct addresses this source had planned on a complete date, inside the "
            "window. One address on one date counts once however many runs of that "
            "date attempted it."
        ),
    )
    publications: int = Field(
        ge=0,
        description=(
            "Those addresses that reached publish on any attempt of their date. Never "
            "more than `opportunities`, which is enforced rather than assumed."
        ),
    )
    source_failures: int = Field(
        ge=0,
        description=(
            "Opportunities lost to a failure this source owns - a refusal, a bad "
            "status, no text, a paywall. Reported beside the ratio and never "
            "subtracted from it, so one lost article is counted once."
        ),
    )
    reliability: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The multiplier the ranker applied to this feed's authority on this run, "
            "from `ledger.feed_reliability` over the trailing "
            "`collect.reliability_window_days`. Published rather than recomputed by a "
            "page: a console figure that is a second derivation of a ranking factor is "
            "two verdicts, and the day they disagree neither is trustworthy."
        ),
    )
    reliability_reads: int = Field(
        ge=0,
        description=(
            "Evidence-bearing reads the factor was reduced over - every read that did "
            "not preserve the streak, so a rest and a robots answer are set aside. "
            "Zero means the factor is the 1.0 a feed with no evidence scores and not a "
            "record of perfect answering, which is the difference a page draws as a "
            "dash rather than a full bar."
        ),
    )

    @model_validator(mode="after")
    def _the_record_is_arithmetically_possible(self) -> Self:
        """No yield numerator exceeds its opportunity count.

        A ratio over a denominator it can beat is a page printing 110 percent,
        and the shape can refuse it here rather than a reviewer noticing it
        later. `source_failures` is bounded the same way and for the same
        reason: it counts opportunities, not rows.
        """
        if self.publications > self.opportunities:
            raise ValueError("publications cannot exceed opportunities")
        if self.source_failures > self.opportunities:
            raise ValueError("source_failures cannot exceed opportunities")
        return self

    @property
    def decisions(self) -> int:
        """Addresses whose fate this source decided: it published or it lost them.

        The honest denominator for a yield, and not `opportunities`. A model
        that would not answer, a rate limit and a robots refusal all cost an
        opportunity and none of them is the publisher's doing, so dividing by
        the wider number charges a source for our outage. Measured 2026-09-06
        over the committed view: `aljazeera-economy` is 78 of 115 offered and 78
        of 79 decided - 68 percent against 99 percent, from the same two rows.

        Derived rather than stored, so this file cannot disagree with itself and
        the payload gains no field (CLAUDE.md section 11).
        """
        return self.publications + self.source_failures

    @property
    def source_yield(self) -> float | None:
        """The share of its own decisions this source turned into a story.

        `None` when it decided nothing, because 0 of 0 is not zero - it is a
        source nobody has asked yet, and a page that prints 0 percent for it is
        making an accusation the record cannot support.
        """
        decided = self.decisions
        return self.publications / decided if decided else None

    @model_validator(mode="after")
    def _a_retirement_names_its_day(self) -> Self:
        """A day exactly when there is a retirement, so neither can be read alone."""
        if self.retired != (self.retired_on is not None):
            raise ValueError("retired_on is present exactly when retired is true")
        return self


class SourceHealthView(Contract):
    """Every address the run may ask, and what the committed record says about it."""

    __schema_stem__: ClassVar[str] = "source-health-view"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13",
            change="Each row gains reliability and reliability_reads, and the view gains a window.",
            why="The ranker discounts a feed's authority by a factor no view could show.",
        ),
        ChangelogEntry(
            version="2026-09-03T09:00",
            change="Initial shape: the run that wrote it and the window it read.",
            why="Permission, availability, retirement and yield were derived in four places.",
        ),
    )

    generated_at: Timestamp
    run_id: RunId
    headline_sentence: HeadlineSentence = Field(
        description=(
            "The one line the page opens with: the worst figure on it against that "
            "figure's own bound, or a count of the figures the record cannot compute "
            "yet, or a sentence saying nothing here is outside its bound. Computed "
            "here rather than in the page, so the sentence and the table below it "
            "are reduced from the same rows. Never absent and never empty - a page "
            "whose summary line can vanish teaches an operator to scroll past it."
        )
    )
    reliability_floor: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "`collect.reliability_floor` - the furthest down the ranker will discount "
            "a feed, and the mark a page puts on the bar it draws each factor in. "
            "Carried because the bound and the figure must come from one run: a page "
            "holding a published factor to a floor it read somewhere else is drawing "
            "two runs on one bar."
        ),
    )
    reliability_window_days: int = Field(
        gt=0,
        description=(
            "`collect.reliability_window_days` - how far back the factor was reduced. "
            "Published so the page can say what the number covers; a bare share with "
            "no period is not a measurement."
        ),
    )
    min_complete_days: int = Field(
        gt=0,
        description=(
            "`collect.source_yield_min_complete_days`. It is both how far back the "
            "publishing record reads and how much of that record is enough to read as "
            "a rate, because there is one question here - how many complete days does "
            "a yield judgement need - and a second number would be a second answer to "
            "it."
        ),
    )
    complete_dates: int = Field(
        ge=0,
        description=(
            "Complete UTC dates the census actually covered, capped at "
            "`min_complete_days`. Today is never one of them: a run is still going, so "
            "its date has opportunities nobody has attempted yet."
        ),
    )
    yield_readable: bool = Field(
        description=(
            "Is the record deep enough to read as a rate? Carried rather than left to "
            "the page, so the page and this file cannot answer it differently."
        )
    )
    first_date: DateStamp | None = Field(
        default=None,
        description="Oldest complete date in the census. Absent when there is none.",
    )
    last_date: DateStamp | None = Field(
        default=None,
        description="Newest complete date in the census. Absent when there is none.",
    )
    sources: list[SourceHealthRow] = Field(
        description=(
            "One row per address a curator left active, ordered by source id. Every "
            "row carries exactly one permission state, so the states sum to the number "
            "of addresses by construction rather than by a page adding them up."
        )
    )

    @model_validator(mode="after")
    def _the_window_agrees_with_itself(self) -> Self:
        """Three cells describe one window, so they are checked against each other."""
        if self.yield_readable != (self.complete_dates >= self.min_complete_days):
            raise ValueError("yield_readable must equal complete_dates >= min_complete_days")
        if self.complete_dates > self.min_complete_days:
            raise ValueError("the census reads at most min_complete_days complete dates")
        if (self.first_date is None) != (self.complete_dates == 0):
            raise ValueError("first_date is present exactly when the census covered a date")
        if (self.last_date is None) != (self.complete_dates == 0):
            raise ValueError("last_date is present exactly when the census covered a date")
        if self.first_date is not None and self.last_date is not None:
            if self.first_date > self.last_date:
                raise ValueError("first_date cannot be after last_date")
        return self

    @model_validator(mode="after")
    def _one_row_per_address(self) -> Self:
        """A repeated source would double one permission state and break the tally."""
        ids = [row.source_id for row in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("sources must name each source once")
        if ids != sorted(ids):
            raise ValueError("sources must be ordered by source id")
        return self

    @model_validator(mode="after")
    def _every_factor_is_inside_the_floor_it_ships_with(self) -> Self:
        """A drawn factor sits between the floor and 1.0, and a bare 1.0 says so.

        `ledger.feed_reliability` clamps into `[floor, 1.0]` and returns exactly
        1.0 when it found no evidence, so both properties hold at the writer.
        Checking them here is what stops a later producer from publishing a
        factor the bar cannot draw - a value under the mark, or a full bar over
        an empty denominator that reads as a perfect record.
        """
        for row in self.sources:
            if row.reliability < self.reliability_floor:
                raise ValueError(
                    f"{row.source_id} carries a factor under reliability_floor"
                )
            if row.reliability_reads == 0 and row.reliability != 1.0:
                raise ValueError(
                    f"{row.source_id} scored no evidence, so its factor must be 1.0"
                )
        return self


for _model in (SourceHealthRow, SourceHealthView):
    _leaked = FORBIDDEN_FIELDS & set(_model.model_fields)
    if _leaked:
        raise AssertionError(
            f"{_model.__name__} carries a private field a page may never receive: "
            f"{sorted(_leaked)}"
        )
