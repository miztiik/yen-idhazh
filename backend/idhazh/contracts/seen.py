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

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Timestamp,
    UrlKey,
)


class SeenRow(Contract):
    """One row of `state/seen/<YYYY-MM>.csv`, appended the first time an address is a candidate.

    It carries no address, for the reason `PublishedRow` carries none: nothing on
    the read path opens one. `ledger.load_seen` reads `url_key` and
    `first_seen_at` and returns a map of the two.
    """

    __schema_stem__: ClassVar[str] = "seen-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-31",
            change="Removed canonical_url. The row is url_key, first_seen_at and first_seen_run.",
            why=(
                "The same defect PublishedRow shed on 2026-08-26, one ledger over, and "
                "it was worse here because this ledger is written for every candidate "
                "rather than for every published item. `load_seen` is the only reader "
                "and it opens url_key and first_seen_at. Measured on the committed "
                "shard: 2,800,867 of 5,705,102 bytes, 49.1 percent of the file, over "
                "25,036 rows in 8 days. The address is still recoverable where it "
                "matters - a row that reached a reader joins to that day's payload by "
                "url_key, and a row that did not is one nobody can look up anyway."
            ),
        ),
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
    first_seen_at: Timestamp
    first_seen_run: RunId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)


class PublishedRow(Contract):
    """One row of `state/published.csv`, appended when an item reaches a committed digest.

    It carries no address. `item_id` and `published_on` join to that day's
    committed payload, where the address is already published as `source_url` -
    see `docs/architecture/sources/freshness.md` for the worked recovery.
    """

    __schema_stem__: ClassVar[str] = "published-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-26",
            change="Removed canonical_url. The row is url_key, published_on and item_id.",
            why=(
                "Nothing on the read path opened it: load_published maps url_key to "
                "published_on by name. It was 48.6 percent of a row on a ledger with "
                "no time bound. The address is recoverable by joining item_id and "
                "published_on against that day's payload, which retention may not touch."
            ),
        ),
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
    published_on: DateStamp = Field(description="The digest date, not the article's own date.")
    item_id: ItemId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)
