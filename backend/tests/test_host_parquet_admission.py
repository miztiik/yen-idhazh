"""Do real forged pages fail admission before Arrow enters its row decoder?"""

from __future__ import annotations

import sys
import tracemalloc
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import FrameType
from typing import Any

import cramjam
import pyarrow
import pyarrow.parquet
import pytest
from test_host_output_verify import LIMITS, render_file, source_row
from thrift.protocol.TCompactProtocol import TCompactProtocol
from thrift.Thrift import TType
from thrift.transport.TTransport import TMemoryBuffer

from idhazh.contracts.file_envelope import Format
from idhazh.contracts.host_output import HOST_OUTPUT_VERSION
from idhazh.ledger import parquet
from idhazh.telemetry.host_output_verify import host_output_columns, read_host_output
from idhazh.telemetry.host_parquet_admission import (
    _Compact,
    _decompress,
    _PageHeader,
    _Transport,
    admit_host_parquet,
    check_parquet_footer,
)

pytestmark = pytest.mark.contract
_Site = tuple[int, int, int]


def _footer_start(data: bytes) -> int:
    return len(data) - 8 - int.from_bytes(data[-8:-4], "little")


def _integer_sites(data: bytes, *, start: int = 0) -> dict[tuple[int, ...], _Site]:
    """Locate mutation sites with Apache's primitives; never interpret a footer schema."""
    source = _Transport(data, start, len(data))
    protocol = _Compact(source, byte_limit=len(data), items=100_000, depth=64)
    sites: dict[tuple[int, ...], _Site] = {}

    def visit(kind: int, path: tuple[int, ...]) -> None:
        if kind == TType.STRUCT:
            protocol.readStructBegin()
            while True:
                _, field_kind, field = protocol.readFieldBegin()
                if field_kind == TType.STOP:
                    break
                visit(field_kind, (*path, field))
                protocol.readFieldEnd()
            protocol.readStructEnd()
        elif kind == TType.LIST:
            item_kind, count = protocol.readListBegin()
            for index in range(count):
                visit(item_kind, (*path, index))
            protocol.readListEnd()
        elif kind in (TType.I16, TType.I32, TType.I64):
            before = source.position
            value = protocol.readFieldByTType(kind, None)
            sites[path] = (before, source.position, kind)
            assert isinstance(value, int)
        else:
            protocol.skip(kind)

    visit(TType.STRUCT, ())
    return sites


def _encoded_integer(kind: int, value: int) -> bytes:
    transport = TMemoryBuffer()
    protocol = TCompactProtocol(transport)
    protocol.writeStructBegin("mutation")
    protocol.writeFieldBegin("value", kind, 1)
    protocol.writeFieldByTType(kind, value, None)
    # The compact field header is one byte; only the scalar replaces the site.
    return bytes(transport.getvalue()[1:])


def _patch_footer(data: bytes, changes: dict[tuple[int, ...], int]) -> bytes:
    start = _footer_start(data)
    footer = data[start:-8]
    sites = _integer_sites(footer)
    for path, value in sorted(changes.items(), key=lambda item: sites[item[0]][0], reverse=True):
        before, after, kind = sites[path]
        footer = footer[:before] + _encoded_integer(kind, value) + footer[after:]
    return data[:start] + footer + len(footer).to_bytes(4, "little") + b"PAR1"


def _column_path(index: int, field: int) -> tuple[int, ...]:
    return 4, 0, 1, index, 3, field


def _generated(
    root: Path,
    *,
    codec: str = "none",
    dictionary: bool = False,
    version: str = "1.0",
    rows: list[dict[str, Any]] | None = None,
    **options: Any,
) -> tuple[Path, bytes]:
    cells = rows if rows is not None else [source_row()]
    path, env, _ = render_file(root, Format.PARQUET, rows=cells, compression=codec)
    schema = parquet.schema_of(host_output_columns(HOST_OUTPUT_VERSION)).with_metadata(
        env.as_metadata()
    )
    sink = pyarrow.BufferOutputStream()
    pyarrow.parquet.write_table(
        pyarrow.Table.from_pylist(cells, schema=schema),
        sink,
        compression=None if codec == "none" else codec,
        use_dictionary=dictionary,
        data_page_version=version,
        write_statistics=False,
        **options,
    )
    data = sink.getvalue().to_pybytes()
    path.write_bytes(data)
    return path, data


