"""Which typed messages and declared inputs belong to one host instrument session?"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    ItemId,
    Model,
    RelPath,
    RunId,
    ServerJob,
    Timestamp,
)
from idhazh.contracts.host_output import (
    INT64_MAX,
    CorrectedHostFingerprintRow,
    HostWriteCompletion,
    HostWritePlan,
)

HOST_EVENT_VERSION: Final = "2026-10-10"
Count = Annotated[int, Field(strict=True, ge=0, le=INT64_MAX)]
PositiveCount = Annotated[int, Field(strict=True, ge=1, le=INT64_MAX)]
FiniteNonnegative = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
FinitePositive = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Token = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.-]*$", max_length=128)]
_CHANGELOG: Final = (
    ChangelogEntry(
        version=HOST_EVENT_VERSION,
        change="Declare bounded host sessions, lifecycle messages and typed observations.",
        why="Serialized exchanges keep instruments separate from output and health writers.",
    ),
)


class ExchangeModel(Model):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def _real_utc_dates(self) -> Self:
        for name in type(self).model_fields:
            value = getattr(self, name)
            if not isinstance(value, str):
                continue
            if name == "date":
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError("date must be a real canonical UTC day")
            elif name in {"ts", "emitted_at", "captured_at", "opened_at", "closed_at"}:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self


class ProcessTarget(ExchangeModel):
    pid: PositiveCount
    start_ticks: Count


class HostEventLimits(ExchangeModel):
    """Required transport knobs; the experiment config supplies their values."""

    max_manifest_bytes: PositiveCount
    max_command_bytes: PositiveCount
    max_result_bytes: PositiveCount
    max_files: PositiveCount
    max_session_events: PositiveCount
    max_session_bytes: PositiveCount
    max_read_bytes: PositiveCount
    max_reads: PositiveCount
    max_workers: PositiveCount
    max_windows: PositiveCount
    max_concurrent_windows: PositiveCount
    retry_window_ms: PositiveCount
    poll_ms: PositiveCount
    readiness_timeout_ms: PositiveCount
    ack_timeout_ms: PositiveCount
    drain_timeout_ms: PositiveCount

    @model_validator(mode="after")
    def _consistent_caps(self) -> Self:
        if self.max_concurrent_windows > self.max_windows:
            raise ValueError("concurrency exceeds the window cap")
        if max(self.max_command_bytes, self.max_result_bytes) > self.max_session_bytes:
            raise ValueError("individual event cap exceeds total session bytes")
        return self


class HostCaptureLimits(ExchangeModel):
    max_proc_text_bytes: PositiveCount
    max_sysfs_text_bytes: PositiveCount
    max_cpu_id: Count
    max_cpu_ids: PositiveCount
    max_cgroup_ancestors: PositiveCount
    max_mount_entries: PositiveCount
    max_processes: PositiveCount
    max_log_bytes: PositiveCount
    max_snapshot_retries: Annotated[int, Field(strict=True, ge=0, le=1)]


class CollectionControls(ExchangeModel):
    memory_profiling_enabled: Annotated[bool, Field(strict=True)] = True
    resource_interval_seconds: FiniteNonnegative
    job_sample_interval_seconds: FinitePositive
    memcpy_enabled: Annotated[bool, Field(strict=True)]
    memcpy_probe_mib: PositiveCount
    memcpy_passes: PositiveCount


class CaptureSource(StrEnum):
    ONLINE = "sysfs.online"
    TOPOLOGY = "sysfs.topology"
    CPUINFO = "proc.cpuinfo"
    CPUFREQ = "sysfs.cpufreq"
    AFFINITY = "sched.affinity"
    CPUSET = "cgroup.cpuset"
    QUOTA = "cgroup.cpu_quota"
    CPU_STAT = "proc.stat"
    LOAD = "proc.loadavg"
    SERVER_MEMORY = "proc.server_status"
    WORKER_MEMORY = "proc.worker_status"
    MACHINE_MEMORY = "proc.meminfo"
    MAJOR_FAULTS = "proc.major_faults"
    JOB_MEMORY = "proc.python_population"
    CLOCK_LOG = "clock.log"
    BOOT_ID = "proc.boot_id"


class UnavailableReason(StrEnum):
    MISSING = "missing"
    MALFORMED = "malformed"
    PERMISSION_DENIED = "permission_denied"
    PID_EXITED = "pid_exited"
    PID_REUSED = "pid_reused"
    DISABLED = "disabled"
    TIMED_OUT = "timed_out"
    SNAPSHOT_CHANGED = "snapshot_changed"
    INCOMPLETE_COVERAGE = "incomplete_coverage"


class UnavailableDiagnostic(ExchangeModel):
    source: CaptureSource
    reason: UnavailableReason


class NamedHostInput(ExchangeModel):
    name: Token
    source: CaptureSource
    relative_path: RelPath


class ExpectedWorker(ExchangeModel):
    emitter_id: Token
    target: ProcessTarget
    server: ProcessTarget | None = None


class ExpectedWindow(ExchangeModel):
    window_id: UUID
    item_id: ItemId
    emitter_id: Token


class HostSessionManifest(ExchangeModel, Contract):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    __schema_stem__: ClassVar[str] = "host-session-manifest"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG

    version: Literal["2026-10-10"]
    date: DateStamp
    run_id: RunId
    attempt: PositiveCount
    job: ServerJob
    shard: Count
    git_sha: CommitSha
    session_id: UUID
    operator_emitter_id: Token
    monitor_emitter_id: Token
    boot_id: UUID
    event_root: RelPath
    output_roots: tuple[RelPath, ...] = Field(min_length=1)
    named_inputs: tuple[NamedHostInput, ...]
    workers: tuple[ExpectedWorker, ...]
    windows: tuple[ExpectedWindow, ...]
    cpu_target: ProcessTarget | None = None
    cpu_target_role: Literal["model_server", "python_worker", "unselected"]
    controls: CollectionControls
    limits: HostEventLimits
    capture_limits: HostCaptureLimits

    @model_validator(mode="after")
    def _declared_session(self) -> Self:
        expected_root = (
            f"backend/var/host-events/{self.run_id}/{self.attempt}/{self.job.value}/"
            f"{self.shard}/{self.session_id}"
        )
        if self.event_root != expected_root:
            raise ValueError("event_root does not name the declared session")
        if len(self.workers) > self.limits.max_workers:
            raise ValueError("declared workers exceed max_workers")
        if len(self.windows) > self.limits.max_windows:
            raise ValueError("declared windows exceed max_windows")
        worker_ids = [worker.emitter_id for worker in self.workers]
        emitters = [self.operator_emitter_id, self.monitor_emitter_id, *worker_ids]
        if len(emitters) != len(set(emitters)):
            raise ValueError("emitter IDs must be distinct")
        window_ids = [window.window_id for window in self.windows]
        if len(window_ids) != len(set(window_ids)):
            raise ValueError("duplicate window identity")
        if any(window.emitter_id not in worker_ids for window in self.windows):
            raise ValueError("window belongs to an undeclared worker")
        for values in (
            [entry.name for entry in self.named_inputs],
            [entry.relative_path for entry in self.named_inputs],
            list(self.output_roots),
        ):
            if len(values) != len(set(values)):
                raise ValueError("duplicate named input or output root")
        if (self.cpu_target is None) != (self.cpu_target_role == "unselected"):
            raise ValueError("CPU target role contradicts the target")
        candidates = (
            [worker.server for worker in self.workers]
            if self.cpu_target_role == "model_server"
            else [worker.target for worker in self.workers]
        )
        if self.cpu_target is not None and self.cpu_target not in candidates:
            raise ValueError("CPU target is not a declared selected server or Python worker")
        servers = {worker.server for worker in self.workers if worker.server is not None}
        if len(servers) > 1:
            raise ValueError("workers disagree on the shard's selected model server")
        if servers and self.cpu_target_role == "python_worker":
            raise ValueError("a server job must select its model server as the CPU target")
        return self

    @property
    def pending_event_limit(self) -> int:
        """J4's four worker slots, declared active-window allowance and eight lifecycle slots."""
        return 4 * len(self.workers) + self.limits.max_concurrent_windows + 8


