"""What one raw day's listing says: which files the day holds, and the digest over their names.

The compaction lists a day the moment it takes it, once, and writes that
listing as the day's `RawDayIndex` beside the compact file it builds. Nothing
else writes a listing, so a listing is always the files one compaction read.
It outlives the raw files it names for `raw_index_keep_days`, so a compact day
can be checked against the files it was built from after they are gone.

The names come from the files `ledger.read_day_files` read, and that read
stops on a file it cannot read, so a listing never names a file the compaction
skipped.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from idhazh.contracts.ledger_index import RawDayIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import RawFile


def listing(
    files: Sequence[RawFile], *, ledger: LedgerName, day: str, listed_at: str
) -> RawDayIndex:
    """The listing of one raw day: its file names in ascending order, and their digest.

    The digest is SHA-256 over the names joined with one newline between them
    and none at the end, so a day that held nothing digests the empty string.
    """
    names = sorted(held.path.name for held in files)
    return RawDayIndex(
        version=RawDayIndex.schema_version(),
        ledger=ledger,
        date=day,
        files=names,
        content_sha256=hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest(),
        listed_at=listed_at,
    )