def _header(data: bytes, offset: int) -> tuple[_PageHeader, int]:
    source = _Transport(data, offset, _footer_start(data))
    header = _PageHeader()
    header.read(_Compact(source, byte_limit=100_000, items=1000, depth=12))
    return header, source.position


def _replace_page(
    data: bytes,
    index: int,
    *,
    dictionary: bool = False,
    change: Callable[[_PageHeader, bytes], tuple[_PageHeader, bytes]],
    extra: bytes = b"",
) -> bytes:
    """Reconcile real chunk offsets/sizes after one page mutation, using Arrow's footer."""
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    group = opened.metadata.row_group(0)
    chunks: list[bytes] = []
    patches: dict[tuple[int, ...], int] = {}
    position = 4
    total = 0
    for column_index in range(group.num_columns):
        chunk = group.column(column_index)
        start = (
            chunk.dictionary_page_offset if chunk.has_dictionary_page else chunk.data_page_offset
        )
        assert start is not None
        raw = data[start : start + chunk.total_compressed_size]
        page_offset = chunk.dictionary_page_offset if dictionary else chunk.data_page_offset
        if column_index == index:
            assert page_offset is not None
            header, body_start = _header(data, page_offset)
            assert header.compressed_page_size is not None
            body = data[body_start : body_start + header.compressed_page_size]
            header, body = change(header, body)
            transport = TMemoryBuffer()
            header.write(TCompactProtocol(transport))
            replacement = bytes(transport.getvalue()) + body + extra
            before = page_offset - start
            # Original body length is independent of the possibly mutated header.
            old_header, _ = _header(data, page_offset)
            assert old_header.compressed_page_size is not None
            after = body_start - start + old_header.compressed_page_size
            raw = raw[:before] + replacement + raw[after:]
        local = 0
        uncompressed = 0
        while local < len(raw):
            # The small temporary file framing makes the same bounded reader usable.
            framed = b"PAR1" + raw + b"\0\0\0\0PAR1"
            header, body_start = _header(framed, 4 + local)
            assert header.uncompressed_page_size is not None
            assert header.compressed_page_size is not None
            if header.type == 2 and chunk.has_dictionary_page:
                patches[_column_path(column_index, 11)] = position + local
            elif header.type in (0, 3) or (local == 0 and not chunk.has_dictionary_page):
                patches.setdefault(_column_path(column_index, 9), position + local)
            uncompressed += body_start - (4 + local) + header.uncompressed_page_size
            local = body_start - 4 + header.compressed_page_size
        patches[_column_path(column_index, 6)] = uncompressed
        patches[_column_path(column_index, 7)] = len(raw)
        total += uncompressed
        position += len(raw)
        chunks.append(raw)
    patches[(4, 0, 2)] = total
    footer = data[_footer_start(data) : -8]
    rebuilt = b"PAR1" + b"".join(chunks) + footer + len(footer).to_bytes(4, "little") + b"PAR1"
    return _patch_footer(rebuilt, patches)


def _insert_header_extra(data: bytes, index: int, extra: bytes) -> bytes:
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    group = opened.metadata.row_group(0)
    chunk = group.column(index)
    _, end = _header(data, chunk.data_page_offset)
    assert data[end - 1] == 0
    delta = len(extra)
    changes = {
        _column_path(index, 6): chunk.total_uncompressed_size + delta,
        _column_path(index, 7): chunk.total_compressed_size + delta,
        (4, 0, 2): group.total_byte_size + delta,
    }
    for subsequent in range(index + 1, group.num_columns):
        column = group.column(subsequent)
        changes[_column_path(subsequent, 9)] = column.data_page_offset + delta
        if column.has_dictionary_page:
            changes[_column_path(subsequent, 11)] = column.dictionary_page_offset + delta
    inserted = data[: end - 1] + extra + data[end - 1 :]
    return _patch_footer(inserted, changes)


