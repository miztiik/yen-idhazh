"""Which members does a dated tree hold, read from a listing's names and never from the disk?

Each tree a gardener task keeps has a grammar: `YYYY/MM/DD.csv` day files, a
`YYYY/MM/DD/` folder of writer files, a published day's folder of pictures,
`YYYY-MM` month files, a trace under its day's folders, a ledger's raw day
folders. The walk that reads each grammar off the disk lives beside the
pipeline code that writes it. A gardener task reads the same grammar off the
names its `FileListing` holds, which is what lets it decide from a commit whose
files it never downloaded.

**Each function answers what its disk twin answers, and refuses what it
refuses.** The twin is named in each docstring, and
`backend/tests/gardener/test_named_trees.py` holds each pair equal over one
tree, strays included. A name git cannot hold - an empty folder - is the one
thing only the disk can show, and no task decides anything from one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn

from idhazh import day_partition, day_shards, ledger, month_partition
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing
from idhazh.ledger.paths import INDEX_DIRNAME
from idhazh.site_weight import SiteSize

logger = logging.getLogger(__name__)


def _below(listing: FileListing, root: Path) -> list[tuple[str, ...]]:
    """Every listed file under `root`, as its path segments below `root`, in path order."""
    base = len(root.relative_to(listing.repo_root).as_posix()) + 1
    return sorted(tuple(path[base:].split("/")) for path in listing.files_under(root))


def _real_day(year: str, month: str, day: str) -> bool:
    """Whether three segments spell a real calendar day in ASCII digits."""
    if not (
        day_partition.is_segment(year, day_partition.YEAR_WIDTH)
        and day_partition.is_segment(month, day_partition.SEGMENT_WIDTH)
        and day_partition.is_segment(day, day_partition.SEGMENT_WIDTH)
    ):
        return False
    try:
        date.fromisoformat(f"{year}-{month}-{day}")
    except ValueError:
        return False
    return True


def _refuse_a_shard(root: Path, parts: tuple[str, ...]) -> NoReturn:
    raise ValueError(
        f"{root.parent.name}/{root.name} holds {'/'.join(parts)}, which is not a file inside "
        "a YYYY/MM/DD day directory. A file the reader cannot place is how it starts missing "
        "rows, so it refuses the read rather than skipping the file."
    )


def shard_files(listing: FileListing, root: Path) -> Iterator[Path]:
    """Every writer file of a `YYYY/MM/DD/` day tree, oldest day first.

    The twin of `day_shards.shard_files(root, days=UNBOUNDED_WINDOW)`: a file
    that is not a `.csv` inside a real day's folder is refused. Like the twin,
    the whole tree is placed before its first file is handed on, so a stray
    anywhere stops the walk before it yields anything.
    """
    found: list[Path] = []
    for parts in _below(listing, root):
        if (
            len(parts) != 4
            or not _real_day(*parts[:3])
            or Path(parts[3]).suffix != day_shards.SUFFIX
        ):
            _refuse_a_shard(root, parts)
        found.append(root.joinpath(*parts))
    yield from found


def shards_by_month(listing: FileListing, root: Path) -> dict[str, list[Path]]:
    """Every writer file of a day tree, grouped by its month, oldest month first.

    The twin of `day_shards.shards_by_month(root, days=UNBOUNDED_WINDOW)`.
    """
    months: dict[str, list[Path]] = {}
    for shard in shard_files(listing, root):
        months.setdefault(day_shards.date_of(shard)[:7], []).append(shard)
    return months


def day_files(listing: FileListing, root: Path) -> Iterator[Path]:
    """Every `YYYY/MM/DD.csv` of a day-file tree, oldest first.

    The twin of `day_partition.day_files`: anything else under the root is
    refused, at the point the walk reaches it.
    """
    for parts in _below(listing, root):
        name = Path(parts[-1])
        if (
            len(parts) != 3
            or name.suffix != ".csv"
            or not _real_day(parts[0], parts[1], name.stem)
        ):
            raise ValueError(
                f"{root.parent.name}/{root.name} holds {'/'.join(parts)}, which is not a "
                "YYYY/MM/DD day file. A file the reader cannot place is how it starts missing "
                "rows, so it refuses the read rather than skipping the file."
            )
        yield root.joinpath(*parts)


@dataclass(frozen=True, slots=True)
class DatedDay:
    """One published day's folder, its date, and the files directly inside it, by name."""

    published: date
    folder: Path
    files: tuple[Path, ...]


