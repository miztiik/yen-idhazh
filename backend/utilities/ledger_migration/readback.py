"""What does the door serve for one migrated day, from stored files that check out?"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from idhazh import ledger
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.filenames import unit_id
from idhazh.ledger.stored_output import check_compact_period, check_raw_day
from utilities.ledger_migration.fold import folded


def door_rows(state_dir: Path, which: LedgerName, day: str) -> list[dict[str, str]]:
    """The day's rows as the door serves them, cell by cell."""
    rows = ledger.load_days(state_dir, which, [day], model=ledger.door_contract(which))
    return [cast("ledger.CsvRecord", row).csv_row() for row in rows]


def migration_rows(
    state_dir: Path, which: LedgerName, day: str, identity: WriterIdentity
) -> list[dict[str, str]]:
    """The rows held by this migration work unit in named compact and raw files."""
    model = ledger.door_contract(which)
    if "unit_id" in model.model_fields:
        raise ValueError(
            f"{which.value}: {model.__name__} declares unit_id, so row writer ownership "
            "cannot be determined"
        )
    migration_unit = str(
        unit_id(
            ledger=which.value,
            covers=day,
            run_id=identity.run_id,
            job=identity.job.value,
            shard=identity.shard,
            producer=identity.producer,
        )
    )
    owned: list[dict[str, str]] = []
    for period, covers in (
        (Period.YEARLY, day[:4]),
        (Period.MONTHLY, day[:7]),
        (Period.DAILY, day),
    ):
        try:
            indexed = check_compact_period(state_dir, which, period, covers)
        except ValueError as refusal:
            raise ValueError(
                f"{which.value}: cannot determine migration ownership from compact "
                f"{period.value} {covers}: {refusal}"
            ) from refusal
        if not indexed:
            continue
        path = ledger.compact_file(state_dir, which, period, covers)
        if path is not None:
            try:
                stored = ledger.load_stored([path], model=model)
            except ValueError as refusal:
                raise ValueError(
                    f"{which.value}: compact {period.value} {covers} cannot expose "
                    f"migration row ownership: {refusal}"
                ) from refusal
            owned.extend(
                cast("ledger.CsvRecord", row.row).csv_row()
                for row in stored
                if row.identity.covers == day and row.identity.unit_id == migration_unit
            )
        break

    for held in ledger.read_day_files(state_dir, which, day):
        owned.extend(
            cast("ledger.CsvRecord", row.row).csv_row()
            for row in ledger.load_stored([held.path], model=model)
            if row.identity.unit_id == migration_unit
        )
    return folded([], owned, ledger.door_key(which))


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
