"""What bounded, expiring evidence can an isolated host comparison prove?"""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self
from uuid import UUID

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
    Count,
    FiniteNonnegative,
    HostSessionManifest,
    HostWindowCells,
    LegacyJobSample,
    LegacyProcessRollcall,
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
    native_artifacts: RelPath
    generated_state: RelPath
    corpus: RelPath
    frontend: RelPath


class FieldBound(Model):
    field: str
    absolute: FiniteNonnegative
    observed_reference_spread: FiniteNonnegative


class FieldClassification(Model):
    field: str
    classification: Literal["unchanged", "corrected", "context", "physical"]


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
    clock_skew_seconds: FiniteNonnegative
    cpu_seconds: FiniteNonnegative
    instrument_wall_seconds: FiniteNonnegative
    instrument_cpu_seconds: FiniteNonnegative
    digest: Sha256
    iterations: PositiveCount
    samples: Count
    cells: HostWindowCells | None
    host: HostFingerprintRow | None
    population: tuple[ProcessTarget, ...]
    reference_files: tuple[RelPath, ...]


class ReferenceSample(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-reference-sample"
    record: LegacyJobSample
    population: tuple[ProcessTarget, ...]
    rollcall: tuple[LegacyProcessRollcall, ...]


class SamplerCompletion(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-reference-sampler-completion"
    samples: PositiveCount


class MonitorMeasurement(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-monitor-measurement"
    target: ProcessTarget
    cpu_seconds: FiniteNonnegative
    rss_bytes: PositiveCount | None
    startup_seconds: FiniteNonnegative | None


class CleanupEvidence(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-cleanup-evidence"
    targets: tuple[ProcessTarget, ...]
    stopped: Literal[True] = True


class PairedEvidence(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-paired-evidence"
    rows: tuple[WorkloadResult, ...] = Field(min_length=2)
    ack_seconds: tuple[FiniteNonnegative, ...] = Field(min_length=4)


class EvidenceSession(Contract):
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    __schema_stem__: ClassVar[str] = "host-evidence-session"
    created_at: Timestamp
    manifest: HostSessionManifest
    host_manifest: HostSessionManifest
    roots: EvidenceRoots
    calibration: tuple[WorkloadResult, ...] = Field(min_length=2)
    bounds: tuple[FieldBound, ...]
    plain: WorkloadResult
    config_sha256: Sha256
    field_classes: tuple[FieldClassification, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        shared = (
            "date",
            "run_id",
            "attempt",
            "job",
            "shard",
            "git_sha",
            "boot_id",
            "controls",
            "limits",
            "capture_limits",
            "cpu_target",
            "cpu_target_role",
            "workers",
            "output_roots",
        )
        if any(
            getattr(self.manifest, name) != getattr(self.host_manifest, name) for name in shared
        ):
            raise ValueError(
                "host and resource sessions must share the declared identity and target"
            )
        if (
            self.manifest.session_id == self.host_manifest.session_id
            or self.manifest.event_root == self.host_manifest.event_root
        ):
            raise ValueError("host and resource event sessions must be distinct")
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
    executable_sha256: Sha256 | None = None
    rustc: str
    git_sha: CommitSha


class EvidenceFile(Model):
    path: RelPath
    bytes: Count
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


class WindowSampleCoverage(Model):
    window_id: UUID
    samples: PositiveCount
    python_pids: tuple[PositiveCount, ...]


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
    monitor_rss_bytes: PositiveCount | None
    ack_seconds: tuple[FiniteNonnegative, ...] = Field(min_length=4)
    paired: tuple[WorkloadResult, ...] = Field(min_length=2)
    resource_event_ids: tuple[UUID, ...] = Field(min_length=1)
    native_population: tuple[PositiveCount, ...]
    population_reference_only: tuple[PositiveCount, ...]
    population_native_only: tuple[PositiveCount, ...]
    native_sample_count: PositiveCount
    window_sample_coverage: tuple[WindowSampleCoverage, ...] = Field(min_length=1)
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
        if (
            self.compile.exit_code != 0
            or self.compile.executable_bytes is None
            or self.compile.executable_sha256 is None
        ):
            raise ValueError("a successful native build and executable size are required")
        if len(self.resource_event_ids) != len(set(self.resource_event_ids)):
            raise ValueError("resource evidence cannot repeat event IDs")
        return self
