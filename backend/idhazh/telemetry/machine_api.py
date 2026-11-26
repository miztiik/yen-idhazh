"""Which closed measurements can a trusted caller file through Host Probes?"""

from __future__ import annotations

import json
import logging
import os
import sys
from asyncio import CancelledError
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from idhazh.contracts.base import DateStamp, Model, PipelineName, RelPath, RunId, Sha256, TaskName
from idhazh.contracts.file_envelope import UnitId, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.model_server_pin import ModelServerPin
from idhazh.contracts.task_performance import TaskPerformanceOutcome, TaskPerformanceRow
from idhazh.publication_paths import IntegrityError, relative, safe_file
from idhazh.telemetry.host import HostCells, process_start_ticks

ORIGIN_ENV = "IDHAZH_MACHINE_API_ORIGIN"
STATE_ROOT_ENV = "IDHAZH_MACHINE_API_STATE_ROOT"
_START = "/api/2026-11-05/start-task-profile"
_STOP = "/api/2026-11-05/stop-task-profile"
_ITEM_VERSION = "2026-11-26"
_START_ITEM = f"/api/{_ITEM_VERSION}/start-item-profile"
_STOP_ITEM = f"/api/{_ITEM_VERSION}/stop-item-profile"
RECORD_PATH = "/api/2026-11-26/record-task-performance"
FINGERPRINT_PATH = "/api/2026-11-05/capture-host-fingerprint"
PRODUCER = "host-probes"
LOG = logging.getLogger(__name__)


class RecordedFile(Model):
    """The native writer's receipt names a stored-row digest, not a byte hash."""

    path: RelPath
    file_id: UUID
    unit_id: UnitId
    covers: DateStamp
    content_sha256: Sha256
    row_count: Literal[1]


class Written(Model):
    status: Literal["written"]
    row: TaskPerformanceRow
    files: tuple[RecordedFile]


class NotWritten(Model):
    status: Literal["disabled", "skipped"]
    reason: Literal["configured_off", "ledger_not_active"]
    row: None
    files: tuple[()]


RESPONSE: TypeAdapter[Written | NotWritten] = TypeAdapter(
    Annotated[Written | NotWritten, Field(discriminator="status")]
)


class Captured(Model):
    status: Literal["written"]
    row: HostFingerprintRow
    files: tuple[RecordedFile]
    unavailable: dict[str, str]


class CaptureDisabled(Model):
    status: Literal["disabled"]
    row: None
    files: tuple[()]
    unavailable: dict[str, str]


_CAPTURE: TypeAdapter[Captured | CaptureDisabled] = TypeAdapter(
    Annotated[Captured | CaptureDisabled, Field(discriminator="status")]
)


class _Projection(BaseModel):
    """Select the closed summary fields, never the detailed samples or process pins."""

    model_config = ConfigDict(extra="ignore", strict=True)


class _Cpu(_Projection):
    user: float
    system: float
    steal: float


class _Observation[T](_Projection):
    value: T | None


class _WorkerCpu(_Projection):
    cpu_time_ms: float


class _Worker(_Projection):
    sampled_rss_max_kb: int | None
    cpu: _Observation[_WorkerCpu]


class _Processes(_Projection):
    worker: _Worker


class ProfileIdentity(Model):
    run_id: RunId
    pipeline_name: PipelineName
    task_name: TaskName


class _Started(_Projection):
    status: Literal["started"]
    handle: UUID


class _ItemStarted(_Started):
    version: Literal["2026-11-26"]


class _ItemProfile(_Projection):
    version: Literal["2026-11-26"]
    identity: ProfileIdentity
    outcome: TaskPerformanceOutcome
    end_reason: str
    cells: HostCells

    @field_validator("cells", mode="before")
    @classmethod
    def _exact_cells(cls, value: object) -> object:
        if not isinstance(value, dict) or value.keys() != HostCells.__dataclass_fields__.keys():
            raise ValueError("item profile must provide exactly the item host cells")
        return value


class _ItemStopped(_Projection):
    status: Literal["stopped"]
    handle: UUID
    end_reason: str
    profile: _ItemProfile


class _Profile(_Projection):
    identity: ProfileIdentity
    outcome: TaskPerformanceOutcome
    started_at: str
    finished_at: str
    elapsed_ms: float
    end_reason: str
    cpu: _Observation[_Cpu]
    machine_available_min_kb: int | None
    processes: _Processes


