"""What does the door serve for one migrated day, from stored files that check out?"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.stored_output import check_compact_period, check_raw_day


def door_rows(state_dir: Path, which: LedgerName, day: str) -> list[dict[str, str]]:
    """The day's rows as the door serves them, cell by cell."""
    rows = ledger.load_days(state_dir, which, [day], model=ledger.door_contract(which))
    return [cast("ledger.CsvRecord", row).csv_row() for row in rows]


def check_output(state_dir: Path, which: LedgerName, day: str, *, required: bool) -> None:
    """Check the day's raw files and every compact period that covers it."""
    raw = check_raw_day(state_dir, which, day)
    compact = [
        check_compact_period(state_dir, which, period, covers)
        for period, covers in (
            (Period.DAILY, day),
            (Period.MONTHLY, day[:7]),
            (Period.YEARLY, day[:4]),
        )
    ]
    if required and any(compact):
        for period in Period:
            path = ledger.compact_index_path(state_dir, which, period)
            if not path.is_file():
                raise ValueError(f"missing compact index {path.name}")
    if required and not raw and not any(compact):
        raise ValueError("migrated output is missing")