class SourceCoverage(ExchangeModel):
    source: CaptureSource
    status: Literal["complete", "partial", "unavailable"]
    expected: Count
    observed: Count
    reason: UnavailableReason | None = None

    @model_validator(mode="after")
    def _coverage(self) -> Self:
        if self.observed > self.expected:
            raise ValueError("observed coverage exceeds expected coverage")
        if self.status == "complete":
            if self.observed != self.expected or self.reason is not None:
                raise ValueError("complete coverage needs every expected input and no reason")
        elif self.reason is None:
            raise ValueError("unavailable or partial coverage needs a typed reason")
        if self.status == "unavailable" and self.observed != 0:
            raise ValueError("unavailable coverage cannot contain successful observations")
        return self


class CpuDiagnostics(ExchangeModel):
    online_cpu_ids: tuple[Count, ...]
    sources: tuple[SourceCoverage, ...]
    target: ProcessTarget | None = None

    @model_validator(mode="after")
    def _unique_sources(self) -> Self:
        if tuple(sorted(set(self.online_cpu_ids))) != self.online_cpu_ids:
            raise ValueError("online CPU IDs must be ordered and unique")
        names = [source.source for source in self.sources]
        allowed = {
            CaptureSource.ONLINE,
            CaptureSource.TOPOLOGY,
            CaptureSource.CPUINFO,
            CaptureSource.CPUFREQ,
            CaptureSource.AFFINITY,
            CaptureSource.CPUSET,
            CaptureSource.QUOTA,
        }
        if len(names) != len(set(names)) or set(names) != allowed:
            raise ValueError("CPU diagnostics require each of the seven declared sources once")
        if any(source.reason is UnavailableReason.DISABLED for source in self.sources):
            raise ValueError("the memory switch cannot disable CPU sources")
        return self


