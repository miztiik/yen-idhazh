"""Where do a ledger's marks sit, how far do they say it is packed, and what does a pass adopt?

A ledger's marks are its three compact indexes. `name_marks` is the one place
their paths come from, so the listing a task is given and the pass that reads it
cannot disagree, and `work_out_marks` is the one place how far each period is
packed is worked out from them. `adopt` is the one place a packed file no entry
names becomes an entry again. Each test writes the indexes and files under
`tmp_path` as a compaction writes them and reads them through a real
`FileListing`, or hands `work_out_marks` periods written here as literals;
nothing reads the committed `state/` (CLAUDE.md section 13).
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener.file_listing import (
    FileListing,
    FileNotFetchedError,
    OverBudgetError,
    TreeEntry,
)
from idhazh.gardener.ledger_marks import adopt, name_marks, read_marks, work_out_marks
from idhazh.gardener.period_inputs import paths_for_task

pytestmark = pytest.mark.contract

WHICH: Final = LedgerName.VISUAL_PRUNES

#: The ledger's compact folder, as a repository path.
COMPACT: Final = "state/compact/visual-prunes"


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


def listed(root: Path) -> FileListing:
    """The ledger's compact folder, listed off the disk as a compaction's own folder is."""
    return FileListing.from_disk(root, [COMPACT], paths=[root / COMPACT])


def test_a_ledger_s_marks_are_its_three_indexes(tmp_path: Path) -> None:
    named = name_marks(state(tmp_path), WHICH)

    assert [(period, shown(tmp_path, named.indexes[period])) for period in Period] == [
        (Period.DAILY, f"{COMPACT}/index/daily.json"),
        (Period.MONTHLY, f"{COMPACT}/index/monthly.json"),
        (Period.YEARLY, f"{COMPACT}/index/yearly.json"),
    ]
    assert list(named) == list(named.indexes.values())


def test_a_ledger_nothing_has_packed_names_nothing(tmp_path: Path) -> None:
    marks = read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert marks.entries == {period: {} for period in Period}
    assert marks.indexed == frozenset()


def test_the_marks_say_what_each_index_lists_an_empty_one_included(tmp_path: Path) -> None:
    """The yearly index is the empty one a pass writes beside the daily one."""
    an_index(tmp_path, Period.DAILY, ["2026-09-01", "2026-09-02"])
    an_index(tmp_path, Period.MONTHLY, ["2026-08"])
    an_index(tmp_path, Period.YEARLY, [])

    marks = read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert {period: list(held) for period, held in marks.entries.items()} == {
        Period.DAILY: ["2026-09-01", "2026-09-02"],
        Period.MONTHLY: ["2026-08"],
        Period.YEARLY: [],
    }
    assert marks.entries[Period.MONTHLY]["2026-08"] == CompactEntry(
        covers="2026-08", rows=1, bytes=1
    )
    assert marks.indexed == frozenset(Period)


@pytest.mark.parametrize(
    ("daily", "monthly", "yearly", "through"),
    [
        ([], [], [], (None, None, None)),
        (["2026-09-01", "2026-09-02"], [], [], ("2026-09-02", None, None)),
        (["2026-09-01", "2026-09-02"], ["2026-08"], [], ("2026-09-02", "2026-08", None)),
        ([], ["2026-08", "2026-09"], [], ("2026-09-30", "2026-09", None)),
        ([], ["2028-02"], [], ("2028-02-29", "2028-02", None)),
        ([], [], ["2025"], ("2025-12-31", "2025-12", "2025")),
        (["2026-02-03"], ["2026-01"], ["2025"], ("2026-02-03", "2026-01", "2025")),
    ],
    ids=[
        "nothing",
        "days-alone",
        "days-after-a-closed-month",
        "a-closed-month-and-no-day-after-it",
        "a-leap-february",
        "a-packed-year-and-nothing-after-it",
        "a-year-then-a-month-then-a-day",
    ],
)
def test_each_mark_is_the_newest_period_its_index_or_a_coarser_one_covers(
    daily: list[str],
    monthly: list[str],
    yearly: list[str],
    through: tuple[str | None, str | None, str | None],
) -> None:
    """A closed month carries the daily mark to its last day, and a packed year both marks.

    So a ledger whose month step has just closed every day it packed still
    resumes the day after that month, and one with no index of a period, or of
    a coarser one, has no mark there.
    """
    marks = work_out_marks({Period.DAILY: daily, Period.MONTHLY: monthly, Period.YEARLY: yearly})

    assert (marks[Period.DAILY], marks[Period.MONTHLY], marks[Period.YEARLY]) == through


def test_the_listing_a_compaction_task_is_given_names_every_mark_its_pass_reads(
    tmp_path: Path,
) -> None:
    """A listing refuses a path no step named, so an unnamed mark would stop the pass."""
    policy = CompactionPolicy.model_validate_json(
        read_text(CONFIG_DIR / "gardener" / "compact-visual-prunes.json")
    )
    an_index(tmp_path, Period.DAILY, ["2026-09-02"])
    named = paths_for_task(
        tmp_path, "compact-visual-prunes", policy, ("2026-08", "2026-08"), today=date(2026, 9, 27)
    )
    listing = FileListing.from_disk(tmp_path, policy.claims(), paths=named)

    marks = read_marks(state(tmp_path), WHICH, listing)

    assert {period: list(held) for period, held in marks.entries.items()} == {
        Period.DAILY: ["2026-09-02"],
        Period.MONTHLY: [],
        Period.YEARLY: [],
    }
    assert marks.indexed == frozenset({Period.DAILY})


def test_an_index_that_describes_another_ledger_is_refused_by_name(tmp_path: Path) -> None:
    an_index(tmp_path, Period.DAILY, [], which=LedgerName.ITEM_HEALTH)

    with pytest.raises(ValueError) as refused:
        read_marks(state(tmp_path), WHICH, listed(tmp_path))

    assert str(refused.value) == "daily.json does not describe the visual-prunes daily period"


def test_the_marks_are_fetched_in_one_widening_and_no_packed_file_comes_with_them(
    tmp_path: Path,
) -> None:
    """The index folder comes whole, and never a period folder beside it.

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
        paths=held,
        widen=asked.append,
    )

    with pytest.raises(FileNotFetchedError, match=r"\(3 such files\)"):
        read_marks(state(tmp_path), WHICH, listing)

    assert asked == [[f"{COMPACT}/index"]]


