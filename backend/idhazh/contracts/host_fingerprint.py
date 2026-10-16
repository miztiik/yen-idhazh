"""What silicon a job drew, and what that job cost, as the host itself reported it.

One row a job. The columns are fixed for the length of that job - a processor
does not change model number mid-run - which is why they are not repeated on
every item row beside the readings that do move.

**The row is written in two halves and neither half is ever edited.** The probe
runs before the job's heaviest step, because the bandwidth reading wants an idle
machine; the clock, the weight-load cost and what the model server itself counted
are only known when the job is over. So each half is a row of this shape carrying
the cells it has, and the compaction is what unites them - one key, no cell filled
twice, one row in the day file.

Pipeline and task names are validated strings. Legacy `job` values remain
readable as enums or strings; readers compare their values, not enum identity.
Hardware identifiers are open strings because a closed vocabulary would refuse
a new part rather than record it. See `docs/reference/host-metrics.md`.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
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

HOST_FINGERPRINT_VERSION: Final = "2026-10-14"
HOST_FINGERPRINT_READ_VERSIONS: Final = frozenset(
    {"2026-10-10", "2026-10-12", HOST_FINGERPRINT_VERSION}
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
_CLOCK_FIELDS: Final = frozenset(
    {"model_load_ms", "job_seconds", "server_prompt_tokens", "server_prompt_seconds"}
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
        "job_seconds",
        "server_prompt_tokens",
    }
)
_CORRECTED_FLOAT_FIELDS: Final = frozenset(
    {
        "cpu_quota_cores",
        "cpu_observed_mhz",
        "cpu_reported_max_mhz",
        "boot_seconds",
        "memcpy_gib_s",
        "model_load_ms",
        "server_prompt_seconds",
    }
)


class _Unset:
    __slots__ = ()


_UNSET: Final = _Unset()

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
            "l3_cache_bytes",
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
            "job_seconds",
            "cpu_logical_processors",
            "model_load_ms",
        ),
    }
)

UNREAD_CELLS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {"Historical machine label and sampling instant": ("measured_at", "runner_name")}
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
            change="Added `model_load_ms`, `job_seconds`; `fingerprint`, `measured_at` optional.",
            why="A job's clock is only known at its end, so the row arrives in two halves.",
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
            "distribution countable without matching model-name strings by hand. "
            "Absent on the half a job writes at its end, which carries the clock and "
            "repeats nothing the probe already recorded."
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
        description=(
            "When the probe read this machine. Absent on the half a job writes at its "
            "end, which measured no machine."
        ),
    )

    model_load_ms: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the server spent opening the weights before the first item. "
            "Once per job, which is this row's grain."
        ),
    )
    job_seconds: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The job's own wall clock. The truncation cap reverts on the slowest work "
            "job's, and before this cell the only place that number lived was the "
            "GitHub jobs API, which drops a job record when the run ages out."
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
            forbidden.update(_CLOCK_FIELDS)
            if data.get("fingerprint") is None or data.get("measured_at") is None:
                raise ValueError("pre-clock schemas require fingerprint and measured_at")
        if version < "2026-09-19":
            forbidden.update({"server_prompt_tokens", "server_prompt_seconds"})
        if version == "2026-09-16" and data.get("job", WORK_JOB) != WORK_JOB:
            raise ValueError("the initial host schema only records work jobs")
        if forbidden.intersection(data):
            raise ValueError("input carries fields not declared by its historical schema")
        return data

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


def _fingerprint_bytes(cells: Mapping[str, object], keys: tuple[str, ...]) -> bytes:
    return json.dumps(
        {key: cells.get(key) for key in keys},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


class HostFingerprintRow(Contract):
    """One normalized host row with corrected CPU meanings and versioned identity."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    __schema_stem__: ClassVar[str] = "host-fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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
            change="`memcpy_probe_mib` records the derived probe buffer.",
            why="The configured floor is not the size actually measured.",
        ),
        ChangelogEntry(
            version="2026-09-19",
            change="Earlier changes are in this contract's git history.",
            why="Git is the archive for older shape changes.",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Earlier changes are in this contract's git history.",
            why="Git is the archive for older shape changes.",
        ),
    )

    date: DateStamp
    run_id: RunId
    job: ServerJob | JobName | None = Field(default=WORK_JOB)
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
    model_load_ms: float | None = Field(default=None, ge=0)
    job_seconds: int | None = Field(default=None, ge=0)
    server_prompt_tokens: int | None = Field(default=None, ge=0)
    server_prompt_seconds: float | None = Field(default=None, ge=0)

    def __init__(
        self,
        *,
        cores: int | _Unset | None = _UNSET,
        threads: int | _Unset | None = _UNSET,
        mhz_max: float | _Unset | None = _UNSET,
        mhz_at_probe: float | _Unset | None = _UNSET,
        **data: Any,
    ) -> None:
        """Keep the exact legacy keyword constructor available to the unchanged collector."""
        for name, value in (
            ("cores", cores),
            ("threads", threads),
            ("mhz_max", mhz_max),
            ("mhz_at_probe", mhz_at_probe),
        ):
            if value is not _UNSET:
                data[name] = value
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _normalize_before_stamping(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        probe_keys = set(LegacyHostFingerprintRow.model_fields) - {"version"} - _CLOCK_FIELDS
        if "version" not in payload and set(payload) == probe_keys:
            return normalize_host_row(payload).model_dump()
        if payload.get("version") in LEGACY_HOST_VERSIONS:
            return normalize_host_row(payload).model_dump()
        if payload.get("version") in HOST_FINGERPRINT_READ_VERSIONS:
            return _check_numbers(payload, cls)
        if LEGACY_CPU_FIELDS.intersection(payload):
            raise ValueError(
                "legacy CPU fields require a declared legacy or exact constructor shape"
            )
        return _check_numbers(payload, cls)

    @model_validator(mode="after")
    def _consistent_measurements(self) -> Self:
        if (self.pipeline_name is None) != (self.task_name is None):
            raise ValueError("host row requires both pipeline_name and task_name")
        if self.task_name is None and self.job is None:
            raise ValueError("host row requires a legacy job or pipeline and task")
        if self.task_name is not None and self.job not in (None, self.task_name):
            raise ValueError("generic host row job must be absent or match task_name")
        for name in ("measured_at", "cpu_target_measured_at"):
            value = getattr(self, name)
            if value is not None:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        if self.version not in HOST_FINGERPRINT_READ_VERSIONS:
            raise ValueError("normalized host row has an unsupported schema version")
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
            if datetime.fromisoformat(self.cpu_target_measured_at) < datetime.fromisoformat(
                self.measured_at
            ):
                raise ValueError("target capture cannot precede the original machine probe")
        return self

    @property
    def mhz_at_probe(self) -> float | None:
        """Temporary read-only compatibility for the unchanged Python collector's log."""
        return self.cpu_observed_mhz

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
        payload["flags"] = row["flags"]
        for name, field in model.model_fields.items():
            if field.default is None and payload.get(name) == "":
                payload[name] = None
        if legacy:
            payload = LegacyHostFingerprintRow.model_validate(payload).model_dump()
        else:
            for name in _CORRECTED_INT_FIELDS:
                if payload.get(name) not in (None, ""):
                    payload[name] = int(payload[name])
            for name in _CORRECTED_FLOAT_FIELDS:
                if payload.get(name) not in (None, ""):
                    payload[name] = float(payload[name])
        return cls.model_validate(payload)


def fingerprint_v2(row: HostFingerprintRow) -> str | None:
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
    """Normalize only finite declared legacy shapes or the exact old probe constructor."""
    payload = dict(data)
    if "version" not in payload:
        probe_keys = set(LegacyHostFingerprintRow.model_fields) - {"version"} - _CLOCK_FIELDS
        if set(payload) != probe_keys:
            raise ValueError("unstamped input is not an unchanged silicon constructor shape")
        payload["version"] = LEGACY_HOST_VERSIONS[-1]
    if payload["version"] in HOST_FINGERPRINT_READ_VERSIONS:
        return HostFingerprintRow.model_validate(payload)
    if payload["version"] not in LEGACY_HOST_VERSIONS:
        raise ValueError("unrecognized host row schema version")
    old = LegacyHostFingerprintRow.model_validate(_check_numbers(payload, LegacyHostFingerprintRow))
    cells = old.model_dump()
    average = cells.pop("mhz_at_probe")
    for key in LEGACY_CPU_FIELDS - {"mhz_at_probe"}:
        cells.pop(key)
    cells.update(
        version=HOST_FINGERPRINT_VERSION,
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
        forbidden.update(_CLOCK_FIELDS)
    if version < "2026-09-19":
        forbidden.update({"server_prompt_tokens", "server_prompt_seconds"})
    return {
        key: value
        for key, value in payload.items()
        if key not in forbidden or value is not None
    }
