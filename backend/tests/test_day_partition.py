"""One rule for every `state/` day tree, held to by every reader of one.

The day-side twin of `test_retention.test_the_month_readers_all_agree_on_what_a
_month_is`, which found three month readers disagreeing on 2026-09-08 and one
file left alone in one store and deleted in another.

**Behaviour rather than identity.** Asserting that two names point at one
function proves nothing about a third place that reimplemented the walk, and a
reimplemented walk is the whole failure. So every reader is driven over a real
tree and asked what it did.

**The set is the readers of a `<YYYY>/<MM>/<DD>.csv` tree under `state/`.**
There is one other day walk in the repository and it is deliberately not in
here: `retention._dated_days` reads `frontend/public/digest/`, where a day is a
DIRECTORY holding a payload rather than a CSV file, and at its root it skips a
name it cannot read instead of refusing it. Driven over these trees it would
refuse the good day file too, because `07.csv` is not a day directory. A
different shape answering a different question is not a disagreement.

Every tree here is built under `tmp_path` from the constants below, so these
checks cost the same on the day `state/published/` holds ten times the days
(`CLAUDE.md` Rule #12, section 13). A built tree also carries the four cases the
committed ledgers have never produced and never will.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_partition, ledger
from idhazh.contracts.app_config import UNBOUNDED_WINDOW
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.seen import PublishedRow
from idhazh.contracts.visual_prune import VisualPruneRow

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


def _write_published(root: Path, date: str) -> None:
    ledger.append_published(
        root.parent,
        date,
        [
            PublishedRow(
                version=PublishedRow.schema_version(),
                url_key=derive_url_key("https://example.org/items/one"),
                published_on=date,
                item_id="ai-01",
            )
        ],
    )


def _write_prune(root: Path, date: str) -> None:
    ledger.append_visual_prunes(
        root.parent,
        date,
        [
            VisualPruneRow(
                version=VisualPruneRow.schema_version(),
                date=date,
                run_id=f"{date}-1",
                policy_months=-1,
                max_deletes_per_run=200,
                dry_run=True,
                candidates_found=0,
                deleted=0,
                skipped_by_fuse=0,
                fuse_tripped=False,
                bytes_reclaimed=0,
                oldest_kept=None,
                payload_bytes_before=1000,
                payload_bytes_after=1000,
            )
        ],
    )


def _days_published(state: Path) -> list[str]:
    return sorted(ledger.load_published(state, today=None, within_days=UNBOUNDED_WINDOW).values())


def _days_pruned(state: Path) -> list[str]:
    return sorted(row.date for row in ledger.load_visual_prunes(state))


def _days_walked(state: Path) -> list[str]:
    root = state / ledger.PUBLISHED_DIRNAME
    return sorted(
        f"{path.parent.parent.name}-{path.parent.name}-{path.stem}"
        for path in day_partition.day_files(root)
    )


#: Every reader of a `state/` day tree: the directory it owns, the writer that
#: puts one day in it, and the read that says which days it found.
#:
#: A row is added here when a reader is added, and that is the point - a reader
#: this table does not drive is the reader that starts disagreeing.
Writer = Callable[[Path, str], None]
Reader = Callable[[Path], list[str]]

READERS: Final[tuple[tuple[str, str, Writer, Reader], ...]] = (
    ("day_partition.day_files", ledger.PUBLISHED_DIRNAME, _write_published, _days_walked),
    ("ledger.load_published", ledger.PUBLISHED_DIRNAME, _write_published, _days_published),
    ("ledger.load_visual_prunes", ledger.VISUAL_PRUNES_DIRNAME, _write_prune, _days_pruned),
)

READER_IDS: Final = tuple(name for name, *_ in READERS)


def _tree(tmp_path: Path, dirname: str, write: Writer, strays: Iterable[str]) -> Path:
    """A state directory holding one real day file, plus whatever else is asked for."""
    state = tmp_path / "state"
    root = state / dirname
    write(root, DAY)
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

    The day is written by the ledger's own writer rather than spelled out here,
    so the assertion is that the reader and the writer agree about the layout
    and not that both agree with a third copy of it in a test.
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

    Each arm holds the good day file as well, so a refusal here is about the
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
    state = _tree(tmp_path, ledger.PUBLISHED_DIRNAME, _write_published, ("notes.txt",))

    with pytest.raises(ValueError) as raised:
        _days_published(state)

    assert "state/published holds notes.txt" in str(raised.value)
    assert "\\" not in str(raised.value)


def test_a_fresh_clone_reads_no_days_and_is_not_a_fault(tmp_path: Path) -> None:
    """No history is what a new checkout has, and every reader answers it empty."""
    assert list(day_partition.day_files(tmp_path / "state" / ledger.PUBLISHED_DIRNAME)) == []


def test_a_window_names_both_of_its_ends(tmp_path: Path) -> None:
    """A cover of `n` days returns `n + 1` dates, newest first.

    Stated because moving this out of `ledger` made it a named public rule, and
    an off-by-one in a cover is a day the reader silently stops opening.
    `ledger.shards_in_window` counts the same way at month grain.
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
