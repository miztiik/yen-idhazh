"""What one published day did, as the console is allowed to read it.

Three of the console's reads open the same two files per day and reduce both to
counts: `loadManifests` reads `run.json`, and `publishedItems` and
`publishedCharts` each walk `digest.json` for a length. This is the one row that
carries all three answers, written to `frontend/public/run-days/<YYYY-MM>.json`
so the console fetches a month of days instead of opening a day payload apiece.

Folding the three is not a shortcut. They share a key, a window and a producer,
and a day payload is hundreds of kilobytes where these counts are two lines - so
splitting them would cost three fetches to answer one question about one day.
The oracle in row 8 asks that every dataset resolve to exactly one schema file,
and three datasets resolving to one file satisfies it: what it forbids is a
dataset with no file, or two files for one shape.

**Counts only, and that is the trust boundary.** A day payload holds article
titles, addresses and summaries. Nothing on this row can hold any of them: every
cell here is an integer, a date, a run id or a model slug, so there is no field
a fetched string could arrive in (Guardrail #11).
"""

from __future__ import annotations

from typing import ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    Slug,
    Timestamp,
)

#: Nothing is forbidden, because nothing on this shape can carry it.
#:
#: The other published projections cut named cells out of a wider ledger row.
#: This one is built the other way round: it is a reduction of two documents to
#: counts, so the refusal is structural rather than a list. A title, an address
#: or a summary has no field to arrive in, and adding one would be adding a
#: string field to a shape whose every cell is a number - which is a change a
#: reviewer sees rather than a cell that slips through a projection.
FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset()


class PublicRunRecord(Model):
    """One run of one day, from that day's `run.json`."""

    run_id: RunId
    n: int = Field(ge=0, description="Which run of the day this was.")
    status: str = Field(min_length=1, max_length=32)
    planned: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    started_at: Timestamp
    source_list_stale: bool = False
    decided: int = Field(
        default=0,
        ge=0,
        description="Items the visual planner posted to the model.",
    )
    prefiltered: int = Field(
        default=0,
        ge=0,
        description=(
            "Items the planner decided without posting, because no enabled kind "
            "could survive its checks."
        ),
    )
    charts_drafted: int = Field(
        default=0,
        ge=0,
        description="Items whose planner reply asked for a chart, whatever the decision became.",
    )
    decision_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What the planner spent. Null and zero are different facts: a visuals job "
            "that never ran spent no measured time, and printing that as zero minutes "
            "reads as a stage that was free rather than one that is missing."
        ),
    )


class PublicRunDay(Contract):
    """One published day: what its runs did, and what the page ended up carrying."""

    __schema_stem__: ClassVar[str] = "public-run-day"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Initial shape: the day's run records, the site size the last run "
                "measured, the models it used, and the published item and chart counts."
            ),
            why=(
                "The console derived all of this at build time by opening every day's "
                "run.json and every day's digest.json, then inlined the result - so "
                "three of its ten reads had no contract, no version stamp and no "
                "changelog (Guardrail #3). One row a day, fetched a month at a time, also "
                "removes the read that costs the most: a day payload is hundreds of "
                "kilobytes and the console wanted two integers out of it (Guardrail #12)."
            ),
        ),
    )

    date: DateStamp
    runs: list[PublicRunRecord] = Field(
        default_factory=list,
        description="Every run of the day, in the order they ran.",
    )
    site_bytes: int = Field(
        default=0,
        ge=0,
        description=(
            "The committed payload tree as the day's LAST run measured it. Taken from "
            "the last run rather than summed: the site is one thing measured once per "
            "run, not a new thing each run."
        ),
    )
    site_files: int = Field(default=0, ge=0)
    models: list[Slug] = Field(
        default_factory=list,
        description="Distinct model ids the day's runs used, in first-seen order.",
    )
    published_items: int = Field(
        default=0,
        ge=0,
        description=(
            "Articles the day payload carries. The denominator of the site's "
            "per-article cost, counted from the same tree site_bytes measures."
        ),
    )
    published_charts: int = Field(
        default=0,
        ge=0,
        description=(
            "Charts a reader can actually see: a visual of kind chart in state "
            "rendered. Counted from the day payload rather than the manifest, because "
            "the manifest records what the planner decided and this records what "
            "survived to the page."
        ),
    )

    @model_validator(mode="after")
    def _a_chart_needs_an_item_to_sit_on(self) -> Self:
        """The charts are a subset of the items, so a day cannot draw more charts
        than it published articles."""
        if self.published_charts > self.published_items:
            raise ValueError(
                f"{self.date} publishes {self.published_items} items and claims "
                f"{self.published_charts} charts"
            )
        return self


if FORBIDDEN_COLUMNS & set(PublicRunDay.model_fields):
    raise AssertionError(
        "a field a reader may never receive is on the published run-day row: "
        f"{sorted(FORBIDDEN_COLUMNS & set(PublicRunDay.model_fields))}"
    )
