"""Does every column the pipeline publishes say which surface reads it?

A column is cheap to add and invisible to forget. It costs a cell on every row
of every run from the day it lands, and nothing about a run goes wrong when
nobody draws it - so an orphan column is found by a person wondering, years
later, what a heading was for. This module is that wondering, done once, as a
rule: every column of `ItemHealthRow` and `HostFingerprintRow` is named exactly
once by `COLUMN_READERS`, or named exactly once by `UNREAD_CELLS` under the
question it would answer if a surface drew it.

**What it settles.** A column minted with no entry fails here, naming the column.
A column deleted while an entry still names it fails here too. And a reader file
that is renamed or removed fails here, naming both sides - so a map that has
rotted is found by the suite rather than by the next person to read it.

**What it cannot settle**, and neither can any test:

- Whether the named surface still DRAWS the value. It checks the file still
  names the column, which a file can do in a dead branch. The browser check is
  what reads the page (CLAUDE.md section 12).
- Whether a column is EMPTY on every committed row. That answer costs a walk of
  the whole archive, which section 13 forbids a test, and it has a fuse besides:
  an assertion that a column is empty goes red on the day it first fills, which
  is a date on the calendar rather than an edit anybody made. It lives in
  `backend/utilities/empty_column_census.py` instead.

Every read here is over the declared list and is fixed in size: one file open per
named reader, about twenty of them, whatever the archive has grown to.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.host_fingerprint import COLUMN_READERS as HOST_READERS
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import COLUMN_READERS as ITEM_READERS
from idhazh.contracts.item_health import UNREAD_CELLS, ItemHealthRow

pytestmark = pytest.mark.contract

#: A column no surface reads, invented here and nowhere else. It is the proof
#: that the rule below bites: hand it to the same checker the real rows use and
#: the checker must name it.
A_COLUMN_NOBODY_READS: Final = "a_column_nobody_reads"


def reader_faults(
    readers: Mapping[str, Sequence[str]],
    unread: Mapping[str, Sequence[str]],
    columns: Sequence[str],
) -> tuple[str, ...]:
    """Every way the two maps and the row's own column list can disagree.

    One pass, three faults, each naming what to do about it. Returning them all
    beats raising on the first: a person who has just renamed six columns wants
    the six, not one of them six times.
    """
    claimed = Counter(
        name for names in (*readers.values(), *unread.values()) for name in names
    )
    known = set(columns)
    faults = [
        f"{name} is a column of this row and no entry names it -"
        " add it to COLUMN_READERS under the surface that reads it,"
        " or to UNREAD_CELLS under the question it would answer"
        for name in columns
        if name not in claimed
    ]
    faults += [
        f"{name} is named {count} times - a column names one reader,"
        " the one that would notice first if the column stopped arriving"
        for name, count in sorted(claimed.items())
        if count > 1
    ]
    faults += [
        f"{name} is named but is not a column of this row -"
        " drop the entry, or correct the spelling"
        for name in sorted(claimed)
        if name not in known
    ]
    return tuple(faults)


def test_every_item_health_column_names_a_reader_or_the_question_it_would_answer() -> (
    None
):
    faults = reader_faults(
        ITEM_READERS, UNREAD_CELLS, tuple(ItemHealthRow.csv_columns())
    )
    assert not faults, "\n".join(faults)


def test_every_host_fingerprint_column_names_a_reader() -> None:
    faults = reader_faults(HOST_READERS, {}, tuple(HostFingerprintRow.csv_columns()))
    assert not faults, "\n".join(faults)


def test_the_rule_bites_when_a_column_arrives_naming_nobody() -> None:
    """The oracle. Add a column to the row and name no reader for it.

    The two tests above pass today, which says nothing about whether they could
    fail. This one adds a column the maps have never heard of and holds the
    checker to naming it - so the green above is a reading rather than a habit.

    It looks for its own fault rather than counting them, so that a real fault
    in the maps fails the tests that own it and leaves this one saying what it
    came to say.
    """
    columns = (*ItemHealthRow.csv_columns(), A_COLUMN_NOBODY_READS)

    faults = reader_faults(ITEM_READERS, UNREAD_CELLS, columns)

    named = [
        fault
        for fault in faults
        if fault.startswith(f"{A_COLUMN_NOBODY_READS} is a column of this row")
    ]
    assert len(named) == 1, faults
    assert "add it to COLUMN_READERS" in named[0]


def test_the_rule_bites_when_an_entry_outlives_its_column() -> None:
    """The other direction: a column deleted while an entry still names it."""
    dropped, *kept = ItemHealthRow.csv_columns()

    faults = reader_faults(ITEM_READERS, UNREAD_CELLS, kept)

    named = [
        fault
        for fault in faults
        if fault.startswith(f"{dropped} is named but is not a column of this row")
    ]
    assert len(named) == 1, faults


@pytest.mark.parametrize(
    ("readers", "row"),
    [
        pytest.param(ITEM_READERS, "ItemHealthRow", id="item-health"),
        pytest.param(HOST_READERS, "HostFingerprintRow", id="host-fingerprint"),
    ],
)
def test_a_named_reader_exists_and_still_names_its_columns(
    readers: Mapping[str, Sequence[str]], row: str
) -> None:
    """Fixed size by construction: one file open per named reader, no walk.

    The file is read here rather than at import so that an unreadable path fails
    this test alone, naming the path, instead of raising while the module loads
    and taking every test in the file with it (CLAUDE.md section 13).
    """
    faults: list[str] = []
    for reader, columns in readers.items():
        path = Path(REPO_ROOT, reader)
        if not path.is_file():
            faults.append(f"{row}: {reader} is named as a reader and does not exist")
            continue
        text = read_text(path)
        faults += [
            f"{row}: {reader} is named as the reader of {name} and does not name it"
            for name in columns
            if not re.search(rf"\b{re.escape(name)}\b", text)
        ]
    assert not faults, "\n".join(faults)


def test_the_unread_columns_are_grouped_by_a_question_a_person_can_read() -> None:
    """A heading that is a category name tells the next person nothing.

    The list exists to be emptied, and it is emptied by somebody reading a
    heading and deciding it is worth a panel. `scores` is not that heading; a
    sentence about what the reader would learn is.
    """
    too_short = [
        question for question in UNREAD_CELLS if len(question.split()) < 5
    ]
    assert not too_short, too_short