# --- a packed file no entry names ---------------------------------------------------


def a_packed_day(root: Path, day: str, *, rows: int) -> Path:
    """One day's packed file, as a compaction writes it, holding `rows` rows filed through the door."""
    identity = WriterIdentity(
        run_id=f"{day}-1",
        attempt=1,
        job=ServerJob.RUN_TASKS,
        shard=0,
        producer="gardener.tasks.visual_prune",
        git_sha="a" * 40,
    )
    filed = [
        VisualPruneRow(
            version=VisualPruneRow.schema_version(),
            date=day,
            run_id=f"{day}-{number}",
            policy_months=-1,
            max_deletes_per_run=200,
            dry_run=True,
            candidates_found=0,
            deleted=0,
            skipped_by_fuse=0,
            fuse_tripped=False,
            bytes_reclaimed=0,
            oldest_kept=None,
            payload_bytes_before=number,
            payload_bytes_after=number,
        )
        for number in range(1, rows + 1)
    ]
    raw = ledger.persist(
        root / "scratch" / ledger.STATE_DIRNAME, filed, ledger=WHICH, covers=day, identity=identity
    )
    return ledger.persist_period(
        state(root),
        ledger.load_stored(raw, model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=WHICH,
        period=Period.DAILY,
        covers=day,
        identity=identity,
        built_from=len(raw),
    )


def test_a_packed_file_no_entry_names_is_adopted_with_its_footer_s_rows_and_its_listed_size(
    tmp_path: Path,
) -> None:
    written = a_packed_day(tmp_path, "2026-09-25", rows=2)

    held = adopt(listed(tmp_path), state(tmp_path), WHICH, Period.DAILY, "2026-09-25")

    assert held is not None
    assert held.path == written
    assert held.entry == CompactEntry(covers="2026-09-25", rows=2, bytes=written.stat().st_size)


def test_a_period_with_no_file_at_its_path_adopts_nothing(tmp_path: Path) -> None:
    a_packed_day(tmp_path, "2026-09-25", rows=1)

    assert adopt(listed(tmp_path), state(tmp_path), WHICH, Period.DAILY, "2026-09-24") is None


def test_a_file_whose_envelope_names_another_day_is_refused_and_never_adopted(
    tmp_path: Path,
) -> None:
    """Adopted, it would put the 25th's rows under the 26th."""
    written = a_packed_day(tmp_path, "2026-09-25", rows=1)
    shutil.copyfile(written, written.with_name("26.parquet"))

    with pytest.raises(ValueError) as refused:
        adopt(listed(tmp_path), state(tmp_path), WHICH, Period.DAILY, "2026-09-26")

    assert str(refused.value) == (
        "26.parquet sits where the visual-prunes daily file for 2026-09-26 goes, and its "
        "envelope says compact visual-prunes daily 2026-09-25, so it is not adopted"
    )


def test_adopting_a_file_spends_the_shard_s_download_budget_and_stops_past_it(
    tmp_path: Path,
) -> None:
    """Reading a day file's footer downloads its month's day files, so Rule R counts them too.

    The two day files weigh 1,100 bytes against a budget of 1,000, so the
    adoption is refused before the checkout widens, by a type a step stops at
    for a later wake rather than reading as a refused file.
    """
    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        [COMPACT],
        [
            TreeEntry(path=f"{COMPACT}/daily/2026/09/20.parquet", blob="1" * 40, size=600),
            TreeEntry(path=f"{COMPACT}/daily/2026/09/21.parquet", blob="2" * 40, size=500),
        ],
        {},
        paths=[f"{COMPACT}/daily/2026/09"],
        widen=asked.append,
        budget=1000,
    )

    with pytest.raises(OverBudgetError) as refused:
        adopt(listing, state(tmp_path), WHICH, Period.DAILY, "2026-09-20")

    assert (refused.value.needed, refused.value.budget) == (1100, 1000)
    assert asked == []


def test_marks_that_do_not_fit_what_is_left_of_the_budget_are_not_downloaded(
    tmp_path: Path,
) -> None:
    """A pass whose marks do not fit takes nothing until a later wake."""
    held = [shown(tmp_path, path) for path in name_marks(state(tmp_path), WHICH)]
    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        [COMPACT],
        [
            TreeEntry(path=path, blob=f"{number:040x}", size=100)
            for number, path in enumerate(held, start=1)
        ],
        {},
        paths=held,
        widen=asked.append,
        budget=299,
    )

    with pytest.raises(OverBudgetError) as refused:
        read_marks(state(tmp_path), WHICH, listing)

    assert refused.value.needed == 300
    assert asked == []
