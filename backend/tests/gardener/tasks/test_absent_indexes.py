"""Where does a compaction look when one of a ledger's indexes is absent, and what does it adopt?

The unit cases ask `_absent_indexes` which periods it looks at, over indexes
written here as literals and a wake's day the test sets. The naming cases
rebuild a ledger built under `tmp_path` over a wake's listing and read which
folders the rebuild named: one a year. The integration cases run the shipped
compaction over a ledger built under `tmp_path` with the helpers in
`_task.py`: an index is removed and the files it named are kept, as a restore
from an older commit or a deleted file leaves them. Nothing reads the
committed `state/` or a clock the test did not set (CLAUDE.md sections 2 and 13).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import ledger, month_partition
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.gardener.file_listing import FileListing, OverBudgetError, TreeEntry
from idhazh.gardener.tasks import _absent_indexes
from idhazh.gardener.tasks._compact_tree import CompactTree

from ._task import context_for, declared
from .test_compaction import (
    VISUALS,
    a_month_file,
    a_packed_file,
    a_packed_month,
    a_pass,
    an_index,
    compact,
    filed,
    files_under,
    index_of,
    quiet_days,
    recovered,
    state,
)

pytestmark = pytest.mark.contract

#: The ledger every case builds, and what packs it.
TASK: Final = "compact-visual-prunes"

#: The ledger's compact folder, as a repository path.
COMPACT: Final = "state/compact/visual-prunes"

#: The ledger's raw folder, as a repository path.
RAW: Final = "state/raw/visual-prunes"

#: The first year a ledger can hold, as `config/idhazh_gardener.json` says it.
FIRST_YEAR: Final = "2026"


def at(day: date) -> datetime:
    """00:00 UTC on a wake's day, the instant every rule counts from."""
    return datetime.combine(day, time.min, tzinfo=UTC)


def policy_of(**changed: object) -> CompactionPolicy:
    held = declared()[TASK]
    assert isinstance(held, CompactionPolicy)
    return CompactionPolicy.model_validate({**held.model_dump(mode="json"), **changed})


def indexed(*, monthly: Sequence[str] = (), yearly: Sequence[str] = ()) -> CompactTree:
    """A ledger's indexes as a pass reads them, with no file behind them: choosing reads none."""
    return CompactTree(
        state_dir=Path("state"),
        ledger=VISUALS,
        listing=FileListing.from_paths(Path(), [], folders=["state"]),
        daily={},
        monthly={month: CompactEntry(covers=month, rows=1, bytes=1) for month in monthly},
        yearly={year: CompactEntry(covers=year, rows=1, bytes=1) for year in yearly},
        raw_days=[],
    )


# --- where it looks: unit cases ----------------------------------------------------

#: The smallest waits the declaration contract allows that pack years.
PACKS_YEARS: Final[dict[str, object]] = {
    "daily_keep_days": 31,
    "monthly_window": {"unit": "forever"},
    "monthly_keep_days": 63,
}


def test_years_run_from_the_first_ledger_year_to_the_newest_one_old_enough_to_pack() -> None:
    """2027 ended at 00:00 UTC on 1 January 2028, and 63 days later is 4 March."""
    policy = policy_of(**PACKS_YEARS)

    on_the_day = _absent_indexes.pick_years(
        policy, now=at(date(2028, 3, 4)), first_ledger_year=FIRST_YEAR
    )
    the_day_before = _absent_indexes.pick_years(
        policy, now=at(date(2028, 3, 3)), first_ledger_year=FIRST_YEAR
    )

    assert (on_the_day, the_day_before) == (["2026", "2027"], ["2026"])


def test_a_declaration_that_packs_no_year_looks_for_no_year_file() -> None:
    years = _absent_indexes.pick_years(
        policy_of(), now=at(date(2030, 1, 1)), first_ledger_year=FIRST_YEAR
    )

    assert years == []


@pytest.mark.parametrize(
    ("changed", "yearly", "first"),
    [
        ({"dry_run": False}, (), "2026-10"),
        ({"dry_run": False, "month_deletes_dry_run": True}, (), "2026-01"),
        ({"dry_run": True}, (), "2026-01"),
        ({**PACKS_YEARS, "dry_run": False}, ("2026",), "2027-01"),
        ({**PACKS_YEARS, "dry_run": False}, (), "2026-01"),
    ],
    ids=[
        "a-live-window",
        "a-window-that-only-reports",
        "a-whole-dry-run",
        "kept-for-ever-after-a-year",
        "kept-for-ever",
    ],
)
def test_months_run_to_the_newest_that_may_close_from_where_a_kept_month_can_be(
    changed: dict[str, object], yearly: tuple[str, ...], first: str
) -> None:
    """On 16 December 2027 the newest month old enough to close is October 2027.

    A 13-month window whose deletes are live keeps October 2026 on. One that
    only reports keeps every month, as a window kept for ever does, and so does
    a task that is a dry run, which deletes nothing, so the months start at the
    January after the newest packed year, or at the first ledger year's.
    """
    months = _absent_indexes.pick_months(
        indexed(yearly=yearly),
        policy_of(**changed),
        now=at(date(2027, 12, 16)),
        first_ledger_year=FIRST_YEAR,
    )

    assert months == month_partition.months_between(first, "2027-10")


