"""What bounded, expiring evidence can an isolated host comparison prove?"""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    RelPath,
    Sha256,
    Timestamp,
)
from idhazh.contracts.host_events import (
    FiniteNonnegative,
    HostSessionManifest,
    HostWindowCells,
    PositiveCount,
    ProcessTarget,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow

EVIDENCE_VERSION = "2026-10-11"
Scalar = int | float | str | None


_CHANGELOG = (
    ChangelogEntry(
        version=EVIDENCE_VERSION,
        change="Declare isolated workload, frozen bounds and exact-byte comparison evidence.",
        why="A later readiness review must distinguish measurements from adoption authority.",
    ),
)


class EvidenceRoots(Model):
    reference: RelPath
    native: RelPath
    generated_state: RelPath
    corpus: RelPath
    frontend: RelPath


class FieldBound(Model):
    field: str
    absolute: FiniteNonnegative
    observed_reference_spread: FiniteNonnegative


class WorkloadRequest(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-workload-request"
    sequence: PositiveCount
    mode: Literal["reference", "native_only", "stop"]


class WorkloadResult(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-workload-result"
    sequence: PositiveCount
    mode: Literal["reference", "native_only"]
    target: ProcessTarget
    wall_seconds: FiniteNonnegative
    cpu_seconds: FiniteNonnegative
    digest: Sha256
    iterations: PositiveCount
    samples: PositiveCount
    cells: HostWindowCells | None
    host: HostFingerprintRow | None
    population: tuple[ProcessTarget, ...]
    reference_files: tuple[RelPath, ...]


class EvidenceSession(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-evidence-session"
    created_at: Timestamp
    manifest: HostSessionManifest
    roots: EvidenceRoots
    calibration: tuple[WorkloadResult, ...] = Field(min_length=2)
    bounds: tuple[FieldBound, ...]
    plain: WorkloadResult
    config_sha256: Sha256

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if any(row.target != self.manifest.cpu_target for row in (*self.calibration, self.plain)):
            raise ValueError("calibration must use the declared live worker")
        names = [bound.field for bound in self.bounds]
        if len(names) != len(set(names)):
            raise ValueError("duplicate frozen field bound")
        return self


class CommandMeasurement(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-command-measurement"
    command: tuple[str, ...]
    wall_seconds: FiniteNonnegative
    exit_code: Annotated[int, Field(strict=True)]
    executable_bytes: PositiveCount | None = None
    rustc: str
    git_sha: CommitSha


class EvidenceFile(Model):
    path: RelPath
    bytes: PositiveCount
    sha256: Sha256


class FieldComparison(Model):
    field: str
    classification: Literal["unchanged", "corrected", "context", "physical"]
    reference: Scalar
    native: Scalar
    absolute_bound: FiniteNonnegative
    passed: Annotated[bool, Field(strict=True)]


class GateEvidence(Model):
    file: EvidenceFile
    cases: PositiveCount
    names: tuple[str, ...] = Field(min_length=1)


class HostEvidenceReport(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-evidence-report"
    generated_at: Timestamp
    git_sha: CommitSha
    platform: Literal["linux"]
    runner: str
    toolchain: str
    config_sha256: Sha256
    session: EvidenceSession
    compile: CommandMeasurement
    startup_seconds: FiniteNonnegative
    monitor_cpu_seconds: FiniteNonnegative
    monitor_rss_bytes: PositiveCount
    ack_seconds: tuple[FiniteNonnegative, ...] = Field(min_length=4)
    paired: tuple[WorkloadResult, ...] = Field(min_length=2)
    native_population: tuple[ProcessTarget, ...]
    population_reference_only: tuple[ProcessTarget, ...]
    population_native_only: tuple[ProcessTarget, ...]
    native_sample_count: PositiveCount
    comparisons: tuple[FieldComparison, ...] = Field(min_length=1)
    files: tuple[EvidenceFile, ...] = Field(min_length=1)
    gates: GateEvidence
    candidate_reader: Literal["idhazh.telemetry.host_output_verify.verify_host_output"]
    shared_reader: Literal["expected_rejection_before_reader_migration"]
    correctness: Literal["passed", "failed"]
    adoption_authorized: Literal[False] = False
    historical_readiness: Literal["blocked"] = "blocked"

    @model_validator(mode="after")
    def _truthful_verdict(self) -> Self:
        passed = all(row.passed for row in self.comparisons)
        if passed != (self.correctness == "passed"):
            raise ValueError("correctness must match every comparison")
        if self.compile.exit_code != 0 or self.compile.executable_bytes is None:
            raise ValueError("a successful native build and executable size are required")
        return self
