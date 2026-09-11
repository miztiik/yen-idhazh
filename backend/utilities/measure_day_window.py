"""What a 90-day window costs at month grain and at day grain, over the same rows.

The one figure `TODO/20260910-24-day-sharded-ledgers-plan.md` is priced against.
Five `state/` ledgers are moving from one file a month to one file a day, and
the windowed read trades **more file handles for fewer bytes**:
`collect.seen_window_days` is 90, so `ledger.load_seen` opens at most 4 month
files today and would open at most 91 day files - while 4 month shards can hold
up to 120 days of rows where 91 day files hold exactly 90. Which way that lands
on a runner is a measurement, and nobody had taken it.

Read-only, offline, and not a stage. It builds its own tree in a temporary
directory, reads it, and deletes it. It touches nothing under `state/`.

**Both arms read one row list, written twice.** The rows are identical; only the
layout differs. So a difference between the arms is the layout and cannot be the
data.

**The arms are interleaved in one process** - month, day, month, day - because a
stopwatch here measures the page cache as much as the code. The same bounded
reads over one fixture came out 16.6 percent apart a few minutes apart on this
project, and every arm that writes more files makes the tree warmer for whatever
runs next - `docs/reference/agent-notes/gates-and-builds.md` records it. Running
one arm to completion and then the other measures the order they ran in.

**Two of the three numbers have no spread.** Files opened and rows read are
arithmetic: a reader either opened a file or it did not. They settle the question
on their own if the clock is a wash, which is why they are reported first.

Usage, from the root of a checkout:

    python backend/utilities/measure_day_window.py

Exit code 0 whatever it finds. It reports a measurement; it does not grade one.
"""

from __future__ import annotations

import argparse
import csv
import platform
import statistics
import sys
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

from idhazh import day_partition, ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.seen import SeenRow

#: Days the fixture holds. Wider than the window, so the month arm's oldest
#: shard carries days the window never asked for - which is the whole trade.
DEFAULT_DAYS: Final = 120

#: `collect.seen_window_days` as the committed config ships it.
DEFAULT_WINDOW: Final = 90

#: The median day of the committed sight ledger on 2026-09-11: 67,205 rows over
#: 20 days, median 3,152. Taken from the real ledger so the fixture is the shape
#: this read meets, rather than a number somebody liked.
DEFAULT_ROWS_A_DAY: Final = 3152

#: Enough passes for a median and a spread, few enough to finish in a minute.
DEFAULT_REPEATS: Final = 9

#: The newest day of the fixture. Fixed rather than today's date, so two runs a
#: week apart measure the same tree.
ANCHOR: Final = "2026-09-07"


@dataclass(frozen=True, slots=True)
class Arm:
    """One layout's answer: what it opened, what it read, and how long it took."""

    grain: str
    files_opened: int
    rows_read: int
    millis: tuple[float, ...]

    @property
    def median_ms(self) -> float:
        return statistics.median(self.millis)

    @property
    def spread_ms(self) -> float:
        return max(self.millis) - min(self.millis)


