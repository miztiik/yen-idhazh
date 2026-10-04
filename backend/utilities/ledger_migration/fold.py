"""How do a day's CSV rows fold onto the rows the door already holds for it?"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from idhazh import day_shards, ledger


def key_of(cells: dict[str, str], key: tuple[str, ...]) -> tuple[str, ...]:
    """A row's cells under the key's columns, in key order."""
    return tuple(cells[name] for name in key)


def folded(
    held: Sequence[dict[str, str]], arriving: Sequence[dict[str, str]], key: tuple[str, ...]
) -> list[dict[str, str]]:
    """The rows the door holds for a day, with the CSV's rows for it folded on.

    The fold today's reader applies to a settled file and a writer's file beside
    it: the door's rows stand where the settled file stood, and the CSV's rows
    arrive after them, so a cell only one side filled is joined and a cell both
    filled goes to the later side unless the key declares a preference.
    Unlike the reader's fold, this keeps the newest schema stamp so verification
    after writing does not refuse a row whose contract advanced its version.
    """
    prefers = ledger.preference_for(key)
    records: dict[tuple[str, ...], day_shards.Held] = {}
    for cells in held:
        records[key_of(cells, key)] = day_shards.Held(0, dict(cells))
    for number, cells in enumerate(arriving):
        record = key_of(cells, key)
        if record not in records:
            records[record] = day_shards.Held(1, dict(cells))
            continue
        version = records[record].cells[day_shards.VERSION_CELL]
        day_shards.settle(
            records[record], day_shards.Waiting(Path(), 1, number, dict(cells)), key, prefers
        )
        records[record].cells[day_shards.VERSION_CELL] = max(
            version, cells[day_shards.VERSION_CELL]
        )
    return [entry.cells for entry in records.values()]
