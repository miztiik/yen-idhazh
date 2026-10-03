"""Which files does a ledger hold for one day or one period, and how far has compaction reached?

Three small files answer it, one question each, and a later run reads every one
of them, so each is a contract with its own stem and changelog:

- `RawDayIndex` lists the raw files one day of one ledger holds.
- `CompactIndex` lists the compact files one period of one ledger holds. It is
  what a reader outside Python fetches to learn which days, months and years
  exist.
- `Watermark` says how far one period of one ledger has been compacted, which
  is where the next compaction resumes.

Each is written whole, never appended to. `CompactEntry` is one line of a
`CompactIndex` and has no file of its own, so it is a `Model`.

**A day, a month and a year are told apart by shape, and one function decides
the shape.** A `PeriodStamp` holds any of them, so without a check a daily index
could list a month and a daily watermark could stand on one. `covers_fits` in
`file_envelope` is the rule the file envelope already applies to a compact
file, so an index, a watermark and the file they describe cannot disagree about
what a daily, a monthly or a yearly period looks like.

Every day, month and year here is a UTC one, and every instant is UTC
(CLAUDE.md section 2).
"""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from typing import ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    FileIdName,
    Model,
    PeriodStamp,
    RunId,
    Sha256,
    Timestamp,
    records_json,
)
from idhazh.contracts.file_envelope import Period, Tier, covers_fits
from idhazh.contracts.ledger_name import LedgerName

#: What each period's stamp looks like, in the words a refusal prints.
_SHAPE: Final[dict[Period, str]] = {
    Period.DAILY: "a UTC day, YYYY-MM-DD",
    Period.MONTHLY: "a UTC month, YYYY-MM",
    Period.YEARLY: "a UTC year, YYYY",
}


def _repeated(values: list[str]) -> list[str]:
    """The values that appear more than once, sorted, each named once."""
    return sorted(value for value, seen in Counter(values).items() if seen > 1)


def _first_descent(values: list[str]) -> tuple[str, str] | None:
    """The first neighbouring pair that does not ascend, or None when every pair does."""
    for before, after in pairwise(values):
        if before >= after:
            return before, after
    return None


class RawDayIndex(Contract):
    """Which raw files exist for one day of one ledger.

    Staged by the site build for days not packed yet, carrying `bytes` so the
    browser can price the files before it fetches them. The compaction no longer
    writes one; a listing an older compaction left omits `bytes`.
    """

    __schema_stem__: ClassVar[str] = "raw-day-index"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-03",
            change="Only the site build writes a listing; the compaction no longer does.",
            why="Nothing read a compaction listing once its day was packed.",
        ),
        ChangelogEntry(
            version="2026-10-02",
            change="bytes is an optional size for each listed file, filled by the site build.",
            why="A browser prices and checks writer files before it fetches them.",
        ),
        ChangelogEntry(
            version="2026-10-01T16:50",
            change="Remove the retired aggregate from the ledger vocabulary.",
            why="Only declared families may reach an index; surviving fields are unchanged.",
        ),
        ChangelogEntry(
            version="2026-10-01",
            change="ledger may name summary-quality-evals, and scores is refused.",
            why="The eval ledger is named for what it holds; its files were rewritten.",
        ),
        ChangelogEntry(
            version="2026-09-27",
            change="Initial shape: the raw files one day of one ledger holds, and their digest.",
            why="A compaction has to know which raw files a day holds before it takes them.",
        ),
    )

    ledger: LedgerName = Field(description="Which ledger the files belong to.")
    date: DateStamp = Field(
        description=(
            "The UTC day the listed files hold rows for. Not the day this index was "
            "written, and not `version`, which dates the shape of this document."
        )
    )
    files: list[FileIdName] = Field(
        description=(
            "The name of every raw file in the day's directory, in ascending order and "
            "none twice. Empty is legal: the day was looked at and made nothing."
        )
    )
    content_sha256: Sha256 = Field(
        description=(
            "SHA-256 of the names in `files`, in their listed order, joined with one "
            "newline between names and none at the end, encoded as UTF-8. An empty list "
            "digests the empty string."
        )
    )
    bytes: list[int] | None = Field(
        default=None,
        description=(
            "The size in bytes of each file in `files`, in the same order. A listing "
            "an older compaction wrote omits it; the site build fills it for days not "
            "packed yet so the browser can price and check each file before it fetches it."
        ),
    )
    listed_at: Timestamp = Field(
        description=(
            "When the site build, or an older compaction, last listed the day's directory, UTC, "
            "to the whole second: the moment this index last agreed with the tree."
        )
    )

    @model_validator(mode="after")
    def _the_files_ascend_and_none_repeats(self) -> Self:
        """A sorted list with no repeat is what the digest is taken over."""
        where = f"the {self.ledger.value} index for {self.date}"
        repeated = _repeated(self.files)
        if repeated:
            raise ValueError(f"{where} names {repeated} more than once")
        descent = _first_descent(self.files)
        if descent is not None:
            raise ValueError(
                f"{where} lists its files out of order: {descent[0]!r} comes before "
                f"{descent[1]!r}, and the names must ascend"
            )
        if self.bytes is not None and len(self.bytes) != len(self.files):
            raise ValueError(
                f"{where} lists {len(self.files)} files and {len(self.bytes)} sizes; "
                "bytes must match files one for one"
            )
        if self.bytes is not None and any(size < 0 for size in self.bytes):
            raise ValueError(f"{where} bytes contains negative sizes")
        return self


