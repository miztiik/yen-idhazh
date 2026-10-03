"""Does each walk over a listing's names answer what its disk twin answers, strays included?

A gardener task reads its trees off the names a `FileListing` holds, so a task
decides from a commit whose files it never downloaded. Each walk in
`idhazh.gardener.named_trees` has a twin that reads the disk, and the task it
serves was proved against that twin. So each pair runs here over one tree on
disk, listed from that disk: the members, their order, and the point a stray
stops the walk have to be the same.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_shards, ledger, month_partition, retention
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import named_trees
from idhazh.gardener.file_listing import FileListing
from idhazh.site_weight import measure

pytestmark = pytest.mark.contract

#: A ledger whose raw and compact folders the door names, for the two raw walks.
RAW: Final = LedgerName.ITEM_HEALTH


def plant(root: Path, files: Iterable[str]) -> Path:
    """Every named file under `root`, each holding its own name, so sizes differ."""
    for relative in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="ascii", newline="\n")
    return root


def walked[T](walk: Callable[[], Iterable[T]]) -> tuple[list[T], bool]:
    """What a walk handed on, and whether it then refused."""
    got: list[T] = []
    try:
        for item in walk():
            got.append(item)
    except ValueError:
        return got, True
    return got, False


def listing_of(repo: Path, folder: str) -> FileListing:
    return FileListing.from_disk(repo, [folder])


SHARD_TREES: Final = {
    "clean": [
        "2025/12/31/x.csv",
        "2026/08/settled.csv",
        "2026/08/31/late.csv",
        "2026/09/01/b.csv",
        "2026/09/01/a.csv",
        "2026/09/02/settled.csv",
    ],
    "a text file in a day": ["2026/09/01/a.csv", "2026/09/02/a.csv", "2026/09/02/notes.txt"],
    "a day that is no day": ["2026/09/01/a.csv", "2026/09/31/a.csv"],
    "a month that is no month": ["2026/09/01/a.csv", "2026/13/01/a.csv"],
    "a file where a day belongs": ["2026/09/01/a.csv", "2026/09/02.csv"],
    "a file at the root": ["2026/09/01/a.csv", "README"],
    "a folder in a day": ["2026/09/01/a.csv", "2026/09/02/deep/a.csv"],
    "a settled month that is no month": ["2026/09/01/a.csv", "2026/13/settled.csv"],
    "a settled file where a month belongs": ["2026/09/01/a.csv", "2026/settled.csv"],
}


@pytest.mark.parametrize("shape", sorted(SHARD_TREES))
def test_the_writer_files_of_a_day_tree_are_the_disk_walks(tmp_path: Path, shape: str) -> None:
    """A closed month's own settled file is a member of both walks, beside its days."""
    root = plant(tmp_path / "state" / "summary-quality-evals-index", SHARD_TREES[shape])
    listing = listing_of(tmp_path, "state/summary-quality-evals-index")

    on_disk = walked(lambda: day_shards.shard_files(root, days=UNBOUNDED_WINDOW))
    by_name = walked(lambda: named_trees.shard_files(listing, root))

    assert by_name == on_disk
    assert on_disk[1] is (shape != "clean"), "the tree does not exercise what it is named for"


PUBLISHED: Final = [
    "index.html",
    "assets/app.js",
    "2026/10/19/digest.json",
    "2026/10/19/ai-0001.json",
    "2026/10/19/ai-0002.json",
    "2026/10/20/ai-0003.json",
    "2026/10/20/charts/ai-0009.json",
    "2026/10/21/run.json",
    "2027/11/15/ai-0005.json",
    "2027/11/15/digest.json",
]
STRAYS: Final = {
    "clean": [],
    "a month that is no month": ["2026/13/01/ai-0001.json"],
    "a day that is no day": ["2026/10/32/ai-0001.json"],
    "a file where a month belongs": ["2026/notes.txt"],
    "a stray in a year the cutoff never opens": ["2028/xx/01/ai-0001.json"],
}


@pytest.mark.parametrize("stray", sorted(STRAYS))
@pytest.mark.parametrize("before", [None, date(2026, 10, 21), date(2027, 1, 1)])
def test_the_days_of_a_published_tree_are_the_disk_walks(
    tmp_path: Path, stray: str, before: date | None
) -> None:
    root = plant(tmp_path / "frontend" / "public" / "digest", [*PUBLISHED, *STRAYS[stray]])
    listing = listing_of(tmp_path, "frontend/public/digest")

    on_disk = walked(
        lambda: [
            (published, folder, tuple(path for path in sorted(folder.iterdir()) if path.is_file()))
            for published, folder in retention.dated_days(root, before=before)
        ]
    )
    by_name = walked(
        lambda: [
            (day.published, day.folder, day.files)
            for day in named_trees.dated_days(listing, root, before=before)
        ]
    )

    assert by_name == on_disk


@pytest.mark.parametrize("limit", [date(2026, 10, 20), date(2026, 10, 21), date(2028, 1, 1)])
def test_the_pictures_past_a_cutoff_and_the_oldest_one_are_the_disk_walks(
    tmp_path: Path, limit: date
) -> None:
    root = plant(tmp_path / "frontend" / "public" / "digest", PUBLISHED)
    listing = listing_of(tmp_path, "frontend/public/digest")

    assert named_trees.visuals_older_than(listing, root, limit) == retention.visuals_older_than(
        root, limit
    )
    assert named_trees.oldest_visual(listing, root) == retention.oldest_visual(root)


