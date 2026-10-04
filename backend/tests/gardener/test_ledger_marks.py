"""Does a ledger's marks name the six files a pass reads, read them once, and refuse one it cannot trust?

A ledger's marks are its three compact indexes and its three watermarks.
`name_marks` is the one place their paths come from, so the listing a task is
given and the pass that reads it cannot disagree. Each test writes the marks
under `tmp_path` as a compaction writes them and reads them through a real
`FileListing`; nothing reads the committed `state/` (CLAUDE.md section 13).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing, FileNotFetchedError, TreeEntry
from idhazh.gardener.ledger_marks import name_marks, read_marks

pytestmark = pytest.mark.contract

WHICH: Final = LedgerName.VISUAL_PRUNES

#: The ledger's compact folder, as a repository path.
COMPACT: Final = "state/compact/visual-prunes"

#: The newest period each watermark these tests write says is packed.
THROUGH: Final = {Period.DAILY: "2026-09-02", Period.MONTHLY: "2026-08", Period.YEARLY: "2025"}


def state(root: Path) -> Path:
    return root / ledger.STATE_DIRNAME


def shown(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def an_index(
    root: Path, period: Period, covers: Sequence[str], *, which: LedgerName = WHICH
) -> None:
    """One period's index naming these periods, as a compaction writes it."""
    held = CompactIndex(
        version=CompactIndex.schema_version(),
        ledger=which,
        period=period,
        entries=[CompactEntry(covers=each, rows=1, bytes=1) for each in covers],
    )
    path = ledger.compact_index_path(state(root), WHICH, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(held.to_json().encode("ascii"))


def a_watermark(root: Path, period: Period, *, says: Period | None = None) -> None:
    """One period's watermark, as a compaction writes it, or another period's in its place."""
    written = says or period
    mark = Watermark(
        version=Watermark.schema_version(),
        ledger=WHICH,
        period=written,
        through=THROUGH[written],
        advanced_at="2026-09-03T00:41:00Z",
        run_id="2026-09-03-1",
    )
    path = ledger.watermark_path(state(root), WHICH, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mark.to_json().encode("ascii"))


def listed(root: Path) -> FileListing:
    """The ledger's compact folder, listed off the disk as a compaction's own folder is."""
    return FileListing.from_disk(root, [COMPACT], paths=[root / COMPACT])


def test_a_ledger_s_marks_are_its_three_indexes_and_its_three_watermarks(tmp_path: Path) -> None:
    named = name_marks(state(tmp_path), WHICH)

    by_period = [
        (period, shown(tmp_path, named.indexes[period]), shown(tmp_path, named.watermarks[period]))
        for period in Period
    ]
    assert by_period == [
        (Period.DAILY, f"{COMPACT}/index/daily.json", f"{COMPACT}/daily/watermark.json"),
        (Period.MONTHLY, f"{COMPACT}/index/monthly.json", f"{COMPACT}/monthly/watermark.json"),
        (Period.YEARLY, f"{COMPACT}/index/yearly.json", f"{COMPACT}/yearly/watermark.json"),
    ]
    assert list(named) == [*named.indexes.values(), *named.watermarks.values()]


def test_a_ledger_nothing_has_packed_reads_as_no_period_packed(tmp_path: Path) -> None:
    marks = read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert marks.through == dict.fromkeys(Period)
    assert marks.entries == {period: {} for period in Period}
    assert marks.indexed == frozenset()


def test_the_marks_say_how_far_each_period_is_packed_and_what_each_index_lists(
    tmp_path: Path,
) -> None:
    """The yearly index is the empty one a pass writes beside the daily one, with no watermark."""
    an_index(tmp_path, Period.DAILY, ["2026-09-01", "2026-09-02"])
    a_watermark(tmp_path, Period.DAILY)
    an_index(tmp_path, Period.MONTHLY, ["2026-08"])
    a_watermark(tmp_path, Period.MONTHLY)
    an_index(tmp_path, Period.YEARLY, [])

    marks = read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert marks.through == {**THROUGH, Period.YEARLY: None}
    assert {period: list(held) for period, held in marks.entries.items()} == {
        Period.DAILY: ["2026-09-01", "2026-09-02"],
        Period.MONTHLY: ["2026-08"],
        Period.YEARLY: [],
    }
    assert marks.entries[Period.MONTHLY]["2026-08"] == CompactEntry(
        covers="2026-08", rows=1, bytes=1
    )
    assert marks.indexed == frozenset(Period)


@pytest.mark.parametrize("period", list(Period))
def test_an_index_its_watermark_says_was_packed_that_is_not_there_is_refused_as_index_missing(
    tmp_path: Path, period: Period
) -> None:
    """Read as empty, the index would be rewritten naming only what this pass packs."""
    a_watermark(tmp_path, period)

    with pytest.raises(ValueError) as refused:
        read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert str(refused.value) == (
        f"index-missing: {COMPACT}/index/{period.value}.json is not there, and watermark.json "
        f"says the {period.value} period is packed through {THROUGH[period]}. Restore "
        f"{period.value}.json from git history before the next wake; an empty one would "
        "forget every period packed before"
    )


def test_a_watermark_that_describes_another_period_is_refused_by_name(tmp_path: Path) -> None:
    an_index(tmp_path, Period.DAILY, [])
    a_watermark(tmp_path, Period.DAILY, says=Period.MONTHLY)

    with pytest.raises(ValueError) as refused:
        read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert str(refused.value) == "watermark.json does not describe the visual-prunes daily period"


def test_an_index_that_describes_another_ledger_is_refused_by_name(tmp_path: Path) -> None:
    an_index(tmp_path, Period.DAILY, [], which=LedgerName.ITEM_HEALTH)

    with pytest.raises(ValueError) as refused:
        read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert str(refused.value) == "daily.json does not describe the visual-prunes daily period"


def test_the_marks_are_fetched_in_one_widening_and_no_packed_file_comes_with_them(
    tmp_path: Path,
) -> None:
    """The index folder comes whole and each watermark by itself, never the folder beside it.

    Nothing widens this checkout, so each file the widening was meant to bring is
    still absent afterwards and the read fails, naming how many there were.
    """
    packed = [
        f"{COMPACT}/daily/2026/09/01.parquet",
        f"{COMPACT}/monthly/2026/08.parquet",
        f"{COMPACT}/yearly/2025/2025.parquet",
    ]
    held = [*(shown(tmp_path, path) for path in name_marks(state(tmp_path), WHICH)), *packed]
    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        [COMPACT],
        [
            TreeEntry(path=path, blob=f"{number:040x}", size=1)
            for number, path in enumerate(held, start=1)
        ],
        {},
        widen=asked.append,
    )

    with pytest.raises(FileNotFetchedError, match=r"\(6 such files\)"):
        read_marks(state(tmp_path), WHICH, listing)

    assert asked == [
        [
            f"{COMPACT}/index",
            f"{COMPACT}/daily/watermark.json",
            f"{COMPACT}/monthly/watermark.json",
            f"{COMPACT}/yearly/watermark.json",
        ]
    ]