def _observe(
    path: Path,
    root: Path,
    *,
    decode_bytes: int = LIMITS.max_decode_bytes,
    rejected: bool = True,
) -> tuple[int, int]:
    """Observe the real Arrow decoder and native allocator, without replacing either."""
    entries: list[str] = []
    allocating_snappy: list[str] = []
    original = sys.getprofile()
    previous_pool = pyarrow.default_memory_pool()
    pool = pyarrow.proxy_memory_pool(previous_pool)

    def profile(frame: FrameType, event: str, argument: Any) -> None:
        if (
            event == "call"
            and frame.f_code.co_name == "iter_batches"
            and frame.f_globals.get("__name__") == "pyarrow.parquet.core"
        ):
            entries.append("row decode")
        if event == "c_call" and getattr(argument, "__name__", "") == "decompress_raw":
            allocating_snappy.append("unbounded raw decompressor")

    pyarrow.set_memory_pool(pool)
    sys.setprofile(profile)
    try:
        if rejected:
            with pytest.raises(ValueError):
                read_host_output(
                    path, root=root, limits=replace(LIMITS, max_decode_bytes=decode_bytes)
                )
        else:
            assert (
                len(
                    read_host_output(
                        path, root=root, limits=replace(LIMITS, max_decode_bytes=decode_bytes)
                    ).rows
                )
                == 1
            )
        peak = int(pool.max_memory())
    finally:
        sys.setprofile(original)
        pyarrow.set_memory_pool(previous_pool)
    assert bool(entries) is not rejected, "observe the real Arrow row decoder only after admission"
    assert allocating_snappy == [], "the allocating raw Snappy decoder must never be called"
    return len(entries), peak


@pytest.mark.parametrize("codec", ["none", "snappy", "zstd"])
@pytest.mark.parametrize("dictionary", [False, True])
@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_real_codecs_plain_and_single_entry_dictionaries(
    tmp_path: Path,
    codec: str,
    dictionary: bool,
    version: str,
) -> None:
    path, data = _generated(tmp_path, codec=codec, dictionary=dictionary, version=version)
    assert (
        read_host_output(path, root=tmp_path, limits=LIMITS).rows[0].cpu_model
        == "Recorded CPU \u03b1"
    )
    assert path.read_bytes() == data


@pytest.mark.parametrize("dictionary", [False, True])
@pytest.mark.parametrize("forged_columns", ["all", "large_value"])
def test_forged_small_zstd_footer_cannot_allocate_two_million_character_value(
    tmp_path: Path,
    dictionary: bool,
    forged_columns: str,
) -> None:
    path, data = _generated(
        tmp_path,
        codec="zstd",
        dictionary=dictionary,
        rows=[source_row() | {"cpu_model": "x" * 2_000_000}],
    )
    assert len(data) < LIMITS.max_file_bytes
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    group = opened.metadata.row_group(0)
    changes = {
        _column_path(index, 6): 0
        for index in (range(group.num_columns) if forged_columns == "all" else [7])
    }
    changes[(4, 0, 2)] = (
        0
        if forged_columns == "all"
        else group.total_byte_size - group.column(7).total_uncompressed_size
    )
    forged = _patch_footer(data, changes)
    path.write_bytes(forged)
    _, peak = _observe(path, tmp_path, decode_bytes=4096)
    assert peak < 4096, f"bounded admission allocated {peak} native bytes"
    assert path.read_bytes() == forged

    # Calibrate the real allocator against the previously vulnerable operation.
    previous_pool = pyarrow.default_memory_pool()
    pool = pyarrow.proxy_memory_pool(previous_pool)
    pyarrow.set_memory_pool(pool)
    try:
        table = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(forged)).read(use_threads=False)
        assert table.column("cpu_model")[0].as_py() == "x" * 2_000_000
        assert pool.max_memory() >= 2_000_000
        del table
    finally:
        pyarrow.set_memory_pool(previous_pool)


@pytest.mark.parametrize("field", [6, 7, 9, 11])
def test_forged_column_totals_and_offsets_fail_before_native_decode(
    tmp_path: Path, field: int
) -> None:
    path, data = _generated(tmp_path, dictionary=True)
    path.write_bytes(_patch_footer(data, {_column_path(0, field): 0}))
    _observe(path, tmp_path)


@pytest.mark.parametrize("codec", ["snappy", "zstd"])
def test_actual_codec_output_cannot_overrun_a_forged_small_page_size(
    tmp_path: Path,
    codec: str,
) -> None:
    path, data = _generated(
        tmp_path,
        codec=codec,
        rows=[source_row() | {"cpu_model": "x" * 2_000_000}],
    )

    def change(header: _PageHeader, body: bytes) -> tuple[_PageHeader, bytes]:
        header.uncompressed_page_size = 32
        return header, body

    forged = _replace_page(data, 7, change=change)
    path.write_bytes(forged)
    tracemalloc.start()
    try:
        _, native_peak = _observe(path, tmp_path, decode_bytes=4096)
        _, python_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert native_peak < 4096
    assert python_peak < 1_000_000
    assert path.read_bytes() == forged


