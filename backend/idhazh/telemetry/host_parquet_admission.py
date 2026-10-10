"""Can these actual Parquet pages safely enter the one-row host decoder?"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import cramjam
from thrift.protocol.TBase import TBase
from thrift.protocol.TCompactProtocol import TCompactProtocol
from thrift.Thrift import TType
from thrift.transport.TTransport import TTransportBase

from idhazh.ledger.arrow_schema import Column, ColumnType

# PageHeader bindings projected from Apache parquet-format 2.12.0, generated
# with Apache Thrift 0.22.0 --gen py:dynamic. Constructors have type annotations;
# Statistics are deliberately skipped by the bounded maintained protocol.
# IDL SHA256: 679937945a457643ec7f91293001cb2c132ded0d42899f5e5c69d8a929ba841f
# https://github.com/apache/parquet-format/blob/apache-parquet-format-2.12.0/src/main/thrift/parquet.thrift
# Licensed under the Apache License, Version 2.0:
# https://www.apache.org/licenses/LICENSE-2.0
_Spec = tuple[Any, ...]


@dataclass
class _DataPageHeader(TBase):  # type: ignore[misc]
    num_values: int | None = None
    encoding: int | None = None
    definition_level_encoding: int | None = None
    repetition_level_encoding: int | None = None
    thrift_spec: ClassVar[_Spec] = (
        None,
        (1, TType.I32, "num_values", None, None),
        (2, TType.I32, "encoding", None, None),
        (3, TType.I32, "definition_level_encoding", None, None),
        (4, TType.I32, "repetition_level_encoding", None, None),
    )


@dataclass
class _DictionaryPageHeader(TBase):  # type: ignore[misc]
    num_values: int | None = None
    encoding: int | None = None
    is_sorted: bool | None = None
    thrift_spec: ClassVar[_Spec] = (
        None,
        (1, TType.I32, "num_values", None, None),
        (2, TType.I32, "encoding", None, None),
        (3, TType.BOOL, "is_sorted", None, None),
    )


@dataclass
class _DataPageHeaderV2(TBase):  # type: ignore[misc]
    num_values: int | None = None
    num_nulls: int | None = None
    num_rows: int | None = None
    encoding: int | None = None
    definition_levels_byte_length: int | None = None
    repetition_levels_byte_length: int | None = None
    is_compressed: bool = True
    thrift_spec: ClassVar[_Spec] = (
        None,
        (1, TType.I32, "num_values", None, None),
        (2, TType.I32, "num_nulls", None, None),
        (3, TType.I32, "num_rows", None, None),
        (4, TType.I32, "encoding", None, None),
        (5, TType.I32, "definition_levels_byte_length", None, None),
        (6, TType.I32, "repetition_levels_byte_length", None, None),
        (7, TType.BOOL, "is_compressed", None, True),
    )


@dataclass
class _IndexPageHeader(TBase):  # type: ignore[misc]
    thrift_spec: ClassVar[_Spec] = ()


@dataclass
class _PageHeader(TBase):  # type: ignore[misc]
    type: int | None = None
    uncompressed_page_size: int | None = None
    compressed_page_size: int | None = None
    crc: int | None = None
    data_page_header: _DataPageHeader | None = None
    index_page_header: _IndexPageHeader | None = None
    dictionary_page_header: _DictionaryPageHeader | None = None
    data_page_header_v2: _DataPageHeaderV2 | None = None
    thrift_spec: ClassVar[_Spec] = (
        None,
        (1, TType.I32, "type", None, None),
        (2, TType.I32, "uncompressed_page_size", None, None),
        (3, TType.I32, "compressed_page_size", None, None),
        (4, TType.I32, "crc", None, None),
        (5, TType.STRUCT, "data_page_header", [_DataPageHeader, _DataPageHeader.thrift_spec], None),
        (
            6,
            TType.STRUCT,
            "index_page_header",
            [_IndexPageHeader, _IndexPageHeader.thrift_spec],
            None,
        ),
        (
            7,
            TType.STRUCT,
            "dictionary_page_header",
            [_DictionaryPageHeader, _DictionaryPageHeader.thrift_spec],
            None,
        ),
        (
            8,
            TType.STRUCT,
            "data_page_header_v2",
            [_DataPageHeaderV2, _DataPageHeaderV2.thrift_spec],
            None,
        ),
    )


class _Transport(TTransportBase):  # type: ignore[misc]
    """A no-copy input window; even an overlong varint has a fixed work bound."""

    def __init__(self, data: bytes, start: int, end: int) -> None:
        self.data = memoryview(data)
        self.position = start
        self.end = end
        self.single_bytes_left: int | None = None

    def read(self, size: int) -> bytes:
        if size == 1 and self.single_bytes_left is not None:
            self.single_bytes_left -= 1
            if self.single_bytes_left < 0:
                raise ValueError("Parquet Thrift varint exceeds its primitive width")
        if size < 0 or size > self.end - self.position:
            raise ValueError("Parquet Thrift read exceeds its bounded byte interval")
        start = self.position
        self.position += size
        return bytes(self.data[start : self.position])


class _Compact(TCompactProtocol):  # type: ignore[misc]
    """Keep maintained compact primitives, bound every recursive/unknown field."""

    def __init__(self, transport: _Transport, *, byte_limit: int, items: int, depth: int) -> None:
        super().__init__(transport, string_length_limit=byte_limit, container_length_limit=items)
        self.items_left = items
        self.field_limit = items
        self.depth_limit = depth
        self.nesting = 0
        self.fields: list[set[int]] = []
        self.source = transport

    def _bounded(self, read: Callable[[], Any], width: int) -> Any:
        previous = self.source.single_bytes_left
        self.source.single_bytes_left = width
        try:
            return read()
        finally:
            self.source.single_bytes_left = previous

    def _charge(self, count: int) -> None:
        self.items_left -= count
        if self.items_left < 0:
            raise ValueError("Parquet Thrift exceeds the cumulative item limit")

    def _enter(self) -> None:
        self.nesting += 1
        if self.nesting > self.depth_limit:
            raise ValueError("Parquet Thrift exceeds the nesting limit")

    def readStructBegin(self) -> None:  # noqa: N802 - Thrift protocol interface.
        self._enter()
        self.fields.append(set())
        super().readStructBegin()

    def readStructEnd(self) -> None:  # noqa: N802
        super().readStructEnd()
        self.fields.pop()
        self.nesting -= 1

    def readFieldBegin(self) -> tuple[None, int, int]:  # noqa: N802
        name, kind, field = self._bounded(super().readFieldBegin, 4)
        if kind != TType.STOP:
            if not 0 < field <= 32767 or field in self.fields[-1]:
                raise ValueError("Parquet Thrift has an invalid or duplicate field")
            if len(self.fields[-1]) >= self.field_limit:
                raise ValueError("Parquet Thrift exceeds the struct field limit")
            self.fields[-1].add(field)
        return name, kind, field

    def readCollectionBegin(self) -> tuple[int, int]:  # noqa: N802
        kind, count = self._bounded(super().readCollectionBegin, 6)
        self._charge(count)
        self._enter()
        return kind, count

    readListBegin = readCollectionBegin  # noqa: N815
    readSetBegin = readCollectionBegin  # noqa: N815

    def readMapBegin(self) -> tuple[int, int, int]:  # noqa: N802
        key, value, count = self._bounded(super().readMapBegin, 6)
        self._charge(2 * count)
        self._enter()
        return key, value, count

    def readCollectionEnd(self) -> None:  # noqa: N802
        super().readCollectionEnd()
        self.nesting -= 1

    readListEnd = readCollectionEnd  # noqa: N815
    readSetEnd = readCollectionEnd  # noqa: N815
    readMapEnd = readCollectionEnd  # noqa: N815

    def readBinary(self) -> bytes:  # noqa: N802
        # The length prefix is an unsigned int32 varint. A one-byte payload can
        # share this allowance; a larger read is bounded by the input window.
        return bytes(self._bounded(super().readBinary, 5))

    def readI16(self) -> int:  # noqa: N802
        return self._integer(super().readI16, 3, 16)

    def readI32(self) -> int:  # noqa: N802
        return self._integer(super().readI32, 5, 32)

    def readI64(self) -> int:  # noqa: N802
        return self._integer(super().readI64, 10, 64)

    def _integer(self, read: Callable[[], Any], width: int, bits: int) -> int:
        value = int(self._bounded(read, width))
        if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
            raise ValueError("Parquet Thrift integer exceeds its declared width")
        return value

    def skip(self, kind: int, max_depth: int = 64) -> None:
        # Thrift's generic skip treats binary statistics as UTF-8 strings.
        if kind == TType.STRING:
            self.readBinary()
        else:
            super().skip(kind, min(max_depth, self.depth_limit))


def _protocol(
    data: bytes, start: int, end: int, *, byte_limit: int, items: int, depth: int
) -> tuple[_Transport, _Compact]:
    source = _Transport(data, start, min(end, start + byte_limit))
    return source, _Compact(source, byte_limit=byte_limit, items=items, depth=depth)


def check_parquet_footer(
    data: bytes, *, max_footer_bytes: int, max_thrift_items: int, max_depth: int
) -> int:
    """Bound compact footer parsing before the native engine constructs metadata."""
    if len(data) < 12 or data[:4] != b"PAR1" or data[-4:] != b"PAR1":
        raise ValueError("invalid Parquet file framing")
    size = int.from_bytes(data[-8:-4], "little")
    if not 0 < size <= min(max_footer_bytes, len(data) - 12):
        raise ValueError("Parquet footer exceeds its byte limit or file boundary")
    start = len(data) - 8 - size
    source, protocol = _protocol(
        data,
        start,
        len(data) - 8,
        byte_limit=max_footer_bytes,
        items=max_thrift_items,
        depth=max_depth,
    )
    try:
        protocol.skip(TType.STRUCT)
        if source.position != len(data) - 8:
            raise ValueError("Parquet footer contains trailing bytes")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid bounded Parquet Thrift footer") from exc
    return start


@dataclass
class _Budget:
    limit: int
    used: int = 0

    def charge(self, size: int) -> None:
        if size < 0 or size > self.limit - self.used:
            raise ValueError("Parquet actual pages exceed the decode byte limit")
        self.used += size


def _decompress(body: memoryview, size: int, codec: str, engine: Any) -> memoryview:
    """Allocate only the admitted target, never the compressed stream's request."""
    try:
        if codec == "none":
            if len(body) != size:
                raise ValueError("uncompressed Parquet page has an inexact size")
            return body
        if codec == "snappy":
            if cramjam.snappy.decompress_raw_len(body) != size:
                raise ValueError("Snappy Parquet page has an inexact uncompressed size")
            target = bytearray(size)
            if cramjam.snappy.decompress_raw_into(body, target) != size:
                raise ValueError("Snappy Parquet page has an inexact decoded size")
            return memoryview(target)
        if codec == "zstd":
            return memoryview(
                engine.Codec("zstd").decompress(body, decompressed_size=size, asbytes=False)
            )
        raise ValueError("unsupported host Parquet compression")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid bounded Parquet compressed page") from exc


