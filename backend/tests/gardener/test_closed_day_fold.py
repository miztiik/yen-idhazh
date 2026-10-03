"""Which closed days does the gardener's fold settle, what does it leave, and what does it never touch?

Driven by built day trees and by the fixtures under `tests/fixtures/day-shards/`,
never by the committed archive. A built tree carries the cases the archive has
never produced - a straggler after a fold, a day that closed at midnight, two
trees closed on one date - and it costs the same on a five-year archive as on a
fresh clone (CLAUDE.md section 13).

Settlement itself is not asked here: `tests/pipeline/test_day_shards.py` holds
which of two rows wins a cell. What this file asks is narrower - given a
settlement that works, which days the fold takes, what it writes, and what it
deletes.

A day is closed once one whole day has passed since it ended, measured from
00:00 UTC on the wake's own day. So at a wake on the 17th, the 15th is the
newest closed day and the 16th is still open.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final

import pytest
from conftest import seed_feed_health

from idhazh import day_shards, ledger
from idhazh.config import load_observation_lookup
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import DEFAULT_CLOSED_AFTER_DAYS
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.observation_lookup import ObservationLookupEntry
from idhazh.evals.observation_batches import lookup_root
from idhazh.evals.observation_lookup import ObservationLookup
from idhazh.gardener import closed_day_fold
from idhazh.gardener.closed_day_fold import Folded, FoldInterruptedError

pytestmark = pytest.mark.contract

#: The wake every fold below is taken at, and the two days either side of the
#: line it draws.
WAKE: Final = "2026-09-17"
OLDEST_OPEN: Final = "2026-09-16"
NEWEST_CLOSED: Final = "2026-09-15"
OLDER_CLOSED: Final = "2026-09-04"

#: Eight work shards of one run, each filing a feed-health row: eight writers,
#: eight files, one day directory.
WORK_SHARDS: Final = tuple(range(8))

#: Three additional feed-health days in the fixture tree.
FEED_DAYS: Final = ("2026-09-05", "2026-09-06", "2026-09-07")

TREE: Final = LedgerName.FEED_HEALTH


def midnight(day: str) -> datetime:
    """00:00 UTC on a day, the instant a wake measures from."""
    return datetime.combine(date.fromisoformat(day), time.min, tzinfo=UTC)


def fold(
    state: Path,
    *,
    wake: str = WAKE,
    dry_run: bool = False,
    skip: frozenset[Path] = frozenset(),
) -> Folded:
    """The fold every test here takes: every tree, at a wake, with the default rule."""
    return closed_day_fold.fold(
        state,
        DAY_TREES,
        now=midnight(wake),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=dry_run,
        skip=skip,
        period_paths=[ledger.tree_root(state, tree) for tree in DAY_TREES],
    )


def a_row(day: str, *, shard: int, run: int = 1) -> FeedHealthRow:
    """One real feed-health row, with a distinct feed for each work shard."""
    return FeedHealthRow.model_validate(
        {
            "run_id": f"{day}-90000000{run}",
            "date": day,
            "feed_id": f"example-feed-{shard}",
            "checked_at": f"{day}T06:00:00Z",
            "outcome": FetchOutcome.OK,
            "status": 200,
            "items": 3,
        }
    )


def file_rows(
    state: Path,
    rows: list[FeedHealthRow],
    *,
    day: str,
    run: int = 1,
    attempt: int = 1,
    shard: int = 0,
) -> Path:
    """File one shard's feed-health rows and return the day folder."""
    ledger.write_segment(
        state,
        TREE,
        rows,
        run_id=f"{day}-90000000{run}",
        attempt=attempt,
        job=ServerJob.WORK,
        shard=shard,
        date=day,
    )
    return ledger.path(state, TREE, day)


def a_full_run(state: Path, day: str) -> Path:
    """Every work shard of one run, each filing its feed-health row into one day."""
    for shard in WORK_SHARDS:
        file_rows(
            state,
            [a_row(day, shard=shard)],
            day=day,
            shard=shard,
        )
    return ledger.path(state, TREE, day)