def _days(anchor: str, count: int) -> list[str]:
    """`count` consecutive dates ending on `anchor`, oldest first."""
    end = date_type.fromisoformat(anchor)
    return [(end - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


def _rows(date: str, count: int) -> list[SeenRow]:
    """One day of first sights, addressed so no two days share a row."""
    return [
        SeenRow(
            version=SeenRow.schema_version(),
            url_key=derive_url_key(f"https://example.org/{date}/{number}"),
            first_seen_at=f"{date}T06:00:00Z",
            first_seen_run=f"{date}-1",
        )
        for number in range(count)
    ]


def _write_month_tree(state: Path, days: Iterable[str], rows_a_day: int) -> None:
    """`state/seen/<YYYY-MM>.csv`, through the ledger's own writer."""
    for date in days:
        ledger.append_seen(state, date, _rows(date, rows_a_day))


def _write_day_tree(state: Path, days: Iterable[str], rows_a_day: int) -> None:
    """`state/seen/<YYYY>/<MM>/<DD>.csv`, the same rows one layout over.

    Written here rather than by the ledger because no ledger files sight rows by
    day yet - that is the change this measurement exists to price. The columns
    come from the contract, so the bytes are the bytes a moved ledger would
    hold.
    """
    columns = SeenRow.csv_columns()
    for date in days:
        path = state / ledger.SEEN_DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            out = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            out.writeheader()
            for row in _rows(date, rows_a_day):
                payload = row.model_dump(mode="json")
                out.writerow({name: payload[name] for name in columns})


def _read_by_day(state: Path, *, today: str, within_days: int) -> dict[str, str]:
    """`ledger.load_seen`, one layout over.

    The same reduction against the same columns - earliest sight wins - so the
    only difference between the arms is which files it opens.
    """
    first_seen: dict[str, str] = {}
    root = state / ledger.SEEN_DIRNAME
    for date in day_partition.days_in_window(today, within_days):
        path = root / date[:4] / date[5:7] / f"{date[8:10]}.csv"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                url_key, at = row["url_key"], row["first_seen_at"]
                if url_key not in first_seen or at < first_seen[url_key]:
                    first_seen[url_key] = at
    return first_seen


def _month_paths(state: Path, today: str, within_days: int) -> list[Path]:
    root = state / ledger.SEEN_DIRNAME
    named = (root / f"{stem}.csv" for stem in ledger.shards_in_window(today, within_days))
    return [path for path in named if path.exists()]


def _day_paths(state: Path, today: str, within_days: int) -> list[Path]:
    root = state / ledger.SEEN_DIRNAME
    named = (
        root / date[:4] / date[5:7] / f"{date[8:10]}.csv"
        for date in day_partition.days_in_window(today, within_days)
    )
    return [path for path in named if path.exists()]


def _data_rows(paths: Iterable[Path]) -> int:
    total = 0
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            total += sum(1 for _ in csv.DictReader(handle))
    return total


def measure(*, days: int, window: int, rows_a_day: int, repeats: int) -> tuple[Arm, Arm]:
    """Build both trees, then read them alternately, and report each arm."""
    dates = _days(ANCHOR, days)
    with tempfile.TemporaryDirectory(prefix="day-window-") as scratch:
        root = Path(scratch)
        by_month = root / "month" / "state"
        by_day = root / "day" / "state"
        _write_month_tree(by_month, dates, rows_a_day)
        _write_day_tree(by_day, dates, rows_a_day)

        month_paths = _month_paths(by_month, ANCHOR, window)
        day_paths = _day_paths(by_day, ANCHOR, window)
        month_rows = _data_rows(month_paths)
        day_rows = _data_rows(day_paths)

        month_ms: list[float] = []
        day_ms: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            month_answer = ledger.load_seen(by_month, today=ANCHOR, within_days=window)
            month_ms.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            day_answer = _read_by_day(by_day, today=ANCHOR, within_days=window)
            day_ms.append((time.perf_counter() - start) * 1000)

            if len(day_answer) > len(month_answer):
                raise AssertionError(
                    "the day arm answered about more addresses than the month arm, "
                    "so the two trees do not hold the same rows and nothing below "
                    "is a measurement of the layout"
                )

    return (
        Arm("month", len(month_paths), month_rows, tuple(month_ms)),
        Arm("day", len(day_paths), day_rows, tuple(day_ms)),
    )


def report(month: Arm, day: Arm, *, window: int, days: int, rows_a_day: int) -> str:
    lines = [
        f"A {window}-day window over a {days}-day ledger of {rows_a_day} rows a day.",
        f"Anchor {ANCHOR}. {len(month.millis)} interleaved passes an arm.",
        f"{platform.platform()}, Python {platform.python_version()}.",
        "",
        f"{'':<8}{'files':>8}{'rows':>10}{'median ms':>12}{'spread ms':>12}",
    ]
    for arm in (month, day):
        lines.append(
            f"{arm.grain:<8}{arm.files_opened:>8}{arm.rows_read:>10}"
            f"{arm.median_ms:>12.1f}{arm.spread_ms:>12.1f}"
        )

    handles = day.files_opened - month.files_opened
    rows = month.rows_read - day.rows_read
    lines.append("")
    lines.append(
        f"The day arm opens {handles} more files and reads {rows} fewer rows - "
        "which is the trade, stated in the two numbers that have no spread."
    )

    gap = day.median_ms - month.median_ms
    widest = max(month.spread_ms, day.spread_ms)
    share = gap / month.median_ms * 100 if month.median_ms else 0.0
    verdict = "inside the spread, so the clock does not separate them"
    if abs(gap) > widest:
        slower = "slower" if gap > 0 else "faster"
        verdict = f"outside the spread: the day arm is {abs(share):.1f} percent {slower}"
    lines.append(f"The day arm's median is {gap:+.1f} ms against the month arm - {verdict}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument("--rows-a-day", type=int, default=DEFAULT_ROWS_A_DAY)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = parser.parse_args(argv)

    month, day = measure(
        days=args.days,
        window=args.window,
        rows_a_day=args.rows_a_day,
        repeats=args.repeats,
    )
    print(report(month, day, window=args.window, days=args.days, rows_a_day=args.rows_a_day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