class HostWindowCells(ExchangeModel):
    """The exact cells returned by HostCells.cells and accepted by ItemHealthRow."""

    cpu_busy_pct: Annotated[float, Field(strict=True, ge=0, le=100)] | None = None
    cpu_busy_max: Annotated[float, Field(strict=True, ge=0, le=100)] | None = None
    cpu_busy_min: Annotated[float, Field(strict=True, ge=0, le=100)] | None = None
    cpu_steal_pct: Annotated[float, Field(strict=True, ge=0, le=100)] | None = None
    load_1m: FiniteNonnegative | None = None
    llama_rss_bytes: Count | None = None
    llama_rss_anon_bytes: Count | None = None
    llama_rss_peak_bytes: Count | None = None
    llama_major_faults: Count | None = None
    python_rss_bytes: Count | None = None
    python_rss_anon_bytes: Count | None = None
    os_mem_available_bytes: Count | None = None
    os_mem_total_bytes: Count | None = None
    os_mem_cached_bytes: Count | None = None
    os_swap_free_bytes: Count | None = None
    os_swap_total_bytes: Count | None = None
    os_mem_available_min_bytes: Count | None = None


WINDOW_CELL_SOURCES: Final = {
    **dict.fromkeys(
        ("cpu_busy_pct", "cpu_busy_max", "cpu_busy_min", "cpu_steal_pct"),
        CaptureSource.CPU_STAT,
    ),
    "load_1m": CaptureSource.LOAD,
    **dict.fromkeys(
        ("llama_rss_bytes", "llama_rss_anon_bytes", "llama_rss_peak_bytes"),
        CaptureSource.SERVER_MEMORY,
    ),
    "llama_major_faults": CaptureSource.MAJOR_FAULTS,
    **dict.fromkeys(("python_rss_bytes", "python_rss_anon_bytes"), CaptureSource.WORKER_MEMORY),
    **dict.fromkeys(
        (
            "os_mem_available_bytes",
            "os_mem_total_bytes",
            "os_mem_cached_bytes",
            "os_swap_free_bytes",
            "os_swap_total_bytes",
            "os_mem_available_min_bytes",
        ),
        CaptureSource.MACHINE_MEMORY,
    ),
}
MEMORY_SOURCES: Final = frozenset(
    {
        CaptureSource.SERVER_MEMORY,
        CaptureSource.WORKER_MEMORY,
        CaptureSource.MACHINE_MEMORY,
        CaptureSource.MAJOR_FAULTS,
        CaptureSource.JOB_MEMORY,
    }
)


class LegacyJobSample(ExchangeModel):
    """rss-samples.jsonl records, without event-envelope fields; kB stays kB."""

    ts: Timestamp
    llama_vmrss_kb: Count | None
    llama_vmhwm_kb: Count | None
    python_vmrss_kb: Count
    python_procs: Count
    python_vmhwm_kb: Count
    mem_total_kb: Count | None
    mem_available_kb: Count | None
    committed_as_kb: Count | None
    cgroup_current_bytes: Count | None