def test_days_run_from_the_month_after_the_monthly_mark_to_the_newest_due_day() -> None:
    days = _absent_indexes.pick_days(
        indexed(monthly=("2026-08",)),
        policy_of(),
        now=at(date(2026, 10, 4)),
        operator_range=None,
        first_ledger_year=FIRST_YEAR,
    )

    assert (days[0], days[-1], len(days)) == ("2026-09-01", "2026-10-02", 32)


@pytest.mark.parametrize(
    ("operator", "first"),
    [(None, "2026-08-01"), (("2026-05", "2026-05"), "2026-05-01"), (("2026-09", "2026-09"), "2026-08-01")],
    ids=["no-range", "a-range-further-back", "a-range-inside-the-look-back"],
)
def test_with_no_monthly_mark_days_run_from_the_first_run_s_look_back_and_a_range_never_narrows_it(
    operator: tuple[str, str] | None, first: str
) -> None:
    """A rebuilt index is written whole, so a day a range left out would be left out for ever."""
    days = _absent_indexes.pick_days(
        indexed(),
        policy_of(lookback=2),
        now=at(date(2026, 10, 4)),
        operator_range=operator,
        first_ledger_year=FIRST_YEAR,
    )

    assert (days[0], days[-1]) == (first, "2026-10-02")


def test_no_day_is_looked_at_from_before_the_first_ledger_year() -> None:
    days = _absent_indexes.pick_days(
        indexed(),
        policy_of(lookback=2),
        now=at(date(2026, 1, 10)),
        operator_range=None,
        first_ledger_year=FIRST_YEAR,
    )

    assert (days[0], days[-1]) == ("2026-01-01", "2026-01-08")


def test_the_files_an_absent_index_is_rebuilt_from_are_fetched_in_one_call_inside_the_budget(
    tmp_path: Path,
) -> None:
    """The two day files sit in two month folders and weigh 1,100 bytes against 1,000.

    One fetch for the whole index names what all of it needs, so the rebuild is
    refused before the checkout widens at all, and a later wake with its whole
    budget takes it.
    """
    entries = [
        TreeEntry(path=f"{COMPACT}/daily/2026/08/31.parquet", blob="1" * 40, size=600),
        TreeEntry(path=f"{COMPACT}/daily/2026/09/01.parquet", blob="2" * 40, size=500),
    ]

    sizes = {entry.path: entry.size for entry in entries if entry.size is not None}

    def lister(paths: Sequence[str]) -> dict[str, int]:
        """Every file at or under each named path, as `git ls-tree -r` lists it."""
        return {
            path: size
            for path, size in sizes.items()
            if any(path == named or path.startswith(f"{named}/") for named in paths)
        }

    asked: list[Sequence[str]] = []
    listing = FileListing.from_commit(
        tmp_path,
        [COMPACT],
        entries,
        {},
        paths=[f"{COMPACT}/index/{period.value}.json" for period in Period],
        widen=asked.append,
        lister=lister,
        budget=1000,
    )
    tree = CompactTree(
        state_dir=state(tmp_path),
        ledger=VISUALS,
        listing=listing,
        daily={},
        monthly={},
        yearly={},
        raw_days=[],
        indexed=frozenset({Period.MONTHLY, Period.YEARLY}),
    )

    with pytest.raises(OverBudgetError) as refused:
        _absent_indexes.rebuild(
            tree,
            policy_of(),
            now=at(date(2026, 9, 4)),
            operator_range=None,
            first_ledger_year=FIRST_YEAR,
            owned_folders=(COMPACT,),
        )

    assert (refused.value.needed, refused.value.budget) == (1100, 1000)
    assert asked == []


# --- what it names: one folder a year --------------------------------------------


def rebuilt(root: Path, wake: date, **changed: Any) -> tuple[CompactTree, list[str]]:
    """A wake's tree after its absent indexes are rebuilt, and every path the rebuild named."""
    context = context_for(TASK, root, today=wake, wake=True, dry_run=False, **changed)
    policy = context.policy
    assert isinstance(policy, CompactionPolicy)
    tree = CompactTree.read(context.state_dir, VISUALS, context.listing)
    before = set(tree.listing.named)
    _absent_indexes.rebuild(
        tree,
        policy,
        now=at(wake),
        operator_range=None,
        first_ledger_year=FIRST_YEAR,
        owned_folders=context.owned_folders,
    )
    return tree, sorted(set(tree.listing.named) - before)