def a_verdict(day: str, *, run: int) -> FeedHealthRow:
    """One feed's verdict on one run, shaped the way the contract's own validators demand."""
    return FeedHealthRow.model_validate(
        {
            "run_id": f"{day}-90000000{run}",
            "date": day,
            "feed_id": "example-feed",
            "checked_at": f"{day}T06:00:00Z",
            "outcome": FetchOutcome.OK,
            "status": 200,
            "items": 3,
        }
    )


def verdicts(state: Path, day: str, *, runs: int = 1) -> Path:
    """The plan job of each run filing its verdict into one day, and that day's folder."""
    for run in range(1, runs + 1):
        seed_feed_health(state, day, [a_verdict(day, run=run)], run_id=f"{day}-90000000{run}")
    return ledger.path(state, LedgerName.FEED_HEALTH, day)


def names_in(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def rows_in(path: Path) -> list[dict[str, str]]:
    """A file's rows, read without newline translation so a CRLF drift shows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def settled_in(state: Path, tree: LedgerName, day: str) -> list[dict[str, str]]:
    """What a reader settles for one day, whichever files the day is holding."""
    return day_shards.settled_day(
        ledger.tree_root(state, tree), day, ledger.segment_key(tree), ledger.segment_contract(tree)
    )


def every_day(state: Path) -> dict[tuple[LedgerName, str], list[dict[str, str]]]:
    """Every recorded day of every tree, as a reader settles it.

    The whole tree, because the claim is about every day in it - and the tree is
    one built here, so the read costs the same whatever the archive holds.
    """
    answers: dict[tuple[LedgerName, str], list[dict[str, str]]] = {}
    for tree in DAY_TREES:
        root = ledger.tree_root(state, tree)
        for days in day_shards.dates_by_month(root, days=UNBOUNDED_WINDOW).values():
            for day in days:
                answers[(tree, day)] = settled_in(state, tree, day)
    return answers


def the_fixture_tree(root: Path) -> Path:
    """Five feed-health days with repeated attempts and a late row after folding.

    Six writer files over three feed-health days, where the plan jobs of two
    runs each filed a verdict; three writer files of one day where two attempts
    repeat an ID; and one day an earlier fold already settled, with a straggler
    beside it.
    """
    state = root / ledger.STATE_DIRNAME
    a_full_run(state, NEWEST_CLOSED)
    fold(state)
    file_rows(
        state,
        [a_row(NEWEST_CLOSED, shard=9, run=2)],
        day=NEWEST_CLOSED,
        run=2,
        shard=9,
    )
    for shard in range(2):
        file_rows(
            state,
            [a_row(OLDER_CLOSED, shard=shard)],
            day=OLDER_CLOSED,
            shard=shard,
        )
    file_rows(
        state,
        [a_row(OLDER_CLOSED, shard=0)],
        day=OLDER_CLOSED,
        attempt=2,
    )
    for day in FEED_DAYS:
        verdicts(state, day, runs=2)
    return state


# --- The oracle ----------------------------------------------------------------


def test_the_fold_changes_no_answer_and_never_touches_an_open_day(tmp_path: Path) -> None:
    """Every day reads the same rows before and after, and the open day keeps its bytes.

    The whole licence for folding at all, taken through the reader every consumer
    uses rather than by comparing files: the claim is about what a reader gets,
    not how many files it opened to get it.
    """
    state = the_fixture_tree(tmp_path)
    wake = "2026-09-22"
    open_day = file_rows(
        state,
        [a_row("2026-09-21", shard=0)],
        day="2026-09-21",
    )
    open_bytes = {path.name: path.read_bytes() for path in open_day.iterdir()}
    before = every_day(state)
    assert len(before) == 6, "the fixture tree has to carry six days or this proves less"
    assert len(before[(TREE, OLDER_CLOSED)]) == 2
    assert len(before[(TREE, NEWEST_CLOSED)]) == len(WORK_SHARDS) + 1

    folded = fold(state, wake=wake)

    assert every_day(state) == before
    assert {path.name: path.read_bytes() for path in open_day.iterdir()} == open_bytes
    assert sorted((day.tree, day.day) for day in folded.days) == sorted(
        key for key in before if key[1] != "2026-09-21"
    )
    for day in folded.days:
        assert names_in(day.folder) == [day_shards.SETTLED_NAME]


# --- Which days the fold takes ---------------------------------------------------


def test_a_tree_with_no_days_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """A fresh clone is not a fault, and neither is a tree a fold already drained."""
    assert fold(tmp_path / ledger.STATE_DIRNAME) == Folded(dry_run=False)


def test_a_closed_day_folds_into_one_file_holding_every_row(tmp_path: Path) -> None:
    """Eight writers leave eight files, and the fold leaves one holding every row.

    Two-sided on purpose: "one file is there" passes on a fold that wrote the
    settled file and kept the eight beside it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    before = settled_in(state, TREE, NEWEST_CLOSED)

    folded = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert [(settled.tree, settled.day) for settled in folded.days] == [
        (TREE, NEWEST_CLOSED)
    ]
    assert folded.files == len(WORK_SHARDS)
    assert rows_in(day / day_shards.SETTLED_NAME) == before


def test_the_newest_open_day_is_left_alone_and_the_day_before_it_is_taken(
    tmp_path: Path,
) -> None:
    """The line, asserted from both sides so an off-by-one cannot pass.

    The day before the wake ended at 00:00 UTC on the wake's own day, so no whole
    day has passed since and a re-run could still be writing it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    open_day = a_full_run(state, OLDEST_OPEN)
    closed_day = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state)

    assert len(names_in(open_day)) == len(WORK_SHARDS), (
        "a day a re-run could still write was folded"
    )
    assert names_in(closed_day) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [NEWEST_CLOSED]


def test_which_days_are_closed_is_measured_from_the_instant_handed_in(tmp_path: Path) -> None:
    """The same tree at two wakes a day apart, so the clock can decide nothing."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)

    assert fold(state, wake="2026-09-16").days == ()
    assert len(names_in(day)) == len(WORK_SHARDS)

    assert [settled.day for settled in fold(state, wake=WAKE).days] == [NEWEST_CLOSED]
    assert names_in(day) == [day_shards.SETTLED_NAME]


def test_every_closed_day_goes_in_one_pass_so_a_missed_wake_catches_up(tmp_path: Path) -> None:
    """A wake after one that did not fold takes every day still waiting, oldest first."""
    state = tmp_path / ledger.STATE_DIRNAME
    older = a_full_run(state, OLDER_CLOSED)
    newer = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state)

    assert names_in(older) == names_in(newer) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [OLDER_CLOSED, NEWEST_CLOSED]


