"""One item's summary: our own text, of a pinned shape.

The article body is never committed and never served; this payload and the
source link are the entire published output. The shape is enforced by the
decoder rather than requested in the prompt, so an injected instruction cannot
change it even if it changes the words (Holy Law #11).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Sha256,
    Slug,
    Timestamp,
    UrlKey,
    derive_output_digest,
)


class SummaryStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class Summary(Contract):
    """The Summarize stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "summary"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22",
            change="Split duration_ms into fetch_ms, extract_ms and summarize_ms.",
            why=(
                "One number covering fetch, extract and summarize could not answer the "
                "question it was there for: a slow item might be a slow host or a slow "
                "model, and only one of those is ours to fix. Additive - the blended "
                "field stays, and a payload written before this still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T02:00",
            change="Added required pipeline_fingerprint and output_digest.",
            why=(
                "Skip-if-exists becomes skip-if-fingerprint-matches, and a match with unequal "
                "output has to be detectable. No payload predates this - the pipeline has "
                "never run - so the read-side migration is the fixtures, restamped here."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: summary text, key points, the model, and the cost.",
            why="Contracts before logic - Summarize is written against a fixed payload.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)

    pipeline_fingerprint: Sha256 = Field(
        description="The stamp of every input that could have moved this text."
    )
    output_digest: Sha256 = Field(
        description="Digest of the words only. Recomputed on read, never trusted."
    )

    model_id: Slug = Field(
        description="The ModelRef id from config. The full ref lives in the manifest."
    )
    attempt: int = Field(
        default=1, ge=1, description="A low-band summary is retried on the smaller model."
    )
    source_truncated: bool = False
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    duration_ms: int = Field(
        default=0, ge=0, description="Fetch plus extract plus summarize. The three below sum to it."
    )
    fetch_ms: int = Field(default=0, ge=0, description="Network. Says more about the host than us.")
    extract_ms: int = Field(default=0, ge=0, description="Boilerplate removal and sanitising.")
    summarize_ms: int = Field(
        default=0,
        ge=0,
        description="The model. The only one of the three that a model swap moves.",
    )

    generated_at: Timestamp
    status: SummaryStatus
    failure_detail: UntrustedLine | None = None

    @model_validator(mode="after")
    def _output_digest_is_rebuilt_not_trusted(self) -> Self:
        if self.output_digest != derive_output_digest(self.summary, self.key_points):
            raise ValueError("output_digest must be the digest of summary and key_points")
        return self

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.status is SummaryStatus.OK:
            if not self.summary or not self.key_points:
                raise ValueError("an ok summary carries summary text and at least one key point")
            if self.failure_detail is not None:
                raise ValueError("an ok summary carries no failure_detail")
        elif self.failure_detail is None:
            raise ValueError("a summary that did not land must record why")
        return self
