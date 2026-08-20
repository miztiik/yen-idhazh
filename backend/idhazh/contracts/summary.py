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
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, Slug, Timestamp, UrlKey


class SummaryStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class Summary(Contract):
    """The Summarize stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "summary"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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

    model_id: Slug = Field(
        description="The ModelRef id from config. The full ref lives in the manifest."
    )
    attempt: int = Field(
        default=1, ge=1, description="A low-band summary is retried on the smaller model."
    )
    source_truncated: bool = False
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)

    generated_at: Timestamp
    status: SummaryStatus
    failure_detail: UntrustedLine | None = None

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
