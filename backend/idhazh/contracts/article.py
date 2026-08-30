"""One item's fetched, extracted and sanitized text - or the recorded failure.

The Extract stage is the trust boundary, crossed exactly once. Everything on
this payload that originated on someone else's server - `title`, `text`,
`source_url` - is data and never instruction (Rule #11). Nothing here may
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
from idhazh.contracts.item_health import FAILURE_CODE_STAGES, FailureCode, ItemStage
from idhazh.contracts.sources import SourceForm
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
            version="2026-08-27",
            change="failure_code may now carry copied_source or leaked_address.",
            why=(
                "Summarize gained two rejects and the failure vocabulary is inlined into "
                "this schema, so this generated file's bytes move even though no field "
                "on this payload changed and extract can never write either value. "
                "Stamped here rather than left to the drift gate to announce (section "
                "11). Additive - a payload written before today names none of the new "
                "values and still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Added source_word_count: the body length before the truncation cap.",
            why=(
                "The length band is named min_source_words and was being chosen from the "
                "post-cap count, which cannot exceed int(truncation_cap_tokens / 1.3). At "
                "the committed cap of 2500 that ceiling is 1923 words, so the 2000-word "
                "band was unreachable by arithmetic. The field is None on payloads written "
                "before it existed, where band_source_words falls back to the post-cap "
                "count the build that wrote them used."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:49",
            change="Added source_form to the extract payload.",
            why=(
                "Summarize and publish need the curator-declared source form after the "
                "plan file is no longer in hand. The field defaults to article so older "
                "payloads still read."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change="Added brief and failure_code to the extract payload.",
            why=(
                "Extract now publishes short or list-shaped pages by default while recording "
                "the shape signal, and it rejects paywalled or unsupported forms with typed "
                "codes that the item-health classifier can carry."
            ),
        ),
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
    source_form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description="Declared by the feed config. Never inferred from extracted text.",
    )

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
    word_count: int = Field(default=0, ge=0, description="Words in `text`, after the cap.")
    source_word_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Words in the extracted body before `extract.truncation_cap_tokens` cut it. "
            "A count, never the text: the pre-cap body is not kept and is not ours to "
            "republish. None on a payload written before the field existed."
        ),
    )
    token_count: int = Field(default=0, ge=0)
    brief: bool = Field(
        default=False,
        description="True when the source is short enough that summarize uses the brief tier.",
    )
    truncated: bool = False
    truncated_at_tokens: int | None = Field(default=None, ge=1)

    published_at: Timestamp | None = None
    fetched_at: Timestamp
    status: ArticleStatus
    failure_code: FailureCode | None = Field(
        default=None,
        description="Typed extract failure, or a recorded extract signal on an ok article.",
    )
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
            if self.failure_code not in {
                None,
                FailureCode.TOO_SHORT,
                FailureCode.NOT_PROSE,
                FailureCode.BOILERPLATE,
            }:
                raise ValueError("an ok article carries only a recorded extract signal")
        elif self.failure_detail is None:
            raise ValueError("a failed article must record why")
        if (
            self.failure_code is not None
            and ItemStage.EXTRACT not in FAILURE_CODE_STAGES[self.failure_code]
            and ItemStage.FETCH not in FAILURE_CODE_STAGES[self.failure_code]
        ):
            raise ValueError("article failure_code must belong to fetch or extract")
        if self.truncated != (self.truncated_at_tokens is not None):
            raise ValueError("truncated and truncated_at_tokens must agree")
        if self.source_word_count is not None and self.source_word_count < self.word_count:
            raise ValueError("source_word_count counts the body before the cap, so it is not less")
        if len(set(self.lenses)) != len(self.lenses):
            raise ValueError("lenses must be distinct")
        if len(set(self.events)) != len(self.events):
            raise ValueError("events must be distinct")
        return self

    @property
    def band_source_words(self) -> int:
        """The length a `summarize.bands` tier is chosen from.

        The read-side migration for `source_word_count`. A payload written
        before the field existed carries only the post-cap count, which is the
        number the build that wrote it used, so that is what it keeps reading.
        """
        return self.word_count if self.source_word_count is None else self.source_word_count
