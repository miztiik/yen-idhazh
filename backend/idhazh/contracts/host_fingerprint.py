"""What hardware a task drew, and how earlier host records remain readable."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date as calendar_date
from datetime import datetime
from types import MappingProxyType
from typing import Any, ClassVar, Final, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from idhazh.contracts.base import (
    WORK_JOB,
    ChangelogEntry,
    Contract,
    DateStamp,
    FingerprintId,
    JobName,
    PipelineName,
    RunId,
    ServerJob,
    TaskName,
    Timestamp,
)

#: The instruction-set flags this project has a reason to read back. A flag
#: outside this list is not recorded, so the column stays a fixed width and
#: adding one is a code change rather than a schema change. These are the ones
#: an inference runtime dispatches on: AVX-512 and AMX decide which kernel
#: llama.cpp picks, and that is the difference the lottery keeps showing up as.
WATCHED_FLAGS: tuple[str, ...] = (
    "amx_bf16",
    "amx_int8",
    "amx_tile",
    "avx2",
    "avx512_bf16",
    "avx512_fp16",
    "avx512_vnni",
    "avx512f",
    "avx_vnni",
    "f16c",
    "fma",
    "sse4_2",
)

HOST_FINGERPRINT_VERSION: Final = "2026-11-28"
_CORRECTED_VERSION: Final = "2026-10-26"
HOST_HARDWARE_VERSION: Final = "2026-11-26"
HOST_FINGERPRINT_READ_VERSIONS: Final = frozenset(
    {"2026-10-10", "2026-10-12", "2026-10-14", _CORRECTED_VERSION, HOST_FINGERPRINT_VERSION}
)
LEGACY_HOST_VERSIONS: Final = (
    "2026-09-16",
    "2026-09-17",
    "2026-09-18",
    "2026-09-19",
    "2026-09-20",
)
INT64_MAX: Final = (1 << 63) - 1
INT64_MIN: Final = -(1 << 63)
LEGACY_CPU_FIELDS: Final = frozenset({"cores", "threads", "mhz_max", "mhz_at_probe"})
HOST_MODEL_FIELDS: Final = frozenset(
    {"model_load_ms", "server_prompt_tokens", "server_prompt_seconds"}
)
# Physical name in retained files, not a field in either readable host model.
RETIRED_HOST_CLOCK: Final = "job_seconds"
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
_CORRECTED_INT_FIELDS: Final = frozenset(
    {
        "shard",
        "fingerprint_version",
        "cpu_family",
        "cpu_model_number",
        "cpu_stepping",
        "cpu_physical_cores",
        "cpu_logical_processors",
        "cpu_allowed_processors",
        "l3_cache_bytes",
        "memcpy_probe_mib",
        "server_prompt_tokens",
    }
)
_CORRECTED_FLOAT_FIELDS: Final = frozenset(
    {
        "cpu_quota_cores",
        "cpu_observed_mhz",
        "cpu_reported_max_mhz",
        "machine_memory_total_mib",
        "boot_seconds",
        "memcpy_gib_s",
        "model_load_ms",
        "server_prompt_seconds",
    }
)


#: The surface that reads each column, by the path that reads it. Every column of
#: this row appears exactly once, so minting a column without saying who will
#: read it fails `backend/tests/contracts/test_column_readers.py` rather than
#: landing quietly and costing a cell on every job for the rest of the archive.
#:
#: **A reader is where the value is turned into an answer**, not where it is
#: written and not where it is carried past. The probe that fills the cell, the
#: ledger that appends it and the generated TypeScript that types it are all on
#: the other side of the question.
#:
#: **One column names one reader, even where several read it.** The one named is
#: the surface that would notice first if the column stopped arriving, which is
#: the fact a person deleting a column needs. A second reader is found by search;
#: the first one to break is not.
#: A declared panel query counts as a reader. Shared, pipelines, model, machine,
#: then voices owns a column when more than one query declares it.
#: Registry ownership does not change the persisted row or its version.
#:
#: What this cannot settle is whether the named surface still DRAWS the value -
#: only that it still names the column. A panel that reads a cell and then throws
#: it away passes here and fails the browser check instead.
COLUMN_READERS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "frontend/src/lib/console/queries/machine.ts": (
            "version",
            "date",
            "run_id",
            "job",
            "pipeline_name",
            "task_name",
            "shard",
            "server_prompt_tokens",
            "server_prompt_seconds",
            "fingerprint",
            "fingerprint_version",
            "cpu_model",
            "l3_cache_bytes",
            "cpu_logical_processors",
        ),
    }
)

UNREAD_CELLS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "Machine detail retained in records after its Hardware presentation was removed": (
            "cpu_vendor",
            "cpu_family",
            "cpu_model_number",
            "cpu_stepping",
            "microcode",
            "cpu_physical_cores",
            "cpu_allowed_processors",
            "cpu_quota_cores",
            "cpu_quota_state",
            "cpu_target_measured_at",
            "cpu_observed_mhz",
            "cpu_reported_max_mhz",
            "flags",
            "boot_seconds",
            "memcpy_gib_s",
            "memcpy_probe_mib",
            "vm_size",
            "vm_location",
            "vm_zone",
            "vm_fault_domain",
        ),
        "Historical machine label and sampling instant": ("measured_at", "runner_name"),
        "Historical model load retained for compatibility": ("model_load_ms",),
        "Total machine RAM returned by the fingerprint API, not drawn by the console": (
            "machine_memory_total_mib",
        ),
    }
)


class LegacyHostFingerprintRow(Contract):
    """One declared pre-correction host row, validated before normalization."""

    __schema_stem__: ClassVar[str] = "host-fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-20",
            change="`memcpy_probe_mib` is the derived buffer, not the configured one.",
            why="A constant could not clear a cache that varies fifteenfold across the fleet.",
        ),
        ChangelogEntry(
            version="2026-09-19",
            change="Added `server_prompt_tokens`, `server_prompt_seconds`.",
            why="Arithmetic over the item ledger cannot check the item ledger.",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Added `model_load_ms`; `fingerprint` and `measured_at` became optional.",
            why="A model reading could be recorded independently of the opening hardware.",
        ),
        ChangelogEntry(
            version="2026-09-17",
            change="Widened `job` to every workflow job that draws its own machine.",
            why="A run whose slowest job is unmeasured is a run whose cost nobody can attribute.",
        ),
        ChangelogEntry(
            version="2026-09-16",
            change="Initial shape: the silicon a job drew, its instruction set and its bandwidth.",
            why="Throughput moved 3.7x by machine and nothing recorded which machine.",
        ),
    )

    date: DateStamp
    run_id: RunId
    job: ServerJob = Field(
        default=WORK_JOB,
        description=(
            "The workflow job that drew this machine. Every job that draws its own "
            "runner writes one row, because a run is only as fast as its slowest job."
        ),
    )
    shard: int = Field(
        ge=0, description="The shard within that job. A single-shard job writes 0."
    )

    fingerprint: FingerprintId | None = Field(
        default=None,
        description=(
            "A digest over the columns that cannot change inside a job - vendor, "
            "family, model, stepping, core counts, cache and flags. Two jobs on the "
            "same kind of machine carry the same value, which is what makes a "
            "distribution countable without matching model-name strings by hand."
        ),
    )

    cpu_model: str | None = Field(
        default=None, description="The `model name` line, in the host's own words."
    )
    cpu_vendor: str | None = Field(
        default=None, description="`vendor_id`: GenuineIntel, AuthenticAMD."
    )
    cpu_family: int | None = Field(
        default=None, description="`cpu family`. With model and stepping this names the part."
    )
    cpu_model_number: int | None = Field(
        default=None, description="`model`, the number rather than the marketing name."
    )
    cpu_stepping: int | None = Field(default=None, description="`stepping`.")
    microcode: str | None = Field(
        default=None, description="`microcode` revision, which moves under a fixed stepping."
    )

    cores: int | None = Field(default=None, ge=1, description="Physical cores the job can see.")
    threads: int | None = Field(
        default=None, ge=1, description="Logical processors. Four on every stock runner so far."
    )
    l3_cache_bytes: int | None = Field(
        default=None,
        ge=0,
        description=(
            "L3 as the host reports it, and what sizes the bandwidth probe. Read "
            "beside `memcpy_probe_mib`: a probe buffer that does not clear this "
            "measured cache rather than memory."
        ),
    )

    mhz_max: float | None = Field(
        default=None, gt=0, description="`CPU max MHz`, where the host publishes one."
    )
    mhz_at_probe: float | None = Field(
        default=None,
        gt=0,
        description=(
            "The mean `cpu MHz` across processors at the moment of the probe. Not a "
            "reading under load - the probe runs before the model server starts - so "
            "it says what the machine idles at, never what it sustains."
        ),
    )

    flags: str = Field(
        default="",
        description=(
            "The watched instruction-set flags this host reported, sorted and space "
            "joined. Empty means none of them, which is itself a reading."
        ),
    )

    boot_seconds: float | None = Field(
        default=None,
        ge=0,
        description=(
            "How long the machine had been up when the job reached this probe. A "
            "small number is a freshly started virtual machine; a large one is a "
            "pooled machine this job was handed."
        ),
    )

    memcpy_gib_s: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Large-block copy bandwidth, bytes read plus bytes written, the way "
            "STREAM counts a copy. Decode is bandwidth bound and nothing else here "
            "measures bandwidth. Absent where the probe was switched off."
        ),
    )
    memcpy_probe_mib: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The buffer each side of the copy used, as used rather than as "
            "configured: the larger of the configured floor and twice "
            "`l3_cache_bytes`. Under twice that cache the figure cannot be read as "
            "a memory rate, which is what rows written before 2026-09-20 carry."
        ),
    )

    vm_size: str | None = Field(
        default=None,
        description=(
            "The platform's own name for this machine size, from the host metadata "
            "service. This is the placement decision in the platform's vocabulary "
            "rather than ours. Absent where the service did not answer."
        ),
    )
    vm_location: str | None = Field(
        default=None, description="The region the metadata service named."
    )
    vm_zone: str | None = Field(
        default=None, description="The availability zone, where the platform publishes one."
    )
    vm_fault_domain: str | None = Field(
        default=None, description="The fault domain, which separates one rack from another."
    )

    runner_name: str | None = Field(
        default=None, description="The runner label the platform gave this job."
    )
    measured_at: Timestamp | None = Field(
        default=None,
        description="When the machine was observed, in UTC.",
    )

    model_load_ms: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the server spent opening the weights before the first item. "
            "Once per job, which is this row's grain."
        ),
    )
    server_prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens llama-server itself counted reading, cached tokens "
            "excluded. The second instrument. The item ledger's own answer is "
            "`sum(input_tokens) - sum(cached_tokens)`; a gap over 5 percent means one "
            "of the two is wrong, and arithmetic over that ledger could never say so."
        ),
    )
    server_prompt_seconds: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Seconds llama-server itself counted reading prompts. Pairs with the cell "
            "above - a rate is a ratio, and the 80 percent defect this check caught in "
            "August 2026 was in the numerator, so one cell alone could not see it."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _declared_input(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or data.get("version") not in LEGACY_HOST_VERSIONS:
            raise ValueError("legacy input requires a declared historical schema version")
        version = data["version"]
        forbidden: set[str] = set()
        if version < "2026-09-18":
            forbidden.update(HOST_MODEL_FIELDS)
            if data.get("fingerprint") is None or data.get("measured_at") is None:
                raise ValueError("earliest host schemas require fingerprint and measured_at")
        if version < "2026-09-19":
            forbidden.update({"server_prompt_tokens", "server_prompt_seconds"})
        if version == "2026-09-16" and data.get("job", WORK_JOB) != WORK_JOB:
            raise ValueError("the initial host schema only records work jobs")
        if forbidden.intersection(data):
            raise ValueError("input carries fields not declared by its historical schema")
        return project_retained_host_cells(data)

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A reading this host could not take is an empty cell.

        Empty is not zero. A machine that publishes no L3 size and a machine with
        no L3 are different facts, and only one of them is interesting.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent reading, never a zero.

        A column the file does not carry at all reads as an empty cell too, so a
        row written before a column existed still opens. That is what keeps a
        widening additive: every cell this row can be missing is one whose
        absence means nobody took the reading, and every other cell fails its own
        field parser by name rather than raising on a bare key.

        `flags` is the one column that has to be there. An empty `flags` is a
        reading - it says the host reported none of the watched instruction-set
        flags - so a file that never carried the column would arrive as that
        reading, and nothing downstream could tell the two apart.

        A column this build cannot place is kept rather than projected away, so
        the model refuses the row instead of quietly losing the cell.
        """
        payload: dict[str, Any] = dict.fromkeys(cls.model_fields, "") | dict(row)
        _parse_retired_csv_cell(payload)
        payload["flags"] = row["flags"]
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time."""
        return tuple(name for name, field in cls.model_fields.items() if field.default is None)


def _check_numbers(data: Any, model: type[Contract]) -> Any:
    """Refuse coercion and non-finite protocol numbers at the shared boundary."""
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


def project_retained_host_cells(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the retired on-disk cell on known stamps, then omit it."""
    payload = dict(data)
    if RETIRED_HOST_CLOCK not in payload:
        return payload
    version = payload.get("version")
    value = payload.pop(RETIRED_HOST_CLOCK)
    if not isinstance(version, str) or version == HOST_FINGERPRINT_VERSION or (
        version not in LEGACY_HOST_VERSIONS
        and version not in HOST_FINGERPRINT_READ_VERSIONS
        and version != HOST_HARDWARE_VERSION
    ):
        raise ValueError("retired host column is not declared by this row stamp")
    if value is not None and (
        version in (*LEGACY_HOST_VERSIONS[:2], HOST_HARDWARE_VERSION)
        or type(value) is not int or not 0 <= value <= INT64_MAX
    ):
        raise ValueError("invalid retired host storage cell")
    return payload


