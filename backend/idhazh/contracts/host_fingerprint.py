"""What silicon a job drew, as the host itself reported it.

One row a job. The columns are fixed for the length of that job - a processor
does not change model number mid-run - which is why they are not repeated on
every item row beside the readings that do move.

**Only `job` is an enum, and that is deliberate.** It is the one column this
project names; every other identifier here is a string the machine chose. A
vendor renames a part, a cloud adds a machine size, a microcode revision ships -
and a closed set would refuse the row rather than record the new thing, which is
the opposite of what an instrument is for. The rule and its cost are written
down in `docs/reference/host-metrics.md`.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    FingerprintId,
    RunId,
    Timestamp,
)
from idhazh.contracts.runtime_counters import WORK_JOB, ServerJob

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


class HostFingerprintRow(Contract):
    """One job, one machine, one row: what the host said it was."""

    __schema_stem__: ClassVar[str] = "host-fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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

    fingerprint: FingerprintId = Field(
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
            "L3 as the host reports it. Read beside `memcpy_probe_mib`: a probe "
            "buffer smaller than this measured cache rather than memory."
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
            "The buffer each side of the copy used. Below `l3_cache_bytes` the figure "
            "is a cache reading."
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
    measured_at: Timestamp

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
        """The inverse. An empty cell is an absent reading, never a zero."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time."""
        return tuple(name for name, field in cls.model_fields.items() if field.default is None)
