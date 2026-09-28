"""How does the ledger door write a file, and what may a browser reach to read one?

Four knobs are read by `idhazh.ledger.persist` and nothing else. `format` is what a
file is written as when its caller names none. The two compressions are one per
tier: snappy for a raw file, which every reader opens without a plugin and which
the compaction reads once, and zstd for a compact file, which is smaller and is
read by this project alone. `published` names the ledgers whose compact files a
browser may fetch.

**`published` ships empty.** No page reads a compact file yet, and an entry here
would publish files that no page opens.

The fifth, `engine_extension_repository`, is read by the site build alone: it is
where the query engine that reads these files downloads its add-ons, and the one
origin for that the page's `connect-src` admits.
"""

from __future__ import annotations

from pydantic import Field, field_validator

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
    engine_extension_repository: str = Field(
        default="https://extensions.duckdb.org",
        description=(
            "Where the query engine downloads an add-on the first time a query needs "
            "one - the parquet reader is one, about 3.2 MB. DuckDB's own host is the "
            "engine's default. The engine is told this address and the page's "
            "`connect-src` admits its origin, so one edit moves both; the engine "
            "checks each add-on's signature before it loads it."
        ),
    )

    @field_validator("engine_extension_repository")
    @classmethod
    def _the_repository_is_a_prefix_the_engine_joins_onto(cls, value: str) -> str:
        """An absolute `https://` prefix with no trailing slash, whitespace or quote.

        The engine appends `/<version>/<platform>/<name>` itself, and the value is
        written into a `SET` statement, so a slash or a quote here breaks the
        address or the statement rather than failing the build.
        """
        if not value.startswith("https://"):
            raise ValueError("ledger.engine_extension_repository begins with https://")
        if value.endswith("/"):
            raise ValueError("ledger.engine_extension_repository carries no trailing slash")
        if any(character in value for character in " \t?#'\""):
            raise ValueError(
                "ledger.engine_extension_repository carries no whitespace, quote, query or fragment"
            )
        return value
