"""Read only named, hash-pinned historical host containers under fixed byte and row bounds."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import struct
import subprocess
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from idhazh.contracts.console_band import ConsoleBand
from idhazh.contracts.file_envelope import FileEnvelope, Format, Period, RowIdentity, Tier
from idhazh.contracts.host_migration import (
    HistoryManifest,
    HistoryRoot,
    HistorySource,
    LegacyRawEvidence,
)
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HOST_PRODUCER,
    LEGACY_HOST_VERSIONS,
    HostStoredRow,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    host_file_id,
    host_unit_id,
    normalize_stored_host_rows,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import json_lines, parquet, paths
from idhazh.ledger.arrow_schema import Column, ColumnType
from idhazh.ledger.filenames import unit_id
from idhazh.telemetry.host_output_verify import (
    VerificationLimits,
    _json,
    _read_bytes,
    _read_json,
    _read_parquet,
    _validate_rows,
    host_output_columns,
)
from idhazh.telemetry.host_parquet_admission import (
    _Budget,
    _decompress,
    _PageHeader,
    _protocol,
    _size,
    check_parquet_footer,
)

# These are the envelope shapes with this exact metadata-key contract, not a
# permissive date interval. Earlier layouts require an explicitly declared adapter.
ENVELOPE_VERSIONS = frozenset(
    {
        "2026-09-27",
        "2026-09-28",
        "2026-09-30",
        "2026-10-01",
        "2026-10-01T16:50",
        "2026-10-06",
        HOST_OUTPUT_VERSION,
    }
)
_GIT_TREE_LOOKUP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class HistoryLimits:
    verification: VerificationLimits
    max_roots: int
    max_periods: int
    max_sources: int
    max_history_file_rows: int
    max_history_rows: int
    max_manifest_bytes: int
    max_bundle_bytes: int

    @classmethod
    def from_config(cls, document: dict[str, Any]) -> HistoryLimits:
        verification = VerificationLimits(**document["verification_limits"])
        knobs = document["history_migration_limits"]
        required = {field.name for field in fields(cls)} - {"verification"}
        if set(knobs) != required or any(type(v) is not int or v < 1 for v in knobs.values()):
            raise ValueError("history_migration_limits requires positive named integer bounds")
        return cls(verification=verification, **knobs)

    def report_bounds(self) -> dict[str, int]:
        return {
            field.name: getattr(self.verification, field.name)
            for field in fields(self.verification)
        } | {
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name != "verification"
        }

    @property
    def history_verification(self) -> VerificationLimits:
        return replace(self.verification, max_rows=self.max_history_file_rows)

    def check_manifest(self, manifest: HistoryManifest) -> None:
        if len(manifest.sources) > self.max_sources:
            raise ValueError("manifest exceeds max_sources")
        if len(manifest.legacy_raw_evidence) > self.max_sources:
            raise ValueError("manifest exceeds max legacy raw evidence")
        if len(manifest.roots) > self.max_roots or len(manifest.closed_periods) > self.max_periods:
            raise ValueError("manifest exceeds root or period bounds")
        if any(s.bytes > self.verification.max_file_bytes for s in manifest.sources):
            raise ValueError("manifest exceeds max_file_bytes")
        if sum(s.bytes for s in manifest.sources) > self.verification.max_total_bytes:
            raise ValueError("manifest exceeds max_total_bytes")
        if len(manifest.to_json().encode("ascii")) > self.max_manifest_bytes:
            raise ValueError("manifest exceeds max_manifest_bytes")


@dataclass(frozen=True)
class HistoryFile:
    source: HistorySource
    data: bytes
    envelope: FileEnvelope | None
    original_rows: tuple[dict[str, Any], ...]
    rows: tuple[HostStoredRow, ...]
    document: dict[str, Any] | None
    container: Format | None


def read_source(source: HistorySource, *, workspace: Path, limits: VerificationLimits) -> bytes:
    try:
        data = _read_bytes(workspace / source.path, root=workspace, cap=limits.max_file_bytes)
    except OSError as error:
        raise ValueError(
            f"{source.path}: missing or unreadable source ({type(error).__name__})"
        ) from error
    if len(data) != source.bytes or hashlib.sha256(data).hexdigest() != source.sha256:
        raise ValueError(f"{source.path}: source physical hash or size drift")
    return data


def _read_evidence(
    evidence: LegacyRawEvidence,
    *,
    workspace: Path,
    limits: VerificationLimits,
    git_path: str | None = None,
) -> bytes:
    try:
        data = _read_bytes(
            workspace / evidence.path,
            root=workspace,
            cap=limits.max_file_bytes,
        )
    except OSError as error:
        raise ValueError(
            f"{evidence.path}: missing or unreadable legacy evidence ({type(error).__name__})"
        ) from error
    if len(data) != evidence.bytes or hashlib.sha256(data).hexdigest() != evidence.sha256:
        raise ValueError(f"{evidence.path}: legacy evidence physical hash or size drift")
    git_blob = hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()
    if git_blob != evidence.git_blob:
        raise ValueError(f"{evidence.path}: Git blob evidence does not match its bytes")
    _verify_git_tree_entry(evidence, workspace=workspace, git_path=git_path)
    return data


def legacy_raw_git_path(evidence: LegacyRawEvidence, root: HistoryRoot) -> str:
    """Resolve a staged legacy CSV path to its exact path in the declared history root."""
    staged = PurePosixPath(evidence.path)
    try:
        relative = staged.relative_to(PurePosixPath("evidence/legacy"))
    except ValueError:
        return evidence.path
    if len(relative.parts) != 4:
        raise ValueError(f"{evidence.path}: legacy evidence path must name one closed day")
    year, month, day, _ = relative.parts
    try:
        closed_day = date.fromisoformat(f"{year}-{month}-{day}")
    except ValueError as error:
        raise ValueError(f"{evidence.path}: legacy evidence path has an invalid UTC day") from error
    if closed_day.isoformat() != f"{year}-{month}-{day}":
        raise ValueError(f"{evidence.path}: legacy evidence path has a noncanonical UTC day")
    return PurePosixPath(root.state_root, *root.prefix, *relative.parts).as_posix()


def _verify_git_tree_entry(
    evidence: LegacyRawEvidence, *, workspace: Path, git_path: str | None = None
) -> None:
    expected_path = evidence.path if git_path is None else git_path
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    common = ["git", "--no-replace-objects", "cat-file", "-t", evidence.git_commit]
    try:
        commit = subprocess.run(
            common,
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=_GIT_TREE_LOOKUP_TIMEOUT_SECONDS,
        )
        if commit.returncode != 0 or commit.stdout.strip() != b"commit":
            raise ValueError(f"{evidence.path}: Git commit evidence is unavailable")
        entry = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "--literal-pathspecs",
                "ls-tree",
                "-z",
                "--full-tree",
                evidence.git_commit,
                "--",
                expected_path,
            ],
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=_GIT_TREE_LOOKUP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"{evidence.path}: Git tree evidence could not be read") from error
    if entry.returncode != 0:
        raise ValueError(f"{evidence.path}: Git commit tree is unavailable")
    records = entry.stdout.split(b"\0")
    if len(records) != 2 or not records[0] or records[1]:
        raise ValueError(f"{evidence.path}: Git commit tree has no exact file entry")
    header, separator, tree_path = records[0].partition(b"\t")
    metadata = header.split(b" ")
    if (
        not separator
        or len(metadata) != 3
        or metadata[1] != b"blob"
        or metadata[2] != evidence.git_blob.encode("ascii")
        or tree_path != expected_path.encode("utf-8")
    ):
        raise ValueError(f"{evidence.path}: Git commit path does not name the claimed blob")


_LEGACY_INT_FIELDS = frozenset(
    {
        "shard",
        "cpu_family",
        "cpu_model_number",
        "cpu_stepping",
        "cores",
        "threads",
        "l3_cache_bytes",
        "memcpy_probe_mib",
        "job_seconds",
        "server_prompt_tokens",
    }
)
_LEGACY_FLOAT_FIELDS = frozenset(
    {
        "mhz_max",
        "mhz_at_probe",
        "boot_seconds",
        "memcpy_gib_s",
        "model_load_ms",
        "server_prompt_seconds",
    }
)


def _legacy_csv_value(name: str, value: str) -> object:
    if value == "":
        return None
    if name in _LEGACY_INT_FIELDS:
        return int(value)
    if name in _LEGACY_FLOAT_FIELDS:
        return float(value)
    return value


def _legacy_raw_row(
    data: bytes, evidence: LegacyRawEvidence
) -> dict[tuple[str, str, int], dict[str, Any]]:
    if not data.isascii() or b"\r" in data or not data.endswith(b"\n"):
        raise ValueError(f"{evidence.path}: legacy raw evidence must be ASCII LF CSV")
    reader = csv.DictReader(io.StringIO(data.decode("ascii"), newline=""))
    expected_fields = set(LegacyHostFingerprintRow.model_fields)
    if (
        reader.fieldnames is None
        or len(reader.fieldnames) != len(set(reader.fieldnames))
        or set(reader.fieldnames) != expected_fields
    ):
        raise ValueError(f"{evidence.path}: legacy raw evidence has an unknown header")
    merged: dict[str, object] = {}
    for record in reader:
        if None in record or any(value is None for value in record.values()):
            raise ValueError(f"{evidence.path}: legacy raw evidence has a malformed row")
        for name, value in record.items():
            parsed = _legacy_csv_value(name, value)
            if parsed is None:
                continue
            previous = merged.get(name)
            if previous is not None and previous != parsed:
                raise ValueError(f"{evidence.path}: legacy raw evidence rows disagree")
            merged[name] = parsed
    try:
        old = LegacyHostFingerprintRow.model_validate(merged)
    except ValueError as error:
        raise ValueError(f"{evidence.path}: legacy raw evidence row is invalid") from error
    identity = HostWriterIdentity(
        run_id=old.run_id,
        attempt=evidence.attempt,
        job=old.job,
        shard=old.shard,
        producer=HOST_PRODUCER,
        git_sha=evidence.git_commit,
    )
    unit = host_unit_id(covers=old.date, identity=identity)
    payload = old.model_dump(mode="json")
    payload.update(
        ledger=LedgerName.HOST_FINGERPRINT.value,
        covers=old.date,
        attempt=evidence.attempt,
        unit_id=str(unit),
    )
    key = (old.run_id, old.job.value, old.shard)
    return {key: payload}


def read_legacy_raw_evidence(
    evidence: LegacyRawEvidence,
    *,
    workspace: Path,
    limits: VerificationLimits,
    git_path: str | None = None,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    return _legacy_raw_row(
        _read_evidence(
            evidence,
            workspace=workspace,
            limits=limits,
            git_path=git_path,
        ),
        evidence,
    )


def _hybrid(data: memoryview, width: int, count: int) -> tuple[int, ...]:
    """Admit a finite RLE/bit-packed stream, including only its final pad group."""
    if width < 0 or width > max(1, count.bit_length()):
        raise ValueError("Parquet RLE width exceeds the bounded cardinality")
    position = 0
    values: list[int] = []
    while position < len(data) and len(values) < count:
        header = 0
        for shift in range(0, 35, 7):
            if position == len(data):
                raise ValueError("truncated Parquet RLE header")
            byte = data[position]
            position += 1
            header |= (byte & 127) << shift
            if not byte & 128:
                break
        else:
            raise ValueError("Parquet RLE varint exceeds int32")
        if header == 0:
            raise ValueError("zero Parquet RLE run")
        if header & 1:
            length = (header >> 1) * 8
            size = (length * width + 7) // 8
            if length > count - len(values) + 7 or position + size > len(data):
                raise ValueError("Parquet bit-packed run exceeds row bounds")
            bits = int.from_bytes(data[position : position + size], "little")
            position += size
            decoded = [(bits >> (index * width)) & ((1 << width) - 1) for index in range(length)]
            remaining = count - len(values)
            if any(decoded[remaining:]):
                raise ValueError("Parquet padded values are not zero")
            values.extend(decoded[:remaining])
        else:
            length = header >> 1
            size = (width + 7) // 8
            if length > count - len(values) or position + size > len(data):
                raise ValueError("Parquet RLE run exceeds row bounds")
            value = int.from_bytes(data[position : position + size], "little")
            position += size
            if value >= 1 << width:
                raise ValueError("Parquet RLE value exceeds its bit width")
            values.extend([value] * length)
    if len(values) != count or position != len(data):
        raise ValueError("Parquet RLE count contradicts actual bytes")
    return tuple(values)


def _plain_values(data: memoryview, column: Column, count: int) -> int:
    if column.type is not ColumnType.STRING:
        if len(data) != count * 8:
            raise ValueError("Parquet PLAIN scalar count differs from bytes")
        return 0
    position = payload = 0
    for _ in range(count):
        if position + 4 > len(data):
            raise ValueError("truncated Parquet PLAIN string")
        length = struct.unpack_from("<i", data, position)[0]
        position += 4
        if length < 0 or length > len(data) - position:
            raise ValueError("Parquet PLAIN string exceeds page bytes")
        position += length
        payload += length
    if position != len(data):
        raise ValueError("Parquet PLAIN string count differs from bytes")
    return payload


def _admit_compact_pages(
    data: bytes,
    opened: Any,
    start_footer: int,
    columns: tuple[Column, ...],
    env: FileEnvelope,
    limits: VerificationLimits,
) -> None:
    footer = opened.metadata
    if (
        not 0 <= footer.num_rows <= limits.max_rows
        or not 0 < footer.num_row_groups <= limits.max_rows
    ):
        raise ValueError("compact Parquet exceeds row/group bounds")
    empty_compact = footer.num_rows == 0 and env.tier is Tier.COMPACT
    if footer.num_rows == 0 and not empty_compact:
        raise ValueError("zero-row Parquet is admitted only for compact history")
    group_counts = tuple(
        footer.row_group(group_id).num_rows for group_id in range(footer.num_row_groups)
    )
    if any(not 0 <= count <= limits.max_rows for count in group_counts) or (
        not empty_compact and any(count == 0 for count in group_counts)
    ):
        raise ValueError("compact Parquet row-group cardinality exceeds row bounds")
    if sum(group_counts) != footer.num_rows:
        raise ValueError("compact Parquet row-group cardinality contradicts its footer")
    budget = _Budget(limits.max_decode_bytes)
    intervals: list[tuple[int, int]] = []
    for group_id in range(footer.num_row_groups):
        group = footer.row_group(group_id)
        if group.num_columns != len(columns):
            raise ValueError("compact Parquet row group has an invalid shape")
        group_size = 0
        for index, column in enumerate(columns):
            chunk = group.column(index)
            if (
                chunk.file_path
                or chunk.path_in_schema != column.name
                or chunk.num_values != group.num_rows
            ):
                raise ValueError("compact Parquet chunk contradicts its rows/path")
            if chunk.has_column_index or chunk.has_offset_index:
                raise ValueError("compact Parquet auxiliary indexes are unsupported")
            if chunk.compression != (
                "UNCOMPRESSED" if env.compression.value == "none" else env.compression.value.upper()
            ):
                raise ValueError("compact Parquet compression contradicts its envelope")
            start = (
                chunk.dictionary_page_offset
                if chunk.has_dictionary_page
                else chunk.data_page_offset
            )
            if start is None or start < 4 or chunk.total_compressed_size <= 0:
                raise ValueError("compact Parquet has invalid chunk offsets")
            end = start + chunk.total_compressed_size
            if end > start_footer or any(start < b and a < end for a, b in intervals):
                raise ValueError("compact Parquet chunks overlap or exceed file body")
            intervals.append((start, end))
            position = start
            dictionary_count: int | None = None
            dictionary_payload = count = page_count = total = 0
            budget.charge(group.num_rows * (8 + int(column.nullable)))
            while position < end:
                page_count += 1
                if page_count > group.num_rows + 1:
                    raise ValueError("compact Parquet exceeds bounded page count")
                stream, protocol = _protocol(
                    data,
                    position,
                    end,
                    byte_limit=limits.max_footer_bytes,
                    items=limits.max_thrift_items,
                    depth=limits.max_json_depth,
                )
                header = _PageHeader()
                header.read(protocol)
                size = _size(header.uncompressed_page_size)
                compressed = _size(header.compressed_page_size)
                if compressed > end - stream.position:
                    raise ValueError("compact Parquet page exceeds chunk bytes")
                budget.charge(stream.position - position + size)
                total += stream.position - position + size
                body = memoryview(data)[stream.position : stream.position + compressed]
                if header.crc is not None and zlib.crc32(body) != header.crc & 0xFFFFFFFF:
                    raise ValueError("compact Parquet page CRC contradicts actual bytes")
                if (
                    sum(
                        value is not None
                        for value in (
                            header.data_page_header,
                            header.data_page_header_v2,
                            header.dictionary_page_header,
                            header.index_page_header,
                        )
                    )
                    != 1
                ):
                    raise ValueError("compact Parquet page has conflicting type headers")
                position = stream.position + compressed
                if header.type == 2 and header.dictionary_page_header is not None:
                    dictionary = header.dictionary_page_header
                    if (
                        dictionary_count is not None
                        or count
                        or dictionary.encoding != 0
                        or (
                            dictionary.num_values is None
                            or not 0 <= dictionary.num_values <= group.num_rows
                        )
                    ):
                        raise ValueError("compact Parquet dictionary exceeds row cardinality")
                    dictionary_count = dictionary.num_values
                    dictionary_payload = _plain_values(
                        _decompress(body, size, env.compression.value),
                        column,
                        dictionary_count,
                    )
                    continue
                page = header.data_page_header
                if (
                    header.type != 0
                    or page is None
                    or page.definition_level_encoding != 3
                    or (
                        page.repetition_level_encoding != 3
                        or page.num_values is None
                        or not 0 < page.num_values <= group.num_rows - count
                    )
                ):
                    raise ValueError("compact Parquet requires bounded flat V1 data pages")
                count += page.num_values
                decoded = _decompress(body, size, env.compression.value)
                present = page.num_values
                if column.nullable:
                    if len(decoded) < 4:
                        raise ValueError("truncated compact definition levels")
                    length = int.from_bytes(decoded[:4], "little")
                    if length > len(decoded) - 4:
                        raise ValueError("compact definition levels exceed page bytes")
                    levels = _hybrid(decoded[4 : 4 + length], 1, page.num_values)
                    present = sum(levels)
                    decoded = decoded[4 + length :]
                if page.encoding == 0:
                    budget.charge(_plain_values(decoded, column, present))
                elif page.encoding in (2, 8) and dictionary_count is not None and decoded:
                    indices = _hybrid(decoded[1:], int(decoded[0]), present)
                    if any(value >= dictionary_count for value in indices):
                        raise ValueError("compact dictionary index exceeds cardinality")
                    budget.charge(dictionary_payload * present)
                else:
                    raise ValueError("unsupported compact Parquet value encoding")
            if (
                count != group.num_rows
                or total != chunk.total_uncompressed_size
                or (chunk.has_dictionary_page != (dictionary_count is not None))
            ):
                raise ValueError("compact actual page totals contradict metadata")
            group_size += total
        if group_size != group.total_byte_size:
            raise ValueError("compact actual row-group size contradicts metadata")
    position = 4
    for start, end in sorted(intervals):
        if start != position:
            raise ValueError("compact Parquet contains unaccounted page bytes")
        position = end
    if position != start_footer:
        raise ValueError("compact Parquet contains unaccounted file bytes")


def _compact(
    data: bytes, limits: VerificationLimits
) -> tuple[FileEnvelope, list[dict[str, Any]], Format]:
    if data.startswith(b"PAR1"):
        footer_start = check_parquet_footer(
            data,
            max_footer_bytes=limits.max_footer_bytes,
            max_thrift_items=limits.max_thrift_items,
            max_depth=limits.max_json_depth,
        )
        with parquet.open_bytes(
            data,
            max_footer_bytes=limits.max_footer_bytes,
            max_footer_items=limits.max_thrift_items,
        ) as opened:
            env = FileEnvelope.from_metadata(
                parquet._envelope_of(opened.metadata.metadata)
            ).validate_container(Format.PARQUET)
            columns = host_output_columns(env.row_schema_version)
            if opened.schema_arrow.remove_metadata() != parquet.schema_of(columns):
                raise ValueError("compact Parquet logical schema contradicts row version")
            if opened.metadata.created_by != f"parquet-cpp-arrow version {env.writer_version}":
                raise ValueError("compact Parquet engine provenance contradicts actual bytes")
            _admit_compact_pages(data, opened, footer_start, columns, env, limits)
            rows: list[dict[str, Any]] = []
            decoded_bytes = 0
            for batch in opened.iter_batches(batch_size=1, use_threads=False):
                if len(rows) + batch.num_rows > opened.metadata.num_rows:
                    raise ValueError("compact Parquet decoded rows exceed its footer cardinality")
                decoded_bytes += batch.nbytes
                if decoded_bytes > limits.max_decode_bytes:
                    raise ValueError("compact Parquet decoded cells exceed byte cap")
                rows.extend(batch.to_pylist())
            if len(rows) != opened.metadata.num_rows:
                raise ValueError("compact Parquet decoded rows contradict its footer cardinality")
            return env, rows, Format.PARQUET
    if not data.isascii() or b"\r" in data or not data.endswith(b"\n"):
        raise ValueError("historical JSONL requires ASCII and LF")
    lines = data.splitlines()
    if not 1 < len(lines) <= limits.max_rows + 1 or len(lines[0]) > limits.max_footer_bytes:
        raise ValueError("compact JSONL exceeds row/envelope limits or is empty")
    for line in lines:
        _json(line, limits)
    metadata, rows = json_lines.read(data)
    if json_lines.render(rows, envelope=metadata) != data:
        raise ValueError("compact JSONL is not canonical")
    if len(json_lines.rows_bytes(rows)) > limits.max_decode_bytes:
        raise ValueError("compact JSONL exceeds decode byte cap")
    return FileEnvelope.from_metadata(metadata).validate_container(Format.JSON), rows, Format.JSON


def decode_history(
    source: HistorySource,
    root: HistoryRoot,
    *,
    data: bytes,
    limits: VerificationLimits,
    legacy_raw_evidence: Mapping[tuple[str, str, int], Mapping[str, object]] | None = None,
) -> HistoryFile:
    if len(data) > limits.max_file_bytes:
        raise ValueError("historical source or candidate exceeds max_file_bytes")
    if source.kind == "set_aside":
        expected = Path(root.state_root, "raw", *root.prefix, paths.SET_ASIDE_DIRNAME)
        if not Path(source.path).is_relative_to(expected):
            raise ValueError(f"{source.path}: set-aside source is outside declared host prefix")
        return HistoryFile(source, data, None, (), (), None, None)
    if source.kind == "view" and source.path.endswith(".csv"):
        raise ValueError("retired historical machine CSV view has no current contract")
    if source.kind not in ("raw", "compact"):
        document = _json(data, limits)
        if not isinstance(document, dict) or "version" not in document:
            raise ValueError(f"{source.path}: document requires original version metadata")
        if source.kind == "view":
            if source.path != "frontend/public/console/band.json" or document["version"] not in (
                "2026-09-09",
                "2026-09-12",
                "2026-09-19",
                "2026-09-23",
                "2026-10-02",
                ConsoleBand.schema_version(),
            ):
                raise ValueError("unknown historical console view path/version")
            ConsoleBand.model_validate(document)
        return HistoryFile(source, data, None, (), (), document, None)
    if source.kind == "raw":
        if data.startswith(b"PAR1"):
            env, originals, _ = _read_parquet(data, limits)
            container = Format.PARQUET
        else:
            env, originals = _read_json(data, limits)
            container = Format.JSON
        normalized = _validate_rows(originals, env)
    else:
        env, originals, container = _compact(data, limits)
        normalized = normalize_stored_host_rows(
            originals,
            content_sha256=env.content_sha256,
            historical_envelope=env,
            legacy_raw_evidence=legacy_raw_evidence,
        )
    if env.version not in ENVELOPE_VERSIONS or env.row_schema_version not in (
        *LEGACY_HOST_VERSIONS,
        HOST_OUTPUT_VERSION,
    ):
        raise ValueError(f"{source.path}: unrecognized envelope or row version")
    expected_tier = Tier.RAW if source.kind == "raw" else Tier.COMPACT
    if (
        env.ledger is not LedgerName.HOST_FINGERPRINT
        or env.tier is not expected_tier
        or (
            env.covers != source.covers
            or (env.period if env.tier is Tier.COMPACT else Period.DAILY) != source.period
        )
    ):
        raise ValueError(f"{source.path}: envelope contradicts manifested period/tier")
    if env.writer.startswith("idhazh_rust.") and env.row_schema_version != HOST_OUTPUT_VERSION:
        raise ValueError("native corrected files cannot masquerade as historical conversion inputs")
    env.validate_container(container)
    registry = paths.overlay_registry(root.prefix[:-1])
    state = Path(root.state_root)
    if env.tier is Tier.COMPACT and env.period is None:
        raise ValueError("compact source requires its original period")
    expected = (
        paths.raw_path(
            state,
            LedgerName.HOST_FINGERPRINT,
            env.covers,
            env.file_id,
            fmt=container,
            registry=registry,
        )
        if env.tier is Tier.RAW
        else (
            paths.compact_path(
                state,
                LedgerName.HOST_FINGERPRINT,
                env.period if env.period is not None else Period.DAILY,
                env.covers,
                fmt=container,
                registry=registry,
            )
        )
    )
    if Path(source.path) != expected:
        raise ValueError(f"{source.path}: path contradicts original period/file identity")
    if env.unit_id != unit_id(
        ledger=env.ledger.value,
        covers=env.covers,
        run_id=env.identity.run_id,
        job=env.identity.job.value,
        shard=env.identity.shard,
        producer=env.identity.producer,
    ) or env.file_id != host_file_id(
        unit=env.unit_id,
        attempt=env.identity.attempt,
        written_at_ms=env.written_at_ms,
    ):
        raise ValueError("original envelope UUID5/UUID8 or allocation clock contradicts lineage")
    columns = host_output_columns(env.row_schema_version)
    for row in originals:
        allowed_versions = (
            {env.row_schema_version}
            if env.row_schema_version == HOST_OUTPUT_VERSION
            else {
                version
                for version in LEGACY_HOST_VERSIONS
                if version <= env.row_schema_version
            }
        )
        if set(row) != {c.name for c in columns} or row["version"] not in allowed_versions:
            raise ValueError("unknown/mixed historical row shape or version")
        for column in columns:
            if row[column.name] is None and not column.nullable:
                raise ValueError("historical row contains a null required cell")
        identity = RowIdentity.model_validate({key: row[key] for key in RowIdentity.model_fields})
        if not (identity.covers == env.covers or identity.covers.startswith(env.covers + "-")):
            raise ValueError("compact row is outside its original period")
    return HistoryFile(source, data, env, tuple(originals), normalized, None, container)


def read_history(
    source: HistorySource,
    root: HistoryRoot,
    *,
    workspace: Path,
    limits: VerificationLimits,
    legacy_raw_evidence: Mapping[tuple[str, str, int], Mapping[str, object]] | None = None,
) -> HistoryFile:
    return decode_history(
        source,
        root,
        data=read_source(source, workspace=workspace, limits=limits),
        limits=limits,
        legacy_raw_evidence=legacy_raw_evidence,
    )
