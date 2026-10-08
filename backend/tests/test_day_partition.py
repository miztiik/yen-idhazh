"""One rule for every `state/` day tree, held to by every reader of one.

The day-side twin of `gardener/tasks/test_telemetry_aggregate_task.py::test_the_month
_readers_all_agree_on_what_a_month_is`, which found three month readers disagreeing on
2026-09-08 and one file left alone in one ledger and deleted in another.

**Behaviour rather than identity.** Asserting that two names point at one
function proves nothing about a third place that reimplemented the walk, and a
reimplemented walk is the whole failure. So every reader is driven over a real
tree and asked what it did.

**The set is the readers of a `<YYYY>/<MM>/<DD>.csv` tree under `state/`.**
There is one other day walk in the repository and it is deliberately not in
here: `retention.dated_days` reads `frontend/public/digest/`, where a day is a
DIRECTORY holding a payload rather than a CSV file, and at its root it skips a
name it cannot read instead of refusing it. Driven over these trees it would
refuse the good day file too, because `07.csv` is not a day directory. A
different shape answering a different question is not a disagreement.

Every tree here is built under `tmp_path` from the constants below, so these
checks cost the same on the day a committed day tree holds ten times the days
(`CLAUDE.md` Guardrail #12, section 13). A built tree also carries the four cases the
committed ledgers have never produced and never will.

**No ledger files this layout now.** The judge's fitted line, the last, moved
under `state/raw/`, so its writer and the post-merge settlement that walked its
tree left this table, and the tree is built by hand in the layout they used.
`day_partition.day_files` stays while the prune verb's CSV branch walks with it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_partition

#: Where the tree every reader below is driven over sits under the state root,
#: two folders deep as a family files its ledgers.
TREE_DIR: Final = "a-family/a-day-tree"

#: The one good day. Fixed, so nothing here expires when the calendar moves.
DAY: Final = "2026-09-07"

#: Every name a day tree may not hold, as a path relative to the tree's root.
#:
#: `2026/13/01.csv` and `2026/09/32.csv` are the right width and the right
#: shape and no date anything here ever wrote. The third is a day stem in
#: Arabic-Indic digits: `re.fullmatch(r"\\d{2}", ...)` takes it, because `\\d`
#: matches another script's numerals, so the ASCII clause is what refuses it.
#: `notes.txt` is the plain case - a file in the tree that is not a day file at
#: all, which a glob would pass over in silence.
STRAYS: Final = (
    "2026/13/01.csv",
    "2026/09/32.csv",
    "2026/09/\u0660\u0667.csv",
    "notes.txt",
)

#: The same stray one level up: a month directory whose name is not ASCII
#: digits, holding nothing. The walk this module replaced entered it, found
#: nothing to refuse and yielded nothing, so the stray was tolerated in a tree
#: whose entire rule is that nothing is tolerated.
EMPTY_STRAY_MONTH: Final = "2026/\u0660\u0669"


def _write_day(state: Path, date: str) -> None:
    """One header-only `<YYYY>/<MM>/<DD>.csv`, where the tree files the day."""
    path = state / TREE_DIR / date[:4] / date[5:7] / f"{date[8:10]}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("version\n", encoding="utf-8", newline="")


def _days_walked(state: Path) -> list[str]:
    root = state / TREE_DIR
    return sorted(day_partition.date_of(path) for path in day_partition.day_files(root))


Writer = Callable[[Path, str], None]
Reader = Callable[[Path], list[str]]

#: Every reader of a `state/` day tree: the directory it owns, the writer that
#: puts one day in it, and the read that says which days it found.
#:
#: A row is added here when a reader is added, and that is the point - a reader
#: this table does not drive is the reader that starts disagreeing.
#: `ledger.load_visual_prunes` left on 2026-09-28 and `ledger.load_published`
#: later, when each ledger moved under `state/raw/`: its days are folders of
#: writer files there, walked by `ledger/raw_files.py`, not `<DD>.csv` files.
#: `ledger.keyed_paths` left when the fitted line moved there too.
READERS: Final[tuple[tuple[str, str, Writer, Reader], ...]] = (
    ("day_partition.day_files", TREE_DIR, _write_day, _days_walked),
)

READER_IDS: Final = tuple(name for name, *_ in READERS)


def _tree(tmp_path: Path, dirname: str, write: Writer, strays: Iterable[str]) -> Path:
    """A state directory holding one real day file, plus whatever else is asked for."""
    state = tmp_path / "state"
    root = state / dirname
    write(state, DAY)
    for relative in strays:
        entry = root / relative
        entry.parent.mkdir(parents=True, exist_ok=True)
        if entry.suffix:
            entry.write_text("header\n", encoding="utf-8")
        else:
            entry.mkdir(exist_ok=True)
    return state


@pytest.mark.parametrize(("name", "dirname", "write", "read"), READERS, ids=READER_IDS)
def test_every_day_tree_reader_names_the_one_day_the_tree_holds(
    tmp_path: Path,
    name: str,
    dirname: str,
    write: Writer,
    read: Reader,
) -> None:
    """The Oracle, first half: one file in, one day out, for every reader.

    No writer files this layout now, so the day is written in it by hand, the
    way the fitted line's writer filed one before it moved to the ledger door.
    """
    state = _tree(tmp_path, dirname, write, ())

    assert read(state) == [DAY], name


@pytest.mark.parametrize(("name", "dirname", "write", "read"), READERS, ids=READER_IDS)
@pytest.mark.parametrize("stray", STRAYS)
def test_every_day_tree_reader_refuses_the_same_names(
    tmp_path: Path,
    name: str,
    dirname: str,
    write: Writer,
    read: Reader,
    stray: str,
) -> None:
    """The Oracle, second half: the same four names stop every reader.

    Each case holds the good day file as well, so a refusal here is about the
    name and never about an empty tree. A reader that skipped the stray would
    return the good day and pass the half above while quietly reading a tree it
    cannot account for.
    """
    state = _tree(tmp_path, dirname, write, (stray,))

    with pytest.raises(ValueError, match="is not a YYYY/MM/DD day file"):
        read(state)


@pytest.mark.parametrize(("name", "dirname", "write", "read"), READERS, ids=READER_IDS)
def test_an_empty_month_directory_that_is_not_ascii_digits_is_refused(
    tmp_path: Path,
    name: str,
    dirname: str,
    write: Writer,
    read: Reader,
) -> None:
    """A stray with nothing in it is still a stray.

    This is the one input where the walk changed. `re.fullmatch(r"\\d{2}", ...)`
    accepted the directory name, the walk stepped into it, and an empty
    directory gave it nothing to refuse - so the stray survived every read. The
    refusal used to come from `date.fromisoformat` one level further down, and
    a level further down is a level that an empty directory never reaches.
    """
    state = _tree(tmp_path, dirname, write, (EMPTY_STRAY_MONTH,))

    with pytest.raises(ValueError, match="is not a YYYY/MM/DD day file"):
        read(state)


def test_the_refusal_names_the_tree_and_the_entry_in_posix_form(tmp_path: Path) -> None:
    """The message is the whole repair instruction, so it names both ends.

    POSIX separators and a relative path, because this string reaches a log
    (`CLAUDE.md` section 2). The tree is named from the path the reader was
    handed rather than from a constant, so a reader pointed at the wrong
    directory says which one it was really reading.
    """
    state = _tree(tmp_path, TREE_DIR, _write_day, ("notes.txt",))

    with pytest.raises(ValueError) as raised:
        _days_walked(state)

    assert "a-family/a-day-tree holds notes.txt" in str(raised.value)
    assert "\\" not in str(raised.value)


def test_a_fresh_clone_reads_no_days_and_is_not_a_fault(tmp_path: Path) -> None:
    """No history is what a new checkout has, and every reader answers it empty."""
    assert list(day_partition.day_files(tmp_path / "state" / TREE_DIR)) == []


def test_the_path_says_which_day_and_which_month_a_file_holds(tmp_path: Path) -> None:
    """`date_of` and `month_of` read the record, so nothing opens a file to ask.

    Both, in one test, because they are the same claim at two widths and a
    boundary is either a day or a month: the prune verb compares a day, and a
    window counted in months compares a month. Driven over the tree the walk
    returns rather than over a path the test spelled, so a layout change breaks
    this before it breaks a pruner.
    """
    state = _tree(tmp_path, TREE_DIR, _write_day, ())
    day = next(iter(day_partition.day_files(state / TREE_DIR)))

    assert day_partition.date_of(day) == DAY
    assert day_partition.month_of(day) == DAY[:7]
    assert day_partition.date_of(day).startswith(day_partition.month_of(day))


def test_a_window_names_both_of_its_ends(tmp_path: Path) -> None:
    """A cover of `n` days returns `n + 1` dates, newest first.

    Stated because moving this out of `ledger` made it a named public rule, and
    an off-by-one in a cover is a day the reader silently stops opening.
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