def test_folding_a_ledger_leaves_the_observation_lookup_unchanged(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    feeds = verdicts(state, NEWEST_CLOSED)
    root = lookup_root(state)
    identity = "a" * 64
    with ObservationLookup(root) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, load_observation_lookup())
        lookup.put(
            [ObservationLookupEntry(namespace="observation", identity=identity)],
            generation="b" * 64,
        )
    before = bytes_under(root)

    folded = fold(state)

    assert names_in(feeds) == [day_shards.SETTLED_NAME]
    assert [settled.tree for settled in folded.days] == [TREE]
    assert bytes_under(root) == before
    with ObservationLookup(root) as lookup:
        assert lookup.recorded([identity, "c" * 64]) == {identity}


def test_only_the_trees_handed_in_are_folded(tmp_path: Path) -> None:
    """A task folds the trees it walks, so a tree another task owns is left to that task."""
    state = tmp_path / ledger.STATE_DIRNAME
    feeds = a_full_run(state, NEWEST_CLOSED)
    before = bytes_under(feeds)

    folded = closed_day_fold.fold(
        state,
        [],
        now=midnight(WAKE),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=False,
        period_paths=[],
    )

    assert folded == Folded(dry_run=False)
    assert bytes_under(feeds) == before


def test_a_day_folder_the_window_took_is_left_to_the_window(tmp_path: Path) -> None:
    """The window goes first, so a day it is removing is never written by the fold."""
    state = tmp_path / ledger.STATE_DIRNAME
    taken = a_full_run(state, OLDER_CLOSED)
    kept = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state, skip=frozenset({taken}))

    assert len(names_in(taken)) == len(WORK_SHARDS)
    assert names_in(kept) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [NEWEST_CLOSED]


