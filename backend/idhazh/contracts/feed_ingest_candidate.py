"""Which sanitized article and configured feed facts belong to one transient offered entry?"""

from __future__ import annotations

import hashlib
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    Sha256,
    Slug,
    Timestamp,
    Url,
    derive_url_key,
)
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier

# Shared by the retained technical fetch/parse DTOs, not by an audit ledger.
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]


def derive_candidate_id(run_id: str, source_id: str, entry_ordinal: int) -> str:
    """Hash validated run/source/zero-based ordinal with newline separators."""
    from pydantic import TypeAdapter

    run = TypeAdapter(RunId).validate_python(run_id)
    source = TypeAdapter(Slug).validate_python(source_id)
    ordinal = TypeAdapter(Count).validate_python(entry_ordinal)
    return hashlib.sha256(f"{run}\n{source}\n{ordinal}".encode()).hexdigest()


class SourceSnapshot(Model):
    """The configured feed facts used by this execution, never inferred labels."""

    source_id: Slug
    publisher_id: Slug | None = None
    feed_url: Url
    title: NonEmpty
    vertical: Slug
    kind: SourceKind
    tier: SourceTier
    form: SourceForm
    status: LifecycleStatus
    weight: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    applied_tier_weight: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FeedIngestCandidate(Contract):
    """One current candidate held only in the bounded server-owned batch."""

    __schema_stem__: ClassVar[str] = "feed-ingest-candidate"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Keep sanitized content and configured feed facts without audit trees.",
            why="The current planner holds complete candidate batches only in memory.",
        ),
    )

    version: Literal["2026-10-25"] = "2026-10-25"
    date: DateStamp
    correlation_id: NonEmpty
    run_id: RunId
    candidate_id: Sha256
    entry_ordinal: Count
    source_id: Slug
    vertical: Slug
    source: SourceSnapshot
    canonical_url: Url
    url_key: Sha256
    title: NonEmpty
    categories: list[str]
    article_text: str
    word_count: Count
    author: str | None
    published_at: Timestamp | None
    fetched_at: Timestamp

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must match canonical_url")
        if self.source_id != self.source.source_id or self.vertical != self.source.vertical:
            raise ValueError("candidate feed must match configured feed facts")
        if self.candidate_id != derive_candidate_id(
            self.run_id, self.source_id, self.entry_ordinal
        ):
            raise ValueError("candidate identity must match run, feed and offered ordinal")
        if self.date != self.fetched_at[:10]:
            raise ValueError("candidate date must match its UTC captured batch clock")
        return self