@pytest.mark.parametrize(
    ("wake", "months", "years"),
    [
        (date(2027, 12, 16), ["2026-01", "2027-10"], ["2026", "2027"]),
        (date(2028, 12, 16), ["2026-01", "2027-10", "2028-10"], ["2026", "2027", "2028"]),
    ],
    ids=["a-wake-in-2027", "a-year-later"],
)
def test_a_monthly_rebuild_of_a_window_that_only_reports_names_one_folder_a_year(
    tmp_path: Path, wake: date, months: list[str], years: list[str]
) -> None:
    """Every month the window keeps is found, and a year later the rebuild names one folder more.

    A window whose deletes only report keeps every month, so the rebuild looks
    from January of the first ledger year. It names each year's month folder
    once, not each month's file, so a year adds one named path, not twelve.
    """
    root = tmp_path / "checkout"
    for month in months:
        a_packed_month(root, month)
    an_index(root, Period.DAILY, [])
    an_index(root, Period.YEARLY, [])

    tree, named = rebuilt(root, wake, month_deletes_dry_run=True)

    assert named == [f"{COMPACT}/monthly/{year}" for year in years]
    assert sorted(tree.monthly) == months


def test_a_daily_rebuild_names_the_folder_of_each_year_its_days_fall_in(tmp_path: Path) -> None:
    """The days after an October monthly mark run across New Year, so two folders are named."""
    root = tmp_path / "checkout"
    for day in ("2026-12-31", "2027-01-02"):
        a_packed_file(root, Period.DAILY, day, day)
    an_index(
        root,
        Period.MONTHLY,
        [CompactEntry(covers="2026-10", rows=0, bytes=0, state=EntryState.EMPTY)],
    )
    an_index(root, Period.YEARLY, [])

    tree, named = rebuilt(root, date(2027, 1, 20))

    assert named == [f"{COMPACT}/daily/2026", f"{COMPACT}/daily/2027"]
    assert sorted(tree.daily) == ["2026-12-31", "2027-01-02"]


def test_a_yearly_rebuild_names_one_folder_a_year_from_the_first_ledger_year(
    tmp_path: Path,
) -> None:
    """On 4 March 2028 the year 2027 is old enough to pack, so 2026 and 2027 are each named once."""
    root = tmp_path / "checkout"
    an_index(root, Period.DAILY, [])
    an_index(root, Period.MONTHLY, [])

    _tree, named = rebuilt(root, date(2028, 3, 4), **PACKS_YEARS)

    assert named == [f"{COMPACT}/yearly/2026", f"{COMPACT}/yearly/2027"]


def a_tree_that_names_nothing(root: Path) -> CompactTree:
    """A ledger with no index, over a listing with no lister: any naming at all is refused."""
    return CompactTree(
        state_dir=state(root),
        ledger=VISUALS,
        listing=FileListing.from_paths(root, [], folders=[COMPACT, RAW]),
        daily={},
        monthly={},
        yearly={},
        raw_days=[],
    )


def rebuild_on_16_december_2027(tree: CompactTree, *, owned_folders: Sequence[str]) -> None:
    _absent_indexes.rebuild(
        tree,
        policy_of(),
        now=at(date(2027, 12, 16)),
        operator_range=None,
        first_ledger_year=FIRST_YEAR,
        owned_folders=owned_folders,
    )


def test_a_ledger_whose_compact_folder_the_commit_lacks_is_not_searched(tmp_path: Path) -> None:
    """No file was ever packed under a folder the commit lacks, so the rebuild names nothing."""
    tree = a_tree_that_names_nothing(tmp_path)

    rebuild_on_16_december_2027(tree, owned_folders=(RAW,))

    assert (tree.listing.named, tree.pending_indexes) == ((), set())


def test_a_ledger_whose_compact_folder_the_commit_holds_is_searched(tmp_path: Path) -> None:
    """The same ledger with its compact folder held names its first month folder, and is refused."""
    tree = a_tree_that_names_nothing(tmp_path)

    with pytest.raises(ValueError) as refused:
        rebuild_on_16_december_2027(tree, owned_folders=(RAW, COMPACT))

    assert str(refused.value) == (
        f"{COMPACT}/monthly/2026 cannot be named now: this listing was built from named "
        "files and has no lister to list more"
    )