class LegacyProcessRollcall(ExchangeModel):
    """python-procs.jsonl records; args remains the sampler's three argv fields."""

    ts: Timestamp
    pid: PositiveCount
    comm: str
    vmrss_kb: Count
    vmhwm_kb: Count | None
    exe: str | None
    args: str | None


LEGACY_JOB_SAMPLE_FILENAME: Final = "rss-samples.jsonl"
LEGACY_PROCESS_ROLLCALL_FILENAME: Final = "python-procs.jsonl"


class MonitorReadyBody(ExchangeModel):
    boot_id: UUID
    supported_version: Literal["2026-10-10"]


class HostCommandBody(ExchangeModel):
    controls: CollectionControls
    input_names: tuple[Token, ...]
    target: ProcessTarget | None = None
    previous_result_id: UUID | None = None

    @model_validator(mode="after")
    def _unique_inputs(self) -> Self:
        if len(self.input_names) != len(set(self.input_names)):
            raise ValueError("duplicate captured input name")
        return self


class WorkerBody(ExchangeModel):
    target: ProcessTarget
    server: ProcessTarget | None = None
    memory_profiling_enabled: Annotated[bool, Field(strict=True)] = True


class WindowBody(ExchangeModel):
    window_id: UUID
    item_id: ItemId
    target: ProcessTarget
    server: ProcessTarget | None = None


class WindowBegunBody(WindowBody):
    captured_at: Timestamp


class WindowAbortBody(WindowBody):
    reason: Literal["cancelled", "work_failed", "instrument_failed"]


class WindowResultBody(WindowBody):
    status: Literal["complete", "incomplete"]
    opened_at: Timestamp | None
    closed_at: Timestamp | None
    memory_profiling_enabled: Annotated[bool, Field(strict=True)] = True
    cells: HostWindowCells
    unavailable: tuple[UnavailableDiagnostic, ...]

    @model_validator(mode="after")
    def _endpoints_and_cells(self) -> Self:
        diagnostics = {entry.source: entry.reason for entry in self.unavailable}
        if len(diagnostics) != len(self.unavailable):
            raise ValueError("duplicate unavailable source")
        if not set(diagnostics) <= set(WINDOW_CELL_SOURCES.values()):
            raise ValueError("unavailable source is not a window instrument")
        if self.status == "complete" and (self.opened_at is None or self.closed_at is None):
            raise ValueError("complete windows require both captured endpoints")
        if self.opened_at and self.closed_at and self.closed_at < self.opened_at:
            raise ValueError("closing snapshot precedes opening snapshot")
        if self.opened_at is None or self.closed_at is None:
            if any(value is not None for value in self.cells.model_dump().values()):
                raise ValueError("a window without both endpoints must have null cells")
        for name, source in WINDOW_CELL_SOURCES.items():
            value = getattr(self.cells, name)
            if value is None and source not in diagnostics:
                raise ValueError(f"null {name} requires a typed unavailable reason")
            if not self.memory_profiling_enabled and source in MEMORY_SOURCES:
                if value is not None or diagnostics.get(source) is not UnavailableReason.DISABLED:
                    raise ValueError("memory off requires null memory/fault cells and disabled")
        if self.memory_profiling_enabled and UnavailableReason.DISABLED in diagnostics.values():
            raise ValueError("enabled instruments cannot claim disabled")
        return self


