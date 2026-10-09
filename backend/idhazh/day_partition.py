"""What one `<YYYY>/<MM>/<DD>` date segment is, and which days a window of `n` days names.

The peer of `month_partition`, and both stay live because both grains do. A
month stem is a filename, so one predicate settles it. A day is a path of three
segments, so the questions here are what one segment may be, which empty date
folders a deleted file leaves behind, and which days a window names.

Every reader of a day folder asks this module what a segment is - the ledger
door's raw day folders (`ledger/raw_files.py`), the gardener's names-only walk
of them (`gardener/named_trees.py`) and the trial-ledger check
(`utilities/pipeline_test_ledgers.py`) - so the rule is written once.

**A segment is ASCII digits, and the clause is written out.** `\\d` in a `str`
pattern matches another script's numerals, so `re.fullmatch(r"\\d{2}", stem)`
takes a day stem in Arabic-Indic digits, and only `date.fromisoformat` then
refuses it - through how CPython compiles its own digit class rather than
through anything this module asked for. A detail of a parser is not a rule.
`month_partition.is_month_stem` states the same clause for the same reason.

`retention.dated_days` walks a different day tree and does not move here. Its
days are DIRECTORIES under `frontend/public/digest/`, and at its root it skips
a name it cannot read instead of refusing it, because that root is shared with
things that are not the day tree. One walk per shape, for the same reason there
is one predicate per grain.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

#: A year is four digits; a month and a day are two.
YEAR_WIDTH: Final = 4
SEGMENT_WIDTH: Final = 2


def is_segment(name: str, width: int) -> bool:
    """Exactly `width` ASCII digits.

    `str.isdigit` on its own accepts another script's numerals, and so does the
    `\\d` this replaced. The `isascii` clause is the load-bearing half.

    Public because every day-folder reader asks it. Two copies of this clause is
    the shape this module exists to end.
    """
    return len(name) == width and name.isascii() and name.isdigit()


def drop_empty_day_dirs(day: Path) -> None:
    """Remove every date directory a deleted file leaves empty behind it.

    Not tidiness: a reader of a day tree walks every year and month directory it
    finds, so a deletion that left them would make the walk cost more each year
    while removing the rows that walk exists to read.

    It climbs while the directory's own name is a date segment. A file inside a
    `<DD>/` day folder leaves a day, a month and a year; a published copy named
    for its month leaves nothing. A ledger root is never a date segment, so the
    climb stops there without being told where there is.

    Here rather than beside any one caller, because every task that deletes a
    dated file owes the same thing to the same walk. It was spelled twice until
    2026-09-16 - once in `retention` and once in `evals.writer`, whose copy said
    in its own docstring that it existed because `retention` imports that module
    rather than the other way round. A shape's rule belongs with the shape, and
    both of those modules already import this one.
    """
    directory = day.parent
    for _ in range(3):
        if not (
            is_segment(directory.name, SEGMENT_WIDTH) or is_segment(directory.name, YEAR_WIDTH)
        ):
            return
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent


def days_in_window(today: str, within_days: int) -> list[str]:
    """The dates a cover of `within_days` names, newest first.

    **Both ends are named, so a cover of `n` returns `n + 1` dates.** That is
    the same arithmetic `month_partition.shards_in_window` uses at month grain, and the
    two agree on purpose: a window of 90 days reaches back to the day 90 days
    ago and reads it, rather than stopping one short of it.

    Days rather than months, because a day tree files by day. Walking days
    rather than subtracting them from a calendar keeps the arithmetic honest
    across a month and a year boundary with no calendar table.
    """
    end = date_type.fromisoformat(today)
    return [(end - timedelta(days=offset)).isoformat() for offset in range(within_days + 1)]


def days_before(first_kept: date_type, lookback: int) -> list[date_type]:
    """The `lookback` days immediately before an exclusive boundary, oldest first."""
    if lookback < 1:
        raise ValueError("day lookback must be at least one")
    return [
        first_kept - timedelta(days=offset)
        for offset in range(lookback, 0, -1)
    ]