def test_real_decoder_observer_and_allocator_are_calibrated(tmp_path: Path) -> None:
    path, _ = _generated(tmp_path, codec="snappy", dictionary=True)
    entries, peak = _observe(path, tmp_path, rejected=False)
    assert entries > 0 and peak > 0


@pytest.mark.parametrize("codec", ["none", "snappy", "zstd"])
def test_real_page_checksums_and_compressed_v2_values(tmp_path: Path, codec: str) -> None:
    path, data = _generated(
        tmp_path,
        codec=codec,
        version="2.0",
        rows=[source_row() | {"cpu_model": "hardware" * 128}],
        write_page_checksum=True,
    )
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    header, _ = _header(data, opened.metadata.row_group(0).column(7).data_page_offset)
    assert header.crc is not None and header.data_page_header_v2 is not None
    if codec != "none":
        assert header.data_page_header_v2.is_compressed is True
    assert (
        read_host_output(path, root=tmp_path, limits=LIMITS).rows[0].cpu_model == "hardware" * 128
    )
    assert path.read_bytes() == data


def test_page_indexes_are_explicitly_outside_the_fixed_raw_profile(tmp_path: Path) -> None:
    path, _ = _generated(tmp_path, write_page_index=True)
    # No statistics means no column index, but Arrow still emits an offset index.
    _observe(path, tmp_path)


@pytest.mark.parametrize(
    "column,encoding",
    [
        ("cpu_model", "DELTA_BYTE_ARRAY"),
        ("cpu_model", "DELTA_LENGTH_BYTE_ARRAY"),
        ("shard", "DELTA_BINARY_PACKED"),
        ("boot_seconds", "BYTE_STREAM_SPLIT"),
    ],
)
def test_real_unsupported_encoders_are_explicitly_refused(
    tmp_path: Path,
    column: str,
    encoding: str,
) -> None:
    path, data = _generated(
        tmp_path,
        rows=[source_row() | {"boot_seconds": 1.0}],
        column_encoding={column: encoding},
    )
    assert pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data)).read().num_rows == 1
    _observe(path, tmp_path)


@pytest.mark.parametrize("shape", ["list", "struct", "int32"])
def test_nested_or_wrong_physical_schema_cannot_enter_native_decode(
    tmp_path: Path,
    shape: str,
) -> None:
    path, env, _ = render_file(tmp_path, Format.PARQUET)
    expected = parquet.schema_of(host_output_columns(HOST_OUTPUT_VERSION))
    index = expected.get_field_index("cpu_model")
    dtype = {
        "list": pyarrow.list_(pyarrow.string()),
        "struct": pyarrow.struct([pyarrow.field("fact", pyarrow.string())]),
        "int32": pyarrow.int32(),
    }[shape]
    cells = source_row() | {
        "cpu_model": {"list": ["CPU"], "struct": {"fact": "CPU"}, "int32": 1}[shape]
    }
    schema = expected.set(index, pyarrow.field("cpu_model", dtype, nullable=True)).with_metadata(
        env.as_metadata()
    )
    sink = pyarrow.BufferOutputStream()
    pyarrow.parquet.write_table(pyarrow.Table.from_pylist([cells], schema=schema), sink)
    path.write_bytes(sink.getvalue().to_pybytes())
    _observe(path, tmp_path)


@pytest.mark.parametrize(
    "kind", ["varint", "string", "container", "depth", "duplicate", "missing_size"]
)
def test_hostile_actual_page_headers_are_bounded_before_native_decode(
    tmp_path: Path,
    kind: str,
) -> None:
    path, data = _generated(tmp_path)
    extras = {
        "varint": b"\x06\x12" + b"\xff" * 20_000 + b"\x01",
        "string": b"\x08\x12\xa0\x8d\x06" + b"x" * 100,
        "container": b"\x09\x12\xf5\x80\x89\x7a",
        "depth": b"\x0c\x12" + b"\x1c" * 20 + b"\x00" * 21,
        "duplicate": b"\x05\x02\x00",
    }
    if kind == "missing_size":
        # Change field 2's type to I64; its required I32 binding must stay unset.
        before, _, _ = _integer_sites(data, start=4)[(2,)]
        forged = data[: before - 1] + b"\x16" + data[before:]
    else:
        forged = _insert_header_extra(data, 0, extras[kind])
    path.write_bytes(forged)
    _observe(path, tmp_path)
    assert path.read_bytes() == forged


