"""Which period paths does one packing pass name for a ledger's named UTC months?"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from utilities.named_inputs import month_directories


def packing_paths(state_dir: Path, which: LedgerName, months: Sequence[str]) -> list[Path]:
    """Named raw and daily month folders, named periods' files, and index metadata.

    Each path is named whether or not it is there, and nothing is read to name
    it. The pass's listing answers only for what was named, so a watermark, a
    period file or a quiet day that is absent reads as absent rather than being
    refused.
    """
    paths: set[Path] = set(month_directories(ledger.raw_root(state_dir, which), months))
    paths.update(
        month_directories(
            ledger.compact_path(state_dir, which, Period.DAILY, f"{months[0]}-01").parents[2],
            months,
        )
    )
    for month in sorted(set(months)):
        year, number = map(int, month.split("-"))
        for day in range(1, calendar.monthrange(year, number)[1] + 1):
            paths.add(ledger.raw_index_path(state_dir, which, f"{month}-{day:02d}"))
        for period, covers in ((Period.MONTHLY, month), (Period.YEARLY, month[:4])):
            for fmt in Format:
                paths.add(ledger.compact_path(state_dir, which, period, covers, fmt=fmt))
    for period in Period:
        paths.add(ledger.compact_index_path(state_dir, which, period))
        paths.add(ledger.watermark_path(state_dir, which, period))
    return sorted(paths)
