"""The local ledger for human labels on published pie and bubble charts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Sha256,
    Slug,
    Timestamp,
    Url,
    derive_text_digest,
)
from idhazh.contracts.visual_type import VisualType

# The instrument measures only these two exact rendered types. Adding a type
# changes the question the rate answers.
VISUAL_LABEL_TYPES: Final[tuple[VisualType, VisualType]] = (
    VisualType.PIE,
    VisualType.BUBBLE,
)
_DRAW_ID_FORMAT: Final = "visual-label-draw-v1"


def visual_label_draw_id(
    *,
    queue_sha256: str,
    queue_date: str,
    published_base_url: str,
    visual_types: tuple[VisualType, VisualType] = VISUAL_LABEL_TYPES,
) -> str:
    """Bind the exact queue bytes, date, destination and type scope."""
    return derive_text_digest(
        "\0".join(
            (
                _DRAW_ID_FORMAT,
                queue_sha256,
                queue_date,
                published_base_url,
                *(visual_type.value for visual_type in visual_types),
            )
        )
    )


def normalize_published_base_url(value: str) -> str:
    """Keep the live destination free of credentials, query strings and fragments."""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(part in {".", ".."} for part in parsed.path.split("/"))
    ):
        raise ValueError(
            "published_base_url must be an HTTPS URL without credentials, "
            "query, fragment or dot path segments"
        )
    return value.rstrip("/")


class VisualLabel(StrEnum):
    """The human's answer to whether a published chart earned its place."""

    KEEP = "keep"
    DISCARD = "discard"


class VisualLabelDraw(Contract):
    """The exact review queue and published destination behind one draw."""

    __schema_stem__: ClassVar[str] = "visual-label-draw"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-27T11:32",
            change="Initial exact-queue draw and published destination.",
            why="A reviewer must revisit the same published visual and queue.",
        ),
    )

    draw_id: Sha256 = Field(description="Digest binding the queue, URL and chart types.")
    queue_sha256: Sha256 = Field(description="Digest of the exact queue file bytes.")
    queue_date: DateStamp
    published_base_url: Url = Field(
        description="Operator-supplied HTTPS base URL for the published dated item route."
    )
    visual_types: tuple[VisualType, VisualType] = VISUAL_LABEL_TYPES
    created_at: Timestamp = Field(description="Draw creation instant in UTC.")

    @field_validator("published_base_url")
    @classmethod
    def _published_base_url_is_safe(cls, value: str) -> str:
        return normalize_published_base_url(value)

    @model_validator(mode="after")
    def _draw_has_the_two_requested_types(self) -> Self:
        if self.visual_types != VISUAL_LABEL_TYPES:
            raise ValueError("a visual-label draw contains pie and bubble rows only")
        expected = visual_label_draw_id(
            queue_sha256=self.queue_sha256,
            queue_date=self.queue_date,
            published_base_url=self.published_base_url,
            visual_types=self.visual_types,
        )
        if self.draw_id != expected:
            raise ValueError("draw_id must identify its exact queue and published destination")
        return self


class VisualLabelRow(Contract):
    """One named reviewer's label for one visual in one exact draw."""

    __schema_stem__: ClassVar[str] = "visual-label-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-27T11:32",
            change="Initial local pie and bubble label row.",
            why="Human verdicts stay separate from machine outcomes.",
        ),
    )

    draw_id: Sha256
    visual_id: Sha256
    reviewer_id: Slug
    queue_position: int = Field(
        ge=1,
        description="One-based position in the draw's published pie and bubble queue.",
    )
    label: VisualLabel
    labelled_at: Timestamp = Field(description="Human label instant in UTC.")

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the row."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)