# --- A dry run, and a fold that stops -----------------------------------------------


def test_a_dry_run_settles_every_day_it_would_fold_and_changes_nothing(tmp_path: Path) -> None:
    """The list a person reads before turning a fold live is the list the live fold takes."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    before = {path.name: path.read_bytes() for path in day.iterdir()}

    rehearsed = fold(state, dry_run=True)

    assert {path.name: path.read_bytes() for path in day.iterdir()} == before
    assert rehearsed.dry_run is True
    assert [settled.day for settled in rehearsed.days] == [NEWEST_CLOSED]
    assert rehearsed.files == len(WORK_SHARDS)
    assert fold(state).days == rehearsed.days


def test_a_row_that_will_not_read_stops_the_fold_and_carries_the_days_before_it(
    tmp_path: Path,
) -> None:
    """The days settled before the failure stand, and the failed day keeps every file.

    A dry run reads the same rows, so it stops on the same day.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    good = a_full_run(state, OLDER_CLOSED)
    bad = a_full_run(state, NEWEST_CLOSED)
    victim = sorted(bad.iterdir())[0]
    with victim.open("a", encoding="utf-8", newline="") as handle:
        handle.write("not,a,feed-row\n")

    with pytest.raises(FoldInterruptedError, match=f"{TREE.value} {NEWEST_CLOSED}") as stop:
        fold(state)

    assert stop.value.so_far.failed is True
    assert [settled.day for settled in stop.value.so_far.days] == [OLDER_CLOSED]
    assert names_in(good) == [day_shards.SETTLED_NAME]
    assert len(names_in(bad)) == len(WORK_SHARDS)


# --- What a second fold does -----------------------------------------------------


def test_a_day_already_folded_is_never_folded_again(tmp_path: Path) -> None:
    """The second fold writes nothing, so a wake that folds every day makes no diff.

    A byte comparison, because "the rows are the same" passes on a rewrite that
    reordered them - and that rewrite would be a diff on every wake.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    written = (day / day_shards.SETTLED_NAME).read_bytes()

    assert fold(state) == Folded(dry_run=False)
    assert (day / day_shards.SETTLED_NAME).read_bytes() == written


def test_a_straggler_that_lands_after_a_fold_is_folded_into_the_file_beside_it(
    tmp_path: Path,
) -> None:
    """A re-run of a closed day writes one more file, and the next wake takes it in."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    late = a_row(NEWEST_CLOSED, shard=9, run=2)
    file_rows(
        state,
        [late],
        day=NEWEST_CLOSED,
        run=2,
        shard=9,
    )
    assert len(names_in(day)) == 2

    folded = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert folded.files == 1, "the settled file is rewritten, so only the straggler goes"
    feeds = [row["feed_id"] for row in rows_in(day / day_shards.SETTLED_NAME)]
    assert late.feed_id in feeds
    assert len(feeds) == len(WORK_SHARDS) + 1


