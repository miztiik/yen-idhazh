"""Which original host cells can be read and packed without losing evidence?"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from idhazh.contracts.file_envelope import FileEnvelope, Format, RowIdentity, Tier
from idhazh.contracts.host_fingerprint import (
    HOST_FINGERPRINT_READ_VERSIONS,
    HOST_FINGERPRINT_VERSION,
    HOST_HARDWARE_VERSION,
    LEGACY_CPU_FIELDS,
    LEGACY_HOST_VERSIONS,
    RETIRED_HOST_CLOCK,
    HostFingerprintRow,
    HostHardwareRow,
    LegacyHostFingerprintRow,
    normalize_host_row,
    project_retained_host_cells,
    strip_null_legacy_placeholders,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import arrow_schema, filenames, json_lines
from idhazh.ledger.arrow_schema import Column, ColumnType

_STAMPS: Final = frozenset(
    (*LEGACY_HOST_VERSIONS, *HOST_FINGERPRINT_READ_VERSIONS, HOST_HARDWARE_VERSION)
)
_WRITER_CELLS: Final = RowIdentity.model_fields.keys() - HostFingerprintRow.model_fields.keys()
_IDENTITY_CELLS: Final = frozenset(RowIdentity.model_fields)
_LEGACY_PAYLOAD: Final = frozenset(LegacyHostFingerprintRow.model_fields)
_HISTORICAL_PAYLOAD: Final = frozenset(HostFingerprintRow.model_fields)
_HARDWARE_PAYLOAD: Final = frozenset(HostHardwareRow.model_fields)
_MODEL_CELLS: Final = _HISTORICAL_PAYLOAD - _HARDWARE_PAYLOAD
KNOWN_CELLS: Final = _IDENTITY_CELLS | _LEGACY_PAYLOAD | _HISTORICAL_PAYLOAD | {RETIRED_HOST_CLOCK}


class HostStorageError(ValueError):
    """This host file cannot be replaced with a verified, lossless copy."""


@dataclass(frozen=True, slots=True)
class HostLayout:
    """The physical columns needed by all original rows in one packed file."""

    historical: bool = False
    legacy_cpu: bool = False
    retired_clock: bool = False

    @property
    def stamp(self) -> str:
        return HOST_FINGERPRINT_VERSION if self.historical else HOST_HARDWARE_VERSION

    def __or__(self, other: HostLayout) -> HostLayout:
        return HostLayout(
            historical=self.historical or other.historical,
            legacy_cpu=self.legacy_cpu or other.legacy_cpu,
            retired_clock=self.retired_clock or other.retired_clock,
        )

    def project(self, cells: Mapping[str, Any]) -> dict[str, Any]:
        """Pad a declared compatibility layout, but never drop an original cell."""
        names = _columns_by_name(self)
        if cells.keys() - names.keys():
            raise HostStorageError("host packing would drop original cells")
        return {name: cells.get(name) for name in names}


@cache
def _columns_by_name(layout: HostLayout) -> dict[str, Column]:
    model = HostFingerprintRow if layout.historical else HostHardwareRow
    result = {column.name: column for column in arrow_schema.columns_of(model)}
    if layout.legacy_cpu:
        result.update(
            (column.name, column)
            for column in arrow_schema.columns_of(LegacyHostFingerprintRow)
            if column.name in LEGACY_CPU_FIELDS
        )
    if layout.retired_clock:
        result[RETIRED_HOST_CLOCK] = Column(RETIRED_HOST_CLOCK, ColumnType.INT64, nullable=True)
    result.update(
        (column.name, column)
        for column in arrow_schema.columns_of(RowIdentity)
        if column.name not in result
    )
    return result


def columns_for(layout: HostLayout) -> tuple[Column, ...]:
    return tuple(_columns_by_name(layout).values())


def layout_for_footer(envelope: FileEnvelope, names: Iterable[str]) -> HostLayout:
    """Select a physical profile; only a compact file may mix row generations."""
    columns = set(names)
    legacy_cpu = bool(columns & LEGACY_CPU_FIELDS)
    if envelope.row_schema_version in (HOST_HARDWARE_VERSION, HOST_FINGERPRINT_VERSION):
        if envelope.tier is Tier.RAW and envelope.row_schema_version == HOST_HARDWARE_VERSION:
            return HostLayout()
        return HostLayout(
            historical=legacy_cpu or bool(columns & _MODEL_CELLS),
            legacy_cpu=legacy_cpu,
            retired_clock=(
                envelope.row_schema_version == HOST_HARDWARE_VERSION
                and RETIRED_HOST_CLOCK in columns
            ),
        )
    return HostLayout(
        historical=True, legacy_cpu=legacy_cpu, retired_clock=RETIRED_HOST_CLOCK in columns,
    )


def layout_for_rows(rows: Iterable[Mapping[str, Any]]) -> HostLayout:
    result = HostLayout()
    for cells in rows:
        version = cells.get("version")
        if not isinstance(version, str) or version not in _STAMPS:
            raise HostStorageError("unrecognized original host row stamp")
        result |= HostLayout(
            historical=version != HOST_HARDWARE_VERSION,
            legacy_cpu=version in LEGACY_HOST_VERSIONS,
        )
    return result


def _check_shape(
    envelope: FileEnvelope,
    layout: HostLayout,
    schema: Any | None,
    *,
    name: str,
) -> None:
    if (
        envelope.ledger is not LedgerName.HOST_FINGERPRINT
        or envelope.row_schema_version not in _STAMPS
    ):
        raise HostStorageError(f"{name} has an undeclared host file stamp or ledger")
    if schema is None:
        return
    from idhazh.ledger import parquet

    stamp = envelope.row_schema_version
    if stamp in (HOST_HARDWARE_VERSION, HOST_FINGERPRINT_VERSION):
        expected = parquet.schema_of(columns_for(layout))
        if set(schema.names) != set(expected.names):
            raise HostStorageError(f"{name} has an unexpected physical host column set")
    else:
        expected = parquet.schema_of(columns_for(HostLayout(
            historical=True, legacy_cpu=True, retired_clock=True,
        )))
    if len(set(schema.names)) != len(schema.names) or any(
        field.name not in expected.names or not expected.field(field.name).type.equals(field.type)
        for field in schema
    ):
        raise HostStorageError(f"{name} has unknown or incompatible physical host columns")


def _payload(
    cells: Mapping[str, Any], envelope: FileEnvelope, layout: HostLayout, *, name: str
) -> dict[str, Any]:
    version = cells["version"]
    allowed = (
        _HARDWARE_PAYLOAD if version == HOST_HARDWARE_VERSION else
        _LEGACY_PAYLOAD if version in LEGACY_HOST_VERSIONS else _HISTORICAL_PAYLOAD
    )
    payload = {key: value for key, value in cells.items() if key not in _WRITER_CELLS}
    if RETIRED_HOST_CLOCK in payload:
        if envelope.row_schema_version == HOST_FINGERPRINT_VERSION or (
            version == HOST_HARDWARE_VERSION and envelope.tier is Tier.RAW
        ):
            raise HostStorageError(f"{name} carries a retired column in a current host shape")
        payload = project_retained_host_cells(payload)
    if version in LEGACY_HOST_VERSIONS:
        # Historical compact files could already pad the early clock columns.
        payload = strip_null_legacy_placeholders(payload)
    for key in payload.keys() - allowed:
        known_padding = (
            (key in _IDENTITY_CELLS and version in LEGACY_HOST_VERSIONS)
            or (envelope.tier is Tier.COMPACT and layout.historical and key in KNOWN_CELLS)
        )
        if not known_padding or payload[key] is not None:
            raise HostStorageError(f"{name} carries cells not declared by its host row stamp")
        del payload[key]
    return payload


def _check_raw_identity(
    envelope: FileEnvelope, identity: RowIdentity, *, name: str
) -> None:
    writer = envelope.identity
    unit = filenames.unit_id(
        ledger=envelope.ledger, covers=identity.covers, run_id=identity.run_id,
        job=str(identity.job) if identity.pipeline_name is None else None,
        pipeline_name=identity.pipeline_name, task_name=identity.task_name,
        shard=identity.shard, producer=writer.producer,
    )
    if identity.unit_id != str(unit):
        raise HostStorageError(f"{name} original host row unit identity mismatch")
    if envelope.row_schema_version == HOST_HARDWARE_VERSION and (
        identity.run_id != writer.run_id
        or identity.attempt != writer.attempt
        or identity.job != writer.job
        or identity.pipeline_name != writer.pipeline_name
        or identity.task_name != writer.task_name
        or identity.shard != writer.shard
        or unit != envelope.unit_id
        or filenames.file_id(
            unit=unit, attempt=writer.attempt, written_at_ms=envelope.written_at_ms
        ) != envelope.file_id
    ):
        raise HostStorageError(f"{name} hardware capture does not match its original writer")


def read_rows(
    envelope: FileEnvelope,
    stored: Sequence[dict[str, Any]],
    schema: Any | None,
    *,
    name: str,
    hardware_only: bool = False,
) -> Iterable[tuple[RowIdentity, HostFingerprintRow | HostHardwareRow, Mapping[str, Any]]]:
    """Verify the writer's digest and shape before offering any normalized reading."""
    if hashlib.sha256(json_lines.rows_bytes(stored)).hexdigest() != envelope.content_sha256:
        raise HostStorageError(f"{name} original host content_sha256 mismatch")
    layout = layout_for_rows(stored)
    if (
        schema is not None and layout.historical
        and envelope.row_schema_version != HOST_FINGERPRINT_VERSION
    ):
        layout = replace(layout, retired_clock=RETIRED_HOST_CLOCK in schema.names)
    _check_shape(envelope, layout, schema, name=name)
    for cells in stored:
        version = cells["version"]
        if version > envelope.row_schema_version or (
            envelope.tier is Tier.RAW
            and ((version == HOST_HARDWARE_VERSION) !=
                 (envelope.row_schema_version == HOST_HARDWARE_VERSION))
        ):
            raise HostStorageError(f"{name} host row stamp disagrees with its file")
        if cells.keys() - KNOWN_CELLS:
            raise HostStorageError(f"{name} carries unknown original host cells")
        if version == HOST_HARDWARE_VERSION and envelope.tier is Tier.RAW and (
            cells.keys() != _HARDWARE_PAYLOAD | _IDENTITY_CELLS
        ):
            raise HostStorageError(f"{name} has an unexpected raw hardware row shape")
        identity = RowIdentity.model_validate(
            {key: cells.get(key) for key in RowIdentity.model_fields}
        )
        if (
            identity.ledger is not envelope.ledger
            or identity.covers != cells.get("date")
            or not (
                identity.covers == envelope.covers
                or identity.covers.startswith(f"{envelope.covers}-")
            )
        ):
            raise HostStorageError(f"{name} original host row identity mismatch")
        if envelope.tier is Tier.RAW and (
            version == HOST_HARDWARE_VERSION or envelope.writer.startswith("idhazh_rust.")
        ):
            _check_raw_identity(envelope, identity, name=name)
        payload = _payload(cells, envelope, layout, name=name)
        row = (
            HostHardwareRow.model_validate(payload)
            if hardware_only else normalize_host_row(payload)
        )
        original = MappingProxyType(
            {key: value for key, value in cells.items() if key in payload or key in _WRITER_CELLS}
        )
        yield identity, row, original


