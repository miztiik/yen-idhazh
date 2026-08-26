"""The month search index (`frontend/public/assist/index/<YYYY-MM>.json`).

A projection of the published days of one month, carrying what browsing and
searching read and nothing else: when an item ran, what it is called, which
vertical it belongs to, and where its vector sits.

**It is derived, never authored.** Every field here is copied from a committed
day payload, so deleting a day and re-running assemble regenerates a correct
shard and no separate rebuild command exists. The day payload keeps its own
embeddings block; this file is a second view of it, which is what keeps the
whole search surface strippable.

**A month, because a month is bounded and history is not.** A global index of
every item ever published grows without bound on the hot path of every page
load, which the published layout rejects on sight. A month shard stops growing
when the month ends, and a page still costs a bounded number of requests.

**The vectors are raw bytes in a sibling `<YYYY-MM>.bin`, not base64 in here.**
Measured 2026-08-26 over 2,119 committed vectors: raw int8 transfers at 249.82
gzipped bytes an item against 322.55 for base64 inside JSON, which is 22.5
percent less. The split also decides who pays - every visitor browsing the month
downloads this JSON, and only a reader who searches downloads the vectors.

**`vector` is a byte offset or null, never a position.** Two of the 2,121
committed items carry no vector, and after the token-budget work some items will
deliberately have none. Omitting them would take them out of the browse list as
well as out of search, which is a bigger loss than not being searchable. A
padded zero vector would be worse still: it scores against every query.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    MonthStamp,
    Slug,
    compact_json,
)

# A byte offset into the sibling `.bin`. Non-negative; the cross-field validator
# below is what pins it to a real vector rather than to an arbitrary byte.
VectorOffset = Annotated[int, Field(ge=0)]


class SearchIndexEntry(Model):
    """One published item, as browsing and searching need it.

    No summary, no source, no band. Carrying the summary would take an entry
    from about 151 bytes to about 850 and a month from 471 KB to roughly 2.7 MB
    gzipped, and it would charge every browsing visitor the full text of every
    item in the month. A result renders by fetching the day payload it names -
    at most one fetch per distinct day on screen, and days already open are
    reused.
    """

    date: DateStamp
    item_id: ItemId
    title: UntrustedLine
    vertical: Slug
    vector: VectorOffset | None = Field(
        default=None,
        description=(
            "Byte offset of this item's vector in the sibling `.bin`, or null when the "
            "item has none. An offset rather than a position, so a reader slices the "
            "file directly instead of counting how many entries above it were skipped."
        ),
    )

    @model_validator(mode="after")
    def _item_id_is_addressed_by_vertical(self) -> Self:
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self


class SearchIndex(Contract):
    """`frontend/public/assist/index/<YYYY-MM>.json`."""

    __schema_stem__: ClassVar[str] = "search-index"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-26",
            change=(
                "Initial shape: one month of published items in published order, each "
                "naming a byte offset into a sibling int8 vector file or null."
            ),
            why=(
                "The archive page inlines every committed day so on-device search can see "
                "the whole corpus, which grows about 170 KB gzipped a day and has no bound. "
                "A month shard bounds it. Contracts before logic, so the shape is fixed "
                "before anything reads it - and nothing does yet, which is what makes this "
                "revertible."
            ),
        ),
    )

    month: MonthStamp
    model_id: Slug = Field(
        description="The encoder that wrote every vector in the sibling file. One index, "
        "one encoder: two encoders in one space score as plausible nonsense rather "
        "than failing."
    )
    dimensions: int = Field(
        ge=1,
        description="Components a vector. At int8 this is also its length in bytes.",
    )
    dtype: Literal["int8"]
    scale: float = Field(
        gt=0.0,
        description=(
            "Multiply a stored byte by this to get a component. Stated rather than "
            "assumed, so a later encoder can quantise against the range unit vectors "
            "actually reach without a breaking change to this file."
        ),
    )
    entries: list[SearchIndexEntry]

    @model_validator(mode="after")
    def _entries_are_this_month_in_published_order(self) -> Self:
        dates = [entry.date for entry in self.entries]
        for date in dates:
            if not date.startswith(f"{self.month}-"):
                raise ValueError(f"entry dated {date} is not in month {self.month}")
        if dates != sorted(dates):
            raise ValueError("entries are in published order, so their dates never go back")

        addressed = [(entry.date, entry.item_id) for entry in self.entries]
        if len(set(addressed)) != len(addressed):
            raise ValueError("an item appears at most once on a date")
        return self

    @model_validator(mode="after")
    def _offsets_are_dense_and_in_order(self) -> Self:
        """The vectors are laid end to end in entry order, with no gaps.

        This is what makes a rebuild byte-identical rather than merely correct:
        there is exactly one file the entries can describe. It is also the check
        that catches a hand-built index, where an offset that is off by one
        vector decodes cleanly and ranks nonsense.
        """
        expected = 0
        for entry in self.entries:
            if entry.vector is None:
                continue
            if entry.vector != expected:
                raise ValueError(
                    f"{entry.item_id} on {entry.date} sits at {entry.vector}, "
                    f"but the vectors before it end at {expected}"
                )
            expected += self.dimensions
        return self

    @property
    def vector_bytes(self) -> int:
        """How long the sibling `.bin` must be. Zero when nothing is searchable."""
        return sum(1 for entry in self.entries if entry.vector is not None) * self.dimensions

    def to_json(self) -> str:
        """Compact, unlike every other payload here - see `compact_json`."""
        return compact_json(self.model_dump(mode="json"))
