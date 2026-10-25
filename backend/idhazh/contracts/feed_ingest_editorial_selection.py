"""Which articles did the editor select, before assigning workers?"""

from typing import Any, ClassVar, Literal, Self

from pydantic import model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Sha256,
    Slug,
    Url,
    derive_url_key,
)
from idhazh.contracts.feed_ingest_candidate import (
    SOURCE_OPERATIONAL_SCORE_VERSION,
    ArticleLabels,
    NonEmpty,
    NonNegative,
    PolicyIdentity,
    PositiveCount,
    ScoreEvidence,
    SourceSnapshot,
    reject_legacy_publisher_exposure,
    reject_legacy_publisher_identity,
    reject_legacy_source_operational,
)


class EditorialSelectionRow(Contract):
    """One ranked article and its measured work, with no worker assignment."""

    __schema_stem__: ClassVar[str] = "feed-ingest-editorial-selection"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Record the saved request-estimate trace without changing article rank.",
            why="Operational adjustments need source, support and state-window evidence.",
        ),
        ChangelogEntry(
            version="2026-10-24T23:00",
            change="Replace feed crowding with separately recorded publisher exposure.",
            why="Day publications and current choices are distinct from historical feed penalties.",
        ),
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Record curated publisher identity in source snapshots.",
            why="New selections preserve reviewed identity without rewriting history.",
        ),
        ChangelogEntry(
            version="2026-10-24",
            change="Record a separate measured source-reliability ranking penalty.",
            why="Delivery history changes priority without changing article quality.",
        ),
        ChangelogEntry(
            version="2026-10-20",
            change="Earlier changes are available in git history.",
            why="The contract changelog keeps its four newest changes and one history pointer.",
        ),
    )
    version: Literal["2026-10-25"] = "2026-10-25"
    date: DateStamp
    correlation_id: NonEmpty
    candidate_id: Sha256
    source_id: Slug
    vertical: Slug
    source: SourceSnapshot
    canonical_url: Url
    url_key: Sha256
    labels: ArticleLabels
    editorial_rank: PositiveCount
    estimated_work: NonNegative
    ratings: ScoreEvidence
    policy: PolicyIdentity

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict):
            reject_legacy_publisher_exposure(value, value.get("ratings"))
            reject_legacy_source_operational(value, value.get("ratings"))
        if isinstance(value, dict) and value.get("version") in {
            "2026-10-20", "2026-10-24", "2026-10-24T20:04", "2026-10-24T23:00"
        }:
            reject_legacy_publisher_identity(value, [value.get("source")])
            ratings = value.get("ratings")
            if (
                value.get("version") == "2026-10-20"
                and isinstance(ratings, dict)
                and ratings.get("source_reliability") is not None
            ):
                raise ValueError("source reliability requires the declared score contract version")
            return {**value, "version": SOURCE_OPERATIONAL_SCORE_VERSION}
        return value

    @model_validator(mode="after")
    def validate_url_key(self) -> Self:
        if self.source_id != self.source.source_id or self.vertical != self.source.vertical:
            raise ValueError("source_id and vertical must match the source snapshot")
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must match canonical_url")
        return self
