"""How far do the indexes a test's compaction left say each period of its ledger is packed?

Worked out from the index files on disk by `ledger_marks.work_out_marks`, the
one rule every pass uses, so a test reads the marks the next pass starts from.
An index that is not there names nothing.
"""

from __future__ import annotations

from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.ledger_marks import work_out_marks


def marks_on_disk(state_dir: Path, which: LedgerName) -> dict[Period, str | None]:
    """Each period's mark, from the indexes of `which` under `state_dir`."""
    covers: dict[Period, list[str]] = {}
    expired_through = None
    for period in Period:
        path = ledger.compact_index_path(state_dir, which, period)
        held = CompactIndex.read(path) if path.is_file() else None
        covers[period] = [entry.covers for entry in held.entries] if held else []
        if held and period is Period.YEARLY:
            expired_through = held.expired_through
    return work_out_marks(covers, expired_through=expired_through)