def _refuse_a_dated(parts: tuple[str, ...], expected: str) -> NoReturn:
    raise ValueError(
        f"{'/'.join(parts)} is not a {expected} of the published day tree. Everything below a "
        "year directory here is written by assemble.day_dir, so a name this pass cannot read "
        "as a date means something else is writing there - and a cleanup that skipped it "
        "quietly would leave files nothing accounts for"
    )


def dated_days(
    listing: FileListing, root: Path, *, before: date | None = None
) -> Iterator[DatedDay]:
    """Every `YYYY/MM/DD/` day folder of a published tree, oldest first, read out of its name.

    The twin of `retention.dated_days`, with the files each day holds: at the
    root a name that is not a year is passed over; below a year a name that is
    not a month or a day is refused; a year or month that cannot hold a day
    before `before` is never looked inside, so nothing in it is refused either.
    """
    rows = _below(listing, root)
    for year_name in sorted({parts[0] for parts in rows if len(parts) > 1}):
        if not day_partition.is_segment(year_name, day_partition.YEAR_WIDTH):
            continue
        year = int(year_name)
        try:
            opens = date(year, 1, 1)
        except ValueError:
            continue
        if before is not None and opens >= before:
            continue
        in_year = [parts[1:] for parts in rows if parts[0] == year_name]
        for month_name in sorted({parts[0] for parts in in_year}):
            in_month = [parts[1:] for parts in in_year if parts[0] == month_name]
            if not day_partition.is_segment(month_name, day_partition.SEGMENT_WIDTH) or any(
                not parts for parts in in_month
            ):
                _refuse_a_dated((year_name, month_name), "month")
            month = int(month_name)
            if not 1 <= month <= 12:
                _refuse_a_dated((year_name, month_name), "month")
            if before is not None and date(year, month, 1) >= before:
                continue
            for day_name in sorted({parts[0] for parts in in_month}):
                in_day = [parts[1:] for parts in in_month if parts[0] == day_name]
                where = (year_name, month_name, day_name)
                if not day_partition.is_segment(day_name, day_partition.SEGMENT_WIDTH) or any(
                    not parts for parts in in_day
                ):
                    _refuse_a_dated(where, "day")
                try:
                    published = date(year, month, int(day_name))
                except ValueError:
                    _refuse_a_dated(where, "day")
                if before is None or published < before:
                    folder = root.joinpath(*where)
                    files = tuple(folder / parts[0] for parts in in_day if len(parts) == 1)
                    yield DatedDay(published=published, folder=folder, files=files)


def _visuals_in(day: DatedDay, without: Collection[Path] = ()) -> list[Path]:
    """The files of one published day named for an item, as `retention` reads a visual."""
    return [
        path
        for path in day.files
        if re.match(ITEM_ID_PATTERN, path.stem) and path not in without
    ]


def visuals_older_than(listing: FileListing, root: Path, limit: date) -> list[Path]:
    """Every picture in a day folder older than `limit`, in path order.

    The twin of `retention.visuals_older_than`.
    """
    return [path for day in dated_days(listing, root, before=limit) for path in _visuals_in(day)]


def oldest_visual(
    listing: FileListing, root: Path, *, without: Collection[Path] = ()
) -> date | None:
    """The published day of the oldest picture the tree holds, or None.

    The twin of `retention.oldest_visual`: it stops at that day, so nothing past
    it is looked at. `without` is what a pass has just deleted, which the
    listing, read before the pass, still names.
    """
    for day in dated_days(listing, root):
        if _visuals_in(day, without):
            return day.published
    return None