class _Stopped(_Projection):
    status: Literal["stopped"]
    handle: UUID
    end_reason: str
    profile: _Profile


class MachineApiError(RuntimeError):
    """A measurement command failed, without changing the measured task's outcome."""


@dataclass(slots=True)
class TaskClose:
    outcome: TaskPerformanceOutcome = "success"
    facts: dict[str, object] = field(default_factory=dict)


class MachineApi:
    def __init__(self, origin: str, *, timeout_ms: int, max_response_bytes: int) -> None:
        address = urlsplit(origin)
        port = address.port
        hostname = address.hostname
        if (
            address.scheme != "http" or hostname not in ("127.0.0.1", "::1") or not port
            or address.username or address.password or address.path or address.query
            or address.fragment or timeout_ms <= 0 or max_response_bytes <= 0
        ):
            raise MachineApiError("invalid owned machine listener settings")
        self.hostname = hostname
        self.port = port
        self.timeout = timeout_ms / 1000
        self.max_response_bytes = max_response_bytes

    @classmethod
    def for_job(cls) -> MachineApi | None:
        if origin := os.environ.get(ORIGIN_ENV):
            try:
                return cls(
                    origin, timeout_ms=int(os.environ["IDHAZH_MACHINE_API_TIMEOUT_MS"]),
                    max_response_bytes=int(os.environ["IDHAZH_MACHINE_API_MAX_RESPONSE_BYTES"]),
                )
            except (ValueError, KeyError) as error:
                raise MachineApiError("invalid owned machine listener settings") from error
        return None

    def _post(self, path: str, payload: Mapping[str, object]) -> bytes:
        conn = HTTPConnection(self.hostname, self.port, timeout=self.timeout)
        try:
            conn.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
            with conn.getresponse() as response:
                if response.status != 200:
                    operation = path.rsplit("/", 1)[-1]
                    # Native errors are bounded; their status is sufficient here.
                    raise MachineApiError(f"{operation} returned HTTP {response.status}")
                data = response.read(self.max_response_bytes + 1)
        except (OSError, HTTPException) as error:
            raise MachineApiError(f"{path.rsplit('/', 1)[-1]} could not complete") from error
        finally:
            conn.close()
        if len(data) > self.max_response_bytes:
            raise MachineApiError("machine response exceeded its byte bound")
        return data

    def _opening(self, identity: ProfileIdentity) -> dict[str, object]:
        pid = os.getpid()
        ticks = process_start_ticks(pid)
        if ticks is None:
            raise MachineApiError("task process pin unavailable")
        return {
            "identity": identity.model_dump(mode="json"),
            "target": {"pid": pid, "start_ticks": str(ticks)},
        }

    def start(self, identity: ProfileIdentity) -> UUID:
        return _Started.model_validate_json(self._post(_START, self._opening(identity))).handle

    def start_item_window(
        self, identity: ProfileIdentity, *, heartbeat_seconds: int, server: ModelServerPin | None,
        memory_profiling_enabled: bool,
    ) -> UUID:
        opening = self._opening(identity)
        opening["waiting_heartbeat_seconds"] = heartbeat_seconds
        if not memory_profiling_enabled:
            opening["memory_profiling_enabled"] = False
        if server is not None:
            opening["server"] = {"pid": server.pid, "start_ticks": str(server.start_ticks)}
        return _ItemStarted.model_validate_json(self._post(_START_ITEM, opening)).handle

    def stop_item_window(
        self, handle: UUID, identity: ProfileIdentity, outcome: TaskPerformanceOutcome,
    ) -> HostCells:
        stopped = _ItemStopped.model_validate_json(
            self._post(_STOP_ITEM, {"handle": str(handle), "outcome": outcome}),
        )
        _verify_close(stopped, handle, identity, outcome)
        return stopped.profile.cells

    def stop(
        self, handle: UUID, identity: ProfileIdentity,
        outcome: TaskPerformanceOutcome,
    ) -> dict[str, object]:
        return closed_measurement(
            self._post(_STOP, {"handle": str(handle), "outcome": outcome}),
            handle=handle, identity=identity, outcome=outcome,
        )

    def record(
        self, *, date: str, identity: WriterIdentity,
        measurement: Mapping[str, object],
    ) -> Written | NotWritten:
        request = record_request(date=date, identity=identity, measurement=measurement)
        return RESPONSE.validate_json(self._post(RECORD_PATH, request))

    def fingerprint(self, date: str, identity: WriterIdentity) -> Captured | CaptureDisabled:
        return _CAPTURE.validate_json(self._post(FINGERPRINT_PATH, {
            "date": date, "writer": identity.model_dump(mode="json"),
        }))

    @contextmanager
    def profile(
        self, identity: ProfileIdentity, retain: Callable[[Mapping[str, object]], None],
    ) -> Iterator[TaskClose]:
        handle = None
        try:
            handle = self.start(identity)
        except (ValueError, MachineApiError) as error:
            unavailable(identity.task_name, "start", error)
        result = TaskClose()
        try:
            yield result
        except (CancelledError, KeyboardInterrupt):
            result.outcome = "cancelled"
            raise
        except SystemExit as error:
            if error.code not in (None, 0):
                result.outcome = "error"
            raise
        except BaseException:
            result.outcome = "error"
            raise
        finally:
            if handle is not None:
                try:
                    retain({**self.stop(handle, identity, result.outcome), **result.facts})
                except (OSError, ValueError, MachineApiError) as error:
                    unavailable(identity.task_name, "close", error)


