"""The migration utility, and the refusal that is the load-bearing half.

A migration that writes an empty tree and unlinks its source is a delete with
exit 0, so the assertions below are in two halves. One half says every row that
went in comes out once, in the day file its own date names. The other says a row
the utility cannot place stops the run with both layouts intact and nothing
unlinked.

`tests/fixtures/day-shard-migration/` is committed rather than built, and it is
three copies of one two-month store because one store cannot carry all the
cases: the read stops on the first row it cannot place, so a store holding a bad
row can never demonstrate a good migration. `clean` is the good path. The other
two each add one bad row, and they add it at opposite ends of the read on
purpose - `not-a-date` in the first shard, so the run stops before the second
shard is even opened, and `empty-date` in the last row of the second shard, so a
whole shard has been read and grouped in memory before the refusal fires.
Neither may leave a byte behind.

The four awkward rows are the ones the committed ledgers do not have: a row on
the first day of a month, a row on the last day of a month, a row whose date
cell is empty, and a row whose date cell is not a date. Two of them are what a
real ledger eventually holds - a run interrupted mid-append, a header migration
half applied - and the fixture is built because the archive has never produced
them (`CLAUDE.md` section 13). It is six files and nothing appends to it, so it
is fixed in size (Guardrail #12).
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR, read_text

from idhazh.day_partition import day_files
from utilities import migrate_to_day_shards as migrate

FIXTURE: Final = FIXTURES_DIR / "day-shard-migration"

#: The column the fixture files by, and the one three of the five real ledgers
#: carry. `state/seen/` carries `first_seen_run` instead, which is why `day_of`
#: is pinned on a run id below rather than only on a bare date.
DATE_COLUMN: Final = "date"

#: The day files `clean` becomes, in the order the report names them.
CLEAN_DAYS: Final = ["2026/08/01.csv", "2026/08/31.csv", "2026/09/07.csv", "2026/09/10.csv"]


def _store(tmp_path: Path, name: str) -> Path:
    """The committed fixture, copied, because a test may not write into a fixture."""
    store = tmp_path / "state" / "item-health"
    shutil.copytree(FIXTURE / name, store)
    return store


def _bytes(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by POSIX relative path.

    Bytes rather than a file list, so "both trees intact" means the trees are
    unchanged rather than merely present.
    """
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _rows_in_months(root: Path) -> Counter[str]:
    """Every data line the month shards hold, counted."""
    found: Counter[str] = Counter()
    for path in sorted(root.glob("*.csv")):
        found.update(read_text(path).split("\n")[1:-1])
    return found


def _rows_in_days(root: Path) -> Counter[str]:
    """Every data line the pipeline's own day walk finds, counted."""
    found: Counter[str] = Counter()
    for path in day_files(root):
        found.update(read_text(path).split("\n")[1:-1])
    return found


def test_every_row_that_went_in_comes_out_once_in_the_day_its_own_date_names(
    tmp_path: Path,
) -> None:
    """The Oracle. A multiset, so a row duplicated into two days fails it.

    A set would pass on a store whose two rows for one day became one, and two
    of these six rows share a day precisely so that a set cannot pass here.
    """
    store = _store(tmp_path, "clean")
    before = _rows_in_months(store)
    assert sum(before.values()) == 6

    report = migrate.run(store, DATE_COLUMN)

    assert _rows_in_days(store) == before
    assert report.rows_in == report.rows_out == 6
    assert report.paths == CLEAN_DAYS
    assert report.shards == ["2026-08.csv", "2026-09.csv"]
    assert not list(store.glob("*.csv"))


def test_a_row_on_the_first_and_the_last_day_of_a_month_gets_its_own_file(
    tmp_path: Path,
) -> None:
    """The month boundary, from both sides, and the rows are copied verbatim.

    A split that derived the day from the shard's own name rather than from the
    row's cell would put all three August rows in one file and still report six
    rows out.
    """
    store = _store(tmp_path, "clean")
    august = read_text(store / "2026-08.csv").split("\n")

    migrate.run(store, DATE_COLUMN)

    first = read_text(store / "2026" / "08" / "01.csv").split("\n")
    last = read_text(store / "2026" / "08" / "31.csv").split("\n")
    assert first == [august[0], august[1], ""]
    assert last == [august[0], august[2], august[3], ""]