def _parse_retired_csv_cell(payload: dict[str, Any]) -> None:
    if RETIRED_HOST_CLOCK in payload:
        value = payload[RETIRED_HOST_CLOCK]
        payload[RETIRED_HOST_CLOCK] = None if value == "" else int(value)


def _fingerprint_bytes(cells: Mapping[str, object], keys: tuple[str, ...]) -> bytes:
    return json.dumps(
        {key: cells.get(key) for key in keys},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


class _HostHardwareCells(Contract):
    """Hardware cells shared by the existing reader and the strict current writer."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    __schema_stem__: ClassVar[str] = "host-hardware-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-26",
            change="Keep hardware and generic task identity; record timing separately.",
            why="Task performance has its own measurement and writer.",
        ),
    )

    date: DateStamp
    run_id: RunId
    job: JobName | None = None
    pipeline_name: PipelineName | None = None
    task_name: TaskName | None = None
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
    cpu_target_measured_at: Timestamp | None = None

    l3_cache_bytes: int | None = Field(default=None, ge=0)
    machine_memory_total_mib: float | None = Field(
        default=None,
        gt=0,
        strict=True,
        description="Linux kernel-visible MemTotal at capture, in MiB; unavailable stays null.",
    )
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
    measured_at: Timestamp | None = None

    @model_validator(mode="before")
    @classmethod
    def _strict_numbers(cls, data: Any) -> Any:
        return _check_numbers(data, cls)

    @model_validator(mode="after")
    def _consistent_measurements(self) -> Self:
        for name in ("measured_at", "cpu_target_measured_at"):
            value = getattr(self, name)
            if value is not None:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        if (self.fingerprint is None) != (self.fingerprint_version is None):
            raise ValueError("fingerprint and fingerprint_version must be present together")
        if self.fingerprint_version == 2 and self.fingerprint != fingerprint_v2(self):
            raise ValueError("fingerprint does not match algorithm 2 hardware facts")
        if (self.cpu_quota_cores is not None) != (self.cpu_quota_state == "finite"):
            raise ValueError("cpu_quota_state is finite iff cpu_quota_cores is present")
        has_target = self.cpu_target_measured_at is not None
        if has_target != (self.cpu_quota_state is not None):
            raise ValueError("target capture time and quota state must be present together")
        if self.cpu_allowed_processors is not None and (
            not has_target or self.cpu_logical_processors is None
        ):
            raise ValueError("allowed processors require a target capture and logical count")
        if self.cpu_logical_processors is not None:
            for name in ("cpu_physical_cores", "cpu_allowed_processors"):
                count = getattr(self, name)
                if count is not None and count > self.cpu_logical_processors:
                    raise ValueError(f"{name} cannot exceed cpu_logical_processors")
        if self.cpu_target_measured_at is not None and self.measured_at is not None:
            if self.cpu_target_measured_at < self.measured_at:
                raise ValueError("target capture cannot precede the original machine probe")
        return self


class HostHardwareRow(_HostHardwareCells):
    """One current hardware capture, without the superseded task measurements."""

    model_config = ConfigDict(strict=True)
    __require_explicit_version__: ClassVar[bool] = True

    version: Literal["2026-11-26"]
    job: JobName | None
    pipeline_name: PipelineName
    task_name: TaskName

    @model_validator(mode="after")
    def _calendar_date(self) -> Self:
        calendar_date.fromisoformat(self.date)
        return self


class HostFingerprintRow(_HostHardwareCells):
    """Hardware and retained model measurements in the normalized read view."""

    __schema_stem__: ClassVar[str] = "host-fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-28",
            change="Project only hardware and retained model measurements.",
            why="Task Performance measures the named work, independently of the runner.",
        ),
        ChangelogEntry(
            version="2026-10-26",
            change="Add optional total machine RAM capacity in MiB.",
            why="Machine capacity is distinct from transient task and process memory.",
        ),
        ChangelogEntry(
            version="2026-10-14",
            change="Allow pipeline and task identity without a legacy job value.",
            why="Shared host records group reusable readings by separate identity columns.",
        ),
        ChangelogEntry(
            version="2026-10-10",
            change="Replace ambiguous CPU cells and add versioned fingerprints.",
            why="Topology, target constraints and frequencies are different measurements.",
        ),
        ChangelogEntry(
            version="2026-09-20",
            change="Earlier changes are in this contract's git history.",
            why="Git is the archive for older shape changes.",
        ),
    )

    job: ServerJob | JobName | None = Field(default=WORK_JOB)
    model_load_ms: float | None = Field(default=None, ge=0)
    server_prompt_tokens: int | None = Field(default=None, ge=0)
    server_prompt_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _normalize_before_stamping(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload = project_retained_host_cells(data)
        if payload.get("version") in LEGACY_HOST_VERSIONS:
            return normalize_host_row(payload).model_dump()
        if LEGACY_CPU_FIELDS.intersection(payload):
            raise ValueError(
                "legacy CPU fields require a declared legacy stamp"
            )
        if payload.get("version") == HOST_HARDWARE_VERSION:
            if any(payload.get(name) is not None for name in HOST_MODEL_FIELDS):
                raise ValueError("hardware capture cannot carry historical timing values")
            hardware = HostHardwareRow.model_validate(
                {key: value for key, value in payload.items() if key not in HOST_MODEL_FIELDS}
            )
            return hardware.model_dump()
        return payload

    @model_validator(mode="after")
    def _host_identity(self) -> Self:
        if self.version == HOST_HARDWARE_VERSION:
            return self
        if (self.pipeline_name is None) != (self.task_name is None):
            raise ValueError("host row requires both pipeline_name and task_name")
        if self.task_name is None and self.job is None:
            raise ValueError("host row requires a legacy job or pipeline and task")
        if self.task_name is not None and self.job not in (None, self.task_name):
            raise ValueError("generic host row job must be absent or match task_name")
        if self.version not in HOST_FINGERPRINT_READ_VERSIONS:
            raise ValueError("normalized host row has an unsupported schema version")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        legacy = any(name in row for name in LEGACY_CPU_FIELDS)
        model = LegacyHostFingerprintRow if legacy else cls
        payload: dict[str, Any] = dict.fromkeys(model.model_fields, "") | dict(row)
        _parse_retired_csv_cell(payload)
        payload["flags"] = row["flags"]
        for name, field in model.model_fields.items():
            if field.default is None and payload.get(name) == "":
                payload[name] = None
        if legacy:
            payload = LegacyHostFingerprintRow.model_validate(payload).model_dump()
        else:
            if payload["job"] == "" and payload["pipeline_name"] and payload["task_name"]:
                payload["job"] = None
            for name in _CORRECTED_INT_FIELDS:
                if payload.get(name) not in (None, ""):
                    payload[name] = int(payload[name])
            for name in _CORRECTED_FLOAT_FIELDS:
                if payload.get(name) not in (None, ""):
                    payload[name] = float(payload[name])
        return cls.model_validate(payload)


def fingerprint_v2(row: _HostHardwareCells) -> str | None:
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


def normalize_host_row(data: Mapping[str, object]) -> HostFingerprintRow:
    """Normalize only declared host shapes without losing supported facts."""
    payload = project_retained_host_cells(data)
    version = payload.get("version")
    if not isinstance(version, str):
        raise ValueError("unrecognized host row schema version")
    if version == HOST_HARDWARE_VERSION:
        hardware = HostHardwareRow.model_validate(payload)
        return HostFingerprintRow.model_construct(**hardware.model_dump())
    if version in HOST_FINGERPRINT_READ_VERSIONS:
        return HostFingerprintRow.model_validate(payload)
    if version not in LEGACY_HOST_VERSIONS:
        raise ValueError("unrecognized host row schema version")
    old = LegacyHostFingerprintRow.model_validate(_check_numbers(payload, LegacyHostFingerprintRow))
    cells = old.model_dump()
    average = cells.pop("mhz_at_probe")
    for key in LEGACY_CPU_FIELDS - {"mhz_at_probe"}:
        cells.pop(key)
    cells.update(
        version=_CORRECTED_VERSION,
        fingerprint_version=1 if old.fingerprint is not None else None,
        cpu_observed_mhz=average,
    )
    return HostFingerprintRow.model_validate(cells)


def strip_null_legacy_placeholders(data: Mapping[str, object]) -> dict[str, object]:
    """Drop null columns added by a later Parquet schema widening."""
    payload = dict(data)
    version = payload.get("version")
    if not isinstance(version, str) or version not in LEGACY_HOST_VERSIONS:
        return payload
    forbidden: set[str] = set()
    if version < "2026-09-18":
        forbidden.update(HOST_MODEL_FIELDS)
    if version < "2026-09-19":
        forbidden.update({"server_prompt_tokens", "server_prompt_seconds"})
    return {
        key: value
        for key, value in payload.items()
        if key not in forbidden or value is not None
    }
