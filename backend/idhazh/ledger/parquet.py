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
from idhazh.ledger.arrow_schema import Column, ColumnType, LogicalField, LogicalType

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


def _arrow_type(logical: ColumnType | LogicalType) -> Any:
    """A logical scalar, list or struct into the engine's native type."""
    if isinstance(logical, ColumnType):
        return _ARROW_TYPES[logical]
    if logical.kind == "scalar":
        if logical.scalar is None:
            raise TypeError(f"{logical!r} is a scalar without a scalar name")
        mapping = {
            "string": pyarrow.string(),
            "int64": pyarrow.int64(),
            "float64": pyarrow.float64(),
            "bool": pyarrow.bool_(),
        }
        return mapping[logical.scalar]
    if logical.kind == "list":
        if logical.item_type is None:
            raise TypeError(f"{logical!r} is a list without an item type")
        item = _arrow_type(logical.item_type)
        return pyarrow.list_(pyarrow.field("item", item, nullable=logical.item_nullable))
    if logical.kind == "struct":
        return pyarrow.struct(
            [
                pyarrow.field(field.name, _arrow_type(field.type), field.nullable)
                for field in logical.fields
            ]
        )
    raise TypeError(f"{logical!r} is not a supported logical tree")


def engine_version() -> str:
    """The engine's own version, which the envelope records because bytes vary by it."""
    return str(pyarrow.__version__)


def _schema(columns: Sequence[Column], metadata: Mapping[bytes, bytes] | None) -> Any:
    """The arrow schema these columns make, carrying `metadata` when there is any."""
    return pyarrow.schema(
        [
            pyarrow.field(column.name, _arrow_type(column.type), column.nullable)
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


def read_footer(path: Path) -> tuple[dict[bytes, bytes], int]:
    """The envelope and how many rows the file holds, both read from its footer, not a row."""
    footer = pyarrow.parquet.read_metadata(path)
    return _envelope_of(footer.metadata), int(footer.num_rows)


def _logical_from_arrow(name: str, data_type: Any) -> ColumnType | LogicalType:
    """The project logical type represented by one Arrow footer field."""
    if pyarrow.types.is_string(data_type):
        return ColumnType.STRING
    if pyarrow.types.is_int64(data_type):
        return ColumnType.INT64
    if pyarrow.types.is_float64(data_type):
        return ColumnType.FLOAT64
    if pyarrow.types.is_boolean(data_type):
        return ColumnType.BOOL
    if pyarrow.types.is_list(data_type):
        field = data_type.value_field
        return LogicalType(
            kind="list",
            item_type=_logical_tree_from_arrow(f"{name}[]", field.type),
            item_nullable=field.nullable,
        )
    if pyarrow.types.is_struct(data_type):
        return LogicalType(
            kind="struct",
            fields=tuple(
                LogicalField(
                    name=field.name,
                    type=_logical_tree_from_arrow(f"{name}.{field.name}", field.type),
                    nullable=field.nullable,
                )
                for field in data_type
            ),
        )
    raise TypeError(f"{name} has parquet type {data_type}, which the ledger type map does not know")


def _logical_tree_from_arrow(name: str, data_type: Any) -> LogicalType:
    """The recursive spelling of one Arrow footer field."""
    logical = _logical_from_arrow(name, data_type)
    if isinstance(logical, LogicalType):
        return logical
    return LogicalType(kind="scalar", scalar=logical.value)


def read_footer_columns(path: Path) -> tuple[dict[bytes, bytes], int, tuple[Column, ...]]:
    """The envelope, row count and columns read from a parquet footer, with no row read."""
    footer = pyarrow.parquet.read_metadata(path)
    schema = footer.schema.to_arrow_schema()
    columns = tuple(
        Column(
            name=field.name,
            type=_logical_from_arrow(field.name, field.type),
            nullable=field.nullable,
        )
        for field in schema
    )
    return _envelope_of(footer.metadata), int(footer.num_rows), columns
