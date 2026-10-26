"""Which UTC instant first established an article's global URL identity?"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Literal, Self

from pydantic import ConfigDict, model_validator

from idhazh.contracts.base import (
    JSON_SCHEMA_DIALECT,
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    canonical_json,
)
from idhazh.contracts.recorded_instant import RecordedInstant

PLANNER_LEDGER_VERSION: Final[Literal["2026-10-25"]] = "2026-10-25"


class PlannerModel(Model):
    """Current planner values reject coercion as well as undeclared fields."""

    model_config = ConfigDict(strict=True, revalidate_instances="always")


class PlannerPayload(PlannerModel):
    """Planner schema metadata without an injected per-row version field."""

    __schema_stem__: ClassVar[str]
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=PLANNER_LEDGER_VERSION,
            change="Declare the metadata-only planner ledgers without generic writer identity.",
            why="The four current planner ledgers replace the retired audit formats.",
        ),
    )

    @classmethod
    def contract_version(cls) -> str:
        return cls.__changelog__[0].version

    @classmethod
    def schema_filename(cls) -> str:
        return f"{cls.__schema_stem__}.schema.json"

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        return cls.model_json_schema() | {
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": cls.schema_filename(),
            "version": cls.contract_version(),
            "changelog": [entry.model_dump(mode="json") for entry in cls.__changelog__],
        }

    @classmethod
    def schema_text(cls) -> str:
        return canonical_json(cls.json_schema())

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls.model_validate_json(text)

    def to_json(self) -> str:
        return canonical_json(self.model_dump(mode="json"))


class PlannerRow(PlannerPayload):
    """A ledger row whose version belongs once to its file, not to every row."""

    __previous_versions__: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def schema_version(cls) -> str:
        return cls.contract_version()

    @classmethod
    def accepts_schema_version(cls, version: str) -> bool:
        return version == cls.schema_version() or version in cls.__previous_versions__

    @classmethod
    def read_row(cls, cells: dict[str, Any], *, schema_version: str) -> Self:
        if not cls.accepts_schema_version(schema_version):
            raise ValueError("incompatible planner row schema version")
        return cls.model_validate(cells)


class DiscoveredArticleRow(PlannerRow):
    """The earliest observed instant for one URL across every supplying feed."""

    __schema_stem__: ClassVar[str] = "feed-ingest-discovered-article"

    url_key: Sha256
    first_seen_at: RecordedInstant
    date: DateStamp

    @model_validator(mode="after")
    def validate_discovery_day(self) -> Self:
        if self.date != self.first_seen_at[:10]:
            raise ValueError("discovery date must be the UTC day of first_seen_at")
        return self


type LedgerContract = Contract | PlannerRow
