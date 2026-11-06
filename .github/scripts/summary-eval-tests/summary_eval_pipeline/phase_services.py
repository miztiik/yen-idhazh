"""How are a phase's fixed owned services closed without replacing its original failure?"""

import time
from dataclasses import dataclass, field

from hhem_evaluator.contracts.api_health import ApiHealth
from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.contracts.unieval_settings import UnievalSettings

from .contracts import PipelineError, RunIdentity, ServerOutcome, ServiceShutdown
from .control import HostReady
from .failures import WorkflowError
from .host_reader import MachineUsage
from .llama import OwnedLlama
from .services import OwnedService
from .settings import PipelineSettings


@dataclass
class PhaseServices:
    run: RunIdentity
    api: OwnedService | None = None
    host: OwnedService | None = None
    native: OwnedLlama | None = None
    health: ApiHealth | None = None
    api_started: float | None = None
    startup_ms: float | None = None
    api_stopped: bool | None = None
    host_stopped: bool | None = None
    llama_stopped: bool | None = None
    machine: MachineUsage | None = None
    servers: list[ServerOutcome] = field(default_factory=list)

    def shutdown(self) -> ServiceShutdown:
        return ServiceShutdown(
            api_stopped=self.api_stopped,
            host_stopped=self.host_stopped,
            llama_stopped=self.llama_stopped,
            worker_exit_confirmed=(
                self.api.stopped.worker_exit_confirmed
                if self.api is not None and self.api.stopped is not None
                else None
            ),
            unieval_worker_exit_confirmed=(
                self.api.stopped.unieval_worker_exit_confirmed
                if self.api is not None and self.api.stopped is not None
                else None
            ),
        )

    def close(
        self,
        settings: ServiceSettings | None,
        shared: ApiSettings | None,
        errors: list[PipelineError],
        work_complete: bool,
        unieval_settings: UnievalSettings | None = None,
        *,
        pipeline: PipelineSettings,
    ) -> None:
        if self.host is not None:
            host_cleanup: PipelineError | None = None
            try:
                if self.host.ready is not None:
                    self.host.finish_measurement("success" if work_complete else "error")
            except WorkflowError as error:
                errors.append(error.error)
            try:
                timeout = (
                    self.host.ready.lifecycle_timeout_ms + pipeline.host_stop_grace_ms
                    if isinstance(self.host.ready, HostReady)
                    else pipeline.host_shutdown_timeout_ms
                )
                self.host.close(timeout)
                self.host_stopped = True
            except WorkflowError as error:
                self.host_stopped = False
                host_cleanup = error.error
            except OSError:
                self.host_stopped = False
                host_cleanup = WorkflowError("SERVICE_STOP_FAILED", "cleanup", "host").error
            if self.host.startup_failure is not None:
                failure = self.host.startup_failure
                original = WorkflowError(
                    "STARTUP_FAILED",
                    "startup",
                    "host",
                    failure.http_status,
                    source_code=failure.error_code,
                ).error
                if original not in errors:
                    errors.append(original)
            if self.host.stopped is not None:
                if self.host.ready is not None and self.host.stopped.error_code is not None:
                    errors.append(
                        WorkflowError(
                            "HOST_FAILED",
                            "host",
                            "host",
                            self.host.stopped.http_status,
                            source_code=self.host.stopped.error_code,
                        ).error
                    )
                self.machine = self.host.stopped.machine
                if self.host.stopped.server is not None:
                    self.servers.append(
                        ServerOutcome.model_validate_json(
                            self.host.stopped.server.model_dump_json()
                        )
                    )
            if host_cleanup is not None:
                errors.append(host_cleanup)
        if self.api is not None:
            if settings is None or shared is None:
                raise ValueError("An evaluator child requires its validated shutdown settings")
            try:
                self.api.close(
                    shared.shutdown_timeout_ms
                    + max(
                        settings.worker.forced_stop_ms,
                        unieval_settings.worker.forced_stop_ms
                        if unieval_settings is not None
                        else 0,
                    )
                )
                self.api_stopped = True
            except WorkflowError as error:
                self.api_stopped = False
                errors.append(error.error)
            except OSError:
                self.api_stopped = False
                errors.append(WorkflowError("SERVICE_STOP_FAILED", "cleanup", "api").error)
            if self.api.stopped is not None:
                if self.api.stopped.worker_exit_confirmed is False:
                    errors.append(WorkflowError("SERVICE_STOP_FAILED", "cleanup", "hhem").error)
                if self.api.stopped.unieval_worker_exit_confirmed is False:
                    errors.append(WorkflowError("SERVICE_STOP_FAILED", "cleanup", "unieval").error)
        if self.api_started is not None:
            day = self.run.started_at.strftime("%Y_%m_%d")
            self.servers.append(
                ServerOutcome(
                    server_name="fastapi-server",
                    startup=(
                        "ready"
                        if self.health is not None and self.health.status == "ready"
                        else "failed"
                    ),
                    startup_ms=self.startup_ms
                    if self.startup_ms is not None
                    else ((time.monotonic() - self.api_started) * 1000),
                    shutdown=(
                        "not_started"
                        if self.api is None
                        else "stopped"
                        if self.api_stopped
                        else "failed"
                    ),
                    exit_code=self.api.process.returncode if self.api is not None else None,
                    log_filename=f"fastapi-server_{day}_{self.run.run_id}_{self.run.attempt}.log",
                    log_available=(
                        self.api.stopped.log_available
                        if self.api is not None
                        and self.api.stopped is not None
                        and self.api.stopped.log_available is not None
                        else self.health.log_available
                        if self.health is not None
                        else False
                    ),
                )
            )
        if self.native is not None:
            try:
                self.native.close()
                self.llama_stopped = (
                    self.native.process is not None and self.native.process.poll() is not None
                )
            except WorkflowError as error:
                self.llama_stopped = False
                errors.append(error.error)
            self.servers.append(self.native.outcome())
