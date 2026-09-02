"""Why a run stopped asking one address, and on what evidence.

One row per retired feed endpoint, appended to `state/feed-retirements.csv`.
A run writes it; nothing in it edits `config/sources.json`, which stays the
registry a person curates.

Retirement is filed against the endpoint and never against the feed. The key is
`endpoint_key` - the sha256 of the configured feed URL - so editing that URL is
a new address with no inherited retirement, and a source that moved can be
asked again by changing one line of curated config.

`http_410` is the only cause the enum admits, and that is the whole design. A
403, a 404, a paywall, a transient failure or an empty feed all say something
about today; only `410 Gone` is the server telling us the address is not coming
back. Every other failure rests a feed, which lifts on its own.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

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
#: comma would need quoting in a file `merge=union` settles line by line, and a
#: run id can never contain one.
EVIDENCE_SEPARATOR = " "


class RetirementCause(StrEnum):
    """Why an address was retired. One member, and adding a second is a design change.

    Retiring on anything softer than `410 Gone` eventually removes unique
    primary or regional reporting over a bad week, and nothing here can put it
    back without a person noticing it went.
    """

    HTTP_410 = "http_410"


class FeedRetirementRow(Contract):
    """One retired endpoint, one row."""

    __schema_stem__: ClassVar[str] = "feed-retirement-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-02T20:00",
            change=(
                "Initial shape: the feed, the endpoint, the day, the deciding run, the "
                "cause and the runs that evidenced it."
            ),
            why=(
                "Only a person could stop the pipeline asking a dead address, so a feed "
                "the server reported permanently gone was requested on every run until "
                "somebody edited curated config. The record has to live outside "
                "config/sources.json: a generated commit may not rewrite a file a "
                "person curates."
            ),
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
        min_length=1,
        description=(
            "The distinct runs whose results justify the retirement, oldest first. "
            "Space-separated in the CSV cell. Recorded rather than counted, so the "
            "decision can be checked against the ledger that produced it."
        ),
    )

    @model_validator(mode="after")
    def _evidence_names_distinct_runs(self) -> Self:
        """One run failing five times is one run's evidence, not five runs' worth.

        The rule the retirement rests on is distinct runs, so a repeated id here
        would let a single bad afternoon retire an address on its own.
        """
        if len(set(self.evidence_run_ids)) != len(self.evidence_run_ids):
            raise ValueError("evidence_run_ids must name distinct runs")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, and the evidence list one cell rather than many.

        A column per evidence run would make the header depend on how much
        evidence the retirement happened to carry, and the header is the one
        thing every reader here maps by.
        """
        payload = self.model_dump(mode="json")
        payload["evidence_run_ids"] = EVIDENCE_SEPARATOR.join(payload["evidence_run_ids"])
        return {name: str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. Every cell on this row is required, so none reads as absent."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        payload["evidence_run_ids"] = tuple(payload["evidence_run_ids"].split(EVIDENCE_SEPARATOR))
        return cls.model_validate(payload)