def test_the_oldest_picture_leaves_out_what_a_pass_just_deleted(tmp_path: Path) -> None:
    """The listing is read before the pass, so it still names a picture the pass took."""
    root = plant(tmp_path / "frontend" / "public" / "digest", PUBLISHED)
    listing = listing_of(tmp_path, "frontend/public/digest")
    taken = {root / "2026/10/19/ai-0001.json", root / "2026/10/19/ai-0002.json"}
    for path in taken:
        path.unlink()

    assert named_trees.oldest_visual(listing, root, without=taken) == retention.oldest_visual(root)


def test_a_trees_weight_is_the_disk_walks(tmp_path: Path) -> None:
    root = plant(tmp_path / "frontend" / "public" / "digest", PUBLISHED)
    listing = listing_of(tmp_path, "frontend/public/digest")

    assert named_trees.measure(listing, root) == measure(root)


def test_the_month_files_of_a_folder_are_the_disk_walks(tmp_path: Path) -> None:
    folder = plant(
        tmp_path / "state" / "item-health-summary",
        [
            "2026-09.csv",
            "2026-08.csv",
            "notes.csv",
            "2026-13.csv",
            "2026-09.json",
            "older/2026-07.csv",
        ],
    )
    listing = listing_of(tmp_path, "state/item-health-summary")

    for suffix in (".csv", ".json"):
        assert named_trees.month_files(listing, folder, suffix) == month_partition.month_files(
            folder, suffix
        )


def test_every_file_under_a_tree_is_the_disk_walks(tmp_path: Path) -> None:
    root = plant(
        tmp_path / "state" / "traces",
        ["2026/09/01/0001-0.jsonl", "2026/09/01/notes.txt", "2026/08/31/0002-0.jsonl", "loose.jsonl"],
    )
    listing = listing_of(tmp_path, "state/traces")

    assert named_trees.files_named(listing, root, ".jsonl") == sorted(root.rglob("*.jsonl"))
    assert named_trees.files_named(listing, root) == sorted(
        path for path in root.rglob("*") if path.is_file()
    )


def test_a_ledgers_raw_days_and_listings_are_the_disk_walks(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    raw = ledger.raw_root(state, RAW)
    plant(
        raw,
        [
            "2026/09/29/a.parquet",
            "2026/09/29/b.parquet",
            "2026/09/30/c.parquet",
            "2026/10/01/deeper/d.parquet",
            "index/2026-09-27.json",
            "index/2026-09-28.json",
            "index/notes.txt",
            "index/2026-13-01.json",
            "junk.txt",
            "2026/09/stray.parquet",
        ],
    )
    listing = listing_of(tmp_path, raw.relative_to(tmp_path).as_posix())

    assert named_trees.raw_days(listing, state, RAW) == ledger.raw_days(state, RAW)
    assert named_trees.listed_days(listing, state, RAW) == ledger.listed_days(state, RAW)


def test_a_compact_file_is_found_by_the_name_the_disk_finds(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    daily = ledger.compact_path(state, RAW, Period.DAILY, "2026-09-01")
    plant(tmp_path, [daily.relative_to(tmp_path).as_posix()])
    compact = daily.relative_to(tmp_path).parents[3].as_posix()
    listing = listing_of(tmp_path, compact)

    for covers in ("2026-09-01", "2026-09-02"):
        assert named_trees.compact_file(
            listing, state, RAW, Period.DAILY, covers
        ) == ledger.compact_file(state, RAW, Period.DAILY, covers)


def an_index(state: Path, period: Period, covers: Iterable[str]) -> None:
    """One compact index naming these periods, as the compaction writes it."""
    held = CompactIndex(
        version=CompactIndex.schema_version(),
        ledger=RAW,
        period=period,
        entries=[CompactEntry(covers=each, rows=1, bytes=1) for each in covers],
    )
    path = ledger.compact_index_path(state, RAW, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(held.to_json(), encoding="ascii", newline="\n")


def test_the_months_a_ledger_holds_are_the_ones_its_indexes_and_raw_folders_name(
    tmp_path: Path,
) -> None:
    """A year only in a year file, one month only in a month file, one only in day
    files, one only in raw days.

    The door reads the three indexes; the names give the same months from the
    files those indexes list, and a raw `index/` folder of listings names no month.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    compact = {
        ledger.compact_path(state, RAW, Period.YEARLY, "2025"),
        ledger.watermark_path(state, RAW, Period.YEARLY),
        ledger.compact_path(state, RAW, Period.MONTHLY, "2026-07"),
        ledger.compact_path(state, RAW, Period.DAILY, "2026-08-01"),
        ledger.compact_path(state, RAW, Period.DAILY, "2026-08-02"),
        ledger.watermark_path(state, RAW, Period.DAILY),
    }
    raw = ledger.raw_root(state, RAW)
    plant(
        tmp_path,
        [
            *(path.relative_to(tmp_path).as_posix() for path in compact),
            (raw / "2026/09/29/a.parquet").relative_to(tmp_path).as_posix(),
            (raw / "index/2025-12-31.json").relative_to(tmp_path).as_posix(),
        ],
    )
    an_index(state, Period.YEARLY, ["2025"])
    an_index(state, Period.MONTHLY, ["2026-07"])
    an_index(state, Period.DAILY, ["2026-08-01", "2026-08-02"])
    compacted = ledger.watermark_path(state, RAW, Period.DAILY).parent.parent
    listing = FileListing.from_disk(
        tmp_path, [raw.relative_to(tmp_path).as_posix(), compacted.relative_to(tmp_path).as_posix()]
    )

    year = [f"2025-{number:02d}" for number in range(1, 13)]
    assert ledger.held_months(state, RAW) == [*year, "2026-07", "2026-08", "2026-09"]
    assert named_trees.held_months(listing, state, RAW) == ledger.held_months(state, RAW)
