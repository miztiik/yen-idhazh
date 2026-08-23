"""What the pipeline has already looked at, and what it has already published.

Two append-only ledgers, because they answer two different questions and are
written by two different jobs.

`SeenRow` answers "how old is this?" for an article whose feed gave no date.
Most feeds that omit a date also omit it consistently, so the only honest age
we have is the first time we saw the address. The plan stage writes it.

`PublishedRow` answers "have we already run this?" A 24-hour window alone does
not stop a repeat: an article published at 23:00 on Monday is seven hours old
at 06:00 on Tuesday and would be planned twice. The assemble stage writes it,
because until a digest is committed nothing was actually published.

Neither row is ever rewritten. A mutable "published" flag on a seen row would
turn an append into a read-modify-write over the whole history, and two runs
racing on that file would lose rows.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Timestamp,
    Url,
    UrlKey,
)


class SeenRow(Contract):
    """One row of `state/seen/<YYYY-MM>.csv`, appended the first time an address is a candidate."""

    __schema_stem__: ClassVar[str] = "seen-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Initial shape: the address, when we first saw it, and the run that saw it.",
            why=(
                "An undated article has no age we can trust. First sight is the only "
                "honest one, and it has to survive the run that observed it."
            ),
        ),
    )

    url_key: UrlKey
    canonical_url: Url
    first_seen_at: Timestamp
    first_seen_run: RunId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)


class PublishedRow(Contract):
    """One row of `state/published.csv`, appended when an item reaches a committed digest."""

    __schema_stem__: ClassVar[str] = "published-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Initial shape: the address, the day it ran, and the item it ran as.",
            why=(
                "A freshness window cannot stop a repeat on its own. Late-evening "
                "articles are still inside the window the next morning."
            ),
        ),
    )

    url_key: UrlKey
    canonical_url: Url
    published_on: DateStamp = Field(description="The digest date, not the article's own date.")
    item_id: ItemId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        return cls.model_validate({name: row[name] for name in cls.model_fields})
