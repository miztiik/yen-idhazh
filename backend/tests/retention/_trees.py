"""Tree builders and clocks more than one retention module needs."""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import day_partition, ledger
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import (
    TERMINAL_STAGES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.measured import SITE_GROWTH_KB_A_DAY
from idhazh.measured import WARNING_DAYS_REQUIRED as WARNING_DAYS

#: The widest span the console's control can select, from the config that owns
#: it. The prune may never delete a shard a read that wide names.
CONSOLE_MAX_WINDOW_DAYS: Final = ConsoleConfig().max_window_days


#: The run every row these tests write is filed under. One value, so a test that
#: writes twice is writing a repeat rather than a second run.
RUN_ID: Final = "2026-08-30-33270983446"


#: The same, for the cleanup tests below, which run against the day the rest of
#: that section already uses.
PRUNE_RUN_ID: Final = "2026-08-21-33270983446"


def site(root: Path, days: dict[str, list[str]]) -> Path:
    for day, files in days.items():
        year, month, number = day.split("-")
        folder = root / year / month / number
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "digest.json").write_text(f'{{"date": "{day}"}}', encoding="utf-8")
        for name in files:
            (folder / name).write_bytes(b"x" * 1000)
    return root


#: Both records, and what to do when either bites, are in `idhazh.measured` -
#: the one place a measured number and its provenance live together.
FASTEST_MEASURED_KB_PER_DAY = int(SITE_GROWTH_KB_A_DAY.value)

WARNING_DAYS_REQUIRED = int(WARNING_DAYS.value)


def days_of_warning(budget_mb: int, kb_per_day: int) -> int:
    """Whole days from the alarm to the wall. A partial day is not a day."""
    return (PAGES_HARD_CAP_MB - budget_mb) * 1024 // kb_per_day


#: The day the fold is run against in every test below, and the twenty months of
#: history it is run over. Twenty rather than fourteen so both sides of the
#: threshold carry several months: at `item_health_full_grain_months` 14 the fold
#: takes six and leaves fourteen, and a threshold off by one shows up as a shard
#: on the wrong side rather than as an empty result.
TODAY: Final = date(2026, 8, 30)

HISTORY_MONTHS: Final = 20


#: How far down the pipeline each terminal stage got, so a row carries the clocks
#: an item that really stopped there would have carried and no others.
STAGES_REACHED: Final = {
    ItemStage.PLAN: (),
    ItemStage.FETCH: ("fetch_ms",),
    ItemStage.EXTRACT: ("fetch_ms", "extract_ms"),
    ItemStage.SUMMARIZE: ("fetch_ms", "extract_ms", "summarize_ms"),
    ItemStage.PUBLISH: ("fetch_ms", "extract_ms", "summarize_ms"),
}

CLOCK_MS: Final = {"fetch_ms": 900, "extract_ms": 1_400, "summarize_ms": 62_000}


#: A failure code each stage really produces. `plan` is a refusal and `publish`
#: is the census's one unambiguous success, so the two ends differ.
STAGE_FAILURE: Final = {
    ItemStage.PLAN: FailureCode.NOT_ATTEMPTED,
    ItemStage.FETCH: FailureCode.HTTP_SERVER_ERROR,
    ItemStage.EXTRACT: FailureCode.PAYWALLED,
    ItemStage.SUMMARIZE: FailureCode.BAD_SHAPE,
    ItemStage.PUBLISH: None,
}


#: The same stages in funnel order. `TERMINAL_STAGES` is a set, and a row's item
#: number is derived from a stage's position, so the census fixture needs the
#: order the enum declares. Deriving it from the enum rather than restating it
#: means a stage added to the terminal set lands here and fails on the two maps
#: above, which is the question a new terminal stage owes an answer to.
TERMINAL_ORDER: Final = tuple(stage for stage in ItemStage if stage in TERMINAL_STAGES)


def months_back(today: date, count: int) -> list[str]:
    """`YYYY-MM` stems, oldest first, ending on the month `today` sits in."""
    total = today.year * 12 + (today.month - 1)
    return [
        f"{(total - offset) // 12:04d}-{(total - offset) % 12 + 1:02d}"
        for offset in reversed(range(count))
    ]


