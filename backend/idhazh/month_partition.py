"""What a `<YYYY-MM>` partition file is called, in one place.

Six directories used to be pruned by month - `state/seen/`, `state/feed-health/`,
`state/item-health/`, `state/item-health-summary/`, `state/scores/` and the
scores ledger's month summaries, plus the browser's copy under
`frontend/public/telemetry/` - and each one used to carry its own answer to "is
this name a month?". The answers disagreed. Measured 2026-09-08: `retention`
refused `2025-13`, `2025-00`, `0000-01` and a stem written in Arabic-Indic
digits, while `evals.writer` and the month summaries' reader accepted all four.
So `2025-13.csv` was left alone in `state/feed-health/` and was summarised and
then DELETED in `state/scores/` - one name, two dispositions, and the
destructive one landing on the ledger that holds the evidence behind every
published quality claim.

**`state/feed-health/` files by day now**, so it walks through `day_partition`
instead and the month rule no longer reaches it. The item-health, scores and
first-sight ledgers are filed by day through the ledger door under `state/raw/`,
so it does not reach them either. The feed-health prune and the item-health
compaction still take a month at a time, because a keep-months knob is a month
boundary whatever the files below it are - and that boundary is arithmetic on a
date rather than a filename, so it needs nothing from here.

**The rule is a real calendar month, spelled in ASCII, seven characters wide.**
`str.isdigit` and `int` both accept another script's numerals, so a stem in
Arabic-Indic digits reads as 2025-01 to a naive check while the writer names its
own file `2025-01`. That is two files claiming one month, and a prune would
summarise over one of them. The ASCII check is written out rather than left to
the date parser: CPython refuses that stem today, but through a detail of how
the parser compiles its digit class rather than through anything this module
asked for, and a detail is not a rule.

**A name this does not recognise is left alone.** It is not deleted and it is
not a fault. These directories are the top of their own ledger, and the stricter
rule the published day tree uses - below a dated level an unreadable name raises
(`retention.dated_days`) - stops at a root by design, because a root is allowed
to hold things that are not the partitioned tree at all.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
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


def months_between(first: str, last: str) -> list[str]:
    """Every real calendar month in the inclusive, caller-named range."""
    if not is_month_stem(first) or not is_month_stem(last):
        raise ValueError("month range endpoints must be real YYYY-MM dates")
    if first > last:
        raise ValueError(f"month range starts after it ends: {first} > {last}")

    year, month = map(int, first.split("-"))
    end_year, end_month = map(int, last.split("-"))
    months: list[str] = []
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def month_files(directory: Path, suffix: str) -> list[Path]:
    """Every `<YYYY-MM><suffix>` in one directory, oldest first, and nothing else.

    One listing of the directory, then a sort of the names it returned - so the
    cost is the ledger's own contents and never what sits beside it. An absent
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
    is how one ledger deletes a month the other still serves.
    """
    if months < 1:
        raise ValueError("keeping fewer than one month would delete the month being written")
    total = today.year * 12 + (today.month - 1) - (months - 1)
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def shards_in_window(today: str, within_days: int) -> list[str]:
    """The month stems a window of days can touch, newest first.

    **No ledger is read with this any more.** Every windowed read in this
    repository files by day and takes `day_partition.days_in_window` -
    `drift.read_windows` was the last month-grained one and moved on 2026-09-13
    with `state/scores/`.

    What it still answers is the question the `keep_months` knobs are sized
    against: how many month-shaped buckets a day-counted window reaches. That is
    why the telemetry-aggregate task keeps 14 months and not 13 against a
    366-day `console.max_window_days`, and `contracts.app_config` states the
    rule while `tests/contracts/` and `tests/retention/` drive it. A grain change
    does not touch it, because both knobs are still counted in months.

    Walking days rather than subtracting months keeps the arithmetic honest
    across a year boundary and needs no calendar table.
    """
    end = date.fromisoformat(today)
    stems: list[str] = []
    for offset in range(within_days + 1):
        stem = (end - timedelta(days=offset)).isoformat()[:7]
        if stem not in stems:
            stems.append(stem)
    return stems