def _one_hybrid(body: memoryview, width: int) -> int:
    # One value admits a single RLE run or one padded eight-value bit-packed
    # group. No run count can make Arrow allocate a larger scratch vector.
    if width not in (0, 1) or not body:
        raise ValueError("unsupported one-row Parquet RLE stream")
    if body[0] == 2 and len(body) == 1 + width:
        value = int(body[1]) if width else 0
    elif body[0] == 3 and len(body) == 1 + width:
        value = int(body[1] & 1) if width else 0
        if width and body[1] >> 1:
            raise ValueError("Parquet bit-packed padding must be zero")
    else:
        raise ValueError("Parquet RLE stream contradicts the one-row profile")
    if value not in (0, 1):
        raise ValueError("Parquet definition level or dictionary index is out of range")
    return value


def _plain(body: memoryview, column: Column, count: int) -> int:
    if count == 0:
        if body:
            raise ValueError("Parquet null/empty dictionary has value bytes")
        return 0
    if column.type is ColumnType.STRING:
        if len(body) < 4:
            raise ValueError("truncated Parquet PLAIN string length")
        length = int.from_bytes(body[:4], "little", signed=True)
        if length < 0 or length != len(body) - 4:
            raise ValueError("Parquet PLAIN string length contradicts actual page bytes")
        return length
    if len(body) != 8:
        raise ValueError("Parquet PLAIN scalar must contain exactly one eight-byte value")
    return 0


