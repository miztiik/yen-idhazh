"""Isolated corrected host output, legacy input and immutable write evidence.

These candidates do not change public collectors, contracts or ledger readers.
Container readers must check original stored-row digests before normalization.
Plans describe expected output; neither a plan nor a receipt grants publication
permission, proves a measurement source, or proves a physical file exists.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Literal, Self

from pydantic import ConfigDict, Field, StringConstraints, field_serializer, model_validator

from idhazh.contracts.base import (
    WORK_JOB,
    ChangelogEntry,
    Contract,
    DateStamp,
    FingerprintId,
    Model,
    RelPath,
    RunId,
    ServerJob,
    Sha256,
    Timestamp,
)
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    RowIdentity,
    Tier,
    WriterIdentity,
)
from idhazh.contracts.host_fingerprint import WATCHED_FLAGS
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt

HOST_OUTPUT_VERSION: Final = "2026-10-10"
HOST_PRODUCER: Final = "telemetry.silicon"
INT64_MAX: Final = (1 << 63) - 1
INT64_MIN: Final = -(1 << 63)
HOST_NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")
LEGACY_HOST_VERSIONS: Final = (
    "2026-09-16",
    "2026-09-17",
    "2026-09-18",
    "2026-09-19",
    "2026-09-20",
)
_LEGACY_CPU_FIELDS: Final = frozenset({"cores", "threads", "mhz_max", "mhz_at_probe"})
_CLOCK_FIELDS: Final = frozenset(
    {
        "model_load_ms",
        "job_seconds",
        "server_prompt_tokens",
        "server_prompt_seconds",
    }
)
_TARGET_FIELDS: Final = frozenset(
    {"cpu_allowed_processors", "cpu_quota_cores", "cpu_quota_state", "cpu_target_measured_at"}
)
_FINGERPRINT_V2_KEYS: Final = (
    "cpu_vendor",
    "cpu_family",
    "cpu_model_number",
    "cpu_stepping",
    "cpu_model",
    "l3_cache_bytes",
    "flags",
)
_FINGERPRINT_V1_KEYS: Final = (*_FINGERPRINT_V2_KEYS, "cores", "threads")
_OUTPUT_CHANGELOG: Final = (
    ChangelogEntry(
        version=HOST_OUTPUT_VERSION,
        change="Declare corrected host CPU readings and versioned fingerprints.",
        why="Isolated output distinguishes measured constraints from legacy estimates.",
    ),
)


class CorrectedHostFingerprintRow(Contract):
    """AN's corrected row. Unchanged fields retain baseline types and defaults."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    __schema_stem__: ClassVar[str] = "host-output-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _OUTPUT_CHANGELOG

    version: Literal["2026-10-10"]
    date: DateStamp
    run_id: RunId
    job: ServerJob = WORK_JOB
    shard: int = Field(ge=0, le=INT64_MAX, strict=True)
    fingerprint: FingerprintId | None = None
    fingerprint_version: Literal[1, 2] | None = None
    cpu_model: str | None = None
    cpu_vendor: str | None = None
    cpu_family: int | None = None
    cpu_model_number: int | None = None
    cpu_stepping: int | None = None
    microcode: str | None = None
    cpu_physical_cores: int | None = Field(default=None, ge=1, le=INT64_MAX, strict=True)
    cpu_logical_processors: int | None = Field(default=None, ge=1, le=INT64_MAX, strict=True)
    cpu_allowed_processors: int | None = Field(default=None, ge=1, le=INT64_MAX, strict=True)
    cpu_quota_cores: float | None = Field(default=None, gt=0, strict=True)
    cpu_quota_state: Literal["finite", "unlimited", "unavailable"] | None = None
    cpu_target_measured_at: Timestamp | None = Field(
        default=None, description="UTC instant of the frozen target constraint capture."
    )
    l3_cache_bytes: int | None = Field(default=None, ge=0)
    cpu_observed_mhz: float | None = Field(default=None, gt=0, strict=True)
    cpu_reported_max_mhz: float | None = Field(default=None, gt=0, strict=True)
    flags: str = ""
    boot_seconds: float | None = Field(default=None, ge=0)
    memcpy_gib_s: float | None = Field(default=None, gt=0)
    memcpy_probe_mib: int | None = Field(default=None, ge=0)
    vm_size: str | None = None
    vm_location: str | None = None
    vm_zone: str | None = None
    vm_fault_domain: str | None = None
    runner_name: str | None = None
    measured_at: Timestamp | None = Field(default=None, description="UTC machine probe instant.")
    model_load_ms: float | None = Field(default=None, ge=0)
    job_seconds: int | None = Field(default=None, ge=0)
    server_prompt_tokens: int | None = Field(default=None, ge=0)
    server_prompt_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _strict_numbers(cls, data: Any) -> Any:
        return _check_numbers(data, cls)

    @model_validator(mode="after")
    def _consistent_measurements(self) -> Self:
        if (self.fingerprint is None) != (self.fingerprint_version is None):
            raise ValueError("fingerprint and fingerprint_version must be present together")
        if self.fingerprint_version == 2 and self.fingerprint != fingerprint_v2(self):
            raise ValueError("fingerprint does not match algorithm 2 hardware facts")
        if (self.cpu_quota_cores is not None) != (self.cpu_quota_state == "finite"):
            raise ValueError("cpu_quota_state is finite iff cpu_quota_cores is present")
        has_target = self.cpu_target_measured_at is not None
        if has_target != (self.cpu_quota_state is not None):
            raise ValueError("target capture time and quota state must be present together")
        if self.cpu_allowed_processors is not None:
            if not has_target or self.cpu_logical_processors is None:
                raise ValueError("allowed processors require a target capture and logical count")
        logical = self.cpu_logical_processors
        if logical is not None:
            for name in ("cpu_physical_cores", "cpu_allowed_processors"):
                count = getattr(self, name)
                if count is not None and count > logical:
                    raise ValueError(f"{name} cannot exceed cpu_logical_processors")
        if self.cpu_target_measured_at is not None and self.measured_at is not None:
            if self.cpu_target_measured_at < self.measured_at:
                raise ValueError("target capture cannot precede the original machine probe")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        return {
            key: "" if value is None else str(value)
            for key, value in self.model_dump(mode="json").items()
        }


