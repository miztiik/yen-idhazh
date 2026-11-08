"""How are independent scorer owners closed after the phase's machine measurement?"""

import asyncio
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.shared.contracts.service_settings import WorkerSettings
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

from .contracts import PipelineError, RunIdentity, ServerOutcome
from .control import HostReady, ServiceStopped
from .failures import WorkflowError
from .host_reader import HonoServerReader, MachineUsage
from .http import loopback_url
from .llama import OwnedLlama
from .phase_contracts import PhaseShutdown
from .scorer_control import ScorerReady, ScorerStopped
from .scorer_evidence import ScorerApiEvidence
from .services import OwnedService
from .settings import PipelineSettings


async def guard_work[Result](
    work: Awaitable[Result],
    service: OwnedService | OwnedLlama,
    pipeline: PipelineSettings,
) -> Result:
    async def watch() -> None:
        while True:
            service.check_alive()
            await asyncio.sleep(pipeline.poll_interval_ms / 1000)

    task, watcher = asyncio.ensure_future(work), asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait((task, watcher), return_when=asyncio.FIRST_COMPLETED)
        # A completed native result survives a subsequent child-exit observation.
        if task not in done:
            await watcher
        return await task
    finally:
        for pending in (task, watcher):
            pending.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)


@dataclass
class ScorerService:
    scorer: ApiComponent
    api_settings: ApiSettings
    worker_settings: WorkerSettings
    owner: OwnedService | None = None
    started: float | None = None
    startup_ms: float | None = None
    health: ApiHealth | None = None
    stopped: bool | None = None
    errors: list[PipelineError] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.api_settings.enabled_routes != (self.scorer,):
            raise ValueError("A scorer owner requires its explicitly selected API settings")

    @property
    def origin(self) -> str:
        listener = self.api_settings.listener
        return loopback_url(listener.host, listener.port)

    def retain_error(self, error: PipelineError) -> None:
        scoped = WorkflowError(
            error.code,
            error.phase,
            "hhem" if self.scorer == "hhem" else "unieval" if self.scorer == "unieval" else "api",
            error.http_status,
            source_code=error.source_code,
        ).error
        if scoped not in self.errors:
            self.errors.append(scoped)

    def observe_health(self, health: ApiHealth) -> None:
        previous = self.health
        self.health = health
        try:
            self.evidence()
        except ValueError:
            self.health = previous
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "api") from None

    def evidence(self) -> ScorerApiEvidence:
        owner = self.owner
        ready = owner.ready if owner is not None and isinstance(owner.ready, ScorerReady) else None
        stopped = (
            owner.stopped
            if owner is not None and isinstance(owner.stopped, ScorerStopped)
            else None
        )
        observed = getattr(self.health, self.scorer) if self.health is not None else None
        worker = observed.worker if observed is not None else None
        exit_observed = (
            stopped.worker_exit
            if stopped is not None
            else WorkerExit(
                pid=worker.pid if worker is not None else None,
                exit_code=None,
                confirmed=False if worker is not None else None,
            )
        )
        log = stopped or self.health or ready
        return ScorerApiEvidence(
            scorer=self.scorer,
            listener=self.api_settings.listener,
            process=owner.expected_process if owner is not None else None,
            service_instance_id=ready.service_instance_id if ready is not None else None,
            health=self.health,
            worker_exit=exit_observed,
            outcome=ServerOutcome(
                server_name="fastapi-server",
                startup=(
                    "ready"
                    if self.health is not None and self.health.status == "ready"
                    else "failed"
                    if self.started is not None
                    else "not_started"
                ),
                startup_ms=self.startup_ms,
                shutdown=(
                    "stopped" if self.stopped is True else "failed"
                    if self.stopped is False else "not_started"
                ),
                exit_code=owner.process.poll() if owner is not None else None,
                log_filename=log.log_file if log is not None else None,
                log_available=log.log_available if log is not None else False,
                error_code=stopped.error_code if stopped is not None else None,
                cleanup_error_code=stopped.cleanup_error_code if stopped is not None else None,
            ),
            errors=tuple(self.errors),
        )

    def close(self) -> None:
        if self.owner is None:
            return
        try:
            self.owner.close(
                self.api_settings.shutdown_timeout_ms
                + self.worker_settings.shutdown_timeout_ms
                + self.worker_settings.forced_stop_ms
            )
            self.stopped = True
        except WorkflowError as error:
            self.stopped = False
            self.retain_error(error.error)
        except OSError:
            self.stopped = False
            self.retain_error(WorkflowError("SERVICE_STOP_FAILED", "cleanup", "api").error)
        failure = self.owner.startup_failure
        if failure is not None:
            self.retain_error(
                WorkflowError(
                    "STARTUP_FAILED", "startup", "api", failure.http_status,
                    source_code=failure.error_code,
                ).error
            )


@dataclass
class PhaseServices:
    run: RunIdentity
    scorer_apis: dict[ApiComponent, ScorerService] = field(default_factory=dict)
    host: OwnedService | None = None
    native: OwnedLlama | None = None
    host_stopped: bool | None = None
    llama_stopped: bool | None = None
    machine: MachineUsage | None = None
    servers: list[HonoServerReader | ServerOutcome] = field(default_factory=list)

    def shutdown(self) -> PhaseShutdown:
        return PhaseShutdown(
            host_stopped=self.host_stopped,
            llama_stopped=self.llama_stopped,
        )

    def close(
        self,
        errors: list[PipelineError],
        work_complete: bool,
        *,
        pipeline: PipelineSettings,
    ) -> None:
        if self.host is not None:
            host_cleanup: PipelineError | None = None
            try:
                if isinstance(self.host.ready, HostReady):
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
            if isinstance(self.host.stopped, ServiceStopped):
                if (
                    isinstance(self.host.ready, HostReady)
                    and self.host.stopped.error_code is not None
                ):
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
                    self.servers.append(self.host.stopped.server)
            if host_cleanup is not None:
                errors.append(host_cleanup)
        # The closing machine sample is complete before either API owner is stopped.
        if self.scorer_apis:
            with ThreadPoolExecutor(max_workers=len(self.scorer_apis)) as closing:
                for future in [
                    closing.submit(api.close) for api in self.scorer_apis.values()
                ]:
                    future.result()
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
