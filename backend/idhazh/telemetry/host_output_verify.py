"""Do the exact named host files satisfy their plan and completed-write evidence?"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from idhazh.contracts.file_envelope import Format, RowIdentity, Tier
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HOST_PRODUCER,
    INT64_MAX,
    INT64_MIN,
    LEGACY_HOST_VERSIONS,
    CandidateFileEnvelope,
    HostStoredRow,
    HostWriteCompletion,
    HostWritePlan,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    host_file_id,
    host_unit_id,
    normalize_stored_host_rows,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import json_lines
from idhazh.ledger.arrow_schema import Column, ColumnType, columns_of
from idhazh.telemetry.host_parquet_admission import admit_host_parquet, check_parquet_footer


@dataclass(frozen=True)
class VerificationLimits:
    """Caller-owned bounds; the owner supplies experiment configuration defaults."""

    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    max_rows: int
    max_footer_bytes: int
    max_decode_bytes: int
    max_thrift_items: int
    max_json_depth: int

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= INT64_MAX:
                raise ValueError(f"{field.name} must be a positive int64")


@dataclass(frozen=True)
class VerifiedHostFile:
    """An in-memory reading, not publication permission or collector evidence."""

    relative_path: str
    format: Format
    envelope: CandidateFileEnvelope
    rows: tuple[HostStoredRow, ...]
    physical_sha256: str
    size_bytes: int
    created_by: str | None


@dataclass(frozen=True)
class HostOutputVerification:
    files: tuple[VerifiedHostFile, ...]
    planned_files: int
    complete: bool


def _safe_path(root: Path, path: Path) -> Path:
    root = root.absolute()
    path = path.absolute()
    if ".." in path.parts or not path.is_relative_to(root):
        raise ValueError("host evidence path is outside the allowed root")
    # Inspect ancestors too: resolving a link would hide the boundary violation.
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("host evidence path contains a symlink or reparse point")
    if path.resolve(strict=True) != path:
        raise ValueError("host evidence path is not canonical")
    return path


def _read_bytes(path: Path, *, root: Path, cap: int) -> bytes:
    safe = _safe_path(root, path)
    before = safe.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("host evidence must be a regular file")
    if before.st_size > cap:
        raise ValueError("host evidence exceeds the file byte limit")
    with safe.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ):
            raise ValueError("host evidence changed before it was opened")
        data = source.read(before.st_size + 1)
    after = _safe_path(root, safe).stat()
    if len(data) > cap:
        raise ValueError("host evidence exceeds the file byte limit")
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or len(data) != before.st_size:
        raise ValueError("host evidence changed while it was read")
    return data


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON evidence contains duplicate keys")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError(f"JSON evidence contains a nonfinite number: {value}")


def _json(data: bytes, limits: VerificationLimits) -> Any:
    depth = 0
    quoted = escaped = False
    for byte in data:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > limits.max_json_depth:
                raise ValueError("JSON evidence exceeds the nesting limit")
        elif byte in (93, 125):
            depth -= 1
    try:
        return json.loads(data, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
    except (RecursionError, OverflowError) as exc:
        raise ValueError("JSON evidence exceeds decoder bounds") from exc


def load_verification_document(
    path: Path, *, root: Path, limits: VerificationLimits
) -> dict[str, Any]:
    """Read one named plan/completion document with bounds before model construction."""
    data = _read_bytes(path, root=root, cap=limits.max_file_bytes)
    document = _json(data, limits)
    if not isinstance(document, dict):
        raise ValueError("verification document must be an object")
    files = document.get("files", [])
    receipt = document.get("receipt", {})
    if not isinstance(files, list) or not isinstance(receipt, dict):
        raise ValueError("verification document has invalid files or receipt")
    writes = receipt.get("writes", {})
    if not isinstance(writes, dict):
        raise ValueError("verification document writes must be an object")
    if len(files) > limits.max_files or len(writes) > limits.max_files:
        raise ValueError("verification document exceeds the file count limit")
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get("rows"), list):
            raise ValueError("planned file must contain a row list")
        if len(file["rows"]) > limits.max_rows:
            raise ValueError("verification document exceeds the row limit")
    return document


def host_output_columns(version: str) -> tuple[Column, ...]:
    """The finite stored schemas in contract order, before legacy normalization."""
    if version == HOST_OUTPUT_VERSION:
        return columns_of(HostStoredRow)
    if version not in LEGACY_HOST_VERSIONS:
        raise ValueError("unrecognized stored host schema version")
    omitted: set[str] = set()
    if version < "2026-09-18":
        omitted.update(("model_load_ms", "job_seconds"))
    if version < "2026-09-19":
        omitted.update(("server_prompt_tokens", "server_prompt_seconds"))
    row = tuple(
        Column(c.name, c.type, False)
        if version < "2026-09-18" and c.name in ("fingerprint", "measured_at")
        else c
        for c in columns_of(LegacyHostFingerprintRow)
        if c.name not in omitted
    )
    names = {c.name for c in row}
    return (*row, *(c for c in columns_of(RowIdentity) if c.name not in names))


def _envelope(metadata: Mapping[bytes, bytes], container: Format) -> CandidateFileEnvelope:
    env = CandidateFileEnvelope.from_metadata(metadata).validate_container(container)
    if env.ledger is not LedgerName.HOST_FINGERPRINT or env.tier is not Tier.RAW:
        raise ValueError("host verifier accepts only host-fingerprint raw files")
    host_output_columns(env.row_schema_version)
    if env.identity.producer != HOST_PRODUCER:
        raise ValueError("host envelope names a foreign logical producer")
    unit = host_unit_id(covers=env.covers, identity=env.identity)
    if env.unit_id != unit or env.file_id != host_file_id(
        unit=unit, attempt=env.identity.attempt, written_at_ms=env.written_at_ms
    ):
        raise ValueError("host envelope contradicts UUID5/UUID8 identity or write clock")
    if metadata[b"unit_id"] != str(env.unit_id).encode() or (
        metadata[b"file_id"] != str(env.file_id).encode()
    ):
        raise ValueError("host envelope UUIDs must use canonical lowercase spelling")
    return env


def _read_json(
    data: bytes, limits: VerificationLimits
) -> tuple[CandidateFileEnvelope, list[dict[str, Any]]]:
    if not data.isascii() or b"\r" in data or not data.endswith(b"\n"):
        raise ValueError("JSONL host output must be ASCII with LF-terminated lines")
    if data.count(b"\n") != 2:
        raise ValueError("a raw host JSONL file must contain exactly one whole row")
    head, _, body = data.partition(b"\n")
    if len(head) > limits.max_footer_bytes or len(body) > limits.max_decode_bytes:
        raise ValueError("JSONL host output exceeds envelope or decode byte limits")
    metadata = _json(head, limits)
    if not isinstance(metadata, dict) or not all(
        isinstance(value, str) for value in metadata.values()
    ):
        raise ValueError("JSONL envelope must contain only string values")
    env = _envelope({k.encode(): v.encode() for k, v in metadata.items()}, Format.JSON)
    for line in body.splitlines():
        row = _json(line, limits)
        if not isinstance(row, dict) or json_lines.rows_bytes((row,)) != line + b"\n":
            raise ValueError("JSONL row is not canonical stored-row bytes")
    # The unchanged container adapter reads exactly the bytes bounded above.
    _, rows = json_lines.read(data)
    return env, rows


def _read_parquet(
    data: bytes, limits: VerificationLimits
) -> tuple[CandidateFileEnvelope, list[dict[str, Any]], str]:
    from idhazh.ledger import parquet

    footer_start = check_parquet_footer(
        data,
        max_footer_bytes=limits.max_footer_bytes,
        max_thrift_items=limits.max_thrift_items,
        max_depth=limits.max_json_depth,
    )
    # Reach the existing engine through its container adapter. Its ordinary
    # whole-file read has no Thrift limits, so inspect a bounded footer first.
    engine = parquet.pyarrow  # type: ignore[attr-defined]  # Existing adapter's engine import.
    with (
        engine.BufferReader(data) as source,
        engine.parquet.ParquetFile(
            source,
            thrift_string_size_limit=limits.max_footer_bytes,
            thrift_container_size_limit=limits.max_thrift_items,
        ) as opened,
    ):
        footer = opened.metadata
        if footer.num_rows != 1 or footer.num_row_groups != 1:
            raise ValueError("a raw host Parquet file must contain exactly one row and row group")
        metadata = dict(footer.metadata or {})
        schema_metadata = dict(opened.schema_arrow.metadata or {})
        if any(metadata.get(key) != value for key, value in schema_metadata.items()):
            raise ValueError("Parquet schema and footer metadata conflict")
        env = _envelope(
            {key: value for key, value in metadata.items() if key != b"ARROW:schema"},
            Format.PARQUET,
        )
        expected = parquet.schema_of(host_output_columns(env.row_schema_version))
        if not opened.schema_arrow.equals(expected, check_metadata=False):
            raise ValueError("Parquet column types, order or nullability contradict the schema")
        created_by = str(footer.created_by or "")
        engine_name = (
            "parquet-rs" if env.writer == "idhazh_rust.ledger.parquet" else "parquet-cpp-arrow"
        )
        if created_by != f"{engine_name} version {env.writer_version}":
            raise ValueError("Parquet created_by contradicts writer and engine version")
        admit_host_parquet(
            data,
            footer_start=footer_start,
            opened=opened,
            columns=host_output_columns(env.row_schema_version),
            compression=env.compression.value,
            max_decode_bytes=limits.max_decode_bytes,
            max_header_bytes=limits.max_footer_bytes,
            max_thrift_items=limits.max_thrift_items,
            max_depth=limits.max_json_depth,
            engine=engine,
        )
        rows: list[dict[str, Any]] = []
        batch_bytes = 0
        for batch in opened.iter_batches(batch_size=1, use_threads=False):
            batch_bytes += batch.nbytes
            if batch_bytes > limits.max_decode_bytes:
                raise ValueError("Parquet batches exceed the decode byte limit")
            rows.extend(batch.to_pylist())
        if len(rows) != footer.num_rows:
            raise ValueError("Parquet row count contradicts its footer")
        return env, rows, created_by


def _validate_rows(
    rows: list[dict[str, Any]], env: CandidateFileEnvelope
) -> tuple[HostStoredRow, ...]:
    # Hash the original dictionaries, not coerced/normalized model dumps.
    normalized = normalize_stored_host_rows(rows, content_sha256=env.content_sha256)
    if env.writer.startswith("idhazh_rust.") and any(
        row.fingerprint_version not in (None, 2) for row in normalized
    ):
        raise ValueError("native host output requires a null fingerprint or sourced algorithm 2")
    if len(rows) != 1:
        raise ValueError("a raw host work unit must contain exactly one whole row")
    columns = host_output_columns(env.row_schema_version)
    expected = {c.name for c in columns}
    for row in rows:
        if set(row) != expected or row.get("version") != env.row_schema_version:
            raise ValueError("stored host fields or versions contradict the envelope schema")
        for column in columns:
            value = row[column.name]
            if value is None:
                if not column.nullable:
                    raise ValueError("stored host row has a null required cell")
            elif column.type is ColumnType.STRING:
                if type(value) is not str:
                    raise ValueError("stored host row has a non-string cell")
            elif column.type is ColumnType.INT64:
                if type(value) is not int or not INT64_MIN <= value <= INT64_MAX:
                    raise ValueError("stored host row has a non-int64 cell")
            elif column.type is ColumnType.FLOAT64:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("stored host row has a nonfinite or coerced float cell")
        for key in ("measured_at", "cpu_target_measured_at"):
            if row.get(key) is not None:
                datetime.strptime(row[key], "%Y-%m-%dT%H:%M:%SZ")
        if (
            row["covers"] != env.covers
            or row["run_id"] != env.identity.run_id
            or row["job"] != env.identity.job.value
            or row["shard"] != env.identity.shard
            or row["attempt"] != env.identity.attempt
            or row["unit_id"] != str(env.unit_id)
        ):
            raise ValueError("stored host row belongs to another envelope identity")
    return normalized


def read_host_output(
    path: Path,
    *,
    root: Path,
    limits: VerificationLimits,
    prefix: tuple[str, ...] = ("host-fingerprint",),
    physical_sha256: str | None = None,
) -> VerifiedHostFile:
    """Read one exact corrected/legacy raw file; never scan, refile or re-encode it."""
    data = _read_bytes(path, root=root, cap=limits.max_file_bytes)
    physical = hashlib.sha256(data).hexdigest()
    if physical_sha256 is not None and physical != physical_sha256:
        raise ValueError("host physical-byte SHA256 contradicts completed-write evidence")
    try:
        if data.startswith(b"PAR1"):
            env, rows, created_by = _read_parquet(data, limits)
            container = Format.PARQUET
        elif data.startswith(json_lines.MAGIC):
            env, rows = _read_json(data, limits)
            created_by = None
            container = Format.JSON
        else:
            raise ValueError("unsupported host output container")
        normalized = _validate_rows(rows, env)
    except (OverflowError, RecursionError, KeyError) as exc:
        raise ValueError("host output contains invalid or overflowing evidence") from exc
    suffix = ".parquet" if container is Format.PARQUET else ".json"
    relative = path.absolute().relative_to(root.absolute())
    expected = Path("raw", *prefix, *env.covers.split("-"), f"{env.file_id}{suffix}")
    if relative != expected:
        raise ValueError("host path contradicts its raw prefix, UTC day or UUID8 filename")
    return VerifiedHostFile(
        relative.as_posix(), container, env, normalized, physical, len(data), created_by
    )


def verify_host_output(
    plan: HostWritePlan,
    completion: HostWriteCompletion,
    *,
    workspace_root: Path,
    target_root: str,
    publication_identity: HostWriterIdentity,
    limits: VerificationLimits,
    require_all: bool = True,
    previous_plan: HostWritePlan | None = None,
) -> HostOutputVerification:
    """Verify named evidence against independently supplied invocation and root expectations."""
    if len(plan.files) > limits.max_files or len(completion.receipt.writes) > limits.max_files:
        raise ValueError("host evidence exceeds the file count limit")
    if any(len(file.rows) > limits.max_rows for file in plan.files):
        raise ValueError("host plan exceeds the row limit")
    plan = HostWritePlan.model_validate(plan.model_dump(mode="json"))
    completion = HostWriteCompletion.model_validate(completion.model_dump(mode="json"))
    if plan.target_root != target_root or plan.publication_identity != publication_identity:
        raise ValueError("host plan belongs to a foreign root or publication invocation")
    completion.validate_plan(plan, require_all=require_all)
    if previous_plan is not None:
        previous_plan = HostWritePlan.model_validate(previous_plan.model_dump(mode="json"))
        plan.validate_successor(previous_plan)
    root = _safe_path(workspace_root, workspace_root / Path(*target_root.split("/")))
    for file in plan.files:
        relative = f"{target_root}/{file.relative_path}"
        if relative not in completion.receipt.writes:
            try:
                _safe_path(root, root / Path(*file.relative_path.split("/")))
            except FileNotFoundError:
                continue
            raise ValueError("completed planned file is missing from receipt evidence")
    selected = [
        file
        for file in plan.files
        if f"{target_root}/{file.relative_path}" in completion.receipt.writes
    ]
    paths = [root / Path(*file.relative_path.split("/")) for file in selected]
    # Preflight the entire finite list before opening any container.
    sizes = [_safe_path(root, path).stat().st_size for path in paths]
    if any(size > limits.max_file_bytes for size in sizes):
        raise ValueError("host evidence exceeds the file byte limit")
    if sum(sizes) > limits.max_total_bytes:
        raise ValueError("host evidence exceeds the total byte limit")
    result: list[VerifiedHostFile] = []
    for file, path in zip(selected, paths, strict=True):
        verified = read_host_output(
            path,
            root=root,
            prefix=plan.prefix,
            limits=limits,
            physical_sha256=completion.receipt.writes[f"{target_root}/{file.relative_path}"],
        )
        if (
            verified.format != file.format
            or verified.envelope != file.envelope
            or verified.rows != file.rows
        ):
            raise ValueError("stored host file contradicts its immutable write plan")
        result.append(verified)
    if sum(file.size_bytes for file in result) > limits.max_total_bytes:
        raise ValueError("host evidence exceeds the total byte limit")
    return HostOutputVerification(tuple(result), len(plan.files), len(result) == len(plan.files))