class CompactEntry(Model):
    """One compact file named in a `CompactIndex`: what it covers, its rows, its size."""

    covers: PeriodStamp = Field(
        description=(
            "The UTC day (`2026-09-23`), the UTC month (`2026-08`) or the UTC year "
            "(`2026`) this one compact file holds rows for."
        )
    )
    rows: int = Field(
        ge=0,
        description="How many rows the file holds after settling: one row per record key.",
    )
    bytes: int = Field(
        ge=0,
        description=(
            "The file's size in bytes, so a reader can check `Content-Length` before it "
            "parses anything."
        ),
    )


class CompactIndex(Contract):
    """Which compact files exist in one period of one ledger.

    Sufficient on its own: a date is in yearly, or in monthly, or in daily, or it
    is not available. The newest daily entry is the newest day compacted, which
    is how a browser tells a day not yet compacted from a hole.
    """

    __schema_stem__: ClassVar[str] = "compact-index"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-01T16:50",
            change="Remove the retired aggregate from the ledger vocabulary.",
            why="Only declared families may reach an index; surviving periods are unchanged.",
        ),
        ChangelogEntry(
            version="2026-10-01",
            change="ledger may name summary-quality-evals, and scores is refused.",
            why="The eval ledger is named for what it holds; its files were rewritten.",
        ),
        ChangelogEntry(
            version="2026-09-30",
            change="period may be yearly, and each of its entries covers a UTC year.",
            why="A finished year's month files may be packed into one year file.",
        ),
        ChangelogEntry(
            version="2026-09-27",
            change="Initial shape: the compact files one period of one ledger holds.",
            why="A reader has to learn which days and months exist without listing a tree.",
        ),
    )

    ledger: LedgerName = Field(description="Which ledger the compact files belong to.")
    period: Period = Field(
        description=(
            "`daily`, `monthly` or `yearly`: how much time each listed file covers, and "
            "which of the ledger's compact directories this index describes."
        )
    )
    entries: list[CompactEntry] = Field(
        description=(
            "One entry per compact file, ascending by what it covers and none twice. "
            "Every entry covers one period of the kind `period` names."
        )
    )

    def to_json(self) -> str:
        """One entry a line - see `records_json`.

        A reader checks which days exist by scanning the list, and an entry's
        three fields mean nothing apart. The layout is not part of the shape, so
        a file in the older layout is still read and is re-laid-out when written.
        """
        return records_json(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def _the_entries_ascend_once_each_at_the_period_s_grain(self) -> Self:
        """A daily index lists days, a monthly one months and a yearly one years, in order."""
        where = f"the {self.ledger.value} {self.period.value} index"
        for entry in self.entries:
            if not covers_fits(entry.covers, tier=Tier.COMPACT, period=self.period):
                raise ValueError(
                    f"{where} holds an entry covering {entry.covers!r}, and every entry "
                    f"in it covers {_SHAPE[self.period]}"
                )
        covers = [entry.covers for entry in self.entries]
        repeated = _repeated(covers)
        if repeated:
            raise ValueError(f"{where} lists {repeated} more than once")
        descent = _first_descent(covers)
        if descent is not None:
            raise ValueError(
                f"{where} lists its entries out of order: {descent[0]!r} comes before "
                f"{descent[1]!r}, and what they cover must ascend"
            )
        return self


class Watermark(Contract):
    """How far one period of one ledger has been compacted.

    A producer file. It says where the next run resumes and nothing else.
    """

    __schema_stem__: ClassVar[str] = "watermark"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-01T16:50",
            change="Remove the retired aggregate from the ledger vocabulary.",
            why="Only declared families may reach a watermark; surviving periods are unchanged.",
        ),
        ChangelogEntry(
            version="2026-10-01",
            change="ledger may name summary-quality-evals, and scores is refused.",
            why="The eval ledger is named for what it holds; its files were rewritten.",
        ),
        ChangelogEntry(
            version="2026-09-30",
            change="period may be yearly, and through then stands on a UTC year.",
            why="A finished year's month files may be packed into one year file.",
        ),
        ChangelogEntry(
            version="2026-09-27",
            change="Initial shape: the newest period compacted, when, and by which run.",
            why="The next compaction has to know where to resume without reading the tree.",
        ),
    )

    ledger: LedgerName = Field(description="Which ledger this watermark belongs to.")
    period: Period = Field(
        description=(
            "`daily`, `monthly` or `yearly`: which of the ledger's compactions it tracks."
        )
    )
    through: PeriodStamp = Field(
        description=(
            "The newest period fully compacted: a UTC day on a daily watermark, a UTC "
            "month on a monthly one and a UTC year on a yearly one. The next run resumes "
            "after it."
        )
    )
    advanced_at: Timestamp = Field(
        description="When the watermark last moved, UTC, to the whole second."
    )
    run_id: RunId = Field(
        description=(
            "The run that moved it here, `<YYYY-MM-DD>-<execution>`. It outlives the "
            "record row that also names that run, because that row is pruned and this "
            "file is not."
        )
    )

    @model_validator(mode="after")
    def _through_is_at_the_period_s_grain(self) -> Self:
        """A daily watermark stands on a day, a monthly one on a month, a yearly one on a year."""
        if not covers_fits(self.through, tier=Tier.COMPACT, period=self.period):
            raise ValueError(
                f"the {self.ledger.value} {self.period.value} watermark stands at "
                f"{self.through!r}, and it must stand at {_SHAPE[self.period]}"
            )
        return self
