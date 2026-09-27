"""How rows and their envelope become one parquet file, and how they come back.

**The only module in the repository that imports pyarrow**, and it does so in
one statement. Every other module reaches the engine through this one, so
replacing it - duckdb is the named candidate - is a change to one file.
`ledger/persist.py` imports this module inside the functions that write and read
parquet, never at its top: pyarrow is an optional extra that only the jobs
touching parquet install, and a module-scope import would stop every stage that
imports the ledger from loading without it.

The envelope is written as the schema's metadata, which pyarrow writes into the
file's key-value metadata. Row-group statistics are left on: a constant column
carries a minimum equal to its maximum, and that is what lets a reader skip a
whole file without decompressing it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import pyarrow.parquet

from idhazh.contracts.file_envelope import Compression
from idhazh.ledger.arrow_schema import Column, ColumnType

#: The key prefix pyarrow uses for its own serialized schema beside our keys.
#: Not part of the envelope, so it is dropped on the way back.
_ENGINE_KEY_PREFIX: Final = b"ARROW:"

_ARROW_TYPES: Final[dict[ColumnType, Any]] = {
    ColumnType.STRING: pyarrow.string(),
    ColumnType.INT64: pyarrow.int64(),
    ColumnType.FLOAT64: pyarrow.float64(),
    ColumnType.BOOL: pyarrow.bool_(),
    ColumnType.STRING_LIST: pyarrow.list_(pyarrow.string()),
}


def engine_version() -> str:
    """The engine's own version, which the envelope records because bytes vary by it."""
    return str(pyarrow.__version__)


def render(
    columns: Sequence[Column],
    rows: Sequence[Mapping[str, Any]],
    *,
    envelope: Mapping[bytes, bytes],
    compression: Compression,
) -> bytes:
    """One whole parquet file: these rows under these columns, the envelope in its footer."""
    schema = pyarrow.schema(
        [
            pyarrow.field(column.name, _ARROW_TYPES[column.type], column.nullable)
            for column in columns
        ],
        metadata=dict(envelope),
    )
    table = pyarrow.Table.from_pylist([dict(row) for row in rows], schema=schema)
    sink = pyarrow.BufferOutputStream()
    pyarrow.parquet.write_table(
        table,
        sink,
        compression=None if compression is Compression.NONE else compression.value,
    )
    return bytes(sink.getvalue().to_pybytes())


def _envelope_of(metadata: Mapping[bytes, bytes] | None) -> dict[bytes, bytes]:
    """Our keys out of a file's metadata, without the engine's own."""
    return {
        key: value
        for key, value in (metadata or {}).items()
        if not key.startswith(_ENGINE_KEY_PREFIX)
    }


def read(data: bytes) -> tuple[dict[bytes, bytes], list[dict[str, Any]]]:
    """A whole parquet file back as its envelope and its rows, in file order."""
    table = pyarrow.parquet.read_table(pyarrow.BufferReader(data))
    return _envelope_of(table.schema.metadata), list(table.to_pylist())


def read_envelope(path: Path) -> dict[bytes, bytes]:
    """The envelope alone, read from the footer without touching a row."""
    return _envelope_of(pyarrow.parquet.read_metadata(path).metadata)