def measure(listing: FileListing, root: Path) -> SiteSize:
    """What a tree weighs, and under which of its top-level children.

    The twin of `site_weight.measure`, from the listing's sizes rather than the disk.
    """
    by_directory: dict[str, int] = {}
    files = 0
    for parts in _below(listing, root):
        by_directory[parts[0]] = by_directory.get(parts[0], 0) + listing.size_of(
            root.joinpath(*parts)
        )
        files += 1
    return SiteSize(sum(by_directory.values()), files, by_directory)


def month_files(listing: FileListing, folder: Path, suffix: str) -> list[Path]:
    """Every `<YYYY-MM><suffix>` directly inside one folder, oldest first, and nothing else.

    The twin of `month_partition.month_files`.
    """
    found = [
        folder / parts[0]
        for parts in _below(listing, folder)
        if len(parts) == 1
        and parts[0].endswith(suffix)
        and month_partition.is_month_stem(parts[0].removesuffix(suffix))
    ]
    return sorted(found, key=lambda path: path.name)


def files_named(listing: FileListing, root: Path, suffix: str | None = None) -> list[Path]:
    """Every file under `root`, or every one ending in `suffix`, in path order.

    For a tree whose members are dated by a rule over the whole path - a trace,
    a trial file - so the walk itself places nothing.
    """
    return [
        root.joinpath(*parts)
        for parts in _below(listing, root)
        if suffix is None or parts[-1].endswith(suffix)
    ]


def raw_days(listing: FileListing, state_dir: Path, which: LedgerName) -> list[str]:
    """Every UTC day a ledger has a raw folder with something in it for, oldest first.

    The twin of `ledger.raw_days`: the `index/` folder is passed over, and any
    other name that is not a `YYYY/MM/DD` folder is named in a warning.
    """
    root = ledger.raw_root(state_dir, which)
    days: set[str] = set()
    for parts in _below(listing, root):
        if parts[0] == INDEX_DIRNAME and len(parts) > 1:
            continue
        if (
            len(parts) > 3
            and day_partition.is_segment(parts[0], day_partition.YEAR_WIDTH)
            and day_partition.is_segment(parts[1], day_partition.SEGMENT_WIDTH)
            and day_partition.is_segment(parts[2], day_partition.SEGMENT_WIDTH)
        ):
            days.add(f"{parts[0]}-{parts[1]}-{parts[2]}")
            continue
        logger.warning(
            "skipped a raw file path=%s reason=not inside a YYYY/MM/DD folder",
            root.joinpath(*parts).relative_to(listing.repo_root).as_posix(),
        )
    return sorted(days)


def listed_days(listing: FileListing, state_dir: Path, which: LedgerName) -> list[str]:
    """Every UTC day a raw listing of this ledger sits under `index/` for, oldest first.

    The twin of `ledger.listed_days`: a name that is not a `<YYYY-MM-DD>.json`
    listing is left out with a warning.
    """
    folder = ledger.raw_root(state_dir, which) / INDEX_DIRNAME
    found: list[str] = []
    for parts in _below(listing, folder):
        path = folder.joinpath(*parts)
        try:
            if (
                len(parts) != 1
                or path.suffix != ".json"
                or ledger.raw_index_path(state_dir, which, path.stem) != path
            ):
                raise ValueError("not a day's listing")
        except ValueError as refusal:
            logger.warning(
                "skipped a raw file path=%s reason=%s",
                path.relative_to(listing.repo_root).as_posix(),
                refusal,
            )
            continue
        found.append(path.stem)
    return found


def compact_file(
    listing: FileListing, state_dir: Path, which: LedgerName, period: Period, covers: str
) -> Path | None:
    """The compact file of one period, whichever format wrote it, or None when there is none.

    The twin of `ledger.compact_file`.
    """
    for fmt in Format:
        found = ledger.compact_path(state_dir, which, period, covers, fmt=fmt)
        if listing.holds(found):
            return found
    return None
