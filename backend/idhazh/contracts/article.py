"""One item's fetched, extracted and sanitized text - or the recorded failure.

The Extract stage is the trust boundary, crossed exactly once. Everything on
this payload that originated on someone else's server - `title`, `text`,
`source_url` - is data and never instruction (Holy Law #11). Nothing here may
become a system prompt, a shell argument, a file path or an outbound URL.

A failure is a state of this payload, not an absence of it: a dead link, a
paywall or a broken extractor degrades its own item and records why, and its
siblings never notice.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    derive_url_key,
)
from idhazh.contracts.taxonomy import EventType, LensId, SourceTier

# Structural bounds on untrusted text that reaches a page or a log line. Not a
# tunable: the extraction caps a reasonable operator would move live in config.
UntrustedLine = Annotated[str, StringConstraints(min_length=1, max_length=500)]


class ArticleStatus(StrEnum):
    OK = "ok"
    FETCH_FAILED = "fetch_failed"
    EXTRACT_FAILED = "extract_failed"
    ROBOTS_DENIED = "robots_denied"


class Article(Contract):
    """The Extract stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "article"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: identity, provenance, text, truncation and failure states.",
            why="Contracts before logic - Extract is written against a fixed payload.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey = Field(
        description="sha256 of canonical_url. Identity for dedupe and skip - a field, never a path."
    )
    source_url: Url = Field(description="The address as discovered.")
    canonical_url: Url = Field(
        description="The address after canonicalisation. url_key derives from it."
    )
    source_id: Slug = Field(description="The feed that carried it.")
    tier: SourceTier

    vertical: Slug
    lenses: list[LensId] = Field(default_factory=list)
    events: list[EventType] = Field(default_factory=list)
    entities: list[Slug] = Field(default_factory=list)
    carried_by: int = Field(
        default=1, ge=1, description="Independent sources that carried this story today."
    )
    rank_score: float = Field(ge=0.0)

    title: UntrustedLine | None = None
    text: str | None = Field(default=None, description="Sanitized text. Never republished.")
    word_count: int = Field(default=0, ge=0)
    token_count: int = Field(default=0, ge=0)
    truncated: bool = False
    truncated_at_tokens: int | None = Field(default=None, ge=1)

    published_at: Timestamp | None = None
    fetched_at: Timestamp
    status: ArticleStatus
    failure_detail: UntrustedLine | None = None

    extractor_version: str = Field(min_length=1)
    sanitizer_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_is_rebuilt_not_trusted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must be the sha256 of canonical_url, recomputed on read")
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.status is ArticleStatus.OK:
            if not self.text or self.title is None:
                raise ValueError("an ok article carries title and text")
            if self.failure_detail is not None:
                raise ValueError("an ok article carries no failure_detail")
        elif self.failure_detail is None:
            raise ValueError("a failed article must record why")
        if self.truncated != (self.truncated_at_tokens is not None):
            raise ValueError("truncated and truncated_at_tokens must agree")
        if len(set(self.lenses)) != len(self.lenses):
            raise ValueError("lenses must be distinct")
        if len(set(self.events)) != len(self.events):
            raise ValueError("events must be distinct")
        return self