def unavailable(task: str, stage: str, error: Exception) -> None:
    detail = str(error) if isinstance(error, MachineApiError) else type(error).__name__
    warn(f"{stage} unavailable for {task}: {detail}")


def warn(message: str) -> None:
    """Report trusted instrument status even when the caller omits unstructured logs."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=Task Performance::{message}", file=sys.stderr)
    else:
        LOG.warning("Task Performance: %s", message)


def private_state(repo: Path) -> Path:
    root = relative(os.environ[STATE_ROOT_ENV])
    parts = root.split("/")
    if (
        len(parts) != 4 or parts[:2] != ["backend", "var"]
        or not parts[2].startswith("machine-task-") or parts[3] != "state"
    ):
        raise IntegrityError("machine recording state is not job private")
    safe_file(repo, f"{root}/.machine-output", exists=False)
    return repo / root


def closed_measurement(
    raw: bytes, *, handle: UUID, identity: ProfileIdentity,
    outcome: TaskPerformanceOutcome,
) -> dict[str, object]:
    """Refuse an automatic or foreign close before projecting its summary."""
    stopped = _Stopped.model_validate_json(raw)
    _verify_close(stopped, handle, identity, outcome)
    return summarize_profile(stopped.profile)


def _verify_close(
    stopped: _Stopped | _ItemStopped, handle: UUID, identity: ProfileIdentity,
    outcome: TaskPerformanceOutcome,
) -> None:
    profile = stopped.profile
    if (
        stopped.handle != handle or stopped.end_reason != profile.end_reason
        or profile.identity != identity
    ):
        raise MachineApiError("closed profile does not match the task or handle")
    if profile.end_reason != "explicit_stop" or profile.outcome != outcome:
        raise MachineApiError("profile closed before the workflow command did")


def summarize_profile(profile: _Profile) -> dict[str, object]:
    """Project the same closed interval as the native summarizeClosedTaskProfile."""
    machine_cpu = profile.cpu.value
    worker = profile.processes.worker
    worker_cpu = worker.cpu.value
    return {
        "task_kind": "workflow-task",
        "outcome": profile.outcome,
        "started_at": profile.started_at,
        "finished_at": profile.finished_at,
        "elapsed_ms": profile.elapsed_ms,
        "machine_cpu_busy_pct": min(100, machine_cpu.user + machine_cpu.system)
        if machine_cpu else None,
        "machine_cpu_steal_pct": machine_cpu.steal if machine_cpu else None,
        "machine_memory_available_min_kib": profile.machine_available_min_kb,
        "worker_rss_peak_kib": worker.sampled_rss_max_kb,
        "worker_cpu_time_ms": worker_cpu.cpu_time_ms if worker_cpu else None,
    }


def record_request(
    *, date: str, identity: WriterIdentity, measurement: Mapping[str, object],
) -> dict[str, object]:
    if identity.job is not None or identity.producer != PRODUCER:
        raise MachineApiError("native recording requires its declared pipeline task writer")
    return {
        "date": date,
        "writer": identity.model_dump(mode="json", exclude={"job", "producer"}),
        "measurement": dict(measurement),
    }