class LegacyHostFingerprintRow(Contract):
    """The finite pre-correction schemas, validated before their fields are removed."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    __schema_stem__: ClassVar[str] = "legacy-host-output-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-20",
            change="Recognize finite historical host inputs.",
            why="Discarded CPU estimates must still pass their original field validation.",
        ),
    )

    version: Literal["2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"]
    date: DateStamp
    run_id: RunId
    job: ServerJob = WORK_JOB
    shard: int = Field(ge=0, le=INT64_MAX, strict=True)
    fingerprint: FingerprintId | None = None
    cpu_model: str | None = None
    cpu_vendor: str | None = None
    cpu_family: int | None = None
    cpu_model_number: int | None = None
    cpu_stepping: int | None = None
    microcode: str | None = None
    cores: int | None = Field(default=None, ge=1)
    threads: int | None = Field(default=None, ge=1)
    l3_cache_bytes: int | None = Field(default=None, ge=0)
    mhz_max: float | None = Field(default=None, gt=0)
    mhz_at_probe: float | None = Field(default=None, gt=0)
    flags: str = ""
    boot_seconds: float | None = Field(default=None, ge=0)
    memcpy_gib_s: float | None = Field(default=None, gt=0)
    memcpy_probe_mib: int | None = Field(default=None, ge=0)
    vm_size: str | None = None
    vm_location: str | None = None
    vm_zone: str | None = None
    vm_fault_domain: str | None = None
    runner_name: str | None = None
    measured_at: Timestamp | None = None
    model_load_ms: float | None = Field(default=None, ge=0)
    job_seconds: int | None = Field(default=None, ge=0)
    server_prompt_tokens: int | None = Field(default=None, ge=0)
    server_prompt_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _declared_input(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or data.get("version") not in LEGACY_HOST_VERSIONS:
            raise ValueError("legacy input requires a declared historical schema version")
        version = data["version"]
        forbidden: set[str] = set()
        if version < "2026-09-18":
            forbidden.update(_CLOCK_FIELDS)
            if data.get("fingerprint") is None or data.get("measured_at") is None:
                raise ValueError("pre-clock schemas require fingerprint and measured_at")
        if version < "2026-09-19":
            forbidden.update({"server_prompt_tokens", "server_prompt_seconds"})
        if version == "2026-09-16" and data.get("job", WORK_JOB) != WORK_JOB:
            raise ValueError("the initial host schema only records work jobs")
        if forbidden.intersection(data):
            raise ValueError("input carries fields not declared by its historical schema")
        return _check_numbers(data, cls)


def _check_numbers(data: Any, model: type[Model]) -> Any:
    if not isinstance(data, Mapping):
        return data
    for name, field in model.model_fields.items():
        value = data.get(name)
        if value is None:
            continue
        annotation = field.annotation
        if annotation in (int, int | None):
            if type(value) is not int or not INT64_MIN <= value <= INT64_MAX:
                raise ValueError(f"{name} must be an int64, not a Boolean or coerced number")
        elif annotation in (float, float | None):
            if type(value) not in (int, float):
                raise ValueError(f"{name} must be a finite number without coercion")
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{name} must be finite")
        elif name == "fingerprint_version" and type(value) is not int:
            raise ValueError("fingerprint_version must be an integer, not a Boolean")
    return data


def _fingerprint_bytes(cells: Mapping[str, object], keys: Sequence[str]) -> bytes:
    return json.dumps(
        {key: cells.get(key) for key in keys},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def fingerprint_v1(row: LegacyHostFingerprintRow) -> str:
    """AO1's historical preimage, including explicit null core/thread facts."""
    return hashlib.sha256(_fingerprint_bytes(row.model_dump(), _FINGERPRINT_V1_KEYS)).hexdigest()[
        :16
    ]


