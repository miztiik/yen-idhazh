"""What a `<YYYY>/<MM>/<DD>.csv` day tree is, in one place.

The peer of `month_partition`, and both stay live because both grains do. A
month stem is a filename, so one predicate settles it. A day is a path of three
segments, so the question is a walk: which entries the tree may hold, which it
refuses, and which days a window of `n` days names.

Two collections read a day tree today - `state/published/` and
`state/visual-prunes/` - and they read it through one private helper inside
`ledger`. More state ledgers are moving to this grain, so the helper comes out
here before it is imported from seven places. That is the shape
`month_partition` was created on 2026-09-08 to end: three directories each
carrying their own answer to "is this name a month", and one file left alone in
one store and deleted in another.

**Nothing inside a day tree is skipped.** A name this cannot place stops the
read. A glob answers "what matched" and says nothing about what did not, so a
file the reader cannot place would sit in a state directory unread and
unmentioned - which is how a reader starts missing rows with nobody noticing.

That is stricter than `month_partition`, and deliberately. A month directory is
the top of its own store and is allowed to hold something that is not the
collection at all. Below a year directory here, every name is written by one
`append_*` and by nothing else, so a name this walk cannot read means something
else is writing there.

**A segment is ASCII digits, and the clause is written out.** `\\d` in a `str`
pattern matches another script's numerals, so `re.fullmatch(r"\\d{2}", stem)`
takes a day stem in Arabic-Indic digits, and only `date.fromisoformat` then
refuses it - through how CPython compiles its own digit class rather than
through anything this module asked for. A detail of a parser is not a rule.
`month_partition.is_month_stem` states the same clause for the same reason.

The clause refuses one thing the regex version let through: an EMPTY directory
named in another script's numerals. The old walk entered it, found nothing to
refuse, and yielded nothing - a stray tolerated in a tree whose whole rule is
that nothing is tolerated.

`retention._dated_days` walks a different day tree and does not move here. Its
days are DIRECTORIES under `frontend/public/digest/` rather than CSV files, and
at its root it skips a name it cannot read instead of refusing it, because that
root is shared with things that are not the day tree. One walk per shape, for
the same reason there is one predicate per grain.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import NoReturn

#: A year is four digits; a month and a day are two.
YEAR_WIDTH = 4
SEGMENT_WIDTH = 2


def _is_segment(name: str, width: int) -> bool:
    """Exactly `width` ASCII digits.

    `str.isdigit` on its own accepts another script's numerals, and so does the
    `\\d` this replaced. The `isascii` clause is the load-bearing half.
    """
    return len(name) == width and name.isascii() and name.isdigit()


def _refuse_stray(entry: Path, root: Path) -> NoReturn:
    """Nothing inside a day tree may be ignored, so an odd name stops the read."""
    raise ValueError(
        f"{root.parent.name}/{root.name} holds "
        f"{entry.relative_to(root).as_posix()}, which is not a YYYY/MM/DD day file. "
        "A file the reader cannot place is how it starts missing rows, so it "
        "refuses the read rather than skipping the file."
    )


def day_files(root: Path) -> Iterator[Path]:
    """Every `<root>/YYYY/MM/DD.csv`, oldest first.

    Walked rather than globbed, so that every entry is accounted for and the
    ones this cannot place are refused rather than passed over.

    A missing directory yields nothing, because a clone with no history is what
    a fresh checkout has and not a fault.
    """
    if not root.is_dir():
        return
    for year in sorted(root.iterdir()):
        if not (year.is_dir() and _is_segment(year.name, YEAR_WIDTH)):
            _refuse_stray(year, root)
        for month in sorted(year.iterdir()):
            if not (month.is_dir() and _is_segment(month.name, SEGMENT_WIDTH)):
                _refuse_stray(month, root)
            for day in sorted(month.iterdir()):
                if not (day.is_file() and day.suffix == ".csv"):
                    _refuse_stray(day, root)
                if not _is_segment(day.stem, SEGMENT_WIDTH):
                    _refuse_stray(day, root)
                try:
                    date_type.fromisoformat(f"{year.name}-{month.name}-{day.stem}")
                except ValueError:
                    _refuse_stray(day, root)
                yield day


def days_in_window(today: str, within_days: int) -> list[str]:
    """The dates a cover of `within_days` names, newest first.

    **Both ends are named, so a cover of `n` returns `n + 1` dates.** That is
    the same arithmetic `ledger.shards_in_window` uses at month grain, and the
    two agree on purpose: a window of 90 days reaches back to the day 90 days
    ago and reads it, rather than stopping one short of it.

    Days rather than months, because a day tree files by day. Walking days
    rather than subtracting them from a calendar keeps the arithmetic honest
    across a month and a year boundary with no calendar table.
    """
    end = date_type.fromisoformat(today)
    return [(end - timedelta(days=offset)).isoformat() for offset in range(within_days + 1)]