@pytest.mark.parametrize("mutation", ["overlap", "gap", "count", "group_total", "footer_rows"])
def test_footer_interval_and_count_reconciliation(tmp_path: Path, mutation: str) -> None:
    path, data = _generated(tmp_path)
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    first = opened.metadata.row_group(0).column(0)
    mutations: dict[str, dict[tuple[int, ...], int]] = {
        "overlap": {_column_path(1, 9): first.data_page_offset},
        "gap": {_column_path(0, 9): first.data_page_offset + 1},
        "count": {_column_path(0, 5): 2_000_000},
        "group_total": {(4, 0, 2): 0},
        "footer_rows": {(3,): 2_000_000},
    }
    changes = mutations[mutation]
    path.write_bytes(_patch_footer(data, changes))
    _observe(path, tmp_path)


@pytest.mark.parametrize("version", ["1.0", "2.0"])
@pytest.mark.parametrize("mutation", ["count", "encoding", "size", "string_length"])
def test_actual_data_page_counts_encodings_sizes_and_string_lengths(
    tmp_path: Path,
    version: str,
    mutation: str,
) -> None:
    path, data = _generated(tmp_path, version=version)

    def change(header: _PageHeader, body: bytes) -> tuple[_PageHeader, bytes]:
        page = header.data_page_header or header.data_page_header_v2
        assert page is not None
        if mutation == "count":
            page.num_values = 2_000_000
        elif mutation == "encoding":
            page.encoding = 7
        elif mutation == "size":
            assert header.uncompressed_page_size is not None
            header.uncompressed_page_size += 1
        else:
            body = (2_000_000).to_bytes(4, "little") + body[4:]
        return header, body

    path.write_bytes(_replace_page(data, 0, change=change))
    _observe(path, tmp_path)


@pytest.mark.parametrize("mutation", ["cardinality", "encoding", "index", "width"])
def test_dictionary_cardinality_and_indices_are_checked_before_decode(
    tmp_path: Path,
    mutation: str,
) -> None:
    path, data = _generated(tmp_path, dictionary=True)

    def change(header: _PageHeader, body: bytes) -> tuple[_PageHeader, bytes]:
        if mutation in ("cardinality", "encoding"):
            page = header.dictionary_page_header
            assert page is not None
            if mutation == "cardinality":
                page.num_values = 2_000_000
            else:
                page.encoding = 2
        elif mutation == "index":
            body = body[:-1] + b"\x01"
        else:
            body = b"\x20" + body[1:]
        return header, body

    path.write_bytes(
        _replace_page(data, 0, dictionary=mutation in ("cardinality", "encoding"), change=change)
    )
    _observe(path, tmp_path)


@pytest.mark.parametrize("mutation", ["definition", "repetition", "rows", "nulls"])
def test_v2_level_prefixes_are_separate_from_compressed_values(
    tmp_path: Path,
    mutation: str,
) -> None:
    path, data = _generated(tmp_path, codec="zstd", version="2.0")

    def change(header: _PageHeader, body: bytes) -> tuple[_PageHeader, bytes]:
        page = header.data_page_header_v2
        assert page is not None
        if mutation == "definition":
            page.definition_levels_byte_length = 2_000_000
        elif mutation == "repetition":
            page.repetition_levels_byte_length = 1
        elif mutation == "rows":
            page.num_rows = 2
        else:
            page.num_nulls = 1
        return header, body

    path.write_bytes(_replace_page(data, 7, change=change))
    _observe(path, tmp_path)


@pytest.mark.parametrize("codec", ["none", "snappy", "zstd"])
@pytest.mark.parametrize("delta", [-1, 1])
def test_codec_rejects_understatement_and_overstatement_without_allocating_output_stream_size(
    codec: str,
    delta: int,
) -> None:
    value = b"bounded real output"
    body = (
        value
        if codec == "none"
        else bytes(cramjam.snappy.compress_raw(value))
        if codec == "snappy"
        else pyarrow.Codec("zstd").compress(value, asbytes=True)
    )
    with pytest.raises(ValueError):
        _decompress(memoryview(body), len(value) + delta, codec, pyarrow)
    assert bytes(_decompress(memoryview(body), len(value), codec, pyarrow)) == value