class HostResultBody(ExchangeModel):
    row: CorrectedHostFingerprintRow
    cpu: CpuDiagnostics
    completion_event_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _source_measurements(self) -> Self:
        if len(self.completion_event_ids) != len(set(self.completion_event_ids)):
            raise ValueError("duplicate completion reference")
        sources = {entry.source: entry for entry in self.cpu.sources}
        logical = self.row.cpu_logical_processors
        if logical is not None:
            online = sources.get(CaptureSource.ONLINE)
            if (
                online is None
                or online.status != "complete"
                or logical != len(self.cpu.online_cpu_ids)
                or online.observed != logical
            ):
                raise ValueError("logical count requires matching complete online evidence")
        for name, source in (
            ("cpu_logical_processors", CaptureSource.ONLINE),
            ("cpu_physical_cores", CaptureSource.TOPOLOGY),
            ("cpu_observed_mhz", CaptureSource.CPUINFO),
            ("cpu_reported_max_mhz", CaptureSource.CPUFREQ),
            ("cpu_allowed_processors", CaptureSource.AFFINITY),
        ):
            evidence = sources[source]
            if getattr(self.row, name) is None and evidence.status == "complete":
                raise ValueError(f"null {name} requires unavailable source diagnostics")
        for source in (CaptureSource.TOPOLOGY, CaptureSource.CPUINFO, CaptureSource.CPUFREQ):
            if sources[source].expected != len(self.cpu.online_cpu_ids):
                raise ValueError("CPU coverage must name the original online inventory size")
        for name, source in (
            ("cpu_physical_cores", CaptureSource.TOPOLOGY),
            ("cpu_reported_max_mhz", CaptureSource.CPUFREQ),
            ("cpu_allowed_processors", CaptureSource.AFFINITY),
        ):
            if getattr(self.row, name) is not None:
                evidence = sources[source]
                if evidence.status != "complete":
                    raise ValueError(f"{name} requires complete source coverage")
        if self.row.cpu_allowed_processors is not None:
            cpuset = sources.get(CaptureSource.CPUSET)
            if cpuset is None or cpuset.status != "complete":
                raise ValueError("allowed count requires complete effective cpuset evidence")
        if self.row.cpu_observed_mhz is not None:
            evidence = sources[CaptureSource.CPUINFO]
            if evidence.observed == 0 or evidence.status == "unavailable":
                raise ValueError("observed MHz requires successful CPU frequency observations")
        if (self.row.cpu_target_measured_at is None) != (self.cpu.target is None):
            raise ValueError("target capture requires the captured PID/start ticks")
        if self.row.cpu_quota_state in ("finite", "unlimited"):
            quota = sources.get(CaptureSource.QUOTA)
            if quota is None or quota.status != "complete":
                raise ValueError("finite/unlimited quota requires complete ancestor evidence")
        elif sources[CaptureSource.QUOTA].status == "complete":
            raise ValueError("unmeasured/unavailable quota requires an unavailable diagnostic")
        return self


class StopBody(ExchangeModel):
    reason: Literal["completed", "cancelled", "failed"]


class StoppedBody(ExchangeModel):
    drained: Literal[True]
    aborted_window_ids: tuple[UUID, ...]

    @model_validator(mode="after")
    def _unique_windows(self) -> Self:
        if len(self.aborted_window_ids) != len(set(self.aborted_window_ids)):
            raise ValueError("stopped result repeats an aborted window")
        return self

    @model_validator(mode="before")
    @classmethod
    def _strict_drained(cls, data: Any) -> Any:
        if isinstance(data, dict) and type(data.get("drained")) is not bool:
            raise ValueError("drained must be a Boolean")
        return data


class InstrumentSkippedBody(ExchangeModel):
    command_kind: Literal["host.probe", "host.target", "host.clock"]
    unavailable: tuple[UnavailableDiagnostic, ...] = Field(min_length=1)
    completion_event_ids: tuple[UUID, ...] = ()


class ProtocolFaultCode(StrEnum):
    IDENTITY = "identity_conflict"
    DUPLICATE = "duplicate_conflict"
    ORDER = "sequence_order"
    STATE = "invalid_state"
    TARGET = "target_conflict"
    BOUNDS = "limit_exhausted"
    RETIRED = "retired_event"
    STORE = "store_failure"


class ProtocolFaultBody(ExchangeModel):
    code: ProtocolFaultCode
    related_event_id: UUID | None


class JobSampleBody(ExchangeModel):
    record: LegacyJobSample


class ProcessRollcallBody(ExchangeModel):
    records: tuple[LegacyProcessRollcall, ...]

    @model_validator(mode="after")
    def _one_capture(self) -> Self:
        if len({record.ts for record in self.records}) > 1:
            raise ValueError("a process rollcall must come from one capture")
        if len({record.pid for record in self.records}) != len(self.records):
            raise ValueError("a process rollcall cannot repeat a PID")
        return self


class WritePlanBody(ExchangeModel):
    plan: HostWritePlan


class WriteCompletedBody(ExchangeModel):
    completion: HostWriteCompletion