def packed_source_layout(path: Path) -> HostLayout:
    """Choose an annual layout from one named packed month's footer, without reading its rows."""
    from idhazh.ledger import parquet

    with path.open("rb") as handle:
        head = handle.read(len(json_lines.MAGIC))
    if head == json_lines.MAGIC:
        metadata, rows = json_lines.read(path.read_bytes())
        envelope = FileEnvelope.from_metadata(metadata).validate_container(Format.JSON)
        layout = layout_for_rows(rows)
        _check_shape(envelope, layout, None, name=path.name)
        return layout
    metadata, schema, count = parquet.read_footer_layout(path)
    envelope = FileEnvelope.from_metadata(metadata).validate_container(Format.PARQUET)
    layout = layout_for_footer(envelope, schema.names) if count else HostLayout()
    _check_shape(envelope, layout, schema, name=path.name)
    return replace(layout, retired_clock=False)


def verify_packed(
    data: bytes, fmt: Format, layout: HostLayout, *, count: int, content_sha256: str
) -> None:
    """Read the rendered shape and digest back before any source may be removed."""
    digest = hashlib.sha256()
    counted = 0
    if fmt is Format.JSON:
        metadata, rows = json_lines.read(data)
        envelope = FileEnvelope.from_metadata(metadata).validate_container(fmt)
        _check_shape(envelope, layout, None, name="packed host file")
        digest.update(json_lines.rows_bytes(rows))
        counted = len(rows)
    else:
        from idhazh.ledger import parquet

        with parquet.open_bytes(data) as opened:
            envelope = FileEnvelope.from_metadata(
                parquet.envelope_metadata(opened.metadata.metadata)
            ).validate_container(fmt)
            _check_shape(envelope, layout, opened.schema_arrow, name="packed host file")
            if set(opened.schema_arrow.names) != _columns_by_name(layout).keys():
                raise HostStorageError("packed host file does not preserve its physical columns")
            for index in range(opened.num_row_groups):
                rows = opened.read_row_group(index, use_threads=False).to_pylist()
                digest.update(json_lines.rows_bytes(rows))
                counted += len(rows)
    if (
        counted != count or digest.hexdigest() != content_sha256
        or envelope.content_sha256 != content_sha256 or envelope.row_schema_version != layout.stamp
    ):
        raise HostStorageError("packed host file does not preserve its original cells")
