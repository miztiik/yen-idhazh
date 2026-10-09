"""Tree builders and clocks more than one retention module needs."""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Final

from conftest import seed_host_fingerprint, seed_item_health

from idhazh import ledger
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import (
    TERMINAL_STAGES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.item_health_summary import ItemHealthSummaryRow
from idhazh.contracts.ledger_name import LedgerName

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


#: The day the fold is run against in every test below, and the twenty months of
#: history it is run over. Twenty rather than fourteen so both sides of the
#: threshold carry several months: at the fold's 14-month full-grain window it
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
    """Two item-health days per month, filed through the ledger door."""
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
            seed_item_health(state_dir, day, rows)


def totals_from_shard(texts: Iterable[str]) -> dict[tuple[str, str], tuple[int, int, int]]:
    """Rows, failures and total milliseconds per (date, stage), read off CSV text.

    Recomputed here from the raw text rather than by calling `compact_month`, so the
    oracle cannot pass by agreeing with the code it is checking. It takes a
    month's census together, because a month is what one aggregate covers. The
    ledger door files parquet, so a caller renders the rows it read back with
    `ledger.render_file` before handing them here.
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
    """Every raw item-health file, oldest first, through the ledger door's own listing.

    A day is a folder of raw files, one file per write, so a day answers with as
    many paths as writes reached it. The whole ledger, because a retention test
    asks what a pass left and a window would hide the months it took.
    """
    return [held.path for held in ledger.list_raw_files(state_dir, LedgerName.ITEM_HEALTH)]


def item_health_months(state_dir: Path) -> list[str]:
    """Which months the item-health ledger still holds, oldest first.

    Read off folder and index names by the ledger door, so no file is opened. A
    pass works on months; only the files below one are days, so a test about
    what a pass kept asks in months.
    """
    return ledger.held_months(state_dir, LedgerName.ITEM_HEALTH)


def census_of(state_dir: Path, date: str) -> list[ItemHealthRow]:
    """One row per item one named day recorded, settled the way the ledger door settles it.

    The read the gardener's `telemetry-aggregate` task itself makes, bounded to
    one day. A test that opened the day's own folder would open a directory, and
    one that opened a single file inside it would answer for one write rather
    than for the day.
    """
    return ledger.load_days(state_dir, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow)


def totals_from_aggregate(
    rows: list[ItemHealthSummaryRow],
) -> dict[tuple[str, str], tuple[int, int, int]]:
    return {(row.date, row.stage.value): (row.items, row.failed, row.sum_ms or 0) for row in rows}


def a_state_tree(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    item_health_history(state, months_back(TODAY, HISTORY_MONTHS))
    return state


#: Names of the right width and shape that are not a month. Every one was
#: accepted by at least one month reader and refused by another before
#: 2026-09-08, which is what made the same file survive in one ledger and get
#: deleted in the next.
NOT_MONTHS: Final = (
    "2025-00",
    "2025-13",
    "0000-01",
    #: `2025-01` in Arabic-Indic digits. `str.isdigit` and `int` both read this
    #: as January 2025, so a naive check finds two files claiming one month.
    "\u0662\u0660\u0662\u0665-\u0660\u0661",
)

def host_fingerprint_history(
    state_dir: Path, months: list[str], *, day_of_month: int = 11
) -> None:
    """One machine row per month, filed through the ledger door.

    `seed_host_fingerprint` files each row under the writer the job that drew
    the machine uses, so each month gets one raw file where a run leaves it.
    """
    seed_host_fingerprint(
        state_dir,
        [
            HostFingerprintRow(
                version=HostFingerprintRow.schema_version(),
                date=f"{month}-{day_of_month:02d}",
                run_id=f"{month}-{day_of_month:02d}-1",
                shard=index,
                cpu_model="AMD EPYC 7763 64-Core Processor",
            )
            for index, month in enumerate(months)
        ],
    )


def host_fingerprint_months(state_dir: Path) -> list[str]:
    """Which months the host-fingerprint ledger still holds, oldest first, from names alone."""
    return ledger.held_months(state_dir, LedgerName.HOST_FINGERPRINT)