# --- what a pass does with an absent index: integration --------------------------


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
def test_an_absent_daily_index_is_rebuilt_from_its_day_files_and_nothing_is_deleted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, wake: bool
) -> None:
    """THE ORACLE for an absent index: each day file at its path is adopted, and the pass deletes nothing.

    The rebuilt index is the one that was lost, byte for byte. Over a wake's
    listing the planner names only the ledger's indexes, so the pass names the
    day files it looks for itself.
    """
    root = tmp_path / "checkout"
    for day in ("2026-09-20", "2026-09-21"):
        filed(root, a_pass(day))
    compact(root, date(2026, 9, 23), max_periods_per_run=31)
    daily = index_of(root, Period.DAILY)
    before = daily.read_bytes()
    packed = {
        path: path.read_bytes()
        for day in ("2026-09-20", "2026-09-21")
        if (path := ledger.compact_file(state(root), VISUALS, Period.DAILY, day)) is not None
    }
    daily.unlink()

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31, wake=wake)

    rebuilt = CompactIndex.read(daily).entries
    assert [(entry.covers, entry.state, entry.rows) for entry in rebuilt] == [
        ("2026-09-20", EntryState.PACKED, 1),
        ("2026-09-21", EntryState.PACKED, 1),
    ]
    assert daily.read_bytes() == before
    for day in ("2026-09-20", "2026-09-21"):
        assert recovered(caplog, day) == [f"note={RecoveryNote.INDEX_REBUILT}"]
    assert outcome.taken == ()
    assert outcome.written == (daily.relative_to(root).as_posix(),)
    assert len(packed) == 2 and all(path.read_bytes() == held for path, held in packed.items())
    assert outcome.stopped_because is StopReason.EXHAUSTED


def test_an_absent_monthly_index_is_rebuilt_from_its_month_files(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """August's file is adopted, so the month step starts at September and nothing is lost.

    On 20 October August is 45 whole days past its end, so a 13-month window
    whose deletes are live keeps it, and the rebuild looks for it.
    """
    root = tmp_path / "checkout"
    august = a_month_file(root, "2026-08")
    an_index(root, Period.DAILY, quiet_days("2026-09-01", "2026-10-18"))
    an_index(root, Period.YEARLY, [])
    monthly = index_of(root, Period.MONTHLY)
    before = monthly.read_bytes()
    monthly.unlink()

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 20), wake=True)

    assert monthly.read_bytes() == before
    assert recovered(caplog, "2026-08") == [f"note={RecoveryNote.INDEX_REBUILT}"]
    assert august.is_file()
    assert (outcome.written, outcome.taken) == ((monthly.relative_to(root).as_posix(),), ())
    assert outcome.stopped_because is StopReason.EXHAUSTED


def test_an_absent_monthly_index_of_a_window_that_only_reports_is_rebuilt_with_every_month_it_keeps(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """January 2026 is past the 13-month window, but nobody approved deleting it, so it is found too.

    On 16 December 2027 the newest month old enough to close is October 2027,
    and the days after it are quiet, so the pass writes the rebuilt index alone.
    """
    root = tmp_path / "checkout"
    kept = {month: a_packed_month(root, month) for month in ("2026-01", "2027-10")}
    held = {month: path.read_bytes() for month, path in kept.items()}
    an_index(root, Period.DAILY, quiet_days("2027-11-01", "2027-12-14"))
    an_index(root, Period.YEARLY, [])
    monthly = index_of(root, Period.MONTHLY)

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2027, 12, 16), wake=True, month_deletes_dry_run=True)

    assert [
        (entry.covers, entry.state, entry.rows) for entry in CompactIndex.read(monthly).entries
    ] == [("2026-01", EntryState.PACKED, 1), ("2027-10", EntryState.PACKED, 1)]
    for month in kept:
        assert recovered(caplog, month) == [f"note={RecoveryNote.INDEX_REBUILT}"]
    assert outcome.taken == ()
    assert outcome.written == (monthly.relative_to(root).as_posix(),)
    assert {month: path.read_bytes() for month, path in kept.items()} == held


def test_a_file_at_a_looked_at_path_whose_envelope_names_another_day_stops_the_pass_by_name(
    tmp_path: Path,
) -> None:
    """Adopted, it would put the 20th's rows under the 21st; left out, the 21st would drop from every read."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    compact(root, date(2026, 9, 23), max_periods_per_run=31)
    twentieth = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-20")
    assert twentieth is not None
    twentieth.with_name("21.parquet").write_bytes(twentieth.read_bytes())
    index_of(root, Period.DAILY).unlink()
    before = files_under(root)

    with pytest.raises(ValueError) as refused:
        compact(root, date(2026, 9, 23), max_periods_per_run=31)

    assert str(refused.value) == (
        "21.parquet sits where the visual-prunes daily file for 2026-09-21 goes, and its "
        "envelope says compact visual-prunes daily 2026-09-20, so it is not adopted"
    )
    assert files_under(root) == before