def fingerprint_v2(row: CorrectedHostFingerprintRow) -> str | None:
    """AO2's static hardware class, or no identity when no fact was sourced."""
    cells = row.model_dump()
    flags = row.flags.split()
    if row.flags != " ".join(sorted(set(flags))) or set(flags) - set(WATCHED_FLAGS):
        raise ValueError("fingerprint flags must be watched, sorted and space-joined")
    numbers = (row.cpu_family, row.cpu_model_number, row.cpu_stepping)
    if any(value is not None and value < 0 for value in numbers):
        raise ValueError("algorithm 2 CPU identifiers must be nonnegative")
    sourced = (
        any(value is not None and value.strip() for value in (row.cpu_model, row.cpu_vendor))
        or any(value is not None for value in numbers)
        or (row.l3_cache_bytes is not None and row.l3_cache_bytes > 0)
        or bool(flags)
    )
    if not sourced:
        return None
    return hashlib.sha256(_fingerprint_bytes(cells, _FINGERPRINT_V2_KEYS)).hexdigest()[:16]


def normalize_host_row(data: Mapping[str, object]) -> CorrectedHostFingerprintRow:
    """Normalize only recognized inputs; callers verify stored digests first."""
    payload = dict(data)
    if "version" not in payload:
        probe_keys = set(LegacyHostFingerprintRow.model_fields) - {"version"} - _CLOCK_FIELDS
        if set(payload) != probe_keys:
            raise ValueError("unstamped input is not an unchanged silicon constructor shape")
        payload["version"] = LEGACY_HOST_VERSIONS[-1]
    if payload["version"] == HOST_OUTPUT_VERSION:
        return CorrectedHostFingerprintRow.model_validate(payload)
    old = LegacyHostFingerprintRow.model_validate(payload)
    cells = old.model_dump()
    average = cells.pop("mhz_at_probe")
    for key in _LEGACY_CPU_FIELDS - {"mhz_at_probe"}:
        cells.pop(key)
    cells.update(
        version=HOST_OUTPUT_VERSION,
        fingerprint_version=1 if old.fingerprint is not None else None,
        cpu_observed_mhz=average,
    )
    return CorrectedHostFingerprintRow.model_validate(cells)


