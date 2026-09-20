"""Why a run stopped asking one address, and on what evidence.

One row per retired feed endpoint, appended to `state/feed-retirements.csv`.
A run writes it; nothing in it edits `config/sources.json`, which stays the
registry a person curates.

Retirement is filed against the endpoint and never against the feed. The key is
`endpoint_key` - the sha256 of the configured feed URL - so editing that URL is
a new address with no inherited retirement, and a source that moved can be
asked again by changing one line of curated config.

`http_410` was the only cause the enum admitted until 2026-09-17, because a
403, a 404, a paywall, a transient failure or an empty feed all say something
about today and only `410 Gone` is the server telling us the address is not
coming back. Every other failure rests a feed, which lifts on its own.

`low_yield` is the second cause and it answers that clause rather than
deleting it. The risk named there is real: retiring on anything softer than
`410` eventually removes unique primary or regional reporting over a bad week.
So a low-yield retirement cannot be decided by a week - it needs a trailing
share under the alarm point, on at least `collect.source_yield_min_complete_days`
finished days and `collect.source_yield_alarm_min_decisions` decisions, held
there for `collect.source_quality_dwell_days` running. A bad week cannot retire
anything.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
)

#: What separates two run ids inside the one evidence cell. A space, because a
#: comma would need quoting in a file that is settled a line at a time, and a
#: run id can never contain one.
EVIDENCE_SEPARATOR = " "

#: The cells that hold a list inside one CSV column. Named once, so the writer
#: and the reader cannot disagree about which columns need splitting.
_EVIDENCE_CELLS: Final = ("evidence_run_ids", "evidence_dates")


class RetirementCause(StrEnum):
    """Why an address was retired. Two members, and adding a third is a design change.

    Retiring on anything softer than `410 Gone` eventually removes unique
    primary or regional reporting over a bad week, and nothing here can put it
    back without a person noticing it went. That clause stands. `LOW_YIELD` is
    what it costs to answer it: three evidence floors and a dwell, spelled out
    in this module's docstring, so no single bad week reaches this row.
    """

    HTTP_410 = "http_410"
    LOW_YIELD = "low_yield"


class FeedRetirementRow(Contract):
    """One retired endpoint, one row."""

    __schema_stem__: ClassVar[str] = "feed-retirement-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-17",
            change="RetirementCause gained low_yield, and evidence_dates beside evidence_run_ids.",
            why="A source that answers and never reads had no way to stop being asked.",
        ),
        ChangelogEntry(
            version="2026-09-02T20:00",
            change="Initial shape: the feed, the endpoint, the day, the deciding run, the cause.",
            why="Only a person could stop the pipeline asking a dead address.",
        ),
    )

    feed_id: Slug
    endpoint_key: Sha256 = Field(
        description="The address that was retired, as `feed_health.derive_endpoint_key` spells it."
    )
    retired_on: DateStamp
    decided_by_run: RunId = Field(description="The run that read the evidence and wrote this row.")
    cause: RetirementCause
    evidence_run_ids: tuple[RunId, ...] = Field(
        default=(),
        description=(
            "The distinct runs whose results justify the retirement, oldest first. "
            "Space-separated in the CSV cell. Recorded rather than counted, so the "
            "decision can be checked against the ledger that produced it. The evidence "
            "cell an `http_410` retirement fills: five runs read five `410` answers."
        ),
    )
    evidence_dates: tuple[DateStamp, ...] = Field(
        default=(),
        description=(
            "The distinct complete days whose yield justifies the retirement, oldest "
            "first. Space-separated in the CSV cell. The evidence cell a `low_yield` "
            "retirement fills, because that decision is made on days and not on runs: "
            "a day the schedule fired five times is still one day under the mark, and "
            "recording its five run ids would say a fortnight's dwell was a fortnight "
            "and a half."
        ),
    )

    @model_validator(mode="after")
    def _the_evidence_matches_the_cause(self) -> Self:
        """Each cause fills its own evidence cell, and exactly one of them.

        The two cells are not interchangeable and the shape says so rather than
        leaving a reader to infer it: a `410` is a run's reading of an address
        and a low yield is a day's share. A row with neither is a retirement
        nobody can check, which is the one thing this ledger exists to prevent.
        """
        runs = len(self.evidence_run_ids)
        dates = len(self.evidence_dates)
        if self.cause is RetirementCause.HTTP_410 and (not runs or dates):
            raise ValueError("an http_410 retirement names the runs that read the 410")
        if self.cause is RetirementCause.LOW_YIELD and (not dates or runs):
            raise ValueError("a low_yield retirement names the days it stayed under the mark")
        return self

    @model_validator(mode="after")
    def _evidence_names_distinct_runs(self) -> Self:
        """One run failing five times is one run's evidence, not five runs' worth.

        The rule the retirement rests on is distinct runs, so a repeated id here
        would let a single bad afternoon retire an address on its own. The same
        holds a day at a time for the dwell, and for the same reason.
        """
        if len(set(self.evidence_run_ids)) != len(self.evidence_run_ids):
            raise ValueError("evidence_run_ids must name distinct runs")
        if len(set(self.evidence_dates)) != len(self.evidence_dates):
            raise ValueError("evidence_dates must name distinct days")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, and each evidence list one cell rather than many.

        A column per evidence run would make the header depend on how much
        evidence the retirement happened to carry, and the header is the one
        thing every reader here maps by.
        """
        payload = self.model_dump(mode="json")
        for name in _EVIDENCE_CELLS:
            payload[name] = EVIDENCE_SEPARATOR.join(payload[name])
        return {name: str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty evidence cell is no evidence, never one empty string.

        `evidence_dates` is read with `get` because it landed after the first
        rows did: a file written before 2026-09-17 has no such column, and the
        read-side answer is the empty tuple its default already means.
        """
        payload: dict[str, Any] = {
            name: row[name] for name in cls.model_fields if name not in _EVIDENCE_CELLS
        }
        for name in _EVIDENCE_CELLS:
            cell = row.get(name, "")
            payload[name] = tuple(cell.split(EVIDENCE_SEPARATOR)) if cell else ()
        return cls.model_validate(payload)
