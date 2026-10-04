"""What is each way a packed ledger can be missing a file called?

There are four, and these are the words the query door uses. The list is
declared in `frontend/src/lib/data/slice-shapes.ts`, where the door and every
console reader take it. This is its copy for the backend, and
`backend/tests/contracts/test_frontend_index_shapes.py` holds the two to one
list, name for name and in order. The gardener's packing logs and the backend's
own ledger reader name a fault in these words, so one search finds it on both
sides.

It sits with the contracts, which import no other subpackage of `idhazh`, so a
persisted record can name a fault (CLAUDE.md section 4).
"""

from __future__ import annotations

from enum import StrEnum


class LedgerFault(StrEnum):
    """One way a packed ledger can be missing a file."""

    #: There is no `index/daily.json`, so no day of the ledger is packed.
    NOT_PACKED = "not-packed"
    #: `index/daily.json` is there and `index/monthly.json` or `index/yearly.json` is not.
    INDEX_MISSING = "index-missing"
    #: An index names a file that is not there.
    FILE_MISSING = "file-missing"
    #: A day between the first and the newest packed day that no index names.
    DAY_MISSING = "day-missing"
