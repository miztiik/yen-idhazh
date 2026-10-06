"""Which members does a dated tree hold, read from a listing's names and never from the disk?

Each tree a gardener task keeps has a grammar: a `YYYY/MM/DD/` folder of writer
files beside a closed month's own `settled.csv`, a published day's folder of
pictures, `YYYY-MM` month files, a trace under its day's folders, a ledger's raw
day folders. The walk that reads each grammar off the disk lives beside the
pipeline code that writes it. A gardener task reads the same grammar off the
names its `FileListing` holds, which is what lets it decide from a commit whose
files it never downloaded.

**Each function answers what its disk twin answers, and refuses what it
refuses.** The twin is named in each docstring, and
`backend/tests/gardener/test_named_trees.py` holds each pair equal over one
tree, strays included. A name git cannot hold - an empty folder - is the one
thing only the disk can show, and no task decides anything from one.

**A walk covers the periods the listing names under its root.** A wake names
the day and month folders each task reads, so a walk over a tree's root answers
for those periods and says nothing of the rest of the tree. It reads through
`FileListing.named_files`, which says so by its name, never through
`files_under`, which refuses a folder no step named. Over a listing that names
the whole root, as the twin tests build, the walk is the disk walk.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn

from idhazh import day_partition, day_shards, ledger, month_partition
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing
from idhazh.site_weight import SiteSize

logger = logging.getLogger(__name__)


def _below(
    listing: FileListing, root: Path, folders: Iterable[Path] | None = None
) -> list[tuple[str, ...]]:
    """Every listed file inside the periods named under `root`, as segments below it, in order.

    With `folders`, every file under those named folders of `root` alone.
    """
    base = len(root.relative_to(listing.repo_root).as_posix()) + 1
    files = (
        listing.named_files(root)
        if folders is None
        else [path for folder in folders for path in listing.files_under(folder)]
    )
    return sorted(tuple(path[base:].split("/")) for path in files)


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
        "a YYYY/MM/DD day directory, nor a closed month's settled.csv. A file the reader "
        "cannot place is how it starts missing rows, so it refuses the read rather than "
        "skipping the file."
    )


def shard_files(listing: FileListing, root: Path) -> Iterator[Path]:
    """Every writer file of a `YYYY/MM/DD/` day tree, and each settled month's file, oldest first.

    The twin of `day_shards.shard_files(root, days=UNBOUNDED_WINDOW)`: a file
    that is neither a `.csv` inside a real day's folder nor a `settled.csv`
    directly inside a real month's folder is refused. Like the twin, the whole
    tree is placed before its first file is handed on, so a stray anywhere stops
    the walk before it yields anything.
    """
    found: list[Path] = []
    for parts in _below(listing, root):
        settled_month = (
            len(parts) == 3
            and parts[2] == day_shards.SETTLED_NAME
            and _real_day(parts[0], parts[1], "01")
        )
        if not settled_month and (
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
    listing: FileListing, root: Path, days: Iterable[date]
) -> Iterator[DatedDay]:
    """Every `YYYY/MM/DD/` day folder of a published tree, oldest first, read out of its name.

    The twin of `retention.dated_days`, with the files each day holds: at the
    root a name that is not a year is passed over; below a year a name that is
    not a month or a day is refused; a year or month that cannot hold a day
    before `before` is never looked inside, so nothing in it is refused either.
    """
    for published in sorted(set(days)):
        folder = root / f"{published:%Y}" / f"{published:%m}" / f"{published:%d}"
        files = tuple(
            listing.repo_root / path
            for path in listing.files_under(folder)
            if Path(path).parent.as_posix() == folder.relative_to(listing.repo_root).as_posix()
        )
        if files:
            yield DatedDay(published=published, folder=folder, files=files)


def _visuals_in(day: DatedDay, without: Collection[Path] = ()) -> list[Path]:
    """The files of one published day named for an item, as `retention` reads a visual."""
    return [
        path
        for path in day.files
        if re.match(ITEM_ID_PATTERN, path.stem) and path not in without
    ]


def visuals_older_than(
    listing: FileListing, root: Path, days: Iterable[date]
) -> list[Path]:
    """Every picture in a day folder older than `limit`, in path order.

    The twin of `retention.visuals_older_than`.
    """
    return [path for day in dated_days(listing, root, days) for path in _visuals_in(day)]


def oldest_visual(
    listing: FileListing, root: Path, day: date, *, without: Collection[Path] = ()
) -> date | None:
    """The published day of the oldest picture the tree holds, or None.

    The twin of `retention.oldest_visual`: it stops at that day, so nothing past
    it is looked at. `without` is what a pass has just deleted, which the
    listing, read before the pass, still names.
    """
    folder = root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    files = tuple(
        listing.repo_root / path
        for path in listing.files_under(folder)
        if Path(path).parent.as_posix() == folder.relative_to(listing.repo_root).as_posix()
    )
    return day if _visuals_in(DatedDay(day, folder, files), without) else None


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


def measure_days(listing: FileListing, root: Path, days: Iterable[date]) -> int:
    """The bytes in these named days, including every file inside each day."""
    return sum(
        listing.size_of(path)
        for day in sorted(set(days))
        for path in listing.files_under(root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}")
    )


def month_files(
    listing: FileListing, folder: Path, suffix: str, months: Iterable[str]
) -> list[Path]:
    """Every `<YYYY-MM><suffix>` directly inside one folder, oldest first, and nothing else.

    The twin of `month_partition.month_files`.
    """
    found = [
        folder / f"{month}{suffix}"
        for month in sorted(set(months))
        if month_partition.is_month_stem(month)
        and listing.holds(folder / f"{month}{suffix}")
    ]
    return found


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


def raw_days(
    listing: FileListing,
    state_dir: Path,
    which: LedgerName,
    *,
    months: Iterable[str] | None = None,
) -> list[str]:
    """Every UTC day a ledger has a raw folder with something in it for, oldest first.

    The twin of `ledger.raw_days`, over the periods the listing names under the
    raw root, or over these months' folders alone, each one a step named: a
    name that is not a `YYYY/MM/DD` folder is named in a warning.
    """
    root = ledger.raw_root(state_dir, which)
    folders = (
        None
        if months is None
        else [root.joinpath(month[:4], month[5:7]) for month in sorted(set(months))]
    )
    days: set[str] = set()
    for parts in _below(listing, root, folders):
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


def held_months(listing: FileListing, state_dir: Path, which: LedgerName) -> list[str]:
    """Every UTC month a ledger may hold a row in, oldest first, from file names alone.

    The twin of `ledger.held_months`, which reads the three compact indexes: here
    the months come from the names of the compact files those indexes list and
    of the raw day folders, so no file is opened. A month named only by a compact
    file, or only by a raw day, is held either way, and a year file names all
    twelve of its months.
    """
    months = {day[:7] for day in raw_days(listing, state_dir, which)}
    shapes = {Period.DAILY: 3, Period.MONTHLY: 2, Period.YEARLY: 2}
    for period, depth in shapes.items():
        folder = ledger.compact_root(state_dir, which, period)
        for parts in _below(listing, folder):
            if len(parts) != depth:
                continue
            stem = Path(parts[-1]).stem
            covers = stem if period is Period.YEARLY else "-".join((*parts[:-1], stem))
            try:
                found = compact_file(listing, state_dir, which, period, covers)
            except ValueError:
                continue
            if found is None:
                continue
            if period is Period.YEARLY:
                months.update(f"{covers}-{number:02d}" for number in range(1, 13))
            else:
                months.add(covers[:7])
    return sorted(months)