def _data_value(
    header: _PageHeader,
    body: memoryview,
    column: Column,
    codec: str,
    engine: Any,
    dictionary_count: int | None,
    dictionary_bytes: int,
) -> int:
    v1, v2 = header.data_page_header, header.data_page_header_v2
    present = 1
    if v1 is not None:
        if (
            v1.num_values != 1
            or v1.definition_level_encoding != 3
            or v1.repetition_level_encoding != 3
        ):
            raise ValueError("Parquet data page count/levels contradict the one-row profile")
        encoding = v1.encoding
        decoded = _decompress(body, _size(header.uncompressed_page_size), codec, engine)
        if column.nullable:
            if len(decoded) < 4:
                raise ValueError("truncated Parquet definition-level prefix")
            length = int.from_bytes(decoded[:4], "little")
            if length > len(decoded) - 4:
                raise ValueError("Parquet definition levels exceed actual page bytes")
            present = _one_hybrid(decoded[4 : 4 + length], 1)
            decoded = decoded[4 + length :]
    elif v2 is not None:
        if v2.num_values != 1 or v2.num_rows != 1 or v2.num_nulls not in (0, 1):
            raise ValueError("Parquet V2 counts contradict the one-row profile")
        encoding = v2.encoding
        definition = _size(v2.definition_levels_byte_length)
        repetition = _size(v2.repetition_levels_byte_length)
        size = _size(header.uncompressed_page_size)
        if repetition != 0 or definition > min(len(body), size):
            raise ValueError("Parquet V2 level prefixes exceed actual page bytes")
        if column.nullable:
            present = _one_hybrid(body[:definition], 1)
        elif definition or v2.num_nulls:
            raise ValueError("required Parquet column has V2 nulls or definition levels")
        if v2.num_nulls != 1 - present:
            raise ValueError("Parquet V2 null count contradicts actual definition levels")
        decoded = _decompress(
            body[definition:], size - definition, codec if v2.is_compressed else "none", engine
        )
    else:
        raise ValueError("Parquet data page lacks its declared header")
    if encoding == 0:
        if dictionary_count is not None:
            raise ValueError("unused Parquet dictionary is outside the one-row profile")
        return _plain(decoded, column, present)
    if encoding not in (2, 8):
        raise ValueError("unsupported host Parquet value encoding (only PLAIN/dictionary)")
    if dictionary_count is None or not decoded or decoded[0] not in (0, 1):
        raise ValueError("Parquet dictionary page or bounded index width is missing")
    if not present:
        if len(decoded) != 1:
            raise ValueError("null Parquet dictionary value contains indices")
        return 0
    if dictionary_count != 1 or _one_hybrid(decoded[1:], int(decoded[0])) != 0:
        raise ValueError("Parquet dictionary cardinality/index contradicts the one-row profile")
    return dictionary_bytes


