"""How rows and their envelope become one parquet file, and how they come back.

**The only module in the repository that imports pyarrow**, and it does so in
one statement. Every other module reaches the engine through this one, so
replacing it - duckdb is the named candidate - is a change to one file.
`ledger/persist.py` imports this module inside the functions that write and read
parquet, never at its top, so importing the ledger never loads pyarrow: a stage
that never opens a parquet file does not pay to load the engine.

The envelope is written as the schema's metadata, which pyarrow writes into the
file's key-value metadata. Row-group statistics are left on: a constant column
carries a minimum equal to its maximum, and that is what lets a reader skip a
whole file without decompressing it.

**A file too big to build at once is written one row group at a time**
(`render_groups`): each group is its own row group, and the envelope is added to
the file's key-value metadata after the last one, because only then is its
digest known. So `read` takes the envelope from the file's key-value metadata,
which holds it whichever way the file was written. `render` also keeps it in the
schema, which is where a build older than `render_groups` looks for it, so a
daily or monthly file stays readable by every build.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
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


def _schema(columns: Sequence[Column], metadata: Mapping[bytes, bytes] | None) -> Any:
    """The arrow schema these columns make, carrying `metadata` when there is any."""
    return pyarrow.schema(
        [
            pyarrow.field(column.name, _ARROW_TYPES[column.type], column.nullable)
            for column in columns
        ],
        metadata=None if metadata is None else dict(metadata),
    )


def _codec(compression: Compression) -> str | None:
    return None if compression is Compression.NONE else compression.value


def render(
    columns: Sequence[Column],
    rows: Sequence[Mapping[str, Any]],
    *,
    envelope: Mapping[bytes, bytes],
    compression: Compression,
) -> bytes:
    """One whole parquet file: these rows under these columns, the envelope in its footer."""
    schema = _schema(columns, envelope)
    table = pyarrow.Table.from_pylist([dict(row) for row in rows], schema=schema)
    sink = pyarrow.BufferOutputStream()
    pyarrow.parquet.write_table(table, sink, compression=_codec(compression))
    return bytes(sink.getvalue().to_pybytes())


def render_groups(
    columns: Sequence[Column],
    groups: Iterable[Sequence[Mapping[str, Any]]],
    *,
    envelope: Callable[[], Mapping[bytes, bytes]],
    compression: Compression,
) -> bytes:
    """One whole parquet file written one row group per group, the envelope added last.

    Each group that holds a row becomes exactly one row group, in order, so its
    statistics bound that group alone; a group with no rows writes none.
    `envelope` is called once, after the last group is written, so it may say
    what only every row together can - their digest. One group is held in memory
    at a time.
    """
    schema = _schema(columns, None)
    sink = pyarrow.BufferOutputStream()
    with pyarrow.parquet.ParquetWriter(sink, schema, compression=_codec(compression)) as writer:
        for rows in groups:
            if rows:
                table = pyarrow.Table.from_pylist([dict(row) for row in rows], schema=schema)
                writer.write_table(table, row_group_size=len(rows))
        writer.add_key_value_metadata(dict(envelope()))
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
    with (
        pyarrow.BufferReader(data) as source,
        pyarrow.parquet.ParquetFile(source) as opened,
    ):
        return _envelope_of(opened.metadata.metadata), list(opened.read().to_pylist())


def read_envelope(path: Path) -> dict[bytes, bytes]:
    """The envelope alone, read from the footer without touching a row."""
    return _envelope_of(pyarrow.parquet.read_metadata(path).metadata)
