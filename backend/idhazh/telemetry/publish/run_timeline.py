"""Publish where one run's time went, item by item, a month at a time.

`RunTimelineRow` settled the shape and left the writer open
(`docs/architecture/publishing/run-timeline.md`). This is the writer. It reads
the per-item census under `state/item-health/` - a day tree, bounded to the days
of one month - and writes `frontend/public/run-timeline/<YYYY-MM>.csv`.

**One ledger, not two.** The contract's step 7 takes its NAME from
`EvalRow.score_ms`, and the value is not a second measurement: `stages/work.py`
times the scorers once and files that same integer as `faithfulness_ms` on the
census row. Joining the score ledger would open a second file a day to read a
number already in the first, and the census copy is the one that matters here
because it is the copy taken inside the item's own clock - so it is the copy
`item_total_ms` already contains, and a residual is only honest when every step
subtracted from a total was counted inside it.

**There is no `state/run-timeline/`.** The contract left the choice open and this
takes the published mirror alone, because every cell is already committed
elsewhere: six durations the census holds, and two numbers that are arithmetic
over them. A committed ledger would be a third copy of numbers git already
carries, and re-deriving it costs one month of day files.

**The run's zero is the earliest item start in that run, not the manifest's.**
The manifest's `started_at` is when the process began, which covers collecting
feeds and planning the day - work no item is charged for and no bar can draw. A
zero there would push every bar right by one constant and make x=0 a moment the
chart never shows. The earliest item start makes x=0 the moment the first item
began, which is the moment the queue starts forming.

**A row with no clock produces no row.** An item the planner listed and no shard
ever picked up has no start, no total and no shard, so it has no bar - and the
contract says an absent row reads as never worked, which is exactly true of it.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Iterable, Mapping
from datetime import date as date_type
from datetime import datetime
from pathlib import Path
from typing import Final

from idhazh import day_shards, ledger
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.run_timeline import RunTimelineRow
from idhazh.telemetry.publish import series

DIRNAME: Final = series.RUN_TIMELINE_DIRNAME
SUFFIX: Final = ".csv"
PUBLIC_COLUMNS: Final[tuple[str, ...]] = RunTimelineRow.csv_columns()

#: Which census column fills which step, in the order the pipeline runs them.
#: Five of the six are an identity on purpose - a rename on either side has to be
#: a rename on both, or a reader comparing a bar against the census is comparing
#: two spellings of one number. The sixth is the pair above: the step is called
#: `score_ms` because that is what the eval ledger calls the scorers' clock, and
#: the census files the same stopwatch as `faithfulness_ms`.
CENSUS_STEPS: Final[Mapping[str, str]] = {
    "fetch_ms": "fetch_ms",
    "extract_ms": "extract_ms",
    "label_ms": "label_ms",
    "summary_ms": "summary_ms",
    "visual_plan_ms": "visual_plan_ms",
    "score_ms": "faithfulness_ms",
}

#: The two steps this writer leaves empty on every row, because nothing in the
#: pipeline times either one. Named rather than implied: a consumer has to be
#: able to ask which columns are absent by design and which are absent because a
#: run failed, and those are different sentences to put on a page.
UNTIMED_STEPS: Final[tuple[str, ...]] = ("plan_ms", "publish_ms")

__all__ = [
    "CENSUS_STEPS",
    "DIRNAME",
    "PUBLIC_COLUMNS",
    "SUFFIX",
    "UNTIMED_STEPS",
    "project",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one run-timeline month."""
    return series.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/run-timeline/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return series.relpath(DIRNAME, f"{month}{SUFFIX}")


def _whole(cell: str | None) -> int | None:
    """A whole count, or None where the cell holds no number."""
    if cell is None or cell == "":
        return None
    try:
        return int(cell)
    except ValueError:
        return None


def _epoch_ms(cell: str | None) -> int | None:
    """A recorded timestamp as milliseconds, or None where the cell is empty.

    The census writes UTC at second precision, so every offset derived from it is
    a whole number of seconds. That is the resolution the pipeline recorded and
    the panel says so; inventing anything finer here would be precision nobody
    measured (`CLAUDE.md` Guardrail #10).
    """
    if cell is None or cell == "":
        return None
    try:
        return int(datetime.fromisoformat(cell.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def project(census: Iterable[Mapping[str, str]]) -> list[RunTimelineRow]:
    """One day of census rows placed on their own runs' clocks.

    Rows in, one list out, and nothing opened - so a test drives this from a
    list, and the caller decides which day it settled and read.

    The rows come back grouped by run and ordered by where each bar starts, which
    is the order the chart draws them in. Sorting here means the published file is
    already in reading order and a browser sorts nothing.
    """
    rows = list(census)

    timed: list[tuple[str, Mapping[str, str], int, int, int]] = []
    for row in rows:
        started = _epoch_ms(row.get("item_started_at"))
        total = _whole(row.get("item_total_ms"))
        shard = _whole(row.get("shard"))
        run_id = row.get("run_id") or ""
        if started is None or total is None or shard is None or run_id == "":
            continue
        timed.append((run_id, row, started, total, shard))

    zero: dict[str, int] = {}
    for run_id, _row, started, _total, _shard in timed:
        zero[run_id] = min(zero.get(run_id, started), started)

    built = [
        RunTimelineRow.model_validate(
            {
                "date": row["date"],
                "run_id": run_id,
                "shard": shard,
                "item_id": row["item_id"],
                "start_offset_ms": started - zero[run_id],
                "item_total_ms": total,
                **{column: _whole(row.get(source)) for column, source in CENSUS_STEPS.items()},
            }
        )
        for run_id, row, started, total, shard in timed
    ]
    built.sort(key=lambda made: (made.run_id, made.start_offset_ms, made.item_id))
    return built


def read_shard(path: Path) -> list[RunTimelineRow]:
    """Load a published shard back through the contract that wrote it."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [RunTimelineRow.from_csv_row(row) for row in reader]


def _month_rows(census_root: Path, dates: Iterable[str]) -> Iterable[Mapping[str, str]]:
    """Every cell of one month, in day order, as the strings a shard holds.

    Each day is settled before it is projected. A day is a directory of
    writer-owned files and a re-run leaves a second attempt beside the first, so
    projecting every file would draw one item's bar twice.
    """
    for date in dates:
        settled = day_shards.settled_day(
            census_root, date, ledger.ITEM_HEALTH_KEY, ItemHealthRow
        )
        for row in project(settled):
            yield row.csv_row()


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date_type,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published run-timeline shard for each census month that changed.

    The census files by day and this mirror files by month, the same pair
    `public_telemetry` already draws and for the same reason: a run writes one
    day, and a browser fetches one month. So a named month opens at most 31
    census files whatever the archive grows to (`CLAUDE.md` Guardrail #12).
    """
    census_root = state_root / ledger.ITEM_HEALTH_DIRNAME
    by_month = day_shards.dates_by_month(census_root, days=UNBOUNDED_WINDOW)

    def encode(month: str) -> bytes:
        return series.encode_csv(
            PUBLIC_COLUMNS, _month_rows(census_root, by_month.get(month, []))
        )

    return series.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=sorted(by_month),
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
