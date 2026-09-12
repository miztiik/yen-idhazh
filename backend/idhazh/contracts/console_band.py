"""The band, the strip and the months list, derived once and fetched first.

`console-shell.ts` derives all of this at build time from six committed ledgers
and inlines the result into all three console documents. This is the shape that
replaces that: one small payload at `frontend/public/console/band.json`, fetched
before anything else, so the console can say "did it work, what is worst, how
much room is left" without opening a single month file.

**The months list rides along and that is the point.** A shell cannot ask for a
month until it knows which months exist, so a band that left the list out would
make the list a second serial hop and the first month a third (row 10, decision
1). It is here because it is the cheapest place a fetch can learn it.

**Sentences, not raw ledgers.** Every string on this shape is one the pipeline
wrote about its own work - a verdict, a route's worst state, a size. None of it
is fetched text and none of it is an address, so there is no cell an article
could arrive in (Guardrail #11). What crosses is what the band prints; the ledgers
behind it stay under `state/`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, MonthStamp, Timestamp

#: Nothing is forbidden, for the same structural reason `public_run_day.py`
#: gives: this shape is not a projection of a ledger row, so there is no cell to
#: cut. Every string on it is a sentence the pipeline composed about its own run,
#: bounded in length, and every number is a count or a measurement of our own
#: work. A ledger cell that wanted to cross would have to be given a field here
#: first, which is a change a reviewer sees.
FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset()

#: Room for a sentence and no room for an article. The band prints one line per
#: fact, so a cap this size is generous for what it holds and far under anything
#: a fetched body would need.
_SENTENCE_MAX: Final = 240

#: A link on the strip: root-absolute, lowercase, trailing-slashed.
#:
#: Spelled as a grammar rather than left a free string because this is the one
#: cell on the band a browser follows. The leading slash is single and the first
#: segment cannot be empty, which is what refuses `//host/` - a protocol-relative
#: URL is an origin wearing a path's clothes, and a site that never calls home
#: (Guardrail #1) must not be able to grow a link that does.
RoutePath = Annotated[
    str, StringConstraints(pattern=r"^/[a-z0-9-]+(?:/[a-z0-9-]+)*/$", max_length=128)
]


class Health(StrEnum):
    """Green: it worked. Amber: look at it. Red: it did not work."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class RouteId(StrEnum):
    """The five console routes. The id is the address; the label is the words.

    `JUDGEMENT` and `VOICES` joined on 2026-09-12. They are declared here before
    either page draws a panel, because the strip is the console's only
    navigation and a tab naming a route the band does not carry is a tab the
    band's own validator refuses.
    """

    PIPELINES = "pipelines"
    MODEL = "model"
    MACHINE = "machine"
    JUDGEMENT = "judgement"
    VOICES = "voices"


class BandRun(Model):
    """One run of the newest day, as the band draws it."""

    health: Health
    label: str = Field(
        min_length=1,
        max_length=_SENTENCE_MAX,
        description="What the square means, for a reader who cannot see the colour.",
    )


class BandVerdict(Model):
    """Whether the newest day worked, in one sentence and one row of squares."""

    date: DateStamp | None = Field(
        default=None,
        description="The newest day the manifests hold, or null before any run.",
    )
    sentence: str = Field(min_length=1, max_length=_SENTENCE_MAX)
    health: Health
    runs: list[BandRun] = Field(
        default_factory=list,
        description=(
            "One square a run, in the order they ran. It says what the sentence "
            "cannot: whether one run ate every failure or all five limped."
        ),
    )
    more_runs: int = Field(
        default=0,
        ge=0,
        description="Runs past the squares drawn. A day of thirty squares is a chart.",
    )


class BandWorst(Model):
    """The one worst thing on the whole console, and which route it is on."""

    id: RouteId
    label: str = Field(min_length=1, max_length=_SENTENCE_MAX)
    href: RoutePath
    sentence: str = Field(min_length=1, max_length=_SENTENCE_MAX)


