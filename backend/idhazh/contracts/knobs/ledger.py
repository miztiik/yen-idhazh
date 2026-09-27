"""How does the ledger door write a file, and which ledgers may a browser address?

Four knobs, read by `idhazh.ledger.persist` and nothing else. `format` is what a
file is written as when its caller names none. The two compressions are one per
tier: snappy for a raw file, which every reader opens without a plugin and which
the compaction reads once, and zstd for a compact file, which is smaller and is
read by this project alone. `published` names the ledgers whose compact files a
browser may fetch.

**`published` ships empty.** No page reads a compact file yet, and an entry here
would publish files that no page opens.
"""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model
from idhazh.contracts.file_envelope import Compression, Format
from idhazh.contracts.ledger_name import LedgerName


class LedgerConfig(Model):
    """The format and compression a ledger file is written with, and what a browser may read."""

    format: Format = Field(
        default=Format.PARQUET,
        description=(
            "What a ledger file is written as when its caller names no format. Parquet "
            "is the format the project is moving `state/` to; JSON lines stays "
            "available for a payload a person reads in a pull request."
        ),
    )
    compression_raw: Compression = Field(
        default=Compression.SNAPPY,
        description=(
            "How a parquet file under `state/raw/` compresses its rows. Snappy is what "
            "every reader supports without a plugin, and a raw file is small and read "
            "once by the compaction."
        ),
    )
    compression_compact: Compression = Field(
        default=Compression.ZSTD,
        description=(
            "How a parquet file under `state/compact/` compresses its rows. zstd is "
            "about 2.2 times smaller than snappy at a thousand rows, and a compact file "
            "is read by this project alone."
        ),
    )
    published: list[LedgerName] = Field(
        default_factory=list,
        description=(
            "The ledgers whose compact files a browser may fetch. Empty until a console "
            "page reads one, because an entry here publishes files."
        ),
    )
