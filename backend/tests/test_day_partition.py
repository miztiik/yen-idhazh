"""What a date segment is, which empty date folders a delete leaves, and which days a window names.

Every day-folder reader asks `day_partition.is_segment` what a year, a month and
a day may be called, so the ASCII rule is held here once rather than by each
reader. Every tree here is built under `tmp_path`, so these checks cost the same
whatever the committed ledgers hold (`CLAUDE.md` Guardrail #12, section 13).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import day_partition


@pytest.mark.parametrize(
    ("name", "width", "is_one"),
    [
        ("2026", day_partition.YEAR_WIDTH, True),
        ("09", day_partition.SEGMENT_WIDTH, True),
        ("9", day_partition.SEGMENT_WIDTH, False),
        ("009", day_partition.SEGMENT_WIDTH, False),
        ("0a", day_partition.SEGMENT_WIDTH, False),
        # A month in Arabic-Indic digits. `str.isdigit` and `\d` both take it,
        # so the ASCII clause is what refuses it.
        ("\u0660\u0669", day_partition.SEGMENT_WIDTH, False),
    ],
)
def test_a_segment_is_ascii_digits_of_its_own_width(name: str, width: int, is_one: bool) -> None:
    """Fails when the ASCII clause goes, or a width is no longer exact."""
    assert day_partition.is_segment(name, width) is is_one


def test_a_delete_drops_the_date_folders_it_empties_and_stops_at_the_root(
    tmp_path: Path,
) -> None:
    """A day, a month and a year go when they hold nothing else; the ledger root stays.

    A reader walks every year and month folder it finds, so a folder a delete
    left empty is one more step on every later read.
    """
    root = tmp_path / "state" / "a-ledger"
    gone = root / "2026" / "09" / "07" / "a.json"
    kept = root / "2026" / "08" / "31" / "b.json"
    for path in (gone, kept):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="ascii", newline="\n")

    gone.unlink()
    day_partition.drop_empty_day_dirs(gone)

    assert not (root / "2026" / "09").exists(), "the emptied day and month are gone"
    assert kept.exists(), "a month that still holds a day is kept, and its year with it"
    assert root.is_dir(), "the ledger root is never a date segment, so the climb stops there"


def test_a_window_names_both_of_its_ends() -> None:
    """A cover of `n` days returns `n + 1` dates, newest first.

    An off-by-one in a cover is a day the reader silently stops opening.
    `month_partition.shards_in_window` counts the same way at month grain.
    """
    days = day_partition.days_in_window("2026-03-02", 3)

    assert days == ["2026-03-02", "2026-03-01", "2026-02-28", "2026-02-27"]


def test_a_window_crosses_a_leap_day_without_a_calendar_table() -> None:
    """February 2028 has 29 days and no arithmetic here knows that.

    The walk subtracts days from a real date, so a month and a year boundary
    cost it nothing. Subtracting months would need a table, and a table is a
    second place for the boundary to be wrong.
    """
    assert day_partition.days_in_window("2028-03-01", 2) == [
        "2028-03-01",
        "2028-02-29",
        "2028-02-28",
    ]