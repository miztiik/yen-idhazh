"""How does the ledger door write a file, and what may a browser reach to read one?

Four knobs are read by `idhazh.ledger.persist` and nothing else. `format` is what a
file is written as when its caller names none. The two compressions are one per
tier: snappy for a raw file, which every reader opens without a plugin and which
the compaction reads once, and zstd for a compact file, which is smaller and is
read by this project alone. `published` names the ledgers whose compact files a
browser may fetch, and `archive_base_url` names the optional public repository
prefix the data explorer can use for older packed files.

**`published` names every packed ledger the console can ask for.** The site
build copies each one's three indexes, trimmed to the widest console span, and
every compact file those trimmed indexes name. It refuses a ledger that lacks any
index. A backend test holds every ledger a console panel asks the browser's query
door for to this list.

`engine_extension_repository` is read by the site build alone: it is
where the query engine that reads these files downloads its add-ons, and the one
origin for that the page's `connect-src` admits.
"""

from __future__ import annotations

from pydantic import Field, ValidationInfo, field_validator

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
            "The ledgers whose compact files a browser may fetch. The site build copies "
            "each one's three indexes trimmed to the widest console span, and the compact "
            "files those trimmed indexes name. Empty by default, because an entry here "
            "publishes files."
        ),
    )
    archive_base_url: str = Field(
        default="",
        description=(
            "The public https prefix for packed ledger files older than this site carries. "
            "Empty means the site only; a non-empty value joins the page's connect-src "
            "origins and is fetched by the page, never handed to the engine."
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

    @field_validator("engine_extension_repository", "archive_base_url")
    @classmethod
    def _browser_reachable_prefix_is_https(cls, value: str, info: ValidationInfo) -> str:
        """An absolute `https://` prefix with no trailing slash, whitespace or quote.

        The engine appends `/<version>/<platform>/<name>` and writes the value into
        a `SET` statement; the archive keeper appends `/state/compact/...`. A
        trailing slash or quote breaks the address or the statement instead of
        failing the build here.
        """
        field = info.field_name or "ledger prefix"
        if field == "archive_base_url" and value == "":
            return value
        if not value.startswith("https://"):
            hint = (
                " is empty or begins with https://"
                if field == "archive_base_url"
                else " begins with https://"
            )
            raise ValueError(f"ledger.{field}{hint}")
        if value.endswith("/"):
            raise ValueError(f"ledger.{field} carries no trailing slash")
        if any(character in value for character in " \t?#'\""):
            raise ValueError(
                f"ledger.{field} carries no whitespace, quote, query or fragment"
            )
        return value
