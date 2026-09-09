"""What a `<YYYY-MM>` partition file is called, in one place.

Six directories are pruned by month - `state/seen/`, `state/feed-health/`,
`state/item-health/`, `state/telemetry-aggregate/`, `state/scores/` and
`state/score-archive/`, plus the browser's copy under
`frontend/public/telemetry/` - and each one used to carry its own answer to "is
this name a month?". The answers disagreed. Measured 2026-09-08: `retention`
refused `2025-13`, `2025-00`, `0000-01` and a stem written in Arabic-Indic
digits, while `evals.writer` and `evals.archive` accepted all four. So
`2025-13.csv` was left alone in `state/feed-health/` and was archived and then
DELETED in `state/scores/` - one name, two dispositions, and the destructive one
landing on the store that holds the evidence behind every published quality
claim.

**The rule is a real calendar month, spelled in ASCII, seven characters wide.**
`str.isdigit` and `int` both accept another script's numerals, so a stem in
Arabic-Indic digits reads as 2025-01 to a naive check while the writer names its
own file `2025-01`. That is two files claiming one month, and a prune would
summarise over one of them. The ASCII check is written out rather than left to
the date parser: CPython refuses that stem today, but through a detail of how
the parser compiles its digit class rather than through anything this module
asked for, and a detail is not a rule.

**A name this does not recognise is left alone.** It is not deleted and it is
not a fault. These directories are the top of their own store, and the stricter
rule the published day tree uses - below a dated level an unreadable name raises
(`retention._dated_days`) - stops at a root by design, because a root is allowed
to hold things that are not the partitioned tree at all.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Final

#: `YYYY-MM` - four digits, a hyphen, two digits.
STEM_WIDTH: Final = 7


def is_month_stem(stem: str) -> bool:
    """True only for a real calendar month written `YYYY-MM` in ASCII.

    Every clause refuses something the others let through. The width and the
    hyphen refuse `2025-1`, which the date parser accepts. `isascii` refuses
    another script's numerals. The parse refuses `2025-00`, `2025-13` and
    `0000-01`, which are seven ASCII characters in the right shape and no month
    anything here ever wrote.
    """
    if len(stem) != STEM_WIDTH or stem[4] != "-" or not stem.isascii():
        return False
    try:
        datetime.strptime(stem, "%Y-%m")
    except ValueError:
        return False
    return True


def month_files(directory: Path, suffix: str) -> list[Path]:
    """Every `<YYYY-MM><suffix>` in one directory, oldest first, and nothing else.

    One listing of the directory, then a sort of the names it returned - so the
    cost is the store's own contents and never what sits beside it. An absent
    directory is not an error: a fresh clone has no history, and no history is
    not a fault.
    """
    if not directory.is_dir():
        return []
    found = [path for path in directory.glob(f"*{suffix}") if is_month_stem(path.stem)]
    return sorted(found, key=lambda path: path.stem)


def oldest_month_kept(today: date, months: int) -> str:
    """The oldest `YYYY-MM` stem an age of `months` still keeps.

    Counted in months rather than in thirty-day steps, because the thing being
    kept is a month file and a month is not thirty days. `months` counts the
    month being written as one of them, so 13 on any day of August 2026 keeps
    `2025-08` through `2026-08` - a whole year of complete months plus the
    partial one.

    It lives here rather than inside one prune because the state ledgers and the
    published tree now age by the same arithmetic, and a boundary computed twice
    is how one store deletes a month the other still serves.
    """
    if months < 1:
        raise ValueError("keeping fewer than one month would delete the month being written")
    total = today.year * 12 + (today.month - 1) - (months - 1)
    return f"{total // 12:04d}-{total % 12 + 1:02d}"