class HostFingerprintInput(CorrectedHostFingerprintRow):
    """Legacy producer adapter; the old MHz getter is not a persisted column."""

    __schema_stem__: ClassVar[str] = "host-output-input"

    @model_validator(mode="before")
    @classmethod
    def _normalize_before_stamping(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            return normalize_host_row(data).model_dump()
        return data

    @property
    def mhz_at_probe(self) -> float | None:
        """Temporary logging getter; remove with the legacy producer."""
        return self.cpu_observed_mhz


class HostWriterIdentity(WriterIdentity):
    """Immutable identity with protocol int64 numbers, not public coercion rules."""

    model_config = ConfigDict(frozen=True)
    attempt: int = Field(ge=1, le=INT64_MAX, strict=True)
    shard: int = Field(ge=0, le=INT64_MAX, strict=True)


def host_unit_id(*, covers: str, identity: WriterIdentity) -> uuid.UUID:
    """AO5, held in step with ledger.filenames without an upward import."""
    if date.fromisoformat(covers).isoformat() != covers:
        raise ValueError("host work units require a canonical UTC day")
    if identity.producer != HOST_PRODUCER:
        raise ValueError("host work units require the telemetry.silicon logical producer")
    name = (
        f"host-fingerprint|{covers}|{identity.run_id}|{identity.job.value}|"
        f"{identity.shard}|{HOST_PRODUCER}"
    )
    return uuid.uuid5(HOST_NAMESPACE, name)


def host_file_id(*, unit: uuid.UUID, attempt: int, written_at_ms: int) -> uuid.UUID:
    """AO6's clock/work-unit address, never a content address."""
    if unit.version != 5:
        raise ValueError("file identity requires a UUID5 work unit")
    for name, value, minimum in (("attempt", attempt, 1), ("written_at_ms", written_at_ms, 0)):
        if type(value) is not int or not minimum <= value <= INT64_MAX:
            raise ValueError(f"{name} must be a valid int64")
    digest = hashlib.sha256(f"{unit}|{attempt}|{written_at_ms}".encode()).digest()
    return uuid.UUID(
        int=(
            (written_at_ms & ((1 << 48) - 1)) << 80
            | 8 << 76
            | (int.from_bytes(digest[:2], "big") & ((1 << 12) - 1)) << 64
            | 0b10 << 62
            | (int.from_bytes(digest[2:10], "big") & ((1 << 62) - 1))
        )
    )


class HostStoredRow(CorrectedHostFingerprintRow):
    """Corrected row followed by identity columns absent from the row contract."""

    __schema_stem__: ClassVar[str] = "host-output-stored-row"
    ledger: LedgerName
    covers: DateStamp
    attempt: int = Field(ge=1, le=INT64_MAX, strict=True)
    unit_id: Annotated[
        str,
        StringConstraints(
            pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    ]

    @model_validator(mode="after")
    def _host_identity(self) -> Self:
        date.fromisoformat(self.date)
        if self.ledger is not LedgerName.HOST_FINGERPRINT or self.covers != self.date:
            raise ValueError("stored host covers must equal the row's UTC date")
        name = (
            f"host-fingerprint|{self.covers}|{self.run_id}|{self.job.value}|"
            f"{self.shard}|{HOST_PRODUCER}"
        )
        if self.unit_id != str(uuid.uuid5(HOST_NAMESPACE, name)):
            raise ValueError("stored row unit_id does not name the logical host producer")
        return self


def canonical_host_rows(rows: Sequence[HostStoredRow]) -> bytes:
    """AO7's canonical stored-order JSON lines, including identity and trailing LF."""
    return b"".join(
        json.dumps(
            row.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
        for row in rows
    )


def normalize_stored_host_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    content_sha256: str,
) -> tuple[HostStoredRow, ...]:
    """Check the original canonical digest and RowIdentity BEFORE legacy migration."""
    original = b"".join(
        json.dumps(
            row,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
        for row in rows
    )
    if hashlib.sha256(original).hexdigest() != content_sha256:
        raise ValueError("original stored host content_sha256 mismatch")
    normalized: list[HostStoredRow] = []
    identity_keys = set(RowIdentity.model_fields)
    own_identity = {"run_id", "job", "shard"}
    for source in rows:
        identity = {key: source[key] for key in identity_keys if key in source}
        _check_numbers(identity, RowIdentity)
        original_identity = RowIdentity.model_validate(identity)
        if (
            original_identity.ledger is not LedgerName.HOST_FINGERPRINT
            or original_identity.covers != source.get("date")
        ):
            raise ValueError("original stored host identity contradicts its date or ledger")
        seed = (
            f"host-fingerprint|{original_identity.covers}|{original_identity.run_id}|"
            f"{original_identity.job.value}|{original_identity.shard}|{HOST_PRODUCER}"
        )
        if original_identity.unit_id != str(uuid.uuid5(HOST_NAMESPACE, seed)):
            raise ValueError("original stored host unit_id does not name its logical producer")
        payload = {key: value for key, value in source.items() if key not in identity_keys}
        payload.update({key: source[key] for key in own_identity})
        row = normalize_host_row(payload)
        normalized.append(HostStoredRow.model_validate(row.model_dump() | identity))
    return tuple(normalized)


class CandidateFileEnvelope(FileEnvelope):
    """H16 provenance oracle, preserving the public envelope and metadata key sets."""

    model_config = ConfigDict(frozen=True)
    __schema_stem__: ClassVar[str] = "host-output-file-envelope"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=HOST_OUTPUT_VERSION,
            change="Allow explicit truthful native host raw writer/container pairs.",
            why="Candidate validation must not pretend Rust bytes were written by Python.",
        ),
        *FileEnvelope.__changelog__[:3],
        ChangelogEntry(
            version="2026-09-30",
            change="Earlier changes are in file-envelope git history.",
            why="The candidate retains public fields and historical envelope semantics.",
        ),
    )

    identity: HostWriterIdentity
    written_at_ms: int = Field(ge=0, le=INT64_MAX, strict=True)
    built_from: int | None = Field(default=None, ge=0, le=INT64_MAX, strict=True)
    writer: Literal[
        "idhazh.ledger.parquet",
        "idhazh_rust.ledger.parquet",
        "idhazh.ledger.json_lines",
        "idhazh_rust.ledger.json_lines",
    ]

    @model_validator(mode="before")
    @classmethod
    def _freeze_identity(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and isinstance(data.get("identity"), WriterIdentity):
            return dict(data) | {"identity": data["identity"].model_dump()}
        return data

    @model_validator(mode="after")
    def _native_scope(self) -> Self:
        known = {entry.version for entry in FileEnvelope.__changelog__} | {HOST_OUTPUT_VERSION}
        if self.version not in known:
            raise ValueError("unrecognized candidate envelope version")
        if self.writer.startswith("idhazh_rust."):
            if (
                self.version != HOST_OUTPUT_VERSION
                or self.row_schema_version != HOST_OUTPUT_VERSION
                or self.ledger is not LedgerName.HOST_FINGERPRINT
                or self.tier is not Tier.RAW
            ):
                raise ValueError("native writer requires corrected host raw envelope/schema")
        if self.writer.endswith(".json_lines") and self.compression is not Compression.NONE:
            raise ValueError("JSON lines must record compression none")
        return self

    def validate_container(self, container: Format) -> Self:
        """The format is a reader-observed property, not a new envelope key."""
        container = Format(container)
        expected = ".parquet" if container is Format.PARQUET else ".json_lines"
        if not self.writer.endswith(expected):
            raise ValueError("writer does not match the observed container")
        return self

    @classmethod
    def from_metadata(cls, mapping: Mapping[bytes, bytes]) -> Self:
        for key in (b"attempt", b"shard", b"written_at_ms", b"built_from"):
            if key in mapping and re.fullmatch(rb"[0-9]+", mapping[key]) is None:
                raise ValueError(f"{key.decode()} metadata must be ASCII decimal")
        return super().from_metadata(mapping)


class HostPlannedFile(Model):
    """One validated immutable day group, ready for rendering before any write."""

    model_config = ConfigDict(frozen=True)
    envelope: CandidateFileEnvelope
    format: Format
    relative_path: RelPath
    rows: tuple[HostStoredRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _matches_declared_file(self) -> Self:
        env = self.envelope.validate_container(self.format)
        if (
            env.ledger is not LedgerName.HOST_FINGERPRINT
            or env.tier is not Tier.RAW
            or env.version != HOST_OUTPUT_VERSION
            or env.row_schema_version != HOST_OUTPUT_VERSION
            or env.identity.producer != HOST_PRODUCER
        ):
            raise ValueError("a host write plan only declares corrected logical host raw files")
        expected_unit = host_unit_id(covers=env.covers, identity=env.identity)
        if env.unit_id != expected_unit:
            raise ValueError("planned unit_id does not match the host work-unit seed")
        if env.file_id != host_file_id(
            unit=expected_unit,
            attempt=env.identity.attempt,
            written_at_ms=env.written_at_ms,
        ):
            raise ValueError("planned file_id does not match the actual write-clock seed")
        for row in self.rows:
            if (
                row.covers != env.covers
                or row.run_id != env.identity.run_id
                or row.attempt != env.identity.attempt
                or row.job != env.identity.job
                or row.shard != env.identity.shard
                or row.unit_id != str(env.unit_id)
            ):
                raise ValueError("planned row identity contradicts its file envelope")
        if len(self.rows) != 1:
            raise ValueError("one host work unit has one whole row, not duplicate row keys")
        if hashlib.sha256(canonical_host_rows(self.rows)).hexdigest() != env.content_sha256:
            raise ValueError("planned canonical hash does not match the stored rows")
        return self


class HostWritePlan(Contract):
    """H15's immutable event invocation and finite set of exact planned host files."""

    model_config = ConfigDict(frozen=True)
    __schema_stem__: ClassVar[str] = "host-write-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=HOST_OUTPUT_VERSION,
            change="Declare immutable event-scoped host write plans.",
            why="Retries and recovery must reference the same rows, paths, IDs and clocks.",
        ),
    )

    version: Literal["2026-10-10"]
    event_id: uuid.UUID
    target_root: RelPath
    publication_identity: HostWriterIdentity
    prefix: tuple[RelPath, ...] = ("host-fingerprint",)
    files: tuple[HostPlannedFile, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _freeze_publication_identity(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and isinstance(
            data.get("publication_identity"),
            WriterIdentity,
        ):
            return dict(data) | {"publication_identity": data["publication_identity"].model_dump()}
        return data

    @model_validator(mode="after")
    def _exact_paths_and_invocation(self) -> Self:
        if not self.prefix or self.prefix[-1] != "host-fingerprint":
            raise ValueError("host prefix must end in host-fingerprint")
        if any("/" in segment for segment in self.prefix):
            raise ValueError("host prefix contains path segments, not paths")
        paths: set[str] = set()
        days: set[str] = set()
        for planned in self.files:
            env = planned.envelope
            invocation = self.publication_identity
            if any(
                getattr(env.identity, key) != getattr(invocation, key)
                for key in ("run_id", "attempt", "job", "shard", "git_sha")
            ):
                raise ValueError("ledger identity belongs to another publication invocation")
            parts = date.fromisoformat(env.covers).isoformat().split("-")
            suffix = ".parquet" if planned.format is Format.PARQUET else ".json"
            expected = "/".join(("raw", *self.prefix, *parts, f"{env.file_id}{suffix}"))
            if planned.relative_path != expected:
                raise ValueError("planned relative path does not match the host raw grammar")
            if planned.relative_path in paths or env.covers in days:
                raise ValueError("a plan must not duplicate a path or UTC day group")
            paths.add(planned.relative_path)
            days.add(env.covers)
        return self

    def validate_successor(self, previous: HostWritePlan) -> Self:
        """AE6: unchanged retries reuse a plan; changed rows need a later real clock."""
        if (
            self.target_root != previous.target_root
            or self.prefix != previous.prefix
            or self.publication_identity != previous.publication_identity
        ):
            raise ValueError("successor belongs to another root or invocation")
        prior = {file.envelope.unit_id: file for file in previous.files}
        if set(prior) != {file.envelope.unit_id for file in self.files}:
            raise ValueError("successor changes the declared work-unit set")
        unchanged = all(
            planned.envelope.content_sha256
            == prior[planned.envelope.unit_id].envelope.content_sha256
            for planned in self.files
        )
        if unchanged:
            if self != previous:
                raise ValueError("identical retries must retain the immutable plan and event")
            return self
        if self.event_id == previous.event_id:
            raise ValueError("changed content requires a new event and strictly later clock")
        for planned in self.files:
            old = prior[planned.envelope.unit_id]
            before, after = old.rows[0], planned.rows[0]
            machine_fields = (
                set(CorrectedHostFingerprintRow.model_fields) - _CLOCK_FIELDS - _TARGET_FIELDS
            )
            if any(getattr(before, key) != getattr(after, key) for key in machine_fields):
                raise ValueError("successor cannot remeasure the original machine probe or hash")
            if before.cpu_target_measured_at is not None and any(
                getattr(before, key) != getattr(after, key) for key in _TARGET_FIELDS
            ):
                raise ValueError("successor cannot refresh the frozen target capture")
            if planned.envelope.content_sha256 == old.envelope.content_sha256:
                if planned != old:
                    raise ValueError("unchanged day groups must retain their immutable file plan")
            elif planned.envelope.written_at_ms <= old.envelope.written_at_ms:
                raise ValueError("changed content requires a new event and strictly later clock")
        return self


class HostPublicationReceipt(Contract):
    """The existing receipt shape with deeply immutable completed-write evidence."""

    model_config = ConfigDict(frozen=True)
    __schema_stem__: ClassVar[str] = "host-publication-receipt"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = PublicationReceipt.__changelog__
    version: Literal["2026-10-09"]
    identity: HostWriterIdentity
    writes: Mapping[RelPath, Sha256] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _freeze_receipt_identity(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and isinstance(data.get("identity"), WriterIdentity):
            return dict(data) | {"identity": data["identity"].model_dump()}
        return data

    @model_validator(mode="after")
    def _freeze_writes(self) -> Self:
        object.__setattr__(self, "writes", MappingProxyType(dict(self.writes)))
        return self

    @field_serializer("writes")
    def _serialize_writes(self, writes: Mapping[str, str]) -> dict[str, str]:
        return dict(writes)


class HostWriteCompletion(Contract):
    """An event's completed subset; verify the physical bytes outside the contract."""

    model_config = ConfigDict(frozen=True)
    __schema_stem__: ClassVar[str] = "host-write-completion"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=HOST_OUTPUT_VERSION,
            change="Bind completed publication receipts to host events.",
            why="Partial I/O failure must retain every previously completed planned file.",
        ),
    )

    version: Literal["2026-10-10"]
    event_id: uuid.UUID
    receipt: HostPublicationReceipt

    @model_validator(mode="before")
    @classmethod
    def _freeze_receipt(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and isinstance(data.get("receipt"), PublicationReceipt):
            return dict(data) | {"receipt": data["receipt"].model_dump()}
        return data

    def validate_plan(self, plan: HostWritePlan, *, require_all: bool = True) -> Self:
        """Membership and invocation checks, not physical hashing or authorization."""
        if self.event_id != plan.event_id:
            raise ValueError("completion belongs to another triggering event")
        if self.receipt.identity != plan.publication_identity:
            raise ValueError("completion receipt belongs to another publication invocation")
        planned = {f"{plan.target_root}/{file.relative_path}" for file in plan.files}
        completed = set(self.receipt.writes)
        if not completed <= planned:
            raise ValueError("completion contains an unplanned path")
        if require_all and completed != planned:
            raise ValueError("completion omits planned files")
        return self