def test_two_folds_of_one_closed_day_write_the_same_bytes(tmp_path: Path) -> None:
    """A fold is a function of the files it read, so folding the same day twice agrees.

    Compared byte for byte rather than row for row: a fold that agreed on the rows
    and disagreed on their order would be a diff every time it ran again.
    """
    first = the_fixture_tree(tmp_path / "first")
    second = the_fixture_tree(tmp_path / "second")

    fold(first, wake="2026-09-22")
    fold(second, wake="2026-09-22")

    def files_under(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    written = files_under(first)
    assert written, "the fixture folded to nothing, so this compared two empty trees"
    assert written == files_under(second)
    assert all(Path(relpath).name == day_shards.SETTLED_NAME for relpath in written)


# --- A closed month settled whole --------------------------------------------------

#: A wake at which August closed a month ago, the 29th of September is a closed
#: day of an open month, and the 30th is still open.
MONTH_WAKE: Final = "2026-10-01"
CLOSED_MONTH: Final = "2026-08"


def a_month_tree(root: Path) -> Path:
    """Five August files hold seven feed keys, beside one closed and one open September day."""
    state = root / ledger.STATE_DIRNAME
    first = "2026-08-03"
    middle = "2026-08-17"
    file_rows(state, [a_row(first, shard=0), a_row(first, shard=1)], day=first)
    file_rows(state, [a_row(first, shard=0), a_row(first, shard=2)], day=first, attempt=2)
    file_rows(state, [a_row(middle, shard=0), a_row(middle, shard=1)], day=middle)
    fold(state, wake="2026-08-20", skip=frozenset({ledger.path(state, TREE, first)}))
    file_rows(state, [a_row(middle, shard=2, run=2)], day=middle, run=2)
    for day in ("2026-08-31", "2026-09-29", "2026-09-30"):
        file_rows(state, [a_row(day, shard=0)], day=day)
    return state


def fold_months(
    state: Path,
    *,
    wake: str = MONTH_WAKE,
    dry_run: bool = False,
    skip: frozenset[Path] = frozenset(),
) -> Folded:
    """A real ledger folded with the closed-month option."""
    return closed_day_fold.fold(
        state,
        [TREE],
        now=midnight(wake),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=dry_run,
        settles_months=True,
        skip=skip,
        period_paths=[ledger.tree_root(state, TREE)],
    )


def keys_in(paths: Iterable[Path]) -> set[tuple[str, ...]]:
    """Every real ledger key these files hold together."""
    return {
        tuple(row[column] for column in ledger.segment_key(TREE))
        for path in paths
        for row in rows_in(path)
    }


def recorded_keys(state: Path) -> set[tuple[str, ...]]:
    return {
        tuple(row[column] for column in ledger.segment_key(TREE))
        for row in day_shards.settled_rows(
            ledger.tree_root(state, TREE),
            ledger.segment_key(TREE),
            ledger.segment_contract(TREE),
            days=UNBOUNDED_WINDOW,
        )
    }


def bytes_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_a_closed_month_settles_into_one_file_holding_every_id_its_days_held(
    tmp_path: Path,
) -> None:
    """The oracle: one file in the month's folder, every ID in it once, and no answer moved.

    The open month is the control on both sides of its own line: its closed day
    folds by day as before, and its open day keeps its bytes.
    """
    state = a_month_tree(tmp_path)
    root = ledger.tree_root(state, TREE)
    month = root / "2026" / "08"
    august = day_shards.one_month(root, CLOSED_MONTH)
    held = keys_in(august)
    assert (len(august), len(held)) == (5, 7), "the fixture needs five files and seven distinct keys"
    open_day = root / "2026" / "09" / "30"
    open_bytes = bytes_under(open_day)
    before = recorded_keys(state)

    folded = fold_months(state)

    assert names_in(month) == [day_shards.SETTLED_NAME], "a file of the closed month was left"
    settled = rows_in(month / day_shards.SETTLED_NAME)
    assert keys_in([month / day_shards.SETTLED_NAME]) == held
    assert len(settled) == len(held), "an ID two writers both filed is in the month file twice"
    assert [(each.tree, each.month, len(each.replaced)) for each in folded.months] == [
        (TREE, CLOSED_MONTH, len(august))
    ]
    assert [(each.tree, each.day) for each in folded.days] == [(TREE, "2026-09-29")]
    assert names_in(root / "2026" / "09" / "29") == [day_shards.SETTLED_NAME]
    assert bytes_under(open_day) == open_bytes
    assert recorded_keys(state) == before


def test_a_second_fold_of_a_settled_month_changes_nothing(tmp_path: Path) -> None:
    """A byte comparison, because a rewrite that reordered the rows is a diff every wake."""
    state = a_month_tree(tmp_path)
    fold_months(state)
    root = ledger.tree_root(state, TREE)
    written = bytes_under(root)

    assert fold_months(state) == Folded(dry_run=False)
    assert bytes_under(root) == written


def test_a_day_that_lands_in_a_settled_month_is_settled_in_at_the_next_pass(
    tmp_path: Path,
) -> None:
    """A re-run reaching back into a closed month leaves a day folder beside the month's file.

    A reader sees its ID at once, and the next pass settles it into the month's
    file with every ID the file already held.
    """
    state = a_month_tree(tmp_path)
    fold_months(state)
    root = ledger.tree_root(state, TREE)
    month = root / "2026" / "08"
    settled = keys_in([month / day_shards.SETTLED_NAME])
    before = recorded_keys(state)
    late = a_row("2026-08-20", shard=9, run=2)
    file_rows(
        state,
        [late],
        day="2026-08-20",
        run=2,
        attempt=2,
    )
    late_key = tuple(late.csv_row()[column] for column in ledger.segment_key(TREE))
    assert names_in(month) == ["20", day_shards.SETTLED_NAME]
    assert recorded_keys(state) == before | {late_key}, "a reader missed the late day"

    folded = fold_months(state)

    assert names_in(month) == [day_shards.SETTLED_NAME]
    assert keys_in([month / day_shards.SETTLED_NAME]) == settled | {late_key}
    assert [(each.month, len(each.replaced)) for each in folded.months] == [(CLOSED_MONTH, 1)]
    assert recorded_keys(state) == before | {late_key}


def test_a_month_closes_whole_days_after_its_last_day_ends(tmp_path: Path) -> None:
    """The line, from both sides: at the first instant of September, August's last day is open.

    So that wake folds August's closed days one by one, as an open month's, and
    the next day's wake settles the month whole - from the settled days and the
    last day's writer file alike.
    """
    state = a_month_tree(tmp_path)
    root = ledger.tree_root(state, TREE)

    first = fold_months(state, wake="2026-09-01")

    assert first.months == ()
    assert [each.day for each in first.days] == ["2026-08-03", "2026-08-17"]
    assert names_in(root / "2026" / "08") == ["03", "17", "31"]

    second = fold_months(state, wake="2026-09-02")

    assert [(each.month, len(each.replaced)) for each in second.months] == [(CLOSED_MONTH, 3)]
    assert names_in(root / "2026" / "08") == [day_shards.SETTLED_NAME]


def test_a_fold_that_does_not_settle_months_keeps_one_file_a_closed_day(
    tmp_path: Path,
) -> None:
    """The month step is the declaration's to ask for; every other tree folds as it did."""
    state = a_month_tree(tmp_path)
    root = ledger.tree_root(state, TREE)

    folded = fold(state, wake=MONTH_WAKE)

    assert folded.months == ()
    assert [each.day for each in folded.days] == [
        "2026-08-03",
        "2026-08-17",
        "2026-08-31",
        "2026-09-29",
    ]
    assert names_in(root / "2026" / "08") == ["03", "17", "31"]


def test_a_dry_run_settles_a_closed_month_and_changes_nothing(tmp_path: Path) -> None:
    """The list a person reads before turning the step live is the list the live step takes."""
    state = a_month_tree(tmp_path)
    root = ledger.tree_root(state, TREE)
    before = bytes_under(root)

    rehearsed = fold_months(state, dry_run=True)

    assert bytes_under(root) == before
    assert rehearsed.dry_run is True
    assert [(each.month, len(each.replaced)) for each in rehearsed.months] == [(CLOSED_MONTH, 5)]
    assert fold_months(state).months == rehearsed.months


def test_a_month_holding_a_day_the_window_took_is_left_to_the_window(tmp_path: Path) -> None:
    """The window goes first, and a month is settled whole or not at all."""
    state = a_month_tree(tmp_path)
    root = ledger.tree_root(state, TREE)
    taken = root / "2026" / "08" / "17"

    folded = fold_months(state, skip=frozenset({taken}))

    assert folded.months == ()
    assert names_in(root / "2026" / "08") == ["03", "17", "31"]
    assert [each.day for each in folded.days] == ["2026-09-29"]