@pytest.mark.parametrize(
    ("tree", "where"),
    [("empty-date", "2026-09.csv line 5"), ("not-a-date", "2026-08.csv line 5")],
)
def test_a_row_it_cannot_place_stops_the_run_with_both_trees_intact(
    tmp_path: Path, tree: str, where: str
) -> None:
    """The refusal, which is the load-bearing half.

    Not "it raised" - every byte of the store is compared, so a run that wrote
    part of a day tree before it stopped fails this even though it unlinked
    nothing. The two trees put the bad row at opposite ends of the read, so this
    holds whether or not a shard had already been read and grouped.
    """
    store = _store(tmp_path, tree)
    before = _bytes(store)

    with pytest.raises(ValueError, match=re.escape(where)):
        migrate.run(store, DATE_COLUMN)

    assert _bytes(store) == before
    assert sorted(before) == ["2026-08.csv", "2026-09.csv"]


def test_a_second_run_over_the_migrated_tree_changes_no_byte(tmp_path: Path) -> None:
    """Idempotence, and it is the store's own shape that gives it.

    A migrated store holds no month shard, so there is nothing to move and the
    utility says so. It is not a flag and not a marker file - which matters,
    because a marker is a thing a restore from the trunk would bring back.
    """
    store = _store(tmp_path, "clean")
    migrate.run(store, DATE_COLUMN)
    once = _bytes(store)

    report = migrate.run(store, DATE_COLUMN)

    assert report.shards == []
    assert report.rows_in == 0
    assert _bytes(store) == once


def test_a_month_shard_beside_anything_else_is_refused_before_a_byte_moves(
    tmp_path: Path,
) -> None:
    """Refused because no reader can walk the result, not because it is untidy.

    The first assertion is this refusal's whole premise: `day_files` stops on a
    month shard at the root of a day tree, so a half-migrated store is already
    unreadable by the pipeline. The repair is a restore from the trunk, because
    a second pass cannot know which rows the first one had already moved.
    """
    store = _store(tmp_path, "clean")
    (store / "notes.txt").write_bytes(b"a stray\n")
    before = _bytes(store)

    with pytest.raises(ValueError, match=re.escape("notes.txt")):
        migrate.run(store, DATE_COLUMN)

    assert _bytes(store) == before
    with pytest.raises(ValueError, match="not a YYYY/MM/DD day file"):
        list(day_files(store))


def test_a_column_the_header_does_not_carry_stops_the_run(tmp_path: Path) -> None:
    """The mis-drive guard: five ledgers move, and they do not share one column name."""
    store = _store(tmp_path, "clean")
    before = _bytes(store)

    with pytest.raises(ValueError, match="carries no 'first_seen_run' column"):
        migrate.run(store, "first_seen_run")

    assert _bytes(store) == before


def test_two_shards_that_disagree_on_the_header_stop_the_run(tmp_path: Path) -> None:
    """A header migration half applied. No one header fits both, so neither is picked."""
    store = _store(tmp_path, "clean")
    september = read_text(store / "2026-09.csv")
    (store / "2026-09.csv").write_bytes(("extra," + september).encode("ascii"))
    before = _bytes(store)

    with pytest.raises(ValueError, match="different header"):
        migrate.run(store, DATE_COLUMN)

    assert _bytes(store) == before


@pytest.mark.parametrize(
    ("cell", "day"),
    [("2026-09-07", "2026-09-07"), ("2026-08-23-3", "2026-08-23"), ("2026-08-23-11", "2026-08-23")],
)
def test_a_day_or_a_run_id_names_a_day(cell: str, day: str) -> None:
    """A run id is `<date>-<n>`, so `state/seen/` files by `first_seen_run`."""
    assert migrate.day_of(cell) == day


@pytest.mark.parametrize(
    "cell",
    ["", "pending", "2026-08-23T15:20:27Z", "20260907", "2026-W01-1", "2026-09-07 "],
)
def test_a_cell_that_names_no_day_file_is_refused(cell: str) -> None:
    """Each of these is refused by a different clause, and one of them is a decision.

    `2026-08-23T15:20:27Z` is `first_seen_at`, and refusing it is what stops
    `state/seen/` being filed by a wall-clock stamp that crosses midnight
    independently of the run its row belongs to. `20260907` and `2026-W01-1` are
    both accepted by `date.fromisoformat` and name no `<YYYY>/<MM>/<DD>` path.
    """
    with pytest.raises(ValueError, match="is dated"):
        migrate.day_of(cell)


def test_every_path_it_reports_is_a_posix_relative_path(tmp_path: Path) -> None:
    """`CLAUDE.md` section 2. A report is a thing that leaves the process."""
    store = _store(tmp_path, "clean")

    report = migrate.run(store, DATE_COLUMN)

    for name in [*report.shards, *report.paths]:
        assert "\\" not in name
        assert ":" not in name
        assert not name.startswith("/")