def health_row(*, day: str, run: int, number: int, stage: ItemStage) -> ItemHealthRow:
    """One census row, shaped the way the contract's own validators demand."""
    code = STAGE_FAILURE[stage]
    # A slower item every third one, so a percentile has something to separate.
    stretch = 1 + (number % 3)
    reached = STAGES_REACHED[stage]

    def clock(name: str) -> int | None:
        return CLOCK_MS[name] * stretch if name in reached else None

    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=day,
        run_id=f"{day}-{run}",
        item_id=f"ai-{number:04d}",
        url_key=hashlib.sha256(f"{day}-{number}".encode("ascii")).hexdigest(),
        canonical_url=f"https://example.test/{day}/{number}",
        vertical="ai",
        source_id="example",
        stage=stage,
        outcome=ItemOutcome.OK if code is None else ItemOutcome.FAILED,
        code=code,
        fetch_ms=clock("fetch_ms"),
        extract_ms=clock("extract_ms"),
        summarize_ms=clock("summarize_ms"),
    )


def item_health_history(state_dir: Path, months: list[str]) -> None:
    """A real item-health shard per month, written through the real appender."""
    for index, month in enumerate(months):
        for day_of_month in (4, 17):
            day = f"{month}-{day_of_month:02d}"
            rows = [
                health_row(day=day, run=1, number=index * 100 + position, stage=stage)
                for position, stage in enumerate(TERMINAL_ORDER)
            ]
            # A second run of the same day, so the fold meets the repeated
            # `(date, run_id, item_id)` keys the committed ledger really carries.
            rows.append(
                health_row(day=day, run=2, number=index * 100 + 50, stage=ItemStage.PUBLISH)
            )
            ledger.append_item_health(state_dir, day, rows)


def totals_from_shard(texts: Iterable[str]) -> dict[tuple[str, str], tuple[int, int, int]]:
    """Rows, failures and total milliseconds per (date, stage), read off the CSVs.

    Recomputed here from the raw text rather than by calling `fold_month`, so the
    oracle cannot pass by agreeing with the code it is checking. It takes a
    month's day files together, because a month is what one aggregate covers.
    """
    totals: dict[tuple[str, str], tuple[int, int, int]] = {}
    for text in texts:
        for row in csv.DictReader(io.StringIO(text)):
            key = (row["date"], row["stage"])
            rows, failures, elapsed = totals.get(key, (0, 0, 0))
            spent = sum(
                int(row[name]) for name in ("fetch_ms", "extract_ms", "summarize_ms") if row[name]
            )
            totals[key] = (rows + 1, failures + (row["outcome"] != "ok"), elapsed + spent)
    return totals


def item_health_days(state_dir: Path) -> list[Path]:
    """Every item-health day file, oldest first, through the pipeline's own walk."""
    return list(day_partition.day_files(state_dir / ledger.ITEM_HEALTH_DIRNAME))


def item_health_months(state_dir: Path) -> list[str]:
    """Which months the item-health day tree still holds, oldest first.

    The boundary the prune works on is still a month; only the files below it are
    days, so a test about what the prune kept asks in months.
    """
    return sorted(day_partition.days_by_month(state_dir / ledger.ITEM_HEALTH_DIRNAME))


def totals_from_aggregate(
    rows: list[TelemetryAggregateRow],
) -> dict[tuple[str, str], tuple[int, int, int]]:
    return {(row.date, row.stage.value): (row.items, row.failed, row.sum_ms or 0) for row in rows}


def a_state_tree(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    item_health_history(state, months_back(TODAY, HISTORY_MONTHS))
    return state


#: Names of the right width and shape that are not a month. Every one was
#: accepted by at least one month reader and refused by another before
#: 2026-09-08, which is what made the same file survive in one store and get
#: deleted in the next.
NOT_MONTHS: Final = (
    "2025-00",
    "2025-13",
    "0000-01",
    #: `2025-01` in Arabic-Indic digits. `str.isdigit` and `int` both read this
    #: as January 2025, so a naive check finds two files claiming one month.
    "\u0662\u0660\u0662\u0665-\u0660\u0661",
)

def feed_health_history(state_dir: Path, months: list[str], *, day_of_month: int = 11) -> None:
    """A real feed-health day file per month, written through the real appender."""
    for index, month in enumerate(months):
        day = f"{month}-{day_of_month:02d}"
        ledger.append_health(
            state_dir,
            day,
            [
                FeedHealthRow(
                    version=FeedHealthRow.schema_version(),
                    run_id=f"{day}-1",
                    date=day,
                    feed_id=f"example-{index:02d}",
                    checked_at=f"{day}T06:00:00Z",
                    outcome=FetchOutcome.OK,
                    status=200,
                    items=3,
                    detail=None,
                )
            ],
        )


def feed_health_months(state_dir: Path) -> list[str]:
    """Which months the feed-health day tree still holds, oldest first.

    The boundary the prune works on is still a month; only the files below it are
    days, so a test about what the prune kept asks in months.
    """
    return sorted(day_partition.days_by_month(state_dir / ledger.HEALTH_DIRNAME))