def _size(value: int | None) -> int:
    if value is None or not 0 <= value <= (1 << 31) - 1:
        raise ValueError("Parquet page has a missing or invalid int32 size")
    return value


def admit_host_parquet(
    data: bytes,
    *,
    footer_start: int,
    opened: Any,
    columns: Sequence[Column],
    compression: str,
    max_decode_bytes: int,
    max_header_bytes: int,
    max_thrift_items: int,
    max_depth: int,
    engine: Any,
) -> int:
    """Validate every page; return charged bytes before any native row decoding.

    This fixed raw profile permits one flat row, one row group, one data page
    per column and at most one PLAIN dictionary with zero or one entry. Auxiliary
    indexes, gaps, nested shapes and other value encodings are explicitly refused.
    """
    footer = opened.metadata
    if footer.num_rows != 1 or footer.num_row_groups != 1:
        raise ValueError("a raw host Parquet file must contain exactly one row and row group")
    group = footer.row_group(0)
    if (
        group.num_rows != 1
        or group.num_columns != len(columns)
        or len(opened.schema) != len(columns)
    ):
        raise ValueError("Parquet row-group shape contradicts the flat one-row host schema")
    budget = _Budget(max_decode_bytes)
    intervals: list[tuple[int, int]] = []
    group_size = 0
    for index, column in enumerate(columns):
        logical = column.type
        if not isinstance(logical, ColumnType) or logical not in (
            ColumnType.INT64,
            ColumnType.FLOAT64,
            ColumnType.STRING,
        ):
            raise ValueError("unsupported host Parquet column type")
        leaf = opened.schema.column(index)
        physical = {
            ColumnType.INT64: "INT64",
            ColumnType.FLOAT64: "DOUBLE",
            ColumnType.STRING: "BYTE_ARRAY",
        }[logical]
        if (
            leaf.name != column.name
            or leaf.path != column.name
            or leaf.physical_type != physical
            or leaf.max_repetition_level != 0
            or leaf.max_definition_level != int(column.nullable)
        ):
            raise ValueError("Parquet physical schema contradicts the flat host schema")
        chunk = group.column(index)
        if chunk.file_path or chunk.num_values != 1 or chunk.path_in_schema != column.name:
            raise ValueError("Parquet column file/path/count contradicts the host schema")
        expected_codec = "UNCOMPRESSED" if compression == "none" else compression.upper()
        if chunk.compression != expected_codec:
            raise ValueError("Parquet compression contradicts its envelope")
        if set(chunk.encodings) - {"PLAIN", "RLE", "RLE_DICTIONARY", "PLAIN_DICTIONARY"}:
            raise ValueError("unsupported host Parquet column encoding")
        if (
            chunk.has_column_index
            or chunk.has_offset_index
            or getattr(chunk, "bloom_filter_offset", None) is not None
        ):
            raise ValueError("Parquet auxiliary indexes are outside the one-row host profile")
        start = (
            chunk.dictionary_page_offset if chunk.has_dictionary_page else chunk.data_page_offset
        )
        if (
            start is None
            or start < 4
            or chunk.total_compressed_size <= 0
            or chunk.total_uncompressed_size < 0
        ):
            raise ValueError("Parquet column has invalid offsets or byte sizes")
        end = start + chunk.total_compressed_size
        if end > footer_start:
            raise ValueError("Parquet column bytes exceed the file body")
        if any(start < old_end and old_start < end for old_start, old_end in intervals):
            raise ValueError("Parquet column page intervals overlap")
        intervals.append((start, end))
        # One flat Arrow cell: eight-byte scalar or two int32 string offsets,
        # plus a validity byte when nullable. String payload is charged below.
        budget.charge(8 + int(column.nullable))
        position = start
        dictionary_count: int | None = None
        dictionary_bytes = 0
        page_count = data_count = total_size = 0
        while position < end:
            page_count += 1
            if page_count > 2 or data_count:
                raise ValueError("Parquet page count contradicts the one-row profile")
            source, protocol = _protocol(
                data,
                position,
                end,
                byte_limit=max_header_bytes,
                items=max_thrift_items,
                depth=max_depth,
            )
            header = _PageHeader()
            try:
                header.read(protocol)
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("invalid bounded Parquet PageHeader") from exc
            header_size = source.position - position
            compressed = _size(header.compressed_page_size)
            uncompressed = _size(header.uncompressed_page_size)
            if compressed > end - source.position:
                raise ValueError("truncated Parquet page body")
            budget.charge(header_size + uncompressed)
            total_size += header_size + uncompressed
            body = memoryview(data)[source.position : source.position + compressed]
            if header.crc is not None and zlib.crc32(body) != header.crc & 0xFFFFFFFF:
                raise ValueError("Parquet page CRC contradicts actual compressed bytes")
            variants = (
                header.data_page_header,
                header.index_page_header,
                header.dictionary_page_header,
                header.data_page_header_v2,
            )
            if sum(value is not None for value in variants) != 1:
                raise ValueError("Parquet page has missing or conflicting type headers")
            if header.type == 2 and header.dictionary_page_header is not None:
                dictionary = header.dictionary_page_header
                if (
                    position != start
                    or position != chunk.dictionary_page_offset
                    or dictionary_count is not None
                    or dictionary.num_values not in (0, 1)
                    or dictionary.encoding != 0
                ):
                    raise ValueError(
                        "Parquet dictionary cardinality/encoding/offset is unsupported"
                    )
                dictionary_count = dictionary.num_values
                dictionary_bytes = _plain(
                    _decompress(body, uncompressed, compression, engine), column, dictionary_count
                )
            elif (header.type == 0 and header.data_page_header is not None) or (
                header.type == 3 and header.data_page_header_v2 is not None
            ):
                if position != chunk.data_page_offset:
                    raise ValueError(
                        "Parquet data-page offset contradicts the actual page interval"
                    )
                data_count += 1
                payload = _data_value(
                    header, body, column, compression, engine, dictionary_count, dictionary_bytes
                )
                budget.charge(payload)
            else:
                raise ValueError("unsupported host Parquet page type")
            position = source.position + compressed
        if (
            position != end
            or data_count != 1
            or chunk.has_dictionary_page != (dictionary_count is not None)
            or total_size != chunk.total_uncompressed_size
        ):
            raise ValueError("Parquet page counts/totals contradict column metadata")
        group_size += total_size
    if group_size != group.total_byte_size:
        raise ValueError("Parquet actual page totals contradict row-group metadata")
    position = 4
    for start, end in sorted(intervals):
        if start != position:
            raise ValueError("Parquet page intervals leave unaccounted body bytes")
        position = end
    if position != footer_start:
        raise ValueError("Parquet page intervals leave unaccounted body bytes")
    return budget.used