def test_page_and_arrow_buffers_share_one_cumulative_budget(tmp_path: Path) -> None:
    path, data = _generated(tmp_path, dictionary=True)
    opened = pyarrow.parquet.ParquetFile(pyarrow.BufferReader(data))
    page_total = opened.metadata.row_group(0).total_byte_size
    assert page_total < LIMITS.max_decode_bytes
    _observe(path, tmp_path, decode_bytes=page_total)
    charged = admit_host_parquet(
        data,
        footer_start=_footer_start(data),
        opened=opened,
        columns=host_output_columns(HOST_OUTPUT_VERSION),
        compression="none",
        max_decode_bytes=LIMITS.max_decode_bytes,
        max_header_bytes=LIMITS.max_footer_bytes,
        max_thrift_items=LIMITS.max_thrift_items,
        max_depth=LIMITS.max_json_depth,
        engine=pyarrow,
    )
    assert charged > page_total + 8 * len(host_output_columns(HOST_OUTPUT_VERSION))
    assert (
        len(
            read_host_output(
                path, root=tmp_path, limits=replace(LIMITS, max_decode_bytes=charged)
            ).rows
        )
        == 1
    )
    _observe(path, tmp_path, decode_bytes=charged - 1)


def test_two_rows_fail_before_native_decode_even_under_generous_row_limit(tmp_path: Path) -> None:
    path, _ = _generated(tmp_path, rows=[source_row(), source_row()])
    _observe(path, tmp_path)


@pytest.mark.parametrize("mutation", ["truncate", "duplicate_data", "crc", "page_type"])
def test_truncated_extra_or_conflicting_pages_are_refused(tmp_path: Path, mutation: str) -> None:
    path, data = _generated(tmp_path)
    if mutation == "truncate":
        path.write_bytes(data[: _footer_start(data) - 1] + data[_footer_start(data) :])
    else:

        def change(header: _PageHeader, body: bytes) -> tuple[_PageHeader, bytes]:
            if mutation == "crc":
                header.crc = 1
            elif mutation == "page_type":
                header.type = 2
            return header, body

        first, body_start = _header(data, 4)
        assert first.compressed_page_size is not None
        extra = (
            data[4 : body_start + first.compressed_page_size]
            if mutation == "duplicate_data"
            else b""
        )
        path.write_bytes(_replace_page(data, 0, change=change, extra=extra))
    _observe(path, tmp_path)


@pytest.mark.parametrize("kind", ["string", "container", "depth", "items", "duplicate"])
def test_maintained_compact_unknown_fields_have_bounded_resources(kind: str) -> None:
    transport = TMemoryBuffer()
    protocol = TCompactProtocol(transport)
    protocol.writeStructBegin("hostile")
    if kind == "string":
        protocol.writeFieldBegin("unknown", TType.STRING, 9)
        protocol.writeBinary(b"x" * 100)
        protocol.writeFieldEnd()
    elif kind in ("container", "items"):
        for field in range(1, 3 if kind == "items" else 2):
            protocol.writeFieldBegin("unknown", TType.LIST, field)
            protocol.writeListBegin(TType.I32, 6 if kind == "items" else 100)
            for _ in range(6 if kind == "items" else 100):
                protocol.writeI32(0)
            protocol.writeListEnd()
            protocol.writeFieldEnd()
    elif kind == "depth":
        for _ in range(20):
            protocol.writeFieldBegin("unknown", TType.STRUCT, 1)
            protocol.writeStructBegin("nested")
        for _ in range(20):
            protocol.writeFieldStop()
            protocol.writeStructEnd()
            protocol.writeFieldEnd()
    else:
        for _ in range(2):
            protocol.writeFieldBegin("unknown", TType.I32, 1)
            protocol.writeI32(0)
            protocol.writeFieldEnd()
    protocol.writeFieldStop()
    protocol.writeStructEnd()
    footer = bytes(transport.getvalue())
    if kind == "string":
        footer = footer[:1] + b"\x80\x20" + footer[2:]  # Claim 4096 bytes, supply only 100.
    data = b"PAR1" + footer + len(footer).to_bytes(4, "little") + b"PAR1"
    with pytest.raises(ValueError):
        check_parquet_footer(data, max_footer_bytes=len(footer), max_thrift_items=10, max_depth=12)