EventKind = Literal[
    "monitor.ready",
    "host.probe",
    "host.target",
    "host.clock",
    "host.result",
    "worker.register",
    "worker.registered",
    "window.begin",
    "window.begun",
    "window.end",
    "window.abort",
    "window.result",
    "monitor.stop",
    "monitor.stopped",
    "instrument.skipped",
    "protocol.fault",
    "host.write.plan",
    "host.write.completed",
    "job.sample",
    "process.rollcall",
]
COMMAND_KINDS: Final = frozenset(
    {
        "host.probe",
        "host.target",
        "host.clock",
        "worker.register",
        "window.begin",
        "window.end",
        "window.abort",
        "monitor.stop",
    }
)
_BODY_TYPES: Final[dict[str, type[ExchangeModel]]] = {
    "monitor.ready": MonitorReadyBody,
    "host.probe": HostCommandBody,
    "host.target": HostCommandBody,
    "host.clock": HostCommandBody,
    "host.result": HostResultBody,
    "worker.register": WorkerBody,
    "worker.registered": WorkerBody,
    "window.begin": WindowBody,
    "window.begun": WindowBegunBody,
    "window.end": WindowBody,
    "window.abort": WindowAbortBody,
    "window.result": WindowResultBody,
    "monitor.stop": StopBody,
    "monitor.stopped": StoppedBody,
    "instrument.skipped": InstrumentSkippedBody,
    "protocol.fault": ProtocolFaultBody,
    "host.write.plan": WritePlanBody,
    "host.write.completed": WriteCompletedBody,
    "job.sample": JobSampleBody,
    "process.rollcall": ProcessRollcallBody,
}


class HostEvent(ExchangeModel, Contract):
    """The kind selects exactly one closed body shape, including in JSON Schema."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    __schema_stem__: ClassVar[str] = "host-event"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG

    version: Literal["2026-10-10"]
    kind: EventKind
    event_id: UUID
    reply_to: UUID | None
    date: DateStamp
    run_id: RunId
    attempt: PositiveCount
    job: ServerJob
    shard: Count
    session_id: UUID
    emitter_id: Token
    sequence: PositiveCount
    emitted_at: Timestamp
    body: (
        MonitorReadyBody
        | HostCommandBody
        | HostResultBody
        | WorkerBody
        | WindowBody
        | WindowBegunBody
        | WindowAbortBody
        | WindowResultBody
        | StopBody
        | StoppedBody
        | InstrumentSkippedBody
        | ProtocolFaultBody
        | WritePlanBody
        | WriteCompletedBody
        | JobSampleBody
        | ProcessRollcallBody
    )

    @model_validator(mode="before")
    @classmethod
    def _discriminate_body(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("kind") in _BODY_TYPES:
            body_type = _BODY_TYPES[data["kind"]]
            body = data.get("body")
            if isinstance(body, Model):
                if type(body) is not body_type:
                    raise ValueError("event kind and body type disagree")
            else:
                body = body_type.model_validate(body)
            return {**data, "body": body}
        return data

    @model_validator(mode="after")
    def _body_and_reply(self) -> Self:
        if type(self.body) is not _BODY_TYPES[self.kind]:
            raise ValueError("event kind and body type disagree")
        unsolicited = {"monitor.ready", "job.sample", "process.rollcall"}
        if self.kind in COMMAND_KINDS | unsolicited:
            if self.reply_to is not None:
                raise ValueError("commands and unsolicited observations cannot be replies")
        elif self.kind != "protocol.fault" and self.reply_to is None:
            raise ValueError("results must name their triggering event")
        if isinstance(self.body, HostResultBody):
            if any(
                getattr(self.body.row, name) != getattr(self, name)
                for name in ("date", "run_id", "job", "shard")
            ):
                raise ValueError("host row identity contradicts its event")
        return self

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> dict[str, Any]:
        schema: dict[str, Any] = handler(core_schema)
        variants = []
        for kind, body_type in _BODY_TYPES.items():
            body_ref = handler.generate_json_schema.generate_inner(
                body_type.__pydantic_core_schema__
            )
            variants.append(
                {
                    "properties": {"kind": {"const": kind}, "body": body_ref},
                    "required": ["kind", "body"],
                }
            )
        schema["allOf"] = [{"oneOf": variants}]
        return schema
