"""Does a migrated day read back through the door as planned, with every filled CSV cell intact?"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from idhazh import day_shards, ledger
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration.fold import folded, key_of
from utilities.ledger_migration.path_labels import describe_error, label_path
from utilities.ledger_migration.readback import check_output, door_rows
from utilities.ledger_migration.refusals import NotProvenError


def prove(
    state_dir: Path,
    which: LedgerName,
    day: str,
    rows: Sequence[dict[str, str]],
    *,
    source_rows: Sequence[dict[str, str]] = (),
) -> None:
    """The day reads back through the door as exactly these rows, cell for cell, or a refusal."""
    context = f"{label_path(state_dir)}: {which.value} {day}"
    try:
        check_output(state_dir, which, day, required=bool(rows))
        readback = door_rows(state_dir, which, day)
    except (ValueError, OSError) as refusal:
        raise NotProvenError(f"{context}: {describe_error(refusal)}") from refusal
    key = ledger.door_key(which)
    back = {key_of(cells, key): cells for cells in readback}
    wanted = {key_of(cells, key): cells for cells in rows}
    if back.keys() != wanted.keys():
        raise NotProvenError(
            f"{context} reads back {len(back)} rows where {len(wanted)} were filed; "
            f"missing {sorted(wanted.keys() - back.keys())[:3]}, "
            f"invented {sorted(back.keys() - wanted.keys())[:3]}"
        )
    for record, cells in wanted.items():
        for column, cell in cells.items():
            if back[record].get(column) != cell:
                raise NotProvenError(
                    f"{context} row {','.join(record)} reads back "
                    f"{column}={back[record].get(column)!r} where {cell!r} was filed"
                )
    for cells in folded([], source_rows, key):
        record = key_of(cells, key)
        if record not in back:
            raise NotProvenError(f"{context}: missing CSV source key {','.join(record)}")
        for column, cell in cells.items():
            if column != day_shards.VERSION_CELL and cell and back[record].get(column) != cell:
                raise NotProvenError(
                    f"{context} row {','.join(record)} reads back "
                    f"{column}={back[record].get(column)!r} where the CSV supplies {cell!r}"
                )