class BandSize(Model):
    """The committed tree against the 1 GB Pages cap (`CLAUDE.md` Guardrail #2)."""

    bytes: int | None = Field(
        default=None,
        ge=0,
        description="The committed payload tree at the newest run, or null if unmeasured.",
    )
    cap_fraction: float | None = Field(
        default=None,
        ge=0.0,
        description="That tree against the cap. Above 1.0 is a site over the cap, not an error.",
    )
    left_mb: float | None = Field(default=None, description="Megabytes left under the cap.")
    articles_to_cap: int | None = Field(
        default=None,
        ge=0,
        description="Articles to the cap, at the cost the whole record measured.",
    )
    measured_days: int = Field(
        default=0,
        ge=0,
        description="Published days the per-article cost was measured over.",
    )
    sentence: str = Field(min_length=1, max_length=_SENTENCE_MAX)


class ConsoleRoute(Model):
    """One route on the strip, carrying its own worst state."""

    id: RouteId
    label: str = Field(min_length=1, max_length=64)
    href: RoutePath
    description: str = Field(min_length=1, max_length=_SENTENCE_MAX)
    worst: str | None = Field(
        default=None,
        max_length=_SENTENCE_MAX,
        description="The route's own worst state, appended to its label. Null when clear.",
    )
    severity: int = Field(
        ge=0,
        le=3,
        description=(
            "How loud the route's worst state is: 0 clear, 1 worth knowing, 2 worth a "
            "look, 3 broken. Ranked rather than coloured - the strip never takes the "
            "health ramp, because a route is a noun."
        ),
    )
    carries: str = Field(
        min_length=1,
        max_length=_SENTENCE_MAX,
        description="One sentence pointing at the panel another route owns.",
    )


class ConsoleBand(Contract):
    """What every console route carries above its own panels."""

    __schema_stem__: ClassVar[str] = "console-band"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12",
            change=(
                "RouteId gains the route ids judgement and voices, so the strip and "
                "the worst-thing link carry five routes rather than three."
            ),
            why=(
                "Additive: an older payload names three of the five and validates "
                "unchanged, and the reader keeps a route the payload omits on the "
                "strip with no worst state. The ids are minted here rather than with "
                "the panels because the band's own validator refuses a worst route "
                "the strip does not carry, so a tab cannot be drawn before its id "
                "exists on this shape."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Initial shape: the verdict, the worst thing, the size, the route "
                "strip, and the months list the console pans over."
            ),
            why=(
                "The band is derived from six committed ledgers and was inlined into "
                "three prerendered documents, so the one thing an operator reads first "
                "was the one thing with no contract and no version stamp (Guardrail #3). "
                "Fetching it first and alone is what lets the console answer 'did it "
                "work' before a single month file lands, and the months list is on it "
                "because a shell that had to ask for the list separately would make "
                "the first month a third serial hop."
            ),
        ),
    )

    generated_at: Timestamp
    verdict: BandVerdict
    worst: BandWorst | None = Field(
        default=None,
        description="Null when every route is clear, which is a state and not an absence.",
    )
    size: BandSize
    routes: list[ConsoleRoute] = Field(
        default_factory=list,
        description="The strip, in the order it is drawn.",
    )
    months: list[MonthStamp] = Field(
        default_factory=list,
        description=(
            "Every month a payload shard exists for, oldest first. The console asks "
            "for a month by name, so this is the list it picks from - and it is here "
            "rather than in a file of its own so the first month is the second hop "
            "and not the third."
        ),
    )

    @model_validator(mode="after")
    def _the_worst_route_is_on_the_strip(self) -> Self:
        """A band pointing at a route the strip does not carry is a link that
        goes nowhere, and the strip is the only navigation the console has."""
        if self.worst is not None and self.worst.id not in {route.id for route in self.routes}:
            raise ValueError(f"the worst route {self.worst.id} is not on the strip")
        return self

    @model_validator(mode="after")
    def _the_months_are_sorted_and_distinct(self) -> Self:
        """The console pans by index, so a repeated or out-of-order month reads
        as a jump backwards in time."""
        if self.months != sorted(set(self.months)):
            raise ValueError("months must be distinct and oldest first")
        return self


if FORBIDDEN_COLUMNS & set(ConsoleBand.model_fields):
    raise AssertionError(
        "a field a reader may never receive is on the console band: "
        f"{sorted(FORBIDDEN_COLUMNS & set(ConsoleBand.model_fields))}"
    )
