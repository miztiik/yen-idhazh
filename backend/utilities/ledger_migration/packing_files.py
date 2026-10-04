"""Which named files may one packing pass see for a ledger's named UTC months?"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from utilities.named_inputs import month_directories


def packing_paths(state_dir: Path, which: LedgerName, months: Sequence[str]) -> list[Path]:
    """Files in named raw and daily months, plus named periods' files and index metadata."""
    paths: set[Path] = set()
    for folder in month_directories(ledger.raw_root(state_dir, which), months):
        if folder.is_dir():
            paths.update(path for path in folder.rglob("*") if path.is_file())
    for folder in month_directories(
        ledger.compact_path(state_dir, which, Period.DAILY, f"{months[0]}-01").parents[2],
        months,
    ):
        if folder.is_dir():
            paths.update(path for path in folder.iterdir() if path.is_file())
    for month in sorted(set(months)):
        year, number = map(int, month.split("-"))
        for day in range(1, calendar.monthrange(year, number)[1] + 1):
            index = ledger.raw_index_path(state_dir, which, f"{month}-{day:02d}")
            if index.is_file():
                paths.add(index)
        for period, covers in ((Period.MONTHLY, month), (Period.YEARLY, month[:4])):
            for fmt in Format:
                path = ledger.compact_path(state_dir, which, period, covers, fmt=fmt)
                if path.is_file():
                    paths.add(path)
    for period in Period:
        for path in (
            ledger.compact_index_path(state_dir, which, period),
            ledger.watermark_path(state_dir, which, period),
        ):
            if path.is_file():
                paths.add(path)
    return sorted(paths)
